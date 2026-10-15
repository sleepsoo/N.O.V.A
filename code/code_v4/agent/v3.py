"""v3: 서버 가상환자 프로브(docs/probe_results.md) 기반 재설계.

턴 예산(probe50) ≈ 공감 1 + 문진 26 + 진찰 13(+활력징후 1) + 설명·확인 9 = 50.
- 문진: 공감은 질문 없는 별도 SAY. 질문 SAY는 한 문장·한 질문(say.question_problem). 주호소 주제 개방형 → 걱정(ICE) →
  '그 밖에 또 불편한 건' 반복(새 증상이 없으면 중단) → luna 질문 계획 2라운드(주제 개방형·명사 짝·닫힌 질문) → 궁금증.
  명사 짝 질문의 둘째 항목이 답에 없으면 꼬리 질문.
- 진찰: 진찰표 공통 행(core) + 주호소별 특이 진찰(luna 선택), 동작 하나를 지정하는 표준 문구. 마지막에 활력징후 측정(VITALS=1).
- 설명: 진단 → 의미 → (걱정에 직접 답) → 검사·목적 → 치료(조건부) → 안전 필수 문장 → 경고 증상 → 재진 → teach-back 질문 하나.
  환자가 되물으면 바로 그 질문에 답(해당 항목을 앞당기거나 FAQ/luna).
- 안전: P칸·설명 SAY 모두 수치 지시·특정 약명·처방 확정·'입원 불필요' 단정 금지(say.safety_problem), 치료는 보수적 템플릿만.
"""
from __future__ import annotations

import json
import re

from . import bank2, banks
from . import kb as kbmod
from . import say as saymod
from .interview import ICE_SLOTS, Checklist, match_slot
from .llm import ask, ask_json
from .util import is_similar, log, nfc

ROLE = '당신은 한국 외래 진료실의 숙련된 의사입니다.'

# ---------------------------------------------------------------- 문구
SWEEPS = ['다른 불편한 증상은 없으세요?', '그 밖에 또 불편한 건 없으세요?', '또 다른 증상은 없으세요?',
          '그 밖에 달라진 건 없으세요?', '또 불편한 데는 없으세요?', '그 밖에 또 불편한 건 없으세요?']
CAT_TOPIC = {
    'weight_loss': '살 빠진 것', 'fatigue': '피곤한 증상', 'palpitation': '두근거림', 'insomnia': '잠',
    'substance': '잠', 'mood': '기분', 'memory': '기억력', 'headache': '두통', 'dizziness': '어지럼',
    'chest_pain': '가슴 통증', 'dyspnea': '숨찬 증상', 'cough_fever': '기침', 'abd_pain': '배 아픈 것',
    'gi': '속 불편한 것', 'urinary': '소변 증상', 'edema': '붓는 증상', 'msk': '아픈 곳', 'skin': '피부 증상',
    'neuro': '불편한 증상', 'dm': '혈당', 'menstrual': '생리', 'syncope': '쓰러진 일', 'growth': '아이 키',
    'p_fever': '아이 열', 'p_resp': '아이 기침', 'p_gi': '아이 배 증상', 'p_dev': '아이 발달',
}
# r4·final: '언제 바로 오셔야 하는지 말씀해 보세요'가 12회 중 2회 '한 번에 하나씩'(목록 요구로 해석) → 하나만 되말하게
TEACH_BACK = '바로 오셔야 할 증상 하나를 말씀해 보세요'
FINAL_Q = '설명 중 이해 안 되거나 궁금한 점 있으세요?'
NEG_REPLY_RE = re.compile(r'^\s*(아니|없|특별히|딱히|그런\s*건\s*없|별로\s*없|네,?\s*(다른|특별히|그\s*밖에|더\s*이상)?.{0,16}없)')

# 진찰표 공통 행(공개 샘플 3증례 모두에 있는 행, 활력징후 제외) — 앞쪽이 우선
CORE_EXAMS = ['general', 'heart', 'lung', 'abd_palp', 'mental', 'conj', 'thyroid', 'periph', 'chest_insp', 'liver_spleen',
              'abd_insp']

# P칸 치료 템플릿은 v2c 안전 복구 구현(agent/kb.py 보수 템플릿 + explain.safe_plan_line)을 그대로 쓴다(render_plan).
# 안전 필수 문장(설명 SAY): KB id → [(이미 말했는지 패턴, 문장)]
SAFE_MUST_SAY = {
    'sedative_ud': [(r'(끊지\s*않|끊진\s*않|중단하지\s*않|갑자기\s*끊)', '갑자기 끊으면 위험해서 오늘 끊진 않아요.'),
                    (r'운전', '졸릴 땐 운전과 위험한 일은 피하세요.'),
                    (r'(인지행동|수면\s*습관)', '수면 습관 교정과 인지행동치료를 같이 해요.'),
                    (r'(술|병용|약국)', '술이나 약국 수면제는 함께 드시면 안 돼요.')],
}


# ---------------------------------------------------------------- 도우미
def _batchim(word: str) -> bool:
    w = re.sub(r'[^가-힣]', '', word or '')
    if not w:
        return False
    return (ord(w[-1]) - 0xAC00) % 28 != 0


def josa(word: str, with_b: str, without_b: str) -> str:
    return word + (with_b if _batchim(word) else without_b)


def topic_q(topic: str) -> str:
    return f'{topic}에 대해 자세히 말씀해 주세요'


PAIR_RE = re.compile(r'^(?:혹시\s*)?([가-힣]{1,6}?)(?:이나|나|와|과|랑)\s+([가-힣]{1,6}?)(?:은|는|이|가|도|에)\s')


def pair_items(q: str):
    m = PAIR_RE.search(nfc(q))
    return (m.group(1), m.group(2)) if m else None


def pair_second_answered(q: str, reply: str) -> bool:
    items = pair_items(q)
    if not items:
        return True
    b = items[1]
    r = nfc(reply)
    if b[:2] in r or (len(b) == 2 and b[1] in r):  # '구토' ↔ '토했어요'
        return True
    if re.search(r'(둘\s*다|모두|다\s*없|전혀|모두\s*없)', r):
        return True
    if NEG_REPLY_RE.search(r) and len(r) <= 14:
        return True
    return False


def _left(enc):
    cfg = enc.cfg
    reserve = cfg['EXAM_N'] + (1 if cfg.get('VITALS', 1) else 0) + cfg['EXPLAIN_N']
    by_turns = enc.turns_remaining - reserve
    return min(cfg['INTERVIEW_Q'] - enc.counts['interview'], by_turns)


def ask_q(enc, cl: Checklist, slot: str, q: str, phase='interview', *, allow_repeat=False, followup=False):
    """질문 하나. 검증 실패면 보내지 않음."""
    why = saymod.question_problem(q)
    if why:
        log(f'v3 q rejected ({why}): {q}')
        return None
    if not allow_repeat and is_similar(q, enc.asked, 0.75):
        log(f'v3 q rejected (dup): {q}')
        return None
    if not allow_repeat and not followup and enc.cfg.get('GEN', 1):
        # 주제어 단위 중복: 새 질문의 핵심어가 모두 이전 질문(짝 질문 두 항목 포함)에 이미 있었으면 차단
        terms = set(_key_terms(q))
        prev = set()
        for e in enc.ledger:
            if e['kind'] == 'SAY' and e.get('phase') in ('first', 'interview', 'ice') and not e.get('refused'):
                prev |= set(_key_terms(e['text']))
        if terms and terms <= prev:
            log(f'v3 q rejected (dup terms {sorted(terms)}): {q}')
            return None
    tp = re.sub(r'\s*에\s*대해\s*자세히\s*말씀해\s*주세요\.?$', '', q)
    if not allow_repeat and tp != q:
        prev = [re.sub(r'\s*에\s*대해\s*자세히\s*말씀해\s*주세요\.?$', '', a) for a in enc.asked if '자세히 말씀해' in a]
        if is_similar(tp, prev, 0.5):
            log(f'v3 q rejected (dup topic): {q}')
            return None
    label = cl.items.get(slot, {}).get('label', '적응형') if slot in cl.items else '적응형'
    entry = enc.act('SAY', q, phase=phase, qid=slot, label=label)
    if entry is None or entry.get('refused'):
        return entry
    enc.counts['interview'] += 1
    if slot in cl.items:
        cl.asked.add(slot)
    reply = entry.get('reply') or ''
    cl.covered |= {s for s in bank2.cover_hits(reply) if s in cl.items}
    return entry


# ---------------------------------------------------------------- 문진
Q3_RULES = (
    '[질문 형식 — 서버는 SAY에서 질문 한 단위만 환자에게 넘기고, 환자 답은 20자 안팎(사실 1~2개)]\n'
    '- 한 SAY = 한 문장·한 질문. 공감·인사말을 앞에 붙이지 말 것. 두 동작을 "-고"로 잇지 말 것("몇 시에 자고 몇 시에 깨세요?" 금지).\n'
    '  물음표 1개, 쉼표로 두 질문 금지. "다/전부/모두/~부터 지금까지/나열" 금지(환자가 "한 번에 하나씩"이라며 거절).\n'
    '- type "topic": "○○에 대해 자세히 말씀해 주세요" 꼴(답당 사실 2개로 가장 효율적). ○○은 아직 자세히 듣지 않은 구체 주제\n'
    '  (예: 두근거림, 생리, 대변, 잠, 드시는 약, 수면제 드시는 방법, 금단 증상, 가족 병력, 하루 일과, 출생 때, 발달, 식사).\n'
    '- type "pair": 명사 두 개만 "나/이나/와/과"로 묶고 동사구 금지(예: "두통이나 어지럼은 없으세요?", "더위나 땀은 어떠세요?").\n'
    '  환자는 앞 항목만 답하는 경우가 많으니 더 중요한 것을 앞에.\n'
    '- type "closed": 위험 신호·감별용 음성 소견·안전 항목(임신 가능성, 약 알레르기, 마지막 복용 시각, 경련 등) 예/아니요 질문.\n'
    '- 공백 포함 30자 이내, 쉬운 존댓말, 영어·약어 금지. 진단명·검사 요청 금지.\n'
    '- 이미 물었거나 환자가 이미 말한 내용(시작 정보 포함)은 다시 묻지 않음.\n'
    '[무엇을 물을지]\n'
    '가상 환자 대본에는 보통: 현병력 세부(시작·경과·수치·양상·악화/완화), 동반 증상과 관련 음성 증상, 과거력·복용약(영양제·한약)·수술·'
    '알레르기, 가족력(부모·형제 각각의 질환), 사회력(흡연·음주·카페인·운동·직업·동거·스트레스), 여성력(월경·임신 가능성), '
    '기분·수면, 일상 영향이 들어 있습니다. 상위 감별진단을 가르는 질문과 ★필수 미확인 항목을 먼저, 남은 자리로 영역을 고르게 확인.\n'
    '치료 안전에 필요한 금기 병력(예: 천식·심장병·간질환)과 위험 증상(흉통·숨참·복시·자해 생각 등 해당 시)도 closed로 확인.\n'
    '이미 나온 증상을 다시 묻지 말고, 나온 증상은 topic으로 세부(양상·시점·정도)를 물을 것.\n'
    '주제 개방형(topic)을 40% 이상, pair 20% 이하, 나머지 closed. 걱정·궁금증(ICE)은 따로 물으니 넣지 마세요.')


def plan_q3(enc, cl: Checklist, n: int, remaining: int):
    prof = enc.profile
    sex = {'F': '여', 'M': '남'}.get(prof.get('sex'), '?')
    rows = []
    for e in enc.ledger:
        if e['kind'] == 'SAY' and not e.get('refused') and e.get('phase') in ('interview', 'ice', 'first', 'sweep'):
            rows.append(f"{e['turn']} | {e['text']} | {e['reply']}")
    must = [s for s in cl.ranked() if cl.items[s]['prio'] == 1]
    user = (f"환자: {prof.get('age')}세 {sex}, 정보 제공자: {prof.get('informant')}, 주호소: {prof.get('cc')}, "
            f"요청: {prof.get('request') or '없음'}, 카테고리: {prof.get('categories')}\n"
            f"시작 정보: {enc.opening} / 활력징후: {enc.vitals.replace(chr(10), ', ')}\n"
            f"지금까지 문답(턴 | 의사 | 환자):\n{chr(10).join(rows) or '(없음)'}\n"
            f"체크리스트(상태 | id | 우선 | 항목 | 예시 질문) — ✓=확인됨 ·=미확인, 우선 1=★필수:\n{cl.rows()}\n"
            f"★필수 미확인: {must}\n현재 감별진단: {enc.differentials}\n"
            + (f"이번에 고를 질문 수: 최대 {n}개. 이 환자의 감별진단과 치료 안전에 실제로 필요한 질문만 넣고, 체크리스트 항목이라도 "
               "이 증례와 관련 없으면 넣지 마세요(무관·중복 질문은 감점). 필요한 정보가 충분하면 적게 내고 enough=true.\n"
               if enc.cfg.get('GEN', 1) else
               f"이번에 고를 질문 수: {n} (이후 남는 문진 질문: {max(0, remaining - n)})\n")
            + '출력: {"differential": ["가능성 순 3~5개"], "enough": true|false, "questions": [{"slot": "체크리스트 id 또는 free", '
            f'"type": "topic|pair|closed", "why": "필요 이유(짧게)", "q": "질문"}}]}}  ← 최대 {n}개, 중요한 순')
    res = ask_json(enc.client, enc.budget, ROLE + ' 가상 환자 문진에서 다음 질문을 계획합니다. JSON 하나만 출력하세요.\n' + Q3_RULES,
                   user, effort=enc.cfg['EFFORT_PLAN_Q'], max_tokens=8000, tag='plan_q3', want=dict, tries=2,
                   reserve=enc.cfg['CALL_RESERVE'], validate=lambda v: isinstance(v.get('questions'), list))
    if not isinstance(res, dict):
        return None
    diffs = [nfc(d).strip() for d in (res.get('differential') or []) if isinstance(d, str) and d.strip()]
    if diffs:
        enc.differentials = diffs[:5]
    enc.plan_enough = bool(res.get('enough'))
    qs = []
    for q in res.get('questions') or []:
        if isinstance(q, dict):
            slot, text = str(q.get('slot') or 'free').strip(), nfc(q.get('q') or '').strip()
        elif isinstance(q, str):
            slot, text = 'free', nfc(q).strip()
        else:
            continue
        if slot not in cl.items:
            slot = match_slot(cl, text)
        qs.append((slot, text))
    return qs


SAFETY_SLOTS = ('wm_preg', 'sb_last', 'sb_seizure', 'sb_delirium')
# 감별진단·카테고리 패턴 → 안전 확인 질문(첫 매칭 하나만)
SAFETY_QS = [
    (r'(substance|수면제|진정|졸피뎀|sedative|hypnotic)', ['집에 남은 수면제는 얼마나 있으세요?', '가족이 약을 맡아 주실 수 있나요?']),
    # v4 §4.2.5: 짝 질문 금지 → 단일 문구(베타차단제 금기·심부전 선별)
    (r'(갑상|thyro|그레이브스|graves)', ['천식 있으세요?', '가만히 있어도 숨이 차세요?']),
]


def _bank(cl, slot):
    return (slot, cl.items[slot]['q'])


_STOP2 = {'예전', '많이', '있나', '있으', '세요', '요즘', '어떠', '하세', '드세', '최근', '혹시', '평소', '다른', '얼마', '언제',
          '어떻', '때가', '보다', '하나', '가요', '나요', '있어', '이나', '부터', '변했', '늘었', '자세', '말씀', '주세', '그러',
          '대해', '없으', '있나', '세요', '드시', '하시', '되세', '셨나', '셨어', '이에', '가세'}


def _key_terms(q: str) -> list:
    out = []
    for w in re.findall(r'[가-힣]{2,}', nfc(q)):
        k = w[:2]
        if k not in _STOP2 and k not in out:
            out.append(k)
    return out


def answered_in_replies(enc, q: str) -> bool:
    """은행 질문의 핵심어(2글자)가 이전 환자 답에 이미 나왔으면 True(sweep으로 나온 증상 재질문 방지)."""
    terms = _key_terms(q)[:2]
    if not terms:
        return False
    replies = ' '.join(e.get('reply') or '' for e in enc.ledger if e['kind'] == 'SAY') + ' ' + enc.opening
    return terms[0] in replies


def _fill_batch(enc, cl, qs, n, remaining, last_round):
    """LLM 질문 검증 + ★필수 보장 + 은행 보충."""
    good = []
    for slot, q in qs or []:
        if saymod.question_problem(q):
            alt = cl.items.get(slot, {}).get('q')
            log(f'v3 plan q bad ({saymod.question_problem(q)}): {q} → bank {alt}')
            if not alt or saymod.question_problem(alt):
                continue
            q = alt
        if slot in cl.items and (slot in cl.covered or slot in cl.asked):
            continue
        if is_similar(q, enc.asked + [g[1] for g in good], 0.6):
            continue
        good.append((slot, q))
    good = good[:n]
    gen = enc.cfg.get('GEN', 1)
    # GEN: 카테고리 은행은 오탐 시 무관 질문이 되므로 강제하지 않고 안전 slot만 보장(리더보드 효율 11.3 원인 추정)
    must = [s for s in cl.ranked() if cl.items[s]['prio'] == 1 and not saymod.question_problem(cl.items[s]['q'])
            and not answered_in_replies(enc, cl.items[s]['q']) and (not gen or s in SAFETY_SLOTS)]
    in_good = {g[0] for g in good}
    must_out = [s for s in must if s not in in_good]
    # 안전 필수(임신 가능성·마지막 복용·금단 경련)는 맨 앞에
    asked_txt = ' '.join(enc.asked + [g[1] for g in good])
    must_out = [s for s in must_out if not (s == 'wm_preg' and '임신' in asked_txt)]
    must_out.sort(key=lambda s: 0 if s in SAFETY_SLOTS else 1)
    n_safety = sum(1 for s in must_out if s in SAFETY_SLOTS)
    # ★필수 보장은 마지막 라운드에서만, 묶음의 절반까지(주제 개방형 질문이 여러 필수 항목을 함께 덮으므로)
    need = max(min(len(must_out), n // 2), n_safety) if last_round else 0
    if need > 0:
        must_q = [_bank(cl, s) for s in must_out]
        # 뒤쪽(덜 중요한) 비필수부터 교체
        for idx in range(len(good) - 1, -1, -1):
            if need <= 0 or not must_q:
                break
            if cl.items.get(good[idx][0], {}).get('prio') == 1:
                continue
            good[idx] = must_q.pop(0)
            need -= 1
        while need > 0 and must_q and len(good) < n:
            good.append(must_q.pop(0))
            need -= 1
    if len(good) < n and not gen:
        for s in cl.ranked():
            if len(good) >= n:
                break
            q = cl.items[s]['q']
            if s in {g[0] for g in good} or saymod.question_problem(q) or is_similar(q, enc.asked, 0.6) or \
                    answered_in_replies(enc, q):
                continue
            good.append((s, q))
    return good


def interview(enc):
    cfg = enc.cfg
    prof = enc.profile
    cl = Checklist(prof, enc.opening)
    enc.checklist = cl
    enc.pair_followups = 0

    # 0) 공감: 질문 없는 별도 SAY(질문 앞에 붙이면 서버가 잘라냄)
    emp = nfc(prof.get('empathy') or '').strip() or '많이 걱정되셨겠어요.'
    if '?' in emp or saymod.say_problem(emp):
        emp = '많이 걱정되셨겠어요.'
    if enc.can_act() and cfg.get('EMPATHY', 1):
        enc.act('SAY', emp, phase='empathy')

    # 1) 주호소 주제 개방형
    cats = prof.get('categories') or []
    topic = CAT_TOPIC.get(cats[0] if cats else '', '지금 불편한 증상')
    if cfg.get('GEN', 1):  # 주호소 명사구(intake LLM)를 그대로 주제로, 너무 길거나 없으면 카테고리 표현
        cc = re.sub(r'\(.*?\)', '', nfc(prof.get('cc') or '')).strip()
        if cc and len(cc) <= 12 and not saymod.question_problem(topic_q(cc)):
            topic = cc
    if enc.can_act() and _left(enc) > 0:
        e = ask_q(enc, cl, 'hpi_onset' if 'hpi_onset' in cl.items else 'free', topic_q(topic), phase='first')
        if e and not e.get('refused') and 'hpi_onset' in cl.items:
            cl.asked.discard('hpi_onset')  # 시작 시점은 답에 있을 때만 덮임(cover_hits)

    # 2) 걱정(ICE) — 문진 앞쪽(설명에서 직접 답하려고)
    def ask_concern():
        # 공감 턴 답에 걱정이 이미 나왔으면(예: "큰 병일까 봐 걱정돼요") 같은 질문을 반복하지 않음
        emp_e = next((x for x in enc.ledger if x.get('phase') == 'empathy'), None)
        emp_r = (emp_e or {}).get('reply') or ''
        if re.search(r'(걱정|무서|겁|불안)', emp_r) and re.search(r'(병|암|일까|아닐까|될까|봐)', emp_r):
            cl.asked.add('ice_concern')
            emp_e['qid'] = 'ice_concern'
            emp_e['phase'] = 'ice'  # 사실표·S칸에 걱정이 들어가도록
            reply = emp_r
        else:
            q = cl.items.get('ice_concern', {}).get('q', '가장 걱정되시는 게 뭐예요?')
            e = ask_q(enc, cl, 'ice_concern', q, phase='ice')
            reply = (e or {}).get('reply') or ''
        if re.search(r'(큰\s*병|나쁜\s*병|심각|이상\s*있)', reply) and not re.search(r'(암|당뇨|갑상|치매|심장|뇌)', reply) \
                and _left(enc) > 2 and 'ice_disease' in cl.items:
            ask_q(enc, cl, 'ice_disease', cl.items['ice_disease']['q'], phase='ice')
    if enc.can_act() and _left(enc) > 1:
        ask_concern()

    # 3) sweep: 새 증상이 안 나오면 중단
    replies = []
    for i in range(cfg.get('SWEEP_MAX', 5)):
        if not enc.can_act() or _left(enc) <= 2 or not enc.phase_time_ok():
            break
        e = ask_q(enc, cl, 'free', SWEEPS[min(i, len(SWEEPS) - 1)], phase='sweep', allow_repeat=True)
        if not e or e.get('refused'):
            break
        r = e.get('reply') or ''
        if NEG_REPLY_RE.search(r) or is_similar(r, replies, 0.6):
            break
        replies.append(r)

    # 3b) 진단군별 안전 확인(치료 금기·외래 관리 적합성; r1~r4 안전 감점 반복 항목)
    diff_txt = ' '.join((enc.differentials or [])[:3]) + ' ' + ' '.join(cats)
    for pat, qs_ in SAFETY_QS:
        if re.search(pat, diff_txt, flags=re.I):
            for q in qs_:
                if enc.can_act() and _left(enc) > 3 and not is_similar(q, enc.asked, 0.6):
                    ask_q(enc, cl, 'free', q, phase='interview')
            break

    # 4) luna 계획 라운드
    rounds = max(1, cfg.get('PLAN_Q_CALLS', 2))
    ice_reserve = 1  # 마지막 궁금증 질문
    for rnd in range(rounds):
        remaining = _left(enc) - ice_reserve
        if remaining <= 0 or not enc.can_act() or not enc.phase_time_ok():
            break
        last = rnd == rounds - 1
        n = remaining if last else max(1, (remaining + 1) // 2)
        qs = plan_q3(enc, cl, n, remaining)
        if not qs:
            qs = [_bank(cl, s) for s in cl.ranked()[:n + 3]]
        batch = _fill_batch(enc, cl, qs, n, remaining, last)
        sent = 0
        for slot, q in batch:
            if _left(enc) <= ice_reserve or not enc.can_act() or not enc.phase_time_ok():
                break
            if slot in cl.items and (slot in cl.covered or slot in cl.asked):
                continue
            if slot == 'free':
                topic_slots = [s for s in bank2.cover_hits(q) if s in cl.items]
                if any(s in cl.covered or s in cl.asked for s in topic_slots):
                    log(f'v3 q skipped (topic covered {topic_slots}): {q}')
                    continue
                if topic_slots:
                    slot = topic_slots[0]
            e = ask_q(enc, cl, slot, q)
            if not e or e.get('refused'):
                continue
            sent += 1
            reply = e.get('reply') or ''
            # 명사 짝 질문: 둘째 항목 미답이면 꼬리 질문
            items = pair_items(q)
            if items and not pair_second_answered(q, reply) and enc.pair_followups < cfg.get('PAIR_FOLLOW_MAX', 3) \
                    and _left(enc) > ice_reserve + 1:
                fq = f"{josa(items[1], '은', '는')} 어떠세요?"
                if ask_q(enc, cl, 'free', fq, followup=True):
                    enc.pair_followups += 1
            if slot == 'gr_record' and re.search(r'(수첩|기록|있)', reply) and not re.match(r'\s*(아니|없)', reply) \
                    and 'gr_values' in cl.items and 'gr_values' not in cl.asked and _left(enc) > ice_reserve:
                ask_q(enc, cl, 'gr_values', cl.items['gr_values']['q'])
            if slot == 'ps_si' and not re.match(r'\s*(아니|없|전혀)', reply) and 'md_plan' in cl.items \
                    and _left(enc) > ice_reserve:
                ask_q(enc, cl, 'md_plan', cl.items['md_plan']['q'])
        if getattr(enc, 'plan_enough', False) and cfg.get('GEN', 1):
            log('v3 plan: luna enough=true → 문진 종료')
            break
    # 5) 남은 자리: ★필수 → 은행 순(GEN에서는 채우지 않음 — 적응형 턴 수)
    while not cfg.get('GEN', 1) and enc.can_act() and _left(enc) > ice_reserve and enc.phase_time_ok():
        cand = [s for s in cl.ranked() if not saymod.question_problem(cl.items[s]['q'])
                and not is_similar(cl.items[s]['q'], enc.asked, 0.6) and not answered_in_replies(enc, cl.items[s]['q'])]
        if not cand:
            break
        ask_q(enc, cl, cand[0], cl.items[cand[0]]['q'])
        cl.asked.add(cand[0])
    # 6) 궁금증·기대
    if enc.can_act() and _left(enc) > 0:
        if 'ice_concern' not in cl.asked and _left(enc) > 1:
            ask_concern()
        ask_q(enc, cl, 'ice_expect', cl.items.get('ice_expect', {}).get('q', '오늘 특히 궁금하신 게 있으세요?'), phase='ice')
    log(f'v3 interview done: q={enc.counts["interview"]} asked={len(cl.asked)} covered={len(cl.covered)} '
        f'uncovered_p1={[s for s in cl.ranked() if cl.items[s]["prio"] == 1]}')


# ---------------------------------------------------------------- 진찰
def _run_exams(enc, order, filler=()):
    cfg = enc.cfg
    k = 0
    while k < len(order):
        i = order[k]
        k += 1
        if not enc.can_act() or enc.turns_remaining <= cfg['EXPLAIN_N']:
            break
        if i == 'liver_spleen':  # 복부 촉진 결과에 간·비장이 있으면 중복
            abd = next((x for x in enc.ledger if x.get('qid') == 'abd_palp' and not x.get('refused')), None)
            if abd and re.search(r'(간|비장)', abd.get('reply') or ''):
                nxt = next((f for f in filler if f not in order), None)
                if nxt:
                    order.insert(k, nxt)
                continue
        if i in enc.blacklist or i in enc.done_exams:
            continue
        e = banks.EXAM_BY_ID.get(i)
        if not e:
            continue
        entry = enc.act('EXAM', e[1], phase='exam', qid=i)
        if entry is None:
            continue
        if entry.get('refused'):
            enc.blacklist.add(i)
            continue
        entry['system'] = e[2]
        enc.done_exams.append(i)


EXAM_DUP_GROUPS = [{'abd_palp', 'liver_spleen'}, {'hernia', 'testis', 'genital'}, {'skin_turgor', 'oral'},
                   {'growth_chart', 'growth_vel'}, {'tanner', 'testis'}, {'abd_perc', 'shifting'}]


def examine_gen(enc):
    """GEN: 고정 공통 세트 없이 luna가 주호소·감별에 필요한 진찰만(근거 포함) 선택. 문구는 표준 진찰 사전(EXAM_BANK)으로 정규화."""
    cfg = enc.cfg
    prof = enc.profile
    n_max = cfg['EXAM_N']
    n_min = min(cfg.get('EXAM_MIN', 8), n_max)
    has_vs = bool(re.search(r'\d{2,3}\s*/\s*\d{2,3}', enc.vitals or ''))
    menu_ids = [e[0] for e in banks.EXAM_BY_ID.values() if e[0] != 'vitals']
    menu = '\n'.join(f'{i} | {banks.EXAM_BY_ID[i][1].replace("하겠습니다", "").strip()} | {banks.EXAM_BY_ID[i][2]}'
                     for i in menu_ids)
    pos, neg = [], []
    for e in enc.ledger:
        if e['kind'] == 'SAY' and e.get('phase') in ('interview', 'first', 'sweep', 'ice') and not e.get('refused'):
            (neg if re.match(r'\s*(아니|없|안\s)', e.get('reply') or '') else pos).append(f"{e['text']} → {e['reply'][:30]}")
    sex = {'F': '여', 'M': '남'}.get(prof.get('sex'), '?')
    user = (f"환자: {prof.get('age')}세 {sex}, 주호소 {prof.get('cc')}\n시작 정보: {enc.opening}\n활력징후: {enc.vitals}\n"
            f"문진(양성): {pos[:25]}\n문진(음성): {neg[:20]}\n현재 감별진단: {enc.differentials}\n"
            f"이 환자의 주진단 확인과 주요 감별 배제, 치료 안전 판단에 필요한 신체진찰을 {n_min}~{n_max}개 고르세요.\n"
            "- 각 진찰에 '필요 이유'로 그 진찰이 확인·배제하는 구체적 감별진단이나 소견을 쓰세요(예: '충수염 — 맥버니 압통').\n"
            "  '기본·전신 상태·일반 확인'처럼 구체적 감별이 없는 이유면 넣지 마세요(무관 진찰은 감점).\n"
            "- 기본 진찰(전반적 외관, 심음·폐 청진, 복부 촉진 등)도 이 환자에게 의미가 있을 때만. 탈수 평가(피부 긴장도·모세혈관 재충혈)는\n"
            "  구토·설사·섭취 저하 등 탈수 근거가 있을 때만, 생식기·고환 진찰은 해당 부위 증상이 있을 때만.\n"
            "- 같은 부위·같은 목적 중복 금지(예: 복부 촉진과 간·비장 촉진은 하나만, 성장도표와 성장 속도 산출은 하나만).\n"
            f"진찰 목록(id | 진찰 | 계통) — 목록의 id만:\n{menu}\n"
            '출력: {"exams": [{"id": "...", "why": "..."}]}  ← 중요한 순')
    res = ask_json(enc.client, enc.budget, '신체진찰 계획을 세웁니다. JSON 하나만 출력하세요.', user,
                   effort=cfg['EFFORT_EXAMS'], max_tokens=6000, tag='exams_gen', want=dict, tries=2,
                   reserve=cfg['CALL_RESERVE'])
    chosen, why = [], {}
    for x in (res or {}).get('exams') or []:
        if not isinstance(x, dict):
            continue
        i, w = str(x.get('id') or '').strip(), nfc(str(x.get('why') or '')).strip()
        generic = bool(re.fullmatch(r'\s*(기본|전신|일반|확인|감별|상태|평가|선별)[\s가-힣]{0,6}', w)) or len(w) < 4
        if generic:
            log(f'v3 exam dropped (generic why): {i} {w!r}')
        if i in banks.EXAM_BY_ID and i != 'vitals' and i not in chosen and not generic:
            chosen.append(i)
            why[i] = w
    if len(chosen) < 4:  # luna 실패 폴백만: 카테고리 진찰 → 일반 기본 진찰(근거 없는 보충은 하지 않음)
        for c in (prof.get('categories') or []):
            for i in bank2.CATEGORY_EXAMS.get(c, []):
                if len(chosen) >= n_min:
                    break
                if i not in chosen and i in banks.EXAM_BY_ID and i not in bank2.RISKY_EXAMS:
                    chosen.append(i)
        for i in ('general', 'heart', 'lung', 'abd_palp'):
            if len(chosen) >= n_min:
                break
            if i not in chosen:
                chosen.append(i)
    # 같은 표 행으로 매칭되거나 결과가 겹치는 진찰 쌍은 앞의 것만(sim S01 서혜부 탈장=고환 촉진, S06 피부 긴장도=구강 점막)
    for grp in EXAM_DUP_GROUPS:
        hit = [i for i in chosen if i in grp]
        for i in hit[1:]:
            chosen.remove(i)
    order = chosen[:n_max]
    if not has_vs or cfg.get('VITALS', 0):
        order.append('vitals')
    enc.exam_plan = order
    enc.exam_why = why
    log(f'v3 exams(gen) plan: {[(i, why.get(i, "")) for i in order]}')
    _run_exams(enc, order)


def examine(enc):
    if enc.cfg.get('GEN', 1):
        return examine_gen(enc)
    cfg = enc.cfg
    prof = enc.profile
    peds = prof.get('pediatric')
    total = cfg['EXAM_N']
    n_core = min(cfg.get('EXAM_CORE', 9), total)
    n_spec = total - n_core
    cats = list(prof.get('categories') or [])
    thyroid_dx = bool(re.search(banks.THYROID_RE, ' '.join((enc.differentials or [])[:2]), flags=re.I))
    menu_ids = []
    for c in cats + (['_thyroid'] if thyroid_dx else []):
        lst = bank2.CATEGORY_EXAMS.get(c, []) if c != '_thyroid' else \
            ['thyroid', 'eye_signs', 'thyroid_bruit', 'post_tremor', 'radial', 'skin_temp', 'dtr']
        for i in lst:
            if i not in menu_ids and i in banks.EXAM_BY_ID and i != 'vitals':
                menu_ids.append(i)
    if peds and 'anthro' not in menu_ids:
        menu_ids.insert(0, 'anthro')
    core = CORE_EXAMS[:n_core]
    spec_menu = [i for i in menu_ids if i not in core]
    chosen = []
    if n_spec > 0 and spec_menu and enc.budget.can_call(cfg['CALL_RESERVE']):
        pos, neg = [], []
        for e in enc.ledger:
            if e['kind'] == 'SAY' and e.get('phase') in ('interview', 'first', 'sweep') and not e.get('refused'):
                (neg if re.match(r'\s*(아니|없|안\s)', e.get('reply') or '') else pos).append(
                    f"{e['text']} → {e['reply'][:30]}")
        menu = '\n'.join(f'{i} | {banks.EXAM_BY_ID[i][1].replace("하겠습니다", "").strip()}' for i in spec_menu)
        sex = {'F': '여', 'M': '남'}.get(prof.get('sex'), '?')
        user = (f"환자: {prof.get('age')}세 {sex}, 주호소 {prof.get('cc')}\n문진(양성): {pos[:25]}\n문진(음성): {neg[:20]}\n"
                f"현재 감별진단: {enc.differentials}\n이미 하기로 한 기본 진찰: {[banks.EXAM_BY_ID[i][1] for i in core]}\n"
                f"아래 목록에서 감별진단을 확인·배제하는 데 가장 중요한 진찰 {n_spec}개를 고르세요(목록 밖 금지, 같은 목적 중복 금지).\n"
                f"목록(id | 진찰):\n{menu}\n출력: {{\"exam_ids\": [\"중요한 순\"]}}")
        res = ask_json(enc.client, enc.budget, '신체진찰 항목을 고릅니다. JSON 하나만 출력하세요.', user,
                       effort=cfg['EFFORT_EXAMS'], max_tokens=6000, tag='exams3', want=dict, tries=2,
                       reserve=cfg['CALL_RESERVE'])
        for i in (res or {}).get('exam_ids') or []:
            i = str(i).strip()
            if i in spec_menu and i not in chosen:
                chosen.append(i)
    for i in spec_menu:  # 부족하면 카테고리 순서로
        if len(chosen) >= n_spec:
            break
        if i not in chosen and i not in bank2.RISKY_EXAMS:
            chosen.append(i)
    chosen = chosen[:n_spec]
    order = chosen + [i for i in CORE_EXAMS if i not in chosen]
    filler = [i for i in order[total:] + spec_menu if i not in order[:total] and i not in bank2.RISKY_EXAMS]
    order = order[:total]
    has_vs = bool(re.search(r'\d{2,3}\s*/\s*\d{2,3}', enc.vitals or ''))
    if cfg.get('VITALS', 1) or not has_vs:
        order.append('vitals')
    log(f'v3 exams plan: {order}')
    enc.exam_plan = order
    k = 0
    while k < len(order):
        i = order[k]
        k += 1
        if not enc.can_act():
            break
        # 복부 촉진 결과에 간·비장이 이미 있으면 간·비장 촉진은 중복(r1 효율 감점) → 다음 후보로 교체
        if i == 'liver_spleen':
            abd = next((x for x in enc.ledger if x.get('qid') == 'abd_palp' and not x.get('refused')), None)
            if abd and re.search(r'(간|비장)', abd.get('reply') or ''):
                nxt = next((f for f in filler if f not in order), None)
                log(f'v3 exam skip liver_spleen (in abd_palp) → {nxt}')
                if nxt:
                    order.insert(k, nxt)
                continue
        reserve = cfg['EXPLAIN_N']
        if enc.turns_remaining <= reserve:
            break
        if i in enc.blacklist or i in enc.done_exams:
            continue
        e = banks.EXAM_BY_ID.get(i)
        if not e:
            continue
        entry = enc.act('EXAM', e[1], phase='exam', qid=i)
        if entry is None:
            continue
        if entry.get('refused'):
            enc.blacklist.add(i)
            continue
        entry['system'] = e[2]
        enc.done_exams.append(i)


# ---------------------------------------------------------------- 계획·설명
LINE_KEYS = ('dx', 'meaning', 'concern', 'tests', 'tests2', 'treatment', 'treatment2', 'warning', 'followup', 'lifestyle')


def _kb_line(k, pat, avoid=None):
    for s in (k or {}).get('say') or []:
        if re.search(pat, s) and not saymod.say_problem(s) and not saymod.safety_problem(s) and \
                not (avoid and re.search(avoid, s)):
            return s
    return ''


def _ok_line(s: str) -> bool:
    return bool(s) and not saymod.say_problem(s) and not saymod.safety_problem(s)


def plan_say(enc) -> dict:
    prof = enc.profile
    facts = getattr(enc, 'facts', None) or []
    a = getattr(enc, 'assess', None) or {}
    k = kbmod.match_kb(enc.dx or '')
    enc.kb = k
    pos = [f"{f['label']}{(' ' + f['detail']) if f['detail'] else ''}" for f in facts if f['pol'] == '+'][:25]
    neg = [f['label'] for f in facts if f['pol'] == '-'][:20]
    abn = [f"{x['name']}: {x['result'][:50]}" for x in (a.get('exams') or [])]
    ice = [f"{e['text']} → {e['reply']}" for e in enc.ledger if str(e.get('qid', '')).startswith('ice')]
    sex = {'F': '여', 'M': '남'}.get(prof.get('sex'), '?')
    ddx = [d['dx'] for d in a.get('differential') or []] or enc.differentials[1:4]
    name = re.search(r'(?:이름은|저는|나는)\s*([가-힣]{2,4}?)(?:이고|이며|입니다|이다|,|\s)', enc.opening)
    title = (prof.get('informant') + '님') if prof.get('pediatric') and prof.get('informant') not in ('본인', '보호자') \
        else ((name.group(1) + ' 님') if name else '')
    user = (f"환자: {prof.get('age')}세 {sex}, 정보 제공자 {prof.get('informant')}, 호칭: {title or '없음'}, 주진단: {enc.dx}, "
            f"감별: {ddx}\n핵심 양성 사실: {pos}\n핵심 음성 사실: {neg}\n진찰 소견: {abn}\n"
            f"환자 걱정·궁금증·요청(ICE): {ice} / 요청: {prof.get('request') or '없음'}\n"
            f"참고 지식표: {json.dumps(kbmod.kb_hint(k), ensure_ascii=False) if k else '없음'}\n"
            '[P] tests: 3~7개 {"name","reason"} — 확진, 주요 감별 배제, 치료 전 기준치, 안전(가임기 여성 임신 확인 등). 불필요·침습 검사 금지.\n'
            ' follow_up: "재진 : 시점과 확인할 것", "모니터링 : 간격과 항목". education: 질환·검사 이유·생활 수칙.\n'
            ' treatment: 이 진단의 표준 초기 치료를 구체적으로(약 계열명·비약물·처치; 숫자 용량·특정 상품명 없이, 조건부 표현).\n'
            '  응급·입원이면 즉시 처치(금식·수액·산소 투여·전문과 협진 등)를 포함.\n'
            ' disposition: 이 환자의 진찰·활력징후·위험 소견으로 직접 결정(level 응급|입원|외래). 복막자극 징후, 저산소·호흡곤란 악화,\n'
            '  불안정 활력, 신경학적 결손, 소아 탈수·처짐 등이 있으면 응급·입원 평가. 위험 소견이 없을 때만 외래. 이유는 실제 소견으로.\n'
            '  설명 문장(followup·treatment)도 이 결정과 일치해야 함(예: 응급이면 "오늘 바로 응급실에서 외과 진료를 받으세요").\n'
            '[설명 문장 lines] 각 항목은 환자에게 실제로 말할 한 문장(공백 포함 28자 이내, 쉬운 존댓말 평서문, 물음표 금지, 영어 약어 금지).\n'
            ' 정형 문구 대신 이 환자의 증상·걱정을 넣어 구체적으로. 소아면 보호자에게 말하듯.\n'
            ' 금지: 숫자 용량·%·"○주분", 특정 약 이름(약 계열명만: 항갑상샘제, 베타차단제 등), "처방해 드려요/드릴게요/시작해요" 같은 처방 확정,'
            ' "걱정 안 해도/완치/확실히" 같은 단정, "진단합니다" 같은 확정(검사 전이므로 "~로 보여요").\n'
            ' dx: 진단을 쉬운 말로(병명 포함). meaning: 왜 그렇게 보는지 — 이 환자의 구체적 증상·진찰 소견과 병의 기전을 연결\n'
            '  (예: "목이 붓고 맥이 빨라 호르몬 과다로 보여요").\n'
            ' concern: 환자 걱정(ICE)에 근거와 함께 직접 답(예: 암 걱정이면 "목이 고르게 커지고 눈 증상이 있어 암보다 갑상선 병이에요").'
            ' 걱정(ICE)이 있으면 concern은 반드시 채울 것.\n'
            ' tests: 핵심 검사 이름과 그 목적(무엇을 확인하는지). tests2: 나머지 검사와 목적(치료 전 안전 확인 등).\n'
            ' treatment: 치료 선택지와 각 역할(조건부: "검사 결과 보고 ~를 같이 정해요"). treatment2: 치료의 함의·주의\n'
            '  (부작용 시 행동, 기간, 다른 선택지 등 한 가지).\n'
            ' warning: 구체적 경고 증상 4개 이상을 "·"로 이어 "~면 바로 오세요."  followup: 재진 시점과 그때 할 일.\n'
            ' lifestyle: 이 환자에게 맞는 실천 가능한 생활 수칙 한 가지.\n'
            '[FAQ] 환자가 되물을 만한 질문에 대한 28자 이내 답(같은 금지 규칙): prognosis, serious, tests, treatment, results, '
            'lifestyle, duration, prescribe(해당 시: 처방 확정 대신 "검사 결과 보고 상의해 정해요"식).\n'
            '출력: {"tests": [{"name": "...", "reason": "..."}], "disposition": [{"level": "응급|입원|외래", "reason": "..."}],\n'
            ' "follow_up": [...], "education": [...], "treatment": [...],\n'
            ' "lines": {"dx": "", "meaning": "", "concern": "", "tests": "", "tests2": "", "treatment": "", "treatment2": "", '
            '"warning": "", "followup": "", "lifestyle": ""}, "faq": {"prognosis": "...", ...}}')
    res = ask_json(enc.client, enc.budget,
                   '당신은 한국 대학병원 외래의 숙련된 전문의입니다. 초진을 마무리하며 계획과 환자 설명을 씁니다. JSON 하나만 출력하세요.',
                   user, effort=enc.cfg['EFFORT_PLAN_SAY'], max_tokens=8000, tag='plan_say3', want=dict, tries=2,
                   max_wait=300, validate=lambda v: isinstance(v.get('lines'), dict))
    res = res if isinstance(res, dict) else {}
    from .explain import _list
    plan = {'tests': _list(res.get('tests')), 'treatment': _list(res.get('treatment')),
            'follow_up': _list(res.get('follow_up')), 'education': _list(res.get('education'))}
    disp = []
    for d in res.get('disposition') or []:
        if isinstance(d, dict):
            lv, rs = nfc(str(d.get('level') or '')).strip(), nfc(str(d.get('reason') or '')).strip()
            if lv or rs:
                disp.append(f'{lv} : {rs}' if lv and rs else (lv or rs))
        elif str(d).strip():
            disp.append(nfc(str(d)).strip())
    plan['disposition_luna'] = disp
    if k and not plan['tests']:
        plan['tests'] = [f'{x} : {y}' for x, y in k['tests']]
    lines = {kk: nfc(str((res.get('lines') or {}).get(kk) or '')).strip() for kk in LINE_KEYS}
    checks = []
    dx_short = re.sub(r'\(.*?\)', '', enc.dx or '').strip()
    fallback = {
        'dx': _kb_line(k, r'(같아요|보여요|의심|가능성)') or f'{dx_short} 가능성이 높아 보여요.',
        'meaning': ((k or {}).get('say') or ['', ''])[1] if k and len(k.get('say') or []) > 1 else '',
        'concern': '',
        'tests': _kb_line(k, saymod.TEST_RE.pattern) or saymod.GENERIC_TEST,
        'treatment': _kb_line(k, r'(치료|약|줄이|조절)', avoid=r'(검사|바로|오세요)') or '검사 결과를 보고 치료를 같이 정해요.',
        'warning': (k or {}).get('red_say') or _warn_from_plan(plan) or saymod.GENERIC_WARN,
        'followup': _kb_line(k, saymod.FOLLOWUP_RE.pattern, avoid=r'바로') or saymod.GENERIC_FOLLOW,
        'lifestyle': _kb_line(k, r'(카페인|운동|수면|생활|쉬세요|기상|낮잠|먹고)', avoid=r'(검사|바로)'),
        'tests2': '',
        'treatment2': _kb_line(k, r'(부작용|열·목|멈추|차단제|방사성|수술|줄여요|조절)', avoid=r'(바로\s*오|검사)'),
    }
    from .explain import SAFE_SAY, safe_say
    for kk in LINE_KEYS:
        s = lines.get(kk) or ''
        if s:  # v2c 설명 SAY 치환(약명→계열명). 구두 처방·수치 지시는 아래 필터에서 KB 폴백으로
            t = safe_say(s)
            if t != SAFE_SAY:
                s = t
        if kk == 'warning' and s and not _ok_line(s):
            s = compress_warning(s)  # 길면 증례별 경고 항목을 30자 안으로 압축(일반 경고 폴백은 무관 경고로 감점, sim S05)
        if s and not _ok_line(s):
            checks.append({'drop': s, 'key': kk, 'why': saymod.say_problem(s) or saymod.safety_problem(s)})
            s = ''
        if kk == 'warning' and s and saymod.warn_count([s]) < (2 if enc.cfg.get('GEN', 1) else 4):
            checks.append({'weak_warning': s})
            s = ''
        if kk == 'followup' and s and not saymod.FOLLOWUP_RE.search(s):
            s = s if fallback['followup'] == saymod.GENERIC_FOLLOW else ''
        if not s:
            s = fallback.get(kk) or ''
            if s and not _ok_line(s):
                s = ''
        lines[kk] = s
    if lines['dx'] and saymod.missing_elements([lines['dx']], enc.dx or '') and 'dx' in saymod.missing_elements(
            [lines['dx'], lines['meaning']], enc.dx or ''):
        alt = f'{dx_short} 가능성이 높아 보여요.'
        if _ok_line(alt):
            lines['dx'] = alt
    # KB 금지 문장·안전 필수 문장
    if k and k.get('ban_say'):
        for kk in LINE_KEYS:
            if lines[kk] and re.search(k['ban_say'], lines[kk]):
                lines[kk] = ''
    # 걱정(ICE)에 질환이 있는데 concern 문장이 비면 직접 답 폴백
    ice_txt = ' '.join(e.get('reply') or '' for e in enc.ledger if str(e.get('qid', '')).startswith('ice'))
    if not lines.get('concern'):
        m = re.search(r'(암|치매|당뇨|심장병|뇌졸중)', ice_txt) or re.search(r'(큰\s*병|나쁜\s*병)', ice_txt)
        if m:
            w = re.sub(r'\s', ' ', m.group(1))
            cand = f'진찰 소견은 {w}보다 지금 진단 쪽에 더 맞아요.'
            if _ok_line(cand):
                lines['concern'] = cand
    musts = []
    must_pats = []
    # 필수 패턴을 담은 문장은 설명 루프에서 필수로 승격되므로, 모든 줄을 대상으로 충족 확인
    said_txt = ' '.join(v for v in lines.values() if v)
    for pat, sent in SAFE_MUST_SAY.get((k or {}).get('id'), []):
        must_pats.append(pat)
        if not re.search(pat, said_txt):
            musts.append(sent)
    faq = {}
    for kk, v in ((k or {}).get('faq') or {}).items():
        if _ok_line(v):
            faq[kk] = v
    for kk, v in (res.get('faq') or {}).items():
        v = nfc(str(v or '')).strip()
        if kk not in faq and _ok_line(v):
            faq[str(kk)] = v
    faq.setdefault('test_pain', '피 뽑을 때 잠깐 따끔하고 금방 끝나요.')
    faq.setdefault('prescribe', '약은 검사 결과 보고 상의해 정해요.')
    enc.say_checks = checks
    log(f'v3 lines: {lines} musts={musts} checks={checks}')
    return {'plan': plan, 'lines': lines, 'musts': musts, 'must_pats': must_pats, 'faq': faq,
            'kb': (k or {}).get('id')}


def _answer(enc, reply: str, said: list, faq: dict, state: dict):
    from .explain import _faq_key
    key = _faq_key(reply)
    if key and key in faq and key not in state['used_faq']:
        state['used_faq'].add(key)
        return faq[key]
    if state['llm_answers'] < enc.cfg.get('ANSWER_LLM_MAX', 1) and enc.budget.can_call(1):
        state['llm_answers'] += 1
        p = enc.plan_v2 or {}
        res = ask(enc.client, enc.budget, '당신은 한국 외래 의사입니다. JSON 하나만 출력하세요.',
                  f'환자의 말: "{reply}" / 진단: {enc.dx} / 검사 계획: {p.get("tests", [])[:4]}\n이미 한 설명: {said}\n'
                  '환자 질문의 핵심에 먼저 직접 답하는 한 문장(공백 포함 28자 이내, 쉬운 존댓말 평서문). 일반 의학 지식으로 답하고, '
                  '숫자 용량·특정 약 이름·처방 확정("드려요/처방할게요")·단정("완치/확실히")·미루기 금지. 출력: {"answer": "..."}',
                  effort=enc.cfg['EFFORT_ANSWER'], max_tokens=4000, tag='answer3', want=dict, reserve=1)
        a = nfc((res or {}).get('answer') or '').strip()
        if _ok_line(a) and a not in said:
            return a
    return '검사 결과를 보고 함께 정해 갈게요.'


def _warn_from_plan(plan: dict) -> str:
    """luna P.follow_up의 '즉시 내원 : A, B, C' 줄로 증례별 경고 문장을 만든다(일반 경고 폴백 전에)."""
    for l in (plan or {}).get('follow_up') or []:
        if re.search(r'(즉시|바로|응급)', l) and ':' in l:
            body = l.split(':', 1)[1]
            body = re.sub(r'(이|가)?\s*(있으면|생기면|나타나면|시).*$', '', body).strip(' .')
            items = [p.strip() for p in re.split(r'[·,]|또는|이나\s', body) if p.strip()]
            if len(items) >= 2:
                return compress_warning('·'.join(items) + '면 바로 오세요.')
    return ''


def compress_warning(s: str) -> str:
    """'A·B·C·D·E가 생기면 바로 오세요' 꼴을 30자 안에 들어가는 만큼의 항목으로 줄임(항목 ≥2일 때만)."""
    items = _warn_items(nfc(s))
    for k in range(len(items), 1, -1):
        cand = f"{'·'.join(items[:k])}면 바로 오세요."
        if len(cand) <= saymod.MAX_SAY and not saymod.say_problem(cand):
            return cand
    return ''


def _warn_items(line: str) -> list:
    """경고 문장의 항목 원문('숨참', '불규칙한 맥', ...)."""
    body = re.split(r'(이|가|이나|면|시|때)?\s*(바로|응급실)', line)[0]
    body = re.sub(r'\s*(이|가)?\s*(생기|있으|오|나타나)\S*$', '', body.strip())
    return [p.strip() for p in re.split(r'[·,]|이나\s|거나\s|또는', body) if p.strip()]


def _warn_terms(line: str) -> list:
    body = re.split(r'(이|가|이나|면|시|때)?\s*(바로|응급실)', line)[0]
    parts = [p.strip() for p in re.split(r'[·,]|이나\s|거나\s|또는', body) if p.strip()]
    stop = {'심한', '심하', '갑자', '생기', '이상', '변화', '증상', '계속', '자주', '많이', '오래', '있으', '나타', '때때'}
    terms = []
    for p in parts:
        words = [re.sub(r'(이|가|을|를|이나|나|면|시)$', '', w) for w in p.split()]
        words = [w for w in words if len(w) >= 2 and w[:2] not in stop]
        if words:
            terms.append(words[0][:2])
    return terms


def explain(enc, ps: dict, quick=False):
    """동적 설명 루프: 필수 항목을 남은 턴 안에 말하고, 남는 턴으로 환자 질문에 답한다."""
    from .explain import _faq_key, is_question
    lines = ps.get('lines') or {}
    faq = ps.get('faq') or {}
    items = []  # (key, text, priority) — priority 낮을수록 먼저 버림
    pri = {'dx': 10, 'warning': 9, 'teach': 8, 'treatment': 7, 'must': 7, 'tests': 6, 'followup': 5, 'meaning': 4.8,
           'concern': 4.6, 'treatment2': 4.4, 'tests2': 3.5, 'lifestyle': 3, 'final': 5.5, 'recheck': 6.5}
    order = ['dx', 'meaning', 'concern', 'tests', 'tests2', 'treatment', 'treatment2', 'must', 'warning', 'followup',
             'lifestyle', 'teach', 'final']
    for key in order:
        if key == 'must':
            for s in ps.get('musts') or []:
                items.append(['must', s])
        elif key == 'teach':
            if lines.get('warning'):
                items.append(['teach', TEACH_BACK])
        elif key == 'final':
            items.append(['final', FINAL_Q])
        elif lines.get(key):
            items.append([key, lines[key]])
    if quick:
        items = [it for it in items if it[0] in ('dx', 'tests', 'warning', 'followup')]
    said = []
    state = {'used_faq': set(), 'llm_answers': 0}
    answers = 0
    amax = 0 if quick else enc.cfg['ANSWER_MAX']
    budget = enc.turns_remaining

    must_pats = ps.get('must_pats') or []
    for it in items:  # 안전 필수 패턴을 이미 담은 문장은 필수로 승격(같은 내용 must 문장 중복 방지)
        if it[0] not in ('must', 'teach', 'final') and any(re.search(p, it[1]) for p in must_pats):
            it[0] = 'must'

    def need(queue):  # 마지막 질문은 환자 되물음에 답할 1턴을 함께 잡는다
        return len(queue) + (1 if any(q[0] == 'final' for q in queue) else 0)

    def trim(queue, avail):
        while need(queue) > avail and queue:
            idx = min(range(len(queue)), key=lambda i: (pri.get(queue[i][0], 3), -i))
            queue.pop(idx)
    queue = list(items)
    turn0 = enc.turn
    cap = enc.cfg['EXPLAIN_N'] if not quick else enc.turns_remaining

    def avail_now():  # 설명 단계 턴 상한 = EXPLAIN_N(프리셋), 서버 잔여 턴도 함께
        return min(enc.turns_remaining, cap - (enc.turn - turn0))
    while queue and enc.can_act():
        avail = avail_now()
        trim(queue, avail)
        if not queue:
            break
        key, text = queue.pop(0)
        phase = 'explain'
        entry = enc.act('SAY', text, phase=phase, qid='x_' + key)
        if not entry or entry.get('refused'):
            continue
        reply = entry.get('reply') or ''
        if key not in ('teach', 'final'):
            said.append(text)
            enc.explained.append(text)
        if key == 'teach':
            terms = _warn_terms(lines.get('warning') or '')
            hit = sum(1 for t in terms if t in reply)
            ok = (hit >= 1 if terms else True) and not re.search(r'한\s*번에\s*하나씩', reply)
            enc.teach_back = {'reply': reply, 'ok': ok}
            if not ok and avail_now() > 0 and not enc.cfg.get('GEN', 1):  # GEN: 경고 재안내는 '반복'으로 감점(sim gen4·5)
                # 같은 경고 문장 반복은 효율 감점(sim gen2) → 환자가 말하지 않은 경고어로 보완 문장
                miss = [w for w in _warn_items(lines['warning']) if w[:2] not in reply][:3]
                fix = f"{'·'.join(miss)}도 생기면 바로 오세요." if miss else ''
                if fix and _ok_line(fix):
                    queue.insert(0, ['recheck', fix])
            continue
        fear = bool(re.search(r'(걱정|두려|무서|불안)', reply)) and key not in ('final',)
        if not (is_question(reply) or fear) or answers >= amax and key != 'final':
            continue
        # 환자가 되물음: 해당 항목이 대기 중이면 앞당기고, 아니면 바로 답
        fk = _faq_key(reply)
        target = {'tests': 'tests', 'results': 'followup', 'treatment': 'treatment', 'prescribe': 'treatment',
                  'lifestyle': 'lifestyle'}.get(fk)
        j = next((i for i, it in enumerate(queue) if it[0] == target), None) if target else None
        if j is not None:
            queue.insert(0, queue.pop(j))
            continue
        if avail_now() <= len([q for q in queue if pri.get(q[0], 3) >= 7]):  # 환자 질문 답이 저우선 설명보다 먼저
            continue  # 필수 항목 말할 턴이 모자라면 답을 생략
        ans = _answer(enc, reply, said, faq, state)
        if ans and ans not in said:
            e2 = enc.act('SAY', ans, phase='explain-answer', qid='x_answer')
            if e2 and not e2.get('refused'):
                said.append(ans)
                enc.explained.append(ans)
                answers += 1
    log(f'v3 explain done: said={len(said)} answers={answers} teach={getattr(enc, "teach_back", None)} '
        f'turns_left={enc.turns_remaining} (start {budget})')


# ---------------------------------------------------------------- P칸(보수적 템플릿, 안전 필터)
def render_plan(enc, plan: dict, k) -> dict:
    """P칸: v2c 안전 복구 구현(explain.render_plan: KB 보수 템플릿·safe_plan_line·dedup·조기 연락 줄)을 그대로 쓰고,
    v3 금지 패턴(say.safety_problem)에 걸리는 줄이 남으면 한 번 더 걸러 낸다."""
    from .explain import render_plan as v2c_render_plan, safe_plan_line
    from .record import vitals_assessment
    out = v2c_render_plan(enc, plan, k)
    luna_disp = (plan or {}).get('disposition_luna') or []
    if luna_disp and enc.cfg.get('GEN', 1):
        # 처치 결정은 luna가 소견 기반으로(응급/입원/외래). KB 기본값 '외래 추적'을 모든 진단에 적용하지 않음.
        head = vitals_assessment(enc).lstrip('- ').split(' → ')[0]
        lines = [head] + [safe_plan_line(l, 'disposition') for l in luna_disp]
        out['disposition'] = '\n'.join(f'- {l}' for l in lines if l)
        if any(re.search(r'(응급|입원)', l.split(':')[0]) for l in luna_disp) and plan.get('follow_up'):
            keep = [l for l in (out.get('follow_up') or '').split('\n') if re.search(r'(즉시|바로|응급|조기\s*연락)', l)]
            fu = [f"- {safe_plan_line(l, 'follow_up')}" for l in plan['follow_up'] if not re.search(r'(즉시|바로)', l)]
            out['follow_up'] = '\n'.join(fu[:3] + keep)
    for f in ('treatment', 'disposition', 'follow_up'):
        lines = [l for l in (out.get(f) or '').split('\n') if l.strip()]
        kept = []
        for l in lines:
            why = saymod.safety_problem(l)
            if why == 'dose' and re.search(r'(mmHg|회/분|°C|SpO2|산소포화)', l):
                why = ''  # 활력징후 수치 줄
            if why and not (why == 'admit' and f == 'disposition' and '고려' in l):
                log(f'v3 P removed ({why}): {l}')
                continue
            kept.append(l)
        out[f] = '\n'.join(saymod.dedup_lines(kept))
    return out


# ---------------------------------------------------------------- 서버 전처리 확인
def check_effective(enc) -> dict:
    """세션 events의 effective_content가 보낸 원문과 다르면(서버 절단) 경고. 제출 전 1회."""
    out = {'checked': 0, 'truncated': []}
    try:
        sess = enc.client.session()
    except Exception as exc:  # noqa: BLE001
        log(f'v3 effective check skipped: {type(exc).__name__}')
        return out
    for ev in (sess or {}).get('events') or []:
        if not isinstance(ev, dict) or ev.get('action') != 'SAY':
            continue
        p = ((ev.get('payload') or {}).get('content') or '').strip()
        ef = ev.get('effective_content')
        out['checked'] += 1
        if ef is not None and nfc(ef).strip() != nfc(p):
            out['truncated'].append({'turn': ev.get('turn'), 'sent': p, 'effective': ef})
    if out['truncated']:
        log(f"WARNING v3 server truncated {len(out['truncated'])} SAY: {out['truncated']}")
    enc.counts['truncated'] = len(out['truncated'])
    return out

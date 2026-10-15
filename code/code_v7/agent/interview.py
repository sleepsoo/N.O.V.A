"""v2 문진: intake(LLM) → 체크리스트(필수★·BOOST·덮임) → 첫 묶음(은행) → luna 배치 계획 2회 → ICE. (v2_spec §5.5, §8.2, §8.3)"""
from __future__ import annotations

import json
import re

from . import bank2
from . import guidelines
from .llm import ask_json
from .util import extract_numbers, fits, is_similar, log, nfc, parse_age, parse_sex, validate_question

ROLE = '당신은 한국 외래 진료실의 숙련된 의사입니다.'
ICE_SLOTS = ('ice_concern', 'ice_disease', 'ice_expect')

# v7 C3-2: 포괄 질문("다른 불편한 증상 있나요?")은 진료당 1회
GENERIC_Q_RE = re.compile(r'(다른|그\s*밖에|또\s*다른|그\s*외).{0,8}(불편|증상|문제|이상)')
# v7 C3-3: 이미 답한 주제를 존재형 free 질문으로 다시 묻지 않는다
TOPIC_RE = {'dyspnea': r'숨\s*(이\s*)?차|숨참|호흡\s*곤란', 'chest': r'가슴.{0,3}(통증|아프|아픔)|흉통',
            'palp': r'두근|심장이\s*(빨리|뛰)', 'weight': r'체중|살이|몸무게', 'sweat': r'땀|발한',
            'fever': r'열이|발열|오한', 'sleep': r'잠을|잠이|수면|불면', 'mood': r'기분|우울',
            'bowel': r'대변|변이|설사|변비', 'urine': r'소변|배뇨', 'menses': r'생리|월경',
            'headache': r'두통|머리가?\s*아', 'dizzy': r'어지', 'tremor': r'떨리|떨림', 'appetite': r'입맛|식욕|식사량'}
WH_Q_RE = re.compile(r'얼마나|언제|어떻게|몇|어디|무슨|어떤')
EXIST_Q_RE = re.compile(r'(있|없|나요|세요|가요)\?$')

Q_RULES = (
    '[질문 규칙]\n'
    '- 질문 하나에 한 가지(예/아니요나 짧은 답이 나오게). 가상 환자는 두 가지를 물으면 보통 첫 항목에만 답하므로 서로 다른 증상 둘을 '
    '묶지 말 것(예: "변비가 있거나 추위를 타나요?" 금지). 병력 이름 둘(예: "고혈압이나 당뇨 있으세요?")만 예외.\n'
    '- 공백 포함 28자 이내, 쉬운 존댓말 의문문(물음표 1개, "~요?/~까?"로 끝남), 영어·약어 금지, 띄어쓰기 정확.\n'
    '- "전부/모두/다 말씀/요약/나열/이상한 것만" 금지(환자가 "한 번에 하나씩 물어봐 주세요"라고만 답함).\n'
    '- 이미 물었거나 환자가 이미 말한 내용(첫 진술 포함)은 묻지 않음. 비슷한 질문 반복 금지.\n'
    '- 환자에게 진단명을 묻지 않음. 검사·처치·진찰을 요청하지 않음(문진만).\n'
    '- 부정형 질문("~없으세요?")보다 긍정형 질문을 우선(답의 극성이 분명하도록).\n'
    '[우선순위]\n'
    '1) ★필수 미확인 항목 2) 상위 감별진단 3개를 서로 가르는 질문(지지·배제 소견, 위험 징후) 3) 권장 4) 선택.\n'
    '답을 들어도 감별진단이 바뀌지 않는 질문은 빼세요.\n'
    '가상 환자 대본에는 보통 다음이 들어 있습니다: 현병력 세부(시작·경과·수치), 동반 증상과 관련 음성 증상, 과거력·복용약(영양제·한약 '
    '포함)·수술, 가족력(부모·형제의 구체 질환), 사회력(흡연·음주·카페인·운동·직업·동거·스트레스), 여성력(월경·임신 가능성), '
    '기분·수면(관련 시), 걱정·궁금증. 남은 질문 수 안에서 이 영역을 고르게 확인하되 진단에 중요한 것부터.\n'
    '순서는 현병력·동반 증상 → 과거력·약물 → 가족력 → 사회력·여성력. 걱정·궁금증(ICE)은 따로 물으니 넣지 마세요.')


# ---------------------------------------------------------------- intake
def intake(enc) -> dict:
    opening = enc.opening
    age = parse_age(opening)
    sex = parse_sex(opening)
    peds_re = bool(re.search(r'(보호자|엄마|아빠|어머니|아버지|할머니|할아버지).{0,20}(함께|같이|데리고|동반|왔)', opening))
    cats_desc = '\n'.join(f'{k}: {v}' for k, v in bank2.CATEGORY_DESC.items())
    sys_prompt = (ROLE + ' 진료 시작 전, 환자의 첫 진술과 활력징후만 보고 진료를 준비합니다. JSON 객체 하나만 출력하세요.\n'
                  f'카테고리 목록(id: 설명):\n{cats_desc}')
    user = (f'시작 정보(환자 첫 진술): {opening}\n활력징후: {enc.vitals.replace(chr(10), ", ")}\n'
            '출력:\n{"age": 정수|null, "sex": "M"|"F"|null, "pediatric": 만 15세 미만 또는 보호자가 대신 답하면 true,\n'
            ' "informant": "본인"|"어머니"|"아버지"|"할머니"|"보호자",\n'
            ' "chief_complaint": "주호소 명사구(요청이 있으면 괄호로, 예: 불면 (수면제 처방 원함))",\n'
            ' "request": "환자가 요청한 것, 없으면 \'\'",\n'
            ' "categories": ["카테고리 id 1~3개, 진단에 가장 중요한 것 먼저"],\n'
            ' "differential": ["가능성 높은 순 감별진단 5개"],\n'
            ' "empathy": "주호소에 대한 짧은 공감 한마디(존댓말 평서문, 14자 이내, 예: 많이 걱정되셨겠어요.)"}')
    res = ask_json(enc.client, enc.budget, sys_prompt, user, effort=enc.cfg['EFFORT_INTAKE'], max_tokens=6000,
                   tag='intake', want=dict, tries=2, reserve=enc.cfg['CALL_RESERVE'])
    res = res if isinstance(res, dict) else {}
    try:
        llm_age = int(res.get('age')) if res.get('age') is not None else None
    except (TypeError, ValueError):
        llm_age = None
    if age is None:
        age = llm_age
    if not sex and str(res.get('sex') or '').upper() in ('M', 'F'):
        sex = str(res['sex']).upper()
    pediatric = (age is not None and age < 15) or (peds_re and (age is None or age < 18)) or \
        (age is None and bool(res.get('pediatric')))
    cc = nfc(res.get('chief_complaint') or '').strip()
    if not cc:
        parts = [p for p in re.split(r'[.。]', opening) if p.strip()]
        cc = (parts[1] if len(parts) > 1 else opening)[:40].strip()
    request = nfc(res.get('request') or '').strip()
    if not request and re.search(bank2.SUBSTANCE_REQUEST_RE, opening):
        request = re.search(r'[^.]*(처방|달라)[^.]*', opening).group(0).strip()
    cats = []
    for c in res.get('categories') or []:
        c = str(c).strip()
        if pediatric:
            c = bank2.PEDS_MAP.get(c, c)
        elif c in bank2.PEDS_ONLY:
            continue
        if c in bank2.CATEGORY_Q and c not in cats:
            cats.append(c)
    for c in bank2.detect_categories(cc + ' ' + opening, pediatric):
        if c not in cats:
            cats.append(c)
    if pediatric and 'growth' in cats:
        cats = ['growth']
    if 'substance' in cats and (request or re.search(bank2.SUBSTANCE_REQUEST_RE, opening)):
        cats.remove('substance')
        cats.insert(0, 'substance')
    cats = cats[:3]
    if not cats:
        cats = ['fatigue'] if not pediatric else ['p_fever']
    informant = '본인'
    if pediatric:
        informant = bank2.informant_title(opening)
    diffs = [nfc(d).strip() for d in (res.get('differential') or []) if isinstance(d, str) and d.strip()][:5]
    empathy = nfc(res.get('empathy') or '').strip()
    if not empathy or '?' in empathy or len(empathy) > 16:
        empathy = '많이 걱정되셨겠어요.'
    prof = {'age': age, 'sex': sex, 'pediatric': bool(pediatric), 'informant': informant, 'cc': cc,
            'request': request, 'categories': cats, 'empathy': empathy, 'answered': []}
    enc.profile = prof
    enc.differentials = diffs
    log(f'intake: {prof} diffs={diffs}')
    return prof


# ---------------------------------------------------------------- checklist
class Checklist:
    def __init__(self, prof: dict, opening: str):
        self.items = {}   # slot -> dict(label,q,prio,group,order)
        self.covered = set()
        self.asked = set()
        peds = prof.get('pediatric')
        age = prof.get('age')
        sex = prof.get('sex')
        cats = list(prof.get('categories') or [])
        self.cats = cats
        order = 0

        def add(lst, group):
            nonlocal order
            for slot, label, q, prio in lst:
                if slot in self.items:
                    continue
                order += 1
                self.items[slot] = {'label': label, 'q': q, 'prio': prio, 'group': group, 'order': order}

        main = cats[0] if cats else None
        if main:
            add(bank2.CATEGORY_Q.get(main, []), 'main')
        if peds:
            title = prof.get('informant') or '보호자분'
            spine = []
            for s, l, q, p in bank2.PEDS_SPINE:
                q = q.replace('어머님', title)
                if age is not None and age >= 7:
                    q = q.replace('어린이집', '학교')
                spine.append((s, l, q, p))
            add(spine, 'common')
            if sex == 'F' and set(cats) & {'menstrual', 'abd_pain', 'urinary'}:
                add(bank2.WOMEN, 'women')
        else:
            add(bank2.ADULT_SPINE, 'common')
            if sex == 'F' and (age is None or 12 <= age <= 55):
                add(bank2.WOMEN, 'women')
            if set(cats) & bank2.PSYCH_SCREEN_FOR or (age is not None and age >= 65):
                add(bank2.PSYCH_SCREEN, 'psych')
        for c in cats[1:]:
            # 부 카테고리 항목은 필수로 두지 않는다(r6 C10: 두근거림 세부 3턴이 위험 증상·눈 증상 문진을 밀어냄)
            add([(s, l, q, max(p, 2)) for s, l, q, p in bank2.CATEGORY_Q.get(c, [])], 'secondary')
        # BOOST
        for c in cats:
            for slot, p in bank2.BOOST.get(c, {}).items():
                if slot in self.items:
                    self.items[slot]['prio'] = min(self.items[slot]['prio'], p)
        for c in cats:
            for slot, p in bank2.DEMOTE.get(c, {}).items():
                if slot in self.items:
                    self.items[slot]['prio'] = p
        # 시작 정보로 덮인 항목
        self.covered |= {s for s in bank2.cover_hits(opening) if s in self.items}
        if peds and 'gr_parents' in self.items and re.search(r'키', opening) is None:
            pass
        log(f'checklist: {len(self.items)} items, covered={sorted(self.covered)}')

    def uncovered(self, include_ice=False):
        out = [s for s in self.items if s not in self.covered and s not in self.asked]
        if not include_ice:
            out = [s for s in out if s not in ICE_SLOTS]
        return out

    def ranked(self):
        grp = {'main': 0, 'common': 1, 'women': 2, 'psych': 3, 'secondary': 4}
        return sorted(self.uncovered(), key=lambda s: (self.items[s]['prio'], grp.get(self.items[s]['group'], 5),
                                                       self.items[s]['order']))

    def rows(self) -> str:
        lines = []
        for s, it in self.items.items():
            if s in ICE_SLOTS or s in ('md_plan', 'gr_values'):
                continue
            mark = '✓' if (s in self.covered or s in self.asked) else '·'
            lines.append(f"{mark} | {s} | {it['prio']} | {it['label']} | {it['q']}")
        return '\n'.join(lines)


# ---------------------------------------------------------------- 실행
def _qa_table(enc) -> str:
    rows = []
    for e in enc.ledger:
        if e['kind'] != 'SAY' or e.get('refused') or e.get('phase') not in ('interview', 'ice', 'first'):
            continue
        rows.append(f"{e['turn']} | {e['text']} | {e['reply']}")
    return '\n'.join(rows) or '(없음)'


def plan_q(enc, cl: Checklist, n: int, remaining: int):
    prof = enc.profile
    sex = {'F': '여', 'M': '남'}.get(prof.get('sex'), '?')
    sys_prompt = (ROLE + ' 가상 환자 문진에서 다음에 물을 질문을 고릅니다. JSON 하나만 출력하세요.\n' + Q_RULES)
    gl = guidelines.hint_interview(enc)
    user = (f"환자: {prof.get('age')}세 {sex}, 정보 제공자: {prof.get('informant')}, 주호소: {prof.get('cc')}, "
            f"요청: {prof.get('request') or '없음'}, 카테고리: {prof.get('categories')}\n"
            f"시작 정보: {enc.opening} / 활력징후: {enc.vitals.replace(chr(10), ', ')}\n"
            f"지금까지 문답(턴 | 의사 | 환자):\n{_qa_table(enc)}\n"
            f"체크리스트(상태 | id | 우선 | 항목 | 예시 질문) — 상태 ✓=확인됨 ·=미확인:\n{cl.rows()}\n"
            f"현재 감별진단: {enc.differentials}\n"
            f"{gl}"
            f"이번에 고를 질문 수: {n}  (ICE 제외 남은 문진 질문: {remaining})\n"
            '출력: {"covered": ["이번 문답까지 확인된 체크리스트 id"], "differential": ["가능성 순 3~5개"],\n'
            f' "questions": [{{"slot": "체크리스트 id 또는 free", "q": "질문"}}]}}  ← 정확히 {n}개, 중요한 순')
    res = ask_json(enc.client, enc.budget, sys_prompt, user, effort=enc.cfg['EFFORT_PLAN_Q'], max_tokens=8000,
                   tag='plan_q', want=dict, tries=2, reserve=enc.cfg['CALL_RESERVE'],
                   validate=lambda v: isinstance(v.get('questions'), list))
    if not isinstance(res, dict):
        return None
    # LLM의 'covered' 주장은 쓰지 않는다(r3: '처방' 한 단어로 여러 기관 처방 문항이 덮여 핵심 질문 누락). 덮임은 COVER_RE·asked만.
    diffs =[nfc(d).strip() for d in (res.get('differential') or []) if isinstance(d, str) and d.strip()]
    if diffs:
        enc.differentials = diffs[:5]
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


def match_slot(cl: Checklist, q: str) -> str:
    """'free' 질문이 체크리스트 은행 문구와 같은/비슷한 질문이면 그 slot으로 본다(덮임·중복 판정용)."""
    for s, it in cl.items.items():
        if it['q'] == q:
            return s
    for s, it in cl.items.items():
        if is_similar(q, [it['q']], 0.6):
            return s
    return 'free'


def _valid(enc, cl: Checklist, slot: str, q: str) -> bool:
    ok, why = validate_question(q, enc.asked)
    if not ok:
        log(f'q rejected ({why}): {q}')
        return False
    if slot != 'free' and slot in cl.items and (slot in cl.covered or slot in cl.asked):
        log(f'q rejected (covered {slot}): {q}')
        return False
    if len(q) > 28 and not fits(q):
        return False
    if GENERIC_Q_RE.search(q) and any(GENERIC_Q_RE.search(a or '') for a in (getattr(enc, 'asked', None) or [])):
        log(f'q rejected (generic_repeat): {q}')
        return False
    return True


def answered_topics(enc) -> set:
    """시작 정보와 이전 환자 답(첫 질문·문진·ICE)에 실제로 나온 주제."""
    texts = [enc.opening or '']
    texts += [e.get('reply') or '' for e in enc.ledger
              if e.get('kind') == 'SAY' and not e.get('refused') and e.get('phase') in ('first', 'interview', 'ice')]
    return {t for t, p in TOPIC_RE.items() if any(re.search(p, x) for x in texts)}


def topic_answered(enc, q: str) -> list:
    """존재형 질문(의문사 없음, '…있/없/나요/세요/가요?'로 끝남)의 주제 중 이미 답한 것. 그 밖의 질문은 []."""
    if not enc.cfg.get('TOPIC_GUARD', 1):
        return []
    q = (q or '').strip()
    if WH_Q_RE.search(q) or not EXIST_Q_RE.search(q):
        return []
    topics = [t for t, p in TOPIC_RE.items() if re.search(p, q)]
    if not topics:
        return []
    done = answered_topics(enc)
    return [t for t in topics if t in done]


def _bank_q(cl: Checklist, slot: str):
    return (slot, cl.items[slot]['q'])


def ask(enc, cl: Checklist, slot: str, q: str, phase='interview') -> dict | None:
    label = cl.items.get(slot, {}).get('label', '적응형') if slot != 'free' else '적응형'
    entry = enc.act('SAY', q, phase=phase, qid=slot, label=label)
    if entry is None or entry.get('refused'):
        return entry
    enc.counts['interview'] += 1
    if slot in cl.items:
        cl.asked.add(slot)
    reply = entry.get('reply') or ''
    cl.covered |= {s for s in bank2.cover_hits(reply) if s in cl.items}
    if entry.get('one_at_a_time'):
        enc.retry_single(q, phase)
    return entry


def run(enc):
    cfg = enc.cfg
    prof = enc.profile
    cl = Checklist(prof, enc.opening)
    enc.checklist = cl
    q_max = cfg['INTERVIEW_Q']
    ice_reserve = 2
    asked = 0

    def left():
        by_turns = enc.turns_remaining - (cfg['EXAM_N'] + cfg['EXPLAIN_N'] + 1)
        return min(q_max - enc.counts['interview'], by_turns)

    # 1. 첫 질문: 공감 + 첫 필수 질문
    ranked = cl.ranked()
    first_slot = 'hpi_onset' if 'hpi_onset' in ranked else (ranked[0] if ranked else 'hpi_course')
    first_q = cl.items.get(first_slot, {}).get('q', '언제부터 그러셨어요?')
    first = f"{prof.get('empathy', '')} {first_q}".strip()
    if not fits(first):
        first = first_q
    if enc.can_act():
        ask(enc, cl, first_slot, first, phase='first')
    # 2. 묶음 루프: 첫 묶음은 은행 우선순위(LLM 호출 없음), 이후 plan_q
    batch_no = 0

    def ask_concern():
        e = ask(enc, cl, 'ice_concern', cl.items.get('ice_concern', {}).get('q', '가장 걱정되시는 게 뭐예요?'), phase='ice')
        reply = (e or {}).get('reply') or ''
        if re.search(r'(큰\s*병|나쁜\s*병|심각|이상\s*있)', reply) and not re.search(r'(암|당뇨|갑상|치매|심장|뇌)', reply) \
                and left() > 2 and 'ice_disease' in cl.items:
            ask(enc, cl, 'ice_disease', cl.items['ice_disease']['q'], phase='ice')

    while left() > ice_reserve and enc.can_act() and enc.phase_time_ok():
        if batch_no == 1 and 'ice_concern' not in cl.asked:
            ask_concern()  # 걱정(ICE)은 문진 앞쪽에: 설명에서 직접 답할 수 있게
            ice_reserve = 1
            if left() <= ice_reserve:
                break
        remaining = left() - ice_reserve
        n = min(cfg['BATCH_N'] if batch_no else cfg['FIRST_BATCH_N'], remaining)
        qs = None
        if batch_no >= 1 and batch_no <= cfg['PLAN_Q_CALLS']:
            qs = plan_q(enc, cl, n, remaining)
        batch_no += 1
        if not qs:
            qs = [_bank_q(cl, s) for s in cl.ranked()[:n + 3]]
        good = []
        for slot, q in qs:
            if slot == 'free':
                hit = topic_answered(enc, q)
                if hit:
                    log(f'q skipped (topic answered {hit}): {q}')
                    continue  # 빈자리는 아래에서 cl.ranked() 다음 순위로 채운다
            if _valid(enc, cl, slot, q) and not is_similar(q, [g[1] for g in good]):
                good.append((slot, q))
        # 필수 미확인이 남은 자리보다 많으면 은행 필수 질문으로 교체
        must = [s for s in cl.ranked() if cl.items[s]['prio'] == 1]
        good = good[:n]
        in_good = {g[0] for g in good}
        must_out = [s for s in must if s not in in_good]
        # 이번 묶음 뒤에 남는 자리로 필수 항목을 다 못 채우면, 모자라는 만큼 이번 묶음에 필수 질문을 넣는다
        need = len(must_out) - max(0, remaining - n)
        if need > 0:
            must_q = [_bank_q(cl, s) for s in must_out]
            # 교체 순서: 선택(3) → free → 권장(2)
            order = sorted(range(len(good)), key=lambda i: {3: 0, None: 1, 2: 2}.get(
                cl.items.get(good[i][0], {}).get('prio'), 3), reverse=False)
            for idx in order:
                if need <= 0 or not must_q:
                    break
                if cl.items.get(good[idx][0], {}).get('prio') == 1:
                    continue
                good[idx] = must_q.pop(0)
                need -= 1
            while need > 0 and must_q and len(good) < n:
                good.append(must_q.pop(0))
                need -= 1
        if len(good) < n:
            for s in cl.ranked():
                if len(good) >= n:
                    break
                if s not in {g[0] for g in good} and not is_similar(cl.items[s]['q'], enc.asked):
                    good.append(_bank_q(cl, s))
        if not good:
            break
        sent = 0
        topic_skipped = 0
        for slot, q in good[:n]:
            if left() <= ice_reserve or not enc.can_act() or not enc.phase_time_ok():
                break
            if slot != 'free' and (slot in cl.covered or slot in cl.asked):
                continue  # 직전 답으로 덮였으면 건너뜀(중복 방지)
            if slot == 'free':
                hit = topic_answered(enc, q)  # 이번 묶음 앞 질문의 답으로 새로 답해진 주제
                if hit:
                    log(f'q skipped (topic answered {hit}): {q}')
                    topic_skipped += 1
                    continue
                topic = [s for s in bank2.cover_hits(q) if s in cl.items]
                if any(s in cl.covered or s in cl.asked for s in topic):
                    log(f'q skipped (topic covered {topic}): {q}')
                    continue
                if topic:
                    slot = topic[0]
            if is_similar(q, enc.asked):
                continue
            entry = ask(enc, cl, slot, q)
            if not entry or entry.get('refused'):
                continue
            sent += 1
            reply = entry.get('reply') or ''
            if slot == 'gr_record' and re.search(r'(수첩|기록|있)', reply) and not re.match(r'\s*(아니|없)', reply) \
                    and 'gr_values' in cl.items and 'gr_values' not in cl.asked and left() > ice_reserve:
                ask(enc, cl, 'gr_values', cl.items['gr_values']['q'])
            if slot == 'ps_si' and not re.match(r'\s*(아니|없|전혀)', reply) and 'md_plan' in cl.items \
                    and left() > ice_reserve:
                ask(enc, cl, 'md_plan', cl.items['md_plan']['q'])
        if sent == 0 and not topic_skipped:
            break  # 주제 건너뜀만 있었으면 다음 묶음(은행 다음 순위)으로 빈자리를 채운다
    # 3. ICE
    if enc.can_act() and left() > 1 and 'ice_concern' not in cl.asked:
        ask_concern()
    if enc.can_act() and left() > 0:
        ask(enc, cl, 'ice_expect', cl.items.get('ice_expect', {}).get('q', '오늘 특히 궁금하신 게 있으세요?'), phase='ice')
    log(f'interview done: asked={len(cl.asked)} covered={len(cl.covered)} '
        f'uncovered_p1={[s for s in cl.ranked() if cl.items[s]["prio"] == 1]}')


# ---------------------------------------------------------------- 진찰 (§8.4)
def examine(enc):
    from . import banks
    cfg = enc.cfg
    prof = enc.profile
    peds = prof.get('pediatric')
    # v7 C2-1: 활력징후는 시작 정보에 값이 있어도 직접 측정한다(EXAM_N 안에서, 최하위 1개가 빠짐).
    # EXAM_VITALS=0이면 v6처럼 시작 정보에 값이 있을 때 생략.
    if cfg.get('EXAM_VITALS', 1):
        has_vs = False
    else:
        has_vs = bool(re.search(r'\d{2,3}\s*/\s*\d{2,3}', enc.vitals or ''))
    always = ([] if has_vs else ['vitals']) + ['general'] + (['anthro'] if peds else [])
    # v7 C2-2: 표 밖 진찰(기분·정동 평가 등)은 계획에서 뺀다
    deny = {s.strip() for s in str(cfg.get('EXAM_DENY', 'affect') or '').split(',') if s.strip()}
    total = cfg['EXAM_N']
    cats = list(prof.get('categories') or [])
    # v7 C2-3: 정신·물질 범주면 공통 보충 행을 CORE_FILL_PSYCH로(복부·하지 후순위)
    core = bank2.CORE_FILL_PSYCH if set(cats) & bank2.PSYCH_EXAM_CATS else bank2.CORE12
    diff_txt = ' '.join(enc.differentials or []) + ' ' + (prof.get('cc') or '')
    thyroid_dx = bool(re.search(banks.THYROID_RE, ' '.join((enc.differentials or [])[:2]), flags=re.I))
    if thyroid_dx and not set(cats) & {'weight_loss', 'palpitation', 'fatigue'}:
        cats.append('_thyroid')
    cat_lists = {c: bank2.CATEGORY_EXAMS.get(c, []) for c in cats}
    cat_lists['_thyroid'] = ['thyroid', 'eye_signs', 'thyroid_bruit', 'post_tremor', 'radial', 'skin_temp']
    floor = []
    for k, c in enumerate(cats[:3]):
        for i in cat_lists.get(c, [])[:(6 if k == 0 else 2)]:
            if i not in floor and i not in always and i not in deny:
                floor.append(i)
    in_cat = {i for c in cats for i in cat_lists.get(c, [])}
    menu_ids = in_cat | set(core) | {'gait', 'cervical_ln', 'skin_temp', 'radial', 'post_tremor', 'dtr', 'power',
                                             'bowel', 'jvp', 'orthostatic'}
    allowed = []
    for e in banks.EXAM_BANK:
        i = e[0]
        if i in always or i not in menu_ids or i in deny or (i == 'vitals' and has_vs):
            continue
        if i in bank2.RISKY_EXAMS and i not in in_cat:
            continue
        if i == 'eye_signs' and not (re.search(banks.THYROID_RE, diff_txt, flags=re.I) or i in floor):
            continue
        if i in banks.CONDITIONAL_EXAMS and i != 'eye_signs' and not re.search(banks.CONDITIONAL_EXAMS[i], diff_txt):
            continue
        allowed.append(e)
    allowed_ids = {e[0] for e in allowed}
    need = max(0, total - len(always) - len(floor))
    llm_ids = []
    if need > 0 and enc.budget.can_call(cfg['CALL_RESERVE']):
        pos, neg = [], []
        for e in enc.ledger:
            if e['kind'] == 'SAY' and e.get('phase') in ('interview', 'first') and not e.get('refused'):
                (neg if re.match(r'\s*(아니|없|안\s)', e.get('reply') or '') else pos).append(
                    f"{e.get('label') or e['text']}: {e['reply'][:30]}")
        menu = '\n'.join(f'{e[0]} | {e[1].replace("하겠습니다", "").strip()} | {e[2]}' for e in allowed)
        sys_prompt = ('신체진찰 항목을 고릅니다. 아래 목록의 id만 쓰고(목록 밖 진찰 금지), 같은 부위·같은 목적은 중복하지 마세요. '
                      '감별진단을 확인·배제하는 진찰을 먼저, 표준 기본 진찰(심음 청진·폐 청진은 특별한 이유가 없으면 포함, 그다음 '
                      '복부 촉진, 결막, 의식)은 남는 자리에. 성장도표 확인과 성장 속도 산출처럼 결과가 겹치는 진찰은 하나만. '
                      '정신·수면·약물 관련 증례에서는 복부·하지 진찰보다 그 증상과 관련된 신경·자율신경 진찰을 먼저 고르세요. '
                      'JSON 하나만 출력하세요.\n진찰 목록(id | 진찰 | 계통):\n' + menu)
        sex = {'F': '여', 'M': '남'}.get(prof.get('sex'), '?')
        user = (f"환자 요약: {prof.get('age')}세 {sex}, 주호소 {prof.get('cc')}, 카테고리 {prof.get('categories')}\n"
                f"문진 핵심(양성): {pos[:25]}\n(음성): {neg[:20]}\n현재 감별진단: {enc.differentials}\n"
                f"이미 하기로 한 진찰: {always + floor}\n고를 개수: {need}\n"
                '출력: {"exam_ids": ["중요한 순서"]}')
        res = ask_json(enc.client, enc.budget, sys_prompt, user, effort=cfg['EFFORT_EXAMS'], max_tokens=6000,
                       tag='exams', want=dict, tries=2, reserve=cfg['CALL_RESERVE'])
        for i in (res or {}).get('exam_ids') or []:
            i = str(i).strip()
            if i in allowed_ids and i not in llm_ids and i not in floor:
                llm_ids.append(i)
    rest = [i for c in cats for i in cat_lists.get(c, [])]
    order = []
    for i in always + floor + llm_ids + rest + core:
        if i not in order and i not in deny and (i in always or i in allowed_ids):
            order.append(i)
    # abd_palp·liver_spleen 둘 다 가능하지만 예산이 빠듯하면 복부 촉진 우선(순서로 해결)
    # v7 C2-4: 실행할 앞 total개를 부위별로 안정 정렬(활력 → 외관 → record.SECTION_ORDER). tail(거절 예비)은 그대로.
    from . import record
    rank = {s: k for k, s in enumerate(record.SECTION_ORDER)}
    head, tail = order[:total], order[total:]
    head.sort(key=lambda i: (0 if i == 'vitals' else 1 if i == 'general' else 2,
                             rank.get(banks.EXAM_BY_ID[i][2], 99)))
    order = head + tail
    log(f'exams plan: {order[:total]}')
    done = 0
    for i in order:
        if done >= total or not enc.can_act():
            break
        if enc.turns_remaining <= cfg['EXPLAIN_N'] + 1:
            break
        if i in enc.blacklist or i in enc.done_exams:
            continue
        e = banks.EXAM_BY_ID.get(i)
        if not e:
            continue
        entry = enc.act('EXAM', e[1], phase='exam', qid=i)
        if entry is None:
            continue
        done += 1
        if entry.get('refused'):
            enc.blacklist.add(i)
            continue
        entry['system'] = e[2]
        enc.done_exams.append(i)

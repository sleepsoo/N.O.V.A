"""v2 문진: intake(LLM) → 체크리스트(필수★·BOOST·덮임) → 첫 묶음(은행) → luna 배치 계획 2회 → ICE. (v2_spec §5.5, §8.2, §8.3)"""
from __future__ import annotations

import json
import re

from . import bank2
from . import cpx
from . import guidelines
from . import store as storemod
from .llm import ask_json
from .util import extract_numbers, fits, is_similar, log, nfc, parse_age, parse_sex, validate_question

ROLE = '당신은 한국 외래 진료실의 숙련된 의사입니다.'
ICE_SLOTS = ('ice_concern', 'ice_disease', 'ice_expect')

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
    return _intake_post(enc, res)


def _intake_post(enc, res) -> dict:
    opening = enc.opening
    age = parse_age(opening)
    sex = parse_sex(opening)
    peds_re = bool(re.search(r'(보호자|엄마|아빠|어머니|아버지|할머니|할아버지).{0,20}(함께|같이|데리고|동반|왔)', opening))
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
            f"사실 장부(양성·모호 단서와 아직 확인 안 된 세부 — 세부 확인 질문을 우선):\n"
            f"{enc.store.summary() if getattr(enc, 'store', None) else '(없음)'}\n"
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
    return True


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
    st = getattr(enc, 'store', None)
    if st is not None:
        st.record(slot, label, entry)
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
    enc.store = storemod.FactStore()
    q_max = cfg['INTERVIEW_Q']
    ice_reserve = 2
    asked = 0
    follow_n = 0

    def left():
        # 진찰·종료 설명·환자 질문 답(ANSWER_RESERVE) 턴을 문진보다 먼저 예약
        by_turns = enc.turns_remaining - (cfg['EXAM_N'] + cfg['EXPLAIN_N'] + 1 + cfg.get('ANSWER_RESERVE', 0))
        return min(q_max - enc.counts['interview'], by_turns)

    def drill(slot, entry):
        """사실 장부: 양성 답이면 그 항목의 세부 질문을 바로 다음 턴에(증례당 FOLLOW_MAX개까지)."""
        nonlocal follow_n
        if not entry or entry.get('refused'):
            return
        for fslot, flabel, fq in enc.store.followups(slot, entry.get('reply') or ''):
            if follow_n >= cfg.get('FOLLOW_MAX', 0) or left() <= ice_reserve or not enc.can_act():
                return
            if fslot in cl.covered or fslot in cl.asked or is_similar(fq, enc.asked):
                continue
            if fslot not in cl.items:
                cl.items[fslot] = {'label': flabel, 'q': fq, 'prio': 1, 'group': 'follow', 'order': len(cl.items) + 1}
            e2 = ask(enc, cl, fslot, fq)
            if e2 and not e2.get('refused'):
                follow_n += 1
                log(f'store follow-up [{slot} -> {fslot}]: {fq}')

    # 1. 첫 질문: 공감 + 첫 필수 질문
    ranked = cl.ranked()
    first_slot = 'hpi_onset' if 'hpi_onset' in ranked else (ranked[0] if ranked else 'hpi_course')
    first_q = cl.items.get(first_slot, {}).get('q', '언제부터 그러셨어요?')
    first = f"{prof.get('empathy', '')} {first_q}".strip()
    if not fits(first):
        first = first_q
    if enc.can_act():
        drill(first_slot, ask(enc, cl, first_slot, first, phase='first'))
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
        for slot, q in good[:n]:
            if left() <= ice_reserve or not enc.can_act() or not enc.phase_time_ok():
                break
            if slot != 'free' and (slot in cl.covered or slot in cl.asked):
                continue  # 직전 답으로 덮였으면 건너뜀(중복 방지)
            if slot == 'free':
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
            drill(slot, entry)
            reply = entry.get('reply') or ''
            if slot == 'gr_record' and re.search(r'(수첩|기록|있)', reply) and not re.match(r'\s*(아니|없)', reply) \
                    and 'gr_values' in cl.items and 'gr_values' not in cl.asked and left() > ice_reserve:
                ask(enc, cl, 'gr_values', cl.items['gr_values']['q'])
            if slot == 'ps_si' and not re.match(r'\s*(아니|없|전혀)', reply) and 'md_plan' in cl.items \
                    and left() > ice_reserve:
                ask(enc, cl, 'md_plan', cl.items['md_plan']['q'])
        if sent == 0:
            break
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
    # 시작 정보에 활력징후 값이 있으면 다시 측정하지 않는다(턴 절약, 그 자리를 증례별 진찰에)
    has_vs = bool(re.search(r'\d{2,3}\s*/\s*\d{2,3}', enc.vitals or ''))
    always = ([] if has_vs else ['vitals']) + ['general'] + (['anthro'] if peds else [])
    total = cfg['EXAM_N']
    cats = list(prof.get('categories') or [])
    diff_txt = ' '.join(enc.differentials or []) + ' ' + (prof.get('cc') or '')
    thyroid_dx = bool(re.search(banks.THYROID_RE, ' '.join((enc.differentials or [])[:2]), flags=re.I))
    if thyroid_dx and not set(cats) & {'weight_loss', 'palpitation', 'fatigue'}:
        cats.append('_thyroid')
    cat_lists = {c: bank2.CATEGORY_EXAMS.get(c, []) for c in cats}
    cat_lists['_thyroid'] = ['thyroid', 'eye_signs', 'thyroid_bruit', 'post_tremor', 'radial', 'skin_temp']
    floor = []
    for k, c in enumerate(cats[:3]):
        for i in cat_lists.get(c, [])[:(6 if k == 0 else 2)]:
            if i not in floor and i not in always:
                floor.append(i)
    in_cat = {i for c in cats for i in cat_lists.get(c, [])}
    menu_ids = in_cat | set(bank2.CORE12) | {'gait', 'cervical_ln', 'skin_temp', 'radial', 'post_tremor', 'dtr', 'power',
                                             'bowel', 'jvp', 'orthostatic'}
    allowed = []
    for e in banks.EXAM_BANK:
        i = e[0]
        if i in always or i not in menu_ids or (i == 'vitals' and has_vs):
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
    for i in always + floor + llm_ids + rest + bank2.CORE12:
        if i not in order and (i in always or i in allowed_ids):
            order.append(i)
    # abd_palp·liver_spleen 둘 다 가능하지만 예산이 빠듯하면 복부 촉진 우선(순서로 해결)
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


# ================================================================ v8: CPX 체크리스트 문진 (sota34_analysis §9.10 단계 1~4)
V8_SYSTEMS = ['gen', 'cv', 'resp', 'gi', 'gu', 'neuro', 'eye', 'neck', 'psy', 'sleep', 'drug', 'wm', 'hx', 'meds', 'fh', 'sh',
              'endo', 'ent', 'msk', 'skin', 'peds', 'growth']


def intake_v8(enc) -> dict:
    """접수 LLM 1회: 프로필 + 감별 5(놓치면 안 될 질환 포함) + 판별 문항 + 예상 치료 금기 확인 문항."""
    opening = enc.opening
    cats_desc = '\n'.join(f'{k}: {v}' for k, v in bank2.CATEGORY_DESC.items())
    sys_prompt = (ROLE + ' 진료 시작 전, 환자의 첫 진술과 활력징후만 보고 진료를 준비합니다. JSON 객체 하나만 출력하세요.\n'
                  f'카테고리 목록(id: 설명):\n{cats_desc}')
    user = (f'시작 정보(환자 첫 진술): {opening}\n활력징후: {enc.vitals.replace(chr(10), ", ")}\n'
            '[질문 문구 규칙] 공백 포함 28자 이내, 쉬운 존댓말 의문문 하나(물음표 1개), 한 가지만 묻기(두 항목이면 같은 장기·계통이고 '
            '공통 술어 하나일 때만, 예: "가슴 통증이나 숨찬 증상 있으세요?"). 영어·약어 금지. 시작 정보에 이미 있는 내용 금지.\n'
            '출력:\n{"age": 정수|null, "sex": "M"|"F"|null, "pediatric": 만 15세 미만 또는 보호자가 대신 답하면 true,\n'
            ' "informant": "본인"|"어머니"|"아버지"|"할머니"|"보호자",\n'
            ' "chief_complaint": "주호소 명사구(요청이 있으면 괄호로, 예: 불면 (수면제 처방 원함))",\n'
            ' "request": "환자가 요청한 것, 없으면 \'\'",\n'
            ' "categories": ["카테고리 id 1~3개, 진단에 가장 중요한 것 먼저"],\n'
            ' "differential": ["가능성 높은 순 감별진단 5개, 놓치면 안 될 위험 질환 1개 이상 포함"],\n'
            ' "discriminators": [{"q": "감별진단을 서로 가르는 문진 질문", "label": "항목명 10자 이내", "system": "계통"}],'
            '  ← 4~8개, 중요한 순(위험 징후·판별 소견 우선)\n'
            ' "contra": [{"q": "가장 가능성 높은 진단의 1차 치료 전에 확인할 금기·안전 질문(예: 천식이나 심장병 있으세요?)", '
            '"label": "항목명"}] ← 0~2개\n'
            f' "empathy": "주호소에 대한 아주 짧은 공감(존댓말, 8자 이내, 예: 걱정되셨죠. / 힘드셨죠.)"}}\n'
            f'계통 값: {V8_SYSTEMS}')
    res = ask_json(enc.client, enc.budget, sys_prompt, user, effort=enc.cfg['EFFORT_INTAKE'], max_tokens=7000,
                   tag='intake', want=dict, tries=2, reserve=enc.cfg['CALL_RESERVE'])
    prof = _intake_post(enc, res)
    res = res if isinstance(res, dict) else {}
    emp = nfc(str(res.get('empathy') or '')).strip()
    if not emp or len(emp) > 9 or '?' in emp:
        emp = '힘드셨죠.' if re.search(r'(잠|불면|아프|아파|통증|힘들)', opening) else '걱정되셨죠.'
    prof['empathy_short'] = emp if emp.endswith('.') else emp + '.'

    def items(key, n):
        out = []
        for d in res.get(key) or []:
            if not isinstance(d, dict):
                continue
            q = nfc(str(d.get('q') or '')).strip()
            label = nfc(str(d.get('label') or '')).strip()[:12] or q[:10]
            sys_ = str(d.get('system') or 'gen').strip()
            if q:
                out.append({'q': q, 'label': label, 'sys': sys_ if sys_ in V8_SYSTEMS else 'gen'})
        return out[:n]
    enc.cpx_llm = {'discriminators': items('discriminators', 8), 'contra': items('contra', 2)}
    log(f"intake_v8 llm items: {enc.cpx_llm}")
    return prof


def _label_kw(label: str) -> str:
    words = [w for w in re.findall(r'[가-힣]{2,}', label or '') if w not in ('여부', '양상', '유무', '증상', '세부', '정도')]
    return '|'.join(dict.fromkeys(w[:2] for w in words)) or '.'


def _llm_units(enc, units: list[dict], bank: bool, built: dict | None = None) -> list[dict]:
    """접수 LLM 문항을 검증해 단위로(v8c 결함 #5).
    은행 범주: 판별 문항은 버린다(은행 항목이 대체). 금기 확인은 검증·관련성 통과 + 성인일 때만 prio 3(은행·필수를 밀어내지 않음).
    은행 밖 범주: 판별 8개까지(prio 1~2)·금기 prio 1, 모두 관련성 검사를 거친다."""
    llm = getattr(enc, 'cpx_llm', None) or {}
    prof = getattr(enc, 'profile', None) or {}
    peds = bool(prof.get('pediatric'))
    cat_sys = cpx.category_systems(built or {'units': units}, prof)
    out = []
    existing = [u['q'] for u in units]
    generic = {'양상', '부위', '지속시간', '발생양상', '유발상황', '경과', '강도(NRS)', '복용약', '가족력'}
    labels = {re.sub(r'\s', '', i[1]) for u in units for i in u['items']
              if len(re.sub(r'\s', '', i[1])) >= 2 and re.sub(r'\s', '', i[1]) not in generic}

    def dup(q):  # 은행 항목 이름이 질문에 그대로 있으면 중복(예: '천식이 있으세요?' ↔ 은행 '천식')
        t = re.sub(r'\s', '', q)
        return next((lab for lab in labels if lab in t), None)
    def checked(q):
        ok, why = cpx.check_question(q)
        ok2, why2 = validate_question(q, existing + [u['q'] for u in out])
        if ok and ok2 and dup(q):
            ok, why = False, f'dup:{dup(q)}'
        if ok and ok2:
            ok, why = cpx.relevant_question(q, cat_sys, peds)
        return ok and ok2, f'{why}/{why2}'
    for k, d in enumerate(llm.get('contra') or []):
        if bank and peds:
            log(f'llm contra dropped (pediatric bank): {d["q"]}')
            continue
        ok, why = checked(d['q'])
        if not ok:
            log(f'llm contra rejected ({why}): {d["q"]}')
            continue
        # 은행 범주는 필수 알레르기·천식 단위가 이미 있으므로 배경(prio 3) — 은행·필수 문항을 밀어내지 않게. 은행 밖이면 핵심(prio 1)
        out.append(cpx.U(f'llm_contra{k}', 'hx', 3 if bank else 1, d['q'],
                         [(f'llm_contra{k}', d['label'], _label_kw(d['label']))],
                         d['sys'] if d['sys'] in ('hx', 'meds') else 'hx', safety=not bank))
    if bank:
        if llm.get('discriminators'):
            log(f"llm discriminators dropped (bank category): {[d['q'] for d in llm['discriminators']]}")
        return out
    n = 0
    for k, d in enumerate(llm.get('discriminators') or []):
        if n >= 8:
            break
        ok, why = checked(d['q'])
        if not ok:
            log(f'llm item rejected ({why}): {d["q"]}')
            continue
        prio = 1 if n < 5 else 2
        out.append(cpx.U(f'llm_d{k}', 'core', prio, d['q'], [(f'llm_d{k}', d['label'], _label_kw(d['label']))], d['sys']))
        n += 1
    return out


def _first_open(prof: dict, main) -> str:
    emp = prof.get('empathy_short') or '걱정되셨죠.'
    if prof.get('pediatric'):
        cands = [f'안녕하세요, {emp} 아이가 다른 불편한 데는요?', '안녕하세요, 아이가 다른 불편한 데는요?']
    elif main in ('substance', 'insomnia'):
        cands = [f'안녕하세요, {emp} 잠 말고 불편한 데는요?', '안녕하세요, 잠 말고 불편한 데는요?']
    else:
        cands = [f'안녕하세요, {emp} 다른 불편한 데는요?', '안녕하세요, 다른 불편한 데는요?']
    return next((c for c in cands if fits(c)), '다른 불편한 데는요?')


class CpxState:
    """항목 상태 장부: item id → {'pol','turn','answered'}; 단위별 질문 기록."""

    def __init__(self, built: dict, chosen: list[dict], backlog: list[dict]):
        self.built = built
        self.units = built['units']
        self.chosen = chosen
        self.backlog = backlog
        self.status: dict[str, dict] = {}
        self.asked_units: list[str] = []
        self.reasked: set[str] = set()
        self.follow_n = 0

    def mark(self, iid, pol, turn, how):
        cur = self.status.get(iid)
        if cur and cur.get('how') == 'asked' and how != 'asked':
            return
        self.status[iid] = {'pol': pol, 'turn': turn, 'how': how}

    def remaining_items(self, u) -> list[tuple]:
        return [i for i in u['items'] if i[0] not in self.status]

    def must_left(self, queue) -> int:
        """핵심(prio 1)·안전·필수 공통 병력·ICE 중 아직 덮이지 않은 단위 수(후속·재질문 가드)."""
        return sum(1 for u in queue if (u['prio'] == 1 or u['safety'] or cpx.is_must(u)) and self.remaining_items(u))

    def hard_left(self, queue) -> int:
        """필수 공통 병력(must)·ICE 중 남은 단위 수 — 어떤 단위도 이 자리를 빼앗지 못한다."""
        return sum(1 for u in queue if cpx.is_must(u) and self.remaining_items(u))


def run_v8(enc):
    cfg = enc.cfg
    prof = enc.profile
    built = cpx.build(prof, enc.opening)
    units = built['units']
    units += _llm_units(enc, units, built['bank'], built)
    budget = int(cfg.get('INTERVIEW_Q', 17))
    st = CpxState(built, [], [])
    enc.cpx = st
    enc.checklist = None
    enc.store = storemod.FactStore()
    # v8c: 진찰(활력 1 포함)·설명·답 턴을 고정 예약
    reserve = int(cfg.get('EXAM_N', 7)) + int(cfg.get('EXPLAIN_MIN', 7)) + int(cfg.get('ANSWER_RESERVE', 2))
    all_items = [i for u in units for i in u['items']]

    def left():
        by_turns = enc.turns_remaining - reserve
        return min(budget - enc.counts['interview'], by_turns)

    labels = {i[0]: (i[1], i[2]) for i in all_items}

    def note_mentions(reply, turn, skip_ids=(), entry=None):
        for iid in cpx.positive_mentions(all_items, reply):
            if iid in skip_ids:
                continue
            st.mark(iid, '+', turn, 'mention')
            if entry is not None:  # 기록용: 묻지 않았지만 말한 양성 항목도 그 턴의 판정으로 남긴다
                entry.setdefault('items', [])
                entry.setdefault('mentioned', []).append(iid)
                entry['items'].append({'id': iid, 'label': labels[iid][0], 'answered': True, 'pol': '+',
                                       'kw': labels[iid][1], 'mention': True})

    for iid in cpx.positive_mentions(all_items, enc.opening):
        st.mark(iid, '+', 0, 'opening')

    def ask_unit(u, q=None, items=None, phase='interview'):
        q = q or u['q']
        items = items or u['items']
        entry = enc.act('SAY', q, phase=phase, qid=u['id'], label='·'.join(i[1] for i in items))
        if entry is None or entry.get('refused'):
            return entry
        enc.counts['interview'] += 1
        st.asked_units.append(u['id'])
        if entry.get('one_at_a_time'):
            enc.retry_single(q, phase)
            return entry
        reply = entry.get('reply') or ''
        judged = cpx.judge(items, reply)
        entry['items'] = judged
        entry['unit'] = u['id']
        entry['ukind'] = u['kind'] if len(items) == len(u['items']) else ('single' if len(items) == 1 else 'pair')
        entry['safety'] = bool(u['safety'])
        for j in judged:
            if j['answered']:
                st.mark(j['id'], j['pol'], entry['turn'], 'asked')
        note_mentions(reply, entry['turn'], skip_ids={i[0] for i in items} | set(st.status), entry=entry)
        enc.store.record(u['id'], entry.get('label') or '', entry)
        return entry

    # 1. 첫 턴: 인사·공감 + 개방형 질문 1개(공감 접두가 잘려도 질문 문장은 남는다)
    if enc.can_act():
        e = enc.act('SAY', _first_open(prof, built['main']), phase='first', qid='open', label='개방형')
        if e and not e.get('refused'):
            enc.counts['interview'] += 0  # 첫 턴은 문진 예산(INTERVIEW_Q) 밖
            note_mentions(e.get('reply') or '', e['turn'], entry=e)
            enc.store.record('open', '개방형', e)

    # 2. 시작 정보·개방형 답으로 이미 덮인 단위는 예산을 쓰지 않게 컴파일
    chosen, backlog = cpx.compile_units(units, budget, covered=set(st.status))
    st.chosen, st.backlog = chosen, backlog
    log(f"cpx: main={built['main']} bank={built['bank']} chosen={[u['id'] for u in chosen]} "
        f"backlog={[u['id'] for u in backlog]}")
    queue = list(chosen)
    pending = []   # 바로 다음에 물을 (unit, q, items): 안전 재질문·양성 후속
    reask_max = int(cfg.get('REASK_MAX', 1))
    follow_max = int(cfg.get('FOLLOW_MAX', 2))
    while left() > 0 and enc.can_act() and enc.phase_time_ok():
        if pending:
            u, q, items = pending.pop(0)
            if all(i[0] in st.status for i in items):
                continue
            if st.must_left(queue) >= left():   # drill·재질문 가드: 필수 미확인 단위가 남은 자리를 다 쓰면 건너뜀
                log(f'cpx pending dropped (guard): {q}')
                continue
            ask_unit(u, q, items)
            continue
        if not queue:
            nxt = next((u for u in st.backlog if u['prio'] <= 2 and st.remaining_items(u)), None)
            if nxt is None:
                break
            st.backlog.remove(nxt)
            queue.append(nxt)
        u = queue.pop(0)
        rem = st.remaining_items(u)
        if not rem:
            log(f'cpx skip (covered): {u["id"]}')
            continue
        hard = cpx.is_must(u)
        core_u = hard or u['prio'] == 1
        if not hard and (st.hard_left(queue) >= left() or (not core_u and st.must_left(queue) >= left())):
            # 필수 공통 병력·ICE(또는 핵심 단위)가 남은 자리를 다 쓰면 나머지는 뒤로(자리가 남으면 대기열에서 다시)
            st.backlog.insert(0, u)
            log(f'cpx defer (must first): {u["id"]}')
            continue
        q, items = u['q'], u['items']
        if len(rem) < len(u['items']):
            single = [i for i in rem if i[0] in cpx.ITEM_Q]
            if len(rem) == 1 and single:
                q, items = cpx.ITEM_Q[rem[0][0]], rem
        if is_similar(q, enc.asked, 0.9):
            continue
        entry = ask_unit(u, q, items)
        if not entry or entry.get('refused') or not entry.get('items'):
            continue
        judged = entry['items']
        # 미응답 안전 항목: 단독 재질문 1회
        if u['safety'] and len(st.reasked) < reask_max * 2:
            for j in judged:
                if not j['answered'] and j['id'] in cpx.ITEM_Q and j['id'] not in st.reasked:
                    st.reasked.add(j['id'])
                    it = next(i for i in u['items'] if i[0] == j['id'])
                    pending.append((u, cpx.ITEM_Q[j['id']], [it]))
                    log(f'cpx reask safety item: {j["id"]}')
                    break
        # 새 양성 → 그 계통 후속 1개(필수 미확인 수가 남은 자리 이상이면 금지)
        f = u.get('follow')
        on = f[4] if f and len(f) > 4 else None
        pos = u['stage'] != 'ice' and any(j['answered'] and j['pol'] in ('+', '?') and not j.get('mention')
                                          and (on is None or j['id'] == on) for j in judged)
        if f and pos and st.follow_n < follow_max and f[0] not in st.status:
            already = f[3] and re.search(f[3], entry.get('reply') or '')
            must = st.must_left(queue) + len(pending)
            room = left() - 1
            if not already and must < room + 0 and not is_similar(f[2], enc.asked):
                st.follow_n += 1
                fu = cpx.U(f[0], u['stage'], 2, f[2], [(f[0], f[1], '.')], u['sys'])
                pending.insert(0, (fu, f[2], fu['items']))
                log(f'cpx follow-up [{u["id"]} -> {f[0]}] must={must} room={room}')
            elif not already:
                log(f'cpx follow-up skipped (guard) [{u["id"]}] must={must} room={room}')
    missing = [u['id'] for u in queue if st.remaining_items(u) and (u['prio'] == 1 or u['safety'])]
    log(f'interview_v8 done: asked={len(st.asked_units)} items={len(st.status)} missing_must={missing}')


CARDIO_EXAM_CATS = {'cardio', 'resp', 'weight_loss', 'fatigue', 'palpitation', 'chest_pain', 'dyspnea', 'edema',
                    'cough_fever'}
CARDIO_POS_RE = re.compile(r'숨이?\s*(차|가빠)|숨차|숨참|가슴.{0,4}(아프|아파|통증|답답|조여)|두근')


def _cardio_positive(enc, st) -> bool:
    """문진에서 호흡곤란·흉통·두근거림 양성(항목 판정 또는 답 문장)."""
    if st is not None and any((st.status.get(i) or {}).get('pol') == '+' for i in ('ros_dysp', 'ros_cp', 'ros_palp')):
        return True
    for e in getattr(enc, 'ledger', None) or []:
        if e.get('kind') != 'SAY' or e.get('phase') not in ('first', 'interview'):
            continue
        for seg in cpx._segments(e.get('reply') or ''):
            if CARDIO_POS_RE.search(seg) and not cpx.NEG_TOK.search(seg):
                return True
    return False


def exam_plan_v8(enc) -> list[str]:
    """v8c 진찰 순서: 활력징후 측정(항상 1회, EXAM_N에 포함) → 범주 핵심 진찰.
    심폐 관련 범주이거나 호흡곤란·흉통·두근거림 양성이면 심음·폐 청진을 핵심 3개 다음(EXAM_N 안)으로 당긴다.
    뒤에는 범주 표준 진찰 목록을 붙여 남는 턴(문진 조기 종료·설명 여유 턴)에 쓴다."""
    from . import banks
    st = getattr(enc, 'cpx', None)
    built = st.built if st else {}
    core = list(built.get('exams') or [])
    prof = enc.profile or {}
    order = ['vitals'] + [i for i in core if i != 'vitals']
    top = ' '.join((enc.differentials or [])[:2])
    if re.search(banks.THYROID_RE, top, flags=re.I) and 'thyroid' not in order:
        order.insert(min(2, len(order)), 'thyroid')
    if prof.get('pediatric') and 'anthro' not in order and built.get('main') != 'growth':
        order.insert(1, 'anthro')
    cats = set(prof.get('categories') or []) | {built.get('main')}
    if cats & CARDIO_EXAM_CATS or _cardio_positive(enc, st):
        pos = 4   # 활력 + 범주 핵심 3개 다음
        move = [i for i in ('heart', 'lung') if i not in order[:pos]]
        order = [i for i in order if i not in move]
        pos = min(pos, len(order))
        order[pos:pos] = move
    extra = [e for c in (prof.get('categories') or []) for e in bank2.CATEGORY_EXAMS.get(c, [])]
    out = []
    for i in order + extra:
        if i not in out and i in banks.EXAM_BY_ID:
            out.append(i)
    return out


def _do_exam(enc, i) -> bool:
    """진찰 1회. 행동(턴)을 썼으면 True."""
    from . import banks
    e = banks.EXAM_BY_ID.get(i)
    if not e:
        return False
    entry = enc.act('EXAM', e[1], phase='exam', qid=i)
    if entry is None:
        return False
    if entry.get('refused'):
        enc.blacklist.add(i)
        return True
    entry['system'] = e[2]
    enc.done_exams.append(i)
    return True


def examine_v8(enc):
    """P3(v8c): 활력징후 측정 1회 + 범주 핵심 진찰(표준 진찰표 문구) EXAM_N개.
    문진이 예산보다 일찍 끝났으면 남는 턴만큼 목록에서 더 한다. 설명·답 예약(EXPLAIN_MIN + ANSWER_RESERVE)에서 멈춘다.
    끝나면 enc.exam_backlog = 아직 안 한 진찰 id(우선순위 순) — 설명 단계 여유 턴에 spare_exam()이 쓴다."""
    cfg = enc.cfg
    st = getattr(enc, 'cpx', None)
    if not (st and st.built.get('exams')):
        enc.exam_backlog = []
        return examine(enc)
    order = exam_plan_v8(enc)
    exam_n = int(cfg.get('EXAM_N', 7))
    short = max(0, int(cfg.get('INTERVIEW_Q', 17)) - int(enc.counts.get('interview', 0)))
    total = exam_n + short
    stop_at = int(cfg.get('EXPLAIN_MIN', 7)) + int(cfg.get('ANSWER_RESERVE', 2))
    log(f'exams plan v8: {order[:total]} (total={total}, backlog={order[total:]})')
    done = 0
    for i in order:
        if done >= total or not enc.can_act() or enc.turns_remaining <= stop_at:
            break
        if i in enc.blacklist or i in enc.done_exams:
            continue
        if _do_exam(enc, i):
            done += 1
    enc.exam_backlog = [i for i in order if i not in enc.done_exams and i not in enc.blacklist]


def spare_exam(enc) -> bool:
    """설명 단계의 남는 턴 1개로 enc.exam_backlog의 다음 진찰 1개를 한다. 행동했으면 True."""
    backlog = getattr(enc, 'exam_backlog', None) or []
    while backlog:
        i = backlog.pop(0)
        if i in enc.blacklist or i in enc.done_exams:
            continue
        if not enc.can_act():
            backlog.insert(0, i)
            return False
        if _do_exam(enc, i):
            return True
    return False

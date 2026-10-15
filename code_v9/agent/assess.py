"""v2 진단 + A칸: high 1회가 사실표(F#)·진찰(E#)을 인용하고, 턴 번호는 코드가 붙인다. (v2_spec §8.6, §9.3, §9.4)"""
from __future__ import annotations

import re

from . import guidelines
from .facts import table as facts_table
from .llm import ask_json
from .util import log, nfc

ROLE = '당신은 한국 대학병원 외래의 숙련된 전문의입니다. 사실표와 진찰 소견만 근거로 주진단과 평가(A)를 씁니다. JSON 하나만 출력하세요.'

DX_CANON = [
    (r'(graves|그레이브스|그레브스|그라브스)', '그레이브스병에 의한 갑상샘항진증', "Graves' disease"),
    (r'(constitutional|체질성)', '체질성 성장지연', 'Constitutional delay of growth and puberty'),
    (r'(sedative|hypnotic|수면제.{0,4}(의존|사용장애)|졸피뎀.{0,4}(의존|사용장애)|진정제.{0,6}사용장애)',
     '수면제(진정수면제) 사용장애', 'Sedative-Hypnotic Use Disorder'),
    (r'(familial short|가족성\s*저신장)', '가족성 저신장', 'Familial short stature'),
    (r'(iron deficiency|철\s*결핍)', '철결핍성 빈혈', 'Iron deficiency anemia'),
    (r'(major depressive|주요\s*우울)', '주요우울장애', 'Major depressive disorder'),
]


VAGUE_DX_RE = r'(원인\s*미상|미상|불명|undetermined|unknown|unspecified|평가\s*필요|^\s*(저신장|불면|체중\s*감소)(증)?\s*$)'


def exam_rows(enc) -> list[dict]:
    from .encounter import exam_name
    out = []
    k = 0
    for e in enc.ledger:
        if e['kind'] != 'EXAM' or e.get('refused'):
            continue
        k += 1
        out.append({'id': f'E{k}', 'turn': e['turn'], 'name': exam_name(e['text']), 'result': e.get('reply') or ''})
    return out


def derived_numbers(enc) -> dict:
    """키·몸무게·BMI·체중 감소율 등(시작 정보 기반). 기록·검증에 쓰는 파생 수치."""
    from .util import parse_korean_number
    t = nfc(enc.opening)
    out = {}

    def grab(pattern):
        vals = []
        for m in re.finditer(pattern, t):
            w = m.group(1).replace(' ', '')
            v = parse_korean_number(w)
            if v is None:
                for i in range(len(w)):
                    v = parse_korean_number(w[i:])
                    if v is not None:
                        break
            if v is not None:
                vals.append(float(v))
        return vals
    hts = grab(r'([가-힣\d.\s]{1,10}?)\s*(?:센티미터|센티|cm)')
    wts = grab(r'([가-힣\d.\s]{1,10}?)\s*(?:키로그람|킬로그램|킬로그람|키로|킬로|kg)')
    ht = next((h for h in reversed(hts) if 40 <= h <= 220), None)
    wt = None
    m = re.search(r'지금은\s*([가-힣\d.\s]{1,10}?)\s*(?:키로그람|킬로그램|키로|킬로|kg)', t)
    if m:
        cand = grab(r'지금은\s*([가-힣\d.\s]{1,10}?)\s*(?:키로그람|킬로그램|키로|킬로|kg)')
        wt = cand[-1] if cand else None
    if wt is None and wts:
        wt = wts[-1]
    if ht and wt and 2 <= wt <= 200:
        out['Ht'] = ht
        out['Wt'] = wt
        if not enc.profile.get('pediatric'):
            out['BMI'] = round(wt / (ht / 100) ** 2, 1)
    return out


def normalize_dx(ko: str, en: str) -> str:
    ko = re.sub(r'\s+', ' ', nfc(ko or '').strip())
    en = re.sub(r'\s+', ' ', nfc(en or '').strip())
    en = re.sub(r'\s*\(.*?\)\s*', ' ', en).strip()
    joined = f'{ko} {en}'
    for pat, cko, cen in DX_CANON:
        if re.search(pat, joined, flags=re.I):
            # 표준명으로 통일(r6c: '졸피뎀 사용장애 (Zolpidem use disorder)'가 허용 진단 목록과 문자열 불일치)
            ko, en = cko, cen
            break
    ko = re.split(r'\s+및\s+', ko)[0].strip()
    s = f'{ko} ({en})' if ko and en and en.lower() not in ko.lower() else (ko or en)
    while len(s.encode('utf-8')) > 490:
        s = s[:-1]
    return s


def dx_and_assess(enc) -> dict:
    facts = getattr(enc, 'facts', None) or []
    exams = exam_rows(enc)
    der = derived_numbers(enc)
    enc.derived = der
    ex_txt = '\n'.join(f"{x['id']} | {x['turn']} | {x['name']} | {x['result']}" for x in exams) or '(없음)'
    gl = guidelines.hint_dx(enc)
    ice = ' / '.join(f"{e['text']} → {e['reply']}" for e in enc.ledger
                     if str(e.get('qid', '')).startswith('ice') and not e.get('refused'))
    user = (f'시작 정보: {enc.opening} / 활력징후: {enc.vitals.replace(chr(10), ", ")} / 파생 수치: {der or "없음"}\n'
            f'사실표(id | 턴 | 영역 | 항목 | +/- | 세부):\n{facts_table(facts) or "(없음)"}\n'
            f'진찰 소견(id | 턴 | 진찰 | 결과):\n{ex_txt}\n'
            f'문진 중 감별진단: {enc.differentials}\n'
            f'{gl}'
            '[주진단] 증상명이 아닌 가장 구체적인 원인 질환명(표준 한국어명 + 영문). 검사 전 임상 진단이어도 가장 가능성 높은 '
            "원인 질환 하나를 고를 것. '원인 미상', '~ 의증 평가 필요', 증상명(저신장·불면·체중 감소)만 쓰는 것은 금지.\n"
            " '및'으로 두 진단을 잇지 말 것. 예: '그레이브스병에 의한 갑상샘항진증', '체질성 성장지연', '수면제(진정수면제) 사용장애'.\n"
            ' 약물 내성·금단·조절 실패·여러 곳 처방이 있으면 해당 물질 사용장애를 우선 고려. 소아 저신장: 가족성 저신장=부모의 현재(성인) 키 '
            '자체가 작음(중간부모키 낮음)·늦은 성장 가족력 없음·골연령=역연령, 체질성 성장지연=부모 키(중간부모키)는 정상이나 부모가 '
            "'어릴 때 작았다가 중·고등학교 때 갑자기 컸다'(늦은 성장·늦은 사춘기)·성장속도 정상 하한·골연령 지연. "
            "'부모가 어릴 때 키가 작았다'는 가족성 저신장의 근거가 아니라 체질성 성장지연의 근거이며, 중간부모키가 정상이면 가족성 저신장 "
            '가능성은 낮음.\n'
            '[방법] 후보 3~4개마다 지지(for)·반대(against) 사실 id를 적고 비교해 고르세요.\n'
            '[근거] 4~6개: ①핵심 병력(수치 포함) ②진찰 소견 ③위험인자·가족력 ④다른 질환을 배제하는 음성 소견. 각 항목은 refs(F#/E#) 필수.\n'
            " 환자가 말한 것은 '호소', 진찰 결과는 '진찰상'. 검사하지 않은 결과(호르몬 수치·영상)를 정상/이상이라 쓰지 말 것. "
            '위 진찰 소견 목록에 없는 진찰(예: 하지 부종·폐 청진을 안 했으면 심부전 징후)은 있다/없다고 쓰지 말 것. '
            "환자가 '아니다'라고 한 증상을 다른 이름으로 바꿔 양성으로 쓰지 말 것(예: 묽은 변 ≠ 설사). "
            '확인된 영향과 모순되는 해석 금지. 턴 번호는 쓰지 말 것(코드가 붙임).\n'
            + (f"환자가 걱정한 것(ICE): {ice}\n" if ice else '') +
            '[감별] 4~5개 가능성 순, 이 환자에서 실제로 고려할 만한 것만. 반드시 포함: (a) 놓치면 안 될 위험 질환 1개, '
            '(b) 환자가 걱정한 질환(ICE에 있으면). reason은 "지지: … / 반대: … / 판단: …" 형식으로 사실표와 극성이 일치하는 소견을 '
            '인용(refs). test는 그 감별을 가르는 검사와 예상 결과(예: "TRAb 음성이면 섭취율 검사").\n'
            '출력: {"candidates": [{"dx": "...", "for": ["F1"], "against": ["F2"]}],\n'
            ' "diagnosis_ko": "...", "diagnosis_en": "...", "confidence": 0~1,\n'
            ' "evidence": [{"text": "사실 → 해석", "refs": ["F3","E2"]}],\n'
            ' "differential": [{"dx": "...", "reason": "...", "refs": ["F5"], "test": "..."}]}')
    res = ask_json(enc.client, enc.budget, ROLE, user, effort=enc.cfg['EFFORT_DX'], max_tokens=8000, tag='dx',
                   want=dict, tries=2, max_wait=300,
                   validate=lambda v: bool(str(v.get('diagnosis_ko') or v.get('diagnosis_en') or '').strip()))
    out = {'facts': facts, 'exams': exams}
    if not res:
        d0 = (enc.differentials or [''])[0]
        out.update({'dx': normalize_dx(d0, '') or '', 'evidence': [], 'differential': [], 'fallback': True})
        log('dx: fallback')
        return out
    ids = {f['id']: f for f in facts}
    ids.update({x['id']: x for x in exams})
    ev = []
    for item in res.get('evidence') or []:
        if not isinstance(item, dict):
            continue
        refs = [r for r in (item.get('refs') or []) if r in ids]
        text = nfc(str(item.get('text') or '')).strip()
        text = re.sub(r'\(?\s*턴\s*\d+[^)]*\)?', '', text).strip()
        if refs and text:
            ev.append({'text': text, 'refs': refs})
    diffs = []
    for item in res.get('differential') or []:
        if not isinstance(item, dict):
            continue
        name = nfc(str(item.get('dx') or '')).strip()
        if not name:
            continue
        refs = [r for r in (item.get('refs') or []) if r in ids]
        reason = re.sub(r'\(?\s*턴\s*\d+[^)]*\)?', '', nfc(str(item.get('reason') or ''))).strip()
        diffs.append({'dx': name, 'reason': reason, 'refs': refs, 'test': nfc(str(item.get('test') or '')).strip()})
    dx_ko, dx_en = res.get('diagnosis_ko'), res.get('diagnosis_en')
    if re.search(VAGUE_DX_RE, f'{dx_ko} {dx_en}', flags=re.I):
        # 막연한 진단이면 후보 중 구체적인 첫 질환으로 교체(지지 근거 많은 순)
        cands = [c for c in (res.get('candidates') or []) if isinstance(c, dict) and c.get('dx')
                 and not re.search(VAGUE_DX_RE, str(c.get('dx')), flags=re.I)]
        cands.sort(key=lambda c: len(c.get('for') or []) - len(c.get('against') or []), reverse=True)
        if cands:
            log(f"dx vague '{dx_ko}' -> '{cands[0]['dx']}'")
            dx_ko, dx_en = str(cands[0]['dx']), ''
    out.update({'dx': normalize_dx(dx_ko, dx_en), 'evidence': ev,
                'differential': diffs[:5], 'confidence': res.get('confidence'), 'candidates': res.get('candidates')})
    if (res.get('confidence') or 1) and isinstance(res.get('confidence'), (int, float)) and res['confidence'] < 0.5:
        log(f"dx low confidence {res['confidence']}")
    try:
        apply_short_stature_rule(enc, out)
    except Exception as ex:  # 규칙 실패가 진단 전체를 막지 않도록
        log(f'dx short-stature rule error: {ex}')
    return out


# ---------------------------------------------------------------- v8c: 소아 저신장 감별(가족성 vs 체질성)
SS_GROUP_RE = re.compile(r'(가족성\s*저신장|familial\s*short|체질성|constitutional|특발성\s*저신장|idiopathic\s*short|'
                         r'유전성\s*저신장|genetic\s*short)', re.I)
FSS_RE = re.compile(r'(가족성\s*저신장|familial\s*short|유전성\s*저신장|genetic\s*short)', re.I)
CDGP_RE = re.compile(r'(체질성|constitutional)', re.I)
FSS_DX = normalize_dx('가족성 저신장', '')
CDGP_DX = normalize_dx('체질성 성장지연', '')
LATE_BLOOM_RE = re.compile(r'(늦게\s*(키가\s*)?(컸|자랐|크)|고등학교.{0,20}(컸|자랐|크)|사춘기.{0,8}늦|'
                           r'중학교.{0,10}(이후|때|들어).{0,10}(컸|자랐)|어릴\s*때.{0,15}작.{0,40}(컸|자랐))')
LATE_NEG_RE = re.compile(r'^.{0,10}(않|없|안\s|아니)')
MPH_RE = re.compile(r'중간\s*부모\s*키\s*:?\s*(\d{3}(?:\.\d)?)')
_NOT_OTHER_PARENT = r'(?:(?!엄마|어머|아빠|아버|모친|부친)\D){0,12}?'
FATHER_RE = re.compile(r'(아빠|아버지|아버님|부친|남편)' + _NOT_OTHER_PARENT + r'(\d{3}(?:\.\d)?)')
MOTHER_RE = re.compile(r'(엄마|어머니|어머님|모친|제\s*키)' + _NOT_OTHER_PARENT + r'(\d{3}(?:\.\d)?)')
BONE_DELAY_RE = re.compile(r'골\s*연령.{0,20}(지연|어림|낮|늦|delay)|bone\s*age.{0,20}delay', re.I)
BONE_NUM_RE = re.compile(r'(?:골\s*연령|bone\s*age)\s*:?\s*(\d{1,2}(?:\.\d)?)\s*(?:세|살|y|년)', re.I)
BONE_NORMAL_RE =re.compile(r'골\s*연령.{0,20}(정상|일치|역연령과\s*같|비슷)|bone\s*age.{0,20}(normal|appropriate)', re.I)
# 임계: 중간부모키 남 <165 / 여 <152 (성별 미상 158.5), 보고된 부모 키 아버지 <162 / 어머니 <150, 130 미만은 잘못 들은 값으로 무시
MPH_CUT = {'M': 165.0, 'F': 152.0, None: 158.5}
FATHER_CUT, MOTHER_CUT, HEIGHT_MIN, HEIGHT_MAX = 162.0, 150.0, 130.0, 210.0


def _patient_texts(enc) -> list[tuple[int, str]]:
    """(턴, 환자 말) 목록: 시작 정보(턴 0) + 문진 답(설명 단계 제외)."""
    out = [(0, nfc(getattr(enc, 'opening', '') or ''))]
    for e in getattr(enc, 'ledger', None) or []:
        if e.get('kind') != 'SAY' or e.get('refused') or str(e.get('phase') or '').startswith('explain'):
            continue
        out.append((e.get('turn'), nfc(e.get('reply') or '')))
    return out


def short_stature_signals(texts, exams, facts=None, sex=None, ledger=None, age=None) -> dict:
    """순수 함수: 늦은 성장 가족력·부모 저신장·골연령 신호. texts=[(턴, 환자 말)], exams=[{'id','turn','name','result'}]."""
    sig = {'late': False, 'late_turn': None, 'late_text': '', 'mph': None, 'mph_exam': None,
           'father': None, 'mother': None, 'parents_short': None, 'bone': None, 'bone_exam': None}
    srcs = list(texts) + [(f.get('turn'), f"{f.get('label') or ''} {f.get('detail') or ''}") for f in (facts or [])
                          if f.get('pol') != '-']
    for turn, t in srcs:
        for m in LATE_BLOOM_RE.finditer(t or ''):
            if LATE_NEG_RE.search(t[m.end():m.end() + 12]):
                continue
            sig.update({'late': True, 'late_turn': turn, 'late_text': t.strip()[:80]})
            break
        if sig['late']:
            break
    if not sig['late']:
        # '부모님 중 늦게 큰 분 있나요?' → '네, 아빠가 그랬어요' 같은 짧은 긍정
        for e in ledger or []:
            for j in e.get('items') or []:
                if j.get('id') in ('gr_late', 'gr_parent_late', 'fh_late') and j.get('answered') and j.get('pol') == '+':
                    sig.update({'late': True, 'late_turn': e.get('turn'), 'late_text': nfc(e.get('reply') or '')[:60]})
    for x in exams or []:
        r = nfc(x.get('result') or '')
        m = MPH_RE.search(r)
        if m and sig['mph'] is None:
            v = float(m.group(1))
            if HEIGHT_MIN <= v <= HEIGHT_MAX:
                sig['mph'], sig['mph_exam'] = v, x.get('id')
        mb = BONE_NUM_RE.search(r)
        if mb and age is not None:
            ba = float(mb.group(1))
            sig['bone'], sig['bone_exam'] = ('delayed' if age - ba >= 1 else 'normal'), x.get('id')
        elif BONE_DELAY_RE.search(r):
            sig['bone'], sig['bone_exam'] = 'delayed', x.get('id')
        elif BONE_NORMAL_RE.search(r):
            sig['bone'], sig['bone_exam'] = 'normal', x.get('id')
    for _turn, t in texts:
        for rx, k in ((FATHER_RE, 'father'), (MOTHER_RE, 'mother')):
            for m in rx.finditer(t or ''):
                v = float(m.group(2))
                if HEIGHT_MIN <= v <= HEIGHT_MAX and sig[k] is None:
                    sig[k] = v
    short = []
    if sig['mph'] is not None:
        short.append(sig['mph'] < MPH_CUT.get(sex, MPH_CUT[None]))
    if sig['father'] is not None:
        short.append(sig['father'] < FATHER_CUT)
    if sig['mother'] is not None:
        short.append(sig['mother'] < MOTHER_CUT)
    if short:
        # 중간부모키가 있으면 그것을 우선(부모 키 진술은 잘못 들릴 수 있음)
        sig['parents_short'] = short[0] if sig['mph'] is not None else any(short)
    return sig


def short_stature_decision(dx: str, sig: dict) -> str | None:
    """'CDGP' | 'FSS' | None(LLM 진단 유지). dx가 소아 저신장 군이 아닐 때는 None."""
    if not SS_GROUP_RE.search(dx or ''):
        return None
    late, short = sig.get('late'), sig.get('parents_short')
    if late and not short:
        return 'CDGP'
    if short and not late:
        return 'FSS'
    if late and short:   # 둘 다: 골연령이 있으면 그것으로, 없으면 LLM 선택 유지
        return {'delayed': 'CDGP', 'normal': 'FSS'}.get(sig.get('bone'))
    if short is False and sig.get('bone') == 'delayed':   # 늦은 성장 가족력은 없지만 부모 키 정상 + 골연령 지연
        return 'CDGP'
    return None


def apply_short_stature_rule(enc, out: dict) -> dict:
    dx = out.get('dx') or ''
    if not SS_GROUP_RE.search(dx):
        return out
    prof = getattr(enc, 'profile', None) or {}
    if prof.get('pediatric') is False and prof.get('age') is not None and prof.get('age') >= 19:
        return out
    facts = out.get('facts') or []
    exams = out.get('exams') or []
    age = prof.get('age') if isinstance(prof.get('age'), (int, float)) else None
    sig = short_stature_signals(_patient_texts(enc), exams, facts, prof.get('sex'), getattr(enc, 'ledger', None), age)
    out['short_stature'] = sig
    choice = short_stature_decision(dx, sig)
    cur = 'CDGP' if CDGP_RE.search(dx) else ('FSS' if FSS_RE.search(dx) else 'ISS')
    new = choice or cur
    if new != cur and new in ('CDGP', 'FSS'):
        log(f"dx short-stature rule: '{dx}' -> '{CDGP_DX if new == 'CDGP' else FSS_DX}' "
            f"(late={sig['late']} parents_short={sig['parents_short']} mph={sig['mph']} father={sig['father']} "
            f"mother={sig['mother']} bone={sig['bone']})")
        out['dx_rule'] = {'from': dx, 'to': new}
        out['dx'] = CDGP_DX if new == 'CDGP' else FSS_DX
        # 이전 진단을 지지하던 근거 줄은 뺀다
        old_re = FSS_RE if cur == 'FSS' else (CDGP_RE if cur == 'CDGP' else re.compile(r'특발성|idiopathic', re.I))
        drop_re = re.compile(old_re.pattern + (r'|유전적\s*요인|부모.{0,8}저신장' if cur == 'FSS' else ''), re.I)
        out['evidence'] = [e for e in out.get('evidence') or [] if not drop_re.search(e.get('text') or '')]
    primary = 'CDGP' if CDGP_RE.search(out['dx']) else ('FSS' if FSS_RE.search(out['dx']) else 'ISS')
    _ensure_ss_evidence(out, sig, primary)
    _ensure_ss_differential(out, sig, primary)
    return out


def _fact_refs(facts, turn) -> list[str]:
    return [f['id'] for f in facts if f.get('turn') == turn and f.get('id')][:1]


def _ensure_ss_evidence(out, sig, primary):
    facts = out.get('facts') or []
    ev = list(out.get('evidence') or [])
    joined = ' '.join(e.get('text') or '' for e in ev)
    add = []
    if primary == 'CDGP' and sig.get('late') and not re.search(r'늦|사춘기\s*지연|고등학교|중학교', joined):
        refs = _fact_refs(facts, sig['late_turn'])
        if refs:
            lt = sig['late_text'].rstrip('.')
            lt = lt if len(lt) <= 60 else lt[:59] + '…'
            add.append({'text': f"부모의 늦은 성장 가족력 호소('{lt}') → 체질성 성장지연 시사", 'refs': refs})
    if sig.get('mph') is not None and sig.get('mph_exam') and not re.search(r'중간\s*부모\s*키|부모\s*키', joined) \
            and bool(sig.get('parents_short')) == (primary == 'FSS'):
        if sig.get('parents_short'):
            t = f"진찰상 중간부모키 {sig['mph']:g}cm로 낮음 → 유전적 목표키가 작아 가족성 저신장 시사"
        else:
            t = f"진찰상 중간부모키 {sig['mph']:g}cm로 정상 범위 → 부모 저신장 아님, 가족성 저신장 가능성 낮음"
        add.append({'text': t, 'refs': [sig['mph_exam']]})
    bone_fits = {'delayed': 'CDGP', 'normal': 'FSS'}.get(sig.get('bone'))
    if bone_fits and bone_fits == primary and sig.get('bone_exam') and \
            not re.search(r'골\s*연령|bone\s*age', joined, re.I):
        add.append({'text': '진찰상 골연령 ' + ('지연 → 체질성 성장지연 시사' if sig['bone'] == 'delayed'
                                            else '역연령과 일치 → 가족성 저신장 시사'), 'refs': [sig['bone_exam']]})
    if add:
        out['evidence'] = add + ev


def _ensure_ss_differential(out, sig, primary):
    if primary not in ('CDGP', 'FSS'):
        return
    other, other_re = (FSS_DX, FSS_RE) if primary == 'CDGP' else (CDGP_DX, CDGP_RE)
    prim_re = CDGP_RE if primary == 'CDGP' else FSS_RE
    diffs = [d for d in out.get('differential') or [] if not prim_re.search(d.get('dx') or '')]
    if any(other_re.search(d.get('dx') or '') for d in diffs):
        out['differential'] = diffs[:5]
        return
    refs = [r for r in [sig.get('mph_exam')] + _fact_refs(out.get('facts') or [], sig.get('late_turn')) if r]
    if primary == 'CDGP':
        mph = f"중간부모키 {sig['mph']:g}cm 정상" if sig.get('mph') is not None else '부모 저신장 근거 없음'
        reason = (f"지지: 저신장·성장속도 정상 하한 / 반대: {mph}, 부모의 늦은 성장 가족력 / 판단: 가능성 낮음")
        test = '골연령 검사(가족성 저신장이면 골연령=역연령, 체질성이면 지연)'
    else:
        reason = ("지지: 저신장·성장속도 정상 하한 / 반대: 부모 키가 작고 늦은 성장 가족력 확인 안 됨 / 판단: 가능성 낮음"
                  if not sig.get('late') else '지지: 부모의 늦은 성장 가족력 / 반대: 부모 키가 작음 / 판단: 골연령으로 감별')
        test = '골연령 검사(체질성 성장지연이면 골연령 지연)'
    diffs.insert(0, {'dx': other, 'reason': reason, 'refs': refs, 'test': test})
    out['differential'] = diffs[:5]


def _turns(refs, ids) -> str:
    ts = []
    for r in refs:
        x = ids.get(r)
        if x is None:
            continue
        t = x.get('turn')
        if t == 0:
            if '시작 정보' not in ts:
                ts.append('시작 정보')
        elif t is not None and t not in ts:
            ts.append(t)
    nums = sorted(t for t in ts if isinstance(t, int))
    parts = (['시작 정보'] if '시작 정보' in ts else []) + ([f"턴 {', '.join(str(n) for n in nums)}"] if nums else [])
    return f" ({'; '.join(parts)})" if parts else ''


def render_assessment(enc, a: dict) -> dict:
    facts = a.get('facts') or []
    exams = a.get('exams') or []
    ids = {f['id']: f for f in facts}
    ids.update({x['id']: x for x in exams})
    dx = enc.dx or a.get('dx') or '진단 미정'
    lines = [f'#1. {dx}']
    ev = a.get('evidence') or []
    for item in ev:
        lines.append(f"- 근거 : {item['text']}{_turns(item['refs'], ids)}")
    if len(ev) < 2:  # 템플릿 근거 보충: 긍정 사실 상위 + 이상 진찰
        pos = [f for f in facts if f['pol'] == '+' and f['sec'] in ('hpi', 'ros', 'fh', 'women', 'psych')][:3]
        for f in pos:
            lines.append(f"- 근거 : {f['label']}{(' ' + f['detail']) if f['detail'] else ''} 호소{_turns([f['id']], ids)}")
        abn = [x for x in exams if re.search(r'\(\+|비대|항진|저하|이상|빈맥', x['result'])][:2]
        for x in abn:
            lines.append(f"- 근거 : 진찰상 {x['name']} {x['result'][:40]}{_turns([x['id']], ids)}")
    diff_lines = []
    for d in a.get('differential') or []:
        reason = d['reason'].rstrip('. ')
        s = f"r/o {d['dx']} : {reason}{_turns(d['refs'], ids)}"
        if d.get('test') and d['test'] not in reason:
            s += f". 감별 검사 : {d['test']}"
        diff_lines.append(s)
    if not diff_lines:
        diff_lines = [f'r/o {x} : 추가 검사로 감별 필요' for x in (enc.differentials or [])[1:4]]
    return {'evidence': '\n'.join(lines), 'differential': '\n'.join(diff_lines)}

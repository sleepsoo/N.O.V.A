"""v2 진단 + A칸: high 1회가 사실표(F#)·진찰(E#)을 인용하고, 턴 번호는 코드가 붙인다. (v2_spec §8.6, §9.3, §9.4)"""
from __future__ import annotations

import re

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
    user = (f'시작 정보: {enc.opening} / 활력징후: {enc.vitals.replace(chr(10), ", ")} / 파생 수치: {der or "없음"}\n'
            f'사실표(id | 턴 | 영역 | 항목 | +/- | 세부):\n{facts_table(facts) or "(없음)"}\n'
            f'진찰 소견(id | 턴 | 진찰 | 결과):\n{ex_txt}\n'
            f'문진 중 감별진단: {enc.differentials}\n'
            '[주진단] 증상명이 아닌 가장 구체적인 원인 질환명(표준 한국어명 + 영문). 검사 전 임상 진단이어도 가장 가능성 높은 '
            "원인 질환 하나를 고를 것. '원인 미상', '~ 의증 평가 필요', 증상명(저신장·불면·체중 감소)만 쓰는 것은 금지.\n"
            " '및'으로 두 진단을 잇지 말 것. 예: '그레이브스병에 의한 갑상샘항진증', '체질성 성장지연', '수면제(진정수면제) 사용장애'.\n"
            ' 약물 내성·금단·조절 실패·여러 곳 처방이 있으면 해당 물질 사용장애를 우선 고려. 소아 저신장: 가족성 저신장=부모 키 자체가 작음, '
            '체질성 성장지연=부모 키는 정상이나 부모의 늦은 사춘기·늦은 성장, 성장속도 정상 하한.\n'
            '[방법] 후보 3~4개마다 지지(for)·반대(against) 사실 id를 적고 비교해 고르세요.\n'
            '[근거] 4~6개: ①핵심 병력(수치 포함) ②진찰 소견 ③위험인자·가족력 ④다른 질환을 배제하는 음성 소견. 각 항목은 refs(F#/E#) 필수.\n'
            " 환자가 말한 것은 '호소', 진찰 결과는 '진찰상'. 검사하지 않은 결과(호르몬 수치·영상)를 정상/이상이라 쓰지 말 것. "
            '위 진찰 소견 목록에 없는 진찰(예: 하지 부종·폐 청진을 안 했으면 심부전 징후)은 있다/없다고 쓰지 말 것. '
            "환자가 '아니다'라고 한 증상을 다른 이름으로 바꿔 양성으로 쓰지 말 것(예: 묽은 변 ≠ 설사). "
            '확인된 영향과 모순되는 해석 금지. 턴 번호는 쓰지 말 것(코드가 붙임).\n'
            '[감별] 3~4개, 이 환자에서 실제로 고려할 만한 것만(드물거나 무관한 질환 금지). reason에는 사실표와 극성이 일치하는 소견을 '
            '인용(refs). test는 감별 검사 1~2개.\n'
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
                'differential': diffs[:4], 'confidence': res.get('confidence'), 'candidates': res.get('candidates')})
    if (res.get('confidence') or 1) and isinstance(res.get('confidence'), (int, float)) and res['confidence'] < 0.5:
        log(f"dx low confidence {res['confidence']}")
    return out


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

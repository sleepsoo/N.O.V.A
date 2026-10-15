"""S칸: LLM은 문답 판정(키·+/-·짧은 detail)만, 서술은 프로그램 템플릿.  cc/hpi만 LLM 서술 + 템플릿 폴백."""
from __future__ import annotations

import re

from . import banks
from .llm import ask_json
from .util import as_text, log, nfc

DOCTOR_ROLE = '당신은 한국 대학병원 외래의 숙련된 전문의입니다.'

PMH_KEYS = ['DM', 'HTN', 'stroke', 'Tbc', 'hepatitis', 'heart_disease', 'dyslipidemia', 'op_hx', 'allergy', 'meds',
            'other_illness']
FH_KEYS = ['DM', 'HTN', 'stroke', 'cancer', 'similar', 'father_height', 'mother_height', 'late_puberty', 'short_stature']
SH_KEYS = ['smoking', 'alcohol', 'job', 'caffeine', 'home', 'exercise']
ROS_FIXED = ['General weakness', 'Fatigue', 'Headache', 'Dizziness', 'Chest pain', 'Palpitation', 'Fever', 'Chill',
             'Cough', 'Sputum', 'Rhinorrhea', 'Abdominal pain', 'Melena', 'Hematochezia', 'Hematemesis', 'Anorexia',
             'Nausea', 'Vomiting', 'Diarrhea', 'Constipation']
ROS_EXTRA = {'Dyspnea': '호흡곤란', 'Edema': '부종', 'Bowel change': '배변 변화', 'Urinary change': '배뇨 변화',
             'Depressed mood': '우울감', 'Anxiety': '불안', 'Sleep disturbance': '수면 장애', 'Weight change': '체중 변화',
             'Menstrual change': '월경 변화', 'LMP': '마지막 월경', 'Sleep': '수면', 'Mood': '기분', 'Appetite': '식욕', 'Puberty signs': '사춘기 징후', 'Heat intolerance': '더위 못 참음',
             'Sweating': '발한', 'Tremor': '손떨림', 'Polydipsia': '갈증·다음', 'Night sweats': '야간 발한',
             'Pregnancy': '임신 가능성'}
PEDS_KEYS = ['출생력', '신생아기', '발달', '예방접종', '영양', '수면·활동', '성장 기록']
FH_LABEL = {'cancer': '암', 'similar': '유사 질환', 'father_height': '부 키', 'mother_height': '모 키',
            'late_puberty': '사춘기 지연', 'short_stature': '저신장'}
SH_LABEL = {'job': '직업', 'caffeine': '카페인', 'home': '가정·사회', 'exercise': '운동'}

SKIP_PHASES = ('empathy',)  # v6: 설명 단계 발언은 수긍·인사만 거르고 포함(facts.explain_row)


def key_guide(peds: bool) -> str:
    g = ['pmh.' + k for k in PMH_KEYS] + ['fh.' + k for k in FH_KEYS] + ['sh.' + k for k in SH_KEYS]
    g += ['ros.' + k for k in ROS_FIXED + list(ROS_EXTRA)]
    if peds:
        g += ['peds.' + k for k in PEDS_KEYS]
    g += ['hpi.onset', 'hpi.course', 'hpi.character', 'hpi.severity', 'hpi.aggravating', 'hpi.relieving',
          'hpi.prior_visit', 'hpi.impact', 'ice.concern', 'ice.expectation']
    return ', '.join(g)


def qa_items(enc) -> list[dict]:
    items = []
    for e in enc.ledger:
        if e['kind'] != 'SAY' or e.get('refused') or e.get('phase') in SKIP_PHASES:
            continue
        if e.get('phase') in ('explain', 'explain-answer'):
            from .facts import explain_row
            r = explain_row(e)
            if r:
                items.append({'turn': r['turn'], 'q': r['q'], 'a': r['a'], 'qid': r['slot'],
                              'keys': ['ice.expectation'] if r['slot'] == 'ice-explain' else [], 'label': r['label']})
            continue
        items.append({'turn': e['turn'], 'q': e['text'], 'a': e['reply'], 'qid': e.get('qid', ''),
                      'keys': banks.QKEYS.get(e.get('qid', ''), []), 'label': e.get('label', '')})
    return items


def is_negative(answer: str) -> bool:
    a = nfc(answer).strip()
    if re.match(r'^(아니|아뇨|없|전혀|안\s|별로\s*없)', a):
        return True
    if re.search(r'(있어요|있습니다|있었|있긴|조금|가끔|자주|많이)', a):
        return False
    return bool(re.search(r'(없어요|없습니다|없었어요|안 피워요|안 마셔요|안 해요|않아요)$', a.rstrip('.! ')))


def is_affirmative(answer: str) -> bool:
    a = nfc(answer).strip()
    return bool(re.match(r'^(네|예|응|맞아요|있어요)', a)) and not is_negative(a)


DETAIL_KEYS = {'pmh.meds', 'pmh.other_illness', 'fh.similar', 'fh.father_height', 'fh.mother_height', 'sh.job',
               'sh.alcohol', 'sh.home', 'sh.caffeine', 'ros.LMP', 'ice.concern', 'ice.expectation', 'ros.Sleep',
               'ros.Mood', 'ros.Appetite'}
# 답의 긍정이 '증상 있음'을 뜻하지 않는(서술형) 키: (+)/(-) 대신 답 요약을 쓴다
NEUTRAL_KEYS = {'ros.Sleep', 'ros.Mood', 'ros.Appetite', 'ros.LMP', 'sh.job', 'sh.home', 'sh.caffeine',
                'fh.father_height', 'fh.mother_height'}


def _short_answer(a: str) -> str:
    """'네, 자연분만이었어요' → '자연분만', '네' → ''. 종결어미를 떼어 임상 약어체에 가깝게."""
    t = re.sub(r'^(네|예|아니요|아뇨|응)[,.\s]*', '', nfc(a).strip())
    t = re.sub(r'\s*(이었어요|였어요|이에요|예요|했어요)[.!]?$', '', t).strip()
    return t.rstrip('.')[:40]


def fallback_findings(items: list[dict]) -> list[dict]:
    out = []
    for it in items:
        label = it.get('label') or ''
        for k in it['keys']:
            if k.startswith(('hpi.', 'ice.')) or k in NEUTRAL_KEYS:
                out.append({'turn': it['turn'], 'key': k, 'pol': '?', 'detail': it['a'][:40], 'label': label})
            elif is_negative(it['a']):
                out.append({'turn': it['turn'], 'key': k, 'pol': '-', 'detail': '', 'label': label})
            elif k in DETAIL_KEYS or k.startswith('peds.'):
                out.append({'turn': it['turn'], 'key': k, 'pol': '+', 'detail': _short_answer(it['a']), 'label': label})
            elif is_affirmative(it['a']):
                out.append({'turn': it['turn'], 'key': k, 'pol': '+', 'detail': '', 'label': label})
    return out


def judge(enc, items: list[dict]) -> list[dict]:
    peds = bool(enc.profile.get('pediatric'))
    listing = '\n'.join(f"턴 {it['turn']} | 키 힌트: {it['keys'] or '-'} | 의사: {it['q']} | 환자: {it['a']}" for it in items)
    user = (f'시작 정보: {enc.opening}\n\n아래는 진료 중 문답입니다. 각 턴의 환자 답을 기록용으로 판정하세요.\n{listing}\n\n'
            f'사용 가능한 키: {key_guide(peds)}\n'
            '목록에 없는 증상·병력은 "ros.other:증상명", "pmh.other:병명", "fh.other:관계 병명", "sh.other:항목" 형태 키를 씁니다.\n'
            '규칙: pol은 "+"(있다고 답함), "-"(없다고 답함), "?"(불분명/서술형). 한 턴에 여러 판정이 가능(예: "고혈압만 있어요" → pmh.DM "-", '
            'pmh.HTN "+"). 환자가 묻지 않은 증상을 말했으면 그것도 판정. detail은 환자 답의 핵심만 15자 이내(숫자는 답 그대로), '
            '없으면 "". 환자가 실제로 말한 것만 근거로 하고 진단을 추론하지 마세요.\n'
            '출력: {"findings": [{"turn": 턴번호, "key": "키", "pol": "+|-|?", "detail": "..."}]}')
    def _ok(v):
        if isinstance(v, list):
            return len(v) > 0
        return isinstance(v, dict) and isinstance(v.get('findings'), list) and len(v['findings']) > 0

    res = ask_json(enc.client, enc.budget, DOCTOR_ROLE + ' 문진 결과를 의무기록 항목으로 정리합니다. JSON 하나만 출력하세요.', user,
                   effort=enc.cfg['JUDGE_EFFORT'], max_tokens=enc.cfg['S_MAX_TOKENS'], tag='S-judge', want=None, tries=2,
                   validate=_ok, reserve=3, max_wait=300)
    if isinstance(res, list):  # 모델이 배열만 낸 경우
        res = {'findings': res}
    findings = []
    turns = {it['turn'] for it in items}
    labels = {it['turn']: it.get('label', '') for it in items}
    for f in (res or {}).get('findings') or []:
        if not isinstance(f, dict):
            continue
        key = nfc(str(f.get('key') or '')).strip()
        pol = str(f.get('pol') or '?').strip()
        pol = pol if pol in ('+', '-', '?') else '?'
        try:
            turn = int(f.get('turn'))
        except (TypeError, ValueError):
            continue
        if not key or '.' not in key or turn not in turns:
            continue
        findings.append({'turn': turn, 'key': key, 'pol': pol, 'detail': nfc(str(f.get('detail') or '')).strip()[:40],
                         'label': labels.get(turn, '')})
    # LLM이 놓친 은행 문항(키 힌트가 있는데 판정이 없는 턴)은 규칙으로 채운다
    judged = {(f['turn'], f['key']) for f in findings}
    for fb in fallback_findings(items):
        if (fb['turn'], fb['key']) not in judged:
            findings.append(fb)
    log(f'S-judge: {len(findings)} findings ({"llm" if res else "rule"})')
    return findings


def _collect(findings):
    """키별 최신 판정."""
    out = {}
    for f in sorted(findings, key=lambda x: x['turn']):
        out[f['key']] = f
    return out


def _m(d, key):
    f = d.get(key)
    return f['pol'] if f and f['pol'] in ('+', '-') else ' '  # 묻지 않은 항목은 '( )'


def _det(d, key):
    f = d.get(key)
    return f['detail'] if f and f.get('detail') else ''


def _with_detail(name, f):
    pol = f['pol'] if f['pol'] in ('+', '-') else ''
    det = f.get('detail') or ''
    if pol and det and pol == '+':
        return f'{name}({pol}, {det})'
    if pol:
        return f'{name}({pol})'
    return f'{name} : {det}' if det else ''


def render_history(enc, findings: list[dict]) -> dict:
    peds = bool(enc.profile.get('pediatric'))
    d = _collect(findings)
    # pmh
    meds = d.get('pmh.meds')
    if meds and meds['pol'] == '-':
        med_line = 'Medicine history : 복용 약 없음 (-)'
    elif meds:
        med_line = f"Medicine history : {meds.get('detail') or '복용 중(+)'}"
    else:
        med_line = 'Medicine history : '
    allergy = f"Allergy ({_m(d, 'pmh.allergy')})" + (f" {_det(d, 'pmh.allergy')}" if _m(d, 'pmh.allergy') == '+' else '')
    pmh = [f"DM / HTN ({_m(d, 'pmh.DM')}/{_m(d, 'pmh.HTN')})", f"previous stroke ({_m(d, 'pmh.stroke')})",
           f"Tbc / hepatitis ({_m(d, 'pmh.Tbc')}/{_m(d, 'pmh.hepatitis')})",
           f"heart disease ({_m(d, 'pmh.heart_disease')})  dyslipidemia ({_m(d, 'pmh.dyslipidemia')})",
           f"Op. Hx ({_m(d, 'pmh.op_hx')})" + (f" {_det(d, 'pmh.op_hx')}" if _m(d, 'pmh.op_hx') == '+' else ''),
           med_line, allergy]
    others = []
    oi = d.get('pmh.other_illness')
    if oi:
        others.append('기타 지병(-)' if oi['pol'] == '-' else (oi.get('detail') or '기타 지병(+)'))
    others += [_with_detail(k.split(':', 1)[1], f) for k, f in d.items() if k.startswith('pmh.other:')]
    others = [o for o in others if o]
    if others:
        pmh.append('Others : ' + ', '.join(others))
    if peds:
        pmh.append('* 소아')
        for k in PEDS_KEYS:
            # 같은 키 여러 턴(출생력 3문항 등)은 모두 모은다. 예/아니요 답은 문항 라벨에 (+)/(-)를 붙인다.
            vals = []
            seen_turns = set()
            for f in sorted(findings, key=lambda x: x['turn']):
                if f['key'] != 'peds.' + k or f['turn'] in seen_turns:
                    continue
                seen_turns.add(f['turn'])
                lab = re.sub(r'^.*-', '', f.get('label') or '')
                pol = f'({f["pol"]})' if f['pol'] in '+-' else ''
                if f.get('detail'):
                    vals.append(f"{lab} {f['detail']}".strip() if lab and lab not in f['detail'] else f['detail'])
                elif lab or pol:
                    vals.append(f'{lab}{pol}')
            pmh.append(f"- {k} : {', '.join(v for v in vals if v)}")
    # fh
    fh = [f"DM / HTN ({_m(d, 'fh.DM')}/{_m(d, 'fh.HTN')})", f"Stroke ({_m(d, 'fh.stroke')})"]
    fo = []
    for k in ('similar', 'cancer', 'father_height', 'mother_height', 'late_puberty', 'short_stature'):
        f = d.get('fh.' + k)
        if f:
            fo.append(_with_detail(FH_LABEL[k], f))
    fo += [_with_detail(k.split(':', 1)[1], f) for k, f in d.items() if k.startswith('fh.other:')]
    fo = [x for x in fo if x]
    if fo:
        fh.append('Others : ' + ', '.join(fo))
    # sh
    if peds:
        sh = ['Smoking / Alcohol : 해당 없음(소아)']
    else:
        sh = [f"Smoking ({_m(d, 'sh.smoking')})" + (f" {_det(d, 'sh.smoking')}" if _m(d, 'sh.smoking') == '+' else ''),
              f"Alcohol ({_m(d, 'sh.alcohol')})" + (f" {_det(d, 'sh.alcohol')}" if _m(d, 'sh.alcohol') == '+' else '')]
    so = []
    for k in ('job', 'caffeine', 'exercise', 'home'):
        f = d.get('sh.' + k)
        if f and (f.get('detail') or f['pol'] in '+-'):
            so.append(f"{SH_LABEL[k]} : {f.get('detail') or ('(-)' if f['pol'] == '-' else '(+)')}")
    so += [_with_detail(k.split(':', 1)[1], f) for k, f in d.items() if k.startswith('sh.other:')]
    so = [x for x in so if x]
    if so:
        sh.append('Others : ' + ', '.join(so))
    # ros
    r = lambda k: _m(d, 'ros.' + k)  # noqa: E731
    ros = [f"General weakness ({r('General weakness')})  Fatigue ({r('Fatigue')})",
           f"Headache ({r('Headache')})  Dizziness ({r('Dizziness')})",
           f"Chest pain ({r('Chest pain')})  Palpitation ({r('Palpitation')})",
           f"Fever/Chill/Cough/Sputum/Rhinorrhea ({r('Fever')}/{r('Chill')}/{r('Cough')}/{r('Sputum')}/{r('Rhinorrhea')})",
           f"Abdominal pain ({r('Abdominal pain')})  Melena ({r('Melena')})  Hematochezia ({r('Hematochezia')})  "
           f"Hematemesis ({r('Hematemesis')})",
           f"Anorexia/Nausea/Vomiting/Diarrhea/Constipation ({r('Anorexia')}/{r('Nausea')}/{r('Vomiting')}/"
           f"{r('Diarrhea')}/{r('Constipation')})"]
    ro = []
    for k, f in d.items():
        if not k.startswith('ros.'):
            continue
        name = k[4:]
        if name in ROS_FIXED:
            continue
        if name.startswith('other:'):
            name = name[6:]
        else:
            name = ROS_EXTRA.get(name, name)
        x = _with_detail(name, f)
        if x:
            ro.append(x)
    if ro:
        ros.append('Others : ' + ', '.join(ro))
    return {'pmh': '\n'.join(pmh), 'fh': '\n'.join(fh), 'sh': '\n'.join(sh), 'ros': '\n'.join(ros)}


def hpi_template(enc, findings: list[dict]) -> dict:
    prof = enc.profile
    sex = {'F': '여자', 'M': '남자'}.get(prof.get('sex'), '')
    age = prof.get('age')
    head = f"{age}세 {sex}".strip() if age is not None else sex
    pos = [_name(f['key']) for f in findings if f['pol'] == '+' and f['key'].startswith('ros.')]
    neg = [_name(f['key']) for f in findings if f['pol'] == '-' and f['key'].startswith('ros.')]
    hpi_bits = [f"{_name(f['key'])} : {f['detail']}" for f in findings if f['key'].startswith('hpi.') and f.get('detail')]
    ice = [f"{f['detail']}" for f in findings if f['key'].startswith('ice.') and f.get('detail')]
    lines = [f"{head}. {enc.opening}".strip('. ')]
    if hpi_bits:
        lines.append('. '.join(hpi_bits))
    if pos or neg:
        lines.append('문진상 ' + (', '.join(dict.fromkeys(pos)) + '(+)' if pos else '') + (' / ' if pos and neg else '')
                     + (', '.join(dict.fromkeys(neg)) + '(-)' if neg else ''))
    if ice:
        lines.append('걱정·기대 : ' + '; '.join(ice))
    lines.append('위 증상으로 내원함.')
    return {'cc': f"C.C : {prof.get('cc') or ''}\nOnset : {_onset(findings)}", 'hpi': '\n'.join(lines)}


def _name(key: str) -> str:
    n = key.split('.', 1)[1] if '.' in key else key
    if n.startswith('other:'):
        return n[6:]
    return ROS_EXTRA.get(n, n)


def _onset(findings):
    for f in findings:
        if f['key'] == 'hpi.onset' and f.get('detail'):
            return f['detail']
    return ''


def write_cc_hpi(enc, findings: list[dict]) -> dict:
    items = qa_items(enc)
    listing = '\n'.join(f"턴 {it['turn']} | 의사: {it['q']} | 환자: {it['a']}" for it in items)
    sys_prompt = DOCTOR_ROLE + ' 초진 의무기록의 주호소와 현병력을 씁니다. JSON 하나만 출력하세요.'
    user = (f'시작 정보(확인된 사실): {enc.opening}\n\n문답:\n{listing}\n\n'
            '간결한 의무기록체로 쓰세요. 규칙: 시작 정보와 문답에 있는 사실만, 숫자·약 이름·기간은 그대로, 추정·해석·진찰 소견 금지, '
            '확인된 음성 증상은 (-)로. hpi는 나이·성별로 시작해 시작 시점→경과→양상·동반 증상→이전 진료→걱정·기대 순서, 3~6문장, '
            '마지막은 "~하여 내원함".\n'
            '출력: {"cc_text": "주호소 짧은 명사구", "onset": "시작 시점(예: 3개월 전)", "pain": "통증이면 NRS·부위·양상, 아니면 해당 없음", '
            '"hpi": "현병력"}')
    res = ask_json(enc.client, enc.budget, sys_prompt, user, effort=enc.cfg['S_EFFORT'], max_tokens=enc.cfg['S_MAX_TOKENS'],
                   tag='S-hpi', want=dict, tries=2, validate=lambda v: len(as_text(v.get('hpi')).strip()) > 20, reserve=3)
    if not res:
        return hpi_template(enc, findings)
    cc = nfc(as_text(res.get('cc_text'))).strip() or enc.profile.get('cc', '')
    onset = nfc(as_text(res.get('onset'))).strip()
    pain = nfc(as_text(res.get('pain'))).strip() or '해당 없음'
    hpi = nfc(as_text(res.get('hpi'))).strip()
    hpi = re.sub(r'(?<=[.다음함])\s+(?=\S)', '\n', hpi) if '\n' not in hpi else hpi
    return {'cc': f'C.C : {cc}\nOnset : {onset}\n통증평가 : {pain}', 'hpi': hpi}


def write_subjective(enc) -> dict:
    items = qa_items(enc)
    findings = judge(enc, items) if items else []
    enc.findings = findings
    out = write_cc_hpi(enc, findings)
    out.update(render_history(enc, findings))
    return out

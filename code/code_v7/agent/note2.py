"""v2 S칸: 서술(cc·hpi·Others·소아 블록)은 luna medium, 고정 칸 (+)/(-)는 검증된 사실표로 코드가 렌더. (v2_spec §8.9, §9.2)"""
from __future__ import annotations

import re

from .facts import qa_rows, table as facts_table
from .llm import ask_json
from .util import as_text, extract_numbers, log, nfc

ROLE = '당신은 한국 대학병원 외래의 숙련된 전문의입니다. 초진 의무기록의 S(주관적 정보) 서술 칸을 씁니다. JSON 하나만 출력하세요.'


def write_s_narrative(enc) -> dict:
    facts = getattr(enc, 'facts', None) or []
    rows = qa_rows(enc, include_late=True)  # v7 C5-a: 설명 중 환자 질문도 원문 참고에 포함
    listing = '\n'.join(f"턴 {r['turn']} | 의사: {r['q']} | 환자: {r['a']}" for r in rows)
    peds = enc.profile.get('pediatric')
    user = (f"시작 정보: {enc.opening} / 정보 제공자: {enc.profile.get('informant')}\n"
            f'사실표(id | 턴 | 영역 | 항목 | +/- | 세부):\n{facts_table(facts)}\n'
            f'문답 원문(참고):\n{listing}\n'
            "규칙: 묻지 않은 것은 쓰지 않음. 숫자·약 이름·기간은 그대로(숫자는 아라비아 숫자로). 환자 진술은 진술로('~ 느낌이 있다고 함', "
            "'~ 호소'), 진찰 소견처럼 쓰지 않음('관찰됨/확인됨/소견' 금지). HPI에 진단명·해석 금지. 확인한 음성 증상은 (-)로.\n"
            "환자 표현을 의학 용어로 바꿔 넓히지 말 것(묽은 변≠설사, '고교 때 갑자기 컸다'≠'사춘기 지연', 특정 질환만 물었으면 "
            "'기타 지병 없음'으로 넓히지 말고 물은 질환만 (-)). 질문이 두 항목을 묶었는데 환자가 한 항목만 답했으면 답한 항목만 기록.\n"
            "- 음성 소견은 물은 범위 그대로(예: '물 섭취 증가(-)'≠'갈증(-)', '심한 두통(-)'≠'두통(-)', '최근 몇 달 성관계 없음'). "
            "'(?)' 표기 금지 — 수치·서술은 '항목 : 세부'.\n"
            "- 같은 사실을 여러 칸에 반복하지 말 것(과거력·가족력 Others 중복 금지).\n"
            "- cc_text: 주호소 명사구(요청 있으면 괄호, 예: '불면 (수면제 처방 원함)'). onset: 시작 시점(숫자 표기, 예: 7년 전). "
            "pain: 통증이면 'NRS n점, 부위, 양상', 아니면 '해당 없음'.\n"
            + ("- hpi: '보호자(모) 동반, 문진은 모가 대신 답함.'으로 시작 → 나이·성별 → " if peds else '- hpi: 나이·성별 → ')
            + "시작 → 경과(수치) → 양상·동반 증상(+) → 관련 음성(-) → 이전 진료·복용 → 일상 영향 → 걱정·기대. 4~8줄(줄바꿈). "
            "마지막은 '~하여 내원함.'\n"
            "- meds: 복용 약(이름·용량·복용법 그대로), 없다고 답했으면 '복용 약·보조제 (-)', 묻지 않았으면 ''.\n"
            "- pmh_others / fh_others / sh_others / ros_others: '항목 (+/-) 세부' 쉼표 나열, 한국어 항목명. 고정 칸(당뇨·고혈압·결핵·"
            "간염·심장병·수술·알레르기·흡연·음주·발열·기침 등 ROS 기본 20항목)은 제외하고 그 밖의 확인된 사실만.\n"
            + ("- peds: ['- 출생력 : ...', '- 신생아기 : ...', '- 발달 : ...', '- 예방접종 : ...', '- 영양 : ...', "
               "'- 수면·활동 : ...', '- 성장 기록 : ...'] (확인한 것만, 임상 약어체, '네,'·'~요' 같은 구어 금지)\n" if peds else '')
            + '출력: {"cc_text","onset","pain","hpi","meds","pmh_others","fh_others","sh_others","ros_others"'
            + (',"peds"' if peds else '') + '}')
    res = ask_json(enc.client, enc.budget, ROLE, user, effort=enc.cfg['EFFORT_S'], max_tokens=8000, tag='S-narr',
                   want=dict, tries=2, reserve=1, max_wait=240,
                   validate=lambda v: len(as_text(v.get('hpi')).strip()) > 20)
    return res if isinstance(res, dict) else {}


def _verify_numbers(enc, text: str) -> str:
    source = enc.opening + '\n' + enc.vitals + '\n' + '\n'.join(
        f"{e['text']} {e.get('reply') or ''}" for e in enc.ledger if not e.get('refused'))
    allowed = extract_numbers(source) | {'0', '1', '2', '3'} | {str(v) for v in (getattr(enc, 'derived', {}) or {}).values()}
    for v in list((getattr(enc, 'derived', {}) or {}).values()):
        try:
            allowed.add(str(int(v)) if float(v) == int(v) else str(v))
        except (TypeError, ValueError):
            pass

    def bad(t):
        t = re.sub(r'턴\s*\d+', '', t)
        out = []
        for m in re.finditer(r'(?<![A-Za-z])\d+(?:\.\d+)?', t):
            n = m.group(0)
            try:
                f = float(n)
                n = str(int(f)) if f == int(f) else str(f)
            except ValueError:
                pass
            if n not in allowed:
                out.append(n)
        return out
    lines = []
    for line in (text or '').split('\n'):
        if bad(line):
            parts = re.split(r'(?<=[.;])\s+|,\s+', line)
            line = ', '.join(p for p in parts if not bad(p)).strip()
        if line.strip():
            lines.append(line)
    return '\n'.join(lines)


def _latest(facts, key):
    best = None
    for f in facts:
        if f['key'] == key and f['pol'] in '+-':
            if best is None or f['turn'] >= best['turn']:
                best = f
    return best


def _m(facts, key):
    f = _latest(facts, key)
    return f['pol'] if f else ' '


def _det(facts, key):
    f = _latest(facts, key)
    return f'{f["detail"]}' if f and f['pol'] == '+' and f.get('detail') else ''


# v7 C5-b: key가 other인 사실 중 라벨이 고정 칸 항목이면 고정 키로 승격(렌더 전용 사본, enc.facts는 그대로)
PROMOTE = [('ros.Chest pain', r'^(흉통|가슴\s*(통증|아픔))'), ('ros.Palpitation', r'^(두근|심계)'),
           ('ros.Headache', r'^두통'), ('ros.Dizziness', r'^어지럼'), ('ros.Fever', r'^(발열|열)$'),
           ('ros.Diarrhea', r'^설사'), ('ros.Constipation', r'^변비'), ('ros.Nausea', r'^(구역|메스꺼움)'),
           ('ros.Vomiting', r'^구토'), ('ros.Abdominal pain', r'^복통'), ('ros.Melena', r'^(흑변|검은\s*변)'),
           ('ros.Hematochezia', r'^혈변'), ('ros.Fatigue', r'^(피로|피곤)'), ('ros.Cough', r'^기침'),
           ('ros.Sputum', r'^가래'), ('pmh.heart_disease', r'^심장(병|\s*질환)'), ('pmh.op_hx', r'^수술'),
           ('pmh.allergy', r'^(약\s*)?알레르기')]
QUALIFIER_RE = re.compile(r'(심한|자주|최근|증가|감소|악화|야간|운동\s*시|계단|안정\s*시)')


def _promote(enc, facts: list) -> list:
    from . import bank2
    from .facts import _source
    rows = None
    out = []
    for f in facts:
        lab = nfc(str(f.get('label') or '')).strip()
        key = next((k for k, p in PROMOTE if re.search(p, lab)), None) \
            if f.get('key') == 'other' and f.get('pol') in ('+', '-') else None
        if not key or key not in bank2.FIXED_KEYS or (f['pol'] == '-' and QUALIFIER_RE.search(lab)):
            out.append(f)
            continue
        if rows is None:
            rows = qa_rows(enc)
        try:
            src = _source(enc, rows, int(f.get('turn')))
        except (TypeError, ValueError):
            src = ''
        if not re.search(bank2.FIXED_KEYS[key], src or ''):  # 그 턴 문답에 어휘 단서가 있어야(validate와 같은 검사)
            out.append(f)
            continue
        out.append(dict(f, key=key, sec=key.split('.')[0]))
        # ROS 고정 칸은 (+)만 찍히므로 세부·한정어가 있는 양성 사실은 Others에도 남긴다(내용 보존)
        if key.startswith('ros.') and f['pol'] == '+' and (f.get('detail') or QUALIFIER_RE.search(lab)):
            out.append(f)
    return out


# v7 C5-c: Others 항목 정리('(?)' 표기, 중복, Medicine history와 같은 항목)
MED_ITEM_RE = re.compile(r'^(복용\s*(중인\s*)?약|약\s*복용|복용약|상용약|영양제|보조제|건강\s*보조|한약)')
MED_NEG_RE = re.compile(r'\(\s*-|없|안\s*먹|복용\s*안')


def _split_items(s: str) -> list[str]:
    items, depth, cur = [], 0, ''
    for ch in s:
        if ch in '([':
            depth += 1
        elif ch in ')]':
            depth = max(0, depth - 1)
        if ch == ',' and depth == 0:
            items.append(cur)
            cur = ''
            continue
        cur += ch
    items.append(cur)
    return [i.strip() for i in items if i.strip()]


def _onorm(s: str) -> str:
    return re.sub(r'[^0-9A-Za-z가-힣]', '', nfc(s))


def _pols(s: str) -> set:
    return set(re.findall(r'\(\s*([+-])', s))


def _bi(s: str) -> set:
    return {s[i:i + 2] for i in range(len(s) - 1)} or {s}


def _dup_item(a: str, b: str) -> bool:
    from .util import similarity
    pa, pb = _pols(a), _pols(b)
    if pa and pb and pa != pb:
        return False
    na, nb = _onorm(a), _onorm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    short, long_ = (na, nb) if len(na) <= len(nb) else (nb, na)
    if len(short) >= 4 and (short in long_ or len(_bi(short) & _bi(long_)) / len(_bi(short)) >= 0.85):
        return True
    return similarity(a, b) >= 0.7


def _fix_item(item: str) -> str:
    t = re.sub(r'\s*\(\s*\?\s*,\s*([^()]*)\)', r' : \1', item)
    t = re.sub(r'\s*\(\s*\?\s*\)\s*', ' : ', t)
    t = re.sub(r'\s*:\s*(:\s*)+', ' : ', t)
    return re.sub(r'^\s*:\s*|\s*:\s*$', '', t).strip()


def _clean_others(text: str) -> str:
    """'Others : ' 줄의 항목 정리. '(?)'→' : ', 같은/포함 항목은 긴 쪽만, Medicine history와 같은 복용약 항목 제거."""
    lines = (text or '').split('\n')
    meds = next((re.sub(r'^\s*Medicine history\s*:\s*', '', l) for l in lines if l.strip().startswith('Medicine history')), '')
    out = []
    for line in lines:
        m = re.match(r'^(\s*Others\s*:\s*)(.*)$', line)
        if not m:
            out.append(line)
            continue
        kept: list[str] = []
        for it in _split_items(m.group(2)):
            it = _fix_item(it)
            if not it:
                continue
            if meds.strip() and MED_ITEM_RE.search(it):
                det = re.search(r'\(\s*[+-]?\s*,?\s*([^()]*)\)', it)
                det = _onorm(det.group(1)) if det else ''
                if ('-' in _pols(it) and MED_NEG_RE.search(meds)) or (det and det in _onorm(meds)):
                    log(f'others: med dup removed: {it}')
                    continue
            hit = next((i for i, k in enumerate(kept) if _dup_item(k, it)), None)
            if hit is None:
                kept.append(it)
            elif len(_onorm(it)) > len(_onorm(kept[hit])):
                kept[hit] = it
        if kept:
            out.append(m.group(1) + ', '.join(kept))
    return '\n'.join(out)


def render_fixed(enc, s: dict) -> dict:
    facts = _promote(enc, getattr(enc, 'facts', None) or [])
    peds = enc.profile.get('pediatric')
    m = lambda k: _m(facts, k)  # noqa: E731
    pmh = [f"DM / HTN ({m('pmh.DM')}/{m('pmh.HTN')})", f"previous stroke ({m('pmh.stroke')})",
           f"Tbc / hepatitis ({m('pmh.Tbc')}/{m('pmh.hepatitis')})",
           f"heart disease ({m('pmh.heart_disease')})  dyslipidemia ({m('pmh.dyslipidemia')})",
           f"Op. Hx ({m('pmh.op_hx')}) {_det(facts, 'pmh.op_hx')}".rstrip(),
           f"Medicine history : {nfc(as_text(s.get('meds'))).strip()}".rstrip(),
           f"Allergy ({m('pmh.allergy')}) {_det(facts, 'pmh.allergy')}".rstrip()]
    po = nfc(as_text(s.get('pmh_others'))).strip()
    if po:
        pmh.append(f'Others : {po}')
    if peds:
        pmh.append('* 소아')
        pl = s.get('peds') or []
        if isinstance(pl, str):
            pl = pl.split('\n')
        for line in pl:
            line = nfc(str(line)).strip()
            if not line:
                continue
            line = re.sub(r'(^|:\s*)(네|예)[,.\s]+', r'\1', line)
            line = re.sub(r'(이었어요|였어요|이에요|예요|했어요|어요|아요)\.?$', '', line).rstrip()
            pmh.append(line if line.startswith('-') else f'- {line}')
    fh = [f"DM / HTN ({m('fh.DM')}/{m('fh.HTN')})", f"Stroke ({m('fh.stroke')})"]
    fo = nfc(as_text(s.get('fh_others'))).strip()
    if fo:
        fh.append(f'Others : {fo}')
    if peds:
        sh = ['Smoking / Alcohol : 해당 없음(소아)']
    else:
        sh = []
        for key, slot, name in (('sh.smoking', 'sh_smoke', 'Smoking'), ('sh.alcohol', 'sh_alcohol', 'Alcohol')):
            mk, dt = m(key), _det(facts, key)
            if mk == ' ':  # 사실 추출이 고정 키를 놓쳤으면 해당 slot 문답에서 직접(물었는데 빈칸이면 기록 오류)
                e = next((x for x in reversed(enc.ledger) if x.get('qid') == slot and not x.get('refused')), None)
                if e:
                    ans = e.get('reply') or ''
                    if re.search(r'(안\s*(마|피)|없|끊|전혀|평생\s*안|아니)', ans):
                        mk = '-'
                    else:
                        mk, dt = '+', re.sub(r'^(네|예)[,.\s]*', '', ans).rstrip('.요')[:24]
            sh.append(f"{name} ({mk}) {dt}".rstrip())
    so = nfc(as_text(s.get('sh_others'))).strip()
    if so:
        sh.append(f'Others : {so}')
    r = lambda k: m('ros.' + k)  # noqa: E731
    ros = [f"General weakness ({r('General weakness')})  Fatigue ({r('Fatigue')})",
           f"Headache ({r('Headache')})  Dizziness ({r('Dizziness')})",
           f"Chest pain ({r('Chest pain')})  Palpitation ({r('Palpitation')})",
           f"Fever/Chill/Cough/Sputum/Rhinorrhea ({r('Fever')}/{r('Chill')}/{r('Cough')}/{r('Sputum')}/{r('Rhinorrhea')})",
           f"Abdominal pain ({r('Abdominal pain')})  Melena ({r('Melena')})  Hematochezia ({r('Hematochezia')})  "
           f"Hematemesis ({r('Hematemesis')})",
           f"Anorexia/Nausea/Vomiting/Diarrhea/Constipation ({r('Anorexia')}/{r('Nausea')}/{r('Vomiting')}/"
           f"{r('Diarrhea')}/{r('Constipation')})"]
    ro = nfc(as_text(s.get('ros_others'))).strip()
    # 누락 점검: +/- 사실 중 라벨이 S 어느 칸에도 없으면 해당 섹션 Others 끝에 덧붙임
    s_text = ' '.join([as_text(s.get(k)) for k in ('hpi', 'cc_text', 'pmh_others', 'fh_others', 'sh_others', 'ros_others',
                                                    'meds')] + [as_text(s.get('peds'))])
    add = {'pmh': [], 'fh': [], 'sh': [], 'ros': []}
    for f in facts:
        # v7 C5-b: hpi 사실도 보충(→ ROS Others), ice는 write_subjective의 걱정·궁금증 줄이 처리
        if f['key'] != 'other' or f['sec'] == 'ice':
            continue
        if f['pol'] not in '+-' and not f.get('detail'):  # v7: '?' 사실은 세부가 있으면 모든 섹션에서 '라벨 : 세부'
            continue
        lab = f['label']
        sec = {'meds': 'pmh', 'women': 'ros', 'psych': 'ros', 'peds': 'pmh', 'hpi': 'ros'}.get(f['sec'], f['sec'])
        sec_text = {'fh': as_text(s.get('fh_others')), 'sh': as_text(s.get('sh_others')),
                    'pmh': as_text(s.get('pmh_others')) + ' ' + as_text(s.get('meds')) + ' ' + as_text(s.get('peds')),
                    'ros': s_text}.get(sec, s_text)
        if f['pol'] not in '+-':
            sec_text = s_text  # '?' 사실은 S 전체로 중복 판정(HPI에 이미 있으면 Others에 다시 넣지 않음)
        det = f.get('detail') or ''
        if not lab or lab in sec_text or lab in ' '.join(add.get(sec, [])) or (det and det in sec_text):
            continue
        if sec in add:
            if f['pol'] in '+-':
                item = f"{lab}({f['pol']}{', ' + det if f['pol'] == '+' and det else ''})"
            else:
                item = f"{lab} : {det}"
            if item not in add[sec]:
                add[sec].append(item)
                s_text += ' ' + lab
    if add['ros']:
        ro = (ro + ', ' if ro else '') + ', '.join(add['ros'])
    if ro:
        ros.append(f'Others : {ro}')
    for sec, lst in (('pmh', pmh), ('fh', fh), ('sh', sh)):
        if add[sec]:
            extra = ', '.join(add[sec])
            idx = next((i for i, l in enumerate(lst) if l.startswith('Others : ')), None)
            if idx is None:
                lst.append(f'Others : {extra}')
            else:
                lst[idx] += ', ' + extra
    return {'pmh': '\n'.join(pmh), 'fh': '\n'.join(fh), 'sh': '\n'.join(sh), 'ros': '\n'.join(ros)}


def _ice_line(enc, hpi: str) -> str:
    """v7 C5-a: ice 사실 중 HPI에 없는 것(detail 앞 8자 기준) 최대 3개를 '걱정·궁금증 : a; b; c' 한 줄로.
    설명 중 질문(late)을 먼저 본다 — 서버 누락의 대부분이 설명 단계 질문이었다(record_coverage B)."""
    ice = [f for f in (getattr(enc, 'facts', None) or []) if f.get('sec') == 'ice']
    ice.sort(key=lambda f: 0 if f.get('label') == '설명 중 질문' else 1)
    items = []
    for f in ice:
        t = nfc(str(f.get('detail') or '')).strip()
        if t and t[:8] not in (hpi or '') and t not in items:
            items.append(t)
    if not items:
        return hpi
    return (hpi or '').rstrip() + '\n걱정·궁금증 : ' + '; '.join(items[:3])


def write_subjective(enc) -> dict:
    s = write_s_narrative(enc)
    prof = enc.profile
    if s:
        cc = nfc(as_text(s.get('cc_text'))).strip() or prof.get('cc', '')
        onset = nfc(as_text(s.get('onset'))).strip()
        pain = nfc(as_text(s.get('pain'))).strip() or '해당 없음'
        hpi = nfc(as_text(s.get('hpi'))).replace('\\n', '\n').strip()
        if '\n' not in hpi:
            hpi = re.sub(r'(?<=[.])\s+(?=\S)', '\n', hpi)
        hpi = _verify_numbers(enc, hpi)
        hpi = re.sub(r'(관찰됨|확인됨|소견상)', '호소함', hpi)
        if len(hpi) < 20:
            hpi = ''
    else:
        cc, onset, pain, hpi = prof.get('cc', ''), '', '해당 없음', ''
    if not hpi:
        from .subjective import hpi_template
        hpi = hpi_template(enc, [])['hpi']
    hpi = _ice_line(enc, hpi)
    out = {'cc': f'C.C : {cc}\nOnset : {onset}\n통증평가 : {pain}', 'hpi': hpi}
    out.update(render_fixed(enc, s or {}))
    return out


def write_objective(enc) -> str:
    from .record import write_objective as v1_obj
    o = v1_obj(enc)
    der = getattr(enc, 'derived', None) or {}
    if der.get('Ht') and der.get('Wt'):
        ht = int(der['Ht']) if der['Ht'] == int(der['Ht']) else der['Ht']
        wt = int(der['Wt']) if der['Wt'] == int(der['Wt']) else der['Wt']
        extra = f" / Ht {ht} cm, Wt {wt} kg(환자 진술)" + (f", BMI {der['BMI']}" if der.get('BMI') else '')
        lines = o.split('\n')
        lines[0] = lines[0] + extra
        o = '\n'.join(lines)
    return o

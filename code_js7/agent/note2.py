"""v2 S칸: 서술(cc·hpi·Others·소아 블록)은 luna medium, 고정 칸 (+)/(-)는 검증된 사실표로 코드가 렌더. (v2_spec §8.9, §9.2)"""
from __future__ import annotations

import re

from .facts import qa_rows, table as facts_table
from .llm import ask_json
from .util import as_text, extract_numbers, log, nfc

ROLE = '당신은 한국 대학병원 외래의 숙련된 전문의입니다. 초진 의무기록의 S(주관적 정보) 서술 칸을 씁니다. JSON 하나만 출력하세요.'


def write_s_narrative(enc) -> dict:
    facts = getattr(enc, 'facts', None) or []
    rows = qa_rows(enc)
    listing = '\n'.join(f"턴 {r['turn']} | 의사: {r['q']} | 환자: {r['a']}" for r in rows)
    peds = enc.profile.get('pediatric')
    user = (f"시작 정보: {enc.opening} / 정보 제공자: {enc.profile.get('informant')}\n"
            f'사실표(id | 턴 | 영역 | 항목 | +/- | 세부):\n{facts_table(facts)}\n'
            f'문답 원문(참고):\n{listing}\n'
            "규칙: 묻지 않은 것은 쓰지 않음. 숫자·약 이름·기간은 그대로(숫자는 아라비아 숫자로). 환자 진술은 진술로('~ 느낌이 있다고 함', "
            "'~ 호소'), 진찰 소견처럼 쓰지 않음('관찰됨/확인됨/소견' 금지). HPI에 진단명·해석 금지. 확인한 음성 증상은 (-)로.\n"
            "환자 표현을 의학 용어로 바꿔 넓히지 말 것(묽은 변≠설사, '고교 때 갑자기 컸다'≠'사춘기 지연', 특정 질환만 물었으면 "
            "'기타 지병 없음'으로 넓히지 말고 물은 질환만 (-)). 질문이 두 항목을 묶었는데 환자가 한 항목만 답했으면 답한 항목만 기록.\n"
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


def render_fixed(enc, s: dict) -> dict:
    facts = getattr(enc, 'facts', None) or []
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
        if f['key'] != 'other' or f['sec'] in ('ice', 'hpi'):
            continue
        if f['pol'] not in '+-' and not (f['sec'] == 'fh' and f.get('detail')):
            continue
        lab = f['label']
        sec = {'meds': 'pmh', 'women': 'ros', 'psych': 'ros', 'peds': 'pmh'}.get(f['sec'], f['sec'])
        sec_text = {'fh': as_text(s.get('fh_others')), 'sh': as_text(s.get('sh_others')),
                    'pmh': as_text(s.get('pmh_others')) + ' ' + as_text(s.get('meds')) + ' ' + as_text(s.get('peds')),
                    'ros': s_text}.get(sec, s_text)
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

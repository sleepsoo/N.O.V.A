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
            "특정 약(스테로이드·한약 등)만 물었으면 meds는 '스테로이드·한약 복용 (-)'처럼 물은 것만, '술과 같이 먹지 않음'은 음주(-)가 아님. "
            "'많이 ~하지는 않음'처럼 정도를 낮춘 답은 (-)로 단정하지 말고 원문 그대로, 기간이 붙은 답(최근 몇 달 성관계 없음)은 기간을 함께.\n"
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
            + (late_ice_prompt(enc) if getattr(enc, 'v4', False) else '')
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


def render_fixed(enc, s: dict, facts=None) -> dict:
    facts = facts if facts is not None else (getattr(enc, 'facts', None) or [])
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
    if getattr(enc, 'v4', False):
        return _write_subjective_v4(enc, s or {}, cc, onset, pain, hpi)
    out = {'cc': f'C.C : {cc}\nOnset : {onset}\n통증평가 : {pain}', 'hpi': hpi}
    out.update(render_fixed(enc, s or {}))
    return out


# ---------------------------------------------------------------- v4 기록 정비(docs/v4_spec.md §4.3)
# ROS 고정 칸 동의어(칸 키 → 정규식). '묽은 변'은 설사로 넓히지 않음(Diarrhea는 '설사'만)
ROS_SYNONYMS = {
    'Chest pain': r'흉통|가슴\s*(통증|아)', 'Palpitation': r'두근|심계', 'Headache': r'두통|머리.{0,2}아',
    'Dizziness': r'어지', 'Fever': r'발열|열(이)?\s*(나|있)', 'Chill': r'오한', 'Cough': r'기침', 'Sputum': r'가래',
    'Rhinorrhea': r'콧물', 'Abdominal pain': r'복통|배.{0,2}아', 'Melena': r'흑변|검은\s*변', 'Hematochezia': r'혈변',
    'Hematemesis': r'토혈', 'Anorexia': r'식욕\s*(저하|부진|없|떨어)', 'Nausea': r'메스꺼|구역|울렁', 'Vomiting': r'구토|토했',
    'Diarrhea': r'설사', 'Constipation': r'변비', 'Fatigue': r'피로|피곤|지치', 'General weakness': r'기운\s*없|힘\s*(이)?\s*빠|무력',
}
SAFETY_NET_STOP = {'아니', '없어', '없습', '없고', '있어', '있습', '그런', '그렇', '별로', '특별', '딱히', '모르', '글쎄', '네그', '정도',
                   '같아', '같습', '요즘', '조금', '많이', '그냥', '이에', '예요', '이요', '했어', '해요', '않아', '않았', '거의', '전혀',
                   '평소', '가끔', '자주', '아직', '처음', '지금', '그때', '저는', '제가', '우리', '아이', '그거', '그건'}


def reconcile_ros(enc, facts, hpi: str) -> list:
    """ROS 고정 칸이 비었는데 사실표(+/−) 라벨·세부나 HPI의 'X (-)/(+)'가 동의어와 맞으면 채울 사실을 만든다."""
    extra = []
    have = {f['key'] for f in facts if f.get('pol') in ('+', '-')}
    for key, pat in ROS_SYNONYMS.items():
        k = 'ros.' + key
        if k in have:
            continue
        pol, turn = None, 0
        for f in facts:
            if f.get('pol') not in ('+', '-') or f.get('key', 'other') != 'other':
                continue
            if re.search(pat, f"{f.get('label') or ''} {f.get('detail') or ''}"):
                pol, turn = f['pol'], f.get('turn', 0)
                break
        if pol is None:
            for line in (hpi or '').split('\n'):
                for m in re.finditer(pat, line):
                    tail = line[m.end():m.end() + 12]
                    mm = re.search(r'\(\s*([+-])\s*\)', tail)
                    if mm:
                        pol = mm.group(1)
                        break
                if pol:
                    break
        if pol:
            extra.append({'id': f'R{len(extra) + 1}', 'turn': turn, 'sec': 'ros', 'key': k, 'label': key, 'pol': pol,
                          'detail': ''})
    if extra:
        log(f'v4 ROS reconcile: {[(e["key"], e["pol"]) for e in extra]}')
    return extra


def _keywords(text: str) -> list:
    out = []
    for w in re.findall(r'[가-힣]{2,}', nfc(text or '')):
        k = w[:2]
        if k not in SAFETY_NET_STOP and k not in out:
            out.append(k)
    return out


def safety_net(enc, s_text: str, limit: int = 5) -> list:
    """문진 문답마다 답의 핵심어가 S 어디에도 없으면 '항목: 답 원문'(30자 이하)으로 ROS Others에 더할 목록."""
    adds = []
    for r in qa_rows(enc):
        if len(adds) >= limit:
            break
        if str(r.get('slot') or '').startswith('ice'):  # 걱정·기대는 HPI(S-narr)·late ICE가 담당
            continue
        ans = nfc(r.get('a') or '').strip()
        keys = _keywords(ans)
        if not keys or any(k in s_text for k in keys):
            continue
        label = r.get('label') or ''
        if re.search(r'(불편한|달라진|증상은\s*없)', r.get('q') or '') and r.get('slot') in ('free', ''):
            label = '기타 증상'
        if not label or label in ('적응형', 'free'):
            label = re.sub(r'(에\s*대해\s*자세히\s*말씀해\s*주세요|있으세요|있나요|어떠세요|하세요|드세요|세요|나요|\?)', '',
                           r.get('q') or '').strip()[:12] or '문진'
        item = f'{label}: {ans}'
        if len(item) > 30:
            item = item[:30].rstrip()
        adds.append(item)
        s_text += ' ' + ans
    return adds


def late_ice(enc) -> list:
    """설명 단계 환자 답 중 질문·두려움(late ICE)."""
    from .say import is_patient_question
    out = []
    for e in enc.ledger:
        if e.get('kind') == 'SAY' and not e.get('refused') and e.get('phase') in ('explain', 'explain-answer'):
            r = nfc(e.get('reply') or '').strip()
            if r and is_patient_question(r) and r not in out:
                out.append(r)
    return out[:3]


def late_ice_prompt(enc) -> str:
    qs = late_ice(enc)
    if not qs:
        return ''
    return (f"- 설명 중 환자 질문·걱정(late ICE): {qs} → hpi 마지막 줄 앞에 '~을 궁금해함/걱정함'으로 한 줄 기록"
            "(질문 원문 내용 그대로, 답은 쓰지 말 것).\n")


def _write_subjective_v4(enc, s: dict, cc: str, onset: str, pain: str, hpi: str) -> dict:
    from .record import unsupported_claims
    facts = list(getattr(enc, 'facts', None) or [])
    qs = late_ice(enc)
    if qs and '궁금' not in hpi and '걱정' not in hpi[-80:]:
        q = qs[0][:40]
        hpi = hpi.rstrip() + f'\n설명 중 "{q}"라고 물으며 궁금해함.'
    hpi = unsupported_claims(enc, hpi)
    facts2 = facts + reconcile_ros(enc, facts, hpi)
    out = {'cc': f'C.C : {cc}\nOnset : {onset}\n통증평가 : {pain}', 'hpi': hpi}
    fixed = render_fixed(enc, s, facts=facts2)
    s_text = ' '.join([hpi, cc] + list(fixed.values()))
    adds = safety_net(enc, s_text)
    if adds:
        ros = fixed['ros'].split('\n')
        idx = next((i for i, l in enumerate(ros) if l.startswith('Others : ')), None)
        if idx is None:
            ros.append('Others : ' + ', '.join(adds))
        else:
            ros[idx] += ', ' + ', '.join(adds)
        fixed['ros'] = '\n'.join(ros)
        log(f'v4 S safety net: {adds}')
    out.update(fixed)
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

"""진단 투표, 계획(P), S(subjective.py)·O(프로그램)·A 작성, 후처리·검증, 폴백 기록, DIAGNOSE 제출.

원칙: gpt-oss-20b는 판정·짧은 서술만, 형식은 프로그램 템플릿이 책임진다.
"""
from __future__ import annotations

import re
import time
import uuid

from nova_sdk import RECORD_FIELDS, NovaError, empty_record

from . import banks, subjective
from .llm import ask_json
from .util import as_text, extract_numbers, log, log_error, nfc

DOCTOR_ROLE = '당신은 한국 대학병원 외래의 숙련된 전문의입니다.'

FACT_RULES = ('규칙: 오직 아래 시작 정보와 진료 기록(대화·진찰)에 있는 사실만 근거로 씁니다. 숫자·약 이름·기간은 기록 그대로 쓰고 '
              '추정·환산하지 않습니다. 진찰하지 않은 소견을 정상이라고 쓰지 않습니다.')

SECTION_ORDER = ['V/S', 'General', 'Growth', 'Pulse', 'Skin', 'H/E/E/N/T', 'Neck', 'Lymph', 'Chest', 'Breast',
                 'Abdomen', 'Genitalia', 'Extremities', 'Neuro', 'Psych']

DIFF_EXAMPLE = ('r/o 소화성 궤양 : 공복 시 통증 악화 없고 흑색변(-)으로 가능성 낮음. 위내시경으로 감별\n'
                'r/o 급성 담낭염 : 발열(-), 머피 징후(-)로 가능성 낮음. 복부 초음파로 확인')


# ------------------------------------------------------------------ 진단
def _norm_dx(s: str) -> str:
    return re.sub(r'[\s()\[\]·,\-\'’"]+', '', nfc(s).lower())


def _dx_key(d: dict) -> tuple[str, str]:
    return _norm_dx(d.get('diagnosis_ko', '')), _norm_dx(d.get('diagnosis_en', ''))


def _same(a: dict, b: dict) -> bool:
    ak, ae = _dx_key(a)
    bk, be = _dx_key(b)
    if ak and bk and (ak == bk or (len(ak) >= 3 and ak in bk) or (len(bk) >= 3 and bk in ak)):
        return True
    if ae and be and (ae == be or (len(ae) >= 6 and ae in be) or (len(be) >= 6 and be in ae)):
        return True
    return False


def format_dx(d: dict) -> str:
    ko = re.sub(r'\s+', ' ', nfc(d.get('diagnosis_ko') or '').strip())
    en = re.sub(r'\s+', ' ', nfc(d.get('diagnosis_en') or '').strip())
    en = re.sub(r'\s*\(.*?\)\s*', ' ', en).strip()  # 영문명 안의 괄호 제거(중첩 괄호 방지)
    if ko and en and en.lower() not in ko.lower():
        s = f'{ko} ({en})'
    else:
        s = ko or en
    while len(s.encode('utf-8')) > 480:
        s = s[:-1]
    return s


def vote_diagnosis(enc) -> tuple[str, dict]:
    cfg = enc.cfg
    sys_prompt = DOCTOR_ROLE + ' 진료 기록을 근거로 최종 주진단을 정합니다. JSON 객체 하나만 출력하세요.'
    user = (f'{enc.start_info()}\n\n진료 기록:\n{enc.transcript(clinical_only=True)}\n\n'
            f'문진 중 고려한 감별진단: {enc.differentials}\n\n'
            '지침: 증상 이름(예: 불면, 체중 감소, 저신장)이 아니라 이 환자의 증상·병력·진찰 소견을 가장 잘 설명하는 구체적 원인 질환명을 '
            '주진단으로 고르세요. 가능하면 원인까지 포함한 표준 진단명(DSM-5·ICD에 있는 이름 하나, 여러 진단·증상명을 "및"으로 '
            '이어 붙이지 말 것)을 쓰세요. '
            '약물 남용·의존 양상(내성, 금단, 조절 실패, 여러 곳 처방)이 있으면 해당 물질 사용장애를 우선 고려하고, '
            '소아 저신장 용어 정의: 가족성 저신장 = 부모 키 자체가 작아 중간부모키가 작은 경우. 체질성 성장지연(constitutional delay '
            'of growth and puberty) = 부모 키는 정상이지만 부모 중 어릴 때 작다가 늦게 컸거나 사춘기가 늦었던 사람이 있고, 성장속도가 '
            '정상 하한·사춘기 징후가 아직 없는 경우. 성장속도 감소나 동반 증상이 있으면 병적 원인(내분비·만성질환)을 고려.\n'
            '방법: 먼저 후보 진단 3개를 정하고 각 후보마다 이 환자에게서 확인된 지지 소견과 맞지 않는 소견을 대본 그대로 적은 뒤, '
            '지지 소견이 가장 많고 반대 소견이 가장 적은 후보를 주진단으로 고르세요.\n'
            '출력: {"candidates": [{"dx": "후보", "for": ["지지 소견"], "against": ["맞지 않는 소견"]}], '
            '"diagnosis_ko": "한국어 진단명", "diagnosis_en": "English name", "confidence": 0~1, '
            '"key_evidence": ["근거 사실 3~5개"], "top_differentials": ["감별진단 3~5개"]}')
    efforts = [e.strip() for e in cfg['DX_EFFORTS'].split(',') if e.strip()]
    samples = []
    for k, effort in enumerate(efforts):
        if enc.time_left() < cfg['RECORD_MIN_SECONDS'] + 60 or not enc.budget.can_call(cfg['CALL_RESERVE'] // 2):
            break
        if len(samples) == 2 and _same(samples[0], samples[1]):
            break  # 두 표가 같으면 세 번째는 생략(시간·비용 절약)
        if samples and enc.budget.degraded:
            break  # Doctor 장애 중이면 한 표로 확정하고 기록에 시간을 남긴다
        res = ask_json(enc.client, enc.budget, sys_prompt, user, effort=effort, max_tokens=cfg['DX_MAX_TOKENS'],
                       tag=f'dx{k + 1}-{effort}', want=dict, tries=2,
                       validate=lambda v: bool(str(v.get('diagnosis_ko') or v.get('diagnosis_en') or '').strip()),
                       max_wait=300)
        if res:
            try:
                res['confidence'] = float(res.get('confidence') or 0.5)
            except (TypeError, ValueError):
                res['confidence'] = 0.5
            res['_effort'] = effort
            samples.append(res)
    if not samples:
        d = {'diagnosis_ko': enc.differentials[0] if enc.differentials else '', 'diagnosis_en': ''}
        return (format_dx(d) or '진단 미정'), {'samples': [], 'fallback': True}
    clusters: list[list[dict]] = []
    for s in samples:
        for c in clusters:
            if _same(c[0], s):
                c.append(s)
                break
        else:
            clusters.append([s])
    # 표 수 → high 표 포함 여부 → 확신도 합
    clusters.sort(key=lambda c: (len(c), any(x['_effort'] == 'high' for x in c), sum(x['confidence'] for x in c)),
                  reverse=True)
    best_cluster = clusters[0]
    best = max(best_cluster, key=lambda x: (bool(x.get('diagnosis_ko')) and bool(x.get('diagnosis_en')),
                                            x['_effort'] == 'high', x['confidence']))
    detail = {'samples': [{k: s.get(k) for k in ('diagnosis_ko', 'diagnosis_en', 'confidence', '_effort')} for s in samples],
              'key_evidence': best.get('key_evidence'), 'top_differentials': best.get('top_differentials'),
              'cluster_sizes': [len(c) for c in clusters]}
    diffs = [format_dx(c[0]) for c in clusters[1:]]
    for d in best.get('top_differentials') or []:
        if isinstance(d, str) and d.strip() and not _same({'diagnosis_ko': d}, best):
            diffs.append(d.strip())
    detail['differentials'] = diffs
    return format_dx(best) or '진단 미정', detail


# ------------------------------------------------------------------ 계획 (P)
DOSE_RE = re.compile(r'\s*\(?\s*\d+(?:[.,]\d+)?\s*(?:[~\-–]\s*\d+(?:[.,]\d+)?\s*)?(?:mg|㎎|mcg|µg|μg|ug|IU|mL|ml|cc'
                     r'|g(?![a-zA-Z])|단위|정|알|캡슐|포)(?![가-힣a-zA-Z])(?:\s*/\s*(?:kg|일|회|day|d))?\s*\)?'
                     r'|\s*(?:하루|1일)\s*\d+\s*회|\s*\b(?:bid|tid|qid|qd|qhs|prn)\b', re.I)
GLOBAL_BAN_RE = re.compile(r'(수면주사|프로포폴|마약성\s*진통제\s*처방)')
PEDS_BAN_RE = re.compile(r'(아스피린|지사제|로페라미드)')
COND_RE = re.compile(r'(고려|확인\s*후|결과에\s*따라|필요\s*시|금기)')


def strip_new_doses(line: str, source_text: str = '') -> str:
    """새 약 용량 표기를 지운다. 문진 원문에 같은 표기(공백 무시)가 있으면 현재 복용약으로 보고 보존."""
    src = re.sub(r'\s+', '', nfc(source_text or '')).lower()

    def _sub(m):
        frag = re.sub(r'\s+', '', m.group(0)).strip('()').lower()
        if frag and src and frag in src:
            return m.group(0)
        return ' '
    new = DOSE_RE.sub(_sub, line)
    return re.sub(r'[ \t]{2,}', ' ', new).replace(' ,', ',').strip()


def clean_plan_text(text: str, *, strip_dose=False, source_numbers=None, source_text='') -> str:
    """P칸 정리. strip_dose는 treatment에만: 새 약 용량(원문에 없는 표기)을 지우고 조건부 문구로 보정."""
    t = nfc(text).replace('\\n', '\n')
    out = []
    for line in t.split('\n'):
        if strip_dose:
            new = strip_new_doses(line, source_text)
            if new != line.strip() and not COND_RE.search(new) and new.strip(' -'):
                new = '- 검사 결과 확인 후 ' + new.strip(' -').rstrip('.') + ' 고려'
            line = new
        line = re.sub(r'[ \t]{2,}', ' ', line)
        if line.strip(' -,;:'):
            out.append(line.rstrip(' ,;:'))
    return '\n'.join(out)


def filter_plan_lines(text: str, pediatric: bool, avoid: str = '') -> str:
    kept = []
    for line in (text or '').split('\n'):
        if GLOBAL_BAN_RE.search(line) or (pediatric and PEDS_BAN_RE.search(line)):
            log(f'plan line removed (ban): {line}')
            continue
        if avoid and re.search(avoid, line):
            log(f'plan line removed (avoid): {line}')
            continue
        kept.append(line)
    return '\n'.join(kept)


def write_plan(enc) -> dict:
    cfg = enc.cfg
    sys_prompt = DOCTOR_ROLE + ' 초진 기록의 계획(P)을 작성합니다. JSON 객체 하나만 출력하세요.'
    user = (f'{enc.start_info()}\n\n진료 기록:\n{enc.transcript(clinical_only=True)}\n\n주진단(아직 검사 전 임상 진단): {enc.dx}\n'
            f'감별진단: {enc.dx_detail.get("differentials") or enc.differentials}\n\n'
            '실제 외래 초진 수준으로 구체적으로 쓰세요. 각 값은 한국어 문자열이며 항목마다 "- "로 시작하는 줄로 나눕니다.\n'
            '초진이므로 약 용량(mg 등)은 쓰지 말고 "검사 결과 확인 후 ○○ 시작 고려", "금기 확인 후 증상 조절제", '
            '"급격한 중단 금지"처럼 조건부로 씁니다(현재 복용 중인 약의 용량은 기록 그대로 써도 됨).\n'
            '확진·주요 감별 배제·치료 전 기준치·안전(가임기 여성은 β-hCG 등)에 필요한 검사만, 불필요·침습적 검사와 적응증 없는 약'
            '(수면제·스테로이드·항히스타민 등)은 쓰지 마세요. 환자 요청(처방 등)이 있으면 그 결정과 이유를 treatment에 한 줄로. '
            'disposition에는 입원 필요/불필요와 근거, follow_up에는 "재진 : 구체적 기간과 확인할 것", "모니터링 : 간격과 항목", '
            '"즉시 내원 : 구체적 경고 증상 4개 이상"을 쓰세요.\n'
            '{"tests": "필요한 혈액·영상·기타 검사명 : 이유 (주진단 확인, 감별진단 배제, 치료 전 기준치) 3~6줄",\n'
            ' "treatment": "약물(계열·원칙)·비약물 치료, 안전 고려 2~5줄",\n'
            ' "disposition": "귀가/외래 추적/전문과 의뢰/입원·응급 중 결정과 이유 1~3줄",\n'
            ' "follow_up": "재진 시점과 그때 확인할 것 1~2줄 + \'즉시 내원 : 경고 증상들\' 1줄",\n'
            ' "education": "질환·검사·치료·생활 수칙·경고 증상 교육 3~5줄"}')
    res = ask_json(enc.client, enc.budget, sys_prompt, user, effort=cfg['PLAN_EFFORT'], max_tokens=cfg['PLAN_MAX_TOKENS'],
                   tag='plan', want=dict, tries=2, reserve=cfg['CALL_RESERVE'] // 2,
                   validate=lambda v: bool(as_text(v.get('tests')).strip()), max_wait=300)
    plan = {}
    src = enc.opening + '\n' + '\n'.join(e.get('reply') or '' for e in enc.ledger)
    peds = bool(enc.profile.get('pediatric'))
    for k in ('tests', 'treatment', 'disposition', 'follow_up', 'education'):
        txt = clean_plan_text(as_text((res or {}).get(k)).strip(), strip_dose=(k == 'treatment'), source_text=src)
        if k in ('tests', 'treatment'):
            txt = filter_plan_lines(txt, peds)
        plan[k] = txt
    if plan.get('treatment') and re.search(r'(시작|처방|투여|복용)', plan['treatment']) and \
            not re.search(r'(금기|알레르기|상호작용)', plan['treatment']):
        plan['treatment'] += '\n- 새 약 시작 전 금기·약물 알레르기·상호작용 확인'
    return plan


def vitals_assessment(enc, short: bool = False) -> str:
    """활력 요약. short=False는 v6 문장(수치 포함), short=True는 v7 C4-d 수치 없는 요약(P 처치 결정용)."""
    v = enc.vitals
    nums = {}
    m = re.search(r'(\d{2,3})\s*/\s*(\d{2,3})', v)
    if m:
        nums['sbp'], nums['dbp'] = int(m.group(1)), int(m.group(2))
    for key, pat in (('hr', r'맥박\s*:?\s*(\d+)'), ('rr', r'호흡\s*:?\s*(\d+)'), ('bt', r'체온\s*:?\s*(\d+(?:\.\d+)?)')):
        mm = re.search(pat, v)
        if mm:
            nums[key] = float(mm.group(1))
    abn, unstable = [], False
    if 'sbp' in nums:
        if nums['sbp'] < 90:
            abn.append('저혈압')
            unstable = True
        elif nums['sbp'] >= 180:
            abn.append('고도 혈압 상승')
            unstable = True
        elif nums['sbp'] >= 140:
            abn.append('혈압 상승')
    if 'hr' in nums:
        if nums['hr'] > 130 or nums['hr'] < 45:
            abn.append('심한 맥박 이상')
            unstable = True
        elif nums['hr'] > 100:
            abn.append(f"빈맥 {int(nums['hr'])}회/분")
        elif nums['hr'] < 55:
            abn.append('서맥')
    if 'rr' in nums and nums['rr'] > 24:
        abn.append('빈호흡')
        unstable = unstable or nums['rr'] > 28
    if 'bt' in nums and nums['bt'] >= 37.8:
        abn.append('발열')
        unstable = unstable or nums['bt'] >= 39.5
    if short:
        if unstable:
            return f"활력징후 불안정({', '.join(abn)}) — 응급 평가 필요"
        return '활력징후 대체로 안정' + (f"({', '.join(abn)})" if abn else '')
    status = '활력징후 불안정 — 응급 평가 필요' if unstable else '활력징후 대체로 안정'
    adm = '입원·응급 평가 필요' if unstable else '급성 위험 징후 없어 입원 불필요, 외래 추적'
    return f"- {status}" + (f"({', '.join(abn)})" if abn else '') + f" : {vitals_line(enc)} → {adm}"


def finalize_plan(enc, plan: dict) -> dict:
    plan = dict(plan or {})
    fbp = fallback_plan(enc)
    for k in RECORD_FIELDS['P']:
        if not (plan.get(k) or '').strip():
            plan[k] = fbp[k]
    va = vitals_assessment(enc)
    if '활력징후' not in plan['disposition'] and 'V/S' not in plan['disposition']:
        plan['disposition'] = va + '\n' + plan['disposition']
    if not re.search(r'(즉시|바로|응급실)', plan['follow_up']):
        plan['follow_up'] += '\n- 즉시 내원 : 증상 급격한 악화, 호흡곤란, 흉통, 의식 변화, 고열 시'
    plan['education'] = education_text(enc.explained, plan.get('education', ''))
    return plan


def education_text(explained, planned_edu: str) -> str:
    """교육칸 = 실제로 말한 문장 + '다음 방문 시 교육 예정' 2줄 이하."""
    said = [x for x in (explained or []) if '?' not in x]
    lines = []
    if said:
        lines.append('진료 중 설명함:')
        lines += [f'- {x}' for x in said]
    said_txt = ' '.join(said)
    later = []
    for l in (planned_edu or '').split('\n'):
        l = l.strip(' -')
        if not l:
            continue
        keys = [w for w in re.findall(r'[가-힣]{2,}', l)][:4]
        if keys and sum(1 for k in keys if k in said_txt) >= max(1, len(keys) // 2):
            continue  # 이미 말한 내용
        later.append(l)
    if later:
        lines.append('다음 방문 시 교육 예정 : ' + '; '.join(later[:2]))
    if not lines:
        lines = ['다음 방문 시 교육 예정 : ' + (planned_edu or '진단·검사·경고 증상 설명').replace('\n', '; ')[:200]]
    return '\n'.join(lines)


# ------------------------------------------------------------------ S
def write_subjective(enc) -> dict:
    return subjective.write_subjective(enc)


def fallback_subjective(enc) -> dict:
    items = subjective.qa_items(enc)
    findings = getattr(enc, 'findings', None) or subjective.fallback_findings(items)
    out = subjective.hpi_template(enc, findings)
    out.update(subjective.render_history(enc, findings))
    return out


def verify_numbers(enc, s: dict) -> dict:
    """cc·hpi에 나온 숫자가 시작 정보·진료 기록에 있는지 확인. 없는 숫자가 있는 문장은 제거(실패 시 템플릿)."""
    # 턴 번호는 근거 숫자가 아니므로 제외하고 문답 내용만 본다
    source = enc.opening + '\n' + enc.vitals + '\n' + '\n'.join(
        f"{e['text']} {e['reply']}" for e in enc.ledger if not e.get('refused'))
    allowed = extract_numbers(source) | {'0', '1', '2', '3'}

    def bad(text: str) -> set[str]:
        out = set()
        text = re.sub(r'턴\s*\d+(?:\s*[-~,/·및]\s*(?:턴\s*)?\d+)*', '', text)  # 턴 번호 인용은 검사 제외
        text = re.sub(r'#1\.?', '', text)
        for m in re.finditer(r'(?<![A-Za-z])\d+(?:\.\d+)?', text):
            n = m.group(0)
            try:
                v = float(n)
                n = str(int(v)) if v == int(v) else str(v)
            except ValueError:
                pass
            if n not in allowed:
                out.add(n)
        return out

    removed = 0
    for k in [k for k in ('cc', 'hpi', 'evidence') if k in s]:
        lines = []
        for line in (s.get(k) or '').split('\n'):
            if bad(line):
                parts = re.split(r'(?<=[.;])\s+|,\s+', line)
                kept = [p for p in parts if not bad(p)]
                removed += len(parts) - len(kept)
                line = ', '.join(kept).strip()
            if line.strip():
                lines.append(line)
        s[k] = '\n'.join(lines)
    if removed:
        log(f'number check: removed {removed} fragments')
    if 'hpi' in s and len(s.get('hpi', '')) < 20:
        s.update({k: v for k, v in fallback_subjective(enc).items() if k in ('cc', 'hpi')})
    return s


# ------------------------------------------------------------------ O (프로그램)
def vitals_line(enc) -> str:
    v = re.sub(r'\s*\n\s*', ', ', enc.vitals.strip())
    v = v.replace('혈압', 'BP').replace('맥박', 'PR').replace('호흡', 'RR').replace('체온', 'BT')
    return re.sub(r'\s*:\s*', ' ', v)


def write_objective(enc) -> str:
    from .encounter import exam_name
    groups: dict[str, list[str]] = {}
    vs_parts = [f'{vitals_line(enc)} (시작 정보)']
    start_nums = extract_numbers(enc.vitals or '')
    same_vs = False
    for e in enc.ledger:
        if e['kind'] != 'EXAM' or e.get('refused'):
            continue
        # v7 C5-d: 활력 측정값이 시작 정보와 같으면(숫자 부분집합) V/S 한 줄로 쓰고 진찰 항목은 다시 덧붙이지 않는다
        if e.get('qid') == 'vitals' and not same_vs:
            got = extract_numbers(e.get('reply') or '')
            if got and start_nums and got <= start_nums:
                vs_parts[0] = f"{vitals_line(enc)} (턴 {e['turn']} 측정, 시작 정보와 같음)"
                same_vs = True
                continue
        name = exam_name(e['text'])
        system = e.get('system') or (banks.EXAM_BY_ID.get(e.get('qid'), (None, None, 'Others'))[2])
        item = f"{name} : {e['reply']} (턴 {e['turn']})"
        if system == 'V/S':
            vs_parts.append(item)
        else:
            groups.setdefault(system, []).append(item)
    lines = ['V/S : ' + ' / '.join(vs_parts)]
    for sec in SECTION_ORDER[1:] + sorted(k for k in groups if k not in SECTION_ORDER):
        if sec in groups:
            lines.append(f'{sec} : ' + '. '.join(groups[sec]))
    return '\n'.join(lines)


# ------------------------------------------------------------------ A
DIFF_LINE = re.compile(r'^r/o\s+[^:]{2,}\s:\s*\S.{5,}')


def _diff_lines(text: str) -> tuple[list[str], list[str]]:
    good, bad = [], []
    for line in nfc(text).replace('\\n', '\n').split('\n'):
        line = line.strip(' -•')
        if not line:
            continue
        if not line.lower().startswith('r/o'):
            line = 'r/o ' + line
        line = re.sub(r'^r/o\s*', 'r/o ', line, flags=re.I)
        line = re.sub(r'\s*[:：]\s*', ' : ', line, count=1)
        (good if DIFF_LINE.match(line) else bad).append(line)
    return good, bad


def write_assessment(enc, s: dict, o_exam: str) -> dict:
    cfg = enc.cfg
    sys_prompt = DOCTOR_ROLE + ' 초진 기록의 평가(A) 칸을 작성합니다. JSON 객체 하나만 출력하세요.'
    diffs = enc.dx_detail.get('differentials') or enc.differentials
    user = (f'{enc.start_info()}\n\n진료 기록:\n{enc.transcript(clinical_only=True)}\n\n진찰 소견 정리:\n{o_exam}\n\n주진단: {enc.dx}\n'
            f'감별진단 후보: {diffs}\n\n{FACT_RULES}\n'
            'evidence: "#1. 주진단" 다음 줄부터 "- 근거 : 사실 → 해석" 3~5줄(병력·진찰 소견을 턴 번호와 함께 인용).\n'
            'differential: 주진단과 같은 증상을 설명할 수 있는 질환만 3~5줄. 각 줄은 반드시 "r/o 진단명 : 어떤 소견 때문에 가능성이 '
            '낮거나 남는지 + 감별 검사" 형식. 서로 모순되는 질환(예: 기능항진 증상에 기능저하 질환)은 넣지 마세요.\n'
            f'형식 예시(다른 증례):\n{DIFF_EXAMPLE}\n'
            '출력: {"evidence": "...", "differential": "줄바꿈으로 구분된 r/o 줄들"}')
    res = ask_json(enc.client, enc.budget, sys_prompt, user, effort=cfg['A_EFFORT'], max_tokens=cfg['A_MAX_TOKENS'],
                   tag='A', want=dict, tries=2, reserve=1, validate=lambda v: bool(as_text(v.get('evidence')).strip()),
                   max_wait=300)
    evidence = nfc(as_text((res or {}).get('evidence'))).replace('\\n', '\n').strip()
    good, bad = _diff_lines(as_text((res or {}).get('differential')))
    if bad and len(good) < 3 and enc.budget.can_call(1) and enc.time_left() > cfg['RECORD_MIN_SECONDS']:
        fix = ask_json(enc.client, enc.budget, sys_prompt,
                       f'주진단: {enc.dx}\n진찰 소견:\n{o_exam}\n\n다음 감별진단 줄에 이유와 감별 검사를 붙여 '
                       f'"r/o 진단명 : 이유. 감별 검사" 형식으로 고치세요.\n' + '\n'.join(bad)
                       + '\n출력: {"differential": "줄바꿈으로 구분"}', effort='low', max_tokens=2500, tag='A-fix',
                       want=dict, tries=1, reserve=1)
        g2, _ = _diff_lines(as_text((fix or {}).get('differential')))
        good += [g for g in g2 if g not in good]
    if len(good) < 2:
        good += bad[: 2 - len(good)]
    if evidence:
        lines = evidence.split('\n')
        if lines[0].lstrip().startswith('#1'):
            lines = lines[1:]  # 첫 줄은 항상 확정된 주진단으로 다시 쓴다("#1. 주진단" 같은 자리표시 방지)
        body = verify_numbers(enc, {'evidence': '\n'.join(lines)})['evidence']  # 기록에 없는 숫자 제거
        evidence = f'#1. {enc.dx}\n' + body
    return {'evidence': evidence, 'differential': '\n'.join(good[:5])}


# ------------------------------------------------------------------ 폴백
def fallback_plan(enc) -> dict:
    return {
        'tests': '- 기본 혈액검사(CBC, 전해질, 간·신장 기능, 혈당) : 전신 상태 평가\n- 주진단 확인을 위한 표적 검사 : 감별진단 배제',
        'treatment': '- 검사 결과 확인 후 원인에 맞는 치료 시작 고려\n- 금기 확인 후 증상 조절',
        'disposition': '- 급성 위험 징후 없어 외래 추적',
        'follow_up': '- 1~2주 후 검사 결과 확인 위해 재진\n- 즉시 내원 : 증상 악화, 호흡곤란, 의식 변화, 흉통 시',
        'education': '- 진단 가능성과 검사 필요성 설명\n- 경고 증상 시 즉시 내원 안내',
    }


# ------------------------------------------------------------------ 후처리·조립·제출
def tidy(text: str) -> str:
    t = nfc(str(text or '')).replace('\\n', '\n').replace('\r', '')
    t = re.sub(r'\)n(?=[A-Za-z가-힣])', ')\n', t)          # "( )nChest" 같은 잔여 n
    t = re.sub(r'[ \t]{3,}', '  ', t)
    lines = []
    for line in t.split('\n'):
        line = line.rstrip()
        opens, closes = line.count('('), line.count(')')
        if opens > closes:
            line += ')' * (opens - closes)
        lines.append(line)
    t = '\n'.join(lines)
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip()


# v6: 안전 확인 문진의 환자 답을 결정적으로 S·P에 남긴다(LLM 추출에 의존하지 않음). 답이 없으면 줄을 넣지 않는다.
NEG_RE = re.compile(r'(없어|없었|없습|없고|없네|없죠|아니|안\s*했|적\s*없|전혀)')
POS_RE = {'seizure': re.compile(r'(경련|발작|헛것|있었|있어|있습)'), 'cardio': re.compile(r'(천식|심장병|심장\s*질환|협심|부정맥|심부전)')}
DENY_RE = re.compile(r'^\s*(아니(요|에요)|없어요|없습니다|그런\s*(건|거|것|적)\S*\s*없)')  # 주제와 무관한 부정('갑상샘 질환은 없어요')은 제외


def _reply(enc, qid='', text=''):
    """문진 원장에서 qid(또는 같은 문장)의 마지막 유효 답(원문, 마침표 제거)과 턴. 없으면 ('', None)."""
    for e in reversed(getattr(enc, 'ledger', None) or []):
        if e.get('kind') == 'SAY' and not e.get('refused') and not e.get('one_at_a_time') and \
                ((qid and e.get('qid') == qid) or (text and e.get('text') == text)) and (e.get('reply') or '').strip():
            return nfc(e['reply']).strip().rstrip('.')[:60], e.get('turn')
    return '', None


def _status(ans, kind):
    if not ans:
        return ''
    if NEG_RE.search(ans):
        return '없음'
    return '있음' if POS_RE[kind].search(ans) else ''


def add_safety_lines(enc, note: dict) -> dict:
    from . import kb as kbmod
    k = getattr(enc, 'kb', None) or kbmod.match_kb(enc.dx or '')
    kid = (k or {}).get('id')
    disp = note['P']['disposition'].split('\n')
    pos = next((i for i, l in enumerate(disp) if '외래 추적이 적절' in l), None)
    if kid == 'sedative_ud':
        last, t1 = _reply(enc, 'sb_last')
        seiz, t2 = _reply(enc, 'sb_seizure')
        parts = ([f'마지막 복용: {last} (턴 {t1})'] if last else []) + ([f'금단 경련·섬망 병력: {seiz} (턴 {t2})'] if seiz else [])
        if parts:
            note['S']['hpi'] = note['S']['hpi'].rstrip() + '\n' + '; '.join(parts)
        st = _status(seiz, 'seizure')
        if st:
            head = f"금단 경련·섬망 병력 {st}" + (f", 마지막 복용 {last}" if last else '') + ' → '
            if st == '없음' and pos is not None:
                disp[pos] = '- ' + head + disp[pos].lstrip('- ')
            else:
                disp.insert(0 if pos is None else pos, '- ' + head + (
                    '외래 감량 가능 여부 재평가' if st == '없음' else '입원 해독 고려 기준 해당, 정신건강의학과 우선 평가'))
    elif kid == 'graves':
        car, t3 = _reply(enc, 'wl_cardio')
        if car and not re.search(r'(Chest pain \(\s*[+-]|흉통|가슴\s*통증|가슴통증)', note['S']['ros']):
            note['S']['ros'] = note['S']['ros'].rstrip() + f'\n흉통/숨참 : {car} (턴 {t3})'
        must = next((m for _, m in (k.get('must_say') or []) if '천식' in m), '')
        ans, t4 = _reply(enc, text=must) if must else ('', None)
        st = _status(ans, 'cardio') if ans and (POS_RE['cardio'].search(ans) or DENY_RE.search(ans)) else ''
        src = f'(턴 {t4})'
        if not st:
            ans, t4 = _reply(enc, 'pmh_other')
            st = '없음' if ans and DENY_RE.search(ans) else ''
            src = f'(턴 {t4} 지병 문진에서 기저질환 부인)'
        if st:
            disp.insert(len(disp) if pos is None else pos + 1, f"- 천식·심장병 {st} 확인{src} → 베타차단제 "
                        + ('금기 없음' if st == '없음' else '신중(내분비내과 상의 후 결정)'))
    note['P']['disposition'] = '\n'.join(disp)
    return note


def build_note(enc, s: dict, o_exam: str, a: dict, plan: dict) -> dict:
    note = empty_record()
    fb = None
    for k in RECORD_FIELDS['S']:
        val = (s or {}).get(k, '')
        if not str(val).strip():
            fb = fb or fallback_subjective(enc)
            val = fb.get(k, '')
        note['S'][k] = val
    note['O']['exam'] = o_exam
    note['O']['tests'] = ''
    a = a or {}
    note['A']['evidence'] = a.get('evidence') or f'#1. {enc.dx}\n- 근거 : ' + (
        '; '.join(str(x) for x in (enc.dx_detail.get('key_evidence') or [])) or enc.profile.get('cc', ''))
    diffs = enc.dx_detail.get('differentials') or enc.differentials
    note['A']['differential'] = a.get('differential') or '\n'.join(f'r/o {d} : 추가 검사로 감별 필요' for d in diffs[:4])
    plan = finalize_plan(enc, plan)
    for k in RECORD_FIELDS['P']:
        note['P'][k] = plan[k]
    for sec, fields in RECORD_FIELDS.items():
        for f in fields:
            note[sec][f] = tidy(note[sec][f])
    return note


def _vs_repeat(line: str, o_nums: set, vl: str):
    """disposition 줄이 O칸 V/S 수치를 반복하면 수치 부분을 지운 줄(남을 내용이 없으면 None). 아니면 원래 줄."""
    if 'mmHg' not in line:
        return line
    nums = extract_numbers(re.sub(r'턴\s*\d+', '', line))
    if not nums or not o_nums or not nums <= o_nums:
        return line
    r = line.replace(vl, '') if vl else line
    r = re.sub(r'\s*:\s*(?=→|$)', ' ', r)
    r = re.sub(r'[ \t]{2,}', ' ', r).rstrip()
    if 'mmHg' in r:  # 수치를 떼어낼 수 없으면 수치 외 내용이 없을 때만 줄을 지운다(내용 보존)
        body = re.sub(r'\d+(?:\.\d+)?|mmHg|회/분|°C|℃|BP|PR|RR|BT|SpO2|혈압|맥박|호흡|체온|[\s:,()\-·/→%]', '', r)
        return None if not body else line
    return r if re.search(r'[가-힣A-Za-z]', r.strip(' -:→,')) else None


def polish_note(enc, note: dict) -> dict:
    """v7 C4-f 기록 마감 정리(내용은 지우지 않고 중복·잘못된 표기만): P 칸 중복 줄 제거(education 제외),
    disposition의 O칸 V/S 수치 반복 제거, S 과거력·가족력·사회력·ROS의 Others 정리."""
    from . import explain
    from .note2 import _clean_others
    P = note.get('P') or {}
    for k in ('tests', 'treatment', 'disposition', 'follow_up'):
        if (P.get(k) or '').strip():
            P[k] = '\n'.join(explain.dedup_lines(P[k].split('\n')))
    o = (note.get('O') or {}).get('exam') or ''
    vs = next((l for l in o.split('\n') if l.startswith('V/S')), '')
    o_nums = extract_numbers(re.sub(r'턴\s*\d+', '', vs))
    if (P.get('disposition') or '').strip() and o_nums:
        vl = vitals_line(enc) if getattr(enc, 'vitals', '') else ''
        kept = []
        for line in P['disposition'].split('\n'):
            new = _vs_repeat(line, o_nums, vl)
            if new is None:
                log(f'disposition V/S repeat removed: {line}')
            elif new.strip():
                kept.append(new)
        if kept:
            P['disposition'] = '\n'.join(kept)
    S = note.get('S') or {}
    for k in ('pmh', 'fh', 'sh', 'ros'):
        if (S.get(k) or '').strip():
            S[k] = _clean_others(S[k])
    return note


def submit(enc, note: dict, diagnosis: str):
    try:  # v6: 두 기록 경로(run.consult v2·finish) 공통 지점에서 안전 문진 답을 S·P에 결정적으로 남김
        note = add_safety_lines(enc, note)
    except Exception as exc:  # 기록 줄 보강 실패가 제출을 막지 않게
        log_error(f'safety lines failed: {type(exc).__name__}: {exc}')
    try:  # v7 C4-f: 마감 정리(add_safety_lines 다음)
        note = polish_note(enc, note)
    except Exception as exc:
        log_error(f'polish note failed: {type(exc).__name__}: {exc}')
    diagnosis = nfc(diagnosis or '').replace('\r', ' ').replace('\n', ' ').strip() or '진단 미정'
    while len(diagnosis.encode('utf-8')) > 490:
        diagnosis = diagnosis[:-1]
    for attempt in range(6):
        rid = str(uuid.uuid4())
        for same in range(4):
            try:
                return enc.client.diagnose(note=note, diagnosis=diagnosis, request_id=rid)
            except NovaError as exc:
                code = exc.code
                if code in ('API_UNAVAILABLE', 'REQUEST_PENDING', 'LOCAL_GATEWAY_UNAVAILABLE', 'INVALID_API_RESPONSE'):
                    time.sleep(3 * (same + 1))
                    continue
                log_error(f'diagnose {code}')
                if code == 'INVALID_RECORD_FIELDS':
                    fixed = empty_record()
                    for s_, fs in RECORD_FIELDS.items():
                        for f in fs:
                            fixed[s_][f] = str((note.get(s_) or {}).get(f) or '') if isinstance(note.get(s_), dict) else ''
                    note = fixed
                elif code == 'RECORD_TOO_LARGE':
                    for s_, fs in RECORD_FIELDS.items():
                        for f in fs:
                            note[s_][f] = note[s_][f][:6000]
                    diagnosis = diagnosis[:100]
                elif code in ('SINGLE_DIAGNOSIS_REQUIRED', 'FINAL_RECORD_REQUIRED'):
                    diagnosis = diagnosis.split(',')[0].strip() or '진단 미정'
                    if not any(v for fs in note.values() for v in fs.values()):
                        note['S']['hpi'] = enc.opening or '기록 없음'
                elif code in ('SESSION_CLOSED', 'SESSION_EXPIRED', 'RUN_NOT_ACTIVE'):
                    return None
                break
            except ValueError as exc:
                log_error(f'diagnose ValueError {exc}')
                note = {s_: {f: str((note.get(s_) or {}).get(f, '')) for f in fs} for s_, fs in RECORD_FIELDS.items()}
                break
    return None

"""v2 계획 + 설명: high 1회로 P 5칸·SAY 9~10문장·FAQ를 함께 만들고(계획과 발화 일치), 검증·필수 요소 보정 후 말한다.
(v2_spec §8.7, §8.8, §10.2, §10.3)"""
from __future__ import annotations

import json
import re

from . import guidelines
from . import kb as kbmod
from . import say as saymod
from . import urgency as urg
from .facts import table as facts_table
from .llm import ask, ask_json
from .util import is_similar, log, nfc

ROLE = '당신은 한국 대학병원 외래의 숙련된 전문의입니다. 초진을 마무리하며 계획(P)을 세우고 환자에게 말할 설명을 씁니다. JSON 하나만 출력하세요.'

FAQ_KEYS = {'prescribe': r'(처방|수면제\s*(주|받))', 'duration': r'(얼마나\s*오래|기간|언제까지|몇\s*(달|년))',
            'results': r'(언제|결과|며칠|얼마나\s*걸)',
            'prognosis': r'(나을|낫|좋아질|회복|클\s*수|자랄|돌아올|돌아오|평생|잘\s*수\s*있|(살|체중|몸무게).{0,6}(찌|찔|쪄|붙|늘|돌아))',
            'test_pain': r'(검사.{0,8}(아프|아파|힘들|무섭))|((아프|아파|힘들).{0,4}검사)', 'serious': r'(큰\s*병|위험|심각|괜찮|암|나쁜)',
            'treatment': r'(약|치료|끊|줄|먹어야|주사|수술)', 'tests': r'(검사|확인|무슨\s*검)',
            'lifestyle': r'(조심|주의|음식|운동|생활|약\s*없이|방법)'}


NEGATION_RE = re.compile(r'(않|안\s|금지|말\s*것|하지\s*말|피하|피함|중단하지|불필요|지양|대신)')

# ---------------------------------------------------------------- v2c 안전 필터
# 초진 P(치료·처치·추적)와 설명 SAY에서 처방 확정·수치 지시·특정 성분명·입원 불필요 단정·중복 줄을 없앤다.
DRUG_CLASS = [
    (r'메티마졸|methimazole|카비마졸|carbimazole|프로필티오우라실|\bPTU\b', '항갑상샘제'),
    (r'프로프라놀롤|propranolol|아테놀롤|atenolol|메토프롤롤|metoprolol|비소프롤롤|bisoprolol', '베타차단제'),
    (r'졸피뎀|zolpidem|에스조피클론|eszopiclone', '수면제'),
    (r'로라제팜|lorazepam|알프라졸람|alprazolam|디아제팜|diazepam|클로나제팜|clonazepam|트리아졸람|triazolam', '진정제'),
    (r'레보티록신|levothyroxine|씬지로이드', '갑상샘호르몬제'),
    (r'메트포르민|metformin', '경구 혈당강하제'),
    (r'아목시실린|amoxicillin', '항생제'),
    (r'아세트아미노펜|acetaminophen|타이레놀|이부프로펜|ibuprofen', '해열진통제'),
]
_DRUG_ANY = '|'.join(p for p, _ in DRUG_CLASS)
_DRUG_PAREN_RE = re.compile(r'\s*\(\s*(?:' + _DRUG_ANY + r')(?:\s*[·,/]\s*(?:' + _DRUG_ANY + r'))*\s*\)', re.I)
NUM_UNIT_RE = re.compile(r'\s*\(?\s*\d+(?:[.,]\d+)?(?:\s*[~\-–]\s*\d+(?:[.,]\d+)?)?\s*'
                         r'(?:mg|㎎|mcg|µg|μg|g(?![a-zA-Z])|%|퍼센트|주분|일분|회분|정|알|캡슐)'
                         r'(?:씩|만|분)?(?![가-힣a-zA-Z])\s*\)?', re.I)
INTERVAL_RE = re.compile(r'\d+(?:\s*[~\-–]\s*\d+)?\s*(?:주|일)\s*마다\s*')
FREQ_RE = re.compile(r'\s*(?:하루|1일)\s*\d+(?:\s*[~\-–]\s*\d+)?\s*(?:회|번)(?:씩)?')
CONFIRM_RE = re.compile(r'\s*(?:을|를)?\s*(?:단기\s*처방|처방합니다|처방함|처방할게요?|처방해\s*드(?:립니다|려요|릴게요?)|'
                        r'드려요|드립니다|드릴게요?|시작합니다|시작함|투여합니다|투여함|투여)')
NO_ADMIT_RE = re.compile(r'(?:,\s*)?(?:급성\s*위험\s*징후\s*없어\s*)?\(?\s*입원\s*(?:은\s*)?'
                         r'(?:불필요|필요\s*없음|필요하지\s*않음|하지\s*않음)\s*\)?(?:\s*,\s*외래\s*추적)?')
NOT_NEEDED_RE = re.compile(r'필요\s*없(?:음|다|어요)')
VITALS_LINE_RE = re.compile(r'(활력징후|V/S|mmHg|SpO2|산소포화)')
DECIDE = '검사 결과 확인 후 전문의와 상의해 결정'
SAFE_SAY = '약은 검사 결과 보고 상의해 조절해요.'
SAY_BAD_RE = re.compile(r'(드려요|드릴게|드립니다|처방(?:해\s*드|할게|해요|합니다)|단기\s*처방|'
                        r'\d+(?:\s*[~\-–]\s*\d+)?\s*(?:mg|㎎|g(?![a-zA-Z])|%|퍼센트|주분|일분|회분|정|알)(?:씩|만|분)?(?![가-힣a-zA-Z])|'
                        r'\d+(?:\s*[~\-–]\s*\d+)?\s*(?:주|일)\s*마다|(?:하루|1일)\s*\d+\s*(?:회|번))', re.I)


def drug_to_class(s: str) -> str:
    t = _DRUG_PAREN_RE.sub('', s)
    for pat, cls in DRUG_CLASS:
        t = re.sub(pat, cls, t, flags=re.I)
    # 계열명은 모두 '제'로 끝남: 조사 보정
    t = re.sub(r'제은', '제는', t)
    t = re.sub(r'제을', '제를', t)
    t = re.sub(r'제과(?=\s)', '제와', t)
    t = re.sub(r'제으로', '제로', t)
    for cls in {c for _, c in DRUG_CLASS}:  # '항갑상샘제 항갑상샘제' 같은 반복 축약
        t = re.sub(rf'{cls}(\s*[·,/]?\s*{cls})+', cls, t)
    return t


def safe_plan_line(line: str, field: str = 'treatment', admit_if: str = '') -> str:
    """P 한 줄 안전 보정. field: treatment/disposition/follow_up/education."""
    t = drug_to_class(nfc(line).strip())
    if field != 'education' and not VITALS_LINE_RE.search(t):
        t = NUM_UNIT_RE.sub(' ', t)
    if field == 'treatment':
        t = INTERVAL_RE.sub('', t)
        t = FREQ_RE.sub('', t)
    if CONFIRM_RE.search(t):
        t = CONFIRM_RE.sub('', t).rstrip(' ,.;—-')
        if DECIDE not in t:
            t = (t + ' — ' if t else '') + DECIDE
    if NO_ADMIT_RE.search(t):
        t = NO_ADMIT_RE.sub('', t).rstrip(' ,.;→—-')
        t = re.sub(r'\s*외래\s*추적$', '', t).rstrip(' ,.;→—-')
        cond = admit_if or '활력징후 불안정·증상 급격한 악화'
        tail = f'현재 외래 추적이 적절하며 {cond} 시 입원 고려'
        t = (t + (' ' if t.endswith('없어') else ' → ') + tail) if t else tail
    if field in ('treatment', 'disposition'):
        t = NOT_NEEDED_RE.sub('현재 필요성 낮으나 경과 보며 재평가', t)
    t = re.sub(r'\(\s*\)', '', t)
    t = re.sub(r'\s+([,.)])', r'\1', t)
    return re.sub(r'[ \t]{2,}', ' ', t).strip(' ,')


def _norm_line(s: str) -> str:
    return re.sub(r'[\W_]+', '', nfc(s or '')).lower()


def dedup_lines(lines: list[str]) -> list[str]:
    """공백·구두점 정규화 후 동일/포함 관계 줄 제거(긴 줄을 남김, 순서 유지)."""
    out, keys = [], []
    for l in lines:
        n = _norm_line(l)
        if not n or any(n in k for k in keys):
            continue
        hit = [i for i, k in enumerate(keys) if k in n]
        if hit:
            out[hit[0]], keys[hit[0]] = l, n
            for i in reversed(hit[1:]):
                del out[i], keys[i]
            continue
        out.append(l)
        keys.append(n)
    return out


def safe_say(s: str) -> str:
    """설명 SAY 안전 보정: 구두 처방·수치 지시는 SAFE_SAY로, 성분명은 계열명으로."""
    t = nfc(s or '').strip()
    if not t:
        return t
    if SAY_BAD_RE.search(t):
        return SAFE_SAY
    t2 = drug_to_class(t)
    if t2 != t and saymod.say_problem(t2):
        return SAFE_SAY
    return saymod.tidy(t2)   # v8c: '초음파 를' 같은 조사 띄어쓰기 정리


def _dedup_exact(lines):
    seen, out = set(), []
    for s in lines:
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [s.strip(' -') for s in v.split('\n') if s.strip(' -')]
    out = []
    for x in v:
        if isinstance(x, dict):
            name = str(x.get('name') or x.get('test') or '').strip()
            reason = str(x.get('reason') or x.get('purpose') or '').strip()
            if name:
                out.append(f'{name} : {reason}' if reason else name)
        elif str(x).strip():
            out.append(str(x).strip(' -'))
    return [nfc(s) for s in out]


def plan_and_say(enc) -> dict:
    prof = enc.profile
    facts = getattr(enc, 'facts', None) or []
    a = getattr(enc, 'assess', None) or {}
    k = kbmod.match_kb(enc.dx or '')
    enc.kb = k
    n = enc.cfg['EXPLAIN_N'] - 1  # 마지막 '더 궁금하신 점'은 코드가 붙임
    pos = [f"{f['label']}{(' ' + f['detail']) if f['detail'] else ''}" for f in facts if f['pol'] == '+'][:25]
    neg = [f['label'] for f in facts if f['pol'] == '-'][:20]
    abn = [f"{x['name']}: {x['result'][:50]}" for x in (a.get('exams') or [])]
    ice = [f"{e['text']} → {e['reply']}" for e in enc.ledger if str(e.get('qid', '')).startswith('ice')]
    sex = {'F': '여', 'M': '남'}.get(prof.get('sex'), '?')
    ddx = [d['dx'] for d in a.get('differential') or []] or enc.differentials[1:4]
    from .record import vitals_assessment
    va = vitals_assessment(enc)
    gl = guidelines.hint_plan(enc)
    gl_rule = ('- [진료지침 발췌]가 있으면 tests·treatment·disposition·follow_up의 근거로 우선 사용하되 환자 사실에 맞는 것만 고르고, '
               '지식표와 충돌하면 지식표를 따를 것. 발췌에 없는 약·검사를 지어내거나 용량 숫자를 쓰지 말 것. 경고 증상은 발췌의 위험 징후를 반영.\n'
               if gl else '')
    user = (f"환자: {prof.get('age')}세 {sex}, 정보 제공자 {prof.get('informant')}, 주진단: {enc.dx}, 감별: {ddx}\n"
            f"핵심 양성 사실: {pos}\n핵심 음성 사실: {neg}\n진찰 소견: {abn}\n활력징후 판단: {va}\n"
            f"환자 걱정·궁금증·요청(ICE): {ice} / 요청: {prof.get('request') or '없음'}\n"
            f"참고 지식표(있으면, 환자에 맞게 취사선택): {json.dumps(kbmod.kb_hint(k), ensure_ascii=False) if k else '없음'}\n"
            f'{gl}'
            '[P 규칙]\n'
            f'{gl_rule}'
            '- tests: 3~7개 {"name","reason"} — 확진, 주요 감별 배제, 치료 전 기준치, 안전(가임기 여성 β-hCG 등). 불필요·침습적 검사 금지.\n'
            "- treatment: 조건부('검사 확인 후 ~ 시작 고려', '금기 확인 후'). 새 약 용량 숫자 금지(현재 복용약은 가능). 비약물 치료 포함.\n"
            '  환자 요청이 있으면 그에 대한 결정과 이유를 한 줄로. 적응증 없는 약(수면제·스테로이드·항히스타민 등) 금지.\n'
            "- disposition: 귀가/외래/의뢰/응급 + 근거(활력징후·위험 징후), '입원 필요/불필요' 명시.\n"
            "- follow_up: '재진 : 구체적 기간과 확인할 것', '모니터링 : 간격과 항목', '즉시 내원 : 구체적 경고 증상'.\n"
            '- education: 질환 설명, 검사 이유, 치료·부작용, 생활 수칙, 경고 증상.\n'
            '[안전 체크 — 해당되는 것만 반영]\n'
            '가임기 여성 임신 확인 / 진정제: 급중단 금지·운전 회피·병용 금지 / 항갑상샘제: 무과립구증·간독성 / 베타차단제: 천식·서맥 금기 /\n'
            'NSAIDs: 위장·신장 / 항생제: 알레르기 / 소아: 아스피린 금지·체중 기반·지사제 금지 / 자살 위험: 안전 계획 / 노인: 낙상.\n'
            f'[SAY 규칙] 정확히 {n}문장, 각 공백 포함 28자 이내, 쉬운 존댓말 평서문, 영어 약어 금지(MRI·CT만 허용), 띄어쓰기 정확,\n'
            " 한 문장 한 메시지, 단정·보장 금지('걱정 안 해도', '완치', '확실히'). 내용 없는 문장 금지 — 모든 문장에 구체 정보.\n"
            ' 순서와 필수 요소:\n'
            " ①진단을 쉬운 말로(병명 포함, 검사 전이므로 '~로 보여요/가능성이 높아요'처럼, '진단합니다' 같은 확정 표현 금지)\n"
            ' ②진단의 의미·원인과 환자 증상과의 연결 한 줄(예: 호르몬이 많아 살이 빠지고 두근거려요)\n'
            ' ③환자 걱정·궁금증에 직접 답(예후 질문이면 예후로, 환자가 말하지 않은 걱정을 지어내지 말 것)\n'
            " 검사 전이므로 아직 확인 안 된 내용(뼈 나이, 호르몬 수치 등)은 '~인지 확인해요'로 말하고 단정하지 말 것.\n"
            ' ④검사 이름과 목적(1~2문장, 피검사 항목·영상·심전도 등 구체적으로)\n'
            ' ⑤치료 계획과 시작 시점(조건부, 지식표가 있으면 그 치료 방향을 따름; 선택지가 있으면 "~와 ~ 중 같이 정해요"처럼 공동 결정)\n'
            ' ⑥약 부작용 경고 또는 안전 수칙(운전·급중단 금지·추가 복용 금지 등 해당 시)\n'
            " ⑦경고 증상: 구체적 증상 4개 이상을 '·'로 이어 한 문장(예: '숨참·불규칙한 맥·고열·혼동 시 바로 오세요.')\n"
            " ⑧재진 시점과 다음 단계(예: '1~2주 뒤 결과 보고 약을 시작해요.') ⑨생활 수칙 1문장(예: 카페인·눈 관리·수면 습관).\n"
            " (문장이 10개 이상이면 ⑩오늘 내용 한 줄 요약, 예: '오늘은 검사하고, 결과 보고 치료를 정해요.')\n"
            " '더 궁금하신 점 있으세요?'는 쓰지 마세요(코드가 붙임). 요청이 있으면 그 결정을 SAY에 포함.\n"
            ' P에 적은 검사·재진 시점·경고 증상·안전 수칙은 SAY에서 반드시 말할 것. 소아면 보호자에게 말하듯.\n'
            '[FAQ] 환자가 물을 만한 질문에 대한 28자 이내 답(존댓말 평서문): prognosis(나을 수 있나/더 클 수 있나), '
            'serious(큰 병인가/위험한가), tests(무슨 검사·왜), treatment(약·기간·끊어도 되나), results(결과는 언제), '
            'lifestyle(생활에서 주의할 점), duration(치료 기간), prescribe(약을 처방해 주나, 해당 시).\n'
            '출력: {"tests": [{"name": "...", "reason": "..."}], "treatment": [...], "disposition": [...], "follow_up": [...],\n'
            ' "education": [...], "say": [...], "faq": {"prognosis": "...", ...}}')
    res = ask_json(enc.client, enc.budget, ROLE, user, effort=enc.cfg['EFFORT_PLAN_SAY'], max_tokens=8000,
                   tag='plan_say', want=dict, tries=2, max_wait=300,
                   validate=lambda v: isinstance(v.get('say'), list) and len(v['say']) >= 3)
    out = {'kb': k['id'] if k else None, 'fallback': False}
    if not res:
        out['fallback'] = True
        res = kb_fallback(enc, k)
    plan = {
        'tests': _list(res.get('tests')), 'treatment': _list(res.get('treatment')),
        'disposition': _list(res.get('disposition')), 'follow_up': _list(res.get('follow_up')),
        'education': _list(res.get('education')),
    }
    say = [nfc(str(s)).strip() for s in res.get('say') or [] if str(s).strip()]
    faq = dict((k or {}).get('faq') or {})  # 검증된 KB 답을 우선
    for kk, v in (res.get('faq') or {}).items():
        if isinstance(v, str) and str(kk) not in faq:
            faq[str(kk)] = nfc(v).strip()
    faq.setdefault('test_pain', '피 뽑을 때 잠깐 따끔하고 금방 끝나요.')
    faq = {kk: safe_say(v) for kk, v in faq.items() if v and not saymod.say_problem(v)}
    say = fix_say(enc, say, k)
    out.update({'plan': plan, 'say': say, 'faq': faq})
    return out


def kb_fallback(enc, k) -> dict:
    if k:
        return {'tests': [f'{a} : {b}' for a, b in k['tests']], 'treatment': list(k['treatment']),
                'disposition': list(k['disposition']), 'follow_up': list(k['follow_up']) + [f"즉시 내원 : {k['red_flags']}"],
                'education': list(k['education']), 'say': list(k['say']), 'faq': dict(k.get('faq') or {})}
    dx_short = re.sub(r'\(.*?\)', '', enc.dx or '').strip()
    say = [s.replace('{dx}', dx_short) for s in kbmod.GENERIC_SAY[:-1]]
    if saymod.say_problem(say[0]):
        say[0] = '말씀과 진찰로 원인이 짐작돼요.'
    return {'tests': ['기본 혈액검사(CBC, 전해질, 간·신장 기능, 혈당) : 전신 상태 평가', '주진단 확인을 위한 표적 검사 : 감별진단 배제'],
            'treatment': ['검사 결과 확인 후 원인에 맞는 치료 시작 고려', '금기 확인 후 증상 조절'],
            'disposition': ['급성 위험 징후 없어 외래 추적(입원 불필요)'],
            'follow_up': ['재진 : 1~2주 후 검사 결과 확인', '즉시 내원 : 증상 악화, 호흡곤란, 흉통, 의식 변화, 고열'],
            'education': ['진단 가능성과 검사 필요성', '경고 증상 시 즉시 내원'], 'say': say, 'faq': {}}


def fix_say(enc, say: list[str], k, max_lines=None) -> list[str]:
    checks = []
    bad_idx = [i for i, s in enumerate(say) if saymod.say_problem(s)]
    if bad_idx and enc.budget.can_call(enc.cfg['CALL_RESERVE']):
        bad = [say[i] for i in bad_idx]
        fix = ask_json(enc.client, enc.budget, '당신은 한국 외래 의사입니다. JSON 하나만 출력하세요.',
                       '다음 문장들을 뜻을 유지하며 각각 공백 포함 28자 이내의 쉬운 존댓말 평서문으로 다시 쓰세요. 띄어쓰기를 지키고 '
                       '영어 약어(MRI·CT 제외)·물음표·단정적 안심("걱정 안 해도", "완치", "확실히")·미루기("나중에 설명")는 쓰지 마세요. '
                       '같은 순서로 JSON {"say": [...]}.\n' + json.dumps(bad, ensure_ascii=False),
                       effort=enc.cfg['EFFORT_SAY_FIX'], max_tokens=4000, tag='say_fix', want=dict, tries=1,
                       reserve=enc.cfg['CALL_RESERVE'])
        fixed = [nfc(str(s)).strip() for s in ((fix or {}).get('say') or [])]
        for j, i in enumerate(bad_idx):
            new = fixed[j] if j < len(fixed) else ''
            checks.append({'orig': say[i], 'why': saymod.say_problem(say[i]), 'fixed': new})
            if new and not saymod.say_problem(new):
                say[i] = new
    kb_say = (k or {}).get('say') or []
    good = []
    for i, s in enumerate(say):
        if saymod.say_problem(s):
            checks.append({'drop': s, 'why': saymod.say_problem(s)})
            continue
        if is_similar(s, good, 0.6):
            checks.append({'drop_dup': s})
            continue
        good.append(s)
    # KB 안전 규칙: 금지 문장 제거, 필수 문장 삽입(경고 문장 앞)
    if k and k.get('ban_say'):
        dropped = [s for s in good if re.search(k['ban_say'], s)]
        good = [s for s in good if s not in dropped]
        if dropped:
            checks.append({'ban_say': dropped})
    fixed_safe = [safe_say(s) for s in good]
    if fixed_safe != good:
        checks.append({'safe_say': [(a, b) for a, b in zip(good, fixed_safe) if a != b]})
    good = _dedup_exact(fixed_safe)
    keep = []
    for pat, sent in (k or {}).get('must_say') or []:
        hit = next((s for s in good if re.search(pat, s)), None)
        if hit:
            keep.append(hit)
        else:
            pos = next((i for i, s in enumerate(good) if saymod.WARN_RE.search(s)), len(good))
            good.insert(pos, sent)
            keep.append(sent)
            checks.append({'must_say': sent})
    n = max_lines or enc.cfg['EXPLAIN_N']
    if max_lines:  # v8: 공감·걱정 근거 요소 보정(문장 수 불변 또는 +1, ensure_elements가 자리를 맞춤)
        good = saymod.ensure_v8(good, enc, keep=keep)
    final = saymod.ensure_elements(good, enc.dx or '', kb_say=[safe_say(s) for s in kb_say],
                                   red_flags_say=(k or {}).get('red_say', ''), max_lines=n, log=log, keep=keep)
    final = _dedup_exact([safe_say(s) for s in final])
    enc.say_keep = list(keep)
    enc.say_checks = checks + [{'missing_before': saymod.missing_elements(good, enc.dx or '')}]
    return final


def _faq_key(reply: str):
    for key, pat in FAQ_KEYS.items():
        if re.search(pat, reply):
            return key
    return None


def is_question(reply: str) -> bool:
    """환자 말에 질문이 들어 있나. v8c: '네, 알겠습니다. 다음 검사는 어떤 게 필요할까요?'처럼 수긍 뒤 질문도 질문(C10 턴27 무시 결함)."""
    r = nfc(reply or '').strip()
    if not r:
        return False
    if '?' in r:
        return True
    for s in re.split(r'(?<=[.!])\s+', r):
        if re.match(r'\s*(네|예)[,.]?\s*(알겠|감사|그럴게|그렇게)', s):
            continue
        if re.search(r'(까요|나요|건가요|는지요|어떻게|언제(?!든)|얼마나)', s):
            return True
    return False


# v7 C6-c: answer() 폴백 2순위(FAQ 값 → 주제별 기본 답 → 범용 문장). 모두 say_problem 통과(테스트)
TOPIC_FALLBACK = {'serious': '검사로 확인한 뒤 결과를 자세히 설명해요.',
                  'treatment': '검사 결과를 보고 치료 방법을 같이 정해요.',
                  'tests': '피검사 결과로 원인을 확인할 거예요.',
                  'results': '결과는 다음 진료 때 함께 봐요.',
                  'prognosis': '치료 반응을 보며 같이 관리해 갈게요.',
                  'duration': '경과를 보며 치료 기간을 같이 정해요.',
                  'lifestyle': '규칙적으로 자고 무리하지 않는 게 좋아요.'}
GENERIC_ANSWER = '오늘 계획대로 하며 같이 조절해 갈게요.'
# 답이 이미 한 말과 겹칠 때 쓰는 다른 범용 답(모두 say_problem 통과, 테스트)
GENERIC_ANSWERS = [GENERIC_ANSWER, '결과가 나오면 그에 맞춰 같이 정해요.', '궁금한 점은 언제든 다시 물어보세요.']
TEACH_BACK = '바로 오셔야 할 증상 하나를 말씀해 보세요.'   # v8c: 더 이상 말하지 않음(호환용 상수)


def _dup(s: str, said: list[str]) -> bool:
    return bool(s) and (s in said or is_similar(s, said, 0.6))


def answer(enc, reply: str, said: list[str], fallback: str = '', use_llm: bool = True) -> str:
    """환자 질문에 대한 직답 한 문장. LLM 답 → (FAQ) 폴백 → 주제별 기본 답 → 범용 답. 이미 한 말과 겹치면 다른 답. 모두 겹치면 ''."""
    a = ''
    if use_llm:
        try:
            a = _answer_llm(enc, reply, said)
        except Exception as exc:  # noqa: BLE001 — 답이 없으면 아래 폴백
            log(f'answer llm failed: {type(exc).__name__}: {exc}')
            a = ''
    if a and not saymod.say_problem(a) and a not in GENERIC_ANSWERS and not _dup(a, said):
        return a
    key = _faq_key(nfc(reply or ''))
    for cand in (fallback, TOPIC_FALLBACK.get(key, '') if key else ''):
        fb = safe_say(cand) if cand else ''
        if fb and not saymod.say_problem(fb) and not _dup(fb, said):
            return fb
    return next((g for g in GENERIC_ANSWERS if g not in said), '')


def _answer_llm(enc, reply: str, said: list[str]) -> str:
    p = getattr(enc, 'plan_v2', None) or {}
    tests = [str(x)[:60] for x in (p.get('tests') or [])[:5]]
    treat = [str(x)[:80] for x in (p.get('treatment') or [])[:3]]
    fu = [str(x)[:60] for x in (p.get('follow_up') or [])[:3]]
    res = ask(enc.client, enc.budget, '당신은 한국 외래 의사입니다. JSON 하나만 출력하세요.',
              f'환자의 질문(그대로): "{reply}"\n진단: {enc.dx}\n계획 — 검사(이름 : 목적): {tests}\n치료: {treat}\n추적·재진: {fu}\n'
              f'이미 한 설명(반복 금지): {said}\n'
              '환자에게 할 답 한 문장(공백 포함 28자 이내, 쉬운 존댓말 평서문, 물음표 금지). 첫마디부터 질문에 대한 직접 답을 하세요. '
              '예) 검사 질문 → "갑상샘 호르몬 피검사와 초음파로 원인을 확인해요.", 기간 질문 → "보통 1~2년 약을 드시며 조절해요.", '
              '예후 질문 → "치료하면 대개 체중도 회복돼요.", 다른 방법 질문 → "수면 습관 교정과 인지행동치료가 도움돼요.". '
              '계획에 있는 검사·치료·시점을 근거로 답하고, 미루기("나중에 설명")·계획과 모순·근거 없는 단정·약 용량 숫자·처방 확정 표현 금지. '
              '출력: {"answer": "..."}',
              effort=enc.cfg['EFFORT_ANSWER'], max_tokens=4000, tag='answer', want=dict, reserve=enc.cfg['CALL_RESERVE'])
    a = safe_say(nfc((res or {}).get('answer') or '').strip())
    if not a or saymod.say_problem(a):
        return ''
    return a


def explain_loop(enc, lines: list[str], faq: dict, quick=False):
    said = []
    answers = 0
    amax = 0 if quick else enc.cfg['ANSWER_MAX']
    used_faq = set()
    for i, line in enumerate(lines):
        if not enc.can_act():
            break
        entry = enc.act('SAY', line, phase='explain')
        if not entry or entry.get('refused'):
            continue
        said.append(line)
        enc.explained.append(line)
        reply = entry.get('reply') or ''
        rest = lines[i + 1:]
        if answers >= amax or not is_question(reply) or enc.turns_remaining <= len(rest) + 1:
            continue
        key = _faq_key(reply)
        ans = None
        if key and key in faq and key not in used_faq:
            # 곧 나올 문장이 같은 주제를 답하면 건너뜀
            if key == 'tests' and any(saymod.TEST_RE.search(s) for s in rest):
                continue
            if key == 'results' and any(saymod.FOLLOWUP_RE.search(s) for s in rest):
                continue
            ans = safe_say(faq[key])
            used_faq.add(key)
        elif key in ('tests', 'results') and any(
                (saymod.TEST_RE if key == 'tests' else saymod.FOLLOWUP_RE).search(s) for s in rest):
            continue
        else:
            ans = answer(enc, reply, said)
        if ans and ans not in said:
            e2 = enc.act('SAY', ans, phase='explain-answer')
            if e2 and not e2.get('refused'):
                said.append(ans)
                enc.explained.append(ans)
                answers += 1


def render_plan(enc, plan: dict, k) -> dict:
    """P 5칸 문자열. 용량 규칙(treatment만), 금지어·avoid 필터, 입원 필요/불필요, 즉시 내원 보장, 교육칸=발화."""
    from .record import COND_RE, GLOBAL_BAN_RE, PEDS_BAN_RE, education_text, strip_new_doses, vitals_assessment
    peds = bool(enc.profile.get('pediatric')) or (enc.profile.get('age') is not None and enc.profile['age'] < 15)
    avoid = (k or {}).get('avoid') or ''
    src = enc.opening + '\n' + '\n'.join(e.get('reply') or '' for e in enc.ledger)

    def keep(line):
        if GLOBAL_BAN_RE.search(line) or (peds and PEDS_BAN_RE.search(line)):
            log(f'P removed (ban): {line}')
            return False
        if avoid and re.search(avoid, line) and not NEGATION_RE.search(line):
            log(f'P removed (avoid): {line}')
            return False
        return True
    tests = [l for l in plan.get('tests') or [] if keep(l)]
    # 말로 설명한 검사가 P.tests에 없으면 보충(발화와 기록 일치)
    said = ' '.join(enc.explained or [])
    tests_txt = ' '.join(tests)
    for word, pat, line in (('심전도', r'심전도', '심전도 : 진료 중 설명한 검사(심박·리듬 확인)'),
                            ('초음파', r'초음파', '초음파 : 진료 중 설명한 검사'),
                            ('엑스레이', r'엑스레이|엑스선|X-?ray', '단순 방사선(X-ray) : 진료 중 설명한 검사'),
                            ('소변', r'소변\s*(약물)?\s*검사', '소변검사 : 진료 중 설명한 검사'),
                            ('MRI', r'MRI', 'MRI : 진료 중 설명한 검사')):
        if re.search(pat, said) and not re.search(pat, tests_txt, flags=re.I):
            kb_line = next((f'{a} : {b}' for a, b in ((k or {}).get('tests') or []) if re.search(pat, a, flags=re.I)),
                           None)
            tests.append(kb_line or line)
    treat = []
    llm_treat = plan.get('treatment') or []
    if k:
        # 안전: 진단 지식표가 맞으면 치료안은 검증된 템플릿(KB)을 쓰고, LLM 줄은 비약물·요청 결정·의뢰만 덧붙인다
        treat = list(k.get('treatment') or [])
        facts = getattr(enc, 'facts', None) or []
        if any(f['key'] == 'sh.smoking' and f['pol'] == '-' for f in facts):  # 비흡연자에게 금연 권고 줄 제거
            treat = [re.sub(r',?\s*(흡연자는\s*)?금연\s*권고(\([^)]*\))?', '', t).strip(' ,') for t in treat]
        # v2c: KB 진단이면 LLM 자유 서술 줄은 치료칸에 넣지 않는다(중복·처방 확정 서술 방지)
        llm_treat = []
    admit_if = (k or {}).get('admit_if', '')
    treat = [safe_plan_line(t, 'treatment', admit_if) for t in treat]
    llm_out = []
    for l in llm_treat:
        if not keep(l):
            continue
        new = strip_new_doses(l, src)
        if new != l.strip() and not COND_RE.search(new):
            new = '검사 결과 확인 후 ' + new.strip().rstrip('.') + ' 고려'
        new = safe_plan_line(re.sub(r'\s{2,}', ' ', new).strip(), 'treatment', admit_if)
        if new:
            llm_out.append(new)
    treat += dedup_lines(llm_out)[:2]
    if k and k.get('ban_treat'):
        treat = [t for t in treat if not re.search(k['ban_treat'], t)]
    for line in (k or {}).get('must_treat') or []:
        line = safe_plan_line(line, 'treatment', admit_if)
        if line not in treat:
            treat.insert(0, line)
    if any(re.search(r'(시작|처방|투여|복용)', t) for t in treat) and not any(
            re.search(r'(금기|알레르기|상호작용)', t) for t in treat):
        treat.append('새 약 시작 전 금기·약물 알레르기·상호작용 확인')
    treat = dedup_lines(treat)
    disp = list((k or {}).get('disposition') or plan.get('disposition') or [])
    va = vitals_assessment(enc).lstrip('- ')
    em = getattr(enc, 'urgency', None) or {}
    lv = em.get('level', 'routine')
    if lv == 'emergency':   # v14: '입원 불필요, 외래 추적' 대신 응급 의뢰 한 줄 + LLM 줄 중 외래·귀가 문구 제거
        rest = [d for d in disp if not re.search(r'외래\s*추적|입원\s*(은\s*)?(불필요|고려)|귀가|활력징후|경과\s*관찰', d)]
        disp = [urg.emergency_disposition(enc, em, vitals_assessment)] + rest
    elif '불안정' not in va and any(re.search(r'입원.{0,6}(필요|불필요|고려)', d) for d in disp):
        disp.insert(0, va.split(' → ')[0])
    else:
        disp.insert(0, va)
    if lv == 'urgent' and not any(re.search(r'(\d\s*~?\s*\d?\s*일\s*(내|이내|뒤|후)|이틀|사흘|당일|조기\s*재진|빠른\s*재진)', d) for d in disp):
        disp.append('급성 경과 → 2~3일 내 조기 재진으로 치료 반응·악화 여부 확인')
    disp = dedup_lines([safe_plan_line(d, 'disposition', admit_if) for d in disp])
    fu = list(plan.get('follow_up') or [])
    if lv == 'emergency':
        fu = [f for f in fu if not (re.search(r'재진|재방문|외래', f) and not re.search(r'응급', f))] + [urg.EMERG_FU]
    elif lv == 'urgent' and not any(re.search(r'\d\s*~?\s*\d?\s*일|당일|이틀|사흘', f) for f in fu if re.search(r'재진', f)):
        fu = [f for f in fu if not re.search(r'^\W*재진\s*:', f)] + [urg.URGENT_FU]
    if not any(re.search(r'(즉시|바로|응급)', f) for f in fu):
        fu.append(f"즉시 내원 : {(k or {}).get('red_flags') or '증상 악화, 호흡곤란, 흉통, 의식 변화, 고열'}")
    ec = (k or {}).get('early_contact')
    if ec and not any(re.search(ec[0], f) for f in fu):
        pos = next((i for i, f in enumerate(fu) if re.search(r'(즉시|바로|응급)', f)), len(fu))
        fu.insert(pos, ec[1])
    fu = dedup_lines([safe_plan_line(f, 'follow_up', admit_if) for f in fu])
    edu_plan = [safe_plan_line(e, 'education', admit_if) for e in (plan.get('education') or [])]
    edu = education_text(enc.explained, '\n'.join(e for e in edu_plan if e))

    def fmt(lst):
        return '\n'.join(f'- {x}' for x in lst if x)
    return {'tests': fmt(tests), 'treatment': fmt(treat), 'disposition': fmt(disp), 'follow_up': fmt(fu),
            'education': edu}


# ================================================================ v8 P4: 계획(P) 전용 호출(medium) + 설명 슬롯 호출(low)
def _context(enc) -> dict:
    prof = enc.profile
    facts = getattr(enc, 'facts', None) or []
    a = getattr(enc, 'assess', None) or {}
    from .record import vitals_assessment
    return {
        'sex': {'F': '여', 'M': '남'}.get(prof.get('sex'), '?'),
        'pos': [f"{f['label']}{(' ' + f['detail']) if f['detail'] else ''}" for f in facts if f['pol'] == '+'][:25],
        'neg': [f['label'] for f in facts if f['pol'] == '-'][:25],
        'abn': [f"{x['name']}: {x['result'][:50]}" for x in (a.get('exams') or [])],
        'ice': [f"{e['text']} → {e['reply']}" for e in enc.ledger
                if str(e.get('qid', '')).startswith('ice') and not e.get('refused')],
        'ddx': [d['dx'] for d in a.get('differential') or []] or enc.differentials[1:4],
        'va': vitals_assessment(enc),
    }


def plan_v8(enc, k) -> dict:
    """P 5칸 + FAQ. 모범 기록형: 검사(확진·감별 조건·기준치·안전), 조건부 치료·금기, 처치 근거, 추적 4유형."""
    prof = enc.profile
    c = _context(enc)
    gl = guidelines.hint_plan(enc)
    gl_rule = ('- [진료지침 발췌]는 검사·추적·경고 증상의 근거로만 쓰고 환자 사실에 맞는 것만 고를 것. 지식표와 충돌하면 지식표를 따를 것.\n'
               if gl else '')
    user = (f"환자: {prof.get('age')}세 {c['sex']}, 정보 제공자 {prof.get('informant')}, 주진단: {enc.dx}, 감별: {c['ddx']}\n"
            f"핵심 양성 사실: {c['pos']}\n핵심 음성 사실: {c['neg']}\n진찰 소견: {c['abn']}\n활력징후 판단: {c['va']}\n"
            f"환자 걱정·궁금증·요청(ICE): {c['ice']} / 요청: {prof.get('request') or '없음'}\n"
            f"참고 지식표(있으면, 환자에 맞게 취사선택): {json.dumps(kbmod.kb_hint(k), ensure_ascii=False) if k else '없음'}\n"
            f'{gl}'
            '[P 규칙]\n'
            f'{gl_rule}'
            '- tests: 4~7개 {"name","reason"}. 확진 검사, 감별진단마다 가르는 검사(예상 결과·시행 조건 포함, 예: "TRAb 음성이면 갑상샘 '
            '섭취율"), 치료 전 기준치(간·혈구 등), 안전(가임기 여성 β-hCG 등). 불필요·침습적 검사 금지.\n'
            "- treatment: 조건부('검사 확인 후 ~ 고려', '금기(문진에서 확인한 것 명시) 확인 후'). 약은 계열명만, 용량·횟수 숫자 금지. "
            '비약물 치료 포함. 요청이 있으면 결정과 이유 한 줄. 적응증 없는 약 금지.\n'
            "- disposition: 외래/의뢰/응급 + 근거(활력징후·위험 징후 유무), 입원 고려 기준 한 줄.\n"
            '- urgency: "emergency"(오늘 응급실·당일 수술/입원 평가가 표준: 급성 복막 징후·급성 관상동맥·대동맥·뇌혈관·수막염·'
            '자궁외임신·염전·케톤산증 등) | "urgent"(2~3일 내 재진·조기 외래 평가) | "routine"(1~2주 뒤 결과 확인). '
            '주진단과 놓치면 안 될 감별을 함께 보고 보수적으로.\n'
            "- follow_up: 4줄 형식 — '재진 : 기간과 확인할 것', '모니터링 : 치료 중 간격과 항목', '의뢰 기준 : 어떤 소견이면 어느 과', "
            "'즉시 내원 : 구체적 경고 증상(약 부작용 신호 포함)'.\n"
            '- education: 질환 설명, 검사 이유, 치료 선택지·기간, 생활 수칙, 경고 증상.\n'
            '[안전 체크 — 해당되는 것만]\n'
            '가임기 여성 임신 확인 / 진정제: 급중단 금지·운전 회피·병용 금지 / 항갑상샘제: 무과립구증(발열·인후통)·간독성(황달) / '
            '베타차단제: 천식·서맥 금기 / NSAIDs: 위장·신장 / 항생제: 알레르기 / 소아: 아스피린 금지 / 자살 위험: 안전 계획 / 노인: 낙상.\n'
            '[FAQ] 환자가 물을 만한 질문에 대한 28자 이내 답(존댓말 평서문, 질문의 핵심에 먼저 직접 답, 기간·예후는 일반적 범위로): '
            'prognosis, serious, tests, treatment, results, lifestyle, duration, prescribe(해당 시).\n'
            '출력: {"tests": [{"name": "...", "reason": "..."}], "treatment": [...], "disposition": [...], "follow_up": [...],\n'
            ' "education": [...], "urgency": "emergency|urgent|routine", "faq": {"prognosis": "...", ...}}')
    res = ask_json(enc.client, enc.budget, ROLE, user, effort=enc.cfg.get('EFFORT_PLAN_P', 'medium'), max_tokens=8000,
                   tag='plan_p', want=dict, tries=2, max_wait=300,
                   validate=lambda v: isinstance(v.get('tests'), list) and len(v['tests']) >= 1)
    return res if isinstance(res, dict) else {}


SAY_SLOTS = [
    ('dx', "공감 3~6자 + 쉬운 병명 + 가능성 표현(예: '많이 걱정되셨죠, 그레이브스병 가능성이 높아요.'). '진단합니다' 금지"),
    ('mech', "원인·기전을 쉬운 말로, 환자가 말한 증상 2개와 '~로/~때문에/~해서'로 연결(예: '면역 이상으로 호르몬이 넘쳐 살 빠지고 "
             "떨려요.'). 소견 나열·'정상이에요' 금지"),
    ('worry', "환자가 말한 걱정(ICE)에 문진·진찰 근거 1~2개로 직접 답(예: '목·눈 소견이 뚜렷해 암보다 갑상샘 병 같아요.'). 걱정이 "
              "없으면 중증도 판단과 근거. 단정·거짓 안심 금지"),
    ('tests', "검사 이름 + 목적(무엇을 확인하려는지) + 결과 볼 시점(예: '피검사·초음파로 원인 확인하고 2주 뒤 봐요.')"),
    ('treat', "치료 선택지와 기간(예: '베타차단제로 두근거림 줄이고 약은 1~2년 써요.'). 계열명 가능, 용량 숫자·"
              "'처방해 드려요'·'나중에 정해요' 같은 미루기 금지"),
    ('warn', "경고 증상 4개 이상을 '·'로 + 약 부작용 신호 1개 이상 + '바로 오세요'(예: '열·목 아픔·숨참·심한 두근거림 땐 바로 오세요.')"),
    ('life', "재진 시점 + 생활·안전 수칙 1개(예: '2주 뒤 오시고 커피는 줄여 주세요.')"),
]


SAY_SLOTS_BASE = list(SAY_SLOTS)
# v11a: 소통 감점 문구(기전-증상 연결 부족, 치료 과정 설명 부족, 호소 증상 관리법 미설명)를 겨냥한 슬롯 설명
SAY_SLOTS_V11_DESC = {
    'mech': "원인을 쉬운 말로 말하고 환자가 직접 말한 증상 2~3개를 그 원인에 연결(예: '호르몬이 넘쳐 살 빠지고 땀 나고 떨려요.'). "
            "소견 나열·'정상이에요' 금지",
    'treat': "치료 방법(계열명)과 진행 방식·기간을 함께(예: '호르몬 낮추는 약을 먹으며 피검사로 1~2년 조절해요.'). 용량 숫자·"
             "'처방해 드려요'·'나중에 정해요' 금지",
    'life': "환자가 호소한 증상 하나의 집에서 관리법 + 재진 시점(예: '눈이 뻑뻑하면 인공눈물 쓰고 2주 뒤 오세요.')",
}


def apply_v11(on: bool) -> None:
    global SAY_SLOTS
    if on:
        SAY_SLOTS = [(k, SAY_SLOTS_V11_DESC.get(k, d)) for k, d in SAY_SLOTS_BASE]
    else:
        SAY_SLOTS = list(SAY_SLOTS_BASE)


# v13: 설명 5문장(+질문 1 + 답 1 = 7턴)으로 줄일 때도 치료 줄을 지킨다. 걱정 질환이 있으면 걱정 직답, 없으면 기전.
SLOT5_V13 = False
# 치료 줄에 예후 문구('좋아져요')를 넣어, 설명 중 '치료하면 좋아질까요?' 질문을 이 줄을 당겨 답한다(답 턴 0)
TREAT_V13_DESC = ("치료 방법(계열명)·기간 + 좋아지는 경과를 한 문장으로(예: '호르몬 낮추는 약으로 1~2년 조절하면 대부분 좋아져요.'). "
                  "용량 숫자·'처방해 드려요'·'나중에 정해요' 금지")


def apply_v13(on: bool) -> None:
    global SLOT5_V13
    SLOT5_V13 = bool(on)


def say_slots(n: int, worry: bool = False) -> list[tuple[str, str]]:
    """n문장 슬롯(말하는 순서): 5=진단·기전·걱정·검사·경고, 6=+치료(6 핵심), 7=+재진·생활.
    v13(SLOT5_V13) 5문장 = 진단·(걱정|기전)·검사(+재진 시점)·치료·경고."""
    if SLOT5_V13 and n == 5:
        keys = ['dx', 'worry' if worry else 'mech', 'tests', 'treat', 'warn']
        return [(k, TREAT_V13_DESC) if k == 'treat' else s for k in keys for s in SAY_SLOTS if s[0] == k]
    if n <= 3:
        keys = ['dx', 'tests', 'warn']
    elif n == 4:
        keys = ['dx', 'worry', 'tests', 'warn']
    elif n == 5:
        keys = ['dx', 'mech', 'worry', 'tests', 'warn']
    else:   # 6 = +치료 선택지·기간(소통 감점 1위), 7 = +재진·생활
        keys = ['dx', 'mech', 'worry', 'tests', 'treat', 'warn'] + (['life'] if n >= 7 else [])
    return [s for s in SAY_SLOTS if s[0] in keys]


def say_v8(enc, plan: dict, n: int, k) -> list[str]:
    c = _context(enc)
    slots = say_slots(n, bool(_worry_word(enc)))
    p = {kk: _list(plan.get(kk))[:5] for kk in ('tests', 'treatment', 'follow_up')}
    must = [s for _, s in (k or {}).get('must_say') or []]
    kb_t = ''
    if k:
        dur = ((k.get('faq') or {}).get('duration') or '').strip()
        kb_t = (f"치료 참고(지식표): {[str(t)[:70] for t in (k.get('treatment') or [])[:3]]}"
                + (f" / 기간: {dur}" if dur else '') + '\n')
    lv = urg.level(enc)
    urg_txt = {'emergency': '긴급도: 응급 — 검사 줄은 오늘 바로 응급실 안내, 치료 줄은 응급실 평가 뒤 결정됨을 알림. 재진 주 단위 금지\n',
               'urgent': '긴급도: 급성 — 재진은 2~3일 뒤, 악화 시 당일 내원\n'}.get(lv, '')
    user = (f"환자: {enc.profile.get('age')}세 {c['sex']}, 정보 제공자 {enc.profile.get('informant')}, 주진단: {enc.dx}\n"
            f"환자가 말한 양성 증상: {c['pos'][:12]}\n진찰 이상 소견: {c['abn'][:8]}\n환자 걱정(ICE): {c['ice']}\n"
            + urg_txt
            + f"계획 요약: 검사 {p['tests']} / 치료 {p['treatment']} / 추적 {p['follow_up']}\n"
            + kb_t
            + (f"반드시 포함할 안전 문장(그대로 쓰기): {must}\n" if must else '')
            + f'[SAY 규칙] 정확히 {len(slots)}문장, 각 공백 포함 28자 이내, 쉬운 존댓말 평서문 한 문장(물음표 금지), 영어 약어 금지(MRI·CT만), '
            "띄어쓰기 정확(조사는 앞말에 붙여 쓰기), 한 문장에 정보 두 개. 단정·보장 금지('걱정 안 해도', '완치', '확실히'). "
            "전문용어 대신 쉬운 말(예: '호르몬을 낮추는 약'). 소아면 보호자에게 말하듯.\n"
            '순서와 슬롯:\n' + '\n'.join(f'{i + 1}. [{key}] {desc}' for i, (key, desc) in enumerate(slots))
            + '\n출력: {"say": ["...", ...]}')
    res = ask_json(enc.client, enc.budget, ROLE, user, effort=enc.cfg.get('EFFORT_PLAN_SAY', 'low'), max_tokens=6000,
                   tag='say_v8', want=dict, tries=2, max_wait=200,
                   validate=lambda v: isinstance(v.get('say'), list) and len(v['say']) >= 3)
    return [nfc(str(s)).strip() for s in ((res or {}).get('say') or []) if str(s).strip()]


# ---------------------------------------------------------------- v8c: 슬롯 문장 품질 게이트 + 결정적 템플릿 폴백
SUMMARY_LINE = '오늘은 검사하고, 결과 보고 치료를 정해요.'
_TEST_WORDS = [(r'(TSH|T4|T3|CBC|혈액|피검사|간기능|간\s*기능|신기능|혈당|HbA1c|당화|IGF|전해질|hCG|TFT|TRAb|항체|페리틴|철|'
                r'ESR|CRP|지질|BUN|AST|ALT|β)', '피검사'),
               (r'초음파', '초음파'), (r'(심전도|ECG|EKG)', '심전도'),
               (r'(X-?ray|엑스레이|엑스선|골연령|뼈\s*나이)', '엑스레이'), (r'소변', '소변검사'), (r'MRI', 'MRI'),
               (r'(?<![A-Za-z])CT(?![A-Za-z])', 'CT')]


def _dx_names(enc) -> tuple[str, str]:
    """(원인 병명, 상태명): '그레이브스병에 의한 갑상샘항진증 (Graves)' → ('그레이브스병', '갑상샘항진증')."""
    raw = re.sub(r'\(.*?\)', '', nfc(getattr(enc, 'dx', '') or '')).strip()
    parts = [p.strip() for p in re.split(r'에\s*의한|으로\s*인한', raw) if p.strip()]
    if not parts:
        return raw, raw
    return parts[0], parts[-1]


def _followup_phrase(enc, k, plan) -> str:
    lv = urg.level(enc)
    if lv == 'urgent':   # v14: 급성 질환은 2~3일 내 재진(LLM 계획이 더 짧게 잡았으면 그대로)
        for s in list(plan.get('follow_up') or []):
            m = re.search(r'(\d+\s*(?:~\s*\d+\s*)?일)\s*(?:뒤|후|안에|내|쯤)', nfc(str(s)))
            if m:
                return re.sub(r'\s+', '', m.group(1)) + ' 뒤'
        return '2~3일 뒤'
    src = list(plan.get('follow_up') or []) + list((k or {}).get('follow_up') or []) + list((k or {}).get('say') or [])
    for s in src:
        m = re.search(r'(\d+\s*(?:~\s*\d+\s*)?(?:일|주|개월|달))\s*(?:뒤|후|안에|내|쯤)', nfc(str(s)))
        if m:
            return re.sub(r'\s+', '', m.group(1)) + ' 뒤'
    return '1~2주 뒤'


def _test_words(text_src: str) -> list[str]:
    out = []
    for pat, w in _TEST_WORDS:
        if re.search(pat, text_src, flags=re.I) and w not in out:
            out.append(w)
    return out


def _pos_symptoms(enc) -> list[str]:
    out = []
    for f in getattr(enc, 'facts', None) or []:
        try:
            if f.get('pol') != '+':
                continue
            lab = re.sub(r'\(.*?\)', '', nfc(str(f.get('label') or ''))).strip()
        except AttributeError:
            continue
        if lab and len(lab) <= 6 and not re.search(r'[A-Za-z]', lab) and lab not in out:
            out.append(lab)
    return out


def _worry_word(enc) -> str:
    m = saymod.WORRY_WORD_RE.search(saymod._ice_text(enc))
    return re.sub(r'\s+', ' ', m.group(1)).strip() if m else ''


def _tests_line(enc, k, plan, base: str = '') -> list[str]:
    src = ' '.join([base] + [str(t) for t in plan.get('tests') or []] + [a for a, _ in (k or {}).get('tests') or []])
    words = _test_words(src) or ['피검사']
    fu = _followup_phrase(enc, k, plan)
    cands = []
    for n in (3, 2, 1):
        w = '·'.join(words[:n])
        cands += [f'{w}로 원인을 확인하고 {fu} 결과 봐요.', f'{w}로 확인하고 {fu} 결과 봐요.']
    return cands


def slot_candidates(slot: str, enc, k, plan) -> list[str]:
    """슬롯별 결정적 폴백 후보(앞일수록 우선). 호출자가 say_problem·slot_problem으로 거른다."""
    name, short = _dx_names(enc)
    kb_say = [safe_say(s) for s in (k or {}).get('say') or []]
    faq = (k or {}).get('faq') or {}
    fu = _followup_phrase(enc, k, plan)
    if slot == 'dx':
        return ([f'{e}{nm} 가능성이 높아요.' for nm in (name, short) for e in ('많이 걱정되셨죠, ', '걱정되셨죠, ', '')]
                + [s for s in kb_say if not saymod.TEST_RE.search(s)])
    if slot == 'mech':
        sy = _pos_symptoms(enc)
        out = []
        if len(sy) >= 2:
            out += [f'{nm} 때문에 {sy[0]}·{sy[1]} 증상이 생겨요.' for nm in (short, name)]
        if sy:
            out += [f'{nm} 때문에 {sy[0]} 증상이 생겨요.' for nm in (short, name)]
        return out + kb_say + [f'{short} 때문에 지금 증상이 생긴 거예요.', f'{name} 때문에 생긴 증상으로 보여요.']
    if slot == 'worry':
        w = _worry_word(enc)
        out = []
        if w:
            out += [f'걱정하신 {w}보다 {nm} 가능성이 높아요.' for nm in (name, short)] + [f'걱정하신 {w}도 검사로 함께 확인해요.']
        out += [faq.get('serious', '')] + kb_say
        return out + [f'진찰 소견상 {short} 가능성이 가장 높아요.', '진찰 소견상 큰 병 가능성은 낮아 보여요.']
    if slot == 'tests':
        if urg.level(enc) == 'emergency':
            return [urg.EMERG_SAY, urg.EMERG_SAY_SHORT]
        good = [s for s in kb_say if saymod.FOLLOWUP_RE.search(s) and saymod.TEST_RE.search(s)]
        return good + _tests_line(enc, k, plan) + [s for s in kb_say if saymod.TEST_RE.search(s)]
    if slot == 'treat':
        out = [faq.get('duration', ''), faq.get('treatment', '')]
        out += [s for s in kb_say if not saymod.TEST_RE.search(s) and not saymod.WARN_RE.search(s)
                and re.search(r'(약|치료|수술|요법|상담|줄여)', s) and not saymod.CAUSAL_RE.search(s)
                and not re.search(r'(상태|같아요|보여요|병이에요)', s)]
        return out + [TOPIC_FALLBACK['treatment'], SAFE_SAY]
    if slot == 'warn':
        return [safe_say((k or {}).get('red_say') or '')] + [s for s in kb_say if saymod.WARN_RE.search(s)] + [saymod.GENERIC_WARN]
    if slot == 'life':
        lf = [s for s in [faq.get('lifestyle', '')] + kb_say
              if s and not saymod.TEST_RE.search(s) and not saymod.WARN_RE.search(s) and saymod.LIFE_RE.search(s)
              and not re.search(r'(상태|같아요|보여요|병이에요)', s)]
        out = [f'{fu} 오시고, {s}' for s in lf] + lf
        return out + [f'{fu} 다시 오시고 무리하지 마세요.', TOPIC_FALLBACK['lifestyle'], saymod.GENERIC_FOLLOW]
    return []


def _slot_fix_llm(enc, bad: list[tuple[str, str]], checks: list) -> list[str]:
    """실패 슬롯 문장 1회 고쳐 쓰기(기존 say_fix 패턴 + 슬롯 지시)."""
    if not bad or not enc.budget.can_call(enc.cfg['CALL_RESERVE']):
        return []
    desc = dict(SAY_SLOTS)
    items = [{'slot': s, 'rule': desc.get(s, ''), 'text': t} for s, t in bad]
    fix = ask_json(enc.client, enc.budget, '당신은 한국 외래 의사입니다. JSON 하나만 출력하세요.',
                   f'진단: {enc.dx}\n다음 설명 문장들을 각 슬롯 규칙에 맞게 고쳐 쓰세요. 각각 공백 포함 28자 이내의 쉬운 존댓말 평서문, '
                   '띄어쓰기 정확(조사는 앞말에 붙임), 영어 약어(MRI·CT 제외)·물음표·단정적 안심("걱정 안 해도", "완치", "확실히")·'
                   '미루기("나중에 설명")·용량 숫자 금지. 같은 순서로 JSON {"say": [...]}.\n'
                   + json.dumps(items, ensure_ascii=False),
                   effort=enc.cfg['EFFORT_SAY_FIX'], max_tokens=4000, tag='say_fix', want=dict, tries=1,
                   reserve=enc.cfg['CALL_RESERVE'])
    return [nfc(str(s)).strip() for s in ((fix or {}).get('say') or [])]


def build_slot_lines(enc, raw: list[str], keys: list[str], k, plan, checks=None) -> list[tuple[str, str, bool]]:
    """LLM 슬롯 문장 → 게이트(say_problem+slot_problem+금지+중복) → 1회 고쳐 쓰기 → 템플릿 폴백.
    반환: [(slot, text, keep)] (말하는 순서). keep=KB 필수 문장(+50 우선순위)."""
    checks = checks if checks is not None else []
    ban = (k or {}).get('ban_say')

    def clean(s):
        return saymod.tidy(safe_say(nfc(str(s or '')).strip()))

    def problem(slot, s, prev):
        if not s:
            return 'empty'
        if ban and re.search(ban, s):
            return 'ban'
        p = saymod.slot_problem(slot, s, enc)
        if p:
            return p
        if slot == 'treat' and s == SAFE_SAY:
            return 'treat_vague'   # 안전 치환 문장은 치료 선택지·기간이 없다 → KB 기간·선택지 우선
        return 'dup' if is_similar(s, prev, 0.6) else ''

    cand = {key: clean(raw[i]) if i < len(raw) else '' for i, key in enumerate(keys)}
    bad = [key for i, key in enumerate(keys) if problem(key, cand[key], [cand[x] for x in keys[:i] if cand[x]])]
    if bad:
        fixed = _slot_fix_llm(enc, [(key, cand[key]) for key in bad], checks)
        for j, key in enumerate(bad):
            new = clean(fixed[j]) if j < len(fixed) else ''
            i = keys.index(key)
            why = problem(key, cand[key], [cand[x] for x in keys[:i] if cand[x]])
            if new and not problem(key, new, [cand[x] for x in keys if x != key and cand[x]]):
                checks.append({'slot': key, 'orig': cand[key], 'why': why, 'fixed': new})
                cand[key] = new
                continue
            prev = [cand[x] for x in keys if x != key and cand[x] and x not in bad[j:]]
            tpl = [clean(c) for c in slot_candidates(key, enc, k, plan) if c]
            pick = next((c for c in tpl if not problem(key, c, prev)), None) or \
                next((c for c in tpl if c and not saymod.say_problem(c) and not is_similar(c, prev, 0.6)), '')
            checks.append({'slot': key, 'orig': cand[key], 'why': why, 'template': pick})
            cand[key] = pick
    entries = [[key, cand[key], False] for key in keys if cand[key]]

    # KB 필수 문장: 이미 맞는 줄이 있으면 그 줄을 keep, 없으면 맞는 슬롯 줄을 대체(빈 슬롯 우선), 그래도 없으면 치료 뒤에 덧붙임
    order = ['treat', 'life', 'warn', 'tests', 'worry', 'mech']
    for pat, sent in (k or {}).get('must_say') or []:
        hit = next((e for e in entries if re.search(pat, e[1])), None)
        if hit:
            hit[2] = True
            continue
        s = clean(sent)
        if saymod.say_problem(s):
            continue
        slot = next((sl for sl in order if any(e[0] == sl and not e[2] for e in entries)
                     and not saymod.slot_problem(sl, s, enc)), None)
        if slot:
            e = next(e for e in entries if e[0] == slot and not e[2])
            checks.append({'must_say': s, 'replaces': e[1]})
            e[1], e[2] = s, True
        else:
            if SLOT5_V13 and len(entries) >= 5:
                checks.append({'must_say_skipped_v13': s})   # v13: 설명 5줄 상한(중간 질문에 답할 턴을 남긴다)
                continue
            sl = saymod.guess_slot(s, enc.dx or '')
            pos = next((i for i, e in enumerate(entries) if e[0] == 'warn'), len(entries))
            entries.insert(pos, [sl, s, True])
            checks.append({'must_say': s, 'added_as': sl})

    # v14 응급: 검사 줄 = 응급실 안내(필수), 재진 '…주 뒤' 문구가 든 다른 줄은 제거
    if urg.level(enc) == 'emergency':
        if not any('응급실' in e[1] for e in entries):
            e = next((e for e in entries if e[0] == 'tests'), None)
            if e is not None:
                checks.append({'emergency_tests': urg.EMERG_SAY, 'replaces': e[1]})
                e[1], e[2] = urg.EMERG_SAY, True
            else:
                entries.insert(min(2, len(entries)), ['tests', urg.EMERG_SAY, True])
        for e in entries:
            if '응급실' in e[1]:
                e[2] = True
        entries = [e for e in entries if not (saymod.FOLLOWUP_RE.search(e[1]) and '응급' not in e[1])]
    if urg.level(enc) == 'urgent':   # v14 급성: LLM 줄의 '…주 뒤' 재진을 2~3일 뒤로
        for e in entries:
            if re.search(r'\d+\s*(?:~\s*\d+\s*)?(?:주|개월|달)\s*(?:뒤|후|안에|내)', e[1]):
                new = re.sub(r'\d+\s*(?:~\s*\d+\s*)?(?:주|개월|달)\s*(?:뒤|후|안에|내)', '2~3일 뒤', e[1])
                if len(nfc(new)) <= 30 and not saymod.say_problem(new):
                    checks.append({'urgent_followup': new, 'replaces': e[1]})
                    e[1] = new
    # 공감(진단 줄) + 환자가 말한 걱정 질환 직답(걱정 줄)
    for e in entries:
        if e[0] == 'dx' and not saymod.EMPATHY_RE.search(e[1]):
            for pre in ('많이 걱정되셨죠, ', '걱정되셨죠, '):
                if not saymod.say_problem(pre + e[1]):
                    e[1] = pre + e[1]
                    break
    w = _worry_word(enc)
    if w and not any(w in e[1] or '걱정하신' in e[1] for e in entries):
        e = next((e for e in entries if e[0] == 'worry' and not e[2]), None)
        if e is not None:
            prev = [x[1] for x in entries if x is not e]
            c = next((c for c in (clean(x) for x in slot_candidates('worry', enc, k, plan)[:3])
                      if c and w in c and not problem('worry', c, prev)), None)
            if c:
                checks.append({'worry_ice': c, 'replaces': e[1]})
                e[1] = c

    # 재진 시점: 어느 줄에도 없으면 검사 줄에 넣는다(생활 줄은 먼저 빠질 수 있음). 응급이면 재진 대신 응급실 안내
    if urg.level(enc) != 'emergency' and not any(saymod.FOLLOWUP_RE.search(e[1]) for e in entries):
        e = next((e for e in entries if e[0] == 'tests'), None)
        if e is not None:
            prev = [x[1] for x in entries if x is not e]
            c = next((c for c in (clean(x) for x in _tests_line(enc, k, plan, e[1]))
                      if not problem('tests', c, prev)), None)
            if c:
                checks.append({'followup_into_tests': c, 'replaces': e[1]})
                e[1] = c
    out, seen = [], set()
    for sl, t, kp in entries:
        if t and t not in seen:
            seen.add(t)
            out.append((sl, t, kp))
    return out


def plan_and_say_v8(enc) -> dict:
    k = kbmod.match_kb(enc.dx or '')
    enc.kb = k
    avail = enc.turns_remaining
    # 문장 n + Q 1 + 마지막 답 1 = 남은 턴. 중간 질문이 오면 explain_loop_v8이 저우선 슬롯 줄을 빼고 답한다.
    n = max(3, min(int(enc.cfg.get('EXPLAIN_MAX_LINES', 7)), avail - 2))
    res = plan_v8(enc, k)
    out = {'kb': k['id'] if k else None, 'fallback': False}
    if not res:
        out['fallback'] = True
        res = kb_fallback(enc, k)
    plan = {kk: _list(res.get(kk)) for kk in ('tests', 'treatment', 'disposition', 'follow_up', 'education')}
    urg.assess(enc, k, res)
    keys = [kk for kk, _ in say_slots(n, bool(_worry_word(enc)))]
    raw = say_v8(enc, plan, n, k)
    if len(raw) < 3:
        raw = []   # 슬롯별 템플릿(KB·진단·양성 사실)으로 채운다
    faq = dict((k or {}).get('faq') or {})
    for kk, v in (res.get('faq') or {}).items():
        if isinstance(v, str) and str(kk) not in faq:
            faq[str(kk)] = nfc(v).strip()
    faq.setdefault('test_pain', '피 뽑을 때 잠깐 따끔하고 금방 끝나요.')
    faq = {kk: safe_say(v) for kk, v in faq.items() if v and not saymod.say_problem(v)}
    checks = []
    entries = build_slot_lines(enc, raw, keys, k, plan, checks)
    say = [t for _, t, _ in entries] + [saymod.QUESTION_LINE]
    slots = [s for s, _, _ in entries] + ['q']
    enc.say_slot_of = {t: s for s, t, _ in entries}
    enc.say_keep = [t for _, t, kp in entries if kp]
    # 여분 턴용 추가 문장(KB, 슬롯 줄과 겹치지 않는 것)
    extras = []
    for s in (k or {}).get('say') or []:
        s2 = saymod.tidy(safe_say(s))
        if s2 and not saymod.say_problem(s2) and not is_similar(s2, say + extras, 0.6) and \
                not ((k or {}).get('ban_say') and re.search(k['ban_say'], s2)):
            extras.append(s2)
    enc.say_extras = extras
    enc.say_checks = checks + [{'missing_after': saymod.missing_elements(say[:-1], enc.dx or '')}]
    out.update({'plan': plan, 'say': say, 'slots': slots, 'faq': faq})
    return out


def _trim_priority(s: str, slot: str = '', dx_ko: str = '') -> int:
    """설명 줄이기 우선순위(작을수록 먼저 뺌): life 10 < mech 20 < worry 30 < treat 60 < tests 70 < warn 90 < dx 100."""
    if s == saymod.QUESTION_LINE:
        return 999
    return saymod.SLOT_PRIO.get(slot or saymod.guess_slot(s, dx_ko), 10)


def fit_lines(lines: list[str], avail: int, keep=None, slots=None, dx_ko: str = '') -> list[str]:
    """설명 문장(+Q 줄) + 마지막 답 1턴이 남은 턴 안에 들도록 슬롯 우선순위가 낮은 줄부터 뺀다(KB 필수 줄 +50)."""
    out = list(lines)
    sl = list(slots) if slots and len(slots) == len(lines) else [''] * len(lines)
    keep = set(keep or [])
    while len(out) + 1 > avail and len(out) > 2:
        cands = [(i, _trim_priority(s, sl[i], dx_ko) + (50 if s in keep else 0)) for i, s in enumerate(out) if i > 0]
        i = min(cands, key=lambda t: (t[1], -t[0]))[0]
        out.pop(i)
        sl.pop(i)
    return out


def _pull_index(items: list[dict], reply: str):
    """환자 질문을 곧 나올 슬롯 줄이 답하면 그 줄 위치(없으면 None). 검사·결과 → 검사/생활 줄, 치료·기간 → 치료 줄, 중증도·예후 → 걱정 줄."""
    key = _faq_key(nfc(reply or ''))
    for i, it in enumerate(items):
        s, t = it['slot'], it['text']
        if key == 'tests' and (s == 'tests' or (s == 'life' and saymod.TEST_RE.search(t))):
            return i
        if key == 'results' and s in ('tests', 'life') and saymod.FOLLOWUP_RE.search(t):
            return i
        if key in ('treatment', 'duration', 'prescribe') and s == 'treat':
            return i
        if key == 'serious' and s == 'worry':
            return i
        if key == 'prognosis' and s in ('worry', 'treat') and re.search(r'(좋아|회복|낫|나아|자라|돌아|대부분|대개)', t):
            return i
        if key == 'lifestyle' and s == 'life' and saymod.LIFE_RE.search(t):
            return i
    return None


def explain_loop_v8(enc, lines: list[str], faq: dict, quick=False):
    """v8c 설명 루프(명시적 턴 회계, 되말하기 없음).
    - 내용 줄을 말하기 전 불변식: 남은 턴 ≥ 남은 내용 줄 + Q 줄 1 + 마지막 답 1. 어기면 최저 우선순위 줄을 뺀다.
    - 내용 줄 뒤 환자 질문: 뒤 슬롯 줄이 답하면 당겨 말하고(추가 턴 없음), 아니면 바로 다음 턴에 답한다(처음 2개는 줄을 빼서라도).
    - Q 줄 뒤 질문은 항상 답하고 그 답으로 끝낸다. 질문이 없으면 남는 턴을 spare_exam → 빠진 설명 줄 → KB 추가 문장에 쓴다."""
    dx_ko = enc.dx or ''
    slot_of = dict(getattr(enc, 'say_slot_of', None) or {})
    keep = set(getattr(enc, 'say_keep', None) or [])
    items: list[dict] = []
    for t in lines:
        if not t or t == saymod.QUESTION_LINE or any(t == it['text'] for it in items):
            continue
        sl = slot_of.get(t) or saymod.guess_slot(t, dx_ko)
        boost = 40 if (SLOT5_V13 and sl == 'worry') else 0   # v13: 기전 줄 대신 들어간 걱정 직답 줄은 치료 줄 다음까지 지킨다
        items.append({'text': t, 'slot': sl, 'prio': saymod.SLOT_PRIO.get(sl, 10) + boost + (50 if t in keep else 0)})
    said: list[str] = []
    dropped: list[dict] = []
    st = {'mid': 0}
    used_faq: set = set()
    use_llm = not quick

    def say(text, phase):
        t = saymod.tidy(text)
        e = enc.act('SAY', t, phase=phase)
        if e is not None and not e.get('refused'):
            said.append(t)
            enc.explained.append(t)
        return e

    def eff_prio(i):
        it = items[i]
        p = it['prio']
        if saymod.FOLLOWUP_RE.search(it['text']) and not any(
                saymod.FOLLOWUP_RE.search(x) for x in said + [o['text'] for j, o in enumerate(items) if j != i]):
            p += 50   # 유일한 재진 시점 줄은 늦게 뺀다
        return p

    def drop_one(protect=999) -> bool:
        cands = [i for i in range(len(items)) if eff_prio(i) < protect]
        if not cands:
            return False
        i = min(cands, key=lambda j: (eff_prio(j), -j))
        it = items.pop(i)
        dropped.append(it)
        log(f'explain: drop [{it["slot"]}] "{it["text"]}"')
        return True

    def fit(extra=0, protect=999) -> bool:
        while items and enc.turns_remaining < len(items) + 2 + extra:
            if not drop_one(protect):
                break
        return enc.turns_remaining >= len(items) + 2 + extra

    def compose(reply) -> str:
        key = _faq_key(nfc(reply or ''))
        if key and key in faq and key not in used_faq:
            c = safe_say(faq[key])
            if c and not saymod.say_problem(c) and not _dup(c, said):
                used_faq.add(key)
                return c
        return answer(enc, reply, said, faq.get(key, '') if key else '', use_llm=use_llm)

    def handle_mid(reply):
        """내용 줄(또는 중간 답) 뒤 환자 질문."""
        while is_question(reply) and enc.can_act():
            j = _pull_index(items, reply)
            if j is not None:
                if j:
                    items.insert(0, items.pop(j))
                log(f'explain: pull [{items[0]["slot"]}] to answer "{reply}"')
                return
            if st['mid'] < 2:
                fit(1, protect=90)   # 처음 2개 중간 질문은 저우선 줄을 빼서라도 답한다(경고·진단 줄은 지킨다)
            if enc.turns_remaining < len(items) + 3:
                log(f'explain: no turn to answer mid question "{reply}"')
                return
            ans = compose(reply)
            if not ans:
                return
            e = say(ans, 'explain-answer')
            if not e or e.get('refused'):
                return
            st['mid'] += 1
            reply = e.get('reply') or ''

    def best_dropped():
        if not dropped:
            return None
        i = max(range(len(dropped)), key=lambda j: (dropped[j]['prio'], -j))
        return dropped.pop(i)

    # 1) 내용 줄
    while items and enc.can_act():
        fit(0)
        if not items:
            break
        it = items.pop(0)
        e = say(it['text'], 'explain')
        if e is None:
            break
        if e.get('refused'):
            continue
        handle_mid(e.get('reply') or '')
    # 2) 여유 턴이 있으면 빠진 줄을 Q 줄 앞에서 마저 말한다(Q 1 + 마지막 답 1은 남김)
    while dropped and enc.can_act() and enc.turns_remaining >= 3:
        it = best_dropped()
        e = say(it['text'], 'explain')
        if e is None:
            break
        if not e.get('refused'):
            handle_mid(e.get('reply') or '')
    if not enc.can_act():
        return
    if enc.turns_remaining < 2 and dropped:
        say(best_dropped()['text'], 'explain')   # 1턴뿐이면 묻고 못 답하느니 정보 한 줄
        return
    # 3) Q 줄 → 질문이면 답(답 뒤 또 질문이면 또 답), 아니면 여분 턴을 정보에 쓴다
    e = say(saymod.QUESTION_LINE, 'explain')
    if not e or e.get('refused'):
        return
    reply = e.get('reply') or ''
    if is_question(reply):
        while is_question(reply) and enc.can_act():
            ans = compose(reply)
            if not ans:
                break
            e2 = say(ans, 'explain-answer')
            if not e2 or e2.get('refused'):
                break
            reply = e2.get('reply') or ''
        return
    _spend_spare(enc, say, said, dropped, best_dropped, compose)


def _spend_spare(enc, say, said, dropped, best_dropped, compose):
    """Q 줄 답이 질문이 아닐 때 남는 턴: interview.spare_exam(있으면) → 빠진 설명 줄 → KB 추가 문장 → 요약. 되말하기는 하지 않는다."""
    extras = list(getattr(enc, 'say_extras', None) or []) + [SUMMARY_LINE]
    exam_ok = True
    while enc.can_act():
        if exam_ok:
            before = enc.turn
            try:
                from . import interview
                fn = getattr(interview, 'spare_exam', None)
                r = fn(enc) if callable(fn) else None
            except Exception as exc:  # noqa: BLE001 — 진찰 보충 실패는 설명 줄로 대신
                log(f'spare_exam failed: {type(exc).__name__}: {exc}')
                r = None
            if enc.turn != before and r:
                continue
            exam_ok = enc.turn != before   # 아무것도 안 했으면 다시 부르지 않는다
            if exam_ok:
                continue
        it = best_dropped()
        line = it['text'] if it else None
        while line is None and extras:
            c = extras.pop(0)
            if c and not saymod.say_problem(c) and not _dup(c, said):
                line = c
        if not line:
            break
        e = say(line, 'explain')
        if e is None:
            break
        reply = '' if e.get('refused') else (e.get('reply') or '')
        if is_question(reply) and enc.can_act():
            ans = compose(reply)
            if ans:
                say(ans, 'explain-answer')


def _pull_next(lines: list[str], i: int, pat) -> None:
    """환자 질문을 뒤 문장이 답하면 그 문장을 바로 다음 턴으로 당긴다(턴 수 불변)."""
    j = next((j for j in range(i + 1, len(lines)) if pat.search(lines[j]) and lines[j] != saymod.QUESTION_LINE), None)
    if j is not None and j > i + 1:
        lines.insert(i + 1, lines.pop(j))

"""v2 계획 + 설명: high 1회로 P 5칸·SAY 9~10문장·FAQ를 함께 만들고(계획과 발화 일치), 검증·필수 요소 보정 후 말한다.
(v2_spec §8.7, §8.8, §10.2, §10.3)"""
from __future__ import annotations

import json
import re

from . import guidelines
from . import kb as kbmod
from . import say as saymod
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
    return t2


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


def fix_say(enc, say: list[str], k) -> list[str]:
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
    n = enc.cfg['EXPLAIN_N']
    final = saymod.ensure_elements(good, enc.dx or '', kb_say=[safe_say(s) for s in kb_say],
                                   red_flags_say=(k or {}).get('red_say', ''), max_lines=n, log=log, keep=keep)
    final = _dedup_exact([safe_say(s) for s in final])
    enc.say_checks = checks + [{'missing_before': saymod.missing_elements(good, enc.dx or '')}]
    return final


def _faq_key(reply: str):
    for key, pat in FAQ_KEYS.items():
        if re.search(pat, reply):
            return key
    return None


def is_question(reply: str) -> bool:
    r = nfc(reply)
    if re.match(r'\s*(네|예)[,.]?\s*(알겠|감사|그럴게|그렇게)', r):
        return False
    return '?' in r or bool(re.search(r'(까요|나요|건가요|어떻게|언제|얼마나)', r))


def answer(enc, reply: str, said: list[str]) -> str:
    p = enc.plan_v2 or {}
    res = ask(enc.client, enc.budget, '당신은 한국 외래 의사입니다. JSON 하나만 출력하세요.',
              f'환자의 말: "{reply}" / 진단: {enc.dx} / 계획 요약: 검사 {p.get("tests", [])[:4]}, 치료 {p.get("treatment", [])[:3]}, '
              f'재진 {p.get("follow_up", [])[:2]}\n이미 한 설명: {said}\n'
              '환자에게 할 답 한 문장(공백 포함 28자 이내, 쉬운 존댓말 평서문). 질문의 핵심(예: 체중이 돌아오나, 약 없이 잘 수 있나, '
              '치료 기간)에 일반적인 의학 지식으로 먼저 직접 답하고(예: "치료하면 대개 체중도 회복돼요."), 이미 한 설명을 반복하지 말 것. '
              '미루기 금지, 계획과 모순 금지, 근거 없는 단정·약속 금지. 출력: {"answer": "..."}',
              effort=enc.cfg['EFFORT_ANSWER'], max_tokens=4000, tag='answer', want=dict, reserve=enc.cfg['CALL_RESERVE'])
    a = safe_say(nfc((res or {}).get('answer') or '').strip())
    if not a or saymod.say_problem(a):
        return '오늘 계획대로 하며 같이 조절해 갈게요.'
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
    if '불안정' not in va and any(re.search(r'입원.{0,6}(필요|불필요|고려)', d) for d in disp):
        disp.insert(0, va.split(' → ')[0])
    else:
        disp.insert(0, va)
    disp = dedup_lines([safe_plan_line(d, 'disposition', admit_if) for d in disp])
    fu = list(plan.get('follow_up') or [])
    if not any(re.search(r'(즉시|바로|응급)', f) for f in fu):
        fu.append(f"즉시 내원 : {(k or {}).get('red_flags') or '증상 악화, 호흡곤란, 흉통, 의식 변화, 고열'}")
    ec = (k or {}).get('early_contact')
    if ec and not any(re.search(ec[0], f) for f in fu):
        pos = next((i for i, f in enumerate(fu) if re.search(r'(즉시|바로|응급)', f)), len(fu))
        fu.insert(pos, ec[1])
    fu = dedup_lines([safe_plan_line(f, 'follow_up', admit_if) for f in fu])
    edu_plan = [safe_plan_line(e, 'education', admit_if) for e in (plan.get('education') or [])]
    edu = education_text(enc.explained, '\n'.join(e for e in edu_plan if e), v4=bool(getattr(enc, 'v4', False)))

    def fmt(lst):
        return '\n'.join(f'- {x}' for x in lst if x)
    return {'tests': fmt(tests), 'treatment': fmt(treat), 'disposition': fmt(disp), 'follow_up': fmt(fu),
            'education': edu}

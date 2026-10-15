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
from .util import is_similar, log, nfc, similarity

ROLE = '당신은 한국 대학병원 외래의 숙련된 전문의입니다. 초진을 마무리하며 계획(P)을 세우고 환자에게 말할 설명을 씁니다. JSON 하나만 출력하세요.'

FAQ_KEYS = {'prescribe': r'(처방|수면제\s*(주|받))', 'duration': r'(얼마나\s*오래|기간|언제까지|몇\s*(달|년))',
            'results': r'(언제|결과|며칠|얼마나\s*걸)',
            'prognosis': r'(나을|낫|좋아질|회복|클\s*수|자랄|돌아올|돌아오|평생|잘\s*수\s*있|(살|체중|몸무게).{0,6}(찌|찔|쪄|붙|늘|돌아))',
            'test_pain': r'(검사.{0,8}(아프|아파|힘들|무섭))|((아프|아파|힘들).{0,4}검사)',
            'serious': r'(큰\s*병|위험|심각|괜찮|암|나쁜|해로|해롭)',  # v7 C6-c: '계속 먹으면 해로울까요?'
            'treatment': r'(약|치료|끊|줄|먹어야|주사|수술)', 'tests': r'(검사|확인|무슨\s*검)',
            'lifestyle': r'(조심|주의|음식|운동|생활|약\s*없이|방법)'}

# v7 C1-b: plan_say에 요청하는 FAQ 키(KB faq에 있는 키는 빼고, 환자 요청이 있으면 prescribe 추가)
FAQ_ASK = ('prognosis', 'serious', 'treatment', 'duration', 'lifestyle')
FAQ_DESC = {'prognosis': 'prognosis(나을 수 있나/더 클 수 있나)', 'serious': 'serious(큰 병인가/위험한가)',
            'treatment': 'treatment(약·기간·끊어도 되나)', 'duration': 'duration(치료 기간)',
            'lifestyle': 'lifestyle(생활에서 주의할 점)', 'prescribe': 'prescribe(약을 처방해 주나)'}


def faq_request_keys(k, prof) -> list[str]:
    have = set(((k or {}).get('faq') or {}).keys())
    keys = [x for x in FAQ_ASK if x not in have]
    if (prof or {}).get('request') and 'prescribe' not in have:
        keys.append('prescribe')
    return keys


# v7 C6-c: answer() 폴백 2순위(FAQ 값 → 주제별 기본 답 → 범용 문장). 모두 say_problem 통과(테스트 T16)
# (설계서 serious 문구 '…알려 드릴게요.'는 SAY_BAD_RE '드릴게'에 걸려 safe_say가 SAFE_SAY로 바꾸므로 어미만 교체)
TOPIC_FALLBACK = {'serious': '검사로 확인한 뒤 결과를 자세히 설명해요.',
                  'treatment': '검사 결과를 보고 치료 방법을 같이 정해요.',
                  'tests': '피검사 결과로 원인을 확인할 거예요.',
                  'results': '결과는 다음 진료 때 함께 봐요.',
                  'prognosis': '치료 반응을 보며 같이 관리해 갈게요.',
                  'lifestyle': '규칙적으로 자고 무리하지 않는 게 좋아요.'}


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
                        r'처방해요|처방했(?:어요|습니다|다)?|처방하겠습니다|'
                        r'드려요|드립니다|드릴게요?|시작합니다|시작함|시작해요|시작할게요?|시작하겠습니다|투여합니다|투여함|투여|'
                        r'올려요|올립니다|올릴게요?|증량(?:합니다|해요|할게요?|함))')
NO_ADMIT_RE = re.compile(r'(?:,\s*)?(?:급성\s*위험\s*징후\s*없어\s*)?\(?\s*입원\s*(?:은\s*)?'
                         r'(?:불필요|필요\s*없음|필요하지\s*않음|하지\s*않음)\s*\)?(?:\s*,\s*외래\s*추적)?')
NOT_NEEDED_RE = re.compile(r'필요\s*없(?:음|다|어요)')
VITALS_LINE_RE = re.compile(r'(활력징후|V/S|mmHg|SpO2|산소포화)')
DECIDE = '검사 결과 확인 후 전문의와 상의해 결정'
SAFE_SAY = '약은 검사 결과 보고 상의해 조절해요.'
SAY_BAD_RE = re.compile(r'(드려요|드릴게|드립니다|처방(?:해\s*드|할게|해요|합니다|했|하겠|드)|단기\s*처방|'
                        r'시작해요|시작할게|시작합니다|시작하겠|올려요|올릴게|올립니다|증량|감량(?:할게|합니다|해\s*드)|'
                        r'(?:용량|약)을?\s*(?:올려|올릴|늘려|늘릴)|'
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
    n = enc.cfg['EXPLAIN_N'] - 2  # v5: 되말하기(TEACH_BACK)와 마지막 '더 궁금하신 점'은 코드가 붙임(설명 턴 수 불변)
    pos = [f"{f['label']}{(' ' + f['detail']) if f['detail'] else ''}" for f in facts if f['pol'] == '+'][:25]
    neg = [f['label'] for f in facts if f['pol'] == '-'][:20]
    abn = [f"{x['name']}: {x['result'][:50]}" for x in (a.get('exams') or [])]
    ice = [f"{e['text']} → {e['reply']}" for e in enc.ledger if str(e.get('qid', '')).startswith('ice')]
    sex = {'F': '여', 'M': '남'}.get(prof.get('sex'), '?')
    ddx = [d['dx'] for d in a.get('differential') or []] or enc.differentials[1:4]
    from .record import vitals_assessment
    va = vitals_assessment(enc)
    gl = guidelines.hint_plan(enc)
    gl_rule = ('- [진료지침 발췌]가 있으면 tests·follow_up의 근거로만 쓰되 환자 사실에 맞는 것만 고르고, '
               '지식표와 충돌하면 지식표를 따를 것. 발췌로 약·치료를 정하지 말고, 검사를 지어내거나 용량 숫자를 쓰지 말 것. '
               '경고 증상은 발췌의 위험 징후를 반영.\n'
               if gl else '')
    # v7 C1-b: KB가 맞으면 render_plan이 LLM 치료 줄을 버리므로 생성하지 않게 한다
    if k:
        treat_rule = '- treatment: [] (약물 치료는 지식표가 정함). 환자 요청에 대한 결정이 필요하면 그 1줄만.\n'
    else:
        treat_rule = ("- treatment: 조건부('검사 확인 후 ~ 시작 고려', '금기 확인 후'). 새 약 용량 숫자 금지(현재 복용약은 가능). 비약물 치료 포함.\n"
                      '  환자 요청이 있으면 그에 대한 결정과 이유를 한 줄로. 적응증 없는 약(수면제·스테로이드·항히스타민 등) 금지.\n')
    # v7 C1-b: FAQ는 KB faq에 없는 키만 요청(요청이 있으면 prescribe 추가), 없으면 지시·출력 키를 뺀다
    faq_keys = faq_request_keys(k, prof)
    faq_rule = ('[FAQ] 환자가 물을 만한 질문에 대한 22자 이내 답(존댓말 평서문): '
                + ', '.join(FAQ_DESC[x] for x in faq_keys) + '.\n') if faq_keys else ''
    faq_out = (', "faq": {' + ', '.join(f'"{x}": "..."' for x in faq_keys) + '}') if faq_keys else ''
    user = (f"환자: {prof.get('age')}세 {sex}, 정보 제공자 {prof.get('informant')}, 주진단: {enc.dx}, 감별: {ddx}\n"
            f"핵심 양성 사실: {pos}\n핵심 음성 사실: {neg}\n진찰 소견: {abn}\n활력징후 판단: {va}\n"
            f"환자 걱정·궁금증·요청(ICE): {ice} / 요청: {prof.get('request') or '없음'}\n"
            f"참고 지식표(있으면, 환자에 맞게 취사선택): {json.dumps(kbmod.kb_hint(k), ensure_ascii=False) if k else '없음'}\n"
            f'{gl}'
            '[P 규칙]\n'
            f'{gl_rule}'
            '- tests: 3~7줄 {"name","reason"}. name은 구체 항목(같은 계열은 한 줄로 묶기, 예: "혈액 : CBC, ESR/CRP, 전해질, '
            'AST/ALT, BUN/Cr, 공복혈당/HbA1c"),\n'
            '  reason은 15자 이내 목적. 증상별로 교정 가능한 원인 검사를 포함. 감별진단의 감별 검사와 일치시킬 것.\n'
            '  결과에 따라 하는 검사는 name 앞에 "(조건부)"를 붙이고 reason에 시행 조건.\n'
            f'{treat_rule}'
            "- disposition: 귀가/외래/의뢰/응급 + 근거(활력징후·위험 징후), '입원 필요/불필요' 명시.\n"
            '- follow_up: "재진 : 기간 — 확인할 항목", "모니터링 : 간격 — 항목"(치료를 시작할 때), '
            '"의뢰 기준 : 어떤 결과·증상이면 어느 진료과",\n'
            '  "즉시 내원 : 구체적 경고 증상 4개 이상". 이상 진찰 소견(예: 안구돌출, 근력 저하)은 모니터링 또는 의뢰 기준에 반영.\n'
            '- education: 이번 설명(SAY)에 넣지 못한 핵심 최대 3개(짧게).\n'
            '[안전 체크 — 해당되는 것만 반영]\n'
            '가임기 여성 임신 확인 / 진정제: 급중단 금지·운전 회피·병용 금지 / 항갑상샘제: 무과립구증·간독성 / 베타차단제: 천식·서맥 금기 /\n'
            'NSAIDs: 위장·신장 / 항생제: 알레르기 / 소아: 아스피린 금지·체중 기반·지사제 금지 / 자살 위험: 안전 계획 / 노인: 낙상.\n'
            f'[SAY 규칙] 정확히 {n}문장, 각 공백 포함 28자 이내, 쉬운 존댓말 평서문, 영어 약어 금지(MRI·CT만 허용), 띄어쓰기 정확,\n'
            " 한 문장 한 메시지, 단정·보장 금지('걱정 안 해도', '완치', '확실히'). 내용 없는 문장 금지 — 모든 문장에 구체 정보.\n"
            " 공감·인사 머리말 금지('걱정되시죠,' 등), 물음표 금지. 약은 계열명만(성분명·용량·횟수 금지), "
            "'시작해요·처방해요·드릴게요·올려요' 같은 처방 확정 표현 금지.\n"
            ' 순서와 필수 요소:\n'
            " ①진단을 쉬운 말로(병명 포함, 검사 전이므로 '~로 보여요/가능성이 높아요'처럼, '진단합니다' 같은 확정 표현 금지)\n"
            " ②원인·기전을 환자 말로, 환자 증상 1~2개와 연결(예: '면역 이상으로 갑상샘 호르몬이 넘쳐 살이 빠져요')\n"
            " ③환자 걱정·궁금증에 직접 답 + 그렇게 판단한 근거 소견 1개(예: '목이 붓고 눈이 나와 암보다 갑상샘 병이에요');"
            ' 환자가 말하지 않은 걱정을 지어내지 말 것.\n'
            '   걱정이 없었으면 생활 수칙 1문장\n'
            " 검사 전이므로 아직 확인 안 된 내용(뼈 나이, 호르몬 수치 등)은 '~인지 확인해요'로 말하고 단정하지 말 것.\n"
            " ④검사 이름과 그 검사로 무엇을 확인하는지(예: '피검사로 호르몬과 원인 항체를 확인해요')\n"
            ' ⑤치료 선택지(계열명)와 결정 시점, 또는 대표 부작용이 생기면 할 행동'
            "(예: '약 먹다 열·목 아프면 멈추고 바로 연락하세요'; 지식표가 있으면 그 방향을 따름)\n"
            " ⑥경고 증상: 구체적 증상 4개 이상을 '·'로 이어 한 문장(예: '숨참·불규칙한 맥·고열·혼동 시 바로 오세요.')\n"
            " ⑦재진 시점과 그때 볼 것(예: '1~2주 뒤 결과 보러 다시 오세요')\n"
            " 되말하기 질문과 '더 궁금하신 점 있으세요?'는 쓰지 마세요(코드가 붙임). 요청이 있으면 그 결정을 SAY에 포함.\n"
            ' P에 적은 검사·재진 시점·경고 증상·안전 수칙은 SAY에서 반드시 말할 것. 소아면 보호자에게 말하듯.\n'
            f'{faq_rule}'
            '출력: {"tests": [{"name": "...", "reason": "..."}], "treatment": [...], "disposition": [...], "follow_up": [...],\n'
            f' "education": [...], "say": [...]{faq_out}}}')
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
    enc.plan_disp_raw = plan['disposition']  # v7 긴급: 응급 승격 판정(fix_say·render_plan 동일 입력)
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


# v7 C6-b: SAY 슬롯(경고·재진·검사·감량). 같은 슬롯은 한 문장만, must_say가 차지한 슬롯의 LLM 문장은 버린다.
# 'warn'은 경고 증상 나열 문장(warn_count ≥ 3)만 — '약 먹다 열·목 아프면 멈추고 바로 연락' 같은 부작용 행동 문장은 별개로 둔다.
TAPER_RE = re.compile(r'(천천히|서서히|조금씩)\s*줄|급히\s*끊|바로\s*끊|혼자\s*끊|갑자기\s*끊')
SLOT_RES = [('warn', saymod.WARN_RE), ('follow', saymod.FOLLOWUP_RE), ('test', saymod.TEST_RE), ('taper', TAPER_RE)]


def _slot(s: str) -> str:
    for name, r in SLOT_RES:
        if r.search(s):
            if name == 'warn' and saymod.warn_count([s]) < 3:
                continue
            return name
    return ''


def _slot_dedup(good: list[str], k, checks: list) -> list[str]:
    must = (k or {}).get('must_say') or []
    must_slots = {_slot(sent) for _, sent in must} - {''}

    def is_must(s):
        return any(re.search(p, s) for p, _ in must)
    # 같은 슬롯 중 남길 문장: 재진은 '오세요'처럼 직접 안내하는 문장, 경고는 증상 수가 많은 문장을 우선(없으면 첫 문장)
    pick = {}
    for i, s in enumerate(good):
        sl = _slot(s)
        if not sl or is_must(s) or sl in must_slots:
            continue
        j = pick.get(sl)
        if j is None:
            pick[sl] = i
        elif sl == 'follow' and COME_RE.search(s) and not COME_RE.search(good[j]):
            pick[sl] = i
        elif sl == 'warn' and saymod.warn_count([s]) > saymod.warn_count([good[j]]):
            pick[sl] = i
    out = []
    for i, s in enumerate(good):
        sl = _slot(s)
        if sl and not is_must(s) and (sl in must_slots or pick.get(sl) != i):
            checks.append({'drop_slot': s, 'slot': sl})
            continue
        out.append(s)
    return out


def _say_body(enc, say: list[str], k, checks: list) -> tuple[list[str], list[str]]:
    """규칙 위반 제거 → 금지·안전 보정 → 슬롯 중복 제거 → must_say 삽입 → (부족하면) KB say로 채움. (good, keep)"""
    good = []
    for s in say:
        if saymod.say_problem(s):
            checks.append({'drop': s, 'why': saymod.say_problem(s)})
            continue
        if is_similar(s, good, 0.6):
            checks.append({'drop_dup': s})
            continue
        good.append(s)
    # KB 안전 규칙: 금지 문장 제거, 필수 문장 삽입(경고 문장 앞)
    # v6: '천식'을 항갑상샘제 금기처럼 말한 틀린 문장 → KB의 천식 필수 문장으로 치환
    good = [next((m for _, m in (k or {}).get('must_say') or [] if '천식' in m), s) if re.search(r'천식', s) and re.search(r'항갑상(샘|선)', s) else s for s in good]
    if k and k.get('ban_say'):
        dropped = [s for s in good if re.search(k['ban_say'], s)]
        good = [s for s in good if s not in dropped]
        if dropped:
            checks.append({'ban_say': dropped})
    fixed_safe = [safe_say(s) for s in good]
    if fixed_safe != good:
        checks.append({'safe_say': [(a, b) for a, b in zip(good, fixed_safe) if a != b]})
    good = _dedup_exact(fixed_safe)
    good = _slot_dedup(good, k, checks)
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
    # v7 C1-c: 본문이 EXPLAIN_N−3 미만이면 KB say로 EXPLAIN_N−2까지 채움(안전·유사도·슬롯 중복 검사)
    n = enc.cfg['EXPLAIN_N']
    if k and len(good) < n - 3:
        for s in k.get('say') or []:
            if len(good) >= n - 2:
                break
            t = safe_say(s)
            if t != s or saymod.say_problem(t) or SAY_BAD_RE.search(t) or is_similar(t, good, 0.5):
                continue
            if k.get('ban_say') and re.search(k['ban_say'], t):
                continue
            sl = _slot(t)
            if sl and any(_slot(g) == sl for g in good):
                continue
            pos = next((i for i, g in enumerate(good) if saymod.WARN_RE.search(g)), len(good))
            good.insert(pos, t)
            checks.append({'kb_fill': t})
    return good, keep


def _say_fix_llm(enc, say: list[str], bad_idx: list[int], checks: list) -> None:
    """v6 say_fix: 규칙 위반 문장을 LLM으로 다시 씀(제자리 교체)."""
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


def fix_say(enc, say: list[str], k) -> list[str]:
    checks = []
    say = list(say)
    bad_idx = [i for i, s in enumerate(say) if saymod.say_problem(s)]
    use_llm = bool(enc.cfg.get('SAY_FIX_LLM', 0))
    if use_llm and bad_idx and enc.budget.can_call(enc.cfg['CALL_RESERVE']):  # v6 동작(플래그 켰을 때만)
        _say_fix_llm(enc, say, bad_idx, checks)
    kb_say = (k or {}).get('say') or []
    good, keep = _say_body(enc, say, k, checks)
    # v7 C1-c: 플래그가 꺼져 있어도 유효 문장이 4개 미만이면 안전망으로 LLM 1회
    if not use_llm and len(good) < 4 and bad_idx and enc.budget.can_call(enc.cfg['CALL_RESERVE']):
        _say_fix_llm(enc, say, bad_idx, checks)
        good, keep = _say_body(enc, say, k, [])
    n = enc.cfg['EXPLAIN_N']
    # v5: 한 칸은 되말하기(TEACH_BACK) 몫 → 전체 설명 턴 수(n)는 그대로
    final = saymod.ensure_elements(good, enc.dx or '', kb_say=[safe_say(s) for s in kb_say],
                                   red_flags_say=(k or {}).get('red_say', ''), max_lines=n - 1, log=log, keep=keep)
    final = _dedup_exact([safe_say(s) for s in final])
    em = emergency_check(enc, k, getattr(enc, 'plan_disp_raw', None) or [])
    if em['escalate']:  # v7 긴급: 재진 문장 → 응급실 안내(문장 수 불변, direct_followup 생략)
        i = next((i for i, s in enumerate(final) if saymod.FOLLOWUP_RE.search(s) and not saymod.WARN_RE.search(s)), None)
        if i is not None and EMERG_SAY not in final:
            log(f'SAY emergency: {final[i]} → {EMERG_SAY}')
            final[i] = EMERG_SAY
        final = add_teach_back(final)
    else:
        final = add_teach_back(direct_followup(final, keep))
    enc.say_checks = checks + [{'missing_before': saymod.missing_elements(good, enc.dx or '')}]
    return final


# ---------------------------------------------------------------- v5 의사소통: 재진 직접 안내 + 되말하기
TEACH_BACK = '바로 오셔야 할 증상 하나를 말씀해 보세요.'
COME_RE = re.compile(r'(오세요|오셔요|와\s*주세요|내원|방문|재진)')


def direct_followup(lines: list[str], keep=None) -> list[str]:
    """재진 시점 문장이 '다시 오세요'로 환자에게 직접 말하지 않으면 그 문장을 'N주 뒤 결과 보러 다시 오세요.'로 바꾼다(문장 수 불변)."""
    if any(saymod.FOLLOWUP_RE.search(s) and COME_RE.search(s) for s in lines):
        return lines
    out = list(lines)
    for i, s in enumerate(out):
        m = saymod.FOLLOWUP_RE.search(s)
        if not m or saymod.WARN_RE.search(s) or s in (keep or []) or (m.group(3) or '') == '마다':
            continue
        when = f'{m.group(1)} 뒤' if m.group(1) else (f'{m.group(0)}에' if m.group(0).startswith('다음') else m.group(0))
        new = f'{when} 결과 보러 다시 오세요.'
        if not saymod.say_problem(new) and not SAY_BAD_RE.search(new):
            out[i] = new
        break
    return out


def add_teach_back(lines: list[str]) -> list[str]:
    """경고 증상 문장 바로 뒤에 되말하기 한 문장을 넣는다(없으면 그대로)."""
    if TEACH_BACK in lines:
        return lines
    body = [l for l in lines if l != saymod.QUESTION_LINE]
    pos = max((i for i, s in enumerate(body) if saymod.WARN_RE.search(s)), default=None)
    if pos is None:
        return lines
    body.insert(pos + 1, TEACH_BACK)
    return body + ([saymod.QUESTION_LINE] if saymod.QUESTION_LINE in lines else [])


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


def answer(enc, reply: str, said: list[str], fallback: str = '') -> str:
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
        # v5: 실질 답이 없으면 같은 주제의 FAQ 답 → v7 C6-c: 주제별 기본 답 → 범용 문장(미응답 감점 방지)
        key = _faq_key(nfc(reply or ''))
        for cand in (fallback, TOPIC_FALLBACK.get(key, '') if key else ''):
            fb = safe_say(cand) if cand else ''
            if fb and not saymod.say_problem(fb) and fb not in said:
                return fb
        return '오늘 계획대로 하며 같이 조절해 갈게요.'
    return a


def _pull_next(lines: list[str], i: int, pat) -> None:
    """v5: 환자 질문을 뒤 문장이 답하면 그 문장을 바로 다음 턴(i+1)으로 당긴다(턴 수 불변, '다음 턴에서 먼저 답')."""
    j = next((j for j in range(i + 1, len(lines)) if pat.search(lines[j])), None)
    if j is not None and j > i + 1:
        lines.insert(i + 1, lines.pop(j))


def explain_loop(enc, lines: list[str], faq: dict, quick=False):
    said = []
    answers = 0
    amax = 0 if quick else enc.cfg['ANSWER_MAX']
    used_faq = set()
    lines = list(lines)
    # v7 C6-c: 마지막 질문('더 궁금하신 점')의 답 1자리를 남겨 둔다 — 중간 질문은 ANSWER_MAX−1까지, 마지막은 ANSWER_MAX까지
    final_i = len(lines) - 1 if lines and lines[-1] == saymod.QUESTION_LINE else None
    for i in range(len(lines)):
        line = lines[i]
        if not enc.can_act():
            break
        entry = enc.act('SAY', line, phase='explain')
        if not entry or entry.get('refused'):
            continue
        said.append(line)
        enc.explained.append(line)
        reply = entry.get('reply') or ''
        rest = lines[i + 1:]
        cap = amax if (final_i is None or i == final_i) else max(0, amax - 1)
        if answers >= cap or not is_question(reply) or enc.turns_remaining < len(rest) + 1:
            continue
        key = _faq_key(reply)
        ans = None
        if key and key in faq and key not in used_faq:
            # 곧 나올 문장이 같은 주제를 답하면 건너뜀
            if key == 'tests' and any(saymod.TEST_RE.search(s) for s in rest):
                _pull_next(lines, i, saymod.TEST_RE)
                continue
            if key == 'results' and any(saymod.FOLLOWUP_RE.search(s) for s in rest):
                _pull_next(lines, i, saymod.FOLLOWUP_RE)
                continue
            ans = safe_say(faq[key])
            used_faq.add(key)
        elif key in ('tests', 'results') and any(
                (saymod.TEST_RE if key == 'tests' else saymod.FOLLOWUP_RE).search(s) for s in rest):
            _pull_next(lines, i, saymod.TEST_RE if key == 'tests' else saymod.FOLLOWUP_RE)
            continue
        else:
            ans = answer(enc, reply, said, faq.get(key, '') if key else '')
        if ans and ans not in said:
            e2 = enc.act('SAY', ans, phase='explain-answer')
            if e2 and not e2.get('refused'):
                said.append(ans)
                enc.explained.append(ans)
                answers += 1


# ---------------------------------------------------------------- v7 C4-c P칸 보조
_TEST_STOP = {'검사', '혈액', '혈액검사', '기능', '기능검사', '확인', '측정', '선별', '필요', '경우', '결과'}


def _test_covered(t: str, lines: list[str]) -> bool:
    """감별 검사 t의 핵심 토큰이 과반 이미 P.tests에 있으면 True(토큰이 없으면 True).
    설계서는 '하나라도'였으나 '갑상샘 섭취율'이 '갑상샘중독증 확인'으로 덮이는 식의 과잉 판정이 있어 과반으로 한다."""
    def norm(s):
        return (s or '').replace('갑상선', '갑상샘')
    toks = [x for x in re.findall(r'[A-Za-z][A-Za-z0-9\-/]+|[가-힣]{2,}', norm(t)) if x not in _TEST_STOP]
    if not toks:
        return True
    txt = norm('\n'.join(lines or []))
    low = txt.lower()

    def hit(x):
        if re.match(r'[A-Za-z]', x):
            xl = x.lower()
            return bool(re.search(r'tft|tsh|free\s*t4', low)) if xl == 'tft' else xl in low
        return x in txt
    return sum(1 for x in toks if hit(x)) * 2 > len(toks)


# 유형 판정 순서: '조기 연락' 줄에 '바로 연락'이 들어 있어 즉시 내원보다 먼저 본다(설계서 순서에서 앞 두 개만 바꿈)
FU_TYPES = [('조기 연락', r'조기\s*연락'), ('즉시 내원', r'즉시|바로|응급'), ('의뢰 기준', r'의뢰|전원|협진'),
            ('재진', r'재진|재방문|결과\s*(확인|보러)|후\s*외래'), ('모니터링', r'모니터링|간격|마다|추적')]
FU_ORDER_HEAD = ('재진', '모니터링')
FU_ORDER_TAIL = ('의뢰 기준', '조기 연락', '즉시 내원')
DEPT_RE = re.compile(r'(내과|외과|의학과|신경과|안과|부인과|인후과|피부과|청소년과|소아과)$')


def _fu_type(line: str) -> str:
    head = line.split(':', 1)[0] if ':' in line else ''
    if head:  # 'X : …' 접두가 있으면 접두로 판정
        for name, pat in FU_TYPES:
            if re.search(pat, head):
                return name
    for name, pat in FU_TYPES:
        if re.search(pat, line):
            return name
    return ''


def _fu_prefixed(name: str, line: str) -> str:
    pat = dict(FU_TYPES)[name]
    head = line.split(':', 1)[0] if ':' in line else ''
    if (head and re.search(pat, head)) or name in line:
        return line
    return f'{name} : {line}'


def order_follow_up(fu: list[str]) -> list[str]:
    """P.추적: 유형별 가장 긴 줄 1개, 재진 → 모니터링 → (미분류 1줄) → 의뢰 기준 → 조기 연락 → 즉시 내원."""
    best, unk = {}, []
    for l in fu:
        t = _fu_type(l)
        if not t:
            unk.append(l)
        elif t not in best or len(l) > len(best[t]):
            best[t] = l
    out = [_fu_prefixed(t, best[t]) for t in FU_ORDER_HEAD if t in best]
    out += unk[:1]
    out += [_fu_prefixed(t, best[t]) for t in FU_ORDER_TAIL if t in best]
    return out


ADMIT_RE = re.compile(r'입원.{0,6}(필요|불필요|고려)')
NO_SIGN_RE = re.compile(r'(징후|소견)\s*(이|가|는)?\s*없(어|음|고)')
SOFT_PREFIX = '확인된 활력징후·진찰 소견상 '


def soften(line: str, enc) -> str:
    """처치 결정 줄: 하지 않은 진찰 소견(의식 명료) 삭제, '징후 없어' 단정에 '확인된 … 소견상' 한정."""
    t = line.strip()
    if '의식 명료' in t and 'mental' not in (getattr(enc, 'done_exams', None) or []):
        t = re.sub(r'의식\s*명료\s*[,·]?\s*', '', t).strip(' ,')
    if NO_SIGN_RE.search(t) and '확인된' not in t:
        t = SOFT_PREFIX + t
    return t


def decide_disposition(enc, disp: list[str], admit_if: str, vitals_assessment) -> list[str]:
    """v7 C4-c 처치 결정: 활력 요약 한 줄(수치는 O칸) + soften + 입원 판단 보장. 불안정이면 v6 긴 문장 그대로."""
    va = vitals_assessment(enc).lstrip('- ')
    try:  # 담당 A: record.vitals_assessment(enc, short=True). 아직 없으면 긴 문장의 앞 구절로 대신한다
        vs = vitals_assessment(enc, short=True)
    except TypeError:
        vs = ''
    vs = (vs or '').strip().lstrip('- ').strip() or va.split(' : ')[0].strip()
    if '불안정' in va or '불안정' in vs:
        return [va] + list(disp)
    out, rest = [], list(disp)
    if rest and re.match(r'\s*활력징후[^,]*,', rest[0]):  # 예: graves KB '활력징후 안정, 갑상샘중독발증 징후 없어 …'
        out.append(soften(re.sub(r'^\s*활력징후[^,]*,\s*', f'{vs}, 확인된 진찰 소견상 ', rest[0], count=1), enc))
        rest = rest[1:]
    else:
        out.append(vs)
    for l in rest:
        l = re.sub(r'^\s*활력징후[^,]*(,\s*|$)', '', l.strip()).strip()  # 활력 서술·수치 반복 제거(맨 앞 한 줄이 대신)
        if l:
            out.append(soften(l, enc))
    if not any(ADMIT_RE.search(l) for l in out):
        out.append(f"현재 외래 추적이 적절하며 {admit_if or '활력징후 불안정·증상 급격한 악화'} 시 입원 고려")
    return out


# ---------------------------------------------------------------- v7 긴급 수정: 감별 검사 필터·응급 승격
# assess.py [감별] 프롬프트의 when 예시(복사되면 버림). (예시 문자열, 그 예시가 맞는 진단 문맥)
DX_PROMPT_WHEN_EXAMPLES = [('TRAb 음성·불명확 시', r'갑상|그레이브스|graves|thyro')]
INVASIVE_TEST_RE = re.compile(r'내시경|대장\s*조영|조영술|생검|골수|요추\s*천자|심도자|혈관\s*조영')
COND_TEST_MAX = 2


def _prompt_example_hit(s: str, ctx: str) -> bool:
    """s가 프롬프트 예시와 같거나 유사(≥0.7·포함)하고, 예시의 검사 문맥이 진단(ctx)과 무관하면 True."""
    s = (s or '').strip()
    if not s:
        return False
    for ex, rel in DX_PROMPT_WHEN_EXAMPLES:
        if (ex in s or s in ex or similarity(s, ex) >= 0.7) and not re.search(rel, ctx or '', flags=re.I):
            return True
    return False


def _invasive_unsupported(t: str, d: dict, k) -> bool:
    """저수율 침습 검사인데 KB 검사 목록·감별 근거(reason)에 같은 검사명이 없으면 True."""
    m = INVASIVE_TEST_RE.search(t or '')
    if not m:
        return False
    word = re.sub(r'\s+', '', m.group(0))
    kb_names = ' '.join(a for a, _ in ((k or {}).get('tests') or []))
    ref = re.sub(r'\s+', '', kb_names + ' ' + str(d.get('reason') or ''))
    return word not in ref


def _cap_conditional(tests: list[str]) -> list[str]:
    out, n = [], 0
    for l in tests:
        if '(조건부)' in l:
            n += 1
            if n > COND_TEST_MAX:
                log(f'P tests dropped (조건부 > {COND_TEST_MAX}): {l}')
                continue
        out.append(l)
    return out


EMERG_EXAM_RED = [(r'반발\s*\S{0,3}통\s*\(\s*\+', '반발통'), (r'근성\s*방어\S{0,4}\s*\(\s*\+', '근성방어'),
                  (r'복막\s*자극\S{0,6}\s*\(\s*\+', '복막자극 징후'), (r'경부\s*강직\s*\(\s*\+', '경부강직'),
                  (r'(케르니그|커니그|브루진스키)\S{0,4}\s*\(\s*\+', '수막자극 징후')]  # code_v4 EXAM_RED 이식
EMERG_TXT_RE = re.compile(r'응급|입원\s*(이\s*)?(필요|치료)|수술|외과\s*(의뢰|협진|평가)|즉시\s*전원')
EMERG_NEG_RE = re.compile(r'불필요|고려|없(어|음|고|으며|다)|않|아님|낮|기준|교육|안내')
EMERG_COND_RE = re.compile(r'(\s시|경우|이면|하면|되면|때)(\s|$)')
EMERG_SAY = '오늘 바로 응급실로 가셔야 해요.'
EMERG_FU = '재진 : 응급 평가 후 결과에 따라 외래 추적'


def _emerg_text_hit(text: str) -> bool:
    for cl in re.split(r'[,.;·→\n]|\s[—-]\s', text or ''):
        m = EMERG_TXT_RE.search(cl)
        if m and not EMERG_NEG_RE.search(cl) and not EMERG_COND_RE.search(cl[:m.start()]):
            return True
    return False


def emergency_check(enc, k, disp=None) -> dict:
    """응급 승격 판정. (a) KB 없음 + dx/LLM disposition이 응급·입원·수술·외과 의뢰를 가리킴,
    (b) 시행한 진찰 양성 응급 소견(복막·수막 자극) 또는 활력징후 불안정. 결과는 enc.emerg_escalate에 저장."""
    res = {'escalate': False, 'red': [], 'text': False, 'dept': ''}
    if not (getattr(enc, 'cfg', None) or {}).get('EMERG_ESCALATE', 1):
        enc.emerg_escalate = res
        return res
    red = []
    for e in getattr(enc, 'ledger', None) or []:
        if e.get('kind') != 'EXAM' or e.get('refused'):
            continue
        for pat, name in EMERG_EXAM_RED:
            if re.search(pat, e.get('reply') or '') and name not in red:
                red.append(name)
    try:
        from .record import vitals_assessment
        if '불안정' in vitals_assessment(enc):
            red.append('활력징후 불안정')
    except Exception:  # noqa: BLE001
        pass
    dx = getattr(enc, 'dx', None) or ''
    text = (not k) and _emerg_text_hit('\n'.join([dx] + [str(x) for x in (disp or [])]))
    dxt = dx + ' ' + ' '.join(d.get('dx') or '' for d in ((getattr(enc, 'assess', None) or {}).get('differential') or [])[:1])
    if re.search(r'수막|뇌염', dxt) or any(r in red for r in ('경부강직', '수막자극 징후')):
        dept = '신경과'
    elif re.search(r'충수|담낭|담석|장폐색|복막|천공|탈장|게실|췌장|장염전|장중첩', dxt) or any(
            r in red for r in ('반발통', '근성방어', '복막자극 징후')):
        dept = '외과'
    else:
        dept = '해당 전문과'
    res = {'escalate': bool(red or text), 'red': red, 'text': bool(text), 'dept': dept}
    enc.emerg_escalate = res
    if res['escalate']:
        log(f'v7 emergency escalate: red={red} text={bool(text)} dept={dept}')
    return res


def emergency_disposition(enc, em: dict, vitals_assessment) -> str:
    try:
        vs = vitals_assessment(enc, short=True)
    except TypeError:
        vs = ''
    vs = (vs or '').strip().lstrip('- ').strip()
    if '활력징후 불안정' in em['red']:  # 불안정이면 v6 긴 문장(수치 포함) 그대로 머리에
        vs = vitals_assessment(enc).strip().lstrip('- ').strip() or '활력징후 불안정'
    finds = [r for r in em['red'] if r != '활력징후 불안정']
    parts = [vs] if vs else []
    if finds:
        parts.append(f"진찰상 {'·'.join(finds)} 양성")
    head = ', '.join(parts) or '진찰·문진상 응급 평가 필요 소견'
    return f"{head} → 응급실 의뢰, 당일 {em['dept']} 평가 필요"


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
    tests = [drug_to_class(l) for l in plan.get('tests') or [] if keep(l)]  # v5: 검사 줄의 성분명도 계열명으로
    # 말로 설명한 검사가 P.tests에 없으면 보충(발화와 기록 일치)
    said = ' '.join(enc.explained or [])
    tests_txt = ' '.join(tests)
    # v7 C4-c: 존재 판정 패턴(have)을 따로 둔다 — 소변은 r'소변'(C01 '소변 약물 선별검사' 있는데 '소변검사' 중복 추가 버그)
    for word, pat, have, line in (('심전도', r'심전도', r'심전도', '심전도 : 진료 중 설명한 검사(심박·리듬 확인)'),
                                  ('초음파', r'초음파', r'초음파', '초음파 : 진료 중 설명한 검사'),
                                  ('엑스레이', r'엑스레이|엑스선|X-?ray', r'엑스레이|엑스선|X-?ray',
                                   '단순 방사선(X-ray) : 진료 중 설명한 검사'),
                                  ('소변', r'소변\s*(약물)?\s*검사', r'소변', '소변검사 : 진료 중 설명한 검사'),
                                  ('MRI', r'MRI', r'MRI', 'MRI : 진료 중 설명한 검사')):
        if re.search(pat, said) and not re.search(have, tests_txt, flags=re.I):
            kb_line = next((f'{a} : {b}' for a, b in ((k or {}).get('tests') or []) if re.search(have, a, flags=re.I)),
                           None)  # v7: KB 줄도 넓은 패턴으로 찾음(C01 '소변 약물 선별검사')
            tests.append(drug_to_class(kb_line or line))
    # v7 C4-c: A칸 감별 검사가 P.tests에 없으면 연결(기본 검사는 그대로, 결과에 따른 검사는 '(조건부)')
    for d in (getattr(enc, 'assess', None) or {}).get('differential') or []:
        t = (d.get('test') or '').strip()
        if not t or _test_covered(t, tests):
            continue
        w = (d.get('when') or '').strip()
        name = re.sub(r'\s*\(환자 우려\)', '', d.get('dx') or '').strip()
        ctx = name + ' ' + (getattr(enc, 'dx', None) or '')
        if _prompt_example_hit(w, ctx) or _prompt_example_hit(t, ctx):
            log(f'P tests dropped (prompt example copied): {t} / {w} / {name}')
            continue
        if _invasive_unsupported(t, d, k):
            log(f'P tests dropped (invasive, no KB/reason support): {t} / {name}')
            continue
        line = f"{t} : {name} 감별" if (not w or w == '기본') else f"(조건부) {t} : {w} — {name} 감별"
        line = drug_to_class(line)
        if keep(line):
            tests.append(line)
    tests = _cap_conditional(dedup_lines(tests))[:8]
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
    disp = decide_disposition(enc, disp, admit_if, vitals_assessment)
    disp = dedup_lines([safe_plan_line(d, 'disposition', admit_if) for d in disp])
    em = emergency_check(enc, k, plan.get('disposition') or [])
    if em['escalate']:  # v7 긴급: 응급 승격 — '외래 추적이 적절'·입원 고려/불필요·활력 줄 대신 응급 의뢰 한 줄
        rest = [d for d in disp if not re.search(r'외래\s*추적|입원\s*(은\s*)?(불필요|고려)|귀가|활력징후', d)]
        disp = dedup_lines([safe_plan_line(emergency_disposition(enc, em, vitals_assessment), 'disposition', admit_if)]
                           + rest)
    fu = list(plan.get('follow_up') or [])
    if em['escalate']:
        fu = [f for f in fu if _fu_type(f) != '재진']  # EMERG_FU는 즉시 내원 보장 뒤에 붙임('응급' 패턴 충돌)
    if not any(re.search(r'(즉시|바로|응급)', f) for f in fu):
        fu.append(f"즉시 내원 : {(k or {}).get('red_flags') or '증상 악화, 호흡곤란, 흉통, 의식 변화, 고열'}")
    ec = (k or {}).get('early_contact')
    if ec and not any(re.search(ec[0], f) for f in fu):
        pos = next((i for i, f in enumerate(fu) if re.search(r'(즉시|바로|응급)', f)), len(fu))
        fu.insert(pos, ec[1])
    # v7 긴급: KB refer_if가 있으면 KB 문장 우선 — LLM 의뢰 줄은 진료과가 겹치든 아니든 KB 1줄로 대체
    if enc.cfg.get('FU_REFER', 1) and (k or {}).get('refer_if'):
        kb_depts = {m for m in re.findall(r'[가-힣]{2,8}과|소아내분비', k['refer_if']) if DEPT_RE.search(m) or m == '소아내분비'}
        for f in [f for f in fu if _fu_type(f) == '의뢰 기준']:
            depts = {m for m in re.findall(r'[가-힣]{2,8}과|소아내분비', f) if DEPT_RE.search(m) or m == '소아내분비'}
            log(f"P follow_up refer → KB ({'overlap' if depts & kb_depts else 'dept mismatch'} {sorted(depts)}): {f}")
            fu.remove(f)
    # v7 C4-c: 의뢰 기준 보장(KB refer_if → 범용 문장)
    if enc.cfg.get('FU_REFER', 1) and not any(_fu_type(f) == '의뢰 기준' for f in fu):
        if (k or {}).get('refer_if'):
            fu.append(f"의뢰 기준 : {k['refer_if']}")
        else:
            src_txt = '\n'.join(disp + list((k or {}).get('treatment') or []) + list((k or {}).get('follow_up') or []))
            spec = next((m for m in re.findall(r'[가-힣]{2,8}과', src_txt) if DEPT_RE.search(m)), '')
            if em['escalate'] and em['dept'] != '해당 전문과':  # 응급 승격 시 추정 진료과('외과'는 위 정규식에 안 걸림)
                spec = em['dept']
            fu.append(f"의뢰 기준 : 검사 이상·증상 악화·치료 반응 부족 시 {spec or '해당 전문과'} 의뢰")
    if em['escalate']:
        fu.append(EMERG_FU)
    fu = dedup_lines([safe_plan_line(f, 'follow_up', admit_if) for f in fu])
    fu = order_follow_up(fu)
    edu_plan = [safe_plan_line(e, 'education', admit_if) for e in (plan.get('education') or [])]
    edu = education_text(enc.explained, '\n'.join(e for e in edu_plan if e))

    def fmt(lst):
        return '\n'.join(f'- {x}' for x in lst if x)
    return {'tests': fmt(tests), 'treatment': fmt(treat), 'disposition': fmt(disp), 'follow_up': fmt(fu),
            'education': edu}

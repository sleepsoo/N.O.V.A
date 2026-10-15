"""환자에게 실제로 말하는 설명 문장(SAY)의 검증·필수 요소 보정. (v2 §8.7 V3·V10, §10.2)"""
from __future__ import annotations

import re

from .util import nfc

MAX_SAY = 30

UNSAFE_RE = re.compile(r'(걱정\s*(안|않|하지\s*마|마세요|없)|괜찮(을|아질)\s*거|꼭\s*낫|완치|확실(히|해)|무조건|문제\s*없|별거\s*아니|'
                       r'재진\s*때\s*(자세히\s*)?설명|나중에\s*(자세히\s*)?설명|서두르겠습니다|치료로\s*치료|'
                       r'진단합니다|확진입니다|확진됐|틀림없)')

FOLLOWUP_RE = re.compile(r'(\d+\s*(?:~\s*\d+\s*)?(일|주|개월|달))\s*(뒤|후|안에|마다|쯤|내)|(다음\s*주|일주일\s*(뒤|후))')
WARN_RE = re.compile(r'바로\s*(오|와|연락|응급|알리|알려|병원|진료)|응급실')
TEST_RE = re.compile(r'(검사|엑스레이|초음파|심전도|MRI|CT|피검사|혈액)')
QUESTION_LINE = '설명 중 이해 안 되거나 궁금한 점 있으세요?'  # 이해 확인 + 질문 기회
GENERIC_WARN = '숨참·흉통·의식 변화·고열 시 바로 오세요.'
GENERIC_FOLLOW = '1~2주 뒤 결과 보고 다음 치료를 정해요.'
GENERIC_TEST = '정확히 확인하려고 피검사를 할게요.'


def say_problem(s: str, *, allow_question=False) -> str:
    """문장이 SAY 규칙을 어기면 이유 문자열, 통과면 ''."""
    t = nfc(s).strip()
    if not t:
        return 'empty'
    if len(t) > MAX_SAY:
        return 'too_long'
    if UNSAFE_RE.search(t):
        return 'unsafe'
    if re.search(r'[A-Za-z]{3,}', re.sub(r'(MRI|CT)', '', t)):
        return 'english'
    if re.search(r'\S{15,}', t):
        return 'no_space'
    if '?' in t and not allow_question:
        return 'question'
    if not allow_question and not re.search(r'(요|다|죠|세요)[.!]?$', t):
        return 'ending'
    return ''


# ---------------------------------------------------------------- v3 질문 검증(서버 전처리 실측: docs/probe_results.md)
# 서버는 SAY에서 질문 한 단위만 환자에게 넘긴다: 공감 접두 삭제, '-고' 연결 절단, 두 질문이면 첫 질문만.
# '다/전부/~부터 지금까지'는 100% '한 번에 하나씩' 거절.
Q_ALL_RE = re.compile(r'(전부|모두|모든|전체|요약|한꺼번에|한\s*번에|다\s*(말씀|알려|얘기|이야기|설명|적어)|부터\s*지금까지|'
                      r'하나하나|나열|이상한\s*것만)')
Q_PAIR_CLAUSE_RE = re.compile(r'(이나|나|와|과|랑)\s+\S*(받은|한|된|난|본|간|있던)\s+적')
Q_TWO_Q_RE = re.compile(r'(요|죠|까|나요|세요)\s*[,，]\s*\S')
Q_PREFIX_RE = re.compile(r'[.!。]\s*\S')
Q_END_RE = re.compile(r'((요|까|세요|나요|가요|죠|니까)\?|(말씀해|얘기해|이야기해|알려|설명해)\s*주(세요|시겠어요\?|실래요\?)|'
                      r'(말씀해|얘기해)\s*보(세요|시겠어요\?))\.?$')
_GO_NOUNS = {'최고', '사고', '참고', '재고', '광고', '창고', '신고', '경고', '보고', '학교', '고고', '중고', '평소고'}


def question_problem(q: str) -> str:
    """v3 문진·확인 질문 SAY 검증. 통과면 '', 아니면 이유.
    한 문장·한 질문, 물음표 ≤1, '-고' 연결 금지, 공감 접두 금지, '다/전부/~부터 지금까지' 금지, 30자 이내."""
    t = nfc(q).strip()
    if not t:
        return 'empty'
    if len(t) > MAX_SAY:
        return 'too_long'
    if t.count('?') > 1:
        return 'multi_q'
    if Q_ALL_RE.search(t):
        return 'all'
    if Q_PREFIX_RE.search(t):
        return 'prefix'
    if Q_TWO_Q_RE.search(t):
        return 'two_q'
    toks = t.rstrip('?.').split()
    for w in toks[:-1]:
        w2 = re.sub(r'[^가-힣]', '', w)
        if w2.endswith('고') and len(w2) >= 2 and w2 not in _GO_NOUNS and not re.search(r'(다|라|냐)고$', w2):
            return 'go_connect'
    if Q_PAIR_CLAUSE_RE.search(t):
        return 'pair_clause'
    if re.search(r'[A-Za-z]{3,}', t):
        return 'english'
    if re.search(r'\S{15,}', t):
        return 'no_space'
    if not Q_END_RE.search(t):
        return 'ending'
    return ''


# ---------------------------------------------------------------- v3 안전 금지 패턴(P칸·설명 SAY 공통)
# 공식 샘플 검증 v2: 안전 15→10. 원인 = 초진 구두·서면 처방 확정, 수치 지시(10~25%, 1~2주분), 특정 약명, '입원 불필요' 단정.
SAFETY_BANS = (
    ('dose', re.compile(r'\d+(?:\.\d+)?\s*(?:~\s*\d+(?:\.\d+)?\s*)?(?:mg|㎎|mcg|μg|ml|mL|cc|IU|단위|%|퍼센트|정\b|정씩|알|'
                        r'캡슐|주분|일분|개월분|회분)')),
    ('prescribe', re.compile(r'(처방합니다|처방할게|처방해\s*(드|요)|처방하겠|처방드|(?<!말씀)(?<!설명)드려요|(?<!말씀)(?<!설명)드릴게|'
                             r'(?<!말씀)(?<!설명)드립니다|드린\s*뒤|시작합니다|시작할게|시작해요|투여합니다|투여할게|복용하세요|'
                             r'드시면\s*돼요)')),
    ('admit', re.compile(r'입원\s*(은\s*)?(불필요|필요\s*없|안\s*해도|하지\s*않아도)')),
    ('drug', re.compile(r'(메티마졸|메티마졸|카비마졸|프로필티오우라실|프로프라놀롤|아테놀롤|레보티록신|씬지로이드|졸피뎀|스틸녹스|'
                        r'알프라졸람|로라제팜|디아제팜|클로나제팜|트라조돈|멜라토닌|에스시탈로프람|설트랄린|플루옥세틴|메트포르민|'
                        r'아목시실린|이부프로펜|아세트아미노펜|타이레놀|오메프라졸|에스오메프라졸|수마트립탄|도네페질|살부타몰|'
                        r'벤조디아제핀\s*(으로|을|를)?\s*(전환|교체|처방))')),
)


def safety_problem(s: str) -> str:
    t = nfc(s)
    for name, pat in SAFETY_BANS:
        if pat.search(t):
            return name
    return ''


# ---------------------------------------------------------------- v4 (docs/v4_spec.md §4.2.2, §4.2.3, §5.2)
V4_FINAL_Q = '설명 중 이해 안 되거나 궁금한 점 있으세요?'
V4_TEACH_BACK = '바로 오셔야 할 증상 하나를 말씀해 보세요'
PAIR_EXEMPT = {V4_FINAL_Q, V4_TEACH_BACK}
# 토큰 끝이 짝 조사처럼 보이지만 짝이 아닌 어휘
PAIR_WORD_EXCEPT = {'얼마나', '언제나', '누구나', '아무나', '하나', '결과', '효과', '내과', '외과', '누나', '사랑', '그나마', '어디나',
                    '진료과', '소아과', '정신과', '이비인후과', '산부인과', '피부과', '안과', '치과', '그나', '조금이나마'}
PAIR_END_RE = re.compile(r'(이나|나|와|과|랑|하고)$')
PAIR_COMPARE_RE = re.compile(r'^(비슷|같|다르|달라|달랐|비교|차이)')
# 조정자 결정 1(negscreen): 음성이 예상되는 선별용 배경 항목 짝만 허용(화이트리스트, 정확히 이 문구)
NEGSCREEN_PAIRS = ('고혈압이나 당뇨 있으세요?', '결핵이나 간염 앓은 적 있으세요?', '수술이나 입원 경험 있으세요?',
                   '약이나 음식 알레르기 있으세요?', '가족 중 고혈압이나 당뇨 있나요?')


def _qnorm(q: str) -> str:
    return re.sub(r'\s+', '', nfc(q or '')).rstrip('?.')


_NEGSCREEN_KEYS = {_qnorm(q) for q in NEGSCREEN_PAIRS}


def pair_problem(q: str, policy: str = 'strict') -> str:
    """단일 항목 강제. 짝('A나 B', 'A와 B', 'A·B', 'A, B', '~거나')이면 이유, 통과면 ''.
    FINAL_Q·TEACH_BACK 면제. policy='negscreen'이면 NEGSCREEN_PAIRS 화이트리스트 문구는 허용."""
    t = nfc(q or '').strip()
    if not t or t in PAIR_EXEMPT:
        return ''
    if policy == 'negscreen' and _qnorm(t) in _NEGSCREEN_KEYS:
        return ''
    if re.search(r'[가-힣A-Za-z0-9)]\s*[·,/]\s*[가-힣A-Za-z]', t):
        return 'pair_list'
    toks = t.rstrip('?.!').split()
    for i, w in enumerate(toks[:-1]):
        w2 = re.sub(r'[^가-힣]', '', w)
        if not w2:
            continue
        if w2.endswith('거나') and len(w2) >= 3:
            return 'pair_geona'
        if w2 in PAIR_WORD_EXCEPT or len(w2) < 2:
            continue
        if i > 0 and re.sub(r'[^가-힣]', '', toks[i - 1]) == '몇' and w2.endswith('이나'):  # '몇 번이나'
            continue
        if PAIR_END_RE.search(w2):
            nxt = re.sub(r'[^가-힣]', '', toks[i + 1])
            if PAIR_COMPARE_RE.search(nxt):  # '또래와 비슷했나요?' 비교 구문
                continue
            if w2.endswith('하고') and len(w2) <= 3 and not nxt:
                continue
            return 'pair'
    return ''


def statement_ok(s: str) -> bool:
    """설명·답 서술문 검증(§5.6): say_problem·safety_problem 0, safe_say가 SAFE_SAY로 바꾸지 않음."""
    t = nfc(s or '').strip()
    if not t or say_problem(t) or safety_problem(t):
        return False
    from .explain import SAFE_SAY, safe_say
    return safe_say(t) != SAFE_SAY


# sweep 답 → 주제 명사(§4.2.3). 앞쪽이 우선. 짝 금지: 하나만
SYMPTOM_NOUN = [
    (r'두근', '두근거림'), (r'떨(리|려|림)', '손 떨림'), (r'숨(이)?\s?차', '숨찬 증상'), (r'어지(럽|러|럼)', '어지럼'),
    (r'졸(리|려|림)', '낮 졸림'), (r'피곤|피로|지치', '피로'), (r'기침', '기침'), (r'가래', '가래'),
    (r'토(했|해)|구토', '구토'), (r'메스껍|메스꺼|울렁', '메스꺼움'), (r'설사|묽', '대변 변화'), (r'변비', '변비'),
    (r'배(가)?\s?아|복통', '배 아픈 것'), (r'머리(가)?\s?아|두통', '두통'), (r'가슴(이)?\s?아|흉통', '가슴 통증'),
    (r'더위|더워', '더위 타는 것'), (r'땀', '땀'), (r'잠|불면|못\s*자', '잠'), (r'기억', '기억력'), (r'집중', '집중력'),
    (r'짜증|예민', '예민해진 것'), (r'불안', '불안'), (r'우울|기분', '기분'), (r'붓|부종|부었|부어', '붓는 증상'),
    (r'저려|저림|저리', '저림'), (r'가려', '가려움'), (r'소변|오줌', '소변'), (r'생리|월경', '생리'), (r'눈', '눈 증상'),
    (r'목(이|에|도)?\s', '목 증상'), (r'열(이)?\s?(나|있|났)|발열|고열', '열'),
]


def symptom_topic(reply: str, asked=()) -> str:
    """sweep 답에서 새 증상 명사 하나(이미 물은 주제면 다음 후보). 없으면 ''."""
    r = nfc(reply or '')
    asked_txt = ' '.join(asked or [])
    for pat, noun in SYMPTOM_NOUN:
        if re.search(pat, r):
            if f'{noun}에 대해' in asked_txt or noun in asked_txt:
                continue
            return noun
    return ''


def is_patient_question(reply: str) -> bool:
    """설명 단계 환자 답이 질문·두려움인지(§5.3): v2 is_question + 두려움 + '까요|나요|건가요|?' 끝."""
    from .explain import is_question
    r = nfc(reply or '').strip()
    if not r:
        return False
    if is_question(r):
        return True
    if re.search(r'(두려|무서|걱정돼|걱정이\s*돼|불안해)', r):
        return True
    return bool(re.search(r'(까요|나요|건가요|\?)[.!]?$', r))


def norm_line(s: str) -> str:
    return re.sub(r'[\s\-–—·,.:;()\[\]~/]+', '', nfc(s))


def dedup_lines(lines) -> list:
    """정규화 중복·유사 줄 제거(앞의 것 유지)."""
    out, keys = [], []
    for l in lines or []:
        k = norm_line(l)
        if not k or k in keys or any(k in x or x in k for x in keys if min(len(k), len(x)) >= 12):
            continue
        out.append(l)
        keys.append(k)
    return out


def warn_count(lines) -> int:
    n = 0
    for s in lines:
        if WARN_RE.search(s):
            body = re.split(r'(이|가|이나|면|시|때)?\s*(바로|응급실)', s)[0]
            parts = [p for p in re.split(r'[·,]|이나\s|나\s|거나\s|또는', body) if p.strip()]
            n += max(1, len(parts))
    return n


def dx_keywords(dx_ko: str) -> list[str]:
    d = re.sub(r'\(.*?\)', '', nfc(dx_ko or ''))
    words = [w for w in re.split(r'[\s·,]+', d) if len(w) >= 2]
    keys = []
    for w in words:
        w2 = re.sub(r'(에\s*의한|으로\s*인한|증|병|장애)$', '', w)
        for k in (w, w2, w[:2]):
            if k and len(k) >= 2 and k not in keys:
                keys.append(k)
    syn = {'갑상샘': '갑상선', '갑상선': '갑상샘'}
    for k in list(keys):
        for a, b in syn.items():
            if a in k:
                keys.append(k.replace(a, b))
    return keys


def missing_elements(lines, dx_ko: str) -> list[str]:
    text = ' '.join(lines)
    miss = []
    keys = dx_keywords(dx_ko)
    if keys and not any(k in text for k in keys):
        miss.append('dx')
    if not TEST_RE.search(text):
        miss.append('tests')
    if warn_count(lines) < 4:
        miss.append('warning')
    if not FOLLOWUP_RE.search(text):
        miss.append('followup')
    return miss


def ensure_elements(lines: list[str], dx_ko: str, *, kb_say=None, red_flags_say='', max_lines=9, log=None,
                    keep=None) -> list[str]:
    """필수 요소(진단·검사·경고 4개+·재진 시점)를 보장. 마지막 줄은 '더 궁금하신 점 있으세요?'."""
    body = [l for l in lines if l and l != QUESTION_LINE and '?' not in l]
    kb_say = [s for s in (kb_say or []) if not say_problem(s)]
    miss = missing_elements(body, dx_ko)
    fixes = []
    for m in miss:
        cand = None
        if m == 'dx':
            short = re.sub(r'\(.*?\)', '', dx_ko or '').strip()
            for c in (f'{short} 가능성이 높아 보여요.', '말씀과 진찰로 원인이 짐작돼요.'):
                if not say_problem(c):
                    cand = c
                    break
            if cand:
                body.insert(0, cand)
                fixes.append(m)
            continue
        if m == 'tests':
            cand = next((s for s in kb_say if TEST_RE.search(s)), GENERIC_TEST)
        elif m == 'warning':
            cand = red_flags_say if red_flags_say and not say_problem(red_flags_say) else None
            cand = cand or next((s for s in kb_say if WARN_RE.search(s) and warn_count([s]) >= 3), None) or GENERIC_WARN
            if warn_count(body + [cand]) < 4 and cand != GENERIC_WARN:
                body.append(cand)
                cand = GENERIC_WARN
        elif m == 'followup':
            cand = next((s for s in kb_say if FOLLOWUP_RE.search(s)), GENERIC_FOLLOW)
        if cand and cand not in body:
            body.append(cand)
            fixes.append(m)
    # 자리 맞추기: 넘치면 앞쪽의 필수 아닌 문장부터 뺀다
    limit = max_lines - 1
    keep = keep or []

    def cat(s):
        if s in keep:
            return 'keep'
        if WARN_RE.search(s):
            return 'warn'
        if FOLLOWUP_RE.search(s):
            return 'follow'
        if TEST_RE.search(s):
            return 'test'
        return ''
    while len(body) > limit:
        cats = [cat(s) for s in body]
        drop = next((i for i in range(len(body) - 1, 0, -1) if not cats[i]), None)
        if drop is None:  # 같은 종류가 2개 이상인 것(예: 검사 문장 2개) 중 뒤의 것
            drop = next((i for i in range(len(body) - 1, 0, -1)
                         if cats[i] not in ('keep',) and cats.count(cats[i]) > 1), None)
        if drop is None:
            drop = next((i for i in range(len(body) - 1, 0, -1) if cats[i] != 'keep'), len(body) - 1)
        body.pop(drop)
    if log and fixes:
        log(f'say fixes: {fixes}')
    return body + [QUESTION_LINE]

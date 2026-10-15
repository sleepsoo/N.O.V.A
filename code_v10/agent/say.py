"""환자에게 실제로 말하는 설명 문장(SAY)의 검증·필수 요소 보정. (v2 §8.7 V3·V10, §10.2)"""
from __future__ import annotations

import re

from .util import nfc

MAX_SAY = 30

UNSAFE_RE = re.compile(r'(걱정\s*(안|않|하지\s*마|마세요|없)|괜찮(을|아질)\s*거|꼭\s*낫|완치|확실(히|해)|무조건|문제\s*없|별거\s*아니|'
                       r'재진\s*때\s*(자세히\s*)?설명|나중에\s*(자세히\s*)?설명|서두르겠습니다|치료로\s*치료|'
                       r'진단합니다|확진입니다|확진됐|틀림없)')

FOLLOWUP_RE = re.compile(r'(\d+\s*(?:~\s*\d+\s*)?(일|주|개월|달))\s*(뒤|후|안에|마다|쯤|내)|(다음\s*주|일주일\s*(뒤|후))')
WARN_RE = re.compile(r'바로\s*(오|와|연락|응급)|응급실')
TEST_RE = re.compile(r'(검사|엑스레이|초음파|심전도|MRI|CT|피검사|혈액)')
QUESTION_LINE_BASE = '더 궁금하신 점 있으세요?'
QUESTION_LINE_V11 = '이해 안 되시거나 더 궁금하신 점 있으세요?'   # v11a: 이해 확인 겸 질문 기회
QUESTION_LINE = QUESTION_LINE_BASE
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


# ---------------------------------------------------------------- v8c: 조사 띄어쓰기 정리 + 슬롯별 품질 게이트
_PARTICLE_RE = re.compile(r'(?<=[가-힣A-Za-z0-9)])\s+(으로|을|를|이|가|은|는|와|과|로|의|에|도)(?=[\s.,!?·]|$)')
_AFTER_BATCHIM = {'을', '이', '은', '과', '으로'}      # 받침 뒤에만 붙는 조사
_AFTER_VOWEL = {'를', '가', '는', '와'}               # 받침 없을 때만 붙는 조사('로'는 ㄹ받침도 허용)
_PARTICLE_CHARS = set('을를이가은는와과로의에도')


def _batchim(ch: str):
    """한글 음절이면 (받침 있음, ㄹ받침) 튜플, 아니면 None."""
    o = ord(ch) - 0xAC00
    if not 0 <= o < 11172:
        return None
    jong = o % 28
    return jong != 0, jong == 8


def tidy(s: str) -> str:
    """'피검사·초음파 를' → '피검사·초음파를'. 앞 글자와 받침이 맞는 조사만 붙인다('검사 후'·'2주 뒤'·'약은 이 정도' 불변)."""
    t = nfc(s or '')

    def fix(m):
        prev = t[m.start() - 1] if m.start() > 0 else ''
        p = m.group(1)
        if p == '이' and prev in _PARTICLE_CHARS:   # '약은 이 정도': 앞 어절이 조사로 끝나면 '이'는 관형사
            return m.group(0)
        b = _batchim(prev)
        if b is not None:
            has, rieul = b
            if p in _AFTER_BATCHIM and not has:
                return m.group(0)
            if p in _AFTER_VOWEL and has:
                return m.group(0)
            if p == '로' and has and not rieul:
                return m.group(0)
        return p
    t = _PARTICLE_RE.sub(fix, t)
    t = re.sub(r'(?<=\S)\s+([.,!?])(?=\s|$)', r'\1', t)
    return re.sub(r'[ \t]{2,}', ' ', t).strip()


CAUSAL_RE = re.compile(r'(때문|으로|해서|면서|원인|탓|넘쳐|늦게|익숙해)')
WORRY_RE = re.compile(r'(걱정|암|큰\s*병|가능성|보다|소견)')
PURPOSE_RE = re.compile(r'(확인|알아보|보려고|위해|원인|수치|정도)')
TREAT_RE = re.compile(r'(약|치료|수술|조절|관찰|요법|상담|줄여)')
LIFE_RE = re.compile(r'(줄이|줄여|피하|피해|쉬세요|쉬어|쉬고|운동|금지|조심|지키|챙기|무리|금연|드세요|하세요|주세요|보세요|쓰세요|'
                     r'도움\s*돼|좋아요)')
SLOT_PRIO = {'life': 10, 'mech': 20, 'worry': 30, 'treat': 60, 'tests': 70, 'warn': 90, 'dx': 100}


def _ctx_dx(ctx) -> str:
    if ctx is None:
        return ''
    if isinstance(ctx, str):
        return ctx
    if isinstance(ctx, dict):
        return ctx.get('dx') or ''
    return getattr(ctx, 'dx', '') or ''


def slot_problem(slot: str, text: str, ctx=None) -> str:
    """슬롯 문장 품질 게이트: 통과면 '', 아니면 이유. ctx는 enc·{'dx':..}·진단 문자열."""
    t = nfc(text or '').strip()
    p = say_problem(t)
    if p:
        return p
    if slot == 'dx':
        keys = dx_keywords(_ctx_dx(ctx))
        if keys and not any(k in t for k in keys):
            return 'dx_missing'
    elif slot == 'mech':
        if re.search(r'정상(이에요|입니다|이에요\.|이네요)[.!]?$', t):
            return 'mech_findings'
        if not CAUSAL_RE.search(t):
            return 'mech_no_cause'
    elif slot == 'worry':
        if not WORRY_RE.search(t):
            return 'worry_missing'
    elif slot == 'tests':
        if not TEST_RE.search(t):
            return 'tests_missing'
        if not PURPOSE_RE.search(t):
            return 'tests_no_purpose'
    elif slot == 'treat':
        if not TREAT_RE.search(t):
            return 'treat_missing'
    elif slot == 'warn':
        if not WARN_RE.search(t) or warn_count([t]) < 3:
            return 'warn_few'
    elif slot == 'life':
        if not (FOLLOWUP_RE.search(t) or LIFE_RE.search(t)):
            return 'life_missing'
    return ''


def guess_slot(text: str, dx_ko: str = '') -> str:
    """슬롯 태그가 없는 줄(폴백 경로)의 슬롯 추정."""
    t = nfc(text or '')
    if WARN_RE.search(t):
        return 'warn'
    if TEST_RE.search(t):
        return 'tests'
    keys = dx_keywords(dx_ko)
    if keys and any(k in t for k in keys) and re.search(r'(가능성|같아요|보여요|의심)', t):
        return 'dx'
    if re.search(r'(약|치료|수술|조절|요법|상담)', t) and not CAUSAL_RE.search(t):
        return 'treat'
    if WORRY_RE.search(t):
        return 'worry'
    if CAUSAL_RE.search(t):
        return 'mech'
    return 'life'


EMPATHY_RE = re.compile(r'(걱정|힘드|힘들|고생|불편|속상|애쓰|많이\s*놀라)')
WORRY_WORD_RE = re.compile(r'(암|당뇨|치매|심장병|뇌졸중|중독|큰\s*병|나쁜\s*병)')


def _ice_text(enc) -> str:
    return ' '.join(e.get('reply') or '' for e in getattr(enc, 'ledger', []) or []
                    if str(e.get('qid', '')).startswith('ice') and not e.get('refused'))


def ensure_v8(lines: list[str], enc, keep=None) -> list[str]:
    """v8 설명 요소 보정: ① 첫 문장 공감(평서문, 서버 절단 없음) ② 환자가 말한 걱정 질환에 대한 직접 답(근거 표현)."""
    out = [l for l in lines if l]
    if out and not EMPATHY_RE.search(out[0]):
        for pre in ('많이 걱정되셨죠, ', '걱정되셨죠, '):
            cand = pre + out[0]
            if not say_problem(cand):
                out[0] = cand
                break
    m = WORRY_WORD_RE.search(_ice_text(enc))
    if m:
        w = re.sub(r'\s+', ' ', m.group(1)).strip()
        if not any(w in s or '걱정하신' in s for s in out):
            short = re.sub(r'\(.*?\)', '', getattr(enc, 'dx', '') or '').strip()
            short = re.split(r'에\s*의한|으로\s*인한', short)[-1].strip()
            cands = [f'걱정하신 {w}보다 {short} 가능성이 높아요.', f'걱정하신 {w}도 검사로 함께 확인해요.',
                     '걱정하신 병도 검사로 함께 확인해요.']
            cand = next((c for c in cands if short and not say_problem(c)), None) or \
                next((c for c in cands[1:] if not say_problem(c)), None)
            if cand:
                out.insert(min(2, len(out)), cand)
                if keep is not None:
                    keep.append(cand)   # 자리 맞추기에서 걱정 직답이 먼저 빠지지 않게
    return out


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
        if drop is None:  # v8: 마지막 수단도 경고 문장은 가장 나중에 뺀다(검사 → 재진 → 경고 순)
            rank = {'': 0, 'test': 1, 'follow': 2, 'warn': 3}
            cand = [(rank.get(cats[i], 9), -i) for i in range(1, len(body)) if cats[i] != 'keep']
            drop = -min(cand)[1] if cand else len(body) - 1
        body.pop(drop)
    if log and fixes:
        log(f'say fixes: {fixes}')
    return body + [QUESTION_LINE]

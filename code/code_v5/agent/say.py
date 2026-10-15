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
QUESTION_LINE = '더 궁금하신 점 있으세요?'
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

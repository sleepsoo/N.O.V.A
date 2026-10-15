"""공통 유틸: NFC 길이 검증, 한국어 숫자 파서, 관대한 JSON 파서, 유사 질문 판정, 로깅."""
from __future__ import annotations

import json
import re
import sys
import time
import unicodedata

MAX_CHARS = 30
_START = time.time()
_ERRORS: list[str] = []


# ---------------------------------------------------------------- logging
def log(msg: str) -> None:
    """stderr로 간결하게. 서버는 stderr 마지막 30줄만 보여 준다."""
    try:
        sys.stderr.write(f'[{time.time() - _START:6.1f}s] {msg}\n')
        sys.stderr.flush()
    except Exception:  # pragma: no cover
        pass


def log_error(msg: str) -> None:
    _ERRORS.append(msg)
    log('ERROR ' + msg)


def error_summary() -> list[str]:
    return list(_ERRORS[-12:])


# ---------------------------------------------------------------- text length
def nfc(text) -> str:
    return unicodedata.normalize('NFC', str(text or ''))


def clen(text) -> int:
    return len(nfc(text))


def fits(text, limit: int = MAX_CHARS) -> bool:
    t = nfc(text).strip()
    return 0 < len(t) <= limit


def split_to_fit(text, limit: int = MAX_CHARS) -> list[str]:
    """긴 문장을 어절 경계에서 limit 이하 조각으로 나눈다(최후 수단)."""
    words = nfc(text).split()
    out, cur = [], ''
    for w in words:
        if len(w) > limit:
            if cur:
                out.append(cur)
                cur = ''
            while len(w) > limit:
                out.append(w[:limit])
                w = w[limit:]
            cur = w
            continue
        cand = (cur + ' ' + w).strip()
        if len(cand) <= limit:
            cur = cand
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    return [o for o in out if o.strip()]


# ---------------------------------------------------------------- Korean numbers
_NATIVE_TENS = {'열': 10, '스물': 20, '스무': 20, '서른': 30, '마흔': 40, '쉰': 50, '예순': 60,
                '일흔': 70, '여든': 80, '아흔': 90}
_NATIVE_ONES = {'하나': 1, '한': 1, '둘': 2, '두': 2, '셋': 3, '세': 3, '석': 3, '서': 3, '넷': 4, '네': 4,
                '넉': 4, '너': 4, '다섯': 5, '여섯': 6, '일곱': 7, '여덟': 8, '아홉': 9}
_SINO_DIGITS = {'영': 0, '공': 0, '일': 1, '이': 2, '삼': 3, '사': 4, '오': 5, '육': 6, '륙': 6, '칠': 7,
                '팔': 8, '구': 9}
_SINO_UNITS = {'십': 10, '백': 100, '천': 1000}


def parse_native(word: str):
    """'예순두' -> 62, '여섯' -> 6, '스무' -> 20, '서른일곱' -> 37. 실패 시 None."""
    w = word.strip()
    if not w:
        return None
    total = 0
    for tens in sorted(_NATIVE_TENS, key=len, reverse=True):
        if w.startswith(tens):
            total = _NATIVE_TENS[tens]
            w = w[len(tens):]
            break
    if w:
        if w in _NATIVE_ONES:
            total += _NATIVE_ONES[w]
        else:
            return None
    return total or None


def parse_sino(word: str):
    """'육십이' -> 62, '백오' -> 105, '십육 점 오' -> 16.5. 실패 시 None."""
    w = re.sub(r'\s+', '', word)
    if not w:
        return None
    if '점' in w:
        a, _, b = w.partition('점')
        ia = parse_sino(a) if a else 0
        if ia is None or not b or any(ch not in _SINO_DIGITS for ch in b):
            return None
        frac = ''.join(str(_SINO_DIGITS[ch]) for ch in b)
        return float(f'{int(ia)}.{frac}')
    total, cur = 0, 0
    seen = False
    for ch in w:
        if ch in _SINO_DIGITS:
            cur = _SINO_DIGITS[ch]
            seen = True
        elif ch in _SINO_UNITS:
            total += (cur or 1) * _SINO_UNITS[ch]
            cur = 0
            seen = True
        else:
            return None
    return (total + cur) if seen else None


def parse_korean_number(word: str):
    w = nfc(word).strip()
    if re.fullmatch(r'\d+(\.\d+)?', w):
        return float(w) if '.' in w else int(w)
    for fn in (parse_native, parse_sino):
        v = fn(w)
        if v is not None:
            return v
    return None


def parse_age(text: str):
    """시작 정보에서 첫 번째 나이(정수, 개월이면 소수 연령)를 찾는다."""
    t = nfc(text)
    m = re.search(r'(\d+)\s*(?:살|세)', t)
    cand = []
    if m:
        cand.append((m.start(), int(m.group(1))))
    for m2 in re.finditer(r'([가-힣]{1,6})\s*(?:살|세)(?![가-힣]*니다)', t):
        word = m2.group(1)
        # 앞에 붙은 조사·관형어 제거를 위해 뒤쪽부터 가장 긴 숫자 단어를 찾는다
        for i in range(len(word)):
            v = parse_korean_number(word[i:])
            if v is not None and 0 < v < 130:
                cand.append((m2.start() + i, int(v)))
                break
    m3 = re.search(r'(?:생후\s*)?(\d+|[가-힣]{1,4})\s*개월\s*(?:된|짜리)?\s*(?:남아|여아|아기|아이|남자|여자)', t)
    if m3:
        v = parse_korean_number(m3.group(1))
        if v is not None:
            cand.append((m3.start(), round(float(v) / 12, 2)))
    if not cand:
        return None
    cand.sort()
    return cand[0][1]


def parse_sex(text: str):
    t = nfc(text)
    pos_f = min([t.find(w) for w in ('여자', '여성', '여아', '딸') if t.find(w) >= 0] or [10 ** 6])
    pos_m = min([t.find(w) for w in ('남자', '남성', '남아', '아들') if t.find(w) >= 0] or [10 ** 6])
    if pos_f == pos_m == 10 ** 6:
        return ''
    return 'F' if pos_f < pos_m else 'M'


def extract_numbers(text: str) -> set[str]:
    """아라비아 숫자와 한국어 수사를 정규화한 숫자 문자열 집합."""
    t = nfc(text)
    t = re.sub(r'([가-힣]+)\s+점\s+([일이삼사오육칠팔구영공])', r'\1점\2', t)
    out = set()
    for m in re.finditer(r'(?<![가-힣])([백천십])(?![가-힣])', t):
        out.add(str(_SINO_UNITS[m.group(1)]))
    for m in re.finditer(r'\d+(?:\.\d+)?', t):
        out.add(_norm_num(m.group(0)))
    for m in re.finditer(r'[가-힣]+', t):
        w = m.group(0)
        if len(w) <= 2:  # '칠 키로', '석 달', '두세 시간' 같은 한 글자 수사
            for ch in w:
                if ch in _SINO_DIGITS:
                    out.add(str(_SINO_DIGITS[ch]))
                if ch in _NATIVE_ONES:
                    out.add(str(_NATIVE_ONES[ch]))
        for i in range(len(w)):
            for j in range(len(w), i, -1):
                piece = w[i:j]
                if len(piece) < 1:
                    continue
                v = parse_native(piece) if len(piece) >= 2 or piece in ('열',) else None
                if v is None and len(piece) >= 2:
                    v = parse_sino(piece)
                if v is not None:
                    out.add(_norm_num(str(v)))
    return out


def _norm_num(s: str) -> str:
    try:
        f = float(s)
    except ValueError:
        return s
    return str(int(f)) if f == int(f) else str(f)


# ---------------------------------------------------------------- JSON
def _clean_json_text(text: str) -> str:
    t = text.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    t = t.replace("\\'", "'")
    t = re.sub(r':\s*([,}])', r': null\1', t)
    t = re.sub(r',\s*([}\]])', r'\1', t)
    return t


def parse_json(text, want=None):
    """모델 출력에서 첫 JSON 값을 꺼낸다. want=dict|list로 형을 고를 수 있다."""
    if not text:
        return None
    raw = str(text)
    blocks = re.findall(r'```(?:json)?\s*(.*?)```', raw, flags=re.S)
    candidates = blocks + [raw]
    decoder = json.JSONDecoder()
    for cand in candidates:
        for variant in (cand, _clean_json_text(cand)):
            for m in re.finditer(r'[\[{]', variant):
                try:
                    value, _ = decoder.raw_decode(variant, m.start())
                except ValueError:
                    continue
                if want is None and isinstance(value, (dict, list)):
                    return value
                if want is not None and isinstance(value, want):
                    return value
    return None


def as_text(value) -> str:
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return '\n'.join(as_text(v) for v in value if as_text(v).strip())
    if isinstance(value, dict):
        return '\n'.join(f'{k} : {as_text(v)}' for k, v in value.items())
    return str(value)


def as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [s for s in re.split(r'\n+', value) if s.strip()]
    return [value]


# ---------------------------------------------------------------- similarity
def _key(text: str) -> str:
    t = nfc(text).lower()
    t = re.sub(r'[\s?.!,·~\-()"\']+', '', t)
    for suf in ('있으세요', '있나요', '있어요', '하세요', '세요', '나요', '어요', '아요', '습니까', '니까', '요'):
        if t.endswith(suf) and len(t) > len(suf) + 2:
            t = t[:-len(suf)]
            break
    return t


def bigrams(text: str) -> set[str]:
    t = _key(text)
    return {t[i:i + 2] for i in range(len(t) - 1)} or {t}


def _jac(ga: set, gb: set) -> float:
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def _strip_particles(t: str) -> str:
    return re.sub(r'[는은을를도]', '', t)


def similarity(a: str, b: str) -> float:
    s1 = _jac(bigrams(a), bigrams(b))
    ka, kb = _strip_particles(_key(a)), _strip_particles(_key(b))
    s2 = _jac({ka[i:i + 2] for i in range(len(ka) - 1)} or {ka}, {kb[i:i + 2] for i in range(len(kb) - 1)} or {kb})
    return max(s1, s2)


_PERSON = re.compile(r'(가족|어머니|아버지|엄마|아빠|부모|형제|자매|할머니|할아버지|친척|남편|아내|아이|친구|주변)')


def _persons(t: str) -> set:
    return set(_PERSON.findall(nfc(t)))


def is_similar(q: str, asked: list[str], threshold: float = 0.5) -> bool:
    kq = _key(q)
    pq = _persons(q)
    for a in asked:
        ka = _key(a)
        if not ka:
            continue
        if pq != _persons(a):
            continue
        if kq == ka or (len(kq) >= 5 and kq in ka) or (len(ka) >= 5 and ka in kq):
            return True
        if similarity(q, a) >= threshold:
            return True
    return False


# ---------------------------------------------------------------- question validator
FORBIDDEN = re.compile(r'(전부|모두|모든|전체|요약|한꺼번에|한번에|다\s*말씀|다\s*알려|다\s*얘기|이상한\s*것만|이상\s*소견만|'
                       r'진단명|무슨\s*병|어떤\s*병인|병명|정리해|나열|목록)')
MULTI = re.compile(r'(있나요\s*없나요|있으세요\s*없으세요|그리고|또한|및\s)')


def validate_question(q, asked: list[str] | None = None) -> tuple[bool, str]:
    """(통과 여부, 이유). 30자, 물음표 1개 이하, 금지어, 복수 질문, 중복."""
    t = nfc(q).strip()
    if not t:
        return False, 'empty'
    if len(t) > MAX_CHARS:
        return False, 'too_long'
    if t.count('?') > 1:
        return False, 'multi_q'
    if FORBIDDEN.search(t):
        return False, 'forbidden'
    if MULTI.search(t):
        return False, 'multi'
    if t.count(',') >= 2 or t.count('·') >= 2 or t.count('/') >= 1:
        return False, 'list'
    if re.search(r'[a-zA-Z]{4,}', t):
        return False, 'english'
    if re.search(r'[가-힣]{10,}', t) or re.search(r'\S{15,}', t):  # 띄어쓰기 없이 붙여 쓴 질문(숫자·영문 포함)
        return False, 'too_long'
    if not re.search(r'(요|까|세요|나요|가요|죠|니까)\?$', t):  # 존댓말 의문문
        return False, 'ending'
    if asked and is_similar(t, asked):
        return False, 'duplicate'
    return True, 'ok'


ONE_AT_A_TIME_RE = re.compile(r'한\s*번에\s*하나씩')


def is_one_at_a_time(reply: str) -> bool:
    return bool(ONE_AT_A_TIME_RE.search(nfc(reply)))

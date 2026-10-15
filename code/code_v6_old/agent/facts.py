"""v2 사실표: 문답에서 사실(F#)을 추출(luna medium) → 코드 검증(턴·고정 키 어휘 단서·숫자). (v2_spec §8.5, §9.1)"""
from __future__ import annotations

import re

from . import bank2
from .llm import ask_json
from .util import extract_numbers, log, nfc

ROLE = '당신은 한국 대학병원 외래의 숙련된 전문의입니다. 문진 결과를 의무기록용 사실표로 정리합니다. JSON 하나만 출력하세요.'
INTERVIEW_PHASES = ('first', 'interview', 'ice', 'interview-single', 'first-single', 'hpi', 'bundle', 'history', 'ros',
                    'adaptive1', 'adaptive2', 'ice-single')
SECS = ('hpi', 'pmh', 'meds', 'fh', 'sh', 'ros', 'women', 'peds', 'psych', 'ice')


EXPLAIN_PHASES = ('explain', 'explain-answer')
# v6: 설명 단계 환자 발언 중 단순 수긍·인사·'없어요'만 거른다(사실 아님)
_ACK = (r'(네|예|응|아|알겠습니다|알겠어요|알았어요|감사합니다|감사해요|고맙습니다|다행이네요|다행이에요|좋아요|그렇군요|'
        r'그럴게요|그렇게\s*할게요|명심할게요|조심할게요|꼭\s*올게요|바로\s*올게요|검사\s*받을게요|괜찮아요|아니(요|오)|아뇨|'
        r'없어요|없습니다|(그런|그런\s*건|궁금한\s*(건|거|점은?)|더는?)\s*없어요)')
ACK_RE = re.compile(rf'\s*{_ACK}(?:[\s,.!~]*{_ACK})*[\s,.!~]*')
# 되말하기(teach-back) 답이 설명 내용을 되풀이한 것이면 환자 병력이 아님
RECALL_RE = re.compile(r'(와야|오면|가야|올게|응급실|병원에|바로)')
ICE_RE = re.compile(r'(\?|궁금|걱정|불안|두려|무서|까요|[하되있없]나요|[건인]가요|싶어요|원해요|바라|좋겠)')
# '네, 천천히 줄여볼게요', '아, 그래서 그런 거군요', '조금 안심이 되네요' 같은 수긍·다짐
COMPLY_RE = re.compile(r'(게요|군요|(안심이\s*되|다행이|좋|감사하|고맙)네요)[.!~]*$')


def is_ack(answer: str) -> bool:
    a = nfc(answer or '').strip()
    return bool(ACK_RE.fullmatch(a)) or (bool(COMPLY_RE.search(a)) and not ICE_RE.search(a))


def explain_row(e) -> dict | None:
    """설명 단계 SAY 한 줄 → 사실 추출용 행(수긍·되말하기면 None). 질문·기대는 slot 'ice-explain'."""
    a = nfc(e.get('reply') or '').strip()
    if not a or is_ack(a) or RECALL_RE.search(a):
        return None
    ice = bool(ICE_RE.search(a))
    return {'turn': e['turn'], 'q': '[설명 단계] ' + e['text'], 'a': a, 'slot': 'ice-explain' if ice else 'explain',
            'label': '마지막 질문·기대' if ice else '설명 중 추가 진술'}


def qa_rows(enc) -> list[dict]:
    rows = []
    for e in enc.ledger:
        if e['kind'] != 'SAY' or e.get('refused'):
            continue
        if e.get('phase') in EXPLAIN_PHASES:
            r = explain_row(e)
            if r:
                rows.append(r)
            continue
        if e.get('phase') == 'empathy':
            continue
        rows.append({'turn': e['turn'], 'q': e['text'], 'a': e.get('reply') or '', 'slot': e.get('qid') or '',
                     'label': e.get('label') or ''})
    return rows


def explain_facts(enc) -> list:
    """사실 추출(facts.extract)은 설명 전에 끝나므로, 설명 단계 행은 규칙으로 사실화해 enc.facts에 덧붙인다(멱등)."""
    facts = list(getattr(enc, 'facts', None) or [])
    have = {f['turn'] for f in facts}
    for r in qa_rows(enc):
        if r['slot'] not in ('explain', 'ice-explain') or r['turn'] in have:
            continue
        det = re.sub(r'^(네|예|아니요|아뇨)[,.\s]+', '', r['a'])
        det = re.sub(r'\s*(이었어요|였어요|이에요|예요|였다)\.?$', '', det).rstrip('. ')
        if len(det) > 30:
            det = det[:29].rsplit(' ', 1)[0] + '…'
        facts.append({'turn': r['turn'], 'sec': 'ice' if r['slot'] == 'ice-explain' else 'hpi', 'key': 'other',
                      'label': r['label'][:16], 'pol': '?', 'detail': det})
    for i, f in enumerate(facts, 1):
        f['id'] = f'F{i}'
    enc.facts = facts
    return facts


def _source(enc, rows, turn: int) -> str:
    if turn == 0:
        return enc.opening
    for r in rows:
        if r['turn'] == turn:
            return r['q'] + ' ' + r['a']
    return ''


def _answer(enc, rows, turn: int) -> str:
    if turn == 0:
        return enc.opening
    for r in rows:
        if r['turn'] == turn:
            return r['a']
    return ''


def _short(a: str) -> str:
    t = re.sub(r'^(네|예|아니요|아뇨|응)[,.\s]*', '', nfc(a).strip())
    return t[:20]


def validate(enc, rows, raw: list) -> list[dict]:
    turns = {0} | {r['turn'] for r in rows}
    out = []
    n = 0
    for f in raw or []:
        if not isinstance(f, dict):
            continue
        try:
            turn = int(f.get('turn'))
        except (TypeError, ValueError):
            continue
        if turn not in turns:
            continue
        key = nfc(str(f.get('key') or 'other')).strip()
        pol = str(f.get('pol') or '?').strip()
        pol = pol if pol in ('+', '-', '?') else '?'
        label = nfc(str(f.get('label') or '')).strip()[:16]
        detail = nfc(str(f.get('detail') or '')).strip()[:30]
        sec = str(f.get('sec') or 'hpi').strip()
        sec = sec if sec in SECS else 'hpi'
        src = _source(enc, rows, turn)
        # 고정 키: 그 턴의 질문/답(턴 0이면 시작 정보)에 어휘 단서가 있어야 함. fh.*는 가족 호칭도 필요
        if key in bank2.FIXED_KEYS:
            ok = re.search(bank2.FIXED_KEYS[key], src)
            if ok and key.startswith('fh.') and not re.search(bank2.FAMILY_WORD + r'|가족|집안', src):
                ok = None
            if ok and turn != 0:
                # 두 항목을 묶은 질문에 환자가 다른 항목만 답했으면(예: 지병·수술 → '고혈압 말곤 없어요') 이 키는 미확인
                q_txt, a_txt = next(((r['q'], r['a']) for r in rows if r['turn'] == turn), ('', ''))
                paired = re.search(r'(이나|거나|나\s)', q_txt)
                bare_neg = re.fullmatch(r'\s*(아니(요|오)?|아뇨|없어요|없습니다|둘\s*다\s*없어요|전혀\s*없어요|네|예)[.,!\s]*'
                                        r'(둘\s*다\s*)?(없어요|있어요)?[.!]?\s*', a_txt or '')
                if paired and not re.search(bank2.FIXED_KEYS[key], a_txt) and not bare_neg and \
                        not re.search(r'둘\s*다|모두|전부', a_txt):
                    ok = None
            if not ok:
                log(f'fact key demoted: {key} turn {turn}')
                key = 'other'
        elif key != 'other':
            key = 'other'
        # 흡연·음주 서술형 답(예: '월 1~2회 가볍게')은 (+)로: 빈칸으로 두면 '확인했는데 미기록' 오류
        if key in ('sh.alcohol', 'sh.smoking') and pol == '?':
            ans0 = _answer(enc, rows, turn)
            if not re.search(r'(안\s*(마|피)|없|끊|안\s*해|전혀|평생)', ans0):
                pol = '+'
                detail = detail or _short(ans0)
        # Anorexia 극성: 입맛 좋다·많이 먹는다 → '-'
        ans = _answer(enc, rows, turn)
        if key == 'ros.Anorexia' and re.search(r'(좋|늘|많이\s*먹|더\s*먹)', ans):
            if pol == '+':
                pol = '-'
                out.append({'turn': turn, 'sec': 'ros', 'key': 'other', 'label': '식욕 증가', 'pol': '+',
                            'detail': _short(ans)})
        # 숫자 검증
        allowed = extract_numbers(src) | extract_numbers(enc.vitals) if turn == 0 else extract_numbers(src)
        nums = re.findall(r'\d+(?:\.\d+)?', detail)
        if any(_norm(x) not in allowed for x in nums):
            detail = '' if turn == 0 else _short(ans)
        if not label:
            row_label = next((r['label'] for r in rows if r['turn'] == turn and r['label'] not in ('', '적응형')), '')
            label = (bank2.FIXED_LABEL.get(key) or row_label or '기타')[:16]
        out.append({'turn': turn, 'sec': sec, 'key': key, 'label': label, 'pol': pol, 'detail': detail})
    for f in out:
        n += 1
        f['id'] = f'F{n}'
    return out


def _norm(s):
    try:
        v = float(s)
        return str(int(v)) if v == int(v) else str(v)
    except ValueError:
        return s


def is_negative(answer: str) -> bool:
    a = nfc(answer).strip()
    if re.match(r'^(아니|아뇨|없|전혀|안\s|별로\s*없)', a):
        return True
    return bool(re.search(r'(없어요|없습니다|없었어요|안 피워요|안 마셔요|안 해요|않아요)[.!]?$', a))


def fallback(enc, rows) -> list[dict]:
    out = []
    for r in rows:
        slot = r['slot']
        neg = is_negative(r['a'])
        pol = '-' if neg else ('+' if re.match(r'^(네|예|있)', r['a'].strip()) else '?')
        keys = bank2.SLOT_KEYS.get(slot) or []
        label = r['label'] or slot
        if keys and pol in '+-':
            for k in keys:
                out.append({'turn': r['turn'], 'sec': k.split('.')[0], 'key': k, 'label': bank2.FIXED_LABEL.get(k, label),
                            'pol': pol, 'detail': '' if neg else _short(r['a'])})
        else:
            sec = 'ice' if slot.startswith('ice') else ('fh' if slot.startswith('fh') else
                                                        ('sh' if slot.startswith('sh') else 'hpi'))
            out.append({'turn': r['turn'], 'sec': sec, 'key': 'other', 'label': label[:16], 'pol': pol,
                        'detail': _short(r['a'])})
    return validate(enc, rows, out)


def extract(enc) -> list[dict]:
    rows = qa_rows(enc)
    if not rows:
        return []
    listing = '\n'.join(f"{r['turn']} | {r['q']} | {r['a']} | {r['slot'] or '-'}" for r in rows)
    keys = ', '.join(bank2.FIXED_KEYS)
    user = (f'시작 정보(턴 0): {enc.opening}\n'
            f'문답(턴 | 의사 | 환자 | 질문 slot):\n{listing}\n'
            f'고정 키(정확히 해당할 때만 사용): {keys}\n'
            '규칙:\n'
            '- 환자(또는 보호자)가 실제로 말한 것만. 한 턴에 여러 사실이면 여러 개. 묻지 않았는데 말한 것도 포함. 시작 정보의 사실은 턴 0.\n'
            '- pol: "+"(있다), "-"(없다/아니다), "?"(서술형·수치·불분명).\n'
            '- key: 고정 키에 정확히 해당하면 그 키(예: "고혈압이나 당뇨 있으세요?"→"아니요" 이면 pmh.HTN "-", pmh.DM "-" 두 개), '
            '아니면 "other".\n'
            '- ros.Anorexia는 입맛·식욕이 줄었을 때만 "+". 입맛이 좋거나 많이 먹으면 ros.Anorexia "-"와 별도 사실 "식욕 증가"(+).\n'
            '- label: 한국어 짧은 항목명(12자 이내, 예: 손떨림, 월경량 감소, 약국 수면유도제).\n'
            '- detail: 20자 이내 임상 약어체(숫자·약 이름·기간은 환자 말 그대로, 예: "하루 5~6알, 새벽 추가").\n'
            '- sec: hpi|pmh|meds|fh|sh|ros|women|peds|psych|ice. 가족 질환은 fh, 복용약·영양제는 meds.\n'
            '- 진단·해석 금지. 환자 표현을 넓히지 말 것(묽은 변≠설사, "고교 때 갑자기 컸다"≠사춘기 지연). '
            '두 항목을 묶은 질문에 한 항목만 답했으면 답한 항목만 사실로.\n'
            '출력: {"facts": [{"turn": 정수, "sec": "...", "key": "...", "label": "...", "pol": "+|-|?", "detail": "..."}]}')
    res = ask_json(enc.client, enc.budget, ROLE, user, effort=enc.cfg['EFFORT_FACTS'], max_tokens=8000, tag='facts',
                   want=dict, tries=2, reserve=3, max_wait=300,
                   validate=lambda v: isinstance(v.get('facts'), list) and len(v['facts']) > 0)
    if not res:
        log('facts: fallback')
        return fallback(enc, rows)
    facts = validate(enc, rows, res.get('facts'))
    # LLM이 놓친 slot 문항(고정 키 대응)은 규칙으로 보충
    have = {(f['turn'], f['key']) for f in facts}
    extra = [f for f in fallback(enc, rows) if f['key'] != 'other' and (f['turn'], f['key']) not in have]
    if extra:
        facts += extra
        for i, f in enumerate(facts, 1):
            f['id'] = f'F{i}'
    log(f'facts: {len(facts)}')
    return facts


def table(facts) -> str:
    return '\n'.join(f"{f['id']} | {f['turn']} | {f['sec']} | {f['label']} | {f['pol']} | {f['detail']}" for f in facts)

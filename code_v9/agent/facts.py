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


PATIENT_Q_RE = re.compile(r'(\?|까요|나요|건가요|어떻게|언제|얼마나|되나요|있나요)')
GENERIC_NEG_RE = re.compile(r'((둘|셋)\s*다\s*(\S+\s*)?(없|안\s|않|아니)|(모두|전부|아무것도|아무\s*(병|문제|증상)도)\s*(\S+\s*)?(없|안\s|않)|'
                            r'그런\s*(병|증상|질환|적|건|거|것|변화|문제|얘기|말|일)\S*\s*(은|는|도)?\s*'
                            r'(들은\s*적\s*|진단받은\s*적\s*|앓은\s*적\s*|받은\s*적\s*|있었던\s*적\s*)?없)')
EXPLAIN_PHASES = ('explain', 'explain-answer', 'explain-extra')
# 고정 키가 없는 항목 id → S 영역(입원력·천식 등은 S pmh Others로)
ITEM_SEC_PREFIX = (('pmh_', 'pmh'), ('fh_', 'fh'), ('sh_', 'sh'), ('ros_', 'ros'), ('ice', 'ice'), ('p_', 'peds'),
                   ('w_', 'women'))


def item_sec(iid: str, default: str = 'hpi') -> str:
    for pre, sec in ITEM_SEC_PREFIX:
        if str(iid or '').startswith(pre):
            return sec
    return default


def effective_items(row) -> list[dict]:
    """v8c: 판정 항목에 포괄 음성('그런 병은 없어요'·'둘 다 없어요')을 반영한다. 어떤 항목도 (+)로 답하지 않았고 답이 포괄 음성이면
    묶음의 모든 항목을 답함·(-)로 본다. 그 외에는 cpx.judge 판정 그대로(미응답 항목은 미응답)."""
    items = [dict(j) for j in (row.get('items') or [])]
    if len(items) > 1 and GENERIC_NEG_RE.search(nfc(row.get('a') or '')) and \
            not any(j.get('answered') and j.get('pol') == '+' for j in items):
        for j in items:
            j['answered'], j['pol'] = True, '-'
    return items


def items_note(items) -> str:
    """v8 항목별 판정 표기: '갈증(-), 소변량(미응답)'."""
    out = []
    for j in items or []:
        if j.get('answered'):
            out.append(f"{j['label']}({j['pol']})")
        else:
            out.append(f"{j['label']}(미응답)")
    return ', '.join(out)


def qa_rows(enc) -> list[dict]:
    rows = []
    for e in enc.ledger:
        if e['kind'] != 'SAY' or e.get('refused'):
            continue
        if e.get('phase') in EXPLAIN_PHASES and (getattr(enc, 'cfg', None) or {}).get('EXPLAIN_Q_TO_S', 1):
            # v8: 설명 중 환자가 한 '질문'만 걱정·궁금증(ICE)으로 S에 반영(수긍·되말하기 답은 제외)
            a = e.get('reply') or ''
            if PATIENT_Q_RE.search(a) and not re.match(r'\s*(네|예)[,.]?\s*(알겠|감사|그럴게)', a):
                rows.append({'turn': e['turn'], 'q': e['text'], 'a': a, 'slot': 'ice_q', 'label': '설명 중 환자 질문',
                             'items': None})
            continue
        if e.get('phase') in ('empathy', 'explain-teachback'):
            continue
        row = {'turn': e['turn'], 'q': e['text'], 'a': e.get('reply') or '', 'slot': e.get('qid') or '',
               'label': e.get('label') or '', 'items': e.get('items')}
        if row['items']:
            row['items'] = effective_items(row)
        rows.append(row)
    return rows


def _item_kw(enc) -> dict:
    st = getattr(enc, 'cpx', None)
    out = {}
    for u in (st.units if st else []):
        for iid, _lab, kw in u['items']:
            out.setdefault(iid, kw)
    return out


def item_filter(enc, rows, facts: list[dict]) -> list[dict]:
    """v8 I3: 묶음 질문에서 환자가 답하지 않은 항목의 음성 사실을 버리고, 답한 항목 중 사실표에 없는 고정 키는 보충한다."""
    from .cpx import ITEM_KEYS
    kws = _item_kw(enc)
    by_turn = {r['turn']: r for r in rows if r.get('items')}
    out = []
    for f in facts:
        r = by_turn.get(f['turn'])
        if r and len(r['items']) > 1:
            txt = f"{f['label']} {f.get('detail') or ''}"

            def score(j):
                kw = j.get('kw') or kws.get(j['id'])
                if ITEM_KEYS.get(j['id']) == f['key'] and f['key'] != 'other':
                    return 4
                if j['label'] and j['label'] in txt:
                    return 3
                if kw and kw != '.' and re.search(kw, f['label']):
                    return 2
                if kw and kw != '.' and re.search(kw, txt):
                    return 1.5
                return 1 if j['label'][:2] and j['label'][:2] in txt else 0
            sc = [(score(j), j) for j in r['items']]
            top = max((s for s, _ in sc), default=0)
            best = [j for s, j in sc if s == top and s > 0]
            if f['pol'] == '-' and best and all(not j.get('answered') for j in best):
                # 가장 잘 맞는 항목이 미응답이면 음성 사실을 버린다(미응답 ≠ 음성)
                log(f"fact dropped (unanswered bundle item): {f['label']} turn {f['turn']}")
                continue
            if f['key'] == 'other' and f['sec'] == 'hpi' and len(best) == 1:
                sec = item_sec(best[0]['id'], '')
                if sec in ('pmh', 'fh', 'sh'):   # 입원력·천식 등 병력 항목은 S pmh 칸으로
                    f = dict(f, sec=sec)
        out.append(f)
    have = {(f['turn'], f['key']) for f in out}
    for t, r in by_turn.items():
        for j in r['items']:
            key = ITEM_KEYS.get(j['id'])
            if not (j.get('answered') and j.get('pol') in ('+', '-')):
                continue
            if key and (t, key) not in have:
                sec = key.split('.')[0]
                out.append({'turn': t, 'sec': sec, 'key': key, 'label': j['label'][:16], 'pol': j['pol'], 'detail': ''})
                have.add((t, key))
            elif not key and item_sec(j['id'], '') == 'pmh' and not any(
                    f['turn'] == t and (j['label'][:2] in f['label'] or (j.get('kw') not in (None, '.') and
                                                                         re.search(j['kw'], f['label'])))
                    for f in out):
                # 고정 키 없는 병력 항목(입원력·천식 등)도 답했으면 S pmh Others에 남는다
                out.append({'turn': t, 'sec': 'pmh', 'key': 'other', 'label': j['label'][:16], 'pol': j['pol'],
                            'detail': '' if j['pol'] == '-' else _short(r['a'])})
    for i, f in enumerate(out, 1):
        f['id'] = f'F{i}'
    return out


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
                # v8 bare_neg 보강: "아니요, 그런 병은 없어요" 같은 포괄 음성은 묶음 질문 각 항목의 음성으로 인정
                generic_neg = bool(GENERIC_NEG_RE.search(a_txt or ''))
                row = next((r for r in rows if r['turn'] == turn), None)
                judged_ok = False
                if row and row.get('items'):
                    from .cpx import ITEM_KEYS
                    judged_ok = any(ITEM_KEYS.get(j['id']) == key and j.get('answered') for j in row['items'])
                if paired and not re.search(bank2.FIXED_KEYS[key], a_txt) and not bare_neg and not generic_neg and \
                        not judged_ok:
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
    from .cpx import ITEM_KEYS
    out = []
    for r in rows:
        slot = r['slot']
        if r.get('items'):  # v8: 항목별 판정을 그대로 사실로(미응답 항목은 만들지 않음)
            for j in r['items']:
                if not j.get('answered'):
                    continue
                key = ITEM_KEYS.get(j['id'], 'other')
                sec = key.split('.')[0] if key != 'other' else \
                    ('ice' if slot.startswith('ice') else item_sec(j['id'], 'hpi'))
                out.append({'turn': r['turn'], 'sec': sec, 'key': key, 'label': j['label'][:16], 'pol': j['pol'],
                            'detail': '' if j['pol'] == '-' else _short(r['a'])})
            continue
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
    return item_filter(enc, rows, validate(enc, rows, out))


def extract(enc) -> list[dict]:
    rows = qa_rows(enc)
    if not rows:
        return []
    listing = '\n'.join(f"{r['turn']} | {r['q']} | {r['a']} | {r['slot'] or '-'}"
                        + (f" | 항목 판정: {items_note(r['items'])}" if r.get('items') and len(r['items']) > 1 else '')
                        for r in rows)
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
            '- 묶음 질문(A나 B, 병력 이름 나열) 답은 항목별로 사실을 따로 만든다(라벨에 각 항목명). "항목 판정"에 (미응답)인 항목은 '
            '사실로 만들지 않는다(음성으로도 쓰지 말 것). "둘 다 없어요"·"그런 병은 없어요"면 각 항목 모두 "-".\n'
            '- slot이 ice_q인 행은 설명 중 환자가 한 질문: sec "ice", label "~ 궁금해함"(예: 치료 기간 궁금해함), pol "?".\n'
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
    facts = item_filter(enc, rows, facts)
    log(f'facts: {len(facts)}')
    return facts


def table(facts) -> str:
    return '\n'.join(f"{f['id']} | {f['turn']} | {f['sec']} | {f['label']} | {f['pol']} | {f['detail']}" for f in facts)

"""v12: 단일 항목 은행 질문을 같은 계통 짝 질문으로 합쳐 턴당 확인 항목을 늘린다(턴 0, Doctor 호출 1회).

배경: 은행 931단위 중 575개(62%)가 단일 항목. 34턴·문진 17단위 고정에서 정보수집은 '단위당 항목 수'로만 늘릴 수 있다.
규칙(사용자 피드백 고정): 묶음은 같은 계통 2항목까지, 3항목·교차 계통 금지. 중요한 항목을 앞에(부분 응답 27/29가 첫 항목).
LLM이 짝과 문구를 제안하고, 프로그램이 계통·길이·문법(cpx.check_question, util.validate_question)을 검증한다.
실패하면 원래 단위를 그대로 쓴다(v10b와 동일).
"""
from __future__ import annotations

import re

from . import cpx
from .llm import ask_json
from .util import log, nfc, validate_question

ROLE = '당신은 한국 외래 진료실의 숙련된 의사입니다.'
MERGE_STAGES = ('core', 'red', 'hx', 'sh', 'fh')
MAX_CANDS = 24
# '무슨 일 하시고 커피는 몇 잔 드세요?'처럼 술어 둘을 '~고'로 이은 문장: 환자는 첫 항목만 답한다(9건 중 1건만 둘 다)
TWO_PRED_RE = re.compile(r'(시고|하고|받고|먹고|마시고|드시고|피우고|있고|없고|되고|었고|았고)\s')
EXCLUDE_IDS = {'hpi_onset'}

# ICE 짝: 걱정(Concern) + 기대(Expectation). 걱정 단독 질문 1턴을 2항목으로.
I_EXPECT = ('ice_expect', '기대(ICE)', r'검사|치료|약|처방|원해|원하|싶|받고|해\s*주|알고')
ICE_PAIR_Q = {'adult': '걱정되는 점이나 바라는 점이 있으세요?', 'peds': '걱정되거나 바라시는 점이 있으세요?'}


def sys_group(u: dict) -> str:
    s = u.get('sys') or 'gen'
    for aff in cpx.AFFINITY:
        if s in aff:
            return '+'.join(sorted(aff))
    return s


def _key(u):
    return (u['prio'], 0 if u['safety'] else 1, cpx.STAGE_RANK.get(u['stage'], 9))


def candidates(units: list[dict], covered=()) -> list[dict]:
    covered = set(covered or ())
    out = []
    for u in units:
        if u.get('kind') != 'single' or u['stage'] not in MERGE_STAGES or u['id'] in EXCLUDE_IDS:
            continue
        if all(i[0] in covered for i in u['items']):
            continue
        out.append(u)
    out.sort(key=_key)
    out = out[:MAX_CANDS]
    groups: dict = {}
    for u in out:
        groups.setdefault(sys_group(u), []).append(u)
    return [u for u in out if len(groups[sys_group(u)]) >= 2]


def merged_unit(a: dict, b: dict, q: str) -> dict:
    stage = min(a['stage'], b['stage'], key=lambda s: cpx.STAGE_RANK.get(s, 9))
    u = cpx.U(f"{a['id']}+{b['id']}", stage, min(a['prio'], b['prio']), q, list(a['items']) + list(b['items']),
              a['sys'], safety=bool(a['safety'] or b['safety']), follow=a.get('follow') or b.get('follow'),
              isys=[a['sys'], b['sys']], must=bool(a.get('must') or b.get('must')))
    u['merged_from'] = [a['id'], b['id']]
    return u


def check_pair(a: dict, b: dict, q: str, asked=()) -> str:
    """'' = 통과."""
    t = nfc(q or '').strip()
    if sys_group(a) != sys_group(b):
        return 'cross_group'
    ok, why = cpx.check_question(t)
    if not ok:
        return why
    ok, why = validate_question(t, list(asked))
    if not ok:
        return why
    if cpx.count_items(t) > 2:
        return 'three_items'
    if TWO_PRED_RE.search(t):
        return 'two_predicates'
    u = merged_unit(a, b, t)
    v = cpx.bundle_violation(u)
    return v


def _prompt(cands: list[dict]) -> str:
    lines = [f"[{k}] ({sys_group(u)}) {u['q']}  — 항목: {u['items'][0][1]}" for k, u in enumerate(cands)]
    return ('아래는 외래 문진에서 물을 단일 질문 목록입니다(번호, 계통, 질문, 항목). 턴이 부족해 같은 계통 질문 둘을 한 문장으로 '
            '합치려 합니다.\n' + '\n'.join(lines) + '\n'
            '[규칙]\n- 괄호 안 계통이 같은 두 질문만 합친다. 한 번호는 한 번만.\n'
            '- 합친 질문: 공백 포함 28자 이내, 쉬운 존댓말 의문문 하나(물음표 1개), 공통 술어 하나'
            "(예: '머리가 아프거나 토하나요?', '열이나 오한이 있나요?', '어디가 어떻게 아프세요?').\n"
            "- '~거나 ~고' 처럼 술어가 둘인 문장, 쉼표로 이은 두 질문, 세 가지 이상 나열 금지.\n"
            '- 더 중요한 질문(번호가 작은 쪽)을 a로, 그 항목을 문장 앞에.\n'
            '- 두 질문이 자연스럽게 합쳐지지 않으면(예: 시간을 묻는 질문 + 증상 유무) 합치지 않는다.\n'
            '- 환자가 한 번에 짧게(20자 안팎) 두 가지 다 답할 수 있어야 한다.\n'
            '출력: {"pairs": [{"a": 번호, "b": 번호, "q": "합친 질문"}]}  (합칠 것이 없으면 빈 목록)')


def merge_singles(enc, units: list[dict], covered=()) -> list[dict]:
    """단일 단위 짝 합치기. 반환: 새 단위 목록(합쳐진 단위는 a 자리에, b는 제거)."""
    cands = candidates(units, covered)
    if len(cands) < 2:
        return units
    res = ask_json(enc.client, enc.budget, ROLE, _prompt(cands), effort=enc.cfg.get('EFFORT_PAIR', 'low'),
                   max_tokens=5000, tag='pair_merge', want=dict, tries=1,
                   reserve=enc.cfg.get('CALL_RESERVE', 15))
    pairs = (res or {}).get('pairs') if isinstance(res, dict) else None
    if not isinstance(pairs, list):
        log('pair_merge: no result')
        return units
    used, merged = set(), {}
    asked = list(getattr(enc, 'asked', None) or [])
    for p in pairs:
        if not isinstance(p, dict):
            continue
        try:
            ia, ib = int(p.get('a')), int(p.get('b'))
        except (TypeError, ValueError):
            continue
        if ia == ib or not (0 <= ia < len(cands) and 0 <= ib < len(cands)) or ia in used or ib in used:
            continue
        a, b = cands[ia], cands[ib]
        if _key(b) < _key(a):
            a, b = b, a
        q = nfc(str(p.get('q') or '')).strip()
        why = check_pair(a, b, q, asked)
        if why:
            log(f'pair_merge rejected ({why}): {a["q"]} + {b["q"]} -> {q}')
            continue
        used |= {ia, ib}
        merged[id(a)] = merged_unit(a, b, q)
        merged[id(b)] = None
        log(f'pair_merge: {a["id"]} + {b["id"]} -> {q}')
    if not merged:
        return units
    out = []
    for u in units:
        if id(u) in merged:
            if merged[id(u)] is not None:
                out.append(merged[id(u)])
        else:
            out.append(u)
    return out


def ice_pair(units: list[dict], peds: bool) -> list[dict]:
    """ICE 걱정 단독 → 걱정·기대 짝(같은 ice 단위 id 유지: 설명·기록이 qid 'ice'로 찾는다)."""
    out = []
    for u in units:
        if u['id'] == 'ice' and len(u['items']) == 1:
            q = ICE_PAIR_Q['peds' if peds else 'adult']
            nu = cpx._clone(u, q=q, items=list(u['items']) + [I_EXPECT])
            nu['kind'] = 'pair'
            out.append(nu if len(nfc(q)) <= cpx.MAX_Q else u)
        else:
            out.append(u)
    return out


EXPECT_RE = re.compile(I_EXPECT[2])

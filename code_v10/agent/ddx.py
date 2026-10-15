"""DDXPlus 기반 감별 질문 선택기(v9).

LLM이 낸 감별진단 이름(한/영 자유 텍스트)을 DDXPlus 질환 id에 매칭하고, 그 질환들 사이에서 감별력이 큰
증거(증상·병력)를 한국어 단일 항목 질문 단위(cpx.U)로 돌려준다.
데이터: agent/data/ddx_kb.json (tools/build_ddx_kb.py로 생성, DDXPlus CC BY 4.0 구조 + 자체 한국어 번역).
순수 stdlib, 공개 함수는 예외를 밖으로 내보내지 않는다(실패 시 빈 결과).
"""
from __future__ import annotations

import json
import os
import re
import unicodedata

KB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'ddx_kb.json')
_KB = None
_SYN = None   # [(cond_id, normalized synonym)]

_HANGUL = re.compile(r'[가-힣]')
_STRIP = re.compile(r'[\s()\[\]{}<>「」『』（）,.;:·/\\\-_\'"`~!?]+')
_MALE = {'m', 'male', 'man', '남', '남성', '남자'}
# DDXPlus 범주형 후속 증거 → 상위 증거(통증 E_53, 피부 병변 E_129, 부종 E_151)
_FOLLOWUP = {'E_54': 'E_53', 'E_55': 'E_53', 'E_56': 'E_53', 'E_57': 'E_53', 'E_59': 'E_53',
             'E_133': 'E_129', 'E_136': 'E_129', 'E_152': 'E_151'}


def _load_kb():
    with open(KB_PATH, encoding='utf-8') as f:
        return json.load(f)


def _kb() -> dict:
    global _KB
    if _KB is None:
        kb = _load_kb()
        if not isinstance(kb, dict) or 'conditions' not in kb or 'evidences' not in kb:
            raise ValueError('bad kb')
        _KB = kb
    return _KB


def _norm(s) -> str:
    t = unicodedata.normalize('NFKD', str(s or ''))
    t = ''.join(ch for ch in t if not unicodedata.combining(ch))
    t = unicodedata.normalize('NFC', t).lower()
    return _STRIP.sub('', t)


def _syn_ok(s: str) -> bool:
    if not s:
        return False
    if _HANGUL.search(s):
        return len(s) >= 2
    return len(s) >= 4


def _synonyms():
    global _SYN
    if _SYN is None:
        out = []
        for cid, c in _kb()['conditions'].items():
            seen = set()
            for raw in [cid, c.get('en'), c.get('ko')] + list(c.get('syn') or []):
                s = _norm(raw)
                if s and s not in seen:
                    seen.add(s)
                    # 짧은 토큰(예: 'sle', 'hiv')은 입력 전체와 정확히 같을 때만 매칭
                    out.append((cid, s, not _syn_ok(s)))
        _SYN = out
    return _SYN


def _match_one(name) -> list[str]:
    t = _norm(name)
    if not t:
        return []
    best = {}   # cid -> (syn, pos)
    for cid, s, exact_only in _synonyms():
        if t == s:
            pos = 0
        elif exact_only or len(s) < 2:
            continue
        else:
            pos = t.find(s)
            if pos < 0:
                continue
        cur = best.get(cid)
        if cur is None or len(s) > len(cur[0]):
            best[cid] = (s, pos)
    exact = [cid for cid, (s, _) in best.items() if s == t]
    if exact:
        return exact[:1]
    # 더 긴 다른 질환 동의어 안에 포함되는 짧은 매칭은 버린다(예: '안정협심증' ⊂ '불안정협심증', '부비동염' ⊂ '만성부비동염')
    keep = []
    for cid, (s, pos) in best.items():
        if any(o != cid and len(os_) > len(s) and s in os_ for o, (os_, _) in best.items()):
            continue
        keep.append((pos, -len(s), cid))
    return [cid for _, _, cid in sorted(keep)]


def match(names) -> list[str]:
    """자유 텍스트 감별진단 이름들 → DDXPlus condition id 목록(입력 순서 유지, 중복 없음)."""
    try:
        if isinstance(names, str):
            names = [names]
        out = []
        for n in names or []:
            for cid in _match_one(n):
                if cid not in out:
                    out.append(cid)
        return out
    except Exception:
        return []


def conditions_info(names) -> list[dict]:
    """로그용: 매칭된 질환의 id/영문/한글 이름."""
    try:
        conds = _kb()['conditions']
        return [{'id': cid, 'en': conds[cid].get('en', cid), 'ko': conds[cid].get('ko', '')} for cid in match(names)]
    except Exception:
        return []


def _is_male(sex) -> bool:
    return _norm(sex) in _MALE if sex else False


def units(names, have_items=None, n: int = 8, prio: int = 1, pediatric: bool = False, sex=None) -> list[dict]:
    """매칭된 상위 ≤4 질환 사이에서 감별력 있는 증거 질문 단위(최대 n개)를 고른다."""
    try:
        from . import cpx
        kb = _kb()
        conds, evs = kb['conditions'], kb['evidences']
        cids = match(names)[:4]
        if not cids or n <= 0:
            return []
        have = set(have_items or ())
        male = _is_male(sex)
        k = len(cids)
        weight = {}
        for r, cid in enumerate(cids):
            sev = int(conds[cid].get('severity') or 3)
            weight[cid] = (1.0 / (r + 1)) * (1.0 + 0.25 * max(0, 5 - sev))
        present, core_of = {}, {}
        for cid in cids:
            c = conds[cid]
            for code in c.get('symptoms') or []:
                present.setdefault(code, set()).add(cid)
                core_of.setdefault(code, set()).add(cid)
            for code in c.get('antecedents') or []:
                present.setdefault(code, set()).add(cid)
        top = cids[0]
        cand = []
        for code, ps in present.items():
            e = evs.get(code)
            if not e:
                continue
            if f'dx_{code}' in have:
                continue
            parent = _FOLLOWUP.get(code)
            if parent and f'dx_{parent}' not in have:
                continue   # 범주형 후속 질문(부위·양상 등)은 상위 질문이 이미 물어졌을 때만
            if male and e.get('sex') == 'F':
                continue
            if pediatric and e.get('adult'):
                continue
            red = bool(e.get('red'))
            w = sum(weight[c] for c in ps)
            disc = w if (k > 1 and len(ps) < k) else 0.0
            if code in core_of:
                disc *= 1.2
            top_core = 1 if top in core_of.get(code, ()) else 0
            is_core = 1 if e.get('stage') == 'core' else 0
            cand.append(((0 if red else 1, -disc, -top_core, -is_core, -w, int(code.split('_')[1])), code, e))
        cand.sort(key=lambda x: x[0])
        prio = max(1, min(3, int(prio)))
        p2 = min(prio + 1, 3)
        picked = []
        for _, code, e in cand:
            if len(picked) >= n:
                break
            q = unicodedata.normalize('NFC', e['q'])
            red = bool(e.get('red'))
            stage = 'red' if red else (e.get('stage') or 'core')
            if stage not in cpx.STAGES:
                stage = 'hx'
            uid = f'dx_{code}'
            u = cpx.U(uid, stage, prio, q, [(uid, e.get('label') or code, '.')], e.get('sys') or 'gen', safety=red)
            if cpx.bundle_violation(u) != '' or not cpx.check_question(q)[0]:
                continue
            picked.append(u)
        half = (len(picked) + 1) // 2
        for i, u in enumerate(picked):
            u['prio'] = prio if i < half else p2
        return picked
    except Exception:
        return []

"""v9 은행 밖·빈약 주호소 보강: 진료지침 문진 섹션 → Doctor LLM 체크리스트(1회) → 묶음 규칙·30자·관련성 필터 → 문진 단위.

폴백 순서: (1) 지침 발췌 + LLM 체크리스트 → (2) DDXPlus 판별 evidence(agent/ddx.py) → (3) 범용 ROS 은행(cpx 'general' 범주).
- 은행 강도: strong(v8 범주 또는 시작 정보 키워드로 잡힌 확장 범주) / medium(접수 LLM만 고른 확장 범주) / weak(범주 없음·'general').
- strong이면 LLM 호출 없음(DDXPlus는 prio 3 대기열 보충만), medium이면 지침 체크리스트 prio 2, weak이면 prio 1.
- 지침 본문은 ZIP에 없다: 실행 중 guidelines.INDEX(NOVA_GUIDELINES_DIR)에서 발췌만 읽는다.
- 어떤 실패도 예외를 밖으로 내지 않고 [] 를 돌려준다. 시간·호출 예산(WRAPUP_SECONDS, CALL_RESERVE)을 지킨다.
"""
from __future__ import annotations

import re

from . import cpx
from . import guidelines
from .llm import ask_json
from .util import log, log_error, nfc, validate_question

SYSTEMS = ['gen', 'cv', 'resp', 'gi', 'gu', 'neuro', 'eye', 'neck', 'psy', 'sleep', 'drug', 'wm', 'hx', 'meds', 'fh', 'sh',
           'endo', 'ent', 'msk', 'skin', 'peds', 'growth']
STAGES = ('core', 'red', 'hx')
GL_CHARS = 2600


def bank_strength(prof: dict, built: dict) -> str:
    main = built.get('main')
    if not main or main == 'general' or not built.get('bank') or prof.get('cat_source') == 'default':
        return 'weak'
    if main in cpx.V8_CATS:
        return 'strong'
    return 'strong' if main in (prof.get('cat_detected') or []) else 'medium'


def _cat_sys(enc, prof: dict, built: dict, diffs: list[str]) -> set:
    """관련성 필터용 계통: 주 범주 은행 계통 + 주호소·시작 정보·감별 후보 문구의 계통 + 전신."""
    text = ' '.join([str(prof.get('cc') or ''), str(getattr(enc, 'opening', '') or '')] + list(diffs or []))
    return set(cpx.category_systems(built, prof)) | set(cpx.systems_of(text)) | {'gen'}


def relevant(q: str, cat_sys, peds: bool) -> tuple[bool, str]:
    """cpx.relevant_question의 수치·소아 말투 검사 + 계통 검사(질문 계통 중 하나라도 범주 계통과 겹치면 통과).
    지침·DDXPlus 문항은 이미 주호소·감별 질환에서 나온 것이므로 '시력이 떨어졌나요?'(눈+떨림 오탐)처럼
    한 단어 오탐으로 버리지 않는다. 범주와 전혀 무관한 계통만 거른다."""
    ok, why = cpx.relevant_question(q, None, peds)
    if not ok:
        return ok, why
    qs = set(cpx.systems_of(q)) - {'hx', 'meds'}
    if cat_sys is not None and qs and not (qs & set(cat_sys)):
        return False, 'off_system:' + ','.join(sorted(qs))
    return True, 'ok'


def _label_kw(label: str) -> str:
    words = [w for w in re.findall(r'[가-힣]{2,}', label or '') if w not in ('여부', '양상', '유무', '증상', '세부', '정도')]
    return '|'.join(dict.fromkeys(w[:2] for w in words)) or '.'


def guideline_text(enc, prof: dict, diffs: list[str]) -> tuple[str, list[str]]:
    """주호소·감별 후보 지침의 병력·증상·감별 섹션 발췌(최대 2문서, GL_CHARS자)."""
    try:
        if not guidelines._on(enc):
            return '', []
        queries = [q for q in [prof.get('cc') or ''] + list(diffs or [])[:3] if q and q.strip()]
        parts, srcs, used = [], [], set()
        for q in queries:
            if len(parts) >= 2:
                break
            t, s = guidelines.gather(enc, [q], [('overview', ['hp', 'ddx', 'dx'], 1300)], 'glck', used)
            if t:
                parts.append(t)
                srcs += s
        text = '\n\n'.join(parts)
        return text[:GL_CHARS], srcs
    except Exception as exc:  # noqa: BLE001
        log_error(f'glcheck guideline_text failed: {type(exc).__name__}: {exc}')
        return '', []


def _prompt(prof: dict, opening: str, diffs: list[str], existing: list[str], text: str, n: int) -> tuple[str, str]:
    sys_prompt = ('당신은 한국 외래 진료실의 숙련된 의사입니다. 진료지침 발췌를 근거로 이 환자 주호소의 CPX형 문진 체크리스트를 '
                  '만듭니다. JSON 객체 하나만 출력하세요.')
    peds = bool(prof.get('pediatric'))
    who = '보호자에게 "아이가 ~했나요?" 말투로' if peds else '환자에게 쉬운 존댓말로'
    user = (f"환자: {prof.get('age')}세 {prof.get('sex') or ''}, 주호소: {prof.get('cc')}\n시작 정보: {opening}\n"
            f"감별 후보: {', '.join(diffs[:5]) or '(없음)'}\n"
            f"이미 물을 질문(중복 금지): {' / '.join(existing[:30])}\n\n{text}\n\n"
            f'[규칙] 지침의 병력·증상·위험 징후·감별 포인트 중 이 주호소 진단에 결정적인 문진 항목 {n}개를 중요한 순서로. '
            f'{who} 물을 질문 문장으로 쓸 것: 공백 포함 28자 이내, 물음표 1개, 한 가지만 묻기(두 항목이면 같은 계통·공통 술어 하나), '
            '영어·약어·수치 기준 질문 금지, 진단명 묻기 금지, 검사·진찰 요청 금지. 공통 병력(복용약·알레르기·가족력·술담배·임신·걱정)은 '
            '이미 물으니 빼고, 주호소 특성(시작·양상·부위·악화/완화), 판별용 동반 증상, 위험 징후(관련 음성), 주호소 특이 과거력 위주.\n'
            '출력: {"items": [{"q": "질문", "label": "항목명 10자 이내", "stage": "core|red|hx", '
            f'"system": "계통", "red": true|false}}]}}\n계통 값: {SYSTEMS}')
    return sys_prompt, user


def compile_items(raw, existing: list[str], cat_sys, peds: bool, prio: int, n: int, prefix: str = 'gl') -> list[dict]:
    """LLM 체크리스트 → 문진 단위. check_question·validate_question(중복)·relevant_question·bundle_violation을 모두 통과한 것만."""
    out = []
    if not isinstance(raw, list):
        return out
    for k, d in enumerate(raw):
        if len(out) >= n:
            break
        if not isinstance(d, dict):
            continue
        q = nfc(str(d.get('q') or '')).strip()
        label = nfc(str(d.get('label') or '')).strip()[:12] or q[:10]
        if not q:
            continue
        ok, why = cpx.check_question(q)
        ok2, why2 = validate_question(q, existing + [u['q'] for u in out])
        ok3, why3 = relevant(q, cat_sys, peds) if ok and ok2 else (False, '')
        if not (ok and ok2 and ok3):
            log(f'glcheck item rejected ({why}/{why2}/{why3}): {q}')
            continue
        stage = str(d.get('stage') or 'core').strip()
        stage = stage if stage in STAGES else 'core'
        sys_ = str(d.get('system') or 'gen').strip()
        sys_ = sys_ if sys_ in SYSTEMS else 'gen'
        red = bool(d.get('red')) or stage == 'red'
        p = prio if len(out) < max(1, (n + 1) // 2 + 1) else min(3, prio + 1)
        u = cpx.U(f'{prefix}{k}', 'red' if red and stage != 'hx' else stage, p, q,
                  [(f'{prefix}{k}', label, '.')], 'hx' if stage == 'hx' and sys_ not in ('hx', 'meds') else sys_,
                  safety=red and stage != 'hx')
        if cpx.bundle_violation(u):
            log(f'glcheck item bundle violation ({cpx.bundle_violation(u)}): {q}')
            continue
        out.append(u)
    return out


def guideline_units(enc, prof: dict, built: dict, diffs: list[str], existing: list[str], prio: int, n: int) -> list[dict]:
    cfg = getattr(enc, 'cfg', {}) or {}
    if not cfg.get('GLCHECK', 1):
        return []
    try:
        if enc.time_left() < float(cfg.get('WRAPUP_SECONDS', 420)) + 300:
            log('glcheck skipped: time')
            return []
    except Exception:  # noqa: BLE001
        pass
    text, srcs = guideline_text(enc, prof, diffs)
    if not text:
        log('glcheck: no guideline excerpt')
        return []
    sys_prompt, user = _prompt(prof, getattr(enc, 'opening', ''), diffs, existing, text, n + 2)
    try:
        res = ask_json(enc.client, enc.budget, sys_prompt, user, effort=cfg.get('EFFORT_GLCHECK', 'low'),
                       max_tokens=int(cfg.get('GLCHECK_MAX_TOKENS', 3000)), tag='glcheck', want=dict, tries=1,
                       reserve=cfg.get('CALL_RESERVE', 15))
    except Exception as exc:  # noqa: BLE001
        log_error(f'glcheck llm failed: {type(exc).__name__}: {exc}')
        return []
    raw = (res or {}).get('items') if isinstance(res, dict) else None
    cat_sys = _cat_sys(enc, prof, built, diffs)
    units = compile_items(raw, existing, cat_sys, bool(prof.get('pediatric')), prio, n)
    if units:
        enc.gl_check_sources = srcs
    log(f'glcheck: {len(units)} units from guideline ({"; ".join(srcs)[:160]})')
    return units


def ddx_units(enc, prof: dict, built: dict, diffs: list[str], units: list[dict], prio: int, n: int) -> list[dict]:
    try:
        from . import ddx
        have = {i[0] for u in units for i in u['items']}
        cand = ddx.units(diffs, have_items=have, n=n + 4, prio=prio, pediatric=bool(prof.get('pediatric')),
                         sex=prof.get('sex'))
        cat_sys = _cat_sys(enc, prof, built, diffs)
        existing = [u['q'] for u in units]
        labels = {re.sub(r'\s', '', i[1]) for v in units for i in v['items'] if len(re.sub(r'\s', '', i[1])) >= 2}
        out = []
        for u in cand or []:
            if len(out) >= n:
                break
            if re.sub(r'\s', '', u['items'][0][1]) in labels:   # 은행이 같은 항목을 이미 묻는다(예: '발열')
                continue
            ok, _ = cpx.check_question(u['q'])
            ok2, _ = validate_question(u['q'], existing + [v['q'] for v in out])
            ok3, _ = relevant(u['q'], cat_sys, bool(prof.get('pediatric')))
            if ok and ok2 and ok3 and not cpx.bundle_violation(u):
                out.append(u)
        # 필터 뒤 순서대로 다시 등급: 앞쪽 (n+1)//2 + 1개는 prio, 나머지는 prio+1 (최대 3)
        top = (n + 1) // 2 + 1
        for k, u in enumerate(out):
            u['prio'] = prio if k < top else min(3, prio + 1)
        if out:
            log(f'ddx units: {[u["q"] for u in out]}')
        return out
    except Exception as exc:  # noqa: BLE001
        log_error(f'glcheck ddx_units failed: {type(exc).__name__}: {exc}')
        return []


def general_units(units: list[dict], prio: int) -> list[dict]:
    spec = cpx.CPX.get('general')
    if not spec:
        return []
    have = {u['id'] for u in units}
    qs = [u['q'] for u in units]
    out = []
    for u in spec['units']:
        if u['id'] in have:
            continue
        ok, _ = validate_question(u['q'], qs + [v['q'] for v in out])
        if not ok:
            continue
        out.append(cpx._clone(u, prio=max(u['prio'], prio)))
    return out


def _demote_general(units: list[dict], keep: int = 3) -> None:
    k = 0
    gen_ids = {u['id'] for u in (cpx.CPX.get('general') or {}).get('units') or []}
    for u in units:
        if u['id'] in gen_ids and u['prio'] == 1 and not u.get('safety'):
            k += 1
            if k > keep:
                u['prio'] = 2


def supplement(enc, built: dict, units: list[dict]) -> list[dict]:
    """은행 강도에 따라 지침 체크리스트 → DDXPlus → 범용 ROS 순으로 보강 단위를 돌려준다. 실패 시 []."""
    try:
        prof = getattr(enc, 'profile', None) or {}
        cfg = getattr(enc, 'cfg', {}) or {}
        strength = bank_strength(prof, built)
        built['strength'] = strength
        diffs = [d for d in (getattr(enc, 'differentials', None) or []) if isinstance(d, str) and d.strip()]
        out: list[dict] = []
        info = {'strength': strength, 'gl': 0, 'ddx': 0, 'general': 0}
        if strength in ('weak', 'medium'):
            prio = 1 if strength == 'weak' else 2
            n = int(cfg.get('GLCHECK_N', 8)) if strength == 'weak' else int(cfg.get('GLCHECK_N_MEDIUM', 5))
            gl = guideline_units(enc, prof, built, diffs, [u['q'] for u in units], prio, n)
            info['gl'] = len(gl)
            out += gl
            if strength == 'weak' and built.get('main') == 'general' and len(gl) >= 4:
                _demote_general(units)   # 지침 체크리스트가 충분하면 범용 은행은 앞 3개(위치·양상·강도)만 핵심
        if strength == 'weak':
            dprio, dn = (1, 6) if not out else (2, 4)
        elif strength == 'medium':
            dprio, dn = 2, 4
        else:
            # strong(v8·키워드 은행): 은행·필수 단위가 예산을 다 채우면 DDXPlus를 붙이지 않는다(남는 슬롯에만)
            room = int(cfg.get('INTERVIEW_Q', 17)) - len(units) - len(out)
            dprio, dn = 3, max(0, min(4, room))
        dx = ddx_units(enc, prof, built, diffs, units + out, dprio, dn) if dn > 0 else []
        info['ddx'] = len(dx)
        out += dx
        if strength == 'weak' and built.get('main') == 'general' and info['gl'] < 4 and len(dx) >= 3:
            _demote_general(units)   # DDXPlus 판별 문항이 충분하면 범용 은행은 앞 3개만 핵심
        if strength == 'weak' and built.get('main') != 'general' and not prof.get('pediatric'):
            gen = general_units(units + out, 1 if not out else 2)
            info['general'] = len(gen)
            out += gen
        built['supp'] = info
        log(f'cpx supplement: {info}')
        return out
    except Exception as exc:  # noqa: BLE001
        log_error(f'glcheck supplement failed: {type(exc).__name__}: {exc}')
        return []

"""v4: 40턴 하드캡 · 범용 진찰(핵심 8 + 특이 ≤5 + flex) · 설명 11턴 재설계 · 지침 레버 결합 (docs/v4_spec.md).

턴 예산(v4_40) = 공감 1 + 문진 14 + 진찰 14 + 설명 11 = 40. Encounter가 min(서버 잔여, TURN_CAP − turn)만 쓰므로 41번째 행동은 없다.
- 문진: 공감(서술) → 주호소 주제 개방 → sweep ×2(+ 새 증상 즉시 주제 후속) → luna 계획 1회(문진 + 특이 진찰, 지침 발췌) →
  본문 우선순위 큐(안전 slot → luna 상위 2 → 과거력 → 복용약 → 가족력 → luna 나머지 → 사회력 → 기분) → ICE 기대.
  질문은 한 항목(say.pair_problem; PAIR_POLICY=negscreen이면 음성 선별 배경 짝 화이트리스트만 허용).
- 진찰: EXAM_POLICY c8flex(핵심 8 + 특이 ≤5 + flex[간·비장 → 복부 시진 → 흉곽 시진 → 갑상선]) | u12(범용 12 + 특이 상위 2),
  record.SECTION_ORDER(머리→발) 정렬, 간·비장 촉진은 복부 촉진 직전. 예산 = min(X_MAX, turns_remaining − EXPLAIN_N).
- 설명: queue(dx·options·link·concern·tests·caution·lifestyle) + tail(followup·must·warning·teach). 남은 턴 ≤ len(tail)이면 tail 강제,
  ≤ len(tail)+2이면 마지막 질문(final) + 답 1턴 예약. 환자 질문은 대기 문장 앞당김 → FAQ → luna 1회 → 템플릿.
"""
from __future__ import annotations

import json
import re

from . import bank2, banks, guidelines
from . import kb as kbmod
from . import say as saymod
from .interview import Checklist, match_slot
from .llm import ask, ask_json
from .record import SECTION_ORDER
from .util import is_similar, log, nfc
from .v3 import (EXAM_DUP_GROUPS, FINAL_Q, NEG_REPLY_RE, SWEEPS, TEACH_BACK, CAT_TOPIC, _key_terms, _kb_line,
                 _warn_from_plan, compress_warning, topic_q)

ROLE = '당신은 한국 외래 진료실의 숙련된 의사입니다.'

# ---------------------------------------------------------------- 진찰
CORE8 = ['vitals', 'general', 'mental', 'conj', 'lung', 'heart', 'abd_palp', 'periph']
FLEX = ['liver_spleen', 'abd_insp', 'chest_insp', 'thyroid']
U12 = list(banks.CORE12)
# 같은 섹션 안 순서(§4.1.3): 활력 → 외관·의식 / 흉곽 시진 → 폐 → 심음 / 복부 시진 → 장음 → 타진 → 간·비장 → 복부 촉진 → 특수 징후
WITHIN = ['vitals', 'orthostatic', 'spo2', 'general', 'mental', 'sedation', 'chest_insp', 'lung', 'heart', 'abd_insp',
          'bowel', 'abd_perc', 'liver_spleen', 'abd_palp']
GENERIC_WHY = re.compile(r'\s*(기본|전신|일반|확인|감별|상태|평가|선별)[\s가-힣]{0,6}')
THYROID_CATS = {'weight_loss', 'fatigue', 'palpitation', 'insomnia', 'mood', 'menstrual', 'growth', 'edema'}
THYROID_CC_RE = r'(체중|살이?\s*(빠|쪘|찌)|피로|피곤|두근|불면|불안|떨림|떨려|생리|월경|성장|키가|설사|변비|붓|부종|목\s*(이|에|앞)|갑상)'
COND_RULES = {  # 조건부 진찰: 주호소·시작 정보·양성 답·감별 텍스트에 맞을 때만
    'spo2': r'(숨이?\s*(차|가빠)|숨참|호흡\s*곤란|흉통|가슴\s*(통증|이?\s*아[프파]|답답)|심부전|폐렴|천식|COPD|dyspn|chest\s*pain|'
            r'heart\s*failure|pneumon|asthma|저산소)',
    'anthro': r'(성장|키가?\s*(작|안\s*자)|저신장|체중\s*증가|살이?\s*(쪘|찌)|비만|섭식|식이|거식|폭식|growth|obes)',
    'axillary_ln': r'(겨드랑|액와|유방)',
    'inguinal_ln': r'(사타구니|서혜|음낭|성기|생식기)',
    'genital': r'(음낭|고환|성기|생식기|배뇨\s*통|사춘기|2차\s*성징)',
    'testis': r'(음낭|고환|사춘기|2차\s*성징)',
    'dre': r'(혈변|항문|직장|전립선|흑변)',
    'breast': r'(유방|젖)',
}
EXAM_DUP_V4 = [g for g in EXAM_DUP_GROUPS if g != {'abd_palp', 'liver_spleen'}]  # v4는 간·비장을 복부 촉진 앞에 따로


def _sec_key(i: str, pos: int):
    sec = banks.EXAM_BY_ID[i][2]
    s = SECTION_ORDER.index(sec) if sec in SECTION_ORDER else len(SECTION_ORDER)
    w = WITHIN.index(i) if i in WITHIN else 100 + pos
    return (s, w)


def order_exams(ids: list) -> list:
    return [i for _, i in sorted(((_sec_key(i, p), i) for p, i in enumerate(ids)), key=lambda x: x[0])]


def _context_text(enc) -> str:
    prof = enc.profile or {}
    pos = ' '.join(e.get('reply') or '' for e in enc.ledger if e.get('kind') == 'SAY' and not e.get('refused')
                   and not NEG_REPLY_RE.search(e.get('reply') or ''))
    return ' '.join([prof.get('cc') or '', enc.opening or '', pos, ' '.join((enc.differentials or [])[:4])])


def _allowed(enc, i: str, ctx: str) -> bool:
    prof = enc.profile or {}
    if i not in banks.EXAM_BY_ID or i == 'vitals':
        return False
    if i == 'anthro' and prof.get('pediatric'):
        return True
    if i in COND_RULES and not re.search(COND_RULES[i], ctx, flags=re.I):
        return False
    if i == 'eye_signs' and not re.search(banks.THYROID_RE, ' '.join(enc.differentials or []), flags=re.I):
        return False
    if i in bank2.RISKY_EXAMS:
        cats = prof.get('categories') or []
        if not any(i in bank2.CATEGORY_EXAMS.get(c, []) for c in cats):
            return False
    return True


def thyroid_related(enc, plan: dict | None) -> bool:
    prof = enc.profile or {}
    if plan and (plan.get('thyroid_relevant') or 'thyroid' in [x[0] for x in plan.get('exams') or []]):
        return True
    cats = prof.get('categories') or []
    if cats and cats[0] in THYROID_CATS and not (prof.get('pediatric') and cats[0] != 'growth'):
        return True  # 관련 기본 범주는 주 카테고리만(intake 부 카테고리 잡음 방지: 소아 귀통증에 insomnia 등)
    if re.search(banks.THYROID_RE, ' '.join((enc.differentials or [])[:3]), flags=re.I):
        return True
    return bool(re.search(THYROID_CC_RE, (prof.get('cc') or '') + ' ' + (enc.opening or '')))


def _dedup_groups(ids: list) -> list:
    out = list(ids)
    for grp in EXAM_DUP_V4:
        hit = [i for i in out if i in grp]
        for i in hit[1:]:
            out.remove(i)
    return out


def exam_plan(enc, budget: int):
    """(실행 순서, 거절 시 대체 후보). §4.1.2·§4.1.3."""
    cfg = enc.cfg
    plan = getattr(enc, 'v4_plan', None) or {}
    ctx = _context_text(enc)
    core_set = set(CORE8) | set(FLEX) | {'vitals'}
    hi, mid = [], []
    for i, why, conf in plan.get('exams') or []:
        if i in core_set or not _allowed(enc, i, ctx):
            if i not in core_set:
                log(f'v4 exam dropped (rule): {i}')
            continue
        if GENERIC_WHY.fullmatch(why or '') or len((why or '').strip()) < 4:
            log(f'v4 exam dropped (generic why): {i} {why!r}')
            continue
        (hi if conf == 'high' else mid).append(i)
    hi, mid = _dedup_groups(hi), [i for i in _dedup_groups(mid) if i not in hi]
    cats = (enc.profile or {}).get('categories') or []
    if not plan.get('exams'):  # 폴백: 주 카테고리 진찰 앞 3개(core·flex·RISKY 제외) + 갑상선(감별에 있으면)
        main = cats[0] if cats else ''
        fb = [i for i in bank2.CATEGORY_EXAMS.get(main, []) if i not in core_set and i not in bank2.RISKY_EXAMS
              and _allowed(enc, i, ctx)]
        hi = fb[:3]
        mid = fb[3:]
    thy = thyroid_related(enc, plan)
    spec_max = int(cfg.get('EXAM_SPEC_MAX', 5))
    if cfg.get('EXAM_POLICY', 'c8flex') == 'u12':
        base = [i for i in U12]
        spec = (hi + mid)[:2]
        extra = [i for i in (hi + mid)[2:]]
    else:
        spec = hi[:spec_max]
        if len(spec) < 2:
            spec += [i for i in mid if i not in spec][:2 - len(spec)]
        if len(spec) < 3:  # luna 특이가 너무 적으면 주 카테고리 진찰로 3개까지(폴백 규칙 확장, OOD 대비)
            main = cats[0] if cats else ''
            for i in bank2.CATEGORY_EXAMS.get(main, []):
                if len(spec) >= 3:
                    break
                if i not in core_set and i not in spec and i not in bank2.RISKY_EXAMS and _allowed(enc, i, ctx):
                    spec.append(i)
            spec = _dedup_groups(spec)
        if thy:
            spec = (['thyroid'] + spec)[:spec_max]
        base = list(CORE8)
        extra = [i for i in FLEX if i not in spec] + [i for i in hi[spec_max:] + mid if i not in spec]
    cat_extra = []
    for c in cats:
        cat_extra += [i for i in bank2.CATEGORY_EXAMS.get(c, []) if i not in bank2.RISKY_EXAMS and _allowed(enc, i, ctx)]
    pool = []
    for i in base + spec + extra + cat_extra:
        if i not in pool and i in banks.EXAM_BY_ID:
            pool.append(i)
    pool = _dedup_groups(pool)
    chosen = order_exams(pool[:max(0, budget)])
    backups = [i for i in pool[max(0, budget):]]
    enc.exam_plan = chosen
    enc.exam_spec = spec
    log(f'v4 exams plan ({cfg.get("EXAM_POLICY", "c8flex")}, budget {budget}): spec={spec} order={chosen} backups={backups[:6]}')
    return chosen, backups


def examine(enc):
    cfg = enc.cfg
    E = cfg['EXPLAIN_N']
    budget = min(int(cfg.get('X_MAX', 16)), enc.turns_remaining - E)
    if budget <= 0 or not enc.can_act():
        return
    order, backups = exam_plan(enc, budget)
    done = 0
    for i in order + backups:
        if done >= budget or not enc.can_act() or enc.turns_remaining <= E:
            break
        if i in enc.blacklist or i in enc.done_exams:
            continue
        if i == 'spo2':
            vs = next((x for x in enc.ledger if x.get('qid') == 'vitals' and not x.get('refused')), None)
            if vs and re.search(r'(SpO2|산소포화)', vs.get('reply') or '', flags=re.I):
                continue
        e = banks.EXAM_BY_ID.get(i)
        if not e:
            continue
        entry = enc.act('EXAM', e[1], phase='exam', qid=i)
        if entry is None:
            continue
        if entry.get('refused'):
            enc.blacklist.add(i)
            continue
        entry['system'] = e[2]
        enc.done_exams.append(i)
        done += 1
    log(f'v4 exams done: {enc.done_exams} refused={sorted(enc.blacklist)}')


# ---------------------------------------------------------------- 문진
ICE_EXPECT = '오늘 특히 궁금하신 게 있으세요?'
ICE_DISEASE = '특히 걱정되는 병이 있으세요?'
BG_ADULT = {  # slot: (문구, 체크리스트 slot, 덮임 slot)
    'pmh': ('평소 앓는 병이 있으세요?', 'pmh_other', {'pmh_other', 'pmh_htn_dm'}),
    'meds': ('드시는 약이 있으세요?', 'pmh_meds', {'pmh_meds'}),
    'fh': ('가족 중에 아픈 분이 있으세요?', 'fh_open', {'fh_open'}),
    'fh2': ('가족 중 또 아픈 분 있나요?', 'fh_open', set()),
    'social': ('하루 일과를 말씀해 주세요', 'sh_job', {'sh_job'}),
    'smoke': ('담배 피우세요?', 'sh_smoke', {'sh_smoke'}),
    'alcohol': ('술은 얼마나 드세요?', 'sh_alcohol', {'sh_alcohol'}),
    'mood': ('요즘 기분은 어떠세요?', 'ps_mood', {'ps_mood'}),
}
BG_PEDS = {
    'pmh': ('입원한 적 있나요?', 'p_illness', {'p_illness'}),
    'meds': ('먹는 약이 있나요?', 'p_meds', {'p_meds'}),
    'fh': ('가족 중에 아픈 분이 있나요?', 'p_fh', {'p_fh'}),
    'fh2': ('가족 중 또 아픈 분 있나요?', 'p_fh', set()),
    'social': ('어린이집 생활은 어떤가요?', 'p_daycare', {'p_daycare'}),
    'birth': ('출산 때 문제는 없었나요?', 'p_perinatal', {'p_perinatal'}),
    'develop': ('발달은 또래와 비슷했나요?', 'p_develop', {'p_develop'}),
}
SAFETY_PREG = '혹시 임신 가능성은 있으세요?'
SAFETY_SED = [('드시는 수면제 이름이 뭐예요?', 'sb_name', r'(졸피뎀|스틸녹스|트리아졸람|로라제팜|알프라졸람|디아제팜|클로나제팜|이름은)'),
              ('수면제는 마지막으로 언제 드셨어요?', 'sb_last', r'(어젯밤|어제\s*밤|오늘\s*아침|마지막으로)'),
              ('약을 끊었을 때 경련한 적 있나요?', 'sb_seizure', r'(경련|발작)')]
SAFETY_SED_EXTRA = ('약을 끊었을 때 헛것이 보인 적 있나요?', 'sb_delirium', r'(헛것|환각|환시)')
SAFETY_THY = [('천식 있으세요?', 'free', r'천식'), ('가만히 있어도 숨이 차세요?', 'free', r'숨이?\s*차')]
HYPERTHY_RE = r'(항진|그레이브스|graves|hyperthyro|thyrotox|갑상(?:선|샘)\s*중독)'
SED_RE = r'(substance|수면제|진정|졸피뎀|sedative|hypnotic|benzodiazepine|벤조)'
SOCIAL_SMOKE_CATS = {'chest_pain', 'dyspnea', 'cough_fever', 'palpitation', 'syncope', 'edema'}
MOOD_CATS = {'insomnia', 'substance', 'mood', 'memory', 'weight_loss', 'palpitation', 'fatigue'}


NEG_END_RE = re.compile(r'(없어요|없습니다|없었어요|없네요|없는\s*것\s*같아요|않아요|않았어요|않습니다|아니에요|아니요|'
                        r'안\s*\S{1,4}요|못\s*느꼈어요)[.!~]?\s*$')


def is_negative(reply: str) -> bool:
    """sweep 답이 음성인지: 앞이 '아니/없…'이거나 끝이 '~는 없어요/않아요'(예: '숨이 차거나 쌕쌕거리는 소리는 없어요.')."""
    r = nfc(reply or '').strip()
    return bool(NEG_REPLY_RE.search(r) or NEG_END_RE.search(r))


def _qleft(enc) -> int:
    """남은 문진 질문 수: INTERVIEW_Q와 '턴 > 진찰 X + 설명 E'(§3.3) 중 작은 것."""
    cfg = enc.cfg
    return min(cfg['INTERVIEW_Q'] - enc.counts['interview'], enc.turns_remaining - (cfg['EXAM_N'] + cfg['EXPLAIN_N']))


def _policy(enc) -> str:
    return str(enc.cfg.get('PAIR_POLICY', 'negscreen'))


def q_problem(enc, q: str) -> str:
    return saymod.question_problem(q) or saymod.pair_problem(q, _policy(enc))


def _covered_text(enc) -> str:
    return enc.opening + ' ' + ' '.join(e.get('reply') or '' for e in enc.ledger if e.get('kind') == 'SAY')


def ask_v4(enc, cl, slot: str, q: str, phase: str = 'interview', *, allow_repeat=False, followup=False, label=''):
    """질문 하나(검증 실패면 보내지 않음). 거절('하나씩'·길이)도 재시도하지 않는다(§3.3-2)."""
    q = nfc(q).strip()
    why = q_problem(enc, q)
    if why:
        log(f'v4 q rejected ({why}): {q}')
        return None
    if not allow_repeat:
        if is_similar(q, enc.asked, 0.75):
            log(f'v4 q rejected (dup): {q}')
            return None
        if not followup:
            terms = set(_key_terms(q))
            prev = set()
            for e in enc.ledger:
                if e['kind'] == 'SAY' and e.get('phase') in ('first', 'interview', 'ice', 'sweep') and not e.get('refused'):
                    prev |= set(_key_terms(e['text']))
            if terms and terms <= prev:
                log(f'v4 q rejected (dup terms {sorted(terms)}): {q}')
                return None
        tp = re.sub(r'\s*에\s*대해\s*자세히\s*말씀해\s*주세요\.?$', '', q)
        if tp != q:
            prevt = [re.sub(r'\s*에\s*대해\s*자세히\s*말씀해\s*주세요\.?$', '', a) for a in enc.asked if '자세히 말씀해' in a]
            if is_similar(tp, prevt, 0.5):
                log(f'v4 q rejected (dup topic): {q}')
                return None
    lab = label or (cl.items.get(slot, {}).get('label') if slot in cl.items else '') or '적응형'
    entry = enc.act('SAY', q, phase=phase, qid=slot, label=lab)
    if entry is None or entry.get('refused'):
        return entry
    if entry.get('one_at_a_time'):
        log(f'v4 one_at_a_time (no retry): {q}')
    enc.counts['interview'] += 1
    if slot in cl.items:
        cl.asked.add(slot)
    cl.covered |= {s for s in bank2.cover_hits(entry.get('reply') or '') if s in cl.items}
    return entry


def safety_slots(enc, cl) -> list:
    """본문 큐 맨 앞 안전 slot(§4.2.5) — 이미 덮였거나 물은 것은 제외."""
    prof = enc.profile or {}
    out = []
    covered = _covered_text(enc)
    age = prof.get('age')
    if not prof.get('pediatric') and prof.get('sex') == 'F' and (age is None or 12 <= age <= 55):
        if 'wm_preg' not in cl.covered and not re.search(r'임신|피임', covered) and '임신' not in ' '.join(enc.asked):
            out.append(('wm_preg' if 'wm_preg' in cl.items else 'free', SAFETY_PREG))
    ctx = ' '.join((enc.differentials or [])[:3]) + ' ' + ' '.join(prof.get('categories') or []) + ' ' + (prof.get('cc') or '')
    if re.search(SED_RE, ctx, flags=re.I):
        for q, slot, cov in SAFETY_SED:
            if not re.search(cov, covered):
                out.append((slot if slot in cl.items else 'free', q))
    if re.search(HYPERTHY_RE, ' '.join((enc.differentials or [])[:3]), flags=re.I):  # 베타차단제 금기: 항진증일 때만
        for q, slot, cov in SAFETY_THY:
            if not re.search(cov, covered):
                out.append((slot, q))
    return out


def _bg(enc, key):
    peds = (enc.profile or {}).get('pediatric')
    table = BG_PEDS if peds else BG_ADULT
    if key not in table:
        return None
    q, slot, cov = table[key]
    if peds and key == 'social' and ((enc.profile or {}).get('age') or 0) >= 7:
        q = '학교 생활은 어떤가요?'
    return q, slot, cov


# ---------------------------------------------------------------- luna 계획 1회(부록 D1)
D1_SYS = (
    '당신은 한국 외래 진료실의 숙련된 의사입니다. 가상 환자 문진의 남은 질문과 신체진찰을 계획합니다. JSON 하나만 출력하세요.\n'
    '[질문 형식 — 서버는 질문 한 단위만 환자에게 넘기고, 환자 답은 20자 안팎(사실 1~2개)]\n'
    '- 한 질문 = 한 문장·한 항목. "A나 B", "A와 B", "A·B", "~거나"처럼 두 항목을 묻지 말 것(환자는 첫 항목만 답함).\n'
    '- 공감·인사말 접두 금지, "-고"로 두 동작 연결 금지, 물음표 1개. "다/전부/모두/~부터 지금까지/나열" 금지.\n'
    '- type "topic": "○○에 대해 자세히 말씀해 주세요"(이미 나온 양성 증상의 시점·빈도·양상·악화 요인).\n'
    '- type "closed": 감별을 가르는 핵심 음성·위험 신호·치료 안전(임신 가능성, 금기 병력) 예/아니요 한 항목.\n'
    '- 30자 이내, 쉬운 존댓말, 진단명·검사 요청 금지. 이미 묻거나 환자가 말한 것(시작 정보 포함)은 다시 묻지 말 것.\n'
    '- [진료지침 발췌]가 있으면 그 질환의 전형 증상·위험 인자·감별 포인트 중 아직 확인 안 된 것을 우선(출처가 감별과 다르면 무시).\n'
    '[진찰] 아래 목록 id만. 기본 진찰(활력·외관·의식·결막·폐·심음·복부 촉진·하지)은 이미 하므로 고르지 말 것.\n'
    "- 각 진찰의 why에는 그 진찰이 확인·배제하는 구체적 감별이나 소견을 쓸 것('기본·전신·일반 확인'이면 넣지 말 것).\n"
    '- 해당 부위 증상·감별이 없는 진찰(산소포화도, 신체 계측, 액와·서혜부 림프절, 생식기)은 넣지 말 것. 같은 목적 중복 금지.')


def _bg_status(enc, cl) -> str:
    def st(slots):
        return '확인' if any(s in cl.covered or s in cl.asked for s in slots) else '미확인'
    if (enc.profile or {}).get('pediatric'):
        return (f"입원·큰 병 {st({'p_illness'})} / 약 {st({'p_meds'})} / 가족력 {st({'p_fh'})} / 출생·발달 "
                f"{st({'p_perinatal', 'p_develop'})}")
    return (f"과거력 {st({'pmh_other', 'pmh_htn_dm'})} / 약 {st({'pmh_meds'})} / 가족력 {st({'fh_open'})} / "
            f"사회력 {st({'sh_smoke', 'sh_alcohol', 'sh_job'})}")


def plan(enc, cl, n: int, safety_qs: list):
    prof = enc.profile or {}
    sex = {'F': '여', 'M': '남'}.get(prof.get('sex'), '?')
    rows = [f"{e['turn']} | {e['text']} | {e['reply']}" for e in enc.ledger
            if e['kind'] == 'SAY' and not e.get('refused') and e.get('phase') in ('first', 'interview', 'ice', 'sweep',
                                                                                     'empathy')]
    core_set = set(CORE8) | set(FLEX) | {'vitals'}
    menu = '\n'.join(f"{e[0]} | {e[1].replace('하겠습니다', '').strip()} | {e[2]}" for e in banks.EXAM_BANK
                     if e[0] not in core_set)
    gl = guidelines.hint_interview(enc, clean=True)
    user = (f"환자: {prof.get('age')}세 {sex}, 정보 제공자 {prof.get('informant')}, 주호소 {prof.get('cc')}\n"
            f"시작 정보: {enc.opening} / 활력징후: {enc.vitals.replace(chr(10), ', ')}\n"
            f"지금까지 문답(턴 | 의사 | 환자):\n{chr(10).join(rows) or '(없음)'}\n"
            f"현재 감별진단: {enc.differentials}\n"
            f"이미 확인한 배경: {_bg_status(enc, cl)} / 반드시 넣을 안전 항목(코드가 이 문구로 따로 물으니 같은 내용은 내지 말 것): "
            f"{[q for _, q in safety_qs] or '없음'}\n"
            f"{gl}"
            f"진찰 목록(id | 진찰 | 계통):\n{menu}\n"
            '출력: {"differential": ["한국어명 (English)" 3~5개],\n'
            ' "questions": [{"type": "topic|closed", "why": "짧게", "q": "질문"}],   ← 최대 ' + str(n + 3) + '개, 중요한 순\n'
            ' "exams": [{"id": "...", "why": "...", "conf": "high|mid"}],          ← 2~6개, 중요한 순\n'
            ' "thyroid_relevant": true|false}')
    res = ask_json(enc.client, enc.budget, D1_SYS, user, effort=enc.cfg['EFFORT_PLAN_Q'], max_tokens=8000, tag='plan_v4',
                   want=dict, tries=2, reserve=enc.cfg['CALL_RESERVE'],
                   validate=lambda v: isinstance(v.get('questions'), list) or isinstance(v.get('exams'), list))
    if not isinstance(res, dict):
        return None
    diffs = [nfc(d).strip() for d in (res.get('differential') or []) if isinstance(d, str) and d.strip()]
    if diffs:
        enc.differentials = diffs[:5]
    qs = []
    for x in res.get('questions') or []:
        if isinstance(x, dict):
            q = nfc(str(x.get('q') or '')).strip()
        elif isinstance(x, str):
            q = nfc(x).strip()
        else:
            continue
        if not q:
            continue
        why = q_problem(enc, q)
        if why:
            log(f'v4 plan q bad ({why}): {q}')
            continue
        qs.append((match_slot(cl, q), q))
    exams = []
    for x in res.get('exams') or []:
        if not isinstance(x, dict):
            continue
        i = str(x.get('id') or '').strip()
        if i not in banks.EXAM_BY_ID or any(i == e[0] for e in exams):
            continue
        conf = 'high' if str(x.get('conf') or 'high').strip().lower().startswith('h') else 'mid'
        exams.append((i, nfc(str(x.get('why') or '')).strip(), conf))
    out = {'questions': qs, 'exams': exams, 'thyroid_relevant': bool(res.get('thyroid_relevant'))}
    log(f'v4 plan: diffs={enc.differentials} qs={qs} exams={exams} thyroid={out["thyroid_relevant"]}')
    return out


def interview(enc):
    cfg = enc.cfg
    prof = enc.profile
    cl = Checklist(prof, enc.opening)
    enc.checklist = cl
    peds = prof.get('pediatric')

    # T1 공감(서술, 질문 없음): 답에서 걱정을 얻는다
    emp = nfc(prof.get('empathy') or '').strip() or '많이 걱정되셨겠어요.'
    if '?' in emp or saymod.say_problem(emp):
        emp = '많이 걱정되셨겠어요.'
    emp_e = None
    if enc.can_act() and cfg.get('EMPATHY', 1):
        emp_e = enc.act('SAY', emp, phase='empathy')

    # T2 주호소 주제 개방(시작 정보도 질문으로 확인돼야 인정)
    cats = prof.get('categories') or []
    topic = CAT_TOPIC.get(cats[0] if cats else '', '지금 불편한 증상')
    cc = re.sub(r'\(.*?\)', '', nfc(prof.get('cc') or '')).strip()
    if cc and len(cc) <= 12 and not q_problem(enc, topic_q(cc)):
        topic = cc
    if enc.can_act() and _qleft(enc) > 0:
        e = ask_v4(enc, cl, 'hpi_onset' if 'hpi_onset' in cl.items else 'free', topic_q(topic), phase='first')
        if e and not e.get('refused') and 'hpi_onset' in cl.items:
            cl.asked.discard('hpi_onset')

    # 공감 답의 걱정 → ICE. 막연하면('큰 병') 다음 턴에 특히 걱정되는 병
    emp_r = (emp_e or {}).get('reply') or '' if isinstance(emp_e, dict) and not emp_e.get('refused') else ''
    if emp_r and re.search(r'(걱정|무서|겁|불안|두려)', emp_r):
        emp_e['qid'] = 'ice_concern'
        emp_e['phase'] = 'ice'
        cl.asked.add('ice_concern')
        if re.search(r'(큰\s*병|나쁜\s*병|심각|이상\s*있|잘못)', emp_r) and \
                not re.search(r'(암|당뇨|갑상|치매|심장|뇌|간|콩팥|신장|결핵)', emp_r) and _qleft(enc) > 2:
            ask_v4(enc, cl, 'ice_disease', ICE_DISEASE, phase='ice')

    # sweep ×2 + 새 증상 즉시 주제 후속(명사화 표, 호출 없음)
    replies = []
    for i in range(min(2, cfg.get('SWEEP_MAX', 2))):
        if not enc.can_act() or _qleft(enc) <= 2 or not enc.phase_time_ok():
            break
        e = ask_v4(enc, cl, 'free', SWEEPS[min(i, len(SWEEPS) - 1)], phase='sweep', allow_repeat=True)
        if not e or e.get('refused'):
            break
        r = e.get('reply') or ''
        if is_negative(r) or is_similar(r, replies, 0.6):
            break
        replies.append(r)
        noun = saymod.symptom_topic(r, enc.asked)
        if noun and _qleft(enc) > 2:
            ask_v4(enc, cl, 'free', topic_q(noun), phase='interview', followup=True)

    # luna 계획 1회(문진 + 특이 진찰, 지침 발췌)
    safety = safety_slots(enc, cl)
    n = max(0, _qleft(enc) - 1)
    pl = plan(enc, cl, n, safety) if enc.budget.can_call(cfg['CALL_RESERVE']) else None
    enc.v4_plan = pl or {}
    luna = list((pl or {}).get('questions') or [])

    # 본문 우선순위 큐
    queue = []  # (slot, q, label, kind)
    for slot, q in safety:
        queue.append((slot, q, '안전', 'safety'))
    for slot, q in luna[:2]:
        queue.append((slot, q, '', 'luna'))
    for key in ('pmh', 'meds', 'fh'):
        b = _bg(enc, key)
        if b:
            if key == 'meds' and re.search(SED_RE, ' '.join(cats) + ' ' + ' '.join(enc.differentials[:2]), flags=re.I):
                continue  # 진정제 증례는 안전 slot의 수면제 이름 질문이 복용약을 대신
            queue.append((b[1], b[0], {'pmh': '과거력', 'meds': '복용약', 'fh': '가족력'}[key], key))
    for slot, q in luna[2:]:
        queue.append((slot, q, '', 'luna'))
    if peds:
        for key in ('social', 'birth', 'develop'):
            b = _bg(enc, key)
            queue.append((b[1], b[0], {'social': '사회력', 'birth': '출생력', 'develop': '발달'}[key], key))
    else:
        first = 'smoke' if set(cats) & SOCIAL_SMOKE_CATS else 'social'
        b = _bg(enc, first)
        queue.append((b[1], b[0], '사회력', first))
        if set(cats) & MOOD_CATS:
            b = _bg(enc, 'mood')
            queue.append((b[1], b[0], '기분', 'mood'))
    # 여분(우선 3): 가족력 꼬리 → 사회력2 → 음성 선별 짝(negscreen) → 섬망력(진정제)
    tail = []
    if not peds:
        tail.append(('fh2',) + _bg(enc, 'fh2')[:2])
        for key in ('alcohol', 'smoke', 'social'):
            b = _bg(enc, key)
            tail.append((key, b[0], b[1]))
    if _policy(enc) == 'negscreen' and not peds:
        tail.append(('neg', '고혈압이나 당뇨 있으세요?', 'pmh_htn_dm'))
        tail.append(('neg', '수술이나 입원 경험 있으세요?', 'pmh_op'))
    ctx = ' '.join((enc.differentials or [])[:3]) + ' ' + ' '.join(cats)
    if re.search(SED_RE, ctx, flags=re.I):
        tail.append(('sed', SAFETY_SED_EXTRA[0], SAFETY_SED_EXTRA[1]))
    for key, q, slot in tail:
        queue.append((slot, q, '', key))

    fh_pos = False
    for slot, q, label, kind in queue:
        if _qleft(enc) <= 1 or not enc.can_act() or not enc.phase_time_ok():
            break
        if kind == 'fh2' and not fh_pos:
            continue
        cov = None
        if kind in BG_ADULT or kind in BG_PEDS:
            b = _bg(enc, kind)
            cov = b[2] if b else None
        if cov and any(s in cl.covered for s in cov if s in cl.items):
            log(f'v4 skip covered {kind}: {q}')
            continue
        if kind == 'luna':
            topic_slots = [s for s in bank2.cover_hits(q) if s in cl.items]
            if slot in cl.items and (slot in cl.covered or slot in cl.asked):
                continue
            if any(s in cl.covered for s in topic_slots):
                continue
        e = ask_v4(enc, cl, slot if (slot in cl.items or slot == 'free') else 'free', q, phase='interview',
                   label=label, followup=(kind == 'fh2'), allow_repeat=(kind == 'fh2'))
        if kind == 'fh' and e and not e.get('refused') and not NEG_REPLY_RE.search(e.get('reply') or ''):
            fh_pos = True
    # 꼬리: ICE 기대(고정, 마지막 문진)
    if enc.can_act() and _qleft(enc) > 0:
        ask_v4(enc, cl, 'ice_expect', ICE_EXPECT, phase='ice', label='궁금증·기대')
    log(f'v4 interview done: q={enc.counts["interview"]} turn={enc.turn} left={enc.turns_remaining}')


# ---------------------------------------------------------------- 계획·설명 문장(부록 D2)
LINE_KEYS_V4 = ('dx', 'options', 'link', 'concern', 'tests', 'caution', 'followup', 'warning', 'lifestyle')
FAQ_KEYS_V4 = [  # 정규식 순서가 우선순위(§5.4)
    ('test_pain', r'검사.{0,8}(아프|아파|힘들|무섭)'),
    ('test_when', r'검사.{0,6}언제|언제.{0,6}검사'),
    ('results', r'결과.{0,6}(언제|며칠|나와)'),
    ('tests', r'무슨\s*검사|어떤\s*검사|검사.{0,6}(받아야|필요|확인|알\s*수)'),
    ('duration', r'얼마나\s*오래|기간|언제까지|몇\s*(달|년)'),
    ('side_effect', r'부작용'),
    ('alternative', r'다른\s*방법|말고|대신|약\s*없이'),
    ('need_treatment', r'치료.{0,4}(필요|해야)|약.{0,4}(먹어야|필요)'),
    ('prognosis', r'나을|낫|좋아질|괜찮아질|회복|더\s*클|자랄|다시\s*(찔|찌)|줄일\s*수|끊을\s*수|잘\s*수\s*있'),
    ('meaning', r'무슨\s*뜻|무슨\s*병|어떤\s*병'),
    ('cause', r'왜|원인|때문|생긴\s*거'),
    ('serious', r'큰\s*병|위험|심각|암|나쁜|괜찮을까'),
    ('treatment', r'치료|약|주사|수술|어떻게\s*해'),
    ('lifestyle', r'조심|주의|음식|운동|생활|해도\s*(돼|되)'),
    ('fear', r'두려|무서|걱정돼|불안해'),
    ('prescribe', r'처방|약\s*(주|받)'),
]
REORDER = {'results': 'followup', 'tests': 'tests', 'side_effect': 'caution', 'alternative': 'options',
           'need_treatment': 'options', 'prognosis': 'options', 'meaning': 'link', 'cause': 'link', 'serious': 'concern',
           'treatment': 'options', 'lifestyle': 'followup', 'fear': 'concern'}
FAQ_DEFAULT = {'test_pain': '피 뽑을 때 잠깐 따끔하고 금방 끝나요.', 'test_when': '오늘 피를 뽑고 1주 뒤 결과를 봐요.',
               'results': '결과는 1주 안에 나와 다시 설명할게요.', 'prescribe': '약은 검사 결과 보고 상의해 정해요.'}
FALLBACK = {  # 부록 C (모두 ≤30자, statement_ok 통과 — U7)
    'link': '말씀하신 증상들이 이 병과 잘 맞아요.',
    'tests': saymod.GENERIC_TEST,
    'options': '검사 결과를 보고 치료 방법을 같이 정해요.',
    'followup': saymod.GENERIC_FOLLOW,
    'warning': saymod.GENERIC_WARN,
    'dx_generic': '검사로 확인할 병으로 보여요.',
    'answer': '검사 결과를 보고 자세히 설명할게요.',
    'emergency_followup': '오늘 바로 응급실에서 진료를 받으세요.',
}
SED_MUSTS = [(r'(끊지\s*않|끊진\s*않|중단하지\s*않|갑자기\s*끊)', '갑자기 끊으면 위험해 오늘은 끊지 않아요.'),
             (r'(운전|약국)', '운전·술·약국 수면제는 피하세요.')]
SED_WARNING = '경련·환각·혼동이면 바로 오세요.'
ICE_DISEASE_RE = (r'(뇌수막염|수막염|폐렴|패혈증|뇌종양|종양|백혈병|간암|위암|대장암|폐암|암|치매|당뇨|심장병|심근경색|뇌졸중|중풍|'
                  r'갑상(?:선|샘)|결핵|맹장|충수염|큰\s*병|나쁜\s*병)')


def faq_key_v4(reply: str):
    for key, pat in FAQ_KEYS_V4:
        if re.search(pat, reply or ''):
            return key
    return None


def _ok(s: str) -> bool:
    return saymod.statement_ok(s)


def _safe(s: str) -> str:
    from .explain import safe_say
    return safe_say(nfc(s or '').strip())


def _cands(v) -> list:
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, list):
        return []
    return [nfc(str(x)).strip() for x in v if str(x or '').strip()]


def _ice_text(enc) -> str:
    return ' '.join(e.get('reply') or '' for e in enc.ledger if str(e.get('qid', '')).startswith('ice'))


def _title(enc) -> str:
    prof = enc.profile or {}
    name = re.search(r'(?:이름은|저는|나는)\s*([가-힣]{2,4}?)(?:이고|이며|입니다|이다|,|\s)', enc.opening)
    if prof.get('pediatric') and prof.get('informant') not in ('본인', '보호자'):
        return (prof.get('informant') or '') + '님'
    return (name.group(1) + ' 님') if name else ''


def _key_ok(enc, key: str, s: str, ice_word: str, emergency: bool) -> bool:
    if key == 'dx':
        return any(k in s for k in saymod.dx_keywords(enc.dx or ''))
    if key == 'warning':
        return bool(saymod.WARN_RE.search(s)) and saymod.warn_count([s]) >= 2
    if key == 'followup':
        if emergency:
            return bool(re.search(r'오늘\s*바로.{0,16}진료|응급실', s))
        return bool(saymod.FOLLOWUP_RE.search(s))
    if key == 'concern' and ice_word:
        return ice_word in s
    return True


def plan_say(enc) -> dict:
    """D2 프롬프트 1회: P(v3.render_plan 호환) + 키마다 후보 2개 + FAQ. 검증 실패 키는 템플릿."""
    prof = enc.profile or {}
    facts = getattr(enc, 'facts', None) or []
    a = getattr(enc, 'assess', None) or {}
    k = kbmod.match_kb(enc.dx or '')
    enc.kb = k
    pos = [f"{f['label']}{(' ' + f['detail']) if f['detail'] else ''}" for f in facts if f['pol'] == '+'][:25]
    neg = [f['label'] for f in facts if f['pol'] == '-'][:20]
    from .encounter import exam_name
    exams = [f"{exam_name(e['text'])}: {(e.get('reply') or '')[:60]}" for e in enc.ledger
             if e['kind'] == 'EXAM' and not e.get('refused')]
    ice = [f"{e['text']} → {e['reply']}" for e in enc.ledger if str(e.get('qid', '')).startswith('ice')]
    sex = {'F': '여', 'M': '남'}.get(prof.get('sex'), '?')
    ddx = [d['dx'] for d in a.get('differential') or []] or enc.differentials[1:4]
    gl = guidelines.hint_plan(enc, kinds_mgmt=['dx', 'fu'], kinds_ovw=['dx', 'fu', 'edu'], clean=True)
    user = (f"환자: {prof.get('age')}세 {sex}, 정보 제공자 {prof.get('informant')}, 호칭 {_title(enc) or '없음'}, "
            f"주진단 {enc.dx}, 감별 {ddx}\n"
            f"핵심 양성 사실: {pos} / 핵심 음성 사실: {neg}\n"
            f"시행한 진찰과 소견(이것만 근거로): {exams}\n"
            f"환자 걱정·궁금증(원문): {ice} / 요청: {prof.get('request') or '없음'}\n"
            f"참고 지식표: {json.dumps(kbmod.kb_hint(k), ensure_ascii=False) if k else '없음'}\n"
            + ('[진료지침 발췌 — 검사·추적·경고 증상·쉬운 설명의 근거로만. 치료 줄과 처방 결정에는 쓰지 말 것. 출처가 주진단과 다르면 무시]\n'
               f'{gl}' if gl else '')
            + '[P]\n'
            '- tests: 3~7개 {"name","reason"} (확진·감별 배제·치료 전 기준치·안전. 불필요·침습 검사 금지)\n'
            '- treatment: 지식표가 있으면 []. 없으면 2줄 이내, 약은 계열명만, "검사 결과 확인 후 ~ 고려" 꼴. 숫자 용량·상품명·성분명 금지.\n'
            '- disposition: [{"level": "응급|입원|외래", "reason": "시행한 진찰·활력징후·문진 사실만"}] — 하지 않은 진찰 소견을 \'없다\'고 쓰지 말 것.\n'
            '- follow_up: "재진 : 시점과 확인할 것", "모니터링 : 간격과 항목", "즉시 내원 : 구체적 경고 증상"\n'
            '- education: 질환·검사 이유·생활 수칙\n'
            '[설명 문장 lines — 키마다 후보 2개. 각 공백 포함 28자 이내, 쉬운 존댓말 평서문, 물음표 금지.\n'
            " 한 문장에 내용 두 가지까지 '-고'나 '·'로 묶어도 됨. 이 환자의 증상·걱정 단어를 넣어 구체적으로.\n"
            ' 금지: 숫자 용량·%·"○주분", 특정 약 이름(계열명만), "처방해 드려요/드릴게요/시작해요/복용하세요", "걱정 마세요/완치/확실히/문제없어요",\n'
            ' "진단합니다"(검사 전이므로 "~로 보여요").]\n'
            ' dx: 병명 + 쉬운 원리 한마디            link: 이 환자의 증상들이 왜 생겼는지\n'
            ' concern: 환자 걱정(예: 암)에 근거와 함께 직접 답(걱정이 있으면 반드시)\n'
            ' tests: 핵심 검사와 목적                options: 예후 한마디 + 치료 선택지(조건부, 공동 결정)\n'
            ' caution: 치료의 주요 부작용·안전 행동 하나(약·시술이 없으면 생활 안전 수칙)\n'
            ' followup: 재진 시점 + 생활 수칙 한 가지(응급·입원이면 "오늘 바로 ~ 진료를 받으세요")\n'
            " warning: 구체적 경고 증상 2~4개를 '·'로 이어 \"~면 바로 오세요.\"   lifestyle: 생활 수칙 한 가지\n"
            '[FAQ — 환자가 되물을 질문의 28자 이내 답, 같은 금지]: prognosis, meaning, cause, serious, tests, test_when, results, treatment,\n'
            ' duration, side_effect, alternative, need_treatment, lifestyle, test_pain, fear, prescribe(해당 시)\n'
            '출력: {"tests": [...], "treatment": [...], "disposition": [...], "follow_up": [...], "education": [...],\n'
            ' "lines": {"dx": ["c1","c2"], "link": [...], "concern": [...], "tests": [...], "options": [...], "caution": [...],\n'
            '           "followup": [...], "warning": [...], "lifestyle": [...]},\n'
            ' "faq": {"prognosis": "...", ...}}')
    res = ask_json(enc.client, enc.budget,
                   '당신은 한국 대학병원 외래의 숙련된 전문의입니다. 초진을 마무리하며 계획(P)과 환자에게 실제로 말할 설명 문장을 씁니다. '
                   'JSON 하나만 출력하세요.', user, effort=enc.cfg['EFFORT_PLAN_SAY'], max_tokens=8000, tag='plan_say4',
                   want=dict, tries=2, max_wait=300, validate=lambda v: isinstance(v.get('lines'), dict))
    res = res if isinstance(res, dict) else {}
    return build_ps(enc, res, k)


EXAM_RED = [(r'반발\s*\S{0,3}통\s*\(\s*\+', '반발통'), (r'근성\s*방어\S{0,4}\s*\(\s*\+', '근성방어'),
            (r'복막\s*자극\S{0,6}\s*\(\s*\+', '복막자극 징후'), (r'경부\s*강직\s*\(\s*\+', '경부강직'),
            (r'(케르니그|커니그|브루진스키)\S{0,4}\s*\(\s*\+', '수막자극 징후')]


def exam_red_flags(enc) -> list:
    """시행한 진찰 결과의 응급 소견(복막자극·수막자극) + 활력징후 불안정."""
    out = []
    for e in enc.ledger:
        if e.get('kind') != 'EXAM' or e.get('refused'):
            continue
        for pat, name in EXAM_RED:
            if re.search(pat, e.get('reply') or '') and name not in out:
                out.append(name)
    try:
        from .record import vitals_assessment
        if '불안정' in vitals_assessment(enc):
            out.append('활력징후 불안정')
    except Exception:  # noqa: BLE001
        pass
    return out


def build_ps(enc, res: dict, k) -> dict:
    from .explain import _list
    plan = {'tests': _list(res.get('tests')), 'treatment': [] if k else _list(res.get('treatment'))[:2],
            'follow_up': _list(res.get('follow_up')), 'education': _list(res.get('education'))}
    disp = []
    for d in res.get('disposition') or []:
        if isinstance(d, dict):
            lv, rs = nfc(str(d.get('level') or '')).strip(), nfc(str(d.get('reason') or '')).strip()
            if lv or rs:
                disp.append(f'{lv} : {rs}' if lv and rs else (lv or rs))
        elif str(d).strip():
            disp.append(nfc(str(d)).strip())
    plan['disposition_luna'] = disp
    if k and not plan['tests']:
        plan['tests'] = [f'{x} : {y}' for x, y in k['tests']]
    emergency = any(re.search(r'(응급|입원)', d.split(':')[0]) for d in disp)
    red = exam_red_flags(enc)
    if red and not emergency:  # 진찰상 위험 소견이 있는데 luna가 외래로 두면 응급 평가로 올림(안전)
        disp.insert(0, f"응급 : 진찰상 {'·'.join(red)} 확인되어 오늘 응급실에서 해당 전문과 평가 필요")
        plan['disposition_luna'] = disp
        emergency = True
        log(f'v4 disposition → 응급 (exam red flags {red})')
    ice_txt = _ice_text(enc)
    m = re.search(ICE_DISEASE_RE, ice_txt)
    ice_word = re.sub(r'\s+', ' ', m.group(1)) if m and not re.search(r'(큰|나쁜)', m.group(1)) else ''
    raw = res.get('lines') if isinstance(res.get('lines'), dict) else {}
    lines, checks = {}, []
    kid = (k or {}).get('id')
    for key in LINE_KEYS_V4:
        chosen = ''
        for c in _cands(raw.get(key)):
            t = c
            if key == 'warning' and saymod.say_problem(t) == 'too_long':
                t = compress_warning(t) or t
            if _ok(t) and _key_ok(enc, key, t, ice_word, emergency):
                chosen = _safe(t)
                break
            checks.append({'drop': c, 'key': key, 'why': saymod.say_problem(t) or saymod.safety_problem(t) or 'key'})
        lines[key] = chosen
    # 폴백(부록 C)
    dx_short = re.sub(r'\(.*?\)', '', enc.dx or '').strip()
    if not lines['dx']:
        cand = f'{dx_short} 가능성이 높아 보여요.'
        if len(dx_short) <= 17 and _ok(cand):
            lines['dx'] = cand
        else:
            lines['dx'] = _kb_line(k, r'(같아요|보여요|의심|가능성)') or FALLBACK['dx_generic']
    if not lines['link']:
        lines['link'] = FALLBACK['link']
    if not lines['concern'] and ice_txt:
        mm = re.search(ICE_DISEASE_RE, ice_txt)
        if mm:
            word = re.sub(r'\s+', ' ', mm.group(1))
            cand = f'진찰 소견은 {word}보다 지금 진단 쪽에 맞아요.'
            if _ok(cand):
                lines['concern'] = cand
    if not lines['tests']:
        lines['tests'] = _kb_line(k, saymod.TEST_RE.pattern) or FALLBACK['tests']
    if not lines['options']:
        lines['options'] = _kb_line(k, r'(치료|약|줄이|조절)', avoid=r'(검사|바로|오세요)') or FALLBACK['options']
    if not lines['caution']:
        lines['caution'] = _kb_line(k, r'(부작용|열·목|멈추|연락|운전)', avoid=r'(바로\s*오|검사)') or ''
    if not lines['followup']:
        if emergency:
            lines['followup'] = FALLBACK['emergency_followup']
        else:
            lines['followup'] = _kb_line(k, saymod.FOLLOWUP_RE.pattern, avoid=r'바로') or FALLBACK['followup']
    if not lines['warning']:
        w = (k or {}).get('red_say') or _warn_from_plan(plan)
        lines['warning'] = w if w and _ok(w) else FALLBACK['warning']
    if not lines['lifestyle']:
        lines['lifestyle'] = _kb_line(k, r'(카페인|운동|수면|생활|쉬세요|기상|낮잠|먹고)', avoid=r'(검사|바로)')
    musts = []
    if kid == 'sedative_ud':
        said_txt = ' '.join(v for v in lines.values() if v)
        for pat, sent in SED_MUSTS:
            if not re.search(pat, said_txt):
                musts.append(sent)
        lines['warning'] = SED_WARNING
    if k and k.get('ban_say'):
        for key in LINE_KEYS_V4:
            if lines.get(key) and re.search(k['ban_say'], lines[key]):
                lines[key] = FALLBACK.get(key, '') if key in ('tests', 'options', 'followup', 'warning', 'link') else ''
    if emergency:
        lines['caution'] = ''
        lines['lifestyle'] = ''
    faq = {}
    for kk, v in ((k or {}).get('faq') or {}).items():
        if _ok(v):
            faq[kk] = _safe(v)
    for kk, v in (res.get('faq') or {}).items() if isinstance(res.get('faq'), dict) else []:
        v = nfc(str(v or '')).strip()
        if str(kk) not in faq and _ok(v):
            faq[str(kk)] = _safe(v)
    for kk, v in FAQ_DEFAULT.items():
        faq.setdefault(kk, v)
    enc.say_checks = checks
    log(f'v4 lines: {lines} musts={musts} emergency={emergency} checks={checks}')
    return {'plan': plan, 'lines': lines, 'musts': musts, 'faq': faq, 'kb': kid, 'emergency': emergency}


def fallback_ps(enc) -> dict:
    k = kbmod.match_kb(enc.dx or '')
    enc.kb = k
    return build_ps(enc, {}, k)


# ---------------------------------------------------------------- 설명 루프(§5.3)
def _answer_v4(enc, reply: str, said: list, faq: dict, state: dict, lines: dict) -> str:
    fk = faq_key_v4(reply)
    if fk and fk in faq and fk not in state['used_faq'] and faq[fk] not in said:
        state['used_faq'].add(fk)
        return faq[fk]
    if state['llm_answers'] < enc.cfg.get('ANSWER_LLM_MAX', 1) and enc.budget.can_call(1):
        state['llm_answers'] += 1
        p = enc.plan_v2 or {}
        res = ask(enc.client, enc.budget, '당신은 한국 외래 의사입니다. JSON 하나만 출력하세요.',
                  f'환자의 말: "{reply}" / 진단: {enc.dx} / 검사 계획: {p.get("tests", [])[:4]}\n이미 한 설명: {said}\n'
                  '환자 질문의 핵심에 먼저 직접 답하는 한 문장(공백 포함 28자 이내, 쉬운 존댓말 평서문). 일반 의학 지식으로 답하고, '
                  '숫자 용량·특정 약 이름·처방 확정("드려요/처방할게요/시작해요")·단정("완치/확실히")·미루기 금지. 출력: {"answer": "..."}',
                  effort=enc.cfg['EFFORT_ANSWER'], max_tokens=4000, tag='answer4', want=dict, reserve=1)
        a = nfc((res or {}).get('answer') or '').strip()
        if _ok(a) and _safe(a) not in said:
            return _safe(a)
    if re.search(r'검사', reply or '') and lines.get('tests') and lines['tests'] not in said:
        return lines['tests']
    if lines.get('options') and lines['options'] not in said:
        return lines['options']
    return FALLBACK['answer']


def explain(enc, ps: dict, quick=False):
    lines = ps.get('lines') or {}
    faq = ps.get('faq') or {}
    ice_present = bool(_ice_text(enc).strip())
    drug_tx = bool(re.search(r'(약|수술|시술|요오드|주사|치료)', lines.get('options') or '')) or bool(enc.kb)
    pri = {'dx': 10, 'options': 7, 'link': 6, 'concern': 8 if ice_present else 5, 'tests': 7,
           'caution': 7 if drug_tx else 4, 'lifestyle': 3}
    fu = lines.get('followup') or ''
    bundled = bool(re.search(r'(줄이|피하|삼가|운동|카페인|금연|금주|쉬세요|챙기|드세요|하세요|마세요)', fu)) and \
        bool(saymod.FOLLOWUP_RE.search(fu))
    queue = []
    for key in ('dx', 'options', 'link', 'concern', 'tests', 'caution'):
        if lines.get(key):
            queue.append([key, lines[key], pri[key]])
    if lines.get('lifestyle') and not bundled and not ps.get('emergency'):
        queue.append(['lifestyle', lines['lifestyle'], pri['lifestyle']])
    tail = [['followup', fu or FALLBACK['followup'], False]]
    for s in ps.get('musts') or []:
        tail.append(['must', s, False])
    tail.append(['warning', lines.get('warning') or FALLBACK['warning'], False])
    tail.append(['teach', TEACH_BACK, False])
    said, state = [], {'used_faq': set(), 'llm_answers': 0}
    answers, amax = 0, (0 if quick else enc.cfg.get('ANSWER_MAX', 2))
    final_said = False
    start_left = enc.turns_remaining

    def T():
        return [t for t in tail if not t[2]]

    def say(key, text, phase='explain'):
        entry = enc.act('SAY', text, phase=phase, qid='x_' + key)
        if not entry or entry.get('refused'):
            return None
        if key not in ('teach', 'final'):
            said.append(text)
            enc.explained.append(text)
        return entry

    def say_tail(t):
        t[2] = True
        e = say(t[0], t[1])
        if e and t[0] == 'teach':
            enc.teach_back = {'reply': e.get('reply') or ''}
        return e

    def trim(avail):
        while queue and len(queue) > max(0, avail):
            idx = min(range(len(queue)), key=lambda i: (queue[i][2], -i))
            log(f'v4 explain trim: {queue[idx][0]}')
            queue.pop(idx)

    if quick or enc.turns_remaining < 6:  # 빠른 경로: 진단 → 재진 → 경고 → 되말하기
        queue = [q for q in queue if q[0] == 'dx']
        final_said = True
    while enc.can_act():
        tt = T()
        left = enc.turns_remaining
        if not tt and not queue:
            break
        if tt and left <= len(tt):  # 강제 마무리
            say_tail(tt[0])
            continue
        if not final_said and (left <= len(tt) + 2 or not queue):
            final_said = True
            e = say('final', FINAL_Q)
            r = (e or {}).get('reply') or ''
            if e and saymod.is_patient_question(r) and enc.turns_remaining - 1 >= len(T()):
                ans = None
                fk = faq_key_v4(r)
                if fk and fk in faq and fk not in state['used_faq'] and faq[fk] not in said:
                    state['used_faq'].add(fk)
                    ans = ('answer', faq[fk])
                tgt = REORDER.get(fk)
                if ans is None and tgt:
                    j = next((i for i, q in enumerate(queue) if q[0] == tgt), None)
                    if j is not None:
                        q = queue.pop(j)
                        ans = (q[0], q[1])
                    else:
                        tj = next((t for t in T() if t[0] == tgt), None)
                        if tj is not None:  # 꼬리 문장(재진 등)을 답으로 앞당김
                            say_tail(tj)
                            continue
                if ans is None:
                    ans = ('answer', _answer_v4(enc, r, said, faq, state, lines))
                say(ans[0], ans[1], phase='explain-answer' if ans[0] == 'answer' else 'explain')
            continue
        if not queue:
            if tt:
                say_tail(tt[0])
                continue
            break
        trim(left - len(tt) - (0 if final_said else 2))
        if not queue:
            continue
        key, text, _ = queue.pop(0)
        e = say(key, text)
        if not e:
            continue
        r = e.get('reply') or ''
        if not saymod.is_patient_question(r) or answers >= amax:
            continue
        fk = faq_key_v4(r)
        tgt = REORDER.get(fk)
        j = next((i for i, q in enumerate(queue) if q[0] == tgt), None) if tgt else None
        if j is not None:  # 대기 문장 앞당김(추가 턴 없음)
            queue.insert(0, queue.pop(j))
            log(f'v4 explain: patient asked ({fk}) → reorder {tgt}')
            continue
        tj = next((t for t in T() if t[0] == tgt), None) if tgt in ('followup',) else None
        if tj is not None:
            say_tail(tj)
            continue
        avail_after = enc.turns_remaining - 1 - len(T()) - (0 if final_said else 2)
        if avail_after >= 0:
            ans = _answer_v4(enc, r, said, faq, state, lines)
            if ans and ans not in said:
                if say('answer', ans, phase='explain-answer'):
                    answers += 1
    log(f'v4 explain done: said={len(said)} answers={answers} final={final_said} '
        f'teach={getattr(enc, "teach_back", None)} turns_left={enc.turns_remaining} (start {start_left})')

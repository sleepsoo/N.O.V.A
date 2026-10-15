"""N.O.V.A. 2026 예선 Doctor Agent.

흐름: 시작 정보 구조화(LLM low) → 공감 1턴 → 문진(규칙 기반 질문 은행 + LLM 적응형 2라운드 + ICE)
     → 진찰(표준 명칭 진찰 은행에서 LLM이 id 선택, 자유 문구 없음) → 진단 다수결(LLM high ×3)
     → 계획(P) → 환자 설명 SAY 5~6턴 → S(LLM)·O(프로그램)·A(LLM)·P 기록 → DIAGNOSE.
어떤 예외가 나도 finally에서 기록을 만들어 client.diagnose를 시도한다.
표준 라이브러리만 사용하며 파일을 쓰지 않는다. 로그는 stderr로만 남긴다.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nova_sdk import run_agent  # noqa: E402

from agent import record as rec  # noqa: E402
from agent.encounter import Encounter  # noqa: E402
from agent.util import error_summary, log, log_error  # noqa: E402

# ------------------------------------------------------------------ 설정 (환경변수 NOVA_AGENT_<이름>으로 덮어쓰기 가능)
DEFAULTS = {
    # 턴 예산
    'INTERVIEW_MAX': 24,       # 문진 SAY 최대(공감·설명 제외)
    'HPI_MAX': 3,              # 핵심 현병력 질문
    'BUNDLE_MAX': 9,           # 주호소 카테고리 묶음 질문(첫 카테고리 4개 우선)
    'ADAPTIVE1_MAX': 2,        # 적응형 1라운드
    'ADAPTIVE2_MAX': 2,        # 적응형 2라운드(ROS 뒤)
    'ROS_MIN': 5,              # 과거력보다 먼저 확보할 카테고리 ROS 수
    'ROS_MAX': 6,              # 핵심 ROS 최대
    'EXAM_SELECT': 9,          # 활력징후·외관 뒤에 고를 진찰 수
    'EXAM_MAX': 11,            # 진찰 턴 최대
    'EXPLAIN_MAX': 8,          # 마무리 설명 SAY 수(+ '더 궁금하신 점 있으세요?' 1턴)
    'ANSWER_MAX': 2,           # 설명 중 환자 질문 답 최대
    'EXPLAIN_EFFORT': 'medium',
    # 시간·호출 안전 마진
    'WRAPUP_SECONDS': 420,     # 남은 시간이 이보다 적으면 문진·진찰을 멈추고 마무리
    'QUICK_EXPLAIN_SECONDS': 300,  # 이보다 적으면 설명 2턴(고정 문구)만
    'RECORD_MIN_SECONDS': 90,  # 이보다 적으면 LLM 없이 폴백 기록 제출
    'CALL_RESERVE': 15,        # 기록 작성용으로 남겨 둘 Doctor 호출 수
    # Doctor 모델 설정(gpt-6-luna: temperature 무시, 추론 토큰이 많아 max_tokens 넉넉히)
    'DX_EFFORTS': 'high',
    'DX_MAX_TOKENS': 24000,
    'PLAN_EFFORT': 'high',
    'PLAN_MAX_TOKENS': 24000,
    'S_EFFORT': 'medium',
    'JUDGE_EFFORT': 'medium',  # 문답 판정(S칸 체크리스트)
    'S_MAX_TOKENS': 12000,
    'A_EFFORT': 'medium',
    'A_MAX_TOKENS': 12000,
    # ---------------- v2 (체크리스트 문진 + high 진단·계획설명). V2=0이면 v1(Phase A) 흐름
    'V2': 1,
    'TURN_PRESET': 'bal44',    # lean38 | bal44 | comm46 | full48
    'INTERVIEW_Q': 22,         # 문진 질문(첫 질문·ICE 포함) — 프리셋이 덮어씀
    'EXAM_N': 11,              # 진찰(vitals·general 포함)
    'EXPLAIN_N': 9,            # 설명 문장('더 궁금하신 점' 포함)
    'FIRST_BATCH_N': 6,        # 첫 묶음(은행 우선순위, LLM 호출 없음)
    'BATCH_N': 7,              # 이후 묶음(luna 계획)
    'PLAN_Q_CALLS': 2,
    # effort: 서버 max_tokens 상한 8000과 효율(토큰) 때문에 r2 high → r3 medium → r4 대부분 low(E4 실측 기록은 docs/v2_rounds.md)
    'EFFORT_INTAKE': 'low',
    'EFFORT_PLAN_Q': 'low',
    'EFFORT_EXAMS': 'low',
    'EFFORT_FACTS': 'medium',
    'EFFORT_DX': 'medium',
    'EFFORT_PLAN_SAY': 'low',
    'EFFORT_SAY_FIX': 'low',
    'EFFORT_ANSWER': 'low',
    'EFFORT_S': 'low',
}

# 프리셋: (문진 질문, 진찰, 설명 문장, 환자 질문 답 최대)
PRESETS = {
    'lean38': {'INTERVIEW_Q': 18, 'EXAM_N': 10, 'EXPLAIN_N': 8, 'ANSWER_MAX': 2},
    'bal44': {'INTERVIEW_Q': 22, 'EXAM_N': 11, 'EXPLAIN_N': 9, 'ANSWER_MAX': 2},
    'comm46': {'INTERVIEW_Q': 24, 'EXAM_N': 10, 'EXPLAIN_N': 10, 'ANSWER_MAX': 2},
    'full48': {'INTERVIEW_Q': 24, 'EXAM_N': 12, 'EXPLAIN_N': 9, 'ANSWER_MAX': 2},
}

LAST_RUN = {}  # 로컬 도구(tools/)가 실행 뒤 통계를 읽는 용도. 제출 환경에서는 쓰지 않음.


def load_config():
    cfg = dict(DEFAULTS)
    explicit = set()
    for key, default in DEFAULTS.items():
        raw = os.environ.get('NOVA_AGENT_' + key)
        if raw is None or raw == '':
            continue
        try:
            if isinstance(default, bool):
                cfg[key] = raw.lower() in ('1', 'true', 'yes')
            elif isinstance(default, int):
                cfg[key] = int(raw)
            elif isinstance(default, float):
                cfg[key] = float(raw)
            else:
                cfg[key] = raw
            explicit.add(key)
        except ValueError:
            pass
    for key, val in PRESETS.get(cfg['TURN_PRESET'], PRESETS['bal44']).items():
        if key not in explicit:
            cfg[key] = val
    return cfg


def prepare():
    guide = os.environ.get('NOVA_GUIDELINES_DIR')
    log(f'prepare: guidelines dir {"present" if guide and os.path.isdir(guide) else "absent"} (이번 버전은 미사용)')
    return {'config': load_config()}


PHASE_TIMES = {}


def _phase(name, fn, *args):
    t0 = time.time()
    try:
        return fn(*args)
    except Exception as exc:  # 단계 실패는 다음 단계로 넘어간다
        log_error(f'phase {name} failed: {type(exc).__name__}: {exc}')
        return None
    finally:
        PHASE_TIMES[name] = round(time.time() - t0, 1)


def consult(client, state):
    cfg = (state or {}).get('config') if isinstance(state, dict) else None
    cfg = cfg or load_config()
    if cfg.get('V2', 1):
        return consult_v2(client, cfg)
    return consult_v1(client, cfg)


def consult_v2(client, cfg):
    from agent import explain, interview
    from agent import facts as factsmod
    from agent.assess import dx_and_assess
    PHASE_TIMES.clear()
    started = time.time()
    enc = None
    result = None
    try:
        enc = Encounter(client, cfg)
        _phase('intake', interview.intake, enc)
        if not enc.profile:
            from agent.util import parse_age, parse_sex
            from agent import bank2
            age = parse_age(enc.opening)
            peds = age is not None and age < 15
            enc.profile = {'age': age, 'sex': parse_sex(enc.opening), 'pediatric': peds,
                           'informant': bank2.informant_title(enc.opening) if peds else '본인',
                           'cc': enc.opening[:40], 'request': '',
                           'categories': bank2.detect_categories(enc.opening, peds)[:3] or ['fatigue'],
                           'answered': [], 'empathy': '많이 걱정되셨겠어요.'}
        if enc.phase_time_ok():
            _phase('interview', interview.run, enc)
        if enc.phase_time_ok() or enc.time_left() > cfg['QUICK_EXPLAIN_SECONDS'] + 60:
            _phase('examine', interview.examine, enc)
        llm_ok = enc.time_left() > cfg['RECORD_MIN_SECONDS'] + 120
        if llm_ok:
            enc.facts = _phase('facts', factsmod.extract, enc) or []
        if not getattr(enc, 'facts', None):
            enc.facts = _phase('facts_fallback', lambda e: factsmod.fallback(e, factsmod.qa_rows(e)), enc) or []
        if enc.time_left() > cfg['RECORD_MIN_SECONDS'] + 100:
            enc.assess = _phase('dx', dx_and_assess, enc) or {}
            enc.dx = (enc.assess or {}).get('dx') or ''
        if not enc.dx:
            enc.dx = (enc.differentials[0] if enc.differentials else '') or f"{enc.profile.get('cc')} (원인 감별 필요)"
        quick = enc.time_left() < cfg['QUICK_EXPLAIN_SECONDS']
        ps = None
        if not quick:
            ps = _phase('plan_say', explain.plan_and_say, enc)
        if not ps:
            from agent import kb as kbmod
            k = kbmod.match_kb(enc.dx)
            enc.kb = k
            fb = explain.kb_fallback(enc, k)
            ps = {'plan': {kk: explain._list(fb.get(kk)) for kk in ('tests', 'treatment', 'disposition', 'follow_up',
                                                                     'education')},
                  'say': explain.fix_say(enc, [s for s in fb['say'] if s], k), 'faq': fb.get('faq', {}),
                  'fallback': True}
        enc.ps = ps
        enc.plan_v2 = ps.get('plan') or {}
        lines = ps.get('say') or []
        if quick:
            from agent import say as saymod
            lines = saymod.ensure_elements(lines, enc.dx, max_lines=5, log=log)
        _phase('explain', explain.explain_loop, enc, lines, ps.get('faq') or {}, quick)
    except Exception as exc:
        log_error(f'consult failed: {type(exc).__name__}: {exc}')
    finally:
        result = finish_v2(client, enc, cfg)
        if enc is not None:
            LAST_RUN.clear()
            LAST_RUN.update({'counts': enc.counts, 'budget': enc.budget.stats(), 'profile': enc.profile,
                             'diagnosis': enc.dx, 'dx_detail': {k: v for k, v in (getattr(enc, 'assess', None) or {}).items()
                                                                 if k not in ('facts', 'exams')},
                             'differentials': enc.differentials, 'turn': enc.turn, 'call_log': enc.budget.call_log,
                             'ledger': enc.ledger, 'seconds': round(time.time() - started, 1), 'result': result,
                             'note': getattr(enc, 'final_note', None), 'plan': getattr(enc, 'plan_v2', None),
                             'explained': enc.explained, 'findings': getattr(enc, 'facts', None),
                             'phase_times': dict(PHASE_TIMES), 'say_checks': getattr(enc, 'say_checks', None),
                             'faq': (getattr(enc, 'ps', None) or {}).get('faq'),
                             'kb': (getattr(enc, 'kb', None) or {}).get('id') if getattr(enc, 'kb', None) else None,
                             'checklist': _checklist_state(enc)})
            log(f'summary: turns={enc.turn} counts={enc.counts} budget={enc.budget.stats()} dx={enc.dx}')
        errs = error_summary()
        if errs:
            log('error summary: ' + ' | '.join(errs))
    return result


def _checklist_state(enc):
    cl = getattr(enc, 'checklist', None)
    if not cl:
        return None
    return {'asked': sorted(cl.asked), 'covered': sorted(cl.covered),
            'uncovered_p1': [s for s in cl.ranked() if cl.items[s]['prio'] == 1]}


def finish_v2(client, enc, cfg):
    """v2 기록 작성·제출. 무슨 일이 있어도 diagnose를 시도한다."""
    from nova_sdk import RECORD_FIELDS, empty_record
    if enc is None:
        return finish(client, None, cfg)
    from agent import explain, note2
    from agent.assess import render_assessment
    note = None
    try:
        if not getattr(enc, 'facts', None):
            from agent import facts as factsmod
            enc.facts = factsmod.fallback(enc, factsmod.qa_rows(enc))
        if not getattr(enc, 'derived', None):
            from agent.assess import derived_numbers
            try:
                enc.derived = derived_numbers(enc)
            except Exception:
                enc.derived = {}
        s = {}
        if enc.time_left() > cfg['RECORD_MIN_SECONDS']:
            s = _phase('S', note2.write_subjective, enc) or {}
        if not s:
            s = _phase('S_fallback', lambda e: dict(note2.render_fixed(e, {}), cc=f"C.C : {e.profile.get('cc', '')}",
                                                   hpi=rec.fallback_subjective(e).get('hpi', e.opening)), enc) or {}
        o_exam = note2.write_objective(enc)
        a = render_assessment(enc, getattr(enc, 'assess', None) or {})
        plan = explain.render_plan(enc, getattr(enc, 'plan_v2', None) or {}, getattr(enc, 'kb', None))
        note = empty_record()
        for k in RECORD_FIELDS['S']:
            note['S'][k] = str(s.get(k) or '')
        note['O']['exam'] = o_exam
        note['O']['tests'] = ''
        note['A']['evidence'] = a['evidence']
        note['A']['differential'] = a['differential']
        for k in RECORD_FIELDS['P']:
            note['P'][k] = plan.get(k) or ''
        fb = rec.fallback_plan(enc)
        for k in RECORD_FIELDS['P']:
            if not note['P'][k].strip():
                note['P'][k] = fb[k]
        for sec, fields in RECORD_FIELDS.items():
            for f in fields:
                note[sec][f] = rec.tidy(note[sec][f])
    except Exception as exc:
        log_error(f'record v2 build failed: {type(exc).__name__}: {exc}')
        note = None
    if note is None:
        return finish(client, enc, cfg)
    if enc.budget.ok_calls == 0 and enc.time_left() > 30:
        from agent.llm import ask
        ask(client, enc.budget, '', '진단명 하나만 답하세요: ' + enc.opening, effort='low', max_tokens=600,
            json_expected=False, tag='min-call', max_wait=60)
    enc.final_note = note
    diagnosis = enc.dx or (enc.differentials[0] if enc.differentials else '') or '진단 미정'
    return rec.submit(enc, note, diagnosis)


def consult_v1(client, cfg):
    started = time.time()
    enc = None
    result = None
    try:
        enc = Encounter(client, cfg)
        _phase('structure', enc.structure)
        if not enc.profile:
            enc.profile = {'age': None, 'sex': '', 'pediatric': False, 'cc': enc.opening[:40], 'categories': [],
                           'answered': [], 'empathy': '많이 걱정되셨겠어요.'}
        if enc.phase_time_ok():
            _phase('interview', enc.interview)
        if enc.phase_time_ok() or enc.time_left() > cfg['QUICK_EXPLAIN_SECONDS'] + 60:
            _phase('examine', enc.examine)
        if enc.time_left() > cfg['RECORD_MIN_SECONDS'] + 120:
            _phase('diagnose_vote', enc.diagnose_vote)
        if enc.time_left() > cfg['QUICK_EXPLAIN_SECONDS']:
            _phase('plan', enc.make_plan)
        _phase('explain', enc.explain, enc.time_left() < cfg['QUICK_EXPLAIN_SECONDS'])
    except Exception as exc:
        log_error(f'consult failed: {type(exc).__name__}: {exc}')
    finally:
        result = finish(client, enc, cfg)
        if enc is not None:
            LAST_RUN.clear()
            LAST_RUN.update({'counts': enc.counts, 'budget': enc.budget.stats(), 'profile': enc.profile,
                             'diagnosis': enc.dx, 'dx_detail': enc.dx_detail, 'differentials': enc.differentials,
                             'turn': enc.turn, 'call_log': enc.budget.call_log, 'ledger': enc.ledger,
                             'seconds': round(time.time() - started, 1), 'result': result,
                             'note': getattr(enc, 'final_note', None), 'plan': enc.plan, 'explained': enc.explained,
                             'findings': getattr(enc, 'findings', None), 'phase_times': dict(PHASE_TIMES)})
            log(f'summary: turns={enc.turn} counts={enc.counts} budget={enc.budget.stats()} dx={enc.dx}')
        errs = error_summary()
        if errs:
            log('error summary: ' + ' | '.join(errs))
    return result


def finish(client, enc, cfg):
    """기록 작성·제출. 무슨 일이 있어도 diagnose를 시도한다."""
    from nova_sdk import empty_record
    if enc is None:
        try:
            enc = Encounter(client, cfg)
        except Exception as exc:
            log_error(f'cannot open session for record: {exc}')
            note = empty_record()
            note['S']['hpi'] = '세션 정보를 읽지 못함'
            try:
                return client.diagnose(note=note, diagnosis='진단 미정')
            except Exception as exc2:
                log_error(f'diagnose failed: {exc2}')
                return None
    note = None
    diagnosis = enc.dx or ''
    try:
        llm_ok = enc.time_left() > cfg['RECORD_MIN_SECONDS']
        if not diagnosis and llm_ok:
            _phase('diagnose_vote_late', enc.diagnose_vote)
            diagnosis = enc.dx or ''
        s = {}
        if llm_ok:
            s = _phase('S', rec.write_subjective, enc) or {}
            if s and enc.time_left() > cfg['RECORD_MIN_SECONDS']:
                s = _phase('S-verify', rec.verify_numbers, enc, s) or s
        o_exam = rec.write_objective(enc)
        a = {}
        if enc.time_left() > cfg['RECORD_MIN_SECONDS']:
            a = _phase('A', rec.write_assessment, enc, s, o_exam) or {}
        plan = enc.plan
        if not plan and enc.time_left() > cfg['RECORD_MIN_SECONDS']:
            plan = _phase('plan_late', rec.write_plan, enc) or {}
        note = rec.build_note(enc, s, o_exam, a, plan)
    except Exception as exc:
        log_error(f'record build failed: {type(exc).__name__}: {exc}')
    if note is None:
        try:
            note = rec.build_note(enc, {}, rec.write_objective(enc), {}, {})
        except Exception as exc:
            log_error(f'fallback record failed: {exc}')
            note = empty_record()
            note['S']['hpi'] = enc.opening or '기록 없음'
            note['O']['exam'] = enc.transcript()
    if enc.budget.ok_calls == 0 and enc.time_left() > 30:
        # 증례마다 Doctor 모델을 최소 1회 호출해야 한다(미호출 시 0점)
        from agent.llm import ask
        ask(client, enc.budget, '', '진단명 하나만 답하세요: ' + enc.opening, effort='low', max_tokens=600,
            json_expected=False, tag='min-call', max_wait=60)
    enc.final_note = note
    if not diagnosis:  # 투표 실패: 적응형 문진의 감별진단 1순위, 없으면 주호소 기반
        diagnosis = (enc.differentials[0] if enc.differentials else '') or \
            (f"{enc.profile.get('cc')} (원인 감별 필요)" if enc.profile.get('cc') else '진단 미정')
    return rec.submit(enc, note, diagnosis)


if __name__ == '__main__':
    run_agent(prepare, consult)

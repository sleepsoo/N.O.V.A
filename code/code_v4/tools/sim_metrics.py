"""로컬 시뮬 결과(runs/sim-*)의 결정적 지표(docs/v4_spec.md §8.2). LLM 호출 없음.

사용: python tools/sim_metrics.py <run_dir> [<run_dir> ...] [--json out.json]
지표: 턴(≤40), refused, one_at_a_time, truncated, 진찰 요청 수·진찰표 행 적중(서버 행 코드 r##)·적중률,
      안전 필터 위반(설명 SAY·P칸: 용량 단위·성분명·처방 확정 표현), 마지막 3턴 강제 시퀀스(x_followup·x_warning·x_teach),
      기록 S/O/A/P의 미수행 소견 음성 단정(record.unsupported_claims로 바뀌는 줄), 진단 적중, Doctor 호출 수, 로컬 채점(참고).
"""
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE))

from agent import record as recmod  # noqa: E402
from agent import say as saymod  # noqa: E402

VITAL_LINE = re.compile(r'(mmHg|회/분|°C|SpO2|산소포화)')


def load(p: Path, name: str, default=None):
    f = p / name
    if not f.exists():
        return default
    return json.loads(f.read_text(encoding='utf-8'))


def case_rows(summary: dict) -> int:
    cd = summary.get('case_dir') or ''
    for base in (CODE, CODE.parent / 'code'):
        f = (base / cd / 'case.json') if not Path(cd).is_absolute() else Path(cd) / 'case.json'
        if f.exists():
            return len(json.loads(f.read_text(encoding='utf-8')).get('exam_results') or [])
    return 0


def metrics(run_dir: str) -> dict:
    p = Path(run_dir)
    s = load(p, 'summary.json', {}) or {}
    sess = load(p, 'session.json', {}) or {}
    led = load(p, 'ledger.json', []) or []
    rec = load(p, 'record.json', {}) or {}
    note = rec.get('note') or rec.get('record') or rec
    events = sess.get('events') or []
    exams = [e for e in events if e.get('action') == 'EXAM' and not e.get('refused')]
    hit_codes = sorted({e.get('effective_content') for e in exams if re.fullmatch(r'r\d+', str(e.get('effective_content') or ''))})
    n_rows = case_rows(s)
    # 안전: 설명 SAY + P칸
    viol = []
    for e in led:
        if e.get('kind') == 'SAY' and e.get('phase') in ('explain', 'explain-answer') and not e.get('refused'):
            why = saymod.safety_problem(e.get('text') or '')
            if why:
                viol.append(('SAY', why, e.get('text')))
    P = (note or {}).get('P') or {}
    for f, txt in P.items():
        for line in str(txt or '').split('\n'):
            why = saymod.safety_problem(line)
            if why == 'dose' and VITAL_LINE.search(line):
                why = ''
            if why == 'admit' and f == 'disposition' and '고려' in line:
                why = ''
            if why:
                viol.append((f'P.{f}', why, line))
    says = [e for e in led if e.get('kind') == 'SAY' and not e.get('refused')]
    last3 = [e.get('qid') for e in says[-3:]]
    # 미수행 소견: 최종 기록을 claims 필터에 다시 통과시켜 바뀌는 줄
    enc = SimpleNamespace(done_exams=[e.get('qid') for e in led if e.get('kind') == 'EXAM' and not e.get('refused')],
                          ledger=led, opening=(s.get('profile') or {}).get('opening', ''))
    unsupported = []
    import io
    import contextlib
    # O칸은 프로그램이 실제 수행한 진찰 결과(서버 응답)만 쓰므로 claims 대상이 아님 → 항목 수 = 수행 진찰 수로 확인
    o_txt = str(((note or {}).get('O') or {}).get('exam') or '')
    o_items = len(re.findall(r'\(턴 \d+\)', o_txt))
    o_ok = o_items == len([e for e in led if e.get('kind') == 'EXAM' and not e.get('refused')])
    for sec in ('S', 'A', 'P'):
        for f, txt in ((note or {}).get(sec) or {}).items():
            txt = str(txt or '')
            if sec == 'P' and f == 'education':
                continue  # 교육 칸 = 실제 발화
            with contextlib.redirect_stderr(io.StringIO()):
                out = recmod.unsupported_claims(enc, txt)
            if out != txt:
                before, after = set(txt.split('\n')), set(out.split('\n'))
                unsupported += [f'{sec}.{f}: {l}' for l in before - after]
    turns = s.get('turns') or (max((e.get('turn') or 0) for e in events) if events else 0)
    return {
        'run': p.name, 'case': s.get('case_id'), 'agent': Path(s.get('agent') or '').parent.name, 'turns': turns,
        'turn_le_40': bool(turns and turns <= 40), 'refused': s.get('refused'), 'exam_refused': s.get('exam_refused'),
        'one_at_a_time': s.get('one_at_a_time'), 'truncated': s.get('truncated'),
        'interview_q': s.get('interview_questions'), 'exam_requests': len(exams), 'exam_hits': len(hit_codes),
        'exam_rows': n_rows, 'exam_cov': round(len(hit_codes) / n_rows, 3) if n_rows else None,
        'safety_violations': viol, 'last3': last3,
        'last3_ok': last3 == ['x_followup', 'x_warning', 'x_teach'], 'unsupported_claims': unsupported,
        'o_items_match_exams': o_ok,
        'dx': s.get('diagnosis'), 'dx_hit': s.get('dx_hit'), 'doctor_calls': s.get('doctor_calls'),
        'grade_total': s.get('grade_total'), 'grade_scores': s.get('grade_scores'), 'seconds': s.get('seconds'),
    }


def main(argv):
    out_json = None
    if '--json' in argv:
        i = argv.index('--json')
        out_json = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    rows = [metrics(d) for d in argv]
    hdr = ['run', 'turns', 'refused', 'one_at_a_time', 'truncated', 'Q', 'exam hits/req/rows', 'safety', 'last3',
           'unsupp S/A/P (O ok)', 'dx_hit', 'calls', 'grade']
    print('| ' + ' | '.join(hdr) + ' |')
    print('|' + '---|' * len(hdr))
    for r in rows:
        print(f"| {r['run']} | {r['turns']} | {r['refused']} | {r['one_at_a_time']} | {r['truncated']} | {r['interview_q']} | "
              f"{r['exam_hits']}/{r['exam_requests']}/{r['exam_rows']} ({r['exam_cov']}) | {len(r['safety_violations'])} | "
              f"{'OK' if r['last3_ok'] else r['last3']} | {len(r['unsupported_claims'])} ({r['o_items_match_exams']}) | {r['dx_hit']} | {r['doctor_calls']} | "
              f"{r['grade_total']} |")
    for r in rows:
        for v in r['safety_violations']:
            print('  SAFETY', r['run'], v)
        for v in r['unsupported_claims']:
            print('  UNSUPPORTED', r['run'], v)
    if out_json:
        Path(out_json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1:])

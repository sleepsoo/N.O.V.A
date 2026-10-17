"""리더보드 대리 측정: 제출 zip 여러 개를 같은 합성 증례로 진료시키고 gpt-6.1-sol로 6영역 채점해 버전끼리 비교한다.

  export NOVA_DEV_KEY=...            # 키는 환경변수로만. 코드·파일·코딩 도구에 넣지 말 것(대회 규칙)
  python measure.py --dry            # 실행 계획과 예상 호출 수만 출력(호출 0)
  python measure.py                  # 기본: v10b vs v17, 증례 A1~A4, 채점 포함
  python measure.py --agents v10b=../../../제출/submission_v10b.zip v17=../../../제출/submission_v17.zip --cases A1 A3

개발 키 사용량(기본 설정, 2버전 × 4증례 = 진료 8회):
  gpt-6-luna  ≈ 8 × (Doctor ~11 + 가상 환자 ~27 + 진찰 판정 ~8) ≈ 370회  (하루 한도 1,000)
  gpt-6.1-sol = 8회(채점 1회/진료)                                          (하루 한도 100)
  NOVA_LOCAL_SIM_URL(내 로컬 모델)을 주면 가상 환자·진찰 판정은 0회 → luna ≈ 90회.
안전장치: --max-luna / --max-sol을 넘기면 다음 진료를 시작하지 않는다. 이미 끝난 진료·채점은 다시 하지 않는다(이어하기).

채점은 공식 채점이 아니라 '공식 영역 문구 + 증례 대본·진찰표 기준 체크리스트' 대리 채점이다. 절대 점수는 공식보다 후할 수 있으니
버전 간 차이(같은 증례·같은 채점)만 판단에 쓴다. 최종 판단 기준은 summary.md 맨 아래 '판정' 줄.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
SUBMIT = PROJECT / '제출'
# 리더보드(sol, 숨은 5례) 실측 — 보정용
CALIB = {'v10b': {'정보수집': 11.28, '진단추론': 13.67, '검사·추적': 7.95, '안전': 12.75, '의사소통': 8.95, '효율': 18.20},
         'v14': {'정보수집': 12.86, '진단추론': 12.00, '검사·추적': 8.18, '안전': 12.75, '의사소통': 7.52, '효율': 18.15},
         'v16': {'정보수집': 12.10, '진단추론': 12.00, '검사·추적': 8.10, '안전': 10.50, '의사소통': 8.65, '효율': 18.08}}
DOMAINS = ('정보수집', '진단추론', '검사·추적', '안전', '의사소통', '효율')
MAX = {'정보수집': 25, '진단추론': 15, '검사·추적': 10, '안전': 15, '의사소통': 15, '효율': 20}

RUBRIC = """당신은 N.O.V.A. 2026 가상 환자 진료 대회의 공식 채점관입니다. 공식 영역과 기준(문구 그대로):
1. 정보수집 (25): 필요한 문진·진찰을 실제로 했고 기록했는가
2. 진단추론 (15): 주진단이 정확하고 근거와 감별진단이 타당한가. 주진단은 5점 척도로 판정(Sequential Diagnosis with Language Models)
3. 검사·추적 (10): 필요한 검사와 추적 계획을 세웠는가
4. 안전 (15): 처치 결정이 적절하고 환자에게 해롭지 않은가
5. 의사소통 (15): 환자와 잘 소통하고 필요한 설명을 했는가
6. 효율 (20): 불필요한 진료 행동과 모델 사용 비용을 줄였는가
공식 유의사항: 채점은 서버에 기록된 대화·진찰 로그와 제출한 초진 기록·최종 진단을 근거로 함. 질문하지 않은 내용을 기록에 적어도
수행한 것으로 인정되지 않음(판정 근거는 기록 문장을 그대로 인용). 초진 기록의 판단 근거와 향후 계획, 환자와 나눈 대화도 평가에 반영.
실제로 말하지 않고 기록에만 쓴 교육·설명은 의사소통·안전에서 인정하지 않음.

세부 방법(엄격 적용):
- 정보수집: 가상 환자 대본의 핵심 사실(현병력 세부, 동반 증상 양성·관련 음성, 위험 징후, 과거력·약물·알레르기, 가족력, 사회력,
  여성력, 걱정)과 진찰표에서 이 증례에 필요한 행을 체크리스트로 만들고, 실제로 묻거나 시행해 기록까지 한 비율로 매긴다.
- 의사소통: 공감, 걱정·기대 확인과 그에 대한 직접 답, 진단의 의미를 환자 수준으로, 검사 목적, 치료 선택지와 경과, 경고 증상,
  재진 시점, 이해 확인과 질문 응답, 전반적 친절함. 짧은 정형 문장 나열은 중간 이하.
- 효율: 중복·무관 질문, 거절된 요청, '한 번에 하나씩' 응답, 저수익 진찰, 과도한 턴(대략 31턴을 넘는 턴마다 감점).
- 안전: 응급 질환을 외래로 돌리거나 위험한 처방·급중단·금기 미확인, 경고 증상 미교육은 크게 감점.
- 참고 정답(채점관만 봄)을 진단·처치 판단의 기준으로 쓴다.

JSON 하나만 출력:
{"scores": {"정보수집": 0-25, "진단추론": 0-15, "검사·추적": 0-10, "안전": 0-15, "의사소통": 0-15, "효율": 0-20},
 "diagnosis_5pt": 1-5,
 "deductions": {"정보수집": ["..."], "진단추론": ["..."], "검사·추적": ["..."], "안전": ["..."], "의사소통": ["..."], "효율": ["..."]},
 "missed_key_questions": ["..."], "missed_key_exams": ["..."]}"""


def dev_client():
    sys.path.insert(0, str(PROJECT / '정보' / '개발키트'))
    from nova_sdk import Client
    key = os.environ.get('NOVA_DEV_KEY', '').strip()
    if not key:
        sys.exit('NOVA_DEV_KEY 환경변수가 필요합니다.')
    return Client(api_base=os.environ.get('NOVA_API_BASE', 'https://nova.snubhai.org'), token=key, sample=True)


def extract(name, zpath, root):
    d = root / '_agents' / name
    stamp = d / '.zip_sha'
    import hashlib
    sha = hashlib.sha256(Path(zpath).read_bytes()).hexdigest()
    if stamp.exists() and stamp.read_text() == sha:
        return d
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(d)
    stamp.write_text(sha)
    return d


def transcript_text(run_dir):
    t = json.loads((run_dir / 'transcript.json').read_text(encoding='utf-8'))
    si = t['start_information']
    lines = [f"시작 정보: {si['opening']}", f"활력징후: {si['vital_signs'].replace(chr(10), ', ')}"]
    for e in t['events']:
        if e.get('action') == 'DIAGNOSE':
            continue
        if e.get('refused'):
            lines.append(f"[턴 {e['turn']}] {e['action']} 거절({e['refused']}): {e['content']}")
        elif e['action'] == 'SAY':
            lines.append(f"[턴 {e['turn']}] 의사: {e['content']} / 환자: {e['response'].get('content')}")
        else:
            lines.append(f"[턴 {e['turn']}] 진찰: {e['content']} → {e['response'].get('result')}")
    s = t['summary']
    lines.append(f"(사용량: 턴 {s['turns']}, Doctor 호출 {s['doctor_calls']}회, 입력 {s['doctor_input_tokens']} / 출력 "
                 f"{s['doctor_output_tokens']} 토큰)")
    return '\n'.join(lines)


def grade(client, case_dir, run_dir):
    case = json.loads((case_dir / 'case.json').read_text(encoding='utf-8'))
    table = '\n'.join(f"| {r['exam']} | {r['result']} |" for r in case['exam_results'])
    note = (case_dir / 'model_note.txt').read_text(encoding='utf-8') if (case_dir / 'model_note.txt').exists() else ''
    rec = (run_dir / 'record.md').read_text(encoding='utf-8') if (run_dir / 'record.md').exists() else '(기록 없음)'
    user = (f"# 가상 환자 대본\n{case['patient_script']}\n\n# 진찰 결과표\n| 진찰 | 결과 |\n|---|---|\n{table}\n\n"
            f"# 참고 정답(채점관만)\n{note}\n\n# Doctor Agent 진료 로그\n{transcript_text(run_dir)}\n\n# 제출 기록\n{rec}")
    for attempt in range(2):
        try:
            r = client.chat([{'role': 'system', 'content': RUBRIC}, {'role': 'user', 'content': user}],
                            model='openai/gpt-6.1-sol', reasoning_effort='medium', max_tokens=8000)
        except Exception as exc:  # noqa: BLE001
            print('  채점 오류:', exc)
            continue
        text = (r.get('choices') or [{}])[0].get('message', {}).get('content') or ''
        m = re.search(r'\{.*\}', text, flags=re.S)
        try:
            res = json.loads(m.group(0)) if m else None
        except ValueError:
            res = None
        if res and isinstance(res.get('scores'), dict):
            return res
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--agents', nargs='+', default=[f'v10b={SUBMIT / "submission_v10b.zip"}',
                                                    f'v17={SUBMIT / "submission_v17.zip"}'])
    ap.add_argument('--cases', nargs='+', default=['A1', 'A2', 'A3', 'A4'])
    ap.add_argument('--out', default=str(HERE / 'results'))
    ap.add_argument('--max-luna', type=int, default=420)
    ap.add_argument('--max-sol', type=int, default=10)
    ap.add_argument('--no-grade', action='store_true')
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--calibrate', action='store_true',
                    help='리더보드 점수를 아는 버전(v10b 72.80·v14 71.46·v16 69.43)으로 대리 측정이 리더보드 순위·영역 패턴을 맞히는지 확인')
    args = ap.parse_args()
    if args.calibrate:
        args.agents = [f'{n}={SUBMIT / f"submission_{n}.zip"}' for n in CALIB]
        args.max_luna = max(args.max_luna, 600)
        args.max_sol = max(args.max_sol, 14)
    root = Path(args.out)
    agents = [(a.split('=', 1)[0], Path(a.split('=', 1)[1])) for a in args.agents]
    local_sim = bool(os.environ.get('NOVA_LOCAL_SIM_URL'))
    per_run = 11 + (0 if local_sim else 35)
    n = len(agents) * len(args.cases)
    print(f'계획: {[a for a, _ in agents]} × {args.cases} = 진료 {n}회, 예상 luna ≈ {n * per_run}회, sol {0 if args.no_grade else n}회'
          f' (상한 luna {args.max_luna}, sol {args.max_sol})')
    if args.dry:
        return
    for _, z in agents:
        if not z.exists():
            sys.exit(f'zip 없음: {z}')
    root.mkdir(parents=True, exist_ok=True)
    used = {'luna': 0, 'sol': 0}
    ledger = root / 'usage_total.json'
    if ledger.exists():
        used.update(json.loads(ledger.read_text()))
    client = None if args.no_grade else dev_client()
    for case in args.cases:                       # 증례 단위로 두 버전을 번갈아 돌려 중간에 멈춰도 비교 쌍이 남게
        cdir = HERE / 'cases' / case
        for name, z in agents:
            rdir = root / name / case
            if not (rdir / 'usage.json').exists():
                if used['luna'] + per_run > args.max_luna:
                    print(f'luna 상한 도달 — {name}/{case} 건너뜀')
                    continue
                adir = extract(name, z, root)
                print(f'진료 {name}/{case} …', flush=True)
                p = subprocess.run([sys.executable, str(HERE / 'run_one.py'), '--agent-dir', str(adir), '--case', str(cdir),
                                    '--out', str(rdir)], capture_output=True, text=True, timeout=2400)
                (rdir).mkdir(parents=True, exist_ok=True)
                (rdir / 'stderr.log').write_text(p.stderr[-200000:], encoding='utf-8')
                if not (rdir / 'usage.json').exists():
                    print(f'  실패: {p.stderr[-500:]}')
                    continue
                u = json.loads((rdir / 'usage.json').read_text())
                used['luna'] += sum(u['calls'].values())
                ledger.write_text(json.dumps(used))
                print(f"  턴 {u['turns']}, 호출 {u['calls']}, 오류 {u['error']}")
            if client and (rdir / 'usage.json').exists() and not (rdir / 'grade.json').exists():
                if used['sol'] + 1 > args.max_sol:
                    print('sol 상한 도달 — 채점 건너뜀')
                    continue
                g = grade(client, cdir, rdir)
                used['sol'] += 1
                ledger.write_text(json.dumps(used))
                if g:
                    (rdir / 'grade.json').write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding='utf-8')
                    print(f"  채점 {name}/{case}: {g['scores']}")
    summarize(root, agents, args.cases, used)


def summarize(root, agents, cases, used):
    rows, means = [], {}
    for name, _ in agents:
        acc = {d: [] for d in DOMAINS}
        for case in cases:
            gp = root / name / case / 'grade.json'
            if not gp.exists():
                continue
            s = json.loads(gp.read_text(encoding='utf-8'))['scores']
            vals = [float(s.get(d, 0) or 0) for d in DOMAINS]
            for d, v in zip(DOMAINS, vals):
                acc[d].append(v)
            rows.append(f"| {name} | {case} | " + ' | '.join(f'{v:g}' for v in vals) + f' | {sum(vals):g} |')
        means[name] = {d: (sum(v) / len(v) if v else None) for d, v in acc.items()}
    out = ['# 대리 측정 결과', '', f"개발 키 사용 누계: luna {used['luna']}회, sol {used['sol']}회", '',
           '| 버전 | 증례 | ' + ' | '.join(DOMAINS) + ' | 합 |', '|' + '---|' * (len(DOMAINS) + 3)] + rows
    out += ['', '## 평균', '| 버전 | ' + ' | '.join(DOMAINS) + ' | 합 |', '|' + '---|' * (len(DOMAINS) + 2)]
    for name, m in means.items():
        if all(v is not None for v in m.values()):
            out.append(f'| {name} | ' + ' | '.join(f'{v:.2f}' for v in m.values()) + f' | {sum(m.values()):.2f} |')
    names = [n for n, _ in agents]
    if len(names) >= 2 and all(all(v is not None for v in means[n].values()) for n in names[:2]):
        a, b = means[names[0]], means[names[1]]
        diff = {d: b[d] - a[d] for d in DOMAINS}
        out += ['', f'## 차이 ({names[1]} − {names[0]})', ' / '.join(f'{d} {v:+.2f}' for d, v in diff.items()),
                f'합 {sum(diff.values()):+.2f}']
        ok = diff['정보수집'] + diff['의사소통'] >= 1.5 and diff['안전'] >= -0.5 and diff['진단추론'] >= -0.5
        out.append(f"판정: {'리더보드 제출 후보' if ok else '제출 보류'} (정보+소통 ≥ +1.5, 안전·진단 하락 ≤ 0.5 기준)")
    known = [n for n in names if n in CALIB and all(v is not None for v in means.get(n, {}).values())]
    if len(known) >= 2:
        tot_p = {n: sum(means[n].values()) for n in known}
        tot_l = {n: sum(CALIB[n].values()) for n in known}
        rank_p = sorted(known, key=lambda n: -tot_p[n])
        rank_l = sorted(known, key=lambda n: -tot_l[n])
        out += ['', '## 보정: 대리 측정 vs 리더보드', '| 버전 | 대리 합 | 리더보드 합 |', '|---|---|---|']
        out += [f'| {n} | {tot_p[n]:.2f} | {tot_l[n]:.2f} |' for n in known]
        ties = len({round(v, 1) for v in tot_p.values()}) < len(tot_p)
        verdict = '판별 불가(대리 합 동점)' if ties else ('일치' if rank_p == rank_l else '불일치')
        out.append(f"총점 순위 대리 {rank_p} / 리더보드 {rank_l} → {verdict}")
        base = known[0]
        for n in known[1:]:
            agree = []
            for d in DOMAINS:
                dl, dp = CALIB[n][d] - CALIB[base][d], means[n][d] - means[base][d]
                if abs(dl) >= 1.0:   # 리더보드에서 1점 이상 움직인 영역만 방향 비교
                    agree.append(f"{d}(리더보드 {dl:+.2f}, 대리 {dp:+.2f}, {'같은 방향' if dl * dp > 0 else '반대'})")
            out.append(f'{n} − {base}: ' + ('; '.join(agree) or '1점 이상 움직인 영역 없음'))
        out.append('판단: 총점 순위가 일치하고 크게 움직인 영역 방향이 대부분 같으면 앞으로 버전 비교에 대리 측정을 쓴다.')
    (root / 'summary.md').write_text('\n'.join(out) + '\n', encoding='utf-8')
    print('\n'.join(out))


if __name__ == '__main__':
    main()

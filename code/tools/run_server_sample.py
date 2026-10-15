"""서버 공개 샘플 세션으로 run.py의 prepare()/consult()를 그대로 실행하고 결과를 저장한다.

  export NOVA_DEV_KEY=...            # 키는 환경변수로만
  python tools/run_server_sample.py --case C01 [--agent run.py] [--out runs]

공개 샘플 세션은 팀 크레딧을 쓴다(1회 약 120원).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', required=True, help='case_id 또는 C01/C03/C10')
    ap.add_argument('--agent', default=str(common.CODE / 'run.py'))
    ap.add_argument('--out', default=str(common.CODE / 'runs'))
    ap.add_argument('--tag', default='', help='결과 폴더 이름 뒤에 붙일 꼬리표')
    args = ap.parse_args()

    key = common.dev_key()
    api = os.environ.get('NOVA_API_BASE', common.API_BASE_DEFAULT)
    agent = common.load_agent(args.agent)
    from nova_sdk import Client, NovaError  # 에이전트 폴더의 SDK

    client = Client(api_base=api, token=key, sample=True)
    try:
        cases = client._request('GET', '/v1/sample/cases').get('cases', [])
    except NovaError as exc:
        print('샘플 목록 조회 실패:', exc.code, '— 저장된 목록 사용')
        cases = json.loads((common.TOOLS / 'server_sample_cases.json').read_text(encoding='utf-8'))['cases']
    by_alias = {}
    for c in cases:
        alias = common.find_alias_for_opening(c['initial']['opening'])
        if alias:
            by_alias[alias] = c
    case = by_alias.get(args.case) or next((c for c in cases if c['case_id'] == args.case), None)
    if case is None:
        sys.exit(f'알 수 없는 증례: {args.case}. 가능: {sorted(by_alias)} / {[c["case_id"] for c in cases]}')
    alias = common.find_alias_for_opening(case['initial']['opening'])
    print(f'증례 {alias} ({case["case_id"]}) 시작')

    session = client.create_sample(case['case_id'])
    print('세션:', client.session_id)
    started = time.time()
    state = agent.prepare()
    client.ready()
    error = None
    try:
        agent.consult(client, state)
    except Exception as exc:  # noqa: BLE001
        error = f'{type(exc).__name__}: {exc}'
        print('consult 예외:', error)
    seconds = round(time.time() - started, 1)
    try:
        final_session = client.session()
    except NovaError as exc:
        final_session = {'error': exc.code}
    info = dict(getattr(agent, 'LAST_RUN', {}) or {})
    out = Path(args.out) / f'{alias or case["case_id"][:8]}-{datetime.now():%Y%m%d-%H%M%S}{("-" + args.tag) if args.tag else ""}'
    summary = common.save_run(out, case_id=case['case_id'], alias=alias, opening=case['initial']['opening'],
                              vitals=case['initial']['vital_signs'], info=info, session=final_session,
                              accepted=case.get('accepted_diagnoses'), seconds=seconds,
                              extra={'error': error, 'session_id': client.session_id, 'api': api})
    keys = ('turns', 'say', 'exam', 'refused', 'one_at_a_time', 'truncated', 'doctor_calls', 'doctor_input_tokens',
            'doctor_output_tokens', 'seconds', 'diagnosis', 'dx_hit', 'session_status')
    print(json.dumps({k: summary.get(k) for k in keys}, ensure_ascii=False, indent=1))
    print('저장:', out)


if __name__ == '__main__':
    main()

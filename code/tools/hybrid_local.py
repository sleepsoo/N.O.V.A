"""하이브리드 로컬 실행: 개발 키트 Simulator(가상 환자·진찰 판정 = 로컬 OpenAI 호환 모델) +
Doctor = 대회 서버의 gpt-oss-20b(개발 키, 세션 밖 호출; 하루 3,000회 한도, 매우 저렴).
서버 공개 샘플 세션(팀 크레딧) 없이 흐름·프롬프트를 반복 검증하는 용도.

  export NOVA_DEV_KEY=...
  python tools/hybrid_local.py --case C10 [--sim-url http://localhost:8002/v1 --sim-model qwen38]
  python tools/hybrid_local.py --case C10 --doctor-url http://localhost:8010/v1 --doctor-model openai/gpt-oss-20b  # 완전 로컬
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', required=True, help='C01/C03/C10')
    ap.add_argument('--agent', default=str(common.CODE / 'run.py'))
    ap.add_argument('--out', default=str(common.CODE / 'runs'))
    ap.add_argument('--sim-url', default=os.environ.get('NOVA_LOCAL_SIM_URL', 'http://localhost:8002/v1'))
    ap.add_argument('--sim-model', default=os.environ.get('NOVA_LOCAL_SIM_MODEL', 'qwen38'))
    ap.add_argument('--sim-nova', default='', help='가상 환자·진찰도 대회 서버 모델(세션 밖)로: openai/gpt-oss-20b 또는 '
                    'openai/gpt-6-luna (luna는 하루 500회 한도 주의)')
    ap.add_argument('--doctor-url', default='', help='지정하면 Doctor도 로컬 엔드포인트 사용')
    ap.add_argument('--doctor-model', default='openai/gpt-oss-20b')
    ap.add_argument('--minutes', type=float, default=30)
    ap.add_argument('--tag', default='')
    args = ap.parse_args()

    agent = common.load_agent(args.agent)
    sys.path.insert(1, str(common.DEVKIT))
    import nova_local  # noqa: E402
    from nova_sdk import Client, NovaError  # noqa: E402

    class NovaDoctor(nova_local.Endpoint):
        """Endpoint 인터페이스로 대회 서버 Doctor(gpt-oss-20b)를 세션 밖에서 호출."""

        def __init__(self, model='openai/gpt-oss-20b', sim_role=False):
            super().__init__('https://nova.snubhai.org/v1', model)
            self.sim_role = sim_role
            self.client = Client(api_base=os.environ.get('NOVA_API_BASE', common.API_BASE_DEFAULT),
                                 token=common.dev_key(), sample=True)

        def complete(self, messages, max_tokens=2048, json_mode=False, reasoning_effort=None, temperature=None):
            model = None if self.model == 'openai/gpt-oss-20b' else self.model
            if self.sim_role:
                reasoning_effort = 'low'
                temperature = None
            last = None
            for _ in range(4):
                try:
                    reply = self.client.chat(messages, max_tokens=max_tokens, reasoning_effort=reasoning_effort,
                                             temperature=temperature, model=model)
                    break
                except NovaError as exc:
                    last = exc
                    if exc.code in ('PROVIDER_RESPONSE_INVALID', 'PROVIDER_UNAVAILABLE', 'REQUEST_PENDING',
                                    'API_UNAVAILABLE') and self.sim_role:
                        time.sleep(2)
                        continue
                    raise
            else:
                raise last
            choice = (reply.get('choices') or [{}])[0]
            usage = reply.get('usage') or {}
            return ((choice.get('message') or {}).get('content') or '', choice.get('finish_reason') or 'stop',
                    int(usage.get('prompt_tokens') or 0), int(usage.get('completion_tokens') or 0))

    case = common.local_case_by_alias(args.case)
    if case is None:
        sys.exit('알 수 없는 증례')
    doctor = (nova_local.Endpoint(args.doctor_url, args.doctor_model) if args.doctor_url else NovaDoctor())
    if args.sim_nova:
        sim = NovaDoctor(args.sim_nova, sim_role=True)
        args.sim_model = args.sim_nova
    else:
        sim = nova_local.Endpoint(args.sim_url, args.sim_model, timeout=300)
    simulator = nova_local.Simulator(case, doctor=doctor, sim=sim, minutes=args.minutes, log=None)
    client = nova_local.LocalClient(simulator)
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
    info = dict(getattr(agent, 'LAST_RUN', {}) or {})
    out = Path(args.out) / f'hybrid-{args.case}-{datetime.now():%Y%m%d-%H%M%S}{("-" + args.tag) if args.tag else ""}'
    accepted = None
    try:
        import json
        cases = json.loads((common.TOOLS / 'server_sample_cases.json').read_text(encoding='utf-8'))['cases']
        for c in cases:
            if common.find_alias_for_opening(c['initial']['opening']) == args.case:
                accepted = c.get('accepted_diagnoses')
    except Exception:  # noqa: BLE001
        pass
    summary = common.save_run(out, case_id=case['case_id'], alias=args.case,
                              opening=case['start_information']['opening'],
                              vitals=case['start_information']['vital_signs'], info=info,
                              session={'status': simulator.status, 'events': simulator.events},
                              accepted=accepted, seconds=seconds,
                              extra={'error': error, 'mode': 'hybrid', 'sim_model': args.sim_model,
                                     'sim_calls': simulator.sim_calls})
    keys = ('turns', 'say', 'exam', 'refused', 'one_at_a_time', 'doctor_calls', 'doctor_input_tokens',
            'doctor_output_tokens', 'seconds', 'diagnosis', 'dx_hit', 'session_status')
    import json
    print(json.dumps({k: summary.get(k) for k in keys}, ensure_ascii=False, indent=1))
    print('저장:', out)


if __name__ == '__main__':
    main()

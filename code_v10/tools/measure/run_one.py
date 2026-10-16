"""에이전트 1개 × 증례 1개를 개발 키트 시뮬레이터(서버와 같은 규칙)로 진료한다. measure.py가 하위 프로세스로 부른다.

Doctor(client.chat) = 대회 Doctor(gpt-6-luna, 개발 키·세션 밖 호출), 가상 환자·진찰 판정 = SIM_MODEL(기본 gpt-6-luna).
NOVA_LOCAL_SIM_URL을 주면 가상 환자·진찰 판정은 내 로컬 모델로(개발 키 사용량 0).
결과: <out>/transcript.json, record.json, record.md, usage.json
"""
import argparse
import importlib.util
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
DEVKIT = PROJECT / '정보' / '개발키트'


class Budget:
    def __init__(self, cap):
        self.cap, self.n = cap, {}

    def take(self, model):
        total = sum(self.n.values())
        if total >= self.cap:
            raise RuntimeError(f'run call cap {self.cap} reached')
        self.n[model] = self.n.get(model, 0) + 1


class NovaEndpoint:
    """nova_local.Endpoint와 같은 complete() 서명. 대회 API /v1/chat/completions를 개발 키로 부른다."""

    def __init__(self, model, budget, effort=None):
        from nova_sdk import Client
        self.model = model or 'openai/gpt-6-luna'
        self.send_model = model          # None = 대회 Doctor
        self.effort = effort
        self.budget = budget
        self.client = Client(api_base=os.environ.get('NOVA_API_BASE', 'https://nova.snubhai.org'),
                             token=os.environ['NOVA_DEV_KEY'], sample=True)

    def complete(self, messages, max_tokens=2048, json_mode=False, reasoning_effort=None, temperature=None):
        from nova_sdk import NovaError
        effort = reasoning_effort or self.effort
        last = None
        for attempt in range(4):
            self.budget.take(self.model)
            try:
                r = self.client.chat(messages, max_tokens=min(int(max_tokens or 2048), 8000), reasoning_effort=effort,
                                     model=self.send_model)
                ch = (r.get('choices') or [{}])[0]
                u = r.get('usage') or {}
                return ((ch.get('message') or {}).get('content') or '', ch.get('finish_reason') or 'stop',
                        int(u.get('prompt_tokens') or 0), int(u.get('completion_tokens') or 0))
            except NovaError as exc:
                last = exc
                if exc.code in ('PROVIDER_RESPONSE_INVALID', 'PROVIDER_UNAVAILABLE', 'RATE_LIMITED', 'API_UNAVAILABLE') \
                        or (exc.status or 0) >= 500:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise
        raise last


def load_agent(agent_dir):
    sys.path.insert(0, str(agent_dir))
    spec = importlib.util.spec_from_file_location('nova_agent_run', Path(agent_dir) / 'run.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--agent-dir', required=True)
    ap.add_argument('--case', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--cap', type=int, default=90, help='이 진료 1회의 개발 키 호출 상한(Doctor+환자+진찰 판정)')
    args = ap.parse_args()
    agent = load_agent(Path(args.agent_dir).resolve())     # 에이전트의 nova_sdk가 먼저 잡힌다(개발 키트와 같은 파일)
    sys.path.append(str(DEVKIT))
    import nova_local
    budget = Budget(args.cap)
    doctor = NovaEndpoint(None, budget)
    if os.environ.get('NOVA_LOCAL_SIM_URL'):
        sim = nova_local.Endpoint.from_env('NOVA_LOCAL_SIM')
    else:
        sim = NovaEndpoint(os.environ.get('SIM_MODEL', 'openai/gpt-6-luna'), budget, effort='low')
    case = nova_local.load_case(args.case)
    simulator = nova_local.Simulator(case, doctor=doctor, sim=sim, minutes=30)
    client = nova_local.LocalClient(simulator)
    started = time.time()
    err = None
    try:
        state = agent.prepare()
        agent.consult(client, state)
    except Exception as exc:  # noqa: BLE001
        err = f'{type(exc).__name__}: {exc}'
    nova_local.save_result(simulator, args.out, started)
    usage = {'calls': budget.n, 'turns': simulator.turns, 'doctor_calls': simulator.doctor_calls,
             'doctor_in': simulator.doctor_input, 'doctor_out': simulator.doctor_output, 'status': simulator.status,
             'error': err, 'finished': datetime.now().isoformat(timespec='seconds')}
    Path(args.out, 'usage.json').write_text(json.dumps(usage, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(usage, ensure_ascii=False))


if __name__ == '__main__':
    main()

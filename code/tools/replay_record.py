"""저장된 run의 ledger로 진단 투표·기록 단계만 다시 실행(세션 밖 Doctor 호출, 크레딧 매우 적음).
프롬프트 수정 효과를 서버 세션 없이 확인하는 용도.

  python tools/replay_record.py --run runs/C03-... [--steps dx,plan,S,A] [--repeat 1]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(1, str(Path(__file__).resolve().parent.parent))
import common  # noqa: E402


class FakeEnc:
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True)
    ap.add_argument('--steps', default='dx')
    ap.add_argument('--repeat', type=int, default=1)
    args = ap.parse_args()
    run_dir = Path(args.run)
    summary = json.loads((run_dir / 'summary.json').read_text(encoding='utf-8'))
    ledger = json.loads((run_dir / 'ledger.json').read_text(encoding='utf-8'))
    case = common.local_case_by_alias(summary['alias'])
    import run as agent_run  # noqa: E402
    from agent import record as rec, subjective  # noqa: E402
    from agent.encounter import Encounter  # noqa: E402
    from agent.llm import Budget  # noqa: E402
    from nova_sdk import Client  # noqa: E402

    client = Client(api_base=os.environ.get('NOVA_API_BASE', common.API_BASE_DEFAULT), token=common.dev_key(), sample=True)
    for i in range(args.repeat):
        enc = Encounter.__new__(Encounter)
        enc.client, enc.cfg = client, agent_run.load_config()
        enc.opening = case['start_information']['opening']
        enc.vitals = case['start_information']['vital_signs']
        enc.budget = Budget(None)
        enc.ledger = ledger
        enc.profile = summary.get('profile') or {}
        enc.differentials = []
        enc.dx, enc.dx_detail, enc.plan, enc.explained = summary.get('diagnosis', ''), {}, {}, summary.get('explained') or []
        steps = args.steps.split(',')
        if 'dx' in steps:
            enc.dx, enc.dx_detail = rec.vote_diagnosis(enc)
            print(f'[{i}] dx:', enc.dx, '| samples:', [(s['diagnosis_ko'], s['_effort']) for s in enc.dx_detail.get('samples', [])],
                  '| hit:', common.dx_hit(enc.dx, summary.get('accepted_diagnoses')))
        if 'plan' in steps:
            print(json.dumps(rec.write_plan(enc), ensure_ascii=False, indent=1))
        if 'S' in steps:
            s = subjective.write_subjective(enc)
            for k, v in s.items():
                print(f'--- {k}\n{v}')
        if 'A' in steps:
            print(json.dumps(rec.write_assessment(enc, {}, rec.write_objective(enc)), ensure_ascii=False, indent=1))
        print('budget', enc.budget.stats())


if __name__ == '__main__':
    main()

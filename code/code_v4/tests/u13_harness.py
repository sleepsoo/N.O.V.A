"""U13 하네스: 주어진 코드 폴더(code_v4 또는 code_js)의 v2 흐름(대조군 V3=0·bal44·GUIDE=1)을 가짜 서버로 돌려
plan_q·dx·plan_and_say 프롬프트(user 메시지)를 JSON으로 출력한다. 지침 hint는 고정 문자열로 바꿔 주입 위치를 비교한다.
사용: python u13_harness.py <code_dir> <tests_dir>   (API·키 없음)"""
import json
import os
import sys
from unittest import mock

code_dir, tests_dir = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
sys.path.insert(0, code_dir)
os.environ.pop('NOVA_GUIDELINES_DIR', None)
env = {'NOVA_AGENT_V2': '1', 'NOVA_AGENT_V3': '0', 'NOVA_AGENT_V4': '0', 'NOVA_AGENT_TURN_PRESET': 'bal44',
       'NOVA_AGENT_GUIDE': '1', 'NOVA_AGENT_TURN_CAP': '50'}
os.environ.update(env)

import run  # noqa: E402  (code_dir의 run)
from agent import guidelines  # noqa: E402

sys.path.insert(1, tests_dir)
import test_v2  # noqa: E402  (V2Client; run·agent는 위에서 이미 code_dir 것으로 로드됨)

assert os.path.dirname(os.path.abspath(run.__file__)) == code_dir, run.__file__

guidelines.hint_interview = lambda enc, *a, **k: '[진료지침 발췌 HINT-IV]\n'
guidelines.hint_dx = lambda enc, *a, **k: '[진료지침 발췌 HINT-DX]\n'
guidelines.hint_plan = lambda enc, *a, **k: '[진료지침 발췌 HINT-PLAN]\n'

prompts = []


class Rec(test_v2.V2Client):
    def chat(self, messages, **kw):
        prompts.append(messages[-1]['content'])
        return super().chat(messages, **kw)


client = Rec(test_v2.V2_C10)
with mock.patch.dict(os.environ, env):
    state = run.prepare()
run.consult(client, state)
out = {'plan_q': [p for p in prompts if '"covered"' in p],
       'dx': [p for p in prompts if 'diagnosis_ko' in p],
       'plan_say': [p for p in prompts if '[FAQ]' in p]}
print('U13JSON' + json.dumps(out, ensure_ascii=False))

"""tools/local_sim.py 무키 모드 테스트(네트워크 없음).

(a) 기본 인자가 --doctor local / 로컬 채점이고, local Doctor 생성·호출 시 NOVA_DEV_KEY를 읽지 않는다.
(b) vLLM 응답(reasoning_content 포함) → (content, finish, 토큰) → Simulator.chat의 ChatResult 형태 변환.
"""
import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(CODE, 'tools'))
sys.path.insert(0, CODE)

import common  # noqa: E402
import local_sim  # noqa: E402

sys.path.insert(1, str(common.DEVKIT))
import nova_local  # noqa: E402
from nova_sdk import Client, NovaError  # noqa: E402

FAKE_KEY = 'nova_FAKE_KEY_FOR_TEST'


class TrackingEnviron(dict):
    """os.environ 대역: NOVA_DEV_KEY 접근을 기록한다."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.touched = []

    def _note(self, key):
        if key == 'NOVA_DEV_KEY':
            self.touched.append(key)

    def __getitem__(self, key):
        self._note(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        self._note(key)
        return super().get(key, default)

    def __contains__(self, key):
        self._note(key)
        return super().__contains__(key)


def vllm_reply(content, reasoning='생각 중...', finish='stop', pin=120, pout=45):
    return {'id': 'x', 'object': 'chat.completion', 'model': 'openai/gpt-oss-20b',
            'choices': [{'index': 0, 'finish_reason': finish,
                         'message': {'role': 'assistant', 'content': content, 'reasoning_content': reasoning}}],
            'usage': {'prompt_tokens': pin, 'completion_tokens': pout, 'total_tokens': pin + pout}}


def default_args(argv=()):
    """local_sim.main의 파서를 그대로 써서 기본 인자를 얻는다."""
    captured = {}

    def fake_run_one(args):
        captured['args'] = args

    with mock.patch.object(sys, 'argv', ['local_sim.py', '--case', 'synthetic_cases/S01', *argv]), \
            mock.patch.object(local_sim, 'run_one', fake_run_one), \
            mock.patch.object(common, 'dev_key', side_effect=AssertionError('dev_key 호출됨')):
        local_sim.main()
    return captured['args']


class TestDefaults(unittest.TestCase):
    def test_defaults_are_local(self):
        args = default_args()
        self.assertEqual(args.doctor, 'local')
        self.assertEqual(args.doctor_url, 'http://localhost:8010/v1')
        self.assertEqual(args.doctor_model, 'openai/gpt-oss-20b')
        self.assertFalse(args.grade_remote)
        self.assertEqual(args.grade_url, 'http://localhost:8010/v1')
        self.assertEqual(local_sim.resolve_grade_model(args), 'openai/gpt-oss-20b')

    def test_main_with_grade_does_not_touch_key(self):
        env = TrackingEnviron(os.environ, NOVA_DEV_KEY=FAKE_KEY)
        with mock.patch.object(os, 'environ', env):
            args = default_args(['--grade'])
        self.assertTrue(args.grade)
        self.assertEqual(env.touched, [])

    def test_remote_flags_require_key(self):
        with self.assertRaises(AssertionError):
            default_args(['--doctor', 'luna'])
        with self.assertRaises(AssertionError):
            default_args(['--grade', '--grade-remote'])
        args = SimpleNamespace(grade_model=None, grade_remote=True)
        self.assertEqual(local_sim.resolve_grade_model(args), local_sim.LUNA)


class TestLocalDoctorNoKey(unittest.TestCase):
    def make(self, **over):
        kw = dict(doctor='local', doctor_url='http://localhost:8010/v1', doctor_model='openai/gpt-oss-20b',
                  max_doctor_calls=30, sim_effort='low', exam_effort='medium')
        kw.update(over)
        args = SimpleNamespace(**kw)
        counter = {'calls': 0, 'local': 0}
        _, Luna, _ = local_sim.build_simulator_classes(nova_local, Client, NovaError, args, counter)
        return args, counter, Luna

    def test_local_doctor_never_reads_key(self):
        env = TrackingEnviron(os.environ, NOVA_DEV_KEY=FAKE_KEY)
        sent = []

        def fake_urlopen(request, timeout=None):
            sent.append(request)
            resp = mock.MagicMock()
            resp.__enter__.return_value.read.return_value = json.dumps(vllm_reply('안녕하세요?')).encode()
            return resp

        with mock.patch.object(os, 'environ', env), \
                mock.patch.object(common, 'dev_key', side_effect=AssertionError('dev_key 호출됨')), \
                mock.patch.object(local_sim.urllib.request, 'urlopen', fake_urlopen):
            args, counter, Luna = self.make()
            doctor = local_sim.make_doctor(nova_local, Client, NovaError, args, counter, LunaDoctor=Luna)
            out = doctor.complete([{'role': 'user', 'content': 'hi'}], max_tokens=4000, reasoning_effort='low')
        self.assertEqual(env.touched, [])
        self.assertEqual(doctor.api_key, '')
        self.assertNotIsInstance(doctor, Luna)
        self.assertEqual(out, ('안녕하세요?', 'stop', 120, 45))
        self.assertEqual(counter, {'calls': 0, 'local': 1})
        req = sent[0]
        self.assertEqual(req.full_url, 'http://localhost:8010/v1/chat/completions')
        self.assertIsNone(req.get_header('Authorization'))
        body = json.loads(req.data)
        self.assertEqual(body['model'], 'openai/gpt-oss-20b')
        self.assertEqual(body['max_tokens'], 4000)
        self.assertEqual(body['reasoning_effort'], 'low')
        self.assertNotIn(FAKE_KEY, req.data.decode())

    def test_token_and_call_limits(self):
        args, counter, Luna = self.make(max_doctor_calls=1)
        doctor = local_sim.make_doctor(nova_local, Client, NovaError, args, counter, LunaDoctor=Luna)
        with self.assertRaises(NovaError) as cm:
            doctor.complete([{'role': 'user', 'content': 'hi'}], max_tokens=8001)
        self.assertEqual(cm.exception.code, 'TOKEN_LIMIT_EXCEEDED')
        with mock.patch.object(doctor, '_post', return_value=vllm_reply('네')):
            doctor.complete([{'role': 'user', 'content': 'hi'}], max_tokens=100)
        with self.assertRaises(NovaError) as cm:
            doctor.complete([{'role': 'user', 'content': 'hi'}], max_tokens=100)
        self.assertEqual(cm.exception.code, 'MODEL_CALL_LIMIT')


class TestConversion(unittest.TestCase):
    def test_content_only_reasoning_dropped(self):
        out = local_sim.completion_tuple(vllm_reply('답입니다', reasoning='긴 추론', finish='stop'))
        self.assertEqual(out, ('답입니다', 'stop', 120, 45))

    def test_none_content_becomes_empty(self):
        out = local_sim.completion_tuple(vllm_reply(None, reasoning='추론만 하다 끝남', finish='length', pin=10, pout=99))
        self.assertEqual(out, ('', 'length', 10, 99))
        self.assertEqual(local_sim.completion_tuple({}), ('', 'stop', 0, 0))

    def test_simulator_chat_result_shape(self):
        """local Doctor → Simulator.chat → SDK ChatResult 형태(choices[0].message.content, usage)."""
        args = SimpleNamespace(doctor='local', doctor_url='http://localhost:8010/v1', doctor_model='openai/gpt-oss-20b',
                               max_doctor_calls=30, sim_effort='low', exam_effort='medium')
        counter = {'calls': 0, 'local': 0}
        _, Luna, Strict = local_sim.build_simulator_classes(nova_local, Client, NovaError, args, counter)
        doctor = local_sim.make_doctor(nova_local, Client, NovaError, args, counter, LunaDoctor=Luna)
        case = json.loads((common.CODE / 'synthetic_cases' / 'S01' / 'case.json').read_text(encoding='utf-8'))
        sim = nova_local.Endpoint('http://localhost:8010/v1', 'openai/gpt-oss-20b')
        simulator = Strict(case, doctor=doctor, sim=sim, minutes=30, log=None)
        client = nova_local.LocalClient(simulator)
        with mock.patch.object(doctor, '_post', return_value=vllm_reply('{"q": "어디가 아프세요?"}')):
            reply = client.chat([{'role': 'user', 'content': '질문 하나'}], max_tokens=2000, reasoning_effort='medium')
        self.assertEqual(reply['choices'][0]['message']['content'], '{"q": "어디가 아프세요?"}')
        self.assertEqual(reply['choices'][0]['finish_reason'], 'stop')
        self.assertEqual(reply['usage'], {'prompt_tokens': 120, 'completion_tokens': 45, 'total_tokens': 165})
        self.assertEqual(simulator.doctor_calls, 1)
        # 빈 content(추론만)는 서버처럼 PROVIDER_RESPONSE_INVALID
        with mock.patch.object(doctor, '_post', return_value=vllm_reply(None)):
            with self.assertRaises(NovaError) as cm:
                client.chat([{'role': 'user', 'content': '질문 하나'}], max_tokens=2000)
        self.assertEqual(cm.exception.code, 'PROVIDER_RESPONSE_INVALID')


class TestGradeParse(unittest.TestCase):
    def test_parse_grade_json(self):
        good = '설명...\n{"scores": {"정보수집": 10}, "total": 55}\n끝'
        self.assertEqual(local_sim.parse_grade_json(good)['total'], 55)
        self.assertIsNone(local_sim.parse_grade_json('JSON 없음 {깨짐'))
        self.assertIsNone(local_sim.parse_grade_json(''))
        two = '{"a": 1} 그리고 {"total": 70, "scores": {}}'
        self.assertEqual(local_sim.parse_grade_json(two)['total'], 70)


if __name__ == '__main__':
    unittest.main()

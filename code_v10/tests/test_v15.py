"""v15: 38턴(문진 17·진찰 11·설명 7줄+답 2) + 친절도 공감 접두(KIND). v15s = 34턴(t34) 같은 스위치."""
import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import run  # noqa: E402
from agent import interview  # noqa: E402
import test_v8 as T  # noqa: E402
from test_v12 import run_var  # noqa: E402

BASE = {'EXAM_POS': '1', 'BANK_V10': '1', 'PAIR_MERGE': '1', 'ICE_PAIR': '1', 'SAY_V11': '1', 'V13': '1', 'V14': '1'}
V15 = dict(BASE, KIND='1', TURN_PRESET='t38')
V15S = dict(BASE, KIND='1', TURN_PRESET='t34')


def enc_with(replies):
    led = [{'kind': 'SAY', 'phase': 'interview', 'turn': i + 1, 'reply': r} for i, r in enumerate(replies)]
    return SimpleNamespace(ledger=led)


class TestKindPrefix(unittest.TestCase):
    def test_positive_gets_prefix(self):
        self.assertTrue(interview.kind_prefix(enc_with(['잔 들 때 손이 떨려요.']), '눈이 튀어나왔나요?').endswith('눈이 튀어나왔나요?'))
        self.assertNotEqual(interview.kind_prefix(enc_with(['배가 많이 아파요.']), '열이 나나요?'), '열이 나나요?')

    def test_negative_or_negated_clause_no_prefix(self):
        self.assertEqual(interview.kind_prefix(enc_with(['아니요, 없어요.']), '열이 나나요?'), '열이 나나요?')
        self.assertEqual(interview.kind_prefix(enc_with(['가슴 통증은 없어요.']), '열이 나나요?'), '열이 나나요?')

    def test_length_and_no_consecutive(self):
        e = enc_with(['배가 많이 아파요.'])
        long_q = '가' * 25 + '있나요?'
        self.assertEqual(interview.kind_prefix(e, long_q), long_q)
        e = enc_with(['배가 많이 아파요.'])
        self.assertNotEqual(interview.kind_prefix(e, '열이 나나요?'), '열이 나나요?')
        e.ledger.append({'kind': 'SAY', 'phase': 'interview', 'turn': 2, 'reply': '토도 했어요.'})
        self.assertEqual(interview.kind_prefix(e, '설사도 하나요?'), '설사도 하나요?')   # 바로 다음 턴은 쉰다

    def test_max_per_case(self):
        e = enc_with([])
        n = 0
        for t in range(1, 40, 2):
            e.ledger.append({'kind': 'SAY', 'phase': 'interview', 'turn': t, 'reply': '많이 아프고 힘들어요, 걱정돼요, 떨려요.'})
            if interview.kind_prefix(e, '열이 나나요?') != '열이 나나요?':
                n += 1
        self.assertLessEqual(n, interview.KIND_MAX)


class TestRuns(unittest.TestCase):
    def test_preset(self):
        with mock.patch.dict(os.environ, {'NOVA_AGENT_TURN_PRESET': 't38'}):
            c = run.load_config()
        self.assertEqual(1 + c['INTERVIEW_Q'] + c['EXAM_N'] + c['EXPLAIN_MIN'] + c['ANSWER_RESERVE'], c['TURN_CAP'])
        self.assertEqual((c['INTERVIEW_Q'], c['EXAM_N'], c['TURN_CAP']), (17, 11, 38))

    def test_v15_limits(self):
        for case in ('C01', 'C03', 'C10'):
            c = run_var(case, V15)
            self.assertLessEqual(c.turns, 38, case)
            self.assertEqual(sum(e[0] == 'EXAM' for e in c.events), 11, case)
            self.assertTrue(all(T.nlen(e[1]) <= 30 for e in c.events), case)
            self.assertIsNotNone(c.diagnosed, case)
            qi = max(i for i, e in enumerate(c.events) if '궁금하신 점' in e[1])
            self.assertEqual(qi, len(c.events) - 2, case)

    def test_v15s_limits(self):
        for case in ('C01', 'C03', 'C10'):
            c = run_var(case, V15S)
            self.assertLessEqual(c.turns, 34, case)
            self.assertEqual(sum(e[0] == 'EXAM' for e in c.events), 7, case)

    def test_kind_off_unchanged(self):
        a = [e[1] for e in run_var('C10', dict(V15, KIND='0')).events]
        b = [e[1] for e in run_var('C10', V15).events]
        self.assertEqual(len(a), len(b))
        self.assertTrue(any(x != y and y.endswith(x) for x, y in zip(a, b)))

    def test_robust(self):
        for kw in ({'llm': 'error'}, {'q_line': 'none', 'explain_q': 'none'}, {'explain_q': 'all'}):
            c = run_var('C01', V15, **kw)
            self.assertLessEqual(c.turns, 38)
            self.assertIsNotNone(c.diagnosed)


if __name__ == '__main__':
    unittest.main()

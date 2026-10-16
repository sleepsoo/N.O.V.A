"""v13: 턴 가치 재배분(t34x = 개방 1 + 문진 15 + 진찰 11 + 설명 5 + 질문 1 + 답 1) + v12b(짝 합치기·걱정·기대 짝·v11a 설명)."""
import os
import re
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import run  # noqa: E402
from agent import explain  # noqa: E402
import test_v8 as T  # noqa: E402
from test_v12 import run_var  # noqa: E402

V12B = {'EXAM_POS': '1', 'BANK_V10': '1', 'PAIR_MERGE': '1', 'ICE_PAIR': '1', 'SAY_V11': '1'}
V13 = dict(V12B, V13='1', TURN_PRESET='t34x')


class TestConfig(unittest.TestCase):
    def test_preset(self):
        with mock.patch.dict(os.environ, {'NOVA_AGENT_TURN_PRESET': 't34x'}):
            c = run.load_config()
        self.assertEqual((c['INTERVIEW_Q'], c['EXAM_N'], c['EXPLAIN_MIN'], c['ANSWER_RESERVE'], c['EXPLAIN_MAX_LINES']),
                         (15, 11, 6, 1, 5))
        self.assertEqual(1 + c['INTERVIEW_Q'] + c['EXAM_N'] + c['EXPLAIN_MIN'] + c['ANSWER_RESERVE'], c['TURN_CAP'])

    def test_slots(self):
        try:
            explain.apply_v13(True)
            self.assertEqual([k for k, _ in explain.say_slots(5, worry=True)], ['dx', 'worry', 'tests', 'treat', 'warn'])
            self.assertEqual([k for k, _ in explain.say_slots(5, worry=False)], ['dx', 'mech', 'tests', 'treat', 'warn'])
            self.assertIn('좋아', dict(explain.say_slots(5))['treat'])
            explain.apply_v13(False)
            self.assertEqual([k for k, _ in explain.say_slots(5)], ['dx', 'mech', 'worry', 'tests', 'warn'])
        finally:
            explain.apply_v13(False)


class TestDryRun(unittest.TestCase):
    def test_turns_exams_limits(self):
        for case in ('C01', 'C03', 'C10'):
            c = run_var(case, V13)
            self.assertLessEqual(c.turns, 34, case)
            self.assertEqual(sum(e[0] == 'EXAM' for e in c.events), 11, case)
            self.assertTrue(all(T.nlen(e[1]) <= 30 for e in c.events), case)
            self.assertIsNotNone(c.diagnosed, case)
            # 마지막 '궁금하신 점' 질문에는 답하고 끝낸다
            qi = max(i for i, e in enumerate(c.events) if '궁금하신 점' in e[1])
            self.assertEqual(qi, len(c.events) - 2, case)

    def test_mid_question_answered(self):
        for case in ('C01', 'C03', 'C10'):
            ev = run_var(case, V13).events
            i = next(i for i, e in enumerate(ev) if e[2] == '치료하면 좋아질 수 있나요?')
            self.assertRegex(ev[i + 1][1], r'좋아|자라|잘 수|대부분', case)

    def test_admission_question_adult_only(self):
        for case in ('C01', 'C10'):
            self.assertFalse(any('입원이나 수술' in e[1] for e in run_var(case, V13).events), case)
        self.assertTrue(any('입원이나 수술' in e[1] for e in run_var('C03', V13).events))

    def test_exam_window_prefers_specific(self):
        ex = [e[1] for e in run_var('C10', V13).events if e[0] == 'EXAM']
        self.assertTrue(any('요골동맥' in x for x in ex))
        self.assertTrue(any('사지 근력' in x for x in ex))

    def test_off_equals_v12b(self):
        a = [e[1] for e in run_var('C10', V12B).events]
        b = [e[1] for e in run_var('C10', dict(V12B, V13='0')).events]
        self.assertEqual(a, b)
        self.assertFalse(explain.SLOT5_V13)

    def test_robust_modes(self):
        for case in ('C01', 'C10'):
            for kw in ({'llm': 'error'}, {'q_line': 'none', 'explain_q': 'none'}, {'explain_q': 'all'}):
                c = run_var(case, V13, **kw)
                self.assertLessEqual(c.turns, 34, (case, kw))
                self.assertIsNotNone(c.diagnosed, (case, kw))
                self.assertTrue(all(T.nlen(e[1]) <= 30 for e in c.events), (case, kw))


if __name__ == '__main__':
    unittest.main()

"""v17 = v10b + 짝 합치기 + 공감 접두 + 이해 확인형 마지막 질문(턴 0 변경만, 34턴·진찰 7·설명 7줄+답 2 그대로)."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from agent import say  # noqa: E402
import test_v8 as T  # noqa: E402
from test_v12 import run_var  # noqa: E402

V10B = {'EXAM_POS': '1', 'BANK_V10': '1'}
V17 = dict(V10B, PAIR_MERGE='1', KIND='1', QLINE_V11='1')


class TestV17(unittest.TestCase):
    def test_shape_same_as_v10b(self):
        for case in ('C01', 'C03', 'C10'):
            a, b = run_var(case, V10B), run_var(case, V17)
            self.assertEqual(b.turns, a.turns, case)
            self.assertEqual([e[0] for e in b.events], [e[0] for e in a.events], case)
            self.assertEqual([e[1] for e in b.events if e[0] == 'EXAM'], [e[1] for e in a.events if e[0] == 'EXAM'], case)
            self.assertTrue(all(T.nlen(e[1]) <= 30 for e in b.events), case)

    def test_question_line_and_reset(self):
        s = [e[1] for e in run_var('C10', V17).events]
        self.assertIn(say.QUESTION_LINE_V11, s)
        s0 = [e[1] for e in run_var('C10', V10B).events]
        self.assertIn(say.QUESTION_LINE_BASE, s0)
        self.assertNotIn(say.QUESTION_LINE_V11, s0)

    def test_kind_applied(self):
        a = [e[1] for e in run_var('C01', V10B).events if e[0] == 'SAY']
        b = [e[1] for e in run_var('C01', V17).events if e[0] == 'SAY']
        self.assertTrue(any(x.startswith(('힘드셨겠어요', '불편하셨겠어요', '아프셨겠어요', '많이', '걱정되셨겠어요', '그러셨군요'))
                            for x in b[1:18]))
        self.assertEqual(a[-1:], b[-1:])


if __name__ == '__main__':
    unittest.main()

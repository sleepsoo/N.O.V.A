"""v16 = v10b 대화 골격(34턴·문진 17·진찰 7·설명 7줄+답 2) + 짝 합치기·긴급도 + 이름 확인 인사 + MAI-DxO 반박자."""
import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import run  # noqa: E402
from agent import assess, interview  # noqa: E402
import test_v8 as T  # noqa: E402
from test_v12 import run_var  # noqa: E402

V16 = {'EXAM_POS': '1', 'BANK_V10': '1', 'PAIR_MERGE': '1', 'V13': '1', 'V14': '1', 'NAME_GREET': '1', 'DX_CHALLENGE': '1',
       'TURN_PRESET': 't34'}


class TestName(unittest.TestCase):
    def test_names(self):
        self.assertEqual(interview.patient_name('이름은 최윤정이고, 나는 서른두 살 여자이다.'), '최윤정')
        self.assertEqual(interview.patient_name('저는 박선희이고, 예순두 살 여자이다.'), '박선희')
        self.assertEqual(interview.patient_name('저는 쉰다섯 살 남자이다.'), '')
        self.assertEqual(interview.patient_name('저는 마흔 살 남자이다.'), '')

    def test_first_turn(self):
        q = interview._first_open({'pediatric': False, 'empathy_short': '걱정되셨죠.'}, 'x', {'NAME_GREET': 1},
                                  '이름은 최윤정이고, 서른두 살 여자이다.')
        self.assertTrue(q.startswith('최윤정님'))
        self.assertLessEqual(T.nlen(q), 30)
        q = interview._first_open({'pediatric': False, 'empathy_short': '걱정되셨죠.'}, 'x', {'NAME_GREET': 1}, '저는 마흔 살 남자이다.')
        self.assertTrue(q.startswith('안녕하세요'))


class TestChallenge(unittest.TestCase):
    def _enc(self, reply):
        client = mock.Mock()
        client.chat.return_value = {'choices': [{'message': {'content': json.dumps(reply, ensure_ascii=False)},
                                                 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 5, 'completion_tokens': 5}}
        budget = SimpleNamespace(can_call=lambda *a, **k: True)
        return SimpleNamespace(client=client, budget=budget, cfg={'CALL_RESERVE': 0, 'EFFORT_DX': 'low'},
                               facts=[{'id': 'F1'}, {'id': 'F2'}], ledger=[])

    def test_switch_only_in_pool_with_unexplained(self):
        diffs = [{'dx': '아급성 갑상샘염'}, {'dx': '불안장애'}]
        good = {'verdict': 'switch', 'final_ko': '아급성 갑상샘염', 'unexplained': [{'fact': 'F2', 'why': '압통'}]}
        with mock.patch.object(assess, 'ask_json', return_value=good):
            self.assertEqual(assess.challenge_dx(self._enc(good), '사실 [주진단]', '그레이브스병', '', diffs, [])[0], '아급성 갑상샘염')
        bad_pool = dict(good, final_ko='뇌종양')
        with mock.patch.object(assess, 'ask_json', return_value=bad_pool):
            self.assertIsNone(assess.challenge_dx(self._enc(bad_pool), '사실', '그레이브스병', '', diffs, []))
        no_fact = dict(good, unexplained=[{'fact': 'F9', 'why': 'x'}])
        with mock.patch.object(assess, 'ask_json', return_value=no_fact):
            self.assertIsNone(assess.challenge_dx(self._enc(no_fact), '사실', '그레이브스병', '', diffs, []))
        keep = {'verdict': 'keep'}
        with mock.patch.object(assess, 'ask_json', return_value=keep):
            self.assertIsNone(assess.challenge_dx(self._enc(keep), '사실', '그레이브스병', '', diffs, []))

    def test_same_dx(self):
        self.assertTrue(assess._same_dx('그레이브스병에 의한 갑상샘항진증 (Graves)', '그레이브스병에 의한 갑상샘항진증'))
        self.assertFalse(assess._same_dx('갑상샘염', '불안장애'))


class TestRuns(unittest.TestCase):
    def test_limits_and_dialogue_shape(self):
        for case in ('C01', 'C03', 'C10'):
            c = run_var(case, V16)
            self.assertLessEqual(c.turns, 34, case)
            self.assertEqual(sum(e[0] == 'EXAM' for e in c.events), 7, case)
            self.assertTrue(all(T.nlen(e[1]) <= 30 for e in c.events), case)
            self.assertIsNotNone(c.diagnosed, case)
        self.assertTrue(run_var('C10', V16).events[0][1].startswith('최윤정님'))
        self.assertTrue(any('김도현 보호자님' in e[1] for e in run_var('C03', V16).events[:1]))

    def test_robust(self):
        for kw in ({'llm': 'error'}, {'q_line': 'none', 'explain_q': 'none'}, {'explain_q': 'all'}):
            c = run_var('C10', V16, **kw)
            self.assertLessEqual(c.turns, 34)
            self.assertIsNotNone(c.diagnosed)


if __name__ == '__main__':
    unittest.main()

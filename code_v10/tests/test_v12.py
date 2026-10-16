"""v12: 단일 질문 짝 합치기(PAIR_MERGE)·걱정·기대 짝(ICE_PAIR). 34턴·같은 계통 2항목 규칙 유지."""
import json
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import run  # noqa: E402
from agent import cpx, pairmerge as pm  # noqa: E402
import test_v8 as T  # noqa: E402

V10B = {'EXAM_POS': '1', 'BANK_V10': '1'}
V12A = dict(V10B, PAIR_MERGE='1', ICE_PAIR='1')
MOCK_PAIRS = {
    'C01': [{'a': 1, 'b': 0, 'q': '하루 몇 알, 마지막은 언제 드셨어요?'},
            {'a': 5, 'b': 7, 'q': '약 드신 뒤 기억이 끊기거나 운전한 적 있나요?'},
            {'a': 2, 'b': 3, 'q': '끊어 보신 적 있고 그때 증상은요?'}],     # 술어 둘 → 거절
    'C03': [{'a': 0, 'b': 1, 'q': '부모님 키와 사춘기가 늦었던 분 있나요?'},
            {'a': 6, 'b': 4, 'q': '잠이나 어린이집 생활은 괜찮나요?'}],
    'C10': [{'a': 0, 'b': 1, 'q': '무슨 일 하시고 커피는 몇 잔 드세요?'}],     # 술어 둘 → 거절
}


def run_var(case, cfg, pairs=None, **kw):
    env = {'NOVA_AGENT_' + k: v for k, v in cfg.items()}
    env['NOVA_AGENT_GUIDE'] = '0'
    op = {'C10': T.C10, 'C01': T.C01, 'C03': T.C03}[case]
    orig = T.FakeClient.answer

    def answer(self, user):
        if '"pairs"' in user:
            return json.dumps({'pairs': (pairs if pairs is not None else MOCK_PAIRS).get(case, [])}, ensure_ascii=False)
        return orig(self, user)
    with mock.patch.dict(os.environ, env), mock.patch.object(T.FakeClient, 'answer', answer):
        client = T.FakeClient(case, op, **kw)
        state = run.prepare()
        run.consult(client, state)
    return client


def u1(uid, sys_, q='질문이에요?', stage='core', prio=1, safety=False):
    return cpx.U(uid, stage, prio, q, [(uid, uid, '.')], sys_, safety=safety)


class TestCheckPair(unittest.TestCase):
    def setUp(self):
        self.a, self.b = u1('a', 'neuro'), u1('b', 'neuro')

    def test_ok(self):
        self.assertEqual(pm.check_pair(self.a, self.b, '열이나 오한이 있나요?'), '')
        self.assertEqual(pm.check_pair(self.a, self.b, '어디가 어떻게 아프세요?'), '')

    def test_rejects(self):
        self.assertEqual(pm.check_pair(self.a, u1('c', 'gi'), '열이나 오한이 있나요?'), 'cross_group')
        self.assertEqual(pm.check_pair(self.a, self.b, '무슨 일 하시고 커피는 몇 잔 드세요?'), 'two_predicates')
        self.assertEqual(pm.check_pair(self.a, self.b, '끊어 보신 적 있고 그때 증상은요?'), 'two_predicates')
        self.assertNotEqual(pm.check_pair(self.a, self.b, '열이나 오한, 기침이 있나요?'), '')
        self.assertNotEqual(pm.check_pair(self.a, self.b, '아주 오래전부터 지금까지 머리가 계속 아프거나 어지러우세요?'), '')
        self.assertNotEqual(pm.check_pair(self.a, self.b, '열이 있나요? 오한은요?'), '')

    def test_affinity_group(self):
        self.assertEqual(pm.sys_group(u1('s', 'sleep')), pm.sys_group(u1('p', 'psy')))


class TestCandidatesAndMerge(unittest.TestCase):
    def test_candidates_need_partner_and_skip_covered(self):
        units = [u1('a', 'neuro'), u1('b', 'neuro'), u1('c', 'gi'), u1('ice', 'ice', stage='ice'),
                 u1('hpi_onset', 'hpi'), u1('d', 'neuro')]
        ids = [u['id'] for u in pm.candidates(units, covered={'d'})]
        self.assertEqual(ids, ['a', 'b'])

    def test_merged_unit(self):
        a, b = u1('a', 'neuro', prio=2), u1('b', 'neuro', prio=1, safety=True)
        m = pm.merged_unit(a, b, '열이나 오한이 있나요?')
        self.assertEqual(m['kind'], 'pair')
        self.assertEqual(m['prio'], 1)
        self.assertTrue(m['safety'])
        self.assertEqual([i[0] for i in m['items']], ['a', 'b'])
        self.assertEqual(cpx.bundle_violation(m), '')

    def test_ice_pair(self):
        units = pm.ice_pair([cpx._clone(cpx.ICE_OPEN, must=True)], peds=False)
        self.assertEqual(units[0]['id'], 'ice')
        self.assertEqual([i[0] for i in units[0]['items']], ['ice_concern', 'ice_expect'])
        self.assertLessEqual(T.nlen(units[0]['q']), 30)
        p = pm.ice_pair([cpx._clone(cpx.P_ICE, must=True)], peds=True)
        self.assertLessEqual(T.nlen(p[0]['q']), 30)


class TestDryRun(unittest.TestCase):
    def test_limits_all_cases(self):
        for case in ('C01', 'C03', 'C10'):
            c = run_var(case, V12A)
            self.assertLessEqual(c.turns, 34, case)
            self.assertTrue(all(T.nlen(e[1]) <= 30 for e in c.events), case)
            self.assertIsNotNone(c.diagnosed, case)

    def test_merged_questions_asked(self):
        s = [e[1] for e in run_var('C01', V12A).events if e[0] == 'SAY']
        self.assertIn('하루 몇 알, 마지막은 언제 드셨어요?', s)
        self.assertNotIn('끊어 보신 적 있고 그때 증상은요?', s)
        self.assertNotIn('요즘 하루에 몇 알 드세요?', s)
        self.assertTrue(any('바라는 점' in x for x in s))

    def test_rejected_pair_keeps_originals(self):
        s = [e[1] for e in run_var('C10', V12A).events if e[0] == 'SAY']
        self.assertNotIn('무슨 일 하시고 커피는 몇 잔 드세요?', s)

    def test_llm_failure_falls_back(self):
        a = [e[1] for e in run_var('C03', V10B).events]
        b = [e[1] for e in run_var('C03', dict(V10B, PAIR_MERGE='1'), pairs={}).events]
        self.assertEqual(a, b)

    def test_off_equals_v10b(self):
        for case in ('C01', 'C10'):
            a = [e[1] for e in run_var(case, V10B).events]
            b = [e[1] for e in run_var(case, dict(V10B, PAIR_MERGE='0', ICE_PAIR='0')).events]
            self.assertEqual(a, b, case)

    def test_turns_unchanged_and_exam_count(self):
        for case in ('C01', 'C03', 'C10'):
            c = run_var(case, V12A)
            self.assertEqual(sum(e[0] == 'EXAM' for e in c.events), 7, case)


if __name__ == '__main__':
    unittest.main()

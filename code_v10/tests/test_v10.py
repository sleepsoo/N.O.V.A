"""v10: 기록 안전장치(REC_BACKSTOP)·양성 진찰 당김(EXAM_POS)·은행 짝 보강(BANK_V10)·과거력 필수(HX_MUST)."""
import os
import re
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import run  # noqa: E402
from agent import cpx, note2  # noqa: E402
import test_v8 as T  # noqa: E402

VARS = {
    'v9': {'REC_BACKSTOP': '0'},
    'a': {},
    'b': {'EXAM_POS': '1', 'BANK_V10': '1'},
    'c': {'EXAM_POS': '1', 'BANK_V10': '1', 'INTERVIEW_Q': '16', 'EXAM_N': '8'},
}
C10_EXTRA = [(r'손이 떨리거나', '잔 들 때 손이 떨리고 계단 오르면 다리 힘이 빠져요.'),
             (r'가족 중 갑상선병이나 당뇨', '어머니가 갑상샘저하증, 할머니가 당뇨셨어요.'),
             (r'가슴 통증이나 숨찬', '가슴 통증은 없고 계단 오르면 숨차요.')]


def run_var(case, var, **kw):
    env = {'NOVA_AGENT_' + k: v for k, v in VARS[var].items()}
    env['NOVA_AGENT_GUIDE'] = '0'
    op = {'C10': T.C10, 'C01': T.C01, 'C03': T.C03}[case]
    pat = dict(T.PATIENT)
    if case == 'C10':
        pat['C10'] = C10_EXTRA + T.PATIENT['C10']
    with mock.patch.dict(os.environ, env), mock.patch.object(T, 'PATIENT', pat):
        client = T.FakeClient(case, op, **kw)
        state = run.prepare()
        run.consult(client, state)
    return client


def seq(c):
    return [(e[0], e[1]) for e in c.events]


class TestDefaults(unittest.TestCase):
    def test_default_flags(self):
        self.assertEqual(run.DEFAULTS['REC_BACKSTOP'], 1)
        for k in ('EXAM_POS', 'BANK_V10', 'HX_MUST'):
            self.assertIn(k, run.DEFAULTS)


class TestBankV10(unittest.TestCase):
    def test_units_pass_bundle_rule(self):
        for uid, (q, _) in list(cpx.V10_FH.items()) + list(cpx.V10_UNITS.items()):
            self.assertLessEqual(len(q), cpx.MAX_Q, q)
        for cat, spec in cpx.CPX.items():
            out = cpx.apply_v10(spec['units'], {}, {'BANK_V10': 1})
            for u in out:
                self.assertEqual(cpx.bundle_violation(u), '', (cat, u['q']))
                self.assertLessEqual(len(u['items']), 2 if u['id'] in cpx.V10_FH or u['id'] in cpx.V10_UNITS
                                     else len(u['items']), u['q'])

    def test_off_is_identity(self):
        units = cpx.CPX['weight_loss']['units']
        self.assertEqual([u['q'] for u in cpx.apply_v10(units, {}, {})], [u['q'] for u in units])

    def test_fh_keys(self):
        self.assertEqual(cpx.ITEM_KEYS['fh_dm'], 'fh.DM')
        self.assertEqual(cpx.ITEM_KEYS['fh_htn'], 'fh.HTN')

    def test_hx_must(self):
        units = [cpx._clone(cpx.HX_HTN_DM, prio=2)]
        out = cpx.apply_v10(units, {'pediatric': False}, {'HX_MUST': 1})
        self.assertTrue(out[0]['must'])
        self.assertEqual(out[0]['prio'], 1)
        out = cpx.apply_v10(units, {'pediatric': True}, {'HX_MUST': 1})
        self.assertFalse(out[0].get('must'))


class TestRuns(unittest.TestCase):
    def test_all_variants_limits(self):
        for var in VARS:
            for case in ('C10', 'C01', 'C03'):
                for kw in ({}, {'q_line': 'none', 'explain_q': 'none'}, {'explain_q': 'all'}, {'llm': 'error'}):
                    c = run_var(case, var, **kw)
                    self.assertLessEqual(c.turns, 34, (var, case, kw))
                    self.assertIsNotNone(c.diagnosed, (var, case, kw))
                    self.assertTrue(all(T.nlen(e[1]) <= 30 for e in c.events), (var, case, kw))

    def test_a_dialogue_identical_to_v9(self):
        """v10a는 대화(SAY/EXAM 순서)가 v9와 같고 기록만 다르다."""
        for case in ('C10', 'C01', 'C03'):
            self.assertEqual(seq(run_var(case, 'v9')), seq(run_var(case, 'a')), case)

    def test_b_c10_pairs_and_exams(self):
        c = run_var('C10', 'b')
        says = [e[1] for e in c.events if e[0] == 'SAY']
        self.assertIn('손이 떨리거나 다리 힘이 빠지나요?', says)
        self.assertIn('가족 중 갑상선병이나 당뇨 있나요?', says)
        exams = [e[1] for e in c.events if e[0] == 'EXAM']
        self.assertIn('피부 온도·발한 촉진하겠습니다', exams)   # 땀(+) → 피부 진찰 유지
        self.assertEqual(sum(e[0] == 'EXAM' for e in c.events), 7)

    def test_c_exam8(self):
        c = run_var('C10', 'c')
        exams = [e[1] for e in c.events if e[0] == 'EXAM']
        self.assertEqual(len(exams), 8)
        self.assertIn('사지 근력 검사하겠습니다', exams)        # 다리 힘 빠짐(+) → 근력 검사

    def test_cardio_exams_protected(self):
        """숨참 양성이 없어도 심폐 범주(체중감소)에서는 심음·폐 청진이 양성 진찰에 밀리지 않는다."""
        pat = dict(T.PATIENT)
        pat['C10'] = [(r'손이 떨리거나', '잔 들 때 손이 떨리고 계단 오르면 다리 힘이 빠져요.')] + T.PATIENT['C10']
        env = {'NOVA_AGENT_GUIDE': '0', 'NOVA_AGENT_EXAM_POS': '1', 'NOVA_AGENT_BANK_V10': '1'}
        with mock.patch.dict(os.environ, env), mock.patch.object(T, 'PATIENT', pat):
            client = T.FakeClient('C10', T.C10)
            run.consult(client, run.prepare())
        exams = [e[1] for e in client.events if e[0] == 'EXAM']
        self.assertIn('심음 청진하겠습니다', exams)
        self.assertIn('폐 청진하겠습니다', exams)

    def test_last_question_answered(self):
        for var in ('a', 'b', 'c'):
            for case in ('C10', 'C01', 'C03'):
                c = run_var(case, var)
                says = [e for e in c.events if e[0] == 'SAY']
                idx = max(i for i, e in enumerate(says) if '궁금하신 점' in e[1])
                self.assertEqual(idx, len(says) - 2, (var, case))   # 마지막 질문 뒤 답 1턴


class TestBackstop(unittest.TestCase):
    def test_c10_items_recorded(self):
        c = run_var('C10', 'b')
        note, _ = c.diagnosed
        s = ' '.join(note['S'].values())
        for lab in ('손떨림', '안구 돌출', '목 부음', '월경량', '불면(-)', '최근 감염(-)'):
            self.assertIn(lab, s, lab)
        self.assertIn('DM / HTN', note['S']['fh'])

    def test_no_unanswered_negative(self):
        """'가슴 통증은 없어요'만 답하면 호흡곤란은 어디에도 (-)로 기록하지 않는다."""
        pat = dict(T.PATIENT)
        pat['C10'] = [(r'가슴 통증이나 숨찬', '가슴 통증은 없어요.')] + T.PATIENT['C10']
        env = {'NOVA_AGENT_GUIDE': '0'}
        with mock.patch.dict(os.environ, env), mock.patch.object(T, 'PATIENT', pat):
            client = T.FakeClient('C10', T.C10)
            run.consult(client, run.prepare())
        s = ' '.join(client.diagnosed[0]['S'].values())
        self.assertNotIn('호흡곤란(-)', s)

    def test_off_no_extra(self):
        c9 = run_var('C10', 'v9')
        s9 = ' '.join(c9.diagnosed[0]['S'].values())
        self.assertNotIn('안구 돌출(+)', s9)

    def test_sections(self):
        c = run_var('C03', 'a')
        S = c.diagnosed[0]['S']
        self.assertIn('저신장 가족력(-)', S['fh'])
        self.assertIn('스테로이드(-)', S['pmh'])
        self.assertNotIn('저신장 가족력', S['ros'])

    def test_present_helpers(self):
        ns = note2._ns('손 떨림 (+), 목 혹(-)')
        self.assertTrue(note2._present('손떨림', ns))
        self.assertTrue(note2._present('식사량·식욕', note2._ns('식욕 증가')))
        self.assertFalse(note2._present('안구 돌출', ns))
        self.assertEqual(note2._detail('네, 잔 들 때 손이 떨려요.', r'떨'), '잔 들 때 손이 떨려요')


if __name__ == '__main__':
    unittest.main()


# ================================================================ v11 (v10b 위 세 방향)
V11 = {'v11a': {'EXAM_POS': '1', 'BANK_V10': '1', 'SAY_V11': '1'},
       'v11b': {'EXAM_POS': '1', 'BANK_V10': '1', 'OPEN_TOPIC': '1'},
       'v11c': {'EXAM_POS': '1', 'BANK_V10': '1', 'HPI_V11': '1'}}
VARS.update(V11)


class TestV11(unittest.TestCase):
    def test_limits(self):
        for var in V11:
            for case in ('C10', 'C01', 'C03'):
                for kw in ({}, {'q_line': 'none', 'explain_q': 'none'}, {'explain_q': 'all'}, {'llm': 'error'}):
                    c = run_var(case, var, **kw)
                    self.assertLessEqual(c.turns, 34, (var, case, kw))
                    self.assertIsNotNone(c.diagnosed)
                    self.assertTrue(all(T.nlen(e[1]) <= 30 for e in c.events), (var, case, kw))

    def test_v11a_question_line_and_reset(self):
        from agent import explain, say
        c = run_var('C10', 'v11a')
        self.assertIn('이해 안 되시거나 더 궁금하신 점 있으세요?', [e[1] for e in c.events])
        self.assertIn('인공눈물', dict(explain.SAY_SLOTS)['life'])
        run_var('C10', 'b')   # 끄면 원래대로 돌아온다(모듈 전역 교체가 남지 않음)
        self.assertEqual(say.QUESTION_LINE, '더 궁금하신 점 있으세요?')
        self.assertEqual(explain.SAY_SLOTS, explain.SAY_SLOTS_BASE)

    def test_v11b_open_topic(self):
        from agent import interview
        self.assertEqual(interview._first_open_topic({'cc': '체중 감소'}, None), '체중 감소에 대해 자세히 말씀해 주시겠어요?')
        self.assertEqual(interview._first_open_topic({'cc': '불면 (수면제 처방 원함)'}, None),
                         '안녕하세요, 불면에 대해 자세히 말씀해 주시겠어요?')
        self.assertEqual(interview._first_open_topic({'cc': '아주 긴 주호소 문장이 들어온 경우입니다'}, None), '')
        c = run_var('C10', 'v11b')
        self.assertTrue(c.events[0][1].startswith('체중 감소에 대해'))
        b = run_var('C10', 'b')
        self.assertIn('불편한 데는요', b.events[0][1])

    def test_v11c_prompt(self):
        c = run_var('C10', 'v11c')
        self.assertTrue(any('항목 (+)' in p and '6~12줄' in p for p in c.prompts))
        b = run_var('C10', 'b')
        self.assertFalse(any('6~12줄' in p for p in b.prompts))
        self.assertTrue(any('4~8줄' in p for p in b.prompts))

    def test_v11_off_equals_v10b(self):
        for case in ('C10', 'C01', 'C03'):
            self.assertEqual(seq(run_var(case, 'b')), seq(run_var(case, 'v11c')), case)   # v11c는 대화 불변

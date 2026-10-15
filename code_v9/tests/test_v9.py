"""v9 단위 테스트: 확장 CPX 은행 스키마, 주호소→범주 매핑, 지침 체크리스트 생성·폴백(개발 키·네트워크·LLM 없음)."""
import os
import re
import sys
import unicodedata
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import run  # noqa: E402
from agent import bank2, banks, cpx, glcheck, guidelines, interview  # noqa: E402
from test_v8 import C01, C03, C10  # noqa: E402


def L(s):
    return len(unicodedata.normalize('NFC', s))


# ---------------------------------------------------------------- 1) 은행 스키마
class TestBankSchema(unittest.TestCase):
    def test_category_count(self):
        self.assertEqual(cpx.EXT_LOADED, list(cpx.EXT_MODULES))
        self.assertGreaterEqual(len(cpx.CPX), 50)
        for c in cpx.V8_CATS:
            self.assertIn(c, cpx.CPX)

    def test_every_question_30_and_bundle(self):
        for cat, spec in cpx.CPX.items():
            self.assertLessEqual(L(spec.get('onset_q') or '?'), 30, cat)
            for u in spec['units'] + list(spec.get('add_common') or []):
                self.assertLessEqual(L(u['q']), 30, (cat, u['q']))
                self.assertTrue(u['q'].endswith('?'), (cat, u['q']))
                self.assertEqual(cpx.bundle_violation(u), '', (cat, u['id'], u['q']))
                if u.get('follow'):
                    self.assertLessEqual(L(u['follow'][2]), 30, (cat, u['follow']))

    def test_ids_unique_within_category(self):
        for cat, spec in cpx.CPX.items():
            uids = [u['id'] for u in spec['units']]
            self.assertEqual(len(uids), len(set(uids)), cat)
            iids = [i[0] for u in spec['units'] for i in u['items']]
            self.assertEqual(len(iids), len(set(iids)), (cat, [i for i in iids if iids.count(i) > 1]))

    def test_unit_id_global_consistency(self):
        seen = {}
        for cat, spec in cpx.CPX.items():
            for u in spec['units']:
                if u['id'] in seen:
                    self.assertEqual(seen[u['id']], u['q'], (cat, u['id']))
                seen[u['id']] = u['q']
        common = {u['id'] for u in cpx.ADULT_COMMON + cpx.PEDS_COMMON}
        for cat in cpx.CPX:
            if cat in cpx.V8_CATS:
                continue
            for u in cpx.CPX[cat]['units']:
                self.assertNotIn(u['id'], common, (cat, u['id']))

    def test_exams_and_budget(self):
        for cat, spec in cpx.CPX.items():
            ex = spec.get('exams') or []
            self.assertTrue(6 <= len(ex) <= 8, (cat, ex))
            for e in ex:
                self.assertIn(e, banks.EXAM_BY_ID, (cat, e))
            p1 = [u for u in spec['units'] if u['prio'] == 1 and u['stage'] in ('core', 'red')]
            if cat not in cpx.V8_CATS:   # v8 범주(weight_loss 11개)는 그대로 둔다
                self.assertLessEqual(len(p1), 10, cat)

    def test_ext_detect_desc(self):
        for cat in cpx.CPX:
            if cat in cpx.V8_CATS:
                continue
            self.assertIn(cat, cpx.DETECT_EXT, cat)
            re.compile(cpx.DETECT_EXT[cat])
            self.assertIn(cat, cpx.category_desc(), cat)
        for k, v in cpx.ITEM_Q.items():
            self.assertLessEqual(L(v), 30, k)

    def test_v8_item_q_mention_not_overridden(self):
        # 확장 모듈은 v8 항목의 단독 재질문·언급 규칙을 바꾸지 않는다
        self.assertEqual(cpx.ITEM_Q['ros_cp'], '가슴 통증이 있으세요?')
        self.assertEqual(cpx.MENTION['ros_palp'], r'두근')


# ---------------------------------------------------------------- 범주 매핑
class Enc:
    def __init__(self, opening, prof=None, diffs=None, cfg=None):
        self.opening = opening
        self.vitals = ''
        self.profile = prof or {}
        self.differentials = diffs or []
        self.cfg = cfg or run.load_config()
        self.client = None
        self.budget = None
        self.calls = 0

    def time_left(self):
        return 1500.0


def cats_for(opening, llm_cats=(), age=None, sex=None):
    enc = Enc(opening)
    res = {'categories': list(llm_cats)}
    if age is not None:
        res['age'] = age
    if sex:
        res['sex'] = sex
    return interview._intake_post(enc, res)


class TestMapping(unittest.TestCase):
    def test_v8_samples_detection_unchanged(self):
        for op, peds in ((C01, False), (C03, True), (C10, False)):
            self.assertEqual(cpx.detect_all(op, peds), bank2.detect_categories(op, peds))
        self.assertEqual(cats_for(C01, ['insomnia', 'substance'])['categories'][0], 'substance')
        self.assertEqual(cats_for(C03, ['growth'])['categories'], ['growth'])
        self.assertEqual(cats_for(C10, ['weight_loss'])['categories'][0], 'weight_loss')

    def test_keyword_examples(self):
        ex = [
            ('마흔 살 남자이다. 허리가 아파서 왔다.', 'back_pain'),
            ('서른 살 여자이다. 소변에 피가 섞여 나와서 왔다.', 'hematuria'),
            ('쉰 살 남자이다. 어제 피를 토해서 왔다.', 'hematemesis'),
            ('스무 살 여자이다. 아침에 쓰러져서 왔다.', 'syncope'),
            ('스물네 살 여자이다. 생리를 석 달째 안 해서 왔다.', 'menstrual'),
            ('스물여덟 살 여자이다. 온몸에 두드러기가 났다.', 'rash'),
            ('예순 살 남자이다. 손이 떨려서 왔다.', 'tremor'),
            ('마흔 살 남자이다. 사흘째 열이 나서 왔다.', 'fever'),
            ('서른 살 남자이다. 설사를 계속 해서 왔다.', 'diarrhea'),
        ]
        for op, want in ex:
            got = cats_for(op)['categories']
            self.assertEqual(got[0], want, (op, got))

    def test_peds_and_sex_branches(self):
        p = cats_for('두 살 남자아이이다. 엄마가 함께 왔다. 어제부터 열이 나서 왔다.', age=2)
        self.assertTrue(p['pediatric'])
        self.assertEqual(p['categories'][0], 'p_fever')
        m = cats_for('서른 살 남자이다. 생리 같은 출혈은 아니고 소변에 피가 나와요.', ['menstrual', 'hematuria'], sex='M')
        self.assertNotIn('menstrual', m['categories'])
        a = cats_for('서른 살 남자이다. 허리가 아파요.', ['p_fever', 'back_pain'])
        self.assertNotIn('p_fever', a['categories'])

    def test_coarse_to_child(self):
        self.assertEqual(cats_for('쉰 살 여자이다. 손가락 마디가 아파서 왔다.', ['msk'])['categories'][0], 'joint_pain')
        self.assertEqual(cats_for('서른 살 여자이다. 온몸이 가려워서 왔다.', ['skin'])['categories'][0], 'pruritus')

    def test_unknown_goes_general(self):
        p = cats_for('서른다섯 살 남자이다. 오른쪽 눈이 빨개져서 왔다.')
        self.assertEqual(p['categories'], ['general'])
        self.assertEqual(p['cat_source'], 'default')

    def test_llm_ext_category_accepted(self):
        p = cats_for('마흔 살 남자이다. 몸이 불편해서 왔다.', ['neck_mass'])
        self.assertEqual(p['categories'][0], 'neck_mass')

    def test_build_ext_and_elderly(self):
        prof = {'age': 70, 'sex': 'M', 'pediatric': False, 'categories': ['hematuria', 'urinary']}
        b = cpx.build(prof, '일흔 살 남자이다. 소변에 피가 나와요.')
        self.assertEqual(b['main'], 'hematuria')
        ids = [u['id'] for u in b['units']]
        self.assertIn('el_fall', ids)
        self.assertTrue(b['bank'])
        ch, _ = cpx.compile_units(b['units'], 17)
        self.assertLessEqual(len(ch), 17)


# ---------------------------------------------------------------- 3) 지침 체크리스트 생성·폴백
RAW = [
    {'q': '시력이 떨어졌나요?', 'label': '시력 저하', 'stage': 'red', 'system': 'eye', 'red': True},
    {'q': '눈곱이 많이 끼나요?', 'label': '분비물', 'stage': 'core', 'system': 'eye'},
    {'q': '증상을 전부 말씀해 주세요.', 'label': '나열', 'stage': 'core', 'system': 'gen'},
    {'q': '안압이 21 이상이라고 들은 적 있나요?', 'label': '안압', 'stage': 'hx', 'system': 'eye'},
    {'q': '관절이 아프거나 허리가 뻣뻣하고 피부에 발진이 있나요?', 'label': '전신', 'stage': 'core', 'system': 'msk'},
    {'q': '배가 아프세요?', 'label': '복통', 'stage': 'core', 'system': 'gi'},
    {'q': '시력이 떨어졌나요?', 'label': '중복', 'stage': 'core', 'system': 'eye'},
    'garbage',
]


class TestGlcheck(unittest.TestCase):
    def test_compile_filters(self):
        units = glcheck.compile_items(RAW, [], {'eye', 'gen'}, False, 1, 8)
        qs = [u['q'] for u in units]
        self.assertEqual(qs, ['시력이 떨어졌나요?', '눈곱이 많이 끼나요?'])
        self.assertTrue(units[0]['safety'])
        self.assertEqual(units[0]['stage'], 'red')
        for u in units:
            self.assertEqual(cpx.bundle_violation(u), '')
            self.assertLessEqual(L(u['q']), 30)
        self.assertEqual(glcheck.compile_items(None, [], None, False, 1, 8), [])

    def _weak(self, diffs=()):
        prof = {'age': 35, 'sex': 'M', 'pediatric': False, 'categories': ['general'], 'cc': '눈 충혈', 'cat_source': 'default'}
        enc = Enc('서른다섯 살 남자이다. 오른쪽 눈이 빨개져서 왔다.', prof, list(diffs))
        b = cpx.build(prof, enc.opening)
        return enc, b

    def test_guideline_path(self):
        enc, b = self._weak(['급성 결막염'])
        with mock.patch.object(guidelines, '_on', return_value=True), \
                mock.patch.object(guidelines, 'gather', return_value=('[출처: X]\nHistory: redness, discharge, vision', ['X'])), \
                mock.patch.object(glcheck, 'ask_json', return_value={'items': RAW}) as aj:
            out = glcheck.supplement(enc, b, b['units'])
        self.assertEqual(aj.call_count, 1)
        self.assertEqual(aj.call_args.kwargs['effort'], 'low')
        self.assertEqual(b['supp']['strength'], 'weak')
        self.assertEqual(b['supp']['gl'], 2)
        self.assertEqual([u['q'] for u in out][:2], ['시력이 떨어졌나요?', '눈곱이 많이 끼나요?'])
        self.assertEqual(out[0]['prio'], 1)

    def test_no_guideline_falls_back(self):
        enc, b = self._weak(['폐렴'])
        with mock.patch.object(glcheck, 'ask_json') as aj:
            out = glcheck.supplement(enc, b, b['units'])
        aj.assert_not_called()                      # 지침 발췌가 없으면 LLM을 부르지 않는다
        self.assertEqual(b['supp']['gl'], 0)
        for u in out:
            self.assertEqual(cpx.bundle_violation(u), '')

    def test_llm_failure_no_exception(self):
        enc, b = self._weak(['급성 결막염'])
        with mock.patch.object(guidelines, '_on', return_value=True), \
                mock.patch.object(guidelines, 'gather', return_value=('text', ['X'])), \
                mock.patch.object(glcheck, 'ask_json', side_effect=RuntimeError('boom')):
            out = glcheck.supplement(enc, b, b['units'])
        self.assertIsInstance(out, list)
        self.assertEqual(b['supp']['gl'], 0)

    def test_total_failure_returns_empty(self):
        enc, b = self._weak()
        with mock.patch.object(glcheck, 'bank_strength', side_effect=RuntimeError('x')):
            self.assertEqual(glcheck.supplement(enc, b, b['units']), [])

    def test_strong_bank_no_llm(self):
        prof = {'age': 32, 'sex': 'F', 'pediatric': False, 'categories': ['weight_loss'], 'cc': '체중 감소',
                'cat_detected': ['weight_loss']}
        enc = Enc(C10, prof, ['그레이브스병'])
        b = cpx.build(prof, C10)
        with mock.patch.object(glcheck, 'ask_json') as aj:
            out = glcheck.supplement(enc, b, b['units'])
        aj.assert_not_called()
        self.assertEqual(b['supp']['strength'], 'strong')
        self.assertTrue(all(u['prio'] == 3 for u in out))
        self.assertEqual(out, [])   # 은행·필수 단위가 예산(17)을 채우면 DDXPlus 보충 없음(남는 슬롯에만)

    def test_strong_small_bank_ddx_fills_room_only(self):
        prof = {'age': 50, 'sex': 'M', 'pediatric': False, 'categories': ['chest_pain'], 'cc': '흉통',
                'cat_detected': ['chest_pain']}
        enc = Enc('쉰 살 남자이다. 가슴이 아파서 왔다.', prof, ['급성 심근경색', '폐색전증'])
        b = cpx.build(prof, enc.opening)
        units = b['units'][:10]
        out = glcheck.supplement(enc, b, units)
        self.assertLessEqual(len(out), 17 - 10)
        self.assertTrue(out and all(u['prio'] == 3 for u in out))
        ch, _ = cpx.compile_units(units + out, 17)
        for u in units:
            if cpx.is_must(u):
                self.assertIn(u, ch)

    def test_medium_strength(self):
        prof = {'age': 40, 'sex': 'M', 'pediatric': False, 'categories': ['neck_mass'], 'cc': '목 불편',
                'cat_detected': []}
        b = cpx.build(prof, '마흔 살 남자이다.')
        self.assertEqual(glcheck.bank_strength(prof, b), 'medium')

    def test_time_budget_skips_llm(self):
        enc, b = self._weak(['급성 결막염'])
        enc.time_left = lambda: 100.0
        with mock.patch.object(guidelines, '_on', return_value=True), \
                mock.patch.object(glcheck, 'ask_json') as aj:
            glcheck.supplement(enc, b, b['units'])
        aj.assert_not_called()


if __name__ == '__main__':
    unittest.main()

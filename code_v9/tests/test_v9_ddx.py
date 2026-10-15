"""v9 DDXPlus 감별 질문 KB·매처 테스트(네트워크·개발 키 없음)."""
import os
import sys
import unicodedata
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from agent import cpx, ddx  # noqa: E402


def nlen(s):
    return len(unicodedata.normalize('NFC', s))


class TestDdxKb(unittest.TestCase):
    def test_kb_loads(self):
        kb = ddx._kb()
        self.assertEqual(kb['license'], 'CC BY 4.0')
        self.assertGreaterEqual(len(kb['conditions']), 49)
        self.assertGreater(len(kb['evidences']), 150)
        self.assertLess(os.path.getsize(ddx.KB_PATH), 300_000)

    def test_questions_valid(self):
        for code, e in ddx._kb()['evidences'].items():
            q = e['q']
            self.assertLessEqual(nlen(q), 30, code)
            self.assertTrue(q.endswith('?'), code)
            self.assertEqual(q.count('?'), 1, code)
            self.assertTrue(cpx.check_question(q)[0], (code, q))
            self.assertLessEqual(nlen(e['label']), 12, code)

    def test_conditions_have_ko(self):
        kb = ddx._kb()
        for cid, c in kb['conditions'].items():
            self.assertTrue(c['ko'], cid)
            for code in c['symptoms'] + c['antecedents']:
                self.assertIn(code, kb['evidences'], (cid, code))


class TestMatch(unittest.TestCase):
    def test_hits(self):
        self.assertEqual(ddx.match(['폐색전증']), ['Pulmonary embolism'])
        self.assertEqual(ddx.match(['급성 심근경색']), ['Possible NSTEMI / STEMI'])
        self.assertEqual(ddx.match(['급성 심근경색 (STEMI)']), ['Possible NSTEMI / STEMI'])
        self.assertEqual(ddx.match(['Pneumonia']), ['Pneumonia'])
        self.assertEqual(ddx.match(['Community-acquired pneumonia']), ['Pneumonia'])
        self.assertEqual(ddx.match(['감기']), ['URTI'])
        self.assertEqual(ddx.match(['불안정 협심증']), ['Unstable angina'])
        self.assertEqual(ddx.match(['만성 부비동염']), ['Chronic rhinosinusitis'])

    def test_order_and_dedup(self):
        self.assertEqual(ddx.match(['폐렴', '폐색전증', 'pneumonia']), ['Pneumonia', 'Pulmonary embolism'])

    def test_no_false_positives(self):
        self.assertEqual(ddx.match(['그레이브스병']), [])
        self.assertEqual(ddx.match(['수면제 사용장애']), [])
        self.assertEqual(ddx.match(['체질성 성장지연']), [])
        self.assertEqual(ddx.match([]), [])
        self.assertEqual(ddx.match(None), [])

    def test_conditions_info(self):
        info = ddx.conditions_info(['폐색전증'])
        self.assertEqual(info[0]['ko'], '폐색전증')
        self.assertEqual(info[0]['en'], 'Pulmonary embolism')


class TestUnits(unittest.TestCase):
    NAMES = ['폐색전증', '폐렴', '급성 심근경색']

    def test_units_valid(self):
        us = ddx.units(self.NAMES)
        self.assertTrue(us)
        self.assertLessEqual(len(us), 8)
        ids = [u['id'] for u in us]
        self.assertEqual(len(ids), len(set(ids)))
        for u in us:
            self.assertEqual(cpx.bundle_violation(u), '', u)
            self.assertTrue(cpx.check_question(u['q'])[0], u)
            self.assertIn(u['stage'], cpx.STAGES)
            self.assertIn(u['prio'], (1, 2))
        reds = [bool(u['safety']) for u in us]
        self.assertEqual(reds, sorted(reds, reverse=True))   # 경고증상 먼저
        self.assertTrue(reds[0])

    def test_have_items_filter(self):
        us = ddx.units(self.NAMES)
        have = {us[0]['items'][0][0], us[1]['items'][0][0]}
        us2 = ddx.units(self.NAMES, have_items=have)
        self.assertFalse(have & {u['items'][0][0] for u in us2})

    def test_n_and_prio(self):
        us = ddx.units(self.NAMES, n=4, prio=2)
        self.assertLessEqual(len(us), 4)
        self.assertEqual([u['prio'] for u in us], [2, 2, 3, 3][:len(us)])

    def test_sex_and_pediatric(self):
        kb = ddx._kb()
        for u in ddx.units(['빈혈', '공황발작', 'GERD', '폐색전증'], n=40, sex='M'):
            self.assertNotEqual(kb['evidences'][u['id'][3:]].get('sex'), 'F', u)
        for u in ddx.units(['폐렴', '기관지염', '폐암', 'COPD'], n=40, pediatric=True):
            self.assertFalse(kb['evidences'][u['id'][3:]].get('adult'), u)

    def test_no_match_empty(self):
        self.assertEqual(ddx.units(['그레이브스병']), [])

    def test_broken_kb_no_raise(self):
        with mock.patch.object(ddx, '_KB', None), mock.patch.object(ddx, '_SYN', None), \
                mock.patch.object(ddx, '_load_kb', side_effect=OSError('missing')):
            self.assertEqual(ddx.units(self.NAMES), [])
            self.assertEqual(ddx.match(self.NAMES), [])
            self.assertEqual(ddx.conditions_info(self.NAMES), [])
        with mock.patch.object(ddx, '_KB', None), mock.patch.object(ddx, '_SYN', None), \
                mock.patch.object(ddx, 'KB_PATH', '/nonexistent/ddx_kb.json'):
            self.assertEqual(ddx.units(self.NAMES), [])


if __name__ == '__main__':
    unittest.main()

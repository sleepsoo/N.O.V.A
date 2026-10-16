"""v14: 긴급도 판정(응급실 안내·조기 재진·기록 처치 결정), 약한 범주 LLM 진찰 선택, 금기 질문 감별 등급. 공개 샘플(만성 3례)은 v13과 동일."""
import json
import os
import re
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import run  # noqa: E402
from agent import explain, urgency as urg  # noqa: E402
import test_v8 as T  # noqa: E402
from test_v12 import run_var  # noqa: E402
from test_v13 import V13  # noqa: E402

V14 = dict(V13, V14='1')

SYNTH = {
    'AB': ('저는 마흔 살 남자이다. 이틀 전부터 오른쪽 아랫배가 아프다.',
           {'age': 40, 'sex': 'M', 'pediatric': False, 'informant': '본인', 'chief_complaint': '복통', 'request': '',
            'categories': ['abd_pain'], 'differential': ['급성 충수염', '게실염', '요로결석', '장염', '탈장']}, 'emergency'),
    'TN': ('저는 마흔다섯 살 남자이다. 한 달 전부터 왼쪽 귀에서 소리가 울리고 잘 안 들린다.',
           {'age': 45, 'sex': 'M', 'pediatric': False, 'informant': '본인', 'chief_complaint': '이명·난청', 'request': '',
            'categories': ['general'], 'differential': ['돌발성 난청', '메니에르병', '이독성 약물', '청신경종', '귀지 매복']}, 'urgent'),
}


def run_synth(key, cfg):
    op, prof, urgency_level = SYNTH[key]
    orig = T.FakeClient.answer

    def answer(self, user):
        if '"discriminators"' in user:
            p = dict(prof, discriminators=[{'q': '열이 나거나 오한이 있나요?', 'label': '발열', 'system': 'gen'}],
                     contra=[{'q': '위장약이나 아스피린 드세요?', 'label': '아스피린'}], empathy='힘드셨죠.')
            return json.dumps(p, ensure_ascii=False)
        if '"pairs"' in user:
            return json.dumps({'pairs': []})
        if '"exam_ids"' in user:
            return json.dumps({'exam_ids': ['ear', 'nystagmus', 'cerebellar', 'cervical_ln', 'dysarthria', 'gait', 'conj']})
        if 'diagnosis_ko' in user:
            return json.dumps({'diagnosis_ko': prof['differential'][0], 'diagnosis_en': '', 'confidence': 0.7, 'evidence': [],
                               'differential': [{'dx': prof['differential'][1], 'reason': '감별', 'refs': [], 'test': '검사'}]},
                              ensure_ascii=False)
        if '[SAY 규칙]' in user:
            n = len(re.findall(r'^\d+\. \[', user, flags=re.M))
            return json.dumps({'say': ['원인 질환 가능성이 높아요.', '그 때문에 지금 증상이 생겨요.',
                                       '피검사로 원인을 확인하고 2주 뒤 결과 봐요.', '약으로 1~2주 치료하면 대부분 좋아져요.',
                                       '고열·심한 통증·의식 변화 시 바로 오세요.'][:n]}, ensure_ascii=False)
        if '"answer"' in user:
            return json.dumps({'answer': '피검사와 필요한 영상검사를 해요.'}, ensure_ascii=False)
        if '"cc_text"' in user:
            return json.dumps({'cc_text': prof['chief_complaint'], 'onset': '', 'pain': '', 'hpi': '', 'meds': '',
                               'pmh_others': '', 'fh_others': '', 'sh_others': '', 'ros_others': ''}, ensure_ascii=False)
        if '[P 규칙]' in user:
            return json.dumps({'tests': [{'name': 'CBC, CRP', 'reason': '염증'}], 'treatment': ['진통제 고려'],
                               'disposition': ['외래 추적'], 'follow_up': ['재진 : 1~2주 뒤 결과 확인'], 'education': ['휴식'],
                               'urgency': urgency_level, 'faq': {'prognosis': '치료하면 대부분 좋아져요.'}}, ensure_ascii=False)
        return orig(self, user)
    env = {'NOVA_AGENT_' + k: v for k, v in cfg.items()}
    env['NOVA_AGENT_GUIDE'] = '0'
    pat = dict(T.PATIENT)
    pat[key] = []
    cq = dict(T.CASE_Q)
    cq[key] = '검사는 뭘 하나요?'
    with mock.patch.dict(os.environ, env), mock.patch.object(T.FakeClient, 'answer', answer), \
            mock.patch.object(T, 'PATIENT', pat), mock.patch.object(T, 'CASE_Q', cq):
        client = T.FakeClient(key, op)
        state = run.prepare()
        run.consult(client, state)
    return client


def fake_enc(dx='', replies=(), v14=True, vitals='혈압 : 120/80 mmHg\n맥박 : 80 회/분\n호흡 : 16 회/분\n체온 : 36.5°C'):
    return SimpleNamespace(cfg={'V14': 1 if v14 else 0}, dx=dx, vitals=vitals, assess={},
                           ledger=[{'kind': 'EXAM', 'reply': r} for r in replies])


class TestAssess(unittest.TestCase):
    def test_exam_red_flag(self):
        e = fake_enc('급성 위장염', ['압통(+), 반발통(+), 근성방어(-)'])
        r = urg.assess(e, None, {'urgency': 'routine'})
        self.assertEqual(r['level'], 'emergency')
        self.assertIn('반발통', r['red'])
        self.assertEqual(r['dept'], '외과')

    def test_dx_name_and_llm(self):
        self.assertEqual(urg.assess(fake_enc('급성 충수염'), None, {})['level'], 'emergency')
        self.assertEqual(urg.assess(fake_enc('지역사회 획득 폐렴'), None, {})['level'], 'urgent')
        self.assertEqual(urg.assess(fake_enc('긴장형 두통'), None, {'urgency': 'urgent'})['level'], 'urgent')
        self.assertEqual(urg.assess(fake_enc('긴장형 두통'), None, {'disposition': ['응급실 전원 필요']})['level'], 'emergency')
        self.assertEqual(urg.assess(fake_enc('긴장형 두통'), None, {'disposition': ['응급 소견 없어 외래 추적']})['level'], 'routine')

    def test_kb_dx_not_escalated_by_text(self):
        k = {'id': 'graves'}
        self.assertEqual(urg.assess(fake_enc('그레이브스병'), k, {'urgency': 'emergency'})['level'], 'routine')
        self.assertEqual(urg.assess(fake_enc('그레이브스병', ['경부 강직(+)']), k, {})['level'], 'emergency')

    def test_unstable_vitals(self):
        e = fake_enc('급성 위장염', vitals='혈압 : 82/50 mmHg\n맥박 : 125 회/분\n호흡 : 22 회/분\n체온 : 38.0°C')
        self.assertEqual(urg.assess(e, None, {})['level'], 'emergency')

    def test_off(self):
        self.assertEqual(urg.assess(fake_enc('급성 충수염', v14=False), None, {'urgency': 'emergency'})['level'], 'routine')

    def test_followup_phrase(self):
        e = SimpleNamespace(urgency={'level': 'urgent'})
        self.assertEqual(explain._followup_phrase(e, None, {}), '2~3일 뒤')
        self.assertEqual(explain._followup_phrase(e, None, {'follow_up': ['재진 : 1일 뒤']}), '1일 뒤')
        e2 = SimpleNamespace(urgency={'level': 'routine'})
        self.assertEqual(explain._followup_phrase(e2, None, {}), '1~2주 뒤')
        self.assertLessEqual(T.nlen(urg.EMERG_SAY), 30)


class TestSamplesUnchanged(unittest.TestCase):
    def test_equals_v13(self):
        for case in ('C01', 'C03', 'C10'):
            a = [e[1] for e in run_var(case, V13).events]
            b = [e[1] for e in run_var(case, V14).events]
            self.assertEqual(a, b, case)
            self.assertFalse(any('응급실' in x for x in b), case)


class TestSynthetic(unittest.TestCase):
    def test_emergency_case(self):
        c = run_synth('AB', V14)
        says = [e[1] for e in c.events if e[0] == 'SAY']
        self.assertLessEqual(c.turns, 34)
        self.assertTrue(any('응급실' in s for s in says))
        self.assertFalse(any(re.search(r'주 뒤', s) for s in says))
        note = c.diagnosed[0]
        self.assertIn('응급실 의뢰', note['P']['disposition'])
        self.assertNotIn('입원 불필요', note['P']['disposition'])
        self.assertIn(urg.EMERG_FU, note['P']['follow_up'])

    def test_emergency_off_says_weeks(self):
        c = run_synth('AB', dict(V14, V14='0'))
        says = [e[1] for e in c.events if e[0] == 'SAY']
        self.assertFalse(any('응급실' in s for s in says))

    def test_weak_category_llm_exams_and_urgent(self):
        c = run_synth('TN', V14)
        ex = [e[1] for e in c.events if e[0] == 'EXAM']
        self.assertEqual(len(ex), 11)
        self.assertTrue(any('고막' in x for x in ex))
        self.assertEqual(c.turns, 34)
        says = [e[1] for e in c.events if e[0] == 'SAY']
        self.assertTrue(any('2~3일 뒤' in s for s in says))
        self.assertIn('2~3일', c.diagnosed[0]['P']['follow_up'])

    def test_weak_category_fills_window_without_llm(self):
        c = run_synth('TN', dict(V14, V14='0'))
        self.assertLess(sum(e[0] == 'EXAM' for e in c.events), 11)   # v13: 범주 표 없음 → 창이 비고 턴 낭비(v14가 고친 결함)


if __name__ == '__main__':
    unittest.main()

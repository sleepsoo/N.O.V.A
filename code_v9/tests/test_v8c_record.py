"""v8c: 소아 저신장 감별 규칙(assess) + 묶음 질문 미응답 항목 기록 무결성(facts/note2/record). LLM 호출 없음."""
from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from agent import assess, facts, note2, record  # noqa: E402

C03 = ('이름은 김도현이고, 여섯 살 남자아이이다. 엄마 김지영, 서른일곱 살이 보호자로 함께 왔다. 엄마는 도현이 키가 또래에 비해 '
       '많이 작은 것 같아 걱정이 된다고 말했다. 엄마가 집에서 키를 재보니, 일 년 전에는 백 센티미터였고 지금은 백오 센티미터 정도였다.')
VITALS = '혈압 : 100/60 mmHg\n맥박 : 90 회/분\n호흡 : 20 회/분\n체온 : 36.7°C'


def it(iid, label, answered, pol, kw='.'):
    return {'id': iid, 'label': label, 'answered': answered, 'pol': pol, 'kw': kw}


def say(turn, q, a, items=None, phase='interview', qid='u'):
    return {'turn': turn, 'kind': 'SAY', 'text': q, 'reply': a, 'phase': phase, 'qid': qid, 'label': '', 'items': items}


def exam(turn, name, result):
    return {'turn': turn, 'kind': 'EXAM', 'text': name, 'reply': result}


class FakeEnc:
    def __init__(self, ledger, opening=C03, sex='M', age=6, pediatric=True):
        self.ledger = ledger
        self.opening = opening
        self.vitals = VITALS
        self.profile = {'age': age, 'sex': sex, 'pediatric': pediatric, 'informant': '모'}
        self.cfg = {}
        self.differentials = []
        self.dx = ''
        self.facts = []


# ---------------------------------------------------------------- 과제 1: 소아 저신장 감별
def _ss_case(late_reply, parents_reply, growth_result, dx, evidence=None, diff=None, extra=None):
    led = [say(3, '부모님 키는 각각 어떻게 되세요?', parents_reply, [it('gr_parents', '부모 키', True, '?')], qid='gr_parents'),
           say(4, '부모님 중 늦게 키가 큰 분 있나요?', late_reply, [it('gr_late', '부모 사춘기 지연', True, '?')], qid='gr_late'),
           say(17, '가족 중 키가 작거나 유전병 있나요?', '아빠는 어릴 때 키가 작았고, 유전 질환은 없어요.',
               [it('gr_fh_short', '저신장 가족력', True, '+', '키|작'), it('gr_fh_genetic', '유전병 가족력', True, '-', '유전')]),
           exam(20, '성장도표 백분위수 확인하겠습니다', growth_result),
           exam(22, '사춘기 성숙도 평가하겠습니다', 'Tanner 1기, 고환 2mL/2mL')] + (extra or [])
    enc = FakeEnc(led)
    fs = [{'id': 'F1', 'turn': 3, 'sec': 'fh', 'key': 'other', 'label': '부모 키', 'pol': '?', 'detail': ''},
          {'id': 'F2', 'turn': 4, 'sec': 'fh', 'key': 'other', 'label': '부 성장 양상', 'pol': '?', 'detail': ''},
          {'id': 'F3', 'turn': 17, 'sec': 'fh', 'key': 'other', 'label': '저신장 가족력', 'pol': '+', 'detail': ''}]
    out = {'facts': fs, 'exams': assess.exam_rows(enc), 'dx': assess.normalize_dx(dx, ''),
           'evidence': evidence if evidence is not None else [], 'differential': diff if diff is not None else []}
    return enc, out


LATE = '아빠는 어릴 때 키가 작아서 할머니가 걱정했는데, 고등학교에 들어가서 갑자기 키가 많이 컸다고 해요.'
NOT_LATE = '아니요, 그런 분은 없어요.'
GROWTH_NORMAL_MPH = '신장 3백분위수 미만, 성장속도 5cm/년(정상 하한), 중간부모키 178cm'
GROWTH_LOW_MPH = '신장 3백분위수 미만, 성장속도 5cm/년(정상 하한), 중간부모키 160cm'


class TestShortStatureRule(unittest.TestCase):
    def test_c03_like_switches_to_cdgp(self):
        ev = [{'text': '가족력에 부모 중 저신장자 있음으로 유전적 요인이 강하게 지지된다', 'refs': ['F3']},
              {'text': '성장 속도 5cm/년으로 정상 하한', 'refs': ['E1']}]
        diff = [{'dx': 'Growth hormone deficiency', 'reason': '…', 'refs': ['E1'], 'test': 'IGF-1'},
                {'dx': '체질성 성장지연', 'reason': '…', 'refs': [], 'test': ''}]
        enc, out = _ss_case(LATE, '아빠는 118cm, 엄마는 165cm예요.', GROWTH_NORMAL_MPH, '가족성 저신장', ev, diff)
        assess.apply_short_stature_rule(enc, out)
        self.assertIn('체질성 성장지연', out['dx'])
        self.assertEqual(out['dx_rule'], {'from': '가족성 저신장 (Familial short stature)', 'to': 'CDGP'})
        sig = out['short_stature']
        self.assertTrue(sig['late'])
        self.assertEqual(sig['late_turn'], 4)
        self.assertIsNone(sig['father'])           # 118cm는 잘못 들린 값 → 무시
        self.assertEqual(sig['mother'], 165.0)
        self.assertEqual(sig['mph'], 178.0)
        self.assertFalse(sig['parents_short'])
        texts = ' '.join(e['text'] for e in out['evidence'])
        self.assertNotIn('유전적 요인', texts)         # 이전 진단 지지 근거 제거
        self.assertIn('늦은 성장 가족력', texts)
        self.assertIn('중간부모키 178cm', texts)
        self.assertIn('가족성 저신장', out['differential'][0]['dx'])
        self.assertFalse(any('체질성' in d['dx'] for d in out['differential']))
        self.assertIn('Growth hormone deficiency', [d['dx'] for d in out['differential']])

    def test_parents_short_no_late_switches_to_fss(self):
        enc, out = _ss_case(NOT_LATE, '아빠는 160cm, 엄마는 148cm예요.', GROWTH_LOW_MPH, '체질성 성장지연')
        assess.apply_short_stature_rule(enc, out)
        self.assertIn('가족성 저신장', out['dx'])
        self.assertTrue(out['short_stature']['parents_short'])
        self.assertFalse(out['short_stature']['late'])
        self.assertIn('체질성 성장지연', out['differential'][0]['dx'])
        self.assertIn('중간부모키 160cm로 낮음', ' '.join(e['text'] for e in out['evidence']))

    def test_both_keeps_llm_choice_and_adds_other(self):
        for dx, other in (('가족성 저신장', '체질성'), ('체질성 성장지연', '가족성')):
            enc, out = _ss_case(LATE, '아빠는 160cm, 엄마는 150cm예요.', GROWTH_LOW_MPH, dx)
            assess.apply_short_stature_rule(enc, out)
            self.assertIn(dx, out['dx'])
            self.assertNotIn('dx_rule', out)
            self.assertIn(other, out['differential'][0]['dx'])

    def test_both_with_delayed_bone_age_goes_cdgp(self):
        extra = [exam(24, '골연령 확인하겠습니다', '골연령 4세(역연령 6세)')]
        enc, out = _ss_case(LATE, '아빠는 160cm, 엄마는 150cm예요.', GROWTH_LOW_MPH, '가족성 저신장', extra=extra)
        assess.apply_short_stature_rule(enc, out)
        self.assertEqual(out['short_stature']['bone'], 'delayed')
        self.assertIn('체질성 성장지연', out['dx'])

    def test_neither_signal_unchanged(self):
        enc, out = _ss_case(NOT_LATE, '잘 모르겠어요.', '신장 3백분위수 미만, 성장속도 5cm/년', '가족성 저신장')
        assess.apply_short_stature_rule(enc, out)
        self.assertIn('가족성 저신장', out['dx'])
        self.assertNotIn('dx_rule', out)
        self.assertIsNone(out['short_stature']['parents_short'])
        self.assertIn('체질성', out['differential'][0]['dx'])   # 감별에는 상대 진단을 넣는다

    def test_idiopathic_maps_by_signal(self):
        enc, out = _ss_case(LATE, '아빠는 175cm, 엄마는 162cm예요.', GROWTH_NORMAL_MPH, '특발성 저신장')
        assess.apply_short_stature_rule(enc, out)
        self.assertIn('체질성 성장지연', out['dx'])

    def test_non_short_stature_dx_untouched(self):
        enc, out = _ss_case(LATE, '아빠는 160cm', GROWTH_LOW_MPH, '성장호르몬 결핍증')
        before = dict(out)
        assess.apply_short_stature_rule(enc, out)
        self.assertEqual(out['dx'], before['dx'])
        self.assertNotIn('short_stature', out)

    def test_negated_late_not_counted(self):
        sig = assess.short_stature_signals([(4, '아빠가 늦게 키가 크지는 않았어요.')], [])
        self.assertFalse(sig['late'])
        sig = assess.short_stature_signals([(4, '엄마가 사춘기가 늦었다고 해요.')], [])
        self.assertTrue(sig['late'])
        sig = assess.short_stature_signals([(4, '아빠는 중학교 들어가서 많이 자랐대요.')], [])
        self.assertTrue(sig['late'])

    def test_short_yes_to_late_question(self):
        led = [say(4, '부모님 중 늦게 키가 큰 분 있나요?', '네, 아빠가 그랬어요.',
                   [it('gr_late', '부모 사춘기 지연', True, '+')])]
        sig = assess.short_stature_signals([(4, '네, 아빠가 그랬어요.')], [], ledger=led)
        self.assertTrue(sig['late'])

    def test_mph_threshold_by_sex(self):
        ex = [{'id': 'E1', 'turn': 20, 'name': '성장도표', 'result': '중간부모키 158cm'}]
        self.assertTrue(assess.short_stature_signals([], ex, sex='M')['parents_short'])    # 남 <165
        self.assertFalse(assess.short_stature_signals([], ex, sex='F')['parents_short'])   # 여 <152
        self.assertTrue(assess.short_stature_signals([], ex)['parents_short'])              # 미상 <158.5

    def test_parent_height_parsing(self):
        sig = assess.short_stature_signals([(3, '아빠는 크고 엄마는 145cm예요.')], [])
        self.assertIsNone(sig['father'])          # 엄마 키를 아빠 키로 잘못 잡지 않음
        self.assertEqual(sig['mother'], 145.0)
        self.assertTrue(sig['parents_short'])
        sig = assess.short_stature_signals([(3, '아빠는 170, 엄마는 158이에요.')], [])
        self.assertFalse(sig['parents_short'])

    def test_decision_table(self):
        d = assess.short_stature_decision
        self.assertEqual(d('가족성 저신장', {'late': True, 'parents_short': False}), 'CDGP')
        self.assertEqual(d('가족성 저신장', {'late': True, 'parents_short': None}), 'CDGP')
        self.assertEqual(d('체질성 성장지연', {'late': False, 'parents_short': True}), 'FSS')
        self.assertIsNone(d('체질성 성장지연', {'late': True, 'parents_short': True}))
        self.assertIsNone(d('가족성 저신장', {'late': False, 'parents_short': None}))
        self.assertEqual(d('가족성 저신장', {'late': False, 'parents_short': False, 'bone': 'delayed'}), 'CDGP')
        self.assertIsNone(d("Graves' disease", {'late': True, 'parents_short': False}))


# ---------------------------------------------------------------- 과제 2: 미응답 항목 기록 무결성
class TestBundleIntegrity(unittest.TestCase):
    def _anv(self, out):
        return next(l for l in out['ros'].split('\n') if l.startswith('Anorexia'))

    def test_partial_triple_unanswered_not_negative(self):
        led = [say(7, '잘 지치거나 변비, 추위 타나요?', '피곤해요.',
                   [it('gr_fatigue', '피로', True, '+', '지치|피곤'), it('ros_constip', '변비', False, '?', '변비'),
                    it('ft_cold', '추위 불내성', False, '?', '추위')])]
        enc = FakeEnc(led)
        rows = facts.qa_rows(enc)
        fb = facts.fallback(enc, rows)
        self.assertFalse(any(f['key'] == 'ros.Constipation' for f in fb))
        llm = [{'turn': 7, 'sec': 'ros', 'key': 'ros.Constipation', 'label': '변비', 'pol': '-', 'detail': ''},
               {'turn': 7, 'sec': 'ros', 'key': 'other', 'label': '추위 불내성', 'pol': '-', 'detail': ''},
               {'turn': 7, 'sec': 'hpi', 'key': 'other', 'label': '피로', 'pol': '+', 'detail': '피곤해요'}]
        out = facts.item_filter(enc, rows, llm)
        self.assertEqual([f['label'] for f in out], ['피로'])
        enc.facts = out
        self.assertTrue(self._anv(note2.render_fixed(enc, {})).endswith('/ )'))   # Constipation 빈칸

    def test_precise_item_match(self):
        # '체중'이 두 항목에 겹쳐도 가장 잘 맞는 항목으로 판정
        led = [say(6, '살이 빠지거나 찌진 않았나요?', '빠지진 않았어요.',
                   [it('gr_wt_loss', '체중 감소', True, '-', '빠지|빠졌'), it('gr_wt_gain', '체중 증가', False, '?', '찌|쪘')])]
        enc = FakeEnc(led)
        out = facts.item_filter(enc, facts.qa_rows(enc), [
            {'turn': 6, 'sec': 'hpi', 'key': 'other', 'label': '체중 감소', 'pol': '-', 'detail': ''},
            {'turn': 6, 'sec': 'hpi', 'key': 'other', 'label': '체중 증가', 'pol': '-', 'detail': ''}])
        self.assertEqual([f['label'] for f in out], ['체중 감소'])

    def test_generic_negative_covers_all(self):
        for reply in ('아니요, 그런 병은 없어요.', '그런 건 없어요.', '둘 다 없어요.'):
            led = [say(7, '고혈압이나 당뇨 있으세요?', reply,
                       [it('pmh_htn', '고혈압', False, '?', '혈압'), it('pmh_dm', '당뇨', False, '?', '당뇨')])]
            enc = FakeEnc(led, sex='F', age=50, pediatric=False)
            rows = facts.qa_rows(enc)
            self.assertTrue(all(j['answered'] and j['pol'] == '-' for j in rows[0]['items']), reply)
            enc.facts = facts.fallback(enc, rows)
            self.assertIn('DM / HTN (-/-)', note2.render_fixed(enc, {})['pmh'], reply)

    def test_generic_regex_requires_negation(self):
        self.assertIsNone(facts.GENERIC_NEG_RE.search('둘 다 있어요.'))
        self.assertIsNone(facts.GENERIC_NEG_RE.search('네, 모두 있어요.'))
        self.assertIsNotNone(facts.GENERIC_NEG_RE.search('둘 다 아니에요.'))
        self.assertIsNotNone(facts.GENERIC_NEG_RE.search('아니요, 그런 적은 없어요.'))
        row = {'a': '천식은 있고 그런 건 없어요.',
               'items': [it('pmh_asthma', '천식', True, '+', '천식'), it('pmh_admit', '입원력', False, '?', '입원')]}
        eff = facts.effective_items(row)
        self.assertFalse(eff[1]['answered'])   # 양성이 섞인 답은 포괄 음성으로 넓히지 않음

    def test_unanswered_fixed_key_blank_not_negative(self):
        led = [say(9, '입원하거나 수술한 적 있나요?', '입원한 적은 없어요.',
                   [it('pmh_admit', '입원력', True, '-', '입원'), it('pmh_op', '수술력', False, '?', '수술')])]
        enc = FakeEnc(led, sex='F', age=40, pediatric=False)
        rows = facts.qa_rows(enc)
        out = facts.item_filter(enc, rows, [
            {'turn': 9, 'sec': 'hpi', 'key': 'other', 'label': '입원력', 'pol': '-', 'detail': ''},
            {'turn': 9, 'sec': 'pmh', 'key': 'pmh.op_hx', 'label': '수술력', 'pol': '-', 'detail': ''}])
        self.assertEqual([(f['label'], f['sec']) for f in out], [('입원력', 'pmh')])   # 입원력 → S pmh
        enc.facts = out
        pmh = note2.render_fixed(enc, {})['pmh']
        self.assertIn('Op. Hx ( )', pmh)
        self.assertIn('입원력(-)', pmh)

    def test_answered_negative_fixed_and_supplement(self):
        led = [say(9, '입원하거나 수술한 적 있나요?', '둘 다 없어요.',
                   [it('pmh_admit', '입원력', True, '-', '입원'), it('pmh_op', '수술력', True, '-', '수술')]),
               say(10, '알레르기나 천식 있나요?', '알레르기는 없어요.',
                   [it('pmh_allergy', '알레르기', True, '-', '알레르기|알러지'), it('pmh_asthma', '천식', False, '?', '천식')])]
        enc = FakeEnc(led, sex='F', age=40, pediatric=False)
        out = facts.item_filter(enc, facts.qa_rows(enc), [])   # LLM이 모두 놓쳐도 항목 판정으로 보충
        keys = {(f['label'], f['key'], f['sec'], f['pol']) for f in out}
        self.assertIn(('수술력', 'pmh.op_hx', 'pmh', '-'), keys)
        self.assertIn(('입원력', 'other', 'pmh', '-'), keys)
        self.assertIn(('알레르기', 'pmh.allergy', 'pmh', '-'), keys)
        self.assertFalse(any(f['label'] == '천식' for f in out))
        enc.facts = out
        pmh = note2.render_fixed(enc, {})['pmh']
        self.assertIn('Op. Hx (-)', pmh)
        self.assertIn('Allergy (-)', pmh)
        self.assertIn('입원력(-)', pmh)

    def test_fallback_sec_for_keyless_pmh_items(self):
        led = [say(11, '천식이나 입원한 적 있나요?', '그런 건 없어요.',
                   [it('pmh_asthma', '천식', False, '?', '천식'), it('pmh_admit', '입원력', False, '?', '입원')])]
        enc = FakeEnc(led, sex='F', age=40, pediatric=False)
        fb = facts.fallback(enc, facts.qa_rows(enc))
        self.assertEqual({(f['label'], f['sec'], f['pol']) for f in fb}, {('천식', 'pmh', '-'), ('입원력', 'pmh', '-')})

    def test_smoking_bundle_item_fills_fixed(self):
        led = [say(12, '담배나 술은 하세요?', '담배는 안 피워요.',
                   [it('sh_smoke', '흡연', True, '-', '담배|흡연|피우|피워'), it('sh_alcohol', '음주', False, '?', '술|마시')],
                   qid='sh_smoke_alc')]
        enc = FakeEnc(led, sex='M', age=40, pediatric=False)
        sh = note2.render_fixed(enc, {})['sh']
        self.assertIn('Smoking (-)', sh)
        self.assertIn('Alcohol ( )', sh)

    def test_explain_phases_to_s(self):
        led = [say(26, '체질성 성장지연 가능성이 높아요.', '그럼 나중에 다 크나요?', phase='explain'),
               say(27, '네, 대개 늦게 따라잡아요.', '검사는 언제 하나요?', phase='explain-answer'),
               say(28, '더 궁금하신 점 있으세요?', '성장호르몬 주사는 안 맞아도 되나요?', phase='explain-extra'),
               say(29, '6개월마다 키를 재요.', '네, 알겠습니다.', phase='explain'),
               say(30, '말씀해 보시겠어요?', '두통이 있으면 바로 와요?', phase='explain-teachback')]
        rows = facts.qa_rows(FakeEnc(led))
        self.assertEqual([(r['turn'], r['slot']) for r in rows], [(26, 'ice_q'), (27, 'ice_q'), (28, 'ice_q')])

    def test_safety_items_generic_negative(self):
        led = [say(8, '끊었을 때 경련이나 헛것이 있었나요?', '그런 건 없었어요.',
                   [it('sb_seizure', '금단 경련', False, '?', '경련'), it('sb_delirium', '금단 환각', False, '?', '헛것')])]
        led[0]['safety'] = True
        items = record._safety_items(FakeEnc(led))
        self.assertEqual({k: v[0] for k, v in items.items()}, {'sb_seizure': '-', 'sb_delirium': '-'})


if __name__ == '__main__':
    unittest.main()

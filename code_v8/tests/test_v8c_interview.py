"""v8c 문진·진찰 결함 수정 테스트(개발 키·네트워크 없음): 묶음 규칙(A), LLM 문항 관련성(B), 필수 공통 병력(C),
미응답 항목(D), 진찰 계획·여유 진찰(E). 가짜 서버 하네스는 test_v8에서 가져온다."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import test_v8 as T  # noqa: E402
from agent import cpx, interview  # noqa: E402

P10 = {'age': 32, 'sex': 'F', 'pediatric': False, 'categories': ['weight_loss']}
P01 = {'age': 62, 'sex': 'F', 'pediatric': False, 'categories': ['insomnia', 'substance'], 'request': '수면제 처방'}
P03 = {'age': 6, 'sex': 'M', 'pediatric': True, 'informant': '어머님', 'categories': ['growth']}


def chosen_ids(prof, opening, covered=(), budget=17):
    chosen, _ = cpx.compile_units(cpx.build(prof, opening)['units'], budget, covered=covered)
    return [u['id'] for u in chosen]


# ---------------------------------------------------------------- A. 묶음 규칙
class TestBundleRule(unittest.TestCase):
    def test_every_bank_unit_ok(self):
        for u in cpx.all_bank_units():
            self.assertEqual(cpx.bundle_violation(u), '', (u['id'], u['q']))
            self.assertLessEqual(T.nlen(u['q']), 30, u['q'])

    def test_violations_detected(self):
        cross = cpx.U('x', 'red', 1, '두통이나 시야 이상은요?', [('a', '두통', '두통'), ('b', '시야', '시야')], 'neuro',
                      isys=['neuro', 'eye'])
        self.assertEqual(cpx.bundle_violation(cross), 'cross_system')
        three = cpx.U('y', 'red', 1, '복통이나 구토, 혈변은 없나요?', [('a', 'a', 'a'), ('b', 'b', 'b'), ('c', 'c', 'c')], 'gi')
        self.assertTrue(cpx.bundle_violation(three))
        hx3_safety = cpx.U('z', 'hx', 1, '천식이나 심장병, 콩팥병 있나요?',
                           [cpx.I_ASTHMA, cpx.I_HEART, ('pmh_kidney', '콩팥', '콩팥')], 'hx')
        self.assertEqual(cpx.bundle_violation(hx3_safety), 'hx3_safety')
        sleep_psy = cpx.U('w', 'core', 1, '잠을 설치거나 불안하세요?', [('a', 'a', 'a'), ('b', 'b', 'b')], 'psy',
                          isys=['sleep', 'psy'])
        self.assertEqual(cpx.bundle_violation(sleep_psy), '')

    def test_fixed_units(self):
        units = {u['id']: u for u in cpx.all_bank_units()}
        self.assertEqual(units['wl_gi_red']['q'], '배가 아프거나 토하세요?')
        self.assertEqual(units['wl_hemato']['q'], '변에 피가 섞인 적 있나요?')
        self.assertEqual(units['wl_hx']['q'], '심장병이나 갑상선 질환 있으세요?')
        self.assertEqual(units['wl_weak']['q'], '기운이 없거나 쉽게 지치세요?')
        self.assertEqual(units['cp_assoc']['q'], '아플 때 숨이 같이 차나요?')
        self.assertTrue(units['cp_assoc']['safety'])
        self.assertEqual(units['dz_neuro']['q'], '말이 어눌하거나 얼굴이 처지나요?')
        self.assertEqual(units['gr_hypo']['q'], '잘 지치거나 추위를 타나요?')
        self.assertEqual(units['gr_ich']['q'], '머리가 자주 아프다고 하나요?')
        self.assertEqual(units['gr_chronic']['kind'], 'hx3')

    def test_check_question_reject(self):
        for q in ('복통이나 구토, 혈변은 없나요?', '잘 지치거나 변비, 추위 타나요?', '두통이나 구토, 시야 이상은요?',
                  '갑상선 질환이나 천식·심장병 있으세요?', '두통이나 시야 이상이 있나요?'):
            self.assertFalse(cpx.check_question(q)[0], q)

    def test_check_question_accept(self):
        for q in ('식사량이나 입맛은 예전과 어떠세요?', '가족과 약 문제로 갈등이 있나요?', '고혈압이나 당뇨 있으세요?',
                  '기분이 가라앉거나 죽고 싶은 적 있나요?', '잠을 설치거나 불안하세요?', '약 알레르기나 천식 있으세요?'):
            self.assertTrue(cpx.check_question(q)[0], (q, cpx.check_question(q)))
        self.assertEqual(cpx.count_items('식사량이나 입맛은 예전과 어떠세요?'), 2)
        self.assertEqual(cpx.count_items('가족과 약 문제로 갈등이 있나요?'), 1)

    def test_item_q_single(self):
        for iid in ('pmh_admit', 'pmh_op', 'pmh_allergy', 'pmh_asthma', 'dz_face', 'ros_abd', 'gr_vision'):
            q = cpx.ITEM_Q[iid]
            self.assertLessEqual(T.nlen(q), 30)
            self.assertEqual(cpx.count_items(q), 1, q)


# ---------------------------------------------------------------- B. LLM 문항 관련성
class FakeEncLLM:
    def __init__(self, prof, llm):
        self.profile = prof
        self.cpx_llm = llm


class TestRelevance(unittest.TestCase):
    C03_BAD = ('잠을 못 자고 스트레스를 많이 받는다고 느끼시나요?', '가슴이 답답하거나 호흡이 힘드시나요?',
               '1년간 평균 월간 키 증가가 1cm 이하인가요?')

    def test_c03_examples_rejected(self):
        built = cpx.build(P03, T.C03)
        sys_ = cpx.category_systems(built, P03)
        for q in self.C03_BAD:
            self.assertFalse(cpx.relevant_question(q, sys_, peds=True)[0], q)

    def test_relevant_accepts_in_category(self):
        built = cpx.build(P10, T.C10)
        sys_ = cpx.category_systems(built, P10)
        self.assertTrue(cpx.relevant_question('목이 아프거나 누르면 아픈가요?', sys_)[0])
        self.assertTrue(cpx.relevant_question('천식이나 심장병 있으세요?', sys_)[0])
        self.assertFalse(cpx.relevant_question('체중이 5kg 이상 빠졌나요?', sys_)[0])

    def test_bank_drops_discriminators_and_peds_contra(self):
        llm = {'discriminators': [{'q': q, 'label': 'x', 'sys': 'gen'} for q in self.C03_BAD],
               'contra': [{'q': '가슴이 답답하거나 호흡이 힘드시나요?', 'label': '호흡', 'sys': 'hx'}]}
        built = cpx.build(P03, T.C03)
        out = interview._llm_units(FakeEncLLM(P03, llm), built['units'], True, built)
        self.assertEqual(out, [])

    def test_bank_adult_contra_prio3(self):
        llm = {'discriminators': [{'q': '목이 아프거나 누르면 아픈가요?', 'label': '목 압통', 'sys': 'neck'}],
               'contra': [{'q': '녹내장 진단받은 적 있나요?', 'label': '녹내장', 'sys': 'hx'}]}
        built = cpx.build(P10, T.C10)
        out = interview._llm_units(FakeEncLLM(P10, llm), built['units'], True, built)
        self.assertEqual([u['id'] for u in out], ['llm_contra0'])
        self.assertEqual(out[0]['prio'], 3)

    def test_nonbank_applies_relevance(self):
        prof = {'age': 40, 'sex': 'M', 'pediatric': False, 'categories': ['msk'], 'cc': '허리 통증'}
        built = cpx.build(prof, '허리가 아파서 왔어요.')
        llm = {'discriminators': [{'q': '1년간 평균 키 증가가 1cm 이하인가요?', 'label': '키', 'sys': 'gen'}], 'contra': []}
        out = interview._llm_units(FakeEncLLM(prof, llm), built['units'], False, built)
        self.assertEqual(out, [])


# ---------------------------------------------------------------- C. 필수 공통 병력
ADULT_MUST_Q = ('입원이나 수술한 적 있으세요?', '약 알레르기나 천식 있으세요?', '가족 중 갑상선병 있는 분 있나요?',
                '담배나 술은 하세요?', '혹시 임신 가능성은 있으세요?', '드시는 약이나 영양제 있으세요?', '혹시 걱정되는 병이 있으세요?')


class TestMandatory(unittest.TestCase):
    def test_must_flags(self):
        b = cpx.build(P10, T.C10)
        must = {u['id'] for u in b['units'] if cpx.is_must(u)}
        self.assertEqual(must, {'hx_admit_op', 'hx_allergy', 'wl_fh', 'sh_smoke_alc', 'wm_preg', 'hx_meds', 'ice'})
        b = cpx.build(P01, T.C01)
        must = {u['id'] for u in b['units'] if cpx.is_must(u)}
        self.assertEqual(must, {'hx_admit_op', 'hx_allergy', 'fh_open', 'sh_alc_smoke', 'sb_meds2', 'ice'})
        fh = next(u for u in b['units'] if u['id'] == 'fh_open')
        self.assertEqual(fh['prio'], 1)   # substance 'demote' 면역
        b = cpx.build(P03, T.C03)
        must = {u['id'] for u in b['units'] if cpx.is_must(u)}
        self.assertEqual(must, {'p_admit_op', 'p_allergy', 'gr_fh', 'ice'})

    def test_own_asthma_uses_allergy_only(self):
        b = cpx.build({'age': 50, 'sex': 'M', 'pediatric': False, 'categories': ['dyspnea']}, '숨이 차서 왔어요.')
        al = next(u for u in b['units'] if u['id'] == 'hx_allergy')
        self.assertEqual(al['q'], '약 알레르기 있으세요?')
        b = cpx.build({'age': 50, 'sex': 'M', 'pediatric': False, 'categories': ['cough_fever']}, '기침이 나요.')
        ids = {u['id'] for u in b['units']}
        self.assertIn('cf_hx', ids)              # 알레르기+천식을 덮는 범주 단위로 대체
        self.assertNotIn('hx_allergy', ids)
        self.assertTrue(next(u for u in b['units'] if u['id'] == 'cf_hx')['must'])

    def test_must_never_victim(self):
        b = cpx.build(P10, T.C10)
        chosen, _ = cpx.compile_units(b['units'], 8)
        ids = {u['id'] for u in chosen}
        self.assertTrue({'hx_admit_op', 'hx_allergy', 'wl_fh', 'sh_smoke_alc', 'wm_preg', 'hx_meds', 'ice'} <= ids)

    def test_chosen_c10(self):
        ids = chosen_ids(P10, T.C10, covered={'ros_palp'})   # 개방형 답 '가슴이 자주 두근거려요'
        want = {'wl_intake', 'wl_heat', 'wl_tremor', 'wl_bowel', 'wl_eye', 'wl_neck', 'wl_cycle', 'wl_sleep', 'wl_fever',
                'wl_cardio', 'hx_admit_op', 'hx_allergy', 'wl_fh', 'sh_smoke_alc', 'wm_preg', 'hx_meds', 'ice'}
        self.assertEqual(set(ids), want)
        self.assertEqual(ids[-1], 'ice')

    def test_chosen_c01(self):
        ids = set(chosen_ids(P01, T.C01))
        want = {'hpi_onset', 'sb_name', 'sb_dose_now', 'sb_tol', 'sb_withdraw', 'sb_cutdown', 'sb_seizure', 'sb_sources',
                'sb_other', 'sb_last', 'ps_mood_si', 'sb_meds2', 'hx_admit_op', 'hx_allergy', 'fh_open', 'sh_alc_smoke', 'ice'}
        self.assertEqual(ids, want)

    def test_chosen_c03(self):
        ids = set(chosen_ids(P03, T.C03))
        want = {'p_admit_op', 'p_allergy', 'gr_fh', 'p_perinatal', 'p_develop', 'gr_parents', 'gr_late', 'gr_puberty',
                'gr_hypo', 'gr_ich', 'gr_chronic', 'gr_steroid', 'ice'}
        self.assertTrue(want <= ids, want - ids)
        self.assertEqual(len(ids), 17)

    def test_dry_run_sets(self):
        s = T.says(T.run_case('C10', T.C10))
        for q in ADULT_MUST_Q + ('잠을 설치거나 불안하세요?', '최근 열이나 감기 기운이 있었나요?', '생리 양이나 기간이 변했나요?',
                                 '가슴 통증이나 숨찬 증상 있으세요?', '목이 붓거나 혹이 만져지나요?'):
            self.assertIn(q, s)
        s = T.says(T.run_case('C01', T.C01))
        for q in ('입원이나 수술한 적 있으세요?', '약 알레르기나 천식 있으세요?', '부모님이나 형제분 앓는 병 있나요?',
                  '술이나 담배는 하세요?', '끊었을 때 경련이나 헛것이 있었나요?', '마지막으로 언제 몇 알 드셨어요?'):
            self.assertIn(q, s)
        s = T.says(T.run_case('C03', T.C03))
        for q in ('입원이나 수술한 적 있나요?', '알레르기 있는 게 있나요?', '가족 중 키가 작거나 유전병 있나요?',
                  '임신이나 출산 때 문제가 있었나요?', '말이나 걷기는 또래만큼 했나요?', '잘 지치거나 추위를 타나요?',
                  '머리가 자주 아프다고 하나요?', '천식이나 장, 콩팥 질환 들은 적 있나요?', '스테로이드나 한약 먹은 적 있나요?'):
            self.assertIn(q, s)

    def test_all_positive_patient_asks_every_must(self):
        def pos(content):
            if '궁금하신 점' in content:
                return '치료 기간이 궁금해요?'
            return '네, 있어요.' if content.endswith('?') else '네, 알겠습니다.'
        c = T.run_case('C10', T.C10, patient=pos)
        s = T.says(c)
        self.assertLessEqual(c.turns, 34)
        for q in ADULT_MUST_Q:
            self.assertIn(q, s)

    def test_dry_runs_limits(self):
        for case, op in (('C10', T.C10), ('C01', T.C01), ('C03', T.C03)):
            c = T.run_case(case, op)
            self.assertLessEqual(c.turns, 34, case)
            self.assertEqual(T.run.LAST_RUN['counts']['refused'], 0, case)
            self.assertTrue(all(T.nlen(x) <= 30 for x in T.says(c)), case)


# ---------------------------------------------------------------- D. 미응답 항목
class TestUnanswered(unittest.TestCase):
    def test_pair_partial(self):
        r = cpx.judge([cpx.I_HEART, cpx.I_THY], '갑상선 질환은 없어요')
        self.assertEqual([(o['answered'], o['pol']) for o in r], [(False, '?'), (True, '-')])

    def test_hx3_generic_negative(self):
        items = [cpx.I_ASTHMA, ('gr_gi', '장 질환', r'장'), ('gr_kidney', '콩팥 질환', r'콩팥|신장')]
        for a in ('아니요, 그런 병은 없어요', '천식이나 장, 콩팥 질환은 없어요', '둘 다 없어요'):
            r = cpx.judge(items, a)
            self.assertTrue(all(o['answered'] and o['pol'] == '-' for o in r), (a, r))

    def test_list_negation_mixed(self):
        items = [cpx.I_ASTHMA, ('gr_gi', '장 질환', r'장'), ('gr_kidney', '콩팥 질환', r'콩팥|신장')]
        r = cpx.judge(items, '천식은 있고, 장이나 콩팥은 없어요')
        self.assertEqual([o['pol'] for o in r], ['+', '-', '-'])

    def test_generic_pair(self):
        for a in ('그런 건 없어요', '둘 다 없어요'):
            r = cpx.judge([cpx.I_HTN, cpx.I_DM], a)
            self.assertTrue(all(o['answered'] and o['pol'] == '-' for o in r), a)


# ---------------------------------------------------------------- E. 진찰
class TestExam(unittest.TestCase):
    def test_c10_exam_plan(self):
        c = T.run_case('C10', T.C10)
        exams = [e[1] for e in c.events if e[0] == 'EXAM']
        self.assertEqual(exams, ['활력징후 측정하겠습니다', '갑상선 촉진하겠습니다', '갑상선 안징후 검사하겠습니다',
                                 '자세성 떨림 확인하겠습니다', '심음 청진하겠습니다', '폐 청진하겠습니다',
                                 '피부 온도·발한 촉진하겠습니다'])

    def test_vitals_first_and_backlog(self):
        for case, op in (('C01', T.C01), ('C03', T.C03)):
            c = T.run_case(case, op)
            exams = [e[1] for e in c.events if e[0] == 'EXAM']
            self.assertEqual(exams[0], '활력징후 측정하겠습니다', case)
            self.assertEqual(len(exams), 7, case)

    def test_cardio_positive_pulls_heart_lung(self):
        enc = _ExamEnc({'age': 40, 'sex': 'M', 'pediatric': False, 'categories': ['headache']}, '머리가 아파요.')
        enc.cpx.status['ros_dysp'] = {'pol': '+', 'turn': 3, 'how': 'asked'}
        order = interview.exam_plan_v8(enc)
        self.assertEqual(order[0], 'vitals')
        self.assertIn('heart', order[:7])
        self.assertIn('lung', order[:7])
        enc2 = _ExamEnc({'age': 40, 'sex': 'M', 'pediatric': False, 'categories': ['headache']}, '머리가 아파요.')
        self.assertNotIn('heart', interview.exam_plan_v8(enc2)[:7])

    def test_examine_fills_when_interview_short_and_spare_exam(self):
        enc = _ExamEnc(P10, T.C10, turns=20)
        enc.counts['interview'] = 15          # 문진 2턴 덜 씀 → 진찰 2개 더
        interview.examine_v8(enc)
        self.assertEqual(enc.done_exams[:7], ['vitals', 'thyroid', 'eye_signs', 'post_tremor', 'heart', 'lung', 'skin_temp'])
        self.assertEqual(len(enc.done_exams), 9)
        self.assertEqual(enc.exam_backlog[0], 'power')
        enc.blacklist.add('power')
        self.assertTrue(interview.spare_exam(enc))
        self.assertEqual(enc.done_exams[-1], 'radial')
        self.assertTrue(enc.ledger[-1].get('system'))
        enc.exam_backlog = []
        self.assertFalse(interview.spare_exam(enc))

    def test_examine_stops_at_reserve(self):
        enc = _ExamEnc(P10, T.C10, turns=12)
        interview.examine_v8(enc)
        self.assertEqual(len(enc.done_exams), 12 - 9)


class _ExamEnc:
    """examine_v8용 최소 Encounter: act가 턴을 하나씩 쓴다."""

    def __init__(self, prof, opening, turns=16):
        self.profile = dict(prof)
        self.opening = opening
        self.vitals = T.VITALS
        self.cfg = T.run.load_config()
        self.cfg.update({'EXAM_N': 7, 'EXPLAIN_MIN': 7, 'ANSWER_RESERVE': 2, 'INTERVIEW_Q': 17})
        self.differentials = []
        self.turns_remaining = turns
        self.counts = {'interview': 17}
        self.blacklist, self.done_exams, self.ledger = set(), [], []
        built = cpx.build(self.profile, opening)
        self.cpx = interview.CpxState(built, [], [])

    def can_act(self):
        return self.turns_remaining > 0

    def act(self, kind, text, *, phase, qid='', label=''):
        self.turns_remaining -= 1
        e = {'kind': kind, 'text': text, 'reply': '특이 소견(-)', 'phase': phase, 'qid': qid}
        self.ledger.append(e)
        return e


if __name__ == '__main__':
    unittest.main()

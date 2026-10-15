"""v8c 설명 단계 테스트: 되말하기 폐지·명시적 턴 회계·환자 질문 답·슬롯 품질 게이트·조사 띄어쓰기(개발 키·네트워크 없음).

실행: env -u NOVA_DEV_KEY python -m pytest -q code_v8/tests/test_v8c_explain.py
"""
import os
import re
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import run  # noqa: E402
from agent import explain, interview, kb as kbmod, say as saymod  # noqa: E402
from test_v8 import C01, C03, C10, CASE_Q, FakeClient, FakeEnc, nlen  # noqa: E402

CASES = (('C10', C10), ('C01', C01), ('C03', C03))
TEST_WORD_RE = re.compile(r'(검사|피검사|초음파|심전도|엑스레이|혈액|소변|MRI|CT)')


def run_with(client):
    with mock.patch.dict(os.environ, {'NOVA_AGENT_GUIDE': '0'}):
        state = run.prepare()
        run.consult(client, state)
    return client


class QClient(FakeClient):
    """첫 설명 문장에 대한 환자 답을 바꾼다(explain_q='first'일 때)."""
    first_reply = '네, 알겠습니다. 다음 검사는 어떤 게 필요할까요?'

    def reply(self, content):
        r = super().reply(content)
        if r == '치료하면 좋아질 수 있나요?':
            return self.first_reply
        return r


def doctor_says(c):
    return [e[1] for e in c.events if e[0] == 'SAY']


def explain_ledger():
    return [e for e in run.LAST_RUN['ledger'] if str(e.get('phase', '')).startswith('explain')]


# ---------------------------------------------------------------- 조사 띄어쓰기
class TestTidy(unittest.TestCase):
    def test_particles_attached(self):
        self.assertEqual(saymod.tidy('피검사·초음파 를 2주 뒤 결과 보고 와요.'), '피검사·초음파를 2주 뒤 결과 보고 와요.')
        self.assertEqual(saymod.tidy('갑상샘 호르몬 을 확인해요.'), '갑상샘 호르몬을 확인해요.')
        self.assertEqual(saymod.tidy('손 엑스레이 로 뼈 나이를 봐요.'), '손 엑스레이로 뼈 나이를 봐요.')
        self.assertEqual(saymod.tidy('혈액검사 로 확인해요.'), '혈액검사로 확인해요.')
        self.assertEqual(saymod.tidy('결과 는 2주 뒤 봐요.'), '결과는 2주 뒤 봐요.')
        self.assertEqual(saymod.tidy('MRI 를 찍어요.'), 'MRI를 찍어요.')
        self.assertEqual(saymod.tidy('그레이브스병 이 의심돼요 .'), '그레이브스병이 의심돼요.')

    def test_untouched(self):
        for s in ('검사 후 2주 뒤 봐요.', '피검사 하고 2주 뒤 결과 봐요.', '약은 이 정도로 드세요.',
                  '숨참·불규칙한 맥·고열·혼동 시 바로 오세요.', '1~2주 뒤 결과 보고 약을 정해요.', '더 궁금하신 점 있으세요?'):
            self.assertEqual(saymod.tidy(s), s)

    def test_safe_say_applies_tidy(self):
        self.assertEqual(explain.safe_say('피검사·초음파 를 2주 뒤 결과 보고 와요.'), '피검사·초음파를 2주 뒤 결과 보고 와요.')


# ---------------------------------------------------------------- 슬롯 품질 게이트
class TestSlotGate(unittest.TestCase):
    DX = {'C10': '그레이브스병에 의한 갑상샘항진증', 'C01': '수면제(진정수면제) 사용장애', 'C03': '체질성 성장지연'}

    def test_c03_nonsense_mech_fails(self):
        self.assertTrue(saymod.slot_problem('mech', '피로에 힘들어하고 언어도 정상이에요.', self.DX['C03']))
        self.assertTrue(saymod.slot_problem('mech', '키가 작고 성장 속도는 정상이에요.', self.DX['C03']))

    def test_good_examples_pass(self):
        good = [('dx', '많이 걱정되셨죠, 그레이브스병 가능성이 높아요.', 'C10'),
                ('mech', '면역 이상으로 호르몬이 넘쳐 살 빠지고 떨려요.', 'C10'),
                ('mech', '몸이 약에 익숙해져 양이 늘고 끊기 힘든 거예요.', 'C01'),
                ('mech', '뼈 나이가 늦으면 늦게까지 자랄 수 있어요.', 'C03'),
                ('worry', '목·눈 소견이 뚜렷해 암보다 갑상샘 병 같아요.', 'C10'),
                ('tests', '피검사·초음파로 원인 확인하고 2주 뒤 봐요.', 'C10'),
                ('treat', '베타차단제로 두근거림 줄이고 약은 1~2년 써요.', 'C10'),
                ('treat', '약은 갑자기 끊지 말고 천천히 줄여요.', 'C01'),
                ('warn', '열·목 아픔·숨참·심한 두근거림 땐 바로 오세요.', 'C10'),
                ('life', '2주 뒤 오시고 커피는 줄여 주세요.', 'C10'),
                ('life', '졸릴 땐 운전과 위험한 일은 피하세요.', 'C01')]
        for slot, text, case in good:
            self.assertEqual(saymod.slot_problem(slot, text, {'dx': self.DX[case]}), '', (slot, text))

    def test_bad_examples_fail(self):
        bad = [('dx', '많이 걱정되셨죠, 검사가 필요해요.'), ('tests', '피검사 하고 2주 뒤 결과 봐요.'),
               ('tests', '원인을 확인해요.'), ('treat', '2주 뒤 결과 봐요.'), ('warn', '열 나면 바로 오세요.'),
               ('worry', '호르몬이 넘쳐요.'), ('life', '그레이브스병이에요.'), ('mech', '그레이브스병 가능성이 높아요?')]
        for slot, text in bad:
            self.assertTrue(saymod.slot_problem(slot, text, self.DX['C10']), (slot, text))

    def test_say_slots(self):
        self.assertEqual([k for k, _ in explain.say_slots(6)], ['dx', 'mech', 'worry', 'tests', 'treat', 'warn'])
        self.assertEqual([k for k, _ in explain.say_slots(7)], ['dx', 'mech', 'worry', 'tests', 'treat', 'warn', 'life'])
        self.assertEqual([k for k, _ in explain.say_slots(5)], ['dx', 'mech', 'worry', 'tests', 'warn'])
        self.assertEqual([k for k, _ in explain.say_slots(3)], ['dx', 'tests', 'warn'])
        self.assertEqual(saymod.SLOT_PRIO, {'life': 10, 'mech': 20, 'worry': 30, 'treat': 60, 'tests': 70, 'warn': 90,
                                            'dx': 100})

    def test_templates_pass_say_problem(self):
        """슬롯별 결정적 폴백(KB·진단·양성 사실)에 say_problem·slot_problem을 통과하는 후보가 늘 있다."""
        for case, dx in self.DX.items():
            enc = FakeEnc([{'turn': 18, 'kind': 'SAY', 'text': '걱정되는 병이 있으세요?', 'reply': '혹시 암일까 봐 걱정돼요.',
                            'qid': 'ice', 'phase': 'interview'}])
            enc.dx = dx
            enc.facts = [{'label': '두근거림', 'pol': '+', 'detail': ''}, {'label': '손떨림', 'pol': '+', 'detail': ''}]
            k = kbmod.match_kb(dx)
            for slot, _ in explain.SAY_SLOTS:
                cands = [explain.safe_say(c) for c in explain.slot_candidates(slot, enc, k, {}) if c]
                ok = [c for c in cands if not saymod.slot_problem(slot, c, enc)]
                self.assertTrue(ok, (case, slot, cands))
                self.assertLessEqual(nlen(ok[0]), 30)

    def test_build_slot_lines_fallback(self):
        """LLM 문장이 게이트를 못 넘고 고쳐 쓰기도 실패하면 템플릿으로 채우고, 재진 시점이 꼭 들어간다."""
        enc = FakeEnc([])
        enc.dx = '체질성 성장지연'
        enc.budget = mock.Mock(can_call=lambda *_: False)
        k = kbmod.match_kb(enc.dx)
        raw = ['걱정 많으셨죠, 체질성 성장지연 가능해요.', '피로에 힘들어하고 언어도 정상이에요.', '키가 걱정되시죠.',
               '골연령, 갑상선, 성장호르몬 검사를 할게요.', '지켜봐요.', '두통·구토·시야 변화·목 거름·발진이면 바로 오세요.']
        keys = [s for s, _ in explain.say_slots(6)]
        out = explain.build_slot_lines(enc, raw, keys, k, {})
        slots = [s for s, _, _ in out]
        self.assertEqual(slots, keys)
        for slot, text, _ in out:
            self.assertEqual(saymod.slot_problem(slot, text, enc), '', (slot, text))
        self.assertNotIn('피로에 힘들어하고 언어도 정상이에요.', [t for _, t, _ in out])
        self.assertTrue(any(saymod.FOLLOWUP_RE.search(t) for _, t, _ in out))


class TestQuestionDetect(unittest.TestCase):
    def test_ack_then_question(self):
        self.assertTrue(explain.is_question('네, 알겠습니다. 다음 검사는 어떤 게 필요할까요?'))
        self.assertTrue(explain.is_question('네, 알겠습니다. 가슴이 두근거리는 건 있나요?'))
        self.assertFalse(explain.is_question('네, 알겠습니다.'))
        self.assertFalse(explain.is_question('아니요, 없어요. 감사합니다.'))
        self.assertFalse(explain.is_question('언제든 올게요.'))

    def test_generic_answers_valid(self):
        for g in explain.GENERIC_ANSWERS:
            self.assertFalse(saymod.say_problem(g), g)
            self.assertEqual(explain.safe_say(g), g)
        self.assertFalse(saymod.say_problem(explain.SUMMARY_LINE))


# ---------------------------------------------------------------- explain_loop_v8 턴 회계(단위)
class SimEnc:
    """턴 상한만 있는 가짜 Encounter. reply_fn(text) → 환자 답."""

    def __init__(self, turns, reply_fn, dx='그레이브스병에 의한 갑상샘항진증'):
        self.turns_remaining = turns
        self.turn = 34 - turns
        self.cfg = {'TURN_CAP': 34, 'EFFORT_ANSWER': 'low', 'CALL_RESERVE': 0}
        self.reply_fn = reply_fn
        self.dx = dx
        self.explained = []
        self.log = []
        self.plan_v2 = {}
        self.client = None
        self.budget = None

    def can_act(self):
        return self.turns_remaining > 0 and self.turn < 34

    def act(self, kind, text, *, phase, qid='', label=''):
        if not self.can_act():
            return None
        self.turn += 1
        self.turns_remaining -= 1
        r = self.reply_fn(text) if kind == 'SAY' else '특이 소견(-)'
        e = {'turn': self.turn, 'kind': kind, 'text': text, 'reply': r, 'phase': phase}
        self.log.append(e)
        return e


LINES = ['많이 걱정되셨죠, 그레이브스병 가능성이 높아요.', '면역 이상으로 호르몬이 넘쳐 살 빠지고 떨려요.',
         '목·눈 소견이 뚜렷해 암보다 갑상샘 병 같아요.', '피검사·초음파로 원인 확인하고 2주 뒤 봐요.',
         '베타차단제로 두근거림 줄이고 약은 1~2년 써요.', '열·목 아픔·숨참·심한 두근거림 땐 바로 오세요.',
         '2주 뒤 오시고 커피는 줄여 주세요.', saymod.QUESTION_LINE]
SLOTS = ['dx', 'mech', 'worry', 'tests', 'treat', 'warn', 'life']


def _loop(enc, lines=LINES, faq=None, spare=None):
    enc.say_slot_of = dict(zip(lines, SLOTS))
    enc.say_keep = []
    with mock.patch.object(explain, '_answer_llm', return_value='치료하면 대개 체중도 회복돼요.'), \
            mock.patch.object(interview, 'spare_exam', spare, create=True):
        explain.explain_loop_v8(enc, list(lines), faq or {'duration': '약은 보통 1~2년 정도 드셔요.'})
    return enc.log


class TestLoopAccounting(unittest.TestCase):
    def test_no_question_spare_turn_no_teachback(self):
        enc = SimEnc(9, lambda t: '네, 알겠습니다.')
        log = _loop(enc)
        texts = [e['text'] for e in log]
        self.assertNotIn(explain.TEACH_BACK, texts)
        self.assertEqual(texts[:7], LINES[:7])
        self.assertEqual(texts[7], saymod.QUESTION_LINE)
        self.assertEqual(len(log), 9)           # 남는 마지막 턴도 정보(KB 없음 → 오늘 요약)로 쓴다
        self.assertEqual(texts[8], explain.SUMMARY_LINE)
        self.assertEqual(enc.turn, 34)

    def test_mid_question_answered_next_turn(self):
        def rf(t):
            if t == LINES[0]:
                return '네, 알겠습니다. 치료하면 좋아질 수 있나요?'
            if t == saymod.QUESTION_LINE:
                return '치료는 얼마나 오래 받아야 하나요?'
            return '네, 알겠습니다.'
        enc = SimEnc(9, rf)
        log = _loop(enc)
        texts = [e['text'] for e in log]
        self.assertEqual(len(log), 9)
        self.assertEqual(log[1]['phase'], 'explain-answer')            # 바로 다음 턴에 답
        self.assertNotIn(LINES[6], texts)                              # 최저 우선순위(생활) 줄을 뺐다
        self.assertEqual(texts[-2], saymod.QUESTION_LINE)
        self.assertEqual(log[-1]['phase'], 'explain-answer')
        self.assertEqual(texts[-1], '약은 보통 1~2년 정도 드셔요.')

    def test_tests_question_pulls_tests_line(self):
        def rf(t):
            return '네, 알겠습니다. 다음 검사는 어떤 게 필요할까요?' if t == LINES[0] else '네, 알겠습니다.'
        enc = SimEnc(9, rf)
        log = _loop(enc)
        self.assertEqual(log[1]['text'], LINES[3])          # 검사 줄을 당겨 바로 답(추가 턴 없음)
        self.assertEqual(log[1]['phase'], 'explain')
        self.assertEqual(len([e for e in log if e['phase'] == 'explain-answer']), 0)

    def test_tight_budget_keeps_core(self):
        enc = SimEnc(6, lambda t: '네, 알겠습니다.')
        log = _loop(enc)
        texts = [e['text'] for e in log]
        self.assertLessEqual(len(log), 6)
        for must in (LINES[0], LINES[3], LINES[4], LINES[5], saymod.QUESTION_LINE):
            self.assertIn(must, texts)

    def test_question_every_line(self):
        enc = SimEnc(9, lambda t: '치료하면 좋아질 수 있나요?')
        log = _loop(enc)
        self.assertEqual(len(log), 9)
        self.assertEqual(log[-1]['phase'], 'explain-answer')
        self.assertEqual(log[-2]['text'], saymod.QUESTION_LINE)
        self.assertGreaterEqual(len([e for e in log[:-2] if e['phase'] == 'explain-answer']), 2)
        self.assertIn(LINES[5], [e['text'] for e in log])      # 경고 줄은 중간 답 때문에 빠지지 않는다

    def test_spare_exam_used(self):
        calls = []

        def fake_spare(enc):
            calls.append(enc.turn)
            return enc.act('EXAM', '경부 림프절 촉진하겠습니다', phase='exam-spare') if len(calls) == 1 else None
        enc = SimEnc(10, lambda t: '네, 알겠습니다.')
        log = _loop(enc, spare=fake_spare)
        self.assertEqual(len(log), 10)
        self.assertEqual(log[8]['kind'], 'EXAM')
        self.assertEqual(log[9]['kind'], 'SAY')           # spare_exam이 더 할 게 없으면 설명 문장
        self.assertNotIn(explain.TEACH_BACK, [e['text'] for e in log])


# ---------------------------------------------------------------- 가짜 서버 e2e
class TestDryRunV8c(unittest.TestCase):
    def test_a_first_explain_question_answered(self):
        for case, op in CASES:
            c = run_with(QClient(case, op, explain_q='first'))
            ev = c.events
            i = next(i for i, e in enumerate(ev) if e[2] == QClient.first_reply)
            self.assertLess(i + 1, len(ev), case)
            nxt = ev[i + 1]
            self.assertEqual(nxt[0], 'SAY', case)
            self.assertTrue(TEST_WORD_RE.search(nxt[1]), (case, nxt[1]))
            self.assertLessEqual(c.turns, 34)

    def test_b_final_question_answered_last(self):
        for case, op in CASES:
            c = run_with(FakeClient(case, op, q_line='question', explain_q='first'))
            self.assertLessEqual(c.turns, 34, case)
            s = doctor_says(c)
            led = explain_ledger()
            qi = max(i for i, e in enumerate(c.events) if e[1] == saymod.QUESTION_LINE)
            self.assertEqual(c.events[qi][2], CASE_Q[case])
            self.assertEqual(qi, len(c.events) - 2, case)       # Q 다음 한 턴(답)으로 끝
            self.assertEqual(c.events[-1][0], 'SAY')
            self.assertEqual(led[-1]['phase'], 'explain-answer', case)
            self.assertNotIn(explain.TEACH_BACK, s)
            self.assertEqual(len(s), len(set(s)), s)

    def test_c_no_final_question_uses_every_turn(self):
        # interview.spare_exam이 있으면 그것으로, 없으면 설명 문장으로 34턴을 채운다
        for spare in ('real', None):
            for case, op in CASES:
                patch = mock.patch.object(interview, 'spare_exam', None, create=True) if spare is None else \
                    mock.patch.object(interview, 'spare_exam', getattr(interview, 'spare_exam', None), create=True)
                with patch:
                    c = run_with(FakeClient(case, op, q_line='none', explain_q='none'))
                s = doctor_says(c)
                self.assertNotIn(explain.TEACH_BACK, s, case)
                self.assertFalse(any(e.get('phase') == 'explain-teachback' for e in run.LAST_RUN['ledger']))
                self.assertEqual(c.turns, 34, (case, spare, s[-4:]))
                self.assertEqual(len(s), len(set(s)), s)
                if spare is None:
                    self.assertEqual(c.events[-1][0], 'SAY')
                    self.assertNotEqual(c.events[-1][1], saymod.QUESTION_LINE)

    def test_d_question_after_every_line(self):
        for case, op in CASES:
            c = run_with(FakeClient(case, op, explain_q='all'))
            self.assertLessEqual(c.turns, 34, case)
            led = explain_ledger()
            self.assertEqual(led[-1]['phase'], 'explain-answer', case)
            self.assertEqual(c.events[-1][0], 'SAY')
            self.assertEqual(c.events[-2][1], saymod.QUESTION_LINE)
            mids = [e for e in led[:-1] if e['phase'] == 'explain-answer']
            self.assertGreaterEqual(len(mids), 2, case)
            s = doctor_says(c)
            self.assertEqual(len(s), len(set(s)), s)
            self.assertTrue(any(saymod.WARN_RE.search(x) for x in s), case)

    def test_spoken_lines_valid(self):
        for case, op in CASES:
            c = run_with(FakeClient(case, op))
            for e in explain_ledger():
                t = e['text']
                self.assertLessEqual(nlen(t), 30, t)
                self.assertEqual(saymod.tidy(t), t)
                self.assertFalse(explain.SAY_BAD_RE.search(t), t)


if __name__ == '__main__':
    unittest.main()

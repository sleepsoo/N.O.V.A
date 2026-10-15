"""v6 수용 테스트: safety_rca.md Fix 1·2·3(안전 확인 문진 + 필수 설명 문장). API 없이 실행."""
import json
import os
import re
import subprocess
import sys
import unicodedata
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
V6 = os.path.dirname(HERE)
V5 = os.path.join(os.path.dirname(V6), 'code_v5')
sys.path.insert(0, V6)
sys.path.insert(0, HERE)

import run  # noqa: E402
from agent import bank2, explain, kb, say as saymod  # noqa: E402
from agent.interview import Checklist  # noqa: E402
from agent.util import validate_question  # noqa: E402
import test_v2  # noqa: E402
from test_v5 import FakeEnc  # noqa: E402

SED_MUST = ['오늘 바로 끊지 않고 천천히 줄여요.', '졸릴 땐 운전 말고 술·약국 수면제도 피하세요.',
            '수면 습관 교정과 인지행동치료도 같이 해요.']
GRAVES_MUST = ['두근거림 약 전에 천식·심장병 있으면 알려 주세요.']
NEW_Q = {'sb_last': '마지막으로 언제 드셨어요?', 'sb_seizure': '약을 끊었을 때 경련한 적 있나요?',
         'wl_cardio': '가슴 통증이나 숨참은 없으세요?'}


def nlen(s):
    return len(unicodedata.normalize('NFC', s))


def _kb(i):
    return next(k for k in kb.KB if k['id'] == i)


def _dry(root, opening_name):
    """code_v5 또는 code_v6의 test_v2 가짜 서버로 한 증례를 돌려 턴·카운트·SAY 목록을 받는다(별도 프로세스: agent 패키지 충돌 방지)."""
    code = ('import sys, json, io, contextlib\n'
            f'sys.path.insert(0, {os.path.join(root, "tests")!r})\n'
            'with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):\n'
            '    import test_v2, run\n'
            f'    c = test_v2.run_v2(test_v2.{opening_name})\n'
            'print(json.dumps({"turns": c.turns, "counts": run.LAST_RUN.get("counts"),'
            ' "say": [e[1] for e in c.events if e[0] == "SAY"], "exam": [e[1] for e in c.events if e[0] == "EXAM"]},'
            ' ensure_ascii=False))\n')
    env = {k: v for k, v in os.environ.items() if k != 'NOVA_DEV_KEY'}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    out = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, env=env, timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


class TestV6Bank(unittest.TestCase):
    def test_substance_bank_safety_slots_prio1(self):  # (a)
        sb = {s: (q, p) for s, _, q, p in bank2.CATEGORY_Q['substance']}
        self.assertEqual(sb['sb_last'], (NEW_Q['sb_last'], 1))
        self.assertEqual(sb['sb_seizure'], (NEW_Q['sb_seizure'], 1))
        prof = {'age': 62, 'sex': 'F', 'pediatric': False, 'categories': ['substance', 'insomnia']}
        cl = Checklist(prof, test_v2.V2_C01)
        must = [s for s in cl.ranked() if cl.items[s]['prio'] == 1]
        self.assertIn('sb_last', must)
        self.assertIn('sb_seizure', must)

    def test_weight_loss_bank_cardio_prio1(self):  # (b)
        wl = {s: (q, p) for s, _, q, p in bank2.CATEGORY_Q['weight_loss']}
        self.assertEqual(wl['wl_cardio'], (NEW_Q['wl_cardio'], 1))
        prof = {'age': 32, 'sex': 'F', 'pediatric': False, 'categories': ['weight_loss', 'fatigue', 'mood']}
        cl = Checklist(prof, test_v2.V2_C10)
        self.assertIn('wl_cardio', [s for s in cl.ranked() if cl.items[s]['prio'] == 1])

    def test_new_bank_questions_valid(self):
        for q in NEW_Q.values():
            self.assertLessEqual(nlen(q), 30, q)
            self.assertTrue(q.endswith('?'))
            self.assertEqual(validate_question(q), (True, 'ok'), q)
            self.assertEqual(saymod.say_problem(q, allow_question=True), '', q)


class TestV6DryRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = {k: {'v5': _dry(V5, k), 'v6': _dry(V6, k)} for k in ('V2_C01', 'V2_C10')}

    def test_c01_new_questions_asked(self):  # (a) 실제 문진 경로에서 선택됨
        says = self.r['V2_C01']['v6']['say']
        self.assertIn(NEW_Q['sb_last'], says)
        self.assertIn(NEW_Q['sb_seizure'], says)
        for s in SED_MUST:
            self.assertIn(s, says)

    def test_c10_new_question_asked(self):  # (b)
        says = self.r['V2_C10']['v6']['say']
        self.assertIn(NEW_Q['wl_cardio'], says)
        self.assertIn(GRAVES_MUST[0], says)

    def test_interview_and_exam_counts_same_as_v5(self):  # (c)
        self.assertEqual(run.load_config()['INTERVIEW_Q'], 22)
        for k, r in self.r.items():
            self.assertEqual(r['v6']['counts']['interview'], 22, k)
            self.assertEqual(r['v6']['counts']['interview'], r['v5']['counts']['interview'], k)
            self.assertEqual(r['v6']['counts']['exam'], r['v5']['counts']['exam'], k)
            self.assertEqual(r['v6']['exam'], r['v5']['exam'], k)
            self.assertEqual(r['v6']['counts']['refused'], 0, k)
        # C01: must_say 개수 불변 → 전체 턴 동일
        self.assertEqual(self.r['V2_C01']['v6']['turns'], self.r['V2_C01']['v5']['turns'])
        # 설명 턴은 EXPLAIN_N 상한 안(빈자리가 있으면 필수 문장이 채움)
        for k, r in self.r.items():
            self.assertLessEqual(r['v6']['turns'], 44, k)


class TestV6MustSay(unittest.TestCase):
    def test_must_say_sentences_valid(self):  # (d)
        sed, gr = _kb('sedative_ud'), _kb('graves')
        self.assertEqual([s for _, s in sed['must_say']], SED_MUST)
        self.assertEqual([s for _, s in gr['must_say']], GRAVES_MUST)
        for k in (sed, gr):
            for pat, s in k['must_say']:
                self.assertLessEqual(nlen(s), 30, s)
                self.assertEqual(saymod.say_problem(s), '', s)
                self.assertIsNone(explain.SAY_BAD_RE.search(s), s)
                self.assertEqual(explain.safe_say(s), s)
                self.assertNotIn('?', s)
                self.assertTrue(re.search(pat, s), s)  # 자기 문장에 패턴이 걸려야 중복 삽입이 없음
                if k.get('ban_say'):
                    self.assertIsNone(re.search(k['ban_say'], s), s)
        self.assertNotRegex(gr['must_say'][0][0], '심장')  # '심전도로 심장…' 오탐 방지

    def test_old_sedative_lines_do_not_satisfy_new_patterns(self):
        sed = _kb('sedative_ud')
        self.assertIsNone(re.search(sed['must_say'][0][0], '약은 갑자기 끊지 말고 천천히 줄여요.'))
        self.assertIsNone(re.search(sed['must_say'][1][0], '졸릴 땐 운전과 위험한 일은 피하세요.'))

    def _assert_elements(self, out, musts):
        n = run.load_config()['EXPLAIN_N']
        self.assertLessEqual(len(out), n)
        self.assertEqual(out[-1], saymod.QUESTION_LINE)
        for s in musts:
            self.assertIn(s, out)
        self.assertTrue(any(saymod.TEST_RE.search(s) for s in out), out)
        self.assertTrue(any(saymod.FOLLOWUP_RE.search(s) and explain.COME_RE.search(s) for s in out), out)
        self.assertTrue(any(saymod.WARN_RE.search(s) for s in out), out)
        self.assertIn(explain.TEACH_BACK, out)
        for s in out:
            self.assertLessEqual(nlen(s), 30, s)

    def test_c10_explain_keeps_followup_and_tests(self):  # (e)
        k = kb.match_kb('그레이브스병에 의한 갑상샘항진증')
        say = ['그레이브스병에 의한 갑상샘항진증 가능성이 높아요.', '호르몬이 많아 살이 빠지고 두근거려요.',
               '현재 소견은 암보다 호르몬 과다를 시사해요.', '갑상샘 호르몬·항체 피검사로 원인을 확인해요.',
               '항갑상샘제를 쓰면 드물게 고열·목 통증이 와요.', '고열·인후통·황달·숨참이면 바로 오세요.',
               '1~2주 뒤 결과 보고 약을 시작해요.', '카페인을 줄이고 충분히 쉬세요.', '심전도로 심장 리듬을 볼게요.']
        out = explain.fix_say(FakeEnc(), list(say), k)
        self._assert_elements(out, GRAVES_MUST)
        # v5 실측 C10 설명(sim-C10-v5) 재현
        v5_say = ['그레이브스병으로 인한 갑상선 항진의 가능성이 큽니다', '호르몬이 많아 체중이 줄고 가슴이 두근거려요',
                  '검사 결과를 확인해 정확한 진단을 노력할 거예요', '항갑상샘제를 쓰면 드물게 고열이 올 수 있어요',
                  '1~2주 뒤 결과 보러 다시 오세요']
        self._assert_elements(explain.fix_say(FakeEnc(), list(v5_say), k), GRAVES_MUST)

    def test_c01_explain_keeps_followup_and_tests(self):
        dx = '수면제(진정수면제) 사용장애'
        k = kb.match_kb(dx)
        say = ['수면제 의존이 생긴 상태로 보여요.', '약에 몸이 익숙해져 양이 늘었어요.', '급히 끊지 말고 천천히 줄여요.',
               '피검사와 소변 약물검사를 할게요.', '감량 중 경련·혼동·환각이 오면 바로 오세요.',
               '1~2주 뒤 오셔서 양을 같이 조정해요.', '규칙적 기상과 낮잠 줄이기를 해 보세요.']
        out = explain.fix_say(FakeEnc(dx), list(say), k)
        self._assert_elements(out, SED_MUST)


def _enc(kid, ledger):
    import types
    k = _kb(kid)
    return types.SimpleNamespace(kb=k, dx=k['name'][0], ledger=ledger)


def _q(qid, text, reply, turn, **kw):
    return dict({'kind': 'SAY', 'qid': qid, 'text': text, 'reply': reply, 'turn': turn, 'phase': 'interview'}, **kw)


def _note(kid):
    k = _kb(kid)
    return {'S': {'hpi': '62세 여성 현병력.', 'ros': 'Chest pain ( )  Palpitation ( )\nOthers : '},
            'P': {'disposition': '- 활력징후 안정 : BP 128/78\n' + '\n'.join('- ' + l for l in k['disposition'])}}


class TestV6SafetyRecord(unittest.TestCase):  # (g) 결정적 기록 줄
    def setUp(self):
        from agent import record
        self.add = record.add_safety_lines

    def test_sedative_negative_prefixes_template(self):
        enc = _enc('sedative_ud', [_q('sb_last', NEW_Q['sb_last'], '어젯밤 자기 전에 네 알을 먹었어요.', 11),
                                   _q('sb_seizure', NEW_Q['sb_seizure'], '그런 건 없어요.', 14)])
        n = self.add(enc, _note('sedative_ud'))
        self.assertIn('마지막 복용: 어젯밤 자기 전에 네 알을 먹었어요 (턴 11); 금단 경련·섬망 병력: 그런 건 없어요 (턴 14)',
                      n['S']['hpi'])
        line = next(l for l in n['P']['disposition'].split('\n') if '외래 추적이 적절' in l)
        self.assertTrue(line.startswith('- 금단 경련·섬망 병력 없음, 마지막 복용 어젯밤 자기 전에 네 알을 먹었어요 → 의식 명료'), line)
        self.assertIn('입원 해독 고려', line)  # KB 보수 분기 유지
        self.assertEqual(n['P']['disposition'].count('\n'), _note('sedative_ud')['P']['disposition'].count('\n'))

    def test_sedative_positive_keeps_conservative_branch(self):
        enc = _enc('sedative_ud', [_q('sb_seizure', NEW_Q['sb_seizure'], '끊었을 때 경련한 적 있어요.', 14)])
        n = self.add(enc, _note('sedative_ud'))
        lines = n['P']['disposition'].split('\n')
        i = next(i for i, l in enumerate(lines) if '입원 해독 고려 기준 해당' in l)
        self.assertTrue(lines[i].startswith('- 금단 경련·섬망 병력 있음 → '))
        self.assertIn('외래 추적이 적절', lines[i + 1])           # 원 템플릿(입원 해독 고려 조건 포함) 그대로
        self.assertIn('입원 해독 고려', lines[i + 1])
        self.assertNotIn('마지막 복용', n['S']['hpi'])            # 묻지 않은 항목은 쓰지 않음

    def test_no_answer_no_line(self):
        for kid in ('sedative_ud', 'graves'):
            led = [_q('sb_seizure', NEW_Q['sb_seizure'], '', 14, refused='X'),
                   _q('wl_cardio', NEW_Q['wl_cardio'], '한 번에 하나씩 물어봐 주세요.', 5, one_at_a_time=True)]
            self.assertEqual(self.add(_enc(kid, led), _note(kid)), _note(kid), kid)
        # 대화가 '네, 알겠습니다'뿐이면 판정하지 않음
        led = [_q('', GRAVES_MUST[0], '네, 알겠습니다.', 36, phase='explain'),
               _q('sb_seizure', NEW_Q['sb_seizure'], '네, 그런 편이에요.', 14)]
        n = self.add(_enc('graves', led), _note('graves'))
        self.assertEqual(n['P'], _note('graves')['P'])
        n = self.add(_enc('sedative_ud', led), _note('sedative_ud'))
        self.assertEqual(n['P'], _note('sedative_ud')['P'])
        self.assertIn('금단 경련·섬망 병력: 네, 그런 편이에요 (턴 14)', n['S']['hpi'])

    def test_graves_lines(self):
        led = [_q('wl_cardio', NEW_Q['wl_cardio'], '가슴 통증은 없어요.', 5),
               _q('', GRAVES_MUST[0], '천식이나 심장병은 없어요.', 36, phase='explain')]
        n = self.add(_enc('graves', led), _note('graves'))
        self.assertIn('흉통/숨참 : 가슴 통증은 없어요 (턴 5)', n['S']['ros'])
        line = next(l for l in n['P']['disposition'].split('\n') if '천식·심장병' in l)
        self.assertEqual(line, '- 천식·심장병 없음 확인(턴 36) → 베타차단제 금기 없음')
        # ROS에 이미 흉통이 있으면 생략, 금기 답이 형식적이면 지병 문진으로 판정
        note = _note('graves')
        note['S']['ros'] += '가슴통증 없음 -'
        led = [_q('wl_cardio', NEW_Q['wl_cardio'], '가슴 통증은 없어요.', 5), _q('pmh_other', '다른 지병이 있으세요?', '그런 건 없어요.', 9),
               _q('', GRAVES_MUST[0], '네, 알겠습니다.', 36, phase='explain')]
        n = self.add(_enc('graves', led), note)
        self.assertNotIn('흉통/숨참', n['S']['ros'])
        self.assertIn('- 천식·심장병 없음 확인(턴 9 지병 문진에서 기저질환 부인) → 베타차단제 금기 없음', n['P']['disposition'])
        # v6b 시뮬 실측: 금기 문장에 엉뚱한 답('…자주 있어요'), 지병 문진도 주제 밖 부정 → 판정하지 않음(줄 없음)
        led = [_q('pmh_other', '다른 지병이 있으세요?', '갑상샘 질환 진단을 받은 적은 없어요.', 9),
               _q('', GRAVES_MUST[0], '가슴이 두근거리는 증상도 자주 있어요.', 39, phase='explain')]
        n = self.add(_enc('graves', led), _note('graves'))
        self.assertNotIn('천식·심장병', n['P']['disposition'])
        led = [_q('', GRAVES_MUST[0], '천식이 있어요.', 36, phase='explain')]
        n = self.add(_enc('graves', led), _note('graves'))
        self.assertIn('베타차단제 신중', n['P']['disposition'])
        self.assertIn('입원 고려', n['P']['disposition'])

    def test_dry_run_note_has_lines(self):
        code = ('import sys, json, io, contextlib\n'
                f'sys.path.insert(0, {HERE!r})\n'
                'with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):\n'
                '    import test_v2, run\n'
                '    test_v2.run_v2(test_v2.V2_C01)\n'
                'print(json.dumps(run.LAST_RUN["note"], ensure_ascii=False))\n')
        env = {k: v for k, v in os.environ.items() if k != 'NOVA_DEV_KEY'}
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        out = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, env=env, timeout=300)
        note = json.loads(out.stdout.strip().splitlines()[-1])
        self.assertIn('마지막 복용: ', note['S']['hpi'])
        self.assertIn('금단 경련·섬망 병력: ', note['S']['hpi'])


class TestV6AsthmaPattern(unittest.TestCase):  # (h)
    WRONG = '항갑상샘제는 간 기능을 체크하고 천식이 있으면 삼가해요'

    def test_wrong_sentence_replaced_by_must(self):
        k = kb.match_kb('그레이브스병에 의한 갑상샘항진증')
        say = ['그레이브스병이 의심되는 갑상샘 항진증이 있어요', '호르몬이 많아 체중이 빠지고 두근거리는 증상이 나타나요',
               '정확한 상태는 혈액검사와 심전도로 확인해요.', self.WRONG, '숨참·불규칙한 맥·고열·혼동 시 바로 오세요',
               '1~2주 뒤 결과 보러 다시 오세요']
        out = explain.fix_say(FakeEnc(), list(say), k)
        self.assertNotIn(self.WRONG, out)
        self.assertEqual(out.count(GRAVES_MUST[0]), 1)
        self.assertFalse(any('천식' in s and '항갑상' in s for s in out), out)

    def test_pattern_scope(self):
        pat = _kb('graves')['must_say'][0][0]
        self.assertRegex(GRAVES_MUST[0], pat)
        for s in ('심전도로 심장 리듬을 볼게요.', '천식 약은 따로 쓰지 않아요.', '두근거림은 베타차단제로 줄일 수 있어요.'):
            self.assertIsNone(re.search(pat, s), s)
        # 다른 진단 KB에는 영향 없음
        sed = kb.match_kb('수면제(진정수면제) 사용장애')
        self.assertEqual(explain.fix_say(FakeEnc('수면제(진정수면제) 사용장애'), [self.WRONG], sed).count(self.WRONG), 1)


if __name__ == '__main__':
    unittest.main()

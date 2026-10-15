"""v5 테스트(code_js 대비 최소 변경 2건). API 없이 실행.
변경 1: 계획용 지침 발췌에서 치료·용량·성분명 제거 + 처방 확정 표현 필터 보강.
변경 2: 설명 슬롯 내용 교체(되말하기·재진 직접 안내·질문에 다음 턴 답) — 설명 턴 수 불변.
"""
import filecmp
import importlib.util
import os
import re
import shutil
import sys
import tempfile
import types
import unicodedata
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
V5 = os.path.dirname(HERE)
JS = os.path.join(os.path.dirname(V5), 'code_js')
sys.path.insert(0, V5)

import run  # noqa: E402
from agent import explain, guidelines, interview, kb, say as saymod  # noqa: E402

DOSE_RE = re.compile(r'\d+(?:\.\d+)?\s*(?:mg|㎎|mcg|%|정|알|주분)', re.I)
DRUG_RE = re.compile(r'(메티마졸|프로프라놀롤|메트포르민|레보티록신|졸피뎀|methimazole|propranolol|metformin)', re.I)
COMMIT_RE = re.compile(r'(시작해요|시작할게|시작합니다|처방해요|처방할게|처방했|드릴게요|올려요|증량)')


def nlen(s):
    return len(unicodedata.normalize('NFC', s))


def _load_js_agent():
    """code_js/agent를 'agent_js' 패키지로 따로 읽는다(대조용)."""
    if 'agent_js' in sys.modules:
        return sys.modules['agent_js']
    spec = importlib.util.spec_from_file_location('agent_js', os.path.join(JS, 'agent', '__init__.py'),
                                                  submodule_search_locations=[os.path.join(JS, 'agent')])
    mod = importlib.util.module_from_spec(spec)
    sys.modules['agent_js'] = mod
    spec.loader.exec_module(mod)
    return mod


GL_DOC = """제목: 그레이브스병 갑상선기능항진증 진료지침
문서 유형: 진료지침
연도: 2024

# 증상과 진찰
두근거림, 체중 감소, 손 떨림, 더위를 못 참는 증상이 흔하다. 갑상선종과 안구 돌출을 진찰한다.

# 감별진단
아급성 갑상선염과 무통성 갑상선염을 감별한다. 갑상선 섭취율 검사가 도움이 된다.

# 진단 검사
혈청 TSH와 유리 T4를 측정한다. TSH 수용체 항체(TRAb)로 그레이브스병을 확인한다.

# 치료
메티마졸 15mg 하루 1회로 시작한다. 프로프라놀롤 10mg 하루 3회로 증상을 조절한다.
항갑상선제는 12~18개월 유지한다.

# 추적 관찰
4~6주 간격으로 갑상선기능검사를 반복한다. 메티마졸 용량은 유리 T4에 따라 감량한다.
고열·인후통이 생기면 무과립구증을 의심하고 즉시 내원하도록 교육한다.
교신 저자: 홍길동, 가나다 의과대학 내과학교실
"""


def _gl_dir():
    root = tempfile.mkdtemp(prefix='v5gl_')
    os.makedirs(os.path.join(root, 'KR_Test'))
    with open(os.path.join(root, 'KR_Test', 'graves.md'), 'w', encoding='utf-8') as f:
        f.write(GL_DOC)
    return root


def _enc(dx='그레이브스병 갑상선기능항진증', diffs=None):
    return types.SimpleNamespace(cfg={'GUIDE': 1}, dx=dx, differentials=diffs or [dx])


class TestV5Sanitize(unittest.TestCase):
    def test_sanitize_drops_treatment_dose_drug(self):
        txt = ('[출처: KR | 지침]\n(dx) 검사: 혈청 TSH와 유리 T4를 측정한다. 메티마졸 15mg 하루 1회로 시작한다.\n'
               '(fu) 추적: 4~6주 간격으로 갑상선기능검사를 반복한다. 용량은 유리 T4에 따라 감량한다. '
               '방사성요오드 치료 후 4-6주 이내 갑상선기능검사를 한다.\n'
               '교신 저자: 홍길동, 가나다 의과대학 내과학교실\n'
               '권고 수준: A 항갑상선제를 우선 고려한다.\n[출처: US | 빈 문서]\nmetformin 500 mg twice daily.')
        out = guidelines.sanitize(txt)
        self.assertIn('혈청 TSH와 유리 T4를 측정한다.', out)
        self.assertIn('4~6주 간격으로 갑상선기능검사를 반복한다.', out)
        for bad in ('메티마졸', '15mg', '감량', '방사성요오드', '교신', '항갑상선제', 'metformin', '빈 문서'):
            self.assertNotIn(bad, out)

    def test_excerpt_skips_treatment_heading(self):
        root = _gl_dir()
        try:
            path = os.path.join(root, 'KR_Test', 'graves.md')
            self.assertIn('메티마졸 15mg', guidelines.excerpt(path, ['tx', 'dx', 'fu'], 1500))       # 기존 동작
            self.assertNotIn('15mg', guidelines.excerpt(path, ['tx', 'dx', 'fu'], 1500, skip_tx=True))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_hint_plan_has_no_treatment(self):
        root = _gl_dir()
        old = guidelines.INDEX
        try:
            guidelines.set_index(guidelines.build_index(root))
            enc = _enc()
            out = guidelines.hint_plan(enc)
            self.assertIn('TSH', out)
            self.assertIn('갑상선기능검사', out)
            self.assertIsNone(DOSE_RE.search(out), out)
            self.assertIsNone(DRUG_RE.search(out), out)
            self.assertNotIn('하루 1회', out)
            self.assertNotIn('교신', out)
            self.assertTrue(enc.gl_sources)  # 인용(교육 칸 '참고 지침' 줄)은 유지
        finally:
            guidelines.set_index(old)
            shutil.rmtree(root, ignore_errors=True)

    def test_gl_rule_tests_followup_only(self):
        src = open(os.path.join(V5, 'agent', 'explain.py'), encoding='utf-8').read()
        m = re.search(r"gl_rule = \((.*?)if gl else", src, re.S)
        self.assertIn('tests·follow_up의 근거로만', m.group(1))
        self.assertNotIn('treatment', m.group(1))
        self.assertNotIn('disposition', m.group(1))


class TestV5Filters(unittest.TestCase):
    def test_say_commit_phrases_replaced(self):
        for s in ('1~2주 뒤 결과 보고 약을 시작해요.', '항갑상샘제를 시작할게요.', '오늘 약을 처방해요.', '항생제 처방했다 48시간 후 확인해요',
                  '약을 드릴게요.', '용량을 올려요.', '혈당약을 증량해요.', '오늘부터 치료를 시작합니다.', '약을 감량할게요.'):
            out = explain.safe_say(s)
            self.assertEqual(out, explain.SAFE_SAY, s)
            self.assertIsNone(COMMIT_RE.search(out))

    def test_say_safe_lines_kept(self):
        for s in ('감량 중 경련·혼동·환각이 오면 바로 오세요.', '항생제를 처방된 기간 다 드세요.', '약은 갑자기 끊지 말고 천천히 줄여요.',
                  '1~2주 뒤 결과 보러 다시 오세요.', explain.TEACH_BACK, '단 음료와 야식부터 줄여 보세요.'):
            self.assertEqual(explain.safe_say(s), s)

    def test_plan_line_commit_replaced(self):
        for l in ('메트포르민 증량합니다', '항갑상샘제 시작해요', '베타차단제 처방했습니다', '약을 올려요'):
            out = explain.safe_plan_line(l, 'treatment')
            self.assertIn(explain.DECIDE, out, l)
            self.assertIsNone(COMMIT_RE.search(out), out)
            self.assertIsNone(DRUG_RE.search(out), out)
        self.assertEqual(explain.safe_plan_line('결과 확인 후 메트포르민 시작 고려(eGFR 확인)', 'treatment'),
                         '결과 확인 후 경구 혈당강하제 시작 고려(eGFR 확인)')

    def test_render_plan_tests_line_drug_class(self):  # S06 code_js 실측: 'eGFR : … 메트포르민 시작 여부 판단'
        enc = types.SimpleNamespace(profile={'age': 54, 'sex': 'M'}, opening='', ledger=[], explained=[], facts=[],
                                    vitals='BP 146/88 mmHg, PR 82 회/분, RR 16 회/분, BT 36.6°C', cfg=run.load_config())
        plan = {'tests': ['eGFR : 신장 기능 확인 및 메트포르민 시작 여부 판단'], 'treatment': [], 'disposition': [],
                'follow_up': [], 'education': []}
        out = explain.render_plan(enc, plan, None)
        self.assertIn('경구 혈당강하제 시작 여부 판단', out['tests'])
        self.assertIsNone(DRUG_RE.search(out['tests']))

    def test_kb_say_unchanged_by_new_filters(self):
        js = _load_js_agent()
        import agent_js.explain as jx  # noqa: F401
        jexp = sys.modules['agent_js.explain']
        for k in kb.KB:
            for s in list(k.get('say') or []) + [x for _, x in k.get('must_say') or []] + [k.get('red_say', '')]:
                if s:
                    self.assertEqual(explain.safe_say(s), jexp.safe_say(s), (k['id'], s))
        self.assertTrue(js)


class FakeEnc:
    def __init__(self, dx='그레이브스병에 의한 갑상샘항진증'):
        self.cfg = run.load_config()
        self.dx = dx
        self.say_checks = None
        self.budget = types.SimpleNamespace(can_call=lambda *a, **k: False)
        self.client = None


class TestV5Explain(unittest.TestCase):
    def _check(self, lines, n):
        self.assertLessEqual(len(lines), n)
        self.assertEqual(lines[-1], saymod.QUESTION_LINE)
        for s in lines[:-1]:
            self.assertEqual(saymod.say_problem(s), '', s)
            self.assertLessEqual(nlen(s), 30, s)
            self.assertIsNone(explain.SAY_BAD_RE.search(s), s)
            self.assertIsNone(re.search(r'고\s*(있|하|드|계)[^ ]*\?', s), s)  # '-고' 접속 질문 없음

    def test_fixed_slot_sentences_valid(self):
        for s in (explain.TEACH_BACK, '1~2주 뒤 결과 보러 다시 오세요.', '다음 주에 결과 보러 다시 오세요.'):
            self.assertEqual(saymod.say_problem(s), '', s)
            self.assertLessEqual(nlen(s), 30)
            self.assertNotIn('?', s)

    def test_fix_say_teach_back_and_direct_followup_same_turns(self):
        enc = FakeEnc()
        k = kb.match_kb(enc.dx)
        n = enc.cfg['EXPLAIN_N']
        say = ['그레이브스병에 의한 갑상샘항진증 가능성이 높아요.', '호르몬이 많아 살이 빠지고 두근거려요.',
               '현재 소견은 암보다 호르몬 과다를 시사해요.', '갑상샘 호르몬·항체 피검사로 원인을 확인해요.',
               '항갑상샘제를 쓰면 드물게 고열·목 통증이 와요.', '고열·인후통·황달·숨참이면 바로 오세요.',
               '1~2주 뒤 결과 보고 약을 시작해요.']
        out = explain.fix_say(enc, list(say), k)
        self._check(out, n)
        self.assertIn(explain.TEACH_BACK, out)
        wi = max(i for i, s in enumerate(out) if saymod.WARN_RE.search(s) and s != explain.TEACH_BACK)
        self.assertEqual(out[wi + 1], explain.TEACH_BACK)
        self.assertTrue(any(saymod.FOLLOWUP_RE.search(s) and explain.COME_RE.search(s) for s in out), out)
        # 설명 턴 상한은 code_js와 같다(EXPLAIN_N)
        long_say = say + ['카페인을 줄이고 충분히 쉬세요.', '눈이 시리면 인공눈물을 쓰세요.', '목이 붓는지도 함께 봐요.']
        self._check(explain.fix_say(FakeEnc(), long_say, k), n)

    def test_direct_followup_rewrite(self):
        lines = ['급성 충수염 가능성이 높아 보여요.', '2~3일 내 결과 보고 후 치료 계획을 정할게요', saymod.QUESTION_LINE]
        out = explain.direct_followup(lines)
        self.assertEqual(out[1], '2~3일 뒤 결과 보러 다시 오세요.')
        same = ['1~2주 뒤 결과 보러 다시 오세요.', saymod.QUESTION_LINE]
        self.assertEqual(explain.direct_followup(same), same)
        mon = ['4~6주마다 피검사로 확인해요.', saymod.QUESTION_LINE]
        self.assertEqual(explain.direct_followup(mon), mon)

    def test_question_pulls_answer_line_forward(self):
        sent = []

        class E:
            cfg = {'ANSWER_MAX': 2}
            explained = []
            turns_remaining = 30

            def can_act(self):
                return True

            def act(self, kind, text, phase=''):
                sent.append(text)
                reply = '결과는 언제 나와요?' if text.startswith('갑상샘') else '네.'
                return {'reply': reply}
        lines = ['갑상샘항진증 가능성이 높아요.', '호르몬이 많아 두근거려요.', '고열·인후통·황달·숨참이면 바로 오세요.',
                 '1~2주 뒤 결과 보러 다시 오세요.', saymod.QUESTION_LINE]
        explain.explain_loop(E(), lines, {})
        self.assertEqual(len(sent), len(lines))                  # 턴 수 불변
        self.assertEqual(sent[1], '1~2주 뒤 결과 보러 다시 오세요.')  # 질문 바로 다음 턴에 답

    def test_answer_fallback_uses_faq(self):
        enc = types.SimpleNamespace(plan_v2={}, dx='x', client=None, budget=None,
                                    cfg={'EFFORT_ANSWER': 'low', 'CALL_RESERVE': 0})
        with mock.patch.object(explain, 'ask', return_value=None):
            self.assertEqual(explain.answer(enc, '나을 수 있나요?', [], '치료하면 대부분 좋아져요.'), '치료하면 대부분 좋아져요.')
            self.assertEqual(explain.answer(enc, '나을 수 있나요?', []), '오늘 계획대로 하며 같이 조절해 갈게요.')


class TestV5InterviewInvariant(unittest.TestCase):
    """정보수집 경로 불변: 문진·진찰·기록 모듈은 code_js와 바이트 동일, hint_interview 출력 동일, 발췌 유무와 무관하게 질문 리스트 동일."""

    def test_untouched_files_identical(self):
        for rel in ('run.py', 'nova_sdk.py', 'requirements.txt', 'agent/interview.py', 'agent/assess.py', 'agent/record.py',
                    'agent/encounter.py', 'agent/subjective.py', 'agent/note2.py', 'agent/facts.py', 'agent/bank2.py',
                    'agent/banks.py', 'agent/kb.py', 'agent/say.py', 'agent/llm.py', 'agent/util.py'):
            self.assertTrue(filecmp.cmp(os.path.join(V5, rel), os.path.join(JS, rel), shallow=False), rel)

    def test_hint_interview_and_dx_identical_to_js(self):
        _load_js_agent()
        import importlib
        jg = importlib.import_module('agent_js.guidelines')
        root = _gl_dir()
        old = guidelines.INDEX
        try:
            guidelines.set_index(guidelines.build_index(root))
            jg.set_index(jg.build_index(root))
            diffs = ['그레이브스병 갑상선기능항진증', '아급성 갑상선염']
            a, b = guidelines.hint_interview(_enc(diffs=diffs)), jg.hint_interview(_enc(diffs=diffs))
            self.assertTrue(a)
            self.assertEqual(a, b)
            self.assertEqual(guidelines.hint_dx(_enc(diffs=diffs)), jg.hint_dx(_enc(diffs=diffs)))
        finally:
            guidelines.set_index(old)
            jg.set_index(None)
            shutil.rmtree(root, ignore_errors=True)

    def test_plan_q_questions_same_with_or_without_excerpt(self):
        cl = interview.Checklist({'age': 32, 'sex': 'F', 'pediatric': False, 'categories': ['weight_loss']}, '체중이 줄었어요.')
        enc = types.SimpleNamespace(profile={'age': 32, 'sex': 'F', 'informant': '본인', 'cc': '체중 감소', 'categories': ['weight_loss']},
                                    opening='체중이 줄었어요.', vitals='BP 120/80', ledger=[], differentials=['그레이브스병'],
                                    cfg=run.load_config(), client=None, budget=None, asked=[])
        fixed = {'questions': [{'slot': 'free', 'q': '더위를 많이 타세요?'}, {'slot': 'free', 'q': '손이 떨리세요?'}]}
        outs = []
        for gl in ('[진료지침 발췌]\n메티마졸 15mg 증량 문구\n', ''):
            with mock.patch.object(interview.guidelines, 'hint_interview', return_value=gl), \
                    mock.patch.object(interview, 'ask_json', return_value=dict(fixed)):
                outs.append(interview.plan_q(enc, cl, 2, 10))
        self.assertEqual(outs[0], outs[1])
        self.assertEqual([q for _, q in outs[0]], ['더위를 많이 타세요?', '손이 떨리세요?'])


if __name__ == '__main__':
    unittest.main()

"""v4 단위 테스트 U1~U14 (docs/v4_spec.md §8.1). API·키 없이 실행(가짜 서버+LLM: V3Client 상속).
pytest 또는 python3 -m unittest로 실행."""
import json
import os
import re
import subprocess
import sys
import time
import unittest
from types import SimpleNamespace
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import run  # noqa: E402
from agent import guidelines, note2, record, v4  # noqa: E402
from agent import say as saymod  # noqa: E402
from agent.record import SECTION_ORDER  # noqa: E402
from nova_sdk import RECORD_FIELDS, NovaError  # noqa: E402
from test_v2 import V2_C01, V2_C03, V2_C10, nlen  # noqa: E402
from test_v3 import V3Client  # noqa: E402

DOSE_RE = re.compile(r'\d+(?:\.\d+)?\s*(?:mg|㎎|mcg|μg|ml|mL|IU|정\b|알|캡슐|주분)')
POISON = '메티마졸 15mg 하루 1회 시작한다. 프로프라놀롤 20 mg을 투여한다. 갑상선 기능 검사를 4~6주 간격으로 시행한다.'


class V4Client(V3Client):
    """v4 프롬프트(plan_v4·plan_say4·answer4)에 답하는 가짜 서버+LLM.
    refuse_exams: 거절(EXAM_NOT_SPECIFIC)할 진찰 문구 집합, one_at_a_time: '한 번에 하나씩'으로 답할 질문 집합,
    sweep_replies: sweep 답 목록, first_reply: 진단 문장 뒤 답, final_reply: 마지막 질문 뒤 답, poison: 오염 LLM 출력."""

    def __init__(self, *a, refuse_exams=(), one_at_a_time=(), sweep_replies=None, first_reply='치료하면 좋아질 수 있나요?',
                 final_reply='약은 얼마나 오래 먹어야 하나요?', poison=False, empathy_reply='큰 병일까 봐 걱정돼요.', **kw):
        super().__init__(*a, **kw)
        self.refuse_exams = set(refuse_exams)
        self.one_at_a_time = set(one_at_a_time)
        self.sweep_replies = list(sweep_replies if sweep_replies is not None else ['가슴이 자주 두근거려요.', '아니요, 없어요.'])
        self.first_reply, self.final_reply = first_reply, final_reply
        self.poison = poison
        self.empathy_reply = empathy_reply
        self.n_say = 0

    def _ok(self, content, ans):
        self.events.append(('SAY', content, ans))
        return {'status': 'OK', 'content': ans, 'turn': self.turns, 'turns_remaining': 50 - self.turns}

    def say(self, content, request_id=None):
        self.n_say += 1
        if self.n_say == 1:
            self._turn(content)
            return self._ok(content, self.empathy_reply)
        if content in self.one_at_a_time:
            self._turn(content)
            return self._ok(content, '한 번에 하나씩 물어봐 주세요.')
        if content in v4.SWEEPS:
            self._turn(content)
            return self._ok(content, self.sweep_replies.pop(0) if self.sweep_replies else '아니요, 없어요.')
        if content == v4.FINAL_Q:
            self._turn(content)
            return self._ok(content, self.final_reply)
        if content.endswith('보여요.') or '같아요' in content:
            self._turn(content)
            return self._ok(content, self.first_reply)
        return super().say(content, request_id)

    def exam(self, content, request_id=None):
        if content in self.refuse_exams:
            self._turn(content)
            raise NovaError('EXAM_NOT_SPECIFIC', 422)
        return super().exam(content, request_id)

    def answer(self, user):
        if '"thyroid_relevant"' in user:
            qs = [{'type': 'closed', 'why': '감별', 'q': '더위나 땀은 어떠세요?'},            # 짝 → 거부
                  {'type': 'closed', 'why': '감별', 'q': '목이 붓거나 아프세요?'},            # ~거나 → 거부
                  {'type': 'topic', 'why': '양상', 'q': '두근거림에 대해 자세히 말씀해 주세요'},  # 이미 물음 → 중복
                  {'type': 'closed', 'why': '안병증', 'q': '눈이 튀어나온 느낌이 있으세요?'},
                  {'type': 'closed', 'why': '감별', 'q': '설사를 자주 하세요?'},
                  {'type': 'topic', 'why': '체중', 'q': '식사량에 대해 자세히 말씀해 주세요'},
                  {'type': 'closed', 'why': '감별', 'q': '목에 통증이 있으세요?'},
                  {'type': 'closed', 'why': '감별', 'q': '손이 떨리세요?'},
                  {'type': 'closed', 'why': '감별', 'q': '갈증이 심하세요?'},
                  {'type': 'closed', 'why': '감별', 'q': '소변을 자주 보세요?'},
                  {'type': 'closed', 'why': '감별', 'q': '열이 나세요?'},
                  {'type': 'closed', 'why': '감별', 'q': '잠은 잘 주무세요?'},
                  {'type': 'closed', 'why': '감별', 'q': '커피는 하루 몇 잔 드세요?'}]
            exams = [{'id': 'thyroid_bruit', 'why': '그레이브스병 — 혈류 증가 잡음', 'conf': 'high'},
                     {'id': 'eye_signs', 'why': '그레이브스 안병증', 'conf': 'high'},
                     {'id': 'post_tremor', 'why': '갑상샘중독 떨림', 'conf': 'high'},
                     {'id': 'spo2', 'why': '저산소 확인', 'conf': 'high'},          # 맥락 없음 → 제외
                     {'id': 'anthro', 'why': '체중 계측', 'conf': 'high'},           # 성인·체중 감소 → 제외
                     {'id': 'skin_temp', 'why': '감별 확인', 'conf': 'high'},         # 일반론 → 제외
                     {'id': 'dtr', 'why': '반사 항진 — 갑상샘중독', 'conf': 'high'},
                     {'id': 'radial', 'why': '빈맥·심방세동', 'conf': 'high'},
                     {'id': 'pretibial', 'why': '경골앞 점액부종', 'conf': 'mid'},
                     {'id': 'nonexistent', 'why': '없음', 'conf': 'high'}]
            return json.dumps({'differential': ['그레이브스병 (Graves disease)', '당뇨병 (Diabetes mellitus)'],
                               'questions': qs, 'exams': exams, 'thyroid_relevant': True}, ensure_ascii=False)
        if '"lines": {"dx": ["c1","c2"]' in user:
            if self.poison:
                lines = {'dx': ['메티마졸 15mg 시작해요.', '그레이브스병으로 보여요, 15mg 드릴게요.'],
                         'options': ['메티마졸로 치료를 시작해요.', '약 15mg 처방해 드려요.'],
                         'link': ['프로프라놀롤 20mg이면 떨림이 줄어요.'], 'concern': ['완치돼요.'],
                         'tests': ['하루 3회 약 먹고 피검사해요.'], 'caution': ['메티마졸 복용하세요.'],
                         'followup': ['1주 뒤 약을 시작해요.'], 'warning': ['열이 나요.'], 'lifestyle': ['메티마졸 드세요.']}
                faq = {'duration': '메티마졸 15mg을 2년 드세요.', 'prognosis': '약 시작해요.'}
                treat = ['메티마졸 15mg 하루 1회 시작', '프로프라놀롤 20 mg 하루 3회']
            else:
                lines = {'dx': ['갑상샘 호르몬이 넘치는 그레이브스병으로 보여요.', '그레이브스병 같아요.'],
                         'options': ['약으로 대부분 좋아지고, 요오드·수술도 있어요.'],
                         'link': ['그래서 살이 빠지고 손이 떨리고 더웠어요.'],
                         'concern': ['목과 눈 소견이 암보다 갑상샘 병에 맞아요.'],
                         'tests': ['피검사로 호르몬과 원인 항체를 확인해요.'],
                         'caution': ['약 먹다 열·목 통증이 생기면 바로 연락하세요.'],
                         'followup': ['1주 뒤 결과 보러 오시고 커피는 줄이세요.'],
                         'warning': ['숨참·불규칙한 맥·고열이면 바로 오세요.'], 'lifestyle': ['커피는 줄이세요.']}
                faq = {'duration': '약은 보통 1~2년 쓰며 피검사로 조절해요.'}
                treat = []
            return json.dumps({'tests': [{'name': 'TSH, free T4', 'reason': '확인'}], 'treatment': treat,
                               'disposition': [{'level': '외래', 'reason': '활력 안정'}],
                               'follow_up': ['재진 : 1주 후 결과 확인', '즉시 내원 : 고열, 숨참'],
                               'education': ['카페인 줄이기'], 'lines': lines, 'faq': faq}, ensure_ascii=False)
        if '"answer"' in user and 'answer4' not in user:
            return json.dumps({'answer': '메티마졸 15mg 처방해 드려요.' if self.poison else '치료하면 대개 체중도 회복돼요.'},
                              ensure_ascii=False)
        return super().answer(user)


def run_v4(opening=V2_C10, env_extra=None, hints=None, **kw):
    client = V4Client(opening, **kw)
    env = {'NOVA_AGENT_V2': '1', 'NOVA_AGENT_V3': '1', 'NOVA_AGENT_V4': '1'}
    env.update(env_extra or {})
    with mock.patch.dict(os.environ, env):
        os.environ.pop('NOVA_GUIDELINES_DIR', None)
        state = run.prepare()
    patches = []
    if hints:
        for name, val in hints.items():
            p = mock.patch.object(guidelines, name, side_effect=lambda *a, _v=val, **k: _v)
            patches.append(p)
            p.start()
    try:
        run.consult(client, state)
    finally:
        for p in patches:
            p.stop()
    return client


def ledger():
    return run.LAST_RUN['ledger']


def phases_count(led):
    emp = 1 if led and led[0]['kind'] == 'SAY' and led[0]['turn'] == 1 else 0
    q = [e for e in led[1:] if e['kind'] == 'SAY' and e.get('phase') in ('first', 'interview', 'ice', 'sweep')]
    x = [e for e in led if e['kind'] == 'EXAM']
    s = [e for e in led if e['kind'] == 'SAY' and e.get('phase') in ('explain', 'explain-answer')]
    return emp, len(q), len(x), len(s)


class TestU1U2Budget(unittest.TestCase):
    def test_u2_budget_no_refusal(self):  # U2
        c = run_v4()
        led = ledger()
        self.assertEqual(c.turns, 40)
        self.assertEqual(max(e['turn'] for e in led), 40)
        self.assertEqual(phases_count(led), (1, 14, 14, 11))
        self.assertEqual(run.LAST_RUN['counts']['refused'], 0)

    def test_u1_hardcap_with_refusals(self):  # U1: 진찰 거절 2회 + '하나씩' 1회
        c = run_v4(refuse_exams={'결막·공막 시진하겠습니다', '갑상선 잡음 청진하겠습니다'},
                   one_at_a_time={'평소 앓는 병이 있으세요?'})
        led = ledger()
        self.assertLessEqual(c.turns, 40)
        self.assertEqual(max(e['turn'] for e in led), 40)
        self.assertEqual(run.LAST_RUN['counts']['exam_refused'], 2)
        self.assertEqual(run.LAST_RUN['counts']['one_at_a_time'], 1)
        says = [e for e in led if e['kind'] == 'SAY']
        self.assertEqual([e['qid'] for e in says[-3:]], ['x_followup', 'x_warning', 'x_teach'])
        self.assertEqual(says[-1]['text'], v4.TEACH_BACK)
        # 설명 단계 11턴 유지(문진·진찰이 거절을 흡수)
        self.assertEqual(phases_count(led)[3], 11)

    def test_u1_server_cap_lower(self):  # 서버 잔여가 더 적으면 서버 값을 따름
        from agent.encounter import Encounter
        cli = SimpleNamespace(session=lambda: {'turns_remaining': 30, 'initial': {'opening': 'x', 'vital_signs': ''},
                                               'deadline': None})
        enc = Encounter(cli, {'TURN_CAP': 40})
        self.assertEqual((enc.turn, enc.turns_remaining), (20, 20))
        cli2 = SimpleNamespace(session=lambda: {'turns_remaining': 50, 'initial': {}, 'deadline': None})
        self.assertEqual(Encounter(cli2, {'TURN_CAP': 40}).turns_remaining, 40)
        self.assertEqual(Encounter(cli2, {}).turns_remaining, 50)


class TestU3Exams(unittest.TestCase):
    def test_u3_c8flex(self):
        c = run_v4()
        led = ledger()
        ids = [e['qid'] for e in led if e['kind'] == 'EXAM']
        for i in v4.CORE8:
            self.assertIn(i, ids)
        spec = run.LAST_RUN['exam_spec']
        self.assertLessEqual(len(spec), 5)
        self.assertIn('thyroid', spec)  # thyroid_relevant → 특이로
        for bad in ('spo2', 'anthro', 'skin_temp'):
            self.assertNotIn(bad, ids)
        self.assertLess(ids.index('liver_spleen'), ids.index('abd_palp'))
        secs = [SECTION_ORDER.index(v4.banks.EXAM_BY_ID[i][2]) for i in ids]
        self.assertEqual(secs, sorted(secs))
        flex_done = [i for i in v4.FLEX if i in ids and i not in spec]
        self.assertEqual(flex_done, [i for i in v4.FLEX if i not in spec][:len(flex_done)])  # flex 순서대로 채움
        self.assertEqual(len(ids), 14)
        self.assertEqual(len(ids), len(set(ids)))

    def test_u3_u12(self):
        run_v4(env_extra={'NOVA_AGENT_EXAM_POLICY': 'u12'})
        ids = [e['qid'] for e in ledger() if e['kind'] == 'EXAM']
        for i in v4.U12:
            self.assertIn(i, ids)
        self.assertEqual(len(ids), 14)
        self.assertLess(ids.index('liver_spleen'), ids.index('abd_palp'))

    def test_u3_conditionals(self):
        enc = SimpleNamespace(profile={'pediatric': False, 'cc': '체중 감소', 'categories': ['weight_loss']},
                              opening='살이 빠졌다', ledger=[], differentials=['당뇨병'], cfg={})
        ctx = v4._context_text(enc)
        self.assertFalse(v4._allowed(enc, 'spo2', ctx))
        self.assertFalse(v4._allowed(enc, 'anthro', ctx))
        self.assertFalse(v4._allowed(enc, 'eye_signs', ctx))
        self.assertFalse(v4._allowed(enc, 'axillary_ln', ctx))
        enc.profile = {'pediatric': True, 'cc': '키가 작음', 'categories': ['growth']}
        self.assertTrue(v4._allowed(enc, 'anthro', v4._context_text(enc)))
        enc.profile = {'pediatric': False, 'cc': '숨참', 'categories': ['dyspnea']}
        self.assertTrue(v4._allowed(enc, 'spo2', v4._context_text(enc)))


class TestU4U5Interview(unittest.TestCase):
    def test_u4_pair_problem(self):
        for q in ('두통이나 어지럼은 없으세요?', '더위나 땀은 어떠세요?', '목이 붓거나 아프세요?', '두통, 어지럼은 없으세요?',
                  '두통·어지럼은 없으세요?', '부모님과 형제 중 아픈 분 있나요?', '고혈압이나 당뇨 있으세요?'):
            self.assertTrue(saymod.pair_problem(q, 'strict'), q)
        for q in ('술은 얼마나 드세요?', '몇 번이나 깨세요?', v4.FINAL_Q, v4.TEACH_BACK, '발달은 또래와 비슷했나요?'):
            self.assertEqual(saymod.pair_problem(q, 'strict'), '', q)
        bg = [x[0] for x in v4.BG_ADULT.values()] + [x[0] for x in v4.BG_PEDS.values()] + \
            [v4.SAFETY_PREG, v4.SAFETY_SED_EXTRA[0], v4.ICE_EXPECT, v4.ICE_DISEASE, '학교 생활은 어떤가요?'] + \
            [q for q, _, _ in v4.SAFETY_SED] + [q for q, _, _ in v4.SAFETY_THY] + list(v4.SWEEPS)
        for q in bg:
            self.assertEqual(saymod.pair_problem(q, 'strict'), '', q)
            self.assertEqual(saymod.question_problem(q), '', q)
        for q in saymod.NEGSCREEN_PAIRS:  # negscreen 화이트리스트: 허용 + 기존 검증 통과
            self.assertEqual(saymod.pair_problem(q, 'negscreen'), '', q)
            self.assertTrue(saymod.pair_problem(q, 'strict'), q)
            self.assertEqual(saymod.question_problem(q), '', q)
        self.assertTrue(saymod.pair_problem('두통이나 어지럼은 없으세요?', 'negscreen'))  # 증상 탐색은 negscreen에서도 거부

    def test_u4_no_pair_sent(self):
        c = run_v4()
        for e in ledger()[1:]:  # 첫 턴 = 공감 서술(걱정 답이면 ice로 재분류)
            if e['kind'] == 'SAY' and e.get('phase') in ('first', 'interview', 'ice', 'sweep'):
                self.assertEqual(saymod.pair_problem(e['text'], 'negscreen'), '', e['text'])
                self.assertEqual(saymod.question_problem(e['text']), '', e['text'])
        texts = [e['text'] for e in ledger() if e['kind'] == 'SAY']
        self.assertNotIn('더위나 땀은 어떠세요?', texts)
        self.assertNotIn('목이 붓거나 아프세요?', texts)
        self.assertIn('혹시 임신 가능성은 있으세요?', texts)
        self.assertIn('천식 있으세요?', texts)

    def test_u4_strict_policy(self):
        run_v4(env_extra={'NOVA_AGENT_PAIR_POLICY': 'strict'})
        for e in ledger()[1:]:
            if e['kind'] == 'SAY' and e.get('phase') in ('first', 'interview', 'ice', 'sweep'):
                self.assertEqual(saymod.pair_problem(e['text'], 'strict'), '', e['text'])

    def test_u5_sweep_followup(self):
        self.assertEqual(saymod.symptom_topic('가슴이 자주 두근거려요'), '두근거림')
        run_v4()
        texts = [e['text'] for e in ledger() if e['kind'] == 'SAY']
        i = texts.index(v4.SWEEPS[0])
        self.assertEqual(texts[i + 1], '두근거림에 대해 자세히 말씀해 주세요')
        self.assertEqual(texts[i + 2], v4.SWEEPS[1])

    def test_u5_negative_sweep_stops(self):
        run_v4(sweep_replies=['아니요, 없어요.', '두근거려요'])
        texts = [e['text'] for e in ledger() if e['kind'] == 'SAY']
        self.assertIn(v4.SWEEPS[0], texts)
        self.assertNotIn(v4.SWEEPS[1], texts)


class TestU6U7Explain(unittest.TestCase):
    def test_u6_question_slots(self):
        c = run_v4()
        says = [e for e in ledger() if e['kind'] == 'SAY' and e.get('phase') in ('explain', 'explain-answer')]
        qids = [e['qid'] for e in says]
        self.assertEqual(qids[0], 'x_dx')
        self.assertEqual(qids[1], 'x_options')  # '치료하면 좋아질 수 있나요?' → options 앞당김(추가 턴 0)
        j = qids.index('x_final')
        self.assertIn(qids[j + 1], ('x_answer', 'x_followup', 'x_options', 'x_tests', 'x_link', 'x_concern', 'x_caution'))
        self.assertEqual(says[j + 1]['text'], run.LAST_RUN['faq']['duration'])  # FAQ duration(KB 검증 답 우선)
        self.assertEqual(qids[-3:], ['x_followup', 'x_warning', 'x_teach'])
        self.assertEqual(len(says), 11)

    def test_u7_templates(self):
        tpl = [v4.FALLBACK[k] for k in ('link', 'tests', 'options', 'followup', 'warning', 'dx_generic', 'answer',
                                        'emergency_followup')] + list(v4.FAQ_DEFAULT.values()) + \
            [s for _, s in v4.SED_MUSTS] + [v4.SED_WARNING, '그레이브스병 가능성이 높아 보여요.',
                                            '진찰 소견은 암보다 지금 진단 쪽에 맞아요.']
        spec_examples = [  # §5.1·§5.4 예시 서술(설계서)
            '갑상샘 호르몬이 넘치는 그레이브스병으로 보여요.', '약으로 대부분 좋아지고, 요오드·수술도 있어요.',
            '그래서 살이 빠지고 손이 떨리고 더웠어요.', '목과 눈 소견이 암보다 갑상샘 병에 맞아요.',
            '피검사로 호르몬과 원인 항체를 확인해요.', '약 먹다 열·목 통증이 생기면 바로 연락하세요.',
            '1주 뒤 결과 보러 오시고 커피는 줄이세요.', '숨참·불규칙한 맥·고열이면 바로 오세요.',
            '갑자기 끊으면 위험해 오늘은 끊지 않아요.', '운전·술·약국 수면제는 피하세요.', '경련·환각·혼동이면 바로 오세요.',
            '걱정 많으셨을 텐데, 암보다 갑상샘 병 쪽이에요.', '피 뽑을 때 잠깐 따끔하고 금방 끝나요.',
            '오늘 피를 뽑고 1주 뒤 결과를 봐요.', '결과는 1주 안에 나와 다시 설명할게요.', '약은 보통 1~2년 쓰며 피검사로 조절해요.',
            '약 말고 방사성 요오드나 수술도 있어요.', '호르몬이 맞춰지면 체중도 대개 돌아와요.', '커피를 줄이고 무리한 운동은 피하세요.',
            '천천히 줄이며 잠 습관도 같이 잡아요.', '약은 검사 결과 보고 상의해 정해요.', '말씀하신 증상들이 이 병과 잘 맞아요.',
            '정확히 확인하려고 피검사를 할게요.', '검사 결과를 보고 치료 방법을 같이 정해요.', '1~2주 뒤 결과 보고 다음 치료를 정해요.',
            '숨참·흉통·의식 변화·고열 시 바로 오세요.', '검사로 확인할 병으로 보여요.', '검사 결과를 보고 자세히 설명할게요.',
            '오늘 바로 응급실에서 외과 진료를 받으세요.']
        for s in tpl + spec_examples:
            self.assertLessEqual(nlen(s), 30, s)
            self.assertTrue(saymod.statement_ok(s), (s, saymod.say_problem(s), saymod.safety_problem(s)))
        musts = ' '.join(s for _, s in v4.SED_MUSTS)
        for pat, _ in v4.SED_MUSTS:
            self.assertTrue(re.search(pat, musts))
        for q in (v4.FINAL_Q, v4.TEACH_BACK, v4.ICE_EXPECT):
            self.assertEqual(saymod.question_problem(q), '', q)

    def test_u7_sedative_musts(self):
        c = run_v4(opening=V2_C01, first_reply='네.', final_reply='아니요, 없어요.')
        texts = [e['text'] for e in ledger() if e['kind'] == 'SAY']
        self.assertIn('갑자기 끊으면 위험해 오늘은 끊지 않아요.', texts)
        self.assertIn('운전·술·약국 수면제는 피하세요.', texts)
        self.assertIn(v4.SED_WARNING, texts)
        self.assertIn('수면제는 마지막으로 언제 드셨어요?', texts)
        self.assertLessEqual(c.turns, 40)
        self.assertEqual([e['qid'] for e in ledger() if e['kind'] == 'SAY'][-1], 'x_teach')


class TestU8Safety(unittest.TestCase):
    def test_u8_poisoned_hint_and_llm(self):
        c = run_v4(poison=True, hints={'hint_plan': '[진료지침 발췌]\n' + POISON + '\n',
                                       'hint_interview': '[진료지침 발췌]\n' + POISON + '\n',
                                       'hint_dx': ''})
        note, dx = c.diagnosed
        texts = [e['text'] for e in ledger() if e['kind'] == 'SAY']
        p_txt = '\n'.join(note['P'][f] for f in RECORD_FIELDS['P'])
        for t in texts + p_txt.split('\n'):
            self.assertIsNone(DOSE_RE.search(t), t)
            self.assertNotIn('시작해요', t)
            self.assertNotIn('메티마졸', t)
            self.assertNotIn('프로프라놀롤', t)
        for f in ('treatment', 'disposition', 'follow_up'):
            for l in note['P'][f].split('\n'):
                self.assertEqual(saymod.safety_problem(l), '', (f, l))
        for e in ledger():
            if e['kind'] == 'SAY' and e.get('phase') in ('explain', 'explain-answer'):
                self.assertEqual(saymod.safety_problem(e['text']), '', e['text'])
                if e.get('qid') not in ('x_final', 'x_teach'):
                    self.assertEqual(saymod.say_problem(e['text']), '', e['text'])

    def test_u8_sanitize(self):
        out = guidelines.sanitize('[출처: 테스트]\n' + POISON + '\nDepartment of Medicine, X University\n'
                                  '증상이 지속되면 재평가한다(권고수준: B).')
        self.assertNotIn('15mg', out)
        self.assertNotIn('메티마졸', out)
        self.assertNotIn('Department', out)
        self.assertNotIn('권고수준', out)
        self.assertIn('갑상선 기능 검사', out)
        self.assertLessEqual(len(guidelines.sanitize('가나다라. ' * 1000)), guidelines.SAN_MAX + 10)


class TestU9U11Record(unittest.TestCase):
    def enc(self, exams=(), says=()):
        led = [{'kind': 'SAY', 'text': q, 'reply': a, 'phase': 'interview'} for q, a in says]
        return SimpleNamespace(done_exams=list(exams), ledger=led, opening='')

    def test_u9_claims(self):
        line = '- 외래 : 활력 안정, 의식 변화 없음'
        self.assertEqual(record.unsupported_claims(self.enc(), line), '- 외래 : 활력 안정')
        self.assertEqual(record.unsupported_claims(self.enc(['mental']), line), line)
        self.assertEqual(record.unsupported_claims(self.enc(['conj']), '황달·부종·의식 변화 없음'), '황달 없음')
        self.assertEqual(record.unsupported_claims(self.enc(says=[('가슴이 아프세요?', '아니요')]), '흉통 없음'), '흉통 없음')
        self.assertEqual(record.unsupported_claims(self.enc(), '흉통 없음'), '')

    def test_u9_run(self):
        c = run_v4()
        note, _ = c.diagnosed
        self.assertNotRegex(note['P']['disposition'], r'의식\s*변화\s*없')

    def test_u10_ros(self):
        enc = SimpleNamespace(profile={'pediatric': False}, ledger=[], facts=[])
        hpi = '32세 여자.\n가슴 통증 (-), 묽은 변 (+)\n두근거림 (+)'
        extra = note2.reconcile_ros(enc, [], hpi)
        got = {e['key']: e['pol'] for e in extra}
        self.assertEqual(got.get('ros.Chest pain'), '-')
        self.assertEqual(got.get('ros.Palpitation'), '+')
        self.assertNotIn('ros.Diarrhea', got)
        fixed = note2.render_fixed(enc, {}, facts=extra)
        self.assertIn('Chest pain (-)', fixed['ros'])
        facts = [{'id': 'F1', 'turn': 3, 'sec': 'ros', 'key': 'other', 'label': '어지럼', 'pol': '-', 'detail': ''}]
        self.assertEqual({e['key']: e['pol'] for e in note2.reconcile_ros(enc, facts, '')}.get('ros.Dizziness'), '-')

    def test_u11_education(self):
        edu = record.education_text(['그레이브스병으로 보여요.'], '카페인 줄이기\n눈 관리', v4=True)
        self.assertNotIn('다음 방문', edu)
        self.assertIn('진료 중 설명함', edu)
        enc = SimpleNamespace(cfg={'GUIDE_CITE': 1}, gl_sources=['A 지침 (KR, 2024)', 'B (US)'])
        cite = guidelines.cite_line(enc)
        self.assertEqual(len(cite.split('\n')), 1)
        self.assertTrue(cite.startswith('참고 지침 : '))
        c = run_v4()
        note, _ = c.diagnosed
        self.assertNotIn('다음 방문 시 교육 예정', note['P']['education'])
        self.assertIn('진료 중 설명함', note['P']['education'])

    def test_u11_late_ice_and_safety_net(self):
        c = run_v4()
        note, _ = c.diagnosed
        self.assertIn('궁금', note['S']['hpi'])


class TestU12U13Guidelines(unittest.TestCase):
    def test_u12_index_none(self):
        guidelines.set_index(None)
        enc = SimpleNamespace(cfg={'GUIDE': 1}, differentials=['그레이브스병 (Graves disease)'], dx='그레이브스병')
        self.assertEqual(guidelines.hint_interview(enc), '')
        self.assertEqual(guidelines.hint_interview(enc, clean=True), '')
        self.assertEqual(guidelines.hint_dx(enc), '')
        self.assertEqual(guidelines.hint_plan(enc), '')
        self.assertEqual(guidelines.hint_plan(enc, kinds_mgmt=['dx', 'fu'], kinds_ovw=['dx', 'fu', 'edu'], clean=True), '')

    @unittest.skipUnless(os.path.isdir(os.path.join(ROOT, '..', 'nova-guidelines-2026', 'guidelines')), '로컬 코퍼스 없음')
    def test_u12_prepare_fast(self):
        gdir = os.path.abspath(os.path.join(ROOT, '..', 'nova-guidelines-2026', 'guidelines'))
        t0 = time.time()
        with mock.patch.dict(os.environ, {'NOVA_GUIDELINES_DIR': gdir}):
            state = run.prepare()
        self.assertLess(time.time() - t0, 10)
        self.assertIsNotNone(state['guidelines'])
        guidelines.set_index(state['guidelines'])
        try:
            enc = SimpleNamespace(cfg={'GUIDE': 1}, differentials=['그레이브스병 (Graves disease)'],
                                  dx='그레이브스병에 의한 갑상샘항진증')
            h = guidelines.hint_plan(enc, kinds_mgmt=['dx', 'fu'], kinds_ovw=['dx', 'fu', 'edu'], clean=True)
            self.assertIsNone(DOSE_RE.search(h or ''), h)
        finally:
            guidelines.set_index(None)

    @unittest.skipUnless(os.path.isdir(os.path.join(ROOT, '..', 'code_js')), 'code_js 없음')
    def test_u13_control_prompts_equal_code_js(self):
        outs = {}
        for d in ('code_v4', 'code_js'):
            code = os.path.abspath(os.path.join(ROOT, '..', d)) if d == 'code_js' else ROOT
            env = {k: v for k, v in os.environ.items() if k != 'NOVA_DEV_KEY'}
            p = subprocess.run([sys.executable, os.path.join(HERE, 'u13_harness.py'), code, HERE], capture_output=True,
                               text=True, env=env, timeout=300)
            line = next((l for l in p.stdout.splitlines() if l.startswith('U13JSON')), None)
            self.assertIsNotNone(line, p.stderr[-2000:])
            outs[d] = json.loads(line[len('U13JSON'):])
        for k in ('plan_q', 'dx', 'plan_say'):
            self.assertTrue(outs['code_v4'][k], k)
            self.assertEqual(outs['code_v4'][k], outs['code_js'][k], k)
            self.assertTrue(any('HINT' in p for p in outs['code_v4'][k]), k)

    def test_u13_preset_js_bal44(self):
        with mock.patch.dict(os.environ, {'NOVA_AGENT_TURN_PRESET': 'js_bal44', 'NOVA_AGENT_GUIDE': '1'}):
            cfg = run.load_config()
        self.assertEqual((cfg['V3'], cfg['V4'], cfg['TURN_CAP'], cfg['EXAM_N'], cfg['EXPLAIN_N']), (0, 0, 50, 11, 9))

    def test_preset_json(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            pj = os.path.join(td, 'preset.json')
            with open(pj, 'w', encoding='utf-8') as f:
                json.dump({'V3': 0, 'TURN_PRESET': 'bal44', 'GUIDE': 1, 'TURN_CAP': 50, 'BOGUS': 1}, f)
            with mock.patch.object(run, 'PRESET_FILE', pj):
                cfg = run.load_config()
            self.assertEqual((cfg['V3'], cfg['TURN_PRESET'], cfg['TURN_CAP'], cfg['EXAM_N']), (0, 'bal44', 50, 11))
            with open(pj, 'w', encoding='utf-8') as f:
                f.write('{broken')
            with mock.patch.object(run, 'PRESET_FILE', pj):
                cfg = run.load_config()
            self.assertEqual((cfg['V4'], cfg['TURN_PRESET'], cfg['TURN_CAP']), (1, 'v4_40', 40))
        with mock.patch.object(run, 'PRESET_FILE', '/nonexistent/preset.json'):
            cfg = run.load_config()
        self.assertEqual((cfg['TURN_PRESET'], cfg['TURN_CAP'], cfg['INTERVIEW_Q'], cfg['EXAM_N'], cfg['EXPLAIN_N'],
                          cfg['EXAM_POLICY'], cfg['EXPLAIN_MODE']), ('v4_40', 40, 14, 14, 11, 'c8flex', 'v4'))


class RedFlagClient(V4Client):
    def exam(self, content, request_id=None):
        r = super().exam(content, request_id)
        if '복부 촉진' in content:
            r = dict(r, result='우하복부 압통(+), 근성방어(+), 반발통(+)')
        return r


class TestEmergencyAndGuideSwitch(unittest.TestCase):
    def test_exam_red_flag_emergency(self):
        client = RedFlagClient(V2_C10)
        with mock.patch.dict(os.environ, {'NOVA_AGENT_V4': '1'}):
            state = run.prepare()
        run.consult(client, state)
        note, _ = client.diagnosed
        self.assertIn('응급', note['P']['disposition'])
        fu = next(e['text'] for e in ledger() if e.get('qid') == 'x_followup')
        self.assertRegex(fu, r'오늘\s*바로|응급실')
        self.assertNotIn('x_caution', [e.get('qid') for e in ledger()])

    def test_guide_off_switch(self):
        import tempfile
        with mock.patch.dict(os.environ, {'NOVA_AGENT_GUIDE': '0'}):
            self.assertEqual(run.load_config()['GUIDE'], 0)
        with tempfile.TemporaryDirectory() as td:
            pj = os.path.join(td, 'preset.json')
            with open(pj, 'w', encoding='utf-8') as f:
                f.write('{"GUIDE": 0}')
            with mock.patch.object(run, 'PRESET_FILE', pj):
                cfg = run.load_config()
                st = run.prepare()
            self.assertEqual((cfg['GUIDE'], cfg['TURN_CAP'], cfg['EXAM_POLICY']), (0, 40, 'c8flex'))
            self.assertIsNone(st['guidelines'])
        guidelines.set_index(object())  # 인덱스가 있어도 GUIDE=0이면 hint 없음
        try:
            enc = SimpleNamespace(cfg={'GUIDE': 0}, differentials=['그레이브스병'], dx='그레이브스병')
            self.assertEqual(guidelines.hint_plan(enc), '')
            self.assertEqual(guidelines.hint_interview(enc, clean=True), '')
        finally:
            guidelines.set_index(None)


class TestDxNormalize(unittest.TestCase):
    def test_unsupported_modifier_removed(self):
        from agent.assess import normalize_dx
        self.assertEqual(normalize_dx('급성 전이성 중이염', 'Acute Otitis Media'), '급성 중이염 (Acute Otitis Media)')
        self.assertEqual(normalize_dx('전이성 폐암', 'Metastatic lung cancer'), '전이성 폐암 (Metastatic lung cancer)')
        self.assertEqual(normalize_dx('만성 폐쇄성 폐질환 급성 악화', 'Acute exacerbation of COPD'),
                         '만성 폐쇄성 폐질환 급성 악화 (Acute exacerbation of COPD)')
        self.assertEqual(normalize_dx('급성 충수염', 'Acute appendicitis'), '급성 충수염 (Acute appendicitis)')
        self.assertEqual(normalize_dx('우측 급성 중이염', ''), '우측 급성 중이염')


class TestU14Regression(unittest.TestCase):
    def test_u14_peds_and_v3_explain_arm(self):
        c = run_v4(opening=V2_C03, first_reply='네.', final_reply='아니요.')
        self.assertLessEqual(c.turns, 40)
        exams = [e['qid'] for e in ledger() if e['kind'] == 'EXAM']
        self.assertIn('anthro', exams)
        c = run_v4(env_extra={'NOVA_AGENT_EXPLAIN_MODE': 'v3'})
        self.assertLessEqual(c.turns, 40)
        self.assertIsNotNone(c.diagnosed)

    def test_u14_llm_error(self):
        c = run_v4(llm='error')
        self.assertIsNotNone(c.diagnosed)
        self.assertLessEqual(c.turns, 40)
        says = [e for e in ledger() if e['kind'] == 'SAY']
        self.assertEqual(says[-1]['qid'], 'x_teach')


if __name__ == '__main__':
    unittest.main()

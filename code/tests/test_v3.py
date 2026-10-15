"""v3 테스트: 질문 검증기(서버 프로브 실측 사례), 안전 금지 패턴, probe50 턴 배분 드라이런. API 없이 실행.
test_agent.py에서 import되어 함께 돈다(cd tests && python3 test_agent.py)."""
import json
import os
import re
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import run  # noqa: E402
from agent import bank2, kb, v3  # noqa: E402
from agent import say as saymod  # noqa: E402
from nova_sdk import RECORD_FIELDS  # noqa: E402
from test_v2 import V2_C01, V2_C03, V2_C10, V2Client, nlen  # noqa: E402

TRUNCATED_BY_SERVER = ['힘드셨겠어요. 낮에 졸리세요?', '몇 시에 자고 몇 시에 깨세요?', '언제 드세요? 얼마나 드세요?',
                       '누구와 사세요, 무슨 일 하세요?', '누구와 사시고 무슨 일 하세요?', '다른 지병이나 수술받은 적 있으세요?',
                       '잠들기 어렵나요, 자주 깨나요?', '이해되셨어요? 한번 말해 보시겠어요?',
                       '많이 걱정되셨겠어요. 식사량은 예전과 비교해 어떠세요?', '잘 웃으시네요, 그런데 우유는 마셔요?']
REFUSED_ONE_AT_A_TIME = ['그 밖에 달라진 점을 다 말씀해 주세요', '드시는 약을 전부 말씀해 주세요', '최근 석 달간 변화를 전부 말씀해 주세요',
                         '수면제 드신 경과를 다 말씀해 주세요', '출생 때부터 지금까지 말씀해 주세요']
PASSED_INTACT = ['두근거림에 대해 자세히 말씀해 주세요', '그 밖에 또 불편한 건 없으세요?', '더위나 땀은 어떠세요?',
                 '두통, 어지럼, 구토는 없으세요?', '아빠와 엄마 키는 각각 몇이에요?', '언제 바로 오셔야 하는지 말씀해 보세요',
                 '어떤 검사를 받는지 말씀해 보시겠어요?', '가장 걱정되시는 게 뭐예요?', '대변은 어떠세요?']


class V3Client(V2Client):
    """v3 프롬프트(plan_q3·exams3·plan_say3·answer3)에 답하는 가짜 서버+LLM. pair_first_only: 짝 질문에 앞 항목만 답."""

    def __init__(self, *a, pair_first_only=True, **kw):
        super().__init__(*a, **kw)
        self.pair_first_only = pair_first_only

    def say(self, content, request_id=None):
        if self.pair_first_only and v3.pair_items(content):
            self._turn(content)
            a, b = v3.pair_items(content)
            ans = f'{a}은 좀 있어요.'
            self.events.append(('SAY', content, ans))
            return {'status': 'OK', 'content': ans, 'turn': self.turns, 'turns_remaining': 50 - self.turns}
        if '말씀해 보세요' in content:
            self._turn(content)
            ans = '네, 알겠어요.'
            self.events.append(('SAY', content, ans))
            return {'status': 'OK', 'content': ans, 'turn': self.turns, 'turns_remaining': 50 - self.turns}
        if content.endswith('보여요.') or '같아요' in content:
            self._turn(content)
            ans = '치료는 어떻게 하나요?'
            self.events.append(('SAY', content, ans))
            return {'status': 'OK', 'content': ans, 'turn': self.turns, 'turns_remaining': 50 - self.turns}
        return super().say(content, request_id)

    def answer(self, user):
        if '"topic|pair|closed"' in user:
            return json.dumps({'differential': ['그레이브스병', '당뇨병'], 'questions': [
                {'slot': 'free', 'type': 'topic', 'q': '두근거림에 대해 자세히 말씀해 주세요'},
                {'slot': 'free', 'type': 'closed', 'q': '몇 시에 자고 몇 시에 깨세요?'},
                {'slot': 'free', 'type': 'pair', 'q': '두통이나 어지럼은 없으세요?'},
                {'slot': 'free', 'type': 'topic', 'q': '드시는 약을 전부 말씀해 주세요'},
                {'slot': 'wl_sweat', 'type': 'closed', 'q': '땀이 많아지셨나요?'},
                {'slot': 'free', 'type': 'topic', 'q': '생리에 대해 자세히 말씀해 주세요'}]}, ensure_ascii=False)
        if '"lines"' in user:
            return json.dumps({'tests': [{'name': 'TSH, free T4', 'reason': '확인'}],
                               'treatment': ['메티마졸 15mg 하루 1회 시작', '수면제 추가 처방'],
                               'follow_up': ['재진 : 1~2주 후 결과 확인', '즉시 내원 : 열'], 'education': ['카페인 줄이기'],
                               'lines': {'dx': '갑상선 호르몬이 넘치는 병으로 보여요.', 'meaning': '호르몬이 많아 살이 빠지고 떨려요.',
                                         'concern': '암보다는 갑상선 문제 가능성이 커요.', 'tests': '피검사로 호르몬과 항체를 볼게요.',
                                         'treatment': '메티마졸 15mg 드릴게요.', 'warning': '열이 나요.',
                                         'followup': '1~2주 뒤 결과 보고 치료를 정해요.', 'lifestyle': '카페인은 줄이세요.'},
                               'faq': {'results': '결과는 일주일쯤 뒤에 나와요.', 'treatment': '약 15mg 처방해 드려요.'}},
                              ensure_ascii=False)
        if '"exams": [{"id"' in user:  # GEN 진찰 계획(근거 없는 항목·목록 밖 id·중복은 코드가 제외)
            ids = ['thyroid', 'eye_signs', 'radial', 'post_tremor', 'skin_temp', 'thyroid_bruit', 'heart', 'abd_palp',
                   'liver_spleen', 'nonexistent']
            if '도현' in self.opening:
                ids = ['anthro', 'growth_chart', 'tanner', 'body_prop', 'dysmorph', 'thyroid', 'general', 'striae']
            return json.dumps({'exams': [{'id': i, 'why': '감별 확인' if i == 'skin_temp' else '그레이브스병 — 소견 확인'}
                                         for i in ids]},
                              ensure_ascii=False)
        if '"answer"' in user:
            return json.dumps({'answer': '검사 결과 보고 같이 정해요.'}, ensure_ascii=False)
        return super().answer(user)


def run_v3(opening, preset=None, **kw):
    client = V3Client(opening, **kw)
    env = {'NOVA_AGENT_V2': '1', 'NOVA_AGENT_V3': '1'}
    if preset:
        env['NOVA_AGENT_TURN_PRESET'] = preset
    with mock.patch.dict(os.environ, env):
        state = run.prepare()
    run.consult(client, state)
    return client


class TestV3Validators(unittest.TestCase):
    def test_server_truncated_patterns_rejected(self):
        for q in TRUNCATED_BY_SERVER + REFUSED_ONE_AT_A_TIME:
            self.assertTrue(saymod.question_problem(q), q)

    def test_intact_patterns_pass(self):
        for q in PASSED_INTACT + v3.SWEEPS + [v3.TEACH_BACK, v3.FINAL_Q]:
            self.assertEqual(saymod.question_problem(q), '', q)
        for t in v3.CAT_TOPIC.values():
            self.assertEqual(saymod.question_problem(v3.topic_q(t)), '', t)

    def test_pair_parse(self):
        self.assertEqual(v3.pair_items('두통이나 어지럼은 없으세요?'), ('두통', '어지럼'))
        self.assertEqual(v3.pair_items('더위나 땀은 어떠세요?'), ('더위', '땀'))
        self.assertIsNone(v3.pair_items('땀이 많아지셨나요?'))
        self.assertFalse(v3.pair_second_answered('두통이나 어지럼은 없으세요?', '약 안 먹으면 머리가 아파요.'))
        self.assertTrue(v3.pair_second_answered('수술이나 입원은 하셨어요?', '수술도 입원도 한 적 없어요.'))
        self.assertEqual(v3.josa('어지럼', '은', '는'), '어지럼은')
        self.assertEqual(v3.josa('커피', '은', '는'), '커피는')

    def test_safety_bans(self):
        bad = ['오늘 끊진 않고, 확인한 최소량만 1~2주분 드려요.', '1~2주마다 10~25%씩 점진 감량', 'TFT 확인 후 항갑상샘제(메티마졸) 시작 고려',
               '활력징후 안정, 급성 위험 징후 없어 입원 불필요', '1~2주 뒤 결과 보고 약을 시작해요.', '프로프라놀롤 20 mg 하루 3회']
        for s in bad:
            self.assertTrue(saymod.safety_problem(s), s)
        ok = ['1~2주 뒤 결과 보고 치료를 정해요.', '자세히 설명드려요.', '갑자기 끊으면 위험해서 오늘 끊진 않아요.']
        for s in ok:
            self.assertEqual(saymod.safety_problem(s), '', s)

    def test_safe_templates_clean(self):
        from agent import explain
        for k in kb.KB:  # v2c KB 템플릿이 safe_plan_line 뒤 v3 금지 패턴도 통과
            for f in ('treatment', 'follow_up'):
                for l in k.get(f) or []:
                    out = explain.safe_plan_line(l, f, k.get('admit_if', ''))
                    self.assertEqual(saymod.safety_problem(out), '', (k['id'], f, out))
        for kid, musts in v3.SAFE_MUST_SAY.items():
            for _, s in musts:
                self.assertEqual(saymod.safety_problem(s), '', s)
                self.assertEqual(saymod.say_problem(s), '', s)
        for _, qs in v3.SAFETY_QS:
            for q in qs:
                self.assertEqual(saymod.question_problem(q), '', q)

    def test_dedup(self):
        self.assertEqual(len(saymod.dedup_lines(['급격한 중단 금지', '급격한 중단 금지.', '- 급격한  중단 금지'])), 1)


class TestV3DryRun(unittest.TestCase):
    def check(self, c):
        self.assertIsNotNone(c.diagnosed)
        note, dx = c.diagnosed
        for s, fs in RECORD_FIELDS.items():
            for f in fs:
                self.assertIsInstance(note[s][f], str)
        led = run.LAST_RUN['ledger']
        says = [e for e in led if e['kind'] == 'SAY' and not e.get('refused')]
        self.assertTrue(all(nlen(e['text']) <= 30 for e in says))
        self.assertLessEqual(c.turns, 50)
        # 질문 SAY는 모두 v3 검증 통과(한 문장·한 질문)
        for e in says:
            if e.get('phase') in ('first', 'interview', 'ice', 'sweep') or e.get('qid') in ('x_teach', 'x_final'):
                self.assertEqual(saymod.question_problem(e['text']), '', e['text'])
        # 안전: P칸·설명 SAY에 금지 패턴 0, P칸 중복 줄 0
        for f in ('treatment', 'disposition', 'follow_up'):
            lines = [l[2:] for l in note['P'][f].split('\n') if l.startswith('- ')]
            for l in lines:
                self.assertEqual(saymod.safety_problem(l), '', (f, l))
            self.assertEqual(len(saymod.dedup_lines(lines)), len(lines), (f, lines))
        for e in says:
            if e.get('phase') in ('explain', 'explain-answer'):
                self.assertEqual(saymod.safety_problem(e['text']), '', e['text'])
        self.assertLessEqual(run.LAST_RUN['budget']['doctor_calls'], 10)
        return note, dx, led

    def test_c10_probe50(self):
        c = run_v3(V2_C10, preset='probe50')
        note, dx, led = self.check(c)
        self.assertIn('그레이브스병', dx)
        says = [e for e in led if e['kind'] == 'SAY']
        self.assertEqual(says[0]['phase'], 'empathy')
        self.assertNotIn('?', says[0]['text'])
        self.assertEqual(says[1]['text'], v3.topic_q(v3.CAT_TOPIC['weight_loss']))
        self.assertTrue(any(e.get('phase') == 'sweep' for e in says))
        self.assertIn('혹시 임신 가능성은 있으세요?', [e['text'] for e in says])
        # 짝 질문 꼬리 질문
        texts = [e['text'] for e in says]
        self.assertIn('두통이나 어지럼은 없으세요?', texts)
        self.assertIn('어지럼은 어떠세요?', texts)
        self.assertNotIn('몇 시에 자고 몇 시에 깨세요?', texts)
        self.assertNotIn('드시는 약을 전부 말씀해 주세요', texts)
        # 진찰: 공통 행 + 특이 + 활력징후 마지막
        exams = [e for e in led if e['kind'] == 'EXAM']
        self.assertEqual(len(exams), run.PRESETS['probe50']['EXAM_N'] + 1)
        self.assertIn('활력징후', exams[-1]['text'])
        names = ' '.join(e['text'] for e in exams)
        for w in ('심음', '폐 청진', '복부 촉진', '결막', '하지 말초', '갑상선 촉진', '전반적 외관'):
            self.assertIn(w, names)
        # 설명: 진단·검사·경고·재진·teach-back, 경고는 4개 이상
        expl = run.LAST_RUN['explained']
        self.assertFalse(saymod.missing_elements(expl, dx), expl)
        self.assertIn(v3.TEACH_BACK, texts)
        self.assertNotIn('메티마졸 15mg 드릴게요.', texts)
        self.assertNotIn('메티마졸', note['P']['treatment'])
        self.assertNotIn('15mg', note['P']['treatment'])
        self.assertNotIn('입원 불필요', note['P']['disposition'])
        # 환자 질문 '치료는 어떻게 하나요?' → 치료 문장이 바로 뒤에 온다
        i = next(k for k, e in enumerate(says) if e.get('qid') == 'x_dx')
        self.assertIn(says[i + 1].get('qid'), ('x_treatment', 'x_answer'))
        # teach-back 실패 → 경고 재설명 1회
        j = texts.index(v3.TEACH_BACK)
        self.assertTrue(j + 1 == len(texts) or '바로' in texts[j + 1], texts[j:])
        self.assertGreaterEqual(c.turns, 46)

    def test_c10_gen(self):  # 일반화 우선(기본 gen46): 고정 공통 진찰·은행 보충 없음, 진찰은 luna 근거 있는 것만
        c = run_v3(V2_C10)
        note, dx, led = self.check(c)
        self.assertIn('그레이브스병', dx)
        self.assertLessEqual(c.turns, 46)
        exams = [e['qid'] for e in led if e['kind'] == 'EXAM']
        self.assertNotIn('skin_temp', exams)      # 근거 없음
        self.assertNotIn('liver_spleen', exams)   # 복부 촉진과 중복
        self.assertNotIn('vitals', exams)         # 시작 정보에 활력징후 있음
        self.assertNotIn('mental', exams)         # 고정 공통 세트 없음
        self.assertEqual(exams, ['thyroid', 'eye_signs', 'radial', 'post_tremor', 'thyroid_bruit', 'heart', 'abd_palp'])
        texts = [e['text'] for e in led if e['kind'] == 'SAY']
        self.assertEqual(texts[1], v3.topic_q('체중 감소'))  # 주호소 명사구 주제
        self.assertIn('혹시 임신 가능성은 있으세요?', texts)  # 안전 slot은 보장
        self.assertIn(v3.TEACH_BACK, texts)
        self.assertEqual(len(texts), len(set(texts)) + texts.count(v3.TEACH_BACK) - 1 + sum(
            1 for t in set(texts) if texts.count(t) > 1 and '바로' in t))  # 경고 재설명 외 중복 SAY 없음

    def test_c01_safety(self):
        c = run_v3(V2_C01)
        note, dx, led = self.check(c)
        texts = [e['text'] for e in led if e['kind'] == 'SAY']
        self.assertTrue(any('운전' in t for t in texts))
        self.assertTrue(any(re.search(r'(끊(진|지)\s*않|갑자기\s*끊)', t) for t in texts))
        self.assertIn('급격한 중단 금지', note['P']['treatment'])
        self.assertEqual(note['P']['treatment'].count('급격한 중단 금지'), 1)
        self.assertIn('조기 연락', note['P']['follow_up'])
        self.assertTrue(any('남은 수면제' in t for t in texts))  # 보유량 확인
        self.assertNotIn('주분', note['P']['treatment'])
        self.assertNotIn('%', note['P']['treatment'])
        self.assertFalse(any('임신' in t for t in texts))

    def test_c03_peds(self):
        c = run_v3(V2_C03)
        note, dx, led = self.check(c)
        exams = ' '.join(e['text'] for e in led if e['kind'] == 'EXAM')
        self.assertIn('신체 계측', exams)
        self.assertIn('해당 없음(소아)', note['S']['sh'])

    def test_bal44_v3(self):
        c = run_v3(V2_C10, preset='bal44', patient='no')
        self.check(c)
        self.assertLessEqual(c.turns, 46)


if __name__ == '__main__':
    unittest.main()

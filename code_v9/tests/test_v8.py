"""v8 단위·드라이런 테스트(개발 키·네트워크 없음). sota34_analysis §9.12 / §7.

실행: env -u NOVA_DEV_KEY PYTHONPATH=<scratchpad>/pylib python3 -m pytest -q -p no:cacheprovider tests
"""
import csv
import json
import os
import re
import sys
import tempfile
import unicodedata
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from nova_sdk import RECORD_FIELDS, NovaError  # noqa: E402

import run  # noqa: E402
from agent import banks, cpx, explain, facts, guidelines, note2, record, say as saymod  # noqa: E402
from agent.util import validate_question  # noqa: E402

C01 = '저는 박선희이고, 예순두 살 여자이다. 잠을 잘 못 자서 병원에 왔다. 수면제를 처방해 달라고 왔다.'
C03 = ('이름은 김도현이고, 여섯 살 남자아이이다. 엄마 김지영, 서른일곱 살이 보호자로 함께 왔다. 엄마는 도현이 키가 또래에 비해 '
       '많이 작은 것 같아 걱정이 된다고 말했다. 엄마는 일 년 전부터 주변에서 도현이가 또래보다 작다는 말을 듣기 시작했다고 했다. '
       '엄마가 집에서 키를 재보니, 일 년 전에는 백 센티미터였고 지금은 백오 센티미터 정도였다.')
C10 = ('이름은 최윤정이고, 나는 서른두 살 여자이다. 최근 석 달 동안 살이 많이 빠져서 병원에 오게 되었다. 원래 몸무게는 '
       '오십육 키로그람 정도였는데, 최근 석 달 사이에 칠 키로그람 정도 빠져서 지금은 사십구 키로그람 정도이다. '
       '저절로 살이 빠져서 걱정이 되었다. 키는 백육십사 센티미터이다.')
VITALS = '혈압 : 138/72 mmHg\n맥박 : 102 회/분\n호흡 : 19 회/분\n체온 : 36.9°C'


def nlen(s):
    return len(unicodedata.normalize('NFC', s))


# ---------------------------------------------------------------- 가짜 서버 + 가짜 Doctor LLM
PATIENT = {
    'C10': [(r'불편한 데는요', '요즘 가슴이 자주 두근거려요.'), (r'식사량|입맛', '입맛이 좋아져 더 많이 먹어요.'),
            (r'더위', '더위 타고 밤엔 잠옷이 젖어요.'), (r'손 떨림', '잔 들 때 손이 떨려요.'),
            (r'대변', '하루 두세 번, 좀 묽어요.'), (r'갈증', '갈증은 없고 소변은 조금 늘었어요.'),
            (r'튀어나오', '좀 튀어나오고 뻑뻑해요.'), (r'목이 붓', '목 앞이 두꺼워졌는데 혹은 없어요.'),
            (r'생리', '두 달째 양이 줄고 짧아졌어요.'), (r'임신', '아니요, 몇 달간 관계가 없었어요.'),
            (r'가슴 통증', '가슴 통증은 없어요.'), (r'숨찬 증상이', '계단 오르면 숨차요.'),
            (r'갑상선 질환이나', '아니요, 그런 병은 없어요.'), (r'약이나 영양제', '아니요, 안 먹어요.'),
            (r'가족 중 갑상선', '어머니가 갑상샘저하증이세요.'), (r'담배나 술', '담배는 안 피우고 술은 가끔요.'),
            (r'걱정되는 병', '혹시 암일까 봐 걱정돼요.'), (r'복통이나 구토', '네, 그런 건 없어요.')],
    'C01': [(r'불편한 데는요', '낮에도 졸리고 멍해요.'), (r'언제부터', '7년 전부터 잠들기 힘들었어요.'),
            (r'이름과 용량', '졸피뎀, 한 알에 10mg이에요.'), (r'몇 알 드세요', '자기 전 네 알, 깨면 한두 알요.'),
            (r'양이 늘거나', '반 알에서 서너 알로 늘었어요.'), (r'안 드시면', '불안하고 식은땀, 손이 떨려요.'),
            (r'줄이거나', '여러 번 했지만 다시 먹었어요.'), (r'경련이나 헛것', '아니요, 그런 적은 없어요.'),
            (r'어디서 처방', '여러 병원에서 받아요.'), (r'약국 약', '약국 수면유도제도 가끔 먹어요.'),
            (r'마지막으로', '어젯밤 네 알, 새벽에 두 알요.'), (r'기억이 끊긴', '가끔 기억이 안 나요.'),
            (r'갈등', '남편, 딸과 갈등이 있어요.'), (r'죽고 싶은', '우울하진 않고 그런 생각은 없어요.'),
            (r'고혈압이나 당뇨', '고혈압은 있고 당뇨는 없어요.'), (r'그 밖에 드시는 약', '혈압약 암로디핀 먹어요.'),
            (r'술이나 담배', '술은 명절에만 한두 잔요.'), (r'걱정되거나 궁금', '계속 먹어도 괜찮을지 걱정돼요.')],
    'C03': [(r'불편한 데는요', '다른 데는 괜찮아요.'), (r'부모님 키', '아빠 170, 엄마 158이에요.'),
            (r'늦게 키가', '아빠가 고등학교 때 컸대요.'), (r'키가 작거나 유전병', '아니요, 둘 다 없어요.'),
            (r'임신이나 출산', '아니요, 별문제 없었어요.'), (r'말이나 걷기', '네, 또래만큼 했어요.'),
            (r'음모나 고환', '아니요, 그런 변화는 없어요.'), (r'변비, 추위', '아니요, 그런 증상은 없어요.'),
            (r'두통이나 구토', '아니요, 그런 증상은 없어요.'), (r'천식이나 장', '아니요, 들은 적 없어요.'),
            (r'스테로이드', '아니요, 둘 다 먹인 적 없어요.'), (r'걱정되시는', '키가 안 클까 봐 걱정돼요.')],
}
CASE_Q = {'C10': '치료는 얼마나 오래 받아야 하나요?', 'C01': '수면제 말고 다른 방법도 있나요?', 'C03': '더 클 수 있을까요?'}


class FakeClient:
    def __init__(self, case, opening, *, q_line='question', explain_q='first', llm='ok', patient=None):
        self.case, self.opening = case, opening
        self.turns = 0
        self.events = []
        self.diagnosed = None
        self.chat_calls = 0
        self.q_line = q_line
        self.explain_q = explain_q
        self.llm = llm
        self.patient = patient
        self.deadline = datetime.now(timezone.utc) + timedelta(minutes=30)
        self.explain_seen = 0
        self.prompts = []

    def session(self):
        return {'session_id': 'x', 'status': 'active', 'turns_remaining': 50 - self.turns,
                'initial': {'opening': self.opening, 'vital_signs': VITALS}, 'deadline': self.deadline.isoformat()}

    def _turn(self, content):
        if self.diagnosed is not None:
            raise NovaError('SESSION_CLOSED', 409)
        if self.turns >= 50:
            raise NovaError('TURN_LIMIT_REACHED', 409)
        if not content or nlen(content) > 30:
            self.turns += 1
            raise NovaError('CONTENT_TOO_LONG', 400)
        self.turns += 1

    def reply(self, content):
        if self.patient:
            return self.patient(content)
        if '궁금하신 점' in content:
            return CASE_Q[self.case] if self.q_line == 'question' else '아니요, 없어요. 감사합니다.'
        if not re.search(r'(\?|요\?)$', content):  # 설명
            self.explain_seen += 1
            if self.explain_q == 'all' or (self.explain_q == 'first' and self.explain_seen == 1):
                return '치료하면 좋아질 수 있나요?'
            return '네, 알겠습니다.'
        for pat, ans in PATIENT[self.case]:
            if re.search(pat, content):
                return ans
        if cpx.count_items(content) >= 3:
            return '아니요, 그런 건 없어요.'
        return '아니요, 없어요.'

    def say(self, content, request_id=None):
        self._turn(content)
        ans = self.reply(content)
        self.events.append(('SAY', content, ans))
        return {'status': 'OK', 'content': ans, 'turn': self.turns, 'turns_remaining': 50 - self.turns}

    def exam(self, content, request_id=None):
        self._turn(content)
        self.events.append(('EXAM', content, '특이 소견(-)'))
        return {'status': 'OK', 'result': '특이 소견(-)', 'turn': self.turns, 'turns_remaining': 50 - self.turns}

    def diagnose(self, note, diagnosis, request_id=None):
        if set(note) != set(RECORD_FIELDS):
            raise NovaError('INVALID_RECORD_FIELDS', 400)
        self.diagnosed = (note, diagnosis)
        return {'status': 'completed'}

    def chat(self, messages, max_tokens=2048, reasoning_effort=None, temperature=None, request_id=None, model=None):
        assert max_tokens <= 8000
        self.chat_calls += 1
        user = messages[-1]['content']
        self.prompts.append(user)
        if self.llm == 'error':
            raise NovaError('PROVIDER_RESPONSE_INVALID', 503)
        return {'choices': [{'message': {'content': self.answer(user)}, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': len(user) // 2, 'completion_tokens': 50}}

    def answer(self, user):
        if '"discriminators"' in user:
            prof = {'C01': {'age': 62, 'sex': 'F', 'pediatric': False, 'informant': '본인', 'chief_complaint': '불면 (수면제 처방 원함)',
                            'request': '수면제 처방', 'categories': ['insomnia', 'substance'],
                            'differential': ['수면제 사용장애', '불면장애', '우울장애', '불안장애', '갑상샘항진증']},
                    'C03': {'age': 6, 'sex': 'M', 'pediatric': True, 'informant': '어머니', 'chief_complaint': '저신장',
                            'request': '', 'categories': ['growth'], 'differential': ['체질성 성장지연', '가족성 저신장', '갑상샘저하증']},
                    'C10': {'age': 32, 'sex': 'F', 'pediatric': False, 'informant': '본인', 'chief_complaint': '체중 감소',
                            'request': '', 'categories': ['weight_loss'],
                            'differential': ['그레이브스병', '당뇨병', '악성종양', '불안장애', '갑상샘염']}}[self.case]
            prof['discriminators'] = [{'q': '목이 아프거나 누르면 아픈가요?', 'label': '목 압통', 'system': 'neck'},
                                      {'q': '두통이나 시야 이상이 있나요?', 'label': '두통', 'system': 'neuro'},   # 교차 계통 → 거절
                                      {'q': '증상을 전부 말씀해 주세요.', 'label': '나열', 'system': 'gen'}]       # 나열 → 거절
            prof['contra'] = [{'q': '천식이 있으세요?', 'label': '천식'}]
            prof['empathy'] = '걱정되셨죠.'
            return json.dumps(prof, ensure_ascii=False)
        if '"facts"' in user:
            return '{}'   # 규칙 폴백 경로를 태운다(항목별 판정 사용)
        if 'diagnosis_ko' in user:
            ko = {'C01': '수면제 사용장애', 'C03': '체질성 성장지연', 'C10': '그레이브스병'}[self.case]
            return json.dumps({'diagnosis_ko': ko, 'diagnosis_en': '', 'confidence': 0.8, 'evidence': [],
                               'differential': [{'dx': '당뇨병', 'reason': '지지: - / 반대: 갈증 없음', 'refs': [], 'test': 'HbA1c'}]},
                              ensure_ascii=False)
        if '[P 규칙]' in user:
            return json.dumps({'tests': [{'name': 'TSH, free T4', 'reason': '확진'}],
                               'treatment': ['메티마졸 15mg 하루 1회 처방합니다', '프로프라놀롤 20 mg 하루 3회'],
                               'disposition': ['외래 추적'], 'follow_up': ['재진 : 2주 뒤 결과 확인', '의뢰 기준 : 안과 증상 악화 시 안과'],
                               'education': ['카페인 줄이기'],
                               'faq': {'duration': '보통 1~2년 약을 드시며 조절해요.', 'prognosis': '치료하면 대부분 좋아져요.'}},
                              ensure_ascii=False)
        if '[SAY 규칙]' in user:
            n = len(re.findall(r'^\d+\. \[', user, flags=re.M))
            base = ['그레이브스병 가능성이 높아요.', '호르몬이 넘쳐 살 빠지고 떨려요.', '목 소견이 뚜렷해 갑상샘 병 같아요.',
                    '피검사·초음파 하고 2주 뒤 결과 봐요.', '졸피뎀 10mg 처방해 드릴게요.', '커피는 줄여 주세요.',
                    '열·목 아픔·숨참·심한 두근거림 땐 바로 오세요.']
            return json.dumps({'say': base[:n]}, ensure_ascii=False)
        if '"answer"' in user:
            return json.dumps({'answer': '보통 1~2년 약으로 조절해요.'}, ensure_ascii=False)
        if '"cc_text"' in user:
            return json.dumps({'cc_text': '체중 감소', 'onset': '3개월 전', 'pain': '해당 없음',
                               'hpi': '32세 여자.\n3개월간 7kg 감소 호소.\n배변 횟수 (?) 변화.\n체중 감소로 내원함.',
                               'meds': '복용 약·보조제 (-)', 'pmh_others': '', 'fh_others': '', 'sh_others': '',
                               'ros_others': '갈증 (?)'}, ensure_ascii=False)
        if '"say"' in user:
            return json.dumps({'say': ['다시 쓴 문장이에요.']}, ensure_ascii=False)
        return '{}'


def run_case(case, opening, **kw):
    client = FakeClient(case, opening, **kw)
    env = {'NOVA_AGENT_GUIDE': '0'}
    with mock.patch.dict(os.environ, env):
        state = run.prepare()
        run.consult(client, state)
    return client


def says(c):
    return [e[1] for e in c.events if e[0] == 'SAY']


# ---------------------------------------------------------------- P1 은행
class TestBank(unittest.TestCase):
    def test_16_categories(self):
        need = {'weight_loss', 'fatigue', 'palpitation', 'insomnia', 'substance', 'mood', 'headache', 'dizziness',
                'chest_pain', 'dyspnea', 'cough_fever', 'abd_pain', 'gi', 'urinary', 'edema', 'growth'}
        self.assertTrue(need <= set(cpx.CPX))

    def test_bank_strings(self):
        for u in cpx.all_bank_units():
            self.assertLessEqual(nlen(u['q']), 30, u['q'])
            self.assertLessEqual(u['q'].count('?'), 1, u['q'])
            self.assertTrue(cpx.check_question(u['q'], whitelisted=True)[0], u['q'])
            self.assertIn(u['stage'], cpx.STAGES)
            self.assertIn(u['prio'], (1, 2, 3))
            for _iid, _lab, kw in u['items']:
                re.compile(kw)
        for q in cpx.ITEM_Q.values():
            self.assertLessEqual(nlen(q), 30, q)
            self.assertTrue(validate_question(q)[0], q)

    def test_bundle_kinds(self):
        """3항목 이상은 같은 계통 음성 묶음(neg3)·병력 이름 나열(hx3)만, 임신 확인은 단독."""
        for u in cpx.all_bank_units():
            n = len(u['items'])
            self.assertLessEqual(n, 3, u['id'])
            if n == 3:
                self.assertIn(u['kind'], ('hx3', 'neg3'))
            if any(i[0] == 'wm_preg' for i in u['items']):
                self.assertEqual(n, 1)
                self.assertTrue(u['safety'])

    def test_unit_ids_unique_per_category(self):
        for c, spec in cpx.CPX.items():
            ids = [u['id'] for u in spec['units']]
            self.assertEqual(len(ids), len(set(ids)), c)

    def test_exams(self):
        for c, spec in cpx.CPX.items():
            self.assertTrue(6 <= len(spec['exams']) <= 8, c)
            for i in spec['exams']:
                self.assertIn(i, banks.EXAM_BY_ID, (c, i))
            self.assertNotIn('vitals', spec['exams'])


# ---------------------------------------------------------------- 검증기·판정
class TestValidator(unittest.TestCase):
    def test_reject(self):
        for q in ('두통이나 시야 이상이 있나요?', '눈 불편감이나 목 부음은 어떠세요?', '복통이나 구토, 혈변은 없나요?',
                  '변비가 있거나 추위를 타고 지치나요?', '잠들기 어렵나요, 자주 깨나요?', '가래가 나오나요? 색은요?',
                  '최근 3개월 동안 체중이 얼마나 빠지셨는지 자세히 말씀해 주시겠어요?'):
            self.assertFalse(cpx.check_question(q)[0], q)

    def test_accept(self):
        for q in ('눈이 튀어나오거나 뻑뻑한가요?', '고혈압이나 당뇨 있으세요?', '대변 횟수나 모양이 변했나요?',
                  '혹시 임신 가능성은 있으세요?', '목이 아프거나 누르면 아픈가요?'):
            self.assertTrue(cpx.check_question(q)[0], q)


SPEC_SRC = os.path.join(HERE, 'data', 'pairs_labeled.tsv')
PAIR_SPEC = [
    (r'^(가족 중 )?(당뇨나 고혈압|고혈압이나 당뇨)', r'당뇨', r'고혈압|혈압'), (r'결핵이나 간염', r'결핵', r'간염'),
    (r'다른 지병이나 수술', r'지병|병', r'수술'), (r'스테로이드나 한약', r'스테로이드', r'한약'), (r'한약이나 영양제', r'한약', r'영양제'),
    (r'^(드시는 |현재 먹는 |지금 먹는 )?(약이나 영양제|다른 약이나 영양제)', r'약|암로디핀|수면제|졸피뎀', r'영양제'),
    (r'입원하거나 크게 아픈|입원이나 큰 병', r'입원', r'큰\s*병|크게|아픈'), (r'임신이나 출산', r'임신', r'출산|분만'),
    (r'천식이나 (콩팥|심장)', r'천식', r'콩팥|심장'), (r'낮에 졸리거나 멍', r'졸', r'멍'), (r'피곤하거나 기운', r'피곤', r'기운'),
    (r'음모나 고환|음모가 나거나 고환', r'음모', r'고환'), (r'말이나 걷기', r'말', r'걷'), (r'살이 빠지거나 찌', r'빠지', r'찌'),
    (r'생리 (양이나 기간|주기나 양)', r'양', r'기간|짧|주기'), (r'대변 횟수나 모양', r'번|회', r'묽|모양|딱딱'),
    (r'물을 많이 드시거나 갈증', r'물', r'갈증'), (r'물을 많이 마시거나 소변', r'물|마시', r'소변'),
    (r'눈이 (튀어나오거나 뻑뻑|뻑뻑하거나 튀어나온)', r'튀어나', r'뻑뻑'), (r'목이 붓거나 혹', r'두꺼|붓|부', r'혹'),
    (r'열이나 오한', r'열', r'오한'), (r'몸이나 다리가 붓', r'몸', r'다리'), (r'기침이나 가래', r'기침', r'가래'),
    (r'가슴 통증이나 숨참', r'가슴|통증', r'숨'), (r'더위나 땀', r'더위|덥', r'땀'), (r'더위나 추위', r'더위', r'추위'),
    (r'두통이나 구토는', r'두통|머리', r'구토|토'), (r'^(변비나 추위|피로감이나 변비|피로나 변비)', r'변비|피로|피곤', r'추위|변비'),
    (r'피부가건조하거나가려움', r'건조', r'가려'), (r'어지럽거나 쓰러질', r'어지', r'쓰러'), (r'키가 작거나 유전병', r'키|작', r'유전'),
    (r'약이나 음식 알레르기', r'약', r'음식'), (r'복통이나 혈변', r'복통|배', r'혈변|피'), (r'신생아 때 황달이나 치료', r'황달', r'치료'),
    (r'배만 나오거나 얼굴', r'배', r'얼굴'), (r'두통이나 시야 이상이', r'두통|머리', r'시야|눈'), (r'눈 불편감이나 목 부음', r'눈', r'목'),
    (r'손이 떨리거나 힘이 빠', r'떨', r'힘'), (r'변비가 있거나 추위를', r'변비', r'추위'), (r'눈이 부풀어 오르거나 가려', r'부풀|튀어', r'가려'),
    (r'잠들기 어렵나요, ', r'잠들', r'깨'),
]
THREE = {'잘 지치거나 변비': [r'지치|피곤', r'변비', r'추위'], '두통이나 구토': [r'두통|머리', r'구토|토', r'시야|눈'],
         '천식이나 장': [r'천식', r'장\s|장질환', r'콩팥|신장'], '먹는 약이나 한약': [r'약', r'한약', r'영양제']}


class TestJudge(unittest.TestCase):
    def _items(self, q):
        for key, kws in THREE.items():
            if key in q:
                return [(f'i{k}', f'항목{k}', kw) for k, kw in enumerate(kws)]
        for pat, ka, kb in PAIR_SPEC:
            if re.search(pat, q):
                return [('a', 'A', ka), ('b', 'B', kb)]
        return None

    def test_regression_196_no_false_both(self):
        """서버 실측 라벨 196행: 부분 응답을 '모두 답함'으로 오판 0건(정보 손실은 허용)."""
        rows = list(csv.reader(open(SPEC_SRC, encoding='utf-8'), delimiter='\t'))[1:]
        self.assertGreaterEqual(len(rows), 190)
        false_both, n = 0, 0
        for _run, _turn, q, a, _kind, lab in rows:
            items = self._items(q)
            if items is None:
                continue
            n += 1
            res = cpx.judge(items, a)
            if lab == 'partial' and all(o['answered'] for o in res):
                false_both += 1
        self.assertGreaterEqual(n, 190)
        self.assertEqual(false_both, 0)

    def test_item_polarity(self):
        r = cpx.judge([cpx.I_HTN, cpx.I_DM], '고혈압은 있고 당뇨는 없어요.')
        self.assertEqual([(o['answered'], o['pol']) for o in r], [(True, '+'), (True, '-')])
        r = cpx.judge([cpx.I_CP, cpx.I_DYSP], '가슴 통증은 없어요.')
        self.assertEqual([(o['answered'], o['pol']) for o in r], [(True, '-'), (False, '?')])
        r = cpx.judge([cpx.I_CP, cpx.I_DYSP], '통증은 없고 계단 오르면 숨차요.')
        self.assertEqual([o['pol'] for o in r], ['-', '+'])

    def test_generic_negative_decomposed(self):
        items = [cpx.I_THY, cpx.I_ASTHMA, cpx.I_HEART]
        for a in ('아니요, 그런 병은 없어요.', '아니요, 들은 적 없어요.', '네, 그런 건 없어요.'):
            r = cpx.judge(items, a)
            self.assertTrue(all(o['answered'] and o['pol'] == '-' for o in r), a)

    def test_positive_mixed_in_neg3(self):
        items = [('a', '피로', r'지치|피곤'), ('b', '변비', r'변비'), ('c', '추위', r'추위')]
        r = cpx.judge(items, '변비는 좀 있어요.')
        self.assertEqual([(o['answered'], o['pol']) for o in r], [(False, '?'), (True, '+'), (False, '?')])

    def test_one_at_a_time_unanswered(self):
        r = cpx.judge([cpx.I_CP, cpx.I_DYSP], '한 번에 하나씩 물어봐 주세요.')
        self.assertFalse(any(o['answered'] for o in r))


# ---------------------------------------------------------------- P2 컴파일
class TestCompile(unittest.TestCase):
    def _built(self, prof, opening):
        return cpx.build(prof, opening)

    def test_order_and_preg_single(self):
        b = self._built({'age': 32, 'sex': 'F', 'pediatric': False, 'categories': ['weight_loss']}, C10)
        chosen, _ = cpx.compile_units(b['units'], 17)
        stages = [cpx.chosen_rank(u) for u in chosen]
        self.assertEqual(stages, sorted(stages))
        self.assertEqual(chosen[-1]['stage'], 'ice')
        preg = [u for u in chosen if u['id'] == 'wm_preg']
        self.assertEqual(len(preg), 1)
        self.assertEqual(preg[0]['kind'], 'single')
        ids = [u['id'] for u in chosen]
        self.assertLess(ids.index('wl_cardio'), ids.index('hx_admit_op'))   # 경고 음성 → 병력
        self.assertLess(ids.index('hx_allergy'), ids.index('wl_fh'))        # 병력 → 가족력
        self.assertLess(ids.index('sh_smoke_alc'), ids.index('wm_preg'))  # 사회력 → 임신

    def test_safety_kept_under_tight_budget(self):
        b = self._built({'age': 32, 'sex': 'F', 'pediatric': False, 'categories': ['weight_loss']}, C10)
        chosen, backlog = cpx.compile_units(b['units'], 8)
        ids = {u['id'] for u in chosen}
        self.assertEqual(len(chosen), 8)
        for must in ('wm_preg', 'hx_admit_op', 'hx_allergy', 'hx_meds', 'wl_fh', 'sh_smoke_alc', 'wl_cardio', 'ice'):
            self.assertIn(must, ids)

    def test_profiles(self):
        b1 = self._built({'age': 62, 'sex': 'F', 'pediatric': False, 'categories': ['insomnia', 'substance'],
                          'request': '수면제 처방'}, C01)
        self.assertEqual(b1['main'], 'substance')
        ids1 = {u['id'] for u in b1['units']}
        self.assertNotIn('wm_preg', ids1)
        self.assertIn('sb_last', ids1)
        self.assertIn('sb_seizure', ids1)
        self.assertIn('hpi_onset', ids1)  # 시작 정보에 시점 없음
        b3 = self._built({'age': 6, 'sex': 'M', 'pediatric': True, 'informant': '어머님', 'categories': ['growth']}, C03)
        ids3 = {u['id'] for u in b3['units']}
        self.assertNotIn('wm_preg', ids3)
        ice = next(u for u in b3['units'] if u['id'] == 'ice')
        self.assertTrue(ice['q'].startswith('어머님'))
        self.assertNotIn('hpi_onset', ids3)  # '일 년 전부터'
        b10 = self._built({'age': 32, 'sex': 'F', 'pediatric': False, 'categories': ['weight_loss']}, C10)
        self.assertEqual(b10['exams'][:2], ['thyroid', 'eye_signs'])

    def test_fallback_category(self):
        b = self._built({'age': 40, 'sex': 'M', 'pediatric': False, 'categories': ['msk']}, '허리가 아파서 왔어요.')
        self.assertFalse(b['bank'])
        self.assertTrue(any(u['id'].startswith('mk_') for u in b['units']))
        self.assertTrue(b['exams'])


# ---------------------------------------------------------------- 드라이런 (가짜 서버)
class TestDryRun(unittest.TestCase):
    def check(self, c):
        self.assertIsNotNone(c.diagnosed)
        note, dx = c.diagnosed
        self.assertTrue(dx.strip())
        self.assertLessEqual(c.turns, 34)
        s = says(c)
        self.assertTrue(all(nlen(x) <= 30 for x in s))
        self.assertEqual(len(s), len(set(s)), s)
        info = run.LAST_RUN
        self.assertEqual(info['counts']['refused'], 0)
        return note, s

    def test_c10(self):
        c = run_case('C10', C10)
        note, s = self.check(c)
        self.assertTrue(s[0].startswith('안녕하세요'))
        self.assertTrue(s[0].endswith('다른 불편한 데는요?'))
        self.assertIn('혹시 임신 가능성은 있으세요?', s)
        self.assertIn('입원이나 수술한 적 있으세요?', s)
        self.assertIn('약 알레르기나 천식 있으세요?', s)
        self.assertNotIn('두통이나 시야 이상이 있나요?', s)   # LLM 교차 계통 문항 거절
        self.assertNotIn('증상을 전부 말씀해 주세요.', s)
        exams = [e[1] for e in c.events if e[0] == 'EXAM']
        self.assertEqual(len(exams), 7, exams)
        self.assertEqual(exams[0], '활력징후 측정하겠습니다')   # v8c: 활력 측정 1회는 항상
        self.assertEqual(s.count(saymod.QUESTION_LINE), 1)
        qi = s.index(saymod.QUESTION_LINE)
        self.assertEqual(qi, len(s) - 2)              # Q 다음 마지막 답
        self.assertNotIn('졸피뎀 10mg 처방해 드릴게요.', s)  # 안전 필터
        self.assertFalse(any(explain.SAY_BAD_RE.search(x) for x in s))
        self.assertNotIn('(?)', note['S']['hpi'] + note['S']['ros'])
        self.assertNotIn('15mg', note['P']['treatment'])
        self.assertIn('DM / HTN', note['S']['pmh'])
        self.assertIn('안전 확인', note['S']['hpi'])

    def test_c01(self):
        c = run_case('C01', C01)
        note, s = self.check(c)
        self.assertTrue(s[0].endswith('잠 말고 불편한 데는요?'))
        self.assertFalse(any('임신' in x for x in s))
        self.assertIn('끊었을 때 경련이나 헛것이 있었나요?', s)
        self.assertIn('마지막으로 언제 몇 알 드셨어요?', s)
        self.assertIn('기분이 가라앉거나 죽고 싶은 적 있나요?', s)
        self.assertIn('금단 경련', note['S']['hpi'])
        # v8c: 예산 17에서 고혈압·당뇨(prio 2)는 필수 공통 병력에 밀림 → 입원·수술·알레르기가 기록된다
        self.assertIn('Op. Hx (-)', note['S']['pmh'])
        self.assertIn('Allergy (-)', note['S']['pmh'])

    def test_c03(self):
        c = run_case('C03', C03)
        note, s = self.check(c)
        self.assertTrue(s[0].endswith('아이가 다른 불편한 데는요?'))
        self.assertFalse(any('임신 가능성' in x for x in s))
        self.assertIn('부모님 키는 각각 어떻게 되세요?', s)
        self.assertTrue(any(x.startswith('어머님') for x in s))
        exams = [e[1] for e in c.events if e[0] == 'EXAM']
        self.assertIn('신체 계측하겠습니다', exams)

    def test_last_answer_guaranteed_when_patient_asks_every_time(self):
        c = run_case('C10', C10, explain_q='all')
        s = says(c)
        self.assertLessEqual(c.turns, 34)
        qi = s.index(saymod.QUESTION_LINE)
        self.assertEqual(qi, len(s) - 2)
        last_reply = c.events[[i for i, e in enumerate(c.events) if e[0] == 'SAY' and e[1] == saymod.QUESTION_LINE][0]][2]
        self.assertTrue(explain.is_question(last_reply))

    def test_no_teachback_when_no_question(self):
        """v8c: 되말하기 폐지 — 질문이 없어도 '바로 오셔야 할 증상…'을 묻지 않고 남는 턴은 정보(진찰·설명)에 쓴다."""
        c = run_case('C10', C10, q_line='none', explain_q='none')
        s = says(c)
        self.assertLessEqual(c.turns, 34)
        self.assertNotIn(explain.TEACH_BACK, s)
        self.assertFalse(any(e.get('phase') == 'explain-teachback' for e in run.LAST_RUN['ledger']))
        self.assertIn(saymod.QUESTION_LINE, s)

    def test_drill_guard_all_positive(self):
        """환자가 모든 질문에 양성으로 답해도 임신·약·걱정 질문이 밀려나지 않는다."""
        def pos(content):
            if '궁금하신 점' in content:
                return '치료 기간이 궁금해요?'
            return '네, 있어요.' if content.endswith('?') else '네, 알겠습니다.'
        c = run_case('C10', C10, patient=pos)
        s = says(c)
        self.assertLessEqual(c.turns, 34)
        for q in ('혹시 임신 가능성은 있으세요?', '드시는 약이나 영양제 있으세요?', '혹시 걱정되는 병이 있으세요?'):
            self.assertIn(q, s)
        self.assertLessEqual(run.LAST_RUN['checklist']['follow_n'], 2)

    def test_safety_reask(self):
        """안전 묶음에서 숨참이 미응답이면 단독 재질문 1회(개방형 답이 단위 2개를 덮어 자리가 남을 때)."""
        base = FakeClient('C10', C10)

        def pat(content):
            if '불편한 데는요' in content:
                return '가슴이 두근거리고 손이 떨려요.'
            return base.reply(content)
        c = run_case('C10', C10, patient=pat)
        s = says(c)
        self.assertIn('숨찬 증상이 있으세요?', s)
        self.assertEqual(s.count('숨찬 증상이 있으세요?'), 1)

    def test_llm_down(self):
        c = run_case('C10', C10, llm='error')
        self.assertIsNotNone(c.diagnosed)
        self.assertLessEqual(c.turns, 34)


# ---------------------------------------------------------------- P5 기록
class FakeEnc:
    def __init__(self, ledger, opening=C10):
        self.ledger = ledger
        self.opening = opening
        self.vitals = VITALS
        self.profile = {'age': 32, 'sex': 'F', 'pediatric': False, 'informant': '본인'}
        self.cfg = run.load_config()
        self.explained = []
        self.differentials = []
        self.dx = ''


def _entry(turn, q, a, items, **kw):
    e = {'turn': turn, 'kind': 'SAY', 'text': q, 'reply': a, 'phase': 'interview', 'qid': kw.get('qid', 'u'),
         'label': '', 'items': cpx.judge(items, a)}
    e.update(kw)
    return e


class TestRecord(unittest.TestCase):
    def test_unanswered_item_negative_dropped(self):
        led = [_entry(5, '가슴 통증이나 숨찬 증상 있으세요?', '가슴 통증은 없어요.', [cpx.I_CP, cpx.I_DYSP])]
        enc = FakeEnc(led)
        rows = facts.qa_rows(enc)
        out = facts.item_filter(enc, rows, [
            {'turn': 5, 'sec': 'ros', 'key': 'ros.Chest pain', 'label': '흉통', 'pol': '-', 'detail': ''},
            {'turn': 5, 'sec': 'ros', 'key': 'other', 'label': '호흡곤란', 'pol': '-', 'detail': ''},
            {'turn': 5, 'sec': 'ros', 'key': 'other', 'label': '숨참', 'pol': '-', 'detail': ''}])
        labels = [f['label'] for f in out]
        self.assertIn('흉통', labels)
        self.assertNotIn('호흡곤란', labels)
        self.assertNotIn('숨참', labels)

    def test_generic_negative_fills_fixed(self):
        led = [_entry(7, '고혈압이나 당뇨 있으세요?', '아니요, 그런 병은 없어요.', [cpx.I_HTN, cpx.I_DM])]
        enc = FakeEnc(led)
        enc.facts = facts.fallback(enc, facts.qa_rows(enc))
        out = note2.render_fixed(enc, {})
        self.assertIn('DM / HTN (-/-)', out['pmh'])
        rows = facts.qa_rows(enc)
        v = facts.validate(enc, rows, [{'turn': 7, 'key': 'pmh.HTN', 'pol': '-', 'label': '고혈압'}])
        self.assertEqual(v[0]['key'], 'pmh.HTN')   # 포괄 음성으로 강등되지 않음

    def test_partial_pair_fixed_blank(self):
        led = [_entry(7, '고혈압이나 당뇨 있으세요?', '고혈압이 있어요.', [cpx.I_HTN, cpx.I_DM])]
        enc = FakeEnc(led)
        enc.facts = facts.fallback(enc, facts.qa_rows(enc))
        out = note2.render_fixed(enc, {})
        self.assertIn('DM / HTN ( /+)', out['pmh'])   # 당뇨는 미응답 → 빈칸(음성 기록 금지)

    def test_strip_unknown(self):
        self.assertEqual(note2.strip_unknown('배변 횟수 (?) 변화, 갈증 (?)'), '배변 횟수 변화, 갈증')

    def test_explain_question_to_s(self):
        led = [{'turn': 30, 'kind': 'SAY', 'text': '그레이브스병 가능성이 높아요.', 'reply': '치료하면 좋아질 수 있나요?',
                'phase': 'explain'},
               {'turn': 31, 'kind': 'SAY', 'text': '피검사 해요.', 'reply': '네, 알겠습니다.', 'phase': 'explain'}]
        rows = facts.qa_rows(FakeEnc(led))
        self.assertEqual([r['slot'] for r in rows], ['ice_q'])

    def test_safety_lines(self):
        led = [_entry(8, '끊었을 때 경련이나 헛것이 있었나요?', '아니요, 그런 적은 없어요.',
                      [('sb_seizure', '금단 경련', r'경련'), ('sb_delirium', '금단 환각', r'헛것')], safety=True),
               _entry(11, '마지막으로 언제 몇 알 드셨어요?', '어젯밤 네 알요.', [('sb_last', '마지막 복용', '.')], safety=True)]
        enc = FakeEnc(led, C01)
        enc.dx = '수면제(진정수면제) 사용장애'
        enc.kb = None
        note = {s: {f: '' for f in fs} for s, fs in RECORD_FIELDS.items()}
        note['S']['hpi'] = '62세 여자.'
        out = record.add_safety_lines(enc, note)
        self.assertIn('금단 경련 (-) (턴 8)', out['S']['hpi'])
        self.assertIn('마지막 복용: 어젯밤 네 알요 (턴 11)', out['S']['hpi'])
        self.assertIn('금단 경련·섬망 병력 없음', out['P']['disposition'])


# ---------------------------------------------------------------- P4 설명·안전
class TestExplain(unittest.TestCase):
    def test_safe_filters(self):
        self.assertEqual(explain.safe_say('졸피뎀 10mg 처방해 드릴게요.'), explain.SAFE_SAY)
        self.assertNotIn('메티마졸', explain.safe_plan_line('메티마졸 15mg 하루 1회 처방합니다'))
        self.assertNotIn('15', explain.safe_plan_line('메티마졸 15mg 하루 1회 처방합니다'))
        s = guidelines.sanitize('TSH를 먼저 측정한다. 메티마졸 15 mg을 하루 1회 투여한다.')
        self.assertIn('TSH', s)
        self.assertNotIn('메티마졸', s)

    def test_say_slots(self):
        self.assertEqual([k for k, _ in explain.say_slots(5)], ['dx', 'mech', 'worry', 'tests', 'warn'])
        self.assertEqual(len(explain.say_slots(6)), 6)
        self.assertEqual(len(explain.say_slots(7)), 7)
        self.assertEqual(len(explain.say_slots(3)), 3)

    def test_fit_lines(self):
        lines = ['그레이브스병 가능성이 높아요.', '호르몬이 넘쳐요.', '암보다 갑상샘 병 같아요.', '피검사 하고 2주 뒤 봐요.',
                 '커피는 줄여요.', '열·숨참·혼동·황달 땐 바로 오세요.', saymod.QUESTION_LINE]
        out = explain.fit_lines(lines, 6)
        self.assertEqual(len(out), 5)
        self.assertEqual(out[0], lines[0])
        self.assertEqual(out[-1], saymod.QUESTION_LINE)
        self.assertIn(lines[5], out)

    def test_ensure_v8(self):
        enc = FakeEnc([{'turn': 18, 'kind': 'SAY', 'text': '혹시 걱정되는 병이 있으세요?', 'reply': '혹시 암일까 봐요.',
                        'qid': 'ice', 'phase': 'interview'}])
        enc.dx = '그레이브스병에 의한 갑상샘항진증'
        out = saymod.ensure_v8(['그레이브스병 가능성이 높아요.', '피검사 해요.'], enc)
        self.assertTrue(saymod.EMPATHY_RE.search(out[0]))
        self.assertTrue(any('걱정하신 암' in x for x in out))
        self.assertTrue(all(not saymod.say_problem(x) for x in out))

    def test_answer_fallback(self):
        enc = FakeEnc([])
        enc.plan_v2 = {}
        enc.client = None
        enc.budget = None
        with mock.patch.object(explain, '_answer_llm', return_value=''):
            a = explain.answer(enc, '치료는 얼마나 오래 해요?', [])
        self.assertEqual(a, explain.TOPIC_FALLBACK['duration'])
        self.assertFalse(saymod.say_problem(a))
        for v in explain.TOPIC_FALLBACK.values():
            self.assertFalse(saymod.say_problem(v), v)
        self.assertFalse(saymod.say_problem(explain.TEACH_BACK, allow_question=True))


# ---------------------------------------------------------------- P6 설정
class TestConfig(unittest.TestCase):
    def test_defaults(self):
        with mock.patch.object(run, 'PRESET_FILE', '/nonexistent/preset.json'):
            cfg = run.load_config()
        self.assertEqual(cfg['TURN_CAP'], 34)
        self.assertEqual(cfg['CPX'], 1)
        self.assertEqual(cfg['INTERVIEW_Q'], 17)
        self.assertEqual(1 + cfg['INTERVIEW_Q'] + cfg['EXAM_N'] + cfg['EXPLAIN_MIN'] + cfg['ANSWER_RESERVE'], 34)

    def test_preset_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'preset.json')
            with open(p, 'w', encoding='utf-8') as f:
                json.dump({'CPX': 0, 'TURN_CAP': 38, 'UNKNOWN': 1}, f)
            with mock.patch.object(run, 'PRESET_FILE', p):
                cfg = run.load_config()
            self.assertEqual(cfg['CPX'], 0)
            self.assertEqual(cfg['TURN_CAP'], 38)
            self.assertNotIn('UNKNOWN', cfg)
            with open(p, 'w', encoding='utf-8') as f:
                f.write('{broken')
            self.assertEqual(run.load_preset_file(p), {})

    def test_first_open_question(self):
        from agent.interview import _first_open
        for prof, main in (({'empathy_short': '걱정되셨죠.'}, 'weight_loss'), ({'empathy_short': '힘드셨죠.'}, 'substance'),
                           ({'pediatric': True, 'empathy_short': '걱정되셨죠.'}, 'growth')):
            q = _first_open(prof, main)
            self.assertLessEqual(nlen(q), 30)
            last = re.split(r'(?<=[.])\s+', q)[-1]   # 공감 접두가 잘려도 질문 문장은 남는다
            self.assertTrue(last.endswith('?'))
            self.assertTrue(validate_question(last)[0], last)


if __name__ == '__main__':
    unittest.main()

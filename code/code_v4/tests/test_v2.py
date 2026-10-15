"""v2 수용 테스트(v2_spec §15). API 없이 실행. test_agent.py에서 import되어 함께 돈다."""
import json
import os
import re
import sys
import time
import unicodedata
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from nova_sdk import RECORD_FIELDS, NovaError  # noqa: E402

import run  # noqa: E402
from agent import bank2, banks, explain, kb, say as saymod  # noqa: E402
from agent.util import validate_question  # noqa: E402

V2_C01 = '저는 박선희이고, 예순두 살 여자이다. 잠을 잘 못 자서 병원에 왔다. 수면제를 처방해 달라고 왔다.'
V2_C03 = ('이름은 김도현이고, 여섯 살 남자아이이다. 엄마 김지영, 서른일곱 살이 보호자로 함께 왔다. 엄마는 도현이 키가 또래에 비해 '
          '많이 작은 것 같아 걱정이 된다고 말했다. 엄마는 일 년 전부터 주변에서 도현이가 또래보다 작다는 말을 듣기 시작했다고 했다. '
          '엄마가 집에서 키를 재보니, 일 년 전에는 백 센티미터였고 지금은 백오 센티미터 정도였다. '
          '몸무게는 일 년 전 십오 키로그람에서 지금은 십육 점 오 키로그람으로 일 점 오 키로그람 늘었다.')
V2_C10 = ('이름은 최윤정이고, 나는 서른두 살 여자이다. 최근 석 달 동안 살이 많이 빠져서 병원에 오게 되었다. 원래 몸무게는 '
          '오십육 키로그람 정도였는데, 최근 석 달 사이에 칠 키로그람 정도 빠져서 지금은 사십구 키로그람 정도이다. '
          '평소에는 몸무게 변화가 거의 없었는데 저절로 살이 빠져서 걱정이 되었다. 키는 백육십사 센티미터이다.')
V2_VITALS = '혈압 : 138/72 mmHg\n맥박 : 102 회/분\n호흡 : 19 회/분\n체온 : 36.9°C'


def nlen(s):
    return len(unicodedata.normalize('NFC', s))


class Clock:
    def __init__(self):
        self.t = time.time()

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += max(0.0, s)


class V2Client:
    """v2 프롬프트에 맞춘 가짜 서버+LLM. patient: 'yes'|'no'. chat_delay: 가짜 시계로 호출당 지연(초)."""

    def __init__(self, opening, patient='yes', llm='good', minutes=30, clock=None, chat_delay=0.0):
        self.opening, self.patient, self.llm = opening, patient, llm
        self.clock = clock
        base = datetime.fromtimestamp(clock.now(), timezone.utc) if clock else datetime.now(timezone.utc)
        self.deadline = base + timedelta(minutes=minutes)
        self.turns, self.events, self.diagnosed, self.chat_calls = 0, [], None, 0
        self.chat_delay = chat_delay
        self.diagnose_calls = 0
        self.timeout = 60

    def session(self):
        return {'session_id': 'x', 'status': 'active', 'turns_remaining': 50 - self.turns,
                'initial': {'opening': self.opening, 'vital_signs': V2_VITALS}, 'deadline': self.deadline.isoformat()}

    def _turn(self, content):
        if self.clock:
            self.clock.sleep(3)
        if self.diagnosed is not None:
            raise NovaError('SESSION_CLOSED', 409)
        if self.turns >= 50:
            raise NovaError('TURN_LIMIT_REACHED', 409)
        if not content or nlen(content) > 30:
            self.turns += 1
            raise NovaError('CONTENT_TOO_LONG', 400)
        self.turns += 1

    def say(self, content, request_id=None):
        self._turn(content)
        if self.patient == 'no':
            ans = '아니요, 없어요.'
        elif '땀이 많아' in content:
            ans = '네, 밤엔 잠옷이 젖을 정도예요.'
        elif '궁금' in content:
            ans = '검사 결과는 언제 나와요?'
        else:
            ans = '네, 그런 편이에요.'
        self.events.append(('SAY', content, ans))
        return {'status': 'OK', 'content': ans, 'turn': self.turns, 'turns_remaining': 50 - self.turns}

    def exam(self, content, request_id=None):
        self._turn(content)
        res = '특이 소견(-)'
        self.events.append(('EXAM', content, res))
        return {'status': 'OK', 'result': res, 'turn': self.turns, 'turns_remaining': 50 - self.turns}

    def diagnose(self, note, diagnosis, request_id=None):
        self.diagnose_calls += 1
        if set(note) != set(RECORD_FIELDS) or any(set(note[s]) != set(f) for s, f in RECORD_FIELDS.items()):
            raise NovaError('INVALID_RECORD_FIELDS', 400)
        assert all(isinstance(v, str) for s in note.values() for v in s.values())
        self.diagnosed = (note, diagnosis)
        return {'status': 'completed'}

    def chat(self, messages, max_tokens=2048, reasoning_effort=None, temperature=None, request_id=None, model=None):
        assert temperature is None, 'temperature는 보내지 않는다'
        assert max_tokens <= 8000, f'max_tokens {max_tokens} > 8000'
        self.chat_calls += 1
        if self.clock:
            self.clock.sleep(self.chat_delay)
        if self.llm == 'error':
            raise NovaError('PROVIDER_RESPONSE_INVALID', 503)
        user = messages[-1]['content']
        text = self.answer(user)
        return {'choices': [{'message': {'content': text}, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': len(user) // 2, 'completion_tokens': 50}}

    def answer(self, user):
        if '"empathy"' in user and 'categories' in user:
            if '수면제' in self.opening:
                return json.dumps({'age': 62, 'sex': 'F', 'pediatric': False, 'informant': '본인',
                                   'chief_complaint': '불면 (수면제 처방 원함)', 'request': '수면제 처방',
                                   'categories': ['insomnia', 'substance'], 'differential': ['수면제 사용장애', '불면장애'],
                                   'empathy': '많이 힘드셨겠어요.'}, ensure_ascii=False)
            if '도현' in self.opening:
                return json.dumps({'age': 6, 'sex': 'M', 'pediatric': True, 'informant': '어머니', 'chief_complaint': '저신장',
                                   'request': '', 'categories': ['growth'], 'differential': ['체질성 성장지연'],
                                   'empathy': '걱정 많으셨겠어요.'}, ensure_ascii=False)
            return json.dumps({'age': 32, 'sex': 'F', 'pediatric': False, 'informant': '본인', 'chief_complaint': '체중 감소',
                               'request': '', 'categories': ['weight_loss'], 'differential': ['그레이브스병', '당뇨병'],
                               'empathy': '많이 걱정되셨겠어요.'}, ensure_ascii=False)
        if '"covered"' in user:
            return json.dumps({'covered': [], 'differential': ['그레이브스병', '당뇨병'],
                               'questions': [{'slot': 'wl_sweat', 'q': '땀이 많아지셨나요?'},
                                             {'slot': 'free', 'q': '열이 나거나 밤에 땀이 나나요?'},
                                             {'slot': 'free', 'q': '증상을 전부 말씀해 주세요.'},
                                             {'slot': 'sh_caffeine', 'q': '커피는 하루 몇 잔 드세요?'},
                                             {'slot': 'free', 'q': '최근체중이5kg이상증가했나요?'}]}, ensure_ascii=False)
        if 'exam_ids' in user:
            return json.dumps({'exam_ids': ['heart', 'nonexistent', 'lung', 'abd_palp']})
        if '"facts"' in user:
            return json.dumps({'facts': [{'turn': 0, 'sec': 'hpi', 'key': 'other', 'label': '체중 감소', 'pol': '+',
                                          'detail': '3달간 7kg'},
                                         {'turn': 2, 'sec': 'ros', 'key': 'ros.Fever', 'pol': '+', 'detail': '27kg'}]},
                              ensure_ascii=False)
        if 'diagnosis_ko' in user:
            ko = '수면제 사용장애' if '수면제' in self.opening else ('체질성 성장지연' if '도현' in self.opening
                                                                 else '그레이브스병')
            return json.dumps({'diagnosis_ko': ko, 'diagnosis_en': '', 'confidence': 0.8,
                               'evidence': [{'text': '체중 감소 호소 → 대사 항진', 'refs': ['F1', 'E1']},
                                            {'text': '없는 근거', 'refs': ['F99']}],
                               'differential': [{'dx': '당뇨병', 'reason': '갈증 없음', 'refs': ['F2'], 'test': 'HbA1c'}]},
                              ensure_ascii=False)
        if '[FAQ]' in user:
            return json.dumps({'tests': [{'name': 'TSH, free T4', 'reason': '확인'}],
                               'treatment': ['메티마졸 15mg 하루 1회 시작', '수면제 추가 처방', '프로프라놀롤 20 mg 하루 3회'],
                               'disposition': ['외래 추적'], 'follow_up': ['재진 : 1~2주'], 'education': ['카페인 줄이기'],
                               'say': ['갑상선 호르몬이 넘치는 병 같아요.', '재진 때 자세히 설명드릴게요.',
                                       '검사 결과에 맞는 치료로 치료할 수 있어요.', '카페인은 줄이세요.'],
                               'faq': {'results': '결과는 일주일쯤 뒤에 나와요.'}}, ensure_ascii=False)
        if '"say"' in user:
            return json.dumps({'say': ['다시 쓴 문장이에요.']}, ensure_ascii=False)
        if '"answer"' in user:
            return json.dumps({'answer': '네, 같이 천천히 해 봐요.'}, ensure_ascii=False)
        if '"cc_text"' in user:
            return json.dumps({'cc_text': '체중 감소', 'onset': '3개월 전', 'pain': '해당 없음',
                               'hpi': '32세 여자.\n3개월간 7kg 감소 호소.\n하루 99알 복용.\n체중 감소로 내원함.',
                               'meds': '복용 약·보조제 (-)', 'pmh_others': '', 'fh_others': '', 'sh_others': '',
                               'ros_others': ''}, ensure_ascii=False)
        return '{}'


def run_v2(opening, **kw):
    preset = kw.pop('preset', None)
    client = V2Client(opening, **kw)
    env = {'NOVA_AGENT_V2': '1', 'NOVA_AGENT_V3': '0', 'NOVA_AGENT_TURN_PRESET': preset or 'bal44'}  # v2 흐름 테스트
    with mock.patch.dict(os.environ, env):
        state = run.prepare()
    run.consult(client, state)
    return client


class TestV2Banks(unittest.TestCase):
    def test_bank_strings(self):  # §15-1
        lists = [bank2.ADULT_SPINE, bank2.WOMEN, bank2.PSYCH_SCREEN, bank2.PEDS_SPINE] + list(bank2.CATEGORY_Q.values())
        for lst in lists:
            slots = [x[0] for x in lst]
            self.assertEqual(len(slots), len(set(slots)), slots)
            for slot, label, q, prio in lst:
                self.assertLessEqual(nlen(q), 28, q)
                self.assertLessEqual(q.count('?'), 1, q)
                self.assertIn(prio, (1, 2, 3))
                ok, why = validate_question(q)
                self.assertTrue(ok, f'{q}: {why}')
        cat_slots = [x[0] for lst in bank2.CATEGORY_Q.values() for x in lst]
        self.assertEqual(len(cat_slots), len(set(cat_slots)))
        for c, b in bank2.BOOST.items():
            self.assertIn(c, bank2.CATEGORY_Q)
            for s in b:
                self.assertIn(s, bank2.ALL_SLOTS, (c, s))
        for c, lst in bank2.CATEGORY_EXAMS.items():
            self.assertIn(c, bank2.CATEGORY_Q)
            for i in lst:
                self.assertIn(i, banks.EXAM_BY_ID, (c, i))
        for e in banks.EXAM_BANK:
            self.assertLessEqual(nlen(e[1]), 30)
        for k in kb.KB:
            for s in k['say']:
                self.assertFalse(saymod.say_problem(s), (k['id'], s, saymod.say_problem(s)))
            for s in (k.get('faq') or {}).values():
                self.assertFalse(saymod.say_problem(s), (k['id'], s))
            if k.get('red_say'):
                self.assertFalse(saymod.say_problem(k['red_say']), k['red_say'])
                self.assertGreaterEqual(saymod.warn_count([k['red_say']]), 4, k['red_say'])

    def test_category_detect(self):  # §15-2
        self.assertEqual(set(bank2.detect_categories(V2_C01, False)), {'insomnia', 'substance'})
        self.assertEqual(set(bank2.detect_categories(V2_C03, True)), {'growth'})
        self.assertIn('weight_loss', bank2.detect_categories(V2_C10, False))
        self.assertNotIn('growth', bank2.detect_categories(V2_C10, False))

    def test_checklist(self):  # §15-3
        from agent.interview import Checklist
        cl = Checklist({'age': 32, 'sex': 'F', 'pediatric': False, 'categories': ['weight_loss']}, V2_C10)
        self.assertEqual(cl.items['wm_preg']['prio'], 1)
        self.assertIn('ps_anxiety', cl.items)
        cl3 = Checklist({'age': 6, 'sex': 'M', 'pediatric': True, 'informant': '어머님', 'categories': ['growth']}, V2_C03)
        self.assertIn('gr_parents', cl3.items)
        self.assertIn('p_perinatal', cl3.items)
        self.assertNotIn('wm_preg', cl3.items)
        self.assertTrue(cl3.items['ice_concern']['q'].startswith('어머님'))
        self.assertEqual(bank2.informant_title(V2_C03), '어머님')
        cl1 = Checklist({'age': 62, 'sex': 'F', 'pediatric': False, 'categories': ['substance', 'insomnia']}, V2_C01)
        first = next(iter(cl1.items))
        self.assertTrue(first.startswith('sb_'))
        self.assertIn('ps_si', cl1.items)
        self.assertNotIn('wm_preg', cl1.items)  # 62세: 가임기 아님

    def test_validate_question(self):  # §15-4
        self.assertFalse(validate_question('최근체중이5kg이상증가했나요?')[0])
        self.assertFalse(validate_question('손과 발이 차갑게 느껴지는가?')[0])
        self.assertFalse(validate_question('가래가 나오나요? 색은요?')[0])
        self.assertTrue(validate_question('혹시 임신 가능성은 있으세요?')[0])

    def test_cover_re(self):  # §15-5
        self.assertIn('wl_fever', bank2.cover_hits('네, 밤엔 잠옷이 젖기도 해요'))
        self.assertIn('p_perinatal', bank2.cover_hits('네, 만삭에 자연분만했어요'))
        self.assertNotIn('pmh_htn_dm', bank2.cover_hits('아버지는 고혈압이에요'))
        self.assertNotIn('sh_alcohol', bank2.cover_hits('아니요, 수술받은 적 없어요'))

    def test_dup_prevention_r4(self):  # §15-14
        c = run_v2(V2_C10)
        says = [e[1] for e in c.events if e[0] == 'SAY']
        self.assertIn('땀이 많아지셨나요?', says)
        self.assertNotIn('열이 나거나 밤에 땀이 나나요?', says)
        self.assertNotIn('증상을 전부 말씀해 주세요.', says)
        self.assertNotIn('최근체중이5kg이상증가했나요?', says)
        self.assertEqual(len(says), len(set(says)))


class FakeEnc:
    def __init__(self, ledger, opening=V2_C10, prof=None):
        self.ledger = ledger
        self.opening = opening
        self.vitals = V2_VITALS
        self.profile = prof or {'age': 32, 'sex': 'F', 'pediatric': False, 'informant': '본인'}
        self.cfg = run.load_config()
        self.explained = []
        self.differentials = []
        self.dx = ''


class TestV2Record(unittest.TestCase):
    def test_facts_validate(self):  # §15-6
        from agent import facts
        ledger = [{'turn': 12, 'kind': 'SAY', 'text': '눈이 부어오르시나요?', 'reply': '네, 좀 부었어요.', 'phase': 'interview'},
                  {'turn': 13, 'kind': 'SAY', 'text': '입맛은 어떠세요?', 'reply': '입맛 좋아요.', 'phase': 'interview'},
                  {'turn': 14, 'kind': 'SAY', 'text': '체중은요?', 'reply': '네, 좀 빠졌어요.', 'phase': 'interview'},
                  {'turn': 15, 'kind': 'SAY', 'text': '가족 중 고혈압 있나요?', 'reply': '아버지가 고혈압이에요.',
                   'phase': 'interview'}]
        enc = FakeEnc(ledger)
        rows = facts.qa_rows(enc)
        out = facts.validate(enc, rows, [
            {'turn': 12, 'key': 'ros.Edema', 'pol': '+', 'label': '부종'},
            {'turn': 12, 'key': 'ros.Headache', 'pol': '+', 'label': '두통'},
            {'turn': 13, 'key': 'ros.Anorexia', 'pol': '+', 'label': '식욕'},
            {'turn': 14, 'key': 'other', 'pol': '+', 'label': '체중 감소', 'detail': '27kg'},
            {'turn': 15, 'key': 'fh.HTN', 'pol': '+', 'label': '고혈압'},
            {'turn': 99, 'key': 'pmh.DM', 'pol': '+'}])
        keys = [(f['turn'], f['key'], f['pol']) for f in out]
        self.assertIn((12, 'other', '+'), keys)
        self.assertNotIn((12, 'ros.Headache', '+'), keys)
        self.assertIn((13, 'ros.Anorexia', '-'), keys)
        self.assertTrue(any(f['label'] == '식욕 증가' for f in out))
        d14 = next(f for f in out if f['turn'] == 14)
        self.assertNotIn('27', d14['detail'])
        self.assertIn((15, 'fh.HTN', '+'), keys)
        self.assertFalse(any(f['turn'] == 99 for f in out))

    def test_render_assessment(self):  # §15-7
        from agent.assess import render_assessment
        enc = FakeEnc([])
        enc.dx = '그레이브스병에 의한 갑상샘항진증'
        a = {'facts': [{'id': 'F3', 'turn': 7, 'label': 'x', 'pol': '+', 'detail': '', 'sec': 'ros'}],
             'exams': [{'id': 'E2', 'turn': 32, 'name': '갑상선 촉진', 'result': '비대(+)'}],
             'evidence': [{'text': '더위 민감 → 대사 항진', 'refs': ['F3', 'E2']}, {'text': '근거2', 'refs': ['F3']}],
             'differential': [{'dx': '당뇨병', 'reason': '갈증(-)', 'refs': ['F3'], 'test': 'HbA1c'}]}
        out = render_assessment(enc, a)
        self.assertIn('(턴 7, 32)', out['evidence'])
        self.assertTrue(out['evidence'].startswith('#1. 그레이브스병'))
        self.assertIn('r/o 당뇨병 : 갈증(-) (턴 7). 감별 검사 : HbA1c', out['differential'])

    def test_render_fixed(self):  # §15-8
        from agent.note2 import render_fixed
        enc = FakeEnc([])
        enc.facts = [{'id': 'F1', 'turn': 5, 'sec': 'pmh', 'key': 'pmh.HTN', 'label': '고혈압', 'pol': '-', 'detail': ''},
                     {'id': 'F2', 'turn': 9, 'sec': 'pmh', 'key': 'pmh.HTN', 'label': '고혈압', 'pol': '+', 'detail': ''},
                     {'id': 'F3', 'turn': 10, 'sec': 'ros', 'key': 'other', 'label': '손떨림', 'pol': '+', 'detail': '글씨 쓸 때'}]
        out = render_fixed(enc, {})
        self.assertIn('DM / HTN ( /+)', out['pmh'])
        self.assertIn('previous stroke ( )', out['pmh'])
        self.assertIn('Tbc / hepatitis ( / )', out['pmh'])
        self.assertIn('손떨림(+, 글씨 쓸 때)', out['ros'])

    def test_say_checks(self):  # §15-9, §15-15
        self.assertTrue(saymod.say_problem('검사 후 재진 때 자세히 설명드릴게요.'))
        self.assertFalse(saymod.say_problem('약을 절대 갑자기 끊지 마세요.'))
        self.assertTrue(saymod.say_problem('검사 결과에 맞는 치료로 치료할 수 있어요.'))
        self.assertTrue(saymod.say_problem('검사로 원인을 확인하고 치료를 서두르겠습니다.'))
        lines = saymod.ensure_elements(['그레이브스병 같아요.'], '그레이브스병에 의한 갑상샘항진증', max_lines=9)
        self.assertEqual(lines[-1], saymod.QUESTION_LINE)
        self.assertFalse(saymod.missing_elements(lines[:-1], '그레이브스병에 의한 갑상샘항진증'))

    def test_plan_rules(self):  # §15-10
        from agent.explain import render_plan
        enc = FakeEnc([], prof={'age': 6, 'sex': 'M', 'pediatric': True, 'informant': '어머님'})
        enc.explained = ['피검사를 할게요.']
        plan = {'tests': ['골연령 : 확인'], 'treatment': ['메티마졸 15mg 하루 1회 시작', '아스피린 복용', '해열제 필요 시'],
                'disposition': [], 'follow_up': [], 'education': ['하루 50~70 mg 카페인 이하로']}
        out = render_plan(enc, plan, None)
        self.assertIn('검사 결과 확인 후 항갑상샘제 시작 고려', out['treatment'])  # v2c: 성분명 → 계열명
        self.assertNotIn('메티마졸', out['treatment'])
        self.assertNotIn('아스피린', out['treatment'])
        self.assertIn('50~70 mg', out['education'])
        self.assertIn('입원', out['disposition'])
        self.assertIn('즉시 내원', out['follow_up'])
        self.assertIn('진료 중 설명함:\n- 피검사를 할게요.', out['education'])


P_BANNED_RE = re.compile(
    r'(\d+(?:\s*[~\-–]\s*\d+)?\s*(?:mg|㎎|%|주분|일분|회분|정|알)(?:씩|만|분)?(?![가-힣a-zA-Z])'
    r'|메티마졸|프로프라놀롤|졸피뎀|레보티록신|메트포르민|아목시실린'
    r'|처방합니다|처방할게|드려요|드릴게|시작합니다|투여|단기\s*처방|입원\s*불필요|필요\s*없음)', re.I)


def assert_safe_plan(tc, note):
    """v2c: P 치료·처치·추적칸 금지 패턴 0, 정규화 후 중복/포함 줄 0."""
    for f in ('treatment', 'disposition', 'follow_up'):
        lines = [l[2:] for l in note['P'][f].split('\n') if l.startswith('- ')]
        for l in lines:
            if f == 'disposition' and re.search(r'(활력징후|mmHg)', l):
                tc.assertIsNone(re.search(r'(입원\s*불필요|필요\s*없음)', l), l)
                continue
            tc.assertIsNone(P_BANNED_RE.search(l), (f, l))
        keys = [explain._norm_line(l) for l in lines]
        for i, a in enumerate(keys):
            for j, b in enumerate(keys):
                if i != j:
                    tc.assertFalse(a in b, (f, lines[i], lines[j]))


class TestV2cSafety(unittest.TestCase):
    def test_kb_templates_clean(self):
        for k in kb.KB:
            adm = k.get('admit_if', '')
            for f in ('treatment', 'disposition', 'follow_up'):
                for line in k.get(f) or []:
                    out = explain.safe_plan_line(line, f, adm)
                    self.assertIsNone(P_BANNED_RE.search(out), (k['id'], f, out))
            for s in list(k.get('say') or []) + list((k.get('faq') or {}).values()) + \
                    [sent for _, sent in k.get('must_say') or []]:
                t = explain.safe_say(s)
                self.assertIsNone(explain.SAY_BAD_RE.search(t), (k['id'], t))
                self.assertLessEqual(nlen(t), 30, t)
                self.assertEqual(t, unicodedata.normalize('NFC', t))
        sed = kb.match_kb('수면제(진정수면제) 사용장애')
        txt = ' '.join(sed['treatment'])
        for w in ('급격한 중단 금지', '전문의 감독', '점진 감량', '처방 일원화', 'CBT-I', '수면위생', '상호작용', '정신건강의학과'):
            self.assertIn(w, txt)
        self.assertFalse(sed.get('must_treat'))

    def test_v2_final_lines_fixed(self):  # v2-final C01/C10 감점 문장 재현
        bad_treat = ['급중단 금지 — 당일 처방 내역(DUR)·실제 총량 확인 후 금단을 막는 최소 용량으로 1~2주분만 단기 처방'
                     '(처방 일원화), 이후 1~2주마다 10~25%씩 감량',
                     'TFT·TRAb 확인 후 항갑상샘제(메티마졸) 시작 고려', '프로프라놀롤 10mg 하루 3회 투여',
                     '레보티록신 50mcg 시작합니다', '졸피뎀 5정 2주분 드려요']
        for l in bad_treat:
            out = explain.safe_plan_line(l, 'treatment')
            self.assertIsNone(P_BANNED_RE.search(out), out)
            self.assertNotRegex(out, r'(하루\s*\d|mcg|\d+\s*주마다)')
        disp = explain.safe_plan_line('활력징후 대체로 안정 : BP 128/78 mmHg, PR 76 회/분 → 급성 위험 징후 없어 입원 불필요, '
                                      '외래 추적', 'disposition', '금단 경련')
        self.assertIn('128/78 mmHg', disp)
        self.assertIn('현재 외래 추적이 적절하며 금단 경련 시 입원 고려', disp)
        self.assertNotIn('불필요', disp)
        for s in ('오늘 끊진 않고, 확인한 최소량만 1~2주분 드려요.', '1~2주마다 조금씩 줄이면 다시 잘 수 있어요.',
                  '하루 2번 드세요.', '처방할게요.'):
            self.assertEqual(explain.safe_say(s), explain.SAFE_SAY)
        self.assertEqual(explain.safe_say('메티마졸은 아침에 드세요.'), '항갑상샘제는 아침에 드세요.')
        self.assertEqual(explain.safe_say('1~2주 뒤 결과 보러 오세요.'), '1~2주 뒤 결과 보러 오세요.')

    def test_dedup(self):
        lines = ['눈 건조·자극감이 있으면 인공눈물', '눈 건조 · 자극감이 있으면 인공눈물.', '급격한 중단 금지',
                 '급격한 중단 금지 — 전문의 감독 아래 점진 감량', '정신건강의학과 협진']
        self.assertEqual(explain.dedup_lines(lines),
                         ['눈 건조·자극감이 있으면 인공눈물', '급격한 중단 금지 — 전문의 감독 아래 점진 감량', '정신건강의학과 협진'])

    def test_render_plan_kb_no_llm_lines(self):
        from agent.explain import render_plan
        enc = FakeEnc([], prof={'age': 62, 'sex': 'F'})
        enc.explained = ['피검사를 할게요.']
        k = kb.match_kb('수면제(진정수면제) 사용장애')
        plan = {'tests': [], 'treatment': ['수면일지, 수면위생 교육 및 불면 인지행동치료를 권하고 협진', '졸피뎀 1~2주분 처방합니다'],
                'disposition': [], 'follow_up': ['재진: 1~2주 후 감량 단계 조정'], 'education': []}
        out = render_plan(enc, plan, k)
        self.assertNotIn('권하고', out['treatment'])
        self.assertNotIn('졸피뎀', out['treatment'])
        self.assertEqual(out['treatment'].count('급격한 중단 금지'), 1)
        self.assertIn('재진 전이라도 조기 연락', out['treatment'])
        self.assertIn('조기 연락 : 금단 증상', out['follow_up'])
        fl = out['follow_up'].split('\n')
        self.assertLess(next(i for i, l in enumerate(fl) if '조기 연락' in l),
                        next(i for i, l in enumerate(fl) if '즉시 내원' in l))
        plan_ec = dict(plan, follow_up=['재진 : 1~2주 후', '금단 증상 시 재진 전 조기 연락'])
        self.assertEqual(render_plan(enc, plan_ec, k)['follow_up'].count('조기 연락'), 1)
        assert_safe_plan(self, {'P': out})
        # KB 없는 진단: LLM 줄은 필터 후 최대 2개(+금기 확인 줄)
        plan2 = {'tests': [], 'treatment': ['A약 10mg 하루 2회 시작합니다', '휴식', '수분 섭취', '운동'],
                 'disposition': ['입원 필요 없음'], 'follow_up': [], 'education': []}
        out2 = render_plan(enc, plan2, None)
        tl = [l for l in out2['treatment'].split('\n') if l]
        self.assertLessEqual(len([l for l in tl if '금기·약물 알레르기' not in l]), 2)
        assert_safe_plan(self, {'P': out2})


class TestV2DryRun(unittest.TestCase):
    def check_note(self, c):
        self.assertIsNotNone(c.diagnosed)
        note, dx = c.diagnosed
        self.assertTrue(dx.strip())
        for s, fs in RECORD_FIELDS.items():
            for f in fs:
                self.assertIsInstance(note[s][f], str)
        says = [e[1] for e in c.events if e[0] == 'SAY']
        self.assertTrue(all(nlen(s) <= 30 for s in says))
        return note, dx, says

    def test_good_c10(self):
        c = run_v2(V2_C10)
        note, dx, says = self.check_note(c)
        self.assertIn('그레이브스병', dx)
        self.assertLessEqual(c.turns, 44)
        self.assertIn('혹시 임신 가능성은 있으세요?', says)
        self.assertTrue(says[0].startswith('많이 걱정되셨겠어요.'))
        self.assertNotIn('재진 때 자세히 설명드릴게요.', says)
        self.assertNotIn('검사 결과에 맞는 치료로 치료할 수 있어요.', says)
        self.assertEqual(says.count(saymod.QUESTION_LINE), 1)
        self.assertIn('결과는 일주일쯤 뒤에 나와요.', says)  # FAQ 즉답
        self.assertIn('(턴', note['A']['evidence'])
        self.assertNotIn('F99', note['A']['evidence'])
        self.assertNotIn('99', note['S']['hpi'])
        self.assertIn('Ht 164 cm, Wt 49 kg', note['O']['exam'])
        self.assertIn('BMI 18.2', note['O']['exam'])
        self.assertNotIn('수면제', note['P']['treatment'])  # KB avoid
        self.assertNotIn('15mg', note['P']['treatment'])
        assert_safe_plan(self, note)
        edu = note['P']['education']
        said = set(says)
        for line in edu.split('\n'):
            if line.startswith('- '):
                self.assertIn(line[2:], said)
        info = run.LAST_RUN
        self.assertLessEqual(info['budget']['doctor_calls'], 14)

    def test_peds_c03(self):
        c = run_v2(V2_C03)
        note, dx, says = self.check_note(c)
        self.assertIn('체질성', dx)
        self.assertTrue(any('어머님' in s for s in says))
        self.assertFalse(any('임신 가능성' in s for s in says))
        self.assertIn('해당 없음(소아)', note['S']['sh'])

    def test_c01_substance_first(self):
        c = run_v2(V2_C01)
        note, dx, says = self.check_note(c)
        self.assertTrue(any(re.search(r'(약 이름|몇 알|언제부터 드셨)', s) for s in says[:5]))
        self.assertFalse(any('임신' in s for s in says))
        # 진정제 의존(v2c): 급중단 금지·운전 회피를 말하되 구두 처방·수치 지시는 없음
        self.assertIn('약은 갑자기 끊지 말고 천천히 줄여요.', says)
        self.assertTrue(any('운전' in s for s in says))
        self.assertFalse(any(explain.SAY_BAD_RE.search(s) for s in says), says)
        tr = note['P']['treatment']
        self.assertIn('급격한 중단 금지', tr)
        self.assertIn('점진 감량', tr)
        self.assertIn('CBT-I', tr)
        self.assertNotIn('1~2주분', tr)
        self.assertNotIn('%', tr)
        self.assertNotIn('수면제 추가 처방', tr)
        self.assertNotIn('입원 불필요', note['P']['disposition'])
        assert_safe_plan(self, note)

    def test_presets(self):  # §15-13
        for preset, cap in (('bal44', 44), ('comm46', 46), ('lean38', 38)):
            c = run_v2(V2_C10, patient='no', preset=preset)
            note, dx, says = self.check_note(c)
            self.assertLessEqual(c.turns, cap, preset)
            ex = [s for e, s in zip(c.events, says) if True]
            expl = run.LAST_RUN['explained']
            self.assertFalse(saymod.missing_elements(expl, dx), (preset, expl))

    def test_turn_allocation(self):  # 조정자 함정 체크리스트: 단계별 턴 배분 드라이런
        c = run_v2(V2_C10)
        led = run.LAST_RUN['ledger']
        phases = [e.get('phase') for e in led]
        exams = [e for e in led if e['kind'] == 'EXAM']
        self.assertFalse(any('활력징후' in e['text'] for e in exams))  # 시작 정보에 활력징후가 있으면 재측정 안 함
        self.assertGreaterEqual(len(exams) - 1, 8)  # 전반적 외관 외 증례별 진찰 8개 이상
        q = [e for e in led if e['kind'] == 'SAY' and e.get('phase') in ('first', 'interview', 'ice')]
        self.assertEqual(len(q), run.PRESETS['bal44']['INTERVIEW_Q'])
        concern = next(i for i, e in enumerate(q) if e.get('qid') == 'ice_concern')
        self.assertLess(concern, 12)  # 걱정(ICE)은 문진 앞쪽
        self.assertGreaterEqual(phases.count('explain'), 6)  # 모의 LLM은 문장을 적게 줌: 필수 요소 보충 후 최소 6
        self.assertLessEqual(c.turns, 44)

    def test_vague_dx_replaced(self):  # r6b C03: '원인 미상의 저신장증' → 후보 중 구체 질환
        class VagueClient(V2Client):
            def answer(self, user):
                if 'diagnosis_ko' in user:
                    return json.dumps({'diagnosis_ko': '원인 미상의 저신장증', 'diagnosis_en': 'Short stature of undetermined etiology',
                                       'candidates': [{'dx': '가족성 저신장', 'for': ['F1'], 'against': ['F2', 'F3']},
                                                      {'dx': '체질성 성장지연', 'for': ['F1', 'F2'], 'against': []}],
                                       'evidence': [], 'differential': []}, ensure_ascii=False)
                return super().answer(user)
        c = VagueClient(V2_C03)
        with mock.patch.dict(os.environ, {'NOVA_AGENT_V2': '1', 'NOVA_AGENT_V3': '0', 'NOVA_AGENT_TURN_PRESET': 'bal44'}):
            state = run.prepare()
        run.consult(c, state)
        self.assertIn('체질성 성장지연', c.diagnosed[1])

    def test_llm_error(self):
        c = run_v2(V2_C10, llm='error')
        note, dx, says = self.check_note(c)
        self.assertGreaterEqual(c.chat_calls, 1)

    def test_slow_provider(self):  # §15-12 장애 모의: 호출당 120초 지연, 1,800초 안에 DIAGNOSE 1회
        clock = Clock()
        with mock.patch('time.time', clock.now), mock.patch('time.sleep', clock.sleep):
            c = run_v2(V2_C10, clock=clock, chat_delay=120.0)
        self.assertEqual(c.diagnose_calls, 1)
        self.assertLessEqual(clock.now() - (c.deadline.timestamp() - 1800), 1800)
        note, dx, says = self.check_note(c)


if __name__ == '__main__':
    unittest.main()

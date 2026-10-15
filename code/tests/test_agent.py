"""단위 테스트 + 모의 LLM 드라이런.  실행: cd code && python -m unittest discover -s tests -v"""
import json
import os
import random
import sys
import unittest
import unicodedata
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from nova_sdk import RECORD_FIELDS, NovaError  # noqa: E402

import run  # noqa: E402
from agent import banks  # noqa: E402
from agent.util import (extract_numbers, is_similar, parse_age, parse_json, parse_korean_number, parse_sex,  # noqa: E402
                        split_to_fit, validate_question)

C01 = '저는 박선희이고, 예순두 살 여자이다. 잠을 잘 못 자서 병원에 왔다. 수면제를 처방해 달라고 왔다.'
C03 = ('이름은 김도현이고, 여섯 살 남자아이이다. 엄마 김지영, 서른일곱 살이 보호자로 함께 왔다. 엄마는 도현이 키가 또래에 비해 '
       '많이 작은 것 같아 걱정이 된다고 말했다. 일 년 전에는 백 센티미터였고 지금은 백오 센티미터 정도였다. '
       '몸무게는 일 년 전 십오 키로그람에서 지금은 십육 점 오 키로그람으로 일 점 오 키로그람 늘었다.')
C10 = ('이름은 최윤정이고, 나는 서른두 살 여자이다. 최근 석 달 동안 살이 많이 빠져서 병원에 오게 되었다. 원래 몸무게는 '
       '오십육 키로그람 정도였는데, 최근 석 달 사이에 칠 키로그람 정도 빠져서 지금은 사십구 키로그람 정도이다. 키는 백육십사 센티미터이다.')


def nlen(s):
    return len(unicodedata.normalize('NFC', s))


class TestBanks(unittest.TestCase):
    def all_questions(self):
        qs = []
        for lst in (banks.ADULT_HPI, banks.PEDS_HPI, banks.ADULT_HISTORY, banks.PEDS_HISTORY, banks.ADULT_ROS,
                    banks.PEDS_ROS, banks.ADULT_ICE, banks.PEDS_ICE, banks.WOMEN_BUNDLE):
            qs += [x[1] for x in lst]
        for _, (_, adult, peds) in banks.CATEGORY_BUNDLES.items():
            qs += [x[1] for x in adult + peds]
        return qs

    def test_question_length(self):
        for q in self.all_questions():
            self.assertLessEqual(nlen(q), 30, q)
            self.assertTrue(q.strip())

    def test_question_validator_on_bank(self):
        for q in self.all_questions():
            ok, why = validate_question(q)
            self.assertTrue(ok, f'{q}: {why}')

    def test_no_false_duplicates(self):
        """같은 진료에서 함께 쓰일 수 있는 은행 문항끼리 중복으로 판정되면 안 된다."""
        for peds in (False, True):
            lists = ((banks.PEDS_HPI, banks.PEDS_HISTORY, banks.PEDS_ROS, banks.PEDS_ICE) if peds else
                     (banks.ADULT_HPI, banks.ADULT_HISTORY, banks.ADULT_ROS, banks.ADULT_ICE, banks.WOMEN_BUNDLE))
            qs = [x[1] for lst in lists for x in lst]
            qs += [x[1] for x in banks.bundle_questions(list(banks.CATEGORY_BUNDLES), peds)]
            qs = list(dict.fromkeys(qs))
            dups = []
            for i, q in enumerate(qs):
                if is_similar(q, qs[:i]):
                    dups.append(q)
            # 일부 묶음 문항은 ROS와 일부러 겹친다(묶음이 먼저 나가면 ROS 문항 생략). 그 수만 제한.
            self.assertLessEqual(len(dups), 8, dups)
            for q in ('가족 중 당뇨나 고혈압 있으세요?', '엄마 키는 얼마인가요?'):
                self.assertNotIn(q, dups)

    def test_exam_bank(self):
        ids = set()
        self.assertGreaterEqual(len(banks.EXAM_BANK), 85)
        for e in banks.EXAM_BANK:
            self.assertEqual(len(e), 5)
            self.assertLessEqual(nlen(e[1]), 30, e[1])
            self.assertNotIn(e[0], ids)
            ids.add(e[0])
            self.assertTrue(e[1].endswith('하겠습니다'), e[1])
        for c, lst in banks.CATEGORY_EXAMS.items():
            for i in lst:
                self.assertIn(i, banks.EXAM_BY_ID, (c, i))

    def test_standard_names_present(self):
        names = ['전반적 외관 시진', '의식·지남력 평가', '활력징후 측정', '결막·공막 시진', '갑상선 촉진', '흉곽 시진', '폐 청진',
                 '심음 청진', '복부 시진', '복부 촉진', '간·비장 촉진', '하지 말초 진찰', '보행 관찰', '자세성 떨림', '심부건반사',
                 '사지 근력 검사', '경부 림프절 촉진', '갑상선 안징후 검사', '갑상선 잡음 청진', '장음 청진', '피부 온도·발한 촉진',
                 '기립성 혈압 측정', '인지기능 선별검사', '신체 계측', '성장도표 백분위수 확인', '사춘기 성숙도 평가', '신체 비율 평가',
                 '안면 기형 소견 시진', '구음장애 확인', '안구진탕 확인', '소뇌 협조운동 검사', '롬베르그 검사', '요골동맥 맥박 촉진',
                 '외안근 운동', '경골앞 점액부종', '자주색 선조 시진', '떨림·서동 관찰', '주간 진정·불안 관찰', '병식 평가']
        phrases = ' | '.join(e[1] for e in banks.EXAM_BANK)
        for n in names:
            self.assertIn(n, phrases, n)


class TestUtil(unittest.TestCase):
    def test_korean_numbers(self):
        self.assertEqual(parse_korean_number('예순두'), 62)
        self.assertEqual(parse_korean_number('서른두'), 32)
        self.assertEqual(parse_korean_number('여섯'), 6)
        self.assertEqual(parse_korean_number('서른일곱'), 37)
        self.assertEqual(parse_korean_number('스무'), 20)
        self.assertEqual(parse_korean_number('백오'), 105)
        self.assertEqual(parse_korean_number('백육십사'), 164)
        self.assertEqual(parse_korean_number('육십이'), 62)
        self.assertEqual(parse_korean_number('십육점오'), 16.5)
        self.assertEqual(parse_korean_number('42'), 42)

    def test_age_sex(self):
        self.assertEqual(parse_age(C01), 62)
        self.assertEqual(parse_age(C03), 6)
        self.assertEqual(parse_age(C10), 32)
        self.assertEqual(parse_age('45세 남자입니다'), 45)
        self.assertEqual(parse_sex(C01), 'F')
        self.assertEqual(parse_sex(C03), 'M')
        self.assertEqual(parse_sex(C10), 'F')

    def test_extract_numbers(self):
        nums = extract_numbers(C10)
        for n in ('32', '56', '7', '49', '164', '3'):
            self.assertIn(n, nums, n)
        nums3 = extract_numbers(C03)
        for n in ('6', '37', '100', '105', '15', '16.5', '1.5'):
            self.assertIn(n, nums3, n)

    def test_parse_json(self):
        self.assertEqual(parse_json('```json\n{"a": 1}\n```'), {'a': 1})
        self.assertEqual(parse_json('설명입니다 {"a": [1,2,],} 끝'), {'a': [1, 2]})
        self.assertEqual(parse_json('["x", "y"]', list), ['x', 'y'])
        self.assertEqual(parse_json('text {“q”: “값”}'), {'q': '값'})
        self.assertIsNone(parse_json('없음'))
        self.assertIsNone(parse_json(''))
        self.assertEqual(parse_json('{"a": {"b": 2}} {"c": 3}'), {'a': {'b': 2}})

    def test_validator(self):
        self.assertTrue(validate_question('언제부터 그러셨어요?')[0])
        self.assertFalse(validate_question('증상을 전부 말씀해 주세요.')[0])
        self.assertFalse(validate_question('가' * 31)[0])
        self.assertFalse(validate_question('열 있나요? 기침은요?')[0])
        self.assertFalse(validate_question('무슨 병인지 아세요?')[0])
        self.assertFalse(validate_question('언제부터 그러셨나요?', ['언제부터 그러셨어요?'])[0])
        self.assertFalse(validate_question('두통, 어지럼, 구토 있나요?')[0])

    def test_similar(self):
        self.assertTrue(is_similar('담배 피우세요?', ['담배는 피우세요?']))
        self.assertFalse(is_similar('담배 피우세요?', ['술은 얼마나 드세요?']))

    def test_split(self):
        parts = split_to_fit('갑상선 기능 항진증이 의심되어 혈액검사와 초음파 검사를 하려고 합니다 괜찮으세요')
        self.assertTrue(all(nlen(p) <= 30 for p in parts))


# ------------------------------------------------------------------ 모의 클라이언트
class FakeClient:
    """서버 규칙 일부를 흉내 내는 가짜 클라이언트. llm_mode: good | garbage | error"""

    def __init__(self, opening, vitals, llm_mode='good', minutes=30):
        self.opening, self.vitals, self.llm_mode = opening, vitals, llm_mode
        self.deadline = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        self.turns = 0
        self.events = []
        self.diagnosed = None
        self.chat_calls = 0
        self.rng = random.Random(0)

    def session(self):
        return {'session_id': 'x', 'status': 'active', 'turns_remaining': 50 - self.turns,
                'initial': {'opening': self.opening, 'vital_signs': self.vitals}, 'deadline': self.deadline.isoformat()}

    def _turn(self, kind, content):
        if self.diagnosed is not None:
            raise NovaError('SESSION_CLOSED', 409)
        if self.turns >= 50:
            raise NovaError('TURN_LIMIT_REACHED', 409)
        if not content or nlen(content) > 30:
            self.turns += 1
            raise NovaError('CONTENT_TOO_LONG', 400)
        self.turns += 1

    def say(self, content, request_id=None):
        self._turn('SAY', content)
        ans = '한 번에 하나씩 물어봐 주세요.' if '전부' in content else '네, 그런 편이에요.'
        self.events.append(('SAY', content, ans))
        return {'status': 'OK', 'content': ans, 'turn': self.turns, 'turns_remaining': 50 - self.turns}

    def exam(self, content, request_id=None):
        self._turn('EXAM', content)
        if '피부 발진' in content:
            raise NovaError('EXAM_NOT_RECOGNIZED', 422)
        res = '특이 소견(-)'
        self.events.append(('EXAM', content, res))
        return {'status': 'OK', 'result': res, 'turn': self.turns, 'turns_remaining': 50 - self.turns}

    def diagnose(self, note, diagnosis, request_id=None):
        if set(note) != set(RECORD_FIELDS) or any(set(note[s]) != set(f) for s, f in RECORD_FIELDS.items()):
            raise NovaError('INVALID_RECORD_FIELDS', 400)
        assert all(isinstance(v, str) for s in note.values() for v in s.values())
        assert diagnosis and '\n' not in diagnosis
        self.diagnosed = (note, diagnosis)
        return {'status': 'completed'}

    def chat(self, messages, max_tokens=2048, reasoning_effort=None, temperature=None, request_id=None, model=None):
        self.chat_calls += 1
        for m in messages:
            assert set(m) == {'role', 'content'} and m['content'].strip()
        user = messages[-1]['content']
        if self.llm_mode == 'error':
            raise NovaError('PROVIDER_RESPONSE_INVALID', 503)
        if self.llm_mode == 'garbage':
            text = self.rng.choice(['', '음... 잘 모르겠습니다', '{"broken": ', '[]', 'null'])
            if not text:
                raise NovaError('PROVIDER_RESPONSE_INVALID', 503)
        else:
            text = self.good_answer(user)
        return {'choices': [{'message': {'content': text}, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': len(user) // 2, 'completion_tokens': 50}}

    def good_answer(self, user):
        if '"empathy"' in user:
            return json.dumps({'age': 62, 'sex': 'F', 'pediatric': False, 'chief_complaint': '불면', 'pain': False,
                               'categories': ['sleep', 'drug'], 'answered': [], 'empathy': '잠을 못 주무셔서 힘드셨겠어요.'},
                              ensure_ascii=False)
        if '"questions"' in user and 'differentials' in user:
            return json.dumps({'differentials': ['수면제 의존', '불면장애'],
                               'questions': ['약을 줄이면 어떤 증상이 생기나요?', '증상을 전부 말해 주세요',
                                             '여러 병원에서 약을 받으시나요, 아니면 한 곳에서 받으시나요?', '낮에도 약을 드세요?']},
                              ensure_ascii=False)
        if '"questions"' in user:
            return json.dumps({'questions': ['여러 병원에서 약 받으세요?']}, ensure_ascii=False)
        if 'exam_ids' in user:
            return json.dumps({'exam_ids': ['mental', 'skin_rash', 'sedation', 'post_tremor', 'nonexistent', 'gait']})
        if 'diagnosis_ko' in user:
            return json.dumps({'diagnosis_ko': '수면제 의존', 'diagnosis_en': 'Sedative-Hypnotic Use Disorder',
                               'confidence': 0.8, 'key_evidence': ['내성'], 'top_differentials': ['불면장애']},
                              ensure_ascii=False)
        if '"tests"' in user and 'disposition' in user:
            return json.dumps({'tests': '- TFT : 감별', 'treatment': '- 점진 감량(졸피뎀 10mg/일에서 시작)', 'disposition': '- 외래',
                               'follow_up': '- 2주 후', 'education': '- 수면위생'}, ensure_ascii=False)
        if '[SAY 규칙]' in user:
            return json.dumps({'say': ['수면제 의존이 의심돼요.', '약에 몸이 익숙해져 양이 늘어난 상태예요.',
                                       '걱정 안 해도 돼요.', '피검사와 심전도를 할게요.',
                                       '오늘 끊지 않고 1~2주마다 조금씩 줄여요.', '졸릴 땐 운전은 피하세요.',
                                       '경련·혼동·환각·심한 불안이 오면 바로 오세요.', '1~2주 뒤 오셔서 양을 조정해요.']},
                              ensure_ascii=False)
        if '"say"' in user:
            return json.dumps({'say': ['걱정되시는 마음 이해해요.']}, ensure_ascii=False)
        if '"dx_plain"' in user:
            return json.dumps({'dx_plain': '수면제 의존', 'cause_plain': '수면제 장기 복용', 'tests': '피검사와 심전도',
                               'treatment': '천천히 약을 줄이는 치료로 아주 오랫동안 꾸준히', 'warning': '경련이나 혼동',
                               'lifestyle': '낮잠은 피하고 같은 시간에 일어나세요.',
                               'concern_reply': '걱정 안 해도 돼요.'}, ensure_ascii=False)
        if '"answer"' in user:
            return json.dumps({'answer': '네, 함께 천천히 해 봐요.'}, ensure_ascii=False)
        if '"findings"' in user:
            return json.dumps({'findings': [{'turn': 2, 'key': 'hpi.onset', 'pol': '?', 'detail': '7년 전'},
                                            {'turn': 15, 'key': 'pmh.DM', 'pol': '-', 'detail': ''},
                                            {'turn': 15, 'key': 'pmh.HTN', 'pol': '+', 'detail': ''},
                                            {'turn': 7, 'key': 'ros.other:손떨림', 'pol': '+', 'detail': ''},
                                            {'turn': 999, 'key': 'pmh.DM', 'pol': '+', 'detail': ''}]},
                              ensure_ascii=False)
        if '"cc_text"' in user:
            return json.dumps({'cc_text': '불면', 'onset': '7년 전', 'pain': '해당 없음',
                               'hpi': '62세 여자. 7년 전부터 불면. 하루 99알 복용.\\n수면제 처방 원해 내원함.'},
                              ensure_ascii=False)
        if '"evidence"' in user:
            return json.dumps({'evidence': '#1. 수면제 의존\n- 근거 : 내성',
                               'differential': 'r/o 불면장애 : 내성 뚜렷해 단독 진단으로 부족\nr/o 우울증'},
                              ensure_ascii=False)
        if '"differential"' in user:
            return json.dumps({'differential': 'r/o 우울증 : 우울감 없음. PHQ-9로 선별'}, ensure_ascii=False)
        return '{}'


VITALS = '혈압 : 128/78 mmHg\n맥박 : 76 회/분\n호흡 : 18 회/분\n체온 : 36.6°C'


class TestDryRun(unittest.TestCase):
    def test_plan_dose_removed(self):
        from agent.record import clean_plan_text
        self.assertNotIn('mg', clean_plan_text('- 메티마졸 20~40mg/일 시작 고려\n- 프로프라놀롤 20 mg 하루 3회',
                                               strip_dose=True))
        self.assertIn('검사 결과 확인 후', clean_plan_text('- 메티마졸 15mg 하루 1회 시작', strip_dose=True))
        self.assertIn('50~70 mg', clean_plan_text('- 하루 50~70 mg 카페인 이하', strip_dose=False))

    def run_case(self, mode, opening=C01, minutes=30):
        """v1(Phase A) 흐름 회귀 테스트: NOVA_AGENT_V2=0."""
        from unittest import mock
        client = FakeClient(opening, VITALS, mode, minutes=minutes)
        with mock.patch.dict(os.environ, {'NOVA_AGENT_V2': '0'}):
            state = run.prepare()
        run.consult(client, state)
        return client

    def test_good_llm(self):
        c = self.run_case('good')
        self.assertIsNotNone(c.diagnosed)
        note, dx = c.diagnosed
        self.assertIn('수면제 의존', dx)
        self.assertLessEqual(c.turns, 50)
        self.assertIn('턴', note['O']['exam'])
        self.assertIn('진료 중 설명함', note['P']['education'])
        self.assertNotIn('99', note['S']['hpi'])  # 진료 기록에 없는 숫자 제거
        self.assertGreaterEqual(c.chat_calls, 1)
        says = [e for e in c.events if e[0] == 'SAY']
        self.assertTrue(all(nlen(e[1]) <= 30 for e in says))
        info = run.LAST_RUN
        self.assertEqual(info['counts']['exam_refused'], 1)  # 피부 발진은 거절 → 블랙리스트
        self.assertIn('DM / HTN (', note['S']['pmh'])
        self.assertIn('손떨림(+)', note['S']['ros'])
        self.assertFalse(any('\\n' in v for sec in note.values() for v in sec.values()))  # 리터럴 백슬래시-n 없음
        self.assertIn('r/o 우울증 : 우울감 없음', note['A']['differential'])
        self.assertIn('활력징후', note['P']['disposition'])
        self.assertNotIn('걱정 안 해도', note['P']['education'])
        self.assertIn('수면제 의존이 의심돼요.', note['P']['education'])
        says = [e[1] for e in c.events if e[0] == 'SAY']
        from agent.say import QUESTION_LINE
        self.assertEqual(says.count(QUESTION_LINE), 1)
        self.assertNotIn('걱정 안 해도 돼요.', says)  # UNSAFE 문장은 말하지 않음
        self.assertLessEqual(c.turns, 48)

    def test_garbage_llm(self):
        c = self.run_case('garbage')
        self.assertIsNotNone(c.diagnosed)
        note, dx = c.diagnosed
        self.assertTrue(dx.strip())
        self.assertTrue(note['O']['exam'])
        self.assertTrue(note['S']['hpi'])

    def test_error_llm(self):
        c = self.run_case('error')
        self.assertIsNotNone(c.diagnosed)

    def test_pediatric(self):
        c = self.run_case('good', opening=C03)
        self.assertIsNotNone(c.diagnosed)
        says = [e[1] for e in c.events if e[0] == 'SAY']
        self.assertTrue(any('만삭' in s for s in says))

    def test_nearly_expired(self):
        c = self.run_case('good', minutes=1.2)  # 72초 남음: 행동 없이도 Doctor 1회 호출 + 기록 제출
        self.assertIsNotNone(c.diagnosed)
        self.assertGreaterEqual(c.chat_calls, 1)

    def test_short_time(self):
        c = self.run_case('good', minutes=5)
        self.assertIsNotNone(c.diagnosed)


from test_v2 import *  # noqa: E402,F401,F403  v2 수용 테스트(§15)
from test_v3 import *  # noqa: E402,F401,F403  v3 검증기·안전·probe50 드라이런

if __name__ == '__main__':
    unittest.main()

"""v7 통합 테스트(code/docs/v7_spec.md §4.1 T1~T20 + C7 프리셋). API 없이 실행.

구성
- 공통 헬퍼
- [A] facts·note2·record: T1·T2·T3·T11·T12·T13 + vitals_assessment(short)·polish_note(C5)
- [B] interview·bank2: T4·T5·T6
- [C] assess·explain·kb: T7·T8·T9·T10·T14·T15·T16·T17 + KB refer_if
- [D] 드라이런·설정: T18(안전 grep)·T19(턴 구조)·C7 프리셋 3종 드라이런·T20(preset.json)
"""
import contextlib
import copy
import functools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unicodedata
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
V7 = os.path.dirname(HERE)
V6 = os.path.join(os.path.dirname(V7), 'code_v6')
sys.path.insert(0, V7)
sys.path.insert(0, HERE)

from nova_sdk import empty_record  # noqa: E402

import run  # noqa: E402
from agent import assess, bank2, banks, explain, facts, interview, kb, note2, record, say as saymod  # noqa: E402
from agent.interview import Checklist  # noqa: E402
import test_v2  # noqa: E402
import test_v5  # noqa: E402
from test_v2 import P_BANNED_RE, V2_C01, V2_C10, V2_VITALS, assert_safe_plan  # noqa: E402


# ================================================================ 공통 헬퍼
GRAVES = '그레이브스병에 의한 갑상샘항진증'
SED = '수면제(진정수면제) 사용장애'
DRUG_RE = re.compile(explain._DRUG_ANY, re.I)
DOSE_RE = re.compile(r'\d+(?:\s*[~\-–]\s*\d+)?\s*(?:mg|㎎|mcg|µg|μg|정|알|캡슐|주분|일분|회분)(?![가-힣a-zA-Z])|하루\s*\d+\s*(?:회|번)',
                     re.I)


def nlen(s):
    return len(unicodedata.normalize('NFC', s))


@functools.lru_cache(maxsize=None)
def _dry(root, opening_name, preset=None):
    """root(code_v6/code_v7)의 test_v2 가짜 서버로 한 증례를 돌린다(별도 프로세스: agent 패키지 충돌 방지).

    preset: 주면 별도 프로세스 안에서 run.PRESET_FILE을 그 경로로 바꾼다(code_v7/preset.json을 만들지 않음).
    같은 인자는 한 번만 돌린다(lru_cache). 결과 dict는 읽기만 할 것.
    """
    code = ('import sys, json, io, contextlib\n'
            f'sys.path.insert(0, {os.path.join(root, "tests")!r})\n'
            'with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):\n'
            '    import test_v2, run\n'
            + (f'    run.PRESET_FILE = {preset!r}\n' if preset else '') +
            f'    c = test_v2.run_v2(test_v2.{opening_name})\n'
            'ph = {}\n'
            'for e in run.LAST_RUN.get("ledger") or []:\n'
            '    ph[e.get("phase")] = ph.get(e.get("phase"), 0) + 1\n'
            'print(json.dumps({"turns": c.turns, "counts": run.LAST_RUN.get("counts"), "phases": ph,'
            ' "say": [e[1] for e in c.events if e[0] == "SAY"], "exam": [e[1] for e in c.events if e[0] == "EXAM"],'
            ' "P": c.diagnosed[0]["P"] if c.diagnosed else None}, ensure_ascii=False))\n')
    env = {k: v for k, v in os.environ.items() if k != 'NOVA_DEV_KEY' and not k.startswith('NOVA_AGENT_')}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    out = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, env=env, timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def _explain_turns(r):
    return r['phases'].get('explain', 0) + r['phases'].get('explain-answer', 0)


# ================================================================ [A] facts·note2·record
A_OPENING = ('이름은 최윤정이고, 나는 서른두 살 여자이다. 최근 석 달 동안 살이 많이 빠져서 병원에 오게 되었다. 원래 몸무게는 '
             '오십육 키로그람 정도였는데, 최근 석 달 사이에 칠 키로그람 정도 빠져서 지금은 사십구 키로그람 정도이다.')


def _say(turn, q, a, phase='interview', qid=''):
    return {'turn': turn, 'kind': 'SAY', 'text': q, 'reply': a, 'phase': phase, 'qid': qid}


class FakeEnc:
    def __init__(self, ledger=None, opening=A_OPENING, vitals=V2_VITALS, cfg=None):
        self.ledger = ledger or []
        self.opening = opening
        self.vitals = vitals
        self.profile = {'age': 32, 'sex': 'F', 'pediatric': False, 'informant': '본인', 'cc': '체중 감소'}
        self.cfg = cfg if cfg is not None else run.load_config()
        self.client = None
        self.budget = None
        self.facts = []
        self.explained = []
        self.differentials = []
        self.dx = ''
        self.derived = {}


LEDGER = [_say(1, '가슴이 아프거나 답답하세요?', '아니요, 그런 건 없어요.'),
          _say(2, '두근거림이 있으세요?', '네, 가끔 두근거려요.'),
          _say(3, '머리가 아프세요?', '심하게 아픈 건 없어요.'),
          _say(4, '대변은 어떠세요?', '하루 2~3번 봐요.'),
          _say(5, '드시는 약 있으세요?', '없어요.')]


class TestT1RowsFrom(unittest.TestCase):
    def test_mixed_rows(self):
        res = {'f': [[1, 'ros', 'ros.Chest pain', '흉통', '-', ''],
                     [2, 'ros', '', '두근거림', '+'],                       # 세부 생략(길이 5)
                     {'turn': 4, 'sec': 'hpi', 'key': 'other', 'label': '배변 횟수', 'pol': '?', 'detail': '하루 2~3번'},
                     [3, 'ros', 'ros.Headache'],                           # 길이 5 미만 → 버림
                     'junk']}
        rows = facts._rows_from(res)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1]['key'], 'other')
        self.assertEqual(rows[1]['detail'], '')
        self.assertEqual(rows[0], {'turn': 1, 'sec': 'ros', 'key': 'ros.Chest pain', 'label': '흉통', 'pol': '-',
                                   'detail': ''})

    def test_same_as_json_after_validate(self):
        enc = FakeEnc(LEDGER)
        qa = facts.qa_rows(enc)
        obj = {'facts': [{'turn': 1, 'sec': 'ros', 'key': 'ros.Chest pain', 'label': '흉통', 'pol': '-', 'detail': ''},
                         {'turn': 2, 'sec': 'ros', 'key': 'ros.Palpitation', 'label': '두근거림', 'pol': '+', 'detail': '가끔'},
                         {'turn': 4, 'sec': 'hpi', 'key': 'other', 'label': '배변 횟수', 'pol': '?', 'detail': '하루 2~3번'}]}
        comp = {'f': [[1, 'ros', 'ros.Chest pain', '흉통', '-', ''], [2, 'ros', 'ros.Palpitation', '두근거림', '+', '가끔'],
                      [4, 'hpi', '', '배변 횟수', '?', '하루 2~3번']]}
        a = facts.validate(enc, qa, facts._rows_from(obj))
        b = facts.validate(enc, qa, facts._rows_from(comp))
        self.assertEqual(a, b)
        self.assertEqual(len(a), 3)


class TestT2QualityGate(unittest.TestCase):
    def _run(self, replies, fmt='compact'):
        cfg = run.load_config()
        cfg['FACTS_FORMAT'] = fmt
        enc = FakeEnc(LEDGER, cfg=cfg)
        tags = []

        def fake(*a, **k):
            tags.append(k.get('tag'))
            r = replies[len(tags) - 1]
            if r is not None:
                assert k['validate'](r)
            return r
        with mock.patch.object(facts, 'ask_json', side_effect=fake):
            out = facts.extract(enc)
        return tags, out

    def test_retry_when_too_few(self):
        json_res = {'facts': [{'turn': t, 'sec': 'hpi', 'key': 'other', 'label': f'항목{t}', 'pol': '+'} for t in (1, 2, 3, 4)]}
        tags, out = self._run([{'f': [[2, 'ros', '', '두근거림', '+', '가끔']]}, json_res])
        self.assertEqual(tags, ['facts', 'facts-json'])
        self.assertGreaterEqual(len(out), 4)
        self.assertEqual([f['id'] for f in out], [f'F{i}' for i in range(1, len(out) + 1)])

    def test_no_retry_when_enough(self):
        comp = {'f': [[t, 'hpi', '', f'항목{t}', '+', ''] for t in (1, 2, 3, 4)]}
        tags, out = self._run([comp])
        self.assertEqual(tags, ['facts'])
        self.assertEqual(len([f for f in out if f['label'].startswith('항목')]), 4)

    def test_retry_fail_fallback(self):
        tags, out = self._run([None, None])
        self.assertEqual(tags, ['facts', 'facts-json'])
        self.assertTrue(out)  # 규칙 폴백

    def test_json_flag_v6(self):
        tags, _ = self._run([{'facts': [{'turn': 1, 'sec': 'ros', 'key': 'other', 'label': 'x', 'pol': '-'}]}], fmt='json')
        self.assertEqual(tags, ['facts'])


class TestT3LateQuestions(unittest.TestCase):
    def test_collect_only_questions(self):
        led = LEDGER + [
            _say(30, '갑상샘 기능이 높아 보여요.', '치료하면 좋아질까요?', phase='explain'),
            _say(31, '피검사로 확인해요.', '네, 알겠습니다.', phase='explain'),
            _say(32, '바로 오셔야 할 증상 하나를 말씀해 보세요.', '열 나고 목 아프면 바로 오나요?', phase='explain'),
            _say(33, '약은 결과 보고 정해요.', '요즘 밤에 땀도 나요.', phase='explain'),
            _say(34, '치료는 몇 달 걸려요.', '치료 기간은 얼마나 걸리나요', phase='explain-answer'),
            dict(_say(35, '재진은 1주 뒤예요.', '언제 오면 되나요?', phase='explain'), refused=True)]
        enc = FakeEnc(led)
        out = facts.late_questions(enc)
        self.assertEqual([f['turn'] for f in out], [30, 34])
        self.assertTrue(all(f['sec'] == 'ice' and f['key'] == 'other' and f['pol'] == '?' and f['label'] == '설명 중 질문'
                            for f in out))
        self.assertEqual(out[0]['detail'], '치료하면 좋아질까요?')
        # 두 번 붙여도 중복 없음(finish_v2 재호출 대비)
        enc.facts = out
        self.assertEqual(facts.late_questions(enc), [])
        # qa_rows: 기본은 설명 단계 제외, include_late면 질문 행만 포함
        self.assertEqual({r['turn'] for r in facts.qa_rows(enc)}, {1, 2, 3, 4, 5})
        self.assertEqual({r['turn'] for r in facts.qa_rows(enc, include_late=True)}, {1, 2, 3, 4, 5, 30, 34})

    def test_ice_line_in_subjective(self):
        enc = FakeEnc(LEDGER)
        enc.facts = [{'id': 'F1', 'turn': 0, 'sec': 'ice', 'key': 'other', 'label': '걱정', 'pol': '+', 'detail': '암일까 걱정'},
                     {'id': 'F2', 'turn': 30, 'sec': 'ice', 'key': 'other', 'label': '설명 중 질문', 'pol': '?',
                      'detail': '치료하면 좋아질까요?'}]
        s = {'cc_text': '체중 감소', 'onset': '3개월 전', 'pain': '해당 없음',
             'hpi': '32세 여자.\n3개월 전부터 체중 감소 호소.\n암일까 걱정되어 내원함.'}
        with mock.patch.object(note2, 'write_s_narrative', return_value=s):
            out = note2.write_subjective(enc)
        self.assertIn('걱정·궁금증 : 치료하면 좋아질까요?', out['hpi'])
        self.assertNotIn('암일까 걱정;', out['hpi'])  # 앞 8자가 hpi에 있으면 넣지 않음


class TestT11CleanOthers(unittest.TestCase):
    def test_question_mark_and_dups(self):
        t = note2._clean_others('Others : 배변 횟수 (?) 하루 2~3번, 손떨림(+, 글씨 쓸 때), 수면 ( ? )')
        self.assertEqual(t, 'Others : 배변 횟수 : 하루 2~3번, 손떨림(+, 글씨 쓸 때), 수면')
        fh = 'DM / HTN (-/-)\nStroke ( )\nOthers : 모친 갑상샘 저하증 (+), 모친 갑상샘 질환(+, 어머니 갑상샘 저하증)'
        out = note2._clean_others(fh)
        self.assertIn('Others : 모친 갑상샘 질환(+, 어머니 갑상샘 저하증)', out)
        self.assertNotIn('저하증 (+),', out)
        self.assertTrue(out.startswith('DM / HTN (-/-)\nStroke ( )'))

    def test_polarity_and_short_kept(self):
        out = note2._clean_others('Others : 두통(+), 두통(-), 기침(-), 밤 기침(-), 부친 고혈압(+), 모친 고혈압(+)')
        for it in ('두통(+)', '두통(-)', '기침(-)', '밤 기침(-)', '부친 고혈압(+)', '모친 고혈압(+)'):
            self.assertIn(it, out)

    def test_medicine_history_dup(self):
        pmh = ('DM / HTN (-/-)\nMedicine history : 복용 약·보조제 (-)\nAllergy (-)\n'
               'Others : 복용약(-), 영양제(-), 갑상샘 질환(-)')
        out = note2._clean_others(pmh)
        self.assertIn('Others : 갑상샘 질환(-)', out)
        self.assertNotIn('영양제(-)', out)
        pmh2 = 'Medicine history : 레보티록신 50mcg 하루 1번\nOthers : 영양제(-), 복용약(+, 레보티록신)'
        out2 = note2._clean_others(pmh2)
        self.assertIn('영양제(-)', out2)  # 약은 있으나 영양제 부인은 다른 내용 → 보존
        self.assertNotIn('복용약(+', out2)


class TestT12Promote(unittest.TestCase):
    def test_promotion(self):
        enc = FakeEnc(LEDGER + [_say(6, '요즘 어떠세요?', '그냥 기운이 없어요.')])
        enc.facts = [{'id': 'F1', 'turn': 1, 'sec': 'ros', 'key': 'other', 'label': '흉통', 'pol': '-', 'detail': ''},
                     {'id': 'F2', 'turn': 3, 'sec': 'ros', 'key': 'other', 'label': '심한 두통', 'pol': '-', 'detail': ''},
                     {'id': 'F3', 'turn': 6, 'sec': 'ros', 'key': 'other', 'label': '어지럼', 'pol': '+', 'detail': ''},
                     {'id': 'F4', 'turn': 2, 'sec': 'ros', 'key': 'other', 'label': '두근거림', 'pol': '+', 'detail': '가끔'}]
        out = note2.render_fixed(enc, {})
        self.assertIn('Chest pain (-)', out['ros'])
        self.assertIn('Headache ( )', out['ros'])          # 한정어 있는 음성은 승격 안 함
        self.assertIn('심한 두통(-)', out['ros'])
        self.assertIn('Palpitation (+)', out['ros'])       # 턴 2는 단서('두근') 있어 승격
        self.assertIn('두근거림(+, 가끔)', out['ros'])       # 세부는 Others에 보존
        self.assertIn('Dizziness ( )', out['ros'])         # 턴 6 '어지럼(+)'은 그 턴 문답에 단서 없어 승격 안 함
        self.assertIn('어지럼(+)', out['ros'])
        self.assertEqual(enc.facts[0]['key'], 'other')     # enc.facts 원본은 그대로

    def test_hpi_and_unknown_supplement(self):
        enc = FakeEnc(LEDGER)
        enc.facts = [{'id': 'F1', 'turn': 4, 'sec': 'hpi', 'key': 'other', 'label': '배변 횟수', 'pol': '?', 'detail': '하루 2~3번'},
                     {'id': 'F2', 'turn': 2, 'sec': 'hpi', 'key': 'other', 'label': '열감', 'pol': '+', 'detail': ''},
                     {'id': 'F3', 'turn': 5, 'sec': 'pmh', 'key': 'other', 'label': '체중 7kg 감소', 'pol': '?',
                      'detail': '3개월간'},
                     {'id': 'F4', 'turn': 0, 'sec': 'ice', 'key': 'other', 'label': '걱정', 'pol': '+', 'detail': '암 걱정'}]
        out = note2.render_fixed(enc, {'hpi': '3개월간 체중 7kg 감소 호소.'})
        self.assertIn('배변 횟수 : 하루 2~3번', out['ros'])
        self.assertIn('열감(+)', out['ros'])
        self.assertNotIn('체중 7kg 감소', out['pmh'])       # S 전체(HPI)에 있으면 보충 안 함
        self.assertNotIn('암 걱정', out['ros'] + out['pmh'])


class TestT13Objective(unittest.TestCase):
    def _exam(self, reply):
        return {'turn': 23, 'kind': 'EXAM', 'text': '활력징후 측정하겠습니다', 'reply': reply, 'qid': 'vitals', 'system': 'V/S'}

    def test_same_one_line(self):
        enc = FakeEnc([self._exam('혈압 138/72 mmHg, 맥박 102회, 호흡 19회, 체온 36.9도입니다.')])
        o = record.write_objective(enc)
        self.assertEqual(o.split('\n')[0],
                         'V/S : BP 138/72 mmHg, PR 102 회/분, RR 19 회/분, BT 36.9°C (턴 23 측정, 시작 정보와 같음)')
        self.assertNotIn('활력징후 측정', o)

    def test_different_both(self):
        enc = FakeEnc([self._exam('혈압 150/90 mmHg, 맥박 110회.')])
        o = record.write_objective(enc).split('\n')[0]
        self.assertIn('(시작 정보)', o)
        self.assertIn('150/90', o)


class TestVitalsShort(unittest.TestCase):
    def test_short(self):
        enc = FakeEnc()
        self.assertEqual(record.vitals_assessment(enc, short=True), '활력징후 대체로 안정(빈맥 102회/분)')
        self.assertTrue(record.vitals_assessment(enc).startswith('- 활력징후 대체로 안정(빈맥 102회/분) : BP 138/72'))
        enc.vitals = '혈압 : 120/80 mmHg\n맥박 : 80 회/분'
        self.assertEqual(record.vitals_assessment(enc, short=True), '활력징후 대체로 안정')
        enc.vitals = '혈압 : 85/50 mmHg\n맥박 : 140 회/분'
        self.assertEqual(record.vitals_assessment(enc, short=True), '활력징후 불안정(저혈압, 심한 맥박 이상) — 응급 평가 필요')


class TestPolishNote(unittest.TestCase):
    def test_polish(self):
        enc = FakeEnc()
        note = empty_record()
        note['O']['exam'] = 'V/S : BP 138/72 mmHg, PR 102 회/분, RR 19 회/분, BT 36.9°C (턴 23 측정, 시작 정보와 같음)'
        va = record.vitals_assessment(enc)
        note['P']['disposition'] = (va + '\n- 확인된 진찰 소견상 외래 추적이 적절\n- BP 138/72 mmHg, PR 102 회/분')
        note['P']['tests'] = '- 갑상선기능검사(TSH, free T4) : 확인\n- 갑상선기능검사(TSH, free T4) : 확인\n- CBC : 기본'
        note['P']['education'] = '- 같은 줄\n- 같은 줄'
        note['S']['fh'] = 'DM / HTN (-/-)\nOthers : 모친 갑상샘 저하증 (+), 모친 갑상샘 질환(+, 어머니 갑상샘 저하증)'
        note['S']['ros'] = 'Headache ( )\nOthers : 배변 횟수 (?) 하루 2~3번'
        out = record.polish_note(enc, note)
        disp = out['P']['disposition'].split('\n')
        self.assertEqual(disp[0], '- 활력징후 대체로 안정(빈맥 102회/분) → 급성 위험 징후 없어 입원 불필요, 외래 추적')
        self.assertEqual(len(disp), 2)                       # 수치만 있는 줄 삭제
        self.assertNotIn('mmHg', out['P']['disposition'])
        self.assertEqual(out['P']['tests'].count('갑상선기능검사'), 1)
        self.assertEqual(out['P']['education'], '- 같은 줄\n- 같은 줄')  # education은 손대지 않음
        self.assertIn('배변 횟수 : 하루 2~3번', out['S']['ros'])
        self.assertNotIn('저하증 (+)', out['S']['fh'])

    def test_disposition_different_numbers_kept(self):
        enc = FakeEnc()
        note = empty_record()
        note['O']['exam'] = 'V/S : BP 138/72 mmHg (시작 정보)'
        note['P']['disposition'] = '- 재측정 BP 150/95 mmHg면 재평가'
        self.assertEqual(record.polish_note(enc, note)['P']['disposition'], '- 재측정 BP 150/95 mmHg면 재평가')

    def test_submit_calls_polish_after_safety(self):
        enc = FakeEnc()
        order = []
        enc.client = types.SimpleNamespace(diagnose=lambda **k: order.append('diagnose') or {'ok': True})
        with mock.patch.object(record, 'add_safety_lines', side_effect=lambda e, n: order.append('safety') or n), \
                mock.patch.object(record, 'polish_note', side_effect=lambda e, n: order.append('polish') or n):
            record.submit(enc, empty_record(), '진단')
        self.assertEqual(order, ['safety', 'polish', 'diagnose'])


# ================================================================ [B] interview·bank2
class ExamEnc:
    def __init__(self, prof, diffs, cfg=None, vitals=V2_VITALS):
        self.cfg = dict(run.load_config(), **(cfg or {}))
        self.profile = prof
        self.differentials = diffs
        self.vitals = vitals
        self.opening = ''
        self.ledger = []
        self.blacklist = set()
        self.done_exams = []
        self.turns_remaining = 30
        self.client = None
        self.budget = types.SimpleNamespace(can_call=lambda *a, **k: True)
        self.done = []

    def can_act(self):
        return True

    def act(self, kind, text, phase=None, qid=None, **kw):
        self.done.append(qid)
        self.turns_remaining -= 1
        return {'kind': kind, 'text': text, 'reply': '특이 소견(-)', 'phase': phase, 'qid': qid}


def _examine(prof, diffs, llm_ids, cfg=None, vitals=V2_VITALS):
    enc = ExamEnc(prof, diffs, cfg, vitals)
    prompts = []

    def fake(client, budget, sys_prompt, user, **kw):
        prompts.append(sys_prompt)
        return {'exam_ids': list(llm_ids)}
    with mock.patch.object(interview, 'ask_json', side_effect=fake):
        interview.examine(enc)
    return enc.done, prompts


C10_PROF = {'age': 32, 'sex': 'F', 'pediatric': False, 'cc': '체중 감소', 'categories': ['weight_loss']}
C01_PROF = {'age': 62, 'sex': 'F', 'pediatric': False, 'cc': '불면 (수면제 처방 원함)',
            'categories': ['substance', 'insomnia', 'mood']}


class TestT4ExamPlan(unittest.TestCase):
    def _sorted_by_region(self, ids):
        rank = {s: k for k, s in enumerate(record.SECTION_ORDER)}
        keys = [rank.get(banks.EXAM_BY_ID[i][2], 99) for i in ids[2:]]
        self.assertEqual(keys, sorted(keys), ids)

    def test_vitals_first_even_with_opening_vitals(self):
        ids, prompts = _examine(C10_PROF, ['그레이브스병', '당뇨병'], ['heart', 'lung', 'abd_palp'])
        self.assertIn('138/72', V2_VITALS)  # 시작 정보에 활력 수치가 있음
        self.assertEqual(ids[:2], ['vitals', 'general'])
        self.assertEqual(len(ids), 11)
        self.assertNotIn('affect', ids)
        self._sorted_by_region(ids)
        # 설계서 C10 기대: vitals, general, radial, skin_temp, eye_signs, thyroid, thyroid_bruit, …
        self.assertEqual(ids[:7], ['vitals', 'general', 'radial', 'skin_temp', 'eye_signs', 'thyroid', 'thyroid_bruit'])
        self.assertTrue(all(i in banks.EXAM_BY_ID for i in ids))  # 표 행 문구만

    def test_c01_psych_insight_no_affect(self):
        ids, prompts = _examine(C01_PROF, ['수면제 사용장애', '불면장애', '우울장애'], ['affect', 'heart', 'abd_palp'])
        self.assertEqual(ids[:2], ['vitals', 'general'])
        self.assertEqual(len(ids), 11)
        self.assertNotIn('affect', ids)  # LLM이 골라도 EXAM_DENY로 제외
        self.assertIn('insight', ids)
        self.assertIn('orthostatic', ids)
        self._sorted_by_region(ids)
        self.assertIn('정신·수면·약물 관련 증례에서는 복부·하지 진찰보다', prompts[0])
        self.assertNotIn('affect |', prompts[0])  # 메뉴에도 없음

    def test_psych_core_fill_and_mood_bank(self):
        self.assertEqual(bank2.CATEGORY_EXAMS['mood'][:2], ['mental', 'insight'])
        self.assertNotIn('affect', bank2.CATEGORY_EXAMS['mood'])
        self.assertTrue(all(i in banks.EXAM_BY_ID for i in bank2.CORE_FILL_PSYCH))
        # LLM 없이 보충만으로 채우면 정신 범주는 CORE_FILL_PSYCH 순서(심음·폐가 복부보다 앞)
        prof = {'age': 40, 'sex': 'M', 'pediatric': False, 'cc': '우울', 'categories': ['mood']}
        ids, _ = _examine(prof, ['우울장애'], [])
        self.assertEqual(len(ids), 11)
        self.assertIn('heart', ids)
        self.assertIn('lung', ids)
        self.assertNotIn('abd_palp', ids)

    def test_flag_off_restores_v6_vitals_skip(self):
        ids, _ = _examine(C10_PROF, ['그레이브스병'], ['heart', 'lung', 'abd_palp'], cfg={'EXAM_VITALS': 0})
        self.assertNotIn('vitals', ids)
        self.assertEqual(ids[0], 'general')
        ids2, _ = _examine(C10_PROF, ['그레이브스병'], ['heart'], cfg={'EXAM_VITALS': 0}, vitals='')
        self.assertEqual(ids2[0], 'vitals')

    def test_peds_always_vitals_general_anthro(self):
        prof = {'age': 6, 'sex': 'M', 'pediatric': True, 'cc': '저신장', 'categories': ['growth']}
        ids, _ = _examine(prof, ['체질성 성장지연'], ['heart', 'lung', 'abd_palp'])
        self.assertEqual(ids[:3], ['vitals', 'general', 'anthro'])
        self.assertEqual(len(ids), 11)


class TestT5Cover(unittest.TestCase):
    def test_c03_onset_and_weight_covered(self):
        prof = {'age': 6, 'sex': 'M', 'pediatric': True, 'informant': '어머님', 'categories': ['growth']}
        cl = Checklist(prof, test_v2.V2_C03)
        self.assertIn('gr_noticed', cl.covered)
        self.assertIn('gr_weight', cl.covered)
        if 'hpi_onset' in cl.items:
            self.assertIn('hpi_onset', cl.covered)
        self.assertTrue(bank2.cover_hits(test_v2.V2_C03) >= {'hpi_onset', 'gr_noticed', 'gr_weight'})
        self.assertNotIn('gr_noticed', cl.ranked())

    def test_c01_onset_not_covered(self):
        prof = {'age': 62, 'sex': 'F', 'pediatric': False, 'categories': ['substance', 'insomnia']}
        cl = Checklist(prof, V2_C01)
        self.assertNotIn('hpi_onset', cl.covered)
        self.assertNotIn('hpi_onset', bank2.cover_hits(V2_C01))

    def test_c10_course_not_covered(self):
        prof = {'age': 32, 'sex': 'F', 'pediatric': False, 'categories': ['weight_loss', 'fatigue']}
        cl = Checklist(prof, V2_C10)
        self.assertNotIn('hpi_course', cl.covered)
        self.assertIn('ft_weight', cl.covered)  # "칠 키로그람 정도 빠져서"

    def test_setdefault_keeps_existing(self):
        for s in bank2.ONSET_SLOTS:
            self.assertEqual(bank2.COVER_RE[s], bank2.COVER_RE['hpi_onset'])
        self.assertEqual(bank2.COVER_RE['gr_weight'], bank2.WEIGHT_CHANGE_RE)
        self.assertNotIn('hpi_course', bank2.cover_hits('몸무게가 3키로 빠졌어요'))


def _qenc(opening='', replies=(), asked=(), cfg=None):
    led = [{'turn': k + 1, 'kind': 'SAY', 'text': f'q{k}', 'reply': r, 'phase': 'interview'} for k, r in enumerate(replies)]
    return types.SimpleNamespace(opening=opening, ledger=led, asked=list(asked),
                                 cfg=dict(run.load_config(), **(cfg or {})))


class TestT6Valid(unittest.TestCase):
    def setUp(self):
        self.cl = Checklist({'age': 32, 'sex': 'F', 'pediatric': False, 'categories': ['weight_loss']}, '')

    def test_generic_question_once(self):
        enc = _qenc(asked=['다른 불편한 증상은 없으세요?'])
        self.assertFalse(interview._valid(enc, self.cl, 'free', '그 밖에 다른 증상 있나요?'))
        self.assertTrue(interview._valid(_qenc(), self.cl, 'free', '그 밖에 다른 증상 있나요?'))
        self.assertTrue(interview._valid(enc, self.cl, 'free', '손이 떨리세요?'))

    def test_topic_answered_skip(self):
        enc = _qenc(replies=['계단 오르면 숨이 차요.'])
        self.assertEqual(interview.topic_answered(enc, '숨이 차지는 않나요?'), ['dyspnea'])
        self.assertEqual(interview.topic_answered(_qenc(replies=['아니요.']), '숨이 차지는 않나요?'), [])
        self.assertEqual(interview.topic_answered(enc, '숨이 얼마나 차세요?'), [])  # 의문사 질문은 허용
        self.assertEqual(interview.topic_answered(_qenc(opening='살이 많이 빠졌다.'), '체중이 줄었나요?'), ['weight'])
        self.assertEqual(interview.topic_answered(_qenc(replies=['숨이 차요.'], cfg={'TOPIC_GUARD': 0}),
                                                  '숨이 차지는 않나요?'), [])
        # 묻기만 하고 답이 다른 데로 샌 주제는 허용(질문 문구는 판정에 쓰지 않음)
        enc2 = _qenc(replies=['잘 모르겠어요.'])
        enc2.ledger[0]['text'] = '숨이 차지는 않나요?'
        self.assertEqual(interview.topic_answered(enc2, '숨이 찬 적 있나요?'), [])

    def test_run_skips_answered_free_question_keeps_22(self):
        class C(test_v2.V2Client):
            def say(self, content, request_id=None):
                if content.startswith('많이 걱정되셨겠어요.'):
                    self._turn(content)
                    ans = '네, 요즘 계단만 올라도 숨이 차요.'
                    self.events.append(('SAY', content, ans))
                    return {'status': 'OK', 'content': ans, 'turn': self.turns, 'turns_remaining': 50 - self.turns}
                return super().say(content, request_id)

            def answer(self, user):
                if '"covered"' in user:
                    return json.dumps({'covered': [], 'differential': ['그레이브스병'],
                                       'questions': [{'slot': 'free', 'q': '숨이 차지는 않나요?'},
                                                     {'slot': 'free', 'q': '숨이 얼마나 차세요?'}]}, ensure_ascii=False)
                return super().answer(user)
        c = C(V2_C10)
        with mock.patch.dict(os.environ, {'NOVA_AGENT_V2': '1', 'NOVA_AGENT_V3': '0', 'NOVA_AGENT_TURN_PRESET': 'bal44'}):
            state = run.prepare()
        run.consult(c, state)
        says = [e[1] for e in c.events if e[0] == 'SAY']
        self.assertNotIn('숨이 차지는 않나요?', says)  # 첫 답에 '숨이 차요' → 존재형 재질문 건너뜀
        self.assertEqual(run.LAST_RUN['counts']['interview'], 22)  # 빈자리는 은행 다음 순위로 채움
        self.assertLessEqual(c.turns, 44)


# ================================================================ [C] assess·explain·kb
def _enc(dx=GRAVES, vitals=V2_VITALS, done=(), diffs=None, ledger=None, prof=None, opening=V2_C10, **cfg):
    c = run.load_config()
    c.update(cfg)
    return types.SimpleNamespace(
        dx=dx, vitals=vitals, opening=opening, ledger=list(ledger or []), explained=[], facts=[],
        profile=prof or {'age': 32, 'sex': 'F', 'pediatric': False, 'informant': '본인'}, cfg=c,
        done_exams=list(done), assess={'differential': diffs or []}, differentials=[], say_checks=None,
        client=None, budget=types.SimpleNamespace(can_call=lambda *a, **k: True))


def _empty_plan(**kw):
    p = {'tests': [], 'treatment': [], 'disposition': [], 'follow_up': [], 'education': []}
    p.update(kw)
    return p


def _lines(field):
    return [l[2:] for l in field.split('\n') if l.startswith('- ')]


class TestV7cAssess(unittest.TestCase):  # T7 + C1-d + C4-a
    def _dx(self, res, **cfg):
        enc = _enc(**cfg)
        enc.facts = [{'id': 'F1', 'turn': 5, 'sec': 'hpi', 'key': 'other', 'label': '체중 감소', 'pol': '+', 'detail': '7kg'},
                     {'id': 'F2', 'turn': 9, 'sec': 'ros', 'key': 'other', 'label': '갈증', 'pol': '-', 'detail': ''}]
        enc.ledger = [{'turn': 20, 'kind': 'SAY', 'qid': 'ice_disease', 'text': '특히 걱정되는 병이 있으세요?',
                       'reply': '암일까 봐 걱정돼요.', 'phase': 'interview'}]
        enc.differentials = ['그레이브스병']
        seen = {}

        def fake(client, budget, role, user, **kw):
            seen['user'] = user
            return copy.deepcopy(res)
        with mock.patch.object(assess, 'ask_json', side_effect=fake), \
                mock.patch.object(assess.guidelines, 'hint_dx', return_value=''):
            out = assess.dx_and_assess(enc)
        return enc, out, seen['user']

    RES = {'diagnosis_ko': GRAVES, 'diagnosis_en': "Graves' disease", 'confidence': 0.9,
           'evidence': [{'text': '체중 감소 → 대사 항진', 'refs': ['F1']}],
           'differential': [
               {'dx': '당뇨병', 'reason': '지지 체중 감소 / 반대 갈증 없음 → 가능성 낮음', 'refs': ['F1', 'F2'],
                'test': 'HbA1c', 'when': '기본'},
               {'dx': '아급성 갑상샘염', 'reason': '지지 체중 감소 → 가능성 중간', 'refs': ['F1'], 'test': '갑상샘 섭취율',
                'when': 'TRAb 음성·불명확 시'},
               {'dx': '악성 종양(환자 우려)', 'reason': '환자 걱정 → 가능성 낮음', 'refs': [], 'test': 'CBC, 흉부 X선', 'when': '기본'},
               {'dx': '부신기능저하증', 'reason': '근거 없음', 'refs': [], 'test': '코르티솔'},
               {'dx': '불안장애', 'reason': 'x', 'refs': ['F1']}, {'dx': '우울증', 'reason': 'x', 'refs': ['F1']},
               {'dx': '셀리악병', 'reason': 'x', 'refs': ['F1']}]}

    def test_prompt_and_parse(self):
        enc, out, user = self._dx(self.RES)
        self.assertIn("환자 걱정·기대(ICE): ['특히 걱정되는 병이 있으세요? → 암일까 봐 걱정돼요.']", user)
        self.assertIn('후보 3개마다', user)
        self.assertIn('[근거] 4~5개', user)
        self.assertIn('70자 이내', user)
        self.assertIn('(환자 우려)', user)
        self.assertIn('"when"', user)
        names = [d['dx'] for d in out['differential']]
        self.assertNotIn('부신기능저하증', names)          # refs 없는 비우려 감별 제거
        self.assertIn('악성 종양(환자 우려)', names)       # 우려는 refs 없어도 유지
        self.assertEqual(len(names), 5)                    # DX_DIFF_N 기본 5
        self.assertEqual(out['differential'][1]['when'], 'TRAb 음성·불명확 시')
        self.assertTrue(out['differential'][2]['concern'])
        _, out3, _ = self._dx(self.RES, DX_DIFF_N=3)
        self.assertEqual(len(out3['differential']), 3)

    def test_render_assessment_when_and_concern(self):
        enc, out, _ = self._dx(self.RES)
        a = assess.render_assessment(enc, out)['differential']
        self.assertIn('r/o 당뇨병 : 지지 체중 감소 / 반대 갈증 없음 → 가능성 낮음 (턴 5, 9). 감별 검사 : HbA1c', a)
        self.assertNotIn('HbA1c (기본)', a)
        self.assertIn('감별 검사 : 갑상샘 섭취율 (TRAb 음성·불명확 시)', a)
        self.assertIn('r/o 악성 종양(환자 우려) : 환자 걱정 → 가능성 낮음. 감별 검사 : CBC, 흉부 X선', a)
        self.assertNotIn('부신기능저하증', a)


class TestV7cPlanTests(unittest.TestCase):  # T8
    def test_differential_tests_linked(self):
        diffs = [{'dx': '아급성 갑상샘염', 'test': '갑상샘 섭취율', 'when': 'TRAb 음성·불명확 시', 'refs': ['F1']},
                 {'dx': '당뇨병', 'test': 'HbA1c', 'when': '기본', 'refs': ['F1']},
                 {'dx': '외인성 갑상샘호르몬(환자 우려)', 'test': '레보티록신 복용력', 'when': '', 'refs': []}]
        enc = _enc(diffs=diffs)
        plan = _empty_plan(tests=['TSH, free T4 : 갑상샘중독증 확인', '공복혈당/HbA1c : 당뇨 감별'])
        out = explain.render_plan(enc, plan, None)['tests']
        self.assertIn('(조건부) 갑상샘 섭취율 : TRAb 음성·불명확 시 — 아급성 갑상샘염 감별', out)
        self.assertEqual(out.count('HbA1c'), 1)                    # 이미 있으면 추가 안 함
        self.assertIn('갑상샘호르몬제 복용력 : 외인성 갑상샘호르몬 감별', out)  # 성분명 → 계열명, '(환자 우려)' 제거
        self.assertIsNone(DRUG_RE.search(out))
        self.assertNotIn('환자 우려', out)

    def test_cap_and_covered(self):
        diffs = [{'dx': f'질환{i}', 'test': f'검사항목{i}', 'when': '기본'} for i in range(6)]
        plan = _empty_plan(tests=[f'항목{i} : 확인' for i in range(5)])
        out = explain.render_plan(_enc(diffs=diffs), plan, None)['tests']
        self.assertLessEqual(len(_lines(out)), 8)
        self.assertTrue(explain._test_covered('혈액 검사', ['x']))           # 불용어만 → covered
        self.assertTrue(explain._test_covered('trab 확인', ['TRAb : 확진']))  # 영문 대소문자 무시
        self.assertFalse(explain._test_covered('갑상샘 초음파', ['TSH : x']))

    def test_urine_not_duplicated(self):  # C01 시뮬 '소변검사 : 진료 중 설명한 검사' 중복
        enc = _enc(dx=SED, prof={'age': 62, 'sex': 'F'})
        enc.explained = ['피검사, 소변 약물검사, 심전도를 할게요.']
        plan = _empty_plan(tests=['소변 약물 선별검사 : 타 진정제 병용 확인', '심전도 : 확인'])
        out = explain.render_plan(enc, plan, kb.match_kb(SED))['tests']
        self.assertNotIn('진료 중 설명한 검사', out)


class TestV7cFollowUp(unittest.TestCase):  # T9
    def test_types_order_refer(self):
        k = kb.match_kb(GRAVES)
        plan = _empty_plan(follow_up=['재진 : 1~2주 후', '1~2주 후 결과 확인 후 항갑상샘제 시작 여부 결정',
                                      '치료 시작 후 4~6주 간격 TFT·CBC', '즉시 내원 : 고열·인후통·황달·숨참'])
        fu = _lines(explain.render_plan(_enc(), plan, k)['follow_up'])
        types_ = [explain._fu_type(l) for l in fu]
        self.assertEqual(types_.count('재진'), 1)
        self.assertIn('1~2주 후 결과 확인 후 항갑상샘제 시작 여부 결정', fu[0])   # 더 긴 줄
        self.assertTrue(fu[0].startswith('재진 : '))
        self.assertEqual(types_, ['재진', '모니터링', '의뢰 기준', '즉시 내원'])
        self.assertTrue(fu[1].startswith('모니터링 : '))
        self.assertEqual(fu[2], '의뢰 기준 : ' + k['refer_if'])

    def test_generic_refer_and_flag(self):
        plan = _empty_plan(disposition=['내분비내과 외래 연계'], follow_up=['2주 후 재진'])
        fu = explain.render_plan(_enc(dx='원인 미상 질환'), plan, None)['follow_up']
        self.assertIn('의뢰 기준 : 검사 이상·증상 악화·치료 반응 부족 시 내분비내과 의뢰', fu)
        plan = _empty_plan(follow_up=['2주 후 재진'])
        fu = explain.render_plan(_enc(dx='원인 미상 질환'), plan, None)['follow_up']
        self.assertIn('해당 전문과 의뢰', fu)
        fu0 = explain.render_plan(_enc(dx='원인 미상 질환', FU_REFER=0), plan, None)['follow_up']
        self.assertNotIn('의뢰 기준', fu0)
        # 기존 LLM 의뢰 줄이 있으면 덧붙이지 않음
        plan = _empty_plan(follow_up=['2주 후 재진', '검사 이상 시 내분비내과 의뢰'])
        fu = explain.render_plan(_enc(dx='원인 미상 질환'), plan, None)['follow_up']
        self.assertEqual(sum('의뢰' in l for l in _lines(fu)), 1)
        self.assertIn('의뢰 기준 : 검사 이상 시 내분비내과 의뢰', fu)

    def test_sedative_early_contact_kept(self):
        k = kb.match_kb(SED)
        plan = _empty_plan(follow_up=['재진 : 1~2주 후', '금단 증상 시 재진 전 조기 연락'])
        fu = _lines(explain.render_plan(_enc(dx=SED), plan, k)['follow_up'])
        self.assertEqual(sum('조기 연락' in l for l in fu), 1)
        t = [explain._fu_type(l) for l in fu]
        self.assertLess(t.index('조기 연락'), t.index('즉시 내원'))
        self.assertIn('의뢰 기준', t)


class TestV7cDisposition(unittest.TestCase):  # T10
    def test_graves_first_line(self):
        out = explain.render_plan(_enc(), _empty_plan(), kb.match_kb(GRAVES))
        d = _lines(out['disposition'])
        self.assertTrue(d[0].startswith('활력징후 대체로 안정(빈맥 102회/분), 확인된 진찰 소견상 갑상샘중독발증 징후 없어 '
                                        '현재 외래 추적이 적절'), d[0])
        self.assertNotIn('mmHg', out['disposition'])       # 활력 수치는 O칸에만
        self.assertNotIn('138/72', out['disposition'])
        self.assertEqual(sum('활력징후 대체로 안정' in l for l in d), 1)
        assert_safe_plan(self, {'P': out})

    def test_sedative_mental_and_safety_lines(self):
        k = kb.match_kb(SED)
        led = [{'kind': 'SAY', 'qid': 'sb_last', 'text': '마지막으로 언제 드셨어요?', 'reply': '어젯밤 자기 전에 네 알을 먹었어요.',
                'turn': 11, 'phase': 'interview'},
               {'kind': 'SAY', 'qid': 'sb_seizure', 'text': '약을 끊었을 때 경련한 적 있나요?', 'reply': '그런 건 없어요.',
                'turn': 14, 'phase': 'interview'}]
        enc = _enc(dx=SED, ledger=led, prof={'age': 62, 'sex': 'F'}, opening=V2_C01,
                   vitals='혈압 : 128/78 mmHg\n맥박 : 76 회/분\n호흡 : 16 회/분\n체온 : 36.5°C')
        out = explain.render_plan(enc, _empty_plan(), k)
        self.assertNotIn('의식 명료', out['disposition'])   # mental 미시행
        d = _lines(out['disposition'])
        self.assertEqual(d[0], '활력징후 대체로 안정')
        line = next(l for l in d if '외래 추적이 적절' in l)
        self.assertTrue(line.startswith(explain.SOFT_PREFIX), line)
        assert_safe_plan(self, {'P': out})
        # add_safety_lines가 '외래 추적이 적절' 줄을 찾아 앞에 붙임(C01 원장 재현)
        enc.kb = k
        note = {'S': {'hpi': '62세 여성.', 'ros': ''}, 'P': dict(out)}
        n = record.add_safety_lines(enc, note)
        dl = n['P']['disposition'].split('\n')
        hit = next(l for l in dl if '외래 추적이 적절' in l)
        self.assertTrue(hit.startswith('- 금단 경련·섬망 병력 없음, 마지막 복용 어젯밤 자기 전에 네 알을 먹었어요 → '), hit)
        self.assertEqual(len(dl), len(d))
        # mental 진찰을 했으면 유지
        enc2 = _enc(dx=SED, done=['mental'], prof={'age': 62, 'sex': 'F'})
        self.assertIn('의식 명료', explain.render_plan(enc2, _empty_plan(), k)['disposition'])

    def test_soften_and_admit_line(self):
        enc = _enc(dx='원인 미상 질환', vitals='혈압 : 120/80 mmHg\n맥박 : 80 회/분')
        plan = _empty_plan(disposition=['활력징후 안정(BP 120/80 mmHg)', '의식 명료, 급성 위험 징후 없어 외래 추적'])
        out = explain.render_plan(enc, plan, None)
        d = _lines(out['disposition'])
        self.assertEqual(d[0], '활력징후 대체로 안정')
        self.assertNotIn('120/80', out['disposition'])
        self.assertNotIn('의식 명료', out['disposition'])
        self.assertIn(explain.SOFT_PREFIX + '급성 위험 징후 없어 외래 추적', out['disposition'])
        self.assertIn('현재 외래 추적이 적절하며 활력징후 불안정·증상 급격한 악화 시 입원 고려', out['disposition'])
        self.assertNotIn('불필요', out['disposition'])
        assert_safe_plan(self, {'P': out})

    def test_unstable_keeps_v6_line(self):
        enc = _enc(vitals='혈압 : 82/50 mmHg\n맥박 : 140 회/분\n호흡 : 30 회/분\n체온 : 39.8°C')
        d = _lines(explain.render_plan(enc, _empty_plan(), kb.match_kb(GRAVES))['disposition'])
        self.assertTrue(d[0].startswith('활력징후 불안정'), d[0])
        self.assertIn('mmHg', d[0])
        self.assertIn('입원·응급 평가 필요', d[0])

    def test_vitals_short_missing_fallback(self):  # 담당 A 인터페이스가 없을 때(TypeError) 방어
        def old_va(enc):
            return '- 활력징후 대체로 안정(빈맥 102회/분) : BP 138/72 mmHg → 급성 위험 징후 없어 입원 불필요, 외래 추적'
        d = explain.decide_disposition(_enc(), ['외래 추적'], '', old_va)
        self.assertEqual(d[0], '활력징후 대체로 안정(빈맥 102회/분)')


class TestV7cFixSay(unittest.TestCase):  # T14
    def _check(self, out, n):
        self.assertLessEqual(len(out), n)
        self.assertEqual(out[-1], saymod.QUESTION_LINE)
        for s in out[:-1]:
            self.assertEqual(saymod.say_problem(s), '', s)
            self.assertLessEqual(nlen(s), 30, s)
            self.assertIsNone(explain.SAY_BAD_RE.search(s), s)
            self.assertIsNone(DRUG_RE.search(s), s)

    def test_no_llm_and_slot_dedup(self):
        k = kb.match_kb(SED)
        enc = _enc(dx=SED)
        say = ['수면제 의존이 생긴 상태로 보여요.', '약에 몸이 익숙해져 양이 늘었어요.', '급히 끊지 말고 천천히 줄여요.',
               '혼자 끊지 말고 서서히 줄여 가요.', '피검사와 소변 약물검사를 할게요.', '심전도 검사도 같이 할게요.',
               '감량 중 경련·혼동·환각이 오면 바로 오세요.', '1~2주 뒤 오셔서 양을 같이 조정해요.',
               'This sentence is english and too long for the rule check.']
        with mock.patch.object(explain, 'ask_json') as m:
            out = explain.fix_say(enc, list(say), k)
        self.assertEqual(m.call_count, 0)                 # SAY_FIX_LLM=0 → LLM 0회
        self._check(out, enc.cfg['EXPLAIN_N'])
        taper = [s for s in out if explain._slot(s) == 'taper']
        self.assertEqual(taper, ['오늘 바로 끊지 않고 천천히 줄여요.'])   # 감량 2문장 → must_say 1
        self.assertEqual(sum(explain._slot(s) == 'test' for s in out), 1)
        self.assertEqual(sum(explain._slot(s) == 'warn' for s in out), 1)

    def test_flag_on_calls_llm(self):
        k = kb.match_kb(GRAVES)
        enc = _enc(SAY_FIX_LLM=1)
        say = ['그레이브스병 같아요.', '면역 이상으로 갑상선이 과하게 일해요.', '피검사로 호르몬을 확인해요.',
               '숨참·불규칙한 맥·고열·혼동 시 바로 오세요.', '1~2주 뒤 결과 보러 다시 오세요.', 'english sentence here']
        with mock.patch.object(explain, 'ask_json', return_value={'say': ['약은 결과 보고 정해요.']}) as m:
            out = explain.fix_say(enc, list(say), k)
        self.assertEqual(m.call_count, 1)
        self.assertIn('약은 결과 보고 정해요.', out)

    def test_kb_fill_limit(self):
        k = kb.match_kb(GRAVES)
        enc = _enc()
        n = enc.cfg['EXPLAIN_N']
        with mock.patch.object(explain, 'ask_json') as m:
            out = explain.fix_say(enc, ['그레이브스병에 의한 갑상샘항진증 가능성이 높아요.', '너무길어서규칙에어긋나는문장입니다아아아아요.'], k)
        self.assertEqual(m.call_count, 0)                 # KB로 채워져 안전망 불필요
        self._check(out, n)
        self.assertIn(explain.TEACH_BACK, out)
        self.assertIn('두근거림 약 전에 천식·심장병 있으면 알려 주세요.', out)
        self.assertTrue(any(c.get('kb_fill') for c in enc.say_checks if isinstance(c, dict)))
        body = [s for s in out if s not in (explain.TEACH_BACK, saymod.QUESTION_LINE)]
        self.assertLessEqual(len(body), n - 2)
        self.assertEqual(len({explain._slot(s) for s in body if explain._slot(s)}),
                         len([s for s in body if explain._slot(s)]))  # 슬롯 중복 없음

    def test_safety_net_llm_once(self):
        enc = _enc(dx='원인 미상 질환')
        say = ['bad english one here', 'another english sentence', '세번째문장도띄어쓰기가전혀없어서실패해요.']
        fixed = {'say': ['원인을 찾으려고 피검사를 해요.', '숨참·흉통·고열·혼동 시 바로 오세요.', '1~2주 뒤 결과 보러 다시 오세요.']}
        with mock.patch.object(explain, 'ask_json', return_value=fixed) as m:
            out = explain.fix_say(enc, list(say), None)
        self.assertEqual(m.call_count, 1)
        self.assertIn('원인을 찾으려고 피검사를 해요.', out)
        self._check(out, enc.cfg['EXPLAIN_N'])


class TestV7cExplainLoop(unittest.TestCase):  # T15
    def test_final_question_answered(self):
        sent = []
        replies = {0: '큰 병인가요?', 1: '약은 얼마나 오래 먹어요?', 8: '계속 먹으면 해로울까요?'}

        class E:
            cfg = {'ANSWER_MAX': 2, 'EFFORT_ANSWER': 'low', 'CALL_RESERVE': 0}
            explained = []
            turns_remaining = 30
            plan_v2 = {}
            dx = GRAVES
            client = budget = None

            def can_act(self):
                return True

            def act(self, kind, text, phase=''):
                sent.append((phase, text))
                self.turns_remaining -= 1
                i = sum(1 for p, _ in sent if p == 'explain') - 1
                return {'reply': replies.get(i, '네.') if phase == 'explain' else '네.'}
        lines = ['그레이브스병 가능성이 높아요.', '면역 이상으로 갑상선이 과하게 일해요.', '목이 붓고 눈이 나와 갑상선 병이에요.',
                 '피검사로 호르몬과 항체를 확인해요.', '약 먹다 열·목 아프면 멈추고 바로 연락하세요.',
                 '숨참·불규칙한 맥·고열·혼동 시 바로 오세요.', explain.TEACH_BACK, '1~2주 뒤 결과 보러 다시 오세요.',
                 saymod.QUESTION_LINE]
        faq = {'serious': '흔한 병이고 약으로 잘 조절돼요.', 'duration': '약은 보통 1~2년 정도 드셔요.'}
        with mock.patch.object(explain, 'ask', return_value=None):
            explain.explain_loop(E(), lines, faq)
        answers = [t for p, t in sent if p == 'explain-answer']
        self.assertEqual(answers[0], faq['serious'])            # 첫 중간 질문
        self.assertNotIn(faq['duration'], answers)              # 둘째 중간 질문은 마지막 몫을 남기려 건너뜀
        self.assertEqual(sent[-1][0], 'explain-answer')         # 마지막 질문에 답
        self.assertEqual(sent[-1][1], explain.TOPIC_FALLBACK['serious'])
        self.assertLessEqual(len(sent), 9 + 2)                  # EXPLAIN_N + ANSWER_MAX

    def test_no_answer_when_turns_short(self):
        sent = []

        class E:
            cfg = {'ANSWER_MAX': 2}
            explained = []
            turns_remaining = 2

            def can_act(self):
                return True

            def act(self, kind, text, phase=''):
                sent.append(phase)
                self.turns_remaining -= 1
                return {'reply': '큰 병인가요?'}
        explain.explain_loop(E(), ['갑상선 병이에요.', '피검사를 해요.', saymod.QUESTION_LINE], {'serious': '흔한 병이에요.'})
        self.assertEqual(sent[:2], ['explain', 'explain'])


class TestV7cFaq(unittest.TestCase):  # T16
    def test_faq_keys_and_fallback(self):
        self.assertEqual(explain._faq_key('계속 먹으면 해로울까요?'), 'serious')
        self.assertEqual(explain._faq_key('몸에 해롭지 않나요?'), 'serious')
        for key, s in explain.TOPIC_FALLBACK.items():
            self.assertEqual(saymod.say_problem(s), '', s)
            self.assertEqual(explain.safe_say(s), s, s)     # 안전 필터가 바꾸지 않음
            self.assertLessEqual(nlen(s), 30)


class TestV7cPlanSayPrompt(unittest.TestCase):  # T17
    def _prompt(self, dx, prof=None, k_override=None):
        enc = _enc(dx=dx, prof=prof)
        enc.assess = {'differential': [], 'exams': []}
        enc.differentials = []
        seen = {}

        def fake(client, budget, role, user, **kw):
            seen['user'] = user
            return {'say': ['그레이브스병 가능성이 높아요.', '피검사로 호르몬을 확인해요.', '1~2주 뒤 결과 보러 다시 오세요.'],
                    'tests': [], 'treatment': [], 'disposition': [], 'follow_up': [], 'education': []}
        with contextlib.ExitStack() as st:
            st.enter_context(mock.patch.object(explain, 'ask_json', side_effect=fake))
            st.enter_context(mock.patch.object(explain.guidelines, 'hint_plan', return_value=''))
            if k_override is not None:
                st.enter_context(mock.patch.object(explain.kbmod, 'match_kb', return_value=k_override))
            out = explain.plan_and_say(enc)
        return seen['user'], out

    def test_kb_treatment_empty_and_faq_keys(self):
        user, out = self._prompt(GRAVES)
        self.assertIn('- treatment: [] (약물 치료는 지식표가 정함)', user)
        self.assertIn('(조건부)', user)
        self.assertIn('의뢰 기준 : 어떤 결과·증상이면 어느 진료과', user)
        self.assertIn('[FAQ]', user)
        faq_part = user.split('[FAQ]')[1]
        self.assertIn('treatment(', faq_part)
        for kk in ('prognosis(', 'serious(', 'duration(', 'lifestyle(', 'prescribe(', 'tests(', 'results('):
            self.assertNotIn(kk, faq_part)                  # KB faq에 있는 키·요청 없는 prescribe 제외
        self.assertIn('22자 이내', faq_part)
        self.assertIn('"faq": {"treatment": "..."}', user)
        self.assertEqual(out['faq']['serious'], kb.match_kb(GRAVES)['faq']['serious'])

    def test_no_kb_keeps_v6_treatment_and_prescribe(self):
        user, _ = self._prompt('원인 미상 질환', prof={'age': 62, 'sex': 'F', 'request': '수면제 처방'})
        self.assertIn("- treatment: 조건부('검사 확인 후 ~ 시작 고려'", user)
        self.assertIn('prescribe(', user.split('[FAQ]')[1])

    def test_no_faq_keys_drops_faq(self):
        k = copy.deepcopy(kb.match_kb(GRAVES))
        k['faq'] = {x: '치료하면 대부분 좋아져요.' for x in explain.FAQ_ASK}
        user, _ = self._prompt(GRAVES, k_override=k)
        self.assertNotIn('[FAQ]', user)
        self.assertNotIn('"faq"', user)


class TestV7cKbRefer(unittest.TestCase):  # C4-e + 안전 grep
    def test_all_kb_have_refer_if(self):
        self.assertGreaterEqual(len(kb.KB), 21)
        for k in kb.KB:
            r = k.get('refer_if')
            self.assertTrue(r and r.strip(), k['id'])
            self.assertTrue(re.search(r'(과|입원|소아내분비|수면클리닉)', r), (k['id'], r))
            self.assertIsNone(DRUG_RE.search(r), (k['id'], r))
            self.assertIsNone(DOSE_RE.search(r), (k['id'], r))
            line = explain.safe_plan_line(f'의뢰 기준 : {r}', 'follow_up', k.get('admit_if', ''))
            self.assertIsNone(P_BANNED_RE.search(line), (k['id'], line))
            self.assertEqual(explain._fu_type(line), '의뢰 기준')

    def test_render_plan_all_kb_safe(self):
        diffs = [{'dx': '외인성 갑상샘호르몬', 'test': '레보티록신 복용력', 'when': '기본'},
                 {'dx': '약물 유발', 'test': '졸피뎀 혈중농도', 'when': '복용력 불명확 시'}]
        for k in kb.KB:
            enc = _enc(dx=k['name'][0], diffs=diffs)
            plan = _empty_plan(tests=['메티마졸 반응 : 확인'], follow_up=['재진 : 1~2주 후', '프로프라놀롤 10mg 하루 3회 투여 후 재평가'],
                               disposition=['급성 위험 징후 없어 입원 불필요'])
            out = explain.render_plan(enc, plan, k)
            assert_safe_plan(self, {'P': out})
            self.assertIsNone(DRUG_RE.search(out['tests']), (k['id'], out['tests']))
            self.assertIsNone(DRUG_RE.search(out['follow_up']), (k['id'], out['follow_up']))
            self.assertIn('의뢰 기준 : ', out['follow_up'])
            self.assertIn('즉시 내원', out['follow_up'])
            self.assertTrue(re.search(r'입원.{0,6}(필요|고려)', out['disposition']), (k['id'], out['disposition']))


# ================================================================ [D] 드라이런·설정
# 실측(2026-10-14, test_v2 가짜 서버, TURN_PRESET bal44, 별도 프로세스):
#   v6·v7 모두 C01·C03·C10 = 43턴 [first 1 + interview 19 + ice 2 (=문진 22) + 진찰 11 + explain 9 + explain-answer 1]
#   → v7 턴 구조는 v6과 동일(차이 0). 진찰 목록만 바뀜(활력징후 첫째·affect 제외, C2).
class TestT18DrySafety(unittest.TestCase):
    """T18: C01·C10 드라이런 P(전 칸)·SAY에 용량·성분명·처방 확정 표현 0.
    패턴은 TestV2cSafety의 P_BANNED_RE·assert_safe_plan(test_v2)과 test_v5의 DOSE_RE·DRUG_RE·COMMIT_RE를 재사용하고,
    explain._DRUG_ANY(DRUG_CLASS 전체 성분명)·DOSE_RE(하루 n회 포함)를 더한다."""
    CASES = ('V2_C01', 'V2_C10')
    # '임의 증량·급감량 없이'(KB 금지 지시)는 처방 확정이 아님 → COMMIT_RE 검사 전에 지운다(실측 C01 treatment 마지막 줄)
    NEG_RE = re.compile(r'임의\s*증량')
    BAN = (P_BANNED_RE, test_v5.DOSE_RE, test_v5.DRUG_RE, DRUG_RE, DOSE_RE)

    def test_p_all_fields_clean(self):
        for k in self.CASES:
            P = _dry(V7, k)['P']
            self.assertEqual(set(P), {'tests', 'treatment', 'disposition', 'follow_up', 'education'}, k)
            for f, v in P.items():
                for l in v.split('\n'):
                    for rx in self.BAN:
                        self.assertIsNone(rx.search(l), (k, f, l))
                    self.assertIsNone(test_v5.COMMIT_RE.search(self.NEG_RE.sub('', l)), (k, f, l))
            assert_safe_plan(self, {'P': P})

    def test_say_clean(self):
        for k in self.CASES:
            says = _dry(V7, k)['say']
            self.assertTrue(says, k)
            for s in says:
                for rx in self.BAN + (test_v5.COMMIT_RE, explain.SAY_BAD_RE):
                    self.assertIsNone(rx.search(s), (k, s))
                self.assertLessEqual(nlen(s), 30, s)


class TestT19DryRun(unittest.TestCase):
    CASES = ('V2_C01', 'V2_C03', 'V2_C10')

    @classmethod
    def setUpClass(cls):
        cls.r = {k: _dry(V7, k) for k in cls.CASES}
        cls.v6 = {k: _dry(V6, k) for k in cls.CASES} if os.path.isdir(V6) else {}

    def test_counts(self):
        for k, r in self.r.items():
            self.assertEqual(r['counts']['interview'], 22, k)
            self.assertEqual(r['counts']['exam'], 11, k)
            self.assertEqual(r['counts']['refused'], 0, k)
            self.assertEqual(r['counts']['exam_refused'], 0, k)
            self.assertLessEqual(r['turns'], 44, k)
            self.assertGreaterEqual(r['turns'], 42, k)
            self.assertLessEqual(_explain_turns(r), 11, k)  # 설명(+답) ≤ EXPLAIN_N + ANSWER_MAX
            if self.v6:
                self.assertLessEqual(abs(r['turns'] - self.v6[k]['turns']), 1, k)

    def test_exams_vitals_no_affect(self):
        for k, r in self.r.items():
            self.assertEqual(r['exam'][0], banks.EXAM_BY_ID['vitals'][1], k)
            self.assertEqual(r['exam'][1], banks.EXAM_BY_ID['general'][1], k)
            self.assertNotIn(banks.EXAM_BY_ID['affect'][1], r['exam'], k)
            names = {e[1] for e in banks.EXAM_BANK}
            self.assertTrue(all(x in names for x in r['exam']), k)  # 표 행 이름만
        self.assertIn(banks.EXAM_BY_ID['orthostatic'][1], self.r['V2_C01']['exam'])

    def test_c03_no_onset_requestion(self):
        says = self.r['V2_C03']['say']
        self.assertFalse(any('언제부터 작다는 말을' in s for s in says))
        self.assertFalse(any('살이 빠지거나 찌진' in s for s in says))


class TestC7PresetDryRun(unittest.TestCase):
    """C7 실험 프리셋 3종 C01 드라이런. 별도 프로세스에서 run.PRESET_FILE만 tools/presets/*.json으로 바꿔
    preset.json 경로 자체를 시험한다(code_v7/preset.json은 만들지 않음).
    실측(2026-10-14, C01):
      기본    43턴 = 문진 22 + 진찰 11 + 설명 9 + 답 1 (설명 계 10)
      v7-lean 38턴 = 문진 22 + 진찰  9 + 설명 6 + 답 1 (설명 계 7 ≤ EXPLAIN_N 7 + ANSWER_MAX 1)
      v7-wide 46턴 = 문진 22 + 진찰 14 + 설명 9 + 답 1 (설명 계 10)
    """
    PDIR = os.path.join(V7, 'tools', 'presets')

    def _run(self, name):
        return _dry(V7, 'V2_C01', os.path.join(self.PDIR, name) if name else None)

    def _common(self, r):
        self.assertEqual(r['counts']['interview'], 22)
        self.assertEqual(r['counts']['refused'], 0)
        self.assertEqual(r['exam'][0], banks.EXAM_BY_ID['vitals'][1])

    def test_default(self):
        r = self._run(None)
        self._common(r)
        self.assertEqual(r['counts']['exam'], 11)
        self.assertTrue(42 <= r['turns'] <= 44, r['turns'])
        self.assertLessEqual(_explain_turns(r), 9 + 2)

    def test_lean(self):
        r = self._run('v7-lean.json')
        self._common(r)
        self.assertEqual(r['counts']['exam'], 9)
        self.assertTrue(36 <= r['turns'] <= 39, r['turns'])
        self.assertLessEqual(_explain_turns(r), 7 + 1)  # EXPLAIN_N 7 + ANSWER_MAX 1
        self.assertLessEqual(r['phases'].get('explain-answer', 0), 1)

    def test_wide(self):
        r = self._run('v7-wide.json')
        self._common(r)
        self.assertEqual(r['counts']['exam'], 14)
        self.assertTrue(45 <= r['turns'] <= 48, r['turns'])
        self.assertLessEqual(r['turns'], 50)
        self.assertLessEqual(_explain_turns(r), 9 + 2)

    def test_no_preset_json_left_in_root(self):
        self._run('v7-lean.json')
        self.assertEqual(run.PRESET_FILE, os.path.join(V7, 'preset.json'))
        self.assertFalse(os.path.exists(run.PRESET_FILE), 'code_v7/preset.json이 남아 있음(기본 zip에는 넣지 않음)')


class TestT20Preset(unittest.TestCase):
    """T20: run.load_config(preset_path) — DEFAULTS → preset.json → NOVA_AGENT_* → TURN_PRESET(explicit 제외)."""
    BASE = dict(run.DEFAULTS, **run.PRESETS['bal44'])

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        clean = {k: v for k, v in os.environ.items() if not k.startswith('NOVA_AGENT_')}
        p = mock.patch.dict(os.environ, clean, clear=True)
        p.start()
        self.addCleanup(p.stop)

    def _file(self, data=None, raw=None):
        path = os.path.join(self.tmp, 'preset.json')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(raw if raw is not None else json.dumps(data))
        return path

    def test_missing_file_is_defaults(self):
        path = os.path.join(self.tmp, 'none.json')
        self.assertEqual(run.load_preset(path), {})
        self.assertEqual(run.load_config(path), self.BASE)

    def test_override_and_coerce(self):
        path = self._file({'EXAM_N': '9', 'EXPLAIN_N': 7.0, 'SAY_FIX_LLM': '1', 'ANSWER_MAX': 1,
                           'EXAM_DENY': 'affect,heart', 'FACTS_FORMAT': 'json'})
        cfg = run.load_config(path)
        self.assertEqual(cfg['EXAM_N'], 9)
        self.assertIsInstance(cfg['EXAM_N'], int)
        self.assertEqual(cfg['EXPLAIN_N'], 7)
        self.assertIsInstance(cfg['EXPLAIN_N'], int)
        self.assertEqual(cfg['SAY_FIX_LLM'], 1)       # '1' → 1
        self.assertIsInstance(cfg['SAY_FIX_LLM'], int)
        self.assertEqual(cfg['ANSWER_MAX'], 1)
        self.assertEqual(cfg['EXAM_DENY'], 'affect,heart')
        self.assertEqual(cfg['FACTS_FORMAT'], 'json')
        self.assertEqual(cfg['INTERVIEW_Q'], 22)      # 준 적 없는 키는 TURN_PRESET(bal44)

    def test_explicit_not_overridden_by_turn_preset(self):
        path = self._file({'EXAM_N': 9})
        os.environ['NOVA_AGENT_TURN_PRESET'] = 'bal44'  # bal44 EXAM_N 11이 preset 9를 덮지 않아야 함
        cfg = run.load_config(path)
        self.assertEqual(cfg['EXAM_N'], 9)
        self.assertEqual(cfg['INTERVIEW_Q'], 22)
        self.assertEqual(cfg['EXPLAIN_N'], 9)
        # preset 안의 TURN_PRESET도 적용되며, 같은 파일의 명시 키는 지킨다
        del os.environ['NOVA_AGENT_TURN_PRESET']
        cfg2 = run.load_config(self._file({'TURN_PRESET': 'lean38', 'EXAM_N': 9}))
        self.assertEqual(cfg2['TURN_PRESET'], 'lean38')
        self.assertEqual(cfg2['INTERVIEW_Q'], 18)
        self.assertEqual(cfg2['EXPLAIN_N'], 8)
        self.assertEqual(cfg2['EXAM_N'], 9)

    def test_unknown_and_bad_values_ignored(self):
        path = self._file({'FOO': 1, 'exam_n': 3, 'EXAM_N': 'abc', 'DX_DIFF_N': None, 'EXPLAIN_N': [1]})
        self.assertEqual(run.load_preset(path), {})
        cfg = run.load_config(path)
        self.assertNotIn('FOO', cfg)
        self.assertNotIn('exam_n', cfg)
        self.assertEqual(cfg, self.BASE)

    def test_broken_json_ignored(self):
        for raw in ('{"EXAM_N": 9,', '[1, 2]', '', '"x"'):
            path = self._file(raw=raw)
            self.assertEqual(run.load_preset(path), {}, raw)
            self.assertEqual(run.load_config(path), self.BASE, raw)

    def test_env_beats_preset(self):
        path = self._file({'EXAM_N': 9, 'FACTS_FORMAT': 'json'})
        os.environ['NOVA_AGENT_EXAM_N'] = '12'
        cfg = run.load_config(path)
        self.assertEqual(cfg['EXAM_N'], 12)
        self.assertEqual(cfg['FACTS_FORMAT'], 'json')
        os.environ['NOVA_AGENT_EXAM_N'] = 'x'         # 변환 실패 환경변수는 무시 → preset 값 유지(explicit)
        self.assertEqual(run.load_config(path)['EXAM_N'], 9)

    def test_default_path_is_preset_file(self):
        path = self._file({'EXAM_N': 14})
        with mock.patch.object(run, 'PRESET_FILE', path):
            self.assertEqual(run.load_config()['EXAM_N'], 14)
            os.environ['NOVA_AGENT_TURN_PRESET'] = 'bal44'
            os.environ['NOVA_AGENT_GUIDE'] = '0'       # 지침 인덱스 없이 prepare만 확인
            self.assertEqual(run.prepare()['config']['EXAM_N'], 14)  # 서버 경로(prepare)도 preset.json을 읽음

    def test_shipped_presets(self):
        pdir = os.path.join(V7, 'tools', 'presets')
        self.assertEqual(run.load_preset(os.path.join(pdir, 'v7-lean.json')), {'EXAM_N': 9, 'EXPLAIN_N': 7, 'ANSWER_MAX': 1})
        self.assertEqual(run.load_preset(os.path.join(pdir, 'v7-wide.json')), {'EXAM_N': 14})
        self.assertEqual(run.load_config(os.path.join(pdir, 'v7-lean.json'))['INTERVIEW_Q'], 22)

    def test_v7_defaults_keys(self):  # C7 DEFAULTS 추가 키
        want = {'EXAM_VITALS': 1, 'EXAM_DENY': 'affect', 'FACTS_FORMAT': 'compact', 'SAY_FIX_LLM': 0,
                'LATE_Q_FACTS': 1, 'FU_REFER': 1, 'DX_DIFF_N': 5, 'DX_ESCALATE': 0, 'TOPIC_GUARD': 1}
        for k, v in want.items():
            self.assertEqual(run.DEFAULTS[k], v, k)


# ================================================================ v7 긴급 수정(감별 검사 필터·KB 의뢰 우선·응급 승격)
S01_VITALS = '혈압 : 124/76 mmHg\n맥박 : 98 회/분\n호흡 : 18 회/분\n체온 : 37.9°C'
S01_LEDGER = [{'kind': 'EXAM', 'text': '복부 촉진하겠습니다', 'reply': '우하복부 압통(+), 근성방어(+) 우하복부 국한, 강직(-)'},
              {'kind': 'EXAM', 'text': '반발통 확인하겠습니다', 'reply': '우하복부 반발압통(+)'},
              {'kind': 'EXAM', 'text': '머피 징후 확인하겠습니다', 'reply': '머피 징후(-)'}]
C10_LEDGER = [{'kind': 'EXAM', 'text': '갑상선 촉진하겠습니다', 'reply': '미만성 비대(+), 결절(-), 압통(-)'},
              {'kind': 'EXAM', 'text': '복부 촉진하겠습니다', 'reply': '압통(-), 종괴(-), 근성방어·강직(-)'}]


class TestV7Hotfix(unittest.TestCase):
    def test_diff_tests_filter(self):
        diffs = [{'dx': '부신피로증후군', 'test': 'ACTH, cortisol 연속', 'when': 'TRAb 음성·불명확 시', 'refs': ['F1']},
                 {'dx': '위장관 질환', 'test': '대변 검사, 위장 내시경', 'when': '기본', 'reason': '지지 소화불량', 'refs': ['F2']},
                 {'dx': '만성 위장관 질환', 'test': '대장 조영술', 'when': '기본', 'reason': '', 'refs': ['F2']},
                 {'dx': '소화성 궤양', 'test': '위 내시경', 'when': '기본', 'reason': '지지 흑색변·내시경 필요 / 반대 없음', 'refs': ['F3']},
                 {'dx': '질환A', 'test': '검사가', 'when': '1차 음성 시', 'refs': ['F1']},
                 {'dx': '질환B', 'test': '검사나', 'when': '2차 음성 시', 'refs': ['F1']},
                 {'dx': '질환C', 'test': '검사다', 'when': '3차 음성 시', 'refs': ['F1']}]
        enc = _enc(dx='제2형 당뇨병', diffs=diffs)
        out = explain.render_plan(enc, _empty_plan(tests=['혈액 : CBC, HbA1c : 기본']), None)['tests']
        self.assertNotIn('TRAb', out)                        # 예시 when 복사 줄 제외
        self.assertNotIn('ACTH', out)
        self.assertNotIn('위장 내시경', out)                  # 근거·KB 없는 침습 검사 제외
        self.assertNotIn('대장 조영술', out)
        self.assertIn('위 내시경 : 소화성 궤양 감별', out)     # 근거(reason)에 있으면 유지
        self.assertLessEqual(out.count('(조건부)'), 2)
        # 갑상샘 문맥에서는 TRAb 조건이 타당 → 유지(기존 T8)
        self.assertTrue(explain._prompt_example_hit('TRAb 음성·불명확 시', '부신피로증후군 제2형 당뇨병'))
        self.assertFalse(explain._prompt_example_hit('TRAb 음성·불명확 시', '아급성 갑상샘염 ' + GRAVES))

    def test_kb_refer_priority(self):
        k = kb.match_kb(SED)
        plan = _empty_plan(follow_up=['재진 : 1~2주 후', '의뢰 기준 : 경련·혼동·고열·고혈압 변화 시 신경과'])
        fu = _lines(explain.render_plan(_enc(dx=SED), plan, k)['follow_up'])
        refer = [l for l in fu if explain._fu_type(l) == '의뢰 기준']
        self.assertEqual(refer, ['의뢰 기준 : ' + k['refer_if']])
        self.assertFalse(any('신경과' in l for l in fu))
        # KB 없으면 LLM 줄 유지
        fu = _lines(explain.render_plan(_enc(dx='원인 미상 질환'), plan, None)['follow_up'])
        self.assertIn('의뢰 기준 : 경련·혼동·고열·고혈압 변화 시 신경과', fu)

    def test_s01_escalation(self):
        enc = _enc(dx='급성 충수염', vitals=S01_VITALS, ledger=S01_LEDGER,
                   diffs=[{'dx': '장간막 림프절염', 'test': '복부 초음파', 'when': '기본', 'refs': ['F1']}])
        enc.plan_disp_raw = ['외래 추적(입원 불필요)']
        plan = _empty_plan(disposition=['외래 추적(입원 불필요)'],
                           follow_up=['재진 : 1~2주 후 결과 확인', '즉시 내원 : 복통 악화·고열·구토'])
        out = explain.render_plan(enc, plan, None)
        d = _lines(out['disposition'])
        self.assertTrue(enc.emerg_escalate['escalate'])
        self.assertIn('응급실 의뢰, 당일 외과 평가 필요', d[0])
        self.assertIn('반발통', d[0])
        self.assertFalse(any('외래 추적이 적절' in l or '입원 불필요' in l for l in d))
        self.assertFalse(any(re.search(r'입원\s*(확정|합니다)|수술\s*(합니다|확정)', l) for l in d))
        fu = _lines(out['follow_up'])
        self.assertIn(explain.EMERG_FU, fu)
        self.assertTrue(any(l.startswith('즉시 내원') for l in fu))
        self.assertIn('외과', ''.join(l for l in fu if explain._fu_type(l) == '의뢰 기준'))
        note = {'S': {'hpi': ''}, 'P': dict(out)}
        record.add_safety_lines(enc, note)                    # '외래 추적이 적절' 없어도 예외 없이
        assert_safe_plan(self, note)
        say = ['급성 충수염 가능성이 높아요.', '맹장에 염증이 생겨 배가 아파요.', '피검사와 복부 CT로 확인해요.',
               '복통 악화·고열·구토·어지럼 시 바로 오세요.', '1~2주 뒤 결과 보러 다시 오세요.']
        with mock.patch.object(explain, 'ask_json') as m:
            s = explain.fix_say(enc, list(say), None)
        self.assertEqual(m.call_count, 0)
        self.assertIn(explain.EMERG_SAY, s)
        self.assertFalse(any('1~2주 뒤' in x for x in s))
        self.assertLessEqual(len(s), enc.cfg['EXPLAIN_N'])
        for x in [x for x in s if x != saymod.QUESTION_LINE]:
            self.assertEqual(saymod.say_problem(x), '', x)
            self.assertLessEqual(nlen(x), 30, x)
            self.assertIsNone(explain.SAY_BAD_RE.search(x), x)
        # 플래그로 끔
        enc0 = _enc(dx='급성 충수염', vitals=S01_VITALS, ledger=S01_LEDGER, EMERG_ESCALATE=0)
        self.assertNotIn('응급실 의뢰', explain.render_plan(enc0, plan, None)['disposition'])

    def test_no_escalation_stable(self):
        for dx, k, ledger in ((GRAVES, kb.match_kb(GRAVES), C10_LEDGER), (SED, kb.match_kb(SED), []),
                              ('긴장성 두통', None, C10_LEDGER)):
            enc = _enc(dx=dx, ledger=ledger)
            plan = _empty_plan(disposition=['급성 위험 징후 없어 외래 추적(입원 불필요)', '증상 악화 시 응급실 내원'],
                               follow_up=['재진 : 1~2주 후'])
            out = explain.render_plan(enc, plan, k)
            self.assertFalse(enc.emerg_escalate['escalate'], dx)
            self.assertNotIn('응급실 의뢰', out['disposition'])
            self.assertNotIn(explain.EMERG_FU, out['follow_up'])
        self.assertTrue(explain._emerg_text_hit('응급 : 외과 평가 필요'))
        self.assertFalse(explain._emerg_text_hit('입원 고려'))


if __name__ == '__main__':
    unittest.main()

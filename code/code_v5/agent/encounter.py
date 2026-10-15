"""진료 흐름: 시작 정보 구조화 → 공감 → 문진(규칙+적응형) → 진찰 → 진단 투표 → 계획 → 설명 → 기록 제출."""
from __future__ import annotations

import json
import re
import time
import uuid

from nova_sdk import NovaError

from . import banks
from .llm import Budget, ask, ask_json
from .util import (MAX_CHARS, clen, fits, is_one_at_a_time, is_similar, log, log_error, nfc, parse_age, parse_sex,
                   split_to_fit, validate_question)

STOP_CODES = {'TURN_LIMIT_REACHED', 'SESSION_EXPIRED', 'SESSION_CLOSED', 'RUN_NOT_ACTIVE'}
TURN_USING = {'EMPTY_CONTENT', 'CONTENT_TOO_LONG', 'EXAM_NOT_SPECIFIC', 'EXAM_NOT_RECOGNIZED'}
ACTION_SAME_ID = {'API_UNAVAILABLE', 'REQUEST_PENDING', 'LOCAL_GATEWAY_UNAVAILABLE', 'INVALID_API_RESPONSE', 'API_ERROR',
                  'PROVIDER_UNAVAILABLE'}
ACTION_NEW_ID = {'PATIENT_RESPONSE_INVALID', 'EXAMINER_RESPONSE_INVALID'}

DOCTOR_ROLE = '당신은 한국 외래 진료실의 숙련된 의사입니다. 가상 환자를 진료하고 있습니다.'
EXPLAIN_KEYS = ('diagnosis', 'tests', 'treatment', 'warning', 'lifestyle', 'concern')


class Encounter:
    def __init__(self, client, cfg: dict):
        self.client = client
        self.cfg = cfg
        session = client.session()
        self.session = session
        initial = session.get('initial') or {}
        self.opening = nfc(initial.get('opening') or '')
        self.vitals = nfc(initial.get('vital_signs') or '')
        self.budget = Budget(session.get('deadline'))
        self.turns_remaining = int(session.get('turns_remaining') or 50)
        self.turn = max(0, 50 - self.turns_remaining)
        self.ledger: list[dict] = []
        self.asked: list[str] = []
        self.planned: list[str] = []
        self.counts = {'say': 0, 'exam': 0, 'refused': 0, 'one_at_a_time': 0, 'skipped_invalid': 0,
                       'exam_refused': 0, 'interview': 0}
        self.stopped = False
        self.profile: dict = {}
        self.differentials: list[str] = []
        self.dx = ''
        self.dx_detail: dict = {}
        self.plan: dict = {}
        self.explained: list[str] = []
        self.blacklist: set[str] = set()
        self.done_exams: list[str] = []
        self.ros_priority: list[str] = []
        self.asked_qids: set[str] = set()

    # ------------------------------------------------------------------ actions
    def time_left(self) -> float:
        return self.budget.seconds_left()

    def can_act(self) -> bool:
        return not self.stopped and self.turns_remaining > 0 and self.time_left() > 90

    def act(self, kind: str, text: str, *, phase: str, qid: str = '', label: str = ''):
        """SAY/EXAM 한 번. 성공하면 원장 항목, 거절이면 {'refused': code}, 실행 못 하면 None."""
        if not self.can_act():
            return None
        text = nfc(text).strip()
        if not fits(text, MAX_CHARS):
            self.counts['skipped_invalid'] += 1
            log(f'skip invalid text ({clen(text)}): {text!r}')
            return None
        request_id = str(uuid.uuid4())
        reply = None
        for attempt in range(7):
            try:
                if kind == 'SAY':
                    reply = self.client.say(text, request_id=request_id)
                else:
                    reply = self.client.exam(text, request_id=request_id)
                break
            except NovaError as exc:
                code = exc.code
                if code in STOP_CODES:
                    self.stopped = True
                    log_error(f'{kind} stop {code}')
                    return None
                if code in TURN_USING:
                    self.turn += 1
                    self.turns_remaining -= 1
                    self.counts['refused'] += 1
                    if kind == 'EXAM':
                        self.counts['exam_refused'] += 1
                    self.ledger.append({'turn': self.turn, 'kind': kind, 'text': text, 'reply': '', 'phase': phase,
                                        'refused': code, 'qid': qid, 'label': label})
                    log(f'turn {self.turn} {kind} REFUSED {code}: {text}')
                    return {'refused': code}
                if code in ACTION_SAME_ID:
                    time.sleep(min(3 * (attempt + 1), 15))
                    continue
                if code in ACTION_NEW_ID:
                    request_id = str(uuid.uuid4())
                    time.sleep(2)
                    continue
                log_error(f'{kind} unexpected {code}: {text}')
                return None
            except ValueError as exc:  # SDK 길이 검사
                log_error(f'{kind} ValueError {exc}')
                return None
        if reply is None:
            log_error(f'{kind} gave up after retries: {text}')
            return None
        turn = reply.get('turn')
        self.turn = int(turn) if isinstance(turn, int) else self.turn + 1
        tr = reply.get('turns_remaining')
        self.turns_remaining = int(tr) if isinstance(tr, int) else self.turns_remaining - 1
        answer = nfc(reply.get('content') if kind == 'SAY' else reply.get('result') or '').strip()
        entry = {'turn': self.turn, 'kind': kind, 'text': text, 'reply': answer, 'phase': phase, 'qid': qid,
                 'label': label}
        self.ledger.append(entry)
        if kind == 'SAY':
            self.counts['say'] += 1
            self.asked.append(text)
            if is_one_at_a_time(answer):
                self.counts['one_at_a_time'] += 1
                entry['one_at_a_time'] = True
        else:
            self.counts['exam'] += 1
        log(f'turn {self.turn} {kind}: {text} -> {answer[:60]}')
        return entry

    # ------------------------------------------------------------------ transcript helpers
    def start_info(self) -> str:
        return f'시작 정보(환자 첫 진술, 확인된 사실): {self.opening}\n시작 활력징후: {self.vitals.replace(chr(10), ", ")}'

    def transcript(self, *, include_refused=False, clinical_only=False) -> str:
        """clinical_only: 공감·마무리 설명 턴 제외(근거·계획 작성용)."""
        lines = []
        for e in self.ledger:
            if clinical_only and e.get('phase') in ('empathy', 'explain', 'explain-answer'):
                continue
            if e.get('refused'):
                if include_refused:
                    lines.append(f"턴 {e['turn']} | ({e['kind']} 거절: {e['text']})")
                continue
            if e['kind'] == 'SAY':
                lines.append(f"턴 {e['turn']} | 의사: {e['text']} | 환자: {e['reply']}")
            else:
                lines.append(f"턴 {e['turn']} | 진찰({exam_name(e['text'])}): {e['reply']}")
        return '\n'.join(lines) or '(아직 없음)'

    def interview_left(self) -> int:
        # 진찰·설명 턴을 남겨 두도록 서버 잔여 턴으로도 제한
        by_turns = self.turns_remaining - (self.cfg['EXAM_MAX'] + self.cfg['EXPLAIN_MAX'] + 2)
        return min(self.cfg['INTERVIEW_MAX'] - self.counts['interview'], by_turns)

    def phase_time_ok(self) -> bool:
        return self.time_left() > self.cfg['WRAPUP_SECONDS']

    # ------------------------------------------------------------------ 1. 시작 정보 구조화
    def structure(self):
        age = parse_age(self.opening)
        sex = parse_sex(self.opening)
        peds_re = bool(re.search(r'(보호자|엄마|아빠|어머니|아버지).{0,20}(함께|같이|데리고|동반)', self.opening))
        cats_list = list(banks.CATEGORY_BUNDLES)
        is_peds = age is not None and age < 15
        hpi = list(banks.PEDS_HPI if is_peds else banks.ADULT_HPI) + list(
            banks.PEDS_HISTORY if is_peds else banks.ADULT_HISTORY)
        sys_prompt = DOCTOR_ROLE + ' 진료 시작 전 환자 첫 진술을 정리합니다. JSON 객체 하나만 출력하세요.'
        user = (f'{self.start_info()}\n\n'
                '다음 키를 가진 JSON을 출력하세요.\n'
                '{"age": 나이(정수, 모르면 null), "sex": "M" 또는 "F", "pediatric": 소아 환자이고 보호자가 대신 답하면 true,\n'
                ' "chief_complaint": "주호소(짧은 한국어 명사구)", "pain": 통증이 주호소면 true,\n'
                f' "categories": {cats_list} 중 주호소와 관련된 것 1~3개,\n'
                f' "answered": 첫 진술에 이미 분명한 답이 있는 문진 항목 id 목록 (가능한 id: {[h[0] + ":" + h[2] for h in hpi]}, '
                'id만 쓰기),\n'
                ' "empathy": "주호소로 겪은 불편·걱정을 알아주는 공감 한마디(존댓말, 25자 이내, 질문 아님. '
                '예시 - 살이 갑자기 빠져서 많이 걱정되셨겠어요. / 잠을 못 주무셔서 많이 힘드셨겠어요.)"}')
        res = ask_json(self.client, self.budget, sys_prompt, user, effort='low', max_tokens=6000, tag='structure',
                       want=dict, tries=2)
        res = res if isinstance(res, dict) else {}
        try:
            llm_age = int(res.get('age')) if res.get('age') is not None else None
        except (TypeError, ValueError):
            llm_age = None
        if age is None:
            age = llm_age
        if not sex and str(res.get('sex', '')).upper() in ('M', 'F'):
            sex = str(res['sex']).upper()
        pediatric = (age is not None and age < 15) or (peds_re and (age is None or age < 18))
        cc = nfc(res.get('chief_complaint') or '').strip()
        if not cc:
            cc = self.opening.split('.')[1].strip() if '.' in self.opening else self.opening[:40]
        # LLM 카테고리는 키워드로도 확인될 때만 채택(불면에 neuro가 붙는 식의 잡음 방지)
        cats = [c for c in (res.get('categories') or []) if c in banks.CATEGORY_BUNDLES
                and re.search(banks.CATEGORY_BUNDLES[c][0], cc + ' ' + self.opening)]
        for c in banks.detect_categories(cc + ' ' + self.opening, pediatric):
            if c not in cats and len(cats) < 4:
                cats.append(c)
        # 소아가 아니면 growth 묶음은 의미 없음
        cats = [c for c in cats if banks.bundle_questions([c], pediatric)]
        if res.get('pain') and 'pain' not in cats and not pediatric:
            cats.insert(0, 'pain')
        if pediatric and 'growth' in cats:
            cats = ['growth']  # 소아 성장 문제는 성장 묶음만(부모 키·사춘기 시기 등 핵심 문항 우선)
        # 약물 관련 주호소(처방 요구 등)는 약물 묶음(복용량·내성·금단·여러 곳 처방)이 진단의 핵심이므로 맨 앞
        for first in ('growth', 'drug'):
            if first in cats:
                cats.remove(first)
                cats.insert(0, first)
        answered = [a.split(':')[0].strip() for a in (res.get('answered') or []) if isinstance(a, str)]
        empathy = nfc(res.get('empathy') or '').strip()
        if not fits(empathy, MAX_CHARS) or '?' in empathy:
            empathy = '많이 걱정되셨겠어요.'
        self.profile = {'age': age, 'sex': sex, 'pediatric': bool(pediatric), 'cc': cc, 'categories': cats[:3],
                        'answered': answered, 'empathy': empathy}
        log(f'profile: {self.profile}')

    # ------------------------------------------------------------------ 2. 문진
    def ask_question(self, q: str, *, phase: str, qid: str = '', label: str = '', check_dup=True) -> bool:
        if self.interview_left() <= 0 or not self.can_act():
            return False
        if check_dup and is_similar(q, self.asked):
            return False
        entry = self.act('SAY', q, phase=phase, qid=qid, label=label)
        if entry is None:
            return False
        self.counts['interview'] += 1
        if isinstance(entry, dict) and entry.get('one_at_a_time'):
            self.retry_single(q, phase)
        return True

    def retry_single(self, q: str, phase: str):
        """'한 번에 하나씩' 응답: 질문을 하나로 줄여 한 번만 다시 묻는다."""
        simple = None
        m = re.match(r'^(.*?)(?:이나|나|랑|이랑|와|과|,)\s', q)
        if m:
            tail = re.search(r'(있으세요\?|있나요\?|하세요\?|드세요\?|나요\?|세요\?)$', q)
            if tail:
                cand = f'{m.group(1)} {tail.group(1)}'
                if fits(cand) and not is_similar(cand, self.asked, 0.9):
                    simple = cand
        if simple is None:
            res = ask(self.client, self.budget, DOCTOR_ROLE,
                      f'환자가 "한 번에 하나씩 물어봐 주세요"라고 했습니다. 다음 질문을 한 가지만 묻는 25자 이내 질문으로 바꾸세요: "{q}"\n'
                      'JSON {"question": "..."} 하나만 출력.', effort='low', max_tokens=800, tag='single', want=dict,
                      reserve=self.cfg['CALL_RESERVE'])
            cand = nfc((res or {}).get('question') or '').strip()
            ok, _ = validate_question(cand, None)
            if ok:
                simple = cand
        if simple and self.interview_left() > 0:
            entry = self.act('SAY', simple, phase=phase + '-single')
            if entry and not entry.get('refused'):
                self.counts['interview'] += 1

    def patient_texts(self) -> list[str]:
        return [self.opening] + [e.get('reply') or '' for e in self.ledger if e['kind'] == 'SAY' and not e.get('refused')]

    def ask_bank(self, items, *, phase: str, cap: int, skip_text: str = ''):
        n = 0
        answered = set(self.profile.get('answered') or [])
        for item in items:
            if n >= cap or self.interview_left() <= 0 or not self.phase_time_ok():
                break
            qid, q, label = item[0], item[1], item[2]
            skip = item[3] if len(item) > 3 else None
            if qid in self.asked_qids or qid in answered:
                continue
            if qid in ('aggravate', 'relieve') and not (set(self.profile.get('categories') or []) & banks.SYMPTOM_CATS):
                continue
            if skip and re.search(skip, skip_text or self.opening):
                continue
            if banks.covered_by_answers(qid, self.patient_texts()):
                self.asked_qids.add(qid)
                log(f'skip covered {qid}: {q}')
                continue
            if self.ask_question(q, phase=phase, qid=qid, label=label):
                self.asked_qids.add(qid)
                n += 1
                last = self.ledger[-1] if self.ledger else {}
                if qid == 'gr_record' and re.search(r'(수첩|기록|있)', last.get('reply') or '') \
                        and not re.search(r'^(아니|없)', last.get('reply') or ''):
                    g = banks.GR_VALUES
                    if self.ask_question(g[1], phase=phase, qid=g[0], label=g[2]):
                        self.asked_qids.add(g[0])
                        n += 1
        return n

    def adaptive(self, n_questions: int, round_no: int, ros_menu=None):
        if n_questions <= 0 or self.interview_left() <= 0 or not self.phase_time_ok():
            return
        upcoming = [q for q in self.planned if not is_similar(q, self.asked, 0.9)]
        sys_prompt = (DOCTOR_ROLE + ' 감별진단을 좁히기 위한 다음 문진 질문을 고릅니다. JSON 객체 하나만 출력하세요.')
        ros_part, ros_out = '', ''
        if ros_menu:
            ros_part = '\n일반 계통 문진 목록 (id | 질문):\n' + '\n'.join(f'{r[0]} | {r[1]}' for r in ros_menu) + '\n'
            ros_out = ', "ros_ids": ["위 계통 문진 목록 중 이 환자에게 중요한 순서대로 id 4~6개"]'
        user = (f'{self.start_info()}\n\n지금까지의 진료:\n{self.transcript()}\n\n'
                f'이후 따로 물을 예정인 질문(이것과 같은 내용은 절대 내지 말 것): {upcoming}\n{ros_part}\n'
                '방법: 먼저 가능성 높은 감별진단 3~5개를 정하고, 각 감별진단을 지지하거나 배제하는 특징 증상·징후·위험인자 중 '
                '아직 확인하지 않은 것을 질문으로 만드세요. (예: 흉통이면 운동 시 악화, 왼팔로 퍼짐, 식은땀, 흡연 등)\n'
                '상위 3개 감별진단을 서로 가르는 질문을 앞에 두고, 답을 들어도 감별진단이 바뀌지 않는 질문은 빼세요. '
                '부정형("~없으세요?")보다 긍정형 질문을 쓰세요.\n'
                '규칙: 한국어 존댓말, 한 번에 한 가지 증상만, 25자 이내, 물음표 하나, 예/아니요로 답할 수 있게. '
                '"전부/모두/다/요약" 금지. 환자에게 진단명을 묻지 말 것. 이미 물었거나 환자가 이미 말한 내용·예정된 질문은 제외.\n'
                f'출력: {{"differentials": ["가능성 높은 순 감별진단"], "questions": ["중요한 순서로 질문 {n_questions + 4}개"]{ros_out}}}')
        res = ask_json(self.client, self.budget, sys_prompt, user, effort='medium', max_tokens=4000,
                       tag=f'adaptive{round_no}', want=dict, tries=2, reserve=self.cfg['CALL_RESERVE'])
        if not isinstance(res, dict):
            return
        diffs = [nfc(d).strip() for d in (res.get('differentials') or []) if isinstance(d, str) and d.strip()]
        if diffs:
            self.differentials = diffs[:5]
        if ros_menu:
            ids = [str(i) for i in (res.get('ros_ids') or []) if isinstance(i, (str, int))]
            self.ros_priority = [i for i in ids if any(r[0] == i for r in ros_menu)]
        qs = [nfc(q).strip() for q in (res.get('questions') or []) if isinstance(q, str)]
        good, bad = [], []
        for q in qs:
            if is_similar(q, upcoming):
                continue
            ok, why = validate_question(q, self.asked + good)
            if ok:
                good.append(q)
            elif why in ('too_long', 'multi', 'list', 'multi_q'):
                bad.append(q)
        if bad and len(good) < n_questions:
            fix = ask_json(self.client, self.budget, DOCTOR_ROLE,
                           '다음 질문들을 각각 한 가지만 묻는 25자 이내 존댓말 질문으로 줄이세요. '
                           f'JSON {{"questions": [...]}} 하나만 출력.\n{bad}', effort='low', max_tokens=1500,
                           tag='shorten', want=dict, tries=1, reserve=self.cfg['CALL_RESERVE'])
            for q in (fix or {}).get('questions') or []:
                q = nfc(q).strip()
                ok, _ = validate_question(q, self.asked + good)
                if ok:
                    good.append(q)
        log(f'adaptive{round_no}: diffs={self.differentials} good={good}')
        n = 0
        for q in good:
            if n >= n_questions:
                break
            if self.ask_question(q, phase=f'adaptive{round_no}', qid=f'ad{round_no}', label='적응형'):
                n += 1

    def interview(self):
        cfg, prof = self.cfg, self.profile
        peds = prof['pediatric']
        age = prof.get('age')
        # 공감
        if self.can_act():
            self.act('SAY', prof['empathy'], phase='empathy')
        hpi = banks.PEDS_HPI if peds else banks.ADULT_HPI
        history = list(banks.PEDS_HISTORY if peds else banks.ADULT_HISTORY)
        if not peds and prof.get('sex') == 'F' and (age is None or 12 <= age <= 55):
            idx = next((i for i, h in enumerate(history) if h[0] == 'fh_open'), len(history))
            history[idx:idx] = [(w[0], w[1], w[2]) for w in banks.WOMEN_BUNDLE if w[0] in ('wm_change', 'wm_pregnancy')]
        cats = prof.get('categories') or []
        if not peds and 'weight' in cats:
            idx = next((i for i, h in enumerate(history) if h[0] == 'fh_open'), len(history) - 1) + 1
            history.insert(idx, banks.FH_AUTOIMMUNE)
        bundle = banks.bundle_questions(cats, peds)
        ros = banks.PEDS_ROS if peds else banks.ordered_ros(cats, banks.ADULT_ROS)
        ice = banks.peds_ice(self.opening) if peds else banks.ADULT_ICE
        self.planned = [h[1] for h in history] + [i[1] for i in ice] + [r[1] for r in ros[:9]]
        self.ask_bank(hpi, phase='hpi', cap=cfg['HPI_MAX'])
        self.ask_bank(bundle, phase='bundle', cap=cfg['BUNDLE_MAX'])
        self.adaptive(cfg['ADAPTIVE1_MAX'], 1)
        ad2_min = min(1, cfg['ADAPTIVE2_MAX'])
        core_hist = [h for h in history if h[0] not in banks.OPTIONAL_HISTORY]
        opt_hist = [h for h in history if h[0] in banks.OPTIONAL_HISTORY]
        # ROS(카테고리 순서)를 과거력보다 먼저 일정 수 확보
        ros_first = min(cfg['ROS_MIN'], max(0, self.interview_left() - len(ice) - ad2_min - 4))
        self.ask_bank(ros, phase='ros', cap=ros_first, skip_text=prof['cc'] + ' ' + self.opening)
        hist_cap = max(0, self.interview_left() - (len(ice) + ad2_min))
        self.ask_bank(core_hist, phase='history', cap=hist_cap)
        self.planned = [i[1] for i in ice]
        self.adaptive(min(cfg['ADAPTIVE2_MAX'], max(0, self.interview_left() - len(ice))), 2)
        extra = max(0, self.interview_left() - len(ice))
        if extra:
            n = self.ask_bank(ros, phase='ros', cap=min(extra, cfg['ROS_MAX']), skip_text=prof['cc'] + ' ' + self.opening)
            extra -= n
        if extra:
            self.ask_bank(opt_hist, phase='history', cap=extra)
        self.ask_bank(ice, phase='ice', cap=len(ice))

    # ------------------------------------------------------------------ 3. 진찰
    def always_exams(self) -> list[str]:
        return banks.PEDS_ALWAYS_EXAMS if self.profile.get('pediatric') else banks.ALWAYS_EXAMS

    def choose_exams(self) -> list[str]:
        prof = self.profile
        always = self.always_exams()
        n = self.cfg['EXAM_MAX'] - len(always)
        diff_txt = ' '.join(self.differentials) + ' ' + (prof.get('cc') or '')
        allowed = [e for e in banks.EXAM_BANK if e[0] not in always
                   and (e[0] not in banks.CONDITIONAL_EXAMS
                        or re.search(banks.CONDITIONAL_EXAMS[e[0]], diff_txt, flags=re.I))]
        allowed_ids = {e[0] for e in allowed}
        # 카테고리 하한: 주 카테고리 앞 6개 + 부 카테고리 앞 2개
        cats = list(prof.get('categories') or [])
        if prof.get('pediatric') and 'growth' in cats:
            cats.remove('growth')
            cats.insert(0, 'growth')
        thyroid_dx = bool(re.search(banks.THYROID_RE, ' '.join(self.differentials[:2]), flags=re.I))
        if thyroid_dx and not any(c in ('weight',) for c in cats):
            cats.append('thyroid')  # 감별 1~2위가 갑상선일 때만 부 카테고리로
        floor = []
        for k, c in enumerate(cats[:3]):
            lst = [i for i in banks.category_exam_list(c) if i in allowed_ids]
            floor += [i for i in lst[:(6 if k == 0 else 2)] if i not in floor]
        menu = '\n'.join(f'{e[0]} | {exam_name(e[1])} | {e[2]}' for e in allowed)
        sys_prompt = (DOCTOR_ROLE + ' 신체진찰 항목을 고릅니다. 아래 목록의 id만 쓰고(목록 밖 진찰 금지), 같은 부위·같은 목적은 '
                      '중복하지 마세요. 감별진단을 확인·배제하는 진찰을 먼저, 표준 기본 진찰(심음·폐 청진, 복부 촉진, 결막, 갑상선, '
                      '의식)은 남는 자리에. JSON 하나만 출력하세요.')
        user = (f'{self.start_info()}\n\n문진 내용:\n{self.transcript()}\n\n현재 감별진단: {self.differentials}\n\n'
                f'진찰 목록 (id | 진찰 | 계통):\n{menu}\n\n'
                f'이미 하기로 한 진찰: {always + floor}\n'
                f'그 외에 감별진단을 확인·배제하는 데 중요한 진찰 {max(1, n - len(floor))}개를 중요한 순서로 고르세요.\n'
                '출력: {"exam_ids": ["id", ...]}')
        res = ask_json(self.client, self.budget, sys_prompt, user, effort='low', max_tokens=6000, tag='exams',
                       want=dict, tries=2, reserve=self.cfg['CALL_RESERVE'])
        llm_ids = []
        for i in (res or {}).get('exam_ids') or []:
            i = str(i).strip()
            if i in allowed_ids and i not in llm_ids:
                llm_ids.append(i)
        rest = []
        for c in cats[:3]:
            rest += banks.category_exam_list(c)
        ids = []
        for i in floor + llm_ids + rest + banks.CORE12:
            if i not in ids and i in allowed_ids:
                ids.append(i)
        # 중복 그룹 제거
        out, groups = [], set()
        for i in ids:
            g = banks.EXAM_BY_ID[i][3]
            if g in groups:
                continue
            groups.add(g)
            out.append(i)
        return out[:n]

    def examine(self):
        if not self.can_act():
            return
        chosen = self.always_exams() + self.choose_exams()
        log(f'exams: {chosen}')
        budget_turns = min(self.cfg['EXAM_MAX'], self.turns_remaining - (self.cfg['EXPLAIN_MAX'] + 2))
        done = 0
        for i in chosen:
            if done >= budget_turns or not self.can_act() or self.time_left() < self.cfg['WRAPUP_SECONDS'] - 60:
                break
            if i in self.blacklist or i in self.done_exams:
                continue
            entry = self.act('EXAM', banks.EXAM_BY_ID[i][1], phase='exam', qid=i)
            if entry is None:
                continue
            done += 1
            if entry.get('refused'):
                self.blacklist.add(i)
                continue
            entry['system'] = banks.EXAM_BY_ID[i][2]
            self.done_exams.append(i)

    # ------------------------------------------------------------------ 4. 진단 투표
    def diagnose_vote(self):
        from .record import vote_diagnosis
        self.dx, self.dx_detail = vote_diagnosis(self)
        log(f'diagnosis: {self.dx}')

    # ------------------------------------------------------------------ 5. 계획 + 설명
    def make_plan(self):
        from .record import write_plan
        self.plan = write_plan(self)

    def explain(self, quick=False):
        from . import say as saymod
        lines = []
        if not quick and self.budget.can_call(self.cfg['CALL_RESERVE']) and self.time_left() > 240:
            lines = self.explanation_lines()
        if not lines:
            lines = fallback_explanation(self.dx_ko(), quick)
        max_lines = 4 if quick else self.cfg['EXPLAIN_MAX'] + 1
        lines = saymod.ensure_elements(lines, self.dx_ko(), max_lines=max_lines, log=log)
        answers = 0
        answer_max = 0 if quick else self.cfg.get('ANSWER_MAX', 2)
        for i, line in enumerate(lines):
            if not self.can_act():
                break
            entry = self.act('SAY', line, phase='explain')
            if not entry or entry.get('refused'):
                continue
            self.explained.append(line)
            reply = entry.get('reply', '')
            remaining = len(lines) - i - 1
            if (answers < answer_max and looks_like_question(reply) and not re.search(r'^(아니|없|괜찮)', reply)
                    and self.turns_remaining > remaining + 1 and self.can_act()):
                answer = self.answer_patient(reply)
                if answer:
                    e2 = self.act('SAY', answer, phase='explain-answer')
                    if e2 and not e2.get('refused'):
                        self.explained.append(answer)
                        answers += 1

    def dx_ko(self) -> str:
        d = self.dx or ''
        return re.sub(r'\s*\(.*?\)\s*$', '', d).strip() or d

    def explanation_lines(self) -> list[str]:
        from . import say as saymod
        ice = [e for e in self.ledger if e.get('qid', '').startswith('ice')]
        ice_txt = '\n'.join(f"{e['text']} -> {e['reply']}" for e in ice) or '(없음)'
        p = self.plan or {}
        n = self.cfg['EXPLAIN_MAX']
        sys_prompt = DOCTOR_ROLE + ' 진료를 마무리하며 환자에게 쉬운 말로 설명합니다. JSON 객체 하나만 출력하세요.'
        audience = '보호자(아이 부모)' if self.profile.get('pediatric') else '환자'
        user = (f'{self.start_info()}\n\n진료 내용:\n{self.transcript()}\n\n주진단: {self.dx}\n'
                f'추가 검사 계획: {p.get("tests", "")}\n치료: {p.get("treatment", "")}\n'
                f'처치: {p.get("disposition", "")}\n추적·경고 증상: {p.get("follow_up", "")}\n'
                f'{audience}의 걱정·기대: {ice_txt}\n\n'
                f'진료를 마치며 {audience}에게 말할 문장 정확히 {n}개를 쓰세요.\n' + SAY_RULES)
        res = ask_json(self.client, self.budget, sys_prompt, user, effort=self.cfg['EXPLAIN_EFFORT'], max_tokens=12000,
                       tag='explain', want=dict, tries=2, reserve=self.cfg['CALL_RESERVE'],
                       validate=lambda v: isinstance(v.get('say'), list) and len(v['say']) >= 3)
        raw = [nfc(str(s)).strip() for s in ((res or {}).get('say') or []) if str(s).strip()]
        good, bad = [], []
        for s in raw:
            (bad if saymod.say_problem(s) else good).append(s)
        if bad and self.budget.can_call(self.cfg['CALL_RESERVE']):
            fix = ask_json(self.client, self.budget, DOCTOR_ROLE,
                           '다음 문장들을 뜻을 유지하며 각각 공백 포함 28자 이내의 쉬운 존댓말 평서문으로 다시 쓰세요. 띄어쓰기를 지키고 '
                           '영어 약어·물음표·단정적 안심("걱정 안 해도", "완치")은 쓰지 마세요. '
                           'JSON {"say": [...]} 하나만 출력(같은 순서).\n' + json.dumps(bad, ensure_ascii=False),
                           effort='low', max_tokens=4000, tag='say-fix', want=dict, tries=1,
                           reserve=self.cfg['CALL_RESERVE'])
            fixed = [nfc(str(s)).strip() for s in ((fix or {}).get('say') or [])]
            fixed_ok = {}
            for orig, new in zip(bad, fixed):
                if new and not saymod.say_problem(new):
                    fixed_ok[orig] = new
            good = [fixed_ok.get(s, s) for s in raw if not saymod.say_problem(fixed_ok.get(s, s))]
        log(f'explain say: {len(good)} ok, {len(bad)} fixed/dropped')
        return good

    def answer_patient(self, question: str) -> str:
        from . import say as saymod
        p = self.plan or {}
        res = ask(self.client, self.budget, DOCTOR_ROLE,
                  f'환자의 말: "{question}"\n진단: {self.dx}\n계획 요약: 검사 {p.get("tests", "")[:300]} / 치료 '
                  f'{p.get("treatment", "")[:300]} / 추적 {p.get("follow_up", "")[:200]}\n이미 한 설명: {self.explained}\n'
                  '환자에게 할 답 한 문장(공백 포함 28자 이내, 쉬운 존댓말 평서문). 질문에 직접 답하고 미루지 말 것'
                  '("재진 때 설명" 금지). 계획과 모순 금지. 근거 없는 단정·약속 금지. JSON {"answer": "..."} 하나만 출력.',
                  effort='low', max_tokens=4000, tag='answer', want=dict, reserve=self.cfg['CALL_RESERVE'])
        a = nfc((res or {}).get('answer') or '').strip()
        if not a or saymod.say_problem(a):
            return '오늘 계획대로 하며 같이 조절해 갈게요.'
        return a


def exam_name(request: str) -> str:
    t = nfc(request).strip()
    for suf in (' 하겠습니다', '하겠습니다', '할게요', ' 할게요'):
        if t.endswith(suf):
            t = t[: -len(suf)].strip()
            break
    return t


def looks_like_question(reply: str) -> bool:
    r = nfc(reply)
    return '?' in r or bool(re.search(r'(궁금|건가요|나요|까요|어떻게|언제|얼마나)', r))


SAY_RULES = (
    '[SAY 규칙] 각 문장은 공백 포함 28자 이내, 쉬운 존댓말 평서문, 영어 약어 금지(MRI·CT만 허용), 한 문장 한 메시지, '
    '띄어쓰기 정확(붙여 쓰기 금지). 단정·보장 금지("걱정 안 해도", "완치", "확실히"). 내용 없는 문장 금지(모든 문장에 구체 정보).\n'
    '순서와 필수 요소: ①진단을 쉬운 말로(병명 포함) ②진단의 의미·원인 한 줄 ③환자 걱정·궁금증에 직접 답 '
    '④검사 이름과 목적(피검사 항목·영상·심전도 등 구체적으로) ⑤치료 계획과 시작 시점(조건부) '
    '⑥약 부작용 경고 또는 안전 수칙(운전·급중단 금지·추가 복용 금지 등 해당 시) '
    '⑦경고 증상: 구체적 증상 4개 이상을 "·"로 이어 한 문장(예: "숨참·불규칙한 맥·고열·혼동 시 바로 오세요.") '
    '⑧재진 시점과 다음 단계(예: "1~2주 뒤 결과 보고 약을 시작해요.") ⑨남으면 생활 수칙.\n'
    '"더 궁금하신 점 있으세요?"는 프로그램이 붙이니 쓰지 마세요. 환자 요청(처방 등)이 있으면 그 결정을 말하세요.\n'
    '출력: {"say": ["문장1", "문장2", ...]}')


def fallback_explanation(dx_ko: str, quick: bool) -> list[str]:
    first = f'{dx_ko} 가능성이 높아 보여요.' if dx_ko else ''
    if not fits(first):
        first = '말씀과 진찰로 원인이 짐작돼요.'
    lines = [first, '정확히 확인하려고 피검사를 할게요.', '검사 결과를 보고 치료를 정할게요.',
             '숨참·흉통·의식 변화·고열 시 바로 오세요.', '1~2주 뒤 결과 보고 다음 치료를 정해요.', '더 궁금하신 점 있으세요?']
    if quick:
        return [first, '정확히 확인하려고 피검사를 할게요.', '숨참·흉통·의식 변화·고열 시 바로 오세요.',
                '1~2주 뒤 결과 보고 다음 치료를 정해요.']
    return lines

"""Doctor 모델 호출 래퍼와 시간·호출 예산 관리."""
from __future__ import annotations

import time
import uuid
from datetime import datetime

from nova_sdk import NovaError

from .util import log, log_error, parse_json

# 같은 request_id로 다시 보내야 하는 오류(서버가 처리 중이거나 일시 장애)
SAME_ID_RETRY = {'PROVIDER_UNAVAILABLE', 'REQUEST_PENDING', 'API_UNAVAILABLE', 'LOCAL_GATEWAY_UNAVAILABLE',
                 'INVALID_API_RESPONSE', 'API_ERROR'}  # 게이트웨이 타임아웃(HTML 응답) 등: 같은 id로 다시 받으면 완료된 답
# 새 request_id로 다시 보내야 하는 오류(빈 답)
NEW_ID_RETRY = {'PROVIDER_RESPONSE_INVALID', 'PROVIDER_USAGE_MISSING'}
# 폴백이 없는 핵심 호출(진단·계획·기록). 나머지는 보조 호출로 보고 장애 시 짧게 기다린다.
ESSENTIAL_TAGS = ('dx', 'plan', 'S-judge', 'A', 'min-call', 'intake', 'facts', 'S')
OPTIONAL_MAX_WAIT = 100.0
# 더 이상 Doctor를 부를 수 없는 오류
FATAL = {'MODEL_CALL_LIMIT', 'MODEL_TOKEN_BUDGET', 'SESSION_EXPIRED', 'SESSION_CLOSED', 'RUN_NOT_ACTIVE'}


class BudgetExhausted(RuntimeError):
    pass


class Budget:
    """세션 마감·Doctor 호출 수·토큰을 추적한다."""

    def __init__(self, deadline_iso=None, *, max_calls=200, max_in=500_000, max_out=100_000):
        self.deadline = None
        if deadline_iso:
            try:
                self.deadline = datetime.fromisoformat(str(deadline_iso).replace('Z', '+00:00')).timestamp()
            except ValueError:
                self.deadline = None
        self.max_calls, self.max_in, self.max_out = max_calls, max_in, max_out
        self.calls = 0          # 서버가 센 것으로 추정되는 호출 수(빈 답 포함)
        self.ok_calls = 0
        self.invalid = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.dead = False       # 호출 한도·토큰 한도 도달
        self.final_reserve = 45.0  # LLM 호출이 침범하지 못하는 마감 직전 시간(기록 제출용)
        self.degraded = False      # Doctor 장애 감지: 보조 호출 생략
        self.started = time.time()
        self.call_log: list[dict] = []

    def seconds_left(self) -> float:
        if self.deadline is None:
            return float('inf')
        return self.deadline - time.time()

    def calls_left(self) -> int:
        return self.max_calls - self.calls

    def tokens_ok(self, expect_out=0) -> bool:
        return self.tokens_in < self.max_in * 0.95 and self.tokens_out + expect_out < self.max_out * 0.97

    def can_call(self, reserve=0) -> bool:
        return not self.dead and self.calls_left() > reserve and self.tokens_ok()

    def stats(self) -> dict:
        return {'doctor_calls': self.calls, 'doctor_ok_calls': self.ok_calls, 'doctor_invalid': self.invalid,
                'doctor_input_tokens': self.tokens_in, 'doctor_output_tokens': self.tokens_out,
                'elapsed_s': round(time.time() - self.started, 1)}


def _sleep(seconds, budget: Budget):
    left = budget.seconds_left()
    time.sleep(max(0.0, min(seconds, left - 5)))


SOFT_OUT_LOW = 35_000   # 누적 출력이 이보다 많으면 effort를 low로 강등
SOFT_OUT_SKIP = 50_000  # 이보다 많으면 보조 호출 생략
MAX_TOKENS_CAP = 8000   # 서버 실측: max_tokens > 8000이면 TOKEN_LIMIT_EXCEEDED(10-13 확인)
LENGTH_RETRY_CAP = MAX_TOKENS_CAP
MIN_TOKENS = {'low': 4000, 'medium': 8000, 'high': 8000}


def ask(client, budget: Budget, system: str, user: str, *, effort='medium', max_tokens=2048, temperature=None,
        json_expected=True, want=None, tag='', reserve=0, max_wait=300.0, optional=None, _length_retry=True):
    """Doctor 모델 한 번 호출(재시도 포함). json_expected면 파싱된 값, 아니면 문자열. 실패 시 None.

    reserve: 이 호출 뒤에 남겨 둘 호출 수(기록 작성용). max_wait: 이 호출에 쓸 최대 시간(초).
    temperature는 gpt-6-luna가 무시하므로 보내지 않는다(인자는 호환용).
    """
    if optional is None:  # 폴백이 있는 보조 호출은 장애 시 빨리 포기한다
        optional = not tag.startswith(ESSENTIAL_TAGS)
    if budget.tokens_out > SOFT_OUT_SKIP and optional:
        log(f'llm[{tag}] skip: soft output cap')
        return None
    if budget.tokens_out > SOFT_OUT_LOW and effort in ('medium', 'high'):
        effort = 'low'
    # luna는 추론 토큰이 많아 max_tokens가 작으면 length로 잘린다: effort별 하한
    max_tokens = min(MAX_TOKENS_CAP, max(int(max_tokens), MIN_TOKENS.get(effort or 'medium', 4000)))
    if optional:
        if budget.degraded:
            log(f'llm[{tag}] skip: provider degraded')
            return None
        max_wait = min(max_wait, OPTIONAL_MAX_WAIT)
    if not budget.can_call(reserve):
        log(f'llm[{tag}] skip: budget (calls={budget.calls}, out={budget.tokens_out})')
        return None
    messages = []
    if system and system.strip():
        messages.append({'role': 'system', 'content': system})
    messages.append({'role': 'user', 'content': user if user and user.strip() else '(내용 없음)'})
    request_id = str(uuid.uuid4())
    started = time.time()
    attempts, invalid_tries = 0, 0
    waits = [3, 6, 10, 15, 20, 30]
    while True:
        attempts += 1
        # 마감 전 DIAGNOSE 제출 시간(final_reserve)을 반드시 남긴다
        limit = min(budget.seconds_left() - budget.final_reserve, max_wait - (time.time() - started))
        if limit < 15:
            log_error(f'llm[{tag}] timeout/deadline after {attempts - 1} attempts')
            return None
        old_timeout = getattr(client, 'timeout', None)
        try:
            kwargs = {'max_tokens': int(max_tokens), 'request_id': request_id}
            if effort:
                kwargs['reasoning_effort'] = effort
            if isinstance(old_timeout, (int, float)):
                client.timeout = max(10, min(old_timeout, limit))  # HTTP 대기도 남은 시간 안으로
            reply = client.chat(messages, **kwargs)
        except NovaError as exc:
            code = exc.code
            if code in FATAL:
                budget.dead = True
                log_error(f'llm[{tag}] fatal {code}')
                return None
            if code in NEW_ID_RETRY:
                budget.calls += 1
                budget.invalid += 1
                invalid_tries += 1
                if invalid_tries >= 3 or not budget.can_call(reserve):
                    log_error(f'llm[{tag}] empty answer x{invalid_tries}')
                    return None
                # 빈 답은 추론이 max_tokens(8000)를 다 써서 생기는 경우가 많다: effort를 한 단계 낮춰 재시도
                if effort == 'high':
                    effort = 'medium'
                elif effort == 'medium' and invalid_tries >= 2:
                    effort = 'low'
                log_error(f'llm[{tag}] empty answer -> retry effort={effort}')
                request_id = str(uuid.uuid4())
                continue
            if code == 'TOKEN_LIMIT_EXCEEDED' and max_tokens > 3000:
                max_tokens = max(3000, int(max_tokens * 0.6))  # 요청 상한 초과: 줄여서 새 id로
                request_id = str(uuid.uuid4())
                log_error(f'llm[{tag}] TOKEN_LIMIT_EXCEEDED -> max_tokens {max_tokens}')
                continue
            if code in SAME_ID_RETRY:
                if attempts > len(waits) or (optional and time.time() - started > OPTIONAL_MAX_WAIT):
                    log_error(f'llm[{tag}] {code} x{attempts}')
                    if optional:
                        budget.degraded = True  # 이후 보조 호출은 건너뛰고 진단·기록에 시간을 남긴다
                    return None
                _sleep(waits[attempts - 1], budget)
                continue
            log_error(f'llm[{tag}] error {code}')
            return None
        except Exception as exc:  # 네트워크 등 예상 밖 오류
            if attempts > 3:
                log_error(f'llm[{tag}] exception {type(exc).__name__}')
                return None
            _sleep(3, budget)
            continue
        finally:
            if isinstance(old_timeout, (int, float)):
                client.timeout = old_timeout
        budget.calls += 1
        budget.ok_calls += 1
        if not optional and time.time() - started < 60:
            budget.degraded = False  # 핵심 호출이 정상 속도로 성공하면 장애 해제
        usage = reply.get('usage') or {}
        budget.tokens_in += int(usage.get('prompt_tokens') or 0)
        budget.tokens_out += int(usage.get('completion_tokens') or 0)
        choice = (reply.get('choices') or [{}])[0]
        content = ((choice.get('message') or {}).get('content') or '').strip()
        finish = choice.get('finish_reason')
        budget.call_log.append({'tag': tag, 'effort': effort, 'max_tokens': max_tokens,
                                'in': usage.get('prompt_tokens'), 'out': usage.get('completion_tokens'),
                                'finish': finish, 'sec': round(time.time() - started, 1)})
        log(f'llm[{tag}] {effort} out={usage.get("completion_tokens")} finish={finish} {time.time() - started:.1f}s')
        if not json_expected:
            return content or None
        value = parse_json(content, want)
        if value is None:
            log(f'llm[{tag}] unparsable: {content[:120]!r}')
            if finish == 'length' and _length_retry:
                bigger = min(LENGTH_RETRY_CAP, int(max_tokens * 1.5))
                lower = {'high': 'medium', 'medium': 'low'}.get(effort, effort)
                if bigger <= max_tokens:  # 상한에 걸려 늘릴 수 없으면 추론을 줄인다
                    effort = lower
                left_wait = max_wait - (time.time() - started)
                if left_wait > 30:
                    return ask(client, budget, system, user, effort=effort, max_tokens=bigger, json_expected=True,
                               want=want, tag=tag + '-len', reserve=reserve, max_wait=left_wait, optional=optional,
                               _length_retry=False)
        return value


def ask_json(client, budget, system, user, *, tries=2, validate=None, **kw):
    """JSON을 얻을 때까지 최대 tries번 호출. validate(value)->bool 통과 못 하면 다시."""
    for i in range(tries):
        value = ask(client, budget, system, user, json_expected=True, **kw)
        if value is not None and (validate is None or validate(value)):
            return value
        if budget.dead:
            return None
        user = user + '\n\n(직전 출력은 형식이 맞지 않았습니다. 설명 없이 JSON 하나만 출력하세요.)'
    return None

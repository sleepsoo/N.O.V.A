"""N.O.V.A. 2026 예선 Doctor Agent — 단계형 베이스라인.

흐름 (턴마다 LLM을 부르지 않고 단계마다 질문 묶음을 계획합니다)
1. 계획: 첫 진술·활력징후로 환자 정보(나이·성별·소아 여부), 초기 감별진단, 현병력 질문 묶음을 만듭니다.
2. 현병력: 계획한 질문을 보내고, 대화를 보고 빠진 현병력·위험 징후 질문을 한 번 더 계획합니다.
3. 과거력·약물·알레르기·가족력·사회력: 규칙(고정 문장)으로 묻습니다. 이미 답한 항목은 건너뜁니다.
4. 감별 문진·진찰: 감별진단을 갱신하고, 가설을 가르는 계통 문진과 진찰 동작(한 번에 하나)을 계획해 수행합니다.
5. 평가·계획: 주진단, 근거, 감별, 검사·치료·처치·추적·교육과 환자 설명 문장을 만듭니다.
6. 설명: 환자에게 진단·계획·경고 증상을 SAY로 실제 설명하고, 환자 질문에 답합니다.
7. 기록: S는 대화만 근거로 LLM이, O(진찰)는 받은 결과를 코드로 그대로 옮겨 적고, A·P는 5단계 결과로 채워 제출합니다.

예선 전용입니다(client.chat은 예선 지정 모델). 본선은 prepare()에서 직접 불러온 모델로 바꿉니다.
"""
import json
import re
import sys
import time
import unicodedata
from datetime import datetime

from nova_sdk import RECORD_FIELDS, NovaError, empty_record, run_agent

MAX_TURNS = 50         # 대회 한도
TIME_MARGIN = 240      # 세션 마감 4분 전부터는 기록 작성으로 넘어갑니다(초)
MAX_CHARS = 30         # SAY·EXAM 한 번에 30자(공백 포함, NFC) 이하
# 단계별 턴 상한. 합계가 MAX_TURNS 안에 들어오도록 잡고, 실제로는 남은 턴에 맞춰 줄입니다.
BUDGET = {'hpi': 8, 'hpi_more': 6, 'core': 12, 'ros': 6, 'exam': 10, 'closing': 4, 'qa': 2}
RESERVE_CLOSING = BUDGET['closing'] + 1   # 설명 단계를 위해 항상 남겨 두는 턴
# 모델 호출 한도(증례당 200회, 입력 500,000·출력 100,000토큰) 안쪽에서 멈춥니다.
CALL_LIMIT, INPUT_LIMIT, OUTPUT_LIMIT = 150, 400_000, 80_000
# 답은 없지만 1턴을 쓰는 거절. 이 밖의 오류(INVALID_KEY 등)는 더 진행해도 소용없으므로 진료를 멈춥니다.
REFUSED_CODES = {'EXAM_NOT_SPECIFIC', 'EXAM_NOT_RECOGNIZED', 'CONTENT_TOO_LONG', 'EMPTY_CONTENT'}
RETRY_CODES = {'PROVIDER_UNAVAILABLE', 'PROVIDER_RESPONSE_INVALID', 'PATIENT_RESPONSE_INVALID',
               'EXAMINER_RESPONSE_INVALID', 'API_UNAVAILABLE'}
FATAL_CHAT_CODES = {'INVALID_KEY', 'MODEL_CALL_LIMIT', 'MODEL_TOKEN_BUDGET', 'MODEL_NOT_ALLOWED'}
EXAM_REGIONS = ('General', 'H/E/E/N/T', 'Neck', 'Chest', 'Abdomen', 'Back', 'Extremities', 'Neuro', 'Skin', 'Others')

# 표준 진찰 메뉴(부위, 진찰명). 공개 샘플 진찰 결과표의 항목 이름을 따릅니다. 보낼 때 '진찰명하겠습니다'.
EXAM_MENU = [
    ('General', '전반적 외관 시진'), ('General', '의식·지남력 평가'), ('General', '인지기능 선별검사'),
    ('General', '기분·정동 평가'), ('General', '병식 평가'), ('General', '기립성 혈압 측정'),
    ('General', '신체 계측'), ('General', '성장도표 백분위수 확인'), ('General', '중간부모키 산출'),
    ('General', '신체 비율 평가'), ('Others', '사춘기 성숙도 평가'),
    ('H/E/E/N/T', '결막·공막 시진'), ('H/E/E/N/T', '동공 대광반사 확인'), ('H/E/E/N/T', '외안근 운동 검사'),
    ('H/E/E/N/T', '갑상선 안징후 검사'), ('H/E/E/N/T', '안구진탕 확인'), ('H/E/E/N/T', '고막 이경 검사'),
    ('H/E/E/N/T', '인두·편도 시진'), ('H/E/E/N/T', '구강 점막 시진'), ('H/E/E/N/T', '부비동 압통 확인'),
    ('H/E/E/N/T', '안면 기형 소견 시진'),
    ('Neck', '갑상선 촉진'), ('Neck', '갑상선 잡음 청진'), ('Neck', '경부 림프절 촉진'),
    ('Neck', '경부 강직 확인'), ('Neck', '경정맥 확장 확인'),
    ('Chest', '흉곽 시진'), ('Chest', '폐 청진'), ('Chest', '흉부 타진'), ('Chest', '심음 청진'),
    ('Chest', '유방 촉진'),
    ('Abdomen', '복부 시진'), ('Abdomen', '장음 청진'), ('Abdomen', '복부 촉진'), ('Abdomen', '복부 타진'),
    ('Abdomen', '간·비장 촉진'), ('Abdomen', '반발통 확인'), ('Abdomen', '머피 징후 확인'),
    ('Abdomen', '맥버니점 압통 확인'), ('Abdomen', '늑척추각 압통 확인'), ('Abdomen', '서혜부 탈장 확인'),
    ('Abdomen', '직장수지검사'),
    ('Back', '척추 압통 확인'), ('Back', '하지직거상 검사'),
    ('Extremities', '요골동맥 맥박 촉진'), ('Extremities', '하지 말초 진찰'), ('Extremities', '관절 부종·압통 확인'),
    ('Extremities', '경골앞 점액부종 확인'), ('Extremities', '손톱 곤봉지 확인'),
    ('Neuro', '사지 근력 검사'), ('Neuro', '심부건반사 검사'), ('Neuro', '사지 감각 검사'),
    ('Neuro', '바빈스키 반사 확인'), ('Neuro', '자세성 떨림 확인'), ('Neuro', '안정시 떨림 확인'),
    ('Neuro', '소뇌 협조운동 검사'), ('Neuro', '롬베르그 검사'), ('Neuro', '보행 관찰'), ('Neuro', '구음장애 확인'),
    ('Skin', '피부 온도·발한 촉진'), ('Skin', '피부 발진 시진'), ('Skin', '자주색 선조 시진'), ('Skin', '피부 긴장도 확인'),
]
EXAM_MENU_TEXT = '\n'.join(f'{i}. {name} ({region})' for i, (region, name) in enumerate(EXAM_MENU))


def log(*args):
    print('[agent]', *args, file=sys.stderr, flush=True)


# ---------------------------------------------------------------- 프롬프트

ROLE = ('당신은 한국 대학병원 외래의 숙련된 의사입니다. 가상 환자를 CPX(임상수행평가) 방식으로 초진합니다. '
        '환자 말은 짧으니 질문은 한 번에 하나만, 쉬운 존댓말로 합니다.')

QUESTION_RULES = f"""질문 작성 규칙
- 질문 하나에 확인할 내용 하나. 여러 항목을 한꺼번에 묻지 않습니다("다 알려 주세요" 금지).
- 각 질문은 공백 포함 {MAX_CHARS - 5}자 이내의 자연스러운 한국어 존댓말 의문문.
- 이미 물었거나 환자가 이미 말한 내용은 다시 묻지 않습니다.
- 환자가 말한 단서는 구체화합니다. 약이면 이름·용량·횟수·늘어난 경과, 증상이면 시작·빈도·정도.
- 문법이 바른 짧은 일상어로 씁니다. 좋은 예: "하루에 몇 알 드세요?", "언제부터 그러셨어요?", "열은 없으셨어요?"
- 환자가 소아이고 보호자가 답하면 "아이가 ~"처럼 보호자에게 묻습니다."""

PLAN_PROMPT = f"""{ROLE}
진료 시작 정보(환자 첫 진술, 활력징후)를 보고 초진 계획을 세웁니다. JSON 객체 하나만 출력하세요.
{{"age": 나이(정수, 모르면 null), "sex": "M" 또는 "F" 또는 null, "child": 만 15세 미만이면 true,
 "informant": "본인" 또는 "보호자",
 "chief_complaint": "주호소 한 줄",
 "differential": ["가능성 높은 순 감별진단 3~5개"],
 "questions": ["현병력 질문 8개를 묻는 순서대로"]}}
현병력 질문은 주호소에 맞춰 시작 시점·경과, 양상, 위치·방사, 정도, 악화·완화 요인, 동반 증상, 이전 진료·치료, 일상 영향 중
첫 진술에 아직 없는 것을 고르고, 감별진단을 가르는 핵심 위험 징후 질문을 1~2개 넣습니다.
첫 진술에 담긴 요청(예: 특정 약 처방 요구)과 단서는 감별진단과 질문에 반드시 반영합니다.
{QUESTION_RULES}"""

FOLLOW_PROMPT = f"""{ROLE}
지금까지의 진료 기록을 보고 다음 문진을 계획합니다. JSON 객체 하나만 출력하세요.
{{"top3": [{{"dx": "가장 가능성 높은 진단 1", "discriminator": "이 진단을 나머지 둘과 가르는 핵심 질문(환자에게 할 문장)"}},
          {{"dx": "진단 2", "discriminator": "..."}}, {{"dx": "진단 3", "discriminator": "..."}}],
 "differential": ["가능성 높은 순 감별진단 3~5개 (top3를 앞에)"],
 "covered": ["아래 기본 항목 중 환자가 이미 답한 항목의 키"],
 "questions": ["다음에 물을 질문들, 중요한 순서대로"]}}
먼저 지금까지의 사실로 가장 가능성 높은 진단 3개를 정하고, 각각을 나머지와 가르는 질문을 만드세요.
그 감별 질문(discriminator)들은 questions 앞쪽에 반드시 포함합니다(이미 확인된 것은 제외).
{QUESTION_RULES}"""

FOLLOW_HPI_TASK = """이번 단계: 현병력 보완. 아직 확인하지 않은 현병력 요소(시작·경과, 양상, 위치, 정도, 악화·완화, 동반 증상,
이전 진료·약 복용)와 놓치면 위험한 위험 징후를 묻는 질문을 최대 {n}개 만드세요. 과거력·가족력·사회력은 다음 단계에서 묻습니다."""

FOLLOW_ROS_TASK = """이번 단계: 감별 문진과 신체 진찰 계획.
1) "questions": 감별진단끼리를 가르는 계통 문진(증상 유무) 질문을 최대 {n}개. 이미 확인한 것은 빼세요.
2) "exam_ids": 아래 진찰 메뉴에서 감별에 필요한 진찰 번호를 중요한 순서로 최대 {m}개.
   주호소와 감별진단에 관련된 부위를 우선하고, 관련 없는 부위는 고르지 않습니다. 활력징후는 이미 있습니다.
3) "extra_exams": 메뉴에 꼭 필요한 진찰이 없을 때만 최대 2개. {{"content": "진찰 동작 하나(예: 어깨 관절 운동범위 검사하겠습니다)",
   "region": "General·H/E/E/N/T·Neck·Chest·Abdomen·Back·Extremities·Neuro·Skin·Others 중 하나"}}, content는 공백 포함 {max_chars}자 이내.
   진찰 동작 하나만 쓰고, 혈액·영상 검사는 넣지 않습니다.

진찰 메뉴
""" + EXAM_MENU_TEXT


ASSESS_PROMPT = f"""{ROLE}
진료가 끝났습니다. 진료 기록(문진·진찰 결과)만 근거로 평가와 계획을 세웁니다. JSON 객체 하나만 출력하세요.
{{"diagnosis": "주진단 하나. '한국어 진단명 (English name)' 형식",
 "evidence": "#1. 주진단\\n- 근거 : 확인한 사실 → 해석\\n- 근거 : ... (3~5줄, 문진·진찰 턴의 실제 사실만)",
 "differential": "r/o 진단명 : 이 진단을 지지·반대하는 확인된 사실과 남은 확인 방법\\n를 3~5줄",
 "tests": "- 검사명 : 이유 (한 줄에 하나, 감별진단 확인에 필요한 혈액·영상·기타 검사)",
 "treatment": "- 약물·비약물 치료 계획 (구체적으로)",
 "disposition": "- 귀가/외래 추적/전문과 의뢰/응급 처치 등 결정과 그 이유",
 "follow_up": "- 재진 시점과 확인할 것\\n- 바로 다시 와야 하는 경고 증상",
 "education": "- 환자에게 설명할 내용(질환, 검사·치료 계획, 생활 수칙, 경고 증상)",
 "closing": ["환자에게 실제로 말할 설명 문장 3~4개"]}}
규칙
- 주진단은 가장 가능성 높은 하나. 근거는 대화와 진찰에서 실제로 확인한 사실만 씁니다.
- 예선에서는 검사를 시행하지 않았으므로 검사 결과를 지어내지 않고, 필요한 검사는 계획(tests)으로만 씁니다.
- closing 문장은 각각 공백 포함 {MAX_CHARS - 2}자 이내의 쉬운 존댓말. 순서대로 ①공감·가능성 높은 진단
  ②필요한 검사·치료 계획 ③바로 와야 하는 경고 증상 ④환자가 걱정한 점에 대한 답이나 생활 수칙.
  의학 용어는 쉬운 말로 바꿉니다."""

SUBJECTIVE_PROMPT = """진료 기록만 근거로 초진 기록의 S(주관적 정보) 칸을 작성합니다. JSON 객체 하나만 출력하세요.
{"cc": "C.C : 주호소\\nOnset : 시작 시점\\n통증평가 : NRS 점수, 부위, 양상, 기간 (통증이 아니면 '해당 없음')",
 "hpi": "나이·성별. 시작, 경과, 양상, 악화·완화 요인, 동반 증상, 이전 진료·약물, 일상 영향, 환자 걱정을 시간 순서로 간결하게",
 "pmh": "DM / HTN ( / )\\nprevious stroke ( )\\nTbc / hepatitis ( / )\\nheart disease ( )  dyslipidemia ( )\\nOp. Hx ( )\\nMedicine history : \\nAllergy ( )\\nOthers : ",
 "fh": "DM / HTN ( / )\\nStroke ( )\\nOthers : ",
 "sh": "Smoking ( ) \\nAlcohol ( ) \\nOthers : 직업, 동거인 등",
 "ros": "General weakness ( )  Fatigue ( )\\nHeadache ( )  Dizziness ( )\\nChest pain ( )  Palpitation ( )\\nFever/Chill/Cough/Sputum/Rhinorrhea ( / / / / )\\nAbdominal pain ( )  Melena ( )  Hematochezia ( )  Hematemesis ( )\\nAnorexia/Nausea/Vomiting/Diarrhea/Constipation ( / / / / )\\nOthers : 위 목록에 없는 확인한 증상들 (+)/(-)"}
규칙
- 위 틀의 항목 순서와 표기를 그대로 쓰고, 괄호 안에는 대화로 확인한 경우에만 + 또는 -를 적습니다.
- 묻지 않았거나 환자가 답하지 않은 항목은 괄호를 비워 둡니다( ). 추측해서 -로 채우지 않습니다.
- 환자가 말한 내용과 다르게 쓰지 않습니다. 숫자·약 이름·기간은 환자 표현 그대로 옮깁니다.
- 시작 정보(첫 진술)는 확인된 사실입니다. 활력징후는 S에 쓰지 않습니다.
- 소아는 보호자 진술임을 hpi 첫머리에 밝히고, 출생·발달·예방접종 등은 pmh의 Others에 적습니다.
- 모든 값은 한국어 문자열(줄바꿈은 \\n)."""

ANSWER_PROMPT = f"""{ROLE}
진료를 마무리하며 진단과 계획을 설명했습니다. 환자의 마지막 말에 답합니다. JSON 객체 하나만 출력하세요.
{{"reply": "공백 포함 {MAX_CHARS - 2}자 이내의 쉬운 존댓말 답 한 문장"}}
진단·계획과 어긋나지 않게 답하고, 질문이 없으면 "더 궁금한 점 있으면 언제든 오세요."처럼 마무리합니다."""


# ---------------------------------------------------------------- 기본 문진(규칙)

def core_questions(patient):
    """과거력·약물·알레르기·가족력·사회력. (키, 질문) 목록. 키는 FOLLOW 단계에서 '이미 답함' 판정에 씁니다."""
    if patient.get('child'):
        items = [
            ('pmh', '아이가 앓았던 병이 있나요?'),
            ('admission', '아이가 입원한 적 있나요?'),
            ('med', '아이가 먹고 있는 약이 있나요?'),
            ('allergy', '아이가 알레르기가 있나요?'),
            ('birth', '출생 때 특별한 문제 있었나요?'),
            ('development', '발달은 또래와 비슷했나요?'),
            ('vaccine', '예방접종은 다 맞았나요?'),
            ('fh', '가족 중에 앓는 병이 있나요?'),
            ('social', '어린이집이나 학교생활은 어떤가요?'),
            ('concern', '가장 걱정되시는 점이 뭔가요?'),
        ]
    else:
        items = [
            ('pmh_chronic', '고혈압이나 당뇨 있으세요?'),
            ('pmh_other', '그 밖에 앓으신 병이 있나요?'),
            ('op', '수술받으신 적 있으세요?'),
            ('med', '지금 드시는 약이 있으세요?'),
            ('allergy', '약 알레르기 있으세요?'),
            ('fh', '가족 중에 앓는 병이 있나요?'),
            ('smoking', '담배는 피우세요?'),
            ('alcohol', '술은 얼마나 드세요?'),
            ('job', '하시는 일이 어떻게 되세요?'),
        ]
        age = patient.get('age')
        if patient.get('sex') == 'F' and (age is None or 12 <= age <= 55):
            items += [('lmp', '마지막 생리는 언제였나요?'), ('pregnancy', '임신 가능성이 있으세요?')]
        items.append(('concern', '가장 걱정되시는 점이 뭔가요?'))
    return items


# ---------------------------------------------------------------- 공통 도구

def parse_json(text):
    """모델 출력에서 첫 JSON 객체를 꺼냅니다(코드 블록이나 앞뒤 설명이 붙어도 됩니다)."""
    decoder = json.JSONDecoder()
    for match in re.finditer(r'\{', text or ''):
        try:
            value, _ = decoder.raw_decode(text, match.start())
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def with_retry(call, *args, **kwargs):
    """일시 오류는 잠시 뒤 다시 시도합니다. 실패한 요청은 턴을 쓰지 않고, 재시도는 새 요청으로 보냅니다."""
    for wait in (2, 5, 10, None):
        try:
            return call(*args, **kwargs)
        except NovaError as exc:
            if exc.code not in RETRY_CODES or wait is None:
                raise
            time.sleep(wait)


def nfc(text):
    return unicodedata.normalize('NFC', str(text or '')).strip()


def fits(text):
    return 0 < len(nfc(text)) <= MAX_CHARS


def key_of(text):
    """중복 질문 판정용: 공백·문장부호를 뺀 형태."""
    return re.sub(r'[\s\W_]+', '', nfc(text))


def text_value(value):
    if isinstance(value, list):
        return '\n'.join(map(str, value))
    return '' if value is None else str(value)


class Doctor:
    """client.chat 래퍼. 호출 수·토큰을 세어 한도 전에 멈춥니다."""

    def __init__(self, client):
        self.client = client
        self.calls = self.input_tokens = self.output_tokens = 0
        self.token_cap = 8192   # TOKEN_LIMIT_EXCEEDED를 받으면 절반씩 줄여 기억합니다.
        self.failures = 0       # 연속 실패 횟수
        self.broken = False     # 인증 오류·호출 한도로 더 부를 수 없음

    def available(self):
        return (not self.broken and self.calls < CALL_LIMIT
                and self.input_tokens < INPUT_LIMIT and self.output_tokens < OUTPUT_LIMIT)

    def ask(self, system, user, *, max_tokens=4096, effort='medium', temperature=None):
        messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]
        extra = {} if temperature is None else {'temperature': temperature}
        while True:
            if not self.available():
                raise NovaError('MODEL_CALL_LIMIT')
            self.calls += 1
            try:
                completion = with_retry(self.client.chat, messages, max_tokens=min(max_tokens, self.token_cap),
                                        reasoning_effort=effort, **extra)
                break
            except NovaError as exc:
                if exc.code != 'TOKEN_LIMIT_EXCEEDED' or self.token_cap <= 1024:
                    raise
                self.token_cap = min(max_tokens, self.token_cap) // 2
                log('max_tokens 축소', self.token_cap)
        usage = completion.get('usage') or {}
        self.input_tokens += int(usage.get('prompt_tokens') or 0)
        self.output_tokens += int(usage.get('completion_tokens') or 0)
        return completion['choices'][0]['message']['content'] or ''

    def ask_json(self, system, user, *, check=None, tries=3, **kwargs):
        """JSON 객체를 받을 때까지 최대 tries번. check(result)가 거짓이면 다시 요청. 끝내 실패하면 {}."""
        for _ in range(tries):
            try:
                result = parse_json(self.ask(system, user, **kwargs))
            except NovaError as exc:
                log('chat 실패', exc.code)
                self.failures += 1
                # 인증·한도 오류나 연속 실패면 이후 호출을 멈추고, 그 밖의 오류는 이번 요청만 포기합니다.
                if exc.code in FATAL_CHAT_CODES or exc.status in (401, 403) or self.failures >= 3:
                    self.broken = True
                return {}
            self.failures = 0
            if result and (check is None or check(result)):
                return result
            user += '\n(직전 출력이 형식에 맞지 않았습니다. 설명 없이 JSON 객체 하나만 출력하세요.)'
        return {}


# ---------------------------------------------------------------- 진료 상태

class Visit:
    def __init__(self, client, session):
        self.client = client
        self.doctor = Doctor(client)
        self.session = session
        self.initial = session['initial']
        self.turns_total = int(session.get('turns_remaining') or MAX_TURNS)
        self.turns_left = min(MAX_TURNS, self.turns_total)
        self.log = []          # 진료 기록 줄(턴 번호 포함)
        self.exams = []        # (턴, 부위, 진찰, 결과)
        self.asked = set()     # 보낸 질문·진찰의 key_of
        self.stopped = False   # 턴·세션 종료로 더 행동할 수 없음
        self.patient = {}
        self.differential = []

    # ---- 시간·턴
    def seconds_left(self):
        deadline = self.session.get('deadline')
        if not deadline:
            return float('inf')
        return datetime.fromisoformat(deadline).timestamp() - time.time()

    def can_act(self, reserve=0):
        return not self.stopped and self.turns_left > reserve and self.seconds_left() > TIME_MARGIN

    def turn_no(self):
        return self.turns_total - self.turns_left

    # ---- 진료 기록 문자열
    def opening(self):
        vitals = self.initial.get('vital_signs')
        if isinstance(vitals, dict):
            vitals = ', '.join(f'{k}: {v}' for k, v in vitals.items())
        return f"시작 정보\n첫 진술: {self.initial.get('opening', '')}\n활력징후: {vitals}"

    def situation(self):
        return self.opening() + '\n\n진료 기록\n' + ('\n'.join(self.log) or '(아직 없음)')

    # ---- 행동
    def _act(self, action, content):
        """행동 하나를 보내고 결과 dict, 거절이면 None. 거절이 아닌 오류(턴·세션 종료, 인증 오류 등)면 stopped."""
        try:
            reply = with_retry(self.client.say if action == 'SAY' else self.client.exam, content)
        except NovaError as exc:
            if exc.code not in REFUSED_CODES:
                log(action, '중단', exc.code)
                self.stopped = True
                return None
            # EXAM_NOT_SPECIFIC·EXAM_NOT_RECOGNIZED·CONTENT_TOO_LONG 등: 답은 없지만 1턴을 씁니다.
            self.turns_left -= 1
            self.log.append(f'[턴 {self.turn_no()}] ({action} "{content}" 거절: {exc.code})')
            log(action, '거절', exc.code, content)
            return None
        remaining = reply.get('turns_remaining')
        self.turns_left = min(self.turns_left - 1, remaining if isinstance(remaining, int) else self.turns_left)
        return reply

    def say(self, content):
        content = nfc(content)
        if not fits(content) or not self.can_act():
            return None
        self.asked.add(key_of(content))
        reply = self._act('SAY', content)
        if reply is None:
            return None
        answer = nfc(reply.get('content'))
        self.log.append(f'[턴 {self.turn_no()}] 의사: {content} / 환자: {answer}')
        log(f'T{self.turn_no()} SAY', content, '→', answer)
        return answer

    def exam(self, content, region='Others'):
        content = nfc(content)
        if not fits(content) or not self.can_act(RESERVE_CLOSING):
            return None
        self.asked.add(key_of(content))
        reply = self._act('EXAM', content)
        if reply is None:
            return None
        result = nfc(reply.get('result'))
        self.log.append(f'[턴 {self.turn_no()}] 진찰({content}): {result}')
        self.exams.append((self.turn_no(), region if region in EXAM_REGIONS else 'Others', content, result))
        log(f'T{self.turn_no()} EXAM', content, '→', result)
        return result

    def ask_all(self, questions, limit, reserve=RESERVE_CLOSING):
        """질문 목록을 순서대로 보냅니다(30자 초과·중복은 건너뜀). 보낸 개수."""
        sent = 0
        for question in questions:
            if sent >= limit or not self.can_act(reserve):
                break
            question = nfc(question)
            if not fits(question) or key_of(question) in self.asked:
                continue
            if self.say(question) is not None:
                sent += 1
        return sent

    # ---- LLM 계획
    def plan(self):
        result = self.doctor.ask_json(PLAN_PROMPT, self.opening() + '\n\n초진 계획:',
                                      check=lambda r: isinstance(r.get('questions'), list))
        self.patient = {
            'age': result.get('age') if isinstance(result.get('age'), int) else None,
            'sex': result.get('sex') if result.get('sex') in ('M', 'F') else None,
            'child': bool(result.get('child')),
        }
        self.differential = [str(d) for d in result.get('differential') or []]
        log('계획', self.patient, self.differential)
        questions = [nfc(q) for q in result.get('questions') or [] if isinstance(q, str)]
        return questions or ['언제부터 그러셨어요?', '처음 시작은 어땠나요?', '점점 심해지고 있나요?',
                             '같이 나타나는 증상이 있나요?', '병원에서 치료받은 적 있나요?']

    def follow(self, task, keys=()):
        core = ', '.join(f'{k}({q})' for k, q in keys) or '(없음)'
        result = self.doctor.ask_json(FOLLOW_PROMPT + '\n\n' + task + f'\n\n기본 항목 키: {core}',
                                      self.situation() + '\n\n다음 계획:',
                                      check=lambda r: isinstance(r.get('questions'), list))
        if result.get('differential'):
            self.differential = [str(d) for d in result['differential']]
        # top3의 감별 질문을 questions 맨 앞에 둡니다.
        disc = [nfc(t.get('discriminator')) for t in result.get('top3') or []
                if isinstance(t, dict) and t.get('discriminator')]
        if disc:
            rest = [q for q in result.get('questions') or [] if isinstance(q, str)]
            result['questions'] = disc + [q for q in rest if key_of(q) not in {key_of(d) for d in disc}]
            log('top3', [t.get('dx') for t in result.get('top3') if isinstance(t, dict)])
        return result


# ---------------------------------------------------------------- 진료 단계

def prepare():
    # 본선: 등록한 로컬 모델을 여기서 불러옵니다(증례 접근 전, 인터넷 없음).
    return None


def consult(client, model):
    visit = Visit(client, client.session())

    # 1. 계획 + 인사를 겸한 첫 현병력 질문
    questions = visit.plan()
    first = questions[0] if questions else '언제부터 그러셨어요?'
    greeting = '안녕하세요. ' + first
    if fits(greeting):
        questions[0] = greeting
    visit.ask_all(questions, BUDGET['hpi'])

    # 2. 현병력 보완(위험 징후 포함)
    core = core_questions(visit.patient)
    if visit.can_act(RESERVE_CLOSING) and visit.doctor.available():
        result = visit.follow(FOLLOW_HPI_TASK.format(n=BUDGET['hpi_more']), core)
        covered = {str(k) for k in result.get('covered') or []}
        visit.ask_all(result.get('questions') or [], BUDGET['hpi_more'])
    else:
        covered = set()

    # 3. 과거력·약물·알레르기·가족력·사회력(규칙)
    # 진찰과 설명을 위한 턴을 남겨 둡니다.
    reserve = RESERVE_CLOSING + min(6, BUDGET['exam'])
    visit.ask_all([q for k, q in core if k not in covered], BUDGET['core'], reserve=reserve)

    # 4. 감별 문진 + 신체 진찰
    if visit.can_act(RESERVE_CLOSING) and visit.doctor.available():
        result = visit.follow(FOLLOW_ROS_TASK.format(n=BUDGET['ros'], m=BUDGET['exam'], max_chars=MAX_CHARS - 4))
        exams = pick_exams(result)
        visit.ask_all(result.get('questions') or [], BUDGET['ros'], reserve=RESERVE_CLOSING + min(len(exams), 6))
        for region, content in exams[:BUDGET['exam']]:
            if not visit.can_act(RESERVE_CLOSING):
                break
            if key_of(content) not in visit.asked:
                visit.exam(content, region)

    # 5. 평가·계획
    assessment = assess(visit)

    # 6. 환자 설명과 질문 응답
    explain(visit, assessment)

    # 7. 기록 작성·제출
    note = build_record(visit, assessment)
    diagnosis = ' '.join(str(assessment.get('diagnosis') or '').split())
    diagnosis = diagnosis or (visit.differential[0] if visit.differential else '진단 미정')
    log('주진단', diagnosis, f'(턴 {visit.turn_no()}, chat {visit.doctor.calls}회,',
        f'토큰 {visit.doctor.input_tokens}/{visit.doctor.output_tokens})')
    return client.diagnose(note=note, diagnosis=diagnosis.encode('utf-8')[:500].decode('utf-8', 'ignore'))


def pick_exams(result):
    """FOLLOW_ROS 결과 → [(부위, 진찰 문장)]. 메뉴 번호를 우선하고, 전반적 외관 시진을 맨 앞에 둡니다."""
    ids = [0]
    for i in result.get('exam_ids') or []:
        try:
            i = int(i)
        except (TypeError, ValueError):
            continue
        if 0 <= i < len(EXAM_MENU) and i not in ids:
            ids.append(i)
    exams = [(EXAM_MENU[i][0], EXAM_MENU[i][1] + '하겠습니다') for i in ids]
    for item in (result.get('extra_exams') or [])[:2]:
        # 묶음 진찰은 EXAM_NOT_SPECIFIC으로 턴만 쓰므로 미리 거릅니다.
        if isinstance(item, dict) and fits(item.get('content')) and not re.search(r'전부|모두|전체|다 해|[,및]', nfc(item['content'])):
            exams.append((str(item.get('region') or 'Others'), nfc(item['content'])))
    return exams


DX_PROMPT = f"""{ROLE}
진료가 끝났습니다. 진료 기록(문진·진찰 결과)만 근거로 가장 가능성 높은 주진단 하나를 정합니다. JSON 객체 하나만 출력하세요.
{{"diagnosis_ko": "한국어 진단명", "diagnosis_en": "English diagnosis name",
 "confidence": 0~1 사이 숫자, "differentials": ["주진단 외 감별진단 3~5개"]}}
규칙
- 증상명이 아니라 가능한 한 구체적인 질환명(원인·유형 포함)으로 씁니다.
- 첫 진술의 요청·단서, 위험 징후, 진찰 소견을 모두 설명하는 진단을 고릅니다."""

DXDOC_PROMPT = f"""{ROLE}
주진단이 확정되었습니다. 진료 기록에 실제로 있는 사실만 인용해 A 칸의 근거와 감별을 작성합니다. JSON 객체 하나만 출력하세요.
{{"evidence": "#1. 주진단명\\n- 근거 : 수집한 사실 → 해석\\n- 근거 : ... (근거 줄 3~5개)",
 "differential": "r/o 진단명 : 어떤 소견으로 가능성이 낮은지 + 감별 검사\\n... (3~5줄)"}}
규칙
- evidence 근거는 문진·진찰에서 실제로 확인한 사실(양성·음성 모두)만 씁니다. 검사 결과를 지어내지 않습니다.
- differential의 각 줄은 반드시 'r/o '로 시작하고 ' : '를 포함합니다. 주어진 감별진단을 우선 사용합니다."""


def _norm_dx(text):
    text = re.sub(r'\([^)]*\)|\[[^\]]*\]', '', nfc(text))
    return re.sub(r'[\s\W_]+', '', text).lower()


def _conf(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.5


def vote_diagnosis(visit, n=3):
    """주진단을 high·temperature 0.7로 n회 독립 샘플링해 다수결(동률은 confidence 합)."""
    samples = []
    for _ in range(n):
        if not visit.doctor.available() or visit.doctor.broken:
            break
        r = visit.doctor.ask_json(DX_PROMPT, visit.situation() + '\n\n주진단:',
                                  check=lambda r: str(r.get('diagnosis_ko') or r.get('diagnosis_en') or '').strip(),
                                  tries=2, max_tokens=6000, effort='high', temperature=0.7)
        if r:
            samples.append(r)
    if not samples:
        return None
    groups = {}
    for r in samples:
        key = _norm_dx(r.get('diagnosis_ko') or r.get('diagnosis_en'))
        g = groups.setdefault(key, {'count': 0, 'conf': 0.0, 'best': r, 'best_conf': -1.0, 'diffs': []})
        g['count'] += 1
        c = _conf(r.get('confidence'))
        g['conf'] += c
        if c > g['best_conf']:
            g['best'], g['best_conf'] = r, c
        g['diffs'] += [str(d) for d in r.get('differentials') or [] if d]
    win = max(groups.values(), key=lambda g: (g['count'], g['conf']))
    best = win['best']
    ko = ' '.join(str(best.get('diagnosis_ko') or '').split())
    en = ' '.join(str(best.get('diagnosis_en') or '').split())
    ko = re.sub(r'\s*\([^)]*\)\s*$', '', ko) or en
    dx = f'{ko} ({en})' if en and en.lower() not in ko.lower() else ko
    # 감별: 다른 표를 받은 진단 + 승자 샘플들의 감별, 중복 제거
    diffs, seen = [], {_norm_dx(ko)}
    others = [g['best'].get('diagnosis_ko') or g['best'].get('diagnosis_en') for g in groups.values() if g is not win]
    for d in others + win['diffs'] + [d for g in groups.values() for d in g['diffs']]:
        k = _norm_dx(d)
        if k and k not in seen:
            seen.add(k)
            diffs.append(str(d))
    log('투표', {k: g['count'] for k, g in groups.items()}, '→', dx)
    return {'diagnosis': dx, 'differentials': diffs[:5]}


def _diff_ok(text):
    lines = [l.strip() for l in text_value(text).split('\n') if l.strip()]
    return len(lines) >= 2 and all(l.startswith('r/o ') and ' : ' in l for l in lines)


def write_dx_docs(visit, dx, diffs):
    """확정 진단으로 evidence·differential을 high로 다시 작성. differential 형식이 틀리면 1회 재요청."""
    user = (visit.situation() + f'\n\n확정 주진단: {dx}\n감별진단 후보: {", ".join(diffs) or "(스스로 정함)"}'
            '\n\nevidence와 differential:')
    r = visit.doctor.ask_json(DXDOC_PROMPT, user, check=lambda r: r.get('evidence') and r.get('differential'),
                              tries=2, max_tokens=6000, effort='high')
    if r and not _diff_ok(r.get('differential')) and visit.doctor.available():
        r2 = visit.doctor.ask_json(DXDOC_PROMPT, user + "\n(직전 differential 형식 오류: 각 줄을 'r/o 진단명 : 설명' 형식으로 쓰세요.)",
                                   check=lambda x: _diff_ok(x.get('differential')), tries=1,
                                   max_tokens=6000, effort='high')
        if r2:
            r['differential'] = r2['differential']
            if r2.get('evidence'):
                r['evidence'] = r2['evidence']
    if r and not _diff_ok(r.get('differential')):
        # 코드로 형식 보정
        fixed = []
        for l in text_value(r.get('differential')).split('\n'):
            l = l.strip().lstrip('-•* ').strip()
            if not l:
                continue
            if not l.lower().startswith('r/o'):
                l = 'r/o ' + l
            elif not l.startswith('r/o '):
                l = 'r/o ' + l[3:].lstrip()
            if ' : ' not in l:
                l = re.sub(r'\s*[:：]\s*', ' : ', l, count=1) if re.search(r'[:：]', l) else l + ' : 추가 검사로 감별'
            fixed.append(l)
        r['differential'] = '\n'.join(fixed)
    return r


def assess(visit):
    voted = vote_diagnosis(visit)
    result = visit.doctor.ask_json(ASSESS_PROMPT, visit.situation()
                                   + (f"\n\n확정 주진단: {voted['diagnosis']}" if voted else '') + '\n\n평가와 계획:',
                                   check=lambda r: str(r.get('diagnosis') or '').strip(),
                                   max_tokens=6000, effort='high')
    if not result:  # high가 실패하면 medium으로 한 번 더
        result = visit.doctor.ask_json(ASSESS_PROMPT, visit.situation() + '\n\n평가와 계획:',
                                       check=lambda r: str(r.get('diagnosis') or '').strip(), tries=2)
    result = result or {}
    if voted:
        result['diagnosis'] = voted['diagnosis']
        if visit.doctor.available():
            docs = write_dx_docs(visit, voted['diagnosis'], voted['differentials'])
            for field in ('evidence', 'differential'):
                if docs and str(docs.get(field) or '').strip():
                    result[field] = text_value(docs[field])
    return result


def explain(visit, assessment):
    lines = [nfc(s) for s in assessment.get('closing') or [] if isinstance(s, str)]
    lines = [s for s in lines if fits(s)][:BUDGET['closing'] - 1]
    if not lines and assessment.get('diagnosis'):
        lines = ['검사 결과를 보고 다시 설명드릴게요.']
    for line in lines:
        if not visit.can_act():
            return
        visit.say(line)
    answer = visit.say('혹시 궁금하신 점 있으세요?')
    for _ in range(BUDGET['qa']):
        if not answer or not visit.can_act() or not visit.doctor.available():
            return
        if not re.search(r'[?？]|까요|나요|가요|어요\?|궁금|걱정|어떻게|언제|괜찮', answer) or re.search(r'없어요|없습니다|괜찮아요', answer):
            return
        reply = visit.doctor.ask_json(
            ANSWER_PROMPT,
            visit.situation() + f"\n\n주진단: {assessment.get('diagnosis', '')}\n계획: {text_value(assessment.get('treatment'))}"
            f"\n{text_value(assessment.get('disposition'))}\n\n환자에게 할 답:",
            check=lambda r: fits(r.get('reply')), tries=2)
        if not reply:
            return
        answer = visit.say(reply['reply'])


def build_record(visit, assessment):
    note = empty_record()

    # S: 대화만 근거로 LLM 작성
    subjective = visit.doctor.ask_json(SUBJECTIVE_PROMPT, visit.situation() + '\n\nS 칸:',
                                       check=lambda r: any(r.get(f) for f in RECORD_FIELDS['S']))
    for field in RECORD_FIELDS['S']:
        note['S'][field] = text_value(subjective.get(field))
    if not any(note['S'].values()):
        note['S']['hpi'] = '\n'.join(visit.log)

    # O: 받은 진찰 결과를 그대로 옮깁니다(지어낼 여지 없음).
    vitals = visit.initial.get('vital_signs')
    if isinstance(vitals, dict):
        vitals = ', '.join(f'{k} {v}' for k, v in vitals.items())
    lines = [f"V/S : {' '.join(str(vitals or '').split())}"]
    for region in EXAM_REGIONS:
        found = [f'{label(content)} - {result} (턴 {turn})' for turn, r, content, result in visit.exams if r == region]
        if found:
            lines.append(f'{region} : ' + '; '.join(found))
    note['O']['exam'] = '\n'.join(lines)
    note['O']['tests'] = ''  # 예선은 검사 없음

    # A·P: 평가 단계 결과
    for section in ('A', 'P'):
        for field in RECORD_FIELDS[section]:
            note[section][field] = text_value(assessment.get(field))
    return note


def label(content):
    """'갑상선 촉진하겠습니다' → '갑상선 촉진'."""
    return re.sub(r'\s*(을|를)?\s*(하겠습니다|할게요|해 볼게요|해보겠습니다|해 보겠습니다|보겠습니다|확인하겠습니다)[.!]?$', '',
                  content).strip() or content


if __name__ == '__main__':
    run_agent(prepare, consult)

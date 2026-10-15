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
{{"differential": ["가능성 높은 순 감별진단 3~5개"],
 "covered": ["아래 기본 항목 중 환자가 이미 답한 항목의 키"],
 "questions": ["다음에 물을 질문들, 중요한 순서대로"]}}
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


SCREEN_PROMPT = f"""{ROLE}
주호소와 감별진단에 맞춰, 응급 평가가 필요한 위험 징후(예: 흉통, 호흡곤란, 의식 변화, 실신, 토혈·흑색변,
마비·구음장애, 고열·경부강직, 자살 생각 등)를 확인하는 선별 질문 3개를 고릅니다. JSON 객체 하나만 출력하세요.
{{"questions": ["예/아니오로 답할 수 있는 질문 3개"]}}
{QUESTION_RULES}"""

PLAN_P_PROMPT = f"""{ROLE}
진료가 끝났습니다. 확정 진단·감별진단·진료 기록(문진·진찰)을 근거로 초진 기록의 P(계획) 칸만 작성합니다. JSON 객체 하나만 출력하세요.
{{"tests": [{{"name": "검사명", "reason": "이 검사로 확인·배제할 진단 또는 목적"}}] (5~8개),
 "treatment": ["치료 계획 항목"],
 "disposition": "귀가/외래 추적/전문과 의뢰/응급 평가 중 결정과 그 이유",
 "follow_up": {{"when": "재진 시점(예: 검사 결과 확인 위해 1주 후)", "warning_signs": ["즉시 내원해야 할 경고 증상 3개 이상"], "monitoring": "재진 때 확인·추적할 것"}},
 "education": ["환자 교육 항목"]}}
규칙
- tests: 주진단 확인 검사와 각 감별진단을 가르는 검사를 모두 포함. 적응증이 있으면 기본 혈액검사(CBC, LFT, RFT, 전해질, 혈당, 소변검사 등)와
  영상·심전도 등을 넣습니다. 예선은 검사를 시행하지 않았으므로 결과를 지어내지 않습니다.
- treatment: 검사로 확진되기 전이므로 특정 용량(mg 등)을 쓰지 말고 "검사 결과 확인 후 ○○ 고려"처럼 조건부로 씁니다.
  복용 중인 약은 임의로 갑자기 끊지 않도록 하고, 새 약은 금기·상호작용·알레르기 확인 후 시작한다고 명시합니다. 대증·비약물 치료를 포함합니다.
- disposition: 활력징후 안정/불안정 여부와 입원 필요/불필요 근거를 반드시 포함합니다.
- education: 질환 설명, 검사·치료 계획, 생활 수칙, 복약 순응, 경고 증상 시 즉시 내원을 포함합니다.
- 모든 값은 한국어. 문자열 안에 줄바꿈 문자를 넣지 않습니다."""


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

    def ask(self, system, user, *, max_tokens=4096, effort='medium'):
        messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]
        while True:
            if not self.available():
                raise NovaError('MODEL_CALL_LIMIT')
            self.calls += 1
            try:
                completion = with_retry(self.client.chat, messages, max_tokens=min(max_tokens, self.token_cap),
                                        reasoning_effort=effort)
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

    # 2-1. 위험 징후 선별 질문 3개(양성이면 응급 평가로 상향)
    screen_red_flags(visit)

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


def assess(visit):
    result = visit.doctor.ask_json(ASSESS_PROMPT, visit.situation() + '\n\n평가와 계획:',
                                   check=lambda r: str(r.get('diagnosis') or '').strip(),
                                   max_tokens=8192, effort='high')
    if not result:  # high가 실패하면 medium으로 한 번 더
        result = visit.doctor.ask_json(ASSESS_PROMPT, visit.situation() + '\n\n평가와 계획:',
                                       check=lambda r: str(r.get('diagnosis') or '').strip(), tries=2)
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

    # A: 평가 단계 결과
    for field in RECORD_FIELDS['A']:
        note['A'][field] = clean_lines(text_value(assessment.get(field)))
    # P: 전용 LLM 호출 + 코드 안전 규칙 + 코드 렌더링
    plan_p = {}
    try:
        plan_p = make_plan(visit, assessment)
    except Exception as exc:  # noqa: BLE001 — 기록 제출은 반드시 해야 합니다.
        log('P 계획 실패', repr(exc))
    rendered = render_plan(visit, assessment, plan_p)
    for field in RECORD_FIELDS['P']:
        note['P'][field] = rendered.get(field) or clean_lines(text_value(assessment.get(field)))
    return note


# ---------------------------------------------------------------- 위험 징후 선별

POSITIVE_RE = re.compile(r'(네|예|있어요|있었어요|있습니다|그래요|맞아요|조금|가끔|약간|심해)')
NEGATIVE_RE = re.compile(r'(없|아니|안 ?(그|했|해|나)|모르|괜찮)')


def screen_red_flags(visit):
    visit.red_flags = []
    if not visit.can_act(RESERVE_CLOSING + 6) or not visit.doctor.available():
        return
    result = visit.doctor.ask_json(SCREEN_PROMPT, visit.situation() + '\n\n위험 징후 선별 질문:',
                                   check=lambda r: isinstance(r.get('questions'), list), tries=2)
    questions = [nfc(q) for q in result.get('questions') or [] if isinstance(q, str)][:3]
    if not questions:
        questions = ['가슴이 아프거나 답답하세요?', '숨이 차지는 않으세요?', '정신이 흐려진 적 있나요?']
    for q in questions:
        if not fits(q) or key_of(q) in visit.asked or not visit.can_act(RESERVE_CLOSING + 4):
            continue
        answer = visit.say(q)
        if answer and POSITIVE_RE.search(answer) and not NEGATIVE_RE.search(answer):
            visit.red_flags.append(f'{q} → {answer}')
    log('위험 징후 양성', visit.red_flags)


# ---------------------------------------------------------------- P 칸

DOSE_RE = re.compile(r'\s*\d+(?:\.\d+)?\s*(?:mg|mcg|㎎|μg|ug|g|mL|ml|IU|단위|정|알|캡슐)(?:\s*/\s*(?:kg|일|회|day|d))?'
                     r'(?:\s*(?:[xX×]\s*\d+|하루\s*\d+\s*회|\d+\s*회|bid|tid|qd|qid|BID|TID|QD|QID))*', re.I)
COND_RE = re.compile(r'고려|확인 후|결과에 따라|필요 시|필요시|조건부|검토')


def clean_lines(text):
    """리터럴 '\\n'·불릿 정리."""
    text = str(text or '').replace('\\n', '\n').replace('\\t', ' ')
    return '\n'.join(ln.rstrip() for ln in text.split('\n') if ln.strip())


def one_line(text):
    return ' '.join(str(text or '').replace('\\n', ' ').split()).strip(' -•·')


def as_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [s for s in clean_lines(value).split('\n') if s.strip()]
    return [] if value is None else [value]


def vitals_dict(visit):
    vitals = visit.initial.get('vital_signs')
    return vitals if isinstance(vitals, dict) else {}


def vitals_unstable(visit):
    """활력징후 수치로 불안정 판정. (불안정 여부, 요약 문자열)."""
    vd = vitals_dict(visit)
    summary = ', '.join(f'{k} {v}' for k, v in vd.items()) or one_line(visit.initial.get('vital_signs'))
    flags = []
    for k, v in vd.items():
        key = str(k).lower()
        nums = [float(x) for x in re.findall(r'\d+(?:\.\d+)?', str(v))]
        if not nums:
            continue
        n = nums[0]
        if re.search(r'bp|혈압', key):
            if n >= 180 or n < 90:
                flags.append(f'{k} {v}')
        elif re.search(r'hr|pr|pulse|맥박|심박', key):
            if n >= 120 or n < 50:
                flags.append(f'{k} {v}')
        elif re.search(r'rr|호흡', key):
            if n >= 24 or n < 10:
                flags.append(f'{k} {v}')
        elif re.search(r'bt|temp|체온', key):
            if n >= 39.0 or n < 35.0:
                flags.append(f'{k} {v}')
        elif re.search(r'spo2|sat|산소', key):
            if n < 92:
                flags.append(f'{k} {v}')
    return bool(flags), summary, flags


def make_plan(visit, assessment):
    if not visit.doctor.available():
        return {}
    ctx = (visit.situation()
           + f"\n\n확정 진단: {assessment.get('diagnosis', '')}"
           + f"\n진단 근거: {one_line(text_value(assessment.get('evidence')))}"
           + f"\n감별진단: {clean_lines(text_value(assessment.get('differential')))}"
           + f"\n현재 감별 목록: {', '.join(visit.differential)}"
           + f"\n위험 징후 선별 양성: {'; '.join(getattr(visit, 'red_flags', [])) or '없음'}"
           + '\n\nP 칸:')
    result = visit.doctor.ask_json(PLAN_P_PROMPT, ctx, check=lambda r: isinstance(r.get('tests'), list),
                                   max_tokens=6000, effort='high', tries=2)
    if not result:
        result = visit.doctor.ask_json(PLAN_P_PROMPT, ctx, check=lambda r: isinstance(r.get('tests'), list),
                                       max_tokens=6000, effort='medium', tries=1)
    return result or {}


def safe_treatment(item):
    """확진 전 특정 용량 제거, 조건부 표현으로 바꿉니다."""
    text = one_line(item)
    had_dose = bool(DOSE_RE.search(text))
    text = DOSE_RE.sub('', text)
    text = re.sub(r'\(\s*\)|\s{2,}', ' ', text).strip(' ,;')
    if not text:
        return ''
    if had_dose and not COND_RE.search(text):
        text = '검사 결과 확인 후 ' + text + ' 고려'
    return text


def render_plan(visit, assessment, plan):
    out = {}
    diagnosis = one_line(assessment.get('diagnosis')) or (visit.differential[0] if visit.differential else '')

    # tests
    lines = []
    for t in as_list(plan.get('tests')):
        if isinstance(t, dict):
            name, reason = one_line(t.get('name')), one_line(t.get('reason'))
        else:
            parts = re.split(r'\s*[:：]\s*', one_line(t), maxsplit=1)
            name, reason = parts[0], (parts[1] if len(parts) > 1 else '')
        if name:
            lines.append(f'- {name} : {reason or "감별진단 확인"}')
    if len(lines) < 5:
        base = [('CBC', '빈혈·감염·염증 평가'), ('LFT', '간기능 평가 및 약물 투여 전 확인'),
                ('RFT(BUN/Cr)', '신기능 평가 및 약물 용량 결정 전 확인'), ('전해질', '전해질 불균형 확인'),
                ('혈당', '대사 이상 확인'), ('소변검사', '요로·신장 이상 확인')]
        have = ' '.join(lines)
        for name, reason in base:
            if len(lines) >= 5:
                break
            if name.split('(')[0] not in have:
                lines.append(f'- {name} : {reason}')
    out['tests'] = '\n'.join(lines[:8])

    # treatment
    lines = [safe_treatment(t) for t in as_list(plan.get('treatment'))]
    lines = [f'- {t}' for t in lines if t]
    if not lines:
        lines = [f'- {s}' for s in (safe_treatment(x) for x in as_list(assessment.get('treatment'))) if s]
    joined = ' '.join(lines)
    if not re.search(r'갑자기|임의로|중단', joined):
        lines.append('- 복용 중인 약은 임의로 갑자기 중단하지 않고 재진 시 조정')
    if not re.search(r'금기|알레르기|상호작용', joined):
        lines.append('- 새 약 시작 전 금기·약물 알레르기·상호작용 확인')
    if not re.search(r'결과 확인 후|결과에 따라', joined):
        lines.append(f'- 검사 결과 확인 후 {diagnosis or "확진"}에 맞는 약물 치료 고려')
    out['treatment'] = '\n'.join(lines)

    # disposition
    unstable, summary, flags = vitals_unstable(visit)
    red = getattr(visit, 'red_flags', [])
    disp = one_line(plan.get('disposition') if not isinstance(plan.get('disposition'), list)
                    else ' '.join(map(str, plan['disposition'])))
    if not disp:
        disp = one_line(text_value(assessment.get('disposition')))
    lines = [f'- {disp}'] if disp else []
    if red or unstable:
        why = '; '.join(red + flags)
        lines.insert(0, f'- 응급 평가 : 위험 징후/활력징후 이상({why})으로 응급실 평가 및 입원 여부 결정')
    if not re.search(r'활력징후|V/S|바이탈', disp):
        lines.append(f'- 활력징후 : {"불안정" if unstable else "안정"} ({summary})')
    if not re.search(r'입원', disp):
        if unstable or red:
            lines.append('- 입원 필요 여부 : 활력징후 이상 또는 위험 징후 양성으로 입원 평가 필요')
        else:
            lines.append('- 입원 불필요 : 활력징후 안정, 위험 징후 없음, 경구 복용·외래 추적 가능')
    out['disposition'] = '\n'.join(lines)

    # follow_up
    fu = plan.get('follow_up')
    lines = []
    if isinstance(fu, dict):
        when = one_line(fu.get('when'))
        warns = [one_line(w) for w in as_list(fu.get('warning_signs')) if one_line(w)]
        mon = one_line(fu.get('monitoring')) if not isinstance(fu.get('monitoring'), list) \
            else ', '.join(one_line(m) for m in fu['monitoring'])
    else:
        when, warns, mon = '', [], ''
        for s in as_list(fu) or as_list(assessment.get('follow_up')):
            lines.append(f'- {one_line(s)}')
    if when:
        lines.append(f'- 재진 시점 : {when}')
    if mon:
        lines.append(f'- 추적 관찰 : {mon}')
    if warns:
        lines.append(f'- 즉시 내원 경고 증상 : {", ".join(warns)}')
    joined = ' '.join(lines)
    if not re.search(r'재진|주 후|일 후|개월', joined):
        lines.append('- 재진 시점 : 1주 후 검사 결과 확인 및 증상 경과 재평가')
    if not re.search(r'경고|즉시|바로|응급', joined) or len(warns) < 3:
        lines.append('- 즉시 내원 경고 증상 : 증상 급격한 악화, 호흡곤란·흉통, 의식 저하·실신, 39도 이상 고열 시 즉시 응급실 방문')
    out['follow_up'] = '\n'.join(lines)

    # education
    lines = [f'- {one_line(e)}' for e in as_list(plan.get('education')) if one_line(e)]
    if not lines:
        lines = [f'- {one_line(e)}' for e in as_list(assessment.get('education')) if one_line(e)]
    if not re.search(r'경고|즉시', ' '.join(lines)):
        lines.append('- 경고 증상이 생기면 재진을 기다리지 말고 즉시 내원하도록 교육')
    out['education'] = '\n'.join(lines)
    return out


def label(content):
    """'갑상선 촉진하겠습니다' → '갑상선 촉진'."""
    return re.sub(r'\s*(을|를)?\s*(하겠습니다|할게요|해 볼게요|해보겠습니다|해 보겠습니다|보겠습니다|확인하겠습니다)[.!]?$', '',
                  content).strip() or content


if __name__ == '__main__':
    run_agent(prepare, consult)

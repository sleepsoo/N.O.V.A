"""N.O.V.A. 2026 예선 Doctor Agent — 변형 v1_checklist(문진 체크리스트 강제로 정보수집 극대화).

변형 요지: 현병력·과거력·가족력·사회력·ROS·걱정을 고정 문구 체크리스트로 모두 묻고(시작 정보에 있는 항목만 건너뜀),
S 작성 시 체크리스트 결과를 (+)/(-)/( ) 표로 넘겨 미확인 항목은 ( )로 남깁니다. 아래는 베이스 설명입니다.

단계형 베이스라인.

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
# 변형 v1_checklist: 문진 체크리스트 강제(문진 ~32턴, 진찰 8턴, 설명 5턴).
BUDGET = {'hpi': 3, 'checklist': 34, 'ros': 2, 'exam': 8, 'closing': 4, 'qa': 1}
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

# ---------------------------------------------------------------- 문진 체크리스트(고정 문구, 각 30자 이내·한 가지만)
# (키, 기록 표 라벨, 성인 질문, 소아 보호자 질문). 시작 정보에 이미 답이 있는 항목만 건너뛰고 모두 묻습니다.
CHECKLIST_HPI = [
    ('onset', 'Onset 발병 시점', '언제부터 그러셨어요?', '아이가 언제부터 그랬나요?'),
    ('course', '경과', '점점 심해지고 있나요?', '점점 심해지고 있나요?'),
    ('character', '양상', '어떤 느낌인지 말씀해 주세요.', '아이가 어떤 모습을 보이나요?'),
    ('severity', '정도', '10점 만점에 몇 점 정도인가요?', '얼마나 심한 편인가요?'),
    ('aggravating', '악화요인', '더 심해지게 하는 게 있나요?', '더 심해지게 하는 게 있나요?'),
    ('relieving', '완화요인', '좀 나아지게 하는 게 있나요?', '좀 나아지게 하는 게 있나요?'),
    ('associated', '동반증상', '같이 나타나는 증상이 있나요?', '같이 나타나는 증상이 있나요?'),
    ('prior_visit', '이전 진료·치료', '이 일로 병원에 가 보셨나요?', '이 일로 병원에 가 보셨나요?'),
]
CHECKLIST_PMH = [
    ('dm', 'DM', '당뇨 있으세요?', '아이가 앓았던 병이 있나요?'),
    ('htn', 'HTN', '고혈압 있으세요?', '아이가 입원한 적 있나요?'),
    ('other_dz', '기타 지병', '그 밖에 앓는 병이 있으세요?', '출생 때 특별한 문제 있었나요?'),
    ('op', 'Op. Hx 수술', '수술받으신 적 있으세요?', '아이가 수술받은 적 있나요?'),
    ('tb_hep', 'Tbc/hepatitis', '결핵이나 간염 앓으신 적 있나요?', '발달은 또래와 비슷했나요?'),
    ('med', '복용약', '지금 드시는 약이 있으세요?', '아이가 먹고 있는 약이 있나요?'),
    ('allergy', 'Allergy', '약 알레르기 있으세요?', '아이가 알레르기가 있나요?'),
]
CHECKLIST_FH = [
    ('fh_similar', 'FH 유사질환', '가족 중 비슷한 증상 있는 분 있나요?', '가족 중 비슷한 증상 있나요?'),
    ('fh_dmhtn', 'FH DM/HTN', '가족 중 당뇨나 고혈압 있나요?', '예방접종은 다 맞았나요?'),
    ('fh_stroke_ca', 'FH 뇌졸중/암', '가족 중 뇌졸중이나 암 있나요?', '가족 중 앓는 병이 있나요?'),
]
CHECKLIST_SH = [
    ('smoking', 'Smoking', '담배는 피우세요?', '집에서 담배 피우는 분 있나요?'),
    ('alcohol', 'Alcohol', '술은 얼마나 드세요?', '아이를 주로 누가 돌보나요?'),
    ('job', '직업', '하시는 일이 어떻게 되세요?', '어린이집이나 학교생활은 어떤가요?'),
]
CHECKLIST_CONCERN = [
    ('concern', '걱정', '가장 걱정되시는 점이 뭔가요?', '가장 걱정되시는 점이 뭔가요?'),
    ('hope', '바라는 점', '오늘 특별히 원하시는 게 있나요?', '오늘 특별히 원하시는 게 있나요?'),
]
CHECKLIST_ROS = [
    ('fever', 'Fever/Chill', '열이나 오한이 있었나요?', '아이가 열이 났나요?'),
    ('weight', '체중변화', '최근 체중이 변했나요?', '최근 아이 체중이 변했나요?'),
    ('appetite', '식욕', '입맛은 어떠세요?', '아이가 잘 먹나요?'),
    ('sleep', '수면', '잠은 잘 주무세요?', '아이가 잠은 잘 자나요?'),
    ('palpitation', 'Palpitation', '가슴이 두근거리지는 않나요?', '아이가 가슴 두근거린다 하나요?'),
    ('dyspnea', 'Dyspnea', '숨이 차지는 않으세요?', '아이가 숨차 하지는 않나요?'),
    ('chest_pain', 'Chest pain', '가슴 통증은 없으세요?', '아이가 가슴 아파하지 않나요?'),
    ('headache', 'Headache/Dizziness', '두통이나 어지럼은 없으세요?', '아이가 머리 아파하지 않나요?'),
    ('stool', '대변', '대변은 평소와 같으세요?', '아이 대변은 평소와 같나요?'),
    ('urine', '소변', '소변 보는 데 불편은 없나요?', '아이 소변은 평소와 같나요?'),
    ('edema', 'Edema', '몸이 붓지는 않나요?', '아이 몸이 붓지는 않나요?'),
    ('mood', '기분', '요즘 기분은 어떠세요?', '아이 기분이나 행동은 어떤가요?'),
]
CHECKLIST_FEMALE = [
    ('lmp', 'LMP', '마지막 생리는 언제였나요?', '마지막 생리는 언제였나요?'),
    ('pregnancy', '임신 가능성', '임신 가능성이 있으세요?', '임신 가능성이 있으세요?'),
]
CHECK_LABELS = {k: lab for group in (CHECKLIST_HPI, CHECKLIST_PMH, CHECKLIST_FH, CHECKLIST_SH,
                                     CHECKLIST_CONCERN, CHECKLIST_ROS, CHECKLIST_FEMALE)
                for k, lab, _, _ in group}


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
 "known": ["아래 체크리스트 키 중 첫 진술에 이미 답이 분명히 나온 항목의 키"],
 "questions": ["주호소에 특화된 질문 3개(위치·방사, 감별진단을 가르는 위험 징후 등)"]}}
시작 시점·경과·양상·정도·악화·완화·동반 증상·이전 진료와 과거력·가족력·사회력·계통 문진은 체크리스트로 따로 묻습니다.
questions에는 체크리스트에 없는, 이 주호소에만 필요한 질문만 넣습니다.
체크리스트 키: """ + ', '.join(f'{k}({v})' for k, v in CHECK_LABELS.items()) + f"""
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

CHECKLIST_RULE = """
- '문진 체크리스트 결과' 표를 반드시 반영합니다. 판정 힌트가 (+)/(-)인 항목은 환자 답 원문을 보고 최종 판정해 해당 칸에 적고,
  '묻지 않음' 항목은 괄호를 비워 ( )로 남깁니다. 위 틀에 칸이 없는 항목(체중·식욕·수면·소변·부종·기분·직업 등)은
  해당 칸의 Others에 '항목 (+/-) 답 요약' 형태로 적습니다. 가족력 유사질환·뇌졸중/암은 fh에, 걱정·바라는 점은 hpi 끝에 적습니다."""

ANSWER_PROMPT = f"""{ROLE}
진료를 마무리하며 진단과 계획을 설명했습니다. 환자의 마지막 말에 답합니다. JSON 객체 하나만 출력하세요.
{{"reply": "공백 포함 {MAX_CHARS - 2}자 이내의 쉬운 존댓말 답 한 문장"}}
진단·계획과 어긋나지 않게 답하고, 질문이 없으면 "더 궁금한 점 있으면 언제든 오세요."처럼 마무리합니다."""


# ---------------------------------------------------------------- 기본 문진(규칙)

def checklist(patient, groups):
    """체크리스트 그룹들 → [(키, 질문)]. 소아면 보호자용 문구, 가임기 여성이면 생리·임신을 사회력 뒤에 붙입니다."""
    child = patient.get('child')
    items = []
    for group in groups:
        items += [(k, child_q if child else adult_q) for k, _, adult_q, child_q in group]
        if group is CHECKLIST_SH and not child:
            age = patient.get('age')
            if patient.get('sex') == 'F' and (age is None or 12 <= age <= 55):
                items += [(k, q) for k, _, q, _ in CHECKLIST_FEMALE]
    return items


SIGN_NEG = re.compile(r'없어|없습니다|없었|없고|없네|아니|안 ?(피|마|먹|해|했|났|아|붓)|안요|괜찮|정상|평소와 같|평소랑 같|그대로|모르|잘 (자|먹|주무)|딱히')


def sign_of(answer):
    """환자 답으로 (+)/(-) 힌트. 최종 판정은 S 작성 LLM이 답 원문으로 합니다."""
    return '(-)' if SIGN_NEG.search(answer or '') else '(+)'


def core_questions(patient):
    """(미사용, 베이스 호환) 과거력·약물·알레르기·가족력·사회력."""
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
        self.known = set()     # 시작 정보에 이미 답이 있는 체크리스트 키
        self.check = {}        # 체크리스트 키 → (질문, 환자 답)
        self.check_sent = 0    # 체크리스트로 쓴 턴 수

    def ask_checklist(self, items, reserve):
        """체크리스트 질문을 순서대로 묻고 답을 키별로 남깁니다. 시작 정보에 있거나 이미 물은 항목은 건너뜁니다."""
        for k, question in items:
            if self.check_sent >= BUDGET['checklist'] or not self.can_act(reserve):
                break
            if k in self.known or k in self.check:
                continue
            question = nfc(question)
            if not fits(question) or key_of(question) in self.asked:
                continue
            answer = self.say(question)
            if answer is not None:
                self.check[k] = (question, answer)
                self.check_sent += 1

    def checklist_table(self):
        """S 작성용 체크리스트 결과 표. 묻지 않은 항목은 ( )."""
        rows = ['키 | 기록 라벨 | 실제 질문 | 환자 답 | 판정 힌트']
        for k, lab in CHECK_LABELS.items():
            if k in self.check:
                q, a = self.check[k]
                rows.append(f'{k} | {lab} | {q} | {a} | {sign_of(a)}')
            elif k in self.known:
                rows.append(f'{k} | {lab} | (시작 정보) | 첫 진술 참고 | 첫 진술대로')
            else:
                rows.append(f'{k} | {lab} | 묻지 않음 | - | ( )')
        return '\n'.join(rows)

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
        self.known = {str(k) for k in result.get('known') or [] if str(k) in CHECK_LABELS}
        log('계획', self.patient, self.differential, '이미 앎:', sorted(self.known))
        questions = [nfc(q) for q in result.get('questions') or [] if isinstance(q, str)]
        return questions or ['어디가 제일 불편하세요?']

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

    # 1. 계획(체크리스트 중 이미 아는 항목 판정 + 주호소 특화 질문)
    questions = visit.plan()
    # 진찰과 설명을 위한 턴을 남겨 둡니다.
    reserve = RESERVE_CLOSING + BUDGET['exam']

    # 2. 현병력 체크리스트(인사를 겸한 첫 질문) → 주호소 특화 질문
    hpi = checklist(visit.patient, [CHECKLIST_HPI])
    hpi = [(k, q) for k, q in hpi if k not in visit.known]
    if hpi and fits('안녕하세요. ' + hpi[0][1]):
        hpi[0] = (hpi[0][0], '안녕하세요. ' + hpi[0][1])
    elif not hpi and questions and fits('안녕하세요. ' + questions[0]):
        questions[0] = '안녕하세요. ' + questions[0]
    visit.ask_checklist(hpi, reserve)
    visit.ask_all(questions, BUDGET['hpi'], reserve=reserve)

    # 3. 과거력·가족력·사회력·걱정·계통 문진 체크리스트(고정 문구, 미확인 항목 전부)
    visit.ask_checklist(checklist(visit.patient, [CHECKLIST_PMH, CHECKLIST_FH, CHECKLIST_SH,
                                                  CHECKLIST_CONCERN, CHECKLIST_ROS]), reserve)

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
    subjective = visit.doctor.ask_json(SUBJECTIVE_PROMPT + CHECKLIST_RULE,
                                       visit.situation() + '\n\n문진 체크리스트 결과\n' + visit.checklist_table()
                                       + '\n\nS 칸:',
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

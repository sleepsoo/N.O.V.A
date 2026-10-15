"""질문 은행(성인·소아 보호자)과 진찰 은행. 모든 문구는 NFC 30자 이하(tests에서 검증)."""
from __future__ import annotations

import re

# ------------------------------------------------------------------ 질문 은행
# (id, 문구, ROS/기록 라벨) — 라벨은 기록 작성 시 어떤 항목을 물었는지 LLM에 알려 주는 힌트.
# skip 정규식이 시작 정보에 걸리면 이미 답한 것으로 보고 묻지 않는다.

ADULT_HPI = [
    ('onset', '언제부터 그러셨어요?', 'Onset', r'(전부터|동안|사이|년 전|달 전|개월|주 전|일 전|어제|그제|며칠|오늘 아침|해 전|부터)'),
    ('course', '그 뒤로 점점 심해지고 있나요?', '경과', None),
    ('impact', '일상생활에 지장이 얼마나 있으세요?', '일상 지장', None),
    ('aggravate', '더 심해지게 하는 게 있나요?', '악화 요인', None),
    ('relieve', '좀 나아지게 하는 게 있나요?', '완화 요인', None),
    ('prior_care', '이 문제로 진료받은 적 있으세요?', '이전 진료', None),
]

PEDS_HPI = [
    ('onset', '언제부터 그랬나요?', 'Onset', r'(전부터|동안|사이|년 전|달 전|개월|주 전|일 전|어제|그제|며칠|오늘 아침|해 전|부터)'),
    ('course', '그 뒤로 점점 심해지고 있나요?', '경과', None),
    ('prior_care', '이 문제로 병원에 가 본 적 있나요?', '이전 진료', None),
]

ADULT_HISTORY = [
    ('pmh_dm_htn', '고혈압이나 당뇨 있으세요?', 'DM/HTN', None),
    ('pmh_other', '다른 지병이나 수술받은 적 있으세요?', '기타 지병·수술', None),
    ('meds', '드시는 약이나 영양제 있으세요?', 'Medicine history', None),
    ('fh_open', '부모님이나 형제분 앓는 병 있나요?', 'FH', None),
    ('smoking', '담배는 피우세요?', 'Smoking', None),
    ('alcohol', '술은 얼마나 드세요?', 'Alcohol', None),
    ('sh_caffeine', '커피는 하루 몇 잔 드세요?', '카페인', None),
    ('job', '무슨 일 하세요?', '직업', None),
    ('sh_exercise', '평소 운동은 얼마나 하세요?', '운동', None),
    ('allergy', '약 알레르기 있으세요?', 'Allergy', None),
]
OPTIONAL_HISTORY = {'allergy', 'sh_exercise'}  # 문진 여유가 있을 때만

PEDS_HISTORY = [
    ('birth_term', '만삭에 낳았나요?', '출생력-재태', None),
    ('p_birth_size', '태어날 때 키와 몸무게는요?', '출생 체격', None),
    ('neonatal', '신생아 때 황달 같은 문제 있었나요?', '신생아기', None),
    ('develop', '말이나 걷기는 또래만큼 했나요?', '발달', None),
    ('p_chronic', '천식이나 장, 콩팥 질환 들은 적 있나요?', '만성질환', None),
    ('admission', '입원하거나 크게 아픈 적 있나요?', '입원력', None),
    ('meds', '먹는 약이나 한약, 영양제 있나요?', 'Medicine history', None),
    ('gr_steroid', '스테로이드 약을 먹은 적 있나요?', '스테로이드', None),
    ('vaccine', '예방접종은 제때 맞았나요?', '예방접종', None),
    ('fh_open', '가족 중 앓는 병 있는 분 있나요?', 'FH', None),
    ('home', '집이나 어린이집 생활은 어떤가요?', '가정·사회', None),
    ('allergy', '약 알레르기 있나요?', 'Allergy', None),
]

ADULT_ROS = [
    # 핵심 ROS(항상 후보, 앞쪽 우선)
    ('ros_palp', '가슴 두근거림 있으세요?', 'Palpitation', None),
    ('ros_dyspnea', '숨이 찬 적 있으세요?', 'Dyspnea', None),
    ('ros_chest', '가슴 아픈 적 있으세요?', 'Chest pain', None),
    ('ros_sleep', '잠은 잘 주무세요?', '수면', r'(잠|불면|수면)'),
    ('ros_mood', '요즘 기분은 어떠세요?', '기분', None),
    ('ros_bowel', '대변 횟수나 모양이 변했나요?', '배변', None),
    ('ros_urine', '소변 보는 게 달라졌나요?', '배뇨', None),
    ('ros_edema', '몸이나 다리가 붓나요?', 'Edema', None),
    ('ros_fatigue', '많이 피곤하거나 기운 없으세요?', 'Fatigue/Weakness', r'(피곤|피로|기운)'),
    # 추가 ROS
    ('ros_fever', '열이나 오한 있으세요?', 'Fever/Chill', None),
    ('ros_weight', '최근 체중 변화 있으세요?', '체중 변화', r'(체중|몸무게|살이|킬로|키로)'),
    ('ros_appetite', '입맛은 어떠세요?', 'Anorexia', None),
    ('ros_headache', '두통 있으세요?', 'Headache', None),
    ('ros_dizzy', '어지러운 적 있으세요?', 'Dizziness', None),
    ('ros_cough', '기침이나 가래 있으세요?', 'Cough/Sputum', None),
    ('ros_abd', '배가 아픈 적 있으세요?', 'Abdominal pain', None),
    ('ros_nv', '메스껍거나 토한 적 있으세요?', 'Nausea/Vomiting', None),
    ('pmh_cvd', '심장병이나 뇌졸중 앓으신 적 있나요?', 'heart disease/stroke', None),
    ('fh_stroke_ca', '가족 중 뇌졸중이나 암 있으세요?', 'FH stroke/cancer', None),
]

PEDS_ROS = [
    ('ros_fever', '아이가 열이 난 적 있나요?', 'Fever', None),
    ('ros_appetite', '밥은 잘 먹나요?', '식사·영양', None),
    ('ros_milk', '우유는 하루에 얼마나 마시나요?', '우유 섭취', None),
    ('ros_sleep', '밤에 잠은 잘 자나요?', '수면', None),
    ('ros_activity', '잘 뛰어놀고 활발한가요?', '활동', None),
    ('ros_fatigue', '쉽게 피곤해하나요?', 'Fatigue', None),
    ('ros_bowel', '변비나 설사가 있나요?', 'Constipation/Diarrhea', None),
    ('ros_vomit', '자주 토하나요?', 'Vomiting', None),
    ('ros_cough', '기침을 자주 하나요?', 'Cough', None),
    ('ros_headache', '머리 아프다고 한 적 있나요?', 'Headache', None),
]

ADULT_ICE = [
    ('ice_concern', '가장 걱정되는 게 뭐예요?', '걱정(ICE)', None),
    ('ice_expect', '오늘 바라시는 게 있으세요?', '기대(ICE)', None),
]

PEDS_ICE = [
    ('ice_concern', '어머님이 가장 걱정되는 게 뭐예요?', '보호자 걱정(ICE)', None),
    ('ice_expect', '오늘 가장 궁금하신 게 뭐예요?', '보호자 기대(ICE)', None),
]


def informant_title(opening: str) -> str:
    t = opening or ''
    if re.search(r'(엄마|어머니)', t):
        return '어머님'
    if re.search(r'(아빠|아버지)', t):
        return '아버님'
    if re.search(r'할머니', t):
        return '할머님'
    if re.search(r'할아버지', t):
        return '할아버님'
    return '보호자분'


def peds_ice(opening: str):
    title = informant_title(opening)
    return [(i[0], i[1].replace('어머님', title), i[2], i[3]) for i in PEDS_ICE]

# 주호소 카테고리별 추가 묶음 (키워드, 성인 문항, 소아 문항)
CATEGORY_BUNDLES = {
    'pain': (r'(통증|아파|아프|쑤|저리|저려|결려|따끔)', [
        ('pain_site', '정확히 어디가 아프세요?', '부위'),
        ('pain_nrs', '통증을 0~10으로 하면 몇 점이에요?', 'NRS'),
        ('pain_char', '어떤 식으로 아프세요?', '양상'),
        ('pain_rad', '아픈 게 다른 데로 퍼지나요?', '방사'),
        ('pain_time', '계속 아프세요, 왔다 갔다 하세요?', '지속/간헐'),
    ], [
        ('pain_site', '아이가 어디를 아파하나요?', '부위'),
        ('pain_char', '얼마나 자주 아파하나요?', '빈도'),
    ]),
    'weight': (r'(체중|살이|몸무게|빠져|빠졌|늘었|마른|피곤|피로|기운|무기력)', [
        ('wt_intake', '식사량은 예전과 비교해 어떠세요?', '식사량'),
        ('wt_heat', '더위를 예전보다 많이 타세요?', '더위 민감'),
        ('wt_sweat', '땀이 많아지셨나요?', '발한'),
        ('wt_tremor', '손이 떨리세요?', '손떨림'),
        ('wt_bowel', '대변 횟수나 모양이 변했나요?', '배변 변화'),
        ('wt_thirst', '물을 많이 마시거나 소변이 늘었나요?', '다음/다뇨'),
        ('wt_eye', '눈이 튀어나오거나 뻑뻑한가요?', '눈 증상'),
        ('wt_neck', '목이 붓거나 혹이 만져지나요?', '목 부음'),
        ('wt_activity', '운동량이나 활동량이 늘었나요?', '활동량'),
    ], [
        ('wt_intake', '아이가 먹는 양은 어떤가요?', '식사량'),
    ]),
    'sleep': (r'(잠|불면|수면|못\s*자)', [
        ('sl_initiate', '잠드는 데 오래 걸리세요?', '입면 장애'),
        ('sl_maintain', '자다가 자주 깨세요?', '수면 유지 장애'),
        ('sl_daytime', '낮에 졸리거나 멍하세요?', '주간 졸림'),
        ('sl_snore', '코골이나 숨 멈춤 있으세요?', '코골이/무호흡'),
        ('sl_caffeine', '커피는 하루 몇 잔 드세요?', '카페인'),
    ], [
        ('sl_maintain', '아이가 자다가 자주 깨나요?', '야간 각성'),
    ]),
    'drug': (r'(약|처방|수면제|진통제|복용)', [
        ('dr_name', '드시는 약 이름과 용량을 아세요?', '약 이름·용량'),
        ('dr_dose', '지금 하루에 몇 알 드세요?', '복용량'),
        ('dr_timing', '하루 중 언제 언제 드세요?', '복용 시각'),
        ('dr_tolerance', '처음보다 약 양이 늘었나요?', '내성'),
        ('dr_withdraw', '약을 안 드시면 어떤 증상이 있나요?', '금단 증상'),
        ('dr_cut', '줄이거나 끊어 보려 하신 적 있나요?', '감량 시도'),
        ('dr_where', '약은 어디서 처방받으세요?', '처방처'),
        ('dr_other', '다른 수면제나 약국 약도 드세요?', '다른 약 병용'),
        ('dr_memory', '약 드신 뒤 기억이 끊긴 적 있나요?', '기억 공백'),
        ('dr_family', '가족들이 약 문제로 걱정하나요?', '대인 갈등'),
    ], []),
    'growth': (r'(키|성장|작아|작은|자라)', [], [
        ('gr_father', '아빠 키는 얼마인가요?', '부 키'),
        ('gr_mother', '엄마 키는 얼마인가요?', '모 키'),
        ('gr_late', '부모님 중 늦게 키가 큰 분 있나요?', '부모 사춘기 지연'),
        ('gr_record', '예전에 잰 키 기록이 있나요?', '성장 기록'),
        ('gr_when', '언제부터 작다는 말을 들었나요?', '작다는 시점'),
        ('gr_short_fh', '가족 중 키가 작거나 유전병 있나요?', '저신장 가족력'),
        ('gr_puberty', '음모나 고환 변화가 있었나요?', '사춘기 징후'),
        ('gr_hypo', '잘 지치거나 변비, 추위 타나요?', '갑상선저하 증상'),
        ('gr_ich', '두통이나 구토, 시야 이상은요?', '두개내 병변 증상'),
    ]),
    'resp': (r'(기침|가래|숨|호흡|천식|쌕쌕|코)', [
        ('rs_sputum', '가래는 무슨 색이에요?', '가래 양상'),
        ('rs_wheeze', '숨 쉴 때 쌕쌕 소리 나나요?', 'Wheezing'),
        ('rs_hemop', '가래에 피가 섞인 적 있나요?', '객혈'),
        ('rs_night', '밤에 더 심해지나요?', '야간 악화'),
    ], [
        ('rs_wheeze', '숨 쉴 때 쌕쌕 소리 나나요?', 'Wheezing'),
        ('rs_night', '밤에 기침이 더 심한가요?', '야간 악화'),
    ]),
    'gi': (r'(배|복통|설사|구토|토|변비|소화|속쓰|메스|대변)', [
        ('gi_nv', '메스껍거나 토하세요?', 'N/V'),
        ('gi_stool', '설사나 변비 있으세요?', 'Diarrhea/Constipation'),
        ('gi_blood', '변에 피가 섞이거나 검은가요?', 'Hematochezia/Melena'),
        ('gi_meal', '식사하고 나서 더 심해지나요?', '식사 관련'),
    ], [
        ('gi_nv', '아이가 토하나요?', 'Vomiting'),
        ('gi_stool', '변은 어떤가요?', '배변'),
    ]),
    'neuro': (r'(두통|머리|어지|저림|마비|떨림|기억|힘이\s*빠|경련)', [
        ('nr_sudden', '갑자기 시작됐나요?', '급성 발생'),
        ('nr_weak', '팔다리에 힘이 빠진 적 있나요?', '위약'),
        ('nr_speech', '말이 어눌해진 적 있나요?', '구음장애'),
        ('nr_vision', '눈이 침침하거나 겹쳐 보이나요?', '시각 증상'),
        ('nr_numb', '손발이 저리세요?', '감각 이상'),
    ], [
        ('nr_seizure', '경련한 적 있나요?', '경련'),
    ]),
    'cardio': (r'(가슴|흉통|두근|숨이\s*차|부종|붓)', [
        ('cv_exert', '움직일 때 더 심해지나요?', '운동 시 악화'),
        ('cv_edema', '다리가 붓나요?', '하지 부종'),
        ('cv_orthop', '누우면 숨이 차나요?', '기좌호흡'),
        ('cv_sweat', '식은땀이 나세요?', '식은땀'),
    ], []),
    'urinary': (r'(소변|오줌|배뇨|요실금|혈뇨)', [
        ('ur_freq', '소변을 자주 보세요?', '빈뇨'),
        ('ur_pain', '소변 볼 때 아프세요?', '배뇨통'),
        ('ur_blood', '소변에 피가 섞이나요?', '혈뇨'),
    ], [
        ('ur_pain', '소변 볼 때 아파하나요?', '배뇨통'),
    ]),
    'fever': (r'(열이|발열|오한|감기|몸살)', [
        ('fv_max', '열은 몇 도까지 났어요?', '최고 체온'),
        ('fv_chill', '오한이 있으세요?', 'Chill'),
        ('fv_contact', '주변에 아픈 사람 있나요?', '접촉력'),
    ], [
        ('fv_max', '열은 몇 도까지 났나요?', '최고 체온'),
    ]),
    'skin': (r'(발진|가려|두드러기|피부|반점)', [
        ('sk_where', '어디에 생겼나요?', '부위'),
        ('sk_itch', '가려우세요?', '소양감'),
        ('sk_new', '새로 쓴 약이나 음식 있나요?', '유발 요인'),
    ], [
        ('sk_where', '어디에 생겼나요?', '부위'),
    ]),
    'msk': (r'(관절|허리|무릎|어깨|목이|손목|발목|뻣뻣)', [
        ('mk_swell', '관절이 붓거나 열감이 있나요?', '관절 부종'),
        ('mk_morning', '아침에 뻣뻣한 게 오래가나요?', '조조강직'),
        ('mk_trauma', '다치거나 무리한 적 있나요?', '외상'),
    ], []),
    'mood': (r'(우울|불안|기분|스트레스|짜증|예민)', [
        ('md_mood', '기분이 우울하세요?', '우울'),
        ('md_anx', '불안하거나 초조하세요?', '불안'),
        ('md_si', '죽고 싶은 생각 드신 적 있나요?', '자살 사고'),
    ], []),
}

WOMEN_BUNDLE = [
    ('wm_cycle', '생리는 규칙적으로 하세요?', '월경 주기'),
    ('wm_change', '생리 양이나 기간이 변했나요?', '월경 변화'),
    ('wm_preg', '마지막 생리는 언제였어요?', 'LMP'),
    ('wm_pregnancy', '혹시 임신 가능성은 있으세요?', '임신 가능성'),
]
GR_VALUES = ('gr_values', '두 살, 네 살 때 키는 얼마였나요?', '과거 계측치')
FH_AUTOIMMUNE = ('fh_autoimmune', '가족 중 갑상선이나 자가면역 병 있나요?', 'FH 자가면역')

# A6: 카테고리 인지형 ROS 순서(v1 id)
ROS_BY_CAT = {
    'weight': ['ros_sleep', 'ros_mood', 'ros_bowel', 'ros_urine', 'ros_abd', 'ros_fever', 'ros_edema', 'ros_dyspnea'],
    'sleep': ['ros_mood', 'ros_fatigue', 'ros_palp', 'ros_headache', 'ros_weight', 'ros_appetite'],
    'drug': ['ros_mood', 'ros_fatigue', 'ros_palp', 'ros_headache', 'ros_dizzy', 'ros_appetite'],
    'mood': ['ros_sleep', 'ros_appetite', 'ros_fatigue', 'ros_weight', 'ros_palp'],
    'cardio': ['ros_dyspnea', 'ros_chest', 'ros_palp', 'ros_edema', 'ros_dizzy', 'ros_fatigue'],
    'resp': ['ros_fever', 'ros_cough', 'ros_dyspnea', 'ros_chest', 'ros_weight', 'ros_edema'],
    'gi': ['ros_nv', 'ros_bowel', 'ros_appetite', 'ros_weight', 'ros_fever', 'ros_urine'],
    'neuro': ['ros_headache', 'ros_dizzy', 'ros_nv', 'ros_fever', 'ros_mood'],
    'urinary': ['ros_fever', 'ros_urine', 'ros_abd', 'ros_nv'],
    'fever': ['ros_cough', 'ros_headache', 'ros_abd', 'ros_urine', 'ros_nv'],
    'pain': ['ros_fever', 'ros_nv', 'ros_appetite', 'ros_weight'],
    'skin': ['ros_fever', 'ros_fatigue'], 'msk': ['ros_fever', 'ros_weight', 'ros_fatigue'],
}


def ordered_ros(categories, ros_bank):
    by_id = {r[0]: r for r in ros_bank}
    order = []
    for c in categories or []:
        for i in ROS_BY_CAT.get(c, []):
            if i in by_id and i not in order:
                order.append(i)
    for r in ros_bank:
        if r[0] not in order:
            order.append(r[0])
    return [by_id[i] for i in order]


# 답 기반 중복 차단: 이전 환자 답(+시작 정보)에 맞으면 그 문항은 이미 확인된 것으로 보고 묻지 않는다(v1 id 기준)
FAMILY_WORD = r'(가족|부모|어머니|아버지|엄마|아빠|형제|자매|언니|오빠|누나|동생|할머니|할아버지|친척|이모|삼촌)'
COVER_RE_V1 = {
    'onset': r'(\d+|[한두세네석]|[일이삼사오육칠팔구십]+)\s*(년|달|개월|주|일)\s*(전|째|동안|사이)|부터',
    'wt_sweat': r'땀', 'ros_fever': r'열이\s*(나|있)', 'wt_intake': r'(많이|더)\s*먹|식사량|입맛|식욕',
    'ros_appetite': r'입맛|식욕|잘\s*먹|(많이|더)\s*먹', 'ros_sleep': r'잠|자요|깨요|못\s*자',
    'meds': r'(먹는|드시는|복용).{0,6}약|약.{0,6}(없|안\s*먹)|영양제', 'smoking': r'담배|흡연',
    'alcohol': r'(?<!수)술|음주|소주|맥주', 'sh_caffeine': r'커피|카페인', 'wm_pregnancy': r'임신|피임',
    'wm_change': r'생리.{0,10}(양|기간|줄|늘|짧|길)', 'birth_term': r'만삭|조산|주\s*만에',
    'p_birth_size': r'\d+(\.\d+)?\s*(kg|킬로|키로|cm|센티)', 'gr_late': r'늦게\s*(컸|크|자)|사춘기.{0,4}늦|수염',
    'dr_where': r'병원|내과|신경과|정신과', 'dr_tolerance': r'(늘었|많아졌|반\s*알|서너)',
    'dr_withdraw': r'안\s*먹으면|못\s*자고|식은땀|손.{0,4}떨', 'ros_bowel': r'대변|변을|설사|묽', 'wt_bowel': r'대변|설사|묽',
    'ros_palp': r'두근', 'wt_tremor': r'떨려|떨림', 'wt_eye': r'눈이|눈.{0,4}(튀어|뻑뻑)', 'wt_neck': r'목.{0,6}(붓|두꺼|혹)',
    'ros_dyspnea': r'숨이?\s*차', 'ros_fatigue': r'피곤|지쳐|기운', 'ros_mood': r'우울|불안|예민|짜증',
    'wt_activity': r'운동|활동량', 'sh_exercise': r'운동', 'job': r'회사|직장|사무|주부|일해|근무',
}
FAMILY_COVER = {'fh_open', 'fh_autoimmune', 'gr_late', 'gr_short_fh'}


def covered_by_answers(qid: str, texts) -> bool:
    pat = COVER_RE_V1.get(qid)
    if not pat:
        return False
    for t in texts:
        if re.search(pat, t or '') and (qid not in FAMILY_COVER or re.search(FAMILY_WORD, t or '')):
            return True
    return False

# 질문 은행 id → 기록 키(판정 프롬프트 힌트·폴백 렌더링용)
QKEYS = {
    'onset': ['hpi.onset'], 'course': ['hpi.course'], 'impact': ['hpi.impact'], 'aggravate': ['hpi.aggravating'],
    'relieve': ['hpi.relieving'], 'prior_care': ['hpi.prior_visit'],
    'pmh_dm_htn': ['pmh.DM', 'pmh.HTN'], 'pmh_other': ['pmh.other_illness', 'pmh.op_hx'], 'pmh_tb_hep': ['pmh.Tbc', 'pmh.hepatitis'],
    'pmh_op': ['pmh.op_hx'], 'meds': ['pmh.meds'], 'allergy': ['pmh.allergy'], 'pmh_cvd': ['pmh.heart_disease', 'pmh.stroke'],
    'fh_similar': ['fh.similar'], 'fh_dm_htn': ['fh.DM', 'fh.HTN'], 'fh_stroke_ca': ['fh.stroke', 'fh.cancer'],
    'smoking': ['sh.smoking'], 'alcohol': ['sh.alcohol'], 'job': ['sh.job'], 'sl_caffeine': ['sh.caffeine'],
    'ros_palp': ['ros.Palpitation'], 'ros_dyspnea': ['ros.Dyspnea'], 'ros_chest': ['ros.Chest pain'],
    'ros_sleep': ['ros.Sleep'], 'ros_mood': ['ros.Mood'], 'ros_bowel': ['ros.Bowel change'],
    'ros_urine': ['ros.Urinary change'], 'ros_edema': ['ros.Edema'], 'ros_fatigue': ['ros.Fatigue', 'ros.General weakness'],
    'ros_fever': ['ros.Fever', 'ros.Chill'], 'ros_weight': ['ros.Weight change'], 'ros_appetite': ['ros.Appetite'],
    'ros_headache': ['ros.Headache'], 'ros_dizzy': ['ros.Dizziness'], 'ros_cough': ['ros.Cough', 'ros.Sputum'],
    'ros_abd': ['ros.Abdominal pain'], 'ros_nv': ['ros.Nausea', 'ros.Vomiting'], 'gi_nv': ['ros.Nausea', 'ros.Vomiting'],
    'gi_stool': ['ros.Diarrhea', 'ros.Constipation'], 'gi_blood': ['ros.Hematochezia', 'ros.Melena'],
    'wm_change': ['ros.Menstrual change'], 'wm_preg': ['ros.LMP'], 'wm_cycle': ['ros.Menstrual change'],
    'ice_concern': ['ice.concern'], 'ice_expect': ['ice.expectation'],
    'birth_term': ['peds.출생력'], 'birth_mode': ['peds.출생력'], 'birth_wt': ['peds.출생력'], 'neonatal': ['peds.신생아기'],
    'develop': ['peds.발달'], 'vaccine': ['peds.예방접종'], 'chronic': ['pmh.other_illness'], 'admission': ['pmh.op_hx'],
    'home': ['sh.home'], 'ros_appetite_p': ['peds.영양'], 'ros_milk': ['peds.영양'], 'ros_activity': ['peds.수면·활동'],
    'gr_record': ['peds.성장 기록'], 'gr_father': ['fh.father_height'], 'gr_mother': ['fh.mother_height'],
    'gr_late': ['fh.late_puberty'], 'gr_short_fh': ['fh.short_stature'], 'gr_puberty': ['ros.Puberty signs'],
    'wm_pregnancy': ['ros.Pregnancy'], 'fh_open': ['fh.similar'], 'sh_caffeine': ['sh.caffeine'],
    'sh_exercise': ['sh.exercise'], 'p_birth_size': ['peds.출생력'], 'p_chronic': ['pmh.other_illness'],
    'gr_steroid': ['pmh.meds'], 'gr_values': ['peds.성장 기록'], 'fh_autoimmune': ['fh.other:자가면역 질환'],
    'wt_bowel': ['ros.Bowel change'], 'wt_thirst': ['ros.Polydipsia'], 'wt_sweat': ['ros.Sweating'],
    'wt_tremor': ['ros.Tremor'], 'wt_heat': ['ros.Heat intolerance'], 'gr_hypo': ['ros.other:갑상선저하 증상'],
    'gr_ich': ['ros.other:두통·구토·시야 이상'],
}


def question_text_ok(q: str) -> bool:
    import unicodedata
    return 0 < len(unicodedata.normalize('NFC', q)) <= 30


def detect_categories(text: str, pediatric: bool) -> list[str]:
    cats = []
    for name, (pattern, adult, peds) in CATEGORY_BUNDLES.items():
        if re.search(pattern, text or '') and (peds if pediatric else adult):
            cats.append(name)
    return cats


def bundle_questions(categories: list[str], pediatric: bool) -> list[tuple[str, str, str]]:
    """카테고리 묶음을 번갈아(round-robin) 섞어 한 카테고리가 상한을 독차지하지 않게 한다.
    첫 카테고리는 처음 두 문항을 먼저 묻는다."""
    lists = []
    for c in categories:
        if c not in CATEGORY_BUNDLES:
            continue
        _, adult, peds = CATEGORY_BUNDLES[c]
        items = list(peds if pediatric else adult)
        if items:
            lists.append(items)
    if not lists:
        return []
    out = lists[0][:4]
    lists[0] = lists[0][4:]
    while any(lists):
        for lst in lists:
            if lst:
                out.append(lst.pop(0))
    return out


SYMPTOM_CATS = {'pain', 'resp', 'gi', 'neuro', 'cardio', 'msk', 'skin', 'urinary', 'fever'}


# ------------------------------------------------------------------ 진찰 은행
# (id, 요청 문구(30자 이하), 기록 계통, 중복 그룹, 적응 키워드)
EXAM_BANK = [
    # 기본
    ('vitals', '활력징후 측정하겠습니다', 'V/S', 'vitals', 'all'),
    ('general', '전반적 외관 시진하겠습니다', 'General', 'general', 'all'),
    ('mental', '의식·지남력 평가하겠습니다', 'General', 'mental', 'neuro psych sleep elderly confusion'),
    ('orthostatic', '기립성 혈압 측정하겠습니다', 'V/S', 'orthostatic', 'dizzy syncope sleep drug elderly dehydration'),
    ('radial', '요골동맥 맥박 촉진하겠습니다', 'Pulse', 'radial', 'palpitation thyroid weight cardio'),
    # 성장·소아
    ('anthro', '신체 계측하겠습니다', 'Growth', 'anthro', 'growth peds weight'),
    ('growth_chart', '성장도표 백분위수 확인하겠습니다', 'Growth', 'growth_chart', 'growth peds'),
    ('growth_vel', '성장 속도·중간부모키 산출하겠습니다', 'Growth', 'growth_vel', 'growth peds'),
    ('body_prop', '신체 비율 평가하겠습니다', 'Growth', 'body_prop', 'growth peds'),
    ('tanner', '사춘기 성숙도 평가하겠습니다', 'Genitalia', 'tanner', 'growth peds puberty'),
    ('dysmorph', '안면 기형 소견 시진하겠습니다', 'H/E/E/N/T', 'dysmorph', 'growth peds development'),
    # 정신·인지
    ('cognitive', '인지기능 선별검사 하겠습니다', 'Neuro', 'cognitive', 'sleep drug memory elderly psych'),
    ('sedation', '주간 진정·불안 관찰하겠습니다', 'General', 'sedation', 'sleep drug psych'),
    ('insight', '병식 평가하겠습니다', 'Psych', 'insight', 'sleep drug psych'),
    # 피부
    ('skin_temp', '피부 온도·발한 촉진하겠습니다', 'Skin', 'skin_temp', 'thyroid weight sweat drug fever'),
    ('skin_rash', '피부 발진 시진하겠습니다', 'Skin', 'skin_rash', 'skin fever rash'),
    ('skin_turgor', '피부 긴장도 확인하겠습니다', 'Skin', 'skin_turgor', 'dehydration gi vomiting'),
    ('striae', '자주색 선조 시진하겠습니다', 'Skin', 'striae', 'cushing weight growth obesity'),
    ('acanthosis', '흑색가시세포증 시진하겠습니다', 'Skin', 'acanthosis', 'obesity diabetes weight'),
    ('skin_dry', '피부 건조 확인하겠습니다', 'Skin', 'skin_dry', 'thyroid fatigue weight'),
    ('spider', '거미혈관종 시진하겠습니다', 'Skin', 'spider', 'liver alcohol'),
    ('nail_pallor', '손톱 창백 확인하겠습니다', 'Skin', 'nail_pallor', 'anemia fatigue'),
    ('clubbing', '곤봉지 확인하겠습니다', 'Extremities', 'clubbing', 'resp lung cardio'),
    ('cap_refill', '모세혈관 재충혈 확인하겠습니다', 'Extremities', 'cap_refill', 'dehydration peds shock'),
    # 머리·눈·귀·코·목
    ('conj', '결막·공막 시진하겠습니다', 'H/E/E/N/T', 'conj', 'anemia jaundice fatigue weight liver'),
    ('pupil', '동공 대광반사 확인하겠습니다', 'H/E/E/N/T', 'pupil', 'neuro headache drug'),
    ('eom', '외안근 운동 검사하겠습니다', 'H/E/E/N/T', 'eom', 'thyroid eye neuro diplopia'),
    ('eye_signs', '갑상선 안징후 검사하겠습니다', 'H/E/E/N/T', 'eye_signs', 'thyroid weight eye'),
    ('nystagmus', '안구진탕 확인하겠습니다', 'H/E/E/N/T', 'nystagmus', 'dizzy neuro drug alcohol'),
    ('fundus', '안저 검사하겠습니다', 'H/E/E/N/T', 'fundus', 'headache htn diabetes vision'),
    ('vfield', '대면 시야 검사하겠습니다', 'H/E/E/N/T', 'vfield', 'headache vision pituitary'),
    ('ear', '고막 시진하겠습니다', 'H/E/E/N/T', 'ear', 'ear fever peds uri'),
    ('pharynx', '인두·편도 시진하겠습니다', 'H/E/E/N/T', 'pharynx', 'sore throat fever uri cough'),
    ('nasal', '비강 시진하겠습니다', 'H/E/E/N/T', 'nasal', 'rhinorrhea uri sinus'),
    ('sinus', '부비동 압통 확인하겠습니다', 'H/E/E/N/T', 'sinus', 'sinus headache uri'),
    ('oral', '구강 점막 시진하겠습니다', 'H/E/E/N/T', 'oral', 'dehydration oral anemia'),
    ('tongue', '혀 시진하겠습니다', 'H/E/E/N/T', 'tongue', 'anemia oral'),
    ('dental', '치아 상태 시진하겠습니다', 'H/E/E/N/T', 'dental', 'weight oral'),
    ('dysarthria', '구음장애 확인하겠습니다', 'Neuro', 'dysarthria', 'neuro drug stroke'),
    ('face_sym', '안면 대칭성 확인하겠습니다', 'Neuro', 'face_sym', 'neuro stroke'),
    ('thyroid', '갑상선 촉진하겠습니다', 'Neck', 'thyroid', 'thyroid weight fatigue palpitation growth'),
    ('thyroid_bruit', '갑상선 잡음 청진하겠습니다', 'Neck', 'thyroid_bruit', 'thyroid weight'),
    ('cervical_ln', '경부 림프절 촉진하겠습니다', 'Neck', 'cervical_ln', 'fever uri weight cancer neck'),
    ('neck_stiff', '경부 강직 확인하겠습니다', 'Neuro', 'neck_stiff', 'headache fever meningitis'),
    ('jvp', '경정맥 팽대 관찰하겠습니다', 'Neck', 'jvp', 'cardio dyspnea edema'),
    ('carotid', '경동맥 잡음 청진하겠습니다', 'Neck', 'carotid', 'stroke cardio dizzy'),
    ('axillary_ln', '액와 림프절 촉진하겠습니다', 'Lymph', 'lymph_other', 'cancer breast weight'),
    ('inguinal_ln', '서혜부 림프절 촉진하겠습니다', 'Lymph', 'lymph_other', 'cancer weight infection'),
    # 흉부
    ('chest_insp', '흉곽 시진하겠습니다', 'Chest', 'chest_insp', 'resp dyspnea cough'),
    ('lung', '폐 청진하겠습니다', 'Chest', 'lung', 'resp cough dyspnea fever cardio all'),
    ('chest_perc', '흉부 타진하겠습니다', 'Chest', 'chest_perc', 'resp pneumonia effusion'),
    ('fremitus', '촉각 진탕 확인하겠습니다', 'Chest', 'fremitus', 'resp pneumonia'),
    ('heart', '심음 청진하겠습니다', 'Chest', 'heart', 'cardio palpitation thyroid dyspnea all'),
    ('pmi', '심첨박동 촉진하겠습니다', 'Chest', 'pmi', 'cardio heart failure'),
    ('breast', '유방 촉진하겠습니다', 'Breast', 'breast', 'breast mass'),
    ('gynecomastia', '여성형 유방 확인하겠습니다', 'Breast', 'gynecomastia', 'liver drug puberty'),
    # 복부
    ('abd_insp', '복부 시진하겠습니다', 'Abdomen', 'abd_insp', 'gi abdomen all'),
    ('bowel', '장음 청진하겠습니다', 'Abdomen', 'bowel', 'gi diarrhea thyroid obstruction'),
    ('abd_perc', '복부 타진하겠습니다', 'Abdomen', 'abd_perc', 'gi ascites distension'),
    ('abd_palp', '복부 촉진하겠습니다', 'Abdomen', 'abd_palp', 'gi abdomen all'),
    ('liver_spleen', '간·비장 촉진하겠습니다', 'Abdomen', 'liver_spleen', 'gi liver weight anemia fever'),
    ('murphy', '머피 징후 확인하겠습니다', 'Abdomen', 'murphy', 'ruq gallbladder gi'),
    ('rebound', '반발통 확인하겠습니다', 'Abdomen', 'rebound', 'gi abdomen peritonitis'),
    ('mcburney', '맥버니 압통 확인하겠습니다', 'Abdomen', 'mcburney', 'rlq appendicitis gi'),
    ('psoas', '요근 징후 확인하겠습니다', 'Abdomen', 'psoas', 'appendicitis'),
    ('rovsing', '로브싱 징후 확인하겠습니다', 'Abdomen', 'rovsing', 'rlq appendicitis'),
    ('obturator', '폐쇄근 징후 확인하겠습니다', 'Abdomen', 'obturator', 'appendicitis pelvic'),
    ('dre', '직장수지검사 하겠습니다', 'Abdomen', 'dre', 'rectal bleeding prostate appendicitis'),
    ('spo2', '산소포화도 측정하겠습니다', 'V/S', 'spo2', 'resp dyspnea copd hypoxia'),
    ('cva', '늑척추각 압통 확인하겠습니다', 'Abdomen', 'cva', 'urinary flank fever kidney'),
    ('shifting', '이동탁음 확인하겠습니다', 'Abdomen', 'shifting', 'ascites liver'),
    ('hernia', '서혜부 탈장 확인하겠습니다', 'Abdomen', 'hernia', 'groin'),
    ('genital', '외부 생식기 시진하겠습니다', 'Genitalia', 'genital', 'urinary peds genital'),
    ('testis', '고환 촉진하겠습니다', 'Genitalia', 'tanner', 'peds puberty scrotal'),
    # 사지·근골격
    ('periph', '하지 말초 진찰하겠습니다', 'Extremities', 'periph', 'cardio edema all'),
    ('pretibial', '경골앞 점액부종 확인하겠습니다', 'Extremities', 'pretibial', 'thyroid'),
    ('calf', '종아리 압통 확인하겠습니다', 'Extremities', 'calf', 'dvt edema leg'),
    ('spine', '척추 압통 확인하겠습니다', 'Extremities', 'spine', 'back pain msk'),
    ('scoliosis', '척추측만 확인하겠습니다', 'Extremities', 'scoliosis', 'back peds growth'),
    ('slr', '하지직거상 검사하겠습니다', 'Extremities', 'slr', 'back sciatica'),
    ('knee', '무릎 관절 압통 확인하겠습니다', 'Extremities', 'knee', 'knee joint msk'),
    ('shoulder', '어깨 관절 가동범위 검사하겠습니다', 'Extremities', 'shoulder', 'shoulder msk'),
    ('hand_joint', '손가락 관절 부종 확인하겠습니다', 'Extremities', 'hand_joint', 'joint arthritis'),
    ('phalen', '팔렌 검사하겠습니다', 'Extremities', 'phalen', 'numb hand carpal'),
    ('tinel', '티넬 징후 확인하겠습니다', 'Extremities', 'tinel', 'numb hand carpal'),
    # 신경
    ('gait', '보행 관찰하겠습니다', 'Neuro', 'gait', 'neuro elderly drug dizzy'),
    ('post_tremor', '자세성 떨림 확인하겠습니다', 'Neuro', 'post_tremor', 'tremor thyroid drug alcohol'),
    ('rest_tremor', '떨림·서동 관찰하겠습니다', 'Neuro', 'rest_tremor', 'tremor parkinson elderly'),
    ('rigidity', '근강직 검사하겠습니다', 'Neuro', 'rigidity', 'parkinson'),
    ('dtr', '심부건반사 검사하겠습니다', 'Neuro', 'dtr', 'neuro thyroid weakness'),
    ('babinski', '바빈스키 징후 확인하겠습니다', 'Neuro', 'babinski', 'neuro stroke'),
    ('power', '사지 근력 검사하겠습니다', 'Neuro', 'power', 'neuro weakness thyroid'),
    ('sensory', '사지 감각 검사하겠습니다', 'Neuro', 'sensory', 'numb neuro diabetes'),
    ('cerebellar', '소뇌 협조운동 검사하겠습니다', 'Neuro', 'cerebellar', 'dizzy neuro drug alcohol'),
    ('romberg', '롬베르그 검사하겠습니다', 'Neuro', 'romberg', 'dizzy neuro drug'),
    ('pronator', '회내근 표류 검사하겠습니다', 'Neuro', 'pronator', 'stroke neuro'),
    ('kernig', '커니그 징후 확인하겠습니다', 'Neuro', 'kernig', 'meningitis headache fever'),
    ('dix', '딕스-홀파이크 검사하겠습니다', 'Neuro', 'dix', 'vertigo dizzy'),
    ('asterixis', '퍼덕떨림 확인하겠습니다', 'Neuro', 'asterixis', 'liver confusion'),
    ('chvostek', '크보스텍 징후 확인하겠습니다', 'Neuro', 'chvostek', 'calcium tetany'),
    ('joint', '관절 부종·압통 확인하겠습니다', 'Extremities', 'joint', 'joint msk arthritis'),
    ('chest_wall', '흉벽 압통 확인하겠습니다', 'Chest', 'chest_wall', 'chest pain msk'),
    ('affect', '기분·정동 평가하겠습니다', 'Psych', 'affect', 'mood psych depression'),
]

EXAM_BY_ID = {e[0]: e for e in EXAM_BANK}
ALWAYS_EXAMS = ['vitals', 'general']
PEDS_ALWAYS_EXAMS = ['vitals', 'general', 'anthro']
THYROID_RE = r'(갑상|thyro|그레이브스|graves)'
# 이 진찰들은 감별진단(또는 주호소)에 해당 키워드가 있을 때만 LLM 후보에 올린다
CONDITIONAL_EXAMS = {'axillary_ln': r'(림프종|림프|감염|결핵|암|종양|유방)', 'inguinal_ln': r'(림프종|림프|감염|결핵|암|종양|성병)',
                     'eye_signs': THYROID_RE}

# v2 §6.3 카테고리별 진찰 우선순위(vitals·general 제외). v1 카테고리는 V1_TO_V2_EXAM_CAT로 대응
CATEGORY_EXAMS_V2 = {
    'weight_loss': ['thyroid', 'eye_signs', 'radial', 'skin_temp', 'post_tremor', 'thyroid_bruit', 'dtr', 'heart',
                    'power', 'conj', 'cervical_ln', 'eom', 'pretibial', 'abd_palp', 'liver_spleen', 'bowel', 'mental'],
    'insomnia': ['mental', 'sedation', 'cognitive', 'post_tremor', 'skin_temp', 'thyroid', 'orthostatic', 'insight',
                 'heart', 'conj'],
    'substance': ['mental', 'sedation', 'cognitive', 'orthostatic', 'post_tremor', 'skin_temp', 'nystagmus',
                  'dysarthria', 'gait', 'cerebellar', 'romberg', 'insight', 'rest_tremor', 'conj', 'liver_spleen'],
    'mood': ['mental', 'affect', 'insight', 'cognitive', 'thyroid', 'post_tremor', 'sedation', 'conj', 'heart'],
    'chest_pain': ['heart', 'lung', 'radial', 'jvp', 'periph', 'calf', 'abd_palp', 'skin_temp', 'chest_insp'],
    'cough_fever': ['pharynx', 'cervical_ln', 'lung', 'chest_perc', 'heart', 'ear', 'sinus', 'nasal', 'chest_insp',
                    'skin_rash'],
    'gi': ['abd_insp', 'bowel', 'abd_palp', 'liver_spleen', 'conj', 'cervical_ln', 'skin_turgor', 'abd_perc',
           'rebound'],
    'urinary': ['cva', 'abd_palp', 'abd_insp', 'abd_perc', 'genital', 'periph'],
    'msk': ['joint', 'spine', 'slr', 'power', 'sensory', 'dtr', 'gait', 'skin_rash'],
    'skin': ['skin_rash', 'oral', 'cervical_ln', 'joint', 'conj'],
    'neuro': ['power', 'sensory', 'dtr', 'babinski', 'pronator', 'face_sym', 'dysarthria', 'cerebellar', 'gait',
              'romberg', 'rest_tremor', 'post_tremor', 'rigidity', 'phalen', 'tinel'],
    'growth': ['anthro', 'growth_chart', 'growth_vel', 'body_prop', 'tanner', 'dysmorph', 'thyroid', 'striae',
               'abd_palp', 'liver_spleen', 'conj', 'heart', 'periph', 'gait', 'mental', 'vfield'],
}
V1_TO_V2_EXAM_CAT = {'weight': 'weight_loss', 'drug': 'substance', 'sleep': 'insomnia', 'cardio': 'chest_pain',
                     'resp': 'cough_fever', 'fever': 'cough_fever', 'gi': 'gi', 'neuro': 'neuro', 'urinary': 'urinary',
                     'skin': 'skin', 'msk': 'msk', 'mood': 'mood', 'growth': 'growth'}
CORE12 = ['vitals', 'general', 'mental', 'conj', 'thyroid', 'chest_insp', 'lung', 'heart', 'abd_insp', 'abd_palp',
          'liver_spleen', 'periph']


def category_exam_list(cat: str) -> list:
    v2 = V1_TO_V2_EXAM_CAT.get(cat)
    if v2 and v2 in CATEGORY_EXAMS_V2:
        return CATEGORY_EXAMS_V2[v2]
    return CATEGORY_EXAMS.get(cat, [])


# 카테고리 → 폴백 진찰 우선순위(v1; pain·thyroid·default만 직접 사용)
CATEGORY_EXAMS = {
    'thyroid':['thyroid', 'eye_signs', 'thyroid_bruit', 'post_tremor', 'dtr', 'radial', 'skin_temp', 'pretibial'],
    'weight': ['thyroid', 'eye_signs', 'skin_temp', 'post_tremor', 'heart', 'radial', 'dtr', 'thyroid_bruit',
               'conj', 'cervical_ln', 'bowel', 'power', 'liver_spleen'],
    'sleep': ['mental', 'sedation', 'cognitive', 'post_tremor', 'insight', 'skin_temp', 'nystagmus', 'dysarthria',
              'gait', 'orthostatic', 'thyroid', 'heart'],
    'drug': ['mental', 'sedation', 'post_tremor', 'nystagmus', 'dysarthria', 'cerebellar', 'gait', 'cognitive',
             'insight', 'skin_temp', 'orthostatic'],
    'growth': ['anthro', 'growth_chart', 'growth_vel', 'body_prop', 'tanner', 'dysmorph', 'thyroid', 'striae',
               'heart', 'abd_palp'],
    'pain': ['abd_palp', 'heart', 'lung', 'spine'],
    'resp': ['chest_insp', 'lung', 'chest_perc', 'heart', 'pharynx', 'cervical_ln', 'clubbing', 'periph'],
    'gi': ['abd_insp', 'bowel', 'abd_palp', 'liver_spleen', 'murphy', 'rebound', 'cva', 'conj', 'skin_turgor'],
    'neuro': ['mental', 'pupil', 'face_sym', 'power', 'dtr', 'sensory', 'cerebellar', 'romberg', 'gait', 'babinski',
              'nystagmus', 'neck_stiff'],
    'cardio': ['heart', 'lung', 'jvp', 'periph', 'radial', 'carotid', 'pmi', 'calf'],
    'urinary': ['cva', 'abd_palp', 'genital', 'abd_insp'],
    'fever': ['pharynx', 'cervical_ln', 'lung', 'heart', 'abd_palp', 'skin_rash', 'neck_stiff', 'ear'],
    'skin': ['skin_rash', 'cervical_ln', 'oral', 'skin_temp'],
    'msk': ['spine', 'knee', 'hand_joint', 'shoulder', 'gait', 'power'],
    'mood': ['mental', 'sedation', 'insight', 'cognitive', 'thyroid', 'post_tremor'],
    'default': ['conj', 'thyroid', 'lung', 'heart', 'abd_palp', 'periph', 'cervical_ln', 'mental'],
}

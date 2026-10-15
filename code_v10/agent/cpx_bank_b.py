"""v9 확장 CPX 은행 B: 소화기·비뇨·여성·유방(속쓰림, 구토, 토혈, 혈변·흑색변, 설사, 변비, 황달, 혈뇨, 하부요로증상,
월경 이상, 비정상 질 출혈, 질 분비물, 임신, 유방 덩이). 의학 지식으로 직접 작성(시판 CPX 교재 문구 복제 아님)."""
from __future__ import annotations

from .cpx import (U, I_FEVER, I_CHILL, I_NV_N, I_NV_V, I_MELENA, I_HEMATO, I_THY, I_OTHER, I_OP)

# ---------------------------------------------------------------- 이 모듈 공통 항목(같은 의미면 범주 간 공유)
I_HEMATEMESIS = ('ros_hematemesis', '토혈', r'피를?\s*토|토혈|토했|토한')
I_WT = ('gi_weight', '체중 감소', r'.')
I_ABD = ('ros_abd', '복통', r'.')
I_DIZZY = ('ros_dizzy', '어지럼', r'어지|핑')
I_SYNC = ('pa_syncope', '실신감', r'쓰러|정신|기절')
I_OLIG = ('ros_oliguria', '소변량 감소', r'소변|줄|안\s*나')
I_DRY = ('ros_dry_mouth', '입마름·갈증', r'입|마르|갈증')
I_NOFLATUS = ('ros_no_flatus', '방귀 안 나옴', r'방귀|가스')
I_DISTEN = ('ros_distension', '복부 팽만', r'부풀|부푸|빵빵|불러|더부룩|부른')
I_DYSURIA = ('ur_dysuria', '배뇨통', r'.')
I_FREQ = ('ur_freq', '빈뇨', r'자주')
I_URG = ('ur_urgency', '절박뇨', r'급|참')
I_ANTICOAG = ('he_anticoag', '항응고·항혈소판제', r'.')
I_NSAID = ('gi_nsaid', '진통제·소염제', r'진통제|소염|아스피린|약')
I_LMP = ('wm_lmp', 'LMP', r'.')
I_HORMONE = ('mn_hormone', '호르몬제', r'호르몬|갱년기')
I_OCP = ('mn_ocp', '경구피임약', r'피임')
I_PELVIC = ('vb_pelvic_pain', '하복부 통증', r'.')
I_POSTCOITAL = ('mn_postcoital', '성교 후 출혈', r'관계|후')
I_INTERMEN = ('mn_intermenstrual', '부정출혈', r'아닐|중간|비치|피|상관')

CPX_EXT = {}

# ---------------------------------------------------------------- 소화기
CPX_EXT['heartburn'] = {
    'onset_q': '언제부터 속이 쓰리셨어요?',
    'units': [
        U('hb_site', 'core', 1, '어디가 쓰리거나 아프세요?', [('hb_site', '부위', r'.')], 'gi'),
        U('hb_char', 'core', 1, '어떤 느낌으로 불편하세요?', [('hb_char', '양상', r'.')], 'gi'),
        U('hb_meal', 'core', 1, '빈속과 식후 중 언제 심하세요?', [('hb_meal', '식사 연관', r'.')], 'gi'),
        U('hb_lying', 'core', 1, '눕거나 숙이면 더 심해지나요?',
          [('hb_lying', '누우면 악화', r'눕|누우|누울|누워'), ('hb_bend', '숙이면 악화', r'숙이|숙일|숙여')], 'gi'),
        U('hb_regurg', 'core', 1, '신물이 목으로 올라오나요?', [('gi_regurg', '역류', r'.')], 'gi'),
        U('hb_night', 'core', 2, '자다가 속이 쓰려 깬 적 있나요?', [('hb_night', '야간 통증', r'.')], 'gi'),
        U('hb_food', 'core', 2, '맵거나 기름진 음식에 심해지나요?', [('hb_food', '음식 악화', r'.')], 'gi'),
        U('hb_dysphagia', 'red', 1, '삼킬 때 걸리거나 아픈가요?',
          [('gi_dysphagia', '연하곤란', r'걸리|걸려'), ('gi_odynophagia', '연하통', r'아프|아파')], 'gi', safety=True),
        U('hb_bleed', 'red', 1, '변이 검거나 피를 토한 적 있나요?', [I_MELENA, I_HEMATEMESIS], 'gi', safety=True),
        U('hb_weight', 'red', 1, '모르게 살이 빠지셨나요?', [I_WT], 'gen', safety=True),
        U('hb_cp', 'red', 1, '움직일 때 가슴이 조이듯 아픈가요?', [('hb_exert_cp', '운동 시 흉통', r'.')], 'cv', safety=True),
        U('hb_vomit', 'red', 2, '토하거나 메스꺼우세요?', [I_NV_V, I_NV_N], 'gi'),
        U('hb_nsaid', 'hx', 1, '진통제나 아스피린을 자주 드세요?',
          [I_NSAID, ('hb_aspirin', '아스피린', r'아스피린')], 'meds'),
        U('hb_hx', 'hx', 2, '위궤양이나 헬리코박터 진단받았나요?',
          [('pmh_ulcer', '위궤양', r'궤양|위염|위'), ('pmh_hpylori', '헬리코박터', r'헬리코|균')], 'hx'),
        U('hb_fh', 'fh', 2, '가족 중 위암 앓은 분 있나요?', [('fh_gi_ca', '위장관암 가족력', r'암|어머니|아버지|가족')], 'fh'),
    ],
    'replace': {'fh_open': 'hb_fh'}, 'demote': {'hx_htn_dm': 2},
    'exams': ['abd_palp', 'abd_insp', 'bowel', 'conj', 'cervical_ln', 'heart', 'liver_spleen'],
}

CPX_EXT['vomiting'] = {
    'onset_q': '언제부터 토하셨어요?',
    'units': [
        U('vo_content', 'core', 1, '토한 것은 어떤 색이고 무엇이었나요?', [('vo_content', '토물 성상', r'.')], 'gi'),
        U('vo_freq', 'core', 1, '하루에 몇 번이나 토하세요?', [('vo_freq', '횟수', r'.')], 'gi'),
        U('vo_blood', 'red', 1, '토한 것에 피가 섞였나요?', [('ros_hematemesis', '토혈', r'.')], 'gi', safety=True),
        U('vo_abd', 'core', 1, '배가 아프세요?', [I_ABD], 'gi'),
        U('vo_diarrhea', 'core', 1, '설사도 하시나요?', [('ros_diarrhea', '설사', r'.')], 'gi'),
        U('vo_obst', 'red', 1, '방귀가 안 나오거나 배가 부푸나요?', [I_NOFLATUS, I_DISTEN], 'gi', safety=True),
        U('vo_neuro', 'red', 1, '머리가 아프거나 목이 뻣뻣한가요?',
          [('ros_headache', '두통', r'머리|두통'), ('ha_neck', '경부 강직', r'목|뻣뻣')], 'neuro', safety=True),
        U('vo_dehyd', 'red', 1, '소변이 줄거나 입이 마르나요?', [I_OLIG, I_DRY], 'gen', safety=True),
        U('vo_lmp', 'core', 1, '마지막 생리는 언제였어요?', [I_LMP], 'wm'),
        U('vo_meal', 'core', 2, '식사하고 얼마 뒤에 토하세요?', [('vo_meal', '식사 연관', r'.')], 'gi'),
        U('vo_fever', 'red', 2, '열이나 오한이 있나요?', [I_FEVER, I_CHILL], 'gen'),
        U('vo_vertigo', 'red', 2, '빙빙 도는 어지럼이 있나요?', [('vo_vertigo', '회전성 어지럼', r'.')], 'neuro'),
        U('vo_food', 'core', 2, '같은 음식 먹고 아픈 사람이 있나요?', [('vo_contact', '음식·접촉력', r'.')], 'gi'),
        U('vo_drug', 'hx', 2, '최근 새로 드신 약이 있나요?', [('vo_newdrug', '새 약물', r'.')], 'meds'),
        U('vo_op', 'hx', 1, '배 수술받은 적 있으세요?', [I_OP], 'hx'),
    ],
    'women_only': {'vo_lmp'}, 'demote': {'fh_open': 3},
    'exams': ['abd_insp', 'bowel', 'abd_palp', 'abd_perc', 'skin_turgor', 'neck_stiff', 'nystagmus'],
}

CPX_EXT['hematemesis'] = {
    'onset_q': '언제 피를 토하셨어요?',
    'units': [
        U('he_amount', 'core', 1, '피를 얼마나 토하셨어요?', [('he_amount', '양', r'.')], 'gi'),
        U('he_color', 'core', 1, '토한 피 색깔이 어땠어요?', [('he_color', '색(선홍·커피찌꺼기)', r'.')], 'gi'),
        U('he_retch', 'core', 1, '피 전에 심하게 헛구역질했나요?', [('he_retch', '선행 구역·구토', r'.')], 'gi'),
        U('he_ongoing', 'red', 1, '지금도 계속 피를 토하나요?', [('he_ongoing', '지속 출혈', r'.')], 'gi', safety=True),
        U('he_melena', 'red', 1, '변이 까맣게 나오나요?', [I_MELENA], 'gi', safety=True),
        U('he_shock', 'red', 1, '어지럽거나 쓰러질 것 같았나요?', [I_DIZZY, I_SYNC], 'neuro', safety=True),
        U('he_abd', 'core', 1, '배가 아프거나 쓰리세요?',
          [('ros_abd', '복통', r'배|아프|아파'), ('gi_heartburn', '속쓰림', r'쓰리|속')], 'gi'),
        U('he_cough', 'red', 2, '기침할 때 피가 나왔나요?', [('he_hemoptysis', '객혈 감별', r'.')], 'resp'),
        U('he_weight', 'red', 2, '모르게 살이 빠지셨나요?', [I_WT], 'gen', safety=True),
        U('he_anticoag', 'hx', 1, '피를 묽게 하는 약을 드세요?', [I_ANTICOAG], 'meds', safety=True),
        U('he_nsaid', 'hx', 1, '진통제나 소염제를 자주 드세요?', [('gi_nsaid', '진통제·소염제', r'.')], 'meds'),
        U('he_liver', 'hx', 1, '간염이나 간경화가 있으세요?',
          [('pmh_hep', '간염', r'간염'), ('pmh_cirrhosis', '간경화', r'간경|경화|간')], 'hx'),
        U('he_ulcer', 'hx', 2, '위궤양을 앓은 적 있으세요?', [('pmh_ulcer', '위궤양', r'.')], 'hx'),
    ],
    'replace': {'sh_smoke_alc': 'sh_alc_smoke'}, 'demote': {'fh_open': 3},
    'exams': ['conj', 'orthostatic', 'abd_palp', 'spider', 'liver_spleen', 'shifting', 'cap_refill'],
}

CPX_EXT['hematochezia'] = {
    'onset_q': '언제부터 변에 피가 보였어요?',
    'units': [
        U('hz_color', 'core', 1, '피 색깔이 어떤가요?', [('hz_color', '색(선홍·검붉음·검정)', r'.')], 'gi'),
        U('hz_amount', 'core', 1, '피가 얼마나 나오나요?', [('hz_amount', '양', r'.')], 'gi'),
        U('hz_mix', 'core', 1, '피가 변에 섞여 나오나요?', [('hz_mixed', '섞임 여부', r'.')], 'gi'),
        U('hz_pain', 'core', 1, '변 볼 때 항문이 아프세요?', [('hz_anal_pain', '배변 시 항문통', r'.')], 'gi'),
        U('hz_habit', 'core', 1, '배변 습관이 최근 바뀌었나요?', [('hz_habit', '배변 습관 변화', r'.')], 'gi'),
        U('hz_shock', 'red', 1, '어지럽거나 쓰러질 것 같았나요?', [I_DIZZY, I_SYNC], 'neuro', safety=True),
        U('hz_weight', 'red', 1, '모르게 살이 빠지셨나요?', [I_WT], 'gen', safety=True),
        U('hz_thin', 'core', 2, '변이 가늘거나 덜 본 느낌인가요?',
          [('hz_thin', '가는 변', r'가늘'), ('hz_tenesmus', '잔변감', r'덜|남|잔변|시원')], 'gi'),
        U('hz_abd', 'core', 2, '배가 아프세요?', [I_ABD], 'gi'),
        U('hz_mucus', 'red', 2, '변에 코 같은 점액이 섞이나요?', [('di_mucus', '점액변', r'.')], 'gi'),
        U('hz_fever', 'red', 2, '열이나 오한이 있나요?', [I_FEVER, I_CHILL], 'gen'),
        U('hz_hemorrhoid', 'hx', 1, '치질이 있다고 들으셨나요?', [('pmh_hemorrhoid', '치핵', r'.')], 'hx'),
        U('hz_drug', 'hx', 1, '피를 묽게 하는 약이나 진통제 드세요?',
          [('he_anticoag', '항응고·항혈소판제', r'혈전|아스피린|묽|와파린|항응고|피'), ('gi_nsaid', '진통제', r'진통제|소염')],
          'meds', safety=True),
        U('hz_scope', 'hx', 2, '대장내시경 받아 보셨어요?', [('hz_colonoscopy', '대장내시경력', r'.')], 'hx'),
        U('hz_fh', 'fh', 1, '가족 중 대장암 앓은 분 있나요?', [('fh_crc', '대장암 가족력', r'암|대장|어머니|아버지|가족')], 'fh'),
    ],
    'replace': {'fh_open': 'hz_fh'}, 'demote': {'hx_htn_dm': 2},
    'exams': ['abd_insp', 'bowel', 'abd_palp', 'conj', 'orthostatic', 'liver_spleen', 'inguinal_ln'],
}

CPX_EXT['diarrhea'] = {
    'onset_q': '언제부터 설사를 하셨어요?',
    'units': [
        U('di_freq', 'core', 1, '하루에 몇 번 정도 보세요?', [('di_freq', '횟수', r'.')], 'gi'),
        U('di_char', 'core', 1, '변이 물처럼 나오나요?', [('di_watery', '변 양상', r'.')], 'gi'),
        U('di_blood', 'red', 1, '변에 피나 코 같은 게 섞이나요?', [I_HEMATO, ('di_mucus', '점액', r'코|점액|미끈')], 'gi',
          safety=True),
        U('di_fever', 'red', 1, '열이나 오한이 있나요?', [I_FEVER, I_CHILL], 'gen', safety=True),
        U('di_abd', 'core', 1, '배가 아프세요?', [I_ABD], 'gi'),
        U('di_vomit', 'core', 1, '토하거나 메스꺼우세요?', [I_NV_V, I_NV_N], 'gi'),
        U('di_food', 'core', 1, '의심되는 음식이나 여행이 있나요?',
          [('gi_food', '음식', r'음식|먹'), ('gi_travel', '여행', r'여행')], 'gi'),
        U('di_dehyd', 'red', 1, '소변이 줄거나 입이 마르나요?', [I_OLIG, I_DRY], 'gen', safety=True),
        U('di_contact', 'core', 2, '주변에 같이 설사하는 사람 있나요?', [('di_contact', '접촉력', r'.')], 'gi'),
        U('di_night', 'core', 2, '자다가도 설사 때문에 깨나요?', [('di_nocturnal', '야간 설사', r'.')], 'gi'),
        U('di_weight', 'red', 2, '모르게 살이 빠지셨나요?', [I_WT], 'gen', safety=True),
        U('di_thy', 'red', 3, '더위를 타거나 땀이 많아졌나요?', [('wl_heat', '더위 불내성', r'더위|덥'), ('wl_sweat', '발한', r'땀')],
          'gen'),
        U('di_milk', 'core', 3, '우유를 먹으면 심해지나요?', [('di_lactose', '유당 연관', r'.')], 'gi'),
        U('di_abx', 'hx', 1, '최근 항생제를 드신 적 있나요?', [('di_abx', '최근 항생제', r'.')], 'meds'),
    ],
    'demote': {'fh_open': 3, 'hx_htn_dm': 2},
    'exams': ['abd_insp', 'bowel', 'abd_palp', 'abd_perc', 'skin_turgor', 'orthostatic', 'thyroid'],
}

CPX_EXT['constipation'] = {
    'onset_q': '언제부터 변을 보기 힘드셨어요?',
    'units': [
        U('cn_freq', 'core', 1, '변은 며칠에 한 번 보세요?', [('cn_freq', '배변 횟수', r'.')], 'gi'),
        U('cn_form', 'core', 1, '변이 딱딱하거나 힘을 많이 주나요?',
          [('cn_hard', '굳은 변', r'딱딱|굳|토끼|단단'), ('cn_strain', '배변 시 힘줌', r'힘')], 'gi'),
        U('cn_blood', 'red', 1, '변에 피가 묻거나 검게 나오나요?', [I_HEMATO, I_MELENA], 'gi', safety=True),
        U('cn_thin', 'red', 1, '변이 연필처럼 가늘어졌나요?', [('hz_thin', '가는 변', r'.')], 'gi', safety=True),
        U('cn_abd', 'core', 1, '배가 아프거나 더부룩하세요?',
          [('ros_abd', '복통', r'아프|아파|통증'), ('cn_bloat', '팽만', r'더부룩|빵빵|가스|부풀')], 'gi'),
        U('cn_obst', 'red', 1, '방귀가 안 나오거나 토하세요?', [I_NOFLATUS, I_NV_V], 'gi', safety=True),
        U('cn_weight', 'red', 1, '모르게 살이 빠지셨나요?', [I_WT], 'gen', safety=True),
        U('cn_alt', 'core', 2, '설사와 변비가 번갈아 오나요?', [('cn_alternate', '설사·변비 교대', r'.')], 'gi'),
        U('cn_relief', 'core', 2, '변을 보면 배가 편해지나요?', [('gi_relief', '배변 후 완화', r'.')], 'gi'),
        U('cn_hypo', 'red', 2, '전보다 추위를 많이 타세요?', [('ft_cold', '추위 불내성', r'.')], 'endo'),
        U('cn_meds', 'hx', 1, '진통제, 철분제, 혈압약 중 드시는 게 있나요?',
          [('cn_opioid', '진통제', r'진통제|마약'), ('cn_iron', '철분제', r'철분|빈혈'), ('cn_ccb', '혈압약', r'혈압')], 'hx'),
        U('cn_diet', 'sh', 2, '물이나 채소는 충분히 드세요?',
          [('cn_water', '수분 섭취', r'물'), ('cn_fiber', '섬유질 섭취', r'채소|야채|과일|섬유')], 'sh'),
        U('cn_fh', 'fh', 1, '가족 중 대장암 앓은 분 있나요?', [('fh_crc', '대장암 가족력', r'암|대장|어머니|아버지|가족')], 'fh'),
    ],
    'replace': {'fh_open': 'cn_fh'},
    'exams': ['abd_insp', 'bowel', 'abd_palp', 'abd_perc', 'hernia', 'thyroid', 'dtr'],
}

CPX_EXT['jaundice'] = {
    'onset_q': '언제부터 노랗게 되셨어요?',
    'units': [
        U('ja_urine', 'core', 1, '소변 색이 진해졌나요?', [('ja_dark_urine', '진한 소변', r'.')], 'gu'),
        U('ja_stool', 'core', 1, '변 색이 하얗게 변했나요?', [('ja_pale_stool', '회색변', r'.')], 'gi'),
        U('ja_pain', 'core', 1, '오른쪽 윗배가 아프세요?', [('ja_ruq', '우상복부 통증', r'.')], 'gi'),
        U('ja_fever', 'red', 1, '열이나 오한이 있나요?', [I_FEVER, I_CHILL], 'gen', safety=True),
        U('ja_weight', 'red', 1, '모르게 살이 빠지셨나요?', [I_WT], 'gen', safety=True),
        U('ja_confusion', 'red', 1, '정신이 흐리거나 자꾸 졸리나요?',
          [('ja_confusion', '의식 저하', r'정신|헷갈|멍|흐리'), ('ja_drowsy', '기면', r'졸')], 'neuro', safety=True),
        U('ja_itch', 'core', 2, '몸이 가려우세요?', [('ja_pruritus', '가려움', r'.')], 'skin'),
        U('ja_appetite', 'core', 2, '입맛이 없거나 메스꺼우세요?',
          [('ros_anorexia', '식욕 저하', r'입맛|식욕|먹'), I_NV_N], 'gi'),
        U('ja_bleed', 'red', 2, '멍이 잘 들거나 피가 잘 나나요?',
          [('ja_bruise', '멍', r'멍'), ('ja_bleed', '출혈 경향', r'피|코피|잇몸')], 'gen', safety=True),
        U('ja_belly', 'red', 2, '배가 불러 오나요?', [('ja_ascites', '복부 팽만(복수)', r'.')], 'gi'),
        U('ja_hep', 'hx', 1, '간염이나 담석이 있으세요?',
          [('pmh_hep', '간염', r'간염|간'), ('pmh_gallstone', '담석', r'담석|쓸개|돌')], 'hx'),
        U('ja_drug', 'hx', 1, '최근 한약이나 새 약을 드셨나요?',
          [('ja_herbal', '한약·건강식품', r'한약|건강|즙'), ('ja_newdrug', '새 약', r'약')], 'meds'),
        U('ja_risk', 'hx', 2, '수혈이나 문신을 받은 적 있나요?',
          [('ja_transfusion', '수혈', r'수혈'), ('ja_tattoo', '문신', r'문신')], 'hx'),
        U('ja_food', 'sh', 2, '날음식을 먹거나 여행 가셨나요?',
          [('ja_raw', '날음식', r'회|날|굴|조개'), ('gi_travel', '여행', r'여행')], 'sh'),
        U('ja_fh', 'fh', 2, '가족 중 간 질환 있는 분 있나요?', [('fh_liver', '간질환 가족력', r'간|어머니|아버지|가족')], 'fh'),
    ],
    'replace': {'fh_open': 'ja_fh', 'sh_smoke_alc': 'sh_alc_smoke'}, 'demote': {'hx_htn_dm': 2},
    'exams': ['conj', 'abd_palp', 'liver_spleen', 'murphy', 'shifting', 'spider', 'asterixis'],
}

# ---------------------------------------------------------------- 비뇨
CPX_EXT['hematuria'] = {
    'onset_q': '언제부터 소변에 피가 보였어요?',
    'units': [
        U('hu_color', 'core', 1, '소변 색이 어떤가요?', [('hu_color', '색', r'.')], 'gu'),
        U('hu_clot', 'core', 1, '핏덩어리가 섞여 나오나요?', [('hu_clot', '혈괴', r'.')], 'gu'),
        U('hu_pain', 'core', 1, '소변 볼 때 아프세요?', [I_DYSURIA], 'gu'),
        U('hu_flank', 'core', 1, '옆구리가 쥐어짜듯 아프세요?', [('hu_colic', '옆구리 산통', r'.')], 'gu'),
        U('hu_fever', 'red', 1, '열이나 오한이 있나요?', [I_FEVER, I_CHILL], 'gen', safety=True),
        U('hu_weight', 'red', 1, '모르게 살이 빠지셨나요?', [I_WT], 'gen', safety=True),
        U('hu_timing', 'core', 2, '소변 처음, 끝, 내내 중 언제 붉나요?', [('hu_timing', '혈뇨 시기', r'.')], 'gu'),
        U('hu_freq', 'core', 2, '소변이 자주 마렵거나 급하세요?', [I_FREQ, I_URG], 'gu'),
        U('hu_uri', 'core', 2, '최근 목감기를 앓으셨나요?', [('hu_uri', '선행 감염', r'.')], 'gen'),
        U('hu_foam', 'red', 2, '소변에 거품이 많이 생기나요?', [('ed_foam', '거품뇨', r'.')], 'gu'),
        U('hu_edema', 'red', 2, '얼굴이나 다리가 붓나요?',
          [('ft_face_edema', '얼굴 부종', r'얼굴|눈'), ('ft_leg_edema', '다리 부종', r'다리|발')], 'gen'),
        U('hu_trauma', 'red', 2, '최근 다치거나 심하게 운동했나요?',
          [('hu_trauma', '외상', r'다치|부딪|넘어|맞'), ('hu_exercise', '격한 운동', r'운동|뛰|마라톤')], 'gen'),
        U('hu_anticoag', 'hx', 1, '피를 묽게 하는 약을 드세요?', [I_ANTICOAG], 'meds', safety=True),
        U('hu_hx', 'hx', 2, '전에 결석이나 콩팥병이 있었나요?',
          [('pmh_stone', '결석', r'결석|돌'), ('pmh_kidney', '콩팥병', r'콩팥|신장')], 'hx'),
        U('hu_dye', 'sh', 2, '일하며 염료나 화학약품을 다루나요?', [('hu_dye', '직업 노출', r'.')], 'sh'),
    ],
    'promote': {'sh_smoke_alc': 1}, 'demote': {'hx_htn_dm': 2},
    'exams': ['cva', 'abd_palp', 'abd_perc', 'periph', 'genital', 'abd_insp', 'conj'],
}

CPX_EXT['luts'] = {
    'onset_q': '언제부터 소변 보기 불편하셨어요?',
    'units': [
        U('lu_stream', 'core', 1, '소변 줄기가 약해졌나요?', [('lu_weak', '약한 소변 줄기', r'.')], 'gu'),
        U('lu_hesit', 'core', 1, '소변이 바로 안 나오거나 끊기나요?',
          [('lu_hesitancy', '지연뇨', r'안\s*나|기다|한참|바로'), ('lu_intermit', '단절뇨', r'끊')], 'gu'),
        U('lu_resid', 'core', 1, '소변 본 뒤에도 남은 느낌인가요?', [('lu_incomplete', '잔뇨감', r'.')], 'gu'),
        U('lu_noct', 'core', 1, '밤에 소변 때문에 몇 번 깨세요?', [('lu_nocturia', '야간뇨', r'.')], 'gu'),
        U('lu_freq', 'core', 1, '소변이 자주 마렵거나 급하세요?', [I_FREQ, I_URG], 'gu'),
        U('lu_leak', 'core', 1, '소변이 새는 적이 있나요?', [('lu_incont', '요실금', r'.')], 'gu',
          follow=('lu_incont_type', '요실금 유형', '기침할 때나 참기 힘들 때 새나요?', r'(기침|재채기|웃|뛰|급|참)', 'lu_incont')),
        U('lu_retention', 'red', 1, '소변이 아예 안 나온 적 있나요?', [('lu_retention', '요폐', r'.')], 'gu', safety=True),
        U('lu_hematuria', 'red', 2, '소변에 피가 섞이나요?', [('ur_hematuria', '혈뇨', r'.')], 'gu', safety=True),
        U('lu_dysuria', 'red', 2, '소변 볼 때 아프세요?', [I_DYSURIA], 'gu'),
        U('lu_fever', 'red', 2, '열이나 오한이 있나요?', [I_FEVER, I_CHILL], 'gen'),
        U('lu_bone', 'red', 2, '허리나 뼈가 아프세요?', [('lu_bone', '뼈 통증', r'.')], 'msk', safety=True),
        U('lu_meds', 'hx', 1, '감기약이나 이뇨제를 드세요?',
          [('lu_antihist', '감기약·항히스타민', r'감기|콧물|알레르기'), ('lu_diuretic', '이뇨제', r'이뇨|소변')], 'meds'),
        U('lu_hx', 'hx', 2, '전립선이나 신경 질환 진단받았나요?',
          [('pmh_prostate', '전립선 질환', r'전립선'), ('pmh_neuro', '신경 질환', r'신경|디스크|파킨슨|중풍')], 'hx'),
        U('lu_fluid', 'sh', 2, '저녁에 물이나 커피를 많이 드세요?',
          [('lu_evening_fluid', '저녁 수분', r'물'), ('lu_evening_caff', '저녁 카페인', r'커피|차|술')], 'sh'),
    ],
    'promote': {'hx_htn_dm': 1}, 'demote': {'fh_open': 2},
    'exams': ['abd_palp', 'abd_perc', 'genital', 'cva', 'sensory', 'spine', 'periph'],
}

# ---------------------------------------------------------------- 여성
CPX_EXT['menstrual'] = {
    'onset_q': '언제부터 생리가 이상했어요?',
    'female': True,
    'units': [
        U('mn_lmp', 'core', 1, '마지막 생리는 언제였어요?', [I_LMP], 'wm'),
        U('mn_cycle', 'core', 1, '생리 주기는 며칠 간격인가요?', [('mn_cycle', '주기', r'.')], 'wm'),
        U('mn_amount', 'core', 1, '생리 양이나 기간이 변했나요?',
          [('wm_amount', '월경량', r'양|량|많|적|줄|늘'), ('wm_duration', '월경 기간·주기', r'기간|짧|길|주기|불규칙')], 'wm'),
        U('mn_pain', 'core', 1, '생리통은 언제 얼마나 아프세요?', [('mn_dysmen', '월경통', r'.')], 'wm'),
        U('mn_inter', 'red', 1, '생리 아닐 때나 관계 후 피가 비치나요?', [I_INTERMEN, I_POSTCOITAL], 'wm', safety=True),
        U('mn_weight', 'core', 1, '최근 체중이 많이 변했나요?', [('ft_weight', '체중 변화', r'.')], 'gen'),
        U('mn_dizzy', 'red', 1, '일어설 때 어지러우세요?', [('ros_dizzy', '기립 어지럼', r'.')], 'neuro', safety=True),
        U('mn_galact', 'core', 2, '유두에서 젖 같은 게 나오나요?', [('mn_galactorrhea', '유즙 분비', r'.')], 'endo'),
        U('mn_hirsut', 'core', 2, '털이 많아지거나 여드름이 늘었나요?',
          [('mn_hirsutism', '다모증', r'털'), ('mn_acne', '여드름', r'여드름|뾰루지')], 'skin'),
        U('mn_stress', 'core', 2, '스트레스나 심한 운동을 하셨나요?',
          [('sh_stress', '스트레스', r'스트레스|힘들|힘든'), ('mn_exercise', '과도한 운동·다이어트', r'운동|다이어트')], 'sh'),
        U('mn_thy', 'red', 2, '더위나 추위를 유난히 타세요?',
          [('wl_heat', '더위 불내성', r'더위|덥'), ('ft_cold', '추위 불내성', r'추위|춥')], 'endo'),
        U('mn_bleed', 'red', 3, '멍이 잘 들거나 코피가 잘 나나요?',
          [('ja_bruise', '멍', r'멍'), ('mn_epistaxis', '코피', r'코피|피')], 'gen'),
        U('mn_contra', 'hx', 1, '피임약이나 호르몬제를 드세요?', [I_OCP, I_HORMONE], 'meds'),
        U('mn_ob', 'hx', 2, '임신이나 출산한 적 있으세요?', [('mn_ob', '산과력', r'.')], 'hx'),
    ],
    'demote': {'hx_htn_dm': 2},
    'exams': ['abd_palp', 'conj', 'thyroid', 'genital', 'breast', 'acanthosis', 'abd_insp'],
}

CPX_EXT['vag_bleeding'] = {
    'onset_q': '언제부터 피가 비치셨어요?',
    'female': True,
    'units': [
        U('vb_menop', 'core', 1, '폐경은 되셨나요?', [('vb_menopause', '폐경 여부', r'.')], 'wm'),
        U('vb_lmp', 'core', 1, '마지막 생리는 언제였어요?', [I_LMP], 'wm'),
        U('vb_amount', 'core', 1, '하루에 패드를 몇 개 쓰세요?', [('vb_pads', '출혈량(패드)', r'.')], 'wm'),
        U('vb_clot', 'core', 1, '핏덩어리가 나오나요?', [('vb_clot', '혈괴', r'.')], 'wm'),
        U('vb_timing', 'core', 1, '생리와 상관없이 피가 나나요?', [('mn_intermenstrual', '부정출혈', r'.')], 'wm'),
        U('vb_postcoital', 'red', 1, '관계 후에 피가 비치나요?', [('mn_postcoital', '성교 후 출혈', r'.')], 'wm', safety=True),
        U('vb_pain', 'core', 1, '아랫배가 아프세요?', [I_PELVIC], 'wm'),
        U('vb_shock', 'red', 1, '어지럽거나 쓰러질 것 같았나요?', [I_DIZZY, I_SYNC], 'neuro', safety=True),
        U('vb_discharge', 'core', 2, '냉이 늘거나 냄새가 나나요?',
          [('vd_discharge', '분비물 증가', r'냉|분비'), ('vd_odor', '냄새', r'냄새')], 'wm'),
        U('vb_weight', 'red', 2, '모르게 살이 빠지셨나요?', [I_WT], 'gen', safety=True),
        U('vb_anticoag', 'hx', 1, '피를 묽게 하는 약을 드세요?', [I_ANTICOAG], 'meds', safety=True),
        U('vb_hrt', 'hx', 1, '호르몬제나 피임약을 드세요?', [I_HORMONE, I_OCP], 'meds'),
        U('vb_pap', 'hx', 1, '자궁경부암 검사는 언제 받으셨어요?', [('vb_pap', '자궁경부 검사력', r'.')], 'hx'),
        U('vb_hx', 'hx', 2, '자궁근종이나 혹이 있다고 들었나요?', [('pmh_myoma', '근종·자궁 질환', r'.')], 'hx'),
    ],
    'women_only': {'vb_lmp'}, 'demote': {'fh_open': 2},
    'exams': ['conj', 'abd_palp', 'genital', 'orthostatic', 'abd_insp', 'inguinal_ln', 'cap_refill'],
}

CPX_EXT['vag_discharge'] = {
    'onset_q': '언제부터 분비물이 늘었어요?',
    'female': True,
    'units': [
        U('vd_color', 'core', 1, '분비물 색깔이 어떤가요?', [('vd_color', '색', r'.')], 'wm'),
        U('vd_odor', 'core', 1, '냄새가 나나요?', [('vd_odor', '냄새', r'.')], 'wm'),
        U('vd_itch', 'core', 1, '가렵거나 따가우세요?',
          [('vd_itch', '가려움', r'가렵|가려'), ('vd_burn', '작열감', r'따가|화끈|쓰라')], 'wm'),
        U('vd_pelvic', 'red', 1, '아랫배가 아프세요?', [I_PELVIC], 'wm', safety=True),
        U('vd_fever', 'red', 1, '열이나 오한이 있나요?', [I_FEVER, I_CHILL], 'gen', safety=True),
        U('vd_bleed', 'red', 1, '관계 후나 생리 아닐 때 피가 비치나요?', [I_POSTCOITAL, I_INTERMEN], 'wm', safety=True),
        U('vd_consist', 'core', 2, '덩어리지거나 거품이 있나요?',
          [('vd_curd', '비지 같은 양상', r'덩어리|비지|치즈|하얀'), ('vd_froth', '거품', r'거품')], 'wm'),
        U('vd_dysuria', 'core', 2, '소변 볼 때 아프세요?', [I_DYSURIA], 'gu'),
        U('vd_dyspar', 'core', 2, '관계할 때 아프세요?', [('vd_dyspareunia', '성교통', r'.')], 'wm'),
        U('vd_lmp', 'core', 2, '마지막 생리는 언제였어요?', [I_LMP], 'wm'),
        U('vd_partner', 'sh', 1, '최근 새로운 상대와 관계가 있었나요?', [('vd_new_partner', '새 성 상대', r'.')], 'sh'),
        U('vd_partner_sx', 'sh', 2, '상대방도 비슷한 증상이 있나요?', [('vd_partner_sx', '상대 증상', r'.')], 'sh'),
        U('vd_abx', 'hx', 1, '최근 항생제를 드신 적 있나요?', [('di_abx', '최근 항생제', r'.')], 'meds'),
        U('vd_hx', 'hx', 2, '전에 질염이나 성병이 있었나요?',
          [('pmh_vaginitis', '질염', r'질염|염증'), ('pmh_sti', '성매개감염', r'성병|임질|클라미디아')], 'hx'),
        U('vd_douche', 'sh', 3, '질 세정제를 자주 쓰세요?', [('vd_douche', '질 세정', r'.')], 'sh'),
    ],
    'women_only': {'vd_lmp'}, 'promote': {'hx_htn_dm': 1}, 'demote': {'fh_open': 3, 'sh_caffeine': 3},
    'exams': ['genital', 'inguinal_ln', 'abd_palp', 'abd_insp', 'skin_rash', 'cva', 'oral'],
}

CPX_EXT['pregnancy'] = {
    'onset_q': '언제 임신을 알게 되셨어요?',
    'female': True,
    'units': [
        U('pg_lmp', 'core', 1, '마지막 생리는 언제였어요?', [I_LMP], 'wm'),
        U('pg_test', 'core', 1, '임신 검사는 어떻게 나왔나요?', [('pg_test', '임신 검사 결과', r'.')], 'wm'),
        U('pg_bleed', 'red', 1, '아래로 피가 비친 적 있나요?', [('pg_bleed', '질출혈', r'.')], 'wm', safety=True),
        U('pg_pain', 'red', 1, '아랫배가 아프세요?', [I_PELVIC], 'wm', safety=True,
          follow=('pg_pain_side', '편측 통증', '한쪽으로 치우쳐 아프세요?', r'(오른|왼|한쪽)')),
        U('pg_shock', 'red', 1, '어지럽거나 쓰러질 것 같았나요?', [I_DIZZY, I_SYNC], 'neuro', safety=True),
        U('pg_nv', 'core', 1, '입덧은 얼마나 심하세요?', [('pg_nv', '입덧 정도', r'.')], 'gi'),
        U('pg_intake', 'red', 1, '물도 못 마실 만큼 토하세요?', [('pg_hyperemesis', '심한 구토', r'.')], 'gi', safety=True),
        U('pg_regular', 'core', 2, '생리 주기는 규칙적이었나요?', [('mn_cycle', '주기', r'.')], 'wm'),
        U('pg_ob', 'hx', 1, '전에 임신이나 출산한 적 있으세요?',
          [('pg_gravida', '임신력', r'임신|처음|첫'), ('pg_para', '출산력', r'출산|낳|분만')], 'hx'),
        U('pg_loss', 'hx', 1, '유산이나 자궁외임신을 겪었나요?',
          [('pg_miscarriage', '유산', r'유산'), ('pg_ectopic_hx', '자궁외임신력', r'자궁외')], 'hx'),
        U('pg_drug', 'hx', 1, '임신 전후로 드신 약 있나요?', [('pg_drug_exp', '약물 노출', r'.')], 'meds'),
        U('pg_folic', 'hx', 2, '엽산은 드시고 계세요?', [('pg_folic', '엽산', r'.')], 'meds'),
        U('pg_chronic', 'hx', 2, '갑상선병이나 다른 지병 있으세요?', [I_THY, I_OTHER], 'hx'),
        U('pg_vacc', 'hx', 3, '풍진 예방접종을 맞으셨나요?', [('pg_rubella', '풍진 면역', r'.')], 'hx'),
        U('pg_plan', 'sh', 2, '이번 임신은 계획하신 건가요?', [('pg_planned', '계획 임신', r'.')], 'sh'),
    ],
    'replace': {'hx_meds': 'pg_drug'}, 'demote': {'sh_caffeine': 2, 'sh_job': 3},
    'exams': ['abd_palp', 'abd_insp', 'genital', 'conj', 'skin_turgor', 'thyroid', 'periph'],
}

# ---------------------------------------------------------------- 유방
CPX_EXT['breast_mass'] = {
    'onset_q': '언제 처음 멍울을 발견하셨어요?',
    'units': [
        U('bm_site', 'core', 1, '어느 쪽 어디에 만져지나요?', [('bm_site', '위치', r'.')], 'skin'),
        U('bm_size', 'core', 1, '크기가 점점 커지나요?', [('bm_growth', '크기 변화', r'.')], 'skin'),
        U('bm_cycle', 'core', 1, '생리 주기에 따라 크기가 변하나요?', [('bm_cyclic', '주기 연관', r'.')], 'wm'),
        U('bm_pain', 'core', 1, '만지면 아프세요?', [('bm_pain', '압통', r'.')], 'skin'),
        U('bm_nipple', 'red', 1, '유두에서 피나 진물이 나오나요?',
          [('bm_nipple_blood', '혈성 유두 분비', r'피'), ('bm_nipple_dc', '유두 분비물', r'진물|분비|나와|나오|고름')], 'skin',
          safety=True),
        U('bm_skin', 'red', 1, '피부가 패이거나 붉어졌나요?',
          [('bm_dimpling', '피부 함몰', r'패|들어|함몰|귤|당겨'), ('bm_redness', '발적', r'붉|빨')], 'skin', safety=True),
        U('bm_axilla', 'red', 1, '겨드랑이에도 멍울이 만져지나요?', [('bm_axilla', '액와 림프절', r'.')], 'skin', safety=True),
        U('bm_find', 'core', 2, '어떻게 발견하셨어요?', [('bm_discovery', '발견 경위', r'.')], 'skin'),
        U('bm_hard', 'core', 2, '단단하거나 잘 안 움직이나요?',
          [('bm_hard', '단단함', r'단단|딱딱'), ('bm_fixed', '고정', r'안\s*움직|고정|붙')], 'skin'),
        U('bm_weight', 'red', 2, '모르게 살이 빠지셨나요?', [I_WT], 'gen', safety=True),
        U('bm_hx', 'hx', 1, '전에 유방 질환이나 조직검사를 했나요?',
          [('pmh_breast', '유방 질환력', r'유방|혹|섬유|낭종'), ('bm_biopsy', '조직검사', r'조직|검사')], 'hx'),
        U('bm_hormone', 'hx', 1, '호르몬제나 피임약을 드세요?', [I_HORMONE, I_OCP], 'meds'),
        U('bm_menarche', 'hx', 2, '초경과 폐경은 몇 살에 하셨어요?',
          [('bm_menarche', '초경 연령', r'초경|살|\d'), ('bm_menopause', '폐경 연령', r'폐경')], 'hx'),
        U('bm_screen', 'hx', 2, '유방 검진은 언제 받으셨어요?', [('bm_screening', '유방 검진력', r'.')], 'hx'),
        U('bm_feed', 'hx', 3, '출산하고 모유 수유를 하셨나요?', [('bm_lactation', '출산·수유력', r'.')], 'hx'),
        U('bm_fh', 'fh', 1, '가족 중 유방암이나 난소암이 있나요?',
          [('fh_breast_ca', '유방암 가족력', r'유방|어머니|언니|이모|엄마|여동생|가족|암'), ('fh_ovary_ca', '난소암 가족력', r'난소')],
          'fh'),
    ],
    'women_only': {'bm_cycle'}, 'replace': {'fh_open': 'bm_fh'}, 'demote': {'hx_htn_dm': 2},
    'exams': ['breast', 'axillary_ln', 'cervical_ln', 'skin_rash', 'lung', 'liver_spleen', 'spine'],
}

# ---------------------------------------------------------------- 탐지·설명
DETECT = {
    'heartburn': r'속(이|이\s*많이|이\s*자주)?\s*쓰(려|리|림|린)|속쓰림|신물|위산|역류|명치|소화(가)?\s*(안\s*(돼|되)|불량|잘\s*안)|체한\s*(것|듯)',
    # 토혈 진술("피를 토했어요")은 토혈 범주만 잡히도록 전체 문장 선행 부정
    'vomiting': r'(?s)^(?!.*(피를?\s*(많이\s*|좀\s*|조금\s*)?토|토혈)).*?(토(해|했|하고|하는|할|하게|하며)|구토|게워)',
    'hematemesis': r'피를?\s*(많이\s*|좀\s*|조금\s*)?토(해|했|하|한)|토혈|토한\s*(것|게)에\s*피|커피\s*찌꺼기',
    'hematochezia': r'(대변|(?<![소대])변|똥)(에|에서)\s*(피|혈)|혈변|피똥|(대변|(?<![소대])변|똥)이\s*(까맣|까만|검|시커멓|빨갛)|흑색변|짜장\s*같은\s*변|항문에서\s*피',
    'diarrhea': r'설사|묽은\s*변|변이\s*묽|물\s*같은\s*변|물똥',
    'constipation': r'변비|(대변|(?<![소대])변)을\s*(잘\s*)?못\s*(봐|보|본|봤)|(대변|(?<![소대])변)이\s*(잘\s*)?안\s*나',
    'jaundice': r'황달|(눈|흰자|피부|얼굴|몸)(이|위가|가)?\s*(좀\s*)?(노래|노랗|누렇|누래)',
    'hematuria': r'혈뇨|(소변|오줌)(에|이|색이|색깔이)?\s*(피|빨갛|빨간|붉|콜라)|피\s*섞인\s*(소변|오줌)|(빨간|붉은)\s*(소변|오줌)',
    'luts': r'(소변|오줌)\s*줄기|잔뇨|야간뇨|요실금|전립선|밤에\s*(자꾸\s*|자주\s*)?(소변|화장실|오줌)|(소변|오줌)(이|을)?\s*(잘\s*)?(안\s*나와|못\s*(봐|보)|보기\s*(힘|어려)|시원하지|새|샌|지려)',
    'menstrual': r'월경|생리통|무월경|생리\s*주기|생리\s*양이\s*(너무\s*)?(많|늘|줄)|생리(를|가)?\s*([가-힣]{1,4}\s*){0,2}(안\s*(해|하|나|와|한)|불규칙|늦어|늦게|끊|없어|없다|이상|건너)',
    'vag_bleeding': r'하혈|(질|부정)\s*출혈|(밑|아래)(으로|에서)\s*피|폐경.{0,12}(피가|출혈)|생리\s*(때가\s*)?아닌데\s*피|생리가?\s*(멈추지|안\s*멈추|끝나지\s*않)',
    'vag_discharge': r'냉이\s*(많|늘|나|심)|냉\s*냄새|질\s*분비물|분비물(이|이\s*많|에서|이\s*늘)|(밑|아래)(이|가)?\s*(가려|가렵)|질염',
    'pregnancy': r'임신(인\s*것\s*같|한\s*것\s*같|했(어요|어|습니다|대요|다고)|\s*테스트|\s*검사|\s*확인|\s*\d+\s*주|\s*중이|\s*초기)|입덧|산전\s*(검사|진찰)|임테기',
    'breast_mass': r'(유방|가슴|젖)(에|에서|\s*쪽에|\s*안에)?\s*(뭐가\s*|무언가\s*|뭔가\s*)?(만져지는\s*)?(멍울|몽우리|혹|덩어리|응어리|단단한\s*게)|유방\s*(종괴|결절|멍울|혹)|유두\s*(에서\s*)?(피|분비물)',
}
DESC = {
    'heartburn': '속쓰림·소화불량(역류·궤양)',
    'vomiting': '구토(원인 감별·탈수)',
    'hematemesis': '토혈(상부위장관 출혈)',
    'hematochezia': '혈변·흑색변',
    'diarrhea': '설사(급성·만성)',
    'constipation': '변비',
    'jaundice': '황달(눈·피부 노래짐)',
    'hematuria': '혈뇨(빨간 소변)',
    'luts': '배뇨 곤란·야간뇨·요실금',
    'menstrual': '월경 이상(무월경·불규칙·월경통)',
    'vag_bleeding': '비정상 질 출혈(폐경 후 포함)',
    'vag_discharge': '질 분비물·외음부 가려움',
    'pregnancy': '임신 확인·입덧·산전 상담',
    'breast_mass': '유방 덩이(멍울)',
}
ITEM_Q = {
    'ros_hematemesis': '피를 토한 적 있나요?',
    'ros_melena': '변이 까맣게 나온 적 있나요?',
    'ros_hematochezia': '변에 피가 섞인 적 있나요?',
    'ros_no_flatus': '방귀가 안 나오나요?',
    'ros_distension': '배가 부풀어 오르나요?',
    'ros_oliguria': '소변량이 줄었나요?',
    'ros_dry_mouth': '입이 바짝 마르나요?',
    'ros_headache': '머리가 아프세요?',
    'ha_neck': '목이 뻣뻣하세요?',
    'ros_dizzy': '어지러우세요?',
    'pa_syncope': '쓰러질 것 같거나 정신을 잃었나요?',
    'gi_dysphagia': '삼킬 때 음식이 걸리나요?',
    'gi_odynophagia': '삼킬 때 아프세요?',
    'ja_confusion': '정신이 흐릿하거나 헷갈리나요?',
    'ja_drowsy': '자꾸 졸리세요?',
    'ja_bruise': '멍이 잘 드세요?',
    'ja_bleed': '코피나 잇몸 피가 잘 나나요?',
    'mn_intermenstrual': '생리 아닐 때 피가 비치나요?',
    'mn_postcoital': '관계 후에 피가 비치나요?',
    'bm_nipple_blood': '유두에서 피가 나오나요?',
    'bm_nipple_dc': '유두에서 분비물이 나오나요?',
    'bm_dimpling': '피부가 움푹 패였나요?',
    'bm_redness': '유방 피부가 붉어졌나요?',
    'he_anticoag': '피를 묽게 하는 약을 드세요?',
}
MENTION = {}
PEDS_MAP = {'vomiting': 'p_gi', 'diarrhea': 'p_gi'}
REFINES = {
    'heartburn': 'gi', 'vomiting': 'gi', 'hematemesis': 'gi', 'hematochezia': 'gi', 'diarrhea': 'gi',
    'constipation': 'gi', 'hematuria': 'urinary', 'luts': 'urinary', 'vag_bleeding': 'menstrual',
}

"""v2 문진 체크리스트 은행·카테고리·중복 차단·고정 키 어휘 (v2_spec §5, §6.3, §9.1).

튜플은 (slot, 라벨, 기본 질문, 우선순위). 우선순위 1=필수(★), 2=권장, 3=선택. 모든 질문 NFC 28자 이하(tests).
진찰 명칭은 v1 banks.EXAM_BANK를 그대로 쓴다(표준 명칭 전수 포함).
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------- 5.1 성인 공통·여성·정신/수면 선별
ADULT_SPINE = [
    ('hpi_onset', 'Onset', '언제부터 그러셨어요?', 1),
    ('hpi_course', '경과', '점점 심해지고 있나요?', 2),
    ('hpi_impact', '일상 지장', '일상생활에 지장이 있으세요?', 2),
    ('hpi_prior', '이전 진료', '이 문제로 진료받은 적 있으세요?', 2),
    ('pmh_htn_dm', 'HTN/DM', '고혈압이나 당뇨 있으세요?', 1),
    ('pmh_other', '기타 질환', '다른 지병이 있으세요?', 1),
    ('pmh_op', '수술력', '수술받은 적 있으세요?', 2),
    ('pmh_meds', '복용약·보조제', '드시는 약이나 영양제 있으세요?', 1),
    ('pmh_allergy', 'Allergy', '약 알레르기 있으세요?', 3),
    ('fh_open', 'FH', '부모님이나 형제분 앓는 병 있나요?', 1),
    ('fh_dm_htn', 'FH DM/HTN', '가족 중 고혈압이나 당뇨 있나요?', 3),
    ('sh_smoke', 'Smoking', '담배는 피우세요?', 1),
    ('sh_alcohol', 'Alcohol', '술은 얼마나 드세요?', 1),
    ('sh_job', '직업', '무슨 일 하세요?', 2),
    ('sh_living', '동거', '누구와 함께 사세요?', 3),
    ('sh_caffeine', '카페인', '커피는 하루 몇 잔 드세요?', 2),
    ('sh_exercise', '운동·활동', '평소 운동은 얼마나 하세요?', 3),
    ('sh_stress', '스트레스', '요즘 스트레스 받는 일 있으세요?', 3),
    ('ice_concern', '걱정(ICE)', '가장 걱정되시는 게 뭐예요?', 1),
    ('ice_disease', '걱정 질환', '특히 걱정되는 병이 있으세요?', 2),
    ('ice_expect', '궁금증·기대', '오늘 특히 궁금하신 게 있으세요?', 1),
]
WOMEN = [
    ('wm_lmp', 'LMP', '마지막 생리는 언제였어요?', 2),
    ('wm_cycle', '월경 변화', '생리 주기나 양이 변했나요?', 2),
    ('wm_preg', '임신 가능성', '혹시 임신 가능성은 있으세요?', 1),
]
PSYCH_SCREEN = [
    ('ps_mood', '우울', '요즘 기분이 많이 가라앉나요?', 2),
    ('ps_interest', '흥미 저하', '즐겁던 일에 흥미가 줄었나요?', 3),
    ('ps_anxiety', '불안', '불안하거나 초조할 때가 많나요?', 2),
    ('ps_si', '자살 사고', '혹시 죽고 싶은 생각이 드신 적 있나요?', 2),
    ('ps_sleep', '수면', '잠은 잘 주무세요?', 2),
    ('ps_appetite', '식욕', '입맛은 어떠세요?', 2),
    ('ps_prior', '정신과 치료력', '정신과 진료받아 보신 적 있으세요?', 2),
    ('ps_family', '가족 관계', '가족과 갈등은 없으세요?', 3),
    ('ps_mania', '조증 선별', '기분이 지나치게 들뜬 적 있나요?', 3),
]
PSYCH_SCREEN_FOR = {'insomnia', 'substance', 'mood', 'memory', 'fatigue', 'weight_loss', 'palpitation'}

# ---------------------------------------------------------------- 5.2 소아(보호자 대상)
PEDS_SPINE = [
    ('hpi_onset', 'Onset', '언제부터 그랬나요?', 1),
    ('hpi_course', '경과', '점점 심해지고 있나요?', 1),
    ('p_birth_size', '출생 체격', '태어날 때 키와 몸무게는요?', 2),
    ('p_perinatal', '주산기', '임신이나 출산 때 문제 있었나요?', 1),
    ('p_neonatal', '신생아기', '신생아 때 황달 같은 문제 있었나요?', 2),
    ('p_develop', '발달', '말이나 걷기는 또래만큼 했나요?', 1),
    ('p_vaccine', '예방접종', '예방접종은 제때 맞았나요?', 3),
    ('p_illness', '입원·큰 병', '입원하거나 크게 아픈 적 있나요?', 1),
    ('p_meds', '약·한약·보조제', '먹는 약이나 한약, 영양제 있나요?', 1),
    ('p_allergy', 'Allergy', '알레르기 있는 게 있나요?', 3),
    ('p_fh', '가족력', '가족 중 앓는 병 있는 분 있나요?', 1),
    ('p_daycare', '어린이집·학교', '어린이집 생활은 잘하나요?', 2),
    ('p_home', '양육 환경', '집에서 키우기 어려운 점은 없나요?', 3),
    ('p_diet', '식사', '밥은 잘 먹는 편인가요?', 2),
    ('p_sleep', '수면', '밤에 잠은 잘 자나요?', 2),
    ('p_activity', '활동', '잘 뛰어놀고 활발한가요?', 2),
    ('ice_concern', '보호자 걱정', '어머님이 가장 걱정되시는 게 뭐예요?', 1),
    ('ice_expect', '보호자 궁금증', '오늘 특히 궁금하신 게 있으세요?', 1),
]

# ---------------------------------------------------------------- 5.3 주호소 카테고리별 은행
CATEGORY_Q = {
    'weight_loss': [
        ('wl_intake', '식사량·식욕', '식사량은 예전과 비교해 어떠세요?', 1),
        ('wl_heat', '더위 민감', '더위를 예전보다 많이 타세요?', 1),
        ('wl_sweat', '발한', '땀이 많아지셨나요?', 2),
        ('wl_palp', '두근거림', '가슴이 두근거릴 때가 있나요?', 1),
        ('wl_tremor', '손떨림', '손이 떨리세요?', 1),
        ('wl_bowel', '배변 변화', '대변 횟수나 모양이 변했나요?', 1),
        ('wl_thirst', '다음', '물을 예전보다 많이 마시나요?', 1),
        ('wl_urine', '소변 변화', '소변 보는 횟수가 늘었나요?', 2),
        ('wl_fever', '발열', '최근 열이 난 적 있나요?', 2),
        ('wl_eye', '눈 증상', '눈이 튀어나오거나 뻑뻑한가요?', 2),
        ('wl_neck', '목 부음', '목이 붓거나 혹이 만져지나요?', 2),
        ('wl_fatigue', '근력 저하', '계단 오를 때 다리에 힘이 빠지나요?', 2),
        ('wl_activity', '활동량', '운동량이나 활동량이 늘었나요?', 2),
        ('wl_gi', '복통', '배가 아픈 적 있나요?', 3),
        ('wl_cough', '기침', '기침이나 가래가 오래가나요?', 3),
        ('wl_fh_thy', '갑상선 가족력', '가족 중 갑상선 질환 있나요?', 3),
    ],
    'fatigue': [
        ('ft_weight', '체중 변화', '최근 체중 변화가 있나요?', 1),
        ('ft_cold', '추위 민감', '추위를 예전보다 많이 타세요?', 1),
        ('ft_constip', '변비', '변비가 생기셨나요?', 2),
        ('ft_edema', '부종', '얼굴이나 다리가 붓나요?', 2),
        ('ft_dyspnea', '운동 시 호흡곤란', '조금만 움직여도 숨이 차나요?', 1),
        ('ft_dizzy', '어지럼', '일어설 때 어지러우세요?', 2),
        ('ft_bleed', '출혈', '변이 검거나 피가 섞인 적 있나요?', 1),
        ('ft_menorrhagia', '월경과다', '생리량이 많은 편인가요?', 2),
        ('ft_thirst', '다음·다뇨', '물을 많이 마시거나 소변이 늘었나요?', 2),
        ('ft_fever', '발열·야간발한', '열이 나거나 밤에 땀이 나나요?', 2),
        ('ft_snore', '코골이·무호흡', '코골이나 숨 멈춤이 있다고 하나요?', 2),
    ],
    'palpitation': [
        ('pa_pattern', '양상', '규칙적으로 빨리 뛰나요?', 1),
        ('pa_onset', '시작·끝', '갑자기 시작해 갑자기 멈추나요?', 1),
        ('pa_duration', '지속', '한 번 두근거리면 얼마나 가나요?', 1),
        ('pa_trigger', '유발 상황', '주로 언제 두근거리세요?', 1),
        ('pa_syncope', '실신·어지럼', '어지럽거나 쓰러질 것 같았나요?', 1),
        ('pa_chest', '흉통', '가슴 통증도 같이 있나요?', 1),
        ('pa_dyspnea', '호흡곤란', '숨이 차지는 않으세요?', 2),
        ('pa_heat', '더위·체중', '더위를 타거나 살이 빠졌나요?', 2),
        ('pa_fh', '심장 가족력', '가족 중 심장병이나 돌연사 있나요?', 2),
    ],
    'insomnia': [
        ('in_type', '입면/유지', '잠들기 어렵나요, 자주 깨나요?', 1),
        ('in_hours', '수면 시간', '보통 몇 시에 자고 깨세요?', 1),
        ('in_daytime', '주간 기능', '낮에 졸리거나 멍하세요?', 1),
        ('in_meds', '수면제 사용', '잠 때문에 드시는 약 있으세요?', 1),
        ('in_snore', '코골이·무호흡', '코골이나 숨 멈춤이 있다고 하나요?', 2),
        ('in_legs', '하지불안', '누우면 다리가 불편하고 저린가요?', 3),
        ('in_habit', '수면 습관', '자기 전 휴대폰을 오래 보세요?', 3),
    ],
    'substance': [
        ('sb_name', '약 이름·용량', '드시는 약 이름과 용량을 아세요?', 1),
        ('sb_since', '복용 기간', '그 약은 언제부터 드셨어요?', 1),
        ('sb_dose_now', '현재 복용량', '요즘 하루에 몇 알 드세요?', 1),
        ('sb_timing', '복용 시각', '하루 중 언제 언제 드세요?', 1),
        ('sb_tolerance', '내성', '처음보다 양이 늘었나요?', 1),
        ('sb_withdraw', '금단', '약을 안 드시면 어떤 증상이 있나요?', 1),
        ('sb_cutdown', '감량 시도·실패', '줄이거나 끊어 보려 하신 적 있나요?', 1),
        ('sb_sources', '여러 기관 처방', '약은 어디서 처방받으세요?', 1),
        ('sb_other', '다른 약 병용', '다른 수면제나 약국 약도 드세요?', 1),
        ('sb_last', '마지막 복용', '마지막으로 언제 드셨어요?', 2),
        ('sb_blackout', '기억 공백', '약 드신 뒤 기억이 끊긴 적 있나요?', 1),
        ('sb_family', '대인 갈등', '가족들이 약 문제로 걱정하나요?', 1),
        ('sb_craving', '갈망·비축', '약이 떨어질까 봐 불안하세요?', 2),
        ('sb_alcohol', '음주 병용', '약을 술과 같이 드신 적 있나요?', 2),
        ('sb_drive', '위험 상황', '약 드시고 운전하신 적 있나요?', 2),
    ],
    'mood': [
        ('md_appetite', '식욕·체중', '입맛이나 체중이 변했나요?', 1),
        ('md_energy', '기력', '기운이 없고 쉽게 지치세요?', 2),
        ('md_concent', '집중력', '집중하기 어려우세요?', 2),
        ('md_guilt', '무가치감', '자신이 쓸모없다고 느끼세요?', 2),
        ('md_plan', '자살 계획', '구체적으로 방법을 생각해 보셨나요?', 2),
        ('md_panic', '공황', '갑자기 숨이 막히고 죽을 것 같나요?', 2),
        ('md_trigger', '계기', '힘든 일이 있으셨나요?', 1),
    ],
    'memory': [
        ('me_example', '증상 예', '주로 어떤 것을 잊으세요?', 1),
        ('me_course', '진행 양상', '서서히 나빠지고 있나요?', 1),
        ('me_adl', '일상 기능', '돈 계산이나 길 찾기는 괜찮으세요?', 1),
        ('me_behavior', '성격 변화', '성격이나 행동이 변했나요?', 2),
        ('me_meds', '약물', '드시는 약이나 수면제 있으세요?', 1),
        ('me_trauma', '두부 외상', '최근 머리를 다친 적 있나요?', 2),
        ('me_gait', '보행·배뇨', '걸음이 느려지거나 소변 실수 있나요?', 2),
        ('me_fh', '치매 가족력', '가족 중 치매 앓은 분 있나요?', 2),
    ],
    'headache': [
        ('ha_onset', '발생 양상', '갑자기 시작됐나요, 서서히였나요?', 1),
        ('ha_site', '부위', '머리 어디가 아프세요?', 1),
        ('ha_char', '양상', '어떻게 아프세요?', 1),
        ('ha_nrs', '강도', '0~10점이면 몇 점이에요?', 1),
        ('ha_freq', '빈도·지속', '얼마나 자주, 얼마나 오래 아파요?', 1),
        ('ha_nv', '구역·구토', '메스껍거나 토하세요?', 1),
        ('ha_photo', '빛·소리 과민', '빛이나 소리에 예민해지나요?', 2),
        ('ha_aura', '전조·시야', '아프기 전 눈앞이 번쩍이나요?', 2),
        ('ha_neuro', '신경 증상', '팔다리 힘 빠짐이나 말 어눌함은요?', 1),
        ('ha_fever', '발열·경부강직', '열이나 목 뻣뻣함은 없으세요?', 1),
        ('ha_worst', '최악의 두통', '평생 처음 겪는 심한 두통인가요?', 1),
        ('ha_morning', '아침 악화', '아침에 일어날 때 더 심한가요?', 2),
        ('ha_analgesic', '진통제 사용', '진통제는 얼마나 자주 드세요?', 2),
        ('ha_trauma', '외상', '최근 머리를 다친 적 있나요?', 2),
    ],
    'dizziness': [
        ('dz_type', '양상', '빙빙 도나요, 핑 도는 느낌인가요?', 1),
        ('dz_position', '자세 유발', '고개를 돌리거나 누울 때 심하나요?', 1),
        ('dz_duration', '지속 시간', '한 번 어지러우면 얼마나 가나요?', 1),
        ('dz_hearing', '청력·이명', '귀가 먹먹하거나 소리가 나나요?', 1),
        ('dz_nv', '구역·구토', '메스껍거나 토하세요?', 2),
        ('dz_neuro', '신경 증상', '말이 어눌하거나 물체가 둘로 보이나요?', 1),
        ('dz_syncope', '실신', '쓰러지거나 정신을 잃은 적 있나요?', 1),
        ('dz_palp', '두근거림', '가슴이 두근거리지는 않나요?', 2),
        ('dz_stand', '기립 시', '일어설 때 어지러우세요?', 2),
        ('dz_uri', '선행 감염', '최근 감기를 앓으셨나요?', 3),
    ],
    'chest_pain': [
        ('cp_site', '부위', '가슴 어디가 아프세요?', 1),
        ('cp_char', '양상', '쥐어짜나요, 찌르듯 아픈가요?', 1),
        ('cp_rad', '방사통', '팔이나 턱으로 뻗치나요?', 1),
        ('cp_exert', '운동 연관', '걷거나 계단 오를 때 심해지나요?', 1),
        ('cp_rest', '휴식 완화', '쉬면 나아지나요?', 1),
        ('cp_duration', '지속 시간', '한 번 아프면 얼마나 가나요?', 1),
        ('cp_assoc', '동반 증상', '식은땀이나 숨참이 같이 있나요?', 1),
        ('cp_breath', '호흡·자세', '숨 쉬거나 누울 때 더 아픈가요?', 2),
        ('cp_meal', '식사 연관', '식사 후나 누우면 속이 쓰린가요?', 2),
        ('cp_leg', '하지 부종', '한쪽 다리가 붓거나 아픈가요?', 2),
        ('cp_risk_lipid', '이상지질혈증', '콜레스테롤이 높다고 들으셨나요?', 2),
        ('cp_fh', '심장 가족력', '가족 중 심장병 앓은 분 있나요?', 2),
    ],
    'dyspnea': [
        ('dy_onset', '발생', '갑자기 숨이 찼나요, 서서히였나요?', 1),
        ('dy_exert', '운동 정도', '어느 정도 움직이면 숨이 차나요?', 1),
        ('dy_orthop', '기좌호흡', '누우면 숨이 더 차나요?', 1),
        ('dy_pnd', '야간 호흡곤란', '자다가 숨이 차서 깬 적 있나요?', 2),
        ('dy_edema', '부종', '다리가 붓나요?', 1),
        ('dy_cough', '기침·가래', '기침이나 가래가 있나요?', 1),
        ('dy_wheeze', '천명', '숨 쉴 때 쌕쌕 소리가 나나요?', 1),
        ('dy_chest', '흉통', '가슴 통증도 있나요?', 1),
        ('dy_fever', '발열', '열이 나지는 않나요?', 2),
        ('dy_smoke', '흡연량', '담배는 하루 몇 개비, 몇 년 피우셨어요?', 2),
    ],
    'cough_fever': [
        ('cf_duration', '기간', '기침은 언제부터 하셨어요?', 1),
        ('cf_sputum', '가래', '가래가 나오면 무슨 색인가요?', 1),
        ('cf_fever', '발열', '열은 몇 도까지 났어요?', 1),
        ('cf_dyspnea', '호흡곤란', '숨이 차지는 않으세요?', 1),
        ('cf_chest', '흉통', '기침할 때 가슴이 아픈가요?', 2),
        ('cf_uri', '상기도 증상', '콧물이나 목 아픔이 있나요?', 2),
        ('cf_hemop', '객혈', '가래에 피가 섞인 적 있나요?', 1),
        ('cf_wt', '체중감소·야간발한', '살이 빠지거나 밤에 땀이 나나요?', 2),
        ('cf_contact', '접촉력', '주변에 비슷하게 아픈 사람 있나요?', 2),
        ('cf_gerd', '역류', '속쓰림이나 신물이 올라오나요?', 3),
        ('cf_asthma', '천식·알레르기', '천식이나 알레르기 있으세요?', 2),
    ],
    'abd_pain': [
        ('ap_site', '부위', '배 어디가 아프세요?', 1),
        ('ap_migrate', '이동', '아픈 곳이 옮겨 갔나요?', 2),
        ('ap_char', '양상', '어떻게 아프세요?', 1),
        ('ap_nrs', '강도', '0~10점이면 몇 점이에요?', 1),
        ('ap_rad', '방사통', '등이나 다른 곳으로 뻗치나요?', 2),
        ('ap_meal', '식사 연관', '식사와 관련해 달라지나요?', 1),
        ('ap_nv', '구역·구토', '메스껍거나 토하세요?', 1),
        ('ap_bowel', '배변', '설사나 변비가 있나요?', 1),
        ('ap_blood', '위장관 출혈', '변이 검거나 피가 섞이나요?', 1),
        ('ap_fever', '발열', '열이 나지는 않나요?', 1),
        ('ap_urine', '비뇨기', '소변 볼 때 아프거나 피가 나오나요?', 2),
        ('ap_nsaid', '진통제·음주', '진통제나 술을 자주 드세요?', 2),
    ],
    'gi': [
        ('gi_char', '양상', '속이 어떻게 불편하세요?', 1),
        ('gi_meal', '식사 연관', '식후에 더 심해지나요?', 1),
        ('gi_heartburn', '속쓰림·역류', '신물이 올라오거나 쓰리나요?', 1),
        ('gi_dysphagia', '연하곤란', '삼킬 때 걸리거나 아픈가요?', 1),
        ('gi_nv', '구역·구토', '메스껍거나 토하세요?', 1),
        ('gi_stool', '배변 양상', '하루 몇 번, 어떤 변을 보세요?', 1),
        ('gi_blood', '출혈', '변이 검거나 피가 섞이나요?', 1),
        ('gi_weight', '체중 감소', '살이 빠지셨나요?', 1),
        ('gi_relief', '배변 후 완화', '변을 보면 배가 편해지나요?', 2),
        ('gi_food', '음식·여행', '상한 음식이나 여행력 있나요?', 2),
        ('gi_nsaid', '진통제·음주', '진통제나 술을 자주 드세요?', 2),
        ('gi_fh', '위장관암 가족력', '가족 중 위암이나 대장암 있나요?', 2),
    ],
    'urinary': [
        ('ur_dysuria', '배뇨통', '소변 볼 때 아프세요?', 1),
        ('ur_freq', '빈뇨·절박', '소변을 자주, 급하게 보세요?', 1),
        ('ur_hematuria', '혈뇨', '소변에 피가 섞이나요?', 1),
        ('ur_flank', '옆구리 통증', '옆구리나 허리가 아프세요?', 1),
        ('ur_fever', '발열·오한', '열이나 오한이 있나요?', 1),
        ('ur_stream', '배뇨 곤란', '소변 줄기가 약하거나 잘 안 나오나요?', 2),
        ('ur_discharge', '분비물', '분비물이 늘거나 냄새가 나나요?', 2),
        ('ur_history', '재발력', '전에 방광염이나 결석 있었나요?', 2),
    ],
    'edema': [
        ('ed_site', '부위', '어디가 주로 붓나요?', 1),
        ('ed_side', '양측성', '양쪽 다리가 다 붓나요?', 1),
        ('ed_time', '시간대', '아침과 저녁 중 언제 더 붓나요?', 2),
        ('ed_dyspnea', '호흡곤란', '숨이 차거나 누우면 답답한가요?', 1),
        ('ed_urine', '소변 변화', '소변에 거품이 많거나 양이 줄었나요?', 1),
        ('ed_weight', '체중 증가', '최근 몸무게가 늘었나요?', 2),
        ('ed_drug', '약물', '혈압약이나 진통제 드세요?', 2),
        ('ed_liver', '간질환·음주', '간이 안 좋다거나 술을 많이 드세요?', 2),
    ],
    'msk': [
        ('mk_site', '부위', '어느 관절이 아프세요?', 1),
        ('mk_swell', '부종·열감', '붓거나 열이 나고 빨개지나요?', 1),
        ('mk_morning', '조조강직', '아침에 뻣뻣함이 얼마나 가나요?', 1),
        ('mk_trauma', '외상', '다치거나 무리한 적 있나요?', 1),
        ('mk_rad', '방사통·저림', '다리로 뻗치거나 저린가요?', 1),
        ('mk_bladder', '대소변 장애', '대소변 보기 힘든 적 있나요?', 1),
        ('mk_night', '야간통', '밤에 쉬어도 아픈가요?', 2),
        ('mk_systemic', '전신 증상', '열이나 체중 감소가 있나요?', 2),
        ('mk_gout', '통풍 위험', '술이나 고기를 자주 드세요?', 3),
    ],
    'skin': [
        ('sk_site', '부위', '어디에 처음 생겼나요?', 1),
        ('sk_itch', '가려움', '가렵거나 아픈가요?', 1),
        ('sk_spread', '확산', '다른 곳으로 퍼지고 있나요?', 1),
        ('sk_trigger', '유발 요인', '새로 쓴 약이나 음식이 있나요?', 1),
        ('sk_fever', '발열', '열이 나지는 않나요?', 2),
        ('sk_mucosa', '점막 침범', '입안이나 눈에도 증상이 있나요?', 2),
        ('sk_atopy', '아토피·알레르기', '아토피나 알레르기 있으세요?', 2),
        ('sk_contact', '접촉', '주변에 비슷한 사람 있나요?', 3),
    ],
    'neuro': [
        ('nr_site', '부위', '어디가 저리거나 힘이 빠지세요?', 1),
        ('nr_onset', '발생 양상', '갑자기 생겼나요, 서서히였나요?', 1),
        ('nr_weak', '근력 저하', '힘이 빠져 물건을 떨어뜨리나요?', 1),
        ('nr_speech', '구음·시야', '말이 어눌하거나 시야가 이상한가요?', 1),
        ('nr_night', '야간 저림', '밤에 손이 더 저린가요?', 2),
        ('nr_tremor_type', '떨림 양상', '가만히 있을 때 떨리나요?', 1),
        ('nr_tremor_alc', '음주 반응', '술을 마시면 떨림이 줄어드나요?', 3),
        ('nr_dm_alc', '당뇨·음주', '당뇨가 있거나 술을 많이 드세요?', 2),
        ('nr_neck_back', '목·허리 통증', '목이나 허리가 아프세요?', 2),
        ('nr_fh', '가족력', '가족 중 비슷한 증상인 분 있나요?', 2),
    ],
    'dm': [
        ('dm_polyuria', '다뇨', '소변을 자주 보세요?', 1),
        ('dm_thirst', '다음', '목이 자주 마르세요?', 1),
        ('dm_weight', '체중 변화', '살이 빠지거나 찌셨나요?', 1),
        ('dm_vision', '시야', '눈이 침침하세요?', 2),
        ('dm_numb', '저림', '손발이 저리세요?', 2),
        ('dm_wound', '상처', '상처가 잘 안 낫나요?', 2),
        ('dm_glucose', '이전 혈당', '전에 혈당이 높다고 들으셨나요?', 1),
        ('dm_diet', '식습관', '단 음료나 야식을 자주 드세요?', 2),
        ('dm_fh', '당뇨 가족력', '가족 중 당뇨 있는 분 있나요?', 1),
    ],
    'menstrual': [
        ('mn_amount', '양', '생리량은 어떤 편이세요?', 1),
        ('mn_pain', '월경통', '생리통이 심하세요?', 2),
        ('mn_spotting', '부정출혈', '생리 아닐 때 피가 비치나요?', 1),
        ('mn_hirsutism', '다모·여드름', '털이 많아지거나 여드름이 늘었나요?', 2),
        ('mn_galact', '유즙 분비', '젖이 나온 적 있나요?', 3),
    ],
    'syncope': [
        ('sy_context', '상황', '어떤 상황에서 쓰러지셨어요?', 1),
        ('sy_prodrome', '전구 증상', '쓰러지기 전에 어떤 느낌이었나요?', 1),
        ('sy_duration', '의식 소실 시간', '정신을 잃은 시간은 얼마였나요?', 1),
        ('sy_seizure', '경련·혀깨묾', '몸이 떨리거나 혀를 깨물었나요?', 1),
        ('sy_exertion', '운동 중', '운동 중에 쓰러진 적 있나요?', 1),
        ('sy_palp', '두근거림·흉통', '전에 두근거림이나 흉통이 있었나요?', 1),
        ('sy_injury', '외상', '쓰러지면서 다치셨나요?', 2),
        ('sy_fh', '돌연사 가족력', '가족 중 젊어서 돌연사한 분 있나요?', 2),
    ],
    # ---------------- 소아 전용
    'growth': [
        ('gr_noticed', '인지 시점', '언제부터 작다는 말을 들었나요?', 1),
        ('gr_record', '성장 기록', '예전에 잰 키 기록이 있나요?', 1),
        ('gr_values', '과거 계측치', '두 살, 네 살 때 키는 얼마였나요?', 1),
        ('gr_parents', '부모 키', '부모님 키는 각각 어떻게 되세요?', 1),
        ('gr_late', '부모 사춘기', '부모님 중 늦게 키가 큰 분 있나요?', 1),
        ('gr_fh', '저신장·유전 가족력', '가족 중 키가 작거나 유전병 있나요?', 1),
        ('gr_chronic', '만성질환', '천식이나 장, 콩팥 질환 들은 적 있나요?', 1),
        ('gr_steroid', '스테로이드', '스테로이드나 한약 먹은 적 있나요?', 1),
        ('gr_puberty', '사춘기 징후', '음모나 고환 변화가 있었나요?', 1),
        ('gr_hypo', '갑상선저하 증상', '잘 지치거나 변비, 추위 타나요?', 1),
        ('gr_cushing', '쿠싱 양상', '배만 나오거나 얼굴이 둥글어졌나요?', 2),
        ('gr_ich', '두개내 병변', '두통이나 구토, 시야 이상은요?', 1),
        ('gr_weight', '체중 변화', '최근 살이 빠지거나 찌진 않았나요?', 1),
        ('gr_milk', '우유·간식', '우유는 하루 얼마나 마시나요?', 2),
    ],
    'p_fever': [
        ('pf_max', '최고 체온', '열은 몇 도까지 났나요?', 1),
        ('pf_duration', '기간', '열은 언제부터 났나요?', 1),
        ('pf_antipyretic', '해열제 반응', '해열제 먹이면 열이 떨어지나요?', 1),
        ('pf_feeding', '수유·식사', '먹는 양은 평소와 비교해 어때요?', 1),
        ('pf_urine', '소변량', '소변은 평소만큼 보나요?', 1),
        ('pf_activity', '처짐', '많이 처지거나 보채나요?', 1),
        ('pf_resp', '호흡기', '기침이나 콧물이 있나요?', 1),
        ('pf_ear', '귀', '귀를 만지거나 아파하나요?', 2),
        ('pf_gi', '구토·설사', '토하거나 설사를 하나요?', 1),
        ('pf_rash', '발진', '몸에 발진이 생겼나요?', 2),
        ('pf_seizure', '경련', '경련한 적 있나요?', 1),
        ('pf_contact', '접촉', '어린이집에 아픈 아이가 있나요?', 2),
    ],
    'p_resp': [
        ('pr_duration', '기간', '기침은 언제부터 했나요?', 1),
        ('pr_night', '야간 악화', '밤이나 새벽에 더 심한가요?', 1),
        ('pr_wheeze', '쌕쌕거림', '숨 쉴 때 쌕쌕 소리가 나나요?', 1),
        ('pr_dyspnea', '호흡곤란', '숨차하거나 갈비뼈가 쏙 들어가나요?', 1),
        ('pr_fever', '발열', '열이 나나요?', 1),
        ('pr_trigger', '유발', '뛰거나 찬 공기에 심해지나요?', 2),
        ('pr_atopy', '아토피·비염', '아토피나 비염이 있나요?', 2),
        ('pr_fh', '천식 가족력', '가족 중 천식이나 알레르기 있나요?', 2),
        ('pr_smoke', '간접흡연', '집에서 담배 피우는 분 있나요?', 2),
    ],
    'p_gi': [
        ('pg_vomit', '구토', '하루 몇 번 토하나요?', 1),
        ('pg_stool', '설사', '설사는 하루 몇 번 하나요?', 1),
        ('pg_blood', '혈변', '변에 피나 코 같은 게 섞이나요?', 1),
        ('pg_pain_site', '복통 부위', '배 어디를 아파하나요?', 1),
        ('pg_intake', '섭취', '물이나 음식은 먹나요?', 1),
        ('pg_urine', '소변·눈물', '소변량이나 눈물이 줄었나요?', 1),
        ('pg_fever', '발열', '열이 나나요?', 1),
        ('pg_food', '음식·접촉', '같이 먹은 사람도 아픈가요?', 2),
    ],
    'p_dev': [
        ('pd_walk', '대근육', '언제 혼자 걸었나요?', 1),
        ('pd_words', '언어', '지금 단어를 몇 개나 말하나요?', 1),
        ('pd_social', '사회성', '눈 맞춤이나 호명 반응은 어떤가요?', 1),
        ('pd_regress', '퇴행', '하던 것을 못 하게 된 게 있나요?', 1),
        ('pd_hearing', '청력', '소리에 잘 반응하나요?', 1),
        ('pd_fine', '소근육', '숟가락질이나 그리기는 어떤가요?', 2),
        ('pd_fh', '발달 가족력', '가족 중 말이 늦었던 분 있나요?', 2),
    ],
}
PEDS_ONLY = {'growth', 'p_fever', 'p_resp', 'p_gi', 'p_dev'}
PEDS_MAP = {'cough_fever': 'p_fever', 'abd_pain': 'p_gi', 'gi': 'p_gi', 'dyspnea': 'p_resp'}

CATEGORY_DESC = {
    'weight_loss': '체중 감소', 'fatigue': '피로·무기력', 'palpitation': '두근거림', 'insomnia': '불면',
    'substance': '약물(수면제·진통제)·알코올 사용 문제, 처방 요청', 'mood': '우울·불안', 'memory': '기억력 저하',
    'headache': '두통', 'dizziness': '어지럼', 'chest_pain': '흉통', 'dyspnea': '호흡곤란', 'cough_fever': '기침·발열(성인)',
    'abd_pain': '복통', 'gi': '소화불량·구역·설사·변비', 'urinary': '배뇨 증상', 'edema': '부종', 'msk': '관절·허리 통증',
    'skin': '피부 발진·가려움', 'neuro': '저림·마비·떨림', 'dm': '혈당·당뇨 의심', 'menstrual': '월경 문제',
    'syncope': '실신', 'growth': '소아 성장 문제(저신장)', 'p_fever': '소아 발열', 'p_resp': '소아 기침·천명',
    'p_gi': '소아 구토·설사·복통', 'p_dev': '소아 발달 지연',
}

# ---------------------------------------------------------------- 5.4 BOOST·감지
BOOST = {
    'weight_loss': {'wm_cycle': 1, 'wm_preg': 1, 'pmh_meds': 1, 'sh_caffeine': 2, 'ps_sleep': 2, 'ps_anxiety': 2},
    'fatigue': {'ps_mood': 1, 'ps_sleep': 1, 'wm_cycle': 2, 'sh_alcohol': 2, 'pmh_meds': 1},
    'palpitation': {'sh_caffeine': 1, 'sh_alcohol': 2, 'ps_anxiety': 2, 'pmh_meds': 1},
    'insomnia': {'sh_caffeine': 1, 'sh_alcohol': 1, 'ps_mood': 1, 'ps_anxiety': 2, 'sh_living': 2, 'sh_stress': 2,
                 'ps_si': 2},
    'substance': {'sh_alcohol': 1, 'sh_living': 2, 'ps_mood': 2, 'ps_si': 2, 'ps_prior': 2, 'sh_caffeine': 2},
    'mood': {'ps_mood': 1, 'ps_interest': 1, 'ps_si': 1, 'ps_sleep': 1, 'sh_alcohol': 1, 'sh_stress': 1,
             'ps_mania': 2, 'ps_prior': 2, 'sh_living': 2},
    'memory': {'ps_mood': 1, 'sh_alcohol': 1, 'pmh_meds': 1, 'sh_living': 1},
    'headache': {'pmh_meds': 1, 'wm_preg': 2, 'sh_caffeine': 2, 'sh_stress': 2},
    'dizziness': {'pmh_meds': 1, 'pmh_htn_dm': 1},
    'chest_pain': {'sh_smoke': 1, 'pmh_htn_dm': 1, 'fh_open': 1},
    'dyspnea': {'sh_smoke': 1, 'sh_job': 2, 'pmh_meds': 1},
    'cough_fever': {'sh_smoke': 1, 'sh_job': 2},
    'abd_pain': {'wm_preg': 1, 'wm_lmp': 1, 'sh_alcohol': 2},
    'gi': {'sh_alcohol': 2, 'pmh_meds': 1},
    'urinary': {'wm_preg': 1, 'wm_lmp': 2},
    'edema': {'pmh_meds': 1, 'pmh_htn_dm': 1},
    'msk': {'sh_job': 2, 'pmh_meds': 2},
    'skin': {'pmh_meds': 1, 'pmh_allergy': 1},
    'neuro': {'pmh_htn_dm': 1, 'sh_alcohol': 2},
    'dm': {'sh_exercise': 2, 'pmh_htn_dm': 1},
    'menstrual': {'wm_lmp': 1, 'wm_cycle': 1, 'wm_preg': 1},
    'syncope': {'pmh_meds': 1, 'pmh_htn_dm': 1},
    'growth': {'p_perinatal': 1, 'p_develop': 1, 'p_illness': 1, 'p_meds': 2, 'p_diet': 2, 'p_activity': 2,
               'p_sleep': 2, 'p_daycare': 2, 'p_home': 2},
    'p_fever': {'p_vaccine': 1, 'p_daycare': 2},
    'p_resp': {'p_vaccine': 2, 'p_daycare': 2},
    'p_gi': {'p_daycare': 2},
    'p_dev': {'p_perinatal': 1, 'p_develop': 1, 'p_fh': 1},
}

DEMOTE = {  # 카테고리 → {slot: 우선순위} (같은 내용을 카테고리 질문이 더 잘 묻는 경우 공통 항목을 낮춤)
    'growth': {'p_fh': 3, 'p_meds': 2, 'p_illness': 2},
}

CATEGORY_DETECT = {
    'weight_loss': r'(체중|몸무게|살이?).{0,8}(빠|줄|감소)|마르|야위',
    'fatigue': r'(피곤|피로|기운이?\s*없|무기력|지치)',
    'palpitation': r'(두근|심장이\s*빨리|가슴이\s*뛰)',
    'insomnia': r'(잠을?\s*(잘\s*)?못|불면|수면|못\s*자)',
    'substance': r'(수면제|진통제|신경안정제|졸피뎀|스틸녹스|처방.{0,8}(달라|원해|받으러)|술을?.{0,6}(끊|많이))',
    'mood': r'(우울|불안|기분|의욕|죽고\s*싶|공황|초조)',
    'memory': r'(기억|깜빡|건망|치매)',
    'headache': r'(두통|머리가?\s*(아프|아파|지끈))',
    'dizziness': r'(어지|빙빙|핑\s*돌)',
    'chest_pain': r'(가슴|흉통).{0,6}(아프|아파|통증|답답|조이|쥐어)',
    'dyspnea': r'(숨이?\s*(차|가빠)|호흡\s*곤란|숨쉬기)',
    'cough_fever': r'(기침|가래|감기|열이\s*나|발열|오한|목이?\s*(아프|따가))',
    'abd_pain': r'(배가?\s*(아프|아파)|복통|명치|옆구리)',
    'gi': r'(속쓰|소화|더부룩|구역|구토|토하|설사|변비|혈변|검은\s*변)',
    'urinary': r'(소변|오줌|배뇨|혈뇨|빈뇨|요실금)',
    'edema': r'(붓|부종|부었)',
    'msk': r'(관절|허리|무릎|어깨|손가락|발목|통풍|뻣뻣)',
    'skin': r'(발진|가려|두드러기|피부|반점|물집)',
    'neuro': r'(저리|저림|마비|힘이\s*빠|떨리|떨림|감각)',
    'dm': r'(당뇨|혈당|갈증|물을\s*많이|소변을\s*자주)',
    'menstrual': r'(생리|월경|하혈|부정\s*출혈)',
    'syncope': r'(쓰러|실신|정신을\s*잃|기절)',
    'growth': r'(키가|키는?\s*(작|안\s*크|또래)|성장|작아|작은\s*(키|편)|안\s*커|자라지)',
    'p_fever': r'(열이|발열|해열)',
    'p_resp': r'(기침|쌕쌕|숨)',
    'p_gi': r'(토하|구토|설사|배가?\s*(아프|아파)|복통)',
    'p_dev': r'(발달|말이\s*늦|걷지|늦게\s*걸)',
}
SUBSTANCE_REQUEST_RE = r'(수면제|진통제|신경안정제|졸피뎀|약).{0,10}(처방|달라|원해|더\s*받)'

# ---------------------------------------------------------------- 5.6 답 기반 중복 차단
FAMILY_WORD = r'(가족|부모|어머니|아버지|엄마|아빠|형제|자매|언니|오빠|누나|동생|할머니|할아버지|친척|이모|삼촌|모친|부친)'
COVER_RE = {
    'hpi_onset': r'(\d+|[한두세네석]|[일이삼사오육칠팔구십]+)\s*(년|달|개월|주|일)\s*(전|째|동안|사이)|부터',
    'wl_sweat': r'땀|잠옷.{0,4}젖', 'wl_fever': r'(밤|잠옷|자다).{0,8}땀|잠옷.{0,4}젖|열이\s*(나|있)',
    'ft_fever': r'(밤|잠옷).{0,8}땀|잠옷.{0,4}젖|열이\s*(나|있)',
    'wl_intake': r'(많이|더)\s*먹|식사량|입맛|식욕', 'ps_appetite': r'입맛|식욕|잘\s*먹|(많이|더)\s*먹',
    'p_diet': r'잘\s*먹|입맛|식욕', 'md_appetite': r'입맛|식욕',
    'ps_sleep': r'잠|자요|깨요|못\s*자', 'p_sleep': r'잠|자요',
    'pmh_meds': r'(먹는|드시는|복용\s*중인)\s*약.{0,6}(없|있|은)|약(이나|도)?\s*(영양제)?.{0,4}안\s*먹|영양제|혈압약|당뇨약',
    'p_meds': r'한약|영양제|먹는\s*약',
    'p_perinatal': r'만삭|자연분만|제왕절개|조산|임신.{0,6}문제',
    'p_birth_size': r'(태어|출생|낳).{0,15}(\d|킬로|키로|센티|그램)',
    'sh_smoke': r'담배|흡연', 'sh_alcohol': r'(?<!수)술|음주|소주|맥주', 'sh_caffeine': r'커피|카페인',
    'wm_preg': r'임신|피임|성관계', 'wm_cycle': r'생리|월경',
    'wm_lmp': r'(\d+|[일이삼사오육칠팔구십]+)\s*(일|주)\s*전.{0,6}(생리|시작)|생리.{0,8}(전|시작)',
    'gr_parents': r'\d{3}\s*(cm|센티)?.{0,10}\d{3}', 'gr_late': r'늦게\s*(컸|크|자)|사춘기.{0,4}늦|수염',
    'sb_sources': r'(여러|두|세|몇)\s*(곳|군데|병원)|(내과|신경과|정신과|의원).{0,8}(받|처방)|병원.{0,6}(받아|처방)','sb_tolerance': r'(양이?\s*늘|늘었|늘어|많아졌)|반\s*알|서너',
    'sb_withdraw': r'안\s*먹으면|불안|손.{0,4}떨|식은땀',
}
COVER_RE.update({
    'pmh_htn_dm': r'고혈압|혈압약|당뇨', 'hpi_course': r'점점|계속\s*(빠|늘|심)|늘었|늘어|심해졌',
    'wl_thirst': r'물을?.{0,6}(마|먹)', 'wl_urine': r'소변', 'pmh_op': r'수술',
    'fh_open': r'(어머니|아버지|엄마|아빠|부모|형제|할머니|할아버지|모친|부친).{0,12}(이에요|이세요|있어|앓|병|증|암|질환|혈압|당뇨)',
    'wl_fh_thy': r'(어머니|아버지|엄마|아빠|부모|형제|할머니|가족).{0,10}갑상',
})
NONFAMILY_SLOTS = {'pmh_htn_dm', 'pmh_other', 'pmh_op', 'pmh_meds'}  # 가족 호칭이 있는 답은 본인 병력을 덮지 않음
FAMILY_SLOTS = {'fh_open', 'fh_dm_htn', 'wl_fh_thy', 'pa_fh', 'cp_fh', 'me_fh', 'gi_fh', 'dm_fh', 'sy_fh', 'nr_fh', 'pr_fh',
                'pd_fh', 'gr_fh', 'gr_late', 'p_fh'}

# ---------------------------------------------------------------- §6.3 카테고리별 진찰 우선순위 (vitals·general 제외)
CATEGORY_EXAMS = {
    'weight_loss': ['thyroid', 'eye_signs', 'radial', 'skin_temp', 'post_tremor', 'thyroid_bruit', 'dtr', 'heart',
                    'power', 'conj', 'cervical_ln', 'eom', 'pretibial', 'abd_palp', 'liver_spleen', 'bowel', 'mental'],
    'fatigue': ['conj', 'thyroid', 'heart', 'lung', 'periph', 'abd_palp', 'liver_spleen', 'cervical_ln', 'skin_temp',
                'dtr', 'mental', 'pretibial'],
    'palpitation': ['radial', 'heart', 'thyroid', 'skin_temp', 'post_tremor', 'lung', 'jvp', 'periph', 'conj',
                    'eye_signs', 'mental'],
    'insomnia': ['mental', 'sedation', 'cognitive', 'post_tremor', 'skin_temp', 'thyroid', 'orthostatic', 'insight',
                 'heart', 'conj'],
    'substance': ['mental', 'sedation', 'cognitive', 'orthostatic', 'post_tremor', 'skin_temp', 'nystagmus',
                  'dysarthria', 'gait', 'cerebellar', 'romberg', 'insight', 'rest_tremor', 'conj', 'liver_spleen'],
    'mood': ['mental', 'affect', 'insight', 'cognitive', 'thyroid', 'post_tremor', 'sedation', 'conj', 'heart'],
    'memory': ['mental', 'cognitive', 'gait', 'rest_tremor', 'rigidity', 'dysarthria', 'pronator', 'dtr', 'babinski',
               'thyroid', 'conj', 'carotid', 'romberg'],
    'headache': ['pupil', 'fundus', 'eom', 'neck_stiff', 'face_sym', 'pronator', 'power', 'cerebellar', 'gait',
                 'sinus', 'vfield', 'mental', 'dtr'],
    'dizziness': ['orthostatic', 'nystagmus', 'dix', 'cerebellar', 'romberg', 'gait', 'heart', 'eom', 'ear',
                  'dysarthria', 'conj', 'radial'],
    'chest_pain': ['heart', 'lung', 'chest_wall', 'radial', 'jvp', 'periph', 'calf', 'abd_palp', 'skin_temp',
                   'chest_insp'],
    'dyspnea': ['chest_insp', 'lung', 'chest_perc', 'heart', 'jvp', 'periph', 'calf', 'clubbing', 'conj', 'radial'],
    'cough_fever': ['pharynx', 'cervical_ln', 'lung', 'chest_perc', 'heart', 'ear', 'sinus', 'nasal', 'chest_insp',
                    'skin_rash'],
    'abd_pain': ['abd_insp', 'bowel', 'abd_palp', 'rebound', 'murphy', 'mcburney', 'cva', 'liver_spleen', 'conj',
                 'abd_perc', 'psoas', 'hernia'],
    'gi': ['abd_insp', 'bowel', 'abd_palp', 'liver_spleen', 'conj', 'cervical_ln', 'skin_turgor', 'abd_perc',
           'rebound'],
    'urinary': ['cva', 'abd_palp', 'abd_insp', 'abd_perc', 'genital', 'periph'],
    'edema': ['periph', 'jvp', 'heart', 'lung', 'shifting', 'liver_spleen', 'abd_insp', 'thyroid', 'calf', 'conj'],
    'msk': ['joint', 'spine', 'slr', 'power', 'sensory', 'dtr', 'gait', 'skin_rash'],
    'skin': ['skin_rash', 'oral', 'cervical_ln', 'joint', 'conj'],
    'neuro': ['power', 'sensory', 'dtr', 'babinski', 'pronator', 'face_sym', 'dysarthria', 'cerebellar', 'gait',
              'romberg', 'rest_tremor', 'post_tremor', 'rigidity', 'phalen', 'tinel'],
    'dm': ['fundus', 'sensory', 'periph', 'skin_temp', 'thyroid', 'heart', 'dtr', 'oral'],
    'menstrual': ['thyroid', 'conj', 'abd_palp', 'skin_temp', 'breast', 'abd_insp'],
    'syncope': ['orthostatic', 'heart', 'radial', 'carotid', 'neck_stiff', 'face_sym', 'power', 'conj'],
    'growth': ['anthro', 'growth_chart', 'body_prop', 'tanner', 'dysmorph', 'thyroid', 'striae', 'heart', 'lung',
               'abd_palp', 'conj', 'periph', 'gait', 'mental', 'liver_spleen', 'vfield'],
    'p_fever': ['ear', 'pharynx', 'cervical_ln', 'lung', 'heart', 'abd_palp', 'skin_rash', 'neck_stiff', 'cap_refill',
                'chest_insp'],
    'p_resp': ['chest_insp', 'lung', 'heart', 'pharynx', 'ear', 'nasal', 'cervical_ln', 'skin_rash', 'cap_refill'],
    'p_gi': ['skin_turgor', 'cap_refill', 'oral', 'abd_insp', 'bowel', 'abd_palp', 'mcburney', 'rebound', 'mental'],
    'p_dev': ['anthro', 'growth_chart', 'dysmorph', 'mental', 'power', 'dtr', 'gait', 'ear', 'eom'],
}
CORE12 = ['vitals', 'general', 'mental', 'conj', 'thyroid', 'chest_insp', 'lung', 'heart', 'abd_insp', 'abd_palp',
          'liver_spleen', 'periph']
RISKY_EXAMS = {'eye_signs', 'sedation', 'rest_tremor', 'growth_vel', 'joint', 'affect'}  # 카테고리·감별일 때만

# ---------------------------------------------------------------- §9.1 고정 키 어휘 단서
FIXED_KEYS = {
    'pmh.DM': r'당뇨|혈당', 'pmh.HTN': r'혈압', 'pmh.stroke': r'뇌졸중|중풍|뇌경색|뇌출혈', 'pmh.Tbc': r'결핵',
    'pmh.hepatitis': r'간염', 'pmh.heart_disease': r'심장|협심|심근|부정맥', 'pmh.dyslipidemia': r'콜레스테롤|고지혈|이상지질',
    'pmh.op_hx': r'수술', 'pmh.allergy': r'알레르기|알러지', 'fh.DM': r'당뇨', 'fh.HTN': r'혈압',
    'fh.stroke': r'뇌졸중|중풍|뇌경색|뇌출혈', 'sh.smoking': r'담배|흡연|피우', 'sh.alcohol': r'(?<!수)술|음주|소주|맥주|마시',
    'ros.General weakness': r'기운|힘이\s*없|무기력|쇠약|힘이\s*빠', 'ros.Fatigue': r'피곤|피로|지치|기운',
    'ros.Headache': r'두통|머리', 'ros.Dizziness': r'어지|핑|빙빙', 'ros.Chest pain': r'가슴|흉통',
    'ros.Palpitation': r'두근|가슴이\s*뛰|심장이', 'ros.Fever': r'열|발열|체온', 'ros.Chill': r'오한|춥|으슬',
    'ros.Cough': r'기침', 'ros.Sputum': r'가래', 'ros.Rhinorrhea': r'콧물|코가', 'ros.Abdominal pain': r'배|복통|명치',
    'ros.Melena': r'검은\s*변|짜장|흑색', 'ros.Hematochezia': r'피|혈변', 'ros.Hematemesis': r'토혈|피.{0,4}토',
    'ros.Anorexia': r'입맛|식욕|먹|식사', 'ros.Nausea': r'메스|구역|울렁', 'ros.Vomiting': r'토|구토',
    'ros.Diarrhea': r'설사', 'ros.Constipation': r'변비|딱딱',
}
FIXED_LABEL = {
    'pmh.DM': '당뇨', 'pmh.HTN': '고혈압', 'pmh.stroke': '뇌졸중', 'pmh.Tbc': '결핵', 'pmh.hepatitis': '간염',
    'pmh.heart_disease': '심장병', 'pmh.dyslipidemia': '이상지질혈증', 'pmh.op_hx': '수술력', 'pmh.allergy': '알레르기',
    'fh.DM': '당뇨', 'fh.HTN': '고혈압', 'fh.stroke': '뇌졸중', 'sh.smoking': '흡연', 'sh.alcohol': '음주',
}

# slot → 고정 키(사실 추출 실패 시 폴백, 그리고 문진 slot 질문의 키 힌트)
SLOT_KEYS = {
    'pmh_htn_dm': ['pmh.HTN', 'pmh.DM'], 'pmh_op': ['pmh.op_hx'], 'pmh_allergy': ['pmh.allergy'],
    'p_allergy': ['pmh.allergy'], 'fh_dm_htn': ['fh.HTN', 'fh.DM'], 'sh_smoke': ['sh.smoking'],
    'sh_alcohol': ['sh.alcohol'], 'ft_fever': ['ros.Fever'], 'wl_fever': ['ros.Fever'], 'cf_fever': ['ros.Fever'],
    'wl_palp': ['ros.Palpitation'], 'pa_chest': ['ros.Chest pain'], 'cp_site': ['ros.Chest pain'],
    'ha_nv': ['ros.Nausea', 'ros.Vomiting'], 'ap_nv': ['ros.Nausea', 'ros.Vomiting'], 'gi_nv': ['ros.Nausea', 'ros.Vomiting'],
    'dz_nv': ['ros.Nausea', 'ros.Vomiting'], 'ft_constip': ['ros.Constipation'], 'ft_dizzy': ['ros.Dizziness'],
    'ps_appetite': ['ros.Anorexia'], 'md_energy': ['ros.Fatigue'], 'cf_sputum': ['ros.Sputum'],
}


def all_slots() -> dict:
    """slot → (라벨, 질문, 우선순위). 같은 slot은 처음 정의를 쓴다."""
    out = {}
    for lst in [ADULT_SPINE, WOMEN, PSYCH_SCREEN, PEDS_SPINE] + list(CATEGORY_Q.values()):
        for slot, label, q, prio in lst:
            out.setdefault(slot, (label, q, prio))
    return out


ALL_SLOTS = all_slots()


def detect_categories(text: str, pediatric: bool) -> list[str]:
    out = []
    for cat, pat in CATEGORY_DETECT.items():
        if cat in PEDS_ONLY and not pediatric:
            continue
        if re.search(pat, text or ''):
            out.append(PEDS_MAP.get(cat, cat) if pediatric else cat)
    return list(dict.fromkeys(out))


def informant_title(text: str) -> str:
    t = text or ''
    if re.search(r'(엄마|어머니|어머님|모친)', t):
        return '어머님'
    if re.search(r'(아빠|아버지|아버님|부친)', t):
        return '아버님'
    if re.search(r'할머니', t):
        return '할머님'
    if re.search(r'할아버지', t):
        return '할아버님'
    return '보호자분'


def cover_hits(text: str) -> set:
    """한 답(또는 시작 정보)이 덮는 slot 집합."""
    hits = set()
    t = text or ''
    fam = bool(re.search(FAMILY_WORD, t))
    for slot, pat in COVER_RE.items():
        if slot in FAMILY_SLOTS and not fam:
            continue
        if slot in NONFAMILY_SLOTS and fam:
            continue
        if re.search(pat, t):
            hits.add(slot)
    return hits

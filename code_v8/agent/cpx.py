"""v8 P1 CPX형 체크리스트 은행 + 묶음 질문 검증기 + 항목별 응답 판정 (sota34_analysis §9.3·§9.10·§6.2·§6.3).

단위(unit) = 한 번에 묻는 질문 하나. 항목(item) = 채점 체크리스트의 한 칸.
- kind: single(1항목) / pair(같은 계통 2항목, 공통 술어) / hx3(병력 이름 3개 나열) / neg3(같은 계통 음성 선별 3개)
- stage: core(핵심 양성) → red(경고 음성) → hx(병력) → fh(가족력) → sh(사회력) → preg(임신, 단독) → ice(걱정 1단계)
- prio: 1 핵심, 2 감별, 3 배경. safety=True면 미응답 시 단독 재질문 1회 대상.
서버 실측(§3.4): 같은 계통 2항목 짝 83% 두 항목 응답, 부분 응답 27/29가 첫 항목 → 중요한 항목을 앞에.
3항목 이상은 같은 계통 음성 묶음이면 포괄 음성("그런 증상은 없어요") 13/14, 양성이 섞이면 양성 하나만 답함.
교차 계통·서로 다른 술어("~거나 ~고")는 첫 항목만(9건 중 1건) → 금지.
"""
from __future__ import annotations

import re

from .util import nfc

STAGES = ('core', 'red', 'hx', 'fh', 'sh', 'preg', 'ice')
STAGE_RANK = {s: i for i, s in enumerate(STAGES)}
MAX_Q = 30


def _kind(items, sys_):
    if len(items) == 1:
        return 'single'
    if len(items) == 2:
        return 'pair'
    return 'hx3' if sys_ in ('hx', 'meds', 'fh') else 'neg3'


def U(uid, stage, prio, q, items, sys_, safety=False, follow=None, isys=None, must=False):
    """follow: 양성일 때 바로 물을 후속 (item_id, 라벨, 질문, 답에 이미 있으면 건너뛸 정규식|None).
    isys: 항목별 계통(묶음 규칙 검사용, 없으면 모두 sys_). must: 범주와 무관하게 반드시 묻는 공통 병력 단위(v8c)."""
    u = {'id': uid, 'stage': stage, 'prio': prio, 'q': q, 'items': [tuple(i) for i in items], 'sys': sys_,
         'kind': _kind(items, sys_), 'safety': safety, 'follow': follow, 'must': must}
    if isys:
        u['isys'] = list(isys)
    return u


# ---------------------------------------------------------------- 공통 항목 (성인)
I_HTN = ('pmh_htn', '고혈압', r'고혈압|혈압')
I_DM = ('pmh_dm', '당뇨', r'당뇨|혈당')
I_MEDS = ('pmh_meds', '복용약', r'약|[가-힣](핀|린|롤|팜|뎀|틴|졸|드)\b|먹고|먹어|드시')
I_SUPP = ('pmh_supp', '영양제·보조제', r'영양제|보조제|한약|비타민')
I_SMOKE = ('sh_smoke', '흡연', r'담배|흡연|피우|피워|금연')
I_ALC = ('sh_alcohol', '음주', r'술|음주|소주|맥주|마셔|마시')
I_CAFF = ('sh_caffeine', '카페인', r'커피|카페인|잔')
I_PREG = ('wm_preg', '임신 가능성', r'임신|관계|피임|생리')
I_ASTHMA = ('pmh_asthma', '천식', r'천식')
I_HEART = ('pmh_heart', '심장병', r'심장')
I_THY = ('pmh_thyroid', '갑상샘 질환력', r'갑상')
I_OTHER = ('pmh_other', '기타 지병', r'지병|병|질환')
I_OP = ('pmh_op', '수술력', r'수술')
I_ALLERGY = ('pmh_allergy', '약 알레르기', r'알레르기|알러지|두드러기')
I_FH = ('fh_open', '가족력', r'어머니|아버지|엄마|아빠|부모|형제|언니|오빠|누나|동생|할머니|할아버지|가족|병|암|혈압|당뇨')
I_CP = ('ros_cp', '흉통', r'흉통|통증|아프|아파|답답|조이')   # '가슴'만으로는 판정하지 않음("가슴이 두근거리고 숨이 차요")
I_DYSP = ('ros_dysp', '호흡곤란', r'숨')
I_MOOD = ('ps_mood', '우울감', r'기분|우울|가라앉|처지')
I_SI = ('ps_si', '자살 사고', r'죽|자살|극단')
I_INTEREST = ('ps_interest', '흥미·의욕 저하', r'의욕|흥미|재미')
I_FEVER = ('ros_fever', '발열', r'열')
I_CHILL = ('ros_chill', '오한', r'오한|춥|으슬')
I_NV_N = ('ros_nausea', '구역', r'메스|울렁|구역')
I_NV_V = ('ros_vomit', '구토', r'토|구토')
I_MELENA = ('ros_melena', '흑색변', r'검|까만|짜장')
I_HEMATO = ('ros_hematochezia', '혈변', r'피|혈변|빨간')

HX_HTN_DM = U('hx_htn_dm', 'hx', 1, '고혈압이나 당뇨 있으세요?', [I_HTN, I_DM], 'hx',
              follow=('pmh_htn_dm_detail', '진단 시기·약', '언제 진단받고 무슨 약 드세요?', r'(년|약|핀|린)'))
HX_MEDS = U('hx_meds', 'hx', 1, '드시는 약이나 영양제 있으세요?', [I_MEDS, I_SUPP], 'meds',
            follow=('pmh_meds_detail', '약 이름·용량', '약 이름과 용량을 아세요?', r'(mg|밀리|[가-힣](핀|린|롤|팜|뎀|틴|졸))',
                    'pmh_meds'))
I_ADMIT = ('pmh_admit', '입원력', r'입원')
# v8c 필수 공통 병력(범주 대체·강등에 면역): 입원·수술 / 약 알레르기·천식 / 가족력 / 술·담배 / 복용약 / 임신 / ICE
HX_ADMIT_OP = U('hx_admit_op', 'hx', 1, '입원이나 수술한 적 있으세요?', [I_ADMIT, I_OP], 'hx', must=True)
HX_ALLERGY = U('hx_allergy', 'hx', 1, '약 알레르기나 천식 있으세요?', [I_ALLERGY, I_ASTHMA], 'hx', safety=True, must=True)
HX_ALLERGY_ONLY = U('hx_allergy', 'hx', 1, '약 알레르기 있으세요?', [I_ALLERGY], 'hx', safety=True, must=True)
FH_OPEN = U('fh_open', 'fh', 1, '부모님이나 형제분 앓는 병 있나요?', [I_FH], 'fh',
            follow=('fh_more', '추가 가족력', '가족 중 또 앓는 분 있나요?', None))
SH_SMOKE_ALC = U('sh_smoke_alc', 'sh', 1, '담배나 술은 하세요?', [I_SMOKE, I_ALC], 'sh',
                 follow=('sh_alcohol_amt', '음주량', '술은 한 번에 얼마나 드세요?', r'(잔|병|캔|\d)', 'sh_alcohol'))
SH_ALC_SMOKE = U('sh_alc_smoke', 'sh', 1, '술이나 담배는 하세요?', [I_ALC, I_SMOKE], 'sh',
                 follow=('sh_alcohol_amt', '음주량', '술은 한 번에 얼마나 드세요?', r'(잔|병|캔|\d)', 'sh_alcohol'))
SH_CAFF = U('sh_caffeine', 'sh', 2, '커피는 하루 몇 잔 드세요?', [I_CAFF], 'sh')
SH_JOB = U('sh_job', 'sh', 3, '무슨 일 하세요?', [('sh_job', '직업', r'일|회사|직장|주부|학생|은퇴|가게|근무')], 'sh')
SH_STRESS = U('sh_stress', 'sh', 3, '요즘 스트레스 받는 일 있으세요?', [('sh_stress', '스트레스', r'스트레스|힘든|일')], 'sh')
WM_PREG = U('wm_preg', 'preg', 1, '혹시 임신 가능성은 있으세요?', [I_PREG], 'wm', safety=True)
WM_CYCLE = U('wm_cycle', 'core', 2, '생리 양이나 기간이 변했나요?',
             [('wm_amount', '월경량', r'양|량|많|적|줄|늘'), ('wm_duration', '월경 기간·주기', r'기간|짧|길|주기|불규칙')], 'wm')
WM_LMP = U('wm_lmp', 'core', 2, '마지막 생리는 언제였어요?', [('wm_lmp', 'LMP', r'전|일|주|달|생리')], 'wm')
PS_MOOD = U('ps_mood', 'red', 2, '기분이 가라앉거나 의욕이 없으세요?', [I_MOOD, I_INTEREST], 'psy',
            follow=('ps_si', '자살 사고', '혹시 죽고 싶은 생각이 드신 적 있나요?', None, 'ps_mood'))
PS_MOOD_SI = U('ps_mood_si', 'red', 1, '기분이 가라앉거나 죽고 싶은 적 있나요?', [I_MOOD, I_SI], 'psy', safety=True,
               follow=('md_plan', '자살 계획', '구체적으로 방법을 생각해 보셨나요?', None, 'ps_si'))
ICE_DISEASE = U('ice', 'ice', 1, '혹시 걱정되는 병이 있으세요?', [('ice_concern', '걱정(ICE)', r'.')], 'ice')
ICE_OPEN = U('ice', 'ice', 1, '가장 걱정되거나 궁금한 게 뭐예요?', [('ice_concern', '걱정·기대(ICE)', r'.')], 'ice')
ONSET = U('hpi_onset', 'core', 1, '언제부터 그러셨어요?', [('hpi_onset', 'Onset', r'.')], 'hpi')

ADULT_COMMON = [HX_HTN_DM, HX_MEDS, HX_ADMIT_OP, HX_ALLERGY, FH_OPEN, SH_SMOKE_ALC, SH_CAFF, SH_JOB]

# ---------------------------------------------------------------- 소아 공통 (보호자 대상)
P_PERI = U('p_perinatal', 'hx', 1, '임신이나 출산 때 문제가 있었나요?',
           [('p_pregnancy', '임신 중 문제', r'임신'), ('p_birth', '출산·분만', r'출산|분만|만삭|조산|제왕')], 'peds')
P_BIRTH = U('p_birth_size', 'hx', 2, '태어날 때 키와 몸무게는요?', [('p_birth_size', '출생 체격', r'\d|킬로|키로|센티|그램')],
            'peds')
P_DEV = U('p_develop', 'hx', 1, '말이나 걷기는 또래만큼 했나요?',
          [('p_dev_speech', '언어 발달', r'말'), ('p_dev_walk', '운동 발달', r'걷|걸')], 'peds')
P_ILL = U('p_admit_op', 'hx', 1, '입원이나 수술한 적 있나요?', [I_ADMIT, I_OP], 'hx', must=True)
P_MEDS = U('p_meds', 'hx', 2, '먹는 약이나 영양제 있나요?', [('p_meds', '복용약', r'약'), ('p_supp', '영양제', r'영양제|비타민')],
           'meds')
P_VACC = U('p_vaccine', 'hx', 3, '예방접종은 제때 맞았나요?', [('p_vaccine', '예방접종', r'접종|맞|주사')], 'peds')
P_ALLERGY = U('p_allergy', 'hx', 1, '알레르기 있는 게 있나요?', [('pmh_allergy', '알레르기', r'알레르기|알러지')], 'hx', safety=True,
              must=True)
P_FH = U('p_fh', 'fh', 1, '가족 중 앓는 병 있는 분 있나요?', [I_FH], 'fh')
P_DAYCARE = U('p_daycare', 'sh', 2, '어린이집 생활은 잘하나요?', [('p_daycare', '어린이집·학교', r'잘|친구|어린이집|학교|선생')], 'peds')
P_DIET = U('p_diet', 'sh', 2, '밥은 잘 먹는 편인가요?', [('p_diet', '식사', r'먹|밥|편식|입')], 'peds')
P_SLEEP = U('p_sleep', 'sh', 2, '밤에 잠은 잘 자나요?', [('p_sleep', '수면', r'잠|자')], 'peds')
P_ICE = U('ice', 'ice', 1, '어머님이 가장 걱정되시는 게 뭐예요?', [('ice_concern', '보호자 걱정', r'.')], 'ice')
PEDS_COMMON = [P_PERI, P_DEV, P_ILL, P_MEDS, P_FH, P_VACC, P_DAYCARE, P_ALLERGY]

# ---------------------------------------------------------------- 범주별 체크리스트 (16범주)
CPX = {}

CPX['weight_loss'] = {
    'onset_q': '언제부터 살이 빠졌어요?',
    'units': [
        U('wl_intake', 'core', 1, '식사량이나 입맛은 예전과 어떠세요?', [('wl_intake', '식사량·식욕', r'식사|입맛|식욕|먹|양')], 'gen'),
        U('wl_heat', 'core', 1, '더위를 타거나 땀이 많아졌나요?',
          [('wl_heat', '더위 불내성', r'더위|덥'), ('wl_sweat', '발한', r'땀|젖')], 'gen'),
        U('wl_palp', 'core', 1, '가슴이 두근거릴 때가 있나요?', [('ros_palp', '두근거림', r'두근|뛰|빨리')], 'cv',
          follow=('wl_palp_freq', '두근거림 빈도', '얼마나 자주 두근거리세요?', r'(자주|매일|하루|번|가끔|늘|항상|가만)')),
        U('wl_tremor', 'core', 1, '손 떨림이 있으세요?', [('wl_tremor', '손떨림', r'떨')], 'neuro'),
        U('wl_bowel', 'core', 1, '대변 횟수나 모양이 변했나요?',
          [('wl_bowel_freq', '배변 횟수', r'번|회|자주|횟수'), ('wl_bowel_form', '변 양상', r'묽|모양|설사|딱딱|변비|물')], 'gi'),
        U('wl_thirst', 'core', 2, '갈증이나 소변량 변화가 있나요?',
          [('wl_thirst', '갈증', r'갈증|목이\s*마르|물'), ('wl_urine', '소변량', r'소변')], 'gu'),
        U('wl_eye', 'core', 1, '눈이 튀어나오거나 뻑뻑한가요?',
          [('wl_eye_prop', '안구 돌출', r'튀어|돌출|커'), ('wl_eye_dry', '안구 건조·자극', r'뻑뻑|건조|따가|충혈')], 'eye',
          follow=('wl_diplopia', '복시·시력', '물체가 둘로 보이거나 흐린가요?', None)),
        U('wl_neck', 'core', 1, '목이 붓거나 혹이 만져지나요?',
          [('wl_neck_swell', '목 부음', r'붓|부었|두꺼|커|부어'), ('wl_neck_mass', '목 혹', r'혹|멍울')], 'neck'),
        U('wl_cycle', 'core', 1, '생리 양이나 기간이 변했나요?',
          [('wm_amount', '월경량', r'양|량|많|적|줄|늘'), ('wm_duration', '월경 기간·주기', r'기간|짧|길|주기|불규칙')], 'wm'),
        U('wl_sleep', 'core', 1, '잠을 설치거나 불안하세요?',
          [('ps_sleep', '불면', r'잠|자|깨'), ('ps_anx', '불안·초조', r'불안|초조|예민|조마')], 'psy', isys=['sleep', 'psy']),
        U('wl_weak', 'core', 2, '기운이 없거나 쉽게 지치세요?',
          [('wl_weak', '기력 저하', r'기운|힘'), ('ros_fatigue', '피로', r'지치|피곤|피로')], 'gen'),
        U('wl_gi_red', 'red', 2, '배가 아프거나 토하세요?', [('ros_abd', '복통', r'복통|배'), I_NV_V], 'gi'),
        U('wl_hemato', 'red', 3, '변에 피가 섞인 적 있나요?', [I_HEMATO], 'gi'),
        U('wl_cardio', 'red', 1, '가슴 통증이나 숨찬 증상 있으세요?', [I_CP, I_DYSP], 'cv', safety=True),
        U('wl_fever', 'red', 1, '최근 열이나 감기 기운이 있었나요?',
          [I_FEVER, ('wl_uri', '최근 감염', r'감기|목\s*아|기침|인후')], 'gen'),
        PS_MOOD,
        U('wl_hx', 'hx', 2, '심장병이나 갑상선 질환 있으세요?', [I_HEART, I_THY], 'hx'),
        U('wl_fh', 'fh', 1, '가족 중 갑상선병 있는 분 있나요?',
          [('fh_thyroid', '갑상샘 가족력', r'갑상|어머니|아버지|엄마|아빠|언니|동생|이모|할머니|가족')], 'fh'),
    ],
    'replace': {'fh_open': 'wl_fh'}, 'demote': {'hx_htn_dm': 2, 'sh_caffeine': 2},
    'exams': ['thyroid', 'eye_signs', 'post_tremor', 'skin_temp', 'heart', 'cervical_ln', 'abd_palp', 'power'],
}

CPX['fatigue'] = {
    'onset_q': '언제부터 피곤하셨어요?',
    'units': [
        U('ft_weight', 'core', 1, '최근 체중 변화가 있나요?', [('ft_weight', '체중 변화', r'체중|살|몸무게|kg|킬로|키로')], 'gen'),
        U('ft_sleep', 'core', 1, '잠은 잘 주무세요?', [('ps_sleep', '수면', r'잠|자|깨')], 'sleep'),
        U('ft_hypo', 'core', 1, '전보다 추위를 많이 타세요?', [('ft_cold', '추위 불내성', r'추위|춥')], 'endo'),
        U('ft_constip', 'core', 2, '변비가 생겼나요?', [('ros_constip', '변비', r'변비|변')], 'gi'),
        U('ft_dysp', 'core', 1, '조금만 움직여도 숨이 차나요?', [I_DYSP], 'cv'),
        U('ft_bleed', 'red', 1, '변이 검거나 피가 섞인 적 있나요?', [I_MELENA, I_HEMATO], 'gi', safety=True),
        U('ft_thirst', 'core', 1, '갈증이나 소변량 변화가 있나요?',
          [('ft_thirst', '갈증', r'갈증|목이\s*마르|물'), ('ft_urine', '소변량', r'소변')], 'gu'),
        U('ft_fever', 'red', 1, '열이나 식은땀이 나나요?', [I_FEVER, ('ft_sweat', '야간 발한', r'땀')], 'gen'),
        PS_MOOD,
        U('ft_snore', 'core', 2, '코골이나 숨 멈춤이 있다고 하나요?',
          [('in_snore', '코골이', r'코골|코를'), ('in_apnea', '수면 무호흡', r'멈|무호흡')], 'sleep'),
        U('ft_menor', 'core', 2, '생리량이 많은 편인가요?', [('ft_menorrhagia', '월경과다', r'많|양|생리')], 'wm'),
        U('ft_dizzy', 'core', 2, '일어설 때 어지러우세요?', [('ros_dizzy', '기립 어지럼', r'어지|핑')], 'neuro'),
        U('ft_edema', 'red', 2, '얼굴이나 다리가 붓나요?', [('ft_face_edema', '얼굴 부종', r'얼굴'), ('ft_leg_edema', '다리 부종', r'다리|발')],
          'gen'),
    ],
    'demote': {}, 'promote': {},
    'exams': ['conj', 'thyroid', 'heart', 'lung', 'cervical_ln', 'abd_palp', 'periph'],
}

CPX['palpitation'] = {
    'onset_q': '언제부터 두근거리셨어요?',
    'units': [
        U('pa_pattern', 'core', 1, '규칙적으로 빨리 뛰나요?', [('pa_pattern', '리듬·속도', r'규칙|불규칙|빨리|건너')], 'cv'),
        U('pa_onset', 'core', 1, '갑자기 시작해 갑자기 멈추나요?', [('pa_onset', '시작·종료 양상', r'갑자기|서서히|멈|천천히')], 'cv'),
        U('pa_duration', 'core', 1, '한 번 두근거리면 얼마나 가나요?', [('pa_duration', '지속 시간', r'분|초|시간|잠깐|계속')], 'cv'),
        U('pa_trigger', 'core', 1, '주로 언제 두근거리세요?', [('pa_trigger', '유발 상황', r'때|후|가만|운동|밤|커피')], 'cv'),
        U('pa_syncope', 'red', 1, '어지럽거나 쓰러질 것 같았나요?', [('ros_dizzy', '어지럼', r'어지|핑'), ('pa_syncope', '실신감', r'쓰러|정신')],
          'neuro', safety=True),
        U('pa_cardio', 'red', 1, '가슴 통증이나 숨찬 증상 있으세요?', [I_CP, I_DYSP], 'cv', safety=True),
        U('pa_heat', 'core', 2, '더위를 타거나 살이 빠졌나요?', [('wl_heat', '더위 불내성', r'더위|덥'), ('pa_wtloss', '체중 감소', r'살|체중|몸무게')],
          'gen'),
        U('pa_tremor', 'core', 2, '손 떨림이 있으세요?', [('wl_tremor', '손떨림', r'떨')], 'neuro'),
        U('pa_caff', 'sh', 1, '커피나 에너지음료를 자주 드세요?', [I_CAFF, ('pa_energy', '에너지음료', r'에너지|음료|박카스')], 'sh'),
        U('pa_hx', 'hx', 1, '심장병이나 갑상선 질환 있으세요?', [I_HEART, I_THY], 'hx', safety=True),
        U('pa_fh', 'fh', 1, '가족 중 심장병이나 돌연사 있나요?', [('fh_heart', '심장병 가족력', r'심장'), ('fh_sudden', '돌연사 가족력', r'돌연|갑자기')],
          'fh'),
        U('pa_anx', 'red', 2, '불안하거나 초조할 때가 많나요?', [('ps_anx', '불안·초조', r'불안|초조|예민')], 'psy'),
    ],
    'replace': {'fh_open': 'pa_fh', 'sh_caffeine': 'pa_caff'}, 'demote': {'hx_htn_dm': 2},
    'exams': ['radial', 'heart', 'thyroid', 'post_tremor', 'skin_temp', 'lung', 'jvp', 'periph'],
}

CPX['insomnia'] = {
    'onset_q': '언제부터 잠을 못 주무셨어요?',
    'units': [
        U('in_type', 'core', 1, '잠들기 어렵거나 자주 깨세요?',
          [('in_initiation', '입면 곤란', r'잠들|잠이\s*안|오래'), ('in_maintenance', '수면 유지 곤란', r'깨')], 'sleep'),
        U('in_hours', 'core', 1, '보통 몇 시에 자고 깨세요?', [('in_hours', '수면 시간대', r'시|새벽|밤')], 'sleep'),
        U('in_day', 'core', 1, '낮에 졸리거나 멍하세요?', [('in_sleepy', '주간 졸림', r'졸'), ('in_foggy', '주간 멍함·기능 저하', r'멍|집중')],
          'sleep'),
        U('in_meds', 'core', 1, '잠 때문에 드시는 약 있으세요?', [('in_meds', '수면제 사용', r'약|수면제|안정제')], 'drug',
          follow=('sb_name', '약 이름·용량', '드시는 약 이름과 용량을 아세요?', r'(mg|[가-힣](뎀|팜|람|녹스))')),
        U('in_anx', 'core', 1, '걱정이 많거나 불안하세요?', [('ps_worry', '걱정 과다', r'걱정|생각'), ('ps_anx', '불안', r'불안|초조')], 'psy'),
        U('in_snore', 'core', 2, '코골이나 숨 멈춤이 있다고 하나요?',
          [('in_snore', '코골이', r'코골|코를'), ('in_apnea', '수면 무호흡', r'멈|무호흡')], 'sleep'),
        U('in_legs', 'core', 3, '누우면 다리가 불편하고 저린가요?', [('in_legs', '하지불안', r'다리|저리')], 'neuro'),
        U('in_habit', 'core', 2, '자기 전 휴대폰을 오래 보세요?', [('in_habit', '수면 위생', r'휴대폰|폰|티비|봐요|보')], 'sleep'),
        PS_MOOD_SI,
        U('in_heat', 'red', 3, '더위를 타거나 땀이 많아졌나요?', [('wl_heat', '더위 불내성', r'더위|덥'), ('wl_sweat', '발한', r'땀')], 'gen'),
        U('in_living', 'sh', 2, '누구와 함께 사세요?', [('sh_living', '동거', r'남편|아내|혼자|가족|딸|아들|부모|함께')], 'sh'),
    ],
    'replace': {'sh_smoke_alc': 'sh_alc_smoke'}, 'promote': {'sh_caffeine': 1}, 'demote': {'fh_open': 3},
    'exams': ['mental', 'sedation', 'cognitive', 'post_tremor', 'thyroid', 'orthostatic', 'skin_temp'],
}

CPX['substance'] = {
    'onset_q': '언제부터 잠을 못 주무셨어요?',
    'units': [
        U('sb_name', 'core', 1, '드시는 수면제 이름과 용량을 아세요?',
          [('sb_name', '약 이름', r'[가-힣]{1,}(뎀|팜|람|녹스|핀)|이름|수면제|졸피'), ('sb_mg', '1회 용량', r'mg|밀리|알|정|그램')], 'drug'),
        U('sb_dose_now', 'core', 1, '요즘 하루에 몇 알 드세요?', [('sb_dose_now', '현재 복용량', r'알|정|개|번')], 'drug'),
        U('sb_tol', 'core', 1, '처음보다 양이 늘거나 효과가 줄었나요?',
          [('sb_tolerance', '내성(증량)', r'늘|많아|양|알'), ('sb_effect', '효과 감소', r'효과|안\s*들|잠이\s*안|소용')], 'drug'),
        U('sb_withdraw', 'core', 1, '약을 안 드시면 어떤 증상이 있나요?', [('sb_withdraw', '금단 증상', r'.')], 'drug'),
        U('sb_cutdown', 'core', 1, '줄이거나 끊어 보려 하신 적 있나요?', [('sb_cutdown', '감량 시도·실패', r'.')], 'drug'),
        U('sb_seizure', 'core', 1, '끊었을 때 경련이나 헛것이 있었나요?',
          [('sb_seizure', '금단 경련', r'경련|발작'), ('sb_delirium', '금단 환각·섬망', r'헛것|환각|환청|헛')], 'drug', safety=True),
        U('sb_sources', 'core', 1, '약은 어디서 처방받으세요?', [('sb_sources', '처방 기관', r'.')], 'drug'),
        U('sb_other', 'core', 1, '다른 수면제나 약국 약도 드세요?',
          [('sb_other_rx', '타 진정수면제', r'수면제|안정제|신경'), ('sb_otc', '약국 수면유도제', r'약국|유도제|수면유도')], 'drug'),
        U('sb_last', 'core', 1, '마지막으로 언제 몇 알 드셨어요?', [('sb_last', '마지막 복용', r'.')], 'drug', safety=True),
        U('sb_blackout', 'core', 2, '약 드신 뒤 기억이 끊긴 적 있나요?', [('sb_blackout', '기억 공백', r'기억|생각')], 'drug'),
        U('sb_family', 'core', 2, '가족과 약 문제로 갈등이 있나요?', [('sb_family', '가족 갈등', r'.')], 'psy'),
        U('in_day', 'core', 2, '낮에 졸리거나 멍하세요?', [('in_sleepy', '주간 졸림', r'졸'), ('in_foggy', '주간 멍함·기능 저하', r'멍|집중')],
          'sleep'),
        PS_MOOD_SI,
        U('sb_drive', 'red', 3, '약 드시고 운전하신 적 있나요?', [('sb_drive', '운전', r'운전|차')], 'drug'),
        U('sb_meds2', 'hx', 1, '그 밖에 드시는 약이 있나요?', [I_MEDS], 'meds'),
    ],
    'replace': {'hx_meds': 'sb_meds2', 'sh_smoke_alc': 'sh_alc_smoke'},
    'demote': {'hx_htn_dm': 2, 'sh_job': 3},
    'exams': ['mental', 'sedation', 'cognitive', 'orthostatic', 'post_tremor', 'cerebellar', 'gait'],
}

CPX['mood'] = {
    'onset_q': '언제부터 기분이 그러셨어요?',
    'units': [
        U('md_trigger', 'core', 1, '힘든 일이 있으셨나요?', [('md_trigger', '계기·스트레스', r'.')], 'psy'),
        U('md_interest', 'core', 1, '즐겁던 일에 흥미가 줄었나요?', [I_INTEREST], 'psy'),
        U('md_sleep', 'core', 1, '잠은 잘 주무세요?', [('ps_sleep', '수면', r'잠|자|깨')], 'sleep'),
        U('md_appetite', 'core', 1, '입맛이나 체중이 변했나요?', [('ros_anorexia', '식욕', r'입맛|식욕|먹'), ('md_weight', '체중 변화', r'체중|살|몸무게')],
          'gen'),
        U('md_energy', 'core', 2, '기운이 없거나 집중이 어려우세요?', [('ros_fatigue', '기력 저하', r'기운|피곤|지치'), ('md_concent', '집중력 저하', r'집중')],
          'psy'),
        U('md_si', 'red', 1, '혹시 죽고 싶은 생각이 드신 적 있나요?', [I_SI], 'psy', safety=True,
          follow=('md_plan', '자살 계획', '구체적으로 방법을 생각해 보셨나요?', None)),
        U('md_guilt', 'core', 2, '자신이 쓸모없다고 느끼세요?', [('md_guilt', '무가치감', r'.')], 'psy'),
        U('md_mania', 'red', 2, '기분이 지나치게 들뜬 적 있나요?', [('ps_mania', '조증 선별', r'들뜬|들떠|기분')], 'psy'),
        U('md_prior', 'hx', 2, '정신과 진료받아 보신 적 있으세요?', [('ps_prior', '정신과 치료력', r'정신과|상담|진료')], 'hx'),
        U('md_hx', 'hx', 1, '갑상선 질환이나 다른 지병 있으세요?', [I_THY, I_OTHER], 'hx'),
        U('md_fh', 'fh', 2, '가족 중 우울증 앓은 분 있나요?', [('fh_psych', '정신질환 가족력', r'우울|정신|어머니|아버지|엄마|아빠|가족')], 'fh'),
        U('md_living', 'sh', 2, '누구와 함께 사세요?', [('sh_living', '동거', r'남편|아내|혼자|가족|딸|아들|부모|함께')], 'sh'),
    ],
    'replace': {'fh_open': 'md_fh', 'sh_smoke_alc': 'sh_alc_smoke'},
    'exams': ['mental', 'affect', 'cognitive', 'insight', 'thyroid', 'sedation', 'post_tremor'],
}

CPX['headache'] = {
    'onset_q': '언제부터 머리가 아프셨어요?',
    'units': [
        U('ha_sudden', 'core', 1, '갑자기 시작됐나요?', [('ha_onset', '발생 양상', r'갑자기|서서히|천천히')], 'neuro'),
        U('ha_site', 'core', 1, '머리 어디가 아프세요?', [('ha_site', '부위', r'.')], 'neuro'),
        U('ha_char', 'core', 1, '어떻게 아프세요?', [('ha_char', '양상', r'.')], 'neuro'),
        U('ha_nrs', 'core', 1, '0에서 10점이면 몇 점이에요?', [('ha_nrs', '강도(NRS)', r'\d|점')], 'neuro'),
        U('ha_freq', 'core', 1, '한 번 아프면 얼마나 가나요?', [('ha_duration', '지속 시간', r'.')], 'neuro'),
        U('ha_nv', 'core', 1, '메스껍거나 토하세요?', [I_NV_N, I_NV_V], 'gi'),
        U('ha_photo', 'core', 2, '빛이나 소리에 예민해지나요?', [('ha_photo', '빛 과민', r'빛|눈부'), ('ha_phono', '소리 과민', r'소리|시끄')],
          'neuro'),
        U('ha_neuro', 'red', 1, '팔다리 힘 빠짐이나 말 어눌함은요?',
          [('ha_weak', '편측 위약', r'힘|팔|다리'), ('ha_speech', '구음장애', r'말|어눌')], 'neuro', safety=True),
        U('ha_fever', 'red', 1, '열이 나나요?', [I_FEVER], 'gen', safety=True),
        U('ha_neck', 'red', 1, '목이 뻣뻣하세요?', [('ha_neck', '경부 강직', r'목|뻣뻣')], 'neuro', safety=True),
        U('ha_worst', 'red', 1, '평생 처음 겪는 심한 두통인가요?', [('ha_worst', '최악의 두통', r'.')], 'neuro', safety=True),
        U('ha_vision', 'red', 2, '물체가 둘로 보이거나 흐린가요?', [('ha_diplopia', '복시', r'둘'), ('ha_blur', '시야 흐림', r'흐리|흐려|침침')],
          'eye'),
        U('ha_morning', 'core', 2, '아침에 일어날 때 더 심한가요?', [('ha_morning', '아침 악화', r'.')], 'neuro'),
        U('ha_analgesic', 'hx', 1, '진통제는 얼마나 자주 드세요?', [('ha_analgesic', '진통제 사용', r'.')], 'meds'),
        U('ha_trauma', 'red', 2, '최근 머리를 다친 적 있나요?', [('ha_trauma', '두부 외상', r'다치|부딪|넘어')], 'neuro'),
        U('ha_contra', 'hx', 2, '위궤양이나 콩팥병 있으세요?', [('pmh_ulcer', '위궤양', r'위궤양|위|속'), ('pmh_kidney', '콩팥병', r'콩팥|신장')], 'hx',
          safety=True),
    ],
    'promote': {'sh_caffeine': 2},
    'exams': ['pupil', 'fundus', 'eom', 'neck_stiff', 'face_sym', 'pronator', 'cerebellar', 'power'],
}

CPX['dizziness'] = {
    'onset_q': '언제부터 어지러우셨어요?',
    'units': [
        U('dz_type', 'core', 1, '빙빙 도는 느낌인가요?', [('dz_type', '어지럼 양상', r'.')], 'neuro'),
        U('dz_position', 'core', 1, '고개를 돌리거나 누울 때 심하나요?', [('dz_turn', '고개 돌릴 때', r'고개|돌리'), ('dz_lying', '누울 때', r'누우|누울|일어')],
          'neuro'),
        U('dz_duration', 'core', 1, '한 번 어지러우면 얼마나 가나요?', [('dz_duration', '지속 시간', r'.')], 'neuro'),
        U('dz_hearing', 'core', 1, '귀가 먹먹하거나 소리가 나나요?', [('dz_fullness', '이충만감·난청', r'먹먹|안\s*들|난청'), ('dz_tinnitus', '이명', r'소리|윙|삐')],
          'ent'),
        U('dz_nv', 'core', 2, '메스껍거나 토하세요?', [I_NV_N, I_NV_V], 'gi'),
        U('dz_neuro', 'red', 1, '말이 어눌하거나 얼굴이 처지나요?',
          [('dz_speech', '구음장애', r'말|어눌'), ('dz_face', '안면 처짐', r'얼굴|처지|처져|처졌')], 'neuro', safety=True),
        U('dz_diplopia', 'red', 2, '물체가 둘로 보이나요?', [('dz_diplopia', '복시', r'둘|겹')], 'eye'),
        U('dz_weak', 'red', 1, '팔다리에 힘이 빠지거나 저리나요?', [('dz_weak', '위약', r'힘'), ('dz_numb', '감각 이상', r'저리|저려|감각')], 'neuro',
          safety=True),
        U('dz_syncope', 'red', 1, '쓰러지거나 정신을 잃은 적 있나요?', [('dz_fall', '쓰러짐', r'쓰러|넘어'), ('dz_loc', '의식 소실', r'정신|기절')],
          'neuro', safety=True),
        U('dz_cardio', 'red', 2, '가슴 통증이나 두근거림이 있나요?', [I_CP, ('ros_palp', '두근거림', r'두근|뛰')], 'cv'),
        U('dz_stand', 'core', 2, '일어설 때 더 어지러우세요?', [('dz_orthostatic', '기립 시 악화', r'.')], 'neuro'),
        U('dz_uri', 'core', 3, '최근 감기를 앓으셨나요?', [('dz_uri', '선행 감염', r'감기|열|기침')], 'gen'),
    ],
    'promote': {'hx_htn_dm': 1}, 'demote': {'fh_open': 3},
    'exams': ['orthostatic', 'nystagmus', 'dix', 'cerebellar', 'romberg', 'gait', 'heart', 'ear'],
}

CPX['chest_pain'] = {
    'onset_q': '언제부터 가슴이 아프셨어요?',
    'units': [
        U('cp_site', 'core', 1, '가슴 어디가 아프세요?', [('cp_site', '부위', r'.')], 'cv'),
        U('cp_char', 'core', 1, '어떻게 아프세요?', [('cp_char', '양상', r'.')], 'cv'),
        U('cp_rad', 'core', 1, '팔이나 턱으로 뻗치나요?', [('cp_rad_arm', '팔 방사통', r'팔|어깨'), ('cp_rad_jaw', '턱 방사통', r'턱|목')], 'cv'),
        U('cp_exert', 'core', 1, '걷거나 계단 오를 때 심해지나요?', [('cp_exert', '운동 연관', r'.')], 'cv'),
        U('cp_rest', 'core', 1, '쉬면 나아지나요?', [('cp_rest', '휴식 완화', r'.')], 'cv'),
        U('cp_duration', 'core', 1, '한 번 아프면 얼마나 가나요?', [('cp_duration', '지속 시간', r'.')], 'cv'),
        U('cp_assoc', 'red', 1, '아플 때 숨이 같이 차나요?', [I_DYSP], 'cv', safety=True),
        U('cp_sweat', 'red', 2, '아플 때 식은땀이 나나요?', [('cp_sweat', '식은땀', r'땀')], 'cv'),
        U('cp_breath', 'core', 2, '숨 쉬거나 누울 때 더 아픈가요?', [('cp_pleuritic', '흡기·자세 악화', r'.')], 'cv'),
        U('cp_meal', 'core', 2, '식사 후 속이 쓰린가요?', [('cp_gerd', '속쓰림', r'쓰리|속|신물')], 'gi'),
        U('cp_leg', 'red', 2, '한쪽 다리가 붓거나 아픈가요?', [('cp_leg', '하지 부종·통증', r'.')], 'cv', safety=True),
        U('cp_lipid', 'hx', 1, '콜레스테롤이나 심장병 있으세요?', [('pmh_lipid', '이상지질혈증', r'콜레스테롤|고지혈|기름'), I_HEART], 'hx'),
        U('cp_fh', 'fh', 1, '가족 중 심장병 앓은 분 있나요?', [('fh_heart', '심장병 가족력', r'심장|어머니|아버지|엄마|아빠|형|가족')], 'fh'),
    ],
    'replace': {'fh_open': 'cp_fh'},
    'exams': ['heart', 'lung', 'chest_wall', 'radial', 'jvp', 'periph', 'calf', 'abd_palp'],
}

CPX['dyspnea'] = {
    'onset_q': '언제부터 숨이 차셨어요?',
    'units': [
        U('dy_sudden', 'core', 1, '갑자기 숨이 찼나요?', [('dy_onset', '발생 양상', r'갑자기|서서히|천천히')], 'resp'),
        U('dy_exert', 'core', 1, '어느 정도 움직이면 숨이 차나요?', [('dy_exert', '운동 정도', r'.')], 'resp'),
        U('dy_orthop', 'core', 1, '누우면 숨이 더 차나요?', [('dy_orthopnea', '기좌호흡', r'.')], 'cv'),
        U('dy_pnd', 'core', 2, '자다가 숨이 차서 깬 적 있나요?', [('dy_pnd', '야간 호흡곤란', r'.')], 'cv'),
        U('dy_edema', 'core', 1, '다리가 붓나요?', [('dy_edema', '하지 부종', r'붓|부어|부종')], 'cv'),
        U('dy_cough', 'core', 1, '기침이나 가래가 있나요?', [('ros_cough', '기침', r'기침'), ('ros_sputum', '가래', r'가래')], 'resp'),
        U('dy_wheeze', 'core', 1, '숨 쉴 때 쌕쌕 소리가 나나요?', [('dy_wheeze', '천명', r'.')], 'resp'),
        U('dy_cp', 'red', 1, '가슴 통증도 있나요?', [I_CP], 'cv', safety=True),
        U('dy_fever', 'red', 2, '열이나 오한 있으세요?', [I_FEVER, I_CHILL], 'gen'),
        U('dy_hemop', 'red', 2, '가래에 피가 섞인 적 있나요?', [('dy_hemoptysis', '객혈', r'.')], 'resp', safety=True),
        U('dy_hx_lung', 'hx', 1, '천식이나 폐 질환 있으세요?', [I_ASTHMA, ('pmh_lung', '폐 질환', r'폐|결핵')], 'hx'),
        U('dy_hx_heart', 'hx', 1, '고혈압이나 심장병 있으세요?', [I_HTN, I_HEART], 'hx'),
        U('dy_smoke', 'sh', 1, '담배나 술은 하세요?', [I_SMOKE, I_ALC], 'sh',
          follow=('sh_smoke_amt', '흡연량', '하루 몇 개비씩 피우세요?', r'(개비|갑|반)', 'sh_smoke')),
        U('dy_job', 'sh', 2, '일하면서 먼지나 연기를 마시나요?', [('sh_dust', '분진 노출', r'먼지|분진'), ('sh_fume', '연기 노출', r'연기|가스')], 'sh'),
    ],
    'replace': {'hx_htn_dm': 'dy_hx_heart', 'sh_smoke_alc': 'dy_smoke'},
    'exams': ['chest_insp', 'lung', 'chest_perc', 'heart', 'jvp', 'periph', 'calf', 'clubbing'],
}

CPX['cough_fever'] = {
    'onset_q': '기침은 언제부터 하셨어요?',
    'units': [
        U('cf_sputum', 'core', 1, '가래가 나오면 무슨 색인가요?', [('ros_sputum', '가래', r'.')], 'resp'),
        U('cf_fever', 'core', 1, '열은 몇 도까지 났어요?', [I_FEVER], 'gen'),
        U('cf_dysp', 'red', 1, '숨이 차지는 않으세요?', [I_DYSP], 'resp', safety=True),
        U('cf_uri', 'core', 1, '콧물이나 목 아픔이 있나요?', [('ros_rhinorrhea', '콧물', r'콧물|코'), ('cf_sore', '인후통', r'목')], 'ent'),
        U('cf_hemop', 'red', 1, '가래에 피가 섞인 적 있나요?', [('cf_hemoptysis', '객혈', r'.')], 'resp', safety=True),
        U('cf_cp', 'red', 2, '기침할 때 가슴이 아픈가요?', [I_CP], 'resp'),
        U('cf_wt', 'red', 2, '체중 감소나 식은땀이 있나요?', [('cf_wtloss', '체중 감소', r'체중|살|몸무게'), ('cf_sweat', '야간 발한', r'땀')], 'gen'),
        U('cf_contact', 'core', 2, '주변에 비슷하게 아픈 사람 있나요?', [('cf_contact', '접촉력', r'.')], 'gen'),
        U('cf_hx', 'hx', 1, '천식이나 약 알레르기 있으세요?', [I_ASTHMA, I_ALLERGY], 'hx', safety=True),
        U('cf_tb', 'hx', 2, '결핵이나 간염 앓은 적 있으세요?', [('pmh_tbc', '결핵', r'결핵'), ('pmh_hep', '간염', r'간염')], 'hx'),
        U('cf_gerd', 'core', 3, '속쓰림이나 신물이 올라오나요?', [('cf_heartburn', '속쓰림', r'쓰리|속'), ('cf_regurg', '역류', r'신물|올라')], 'gi'),
    ],
    'replace': {'hx_allergy': 'cf_hx'}, 'demote': {'hx_htn_dm': 2},
    'exams': ['pharynx', 'cervical_ln', 'lung', 'chest_perc', 'heart', 'ear', 'sinus'],
}

CPX['abd_pain'] = {
    'onset_q': '언제부터 배가 아프셨어요?',
    'units': [
        U('ap_site', 'core', 1, '배 어디가 아프세요?', [('ap_site', '부위', r'.')], 'gi'),
        U('ap_char', 'core', 1, '어떻게 아프세요?', [('ap_char', '양상', r'.')], 'gi'),
        U('ap_nrs', 'core', 1, '0에서 10점이면 몇 점이에요?', [('ap_nrs', '강도(NRS)', r'\d|점')], 'gi'),
        U('ap_migrate', 'core', 2, '아픈 곳이 옮겨 갔나요?', [('ap_migrate', '통증 이동', r'.')], 'gi'),
        U('ap_meal', 'core', 1, '식사와 관련해 달라지나요?', [('ap_meal', '식사 연관', r'.')], 'gi'),
        U('ap_nv', 'core', 1, '메스껍거나 토하세요?', [I_NV_N, I_NV_V], 'gi'),
        U('ap_bowel', 'core', 1, '설사나 변비가 있나요?', [('ros_diarrhea', '설사', r'설사|묽'), ('ros_constip', '변비', r'변비|딱딱')], 'gi'),
        U('ap_blood', 'red', 1, '변이 검거나 피가 섞이나요?', [I_MELENA, I_HEMATO], 'gi', safety=True),
        U('ap_fever', 'red', 1, '열이나 오한이 있나요?', [I_FEVER, I_CHILL], 'gen'),
        U('ap_urine', 'red', 2, '소변 볼 때 아프세요?', [('ur_dysuria', '배뇨통', r'.')], 'gu'),
        U('ap_rad', 'core', 2, '등이나 다른 곳으로 뻗치나요?', [('ap_rad', '방사통', r'.')], 'gi'),
        U('ap_lmp', 'core', 1, '마지막 생리는 언제였어요?', [('wm_lmp', 'LMP', r'.')], 'wm'),
        U('ap_op', 'hx', 1, '배 수술받은 적 있으세요?', [I_OP], 'hx'),
        U('ap_nsaid', 'hx', 2, '진통제나 술을 자주 드세요?', [('ap_nsaid', '진통제 사용', r'진통제|약'), I_ALC], 'meds'),
        U('ap_fh', 'fh', 2, '가족 중 위암이나 대장암 있나요?', [('fh_gi_ca', '위장관암 가족력', r'암|어머니|아버지|가족')], 'fh'),
    ],
    'women_only': {'ap_lmp'}, 'replace': {'fh_open': 'ap_fh'}, 'demote': {'hx_htn_dm': 2},
    'exams': ['abd_insp', 'bowel', 'abd_palp', 'rebound', 'murphy', 'mcburney', 'cva', 'liver_spleen'],
}

CPX['gi'] = {
    'onset_q': '언제부터 그러셨어요?',
    'units': [
        U('gi_char', 'core', 1, '속이 어떻게 불편하세요?', [('gi_char', '양상', r'.')], 'gi'),
        U('gi_meal', 'core', 1, '식후에 더 심해지나요?', [('gi_meal', '식사 연관', r'.')], 'gi'),
        U('gi_heartburn', 'core', 1, '속쓰림이나 신물이 올라오나요?', [('gi_heartburn', '속쓰림', r'쓰리|속'), ('gi_regurg', '역류', r'신물|올라')],
          'gi'),
        U('gi_nv', 'core', 1, '메스껍거나 토하세요?', [I_NV_N, I_NV_V], 'gi'),
        U('gi_stool', 'core', 1, '대변 횟수나 모양이 변했나요?', [('gi_stool_freq', '배변 횟수', r'번|회|자주'), ('gi_stool_form', '변 양상', r'묽|설사|딱딱|변비|모양')],
          'gi'),
        U('gi_dysphagia', 'red', 1, '삼킬 때 걸리거나 아픈가요?', [('gi_dysphagia', '연하곤란', r'걸리|걸려'), ('gi_odynophagia', '연하통', r'아프|아파')],
          'gi', safety=True),
        U('gi_blood', 'red', 1, '변이 검거나 피가 섞이나요?', [I_MELENA, I_HEMATO], 'gi', safety=True),
        U('gi_weight', 'red', 1, '살이 빠지셨나요?', [('gi_weight', '체중 감소', r'.')], 'gen', safety=True),
        U('gi_relief', 'core', 2, '변을 보면 배가 편해지나요?', [('gi_relief', '배변 후 완화', r'.')], 'gi'),
        U('gi_food', 'core', 2, '상한 음식이나 여행력 있나요?', [('gi_food', '음식', r'음식|먹'), ('gi_travel', '여행', r'여행')], 'gi'),
        U('gi_nsaid', 'hx', 1, '진통제나 술을 자주 드세요?', [('gi_nsaid', '진통제 사용', r'진통제|약'), I_ALC], 'meds'),
        U('gi_fh', 'fh', 2, '가족 중 위암이나 대장암 있나요?', [('fh_gi_ca', '위장관암 가족력', r'암|어머니|아버지|가족')], 'fh'),
    ],
    'replace': {'fh_open': 'gi_fh'}, 'demote': {'hx_htn_dm': 2},
    'exams': ['abd_insp', 'bowel', 'abd_palp', 'liver_spleen', 'abd_perc', 'conj', 'cervical_ln'],
}

CPX['urinary'] = {
    'onset_q': '언제부터 그러셨어요?',
    'units': [
        U('ur_dysuria', 'core', 1, '소변 볼 때 아프세요?', [('ur_dysuria', '배뇨통', r'.')], 'gu'),
        U('ur_freq', 'core', 1, '소변이 자주 마렵거나 급하세요?', [('ur_freq', '빈뇨', r'자주'), ('ur_urgency', '절박뇨', r'급|참')], 'gu'),
        U('ur_hematuria', 'core', 1, '소변에 피가 섞이나요?', [('ur_hematuria', '혈뇨', r'.')], 'gu'),
        U('ur_flank', 'red', 1, '옆구리나 허리가 아프세요?', [('ur_flank', '옆구리 통증', r'옆구리'), ('ur_back', '요통', r'허리')], 'gu'),
        U('ur_fever', 'red', 1, '열이나 오한이 있나요?', [I_FEVER, I_CHILL], 'gen', safety=True),
        U('ur_stream', 'core', 2, '소변 줄기가 약해졌나요?', [('ur_stream', '배뇨 곤란', r'.')], 'gu'),
        U('ur_discharge', 'core', 2, '분비물이 늘거나 냄새가 나나요?', [('ur_discharge', '분비물', r'분비|냉'), ('ur_odor', '냄새', r'냄새')], 'gu'),
        U('ur_history', 'hx', 2, '전에 방광염이나 결석 있었나요?', [('pmh_uti', '방광염 과거력', r'방광염|염증'), ('pmh_stone', '결석', r'결석|돌')], 'hx'),
        U('ur_nv', 'red', 2, '메스껍거나 토하세요?', [I_NV_N, I_NV_V], 'gi'),
    ],
    'promote': {'hx_allergy': 1},
    'exams': ['cva', 'abd_palp', 'abd_insp', 'abd_perc', 'genital', 'periph'],
}

CPX['edema'] = {
    'onset_q': '언제부터 부으셨어요?',
    'units': [
        U('ed_site', 'core', 1, '어디가 주로 붓나요?', [('ed_site', '부위', r'.')], 'gen'),
        U('ed_side', 'core', 1, '양쪽 다리가 다 붓나요?', [('ed_side', '양측성', r'.')], 'gen'),
        U('ed_time', 'core', 2, '아침과 저녁 중 언제 더 붓나요?', [('ed_time', '시간대', r'.')], 'gen'),
        U('ed_dysp', 'red', 1, '숨이 차거나 가슴이 답답한가요?', [I_DYSP, ('ed_chest', '흉부 압박감', r'답답|가슴')], 'cv', safety=True),
        U('ed_urine', 'core', 1, '소변에 거품이 많거나 줄었나요?', [('ed_foam', '거품뇨', r'거품'), ('ed_oliguria', '소변량 감소', r'줄|양')], 'gu'),
        U('ed_weight', 'core', 2, '최근 몸무게가 늘었나요?', [('ed_weight', '체중 증가', r'.')], 'gen'),
        U('ed_drug', 'hx', 1, '혈압약이나 진통제 드세요?', [('ed_bp_drug', '혈압약', r'혈압'), ('ed_nsaid', '진통제', r'진통제')], 'meds'),
        U('ed_hx', 'hx', 1, '심장병이나 콩팥병 있으세요?', [I_HEART, ('pmh_kidney', '콩팥병', r'콩팥|신장')], 'hx'),
        U('ed_liver', 'hx', 2, '간이 안 좋다고 들으셨나요?', [('pmh_liver', '간질환', r'.')], 'hx'),
        U('ed_hypo', 'core', 2, '전보다 추위를 많이 타세요?', [('ft_cold', '추위 불내성', r'추위|춥')], 'endo'),
        U('ed_calf', 'red', 2, '한쪽 다리가 아프거나 붉은가요?', [('ed_calf_pain', '편측 하지 통증', r'아프|아파'), ('ed_calf_red', '발적', r'붉|빨')],
          'cv', safety=True),
    ],
    'exams': ['periph', 'jvp', 'heart', 'lung', 'shifting', 'liver_spleen', 'thyroid', 'abd_insp'],
}

CPX['growth'] = {
    'onset_q': '언제부터 작다는 말을 들었나요?',
    'peds': True,
    'units': [
        U('gr_record', 'core', 2, '예전에 잰 키 기록이 있나요?', [('gr_record', '성장 기록', r'.')], 'growth',
          follow=('gr_values', '과거 계측치', '두 살, 네 살 때 키는 얼마였나요?', r'(\d{2,3}|센티|cm)')),
        U('gr_parents', 'core', 1, '부모님 키는 각각 어떻게 되세요?', [('gr_parents', '부모 키', r'\d|센티|cm|커|작')], 'growth'),
        U('gr_late', 'core', 1, '부모님 중 늦게 키가 큰 분 있나요?', [('gr_late', '부모 사춘기 지연', r'.')], 'growth'),
        U('gr_fh', 'fh', 1, '가족 중 키가 작거나 유전병 있나요?', [('gr_fh_short', '저신장 가족력', r'키|작'), ('gr_fh_genetic', '유전병 가족력', r'유전')],
          'fh'),
        U('gr_puberty', 'core', 1, '음모나 고환 변화가 있었나요?', [('gr_pubic', '음모', r'음모|털'), ('gr_testis', '고환 변화', r'고환')], 'growth'),
        U('gr_hypo', 'red', 1, '잘 지치거나 추위를 타나요?',
          [('gr_fatigue', '피로', r'지치|피곤'), ('ft_cold', '추위 불내성', r'추위|춥')], 'endo'),
        U('gr_constip', 'red', 3, '변비가 있나요?', [('ros_constip', '변비', r'변비')], 'gi'),
        U('gr_ich', 'red', 1, '머리가 자주 아프다고 하나요?', [('ros_headache', '두통', r'두통|머리|아프|아파')], 'neuro', safety=True),
        U('gr_vision', 'red', 2, '눈이 잘 안 보인다고 하나요?', [('gr_vision', '시야 이상', r'시야|눈|보')], 'eye'),
        U('gr_cushing', 'red', 2, '배만 나오거나 얼굴이 둥글어졌나요?', [('gr_central', '중심성 비만', r'배'), ('gr_moon', '달덩이 얼굴', r'얼굴')],
          'endo'),
        U('gr_chronic', 'hx', 1, '천식이나 장, 콩팥 질환 들은 적 있나요?',
          [I_ASTHMA, ('gr_gi', '장 질환', r'장'), ('gr_kidney', '콩팥 질환', r'콩팥|신장')], 'hx'),
        U('gr_steroid', 'hx', 1, '스테로이드나 한약 먹은 적 있나요?', [('gr_steroid', '스테로이드', r'스테로이드'), ('gr_herbal', '한약', r'한약')],
          'meds'),
        U('gr_weight', 'core', 2, '최근 살이 빠지거나 찌진 않았나요?', [('gr_wt_loss', '체중 감소', r'빠지|빠졌'), ('gr_wt_gain', '체중 증가', r'찌|쪘')],
          'gen'),
        U('gr_milk', 'sh', 3, '우유는 하루 얼마나 마시나요?', [('gr_milk', '우유 섭취', r'.')], 'peds'),
    ],
    'replace': {'p_fh': 'gr_fh', 'p_meds': 'gr_steroid'},
    'promote': {'p_perinatal': 1, 'p_develop': 1, 'p_daycare': 2},
    'add_common': [P_BIRTH, P_DIET, P_SLEEP],
    'exams': ['anthro', 'growth_chart', 'body_prop', 'tanner', 'dysmorph', 'thyroid', 'striae'],
}

# 그 밖의 주호소: 기존 bank2.CATEGORY_Q + 접수 LLM 생성 체크리스트로 폴백(보고서에 명시)
FALLBACK_EXAMS_N = 7

# ---------------------------------------------------------------- 계통 사전 (자유 질문 검증용)
SYSTEM_LEX = [
    ('cv', r'가슴|흉통|두근|심장|숨이?\s*차|숨참|숨찬|맥|부정맥|협심'),
    ('resp', r'기침|가래|쌕쌕|천명|폐|객혈'),
    ('gi', r'배|복통|구토|토하|메스|구역|설사|변비|대변|혈변|검은\s*변|속쓰|소화|신물|삼킬'),
    ('gu', r'소변|오줌|배뇨|갈증|물을'),
    ('neuro', r'두통|머리|어지|저리|저림|마비|힘이?\s*빠|떨|경련|어눌|쓰러|기억'),
    ('eye', r'눈|시야|시력|침침|둘로|튀어나'),
    ('neck', r'목이?\s*(붓|부|두꺼)|목\s*앞|혹|멍울|갑상'),
    ('psy', r'기분|우울|불안|초조|죽고|자살|의욕|흥미'),
    ('sleep', r'잠|불면|졸리|코골|깨'),
    ('gen', r'열|오한|땀|더위|추위|체중|살이|피곤|피로|지치|기운'),
    ('wm', r'생리|월경|임신'),
    ('sh', r'담배|술|커피|운동|직업|일\s*하'),
    ('hx', r'고혈압|당뇨|지병|수술|입원|알레르기|천식|결핵|간염|질환|병'),
    ('meds', r'약|영양제|한약|보조제|진통제'),
    ('fh', r'가족|부모|형제|어머니|아버지'),
]
# '과/와'는 구분자로 보지 않는다('예전과', '가족과' 오탐)
SEP_RE = re.compile(r'(이나\s|거나\s|[가-힣]나\s|·|,|랑\s|이랑\s)')
MIXED_RE = re.compile(r'거나\s.+[가-힣]고\s(?!싶)')
AFFINITY = ({'sleep', 'psy'},)            # 교차 계통이지만 짝으로 허용하는 조합
NAME_SYS = ('hx', 'meds', 'fh')           # 병력·약·가족력 '이름' 나열은 장기와 무관하게 허용
# 3항목 병력 이름 나열(hx3)에 넣으면 안 되는 안전 항목(단독·짝으로만 묻는다)
SAFETY_ITEMS = {'ps_si', 'wm_preg', 'pmh_allergy', 'sb_seizure', 'sb_delirium', 'sb_last', 'ros_cp', 'ros_dysp',
                'ros_hematochezia', 'ros_melena', 'pmh_heart'}


def systems_of(text: str) -> list[str]:
    out = []
    for sys_, pat in SYSTEM_LEX:
        if re.search(pat, text or '') and sys_ not in out:
            out.append(sys_)
    return out


def count_items(q: str) -> int:
    return len(SEP_RE.findall(nfc(q))) + 1


def check_question(q: str, whitelisted: bool = False) -> tuple[bool, str]:
    """v8 묶음 질문 검증기. 은행 문구(whitelisted)는 테스트로 따로 검증하므로 길이·문법만 본다.
    자유 질문: 3항목 이상 금지, '~거나 ~고' 금지, 두 질문(쉼표·물음표 2개) 금지, 2항목이면 계통이 같아야 함."""
    t = nfc(q or '').strip()
    if not t:
        return False, 'empty'
    if len(t) > MAX_Q:
        return False, 'too_long'
    if t.count('?') > 1:
        return False, 'two_questions'
    if re.search(r'(나요|세요|까요|어요|가요)\s*,\s*\S', t):
        return False, 'comma_two_questions'
    if whitelisted:
        return True, 'ok'
    if MIXED_RE.search(t):
        return False, 'mixed_predicate'
    n = count_items(t)
    if n >= 3:
        return False, 'three_items'
    if n == 2:
        parts = [p for p in SEP_RE.split(t) if p and not SEP_RE.fullmatch(p)]
        if len(parts) >= 2:
            a, b = set(systems_of(parts[0])), set(systems_of(' '.join(parts[1:])))
            if a and b and not a & b and not any(a | b <= s for s in AFFINITY) and not a | b <= set(NAME_SYS):
                return False, 'cross_system'
    return True, 'ok'


def bundle_violation(u: dict) -> str:
    """은행 단위 묶음 규칙(v8c). '' = 통과.
    한 문장·30자·물음표 1개·공통 술어 하나, 같은 계통 최대 2항목(중요 항목 먼저).
    예외: 병력 질환 이름 3개 나열(hx3, 안전 항목·safety 없음), 가족력 이름 나열, 병력·약 이름 짝, {수면, 정신} 짝."""
    t = nfc(u.get('q') or '').strip()
    ok, why = check_question(t, whitelisted=True)
    if not ok:
        return why
    if t.count('?') != 1:
        return 'no_question_mark'
    if MIXED_RE.search(t):
        return 'mixed_predicate'
    items = u.get('items') or []
    n = len(items)
    if n <= 1:
        return ''
    isys = list(u.get('isys') or [u.get('sys')] * n)
    if len(isys) != n:
        return 'isys_len'
    sys_ = u.get('sys')
    if n >= 4:
        return 'four_items'
    if n == 3:
        if sys_ == 'fh':
            return ''
        if sys_ != 'hx' or u.get('kind') != 'hx3':
            return 'three_items'
        if u.get('safety') or any(i[0] in SAFETY_ITEMS for i in items):
            return 'hx3_safety'
        return ''
    if sys_ in NAME_SYS:
        return ''
    s = set(isys)
    if len(s) == 1 or any(s <= a for a in AFFINITY):
        return ''
    return 'cross_system'


NUM_RE = re.compile(r'\d|cm|센티|킬로|평균|이하|이상인가요|퍼센트|%')
ADULT_PHRASE_RE = re.compile(r'느끼시나요|드시나요|하시나요|스트레스|담배|(?<!수)술')


def relevant_question(q: str, cat_systems, peds: bool = False) -> tuple[bool, str]:
    """LLM 자유 질문의 범주 관련성(v8c 결함 #5). 수치·기준값 질문, 범주 계통 밖 질문, 소아에 성인 말투를 거른다."""
    t = nfc(q or '').strip()
    if NUM_RE.search(t):
        return False, 'numeric'
    if peds and ADULT_PHRASE_RE.search(t):
        return False, 'adult_phrasing'
    if cat_systems is not None:
        extra = set(systems_of(t)) - set(cat_systems) - {'hx', 'meds'}
        if extra:
            return False, 'off_system:' + ','.join(sorted(extra))
    return True, 'ok'


def category_systems(built: dict, prof: dict | None = None) -> set:
    """주 범주 은행 단위의 계통 집합(항목별 isys 포함). 은행 밖 범주는 범주 문항·주호소 문구의 계통으로 추정."""
    out = set()
    spec = CPX.get(built.get('main')) if built.get('main') else None
    if spec:
        for u in spec['units'] + list(spec.get('add_common') or []):
            out.add(u['sys'])
            out.update(u.get('isys') or [])
    else:
        for u in built.get('units') or []:
            if u.get('sys') == 'legacy':
                out.update(systems_of(u['q']))
        out.update(systems_of(' '.join(str((prof or {}).get(k) or '') for k in ('cc', 'chief_complaint'))))
        out.add('gen')
    return out


# ---------------------------------------------------------------- 항목별 응답 판정 (§6.3 확장: 3항목)
GENERIC_ALL = re.compile(r'(둘\s*다|모두|셋\s*다|다\s*없|아무것도|아무\s*문제|그런\s*(증상|병|질환|적|건|거|것|변화|문제|가족|얘기|말|분|일)|'
                         r'전혀\s*없|별\s*문제\s*없|특별한\s*문제\s*없|또래(만큼|와|랑|처럼|보다))')
EXPERIENCE_NEG = re.compile(r'^\s*(아니(요|오)?|아뇨)[,.\s]*([가-힣]+\s*)?(적|일)\s*(은|이|도)?\s*없')
BARE_NEG = re.compile(r'\s*((아니(요|오)?|아뇨|네|예)[.,!\s]*)?(없어요|없습니다|없었어요|안\s*해요|않아요|전혀\s*없어요|전혀요)'
                      r'[.!\s]*')
NEG_TOK = re.compile(r'(없|않|안\s*[가-힣]|안[가-힣]{0,2}요|아니|전혀|별로|못\s*느|평소\s*(같|와|처럼)|그대로|변화\s*없|괜찮)')
UNSURE_RE = re.compile(r'(잘\s*모르|모르겠|기억이\s*안|글쎄)')
SPLIT_RE = re.compile(r'[,.;]|(?<=고)\s|(?<=만)\s|(?<=데)\s|(?<=지만)\s|(?<=는데)\s')


def _segments(reply: str) -> list[str]:
    return [s.strip() for s in SPLIT_RE.split(nfc(reply or '')) if s and s.strip()]


PRED_END_RE = re.compile(r'(요|다|고|데|만|서|면|죠|네|음|함|[?!])\s*$')


def _item_pol(reply: str, kw: str, default_neg: bool) -> str:
    segs = _segments(reply)
    for k, seg in enumerate(segs):
        if re.search(kw, seg):
            if NEG_TOK.search(seg):
                return '-'
            # "천식이나 장, 콩팥 질환은 없어요": 술어 없는 이름 나열 조각은 뒤 절의 극성을 따른다
            j = k
            while j + 1 < len(segs) and not PRED_END_RE.search(segs[j]):
                j += 1
                if NEG_TOK.search(segs[j]):
                    return '-'
            return '+'
    return '-' if default_neg else '+'


def judge(items, reply: str) -> list[dict]:
    """items: [(id, label, kw)]. 반환: 항목마다 {'id','label','answered','pol'('+','-','?')}.
    부분 응답을 '모두 답함'으로 오판하지 않는 쪽으로 보수적으로 판정한다(정보 손실은 허용, 거짓 음성 기록은 금지)."""
    r = nfc(reply or '').strip()
    out = [{'id': i[0], 'label': i[1], 'answered': False, 'pol': '?', 'kw': i[2]} for i in items]
    if not r or re.search(r'한\s*번에\s*하나씩', r):
        return out
    starts_neg = bool(re.match(r'\s*(아니(요|오)?|아뇨|없|전혀)', r))
    if len(items) == 1:
        o = out[0]
        o['answered'] = True
        if UNSURE_RE.search(r):
            o['pol'] = '?'
        elif starts_neg or re.search(r'(없어요|없습니다|없었어요|않아요|않았어요|안\s*(해|마셔|피워|먹어)요|적\s*없)[.!]?\s*$', r):
            o['pol'] = '-'
        elif re.match(r'\s*(네|예|있|응)', r) or re.search(r'(있어요|있었어요)[.!]?\s*$', r):
            o['pol'] = '+'
        else:
            o['pol'] = '?'   # 서술·정보형
        return out
    hits = [bool(items[k][2] != '.' and re.search(items[k][2], r)) for k in range(len(items))]
    generic = bool(GENERIC_ALL.search(r))
    all_word = bool(re.search(r'(둘\s*다|셋\s*다|모두|아무것도)', r))
    if any(hits):
        if all(hits) or all_word:
            for k, o in enumerate(out):
                o['answered'] = True
                o['pol'] = _item_pol(r, items[k][2], starts_neg or (all_word and not hits[k]))
                if all_word and not hits[k]:
                    o['pol'] = '-' if NEG_TOK.search(r) else '+'
            return out
        for k, o in enumerate(out):
            if hits[k]:
                o['answered'] = True
                o['pol'] = _item_pol(r, items[k][2], starts_neg)
        # "우울하진 않고 그런 생각은 없어요": 항목 단어가 없는 다른 절의 지시어 음성은 남은 항목 하나에만 붙인다
        rest = [o for o in out if not o['answered']]
        if len(rest) == 1:
            for seg in _segments(r):
                if any(items[k][2] != '.' and re.search(items[k][2], seg) for k in range(len(items))):
                    continue
                if re.search(r'그런\s*(생각|적|건|거|것|증상|일|변화)\S*\s*(은|는|도)?\s*없', seg):
                    rest[0]['answered'] = True
                    rest[0]['pol'] = '-'
                    break
        return out
    # 항목 단어가 하나도 없는 답
    if generic or EXPERIENCE_NEG.search(r) or BARE_NEG.fullmatch(r):
        neg = bool(NEG_TOK.search(r)) or starts_neg
        for o in out:
            o['answered'] = True
            o['pol'] = '-' if neg else '?'
        if not neg:   # "네, 그래요" 같은 포괄 긍정은 첫 항목만 인정
            for o in out[1:]:
                o['answered'] = False
        return out
    # 모호: 부분 응답 27/29가 첫 항목 → 첫 항목만 인정
    out[0]['answered'] = True
    if UNSURE_RE.search(r) or re.search(r'(말고|말곤|빼고|외에|외엔|밖에)', r):
        out[0]['pol'] = '?'   # "아빠 말고는 없어요" 같은 예외 답은 극성을 정하지 않는다(서술로 기록)
    else:
        out[0]['pol'] = '-' if (starts_neg or NEG_TOK.search(r)) else '+'
    return out


# 단독 재질문·부분 덮임 때 쓰는 항목별 단일 질문(긍정형: 답의 극성이 분명하도록)
ITEM_Q = {
    'ros_cp': '가슴 통증이 있으세요?', 'ros_dysp': '숨찬 증상이 있으세요?', 'pmh_asthma': '천식이 있으세요?',
    'pmh_heart': '심장병이 있으세요?', 'pmh_thyroid': '갑상선 질환을 앓은 적 있나요?', 'pmh_dm': '당뇨가 있으세요?',
    'pmh_htn': '고혈압이 있으세요?', 'pmh_allergy': '약 알레르기가 있으세요?', 'pmh_supp': '영양제나 한약도 드세요?',
    'pmh_op': '수술받은 적 있으세요?', 'pmh_kidney': '콩팥병이 있으세요?',
    'sb_seizure': '약을 끊었을 때 경련한 적 있나요?', 'sb_delirium': '끊었을 때 헛것이 보인 적 있나요?',
    'ps_si': '혹시 죽고 싶은 생각이 드신 적 있나요?', 'ps_mood': '요즘 기분이 많이 가라앉나요?',
    'ros_hematochezia': '변에 피가 섞인 적 있나요?', 'ros_melena': '변이 까맣게 나온 적 있나요?', 'ros_vomit': '토한 적 있나요?',
    'ros_fever': '열이 난 적 있나요?', 'ros_chill': '오한이 있으세요?', 'ha_neck': '목이 뻣뻣하세요?', 'ha_speech': '말이 어눌해졌나요?',
    'dz_diplopia': '물체가 둘로 보이나요?', 'dz_speech': '말이 어눌해졌나요?', 'dz_numb': '팔다리가 저리세요?',
    'dz_loc': '정신을 잃은 적 있나요?', 'gr_vision': '눈이 잘 안 보인다고 하나요?', 'cp_sweat': '식은땀이 나세요?',
    'ed_chest': '가슴이 답답하세요?', 'ed_calf_red': '다리가 붉어졌나요?', 'gi_odynophagia': '삼킬 때 아프세요?',
    'wl_sweat': '땀이 많아지셨나요?', 'wl_urine': '소변량이 늘었나요?', 'wl_neck_mass': '목에 혹이 만져지나요?',
    'wl_eye_dry': '눈이 뻑뻑하세요?', 'wm_duration': '생리 기간이나 주기가 변했나요?', 'pa_syncope': '쓰러질 것 같은 적 있나요?',
    'pmh_admit': '입원한 적 있으세요?', 'dz_face': '얼굴 한쪽이 처졌나요?', 'ros_abd': '배가 아프세요?',
    'ft_cold': '추위를 많이 타세요?', 'gr_fatigue': '쉽게 지치나요?',
}


# 묻지 않았는데 답(또는 시작 정보)에 양성으로 나오면 덮인 것으로 보는 항목(구체 표현만; 한 글자 키워드는 오탐이 많아 쓰지 않음)
MENTION = {
    'ros_palp': r'두근', 'wl_tremor': r'손.{0,4}떨|떨려|떨림', 'wl_sweat': r'땀이?\s*(많|나)|잠옷.{0,4}젖', 'wl_heat': r'더위',
    'wl_intake': r'(많이|더)\s*먹|입맛|식욕', 'in_sleepy': r'졸려|졸리|졸음', 'in_foggy': r'멍해|멍하',
    'ros_dysp': r'숨이?\s*차|숨차', 'ps_sleep': r'잠을?\s*(못|설)|불면', 'ps_anx': r'불안|초조', 'sb_tolerance': r'늘었|늘려|서너',
    'sb_sources': r'(여러|두|세)\s*(곳|군데|병원)', 'ros_fatigue': r'피곤|지치|피로', 'ft_weight': r'(살|체중|몸무게).{0,6}(빠|줄|늘|쪘)',
    'wl_eye_prop': r'눈이?\s*튀어', 'wl_neck_swell': r'목.{0,4}(붓|부었|두꺼)', 'ros_diarrhea': r'설사', 'ros_constip': r'변비',
}


def positive_mentions(items, reply: str) -> list[str]:
    """묻지 않은 항목이 답에 양성으로 언급됐는지(덮임 판정용). MENTION에 있는 항목만, 부정 문맥이면 제외."""
    out = []
    for iid, _lab, _kw in items:
        pat = MENTION.get(iid)
        if not pat or iid in out:
            continue
        for seg in _segments(reply):
            if re.search(pat, seg) and not NEG_TOK.search(seg):
                out.append(iid)
                break
    return out


# ---------------------------------------------------------------- 범주 체크리스트 구성
def onset_known(opening: str) -> bool:
    return bool(re.search(r'(\d+|[한두세네석넉]|[일이삼사오육칠팔구십]+|여러|몇)\s*(년|해|달|개월|주|일)\s*(전|째|동안|사이|간)|'
                          r'(어제|그제|오늘|지난\s*(주|달)|작년|올해)', opening or ''))


def _clone(u, **kw):
    v = dict(u)
    v['items'] = list(u['items'])
    v.update(kw)
    return v


# 필수 공통 병력 슬롯(v8c 결함 #6). 가족력·복용약은 범주 대체 단위(예: 가족 중 갑상선병)를 인정,
# 나머지(입원·수술, 알레르기·천식, 술·담배)는 대체 단위가 같은 항목을 덮을 때만 대체.
MUST_COMMON = {'hx_admit_op', 'hx_allergy', 'hx_meds', 'fh_open', 'sh_smoke_alc', 'p_admit_op', 'p_allergy', 'p_fh'}
MUST_ANY_REPLACEMENT = {'hx_meds', 'fh_open', 'p_fh'}


def _covers(new_u, old_u) -> bool:
    return {i[0] for i in old_u['items']} <= {i[0] for i in new_u['items']}


def legacy_units(cat: str) -> list[dict]:
    """은행에 없는 범주: bank2.CATEGORY_Q 문항을 단일 단위로(LLM 폴백과 합침)."""
    from . import bank2
    out = []
    for slot, label, q, prio in bank2.CATEGORY_Q.get(cat, []):
        if len(nfc(q)) > MAX_Q:
            continue
        words = [w for w in re.findall(r'[가-힣]{2,}', label) if w not in ('여부', '양상', '세부')]
        kw = '|'.join(w[:2] for w in words) or '.'
        stage = 'red' if re.search(r'(출혈|실신|경련|신경|의식|흉통|호흡곤란|발열)', label) else 'core'
        out.append(U(slot, stage, min(prio, 2), q, [(slot, label, kw)], 'legacy'))
    return out


def build(prof: dict, opening: str) -> dict:
    """프로필 → {'units': [...], 'exams': [...], 'cats': [...], 'bank': bool}. 순서는 compile에서 정한다."""
    cats = list(prof.get('categories') or [])
    peds = bool(prof.get('pediatric'))
    sex, age = prof.get('sex'), prof.get('age')
    main = next((c for c in cats if c in CPX), None)
    if 'substance' in cats and (prof.get('request') or 'insomnia' in cats):
        main = 'substance'
    spec = CPX.get(main) if main else None
    units = []
    if spec:
        units += [_clone(u) for u in spec['units']]
    else:
        for c in cats[:1]:
            units += legacy_units(c)
    # 부 범주: 핵심(prio 1) 단위 최대 2개만 prio 2로
    for c in cats:
        if c == main or c not in CPX:
            continue
        if (main == 'substance' and c == 'insomnia') or (CPX.get(c, {}).get('peds') and not peds):
            continue
        extra = [u for u in CPX[c]['units'] if u['prio'] == 1 and u['stage'] in ('core', 'red')][:2]
        units += [_clone(u, prio=2) for u in extra]
    have_ids = {u['id'] for u in units}
    common = list(PEDS_COMMON if peds else ADULT_COMMON)
    common += list((spec or {}).get('add_common') or [])
    repl = dict((spec or {}).get('replace') or {})
    registry = {u['id']: u for u in [SH_ALC_SMOKE, SH_SMOKE_ALC, SH_STRESS, WM_LMP] + common}
    cat_by_id = {u['id']: u for u in units}
    own_asthma = any(i[0] == 'pmh_asthma' for u in units for i in u['items'])
    must_ids = set()
    for u in common:
        if u['id'] in have_ids:
            continue
        new = repl.get(u['id'])
        if new and u['id'] in MUST_COMMON:
            nu = cat_by_id.get(new) or registry.get(new)
            if nu is not None and (u['id'] in MUST_ANY_REPLACEMENT or _covers(nu, u)):
                must_ids.add(new)      # 필수 슬롯을 같은 항목을 덮는 범주 단위로 대체
            else:
                repl.pop(u['id'])      # 대체 단위가 필수 항목을 덮지 못하면 공통 단위를 그대로 둔다
                new = None
        if new:
            continue
        if u['id'] == 'hx_allergy' and own_asthma:
            u = HX_ALLERGY_ONLY        # 범주에 천식 항목이 이미 있으면 알레르기만
        units.append(_clone(u))
        have_ids.add(u['id'])
        if u['id'] in MUST_COMMON:
            must_ids.add(u['id'])
    for old, new in repl.items():  # 대체 단위가 범주 목록에 없으면 공통 등록부에서 가져온다(예: 술이나 담배)
        if new not in have_ids and new in registry:
            units.append(_clone(registry[new], prio=min(registry[new]['prio'],
                                                         next((u['prio'] for u in common if u['id'] == old), 9))))
            have_ids.add(new)
    for uid, p in ((spec or {}).get('promote') or {}).items():
        for u in units:
            if u['id'] == uid:
                u['prio'] = min(u['prio'], p)
    for u in units:
        if u['id'] in must_ids:
            u['must'] = True
            u['prio'] = 1
    for uid, p in ((spec or {}).get('demote') or {}).items():
        for u in units:
            if u['id'] == uid and not u.get('must'):   # 필수 공통 병력은 강등 면역
                u['prio'] = p
    female_fertile = (sex == 'F') and not peds and (age is None or 12 <= age <= 55)
    women_only = {'wl_cycle', 'ft_menor', 'ap_lmp'} | set((spec or {}).get('women_only') or [])
    units = [u for u in units if u['id'] not in women_only or female_fertile]
    if female_fertile:
        if not any(u['id'] == 'wl_cycle' for u in units):
            units.append(_clone(WM_CYCLE))
        units.append(_clone(WM_PREG, must=True, prio=1))
    # 정신 선별(기분)은 정신·수면 범주가 아니면 감별(prio 2)로
    if not peds and not any(u['sys'] == 'psy' and u['stage'] == 'red' for u in units):
        units.append(_clone(PS_MOOD))
    # 발병 시점
    if not onset_known(opening):
        q = (spec or {}).get('onset_q') or ONSET['q']
        units.insert(0, _clone(ONSET, q=q))
    units.append(_clone(P_ICE if peds else (ICE_DISEASE if re.search(r'걱정', opening or '') else ICE_OPEN), must=True))
    if peds:
        title = prof.get('informant') or '보호자분'
        for u in units:
            if u['id'] == 'ice':
                u['q'] = u['q'].replace('어머님', title)
            if age is not None and age >= 7 and u['id'] == 'p_daycare':
                u['q'] = u['q'].replace('어린이집', '학교')
    exams = list((spec or {}).get('exams') or [])
    if not exams:
        from . import bank2
        exams = [e for c in cats[:1] for e in bank2.CATEGORY_EXAMS.get(c, [])][:FALLBACK_EXAMS_N]
    return {'units': units, 'exams': exams, 'main': main, 'bank': bool(spec)}


def is_must(u) -> bool:
    return bool(u.get('must')) or u['stage'] == 'ice'


def chosen_rank(u) -> float:
    """묻는 순서: stage 순. 단, 증상(core·red) 단계의 감별·배경(prio ≥ 2) 단위는 핵심 증상 뒤·병력 앞에 둔다
    — 남는 자리가 부족하면 이 단위가 먼저 양보하고 안전 재질문·후속이 자리를 쓴다."""
    r = STAGE_RANK.get(u['stage'], 9)
    if u['stage'] in ('core', 'red') and u['prio'] >= 2 and not is_must(u):
        return STAGE_RANK['red'] + 0.5
    return r


def compile_units(units: list[dict], budget: int, covered=()) -> tuple[list[dict], list[dict]]:
    """예산 안에서 고를 단위 + 남는 대기열. 필수 공통 병력(must)·ICE를 먼저 넣고(교체 대상 아님),
    그다음 prio 1(안전 우선) → 2 → 3. covered: 이미 덮인 항목 id(시작 정보·개방형 답) — 모두 덮인 단위는 예산을 쓰지 않는다.
    선택된 단위는 stage 순서(핵심 양성 → 경고 음성 → 병력 → 가족력 → 사회력 → 임신 → 걱정)로 정렬."""
    covered = set(covered or ())

    def done(u):
        return all(i[0] in covered for i in u['items'])

    def protected(u):
        return is_must(u) or (u['safety'] and u['prio'] == 1)

    def key(u):
        return (0 if u['prio'] == 1 else 1, u['prio'], 0 if u['safety'] else 1, STAGE_RANK.get(u['stage'], 9))
    avail = [u for u in units if not done(u)]
    musts = sorted([u for u in avail if is_must(u)], key=key)
    ranked = sorted([u for u in avail if not is_must(u)], key=key)
    chosen = musts[:budget]
    room = max(0, budget - len(chosen))
    chosen, backlog = chosen + ranked[:room], musts[budget:] + ranked[room:] + [u for u in units if done(u)]
    # 핵심 안전(prio 1)이 예산 밖으로 밀렸으면 보호 대상이 아닌 단위와 교체(필수 단위는 교체 대상 아님)
    for u in list(backlog):
        if not protected(u) or is_must(u):
            continue
        victim = next((c for c in reversed(chosen) if not protected(c)), None)
        if victim is None:
            break
        chosen.remove(victim)
        backlog.insert(0, victim)
        backlog.remove(u)
        chosen.append(u)
    order = {id(u): i for i, u in enumerate(units)}
    chosen.sort(key=lambda u: (chosen_rank(u), order[id(u)]))
    backlog.sort(key=lambda u: (u['prio'], STAGE_RANK.get(u['stage'], 9), order[id(u)]))
    return chosen, backlog


def all_bank_units() -> list[dict]:
    out = []
    for spec in CPX.values():
        out += spec['units'] + list(spec.get('add_common') or [])
    out += ADULT_COMMON + PEDS_COMMON + [WM_PREG, WM_CYCLE, WM_LMP, PS_MOOD, PS_MOOD_SI, ICE_DISEASE, ICE_OPEN, ONSET,
                                          SH_ALC_SMOKE, SH_STRESS, P_BIRTH, P_DIET, P_SLEEP, P_ICE, HX_ALLERGY_ONLY]
    return out


def bank_questions() -> set:
    return {nfc(u['q']) for u in all_bank_units()}


# 진찰 표준 문구 → 체크리스트 항목(기록 키) 대응은 기존 banks.EXAM_BANK 사용.
ITEM_KEYS = {
    'pmh_htn': 'pmh.HTN', 'pmh_dm': 'pmh.DM', 'pmh_op': 'pmh.op_hx', 'pmh_allergy': 'pmh.allergy',
    'pmh_heart': 'pmh.heart_disease', 'pmh_lipid': 'pmh.dyslipidemia', 'pmh_tbc': 'pmh.Tbc', 'pmh_hep': 'pmh.hepatitis',
    'sh_smoke': 'sh.smoking', 'sh_alcohol': 'sh.alcohol', 'ros_cp': 'ros.Chest pain', 'ros_palp': 'ros.Palpitation',
    'ros_fever': 'ros.Fever', 'ros_chill': 'ros.Chill', 'ros_cough': 'ros.Cough', 'ros_sputum': 'ros.Sputum',
    'ros_rhinorrhea': 'ros.Rhinorrhea', 'ros_abd': 'ros.Abdominal pain', 'ros_nausea': 'ros.Nausea',
    'ros_vomit': 'ros.Vomiting', 'ros_melena': 'ros.Melena', 'ros_hematochezia': 'ros.Hematochezia',
    'ros_diarrhea': 'ros.Diarrhea', 'ros_constip': 'ros.Constipation', 'ros_headache': 'ros.Headache',
    'ros_dizzy': 'ros.Dizziness', 'ros_fatigue': 'ros.Fatigue', 'ros_anorexia': 'ros.Anorexia',
}

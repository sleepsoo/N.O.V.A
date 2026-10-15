"""DDXPlus 질환→증거 구조를 한국어 CPX 질문 KB로 압축한다(오프라인 빌드, 제출 zip 제외).

입력(CC BY 4.0): DDXPlus release_conditions.json / release_evidences.json (환자 zip 파일은 사용하지 않음).
출력: agent/data/ddx_kb.json

한국어 질문·라벨·질환명은 우리가 직접 작성한 번역·각색이며, DDXPlus에서는 질환–증거 연결 구조만 가져온다.

실행: python tools/build_ddx_kb.py [DDXPlus 디렉터리]
"""
from __future__ import annotations

import json
import os
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_SRC = os.path.join(os.path.dirname(ROOT), '공개 벤치마크', 'DDXPlus')
OUT = os.path.join(ROOT, 'agent', 'data', 'ddx_kb.json')

SYSTEMS = {'gen', 'cv', 'resp', 'gi', 'gu', 'neuro', 'eye', 'neck', 'psy', 'sleep', 'drug', 'wm', 'hx', 'meds', 'fh',
           'sh', 'endo', 'ent', 'msk', 'skin'}

# 예/아니오 질문으로 의미가 없거나 다른 증거와 중복되는 범주형 증거(건너뜀)
SKIPPED = {
    'E_17': '아시아계 혈통 여부 — 한국 환자에게 무의미',
    'E_58': '통증 위치의 정밀도(0-10) — E_55 부위 질문과 중복',
    'E_130': '발진 색(범주형) — 신체 진찰 소견',
    'E_131': '병변 탈락 여부(범주형) — 신체 진찰 소견',
    'E_132': '발진 부기 정도(0-10) — 신체 진찰 소견',
    'E_134': '발진 통증 강도(0-10) — E_56과 중복',
    'E_135': '병변 크기 1cm 초과(범주형) — 신체 진찰 소견',
    'E_183': '농촌 거주 — 감별력 낮음',
    'E_195': '교외 거주 — 감별력 낮음',
    'E_207': '대도시 거주 — 감별력 낮음',
}

# 여성 전용(남성에게 묻지 않음), 성인 전용 노출(소아에게 묻지 않음)
FEMALE_ONLY = {'E_11', 'E_141', 'E_145', 'E_163', 'E_167'}
ADULT_ONLY = {'E_27', 'E_35', 'E_60', 'E_61', 'E_62', 'E_78', 'E_79', 'E_115', 'E_189', 'E_191', 'E_198', 'E_199',
              'E_200'}

# code: (질문 ≤30자, 라벨 ≤12자, 계통, 경고증상)
EVID = {
    'E_0': ('최근에 바이러스 감염을 앓으셨어요?', '최근 바이러스감염', 'gen', False),
    'E_1': ('최근 중이염으로 항생제를 드셨어요?', '중이염 항생제', 'meds', False),
    'E_2': ('HIV 감염 진단을 받으신 적 있나요?', 'HIV 감염', 'hx', False),
    'E_3': ('심낭염을 앓으신 적 있나요?', '심낭염 병력', 'hx', False),
    'E_4': ('본인이나 가족이 크룹을 앓은 적 있나요?', '크룹 병력', 'hx', False),
    'E_5': ('폐에 물이 찬 적이 있나요?', '폐부종 병력', 'hx', False),
    'E_6': ('만성 췌장염이 있으세요?', '만성 췌장염', 'hx', False),
    'E_7': ('식사를 잘 못 챙겨 드시나요?', '불량한 식습관', 'sh', False),
    'E_8': ('현재 투석을 받고 계세요?', '투석', 'hx', False),
    'E_9': ('림프샘이 붓거나 아프신가요?', '림프절 비대', 'gen', False),
    'E_10': ('최근 소염진통제를 드셨어요?', '소염진통제 복용', 'meds', False),
    'E_11': ('아이에게 9개월 넘게 모유 수유하셨어요?', '장기 모유수유', 'wm', False),
    'E_12': ('심한 음식 알레르기가 있으세요?', '음식 알레르기', 'hx', False),
    'E_13': ('최근 2주간 증상이 점점 쉽게 생기나요?', '악화되는 흉통', 'cv', True),
    'E_14': ('가만히 쉴 때도 가슴이 아프세요?', '안정 시 흉통', 'cv', True),
    'E_15': ('최근 일주일 내 항정신병약을 드셨어요?', '항정신병약 복용', 'meds', False),
    'E_16': ('불안감을 느끼세요?', '불안감', 'psy', False),
    'E_18': ('낭포성 섬유증이 있으세요?', '낭포성 섬유증', 'hx', False),
    'E_19': ('갑상샘 기능항진증 진단을 받으셨어요?', '갑상샘항진증', 'hx', False),
    'E_20': ('류마티스 관절염이 있으세요?', '류마티스관절염', 'hx', False),
    'E_21': ('전에 기흉을 앓으신 적 있나요?', '기흉 병력', 'hx', False),
    'E_22': ('심장 판막 질환이 있으세요?', '판막 질환', 'hx', False),
    'E_23': ('자는 동안 숨을 멈춘다는 말을 들으세요?', '수면 중 무호흡', 'sleep', False),
    'E_24': ('빈혈 진단을 받으신 적 있나요?', '빈혈 병력', 'hx', False),
    'E_25': ('가족 중에 군발두통 있는 분이 계세요?', '군발두통 가족력', 'fh', False),
    'E_26': ('가족 중에 빈혈 있는 분이 계세요?', '빈혈 가족력', 'fh', False),
    'E_27': ('성병을 앓으신 적 있나요?', '성병 병력', 'hx', False),
    'E_28': ('가족 중에 근무력증 있는 분이 계세요?', '근무력증 가족력', 'fh', False),
    'E_29': ('가족 중에 정신질환 있는 분이 계세요?', '정신질환 가족력', 'fh', False),
    'E_30': ('배가 더부룩하거나 부풀어 오르나요?', '복부 팽만', 'gi', False),
    'E_31': ('중증 COPD가 있으세요?', '중증 COPD', 'hx', False),
    'E_32': ('식욕이 줄었나요?', '식욕 저하', 'gen', False),
    'E_33': ('몸을 앞으로 숙이면 통증이 줄어드나요?', '앞숙임 시 호전', 'cv', False),
    'E_34': ('현재 치료 중인 암이 있으세요?', '활동성 암', 'hx', False),
    'E_35': ('커피나 차를 자주 드시나요?', '커피·차', 'sh', False),
    'E_37': ('암이 다른 곳으로 전이되었나요?', '전이암', 'hx', False),
    'E_38': ('턱이 아프거나 힘이 빠지나요?', '턱 통증', 'cv', False),
    'E_39': ('최근 정신이 혼미하거나 헷갈리세요?', '혼동', 'neuro', True),
    'E_40': ('백일해 환자와 접촉하신 적 있나요?', '백일해 접촉', 'sh', False),
    'E_41': ('2주 내 비슷한 증상의 사람과 접촉했나요?', '유증상자 접촉', 'sh', False),
    'E_42': ('알레르기 있는 음식이나 물질에 노출됐나요?', '알레르겐 노출', 'gen', False),
    'E_43': ('경련하며 의식을 잃은 적 있나요?', '경련', 'neuro', True),
    'E_44': ('스테로이드 약을 드시나요?', '스테로이드 복용', 'meds', False),
    'E_45': ('기침할 때 피가 나오나요?', '객혈', 'resp', True),
    'E_46': ('지난 1년간 천식 발작이 2번 이상 있었나요?', '잦은 천식발작', 'hx', False),
    'E_47': ('크론병이나 궤양성 대장염이 있으세요?', '염증성 장질환', 'hx', False),
    'E_48': ('4명 이상과 함께 사시나요?', '다인 가구', 'sh', False),
    'E_49': ('어린이집에 다니거나 근무하시나요?', '어린이집', 'sh', False),
    'E_50': ('땀이 평소보다 많이 나나요?', '발한', 'gen', False),
    'E_51': ('설사를 하시나요?', '설사', 'gi', False),
    'E_52': ('물체가 두 개로 겹쳐 보이나요?', '복시', 'eye', True),
    'E_53': ('아픈 곳이 있으세요?', '통증 유무', 'gen', False),
    'E_54': ('어떤 식으로 아프세요?', '통증 양상', 'gen', False),
    'E_55': ('어디가 아프세요?', '통증 부위', 'gen', False),
    'E_56': ('통증은 얼마나 심하세요?', '통증 강도', 'gen', False),
    'E_57': ('통증이 다른 곳으로 뻗치나요?', '방사통', 'gen', False),
    'E_59': ('통증이 갑자기 생겼나요?', '급성 발생', 'gen', False),
    'E_60': ('에너지 음료를 자주 드시나요?', '에너지음료', 'sh', False),
    'E_61': ('현재 주사로 마약을 하시나요?', '정맥 약물 사용', 'sh', False),
    'E_62': ('각성제를 자주 드시나요?', '각성제 사용', 'sh', False),
    'E_63': ('말할 때 발음이 어눌해졌나요?', '구음장애', 'neuro', True),
    'E_64': ('조금만 움직여도 숨이 차세요?', '운동 시 호흡곤란', 'resp', False),
    'E_65': ('삼키기 힘들거나 걸리는 느낌이 있나요?', '삼킴곤란', 'ent', False),
    'E_66': ('숨이 많이 차세요?', '호흡곤란', 'resp', True),
    'E_67': ('자다가 숨이 차서 깬 적 있나요?', '야간 호흡곤란', 'resp', False),
    'E_69': ('당뇨가 있으세요?', '당뇨', 'hx', False),
    'E_70': ('체중이 많이 나가시는 편인가요?', '비만', 'hx', False),
    'E_71': ('고지혈증이 있으세요?', '고지혈증', 'hx', False),
    'E_72': ('지난 1년간 COPD 악화가 있었나요?', 'COPD 악화력', 'hx', False),
    'E_73': ('최근 한 달 내 에볼라 환자와 접촉했나요?', '에볼라 접촉', 'sh', True),
    'E_74': ('눈이 전체적으로 빨개졌나요?', '결막 충혈', 'eye', False),
    'E_75': ('숨이 막히는 느낌이 드세요?', '질식감', 'resp', True),
    'E_76': ('살짝 어지러우세요?', '가벼운 어지럼', 'neuro', False),
    'E_77': ('색깔 있는 가래가 많이 나오나요?', '화농성 가래', 'resp', False),
    'E_78': ('술을 많이 드시는 편인가요?', '과음', 'sh', False),
    'E_79': ('담배를 피우세요?', '흡연', 'sh', False),
    'E_80': ('우울증 진단을 받은 적 있나요?', '우울증 병력', 'hx', False),
    'E_81': ('평소 불안이 심한 편이세요?', '만성 불안', 'psy', False),
    'E_82': ('쓰러질 것처럼 어지러우세요?', '실신감', 'neuro', True),
    'E_83': ('얼굴이나 눈 근육에 힘이 빠지나요?', '안면근력 저하', 'neuro', False),
    'E_84': ('양팔이나 양다리에 힘이 빠지나요?', '사지 근력저하', 'neuro', True),
    'E_86': ('가족 중에 알레르기 있는 분이 계세요?', '알레르기 가족력', 'fh', False),
    'E_87': ('가족 중에 천식 있는 분이 계세요?', '천식 가족력', 'fh', False),
    'E_88': ('피곤해서 일상생활이 힘드세요?', '심한 피로', 'gen', False),
    'E_89': ('늘 피곤하고 자도 개운하지 않으세요?', '만성 피로', 'gen', False),
    'E_90': ('피곤하면 근력이 더 떨어지나요?', '피로 시 근력악화', 'neuro', False),
    'E_91': ('열이 나세요?', '발열', 'gen', False),
    'E_92': ('갑자기 볼이 빨개졌나요?', '안면 홍조', 'skin', False),
    'E_93': ('발이 저리거나 감각이 둔하세요?', '발 저림', 'neuro', False),
    'E_94': ('오한이 있으세요?', '오한', 'gen', False),
    'E_95': ('파킨슨병이 있으세요?', '파킨슨병', 'hx', False),
    'E_96': ('최근 체중이 늘었나요?', '체중 증가', 'gen', False),
    'E_97': ('목구멍이 아프세요?', '인후통', 'ent', False),
    'E_98': ('열공 탈장 진단을 받으셨어요?', '열공탈장', 'hx', False),
    'E_99': ('본인이나 가족이 편두통이 있나요?', '편두통 병력', 'hx', False),
    'E_100': ('호르몬제를 드시나요?', '호르몬제', 'meds', False),
    'E_101': ('지난 1년간 천식으로 입원하셨어요?', '천식 입원력', 'hx', False),
    'E_102': ('혈압이 높아서 오셨어요?', '고혈압 내원', 'hx', False),
    'E_103': ('냄새를 잘 못 맡으세요?', '후각 저하', 'ent', False),
    'E_104': ('고혈압이 있으세요?', '고혈압', 'hx', False),
    'E_105': ('심근경색이나 협심증을 앓으셨어요?', '관상동맥질환', 'hx', False),
    'E_106': ('심부전이 있으세요?', '심부전', 'hx', False),
    'E_107': ('뇌졸중을 앓으신 적 있나요?', '뇌졸중 병력', 'hx', False),
    'E_108': ('혈액순환 문제가 있으세요?', '말초순환장애', 'hx', False),
    'E_109': ('다리 혈전증을 앓으신 적 있나요?', '심부정맥혈전증', 'hx', False),
    'E_110': ('최근 한 달 사이 3일 넘게 누워 지내셨나요?', '장기 부동', 'hx', False),
    'E_111': ('죽을 것 같은 공포를 느끼셨어요?', '죽음의 공포', 'psy', False),
    'E_112': ('기침 후 숨소리가 거칠어지나요?', '흡기 천명음', 'resp', False),
    'E_113': ('만성 신부전이 있으세요?', '만성 신부전', 'hx', False),
    'E_114': ('요즘 짜증이 늘고 기분 변화가 심하세요?', '과민·기분변동', 'psy', False),
    'E_115': ('최근 6개월 여러 명과 콘돔 없이 관계했나요?', '위험 성관계', 'sh', False),
    'E_116': ('최근 2주 안에 감기를 앓으셨어요?', '최근 감기', 'hx', False),
    'E_118': ('폐렴을 앓으신 적 있나요?', '폐렴 병력', 'hx', False),
    'E_119': ('만성 부비동염 진단을 받으셨어요?', '만성 부비동염', 'hx', False),
    'E_120': ('코에 물혹이 있으세요?', '비용종', 'hx', False),
    'E_121': ('코뼈가 휘었다는 말을 들으셨어요?', '비중격만곡', 'hx', False),
    'E_123': ('COPD가 있으세요?', 'COPD', 'hx', False),
    'E_124': ('천식이 있거나 흡입기를 쓰신 적 있나요?', '천식 병력', 'hx', False),
    'E_125': ('역류성 식도염 진단을 받으셨어요?', '역류질환 병력', 'hx', False),
    'E_126': ('간경화가 있으세요?', '간경화', 'hx', False),
    'E_127': ('눈물이 많이 나세요?', '눈물 과다', 'eye', False),
    'E_128': ('잠깐 숨도 말도 막힌 적이 있나요?', '일시적 질식', 'resp', True),
    'E_129': ('피부에 발진이나 이상이 생겼나요?', '피부 병변', 'skin', False),
    'E_133': ('발진은 어디에 생겼나요?', '발진 부위', 'skin', False),
    'E_136': ('피부가 가려우세요?', '가려움', 'skin', False),
    'E_137': ('림프절 제거 수술을 받으셨어요?', '림프절 절제술', 'hx', False),
    'E_138': ('섬유근육통이 있으세요?', '섬유근육통', 'hx', False),
    'E_139': ('선천성 심장 질환이 있으세요?', '선천성 심질환', 'hx', False),
    'E_140': ('최근 검은 변을 보셨어요?', '흑색변', 'gi', True),
    'E_141': ('첫 생리를 12살 전에 하셨어요?', '이른 초경', 'wm', False),
    'E_142': ('어머니가 천식이 있으세요?', '모친 천식', 'fh', False),
    'E_143': ('일주일에 4번 이상 운동하세요?', '규칙적 운동', 'sh', False),
    'E_144': ('온몸 근육이 아프세요?', '전신 근육통', 'msk', False),
    'E_145': ('생리량이 많거나 오래 하시나요?', '과다월경', 'wm', False),
    'E_146': ('혈액 응고 방지제를 드시나요?', '항응고제', 'meds', False),
    'E_147': ('최근 병원에서 진정 주사를 맞으셨어요?', '진정제 주사', 'meds', False),
    'E_148': ('속이 메스껍거나 토할 것 같으세요?', '구역', 'gi', False),
    'E_149': ('칼슘통로차단제를 드시나요?', '칼슘통로차단제', 'meds', False),
    'E_150': ('증상 이후 방귀나 대변이 나오나요?', '배변·방귀', 'gi', False),
    'E_151': ('몸에 부은 곳이 있으세요?', '부종', 'gen', False),
    'E_152': ('어디가 부으셨어요?', '부종 부위', 'gen', False),
    'E_153': ('골다공증 치료를 받고 계세요?', '골다공증', 'hx', False),
    'E_154': ('얼굴이 평소보다 창백한가요?', '창백', 'gen', False),
    'E_155': ('가슴이 두근거리세요?', '두근거림', 'cv', False),
    'E_156': ('한쪽 얼굴에 힘이 빠진 적 있나요?', '안면마비', 'neuro', True),
    'E_157': ('팔다리와 입 주변이 저리세요?', '사지·입주위 저림', 'neuro', False),
    'E_158': ('내분비나 호르몬 질환이 있으세요?', '내분비 질환', 'hx', False),
    'E_159': ('의식을 잃은 적 있나요?', '의식소실', 'neuro', True),
    'E_160': ('조산이나 출생 시 문제가 있었나요?', '조산·출생합병증', 'hx', False),
    'E_161': ('입맛이 없거나 금방 배부르세요?', '조기 포만감', 'gi', False),
    'E_162': ('최근 3개월간 체중이 저절로 줄었나요?', '체중 감소', 'gen', True),
    'E_163': ('질 분비물이 있으세요?', '질 분비물', 'wm', False),
    'E_164': ('맥이 아주 불규칙하게 뛰나요?', '불규칙 맥박', 'cv', False),
    'E_165': ('가족 중에 기흉을 앓은 분이 계세요?', '기흉 가족력', 'fh', False),
    'E_166': ('기침 끝에 토하신 적 있나요?', '기침 후 구토', 'resp', False),
    'E_167': ('임신 가능성이 있으세요?', '임신 가능성', 'wm', False),
    'E_168': ('혀가 입 밖으로 나오려 하나요?', '혀 내밂', 'neuro', False),
    'E_169': ('코나 목 안쪽이 가려우세요?', '코·목 가려움', 'ent', False),
    'E_170': ('눈이 심하게 가려우세요?', '눈 가려움', 'eye', False),
    'E_171': ('몸이나 주변이 낯설게 느껴지세요?', '이인감', 'psy', False),
    'E_172': ('눈꺼풀이 잘 안 떠지나요?', '안검하수', 'eye', False),
    'E_173': ('명치부터 목까지 타는 듯하세요?', '가슴쓰림', 'gi', False),
    'E_174': ('체중이 줄거나 입맛이 없으세요?', '체중·식욕 감소', 'gen', False),
    'E_175': ('최근 몸이 처지고 기운이 없으세요?', '전신 쇠약감', 'gen', False),
    'E_176': ('팔다리나 얼굴에 힘이 빠진 적 있나요?', '마비·근력저하', 'neuro', True),
    'E_177': ('몸 어딘가가 저리거나 감각이 둔하세요?', '감각 이상', 'neuro', False),
    'E_178': ('멍이 잘 들거나 피가 잘 나나요?', '출혈 경향', 'gen', True),
    'E_179': ('변에 선홍색 피가 섞여 나오나요?', '혈변', 'gi', True),
    'E_180': ('눈동자가 마음대로 돌아가나요?', '안구 편위', 'eye', False),
    'E_181': ('코가 막히거나 맑은 콧물이 나나요?', '코막힘·콧물', 'ent', False),
    'E_182': ('누렇거나 푸른 콧물이 나오나요?', '화농성 콧물', 'ent', False),
    'E_184': ('혈관 확장제를 드시나요?', '혈관확장제', 'meds', False),
    'E_185': ('머리를 다친 적 있나요?', '두부 외상', 'hx', False),
    'E_186': ('수면무호흡증 진단을 받으셨어요?', '수면무호흡증', 'hx', False),
    'E_187': ('참치 같은 생선을 드신 뒤 생겼나요?', '붉은살 생선 섭취', 'sh', False),
    'E_188': ('변이 희고 소변이 진한가요?', '회색변·진한소변', 'gi', False),
    'E_189': ('HIV 감염자와 성관계한 적 있나요?', 'HIV 감염자 접촉', 'sh', False),
    'E_190': ('침이 평소보다 많이 나오나요?', '침 흘림', 'ent', True),
    'E_191': ('예전에 담배를 피우셨어요?', '과거 흡연', 'sh', False),
    'E_192': ('목 근육이 굳어 고개를 못 돌리세요?', '사경', 'neck', False),
    'E_193': ('얼굴이나 목 근육이 경련하나요?', '근육 연축', 'neuro', False),
    'E_194': ('숨 들이쉴 때 높은 소리가 나나요?', '협착음', 'resp', True),
    'E_196': ('최근 한 달 내 수술을 받으셨어요?', '최근 수술', 'hx', False),
    'E_197': ('신증후군 진단을 받으셨어요?', '신증후군', 'hx', False),
    'E_198': ('농업에 종사하세요?', '농업 종사', 'sh', False),
    'E_199': ('건설업에 종사하세요?', '건설업 종사', 'sh', False),
    'E_200': ('광업에 종사하세요?', '광업 종사', 'sh', False),
    'E_201': ('기침을 하세요?', '기침', 'resp', False),
    'E_202': ('기침 끝에 흡 하는 소리가 나나요?', '백일해성 기침', 'resp', False),
    'E_203': ('심하게 몰아서 기침하세요?', '발작성 기침', 'resp', False),
    'E_204': ('최근 해외여행 다녀오셨어요?', '해외여행', 'sh', False),
    'E_205': ('입이 잘 안 벌어지거나 턱이 아프세요?', '개구장애', 'neuro', False),
    'E_206': ('입안에 아픈 궤양이 있으세요?', '구강 궤양', 'ent', False),
    'E_208': ('평소 많이 마른 편이세요?', '저체중', 'hx', False),
    'E_209': ('예방접종은 다 맞으셨어요?', '예방접종', 'hx', False),
    'E_210': ('피나 커피색 물질을 토하셨어요?', '토혈', 'gi', True),
    'E_211': ('여러 번 토하거나 헛구역질하셨어요?', '반복 구토', 'gi', False),
    'E_212': ('목소리가 쉬거나 변했나요?', '쉰 목소리', 'ent', False),
    'E_213': ('최근 코감기약이나 각성제를 드셨어요?', '충혈제거제', 'meds', False),
    'E_214': ('숨 내쉴 때 쌕쌕거리나요?', '호기성 천명', 'resp', False),
    'E_215': ('먹고 나면 증상이 심해지나요?', '식후 악화', 'gi', False),
    'E_216': ('움직이면 통증이 심해지나요?', '움직임 시 악화', 'msk', False),
    'E_217': ('누우면 심해지고 앉으면 나아지나요?', '눕기 시 악화', 'resp', False),
    'E_218': ('움직이면 심해지고 쉬면 나아지나요?', '운동 시 악화', 'cv', False),
    'E_219': ('밤에 증상이 더 심하세요?', '야간 악화', 'gen', False),
    'E_220': ('숨을 깊이 쉬면 아프세요?', '흡기 시 통증', 'resp', False),
    'E_221': ('기침하거나 힘줄 때 더 아프세요?', '복압 시 악화', 'gen', False),
    'E_222': ('매일 간접흡연에 노출되세요?', '간접흡연', 'sh', False),
    'E_223': ('가족 중에 췌장암 있는 분이 계세요?', '췌장암 가족력', 'fh', False),
    'E_224': ('가족 중에 폐암 있는 분이 계세요?', '폐암 가족력', 'fh', False),
    'E_225': ('가족 중 50세 전에 심장병 있었나요?', '조기 심질환 가족력', 'fh', False),
    'E_226': ('알레르기가 잘 생기는 편이세요?', '알레르기 체질', 'hx', False),
    'E_227': ('면역력이 떨어져 있으세요?', '면역저하', 'hx', False),
}

# DDXPlus condition id: (한국어 이름, [동의어(한/영)])
COND = {
    'Spontaneous pneumothorax': ('자연기흉', ['기흉', '자발성 기흉', 'pneumothorax']),
    'Cluster headache': ('군발두통', ['군집두통', 'cluster headache']),
    'Boerhaave': ('보어하베 증후군', ['식도 파열', '자발성 식도파열', 'boerhaave', 'esophageal rupture']),
    'Spontaneous rib fracture': ('자발성 늑골 골절', ['늑골 골절', '갈비뼈 골절', 'rib fracture']),
    'GERD': ('위식도 역류질환', ['역류성 식도염', '위식도역류', 'gerd', 'reflux esophagitis']),
    'HIV (initial infection)': ('급성 HIV 감염', ['HIV 감염', '에이즈', 'acute hiv', 'hiv infection']),
    'Anemia': ('빈혈', ['철결핍성 빈혈', 'anemia', 'anaemia']),
    'Viral pharyngitis': ('바이러스 인두염', ['인두염', '인후염', 'pharyngitis']),
    'Inguinal hernia': ('서혜부 탈장', ['사타구니 탈장', '탈장', 'inguinal hernia']),
    'Myasthenia gravis': ('중증 근무력증', ['근무력증', 'myasthenia']),
    'Whooping cough': ('백일해', ['whooping cough', 'pertussis']),
    'Anaphylaxis': ('아나필락시스', ['과민성 쇼크', 'anaphylaxis', 'anaphylactic']),
    'Epiglottitis': ('후두개염', ['급성 후두개염', 'epiglottitis']),
    'Guillain-Barré syndrome': ('길랭-바레 증후군', ['길랑바레', '길랭바레', 'guillain']),
    'Acute laryngitis': ('급성 후두염', ['후두염', 'laryngitis']),
    'Croup': ('크룹', ['후두기관기관지염', 'croup', 'laryngotracheobronchitis']),
    'PSVT': ('발작성 상심실성 빈맥', ['상심실성 빈맥', '발작성 빈맥', 'psvt', 'supraventricular tachycardia']),
    'Atrial fibrillation': ('심방세동', ['심방 세동', 'atrial fibrillation', 'afib']),
    'Bronchiectasis': ('기관지확장증', ['기관지 확장증', 'bronchiectasis']),
    'Allergic sinusitis': ('알레르기 비염', ['알레르기성 비염', '알레르기성 부비동염', 'allergic rhinitis',
                                         'allergic sinusitis', 'hay fever']),
    'Chagas': ('샤가스병', ['샤가스', 'chagas']),
    'Scombroid food poisoning': ('스콤브로이드 중독', ['히스타민 식중독', '고등어 중독', 'scombroid']),
    'Myocarditis': ('심근염', ['myocarditis']),
    'Larygospasm': ('후두경련', ['후두 연축', 'laryngospasm', 'larygospasm']),
    'Acute dystonic reactions': ('급성 근긴장이상 반응', ['급성 근긴장이상', '근긴장이상', '이긴장증', 'dystonia',
                                                 'dystonic']),
    'Localized edema': ('국소 부종', ['국소부종', '혈관부종', '혈관성 부종', 'localized edema', 'angioedema']),
    'SLE': ('전신 홍반 루푸스', ['전신홍반루푸스', '루푸스', 'lupus', 'systemic lupus']),
    'Tuberculosis': ('결핵', ['폐결핵', 'tuberculosis']),
    'Unstable angina': ('불안정 협심증', ['불안정형 협심증', 'unstable angina']),
    'Stable angina': ('안정 협심증', ['안정형 협심증', '협심증', 'stable angina', 'angina']),
    'Ebola': ('에볼라', ['에볼라 출혈열', 'ebola']),
    'Acute otitis media': ('급성 중이염', ['중이염', 'otitis media']),
    'Panic attack': ('공황발작', ['공황장애', '공황 발작', 'panic attack', 'panic disorder']),
    'Bronchospasm / acute asthma exacerbation': ('급성 천식 악화', ['천식 발작', '천식 악화', '천식', '기관지 경련',
                                                                 'asthma', 'bronchospasm']),
    'Bronchitis': ('급성 기관지염', ['기관지염', 'bronchitis']),
    'Acute COPD exacerbation / infection': ('COPD 급성 악화', ['만성 폐쇄성 폐질환', '만성폐쇄성폐질환', 'copd']),
    'Pulmonary embolism': ('폐색전증', ['폐동맥 색전증', '폐색전', '폐동맥색전', 'pulmonary embolism']),
    'URTI': ('상기도 감염', ['상기도감염', '감기', '코감기', 'urti', 'common cold', 'upper respiratory']),
    'Influenza': ('인플루엔자', ['독감', 'influenza']),
    'Pneumonia': ('폐렴', ['지역사회획득 폐렴', 'pneumonia']),
    'Acute rhinosinusitis': ('급성 부비동염', ['부비동염', 'acute sinusitis', 'acute rhinosinusitis', 'sinusitis']),
    'Chronic rhinosinusitis': ('만성 부비동염', ['축농증', 'chronic sinusitis', 'chronic rhinosinusitis']),
    'Bronchiolitis': ('세기관지염', ['급성 세기관지염', 'bronchiolitis']),
    'Pulmonary neoplasm': ('폐암', ['폐종양', '폐 종양', 'lung cancer', 'pulmonary neoplasm', 'lung neoplasm']),
    'Possible NSTEMI / STEMI': ('급성 심근경색', ['심근경색', '급성 관상동맥 증후군', '급성관상동맥증후군', 'nstemi',
                                               'stemi', 'myocardial infarction', 'heart attack']),
    'Sarcoidosis': ('사르코이드증', ['유육종증', 'sarcoidosis']),
    'Pancreatic neoplasm': ('췌장암', ['췌장 종양', 'pancreatic cancer', 'pancreatic neoplasm']),
    'Acute pulmonary edema': ('급성 폐부종', ['폐부종', '급성 심부전', '심부전', 'pulmonary edema', 'heart failure']),
    'Pericarditis': ('심낭염', ['심막염', '급성 심낭염', 'pericarditis']),
}


def nlen(s: str) -> int:
    return len(unicodedata.normalize('NFC', s))


def stage_of(code: str, sys_: str, is_ante: bool) -> str:
    if code == 'E_167':
        return 'preg'
    if sys_ == 'fh':
        return 'fh'
    if sys_ == 'sh':
        return 'sh'
    return 'hx' if is_ante else 'core'


def build(src: str) -> dict:
    with open(os.path.join(src, 'release_conditions.json'), encoding='utf-8') as f:
        conds = json.load(f)
    with open(os.path.join(src, 'release_evidences.json'), encoding='utf-8') as f:
        evids = json.load(f)

    used = set()
    for c in conds.values():
        used |= set(c['symptoms']) | set(c['antecedents'])
    missing = sorted(used - set(EVID) - set(SKIPPED))
    assert not missing, f'untranslated evidences: {missing}'
    assert not set(EVID) & set(SKIPPED)

    ev_out = {}
    for code in sorted(set(EVID) & used, key=lambda x: int(x.split('_')[1])):
        q, label, sys_, red = EVID[code]
        q = unicodedata.normalize('NFC', q)
        label = unicodedata.normalize('NFC', label)
        assert nlen(q) <= 30, (code, q, nlen(q))
        assert q.endswith('?') and q.count('?') == 1, (code, q)
        assert ',' not in q, (code, q)
        assert nlen(label) <= 12, (code, label, nlen(label))
        assert sys_ in SYSTEMS, (code, sys_)
        e = {'q': q, 'label': label, 'sys': sys_, 'red': bool(red),
             'stage': stage_of(code, sys_, bool(evids[code]['is_antecedent']))}
        if code in FEMALE_ONLY:
            e['sex'] = 'F'
        if code in ADULT_ONLY:
            e['adult'] = True
        ev_out[code] = e

    missing_c = sorted(set(conds) - set(COND))
    assert not missing_c, f'untranslated conditions: {missing_c}'
    c_out = {}
    for cid, c in conds.items():
        ko, syn = COND[cid]
        c_out[cid] = {
            'en': c.get('cond-name-eng') or cid,
            'ko': ko,
            'syn': syn,
            'severity': int(c.get('severity') or 3),
            'symptoms': [k for k in c['symptoms'] if k in ev_out],
            'antecedents': [k for k in c['antecedents'] if k in ev_out],
        }
    return {
        'source': 'DDXPlus (Fansi Tchango et al., NeurIPS 2022 Datasets and Benchmarks) — '
                  'release_conditions.json / release_evidences.json; Korean text is our own translation/adaptation',
        'license': 'CC BY 4.0',
        'skipped': sorted(SKIPPED, key=lambda x: int(x.split('_')[1])),
        'conditions': c_out,
        'evidences': ev_out,
    }


def main(argv):
    src = argv[1] if len(argv) > 1 else DEFAULT_SRC
    kb = build(src)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    data = json.dumps(kb, ensure_ascii=False, separators=(',', ':'))
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(data)
    size = len(data.encode('utf-8'))
    assert size < 300_000, size
    print(f'wrote {OUT}: {size} bytes, {len(kb["conditions"])} conditions, {len(kb["evidences"])} evidences, '
          f'{len(kb["skipped"])} skipped')


if __name__ == '__main__':
    main(sys.argv)

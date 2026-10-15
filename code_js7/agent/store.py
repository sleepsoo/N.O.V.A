"""문진 사실 장부(fact store): 환자 답마다 항목별 사실을 쌓고, 양성 단서는 바로 후속 질문으로 파고든다.

v2까지는 양성 단서(예: '가만히 있어도 두근거려요')가 나와도 같은 묶음 안에서는 파고들지 못하고
다음 LLM 계획 시점에야 반영됐다. 장부는
1) 답할 때마다 slot → (턴, 질문, 답, 극성)을 기록하고
2) 양성(또는 정보형) 답이면 FOLLOWUP에 정한 세부 질문을 바로 다음 턴에 묻게 하며
3) LLM 계획(plan_q)에 '양성 단서와 아직 확인 안 된 세부' 요약을 넘긴다.
후속 질문도 체크리스트 slot으로 등록해 기존 중복 방지(asked·covered·유사 질문)를 그대로 탄다.
"""
from __future__ import annotations

import re

from .util import nfc

# 답 극성
NEG_RE = re.compile(r'^\s*(아니(요|오)?|아뇨|없|전혀|안\s|별로\s*없)|(없어요|없습니다|없었어요|안\s*피워요|안\s*마셔요|안\s*먹어요|'
                    r'안\s*해요|않아요|않았어요|적\s*없어요)[.!]?\s*$')
AMBIG_RE = re.compile(r'(말고는|말곤|빼고|외에는|보다는|보단|기보다|글쎄|잘\s*모르|모르겠)')
POS_RE = re.compile(r'^\s*(네|예|응|있|조금|가끔|자주|많이|항상|매일|요즘)|(있어요|있었어요|해요|돼요|타요|나요|떨려요|'
                    r'두근거려요|아파요|빠져요|늘었어요|줄었어요)[.!]?\s*$')


def polarity(answer: str) -> str:
    """'neg' | 'ambig' | 'pos' | 'info'(수치·서술형)."""
    a = nfc(answer).strip()
    if not a:
        return 'ambig'
    if AMBIG_RE.search(a):
        return 'ambig'
    if NEG_RE.search(a):
        return 'neg'
    if POS_RE.search(a):
        return 'pos'
    return 'info'


# slot → (트리거, [(후속 slot, 라벨, 질문[, 답에 이미 있으면 건너뛸 정규식])]). 트리거: 'pos'(양성일 때), 'any'(부정이 아닐 때 = 양성·정보형·모호)
# 질문은 모두 NFC 28자 이하(tests). 이미 은행에 있는 slot을 쓰면 그 은행 질문 대신 여기 문구로 바로 묻는다.
FOLLOWUP = {
    # 과거력·약물·가족력·사회력: 양성이면 무엇·언제·얼마나
    'pmh_htn_dm': ('pos', [('pmh_htn_dm_detail', '진단 시기·약', '언제 진단받고 무슨 약 드세요?', r'(년|약|핀|린|정\b)')]),
    'pmh_other': ('pos', [('pmh_other_detail', '질환 세부', '언제 진단받고 치료 중이세요?')]),
    'pmh_op': ('pos', [('pmh_op_detail', '수술 세부', '무슨 수술을 언제 받으셨어요?', r'(수술.{0,6}(년|살|때)|(년|살|때).{0,10}수술)')]),
    'pmh_meds': ('pos', [('pmh_meds_detail', '약 이름·용량', '약 이름과 용량을 아세요?', r'(mg|밀리|[가-힣]+(핀|린|롤|정|틴|드)\b)')]),
    'pmh_allergy': ('pos', [('pmh_allergy_detail', '알레르기 반응', '어떤 약에 어떤 반응이 있었나요?')]),
    'fh_open': ('any', [('fh_detail', '가족력 세부', '누가 몇 살쯤 그 병을 앓으셨어요?', r'(\d+\s*(살|세|대)|[가-힣]+십\s*대|돌아가)')]),
    'sh_smoke': ('pos', [('sh_smoke_amt', '흡연량', '하루 몇 개비, 몇 년 피우셨어요?', r'(개비|갑|반\s*갑)')]),
    'sh_alcohol': ('pos', [('sh_alcohol_amt', '음주량', '한 번에 얼마나 드세요?', r'(잔|병|캔|\d)')]),
    'wm_cycle': ('pos', [('wm_cycle_detail', '월경 변화 세부', '언제부터 어떻게 달라졌나요?', r'(달|개월|주).{0,12}(줄|늘|짧|길|불규칙)')]),
    'ps_mood': ('pos', [('ps_interest', '흥미 저하', '즐겁던 일에 흥미가 줄었나요?'),
                        ('ps_si', '자살 사고', '혹시 죽고 싶은 생각이 드신 적 있나요?')]),
    'ps_anxiety': ('pos', [('ps_anx_detail', '불안 상황', '주로 언제 불안하세요?')]),
    'ps_si': ('pos', [('md_plan', '자살 계획', '구체적으로 방법을 생각해 보셨나요?')]),
    # 체중 감소·갑상선
    'wl_palp': ('pos', [('wl_palp_freq', '두근거림 빈도', '얼마나 자주 두근거리세요?', r'(자주|매일|하루|번|가끔|늘|항상)'),
                        ('wl_palp_irreg', '불규칙 맥', '맥이 불규칙하게 뛰나요?')]),
    'wl_tremor': ('pos', [('wl_tremor_when', '떨림 상황', '어떨 때 손이 떨리세요?', r'(때|들|쓸|잡)')]),
    'wl_bowel': ('any', [('wl_bowel_freq', '배변 횟수', '하루에 몇 번 보세요?', r'(\d|[한두세네다섯]\s*번|회)')]),
    'wl_eye': ('pos', [('wl_diplopia', '복시', '물체가 둘로 보이나요?')]),
    'wl_neck': ('pos', [('wl_neck_pain', '목 통증', '목이 아프거나 누르면 아픈가요?')]),
    'wl_fatigue': ('pos', [('wl_fatigue_when', '근력 저하 양상', '언제부터 다리 힘이 빠졌나요?')]),
    # 두근거림
    'pa_syncope': ('pos', [('pa_syncope_detail', '실신 상황', '실제로 정신을 잃은 적 있나요?')]),
    'pa_chest': ('pos', [('pa_chest_detail', '흉통 양상', '가슴이 어떻게 아프세요?')]),
    # 불면·약물
    'in_meds': ('pos', [('sb_name', '약 이름·용량', '드시는 약 이름과 용량을 아세요?')]),
    'sb_dose_now': ('any', [('sb_last', '마지막 복용', '마지막으로 언제 몇 알 드셨어요?', r'(어제|오늘|어젯밤|새벽|아침)')]),
    'sb_withdraw': ('any', [('sb_seizure', '금단 경련', '약을 끊었을 때 경련한 적 있나요?'),
                            ('sb_delirium', '금단 환각', '끊었을 때 헛것이 보인 적 있나요?')]),
    'sb_cutdown': ('pos', [('sb_cutdown_fail', '감량 실패', '줄이다 다시 드신 이유가 뭐예요?')]),
    'sb_blackout': ('pos', [('sb_sleepact', '복합수면행동', '잠결에 뭘 먹거나 돌아다녔나요?')]),
    'sb_other': ('pos', [('sb_other_detail', '병용 약 세부', '그 약은 얼마나 자주 드세요?', r'(가끔|매일|자주|번|일주일)')]),
    # 소아 성장
    'gr_fh': ('any', [('gr_fh_detail', '가족 저신장 세부', '그분 키는 얼마나 되세요?', r'(\d{2,3}|센티|cm)')]),
    'gr_chronic': ('pos', [('gr_chronic_detail', '만성질환 세부', '어떤 병으로 치료받았나요?')]),
    'gr_hypo': ('pos', [('gr_cold', '추위 민감', '추위를 많이 타나요?')]),
    'gr_puberty': ('pos', [('gr_puberty_when', '사춘기 시작', '언제부터 그런 변화가 있었나요?')]),
    'gr_weight': ('pos', [('gr_weight_detail', '체중 변화 세부', '얼마나 빠지거나 쪘나요?', r'(\d|킬로|키로|kg)')]),
    # 공통 증상
    'hpi_course': ('pos', [('hpi_course_detail', '경과 세부', '언제부터 더 심해졌나요?', r'(전부터|년|달|개월|주)')]),
    'hpi_impact': ('pos', [('hpi_impact_detail', '일상 지장 세부', '어떤 일이 가장 힘드세요?')]),
}


class FactStore:
    def __init__(self):
        self.rows: list[dict] = []        # 답 하나당 한 줄
        self.followed: set[str] = set()   # 후속 질문을 이미 낸 slot

    def record(self, slot: str, label: str, entry: dict) -> dict:
        row = {'slot': slot or 'free', 'label': label or '', 'turn': entry.get('turn'), 'q': entry.get('text') or '',
               'a': entry.get('reply') or '', 'pol': polarity(entry.get('reply') or '')}
        self.rows.append(row)
        return row

    def followups(self, slot: str, answer: str) -> list[tuple[str, str, str]]:
        """방금 답한 slot의 후속 질문(아직 내지 않은 것만)."""
        if slot in self.followed or slot not in FOLLOWUP:
            return []
        trig, items = FOLLOWUP[slot]
        pol = polarity(answer)
        if pol == 'neg' or (trig == 'pos' and pol not in ('pos',)):
            return []
        self.followed.add(slot)
        a = nfc(answer)
        # 답에 이미 그 세부가 들어 있으면(예: '하루 두세 번 보고 묽어요') 다시 묻지 않는다
        return [it[:3] for it in items if not (len(it) > 3 and re.search(it[3], a))]

    def summary(self, limit: int = 12) -> str:
        """LLM 계획용: 양성·모호 단서와 아직 확인하지 않은 세부."""
        out = []
        for r in self.rows:
            if r['pol'] not in ('pos', 'ambig', 'info'):
                continue
            todo = ''
            if r['slot'] in FOLLOWUP and r['slot'] not in self.followed:
                todo = ' → 세부 미확인: ' + ', '.join(it[1] for it in FOLLOWUP[r['slot']][1])
            out.append(f"턴 {r['turn']} {r['label'] or r['q']}: {r['a'][:30]}{todo}")
        return '\n'.join(out[-limit:]) or '(없음)'

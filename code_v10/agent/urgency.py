"""v14: 처치 긴급도(응급·조기 재진·일반) 판정 — 숨은 급성 증례의 안전·추적 결함 보강.

배경: v8 이후 설명 경로(plan_and_say_v8·render_plan)에 v7의 응급 승격이 없어, 급성 복통·흉통 같은 증례에도
'…하고 2주 뒤 결과 봐요'를 말하고 기록도 '입원 불필요, 외래 추적'으로 남았다(공개 샘플 3례는 모두 만성이라 드러나지 않음).
판정 근거: (a) 시행한 진찰의 응급 소견(복막·수막 자극) (b) 활력징후 불안정 (c) 계획 LLM의 urgency 판단
(d) 진단명 자체가 응급·급성 질환(KB 없는 경우만; KB 진단은 KB 추적 시점을 따른다).
"""
from __future__ import annotations

import re

from .util import log, nfc

EMERG_EXAM_RED = [(r'반발\s*\S{0,3}통\s*\(\s*\+', '반발통'), (r'근성\s*방어\S{0,4}\s*\(\s*\+', '근성방어'),
                  (r'복막\s*자극\S{0,6}\s*\(\s*\+', '복막자극 징후'), (r'경부\s*강직\s*\(\s*\+', '경부강직'),
                  (r'(케르니그|커니그|브루진스키)\S{0,4}\s*\(\s*\+', '수막자극 징후'),
                  (r'의식\s*(저하|혼탁|장애)\s*\(\s*\+|지남력\s*[0-2]\s*/\s*3', '의식 저하')]
EMERG_TXT_RE = re.compile(r'응급|입원\s*(이\s*)?(필요|치료)|수술\s*(필요|적응|평가)|외과\s*(의뢰|협진|평가)|즉시\s*전원')
EMERG_NEG_RE = re.compile(r'불필요|고려|없(어|음|고|으며|다)|않|아님|낮|기준|교육|안내|배제')
EMERG_COND_RE = re.compile(r'(\s시|경우|이면|하면|되면|때)(\s|$)')
# 진단명만으로 당일 응급 평가가 표준인 질환(KB 없는 진단에만 적용)
EMERG_DX_RE = re.compile(r'충수|담낭염|담관염|장폐색|천공|복막염|장중첩|장염전|감돈|대동맥|박리|심근경색|급성\s*관상|불안정\s*협심|'
                         r'폐색전|폐렴\s*\(중증|기흉|뇌졸중|뇌경색|뇌출혈|지주막하|일과성\s*허혈|수막염|뇌염|자궁외|난소\s*염전|'
                         r'고환\s*염전|케톤산증|고삼투|갑상샘\s*중독\s*발증|부신\s*위기|아나필락시스|패혈증|화농성\s*관절|'
                         r'급성\s*녹내장|척수\s*압박|말총|횡문근|급성\s*신손상|상부\s*위장관\s*출혈|토혈|심부정맥|심내막염|심근염|'
                         r'급성\s*담낭|급성\s*췌장|신우신염\s*\(중증|경막', re.I)
# 2~3일 내 재진·조기 외래 평가가 표준인 급성 질환(KB 없는 진단)
URGENT_DX_RE = re.compile(r'폐렴|신우신염|요로결석|담석|급성\s*(위장염|기관지염|편도염|인두염|부비동염|방광염|요도염)|대상포진|'
                          r'봉와직염|농가진|급성\s*통풍|급성\s*관절|요추\s*염좌|추간판|좌골|급성\s*중이염|가와사키|열성\s*경련|'
                          r'탈수|식중독|위궤양|십이지장|소화성\s*궤양|급성\s*위염|급성\s*간염|전염성\s*단핵구|수족구|독감|인플루엔자|'
                          r'코로나|천식\s*악화|만성\s*폐쇄성\s*폐질환\s*악화|심부전\s*악화|협심증|부정맥|발작성', re.I)
EMERG_SAY = '지금 바로 응급실에서 원인 검사를 받으셔야 해요.'   # tests 슬롯(검사+목적 게이트 통과) 대체 문장
EMERG_SAY_SHORT = '오늘 바로 응급실로 가셔야 해요.'
EMERG_FU = '재진 : 응급 평가 후 결과에 따라 외래 추적'
URGENT_FU = '재진 : 2~3일 내 증상 재평가(악화 시 당일 내원)'
LEVELS = ('routine', 'urgent', 'emergency')


def _text_hit(text: str) -> bool:
    for cl in re.split(r'[,.;·→\n]|\s[—-]\s', text or ''):
        m = EMERG_TXT_RE.search(cl)
        if m and not EMERG_NEG_RE.search(cl) and not EMERG_COND_RE.search(cl[:m.start()]):
            return True
    return False


def _dept(dxt: str, red: list[str]) -> str:
    if re.search(r'수막|뇌염|뇌졸중|뇌경색|뇌출혈|지주막하|경막', dxt) or any(r in red for r in ('경부강직', '수막자극 징후', '의식 저하')):
        return '신경과'
    if re.search(r'충수|담낭|담관|담석|장폐색|복막|천공|감돈|탈장|게실|췌장|장염전|장중첩', dxt) or any(
            r in red for r in ('반발통', '근성방어', '복막자극 징후')):
        return '외과'
    if re.search(r'심근|관상|협심|대동맥|폐색전|부정맥|심내막|심근염', dxt):
        return '심장내과'
    if re.search(r'자궁외|난소', dxt):
        return '산부인과'
    if re.search(r'고환', dxt):
        return '비뇨의학과'
    return '해당 전문과'


def assess(enc, k, plan_res: dict | None) -> dict:
    """긴급도 판정 → {'level','red','dept','why'}; enc.urgency에 저장. 설정 V14가 꺼져 있으면 routine."""
    res = {'level': 'routine', 'red': [], 'dept': '', 'why': []}
    cfg = getattr(enc, 'cfg', None) or {}
    if not cfg.get('V14'):
        enc.urgency = res
        return res
    red, why = [], []
    for e in getattr(enc, 'ledger', None) or []:
        if e.get('kind') != 'EXAM' or e.get('refused'):
            continue
        for pat, name in EMERG_EXAM_RED:
            if re.search(pat, e.get('reply') or '') and name not in red:
                red.append(name)
    try:
        from .record import vitals_assessment
        if '불안정' in vitals_assessment(enc):
            red.append('활력징후 불안정')
    except Exception:  # noqa: BLE001
        pass
    dx = nfc(getattr(enc, 'dx', None) or '')
    diffs = [d.get('dx') or '' for d in ((getattr(enc, 'assess', None) or {}).get('differential') or [])[:1]]
    dxt = dx + ' ' + ' '.join(diffs)
    level = 'routine'
    if red:
        level, why = 'emergency', [f'진찰·활력: {"·".join(red)}']
    llm_u = str((plan_res or {}).get('urgency') or '').strip().lower()
    disp_txt = '\n'.join(str(x) for x in ((plan_res or {}).get('disposition') or []))
    if not k:   # KB 진단(만성·검증된 추적 계획)은 진단명·LLM 판단으로 승격하지 않는다(진찰·활력 소견만)
        if llm_u == 'emergency' or _text_hit(disp_txt) or EMERG_DX_RE.search(dx):
            level = 'emergency'
            why.append('LLM urgency' if llm_u == 'emergency' else ('처치 결정 문구' if _text_hit(disp_txt) else '진단명(응급 질환)'))
        elif level == 'routine' and (llm_u == 'urgent' or URGENT_DX_RE.search(dx)):
            level = 'urgent'
            why.append('LLM urgency' if llm_u == 'urgent' else '진단명(급성 질환)')
    res = {'level': level, 'red': red, 'dept': _dept(dxt, red) if level == 'emergency' else '', 'why': why}
    enc.urgency = res
    if level != 'routine':
        log(f'v14 urgency: {res}')
    return res


def level(enc) -> str:
    return (getattr(enc, 'urgency', None) or {}).get('level', 'routine')


def emergency_disposition(enc, em: dict, vitals_assessment) -> str:
    vs = ''
    try:
        vs = (vitals_assessment(enc) or '').strip().lstrip('- ').strip()
        vs = vs.split(' → ')[0]
    except Exception:  # noqa: BLE001
        pass
    finds = [r for r in em.get('red') or [] if r != '활력징후 불안정']
    parts = [vs] if vs else []
    if finds:
        parts.append(f"진찰상 {'·'.join(finds)} 양성")
    if not finds and em.get('why'):
        parts.append('급성 응급 질환 의심 소견')
    head = ', '.join(parts) or '응급 평가 필요 소견'
    return f"{head} → 응급실 의뢰, 당일 {em.get('dept') or '해당 전문과'} 평가 필요(입원 여부는 응급 평가 후 결정)"

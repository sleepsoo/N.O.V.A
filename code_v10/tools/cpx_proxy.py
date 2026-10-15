"""체크리스트 대리 평가기(sota34_analysis §9.12-1): 공개 3증례 가설 체크리스트로 transcript가 덮은 문진·진찰·설명·안전 비율.

점수 예측이 아니라 '설계 준수' 지표다. 가설 체크리스트는 §9.4(C10)·§9.5(C01)와 C03 모범 기록 S·O·P에서 재구성했다.
판정: 문진 항목 = 문진 단계 의사 질문이 그 항목을 물었거나(q 정규식) 환자 답·시작 정보에 그 사실이 나왔으면(a 정규식) 덮임.
진찰 = EXAM 문장이 표준 행 이름과 맞으면. 설명 = 설명 단계 SAY 슬롯 정규식. 안전 = 질문·설명·기록 정규식.

사용:
  python tools/cpx_proxy.py --run ../code/runs/sim-C10-v8a            # ledger.json(+record.json, summary.json의 case_id)
  python tools/cpx_proxy.py --run DIR --case C10 --json                  # 결과 JSON
표준 라이브러리만 사용, 네트워크·키 없음.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata

INTERVIEW_PHASES = {'first', 'interview', 'ice', 'interview-single', 'first-single', 'ice-single', 'hpi', 'bundle', 'history',
                    'ros', 'adaptive1', 'adaptive2', 'empathy'}
EXPLAIN_PHASES = {'explain', 'explain-answer', 'explain-teachback'}

# (id, 라벨, 질문 정규식, 답 정규식 또는 None, 시작 정보 정규식 또는 None)
CHECK = {
    'C10': {
        'interview': [
            ('H1', '감량 양·기간', r'몇\s*(킬로|kg)|얼마나\s*빠', None, r'킬로|키로|kg'),
            ('H2', '의도 여부', r'다이어트|일부러', None, r'다이어트|저절로'),
            ('H3', '식욕·식사량', r'식사|입맛|식욕', r'입맛|많이\s*먹|식사', None),
            ('H4', '활동량', r'활동량|운동량', None, None),
            ('H5', '더위 불내성', r'더위|덥', r'더위', None),
            ('H6', '발한', r'땀', r'땀|젖', None),
            ('H7', '두근거림', r'두근', r'두근', None),
            ('H8', '손떨림', r'떨', r'떨', None),
            ('H9', '불안·불면', r'불안|잠|초조', r'불안|잠|초조', None),
            ('H10', '피로·근력', r'지치|피곤|힘이?\s*빠', None, None),
            ('H11', '배변 변화', r'대변|배변|설사|변비', r'묽|번', None),
            ('H12', '복통·구토·혈변', r'복통|구토|혈변|배가', None, None),
            ('H13', '갈증·소변', r'갈증|소변|물을', None, None),
            ('H14', '월경', r'생리|월경', r'생리|양이', None),
            ('H15', '임신', r'임신', None, None),
            ('H16', '눈', r'눈', r'눈|뻑뻑|튀어', None),
            ('H17', '목(비대·혹·연하)', r'목이|목에|혹|삼키', r'목', None),
            ('H18', '최근 감염·발열', r'열이|감기|발열', None, None),
            ('H19', '흉통·숨참·부종', r'가슴\s*통증|숨|흉통|붓', None, None),
            ('H20', '우울·스트레스', r'기분|우울|스트레스', None, None),
            ('H21', '갑상선·만성질환 과거력', r'갑상선\s*질환|지병|질환이나|천식', None, None),
            ('H22', '약·보조제', r'약이나|영양제|드시는\s*약', None, None),
            ('H23', '가족력', r'가족|부모', r'어머니|아버지', None),
            ('H24', '흡연·음주', r'담배|술', None, None),
            ('H25', '카페인·직업', r'커피|카페인|무슨\s*일|직업', None, None),
            ('H26', '치아·저작', r'치아|씹', None, None),
            ('H27', '걱정·기대', r'걱정|궁금', None, None),
        ],
        'exam': [('E2', '갑상선 촉진', r'갑상선 촉진'), ('E3', '안징후', r'안징후'), ('E4', '자세성 떨림', r'자세성 떨림'),
                 ('E5', '피부 온도·발한', r'피부 온도'), ('E6', '심음', r'심음'), ('E7', '경부 림프절', r'경부 림프절'),
                 ('E8', '복부 촉진', r'복부 촉진'), ('E9', '근력·반사', r'근력|심부건반사')],
        'explain': [('X1', '진단', r'그레이브스|갑상[선샘]'), ('X2', '기전·증상 연결', r'호르몬|면역|넘쳐|때문'),
                    ('X3', '걱정 직답·근거', r'암|걱정하신|보다'), ('X4', '검사·목적', r'검사|초음파'),
                    ('X5', '치료·경과', r'약으로|치료|조절|년'), ('X6', '경고(부작용 신호 포함)', r'바로\s*(오|와)|응급'),
                    ('X7', '재진', r'\d+\s*(~\s*\d+\s*)?(주|일|개월|달)\s*(뒤|후)|재진|다시\s*오')],
        'safety': [('S1', '임신 확인', 'q', r'임신'), ('S2', 'β차단제 금기(천식·심장병)', 'q', r'천식|심장'),
                   ('S3', '약 부작용 행동(발열·인후통·황달 등)', 'x', r'(열|목\s*아|인후|황달|숨참|두근).{0,20}바로'),
                   ('S4', '처치 근거(기록)', 'r', r'금기|천식|β|베타')],
    },
    'C01': {
        'interview': [
            ('H1', '불면 시작·양상', r'언제부터|잠들기|깨', r'년\s*전|잠들', None), ('H2', '수면 습관', r'몇\s*시|휴대폰|습관', None, None),
            ('H3', '주간 기능', r'낮에|졸리|멍|불편한\s*데', r'졸|멍', None), ('H4', '약 이름·용량', r'이름|용량', r'졸피|mg', None),
            ('H5', '현재 복용량·시각', r'몇\s*알|하루에', r'알', None), ('H6', '내성', r'늘|효과', r'늘', None),
            ('H7', '금단', r'안\s*드시면|끊으면', r'불안|땀|떨', None), ('H8', '감량 실패', r'줄이|끊어\s*보', None, None),
            ('H9', '여러 병원', r'어디서|처방받', r'병원', None), ('H10', '약국 약·병용', r'약국|다른\s*수면제', None, None),
            ('H11', '마지막 복용', r'마지막', None, None), ('H12', '비축', r'떨어질|모아|남은', None, None),
            ('H13', '기억 공백', r'기억', None, None), ('H14', '가족 갈등', r'가족|갈등', r'갈등|남편|딸', None),
            ('H15', '음주', r'술', None, None), ('H16', '카페인', r'커피|카페인', None, None), ('H17', '흡연', r'담배', None, None),
            ('H18', '운동', r'운동', None, None), ('H19', '과거력', r'고혈압|당뇨|지병', None, None),
            ('H20', '복용약', r'그\s*밖에\s*드시는|다른\s*약|드시는\s*약', r'암로디핀|혈압약', None),
            ('H21', '정신과 치료력', r'정신과|상담', None, None), ('H22', '우울·자살 사고', r'기분|우울|죽고', None, None),
            ('H23', '코골이·하지불안', r'코골|다리', None, None), ('H24', '가족력', r'가족\s*중|부모님', None, None),
            ('H25', '동거·직업', r'함께\s*사|누구와|무슨\s*일', None, None), ('H26', 'ICE', r'걱정|궁금', None, None),
            ('H27', '금단 경련·섬망', r'경련|헛것', None, None), ('H28', '운전', r'운전', None, None),
        ],
        'exam': [('E1', '의식·지남력', r'의식'), ('E2', '주간 진정·불안', r'진정'), ('E3', '인지 선별', r'인지기능'),
                 ('E4', '기립성 혈압', r'기립성'), ('E5', '자세성 떨림', r'자세성 떨림'), ('E6', '소뇌 협조', r'소뇌'),
                 ('E7', '보행', r'보행'), ('E8', '안구진탕·구음', r'안구진탕|구음'), ('E9', '갑상선', r'갑상선 촉진')],
        'explain': [('X1', '진단', r'의존|사용장애|중독'), ('X2', '기전', r'익숙|내성|늘고|끊기\s*힘'),
                    ('X3', '걱정 직답·근거', r'걱정|괜찮|위험'), ('X4', '검사', r'검사|심전도'),
                    ('X5', '치료·경과', r'줄여|감량|인지행동|치료'), ('X6', '경고', r'바로\s*(오|와)|응급'),
                    ('X7', '재진', r'\d+\s*(~\s*\d+\s*)?(주|일|개월|달)\s*(뒤|후)|재진|다시\s*오')],
        'safety': [('S1', '마지막 복용', 'q', r'마지막'), ('S2', '금단 경련·섬망 병력', 'q', r'경련|헛것'),
                   ('S3', '우울·자살 사고', 'q', r'죽고|자살'), ('S4', '급중단 금지 교육', 'x', r'끊지|천천히\s*줄'),
                   ('S5', '운전·병용 금지 교육', 'x', r'운전|술')],
    },
    'C03': {
        'interview': [
            ('H1', '인지 시점·경과', r'언제부터', None, r'일\s*년\s*전'), ('H2', '가정 측정치', r'잰|측정', None, r'센티'),
            ('H3', '영유아 검진 기록', r'기록|수첩|두\s*살|네\s*살', None, None),
            ('H4', '발달', r'말이나\s*걷기|발달|또래만큼', None, None), ('H5', '체중 변화', r'살이|체중', None, r'키로'),
            ('H6', '식욕·식사', r'밥|먹|식사|우유', None, None), ('H7', '갑상샘저하 증상', r'지치|변비|추위', None, None),
            ('H8', '쿠싱 증상', r'배만|둥글', None, None), ('H9', '사춘기 징후', r'음모|고환', None, None),
            ('H10', '걱정·기대', r'걱정|궁금', None, None), ('H11', '출생력(분만)', r'출산|분만|태어', None, None),
            ('H12', '출생 체격', r'태어날\s*때|출생', None, None), ('H13', '임신 중 문제', r'임신', None, None),
            ('H14', '신생아기', r'신생아|황달', None, None), ('H15', '수면', r'잠', None, None),
            ('H16', '활동', r'뛰어|활동|활발', None, None), ('H17', '만성질환', r'천식|콩팥|장,', None, None),
            ('H18', '입원·큰 병', r'입원|크게\s*아픈', None, None), ('H19', '복용약·한약·스테로이드', r'약|스테로이드|한약', None, None),
            ('H20', '부모 키', r'부모님\s*키', r'\d{3}', None), ('H21', '부 늦은 성장·사춘기', r'늦게', None, None),
            ('H22', '가족 저신장·유전병', r'키가\s*작거나|유전', None, None), ('H23', '어린이집', r'어린이집|학교', None, None),
            ('H24', '양육 환경', r'집에서|양육|키우기', None, None), ('H25', '두통·구토·시야(위험 징후)', r'두통|구토|시야', None, None),
        ],
        'exam': [('E1', '신체 계측', r'신체 계측'), ('E2', '성장도표', r'성장도표'), ('E3', '성장속도·중간부모키', r'성장 속도'),
                 ('E4', '신체 비율', r'신체 비율'), ('E5', '자주색 선조', r'선조'), ('E6', '안면 기형', r'안면 기형'),
                 ('E7', '갑상선', r'갑상선 촉진'), ('E8', '사춘기 성숙도', r'사춘기 성숙도'), ('E9', '복부 촉진', r'복부 촉진')],
        'explain': [('X1', '진단', r'체질성|늦게\s*크|성장\s*지연'), ('X2', '원인·패턴', r'사춘기|아빠|늦게|패턴|속도'),
                    ('X3', '걱정 직답·근거', r'큰\s*병|클\s*수|자라|키'), ('X4', '검사', r'검사|엑스레이|뼈\s*나이|골연령'),
                    ('X5', '치료·경과', r'치료|자라요|크는|성장호르몬'), ('X6', '경고', r'바로\s*(오|와)|응급'),
                    ('X7', '재진·추적', r'\d+\s*(~\s*\d+\s*)?(주|일|개월|달)\s*(뒤|후|마다)|재진|다시\s*오')],
        'safety': [('S1', '두개내 위험 징후 문진', 'q', r'두통|구토|시야'), ('S2', '갑상샘저하 증상 문진', 'q', r'변비|추위|지치'),
                   ('S3', '경고 교육', 'x', r'바로\s*(오|와)')],
    },
}


def nfc(s):
    return unicodedata.normalize('NFC', s or '')


def load_run(run_dir):
    with open(os.path.join(run_dir, 'ledger.json'), encoding='utf-8') as f:
        ledger = json.load(f)
    record, opening, case = {}, '', None
    p = os.path.join(run_dir, 'record.json')
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f:
            record = json.load(f)
    p = os.path.join(run_dir, 'summary.json')
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f:
            s = json.load(f)
        case = s.get('case_id')
    p = os.path.join(run_dir, 'transcript.md')   # local_sim 대본 첫머리 '시작 정보: …'
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f:
            m = re.search(r'^시작 정보:\s*(.+)$', f.read(), flags=re.M)
        opening = m.group(1).strip() if m else ''
    return ledger, record, opening, case


def evaluate(case, ledger, record=None, opening=''):
    spec = CHECK[case]
    say_iv = [e for e in ledger if e.get('kind') == 'SAY' and not e.get('refused') and e.get('phase') in INTERVIEW_PHASES]
    say_ex = [e for e in ledger if e.get('kind') == 'SAY' and not e.get('refused') and e.get('phase') in EXPLAIN_PHASES]
    exams = [e for e in ledger if e.get('kind') == 'EXAM' and not e.get('refused')]
    qs = [nfc(e.get('text')) for e in say_iv]
    ans = [nfc(e.get('reply')) for e in say_iv]
    ex_txt = [nfc(e.get('text')) for e in say_ex]
    rec_txt = json.dumps(record or {}, ensure_ascii=False)
    out = {'case': case}
    hit = []
    for iid, label, qre, are, sre in spec['interview']:
        by = None
        if any(re.search(qre, q) for q in qs):
            by = 'q'
        elif are and any(re.search(are, a) for a in ans):
            by = 'a'
        elif sre and re.search(sre, nfc(opening)):
            by = 'start'
        hit.append({'id': iid, 'label': label, 'covered': bool(by), 'by': by})
    out['interview'] = hit
    out['exam'] = [{'id': i, 'label': l, 'covered': any(re.search(p, nfc(e.get('text'))) for e in exams)}
                   for i, l, p in spec['exam']]
    out['explain'] = [{'id': i, 'label': l, 'covered': any(re.search(p, s) for s in ex_txt)} for i, l, p in spec['explain']]
    saf = []
    for i, l, where, p in spec['safety']:
        src = {'q': qs, 'x': ex_txt, 'r': [rec_txt]}[where]
        saf.append({'id': i, 'label': l, 'covered': any(re.search(p, s) for s in src)})
    out['safety'] = saf
    for k in ('interview', 'exam', 'explain', 'safety'):
        n = len(out[k])
        c = sum(1 for x in out[k] if x['covered'])
        out[k + '_ratio'] = round(c / n, 3) if n else 0.0
        out[k + '_n'] = f'{c}/{n}'
    out['targets_met'] = {'interview>=0.80': out['interview_ratio'] >= 0.80, 'exam>=0.75': out['exam_ratio'] >= 0.75,
                          'explain=7/7': out['explain_n'] == '7/7' if len(spec['explain']) == 7 else None,
                          'safety=100%': out['safety_ratio'] == 1.0}
    out['turns'] = max([e.get('turn') or 0 for e in ledger] or [0])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True, help='local_sim 결과 폴더(ledger.json 포함)')
    ap.add_argument('--case', choices=sorted(CHECK), default=None)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    ledger, record, opening, case = load_run(a.run)
    case = a.case or case
    if case not in CHECK:
        m = re.search(r'(C0[13]|C10)', a.run)
        case = m.group(1) if m else None
    if case not in CHECK:
        sys.exit('증례(C01/C03/C10)를 --case로 지정하세요')
    res = evaluate(case, ledger, record, opening)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return res
    print(f"[{case}] turns={res['turns']} 문진 {res['interview_n']} ({res['interview_ratio']:.0%}) / 진찰 {res['exam_n']} "
          f"({res['exam_ratio']:.0%}) / 설명 {res['explain_n']} / 안전 {res['safety_n']}")
    for k in ('interview', 'exam', 'explain', 'safety'):
        miss = [f"{x['id']} {x['label']}" for x in res[k] if not x['covered']]
        if miss:
            print(f'  {k} 미충족: ' + ', '.join(miss))
    return res


if __name__ == '__main__':
    main()

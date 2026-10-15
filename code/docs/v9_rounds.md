# v9 라운드 기록 — CPX 은행 확장 · DDXPlus · 지침 체크리스트

작업 폴더 `code_v9/`(code_v8 복사본). 개발 키·공식 서버·로컬 LLM 시뮬레이션 **미사용**(사용자 지시). 검증은 단위 테스트 + 모의 LLM 드라이런 + zip 해제·import 확인만.

## 배경
v8(34턴) 샘플 77.79점 중 정보수집(12.49)이 가장 약하다. v8 문진 엔진은 16범주 은행 밖 주호소(숨은 증례)에서 범주를 못 찾아
`fatigue` 등 엉뚱한 은행으로 떨어졌다(예: 모의 '눈 충혈' → fatigue, '손가락 관절 부종' → edema). v9 목표: 국시 CPX 임상표현 수준
은행 + 은행 밖 주호소의 실행 중 체크리스트 생성.

## 변경점
### 1) CPX 체크리스트 은행 16 → 62범주 (896단위)
- 새 모듈 `agent/cpx_bank_a.py`·`cpx_bank_b.py`·`cpx_bank_c.py`(의학 지식으로 직접 작성, 시판 교재 문구 복제 아님). v8과 같은 스키마
  (core/red/hx/fh/sh, prio, safety, follow, isys, exams 7개=기존 EXAM_BANK id만).
- `cpx._load_ext()`가 v8 `CPX`에 합친다. v8 16범주 재정의 금지, v8 항목 id의 ITEM_Q·MENTION 덮어쓰기 금지, 모듈 import 실패 시 v8 은행으로 진행.
- 범주 목록(괄호=단위 수)
  - A 전신·호흡·ENT·심혈관·내분비·상담: general(범용 ROS 폴백 14), fever 16, rhinorrhea 16, sore_throat 16, hemoptysis 16, syncope 16,
    hypertension 16, dm 16, neck_mass 16, weight_gain 16, checkup 15, smoking_cess 15, alcohol 16, ear 14
  - B 소화기·비뇨·여성·유방: heartburn 15, vomiting 15, hematemesis 13, hematochezia 15, diarrhea 14, constipation 13, jaundice 15,
    hematuria 15, luts 14, menstrual 14, vag_bleeding 14, vag_discharge 15, pregnancy 15, breast_mass 16
  - C 신경·근골격·피부·정신·소아·예방: joint_pain 17, back_pain 15, neck_pain 15, rash 16, pruritus 14, seizure 16, weakness_numb 15,
    memory 16, confusion 15, tremor 15, anxiety 16, suicide 16, p_fever 13, p_seizure 12, p_gi 14, p_resp 15, p_dev 14, vaccination 13
  - v8 16범주(그대로): weight_loss, fatigue, palpitation, insomnia, substance, mood, headache, dizziness, chest_pain, dyspnea,
    cough_fever, abd_pain, gi, urinary, edema, growth
- 주호소 → 범주 매핑(`cpx.detect_all`·`resolve_categories`, `interview._intake_post`)
  - 접수 LLM 범주(확장 범주 설명 포함한 목록에서 고름) + v8 키워드 탐지 + v9 확장 키워드 탐지(뒤에 붙임 → v8 순서 보존). 여러 범주 동시 허용.
  - 세부 범주 우선(REFINES: 예 hematuria>urinary, hematemesis>gi, back_pain>msk), 은행 없는 포괄 범주(msk·skin·neuro)는 시작 정보
    단어로 세부 범주 삽입, 열만 있고 호흡기 단어 없으면 fever>cough_fever, 관절 단어가 있으면 joint_pain>edema.
  - 소아: 성인 범주 → 소아 범주(PEDS_MAP: fever→p_fever, vomiting·diarrhea→p_gi, seizure→p_seizure), 성인은 소아 전용 범주 제외.
    여성: 여성 전용 범주(menstrual, vag_bleeding, vag_discharge, pregnancy)는 남성에서 제외, 임신 범주면 공통 임신 질문 생략.
    고령(65세+): 낙상 질문 `el_fall` prio 2 추가.
  - 범주를 못 찾으면 성인은 `general`(cat_source=default) → 아래 3)의 보강 대상.
- 34턴 예산(개방 1 + 문진 17 + 진찰 7 + 설명 7 + 답 2)·compile/must 로직은 그대로. 확장 범주는 prio-1 증상 단위 ≤9.

### 2) DDXPlus 질환별 증상 KB
- `tools/build_ddx_kb.py`(zip 제외) → `agent/data/ddx_kb.json` 40KB: 49질환(영·한 이름·동의어), 213 evidence(한국어 질문 30자 이내·
  라벨·계통·위험징후·단계). 질문으로 만들 수 없는 10개 코드는 제외 사유 기록. 환자 파일 미포함.
- `agent/ddx.py`: `match(names)`(감별 후보 → 질환 id, 짧은 동의어 오탐 방지), `units(names, have_items, n, prio, pediatric, sex)`
  (위험징후 → 판별력(일부 후보에만 있는 증상) → 상위 질환 핵심 증상 순, 성별·소아 필터, 단일 항목 단위), 실패 시 [].
- `agent/data/LICENSES.md`: DDXPlus(Fansi Tchango et al., NeurIPS 2022 D&B, CC BY 4.0) 인용, 한국어 문구는 자체 번역·작성, 지침 본문 미포함 명시.

### 3) 은행 밖·빈약 주호소: 지침 → 실행 중 체크리스트 (`agent/glcheck.py`)
- 은행 강도: strong(v8 범주 또는 키워드로 잡힌 확장 범주) / medium(접수 LLM만 고른 확장 범주) / weak(general·기본값·은행 없음).
- **폴백 순서**: ① 진료지침 검색(guidelines.gather, 주호소+감별 상위 3, History·증상·감별·평가 섹션 최대 2문서 2,600자) → Doctor LLM 1회
  (low effort, max 3,000토큰, 남은 시간 ≥ WRAPUP_SECONDS+300초, CALL_RESERVE 유지) → JSON 항목 → check_question(30자·묶음)·
  validate_question(중복)·관련성(수치·소아 말투·계통 겹침)·bundle_violation 필터 → 단위. ② DDXPlus 판별 evidence. ③ 범용 ROS 은행.
- 등급: weak는 지침 prio 1(충분하면 범용 은행 앞 3개만 핵심), DDXPlus prio 1~2, medium은 prio 2. **strong은 LLM 호출 없음**,
  DDXPlus는 prio 3이고 `INTERVIEW_Q - 은행 단위 수`만큼(남는 슬롯)만 붙인다 → v8 필수 문항을 밀어내지 않음(테스트로 고정).
- 지침 발췌가 없으면 LLM을 부르지 않는다. 모든 예외는 내부에서 삼키고 []. weak일 때 접수 LLM 판별 문항도 다시 허용.
- 관련성 필터 메모: `cpx.relevant_question`의 계통 사전은 '시력이 떨어졌나요?'를 '떨'(떨림)로 신경계 오탐한다. glcheck에서는 질문 계통 중
  하나라도 범주 계통(은행·주호소·시작 정보·감별 문구)과 겹치면 통과(완전히 무관한 계통만 거름).
- prepare(): 기존 지침 제목 인덱스만(본문 미포함·미적재). DDXPlus KB는 첫 사용 시 lazy load.

## 검증
- `python -m pytest -q code_v9/tests`: **147 통과**(v8 111 유지 + test_v9 23 + test_v9_ddx 13).
  - 은행 스키마: 전 범주 모든 질문·후속·onset 30자 이내, bundle_violation 0, 범주 내 단위·항목 id 중복 0, 전역 단위 id 일관성,
    진찰 id 유효(6~8개), 확장 범주 DETECT·DESC 존재.
  - 매핑: C01·C03·C10 탐지 결과 v8과 동일, 키워드 예시 9종, 소아·성별 분기, 포괄→세부, 미지 주호소→general.
  - 지침 체크리스트: 위반 문항 필터, 지침 경로(LLM 1회·low), 지침 없음→LLM 미호출, LLM 예외·전체 예외→[], 시간 부족→LLM 미호출,
    strong→LLM 없음·DDXPlus 남는 슬롯만, medium 판정.
- 검증기 `scratchpad/v9/validate_bank.py`: cpx_bank_a/b/c 모두 ERRORS 0.
- **C01·C03·C10 순서 회귀**: 4모드(default·no_final_q·ask_all·llm_down) × 3증례 SAY/EXAM 순서가 v8과 **바이트 동일**(12/12).
- 모의 LLM 드라이런(`scratchpad/v9/dryrun_v9.py`, 가상 증례는 시작 정보만 직접 작성): FAILURES 0 — 예외 0, 거절 0, 34턴 이내,
  SAY 최대 30자, 자유 질문 묶음 위반 0. 핵심 항목 커버(질문 문구 정규식 기준, 지침 on):

| 증례(가상) | v8 주 범주 | v8 커버 | v9 주 범주 | v9 커버 | 턴/거절 |
|---|---|---|---|---|---|
| X1 요통 | 없음(legacy) | 5/6 (위반 1) | back_pain | 6/6 | 34/0 |
| X2 피부발진 | 없음 | 3/5 | rash | 4/5 | 34/0 |
| X3 혈뇨(68세) | urinary | 5/7 | hematuria | 7/7 | 34/0 |
| X4 실신 | 없음 (위반 1) | 5/7 | syncope | 6/7 | 34/0 |
| X5 손가락 관절통 | edema(오분류) | 2/6 | joint_pain | 6/6 | 34/0 |
| X6 무월경 | 없음 | 3/6 | menstrual | 5/6 | 34/0 |
| X7 눈 충혈(은행 없음) | fatigue | 0/6 | general+지침 5문항 | 4/6 (지침 없으면 0/6) | 34/0 |
| X8 2세 발열 | 없음 | 6/8 | p_fever | 8/8 | 34/0 |
| X9 쉰 목소리(은행 없음) | fatigue | 3/5 | general+DDXPlus 5문항 | 3/5 | 34/0 |
| C01/C03/C10 | — | — | v8과 동일 | — | 33~34/0 |

  LLM 장애 모드에서도 X1~X6·X8은 키워드 탐지로 같은 범주(X5는 관절 규칙으로 joint_pain), X7·X9는 general 범용 은행으로 진행.
- 개발 키 grep: zip 해제본에서 `NOVA_DEV_KEY`·키 형식 문자열 0건.

## 제출물
`제출/submission_v9.zip` — 28파일(run.py, requirements.txt, nova_sdk.py, agent/*.py 23, agent/data/LICENSES.md, agent/data/ddx_kb.json),
244,810바이트, sha256 `f7d61f3f791c01716ad297270a6c5aebeb078fabdda579ce3f94eb95fce74cec`. 슬래시 경로, tests·tools·__pycache__·지침 본문 없음.
빈 폴더에 zipfile로 풀어 `python -I`로 run·agent 전 모듈 import, `run.prepare()` 확인(62범주, 확장 3모듈 로드).

## 데이터 출처
- DDXPlus: Fansi Tchango A., Goel R., Wen Z., Martel J., Ghosn J. "DDXPlus: A New Dataset For Automatic Medical Diagnosis",
  NeurIPS 2022 Datasets and Benchmarks, CC BY 4.0. 질환–evidence 구조만 사용, 한국어 문구는 자체 번역.
- 진료지침: 운영진 제공 `/opt/nova/guidelines`를 실행 중 검색·발췌만(본문 zip 미포함, 변경본 배포 없음).
- CPX 은행 문항: 팀 자체 작성.

## 잔여 위험
- 실제 효과 미확인(리더보드·서버 미실행). 확장 은행 문구·kw 정규식은 실제 가상환자 답으로 검증되지 않음(v8 은행은 서버 실측 근거).
- 키워드 탐지 오탐 가능성(예: '열이 나요'+'기침'은 cough_fever 유지, '목이 아파요'는 sore_throat; 복합 주호소에서 주 범주 선택은 LLM 순서 우선).
- 지침 체크리스트는 실제 지침 발췌 품질·LLM 출력에 의존(모의 드라이런은 고정 JSON). 지침 검색이 엉뚱한 문서를 고르면 관련성 필터만이 방어선.
- DDXPlus 49질환은 호흡기·심혈관 편중, 질문 일부(예: '어린이집에 다니거나 근무하시나요?')는 한국 CPX 맥락에 어색. 주호소를 다시 묻는
  문항('목소리가 쉬거나 변했나요?')이 남을 수 있음.
- 소아 범주 일부 문구에 '입술'이 있어 자유 질문용 ADULT_PHRASE_RE(술)와 겹치나, 은행 문구는 화이트리스트라 영향 없음.
- breast_mass의 월경·수유 관련 prio 2~3 단위는 남성에서도 예산이 남으면 물을 수 있음.
- 범주 목록이 길어져 접수 LLM 프롬프트가 약 1KB 늘었음(토큰 영향 미미).

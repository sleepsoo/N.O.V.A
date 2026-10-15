# v7 설계서 — code_v6 기반 리더보드(sol) 대응판 (2026-10-14)

- 근거 분석: `code/docs/leaderboard_analysis.md`. 표식 [실측]/[추론]/[추측]은 분석서와 같다.
- 이 문서는 구현자가 그대로 따를 수준의 사양이다. 코드 스니펫은 계약(형식·정규식·프롬프트 문구)이 중요한 곳에만 넣었다.

## 0. 목표·원칙·범위

**목표**
- 리더보드(sol)와 최종 3채점기(sol·Claude·Gemini)에서 채점기에 관계없이 인정될 요소를 올린다.
- 샘플 검증(luna) 점수는 v6(81.3)보다 떨어뜨리지 않는다.

**원칙**
1. 문진 22, 진찰 11, 설명 상한 9(+환자 질문 답 ≤2), 총 42~44턴을 유지한다. 턴 소모 없는 변경을 우선한다.
2. 진단(dx) 호출 effort medium과 v6 안전 장치(KB must_say·add_safety_lines·safe_plan_line)는 그대로 둔다. 진단 15·안전 15 유지가 우선이다.
3. 기록 내용은 지우지 않는다. 중복과 잘못된 표기만 정리한다. v4의 claims 필터처럼 내용을 지워 정보수집이 폭락하는 일을 막기 위해서다.
4. 모든 변경은 `DEFAULTS` 플래그로 끌 수 있게 한다. `preset.json` 한 파일로 끄고 켜서 실험 zip을 만든다(C7).

**범위 밖**
- 문진 계획 프롬프트(plan_q)와 지침 발췌(guidelines.py)
- intake, Doctor effort 상향
- 턴 구조 변경. 턴 구조 변경은 리더보드 실험 변형(C7 프리셋)으로만 다룬다.

**작업 시작**
- `cp -r code_v6 code_v7`(runs·__pycache__ 제외)
- 바뀌는 파일: `run.py`, `agent/{interview,bank2,facts,assess,explain,note2,record,kb}.py`, `tests/test_v7.py`(신규)
- 그대로 두는 파일: `guidelines.py`, `llm.py`, `encounter.py`, `say.py`, `subjective.py`, `banks.py`, `util.py`, `nova_sdk.py`

## 1. 변경 요약

| ID | 영역 | 내용 | 파일·함수 | 턴 | sol 기대 [추측] | luna 영향 | 위험 | 우선 |
|---|---|---|---|---|---|---|---|---|
| C1 | 효율(비용) | Doctor 출력 −15~20%: facts 출력 배열 압축, say_fix LLM 기본 끔, plan_say 출력 축소, dx 개수 상한 | facts.extract, explain.plan_and_say·fix_say, assess.dx_and_assess | 0 | 효율 +0~0.5 | 0~+0.2 | facts 파싱 → 재시도 경로로 완화 | P0 |
| C2 | 정보·효율 | 진찰: 활력징후 항상 측정(11 안에서), 표 밖 `affect` 제외, 정신·물질 범주는 일반 진찰 후순위, 부위별 정렬 | interview.examine, bank2 | 0 | 정보 +0.1~0.6, 효율 +0.1~0.4 | 0 | 낮음 | P0 |
| C3 | 효율 | 문진: 범주별 시점·체중 슬롯 시작 정보 덮임, 포괄 질문 1회 제한, 이미 답한 주제 재질문 차단(대체는 은행 다음 순위, 22 유지) | bank2.COVER_RE, interview._valid·run | 0 | 효율 +0.1~0.4, 정보 −0.1~0 | ±0 | 문진 집합이 일부 바뀜 | P0 |
| C4 | 진단·검사 | A/P: 감별 4~5개(refs 필수, 환자 우려 포함, test·when), P.tests에 조건부 검사 자동 연결, P.추적 유형 정리와 의뢰 기준 필수, 처치 결정의 미평가 단정·활력 수치 반복 제거 | assess, explain.render_plan, record, kb | 0 | 진단 +0.2~0.7, 검사 +0.5~1.2 | 검사 +0~0.3 | 새 P 줄 안전 필터 필수 | P0 |
| C5 | 정보(기록) | S/O 기록: 설명 중 환자 질문을 사실·HPI에, hpi·'?' 사실 렌더, 고정 칸 승격, Others 중복 제거, '(?)' 정리, O 활력 한 줄 | run.finish_v2, facts, note2, record.write_objective | 0 | 정보 +0.1~0.3, 기록 오류 감소 | 0~+0.2 | 낮음 | P0 |
| C6 | 소통·효율 | 설명: SAY ②③④⑤⑦ 구체화, 슬롯 중복 제거, 마지막 질문 답 보장, FAQ 키 보강 | explain.plan_and_say·fix_say·explain_loop·answer | 0(드물게 +1) | 소통 +0.2~0.6, 효율 +0.2~0.4 | 0~+0.3 | 낮음 | P0 |
| C7 | 운영 | `preset.json` 오버라이드, 실험 프리셋 v7-lean·v7-wide | run.load_config | — | — | — | 없음 | P0 |
| C8 | 옵션 | facts effort low, dx low+승급, 은행 문구 2개(수술·입원 짝), cdgp 수첩 안내 | 각 파일, 기본 off | 0 | 불확실 | 불확실 | 중간 | P2 |

**기본안 합계 기대 [추측]**: sol 총점 +2~5(v6 추정 대비), luna −0.8~+1.5.

## 2. 상세 사양

### C1. Doctor 토큰 절감

#### C1-0. 호출별 사양과 목표

luna 실측은 v2c 계열 35회 평균이다(분석서 §4.2).

| tag | effort | max_tokens | v7 변경 | luna 출력 실측 → 목표 |
|---|---|---|---|---|
| intake | low | 6000 | 없음 | 233 → 230 |
| plan_q ×2 | low | 8000 | 없음(문진 보호) | 1,297 → 1,300 |
| exams | low | 6000 | 활력징후 고정으로 `need`가 줄어 호출 생략이 늘고, 프롬프트에 1문장 추가(C2) | 254 → 0~250 |
| facts | **medium 유지** | 8000 | 출력을 배열 압축(C1-a) | 1,991 → 1,000~1,200 |
| dx | **medium 유지** | 8000 | ICE·when 추가, 개수 상한(C1-d, C4) | 2,367 → 2,300~2,500 |
| plan_say | low | 8000 | 출력 축소(C1-b) | 1,718 → 1,100~1,300 |
| say_fix | low | 4000 | **기본 끔**(C1-c) | 673(23%만) → 0 |
| answer | low | 4000 | 없음 | 172(14%만) → 같음 |
| S-narr | low | 8000 | 규칙 2줄 추가(C5) | 793 → 800 |
| **합** | | | | **8,831(v6 추정 ~9.3k) → 7.0~7.6k, 호출 8.4 → ~8.0** |

- 입력은 18~21k로 거의 그대로다. 지침 발췌는 문진·진단 품질 근거여서 줄이지 않는다.
- 입력 단가는 출력의 1/5이고, 사용량이 효율을 좌우한다는 근거가 약하다(분석서 §4.4).

**정확도 안전장치**
- dx·facts effort는 바꾸지 않는다.
- facts는 형식만 바꾸고 품질 게이트를 둔다(C1-a).
- dx 출력 스키마는 필드 추가만 한다. 기존 필드 의미는 그대로다.
- `llm.ask`의 길이·빈 답 재시도와 `MIN_TOKENS` 하한은 그대로 둔다.

#### C1-a. facts 출력 배열 압축 (`agent/facts.py`)

- 근거: 사실 38개가 JSON 3,625자 대 압축 940자였다 [실측]. luna facts 출력은 대부분 보이는 JSON이다.
- `extract()`의 출력 지시 한 줄을 다음으로 바꾼다. 나머지 규칙 문구는 v6 그대로다.
  ```
  출력: {"f": [[턴, "영역", "고정키", "항목", "극성", "세부"], ...]}
  - 사실 하나당 배열 하나. 고정키가 없으면 "". 극성은 "+", "-", "?" 중 하나. 설명·주석·다른 키 금지.
  ```
- `ask_json` validate: `isinstance(v.get('f') or v.get('facts'), list) and len(v.get('f') or v.get('facts')) > 0`
- 새 함수 `_rows_from(res) -> list[dict]`
  - 배열 행 `[t, s, k, l, p, d]`는 `{'turn','sec','key'(빈 값이면 'other'),'label','pol','detail'}`로 바꾼다.
  - dict 행(모델이 객체로 답한 경우)은 그대로 받는다.
  - 길이가 5 미만인 행은 버린다.
- 이어서 기존 `validate(enc, rows, raw)`를 그대로 적용한다.
- **품질 게이트**
  - `n_ans` = qa_rows 중 답이 비지 않은 행 수
  - `len(facts) < max(3, n_ans // 2)`이면 v6의 객체 형식 프롬프트로 1회 재시도한다. 로그 태그는 `facts-json`.
  - 재시도도 실패하면 기존 `fallback()`
- 플래그: `FACTS_FORMAT='compact'`(기본) | `'json'`(v6 동작)

#### C1-b. plan_say 출력 축소 (`agent/explain.py: plan_and_say`)

[P 규칙] 줄을 바꾼다. 문구는 그대로 쓴다.

- tests
  ```
  - tests: 3~7줄 {"name","reason"}. name은 구체 항목(같은 계열은 한 줄로 묶기, 예: "혈액 : CBC, ESR/CRP, 전해질, AST/ALT, BUN/Cr, 공복혈당/HbA1c"),
    reason은 15자 이내 목적. 증상별로 교정 가능한 원인 검사를 포함. 감별진단의 감별 검사와 일치시킬 것.
    결과에 따라 하는 검사는 name 앞에 "(조건부)"를 붙이고 reason에 시행 조건.
  ```
- treatment
  - KB가 맞으면(`k` 있음): `- treatment: [] (약물 치료는 지식표가 정함). 환자 요청에 대한 결정이 필요하면 그 1줄만.`
  - KB가 없으면 v6 문구 그대로
  - 근거: render_plan은 KB가 맞으면 LLM 치료 줄을 버린다. 지금은 버릴 줄을 생성하고 있다.
- follow_up
  ```
  - follow_up: "재진 : 기간 — 확인할 항목", "모니터링 : 간격 — 항목"(치료를 시작할 때), "의뢰 기준 : 어떤 결과·증상이면 어느 진료과",
    "즉시 내원 : 구체적 경고 증상 4개 이상". 이상 진찰 소견(예: 안구돌출, 근력 저하)은 모니터링 또는 의뢰 기준에 반영.
  ```
- education: `- education: 이번 설명(SAY)에 넣지 못한 핵심 최대 3개(짧게).`
- [FAQ]
  - 요청 키 = `[prognosis, serious, treatment, duration, lifestyle]` − KB faq에 이미 있는 키, 요청이 있으면 `prescribe` 추가
  - 답은 "22자 이내"
  - 요청 키가 없으면 FAQ 지시와 출력 키를 아예 뺀다.
- 출력 JSON 키는 v6과 같다. 파싱 코드는 바꾸지 않는다.

#### C1-c. say_fix 결정적 처리 (`explain.fix_say`)

- `cfg['SAY_FIX_LLM']`이 0(기본)이면 LLM 재작성 블록을 건너뛴다.
  - 규칙 위반 문장은 다음 루프에서 버려진다(v6 코드가 이미 함).
  - v2c 계열 luna 35회 중 8회(23%)에서 say_fix가 0.3~1.2k 출력을 썼다 [실측].
- 버린 뒤 본문(되말하기·마지막 질문 제외)이 `EXPLAIN_N − 3`개 미만이고 KB가 있으면 KB `say` 문장으로 채운다.
  - 조건: `safe_say` 통과, 기존 문장과 `is_similar < 0.5`, 슬롯(C6-b) 중복 아님
  - 채우는 한도: `EXPLAIN_N − 2`
- 그래도 유효 문장이 4개 미만일 때만 LLM say_fix를 1회 호출한다(`SAY_FIX_LLM`과 무관한 안전망).

#### C1-d. dx 출력 상한 (`assess.dx_and_assess`)

- 프롬프트 문구를 다음으로 바꾼다.
  - "후보 3~4개" → "후보 3개"
  - "[근거] 4~6개" → "[근거] 4~5개"
  - 각 text·reason에 "70자 이내" 추가
  - 감별은 C4-a 규칙
- 출력 필드는 추가만 한다(`when`). `candidates`는 막연한 진단 대체용으로 유지한다.

#### C1-e. (옵션, 기본 off) 공격적 절감 — C8

- `EFFORT_FACTS='low'`: −0.3~0.6k 추정. luna low의 추출 정확도는 실측이 없다.
- `DX_ESCALATE=1`: dx를 low로 먼저 부른다. 다음 중 하나면 medium으로 다시 부른다. −0.8~1.2k 추정. 진단 정확도 위험이 있다.
  - 막연한 진단(`VAGUE_DX_RE`)
  - `confidence < 0.75`
  - 후보 1·2위의 for−against 차이 ≤ 1
- 둘 다 샘플 검증 2회 이상으로 진단 15·정보 유지가 확인되기 전에는 리더보드에 쓰지 않는다.

### C2. 진찰 세트 교정 (`agent/interview.py: examine`, `agent/bank2.py`)

근거
- 활력징후 직접 측정이 없으면 9/31이 행을 불인정했다. 공개 표 3/3에 행이 있고 매칭은 52/52다. v3 계열 18건은 모두 측정했는데, 측정이 효율 감점 사유가 된 적은 0/18이다 [실측].
- 표 밖 `기분·정동 평가`는 C01에서 분자에 들어가지 않았다 [실측].
- C01에서 sol은 복부·하지·결막을 금단 관련 진찰보다 낮은 우선순위로 지적했다 [실측].

1. **활력징후 고정**
   - `always = ['vitals', 'general'] + (['anthro'] if peds else [])`. `cfg['EXAM_VITALS']=1`이 기본이다.
   - `has_vs` 생략 조건(400~401행)과 `(i == 'vitals' and has_vs)` 제외(421행)를 없앤다.
   - 총수 `EXAM_N=11`은 그대로라서 우선순위 최하위 1개가 빠진다(턴 불변).
2. **표 밖 진찰 제외**
   - `deny = set(cfg.get('EXAM_DENY', 'affect').split(','))`
   - `floor`·`allowed`·`order`·`rest`에서 deny id를 뺀다.
   - `bank2.CATEGORY_EXAMS['mood']`에서도 `'affect'`를 지운다. 그러면 mood 범주 앞 2개가 `mental`, `insight`가 된다(C01 표에 '병식 평가' 있음).
3. **정신·물질 범주 공통 행 순서**
   - `bank2`에 다음을 추가한다.
     ```python
     PSYCH_EXAM_CATS = {'insomnia', 'substance', 'mood', 'memory'}
     CORE_FILL_PSYCH = ['vitals', 'general', 'mental', 'heart', 'lung', 'thyroid', 'conj', 'chest_insp',
                        'abd_palp', 'abd_insp', 'liver_spleen', 'periph']
     ```
   - `examine`의 `order` 마지막 보충과 `menu_ids`에 쓰는 `bank2.CORE12`를, 범주가 PSYCH_EXAM_CATS와 겹치면 `CORE_FILL_PSYCH`로 바꾼다. 다른 범주는 `CORE12`를 그대로 쓴다.
   - exams LLM 시스템 프롬프트 끝에 1문장을 추가한다: "정신·수면·약물 관련 증례에서는 복부·하지 진찰보다 그 증상과 관련된 신경·자율신경 진찰을 먼저 고르세요."
4. **부위별 정렬** — sol C10 "진찰 순서가 분산되어 체계적인 부위별 진찰보다 비효율적" 대응
   - 기존 `order`를 만든 뒤 `head = order[:total]`, `tail = order[total:]`로 나눈다.
   - `head`를 다음 키로 안정 정렬한다. `tail`은 거절이 났을 때의 예비이고 순서를 바꾸지 않는다.
     ```python
     rank = {s: i for i, s in enumerate(record.SECTION_ORDER)}
     head.sort(key=lambda i: (0 if i == 'vitals' else 1 if i == 'general' else 2,
                              rank.get(banks.EXAM_BY_ID[i][2], 99)))
     order = head + tail
     ```
   - 실행 루프는 v6 그대로다. 거절도 `done += 1`, 블랙리스트 처리도 같다.
5. **문구**: 모두 `banks.EXAM_BANK`의 표 행 이름 문구를 쓴다. 자유 문구는 금지(v6과 같음).
   - 서버 매칭 실측: 활력 52/52, 외관 70/70, 의식 36/36, 결막 28/28, 폐 52/52, 심음 58/58, 복부 촉진 43/43, 하지 21/21, 갑상선 57/57
   - `흉곽 시진`·`복부 시진`은 서버 미검증이다 [추측: 행 이름과 같아 매칭].

**드라이런 기대**(test_v2 가짜 서버)
- C01: `vitals, general, orthostatic(V/S), …, insight` 포함, `affect` 없음
- C10: `vitals, general, radial, skin_temp, eye_signs, thyroid, thyroid_bruit, …`
- 셋 모두 진찰 11

### C3. 문진 중복·재질문 정리 — 문진 22 유지 (`agent/bank2.py`, `agent/interview.py`)

근거
- 시작 정보 재질문 10/31: C03 "언제부터 작다는 말을 들었나요?"는 시작 정보에 "일 년 전부터"가 있었다.
- 중복 질문 18/31, 포괄 질문 반복 12/31 [실측]
- 반대로 9/31은 시작 정보만 옮긴 사실을 불인정했다. 그래서 **시작 정보에 그대로 적힌 시점·체중 수치만** 덮고, 경과(`hpi_course`)는 덮지 않는다. C10 "계속 빠짐"은 대본 사실이다.

1. `bank2.py`: `COVER_RE`를 보강한다. 기존 키는 덮어쓰지 않는다(`setdefault`).
   ```python
   ONSET_SLOTS = ('gr_noticed', 'pf_duration', 'cf_duration', 'pr_duration')   # '언제부터'형 범주 슬롯
   for _s in ONSET_SLOTS:
       COVER_RE.setdefault(_s, COVER_RE['hpi_onset'])
   WEIGHT_CHANGE_RE = r'(키로|킬로|kg|㎏).{0,25}(빠|늘|줄|쪘|찌)|(빠|늘|줄|쪘|찌).{0,12}(키로|킬로|kg|㎏)'
   for _s in ('gr_weight', 'ft_weight'):
       COVER_RE.setdefault(_s, WEIGHT_CHANGE_RE)
   ```
   - `Checklist.__init__`이 `cover_hits(opening)`으로 덮인 슬롯을 뺀다(기존 메커니즘). 첫 질문은 `ranked[0]`로 넘어간다.
2. `interview._valid()`: 포괄 질문을 1회로 제한한다.
   ```python
   GENERIC_Q_RE = re.compile(r'(다른|그\s*밖에|또\s*다른|그\s*외).{0,8}(불편|증상|문제|이상)')
   if GENERIC_Q_RE.search(q) and any(GENERIC_Q_RE.search(a) for a in enc.asked): reject('generic_repeat')
   ```
3. `interview.run()`: 이미 답한 주제는 free 질문으로 다시 묻지 않는다.
   - 대상: LLM free 질문 중 존재형 질문만. 의문사 `얼마나|언제|어떻게|몇|어디|무슨|어떤`이 없고 `(있|없|나요|세요|가요)\?$`로 끝나는 질문이다.
   - 판정: 그 주제가 **이전 환자 답(또는 시작 정보)에 실제로 나왔으면** 건너뛴다. 묻기만 하고 답이 다른 데로 샌 주제는 허용한다(v6 시뮬 C10 숨참 사례).
     ```python
     TOPIC_RE = {'dyspnea': r'숨\s*(이\s*)?차|숨참|호흡\s*곤란', 'chest': r'가슴.{0,3}(통증|아프|아픔)|흉통',
                 'palp': r'두근|심장이\s*(빨리|뛰)', 'weight': r'체중|살이|몸무게', 'sweat': r'땀|발한',
                 'fever': r'열이|발열|오한', 'sleep': r'잠을|잠이|수면|불면', 'mood': r'기분|우울',
                 'bowel': r'대변|변이|설사|변비', 'urine': r'소변|배뇨', 'menses': r'생리|월경',
                 'headache': r'두통|머리가?\s*아', 'dizzy': r'어지', 'tremor': r'떨리|떨림', 'appetite': r'입맛|식욕|식사량'}
     answered = {t for t, p in TOPIC_RE.items() if re.search(p, enc.opening)} | \
                {t for e in enc.ledger if e['kind'] == 'SAY' and not e.get('refused')
                   and e.get('phase') in ('first', 'interview', 'ice') for t, p in TOPIC_RE.items()
                   if re.search(p, e.get('reply') or '')}
     ```
   - free 질문의 주제가 `answered`에 있으면 `log('q skipped (topic answered)')` 후 건너뛴다. 빈자리는 기존 묶음 루프가 `cl.ranked()` 다음 순위로 채운다.
   - 플래그 `TOPIC_GUARD`(기본 1)로 끌 수 있게 한다(C7).
4. 불변식(테스트로 고정): 공개 3증례 드라이런에서 문진 수 22(첫 질문·ICE 포함), C03에 `gr_noticed` 질문 없음.

### C4. A/P 템플릿 보정 (턴 소모 0)

모범 기록 형식에 맞춘다: 감별 "r/o X : 근거 → 가능성. 감별 검사", P "구체 검사 묶음, 재진·간격·의뢰 기준·즉시 내원".

#### C4-a. dx 프롬프트·파싱 (`agent/assess.py: dx_and_assess`)

- ICE를 입력에 넣는다.
  - `ice = [f"{e['text']} → {e['reply']}" for e in enc.ledger if str(e.get('qid','')).startswith('ice') and e.get('reply')]`
  - 사실표 다음 줄에 추가: `f"환자 걱정·기대(ICE): {ice or '없음'}\n"`
- `[감별]` 문단(116행)을 다음으로 바꾼다.
  ```
  [감별] 4~5개. ①주진단과 가장 헷갈리는 질환 ②환자가 걱정한 질환이 있으면 반드시 포함(dx 끝에 "(환자 우려)")
   ③체중 감소·피로처럼 비특이 주호소면 소모성 질환 또는 정신과적 원인 1개 이상.
   각 항목은 사실표·진찰 소견에 지지(for) 또는 반대(against) 근거가 있어야 함(refs 필수). 관련 문진을 하지 않아 근거가 없는 질환은 넣지 말 것.
   reason: '지지 … / 반대 … → 가능성 낮음|중간|배제 어려움' 형식 70자 이내. test: 이 감별을 가르는 검사 1~2개(구체 항목명).
   when: test가 처음부터 할 기본 검사면 "기본", 결과에 따라 하는 검사면 시행 조건(예: "TRAb 음성·불명확 시").
  ```
- 출력 스키마의 differential 항목을 `{"dx","reason","refs","test","when"}`로 바꾼다.
- 파싱
  - `when`을 보존한다.
  - `concern = '(환자 우려)' in name`
  - refs가 비고 concern도 아니면 버린다(로그). concern이면 refs가 비어도 둔다. ICE 질문 턴은 사실표에 ice 사실로 있다.
  - 상한은 `diffs[:4]` → `diffs[:cfg['DX_DIFF_N']]`(기본 5).

#### C4-b. A칸 렌더 (`assess.render_assessment`)

```python
s = f"r/o {d['dx']} : {reason}{_turns(d['refs'], ids)}"
if d.get('test') and d['test'] not in reason:
    w = (d.get('when') or '').strip()
    s += f". 감별 검사 : {d['test']}" + (f" ({w})" if w and w != '기본' else '')
```

#### C4-c. P칸 렌더 (`explain.render_plan`)

1. **감별 검사 → P.tests 연결**
   - 기존 검사 보충 루프 뒤에 넣는다.
     ```python
     for d in (getattr(enc, 'assess', None) or {}).get('differential') or []:
         t = (d.get('test') or '').strip()
         if not t or _test_covered(t, tests):
             continue
         w = (d.get('when') or '').strip()
         name = re.sub(r'\s*\(환자 우려\)', '', d['dx'])
         line = f"{t} : {name} 감별" if (not w or w == '기본') else f"(조건부) {t} : {w} — {name} 감별"
         tests.append(drug_to_class(line))
     tests = dedup_lines(tests)[:8]
     ```
   - `_test_covered(t, lines)`
     - 토큰: `re.findall(r'[A-Za-z][A-Za-z0-9\-/]+|[가-힣]{2,}', t)`
     - 불용어 제외: `{'검사','혈액','혈액검사','기능','기능검사','확인','측정','선별','필요','경우','결과'}`
     - 남은 토큰 중 하나라도 `'\n'.join(lines)`에 있으면(영문은 대소문자 무시) covered
     - 남은 토큰이 없으면 covered로 본다.
   - v6 버그 수정: 말로 설명한 검사 보충 루프에서 소변 검사의 존재 판정을 `r'소변'`으로 넓힌다(C01 시뮬 "소변검사 : 진료 중 설명한 검사" 중복).
2. **P.추적 유형 정리**
   - 줄마다 유형을 다음 순서로 판정한다.
     - 즉시 내원: `즉시|바로|응급`
     - 조기 연락: `조기\s*연락`
     - 의뢰 기준: `의뢰|전원|협진`
     - 재진: `재진|재방문|결과\s*(확인|보러)|후\s*외래`
     - 모니터링: `모니터링|간격|마다|추적`
   - 유형별로 가장 긴 줄 1개만 남긴다.
   - 출력 순서: 재진 → 모니터링 → 의뢰 기준 → 조기 연락 → 즉시 내원. 미분류 줄은 모니터링 뒤에 최대 1줄.
   - 접두가 없으면 `유형 : `을 붙인다.
   - **의뢰 기준 보장**(`FU_REFER=1`): 없으면 아래 순서로 넣는다.
     1. `k['refer_if']`(C4-e)
     2. 범용 문장: `f"의뢰 기준 : 검사 이상·증상 악화·치료 반응 부족 시 {spec or '해당 전문과'} 의뢰"`. `spec`은 disposition·KB 문장에서 `([가-힣]{2,8}과)`로 찾은 첫 진료과다.
   - 기존 즉시 내원 보장과 `early_contact` 삽입은 유지한다.
3. **처치 결정** — 아래 순서대로 처리한다.
   1. 활력 요약 `vs = vitals_assessment(enc, short=True)`(C4-d). 수치 전체는 O칸에 있으므로 P에 다시 쓰지 않는다. 불안정이면 v6 긴 문장을 그대로 쓰고 2~3은 건너뛴다.
   2. 첫 줄이 `활력징후`로 시작하면(예: graves KB) 앞 구절 `활력징후[^,]*,`를 `f'{vs}, 확인된 진찰 소견상'`으로 바꾼다.
      예: "활력징후 대체로 안정(빈맥 102회/분), 확인된 진찰 소견상 갑상샘중독발증 징후 없어 현재 외래 추적이 적절하며 …"
   3. 그 밖의 줄에 `soften(line, enc)`를 적용한다.
      - `'의식 명료'`가 있고 `'mental' not in enc.done_exams`면 그 구절을 지운다.
      - `(징후|소견)\s*(이|가|는)?\s*없(어|음|고)`가 있으면 앞에 `확인된 활력징후·진찰 소견상 `을 붙인다.
      - 그다음 맨 앞에 `vs` 한 줄을 넣는다.
   4. 입원 판단 문장(`입원.{0,6}(필요|불필요|고려)`)이 하나도 없으면 v2c 형식으로 덧붙인다: `f"현재 외래 추적이 적절하며 {admit_if or '활력징후 불안정·증상 급격한 악화'} 시 입원 고려"`. "입원 불필요" 단정은 쓰지 않는다.
   - `add_safety_lines`는 `'외래 추적이 적절'` 문자열로 위치를 찾으므로 이 처리 뒤에도 동작한다(테스트 T10).

#### C4-d. 활력 요약 (`record.vitals_assessment(enc, short=False)`)

- `short=True`면 다음을 돌려준다.
  - 안정: `'활력징후 대체로 안정' + (f"({', '.join(abn)})" if abn else '')`
  - 불안정: `f"활력징후 불안정({', '.join(abn)}) — 응급 평가 필요"`
- 기본값(`False`)은 v6 문장 그대로다. plan_say 프롬프트와 `finalize_plan`이 쓴다.

#### C4-e. KB 보강 (`agent/kb.py`)

- 22개 항목 모두에 `'refer_if'`를 추가한다. 용량·성분명은 금지한다. 예:

| id | refer_if |
|---|---|
| graves | 안병증 악화(시력 저하·복시)는 안과, 확진·약물 부작용·조절 실패는 내분비내과 |
| hypothyroid | 임신 계획·심질환 동반·조절 실패 시 내분비내과 |
| sedative_ud | 금단 경련·섬망 병력, 외래 감량 실패, 자해 위험 시 정신건강의학과 우선 의뢰(입원 해독 고려) |
| cdgp | 성장속도 연 4cm 미만으로 감소, 골연령·선별검사 이상 시 소아내분비 |
| t2dm | 매우 높은 혈당·케톤·합병증 의심 시 내분비내과 |
| ida | 위장관 출혈 의심·치료 반응 없음 시 소화기내과(월경과다는 산부인과) |
| migraine | 신경학적 이상·두통 양상 급변 시 신경과 |
| pneumonia | 저산소·호흡곤란 악화·치료 반응 없음 시 호흡기내과 또는 입원 |

- 나머지 항목도 같은 형식(조건 → 진료과)으로 쓴다.

#### C4-f. 기록 마감 정리 (`record.polish_note(enc, note)`, 신규)

- `submit()` 첫머리에서 `add_safety_lines` **다음**에 try로 호출한다. 두 기록 경로(finish_v2·finish)에 공통이다.
- P 각 칸(education 제외)에 `explain.dedup_lines`를 적용한다. 순환 import를 피하려고 함수 안에서 지역 import한다.
- disposition에서 `mmHg`가 든 줄이 O칸 V/S와 같은 수치를 반복하면 지운다.
- S의 pmh·fh·sh·ros 칸은 `_clean_others`(C5-c)로 정리한다.

### C5. S/O 기록 위생

#### C5-a. 설명 중 환자 질문 기록 (`run.finish_v2`, `agent/facts.py`, `agent/note2.py`)

- 근거: 서버 실행본 누락 7건 중 6건이 설명 단계 환자 질문·기대였다 [실측, record_coverage B].
- facts 추출은 설명 단계 **전**에 돌므로 LLM 재추출 대신 결정적으로 붙인다.
- `facts.late_questions(enc) -> list[dict]`(신규)
  - 대상: phase가 `explain`·`explain-answer`인 원장 행 중 환자 답이 질문 꼴인 것(`\?|까요|나요|건가요|되나요|어떻게|언제|얼마나`)
  - 의사 문장이 되말하기(`'바로 오셔야 할 증상 하나를 말씀해 보세요.'`)인 행은 제외한다.
  - 사실 형식: `{'turn','sec':'ice','key':'other','label':'설명 중 질문','pol':'?','detail': 답[:30]}`
  - 증상 진술은 넣지 않는다. 되말하기 답의 경고 증상이 양성 증상으로 잘못 기록되는 것을 막기 위해서다.
- `run.finish_v2`: S 작성 전에 `cfg['LATE_Q_FACTS']`이면 `enc.facts += facts.late_questions(enc)`(id 재부여)
- `facts.qa_rows(enc, include_late=False)`에 인자를 추가하고, `note2.write_s_narrative`만 `include_late=True`로 부른다. 같은 질문 판정을 쓴다.
- `note2.write_subjective`: hpi 작성 뒤, sec가 ice인 사실 중 detail 앞 8자가 hpi에 없는 것을 최대 3개 모아 `걱정·궁금증 : a; b; c` 한 줄로 덧붙인다.

#### C5-b. `note2.render_fixed` 보충 규칙

1. **hpi 사실**: 극성 +/−이고 라벨이 S 어디에도 없으면 ROS Others에 보충한다.
   - `f['sec'] in ('ice','hpi')` 건너뛰기에서 hpi를 뺀다. ice는 C5-a가 처리한다.
   - 섹션 대응 dict에 `'hpi': 'ros'`를 추가한다.
2. **극성 '?' 사실**: detail이 있으면 모든 섹션에서 `라벨 : detail`로 보충한다. 지금은 fh만 한다.
   - 조건을 `if f['pol'] not in '+-' and not f.get('detail'): continue`로 바꾼다.
   - 중복 판정은 해당 칸이 아니라 **S 전체 텍스트**(`s_text`)로 한다. HPI에 이미 있는 내용이 Others에 다시 들어가는 것을 막기 위해서다.
3. **고정 칸 승격**: 렌더 전에 key가 `other`인 사실의 라벨이 아래 패턴과 앞부분이 맞으면 key를 고정 키로 바꾼다.
   - 조건 ①: 그 턴 문답에 `bank2.FIXED_KEYS[key]` 어휘 단서가 있어야 한다(validate와 같은 검사).
   - 조건 ②: 극성 '−'이면 라벨에 한정어 `(심한|자주|최근|증가|감소|악화|야간|운동\s*시|계단|안정\s*시)`가 없어야 한다. "심한 두통(−)→Headache(−)" 기록 오류를 막기 위해서다.
   ```python
   PROMOTE = [('ros.Chest pain', r'^(흉통|가슴\s*(통증|아픔))'), ('ros.Palpitation', r'^(두근|심계)'),
              ('ros.Headache', r'^두통'), ('ros.Dizziness', r'^어지럼'), ('ros.Fever', r'^(발열|열)$'),
              ('ros.Diarrhea', r'^설사'), ('ros.Constipation', r'^변비'), ('ros.Nausea', r'^(구역|메스꺼움)'),
              ('ros.Vomiting', r'^구토'), ('ros.Abdominal pain', r'^복통'), ('ros.Melena', r'^(흑변|검은\s*변)'),
              ('ros.Hematochezia', r'^혈변'), ('ros.Fatigue', r'^(피로|피곤)'), ('ros.Cough', r'^기침'),
              ('ros.Sputum', r'^가래'), ('pmh.heart_disease', r'^심장(병|\s*질환)'), ('pmh.op_hx', r'^수술'),
              ('pmh.allergy', r'^(약\s*)?알레르기')]
   ```

#### C5-c. Others 정리 (`note2`, `record.polish_note`)

- `_clean_others(text)`: `Others : ` 뒤 항목을 `, `로 나눈다.
  - `(?)`·`( ? )`를 ` : `로 바꾼다. 예: "배변 횟수 (?) 하루 2~3번" → "배변 횟수 : 하루 2~3번"
  - 정규화(공백·기호 제거) 뒤 다른 항목에 포함되거나 `util.similarity ≥ 0.7`인 항목은 긴 쪽만 남긴다. 예: "모친 갑상샘 저하증 (+)"와 "모친 갑상샘 질환(+, 어머니 갑상샘 저하증)"
  - Medicine history 칸과 같은 내용의 pmh Others 항목(`복용약(-)`, `영양제(-)`)을 지운다.
- `write_s_narrative` 규칙에 2줄을 추가한다.
  ```
  - 음성 소견은 물은 범위 그대로(예: '물 섭취 증가(-)'≠'갈증(-)', '심한 두통(-)'≠'두통(-)', '최근 몇 달 성관계 없음').
    '(?)' 표기 금지 — 수치·서술은 '항목 : 세부'.
  - 같은 사실을 여러 칸에 반복하지 말 것(과거력·가족력 Others 중복 금지).
  ```

#### C5-d. O칸 활력 한 줄 (`record.write_objective`)

- `qid == 'vitals'` 진찰 결과의 숫자 집합(`util.extract_numbers`)이 시작 정보 활력 숫자의 부분집합이면 한 줄로 쓴다. vitals 진찰 항목은 V/S에 다시 덧붙이지 않는다.
  - `V/S : {vitals_line} (턴 n 측정, 시작 정보와 같음)`
- 다르면 v6처럼 두 값을 모두 쓴다.

### C6. 설명·응답 (`agent/explain.py`)

#### C6-a. SAY 슬롯 문구 (`plan_and_say` [SAY 규칙])

①⑥은 그대로 두고 아래만 바꾼다.

```
 ②원인·기전을 환자 말로, 환자 증상 1~2개와 연결(예: '면역 이상으로 갑상샘 호르몬이 넘쳐 살이 빠져요')
 ③환자 걱정·궁금증에 직접 답 + 그렇게 판단한 근거 소견 1개(예: '목이 붓고 눈이 나와 암보다 갑상샘 병이에요');
   걱정이 없었으면 생활 수칙 1문장
 ④검사 이름과 그 검사로 무엇을 확인하는지(예: '피검사로 호르몬과 원인 항체를 확인해요')
 ⑤치료 선택지(계열명)와 결정 시점, 또는 대표 부작용이 생기면 할 행동(예: '약 먹다 열·목 아프면 멈추고 바로 연락하세요')
 ⑦재진 시점과 그때 볼 것(예: '1~2주 뒤 결과 보러 다시 오세요')
```

- 근거: sol 소통 감점 빈도는 기전 19, 선택지 20, 걱정 근거 13, 검사 목적 12(/31) [실측].
- 안전 필터(`SAY_BAD_RE`, `safe_say`)는 그대로 거친다. ⑤의 "멈추고 바로 연락"은 KB graves say에 이미 있는 문장형이다.

#### C6-b. 슬롯 중복 제거 (`fix_say`)

- 근거: 설명 반복 20/31. C01 감량 문장 3개 [실측].
- `good`을 만든 직후, must_say 삽입 **전**에 적용한다.
  ```python
  SLOT_RES = [('warn', saymod.WARN_RE), ('follow', saymod.FOLLOWUP_RE), ('test', saymod.TEST_RE),
              ('taper', re.compile(r'(천천히|서서히|조금씩)\s*줄|급히\s*끊|바로\s*끊|혼자\s*끊|갑자기\s*끊'))]
  def _slot(s): return next((n for n, r in SLOT_RES if r.search(s)), '')
  must_slots = {_slot(sent) for _, sent in (k or {}).get('must_say') or []} - {''}
  ```
  - LLM 문장의 슬롯이 `must_slots`에 있으면 버린다. must_say가 그 자리를 채운다.
  - 같은 슬롯(warn·follow·test·taper)은 첫 문장만 남긴다.
  - 슬롯이 없는 문장(진단·기전·걱정·치료)은 v6처럼 `is_similar 0.6`으로만 거른다.

#### C6-c. 마지막 질문 답 보장 (`explain_loop`)

- 근거: 마지막 질문 미응답 4/31. v2c C01 서버에서 폴백 문장이 무응답이었다 [실측].
- 동작
  - `final_i` = 마지막 줄이 `saymod.QUESTION_LINE`이면 그 인덱스
  - 중간 질문의 답 상한은 `ANSWER_MAX − 1`(기본 1), 마지막 질문은 `ANSWER_MAX`(기본 2)
  - 남은 턴 조건은 `enc.turns_remaining >= len(rest) + 1`
  - 결과적으로 설명 최대 턴은 v6과 같다(9 + 2).
- FAQ 키: `FAQ_KEYS['serious']`에 `해로|해롭` 추가. "계속 먹으면 해로울까요?"가 FAQ에 걸리게 한다.
- `answer()` 폴백
  - FAQ 값 → 주제별 기본 답 → 기존 문장 순서
  - 주제별 기본 답(모두 `say_problem` 통과 확인):
    ```python
    TOPIC_FALLBACK = {'serious': '검사로 확인하고 결과를 자세히 알려 드릴게요.',
                      'treatment': '검사 결과를 보고 치료 방법을 같이 정해요.',
                      'tests': '피검사 결과로 원인을 확인할 거예요.',
                      'results': '결과는 다음 진료 때 함께 봐요.',
                      'prognosis': '치료 반응을 보며 같이 관리해 갈게요.',
                      'lifestyle': '규칙적으로 자고 무리하지 않는 게 좋아요.'}
    ```

#### C6-d. (옵션, 미검증) 공감 문장

- 서버가 첫 질문 앞의 공감 문장을 잘라 effective_content에서 빠진다 [실측, probe].
- 평서문은 잘리지 않는 것으로 관찰됐다 [실측: '-고' 평서문 통과].
- ③ 문장을 "걱정 많으셨을 텐데"로 시작하는 한 문장 평서형으로 하는 방안은 서버 절단 규칙이 미검증이라 기본에서 뺀다.

### C7. 설정·실험 프리셋 (`run.py`)

- `DEFAULTS`에 추가한다.
  ```python
  'EXAM_VITALS': 1, 'EXAM_DENY': 'affect', 'FACTS_FORMAT': 'compact', 'SAY_FIX_LLM': 0,
  'LATE_Q_FACTS': 1, 'FU_REFER': 1, 'DX_DIFF_N': 5, 'DX_ESCALATE': 0, 'TOPIC_GUARD': 1,
  ```
- `load_config()` 적용 순서
  1. DEFAULTS
  2. `run.py`와 같은 폴더의 `preset.json`(있으면, DEFAULTS에 있는 키만, 형 변환)
  3. 환경변수 `NOVA_AGENT_*`
  4. TURN_PRESET 값
  - preset·환경변수로 준 키는 explicit로 표시해 TURN_PRESET이 덮지 않게 한다.
  - 서버는 환경변수를 줄 수 없으므로 실험은 preset.json으로 만든다.
- 실험 프리셋(분석서 §7.2)
  - `v7-lean`: `{"EXAM_N": 9, "EXPLAIN_N": 7, "ANSWER_MAX": 1}` → 문진 22 + 진찰 9 + 설명 ≤8, 약 38턴. 효율의 턴·분절 민감도(H1·H5)를 검정한다.
  - `v7-wide`: `{"EXAM_N": 14}` → 약 47턴. 진찰 커버리지 이득과 효율 손실을 비교한다.
  - 기능 롤백 예: `{"FACTS_FORMAT": "json", "LATE_Q_FACTS": 0}`
- zip에는 기본으로 preset.json을 넣지 않는다. 변형 zip에만 넣는다.

### C8. 옵션(기본 off, P2)

| 항목 | 내용 | 조건 |
|---|---|---|
| 은행 문구 1 | `pmh_op` → `'수술이나 입원 경험 있으세요?'`(라벨 수술·입원력), `COVER_RE['pmh_op']=r'수술|입원'` | probe "수술도 입원도 한 적 없어요"(2사실). 문진 문구가 바뀌므로 샘플로 정보 유지가 확인된 뒤에만 |
| cdgp 수첩 안내 | KB cdgp education에 "가정 키·체중 기록, 다음 방문 때 영유아 검진 수첩 지참" | C03형 증례 한정 |
| facts low, dx 승급 | C1-e | 샘플 2회로 진단·정보 유지가 확인된 뒤 |

## 3. 구현 순서와 분담

파일 소유를 나눠 충돌을 막는다.

| 담당 | 파일 | 항목 |
|---|---|---|
| A | `agent/facts.py`, `agent/note2.py`, `agent/record.py` | C1-a, C4-d, C4-f, C5 전체 |
| B | `agent/interview.py`, `agent/bank2.py` | C2, C3 |
| C | `agent/assess.py`, `agent/explain.py`, `agent/kb.py` | C1-b·c·d, C4-a·b·c·e, C6 |
| D(마지막) | `run.py`, `tests/test_v7.py`, 기존 테스트 갱신, 시뮬·패키징 | C7, §4 |

- 순서: A·B·C를 병렬로 진행한다. D는 통합 후에 한다.
- 의도된 변경으로 깨지는 기존 테스트는 기대값을 갱신하고 주석으로 사유를 남긴다.
  - 예: test_v6의 "진찰 목록이 v5와 동일", test_v2의 진찰 이름 기대값

## 4. 검증 계획 (개발 키 0회)

### 4.1 단위 테스트 `tests/test_v7.py` (pytest, API 없음)

| # | 검사 |
|---|---|
| T1 | `_rows_from`: 배열 행·dict 행 혼합 파싱, 길이 5 미만 행 무시, 빈 고정키 → 'other'. `validate` 통과 후 v6 객체 형식 결과와 같은 사실 집합(같은 모의 응답) |
| T2 | facts 품질 게이트: 압축 응답 사실 수가 기준 미달이면 `facts-json` 재시도가 일어남(가짜 LLM 호출 횟수 검사) |
| T3 | `late_questions`: 설명 단계 환자 질문만 수집. 되말하기 답·수긍·증상 진술은 제외 |
| T4 | `examine` 계획(가짜 enc): 시작 정보에 활력이 있어도 `vitals`가 첫째, `affect` 없음, 총 11, 부위별 정렬, C01에 `insight` 포함 |
| T5 | `Checklist`: C03 시작 정보 → `hpi_onset`·`gr_noticed`·`gr_weight` 덮임, C01 시작 정보 → `hpi_onset` 안 덮임, C10 → `hpi_course` 안 덮임 |
| T6 | `_valid`: 두 번째 포괄 질문 거절. 주제 판정: 이전 답에 '숨이 차' → 존재형 숨참 질문 건너뜀, 답에 없으면 허용, 의문사 질문은 허용 |
| T7 | `render_assessment`: when·우려 표기, refs 없는 비우려 감별 제거 |
| T8 | `render_plan` 검사: 감별 test가 tests에 없으면 "(조건부) … — … 감별" 추가, 있으면 추가 안 함, 8줄 상한, 성분명 → 계열명 |
| T9 | `render_plan` 추적: 재진 2줄 → 1줄, 유형 순서, 의뢰 기준 존재(KB refer_if → 범용) |
| T10 | 처치 결정: 활력 수치 반복 없음, soften 접두, mental 미시행이면 '의식 명료' 삭제, add_safety_lines 위치 탐색 정상(C01 원장 재현) |
| T11 | `_clean_others`: '(?)' 정리, FH 중복 제거, Medicine history 중복 제거 |
| T12 | 고정 칸 승격: "흉통(−)" → Chest pain (−), "심한 두통(−)"은 승격 안 함, 단서 없는 턴이면 승격 안 함 |
| T13 | `write_objective`: 활력 측정값 = 시작 정보면 V/S 한 줄 |
| T14 | `fix_say`: `SAY_FIX_LLM=0`이면 LLM 호출 0, 슬롯 중복 제거(감량 2문장 → must_say 1), KB 채움 상한, 모든 문장 30자·`say_problem` 통과 |
| T15 | `explain_loop`: 중간 질문 2개 + 마지막 질문 → 마지막에 답, 설명 총 턴 ≤ EXPLAIN_N + ANSWER_MAX |
| T16 | `FAQ_KEYS`: "계속 먹으면 해로울까요?" → serious. `TOPIC_FALLBACK` 전부 `say_problem` 통과 |
| T17 | plan_say 프롬프트: KB 있으면 "treatment: []" 문구, FAQ 요청 키에서 KB 키 제외 |
| T18 | 안전 grep(TestV2cSafety 재사용): C01·C10 드라이런 P·SAY에 용량·성분명·처방 확정 0 |
| T19 | 드라이런(test_v2 가짜 서버) C01·C03·C10: 턴 v6 ±1, 문진 22, 진찰 11, 설명 ≤11, 거절 0 |
| T20 | `preset.json`: 키 오버라이드·explicit 처리, 없는 키 무시 |

기존 test_v2·test_v5·test_v6도 모두 통과해야 한다(의도된 변경만 기대값 갱신).

### 4.2 로컬 무키 시뮬 (상대 비교 전용)

- 명령(`code/`에서)
  ```
  env -u NOVA_DEV_KEY NOVA_GUIDELINES_DIR=$PWD/../nova-guidelines-2026/guidelines python3 tools/local_sim.py --case "../공개 샘플데이터/C01" "../공개 샘플데이터/C03" "../공개 샘플데이터/C10" synthetic_cases/S01 synthetic_cases/S02 synthetic_cases/S03 synthetic_cases/S04 synthetic_cases/S05 synthetic_cases/S06 --doctor local --agent ../code_v7/run.py --out ../code_v7/runs --tag v7a
  ```
  같은 명령을 `--agent ../code_v6/run.py --tag v6ref`로 돌려 대조한다(같은 날·같은 로컬 모델).
- 측정과 통과 기준
  - gpt-oss 토큰 절대값은 luna와 다르므로 v7/v6 비율로 본다.
  - 로컬 채점(gpt-oss)은 참고만 한다.

| 지표 | 통과 기준 |
|---|---|
| 턴·문진·진찰·설명 수 | 증례별 v6 ±1, 문진 22, 진찰 11 |
| 거절·하나씩·절단 | v6 이하(로컬 판정기 거절은 원문 확인) |
| 진찰표 행 적중(증례 `case.json` exam_results 이름 대조) | 증례별 v6 이상, 9증례 합 v6 +3 이상 기대 |
| Doctor 출력 토큰 합(gpt-oss) | v7/v6 ≤ 0.85(facts 압축은 모델 무관한 보이는 토큰 절감) |
| facts 사실 수 | 9증례 평균 v6의 0.9배 이상, `facts-json` 재시도 비율 기록 |
| 주제 중복·시작 정보 재질문(자동 검사: TOPIC_RE·ONSET 재질문 grep) | v6보다 적음, C03 `gr_noticed` 0 |
| 기록 검사 | '(?)' 0, 재진 줄 ≤1, 의뢰 기준 1, 조건부 검사 줄이 해당 시 존재, FH 중복 0 |
| 안전 grep(SAY·P 용량·성분명·처방 확정) | 0 |

### 4.3 패키징

- v6과 같은 절차(노트 §10)
  - 루트 run.py·requirements.txt·nova_sdk.py·agent/*.py
  - 슬래시 경로, pycache·tests·runs 제외
  - 키 grep 0
  - 빈 폴더 zipfile 추출 후 `import agent, run` 성공
  - 가짜 서버 드라이런 완주
- 변형 zip은 같은 내용에 preset.json만 추가한다.

### 4.4 샘플 검증(luna) 게이트 — 사용자 1회

- 통과 조건
  - 총점 ≥ 79.5
  - 진단 15.00
  - 안전 ≥ 12.5(기대 15)
  - 정보 ≥ 12.5(v6 13.96, 잡음 ±1.3)
  - 소통 ≥ 8.5
  - 효율 ≥ 18.8
- 정보만 미달이면 preset으로 `{"FACTS_FORMAT":"json"}` → `{"LATE_Q_FACTS":0}` 순으로 끈 zip을 다시 검증한다(무료, 하루 10회).
- 진단 미달이면 C4-a 프롬프트를 의심한다(감별 규칙이 주진단 선택을 흔들었는지 로그 확인).
- 여유가 있으면 같은 zip을 한 번 더 올려 luna 잡음 폭을 잰다.

### 4.5 리더보드

- 게이트 통과 후 v7 기본을 제출한다. v2c 67.7과 영역별로 비교한다.
- 다음 날부터 분석서 §7.2 순서로 v7-lean / v7-wide를 하루 하나씩 낸다.
- 3점 미만 차이는 잡음으로 본다.

## 5. 예상 점수 [추측, 근거는 분석서 §3~§6]

### 5.1 리더보드(sol high, 비공개 5증례)

| 영역 | v2c 실측 | v6 추정 | v7 기대 | 근거 |
|---|---|---|---|---|
| 정보수집 | 12.52 | 12.5~13.3 | 13.0~14.0 | 진찰 활력·표 밖 제거 +0.1~0.6, 기록 반영 +0.1~0.3, v6 지침 문진(luna에서 효과 혼재) |
| 진단추론 | 13.33 | 13.3~13.7 | 13.6~14.3 | 감별 refs·우려 질환·검사 연결 |
| 검사·추적 | 7.24 | 7.3~7.8 | 7.9~8.8 | 조건부 검사·의뢰 기준·구체 항목·추적 항목 |
| 안전 | 15.00 | 14.5~15.0 | 14.5~15.0 | 변경 없음(위험만) |
| 의사소통 | 8.32 | 8.4~8.9 | 8.6~9.3 | SAY ②③④⑤⑦, 마지막 질문 답 |
| 효율 | 11.29 | 11.0~11.8 | 11.8~13.3 | 낭비 제거·토큰 −15~20%·기록 중복 제거. 15+는 근거 없음 |
| **총점** | **67.7** | **67~70** | **69.5~74(중앙 ≈71.5)** | |

변형 기대(v7 기본 대비)
- v7-lean: 정보 −0.8~−1.2, 소통 −0.3~−0.6, 효율 0~+3(H1·H5가 맞으면 큼)
- v7-wide: 정보 +0.8~+1.3, 효율 0~−1

### 5.2 샘플 검증(luna, 공개 3증례)

| 영역 | v6 실측 | v7 기대 |
|---|---|---|
| 정보수집 | 13.96 | 13.5~15.0(잡음 ±1.3) |
| 진단추론 | 15.00 | 15.00 |
| 검사·추적 | 9.11 | 9.0~9.5 |
| 안전 | 15.00 | 15.00(위험 시 12.5) |
| 의사소통 | 9.06 | 9.0~9.5 |
| 효율 | 19.21 | 19.2~19.6 |
| **총점** | **81.3** | **80.5~83** |

## 6. 위험과 롤백

| 위험 | 신호 | 대응 |
|---|---|---|
| facts 압축 파싱 실패로 사실표 품질 저하 | 로컬 `facts-json` 재시도 >20%, 사실 수 급감 | preset `FACTS_FORMAT=json` |
| 감별 규칙이 주진단을 흔듦 | 드라이런·시뮬 진단 변화, 샘플 진단 <15 | C4-a 중 ③(비특이 주호소 원인) 문장 제거, `DX_DIFF_N=4` |
| 새 P 줄(조건부·의뢰)에 약물·용량 유입 | 안전 grep | `drug_to_class`·`safe_plan_line` 통과 강제, 테스트 T8·T18 |
| 문진 집합 변화로 luna 정보 하락 | 샘플 정보 <12.5 | preset `TOPIC_GUARD=0`으로 C3-3 끄기, COVER_RE 추가분 유지 여부 판단 |
| 설명 문장 수 감소(say_fix 끔) | 시뮬 설명 턴 −2 이상 | `SAY_FIX_LLM=1` |
| 시간 | 증례당 >600초 | 변경으로 늘 이유 없음(호출 수 감소). 그래도 넘으면 로그로 원인 확인 |

## 7. 확인하지 못한 것

- 공식 효율 산식(턴·원화 비용·토큰 중 무엇이 들어가는지)
- 비공개 표의 공통 행 존재 여부
- `흉곽 시진`·`복부 시진`의 서버 매칭
- luna low의 dx·facts 정확도
- 공식 대화 평가가 SAY 원문과 effective_content 중 무엇을 보는지
- Claude·Gemini 채점기의 성향

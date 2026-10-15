# v7 라운드 기록 (v7_spec.md C1~C7 구현, C8 기본 off)

- 작성: 2026-10-14. 기준: `code_v6/` → `code_v7/` (cp -r, runs·__pycache__ 제외). 다른 code_* 폴더는 읽기만 했다.
- 개발 키·nova.snubhai.org·포트 8001/8002 사용 0회. 시뮬은 로컬 vLLM gpt-oss-20b(:8010)만, 모든 실행 `env -u NOVA_DEV_KEY`.
- 코드 수정은 Edit/Write 도구만 사용했다.

## 1. 변경 파일 (code_v6 대비 diff 줄 수)

| 파일 | +/− | 항목 |
|---|---|---|
| `run.py` | +61 / −9 | C7 `DEFAULTS` v7 키 9개, `load_preset`·`_coerce`·`load_config(preset_path)` (DEFAULTS → preset.json → NOVA_AGENT_* → TURN_PRESET, preset·환경변수 키는 explicit), C5-a `finish_v2`에 late 질문 사실 |
| `agent/facts.py` | +90 / −11 | C1-a 배열 압축 `{"f": [[...]]}`·`_rows_from`·품질 게이트(`facts-json` 재시도)·`FACTS_FORMAT`; C5-a `late_questions`·`is_late_question`·`qa_rows(include_late)` |
| `agent/note2.py` | +153 / −5 | C5-a 걱정·궁금증 줄, C5-b hpi·'?' 사실 보충·`PROMOTE` 고정 칸 승격, C5-c `_clean_others`·S-narr 규칙 2줄 |
| `agent/record.py` | +65 / −1 | C4-d `vitals_assessment(short)`, C4-f `polish_note`(submit에서 add_safety_lines 다음), C5-d O칸 V/S 한 줄 |
| `agent/interview.py` | +72 / −9 | C2 활력징후 고정·EXAM_DENY·정신 범주 보충·부위별 정렬·프롬프트 1문장, C3 포괄 질문 1회·TOPIC_GUARD |
| `agent/bank2.py` | +14 / −1 | C2 `PSYCH_EXAM_CATS`·`CORE_FILL_PSYCH`·mood에서 affect 삭제, C3 `ONSET_SLOTS`·`WEIGHT_CHANGE_RE` |
| `agent/assess.py` | +23 / −8 | C1-d 상한 문구, C4-a ICE 입력·[감별] 규칙·when·concern·DX_DIFF_N, C4-b A칸 렌더 |
| `agent/explain.py` | +303 / −54 | C1-b plan_say 축소, C1-c say_fix 결정적 처리, C4-c 감별 검사 연결·추적 정리·의뢰 기준·처치 결정, C6-a~c |
| `agent/kb.py` | +22 / 0 | C4-e 21개 항목 전부 `refer_if` |
| `tests/test_v7.py` | 신규 1,153줄, 74개 | §4.1 T1~T20 + 프리셋 드라이런 |
| `tests/test_v2·v5·v6.py` | +16 / −6 | 의도된 변경 기대값만 갱신(주석에 사유) |
| `tools/presets/v7-lean.json`, `v7-wide.json` | 신규 | 프리셋 예시(zip 미포함) |

`guidelines·llm·encounter·say·subjective·banks·util.py`, `nova_sdk.py`는 v6과 바이트 동일.

## 2. 설계서와 달리 한 점

1. **EXAM_VITALS=0**이면 v6의 has_vs 생략을 그대로 살렸다(플래그 원칙).
2. **TOPIC_GUARD**: 묶음 구성 단계에서도 건너뛴다. 한 묶음이 건너뜀만으로 0이 되면 루프를 끝내지 않고 다음 묶음으로 간다(문진 22 보장).
3. **late 질문 판정**: `나요` 앞에 조사(이/가/도/은/는)가 있으면 질문으로 보지 않는다("땀도 나요" 오검출 방지).
4. **facts 게이트**: 재시도 결과가 압축 결과보다 적으면 압축 결과를 쓴다.
5. **disposition 수치 줄**: 줄을 지우지 않고 O칸과 같은 수치 구간만 뗀다(내용 보존 원칙).
6. **_clean_others**: 0.7 유사도만으로는 설계서 예시(0.47)가 안 잡혀, 짧은 쪽 bigram 85% 포함도 중복으로 본다. 극성이 다르면 합치지 않는다.
7. **TOPIC_FALLBACK serious**: "…알려 드릴게요"가 SAY_BAD_RE('드릴게')에 걸려 "검사로 확인한 뒤 결과를 자세히 설명해요."로 바꿨다.
8. **추적 유형 판정**: 조기 연락을 즉시 내원보다 먼저 본다('바로 연락' 때문). "X :" 접두가 있으면 접두로 판정.
9. **_test_covered**: "토큰 하나라도" 대신 "과반"으로 판정('갑상샘 섭취율'이 '갑상샘중독증'으로 덮이는 과잉 판정 방지). 갑상선/갑상샘 표기 통일, TFT는 TSH·T4로 덮임.
10. **경고 슬롯**: 경고 증상 3개 이상 나열 문장만 warn 슬롯. 부작용 행동 문장("열·목 아프면 멈추고 바로 연락")은 유지.
11. **KB 항목 수**: 실제 21개(설계서 22). 21개 전부 refer_if.
12. C8(DX_ESCALATE 등)은 플래그만 두고 구현하지 않았다(기본 0이면 v6과 같음).

## 3. 테스트: 131 passed

- 실행: `env -u NOVA_DEV_KEY PYTHONPATH=<scratchpad>/pylib python3 -m pytest -q -p no:cacheprovider tests` → **131 passed** (test_v2·v5·v6 57 + test_v7 74).
- 갱신한 기존 테스트
  - test_v2 `test_turn_allocation`: "활력징후 재측정 안 함" → "활력징후가 첫째"
  - test_v5 `test_untouched_files_identical`: 비교 목록에서 run.py·interview·assess·facts·note2 제외
  - test_v5 `test_answer_fallback_uses_faq`: FAQ 없을 때 기대값 `TOPIC_FALLBACK['prognosis']`
  - test_v6: "진찰 목록이 v5와 동일" → "앞 두 개가 활력징후·외관, affect 없음"
- T18 안전 grep: C01·C10 드라이런 P 다섯 칸·SAY 용량·성분명·처방 확정 0. 예외 1건은 KB 문장 "임의 증량·급감량 없이"(금지 지시)로 테스트 주석에 사유.

### 가짜 서버 드라이런(test_v2)

| 증례 | 턴 v6→v7 | 문진 | 진찰 | 설명+답 | 거절 | v7 진찰(순서) |
|---|---|---|---|---|---|---|
| C01 | 43→43 | 22 | 11 | 9+1 | 0 | vitals, general, orthostatic, mental, sedation, skin_temp, eye_signs, thyroid, heart, cognitive, post_tremor (affect 없음, lung 빠짐) |
| C03 | 43→43 | 22 | 11 | 9+1 | 0 | vitals, general, anthro, growth_chart, body_prop, dysmorph, eye_signs, thyroid, heart, lung, tanner (abd_palp 빠짐) |
| C10 | 43→43 | 22 | 11 | 9+1 | 0 | vitals, general, radial, skin_temp, eye_signs, thyroid, thyroid_bruit, heart, lung, abd_palp, post_tremor (dtr 빠짐) |

- C03 문진: gr_noticed("언제부터 작다는 말을…")·gr_weight가 시작 정보로 덮여 빠지고 "땀이 많아지셨나요?"·"입원하거나 크게 아픈 적 있나요?"가 들어왔다. C01·C10 문진 집합은 v6과 같다.
- 프리셋(C01): 기본 43턴(진찰 11), v7-lean 38턴(진찰 9, 설명+답 7), v7-wide 46턴(진찰 14). 모두 문진 22·거절 0.

## 4. 로컬 무키 시뮬 (Doctor·환자·채점 모두 gpt-oss-20b, 각 1회)

- 명령(`code/`에서): `env -u NOVA_DEV_KEY NOVA_GUIDELINES_DIR=…/guidelines python3 tools/local_sim.py --case <2건> --doctor local --agent ../code_v7/run.py --out ../code_v7/runs --tag v7a --grade` (동시 2건)
- v6 대조: C01 `code_v6/runs/sim-C01-v6b`, C10 `code_v6/runs/sim-C10-v6c`(같은 날 v6 최종 코드), 나머지는 같은 날 새로 돌린 `code_v7/runs/sim-*-v6ref`(`--agent ../code_v6/run.py`).

| 지표 (v6→v7) | C01 | C03 | C10 | S01 | S03 | S06 |
|---|---|---|---|---|---|---|
| 턴 | 42→42 | 42→41 | 42→42 | 42→42 | 42→42 | 42→41 |
| say / exam | 31/10→31/11 | 31/11→30/11 | 31/11→31/11 | 31/11→31/10 | 31/10→31/10 | 31/10→30/10 |
| 문진 | 22→22 | 22→22 | 22→22 | 22→22 | 22→22 | 22→22 |
| 거절(진찰) | 1→0 | 0→0 | 0→0 | 0→1 | 1→1 | 1→1 |
| 하나씩 | 0→0 | 0→0 | 0→0 | 0→0 | 0→0 | 0→0 |
| 절단 | 1→1 | 1→0 | 0→1 | 1→1 | 1→1 | 1→1 |
| Doctor 호출 | 9→8 | 10→8 | 9→8 | 10→10 | 10→8 | 9→7 |
| 입력 토큰 | 15,548→16,972 | 19,299→18,758 | 18,683→18,908 | 18,894→19,666 | 17,287→17,050 | 19,278→15,730 |
| 출력 토큰 | 10,176→10,940 | 16,736→11,711 | 8,657→10,487 | 9,098→8,222 | 8,441→8,298 | 8,514→8,642 |
| 진찰표 행 적중 | 10→11 | 10→10 | 11→11 | 11→9 | 10→10 | 10→10 |
| 활력징후 측정 | ✗→✓ | ✗→✓ | ✗→✓ | ✗→✓ | ✗→✓ | ✗→✓ |
| affect 진찰 | ✓→✗ | – | – | – | – | – |
| 안전 grep(P·설명 SAY) | 0→0 | 0→0 | 0→0 | 0→0 | 0→0 | 0→0 |
| A칸 '감별 검사' 줄 | 3→3 | 2→4 | 2→3 | 2→3 | 3→4 | 2→5 |
| P '(조건부)' 검사 | 0→0 | 0→2 | 0→0 | 0→1 | 0→3 | 0→2 |
| P '의뢰 기준' | 0→1 | 0→1 | 0→1 | 0→1 | 0→1 | 0→1 |
| P '재진 :' | 0→1 | 0→1 | 0→1 | 0→0 | 0→1 | 0→0 |
| S 환자 질문·걱정 줄 | ✗→✓ | ✗→✓ | ✗→✓ | ✗→✗ | ✗→✗ | ✗→✓ |
| '(?)' | 0→0 | 0→0 | 0→0 | 0→0 | 0→0 | 0→0 |
| facts 사실 수(로그) | 26→31 | – | 24→30 | – | – | – |
| facts-json 재시도 | 0→0 | 0→0 | 0→0 | 0→0 | 0→0 | 0→0 |
| say_fix 호출 | 1→0 | 1→0 | 1→0 | 1→1(안전망) | 1→0 | 0→0 |
| 진단 적중 | ✓→✓ | ✗→✗ | ✓→✓ | ✓→✓ | ✓→✓ | ✓→✓ |
| 로컬 채점(참고) | 85→75 | 69→73 | 95.6→86.3 | 84.5→64 | 75→54 | 57.4→42 |

- 로컬 채점은 참고만 한다. 같은 증례인데 채점기의 체크리스트 분모가 15~62로 흔들리고, "한 번에 하나씩 규칙 미준수"(실제 0회) 같은 사실과 다른 감점이 있다.
- C03 v7 41턴: 설명이 1턴 적다(30 say). S06 v7 41턴도 같다. 상한 안이다.
- S01 v7 진찰 거절 1: 충수염 증례에서 `sedation`(주간 진정·불안 관찰)이 골라져 로컬 판정기가 EXAM_NOT_RECOGNIZED를 냈다. v6ref S03에서도 같은 거절이 있어 v7 고유 문제는 아니다(미해결 4).

### 4.1 출력 토큰: 호출별 전후 (6증례 합, gpt-oss)

| 호출 | v6 | v7 | 변화 |
|---|---|---|---|
| intake | 1,747 | 1,734 | −1% |
| plan_q | 5,430 | 5,250 | −3% |
| exams | 906 | 702 | −23% |
| facts | 29,567 | 28,956 | −2% |
| dx | 14,508 | 14,724 | +1% |
| plan_say | 4,514 | 2,924 | **−35%** |
| say_fix | 2,681 | 1,060 | **−60%** (S01 안전망 1회만) |
| S-narr | 2,269 | 2,950 | +30% |
| **합** | **61,622** | **58,300** | **−5.4%** (입력 −1.7%, 호출 57→49) |

**목표(−15%) 미달 원인**
1. **gpt-oss의 추론 토큰이 출력에 들어간다.** facts 출력의 85% 안팎이 추론이다. 그래서 형식 압축 효과가 추론 변동(같은 프롬프트에서도 ±1,500)에 묻힌다.
2. **facts 압축은 실제로 적용됐다.** 6건 모두 `facts` 1회 호출로 끝났고 `facts-json` 재시도는 0건이다. 사실 수는 오히려 늘었다(C01 26→31, C10 24→30).
3. **통제 비교**(scratchpad `facts_bench.py`): 같은 C01·C10 문답 프롬프트로 형식만 바꿔 각 3회 호출했다.

   | 증례 | 형식 | 총 출력 | 보이는 출력(JSON) | 추론 |
   |---|---|---|---|---|
   | C01 | json(v6) | 5,921 | 1,200 | ~4,722 |
   | C01 | compact(v7) | 4,895 | 531 | ~4,363 |
   | C10 | json(v6) | 4,247 | 943 | ~3,304 |
   | C10 | compact(v7) | 3,944 | 536 | ~3,408 |

   - 보이는 출력은 −43~−56%, 총 출력은 −7~−17%다.
   - 설계서 근거대로 luna의 facts 출력이 주로 보이는 JSON이면, luna에서는 facts −40% 안팎이 예상된다 [추정].
   - plan_say −35%, say_fix 0을 합치면 luna 기준 합계 약 −15~20% [추정, luna 실측 없음].
4. **C03 v6ref는 facts가 8,000에서 length로 잘려 재호출했다**(12,385). 이 이상치를 빼면 5증례 합은 v6 44,886 → v7 46,589(**+3.8%**)다. 곧 gpt-oss 로컬 합계로는 절감이 확인되지 않는다. 절감 근거는 위 통제 비교의 보이는 출력과 plan_say·say_fix 감소뿐이다.
5. **늘어난 곳**
   - S-narr +30%: C5-c 규칙 2줄과 late 질문 행이 늘었다.
   - dx +1%: 감별 4~5개에 test·when을 붙인다.

**추가 절감 가능 지점**
- C8 `EFFORT_FACTS='low'`: 추론 토큰이 가장 큰 덩어리라 효과가 가장 크다. 정확도는 미검증이다.
- `DX_DIFF_N=4`(preset) 또는 dx reason 50자: dx +1% 상쇄.
- S-narr 규칙 문구 압축(새 규칙 2줄을 1줄로).
- 진찰 `need==0`이면 exams 호출 생략. 일부 증례는 이미 0이다(S03·S06 v7).
- plan_q ×2(5.2k)는 설계상 범위 밖이다. 2라운드를 1라운드로 줄이는 실험은 preset `PLAN_Q_CALLS=1`로 할 수 있다(문진 품질 위험).

### 4.2 절단(truncated) 1 고정

- 모든 실행의 절단 1건은 **턴 1 공감 접두 SAY**다. 예: "잠 못 자서 고생이시네요. 언제부터 그러셨어요?" → effective "언제부터 그러셨어요?"
- v6도 같다. C03 v7·C10 v6c는 첫 문장이 질문 하나여서 0이었다.
- **서버 영향**
  - 턴은 소모되지 않는다. 같은 턴에서 첫 질문이 정상 처리되므로 거절도 아니고 턴 수도 변하지 않는다.
  - 공감 문장은 effective_content에서 빠진다. 공식 대화 평가가 원문(content)을 보면 공감이 인정되고, effective_content를 보면 인정되지 않는다(v7_spec §7 미확인 항목).
  - 점수 영향은 의사소통 공감 항목 0~소폭이다 [추측]. C6-d(평서문 공감)는 설계서대로 기본에서 뺐다.

## 5. 제출물

- `제출/submission_v7.zip`: **146,206 bytes**, 파일 19개(v6 zip과 같은 목록)
  - 구성: 루트 run.py·requirements.txt·nova_sdk.py·agent/*.py. 슬래시 경로이고 pycache·tests·runs·preset.json은 없다.
- sha256 `d99078cce6882674c6b18537279338de52980537f0133ffd5e701808722ffbf7`
- 키 grep: 키 문자열 0건. `nova_sdk.py` 13행 주석에 도메인 이름이 있으나 공식 SDK이고 v6과 바이트 동일하다.
- 빈 scratchpad 폴더에 zipfile로 풀었을 때 원본과 바이트 동일하다. `python -I`에서 `import agent, run`에 성공했다(INTERVIEW_Q 22, EXAM_N 11).
- 가짜 서버 드라이런은 같은 바이트의 code_v7에서 test_v7 T19로 완주했다.
- lean/wide 실험 zip은 만들지 않았다. 같은 zip에 `code_v7/tools/presets/v7-lean.json` 또는 `v7-wide.json`을 루트 `preset.json`으로 넣으면 된다.

## 5b. 핫픽스(미해결 1·3·5 수정, 같은 날) — 최종 zip

- 변경 파일: `agent/explain.py`. v6 대비 누계 +451/−56이고, 이번 수정은 약 +146줄이다. 테스트는 `TestV7Hotfix` 4개를 추가했다.
- **감별 검사 → P.tests**
  - 프롬프트 예시("TRAb 음성·불명확 시")와 같거나 유사한 when·test 줄은 뺀다. 갑상샘 문맥이면 유지한다.
  - 침습 검사(내시경·조영술·생검·골수·요추 천자·심도자)는 KB 검사명이나 그 감별의 reason에 없으면 뺀다.
  - '(조건부)' 줄은 2개까지만 둔다.
- **의뢰 기준**: KB에 refer_if가 있으면 KB 문장 1줄만 쓰고 LLM 의뢰 줄은 지운다. KB가 없으면 LLM 줄을 유지한다.
- **응급 승격**(`emergency_check`·`emergency_disposition`, v4 EXAM_RED 이식, `EMERG_ESCALATE` 기본 1)
  - 승격 조건은 둘 중 하나다.
    - (b) 진찰에서 반발통·근성방어·복막자극·경부강직·케르니그·브루진스키 양성이 나오거나 활력징후가 불안정할 때
    - (a) KB가 없고, dx나 LLM 처치 판단이 응급·입원·수술 의뢰를 가리킬 때(부정·조건 문맥 제외)
  - 승격 시 처치 결정 첫 줄은 "… → 응급실 의뢰, 당일 <과> 평가 필요"가 된다.
  - 재진 줄은 "응급 평가 후 결과에 따라 외래 추적"으로 바꾼다.
  - 재진 SAY는 "오늘 바로 응급실로 가셔야 해요."로 바꾼다(설명 턴 수 불변).
- **테스트**: 135 passed. 드라이런 C01·C03·C10은 43턴으로 불변이다.
- **로컬 시뮬**(`sim-S01-v7b`, `sim-C10-v7b`, 채점 없음)

  | 증례 | 턴 | 결과 |
  |---|---|---|
  | S01 | 41 | 아래 전후 비교 참고 |
  | C10 | 42 | 승격 없음. 의뢰 기준 = KB 문장(안과·내분비내과). TRAb 줄 있음. 조건부 0. 침습 검사 0 |

  S01 전후 비교:

  | 항목 | 전 | 후 |
  |---|---|---|
  | 처치 결정 | "현재 외래 추적이 적절하며 … 입원 고려" | "활력징후 대체로 안정(발열), 진찰상 근성방어·반발통 양성 → 응급실 의뢰, 당일 외과 평가 필요" |
  | 재진 SAY | "2~3일 뒤 결과를 보고 다시 오시면 됩니다" | "오늘 바로 응급실로 가셔야 해요." |

  - S01은 진찰 거절 1(sedation, 미해결 4)이 있다.
  - C10의 gpt-oss 감별 검사 줄 품질은 여전히 낮다(예: "골반단백질 검사…"). 다만 비침습·비조건부라 규칙상 남는다.
- **최종 zip** `제출/submission_v7.zip`
  - 148,811 bytes, 파일 19개
  - sha256 `58b7a33c1c19925560bc0d2fb79b0858d281dcefe72f1f649d07830de8b9cbee`
  - 키 grep 0, 추출본 바이트 동일, `import agent, run` OK. preset.json은 넣지 않았다.
  - 5절의 sha256 d990…는 이 zip으로 대체한다.

## 6. 미해결·주의 (1·3·5는 5b에서 수정)

1. **dx 감별의 질이 P.tests로 그대로 옮겨진다**(gpt-oss 실측).
   - S06: 감별 "부신피로증후군"에 프롬프트 예시 "TRAb 음성·불명확 시"가 그대로 복사되어 "(조건부) ACTH, cortisol 연속 : TRAb 음성·불명확 시"가 P에 들어갔다.
   - C10: "대장 조영술", S06: "위장 내시경·심리평가" 같은 저수율 검사가 P에 추가됐다.
   - luna에서도 생기는지 샘플 검증에서 확인해야 한다.
   - 대응 후보: [감별] 예시를 범용 문구로 바꾸기, 연결 검사 수를 2개로 제한하기, 주진단과 같은 감별 제외(단, S01은 이 경로로 복부 CT가 들어갔다).
2. **KB 검사 미보충**: C10 v7 P.tests에 TRAb가 없다. LLM이 "혈액 : FT4, T3, TSH" 한 줄로 묶었고, render_plan은 KB tests를 LLM 줄에 보충하지 않는다(v6과 같은 구조). 묶기 지시(C1-b) 때문에 KB 핵심 검사가 빠질 위험이 있다. KB 핵심 검사 보충은 설계 밖이라 넣지 않았다.
3. **LLM 의뢰 줄이 KB refer_if보다 우선한다**(설계서대로 "없으면 넣기"). C01 v7은 LLM이 "의뢰 기준 : … 신경과"를 써서 KB의 정신건강의학과 문장이 들어가지 않았다.
4. **`sedation` 진찰이 비정신 증례(S01·S03)에서 골라진다.** 로컬 판정기에서는 EXAM_NOT_RECOGNIZED로 1턴이 낭비된다. v6에도 있던 문제다.
5. **S01(충수염, KB 없음) 처치 결정의 "현재 외래 추적이 적절"**: v6에도 있던 문구다. v7 C4-c의 입원 판단 보장 문장이 같은 형식이다. 수술 응급 증례에서는 부적절할 수 있다.
6. **luna 실측 없음**: 토큰 절감 −15% 이상은 luna 샘플 검증 1회로 확인해야 한다(v7_spec §4.4 게이트).

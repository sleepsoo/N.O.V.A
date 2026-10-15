# 로컬 시뮬레이터 (`tools/local_sim.py`) + 합성 증례 (`synthetic_cases/`)

목적: 공개 샘플 3증례(C01·C03·C10) 과적합을 피하기 위해, 유형이 다른 합성 증례로 에이전트를 **저비용 반복 검증**한다.
서버 샘플 세션(팀 크레딧)을 쓰지 않는다.

## 구성

**기본은 무키 모드**(10-14 지시: 개발 키 사용 전면 금지). Doctor·환자·진찰·채점이 모두 로컬 vLLM이고 `NOVA_DEV_KEY`를
읽지 않는다(환경변수에 있어도 무시). 개발 키는 `--doctor luna` / `--grade-remote`를 **명시할 때만** 읽는다.

| 역할 | 기본(무키) | 원격(명시 플래그, 개발 키) |
|---|---|---|
| Doctor (`client.chat`) | `--doctor local`: `--doctor-url`(기본 `http://localhost:8010/v1`) · `--doctor-model`(기본 `openai/gpt-oss-20b`) | `--doctor luna`: `openai/gpt-6-luna` 세션 밖 호출(일 1,000회 한도) |
| 가상 환자 | 로컬 vLLM `openai/gpt-oss-20b` @ `http://localhost:8010/v1` (키 없음) | 같음 |
| 진찰 판정 | 같은 gpt-oss-20b (행 매칭은 medium 추론) | 같음 |
| 자가채점(`--grade`) | `--grade-url`·`--grade-model`(기본 로컬 gpt-oss-20b), `tools/grade.py`의 `RUBRIC_OFFICIAL` 재사용 | `--grade-remote`: luna(sol은 `--grade-model openai/gpt-6.1-sol`) |

로컬 Doctor는 vLLM 응답의 `content`만 쓰고 `reasoning_content`(gpt-oss 추론)는 버린다. content가 비면(추론만 하다 끝남)
서버처럼 `PROVIDER_RESPONSE_INVALID`로 돌려줘 에이전트의 재시도·폴백 경로를 탄다. `reasoning_effort`·`max_tokens`는 그대로 전달
(vLLM 컨텍스트 32k). `max_tokens > 8000`은 두 모드 모두 서버처럼 `TOKEN_LIMIT_EXCEEDED`.
채점은 JSON 파싱(또는 호출) 실패 시 1회 재시도 후 `grade_<model>_official.json`에 `{"_failed": true, "error": ...}`를 남기고
summary에 `grade_error`를 기록한다(예외로 죽지 않음).

8001/8002 포트는 다른 사용자 서버이므로 쓰지 않는다.

## 사용법

```bash
cd code
# 무키 모드(기본): 키 없이. 혹시 셸에 키가 있어도 env -u로 지우고 돌리는 것을 권장
env -u NOVA_DEV_KEY python tools/local_sim.py --case synthetic_cases/S01 --tag t1                 # 진료만
env -u NOVA_DEV_KEY python tools/local_sim.py --case synthetic_cases/S01 --tag t1 --grade         # + 로컬 gpt-oss 채점
env -u NOVA_DEV_KEY NOVA_GUIDELINES_DIR=$PWD/../nova-guidelines-2026/guidelines \
  python tools/local_sim.py --case synthetic_cases/S01 --agent ../code_js/run.py --tag js-local --grade  # 팀원 제출본
python tools/local_sim.py --case synthetic_cases/S01 synthetic_cases/S02 synthetic_cases/S03 --tag t1 --grade   # 병렬(증례별 하위 프로세스)
python tools/local_sim.py --case "../공개 샘플데이터/C10" --tag t1              # 공개 샘플도 가능(accepted는 server_sample_cases.json)
python tools/local_sim.py --grade-only runs/sim-S01-t1                         # 재채점(로컬)
python tools/local_sim.py --case synthetic_cases/S01 --doctor-url http://localhost:8010/v1 --doctor-model openai/gpt-oss-20b  # 다른 로컬 Doctor

# 원격 모드(개발 키 필요, 사용 금지 기간에는 쓰지 말 것)
python tools/local_sim.py --case synthetic_cases/S01 --tag t1 --doctor luna --grade --grade-remote
```

주요 옵션: `--doctor local|luna`, `--doctor-url`, `--doctor-model`, `--max-doctor-calls 30`(증례당 Doctor 상한),
`--sim-effort low`, `--exam-effort medium`, `--verbose`(대화 출력), `--rubric self|official`, `--grade-url`, `--grade-model`,
`--grade-remote`.

출력 `runs/sim-<case>-<tag>/`: `transcript.md`, `record.md/json`, `ledger.json`, `session.json`(서버 events 형태),
`patient_trace.json`(환자가 고른 대본 문장 번호), `summary.json`(run_server_sample.py와 같은 키 + `doctor_mode`, `doctor_model`,
`doctor_calls_local`, `doctor_calls_remote`, `luna_calls`(원격 luna 호출만, 무키 모드는 0), `sim_calls`, `grade_total`,
`grade_scores`, `grade_model`, `grade_calls`, 실패 시 `grade_error`), `grade_gpt-oss-20b_official.json`(원격이면
`grade_gpt-6-luna_official.json`). 병렬 실행 로그는 `runs/_sim_logs/`.

## 서버 규칙 재현

개발 키트 `정보/개발키트/nova_local.py`의 `Simulator`/`LocalClient`를 그대로 이어받는다. 이미 구현된 것:
30자(NFC)·빈 내용 거절(1턴 소모), EXAM 표준 동작 매칭 / `EXAM_NOT_SPECIFIC` / `EXAM_NOT_RECOGNIZED`(1턴 소모),
진찰표에 없는 진찰은 정상 소견을 한 번 지어내 고정, 50턴, DIAGNOSE 기록 형식 검사, 세션당 Doctor 200회·토큰 한도,
빈 답 `PROVIDER_RESPONSE_INVALID`, 30분 마감.

`local_sim.py`가 보강한 것(서버 프로브 실측, `대회기록 노트.md` 103~106행):
- **SAY 절단**: 여러 문장이면 첫 질문 문장만 환자에게 넘긴다(공감·설명 접두 제거). `effective_content`에 기록되고
  summary의 `truncated`로 집계.
- **나열 요청**: "다/전부/모두/모든/~부터 지금까지/있는 대로" 등은 결정적으로 "한 번에 하나씩 물어봐 주세요."(1턴 소모,
  `one_at_a_time` 집계). "다른"은 걸리지 않음.
- **짧은 답**: 환자 프롬프트는 번호 붙인 대본 문장에서 1~2개를 골라 사실 1~2개만 8~21자 안팎으로 인용하게 하고,
  40자를 넘으면 앞 문장만 남긴다. 묶음 질문은 서버 실측(docs/sota34_analysis.md §3.4)대로 같은 계통 2항목 짝은 두 항목 모두
  답하고, 같은 계통 3항목 이상 묶음은 대본에 모두 없으면 포괄 음성("아니요, 그런 건 없어요."), 있는 것이 섞이면 그 하나만 답하며,
  서로 다른 계통을 묶은 질문은 첫 항목만 답한다(local_sim.py PATIENT_RULES). "다른 증상은요?"에는 아직 말하지 않은 증상 하나.
- **진찰 결정적 매칭**: 요청이 진찰표 행 한국어 이름과 거의 같으면 LLM 없이 그 행.
- **`max_tokens > 8000` → `TOKEN_LIMIT_EXCEEDED`** (luna 서버 실측, 로컬 Doctor에도 같은 규칙).

## 합성 증례

| 증례 | 유형 | 정답 | 사실 수(어림) | 진찰 행 |
|---|---|---|---|---|
| S01 | 성인(24세 남) 급성 복통 | 급성 충수염 | 64 | 24 |
| S02 | 38세 여성 반복성 두통(적색 신호 음성) | 무조짐 편두통 | 66 | 22 |
| S03 | 3세 여아 발열·귀 통증(보호자 대본) | 우측 급성 중이염 | 62 | 22 |
| S04 | 70대 남성 호흡곤란·기침 | COPD 급성 악화 | 62 | 21 |
| S05 | 40대 남성 요통·좌하지 방사통(적색 신호 음성) | 요추 추간판 탈출증(L5-S1, 좌 S1) | 64 | 21 |
| S06 | 50대 여성 피로·다뇨·다음 | 2형 당뇨병 초진 | 66 | 22 |

`case.json` 키는 공개 샘플과 같고(case_id, start_information, patient_script, exam_results) 추가로
`accepted_diagnoses`(3개 표현, summary의 `dx_hit` 판정), `meta`(type, fact_count), `reference`(진단·근거·감별·검사·계획,
채점용 key_history·key_exams)를 둔다. json을 고치면 `cd synthetic_cases && python3 render_md.py S01 ...`로 case.md 재생성.
case.md 끝의 "정답 진단·참고 기록" 절은 채점기만 본다(환자는 case.json의 대본만 봄).

## 한계 (해석 시 주의)

- **gpt-oss-20b 환자는 서버 환자보다 약하다.** 대본 문어체("~이다")를 그대로 읊는 일이 잦고, 묶음 질문에 두 항목을 다 답하거나,
  열린 질문("다른 증상은?")에 음성 사실을 답하기도 한다. 답 하나에 사실이 서버보다 조금 많거나 적을 수 있다.
  → 정보수집 점수의 **절대값**보다 같은 시뮬레이터에서의 **버전 간 비교**와 결정적 지표(거절·하나씩·턴·진단 적중)로 쓴다.
- SAY 절단은 문장 경계 규칙으로 근사한다. 서버의 '-고' 연결 절단("드시고 술도 드세요?")은 재현하지 않는다.
- 진찰 판정: 부위 표현("오른쪽 아랫배 눌러보겠습니다")이 해당 행(복부 촉진)으로 가지 않고 지어낸 소견이 될 수 있고,
  진찰표에 없는 진찰의 지어낸 소견 형식이 어색할 수 있다. 서버 판정 모델과 거절 경계가 다를 수 있다.
- 무키 모드의 Doctor는 gpt-oss-20b라 실제 대회 Doctor(gpt-6-luna)보다 약하다(JSON 형식 실패·빈 응답이 잦을 수 있음).
  점수 절대값보다 같은 설정에서의 에이전트 간 비교·결정적 지표로 쓴다. 로컬 gpt-oss 채점도 luna 채점과 수준이 다르다.
- 자가채점은 공식 채점관이 아니므로 공식 점수와 오프셋이 있다(공개 샘플에서 보정 필요). 합성 증례의 대본·정답은 의학적으로 검토된
  공식 증례가 아니다.
- 실행 시간: 환자 응답 3~15초/턴(로컬 gpt-oss) → 증례당 수 분. luna 응답 지연은 서버 상황에 따름.

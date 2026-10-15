# NOVA 개발 키트 (내 컴퓨터에서 공개 샘플 진료)

대회 서버에 제출하지 않고, 공개 샘플 증례로 내 에이전트를 **내 컴퓨터에서** 끝까지 돌려 보는 도구입니다.
제출용 코드는 시작 패키지(`nova-starter.zip`)의 `run.py`이고, 이 키트는 그 `run.py`를 그대로 불러 실행합니다.

```text
nova-devkit/
├── develop.py        실행 도구
├── nova_local.py     로컬 시뮬레이터(가상 환자·진찰 판정·Doctor 모델 연결, 서버와 같은 규칙)
├── nova_sdk.py       대회 SDK (시작 패키지와 같음)
├── run.py            기본 에이전트 (시작 패키지와 같음)
└── samples/          공개 샘플 증례 (case.json, case.md, model_record.md)
```

## 1. 모델 준비

Doctor 모델 자리에 대회 지정 모델과 같은 **gpt-oss-20b**를 쓰는 것을 권합니다. OpenAI 호환 주소(`/v1/chat/completions`)면
무엇이든 됩니다.

```bash
# Ollama (가장 간단)
ollama pull gpt-oss:20b          # 기본 주소 http://localhost:11434/v1, 모델 이름 gpt-oss:20b

# 또는 vLLM
vllm serve openai/gpt-oss-20b --port 8000
export NOVA_LOCAL_DOCTOR_URL=http://localhost:8000/v1
export NOVA_LOCAL_DOCTOR_MODEL=openai/gpt-oss-20b
```

가상 환자와 진찰 판정도 같은 모델을 씁니다. 서버의 가상 환자는 더 큰 모델이므로, 쓸 수 있다면 따로 지정하세요.

```bash
export NOVA_LOCAL_SIM_URL=https://api.example.com/v1    # OpenAI 호환 상용 API 등
export NOVA_LOCAL_SIM_MODEL=모델이름
export NOVA_LOCAL_SIM_KEY=...                            # 키는 코드·ZIP에 넣지 마세요
```

| 환경변수 | 뜻 | 기본값 |
|---|---|---|
| `NOVA_LOCAL_DOCTOR_URL` / `_MODEL` / `_KEY` | Doctor 모델 (`client.chat`) | `http://localhost:11434/v1` / `gpt-oss:20b` / 없음 |
| `NOVA_LOCAL_SIM_URL` / `_MODEL` / `_KEY` | 가상 환자·진찰 판정 모델 | Doctor와 같음 |
| `NOVA_LOCAL_STREAM` | `1`이면 스트리밍으로 받음(긴 답을 스트리밍으로만 허용하는 API·프록시용) | 사용 안 함 |

## 2. 실행

```bash
python develop.py --list                                  # 샘플 목록
python develop.py --case samples/C10                      # ./run.py로 진료
python develop.py --case samples/C10 --agent ~/my_agent/run.py
python develop.py --case samples/C10 --manual             # 내가 의사가 되어 직접 질문(s)·진찰(e)
```

진료 내용이 화면에 나오고, 끝나면 `results/<증례>-<시각>/`에 저장됩니다.

- `transcript.json`: 턴별 질문·진찰과 응답, Doctor 호출 수와 토큰 수
- `record.md`, `record.json`: 제출한 S·O·A·P 기록과 주진단

`samples/<증례>/case.md`의 대본·진찰 결과표, `model_record.md`의 모범 기록과 비교해 무엇을 놓쳤는지 확인하세요.
모범 기록은 작성 예시이며 채점 기준이 아닙니다. 진료지침 자료를 쓰는 에이전트라면 `NOVA_GUIDELINES_DIR`도 지정하세요.

## 3. 서버와 같은 점

- 처음 받는 정보는 시작 정보(환자 첫마디 한 줄과 활력징후)뿐입니다.
- SAY(질문·설명)와 EXAM(진찰 동작 하나)은 각각 1턴, 최대 50턴, 한 번에 30자(NFC) 이하입니다.
- 진찰은 한 번에 동작 하나만 요청합니다. 여러 진찰을 뭉뚱그리면 `EXAM_NOT_SPECIFIC`, 신체진찰이 아닌 요청(문진·검사·처치·기록 등)이나
  존재하지 않는 진찰은 `EXAM_NOT_RECOGNIZED`이고, 둘 다 턴을 쓰지 않습니다. 예선에는 TEST가 없습니다(`ACTION_NOT_AVAILABLE`).
- 가상 환자는 한 질문에 하나만 짧게 답하고, 한꺼번에 나열해 달라는 요청에는 "한 번에 하나씩 물어봐 주세요."라고만 답합니다.
- `DIAGNOSE`로 S·O·A·P 기록과 주진단을 내면 끝납니다. 기록 형식 오류 코드와 크기 제한, 진료 30분 제한,
  Doctor 모델 호출 한도(세션당 200회, 입력 50만·출력 10만 토큰), 빈 답의 `PROVIDER_RESPONSE_INVALID`도 서버와 같습니다.

## 4. 서버와 다른 점

- **가상 환자·진찰 판정·Doctor 모델이 내가 지정한 모델입니다.** 서버의 모델·지시문과 같지 않으므로 같은 질문에도 답이
  조금 다를 수 있습니다. 서버에서의 동작은 개발 키로 서버 샘플을 실행해 확인하세요(시작 패키지의 `sample.py`).
- **채점하지 않습니다.** 점수는 서버의 샘플 검증(우리 팀 참고 점수)과 공식 평가에서 확인하세요.
- 로컬 모델이 응답 형식을 지키지 못해도 시뮬레이터가 최대한 받아들입니다. 서버는 다시 시도한 뒤
  `PATIENT_RESPONSE_INVALID`나 `EXAMINER_RESPONSE_INVALID`를 돌려줄 수 있으니, 에이전트는 일시 오류를 다시 시도하도록 만드세요.
- 인터넷 차단·읽기 전용 파일 시스템 같은 실행 환경 제한은 재현하지 않습니다. 시작 패키지의 `local.Dockerfile`로 따로 확인하세요.

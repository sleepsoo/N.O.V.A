# N.O.V.A. 2026 참고용 진단 벤치마크

가상 환자 초진 과제와 형식이 비슷한 외부 공개 데이터셋 3개입니다. 개발과 자체 평가에 참고하라고 드리는 자료입니다.

- 대회 평가 증례가 아닙니다. 평가 증례는 한국어 가상 환자 대본과 진찰 결과표 형식이고, 이 데이터는 모두 영어이며 형식도 다릅니다.
- 모두 이미지가 없는 텍스트 데이터이고, 재배포와 연구 결과 공개를 허용하는 라이선스입니다.
- 파일은 공식 배포처의 원본을 그대로 담았습니다. 수집일은 2026-10-10입니다.

| 폴더 | 대회에서 닮은 단계 | 규모 | 라이선스 |
|---|---|---|---|
| `AgentClinic-MedQA/` | 문진·신체진찰·검사·진단 전체 | 증례 215건 | MIT |
| `DDXPlus/` | 문진 (한 번에 하나씩 질문) | 합성 환자 1,292,579명, 질환 49종 | CC BY 4.0 |
| `ACI-Bench/` | 진료 대화를 진료 기록으로 정리 | 대화-기록 쌍 207건 | CC BY 4.0 |

---

## 1. AgentClinic-MedQA

미국 의사국가시험형 문제(MedQA)를 OSCE 진료 시나리오로 재구성한 증례입니다. 환자 진술, 신체진찰 소견, 검사 결과, 정답 진단이 따로 나뉘어 있어 대회의 SAY·EXAM·TEST·DIAGNOSE 구조와 바로 대응합니다.

| 파일 | 내용 |
|---|---|
| `agentclinic_medqa_extended.jsonl` | 증례 215건. 아래 기본판 107건을 모두 포함합니다 |
| `agentclinic_medqa.jsonl` | 기본판 107건. 논문 초판 실험용 |
| `LICENSE.txt` | AgentClinic MIT 라이선스 |
| `LICENSE_MedQA.txt` | 원천 데이터 MedQA의 MIT 라이선스 |

한 줄이 한 증례이며, `OSCE_Examination` 아래에 다음 항목이 있습니다.

| 항목 | 내용 | 대회 증례에서 대응하는 것 |
|---|---|---|
| `Objective_for_Doctor` | 의사에게 주는 과제 설명 | |
| `Patient_Actor` | 인구학 정보, 현병력, 증상, 과거력, 사회력, 계통 문진 | 가상 환자 대본 (SAY에 대한 답) |
| `Physical_Examination_Findings` | 활력징후와 부위별 진찰 소견 | 진찰 결과표 (EXAM 결과) |
| `Test_Results` | 혈액검사, 영상검사 등 결과. 215건 중 211건에 있음 | 본선의 TEST 결과 |
| `Correct_Diagnosis` | 정답 진단 | 주진단 |

- 영상 소견은 글로만 적혀 있고 이미지 파일은 없습니다. 이미지가 들어간 NEJM판은 넣지 않았습니다.
- 출처: https://github.com/SamuelSchmidgall/AgentClinic (커밋 b6fbe22300e99a267a7ac94eaa465ab552eef741)
- 인용:
  - Schmidgall S, Ziaei R, Harris C, Reis E, Jopling J, Moor M. AgentClinic: a multimodal agent benchmark to evaluate AI in simulated clinical environments. arXiv:2405.07960 (2024).
  - Jin D, Pan E, Oufattole N, Weng WH, Fang H, Szolovits P. What Disease does this Patient Have? A Large-scale Open Domain Question Answering Dataset from Medical Exams. arXiv:2009.13081 (2020).

## 2. DDXPlus (영어판 v2)

의료 지식베이스와 규칙 기반 문진 시스템으로 만든 합성 환자 데이터입니다. 환자가 처음 호소한 증상에서 시작해 질문을 하나씩 던져 증상과 병력을 확인하는 문진 연습에 맞습니다. 신체진찰과 검사는 없습니다.

| 파일 | 내용 |
|---|---|
| `release_evidences.json` | 증상·병력 문항 223개. 영어 질문문(`question_en`), 답의 종류, 선택지 의미 |
| `release_conditions.json` | 질환 49종. ICD-10 코드, 관련 증상·병력, 중증도 |
| `release_train_patients.zip` | 학습용 환자 1,025,602명 |
| `release_validate_patients.zip` | 검증용 환자 132,448명 |
| `release_test_patients.zip` | 시험용 환자 134,529명 |
| `LICENSE.txt` | CC BY 4.0 고지와 인용 |

환자 파일은 zip 안에 확장자 없는 CSV 하나가 들어 있습니다. 압축을 풀면 약 850MB이며, `pandas.read_csv`로 zip을 바로 읽을 수 있습니다.

| 열 | 내용 |
|---|---|
| `AGE`, `SEX` | 나이, 성별 |
| `INITIAL_EVIDENCE` | 환자가 처음 호소한 증상 코드 |
| `EVIDENCES` | 환자가 가진 증상·병력 코드 목록. `E_54_@_V_112`처럼 문항과 답을 함께 적습니다 |
| `PATHOLOGY` | 정답 질환 |
| `DIFFERENTIAL_DIAGNOSIS` | 감별진단 목록과 확률 |

- 코드의 뜻은 `release_evidences.json`에서 찾습니다. 대화문 형태가 필요하면 직접 만들어야 합니다.
- 출처: https://doi.org/10.6084/m9.figshare.22687585.v2 (MD5가 figshare 공시값과 일치함을 확인)
- 인용: Fansi Tchango A, Goel R, Wen Z, Martel J, Ghosn J. DDXPlus: A New Dataset For Automatic Medical Diagnosis. NeurIPS 2022 Datasets and Benchmarks Track. arXiv:2205.09148.

## 3. ACI-Bench

의사와 환자의 진료 대화 전문과, 그 대화로 작성한 진료 기록의 쌍입니다. 대회 마지막에 SOAP 기록을 쓰는 단계와 같은 과제입니다. 진단을 맞히는 벤치마크는 아니어서 정답 진단 라벨은 따로 없습니다.

| 경로 | 내용 |
|---|---|
| `aci-bench-corpus/challenge_data/` | 주 데이터. train 67, valid 20, test1·test2·test3 각 40, 합계 207건 |
| `aci-bench-corpus/src_experiment_data/` | 같은 대화의 음성인식판과 교정판. 실험용 |
| `aci-bench-corpus/README.txt` | 배포처 원본 설명 |
| `LICENSE.txt` | CC BY 4.0 고지와 인용 |

- 각 CSV는 `encounter_id`, `dialogue`, `note` 열을 가집니다. 대화에는 `[doctor]`, `[patient]` 화자 표시가 붙어 있습니다.
- `*_metadata.csv`에 나이, 성별, 주소(`cc`), 부가 호소가 있습니다. `encounter_id`로 연결합니다.
- 진료 기록은 주소, 현병력, 계통 문진, 신체진찰, 검사 결과, 평가 및 계획 같은 제목으로 나뉩니다. 초진기록의 S·O·A·P에 대응시킬 수 있습니다.
- 일부 대화는 음성인식 과정에서 의사와 환자 화자 표시가 뒤바뀌어 있습니다. 배포처가 일부러 고치지 않았다고 밝혔습니다.
- 출처: https://doi.org/10.6084/m9.figshare.22494601.v1 (원본 zip의 MD5 e3e2456f1e84cdae844f122890c9340c, 공시값과 일치)
- 인용: Yim W, Fu Y, Ben Abacha A, Snider N, Lin T, Yetisgen M. ACI-BENCH: a Novel Ambient Clinical Intelligence Dataset for Benchmarking Automatic Visit Note Generation. Scientific Data 10, 586 (2023).

---

## 이용 시 주의

- 대회 규칙상 외부 데이터는 연구 결과 공개를 허용하는 라이선스일 때 쓸 수 있고, 출처와 생성 과정을 밝혀야 합니다. 이 데이터로 학습하거나 변환 데이터를 만들었다면 각 절의 인용과 처리 과정을 기록해 두세요.
- 실행 중에는 외부에서 자료를 내려받을 수 없습니다. 실행 중에 쓰려면 제출물 크기 제한 안에서 함께 담아야 합니다.
- 세 데이터 모두 영어입니다. 대회의 한국어 30자 질문 제한에 맞추려면 번역이나 재작성이 필요합니다.
- 재배포할 때는 각 폴더의 `LICENSE` 파일과 인용 표기를 함께 유지하세요. CC BY는 출처 표시가 필수이고, 내용을 바꿨다면 바꾼 사실을 밝혀야 합니다.
- 연구·평가용 데이터입니다. 실제 진료 판단에 쓰면 안 됩니다.

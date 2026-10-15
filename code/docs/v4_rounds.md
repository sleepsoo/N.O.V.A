# v4 라운드 기록 (2026-10-14)

- 구현 폴더: `code_v4/` (`code/` 복사 후 작업, runs·__pycache__ 제외). 설계서: `code/docs/v4_spec.md`.
- 개발 키 사용 0, nova.snubhai.org 호출 0. 로컬 검증은 로컬 vLLM gpt-oss-20b(:8010, 무키)만 사용.
- 조정자 결정: ① 짝 질문 = 음성 선별 배경 항목 화이트리스트만 허용(PAIR_POLICY=negscreen, 기본), 증상 탐색은 단일 항목 ② 진찰 기본 = 핵심 8 + 특이 ≤5 + 보충(flex) ③ 턴 하드캡 40 예외 없음(44턴 변형 없음).
- 제출물 변경 지시(진행 중 2회): 6개 → 2개 → **최종 1개** `제출/submission_v4.zip`(c8flex·v4 설명·40턴). u12 팔은 zip을 만들지 않고 코드의 preset 전환만 남김.

## 1. 변경 파일

| 파일 | 내용 |
|---|---|
| `agent/encounter.py` | §3.2 하드캡: `server_remaining` 분리, `turns_remaining = min(서버 잔여, TURN_CAP − turn)`(성공·TURN_USING 거절 모두) |
| `agent/guidelines.py` | code_js 이식(P1) + `sanitize()`(용량·횟수·증량·성분명 문장, 저자·소속 줄, 권고수준 꼬리표 제거, 1,800자) + `hint_interview(enc, clean)` + `hint_plan(enc, kinds_mgmt, kinds_ovw, clean)`(기본값 = code_js) |
| `agent/interview.py` | P3 주입(code_js 동일) + intake 감별 형식 "한국어명 (English)"(v4일 때만) |
| `agent/assess.py` | P4 주입(code_js 동일) + `strip_unsupported_modifiers()`: 영문명에 근거 없는 한국어 수식어 제거(sim S03 "급성 **전이성** 중이염" 대응) |
| `agent/explain.py` | P5 주입(code_js 동일, 대조군 전용) + `render_plan` 교육 칸 v4 플래그 |
| `agent/say.py` | `pair_problem`(단일 항목 강제·negscreen 화이트리스트), `statement_ok`, `SYMPTOM_NOUN`/`symptom_topic`, `is_patient_question` |
| `agent/v3.py` | `SAFETY_QS` 갑상선 짝 문구 → `천식 있으세요?`·`가만히 있어도 숨이 차세요?` |
| `agent/record.py` | `education_text(v4=True)`("다음 방문 시 교육 예정" 없음), `unsupported_claims()`(claims 필터), O칸 spo2→활력 오매칭 표기 |
| `agent/note2.py` | `reconcile_ros()`, 누락 안전망(`safety_net`, ROS Others ≤5), late ICE(S-narr 입력 + HPI 마지막 줄), `render_fixed(facts=)` |
| `agent/v4.py` (신규) | 문진(공감·주제 개방·sweep+즉시 주제 후속·luna 계획 1회·우선순위 큐·ICE), 진찰(c8flex/u12, 조건 규칙, SECTION_ORDER, 간·비장→복부 촉진), plan_say(D2, 후보 2개 검증, 부록 C 폴백, FAQ 16키), 설명 루프(§5.3 tail 강제·final+답 예약·앞당김) |
| `run.py` | DEFAULTS(V4·TURN_CAP·EXAM_POLICY·EXPLAIN_MODE·PAIR_POLICY·GUIDE·GUIDE_CITE·X_MAX·EXAM_SPEC_MAX), 프리셋 v4_40/v4_40i/v4_40c/js_bal44, `preset.json`(zip 루트) 로드, P2 이식, `consult_v4`, finish_v2 claims 필터·cite_line |
| `tools/make_submission.sh` | 2번째 인자 preset.json, 백슬래시·금지 경로 검사 |
| `tools/sim_metrics.py` (신규) | 로컬 시뮬 결정적 지표 집계 |
| `tools/presets/{core8,u12}.json` | 팔 설정 예시(zip에는 넣지 않음: 기본값 = core8) |
| `tests/test_v4.py`, `tests/u13_harness.py` (신규) | U1~U14 + 추가(응급 소견 승격, GUIDE 스위치, 진단 수식어) |
| `tests/test_v3.py` | v3 회귀 테스트 env에 `NOVA_AGENT_V4=0` 추가(기본값이 v4로 바뀌어서) |

## 2. 테스트
- `PYTHONPATH=<scratchpad>/pylib python -m pytest tests -q` → **127 passed** (기존 96 + v4 31).
- `cd tests && python3 test_agent.py` → 53 tests OK (U14).
- U13: 대조군(V3=0·bal44·GUIDE=1)의 plan_q·dx·plan_and_say 프롬프트가 code_js와 문자열 동일(hint 주입 위치 포함, C10 가짜 서버).

## 3. 설계서와 다르게(또는 더해) 구현한 점
1. **특이 진찰 보충**: luna 특이가 3개 미만이면 주 카테고리 진찰(core·flex·RISKY 제외)로 3개까지 채움. 로컬 gpt-oss가 특이를 2개만 줄 때 갑상선 촉진(flex4)이 충수염 증례에 들어가던 문제(sim S01-v4a) 대응.
2. **진찰 응급 소견 → 응급 처치 승격**: 반발통·근성방어·복막/수막 자극(+) 또는 활력 불안정이면 luna가 '외래'라고 해도 disposition 맨 앞에 응급 줄, 재진 문장을 "오늘 바로 응급실에서 진료를 받으세요."로(sim S01-v4a: 충수염인데 "1~2주 뒤 재진"을 말함).
3. **sweep 음성 판정 보강**: "숨이 차거나 쌕쌕거리는 소리는 없어요."처럼 끝이 부정이면 음성(즉시 후속 질문·두 번째 sweep 안 함).
4. **갑상선 안전 slot**은 감별에 *항진증*(그레이브스·항진·중독)이 있을 때만(저하증 감별로 천식·숨참을 묻던 C01-v4c 낭비 대응). 관련 기본 범주의 갑상선 특이 승격은 주 카테고리만(소아 귀통증에 intake가 붙인 insomnia 잡음 대응).
5. D1 프롬프트의 "반드시 넣을 안전 항목"은 코드가 그 문구로 직접 묻으므로 "같은 내용은 내지 말 것"을 덧붙임(중복 방지).
6. claims 필터는 A·P 외에 S(HPI)에도 적용, 위치는 `finish_v2`(v4일 때) — 설계서의 render_plan/render_assessment 끝과 효과 동일.
7. negscreen 화이트리스트 문구: `고혈압이나 당뇨 있으세요?`, `결핵이나 간염 앓은 적 있으세요?`, `수술이나 입원 경험 있으세요?`(설계서 "수술이나 입원한 적"은 기존 검증기 pair_clause에 걸려 "경험"으로 바꿈), `약이나 음식 알레르기 있으세요?`, `가족 중 고혈압이나 당뇨 있나요?`. 증상 짝(`가슴 통증이나 숨참은…`)은 조정자 결정에 따라 제외. 본문 큐 여분(우선 3)에서만 사용.
8. 진단명 수식어 보정(조정자 요청): `normalize_dx`에서 영문명에 근거 없는 한국어 수식어(전이성·악성·만성·재발성·이차성·특발성·세균성 등 21종) 제거. COPD·CKD는 '만성' 근거로 인정. 모든 흐름에 적용.

## 4. 로컬 시뮬(무키, Doctor·환자·진찰·채점 = 로컬 gpt-oss-20b)

결정적 지표(`tools/sim_metrics.py`). 진찰 적중 = 서버 행 코드(r##)로 매칭된 진찰표 행 수 / 요청 수 / 표 행 수.

| 실행 | 턴 | 거절 | 하나씩 | 절단 | 문진 Q | 진찰 적중/요청/표 | 안전 위반 | 마지막 3턴 | 미수행 소견(S/A/P) | 진단 | Doctor 호출 | 로컬 채점(참고) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S01 v4 (v4c) | 38 | 0 | 0 | 0 | 14 | 14/14/24 (58%) | 0 | followup·warning·teach | 0 | 적중 | 7 | 38 |
| S03 소아 v4 (v4c) | 39 | 1(진찰) | 0 | 0 | 14 | 10/13/22 (45%) | 0 | OK | 0 | 적중 | 6 | 52 |
| S06 만성 v4 (v4c) | 39 | 0 | 0 | 0 | 14 | 10/14/22 (45%) | 0 | OK | 0 | 적중 | 7 | 52 |
| C01 v4 (v4d) | 39 | 0 | 0 | 0 | 14 | 13/14/24 (54%) | 0 | OK | 0 | **오답**(범불안장애) | 6 | 26 |
| C03 v4 (v4c) | 38 | 0 | 0 | 0 | 12 | 16/16/20 (80%) | 0 | OK | 0 | 적중 | 6 | 78 |
| C10 v4 (v4c) | 39 | 0 | 0 | 0 | 14 | 13/14/23 (57%) | 0 | OK | 0 | 적중 | 7 | 63.8 |
| S03 code_js 대조 | 42 | 1 | 0 | 1 | 22 | 10/10/22 (45%) | 0 | — | 0 | 적중 | 9 | 78 |
| S01 code_js 대조(기존) | 42 | 0 | 0 | 1 | 22 | 9/11/24 (38%) | 0 | — | 0 | 적중 | 8 | 76 |

- 6/6 턴 ≤ 40, 거절은 진찰 NOT_SPECIFIC 1건(S03 하지 말초 진찰 — 합성 증례 표에 없음), 하나씩 0, 절단 0, 안전 위반 0, 마지막 3턴 6/6, 미수행 음성 단정 0(O칸은 수행 진찰 수 = 기록 항목 수 확인).
- **진찰표 적중률(공개 3증례)**: C01 54% · C03 80% · C10 57% → 평균 **64%**. 설계서 추정 48%→63%와 일치(로컬은 이름 일치 결정 매칭이라 서버보다 관대할 수 있음). 결정 매칭만 따지면 범용 12행(core8+flex 4)이 세 증례 모두 12/12 적중.
- 합성 증례(비관 OOD): S01 58%, S03 45%, S06 45% (code_js S01 38%, S03 45%).
- 로컬 채점은 gpt-oss가 같은 증례에서도 체크리스트 총 항목 수를 27~64로 다르게 잡는 등 변동이 커 판정에 쓰지 않음. 다만 v4가 문진 14문항이라 정보수집이 낮게 잡히는 경향은 설계서 §7.2 예상(문진 −3~−7%p)과 같은 방향.
- 이전 라운드: S01-v4a(특이 보충·응급 승격 전, 13/14/24, 재진 "1~2주" 오류) → v4c에서 해소. S03-v4b 진단 "급성 전이성 중이염" → 수식어 보정 후 v4c "급성 중이염".

## 5. 제출물
- `제출/submission_v4.zip` (179,321 bytes): run.py·requirements.txt·nova_sdk.py·agent/(22 entries), preset.json 없음 → 기본 팔(v4_40·TURN_CAP 40·c8flex·v4 설명·negscreen·GUIDE 1).
- 검증: 빈 폴더에 zipfile로 풀어 `import agent, run` 성공, 백슬래시 0, `__pycache__`·runs·tests 0, 키 패턴 grep 0.
- **팔 전환**: zip 루트 `preset.json` 한 줄 또는 환경변수 `NOVA_AGENT_<키>`. 예) u12 = `{"EXAM_POLICY": "u12"}`.
- **지침 주입 on/off**: `{"GUIDE": 0}`(preset.json) 또는 `NOVA_AGENT_GUIDE=0` → prepare()가 인덱스를 만들지 않고 모든 hint가 '' (테스트 `test_guide_off_switch`). 참고 지침 줄만 끄려면 `GUIDE_CITE: 0`.

## 6. 미해결
1. C01 로컬 진단 오답 2회(로컬 gpt-oss가 수면제 사용장애 대신 불면/불안). luna(v3-gen) 실측은 적중했으므로 로컬 Doctor 한계로 보나, 문진 14문항에서 진정제 slot 3개를 쓰고도 감별이 바뀐 점은 샘플 검증에서 확인 필요.
2. 로컬 gpt-oss의 설명 문장 품질(사실 오류·무관 문장)은 검증기가 형식만 거르므로 막지 못함. luna에서는 덜할 것으로 보지만 확인 필요.
3. `흉곽 시진`·`복부 시진` 서버 매칭은 여전히 미관측(로컬은 이름 일치라 통과).
4. 진단명이 증상명("저신장 (Short Stature)", C03 로컬)으로 나오는 경우가 남음 — 프롬프트 규칙은 있으나 normalize 단계 강제는 없음(U13 프롬프트 동일성 유지 때문에 dx 프롬프트는 건드리지 않음).
5. 샘플 검증·리더보드 미실행(개발 키 금지).

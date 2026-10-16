# 리더보드 대리 측정 (개발 키 최소 사용)

리더보드 숨은 증례와 비슷한 합성 증례 4개(A1 급성 충수염 · A2 철결핍성 빈혈 · A3 요추 추간판 탈출증 · A4 소아 급성 중이염)로
제출 zip 두 개를 같은 조건에서 진료시키고, gpt-6.1-sol로 6영역을 채점해 **차이**를 본다.

## 실행 (팀원 PC, 저장소 루트에서)
```bash
git pull                                   # 브랜치 v10-info-gathering
cd code_v10/tools/measure
export NOVA_DEV_KEY=...                    # 환경변수로만. 파일·코딩 도구에 넣지 말 것
python measure.py --dry                    # 계획·예상 호출 수만(호출 0)
python measure.py                          # v10b vs v17 × A1~A4, 끝나면 results/summary.md
```
- 예상 사용량: gpt-6-luna 약 370회(하루 1,000), gpt-6.1-sol 8회(하루 100). `--max-luna`·`--max-sol`을 넘으면 멈춘다.
- 더 줄이기: `--cases A1 A3`(절반), 또는 로컬 모델이 있으면 `export NOVA_LOCAL_SIM_URL=… NOVA_LOCAL_SIM_MODEL=…`로
  가상 환자·진찰 판정을 로컬에서(luna 약 90회).
- 중간에 끊겨도 다시 실행하면 끝난 진료·채점은 건너뛴다. 결과: `results/<버전>/<증례>/` transcript·record·grade.
- 판정 줄: 정보수집+의사소통 합 ≥ +1.5 이고 안전·진단 하락 ≤ 0.5면 '리더보드 제출 후보'.

## 한계
- 채점은 공식 지시문·루브릭이 아니라 공식 영역 문구 기반 대리 채점. 절대 점수보다 **같은 증례에서의 버전 차이**만 본다.
- 가상 환자는 공식(sol)과 달리 luna. 증례 4개는 표본이 작으니 차이 1점 안팎은 변동으로 본다.
- `results/` 폴더 통째로 공유해 주면 로그를 보고 원인을 분석한다(키는 들어 있지 않음).

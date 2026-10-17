#!/usr/bin/env bash
# 사용자 터미널에서 한 번 실행: 키를 화면에 보이지 않게 입력받아(파일·기록에 남기지 않음) 보정 측정 → 결과 요약 출력.
# 대회 규칙상 개발 키는 코딩 도구(Claude 등)에 넘기지 말고 이 스크립트를 사람이 직접 실행할 것.
set -e
cd "$(dirname "$0")"
if [ -z "$NOVA_DEV_KEY" ]; then
  read -r -s -p "NOVA 개발 키 입력(화면에 안 보임): " NOVA_DEV_KEY; echo
fi
export NOVA_DEV_KEY
python3 measure.py --calibrate --dry
python3 measure.py --calibrate "$@"
echo; echo "끝. 결과: $(pwd)/results/summary.md — Claude에게 '결과 분석해줘'라고 하면 됩니다."

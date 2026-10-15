#!/usr/bin/env bash
# 개발 키트 develop.py로 완전 로컬 실행(크레딧·채점 없음).
# 사용: bash tools/local_devkit.sh [C01|C03|C10] [DOCTOR_URL] [DOCTOR_MODEL] [SIM_URL] [SIM_MODEL]
# 기본: Doctor http://localhost:8010/v1 openai/gpt-oss-20b, 가상 환자·진찰 http://localhost:8002/v1 qwen38
set -uo pipefail
CODE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEVKIT="$CODE_DIR/../정보/개발키트"
CASE="${1:-C10}"
export NOVA_LOCAL_DOCTOR_URL="${2:-${NOVA_LOCAL_DOCTOR_URL:-http://localhost:8010/v1}}"
export NOVA_LOCAL_DOCTOR_MODEL="${3:-${NOVA_LOCAL_DOCTOR_MODEL:-openai/gpt-oss-20b}}"
export NOVA_LOCAL_SIM_URL="${4:-${NOVA_LOCAL_SIM_URL:-http://localhost:8002/v1}}"
export NOVA_LOCAL_SIM_MODEL="${5:-${NOVA_LOCAL_SIM_MODEL:-qwen38}}"

for url in "$NOVA_LOCAL_DOCTOR_URL" "$NOVA_LOCAL_SIM_URL"; do
  if ! curl -s -m 5 "$url/models" >/dev/null; then
    echo "모델 서버 응답 없음: $url — 건너뜁니다." >&2
    exit 2
  fi
done

SAMPLE_DIR="$CODE_DIR/../공개 샘플데이터/$CASE"
cd "$DEVKIT" && python3 develop.py --case "$SAMPLE_DIR" --agent "$CODE_DIR/run.py" --out "$CODE_DIR/runs/devkit" --quiet

#!/usr/bin/env bash
# 제출 ZIP 생성: run.py, requirements.txt, nova_sdk.py, agent/ 패키지만 담는다.
# 사용: bash tools/make_submission.sh [출력경로]
set -euo pipefail
CODE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$CODE_DIR/../제출/submission_v1.zip}"
mkdir -p "$(dirname "$OUT")"
OUT="$(cd "$(dirname "$OUT")" && pwd)/$(basename "$OUT")"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

for f in run.py requirements.txt nova_sdk.py; do
  [ -f "$CODE_DIR/$f" ] || { echo "필수 파일 없음: $f" >&2; exit 1; }
  cp "$CODE_DIR/$f" "$STAGE/"
done
mkdir -p "$STAGE/agent"
for f in "$CODE_DIR"/agent/*.py; do cp "$f" "$STAGE/agent/"; done

# 문법 검사 + 키 문자열 유출 검사
python3 -m py_compile "$STAGE"/run.py "$STAGE"/nova_sdk.py "$STAGE"/agent/*.py
find "$STAGE" -name '__pycache__' -type d -prune -exec rm -rf {} +
if grep -rIl 'nova_[A-Za-z0-9]\{16,\}' "$STAGE" >/dev/null 2>&1; then
  echo "키로 보이는 문자열이 포함되어 있습니다. 중단." >&2; exit 1
fi

rm -f "$OUT"
(cd "$STAGE" && zip -q -r -X "$OUT" run.py requirements.txt nova_sdk.py agent)

# 검증: 루트 run.py, 크기
unzip -l "$OUT" | awk 'NR>3 {print}' | head -n -2
unzip -Z1 "$OUT" | grep -qx 'run.py' || { echo "루트에 run.py 없음" >&2; exit 1; }
unzip -Z1 "$OUT" | grep -qx 'requirements.txt' || { echo "루트에 requirements.txt 없음" >&2; exit 1; }
SIZE=$(stat -c %s "$OUT")
[ "$SIZE" -le 50000000 ] || { echo "50MB 초과: $SIZE" >&2; exit 1; }
echo "OK: $OUT ($SIZE bytes)"

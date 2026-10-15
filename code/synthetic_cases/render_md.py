"""합성 증례 case.json -> case.md 재생성 (json을 고친 뒤 실행).

  cd code/synthetic_cases && python3 render_md.py S01 S02 S03 S04 S05 S06
"""
import json
import sys
from pathlib import Path

for d in sys.argv[1:]:
    d = Path(d)
    c = json.loads((d / 'case.json').read_text(encoding='utf-8'))
    si = c['start_information']
    assert c['patient_script'].startswith(si['opening'])
    vit = '  \n'.join(si['vital_signs'].split('\n'))
    rows = '\n'.join(f"| {r['exam']} | {r['result']} |" for r in c['exam_results'])
    ref = c['reference']
    md = f"""# 합성 증례 {c['case_id']}

유형: {c['meta']['type']} · 대본 사실 수 약 {c['meta']['fact_count']}개 · 진찰표 {len(c['exam_results'])}행

## 시작 정보 (Doctor Agent가 받는 내용)

> {si['opening']}

{vit}

## 가상 환자 대본 (가상 환자만 봄)

{c['patient_script']}

## 진찰 결과표 (진찰 판정 모델만 봄)

| 진찰 | 결과 |
|---|---|
{rows}

## 정답 진단·참고 기록 (채점용)

- 주진단: {ref['diagnosis']}
- 인정 표현(accepted_diagnoses): {' / '.join(c['accepted_diagnoses'])}

### 근거

```
{ref['evidence']}
```

### 감별진단

```
{ref['differential']}
```

### 필요 검사

```
{ref['tests']}
```

### 처치·추적·교육

```
{ref['plan']}
```

### 핵심 병력 체크리스트

""" + '\n'.join(f'- {x}' for x in ref['key_history']) + "\n\n### 핵심 진찰\n\n" + '\n'.join(f'- {x}' for x in ref['key_exams']) + '\n'
    (d / 'case.md').write_text(md, encoding='utf-8')
    print(c['case_id'], c['meta']['type'], c['accepted_diagnoses'][0], c['meta']['fact_count'], len(c['exam_results']),
          len(ref['key_history']), all(k in {r['exam'] for r in c['exam_results']} for k in ref['key_exams']))

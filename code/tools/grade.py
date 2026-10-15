"""자가 채점: 개발 키로 세션 밖 gpt-6-luna(기본) 또는 gpt-6.1-sol을 불러 run 결과를 6개 영역으로 채점한다.

  export NOVA_DEV_KEY=...
  python tools/grade.py --run runs/C01-2026... [--model openai/gpt-6-luna|openai/gpt-6.1-sol]

입력: 공개 샘플 case.md(대본+진찰표), model_record.md(참고), 대화·진찰 로그(transcript.md), 제출 기록(record.md).
결과: runs/<dir>/grade_<model>.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(1, str(Path(__file__).resolve().parent.parent))  # code/ (nova_sdk)
import common  # noqa: E402

RUBRIC = """당신은 N.O.V.A. 2026 가상 환자 진료 대회의 채점관입니다. 아래 증례 원문(가상 환자 대본·진찰 결과표), 참고용 모범 기록,
Doctor Agent의 실제 진료 로그(대화·진찰)와 제출한 초진 기록·주진단을 보고 100점 만점으로 채점하세요.

영역과 배점:
1. 정보수집 (25): 필요한 문진·진찰을 실제로 했고 기록했는가. 대본의 핵심 병력(현병력·과거력·약물·가족력·사회력·계통 문진)과
   진찰표의 핵심 진찰을 얼마나 실제로 물었/했고 S·O 칸에 기록했는가.
2. 진단추론 (15): 주진단이 정확한가(5점 척도로 판정: 5=정답과 동일/동의어, 4=매우 근접, 3=관련 있으나 덜 구체적, 2=부분적, 1=오답)와
   근거·감별진단의 타당성.
3. 검사·추적 (10): 필요한 검사(P.tests)와 추적 계획(재진 시점, 경고 증상)을 세웠는가.
4. 안전 (15): 처치 결정이 적절하고 환자에게 해롭지 않은가(위험한 처방·급격한 중단·응급 놓침 등).
5. 의사소통 (15): 진료 중 실제 SAY로 공감·설명(진단, 검사, 치료, 경고 증상, 생활 교육)·질문 기회를 주었는가.
   기록에만 쓰고 말하지 않은 교육은 인정하지 않음.
6. 효율 (20): 불필요한 진료 행동(중복 질문, 거절된 요청, 무관한 진찰, '한 번에 하나씩' 응답을 부른 질문)과 모델 사용 비용.

채점 원칙:
- 서버 로그(대화·진찰)와 제출 기록만 근거로 한다. 묻지 않은 내용을 기록에 적어도 인정하지 않는다. 확인 내용과 다르게 적으면 감점.
- (-) 음성 소견도 실제로 물어본 경우만 인정한다. 진찰 소견은 결과를 받은 턴 번호가 있어야 가장 높게 인정.
- 모범 기록은 형식·수준 참고이며 만점 답안이 아니다.

JSON 하나만 출력:
{"scores": {"정보수집": 0-25, "진단추론": 0-15, "검사·추적": 0-10, "안전": 0-15, "의사소통": 0-15, "효율": 0-20},
 "total": 0-100, "diagnosis_5pt": 1-5,
 "deductions": {"정보수집": ["감점 사유"], "진단추론": [...], "검사·추적": [...], "안전": [...], "의사소통": [...], "효율": [...]},
 "missed_key_questions": ["놓친 핵심 문진"], "missed_key_exams": ["놓친 핵심 진찰"], "record_errors": ["기록 오류"],
 "top_improvements": ["가장 효과 큰 개선 3~5개"]}"""


RUBRIC_OFFICIAL = """당신은 N.O.V.A. 2026 가상 환자 진료 대회의 공식 채점관입니다. 공식 영역과 기준(문구 그대로):
1. 정보수집 (25): 필요한 문진·진찰을 실제로 했고 기록했는가
2. 진단추론 (15): 주진단이 정확하고 근거와 감별진단이 타당한가. 주진단은 5점 척도로 판정
3. 검사·추적 (10): 필요한 검사와 추적 계획을 세웠는가
4. 안전 (15): 처치 결정이 적절하고 환자에게 해롭지 않은가
5. 의사소통 (15): 환자와 잘 소통하고 필요한 설명을 했는가
6. 효율 (20): 불필요한 진료 행동과 모델 사용 비용을 줄였는가
공식 유의사항: 채점은 서버에 기록된 대화·진찰 로그와 제출한 초진 기록·최종 진단을 근거로 함. 질문하지 않은 내용을 기록에 적어도
수행한 것으로 인정되지 않음. 초진 기록의 판단 근거와 향후 계획, 환자와 나눈 대화도 평가에 반영.

세부 채점 방법(엄격 적용):
- 정보수집: 먼저 가상 환자 대본의 핵심 사실(병력의 (+)/(-) 항목, 과거력·약물·가족력·사회력·ROS·걱정)과 진찰 결과표의 행을
  각각 체크리스트로 만들고, 실제로 묻거나 시행해 기록까지 한 항목의 비율로 점수를 매기세요(25 × 문진 커버리지 0.6 + 진찰
  커버리지 0.4 정도). 체크리스트 항목 수와 확인된 수를 출력에 적으세요. 일부만 확인하면 높은 점수를 주지 마세요.
- 의사소통: 대화에서 실제로 말한 것만. 공감, 걱정·기대 확인과 그에 대한 직접 답, 진단의 의미를 환자 수준으로, 검사 목적,
  치료 선택지와 함의, 경고 증상, 재진 시점, 이해 확인과 질문 응답이 모두 구체적이어야 높은 점수. 짧은 정형 문장 나열은 중간 이하.
- 효율: 중복·무관 질문, 거절, '한 번에 하나씩' 응답, 과도한 턴과 모델 사용량을 감점.
- 나머지 영역은 모범 기록 수준과 비교해 엄격하게.

JSON 하나만 출력:
{"checklist": {"history_total": n, "history_done": n, "exam_total": n, "exam_done": n},
 "scores": {"정보수집": 0-25, "진단추론": 0-15, "검사·추적": 0-10, "안전": 0-15, "의사소통": 0-15, "효율": 0-20},
 "total": 0-100, "diagnosis_5pt": 1-5,
 "deductions": {"정보수집": ["감점 사유"], "진단추론": [...], "검사·추적": [...], "안전": [...], "의사소통": [...], "효율": [...]},
 "missed_key_questions": ["놓친 핵심 문진"], "missed_key_exams": ["놓친 핵심 진찰"], "record_errors": ["기록 오류"],
 "top_improvements": ["가장 효과 큰 개선 3~5개"]}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True)
    ap.add_argument('--model', default='openai/gpt-6-luna')
    ap.add_argument('--effort', default='medium')
    ap.add_argument('--rubric', default='self', choices=['self', 'official'],
                    help='official: 공식 영역 문구 + 체크리스트 비례 엄격 채점(공식 샘플 검증 보정용)')
    args = ap.parse_args()
    run_dir = Path(args.run)
    summary = json.loads((run_dir / 'summary.json').read_text(encoding='utf-8'))
    alias = summary.get('alias')
    if not alias:
        sys.exit('공개 샘플 별칭(C01/C03/C10)을 알 수 없는 run입니다.')
    case_md = (common.SAMPLES / alias / 'case.md').read_text(encoding='utf-8')
    model_md = (common.SAMPLES / alias / 'model_record.md').read_text(encoding='utf-8')
    transcript = (run_dir / 'transcript.md').read_text(encoding='utf-8')
    record = (run_dir / 'record.md').read_text(encoding='utf-8')
    usage = (f"턴 {summary.get('turns')}, Doctor 호출 {summary.get('doctor_calls')}회, 입력 {summary.get('doctor_input_tokens')}"
             f" / 출력 {summary.get('doctor_output_tokens')} 토큰, 거절 {summary.get('refused')}회, "
             f"'한 번에 하나씩' 응답 {summary.get('one_at_a_time')}회")
    user = (f'# 증례 원문\n{case_md}\n\n# 참고 모범 기록\n{model_md}\n\n# Doctor Agent 진료 로그\n{transcript}\n\n'
            f'# 모델 사용량\n{usage}\n\n# 제출 기록\n{record}')

    from nova_sdk import Client, NovaError
    client = Client(api_base=os.environ.get('NOVA_API_BASE', common.API_BASE_DEFAULT), token=common.dev_key(),
                    sample=True)
    result = None
    for attempt in range(3):
        try:
            reply = client.chat([{'role': 'system', 'content': RUBRIC_OFFICIAL if args.rubric == 'official' else RUBRIC}, {'role': 'user', 'content': user}],
                                model=args.model, reasoning_effort=args.effort, max_tokens=6000)
        except NovaError as exc:
            print('채점 호출 오류:', exc.code)
            continue
        text = reply['choices'][0]['message']['content'] or ''
        m = re.search(r'\{.*\}', text, flags=re.S)
        try:
            result = json.loads(m.group(0)) if m else None
        except ValueError:
            result = None
        if result:
            result['usage'] = reply.get('usage')
            break
    if not result:
        sys.exit('채점 결과를 파싱하지 못했습니다.')
    name = args.model.split('/')[-1]
    (run_dir / f'grade_{name}{"_official" if args.rubric == "official" else ""}.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    scores = result.get('scores') or {}
    print(f'{alias} {name}: total={result.get("total")} ' + ' '.join(f'{k}={v}' for k, v in scores.items())
          + f' dx5={result.get("diagnosis_5pt")}')
    for k in ('missed_key_questions', 'missed_key_exams', 'record_errors', 'top_improvements'):
        print(f'- {k}: {result.get(k)}')


if __name__ == '__main__':
    main()

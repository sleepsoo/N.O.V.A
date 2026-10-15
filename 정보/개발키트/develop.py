"""공개 샘플 증례로 내 에이전트를 내 컴퓨터에서 실행합니다(채점 없음).

  python develop.py --list                              # 들어 있는 샘플 증례
  python develop.py --case samples/C10                  # ./run.py의 prepare()·consult()로 진료
  python develop.py --case samples/C10 --agent ../my_agent/run.py
  python develop.py --case samples/C10 --manual         # 내가 직접 의사가 되어 가상 환자와 대화

모델 연결(OpenAI 호환 주소)은 환경변수로 정합니다. 자세한 내용은 README.md를 보세요.
  NOVA_LOCAL_DOCTOR_URL / _MODEL / _KEY   Doctor 모델(대회의 gpt-oss-20b 자리)  기본: Ollama gpt-oss:20b
  NOVA_LOCAL_SIM_URL / _MODEL / _KEY      가상 환자·진찰 판정 모델                기본: Doctor와 같음
"""
import argparse
import importlib.util
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from nova_local import LocalClient, NovaError, Simulator, load_case, save_result  # noqa: E402


def load_agent(path):
    path = Path(path).resolve()
    sys.path.insert(0, str(path.parent))  # 에이전트 폴더의 모듈(nova_sdk 등)을 먼저 찾도록
    spec = importlib.util.spec_from_file_location('nova_agent', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ('prepare', 'consult'):
        if not callable(getattr(module, name, None)):
            raise SystemExit(f'{path}에 {name}() 함수가 없습니다.')
    return module


def manual(client):
    print('\n직접 진료: "s 질문", "e 진찰 동작", "q" 종료 (한 번에 30자 이하)')
    while True:
        line = input('> ').strip()
        if line in ('q', 'quit', 'exit'):
            return
        kind, _, content = line.partition(' ')
        try:
            if kind == 's':
                client.say(content)
            elif kind == 'e':
                client.exam(content)
            else:
                print('s 또는 e로 시작하세요.')
        except NovaError as exc:
            used = exc.code in ('EMPTY_CONTENT', 'CONTENT_TOO_LONG', 'EXAM_NOT_SPECIFIC', 'EXAM_NOT_RECOGNIZED')
            print(f'(오류 {exc.code}: 답은 없고 1턴을 썼습니다)' if used else f'(오류 {exc.code}: 턴을 쓰지 않았습니다)')
        except ValueError as exc:
            print(f'({exc})')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--case', help='샘플 폴더 또는 case.json (예: samples/C10)')
    parser.add_argument('--agent', default='run.py', help='prepare()와 consult(client, state)가 있는 파일 (기본 ./run.py)')
    parser.add_argument('--manual', action='store_true', help='에이전트 대신 직접 질문·진찰')
    parser.add_argument('--minutes', type=float, default=30, help='진료 제한 시간(분, 대회와 같은 30분). 0이면 제한 없음')
    parser.add_argument('--out', default='results', help='결과 폴더')
    parser.add_argument('--quiet', action='store_true', help='대화를 화면에 출력하지 않음')
    parser.add_argument('--list', action='store_true', help='samples/ 아래 증례 목록')
    args = parser.parse_args()

    if args.list or not args.case:
        cases = sorted(p.parent for p in (HERE / 'samples').glob('*/case.json'))
        for folder in cases:
            case = load_case(folder)
            print(f'{folder.relative_to(HERE)}  {case["start_information"]["opening"][:60]}')
        if not cases:
            print('samples/ 폴더에 공개 샘플이 없습니다. 개발 가이드에서 샘플 ZIP을 받아 samples/에 푸세요.')
        return

    case = load_case(args.case)
    simulator = Simulator(case, minutes=args.minutes, log=None if args.quiet else print)
    for role, endpoint in (('Doctor', simulator.doctor), ('가상 환자·진찰', simulator.sim)):
        try:
            endpoint.complete([{'role': 'user', 'content': '안녕하세요'}], max_tokens=256)
        except NovaError:
            raise SystemExit(f'{role} 모델에 연결하지 못했습니다: {endpoint.model} @ {endpoint.base_url}\n'
                             '모델 서버가 켜져 있는지, NOVA_LOCAL_* 환경변수가 맞는지 확인하세요(README.md 1장).')
    client = LocalClient(simulator)
    print(f'증례 {case["case_id"]} · Doctor {simulator.doctor.model} @ {simulator.doctor.base_url}'
          f' · 가상 환자·진찰 {simulator.sim.model} @ {simulator.sim.base_url}')
    print(f'시작 정보: {case["start_information"]["opening"]}\n{case["start_information"]["vital_signs"]}\n')
    started = time.time()
    try:
        if args.manual:
            manual(client)
        else:
            agent = load_agent(args.agent)
            state = agent.prepare()   # 대회에서는 준비 단계(10분, 증례 접근 없음)
            client.ready()
            agent.consult(client, state)  # 대회에서는 진료 단계(30분)
    except KeyboardInterrupt:
        print('\n중단했습니다.')
    except NovaError as exc:
        print(f'\n에이전트가 처리하지 않은 오류로 끝났습니다: {exc.code}')
    out = Path(args.out) / f'{case["case_id"]}-{datetime.now():%Y%m%d-%H%M%S}'
    summary = save_result(simulator, out, started)
    print(f'\n상태 {summary["status"]} · {summary["turns"]}턴 · Doctor 호출 {summary["doctor_calls"]}회'
          f' (입력 {summary["doctor_input_tokens"]:,} / 출력 {summary["doctor_output_tokens"]:,} 토큰) · {summary["seconds"]}초')
    print(f'결과: {out}/ (transcript.json, record.md)')
    model = HERE / 'samples' / case['case_id'] / 'model_record.md'
    if model.exists():
        print(f'모범 기록과 비교: {model.relative_to(HERE)}')


if __name__ == '__main__':
    main()

"""code_v10 → 제출/submission_<이름>.zip. 변형은 run.py DEFAULTS 값만 다르다.

사용: python code_v10/tools/build_submissions.py v10b v11a   (인자 없으면 전체)
저장소 루트 기준 경로를 쓰며, 만든 뒤 빈 폴더에 풀어 격리 파이썬으로 import·설정을 확인한다.
"""
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, 'code_v10')
OUT_DIR = os.path.join(ROOT, '제출')
B = {'EXAM_POS': 1, 'BANK_V10': 1}          # v10b 기준선
VARIANTS = {
    'v10a': {},
    'v10b': dict(B),
    'v10c': dict(B, TURN_PRESET='t34e'),
    'v11a': dict(B, SAY_V11=1),
    'v11b': dict(B, OPEN_TOPIC=1),
    'v11c': dict(B, HPI_V11=1),
    # v12: 34턴·같은 계통 2항목 규칙 안에서 턴당 항목 수(단일 질문 짝 합치기·걱정·기대 짝)
    'v12a': dict(B, PAIR_MERGE=1, ICE_PAIR=1),
    'v12b': dict(B, PAIR_MERGE=1, ICE_PAIR=1, SAY_V11=1),
    'v12c': dict(B, PAIR_MERGE=1, ICE_PAIR=1, SAY_V11=1, TURN_PRESET='t34e'),
    # v13: 턴 가치 재배분(진찰 11·설명 5줄+질문+답 1·문진 15 짝) + v12b
    'v13': dict(B, PAIR_MERGE=1, ICE_PAIR=1, SAY_V11=1, V13=1, TURN_PRESET='t34x'),
}
SHOW = ('REC_BACKSTOP', 'EXAM_POS', 'BANK_V10', 'PAIR_MERGE', 'ICE_PAIR', 'V13', 'SAY_V11', 'OPEN_TOPIC', 'HPI_V11', 'TURN_PRESET', 'INTERVIEW_Q', 'EXAM_N',
        'EXPLAIN_N', 'EXPLAIN_MIN', 'ANSWER_RESERVE', 'EXPLAIN_MAX_LINES', 'TURN_CAP')


def files():
    out = ['run.py', 'requirements.txt', 'nova_sdk.py']
    for d, _, fs in os.walk(os.path.join(SRC, 'agent')):
        if '__pycache__' in d:
            continue
        out += [os.path.relpath(os.path.join(d, f), SRC) for f in sorted(fs) if not f.endswith('.pyc')]
    return sorted(out)


def patch_run(text, kv):
    for k, v in kv.items():
        pat = re.compile(r"(\n    '%s': )([^,]+)(,)" % re.escape(k))
        val = repr(v) if isinstance(v, str) else str(v)
        text, n = pat.subn(lambda m: m.group(1) + val + m.group(3), text, count=1)
        if n != 1:
            raise SystemExit(f'run.py DEFAULTS에 {k} 없음')
    return text


def build(name, kv):
    out = os.path.join(OUT_DIR, f'submission_{name}.zip')
    run_txt = patch_run(open(os.path.join(SRC, 'run.py'), encoding='utf-8').read(), kv)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for rel in files():
            arc = rel.replace(os.sep, '/')
            if arc == 'run.py':
                z.writestr(arc, run_txt)
            else:
                z.write(os.path.join(SRC, rel), arc)
    sha = hashlib.sha256(open(out, 'rb').read()).hexdigest()
    with tempfile.TemporaryDirectory() as tgt, zipfile.ZipFile(out) as z:
        bad = [n for n in z.namelist() if '\\' in n or '__pycache__' in n or n.startswith(('tests/', 'tools/'))]
        z.extractall(tgt)
        code = ("import sys; sys.path.insert(0, '.'); import run, agent, importlib, pkgutil;"
                "[importlib.import_module('agent.'+m.name) for m in pkgutil.iter_modules(agent.__path__)];"
                f"c=run.load_config(); run.prepare(); print({{k: c[k] for k in {SHOW!r}}})")
        r = subprocess.run([sys.executable, '-I', '-c', code], cwd=tgt, capture_output=True, text=True, timeout=300)
        n = len(z.namelist())
    print(f'{name}: {out} {os.path.getsize(out)}B files={n} sha256={sha}')
    print('   bad paths:', bad or 'none', '|', r.stdout.strip().splitlines()[-1] if r.returncode == 0 else r.stderr[-400:])


if __name__ == '__main__':
    for name in (sys.argv[1:] or list(VARIANTS)):
        build(name, VARIANTS[name])

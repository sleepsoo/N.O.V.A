"""tools/ 공용 도우미: 에이전트 로드, 별칭 매핑, 결과 저장(transcript.md, record.md, summary.json)."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
CODE = TOOLS.parent
PROJECT = CODE.parent
SAMPLES = PROJECT / '공개 샘플데이터'
DEVKIT = PROJECT / '정보' / '개발키트'
API_BASE_DEFAULT = 'https://nova.snubhai.org'

RECORD_LABELS = {
    'S': {'cc': '[S] 주호소', 'hpi': '[S] 현병력', 'pmh': '[S] 과거력·약물·알레르기', 'fh': '[S] 가족력', 'sh': '[S] 사회력',
          'ros': '[S] 계통 문진'},
    'O': {'exam': '[O] 진찰 소견', 'tests': '[O] 검사 결과'},
    'A': {'evidence': '[A] 근거', 'differential': '[A] 감별진단'},
    'P': {'tests': '[P] 추가 검사', 'treatment': '[P] 치료', 'disposition': '[P] 처치 결정', 'follow_up': '[P] 추적',
          'education': '[P] 환자 교육'},
}


def dev_key() -> str:
    key = os.environ.get('NOVA_DEV_KEY', '').strip()
    if not key:
        sys.exit('NOVA_DEV_KEY 환경변수가 필요합니다 (키를 코드·파일에 쓰지 마세요).')
    return key


def load_agent(path):
    path = Path(path).resolve()
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location('nova_agent_run', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def nfc(s):
    return unicodedata.normalize('NFC', str(s or ''))


def local_case_by_alias(alias: str):
    folder = SAMPLES / alias
    if (folder / 'case.json').exists():
        return json.loads((folder / 'case.json').read_text(encoding='utf-8'))
    return None


def find_alias_for_opening(opening: str) -> str | None:
    for folder in sorted(SAMPLES.glob('C*')):
        cj = folder / 'case.json'
        if cj.exists():
            case = json.loads(cj.read_text(encoding='utf-8'))
            if nfc(case['start_information']['opening'])[:30] == nfc(opening)[:30]:
                return folder.name
    return None


def render_record_md(note: dict, diagnosis: str) -> str:
    parts = []
    for sec, fields in RECORD_LABELS.items():
        for f, label in fields.items():
            val = ((note or {}).get(sec) or {}).get(f) or '(없음)'
            parts.append(f'## {label}\n\n```\n{val}\n```\n')
    parts.append(f'## 주진단\n\n```\n{diagnosis}\n```\n')
    return '\n'.join(parts)


def render_transcript_md(opening: str, vitals: str, ledger: list[dict]) -> str:
    lines = [f'# 진료 기록\n\n시작 정보: {opening}\n\n활력징후: {vitals.replace(chr(10), ", ")}\n']
    for e in ledger:
        if e.get('refused'):
            lines.append(f"- 턴 {e['turn']} [{e.get('phase')}] **{e['kind']} 거절 {e['refused']}**: {e['text']}")
        elif e['kind'] == 'SAY':
            flag = ' ⚠하나씩' if e.get('one_at_a_time') else ''
            lines.append(f"- 턴 {e['turn']} [{e.get('phase')}] 의사: {e['text']}  \n  환자: {e['reply']}{flag}")
        else:
            lines.append(f"- 턴 {e['turn']} [{e.get('phase')}] 진찰({e['text']}): {e['reply']}")
    return '\n'.join(lines) + '\n'


def events_to_ledger(events: list) -> list[dict]:
    """서버/로컬 events를 ledger 비슷한 형태로(가능한 범위에서)."""
    out = []
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        action = ev.get('action')
        if action not in ('SAY', 'EXAM'):
            continue
        resp = ev.get('response') or {}
        out.append({'turn': ev.get('turn'), 'kind': action, 'text': ev.get('content', ''),
                    'reply': resp.get('content') or resp.get('result') or '', 'refused': ev.get('refused'),
                    'phase': 'server'})
    return out


def norm_dx(s: str) -> str:
    return re.sub(r'[\s()\[\]·,\-\'’"]+', '', nfc(s).lower())


def dx_hit(diagnosis: str, accepted: list[str]) -> bool:
    d = norm_dx(diagnosis)
    ko = norm_dx(re.sub(r'\(.*?\)', '', nfc(diagnosis)))
    for a in accepted or []:
        na = norm_dx(a)
        if not na:
            continue
        if na == d or na == ko or na in d or (len(ko) >= 3 and ko in na):
            return True
    return False


def save_run(out: Path, *, case_id, alias, opening, vitals, info: dict, session: dict | None, accepted, seconds,
             extra=None):
    out.mkdir(parents=True, exist_ok=True)
    ledger = info.get('ledger') or []
    note = info.get('note') or {}
    dx = info.get('diagnosis') or ''
    (out / 'transcript.md').write_text(render_transcript_md(opening, vitals, ledger), encoding='utf-8')
    (out / 'record.md').write_text(f'# {alias or case_id} 제출 기록\n\n' + render_record_md(note, dx), encoding='utf-8')
    (out / 'record.json').write_text(json.dumps({**(note or {}), 'diagnosis': dx}, ensure_ascii=False, indent=2),
                                     encoding='utf-8')
    if session is not None:
        (out / 'session.json').write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 'ledger.json').write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding='utf-8')
    counts = info.get('counts') or {}
    budget = info.get('budget') or {}
    summary = {
        'case_id': case_id, 'alias': alias, 'turns': info.get('turn'),
        'say': counts.get('say'), 'exam': counts.get('exam'), 'refused': counts.get('refused'),
        'exam_refused': counts.get('exam_refused'), 'one_at_a_time': counts.get('one_at_a_time'),
        'interview_questions': counts.get('interview'), 'skipped_invalid': counts.get('skipped_invalid'),
        'doctor_calls': budget.get('doctor_calls'), 'doctor_invalid': budget.get('doctor_invalid'),
        'doctor_input_tokens': budget.get('doctor_input_tokens'), 'doctor_output_tokens': budget.get('doctor_output_tokens'),
        'seconds': seconds, 'diagnosis': dx, 'accepted_diagnoses': accepted,
        'dx_hit': dx_hit(dx, accepted) if accepted else None, 'dx_samples': (info.get('dx_detail') or {}).get('samples'),
        'profile': info.get('profile'), 'explained': info.get('explained'), 'call_log': info.get('call_log'),
        'phase_times': info.get('phase_times'), 'findings': info.get('findings'),
        'session_status': (session or {}).get('status'), 'result': info.get('result'),
    }
    trunc = []
    for ev in (session or {}).get('events') or []:
        if isinstance(ev, dict) and ev.get('action') == 'SAY' and 'payload' in ev:
            p, ef = (ev['payload'].get('content') or '').strip(), ev.get('effective_content')
            if ef is not None and nfc(ef).strip() != nfc(p):
                trunc.append({'turn': ev.get('turn'), 'sent': p, 'effective': ef})
    summary['truncated'] = len(trunc)
    summary['truncated_detail'] = trunc
    summary['teach_back'] = info.get('teach_back')
    summary['exam_plan'] = info.get('exam_plan')
    if extra:
        summary.update(extra)
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary

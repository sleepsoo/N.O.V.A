"""서버 가상환자 응답 특성 프로브 (제출 코드와 무관한 실험 스크립트).

  export NOVA_DEV_KEY=...           # 키는 환경변수로만
  python tools/probe_patient.py --case C10 --plan c10a

측정: (A) 개방형 vs 닫힌 질문의 사실 수확량, (B) 진찰표 밖/변형 명칭 진찰 처리,
(C) 설명 단계 상호작용·teach-back, (D) 답변 길이.
각 세션의 원 응답과 서버 events 전체를 runs/probe/<alias>-<plan>-<시각>.json 에 저장한다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

sys.path.insert(0, str(common.CODE))
from nova_sdk import Client, NovaError, empty_record  # noqa: E402

CASE_IDS = {
    'C01': '4fa07144-04e5-4116-a18e-88d8a90cc21a',
    'C10': '35dd8b69-2531-454e-bb8c-fb8030293447',
    'C03': 'ef3649a9-330b-4e12-ad2d-fab94d019330',
}

# (action, content, tag) — tag: open / closed / exam_in / exam_out / exam_var / explain / teach / probe
OPEN_CORE = [
    ('SAY', '증상이 어떻게 시작됐는지 말씀해 주세요', 'open'),
    ('SAY', '그 밖에 달라진 점을 다 말씀해 주세요', 'open'),
    ('SAY', '다른 불편한 증상은 없으세요?', 'open'),
    ('SAY', '평소 건강은 어떠셨어요?', 'open'),
    ('SAY', '드시는 약을 전부 말씀해 주세요', 'open'),
    ('SAY', '가족 중 아픈 분이 있으세요?', 'open'),
    ('SAY', '하루 일과를 말씀해 주세요', 'open'),
    ('SAY', '술·담배·커피는 어떠세요?', 'open_bundle'),
    ('SAY', '최근 석 달간 변화를 전부 말씀해 주세요', 'open_all'),
]

PLANS = {
    'c10a': OPEN_CORE + [
        ('SAY', '더 자세히 말씀해 주시겠어요?', 'open_followup'),
        ('SAY', '또 다른 변화는 없으세요?', 'open_followup'),
        ('SAY', '손이 떨리세요?', 'closed'),
        ('SAY', '변이 묽어지셨나요?', 'closed'),
        ('SAY', '생리는 규칙적인가요?', 'closed'),
        ('SAY', '눈이 튀어나온 느낌이 있으세요?', 'closed'),
        ('SAY', '담배 피우세요?', 'closed'),
        ('EXAM', '갑상선 촉진하겠습니다', 'exam_in'),
        ('EXAM', '복부 촉진하겠습니다', 'exam_in'),
        ('EXAM', '경부 림프절 촉진하겠습니다', 'exam_in'),
        ('EXAM', '롬베르그 검사하겠습니다', 'exam_out'),
        ('EXAM', '보행 관찰하겠습니다', 'exam_out'),
        ('EXAM', '동공 대광반사 확인하겠습니다', 'exam_out'),
        ('EXAM', '손톱 시진하겠습니다', 'exam_out'),
        ('EXAM', '복부 진찰하겠습니다', 'exam_var'),
        ('EXAM', '눈 진찰하겠습니다', 'exam_var'),
        ('EXAM', '목 앞을 만져보겠습니다', 'exam_var'),
        ('EXAM', '목에 청진기 대보겠습니다', 'exam_var'),
        ('EXAM', '무릎 반사 확인하겠습니다', 'exam_var'),
        ('EXAM', '손을 앞으로 뻗어 보세요', 'exam_var'),
        ('EXAM', '갑상선 촉진하겠습니다', 'exam_repeat'),
        ('SAY', '갑상선 기능이 높아진 것으로 보여요', 'explain'),
        ('SAY', '혈액검사로 호르몬을 확인할게요', 'explain'),
        ('SAY', '궁금하신 점 있으세요?', 'explain_q'),
        ('SAY', '네, 혈액검사로 확인할 수 있어요', 'explain_answer'),
        ('SAY', '약으로 대부분 잘 조절돼요', 'explain'),
        ('SAY', '이해되셨어요? 한번 말해 보시겠어요?', 'teach'),
        ('SAY', '어떤 검사를 받는지 말씀해 보시겠어요?', 'teach'),
    ],
    'c10b': [
        ('SAY', '증상이 어떻게 시작됐는지 말씀해 주세요', 'open_repeat'),
        ('SAY', '다른 불편한 증상은 없으세요?', 'open_sweep'),
        ('SAY', '그 밖에 또 불편한 건 없으세요?', 'open_sweep'),
        ('SAY', '그 밖에 또 불편한 건 없으세요?', 'open_sweep'),
        ('SAY', '또 다른 증상은 없으세요?', 'open_sweep'),
        ('SAY', '요즘 몸 상태는 어떠세요?', 'open'),
        ('SAY', '어디가 제일 불편하세요?', 'open'),
        ('SAY', '두근거림에 대해 자세히 말씀해 주세요', 'open_topic'),
        ('SAY', '생리에 대해 자세히 말씀해 주세요', 'open_topic'),
        ('SAY', '대변은 어떠세요?', 'open_topic'),
        ('SAY', '눈에 대해 자세히 말씀해 주세요', 'open_topic'),
        ('SAY', '더위나 땀은 어떠세요?', 'pair_na'),
        ('SAY', '잠과 기분은 어떠세요?', 'pair_gwa'),
        ('SAY', '눈이나 목에 변화가 있나요?', 'pair_na'),
        ('SAY', '피곤하거나 숨이 차세요?', 'pair_geona'),
        ('SAY', '가족 중 다른 아픈 분도 있나요?', 'open_followup'),
        ('SAY', '어떤 점이 가장 걱정되세요?', 'open'),
        ('EXAM', '갑상선 청진하겠습니다', 'exam_var'),
        ('EXAM', '심장 청진하겠습니다', 'exam_var'),
        ('EXAM', '피부 만져보겠습니다', 'exam_var'),
        ('EXAM', '안구 돌출 확인하겠습니다', 'exam_var'),
        ('EXAM', '아킬레스건 반사 확인하겠습니다', 'exam_var'),
        ('EXAM', '정강이 앞 피부 확인하겠습니다', 'exam_var'),
        ('EXAM', '맥박 재겠습니다', 'exam_var'),
        ('EXAM', '다리 근력 확인하겠습니다', 'exam_var'),
        ('EXAM', '혈압 재겠습니다', 'exam_var'),
        ('SAY', '그레이브스병이 의심돼요', 'explain'),
        ('SAY', '호르몬이 많아 두근거리고 떨려요', 'explain'),
        ('SAY', '피검사와 초음파를 할게요', 'explain'),
        ('SAY', '약으로 호르몬을 낮추면 좋아져요', 'explain'),
        ('SAY', '제 설명을 다시 말씀해 주시겠어요?', 'teach'),
        ('SAY', '어떤 치료를 받는지 말씀해 보세요', 'teach'),
        ('SAY', '열이나 목이 아프면 바로 오세요', 'explain'),
        ('SAY', '언제 바로 오셔야 하는지 말씀해 보세요', 'teach'),
    ],
    'c01b': [
        ('SAY', '다른 불편한 증상은 없으세요?', 'open_sweep'),
        ('SAY', '그 밖에 또 불편한 건 없으세요?', 'open_sweep'),
        ('SAY', '그 밖에 또 불편한 건 없으세요?', 'open_sweep'),
        ('SAY', '그 밖에 또 불편한 건 없으세요?', 'open_sweep'),
        ('SAY', '그 밖에 또 불편한 건 없으세요?', 'open_sweep'),
        ('SAY', '그 밖에 또 불편한 건 없으세요?', 'open_sweep'),
        ('SAY', '그 밖에 또 불편한 건 없으세요?', 'open_sweep'),
        ('SAY', '두통이나 어지럼은 없으세요?', 'pair_neg'),
        ('SAY', '두통, 어지럼, 구토는 없으세요?', 'triple_neg'),
        ('SAY', '수술이나 입원한 적 있으세요?', 'pair_na'),
        ('SAY', '가족 중 다른 아픈 분도 있나요?', 'open_followup'),
        ('SAY', '가족 중 또 아픈 분 있나요?', 'open_followup'),
        ('SAY', '누구와 사시고 무슨 일 하세요?', 'probe_compound'),
        ('SAY', '누구와 사세요, 무슨 일 하세요?', 'probe_twoq'),
        ('SAY', '가족 관계는 어떠세요?', 'open_topic'),
        ('SAY', '약 줄이려고 해 보신 적 있어요?', 'closed'),
        ('SAY', '그때 어떠셨어요?', 'open_followup'),
        ('SAY', '또 어떤 증상이 있었어요?', 'open_followup'),
        ('SAY', '약이 떨어질까 봐 걱정되세요?', 'closed'),
        ('SAY', '가장 궁금하신 게 뭐예요?', 'open'),
        ('SAY', '또 궁금하신 건요?', 'open_followup'),
    ],
    'c01a': OPEN_CORE[:7] + [
        ('SAY', '술·담배·커피는 어떠세요?', 'open_bundle'),
        ('SAY', '수면제 드신 경과를 다 말씀해 주세요', 'open_all'),
        ('SAY', '잠에 대해 자세히 말씀해 주세요', 'open_topic'),
        ('SAY', '약을 끊으면 어떻게 되세요?', 'open_topic'),
        ('SAY', '생활에 어떤 영향이 있었어요?', 'open_topic'),
        ('SAY', '힘드셨겠어요. 낮에 졸리세요?', 'probe_prefix'),
        ('SAY', '몇 시에 자고 몇 시에 깨세요?', 'probe_compound'),
        ('SAY', '언제 드세요? 얼마나 드세요?', 'probe_twoq'),
        ('SAY', '수면제 몇 알 드세요?', 'closed'),
        ('SAY', '여러 병원에서 처방받으세요?', 'closed'),
        ('SAY', '고혈압 있으세요?', 'closed'),
        ('SAY', '담배 피우세요?', 'closed'),
        ('SAY', '기억이 안 나는 적이 있으세요?', 'closed'),
        ('EXAM', '보행 관찰하겠습니다', 'exam_in'),
        ('EXAM', '경부 림프절 촉진하겠습니다', 'exam_out'),
        ('EXAM', '심부건반사 확인하겠습니다', 'exam_out'),
        ('EXAM', '외안근 운동 확인하겠습니다', 'exam_out'),
        ('EXAM', '갑상선 잡음 청진하겠습니다', 'exam_out'),
        ('EXAM', '걸음걸이 보겠습니다', 'exam_var'),
        ('EXAM', '눈 감고 서 계셔 보세요', 'exam_var'),
        ('EXAM', '손가락으로 코를 짚어 보세요', 'exam_var'),
        ('EXAM', '기억력 검사하겠습니다', 'exam_var'),
        ('EXAM', '손 떨림 보겠습니다', 'exam_var'),
        ('EXAM', '누웠다 일어서서 혈압 재겠습니다', 'exam_var'),
        ('EXAM', '병식 평가하겠습니다', 'exam_in'),
        ('SAY', '수면제 의존이 생긴 것으로 보여요', 'explain'),
        ('SAY', '천천히 줄이면 끊을 수 있어요', 'explain'),
        ('SAY', '궁금하신 점 있으세요?', 'explain_q'),
        ('SAY', '갑자기 끊으면 위험해서 천천히 줄여요', 'explain_answer'),
        ('SAY', '이해되셨어요? 한번 말해 보시겠어요?', 'teach'),
    ],
    'c03a': OPEN_CORE[:7] + [
        ('SAY', '출생 때부터 지금까지 말씀해 주세요', 'open_topic'),
        ('SAY', '부모님 키와 성장은 어떠셨어요?', 'open_topic'),
        ('SAY', '아이 발달은 어땠어요?', 'open_topic'),
        ('SAY', '최근 일 년간 변화를 전부 말씀해 주세요', 'open_all'),
        ('SAY', '식사·잠·운동은 어떤가요?', 'open_bundle'),
        ('SAY', '아빠와 엄마 키는 각각 몇이에요?', 'probe_nounpair'),
        ('SAY', '잘 웃으시네요, 그런데 우유는 마셔요?', 'probe_prefix'),
        ('SAY', '아빠가 사춘기가 늦었나요?', 'closed'),
        ('SAY', '변비가 있나요?', 'closed'),
        ('SAY', '복용하는 약이 있나요?', 'closed'),
        ('SAY', '잘 먹나요?', 'closed'),
        ('SAY', '만삭에 태어났나요?', 'closed'),
        ('EXAM', '신체 계측하겠습니다', 'exam_in'),
        ('EXAM', '심부건반사 확인하겠습니다', 'exam_out'),
        ('EXAM', '경부 림프절 촉진하겠습니다', 'exam_out'),
        ('EXAM', '롬베르그 검사하겠습니다', 'exam_out'),
        ('EXAM', '척추 시진하겠습니다', 'exam_out'),
        ('EXAM', '키를 재겠습니다', 'exam_var'),
        ('EXAM', '고환 크기 확인하겠습니다', 'exam_var'),
        ('EXAM', '성장곡선 확인하겠습니다', 'exam_var'),
        ('EXAM', '팔 길이 재겠습니다', 'exam_var'),
        ('EXAM', '얼굴 생김새 보겠습니다', 'exam_var'),
        ('SAY', '체질적으로 늦게 크는 것으로 보여요', 'explain'),
        ('SAY', '뼈나이 검사로 확인해 볼게요', 'explain'),
        ('SAY', '궁금하신 점 있으세요?', 'explain_q'),
        ('SAY', '최종 키는 대개 정상 범위예요', 'explain_answer'),
        ('SAY', '이해되셨어요? 한번 말해 보시겠어요?', 'teach'),
    ],
}


def send(client, action, content):
    rid = str(uuid.uuid4())
    for attempt in range(2):
        t0 = time.time()
        try:
            resp = client.action(action, content=content, request_id=rid)
            return {'ok': True, 'response': resp, 'sec': round(time.time() - t0, 1)}
        except NovaError as exc:
            if exc.code in ('API_UNAVAILABLE', 'PROVIDER_UNAVAILABLE') and attempt == 0:
                time.sleep(3)
                continue
            return {'ok': False, 'code': exc.code, 'http': exc.status, 'sec': round(time.time() - t0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', required=True, choices=sorted(CASE_IDS))
    ap.add_argument('--plan', required=True, choices=sorted(PLANS))
    ap.add_argument('--out', default=str(common.CODE / 'runs' / 'probe'))
    args = ap.parse_args()

    key = common.dev_key()
    api = os.environ.get('NOVA_API_BASE', common.API_BASE_DEFAULT)
    client = Client(api_base=api, token=key, sample=True)
    session = client.create_sample(CASE_IDS[args.case])
    print('세션:', client.session_id, flush=True)
    log = []
    for i, (action, content, tag) in enumerate(PLANS[args.plan], 1):
        content = common.nfc(content)
        assert len(content) <= 30, content
        r = send(client, action, content)
        entry = {'i': i, 'action': action, 'content': content, 'tag': tag, **r}
        log.append(entry)
        resp = r.get('response') or {}
        shown = resp.get('content') or resp.get('result') or r.get('code')
        print(f"{i:2d} [{tag}] {action} {content} -> {shown} (남은 {resp.get('turns_remaining')})", flush=True)
        if not r['ok'] and r.get('code') in ('TURN_LIMIT_REACHED', 'SESSION_CLOSED', 'SESSION_EXPIRED'):
            break
    try:
        dx = client.diagnose(note=empty_record(), diagnosis='프로브 세션(채점 무관)')
    except NovaError as exc:
        dx = {'error': exc.code}
    try:
        final = client.session()
    except NovaError as exc:
        final = {'error': exc.code}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f'{args.case}-{args.plan}-{datetime.now():%Y%m%d-%H%M%S}.json'
    path.write_text(json.dumps({'case': args.case, 'plan': args.plan, 'session_id': client.session_id,
                                'initial': session.get('initial'), 'log': log, 'diagnose': dx,
                                'session': final}, ensure_ascii=False, indent=1), encoding='utf-8')
    print('저장:', path)


if __name__ == '__main__':
    main()

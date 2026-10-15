import sys, re, collections
rows = [l.rstrip('\n').split('\t') for l in open(sys.argv[1]) if l.strip()]
# (question pattern, A kw, B kw, kind) kind: same / cross / diffverb / three
SPEC = [
 (r'^(가족 중 )?(당뇨나 고혈압|고혈압이나 당뇨)', r'당뇨', r'고혈압|혈압', 'same'),
 (r'결핵이나 간염', r'결핵', r'간염', 'same'),
 (r'다른 지병이나 수술', r'지병|병', r'수술', 'same'),
 (r'스테로이드나 한약', r'스테로이드', r'한약', 'same'),
 (r'한약이나 영양제', r'한약', r'영양제', 'same'),
 (r'^(드시는 |현재 먹는 |지금 먹는 )?(약이나 영양제|다른 약이나 영양제)', r'약|암로디핀|수면제|졸피뎀', r'영양제', 'same'),
 (r'입원하거나 크게 아픈|입원이나 큰 병', r'입원', r'큰\s*병|크게|아픈', 'same'),
 (r'임신이나 출산', r'임신', r'출산|분만', 'same'),
 (r'천식이나 (콩팥|심장)', r'천식', r'콩팥|심장', 'same'),
 (r'낮에 졸리거나 멍', r'졸', r'멍', 'same'),
 (r'피곤하거나 기운', r'피곤', r'기운', 'same'),
 (r'음모나 고환|음모가 나거나 고환', r'음모', r'고환', 'same'),
 (r'말이나 걷기', r'말', r'걷', 'same'),
 (r'살이 빠지거나 찌', r'빠지', r'찌', 'same'),
 (r'생리 (양이나 기간|주기나 양)', r'양', r'기간|짧|주기', 'same'),
 (r'대변 횟수나 모양', r'번|회', r'묽|모양|딱딱', 'same'),
 (r'물을 많이 드시거나 갈증', r'물', r'갈증', 'same'),
 (r'물을 많이 마시거나 소변', r'물|마시', r'소변', 'diffverb'),
 (r'눈이 (튀어나오거나 뻑뻑|뻑뻑하거나 튀어나온)', r'튀어나', r'뻑뻑', 'same'),
 (r'목이 붓거나 혹', r'두꺼|붓|부', r'혹', 'same'),
 (r'열이나 오한', r'열', r'오한', 'same'),
 (r'몸이나 다리가 붓', r'몸', r'다리', 'same'),
 (r'기침이나 가래', r'기침', r'가래', 'same'),
 (r'가슴 통증이나 숨참', r'가슴|통증', r'숨', 'same'),
 (r'더위나 땀', r'더위|덥', r'땀', 'same'),
 (r'더위나 추위', r'더위', r'추위', 'same'),
 (r'두통이나 구토는', r'두통|머리', r'구토|토', 'same'),
 (r'^(변비나 추위|피로감이나 변비|피로나 변비)', r'변비|피로|피곤', r'추위|변비', 'same'),
 (r'피부가건조하거나가려움', r'건조', r'가려', 'same'),
 (r'어지럽거나 쓰러질', r'어지', r'쓰러', 'same'),
 (r'키가 작거나 유전병', r'키|작', r'유전', 'same'),
 (r'약이나 음식 알레르기', r'약', r'음식', 'same'),
 (r'복통이나 혈변', r'복통|배', r'혈변|피', 'same'),
 (r'신생아 때 황달이나 치료', r'황달', r'치료', 'same'),
 (r'배만 나오거나 얼굴', r'배', r'얼굴', 'same'),
 # cross-system / different verbs
 (r'두통이나 시야 이상이', r'두통|머리', r'시야|눈', 'cross'),
 (r'눈 불편감이나 목 부음', r'눈', r'목', 'cross'),
 (r'손이 떨리거나 힘이 빠', r'떨', r'힘', 'cross'),
 (r'변비가 있거나 추위를', r'변비', r'추위', 'diffverb'),
 (r'눈이 부풀어 오르거나 가려', r'부풀|튀어', r'가려', 'diffverb'),
 (r'잠들기 어렵나요, ', r'잠들', r'깨', 'twoq'),
 (r'잘 지치거나 변비, 추위|두통이나 구토, 시야|천식이나 장, 콩팥|천식이나 장·콩팥|먹는 약이나 한약, 영양제', None, None, 'three'),
]
GENERIC = re.compile(r'(둘\s*다|모두|그런\s*(증상|병|질환|적|건|것|변화|가족|얘기|말|분)|아무것도|^아니(요|오)?[,.]?\s*(없|안|그런|들은|진단|먹은)|^(네|예)[,.]?\s*(둘|그런)|^없어요|문제\s*(없|는 없))')
res = collections.defaultdict(lambda: collections.Counter())
examples = collections.defaultdict(list)
for run, turn, q, a in rows:
    for pat, ka, kb, kind in SPEC:
        if re.search(pat, q):
            if kind == 'three':
                cls = 'generic' if GENERIC.search(a) else 'partial'
            else:
                ha = bool(re.search(ka, a)); hb = bool(re.search(kb, a))
                if ha and hb: cls = 'both'
                elif GENERIC.search(a) and not (ha ^ hb): cls = 'both(generic)'
                elif GENERIC.search(a) and re.search(r'(둘\s*다|모두|그런)', a): cls = 'both(generic)'
                elif ha or hb: cls = 'partial'
                else: cls = 'other'
            res[kind][cls] += 1
            examples[(kind, cls)].append(f'{q} -> {a}')
            break
for kind, c in res.items():
    tot = sum(c.values())
    print(kind, tot, dict(c))
print()
for key in [('same','partial'), ('same','other'), ('cross','partial'), ('cross','other'), ('diffverb','partial'), ('diffverb','both'), ('three','partial'), ('three','generic')]:
    print('##', key)
    for e in examples.get(key, [])[:30]:
        print('   ', e)

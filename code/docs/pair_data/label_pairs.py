import sys, re, csv
sys.path.insert(0, sys.argv[2])
rows = [l.rstrip('\n').split('\t') for l in open(sys.argv[1]) if l.strip()]
exec(open(sys.argv[2] + '/classify_pairs.py').read().split('res = collections')[0])  # reuse SPEC, GENERIC
FIX_BOTH = ['또래처럼 말하고 걸었어요', '건조하거나 가렵진 않아요', '문제 없이 만삭에 자연분만', '생리량과 기간이 줄었어요',
            '또래와 비슷했어요', '또래만큼', '또래랑 비슷', '갑자기 변하진', '갑작스런 변화', '알레르기는 없어요', '붓지는 않아요', '아빠 말고는 없어요']
FIX_PARTIAL = ['고혈압 말곤 없어요', '생리량이 많이 줄었어요']
out = csv.writer(open(sys.argv[3], 'w', newline=''), delimiter='\t')
out.writerow(['run', 'turn', 'question', 'answer', 'kind', 'label'])
cnt = {}
for run, turn, q, a in rows:
    for pat, ka, kb, kind in SPEC:
        if re.search(pat, q):
            if kind == 'three':
                lab = 'generic' if GENERIC.search(a) else 'partial'
            else:
                ha = bool(re.search(ka, a)); hb = bool(re.search(kb, a))
                if ha and hb: lab = 'both'
                elif GENERIC.search(a): lab = 'both'
                elif ha or hb: lab = 'partial'
                else: lab = 'other'
                if any(s in a for s in FIX_BOTH): lab = 'both'
                if any(s in a for s in FIX_PARTIAL): lab = 'partial'
                if lab == 'other': lab = 'both'
            out.writerow([run, turn, q, a, kind, lab])
            cnt[(kind, lab)] = cnt.get((kind, lab), 0) + 1
            break
for k, v in sorted(cnt.items()): print(k, v)

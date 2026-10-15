import json, glob, os, re, sys
root = sys.argv[1]
rows = []
seen = set()
for d in sorted(glob.glob(os.path.join(root, '*'))):
    lp = os.path.join(d, 'ledger.json'); sp = os.path.join(d, 'summary.json')
    if not (os.path.exists(lp) and os.path.exists(sp)):
        continue
    s = json.load(open(sp))
    api = str(s.get('api') or '')
    if 'nova.snubhai' not in api:
        continue
    for e in json.load(open(lp)):
        if e.get('kind') != 'SAY' or e.get('refused'):
            continue
        ph = e.get('phase') or ''
        if ph.startswith('explain') or ph == 'empathy':
            continue
        q = e.get('text') or ''; a = e.get('reply') or ''
        # pair markers
        if re.search(r'(이나|거나|[가-힣]나\s|이랑|랑\s|와\s|과\s|·|,)', q):
            key = (q, a)
            if key in seen: continue
            seen.add(key)
            rows.append((os.path.basename(d), e.get('turn'), q, a))
for r in rows:
    print('\t'.join(str(x) for x in r))
print('N', len(rows), file=sys.stderr)

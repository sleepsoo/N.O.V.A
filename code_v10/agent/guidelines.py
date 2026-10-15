"""진료지침 검색·발췌(KR/US). 본문은 ZIP에 넣지 않고 실행 중 NOVA_GUIDELINES_DIR에서 읽는다(원문 변경본 배포 금지 조건 준수).

- prepare(): catalog.csv(없으면 각 파일 머리글)로 제목 → 파일 경로 인덱스만 만든다(본문 안 읽음, 수 초).
- 검색은 임베딩 없이 진단명 ↔ 제목 토큰 매칭(영어 단어 + 한글 어절·2-gram, idf 가중).
- 발췌는 마크다운 헤딩 키워드(History·Evaluation·Treatment·Follow-up / 진단·치료·추적 …)로 필요한 섹션만 잘라 쓴다.
- 모든 함수는 실패해도 예외를 밖으로 내지 않고 빈 문자열을 돌려준다(기존 흐름을 막지 않음).
"""
from __future__ import annotations

import csv
import math
import os
import re
import time
from collections import defaultdict

from .util import log, log_error, nfc

INDEX = None  # 모듈 전역: run.consult()가 prepare()가 만든 인덱스를 set_index()로 넣는다.

STOP_EN = {'the', 'and', 'for', 'with', 'from', 'due', 'disease', 'disorder', 'syndrome', 'other', 'type', 'not', 'unspecified',
           'acute', 'chronic', 'primary', 'secondary', 'adult', 'adults', 'patients', 'patient', 'clinical', 'guideline',
           'guidelines', 'practice', 'management', 'treatment', 'diagnosis', 'korea', 'korean', 'archived', 'update', 'review'}
STOP_KO = {'장애', '질환', '증후', '후군', '증후군', '검사', '치료', '진단', '환자', '지침', '진료', '권고', '가이드', '가이드라인', '합의안', '권고안', '진료권고안', '임상진료지침', '임상진료', '전문가', '의견', '최신', '개정안'}
PARTICLE = re.compile(r'(에서|으로|에게|의|을|를|은|는|이|가|에|와|과|도|로|및)$')
# 질환 본문이 아닌 변형 문서(선별·병리·소아·임신 등)는 질의에 그 단어가 없으면 감점
OFF_TOPIC = re.compile(r'screening|pathology|histology|physiology|anatomy|embryology|nursing|pregnan|children|pediatric|neonat|infant|'
                       r'선별|검진|임신|소아|신생아|병리', re.I)
CLINICAL_TYPES = ('진료지침', '권고문', '합의문', '요약본', '근거 리뷰')

SECTION_KEYS = {
    'hp': r'history|physical|presentation|clinical\s*(feature|manifest|present)|symptom|signs?\b|etiolog|risk\s*factor|'
          r'증상|임상\s*양상|임상\s*소견|진찰|병력|문진|위험\s*인자|원인',
    'dx': r'evaluat|diagnos|criteria|work-?up|laborator|imaging|screening|test|검사|진단|평가|선별',
    'ddx': r'differential|감별',
    'tx': r'treatment|management|therap|pharmaco|intervention|recommend|치료|관리|권고|약물|처치',
    'fu': r'follow|monitor|prognos|complication|red\s*flag|warning|referral|disposition|admission|hospitali[sz]|consult|'
          r'추적|경과|합병증|예후|경고|의뢰|입원|응급|감시',
    'edu': r'patient\s*education|deterrence|pearls|counsel|enhancing|교육|생활|자가\s*관리|예방|주의',
}
SKIP_HEAD = re.compile(r'reference|review\s*question|bibliograph|acknowledg|conflict|funding|참고\s*문헌|문헌|감사의\s*글|이해\s*상충|'
                       r'author|disclosure|copyright|appendix|부록', re.I)
META_LINE = re.compile(r'^\s*(?:[-*>]\s*)?(?:\*\*)?(제목|발행기관|연도|언어|출처(?:\s*주소)?|라이선스|문서\s*유형|title|source|license|'
                       r'publisher|year|language|url)(?:\*\*)?\s*[:：]', re.I)
HAN = re.compile(r'[가-힣]+')
ENW = re.compile(r'[a-z][a-z\-\']{2,}')


# ---------------------------------------------------------------- 토큰
def _norm_ko(s: str) -> str:
    if '갑상' in s:
        s = s.replace('갑상샘', '갑상선').replace('샘', '선')
        s = re.sub(r'갑상선(?!기능)(항진증|저하증)', r'갑상선기능\1', s)
    return s


def tokens(text: str) -> set[str]:
    t = _norm_ko(nfc(text).lower())
    out = set()
    for w in ENW.findall(t):
        w = w.strip("-'")
        for part in ([w] + (w.split('-') if '-' in w else [])):
            part = part.strip("-'")
            if len(part) >= 3 and part not in STOP_EN:
                out.add(part[:-1] if part.endswith('s') and len(part) > 4 else part)
    for w in HAN.findall(t):
        if len(w) >= 4:
            w = PARTICLE.sub('', w) or w
        if len(w) == 1 or w.endswith('학회'):
            continue
        if w not in STOP_KO:
            out.add(w)
        for i in range(len(w) - 1):
            if w[i:i + 2] not in STOP_KO:
                out.add(w[i:i + 2])
    return out


def _flat(s: str) -> str:
    return re.sub(r'[^0-9a-z가-힣]+', '', _norm_ko(nfc(s).lower()))


def split_dx(s: str) -> list[str]:
    """'그레이브스병에 의한 갑상샘항진증 (Graves' disease)' → ['그레이브스병에 의한 갑상샘항진증', "Graves' disease", ...]"""
    s = nfc(s or '').strip()
    if not s:
        return []
    inner = [p.strip() for p in re.findall(r'\(([^)]*)\)', s) if p.strip()]
    base = re.sub(r'\s*\([^)]*\)', '', s).strip()
    out = []
    for q in [base] + inner:
        clauses = [c.strip() for c in re.split(r'\s*(?:에\s*의한|으로\s*인한|에\s*따른)\s*', q) if c.strip()]
        joined = ' '.join(clauses)
        for c in [joined] + (clauses if len(clauses) > 1 else []):
            if c and (len(c) >= 3 or ' ' in c) and c not in out:
                out.append(c)
    return out


# ---------------------------------------------------------------- 인덱스
class Index:
    def __init__(self, entries: list[dict], root: str):
        self.root = root
        self.entries = entries
        self.inv: dict[str, list[int]] = defaultdict(list)
        self.toks: list[set[str]] = []
        for i, e in enumerate(entries):
            tk = tokens(e['title'])
            self.toks.append(tk)
            for t in tk:
                self.inv[t].append(i)
        n = max(1, len(entries))
        self.idf = {t: math.log(1 + n / (1 + len(v))) for t, v in self.inv.items()}

    def __len__(self):
        return len(self.entries)


def set_index(idx) -> None:
    global INDEX
    INDEX = idx


def _read_head(path: str, nbytes: int = 1600) -> str:
    try:
        with open(path, 'rb') as f:
            return f.read(nbytes).decode('utf-8', 'ignore')
    except OSError:
        return ''


def _entry_from_row(row: dict) -> dict | None:
    rel = (row.get('파일명') or row.get('file') or '').strip()
    title = (row.get('제목') or row.get('title') or '').strip()
    if not rel or not title:
        return None
    try:
        year = int(float(row.get('연도') or 0))
    except (TypeError, ValueError):
        year = 0
    return {'path': rel.replace('\\', '/'), 'title': nfc(title), 'org': (row.get('발행기관') or '').strip(),
            'year': year, 'lang': (row.get('언어') or '').strip(), 'dtype': (row.get('문서 유형') or '').strip(),
            'src': rel.replace('\\', '/').split('/')[0]}


def build_index(root: str | None, max_seconds: float = 300.0) -> Index | None:
    """catalog.csv가 있으면 그것으로, 없으면 파일 머리글을 훑어 제목 인덱스를 만든다."""
    if not root or not os.path.isdir(root):
        log('guidelines: dir absent')
        return None
    t0 = time.time()
    entries: list[dict] = []
    for cand in (os.path.join(root, 'catalog.csv'), os.path.join(os.path.dirname(root.rstrip('/')), 'catalog.csv')):
        if os.path.isfile(cand):
            try:
                with open(cand, encoding='utf-8-sig', newline='') as f:
                    for row in csv.DictReader(f):
                        e = _entry_from_row(row)
                        if e and os.path.isfile(os.path.join(root, e['path'])):
                            entries.append(e)
                log(f'guidelines: catalog.csv {len(entries)} entries')
            except Exception as exc:
                log_error(f'guidelines: catalog read failed {exc}')
                entries = []
            break
    if not entries:  # 머리글 스캔(폴백)
        for sub in sorted(os.listdir(root)):
            d = os.path.join(root, sub)
            if not os.path.isdir(d):
                continue
            for fn in sorted(os.listdir(d)):
                if not fn.endswith('.md'):
                    continue
                if time.time() - t0 > max_seconds:
                    break
                head = _read_head(os.path.join(d, fn))
                title = ''
                m = re.search(r'^\s*(?:title|제목)\s*[:：]\s*(.+)$', head, re.I | re.M)
                if m:
                    title = m.group(1).strip()
                if not title:
                    m = re.search(r'^#\s+(.+)$', head, re.M)
                    title = m.group(1).strip() if m else fn[:-3]
                ym = re.search(r'(?:연도|year)\s*[:：]\s*(\d{4})', head, re.I)
                dt = re.search(r'(?:문서\s*유형)\s*[:：]\s*(.+)', head)
                entries.append({'path': f'{sub}/{fn}', 'title': nfc(title), 'org': '', 'year': int(ym.group(1)) if ym else 0,
                                'lang': '한국어' if HAN.search(title) else '영어', 'dtype': dt.group(1).strip() if dt else '',
                                'src': sub})
        log(f'guidelines: head scan {len(entries)} entries')
    if not entries:
        return None
    idx = Index(entries, root)
    log(f'guidelines: index ready {len(idx)} docs, {len(idx.inv)} tokens, {time.time() - t0:.1f}s')
    return idx


# ---------------------------------------------------------------- 검색
def _is_guideline(e) -> bool:
    return any(t in e['dtype'] for t in CLINICAL_TYPES) and '일반인용' not in e['dtype']


def _mode_bonus(e: dict, mode: str) -> float:
    src, dt = e['src'], e['dtype']
    if mode == 'overview':          # 질환 개요(교과서): StatPearls 우선
        if src == 'US_StatPearls':
            return 0.3
        if '일반인용' in dt:
            return -0.6
        return 0.05 if _is_guideline(e) else -0.1
    if mode == 'mgmt':              # 진단·치료 지침: 한국 지침 > 미국 지침 > 개요
        if '일반인용' in dt:
            return -0.6
        if src.startswith('KR_') and _is_guideline(e):
            return 0.3
        if _is_guideline(e) or src in ('US_USPSTF', 'US_VA-DoD', 'US_NCI-PDQ'):
            return 0.18
        return 0.0 if src == 'US_StatPearls' else -0.05
    if mode == 'edu_ko':            # 환자용 한국어 설명
        if src == 'KR_HealthInfo' or ('일반인용' in dt and e['lang'] == '한국어'):
            return 0.35
        return -0.8
    return 0.0


def search(idx: Index | None, queries: list[str], mode: str, k: int = 1, min_cov: float = 0.7) -> list[tuple[float, dict]]:
    if idx is None:
        return []
    best: dict[int, float] = {}
    for q in queries:
        qt = tokens(q)
        if not qt:
            continue
        den = sum(idx.idf.get(t, 0.0) for t in qt) or 1.0
        cand = set()
        for t in qt:
            cand.update(idx.inv.get(t, ()))
        qf = _flat(q)
        for i in cand:
            e = idx.entries[i]
            if mode == 'edu_ko' and _mode_bonus(e, mode) < 0:
                continue  # 환자용 한국어 설명은 KR_HealthInfo 등 일반인용 한국어 문서만
            num = sum(idx.idf.get(t, 0.0) for t in (qt & idx.toks[i]))
            cov = num / den
            if cov < min_cov:
                continue
            tf = _flat(e['title'])
            tden = sum(idx.idf.get(t, 0.0) for t in idx.toks[i]) or 1.0
            tcov = num / tden  # 제목이 질의 외 다른 질환·주제를 얼마나 더 다루는가(낮을수록 다른 문서)
            if tcov < 0.3:
                continue
            s = 0.6 * cov + 0.6 * tcov
            if qf and qf in tf:
                s += 0.3
                if tf.startswith(qf):
                    s += 0.1
            if mode != 'edu_ko':
                for m in OFF_TOPIC.finditer(e['title']):
                    if m.group(0).lower() not in q.lower():
                        s -= 0.3
                        break
            s += _mode_bonus(e, mode)
            if e['year'] >= 2020:
                s += 0.08
            elif e['year'] and e['year'] < 2010:
                s -= 0.08
            if s > best.get(i, -9):
                best[i] = s
    ranked = sorted(best.items(), key=lambda kv: -kv[1])
    out = []
    for i, s in ranked:
        if s < 0.8:
            break
        out.append((s, idx.entries[i]))
        if len(out) >= k:
            break
    return out


# ---------------------------------------------------------------- 발췌
def _clean(text: str) -> str:
    t = re.sub(r'<[^>]+>', ' ', text)
    t = re.sub(r'\[([^\]]+)\]\((?:[^)]*)\)', r'\1', t)
    t = re.sub(r'\[\s*\d+(?:\s*[,–\-]\s*\d+)*\s*\]', '', t)
    t = re.sub(r'\(\s*\d+(?:\s*[,–\-]\s*\d+)*\s*\)', '', t)
    t = re.sub(r'^\s*\|?[\s:\-|]{5,}\|?\s*$', '', t, flags=re.M)
    t = re.sub(r'[*_`]{1,3}', '', t)
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r'\n\s*\n+', '\n', t)
    return t.strip()


def _body(text: str) -> str:
    t = text
    if t.startswith('---'):
        end = t.find('\n---', 3)
        if end > 0:
            t = t[end + 4:]
    lines = [l for l in t.split('\n') if not META_LINE.match(l)]
    return '\n'.join(lines)


def _cut(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    m = max(cut.rfind('. '), cut.rfind('다.'), cut.rfind('\n'))
    return (cut[:m + 1] if m > limit * 0.5 else cut).strip()


def sections(path: str) -> list[tuple[str, str]]:
    try:
        with open(path, encoding='utf-8', errors='ignore') as f:
            raw = f.read()
    except OSError:
        return []
    raw = _body(raw)
    parts = re.split(r'^(#{1,6})\s+(.*)$', raw, flags=re.M)
    out = [('', parts[0])] if parts and parts[0].strip() else []
    for i in range(1, len(parts) - 2, 3):
        out.append((parts[i + 1].strip(), parts[i + 2]))
    return out


def excerpt(path: str, kinds: list[str], chars: int, skip_tx: bool = False) -> str:
    """헤딩 키워드로 kinds 섹션만 골라 합치고 chars로 자른다. 매칭이 없으면 앞부분. skip_tx(v5)면 치료 헤딩 섹션 제외."""
    secs = [(h, b) for h, b in sections(path) if not SKIP_HEAD.search(h) and not (skip_tx and TX_HEAD.search(h))]
    if not secs:
        return ''
    per = max(250, chars // max(1, len(kinds)))
    picked, used = [], set()
    for kd in kinds:
        pat = re.compile(SECTION_KEYS.get(kd, kd), re.I)
        got = [(h, b) for h, b in secs if h and pat.search(h) and h not in used]
        got.sort(key=lambda hb: -len(hb[1]))
        text = ''
        for h, b in got[:2]:
            used.add(h)
            body = _clean(b)
            if len(body) < 40:
                continue
            text += f'{h}: {body}\n'
        if text:
            picked.append(f'({kd}) ' + _cut(text, per))
    if not picked:
        text = ' '.join(_clean(b) for h, b in secs[:3])
        return _cut(text, chars)
    return _cut('\n'.join(picked), chars + 200)


def _cache(enc) -> dict:
    c = getattr(enc, 'gl_cache', None)
    if c is None:
        c = {}
        try:
            enc.gl_cache = c
        except Exception:
            pass
    return c


def _label(e: dict) -> str:
    org = e['org'].split('/')[0].strip()[:30] if e.get('org') else ''
    return f"{e['src']} | {e['title'][:70]}" + (f" ({org}, {e['year']})" if e.get('year') else '')


def gather(enc, queries: list[str], plan: list[tuple[str, list[str], int]], key: str, exclude: set | None = None,
           skip_tx: bool = False) -> tuple[str, list[str]]:
    """plan: [(mode, kinds, chars)] 각각 최상위 문서 하나를 발췌. 반환: (텍스트, 출처 라벨들)."""
    cache = _cache(enc)
    ck = (key, tuple(queries))
    if ck in cache:
        return cache[ck]
    idx = INDEX
    if idx is None or not queries:
        return '', []
    flat_q = []
    for q in queries:
        flat_q += split_dx(q)
    texts, srcs, seen = [], [], set(exclude or ())
    for mode, kinds, chars in plan:
        hits = search(idx, flat_q, mode, k=2)
        for s, e in hits:
            if e['path'] in seen:
                continue
            seen.add(e['path'])
            full = os.path.join(idx.root, e['path'])
            try:
                if mode == 'edu_ko':
                    body = _cut(_clean(' '.join(b for h, b in sections(full) if not SKIP_HEAD.search(h)
                                                and not (skip_tx and TX_HEAD.search(h)))), chars)
                else:
                    body = excerpt(full, kinds, chars, skip_tx)
            except Exception as exc:
                log_error(f'guidelines excerpt failed {e["path"]}: {exc}')
                continue
            if len(body) < 80:
                continue
            texts.append(f'[출처: {_label(e)}]\n{body}')
            srcs.append(f"{e['title'][:80]} ({e['src']}{', ' + str(e['year']) if e.get('year') else ''})")
            break
    res = ('\n\n'.join(texts), srcs)
    if exclude is not None:
        exclude.update(seen)
    cache[ck] = res
    if texts:
        log(f'guidelines[{key}]: ' + ' || '.join(srcs))
    return res


# ---------------------------------------------------------------- v5 계획용 정제: 치료 섹션·용량·성분명·저자 줄 제거
# (code_v4 sanitize 이식. 계획 프롬프트에 약물 치료 서술이 들어가 P·설명이 처방 확정처럼 읽히는 것을 막는다)
TX_HEAD = re.compile(r'treatment|management|therap|pharmaco|medication|drug|dos(?:e|ing|age)|regimen|'
                     r'치료|관리|약물|처방|투약|투여|용량', re.I)
SAN_DOSE = re.compile(r'\d+(?:\.\d+)?\s*(?:mg|㎎|mcg|μg|µg|g\b|mL|ml|IU|단위|정|알|캡슐|%)', re.I)
SAN_REGIMEN = re.compile(r'(용량|증량|감량|하루\s*\d+\s*(?:회|번)|1일\s*\d+\s*(?:회|번)|투여\s*(?:량|횟수)|\bdos(?:e|ing|age)\b|'
                         r'titrat|\bmg/kg\b|once\s+daily|twice\s+daily)', re.I)
SAN_DRUG = re.compile(r'(메티마졸|카비마졸|프로필티오우라실|프로프라놀롤|아테놀롤|메토프롤롤|비소프롤롤|레보티록신|씬지로이드|졸피뎀|'
                      r'스틸녹스|에스조피클론|알프라졸람|로라제팜|디아제팜|클로나제팜|트리아졸람|트라조돈|멜라토닌|에스시탈로프람|'
                      r'설트랄린|플루옥세틴|메트포르민|아목시실린|이부프로펜|아세트아미노펜|타이레놀|오메프라졸|에스오메프라졸|'
                      r'수마트립탄|도네페질|살부타몰|인슐린|방사성\s*요오드|메트폴민|메트포민|메치마졸|티아졸리딘|설포닐|methimazole|carbimazole|propylthiouracil|\bPTU\b|'
                      r'propranolol|atenolol|metoprolol|bisoprolol|levothyroxine|zolpidem|eszopiclone|alprazolam|lorazepam|'
                      r'diazepam|clonazepam|triazolam|trazodone|escitalopram|sertraline|fluoxetine|metformin|amoxicillin|'
                      r'ibuprofen|acetaminophen|omeprazole|esomeprazole|sumatriptan|donepezil|salbutamol|albuterol|insulin|'
                      r'radioactive\s+iodine|\bRAI\b|sulfonylurea|SGLT-?2|DPP-?4|GLP-?1|thiazolidinedione|\bTZDs?\b)', re.I)
# 치료 서술 문장(계획 프롬프트에서는 검사·추적 근거만 남긴다)
SAN_TX = re.compile(r'(치료|투여|투약|처방|복용|요법|약물|수술|절제|중단|항갑상[선샘]제|베타\s*차단제|강하제|억제제|'
                    r'treat|therap|medicat|prescri|surg|thyroidectomy|ablation|initiat)', re.I)
SAN_AUTHOR = re.compile(r'(Department\s+of|College\s+of\s+Medicine|School\s+of\s+Medicine|University|Hospital,|의과대학|교실|'
                        r'저자|교신\s*저자|소속\s*[:：]|E-?mail|Correspondence)', re.I)
SAN_GRADE = re.compile(r'[\(\[]?\s*(?:권고\s*(?:수준|등급|강도)|근거\s*(?:수준|등급)|level\s+of\s+evidence|grade\s+of\s+recommendation)'
                       r'\s*[:：]?\s*[A-Za-z0-9가-힣+\-, ]{0,12}[\)\]]?', re.I)


def sanitize(text: str) -> str:
    """발췌 정제: 문장 단위로 용량·횟수·증량·성분명·치료 서술 문장과 저자·소속 줄을 지우고 권고수준 꼬리표를 뗀다. 실패 시 ''."""
    try:
        out_lines = []
        for line in (text or '').split('\n'):
            if line.startswith('[출처:'):
                out_lines.append(line)
                continue
            if SAN_AUTHOR.search(line):
                continue
            line = SAN_GRADE.sub('', line)
            keep = [s.strip() for s in re.split(r'(?<=[.!?。])\s+|(?<=다\.)\s*|;\s+', line)
                    if s and s.strip() and not (SAN_DOSE.search(s) or SAN_REGIMEN.search(s) or SAN_DRUG.search(s)
                                                or SAN_TX.search(s))]
            line = ' '.join(keep).strip()
            if line and not re.fullmatch(r'\(\w+\)', line):
                out_lines.append(line)
        text = '\n'.join(out_lines)
        return re.sub(r'\[출처:[^\]]*\]\s*(?=\n*\[출처:|\Z)', '', text).strip()  # 본문이 다 지워진 출처 줄
    except Exception as exc:  # noqa: BLE001
        log_error(f'guidelines sanitize failed: {type(exc).__name__}: {exc}')
        return ''


# ---------------------------------------------------------------- 단계별 진입점(실패해도 빈 문자열)
def _on(enc) -> bool:
    try:
        return bool(enc.cfg.get('GUIDE', 1)) and INDEX is not None
    except Exception:
        return False


def hint_interview(enc) -> str:
    """감별진단 상위 2~3개의 병력·진찰·감별 포인트(문진 계획용)."""
    try:
        if not _on(enc):
            return ''
        diffs = [d for d in (enc.differentials or [])[:3] if d]
        if not diffs:
            return ''
        cache = _cache(enc)
        ck = ('iv-all', tuple(diffs))
        if ck in cache:
            return cache[ck]
        parts = []
        for d in diffs:
            t, _ = gather(enc, [d], [('overview', ['hp', 'ddx'], 700)], 'iv')
            if t:
                parts.append(t)
        text = '\n\n'.join(parts)
        out = (f'[진료지침 발췌 — 감별진단별 병력·진찰·감별 포인트(참고, 이미 확인된 것은 다시 묻지 말 것. 출처 제목이 해당 질환과 다르면 무시)]\n{text}\n' if text else '')
        cache[ck] = out
        return out
    except Exception as exc:
        log_error(f'guidelines hint_interview failed: {type(exc).__name__}: {exc}')
        return ''


def hint_dx(enc) -> str:
    """후보 질환의 진단 기준·감별(진단 호출용)."""
    try:
        if not _on(enc):
            return ''
        diffs = [d for d in (enc.differentials or [])[:3] if d]
        if not diffs:
            return ''
        parts = []
        for d in diffs:
            t, _ = gather(enc, [d], [('overview', ['dx', 'ddx', 'hp'], 900)], 'dx')
            if t:
                parts.append(t)
        text = '\n\n'.join(parts)
        return (f'[진료지침 발췌 — 후보 질환의 진단 기준·감별(참고). 사실표에 없는 내용을 사실로 쓰지 말 것. 출처 제목이 해당 질환과 다르면 무시]\n{text}\n' if text else '')
    except Exception as exc:
        log_error(f'guidelines hint_dx failed: {type(exc).__name__}: {exc}')
        return ''


def hint_plan(enc) -> str:
    """주진단의 검사·추적·경고 증상(계획 호출용). 한국 지침 우선, 환자용 한국어 설명 포함.
    v5: 치료 헤딩 섹션을 빼고(skip_tx) sanitize()로 용량·성분명 문장을 지운다(안전 12.5 원인 차단)."""
    try:
        if not _on(enc):
            return ''
        dx = enc.dx or ''
        if not dx:
            return ''
        qs = [dx]
        text_parts, srcs = [], []
        used: set = set()
        t1, s1 = gather(enc, qs, [('mgmt', ['dx', 'fu'], 1700)], 'plan-mgmt', used, skip_tx=True)
        t2, s2 = gather(enc, qs, [('overview', ['dx', 'fu', 'edu'], 1400)], 'plan-ovw', used, skip_tx=True)
        t3, s3 = gather(enc, qs, [('edu_ko', ['edu'], 800)], 'plan-edu', used, skip_tx=True)
        for t, s in ((t1, s1), (t2, s2), (t3, s3)):
            t = sanitize(t)
            if t:
                text_parts.append(t)
                srcs += s
        enc.gl_sources = list(dict.fromkeys(srcs))
        text = '\n\n'.join(text_parts)
        return (f'[진료지침 발췌 — 검사·추적·경고 증상 근거용(치료·약물 내용은 제외됨). 한국 지침 우선, 환자용 한국어 설명은 '
                f'설명 문장 표현 참고용. 출처 제목이 주진단과 다르면 무시]\n{text}\n' if text else '')
    except Exception as exc:
        log_error(f'guidelines hint_plan failed: {type(exc).__name__}: {exc}')
        return ''


def cite_line(enc) -> str:
    try:
        if not enc.cfg.get('GUIDE_CITE', 1):
            return ''
        srcs = list(getattr(enc, 'gl_sources', None) or [])[:3]
        return ('참고 지침 : ' + '; '.join(srcs)) if srcs else ''
    except Exception:
        return ''

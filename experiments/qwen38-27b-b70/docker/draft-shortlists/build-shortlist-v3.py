#!/usr/bin/env python3
"""Draft-head shortlist v3: token frequencies over broad general text (WikiText-103 train, English prose) plus general
Python source (the CPython standard library), tokenized with the served model's tokenizer. Writes v3-top{N}.txt and
reports coverage of the strict suite's recorded outputs for the old and new lists. No lab text is used, so the list
cannot be tuned to the benchmark.

usage: build-shortlist-v3.py --tokenizer /path/model --wikitext wikitext103.txt --stdlib /usr/lib/python3.12 --out DIR
       [--old shortlist-u-v1all-v2top65k.txt] [--strict performance.json ...]
"""
import argparse, collections, json, glob, os
from pathlib import Path
from transformers import AutoTokenizer

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--tokenizer', required=True); ap.add_argument('--wikitext', required=True); ap.add_argument('--stdlib', required=True)
ap.add_argument('--out', required=True); ap.add_argument('--old'); ap.add_argument('--strict', nargs='*', default=[])
ap.add_argument('--max-chars', type=int, default=400_000_000)
a = ap.parse_args()
tok = AutoTokenizer.from_pretrained(a.tokenizer)
counts = collections.Counter(); totals = {}

def count(name, text):
    n = 0
    for i in range(0, len(text), 200_000):
        ids = tok(text[i:i + 200_000], add_special_tokens=False)['input_ids']; counts.update(ids); n += len(ids)
    totals[name] = n

pass
code = ''.join(open(p, errors='ignore').read() for p in sorted(glob.glob(os.path.join(a.stdlib, '*.py'))))
count('cpython-stdlib', code)
ranked = [t for t, _ in counts.most_common()]; special = list(tok.all_special_ids); tot = sum(counts.values())
Path(a.out).mkdir(parents=True, exist_ok=True)
report = {'tokens_per_source': totals, 'distinct': len(counts), 'vocab': len(tok), 'lists': {}}
old = set(int(x) for x in open(a.old).read().split()) if a.old else set()
suite = collections.Counter()
for path in a.strict:
    doc = json.load(open(path))
    rows = doc['rows'] if 'rows' in doc else doc.get('oracle', {}).get('rows', [])
    for row in rows:
        suite.update(row.get('token_ids') or row.get('output_token_ids') or [])
def coverage(S, c): return 100 * sum(v for t, v in c.items() if t in S) / max(1, sum(c.values()))
count('wikitext-103', open(a.wikitext, errors='ignore').read(a.max_chars))
ranked = [t for t, _ in counts.most_common()]; special = list(tok.all_special_ids); tot = sum(counts.values())
if old:
    report['lists']['old-u-v1all-v2top65k'] = {'size': len(old), 'corpus_coverage_pct': coverage(old, counts), 'suite_output_coverage_pct': coverage(old, suite) if suite else None}
for N in (32768, 49152, 65536, 98304):
    S = sorted(set(ranked[:N]) | set(special)); open(f'{a.out}/shortlist-v3-top{N}.txt', 'w').write('\n'.join(map(str, S)) + '\n')
    report['lists'][f'v3-top{N}'] = {'size': len(S), 'corpus_coverage_pct': coverage(set(S), counts), 'suite_output_coverage_pct': coverage(set(S), suite) if suite else None,
                                     'jaccard_vs_old': len(set(S) & old) / len(set(S) | old) if old else None}
json.dump(report, open(f'{a.out}/report.json', 'w'), indent=2); print(json.dumps(report, indent=1))

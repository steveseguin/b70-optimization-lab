"""Inventory retained prepared commands and K2 choices, without executing code."""
import collections
import hashlib
import json
from pathlib import Path

E = Path(__file__).resolve().parent
P = E.parents[1]
S = P.parent
ROOTS = {
    'p44-record': S / 'packet44-context/build/c4096b',
    'p45-dr0': P / 'build/c4096-dr0-gpu',
    'p45-dr1': P / 'build/c4096-dr1-gpu',
    'p44-control-a': S / 'packet44-context/build/c4096ctl15a',
    'p44-control-b': S / 'packet44-context/build/c4096ctl15b',
}
hashes = {}

def raw(path):
    data = path.read_bytes()
    hashes[str(path.relative_to(S))] = hashlib.sha256(data).hexdigest()
    return data

def summarize_comparison(c):
    return {
        'selected': c.get('selected'),
        'selection_timing_mode': c.get('selection_timing_mode'),
        'median_ns': {k: v['execution_sum']['median_ns']
                      for k, v in c.get('variants', {}).items()},
        'workloads': {k: summarize_comparison(v)
                      for k, v in c.get('workloads', {}).items()},
    }

result = {}
for name, root in ROOTS.items():
    dispatch = root / 'K2/run0/dispatch-measured.json'
    if not dispatch.exists():
        continue
    entry = {'dispatch': json.loads(raw(dispatch)), 'ranks': {}}
    summary = root / 'K2/run0/summary.json'
    if summary.exists():
        source = json.loads(raw(summary))
        entry['comparisons'] = {
            k: {'selected': v.get('selected'),
                'comparisons': {c: summarize_comparison(d)
                                for c, d in v.get('comparisons', {}).items()}}
            for k, v in source['classes'].items()
        }
    for rank in (0, 1):
        path = root / f'WS128/run/ranks/rank{rank}/prepared-arguments-parity0.jsonl'
        if not path.exists():
            continue
        rows = [json.loads(x) for x in raw(path).splitlines()]
        labels = collections.Counter(x['label'] for x in rows)
        families = collections.Counter()
        for label, count in labels.items():
            family = label.split('.', 2)[2] if label.startswith('blk.') else label
            families[family] += count
        entry['ranks'][rank] = {
            'commands': len(rows), 'families': dict(sorted(families.items())),
            'labels': dict(sorted(labels.items())),
        }
    result[name] = entry
(E / 'kernels.json').write_text(json.dumps(result, separators=(',', ':')) + '\n')
(E / 'kernel-input-hashes.json').write_text(json.dumps(hashes, indent=2) + '\n')
for name, entry in result.items():
    print(name, {r: v['commands'] for r, v in entry['ranks'].items()})

#!/usr/bin/env python3
"""Test stand-in for scripts/compare-clip.py: same CLI (reference candidate --output P), same report
shape, compares the four sha256s of the two validation summaries under $FAKE_ROOT."""
import argparse, json, os
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('reference')
ap.add_argument('candidate')
ap.add_argument('--output', type=Path, required=True)
a = ap.parse_args()
root = Path(os.environ['FAKE_ROOT'])
assert not a.output.exists()
s = [json.loads((root / 'output/validation' / n / 'summary.json').read_text())['tensors'] for n in (a.reference, a.candidate)]
for n in (a.candidate,):
    for f in ('history.json', 'submission.json', 'result.json', 'prompt.json', 'identity.json'):
        assert (root / 'requests' / n / f).is_file(), (n, f)
comp = {k: {'bitwise_equal': s[0][k]['sha256'] == s[1][k]['sha256']} for k in s[0]}
a.output.write_text(json.dumps({'status': 'passed' if all(v['bitwise_equal'] for v in comp.values()) else 'failed',
                                'comparisons': comp}, indent=1) + '\n')

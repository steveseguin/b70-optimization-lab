#!/usr/bin/env python3
"""Independently compare saved numerical outputs and execution receipts."""
import argparse
import hashlib
import json
from pathlib import Path

import torch
from safetensors.torch import load_file

parser = argparse.ArgumentParser()
parser.add_argument('names', nargs='+')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
assert len(args.names) >= 3 and len(set(args.names)) == len(args.names)
root = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
assert not (root / 'FAULT.json').exists(), 'recorded device fault'
assert not args.output.exists(), 'never overwrite a verification receipt'
assert json.loads((root / 'model-verification.json').read_text())['status'] == 'passed'
all_tensors = []
report = {'status': 'running', 'runs': [], 'comparisons': [],
          'scope': 'same process, same native BF16 checkpoint/workflow/device; full recomputation',
          'cross_process_determinism': 'not tested',
          'parity_against_dev_or_cuda': 'not tested; distinct target/runtime'}
reference_prompt = None
for name in args.names:
    folder = root / 'output/validation' / name
    meta = json.loads((folder / 'summary.json').read_text())
    assert meta['deterministic_enabled'] and not meta['deterministic_warn_only']
    tensors = load_file(str(folder / 'tensors.safetensors'))
    assert list(tensors['images'].shape) == [25, 256, 256, 3]
    assert tensors['images'].std() > 0.01, 'degenerate output'
    assert bool((tensors['images'][1:] != tensors['images'][:-1]).any()), 'all frames identical'
    for key, t in tensors.items():
        assert torch.isfinite(t).all(), (name, key, 'nonfinite')
        actual = hashlib.sha256(t.view(torch.uint8).numpy().tobytes()).hexdigest()
        assert actual == meta['tensors'][key]['sha256'], (name, key, 'capture hash mismatch')
        assert list(t.shape) == meta['tensors'][key]['shape']
        assert str(t.dtype) == meta['tensors'][key]['dtype']
    request = root / 'requests' / name
    history = json.loads((request / 'history.json').read_text())
    assert history['status']['status_str'] == 'success'
    assert not any(msg[1].get('nodes') for msg in history['status']['messages'] if msg[0] == 'execution_cached')
    prompt = json.loads((request / 'prompt.json').read_text())
    for node, field in [('414', 'run_name'), ('413', 'filename_prefix'), ('75', 'filename_prefix')]:
        prompt[node]['inputs'][field] = '<output-path>'
    if reference_prompt is None:
        reference_prompt = prompt
    assert prompt == reference_prompt, 'generation identity changed'
    report['runs'].append({'name': name, 'capture': meta,
                          'seconds': json.loads((request / 'result.json').read_text())['seconds'],
                          'history_sha256': hashlib.sha256((request / 'history.json').read_bytes()).hexdigest()})
    all_tensors.append(tensors)
for i in range(1, len(all_tensors)):
    row = {'reference': args.names[0], 'candidate': args.names[i], 'tensors': {}}
    for key, a in all_tensors[0].items():
        b = all_tensors[i][key]
        same_layout = a.shape == b.shape and a.dtype == b.dtype
        identical = same_layout and torch.equal(a.view(torch.uint8), b.view(torch.uint8))
        row['tensors'][key] = {'bitwise_equal': identical}
        if same_layout:
            row['tensors'][key].update(max_abs_diff=float((a.float() - b.float()).abs().max()),
                                       unequal_values=int((a != b).sum()))
    report['comparisons'].append(row)
report['status'] = 'passed' if all(t['bitwise_equal'] for r in report['comparisons'] for t in r['tensors'].values()) else 'failed'
args.output.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'status': report['status'], 'runs': args.names, 'comparisons': report['comparisons']}, indent=2))
raise SystemExit(0 if report['status'] == 'passed' else 1)

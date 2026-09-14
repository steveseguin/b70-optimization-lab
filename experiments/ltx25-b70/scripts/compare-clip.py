#!/usr/bin/env python3
"""Independent exact-output gate for an explicitly recorded optimization graph."""
import argparse
import hashlib
import json
from pathlib import Path

import torch
from safetensors.torch import load_file

parser = argparse.ArgumentParser()
parser.add_argument('reference')
parser.add_argument('candidate')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
assert not (root / 'FAULT.json').exists()
assert not args.output.exists()
archives = []
identities = []
for name in [args.reference, args.candidate]:
    path = root / 'output/validation' / name
    meta = json.loads((path / 'summary.json').read_text())
    assert meta['deterministic_enabled'] and not meta['deterministic_warn_only']
    tensors = load_file(str(path / 'tensors.safetensors'))
    assert set(tensors) == set(meta['tensors']) == {'images', 'video_latent', 'audio_latent', 'waveform'}
    for key, value in tensors.items():
        assert torch.isfinite(value).all(), (name, key)
        assert hashlib.sha256(value.view(torch.uint8).numpy().tobytes()).hexdigest() == meta['tensors'][key]['sha256']
    request = root / 'requests' / name
    history = json.loads((request / 'history.json').read_text())
    submission = json.loads((request / 'submission.json').read_text())
    result = json.loads((request / 'result.json').read_text())
    prompt = json.loads((request / 'prompt.json').read_text())
    assert history['prompt'][1] == submission['prompt_id'] == result['prompt_id']
    assert history['prompt'][2] == prompt
    assert history['status']['status_str'] == 'success'
    assert not any(m[1].get('nodes') for m in history['status']['messages'] if m[0] == 'execution_cached')
    identities.append({'name': name, 'prompt_id': submission['prompt_id'],
                       'prompt_sha256': hashlib.sha256((request / 'prompt.json').read_bytes()).hexdigest(),
                       'server_identity': json.loads((request / 'identity.json').read_text()),
                       'sample_rate': meta['sample_rate'], 'client_seconds': result['seconds']})
    archives.append(tensors)
assert identities[0]['prompt_id'] != identities[1]['prompt_id']
assert identities[0]['sample_rate'] == identities[1]['sample_rate']
assert identities[0]['server_identity']['model_verification_sha256'] == identities[1]['server_identity']['model_verification_sha256']
comparisons = {}
for key, a in archives[0].items():
    b = archives[1][key]
    layout = a.dtype == b.dtype and a.shape == b.shape
    same = layout and torch.equal(a.view(torch.uint8), b.view(torch.uint8))
    comparisons[key] = {'bitwise_equal': same, 'same_layout': layout}
    if layout:
        comparisons[key].update(max_abs_diff=float((a.float() - b.float()).abs().max()),
                                unequal_values=int((a != b).sum()))
report = {'status': 'passed' if all(x['bitwise_equal'] for x in comparisons.values()) else 'failed',
          'scope': 'exact output comparison; graph changes are intentional and must be reviewed separately',
          'executions': identities, 'comparisons': comparisons}
args.output.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'status': report['status'], 'comparisons': comparisons}, indent=2))
raise SystemExit(0 if report['status'] == 'passed' else 1)

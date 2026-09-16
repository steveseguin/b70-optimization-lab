#!/usr/bin/env python3
"""Exact-output gate against a reference whose raw tensors were pruned.

Same candidate checks as compare-clip.py (archive hashes recomputed from the raw
bytes, strict determinism, finiteness, history/prompt/submission binding, no
cached execution nodes). The reference contributes its recorded per-tensor
SHA-256, dtype and shape from summary.json, plus its request binding; if its raw
tensors are still present they are re-hashed and must agree with the summary.
Equality is SHA-256 equality of the raw bytes of all four outputs, which is the
same relation compare-clip.py checks bytewise.
"""
import argparse, hashlib, json
from pathlib import Path
import torch
from safetensors.torch import load_file

ap = argparse.ArgumentParser()
ap.add_argument('reference'); ap.add_argument('candidate')
ap.add_argument('--output', type=Path, required=True)
a = ap.parse_args()
root = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
assert not (root / 'FAULT.json').exists()
assert not a.output.exists()
KEYS = {'images', 'video_latent', 'audio_latent', 'waveform'}


def request_identity(name):
    request = root / 'requests' / name
    history = json.loads((request / 'history.json').read_text())
    submission = json.loads((request / 'submission.json').read_text())
    result = json.loads((request / 'result.json').read_text())
    prompt = json.loads((request / 'prompt.json').read_text())
    assert history['prompt'][1] == submission['prompt_id'] == result['prompt_id']
    assert history['prompt'][2] == prompt
    assert history['status']['status_str'] == 'success'
    assert not any(m[1].get('nodes') for m in history['status']['messages'] if m[0] == 'execution_cached')
    return {'name': name, 'prompt_id': submission['prompt_id'],
            'prompt_sha256': hashlib.sha256((request / 'prompt.json').read_bytes()).hexdigest(),
            'server_identity': json.loads((request / 'identity.json').read_text())}


def summary(name):
    meta = json.loads((root / 'output/validation' / name / 'summary.json').read_text())
    assert meta['deterministic_enabled'] and not meta['deterministic_warn_only']
    assert set(meta['tensors']) == KEYS
    return meta


def rehash(name, meta):
    tensors = load_file(str(root / 'output/validation' / name / 'tensors.safetensors'))
    assert set(tensors) == KEYS
    for key, value in tensors.items():
        assert torch.isfinite(value).all(), (name, key)
        assert hashlib.sha256(value.view(torch.uint8).numpy().tobytes()).hexdigest() == meta['tensors'][key]['sha256'], (name, key)
        assert list(value.shape) == list(meta['tensors'][key]['shape']) and str(value.dtype) == meta['tensors'][key]['dtype'], (name, key)


ref_meta, cand_meta = summary(a.reference), summary(a.candidate)
rehash(a.candidate, cand_meta)                      # candidate raw bytes are required
ref_raw = (root / 'output/validation' / a.reference / 'tensors.safetensors').is_file()
if ref_raw:
    rehash(a.reference, ref_meta)
ids = [request_identity(a.reference), request_identity(a.candidate)]
assert ids[0]['prompt_id'] != ids[1]['prompt_id']
assert ref_meta['sample_rate'] == cand_meta['sample_rate']
assert ids[0]['server_identity']['model_verification_sha256'] == ids[1]['server_identity']['model_verification_sha256']
comparisons = {}
for key in sorted(KEYS):
    r, c = ref_meta['tensors'][key], cand_meta['tensors'][key]
    layout = r['dtype'] == c['dtype'] and list(r['shape']) == list(c['shape'])
    comparisons[key] = {'bitwise_equal': layout and r['sha256'] == c['sha256'], 'same_layout': layout,
                        'reference_sha256': r['sha256'], 'candidate_sha256': c['sha256']}
report = {'status': 'passed' if all(x['bitwise_equal'] for x in comparisons.values()) else 'failed',
          'scope': 'exact output comparison by raw-byte SHA-256; candidate bytes re-hashed, reference bytes ' +
                   ('re-hashed' if ref_raw else 'pruned after verification, summary hashes used'),
          'reference_raw_present': ref_raw, 'executions': ids, 'comparisons': comparisons}
a.output.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'status': report['status'], 'reference_raw_present': ref_raw}))

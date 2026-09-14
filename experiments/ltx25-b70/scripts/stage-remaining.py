#!/usr/bin/env python3
"""Verify remaining exact components while preserving the failed first attempt."""
import hashlib
import json
import os
from pathlib import Path
import time

source = Path('/mnt/raid-models/models/intake-20260912/Lightricks--LTX-2.5')
target = Path('/mnt/fast-ai/llm-models/LTX-2.5-baseline')
evidence = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
model = next(m for m in json.loads((source.parent / 'download-manifest.json').read_text())['models'] if m['repo'] == 'Lightricks/LTX-2.5')
names = ['latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors',
         'vae/ltx-2.5-audio-vae-bf16.safetensors', 'vae/ltx-2.5-video-vae-bf16.safetensors',
         'text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors']
report = {'revision': model['revision'], 'status': 'running', 'files': []}
receipt = evidence / 'remaining-components-verification.json'

def save():
    temp = receipt.with_suffix('.tmp')
    temp.write_text(json.dumps(report, indent=2) + '\n')
    temp.replace(receipt)

save()
for name in names:
    entry = next(f for f in model['files'] if f['name'] == name)
    src, dst = source / name, target / name
    assert src.stat().st_size == entry['size']
    dst.parent.mkdir(parents=True, exist_ok=True)
    partial = dst.with_suffix('.incoming')
    assert not dst.exists() and not partial.exists()
    h = hashlib.sha256()
    print('copy', name, flush=True)
    with src.open('rb') as fi, partial.open('xb') as fo:
        while block := fi.read(8 * 1024**2):
            h.update(block)
            fo.write(block)
        fo.flush()
        os.fsync(fo.fileno())
    row = {'name': name, 'bytes': entry['size'], 'expected_sha256': entry['sha256'], 'source_sha256': h.hexdigest()}
    report['files'].append(row)
    if h.hexdigest() != entry['sha256']:
        row['status'] = 'failed-source-hash'
        report['status'] = 'failed'
        save()
        raise RuntimeError('source hash mismatch: ' + name)
    hd = hashlib.sha256()
    with partial.open('rb') as fi:
        while block := fi.read(8 * 1024**2):
            hd.update(block)
    row['sha256'] = hd.hexdigest()
    assert hd.hexdigest() == entry['sha256']
    partial.rename(dst)
    row['status'] = 'passed'
    save()
    print('verified', name, flush=True)
report['status'] = 'passed'
save()

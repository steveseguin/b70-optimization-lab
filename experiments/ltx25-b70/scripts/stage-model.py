#!/usr/bin/env python3
"""Copy the selected native BF16 components and verify both reads against intake."""
import hashlib
import json
import os
from pathlib import Path
import time

source = Path('/mnt/raid-models/models/intake-20260912/Lightricks--LTX-2.5')
target = Path('/mnt/fast-ai/llm-models/LTX-2.5-baseline')
receipt = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/model-verification.json')
manifest = json.loads((source.parent / 'download-manifest.json').read_text())
model = next(x for x in manifest['models'] if x['repo'] == 'Lightricks/LTX-2.5')
selected = [x for x in model['files'] if x['name'] in {
    'diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors',
    'text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors',
    'vae/ltx-2.5-video-vae-bf16.safetensors',
    'vae/ltx-2.5-audio-vae-bf16.safetensors',
    'latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors',
}]
assert len(selected) == 5
assert os.path.ismount('/mnt/raid-models')
assert os.statvfs(target).f_bavail * os.statvfs(target).f_frsize > sum(x['size'] for x in selected) + 50 * 1024**3
report = {'revision': model['revision'], 'source': str(source), 'target': str(target), 'files': [], 'status': 'running'}

def save():
    temp = receipt.with_suffix('.tmp')
    temp.write_text(json.dumps(report, indent=2) + '\n')
    temp.replace(receipt)

save()
for entry in selected:
    start = time.monotonic()
    src, dst = source / entry['name'], target / entry['name']
    assert src.stat().st_size == entry['size']
    dst.parent.mkdir(parents=True, exist_ok=True)
    partial = dst.with_suffix('.incoming')
    assert not dst.exists() and not partial.exists(), dst
    h = hashlib.sha256()
    print('copy', entry['name'], flush=True)
    with src.open('rb') as fi, partial.open('xb') as fo:
        for block in iter(lambda: fi.read(8 * 1024**2), b''):
            h.update(block)
            fo.write(block)
        fo.flush()
        os.fsync(fo.fileno())
    assert h.hexdigest() == entry['verified_sha256'], ('source hash', entry['name'])
    hd = hashlib.sha256()
    with partial.open('rb') as fi:
        for block in iter(lambda: fi.read(8 * 1024**2), b''):
            hd.update(block)
    assert hd.hexdigest() == h.hexdigest(), ('destination hash', entry['name'])
    partial.rename(dst)
    report['files'].append({'name': entry['name'], 'bytes': dst.stat().st_size,
                            'sha256': hd.hexdigest(), 'seconds': time.monotonic() - start})
    save()
    print('verified', entry['name'], flush=True)
report['status'] = 'passed'
save()

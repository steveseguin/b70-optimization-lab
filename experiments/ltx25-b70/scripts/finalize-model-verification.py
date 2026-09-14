#!/usr/bin/env python3
"""Verify all five persisted components, then atomically open the generation gate."""
import hashlib
import json
import mmap
import os
from pathlib import Path

root = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
model_root = Path('/mnt/fast-ai/llm-models/LTX-2.5-baseline')
gate = root / 'model-verification.json'
previous = json.loads(gate.read_text())
assert previous['status'] != 'passed', 'preserve the successful gate; this is a one-shot finalizer'
remaining = json.loads((root / 'remaining-components-verification.json').read_text())
repair = json.loads((root / 'localized-repair-promotion.json').read_text())
assert repair['status'] == 'passed'
assert repair['direct_io_sha256'] == repair['expected_sha256']
rows = [
    {'name': 'diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors',
     'bytes': repair['bytes'], 'expected_sha256': repair['expected_sha256']},
    *remaining['files']]
assert len(rows) == len({row['name'] for row in rows}) == 5
manifest = json.loads(Path('/mnt/raid-models/models/intake-20260912/download-manifest.json').read_text())
model = next(m for m in manifest['models'] if m['repo'] == 'Lightricks/LTX-2.5')
assert model['revision'] == remaining['revision']
expected = {f['name']: f for f in model['files']}
report = {'revision': remaining['revision'], 'target': str(model_root), 'status': 'verifying',
          'original_staging_status': remaining['status'], 'files': []}
for row in rows:
    assert row['expected_sha256'] == expected[row['name']]['sha256']
    assert row['bytes'] == expected[row['name']]['size']
    path = model_root / row['name']
    assert path.stat().st_size == row['bytes']
    fd = os.open(path, os.O_RDONLY | os.O_DIRECT)
    h = hashlib.sha256()
    try:
        with mmap.mmap(-1, 8 * 1024**2) as buffer:
            size_left = row['bytes']
            while size_left:
                n = os.readv(fd, [buffer])
                assert n > 0
                h.update(buffer[:n])
                size_left -= n
    finally:
        os.close(fd)
    assert h.hexdigest() == row['expected_sha256'], ('persisted hash mismatch', row['name'])
    report['files'].append({'name': row['name'], 'bytes': row['bytes'],
                            'sha256': h.hexdigest(), 'direct_io_verified': True})
    print('direct-io verified', row['name'], flush=True)
assert len(report['files']) == 5
report['status'] = 'passed'
temp = root / 'model-verification.tmp'
with temp.open('w') as f:
    f.write(json.dumps(report, indent=2) + '\n')
    f.flush()
    os.fsync(f.fileno())
temp.replace(root / 'model-verification.json')
fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
os.fsync(fd)
os.close(fd)
print('PASS: all five exact native BF16 components verified; generation gate open', flush=True)

#!/usr/bin/env python3
"""One bounded candidate: replace independently compared bytes, require full SHA."""
import hashlib
import json
import mmap
import os
from pathlib import Path

evidence = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
original = evidence / 'quarantine/ltx-2.5-distilled-transformer-ad9eb77d.rejected'
candidate = Path('/mnt/fast-ai/llm-models/LTX-2.5-baseline/diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.repair-candidate')
expected = '31eb3cad89b9e54e99dd3baf286f70825ac4f6c660a70d9184d895be76d7bff4'
comparison = json.loads((evidence / 'repair-block-comparison.json').read_text())
replacement = (evidence / 'repair-block-publisher.bin').read_bytes()
assert hashlib.sha256(replacement).hexdigest() == comparison['publisher_block_sha256']
offset = comparison['block_offset']
assert offset % (8 * 1024**2) == 0
h = hashlib.sha256()
with original.open('rb') as src, candidate.open('xb') as out:
    position = 0
    while block := src.read(8 * 1024**2):
        if position == offset:
            assert hashlib.sha256(block).hexdigest() == comparison['bad_block_sha256']
            block = replacement
        out.write(block)
        h.update(block)
        position += len(block)
    out.flush()
    os.fsync(out.fileno())
report = {'expected_sha256': expected, 'candidate_sha256': h.hexdigest(), 'bytes': position,
          'original': str(original), 'candidate': str(candidate), 'repair': comparison,
          'status': 'candidate-hash-match' if h.hexdigest() == expected else 'failed'}
receipt = evidence / 'localized-repair-verification.json'
receipt.write_text(json.dumps(report, indent=2) + '\n')
assert h.hexdigest() == expected, 'candidate still differs; retain artifacts and continue full download'
hd = hashlib.sha256()
fd = os.open(candidate, os.O_RDONLY | os.O_DIRECT)
try:
    with mmap.mmap(-1, 8 * 1024**2) as buffer:
        remaining = position
        while remaining:
            n = os.readv(fd, [buffer])
            assert n > 0
            hd.update(buffer[:n])
            remaining -= n
finally:
    os.close(fd)
report['direct_io_sha256'] = hd.hexdigest()
report['status'] = 'passed' if hd.hexdigest() == expected else 'failed-persisted-hash'
receipt.write_text(json.dumps(report, indent=2) + '\n')
assert report['status'] == 'passed'
print(json.dumps(report, indent=2), flush=True)

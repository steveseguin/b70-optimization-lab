#!/usr/bin/env python3
"""Make one separate repair candidate; publish only after two full hash passes."""
import hashlib
import json
import mmap
import os
from pathlib import Path

root = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
original = root / 'quarantine/gemma4-encoder-24ab21fc.rejected'
dest = Path('/mnt/fast-ai/llm-models/LTX-2.5-baseline/text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors')
candidate = dest.with_suffix('.repair-candidate')
expected = 'ef7243612fdae7a75cb4d5cee9433e81380675fb6c213bd98ae74a9cd16561d1'
comparison = json.loads((root / 'encoder-damage-localization.json').read_text())
assert comparison['status'] == 'localized-candidate'
assert comparison['block_size'] == 8 * 1024**2
replacements = {row['offset']: row for row in comparison['differences']}
assert replacements and not dest.exists()
seen = set()
h = hashlib.sha256()
with original.open('rb') as src, candidate.open('xb') as out:
    position = 0
    while block := src.read(comparison['block_size']):
        if position in replacements:
            row = replacements[position]
            assert hashlib.sha256(block).hexdigest() == row['old_sha256']
            replacement = (root / f'encoder-repair-blocks/{position}-new.bin').read_bytes()
            assert len(replacement) == len(block)
            assert hashlib.sha256(replacement).hexdigest() == row['new_sha256']
            block = replacement
            seen.add(position)
        out.write(block)
        h.update(block)
        position += len(block)
    out.flush()
    os.fsync(out.fileno())
assert seen == set(replacements)
report = {'expected_sha256': expected, 'candidate_sha256': h.hexdigest(), 'bytes': position,
          'original': str(original), 'candidate': str(candidate), 'repair': comparison,
          'status': 'candidate-hash-match' if h.hexdigest() == expected else 'failed'}
receipt = root / 'encoder-repair-verification.json'
assert not receipt.exists()
receipt.write_text(json.dumps(report, indent=2) + '\n')
assert h.hexdigest() == expected, 'candidate still differs; preserve it and continue full download'
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
assert not dest.exists(), 'another verified publisher may have completed; preserve both'
candidate.rename(dest)
fd = os.open(dest.parent, os.O_RDONLY | os.O_DIRECTORY)
os.fsync(fd)
os.close(fd)
report['promoted_path'] = str(dest)
(root / 'encoder-repair-promotion.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'status': 'passed', 'bytes': position, 'sha256': hd.hexdigest(),
                  'repaired_blocks': len(replacements), 'promoted_path': str(dest)}), flush=True)

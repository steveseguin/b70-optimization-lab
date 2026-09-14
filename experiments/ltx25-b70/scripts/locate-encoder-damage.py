#!/usr/bin/env python3
"""Compare each completed download block once; stop after a localized cluster."""
import hashlib
import json
from pathlib import Path
import time

root = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
original = root / 'quarantine/gemma4-encoder-24ab21fc.rejected'
download = Path('/mnt/fast-ai/llm-models/LTX-2.5-baseline/text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.download-incoming')
blocks = root / 'encoder-repair-blocks'
blocks.mkdir(exist_ok=False)
report = {'block_size': 8388608, 'checked_bytes': 0, 'differences': [], 'status': 'scanning-download'}
receipt = root / 'encoder-damage-localization.json'
deadline = time.monotonic() + 4000
with original.open('rb') as a, download.open('rb') as b:
    while time.monotonic() < deadline:
        available = max(0, download.stat().st_size // 8388608 * 8388608 - 8388608)
        while report['checked_bytes'] < available:
            offset = report['checked_bytes']
            x, y = a.read(8388608), b.read(8388608)
            assert len(x) == len(y) == 8388608
            if x != y:
                (blocks / f'{offset}-old.bin').write_bytes(x)
                (blocks / f'{offset}-new.bin').write_bytes(y)
                row = {'offset': offset, 'old_sha256': hashlib.sha256(x).hexdigest(),
                       'new_sha256': hashlib.sha256(y).hexdigest(),
                       'byte_changes': [{'offset': offset+i, 'before': u, 'after': v}
                                        for i, (u, v) in enumerate(zip(x, y)) if u != v]}
                report['differences'].append(row)
                print('DIFFERING BLOCK', offset, len(row['byte_changes']), flush=True)
            report['checked_bytes'] += 8388608
            if report['differences'] and report['checked_bytes'] > report['differences'][-1]['offset'] + 64*1024**2:
                report['status'] = 'localized-candidate'
                receipt.write_text(json.dumps(report, indent=2) + '\n')
                print('localized candidate ready', report['checked_bytes'], flush=True)
                raise SystemExit(0)
        receipt.write_text(json.dumps(report, indent=2) + '\n')
        time.sleep(3)
raise TimeoutError('no complete localization before deadline; inspect download')

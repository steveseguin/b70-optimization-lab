#!/usr/bin/env python3
"""One-attempt pinned BF16 download; publish only after a direct-I/O hash pass."""
import argparse
import hashlib
import json
import mmap
import os
from pathlib import Path
import time
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('filename')
args = parser.parse_args()
root = Path('/mnt/fast-ai/llm-models/LTX-2.5-baseline')
evidence = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
manifest = json.loads(Path('/mnt/raid-models/models/intake-20260912/download-manifest.json').read_text())
model = next(m for m in manifest['models'] if m['repo'] == 'Lightricks/LTX-2.5')
entry = next(f for f in model['files'] if f['name'] == args.filename)
dest = root / entry['name']
dest.parent.mkdir(parents=True, exist_ok=True)
partial = dest.with_suffix('.download-incoming')
assert not dest.exists() and not partial.exists()
report_path = evidence / (dest.stem + '-download.json')
report = {'revision': model['revision'], 'file': entry['name'], 'expected_sha256': entry['sha256'],
          'bytes': entry['size'], 'status': 'downloading'}

def save():
    temp = report_path.with_suffix('.tmp')
    temp.write_text(json.dumps(report, indent=2) + '\n')
    temp.replace(report_path)

save()
start = time.monotonic()
try:
    token = Path('/home/steve/.config/huggingface/token').read_text().strip()
    url = f"https://huggingface.co/Lightricks/LTX-2.5/resolve/{model['revision']}/{entry['name']}?download=true"
    request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token,
                                                  'Range': f"bytes=0-{entry['size'] - 1}"})
    h = hashlib.sha256()
    count = 0
    logged = 0
    with urllib.request.urlopen(request, timeout=120) as response, partial.open('xb') as out:
        assert response.status in (200, 206)
        if response.status == 206:
            assert response.headers['Content-Range'] == f"bytes 0-{entry['size'] - 1}/{entry['size']}"
        while block := response.read(8 * 1024**2):
            out.write(block)
            h.update(block)
            count += len(block)
            if count - logged >= 1024**3:
                print(json.dumps({'file': entry['name'], 'GB': round(count/1e9, 2),
                                  'MB_per_s': round(count / (time.monotonic() - start) / 1e6, 2)}), flush=True)
                logged = count
        out.flush()
        os.fsync(out.fileno())
    assert count == entry['size'], ('size', count)
    report['download_sha256'] = h.hexdigest()
    assert h.hexdigest() == entry['sha256'], 'network hash mismatch'
    report['status'] = 'verifying-persisted-bytes'
    save()
    hd = hashlib.sha256()
    fd = os.open(partial, os.O_RDONLY | os.O_DIRECT)
    try:
        with mmap.mmap(-1, 8 * 1024**2) as buffer:
            remaining = count
            while remaining:
                n = os.readv(fd, [buffer])
                assert n > 0
                hd.update(buffer[:n])
                remaining -= n
    finally:
        os.close(fd)
    report['direct_io_sha256'] = hd.hexdigest()
    assert hd.hexdigest() == entry['sha256'], 'persisted hash mismatch'
    partial.rename(dest)
    fd = os.open(dest.parent, os.O_RDONLY | os.O_DIRECTORY)
    os.fsync(fd)
    os.close(fd)
    report['seconds'] = time.monotonic() - start
    report['status'] = 'passed'
    save()
    print(json.dumps(report), flush=True)
except Exception as error:
    report['status'] = 'failed'
    report['error_type'] = type(error).__name__
    report['http_status'] = getattr(error, 'code', None)
    save()
    raise RuntimeError(f'download/verification failed; see {report_path}') from None

#!/bin/bash
# Refuse a sealed packet that the host freeze truncated. A freeze zeroes every
# file the page cache had not flushed; on 2026-09-17 a whole packet (1,397 files)
# came back empty and its zero-byte launcher made `--check-only` exit 0 with no
# output. Exit 0 only when the packet has no zero-byte files, a non-empty
# launcher and checker, and the manifest hashes every listed file correctly.
set -u
P="${1:?packet dir}"
[ -d "$P" ] || { echo "no such packet: $P"; exit 1; }
# Zero-byte files are only acceptable when the manifest lists them with the
# hash of empty content (ComfyUI ships empty __init__.py placeholders).
z=$(python3 - "$P" <<'PY'
import hashlib, json, os, sys
from pathlib import Path
p = Path(sys.argv[1]); empty = hashlib.sha256(b'').hexdigest()
try:
    listed = json.loads((p / 'manifest.json').read_text())['files']
except Exception:
    print(10**6); sys.exit(0)
bad = 0
for f in p.rglob('*'):
    if f.is_file() and f.stat().st_size == 0:
        rel = str(f.relative_to(p))
        if listed.get(rel) != empty:
            bad += 1
print(bad)
PY
)
[ "$z" -eq 0 ] || { echo "packet integrity: $z zero-byte files not declared empty by the manifest in $P (freeze-truncated); do not launch"; exit 1; }
for f in launch/serve-encoder.py launch/encoder_runtime_common.py manifest.json; do
  [ -s "$P/$f" ] || { echo "packet integrity: missing or empty $f"; exit 1; }
done
python3 - "$P" <<'PY' || exit 1
import hashlib, json, sys
from pathlib import Path
p = Path(sys.argv[1]); m = json.loads((p / 'manifest.json').read_text())
bad = [n for n, d in m['files'].items() if not (p / n).is_file() or hashlib.sha256((p / n).read_bytes()).hexdigest() != d]
print('packet integrity: %d files listed, %d mismatched' % (len(m['files']), len(bad)))
sys.exit(1 if bad else 0)
PY
echo "packet integrity: ok ($P)"

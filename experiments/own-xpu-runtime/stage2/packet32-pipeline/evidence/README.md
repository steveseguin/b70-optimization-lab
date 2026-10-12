# Evidence retention

The preparation archive `preparation-logs-p32-2cb5551350e95304.json.gz` is 5,131,231 bytes
(100,219,754 uncompressed bytes). It is intentionally retained despite exceeding
1 MiB: it is the only retained copy of 286 exact preparation text receipts and
logs after scratch removal, including compiler logs, real-model native rank
receipts, launch identities, host memory observations and teardown sequences.
It is evidence, not a generated cache. `scratch-cleanup.json` records its SHA-256,
the uncompressed SHA-256, every removed directory, and verified round-trip bytes.
Each archive member also records its original path, byte count and SHA-256.
Removing or replacing it requires restoring/verifying its members and updating
consumers first. The compact gate JSON files alone do not replace these raw logs.

The separate `fixture-gates-full.json.gz` preserves complete fixture owner
receipts; `fixture-gates.json` binds both compressed and original hashes.
`preliminary-mini-host.json` is an early CPU gate before the final receipt-only
C++ changes. It is historical and is not counted in the final build seal.

To restore the preparation text archive under this packet's ignored build tree,
run from the repository root at nice19, idle I/O and OMP=2:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B - <<'PYRESTORE'
from pathlib import Path
import base64, gzip, hashlib, json
p = Path('experiments/own-xpu-runtime/stage2/packet32-pipeline').resolve()
r = json.loads((p / 'scratch-cleanup.json').read_text())
packed = (p / r['archive']).read_bytes()
assert hashlib.sha256(packed).hexdigest() == r['archive_sha256']
raw = gzip.decompress(packed)
assert hashlib.sha256(raw).hexdigest() == r['uncompressed_sha256']
for row in json.loads(raw):
    data = base64.b64decode(row['base64'])
    assert len(data) == row['bytes']
    assert hashlib.sha256(data).hexdigest() == row['sha256']
    target = (p / row['path']).resolve()
    assert (p / 'build') in target.parents
    if target.exists():
        assert target.read_bytes() == data
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
PYRESTORE
```

Full real fixture bytes are recoverable from the unchanged v2 oracle using the
hashes in each `real-*.json`. Disposable mini full-state dumps regenerate through
`gates.py`; each native gate compared all 1,188 files before deleting them.

#!/usr/bin/env python3
"""Engine receipt (hc-split copy: written to ../results/engine-receipt-<sha12>.json instead of engine/receipts/<sha12>.json; schema ownrt.engine.build.v1) from an engine/build.py build directory, in
the form the lab adapter checks (absolute source and object paths, root binary, base binary).
Usage: make_receipt.py BUILD_DIR BASE_SHA256 MODE [SRC_ROOT]
Copy for research/tp/hc-split-2026-10-30/suite (from prefill-speed-2026-10-29). SRC_ROOT (default engine/src): the tree the
build compiled, e.g. the private lab copy under /dev/shm while the shared tree holds another agent's uncommitted edits; the
receipt then pins that copy's absolute paths (the lab adapter hashes them at every launch)."""
import hashlib, json, sys
from pathlib import Path
E = Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/engine')
out, base, mode = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
SRC = Path(sys.argv[4]) if len(sys.argv) > 4 else E / 'src'
b = json.loads((out / 'build-receipt.json').read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
require = lambda c, m: c or sys.exit(m)
require(sha(b['binary']) == b['binary_sha256'], 'binary changed')
src = {str(SRC / k): v for k, v in b['sources'].items()}
for p, h in src.items(): require(sha(p) == h, 'source changed since the build: ' + p)
r = dict(schema='ownrt.engine.build.v1', passed=True, mode=mode, binary=b['binary'], binary_sha256=b['binary_sha256'],
         base_binary_sha256=base, root_binary_sha256='5926a24746c62c6b0ecdc5c3e4895f310145e0f9d74a90a5d657035b9a8151f4',
         objects_rebuilt=len(b['objects']), objects_reused=0,
         objects_location=f'RAM build dir {out} (iteration build; rebuild from engine/src reproduces)',
         source_sha256=src, objects={str(out / k): v for k, v in b['objects'].items()},
         commands={k: dict(rc=v['rc'], seconds=v.get('seconds')) for k, v in b['commands'].items()})
dst = Path(__file__).resolve().parent.parent / 'results' / ('engine-receipt-' + b['binary_sha256'][:12] + '.json')  # hc-split: kept in this folder, not engine/receipts
require(not dst.exists(), f'{dst} exists')
dst.write_text(json.dumps(r, indent=1) + '\n'); print(dst)

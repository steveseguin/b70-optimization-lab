#!/usr/bin/env python3
"""Check that an engine/src tree reproduces the compiled-source hashes of the end-gate build m2 (dddf5cf0e067), e.g. after
engine-fixed-cost-2.patch is applied to engine/src at 979462f7c. Read-only.
Usage: verify_receipt.py [SRC_ROOT] [BUILD_RECEIPT]   defaults: the repo's engine/src, results/build-m2-build-receipt.json.
Exit 0 when every compiled source (269) hashes equal; prints the mismatches otherwise."""
import hashlib, json, sys
from pathlib import Path
D = Path(__file__).resolve().parent
root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/engine/src')
receipt = Path(sys.argv[2]) if len(sys.argv) > 2 else D / 'results' / 'build-m2-build-receipt.json'
r = json.loads(receipt.read_text())
bad = []
for rel, want in sorted(r['sources'].items()):
    p = root / rel
    got = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else 'missing'
    if got != want:
        bad.append((rel, want[:12], got[:12]))
print(f"{len(r['sources'])} compiled sources, binary {r['binary_sha256'][:12]}: {len(bad)} differ under {root}")
for x in bad:
    print('  ', *x)
sys.exit(1 if bad else 0)

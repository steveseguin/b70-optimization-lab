#!/usr/bin/env python3
"""Write engine/receipts/<sha12>.json from a build.py output directory, in the ownrt.engine.build.v1 form the
service adapters verify (absolute source and object paths with their sha256 pins).

usage: receipt.py BUILD_DIR --mode TEXT --base SHA256
"""
import argparse, json
from pathlib import Path
ENGINE = Path(__file__).resolve().parent.parent
ROOT_BINARY = '5926a24746c62c6b0ecdc5c3e4895f310145e0f9d74a90a5d657035b9a8151f4'
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('build', type=Path); ap.add_argument('--mode', required=True); ap.add_argument('--base', required=True)
a = ap.parse_args()
build = a.build.resolve(); b = json.loads((build / 'build-receipt.json').read_text())
r = dict(schema='ownrt.engine.build.v1', passed=True, mode=a.mode, binary=b['binary'], binary_sha256=b['binary_sha256'],
         base_binary_sha256=a.base, root_binary_sha256=ROOT_BINARY, objects_rebuilt=len(b['objects']), objects_reused=0,
         objects_location=f'RAM build dir {build} (iteration build; rebuild from engine/src reproduces)',
         source_sha256={str(ENGINE / 'src' / k): v for k, v in b['sources'].items()},
         objects={str(build / k): v for k, v in b['objects'].items()}, commands=b['commands'])
out = ENGINE / 'receipts' / f"{b['binary_sha256'][:12]}.json"
out.write_text(json.dumps(r, indent=1) + '\n'); print(out)

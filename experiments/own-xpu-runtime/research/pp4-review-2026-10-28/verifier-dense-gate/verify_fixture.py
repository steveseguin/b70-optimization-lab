#!/usr/bin/env python3
"""Bounded source/fixture hash check before a separately coordinated kernel run."""
from hashlib import sha256
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
registration=json.loads((HERE/'registration.json').read_text())
for path,digest in registration['source_pins'].items():
    if sha256(Path(path).read_bytes()).hexdigest()!=digest:raise SystemExit('Source changed: '+path)
for path,digest in registration['harness_pins'].items():
    if sha256((HERE/path).read_bytes()).hexdigest()!=digest:raise SystemExit('Harness changed: '+path)
root=Path(sys.argv[1]);receipt=json.loads((root/'fixture.json').read_text())
if receipt['registration_sha256']!=sha256((HERE/'registration.json').read_bytes()).hexdigest():raise SystemExit('Fixture registration changed')
for name,size,key in (('weights.q5k',18022400,'weights_sha256'),('inputs.f32',30720,'inputs_sha256')):
    path=root/name
    if path.is_symlink() or not path.is_file() or path.stat().st_size!=size:raise SystemExit('Bounded regular fixture required: '+name)
    if sha256(path.read_bytes()).hexdigest()!=receipt[key]:raise SystemExit('Fixture changed: '+name)
print(json.dumps(dict(passed=True,scope='Source/fixture hashes only; no compilation or device execution')))

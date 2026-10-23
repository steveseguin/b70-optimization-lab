"""Read-only, hash-bound reuse of packet196's proven local safety helpers."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def verify():
    pins = json.loads((HERE / 'helper-pins.json').read_text())
    for name, digest in pins['files_sha256'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError('shared lifecycle helper changed: ' + name)
    return pins


pins = verify()
PARENT = ROOT / pins['parent']
spec = importlib.util.spec_from_file_location('packet197_owned_safety_import', PARENT / 'safety.py')
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
S.UNIT = 'packet197-warm-request-front-a'  # private module instance; no source or other process is changed
RESTORE = PARENT / 'restore.py'

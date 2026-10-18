"""Fail closed on live pins outside this packet; no directory exceptions."""
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[3]


def allowed_inputs():
    row = json.loads((P / 'immutable-inputs.json').read_text())
    binding = P / 'oracle-binding.json'
    assert hashlib.sha256(binding.read_bytes()).hexdigest() == row['oracle_binding_sha256']
    oracle = json.loads(binding.read_text())['files_sha256']
    pins = row['files_sha256']
    assert all(pins.get(n) == h for n, h in oracle.items())
    for name in pins.keys() - oracle.keys():
        path = Path(name)
        assert '/packet58j-onecard-port/build/' in name
        assert path.suffix == '.o' or path.name in ('own-rt-iq3', 'p58-cache-fixtures', 'fullshape-submit')
    return pins


def check_pins(root, pins):
    if not isinstance(pins, dict) or not pins:
        raise ValueError('empty pin closure')
    allowed = allowed_inputs()
    for name, digest in pins.items():
        rel = Path(name)
        if rel.is_absolute() or '..' in rel.parts:
            raise ValueError('unsafe pinned path: ' + name)
        path = (root / rel).resolve()
        if not path.is_relative_to(P):
            key = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
            if allowed.get(key) != digest:
                raise ValueError('external mutable pin refused: ' + name)

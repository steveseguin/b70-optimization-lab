"""Local pin boundary; independent authoritative lanequeue pin_guard still runs."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
def check_pins(root,pins):
    if not pins:raise ValueError('empty pin map')
    oracle=json.loads((P/'oracle-binding.json').read_text())['files_sha256']
    binary=json.loads((P/'evidence/build.json').read_text())['immutable_binary_inputs']
    for name,digest in pins.items():
        p=(root/name).resolve()
        if p.is_relative_to(P):continue
        key=str(p.relative_to(ROOT))
        if oracle.get(key)!=digest and binary.get(key)!=digest:raise ValueError('external mutable pin: '+name)

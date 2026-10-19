"""Only the owning packet and registered oracle may appear in live source pins."""
from pathlib import Path
import json
P=Path(__file__).resolve().parents[1]
ROOT=P.parents[3]
def allowed_inputs():return json.loads((P/'oracle-binding.json').read_text())['files_sha256']
def check_pins(root,pins):
    if not isinstance(pins,dict) or not pins:raise ValueError('empty pin closure')
    allowed=allowed_inputs()
    for n,h in pins.items():
        rel=Path(n)
        if rel.is_absolute() or '..' in rel.parts:raise ValueError('unsafe pinned path')
        path=(root/rel).resolve()
        if path.is_relative_to(P):continue
        key=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
        if allowed.get(key)!=h:raise ValueError('external mutable pin refused: '+n)

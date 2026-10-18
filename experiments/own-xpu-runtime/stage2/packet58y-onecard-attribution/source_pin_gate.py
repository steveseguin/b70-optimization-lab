"""Reject seals that depend on mutable paths outside this packet."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]

def validate_pins(root,pins):
    if not isinstance(pins,dict) or not pins:raise ValueError('empty pins')
    allowed=json.loads((P/'immutable-inputs.json').read_text())['files']
    for name,digest in pins.items():
        rel=Path(name)
        if rel.is_absolute() or '..' in rel.parts:raise ValueError('unsafe pinned path: '+name)
        path=root/rel;resolved=path.resolve()
        if resolved.is_relative_to(P):continue
        key=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else ''
        row=allowed.get(key)
        if not row or row['sha256']!=digest or row['resolved_path']!=str(resolved):
            raise ValueError('external mutable pinned path: '+name)

def validate_receipt(row):
    validate_pins(ROOT,row['sources'])
    for key in ('gates','artifacts'):validate_pins(P,row[key])


def validate_metadata():
    # Local copy of the lab's parser: inspect every reachable current pin map.
    # Historical lineage is deliberately opaque; its own bytes remain sealed.
    import pin_inventory as inventory
    pins,manifests=inventory.collect_pins(P,ROOT)
    for path,digest,source in pins:
        if path.is_relative_to(P) and path.resolve().is_relative_to(P):continue
        if not path.is_relative_to(ROOT):raise ValueError('pin escapes repository: '+str(path))
        validate_pins(ROOT,{str(path.relative_to(ROOT)):digest})
    return dict(pins=len(pins),manifests=len(manifests))

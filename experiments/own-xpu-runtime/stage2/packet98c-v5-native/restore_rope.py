"""Restore only the ignored generated header from its immutable local parent."""
import hashlib
import json
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
def restore():
    pins=json.loads((P/'source-copy-provenance.json').read_text())['packet97']
    for name,digest in pins.items():
        if not name.endswith('/build/fusion-rope.hpp'):continue
        source=ROOT/name
        target=P/'sources'/name.split('/build/checked/',1)[1]
        raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()==digest
        assert not target.exists() or target.read_bytes()==raw
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():target.write_bytes(raw)
if __name__=='__main__':restore()

#!/usr/bin/env python3
"""Restore read-only parent fixtures and packet-owned output view, CPU only."""
import json
import os
from pathlib import Path
from storage import B,REGISTERED_CHAIN,digest
P=Path(__file__).resolve().parent
PARENT=P.parent/'packet56-draft-prefix'
def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert not (B/REGISTERED_CHAIN).exists(),'chain already started'
    parent=json.loads((PARENT/'build-receipt.json').read_text())
    B.mkdir(parents=True,exist_ok=True)
    for name,expected in parent['artifacts_sha256'].items():
        if name in ('device/own-rt-iq3','gnu-host/own-rt-iq3'):continue
        source=PARENT/'build'/name;dest=P/'build'/name
        assert digest(source)==expected,name
        dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():dest.symlink_to(source.resolve())
        assert digest(dest)==expected
    for dest,source in ((P/'build/input',PARENT/'build/input'),(P/'build'/REGISTERED_CHAIN,B/REGISTERED_CHAIN)):
        if not dest.is_symlink():dest.symlink_to(source.resolve())
        assert dest.resolve()==source.resolve()
    from prepare_inputs import restore
    print(json.dumps(restore()))
if __name__=='__main__':main()

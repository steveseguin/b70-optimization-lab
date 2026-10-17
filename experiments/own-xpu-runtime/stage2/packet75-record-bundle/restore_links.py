#!/usr/bin/env python3
"""Restore ignored read-only links from packet65/56; never build, load or execute a model."""
import json
import os
from pathlib import Path
from storage import digest as sha
from bundle_selection import EXPERTS
P=Path(__file__).resolve().parent
BASE=P.parent/'packet65-expert-occupancy'

def link(source,destination,hard=False):
    destination.parent.mkdir(parents=True,exist_ok=True)
    if not destination.exists() and not destination.is_symlink():
        os.link(source.resolve(),destination) if hard else destination.symlink_to(source.resolve())
    if source.is_file():
        if sha(source)!=sha(destination):raise ValueError('restored file differs: '+str(destination))
    elif source.resolve()!=destination.resolve():raise ValueError('directory binding differs')

def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    build=json.loads((P/'build-device-receipt.json').read_text())
    for name,expected in build['artifacts'].items():
        if sha(BASE/name)!=expected:raise ValueError('packet65 binary changed')
        link(BASE/name,P/name)
    link(P.parent/'packet49-integrate/oracle',P/'oracle')
    for expert in EXPERTS:
        source=BASE/'selections'/expert
        target=P/'selections'/('1-draft-hc-batch-'+expert)
        seal=json.loads((source/'screen-seal.json').read_text())
        for name,expected in dict(seal['artifacts'],**seal['fixture_files']).items():
            if sha(source/name)!=expected:raise ValueError('parent artifact changed')
            link(source/name,target/name,hard=True)
    from prepare_chain import main as restore_chain
    restore_chain()
    print('PASS: references restored without compilation or model execution')

if __name__=='__main__':main()

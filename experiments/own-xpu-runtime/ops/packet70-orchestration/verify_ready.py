#!/usr/bin/env python3
"""Coordinator entry guard: a mock or stale readiness record cannot launch a chain."""
import json
import os
from pathlib import Path
import orchestrate as o

def verify(row,root=o.ROOT,boot=None):
    o.require(row.get('ready') is True and row.get('dry_run') is False
              and row.get('chain_launched') is False,'real completed CPU preparation required')
    boot=boot or Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    o.require(row['boot_id']==boot,'ready boot changed')
    o.require(row['command']==o.chain_command(),'chain command changed')
    for key,name in (('build_receipt_sha256','build-receipt.json'),('selection_sha256','selection.json')):
        o.require(row[key]==o.digest(root/o.PACKET/name),'ready packet bytes changed: '+name)
    for name,expected in row['orchestration_sources'].items():
        o.require(o.digest(o.HERE/name)==expected,'orchestration source changed: '+name)
    return row

if __name__=='__main__':
    o.require(os.getpriority(os.PRIO_PROCESS,0)==19 and set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32)), 'CPU helper conditions required')
    verify(o.read(o.HERE/'ready.json'));print('PASS: current real ready record')

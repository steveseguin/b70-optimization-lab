#!/usr/bin/env python3
"""Verify packet69's own CPU-only wrapper seal; never writes frozen parents."""
from common import ROOT,HERE,read,require,verify_map

def verify():
    row=read(HERE/'wrapper-seal.json')
    require(row['passed'] is True and row['device_executed'] is False,'wrapper gate missing')
    verify_map(ROOT,row['sources'])
    require({str(p.relative_to(ROOT)) for p in HERE.glob('*.py')} <= set(row['sources']), 'unsealed wrapper source')
    return row

if __name__=='__main__':
    from conditions import cpu_gate
    cpu_gate();verify();print('PASS: packet69 screen wrapper seal')

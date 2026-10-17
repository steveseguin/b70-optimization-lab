#!/usr/bin/env python3
"""Verify packet70's own CPU-only wrapper seal; never writes frozen parents."""
from pathlib import Path
from common import ROOT,HERE,read,require,verify_map

def verify():
    row=read(HERE/'wrapper-seal.json')
    require(row['passed'] is True and row['device_executed'] is False,'wrapper gate missing')
    verify_map(ROOT,row['sources'])
    require({str(p.relative_to(ROOT)) for p in HERE.glob('*.py')} ==
            {name for name in row['sources'] if Path(name).parent == HERE.relative_to(ROOT)
             and Path(name).suffix == '.py'}, 'wrapper source inventory changed')
    return row

if __name__=='__main__':
    from conditions import cpu_gate
    cpu_gate();verify();print('PASS: packet70 screen wrapper seal')

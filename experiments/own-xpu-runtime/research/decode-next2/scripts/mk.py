#!/usr/bin/env python3
"""mk.py NAME BINARY [KEY=VAL ...]: launch json from the dnext F.json template (live env + OWNRT_DECODE_NEXT=1)."""
import json,sys
d=json.load(open('/dev/shm/ownrt-lab-dnext/launch/F.json'))
name,binary=sys.argv[1],sys.argv[2]
i=d['argv'].index('/dev/shm/engine-build-lab-dnext-fin/sc117-engine');d['argv'][i]=binary
assert d['environment'].get('OWNRT_DECODE_NEXT')=='1'
for kv in sys.argv[3:]:
    k,v=kv.split('=',1)
    if v=='':d['environment'].pop(k,None)
    else:d['environment'][k]=v
json.dump(d,open(f'/dev/shm/ownrt-lab-dn2/launch/{name}.json','w'),indent=1)

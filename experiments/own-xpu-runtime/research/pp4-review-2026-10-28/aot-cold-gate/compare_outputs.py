#!/usr/bin/env python3
"""Cross-binary exact full-output and guard comparison; no device operations."""
import hashlib,json,sys
from pathlib import Path
expected={f'scalar-width{w}.u32':w*10240*4 for w in (1,2,3)}
expected.update({f'candidate-width{w}-tile{t}.u32':(3*10240+64)*4 for w in (1,2,3) for t in (2,4)})
a,b=map(Path,sys.argv[1:3]);result={}
for p in (a,b):
 assert p.is_dir() and not p.is_symlink()
 assert {x.name for x in p.iterdir()}==set(expected),'exact nine output files required'
for name,n in expected.items():
 pa,pb=a/name,b/name
 assert pa.is_file() and pb.is_file() and not pa.is_symlink() and not pb.is_symlink()
 assert pa.stat().st_size==pb.stat().st_size==n,'exact output extent'
 x,y=pa.read_bytes(),pb.read_bytes();assert x==y,'cross-binary bit mismatch: '+name
 result[name]={'bytes':n,'sha256':hashlib.sha256(x).hexdigest()}
print(json.dumps({'passed':True,'files':result,'compared_bytes':sum(expected.values()),'scope':'Full scalar/candidate outputs plusguard/unusedrows exactcrossbinary; source/fixture/firstprocess timing identity verified separately'},indent=2))

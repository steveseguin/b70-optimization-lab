#!/usr/bin/env python3
"""Create 64 route-logit rows; no model or GPU execution."""
import hashlib
import json
import pathlib
import random
import struct
import sys

out=pathlib.Path(sys.argv[1]);out.mkdir()
native=pathlib.Path('/dev/shm/sc117-reference-prefix178-20261028-r1/router-lastrow-extract')
receipt=json.loads((native/'receipt.json').read_text())
assert receipt['full_sealed_source_hash_verified']
records={entry['name']:entry for entry in receipt['members']}
payload=bytearray();rows=[]
def add(name,data,**meta):
    assert len(data)==2048
    rows.append(dict(row=len(rows),label=name,sha256=hashlib.sha256(data).hexdigest(),**meta));payload.extend(data)
for layer in range(48):
    source=native/f'blk.{layer}.router.bin';data=source.read_bytes();record=records[source.name]
    assert len(data)==record['bytes'] and hashlib.sha256(data).hexdigest()==record['sha256']
    add(f'actual-native-layer-{layer:02d}',data,source=str(source))
rng=random.Random(0x117b70)
for kind in range(16):
    if kind==0: score=[0.0]*512
    elif kind==1: score=[i/64 for i in range(512)]
    elif kind==2: score=[(511-i)/64 for i in range(512)]
    elif kind==3:
        score=[-2.0]*512
        for i in range(9):score[i]=10+i
        score[62]=score[477]=9
    elif kind==4:
        score=[-float(i+1)/64 for i in range(512)];score[17]=score[391]=10
    elif kind==5:
        score=[-2.0]*512
        for i in range(9):score[i]=10+i
        score[9]=score[10]=9
    elif kind==6:score=[-3.0]*512
    elif kind==7:score=[i%7 for i in range(512)]
    elif kind==8:score=[(i//13)%5 for i in range(512)]
    elif kind==9:score=[((i+256 if i%2 else i+1) if i<256 else 2*(i-256)+2)/64 for i in range(512)]
    elif kind==10:score=[rng.randrange(128)/16 for _ in range(512)]
    elif kind==11:score=[rng.random() for _ in range(512)]
    elif kind==12:
        score=[-100.0]*512
        for i in range(10):score[i]=i
    elif kind==13:score=[5.0 if i>=480 else -i/64 for i in range(512)]
    elif kind==14:score=[10.0]+[0.0]*511
    else:
        score=[-3.0]*512
        for i in range(9):score[200+i]=10+i
        score[222]=score[223]=9
    add(f'synthetic-{kind}',struct.pack('<512f',*score),synthetic=True)
assert len(rows)==64 and len(payload)==131072
(out/'input.f32').write_bytes(payload)
manifest=dict(schema='ownrt.reference-route-input.v1',rows=64,width=512,bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest(),rows_detail=rows,source_receipt=str(native/'receipt.json'),source_receipt_sha256=hashlib.sha256((native/'receipt.json').read_bytes()).hexdigest(),gpu_executed=False)
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({k:v for k,v in manifest.items() if k!='rows_detail'}))

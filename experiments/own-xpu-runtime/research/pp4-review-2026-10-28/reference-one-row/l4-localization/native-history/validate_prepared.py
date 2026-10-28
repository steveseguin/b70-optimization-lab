"""Strict bounded prepared-history sidecar checks. No device or model access."""
from pathlib import Path
import struct
import validate as V
ROWS=244;SCRATCH=4192*4;ROW_BYTES=17164;TOTAL=ROWS*ROW_BYTES
READS={3:192,4:192,15:4,17:4,18:4,19:SCRATCH}
def verify(directory,attempts,controls_reference):
 root=Path(directory);attempts=Path(attempts);control=Path(controls_reference)
 assert root.is_dir() and not root.is_symlink()
 assert {p.name for p in root.iterdir()}=={'prepared.bin','rows.jsonl','seal.json'}
 files=[root/n for n in ('prepared.bin','rows.jsonl','seal.json')]+[attempts,control]
 before={p:V.stamp(p)for p in files};assert before[root/'prepared.bin'][2]==TOTAL
 assert before[root/'rows.jsonl'][2]<8*1024**2 and before[attempts][2]<8*1024**2 and before[control][2]==384
 data=(root/'prepared.bin').read_bytes();index=(root/'rows.jsonl').read_bytes();seal=V.load((root/'seal.json').read_bytes());expected=control.read_bytes()
 assert seal==dict(schema='ownrt.l4-prepared-history.v1',rows=ROWS,row_bytes=ROW_BYTES,payload_bytes=TOTAL,payload_sha256=V.sha(data),index_sha256=V.sha(index))
 rows=[V.load(x)for x in index.splitlines()];observed=[V.load(x)for x in attempts.read_bytes().splitlines()];assert len(rows)==len(observed)==ROWS
 for p,(row,attempt)in enumerate(zip(rows,observed)):
  assert row['position']==attempt['position']==p and row['offset']==p*ROW_BYTES
  piece=data[p*ROW_BYTES:(p+1)*ROW_BYTES];assert row['scratch_sha256']==V.sha(piece[:SCRATCH])
  parts=[piece[SCRATCH:SCRATCH+192],piece[SCRATCH+192:SCRATCH+384],piece[-12:-8],piece[-8:-4],piece[-4:]]
  assert row['controls_sha256']==[V.sha(x)for x in parts]
  assert b''.join(parts[:2])==expected,'actual bound a/dt differ from independently pinned GGUF controls'
  assert struct.unpack('<3i',piece[-12:])==(0,p,1)
  meta=row['invocation'];assert meta['site']==attempt['site'] and meta['implementation']==2 and meta['bank_parity']==p%2
  stages=meta['actual_stages'];calls=attempt['observed_calls'];commands=attempt['commands']
  assert len(stages)==len(calls)==len(commands)==2
  bindings=meta['bindings'];assert [b['slot']for b in bindings]==list(range(20))
  for j,(s,c,command)in enumerate(zip(stages,calls,commands)):
   assert s['stage']==c['stage']==(0 if j else 1) and s['prepared'] is c['prepared'] is True
   assert s['kernel']=='round2::Kernel<gdn,%d>'%s['stage'] and s['shape']==c['shape']==stages[0]['shape']
   assert len(s['shape'])==9 and s['shape'][1]==1 and s['shape'][5]==94 and s['shape'][6]==4096
   assert command['queue']==0 and command['ids']==[b['allocation']for b in bindings]
   assert command['pointers']==c['pointers']==[b['pointer']for b in bindings]
  for slot,n in READS.items():
   b=bindings[slot];assert b['read_slot'] is True and b['binding']=='bound' and b['live'] is True and b['memory_kind']==0
   assert b['allocation']>0 and b['pointer']==b['base']+b['offset'] and b['pointer']%4==0
   assert 0<=b['offset']<=b['allocation_bytes']-n
  assert bindings[3]['label']=='card0:weight:blk.4.ssm_a' and bindings[4]['label']=='card0:weight:blk.4.ssm_dt.bias'
 for p,s in before.items():assert V.stamp(p)==s
 return dict(rows=ROWS,payload_bytes=TOTAL,payload_sha256=seal['payload_sha256'],index_sha256=seal['index_sha256'],attempts_sha256=V.sha(attempts.read_bytes()),control_reference_sha256=V.sha(expected),scope='Actual prepared binding/shape/control sidecar only; require owner success and full final-source neutrality separately.')

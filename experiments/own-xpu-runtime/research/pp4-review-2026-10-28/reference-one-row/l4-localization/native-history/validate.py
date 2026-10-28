"""Bounded sealed L4 sidecar verification; no model/device access."""
from pathlib import Path
import hashlib,json,stat
ROWS=244;EXTENTS={'conv':40960,'alpha':192,'beta':192,'y':24576};ROW_BYTES=sum(EXTENTS.values());TOTAL=ROWS*ROW_BYTES
sha=lambda b:hashlib.sha256(b).hexdigest()
def pairs(items):
 d={}
 for k,v in items:
  if k in d:raise ValueError('duplicate JSON key')
  d[k]=v
 return d
def load(b):return json.loads(b,object_pairs_hook=pairs)
def stamp(p):
 s=p.stat(follow_symlinks=False);assert stat.S_ISREG(s.st_mode) and s.st_nlink==1
 return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
def verify(directory,tokens=None):
 root=Path(directory);assert not root.is_symlink() and root.is_dir()
 expected={'history.bin','rows.jsonl','initial.json','seal.json'};assert {p.name for p in root.iterdir()}==expected
 before={name:stamp(root/name) for name in expected};assert before['history.bin'][2]==TOTAL
 assert before['rows.jsonl'][2]<1024**2 and before['initial.json'][2]<4096 and before['seal.json'][2]<4096
 content={name:(root/name).read_bytes() for name in expected};seal=load(content['seal.json']);initial=load(content['initial.json'])
 assert seal['schema']=='ownrt.l4-raw-history.v1' and seal['rows']==ROWS and seal['row_bytes']==ROW_BYTES and seal['payload_bytes']==TOTAL
 assert seal['payload_sha256']==sha(content['history.bin']) and seal['index_sha256']==sha(content['rows.jsonl']) and seal['initial_sha256']==sha(content['initial.json'])
 assert initial['schema']=='ownrt.l4-raw-initial.v1' and initial['before_position']==0 and initial['positive_zero'] is True and initial['bank_parity'] in [0,1]
 for field,n in [('state',3145728),('history',122880)]:assert initial[field+'_bytes']==n and initial[field+'_sha256']==sha(bytes(n))
 rows=[load(line) for line in content['rows.jsonl'].splitlines()];assert len(rows)==ROWS
 if tokens is not None:assert len(tokens)==ROWS
 for p,row in enumerate(rows):
  assert row['position']==p and type(row['sequence']) is int and row['sequence']==0
  assert row['fixture']==(1 if p==ROWS-1 else 0) and row['bank_parity_before_swap']==(initial['bank_parity']^(p&1))
  assert type(row['token']) is int and row['token']>=0
  if tokens is not None:assert row['token']==tokens[p]
  assert list(row['fields'])==list(EXTENTS);offset=p*ROW_BYTES
  for field,n in EXTENTS.items():
   item=row['fields'][field];assert item['offset']==offset and item['bytes']==n
   assert item['sha256']==sha(content['history.bin'][offset:offset+n]);offset+=n
 for name,identity in before.items():assert stamp(root/name)==identity
 return dict(rows=ROWS,payload_bytes=TOTAL,payload_sha256=seal['payload_sha256'],index_sha256=seal['index_sha256'],initial_sha256=seal['initial_sha256'],initial_positive_zero=True,scope='Strict raw history only; owner clean exit and final full-source parity are separate gates.')

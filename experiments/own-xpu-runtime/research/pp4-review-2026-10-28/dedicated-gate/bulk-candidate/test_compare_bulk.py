"""Offline bulk-source and suffix checks; native fixture is CPU run_loop evidence only.

Run with OWNRT_COMPARE_OVERLAY=/path/to/helper/overlay and optional
OWNRT_BULK_PLANNING=/path/to/patched/engine/planning before canonical application.
"""
import copy
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
ENGINE=ROOT/'engine'
sys.path.insert(0,os.environ.get('OWNRT_BULK_PLANNING',str(ENGINE/'planning')))
sys.path.insert(0,str(HERE.parent))
import test_compare as OLD
from rolling_provider import dedicated_prefill as P
from rolling_provider.dedicated import DedicatedCoordinator
HELPERS=Path(os.environ.get('OWNRT_COMPARE_OVERLAY',str(HERE.parent)))
C=types.ModuleType('bulk_compare');C.__file__=str(HELPERS/'compare.py')
src=Path(C.__file__).read_text().replace("ENGINE=Path(__file__).resolve().parents[3]/'engine'",f"ENGINE=Path({str(ENGINE)!r})")
exec(compile(src,C.__file__,'exec'),C.__dict__)

class BulkProof(unittest.TestCase):
 def source(self,directory):
  f=json.loads((HERE/'native-wire-fixture/fixture.json').read_text());prompt=f['prompt_tokens']
  m=DedicatedCoordinator(stages=3,request=bytes(32),epoch=0,prompt=prompt,max_new=4,context=128,vocab=128,eos_token_ids=[127],stream_bytes=16,speculative_depth=3)
  native=[json.loads(s) for s in (HERE/'native-wire-fixture/provider-prefill-chunks.jsonl').read_text().splitlines()]
  pairs=[json.loads(s) for s in (HERE/'native-wire-fixture/provider-prefill-pairs.jsonl').read_text().splitlines()]
  journal=[]
  for n in native:
   start,count,sequence=n['start'],n['count'],n['sequence'];parity=(start//4)%2
   records=[]
   for role in (1,2):
    fields=(P.CHUNK_MAGIC,1,1280,sequence,role,0 if role==1 else 2,3,parity,start,count,4,16,15,sequence,prompt[start+count] if role==1 else 0xffffffff,0,0,bytes(32),bytes.fromhex(n['prompt_sha256']),m.proposals.hashes[start],m.proposals.hashes[start+count],bytes(32) if role==1 else bytes.fromhex(n['raw_sha256']),bytes(24))
    tokens=prompt[start:start+count]+[0]*(256-count) if role==1 else [0]*256
    records.append(P.RECORD.pack(*fields)+P.TOKENS.pack(*tokens))
   seed,final=records
   self.assertEqual(sha256(seed).hexdigest(),n['seed_record_sha256']);self.assertEqual(sha256(final).hexdigest(),n['final_record_sha256'])
   ack=P.ACK.pack(P.ACK_MAGIC,1,256,sequence,start,count,parity,4,16,3,sequence,sequence,start+count+1,1,0,0,0,start+count,bytes(32),bytes.fromhex(n['prompt_sha256']),sha256(seed).digest(),sha256(final).digest(),bytes.fromhex(n['raw_sha256']),bytes(16))
   journal.append(dict(event='authenticated-prefill-chunk',start=start,count=count,parity=parity,target_sequences=[sequence]*3,seed_record_hex=seed.hex(),final_record_hex=final.hex(),provider_command_hex=struct.pack('<8i',28,count,start,parity,0,sequence,0x50525631,1).hex(),provider_reply_hex=struct.pack('<8i4d',0,-1,0,256,sequence,-1,0x50525631,1,0.,0.,0.,0.).hex(),provider_ack_hex=ack.hex(),target_reply_hex=[struct.pack('<8i4d',0,-1,0,count*16,sequence,0 if stage==0 else 1,stage,int(stage==2),0.,0.,0.,0.).hex() for stage in range(3)]))
  self.assertEqual(bytes.fromhex(journal[-1]['provider_ack_hex']),(HERE/'native-wire-fixture/ack-3.bin').read_bytes())
  return m,journal,pairs,native
 def ingest(self,d,m,j,p,n):
  paths=[Path(d)/name for name in ('journal','pairs','chunks')]
  for path,rows in zip(paths,(j,p,n)):path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
  return P.prefix_evidence(*paths,m,rows=4)
 def test_native_source_and_ack(self):
  with tempfile.TemporaryDirectory() as d:
   m,j,p,n=self.source(d);self.assertEqual(self.ingest(d,m,j,p,n)['positions'],9)
 def test_bad_actual_ack_and_source(self):
  with tempfile.TemporaryDirectory() as d:
   m,j,p,n=self.source(d)
   for field in ('provider_ack_hex','seed_record_hex','final_record_hex'):
    bad=copy.deepcopy(j);raw=bytearray.fromhex(bad[-1][field]);raw[-1]^=1;bad[-1][field]=raw.hex()
    with self.subTest(field=field),self.assertRaises(ValueError):self.ingest(d,m,bad,p,n)
 def test_missing_duplicate_out_of_order_native_pairs(self):
  with tempfile.TemporaryDirectory() as d:
   m,j,p,n=self.source(d)
   for bad in (p[:-1],p+[p[-1]],[p[1],p[0]]+p[2:]):
    with self.assertRaises(ValueError):self.ingest(d,m,j,bad,n)
 def suffix(self):
  r=OLD.commands();issued,complete=r;issued['sequence']=complete['sequence']=2;row=issued['row'];row['position']=2
  issued['request_hex']=struct.pack('<8i',27,row['token'],2,row['fixture'],3,2,0x50525631,1).hex()
  p=complete['provider'];p.update(provider_serial=2,seed_position=2,restored_position=2)
  raw=bytearray.fromhex(p['proposal_hex']);struct.pack_into('<Q',raw,24,2);struct.pack_into('<Q',raw,56,2);struct.pack_into('<2i',raw,64,2,2)
  p.update(proposal_hex=raw.hex(),proposal_sha256=sha256(raw).hexdigest(),reply_hex=struct.pack('<8i4d',0,21,0,224,2,-1,0x50525631,1,0.,0.,0.,0.).hex());return r
 def prefix(self):return dict(positions=1,actual_native_chunks=[{}],actual_native_pairs=[dict(position=1,token=7,hidden_bytes=40960,hidden_sha256='12'*32)])
 def test_suffix_first_serial_and_sequence_offset(self):
  self.assertEqual([r['position'] for r in C.canonical_pairs(self.suffix(),3,prefix=self.prefix())],[1,2])
  for bad in ([],self.suffix()+self.suffix(),OLD.commands()):
   with self.assertRaises(ValueError):C.canonical_pairs(bad,3,prefix=self.prefix())
  bad=self.suffix();bad[1]['provider']['provider_serial']=1
  with self.assertRaises(ValueError):C.canonical_pairs(bad,3,prefix=self.prefix())
 def test_native_chunk_sequence_mismatch(self):
  with tempfile.TemporaryDirectory() as d:
   m,j,p,n=self.source(d);n[1]['sequence']+=1
   with self.assertRaises(ValueError):self.ingest(d,m,j,p,n)
 def test_default_unchanged(self):self.assertEqual(len(C.canonical_pairs(OLD.commands(),2)),1)

def load_tests(loader,tests,pattern):
 OLD.C=C;OLD.prepare.C=C
 tests.addTests(loader.loadTestsFromModule(OLD));return tests
if __name__=='__main__':unittest.main()

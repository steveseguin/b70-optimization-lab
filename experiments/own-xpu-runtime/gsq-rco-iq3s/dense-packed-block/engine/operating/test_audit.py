"""Tiny temporary evidence only; never calls the full audit or live coordinator."""
import gzip,hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('dense_packed_bundle_audit',P/'audit.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
def digest(b):return hashlib.sha256(b).hexdigest()
class AuditTests(unittest.TestCase):
 def bundle(self,root,data=b'abc'):
  root.mkdir();h=digest(data);state=json.dumps({'buffers':{'x':h}},separators=(',',':')).encode();index=f'GSQ_STATE_BUNDLE_V1\nx.bin\t0\t{len(data)}\t{h}\n'.encode()
  seal=f'GSQ_STATE_SEAL_V1\n{len(data)}\n{h}\n{digest(index)}\n{digest(state)}\n'.encode()
  for name,b in [('state.bundle',data),('state-index.tsv',index),('state.json',state),('state-seal.txt',seal)]:(root/name).write_bytes(b)
  return {'state.json':{'bytes':len(state),'sha256':digest(state)},'x.bin':{'bytes':len(data),'sha256':h}}
 def test_exact_range_and_physical_hash_single_pass(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'bundle';expected=self.bundle(path);result=A.U.stream_bundle(path,expected)
   self.assertEqual(result['logical_map'],{k:v['sha256'] for k,v in expected.items()});self.assertEqual(result['payload_bytes'],3);self.assertEqual(result['ranges'],1)
 def test_payload_corruption_refused(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'bundle';expected=self.bundle(path);(path/'state.bundle').write_bytes(b'bad')
   with self.assertRaisesRegex(ValueError,'range bytes'):A.U.stream_bundle(path,expected)
 def test_initial_semantics_not_assumed_but_bytes_verified(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'bundle';expected=self.bundle(path);expected['x.bin']['sha256']='0'*64;expected['state.json']['sha256']='0'*64
   result=A.U.stream_bundle(path,expected,semantic_oracle=False);self.assertEqual(set(result['baseline_hash_differences']),{'x.bin','state.json'})
   with self.assertRaisesRegex(ValueError,'baseline'):A.U.stream_bundle(path,expected,semantic_oracle=True)
 def test_all54_inventory_join_and_missing_refusal(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);index=root/'index.gz';bases=[root/f'group{i}' for i in range(27)]
   rows=[{'root':'evidence','path':f'group{i}/rank{r}/state-2147483647/state.json','bytes':1,'sha256':'0'*64} for i in range(27) for r in (0,1)]
   def save(rows):
    with gzip.open(index,'wt') as f:
     for row in rows:f.write(json.dumps(row)+'\n')
   save(rows)
   with patch.object(A,'EVIDENCE',root),patch.object(A,'OLD_INDEX',index),patch.object(A,'OLD_INDEX_SHA',A.sha(index)):self.assertEqual(len(A.expected_members(bases)),54)
   save(rows[:-1])
   with patch.object(A,'EVIDENCE',root),patch.object(A,'OLD_INDEX',index),patch.object(A,'OLD_INDEX_SHA',A.sha(index)),self.assertRaisesRegex(ValueError,'all54'):A.expected_members(bases)
 def test_pending_identity_and_unchanged_allocation_totals(self):
  self.assertIsNone(A.PLAN_SHA);self.assertIsNone(A.BINARY);self.assertIsNone(A.BUILD_SHA)
  self.assertEqual(A.CAND.name,'engine');self.assertEqual(A.CAND.parent.name,'dense-packed-block')
  self.assertEqual(A.L.name,'gsq-rco-iq3s')
  ledger=json.loads((P/'candidate-ledger.json').read_text())['scenarios']['split24-24_mtp-rank0']['ranks']
  self.assertEqual([r['device_logical_bytes'] for r in ledger],[30994676618,29966053268])
  with self.assertRaisesRegex(ValueError,'fixed admitted plan'):A.run('0'*64)
 def test_missing_physical_contact_cannot_pass(self):
  terminal=dict(passed=True,first_error=None,original_error=None,children_exited=True,target_descriptors_empty=True,observed_target_contact=[True,False])
  with self.assertRaisesRegex(ValueError,'owner/contact'):A.B.validate_passive({}, {},terminal)
if __name__=='__main__':unittest.main(verbosity=2)

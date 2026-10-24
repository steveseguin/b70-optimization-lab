import hashlib,importlib.util,json,pathlib,struct,tempfile,unittest
P=pathlib.Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('f32_b_audit_tests',P/'audit.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
class Tests(unittest.TestCase):
 def test_exact_new_geometry(self):
  for name,old,new in [('blk.0.gdn.state.bin',1572864,3145728),('alternate-blk.0.gdn.history.bin',61440,122880),('blk.1.ple.history.bin',184320,368640),('blk.3.qsa.keys.bin',512,512)]:self.assertEqual(A.corrected_extent(name,old),new)
  with self.assertRaises(AssertionError):A.corrected_extent('blk.0.gdn.state.bin',16)
 def test_new_bytes_not_old_hash(self):
  h=lambda x:hashlib.sha256(x).hexdigest()
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp);name='blk.0.gdn.state.bin';data=struct.pack('<4I',0x3f800001,0x80000000,0x3f800000,0x3eaaaaab);state=json.dumps({'buffers':{'blk.0.gdn.state':h(data)}}).encode();index=f'GSQ_STATE_BUNDLE_V1\n{name}\t0\t16\t{h(data)}\n'.encode();seal=f'GSQ_STATE_SEAL_V1\n16\n{h(data)}\n{h(index)}\n{h(state)}\n'.encode()
   for n,v in [('state.bundle',data),('state-index.tsv',index),('state.json',state),('state-seal.txt',seal)]: (p/n).write_bytes(v)
   expected={name:{'bytes':16,'sha256':'0'*64},'state.json':{'bytes':len(state),'sha256':'0'*64}}
   out=A.S.stream_bundle(p,expected,semantic_oracle=False);self.assertEqual(out['logical_map'][name],h(data));self.assertEqual(out['recurrent_precision'][name],{'words':4,'non_bf16_words':2})
   (p/'state.bundle').write_bytes(bytes(16))
   with self.assertRaises(AssertionError):A.S.stream_bundle(p,expected,semantic_oracle=False)
 def test_closed_budget(self):
  v=dict(stage=5,acknowledged=['initial_reset','target_dump','second_reset','mtp_dump','finish'],remaining_payload_bytes=0,metadata_reserve_bytes=128<<20,external_floor_bytes=2<<30);A.budget_ok(v)
  with self.assertRaises(AssertionError):A.budget_ok(dict(v,stage=4))
 def test_raw_enriched_join(self):
  raw={'name':'x','result':{'tokens':[1]}};A.raw_join(raw,dict(raw,reference_comparison={'equal':False}))
  with self.assertRaises(AssertionError):A.raw_join({'name':'y'},dict(raw,reference_comparison={}))
if __name__=='__main__':unittest.main()

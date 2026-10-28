import hashlib,importlib.util,json,subprocess,tarfile,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
spec=importlib.util.spec_from_file_location('gpu_route_candidate',Path(__file__).with_name('run.py'));M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
class Tests(unittest.TestCase):
 def test_frozen_complete_inputs(self):self.assertEqual(len(M.suite()),12);self.assertEqual(len(M.H.cases()),7)
 def test_no_registration_no_planning(self):
  with self.assertRaises((KeyError,FileNotFoundError)):M.registration({})
 def test_generation_natural_eos_and_missing_timing_irrelevant(self):
  r={'tokens':[17,248044],'stats':{'guesses':0},'rank_trace':[dict(rank=k,op=1,position=p,speculative=False)for k in (0,1)for p in range(4)]};M.validate_generation(r,[1,2,3],[248044,248046])
  r['tokens']=[17,18]
  with self.assertRaises(Exception):M.validate_generation(r,[1,2,3],[248044,248046])
 def test_generation_early_eos_and_missing_position_rejected(self):
  r={'tokens':[248044,17],'stats':{'guesses':0},'rank_trace':[]}
  with self.assertRaises(Exception):M.validate_generation(r,[1],[248044,248046])
  r['tokens']=[248044]
  with self.assertRaises(Exception):M.validate_generation(r,[1],[248044,248046])
 def cold_fixture(self,root):
  state={};baseline={}
  for k in ('0','1'):
   for name in ['first','repeat']:
    d=root/name/k;d.mkdir(parents=True);(d/'state.bundle').write_bytes(b'cold state')
   for obj,name in [(state,'repeat'),(baseline,'first')]:obj[k]={'path':str(root/name/k),'sources':{'x':'hash'},'bundle_sha256':sha(root/name/k/'state.bundle')}
  return dict(state=state,compared_to_first_actual_cold=True,actual_canonical_bytes_compared={'0':10,'1':10}),dict(state=baseline)
 def test_cold_delete_only_proven_duplicates_initial_retained(self):
  with tempfile.TemporaryDirectory()as tmp:
   a,b=self.cold_fixture(Path(tmp));r=M.drop_duplicate_cold(a,b);self.assertTrue(r['removed_files_absent']);self.assertTrue(all((Path(x['path'])/'state.bundle').exists()for x in b['state'].values()))
 def test_cold_bad_sources_refused_before_any_unlink(self):
  with tempfile.TemporaryDirectory()as tmp:
   a,b=self.cold_fixture(Path(tmp));a['state']['1']['sources']={'other':'bad'}
   with self.assertRaises(Exception):M.drop_duplicate_cold(a,b)
   self.assertTrue(all((Path(x['path'])/'state.bundle').exists()for x in a['state'].values()))
 def test_native_call_has_only_actual_prompt_cap_and_eos(self):
  with tempfile.TemporaryDirectory()as tmp:
   transport=SimpleNamespace(seq=[10,20],pending=[False,False],request_output=Path(tmp));observed=[]
   class Controller:
    def __init__(self,t,draft,overlap,dumps,**kw):self.t=t;self.assertions=(draft,overlap,dumps,kw)
    def run(self,prompt,count,eos):observed.append((prompt,count,eos,self.assertions));self.t.seq=[x+1 for x in self.t.seq];return {'tokens':[248044]}
   adapter=SimpleNamespace(NativeController=Controller,BASE=SimpleNamespace(Draft=lambda mode:mode));M.run_native(adapter,transport,[4,5],512,[248044]);self.assertEqual(observed,[([4,5],512,[248044],('none',False,False,{'prefill':0,'start':0}))])
 def archive_fixture(self,root):
  members=[];records=[];references=[]
  for i in range(7):
   a={'id':str(i),'actual_output_ids':[i],'layer_captures':[{'path':'layer-00.bf16','sha256':'layer'}],'full_state':{}};b=dict(a,full_state={})
   for rank in ('0','1'):
    c=root/f'candidate/{i}/{rank}';ref=root/f'reference/{i}/{rank}';c.mkdir(parents=True);ref.mkdir(parents=True);payload=bytes([i,int(rank)])*19;(c/'state.bundle').write_bytes(payload);(ref/'state.bundle').write_bytes(payload);h=sha(c/'state.bundle')
    a['full_state'][rank]={'path':str(c),'sources':{'x':h},'bundle_sha256':h};b['full_state'][rank]={'path':str(ref),'sources':{'x':h},'bundle_sha256':h};members.append({'path':str(ref/'state.bundle'),'member':f'{i}/{rank}/state.bundle','bytes':len(payload),'sha256':h})
   records.append(a);references.append(b)
  tar=root/'states.tar'
  with tarfile.open(tar,'w')as t:
   for row in members:t.add(row['path'],arcname=row['member'])
  archive=root/'states.tar.zst';subprocess.run(['zstd','-q','-o',str(archive),str(tar)],check=True);return records,{'records':references},{'archive':str(archive),'members':members}
 def test_one_archive_stream_actual_all_fourteen_payloads(self):
  with tempfile.TemporaryDirectory()as tmp:
   a,b,c=self.archive_fixture(Path(tmp));r=M.compare_archive(a,b,c);self.assertEqual(len(r['members']),14);self.assertEqual(r['bytes_compared'],14*38)
 def test_archive_source_map_and_actual_payload_corruption_rejected(self):
  with tempfile.TemporaryDirectory()as tmp:
   a,b,c=self.archive_fixture(Path(tmp));a[0]['full_state']['0']['sources']={'x':'bad'}
   with self.assertRaises(Exception):M.compare_archive(a,b,c)
   a[0]['full_state']['0']['sources']=b['records'][0]['full_state']['0']['sources'];(Path(a[0]['full_state']['0']['path'])/'state.bundle').write_bytes(b'x'*38)
   with self.assertRaises(Exception):M.compare_archive(a,b,c)
if __name__=='__main__':unittest.main()

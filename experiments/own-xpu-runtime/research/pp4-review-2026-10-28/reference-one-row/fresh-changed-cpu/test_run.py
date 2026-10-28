import importlib.util,json,os,subprocess,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location('changed',HERE/'run.py');R=importlib.util.module_from_spec(s);s.loader.exec_module(R)
class Tests(unittest.TestCase):
 def test_actual_wrapper_two_fresh_contexts_and_reuse_mutations(self):
  with tempfile.TemporaryDirectory()as d:
   root=Path(d);out=root/'out';out.mkdir();paths=[]
   for i in range(2):
    f=root/f'{i}.json';R.save(f,dict(tokens=[i,i+1,i+2],score_from=1,full_rows=[]));paths.append(f)
   listing=root/'list';listing.write_text(''.join(str(p)+'\n'for p in paths))
   rc=subprocess.run(['/dev/shm/sc117-reference-changed-fixture-20261028-r1','mock-model',str(listing),str(out),'8'],env=dict(os.environ,EXACT_KV='f32'),capture_output=True,text=True);self.assertEqual(rc.returncode,0,rc.stderr)
   self.assertEqual(json.loads((out/'lifecycle.json').read_text()),dict(loaded_models=1,completed_fresh_contexts=2,returncode=0))
   actual=root/'actual.json';actual.write_bytes(paths[0].read_bytes());c=dict(input=str(actual),score_from=1,generated_tokens=2);rows=out/'case-00/rows.jsonl'
   proof=R.reuse_proof(c,paths[0],rows);self.assertIsNotNone(proof);self.assertEqual(proof['comparison']['matches'],2)
   original=json.loads(actual.read_text())
   for position in range(3):
    changed=json.loads(json.dumps(original));changed['tokens'][position]+=1;R.save(actual,changed);self.assertIsNone(R.reuse_proof(c,paths[0],rows))
   changed=dict(original,score_from=2);R.save(actual,changed);self.assertIsNone(R.reuse_proof(c,paths[0],rows))
   R.save(actual,original);lines=rows.read_text().splitlines();rows.write_text('\n'.join(lines[:-1])+'\n');self.assertRaises(ValueError,R.reuse_proof,c,paths[0],rows)
 def test_only_outer_count_changed(self):
  original=(HERE.parent/'fresh-twelve-cpu/exact-logits-twelve.cpp').read_text();expected=original.replace('TWELVE_INPUT_PATHS','TWO_CHANGED_INPUT_PATHS').replace('inputs.size()!=12','inputs.size()!=2');self.assertEqual((HERE/'exact-logits-changed.cpp').read_text(),expected)
 def test_actual_mixed_authority_counts_and_mapping(self):
  a=json.loads(Path('/dev/shm/sc117-reference-changed-inputs-20261028-r2/inputs.json').read_text());fresh=[c for c in a['cases']if c['reference_kind']=='fresh-changed-input'];reused=[c for c in a['cases']if c['reference_kind']=='reused-identical-historical']
  self.assertEqual([(c['index'],c['id'],c['cpu_context_index'])for c in fresh],[(2,'bug-report-synthesis',0),(11,'technical-guide',1)])
  self.assertEqual(sum(c['generated_tokens']for c in fresh),1024);self.assertEqual(sum(c['generated_tokens']for c in reused),4941);self.assertEqual(sum(c['historical_reuse']['comparison']['matches']for c in reused),4941)
if __name__=='__main__':unittest.main()

import importlib.util,json,os,subprocess,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('teacher',HERE/'run.py');R=importlib.util.module_from_spec(s);s.loader.exec_module(R)
class Tests(unittest.TestCase):
 def test_original_scoring_body_unchanged(self):
  original=(R.ROOT/'gsq-rco-iq3s/service-speed/e-reference/exact-logits.cpp').read_text();body=original[original.index('    auto cp = llama_context_default_params();'):original.index('    return 0;\n}')].replace('fclose(rows); llama_batch_free(batch); llama_free(ctx); llama_model_free(model); llama_backend_free();','fclose(rows); llama_batch_free(batch); llama_free(ctx);')
  self.assertIn(body,(HERE/'exact-logits-twelve.cpp').read_text())
 def test_fresh_lifecycle_and_rows(self):
  with tempfile.TemporaryDirectory()as d:
   root=Path(d);out=root/'out';out.mkdir();paths=[]
   for i in range(12):
    f=root/f'{i}.json';R.save(f,dict(tokens=[i,i+1,i+2],score_from=1,full_rows=[]));paths.append(str(f))
   listing=root/'inputs';listing.write_text(''.join(p+'\n'for p in paths))
   result=subprocess.run(['/dev/shm/sc117-reference-twelve-fixture-20261028-r1','mock-model',str(listing),str(out),'8'],env=dict(os.environ,EXACT_KV='f32'),capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads((out/'lifecycle.json').read_text()),dict(loaded_models=1,completed_fresh_contexts=12,returncode=0))
   for i,p in enumerate(paths):
    c=dict(input=p,score_from=1,generated_tokens=2);proof=R.validate_rows(out/f'case-{i:02d}/rows.jsonl',c);self.assertEqual(proof['matches'],2);self.assertFalse(proof['mismatches'])
   rowfile=out/'case-00/rows.jsonl';rows=[json.loads(x)for x in rowfile.read_text().splitlines()];rows[0]['argmax']=31;rows[0]['top'][0][0]=31;rowfile.write_text(''.join(json.dumps(r)+'\n'for r in rows));self.assertEqual(len(R.validate_rows(rowfile,dict(input=paths[0],score_from=1,generated_tokens=2))['mismatches']),1)
   rows.pop(1);rowfile.write_text(''.join(json.dumps(r)+'\n'for r in rows));self.assertRaises(ValueError,R.validate_rows,rowfile,dict(input=paths[0],score_from=1,generated_tokens=2))
 def test_no_model_for_bad_manifest(self):
  with tempfile.TemporaryDirectory()as d:
   root=Path(d);out=root/'out';out.mkdir();listing=root/'inputs';listing.write_text('/absolute/repeated\n'*12)
   result=subprocess.run(['/dev/shm/sc117-reference-twelve-fixture-20261028-r1','mock-model',str(listing),str(out),'8'],capture_output=True,text=True)
   self.assertEqual(result.returncode,2);self.assertFalse((out/'lifecycle.json').exists());self.assertFalse(list(out.iterdir()))
if __name__=='__main__':unittest.main()

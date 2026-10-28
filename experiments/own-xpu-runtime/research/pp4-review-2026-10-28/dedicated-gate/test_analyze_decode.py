"""Small synthetic artifact schemas; never inference/performance evidence."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from analyze_decode import analyze

class AnalyzeTests(unittest.TestCase):
    def artifacts(self,tmp):
        d=Path(tmp)/'dedicated';p=Path(tmp)/'pp4';d.mkdir();p.mkdir()
        outputs=list(range(100));prompt=[2,3];frontier=101
        stage=dict(argv=['--gsq-packed','--draft-experts','fp8','--draft-model','/model'],environment={'FilterBdfPath':'a','SYCL_CACHE_DIR':'/fresh/a','MATH_FLAG':'1'})
        plan=dict(stages=[stage,deepcopy(stage)],provider=deepcopy(stage),prompt_tokens=prompt,context=262144,
            max_new=512,vocab=2000,eos_token_ids=[99],speculative_depth=3,check_policy='measured',
            model_identity_sha256='model',draft_model_sha256='draft',activation_dtype='F32',pins={'/build/sc117-engine':'binary'})
        result=dict(output_ids=outputs,input_position=frontier,provider_pairs=100,provider_serial=100,cancelled=False)
        dedicated=dict(result,schema='ownrt.dedicated-provider-driver-result.v1',passed=True,live_pids=[],
            returncodes={'0':0,'1':0,'provider':0},emitted_elapsed_seconds=[1+i*.1 for i in range(100)],scheduler_wall_seconds=12)
        pp=dict(schema='ownrt.persistent-rolling-request-result.v1',passed=True,output_ids=outputs,
            cached_tokens=0,prompt_state_reused=False,request_started_monotonic_s=200,request_finished_monotonic_s=212)
        save=lambda root,name,data:(root/name).write_text(json.dumps(data))
        save(d,'plan.json',plan);save(p,'request-plan.json',plan);save(d,'driver-result.json',dedicated)
        save(p,'driver-result.json',result);save(p,'result.json',pp)
        save(p.parent,'result.json',dict(passed=True,live_pids=[],returncodes={'0':0,'1':0}))
        (d/'commands.jsonl').write_text(json.dumps(dict(event='issued',stage=0,op=24,row={'position':0}))+'\n')
        for root,start in ((d,100),(p,200)):
            (root/'tokens.jsonl').write_text(''.join(json.dumps(dict(index=i,token=t,committed_monotonic_s=start+1+i*.1))+'\n' for i,t in enumerate(outputs)))
        return d,p
    def test_exact_first100_99_intervals(self):
        with TemporaryDirectory() as tmp:
            d,p=self.artifacts(tmp);r=analyze(d,p)
            self.assertEqual(r['timing']['dedicated']['first100']['intervals'],99)
            self.assertAlmostEqual(r['timing']['dedicated']['first100']['tokens_per_second'],10)
            self.assertEqual(r['output_cap'],512);self.assertTrue(r['ended_on_eos'])
    def test_missing_actual_commit_timing_rejected(self):
        with TemporaryDirectory() as tmp:
            d,p=self.artifacts(tmp);rows=[json.loads(l) for l in (p/'tokens.jsonl').read_text().splitlines()]
            rows[0].pop('committed_monotonic_s');(p/'tokens.jsonl').write_text('\n'.join(map(json.dumps,rows)))
            with self.assertRaisesRegex(ValueError,'actual commit timestamps'):analyze(d,p)
    def test_output_mismatch_rejected(self):
        with TemporaryDirectory() as tmp:
            d,p=self.artifacts(tmp);r=json.loads((p/'result.json').read_text());r['output_ids'][0]=123
            (p/'result.json').write_text(json.dumps(r))
            with self.assertRaisesRegex(ValueError,'exact output IDs'):analyze(d,p)
if __name__=='__main__':unittest.main()

"""Focused integrity tests using small synthetic receipts, without model calls."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SPEC=importlib.util.spec_from_file_location('collector',Path(__file__).with_name('collect_results.py'))
C=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(C)


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.raw=self.root/'raw';self.raw.mkdir();self.out=self.root/'packet'
        (self.raw/'server').mkdir();self.write('server/state.json',{'status':'ready'})
        for name in (*C.RUNS,C.INVALID,C.MODEL_LIMIT):self.run_fixture(name,name in C.RUNS)

    def write(self,name,value):
        path=self.raw/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(C.encoded(value))

    def run_fixture(self,name,passed):
        directory=self.raw/name;directory.mkdir()
        call={'directory':'001','status':'completed','prompt_tokens':512,'completion_tokens':2,
              'http_ttft_s':0.3,'server_prefill_s':0.2,'server_prefill_tokens_s':2560,
              'decode_stream_proxy_tokens_s':50,'elapsed_s':0.4}
        response={'text':'ok','text_sha256':C.sha(b'ok'),'prompt_tokens':512,'completion_tokens':2,
                  'cached_tokens':0,'usage':{'prompt_tokens_details':{'cached_tokens':0}},
                  'token_ids_available':True,'token_ids':[1,2],
                  'http_ttft_s':0.3,'server_prefill_s':0.2,'server_prefill_tokens_per_s':2560,
                  'decode_stream_proxy_tokens_s':50,'elapsed_s':0.4,
                  'raw_delta':{'vllm:prompt_tokens_total':512,'vllm:request_prefill_time_seconds_count':1,
                               'vllm:request_prefill_time_seconds_sum':0.2}}
        self.write(name+'/requests/001/attempt.json',call);self.write(name+'/requests/001/response.json',response)
        self.write(name+'/requests/001/token-count.json',{'input_tokens':512})
        stream='data: '+json.dumps({'choices':[{'token_ids':[1,2],'delta':{'content':'ok'}}]})+'\n\ndata: [DONE]\n\n'
        (directory/'requests/001/response.sse').write_text(stream)
        self.write(name+'/task.json',{'expected_baseline_failure':True,'expected_baseline_error':'known bug'})
        self.write(name+'/baseline-validation.json',{'returncode':1,'output':'known bug observed'})
        self.write(name+'/sandbox.json',{'stopped':True})
        patch={'patch_sha256':C.sha(b'fixture patch'),'changed_files':[{'path':'answer.py'}],'source_repo_unchanged':True,'baseline_unchanged':True}
        self.write(name+'/changes.json',patch);(directory/'changes.patch').write_bytes(b'fixture patch')
        result={'task_id':name,'status':'tests-passed-awaiting-review' if passed else 'incomplete',
                'model_requests':1,'requests':[call],'elapsed_seconds':1,'source_commit':'a'*40,
                'acceptance_passed':passed,'agent_result':{'exit_status':'Submitted' if passed else 'LimitsExceeded'},
                'patch':patch,'human_review':'pending','acceptance_tree_sha256':'b'*64 if passed else None,
                'final_workspace_tree_sha256':'b'*64 if passed else None,'final_workspace_matches_acceptance':passed}
        self.write(name+'/result.json',result)
        if passed:self.write(name+'/validation-1.json',{'accepted':True,'returncode':0,'workspace_stable':True,'workspace_after_sha256':'b'*64})
        (directory/'workspace').mkdir();(directory/'workspace/large-secret').write_text('excluded')
        (directory/'source.tar').write_bytes(b'not compact')
        (directory/'symlink').symlink_to('/etc/passwd')
        self.write(name+'/snapshot.json',{'source_commit':'a'*40})
        (directory/'independent-review.md').write_text('Independent review remains separate from human approval.\n')

    def test_roundtrip_exclusions_and_separate_attempts(self):
        receipt=C.collect(self.raw,self.out)
        self.assertTrue(receipt['verified']);self.assertEqual(receipt['accepted_tasks'],5)
        manifest=json.loads((self.out/'manifest.json').read_text())
        self.assertFalse(any('/workspace/' in name or name.endswith('/source.tar') or name.endswith('/symlink') for name in manifest['members']))
        summary=json.loads((self.out/'summary.json').read_text())
        self.assertEqual(summary['requests_total'],5)
        self.assertEqual(summary['metrics']['server_prefill_tokens_s']['median'],2560)
        self.assertTrue((self.out/'invalid-attempt-summary.json').exists())
        self.assertIn('not an infrastructure failure',(self.out/'model-limit-attempt-summary.json').read_text())
        self.assertEqual((self.out/'patches'/f'{C.RUNS[0]}.patch').read_bytes(),b'fixture patch')
        self.assertEqual((self.out/'reviews'/f'{C.RUNS[0]}.md').read_bytes(),(self.raw/C.RUNS[0]/'independent-review.md').read_bytes())

    def test_missing_run_refuses_before_creating_output(self):
        (self.raw/C.RUNS[-1]/'result.json').unlink()
        with self.assertRaises(C.IntegrityError):C.collect(self.raw,self.out)
        self.assertFalse(self.out.exists())

    def test_summary_tampering_rejected(self):
        C.collect(self.raw,self.out)
        path=self.out/'summary.json';summary=json.loads(path.read_text());summary['requests_total']=999;path.write_bytes(C.encoded(summary))
        with self.assertRaisesRegex(C.IntegrityError,'summary differs'):C.verify(self.out)

    def test_archive_tampering_rejected(self):
        C.collect(self.raw,self.out)
        with (self.out/'evidence.tar.gz').open('ab') as file:file.write(b'changed')
        with self.assertRaisesRegex(C.IntegrityError,'archive SHA'):C.verify(self.out)

    def test_response_metric_mismatch_rejected(self):
        path=self.raw/C.RUNS[0]/'requests/001/response.json';row=json.loads(path.read_text());row['server_prefill_tokens_per_s']=999
        path.write_bytes(C.encoded(row))
        with self.assertRaisesRegex(C.IntegrityError,'metric differs'):C.collect(self.raw,self.out)

    def test_claimed_acceptance_without_tree_receipt_rejected(self):
        path=self.raw/C.RUNS[0]/'validation-1.json';row=json.loads(path.read_text());row['workspace_after_sha256']='wrong'
        path.write_bytes(C.encoded(row))
        with self.assertRaisesRegex(C.IntegrityError,'claimed acceptance'):C.collect(self.raw,self.out)

    def test_wrong_baseline_failure_is_not_supported(self):
        self.write(C.RUNS[0]+'/baseline-validation.json',{'returncode':1,'output':'unrelated import error'})
        with self.assertRaisesRegex(C.IntegrityError,'claimed acceptance'):C.collect(self.raw,self.out)

    def test_running_sandbox_cannot_support_acceptance(self):
        self.write(C.RUNS[0]+'/sandbox.json',{'stopped':False})
        with self.assertRaisesRegex(C.IntegrityError,'claimed acceptance'):C.collect(self.raw,self.out)

    def test_changed_baseline_cannot_support_acceptance(self):
        name=C.RUNS[0];path=self.raw/name/'result.json';result=json.loads(path.read_text());result['patch']['baseline_unchanged']=False
        self.write(name+'/result.json',result);self.write(name+'/changes.json',result['patch'])
        with self.assertRaisesRegex(C.IntegrityError,'claimed acceptance'):C.collect(self.raw,self.out)

    def test_cached_response_rejected(self):
        path=self.raw/C.RUNS[0]/'requests/001/response.json';response=json.loads(path.read_text());response['cached_tokens']=1
        path.write_bytes(C.encoded(response))
        with self.assertRaisesRegex(C.IntegrityError,'cache-zero'):C.collect(self.raw,self.out)

    def test_prompt_token_count_mismatch_rejected(self):
        self.write(C.RUNS[0]+'/requests/001/token-count.json',{'input_tokens':513})
        with self.assertRaisesRegex(C.IntegrityError,'prompt length'):C.collect(self.raw,self.out)

    def test_full_output_tokens_must_match_raw_stream(self):
        path=self.raw/C.RUNS[0]/'requests/001/response.sse';path.write_text(path.read_text().replace('[1, 2]','[1, 3]'))
        with self.assertRaisesRegex(C.IntegrityError,'full output differs'):C.collect(self.raw,self.out)

    def test_public_patch_tampering_rejected(self):
        C.collect(self.raw,self.out)
        (self.out/'patches'/f'{C.RUNS[0]}.patch').write_text('changed')
        with self.assertRaisesRegex(C.IntegrityError,'public file differs'):C.verify(self.out)


if __name__=='__main__':unittest.main()

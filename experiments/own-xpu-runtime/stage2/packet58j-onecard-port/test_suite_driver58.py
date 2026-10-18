import copy
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
import suite_driver as D
import packet58_submission as S

class SuiteTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.actual=self.root/'actual';self.actual.mkdir()
        self.oracle=self.root/'oracle';self.oracle.mkdir();self.bundle=self.root/'bundle';self.bundle.mkdir()
        (self.bundle/'input.json').write_text(json.dumps({'tokens':[1,2,3]}))
        self.entry={'prompt_id':'code-review','prompt_tokens':3,'input_bundle':'bundle'}
        self.record=dict(schema='own-runtime.iq3.packet26.run.v1',passed=True,arithmetic=D.ARITHMETIC,
            tokens=list(range(128)),cached_tokens=0,gpu_count=1,decode_mode='plain',context=4096,
            requested_max_new=128,prompt_tokens=3,request_start_monotonic=10.,request_end_monotonic=13.,
            timing_rows=[{'completed_monotonic':11.+i*.01} for i in range(128)])
        D.save(self.actual/'result.json',self.record)
        D.save(self.actual/'reset.json',dict(passed=True,cached_tokens=0,allocation_ids_preserved=True))
        D.save(self.oracle/'receipt.json',dict(schema='own-runtime.iq3.packet26.run.v1',passed=True,
            arithmetic=D.ARITHMETIC,tokens=list(range(128))))
    def compare(self):
        with patch.object(D,'ROOT',self.root):return D.compare_request(self.actual,self.oracle,self.entry,128,'none')
    def test_exact_metric_and_reset(self):
        row=self.compare();self.assertAlmostEqual(row['tok_s_1_100_intervals_after_ttft'],100.)
        self.assertEqual(row['submission100']['numerator'],99)
        self.assertTrue(row['metric_window_eligible']);self.assertEqual(row['ttft_ms'],1000.)
    def test_changed_token_rejected(self):
        self.record['tokens'][98]=99;D.save(self.actual/'result.json',self.record)
        with self.assertRaisesRegex(ValueError,'token identity'):self.compare()
    def test_duplicate_timestamp_rejected(self):
        self.record['timing_rows'][50]=self.record['timing_rows'][49];D.save(self.actual/'result.json',self.record)
        with self.assertRaisesRegex(ValueError,'timestamps'):self.compare()
    def test_wrong_gpu_or_reuse_rejected(self):
        for key,value in [('gpu_count',2),('decode_mode','mtp'),('cached_tokens',1)]:
            changed=copy.deepcopy(self.record);changed[key]=value;D.save(self.actual/'result.json',changed)
            with self.assertRaisesRegex(ValueError,'identity'):self.compare()
    def test_reset_required(self):
        (self.actual/'reset.json').unlink()
        with self.assertRaises(FileNotFoundError):self.compare()
    def test_no_onecard_threshold_inherits_tp2(self):
        row=S.threshold();self.assertEqual(row['gpu_count'],1);self.assertEqual(row['threshold_tok_s'],24.338653323339745)
    def test_payload_onecard_plain_scope(self):
        row=self.compare()
        result=dict(requests=[row]*12,primary_metric=dict(name=D.METRICS.PRIMARY,value_tok_s=100),
            secondary=dict(wall_rate_statistics=dict(median=50),ttft_statistics=dict(median=1000)),
            promotionIdentity=dict(runtime_revision='1234567'),card=0)
        ref=dict(path='fixture',sha256='a'*64)
        with self.assertRaisesRegex(ValueError,'second whole-host timing'):
            S.payload(result,ref,ref)
        result['fresh_timing_repeat_passed']=True  # hypothetical separately qualified repeat
        item=S.payload(result,ref,ref);payload=item['payload'];flags=payload['engineFlags']
        self.assertEqual(payload['hardware']['gpuCount'],1);self.assertFalse(flags['mtpEnabled'])
        self.assertFalse(flags['realisticSuiteGatePassed']);self.assertEqual(flags['metricWindowIntervals'],99)
        self.assertNotIn('targetSplit',flags);self.assertNotIn('draftRank',flags)
    def test_missing_evidence_refuses_before_output(self):
        with patch('window.build_gate',side_effect=ValueError('missing seal')):
            out=self.root/'out'
            with self.assertRaisesRegex(ValueError,'missing seal'):S.prepare(self.root,out)
            self.assertFalse(out.exists())
    def test_native_mask_and_modes(self):
        bundle={'prompt_id':'incident-retrospective','input_bundle':'bundle'}
        D.save(self.bundle/'input.json',{'model_dir':'/mnt/usb-models/llm-models/unsloth-Qwen3.8-Flash-Next-GGUF-766911a6/UD-IQ3_XXS'})
        args=types.SimpleNamespace(window='WS128',output=self.root,miss_mode='zerocopy')
        with patch.object(D,'ROOT',self.root),patch.object(D,'sha',return_value='a'*64):
            cmd=D.native_command(args,{'prompts':[bundle]},self.root/'table')
        self.assertEqual(cmd[cmd.index('--card')+1],'0')
        self.assertEqual(cmd[cmd.index('--miss-path')+1],'zero-copy')
        self.assertEqual(cmd[cmd.index('--retain-steps')+1],'none')

if __name__=='__main__':unittest.main()

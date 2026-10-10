import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import jsonschema
import torch

from common import file_hash, json_bytes, load_tensor
from compare_fixtures import compare, difference
from extract_fixtures import Recorder, refuse_capture, schema, validate_native_identity, forbid_graph_entrypoints, normalize_oracle
from mock_comparator import EAGER, mock_identity, run_mock


class RoundTrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='packet4-cpu-')
        cls.root = Path(cls.tmp.name)
        for model in ('27b', 'flash-next'):
            run_mock(cls.root/model, model, chunk_bytes=65536)
    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_27b_exact_all_recorded(self):
        r = compare(self.root/'27b')
        self.assertTrue(r['all_recorded_exact'])
        self.assertEqual(len(r['operators']), 33)
        self.assertTrue(all(u['status']=='VERIFIED-EXACT' for u in r['census'].values()))
        self.assertTrue(all(u['qualification']=='UNTESTED' for u in r['census'].values()))

    def test_flash_exact_all_recorded(self):
        r = compare(self.root/'flash-next')
        self.assertTrue(r['all_recorded_exact'])
        self.assertEqual(len(r['operators']), 42)
        self.assertFalse(r['promotion_eligible'])
        self.assertTrue(all(u['status']=='VERIFIED-EXACT' for u in r['census'].values()))

    def test_raw_dtype_hashes_state_and_rows(self):
        for model in ('27b','flash-next'):
            root = self.root/model
            run = json.loads((root/'extraction-result.json').read_text())
            observed = set()
            for entry in run['fixtures']:
                f = json.loads((root/entry['path']).read_text())
                jsonschema.validate(f, schema())
                observed.add(f['operator']['M'])
                self.assertEqual(f['diagnostic']['rows'], list(range(f['operator']['M'])))
                for group in ('inputs','outputs','state_before','state_after'):
                    for t in f[group]:
                        self.assertEqual(file_hash(root/t['artifact']['path']), t['artifact']['sha256'])
                        self.assertEqual(load_tensor(root,t,2**30).shape, torch.Size(t['shape']))
                if f['operator']['name']=='gdn_recurrence':
                    before, after = f['state_before'][0], f['state_after'][0]
                    self.assertNotEqual(before['artifact']['sha256'],after['artifact']['sha256'])
                    self.assertEqual(after['dtype'], 'F32' if model=='27b' else 'BF16')
            self.assertEqual(observed,{1,2,6})

    def mutated_bundle(self):
        # Reflinks are not assumed; small subsets avoid copying whole bundles.
        tmp = tempfile.TemporaryDirectory(prefix='packet4-mutation-')
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        source = self.root/'27b'
        run = json.loads((source/'extraction-result.json').read_text())
        run['fixtures'] = run['fixtures'][:1]
        for name in ('oracle.json','run-identity.json','pending.json','extractor.py.txt'):
            (root/name).write_bytes((source/name).read_bytes())
        f = json.loads((source/run['fixtures'][0]['path']).read_text())
        for group in ('inputs','outputs','state_before','state_after'):
            for t in f[group]:
                name=t['artifact']['path']
                (root/name).write_bytes((source/name).read_bytes())
        self.save_mutation(root,run,f)
        return root,run,f

    def save_mutation(self,root,run,f):
        name=run['fixtures'][0]['path']
        (root/name).write_bytes(json_bytes(f))
        run['fixtures'][0]['sha256']=file_hash(root/name)
        (root/'extraction-result.json').write_bytes(json_bytes(run))

    def test_nonexact_classification_and_uncovered_rows(self):
        root,run,f=self.mutated_bundle()
        t=f['outputs'][0]
        path=root/t['artifact']['path']
        raw=bytearray(path.read_bytes());raw[0]^=1;path.write_bytes(raw)
        t['artifact']['sha256']=file_hash(path)
        self.save_mutation(root,run,f)
        r=compare(root)
        self.assertEqual(r['census']['U1']['status'],'VERIFIED-DIFF')
        self.assertEqual(r['census']['U7']['status'],'UNTESTED')
        self.assertEqual(r['operators'][0]['comparisons']['result']['max_ulp'],1)

    def test_unmapped_operator_untested(self):
        root,run,f=self.mutated_bundle();f['diagnostic']['reference_call']=None
        self.save_mutation(root,run,f)
        self.assertEqual(compare(root)['census']['U1']['status'],'UNTESTED')

    def test_unmapped_output_untested(self):
        root,run,f=self.mutated_bundle();f['diagnostic']['expected']={}
        self.save_mutation(root,run,f)
        self.assertEqual(compare(root)['census']['U1']['status'],'UNTESTED')

    def test_blob_corruption_rejected(self):
        root,run,f=self.mutated_bundle()
        (root/f['inputs'][0]['artifact']['path']).write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError,'hash'):compare(root)

    def test_envelope_corruption_rejected(self):
        root,run,f=self.mutated_bundle()
        (root/run['fixtures'][0]['path']).write_text('{}')
        with self.assertRaisesRegex(ValueError,'envelope'):compare(root)

    def test_no_token_substitution(self):
        root,run,f=self.mutated_bundle();run['token_ids'][0]+=1
        self.save_mutation(root,run,f)
        with self.assertRaisesRegex(ValueError,'neutrality'):compare(root)

    def test_rejected_neutrality_not_compared(self):
        root,run,f=self.mutated_bundle();run['status']='rejected'
        self.save_mutation(root,run,f)
        with self.assertRaisesRegex(ValueError,'rejected'):compare(root)

    def test_stale_reference_not_compared(self):
        root,run,f=self.mutated_bundle();f['diagnostic']['reference_sha256']='0'*64
        self.save_mutation(root,run,f)
        with self.assertRaisesRegex(ValueError,'reference changed'):compare(root)

    def test_path_escape(self):
        root,run,f=self.mutated_bundle();f['inputs'][0]['artifact']['path']='../escape'
        self.save_mutation(root,run,f)
        with self.assertRaises(jsonschema.ValidationError):compare(root)

    def test_comparison_cap(self):
        with self.assertRaisesRegex(ValueError,'cap exceeded'):compare(self.root/'27b', 8)


class Guards(unittest.TestCase):
    def recorder(self, cap=200000):
        from common import token_hash
        tmp=tempfile.TemporaryDirectory(prefix='packet4-guard-');self.addCleanup(tmp.cleanup)
        oracle={'rows':[{'prompt_id':str(i),'prompt_sha256':token_hash([i]),'token_ids':[1], 'sha256':token_hash([1])} for i in range(12)]}
        return Recorder(Path(tmp.name)/'fixtures','27b',mock_identity(),dict(EAGER),oracle,'0',cap,16)

    def test_graph_refusal_before_any_write(self):
        for key,value in [('enforce_eager',False),('graph_mode','FULL_DECODE_ONLY'),('compile_mode','VLLM_COMPILE'),('prefix_caching',True)]:
            config=dict(EAGER);config[key]=value
            with self.assertRaises(ValueError):refuse_capture(config)

    def test_graph_environment_refusal(self):
        with patch.dict('os.environ',{'VLLM_XPU_ENABLE_XPU_GRAPH':'1'}):
            with self.assertRaisesRegex(ValueError,'graph capture'):refuse_capture(EAGER)

    def test_compile_refusal(self):
        with patch('torch.compiler.is_compiling',return_value=True):
            with self.assertRaisesRegex(ValueError,'compiled region'):refuse_capture(EAGER)

    def test_native_missing_identity(self):
        with self.assertRaisesRegex(ValueError,'native identity missing'):validate_native_identity({'mock':False})

    def test_mock_meta_rejected_without_device_query(self):
        r=self.recorder()
        with self.assertRaisesRegex(ValueError,'CPU tensors'):r.tensor('x',torch.empty(1,device='meta'))

    def test_total_byte_cap_before_copy(self):
        r=self.recorder();before=r.used
        with self.assertRaisesRegex(ValueError,'cap exceeded'):r.tensor('large',torch.empty(100000))
        self.assertEqual(before,r.used)

    def test_strided_broadcast_scalar_empty_roundtrip(self):
        r=self.recorder()
        for i,x in enumerate((torch.arange(24).reshape(4,6).T,torch.ones(1,3).expand(7,3),torch.tensor(3.),torch.empty(0,3))):
            t=r.tensor(str(i),x)
            self.assertTrue(torch.equal(load_tensor(r.root,t,2**20),x.reshape(1) if x.ndim==0 else x))

    def test_hook_return_identity_and_removal_on_failure(self):
        # begin/end exercised independently of synthetic reference math.
        r=self.recorder()
        m=torch.nn.Identity();x=torch.tensor([1.])
        with patch.object(r,'begin',return_value=None):
            with r.hook(m,{},lambda m,a,k: (list(a),k),lambda m,a,k,y:{'y':y}):
                self.assertIs(m(x),x)
            self.assertFalse(m._forward_hooks);self.assertFalse(m._forward_pre_hooks)
            with self.assertRaisesRegex(RuntimeError,'intentional'):
                with r.hook(m,{},lambda m,a,k: (list(a),k),lambda m,a,k,y:{'y':y}):
                    raise RuntimeError('intentional')
            self.assertFalse(m._forward_hooks);self.assertFalse(m._forward_pre_hooks)

    def test_graph_flip_refused_before_read(self):
        r=self.recorder();r.config['graph_mode']='FULL'
        with self.assertRaisesRegex(ValueError,'eager only'):r.tensor('x',torch.ones(1))

    def test_qualified_schema_forbidden(self):
        jsonschema.Draft202012Validator.check_schema(schema())
        self.assertNotIn('qualified',schema()['properties']['status']['enum'])

    def spec(self):
        return {'name':'residual','layer':0,'M':1,'N':1,'K':1,'rows':[0],
                'positions':[0],'valid_rows':[True],'arithmetic_order':'synthetic add',
                'rounding_points':['F32'],'census_items':['U3'],'reference':'residual_add',
                'expected':{'result':'outputs:result'},'location':'mock.inplace','rank':0}

    def test_monkeypatch_inplace_original_once_and_restored(self):
        import types
        r=self.recorder();calls=[]
        def add(x,y):
            calls.append(1);x.add_(y)
        owner=types.SimpleNamespace(add=add)
        x=torch.tensor([1.]);y=torch.tensor([2.])
        with r.monkeypatch(owner,'add',lambda a,k:self.spec(),lambda a,k:([a[0],a[1]],{}),
                          lambda a,k,o:{'result':a[0]},lambda a,k:{}):
            self.assertIsNone(owner.add(x,y))
        self.assertIs(owner.add,add);self.assertEqual(calls,[1]);self.assertEqual(x.item(),3)
        r.finish([1]);self.assertTrue(compare(r.root)['all_recorded_exact'])

    def test_oracle_mismatch_stores_rejection(self):
        r=self.recorder();x=torch.tensor([1.])
        idx=r.begin(self.spec(),[x,x],{},{});r.end(idx,{'result':x+x},{})
        with self.assertRaisesRegex(AssertionError,'final token'):r.finish([2])
        result=json.loads((r.root/'extraction-result.json').read_text())
        self.assertEqual(result['status'],'rejected')
        with self.assertRaises(ValueError):compare(r.root)

    def test_cache_hit_stores_rejection(self):
        r=self.recorder();x=torch.tensor([1.])
        idx=r.begin(self.spec(),[x,x],{},{});r.end(idx,{'result':x+x},{})
        with self.assertRaisesRegex(AssertionError,'cached_tokens'):r.finish([1],cached_tokens=1)

    def test_capture_entrypoint_cannot_run(self):
        import types
        calls=[]
        original=lambda:calls.append(1)
        owner=types.SimpleNamespace(capture_begin=original)
        with forbid_graph_entrypoints([(owner,'capture_begin')]):
            with self.assertRaisesRegex(RuntimeError,'capture refused'):owner.capture_begin()
        self.assertIs(owner.capture_begin,original);self.assertEqual(calls,[])

    def test_missing_capture_entrypoint_restores_earlier_patch(self):
        import types
        original=lambda:None
        owner=types.SimpleNamespace(capture_begin=original)
        with self.assertRaises(AttributeError):
            with forbid_graph_entrypoints([(owner,'capture_begin'),(owner,'missing')]):pass
        self.assertIs(owner.capture_begin,original)

    def test_both_real_oracle_envelopes_parse_without_model_reads(self):
        from common import LANE, token_hash
        for stage in ('stage1','stage2'):
            value=normalize_oracle(json.loads((LANE/stage/'packet1/oracle-token-ids.json').read_text()))
            self.assertEqual(len(value['rows']),12)
            for row in value['rows']:self.assertEqual(row['sha256'],token_hash(row['token_ids']))

    def test_identity_audit_all_seal_members(self):
        from audit_identity import audit
        a=audit();members=[m for s in a['a367']['sealed_series'] for m in s['members']]
        self.assertEqual(len(members),75);self.assertTrue(all(m['matched'] for m in members))
        self.assertIsNone(a['a367']['certified_image_digest'])
        self.assertFalse(a['reopen']['certified_as_A367'])

    def test_native_cli_refuses_before_import(self):
        import os, subprocess, sys
        from common import HERE
        tmp=tempfile.TemporaryDirectory(prefix='packet4-cli-');self.addCleanup(tmp.cleanup)
        root=Path(tmp.name)
        result=subprocess.run([sys.executable,'-B',str(HERE/'extract_fixtures.py'),'--model','flash-next','--output',str(root/'out')],capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
        self.assertIn('A367 has no certified image digest',result.stderr)
        self.assertFalse((root/'out').exists())

    def test_mock_and_compare_cli_both_models(self):
        import subprocess, sys
        from common import HERE
        tmp=tempfile.TemporaryDirectory(prefix='packet4-cli-');self.addCleanup(tmp.cleanup)
        root=Path(tmp.name)
        for model in ('27b','flash-next'):
            capture=subprocess.run([sys.executable,'-B',str(HERE/'extract_fixtures.py'),'--mock','--model',model,'--output',str(root/model),'--max-bytes',str(128*1024**2)],capture_output=True,text=True)
            self.assertEqual(capture.returncode,0,capture.stderr)
            report=root/(model+'-report.json')
            replay=subprocess.run([sys.executable,'-B',str(HERE/'compare_fixtures.py'),str(root/model),'--output',str(report)],capture_output=True,text=True)
            self.assertEqual(replay.returncode,0,replay.stderr)
            self.assertTrue(json.loads(report.read_text())['all_recorded_exact'])


class Differences(unittest.TestCase):
    def test_one_ulp_f16_bf16_f32(self):
        for dtype in (torch.float16,torch.bfloat16,torch.float32):
            a=torch.tensor([1.],dtype=dtype);b=torch.nextafter(a,torch.full_like(a,2))
            self.assertEqual(difference(a,b)['max_ulp'],1)
    def test_negative_sign_ulp(self):
        a=torch.tensor([-1.]);b=torch.nextafter(a,torch.tensor([-2.]))
        self.assertEqual(difference(a,b)['max_ulp'],1)
    def test_signed_zero_bits(self):
        r=difference(torch.tensor([0.]),torch.tensor([-0.]))
        self.assertFalse(r['bit_exact']);self.assertEqual(r['max_abs'],0)
    def test_nan_not_tolerance_pass(self):
        r=difference(torch.tensor([float('nan')]),torch.tensor([1.]))
        self.assertFalse(r['bit_exact']);self.assertIsNone(r['max_ulp'])
    def test_i64_no_overflow(self):
        r=difference(torch.tensor([-(2**63)]),torch.tensor([2**63-1]))
        self.assertEqual(r['max_abs'],2**64-1)
    def test_shape_and_dtype(self):
        self.assertFalse(difference(torch.ones(1),torch.ones(2))['bit_exact'])
        self.assertFalse(difference(torch.ones(1),torch.ones(1,dtype=torch.float16))['bit_exact'])
    def test_empty(self):
        self.assertTrue(difference(torch.empty(0),torch.empty(0))['bit_exact'])


if __name__=='__main__':unittest.main()

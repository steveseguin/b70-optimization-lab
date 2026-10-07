#!/usr/bin/env python3
"""CPU source/authorization controls; no Torch, native imports, endpoint or runtime writes."""
import ast
import contextvars
import importlib.util
import os
from pathlib import Path
import sys
import types
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
spec=importlib.util.spec_from_file_location('geometry_overlay',Path(__file__).with_name('geometry_overlay.py'))
G=importlib.util.module_from_spec(spec);spec.loader.exec_module(G)
PARENT=Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-upstream-99b')
ENV={'LTX_OUTPUT_SIZE':'640x384','LTX_SAMPLER_PLACEMENT':'two-way','LTX_SAMPLER_WORKERS':'2',
     'LTX_SAMPLER_BATCH':'1','LTX_SAMPLER_SHARED_POOL':'1','LTX_DECODE_REPLICA_DEVICE':'xpu:2','LTX_DECODE_REPLICAS':'1'}


def module(size='640x384'):
    obj=types.ModuleType('synthetic_geometry')
    with patch.dict(os.environ,dict(ENV,LTX_OUTPUT_SIZE=size),clear=True):
        exec(compile(G.transform(G.GEOMETRY_PATH,(PARENT/G.GEOMETRY_PATH).read_bytes()),'<transformed geometry>','exec'),obj.__dict__)
    return obj


def authority(phase='native_reference',**updates):
    calls=[]
    def require_phase(role,qid,run_name):
        calls.append((role,qid,run_name))
        return dict({'role':role,'qualification_id':qid,'run_name':run_name,'phase':phase,
                    'plan_sha256':G.PLAN_SHA256,'comparison_mode':'same-size-native-v1',
                    'runtime_manifest_sha256':'a'*64,'server_identity_sha256':'b'*64,
                    'reference_receipt_sha256':'c'*64,'candidate_receipt_sha256':'d'*64},**updates)
    return types.SimpleNamespace(require_phase=require_phase,auxiliary_metadata=lambda:None),calls


def entry(m,role='text',body=None):
    @m.receipt_scope(role=role)
    def call(run_name,output_size='256x256',speed_only=False,comparison_mode='historical',qualification_id=''):
        m.admit_arm(output_size,speed_only)
        if body:body()
        return m.receipt_metadata()
    return call


class GeometryControls(unittest.TestCase):
    def setUp(self):
        self.m=module();self.env=patch.dict(os.environ,ENV,clear=True);self.env.start();self.addCleanup(self.env.stop)
        self.kw=dict(run_name='resolution-w2-20261007-native-p1-boat',output_size='640x384',
                     speed_only=False,comparison_mode='same-size-native-v1',qualification_id=G.QUALIFICATION_ID)

    def test_historical_geometry_and_guards_unchanged(self):
        m=module('256x256');self.assertEqual(entry(m)('historical'),{'output_size':'256x256','speed_only':False,'comparison':'references:w93c'})
        self.assertEqual(entry(m)('historical',speed_only=True)['comparison'],'none (speed only)')
        with self.assertRaises(RuntimeError):entry(self.m)('historical',output_size='640x384')
        self.assertEqual(entry(self.m)('historical',output_size='640x384',speed_only=True)['comparison'],'none (speed only)')
        with self.assertRaises(RuntimeError):self.m.require_reference_size()
        with self.assertRaises(RuntimeError):self.m.admit_arm('640x384',False)

    def test_valid_native_text_and_scope_reset(self):
        auth,calls=authority();ran=[]
        with patch.dict(sys.modules,{'ltx_resolution_session':auth}):
            result=entry(self.m,body=lambda:ran.append(True))(**self.kw)
        self.assertEqual(len(calls),1);self.assertEqual(ran,[True]);self.assertFalse(result['speed_only'])
        self.assertFalse(result['output_parity_claimed']);self.assertEqual(result['phase_authorization']['phase'],'native_reference')
        self.assertIsNone(self.m._RESOLUTION_CONTEXT.get())
        with self.assertRaises(RuntimeError):self.m.admit_arm('640x384',False)

    def test_phase_refusal_before_numerical_body(self):
        for phase,role in [('native_reference','sampler'),('native_reference','decode'),('reference_verified','text'),('candidate_verified','sampler')]:
            auth,_=authority(phase);ran=[]
            with self.subTest(phase=phase,role=role),patch.dict(sys.modules,{'ltx_resolution_session':auth}),self.assertRaises(RuntimeError):
                entry(self.m,role,lambda:ran.append(True))(**self.kw)
            self.assertEqual(ran,[])

    def test_preparation_and_timing_need_real_reference_and_candidate_receipts(self):
        for phase,missing in [('optimized_preparation','reference_receipt_sha256'),('timing','candidate_receipt_sha256')]:
            auth,_=authority(phase,**{missing:None})
            with patch.dict(sys.modules,{'ltx_resolution_session':auth}),self.assertRaises(RuntimeError):entry(self.m,'sampler')(**self.kw)
        for phase in ('optimized_preparation','timing'):
            auth,_=authority(phase)
            with patch.dict(sys.modules,{'ltx_resolution_session':auth}):
                self.assertEqual(entry(self.m,'decode')(**self.kw)['phase_authorization']['phase'],phase)

    def test_wrong_plan_role_request_runtime_refused(self):
        for key,value in [('plan_sha256','f'*64),('qualification_id','f'*64),('role','decode'),('run_name','another'),
                          ('runtime_manifest_sha256','not-a-sha'),('server_identity_sha256',None)]:
            auth,_=authority(**{key:value})
            with self.subTest(key=key),patch.dict(sys.modules,{'ltx_resolution_session':auth}),self.assertRaises(RuntimeError):
                entry(self.m)(**self.kw)

    def test_unknown_or_spoofed_modes_and_geometry_refuse(self):
        for key,value in [('comparison_mode','unknown'),('qualification_id','f'*64),('output_size','512x320'),('speed_only',True),('speed_only',0)]:
            with self.subTest(key=key),self.assertRaises(RuntimeError):entry(self.m)(**dict(self.kw,**{key:value}))
        with self.assertRaises(RuntimeError):entry(self.m)(**dict(self.kw,comparison_mode='historical'))

    def test_configuration_changes_refuse_before_authority(self):
        for key,value in [('LTX_SAMPLER_WORKERS','1'),('LTX_SAMPLER_WORKERS','3'),('LTX_SAMPLER_BATCH','2'),('LTX_SAMPLER_PLACEMENT','two-way20-28'),('LTX_DECODE_REPLICA_DEVICE','xpu:1')]:
            auth,calls=authority()
            with patch.dict(os.environ,{key:value}),patch.dict(sys.modules,{'ltx_resolution_session':auth}),self.assertRaises(RuntimeError):entry(self.m)(**self.kw)
            self.assertEqual(calls,[])

    def test_authority_failure_and_body_exception_propagate_without_scope_leak(self):
        class Stop(Exception):pass
        def fail(*a):raise Stop('authority failed')
        with patch.dict(sys.modules,{'ltx_resolution_session':types.SimpleNamespace(require_phase=fail)}),self.assertRaises(Stop):entry(self.m)(**self.kw)
        auth,_=authority()
        with patch.dict(sys.modules,{'ltx_resolution_session':auth}),self.assertRaises(Stop):entry(self.m,body=fail)(**self.kw)
        self.assertIsNone(self.m._RESOLUTION_CONTEXT.get())

    def test_context_does_not_authorize_worker_or_nested_historical_call(self):
        auth,_=authority()
        def nested():
            with self.assertRaises(RuntimeError):contextvars.Context().run(self.m.admit_arm,'640x384',False)
            with self.assertRaises(RuntimeError):entry(self.m)('nested',output_size='640x384',speed_only=True)
        with patch.dict(sys.modules,{'ltx_resolution_session':auth}):entry(self.m,body=nested)(**self.kw)

    def test_auxiliary_worker_metadata_cannot_grant_numerical_admission(self):
        auth,_=authority('reference_verified')
        aux=auth.require_phase('auxiliary',G.QUALIFICATION_ID,None)
        aux['output_parity_claimed']=False
        auth.auxiliary_metadata=lambda:dict(aux)
        with patch.dict(sys.modules,{'ltx_resolution_session':auth}):
            result=contextvars.Context().run(self.m.receipt_metadata)
            self.assertEqual(result['session_observation']['phase'],'reference_verified')
            self.assertFalse(result['speed_only']);self.assertFalse(result['output_parity_claimed'])
            self.assertNotIn('phase_authorization',result)
            with self.assertRaises(RuntimeError):self.m.admit_arm('640x384',False)
            aux['plan_sha256']='0'*64
            with self.assertRaises(RuntimeError):self.m.receipt_metadata()

    def test_actual_session_authority_integration(self):
        spec=importlib.util.spec_from_file_location('geometry_real_session',Path(__file__).with_name('session.py'))
        session=importlib.util.module_from_spec(spec);spec.loader.exec_module(session)
        plan=Path(__file__).resolve().parent.parent/'20261007-resolution-w2-102/candidate-plan.json'
        state={'queue_pending':0,'queue_running':0,'pipeline':{'running':0,'stages':{}},
               'fault':False,'sampler_routes':0,'lean_state':0,'decode_replicas':0}
        with tempfile.TemporaryDirectory() as td:
            a=session.configure(plan,'a'*64,'b'*64,Path(td),lambda:dict(state),{})
            row=a.plan['requests'][0]
            with patch.dict(sys.modules,{'ltx_resolution_session':session}):
                a.begin(row['name'],row['graph'],'independent-request')
                result=entry(self.m)(**self.kw)
                self.assertEqual(result['phase_authorization']['plan_sha256'],G.PLAN_SHA256)
                self.assertIsNone(result['phase_authorization']['reference_receipt_sha256'])
                a.finish([('execution_cached',{'nodes':[]}),('execution_success',{'prompt_id':'independent-request'})])
                self.assertFalse(self.m.receipt_metadata()['output_parity_claimed'])
                with self.assertRaises(RuntimeError):self.m.admit_arm('640x384',False)
                with self.assertRaisesRegex(RuntimeError,'active request'):entry(self.m)(**self.kw)
                self.assertIsNotNone(a.failed)
                with self.assertRaisesRegex(RuntimeError,'Session halted'):
                    a.begin(row['name'],row['graph'],'refused-after-halt')

    def test_transform_exact_inventory_and_mirrors(self):
        sources={p:(PARENT/p).read_bytes() for p in G.SOURCE_HASHES};out=G.transform_sources(sources)
        self.assertEqual(len(out),7);self.assertNotIn('torch',sys.modules)
        for name,(role,_,package) in G.SPECS.items():
            raw=out['source/scripts/'+name];self.assertEqual(raw,out['source/custom_nodes/'+package+'/__init__.py'])
            before=ast.parse(sources['source/scripts/'+name]);after=ast.parse(raw)
            oldclasses={n.name:n for n in before.body if isinstance(n,ast.ClassDef)}
            newclasses={n.name:n for n in after.body if isinstance(n,ast.ClassDef)}
            for cname,c in oldclasses.items():
                oldf={n.name:n for n in c.body if isinstance(n,ast.FunctionDef)}
                newf={n.name:n for n in newclasses[cname].body if isinstance(n,ast.FunctionDef)}
                for name,func in oldf.items():
                    if name=='INPUT_TYPES':continue
                    self.assertEqual([ast.dump(n) for n in func.body],[ast.dump(n) for n in newf[name].body])
            self.assertIn(b"comparison_mode='historical', qualification_id=''",raw)

    def test_changed_reapplied_or_missing_source_refuses(self):
        raw=(PARENT/G.GEOMETRY_PATH).read_bytes()
        for bad in (raw+b'\n',G.transform(G.GEOMETRY_PATH,raw)):
            with self.assertRaises(ValueError):G.transform(G.GEOMETRY_PATH,bad)
        with self.assertRaises(ValueError):G.transform('unknown',raw)
        with self.assertRaises(ValueError):G.transform_sources({G.GEOMETRY_PATH:raw})


if __name__=='__main__':unittest.main(verbosity=2)

"""Synthetic metadata tests using the actual pinned110 safety controller."""
import importlib.util
from pathlib import Path
import sys
import threading
from types import SimpleNamespace as NS
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import conditioning_guard as G

SOURCE = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-duration-full-110/source/scripts/native_safety.py')
spec = importlib.util.spec_from_file_location('conditioning_test_sealed110_safety', SOURCE)
S = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = S
spec.loader.exec_module(S)
SHA = 'a' * 64


class Tensor:
    def __init__(self, shape):
        self.shape = list(shape)
        self.storage = id(self)
        self.dtype, self.device, self.contiguous = 'torch.float32', 'cpu', True


class Fixture:
    def __init__(self):
        self.objects = {role: NS() for role in S.ROLES}
        self.vae = self.objects['video_vae']
        self.vae.first_stage_model = NS(encoder=NS())
        self.free = dict(G.PRE)
        self.fault = False
        self.syncs = []
        self.cache_count = self.foreign = 0
        self.cache_source = G.ENCODER_SHA256
        self.anchor_hash = SHA
        self.anchor_finite = True
        self.calls = []
        self.inspect_hook = None
        self.safety = S.NativeReferenceSafety(
            plan_sha256=SHA, runtime_sha256='b'*64, objects=self.objects,
            expected_residence={r: 'c'*64 for r in S.ROLES},
            synchronize=self.syncs.append, inspect=self.inspect, require_phase=lambda: None)
        self.guard = G.ConditioningStageGuard(controller=self.safety,
            tensor_metadata=self.meta, inspect_anchor=self.anchor_check,
            inspect_encoder_cache=self.cache, unwrap_output=lambda x: x.result[0])
        self.anchor = Tensor([1, 384, 640, 3])

    def inspect(self, objects):
        if self.inspect_hook:
            self.inspect_hook()
        return dict(plan_sha256=SHA, runtime_sha256='b'*64, phase='native-reference',
            fault=self.fault, text_graphs_captured=True, window_qualified=True,
            sampler_routes=0, decoder_replicas=0, physical_free_bytes=dict(self.free),
            peaks={c: dict(allocated=1, reserved=2, peak=1) for c in G.PRE},
            residence={r: dict(object_id=id(objects[r]), device=c, dtype='torch.bfloat16',
                              fully_resident=True, ownership_sha256='c'*64)
                       for r,c in S.ROLES.items()})

    def meta(self, obj):
        return dict(object_id=id(obj), storage_id=obj.storage, shape=obj.shape,
                    dtype=obj.dtype, device=obj.device, contiguous=obj.contiguous)

    def anchor_check(self, obj):
        assert obj is self.anchor
        return dict(sha256=self.anchor_hash, finite=self.anchor_finite)

    def cache(self, encoder, tid):
        return dict(source_sha256=self.cache_source, encoder_id=id(encoder),
                    thread_ident=tid, entry_count=self.cache_count,
                    foreign_entry_count=self.foreign)

    def begin(self, name='conditioned-1'):
        self.safety.before(name)
        self.guard.begin_request(name, anchor=self.anchor, expected_anchor_sha256=SHA)

    def native(self, **kw):
        self.calls.append(kw)
        return NS(result=({'samples': Tensor(kw['latent']['samples'].shape),
                           'noise_mask': Tensor([1, 1, 7, 1, 1])},))

    def stage(self, stage='A', call=None, **overrides):
        args=dict(request_id=self.guard.active, vae=self.vae,
                  latent={'samples': Tensor(G.SHAPES.get(stage, G.SHAPES['A']))},
                  native_call=call or self.native)
        args.update(overrides)
        return self.guard.run_stage(stage, **args)


class Tests(unittest.TestCase):
    def assert_latched(self, f):
        self.assertIsNotNone(f.guard.failed)
        self.assertIsNotNone(f.safety.failed)
        before=len(f.calls)
        with self.assertRaises(Exception): f.stage()
        self.assertEqual(before,len(f.calls))

    def test_success_original_nodeoutput_exact_kwargs_and_real_snapshots(self):
        f=Fixture();f.begin();returned=[]
        def native(**kw):
            result=f.native(**kw);returned.append(result);return result
        self.assertIs(f.stage('A', native),returned[0])
        self.assertIs(f.stage('B', native),returned[1])
        f.guard.finish_request('conditioned-1');f.safety.after()
        self.assertIsNone(f.guard.failed)
        self.assertIsNone(f.guard.anchor)
        self.assertEqual(len(f.syncs),6*4)
        stages=[r for r in f.guard.receipts if r['event']=='stage']
        self.assertEqual([r['stage'] for r in stages],['A','B'])
        for row,kw in zip(stages,f.calls):
            self.assertTrue(row['completed'])
            self.assertEqual(row['before']['required_physical_free_bytes'],G.PRE)
            self.assertEqual(row['after']['required_physical_free_bytes'],G.POST)
            self.assertIs(kw['image'],f.anchor);self.assertIs(kw['vae'],f.vae)
            self.assertEqual(kw['strength'],1.0);self.assertIs(kw['bypass'],False)
        self.assertEqual([r['source_derived_encode_expectation']['workspace_estimate_bytes']
                          for r in stages],[68812800,275251200])
        self.assertEqual([r['source_derived_encode_expectation']['expected_input_shape']
                          for r in stages],[[1,3,1,192,320],[1,3,1,384,640]])
        self.assertTrue(all(r['source_derived_encode_expectation']['internal_pixels_observed'] is False
                            for r in stages))

    def test_source_controller_refuses_imitation(self):
        with self.assertRaises(Exception):
            G.ConditioningStageGuard(controller=NS(),tensor_metadata=lambda x:x,
                inspect_anchor=lambda x:x,inspect_encoder_cache=lambda *a:None,
                unwrap_output=lambda x:x)

    def test_four_conditioned_request_cap_and_no_cross_request_anchor(self):
        f=Fixture()
        for i in range(4):
            name='r'+str(i);f.begin(name);f.stage();f.stage('B')
            f.guard.finish_request(name);f.safety.after()
            f.anchor=Tensor([1,384,640,3])
        with self.assertRaises(G.ConditioningRefusal):f.begin('r4')
        self.assert_latched(f)

    def test_reject_b_first_duplicate_a_and_duplicate_b(self):
        for completed,next_stage in [([], 'B'),(['A'],'A'),(['A','B'],'B')]:
            with self.subTest(completed=completed):
                f=Fixture();f.begin()
                for stage in completed:f.stage(stage)
                with self.assertRaises(G.ConditioningRefusal):f.stage(next_stage)
                self.assertEqual(len(f.calls),len(completed));self.assert_latched(f)

    def test_finish_missing_b(self):
        f=Fixture();f.begin();f.stage()
        with self.assertRaises(G.ConditioningRefusal):f.guard.finish_request('conditioned-1')
        self.assert_latched(f)

    def test_bound_vae_encoder_and_safety_owner(self):
        for mutation in [lambda f:setattr(f.vae.first_stage_model,'encoder',NS()),
                         lambda f:setattr(f.vae,'_ltx_native_reference_safety',None),
                         lambda f:f.safety.objects.update(video_vae=NS())]:
            f=Fixture();f.begin();mutation(f)
            with self.assertRaises(G.ConditioningRefusal):f.stage()
            self.assertEqual(f.calls,[]);self.assert_latched(f)
        f=Fixture();f.begin()
        with self.assertRaises(G.ConditioningRefusal):f.stage(vae=NS())
        self.assert_latched(f)

    def test_anchor_hash_finite_storage_and_shape_rechecked(self):
        for mutation in [lambda f:setattr(f,'anchor_hash','d'*64),
                         lambda f:setattr(f,'anchor_finite',False),
                         lambda f:setattr(f.anchor,'storage',123),
                         lambda f:setattr(f.anchor,'shape',[1,192,320,3])]:
            f=Fixture();f.begin();f.stage();mutation(f)
            with self.assertRaises(G.ConditioningRefusal):f.stage('B')
            self.assertEqual(len(f.calls),1);self.assert_latched(f)

    def test_stage_input_geometry_dtype_device_and_existing_mask(self):
        for key,value in [('shape',[1,128,4,6,10]),('dtype','torch.bfloat16'),
                          ('device','xpu:3'),('contiguous',False)]:
            f=Fixture();f.begin();t=Tensor(G.SHAPES['A']);setattr(t,key,value)
            with self.assertRaises(G.ConditioningRefusal):f.stage(latent={'samples':t})
            self.assert_latched(f)
        f=Fixture();f.begin()
        with self.assertRaises(G.ConditioningRefusal):
            f.stage(latent={'samples':Tensor(G.SHAPES['A']),'noise_mask':object()})

    def test_changed_active_request_before_during_and_snapshot(self):
        for where in ['before','during','snapshot']:
            f=Fixture();f.begin()
            if where=='before':f.safety.active='wrong'
            if where=='snapshot':f.inspect_hook=lambda:setattr(f.safety,'active','wrong')
            def native(**kw):
                if where=='during':f.safety.active='wrong'
                return f.native(**kw)
            with self.assertRaises(G.ConditioningRefusal):f.stage(call=native)
            self.assert_latched(f)
            if where!='during':self.assertEqual(f.calls,[])

    def test_snapshot_anchor_or_cache_change_refuses_before_call_or_exposure(self):
        for snapshot_number in [1,2]:
            for changed in ['anchor','cache']:
                with self.subTest(snapshot_number=snapshot_number,changed=changed):
                    f=Fixture();f.begin();count=0
                    def hook():
                        nonlocal count
                        count+=1
                        if count==snapshot_number:
                            if changed=='anchor':f.anchor_hash='d'*64
                            else:f.cache_count=1
                    f.inspect_hook=hook
                    with self.assertRaises(G.ConditioningRefusal):f.stage()
                    self.assertEqual(len(f.calls),snapshot_number-1)
                    row=next(r for r in f.guard.receipts if r['event']=='stage')
                    self.assertFalse(row['completed'])
                    self.assertEqual(f.guard.next_stage,'A')
                    self.assert_latched(f)

    def test_swallowed_pre_snapshot_recursive_stage_cannot_clear_outer_busy(self):
        f=Fixture();f.begin();observed=[]
        def hook():
            f.inspect_hook=None
            try:f.stage()
            except G.ConditioningRefusal:pass
            observed.append(f.guard.in_call)
        f.inspect_hook=hook
        with self.assertRaises(G.ConditioningRefusal):f.stage()
        self.assertEqual(observed,[True])
        self.assertFalse(f.guard.in_call)
        self.assertEqual(f.calls,[])
        self.assert_latched(f)

    def test_swallowed_metadata_reentry_into_each_public_api_fails_outer_stage(self):
        for target in ['run','begin','finish']:
            with self.subTest(target=target):
                f=Fixture();f.begin();base=f.guard.tensor_metadata;observed=[]
                def metadata(obj):
                    f.guard.tensor_metadata=base
                    try:
                        if target=='run':f.stage()
                        elif target=='begin':f.guard.begin_request('next',anchor=f.anchor,expected_anchor_sha256=SHA)
                        else:f.guard.finish_request('conditioned-1')
                    except G.ConditioningRefusal:pass
                    observed.append(f.guard.in_call)
                    return base(obj)
                f.guard.tensor_metadata=metadata
                with self.assertRaises(G.ConditioningRefusal):f.stage()
                self.assertEqual(observed,[True]);self.assertEqual(f.calls,[])
                self.assertFalse(f.guard.in_call);self.assert_latched(f)

    def test_begin_and_finish_callbacks_also_hold_busy_until_outer_exit(self):
        for phase in ['begin','finish']:
            with self.subTest(phase=phase):
                f=Fixture()
                if phase=='finish':f.begin();f.stage();f.stage('B')
                else:f.safety.before('conditioned-1')
                base=f.guard.inspect_encoder_cache;observed=[]
                def cache(*args):
                    f.guard.inspect_encoder_cache=base
                    try:f.stage()
                    except G.ConditioningRefusal:pass
                    observed.append(f.guard.in_call)
                    return base(*args)
                f.guard.inspect_encoder_cache=cache
                with self.assertRaises(G.ConditioningRefusal):
                    if phase=='begin':f.guard.begin_request('conditioned-1',anchor=f.anchor,expected_anchor_sha256=SHA)
                    else:f.guard.finish_request('conditioned-1')
                self.assertEqual(observed,[True]);self.assertFalse(f.guard.in_call)
                self.assertEqual(len(f.calls),0 if phase=='begin' else 2)
                self.assertFalse(any(r['event']=='finish' for r in f.guard.receipts))
                self.assert_latched(f)

    def test_thread_owner_change(self):
        f=Fixture();f.begin();f.guard.thread_ident=threading.get_ident()+1
        with self.assertRaises(G.ConditioningRefusal):f.stage()
        self.assert_latched(f)

    def test_cache_callback_wrong_thread_and_boolean_counts(self):
        for field,value in [('thread_ident',0),('entry_count',False),('foreign_entry_count',False)]:
            f=Fixture();f.begin();base=f.guard.inspect_encoder_cache
            f.guard.inspect_encoder_cache=lambda *args:{**base(*args),field:value}
            with self.assertRaises(G.ConditioningRefusal):f.stage()
            self.assert_latched(f)

    def test_lowercase_stage_alias_refused(self):
        f=Fixture();f.begin()
        with self.assertRaises(G.ConditioningRefusal):f.stage('a')
        self.assertEqual(f.calls,[]);self.assert_latched(f)

    def test_low_pre_memory_on_each_card_never_calls_native(self):
        for card in G.PRE:
            f=Fixture();f.begin();f.free[card]-=1
            with self.assertRaises(S.SafetyRefusal):f.stage()
            self.assertEqual(f.calls,[]);self.assert_latched(f)

    def test_low_post_floor_leaves_partial_evidence(self):
        f=Fixture();f.begin()
        def native(**kw):
            f.free['xpu:3']=2*G.GIB-1;return f.native(**kw)
        with self.assertRaises(S.SafetyRefusal):f.stage(call=native)
        self.assert_latched(f)
        row=next(r for r in f.guard.receipts if r['event']=='stage')
        self.assertFalse(row['completed']);self.assertIn('before',row)
        self.assertEqual(row['exception'],'SafetyRefusal')
        evidence=f.safety.receipts[row['controller_receipt_start']:row['controller_receipt_end']]
        self.assertTrue(any(r.get('event')=='conditioning-A-after' and not r['admitted'] for r in evidence))

    def test_cache_residue_wrong_source_foreign_or_owner(self):
        for field,value in [('cache_count',1),('foreign',1),('cache_source','d'*64)]:
            f=Fixture();f.begin();setattr(f,field,value)
            with self.assertRaises(G.ConditioningRefusal):f.stage()
            self.assertEqual(f.calls,[]);self.assert_latched(f)
        f=Fixture();f.begin();base=f.guard.inspect_encoder_cache
        f.guard.inspect_encoder_cache=lambda *args:{**base(*args),'encoder_id':1}
        with self.assertRaises(G.ConditioningRefusal):f.stage()
        self.assert_latched(f)

    def test_cache_residue_after_native(self):
        f=Fixture();f.begin()
        def native(**kw):
            f.cache_count=1;return f.native(**kw)
        with self.assertRaises(G.ConditioningRefusal):f.stage(call=native)
        self.assert_latched(f)

    def test_oom_preserved_no_retry_both_latched_and_cleanup_evidence(self):
        f=Fixture();f.begin();error=MemoryError('synthetic encode OOM')
        def native(**kw):
            f.calls.append(kw);raise error
        with self.assertRaises(MemoryError) as caught:f.stage(call=native)
        self.assertIs(caught.exception,error);self.assertEqual(len(f.calls),1)
        self.assert_latched(f)
        row=next(r for r in f.guard.receipts if r['event']=='stage')
        self.assertFalse(row['completed']);self.assertEqual(row['cache_on_failure']['entry_count'],0)

    def test_fault_before_and_after_native(self):
        for before in [True,False]:
            f=Fixture();f.begin();f.fault=before
            def native(**kw):
                f.fault=True;return f.native(**kw)
            with self.assertRaises(S.SafetyRefusal):f.stage(call=native)
            self.assertEqual(len(f.calls),0 if before else 1);self.assert_latched(f)

    def test_bad_output_shape_mask_and_alias(self):
        for defect in ['shape','mask','alias']:
            f=Fixture();f.begin()
            def native(**kw):
                result=f.native(**kw);out=result.result[0]
                if defect=='shape':out['samples'].shape=[1,128,1,6,10]
                if defect=='mask':out['noise_mask'].dtype='torch.bfloat16'
                if defect=='alias':out['samples']=kw['latent']['samples']
                return result
            with self.assertRaises(G.ConditioningRefusal):f.stage(call=native)
            self.assert_latched(f)

    def test_native_mutating_anchor_refused_before_return(self):
        f=Fixture();f.begin()
        def native(**kw):
            f.anchor_hash='e'*64;return f.native(**kw)
        with self.assertRaises(G.ConditioningRefusal):f.stage(call=native)
        self.assert_latched(f)

    def test_overlap_and_reentry_fail_persistently(self):
        f=Fixture();f.begin()
        with self.assertRaises(G.ConditioningRefusal):
            f.guard.begin_request('conditioned-1',anchor=f.anchor,expected_anchor_sha256=SHA)
        self.assert_latched(f)
        f=Fixture();f.begin()
        def native(**kw):
            try:f.stage()
            except G.ConditioningRefusal:pass
            return f.native(**kw)
        with self.assertRaises(G.ConditioningRefusal):f.stage(call=native)
        self.assert_latched(f)

    def test_failed_guard_refuses_new_request_even_after_manual_active_clear(self):
        f=Fixture();f.begin()
        with self.assertRaises(G.ConditioningRefusal):f.stage('B')
        f.guard.active=None;f.safety.active='next'
        with self.assertRaises(G.ConditioningRefusal):
            f.guard.begin_request('next',anchor=f.anchor,expected_anchor_sha256=SHA)
        self.assertEqual(f.calls,[]);self.assert_latched(f)


if __name__ == '__main__':
    unittest.main()

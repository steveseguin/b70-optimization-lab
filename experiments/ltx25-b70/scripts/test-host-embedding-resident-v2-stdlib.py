#!/usr/bin/env python3
"""Inactive CLIP-only transition proof using stdlib fakes, never native imports."""
import ast
import gc
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import weakref

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m

old=load('resident_v1_test_helpers',HERE/'test-host-embedding-resident-stdlib.py')
mem=load('host_embedding_transition_memory',HERE/'host_embedding_transition_memory.py')
TARGET=HERE/'host_embedding_resident_node_v2.py'

class Box:
    def __init__(self,**kwargs):self.__dict__.update(kwargs)

class Assembly(old.Assembly):
    def __init__(self,root):
        super().__init__(root);self.registry=[];self.weakclips=[];self.available=128*1024**3;self.memory_events=[]
    def clip(self,**kwargs):
        self.event('clip',kwargs)
        model=Box(parameters=lambda:[Box(device=old.Device('cpu'))])
        patcher=Box(model=model,loaded_size=lambda:0,load_device=old.Device('xpu:2'))
        group=Box(mode=kwargs['mode'],retired=False,owner=None)
        if kwargs['mode']=='host-table':
            weight=Box();hostmodel=Box(weight=weight);host=Box(model=hostmodel)
            group.owner=Box(host=host,weight=weight)
            self.registry.append(weakref.ref(host))
        def guard():
            if group.retired:raise RuntimeError('retired')
        def retire(clip):
            guard();self.event('retire',group.mode);group.retired=True
            return {'original_ownership_restored':True,'all_shared_clones_retired':True}
        group.guard=guard;group.detach_restore=retire
        group.inventory=lambda clip:{'mode':group.mode,'encoder':{'parameters':{'records':[{'device':'xpu:2','bytes':1024}]},'buffers':{'records':[]}}}
        clip=Box(_host_embedding=group,patcher=patcher,cond_stage_model=model)
        self.registry.append(weakref.ref(patcher));self.weakclips.append(weakref.ref(clip))
        return clip
    def shard(self,model,**kwargs):
        super().shard(model,**kwargs)
        model.model=Box();model.shard=Box(model=Box())
        model.get_additional_models_with_key=lambda key:[model.shard]
        return model
    def cleanup(self):
        self.event('cleanup-native');self.registry[:]=[r for r in self.registry if r() is not None]
    def setup(self,module):
        module.checkpoint_geometry=lambda path:{'construction_overlap_bytes':mem.CHECKPOINT_TENSOR_BYTES+mem.REGISTERED_STATE_BYTES}
        def admission(stage,allocation):
            self.memory_events.append((stage,allocation))
            return mem.admission(stage,allocation,snapshot={'bytes':{'MemAvailable':self.available},'source':'synthetic'})
        module.admission=admission
        mm=sys.modules['comfy.model_management']
        mm.cleanup_models=self.cleanup;mm.loaded_models=lambda:[r() for r in self.registry if r() is not None]
        mm.unload_all_models=lambda:(_ for _ in ()).throw(AssertionError('bulk unload forbidden'))

class Tests(unittest.TestCase):
    def enter(self,a):
        context=a.loaded();m,node=context.__enter__();a.setup(m)
        self.addCleanup(context.__exit__,None,None,None)
        return m,node
    def test_three_generations_keep_shared_and_release_clip(self):
        with tempfile.TemporaryDirectory() as root,patch.object(old,'TARGET',TARGET):
            a=Assembly(root);m,node=self.enter(a)
            first=node.load('split','control');shared=[id(first[i]) for i in [0,2,3,4]];oldref=weakref.ref(first[1]);del first
            second=node.load('split','host-table');self.assertIsNone(oldref());self.assertEqual(shared,[id(second[i]) for i in [0,2,3,4]])
            hostref=weakref.ref(second[1]._host_embedding.owner);del second
            third=node.load('split','control');self.assertIsNone(hostref());self.assertEqual(shared,[id(third[i]) for i in [0,2,3,4]])
            self.assertEqual(sum(e[0]=='unet' for e in a.events),1);self.assertEqual(sum(e[0]=='vae' for e in a.events),2)
            self.assertEqual(sum(e[0]=='upscale' for e in a.events),1);self.assertEqual(sum(e[0]=='clip' for e in a.events),3)
            self.assertEqual(sum(e[0]=='cleanup-native' for e in a.events),2)
            self.assertFalse(any(e[0]=='unload_all' for e in a.events))
            release=json.loads((Path(root)/'host-components-03-control-retired-owner-release.json').read_text())
            self.assertTrue(release['all_retired_weakrefs_dead']);self.assertTrue(release['retired_patcher_ids_absent_from_registry'])
            self.assertIn('host_weight',release['checked'])
            self.assertEqual(m._generation,3)
    def test_external_model_owner_fails_before_replacement(self):
        with tempfile.TemporaryDirectory() as root,patch.object(old,'TARGET',TARGET):
            a=Assembly(root);m,node=self.enter(a)
            first=node.load('split','control');leak=first[1].cond_stage_model;del first
            with self.assertRaisesRegex(RuntimeError,'survived'):node.load('split','host-table')
            self.assertEqual(sum(e[0]=='clip' for e in a.events),1);self.assertIsNotNone(m._shared)
            self.assertIsNotNone(m._failure);self.assertIsNotNone(leak)
            with self.assertRaisesRegex(RuntimeError,'failed'):node.load('split','host-table')
    def test_external_output_tuple_fails_closed(self):
        with tempfile.TemporaryDirectory() as root,patch.object(old,'TARGET',TARGET):
            a=Assembly(root);m,node=self.enter(a);retained=node.load('split','control')
            with self.assertRaisesRegex(RuntimeError,'survived'):node.load('split','host-table')
            self.assertTrue(retained[1]._host_embedding.retired)
    def test_restore_floor_before_any_copy(self):
        with tempfile.TemporaryDirectory() as root,patch.object(old,'TARGET',TARGET):
            a=Assembly(root);m,node=self.enter(a);node.load('split','control')
            a.available=mem.EXISTING_HEADROOM_BYTES+1023
            with self.assertRaisesRegex(RuntimeError,'before-restore'):node.load('split','host-table')
            self.assertFalse(any(e[0]=='retire' for e in a.events));self.assertIsNotNone(m._components)
    def test_constructor_floor_after_old_death(self):
        with tempfile.TemporaryDirectory() as root,patch.object(old,'TARGET',TARGET):
            a=Assembly(root);m,node=self.enter(a);node.load('split','control')
            a.available=mem.EXISTING_HEADROOM_BYTES+mem.REGISTERED_STATE_BYTES
            with self.assertRaisesRegex(RuntimeError,'before-construction'):node.load('split','host-table')
            self.assertIsNone(a.weakclips[0]());self.assertIsNotNone(m._shared)
            self.assertEqual(sum(e[0]=='clip' for e in a.events),1)
            result=json.loads((Path(root)/'host-components-02-host-table-result.json').read_text())
            self.assertEqual(result['status'],'failed');self.assertTrue(result['shared_components_retained'])
    def test_constructor_failure_retains_shared_and_no_retry(self):
        with tempfile.TemporaryDirectory() as root,patch.object(old,'TARGET',TARGET):
            a=Assembly(root);m,node=self.enter(a);node.load('split','control');a.failure='clip'
            with self.assertRaisesRegex(RuntimeError,'injected clip'):node.load('split','host-table')
            self.assertIsNotNone(m._shared);self.assertIsNone(a.weakclips[0]())
            with self.assertRaisesRegex(RuntimeError,'failed'):node.load('split','host-table')
    def test_threshold_exact_and_no_swap_credit(self):
        allocation=mem.CHECKPOINT_TENSOR_BYTES+mem.REGISTERED_STATE_BYTES;floor=allocation+mem.EXISTING_HEADROOM_BYTES
        for delta,expected in [(-1,False),(0,True),(1,True)]:
            r=mem.admission('construction',allocation,snapshot={'bytes':{'MemAvailable':floor+delta,'SwapFree':10**15}})
            self.assertIs(r['passed'],expected);self.assertFalse(r['swap_counted_as_headroom'])
        self.assertEqual(allocation,52495358666)
    def test_missing_malformed_meminfo_refusal(self):
        valid='MemTotal: 100 kB\nMemAvailable: 80 kB\nMemFree: 60 kB\nSwapFree: 0 kB\nSwapTotal: 20 kB\n'
        with patch.object(mem.Path,'read_text',return_value=valid):self.assertEqual(mem.memory_snapshot()['bytes']['MemAvailable'],81920)
        for invalid in ['',valid.replace('80 kB','-1 kB'),valid.replace('80 kB','80 MB'),valid.replace('80 kB','101 kB')]:
            with patch.object(mem.Path,'read_text',return_value=invalid):
                with self.assertRaises((RuntimeError,KeyError)):mem.memory_snapshot()
    def test_actual_checkpoint_header_only_budget(self):
        p=Path('/mnt/fast-ai/llm-models/LTX-2.5-baseline/text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors')
        r=mem.checkpoint_geometry(p);self.assertEqual(r['construction_overlap_bytes'],52495358666)
    def test_source_no_bulkoffload_or_registry_mutation(self):
        tree=ast.parse(TARGET.read_text())
        forbidden={'unload_all_models','unload_model_and_clones','free_memory','to','empty_cache','synchronize'}
        calls={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertFalse(calls&forbidden);self.assertNotIn('current_loaded_models',TARGET.read_text())
        self.assertNotIn('torch',sys.modules);self.assertFalse(any(k.startswith('comfy.') for k in sys.modules))

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(json.dumps({'status':'passed' if result.wasSuccessful() else 'failed','tests_run':result.testsRun,
        'scope':'stdlib fakes and checkpoint header only; no native CPU/GPU imports or execution, no endpoint calls',
        'native_imports':False,'source_sha256s':{str(p):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [TARGET,HERE/'host_embedding_transition_memory.py',Path(__file__)]}}))
    raise SystemExit(0 if result.wasSuccessful() else 1)

"""Inactive actual tiny-CPU CLIP lifecycle proof; guarded driver import only.

Nonencoder factory imports and host memory observations are explicit fakes.
CLIP, candidate ownership, ModelPatcher loading and registry cleanup are actual.
"""
from contextlib import contextmanager, ExitStack
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

LANE=Path(__file__).resolve().parents[1]

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m

base=load('qualified_actual_clip_integration',LANE/'scripts/test-host-embedding-integration-cpu-fixture.py')
torch,mm=base.torch,base.mm
memory=load('host_embedding_transition_memory',LANE/'scripts/host_embedding_transition_memory.py')
EVIDENCE=[]

class Box:
    def __init__(self,**kwargs):self.__dict__.update(kwargs)


class Assembly:
    def __init__(self,root):
        self.root=Path(root);self.constructed=0;self.nonencoder_calls=[]
        self.available=128*1024**3;self.weak_clips=[]
        self.identity={'model_verification_sha256':'273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f',
                       'server_identity_sha256':'CPU-fixture-no-server'}
    def tiny_clip(self,**kwargs):
        if kwargs['model_options'] != {'load_device':torch.device('xpu:2'),'offload_device':torch.device('cpu')}:
            raise RuntimeError('Resident factory logical device contract changed')
        # Physical CPU execution is deliberate fixture injection. The prior
        # qualified factory test separately covers original initial-CPU options.
        clip=base.adapted(kwargs['mode'])
        self.constructed+=1;self.weak_clips.append(weakref.ref(clip));return clip
    def unet(self,*args):
        self.nonencoder_calls.append('diffusion')
        return (Box(load_device=torch.device('cpu'),model=Box()),)
    def vae(self,**kwargs):
        self.nonencoder_calls.append('vae')
        return Box(device=torch.device('cpu'),throw_exception_if_invalid=lambda:None)
    def upscaler(self,*args):
        self.nonencoder_calls.append('upscaler');return (Box(),)
    def shard(self,model,**kwargs):
        self.nonencoder_calls.append('shard');shard=Box(model=Box())
        model.get_additional_models_with_key=lambda key:[shard]
        model.ltx_layer_shard_report={'fixture':'nonencoder metadata only'};return model
    def admit(self,stage,allocation):
        return memory.admission(stage,allocation,snapshot={'source':'synthetic fixture MemAvailable; no large allocation',
                                                          'bytes':{'MemAvailable':self.available}})
    def exclusive(self,path,value,root):
        with Path(path).open('x') as f:json.dump(value,f)


@contextmanager
def assembly(name):
    with tempfile.TemporaryDirectory(prefix='host-resident-cpu-') as root, ExitStack() as stack:
        a=Assembly(root)
        # Stub only nonencoder construction modules; actual Comfy CLIP and memory
        # manager stay installed and untouched throughout all loader operations.
        stubs={n:types.ModuleType(n) for n in ('nodes','comfy_extras','comfy_extras.nodes_hunyuan','ltx_layer_shard')}
        stubs['comfy_extras'].__path__=[]
        stubs['nodes'].UNETLoader=lambda:Box(load_unet=a.unet)
        stubs['comfy_extras.nodes_hunyuan'].LatentUpscaleModelLoader=Box(execute=a.upscaler)
        stubs['ltx_layer_shard'].apply_layer_shard=a.shard
        stack.enter_context(patch.dict(sys.modules,stubs))
        module_name='resident_actual_cpu_'+name
        resident=load(module_name,LANE/'scripts/host_embedding_resident_node_v2.py')
        stack.enter_context(patch.object(resident,'load_clip',a.tiny_clip))
        stack.enter_context(patch.object(resident,'_context',lambda root:(a.root,dict(a.identity))))
        stack.enter_context(patch.object(resident,'ROOT',a.root))
        stack.enter_context(patch.object(resident,'_exclusive_json',a.exclusive))
        stack.enter_context(patch.object(resident,'checkpoint_geometry',lambda path:{
            'construction_overlap_bytes':memory.CHECKPOINT_TENSOR_BYTES+memory.REGISTERED_STATE_BYTES,
            'fixture_geometry_only':True}))
        stack.enter_context(patch.object(resident,'admission',a.admit))
        stack.enter_context(patch.object(resident.folder_paths,'get_full_path_or_raise',lambda *args:'fixture-no-weights'))
        stack.enter_context(patch.object(resident.folder_paths,'get_folder_paths',lambda *args:[]))
        stack.enter_context(patch.object(resident.comfy.sd,'VAE',a.vae))
        stack.enter_context(patch.object(resident.comfy.utils,'load_torch_file',lambda *args,**kwargs:({},{})))
        # A regression to device-wide unload is a hard test error. The actual
        # native CPU loader and cleanup_models/loaded_models are NOT mocked.
        stack.enter_context(patch.object(mm,'unload_all_models',side_effect=AssertionError('No bulk unload allowed')))
        try:
            with torch.inference_mode():
                yield a,resident,resident.LTXHostEmbeddingComponents()
        finally:
            EVIDENCE.append({'case':name,'constructed_clips':a.constructed,'nonencoder_calls':a.nonencoder_calls,
                'receipts':{p.name:json.loads(p.read_text()) for p in sorted(a.root.glob('*.json'))},
                'fixture_scope':'Actual tiny CPU CLIP/model manager; nonencoder objects and memory observations are fakes'})
            # Cleanup belongs to the disposable fixture only. Transition weakref
            # assertions in the node have already run before this scope exits.
            if resident._components is not None and not resident._components[1]._host_embedding.retired:
                resident._components[1]._host_embedding.detach_restore(resident._components[1])
            resident._components=None;resident._pending=[];resident._shared=None
            sys.modules.pop(module_name,None)
            gc.collect();mm.cleanup_models()


def compute(clip):
    actual=clip.encode_from_tokens(base.TOKENS,return_dict=True)['cond']
    raw=base.base.raw(actual)
    clip._host_embedding.consume_observations()
    return (raw,str(actual.dtype),tuple(actual.shape),tuple(actual.stride()))


def registry_ids():
    return {id(p) for p in mm.loaded_models() if p is not None}


class Tests(unittest.TestCase):
    def test_actual_control_host_control_registry_death_and_exactness(self):
        with assembly('roundtrip') as (a,m,node):
            expected=None;shared=None;old_refs=None
            for mode in ('control','host-table','control'):
                outputs=node.load('split',mode)
                clip=outputs[1]
                result=compute(clip)
                if expected is None:expected=result
                self.assertEqual(result,expected)
                ids=m.shared_identity(m._shared)
                if shared is None:shared=ids
                self.assertEqual(ids,shared)
                if old_refs:
                    self.assertTrue(all(ref() is None for ref in old_refs.values()))
                    # Object IDs may be reused after replacement allocation.
                    # The actual node checks native registry removal BEFORE it.
                    release=json.loads((a.root/f'host-components-{m._generation:02d}-{mode}-retired-owner-release.json').read_text())
                    self.assertTrue(release['retired_patcher_ids_absent_from_registry'])
                owned={id(clip.patcher)}
                if clip._host_embedding.owner is not None:
                    owned.add(id(clip._host_embedding.owner.host))
                self.assertTrue(owned <= registry_ids())
                old_refs=m.retirement_refs(clip)
                del clip,outputs
            self.assertEqual(a.constructed,3)
            self.assertEqual(a.nonencoder_calls,['diffusion','vae','vae','upscaler','shard'])
            self.assertEqual(m._generation,3)
            EVIDENCE.append({'case':'roundtrip-byte-oracle','dtype':expected[1],'shape':expected[2],
                'stride':expected[3],'raw_sha256':hashlib.sha256(expected[0]).hexdigest(),
                'scope':'Tiny CPU scaled-embedding/linear output only; no real clip or accelerator parity'})

    def refused_owner(self,kind):
        with assembly('survivor-'+kind) as (a,m,node):
            outputs=node.load('split','host-table');clip=outputs[1];compute(clip)
            if kind=='clone':held=clip.clone()
            elif kind=='model':held=clip.cond_stage_model
            else:held=outputs
            del clip,outputs
            with self.assertRaisesRegex(RuntimeError,'survived'):
                node.load('split','control')
            self.assertEqual(a.constructed,1);self.assertIsNotNone(m._shared);self.assertIsNotNone(m._failure)
            with self.assertRaisesRegex(RuntimeError,'failed'):
                node.load('split','control')
            del held
            gc.collect();mm.cleanup_models()

    def test_external_actual_clone_refuses_replacement(self):self.refused_owner('clone')
    def test_external_actual_model_refuses_replacement(self):self.refused_owner('model')
    def test_external_output_tuple_refuses_replacement(self):self.refused_owner('tuple')

    def test_restore_memory_refusal_before_retirement(self):
        with assembly('restore-budget') as (a,m,node):
            outputs=node.load('split','control');clip=outputs[1];compute(clip)
            a.available=memory.EXISTING_HEADROOM_BYTES-1
            with self.assertRaisesRegex(RuntimeError,'before-restore'):
                node.load('split','host-table')
            self.assertFalse(clip._host_embedding.retired)
            self.assertEqual(a.constructed,1);self.assertIs(m._components,outputs)
            self.assertFalse(list(a.root.glob('*-unload.json')))
            del clip,outputs

    def test_construction_memory_refusal_after_actual_owner_death(self):
        with assembly('construction-budget') as (a,m,node):
            outputs=node.load('split','host-table');clip=outputs[1];compute(clip)
            refs=m.retirement_refs(clip)
            ids={id(clip.patcher),id(clip._host_embedding.owner.host)}
            del clip,outputs
            a.available=memory.EXISTING_HEADROOM_BYTES+memory.REGISTERED_STATE_BYTES
            with self.assertRaisesRegex(RuntimeError,'before-construction'):
                node.load('split','control')
            self.assertTrue(all(ref() is None for ref in refs.values()))
            self.assertFalse(ids & registry_ids());self.assertEqual(a.constructed,1)
            self.assertIsNotNone(m._shared);self.assertIsNone(m._components)


TEST_NAMES=sorted(name for name in vars(Tests) if name.startswith('test_'))

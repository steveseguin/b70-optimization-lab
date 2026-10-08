"""Small compiled source fixtures; no Torch, models, GPU or raw captures."""
import hashlib
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import threading
import types
import unittest

from native_bindings import NativeBindings


class Dtype:
    def __init__(self, name): self.name=name
    def __str__(self): return self.name


class Tensor:
    def __init__(self, torch, *, pointer=100, raw=b'\0'*8, shape=(1,384,640,3)):
        self.dtype,self.layout=torch.float32,torch.strided
        self.device,self.shape='cpu',shape
        self.pointer,self.raw,self.contiguous=pointer,raw,True
    def is_contiguous(self): return self.contiguous
    def untyped_storage(self): return types.SimpleNamespace(data_ptr=lambda:self.pointer)
    def detach(self): return self
    def numpy(self): return self
    def tobytes(self, *, order):
        assert order=='C'
        return self.raw


class BindingTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.packet=Path(self.temp.name);self.manifest={'files':{}}
        self.torch=types.SimpleNamespace(float32=Dtype('torch.float32'),
            bfloat16=Dtype('torch.bfloat16'),strided=object(),Tensor=Tensor)
        self.torch.get_default_dtype=lambda:self.torch.float32
        self.mm=types.SimpleNamespace(intermediate_device=lambda:'cpu')
        self.output=self.module('source/comfy_api/latest/_io.py', '''
class NodeOutput:
    def __init__(self,*args,ui=None,expand=None,block_execution=None):
        self.args,self.ui,self.expand,self.block_execution=args,ui,expand,block_execution
    @property
    def result(self): return self.args if self.args else None
''')
        self.encoder_module=self.module('source/comfy/ldm/lightricks/vae/causal_video_autoencoder.py', '''
class Encoder:
    def __init__(self): self.modules=[]
    def forward(self,*args,**kwargs): return None
    def named_modules(self): return iter(self.modules)
''')
        self.vae_module=self.module('source/comfy/sd.py','''
class VAE:
    def encode(self,pixels): return pixels
    def decode(self,latent): return latent
    def vae_output_dtype(self): return torch.float32
''',torch=self.torch)
        self.native=self.module('source/comfy_extras/nodes_lt.py','''
class LTXVImgToVideoInplace:
    @classmethod
    def execute(cls,vae,image,latent,strength,bypass=False):
        calls.append(dict(vae=vae,image=image,latent=latent,strength=strength,bypass=bypass))
        return io.NodeOutput(latent)
''',torch=self.torch,io=self.output,calls=[])
        self.anchor=self.module('source/scripts/continuation_anchor.py','''
import struct
FRAME_BYTES=8
def finite_bytes(raw):
    if len(raw)%4: raise ValueError('unaligned')
    if any((x[0]&0x7f800000)==0x7f800000 for x in struct.iter_unpack('<I',raw)):
        raise ValueError('nonfinite')
''')
        self.guard=self.module('source/scripts/conditioning_guard.py','''
class ConditioningStageGuard: pass
''')
        self.safety=self.module('source/scripts/native_safety.py','''
class NativeReferenceSafety: pass
''')
        self.video=self.vae_module.VAE()
        self.encoder=self.encoder_module.Encoder()
        self.video.first_stage_model=types.SimpleNamespace(encoder=self.encoder)
        self.video.vae_dtype=self.torch.bfloat16
        self.video.device,self.video.output_device='xpu:3','cpu'
        self.video.disable_offload=True
        self.video.downscale_index_formula=(8,32,32)
        self.controller=self.safety.NativeReferenceSafety()
        self.video._ltx_native_reference_safety=self.controller
        self.adapter=types.SimpleNamespace(objects={'video_vae':self.video},controller=self.controller)
        self.nodes=types.SimpleNamespace(NODE_CLASS_MAPPINGS={
            'LTXVImgToVideoInplace':self.native.LTXVImgToVideoInplace})
        self.b=self.construct()

    def module(self, relative, source, **globals):
        path=self.packet/relative;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(source)
        self.manifest['files'][relative]=hashlib.sha256(path.read_bytes()).hexdigest()
        name='binding_fixture_'+str(id(self))+'_'+str(len(self.manifest['files']))
        module=types.ModuleType(name);module.__file__=str(path)
        module.__dict__.update(globals);sys.modules[name]=module
        self.addCleanup(sys.modules.pop,name,None)
        exec(compile(source,str(path),'exec'),module.__dict__)
        return module

    def construct(self, **updates):
        kwargs=dict(packet=self.packet,manifest=self.manifest,torch=self.torch,nodes=self.nodes,
                    model_management=self.mm,adapter=self.adapter,anchor_module=self.anchor,
                    guard_module=self.guard,output_type=self.output.NodeOutput)
        kwargs.update(updates)
        return NativeBindings(**kwargs)

    def test_source_bound_native_call_preserves_exact_objects_and_result(self):
        image=Tensor(self.torch);latent={'samples':Tensor(self.torch,pointer=200)}
        result=self.b.native_call(vae=self.video,image=image,latent=latent,strength=1.,bypass=False)
        self.assertIs(type(result),self.output.NodeOutput)
        self.assertIs(self.b.unwrap_output(result),latent)
        self.assertEqual(len(self.native.calls),1)
        for key,value in [('vae',self.video),('image',image),('latent',latent)]:
            self.assertIs(self.native.calls[0][key],value)
        self.assertEqual(len(self.b.receipt()['sources']),7)

    def test_native_registration_and_function_replacement_refused(self):
        self.nodes.NODE_CLASS_MAPPINGS['LTXVImgToVideoInplace']=object
        with self.assertRaises(RuntimeError):self.b.check_native()
        self.nodes.NODE_CLASS_MAPPINGS['LTXVImgToVideoInplace']=self.b.cls
        self.b.cls.execute=classmethod(lambda cls,**kwargs:None)
        with self.assertRaises(RuntimeError):self.b.check_native()

    def test_native_code_and_globals_rebinding_refused(self):
        original=self.b.function.__code__
        replacement=compile('def other(cls,vae,image,latent,strength,bypass=False): return None',
                            original.co_filename,'exec')
        scope={};exec(replacement,scope)
        self.b.function.__code__=scope['other'].__code__
        with self.assertRaises(RuntimeError):self.b.check_native()
        self.b.function.__code__=original
        self.native.torch=object()
        with self.assertRaises(RuntimeError):self.b.check_native()

    def test_source_drift_manifest_omission_and_symlink_refused(self):
        relative='source/comfy_extras/nodes_lt.py';path=self.packet/relative
        raw=path.read_bytes();path.write_bytes(raw+b'\n# drift\n')
        with self.assertRaises(RuntimeError):self.b.check_native()
        path.write_bytes(raw);pin=self.manifest['files'].pop(relative)
        with self.assertRaises(RuntimeError):self.b.check_native()
        self.manifest['files'][relative]=pin
        other=self.packet/'same-bytes';other.write_bytes(raw);path.unlink();path.symlink_to(other)
        with self.assertRaises(RuntimeError):self.b.check_native()

    def test_vae_encoder_and_controller_owner_replacement_refused(self):
        self.video.first_stage_model.encoder=object()
        with self.assertRaises(RuntimeError):self.b.check_native()
        self.video.first_stage_model.encoder=self.encoder
        self.video._ltx_native_reference_safety=object()
        with self.assertRaises(RuntimeError):self.b.check_native()
        self.video._ltx_native_reference_safety=self.controller
        self.adapter.objects['video_vae']=object()
        with self.assertRaises(RuntimeError):self.b.check_native()

    def test_settings_refuse_dtype_device_offload_and_geometry_drift(self):
        for name,value in [('vae_dtype',self.torch.float32),('device','xpu:2'),
                           ('output_device','xpu:0'),('disable_offload',False),
                           ('downscale_index_formula',(8,16,32))]:
            with self.subTest(name=name):
                old=getattr(self.video,name);setattr(self.video,name,value)
                with self.assertRaises(RuntimeError):self.b.settings()
                setattr(self.video,name,old)
        self.mm.intermediate_device=lambda:'xpu:0'
        with self.assertRaises(RuntimeError):self.b.settings()
        self.mm.intermediate_device=lambda:'cpu'
        self.torch.get_default_dtype=lambda:self.torch.bfloat16
        with self.assertRaises(RuntimeError):self.b.settings()

    def test_metadata_rejects_wrong_tensor_dtype_device_layout_contiguity(self):
        for name,value in [('dtype',self.torch.bfloat16),('device','xpu:0'),
                           ('layout',object()),('contiguous',False)]:
            tensor=Tensor(self.torch);setattr(tensor,name,value)
            with self.subTest(name=name),self.assertRaises(RuntimeError):self.b.tensor_metadata(tensor)
        with self.assertRaises(RuntimeError):self.b.tensor_metadata(object())

    def test_alias_metadata_exposes_storage_identity_without_copy(self):
        first=Tensor(self.torch,pointer=100);alias=Tensor(self.torch,pointer=100)
        a=self.b.tensor_metadata(first);b=self.b.tensor_metadata(alias)
        self.assertNotEqual(a['object_id'],b['object_id'])
        self.assertEqual(a['storage_id'],b['storage_id'])
        self.assertEqual(a['shape'],[1,384,640,3])

    def test_anchor_hash_preserves_signed_zero_and_rejects_nonfinite_or_shape(self):
        raw=struct.pack('<II',0x80000000,0)
        result=self.b.inspect_anchor(Tensor(self.torch,raw=raw))
        self.assertEqual(result,{'sha256':hashlib.sha256(raw).hexdigest(),'finite':True})
        for bits in (0x7f800000,0x7fc00000,0xff800000):
            with self.subTest(bits=bits),self.assertRaises(ValueError):
                self.b.inspect_anchor(Tensor(self.torch,raw=struct.pack('<II',bits,0)))
        with self.assertRaises(RuntimeError):self.b.inspect_anchor(Tensor(self.torch,shape=(1,8,8,3)))
        with self.assertRaises(RuntimeError):self.b.inspect_anchor(Tensor(self.torch,raw=b'\0'*4))

    def test_encoder_cache_counts_all_own_and_foreign_entries(self):
        tid=threading.get_ident()
        self.encoder.modules=[('',self.encoder),('a',types.SimpleNamespace(temporal_cache_state={tid:None})),
            ('b',types.SimpleNamespace(temporal_cache_state={tid:(),tid+1:()})),
            ('other',types.SimpleNamespace(no_cache=True))]
        result=self.b.inspect_encoder_cache(self.encoder,tid)
        self.assertEqual(result['entry_count'],2)
        self.assertEqual(result['foreign_entry_count'],1)
        self.assertEqual(result['encoder_id'],id(self.encoder))
        self.assertEqual(result['source_sha256'],self.manifest['files'][
            'source/comfy/ldm/lightricks/vae/causal_video_autoencoder.py'])
        with self.assertRaises(RuntimeError):self.b.inspect_encoder_cache(self.encoder,tid+1)
        with self.assertRaises(RuntimeError):self.b.inspect_encoder_cache(object(),tid)
        self.encoder.modules=[('bad',types.SimpleNamespace(temporal_cache_state=[]))]
        with self.assertRaises(RuntimeError):self.b.inspect_encoder_cache(self.encoder,tid)

    def test_output_unwrap_refuses_side_channels_type_and_arity(self):
        O=self.output.NodeOutput
        for value in [({},),{},O(),O({},{}),O({},ui={}),O({},expand={}),O({},block_execution='x')]:
            with self.subTest(value=type(value)),self.assertRaises(RuntimeError):self.b.unwrap_output(value)
        class Sub(O):pass
        with self.assertRaises(RuntimeError):self.b.unwrap_output(Sub({}))

    def test_encoder_forward_code_replacement_refused(self):
        old=self.b.encoder_function.__code__
        scope={};exec(compile('def replacement(self,*args,**kwargs): return 9',old.co_filename,'exec'),scope)
        self.b.encoder_function.__code__=scope['replacement'].__code__
        with self.assertRaises(RuntimeError):self.b.check_native()


if __name__=='__main__':unittest.main()

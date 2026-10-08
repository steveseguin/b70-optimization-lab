"""Trusted111 native conditioning bindings; inert until explicit runtime setup.

No imports of Torch/Comfy, device discovery, conversion or source mutation here.
The sealed runtime supplies loaded modules and the admitted native adapter.
"""
import hashlib
import inspect
from pathlib import Path
import sys
import threading


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


class NativeBindings:
    def __init__(self, *, packet, manifest, torch, nodes, model_management,
                 adapter, anchor_module, guard_module, output_type):
        self.packet, self.manifest = Path(packet), manifest
        self.torch, self.nodes, self.mm = torch, nodes, model_management
        self.adapter, self.anchor_module, self.guard_module = adapter, anchor_module, guard_module
        self.output_type = output_type
        self.video = adapter.objects['video_vae']
        self.encoder = self.video.first_stage_model.encoder
        self.cls = nodes.NODE_CLASS_MAPPINGS['LTXVImgToVideoInplace']
        self.method = self.cls.execute
        self.function = self.method.__func__
        self.code = self.function.__code__
        self.encoder_function = self.encoder.forward.__func__
        self.encoder_code = self.encoder_function.__code__
        self.output_init = output_type.__init__
        self.output_result = output_type.result
        self.output_init_code = self.output_init.__code__
        self.output_result_code = self.output_result.fget.__code__
        self.vae_encode = type(self.video).encode
        self.vae_decode = type(self.video).decode
        self.vae_encode_code, self.vae_decode_code = self.vae_encode.__code__, self.vae_decode.__code__
        self.sources = {}
        self.module_bindings = [self.bind_module(anchor_module, 'source/scripts/continuation_anchor.py'),
                                self.bind_module(guard_module, 'source/scripts/conditioning_guard.py')]
        self.check_native()
        self.settings()

    def pin(self, relative):
        path = self.packet / relative
        require(self.packet.is_absolute() and not Path(relative).is_absolute() and
                '..' not in path.parts and not any(p.is_symlink() for p in (path, *path.parents)) and
                relative in self.manifest['files'] and path.is_file(),
                'Native binding source absent from manifest: ' + relative)
        raw = path.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        require(actual == self.manifest['files'][relative], 'Native binding source changed: ' + relative)
        self.sources[str(path)] = actual
        return path

    def bind_module(self, module, relative):
        path = self.pin(relative)
        require(sys.modules.get(module.__name__) is module and
                Path(module.__file__).resolve() == path.resolve(), 'Helper module source/owner differs')
        functions, classes = {}, {}
        for name, value in vars(module).items():
            if inspect.isfunction(value) and value.__globals__ is vars(module):
                functions[name] = (value, value.__code__)
            elif inspect.isclass(value) and value.__module__ == module.__name__:
                require(Path(inspect.getsourcefile(value)).resolve() == path.resolve(),
                        'Helper class source differs')
                methods = {}
                for key, descriptor in vars(value).items():
                    fn = descriptor.__func__ if isinstance(descriptor, (staticmethod, classmethod)) else descriptor
                    if inspect.isfunction(fn):
                        methods[key] = (descriptor, fn, fn.__code__)
                classes[name] = (value, methods)
        require(functions or classes, 'Helper module has no owned code')
        return module, relative, functions, classes

    def check_module(self, binding):
        module, relative, functions, classes = binding
        path = self.pin(relative)
        require(sys.modules.get(module.__name__) is module and
                Path(module.__file__).resolve() == path.resolve(), 'Helper module owner changed')
        for name, (fn, code) in functions.items():
            require(getattr(module, name, None) is fn and fn.__code__ is code and
                    fn.__globals__ is vars(module) and Path(code.co_filename).resolve() == path.resolve(),
                    'Helper function source/code/owner changed: ' + name)
        for name, (cls, methods) in classes.items():
            require(getattr(module, name, None) is cls and cls.__module__ == module.__name__,
                    'Helper class owner changed: ' + name)
            actual = {key for key, value in vars(cls).items()
                      if inspect.isfunction(value) or isinstance(value, (staticmethod, classmethod))}
            require(actual == set(methods), 'Helper class method set changed: ' + name)
            for key, (descriptor, fn, code) in methods.items():
                require(vars(cls).get(key) is descriptor and fn.__code__ is code and
                        fn.__globals__ is vars(module) and Path(code.co_filename).resolve() == path.resolve(),
                        'Helper class method changed: ' + name + '.' + key)

    def check_native(self):
        require(self.nodes.NODE_CLASS_MAPPINGS.get('LTXVImgToVideoInplace') is self.cls and
                self.cls.execute.__func__ is self.function and self.function.__code__ is self.code,
                'Native conditioner registration/method changed')
        path = self.pin('source/comfy_extras/nodes_lt.py')
        require(Path(self.code.co_filename).resolve() == path.resolve() and
                self.function.__globals__.get('LTXVImgToVideoInplace') is self.cls and
                self.function.__globals__.get('torch') is self.torch and
                getattr(self.function.__globals__.get('io'), 'NodeOutput', None) is self.output_type,
                'Native V3 conditioner defining module changed')
        require(list(inspect.signature(self.method).parameters) ==
                ['vae', 'image', 'latent', 'strength', 'bypass'], 'Native conditioner API changed')
        encoder_path = self.pin('source/comfy/ldm/lightricks/vae/causal_video_autoencoder.py')
        require(self.video is self.adapter.objects['video_vae'] and
                self.encoder is self.video.first_stage_model.encoder and
                self.encoder.forward.__func__ is self.encoder_function and
                self.encoder_function.__code__ is self.encoder_code and
                Path(self.encoder_code.co_filename).resolve() == encoder_path.resolve(),
                'Native encoder owner/source/method changed')
        output_path = self.pin('source/comfy_api/latest/_io.py')
        require(self.output_type.__init__ is self.output_init and
                self.output_type.result is self.output_result and
                self.output_init.__code__ is self.output_init_code and
                self.output_result.fget.__code__ is self.output_result_code and
                Path(self.output_init_code.co_filename).resolve() == output_path.resolve() and
                Path(self.output_result_code.co_filename).resolve() == output_path.resolve() and
                self.output_init.__globals__.get('NodeOutput') is self.output_type and
                self.output_result.fget.__globals__ is self.output_init.__globals__,
                'NodeOutput implementation changed')
        vae_path = self.pin('source/comfy/sd.py')
        require(type(self.video).encode is self.vae_encode and type(self.video).decode is self.vae_decode and
                getattr(self.video.encode, '__func__', None) is self.vae_encode and
                getattr(self.video.decode, '__func__', None) is self.vae_decode and
                self.vae_encode.__code__ is self.vae_encode_code and
                self.vae_decode.__code__ is self.vae_decode_code and
                Path(self.vae_encode_code.co_filename).resolve() == vae_path.resolve() and
                Path(self.vae_decode_code.co_filename).resolve() == vae_path.resolve(),
                'VAE implementation changed')
        for relative in ('source/scripts/native_safety.py', 'source/scripts/conditioning_guard.py',
                         'source/scripts/continuation_anchor.py'):
            self.pin(relative)
        for binding in self.module_bindings:
            self.check_module(binding)
        require(getattr(self.video, '_ltx_native_reference_safety', None) is self.adapter.controller,
                'Native encoding has no admitted safety owner')

    def settings(self):
        t, vae = self.torch, self.video
        require(t.get_default_dtype() is t.float32 and str(self.mm.intermediate_device()) == 'cpu',
                'Native default dtype/intermediate policy differs')
        require(vae.vae_dtype is t.bfloat16 and vae.vae_output_dtype() is t.float32 and
                str(vae.device) == 'xpu:3' and str(vae.output_device) == 'cpu' and
                vae.disable_offload is True and tuple(vae.downscale_index_formula)[1:] == (32, 32),
                'Native VAE dtype/device/residency/scaling policy differs')
        return {'torch_default_dtype': str(t.get_default_dtype()),
                'intermediate_device': str(self.mm.intermediate_device()),
                'vae_model_dtype': str(vae.vae_dtype), 'vae_output_dtype': str(vae.vae_output_dtype())}

    def tensor_metadata(self, tensor):
        t = self.torch
        require(isinstance(tensor, t.Tensor) and tensor.dtype is t.float32 and
                str(tensor.device) == 'cpu' and tensor.layout is t.strided and
                tensor.is_contiguous(), 'Expected native contiguous CPU F32 tensor')
        return {'object_id': id(tensor), 'storage_id': int(tensor.untyped_storage().data_ptr()),
                'shape': list(tensor.shape), 'dtype': str(tensor.dtype),
                'device': str(tensor.device), 'contiguous': True}

    def inspect_anchor(self, image):
        self.check_native()
        meta = self.tensor_metadata(image)
        require(meta['shape'] == [1, 384, 640, 3], 'Anchor geometry changed')
        raw = image.detach().numpy().tobytes(order='C')
        require(len(raw) == self.anchor_module.FRAME_BYTES, 'Anchor byte length changed')
        self.anchor_module.finite_bytes(raw)
        return {'sha256': hashlib.sha256(raw).hexdigest(), 'finite': True}

    def inspect_encoder_cache(self, encoder, thread_ident):
        self.check_native()
        require(encoder is self.encoder and thread_ident == threading.get_ident(),
                'Encoder cache inspection owner/thread differs')
        own = foreign = 0
        for _, module in encoder.named_modules():
            if not hasattr(module, 'temporal_cache_state'):
                continue
            state = module.temporal_cache_state
            require(type(state) is dict, 'Unexpected encoder temporal cache representation')
            own += int(thread_ident in state)
            foreign += sum(key != thread_ident for key in state)
        path = str(self.packet/'source/comfy/ldm/lightricks/vae/causal_video_autoencoder.py')
        return {'source_sha256': self.sources[path], 'encoder_id': id(encoder),
                'thread_ident': thread_ident, 'entry_count': own, 'foreign_entry_count': foreign}

    def unwrap_output(self, result):
        self.check_native()
        require(type(result) is self.output_type and result.ui is None and result.expand is None and
                result.block_execution is None and type(result.result) is tuple and len(result.result) == 1,
                'Native conditioner must return its unchanged one-result NodeOutput')
        return result.result[0]

    def native_call(self, **kwargs):
        self.check_native()
        self.settings()
        return self.method(**kwargs)

    def receipt(self):
        self.check_native()
        return {'method': 'LTXVImgToVideoInplace.execute', 'sources': dict(self.sources)}

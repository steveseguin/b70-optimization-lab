"""Trusted111 native conditioning bindings; inert until explicit runtime setup.

No imports of Torch/Comfy, device discovery, conversion or source mutation here.
The sealed runtime supplies loaded modules and the admitted native adapter.
"""
import hashlib
import inspect
from pathlib import Path
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
        self.vae_encode = type(self.video).encode
        self.vae_decode = type(self.video).decode
        self.sources = {}
        self.check_native()
        self.settings()

    def pin(self, relative):
        path = self.packet / relative
        require(relative in self.manifest['files'] and path.is_file() and not path.is_symlink(),
                'Native binding source absent from manifest: ' + relative)
        raw = path.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        require(actual == self.manifest['files'][relative], 'Native binding source changed: ' + relative)
        self.sources[str(path)] = actual
        return path

    def check_native(self):
        require(self.nodes.NODE_CLASS_MAPPINGS.get('LTXVImgToVideoInplace') is self.cls and
                self.cls.execute.__func__ is self.function and self.function.__code__ is self.code,
                'Native conditioner registration/method changed')
        path = self.pin('source/comfy_extras/nodes_lt.py')
        require(Path(self.code.co_filename).resolve() == path.resolve() and
                self.function.__globals__.get('LTXVImgToVideoInplace') is self.cls and
                self.function.__globals__.get('torch') is self.torch,
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
                Path(self.output_init.__code__.co_filename).resolve() == output_path.resolve(),
                'NodeOutput implementation changed')
        vae_path = self.pin('source/comfy/sd.py')
        require(type(self.video).encode is self.vae_encode and type(self.video).decode is self.vae_decode and
                Path(self.vae_encode.__code__.co_filename).resolve() == vae_path.resolve() and
                Path(self.vae_decode.__code__.co_filename).resolve() == vae_path.resolve(),
                'VAE implementation changed')
        for relative in ('source/scripts/native_safety.py', 'source/scripts/conditioning_guard.py',
                         'source/scripts/continuation_anchor.py'):
            self.pin(relative)
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

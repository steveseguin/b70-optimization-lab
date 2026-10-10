"""Packet123 decoder-only resident replica. No imports initialize a device.

The independent decoder is copied BEFORE graph/cone shadows are installed. Each
tensor is copied directly to the destination; deepcopy's memo prevents a second
temporary decoder on xpu:3. The encoder is deliberately absent. Native decode,
seed-zero noise, dtype, CPU output copy and in-place output normalization stay
unchanged. Same-card CPU tests are not cross-card numerical proof: all nine
qualification decodes compare complete images and every live cone checks its
anchor against this display. Any error latches, with no fallback.
"""
import copy
import hashlib
import os
import time

GIB = 2 ** 30
FLOOR_BYTES = 2 * GIB
# Packet118b receipt peak-over-idle envelope 2,404,414,464 bytes; 4 GiB
# admission reserve adds >1 GiB. It is conservative evidence, not a proven peak.
TRANSIENT_BYTES = 4 * GIB
LATCH_NAME = 'display-replica-120-refused.json'
CHOICES = ('xpu:3', 'xpu:2')


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def launch_device(env=None):
    value = (os.environ if env is None else env).get('LTX_DISPLAY_DEVICE', 'xpu:3')
    require(value in CHOICES, 'LTX_DISPLAY_DEVICE must be xpu:3 or xpu:2')
    return value


def validate_scope(device, frames, anchor, anchor_decode, schedule):
    require(device in CHOICES, 'Invalid display device')
    require(device == 'xpu:3' or (frames in (121, 145, 169) and anchor == 'frame' and anchor_decode == 'cone'
                                and schedule == 'eager-display'),
            'xpu:2 display requires the selected-length frame/cone/eager-display scope')


def transient_bytes(frames):
    from stream_contract import launch_display_transient_bytes
    return launch_display_transient_bytes(frames)


def budget(free, resident_bytes=0, transient_bytes=TRANSIENT_BYTES, screening_bytes=0):
    require(type(free) is int and type(resident_bytes) is int and type(transient_bytes) is int
            and min(free, resident_bytes, transient_bytes) >= 0, 'Invalid display memory census')
    require(type(screening_bytes) is int and screening_bytes >= 0, 'Invalid screening margin')
    minimum = resident_bytes + transient_bytes + FLOOR_BYTES
    require(free >= minimum + screening_bytes,
            'Display replica refuses: free %d < resident %d + transient %d + 2 GiB floor'
            % (free, resident_bytes, transient_bytes))
    return {'free_bytes': free, 'new_resident_bytes': resident_bytes, 'transient_budget_bytes': transient_bytes,
            'floor_bytes': FLOOR_BYTES, 'margin_bytes': free - minimum}


def tensors(model):
    return list(model.named_parameters()) + list(model.named_buffers())


def facts(model):
    return tuple((name, id(t), str(t.device), str(t.dtype), tuple(t.shape), tuple(t.stride()), t.storage_offset(), t.data_ptr(), t._version)
                 for name, t in tensors(model))


def clone_decoder_only(torch, source, device):
    """CPU-testable copy primitive. Destination is validated by ResidentDisplay."""
    # Comfy's executor prepares inside inference_mode. Our private resident
    # weights require version counters for the immutable-residency guard.
    with torch.inference_mode(False), torch.no_grad():
        return _clone_decoder_only(torch, source, device)


def _clone_decoder_only(torch, source, device):
    require(set(source._modules) == {'encoder', 'decoder', 'per_channel_statistics'},
            'Unexpected native VAE children; cannot exclude encoder safely')
    for name in ('forward', 'forward_pre_diffusion', 'forward_diff_step'):
        require(name not in source.decoder.__dict__, 'Copy must precede decoder graph/cone wrappers: ' + name)
    for root in (source, source.decoder, source.per_channel_statistics):
        for name, value in vars(root).items():
            require(not isinstance(value, torch.Tensor), 'Unregistered tensor in display source: ' + name)
    for part in (source.decoder, source.per_channel_statistics):
        for module in part.modules():
            for name, value in vars(module).items():
                require(not isinstance(value, torch.Tensor), 'Unregistered decoder tensor: ' + name)
    memo = {id(source.encoder): None}
    parts = (source.decoder, source.per_channel_statistics)
    for part in parts:
        for _, tensor in tensors(part):
            if id(tensor) not in memo:
                copied = tensor.detach().to(device=device, copy=True)
                if isinstance(tensor, torch.nn.Parameter):
                    copied = torch.nn.Parameter(copied, requires_grad=tensor.requires_grad)
                memo[id(tensor)] = copied
    replica = copy.deepcopy(source, memo)
    require(replica.encoder is None, 'Replica unexpectedly owns an encoder')
    old = dict(tensors(source.decoder) + [('statistics.' + n, t) for n, t in tensors(source.per_channel_statistics)])
    new = dict(tensors(replica.decoder) + [('statistics.' + n, t) for n, t in tensors(replica.per_channel_statistics)])
    require(old.keys() == new.keys(), 'Replica parameter census differs')
    for name, tensor in old.items():
        target = new[name]
        require(target is not tensor and str(target.device) == str(device) and target.dtype == tensor.dtype
                and tuple(target.shape) == tuple(tensor.shape), 'Replica residency/dtype differs: ' + name)
        require(torch.equal(tensor.detach().to('cpu').contiguous().view(torch.uint8),
                            target.detach().to('cpu').contiguous().view(torch.uint8)),
                'Replica copied weight bytes differ: ' + name)
    return replica


class ResidentDisplay:
    def __init__(self, torch, vae, frames, free_bytes, latch):
        self.torch, self.native, self.free_bytes, self.latch = torch, vae, free_bytes, latch
        self.device, self.frames = 'xpu:2', frames
        require(frames in (121, 145, 169), 'Replica transient reservation covers 121/145 frames')
        require(type(vae.first_stage_model).__name__ == 'CausalDiffusionVAE', 'Unsupported display VAE')
        require(vae.vae_dtype is torch.bfloat16 and vae.vae_output_dtype() is torch.float32
                and str(vae.output_device) == 'cpu' and str(vae.device) == 'xpu:3'
                and vae.latent_dim == 3 and vae.disable_offload is True,
                'Native display policy differs')
        source = vae.first_stage_model
        self.resident_bytes = sum(t.numel() * t.element_size() for part in
                                  (source.decoder, source.per_channel_statistics) for _, t in tensors(part))
        self.transient_bytes = transient_bytes(frames)
        self.screening_bytes = 3 * GIB // 4 if frames >= 145 else 0
        self.before = budget(free_bytes(), self.resident_bytes, self.transient_bytes, self.screening_bytes)
        self.model = clone_decoder_only(torch, source, self.device)
        torch.xpu.synchronize(self.device)
        self.baseline = facts(self.model)
        self.after = budget(free_bytes(), transient_bytes=self.transient_bytes, screening_bytes=self.screening_bytes)
        self.calls = 0
        self.last_memory = None

    def counters(self):
        xpu = self.torch.xpu
        return {'allocated': int(xpu.memory_allocated(self.device)),
                'reserved': int(xpu.memory_reserved(self.device)),
                'peak_allocated': int(xpu.max_memory_allocated(self.device))}

    def check(self):
        require(facts(self.model) == self.baseline, 'Display replica residency/weights changed')
        require(self.model.encoder is None, 'Replica acquired an encoder')

    def decode(self, latent):
        """Native sd.VAE.decode untiled batch-one arithmetic, with residency already owned.

        Does not enter model_management: the replica cannot evict or move any
        admitted model. Its bytes and physical free memory are checked directly.
        There is no OOM retry, tiling, graph, noise cache or asynchronous thread.
        """
        t, vae = self.torch, self.native
        self.check()
        require(tuple(latent.shape) == (1, 128, (self.frames - 1) // 8 + 1, 8, 8),
                'Display replica requires the selected-length batch-one latent')
        before = budget(self.free_bytes(), transient_bytes=self.transient_bytes, screening_bytes=self.screening_bytes)
        allocator_before = self.counters()
        started = time.time_ns()
        with t.inference_mode(), t.xpu.device(self.device):
            samples = latent.to(device=self.device, dtype=vae.vae_dtype)
            out = self.model.decode(samples).to(device=vae.output_device, dtype=vae.vae_output_dtype(), copy=True)
            pixels = t.empty((latent.shape[0],) + tuple(out.shape[1:]),
                             device=vae.output_device, dtype=vae.vae_output_dtype())
            pixels[0:1].copy_(out)
            del out, samples
            vae.process_output(pixels[0:1])
            images = pixels.to(vae.output_device).movedim(1, -1)
            images = images.reshape(-1, images.shape[-3], images.shape[-2], images.shape[-1])
        after = self.free_bytes()
        require(type(after) is int and after >= FLOOR_BYTES + self.screening_bytes, 'Display replica crossed the 2 GiB floor')
        allocator_after = self.counters()
        # No reset of device-global allocator statistics beside another owner.
        # A historical high peak can conservatively refuse this arm; it cannot
        # conceal a newly observed high peak. Retained reservation is checked too.
        observed = max(0, allocator_after['peak_allocated'] - allocator_before['allocated'],
                       allocator_after['reserved'] - allocator_before['reserved'])
        require(observed <= self.transient_bytes, 'Display replica exceeded its length-scaled observed transient allowance')
        self.check()
        self.calls += 1
        self.last_memory = {'before': before, 'after_free_bytes': after, 'seconds': (time.time_ns()-started)/1e9,
                            'allocator_before': allocator_before, 'allocator_after': allocator_after,
                            'observed_peak_or_reservation_growth_bytes': observed,
                            'peak_is_device_global_not_reset': True}
        return images

    def receipt(self):
        return {'device': self.device, 'resident_bytes': self.resident_bytes, 'encoder_bytes': 0,
                'graph_pool_bytes': 0, 'transient_budget_bytes': self.transient_bytes, 'floor_bytes': FLOOR_BYTES,
                'before_install': self.before, 'after_install': self.after, 'calls': self.calls,
                'last_decode': self.last_memory, 'weight_copy_bitwise_equal': True,
                'native_seed': 0, 'dtype': str(self.native.vae_dtype), 'single_decode_thread': True}


def compare(torch, images, reference):
    def digest(value):
        return hashlib.sha256(value.detach().to('cpu').contiguous().view(torch.uint8).numpy()).hexdigest()
    a, b = digest(images), digest(reference)
    same = images.dtype == reference.dtype and tuple(images.shape) == tuple(reference.shape) and a == b
    return {'device': 'xpu:2', 'reference_device': 'xpu:3', 'mode': 'eager-uncached', 'equal': bool(same),
            'images_sha256': a, 'reference_images_sha256': b}

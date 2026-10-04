"""Packet 91: decode placement and the cross-card decode probe.

Placements, selected per request by the decode node's mode (a graph arm):

- ``pipeline`` / ``pipeline-save`` (control): every clip decodes on the
  resident VAEs on xpu:3 through ComfyUI's native ``VAE.decode``, exactly as
  in packet 90c.
- ``pipeline-replica``: a second decode worker with its own replica of the
  video and audio VAEs on xpu:1 (the transformer-shard card, ~55 % idle in
  f90c). Even clip indices decode natively on xpu:3, odd ones on the
  replica; two decode jobs are in flight and the run-behind collect emits
  them strictly in clip order (``ltx_pipeline.run_behind``).
- ``pipeline-moved``: every clip on the xpu:1 replica, one at a time.

The replica is built by copying every parameter, buffer and plain tensor
attribute of the resident VAE modules to xpu:1 (exact copies, verified with
torch.equal), never through ComfyUI's model management: its
``load_models_gpu(memory_required=...)`` could evict the transformer shard
from xpu:1 to make room. The replica decode therefore mirrors the non-tiled
path of ``comfy.sd.VAE.decode`` (and the reshape/movedim of the VAEDecode
and LTXVAudioVAEDecode nodes) line for line, without the model-management
call; a tiled fallback is not mirrored (an OOM raises instead).

Nothing here is trusted on faith: the replica placements are refused until
``LTXDecodeReplicaProbe`` has decoded the ten fixtures' certified latents on
both cards in this server process and every image and waveform is
byte-identical across the two cards and to the stored references.

Lock order (packet 91b). Every eager replica operation on xpu:1 -- the
construction copy, the probe's replica decodes and every pipelined replica
decode -- holds ``ltx_graph_capture.CAPTURE_LOCK`` in SHARED mode, the mode
the sampler's graph replays use, so a graph capture (exclusive) never
overlaps replica kernels or allocations and vice versa. Acquisition order is
always outer to inner:

    decode node _REPLICA_LOCK  ->  CAPTURE_LOCK (shared)  ->  Replica.lock
    resident fast-path _LOAD_LOCK  ->  CAPTURE_LOCK (shared)   (construction)

No code path holds CAPTURE_LOCK (either mode) while taking _REPLICA_LOCK,
Replica.lock or _LOAD_LOCK (graph captures and replays only synchronise,
fill static buffers and record/replay), so no cycle exists. The decode
thread never captures, so it never requests the exclusive mode while
holding the shared one.

Placement is an explicit allowlist (``ALLOWED_DEVICES``); a replica whose
tensors are not all on its slot's device is refused. The VAE graph gate is
not involved: every packet-91 arm runs it in ``original`` mode, and no
replica decode is graph-captured.
"""
import contextlib
import copy
import hashlib
import threading

import torch

NATIVE_DEVICE = 'xpu:3'
REPLICA_DEVICE = 'xpu:1'
ALLOWED_DEVICES = {'native': NATIVE_DEVICE, 'replica': REPLICA_DEVICE}
PLACEMENTS = {'pipeline': ('native',), 'pipeline-save': ('native',),
              'pipeline-replica': ('native', 'replica'), 'pipeline-moved': ('replica',),
              # Packet 92b: decode in a child process with its own VAEs on xpu:3.
              'pipeline-child': ('child',)}
REPLICA_MODES = ('pipeline-replica', 'pipeline-moved')
# Free device memory required on xpu:1 after the replica weights are placed
# (decode working set on xpu:3 in f90c was at most ~4.8 GiB reserved beyond
# the resident weights) and after the probe's decodes (cached blocks
# included). Below either, the replica is refused rather than risk paging.
MIN_FREE_AFTER_BUILD = 5 * 2**30
MIN_FREE_AFTER_PROBE = 1 * 2**30


def require(value, message):
    if not value:
        raise RuntimeError(message)


@contextlib.contextmanager
def shared(capture_lock):
    """Hold the capture/replay lock in the replay (shared) mode."""
    require(capture_lock is not None and hasattr(capture_lock, 'acquire_shared'),
            'Replica work needs the graph capture/replay lock')
    capture_lock.acquire_shared()
    try:
        yield
    finally:
        capture_lock.release_shared()


def slot_for(mode, index):
    """Which placement decodes clip `index` under `mode` (deterministic, recorded)."""
    require(mode in PLACEMENTS, 'Unknown decode placement mode: ' + repr(mode))
    require(isinstance(index, int) and index >= 0, 'Clip index must be a non-negative integer')
    slots = PLACEMENTS[mode]
    return slots[index % len(slots)]


def tensor_sha256(t):
    """The oracle capture node's convention (capture_node.py)."""
    return hashlib.sha256(t.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()


def _plain_tensor_attrs(module):
    """(owner, name, tensor) for tensor attributes that are not parameters or buffers."""
    out = []
    for sub in module.modules():
        for name, value in vars(sub).items():
            if isinstance(value, torch.Tensor) and not isinstance(value, torch.nn.Parameter):
                out.append((sub, name, value))
    return out


def placement_offenders(module, device):
    """Every tensor (parameter, buffer, plain attribute) not on `device`."""
    device = torch.device(device)
    bad = []
    for name, t in list(module.named_parameters()) + list(module.named_buffers()):
        if t.device != device:
            bad.append((name, str(t.device)))
    for owner, name, t in _plain_tensor_attrs(module):
        if t.device != device:
            bad.append((type(owner).__name__ + '.' + name, str(t.device)))
    return bad


def ensure_vaes_resident(load_models_gpu, vaes, idle, loads_frozen):
    """Packet 94d: bring the native VAEs wholly onto their card BEFORE a replica is copied.

    Serial capture-pass prompts are pipeline fills, so nothing decodes and ComfyUI
    leaves both VAEs on their offload device (in 93c a pipelined warm's first real
    decode loaded them as a side effect). This is the explicit step: allowed only
    before the freeze and with the pipeline idle; one full load through ComfyUI's
    own loader (force_full_load); then every tensor must be on the VAE's device.
    build_replica's own refusal to copy a moving model is unchanged."""
    require(idle, 'VAE residency step needs an idle pipeline')
    require(not loads_frozen, 'VAE residency step must run before the freeze (loads are frozen)')
    before = {type(v.first_stage_model).__name__: len(placement_offenders(v.first_stage_model, v.device))
              for v in vaes}
    load_models_gpu([v.patcher for v in vaes], force_full_load=True)
    after = {type(v.first_stage_model).__name__: len(placement_offenders(v.first_stage_model, v.device))
             for v in vaes}
    require(not any(after.values()), 'VAEs are still not wholly on their device after the load: %s' % after)
    return {'step': 'explicit full load of both VAEs onto their card before the replica copy',
            'offending_tensors_before': before, 'offending_tensors_after': after,
            'devices': [str(v.device) for v in vaes]}


def check_placement(module, slot):
    """The explicit allowlist: a module may serve `slot` only if all its tensors live on that slot's card."""
    require(slot in ALLOWED_DEVICES, 'Placement slot not admitted: ' + repr(slot))
    bad = placement_offenders(module, ALLOWED_DEVICES[slot])
    require(not bad, 'Decode module for slot %s has tensors off %s: %s'
            % (slot, ALLOWED_DEVICES[slot], bad[:4]))
    return True


def _staged(t, device):
    return t.detach().to('cpu', copy=True).to(device)


def _equal_on_host(a, b):
    """Byte equality (so NaN payloads and -0.0 count too)."""
    a, b = a.detach().to('cpu').contiguous(), b.detach().to('cpu').contiguous()
    if a.dtype != b.dtype or a.shape != b.shape:
        return False
    if a.numel() == 0:
        return True
    return bool(torch.equal(a.reshape(-1).view(torch.uint8), b.reshape(-1).view(torch.uint8)))


class Replica:
    __slots__ = ('module', 'device', 'stream', 'lock', 'report')

    def __init__(self, module, device, stream, report):
        self.module = module
        self.device = torch.device(device)
        self.stream = stream
        self.lock = threading.Lock()
        self.report = report


def clone_module(src, source_device, device, stage=None):
    """Deep copy of `src` whose every parameter, buffer and plain tensor
    attribute is a fresh copy on `device` (via `stage`, default: through host
    memory), torch.device attributes naming `source_device` repointed, and the
    copy verified byte-for-byte. Returns (module, rewritten_attrs)."""
    stage = stage or _staged
    source_device = torch.device(source_device)
    with torch.inference_mode(False), torch.no_grad():
        memo = {}
        for t in src.parameters():
            memo[id(t)] = torch.nn.Parameter(stage(t, device), requires_grad=False)
        for t in src.buffers():
            memo[id(t)] = stage(t, device)
        for _owner, _name, t in _plain_tensor_attrs(src):
            if id(t) not in memo:
                memo[id(t)] = stage(t, device)
        module = copy.deepcopy(src, memo)
        rewritten = []
        for sub in module.modules():
            for name, value in list(vars(sub).items()):
                if isinstance(value, torch.device) and value == source_device:
                    setattr(sub, name, torch.device(device))
                    rewritten.append(type(sub).__name__ + '.' + name)
        # Every parameter, every buffer (persistent AND non-persistent:
        # state_dict() would skip e.g. the NA decoder's
        # default_inference_timesteps) and every plain tensor attribute.
        mismatched = []
        pairs = []
        for kind, a_items, b_items in (('param', list(src.named_parameters()), list(module.named_parameters())),
                                       ('buffer', list(src.named_buffers()), list(module.named_buffers()))):
            require([n for n, _ in a_items] == [n for n, _ in b_items], 'Replica %s names differ' % kind)
            pairs += [(kind + ':' + n, a, b) for (n, a), (_m, b) in zip(a_items, b_items)]
        src_attrs, rep_attrs = _plain_tensor_attrs(src), _plain_tensor_attrs(module)
        require(len(src_attrs) == len(rep_attrs), 'Replica tensor attributes differ')
        for (_o1, n1, a), (_o2, n2, b) in zip(src_attrs, rep_attrs):
            require(n1 == n2, 'Replica tensor attribute names differ')
            pairs.append(('attr:' + n1, a, b))
        for name, a, b in pairs:
            if (a.numel() and a.data_ptr() == b.data_ptr()) or not _equal_on_host(a, b):
                mismatched.append(name)
    require(not mismatched, 'Replica copy is not exact or shares storage: %s' % mismatched[:4])
    return module, rewritten


def verified_tensors(module):
    """Count and bytes of what clone_module verifies (params, all buffers, tensor attrs)."""
    tensors = [t for _, t in module.named_parameters()] + [t for _, t in module.named_buffers()] + \
        [t for _o, _n, t in _plain_tensor_attrs(module)]
    return len(tensors), int(sum(t.numel() * t.element_size() for t in tensors))


def build_replica(vae, device, load_lock, capture_lock, make_stream=None):
    """Exact copy of `vae.first_stage_model` on `device`, outside ComfyUI's model management."""
    src = vae.first_stage_model
    source_device = torch.device(str(vae.device))
    require(torch.device(device) != source_device, 'Replica must live on a different card')
    slot = [k for k, v in ALLOWED_DEVICES.items() if torch.device(v) == torch.device(device)]
    require(slot == ['replica'], 'Replica device is not the admitted replica card')
    require(not placement_offenders(src, source_device),
            'Resident VAE is not wholly on its device; refusing to copy a moving model')
    # Under ComfyUI's load lock, so model management cannot move the source
    # mid-copy, and the capture lock (shared), so no graph capture is recording
    # while the copies allocate on xpu:1. Order: _LOAD_LOCK -> CAPTURE_LOCK.
    with load_lock, shared(capture_lock):
        module, rewritten = clone_module(src, source_device, device)
    check_placement(module, 'replica')
    stream = (make_stream or (lambda d: torch.xpu.Stream(device=d)))(device)
    count, nbytes = verified_tensors(module)
    report = {'class': type(src).__name__, 'device': str(device),
              'tensors_byte_verified': count, 'bytes': nbytes,
              'verified': 'parameters, all buffers (persistent and non-persistent), plain tensor attributes',
              'device_attrs_rewritten': rewritten}
    return Replica(module, device, stream, report)


def vae_decode_on(replica, vae, samples_in):
    """`comfy.sd.VAE.decode`, non-tiled path, on the replica module (no model management)."""
    import comfy.model_prefetch
    vae.throw_exception_if_invalid()
    if vae.latent_dim == 2 and samples_in.ndim == 5:
        samples_in = samples_in[:, :, 0]
    require(samples_in.shape[0] == 1, 'Replica decode mirrors the single-batch path only')
    model = replica.module
    require(next(model.parameters()).device == replica.device, 'Replica moved off its card')
    with replica.lock, torch.xpu.device(replica.device), torch.xpu.stream(replica.stream):
        preallocated = False
        pixel_samples = None
        if getattr(model, 'comfy_has_chunked_io', False):
            with comfy.model_prefetch.pause_malloc_graph():
                pixel_samples = torch.empty(model.decode_output_shape(samples_in.shape),
                                            device=vae.output_device, dtype=vae.vae_output_dtype())
            preallocated = True
        samples = samples_in[0:1].to(device=replica.device, dtype=vae.vae_dtype)
        if preallocated:
            model.decode(samples, output_buffer=pixel_samples[0:1])
        else:
            out = model.decode(samples).to(device=vae.output_device, dtype=vae.vae_output_dtype(), copy=True)
            with comfy.model_prefetch.pause_malloc_graph():
                pixel_samples = torch.empty((samples_in.shape[0],) + tuple(out.shape[1:]),
                                            device=vae.output_device, dtype=vae.vae_output_dtype())
            pixel_samples[0:1].copy_(out)
            del out
        vae.process_output(pixel_samples[0:1])
        replica.stream.synchronize()
    return pixel_samples.to(vae.output_device).movedim(1, -1)


def decode_clip_replica(video_replica, audio_replica, vae, audio_vae, video_latent, audio_latent):
    """What VAEDecode and LTXVAudioVAEDecode return, decoded on the replica card.

    The caller must hold CAPTURE_LOCK in shared mode around this call (see
    the lock order in the module docstring)."""
    latent = video_latent['samples']
    if latent.is_nested:
        latent = latent.unbind()[0]
    images = vae_decode_on(video_replica, vae, latent)
    if len(images.shape) == 5:
        images = images.reshape(-1, images.shape[-3], images.shape[-2], images.shape[-1])
    audio_samples = audio_latent['samples']
    if audio_samples.is_nested:
        audio_samples = audio_samples.unbind()[-1]
    waveform = vae_decode_on(audio_replica, audio_vae, audio_samples).movedim(-1, 1).to(audio_samples.device)
    audio = {'waveform': waveform, 'sample_rate': int(audio_vae.first_stage_model.output_sample_rate)}
    return images, audio


def free_bytes(device, xpu=None):
    """Device free memory: driver view when available, else total - torch reserved."""
    xpu = xpu or torch.xpu
    index = torch.device(device).index
    try:
        free, _total = xpu.mem_get_info(index)
        return int(free), 'mem_get_info'
    except Exception:  # noqa: BLE001
        total = xpu.get_device_properties(index).total_memory
        return int(total - xpu.memory_reserved(index)), 'total-minus-reserved'


def release_replicas(replicas, device, capture_lock, xpu=None):
    """Drop every replica reference and return the freed device memory.

    Called on any non-passing probe verdict so the control arm keeps today's
    headroom on xpu:1. empty_cache runs on xpu:1 only (torch.xpu.empty_cache
    acts on the current device) and under CAPTURE_LOCK (shared), so it never
    overlaps a graph capture; it releases only unused blocks of the default
    allocator pool, never a captured graph's private pool."""
    import gc
    xpu = xpu or torch.xpu
    index = torch.device(device).index
    before = {'reserved': int(xpu.memory_reserved(index)), 'free': free_bytes(device, xpu)}
    names = sorted(replicas)
    replicas.clear()
    gc.collect()
    with shared(capture_lock), xpu.device(device):
        xpu.empty_cache()
    after = {'reserved': int(xpu.memory_reserved(index)), 'free': free_bytes(device, xpu)}
    return {'released': names, 'before': before, 'after': after,
            'reserved_freed_bytes': before['reserved'] - after['reserved']}


def probe_rows(fixtures, load_tensors, native_decode, replica_decode):
    """Decode every fixture's certified latents on both cards; compare bytes.

    `fixtures`: rows with 'fixture', 'source', 'source_sha256' and 'expected'
    ({images, video_latent, audio_latent, waveform: sha256}).
    `load_tensors(row)` -> dict of CPU tensors (after checking the file hash).
    `native_decode` / `replica_decode`: (video_latent, audio_latent) -> (images, audio).
    Returns (passed, rows).
    """
    rows = []
    for fx in fixtures:
        row = {'fixture': fx['fixture'], 'source': fx['source']}
        tensors = load_tensors(fx)
        inputs_ok = all(tensor_sha256(tensors[k]) == fx['expected'][k] for k in ('video_latent', 'audio_latent'))
        row['inputs_certified'] = inputs_ok
        if not inputs_ok:
            row['passed'] = False
            rows.append(row)
            continue
        video_latent = {'samples': tensors['video_latent']}
        audio_latent = {'samples': tensors['audio_latent']}
        results = {}
        for slot, fn in (('native', native_decode), ('replica', replica_decode)):
            images, audio = fn(video_latent, audio_latent)
            results[slot] = (images.detach().cpu().contiguous(), audio['waveform'].detach().cpu().contiguous())
            row[slot] = {'images_sha256': tensor_sha256(images), 'waveform_sha256': tensor_sha256(audio['waveform'])}
        row['native_matches_reference'] = (row['native']['images_sha256'] == fx['expected']['images'] and
                                           row['native']['waveform_sha256'] == fx['expected']['waveform'])
        row['replica_matches_reference'] = (row['replica']['images_sha256'] == fx['expected']['images'] and
                                            row['replica']['waveform_sha256'] == fx['expected']['waveform'])
        (ni, nw), (ri, rw) = results['native'], results['replica']
        row['cards_bytewise_equal'] = (ni.dtype == ri.dtype and ni.shape == ri.shape and nw.shape == rw.shape and
                                       bool(torch.equal(ni.view(torch.uint8), ri.view(torch.uint8))) and
                                       bool(torch.equal(nw.view(torch.uint8), rw.view(torch.uint8))))
        row['passed'] = (row['native_matches_reference'] and row['replica_matches_reference'] and
                         row['cards_bytewise_equal'])
        rows.append(row)
    passed = bool(rows) and all(r['passed'] for r in rows)
    return passed, rows

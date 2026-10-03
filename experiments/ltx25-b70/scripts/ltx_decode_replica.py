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

Placement is an explicit allowlist (``ALLOWED_DEVICES``); a replica whose
tensors are not all on its slot's device is refused. The VAE graph gate is
not involved: every packet-91 arm runs it in ``original`` mode, and no
replica decode is graph-captured.
"""
import copy
import hashlib
import threading

import torch

NATIVE_DEVICE = 'xpu:3'
REPLICA_DEVICE = 'xpu:1'
ALLOWED_DEVICES = {'native': NATIVE_DEVICE, 'replica': REPLICA_DEVICE}
PLACEMENTS = {'pipeline': ('native',), 'pipeline-save': ('native',),
              'pipeline-replica': ('native', 'replica'), 'pipeline-moved': ('replica',)}
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
        mismatched = []
        src_state, rep_state = src.state_dict(), module.state_dict()
        require(list(src_state) == list(rep_state), 'Replica state-dict keys differ')
        for key in src_state:
            if (src_state[key].numel() and src_state[key].data_ptr() == rep_state[key].data_ptr()) or \
                    not _equal_on_host(src_state[key], rep_state[key]):
                mismatched.append(key)
        src_attrs, rep_attrs = _plain_tensor_attrs(src), _plain_tensor_attrs(module)
        require(len(src_attrs) == len(rep_attrs), 'Replica tensor attributes differ')
        for (_o1, n1, a), (_o2, n2, b) in zip(src_attrs, rep_attrs):
            if n1 != n2 or (a.numel() and a.data_ptr() == b.data_ptr()) or not _equal_on_host(a, b):
                mismatched.append('attr:' + n1)
    require(not mismatched, 'Replica copy is not exact or shares storage: %s' % mismatched[:4])
    return module, rewritten


def build_replica(vae, device, load_lock, make_stream=None):
    """Exact copy of `vae.first_stage_model` on `device`, outside ComfyUI's model management."""
    src = vae.first_stage_model
    source_device = torch.device(str(vae.device))
    require(torch.device(device) != source_device, 'Replica must live on a different card')
    slot = [k for k, v in ALLOWED_DEVICES.items() if torch.device(v) == torch.device(device)]
    require(slot == ['replica'], 'Replica device is not the admitted replica card')
    require(not placement_offenders(src, source_device),
            'Resident VAE is not wholly on its device; refusing to copy a moving model')
    # Under ComfyUI's load lock, so model management cannot move the source mid-copy.
    with load_lock:
        module, rewritten = clone_module(src, source_device, device)
    check_placement(module, 'replica')
    stream = (make_stream or (lambda d: torch.xpu.Stream(device=d)))(device)
    state = module.state_dict()
    report = {'class': type(src).__name__, 'device': str(device),
              'tensors': len(state) + len(_plain_tensor_attrs(module)),
              'bytes': int(sum(t.numel() * t.element_size() for t in state.values())),
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
    """What VAEDecode and LTXVAudioVAEDecode return, decoded on the replica card."""
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


def free_bytes(device):
    """Device free memory: driver view when available, else total - torch reserved."""
    index = torch.device(device).index
    try:
        free, _total = torch.xpu.mem_get_info(index)
        return int(free), 'mem_get_info'
    except Exception:  # noqa: BLE001
        total = torch.xpu.get_device_properties(index).total_memory
        return int(total - torch.xpu.memory_reserved(index)), 'total-minus-reserved'


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

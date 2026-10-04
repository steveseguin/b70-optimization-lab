"""Packet 93: lean conditioning (exact by construction) and the context-hash sentry.

Lean (sampler mode 'pipeline-lean', off unless that arm is requested):
the eight-plus-eight-layer text connectors (`preprocess_text_embeds`, called
from model_base.LTXAV.extra_conds for every conditioning in every
`process_conds`) run four times per clip today: positive and negative in stage
a, positive and negative in stage b. The graph feeds the SAME conditioning to
positive and negative (node 365) and cfg is 1, so the negative's result is
never read, and stage b repeats stage a's input bytes. Under lean, a per-clip,
per-thread memo computes the connector pass once and serves later calls whose
input is byte-identical (same dtype, shape, device, and bitwise-equal
contents, asserted on every reuse) with a private copy of the stored output.
A different input is computed normally. The memo lives for one clip on one
sampler worker and is dropped when the clip finishes: never across clips.

Sentry (both control and lean arms): the sha256 of the context tensor actually
passed to the FIRST diffusion-model forward of each sampler stage, recorded per
clip, so the run proves the sampler inputs are unchanged between arms. It only
reads (a device-to-host copy, outside any graph capture: the forward entry is
eager, captures are per block inside it).
"""
import hashlib
import threading

_tls = threading.local()
_MEMO_INSTALLED = {}
_SENTRY_INSTALLED = {}
_LOCK = threading.Lock()


def require(value, message):
    if not value:
        raise RuntimeError(message)


def bitwise_equal(a, b):
    import torch
    if not (isinstance(a, torch.Tensor) and isinstance(b, torch.Tensor)):
        return False
    if a.dtype != b.dtype or tuple(a.shape) != tuple(b.shape) or a.device != b.device:
        return False
    if a.dtype in (torch.bfloat16, torch.float16):
        return bool(torch.equal(a.contiguous().view(torch.int16), b.contiguous().view(torch.int16)))
    if a.dtype == torch.float32:
        return bool(torch.equal(a.contiguous().view(torch.int32), b.contiguous().view(torch.int32)))
    if a.dtype == torch.float64:
        return bool(torch.equal(a.contiguous().view(torch.int64), b.contiguous().view(torch.int64)))
    return bool(torch.equal(a, b))


def tensor_sha256(t):
    import torch
    host = t.detach().to('cpu', copy=True).contiguous()
    digest = hashlib.sha256(str((tuple(host.shape), str(host.dtype))).encode())
    digest.update(host.view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


# --- per-clip context on a sampler worker thread ------------------------------
def begin_clip(clip_index, lean):
    require(getattr(_tls, 'ctx', None) is None, 'A lean/sentry context is already open on this thread')
    _tls.ctx = {'clip_index': clip_index, 'lean': bool(lean), 'memo': [], 'computed': 0, 'reused': 0,
                'passthrough': 0, 'stage': None, 'sentries': {}, 'forwards': {}}


def set_stage(stage):
    ctx = getattr(_tls, 'ctx', None)
    if ctx is not None:
        ctx['stage'] = stage
        ctx['forwards'].setdefault(stage, 0)


def end_clip():
    ctx = getattr(_tls, 'ctx', None)
    _tls.ctx = None
    if ctx is None:
        return None
    ctx['memo'] = []          # drop the clip's stored tensors now
    return {'clip_index': ctx['clip_index'], 'lean': ctx['lean'],
            'connector_computed': ctx['computed'], 'connector_reused': ctx['reused'],
            'connector_passthrough': ctx['passthrough'],
            'stage_a_context_sha256': ctx['sentries'].get('a'),
            'stage_b_context_sha256': ctx['sentries'].get('b'),
            'forwards_per_stage': dict(ctx['forwards'])}


# --- the memo -----------------------------------------------------------------
def memo_call(original, context, unprocessed=False):
    """One preprocess_text_embeds call under the thread's clip context."""
    ctx = getattr(_tls, 'ctx', None)
    if ctx is None or not ctx['lean']:
        if ctx is not None:
            ctx['passthrough'] += 1
        return original(context, unprocessed=unprocessed)
    key = (bool(unprocessed), tuple(context.shape), str(context.dtype), str(context.device))
    for entry_key, stored_in, stored_out in ctx['memo']:
        if entry_key == key and bitwise_equal(stored_in, context):
            ctx['reused'] += 1
            return stored_out.clone()
    out = original(context, unprocessed=unprocessed)
    ctx['memo'].append((key, context.detach().clone(), out.detach().clone()))
    ctx['computed'] += 1
    return out


def install_memo(diffusion_model):
    """Shadow preprocess_text_embeds on the instance (idempotent). With no lean
    context on the calling thread it calls the original with the same arguments."""
    with _LOCK:
        if id(diffusion_model) in _MEMO_INSTALLED:
            return False
        require('preprocess_text_embeds' not in vars(diffusion_model),
                'preprocess_text_embeds is already shadowed')
        original = diffusion_model.preprocess_text_embeds

        def preprocess_text_embeds(context, unprocessed=False):
            return memo_call(original, context, unprocessed=unprocessed)

        diffusion_model.preprocess_text_embeds = preprocess_text_embeds
        _MEMO_INSTALLED[id(diffusion_model)] = original
        return True


# --- the sentry ---------------------------------------------------------------
def sentry_observe(args, kwargs):
    ctx = getattr(_tls, 'ctx', None)
    if ctx is None or ctx['stage'] is None:
        return
    stage = ctx['stage']
    ctx['forwards'][stage] = ctx['forwards'].get(stage, 0) + 1
    if stage in ctx['sentries']:
        return
    context = kwargs.get('context', args[2] if len(args) > 2 else None)
    ctx['sentries'][stage] = None if context is None else tensor_sha256(context)


def install_sentry(diffusion_model):
    with _LOCK:
        if id(diffusion_model) in _SENTRY_INSTALLED:
            return False
        require('forward' not in vars(diffusion_model), 'Diffusion model forward is already shadowed')
        original = diffusion_model.forward

        def forward(*args, **kwargs):
            sentry_observe(args, kwargs)
            return original(*args, **kwargs)

        diffusion_model.forward = forward
        _SENTRY_INSTALLED[id(diffusion_model)] = original
        return True

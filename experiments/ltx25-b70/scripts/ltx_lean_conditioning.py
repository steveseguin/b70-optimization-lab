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

Packet 96 (batch servers only, LTX_SAMPLER_BATCH 2 or 4): one sampler job carries B
clips. Their raw text features differ in token count and cannot be stacked, so the
batch cond carries a placeholder naming a per-job list of the clips' own raw
tensors (register_batch_raw). The memo shadow is installed in every pipelined mode
on a batch server; called with a placeholder, it converts each clip's raw tensor
exactly as extra_conds would (same device and dtype as the converted placeholder),
runs the connector at batch 1 per clip (lean: computed once per clip per job and
reused only for the SAME row's byte-identical input, never across rows), and stacks
the processed rows (each a fixed 1024 tokens). The sentry also records each row's
context hash, and an optional observer (the batch guard) sees every forward. With
batch 1 (every batch-1 server) none of this runs.
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
def begin_clip(clip_index, lean, batch=1, observer=None):
    require(getattr(_tls, 'ctx', None) is None, 'A lean/sentry context is already open on this thread')
    _tls.ctx = {'clip_index': clip_index, 'lean': bool(lean), 'memo': [], 'computed': 0, 'reused': 0,
                'passthrough': 0, 'stage': None, 'sentries': {}, 'forwards': {}}
    if batch != 1:
        # Packet 96: a batch job (B rows); per-row memo and per-row context hashes.
        require(isinstance(batch, int) and batch > 1, 'Unsupported batch %r' % (batch,))
        _tls.ctx.update({'batch': batch, 'observer': observer, 'row_memo': {k: [] for k in range(batch)},
                         'row_sentries': {}, 'batch_raw': []})


def register_batch_raw(raws):
    """Packet 96: register one cond's per-clip raw text features for this batch job;
    returns the tag its placeholder carries."""
    ctx = getattr(_tls, 'ctx', None)
    require(ctx is not None and ctx.get('batch', 1) != 1, 'No batch job context on this thread')
    require(len(raws) == ctx['batch'], 'Expected %d per-clip raw tensors, got %d' % (ctx['batch'], len(raws)))
    ctx['batch_raw'].append(list(raws))
    return len(ctx['batch_raw']) - 1


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
    out = {'clip_index': ctx['clip_index'], 'lean': ctx['lean'],
           'connector_computed': ctx['computed'], 'connector_reused': ctx['reused'],
           'connector_passthrough': ctx['passthrough'],
           'stage_a_context_sha256': ctx['sentries'].get('a'),
           'stage_b_context_sha256': ctx['sentries'].get('b'),
           'forwards_per_stage': dict(ctx['forwards'])}
    if ctx.get('batch', 1) != 1:
        ctx['row_memo'] = {}
        ctx['batch_raw'] = []
        out.update({'batch': ctx['batch'],
                    'stage_a_row_sha256s': ctx['row_sentries'].get('a'),
                    'stage_b_row_sha256s': ctx['row_sentries'].get('b')})
    return out


# --- the memo -----------------------------------------------------------------
def memo_call(original, context, unprocessed=False):
    """One preprocess_text_embeds call under the thread's clip context."""
    ctx = getattr(_tls, 'ctx', None)
    if ctx is not None and ctx.get('batch', 1) != 1:
        return _batch_rows(ctx, original, context, unprocessed)
    return _one(ctx, ctx['memo'] if ctx is not None else None, original, context, unprocessed)


def _one(ctx, memo, original, context, unprocessed):
    if ctx is None or not ctx['lean']:
        if ctx is not None:
            ctx['passthrough'] += 1
        return original(context, unprocessed=unprocessed)
    key = (bool(unprocessed), tuple(context.shape), str(context.dtype), str(context.device))
    for entry_key, stored_in, stored_out in memo:
        if entry_key == key and bitwise_equal(stored_in, context):
            ctx['reused'] += 1
            return stored_out.clone()
    out = original(context, unprocessed=unprocessed)
    memo.append((key, context.detach().clone(), out.detach().clone()))
    ctx['computed'] += 1
    return out


def _batch_rows(ctx, original, context, unprocessed):
    """Packet 96: `context` is the converted placeholder of a batch cond. Each clip's own
    raw tensor gets the conversion extra_conds gave the placeholder (its device and
    dtype), the connector runs once per clip at batch 1, the lean memo is per row, and
    the rows (fixed shape) are stacked."""
    import torch
    batch = ctx['batch']
    require(context.dim() == 3 and context.shape[0] == batch and context.shape[-1] == 1,
            'Batch job context is not a %d-row placeholder: %s' % (batch, tuple(context.shape)))
    tag = context.shape[1] - 1
    require(0 <= tag < len(ctx['batch_raw']), 'No registered raw features for placeholder tag %d' % tag)
    raws = ctx['batch_raw'][tag]
    outs = [_one(ctx, ctx['row_memo'][k], original, raws[k].to(device=context.device, dtype=context.dtype),
                 unprocessed) for k in range(batch)]
    require(all(tuple(o.shape) == tuple(outs[0].shape) for o in outs),
            'Connector outputs differ in shape between clips: %s' % [tuple(o.shape) for o in outs])
    return torch.cat(outs, dim=0)


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


def install_batch_rows(diffusion_model):
    """Packet 96, batch servers only: the per-clip connector split for batch jobs lives in
    the preprocess_text_embeds shadow, so a batch server installs it in every pipelined
    mode. It is the same shadow as install_memo (idempotent, shared); outside a lean job
    it never memoises (each row is computed, a passthrough per row). Never called on a
    batch-1 server."""
    return install_memo(diffusion_model)


# --- the sentry ---------------------------------------------------------------
def sentry_observe(args, kwargs):
    ctx = getattr(_tls, 'ctx', None)
    if ctx is None or ctx['stage'] is None:
        return
    stage = ctx['stage']
    ctx['forwards'][stage] = ctx['forwards'].get(stage, 0) + 1
    first = stage not in ctx['sentries']
    if first:
        context = kwargs.get('context', args[2] if len(args) > 2 else None)
        ctx['sentries'][stage] = None if context is None else tensor_sha256(context)
        if ctx.get('batch', 1) != 1:
            # Packet 96: each row hashed like a batch-1 clip's context (same shape string).
            ctx['row_sentries'][stage] = (None if context is None else
                                          [tensor_sha256(context[k:k + 1]) for k in range(context.shape[0])])
    if ctx.get('observer') is not None:
        ctx['observer'](stage, first, args, kwargs)


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

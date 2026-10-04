"""Packet 96: one sampler job carries B consecutive clips as one batch of B.

The transformer blocks are bound by reading their weights, so one forward that
serves B clips reads the weights once for all B. This module holds the parts of
the batched sampler that do not need a GPU: the server option, the grouping of
consecutive clips into fixed-size jobs, the emission depth, the stacking of
per-clip inputs, the per-clip noise, and the checks that refuse a job.

Exactness rules (each enforced here or in pipeline_sampler_node.sample_batch):

- Every clip's inputs are exactly what it would get alone, stacked. Initial noise:
  each clip's own Noise object draws for a batch-1 latent of its own shape and its
  own seed (comfy.sample.prepare_noise), then the rows are concatenated. Ancestral
  per-step noise: one generator per clip, built by the stock default_noise_sampler
  for a batch-1 view, concatenated per step. Conditioning: the raw text features
  have a per-prompt token count, so they cannot be stacked; only the connector
  output (a fixed 1024 tokens) can. The batch cond therefore carries a small
  placeholder whose shape names a per-job list of the clips' own raw features;
  inside the stock extra_conds call, ltx_lean_conditioning runs the connector per
  clip at batch 1 on that clip's raw tensor (converted exactly as extra_conds
  converts it) and stacks the processed rows.
- Lockstep: every clip in a job samples at the same sigma (the sigma schedules must
  be bitwise equal), because av_model mixes rows through a_timestep_scaled.max().
- Fixed batch shape: a job always has B rows. Missing rows (start of a capture
  pass, end of a stream) repeat the last real clip's inputs and are discarded.
- Fail closed: any mismatch refuses the job with a recorded reason. A batch server
  never falls back to batch 1.

No GPU, no ComfyUI import at module level (CPU tests import it directly).
"""
import threading

BATCH_CHOICES = (1, 2, 4)
ENVIRONMENT = 'LTX_SAMPLER_BATCH'
# Emission depth (prompts between submitting a clip and emitting it). Bounded so a
# mistyped graph cannot park an unbounded number of clips.
MAX_BATCH_DEPTH = 24
# Diffusion-forward arguments that legitimately carry no batch dimension.
UNBATCHED_SUFFIXES = ('sample_sigmas',)
# transformer_options entries that are infrastructure, never per-row data.
SKIP_KEYS = ('patches_replace', '_ltx_layer_shard_forward_transfers', 'wrappers', 'callbacks', 'patches')


class BatchRefused(RuntimeError):
    """A batch job (or a batch request) was refused; the message is the recorded reason."""


def need(ok, reason):
    if not ok:
        raise BatchRefused(reason)


def read_batch(environ):
    raw = environ.get(ENVIRONMENT, '1') or '1'
    try:
        value = int(raw)
    except ValueError:
        value = None
    if value not in BATCH_CHOICES:
        raise RuntimeError('%s must be one of %s' % (ENVIRONMENT, BATCH_CHOICES))
    return value


def timed_depth(workers, batch):
    """Emission depth for `workers` sampler jobs in flight plus one queued job.
    batch 1 gives `workers`, the packet 95 depth."""
    return (workers + 1) * batch - 1


def serial_depth(batch):
    """Smallest depth that cannot deadlock: the prompt that completes a group waits
    for that group's own job, so jobs run strictly one at a time."""
    return batch - 1


def depth_ok(depth, batch):
    return isinstance(depth, int) and max(1, serial_depth(batch)) <= depth <= MAX_BATCH_DEPTH


# --- grouping consecutive clips into jobs ---------------------------------------
class Grouper:
    """Groups consecutive clip indices into jobs of exactly `batch` rows.

    A job closes when it holds `batch` clips, or when the depositing prompt is the
    last of its stream (`stream_last`); then the missing rows repeat the last real
    clip and are marked as fills. Clips of one job must be consecutive and share one
    signature (mode, depth, batch); anything else is refused, never regrouped."""

    def __init__(self, batch):
        need(batch in BATCH_CHOICES, 'unsupported batch %r' % (batch,))
        self.batch = batch
        self.lock = threading.Lock()
        self.open = []                 # [(clip_index, item)]
        self.signature = None
        self.clip_job = {}             # clip index -> job key (first clip of its job)
        self.jobs = {}                 # job key -> {'clips': [...], 'emitted': set()}
        self.used = set()              # every clip index ever deposited (an index is never reused)

    def open_clips(self):
        with self.lock:
            return [c for c, _ in self.open]

    def deposit(self, clip_index, item, signature, stream_last):
        with self.lock:
            need(isinstance(clip_index, int) and clip_index >= 0, 'clip index must be a non-negative integer')
            need(clip_index not in self.clip_job and clip_index not in self.used,
                 'clip %d was already deposited on this server (stale index from an earlier stream)' % clip_index)
            if self.open:
                last = self.open[-1][0]
                need(clip_index == last + 1,
                     'clip %d does not follow the open group %s: a stream ended without its last prompt; '
                     'refused (start a new stream only after the previous one flushed)'
                     % (clip_index, [c for c, _ in self.open]))
                need(signature == self.signature,
                     'clip %d has request signature %r, the open group %r' % (clip_index, signature, self.signature))
            else:
                self.signature = signature
            self.open.append((clip_index, item))
            self.used.add(clip_index)
            if len(self.open) < self.batch and not stream_last:
                return None
            real = list(self.open)
            self.open = []
            self.signature = None
            rows = [(c, it) for c, it in real]
            fill_slots = list(range(len(rows), self.batch))
            while len(rows) < self.batch:
                rows.append((None, real[-1][1]))      # repeat the last real clip's inputs
            key = real[0][0]
            clips = [c for c, _ in real]
            for c in clips:
                self.clip_job[c] = key
            self.jobs[key] = {'clips': clips, 'emitted': set()}
            return {'key': key, 'rows': rows, 'clips': clips, 'fill_slots': fill_slots,
                    'fill_of': real[-1][0] if fill_slots else None, 'batch': self.batch,
                    'signature': signature}

    def job_of(self, clip_index):
        with self.lock:
            return self.clip_job.get(clip_index)

    def emitted(self, clip_index):
        """Record that a clip was emitted. True when every real clip of its job has been
        emitted (the job can then be released)."""
        with self.lock:
            key = self.clip_job.pop(clip_index)
            job = self.jobs[key]
            job['emitted'].add(clip_index)
            done = job['emitted'] == set(job['clips'])
            if done:
                del self.jobs[key]
            return done

    def clear(self):
        with self.lock:
            self.open = []
            self.signature = None
            self.clip_job.clear()
            self.jobs.clear()
            self.used.clear()


def emission_index(clip_index, depth):
    return clip_index - depth


# --- stacking ----------------------------------------------------------------------
def _tensor_like(value):
    return hasattr(value, 'shape') and hasattr(value, 'dtype') and hasattr(value, 'device')


def equal_values(a, b):
    """Bitwise for tensors (dtype, shape, device and bytes), == for everything else."""
    if _tensor_like(a) or _tensor_like(b):
        if not (_tensor_like(a) and _tensor_like(b)):
            return False
        import torch
        if a.dtype != b.dtype or tuple(a.shape) != tuple(b.shape) or a.device != b.device:
            return False
        return bool(torch.equal(a.contiguous().view(torch.uint8), b.contiguous().view(torch.uint8)))
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(equal_values(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return type(a) is type(b) and len(a) == len(b) and all(equal_values(x, y) for x, y in zip(a, b))
    try:
        return bool(a == b)
    except Exception:  # noqa: BLE001
        return a is b


def stack_rows(tensors, what):
    """Concatenate batch-1 tensors along dim 0 (each must be batch 1, same layout)."""
    import torch
    first = tensors[0]
    for t in tensors:
        need(_tensor_like(t) and t.dim() >= 1 and t.shape[0] == 1, '%s: every row must be a batch-1 tensor' % what)
        need(t.dtype == first.dtype and tuple(t.shape) == tuple(first.shape) and t.device == first.device,
             '%s: rows differ in dtype/shape/device' % what)
    return torch.cat(list(tensors), dim=0)


def stack_latent_dicts(dicts, what):
    """One latent dict of B rows from B batch-1 latent dicts. Every key other than
    'samples' must be equal; masks and batch indices are refused (not in this recipe)."""
    keys = set(dicts[0])
    for d in dicts:
        need(set(d) == keys, '%s: latent keys differ between clips' % what)
        need('noise_mask' not in d and 'batch_index' not in d, '%s: masks/batch indices are not supported' % what)
        need(not getattr(d['samples'], 'is_nested', False), '%s: a stage input latent is already nested' % what)
    out = {}
    for k in keys:
        if k == 'samples':
            out[k] = stack_rows([d[k] for d in dicts], what + '.samples')
        else:
            need(all(equal_values(d[k], dicts[0][k]) for d in dicts), '%s: %r differs between clips' % (what, k))
            out[k] = dicts[0][k]
    return out


def nested_rows(nested, batch, what):
    parts = list(nested.unbind())
    need(len(parts) == 2, '%s: expected a video+audio latent' % what)
    for t in parts:
        need(t.shape[0] == batch, '%s: leading dimension %d, batch %d' % (what, t.shape[0], batch))
    return parts


def rows_uniform_nonzero(nested, batch):
    """inner_sample shifts a latent only if count_nonzero(whole batch) > 0. That is a
    batch-wide decision; it is per-clip exact only when every row agrees."""
    import torch
    parts = nested_rows(nested, batch, 'stage latent')
    flags = [any(int(torch.count_nonzero(t[k])) > 0 for t in parts) for k in range(batch)]
    return len(set(flags)) == 1, flags


class BatchNoise:
    """Initial noise for B rows: each row from its own clip's Noise object, drawn for a
    batch-1 latent of that clip's shape (prepare_noise seeds the global generator with the
    clip's seed and draws video then audio), then concatenated. Never one batch-B draw.
    All B draws run under `lock` (the process-wide noise lock), so no other sampler thread
    can interleave with the global generator."""

    def __init__(self, noises, lock):
        need(len(noises) >= 1, 'no noise objects')
        self.noises = list(noises)
        self.lock = lock
        self.seed = getattr(self.noises[0], 'seed', None)
        self.seeds = [getattr(n, 'seed', None) for n in self.noises]

    def generate_noise(self, input_latent):
        import torch
        samples = input_latent['samples']
        need('batch_index' not in input_latent, 'batch_index is not supported')
        need(getattr(samples, 'is_nested', False), 'stage latent must be a video+audio latent')
        parts = nested_rows(samples, len(self.noises), 'noise input')
        nested_type = type(samples)
        rows = []
        with self.lock:
            for k, noise in enumerate(self.noises):
                row = {kk: vv for kk, vv in input_latent.items() if kk != 'samples'}
                row['samples'] = nested_type([t[k:k + 1] for t in parts])
                rows.append(list(noise.generate_noise(row).unbind()))
        return nested_type([torch.cat([r[i] for r in rows], dim=0) for i in range(len(parts))])


ANCESTRAL = ('sample_euler_ancestral', 'sample_euler_ancestral_RF')


def batched_ksampler(samplers, seeds, ksampler_cls, default_noise_sampler):
    """A KSAMPLER equal to the clips' own, except that its ancestral per-step noise is
    one generator per clip (default_noise_sampler on a batch-1 view, exactly as the
    batch-1 sampler builds it from that clip's seed), concatenated per step."""
    s0 = samplers[0]
    for s in samplers:
        need(type(s) is ksampler_cls, 'sampler is not a KSAMPLER')
        need(s.sampler_function is s0.sampler_function, 'clips use different sampler functions')
        need(equal_values(s.extra_options, s0.extra_options) and equal_values(s.inpaint_options, s0.inpaint_options),
             'clips use different sampler options')
    base = s0.sampler_function
    need(getattr(base, '__name__', '') in ANCESTRAL, 'only euler_ancestral is admitted (got %r)'
         % getattr(base, '__name__', base))
    need('noise_sampler' not in s0.extra_options, 'a custom noise sampler is already set')
    need(not s0.inpaint_options.get('random', False), 'random inpaint noise is not supported')
    seeds = list(seeds)
    need(all(isinstance(s, int) for s in seeds), 'every clip needs an integer seed')

    def batched(model, x, sigmas, extra_args=None, callback=None, disable=None, **kwargs):
        import torch
        need(kwargs.get('noise_sampler') is None, 'a noise sampler was passed in')
        need(x.shape[0] == len(seeds), 'sampler input has %d rows, %d seeds' % (x.shape[0], len(seeds)))
        need((extra_args or {}).get('seed') == seeds[0], 'sampler seed is not the first row seed')
        per_row = [default_noise_sampler(x[k:k + 1], seed=seed) for k, seed in enumerate(seeds)]

        def noise_sampler(sigma, sigma_next):
            return torch.cat([ns(sigma, sigma_next) for ns in per_row], dim=0)

        kwargs['noise_sampler'] = noise_sampler
        return base(model, x, sigmas, extra_args=extra_args, callback=callback, disable=disable, **kwargs)

    batched.__name__ = getattr(base, '__name__', 'sampler') + '_rows'
    return ksampler_cls(batched, dict(s0.extra_options), dict(s0.inpaint_options))


# Cond metadata the LTXAV model never reads: model_base.LTXAV.extra_conds does not look at
# it and BaseModel.encode_adm (inherited) returns None. It may differ between clips; the
# batch cond carries the first clip's value.
META_UNREAD = ('pooled_output',)


def placeholder(batch, tag):
    """Stand-in cross_attn for a batch cond: B rows, shape[1] - 1 = the tag of the
    registered per-clip raw list, last dimension 1 (never a real feature width)."""
    import torch
    return torch.zeros(batch, tag + 1, 1)


def placeholder_tag(context, batch):
    need(context is not None and context.dim() == 3 and context.shape[0] == batch and context.shape[-1] == 1,
         'batch cond context is not a placeholder of %d rows: %s' % (batch, tuple(getattr(context, 'shape', ()))))
    return context.shape[1] - 1


def split_cond(converted, what):
    """One converted cond dict -> (raw cross_attn tensor, metadata without uuid)."""
    need(isinstance(converted, dict) and 'cross_attn' in converted, '%s: no cross_attn' % what)
    need(converted.get('model_conds', {}) == {}, '%s: unexpected model_conds' % what)
    meta = {k: v for k, v in converted.items() if k not in ('cross_attn', 'model_conds', 'uuid')}
    return converted['cross_attn'], meta


def stacked_conds(guiders, what, register):
    """ComfyUI-format conds ({'positive': [[placeholder, meta]], 'negative': ...}). Each
    name's per-clip raw text features are registered (register(list) -> tag) for the
    per-clip connector; the placeholder names the tag. Every other field must be equal
    between clips (an unequal per-clip tensor would be repeated, not stacked, so it is
    refused), except META_UNREAD."""
    out = {}
    keys = set(guiders[0].original_conds)
    need(keys == {'positive', 'negative'}, '%s: unexpected cond keys %s' % (what, sorted(keys)))
    for name in sorted(keys):
        raws, metas = [], []
        for g in guiders:
            need(set(g.original_conds) == keys, '%s: cond keys differ between clips' % what)
            conds = g.original_conds[name]
            need(isinstance(conds, list) and len(conds) == 1, '%s.%s: exactly one cond per clip' % (what, name))
            raw, meta = split_cond(conds[0], '%s.%s' % (what, name))
            raws.append(raw)
            metas.append(meta)
        for m in metas:
            read = {k: v for k, v in m.items() if k not in META_UNREAD}
            need(equal_values(read, {k: v for k, v in metas[0].items() if k not in META_UNREAD}),
                 '%s.%s: cond metadata differs between clips' % (what, name))
        r0 = raws[0]
        for r in raws:
            need(_tensor_like(r) and r.dim() == 3 and r.shape[0] == 1 and r.shape[-1] == r0.shape[-1] and
                 r.dtype == r0.dtype and r.device == r0.device,
                 '%s.%s: raw text features are not batch-1 [1, tokens, width] of one width/dtype/device' % (what, name))
        out[name] = [[placeholder(len(guiders), register(list(raws))), dict(metas[0])]]
    return out


def batch_guider(guiders, what, register):
    """A guider of the clips' own class over the batch conds, with the same patcher,
    model options and cfg scales (all required identical)."""
    g0 = guiders[0]
    for g in guiders:
        need(type(g) is type(g0), '%s: guider classes differ' % what)
        need(g.model_patcher is g0.model_patcher, '%s: guiders use different patchers' % what)
        need(g.model_options is g0.model_options, '%s: guiders carry different model options' % what)
        need((getattr(g, 'video_cfg', None), getattr(g, 'audio_cfg', None), g.cfg) ==
             (getattr(g0, 'video_cfg', None), getattr(g0, 'audio_cfg', None), g0.cfg),
             '%s: cfg scales differ' % what)
    conds = stacked_conds(guiders, what, register)
    new = type(g0)(g0.model_patcher)
    new.model_options = g0.model_options
    new.inner_set_conds(conds)
    if hasattr(g0, 'video_cfg'):
        new.set_cfg(g0.video_cfg, g0.audio_cfg)
    else:
        new.set_cfg(g0.cfg)
    return new


def lockstep_sigmas(sigma_list, what):
    s0 = sigma_list[0]
    need(all(equal_values(s, s0) for s in sigma_list), '%s: sigma schedules differ between clips (lockstep '
         'required: av_model mixes rows through a_timestep_scaled.max())' % what)
    return s0


# --- the per-forward guard -----------------------------------------------------------
def forward_census(value, path='arg'):
    """{path: shape} of every tensor in a diffusion-forward argument tree."""
    out = {}
    if _tensor_like(value):
        out[path] = list(value.shape)
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            out.update(forward_census(v, '%s[%d]' % (path, i)))
    elif isinstance(value, dict):
        for k, v in value.items():
            if k in SKIP_KEYS:
                continue
            out.update(forward_census(v, '%s.%s' % (path, k)))
    else:
        data = getattr(value, 'data', None)        # LTX CompressedTimestep carries its rows in .data
        if _tensor_like(data):
            out[path + '<data>'] = list(data.shape)
    return out


def census_violations(census, batch):
    """Every tensor argument must carry the batch in its leading dimension, except the
    known unbatched ones (the sigma schedule). A batch-1 tensor here would be a per-clip
    argument that was not stacked."""
    bad = []
    for path, shape in sorted(census.items()):
        if path.endswith(UNBATCHED_SUFFIXES):
            continue
        if not shape or shape[0] != batch:
            bad.append('%s %s' % (path, shape))
    return bad


def expected_stacked_census(census_b1, batch):
    """What the packet 72 batchproof stacker produces from a batch-1 census: leading
    dimension 1 becomes `batch`; unbatched tensors pass through."""
    out = {}
    for path, shape in census_b1.items():
        shape = list(shape)
        dims = [d for d in shape if isinstance(d, int)]
        if not path.endswith(UNBATCHED_SUFFIXES) and dims and dims[0] == 1:
            shape[0] = batch
        out[path] = shape
    return out


def rows_equal(tensor):
    """True if every row equals row 0 bitwise (host read; call once per stage)."""
    import torch
    if tensor is None or not _tensor_like(tensor) or tensor.dim() == 0 or tensor.shape[0] <= 1:
        return True
    first = tensor[0:1].expand_as(tensor).contiguous()
    return bool(torch.equal(tensor.contiguous().view(torch.uint8), first.view(torch.uint8)))


def forward_timesteps(args, kwargs):
    """(v_timestep, a_timestep, option sigmas) at the LTXAV forward entry."""
    t = args[1] if len(args) > 1 else kwargs.get('timestep')
    if isinstance(t, (tuple, list)) and len(t) == 2:
        v, a = t
    else:
        v = a = t
    options = kwargs.get('transformer_options', args[5] if len(args) > 5 else None) or {}
    return v, a, options.get('sigmas') if isinstance(options, dict) else None


def make_forward_guard(batch, refuse):
    """Observer for ltx_lean_conditioning's forward sentry: on every forward the shape
    census must carry the batch on every per-row argument; on the first forward of each
    stage the timesteps and option sigmas must be equal on every row (lockstep)."""
    def guard(stage, first, args, kwargs):
        census = forward_census(list(args), 'args')
        census.update(forward_census({k: v for k, v in kwargs.items()}, 'kwargs'))
        bad = census_violations(census, batch)
        if bad:
            refuse('stage %s: arguments without the batch dimension: %s' % (stage, '; '.join(bad[:8])))
        if first:
            v, a, sig = forward_timesteps(args, kwargs)
            for name, t in (('v_timestep', v), ('a_timestep', a), ('option sigmas', sig)):
                if not rows_equal(t):
                    refuse('stage %s: %s differs between rows (lockstep required)' % (stage, name))
    return guard


# --- captured signatures ------------------------------------------------------------
def leading_dims(described):
    """Leading dimensions of every tensor in a ltx_graph_capture.describe() tree.

    describe() nodes are tagged tuples whose first element is a string: ('T', shape, ...)
    for a tensor, ('S', repr) for a scalar, ('tuple'|'list', (child, ...)),
    ('dict', ((key, child), ...)) and (class name, ((attribute, child), ...)). A payload
    tuple (the children of a tuple/list/dict/object node) has no tag and every one of
    its elements is a child."""
    out = set()
    if isinstance(described, (tuple, list)) and described:
        head = described[0]
        if head == 'T' and len(described) > 1 and isinstance(described[1], tuple):
            if described[1]:
                out.add(described[1][0])
            return out
        children = described[1:] if isinstance(head, str) else described
        for part in children:
            out |= leading_dims(part)
    return out


def signature_batches(routes, idents):
    """Set of activation leading dimensions over every captured sampler signature of the
    given worker threads (signature key[0] is describe(routed['img']))."""
    dims = set()
    for route in routes:
        for t in idents:
            for key in route.entries.get(t, {}):
                dims |= leading_dims(key[0] if isinstance(key, tuple) and key else key)
    return sorted(dims)


# --- fixture arrangements for the reference and proof arms ---------------------------
ORDERS = {
    2: {'ref': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        # same slots, different neighbours: (0,3) (2,5) (4,7) (6,9) (8,1)
        'proof-neighbours': [0, 3, 2, 5, 4, 7, 6, 9, 8, 1],
        # same neighbours, swapped slots: (1,0) (3,2) ...
        'proof-slots': [1, 0, 3, 2, 5, 4, 7, 6, 9, 8]},
    4: {'ref': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1],
        # a different grouping: (0,5,2,7) (4,9,6,1) (8,3,0,5)
        'proof-neighbours': [0, 5, 2, 7, 4, 9, 6, 1, 8, 3, 0, 5],
        # a rotation by one: every fixture changes slot
        'proof-slots': [1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2]},
}


def order_for(name, batch, count, fixtures=10):
    """Fixture index per prompt. 'cycle': i mod 10 (packet 95). 'shift': cycle k is
    rotated by k, so batch composition changes from cycle to cycle. Named orders are
    followed by the cycle continuing after their last fixture (the drain prompts)."""
    if name == 'cycle':
        return [i % fixtures for i in range(count)]
    if name == 'shift':
        return [(i + i // fixtures) % fixtures for i in range(count)]
    base = list(ORDERS[batch][name])
    nxt = (base[-1] + 1) % fixtures
    while len(base) < count:
        base.append(nxt)
        nxt = (nxt + 1) % fixtures
    return base[:count]


def arrangement(order, batch, real_count):
    """For prompts 0..real_count-1 of a stream grouped from its first prompt: per prompt
    (slot, sorted neighbour fixtures)."""
    out = []
    for i in range(real_count):
        g = i // batch
        members = order[g * batch:(g + 1) * batch]
        out.append((i % batch, sorted(members[:i % batch] + members[i % batch + 1:])))
    return out

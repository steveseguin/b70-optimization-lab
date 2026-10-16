"""Keep a skipped request's accepted-draft count across the step it sat out (research overlay, B70_SPEC_RESUME_ACCEPTED=1).

The defect (stock vLLM 0.29, V1 GPU model runner, async scheduling + speculative decoding + a GDN/Mamba model with
mamba_cache_mode "none"; R310/R313/R314 alike). After a verify step that accepts `a` tokens of a request, the GDN
kernels keep one state per verify row in that request's state slots and the NEXT step reads its starting state
(and conv window) from slot a - 1, using `num_accepted_tokens` (gdn_attn.py:396-397 -> _xpu_ops.py:143/:250).
Under async scheduling that count is only known on the device: _prepare_inputs fills `num_accepted_tokens` with 1
(gpu_model_runner.py:2154-2157) and `update_num_computed_tokens_for_batch_change` (spec_decode/utils.py:566-596,
called at gpu_model_runner.py:2172-2189) puts back `valid_sampled_token_count` ONLY for rows whose request was in
the IMMEDIATELY PREVIOUS step (prev_positions >= 0). A running request that is left out of one step (the
scheduler skips it, e.g. b70_exclusive_prefill hides it for a prompt-only step through next_decode_eligible_step)
is removed from the persistent batch by _update_states (gpu_model_runner.py:1257-1263), and remove_request also
pops it from `prev_req_id_to_index` (gpu_input_batch.py:573-574). When it comes back its prev position is -1, its
count stays 1, and the kernels start from slot 0: the state after the first verify row of its last step, missing
a - 1 accepted tokens. Its next token is computed from a wrong recurrent state.
(The synchronous path loses it too: input_batch.add_request resets num_accepted_tokens_cpu to 1,
gpu_input_batch.py:484. This overlay handles the async path, which is what the lanes run.)

Version 0.1.0 stored the count inside _prepare_inputs and never fired on the GPU run of 2026-10-04
(fp8-r314-mtp5-s4-resume-20261004): by then _update_states had already removed the hidden request from
`prev_req_id_to_index`, so it looked like it had never been there. 0.2.0 stores it before _update_states runs.

What this overlay does (class-level wrappers on GPUModelRunner, host-side bookkeeping only):
  _update_states, before the stock call: for every request in `prev_req_id_to_index` (the previous step) that this
    step does not schedule and that has not finished, store valid_sampled_token_count_gpu[its previous row]
    (a device-side copy, no host sync), clamped to >= 1;
  _prepare_inputs, after the stock call: for every row whose request is not in the previous step and has a stored
    count, write it into num_accepted_tokens.gpu[row], which is what the stock correction would have written had
    the request not been skipped. Requests resumed from preemption (state recomputed from the prompt) and finished
    requests only drop their stored count.
  When a returning request carries placeholder drafts (-1: the real drafts of its last step were never handed to
    the scheduler under async scheduling), the -1 input ids are replaced by 0 in input_ids so no embedding lookup
    sees a negative id (one card: plain index; two cards: masked anyway). The rejection sampler still compares the
    -1 drafts, so all of them are rejected and the step yields one token, from row 0, as before.
Nothing changes for a request that ran in the previous step (the stock path), so a lone user's steps and every
step of a run without skipped requests are untouched.

B70_SPEC_RESUME_DEBUG=N (default 0): for the first N steps whose set of scheduled requests differs from the previous
step's, one WARNING line per rank with the step counter, scheduled request ids (last 8 characters) with their
scheduled token counts, the previous step's ids, num_accepted_tokens per request after the stock call and after
the overlay, the stored counts used, and the previous step's valid sampled token counts. Reading those device
values forces a host sync in those steps (debug mode only): it changes timing, not arithmetic.

Cost: a skipped request's first step back yields one token (its drafts are lost, as in the stock engine), unless
B70_SPEC_RESUME_DRAFTS=1 (0.4.0, below) gives them back.

0.3.0 (2026-10-16): prefix caching (`--enable-prefix-caching --mamba-cache-mode align`). There the count the GDN
kernels read comes from the CPU array `input_batch.num_accepted_tokens_cpu`: after each step the align postprocess
(mamba_utils.postprocess_mamba_align_gpu) copies its per-request result there (1 where it already moved the state to
the block-aligned slot), `_prepare_inputs` keeps it only for rows of the previous step (others get 1,
gpu_model_runner.py:2137-2144), `preprocess_mamba` uses it as the accepted-token bias when the state crosses a block
(mamba_utils.py:1505-1523), and then the GPU count is rewritten from the CPU array (gpu_model_runner.py:4437-4444),
which undid 0.2.0's GPU-side restore. Campaign 24 (two requests, MTP5, align mode): 2 garbage and 27 of 36 replies
different from solo; without prefix caching 0 of 36. In align mode this overlay therefore stores the CPU value of a
request that sits out (after waiting for the event the stock code waits on in the same step anyway) and writes it
back into the CPU array, the host buffer and the GPU count of its row when it returns, after the stock
`_prepare_inputs` and before `preprocess_mamba`.

0.4.0 (2026-10-16): B70_SPEC_RESUME_DRAFTS=1 (default off; without it 0.4.0 behaves as 0.3.0) also keeps the
returning request's drafts, so its first step back is a normal verify step instead of one token. The drafter's
proposals for a request are made at the end of its last step (`runner._draft_token_ids`, one row per previous-step
row, gpu_model_runner.py:4701-4715); the stock code copies them into the next step's input ids only for rows that
ran in the previous step (`_prepare_input_ids`, :1909-1929). A request that sat out comes back with placeholder (-1)
drafts, and the rejection sampler compares the draft ids it gathers from input_ids inside `_prepare_inputs`
(`_calc_spec_decode_metadata`, :2939-2941), so every draft is rejected. Long prompts make this frequent: with
pure steps every prompt chunk is a step the writers sit out (2026-10-15 sweep, 16 users: mean acceptance length
4.1 one at a time on the long suite, 1.5-2.9 with 16 users, ten-second windows at 1.00).
What it does: before `_update_states`, the previous-step drafts of each request this step leaves out are copied
(device side) next to its stored count; after the stock `_prepare_inputs`, for a returning request whose scheduled
drafts are all placeholders, the stored drafts are written at its draft positions in `input_ids.gpu` (what the model
reads) and in `spec_decode_metadata.draft_token_ids` (what the rejection sampler compares). These are the drafts the
request would have been given had it not sat out: nothing it has seen changed while it waited. The verify step has
the same shape as before (1 + drafts rows); every output token is still the target model's own choice, so answers do
not change, only how many tokens a step accepts. Requests that ran in the previous step, requests with real
(non-placeholder) scheduled drafts, and steps with no returning request are untouched.

0.5.0 (2026-10-16): align mode, a new request's count (B70_SPEC_RESUME_FRESH, default 1; 0 gives 0.4.0). With
prefix caching and drafting, a request that starts from a cache hit pre-copies the hit block's state into its own
block with bias `num_accepted_tokens_cpu[row] - 1` (mamba_utils.py:1505-1523), so its count must be 1. The stock
code makes it 1 through `new_mask` in `_prepare_inputs` (gpu_model_runner.py:2132-2150), but only when
`prev_req_id_to_index` is non-empty. When every request of the previous step has finished, remove_request has
popped them all (gpu_input_batch.py:573-574), the dict is empty, and the "non-async" branch copies the CPU array
as is. add_request wrote 1 into the reused row (gpu_input_batch.py:484), but the finished request's last align
postprocess copies its own count into that row on the device (mamba_utils.py:1637-1639, non_blocking) and the
event wait just before the branch lets that copy land first: the new request reads its starting state shifted by
the previous request's accepted count. One sequence makes every hand-over such a step (Q3 on 2026-10-16: 37-39 of
64 long answers equal to the paused pass, all differing ones started from a hit, most at the first or second
token); two sequences only when both finish together (P1: 1-2 of 64). Fix: after the stock `_prepare_inputs`, rows
of requests not in the previous step with no stored count get 1 in the CPU array, the host buffer and the device
count, before `preprocess_mamba` reads them. Rows the stock code already set to 1 are not touched; non-align runs
never take this path.
"""
import os

_GUARD = '_b70_spec_resume_accepted'


def _state(runner):
    st = runner.__dict__.get('_b70_resume')
    if st is None:
        st = runner.__dict__['_b70_resume'] = {'stash': {}, 'drafts': {}, 'prev_sched': (), 'step': 0, 'debug': None,
                                               'debug_left': int(os.environ.get('B70_SPEC_RESUME_DEBUG', '0') or 0)}
    return st


def fresh_reset_enabled():
    return os.environ.get('B70_SPEC_RESUME_FRESH', '1').strip() != '0'


def resume_drafts_enabled():
    return os.environ.get('B70_SPEC_RESUME_DRAFTS', '').strip() == '1'


def _short(rid):
    return str(rid)[-8:]


def current_req_ids(runner):
    batch = runner.input_batch
    n = int(getattr(batch, 'num_reqs', len(batch.req_ids)))
    return [r for r in list(batch.req_ids)[:n] if r is not None]


def align_mode(runner):
    """Prefix caching with the recurrent state kept at block boundaries: the accepted count lives in the CPU array."""
    return getattr(getattr(runner, 'cache_config', None), 'mamba_cache_mode', None) == 'align'


def stash_unscheduled(runner, stash, scheduler_output):
    """Before _update_states: store the accepted counts of previous-step requests this step leaves out
    (device-side copies; in align mode the postprocessed CPU values)."""
    import torch
    prev = getattr(runner.input_batch, 'prev_req_id_to_index', None)
    scheduled = scheduler_output.num_scheduled_tokens
    finished = getattr(scheduler_output, 'finished_req_ids', ()) or ()
    if align_mode(runner):
        cpu = getattr(runner.input_batch, 'num_accepted_tokens_cpu', None)
        if not prev or cpu is None:
            return 0
        dropped = [(rid, int(idx)) for rid, idx in prev.items()
                   if rid not in scheduled and rid not in finished and int(idx) < len(cpu)]
        if not dropped:
            return 0
        event = getattr(runner, 'num_accepted_tokens_event', None)
        if event is not None:
            event.synchronize()           # the previous step's postprocess copy; stock waits on it this step anyway
        for rid, idx in dropped:
            stash[rid] = max(1, int(cpu[idx]))
        return len(dropped)
    counts = getattr(runner, 'valid_sampled_token_count_gpu', None)
    if not prev or counts is None:
        return 0
    dropped = [(rid, int(idx)) for rid, idx in prev.items()
               if rid not in scheduled and rid not in finished and int(idx) < counts.shape[0]]
    if not dropped:
        return 0
    index = torch.tensor([i for _, i in dropped], dtype=torch.long).to(counts.device, non_blocking=True)
    values = counts.index_select(0, index).to(torch.int32).clamp_(min=1)      # a copy: later steps reuse the buffer
    for j, (rid, _) in enumerate(dropped):
        stash[rid] = values[j:j + 1]
    return len(dropped)


def stash_drafts(runner, drafts_stash, scheduler_output):
    """Before _update_states: copy the drafts the previous step proposed for the requests this step leaves out."""
    import torch
    drafts = getattr(runner, '_draft_token_ids', None)
    prev = getattr(runner.input_batch, 'prev_req_id_to_index', None)
    if not torch.is_tensor(drafts) or drafts.dim() != 2 or not prev:
        return 0
    scheduled = scheduler_output.num_scheduled_tokens
    finished = getattr(scheduler_output, 'finished_req_ids', ()) or ()
    dropped = [(rid, int(idx)) for rid, idx in prev.items()
               if rid not in scheduled and rid not in finished and int(idx) < drafts.shape[0]]
    if not dropped:
        return 0
    index = torch.tensor([i for _, i in dropped], dtype=torch.long).to(drafts.device, non_blocking=True)
    rows = drafts.index_select(0, index)                     # a copy: the next step's drafter replaces the tensor
    for j, (rid, _) in enumerate(dropped):
        drafts_stash[rid] = rows[j]
    return len(dropped)


def restore_drafts(runner, drafts_stash, scheduler_output, result):
    """After the stock _prepare_inputs: give a returning request with placeholder drafts its stored drafts, in
    input_ids.gpu and in the spec-decode metadata's draft ids. Returns the number of draft tokens written."""
    import torch
    for rid in getattr(scheduler_output, 'finished_req_ids', ()) or ():
        drafts_stash.pop(rid, None)
    cached = getattr(scheduler_output, 'scheduled_cached_reqs', None)
    for rid in getattr(cached, 'resumed_req_ids', ()) or ():
        drafts_stash.pop(rid, None)
    if not drafts_stash:
        return 0
    prev = getattr(runner.input_batch, 'prev_req_id_to_index', None) or {}
    spec = getattr(scheduler_output, 'scheduled_spec_decode_tokens', None) or {}
    counts = scheduler_output.num_scheduled_tokens
    metadata = result[1] if isinstance(result, tuple) and len(result) > 1 else None
    pos = offset = 0
    input_pos, meta_pos, values = [], [], []
    for rid in current_req_ids(runner):
        drafts = list(spec.get(rid, ()))
        end = pos + int(counts.get(rid, 0))
        if rid not in prev:
            stored = drafts_stash.pop(rid, None)
            if stored is not None and drafts and all(t < 0 for t in drafts):
                k = min(len(drafts), int(stored.shape[0]))
                input_pos.extend(range(end - len(drafts), end - len(drafts) + k))
                meta_pos.extend(range(offset, offset + k))
                values.append(stored[:k])
        pos, offset = end, offset + len(drafts)
    if not values:
        return 0
    target = runner.input_ids.gpu
    flat = torch.cat(values).to(device=target.device, dtype=target.dtype)
    target.index_copy_(0, torch.tensor(input_pos, dtype=torch.long).to(target.device, non_blocking=True), flat)
    ids = getattr(metadata, 'draft_token_ids', None)
    if ids is not None:
        ids.index_copy_(0, torch.tensor(meta_pos, dtype=torch.long).to(ids.device, non_blocking=True),
                        flat.to(device=ids.device, dtype=ids.dtype))
    return len(input_pos)


def reset_fresh_rows(runner, rows):
    """Align mode, after the stock _prepare_inputs: rows of requests that did not run in the previous step and have
    no stored count (new requests) get count 1, which the stock code means to give them but skips when every
    previous-step request has finished (see 0.5.0 in the module docstring). Returns the rows changed."""
    import torch
    cpu = runner.input_batch.num_accepted_tokens_cpu
    changed = [r for r in rows if r < len(cpu) and int(cpu[r]) != 1]
    if not changed:
        return []
    host = getattr(runner.num_accepted_tokens, 'np', None)
    for r in changed:
        cpu[r] = 1
        if host is not None:
            host[r] = 1
    target = runner.num_accepted_tokens.gpu
    index = torch.tensor(changed, dtype=torch.long).to(target.device, non_blocking=True)
    target.index_fill_(0, index, 1)
    return changed


def restore_returning(runner, stash, scheduler_output):
    """After the stock _prepare_inputs: write stored counts for requests back after sitting out.
    Returns [(row, req_id, stored tensor)] for the rows fixed."""
    import torch
    for rid in getattr(scheduler_output, 'finished_req_ids', ()) or ():
        stash.pop(rid, None)
    cached = getattr(scheduler_output, 'scheduled_cached_reqs', None)
    for rid in getattr(cached, 'resumed_req_ids', ()) or ():
        stash.pop(rid, None)                                   # preempted and recomputed from the prompt
    prev = getattr(runner.input_batch, 'prev_req_id_to_index', None) or {}
    spec = getattr(scheduler_output, 'scheduled_spec_decode_tokens', None) or {}
    fixed, fresh, placeholder_drafts = [], [], False
    for row, rid in enumerate(current_req_ids(runner)):
        if rid in prev:
            continue                                           # ran last step: the stock correction covers it
        placeholder_drafts |= any(t < 0 for t in spec.get(rid, ()))
        value = stash.pop(rid, None)
        if value is not None:
            fixed.append((row, rid, value))
        else:
            fresh.append(row)
    if fresh and align_mode(runner) and fresh_reset_enabled():
        _state(runner)['fresh_resets'] = reset_fresh_rows(runner, fresh)
    if fixed and align_mode(runner):
        cpu = runner.input_batch.num_accepted_tokens_cpu
        host = getattr(runner.num_accepted_tokens, 'np', None)
        for row, _, value in fixed:
            cpu[row] = value                                   # what preprocess_mamba and the later GPU copy read
            if host is not None:
                host[row] = value
        target = runner.num_accepted_tokens.gpu
        index = torch.tensor([r for r, _, _ in fixed], dtype=torch.long).to(target.device, non_blocking=True)
        target.index_copy_(0, index, torch.tensor([v for _, _, v in fixed], dtype=target.dtype).to(target.device))
    elif fixed:
        target = runner.num_accepted_tokens.gpu
        index = torch.tensor([r for r, _, _ in fixed], dtype=torch.long).to(target.device, non_blocking=True)
        target.index_copy_(0, index, torch.cat([v for _, _, v in fixed]).to(device=target.device, dtype=target.dtype))
    if placeholder_drafts:
        total = int(scheduler_output.total_num_scheduled_tokens)
        runner.input_ids.gpu[:total].clamp_(min=0)
        cpu = getattr(runner.input_ids, 'cpu', None)
        if cpu is not None:
            cpu[:total].clamp_(min=0)
    return fixed


def wrap_update_states(original):
    def _update_states(self, scheduler_output, *args, **kwargs):
        st = _state(self)
        st['step'] += 1
        sched = dict(scheduler_output.num_scheduled_tokens)
        st['debug'] = None
        if st['debug_left'] > 0 and set(sched) != set(st['prev_sched']):
            st['debug_left'] -= 1
            valid = getattr(self, 'valid_sampled_token_count_gpu', None)
            prev = dict(getattr(self.input_batch, 'prev_req_id_to_index', None) or {})
            st['debug'] = {'step': st['step'], 'sched': sched, 'prev_sched': list(st['prev_sched']),
                           'prev_map': prev, 'valid_prev': valid.tolist() if valid is not None else None}   # sync
        st['prev_sched'] = tuple(sched)
        if getattr(self, 'use_async_spec_decode', False):
            stash_unscheduled(self, st['stash'], scheduler_output)
            if resume_drafts_enabled():
                stash_drafts(self, st['drafts'], scheduler_output)
        return original(self, scheduler_output, *args, **kwargs)
    setattr(_update_states, _GUARD, True)
    return _update_states


def wrap_prepare_inputs(original, stats=None, log=None):
    def _prepare_inputs(self, scheduler_output, *args, **kwargs):
        st = _state(self)
        result = original(self, scheduler_output, *args, **kwargs)
        if not getattr(self, 'use_async_spec_decode', False):
            return result
        dbg = st.get('debug')
        rows = current_req_ids(self)
        before = self.num_accepted_tokens.gpu[:len(rows)].clone() if dbg is not None else None
        written = restore_drafts(self, st['drafts'], scheduler_output, result) if resume_drafts_enabled() else 0
        fixed = restore_returning(self, st['stash'], scheduler_output)
        resets = st.get('fresh_resets')
        if stats is not None and resets:
            first = not stats.get('fresh')
            stats['fresh'] = stats.get('fresh', 0) + len(resets)
            if first and log is not None:
                log('b70_spec_resume_accepted: first new-request count reset, %d row(s) set to 1 after the previous '
                    "step's requests all finished (step %d)", len(resets), st['step'])
            st['fresh_resets'] = []
        if stats is not None and written:
            first = not stats.get('drafts')
            stats['drafts'] = stats.get('drafts', 0) + written
            if first and log is not None:
                log('b70_spec_resume_accepted: first draft restore, %d draft token(s) given back to returning '
                    'request(s) (step %d)', written, st['step'])
        if stats is not None and fixed:
            first = not stats.get('rows')
            stats['rows'] = stats.get('rows', 0) + len(fixed)
            if first and log is not None:
                log('b70_spec_resume_accepted: first restore, %d returning request(s) given their accepted-token '
                    'count (step %d)', len(fixed), st['step'])
        if dbg is not None and log is not None:
            after = self.num_accepted_tokens.gpu[:len(rows)].tolist()                                     # sync
            before = before.tolist()
            log('b70_spec_resume_debug step=%d sched=%s prev=%s prev_rows=%s acc_stock=%s acc_overlay=%s stored=%s '
                'valid_prev=%s', dbg['step'],
                {_short(r): n for r, n in dbg['sched'].items()}, [_short(r) for r in dbg['prev_sched']],
                {_short(r): i for r, i in dbg['prev_map'].items()},
                {_short(r): before[i] for i, r in enumerate(rows)}, {_short(r): after[i] for i, r in enumerate(rows)},
                {_short(r): int(v) if isinstance(v, int) else int(v.item()) for _, r, v in fixed}, dbg['valid_prev'])
        return result
    setattr(_prepare_inputs, _GUARD, True)
    return _prepare_inputs


def install(cls, log=None):
    if getattr(cls, _GUARD, False):
        return False
    stats = {}
    cls._update_states = wrap_update_states(cls._update_states)
    cls._prepare_inputs = wrap_prepare_inputs(cls._prepare_inputs, stats, log)
    setattr(cls, _GUARD, True)
    return True


def register():
    if os.environ.get('B70_SPEC_RESUME_ACCEPTED', '').strip() != '1':
        return
    from vllm.logger import init_logger
    from vllm.v1.worker import gpu_model_runner as module

    logger = init_logger('b70_spec_resume_accepted')
    if install(module.GPUModelRunner, logger.warning):
        logger.warning('b70_spec_resume_accepted 0.5.0: installed on GPUModelRunner._update_states/_prepare_inputs '
                       '(requests that sat out a step keep their accepted-token count; async speculative decoding '
                       'only; align-mode prefix caching handled; new-request count reset %s; drafts kept %s; debug steps %s)',
                       'on' if fresh_reset_enabled() else 'off', 'on' if resume_drafts_enabled() else 'off', os.environ.get('B70_SPEC_RESUME_DEBUG', '0') or '0')

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

Cost: a skipped request's first step back yields one token (its drafts are lost, as in the stock engine).
"""
import os

_GUARD = '_b70_spec_resume_accepted'


def _state(runner):
    st = runner.__dict__.get('_b70_resume')
    if st is None:
        st = runner.__dict__['_b70_resume'] = {'stash': {}, 'prev_sched': (), 'step': 0, 'debug': None,
                                               'debug_left': int(os.environ.get('B70_SPEC_RESUME_DEBUG', '0') or 0)}
    return st


def _short(rid):
    return str(rid)[-8:]


def current_req_ids(runner):
    batch = runner.input_batch
    n = int(getattr(batch, 'num_reqs', len(batch.req_ids)))
    return [r for r in list(batch.req_ids)[:n] if r is not None]


def stash_unscheduled(runner, stash, scheduler_output):
    """Before _update_states: store the device-side accepted counts of previous-step requests this step leaves out."""
    import torch
    prev = getattr(runner.input_batch, 'prev_req_id_to_index', None)
    counts = getattr(runner, 'valid_sampled_token_count_gpu', None)
    if not prev or counts is None:
        return 0
    scheduled = scheduler_output.num_scheduled_tokens
    finished = getattr(scheduler_output, 'finished_req_ids', ()) or ()
    dropped = [(rid, int(idx)) for rid, idx in prev.items()
               if rid not in scheduled and rid not in finished and int(idx) < counts.shape[0]]
    if not dropped:
        return 0
    index = torch.tensor([i for _, i in dropped], dtype=torch.long).to(counts.device, non_blocking=True)
    values = counts.index_select(0, index).to(torch.int32).clamp_(min=1)      # a copy: later steps reuse the buffer
    for j, (rid, _) in enumerate(dropped):
        stash[rid] = values[j:j + 1]
    return len(dropped)


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
    fixed, placeholder_drafts = [], False
    for row, rid in enumerate(current_req_ids(runner)):
        if rid in prev:
            continue                                           # ran last step: the stock correction covers it
        placeholder_drafts |= any(t < 0 for t in spec.get(rid, ()))
        value = stash.pop(rid, None)
        if value is not None:
            fixed.append((row, rid, value))
    if fixed:
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
        fixed = restore_returning(self, st['stash'], scheduler_output)
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
                {_short(r): int(v.item()) for _, r, v in fixed}, dbg['valid_prev'])
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
        logger.warning('b70_spec_resume_accepted 0.2.0: installed on GPUModelRunner._update_states/_prepare_inputs '
                       '(requests that sat out a step keep their accepted-token count; async speculative decoding '
                       'only; debug steps %s)', os.environ.get('B70_SPEC_RESUME_DEBUG', '0') or '0')

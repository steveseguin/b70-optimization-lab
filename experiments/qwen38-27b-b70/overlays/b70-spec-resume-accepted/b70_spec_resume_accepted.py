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
is removed from the persistent batch (gpu_model_runner.py:1257-1263); when it comes back its prev position is -1,
its count stays 1, and the kernels start from slot 0: the state after the first verify row of its last step,
missing a - 1 accepted tokens. Its next token is computed from a wrong recurrent state.
(The synchronous path loses it too: input_batch.add_request resets num_accepted_tokens_cpu to 1,
gpu_input_batch.py:484. This overlay handles the async path, which is what the lanes run.)

Evidence (2026-10-04, /mnt/fast-ai/bench-results/fp8-r314-mtp5-s4-20261004, 4 users, depth-5 MTP, pure steps):
every one of the 215 answers that differed from solo had, at or before its first wrong token, a step it sat out
right after a step that had accepted two or more tokens; the first wrong token is the first token of the step
after the skip in 40 of 57 short answers. Without the scheduling overlay no request is ever skipped and those
runs did not show this pattern.

What this overlay does (GPUModelRunner._prepare_inputs, class-level wrapper, host-side bookkeeping only):
  before the stock call, for every request that was in the previous step but is not in this one, it stores
    valid_sampled_token_count_gpu[its previous row] (a device-side copy, no host sync), clamped to >= 1;
  after the stock call, for every row whose request is back after sitting out (not in the previous step) and has
    a stored count, it writes that count into num_accepted_tokens.gpu[row], exactly what the stock correction
    would have written had the request not been skipped. Requests resumed from preemption (state recomputed from
    the prompt) and finished requests only drop their stored count.
  When a returning request carries placeholder drafts (-1: the real drafts of its last step were never handed to
    the scheduler under async scheduling), the -1 input ids are replaced by 0 in input_ids so no embedding lookup
    sees a negative id (one card: plain index; two cards: masked anyway). The rejection sampler still compares the
    -1 drafts, so all of them are rejected and the step yields one token, from row 0, as before.
Nothing changes for a request that ran in the previous step (the stock path), so a lone user's steps and
every step of a run without skipped requests are untouched.

Cost: a skipped request's first step back yields one token (its drafts are lost, as in the stock engine).
"""
import os

_GUARD = '_b70_spec_resume_accepted'


def current_req_ids(runner):
    batch = runner.input_batch
    n = int(getattr(batch, 'num_reqs', len(batch.req_ids)))
    return [r for r in list(batch.req_ids)[:n] if r is not None]


def stash_dropped(runner, stash):
    """Store the device-side accepted counts of requests that ran last step and are absent from this one."""
    import torch
    prev = getattr(runner.input_batch, 'prev_req_id_to_index', None)
    counts = getattr(runner, 'valid_sampled_token_count_gpu', None)
    if not prev or counts is None:
        return 0
    present = set(current_req_ids(runner))
    dropped = [(rid, int(idx)) for rid, idx in prev.items() if rid not in present and int(idx) < counts.shape[0]]
    if not dropped:
        return 0
    index = torch.tensor([i for _, i in dropped], dtype=torch.long).to(counts.device, non_blocking=True)
    values = counts.index_select(0, index).to(torch.int32).clamp_(min=1)      # a copy: later steps may reuse the buffer
    for j, (rid, _) in enumerate(dropped):
        stash[rid] = values[j:j + 1]
    return len(dropped)


def restore_returning(runner, stash, scheduler_output):
    """Write stored counts into num_accepted_tokens.gpu for requests back after sitting out. Returns rows fixed."""
    import torch
    for rid in getattr(scheduler_output, 'finished_req_ids', ()) or ():
        stash.pop(rid, None)
    cached = getattr(scheduler_output, 'scheduled_cached_reqs', None)
    for rid in getattr(cached, 'resumed_req_ids', ()) or ():
        stash.pop(rid, None)                                   # preempted and recomputed from the prompt
    prev = getattr(runner.input_batch, 'prev_req_id_to_index', None) or {}
    spec = getattr(scheduler_output, 'scheduled_spec_decode_tokens', None) or {}
    rows, values, placeholder_drafts = [], [], False
    for row, rid in enumerate(current_req_ids(runner)):
        if rid in prev:
            continue                                           # ran last step: the stock correction covers it
        placeholder_drafts |= any(t < 0 for t in spec.get(rid, ()))
        value = stash.pop(rid, None)
        if value is not None:
            rows.append(row)
            values.append(value)
    if rows:
        target = runner.num_accepted_tokens.gpu
        index = torch.tensor(rows, dtype=torch.long).to(target.device, non_blocking=True)
        target.index_copy_(0, index, torch.cat(values).to(device=target.device, dtype=target.dtype))
    if placeholder_drafts:
        total = int(scheduler_output.total_num_scheduled_tokens)
        runner.input_ids.gpu[:total].clamp_(min=0)
        cpu = getattr(runner.input_ids, 'cpu', None)
        if cpu is not None:
            cpu[:total].clamp_(min=0)
    return len(rows)


def wrap_prepare_inputs(original, stats=None, on_first=None):
    def _prepare_inputs(self, scheduler_output, *args, **kwargs):
        stash = self.__dict__.setdefault('_b70_resume_stash', {})
        if getattr(self, 'use_async_spec_decode', False):
            stash_dropped(self, stash)
        result = original(self, scheduler_output, *args, **kwargs)
        if getattr(self, 'use_async_spec_decode', False):
            fixed = restore_returning(self, stash, scheduler_output)
            if stats is not None and fixed:
                stats['rows'] = stats.get('rows', 0) + fixed
                if on_first is not None and stats['rows'] == fixed:
                    on_first(fixed)
        return result
    setattr(_prepare_inputs, _GUARD, True)
    return _prepare_inputs


def register():
    if os.environ.get('B70_SPEC_RESUME_ACCEPTED', '').strip() != '1':
        return
    from vllm.logger import init_logger
    from vllm.v1.worker import gpu_model_runner as module

    logger = init_logger('b70_spec_resume_accepted')
    cls = module.GPUModelRunner
    if getattr(cls, _GUARD, False):
        return
    stats = {}
    cls._prepare_inputs = wrap_prepare_inputs(
        cls._prepare_inputs, stats,
        lambda n: logger.warning('b70_spec_resume_accepted: first restore, %d returning request(s) given their '
                                 'accepted-token count', n))
    setattr(cls, _GUARD, True)
    logger.warning('b70_spec_resume_accepted: installed on GPUModelRunner._prepare_inputs (requests that sat out a '
                   'step keep their accepted-token count; async speculative decoding only)')

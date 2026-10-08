"""Pure scheduling steps for lossless multi-user serving (research overlay). Enabled with B70_EXCLUSIVE_PREFILL=1.

Why: with several users, vLLM packs whatever fits into each step: one user's prompt chunk next to other users'
decode rows, or two users' prompts together. On this lane a row's result depends, at the last bit, on what shares
its kernel call, so a few answers flip at exact logit ties (2026-10-04: 58-63 of 64 long-prompt answers equal to
their solo answers at 4, 8 and 16 users). A lone user never sees that, because a lone user's steps are pure.

What this does: every scheduling step is one of two kinds, and they alternate when both have work.
  P step  exactly one request's prompt chunk and nothing else, with the whole token budget, so its chunk
          boundaries are the ones it would have alone;
  D step  decode rows only, no prompt chunk, and no new request admitted.
It changes no arithmetic. It only decides who shares a step, using two hooks the scheduler already has:
`Request.next_decode_eligible_step` (skip a running request for one step) and `max_num_running_reqs` (block or
allow one admission), both restored after the call.

Cost: decode users wait while a prompt chunk is read (about a second per 4,096 tokens on two cards).

B70_EXCLUSIVE_PREFILL_BATCH=N (default 1): a prompt-only step may take up to N NEW requests together, but only inside
the range the censuses of 2026-10-04 prove bit-identical to reading each prompt alone: every prompt at least 17 tokens
and at most 512 tokens in the step (data/2026-10-04-kernel-census/). Longer or shorter prompts are read alone.
"""
import os


def _choose(prefilling, decoding, has_waiting, can_admit, last):
    """Return 'P', 'D' or None for this step."""
    want_p = bool(prefilling) or (has_waiting and can_admit)
    want_d = bool(decoding)
    if want_p and (not want_d or last == 'D'):
        return 'P'
    if want_d:
        return 'D'
    return 'P' if want_p else None


def admit_count(prompt_lengths, budget, batch, min_len=17, max_total=512):
    """How many of the leading waiting requests may share one prompt-only step.

    Several may share only inside the range the 2026-10-04 censuses prove bit-identical to reading each prompt alone:
    every prompt at least `min_len` tokens (below 17 the recurrent layers' BA projection takes another code path when
    the step holds more rows) and the step at most `max_total` tokens in all (the row range of the GEMM and
    normalisation censuses). Anything else is read alone, in its usual chunks. Always at least one."""
    lengths = list(prompt_lengths)
    count, used = 0, 0
    for length in lengths:
        if count >= batch or length is None or length < min_len or used + length > min(budget, max_total):
            break
        count += 1
        used += length
    return max(count, 1)


def register():
    if os.environ.get('B70_EXCLUSIVE_PREFILL', '').strip() != '1':
        return
    batch = max(1, int(os.environ.get('B70_EXCLUSIVE_PREFILL_BATCH', '1') or '1'))
    min_len = int(os.environ.get('B70_EXCLUSIVE_PREFILL_BATCH_MIN_LEN', '17'))
    max_total = int(os.environ.get('B70_EXCLUSIVE_PREFILL_BATCH_TOKENS', '512'))
    from vllm.logger import init_logger
    from vllm.v1.core.sched import scheduler as module

    logger = init_logger('b70_exclusive_prefill')
    cls = module.Scheduler
    if getattr(cls, '_b70_exclusive_prefill', False):
        return
    original = cls.schedule
    stats = {'P': 0, 'D': 0, 'none': 0}

    def schedule(self, *args, **kwargs):
        running = list(self.running)
        prefilling = [r for r in running if r.is_prefill_chunk]
        decoding = [r for r in running if not r.is_prefill_chunk]
        has_waiting = bool(self.waiting) or bool(self.skipped_waiting)
        limit = self.max_num_running_reqs
        can_admit = len(running) < limit
        last = self.__dict__.get('_b70_last_step_kind', 'D')
        kind = _choose(prefilling, decoding, has_waiting, can_admit, last)
        if kind is None:
            stats['none'] += 1
            return original(self, *args, **kwargs)
        step = self.current_step + 1          # schedule() increments it first
        if kind == 'P' and prefilling:
            hide = [r for r in running if r is not prefilling[0]]
            allow = len(running)              # nobody new this step
        elif kind == 'P':
            hide = running                    # new requests only: one, or several short prompts that each fit whole
            fresh = 1
            if batch > 1:
                try:
                    lengths = [getattr(r, 'num_prompt_tokens', None) if getattr(r, 'num_computed_tokens', 0) == 0 else None
                               for r in list(self.skipped_waiting) + list(self.waiting)]
                    fresh = admit_count(lengths, self.max_num_scheduled_tokens, min(batch, limit - len(running)),
                                        min_len, max_total)
                except Exception:      # an unfamiliar queue type: fall back to one at a time
                    fresh = 1
            stats['admitted_together'] = max(stats.get('admitted_together', 1), fresh)
            allow = len(running) + fresh
        else:
            hide = prefilling
            allow = len(running)
        for request in hide:
            request.next_decode_eligible_step = step + 1
        self.max_num_running_reqs = max(allow, 1)
        try:
            return original(self, *args, **kwargs)
        finally:
            self.max_num_running_reqs = limit
            self.__dict__['_b70_last_step_kind'] = kind
            stats[kind] += 1
            total = stats['P'] + stats['D']
            if total in (1, 1000, 20000):
                logger.warning('b70_exclusive_prefill: %d prompt-only and %d decode-only steps so far; most prompts in one '
                               'step %d', stats['P'], stats['D'], stats.get('admitted_together', 1))

    cls.schedule = schedule
    cls._b70_exclusive_prefill = True
    logger.warning('b70_exclusive_prefill: installed on Scheduler (pure prompt-only and decode-only steps; up to %d short '
                   'prompts per prompt-only step)', batch)

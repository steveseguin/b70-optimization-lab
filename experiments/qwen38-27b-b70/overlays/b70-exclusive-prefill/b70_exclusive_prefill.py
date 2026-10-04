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


def register():
    if os.environ.get('B70_EXCLUSIVE_PREFILL', '').strip() != '1':
        return
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
            hide = running                    # one new request, alone
            allow = len(running) + 1
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
                logger.warning('b70_exclusive_prefill: %d prompt-only and %d decode-only steps so far', stats['P'], stats['D'])

    cls.schedule = schedule
    cls._b70_exclusive_prefill = True
    logger.warning('b70_exclusive_prefill: installed on Scheduler (pure prompt-only and decode-only steps)')

"""Copy-from-context draft tokens on top of the MTP drafts (research overlay). Enabled with B70_COPY_DRAFT=1.

Plan: notes/2026-10-04-copy-draft-sizing-prereg.md. The server drafts k tokens per step with the MTP head and checks
them in one verify pass. When the last N >= B70_COPY_DRAFT_MIN_MATCH (default 6) tokens of a request's context
(prompt + accepted output) occurred earlier in that context, this replaces that request's k MTP draft tokens with the
k tokens that followed the earlier occurrence (longest match up to B70_COPY_DRAFT_MAX_MATCH, default 8; most recent
occurrence on ties). Shapes never change: every request still gets exactly k draft tokens, only the ids differ, and
the verify pass compares the target's choice against the very ids that were fed in. Lossless by construction for
greedy requests; non-greedy rows and anything doubtful keep the MTP draft.

Where the context comes from (vLLM 0.29 V1 runner, read from the R310 image):
- async scheduling (the default for the MTP method with the multiproc executor): the worker never writes the accepted
  tokens into `input_batch.token_ids_cpu` (bookkeeping writes -1 placeholders), and the accepted tokens of the step
  that just verified are on the card only. This overlay copies each step's sampled-token rows to the host on a side
  stream right after sampling (before the MTP drafter is queued), keeps its own per-request history (prompt + accepted
  tokens), and waits for that small copy at the start of the next step's input preparation (`_prepare_input_ids`),
  just before the drafts are scattered into the input ids. That wait is the one host/card sync the stock async path
  does not do: the host stops running ahead of the card at the end of the verify pass (the MTP drafter is already
  queued, so the card keeps working while the host finishes input preparation).
- sync scheduling (--no-async-scheduling): the drafts go to the scheduler through `take_draft_token_ids`, after
  bookkeeping has written the accepted tokens into `token_ids_cpu`; the replacement is done on those host lists, so no
  extra sync at all.

Every TP rank makes the same decision from the same sampled tokens (no readiness polling, no rank-local state), so the
ranks always feed identical ids.
"""
import os
from bisect import bisect_right

_PLACEHOLDER = -1


# ----------------------------------------------------------------------------------------------------------------------
# Pure lookup (no torch)
# ----------------------------------------------------------------------------------------------------------------------

def find_copy_draft(context, k, min_match, max_match):
    """Reference lookup. The longest suffix of `context` of length max_match..min_match that occurs earlier with at
    least k tokens after that occurrence; the most recent such occurrence; returns the k tokens that follow it, or
    None. Occurrences may overlap the suffix (periodic text); the k tokens must lie inside the context."""
    context = list(context)
    length = len(context)
    if k < 1 or min_match < 1 or max_match < min_match:
        return None
    for n in range(min(max_match, length - k), min_match - 1, -1):
        suffix = context[length - n:]
        for start in range(length - n - k, -1, -1):
            if context[start:start + n] == suffix:
                return context[start + n:start + n + k]
    return None


class CopyIndex:
    """Incremental version of `find_copy_draft` for one request: an index from each min_match-gram to the start
    positions where it occurs, extended as tokens are appended. A lookup scans the occurrences of the last gram from
    the most recent backwards and extends each match backwards up to max_match. `max_scan` caps the occurrences
    examined per lookup (None = all, which is exactly `find_copy_draft`)."""

    __slots__ = ('min_match', 'max_match', 'max_scan', 'tokens', '_starts')

    def __init__(self, min_match, max_match, max_scan=None, tokens=()):
        if min_match < 1 or max_match < min_match:
            raise ValueError('need 1 <= min_match <= max_match')
        self.min_match, self.max_match, self.max_scan = min_match, max_match, max_scan
        self.tokens = []
        self._starts = {}
        if tokens:
            self.extend(tokens)

    def __len__(self):
        return len(self.tokens)

    def extend(self, new_tokens):
        tokens, m, starts = self.tokens, self.min_match, self._starts
        old = len(tokens)
        tokens.extend(int(t) for t in new_tokens)
        for start in range(max(0, old - m + 1), len(tokens) - m + 1):
            key = tuple(tokens[start:start + m])
            positions = starts.get(key)
            if positions is None:
                starts[key] = [start]
            else:
                positions.append(start)

    def propose(self, k):
        tokens, m = self.tokens, self.min_match
        length = len(tokens)
        if k < 1 or length < m + k:
            return None
        positions = self._starts.get(tuple(tokens[length - m:]))
        if not positions:
            return None
        limit = length - m - k            # latest gram start that still has k tokens after the gram
        tail = length - m - 1             # token just before the suffix gram
        extra_max = self.max_match - m
        best_extra, best_start, scanned = -1, -1, 0
        i = bisect_right(positions, limit) - 1
        while i >= 0:
            start = positions[i]
            extra = 0
            while extra < extra_max and start - 1 - extra >= 0 and tokens[start - 1 - extra] == tokens[tail - extra]:
                extra += 1
            if extra > best_extra:
                best_extra, best_start = extra, start
                if extra == extra_max:
                    break
            scanned += 1
            if self.max_scan and scanned >= self.max_scan:
                break
            i -= 1
        if best_start < 0:
            return None
        begin = best_start + m
        return tokens[begin:begin + k]


def accepted_prefix(row):
    """Tokens of one sampled row up to the first placeholder (rejected positions are -1)."""
    out = []
    for token in row:
        if token < 0:
            break
        out.append(int(token))
    return out


class CopyDraftBook:
    """Per-request histories, the copy decision, and counters. No torch."""

    def __init__(self, k, min_match, max_match, max_scan=256):
        self.k, self.min_match, self.max_match, self.max_scan = k, min_match, max_match, max_scan
        self.index = {}           # req_id -> CopyIndex
        self.poisoned = set()     # req_ids whose history can no longer be trusted (never rebuilt in async mode)
        self.last_kind = {}       # req_id -> 'copy' | 'mtp' for the draft now waiting for verification
        self.stats = dict(steps=0, steps_with_copy=0, rows=0, copies=0, copy_verified=0, copy_accepted=0,
                          mtp_verified=0, mtp_accepted=0, rebuilds=0, skipped_steps=0, poisoned=0)

    def _new(self, tokens):
        return CopyIndex(self.min_match, self.max_match, self.max_scan, tokens)

    def _attribute(self, req_id, num_new):
        kind = self.last_kind.pop(req_id, None)
        if kind is not None and num_new >= 1:
            self.stats[kind + '_verified'] += 1
            self.stats[kind + '_accepted'] += num_new - 1

    def drop(self, req_id, poison=False):
        self.index.pop(req_id, None)
        self.last_kind.pop(req_id, None)
        if poison and req_id not in self.poisoned:
            self.poisoned.add(req_id)
            self.stats['poisoned'] += 1

    def prune(self, live):
        for req_id in [r for r in self.index if r not in live]:
            self.drop(req_id)
        if self.poisoned:
            self.poisoned = {r for r in self.poisoned if r in live}

    def observe_async(self, req_id, prompt, accepted, first):
        """Async mode: append one step's accepted tokens. A history is only started at the step that completed the
        prompt (`first`), from the prompt; any other unknown request is poisoned rather than guessed."""
        if req_id in self.poisoned or not accepted:
            return
        index = self.index.get(req_id)
        if index is None:
            if not first or prompt is None or any(t < 0 for t in prompt):
                self.drop(req_id, poison=True)
                return
            self.index[req_id] = self._new(list(prompt) + list(accepted))
            return
        self._attribute(req_id, len(accepted))
        index.extend(accepted)

    def observe_sync(self, req_id, row, count):
        """Sync mode: `row[:count]` is the request's full accepted history (token_ids_cpu, num_tokens_no_spec)."""
        index = self.index.get(req_id)
        have = len(index) if index is not None else 0
        if index is None or have > count or (have and int(row[have - 1]) != index.tokens[-1]):
            tokens = _as_list(row[:count])
            self.last_kind.pop(req_id, None)
            if any(t < 0 for t in tokens):
                self.drop(req_id)
                return
            self.index[req_id] = self._new(tokens)
            if index is not None:
                self.stats['rebuilds'] += 1
            return
        if count > have:
            new = _as_list(row[have:count])
            if any(t < 0 for t in new):
                self.drop(req_id)
                return
            self._attribute(req_id, len(new))
            index.extend(new)

    def choose(self, req_id, k):
        """The copy draft for this request, or None (keep MTP). Records which kind is now waiting for verification."""
        index = self.index.get(req_id)
        draft = index.propose(k) if index is not None and k == self.k else None
        if draft is not None and len(draft) != k:
            draft = None
        if index is not None:
            self.last_kind[req_id] = 'copy' if draft is not None else 'mtp'
        return draft

    def step(self, rows, copies):
        self.stats['steps'] += 1
        self.stats['rows'] += rows
        self.stats['copies'] += copies
        if copies:
            self.stats['steps_with_copy'] += 1

    def summary(self, mode):
        s = self.stats

        def rate(kind):
            verified = s[kind + '_verified']
            return '%.2f/%d over %d rows' % (s[kind + '_accepted'] / verified, self.k, verified) if verified else 'n/a'
        return ('b70_copy_draft[%s]: %d draft steps, %d with a copy draft (%.1f%%), %d of %d rows copied; '
                'accepted per verify: copy %s, mtp %s; skipped steps %d, history rebuilds %d, poisoned %d' % (
                    mode, s['steps'], s['steps_with_copy'], 100.0 * s['steps_with_copy'] / max(1, s['steps']),
                    s['copies'], s['rows'], rate('copy'), rate('mtp'), s['skipped_steps'], s['rebuilds'],
                    s['poisoned']))


def _as_list(values):
    return [int(t) for t in (values.tolist() if hasattr(values, 'tolist') else values)]


def settings_from_env(environ=None):
    environ = os.environ if environ is None else environ
    min_match = int(environ.get('B70_COPY_DRAFT_MIN_MATCH', '6'))
    max_match = int(environ.get('B70_COPY_DRAFT_MAX_MATCH', '8'))
    max_scan = int(environ.get('B70_COPY_DRAFT_MAX_SCAN', '256'))
    log_every = int(environ.get('B70_COPY_DRAFT_LOG_EVERY', '2000'))
    if min_match < 1 or max_match < min_match:
        raise ValueError('b70_copy_draft: need 1 <= B70_COPY_DRAFT_MIN_MATCH <= B70_COPY_DRAFT_MAX_MATCH')
    return dict(min_match=min_match, max_match=max_match, max_scan=max_scan or None, log_every=max(1, log_every))


# ----------------------------------------------------------------------------------------------------------------------
# Runner glue (torch)
# ----------------------------------------------------------------------------------------------------------------------

class StreamCopier:
    """Copy a step's sampled-token rows to pinned host memory on a side stream, ordered right after sampling."""

    def __init__(self, torch):
        self.torch = torch
        self.stream = torch.cuda.Stream()
        self.event = torch.Event()
        self.buffer = None

    def start(self, sampled):
        torch = self.torch
        rows, width = sampled.shape
        if self.buffer is None or self.buffer.dtype != sampled.dtype or self.buffer.shape[0] < rows \
                or self.buffer.shape[1] < width:
            self.buffer = torch.empty((max(rows, 8), width), dtype=sampled.dtype, pin_memory=True)
        self.stream.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(self.stream):
            self.buffer[:rows, :width].copy_(sampled, non_blocking=True)
            self.event.record()
        return _Handle(self, sampled, rows, width)


class _Handle:
    def __init__(self, copier, source, rows, width):
        self.copier, self.source, self.rows, self.width = copier, source, rows, width

    def wait(self):
        self.copier.event.synchronize()
        self.source = None
        return self.copier.buffer[:self.rows, :self.width].tolist()


class ImmediateCopier:
    """Same interface without streams (CPU tests, or a device without side streams)."""

    def start(self, sampled):
        rows = sampled.tolist()
        return type('H', (), {'wait': staticmethod(lambda: rows)})()


class _Pending:
    __slots__ = ('handle', 'req_ids', 'discard', 'greedy', 'first', 'drafts', 'replace_ok', 'structured')


class _State:
    def __init__(self, mode, k, book, copier, log_every):
        self.mode, self.k, self.book, self.copier, self.log_every = mode, k, book, copier, log_every
        self.pending = None
        self.live = None          # the draft tensor our propose wrapper returned last
        self.proposed = False
        self.disabled = False
        self.announced = False


def _is_mtp(spec):
    method = str(getattr(spec, 'method', '') or '')
    return method == 'mtp' or method.endswith('_mtp')


def _state_for(runner, torch, logger, settings, copier_factory):
    state = getattr(runner, '_b70_copy_draft_state', None)
    if state is not None:
        return None if state is False or state.disabled else state
    spec = getattr(runner, 'speculative_config', None)
    reason = None
    if spec is None:
        reason = 'no speculative decoding'
    elif not _is_mtp(spec):
        reason = 'method %r is not MTP' % getattr(spec, 'method', None)
    elif getattr(spec, 'disable_padded_drafter_batch', False):
        reason = 'padded drafter batch disabled'
    elif getattr(getattr(runner, 'parallel_config', None), 'pipeline_parallel_size', 1) > 1:
        reason = 'pipeline parallel'
    elif getattr(runner, 'enable_prompt_embeds', False):
        reason = 'prompt embeds'
    if reason is not None:
        logger.warning('b70_copy_draft: not active (%s); drafts are left as they are', reason)
        runner._b70_copy_draft_state = False
        return None
    k = int(runner.num_spec_tokens)
    mode = 'async' if runner.use_async_scheduling else 'sync'
    book = CopyDraftBook(k, settings['min_match'], settings['max_match'], settings['max_scan'])
    copier = (copier_factory or (lambda: StreamCopier(torch)))() if mode == 'async' else None
    state = _State(mode, k, book, copier, settings['log_every'])
    runner._b70_copy_draft_state = state
    logger.warning('b70_copy_draft: active, %s scheduling, %d draft tokens, match %d..%d tokens', mode, k,
                   settings['min_match'], settings['max_match'])
    return state


def _fail(state, logger, where):
    state.disabled = True
    state.pending = None
    logger.exception('b70_copy_draft: error in %s; disabled, MTP drafts left untouched from here on', where)


def _ingest(runner, state, pending):
    rows = pending.handle.wait()
    book, requests = state.book, runner.requests
    for i, req_id in enumerate(pending.req_ids):
        if pending.discard[i]:
            continue
        accepted = accepted_prefix(rows[i])
        if not accepted:
            continue
        request = requests.get(req_id)
        prompt = getattr(request, 'prompt_token_ids', None) if request is not None else None
        book.observe_async(req_id, prompt, accepted, pending.first[i])
    book.prune(requests)


def merge_drafts(torch, drafts, copies):
    """`drafts` [n, k] with the rows in `copies` {row: [k ids]} replaced; out of place, same shape and dtype."""
    rows, k = drafts.shape
    pin = drafts.device.type != 'cpu'
    values = [copies.get(i) or [0] * k for i in range(rows)]
    values = torch.tensor(values, dtype=drafts.dtype, pin_memory=pin).to(drafts.device, non_blocking=True)
    mask = torch.tensor([i in copies for i in range(rows)], dtype=torch.bool, pin_memory=pin)
    mask = mask.to(drafts.device, non_blocking=True)
    return torch.where(mask.unsqueeze(1), values, drafts)


def _maybe_log(state, logger):
    if not state.announced and state.book.stats['copies']:
        state.announced = True
        logger.warning('b70_copy_draft: first copy draft placed')
    if state.book.stats['steps'] % state.log_every == 0:
        logger.warning(state.book.summary(state.mode))


def _replace_async(runner, state, torch, logger):
    pending, state.pending = state.pending, None
    _ingest(runner, state, pending)
    if (not pending.replace_ok or pending.structured or runner._draft_token_ids is not pending.drafts
            or runner._draft_token_ids is not state.live or getattr(runner, '_draft_token_req_ids', None) is not None
            or getattr(runner, '_draft_probs', None) is not None):
        state.book.stats['skipped_steps'] += 1
        return
    copies, rows = {}, 0
    for i, req_id in enumerate(pending.req_ids):
        if pending.discard[i] or not pending.greedy[i]:
            continue
        rows += 1
        draft = state.book.choose(req_id, state.k)
        if draft is not None:
            copies[i] = draft
    state.book.step(rows, len(copies))
    if copies:
        runner._draft_token_ids = merge_drafts(torch, pending.drafts, copies)
    _maybe_log(state, logger)


def _apply_sync(runner, state, result, logger):
    if (not state.proposed or runner._draft_token_ids is not state.live
            or getattr(runner, '_draft_probs', None) is not None):
        state.book.stats['skipped_steps'] += 1
        return
    state.proposed = False
    batch, book = runner.input_batch, state.book
    discard = runner.discard_request_mask.np
    copies, rows = 0, 0
    for j, req_id in enumerate(result.req_ids):
        i = batch.req_id_to_index.get(req_id)
        if i is None:
            continue
        book.observe_sync(req_id, batch.token_ids_cpu[i], int(batch.num_tokens_no_spec[i]))
        draft_row = result.draft_token_ids[j]
        if discard[i] or req_id not in batch.greedy_reqs or len(draft_row) != state.k:
            continue
        rows += 1
        draft = book.choose(req_id, state.k)
        if draft is not None:
            draft_row[:] = draft
            copies += 1
    book.prune(runner.requests)
    book.step(rows, copies)
    _maybe_log(state, logger)


def install(cls, torch, logger, settings, copier_factory=None):
    """Patch the runner class once. `copier_factory` replaces the side-stream copier (tests)."""
    if getattr(cls, '_b70_copy_draft', False):
        return
    original_propose = cls.propose_draft_token_ids
    original_prepare_ids = cls._prepare_input_ids
    original_take = cls.take_draft_token_ids
    original_sample = cls.sample_tokens

    def propose_draft_token_ids(self, scheduler_output, sampled_token_ids, *args, **kwargs):
        state = _state_for(self, torch, logger, settings, copier_factory)
        if state is None:
            return original_propose(self, scheduler_output, sampled_token_ids, *args, **kwargs)
        handle = None
        if state.mode == 'async':
            try:
                if state.pending is not None:   # not consumed by an input preparation: still take its tokens
                    pending, state.pending = state.pending, None
                    _ingest(self, state, pending)
                if torch.is_tensor(sampled_token_ids) and sampled_token_ids.dim() == 2:
                    handle = state.copier.start(sampled_token_ids)   # queued before the MTP drafter
            except Exception:
                _fail(state, logger, 'propose (before)')
                return original_propose(self, scheduler_output, sampled_token_ids, *args, **kwargs)
        drafts = original_propose(self, scheduler_output, sampled_token_ids, *args, **kwargs)
        if state.disabled:
            return drafts
        try:
            state.proposed = True
            state.live = drafts
            if state.mode == 'async':
                if handle is None:
                    self._b70_copy_draft_poison_batch = True
                    return drafts
                rows = sampled_token_ids.shape[0]
                req_ids = list(self.input_batch.req_ids)
                pending = _Pending()
                pending.handle = handle
                pending.req_ids = req_ids[:rows]
                pending.discard = [bool(x) for x in self.discard_request_mask.np[:rows]]
                greedy = self.input_batch.greedy_reqs
                pending.greedy = [r in greedy for r in pending.req_ids]
                scheduled = scheduler_output.num_scheduled_tokens
                first = []
                for req_id in pending.req_ids:
                    request = self.requests.get(req_id)
                    prompt = getattr(request, 'prompt_token_ids', None) if request is not None else None
                    first.append(prompt is not None and request.num_computed_tokens + scheduled.get(req_id, 0)
                                 == len(prompt))
                pending.first = first
                pending.drafts = drafts
                pending.replace_ok = (torch.is_tensor(drafts) and drafts.dim() == 2 and drafts.shape[0] == rows
                                      and len(req_ids) == rows and drafts.shape[1] == state.k
                                      and not drafts.is_floating_point())
                pending.structured = bool(getattr(scheduler_output, 'has_structured_output_requests', False))
                state.pending = pending
        except Exception:
            _fail(state, logger, 'propose (after)')
        return drafts

    def _prepare_input_ids(self, *args, **kwargs):
        state = getattr(self, '_b70_copy_draft_state', None)
        if state and not state.disabled and state.mode == 'async' and state.pending is not None:
            try:
                _replace_async(self, state, torch, logger)
            except Exception:
                _fail(state, logger, '_prepare_input_ids')
        return original_prepare_ids(self, *args, **kwargs)

    def take_draft_token_ids(self):
        result = original_take(self)
        state = getattr(self, '_b70_copy_draft_state', None)
        if state and not state.disabled and state.mode == 'sync' and result is not None:
            try:
                _apply_sync(self, state, result, logger)
            except Exception:
                _fail(state, logger, 'take_draft_token_ids')
        return result

    def sample_tokens(self, *args, **kwargs):
        state = getattr(self, '_b70_copy_draft_state', None)
        real_step = getattr(self, 'execute_model_state', None) is not None
        if state:
            state.proposed = False
        self._b70_copy_draft_poison_batch = False
        output = original_sample(self, *args, **kwargs)
        state = getattr(self, '_b70_copy_draft_state', None)
        if state and not state.disabled and state.mode == 'async' and real_step \
                and (not state.proposed or self._b70_copy_draft_poison_batch):
            # Tokens were accepted that this overlay did not see (drafter skipped): never trust these histories again.
            for req_id in list(self.input_batch.req_ids):
                state.book.drop(req_id, poison=True)
        return output

    cls.propose_draft_token_ids = propose_draft_token_ids
    cls._prepare_input_ids = _prepare_input_ids
    cls.take_draft_token_ids = take_draft_token_ids
    cls.sample_tokens = sample_tokens
    cls._b70_copy_draft = True


def register():
    if os.environ.get('B70_COPY_DRAFT', '').strip() != '1':
        return
    settings = settings_from_env()
    import torch
    from vllm.logger import init_logger
    from vllm.v1.worker import gpu_model_runner as module

    install(module.GPUModelRunner, torch, init_logger('b70_copy_draft'), settings)

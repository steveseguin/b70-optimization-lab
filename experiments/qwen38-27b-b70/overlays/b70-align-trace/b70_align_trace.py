"""Align-mode recurrent-state trace (research overlay, debug only). B70_ALIGN_TRACE=1.

Written 2026-10-16 for the prefix cache + drafting difference (notes/2026-10-04-fp8-multiuser-prereg.md, Q3): with
one sequence and the long prompts sent at once, a third of the answers that start from a cache hit differ from the
paused one-at-a-time pass, usually at the first or second token. This logs, per step and per row, what the align
pre-copy decides (mamba_utils.preprocess_mamba: previous and current state column, accepted-token bias, the
recurrent group's block ids for the row) and what the scheduler handed the worker (new requests with their cache
hit and block ids, new block ids of running requests, finished ids), so a differing answer can be traced to the
block it read its starting state from.

CPU values only, read where the stock code already has them on the host: no device reads, no syncs; it does not
change what is computed. Logging runs only while the flag file exists (default /root/.cache/vllm/b70-align-trace.on,
the run's cache folder on the host), so a live server can be traced for one probe and not the next. Output: one
JSON line per step to B70_ALIGN_TRACE_DIR (default /root/.cache/vllm/b70-align-trace)/rank<r>-<pid>.jsonl, rank 0
only unless B70_ALIGN_TRACE_ALL_RANKS=1.

B70_ALIGN_TRACE_DEEP=1 (0.2.0) also checksums, per row, the recurrent state the step's kernels start from (column
curr + count - 1 after the pre-copy) in the first layer of each recurrent group: sum and absolute sum of each state
tensor, computed on the device right after the pre-copy, copied to pinned host memory without waiting, and written
as {"deep": step, ...} lines once their event has completed (polled each step, never waited on). It adds a few small
kernels per step; it does not wait for the device or change what is computed.
"""
import json
import os

_GUARD = '_b70_align_trace'
FLAG = os.environ.get('B70_ALIGN_TRACE_FLAG', '/root/.cache/vllm/b70-align-trace.on')
OUT_DIR = os.environ.get('B70_ALIGN_TRACE_DIR', '/root/.cache/vllm/b70-align-trace')
_state = {'step': 0, 'fh': None, 'sched': None, 'rank': None}
DEEP = os.environ.get('B70_ALIGN_TRACE_DEEP', '').strip() == '1'
_deep = {'pool': None, 'next': 0, 'pending': [], 'layers': None}
POOL, WIDTH = 256, 96


def _deep_layers(kv_cache_config, gids):
    if _deep['layers'] is None:
        _deep['layers'] = [(gid, kv_cache_config.kv_cache_groups[gid].layer_names[0]) for gid in gids]
    return _deep['layers']


def drain_deep(block=False):
    keep = []
    for step, meta, host, n, event in _deep['pending']:
        if block:
            event.synchronize()
        if event.query():
            vals = host[:n].tolist()
            j = 0
            for m in meta:
                k = m.pop('n')
                m['sums'] = [round(v, 6) for v in vals[j:j + k]]
                j += k
            _write({'deep': step, 'rows': meta})
        else:
            keep.append((step, meta, host, n, event))
    _deep['pending'] = keep


def enqueue_deep(step, rows, input_batch, forward_context, kv_cache_config, gids):
    import torch
    if _deep['pool'] is None:
        _deep['pool'] = [torch.empty(WIDTH, dtype=torch.float64, pin_memory=True) for _ in range(POOL)]
    drain_deep()
    if len(_deep['pending']) >= POOL - 1:
        drain_deep(block=True)
    vals, meta = [], []
    for row in rows:
        i = row['row']
        count = int(input_batch.num_accepted_tokens_cpu[i])
        entry = {'rid': row['rid'], 'count_after': count, 'layers': [], 'n': 0}
        for gid, name in _deep_layers(kv_cache_config, gids):
            blocks = row['mamba_blocks'].get(gid, [])
            col = (row.get('curr') or 0) + max(count - 1, 0)
            if col >= len(blocks):
                continue
            block = blocks[col]
            for t in forward_context[name].kv_cache:
                x = t[block].float()
                vals += [x.sum(), x.abs().sum()]
                entry['n'] += 2
            entry['layers'].append({'gid': gid, 'col': col, 'block': block})
        meta.append(entry)
    if not vals or len(vals) > WIDTH:
        return
    gpu = torch.stack(vals).double()
    host = _deep['pool'][_deep['next'] % POOL]
    _deep['next'] += 1
    host[:len(vals)].copy_(gpu, non_blocking=True)
    event = torch.xpu.Event()
    event.record()
    _deep['pending'].append((step, meta, host, len(vals), event))


def _rank():
    if _state['rank'] is None:
        try:
            import torch.distributed as dist
            _state['rank'] = dist.get_rank() if dist.is_initialized() else 0
        except Exception:
            _state['rank'] = 0
    return _state['rank']


def active():
    if _rank() != 0 and os.environ.get('B70_ALIGN_TRACE_ALL_RANKS') != '1':
        return False
    return os.path.exists(FLAG)


def _write(rec):
    fh = _state['fh']
    if fh is None:
        os.makedirs(OUT_DIR, exist_ok=True)
        fh = open(os.path.join(OUT_DIR, f'rank{_rank()}-{os.getpid()}.jsonl'), 'a', buffering=1)
        _state['fh'] = fh
    fh.write(json.dumps(rec, separators=(',', ':')) + '\n')


def _ids(block_ids):
    """Per-group block id lists (tuple of lists or None) as plain lists."""
    if block_ids is None:
        return None
    return [list(map(int, g)) for g in block_ids]


def summarize_scheduler_output(so):
    new = []
    for r in getattr(so, 'scheduled_new_reqs', ()) or ():
        new.append({'rid': r.req_id, 'computed': int(r.num_computed_tokens),
                    'prompt_len': len(r.prompt_token_ids or ()), 'blocks': _ids(r.block_ids)})
    cached = []
    c = getattr(so, 'scheduled_cached_reqs', None)
    if c is not None:
        resumed = set(getattr(c, 'resumed_req_ids', ()) or ())
        for i, rid in enumerate(c.req_ids):
            cached.append({'rid': rid, 'computed': int(c.num_computed_tokens[i]),
                           'new_blocks': _ids(c.new_block_ids[i]), 'resumed': rid in resumed})
    spec = getattr(so, 'scheduled_spec_decode_tokens', None) or {}
    return {'new': new, 'cached': cached, 'finished': sorted(getattr(so, 'finished_req_ids', ()) or ()),
            'sched': {k: int(v) for k, v in so.num_scheduled_tokens.items()},
            'spec': {k: [int(t) for t in v] for k, v in spec.items()}}


def wrap_update_states(original):
    def _update_states(self, scheduler_output, *args, **kwargs):
        _state['step'] += 1
        _state['sched'] = summarize_scheduler_output(scheduler_output) if active() else None
        return original(self, scheduler_output, *args, **kwargs)
    setattr(_update_states, _GUARD, True)
    return _update_states


def wrap_preprocess(original):
    def preprocess_mamba(scheduler_output, kv_cache_config, cache_config, mamba_state_idx, input_batch, requests,
                         forward_context, mamba_state_copy_funcs, copy_bufs, align_ctx=None):
        if not active():
            return original(scheduler_output, kv_cache_config, cache_config, mamba_state_idx, input_batch, requests,
                            forward_context, mamba_state_copy_funcs, copy_bufs, align_ctx=align_ctx)
        rows = []
        gids = list(getattr(copy_bufs, 'mamba_group_ids', ()) or ())
        for i, rid in enumerate(input_batch.req_ids):
            req = requests[rid]
            row = {'row': i, 'rid': rid, 'computed': int(req.num_computed_tokens),
                   'sched': int(scheduler_output.num_scheduled_tokens.get(rid, 0)),
                   'prev': mamba_state_idx.get(rid), 'count': int(input_batch.num_accepted_tokens_cpu[i])}
            rows.append(row)
        result = original(scheduler_output, kv_cache_config, cache_config, mamba_state_idx, input_batch, requests,
                          forward_context, mamba_state_copy_funcs, copy_bufs, align_ctx=align_ctx)
        src = getattr(getattr(align_ctx, 'precopy_src_col_buf', None), 'np', None)
        bias = getattr(getattr(align_ctx, 'precopy_token_bias_buf', None), 'np', None)
        for row in rows:
            i = row['row']
            row['curr'] = mamba_state_idx.get(row['rid'])
            if src is not None:
                row['src_col'] = int(src[i])
                row['bias'] = int(bias[i])
            tables = {}
            for gid in gids:
                bt = input_batch.block_table[gid]
                n = int(bt.num_blocks_per_row[i])
                tables[gid] = [int(x) for x in bt.block_table.np[i, :n]]
            row['mamba_blocks'] = tables
        _write({'step': _state['step'], 'so': _state['sched'], 'rows': rows})
        if DEEP:
            enqueue_deep(_state['step'], rows, input_batch, forward_context, kv_cache_config, gids)
        return result
    setattr(preprocess_mamba, _GUARD, True)
    return preprocess_mamba


def register():
    if os.environ.get('B70_ALIGN_TRACE', '').strip() != '1':
        return
    from vllm.logger import init_logger
    from vllm.v1.worker import gpu_model_runner as runner_module
    from vllm.v1.worker import mamba_utils

    logger = init_logger('b70_align_trace')
    if getattr(mamba_utils.preprocess_mamba, _GUARD, False):
        return
    mamba_utils.preprocess_mamba = wrap_preprocess(mamba_utils.preprocess_mamba)
    cls = runner_module.GPUModelRunner
    cls._update_states = wrap_update_states(cls._update_states)
    logger.warning('b70_align_trace 0.2.0: installed (logs while %s exists, to %s; state checksums %s)', FLAG, OUT_DIR,
                   'on' if DEEP else 'off')

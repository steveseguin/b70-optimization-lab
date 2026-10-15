"""Allocation admission only; driver residency is a separate device receipt."""
ARENA_LIMIT_BYTES = 30 * 1024**3  # Must equal Engine::allocate; not a caller override.

def arena_bytes(row):
    keys=('target_modeled_allocations_bytes','allocation_reserve_bytes',
          'draft_total_bytes','draft_duplicate_head_bytes','target_total_bytes','total_with_mtp_bytes')
    if any(type(row.get(k)) is not int or row[k] < 0 for k in keys):
        raise ValueError('invalid arena allocation components')
    target=row['target_modeled_allocations_bytes']
    total=target+row['draft_total_bytes']+row['draft_duplicate_head_bytes']
    if row['target_total_bytes'] != target+row['allocation_reserve_bytes'] or row['total_with_mtp_bytes'] != total+row['allocation_reserve_bytes']:
        raise ValueError('inconsistent arena allocation components')
    # Derive this independently; never trust a stored "passed" boolean or the
    # ledger's arena summary to authorize device contact.
    return total

def configuration(ledger, context, draft_rank=0, target_split=0):
    if draft_rank not in (0,1) or target_split not in (0,23,24):
        raise ValueError('invalid draft placement/target split')
    key=f'{draft_rank}-split23' if target_split==23 else ('0-split24' if draft_rank==0 and target_split==24 else str(draft_rank))
    if target_split==23 and context not in (4096,32768):
        raise ValueError('23/25 split admitted only at context4096/32768, subject to reserve')
    if key=='0-split24' and context!=4096:
        raise ValueError('24/24 rank0 draft admitted at context4096 only; 32K reserve is insufficient')
    try: row=ledger['placements'][key]['capacities'][str(context)]
    except KeyError as exc: raise ValueError('context is not admitted by memory plan') from exc
    if ledger.get('arena_limit_bytes',ARENA_LIMIT_BYTES) != ARENA_LIMIT_BYTES:
        raise ValueError('30 GiB arena cap changed')
    for r in row['ranks']:
        owned=arena_bytes(r)
        if owned > ARENA_LIMIT_BYTES:
            raise ValueError(f"planned rank{r['rank']} 30 GiB arena margin below zero: {owned-ARENA_LIMIT_BYTES} bytes over")
        free=ledger['capacity_bytes']-r['total_with_mtp_bytes']
        if not r['allocation_margin_passed'] or free < ledger['minimum_free_bytes'] or free != r['free_with_mtp_bytes']:
            raise ValueError('planned device allocation margin below 1.5 GB or inconsistent free bytes')
    return row


def check(census, ledger, rank, mtp=False, context=256, draft_rank=0, target_split=0):
    if rank not in (0, 1) or draft_rank not in (0, 1):
        raise ValueError('invalid rank')
    total = census['totals']['device']
    live = sum(r['bytes'] for r in census['allocations'] if r['live'] and r['memory'] == 'device')
    if live != total:
        raise ValueError('device census live total differs')
    if total <= 0:
        raise ValueError('empty device allocation census')
    if total > ARENA_LIMIT_BYTES:
        raise ValueError('live rank exceeds 30 GiB per-card arena')
    try:
        planned = configuration(ledger,context,draft_rank,target_split)['ranks'][rank]
    except KeyError as exc:
        raise ValueError('context is not admitted by memory plan') from exc
    limit = planned['total_with_mtp_bytes'] if mtp else planned['target_total_bytes']
    if total > limit:
        raise ValueError('rank allocations exceed context-specific plan')
    free = ledger['capacity_bytes'] - total
    if free < ledger['minimum_free_bytes']:
        raise ValueError('device allocation margin below 1.5 GB')
    result=dict(rank=rank, draft_rank=draft_rank, context_capacity=context, device_allocation_bytes=total,
                capacity_bytes=ledger['capacity_bytes'], planned_maximum_bytes=limit,
                planned_free_bytes=free, minimum_free_bytes=ledger['minimum_free_bytes'],
                passed=True, scope='allocation admission; driver overhead/residency unmeasured')
    if target_split:result.update(target_split=target_split,arena_limit_bytes=ARENA_LIMIT_BYTES,arena_headroom_bytes=ARENA_LIMIT_BYTES-total)
    return result


def snapshot(pid, proc=None):
    from pathlib import Path
    root = (Path('/proc') if proc is None else Path(proc))/str(pid)
    keys = ('VmRSS:', 'VmHWM:', 'RssAnon:', 'RssFile:', 'RssShmem:', 'Cpus_allowed_list:')
    try:
        status = [line for line in (root/'status').read_text().splitlines() if line.startswith(keys)]
    except FileNotFoundError:
        return dict(pid=pid, status=[], drm_fdinfo={}, process_exited=True)
    drm = {}
    try:
        descriptors = list((root/'fdinfo').iterdir())
    except (FileNotFoundError, PermissionError):
        descriptors = []
    for f in descriptors:
        try:
            rows = [line for line in f.read_text().splitlines() if line.startswith('drm-')]
        except (FileNotFoundError, PermissionError):
            continue
        if rows:
            drm[f.name] = rows
    return dict(pid=pid, status=status, drm_fdinfo=drm,
                phase='both ranks READY, including draft load; before first HALF',
                interpretation='Raw per-fd counters; shared clients may repeat. No device open or discovery.')

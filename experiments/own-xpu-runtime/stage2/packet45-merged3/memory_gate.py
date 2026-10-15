"""Allocation admission only; driver residency is a separate device receipt."""
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
    if target_split and not all(r['allocation_margin_passed'] and r['free_with_mtp_bytes']>=ledger['minimum_free_bytes'] for r in row['ranks']):
        raise ValueError('planned device allocation margin below 1.5 GB')
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
    if target_split:result['target_split']=target_split
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

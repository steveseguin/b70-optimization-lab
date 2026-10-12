"""Allocation admission only; driver residency is a separate device receipt."""
def check(census, ledger, rank, mtp=False):
    total=census['totals']['device']
    live=sum(r['bytes'] for r in census['allocations'] if r['live'] and r['memory']=='device')
    if live!=total:raise ValueError('device census live total differs')
    free=ledger['capacity_bytes']-total
    if free<ledger['minimum_free_bytes']:raise ValueError('device allocation margin below1.5GB')
    if rank==1 and mtp and total>ledger['rank1_total_bytes']:raise ValueError('rank1 draft allocations exceed sealed plan')
    return dict(rank=rank,device_allocation_bytes=total,capacity_bytes=ledger['capacity_bytes'],
                planned_free_bytes=free,minimum_free_bytes=ledger['minimum_free_bytes'],
                passed=True,scope='allocation admission; driver overhead/residency unmeasured')

def snapshot(pid, proc=None):
    from pathlib import Path
    root=(Path('/proc') if proc is None else Path(proc))/str(pid)
    keys=('VmRSS:','VmHWM:','RssAnon:','RssFile:','RssShmem:','Cpus_allowed_list:')
    status=[line for line in (root/'status').read_text().splitlines() if line.startswith(keys)]
    drm={}
    for f in (root/'fdinfo').iterdir():
        try:rows=[line for line in f.read_text().splitlines() if line.startswith('drm-')]
        except (FileNotFoundError,PermissionError):continue
        if rows:drm[f.name]=rows
    return dict(pid=pid,status=status,drm_fdinfo=drm,phase='both ranks READY, including draft load; before first HALF',
                interpretation='Raw per-fd counters; shared clients may repeat. No device open or discovery.')

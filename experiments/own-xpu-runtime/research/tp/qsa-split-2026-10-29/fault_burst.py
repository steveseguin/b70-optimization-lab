#!/usr/bin/env python3
"""The 35.7 ms rank-1 half of rank0-trims-2026-10-29's tptsx-r1 server (CPU only, retained traces). Scans every retained
per-half row (req-*/rank*/timings.jsonl) of the four-card suites archived on 2026-10-29 for minor-fault bursts, and
puts the burst half next to its neighbours, rank 0's halves at the same positions, the capacity re-prepares and the
rank-1 process's memory after load. Writes results/fault-burst.json."""
import glob, json, os, statistics as st
from pathlib import Path
D = Path(__file__).resolve().parent
A = '/mnt/raid-models/ownrt-experiment-archives/2026-10-29'
SUITES = ['rank0-trims-suite-20261029', 'target-head-split-repeat-20261029', 'target-head-split-suite-20261029', 'svc-ready-suite-20261029']
out = dict(schema='ownrt.fault-burst.v1', source=A, suites={}, bursts=[])
rows_total = 0
for suite in SUITES:
    for arm in sorted(glob.glob(f'{A}/{suite}/arm-*')):
        n, mx = 0, {}
        for f in sorted(glob.glob(arm + '/evidence/run-*/req-*/rank*/timings.jsonl')):
            rank, req = f.split('/')[-2], f.split('/')[-3]
            for line in open(f):
                r = json.loads(line)
                if 'process_minor_faults' not in r: continue
                n += 1; mx[rank] = max(mx.get(rank, 0), r['process_minor_faults'])
                if r['process_minor_faults'] > 200:
                    out['bursts'].append(dict(suite=suite, server=os.path.basename(arm), request=req, rank=rank, position=r['position'],
                        fixture=r['fixture'], half_ms=r['half_completion_ms'], enqueue_loop_ms=r['enqueue_loop_ms'], wait_ms=r['wait_ms'],
                        minor_faults=r['process_minor_faults'], major_faults=r['process_major_faults'],
                        voluntary_cs=r['process_voluntary_context_switches'], involuntary_cs=r['process_involuntary_context_switches'],
                        capacity_reprepares=r['capacity_reprepares'], launch_extent=r['launch_extent']))
        rows_total += n
        out['suites'].setdefault(suite, {})[os.path.basename(arm)] = dict(rows=n, max_minor_faults_per_half=mx)
out['rows_scanned'] = rows_total
# The burst request in detail
req = glob.glob(f'{A}/rank0-trims-suite-20261029/arm-tptsx-r1/evidence/run-*/req-000040')[0]
r1 = [json.loads(l) for l in open(req + '/rank1/timings.jsonl')]
r0 = [json.loads(l) for l in open(req + '/rank0/timings.jsonl') if 'process_minor_faults' in l]
dec = [r for r in r1 if r['fixture'] > 0]
out['burst_request'] = dict(
    request=req, rank1_decode_halves=len(dec),
    rank1_median=dict(half_ms=st.median(r['half_completion_ms'] for r in dec), enqueue_loop_ms=st.median(r['enqueue_loop_ms'] for r in dec),
                      minor_faults=st.median(r['process_minor_faults'] for r in dec), voluntary_cs=st.median(r['process_voluntary_context_switches'] for r in dec)),
    rank1_reprepares=[dict(position=r['position'], minor_faults=r['process_minor_faults'], half_ms=r['half_completion_ms'])
                      for a, r in zip(r1, r1[1:]) if r['capacity_reprepares'] != a['capacity_reprepares']],
    rank0_same_positions=[dict(position=r['position'], speculative=r['speculative'], minor_faults=r['process_minor_faults'], half_ms=r['half_completion_ms'])
                          for r in r0 if 3549 <= r['position'] <= 3552])
status = Path(glob.glob(f'{A}/rank0-trims-suite-20261029/arm-tptsx-r1/evidence/run-*/rank1/host-status-after_load.txt')[0]).read_text()
out['rank1_after_load'] = {l.split(':')[0]: l.split(':')[1].strip() for l in status.splitlines() if l.split(':')[0] in ('VmRSS', 'RssAnon', 'RssFile', 'RssShmem', 'VmHWM')}
out['host_now'] = dict(numa_nodes=len(glob.glob('/sys/devices/system/node/node[0-9]*')), numa_balancing=Path('/proc/sys/kernel/numa_balancing').read_text().strip(),
    thp=Path('/sys/kernel/mm/transparent_hugepage/enabled').read_text().strip(), mglru=Path('/sys/kernel/mm/lru_gen/enabled').read_text().strip(),
    swap_devices=len(Path('/proc/swaps').read_text().splitlines()) - 1,
    vmstat_since_boot={k: v for k, v in (l.split() for l in open('/proc/vmstat')) if k in ('pgsteal_kswapd', 'workingset_refault_file', 'pgmigrate_success', 'compact_daemon_wake', 'compact_stall', 'allocstall_normal')})
(D / 'results').mkdir(exist_ok=True)
(D / 'results/fault-burst.json').write_text(json.dumps(out, indent=1) + '\n')
print(json.dumps({k: v for k, v in out.items() if k != 'suites'}, indent=1))

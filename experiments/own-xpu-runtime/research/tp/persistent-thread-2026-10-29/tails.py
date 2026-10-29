#!/usr/bin/env python3
"""Tail halves and per-thread page faults of the suite servers (research/tp/persistent-thread-2026-10-29), CPU only.
Each server's work directory (/dev/shm/tp-svc-pt-20261029/arm-<name>, or its RAID archive) keeps every request's per-half
rows: the lab service copies req-*/rank*/timings.jsonl into control/run-*/tp-evidence/ before it releases a request
directory, and the last request's rows stay in evidence/run-*/req-*/. Only the suite's own requests (label 'client' in
requests.jsonl: the 12 prompts and the 3,490-token prompt) are used; startup-gate requests are not.
Per server and rank (decode halves, fixture > 0): half_completion_ms median/p99/max, the number of halves above 2x the
median, and the faults per thread (faults.py classes). Usage: tails.py OUT.json NAME=WORKDIR ..."""
import glob, importlib.util, json, statistics as st, sys
from pathlib import Path
D = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('faults', D / 'faults.py'); F = importlib.util.module_from_spec(spec); spec.loader.exec_module(F)
out = {}
for arg in sys.argv[2:]:
    name, w = arg.split('=', 1)
    control = Path(glob.glob(f'{w}/control/run-*')[0]); evidence = Path(glob.glob(f'{w}/evidence/run-*')[0])
    reqs = [json.loads(l) for l in open(control / 'requests.jsonl')]
    client = [r['request'] for r in reqs if r['label'] == 'client']
    server = dict(client_requests=client, ranks={})
    for rank in (0, 1):
        rows, missing = [], []
        for n in client:
            f = control / 'tp-evidence' / f'req-{n:06d}-rank{rank}-timings.jsonl'
            if not f.exists():
                f = evidence / f'req-{n:06d}' / f'rank{rank}' / 'timings.jsonl'
            if not f.exists():
                missing.append(n); continue
            for r in F.half_rows(f, lambda r: r['fixture'] > 0):
                r['request'] = n; rows.append(r)
        s = F.summarize(rows)
        if rows:
            h = sorted(r['half_completion_ms'] for r in rows); med = st.median(h)
            worst = max(rows, key=lambda r: r['half_completion_ms'])
            s['half_ms'].update(p99=round(h[min(len(h) - 1, len(h) * 99 // 100)], 4), above_2x_median=sum(1 for x in h if x > 2 * med),
                                worst=dict(request=worst['request'], position=worst['position'], speculative=worst['speculative'],
                                           half_ms=worst['half_completion_ms'], enqueue_loop_ms=worst['enqueue_loop_ms'], wait_ms=worst['wait_ms'],
                                           process_minor_faults=worst['process_minor_faults'], thread_minor_faults=worst.get('thread_minor_faults'),
                                           card1_thread_minor_faults=worst.get('card1_thread_minor_faults')))
            s['halves_over_200_process_faults'] = sum(1 for r in rows if r['process_minor_faults'] > 200)
        s['missing_requests'] = missing
        server['ranks'][f'rank{rank}'] = s
    out[name] = server
    print(name, json.dumps({k: dict(halves=v['halves'], half_ms=v.get('half_ms'), process=v.get('process'), main=v.get('main'), card1=v.get('card1'),
                                    other=v.get('other'), missing=v['missing_requests']) for k, v in server['ranks'].items()}))
Path(sys.argv[1]).write_text(json.dumps(out, indent=1) + '\n')

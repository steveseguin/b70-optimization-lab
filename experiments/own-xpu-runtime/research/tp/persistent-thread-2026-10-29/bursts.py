#!/usr/bin/env python3
"""Every per-half fault burst (> 150 process minor faults) of the suite servers and the token-by-token rank-1 gate run
(research/tp/persistent-thread-2026-10-29), CPU only, with the split by thread. The burst sizes per thread follow a
doubling ladder (about 100, 196, 387, 772, 1539, 3075, 6147 pages); this lists them so the next run can be compared.
Usage: bursts.py OUT.json ARCHIVE_DIR (the suite archive, arm-<name>/ work directories)"""
import glob, json, os, sys
from pathlib import Path
D = Path(__file__).resolve().parent
out = dict(schema='ownrt.tp-fault-bursts.v1', threshold=150, servers={}, ladder_pages={})


def rows(f):
    for line in open(f):
        if '"half_completion_ms"' in line:
            yield json.loads(line)


def burst(r, **k):
    return dict(k, position=r['position'], fixture=r['fixture'], half_ms=round(r['half_completion_ms'], 3), process=r['process_minor_faults'],
                main=r.get('thread_minor_faults'), card1=r.get('card1_thread_minor_faults'), capacity_reprepares=r['capacity_reprepares'])


for w in sorted(glob.glob(sys.argv[2] + '/arm-*')):
    name = os.path.basename(w)[4:]
    control = glob.glob(w + '/control/run-*')[0]; evidence = glob.glob(w + '/evidence/run-*')[0]
    label = {r['request']: r['label'] for r in map(json.loads, open(control + '/requests.jsonl'))}
    found = []
    for rank in (0, 1):
        files = [(int(os.path.basename(f)[4:10]), f) for f in glob.glob(f'{control}/tp-evidence/req-*-rank{rank}-timings.jsonl')]
        files += [(int(f.split('/')[-3][4:10]), f) for f in glob.glob(f'{evidence}/req-*/rank{rank}/timings.jsonl')]
        for req, f in sorted(files):
            for r in rows(f):
                if r['process_minor_faults'] > 150 and r['fixture'] > 0:
                    found.append(burst(r, rank=rank, request=req, label=label.get(req)))
    out['servers'][name] = found
tbt = D / 'evidence/g-r1-tptqp-tbt/rank1/timings.jsonl'
out['gate_g-r1-tptqp-tbt'] = [burst(r, rank=1) for r in rows(tbt) if r['process_minor_faults'] > 150 and r['position'] > 0]
for v in list(out['servers'].values()) + [out['gate_g-r1-tptqp-tbt']]:
    for b in v:
        for t in ('main', 'card1'):
            if b[t] and b[t] > 50:
                k = min((100, 196, 387, 772, 1539, 3075, 6147, 12294), key=lambda x: abs(x - b[t]))
                out['ladder_pages'][str(k)] = out['ladder_pages'].get(str(k), 0) + 1
Path(sys.argv[1]).write_text(json.dumps(out, indent=1) + '\n')
print(json.dumps(dict(ladder_pages=out['ladder_pages'], bursts={k: len(v) for k, v in out['servers'].items()}, gate=len(out['gate_g-r1-tptqp-tbt']))))

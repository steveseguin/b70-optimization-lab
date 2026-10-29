#!/usr/bin/env python3
"""CPU-only plan-cap probe: run one rank of the lab adapter's command with OWNRT_PLAN_ONLY=1, which exits after
write_plan (owned_bytes per card, 30 GiB cap) and before any device contact (rank.hpp). Usage: plan_probe.py ARM RANK OUT"""
import importlib.util, json, os, socket, subprocess, sys, time
from pathlib import Path
arm, rank, out = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3])
spec = importlib.util.spec_from_file_location('lab_adapter', Path(__file__).parent / 'lab/adapter6_tp.py')
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)
plan = A.build_plan(out / 'control', mini=False, max_new=128, seconds=172800, evidence_output=out / 'evidence')
A.validate_plan(plan)
(out / 'control').mkdir(mode=0o700); (out / 'evidence').mkdir(mode=0o700)
shared = out / 'control/shared.bin'
with open(shared, 'wb') as f: f.truncate(A.BASE.SHARED)
parent, child = socket.socketpair(); r, w = os.pipe()
cmd = A.command(plan, rank, child.fileno(), r)
env = dict(plan['environment'][rank], OWNRT_PLAN_ONLY='1')
for k in ('SYCL_CACHE_DIR', 'NEO_CACHE_DIR', 'XDG_CACHE_HOME'): Path(env[k]).mkdir(parents=True, exist_ok=True)
log = open(out / f'rank{rank}.log', 'w')
t = time.monotonic()
p = subprocess.Popen(cmd, pass_fds=(child.fileno(), r), stdout=log, stderr=subprocess.STDOUT, env=env)
child.close()
rc = p.wait(timeout=600)
text = (out / f'rank{rank}.log').read_text()
print(json.dumps(dict(arm=arm, rank=rank, rc=rc, seconds=round(time.monotonic() - t, 1), log=text.strip()[-600:],
                      plan_only=(out / f'evidence/rank{rank}/plan-only.json').read_text() if (out / f'evidence/rank{rank}/plan-only.json').exists() else None)))

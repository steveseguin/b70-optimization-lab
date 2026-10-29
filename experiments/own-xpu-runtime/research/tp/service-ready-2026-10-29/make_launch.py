#!/usr/bin/env python3
"""Rank launch JSON (argv + environment) for the rank drivers, from the lab adapter's command for an arm of arm_env.py.
The drivers replace channel, stop fd, shared file and output; --tp in a driver switches to two cards.
Usage: make_launch.py ARM RANK OUT.json [--bdf 0000:23:00.0]   (env: SC117_ENGINE_RECEIPT)"""
import argparse, importlib.util, json, os, sys, tempfile
from pathlib import Path
D = Path(__file__).resolve().parent
ap = argparse.ArgumentParser(); ap.add_argument('arm'); ap.add_argument('rank', type=int); ap.add_argument('out')
ap.add_argument('--bdf', default='0000:23:00.0', help='one-card device for the one-card arms (FilterBdfPath)')
a = ap.parse_args()
spec = importlib.util.spec_from_file_location('arm_env', D / 'arm_env.py'); E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)
os.environ.update(E.env(a.arm))
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('lab_adapter', D / 'lab/adapter6_tp.py'); A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)
with tempfile.TemporaryDirectory(dir='/dev/shm') as tmp:
    os.chmod(tmp, 0o700)
    plan = A.build_plan(Path(tmp) / 'control', mini=False, max_new=128, seconds=172800, evidence_output=Path(tmp) / 'evidence')
    A.validate_plan(plan)
    argv = A.command(plan, a.rank, 0, 0)
env = dict(plan['environment'][a.rank])
for k in ('SYCL_CACHE_DIR', 'NEO_CACHE_DIR', 'XDG_CACHE_HOME'): env.pop(k)
changes = [f'arm {a.arm} of arm_env.py, rank {a.rank}', 'binary ' + plan['binary_sha256'][:12]]
if not A.tp_rank(a.rank):
    env['FilterBdfPath'] = a.bdf; changes.append('FilterBdfPath=' + a.bdf + ' (one-card arm; --tp pops it)')
Path(a.out).write_text(json.dumps(dict(argv=argv, environment=env, changes=changes), indent=1) + '\n')
print(a.out, ' '.join(argv[3:6]), plan['binary_sha256'][:12])

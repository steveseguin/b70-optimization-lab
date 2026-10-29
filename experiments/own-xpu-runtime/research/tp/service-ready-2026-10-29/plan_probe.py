#!/usr/bin/env python3
"""CPU-only plan probe: run one rank of the lab adapter's command (lab/adapter6_tp.py, arm environment from arm_env.py)
with OWNRT_PLAN_ONLY=1, which exits after the plan (owned bytes per card, 30 GiB cap) and before any device contact
(rank.hpp). Usage: plan_probe.py ARM RANK OUT   (env: SC117_ENGINE_RECEIPT, ARM_CONTEXT, ARM_PREFILL_ROWS)"""
import importlib.util, json, os, re, socket, subprocess, sys, time
from pathlib import Path
D = Path(__file__).resolve().parent
arm, rank, out = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3]).absolute()
spec = importlib.util.spec_from_file_location('arm_env', D / 'arm_env.py'); E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)
os.environ.update(E.env(arm))
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('lab_adapter', D / 'lab/adapter6_tp.py')
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)
out.mkdir(mode=0o700)
plan = A.build_plan(out / 'control', mini=False, max_new=128, seconds=172800, evidence_output=out / 'evidence')
if os.environ.get('PROBE_NO_VALIDATE')!='1':A.validate_plan(plan)  # =1: an older binary whose sources differ from engine/src (plan-only diagnostic)
(out / 'control').mkdir(mode=0o700); (out / 'evidence').mkdir(mode=0o700)
with open(out / 'control/shared.bin', 'wb') as f: f.truncate(A.BASE.SHARED)
if A.PREFILL_ROWS:
    with open(out / 'control/prefill.bin', 'wb') as f:
        f.truncate(A.prefill_bytes(A.PREFILL_ROWS)); f.seek(0); f.write(__import__('struct').pack('<4I', 0x31465050, 1, A.PREFILL_ROWS, A.PREFILL_STREAM))
parent, child = socket.socketpair(); r, w = os.pipe()
cmd = A.command(plan, rank, child.fileno(), r)
env = dict(plan['environment'][rank], OWNRT_PLAN_ONLY='1')
for k in ('SYCL_CACHE_DIR', 'NEO_CACHE_DIR', 'XDG_CACHE_HOME'): Path(env[k]).mkdir(parents=True, exist_ok=True)
log = open(out / f'rank{rank}.log', 'w')
t = time.monotonic()
p = subprocess.Popen(cmd, pass_fds=(child.fileno(), r), stdout=log, stderr=subprocess.STDOUT, env=env)
child.close()
rc = p.wait(timeout=900)
text = (out / f'rank{rank}.log').read_text()
cards = [dict(card=int(m[0]), owned_bytes=int(m[1]), weights=int(m[2])) for m in re.findall(r'card (\d+) owned_bytes (\d+) weights (\d+)', text)]
tp = [dict(card=int(m[0]), owned_bytes=int(m[1]), weights=int(m[2]), buffers=int(m[3])) for m in re.findall(r'tp card (\d+) planned_bytes (\d+) weights (\d+) buffers (\d+)', text)]
row = dict(arm=arm, rank=rank, context=int(os.environ['SC117_CONTEXT']), prefill_rows=A.PREFILL_ROWS, ring=os.environ.get('OWNRT_QSA_RAW_RING'),
           binary=plan['binary_sha256'][:12], rc=rc, seconds=round(time.monotonic() - t, 1), one_card_plan=cards, tp_plan=tp,
           cap_bytes=30 * 1024**3, log_tail=text.strip()[-500:])
(out / 'probe.json').write_text(json.dumps(row, indent=1) + '\n')
print(json.dumps({k: v for k, v in row.items() if k != 'log_tail'}), '|', text.strip()[-200:].replace('\n', ' / '))

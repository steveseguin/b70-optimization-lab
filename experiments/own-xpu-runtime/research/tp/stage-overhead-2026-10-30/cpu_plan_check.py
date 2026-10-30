#!/usr/bin/env python3
"""CPU-only plan check of the two diagnostics (no device contact): runs the engine with OWNRT_PLAN_ONLY=1, which stops
after the (TP) plan transform and before the Engine opens any device. Checks
  * OWNRT_TP_SHAPE_PROBE=0/1 on one card: tp-shape-probe.json (launch counts) and no exchange op left in the plan;
  * the four-card plan with OWNRT_TP_EXCHANGE_STATS: tp-exchange-slots.json (one label per exchange slot).
Usage: cpu_plan_check.py BINARY OUTDIR"""
import json, os, socket, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
PS = HERE.parent / 'prefill-speed-2026-10-29'
sys.path.insert(0, str(PS))
import tp_rank0_driver as R0  # noqa: E402
binary, outdir = sys.argv[1], Path(sys.argv[2])
full = dict(OWNRT_TP_EXPERTS='compact', OWNRT_TP_EXCHANGE='direct', OWNRT_TP_GDN='heads', OWNRT_TP_QSA_SPLIT='1',
            OWNRT_TP_SPLIT='.attention,.gdn.qkv')
cases = []
for rank in (1, 0):
    extra = dict(OWNRT_TARGET_HEAD_SPLIT='1') if rank == 1 else {}
    for c in (0, 1):
        cases.append((f'r{rank}-probe{c}', rank, False, {**full, **extra, 'OWNRT_TP_SHAPE_PROBE': str(c)}))
    cases.append((f'r{rank}-full-xs', rank, True, {**full, **extra, 'OWNRT_TP_EXCHANGE_STATS': '1', 'OWNRT_TP_THREADS': '1',
                                                    'OWNRT_TP_CARD_CONTEXT': '1'}))
report = {}
for name, rank, tp, envs in cases:
    launch = json.loads((PS / f'rank{rank}-launch-c65536-b51c9e8d803e.json').read_text())
    argv, env = list(launch['argv']), dict(launch['environment'])
    out = outdir / name; out.mkdir(parents=True, exist_ok=False)
    shared = out / 'shared.bin'; shared.write_bytes(bytes(R0.SHARED))
    parent, child = socket.socketpair(); stop_r, stop_w = os.pipe()
    def rep(flag, value):
        argv[argv.index(flag) + 1] = value
    rep('--channel', str(child.fileno())); rep('--stop-fd', str(stop_r)); rep('--shared', str(shared)); rep('--output', str(out / f'rank{rank}'))
    for flag in ('--prefill-rows', '--prefill-shared'):
        if flag in argv:
            i = argv.index(flag); del argv[i:i + 2]
    argv[next(k for k, x in enumerate(argv) if x.endswith('sc117-engine'))] = binary
    if tp:
        rep('--cards', '2'); argv.append('--tp-replicate'); env['ZE_AFFINITY_MASK'] = '0,3'; env.pop('FilterBdfPath', None)
        env['ONEAPI_DEVICE_SELECTOR'] = 'level_zero:*'
    full_env = dict(os.environ); full_env.update(env); full_env.update(envs); full_env['OWNRT_PLAN_ONLY'] = '1'; full_env['ONEAPI_DEVICE_SELECTOR'] = 'opencl:cpu'  # plan only: no GPU runtime
    log = open(out / 'engine.log', 'w')
    rc = subprocess.run(argv, env=full_env, pass_fds=(child.fileno(), stop_r), stdout=log, stderr=subprocess.STDOUT, timeout=600).returncode
    child.close(); os.close(stop_r); os.close(stop_w); parent.close()
    r = out / f'rank{rank}'
    po = json.loads((r / 'plan-only.json').read_text()) if (r / 'plan-only.json').exists() else None
    item = dict(rc=rc, plan_only=po)
    if (r / 'tp-shape-probe.json').exists():
        item['probe'] = json.loads((r / 'tp-shape-probe.json').read_text())
    if (r / 'tp-exchange-slots.json').exists():
        s = json.loads((r / 'tp-exchange-slots.json').read_text())['slots']
        kinds = {}
        for x in s:
            k = x['label'].split('.', 2)[-1] if x['label'].startswith('blk.') else x['label']
            kinds[k] = kinds.get(k, 0) + 1
        item['exchange_slots'] = dict(count=len(s), slots_contiguous=sorted(x['slot'] for x in s) == list(range(len(s))), kinds=kinds)
    item['ok'] = rc == 0 and po is not None and (('probe' in item) if 'probe' in name else ('exchange_slots' in item))
    report[name] = item
    print(name, json.dumps(item), flush=True)
(outdir / 'cpu-plan-check.json').write_text(json.dumps(report, indent=1) + '\n')
sys.exit(0 if all(v['ok'] for v in report.values()) else 1)

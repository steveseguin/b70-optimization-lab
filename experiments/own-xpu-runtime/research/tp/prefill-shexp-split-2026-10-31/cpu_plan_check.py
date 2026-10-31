#!/usr/bin/env python3
"""Gate 1a (CPU only, no device contact) for OWNRT_PREFILL_SHEXP_SPLIT (research/tp/prefill-shexp-split-2026-10-31): runs
the engine with OWNRT_PLAN_ONLY=1, which stops after the TP plan transform and its per-card admission (tp-plan.json),
before any device is opened. Per rank (both TP ranks, context 131072) and mode (off, full, gateup, down):
  * the decode plan is unchanged: the decode exchange sites and their flag slots (tp-exchange-slots.json) equal flag off,
    and the stored weights per card equal flag off (whole replicated weights, no slice, no copy);
  * the only planned addition is the per-card half buffers ('#tp') of the split prefill sites: per layer
    gate#tp, up#tp, act#tp (I/2 floats each) for full/gateup and down#tp (H/2 floats) for full/down, so the planned
    buffer bytes per card grow by exactly that;
  * the prefill flag slots of the new exchanges (128 + decode slots .. + 2 per layer for full, 1 for gateup/down) stay
    below the 256-slot control block.
The engine-side replacement of the prefill sites (prefill_allocate) runs at device time; its record
prefill-shexp-split.json is checked by run_phase.sh on the first device smoke.
Usage: cpu_plan_check.py BINARY_TAG OUTDIR   (launch JSONs rank<r>-launch-c131072-<TAG>.json of this folder)"""
import json, os, socket, subprocess, sys
from pathlib import Path
D = Path(__file__).resolve().parent
sys.path.insert(0, str(D))
import tp_rank0_driver as R0  # noqa: E402
tag, outdir = sys.argv[1], Path(sys.argv[2])
full = dict(OWNRT_TP_EXPERTS='compact', OWNRT_TP_EXCHANGE='direct', OWNRT_TP_GDN='heads', OWNRT_TP_QSA_SPLIT='1',
            OWNRT_TP_SPLIT='.attention,.gdn.qkv', OWNRT_TP_THREADS='1', OWNRT_TP_CARD_CONTEXT='1', OWNRT_TP_EXCHANGE_STATS='1')
SLOTS, BASE = 256, 128
I, H = 640, 2560  # SC117 shared expert: intermediate rows, hidden rows
MODES = ('off', 'full', 'gateup', 'down')


def run(name, rank, envs):
    launch = json.loads((D / f'rank{rank}-launch-c131072-{tag}.json').read_text())
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
    rep('--cards', '2'); argv.append('--tp-replicate'); env['ZE_AFFINITY_MASK'] = '0,3'; env.pop('FilterBdfPath', None)
    full_env = dict(os.environ); full_env.update(env); full_env.update(envs); full_env['OWNRT_PLAN_ONLY'] = '1'
    full_env['ONEAPI_DEVICE_SELECTOR'] = 'opencl:cpu'  # plan only: no GPU runtime
    with open(out / 'engine.log', 'w') as log:
        rc = subprocess.run(argv, env=full_env, pass_fds=(child.fileno(), stop_r), stdout=log, stderr=subprocess.STDOUT, timeout=900,
                            preexec_fn=lambda: os.nice(19 - os.nice(0))).returncode
    child.close(); os.close(stop_r); os.close(stop_w); parent.close()
    return rc, out / f'rank{rank}'


def load(r, f):
    p = r / f
    return json.loads(p.read_text()) if p.exists() else None


report, ok = {}, True
for rank in (1, 0):
    extra = dict(OWNRT_TARGET_HEAD_SPLIT='1') if rank == 1 else {}
    res = {}
    for mode in MODES:
        envs = {**full, **extra}
        if mode != 'off':
            envs['OWNRT_PREFILL_SHEXP_SPLIT'] = '1' if mode == 'full' else mode
        rc, r = run(f'r{rank}-{mode}', rank, envs)
        res[mode] = dict(rc=rc, plan_only=load(r, 'plan-only.json'), tp_plan=load(r, 'tp-plan.json'), slots=load(r, 'tp-exchange-slots.json'))
        lp = load(r, 'launch-plan.json')
        res[mode]['layers'] = sorted({int(l['label'].split('.')[1]) for l in (lp or {}).get('launches', []) if l['label'].endswith('.shexpgate')})
    off = res['off']; rr = dict(cases={})
    for mode in MODES:
        x = res[mode]; c = dict(rc=x['rc'], plan_only=bool(x['plan_only'] and x['plan_only'].get('tp_plan')))
        if x['tp_plan'] and off['tp_plan']:
            c['weights_equal_off'] = all(a['weights'] == b['weights'] and a['weight_tensors'] == b['weight_tensors'] and a['sliced_tensors'] == b['sliced_tensors']
                                         for a, b in zip(x['tp_plan']['cards'], off['tp_plan']['cards']))
            c['buffer_bytes_delta'] = [a['buffers'] - b['buffers'] for a, b in zip(x['tp_plan']['cards'], off['tp_plan']['cards'])]
        n = len(x['layers'])
        per_layer = {'off': 0, 'full': (3 * I // 2 + H // 2) * 4, 'gateup': 3 * I // 2 * 4, 'down': H // 2 * 4}[mode]
        c['layers'] = n; c['expected_delta'] = n * per_layer
        c['delta_ok'] = c.get('buffer_bytes_delta') == [n * per_layer] * 2
        c['decode_slots_equal_off'] = x['slots'] == off['slots'] and x['slots'] is not None
        decode_slots = 1 + max(s['slot'] for s in x['slots']['slots']) if x['slots'] else None
        new = {'off': 0, 'full': 2, 'gateup': 1, 'down': 1}[mode] * n
        c['decode_slots'] = decode_slots; c['prefill_slot_end'] = BASE + decode_slots + new if decode_slots else None
        c['slots_ok'] = c['prefill_slot_end'] is not None and c['prefill_slot_end'] <= SLOTS
        c['passed'] = c['rc'] == 0 and c['plan_only'] and c.get('weights_equal_off') and c['delta_ok'] and c['decode_slots_equal_off'] and c['slots_ok'] and n > 0
        ok = ok and bool(c['passed']); rr['cases'][mode] = c
    report[f'rank{rank}'] = rr
report['passed'] = ok
(outdir / 'cpu-plan-check.json').write_text(json.dumps(report, indent=1) + '\n')
print(json.dumps(report, indent=1))
sys.exit(0 if ok else 1)

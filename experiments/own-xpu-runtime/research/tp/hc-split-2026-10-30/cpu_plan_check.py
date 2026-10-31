#!/usr/bin/env python3
"""Gate 1a (CPU only, no device contact) for OWNRT_TP_HC_SPLIT: runs the engine with OWNRT_PLAN_ONLY=1, which stops after
the TP plan transform and its per-card admission (tp-plan.json), before any device is opened. Checks per rank:
  * the split sites (tp-hc-split.json): every hc.a/f low and gate of the rank's layers (+ final.low / final.gate on
    rank 1), card c computing the contiguous rows [c*R/2, (c+1)*R/2) into y#tp, the whole-weight row offset unless the
    prefill token is set;
  * one tp_xgather pair per site: y#tp -> y, R/2 values per card at c*R/2, one flag slot per site after every other
    exchange site (the other sites keep the flag-off slots), slots contiguous and unique (tp-exchange-slots.json);
  * the dump layout: the two cards' exchanged halves tile [0, R) of y exactly once (y is the one-card buffer; y#tp is
    skipped by the dump), so the bitwise gate against one card reads the one-card layout;
  * per-card admission (tp-plan.json): whole-weight mode stores exactly the flag-off weights; prefill mode stores half of
    each split weight (rows x K x 2 bytes less per site); the prefill flag slots (decode slot + max(128, decode slots))
    stay below the 512-slot control block.
Usage: cpu_plan_check.py BINARY OUTDIR"""
import json, os, socket, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
PS = HERE.parent / 'prefill-speed-2026-10-29'
sys.path.insert(0, str(PS))
import tp_rank0_driver as R0  # noqa: E402
binary, outdir = sys.argv[1], Path(sys.argv[2])
full = dict(OWNRT_TP_EXPERTS='compact', OWNRT_TP_EXCHANGE='direct', OWNRT_TP_GDN='heads', OWNRT_TP_QSA_SPLIT='1',
            OWNRT_TP_SPLIT='.attention,.gdn.qkv', OWNRT_TP_THREADS='1', OWNRT_TP_CARD_CONTEXT='1', OWNRT_TP_EXCHANGE_STATS='1')
SLOTS = 512
cases = []
for rank in (1, 0):
    extra = dict(OWNRT_TARGET_HEAD_SPLIT='1') if rank == 1 else {}
    cases.append((f'r{rank}-off', rank, {**full, **extra}))
    cases.append((f'r{rank}-hs', rank, {**full, **extra, 'OWNRT_TP_HC_SPLIT': '1'}))
    cases.append((f'r{rank}-hsp', rank, {**full, **extra, 'OWNRT_TP_HC_SPLIT': 'low,gate,final,prefill'}))
    cases.append((f'r{rank}-low', rank, {**full, **extra, 'OWNRT_TP_HC_SPLIT': 'low'}))


def run(name, rank, envs):
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
    rep('--cards', '2'); argv.append('--tp-replicate'); env['ZE_AFFINITY_MASK'] = '0,3'; env.pop('FilterBdfPath', None)
    full_env = dict(os.environ); full_env.update(env); full_env.update(envs); full_env['OWNRT_PLAN_ONLY'] = '1'
    full_env['ONEAPI_DEVICE_SELECTOR'] = 'opencl:cpu'  # plan only: no GPU runtime
    with open(out / 'engine.log', 'w') as log:
        rc = subprocess.run(argv, env=full_env, pass_fds=(child.fileno(), stop_r), stdout=log, stderr=subprocess.STDOUT, timeout=900).returncode
    child.close(); os.close(stop_r); os.close(stop_w); parent.close()
    return rc, out / f'rank{rank}'


def load(r, f):
    p = r / f
    return json.loads(p.read_text()) if p.exists() else None


report, plans, slots_off = {}, {}, {}
for name, rank, envs in cases:
    rc, r = run(name, rank, envs)
    item = dict(rc=rc, plan_only=load(r, 'plan-only.json'))
    errors = []
    tp = load(r, 'tp-plan.json'); xs = load(r, 'tp-exchange-slots.json'); hs = load(r, 'tp-hc-split.json')
    if rc or not item['plan_only'] or not tp or not xs:
        errors.append(f'rc {rc} or missing plan-only / tp-plan / exchange slots')
    else:
        plans[name] = tp
        slots = xs['slots']; nums = sorted(x['slot'] for x in slots)
        item['exchange_slots'] = len(slots)
        if nums != list(range(len(slots))): errors.append('exchange slots not contiguous/unique')
        if 'HC_SPLIT' not in json.dumps(envs):
            slots_off[rank] = {x['label']: x['slot'] for x in slots}
            if hs: errors.append('tp-hc-split.json without the flag')
        else:
            tokens = envs['OWNRT_TP_HC_SPLIT']; tokens = 'low,gate,final' if tokens == '1' else tokens
            want = set(tokens.split(',')); prefill = 'prefill' in want
            layers = range(23, 48) if rank == 1 else range(0, 23)
            expect = {}
            for L in layers:
                for b in 'af':
                    if 'low' in want: expect[f'blk.{L}.hc.{b}.low'] = 320
                    if 'gate' in want: expect[f'blk.{L}.hc.{b}.gate'] = 10240
            if rank == 1 and 'final' in want:
                expect['final.low'] = 320; expect['final.gate'] = 10240
            launches = hs['launches'] if hs else []
            gem = {(l['label'], l['card']): l for l in launches if l['op'] == 'gemv'}
            xg = {(l['label'][:-len('.tp_xgather')], l['card']): l for l in launches if l['op'] == 'tp_xgather'}
            if set(k[0] for k in gem) != set(expect) or set(k[0] for k in xg) != set(expect):
                errors.append(f'split sites {len(set(k[0] for k in gem))} / exchanges {len(set(k[0] for k in xg))}, expected {len(expect)}')
            weight_delta = 0
            off_slots = slots_off.get(rank, {})
            for lab, R in expect.items():
                site_slots = set()
                for c in (0, 1):
                    g = gem.get((lab, c)); x = xg.get((lab, c))
                    if not g or not x: errors.append(f'{lab} card {c} missing'); continue
                    ok = (g['row_begin'] == c * R // 2 and g['row_count'] == R // 2 and g['row_offset'] == (not prefill)
                          and g['output'] == lab + '#tp' and g['shape'][1] == R)
                    if lab.startswith('blk.'):
                        ok = ok and g['output'] == lab + '#tp'
                    if not ok: errors.append(f'{lab} card {c} split launch {g}')
                    if not (x['inputs'] == lab + '#tp' and x['output'] == lab and x['parameter'] == R // 2 and x['shape'][0] == R
                            and x['row_offset'] == (not prefill)):
                        errors.append(f'{lab} card {c} exchange {x}')
                    site_slots.add(x['shape'][1])
                if len(site_slots) != 1: errors.append(f'{lab}: exchange halves on different slots {site_slots}')
                cover = sorted((c * R // 2, R // 2) for c in (0, 1))  # tp_xgather: card c's half at c*half on both cards
                at = 0
                for first, n in cover:
                    if first != at: errors.append(f'{lab}: dump layout gap/overlap at {at}')
                    at = first + n
                if at != R: errors.append(f'{lab}: dump layout covers {at} of {R}')
                weight_delta += (R // 2) * (10240 if R == 320 else 320) * 2
            first = hs['first_slot'] if hs else -1
            nonhc = {x['label']: x['slot'] for x in slots if not any(x['label'] == k + '.tp_xgather' for k in expect)}
            if off_slots and nonhc != off_slots: errors.append('the other exchange sites changed slots')
            if first != len(off_slots): errors.append(f'first HC slot {first}, flag-off sites {len(off_slots)}')
            base = max(128, len(slots))
            if base + len(slots) - 1 >= SLOTS: errors.append(f'prefill slots reach {base + len(slots) - 1}')
            item.update(sites=len(expect), first_slot=first, slots_total=len(slots), prefill_slot_base=base,
                        prefill_slot_max=base + len(slots) - 1, hc=dict((k, v) for k, v in (hs or {}).items() if k != 'launches'))
            off = plans.get(f'r{rank}-off')
            if off:
                for c in (0, 1):
                    w0 = off['cards'][c]['weights']; w1 = tp['cards'][c]['weights']
                    want_w = w0 - weight_delta if prefill else w0
                    if w1 != want_w: errors.append(f'card {c} weights {w1}, expected {want_w} (flag off {w0})')
                item['weights_per_card'] = [tp['cards'][c]['weights'] for c in (0, 1)]
                item['planned_bytes_per_card'] = [tp['cards'][c]['planned_bytes'] for c in (0, 1)]
                item['weights_saved_per_card'] = weight_delta if prefill else 0
    item['errors'] = errors; item['ok'] = not errors
    report[name] = item
    print(name, json.dumps({k: v for k, v in item.items() if k != 'hc'}), flush=True)
(outdir / 'cpu-plan-check.json').write_text(json.dumps(report, indent=1) + '\n')
sys.exit(0 if all(v['ok'] for v in report.values()) else 1)

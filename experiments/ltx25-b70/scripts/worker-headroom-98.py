#!/usr/bin/env python3
"""Packet 98 CPU-only headroom planner, derived from the untouched packet 97 helper.

Pass --size 256x256|512x320|640x384 with plan/live/calibrate. Default-size
arithmetic is unchanged. Larger pooled two-way plans use the SHA-bound packet 97
freeze/calibration snapshot, scaling measured per-worker memory by video tokens,
then adding 50% and 0.25 GiB. Decoder growth is charged separately. These are
estimates, not proven bounds. Other layouts use the scaled private-pool estimate.

Larger plans admit only if all workers leave the 2 GiB floor and enough replica
probe room. Live readings and the freeze remain mandatory. Missing/nonfinite
readings refuse. Same-packet calibrations require matching output size/layout;
before/after receipts must have the same identity, size and batch, in time order.
Exit 18 means insufficient room. No device API is imported or called.

See notes/2026-10-06-packet-98-build.md for equations and measured source files.
"""
import math, glob
import json
import os
import sys
import time
from pathlib import Path

import hashlib
from ltx_output_size_98 import dimensions
SIZE = '256x256'
SCALE = 1.0
BASIS_PATH = Path(__file__).resolve().parents[1] / 'data/size-98-memory-basis.json'
BASIS_SHA = 'a4a16ce02e0df02c46fbfb4676bdc8bc16062d08f2e235714c5d633c11b6c4d7'

def size_basis():
    raw = BASIS_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != BASIS_SHA:
        raise RuntimeError('packet 97 memory basis changed')
    return json.loads(raw)

def size_worker_cost(layout, batch, pool):
    if SCALE > 1 and pool and layout == 'two-way':
        row = size_basis()['batches'][str(batch)]['per_worker_gib']
        return {c: row[c] * SCALE * 1.5 + (0.25 if LAYOUTS[layout][c] else 0) for c in CARDS}
    return None

def decode_growth():
    # Conservative extrapolation: measured decoder peak grows 0.9 GiB at 3.75x.
    # Charge 0.5 GiB per extra baseline pixel area, plus 50% margin (2.063 at 3.75x).
    return 0.5 * (SCALE - 1) * 1.5

GIB = 2**30
FLOOR = 2.0
PER_BLOCK_GIB = {1: 0.12, 2: 0.24, 4: 0.48}
GLUE_GIB = {1: 0.1, 2: 0.2, 4: 0.4}
LAYOUTS = {'two-way': {'xpu:0': 23, 'xpu:1': 25, 'xpu:2': 0, 'xpu:3': 0},
           'shard3-c': {'xpu:0': 20, 'xpu:1': 20, 'xpu:2': 8, 'xpu:3': 0},
           'shard4-a': {'xpu:0': 18, 'xpu:1': 18, 'xpu:2': 8, 'xpu:3': 4}}
PRE_DECODE = {'xpu:1': 1.8, 'xpu:3': 1.9}
REPLICA_WEIGHTS_GIB = 1.8        # packet 96 PRE_DECODE figure for the replica's own card
VAE_LOAD_GIB = 1.9               # the native VAEs' load onto xpu:3
REPLICA_FREEZE_GIB = 2.2         # replica cost at the freeze on its card (96 receipts: 2.12-2.19)
REPLICA_PROBE_FREE_GIB = 5.0     # ltx_decode_replica.MIN_FREE_AFTER_BUILD (free right after the copy)
REPLICA_COPY_GIB = 1.71          # the copy's own bytes (96 probe receipts: video 1.371 + audio 0.340 GiB)
# Free at the freeze = free after the copy - (REPLICA_FREEZE_GIB - REPLICA_COPY_GIB) (the probe's
# decode scratch that stays reserved), so the probe's 5 GiB rule is 4.51 GiB at the freeze.
REPLICA_MIN_FREE_GIB = round(REPLICA_PROBE_FREE_GIB - (REPLICA_FREEZE_GIB - REPLICA_COPY_GIB), 2)
REPLICA_SPECS = {'xpu:1': ('xpu:1',), 'xpu:2': ('xpu:2',), 'xpu:1,xpu:2': ('xpu:1', 'xpu:2'),
                 'xpu:2,xpu:1': ('xpu:2', 'xpu:1')}


def replica_cards(spec):
    if spec not in REPLICA_SPECS:
        raise SystemExit('replica spec must be one of %s, not %r' % (sorted(REPLICA_SPECS), spec))
    return REPLICA_SPECS[spec]


def pre_decode(spec='xpu:1'):
    """Room the decode stage still takes after the capture pass, per card (GiB)."""
    room = {'xpu:3': VAE_LOAD_GIB + decode_growth()}
    for card in replica_cards(spec):
        room[card] = room.get(card, 0.0) + REPLICA_WEIGHTS_GIB + decode_growth()
    return room


def zero_worker_free(layout, spec='xpu:1', batch=1):
    """Free GiB per card at the freeze with no sampler worker, for this replica placement."""
    if SCALE > 1 and layout == 'two-way':
        row = size_basis()['batches'][str(batch)]
        zero = {c: row['freeze_free_gib'][c] + 2 * row['per_worker_gib'][c] for c in CARDS}
        # This measured basis includes a replica on card 2. Never credit it back.
        for c in set(replica_cards(spec)) | {'xpu:3'}:
            zero[c] -= decode_growth()
            if c == 'xpu:1':
                zero[c] -= REPLICA_FREEZE_GIB
        return zero
    zero = dict(ZERO_WORKER_FREE_GIB[layout])
    if SCALE > 1:
        for c in set(replica_cards(spec)) | {'xpu:3'}:
            zero[c] -= decode_growth()
    for card in replica_cards(spec):
        if card != 'xpu:1':
            zero[card] = round(zero[card] - REPLICA_FREEZE_GIB, 3)
    return zero
MEASURED_FACTOR = 1.25
MEASURED_PAD_GIB = 0.25
CARDS = ('xpu:0', 'xpu:1', 'xpu:2', 'xpu:3')


def _finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
# Free GiB per card at the freeze with zero sampler workers, from measured receipts:
# two-way: 95b w2 freeze (2.65, 4.78, 11.84, 14.55) + 2 x the 94f per-worker cost (2.76, 3.00, 0, 0);
# shard4-a: 95b w3 freeze (5.31, 9.45, 2.88, 9.98) + 3 x the 95b worker-2 cost (2.18, 2.10, 0.98, 0.53);
# shard3-c: 94f w2 freeze (5.72, 9.79, 4.04, 14.9) + 2 x the 95-note per-worker cost (2.40, 2.40, 0.96, 0).
ZERO_WORKER_FREE_GIB = {
    'two-way': {'xpu:0': 8.17, 'xpu:1': 10.78, 'xpu:2': 11.84, 'xpu:3': 14.55},
    'shard4-a': {'xpu:0': 11.85, 'xpu:1': 15.75, 'xpu:2': 5.82, 'xpu:3': 11.57},
    'shard3-c': {'xpu:0': 10.52, 'xpu:1': 14.59, 'xpu:2': 5.96, 'xpu:3': 14.9}}


def worker_cost(layout, batch, pool=0):
    """The private-pool bound (also used with the shared pool, which cannot need more)."""
    sized = size_worker_cost(layout, batch, pool)
    if sized is not None:
        return sized
    return {card: SCALE * (PER_BLOCK_GIB[batch] * blocks + (GLUE_GIB[batch] if card == 'xpu:0' else 0.0))
            for card, blocks in LAYOUTS[layout].items()}


def plan(layout, workers, batch, pool=0, calibration=None, spec='xpu:1'):
    if pool and calibration is not None and calibration[0] is not None:
        cost = calibrated_cost(layout, batch, calibration[0])
        basis = 'calibration %s' % calibration[1]
    else:
        cost = worker_cost(layout, batch, pool)
        basis = ('packet 97 measured pooled worker x token ratio x 1.5 + 0.25 GiB' if size_worker_cost(layout, batch, pool) else 'private-pool bound')
    zero = zero_worker_free(layout, spec, batch)
    one = {c: round(zero[c] - cost[c], 3) for c in zero}
    all_w = {c: round(zero[c] - workers * cost[c], 3) for c in zero}
    short = {c: v for c, v in one.items() if v < FLOOR}
    replica_free = one if SCALE == 1 else all_w
    replica_short = {c: replica_free[c] for c in replica_cards(spec) if replica_free[c] < REPLICA_MIN_FREE_GIB}
    return not short and not replica_short and (SCALE == 1 or all(v >= FLOOR for v in all_w.values())), {
                       'output_size': SIZE, 'token_scale': SCALE,
                       'layout': layout, 'workers': workers, 'batch': batch, 'shared_pool': pool,
                       'replica_spec': spec, 'replica_cards': list(replica_cards(spec)),
                       'zero_worker_free_gib': zero,
                       'replica_cards_short_of_probe_room': replica_short,
                       'replica_min_free_gib': REPLICA_MIN_FREE_GIB,
                       'predicted_free_gib_one_worker': one, 'predicted_free_gib_all_workers': all_w,
                       'per_worker_cost_gib': {c: round(v, 3) for c, v in cost.items()},
                       'short_with_one_worker': short,
                       'all_workers_fit_prediction': all(v >= FLOOR for v in all_w.values()),
                       'basis': basis,
                       'assumption': ("worker 0's pooled cost does not exceed the calibrated worker's by more than "
                                      'the margin; the floor re-measured after the chain check at the freeze is the '
                                      'backstop' if basis != 'private-pool bound' else
                                      'private-pool bound, linear in the batch (an upper bound; also with the shared pool)')}


CALIBRATION_SCHEMA = 'ltx.pool-calibration-98.v1'
DEFAULT_CAL_ROOT = str(Path(__file__).resolve().parents[1] / 'data' / 'size-98')


def find_calibration(root, manifest, layout, batch):
    """(receipt, path) of the best matching calibration, or (None, [reasons])."""
    if not manifest:
        return None, ['no manifest given']
    best, reasons = None, []
    for path in sorted(glob.glob(os.path.join(root, '%s-w*-b*-p1-d*' % layout, 'pool-calibration.json'))):
        try:
            rec = json.load(open(path))
        except (OSError, ValueError):
            reasons.append('%s: unreadable' % path)
            continue
        why = []
        if rec.get('schema') != CALIBRATION_SCHEMA:
            why.append('schema')
        if rec.get('packet_manifest_sha256') != manifest:
            why.append('manifest')
        if rec.get('output_size') != SIZE:
            why.append('output size')
        if rec.get('layout') != layout:
            why.append('layout')
        if rec.get('shared_pool') != 1:
            why.append('pool off')
        if isinstance(rec.get('batch'), int) and rec['batch'] > batch:
            why.append('batch above %d' % batch)
        pc = rec.get('per_card_gib')
        if not isinstance(pc, dict) or any(not _finite(pc.get(c)) or pc.get(c) < 0 for c in CARDS):
            why.append('per-card figures missing, partial or not finite')
        if not isinstance(rec.get('batch'), int) or isinstance(rec.get('batch'), bool) or rec.get('batch', 0) < 1:
            why.append('batch not a positive integer')
        if not rec.get('source_identity_sha256') or rec.get('source_identity_match') is not True:
            why.append('source receipts not shown to be from one server run')
        if why:
            reasons.append('%s: %s' % (path, ', '.join(why)))
            continue
        key = (rec['batch'], rec.get('written_unix', 0))
        if best is None or key > best[0]:
            best = (key, rec, path)
    if best is None:
        return None, reasons
    return best[1], best[2]


def calibrated_cost(layout, batch, rec):
    scale = batch / rec['batch']
    return {c: (rec['per_card_gib'][c] * scale * MEASURED_FACTOR + MEASURED_PAD_GIB) if blocks else 0.0
            for c, blocks in LAYOUTS[layout].items()}


def calibrate(before_free, after_free, layout, batch, worker, manifest):
    cost = measured_cost(before_free, after_free)
    if cost is None:
        raise SystemExit('calibrate: both receipts need finite free_bytes for all four cards')
    return {'schema': CALIBRATION_SCHEMA, 'output_size': SIZE, 'packet_manifest_sha256': manifest, 'layout': layout, 'batch': batch,
            'shared_pool': 1, 'worker': worker, 'per_card_gib': {c: round(v, 4) for c, v in cost.items()},
            'written_unix': time.time(),
            'definition': "free device memory before this worker's serial capture minus after it, per card, GiB"}


def measured_cost(prev_free, now_free):
    """Per-card GiB the previous worker's capture took (free before - free after), or None.
    None unless BOTH readings carry a finite, non-negative byte count for every one of the four cards:
    a partial reading must never turn into a zero charge."""
    if not isinstance(prev_free, dict) or not isinstance(now_free, dict):
        return None
    out = {}
    for card in CARDS:
        a, b = prev_free.get(card), now_free.get(card)
        if not _finite(a) or not _finite(b) or a < 0 or b < 0:
            return None
        out[card] = max(0.0, (a - b) / GIB)
    return out


def worker_estimate(layout, batch, pool=0, prev_free=None, now_free=None, calibration=None):
    """(per-card GiB charged for one more worker, basis, bound, measured). `calibration` is a
    (receipt, path) from find_calibration, used only on a pooled server without an in-run
    measurement."""
    bound = worker_cost(layout, batch, pool)
    measured = measured_cost(prev_free, now_free) if pool else None
    if measured is None:
        if pool and calibration is not None and calibration[0] is not None:
            rec, path = calibration
            return (calibrated_cost(layout, batch, rec),
                    'calibration %s (batch %d) x %d/%d x %.2f + %.2f GiB' % (path, rec['batch'], batch, rec['batch'],
                                                                           MEASURED_FACTOR, MEASURED_PAD_GIB),
                    bound, None)
        return bound, ('packet 97 measured pooled worker x token ratio x 1.5 + 0.25 GiB' if size_worker_cost(layout, batch, pool) else 'private-pool bound'), bound, measured
    est = {c: (measured[c] * MEASURED_FACTOR + MEASURED_PAD_GIB) if LAYOUTS[layout].get(c) else 0.0
           for c in bound}
    return est, 'previous worker measured x %.2f + %.2f GiB' % (MEASURED_FACTOR, MEASURED_PAD_GIB), bound, measured


def needed(layout, batch, pre_decode=True, pool=0, prev_free=None, now_free=None, calibration=None, spec='xpu:1'):
    cost = worker_estimate(layout, batch, pool, prev_free, now_free, calibration)[0]
    room = globals()['pre_decode'](spec) if pre_decode else {}
    return {c: FLOOR + cost[c] + room.get(c, 0.0) for c in cost}


def live(free_bytes, layout, batch, pre_decode=True, pool=0, prev_free=None, calibration=None, spec='xpu:1'):
    short = {}
    for card, need in needed(layout, batch, pre_decode, pool, prev_free, free_bytes, calibration, spec).items():
        have = free_bytes.get(card)
        if not _finite(have) or have < need * GIB:
            short[card] = {'free_gib': None if not _finite(have) else round(have / GIB, 3), 'needed_gib': round(need, 3)}
    return not short, short


def _flags(argv):
    pos, flags, i = [], {}, 0
    while i < len(argv):
        if argv[i].startswith('--'):
            flags[argv[i][2:]] = argv[i + 1]
            i += 2
        else:
            pos.append(argv[i])
            i += 1
    return pos, flags


def main(argv):
    pos, flags = _flags(argv[1:])
    global SIZE, SCALE
    SIZE = flags.get('size', '256x256')
    w, h = dimensions(SIZE)
    SCALE = w * h / 65536
    manifest = flags.get('manifest')
    cal_root = flags.get('calibration-root', DEFAULT_CAL_ROOT)
    spec = flags.get('replicas', 'xpu:1')
    replica_cards(spec)
    if pos and pos[0] == 'calibrate' and len(pos) == 6:
        out = flags.get('out')
        if not out or not manifest:
            print('calibrate needs --manifest and --out')
            return 2
        rb, ra = json.load(open(pos[1])), json.load(open(pos[2]))
        if any(r.get('output_size') != SIZE or r.get('sampler_batch') != int(pos[4]) for r in (rb, ra)):
            raise SystemExit('calibration size, batch or layout differs')
        ids = (rb.get('server_identity_sha256'), ra.get('server_identity_sha256'))
        if not ids[0] or ids[0] != ids[1]:
            print('calibrate: the two receipts are not from one server run (server_identity_sha256 %r vs %r)' % ids)
            return 2
        if not (_finite(rb.get('time')) and _finite(ra.get('time')) and rb['time'] < ra['time']):
            print('calibrate: the "before" receipt is not older than the "after" receipt')
            return 2
        before = rb.get('free_bytes') or {}
        after = ra.get('free_bytes') or {}
        rec = calibrate(before, after, pos[3], int(pos[4]), int(pos[5]), manifest)
        rec.update({'before': pos[1], 'after': pos[2], 'source_identity_sha256': ids[0], 'source_identity_match': True})
        Path(out).write_text(json.dumps(rec, indent=2) + '\n')
        print(json.dumps(rec))
        return 0
    pool = int(pos[4]) if len(pos) >= 5 else 0
    if pool not in (0, 1):
        print('shared pool must be 0 or 1')
        return 2
    if pos and pos[0] == 'plan' and len(pos) in (4, 5):
        layout, batch = pos[1], int(pos[3])
        found = find_calibration(cal_root, manifest, layout, batch) if pool else (None, ['pool off'])
        ok, detail = plan(layout, int(pos[2]), batch, pool, found, spec)
        detail['calibration_considered'] = found[1]
        print(json.dumps({'room_for_first_worker': ok, **detail}))
        return 0 if ok else 18
    if pos and pos[0] == 'live' and len(pos) in (4, 5, 6):
        receipt = json.load(open(pos[1]))
        if receipt.get('output_size') != SIZE:
            raise SystemExit('coverage output size differs')
        now = receipt.get('free_bytes') or {}
        prev = None
        if len(pos) == 6:
            previous = json.load(open(pos[5]))
            for key in ('output_size', 'server_identity_sha256', 'sampler_batch'):
                if receipt.get(key) is None or previous.get(key) != receipt[key]:
                    raise SystemExit('previous worker receipt differs: ' + key)
            if not (_finite(previous.get('time')) and _finite(receipt.get('time')) and previous['time'] < receipt['time']):
                raise SystemExit('previous worker receipt time is not older')
            prev = previous.get('free_bytes')
        layout, batch = pos[2], int(pos[3])
        found = find_calibration(cal_root, manifest, layout, batch) if (pool and prev is None) else (None, [])
        ok, short = live(now, layout, batch, pool=pool, prev_free=prev, calibration=found, spec=spec)
        est, basis, bound, measured = worker_estimate(layout, batch, pool, prev, now, found)
        print(json.dumps({'output_size': SIZE, 'room_for_one_more_worker': ok, 'short': short, 'batch': batch, 'shared_pool': pool,
                          'replica_spec': spec, 'pre_decode_gib': pre_decode(spec),
                          'basis': basis, 'charged_gib': {c: round(v, 3) for c, v in est.items()},
                          'private_pool_bound_gib': {c: round(v, 3) for c, v in bound.items()},
                          'previous_worker_measured_gib': (None if measured is None else
                                                           {c: round(v, 3) for c, v in measured.items()}),
                          'calibration_considered': found[1],
                          'needed_gib': {c: round(v, 3) for c, v in
                                         needed(layout, batch, pool=pool, prev_free=prev, now_free=now,
                                                calibration=found, spec=spec).items()}}))
        return 0 if ok else 18
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))

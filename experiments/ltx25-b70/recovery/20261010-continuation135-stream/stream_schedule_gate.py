"""Packet123 live schedule audit. Standard library; reads receipts, never a runtime/endpoint.

Passing means the selected receipt sample meets these identity/schedule checks. It
does not qualify performance, prove device timing, or replace nine-chain qualification.
"""
from stream_contract import display_transient_bytes, receipt_display_transient_bytes
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

CARDS = ['xpu:0', 'xpu:1', 'xpu:2', 'xpu:3']
HASH = re.compile(r'[0-9a-f]{64}\Z')


def _dict(value):
    return value if type(value) is dict else {}


def _rows(value):
    return list(value.values()) if type(value) is dict else value if type(value) is list else []


def _hash(value):
    return type(value) is str and HASH.fullmatch(value) is not None


def _seconds(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def check(receipts, decodes, control_receipts=None, control_decodes=None):
    failures, fallbacks = [], []
    hits, misses, compared = 0, 0, 0
    rows = [r for r in _rows(receipts) if type(r) is dict and r.get('kind') == 'stream']
    decode_map = {r.get('run_name'): r for r in _rows(decodes) if type(r) is dict}
    by_name = {r.get('run_name'): r for r in rows}

    def need(ok, why):
        if not ok:
            failures.append(why)
        return bool(ok)

    need(bool(rows), 'No live stream receipts selected')
    need(len(by_name) == len(rows), 'Duplicate run names')
    seqs = [r.get('stream_seq') for r in rows]
    need(all(type(s) is int and s >= 0 for s in seqs) and len(set(seqs)) == len(seqs),
         'Invalid or duplicate stream sequences')
    options = _dict(rows[0].get('server_options')) if rows else {}
    need(bool(options), 'Missing server options')
    display, ahead, schedule = (options.get(k) for k in
                                 ('display_schedule', 'anchor_read_ahead', 'snapshot_schedule'))
    worker = options.get('display_worker', 'serial')
    need(worker in ('serial', 'parallel'), 'Invalid display worker')
    mode = options.get('snapshot_mode')
    device = options.get('display_device')
    need(device == 'xpu:2' or 'display_replica_transient_budget_bytes' not in options, 'Explicit reserve requires replica')
    need(device in ('xpu:3', 'xpu:2'), 'Invalid or missing display device')
    need(display in ('sampler-a', 'sampler-b', 'eager-display'), 'Invalid display schedule')
    need(type(ahead) is int and ahead in (0, 1), 'Invalid anchor read-ahead option')
    need(schedule in ('full', 'a-xpu3-sync'), 'Invalid snapshot schedule')
    need(mode in ('walk', 'fingerprint'), 'Invalid snapshot mode')
    need(schedule != 'a-xpu3-sync' or mode == 'fingerprint', 'Reduced barriers require fingerprint mode')
    control = control_receipts is not None or control_decodes is not None
    controls = {r.get('stream_seq'): r for r in _rows(control_receipts) if type(r) is dict and r.get('kind') == 'stream'}
    control_ds = {r.get('run_name'): r for r in _rows(control_decodes) if type(r) is dict}
    if control:
        need(control_receipts is not None and control_decodes is not None, 'Both control receipt sets required')
    for r in rows:
        if worker == 'parallel':
            from stream_contract import check_display_worker_scope
            try:
                check_display_worker_scope(worker, r.get('frames'), r.get('placement'), r.get('anchor'),
                    r.get('decoder_graph'), _dict(r.get('levers')).get('anchor_decode'),
                    options.get('aux_residency'), device, display)
            except ValueError as exc:
                need(False, str(exc))
        name = r.get('run_name')
        tag = str(name) + ': '
        need(r.get('committed') is True, tag + 'Uncommitted receipt')
        need(r.get('server_options') == options, tag + 'Server options differ')
        need(r.get('sanity') == {'finite': True, 'shapes': True, 'anchor_chain': True}, tag + 'Sanity failed')
        need(_hash(r.get('qualification_verdict_sha256')), tag + 'Missing qualification verdict binding')
        d = decode_map.get(name, {})
        need(bool(d) and d.get('kind') == 'stream' and d.get('stream_seq') == r.get('stream_seq') and
             d.get('prompt_id') == r.get('prompt_id') and type(r.get('prompt_id')) is str,
             tag + 'Decode identity differs or missing')
        if 'display_worker' in options:
            try:
                from stream_receipts import validate_display_worker
                validate_display_worker(d, options)
            except ValueError as exc:
                need(False, tag + str(exc))
        ds = _dict(d.get('schedule'))
        need(ds.get('display_schedule') == display, tag + 'Decode display option differs')
        need(ds.get('gated') is False, tag + 'Live stream incorrectly marked gated')
        anchor = _dict(r.get('anchor_out')).get('sha256')
        need(_hash(anchor) and d.get('last_frame_sha256') == anchor, tag + 'Anchor binding differs')
        cone = _dict(r.get('levers')).get('anchor_decode') == 'cone'
        need(d.get('display_device') == device, tag + 'Display device differs or missing')
        proof = d.get('display_replica')
        if device == 'xpu:2':
            try:
                allowance = receipt_display_transient_bytes(r['frames'], options)
            except (ValueError, KeyError):
                need(False, tag + 'Invalid replica transient allowance')
                allowance = 0
            need(r.get('frames') in (121, 145, 169) and r.get('anchor') == 'frame' and cone and display == 'eager-display',
                 tag + 'Replica launch scope differs')
            proof = _dict(proof)
            need(proof.get('device') == 'xpu:2' and proof.get('reference_device') == 'xpu:3' and
                 proof.get('mode') == 'eager-uncached' and 'equal' in proof and proof['equal'] is None,
                 tag + 'Live replica proof missing or claims an unperformed full-image comparison')
            residency = _dict(proof.get('residency'))
            need(residency.get('device') == 'xpu:2' and residency.get('encoder_bytes') == 0 and
                 residency.get('graph_pool_bytes') == 0 and residency.get('weight_copy_bitwise_equal') is True and
                 residency.get('single_decode_thread') is True and residency.get('native_seed') == 0 and
                 residency.get('dtype') == 'torch.bfloat16' and type(residency.get('resident_bytes')) is int and
                 residency['resident_bytes'] > 0 and residency.get('floor_bytes') == 2**31 and
                 residency.get('transient_budget_bytes') == allowance and
                 type(residency.get('calls')) is int and residency['calls'] > 0,
                 tag + 'Replica residency policy missing or differs')
            memory = _dict(residency.get('last_decode'))
            before = _dict(memory.get('before'))
            need(type(before.get('free_bytes')) is int and before['free_bytes'] >= (allowance + 2**31) and
                 before.get('floor_bytes') == 2**31 and before.get('transient_budget_bytes') == allowance and
                 before.get('new_resident_bytes') == 0 and
                 type(before.get('margin_bytes')) is int and before['margin_bytes'] == before['free_bytes']-(allowance + 2**31) and
                 type(memory.get('after_free_bytes')) is int and memory['after_free_bytes'] >= 2**31 and
                 _seconds(memory.get('seconds')), tag + 'Replica memory evidence missing or unsafe')
            counters = [_dict(memory.get(key)) for key in ('allocator_before', 'allocator_after')]
            valid_counters = all(all(type(row.get(key)) is int and row[key] >= 0
                                     for key in ('allocated', 'reserved', 'peak_allocated')) for row in counters)
            need(valid_counters, tag + 'Replica allocator counters missing or invalid')
            if valid_counters:
                old, new = counters
                growth = max(0, new['peak_allocated']-old['allocated'], new['reserved']-old['reserved'])
                need(all(row['allocated'] <= row['reserved'] and row['peak_allocated'] >= row['allocated']
                         for row in counters) and new['peak_allocated'] >= old['peak_allocated'] and
                     memory.get('peak_is_device_global_not_reset') is True and
                     type(memory.get('observed_peak_or_reservation_growth_bytes')) is int and
                     memory['observed_peak_or_reservation_growth_bytes'] == growth and growth <= allowance,
                     tag + 'Replica allocator growth exceeds budget or its evidence differs')
        else:
            need(proof is None, tag + 'Replica ran with display device off')
        if cone:
            ad = _dict(d.get('anchor_decode'))
            need(ad.get('mode') == 'cone' and ad.get('equal') is True and
                 ad.get('last_frame_sha256') == anchor and ad.get('display_last_frame_sha256') == anchor,
                 tag + 'Cone/display byte check missing or unequal')
        if display == 'sampler-b' and cone:
            release = _dict(ds.get('display_release'))
            reason = release.get('reason')
            go, extra = ds.get('go_wait_s'), release.get('waited_s')
            need(_seconds(go) and _seconds(extra) and go + extra <= 3.000002,
                 tag + 'Combined display waits exceed 3 seconds or are missing')
            if reason == 'matching-successor-sampler-b-start':
                event = _dict(release.get('event'))
                btime, start = event.get('sampler_b_start_ns'), _dict(d.get('timing_ns')).get('display_start')
                need(event.get('source_run_name') == name and event.get('anchor_sha256') == anchor and
                     type(event.get('consumer_run_name')) is str and event['consumer_run_name'] != name and
                     type(event.get('prompt_id')) is str and type(btime) is int and btime > 0 and
                     type(start) is int and start >= btime,
                     tag + 'Display release is not bound to matching successor sampler B')
                successor = by_name.get(event.get('consumer_run_name'))
                if successor is not None:
                    ain = _dict(successor.get('anchor_in'))
                    need(successor.get('prompt_id') == event.get('prompt_id') and
                         ain.get('source_run_name') == name and ain.get('sha256') == anchor and
                         _dict(successor.get('timing_ns')).get('sampler_b_start') == btime,
                         tag + 'Successor receipt disagrees with release event')
            elif reason == 'bound':
                fallbacks.append(name)
                need(False, tag + 'Bounded display fallback: sample cannot admit a speed comparison')
            else:
                need(False, tag + 'Missing/invalid/halted live display release')
        snapshots = r.get('snapshots')
        snapshots = snapshots if type(snapshots) is list else []
        middle = ['A-before', 'A-after', 'B-before', 'B-after'] if r.get('anchored') and r.get('anchor') == 'frame' else []
        if r.get('anchored') and r.get('anchor') == 'mixed':
            middle = ['B-before', 'B-after']
        need([_dict(s).get('label') for s in snapshots] == ['request-before'] + middle + ['request-after'],
             tag + 'Snapshot labels missing or out of order')
        near = False
        for snap in snapshots:
            snap = _dict(snap)
            label = snap.get('label')
            margin = snap.get('min_margin_bytes')
            need(type(margin) is int, tag + str(label) + ': missing memory margin')
            if worker == 'parallel' or (r.get('frames') == 169 and device == 'xpu:2'):
                need(type(margin) is int and margin >= 3 * 2**28, tag + 'Packet125 memory margin below0.75GiB')
            near = near or (type(margin) is int and margin <= 2**29)
            need(snap.get('mode') == mode and snap.get('memory_cards') == CARDS,
                 tag + str(label) + ': snapshot mode or all-card readings differ')
            reduced = snap.get('synchronized') == ['xpu:3']
            if reduced:
                need(schedule == 'a-xpu3-sync' and mode == 'fingerprint' and
                     label in ('A-before', 'A-after') and snap.get('dual') is False and
                     type(r.get('stream_seq')) is int and r['stream_seq'] % 20 != 0,
                     tag + str(label) + ': forbidden reduced barriers')
            else:
                need(snap.get('synchronized') == CARDS, tag + str(label) + ': four-card barriers missing')
            if snap.get('dual') is True:
                need(snap.get('agree') is True and not reduced, tag + str(label) + ': dual verdict disagrees')
            need(type(snap.get('dual')) is bool, tag + str(label) + ': missing dual flag')
            if mode == 'fingerprint' and (near or (type(r.get('stream_seq')) is int and r['stream_seq'] % 20 == 0)):
                need(snap.get('dual') is True, tag + str(label) + ': required dual snapshot missing')
            if mode == 'walk':
                need(snap.get('dual') is False, tag + str(label) + ': walk mode unexpectedly dual')
        source = r.get('anchor_read_source')
        if ahead and r.get('anchored') and r.get('anchor') == 'frame':
            if source == 'verified-read-ahead':
                hits += 1
            else:
                misses += 1
                need(source in ('native-miss', 'native-file-changed'), tag + 'Unknown read-ahead consume source')
        elif not ahead and r.get('anchored') and r.get('anchor') == 'frame':
            need(source == 'native', tag + 'Read-ahead ran with option off')
        if control:
            cr = controls.get(r.get('stream_seq'), {})
            cd = control_ds.get(cr.get('run_name'), {})
            same = bool(cr) and bool(cd)
            for key in ('seed', 'frames', 'anchor', 'reset', 'prompt_sha256'):
                same = same and key in r and key in cr and r[key] == cr[key]
            for tensor in ('images', 'waveform'):
                value = _dict(_dict(d.get('tensors')).get(tensor)).get('sha256')
                same = same and _hash(value) and value == _dict(_dict(cd.get('tensors')).get(tensor)).get('sha256')
            same = same and anchor == _dict(cr.get('anchor_out')).get('sha256') and anchor == cd.get('last_frame_sha256')
            if need(same, tag + 'Control identity or output bytes differ/missing'):
                compared += 1
    if ahead:
        need(hits > 0, 'Read-ahead selected but no verified live hit observed')
    return {'schema': 'ltx.stream123.live-schedule-gate.v1', 'passed': not failures,
            'failures': failures, 'selected_live_chunks': len(rows), 'server_options': options,
            'read_ahead_hits': hits, 'read_ahead_misses': misses, 'bounded_fallbacks': fallbacks,
            'control_compared_chunks': compared, 'performance_qualified': False,
            'limits': 'Receipt audit only; no performance claim, no device proof; qualification receipts skipped.'}


def read_run(run, first, last, file_hashes):
    """Explicit directory; no inferred run, endpoint, imports or writes."""
    folder = Path(run) / 'receipts'
    receipts, decodes = [], []
    for path in sorted(folder.glob('receipt-*.json')):
        raw = path.read_bytes()
        file_hashes[str(path)] = hashlib.sha256(raw).hexdigest()
        r = json.loads(raw)
        if r.get('kind') != 'stream' or type(r.get('stream_seq')) is not int or not first <= r['stream_seq'] <= last:
            continue
        name = r.get('run_name')
        if type(name) is not str or not re.fullmatch(r'[A-Za-z0-9_-]+', name):
            raise ValueError('Unsafe run name in receipt')
        dp = folder / ('decode-' + name + '.json')
        dr = dp.read_bytes()
        file_hashes[str(dp)] = hashlib.sha256(dr).hexdigest()
        receipts.append(r)
        decodes.append(json.loads(dr))
    return receipts, decodes


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', required=True, type=Path)
    p.add_argument('--control-run', type=Path)
    p.add_argument('--first', type=int, default=0)
    p.add_argument('--last', type=int, default=2**63 - 1)
    args = p.parse_args(argv)
    if args.first < 0 or args.last < args.first:
        p.error('Require 0 <= first <= last')
    hashes = {}
    try:
        receipts, decodes = read_run(args.run, args.first, args.last, hashes)
        controls = read_run(args.control_run, args.first, args.last, hashes) if args.control_run else (None, None)
        result = check(receipts, decodes, *controls)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        result = {'passed': False, 'failures': ['Receipt read/parse error: ' + str(exc)], 'performance_qualified': False}
    result['files_sha256'] = hashes
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

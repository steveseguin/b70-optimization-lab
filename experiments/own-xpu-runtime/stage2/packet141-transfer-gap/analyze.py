#!/usr/bin/env python3
"""Read completed packet141 diagnostic evidence on CPU; never launch or queue."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import resource
from statistics import median
import sys

P = Path(__file__).resolve().parent
ARMS = ('a', 'b', 'c', 'natural')
CAP = 200_000_000


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    require(path.stat().st_size <= 20_000_000, 'oversized JSON: ' + str(path))
    return json.loads(path.read_text())


def rows(path):
    with path.open() as stream:
        while line := stream.readline(1_000_001):
            require(len(line) <= 1_000_000, 'oversized JSONL row')
            yield json.loads(line)


def positive(value, name):
    require(type(value) in (int, float) and math.isfinite(value) and value > 0, name)
    return value


def broad(name):
    if name.startswith('hc.'):
        return 'HC'
    if name.startswith(('gdn.', 'qsa.')) or name == 'attention':
        return 'attention'
    if name in ('expsgate', 'expsup'):
        return 'MoE gate/up'
    if name == 'expsdown':
        return 'MoE down'
    if name in ('router', 'shexpdown', 'shexpgate', 'shexpup', 'shared_gate'):
        return 'shared + fused router'
    if name == 'route':
        return 'route'
    if name in ('ple.kn', 'ple.qn', 'ple.cn') or name.endswith('.norm'):
        return 'norms'
    return 'small'


def decision(classes, validity, reg):
    """A validity failure can only withhold the owner's registered verdict."""
    require(bool(classes), 'empty class table')
    if validity:
        return dict(verdict='inconclusive', reasons=validity, followup_classes=[])
    follow = [name for name, r in classes.items()
              if r['a_over_b'] >= reg['followup_ratio_at_least']
              and r['a_ms'] >= reg['followup_class_ms_at_least']]
    if follow:
        return dict(verdict='class-specific-layout-allocation-order', followup_classes=follow)
    if all(r['a_over_b'] <= reg['close_if_all_ratios_at_most'] for r in classes.values()):
        return dict(verdict='close-kernel-bound-under-diagnostic', followup_classes=[],
                    interpretation='Retain the 59–60 working band; no new speed measurement.')
    return dict(verdict='report-and-close-intermediate', followup_classes=[])


def timings(plan, reg, event_rows, halves, controls, states, touch_rows):
    sites = {r['site']: r for r in plan['sites']}
    require(len(sites) == len(plan['sites']), 'duplicate plan site')
    require(plan['kernels'] == sum(r['kernel_count'] for r in sites.values()), 'plan kernel count')
    active = [i for i, r in sites.items() if r['kernel_count']]
    require(active == sorted(active), 'plan site order')
    blocks = reg['blocks']
    expected_halves = {(b, a) for b in range(blocks) for a in ARMS}
    touches = {r['site']: r for r in touch_rows}
    require(len(touch_rows) == len(sites) and set(touches) == set(sites), 'touch plan coverage')
    for i, r in touches.items():
        require(r['kernel_count'] == sites[i]['kernel_count'], 'touch kernel count')
        require(type(r['pretouch_events']) is int and r['pretouch_events'] >= 0
                and type(r['pretouch_bytes']) is int and r['pretouch_bytes'] >= 0, 'touch sizes')
    # Every expected event appears once, in source order, including warmups and
    # individual passes within a fused site. No optional prompt/site subset.
    expected = {}
    for b, arm in expected_halves:
        seq = []
        for i in active:
            for repeat in range(reg['warm_repeats'] if arm == 'b' else 1):
                if arm == 'c':
                    seq.extend([(i, repeat, True)] * touches[i]['pretouch_events'])
                seq.extend([(i, repeat, False)] * sites[i]['kernel_count'])
        expected[b, arm] = seq
    offset = Counter()
    previous_end = {}
    first = {}
    sums = defaultdict(lambda: defaultdict(int))
    detail = defaultdict(lambda: defaultdict(int))
    touch_ns = Counter()
    all_ns = Counter()
    event_count = 0
    for row in event_rows:
        key = row['block'], row['arm']
        require(key in expected_halves, 'unregistered block/arm')
        k = offset[key]
        require(k < len(expected[key]), 'extra event')
        require(type(row['pretouch']) is bool and type(row['warmup']) is bool, 'event flags')
        require((row['site'], row['repeat'], row['pretouch']) == expected[key][k], 'event sequence/coverage')
        site = sites[row['site']]
        require(row['label'] == site['label'] and row['class'] == site['class'], 'event class/label changed')
        require(row['warmup'] == (row['arm'] == 'b' and row['repeat'] < reg['warmup_repeats']), 'warmup flag')
        start, end = row['start_ns'], row['end_ns']
        require(type(start) is int and type(end) is int and 0 < start < end
                and end - start < 4_000_000_000, 'invalid event clock')
        require(start >= previous_end.get(key, 0), 'overlapping/reordered serial event clock')
        first.setdefault(key, start)
        previous_end[key] = end
        duration = end - start
        if row['pretouch']:
            touch_ns[key] += duration
        else:
            all_ns[key] += duration
            if not row['warmup']:
                sample = (*key, row['repeat'])
                sums[sample][broad(row['class'])] += duration
                detail[sample][row['class']] += duration
        offset[key] += 1
        event_count += 1
    require(all(offset[k] == len(v) for k, v in expected.items()), 'missing events')
    half_map = {(r['block'], r['arm']): r for r in halves}
    require(len(halves) == len(expected_halves) and set(half_map) == expected_halves, 'half coverage')
    for key, row in half_map.items():
        require(row['routes_equal'] is True and row['state_equal'] is True, 'half equality failed')
        require(row['arm'] == ARMS[(row['block'] + row['slot']) % 4]
                and row['slot'] in range(4), 'cyclic order')
        positive(row['wall_ms'], 'half wall clock')
        if key[1] != 'b':
            require(row['kernel_ns'] == all_ns[key] and row['pretouch_ns'] == touch_ns[key]
                    and row['event_span_ns'] == previous_end[key] - first[key], 'half/event accounting differs')
        else:
            require(row['kernel_ns'] == row['pretouch_ns'] == row['event_span_ns'] == 0, 'warm accounting format')
    control_map = {r['block']: r for r in controls}
    require(len(controls) == blocks and set(control_map) == set(range(blocks)), 'control coverage')
    for row in controls:
        require(row['state_equal'] is True, 'control state mismatch')
        positive(row['wall_ms'], 'control wall clock')
    state_map = {(r['block'], r['arm']): r['sha256_by_allocation'] for r in states}
    require(len(states) == len(expected_halves) and set(state_map) == expected_halves, 'state coverage')
    reference = state_map[0, 'a']
    require(reference and all(re.fullmatch(r'[0-9a-f]{64}', v) for v in reference.values()), 'invalid state hash')
    require(all(v == reference for v in state_map.values()), 'whole-half state hashes differ')
    classes = set(sums[0, 'a', 0])
    require(classes == set(reg['classes']), 'class coverage')
    require(all(set(v) == classes for v in sums.values()), 'partial class sample')
    warm = range(reg['warmup_repeats'], reg['warm_repeats'])

    def aggregate(table):
        names = sorted(table[0, 'a', 0])
        result = {}
        for name in names:
            arm_ms = {a: [median([table[b, a, r][name] / 1e6 for r in warm])
                           if a == 'b' else table[b, a, 0][name] / 1e6
                           for b in range(blocks)] for a in ARMS}
            result[name] = {a + '_ms': median(v) for a, v in arm_ms.items()}
            result[name]['block_ms'] = arm_ms
            for numerator, denominator in [('a', 'b'), ('c', 'b'), ('c', 'a'), ('natural', 'a')]:
                result[name][numerator + '_over_' + denominator] = median(
                    [n / d for n, d in zip(arm_ms[numerator], arm_ms[denominator])])
        return result

    result = aggregate(sums)
    pretouch = dict(bytes_per_half=sum(touches[i]['pretouch_bytes'] for i in active),
                    events_per_half=sum(touches[i]['pretouch_events'] for i in active),
                    time_ms=median([touch_ns[b, 'c'] / 1e6 for b in range(blocks)]))
    validity = []
    for name, row in result.items():
        if row['a_ms'] >= reg['forced_cold_validity_min_class_ms'] and not (1 - reg['forced_cold_natural_max_relative_difference'] <= row['natural_over_a'] <= 1 + reg['forced_cold_natural_max_relative_difference']):
            validity.append('cold/no-extra-eviction disagreement: ' + name)
    overhead = median([half_map[b, 'a']['wall_ms'] / control_map[b]['wall_ms'] for b in range(blocks)])
    if not (1 - reg['instrumented_control_max_relative_difference'] <= overhead <= 1 + reg['instrumented_control_max_relative_difference']):
        validity.append('instrumented/control wall difference exceeds 10%')
    gaps = {}
    for arm in ('a', 'c', 'natural'):
        span = median([half_map[b, arm]['event_span_ns'] / 1e6 for b in range(blocks)])
        gap = median([(half_map[b, arm]['event_span_ns'] - all_ns[b, arm] - touch_ns[b, arm]) / 1e6 for b in range(blocks)])
        require(gap >= 0 and span > 0, 'negative queue gap')
        gaps[arm] = dict(span_ms=span, between_events_ms=gap, fraction=gap / span,
                         kernel_ms=median([all_ns[b, arm] / 1e6 for b in range(blocks)]),
                         pretouch_ms=median([touch_ns[b, arm] / 1e6 for b in range(blocks)]),
                         wall_ms=median([half_map[b, arm]['wall_ms'] for b in range(blocks)]))
        if gap >= reg['material_issue_gap_ms'] and gap / span > reg['material_issue_gap_fraction']:
            validity.append('material between-kernel issue gap: ' + arm)
    return dict(classes=result, original_site_classes=aggregate(detail), event_count=event_count,
                state_allocation_count=len(reference), controls=controls, timing=gaps, pretouch=pretouch,
                warm_wall_ms=[half_map[b, 'b']['wall_ms'] for b in range(blocks)],
                instrumented_over_control_wall=overhead, **decision(result, validity, reg))


def analyze(output):
    from capture_identity import verify, verify_identity
    verify()
    output = output.resolve()
    require(output.is_dir(), 'device evidence pending: output directory absent')
    total = 0
    for path in output.rglob('*'):
        require(not path.is_symlink(), 'symlink in device evidence')
        if path.is_file():
            total += path.stat().st_size
    require(total <= CAP, 'probe output exceeds 200 MB')
    window = read(output / 'window.json')
    require(window.get('passed') is True and window.get('device_executed') is True
            and window.get('device_complete') is True and window.get('lease_released') is True
            and window.get('child_still_running') is False and not window.get('child_retained')
            and not window.get('stop_reasons') and window.get('diagnostic_only') is True, 'window not complete and clean')
    files = window['files']
    require(files, 'window hashes missing')
    for name, digest in files.items():
        path = output / name
        require(path.resolve().is_relative_to(output), 'unsafe evidence path')
        require(sha(path) == digest, 'changed evidence: ' + name)
    identity = read(output / 'identity.json')
    verify_identity(identity)
    require(window['identity'] == identity, 'window identity changed')
    coord = read(output / 'lane-coordination.json')
    require(coord.get('passed') is True and coord.get('released_before_report') is True, 'lane release unproven')
    require(read(output / 'run/teardown.json').get('drained') is True, 'drain unproven')
    proof = read(output / 'run/report-inputs.json')
    require(proof.get('passed') is True and proof.get('device_isolation', {}).get('passed') is True, 'oracle/isolation receipt')
    suite = read(P / 'suite.snapshot.json')
    require(read(output / 'suite-manifest.snapshot.json') == suite, 'suite changed')
    require(len(proof['requests']) == 2, 'oracle request coverage')
    oracle = suite['prompts'][0]['expected_tokens']
    for request, count, name in zip(proof['requests'], (47, 8), ('incident-retrospective', 'post-probe')):
        require(request.get('passed') is True and request.get('exact_reference') is True
                and request['tokens'] == oracle[:count], 'token oracle mismatch')
        receipt = read(output / 'run' / name / 'receipt.json')
        require(receipt['tokens'] == request['tokens'] and receipt.get('exact_reference') is True, 'model receipt differs')
    native = output / 'run/incident-retrospective/rank0'
    complete = read(native / 'p141-complete.json')
    require(complete == dict(passed=True, diagnostic_only=True, blocks=4, arms=4,
                             arithmetic='iq3-p49-split32-v1'), 'native completion mismatch')
    mandatory = ['identity.json', 'suite-manifest.snapshot.json', 'run/teardown.json', 'run/report-inputs.json',
                 'run/incident-retrospective/receipt.json', 'run/post-probe/receipt.json']
    mandatory += ['run/incident-retrospective/rank0/' + name for name in (
        'p141-complete.json', 'p141-events.jsonl', 'p141-halves.jsonl', 'p141-controls.jsonl',
        'p141-state-hashes.jsonl', 'p141-touch-plan.jsonl')]
    require(all(name in files for name in mandatory), 'required evidence not hash-bound')
    result = timings(read(P / 'probe-plan.json'), read(P / 'preregistration.json'),
                     rows(native / 'p141-events.jsonl'), list(rows(native / 'p141-halves.jsonl')),
                     list(rows(native / 'p141-controls.jsonl')), list(rows(native / 'p141-state-hashes.jsonl')),
                     list(rows(native / 'p141-touch-plan.jsonl')))
    result.update(schema='packet141.analysis.v1', evidence_valid=True, diagnostic_only=True,
                  speed_claim=False, arithmetic='iq3-p49-split32-v1', exact_tokens=55,
                  window_sha256=sha(output / 'window.json'), evidence_bytes=total,
                  aggregation='Sum events per class in each complete half; median four warm repeats per block; median four matched block ratios.',
                  limitations=['One captured workload, rank0 only, no throughput qualification.',
                               'No-extra-eviction follows state restoration; cache occupancy is not directly measured.',
                               'Warm state restores can affect residency; restore costs are excluded.',
                               'Fused events remain indivisible; route includes fused shared activation and shared-down includes mixture/combine.',
                               'Pre-touch traffic and timing are reported separately, not a free speedup.'])
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, help='Optional analysis JSON, outside the sealed input tree')
    ap.add_argument('--input', type=Path, default=P / 'evidence/probe-B-repair141c')
    args = ap.parse_args()
    if args.output and args.output.resolve().is_relative_to(args.input.resolve()):
        ap.error('analysis output must be outside the sealed input tree')
    code = 0
    try:
        result = analyze(args.input)
    except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError) as error:
        result = dict(schema='packet141.analysis.v1', evidence_valid=False,
                      diagnostic_only=True, speed_claim=False, verdict='pending-or-invalid', reason=str(error))
        code = 2
    text = json.dumps(result, indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.write_text(text)
    print(text, end='')
    return code



if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    raise SystemExit(main())

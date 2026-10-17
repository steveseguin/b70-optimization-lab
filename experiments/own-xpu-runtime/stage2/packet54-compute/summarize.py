#!/usr/bin/env python3
"""Strict packet54 evidence validation; no device or model work occurs here."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
CLASSES = ('route', 'gdn.recurrence', 'hc.inject_mix_norm', 'ffn.combine')
VARIANTS = ('route-rank4', 'route-exp32-rank4', 'rows4-shared', 'rows8-shared', 'mix-vector4',)
CLASS_VARIANTS = {'route': ('route-rank4', 'route-exp32-rank4'), 'gdn.recurrence': ('rows4-shared', 'rows8-shared'), 'hc.inject_mix_norm': ('mix-vector4',), 'ffn.combine': ()}
EXPECTED_BUFFERS = {'route': 8, 'gdn.recurrence': 5, 'hc.inject_mix_norm': 11, 'ffn.combine': 4}
EXPECTED_BYTES = {'route': 4684, 'gdn.recurrence': 1585164, 'hc.inject_mix_norm': 53788, 'ffn.combine': 20492}
EXPECTED_EVENTS = {'route': {'control': 4, 'route-rank4': 4, 'route-exp32-rank4': 4}, 'gdn.recurrence': {'control': 1, 'rows4-shared': 1, 'rows8-shared': 1}, 'hc.inject_mix_norm': {'control': 10, 'mix-vector4': 10}, 'ffn.combine': {'control': 1}}
BANKED_US = (23.4385, 23.4375)
WARMUP, ITERATIONS, EXACT_FIXTURES = 10, 210, 2

def require(ok, message):
    if not ok:
        raise ValueError(message)

def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def native_receipt(run, mode):
    row = json.loads((run/'receipt.json').read_text())
    require(row.get('schema') == 'ownrt.packet54.bench.v1' and row.get('mode') == mode
            and row.get('passed') is True and row.get('safe_to_exit') is True
            and row.get('device_executed') is (mode not in ('cpu', 'cpu-full')), 'native gate/teardown/backend failed')
    return row

def manifest(run):
    row = json.loads((run/'manifest.json').read_text())
    registered = json.loads((HERE/'manifest.json').read_text())
    require(row == registered, 'native manifest differs from sealed registration')
    require(set(row['classes']) == set(CLASSES) and len(row['classes']) == len(CLASSES)
            and tuple(row['variants']) == VARIANTS, 'class/variant census differs')
    require(row['warmup'] == WARMUP and row['iterations'] == ITERATIONS
            and row['exact_fixtures'] == EXACT_FIXTURES, 'case counts changed')
    require(row.get('class_variants') == {c:list(v) for c,v in CLASS_VARIANTS.items()},
            'class-specific variant census differs')
    require(row.get('m_values') == [1,2] and row.get('routes') == 10,
            'serial rows or routed expert count differ')
    require(row.get('expected_buffers') == EXPECTED_BUFFERS
            and row.get('expected_bytes') == EXPECTED_BYTES, 'production capture census differs')
    require(row.get('expected_events') == EXPECTED_EVENTS, 'production compute-event census differs')
    return row

def _hash(value):
    return isinstance(value, str) and len(value) == 64 and set(value) <= set('0123456789abcdef')

def exceptional(run, mode='exact'):
    """Same-backend exceptional production parity; never a CPU/device oracle."""
    require(mode in ('exact', 'cpu-full', 'timing'), 'exception fixture mode differs')
    path = Path(run) / 'exceptions.jsonl'
    require(path.is_file(), 'exception comparison sidefile missing')
    rows = read_rows(path)
    expected = {('hc.mix', 'mix-vector4'): (4, 5132)}
    require(len(rows) == (0 if mode == 'timing' else len(expected)), 'exception comparison census differs')
    if not rows:
        return []
    observed = {}
    for row in rows:
        require(isinstance(row, dict) and set(row) == {'class', 'variant', 'equal', 'sha256', 'production_sha256', 'buffers', 'bytes'},
                'exception comparison fields differ')
        require(isinstance(row['class'], str) and isinstance(row['variant'], str),
                'exception comparison class/variant type differs')
        key = row['class'], row['variant']
        require(key in expected and key not in observed, 'exception comparison duplicate/foreign class/variant')
        require(row['equal'] is True and _hash(row['sha256']) and row['sha256'] == row['production_sha256'],
                'exception production byte mismatch')
        buffers, size = expected[key]
        require(type(row['buffers']) is int and row['buffers'] == buffers
                and type(row['bytes']) is int and row['bytes'] == size,
                'exception output capture census differs')
        observed[key] = row
    require(set(observed) == set(expected), 'exception comparison keys incomplete')
    return [observed[key] for key in sorted(observed)]

def exact(run):
    run = Path(run)
    receipt, spec = native_receipt(run, 'exact'), manifest(run)
    exceptions = exceptional(run)
    rows = read_rows(run/'comparisons.jsonl')
    expected = {(cls, var, m, token, fixture) for cls in CLASSES for var in ('control', *CLASS_VARIANTS[cls])
                for m in (1,2) for token in range(m) for fixture in range(EXACT_FIXTURES)}
    observed = {}
    for row in rows:
        key = row['class'], row['variant'], row['m'], row['token_row'], row['iteration']
        require(key in expected and key not in observed, 'duplicate/foreign exact case')
        require(row.get('equal') is True and _hash(row.get('sha256'))
                and row['sha256'] == row.get('cpu_sha256'), 'CPU-reference byte mismatch')
        require(row.get('production_equal') is True
                and row['sha256'] == row.get('production_sha256'), 'production byte mismatch')
        require(type(row.get('buffers')) is int and row['buffers'] == spec['expected_buffers'][row['class']],
                'incomplete observable-output capture')
        require(type(row.get('bytes')) is int and row['bytes'] == spec['expected_bytes'][row['class']],
                'observable-output byte extent differs')
        observed[key] = row
    require(set(observed) == expected and receipt.get('checks') == len(expected), 'exact campaign incomplete')
    for (cls, variant, m, token, fixture), row in observed.items():
        control = observed[cls, 'control', m, token, fixture]
        require(row['sha256'] == control['sha256'], 'candidate differs from captured production control')
    # Only canonical captures define fresh-process determinism, never elapsed times.
    captures = [dict(key=list(k), sha256=observed[k]['sha256']) for k in sorted(observed)]
    identity = hashlib.sha256(json.dumps(dict(ordinary=captures, exceptional=exceptions), sort_keys=True).encode()).hexdigest()
    return dict(passed=True, exact_output_identity=identity, comparisons=len(rows),
                production_equal=True, unchanged_arithmetic=True,
                exceptional_comparisons=len(exceptions),
                exceptional_scope='same-backend production parity; no CPU/device oracle claim')

def timing(run):
    run = Path(run)
    native_receipt(run, 'timing')
    spec = manifest(run)
    exceptional(run, 'timing')
    rows = read_rows(run/'iterations.jsonl')
    expected = {(cls, variant, m, token, i, arm)
                for cls in CLASSES for variant in CLASS_VARIANTS[cls] for m in (1,2)
                for token in range(m) for i in range(ITERATIONS) for arm in ('control','candidate')}
    observed = {}
    for row in rows:
        var = row['pair_variant']
        require(row['variant'] in ('control',var), 'timing arm differs from pair')
        arm = 'control' if row['variant'] == 'control' else 'candidate'
        key = row['class'], var, row['m'], row['token_row'], row['iteration'], arm
        require(key in expected and key not in observed, 'duplicate/foreign timing case')
        require(row.get('warmup') is (row['iteration'] < WARMUP), 'warmup identity differs')
        events = row.get('events', [])
        require(len(events) == spec['expected_events'][row['class']][row['variant']], 'compute event count differs')
        seen, total = set(), 0
        for event in events:
            start, end = event.get('start_ns'), event.get('end_ns')
            require(type(start) is int and type(end) is int and 0 < start < end
                    and end-start < 4_000_000_000, 'invalid compute event endpoints')
            require((start,end) not in seen, 'duplicate compute event')
            seen.add((start,end)); total += end-start
        require(type(row.get('gpu_ns')) is int and total > 0 and total == row['gpu_ns'], 'event sum differs')
        observed[key] = row['gpu_ns']
    require(set(observed) == expected, 'timing campaign incomplete')
    result = {}
    for cls in CLASSES:
        result[cls] = {}
        for variant in CLASS_VARIANTS[cls]:
            result[cls][variant] = {}
            for m in (1,2):
                def values(arm):
                    return [sum(observed[cls,variant,m,token,i,arm] for token in range(m))/1000
                            for i in range(WARMUP,ITERATIONS)]
                current, candidate = values('control'), values('candidate')
                saved = [a-b for a,b in zip(current,candidate)]
                ordered = sorted(saved)
                result[cls][variant][str(m)] = dict(
                    control_us=statistics.median(current), candidate_us=statistics.median(candidate),
                    median_paired_saved_us=statistics.median(saved), p10_paired_saved_us=ordered[19],
                    p90_paired_saved_us=ordered[179], measured_pairs=200)
    return dict(passed=True, device_executed=True, microbenchmark_only=True, model_speed_claim=False,
                classes=result, timing_definition='sum of all completed compute-event durations for each class; M2 sums both serial rows')

def choose(summaries):
    require(len(summaries) == 2, 'two timing owners required')
    choices, totals = {}, [0.,0.]
    for cls in CLASSES:
        options = {'control': [0.,0.]}
        options.update({var:[s['classes'][cls][var]['1']['median_paired_saved_us'] for s in summaries]
                        for var in CLASS_VARIANTS[cls]})
        require(all(math.isfinite(v) for saves in options.values() for v in saves), 'nonfinite saving')
        selected = sorted(options, key=lambda name: (-min(options[name]), name != "control", name))[0]
        saved = options[selected]
        choices[cls] = dict(variant=selected, owner_saved_us=saved)
        totals = [a+b for a,b in zip(totals,saved)]
    return dict(selected_classes=choices, owner_saved_us=totals, threshold_us=25,
                compute_proceeds=all(value >= 25 for value in totals),
                banked_p53b_owner_us=list(BANKED_US), combined_owner_us=[a+b for a,b in zip(BANKED_US,totals)],
                integration_threshold_us=40, packet49d_trigger=all(a+b>=40 for a,b in zip(BANKED_US,totals)),
                decision_metric='sum of per-class paired median savings using one common selection; ordinary M1 only',
                oracle_started=False, engine_integrated=False)

def fresh_pair(paths):
    require(len(paths) == 2 and len({str(Path(p).resolve()) for p in paths}) == 2, 'two different timing windows required')
    from window_support import sealed_gate, prerequisite, verify_files, sha
    sealed_gate()
    windows = [json.loads(Path(p).read_text()) for p in paths]
    for row in windows:
        require(row.get('schema') == 'own-runtime.packet54.window.v1' and row.get('passed') is True
                and row.get('mode') == 'timing' and row.get('device_executed') is True
                and row.get('child_still_running') is False, 'incomplete timing owner')
        require(type(row.get('pid')) is int and row['pid'] > 0 and row.get('process_start_ticks'), 'owner identity missing')
        require(row['seal_sha256'] == sha(HERE/'seal.json'), 'timing seal differs')
        require(row.get('binary_sha256') == sha(HERE/'build/device/compute-bench') and row.get('card') == 0, 'timing binary/card differs')
    for key in ('seal_sha256','binary_sha256','card','boot_id','environment','exactness_companions','coordinator_fault_review'):
        require(key in windows[0] and windows[0][key] == windows[1].get(key), 'timing identity differs: '+key)
    require(len({(r['pid'],r['process_start_ticks']) for r in windows}) == 2, 'timing owners not fresh')
    summaries = []
    for path, row in zip(paths, windows):
        require(set(row['native_files']) == {'run/'+n for n in ('receipt.json','comparisons.jsonl','iterations.jsonl','exceptions.jsonl','manifest.json')}, 'native timing closure incomplete')
        verify_files(row['native_files'], Path(path).resolve().parent)
        companions = row['exactness_companions']
        require(len(companions) == 2, 'missing exactness companions')
        for c in companions:
            require(sha(c['path']) == c['sha256'], 'exactness companion changed')
        prerequisite([Path(c['path']) for c in companions], row)
        summaries.append(timing(Path(path).parent/'run'))
    return dict(schema='own-runtime.packet54.two-owner-timing.v1', passed=True, device_executed=True,
                model_speed_claim=False, windows=[str(Path(p).resolve()) for p in paths],
                fresh_owners=summaries, **choose(summaries))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--windows', nargs=2, type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'summary output must be new')
    args.output.write_text(json.dumps(fresh_pair(args.windows), indent=2)+'\n')

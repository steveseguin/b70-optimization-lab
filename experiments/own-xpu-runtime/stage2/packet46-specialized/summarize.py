#!/usr/bin/env python3
"""Validate layer-window evidence and compute the preregistered GPU-only bar."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

LAYERS = {4: 'ordinary_gdn', 3: 'qsa'}
BASELINE_LAUNCHES = {4: 35, 3: 41}
HERE = Path(__file__).resolve().parent


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read_rows(path):
    with Path(path).open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def capture_manifest(rows):
    return [{key: value for key, value in row.items() if key not in ('sha256', 'equal')}
            for row in rows]


def exact(run, *, cpu=False, manifest_path=None):
    run = Path(run)
    receipt = json.loads((run / 'receipt.json').read_text())
    require(receipt.get('passed') is True and receipt.get('mode') == 'exact', 'exact native gate failed')
    require(receipt.get('cpu_mock') is cpu, 'wrong exactness backend')
    require(receipt.get('safe_to_exit') is True, 'native teardown not safe')
    rows = read_rows(run / 'comparisons.jsonl')
    require(rows and receipt.get('checks') == len(rows), 'missing exact comparisons')
    expected = {(layer, iteration) for layer in LAYERS for iteration in range(6)}
    complete, intermediate = set(), set()
    for row in rows:
        key = row['layer'], row['iteration']
        require(key in expected and row.get('equal') is True, 'invalid/failed exact case')
        require(isinstance(row.get('bytes'), int) and row['bytes'] > 0, 'empty exact byte range')
        require(isinstance(row.get('sha256'), str) and len(row['sha256']) == 64
                and set(row['sha256']) <= set('0123456789abcdef'),
                'missing exact output identity')
        require(row.get('scope') in ('producer', 'logical-state', 'all-mutable-allocation'),
                'unknown comparison scope')
        (complete if row['scope'] == 'all-mutable-allocation' else intermediate).add(key)
    require(complete == expected and intermediate == expected, 'missing complete-state/intermediate cases')
    if not cpu or manifest_path is not None:
        manifest_path = HERE / 'exact-capture-manifest.json' if manifest_path is None else Path(manifest_path)
        manifest = json.loads(manifest_path.read_text())
        captures = manifest['captures'] if isinstance(manifest, dict) else manifest
        require(capture_manifest(rows) == captures,
                'complete capture manifest differs; missing/extra/reordered byte range')
    require(all(receipt.get('route_set_counts', {}).get(str(layer), 0) >= 2 for layer in LAYERS),
            'changed expert sets not demonstrated')
    digest = hashlib.sha256((run / 'comparisons.jsonl').read_bytes()).hexdigest()
    return dict(passed=True, exact_output_identity=digest, comparisons=len(rows), cases=len(expected))


def timing(run):
    run = Path(run)
    receipt = json.loads((run / 'receipt.json').read_text())
    require(receipt.get('passed') is True and receipt.get('mode') == 'timing'
            and receipt.get('cpu_mock') is False and receipt.get('safe_to_exit') is True,
            'native timing or teardown failed')
    require(receipt.get('timing_pair_checks') == 420,
            'all timing-only input pairs must pass raw complete-state/error checks')
    rows = read_rows(run / 'iterations.jsonl')
    expected = {(layer, iteration, arm) for layer in LAYERS for iteration in range(210)
                for arm in ('current', 'specialized')}
    observed = {}
    for row in rows:
        key = row['layer'], row['iteration'], row['mode']
        require(key in expected and key not in observed, 'missing/duplicate/foreign timing case')
        require(row.get('warmup') is (row['iteration'] < 10), 'warmup identity changed')
        require(row.get('position') == 4095 and row.get('occupied_context') == 4096,
                'timing must use occupied 4K prefix')
        require(isinstance(row.get('gpu_ns'), int) and row['gpu_ns'] > 0, 'invalid GPU duration')
        events = row.get('events', [])
        require(events and len(events) == row['submissions'], 'compute-event coverage incomplete')
        class_totals = {}
        event_ids = set()
        for event in events:
            start, end = event.get('start_ns'), event.get('end_ns')
            require(type(start) is int and type(end) is int and 0 < start < end
                    and end - start <= 4_000_000_000, 'invalid GPU event endpoints')
            require(type(event.get('id')) is int and event['id'] > 0,
                    'invalid compute event identity')
            require(event.get('id') not in event_ids, 'duplicate compute event')
            event_ids.add(event['id'])
            cls = event['class']
            require(isinstance(cls, str) and bool(cls), 'empty compute class')
            class_totals[cls] = class_totals.get(cls, 0) + end - start
        require(class_totals == row.get('classes_ns') and sum(class_totals.values()) == row['gpu_ns'],
                'class/event accounting differs')
        count = BASELINE_LAUNCHES[row['layer']]
        require(row['submissions'] == count if row['mode'] == 'current' else 0 < row['submissions'] < count,
                'baseline census or fewer-launch mechanism failed')
        observed[key] = row
    require(set(observed) == expected, 'timing campaign incomplete')
    result = {}
    for layer, name in LAYERS.items():
        current = [observed[layer, i, 'current']['gpu_ns'] / 1000 for i in range(10, 210)]
        specialized = [observed[layer, i, 'specialized']['gpu_ns'] / 1000 for i in range(10, 210)]
        savings = [a - b for a, b in zip(current, specialized)]
        def stats(values):
            ordered = sorted(values)
            # Exact order statistics: no synthetic/interpolated timing points.
            return dict(median=statistics.median(values), p10=ordered[19], p90=ordered[179])
        class_medians = {}
        for arm in ('current', 'specialized'):
            classes = set().union(*(observed[layer, i, arm]['classes_ns'] for i in range(10, 210)))
            class_medians[arm] = {cls: statistics.median(
                observed[layer, i, arm]['classes_ns'].get(cls, 0) / 1000 for i in range(10, 210))
                for cls in sorted(classes)}
        result[name] = dict(current_gpu_us=stats(current), specialized_gpu_us=stats(specialized),
                            paired_saved_gpu_us=stats(savings), class_median_gpu_us=class_medians,
                            integration_bar_us=80, bar_passed=statistics.median(savings) >= 80,
                            measured_pairs=200)
    return dict(passed=True, device_executed=True, microbenchmark_only=True,
                model_speed_claim=False, layers=result,
                timing_definition='sum of unique completed compute-event end-start per full layer')


def fresh_pair(paths):
    require(len(paths) == 2 and len({str(Path(p).resolve()) for p in paths}) == 2,
            'two different timing windows required')
    windows = [json.loads(Path(p).read_text()) for p in paths]
    for row in windows:
        require(row.get('passed') is True and row.get('mode') == 'timing'
                and row.get('device_executed') is True and row.get('child_still_running') is False,
                'incomplete timing window')
    for key in ('seal_sha256', 'binary_sha256', 'card', 'boot_id', 'environment', 'exactness_companions'):
        require(windows[0].get(key) is not None and windows[0][key] == windows[1].get(key),
                'fresh timing identity differs: ' + key)
    require(windows[0].get('coordinator_fault_review') == windows[1].get('coordinator_fault_review'),
            'fresh timing fault-review identity differs')
    require(len({(r['pid'], r['process_start_ticks']) for r in windows}) == 2,
            'timing owners not fresh')
    # Check the window-bound bytes again; a historical passed boolean is insufficient.
    from window_support import prerequisite, verify_files, sha
    for path, row in zip(paths, windows):
        verify_files(row['native_files'], Path(path).resolve().parent)
        companions = row['exactness_companions']
        require(isinstance(companions, list) and len(companions) == 2, 'exactness companions missing')
        for companion in companions:
            require(sha(Path(companion['path'])) == companion['sha256'], 'exactness companion changed')
        prerequisite([Path(c['path']) for c in companions], row)
    summaries = [timing(Path(p).parent / 'run') for p in paths]
    return dict(schema='own-runtime.packet46.two-owner-timing.v1', passed=True,
                device_executed=True, model_speed_claim=False,
                windows=[str(Path(p).resolve()) for p in paths],
                integration_candidates={name: all(row['layers'][name]['bar_passed'] for row in summaries)
                                        for name in LAYERS.values()}, fresh_owners=summaries)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--windows', nargs=2, type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'summary output must be new')
    args.output.write_text(json.dumps(fresh_pair(args.windows), indent=2) + '\n')

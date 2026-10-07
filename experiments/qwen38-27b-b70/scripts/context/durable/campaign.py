#!/usr/bin/env python3
"""Freeze or execute a balanced pilot. Never starts/restarts a model server."""
import argparse
from collections import Counter
import fcntl
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

from pilot import (ARMS, run, StubClient, HTTPClient, atomic, append,
                   busy_endpoint, endpoint_lock_path)
from tasks import verify, make_task
from extraction import DEVELOPMENT_INDICES


def source_hashes():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path(__file__).parent.glob('*.py') if not p.name.startswith('test_')}


def plan(suite_path):
    suite_path = Path(suite_path)
    suite = json.loads(suite_path.read_text())
    arms = suite['arms']
    if len(arms) != len(ARMS) or set(arms) != set(ARMS):
        raise ValueError('pilot suite must contain each of summary, archive and quoted exactly once')
    if not suite['cases']:
        raise ValueError('pilot suite has no cases')
    cases, seen_tasks, seen_stems = [], set(), set()
    for i, row in enumerate(suite['cases']):
        path = suite_path.parent / row['path']
        if not path.resolve().is_relative_to(suite_path.parent.resolve()):
            raise ValueError('task must be inside the suite directory')
        if row['task_sha256'] in seen_tasks or path.stem in seen_stems:
            raise ValueError('duplicate task identity or output name in suite')
        seen_tasks.add(row['task_sha256']); seen_stems.add(path.stem)
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['file_sha256']:
            raise ValueError(f'task file changed: {path}')
        task = json.loads(path.read_text()); verify(task)
        if task['task_sha256'] != row['task_sha256']:
            raise ValueError('suite task identity mismatch')
        order = arms[i % len(arms):] + arms[:i % len(arms)]
        cases.extend({'task': row['path'], 'task_sha256': row['task_sha256'],
                      'file_sha256': row['file_sha256'], 'arm': arm} for arm in order)
    return {'schema': 'durable-pilot-plan.v1',
            'suite_sha256': hashlib.sha256(suite_path.read_bytes()).hexdigest(),
            'source_sha256': source_hashes(), 'runs': cases, 'context_limit_utf8_bytes': 32768,
            'calibration_gate': '100% exact events and source order on fixed development batches 1,2,3,4,8,12,16,20,24,28,32,36,40,44,47,48 of seed-7 48-batch 320-filler report and dispatch tasks at a 32768-byte budget.',
            'quality_gate': 'Every final answer correct in every planned model trial; no missing, duplicate, invalid, unfinished or failed attempts.',
            'speed_gate': 'Complete model trials and a fresh campaign attempt only. At least 10% lower median paired elapsed ratio versus archive; pilot evidence only.',
            'promotion': 'No general memory, unlimited-context, or model-quality guarantee from this synthetic pilot.'}


def verify_frozen(frozen, suite_path, item):
    """Check bytes as well as self-reported hashes immediately around each trial."""
    if source_hashes() != frozen['source_sha256']:
        raise ValueError('source files changed after campaign was frozen')
    if hashlib.sha256(suite_path.read_bytes()).hexdigest() != frozen['suite_sha256']:
        raise ValueError('suite manifest changed after campaign was frozen')
    data = (suite_path.parent / item['task']).read_bytes()
    if hashlib.sha256(data).hexdigest() != item['file_sha256']:
        raise ValueError('task bytes changed after campaign was frozen')
    task = json.loads(data); verify(task)
    if task['task_sha256'] != item['task_sha256']:
        raise ValueError('task identity differs from frozen trial')
    return task


def verify_result(result, frozen, item, kind, identity):
    required = {'status': 'completed', 'task_sha256': item['task_sha256'], 'arm': item['arm'],
                'measurement_kind': kind, 'source_sha256': frozen['source_sha256'],
                'server_identity': identity, 'context_limit_utf8_bytes': frozen['context_limit_utf8_bytes']}
    for key, value in required.items():
        if result.get(key) != value:
            raise ValueError(f'trial result disagrees with frozen execution identity: {key}')


def validate_calibration(paths, frozen, identity):
    """No holdout requests until both preregistered development styles pass."""
    if not paths or len(paths) != 2:
        raise ValueError('live campaign requires --calibration with two seed-7 extraction result files')
    styles, records = set(), []
    for path in paths:
        path = Path(path)
        data = path.read_bytes(); result = json.loads(data)
        style = result.get('style')
        rows = result.get('rows')
        if (result.get('measurement_kind') != 'model' or result.get('status') != 'completed'
                or result.get('gate_passed') is not True or result.get('seed') != 7
                or style not in {'report', 'dispatch'} or style in styles
                or not isinstance(rows, list) or not rows
                or not all(row.get('valid_format') is True and row.get('exact_order') is True for row in rows)):
            raise ValueError('calibration must pass on seed 7, once each for report and dispatch, with correct event order')
        expected_task = make_task(seed=7, batches=48, filler_words=320, style=style)
        if (result.get('indices') != DEVELOPMENT_INDICES
                or [row.get('batch_id') for row in rows] != DEVELOPMENT_INDICES
                or result.get('context_limit_utf8_bytes') != 32768
                or result.get('task_sha256') != expected_task['task_sha256']):
            raise ValueError('calibration requires the fixed 16 development batches, 32768-byte budget, and seed-7/48-batch/320-filler task identity')
        for metric in ('event_precision', 'event_recall'):
            value = result.get(metric)
            if type(value) not in (int, float) or not math.isfinite(value) or value != 1:
                raise ValueError('calibration precision and recall must each be 100% exact')
        if (result.get('source_sha256') != frozen['source_sha256']
                or result.get('server_identity') != identity
                or result.get('endpoint') != identity['endpoint']
                or result.get('model') != identity['model']):
            raise ValueError('calibration source/model/server identity differs from this campaign')
        styles.add(style)
        records.append({'path': str(path.resolve()), 'sha256': hashlib.sha256(data).hexdigest()})
    return records


def summarize(results, expected_runs=None, *, campaign_clean=True):
    """A partial/duplicate/mismatched matrix can never produce a passing gate."""
    if expected_runs is None:
        expected_runs = [{'task_sha256': task, 'arm': arm}
                         for task in {r.get('task_sha256') for r in results} for arm in ARMS]
    expected = Counter((r['task_sha256'], r['arm']) for r in expected_runs)
    actual = Counter((r.get('task_sha256'), r.get('arm')) for r in results)
    complete = bool(expected) and all(n == 1 for n in expected.values()) and actual == expected
    arms, paired = {}, {}
    valid_results = True
    for result in results:
        score = result.get('score') or {}
        asked, correct = score.get('asked'), score.get('correct')
        valid = (result.get('status') == 'completed' and score.get('valid') is True
                 and type(asked) is int and type(correct) is int and asked > 0 and 0 <= correct <= asked)
        seconds = result.get('wall_seconds_this_session')
        timing = (result.get('measurement_kind') == 'model' and result.get('timing_complete') is True
                  and not result.get('resumed', False) and type(seconds) in (int, float)
                  and math.isfinite(seconds) and seconds > 0)
        arm = arms.setdefault(result.get('arm'), {'completed': 0, 'asked': 0, 'correct': 0,
                                                 'all_valid': True, 'model_timing': True})
        arm['completed'] += result.get('status') == 'completed'
        arm['asked'] += asked if type(asked) is int else 0
        arm['correct'] += correct if type(correct) is int else 0
        arm['all_valid'] &= valid
        arm['model_timing'] &= timing
        valid_results &= valid and result.get('measurement_kind') == 'model'
        paired.setdefault(result.get('task_sha256'), {})[result.get('arm')] = result
    quality = (complete and campaign_clean and valid_results
               and all(a['correct'] == a['asked'] for a in arms.values()))
    timing_eligible = quality and all(a['model_timing'] for a in arms.values())
    ratios = []
    if timing_eligible:
        for case in paired.values():
            if 'archive' not in case or 'quoted' not in case:
                timing_eligible = False
                break
            ratios.append(case['quoted']['wall_seconds_this_session'] / case['archive']['wall_seconds_this_session'])
    median = statistics.median(ratios) if ratios and timing_eligible else None
    return {'arms': arms, 'complete_planned_matrix': complete, 'campaign_clean': campaign_clean,
            'expected_trials': sum(expected.values()), 'observed_trials': len(results),
            'quality_gate_passed': quality, 'median_quoted_over_archive_elapsed_ratio': median,
            'speed_gate_passed': bool(median is not None and median <= .9),
            'scope': 'Synthetic pilot only; stub, partial, resumed or failed campaigns never qualify.'}


def execute(frozen, suite_path, out, *, stub=False, endpoint=None,
            model='qwen38-27b-fp8', server_identity=None, calibration=None):
    """Run under the shared host lock; append failure history and never skip a failure."""
    suite_path, out = Path(suite_path), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    identity = None if stub else {'endpoint': endpoint, 'model': model,
        'launch_sha256': hashlib.sha256(Path(server_identity).read_bytes()).hexdigest()}
    calibration_records = [] if stub else validate_calibration(calibration, frozen, identity)
    execution = {'measurement_kind': 'stub' if stub else 'model', 'server_identity': identity,
                 'calibration': calibration_records,
                 'plan_sha256': hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest()}
    identity_path = out / 'execution-identity.json'
    history_path = out / 'campaign-attempts.jsonl'
    with endpoint_lock_path(None if stub else endpoint).open('a') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if identity_path.exists() and json.loads(identity_path.read_text()) != execution:
            raise ValueError('campaign execution identity changed; use a new output directory')
        atomic(identity_path, execution)
        # Reopening a completed campaign only returns its already-qualified result.
        if (out / 'summary.json').exists():
            for item in frozen['runs']:
                verify_frozen(frozen, suite_path, item)
            return json.loads((out / 'summary.json').read_text())
        clean = not history_path.exists()
        attempt = time.time_ns()
        append(history_path, {'attempt': attempt, 'status': 'started', 'time': time.time()})
        results, trial = [], None
        try:
            if not stub and busy_endpoint(endpoint):
                raise RuntimeError('protected campaign active; no requests sent')
            for item in frozen['runs']:
                trial = str(out / (Path(item['task']).stem + '-' + item['arm']))
                task = verify_frozen(frozen, suite_path, item)
                if not stub and hashlib.sha256(Path(server_identity).read_bytes()).hexdigest() != identity['launch_sha256']:
                    raise ValueError('server identity file changed during campaign')
                for record in calibration_records:
                    if hashlib.sha256(Path(record['path']).read_bytes()).hexdigest() != record['sha256']:
                        raise ValueError('calibration evidence changed during campaign')
                client = StubClient(task) if stub else HTTPClient(endpoint, model)
                result = run(task, item['arm'], trial, client,
                             frozen['context_limit_utf8_bytes'], identity=identity)
                verify_frozen(frozen, suite_path, item)
                if not stub and hashlib.sha256(Path(server_identity).read_bytes()).hexdigest() != identity['launch_sha256']:
                    raise ValueError('server identity file changed during trial')
                verify_result(result, frozen, item, execution['measurement_kind'], identity)
                results.append(result)
            summary = summarize(results, frozen['runs'], campaign_clean=clean)
            summary['status'] = 'completed'
            atomic(out / 'summary.json', summary)
            status = {'attempt': attempt, 'status': 'completed', 'completed': len(results), 'time': time.time()}
            append(history_path, status); atomic(out / 'campaign-status.json', status)
            return summary
        except BaseException as error:
            status = {'attempt': attempt, 'status': 'failed', 'trial': trial,
                      'error': f'{type(error).__name__}: {error}', 'completed': len(results), 'time': time.time()}
            append(history_path, status); atomic(out / 'campaign-status.json', status)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True); parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--stub', action='store_true'); parser.add_argument('--execute', action='store_true')
    parser.add_argument('--endpoint'); parser.add_argument('--model', default='qwen38-27b-fp8')
    parser.add_argument('--server-identity', type=Path)
    parser.add_argument('--calibration', type=Path, nargs=2,
                        help='passing seed-7 report and dispatch extraction result.json files (required live)')
    args = parser.parse_args()
    if args.execute and not args.stub and (not args.endpoint or not args.server_identity):
        parser.error('live execution requires endpoint and server identity')
    if args.execute and not args.stub and not args.calibration:
        parser.error('live execution requires --calibration REPORT_RESULT DISPATCH_RESULT')
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / 'campaign.lock').open('a') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        frozen = plan(args.suite)
        dest = args.out / 'plan.json'
        if dest.exists() and json.loads(dest.read_text()) != frozen:
            raise ValueError('frozen source/task identity changed; choose a new campaign directory')
        atomic(dest, frozen)
        if not args.stub and not args.execute:
            print(f'Frozen {len(frozen["runs"])} trials; no requests sent. Use --execute only on an idle qualified endpoint.')
            return
        print(json.dumps(execute(frozen, args.suite, args.out, stub=args.stub,
                                 endpoint=args.endpoint, model=args.model,
                                 server_identity=args.server_identity, calibration=args.calibration), indent=2))


if __name__ == '__main__':
    main()

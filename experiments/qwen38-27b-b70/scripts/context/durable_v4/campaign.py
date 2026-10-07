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
                   busy_endpoint, endpoint_lock_path, grade)
from tasks import verify, make_task
from extraction import DEVELOPMENT_INDICES

PROTOCOL = 'durable-context-r4'
STAGE_SEEDS = {'development': (17, 29), 'holdout': (401, 502, 603)}


def generation_identity():
    # Independent protocol constants: do not accept an altered client's defaults.
    return {'answer_generation': {'enable_thinking': True, 'reasoning_effort': 'medium', 'max_tokens': 8192},
            'ingestion_generation': {'enable_thinking': False, 'max_tokens': 4096}}


def verify_generation(record):
    for field, expected in generation_identity().items():
        actual = record.get(field)
        if (not isinstance(actual, dict) or set(actual) != set(expected)
                or any(type(actual[key]) is not type(value) or actual[key] != value
                       for key, value in expected.items())):
            raise ValueError(f'{field} differs from the fixed r4 generation protocol')


def stage_tasks(stage):
    if stage not in STAGE_SEEDS:
        raise ValueError('stage must be development or holdout')
    return {task['task_sha256']: task for seed in STAGE_SEEDS[stage]
            for style in ('report', 'dispatch')
            for task in [make_task(seed=seed, batches=48, filler_words=320, style=style)]}


def source_hashes():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path(__file__).parent.glob('*.py') if not p.name.startswith('test_')}


def plan(suite_path, stage='development'):
    suite_path = Path(suite_path)
    suite = json.loads(suite_path.read_text())
    arms = suite['arms']
    if len(arms) != len(ARMS) or set(arms) != set(ARMS):
        raise ValueError('pilot suite must contain each of summary, archive and quoted exactly once')
    if not suite['cases']:
        raise ValueError('pilot suite has no cases')
    fixed = stage_tasks(stage)
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
        if task['task_sha256'] not in fixed:
            raise ValueError(f'{stage} accepts only its fixed 48-batch/320-filler task identities')
        order = arms[i % len(arms):] + arms[:i % len(arms)]
        cases.extend({'task': row['path'], 'task_sha256': row['task_sha256'],
                      'file_sha256': row['file_sha256'], 'arm': arm} for arm in order)
    if seen_tasks != set(fixed):
        raise ValueError(f'{stage} requires every fixed seed/style exactly once')
    return {'schema': 'durable-pilot-plan.v4', 'protocol': PROTOCOL, 'stage': stage,
            **generation_identity(),
            'suite_sha256': hashlib.sha256(suite_path.read_bytes()).hexdigest(),
            'source_sha256': source_hashes(), 'runs': cases, 'context_limit_utf8_bytes': 32768,
            'max_retrieval': 24, 'max_answer_calls': 32,
            'calibration_gate': '100% exact events and source order on fixed development batches 1,2,3,4,8,12,16,20,24,28,32,36,40,44,47,48 of seed-7 48-batch 320-filler report and dispatch tasks at a 32768-byte budget.',
            'primary_arms': ['archive', 'quoted'], 'secondary_arms': ['summary'],
            'quality_gate': 'Primary archive/quoted answers all correct; all three arms complete, valid, clean and unresumed. Summary accuracy is secondary.',
            'speed_gate': 'Known zero cached prompt tokens on every call in every arm; also required for development admission. Single-server paired ratios are descriptive only; no speed gate passes without two fresh qualified servers.',
            'promotion': 'No general memory, unlimited-context, or model-quality guarantee from this synthetic pilot.'}


def verify_frozen(frozen, suite_path, item):
    """Check bytes as well as self-reported hashes immediately around each trial."""
    verify_generation(frozen)
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


def verify_cache_log(result, path):
    """Recompute cache evidence from immutable raw call rows, without fallback totals."""
    data = Path(path).read_bytes()
    calls = [json.loads(line) for line in data.splitlines()]
    complete, total = bool(calls), 0
    for call in calls:
        usage = call.get('usage') if isinstance(call, dict) else None
        details = usage.get('prompt_tokens_details') if isinstance(usage, dict) else None
        count = details.get('cached_tokens') if isinstance(details, dict) else None
        prompt = usage.get('prompt_tokens') if isinstance(usage, dict) else None
        valid = (isinstance(call, dict) and 'error' not in call and type(count) is int and count >= 0
                 and type(prompt) is int and count <= prompt)
        complete &= valid
        if valid:
            total += count
    expected = {'complete': complete, 'cached_tokens': total if complete else None, 'calls': len(calls)}
    actual = result.get('cache_usage')
    if (not isinstance(actual, dict) or set(actual) != set(expected)
            or any(type(actual[key]) is not type(value) or actual[key] != value for key, value in expected.items())
            or type(result.get('calls')) is not int or result['calls'] != len(calls)):
        raise ValueError('native cache aggregate disagrees with raw calls.jsonl')
    return {'path': str(Path(path).resolve()), 'sha256': hashlib.sha256(data).hexdigest()}


def verify_result(result, frozen, item, kind, identity, calls_path=None):
    verify_generation(result)
    verify_generation(frozen)
    required = {'schema': 'durable-pilot-run.v4', 'protocol': PROTOCOL,
                'status': 'completed', 'task_sha256': item['task_sha256'], 'arm': item['arm'],
                'measurement_kind': kind, 'source_sha256': frozen['source_sha256'],
                'server_identity': identity, 'context_limit_utf8_bytes': frozen['context_limit_utf8_bytes'],
                'max_retrieval': 24, 'max_answer_calls': 32,
                'answer_protocol_completed': True, 'processed_batches': 48}
    for key, value in required.items():
        if result.get(key) != value:
            raise ValueError(f'trial result disagrees with frozen execution identity: {key}')
    for key in ('processed_batches', 'max_retrieval', 'max_answer_calls', 'context_limit_utf8_bytes'):
        if type(result[key]) is not int:
            raise ValueError(f'native result {key} must be an integer')
    if result['answer_protocol_completed'] is not True:
        raise ValueError('native answer protocol must explicitly complete')
    usage = result.get('answer_protocol')
    if (not isinstance(usage, dict) or type(usage.get('calls')) is not int
            or not 1 <= usage['calls'] <= 32 or type(usage.get('retrievals')) is not int
            or not 0 <= usage['retrievals'] <= 24):
        raise ValueError('native answer protocol usage exceeds the fixed budgets')
    task = stage_tasks(frozen['stage'])[item['task_sha256']]
    answers = result.get('answers')
    if not isinstance(answers, dict) or set(answers) != set(task['oracle']['answers']):
        raise ValueError('native result must cover exactly all 24 question IDs')
    if result.get('score') != grade(task, answers):
        raise ValueError('native result score disagrees with independent answer grading')
    if kind == 'model':
        if calls_path is None:
            raise ValueError('live result verification requires native calls.jsonl')
        failures = Path(calls_path).parent / 'failures.jsonl'
        if failures.exists() and failures.stat().st_size:
            raise ValueError('completed native trial has recorded failures')
        record = verify_cache_log(result, calls_path)
        if any(not isinstance(call, dict) or 'error' in call
               for call in map(json.loads, Path(calls_path).read_bytes().splitlines())):
            raise ValueError('completed native trial contains a failed call')
        return record


def validate_calibration(paths, frozen, identity):
    """No holdout requests until both preregistered development styles pass."""
    verify_generation(frozen)
    if not paths or len(paths) != 2:
        raise ValueError('live campaign requires --calibration with two seed-7 extraction result files')
    styles, records = set(), []
    for path in paths:
        path = Path(path)
        data = path.read_bytes(); result = json.loads(data)
        verify_generation(result)
        style = result.get('style')
        rows = result.get('rows')
        if (result.get('schema') != 'durable-extraction-diagnostic.v4' or result.get('protocol') != PROTOCOL
                or result.get('measurement_kind') != 'model' or result.get('status') != 'completed'
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
    """Primary-pair quality; all arms still must complete cleanly and remain visible."""
    if expected_runs is None:
        expected_runs = [{'task_sha256': task, 'arm': arm}
                         for task in {r.get('task_sha256') for r in results} for arm in ARMS]
    expected = Counter((r['task_sha256'], r['arm']) for r in expected_runs)
    actual = Counter((r.get('task_sha256'), r.get('arm')) for r in results)
    full_arms = all({arm for task_id, arm in expected if task_id == task} == set(ARMS)
                    for task in {key[0] for key in expected})
    complete = bool(expected) and full_arms and all(n == 1 for n in expected.values()) and actual == expected
    arms, paired = {}, {}
    valid_results = True
    for result in results:
        score = result.get('score') or {}
        asked, correct = score.get('asked'), score.get('correct')
        valid = (result.get('status') == 'completed' and score.get('valid') is True
                 and type(asked) is int and type(correct) is int and asked == 24 and 0 <= correct <= asked
                 and result.get('resumed') is False and result.get('timing_complete') is True
                 and result.get('answer_protocol_completed') is True and result.get('processed_batches') == 48)
        seconds = result.get('wall_seconds_this_session')
        timing = (result.get('measurement_kind') == 'model' and valid
                  and type(seconds) in (int, float) and math.isfinite(seconds) and seconds > 0)
        cache = result.get('cache_usage') or {}
        cold = (cache.get('complete') is True and type(cache.get('cached_tokens')) is int
                and cache['cached_tokens'] == 0 and type(cache.get('calls')) is int and cache['calls'] > 0)
        arm = arms.setdefault(result.get('arm'), {'completed': 0, 'asked': 0, 'correct': 0,
                                                 'all_valid': True, 'model_timing': True, 'cache_zero_known': True})
        arm['completed'] += result.get('status') == 'completed'
        arm['asked'] += asked if type(asked) is int else 0
        arm['correct'] += correct if type(correct) is int else 0
        arm['all_valid'] &= valid
        arm['model_timing'] &= timing
        arm['cache_zero_known'] &= cold
        valid_results &= valid and result.get('measurement_kind') == 'model'
        paired.setdefault(result.get('task_sha256'), {})[result.get('arm')] = result
    eligible = complete and campaign_clean and valid_results
    primary_quality = eligible and all(arms[a]['correct'] == arms[a]['asked'] for a in ('archive', 'quoted'))
    all_quality = eligible and all(a['correct'] == a['asked'] for a in arms.values())
    timing_eligible = primary_quality and all(arm['model_timing'] and arm['cache_zero_known']
                                              for arm in arms.values())
    ratios = ([case['quoted']['wall_seconds_this_session'] / case['archive']['wall_seconds_this_session']
               for case in paired.values()] if timing_eligible else [])
    median = statistics.median(ratios) if ratios else None
    return {'arms': arms, 'complete_planned_matrix': complete, 'campaign_clean': campaign_clean,
            'primary_arms': ['archive', 'quoted'], 'secondary_arms': ['summary'],
            'expected_trials': sum(expected.values()), 'observed_trials': len(results),
            'primary_quality_gate_passed': primary_quality, 'all_arms_quality_gate_passed': all_quality,
            'quality_gate_passed': primary_quality, 'quality_gate_definition': 'Alias of primary_quality_gate_passed; summary accuracy is secondary.',
            'timing_eligible': timing_eligible, 'median_quoted_over_archive_elapsed_ratio': median,
            'single_server_speed_signal': bool(median is not None and median <= .9),
            'speed_gate_passed': False,
            'scope': 'Synthetic primary-pair pilot. Single-server timing is descriptive; confirmation requires two fresh qualified servers.'}


def stage_summary(results, frozen, clean, status):
    result = summarize(results, frozen['runs'], campaign_clean=clean)
    result.update(schema='durable-pilot-summary.v4', protocol=PROTOCOL, stage=frozen['stage'], status=status,
                  source_sha256=frozen['source_sha256'], **generation_identity())
    result['development_gate_passed'] = bool(frozen['stage'] == 'development'
        and status == 'completed' and result['quality_gate_passed']
        and len(results) == 12 and all(r.get('resumed') is False
            and r.get('timing_complete') is True and r.get('answer_protocol_completed') is True
            and r.get('processed_batches') == 48 for r in results)
        and all(arm['model_timing'] and arm['cache_zero_known'] for arm in result['arms'].values()))
    return result


def validate_development(directory, frozen, identity):
    """Independently inspect twelve native trials; a passed summary is not evidence alone."""
    if directory is None:
        raise ValueError('live holdout requires --development-results DIRECTORY')
    directory = Path(directory).resolve()
    records = []
    def read(path):
        data = path.read_bytes()
        records.append({'path': str(path.resolve()), 'sha256': hashlib.sha256(data).hexdigest()})
        return json.loads(data)
    dev = read(directory / 'plan.json')
    verify_generation(frozen)
    verify_generation(dev)
    if (dev.get('schema') != 'durable-pilot-plan.v4' or dev.get('protocol') != PROTOCOL
            or dev.get('stage') != 'development' or dev.get('source_sha256') != frozen['source_sha256']
            or dev.get('context_limit_utf8_bytes') != 32768 or dev.get('max_retrieval') != 24
            or dev.get('max_answer_calls') != 32 or dev.get('primary_arms') != ['archive', 'quoted']
            or dev.get('secondary_arms') != ['summary']):
        raise ValueError('development plan protocol/source/budget identity differs')
    tasks = stage_tasks('development')
    expected = Counter((task, arm) for task in tasks for arm in ARMS)
    if Counter((r['task_sha256'], r['arm']) for r in dev.get('runs', [])) != expected:
        raise ValueError('development plan must contain all twelve fixed trials exactly once')
    execution = read(directory / 'execution-identity.json')
    verify_generation(execution)
    if (execution.get('schema') != 'durable-pilot-execution.v4'
            or execution.get('protocol') != PROTOCOL or execution.get('stage') != 'development'
            or execution.get('measurement_kind') != 'model' or execution.get('server_identity') != identity
            or execution.get('plan_sha256') != hashlib.sha256(json.dumps(dev, sort_keys=True).encode()).hexdigest()):
        raise ValueError('development execution runtime/plan identity differs')
    history_path = directory / 'campaign-attempts.jsonl'
    data = history_path.read_bytes()
    records.append({'path': str(history_path), 'sha256': hashlib.sha256(data).hexdigest()})
    history = [json.loads(line) for line in data.splitlines()]
    if (len(history) != 2 or [r.get('status') for r in history] != ['started', 'completed']
            or history[0].get('attempt') != history[1].get('attempt') or history[1].get('completed') != 12):
        raise ValueError('development must be a clean, single completed attempt')
    results, paths = [], set()
    for item in dev['runs']:
        trial = directory / (Path(item['task']).stem + '-' + item['arm'])
        if trial in paths or not trial.resolve().is_relative_to(directory):
            raise ValueError('duplicate or escaping development trial path')
        paths.add(trial)
        native = read(trial / 'result.json')
        records.append(verify_result(native, dev, item, 'model', identity, trial / 'calls.jsonl'))
        if native.get('resumed') is not False or native.get('timing_complete') is not True:
            raise ValueError('development trial is resumed or has incomplete timing')
        if (trial / 'failures.jsonl').exists() and (trial / 'failures.jsonl').stat().st_size:
            raise ValueError('development trial has recorded failures')
        results.append(native)
    if set(directory.glob('*/result.json')) != {path / 'result.json' for path in paths}:
        raise ValueError('unexpected or missing native development trial results')
    stored = read(directory / 'summary.json')
    verify_generation(stored)
    recomputed = stage_summary(results, dev, True, 'completed')
    if stored != recomputed or not recomputed['development_gate_passed']:
        raise ValueError('development summary differs from independently verified twelve-trial gate')
    return records


def execute(frozen, suite_path, out, *, stub=False, endpoint=None,
            model='qwen38-27b-fp8', server_identity=None, calibration=None, development_results=None):
    """Run under the shared host lock; append failure history and never skip a failure."""
    suite_path, out = Path(suite_path), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    identity = None if stub else {'endpoint': endpoint, 'model': model,
        'launch_sha256': hashlib.sha256(Path(server_identity).read_bytes()).hexdigest()}
    try:
        verify_generation(frozen)
        calibration_records = [] if stub else validate_calibration(calibration, frozen, identity)
        development_records = (validate_development(development_results, frozen, identity)
            if not stub and frozen['stage'] == 'holdout' else [])
    except BaseException as error:
        atomic(out / 'partial-summary.json', stage_summary([], frozen, False, 'failed'))
        atomic(out / 'campaign-status.json', {'status': 'failed', 'phase': 'prerequisite-gates',
            'stage': frozen['stage'], 'protocol': PROTOCOL, 'completed': 0,
            'error': f'{type(error).__name__}: {error}'})
        raise
    execution = {'schema': 'durable-pilot-execution.v4', 'protocol': PROTOCOL, 'stage': frozen['stage'],
                 **generation_identity(),
                 'measurement_kind': 'stub' if stub else 'model', 'server_identity': identity,
                 'calibration': calibration_records, 'development': development_records,
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
        results, trial, cache_records = [], None, []
        try:
            atomic(out / 'partial-summary.json', stage_summary([], frozen, clean, 'running'))
            if not stub and busy_endpoint(endpoint):
                raise RuntimeError('protected campaign active; no requests sent')
            for item in frozen['runs']:
                trial = str(out / (Path(item['task']).stem + '-' + item['arm']))
                atomic(out / 'campaign-status.json', {'status': 'running', 'stage': frozen['stage'],
                    'protocol': PROTOCOL, 'trial': trial, 'completed': len(results),
                    'expected': len(frozen['runs'])})
                task = verify_frozen(frozen, suite_path, item)
                if not stub and hashlib.sha256(Path(server_identity).read_bytes()).hexdigest() != identity['launch_sha256']:
                    raise ValueError('server identity file changed during campaign')
                for record in calibration_records + development_records:
                    if hashlib.sha256(Path(record['path']).read_bytes()).hexdigest() != record['sha256']:
                        raise ValueError('calibration evidence changed during campaign')
                client = StubClient(task) if stub else HTTPClient(endpoint, model)
                result = run(task, item['arm'], trial, client,
                             frozen['context_limit_utf8_bytes'], identity=identity)
                verify_frozen(frozen, suite_path, item)
                if not stub and hashlib.sha256(Path(server_identity).read_bytes()).hexdigest() != identity['launch_sha256']:
                    raise ValueError('server identity file changed during trial')
                cache_record = verify_result(result, frozen, item, execution['measurement_kind'], identity, Path(trial) / 'calls.jsonl')
                if cache_record is not None:
                    cache_records.append(cache_record)
                    atomic(out / 'cache-evidence.json', cache_records)
                results.append(result)
                progress = stage_summary(results, frozen, clean, 'running')
                atomic(out / 'partial-summary.json', progress)
                atomic(out / 'campaign-status.json', {'status': 'running', 'stage': frozen['stage'],
                    'protocol': PROTOCOL, 'completed': len(results), 'expected': len(frozen['runs'])})
            summary = stage_summary(results, frozen, clean, 'completed')
            atomic(out / 'summary.json', summary)
            status = {'attempt': attempt, 'status': 'completed', 'completed': len(results), 'time': time.time()}
            append(history_path, status); atomic(out / 'campaign-status.json', status)
            return summary
        except BaseException as error:
            partial = stage_summary(results, frozen, False, 'failed')
            atomic(out / 'partial-summary.json', partial)
            status = {'attempt': attempt, 'status': 'failed', 'trial': trial,
                      'stage': frozen['stage'], 'protocol': PROTOCOL,
                      'error': f'{type(error).__name__}: {error}', 'completed': len(results), 'time': time.time()}
            append(history_path, status); atomic(out / 'campaign-status.json', status)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True); parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--stage', choices=STAGE_SEEDS, required=True)
    parser.add_argument('--development-results', type=Path)
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
    if args.execute and not args.stub and args.stage == 'holdout' and not args.development_results:
        parser.error('live holdout requires --development-results DIRECTORY')
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / 'campaign.lock').open('a') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        frozen = plan(args.suite, args.stage)
        dest = args.out / 'plan.json'
        if dest.exists() and json.loads(dest.read_text()) != frozen:
            raise ValueError('frozen source/task identity changed; choose a new campaign directory')
        atomic(dest, frozen)
        if not args.stub and not args.execute:
            print(f'Frozen {len(frozen["runs"])} trials; no requests sent. Use --execute only on an idle qualified endpoint.')
            return
        print(json.dumps(execute(frozen, args.suite, args.out, stub=args.stub,
                                 endpoint=args.endpoint, model=args.model,
                                 server_identity=args.server_identity, calibration=args.calibration,
                                 development_results=args.development_results), indent=2))


if __name__ == '__main__':
    main()

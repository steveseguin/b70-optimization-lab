#!/usr/bin/env python3
"""CPU-only campaign 59 receipts; a completed quality failure is still evidence.

  campaign59_result.py --run c59a --out /path/c59a-result.json
  campaign59_result.py --compare --out /path/c59-comparison.json

No trajectories or snapshots are loaded. --out names a JSON file; the unchanged
quality audit and fixed-fixture receipt are saved beside individual results.
Exit 0 means complete, valid evidence, NOT quality success or promotion.
Exit 2 means missing, invalid, unfinished, or mismatched-fixture evidence.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import shutil
import subprocess
import sys

import campaign_time_budget


BASE = Path('/mnt/fast-ai/bench-results/context-longrun-20261016')
ROOT_MTIME = 1792687500
ARM = 'K32V'
SEED = 2
HERE = Path(__file__).resolve().parent


def require(value, message):
    if not value:
        raise ValueError(message)


def object_at(path):
    value = json.loads(path.read_text())
    require(isinstance(value, dict), f'{path}: expected object')
    return value


def records(path):
    count = 0
    with path.open() as stream:
        for number, line in enumerate(stream, 1):
            value = json.loads(line)
            require(isinstance(value, dict), f'{path}:{number}: expected object')
            count += 1
            yield value
    require(count, f'{path}: empty JSONL')


def unique(pattern):
    values = sorted(BASE.glob(pattern))
    require(len(values) == 1, f'{pattern}: expected one match, found {len(values)}')
    return values[0]


def receipt(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return {'path': str(path.resolve()), 'sha256': digest.hexdigest(),
            'bytes': path.stat().st_size}


def sha_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


def paths(run):
    state = unique(f'proxy-state/{run}-{ARM}-hostile2mk-s2/*/state.json').parent
    job = BASE / f'runs/{run}/hostile2mk/jobs/{ARM}__sparse-memory-t2000k-poison-retro-s2'
    details = unique(str(job.relative_to(BASE)) + '/*/verifier/details.json')
    trial = details.parent.parent
    stage = 'a2' if run == 'c55' else 'a1'
    return {'notes': state / 'notes-history.jsonl', 'archive': state / 'archive.jsonl',
            'events': state / 'events.jsonl', 'proxy_state': state / 'state.json',
            'calls': state / 'calls.jsonl', 'details': details, 'job': job / 'result.json',
            'trial': trial / 'result.json', 'timing': trial / 'agent/timing.json',
            'server': BASE / f'server/tp2-w262144-s2-xp-mtp5-p832-{run}-{stage}/state.json',
            'fixture': trial / 'agent/stable-fixture.json'}


def opening(path):
    rows = list(itertools.islice(records(path), 2))
    require(len(rows) == 2 and rows[1]['role'] == 'tool', f'{path}: missing opening tool output')
    require(isinstance(rows[1]['text'], str), f'{path}: nontext opening output')
    return rows[1]['text']


def validate_fixture_opening(fixture, archive, baseline_archive):
    require(fixture.get('path') == '/' and fixture.get('mtime_ns') == ROOT_MTIME * 1_000_000_000,
            f'fixed fixture root mtime must equal {ROOT_MTIME} seconds')
    actual, expected = opening(archive), opening(baseline_archive)
    require(actual == expected, 'opening tool text differs from c55 (including parent directory mtime)')
    return {'root_mtime': ROOT_MTIME, 'opening_tool_matches_c55': True,
            'opening_tool_text_sha256': sha_text(actual),
            'scope': 'Saved archive text, which excludes tool-call IDs; no timestamp normalization.'}


def inspect(run, out=None):
    p = paths(run)
    for key, path in p.items():
        if key != 'fixture' or run != 'c55':
            require(path.is_file(), f'{run}: missing {key}: {path}')
    detail, job, trial, server = (object_at(p[k]) for k in ('details', 'job', 'trial', 'server'))
    require(detail.get('n') == 423 and detail.get('void') is False,
            f'{run}: expected completed nonvoid 423-key grading')
    require(detail.get('answers_file_ok') is True and len(detail['per_key']) == 423,
            f'{run}: invalid answer file or graded-key count')
    require(detail.get('correct') == sum(v == 'correct' for v in detail['per_key'].values()),
            f'{run}: inconsistent correct count')
    require(job.get('finished_at') and job.get('n_total_trials') == 1 and
            job['stats']['n_completed_trials'] == 1 and job['stats']['n_errored_trials'] == 0,
            f'{run}: job not successfully completed')
    require(all(job['stats'].get(key) == 0 for key in
                ('n_running_trials', 'n_pending_trials', 'n_cancelled_trials')),
            f'{run}: running, pending, or cancelled trials remain')
    require(trial.get('finished_at') and trial.get('exception_info') is None,
            f'{run}: trial unfinished or has exception')
    require(server.get('status') == 'stopped' and server.get('stop_confirmed') is True and
            server.get('error') is None and server.get('finished_at'),
            f'{run}: server lacks clean confirmed stop')
    # Refuse cut/malformed logs even though the historical time-budget reader
    # tolerates a partial trailing line for live diagnostics.
    for key in ('notes', 'archive', 'events', 'calls'):
        for _ in records(p[key]):
            pass
    task = Path(trial['task_id']['path'])
    audit_args = argparse.Namespace(seed=2, task=task, state=p['proxy_state'].parent,
                                    details=p['details'])
    import audit_hostile_release
    audit = audit_hostile_release.audit(audit_args)
    fixture_check = None
    if run != 'c55':
        fixture_check = validate_fixture_opening(object_at(p['fixture']), p['archive'], paths('c55')['archive'])
    budget = campaign_time_budget.budget(run, ARM, SEED)
    pins = {key: receipt(path) for key, path in p.items() if key != 'fixture' or run != 'c55'}
    pins['audit_script'] = receipt(HERE / 'audit_hostile_release.py')
    pins['time_budget_script'] = receipt(HERE / 'campaign_time_budget.py')
    result = {'run': run, 'complete_evidence': True, 'quality_audit_pass': audit['all_checked_predictions_passed'],
              'score': audit['score'], 'notes': audit['notes'], 'checks': audit['checks'],
              'fixture': fixture_check, 'time_budget': budget, 'provenance': pins}
    if out is not None:
        audit_path = out.with_name(out.stem + '-audit.json')
        # Exercise the existing CLI unchanged and retain its complete result.
        command = [sys.executable, str(HERE / 'audit_hostile_release.py'), '--seed', '2',
                   '--task', str(task), '--state', str(p['proxy_state'].parent),
                   '--details', str(p['details']), '--output', str(audit_path)]
        completed = subprocess.run(command, capture_output=True, text=True)
        require(completed.returncode in (0, 1), f'audit failed: {completed.stderr}')
        require((completed.returncode == 0) == result['quality_audit_pass'], 'audit verdict changed')
        result['audit_command'] = command
        result['audit_receipt'] = receipt(audit_path)
        if run != 'c55':
            fixture_copy = out.with_name(out.stem + '-fixture.json')
            shutil.copyfile(p['fixture'], fixture_copy)
            result['fixture_receipt'] = receipt(fixture_copy)
    return result


def compare_sequences(left_path, right_path, field):
    marker = object()
    left_hash, right_hash = hashlib.sha256(), hashlib.sha256()
    left_count = right_count = 0
    first = None
    for index, pair in enumerate(itertools.zip_longest(records(left_path), records(right_path), fillvalue=marker)):
        values = []
        for side, (row, digest) in enumerate(zip(pair, (left_hash, right_hash))):
            if row is marker:
                values.append(marker)
                continue
            value = row[field]
            require(isinstance(value, str), f'{field}: expected text')
            digest.update(json.dumps(value, ensure_ascii=False).encode() + b'\n')
            values.append(value)
            if side == 0:
                left_count += 1
            else:
                right_count += 1
        if first is None and values[0] != values[1]:
            first = {'zero_based_index': index, 'left': None, 'right': None}
            for label, value in zip(('left', 'right'), values):
                if value is not marker:
                    first[label] = {'sha256': sha_text(value), 'characters': len(value), 'excerpt': value[:1600]}
    return {'identical': first is None, 'lengths': [left_count, right_count],
            'sequence_sha256': [left_hash.hexdigest(), right_hash.hexdigest()], 'first_difference': first}


def compare():
    runs = ['c55', 'c59a', 'c59b']
    result = {'runs': [inspect(run) for run in runs], 'comparisons': [],
              'complete_evidence': True}
    for left, right in itertools.combinations(runs, 2):
        a, b = paths(left), paths(right)
        answers = [object_at(p['details'])['answers'] for p in (a, b)]
        keys = sorted(set(answers[0]) | set(answers[1]))
        differing = [k for k in keys if (k in answers[0]) != (k in answers[1]) or answers[0].get(k) != answers[1].get(k)]
        notes = compare_sequences(a['notes'], b['notes'], 'notes')
        archive = compare_sequences(a['archive'], b['archive'], 'text')
        result['comparisons'].append({'left': left, 'right': right,
            'notes': notes, 'archive_text': archive,
            'conclusions': {'opening_tool_input_equal': opening(a['archive']) == opening(b['archive']),
                            'saved_notes_and_archive_model_text_equal': notes['identical'] and archive['identical'],
                            'graded_answers_equal': not differing,
                            'both_quality_audits_pass': all(x['quality_audit_pass'] for x in result['runs'] if x['run'] in (left, right)),
                            'scope': 'Opening tool equality is not complete HTTP request identity; archive text includes tools and assistant text. No promotion.'},
            'answers': {'identical': not differing, 'lengths': [len(x) for x in answers],
                        'different_keys': differing, 'first_difference': None if not differing else
                        {'key': differing[0], 'left': answers[0].get(differing[0]), 'right': answers[1].get(differing[0])}}})
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--run', choices=('c59a', 'c59b'))
    mode.add_argument('--compare', action='store_true')
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    result = {'schema': 'ctxkeeper.campaign59-result.v1', 'at': datetime.now(timezone.utc).isoformat(),
              'script': receipt(Path(__file__)), 'promotion': False,
              'scope': 'Read-only evidence validation. Exit success does not adopt the memo or certify quality.'}
    try:
        result.update(compare() if args.compare else inspect(args.run, args.out))
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        result.update(complete_evidence=False, error=str(exc))
        args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
        print(f'{args.out}: INVALID EVIDENCE: {exc}', file=sys.stderr)
        return 2
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(f'{args.out}: complete evidence; promotion=false')
    return 0


if __name__ == '__main__':
    sys.exit(main())

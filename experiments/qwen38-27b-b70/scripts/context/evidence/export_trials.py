#!/usr/bin/env python3
"""Validate Harbor trial evidence and export deterministic, reviewable projections.

No model calls. Never turn a rounded reward into an answer count. Each attempt
is retained; an invalid or unfinished attempt cannot become a measured success.
"""
import argparse
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import tomllib


SCHEMA = 'context-trial-manifest.v1'
METRICS = {'wall_s': 'elapsed_seconds', 'completion_tokens': 'completion_tokens',
           'peak_sent_ctx': 'peak_context_tokens', 'lm_calls': 'lm_calls',
           'prompt_tokens': 'prompt_tokens', 'cached_tokens': 'cached_tokens'}
COPY_KEYS = {'verifier', 'task', 'expected', 'summary', 'usage'}


class EvidenceError(ValueError):
    pass


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False,
                       allow_nan=False) + '\n').encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    try:
        value = json.loads(Path(path).read_text())
    except (OSError, ValueError) as error:
        raise EvidenceError(f'{path}: {error}') from error
    if not isinstance(value, dict):
        raise EvidenceError(f'{path}: expected a JSON object')
    return value


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise EvidenceError(f'{name}: expected an integer >= {minimum}, got {value!r}')
    return value


def validate_grade(grade, expected=None):
    if not isinstance(grade, dict) or (expected is not None and not isinstance(expected, dict)):
        raise EvidenceError('grade and expected answers must be JSON objects')
    n = integer(grade.get('n'), 'verifier.n', 1)
    correct = integer(grade.get('correct'), 'verifier.correct')
    if correct > n or type(grade.get('void')) is not bool:
        raise EvidenceError('verifier.correct exceeds n or void is not a boolean')
    if expected is not None and len(expected) != n:
        raise EvidenceError('verifier.n differs from expected-answer count')
    counts = grade.get('counts')
    if counts is not None:
        if not isinstance(counts, dict) or sum(integer(v, 'counts') for v in counts.values()) != n:
            raise EvidenceError('verifier.counts do not sum to n')
        if counts.get('correct') != correct:
            raise EvidenceError('verifier.counts.correct differs from correct')
    per_key = grade.get('per_key')
    if per_key is not None:
        if not isinstance(per_key, dict) or len(per_key) != n:
            raise EvidenceError('verifier.per_key count differs from n')
        if sum(v == 'correct' for v in per_key.values()) != correct:
            raise EvidenceError('verifier.per_key correct count differs from correct')
        if expected is not None and set(per_key) != set(expected):
            raise EvidenceError('verifier.per_key differs from expected keys')
    # Counts, never these fractions, determine the exported numerator/denominator.
    for key, fraction in [('score_raw', correct / n),
                          ('score', 0 if grade['void'] else correct / n)]:
        if key in grade:
            value = grade[key]
            if type(value) not in (float, int) or not math.isfinite(value) or abs(value - fraction) > 1e-8:
                raise EvidenceError(f'verifier.{key} contradicts the exact counts/void flag')
    return correct, n, grade['void']


def parse_summary(data):
    lines = data.decode().splitlines()
    if len(lines) < 2 or not lines[0].startswith('arm\t'):
        raise EvidenceError('summary: missing TSV header or trial row')
    return next(csv.DictReader(lines[:2], delimiter='\t'))


def metrics_from_summary(summary):
    result = {name: None for name in METRICS.values()}
    for key, name in METRICS.items():
        value = summary.get(key)
        if value not in (None, ''):
            try:
                number = float(value) if key == 'wall_s' else int(value)
            except (ValueError, TypeError) as error:
                raise EvidenceError(f'invalid summary metric {key}: {value!r}') from error
            if number < 0 or not math.isfinite(number):
                raise EvidenceError(f'invalid summary metric {key}: {value!r}')
            result[name] = number
    return result


def source(path, expected_hash=None):
    data = Path(path).read_bytes()
    sha = digest(data)
    if expected_hash and sha != expected_hash:
        raise EvidenceError(f'{path}: SHA256 differs from review index')
    return {'original_path': str(path), 'sha256': sha, 'bytes': len(data)}, data


def version(value=None, source_key=None):
    return {'value': value if value else None, 'status': 'recorded' if value else 'unknown',
            'source': source_key if value else None}


def make_row(record_id, sources, blobs, summary, metadata, grade, expected,
             completed, exception=None, agent=None, versions=None):
    trial_id = Path(record_id).name
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', trial_id):
        raise EvidenceError('unsafe trial identifier')
    kwargs = (agent or {}).get('kwargs') or {}
    for key in ('seed', 'stream_tokens', 'target_tokens'):
        if metadata.get(key) is not None:
            integer(metadata[key], f'task.{key}')
    for summary_key, task_key in [('seed', 'seed'), ('size', 'stream_tokens')]:
        if summary.get(summary_key) not in (None, '') and metadata.get(task_key) is not None:
            if int(summary[summary_key]) != metadata[task_key]:
                raise EvidenceError(f'summary.{summary_key} differs from task.{task_key}')
    if summary.get('mode') and summary['mode'] != metadata.get('mode'):
        raise EvidenceError('summary.mode differs from task.mode')
    correct = asked = void = None
    if grade is not None:
        correct, asked, void = validate_grade(grade, expected)
    status = 'completed' if completed and grade is not None else ('interrupted' if exception else 'incomplete')
    kind = metadata.get('kind')
    family = ('retention' if metadata.get('n_surprise', 0) else 'narrative') if kind in ('sparse', 'prose') else {'kv': 'key_value', 'kvstream': 'key_value', 'ledger': 'ledger'}.get(kind, 'unknown')
    fingerprint_parts = {key: sources[key]['sha256'] for key in ('stream', 'expected') if key in sources}
    fingerprint = digest(encoded(fingerprint_parts)) if len(fingerprint_parts) == 2 else None
    row = {'id': trial_id, 'source_record_id': record_id, 'status': status,
           'completed': status == 'completed', 'correct': correct, 'asked': asked, 'void': void,
           'arm': summary.get('arm') or Path(record_id).parent.name.split('__')[0],
           'task_family': family, 'seed': metadata.get('seed'), 'mode': metadata.get('mode'),
           'target_tokens': metadata.get('target_tokens'), 'input_tokens': metadata.get('stream_tokens'),
           'density': metadata.get('density'), 'task_fingerprint': fingerprint,
           'task_fingerprint_method': 'sha256 of canonical JSON mapping stream and expected SHA256s',
           'task_metadata': metadata, 'context_budget_tokens': kwargs.get('context_budget_tokens'),
           'archive': kwargs.get('archive'), 'quoted': kwargs.get('quoted'),
           'model_name': (agent or {}).get('model_name'),
           'exception_type': exception, 'violations': (grade or {}).get('violations', []),
           'versions': versions or {key: version() for key in ('agent', 'harness', 'checker', 'generator', 'runtime', 'model_revision')},
           'sources': sources, **metrics_from_summary(summary)}
    for key, item in sources.items():
        item['copy_path'] = f'sources/{trial_id}/{key}' if key in COPY_KEYS and key in blobs else None
    return row, blobs


def import_review(index_path):
    index_path = Path(index_path).resolve()
    index = read_json(index_path)
    if index.get('schema') != 'context-review-evidence.v1':
        raise EvidenceError('unsupported review-index schema')
    imported = []
    for old in index.get('rows', []):
        sources, blobs = {}, {}
        names = {'summary': 'summary.tsv', 'verifier': 'verifier.json', 'task': 'task.toml', 'expected': 'expected.json'}
        for key, item in old['sources'].items():
            original = Path(item['path'])
            copy = old.get('copies', {}).get(names.get(key))
            if copy:
                path = (index_path.parent / copy).resolve()
                if not path.is_relative_to(index_path.parent):
                    raise EvidenceError('review copy escapes index directory')
                info, data = source(path, item['sha256'])
                info['original_path'] = str(original)
                info['imported_copy'] = str(path)
                sources[key], blobs[key] = info, data
            else:
                if not re.fullmatch('[0-9a-f]{64}', item.get('sha256', '')):
                    raise EvidenceError('review source has invalid SHA256')
                sources[key] = {'original_path': str(original), 'sha256': item['sha256'],
                                'bytes': item['bytes'], 'verification': 'recorded hash; bytes not imported'}
        if not {'summary', 'verifier', 'task', 'expected'} <= blobs.keys():
            raise EvidenceError('review row lacks its score/task/summary source copies')
        summary = parse_summary(blobs['summary'])
        metadata = tomllib.loads(blobs['task'].decode())['metadata']
        grade = json.loads(blobs['verifier'])
        expected = json.loads(blobs['expected'])
        row, blobs = make_row(old['id'], sources, blobs, summary, metadata, grade, expected,
                              True, agent=old.get('agent'))
        row['import_method'] = 'curated review source copies'
        row['review_index_sha256'] = digest(index_path.read_bytes())
        imported.append((row, blobs))
    return imported


def raw_trial(path):
    path = Path(path).resolve()
    sources, blobs = {}, {}
    def get(key, file, required=False):
        file = Path(file)
        if not file.exists():
            if required:
                raise EvidenceError(f'{file}: missing required source')
            return None
        info, data = source(file)
        sources[key], blobs[key] = info, data
        return data
    config = json.loads(get('trial_config', path / 'config.json', True))
    result_data = get('trial_result', path / 'result.json')
    result = json.loads(result_data) if result_data else {}
    task_path = config.get('task', {}).get('path')
    if not task_path:
        raise EvidenceError(f'{path}: task path missing')
    task = Path(task_path)
    if not task.is_absolute():
        task = path / task
    metadata = tomllib.loads(get('task', task / 'task.toml', True).decode())['metadata']
    expected = json.loads(get('expected', task / 'tests/expected.json', True))
    get('stream', task / 'environment/stream.jsonl')
    get('grader', task / 'tests/grade.py')
    grade_data = get('verifier', path / 'verifier/details.json')
    grade = json.loads(grade_data) if grade_data else None
    usage_data = get('usage', path / 'agent/usage.json')
    usage = json.loads(usage_data) if usage_data else {}
    summary = {}
    # A job summary is attributable only when the job has exactly one attempt.
    attempts = [p for p in path.parent.iterdir() if p.is_dir() and (p / 'config.json').exists()]
    summary_path = path.parent.parent.parent / (path.parent.name + '.summary.txt')
    if len(attempts) == 1 and summary_path.exists():
        summary = parse_summary(get('summary', summary_path))
    if not summary:
        summary = {'arm': path.parent.name.split('__')[0]}
        for key, usage_key in [('completion_tokens', 'completion_tokens'), ('lm_calls', 'n_lm_calls'),
                               ('prompt_tokens', 'prompt_tokens'), ('cached_tokens', 'cached_tokens')]:
            if usage.get(usage_key) is not None:
                summary[key] = usage[usage_key]
        if result.get('started_at') and result.get('finished_at'):
            summary['wall_s'] = (datetime.fromisoformat(result['finished_at']) - datetime.fromisoformat(result['started_at'])).total_seconds()
    versions = {key: version() for key in ('agent', 'harness', 'checker', 'generator', 'runtime', 'model_revision')}
    versions['agent'] = version(result.get('agent_info', {}).get('version'), 'trial_result.agent_info.version')
    versions['harness'] = version(usage.get('code_fingerprint'), 'usage.code_fingerprint')
    exception = (result.get('exception_info') or {}).get('exception_type')
    row, blobs = make_row(str(path), sources, blobs, summary, metadata, grade, expected,
                          bool(result.get('finished_at')) and not exception,
                          exception=exception, agent=config.get('agent'), versions=versions)
    row['import_method'] = 'raw Harbor trial'
    return row, blobs


def discover(root):
    root = Path(root).resolve()
    if not root.exists():
        raise EvidenceError(f'{root}: input root does not exist')
    candidates = [root] if (root / 'config.json').exists() else []
    candidates.extend(p.parent for p in root.rglob('config.json'))
    found = []
    for p in sorted(set(candidates)):
        cfg = read_json(p / 'config.json')
        if isinstance(cfg.get('task'), dict) and cfg.get('trial_name'):
            found.append(p)
    return found


def markdown(rows):
    text = ['# Context trial evidence', '',
            'Each row is one attempt. Counts come from the verifier, never rounded reward. '
            'Voided and unfinished attempts remain visible. Missing measurements are shown as unknown.', '',
            '| Trial | Arm | Task | Input tokens | Seed | Correct / asked | Status | Elapsed seconds |',
            '| --- | --- | --- | ---: | ---: | --- | --- | ---: |']
    for r in rows:
        score = f"{r['correct']}/{r['asked']}" if r['correct'] is not None else 'unknown'
        status = r['status'] + ('; void' if r['void'] else '')
        vals = [r['id'], r['arm'], r['task_family'], r['input_tokens'], r['seed'], score, status, r['elapsed_seconds']]
        text.append('| ' + ' | '.join(str(v).replace('|', '\\|') if v is not None else 'unknown' for v in vals) + ' |')
    return '\n'.join(text) + '\n'


def export(review_indexes, roots, output):
    imported = []
    for index in review_indexes:
        imported.extend(import_review(index))
    for root in roots:
        imported.extend(raw_trial(path) for path in discover(root))
    if not imported:
        raise EvidenceError('no trial records found')
    unique = {}
    for row, blobs in imported:
        if row['id'] in unique:
            old, _ = unique[row['id']]
            if old['sources'].get('verifier', {}).get('sha256') != row['sources'].get('verifier', {}).get('sha256') or old['task_fingerprint'] != row['task_fingerprint']:
                raise EvidenceError(f"conflicting evidence for trial {row['id']}")
            # Curated copies retain historical identity and attribution when also found raw.
            continue
        unique[row['id']] = row, blobs
    rows = [unique[key][0] for key in sorted(unique)]
    manifest = {'schema': SCHEMA, 'rows': rows,
                'counts': {state: sum(r['status'] == state for r in rows) for state in ('completed', 'interrupted', 'incomplete')},
                'policy': 'One row per attempt; no best-run selection. Unknown code revisions remain unknown. '
                          'Task fingerprint binds exact stream and expected answers, not harness/runtime identity.'}
    manifest_bytes = encoded(manifest)
    projection = {'schema': 'context-trial-site.v1', 'manifest_sha256': digest(manifest_bytes), 'rows': rows}
    output = Path(output)
    # Validate all inputs before writing any new export.
    output.mkdir(parents=True, exist_ok=True)
    for row, blobs in unique.values():
        for key, item in row['sources'].items():
            if item['copy_path']:
                dest = output / item['copy_path']
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(blobs[key])
    (output / 'manifest.json').write_bytes(manifest_bytes)
    (output / 'site_projection.json').write_bytes(encoded(projection))
    (output / 'results.md').write_text(markdown(rows))
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-index', action='append', default=[], type=Path)
    parser.add_argument('--root', action='append', default=[], type=Path,
                        help='Harbor trial, job, or campaign root; repeat to add roots')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    if not args.review_index and not args.root:
        parser.error('provide --review-index and/or --root')
    try:
        manifest = export(args.review_index, args.root, args.output)
    except (EvidenceError, OSError, ValueError, KeyError, TypeError) as error:
        print(f'evidence export failed: {error}', file=sys.stderr)
        return 1
    print(f"Validated {len(manifest['rows'])} trials: {manifest['counts']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

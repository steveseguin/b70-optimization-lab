#!/usr/bin/env python3
"""Reproduce command accounting and conditional event DAGs. CPU only.

No invented head decomposition is a measurement. Two compatible decompositions
are deliberately retained to test whether the admission decision is identifiable.
"""
import argparse
import ast
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import statistics as st
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def method(filename, names):
    tree = ast.parse((HERE / 'method' / filename).read_bytes())
    body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in body} == set(names)
    exec(compile(ast.Module(body=body, type_ignores=[]), filename, 'exec'), globals())


class DAG:
    def __init__(self):
        self.nodes = {}

    def add(self, name, duration, *dependencies, release=0.):
        assert duration >= 0
        start = max([release, *(self.nodes[d]['end'] for d in dependencies)])
        self.nodes[name] = {'start': start, 'end': start + duration,
                            'duration': duration, 'dependencies': list(dependencies)}
        return start + duration


def decomposition(row, wait):
    """An explicit compatible witness, NOT an estimate of any head duration.

    Set suffix service to the measured B-minus-A tail, and choose a longer
    local head so both w=0 and w>0 can have exactly the same observed B.
    Actual transfer/setup/retirement subdivision is not observed. This is a
    coarse host dependency witness, not a claim of GPU busy time.
    """
    a, b = row['A'] + row['spec_start_offset_ms'], row['B']
    assert b > a > 0, (a, b)
    suffix = b - a
    prefix = max(.8, suffix + .1)
    body = b - wait - prefix
    assert body >= 0 and body <= a
    return body, prefix, suffix


def simulate(row, wait=0., order='current'):
    """One first99 interval, using the original start-emission hit label.

    D_next belongs to the next emission and is moved into this B. Bootstrap
    before the first sampled emission is excluded on both schedules; the
    difference between D_next and D is retained, not rounded away.
    """
    body, prefix, suffix = decomposition(row, wait)
    g = DAG()
    g.add('restore', row['R'])
    g.add('corrected_A', row['C'], 'restore')
    g.add('confirmed_D', row['D'] if order == 'current' or not row['hit'] else 0.)
    ready = g.add('handover', 0., 'confirmed_D', 'corrected_A')
    # Offset is a measured signed start offset; do not invent a positive copy.
    astart = ready + row['spec_start_offset_ms']
    assert astart >= 0 or astart > -0.01
    g.add('next_A', row['A'], release=astart)
    g.add('target_body_and_hidden', body, 'handover')
    if order == 'current':
        g.add('local_head', prefix, 'target_body_and_hidden')
        g.add('suffix_service', suffix, 'target_body_and_hidden', 'next_A')
        g.add('verified', 0., 'local_head', 'suffix_service')
    elif order in ('draft_before_publish', 'publish_before_draft'):
        g.add('speculative_D_next', row['D_next'], 'target_body_and_hidden')
        g.add('local_head', prefix, 'speculative_D_next')
        publication = ('speculative_D_next' if order == 'draft_before_publish'
                       else 'target_body_and_hidden')
        g.add('suffix_service', suffix, publication, 'next_A')
        g.add('verified', 0., 'local_head', 'suffix_service')
    elif order == 'draft_before_merge':
        g.add('local_head', prefix, 'target_body_and_hidden')
        g.add('suffix_service', suffix, 'target_body_and_hidden', 'next_A')
        g.add('speculative_D_next', row['D_next'], 'local_head')
        g.add('verified', 0., 'speculative_D_next', 'suffix_service')
    else:
        raise ValueError(order)
    # The signed observed remainder is retained once; not a physical DAG node.
    return g.nodes['verified']['end'] + row['unresolved_control_gaps_ms'], g.nodes


def summarize(rows, predicted):
    baseline = sum(r['elapsed_ms'] for r in rows)
    proposed = sum(predicted)
    return {'pooled_interval_rate_change_percent': 100 * (baseline / proposed - 1),
            'mean_interval_ms': st.mean(predicted),
            'pooled_interval_rate_tok_s': 1000 * len(rows) / proposed,
            'conditional_ms': {label: st.mean(p for r, p in zip(rows, predicted)
                                             if r['hit'] == hit)
                               for label, hit in [('hit', True), ('miss', False)]}}


def evaluate(rows, wait, order):
    return [simulate(row, wait, order)[0] for row in rows]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (8 * 1024**3, 8 * 1024**3))
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    assert shutil.disk_usage(ROOT).free >= 25_000_000_000
    method('p85_model.py', ('duration', 'intervals'))
    method('p108_extract.py', ('union_ms',))
    archive = tarfile.open(HERE / 'inputs.tar.gz', 'r:gz')
    snapshot = json.load(archive.extractfile('snapshot.json'))
    def raw(name):
        data = archive.extractfile(name).read()
        pin = snapshot['files'][name]
        assert len(data) == pin['bytes'] and hashlib.sha256(data).hexdigest() == pin['sha256'], name
        return data
    # Verify every member, including all negative indexes and empty timing files.
    for name in snapshot['files']:
        raw(name)
    runs, details = [], []
    for run in snapshot['runs']:
        folder = run['folder']
        summary = json.loads(raw(folder + '/summary.json'))
        selection = json.loads(raw(folder + '/run/adapter/selection.json'))
        assert selection['draft']['head_prefix'] == 'p114-80128'
        assert selection['choices']['head'] == 'head-split-compute'
        assert summary['arithmetic'] == 'iq3-p49-split32-v1'
        assert len(summary['requests']) == 12
        rows, requests = [], []
        for request in summary['requests']:
            assert request['exact_oracle'] is True and request['cached_tokens'] == 0
            rr = intervals(request)
            index = {(t['rank'], t['op'], t['position']): t
                     for t in request['rank_trace'] if t['op'] == 9}
            for i, r in enumerate(rr):
                r['D_next'] = duration(index[(1, 9, r['position'] + 1)])
                r['prompt_id'] = request['prompt_id']
                r['prompt_class'] = request['prompt_class']
                stamps = request['generated_token_completion_timestamps']
                r['rank0_command_union_ms'] = union_ms(request['rank_trace'], 0, stamps[i], stamps[i+1])
            rows.extend(rr)
            requests.append({'prompt_id': request['prompt_id'], 'prompt_class': request['prompt_class'],
                             'output_token_sha256': request['output_token_sha256'],
                             'prompt_token_sha256': request['prompt_token_sha256']})
        assert len(rows) == 1188
        baseline = evaluate(rows, 0., 'current')
        error = max(abs(p-r['elapsed_ms']) for p, r in zip(baseline, rows))
        assert error < 1e-7, error
        scenarios = []
        for wait in (0., .2, .4, .6, 1.):
            for order in ('draft_before_publish', 'publish_before_draft', 'draft_before_merge'):
                predictions = evaluate(rows, wait, order)
                scenarios.append({'assumed_merge_wait_ms': wait, 'order': order,
                                  'is_measurement': False, **summarize(rows, predictions)})
                # Every witness reproduces the exact observed current envelope.
                assert max(abs(simulate(r, wait)[0]-r['elapsed_ms']) for r in rows) < 1e-7
        lo, hi = 0., 1.
        for _ in range(45):
            mid = (lo+hi)/2
            ratio = summarize(rows, evaluate(rows, mid, 'publish_before_draft'))['pooled_interval_rate_change_percent']
            if ratio < .5:
                lo = mid
            else:
                hi = mid
        conditional = {}
        for hit, label in ((True, 'hit'), (False, 'miss')):
            subset = [r for r in rows if r['hit'] == hit]
            conditional[label] = {'n': len(subset), 'mean_ms': {
                key: st.mean(r[key] for r in subset) for key in (
                    'elapsed_ms', 'A', 'B', 'D', 'D_next', 'R', 'C',
                    'spec_start_offset_ms', 'unresolved_control_gaps_ms',
                    'rank0_command_union_ms')}}
        example = rows[0]
        examples = [{'assumed_merge_wait_ms': wait, 'order': order,
                     'is_measurement': False, 'interval_ms': simulate(example, wait, order)[0],
                     'nodes': simulate(example, wait, order)[1]}
                    for wait in (0., .6) for order in ('current', 'draft_before_publish',
                                                      'publish_before_draft', 'draft_before_merge')]
        runs.append({'lane': run['lane'], 'selection_sha256': hashlib.sha256(raw(folder + '/run/adapter/selection.json')).hexdigest(),
                     'binary_sha256': summary['requests'][0]['binary_sha256'],
                     'baseline': summarize(rows, baseline), 'conditional': conditional,
                     'reported_class_balanced_tok_s': summary['class_balanced_tok_s_1_100_intervals_after_ttft']['median'],
                     'current_DAG_max_error_ms': error, 'scenarios': scenarios,
                     'uniform_wait_needed_for_half_percent_ms': hi,
                     'discarded_D_mean_ms_per_interval': st.mean(0. if r['hit'] else r['D'] for r in rows),
                     'finite_window_D_next_minus_D_ms': sum(r['D_next']-r['D'] for r in rows),
                     'requests': requests, 'example_DAGs': examples})
        details.append({'lane': run['lane'], 'rows': rows})
    matches = []
    for name in snapshot['files']:
        if name.endswith('DO-NOT-REPEAT.md'):
            lines = raw(name).decode().splitlines()
            selected = [{'line': i+1, 'text': line} for i, line in enumerate(lines)
                        if re.search(r'draft|head|depth.?two|depth.?2|speculat|rollback|publication', line, re.I)]
            matches.append({'path': name, 'sha256': snapshot['files'][name]['sha256'], 'matches': selected})
    result = {'schema': 'own-runtime.packet126.dependency-simulation.v1',
              'device_executed': False, 'submission_eligible': False,
              'candidate_admitted': False,
              'decision': 'No supported >=0.5% prediction: no-wait scenario loses; split-head wait is unobserved and compatible witnesses straddle the gate.',
              'input_archive_sha256': hashlib.sha256((HERE/'inputs.tar.gz').read_bytes()).hexdigest(),
              'method_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((HERE/'method').glob('*.py'))},
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'runs': runs,
              'limitations': ['Assumed merge waits/head decompositions are sensitivity scenarios, never measured times.',
                             'Zero new transaction/rollback/publication overhead is optimistic.',
                             'Acceptance and exact draft arithmetic are assumed unchanged, not device-qualified.',
                             'Pooled first99 interval rates are not the headline class-balanced metric.',
                             'Existing command times include overlapping host/device work and are not a per-kernel GPU budget.',
                             'First99 stationary-window calculation excludes prompt startup and response termination; D_next-D boundary is retained.']}
    outputs = {'simulation.json': (json.dumps(result, indent=2, sort_keys=True)+'\n').encode(),
               'prior-audit.json': (json.dumps({'indexes_checked': len(matches), 'indexes': matches}, indent=2)+'\n').encode(),
               'intervals.json.gz': gzip.compress((json.dumps(details, sort_keys=True)+'\n').encode(), mtime=0)}
    for name, data in outputs.items():
        if args.check:
            assert (HERE/name).read_bytes() == data, name
        else:
            (HERE/name).write_bytes(data)
    print(json.dumps({'passed': True, 'archive_members_verified': len(snapshot['files']),
                      'negative_indexes_checked': len(matches),
                      'runs': [{'lane': r['lane'], 'conditional': r['conditional'],
                                'no_wait': r['scenarios'][0],
                                'wait_needed_ms': r['uniform_wait_needed_for_half_percent_ms']}
                               for r in runs]}, indent=2))


if __name__ == '__main__':
    main()

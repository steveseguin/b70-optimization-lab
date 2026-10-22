#!/usr/bin/env python3
"""Combine fresh exhaustive-mini and sampled-real strict rollback CPU proofs."""
import argparse
import hashlib
import json
from pathlib import Path
import seal40
P = Path(__file__).resolve().parent


def validate(row, real):
    for name in ('passed', 'terminal_eos', 'raw_allocation_bytes_equal',
                 'all_inventoried_allocations', 'snapshot_rollback'):
        assert row.get(name) is True, (name, real)
    assert row.get('device_executed') is False and row.get('performance_claim') is False
    assert row.get('screen') is False and row.get('real_model') is real
    assert row.get('committed_state_scrubbed') is False
    assert set(row.get('controllers', ())) == {'native', 'python'}
    assert row.get('every_mini_launch_boundary') is (not real)
    assert row.get('real_model_sampled_boundaries') is real
    rows = row['rows']
    assert rows and all(r['tokens_equal'] and r['raw_allocation_bytes_equal'] for r in rows)
    groups = {}
    for item in rows:
        key = (item['controller'], item['position'], item['retain_steps'])
        groups.setdefault(key, []).append(item)
    positions = set(row['sampled_positions'])
    assert positions and (not real or len(positions) >= 2)
    expected = {(c, p, r) for c in ('native', 'python') for p in positions
                for r in ('none', '1-8,97-104')}
    assert set(groups) == expected, 'missing controller/position/retention coverage'
    for key, group in groups.items():
        nset = {r['actual_compute_launches'] for r in group}
        assert len(nset) == 1
        n = nset.pop()
        cuts = [r['launch_boundary'] for r in group]
        assert len(cuts) == len(set(cuts)), 'duplicate cut'
        if real:
            assert {0, n, n+1} <= set(cuts)
            assert len([v for v in cuts if 0 < v < n]) >= 4
        else:
            assert set(cuts) == set(range(n+2)), 'mini launch coverage incomplete'
    negatives = row['negative_controls']
    assert {(r['controller'], r['position'], r['kind']) for r in negatives} == {
        (c, p, k) for c in ('native', 'python') for p in positions
        for k in ('active-bank', 'valid-qsa-prefix')}
    assert all(r['actual_cpu_memory_corruption'] and r['rejected_by_full_state_comparison'] for r in negatives)
    assert row['negative_control_count'] == len(negatives)
    assert row['gate_count'] == len(rows) + len(negatives)
    assert len(row['owners']) == 1 + len(groups)//2 + len(rows) + len(negatives)
    return dict(gates=row['gate_count'], comparisons=len(rows), negative_controls=len(negatives),
                owners=len(row['owners']), sampled_positions=sorted(positions))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mini', default='terminal-eos-all-state-mini-both.json')
    ap.add_argument('--real', default='terminal-eos-all-state-real-both.json')
    ap.add_argument('--output', default='terminal-eos-all-state-gates.json')
    a = ap.parse_args()
    binaries = seal40.artifacts(P)
    recorded, _ = seal40.load_ledger(P, binaries)
    sources = {Path(__file__).name: seal40.sha(__file__)}
    children = []
    prerequisites = {}
    for name, real in ((a.mini, False), (a.real, True)):
        path = P/name
        assert path.resolve().parent == P and name in recorded, 'fresh current execution ledger required'
        row = seal40.read(path)
        counts = validate(row, real)
        errors, ns, nb = seal40.receipt_bindings(row, binaries, P)
        assert not errors and ns and nb, (name, errors)
        ledger = recorded[name]
        assert ledger['receipt_sha256'] == seal40.sha(path)
        sources.update(row['source_sha256'])
        prerequisites[name] = seal40.sha(path)
        children.append(dict(receipt=name, receipt_sha256=seal40.sha(path),
                             binary_sha256=row['binary_sha256'],
                             execution_ledger=dict(path=ledger['ledger'], sha256=ledger['ledger_sha256']),
                             owner_archives=[owner['archive'] for owner in row['owners']],
                             real_model=real, **counts))
    out = dict(schema='packet40.strict-terminal-aggregate.v1', passed=True, device_executed=False,
               terminal_eos=True, raw_allocation_bytes_equal=True, all_inventoried_allocations=True,
               every_mini_launch_boundary=True, real_model_sampled_boundaries=True,
               controllers=['native', 'python'], snapshot_rollback=True,
               committed_state_scrubbed=False, performance_claim=False, diagnostic_only=True,
               logical_event_scope='Scheduling counter excluded from equality; raw inventory SHA and counter retained per owner.',
               real_prompt_scope='Original seven-token prefix with zero or one verified generated token appended; full-weight production launches; diagnostic, not full-prompt oracle or speed evidence.',
               source_sha256=sources, prerequisite_receipts_sha256=prerequisites, children=children,
               gate_count=sum(c['gates'] for c in children),
               negative_control_count=sum(c['negative_controls'] for c in children))
    destination = P/a.output
    assert destination.resolve().parent == P
    seal40.save(destination, out)
    print(json.dumps(dict(passed=True, receipt=a.output, gates=out['gate_count'])))

if __name__ == '__main__':
    main()

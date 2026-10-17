#!/usr/bin/env python3
"""Build hash-bound CPU census mapping after the admitted lifecycle has exited.

python3 -B build_manifest.py --run-dir RAID_RUN --arm eager-census --output MAP
Requires all owners gone and the full post-exit watch. Discovers PTI
Chrome JSON under run-dir/unitrace (including result-dir per-process folders),
and PID/rank receipts under run-dir/markers. Never infers rank from a synthetic
GPU PID. Parent/API-only traces and malformed/unbound worker evidence are
retained in excluded_traces; missing ranks remain analysis findings. Malformed
Chrome files, ambiguous PID bindings and changed source pins fail closed.
Use after all server owners have gone; this script only reads CPU files.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('census_analysis_manifest', ROOT / 'analyze_census.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)
spec = importlib.util.spec_from_file_location('census_marker_pins', ROOT / 'trace_marks.py')
marks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(marks)


def safe_file(path, root):
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
        raise ValueError(f'not a regular file within run directory: {path}')


def build(run_dir, arm, output):
    root = Path(run_dir).resolve(strict=True)
    output = Path(output).resolve()
    lifecycle_path = root / 'census-run.json'
    safe_file(lifecycle_path, root)
    lifecycle = json.loads(lifecycle_path.read_text())
    if lifecycle.get('schema') != 'own-xpu-runtime.packet4.a367-census.v1':
        raise ValueError('wrong lifecycle receipt schema')
    if lifecycle.get('all_owners_gone') is not True or lifecycle.get('gap_complete') is not True:
        raise ValueError('offline analysis requires all owners gone and full post-exit gap')
    if arm not in {'graph-reference', 'graph-census', 'eager-census'}:
        raise ValueError('unknown arm')
    identity_path = root / 'identity.json'
    safe_file(identity_path, root)
    identity_hash = analysis.sha(identity_path)
    identity = json.loads(identity_path.read_text())
    if (identity.get('schema') != 'own-xpu-runtime.packet4.a367-census-identity.v1'
            or identity.get('arm') != arm or lifecycle.get('identity_sha256') != identity_hash):
        raise ValueError('arm or identity hash disagrees with lifecycle')
    def relative(path):
        return os.path.relpath(path, output.parent)
    manifest = {'schema': analysis.SCHEMA, 'arm': arm, 'auto_itt': True,
                'expected_ranks': [0, 1, 2, 3], 'traces': [], 'excluded_traces': [],
                'steps': [], 'family_rules': [], 'graph_opaque': False,
                'lifecycle': {'path': relative(lifecycle_path), 'sha256': analysis.sha(lifecycle_path)},
                'identity': {'path': relative(identity_path), 'sha256': identity_hash},
                'rank_receipts': [], 'notes': []}
    if arm == 'graph-reference':
        manifest['notes'].append('Untraced timing reference: no device kernel census expected; no fabricated steps.')
        return manifest
    by_pid, by_rank = {}, {}
    for path in sorted((root / 'markers').glob('marker-rank-*-pid-*.json')):
        safe_file(path, root)
        receipt = json.loads(path.read_text())
        rank, pid = receipt.get('rank'), receipt.get('pid')
        if (receipt.get('schema') != 'a367-census-marker-rank-v1' or type(rank) is not int
                or rank not in range(4) or type(pid) is not int or pid <= 0):
            raise ValueError(f'invalid worker rank receipt: {path}')
        if path.name != f'marker-rank-{rank}-pid-{pid}.json':
            raise ValueError('worker receipt filename disagrees with content')
        if receipt.get('source_pins') != marks.SOURCE_PINS:
            raise ValueError('worker marker source pins drifted')
        if pid in by_pid or rank in by_rank:
            raise ValueError('duplicate worker PID or rank receipt')
        by_pid[pid] = (rank, path)
        by_rank[rank] = pid
        manifest['rank_receipts'].append({'rank': rank, 'worker_pid': pid,
                                         'path': relative(path), 'sha256': analysis.sha(path)})
    seen_paths, seen_ranks = set(), set()
    trace_root = root / 'unitrace'
    for path in sorted(trace_root.rglob('*.json')) if trace_root.exists() else []:
        safe_file(path, root)
        with path.open('r', encoding='utf-8') as handle:
            prefix = handle.read(4096)
        if not re.search(r'"traceEvents"\s*:', prefix):
            continue  # run_config and metrics files are not Chrome traces.
        if path.stat().st_size > 1024 * 1024 * 1024:
            raise ValueError('trace exceeds 1 GiB offline parser limit')
        payload = json.loads(path.read_text())
        events = payload.get('traceEvents') if isinstance(payload, dict) else None
        if not isinstance(events, list) or any(not isinstance(e, dict) for e in events):
            raise ValueError(f'malformed Chrome trace: {path}')
        # PTI writes real worker process_name metadata first; GPU metadata comes
        # later. Host cpu_op/H2D records provide an independent binding when present.
        host_pids = {e.get('pid') for e in events if e.get('cat') == 'cpu_op' or
                     (e.get('ph') == 's' and str(e.get('cat', '')).startswith('Flow_H2D_'))}
        first_process = next((e for e in events if e.get('ph') == 'M' and e.get('name') == 'process_name'), None)
        if first_process is not None:
            host_pids.add(first_process.get('pid'))
        matched = host_pids.intersection(by_pid)
        if len(matched) > 1:
            raise ValueError('trace spans multiple worker PIDs; cannot bind rank')
        digest = analysis.sha(path)
        if digest in seen_paths:
            raise ValueError('duplicate trace bytes would double-count device work')
        seen_paths.add(digest)
        receipt = {'path': relative(path), 'sha256': digest, 'bytes': path.stat().st_size,
                   'device_events': sum(e.get('ph') == 'X' and e.get('cat') == 'gpu_op' for e in events),
                   'host_pids': sorted(p for p in host_pids if type(p) is int)}
        if not matched:
            receipt['reason'] = 'No marker receipt binds this host PID; parent/API-only or unbound trace retained.'
            manifest['excluded_traces'].append(receipt)
            continue
        pid = next(iter(matched))
        rank, rank_path = by_pid[pid]
        seen_ranks.add(rank)
        manifest['traces'].append({**receipt, 'id': f'r{rank}-t{len(manifest["traces"])}',
                                   'rank': rank, 'worker_pid': pid,
                                   'rank_evidence': relative(rank_path),
                                   'rank_evidence_sha256': analysis.sha(rank_path)})
    manifest['notes'].append(f'Observed worker traces for ranks {sorted(seen_ranks)}; absent ranks stay missing.')
    if arm == 'graph-census' and not any(t['device_events'] for t in manifest['traces']):
        manifest['graph_opaque'] = True
        manifest['notes'].append('No graph device events observed; this does not prove tracer compatibility.')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', required=True, type=Path)
    parser.add_argument('--arm', required=True, choices=['graph-reference', 'graph-census', 'eager-census'])
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    manifest = build(args.run_dir, args.arm, args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write('\n')
    print(json.dumps({'manifest': str(args.output), 'traces': len(manifest['traces']),
                      'excluded_traces': len(manifest['excluded_traces'])}))


if __name__ == '__main__':
    main()

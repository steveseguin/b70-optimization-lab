#!/usr/bin/env python3
"""CPU-only accounting of existing bundle7 receipts; no device imports.

Extract unchanged accounting functions from byte-preserved method snapshots,
without executing their historical import-time resource-limit side effects.
"""
import argparse
import ast
import gzip
import hashlib
import json
from pathlib import Path
import resource
import statistics as st
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SH = HERE.parent / 'screen/v4-lanes/evidence'
SOURCES = {}
ARCHIVE = None


def read(p):
    relative = str(p.relative_to(ROOT))
    raw = (ARCHIVE.extractfile(relative).read()
           if ARCHIVE is not None and relative in ARCHIVE.getnames()
           else p.read_bytes())
    SOURCES[str(p.relative_to(ROOT))] = {
        'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    return raw


def method(file, names):
    tree = ast.parse(read(HERE / 'method' / file))
    body = [node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in body} == set(names)
    exec(compile(ast.Module(body=body, type_ignores=[]), file, 'exec'), globals())


def summarize(rows):
    return {label: {'n': len(z), 'mean_ms': {
        k: st.mean(x[k] for x in z) for k in rows[0]
        if k not in ('i', 'position', 'hit', 'draft_rank')
        and all(isinstance(x[k], (int, float)) for x in z)},
        'slack_median_ms': st.median(x['rank0_slack_ms'] for x in z),
        'slack_min_ms': min(x['rank0_slack_ms'] for x in z),
        'slack_max_ms': max(x['rank0_slack_ms'] for x in z)}
        for hit, label in ((True, 'hit'), (False, 'miss'))
        if (z := [x for x in rows if x['hit'] == hit])}


def main():
    global ARCHIVE
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (8 * 1024**3, 8 * 1024**3))
    assert __import__('shutil').disk_usage(ROOT).free >= 25_000_000_000
    assert __import__('os').getpriority(__import__('os').PRIO_PROCESS, 0) == 19
    assert set(__import__('os').sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    ARCHIVE = tarfile.open(HERE / 'inputs.tar.gz', 'r:gz')
    snapshot = json.loads(ARCHIVE.extractfile('snapshot.json').read())
    for relative, pin in snapshot['files'].items():
        raw = ARCHIVE.extractfile(relative).read()
        assert len(raw) == pin['bytes'] and hashlib.sha256(raw).hexdigest() == pin['sha256']
    read(Path(__file__))
    method('p85_model.py', ('duration', 'intervals'))
    method('p108_extract.py', ('union_ms',))
    runs = []
    for run in snapshot['runs']:
        folder = ROOT / run['source']
        requests = []
        manifest = json.loads(read(folder / 'suite-manifest.snapshot.json'))
        identity = json.loads(read(folder / 'identity.json'))
        selection = json.loads(read(folder / 'run/adapter/selection.json'))
        rows = []
        for relative in run['receipts']:
            p = ROOT / relative
            r = json.loads(read(p))
            rr = intervals(r)
            stamps = r['generated_token_completion_timestamps']
            for i, x in enumerate(rr):
                for rank in (0, 1):
                    busy = union_ms(r['rank_trace'], rank, stamps[i], stamps[i+1])
                    x[f'rank{rank}_host_command_busy_ms'] = busy
                    x[f'rank{rank}_outside_host_commands_ms'] = x['elapsed_ms'] - busy
                    assert -1e-7 <= busy <= x['elapsed_ms'] + 1e-7
            rows.extend(rr)
            requests.append({'source': str(p.relative_to(ROOT)),
                             'prompt_id': r['prompt_id'],
                             'prompt_class': r['prompt_class'],
                             'output_tokens': r['output_tokens'],
                             'exact_oracle': r['exact_oracle'],
                             'conditional': summarize(rr), 'intervals': rr})
        census = []
        copies = {}
        for relative in run['rank_files']:
            p = ROOT / relative
            raw = read(p)
            census.append({'path': relative, 'bytes': len(raw)})
            if p.parent.name == 'rank0' and p.name == 'p105-transfers.jsonl':
                for line in raw.splitlines():
                    event = json.loads(line)
                    copies.setdefault(event['leg'], []).append(event['host_us'] / 1000)
        split_head = selection['choices']['head'] == 'head-split-compute'
        for leaf in ('native_controller.hpp', 'rank.hpp', 'p105_runtime.hpp'):
            read(HERE.parent / 'packet118-record-bundle' / leaf)
        copy_stats = {leg: {'n': len(v), 'mean_ms': st.mean(v), 'min_ms': min(v)}
                      for leg, v in copies.items()}
        minimum_copy = sum(s['min_ms'] for s in copy_stats.values())
        conditional = summarize(rows)
        for label, group in conditional.items():
            tail = group['mean_ms']['rank0_slack_ms']
            group['usable_rank0_slack_ms'] = None if split_head else tail
            group['loose_mean_slack_upper_bound_ms'] = tail - minimum_copy if split_head else tail
        assert len(requests) == 12 and len(rows) == 1188
        runs.append({'source': str(folder.relative_to(ROOT)),
                     'summary_present_at_snapshot': run['summary_present'],
                     'identity': identity, 'selection': selection,
                     'request_count': len(requests), 'interval_count': len(rows),
                     'conditional': conditional, 'requests': requests,
                     'untraced_rank0_head_service': split_head,
                     'rank0_head_transfer_all_calls': copy_stats,
                     'minimum_mandatory_head_copy_ms': minimum_copy,
                     'rank_file_census': census})
    result = {'schema': 'packet123.slack.v1',
              'definition': 'First 99 emission intervals per suite request. Hit labels starting emission. Legacy rank0_slack_ms = B - A - start offset: on split-head runs this is an APPARENT TAIL containing untraced mandatory rank0 head service. Busy is clipped union of all RECORDED rank command envelopes. Outside includes head service, dependency/control time; it is not GPU idle.',
              'scope': 'Existing receipts only; no speed verdict or output promotion. Bundle7 usable slack UNKNOWN, admission >=0.3 ms UNPROVEN, not a measured <0.3 ms failure.',
              'admission': {'threshold_ms': 0.3, 'usable_hit_slack_ms': None,
                            'status': 'blocked-missing-head-service-timestamps',
                            'placement_preparation_admitted': False},
              'runs': runs, 'sources': SOURCES}
    detail = (json.dumps(result, indent=2) + '\n').encode()
    for r in runs:
        for request in r['requests']:
            request.pop('intervals')
    result['interval_artifact'] = {'path': 'intervals.json.gz',
                                 'uncompressed_sha256': hashlib.sha256(detail).hexdigest()}
    summary = (json.dumps(result, indent=2) + '\n').encode()
    if args.check:
        assert gzip.decompress((HERE / 'intervals.json.gz').read_bytes()) == detail
        assert (HERE / 'slack.json').read_bytes() == summary
        print('PASS: input pins, all 2376 interval unions, and deterministic replay')
    else:
        (HERE / 'intervals.json.gz').write_bytes(gzip.compress(detail, mtime=0))
        (HERE / 'slack.json').write_bytes(summary)
        print(json.dumps({'admission': result['admission'], 'runs': len(runs)}))


if __name__ == '__main__':
    main()

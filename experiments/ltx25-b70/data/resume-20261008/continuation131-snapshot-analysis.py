#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""CPU-only snapshot budget from a fixed read of each saved client manifest.

Reads JSON files only. Writes one new sibling artifact; no imports from a runtime,
no client/run mutations, devices, network, processes, or temporary directories.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

HERE = Path(__file__).parent
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
LABELS = ('request-before', 'A-before', 'A-after', 'B-before', 'B-after', 'request-after')
SOURCES = {}


def read(path, lines=False):
    raw = path.read_bytes()
    SOURCES[str(path)] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    return [json.loads(line) for line in raw.splitlines() if line.strip()] if lines else json.loads(raw)


def stats(values):
    return {'n': len(values), 'median': median(values), 'mean': mean(values),
            'min': min(values), 'max': max(values)} if values else None


def summarize(rows):
    return {key: stats([r[key] for r in rows]) for key in rows[0]
            if isinstance(rows[0][key], (int, float)) and key != 'seq'} if rows else {}


def collect(session):
    manifest_path = Path('/home/steve/ltx-stream') / session / 'manifest.jsonl'
    manifest = read(manifest_path, lines=True)
    first = manifest[0]
    packet = first['run_name'].split('-')[0][6:]
    roots = []
    for path in ROOT.glob('encoder-server-continuation-stream-' + packet + '*'):
        probe = path / 'receipts' / ('receipt-' + first['run_name'] + '.json')
        if probe.is_file() and read(probe)['server_identity_sha256'] == first['server_identity_sha256']:
            roots.append(path)
    assert len(roots) == 1, roots
    root = roots[0]
    receipts = {m['stream_seq']: read(root / 'receipts' / ('receipt-' + m['run_name'] + '.json'))
                for m in manifest}
    rows = []
    for seq, receipt in sorted(receipts.items()):
        if seq < 10:
            continue
        options = receipt['server_options']
        assert options['snapshot_digest_cache'] == 1 and options['snapshot_schedule'] == 'full'
        snaps = {s['label']: s for s in receipt['snapshots']}
        assert tuple(snaps) == LABELS
        assert all(s['synchronized'] == ['xpu:0', 'xpu:1', 'xpu:2', 'xpu:3'] for s in snaps.values())
        row = {'seq': seq, 'dual': any(s['dual'] for s in snaps.values()),
               **{label: snaps[label]['seconds'] for label in LABELS},
               'first_three': sum(snaps[label]['seconds'] for label in LABELS[:3]),
               'a_pair': snaps['A-before']['seconds'] + snaps['A-after']['seconds'],
               'all_six': sum(s['seconds'] for s in snaps.values()),
               'request_wrapper': receipt['timing_s']['submit_split']['request_before_snapshot']}
        for part in ('state', 'facts', 'residence', 'memory', 'dual_walk', 'dual_fingerprint'):
            row['first_three_' + part] = sum(snaps[label]['parts_s'].get(part, 0) for label in LABELS[:3])
            row['a_pair_' + part] = sum(snaps[label]['parts_s'].get(part, 0) for label in ('A-before', 'A-after'))
        if seq + 1 in receipts:
            row['period_to_next'] = (receipts[seq + 1]['timing_ns']['submit'] - receipt['timing_ns']['submit']) / 1e9
        rows.append(row)
    # Period summaries need consecutive receipts; other summaries use all complete rows.
    windows = {}
    for name, selected in [('complete_prefix', rows), ('fixed40', [r for r in rows if 10 <= r['seq'] < 50])]:
        complete = [{k: v for k, v in row.items() if k != 'period_to_next'} for row in selected]
        windows[name] = {'n': len(selected), 'range': [selected[0]['seq'], selected[-1]['seq']],
                         'all': summarize(complete), 'ordinary': summarize([r for r in complete if not r['dual']]),
                         'dual': summarize([r for r in complete if r['dual']]),
                         'period_to_next': stats([r['period_to_next'] for r in selected if 'period_to_next' in r])}
    return {'root': str(root), 'identity': first['server_identity_sha256'], 'frames': first['frames'],
            'manifest_rows': len(manifest), 'options': options, 'windows': windows, 'rows': rows}


if __name__ == '__main__':
    runs = {s: collect(s) for s in ('s127-live01', 's128-live01', 's128-gc60-live01', 's129-live01')}
    author = HERE.parent.parent / 'recovery' / '20261010-continuation130-stream'
    for name in ('snapshot_fingerprint.py', 'candidate_safety.py', 'test_snapshot_schedule.py', 'launch-130.sh'):
        path = author / name
        raw = path.read_bytes()
        SOURCES[str(path)] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    path = ROOT / 'prepared-continuation-stream-130' / 'source' / 'scripts' / 'native_adapter.py'
    raw = path.read_bytes()
    SOURCES[str(path)] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    out = {'schema': 'ltx.continuation131.cpu-snapshot-budget.v1',
           'observed_utc': datetime.now(timezone.utc).isoformat(),
           'method': 'Measured inspector seconds, summed within each receipt before summary. Initial three = request-before, A-before, A-after. Ordinary excludes mandatory dual walks. Fixed40 = stream_seq 10..49. Controller pre-inspection barriers have no separate timer. No candidate schedule was run.',
           'runs': runs, 'sources': SOURCES}
    with (HERE / 'continuation131-snapshot-evidence.json').open('x') as handle:
        handle.write(json.dumps(out, indent=2, ensure_ascii=False) + '\n')
    for session, run in runs.items():
        print(session, 'prefix', run['windows']['complete_prefix']['n'], run['windows']['complete_prefix']['range'])
        for window in ('fixed40', 'complete_prefix'):
            for kind in ('all', 'ordinary', 'dual'):
                values = run['windows'][window][kind]
                print(window, kind, {k: {'n': values[k]['n'], 'median': values[k]['median'], 'mean': values[k]['mean']}
                                     for k in ('request-before', 'A-before', 'A-after', 'first_three', 'a_pair_memory', 'all_six')})

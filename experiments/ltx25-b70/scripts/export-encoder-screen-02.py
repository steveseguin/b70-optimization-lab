#!/usr/bin/env python3
"""Export completed screen evidence without touching runtime or review media."""
import gzip
import hashlib
import json
from pathlib import Path
import statistics

LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
SOURCE = ROOT / 'encoder-screen-02'
DEST = LANE / 'data/encoder-screen-02'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    evidence, inventory = {}, {}

    def read(path):
        raw = path.read_bytes()
        name = str(path.relative_to(ROOT))
        evidence[name] = raw.decode()
        inventory[name] = {'sha256': digest(raw), 'bytes': len(raw)}
        return json.loads(raw) if path.suffix == '.json' else raw.decode()

    progress = read(SOURCE / 'progress.json')
    if progress['status'] != 'passed' or progress['completed_requests'] != 25:
        raise RuntimeError('Only a completed passing screen can be exported here')
    identity = read(SOURCE / 'identity.json')
    server = Path(identity['encoder_run_dir'])
    for path in sorted(SOURCE.iterdir()):
        if path.is_file():
            read(path)
    for name in ('server-identity.json', 'server-args.json', 'determinism-after-import.json',
                 'encoder-screen-02-wrapper.json'):
        read(server / name)
    for path in sorted(server.glob('components-*-split-*.json')):
        read(path)
    read(ROOT / 'encoder-screen-02-client.log')
    read(ROOT / 'encoder-migration-02.json')
    rows = []
    for row in progress['rows']:
        run = row['run']
        if row['status'] != 'passed':
            raise RuntimeError('Incomplete row')
        placement = read(SOURCE / (run + '-placement.json'))
        parity = read(SOURCE / (run + '-parity.json'))
        if not (placement['passed'] and parity['status'] == 'passed' and
                set(parity['comparisons']) == {'images', 'video_latent', 'audio_latent', 'waveform'} and
                all(x['bitwise_equal'] for x in parity['comparisons'].values()) and
                row['capture']['deterministic_enabled'] is True and
                row['capture']['deterministic_warn_only'] is False):
            raise RuntimeError('Quality receipt failed')
        for name in ('profile.json', 'prompt.json', 'history.json', 'identity.json'):
            read(ROOT / 'requests' / run / name)
        a = placement['inspection']['accounting']
        small = placement['inspection']['small_state']
        actual = (a['registered_parameter_bytes_on_load_device'] +
                  a['registered_persistent_buffer_bytes_on_load_device'])
        rows.append({**{k: row[k] for k in ('run', 'arm', 'variant', 'fixture', 'initialization', 'reference')},
            'preview_ready_seconds': row['profile']['preview_ready_seconds'],
            'tensor_archive_ready_seconds': row['profile']['tensor_archive_ready_seconds'],
            'node_seconds': {n['node']: n['seconds'] for n in row['profile']['nodes']},
            'exact_four_outputs': True, 'strict_determinism': True,
            'actual_registered_resident_bytes': actual,
            'reported_loaded_bytes': a['reported_loaded_weight_bytes'],
            'accounting_shortfall_bytes': actual - a['reported_loaded_weight_bytes'],
            'offload_buffer_bytes': a['reported_offload_buffer_bytes'],
            'small_state_xpu_counts': {kind: sum(r['kind'] == kind and r['device'] == 'xpu:2'
                                                for r in small['records'])
                                       for kind in ('rmsnorm', 'scalar')},
            'capture': row['capture'], 'comparisons': parity['comparisons']})
    arms = []
    for arm in progress['arms']:
        warm = [r for r in rows if r['arm'] == arm['arm'] and not r['initialization']]
        arms.append({**arm, 'warm_count': len(warm),
            'warm_tensor_median_seconds': statistics.median(r['tensor_archive_ready_seconds'] for r in warm),
            'node_median_seconds': {node: statistics.median(r['node_seconds'][node] for r in warm)
                                    for node in ('364', '344', '368', '374', '358', '414', '75')}})
    summary = {'schema': 'ltx.encoder-screen-result.v1', 'status': 'passed',
        'campaign': SOURCE.name, 'source_root': str(ROOT), 'identity': identity,
        'completed_requests': 25, 'exact_four_outputs': True, 'strict_determinism': True,
        'speed_promotion': False, 'streaming_qualification': False,
        'limits': ['Four warm samples per arm in one persistent process.',
                   'First request per arm includes rebuild and is excluded.',
                   'Control small-state placement changes during warm-up; compare matching fixture positions.',
                   'Node times are client event intervals, not synchronized kernel timings.',
                   'Exact tensor comparisons qualify these three prompt/seed fixtures only.'],
        'arms': arms, 'rows': rows, 'retained_outputs': progress['retained_outputs']}
    DEST.mkdir(exist_ok=False)
    # Original receipt/log bytes survive JSON string escaping and deterministic gzip.
    packed = json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    compressed = gzip.compress(packed, mtime=0)
    (DEST / 'evidence.json.gz').write_bytes(compressed)
    summary['evidence_archive_sha256'] = digest(compressed)
    summary['exporter_sha256'] = digest(Path(__file__).read_bytes())
    for name, value in (('summary.json', summary), ('inventory.json', inventory)):
        (DEST / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    restored = json.loads(gzip.decompress(compressed))
    if any(digest(restored[name].encode()) != info['sha256'] for name, info in inventory.items()):
        raise RuntimeError('Archive roundtrip failed')
    print(json.dumps({'status': 'passed', 'files': len(inventory), 'archive_bytes': len(compressed),
                      'arms': arms}, indent=2))


if __name__ == '__main__':
    main()

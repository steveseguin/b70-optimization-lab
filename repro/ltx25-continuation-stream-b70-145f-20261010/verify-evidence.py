#!/usr/bin/env python3
"""Offline, standard-library-only audit. No runtime imports, devices or network."""
import hashlib
import json
import math
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bound(item):
    path = ROOT / item['path']
    if not path.resolve().is_relative_to(ROOT):
        raise ValueError('Evidence path escapes repository')
    if digest(path) != item['sha256']:
        raise ValueError('Hash differs: ' + item['path'])
    return path


def main():
    checked = 0
    for line in (HERE / 'manifest.sha256').read_text().splitlines():
        sha, name = line.split('  ', 1)
        bound({'path': name, 'sha256': sha})
        checked += 1
    att = json.loads((HERE / 'promotion-attestation.json').read_text())
    bound(att['performance_evidence'])
    for item in att['quality_evidence']:
        verdict = json.loads(bound(item).read_text())
        if not verdict['passed'] or verdict['failures']:
            raise ValueError('Recorded native qualification did not pass')
        if not all(row['all_identical'] for row in verdict['exact_replay']):
            raise ValueError('Recorded replay differs')
        if not all(all(row['per_tensor'].values()) for row in verdict['reference_check']):
            raise ValueError('Recorded reference differs')
    if all(att['gates'].values()):
        raise ValueError('This evidence snapshot does not support complete promotion')
    data = json.loads((HERE / 'evidence/pacing-snapshot.json').read_text())
    measured = 0
    for run in data['runs']:
        stats = run.get('statistics')
        if not stats:
            continue
        periods = run['unthrottled_prefix_periods_destination_seq_seconds']
        values = [row[1] for row in periods]
        if any(row[0] < 10 for row in periods):
            raise ValueError('Warmup cutoff differs')
        expected = {'n': len(values), 'median_s': statistics.median(values),
                    'mean_s': statistics.mean(values),
                    'p90_s': sorted(values)[math.ceil(.9 * len(values)) - 1]}
        for key, value in expected.items():
            if not math.isclose(stats[key], value, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError('Statistics differ: ' + run['run_name'] + ':' + key)
        measured += 1
    # Bind public row labels to a specific captured run, never a coincident rate.
    row_sources = {
        'Initial 97-frame stream (117)': ('117', 97, 's117-stream01'),
        '121 frames, fingerprint checks (118b)': ('118b', 121, 's118b-live01'),
        '121 frames, decoder graph (119)': ('119', 121, 's119-live01'),
        '121 frames, display replica (120)': ('120', 121, 's120-live01'),
        '145 frames, eager decoder (121)': ('121', 145, 's121-live01'),
        '145 frames, storage accounting (123b)': ('123b', 145, 's123b-legacy-live01'),
        '145 frames, parallel display (124)': ('124', 145, 's124-live01'),
        '145 frames, GC 60 (125)': ('125', 145, 's125-live01'),
        '145 frames, background scan (126)': ('126', 145, 's126-live01'),
        '145 frames, digest cache (127)': ('127', 145, 's127-live01'),
        '145 frames, idle maintenance (128)': ('128', 145, 's128-live01'),
        '145 frames, atomic evidence (129)': ('129', 145, 's129-live01'),
        '145 frames, text split and cone graph (133b)': ('133b', 145, 's133b-live02'),
        '145 frames, GC 60 — early window': ('135', 145, 's135-live01'),
        '145 frames, GC 10 — early window': ('135', 145, 's135-gc10-live01'),
    }
    public = json.loads((HERE / 'video-measurements.json').read_text())
    seen = set()
    for row in public['rows']:
        if row['period_seconds'] is None:
            if row['samples'] != 0:
                raise ValueError('Unmeasured public row has samples')
            continue
        key = row_sources[row['label']]
        matches = [run for run in data['runs'] if
                   (run['packet'], run['frames'], Path(run['work_dir']).name) == key]
        if len(matches) != 1 or row['label'] in seen:
            raise ValueError('Public measurement run binding is ambiguous')
        run = matches[0]
        if (row['period_seconds'] != round(run['statistics']['median_s'], 4) or
                row['samples'] != run['statistics']['n'] or
                row['new_video_seconds'] != run['new_video_seconds_per_continuation'] or
                row['evidence'] != str((HERE / 'evidence/pacing-snapshot.json').relative_to(ROOT))):
            raise ValueError('Public row differs from its captured run: ' + row['label'])
        seen.add(row['label'])
    if seen != set(row_sources):
        raise ValueError('Expected public measurement rows missing')
    identity = json.loads((HERE / 'identity.json').read_text())
    for packet, expected in identity['packets'].items():
        receipt = json.loads((ROOT / f'experiments/ltx25-b70/data/resume-20261008/continuation{packet}-build.json').read_text())
        if any(receipt[key] != value for key, value in expected.items()):
            raise ValueError('Sealed packet identity differs: ' + packet)
    print(f'PASS: {checked} file hashes; {measured} timing windows; {len(seen)} public measurement rows; native135 exactness and packet135/137 seals.')
    print('Strict promotion remains blocked; this verifies stored evidence, not a fresh host or live device.')


if __name__ == '__main__':
    main()

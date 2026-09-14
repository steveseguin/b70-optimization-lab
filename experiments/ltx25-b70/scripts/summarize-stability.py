#!/usr/bin/env python3
"""Summarize completed bounded requests and passive memory observations."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics


def memory_kib(value):
    fields = value.split()
    scale = {'KiB': 1, 'kB': 1, 'MiB': 1024, 'GiB': 1024 ** 2}
    return float(fields[0]) * scale.get(fields[1] if len(fields) > 1 else 'KiB', 1)


def memory(snapshot):
    status = dict(line.split(':', 1) for line in snapshot['process_status'].splitlines() if ':' in line)
    host = dict(line.split(':', 1) for line in snapshot['host_meminfo'].splitlines() if ':' in line)
    return {'rss_mib': memory_kib(status['VmRSS']) / 1024,
            'swap_mib': memory_kib(status['VmSwap']) / 1024,
            'available_host_mib': memory_kib(host['MemAvailable']) / 1024,
            'vram_mib_by_drm_client': {key: memory_kib(client['fields']['drm-resident-vram0']) / 1024
                                      for key, client in snapshot['drm_clients'].items()
                                      if 'drm-resident-vram0' in client['fields']}}


def distribution(values):
    # Nearest rank, explicit because p95 is sensitive to the small sample count.
    import math
    ordered = sorted(values)
    return {'n': len(values), 'min': min(values), 'median': statistics.median(values),
            'p95_nearest_rank': ordered[math.ceil(.95 * len(values)) - 1], 'max': max(values)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('campaign', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'preserve earlier summaries'
    progress = json.loads((args.campaign / 'progress.json').read_text())
    assert progress['status'] == 'passed' and len(progress['rows']) == 30
    assert progress['all_10_fixtures_exact_repeats']
    rows = []
    for run in progress['rows']:
        loading = []
        for line in run['loading_log_lines']:
            match = re.search(r'([\d.]+) MB loaded, ([\d.]+) MB offloaded, ([\d.]+) MB buffer reserved', line)
            if match:
                value = tuple(map(float, match.groups()))
                if value not in loading:
                    loading.append(value)
            else:
                match = re.search(r'Unloaded partially: [\d.]+ MB freed, ([\d.]+) MB remains loaded, ([\d.]+) MB buffer reserved', line)
                if match:
                    value = (float(match[1]), None, float(match[2]))
                    if value not in loading:
                        loading.append(value)
        assert len(loading) == 1, (run['run'], 'ambiguous encoder load report', loading)
        if 'parity_path' in run:
            comparison = json.loads(Path(run['parity_path']).read_text())
            assert comparison['status'] == 'passed'
            assert all(v['bitwise_equal'] and v['max_abs_diff'] == 0 and v['unequal_values'] == 0
                       for v in comparison['comparisons'].values())
        profile = run['profile']
        rows.append({'run': run['run'], 'fixture': run['fixture'], 'round': run['round'],
                     'preview_seconds': profile['preview_ready_seconds'],
                     'tensor_seconds': profile['tensor_archive_ready_seconds'],
                     'client_seconds': profile['seconds'],
                     'encoder_reported_loaded_mib': loading[0][0],
                     'encoder_reported_offloaded_mib': loading[0][1],
                     'encoder_reported_buffer_mib': loading[0][2],
                     'after': memory(run['after'])})
    retained = progress['retained_outputs']
    assert len(retained) <= 3 and all(row['relative_path'].endswith('.mp4') for row in retained)
    for row in retained:
        path = Path(row['path'])
        assert path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
    receipts = [json.loads(line) for line in (args.campaign / 'deletion-receipts.jsonl').read_text().splitlines()]
    deleted = [r for r in receipts if r['phase'] == 'completed']
    assert len({r['relative_path'] for r in deleted}) == len(deleted)
    assert all(not Path(r['path']).exists() for r in deleted)
    assert sum(r['relative_path'].endswith('.safetensors') for r in deleted) == 30
    first, last = rows[0], rows[-1]
    clients = set(first['after']['vram_mib_by_drm_client'])
    assert all(set(row['after']['vram_mib_by_drm_client']) == clients for row in rows)
    memory_summary = {key: distribution([row['after'][key] for row in rows])
                      for key in ['rss_mib', 'swap_mib', 'available_host_mib']}
    memory_summary['vram_mib_by_drm_client'] = {
        key: {**distribution([row['after']['vram_mib_by_drm_client'][key] for row in rows]),
              'first': first['after']['vram_mib_by_drm_client'][key],
              'last': last['after']['vram_mib_by_drm_client'][key]}
        for key in sorted(clients)}
    summary = {'status': 'exact repeat gate passed; memory interpretation requires source audit',
               'campaign': str(args.campaign), 'rows': rows,
               'preview_seconds': distribution([row['preview_seconds'] for row in rows]),
               'tensor_seconds': distribution([row['tensor_seconds'] for row in rows]),
               'client_seconds': distribution([row['client_seconds'] for row in rows]),
               'per_round_preview_seconds': {str(i): distribution([r['preview_seconds'] for r in rows if r['round'] == i])
                                             for i in [1, 2, 3]},
               'memory': memory_summary,
               'reported_encoder_offload_mib_first_last': [first['encoder_reported_offloaded_mib'], last['encoder_reported_offloaded_mib']],
               'quality': {'fixtures': 10, 'executions': 30, 'repeats_per_fixture': 3,
                           'original_reference_fixtures': 3, 'new_split_reference_fixtures': 7,
                           'independent_pairwise_receipts': sum('parity_path' in r for r in progress['rows'])},
               'retention': {'deleted_files': len(deleted), 'deleted_bytes': sum(r['bytes'] for r in deleted),
                             'retained_preview_files': len(retained), 'retained_preview_bytes': sum(r['bytes'] for r in retained),
                             'retained_campaign_tensor_archives': 0,
                             'original_references': 'untouched'},
               'limitations': ['Short sequential same-process campaign, not continuous streaming or an endurance proof',
                               'The p95 uses nearest rank over30 requests; only10 distinct prompts',
                               'fdinfo exposes driver/client residency, not per-parameter placement or allocator live bytes; shared GTT is not summed',
                               'Candidate patches are not active; this is the unchanged split baseline',
                               'Deleting verified output archives retains evidence hashes, not the ability to reread those deleted bytes']}
    args.output.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k not in ['rows', 'memory']}, indent=2))


if __name__ == '__main__':
    main()

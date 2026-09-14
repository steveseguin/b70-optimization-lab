#!/usr/bin/env python3
"""Preserve the failed native compiler screen and generated textual kernels."""
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
CAMPAIGN = 'compiler-screen-02'
SERVER = 'encoder-server-compiler-03'
OUT = Path(__file__).resolve().parents[1] / 'data' / CAMPAIGN


def main():
    progress = json.loads((ROOT / CAMPAIGN / 'progress.json').read_text())
    assert progress['status'] == 'failed' and len(progress['rows']) == 3
    runs = [row['run'] for row in progress['rows']]
    assert all(row['status'] == 'passed' for row in progress['rows'][:2])
    assert progress['rows'][2]['status'] == 'failed'
    call = json.loads((ROOT / SERVER / ('compiler-' + runs[2]) / 'call-01.json').read_text())
    assert not call['passed'] and not call['stage_check']
    paths = list((ROOT / CAMPAIGN).rglob('*'))
    paths += [ROOT / (CAMPAIGN + '.log'), ROOT / (SERVER + '.log')]
    paths += list((ROOT / SERVER / 'inductor-cache').rglob('*.py'))
    for run in runs:
        paths += list((ROOT / 'requests' / run).rglob('*'))
        paths += list((ROOT / SERVER / ('compiler-' + run)).rglob('*'))
        paths += [ROOT / SERVER / ('encoder-placement-' + run + '.json'),
                  ROOT / 'output/validation' / run / 'summary.json']
    paths += [ROOT / SERVER / name for name in ('server-identity.json', 'server-args.json',
                                               'determinism-after-import.json')]
    text = {}
    for path in sorted(set(paths)):
        if not path.is_file() or path.is_symlink() or path.suffix not in ('.json', '.jsonl', '.log', '.txt', '.py'):
            continue
        assert path.stat().st_size <= 16 * 1024**2, path
        text[str(path.relative_to(ROOT))] = path.read_bytes().decode('utf-8')
    inventory = {name: hashlib.sha256(value.encode()).hexdigest() for name, value in text.items()}
    raw = json.dumps(text, ensure_ascii=False).encode()
    compressed = gzip.compress(raw, mtime=0)
    assert json.loads(gzip.decompress(compressed)) == text
    summary = {'schema': 'ltx25.compiler-native-failure.v1', 'status': 'failed-native-exactness',
               'campaign': CAMPAIGN, 'server_run': SERVER, 'server_pid': 6502,
               'completed_exact_eager_clips': 2, 'compiled_candidate_qualified': False,
               'eager_clips': [{'run': row['run'], 'initialization': row['initialization'],
                                'preview_ready_seconds': row['profile']['preview_ready_seconds'],
                                'client_seconds': row['profile']['seconds']}
                               for row in progress['rows'][:2]],
               'failed_native_call': {key: call[key] for key in ('block_index', 'call', 'stage_signature',
                                                               'eager_vs_compiled', 'failures')},
               'compiled_repeat_tested': False, 'second_stage_tested': False,
               'full_compiled_clip_generated': False, 'candidate_speed_measured': False,
               'counter_delta_recorded': 'counter_delta' in call,
               'queue_after_failure': json.loads((ROOT / CAMPAIGN / 'queue-after-failure.json').read_text()),
               'fault_latch_present_at_export': (ROOT / 'FAULT.json').exists(),
               'exported_text_files': len(text), 'exporter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'evidence_sha256': hashlib.sha256(compressed).hexdigest()}
    OUT.mkdir(exist_ok=False)
    (OUT / 'evidence.json.gz').write_bytes(compressed)
    (OUT / 'inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'status': summary['status'], 'text_files': len(text),
                      'archive_bytes': len(compressed), 'eager_clips': summary['eager_clips']}))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Export completed compiler-screen-03 text evidence without judging its outcome.

Run only after the campaign owner confirms completion. This reads source and
receipts, never contacts the server or imports a native model/runtime library.
Raw tensors, media, compiler binaries and cache metadata are not exported.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import stat

ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
LANE = Path(__file__).resolve().parents[1]
CAMPAIGN = 'compiler-screen-03'
SERVER = 'encoder-server-compiler-04'
OUT = LANE / 'data' / CAMPAIGN
TEXT_SUFFIXES = {'.json', '.jsonl', '.log', '.txt', '.py', '.patch', '.yaml', '.yml', '.toml', '.cfg', '.ini'}
MAX_FILE_BYTES = 16 * 1024**2
MAX_TOTAL_BYTES = 256 * 1024**2


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def read_stable(path):
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'Symlink in evidence path: ' + str(path))
    before = path.stat()
    require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_FILE_BYTES,
            'Evidence file is not regular or exceeds size limit: ' + str(path))
    with path.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        require(identity(opened) == identity(before), 'Evidence replaced before read: ' + str(path))
        raw = stream.read(MAX_FILE_BYTES + 1)
        require(len(raw) == before.st_size and identity(os.fstat(stream.fileno())) == identity(before),
                'Evidence changed during read: ' + str(path))
    return raw, identity(before)


def add_tree(paths, root, suffixes=TEXT_SUFFIXES):
    if not root.exists():
        return
    require(root.is_dir() and not root.is_symlink(), 'Unexpected evidence directory: ' + str(root))
    for path in root.rglob('*'):
        require(not path.is_symlink(), 'Symlink in evidence tree: ' + str(path))
        if path.is_file() and path.suffix in suffixes:
            paths.add(path)


def selected_paths(runs, packet, manifest):
    paths = {ROOT / CAMPAIGN / 'progress.json', ROOT / CAMPAIGN / 'preregistration.json',
             ROOT / SERVER / 'server-identity.json', ROOT / SERVER / 'server-args.json',
             ROOT / SERVER / 'determinism-after-import.json', packet / 'manifest.json'}
    add_tree(paths, ROOT / CAMPAIGN)
    # Include every direct identity/component/placement/journal receipt and log.
    for path in (ROOT / SERVER).iterdir():
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            paths.add(path)
    for name in (CAMPAIGN + '.log', CAMPAIGN + '-client.log', SERVER + '.log', 'FAULT.json'):
        if (ROOT / name).exists():
            paths.add(ROOT / name)
    add_tree(paths, ROOT / SERVER / 'native-rms-graphs')
    # Preserve generated source, never binary artifacts or cache serialization.
    for cache in ('inductor-cache', 'triton-cache'):
        add_tree(paths, ROOT / SERVER / cache, {'.py'})
    for run in runs:
        add_tree(paths, ROOT / 'requests' / run)
        add_tree(paths, ROOT / SERVER / ('compiler-' + run))
        summary = ROOT / 'output/validation' / run / 'summary.json'
        if summary.exists():
            paths.add(summary)
    # Preserve the sealed source/config/patch closure, including before/after
    # provenance. Only inventoried text formats are selected; never weights.
    for name in manifest['files']:
        relative = Path(name)
        require(not relative.is_absolute() and '..' not in relative.parts, 'Unsafe manifest path')
        if relative.suffix in TEXT_SUFFIXES:
            paths.add(packet / relative)
    for name in ('run-compiler-screen-v3.py', 'run-compiler-screen-v2.py', 'run-compiler-screen.py',
                 'run-encoder-screen.py', 'compare-clip.py', 'profile-clip.py', 'run-stability.py',
                 'export-compiler-screen-03.py'):
        paths.add(LANE / 'scripts' / name)
    return paths


def archive_name(path):
    if path.is_relative_to(ROOT):
        return str(path.relative_to(ROOT))
    require(path.is_relative_to(LANE), 'Evidence outside approved roots')
    return 'repository/experiments/ltx25-b70/' + str(path.relative_to(LANE))


def main():
    require(not OUT.exists() and not OUT.is_symlink(), 'Export already exists; never overwrite')
    progress_raw, _ = read_stable(ROOT / CAMPAIGN / 'progress.json')
    progress = json.loads(progress_raw)
    require(progress.get('status') in ('passed', 'failed'), 'Campaign is not finalized; do not export a running campaign')
    prereg_raw, _ = read_stable(ROOT / CAMPAIGN / 'preregistration.json')
    prereg = json.loads(prereg_raw)
    require(prereg['campaign'] == CAMPAIGN, 'Campaign preregistration differs')
    rows = progress['rows']
    require(isinstance(rows, list) and isinstance(prereg['schedule'], list), 'Invalid campaign rows')
    planned = [row['run'] for row in prereg['schedule']]
    attempted = [row['run'] for row in rows]
    require(len(planned) == len(set(planned)) and len(attempted) == len(set(attempted)), 'Duplicate run identities')
    require(all(isinstance(run, str) and re.fullmatch(r'compiler-screen-03-r[0-9]{2}-[a-z0-9-]+', run)
                for run in planned) and attempted == planned[:len(attempted)], 'Unexpected campaign schedule/order')
    runs = planned  # Include any partial request artifacts even if no row was committed.
    server_raw, _ = read_stable(ROOT / SERVER / 'server-identity.json')
    server = json.loads(server_raw)
    require(server['encoder_run_dir'] == str(ROOT / SERVER), 'Server identity path differs')
    packet = Path(server['source_packet_path'])
    require(packet.parent == ROOT and re.fullmatch(r'prepared-encoder-compiler-[a-z0-9-]+', packet.name),
            'Unexpected source packet path')
    manifest_raw, _ = read_stable(packet / 'manifest.json')
    require(hashlib.sha256(manifest_raw).hexdigest() == server['source_packet_manifest_sha256'],
            'Server source manifest hash differs')
    manifest = json.loads(manifest_raw)
    paths = selected_paths(runs, packet, manifest)
    text, file_identities, total = {}, {}, 0
    for path in sorted(paths):
        raw, file_identities[path] = read_stable(path)
        total += len(raw)
        require(total <= MAX_TOTAL_BYTES, 'Text export exceeds bounded total size')
        text[archive_name(path)] = raw.decode('utf-8')
        if path.is_relative_to(packet) and path != packet / 'manifest.json':
            relative = str(path.relative_to(packet))
            require(hashlib.sha256(raw).hexdigest() == manifest['files'][relative],
                    'Inventoried packet source changed: ' + relative)
    require(text[archive_name(ROOT / CAMPAIGN / 'progress.json')].encode() == progress_raw
            and text[archive_name(ROOT / CAMPAIGN / 'preregistration.json')].encode() == prereg_raw
            and text[archive_name(ROOT / SERVER / 'server-identity.json')].encode() == server_raw,
            'Campaign identity/status changed while collecting evidence')
    client_key = archive_name(LANE / 'scripts/run-compiler-screen-v3.py')
    require(hashlib.sha256(text[client_key].encode()).hexdigest() == prereg['client_sha256'],
            'Campaign client source differs from preregistration')
    inventory = {name: hashlib.sha256(value.encode()).hexdigest() for name, value in text.items()}
    raw_bundle = json.dumps(text, ensure_ascii=False).encode()
    compressed = gzip.compress(raw_bundle, mtime=0)
    require(json.loads(gzip.decompress(compressed)) == text, 'Archive round-trip failed')
    require(paths == selected_paths(runs, packet, manifest), 'Evidence file set changed; export is incomplete')
    for path, before in file_identities.items():
        require(not path.is_symlink() and identity(path.stat()) == before, 'Evidence changed before sealing: ' + str(path))
    counts = {}
    for row in rows:
        mode = row.get('mode', 'unknown')
        status = row.get('status', 'unreported')
        counts.setdefault(mode, {})[status] = counts.setdefault(mode, {}).get(status, 0) + 1
    summary = {'schema': 'ltx25.compiler-native-export.v1', 'status': progress['status'],
               'status_scope': 'Copied final campaign status; exporter does not rerun qualification gates',
               'campaign': CAMPAIGN, 'server_run': SERVER, 'server_pid': server['pid'],
               'server_boot_id': server['boot_id'], 'source_packet': str(packet),
               'source_packet_manifest_sha256': server['source_packet_manifest_sha256'],
               'planned_requests': len(planned), 'recorded_requests': len(rows),
               'reported_row_counts': counts, 'failure_stage': progress.get('failure_stage'),
               'reported_error': progress.get('error'), 'qualification_recomputed': False,
               'speed_promotion': False, 'streaming_qualification': False,
               'request_profiles': [{'run': row['run'], 'mode': row.get('mode'),
                    'status': row.get('status'), 'initialization': row.get('initialization'),
                    'profile': row.get('profile'), 'parity_path': row.get('parity_path')} for row in rows],
               'fault_latch_present_at_export': (ROOT / 'FAULT.json').exists(),
               'exported_text_files': len(text), 'source_text_bytes': total,
               'archive_bytes': len(compressed), 'max_file_bytes': MAX_FILE_BYTES,
               'max_total_source_bytes': MAX_TOTAL_BYTES,
               'excluded': ['raw tensors', 'media', 'compiler/cache binaries and serialized cache metadata'],
               'exporter_sha256': inventory[archive_name(Path(__file__).resolve())],
               'evidence_sha256': hashlib.sha256(compressed).hexdigest()}
    OUT.mkdir(exist_ok=False)
    with (OUT / 'evidence.json.gz').open('xb') as stream:
        stream.write(compressed)
    for name, value in (('inventory.json', inventory), ('summary.json', summary)):
        with (OUT / name).open('x') as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write('\n')
    print(json.dumps({'status': summary['status'], 'text_files': len(text),
                      'archive_bytes': len(compressed), 'output': str(OUT)}))


if __name__ == '__main__':
    main()

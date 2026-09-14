#!/usr/bin/env python3
"""Export terminal packet10 NA confirmation text evidence; never run models or clients.

The campaign owner runs this only after the client is terminal. Any ongoing
server log mutation makes the export refuse sealing, not retry.
No raw tensor/media/weight files, whole Comfy tree, or binary cache is copied.
"""
import argparse
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import statistics

ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
LANE = Path(__file__).resolve().parents[1]
REPO = LANE.parents[1]
PACKET = ROOT / 'prepared-encoder-na-axis-10'
SERVER = ROOT / 'encoder-server-na-axis-10'
PACKET_SHA = 'd6ec6c63869d30dbe009708095f53811372e228becf16b7475ad30d11213fe6a'
CLIENT_SHA = '265c0925b9bf04bc53a7653b7bbcdde991b0a32fe2c887c1dfd6a9e48f5df22b'
ADMISSION_SHA = '2ee3f7d064454137a4192370cbf4e86247cbc5dd9f79c8c3de59cb9380210e0a'
VALIDATOR_SHA = 'ac11e8fc95275660d76336cafd892a6ec67e0c4f68b0208f5752a328b254274c'
CAMPAIGN = 'na-axis-confirm-01'
PRIOR_CAMPAIGN = 'na-axis-screen-01'
PRIOR_CLIENT_SHA = '28fd569ab0acecb10a9b59821a707eb917d80bb013bdb973d046a8e6ad074988'
PRIOR_PROGRESS_SHA = 'a0da72e9a1a85086b41bb02c66e9eda63401a649b5795e0a63e46deceb244568'
PRIOR_EXPORT = LANE / 'data/na-axis-screen-01-export'
PRIOR_ARCHIVE_SHA = 'c8b0cf80eab96efbec59023df2a0d9d36a57d69a9d9bcc123fc31e6aa3109e07'
PRIOR_EXPORT_PINS = {
    'summary.json': '691ebdbb96a3c99edc3f6d4ffbb6219275d730610e849982ccf76c74640bb06a',
    'manifest.json': '9df6a58b55c8878eda58d3abd3bd8112fb38b7cb6d8e80d7f08aea4633f7f230',
}
BLOCKS = (('boat', 'OCO'), ('marble', 'COC'), ('bird', 'OCO'),
          ('bird', 'COC'), ('marble', 'OCO'), ('boat', 'COC'))
KITCHEN = Path('/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/comfy_kitchen')
REFERENCES = ('baseline-01', 'speed-oracle-marble', 'speed-oracle-bird')
HELPERS = {
    'run-na-axis-confirm.py': CLIENT_SHA,
    'ltx_na_axis_confirmation.py': ADMISSION_SHA,
    'run-na-axis-screen-v2.py': PRIOR_CLIENT_SHA,
    'export-na-axis-screen.py': '602776b0859eceedfc8e2cccdaaff44feb66edbe66c8cdeeb8d8f673d9862f81',
    'ltx_na_axis_receipts.py': VALIDATOR_SHA,
    'run-multiblock-screen-v3.py': 'd8054e9866dfb314a5df37415811a5d4a5db79828b0494cca5f3526884ee3114',
    'run-encoder-screen.py': '4ec94d7e69c3d93b2caa740209f6a84ff35d56bdbbb8bf55f4b9782bacde10b0',
    'profile-clip.py': 'ad0141ff493c8c4cc5993ff4f8c2aceea76c2e99359477c7cef2d24628eb1980',
    'compare-clip.py': '80ee7a45468f95c6c0b8df9ecceea338af9fdf4d2537ba5966603b4f5b03fe0e',
    'run-stability.py': '7769cf87ed005be6e13dc6acced399f1541f68bc988953e7a409ba7fb80937b2',
}
TEXT_SUFFIXES = {'.json', '.jsonl', '.log', '.txt', '.py', '.patch', '.yaml', '.yml'}
OUTPUTS = {'images', 'video_latent', 'audio_latent', 'waveform'}
MAX_FILE_BYTES = 64 * 1024**2  # Progress embeds many block receipts.
MAX_TOTAL_BYTES = 256 * 1024**2
MAX_SCAN_ENTRIES = 8192


def require(value, message):
    if not value:
        raise RuntimeError(message)


def identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def safe(path):
    path = Path(path).absolute()
    require('..' not in path.parts and not any(p.is_symlink() for p in (path, *path.parents)),
            'Unsafe/symlink evidence path: ' + str(path))
    return path


def read_stable(path, limit=MAX_FILE_BYTES):
    path = safe(path)
    before = path.stat()
    require(stat.S_ISREG(before.st_mode) and before.st_size <= limit,
            'Not regular or exceeds file bound: ' + str(path))
    with path.open('rb') as stream:
        require(identity(os.fstat(stream.fileno())) == identity(before), 'Evidence replaced before read')
        raw = stream.read(limit + 1)
        require(len(raw) == before.st_size and identity(os.fstat(stream.fileno())) == identity(before),
                'Evidence changed during read: ' + str(path))
    require(identity(safe(path).stat()) == identity(before), 'Evidence path replaced during read')
    return raw, identity(before)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def unique_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON evidence key')
            result[key] = value
        return result
    def invalid_constant(value):
        raise RuntimeError('Nonfinite JSON evidence constant: ' + value)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)


def add_tree(paths, root):
    root = safe(root)
    if not root.exists():
        return
    require(root.is_dir(), 'Evidence tree is not a directory')
    for index, path in enumerate(root.rglob('*'), 1):
        require(index <= MAX_SCAN_ENTRIES, 'Evidence tree exceeds scan bound')
        safe(path)
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            paths.add(path)
            require(len(paths) <= MAX_SCAN_ENTRIES, 'Evidence inventory exceeds file bound')


def archive_name(path):
    path = safe(path)
    if path.is_relative_to(ROOT):
        return str(path.relative_to(ROOT))
    if path.is_relative_to(KITCHEN):
        return 'installed/comfy_kitchen/' + str(path.relative_to(KITCHEN))
    require(path.is_relative_to(LANE), 'Source outside approved evidence roots')
    return 'repository/experiments/ltx25-b70/' + str(path.relative_to(LANE))


def selected_paths(campaign, runs, manifest, prior_bindings):
    paths = {ROOT / campaign / 'progress.json', ROOT / campaign / 'preregistration.json',
             SERVER / 'server-identity.json', SERVER / 'server-args.json',
             SERVER / 'determinism-after-import.json', PACKET / 'manifest.json'}
    add_tree(paths, ROOT / campaign)
    add_tree(paths, ROOT / PRIOR_CAMPAIGN)
    add_tree(paths, ROOT / 'na-axis-migration-10')
    paths.add(ROOT / 'model-verification.json')
    for path in SERVER.iterdir():
        safe(path)
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            paths.add(path)
    for name in (campaign + '.log', campaign + '-client.log', SERVER.name + '.log', 'FAULT.json'):
        path = safe(ROOT / name)
        if path.exists():
            paths.add(path)
    for run in (*runs, *REFERENCES):
        add_tree(paths, ROOT / 'requests' / run)
        if run in runs:
            add_tree(paths, SERVER / ('na-axis-' + run))
        summary = safe(ROOT / 'output/validation' / run / 'summary.json')
        if summary.exists():
            paths.add(summary)
    # Preserve the small reviewed extension/startup/graph/patch closure only.
    # The complete manifest pins the remaining Comfy sources without copying them.
    core = {'source/nodes.py', 'source/comfy/sd.py',
            'source/comfy/ldm/lightricks/vae/na_diffusion_decoder.py'}
    scripts = {'source/scripts/' + name for name in manifest['extension_sha256s']}
    for name in manifest['files']:
        relative = Path(name)
        require(not relative.is_absolute() and '..' not in relative.parts, 'Unsafe manifest entry')
        selected = (name in core or name in scripts or name == 'model-paths.yaml' or
                    name.startswith(('launch/', 'graphs/', 'patches/', 'provenance/')) or
                    name.endswith('-parent-manifest.json') or
                    (name.startswith('source/custom_nodes/ltx_') and name.endswith('/__init__.py')))
        if selected and relative.suffix in TEXT_SUFFIXES:
            paths.add(PACKET / name)
    for name in (*HELPERS, 'export-na-axis-confirm.py'):
        paths.add(LANE / 'scripts' / name)
    for name in manifest['na_axis']['dependencies']:
        path = safe(name)
        require(path.is_relative_to(KITCHEN) and path.suffix == '.py', 'Unexpected installed source dependency')
        paths.add(path)
    paths.add(LANE / 'data/speed-resident-split-api.json')
    for relative in prior_bindings:
        relative = Path(relative)
        require(not relative.is_absolute() and relative.parts and '..' not in relative.parts
                and relative.suffix in TEXT_SUFFIXES, 'Unsafe/nontext prior admission evidence path')
        paths.add(safe(ROOT / relative))
    paths.update(PRIOR_EXPORT / name for name in PRIOR_EXPORT_PINS)
    require(len(paths) <= MAX_SCAN_ENTRIES, 'Evidence inventory exceeds file bound')
    return paths


def parsed_optional(text, path):
    name = archive_name(path)
    if name not in text:
        return None
    try:
        value = unique_json(text[name])
        return value if isinstance(value, dict) else {'export_parse_error': 'Expected JSON object'}
    except (ValueError, RuntimeError) as error:
        return {'export_parse_error': repr(error)}


def parity_summary(text, campaign, row):
    path = ROOT / campaign / (row['run'] + '-parity.json')
    parity = parsed_optional(text, path)
    comparisons = parity.get('comparisons', {}) if isinstance(parity, dict) else {}
    comparisons = comparisons if isinstance(comparisons, dict) else {}
    profile = parsed_optional(text, ROOT / 'requests' / row['run'] / 'profile.json')
    exact = (isinstance(parity, dict) and parity.get('status') == 'passed' and
             set(comparisons) == OUTPUTS and all(isinstance(v, dict) and v.get('bitwise_equal') is True
                                                 for v in comparisons.values()))
    decoder_path = SERVER / ('na-axis-' + row['run']) / 'result.json'
    decoder = parsed_optional(text, decoder_path)
    route = decoder.get('route') if isinstance(decoder, dict) else None
    return {'run': row['run'], 'mode': row.get('mode'), 'fixture': row.get('fixture'),
            'pair': row.get('pair'), 'order': row.get('order'),
            'status': row.get('status'), 'initialization': row.get('initialization'),
            'parity_status': parity.get('status') if isinstance(parity, dict) else None,
            'reported_all_four_outputs_exact': exact, 'comparisons': comparisons,
            'parity_parse_error': parity.get('export_parse_error') if isinstance(parity, dict) else None,
            'parity_path': archive_name(path) if parity is not None else None,
            'profile': profile, 'timings': timing_values(profile),
            'decoder_receipt_path': archive_name(decoder_path) if decoder is not None else None,
            'reported_decoder_status': decoder.get('status') if isinstance(decoder, dict) else None,
            'reported_na_call_count': len(route['calls']) if isinstance(route, dict) and isinstance(route.get('calls'), list) else None,
            'capture_summary': parsed_optional(text, ROOT / 'output/validation' / row['run'] / 'summary.json')}


def timing_values(profile):
    """Approximate client-event intervals/readiness, never kernel timings."""
    if not isinstance(profile, dict):
        return {}
    values = {key: profile.get(key) for key in ('preview_ready_seconds', 'tensor_archive_ready_seconds')}
    nodes = profile.get('nodes', [])
    nodes = nodes if isinstance(nodes, list) else []
    for metric, ids in (('sampler_intervals_seconds', {'344', '368'}),
                        ('text_encoder_interval_seconds', {'364'}),
                        ('video_decoder_interval_seconds', {'374'}),
                        ('audio_decoder_interval_seconds', {'358'})):
        selected = [n for n in nodes if isinstance(n, dict) and str(n.get('node')) in ids]
        values[metric] = (sum(n['seconds'] for n in selected) if
            {str(n.get('node')) for n in selected} == ids and
            all(type(n.get('seconds')) in (int, float) and math.isfinite(n['seconds']) and
                n['seconds'] >= 0 for n in selected) else None)
    return {key: value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None
            for key, value in values.items()}


def expected_schedule(campaign):
    rows = []
    for block, (fixture, order) in enumerate(BLOCKS):
        for letter in order:
            mode = 'original' if letter == 'O' else 'axis-cache'
            rows.append({'mode': mode, 'fixture': fixture, 'pair': f'{block+1:02d}-{fixture}-{order.lower()}',
                'order': order, 'initialization': False,
                'run': f'{campaign}-r{len(rows)+1:02d}-{mode}-{fixture}'})
    return rows


def terminal_rows(progress, prereg, campaign):
    require(all(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value)
                for value in (CLIENT_SHA, ADMISSION_SHA)), 'Confirmation exporter is not pinned')
    require(isinstance(progress, dict) and isinstance(prereg, dict), 'Invalid campaign documents')
    require(progress.get('status') in ('passed', 'failed'), 'Campaign is not terminal; do not export')
    require(prereg.get('campaign') == campaign and prereg.get('packet_manifest_sha256') == PACKET_SHA and
            prereg.get('client_sha256') == CLIENT_SHA and prereg.get('validator_sha256') == VALIDATOR_SHA,
            'Campaign source identity differs from the reviewed packet10 client')
    require(prereg.get('max_requests') == 18 and prereg.get('prior_client_sha256') == PRIOR_CLIENT_SHA and
            prereg.get('admission_helper_sha256') == ADMISSION_SHA, 'Confirmation admission identity differs')
    require(prereg.get('inherited_v3_sha256') == HELPERS['run-multiblock-screen-v3.py'] and
            prereg.get('frozen_helpers') == {name: HELPERS[name] for name in
                ('profile-clip.py', 'compare-clip.py', 'run-stability.py')}, 'Frozen helper identity differs')
    schedule, rows = prereg.get('schedule'), progress.get('rows')
    require(schedule == expected_schedule(campaign) and isinstance(rows, list), 'Invalid bounded schedule')
    require(len(rows) <= len(schedule) and all(isinstance(row, dict) for row in rows), 'Invalid attempted rows')
    for row, plan in zip(rows, schedule):
        require(all(row.get(key) == value for key, value in plan.items()), 'Recorded request differs from plan')
    if progress['status'] == 'passed':
        require(len(rows) == 18 and progress.get('completed_requests') == 18 and
                all(row.get('status') == 'passed' for row in rows), 'Incomplete passed campaign')
    return schedule, rows


def paired_results(rows, output_rows):
    by_run = {row['run']: row for row in output_rows}
    triples = []
    for block, (fixture, order) in enumerate(BLOCKS):
        pair = f'{block+1:02d}-{fixture}-{order.lower()}'
        chosen = [row for row in rows if row.get('pair') == pair]
        modes = ['original' if letter == 'O' else 'axis-cache' for letter in order]
        if (len(chosen) != 3 or [r.get('mode') for r in chosen] != modes or
                any(r.get('order') != order for r in chosen) or
                any(r.get('status') != 'passed' or r.get('initialization') is not False or
                    not by_run[r['run']]['reported_all_four_outputs_exact'] for r in chosen)):
            continue
        metrics = {}
        for metric in ('preview_ready_seconds', 'tensor_archive_ready_seconds', 'video_decoder_interval_seconds'):
            samples = [by_run[row['run']]['timings'].get(metric) for row in chosen]
            if not all(type(t) in (int, float) and math.isfinite(t) and t > 0 for t in samples):
                continue
            original = (samples[0] + samples[2]) / 2 if order == 'OCO' else samples[1]
            cached = samples[1] if order == 'OCO' else (samples[0] + samples[2]) / 2
            metrics[metric] = {'samples_seconds': samples, 'original_mean_seconds': original,
                'cache_mean_seconds': cached, 'cache_minus_original_seconds': cached - original,
                'original_mean_over_cache_mean': original / cached}
        triples.append({'fixture': fixture, 'order': order, 'pair': pair,
                        'runs': [r['run'] for r in chosen], 'metrics': metrics})
    metric_names = ('preview_ready_seconds', 'tensor_archive_ready_seconds', 'video_decoder_interval_seconds')
    fixture_means = {}
    for fixture in ('boat', 'marble', 'bird'):
        chosen = [row for row in triples if row['fixture'] == fixture]
        if len(chosen) == 2 and {row['order'] for row in chosen} == {'OCO', 'COC'}:
            fixture_means[fixture] = {metric: statistics.mean(row['metrics'][metric]['cache_minus_original_seconds']
                for row in chosen) for metric in metric_names if all(metric in row['metrics'] for row in chosen)}
    return {'paired_samples': len(triples), 'triples': triples,
        'fixture_mean_cache_minus_original_seconds': fixture_means,
        'metric_summaries': {metric: {'paired_samples': len(values),
            'median_cache_minus_original_seconds': statistics.median(values) if values else None}
            for metric in metric_names
            for values in [[row['metrics'][metric]['cache_minus_original_seconds']
                            for row in triples if metric in row['metrics']]]},
        'scope': 'Copied parity report status and client-event intervals; screening only, no qualification recomputed'}


def prior_admission_bindings(prereg, server):
    admission = prereg.get('prior_screen_admission')
    require(isinstance(admission, dict) and admission.get('status') == 'completed-screen-admitted' and
            admission.get('prior_campaign') == PRIOR_CAMPAIGN and admission.get('progress_sha256') == PRIOR_PROGRESS_SHA and
            admission.get('identity') == server and admission.get('prior_requests') == 11 and
            admission.get('prior_scoped_decodes') == 9, 'Prior screen admission identity differs')
    bindings = admission.get('evidence_sha256s')
    require(isinstance(bindings, dict) and 1 <= len(bindings) <= MAX_SCAN_ENTRIES and
            bindings.get(PRIOR_CAMPAIGN + '/progress.json') == PRIOR_PROGRESS_SHA,
            'Missing prior admission evidence binding')
    for name, checksum in bindings.items():
        relative = Path(name)
        require(not relative.is_absolute() and relative.parts and '..' not in relative.parts
                and relative.suffix in TEXT_SUFFIXES and isinstance(checksum, str)
                and re.fullmatch(r'[0-9a-f]{64}', checksum), 'Unsafe prior evidence binding')
    return bindings


def verify_prior_text(prereg, server, text):
    bindings = prior_admission_bindings(prereg, server)
    for name, checksum in bindings.items():
        require(digest(text[archive_name(ROOT / name)].encode('utf-8')) == checksum,
                'Prior admitted evidence changed: ' + name)
    for name, checksum in PRIOR_EXPORT_PINS.items():
        require(digest(text[archive_name(PRIOR_EXPORT / name)].encode('utf-8')) == checksum,
                'Prior screen export evidence changed: ' + name)
    summary = unique_json(text[archive_name(PRIOR_EXPORT / 'summary.json')])
    prior_manifest = unique_json(text[archive_name(PRIOR_EXPORT / 'manifest.json')])
    require(summary['status'] == 'passed' and summary['campaign'] == PRIOR_CAMPAIGN and
            summary['packet_manifest_sha256'] == PACKET_SHA and summary['server_pid'] == server['pid'] and
            summary['server_boot_id'] == server['boot_id'] and summary['evidence_sha256'] == PRIOR_ARCHIVE_SHA and
            prior_manifest['archive'] == 'evidence.json.gz' and prior_manifest['archive_sha256'] == PRIOR_ARCHIVE_SHA,
            'Prior export archive/process identity differs')
    return {'campaign': PRIOR_CAMPAIGN, 'progress_sha256': PRIOR_PROGRESS_SHA,
            'admission_bound_text_files': len(bindings), 'export_text_sha256s': PRIOR_EXPORT_PINS,
            'archive_path': archive_name(PRIOR_EXPORT / 'evidence.json.gz'),
            'archive_sha256': PRIOR_ARCHIVE_SHA, 'archive_included': False,
            'scope': 'Prior raw comparison receipts remain evidence; deleted raw archives are not regenerated'}


def export(campaign, output):
    require(isinstance(campaign, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', campaign), 'Unsafe campaign')
    require(campaign == CAMPAIGN, 'Exporter requires preregistered na-axis-confirm-01')
    output = safe(output)
    require(output.is_relative_to(REPO) and output != REPO and output.parent.is_dir() and
            not output.exists(), 'Use a new export directory under the repository')
    progress_raw, _ = read_stable(ROOT / campaign / 'progress.json')
    prereg_raw, _ = read_stable(ROOT / campaign / 'preregistration.json')
    progress, prereg = unique_json(progress_raw), unique_json(prereg_raw)
    schedule, rows = terminal_rows(progress, prereg, campaign)
    planned = [row['run'] for row in schedule]
    server_raw, _ = read_stable(SERVER / 'server-identity.json')
    server = unique_json(server_raw)
    require(server.get('encoder_run_dir') == str(SERVER) and server.get('source_packet_path') == str(PACKET) and
            server.get('source_packet_manifest_sha256') == PACKET_SHA and prereg.get('identity') == server,
            'Campaign/server/packet binding changed')
    prior_bindings = prior_admission_bindings(prereg, server)
    manifest_raw, _ = read_stable(PACKET / 'manifest.json')
    require(digest(manifest_raw) == PACKET_SHA, 'Pinned packet manifest changed')
    manifest = unique_json(manifest_raw)
    require(manifest['schema'] == 'ltx.na-axis-runtime-packet.v2', 'Unexpected packet schema')
    paths = selected_paths(campaign, planned, manifest, prior_bindings)
    text, stable, total = {}, {}, 0
    prior_archive = safe(PRIOR_EXPORT / 'evidence.json.gz')
    prior_archive_raw, stable[prior_archive] = read_stable(prior_archive)
    require(digest(prior_archive_raw) == PRIOR_ARCHIVE_SHA, 'Prior archive hash changed')
    for path in sorted(paths):
        raw, stable[path] = read_stable(path)
        total += len(raw)
        require(total <= MAX_TOTAL_BYTES, 'Text export exceeds bounded total size')
        text[archive_name(path)] = raw.decode('utf-8')
        if path.is_relative_to(PACKET) and path != PACKET / 'manifest.json':
            require(digest(raw) == manifest['files'][str(path.relative_to(PACKET))], 'Packet source changed')
        if path.is_relative_to(KITCHEN):
            require(digest(raw) == manifest['na_axis']['dependencies'][str(path)], 'Installed source dependency changed')
    for path, raw in ((ROOT / campaign / 'progress.json', progress_raw),
                      (ROOT / campaign / 'preregistration.json', prereg_raw),
                      (SERVER / 'server-identity.json', server_raw), (PACKET / 'manifest.json', manifest_raw)):
        require(text[archive_name(path)].encode() == raw, 'Terminal identity changed during export')
    for name, expected in HELPERS.items():
        require(digest(text[archive_name(LANE / 'scripts' / name)].encode()) == expected, 'Reviewed exporter dependency changed')
    prior_evidence = verify_prior_text(prereg, server, text)
    inventory = {name: digest(value.encode()) for name, value in text.items()}
    output_rows = [parity_summary(text, campaign, row) for row in rows]
    require(all(row['status'] != 'passed' or row['reported_all_four_outputs_exact'] for row in output_rows),
            'A passed request lacks its original four-output parity report')
    raw_bundle = json.dumps(text, ensure_ascii=False).encode()
    compressed = gzip.compress(raw_bundle, mtime=0)
    require(unique_json(gzip.decompress(compressed)) == text, 'Archive round-trip failed')
    require(paths == selected_paths(campaign, planned, manifest, prior_bindings), 'Evidence file set/source changed during export')
    for path, before in stable.items():
        require(identity(safe(path).stat()) == before, 'Evidence changed before sealing: ' + str(path))
    summary = {'schema': 'ltx25.na-axis-confirmation-terminal-export.v1', 'status': progress['status'],
        'status_scope': 'Copied terminal campaign status, with preserved parity reports; native qualification not rerun',
        'campaign': campaign, 'server_run': SERVER.name, 'server_pid': server['pid'],
        'server_boot_id': server['boot_id'], 'source_packet': str(PACKET), 'packet_manifest_sha256': PACKET_SHA,
        'client_sha256': CLIENT_SHA, 'validator_sha256': VALIDATOR_SHA,
        'admission_helper_sha256': ADMISSION_SHA, 'prior_screen': prior_evidence,
        'startup_tools_sha256': manifest['startup_tools'],
        'extension_sha256s': manifest['extension_sha256s'],
        'exporter_sha256': inventory[archive_name(Path(__file__).resolve())],
        'startup_log_pins': {name: value for name, value in inventory.items() if
            (name.startswith(SERVER.name + '/') and '/' not in name[len(SERVER.name) + 1:]) or
            name in (SERVER.name + '.log', campaign + '.log', campaign + '-client.log')},
        'planned_requests': len(planned), 'recorded_requests': len(rows),
        'failure_stage': progress.get('failure_stage'), 'reported_error': progress.get('error'),
        'requests': output_rows, 'paired_results': paired_results(rows, output_rows),
        'reported_paired_results': progress.get('paired_results'),
        'source_pin_closure': manifest['na_axis']['source_pin_closure'],
        'correction_provenance': manifest['na_axis_correction'],
        'qualification_recomputed': False, 'speed_promotion': False, 'streaming_qualification': False,
        'fault_latch_present_at_export': 'FAULT.json' in text or SERVER.name + '/FAULT.json' in text,
        'exported_text_files': len(text), 'source_text_bytes': total, 'archive_bytes': len(compressed),
        'evidence_sha256': digest(compressed), 'max_file_bytes': MAX_FILE_BYTES,
        'max_total_source_bytes': MAX_TOTAL_BYTES, 'max_scan_entries': MAX_SCAN_ENTRIES,
        'excluded': ['raw weights', 'raw tensor archives', 'video/images/audio', 'whole Comfy tree',
                     'binary/serialized/generated caches']}
    output.mkdir(exist_ok=False)
    with (output / 'evidence.json.gz').open('xb') as stream:
        stream.write(compressed)
    export_manifest = {'schema': 'ltx25.text-evidence-archive.v1', 'archive': 'evidence.json.gz',
        'archive_sha256': digest(compressed), 'archive_bytes': len(compressed),
        'encoding': 'gzip of a UTF-8 JSON object mapping archive-relative paths to exact source text',
        'files': {name: {'sha256': checksum, 'bytes': len(text[name].encode('utf-8'))}
                  for name, checksum in inventory.items()},
        'qualification_recomputed': False}
    for name, value in (('inventory.json', inventory), ('manifest.json', export_manifest), ('summary.json', summary)):
        with (output / name).open('x') as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write('\n')
    return {'status': summary['status'], 'output': str(output), 'files': len(text),
            'archive_bytes': len(compressed), 'evidence_sha256': summary['evidence_sha256']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.campaign, args.output), indent=2))

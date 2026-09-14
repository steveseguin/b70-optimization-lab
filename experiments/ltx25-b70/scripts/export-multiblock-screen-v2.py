#!/usr/bin/env python3
"""Export terminal packet07 campaign text evidence; never run models or clients.

The campaign owner runs this only after the client is terminal. Any ongoing
server compilation/log mutation makes the export refuse sealing, not retry.
No raw tensor/media/weight files, whole Comfy tree, or binary cache is copied.
"""
import argparse
import ast
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
PACKET = ROOT / 'prepared-encoder-compiler-07'
SERVER = ROOT / 'encoder-server-compiler-07'
PACKET_SHA = 'afdbad186a6873a286f93e9d1e715f6bf4c17e1552d75dbce2a3e03c0a1f35c1'
CLIENT_SHA = 'dfb1ed9a8875173e644aecf17068f7b244fbcc02ce4264a76c2aa1ed279b8945'
VALIDATOR_SHA = '2eb5cfe0a719d41b5d240b9f2b5fe68bc6c3816874de3f18f8ace527914e22dd'
CAMPAIGN = 'multiblock-screen-02'
SELECTIONS = {'all48': tuple(range(48))}
TEXT_SUFFIXES = {'.json', '.jsonl', '.log', '.txt', '.py', '.patch', '.yaml', '.yml'}
OUTPUTS = {'images', 'video_latent', 'audio_latent', 'waveform'}
MAX_FILE_BYTES = 64 * 1024**2  # Progress embeds many block receipts.
MAX_TOTAL_BYTES = 256 * 1024**2
MAX_GENERATED_FILE_BYTES = 8 * 1024**2
MAX_GENERATED_TOTAL_BYTES = 64 * 1024**2
MAX_GENERATED_SCAN_FILES = 8192


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
    return json.loads(raw, object_pairs_hook=pairs)


def add_tree(paths, root):
    root = safe(root)
    if not root.exists():
        return
    require(root.is_dir(), 'Evidence tree is not a directory')
    for path in root.rglob('*'):
        safe(path)
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            paths.add(path)


def archive_name(path):
    path = safe(path)
    if path.is_relative_to(ROOT):
        return str(path.relative_to(ROOT))
    require(path.is_relative_to(LANE), 'Source outside approved evidence roots')
    return 'repository/experiments/ltx25-b70/' + str(path.relative_to(LANE))


def generated_sources():
    """Select only emitted Python wrappers with actual opaque RMS call syntax."""
    cache = safe(SERVER / 'inductor-cache')
    selected, records, scanned, total = set(), [], 0, 0
    if not cache.exists():
        return selected, records
    for path in sorted(cache.rglob('*.py')):
        scanned += 1
        require(scanned <= MAX_GENERATED_SCAN_FILES, 'Generated Python scan exceeded file bound')
        safe(path)
        raw, _ = read_stable(path, MAX_GENERATED_FILE_BYTES)
        if b'torch.ops.ltx_exact_rms.native.default(' not in raw:
            continue
        counts, parse_error = {}, None
        try:
            tree = ast.parse(raw.decode('utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    target = ast.unparse(node.func)
                    if target in ('torch.ops.ltx_exact_rms.native.default',
                                  'torch.ops.ltx_exact_activations.sigmoid.default',
                                  'torch.ops.ltx_exact_activations.gelu.default'):
                        counts[target] = counts.get(target, 0) + 1
        except SyntaxError as error:
            parse_error = repr(error)  # Preserve stable incomplete failed compiler source.
        if not counts.get('torch.ops.ltx_exact_rms.native.default') and parse_error is None:
            continue
        total += len(raw)
        require(total <= MAX_GENERATED_TOTAL_BYTES, 'Generated wrapper source exceeded total bound')
        selected.add(path)
        records.append({'path': archive_name(path), 'sha256': digest(raw), 'bytes': len(raw),
                        'emitted_native_call_counts': counts, 'source_parse_error': parse_error})
    return selected, records


def selected_paths(campaign, runs, manifest):
    paths = {ROOT / campaign / 'progress.json', ROOT / campaign / 'preregistration.json',
             SERVER / 'server-identity.json', SERVER / 'server-args.json',
             SERVER / 'determinism-after-import.json', PACKET / 'manifest.json'}
    add_tree(paths, ROOT / campaign)
    for path in SERVER.iterdir():
        safe(path)
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            paths.add(path)
    for name in (campaign + '.log', campaign + '-client.log', SERVER.name + '.log', 'FAULT.json'):
        path = safe(ROOT / name)
        if path.exists():
            paths.add(path)
    for selection in SELECTIONS:
        add_tree(paths, SERVER / ('native-multiblock-' + selection))
    for run in runs:
        add_tree(paths, ROOT / 'requests' / run)
        add_tree(paths, SERVER / ('compiler-' + run))
        summary = safe(ROOT / 'output/validation' / run / 'summary.json')
        if summary.exists():
            paths.add(summary)
    # Preserve the small reviewed extension/startup/graph/patch closure only.
    # The complete manifest pins the remaining Comfy sources without copying them.
    core = {'source/comfy/ldm/lightricks/av_model.py', 'source/comfy/ldm/lightricks/model.py',
            'source/comfy/ldm/common_dit.py', 'source/comfy/model_patcher.py'}
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
    for name in ('run-multiblock-screen-v2.py', 'ltx_multiblock_receipts_v2.py',
                 'run-encoder-screen.py', 'compare-clip.py', 'profile-clip.py', 'run-stability.py',
                 'export-multiblock-screen-v2.py'):
        paths.add(LANE / 'scripts' / name)
    generated, wrappers = generated_sources()
    paths.update(generated)
    return paths, wrappers


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
    return {'run': row['run'], 'mode': row.get('mode'), 'selection': row.get('selection'),
            'status': row.get('status'), 'initialization': row.get('initialization'),
            'parity_status': parity.get('status') if isinstance(parity, dict) else None,
            'all_four_outputs_exact': exact, 'comparisons': comparisons,
            'parity_parse_error': parity.get('export_parse_error') if isinstance(parity, dict) else None,
            'parity_path': archive_name(path) if parity is not None else None,
            'profile': profile, 'timings': timing_values(profile),
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


def paired_results(rows, output_rows):
    by_run = {row['run']: row for row in output_rows}
    results = {}
    for selection in SELECTIONS:
        triples = []
        for fixture in ('boat', 'marble', 'bird'):
            chosen = [row for row in rows if row.get('pair') == selection + '-' + fixture]
            if (len(chosen) != 3 or [r.get('mode') for r in chosen] != ['restored', 'compiled', 'restored'] or
                    any(r.get('status') != 'passed' or r.get('initialization') is not False or
                        not by_run[r['run']]['all_four_outputs_exact'] for r in chosen)):
                continue
            profiles = [by_run[row['run']]['profile'] for row in chosen]
            times = [p.get('preview_ready_seconds') if isinstance(p, dict) else None for p in profiles]
            if not all(type(t) in (int, float) and math.isfinite(t) and t > 0 for t in times):
                continue
            control = (times[0] + times[2]) / 2
            metrics = {}
            for metric in ('preview_ready_seconds', 'tensor_archive_ready_seconds', 'sampler_intervals_seconds'):
                samples = [by_run[row['run']]['timings'].get(metric) for row in chosen]
                if not all(type(t) in (int, float) and math.isfinite(t) and t > 0 for t in samples):
                    continue
                baseline = (samples[0] + samples[2]) / 2
                metrics[metric] = {'samples_seconds': samples, 'control_mean_seconds': baseline,
                    'compiled_minus_control_mean_seconds': samples[1] - baseline,
                    'control_mean_over_compiled': baseline / samples[1]}
            triples.append({'fixture': fixture, 'runs': [r['run'] for r in chosen],
                            'preview_seconds': times, 'control_mean_seconds': control,
                            'compiled_minus_control_mean_seconds': times[1] - control,
                            'control_mean_over_compiled': control / times[1], 'metrics': metrics})
        results[selection] = {'paired_samples': len(triples), 'triples': triples,
            'median_compiled_minus_control_mean_seconds': statistics.median(
                row['compiled_minus_control_mean_seconds'] for row in triples) if triples else None,
            'metric_summaries': {metric: {'paired_samples': len(values),
                'median_compiled_minus_control_mean_seconds': statistics.median(values) if values else None}
                for metric in ('preview_ready_seconds', 'tensor_archive_ready_seconds', 'sampler_intervals_seconds')
                for values in [[r['metrics'][metric]['compiled_minus_control_mean_seconds']
                                for r in triples if metric in r['metrics']]]},
            'scope': 'Approximate client-event intervals/readiness; neither kernel-only timing nor streaming qualification'}
    return results


def graph_coverage(text):
    """Observed receipts, including failed/partial attempts; not qualification."""
    coverage = {}
    for selection, indices in SELECTIONS.items():
        blocks = {}
        for index in indices:
            prefix = f'{SERVER.name}/native-multiblock-{selection}/block-{index:02d}/'
            files = sorted(name for name in text if name.startswith(prefix))
            receipts = []
            for name in files:
                if not re.fullmatch(re.escape(prefix) + r'graph-[0-9]+\.json', name):
                    continue
                row = parsed_optional(text, ROOT / name)
                receipts.append({'path': name, 'sha256': digest(text[name].encode()),
                    'graph': row.get('graph'), 'status': row.get('status'),
                    'parse_error': row.get('export_parse_error'), 'error': row.get('error'),
                    'rms_sites': len(row['replacements']) if isinstance(row.get('replacements'), list) else None,
                    'activation_sites': len(row['activation_replacements']) if isinstance(row.get('activation_replacements'), list) else None,
                    'activation_kind_counts': {kind: sum(isinstance(r, dict) and r.get('kind') == kind
                        for r in row.get('activation_replacements', [])) for kind in ('sigmoid', 'gelu')}
                        if isinstance(row.get('activation_replacements'), list) else None})
            if files:
                blocks[str(index)] = {'source_files': files, 'graph_receipt_count': len(receipts),
                    'reported_successful_graphs': sum(r['status'] == 'compiled-native-activations-boundary' for r in receipts),
                    'receipts': receipts}
        coverage[selection] = {'planned_blocks': list(indices), 'observed_blocks': len(blocks),
                              'observed_graph_receipts': sum(b['graph_receipt_count'] for b in blocks.values()),
                              'blocks': blocks}
    return coverage


def export(campaign, output):
    require(isinstance(campaign, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', campaign), 'Unsafe campaign')
    require(campaign == CAMPAIGN, 'Exporter requires preregistered campaign02')
    output = safe(output)
    require(output.is_relative_to(REPO) and output != REPO and output.parent.is_dir() and
            not output.exists(), 'Use a new export directory under the repository')
    progress_raw, _ = read_stable(ROOT / campaign / 'progress.json')
    prereg_raw, _ = read_stable(ROOT / campaign / 'preregistration.json')
    progress, prereg = unique_json(progress_raw), unique_json(prereg_raw)
    require(progress.get('status') in ('passed', 'failed'), 'Campaign is not terminal; do not export')
    require(prereg.get('campaign') == campaign and prereg.get('packet_manifest_sha256') == PACKET_SHA and
            prereg.get('client_sha256') == CLIENT_SHA and prereg.get('receipt_validator_sha256') == VALIDATOR_SHA,
            'Campaign source identity differs from the reviewed packet07 client')
    schedule, rows = prereg.get('schedule'), progress.get('rows')
    require(isinstance(schedule, list) and len(schedule) == 12 and isinstance(rows, list), 'Invalid bounded schedule')
    planned, attempted = [r['run'] for r in schedule], [r['run'] for r in rows]
    require(len(set(planned)) == len(planned) and len(set(attempted)) == len(attempted) and
            attempted == planned[:len(attempted)] and all(
                re.fullmatch(re.escape(campaign) + r'-r[0-9]{2}-[a-z0-9-]+', name) for name in planned),
            'Unexpected request identities/order')
    for row, plan in zip(rows, schedule):
        require(all(row.get(key) == value for key, value in plan.items()), 'Recorded request differs from plan')
    if progress['status'] == 'passed':
        require(len(rows) == 12 and all(row.get('status') == 'passed' for row in rows), 'Incomplete passed campaign')
    server_raw, _ = read_stable(SERVER / 'server-identity.json')
    server = unique_json(server_raw)
    require(server.get('encoder_run_dir') == str(SERVER) and server.get('source_packet_path') == str(PACKET) and
            server.get('source_packet_manifest_sha256') == PACKET_SHA and prereg.get('identity') == server,
            'Campaign/server/packet binding changed')
    manifest_raw, _ = read_stable(PACKET / 'manifest.json')
    require(digest(manifest_raw) == PACKET_SHA, 'Pinned packet manifest changed')
    manifest = unique_json(manifest_raw)
    paths, wrappers = selected_paths(campaign, planned, manifest)
    text, stable, total = {}, {}, 0
    for path in sorted(paths):
        raw, stable[path] = read_stable(path)
        total += len(raw)
        require(total <= MAX_TOTAL_BYTES, 'Text export exceeds bounded total size')
        text[archive_name(path)] = raw.decode('utf-8')
        if path.is_relative_to(PACKET) and path != PACKET / 'manifest.json':
            require(digest(raw) == manifest['files'][str(path.relative_to(PACKET))], 'Packet source changed')
    for path, raw in ((ROOT / campaign / 'progress.json', progress_raw),
                      (ROOT / campaign / 'preregistration.json', prereg_raw),
                      (SERVER / 'server-identity.json', server_raw), (PACKET / 'manifest.json', manifest_raw)):
        require(text[archive_name(path)].encode() == raw, 'Terminal identity changed during export')
    for name, expected in [('run-multiblock-screen-v2.py', CLIENT_SHA), ('ltx_multiblock_receipts_v2.py', VALIDATOR_SHA)]:
        require(digest(text[archive_name(LANE / 'scripts' / name)].encode()) == expected, 'Reviewed exporter dependency changed')
    inventory = {name: digest(value.encode()) for name, value in text.items()}
    output_rows = [parity_summary(text, campaign, row) for row in rows]
    require(all(row['status'] != 'passed' or row['all_four_outputs_exact'] for row in output_rows),
            'A passed request lacks its original four-output parity report')
    raw_bundle = json.dumps(text, ensure_ascii=False).encode()
    compressed = gzip.compress(raw_bundle, mtime=0)
    require(unique_json(gzip.decompress(compressed)) == text, 'Archive round-trip failed')
    require((paths, wrappers) == selected_paths(campaign, planned, manifest), 'Evidence file set/source changed during export')
    for path, before in stable.items():
        require(identity(safe(path).stat()) == before, 'Evidence changed before sealing: ' + str(path))
    summary = {'schema': 'ltx25.multiblock-terminal-export.v1', 'status': progress['status'],
        'status_scope': 'Copied terminal campaign status, with preserved parity reports; native qualification not rerun',
        'campaign': campaign, 'server_run': SERVER.name, 'server_pid': server['pid'],
        'server_boot_id': server['boot_id'], 'source_packet': str(PACKET), 'packet_manifest_sha256': PACKET_SHA,
        'client_sha256': CLIENT_SHA, 'validator_sha256': VALIDATOR_SHA,
        'startup_tools_sha256': manifest['startup_tools'],
        'extension_sha256s': manifest['extension_sha256s'],
        'exporter_sha256': inventory[archive_name(Path(__file__).resolve())],
        'startup_log_pins': {name: value for name, value in inventory.items() if
            (name.startswith(SERVER.name + '/') and '/' not in name[len(SERVER.name) + 1:]) or
            name in (SERVER.name + '.log', campaign + '.log', campaign + '-client.log')},
        'planned_requests': len(planned), 'recorded_requests': len(rows),
        'failure_stage': progress.get('failure_stage'), 'reported_error': progress.get('error'),
        'requests': output_rows, 'paired_results': paired_results(rows, output_rows),
        'graph_coverage': graph_coverage(text), 'generated_wrappers': wrappers,
        'generated_wrapper_scope': 'Shared cache source inventory; wrapper count is not a block/graph qualification count',
        'qualification_recomputed': False, 'speed_promotion': False, 'streaming_qualification': False,
        'fault_latch_present_at_export': 'FAULT.json' in text,
        'exported_text_files': len(text), 'source_text_bytes': total, 'archive_bytes': len(compressed),
        'evidence_sha256': digest(compressed), 'max_file_bytes': MAX_FILE_BYTES,
        'max_total_source_bytes': MAX_TOTAL_BYTES, 'max_generated_source_bytes': MAX_GENERATED_TOTAL_BYTES,
        'excluded': ['raw weights', 'raw tensor archives', 'video/images/audio', 'whole Comfy tree',
                     'binary/serialized caches', 'generated Python without actual opaque RMS calls']}
    output.mkdir(exist_ok=False)
    with (output / 'evidence.json.gz').open('xb') as stream:
        stream.write(compressed)
    for name, value in (('inventory.json', inventory), ('summary.json', summary)):
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

#!/usr/bin/env python3
"""Export terminal packet11 encoder screen text; never execute native work.

The campaign owner runs this only after the client is terminal. Failed campaigns
require --allow-failed; partial evidence is preserved without claiming a pass.
No tensor, media, weight, or binary cache bytes are read or included.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PACKET = ROOT / 'prepared-encoder-host-embedding-11'
SERVER = ROOT / 'encoder-server-host-embedding-11'
CAMPAIGN = 'host-embedding-screen-01'
DESTINATION = LANE / 'data/host-embedding-screen-01'
PACKET_SHA = '34b7ff2f7a74b6951f87dd2621738b37930d15a5de9d064409c8b12351adcf08'
CLIENT_SHA = '2712e10381219e6b7c63fb8be237256519abefb07e23d5681d4f1689a07c07a9'
VALIDATOR_SHA = '085792c1b2148db86abca387e4142d15da948cb52b1b10e0b3ea4dd84d8a6efd'
CONTRACT_SHA = '80be5c70f42cbe004a0be7af7c8b43a02269d29d9b6fbb6eb53597176b6e4add'
SHARED_SHA = '8c4bd7e85d862529d395b84d89c63d70c90c921d3c6b0b6c35826d73e30e315e'
REFERENCES = {'boat': 'baseline-01', 'marble': 'speed-oracle-marble', 'bird': 'speed-oracle-bird'}
HELPERS = {
    'run-host-embedding-screen.py': CLIENT_SHA,
    'ltx_host_embedding_receipts.py': VALIDATOR_SHA,
    'export-na-axis-confirm.py': SHARED_SHA,
    'run-multiblock-screen-v3.py': 'd8054e9866dfb314a5df37415811a5d4a5db79828b0494cca5f3526884ee3114',
    'run-encoder-screen.py': '4ec94d7e69c3d93b2caa740209f6a84ff35d56bdbbb8bf55f4b9782bacde10b0',
    'profile-clip.py': 'ad0141ff493c8c4cc5993ff4f8c2aceea76c2e99359477c7cef2d24628eb1980',
    'compare-clip.py': '80ee7a45468f95c6c0b8df9ecceea338af9fdf4d2537ba5966603b4f5b03fe0e',
    'run-stability.py': '7769cf87ed005be6e13dc6acced399f1541f68bc988953e7a409ba7fb80937b2',
}


def load_stdlib(name, path, expected):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise RuntimeError('Frozen export helper changed: ' + str(path))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


shared = load_stdlib('host_export_shared', LANE / 'scripts/export-na-axis-confirm.py', SHARED_SHA)
validators = load_stdlib('host_export_receipts', LANE / 'scripts/ltx_host_embedding_receipts.py', VALIDATOR_SHA)
require, safe, read_stable = shared.require, shared.safe, shared.read_stable
unique_json, digest, archive_name = shared.unique_json, shared.digest, shared.archive_name
TEXT_SUFFIXES = shared.TEXT_SUFFIXES
OUTPUTS = shared.OUTPUTS


def expected_schedule():
    rows = []
    for generation, (arm, mode) in enumerate((('control-a', 'control'), ('host-table', 'host-table'), ('control-b', 'control')), 1):
        for ordinal, fixture in enumerate(('boat', 'boat', 'marble', 'bird', 'boat'), 1):
            rows.append({'arm': arm, 'mode': mode, 'generation': generation, 'ordinal': ordinal,
                'fixture': fixture, 'initialization': ordinal == 1,
                'run': f'{CAMPAIGN}-r{len(rows)+1:02d}-{arm}-{fixture}'})
    return rows


def terminal_rows(progress, prereg, allow_failed=False):
    require(progress.get('status') in ('passed', 'failed'), 'Client campaign is not terminal')
    require(progress['status'] == 'passed' or allow_failed is True, 'Failed export requires --allow-failed')
    require(prereg.get('campaign') == CAMPAIGN and prereg.get('max_requests') == 15
        and prereg.get('packet_manifest_sha256') == PACKET_SHA and prereg.get('client_sha256') == CLIENT_SHA
        and prereg.get('validator_sha256') == VALIDATOR_SHA and prereg.get('registered_contract_sha256') == CONTRACT_SHA,
        'Unreviewed campaign source/schedule identity')
    require(prereg.get('inherited_v3_sha256') == HELPERS['run-multiblock-screen-v3.py']
        and prereg.get('frozen_helpers') == {name: HELPERS[name] for name in
            ('profile-clip.py', 'compare-clip.py', 'run-stability.py')}, 'Inherited helper identity differs')
    plan, rows = prereg.get('schedule'), progress.get('rows')
    require(plan == expected_schedule() and isinstance(rows, list) and len(rows) <= 15, 'Unexpected bounded schedule')
    for row, planned in zip(rows, plan):
        require(isinstance(row, dict) and all(row.get(k) == v for k, v in planned.items()), 'Attempt differs from planned prefix')
        require(row.get('status') in ('passed', 'failed', 'running'), 'Unknown request status')
    if progress['status'] == 'passed':
        require(len(rows) == progress.get('completed_requests') == 15
            and all(row['status'] == 'passed' for row in rows), 'Incomplete passed campaign')
        require(progress.get('speed_promotion') is False and progress.get('streaming_qualification') is False,
                'Screening cannot claim promotion/streaming')
    return plan, rows


def selected_paths(plan, manifest, contract):
    paths = {ROOT / CAMPAIGN / 'progress.json', ROOT / CAMPAIGN / 'preregistration.json',
        SERVER / 'server-identity.json', SERVER / 'server-args.json', SERVER / 'determinism-after-import.json',
        ROOT / 'model-verification.json', PACKET / 'manifest.json',
        LANE / 'data/host-embedding-registered-contract-01.json', safe(contract['source_path']),
        LANE / 'data/speed-resident-split-api.json'}
    shared.add_tree(paths, ROOT / CAMPAIGN)
    shared.add_tree(paths, ROOT / 'host-embedding-migration-11')
    for path in SERVER.iterdir():
        safe(path)
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            paths.add(path)
    for name in (SERVER.name + '.log', CAMPAIGN + '.log', CAMPAIGN + '-client.log', 'FAULT.json'):
        path = safe(ROOT / name)
        if path.exists(): paths.add(path)
    for run in [row['run'] for row in plan] + list(REFERENCES.values()):
        shared.add_tree(paths, ROOT / 'requests' / run)
        summary = safe(ROOT / 'output/validation' / run / 'summary.json')
        if summary.exists(): paths.add(summary)
    core = {'source/nodes.py', 'source/comfy/sd.py', 'source/comfy/model_patcher.py',
        'source/comfy/model_management.py', 'source/comfy/ops.py', 'source/comfy/sd1_clip.py',
        'source/comfy/text_encoders/lt.py', 'source/comfy/text_encoders/llama.py',
        'source/comfy/text_encoders/gemma4.py'}
    scripts = {'source/scripts/' + name for name in manifest['extension_sha256s']}
    for name in manifest['files']:
        relative = Path(name)
        require(not relative.is_absolute() and '..' not in relative.parts, 'Unsafe manifest path')
        selected = (name in core or name in scripts or name == 'model-paths.yaml'
            or name.startswith(('launch/', 'graphs/', 'patches/', 'provenance/'))
            or name.endswith('-parent-manifest.json')
            or (name.startswith('source/custom_nodes/ltx_') and name.endswith('/__init__.py')))
        if selected and relative.suffix in TEXT_SUFFIXES: paths.add(PACKET / name)
    for name in (*HELPERS, Path(__file__).name): paths.add(LANE / 'scripts' / name)
    require(len(paths) <= shared.MAX_SCAN_ENTRIES, 'Text inventory exceeds bound')
    return paths


def document(text, path, optional=False):
    key = archive_name(path)
    if optional and key not in text: return None
    require(key in text, 'Missing required text evidence: ' + key)
    try:
        result = unique_json(text[key])
        require(isinstance(result, dict), 'Expected JSON object: ' + key)
        return result
    except (ValueError, RuntimeError) as error:
        if optional:
            return {'export_parse_error': repr(error), 'source_path': key}
        raise


def row_summary(text, row, server, contract, previous, components):
    run, mode = row['run'], row['mode']
    parity_path = ROOT / CAMPAIGN / (run + '-parity.json')
    parity = document(text, parity_path, optional=True)
    comparisons = parity.get('comparisons', {}) if parity else {}
    comparisons = comparisons if isinstance(comparisons, dict) else {}
    exact = (parity is not None and parity.get('status') == 'passed' and set(comparisons) == OUTPUTS
        and all(isinstance(value, dict) and value.get('bitwise_equal') is True
            and value.get('same_layout') is True for value in comparisons.values()))
    result = {**{k: row[k] for k in expected_schedule()[0]}, 'status': row['status'],
        'reported_all_four_outputs_exact': exact, 'comparisons': comparisons,
        'parity_path': archive_name(parity_path) if parity else None,
        'profile': document(text, ROOT / 'requests' / run / 'profile.json', optional=True),
        'placement': document(text, SERVER / ('host-embedding-placement-' + run + '.json'), optional=True),
        'capture_summary': document(text, ROOT / 'output/validation' / run / 'summary.json', optional=True)}
    result['timings'] = shared.timing_values(result['profile'])
    if row['status'] != 'passed':
        return result, previous, components
    require(exact, 'Passed request lacks exact original four-output receipt: ' + run)
    request = ROOT / 'requests' / run
    submitted = document(text, request / 'prompt.json')
    submission = document(text, request / 'submission.json')
    history = document(text, request / 'history.json')
    request_result = document(text, request / 'result.json')
    request_identity = document(text, request / 'identity.json')
    require(request_identity == server, 'Request server identity differs')
    require(history['prompt'][1] == submission['prompt_id'] == request_result['prompt_id']
        and history['prompt'][2] == submitted and history['status']['status_str'] == 'success'
        and not any(item[1].get('nodes') for item in history['status']['messages'] if item[0] == 'execution_cached'),
        'Request identity/status/cache evidence differs')
    executions = parity['executions']
    require(len(executions) == 2 and executions[0]['name'] == REFERENCES[row['fixture']]
        and executions[1]['name'] == run and executions[1]['prompt_id'] == submission['prompt_id']
        and executions[1]['server_identity'] == server
        and executions[1]['prompt_sha256'] == digest(text[archive_name(request / 'prompt.json')].encode()),
        'Parity is not bound to this original/request')
    capture = result['capture_summary']
    reference = document(text, ROOT / 'output/validation' / REFERENCES[row['fixture']] / 'summary.json')
    require(capture['run_name'] == run and capture['deterministic_enabled'] is True
        and capture['deterministic_warn_only'] is False and capture['sample_rate'] == reference['sample_rate'] == 48000
        and set(capture['tensors']) == OUTPUTS, 'Capture metadata differs')
    for name in OUTPUTS:
        require(capture['tensors'][name]['finite'] is True and all(capture['tensors'][name][key] == reference['tensors'][name][key]
            for key in ('shape', 'dtype', 'sha256')), 'Capture hash/layout differs from original: ' + name)
    prefix = f"host-components-{row['generation']:02d}-{mode}"
    started = document(text, SERVER / (prefix + '-started.json'))
    component = document(text, SERVER / (prefix + '-result.json'))
    identity_sha = digest(text[archive_name(SERVER / 'server-identity.json')].encode())
    model_sha = server['model_verification_sha256']
    validators.component(started, component, contract=contract, mode=mode, generation=row['generation'],
        server_sha=identity_sha, model_sha=model_sha)
    if row['initialization']:
        if components is not None:
            retirement = document(text, SERVER / (prefix + '-unload.json'))
            validators.unload(retirement, contract=contract, previous=previous,
                old_generation=row['generation'] - 1, new_generation=row['generation'], mode=mode,
                server_sha=identity_sha, model_sha=model_sha)
        else:
            require(row['generation'] == 1, 'Missing prior component generation')
        components, previous = component, None
    else:
        require(components == component, 'Component changed within arm')
    validators.placement(result['placement'], contract=contract, run=run, mode=mode, ordinal=row['ordinal'],
        server_sha=identity_sha, model_sha=model_sha, initial=components['encoder_initial_ownership'], previous=previous)
    return result, result['placement'], components


def retention_summary(progress, text, plan):
    inventory = document(text, ROOT / CAMPAIGN / 'output-inventory.json', optional=True)
    deletion_key = archive_name(ROOT / CAMPAIGN / 'deletion-receipts.jsonl')
    records, parse_errors = [], []
    for ordinal, line in enumerate(text.get(deletion_key, '').splitlines(), 1):
        if not line.strip(): continue
        try:
            records.append(unique_json(line))
        except (ValueError, RuntimeError) as error:
            require(progress['status'] == 'failed', 'Invalid passed deletion receipt')
            parse_errors.append({'line': ordinal, 'error': repr(error)})
    if inventory is not None and 'export_parse_error' in inventory:
        require(progress['status'] == 'failed', 'Invalid passed output inventory')
        parse_errors.append(inventory)
        inventory = None
    allowed = {row['run'] for row in plan}
    deleted, intents = set(), {}
    for entry in records:
        require(entry['run'] in allowed and entry['action'] == 'delete' and entry['parity_passed'] is True,
                'Deletion receipt outside this verified campaign')
        relative = Path(entry['relative_path'])
        require(not relative.is_absolute() and '..' not in relative.parts and relative.suffix in ('.mp4','.safetensors'),
                'Unsafe retention path')
        require(relative.parent in (Path('output') / entry['run'], Path('output/validation') / entry['run']),
                'Retention path outside recorded run')
        comparable = {k: v for k, v in entry.items() if k != 'phase'}
        if entry['phase'] == 'completed':
            require(intents.get(entry['relative_path']) == comparable
                and entry['relative_path'] not in deleted, 'Deletion completion lacks unique matching intent')
            deleted.add(entry['relative_path'])
        else:
            require(entry['phase'] == 'intent' and entry['relative_path'] not in intents, 'Unknown/duplicate deletion intent')
            intents[entry['relative_path']] = comparable
    remaining = []
    if inventory is not None:
        for run, entries in inventory.items():
            require(run in allowed and isinstance(entries, list) and len(entries) == 2, 'Unknown retained run/inventory')
            for entry in entries:
                require(entry['run'] == run, 'Inventory run mismatch')
                if entry['relative_path'] in intents:
                    require(all(intents[entry['relative_path']].get(k) == v for k,v in entry.items()),
                            'Deletion receipt differs from inventoried output')
                if entry['relative_path'] not in deleted: remaining.append(entry)
    if progress['status'] == 'passed':
        require(inventory is not None and set(inventory) == allowed, 'Passed campaign lacks all15 output inventories')
        require(progress['retained_outputs'] == remaining and len(remaining) == 3
            and all(Path(entry['relative_path']).suffix == '.mp4' for entry in remaining),
            'Passed campaign violates three-preview/raw-retirement bound')
        for run in allowed:
            require(str(Path('output/validation') / run / 'tensors.safetensors') in deleted,
                    'Passed raw archive lacks completed deletion receipt')
    return {'reported_remaining_outputs': remaining, 'completed_deletions': len(deleted),
        'partial_text_parse_errors': parse_errors,
        'retained_preview_count': sum(Path(entry['relative_path']).suffix == '.mp4' for entry in remaining),
        'binary_outputs_included': False, 'scope': 'Validated text retention receipts; media and raw bytes not reopened'}


def export(output=DESTINATION, allow_failed=False):
    output = safe(output)
    require(output == DESTINATION and not output.exists() and output.parent.is_dir(), 'Require new fixed export directory')
    originals = {}
    for path in (ROOT / CAMPAIGN / 'progress.json', ROOT / CAMPAIGN / 'preregistration.json',
                 SERVER / 'server-identity.json', PACKET / 'manifest.json', LANE / 'data/host-embedding-registered-contract-01.json'):
        originals[path] = read_stable(path)[0]
    progress = unique_json(originals[ROOT / CAMPAIGN / 'progress.json'])
    prereg = unique_json(originals[ROOT / CAMPAIGN / 'preregistration.json'])
    plan, rows = terminal_rows(progress, prereg, allow_failed)
    server = unique_json(originals[SERVER / 'server-identity.json'])
    require(server['encoder_run_dir'] == str(SERVER) and server['source_packet_path'] == str(PACKET)
        and server['source_packet_manifest_sha256'] == PACKET_SHA and prereg['identity'] == server,
        'Campaign/server/packet identity differs')
    require(digest(originals[PACKET / 'manifest.json']) == PACKET_SHA, 'Sealed packet changed')
    manifest = unique_json(originals[PACKET / 'manifest.json'])
    require(manifest['schema'] == 'ltx.host-embedding-runtime-packet.v1', 'Wrong packet schema')
    require(digest(originals[LANE / 'data/host-embedding-registered-contract-01.json']) == CONTRACT_SHA, 'Contract changed')
    contract = unique_json(originals[LANE / 'data/host-embedding-registered-contract-01.json'])
    require(prereg['registered_contract'] == contract, 'Preregistered original contract differs')
    paths = selected_paths(plan, manifest, contract)
    text, stable, total = {}, {}, 0
    for path in sorted(paths):
        raw, stable[path] = read_stable(path)
        total += len(raw)
        require(total <= shared.MAX_TOTAL_BYTES, 'Text export exceeds total bound')
        text[archive_name(path)] = raw.decode('utf-8')
        if path.is_relative_to(PACKET) and path != PACKET / 'manifest.json':
            require(digest(raw) == manifest['files'][str(path.relative_to(PACKET))], 'Sealed source bytes changed')
    for path, raw in originals.items():
        require(text[archive_name(path)].encode() == raw, 'Terminal/source identity changed during export')
    for name, expected in HELPERS.items():
        require(digest(text[archive_name(LANE / 'scripts' / name)].encode()) == expected, 'Frozen evidence helper changed')
    require(digest(text[archive_name(safe(contract['source_path']))].encode()) == contract['source_sha256'],
            'Original registration evidence changed')
    output_rows, previous, components = [], None, None
    for row in rows:
        value, previous, components = row_summary(text, row, server, contract, previous, components)
        output_rows.append(value)
    retained = retention_summary(progress, text, plan)
    raw_bundle = json.dumps(text, ensure_ascii=False).encode()
    compressed = gzip.compress(raw_bundle, mtime=0)
    require(unique_json(gzip.decompress(compressed)) == text, 'Archive round-trip failed')
    require(paths == selected_paths(plan, manifest, contract), 'Evidence file set changed during export')
    for path, before in stable.items():
        require(shared.identity(safe(path).stat()) == before, 'Evidence changed before sealing: ' + str(path))
    require('torch' not in sys.modules, 'Text exporter imported Torch')
    inventory = {name: {'sha256': digest(value.encode()), 'bytes': len(value.encode())} for name, value in text.items()}
    summary = {'schema': 'ltx25.host-embedding-terminal-export.v1', 'status': progress['status'],
        'status_scope': 'Terminal client status and validated text receipts; native raw equality not rerun',
        'campaign': CAMPAIGN, 'planned_requests': 15, 'recorded_requests': len(rows),
        'passed_requests': sum(row['status'] == 'passed' for row in rows),
        'failure_stage': progress.get('failure_stage'), 'reported_error': progress.get('error'),
        'server_run': SERVER.name, 'server_pid': server['pid'], 'server_boot_id': server['boot_id'],
        'packet_manifest_sha256': PACKET_SHA, 'client_sha256': CLIENT_SHA, 'validator_sha256': VALIDATOR_SHA,
        'contract_sha256': CONTRACT_SHA, 'exporter_sha256': inventory[archive_name(Path(__file__).resolve())]['sha256'],
        'requests': output_rows, 'reported_paired_results': progress.get('paired_results'),
        'retention': retained, 'extension_sha256s': manifest['extension_sha256s'],
        'host_embedding': manifest['host_embedding'], 'qualification_recomputed': False,
        'speed_promotion': False, 'streaming_qualification': False,
        'exported_text_files': len(text), 'source_text_bytes': total, 'archive_bytes': len(compressed),
        'evidence_sha256': digest(compressed), 'max_file_bytes': shared.MAX_FILE_BYTES,
        'max_total_source_bytes': shared.MAX_TOTAL_BYTES,
        'excluded': ['raw tensor archives', 'weights', 'video/images/audio', 'whole Comfy tree', 'binary/generated caches']}
    output.mkdir(exist_ok=False)
    with (output / 'evidence.json.gz').open('xb') as stream: stream.write(compressed)
    export_manifest = {'schema': 'ltx25.text-evidence-archive.v1', 'archive': 'evidence.json.gz',
        'archive_sha256': digest(compressed), 'archive_bytes': len(compressed), 'files': inventory,
        'encoding': 'gzip of UTF-8 JSON mapping archive-relative paths to exact source text', 'qualification_recomputed': False}
    for name, value in (('manifest.json',export_manifest),('summary.json',summary)):
        with (output / name).open('x') as stream: json.dump(value,stream,indent=2);stream.write('\n')
    return {'status': progress['status'], 'output': str(output), 'files':len(text), 'evidence_sha256':digest(compressed)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DESTINATION)
    parser.add_argument('--allow-failed',action='store_true')
    args=parser.parse_args()
    print(json.dumps(export(args.output,args.allow_failed),indent=2))

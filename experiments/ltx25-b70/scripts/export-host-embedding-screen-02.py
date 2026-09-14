#!/usr/bin/env python3
"""Preserve terminal screen02 text, including partial/failed receipts.

Root owner must confirm the client is terminal before invoking. This exports
evidence and reported status; it does not rerun quality or lifecycle gates.
No native imports, process/device/endpoint queries, media or raw tensor reads.
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
PACKET = ROOT / 'prepared-encoder-host-embedding-12'
SERVER = ROOT / 'encoder-server-host-embedding-12'
CAMPAIGN = 'host-embedding-screen-02'
DESTINATION = LANE / 'data/host-embedding-screen-02-export'
PACKET_SHA = 'b29b750c31feda9d4be7fdc768e876a1f5d58ad11a699022b1d8ae6bdaa59666'
CLIENT_SHA = 'bfa2a383a0bfb803c3c478a2eeae959a16d6fedc9721c17e9f131f6f34b477bf'
VALIDATOR_SHA = '8a86a290bfc7a225b86cf3e6fa50bfe985a64aaebd3d5aaa26cef7c95784d490'
CONTRACT_SHA = '80be5c70f42cbe004a0be7af7c8b43a02269d29d9b6fbb6eb53597176b6e4add'
COLD_SHA = 'f596d6b4ad0f83efce39342a0d4a897aedd267e7df0f2f23f4403e704cb96058'
SHARED_SHA = '8c4bd7e85d862529d395b84d89c63d70c90c921d3c6b0b6c35826d73e30e315e'
HELPERS = {
    'run-host-embedding-screen-v3.py': CLIENT_SHA,
    'ltx_host_embedding_receipts_v3.py': VALIDATOR_SHA,
    'export-na-axis-confirm.py': SHARED_SHA,
    'run-multiblock-screen-v3.py': 'd8054e9866dfb314a5df37415811a5d4a5db79828b0494cca5f3526884ee3114',
    'run-encoder-screen.py': '4ec94d7e69c3d93b2caa740209f6a84ff35d56bdbbb8bf55f4b9782bacde10b0',
    'profile-clip.py': 'ad0141ff493c8c4cc5993ff4f8c2aceea76c2e99359477c7cef2d24628eb1980',
    'compare-clip.py': '80ee7a45468f95c6c0b8df9ecceea338af9fdf4d2537ba5966603b4f5b03fe0e',
    'run-stability.py': '7769cf87ed005be6e13dc6acced399f1541f68bc988953e7a409ba7fb80937b2',
}
shared_path = LANE / 'scripts/export-na-axis-confirm.py'
if hashlib.sha256(shared_path.read_bytes()).hexdigest() != SHARED_SHA:
    raise RuntimeError('Frozen text archive helper changed')
spec = importlib.util.spec_from_file_location('screen02_text_helpers', shared_path)
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)
require, safe, digest = shared.require, shared.safe, shared.digest
validator_path = LANE / 'scripts/ltx_host_embedding_receipts_v3.py'
if digest(validator_path.read_bytes()) != VALIDATOR_SHA:
    raise RuntimeError('Frozen receipt validator changed')
spec = importlib.util.spec_from_file_location('screen02_partial_receipts', validator_path)
validators = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validators)


def schedule():
    rows = []
    for generation, (arm, mode) in enumerate((('control-a', 'control'), ('host-table', 'host-table'), ('control-b', 'control')), 1):
        for ordinal, fixture in enumerate(('boat', 'boat', 'marble', 'bird', 'boat'), 1):
            rows.append({'arm': arm, 'mode': mode, 'generation': generation, 'ordinal': ordinal,
                'fixture': fixture, 'initialization': ordinal == 1,
                'run': f'{CAMPAIGN}-r{len(rows)+1:02d}-{arm}-{fixture}'})
    return rows


def document(text, path):
    key = shared.archive_name(path)
    if key not in text:
        return {'export_missing': True, 'path': key}
    try:
        value = shared.unique_json(text[key])
        require(isinstance(value, dict), 'Expected JSON object')
        return value
    except (ValueError, RuntimeError) as error:
        return {'export_parse_error': repr(error), 'path': key}


def terminal_gate(progress, declared):
    require(declared in ('passed', 'failed'), 'Explicit terminal owner declaration required')
    if declared == 'passed':
        rows = progress.get('rows')
        require(progress.get('status') == 'passed' and isinstance(rows, list)
            and len(rows) == progress.get('completed_requests') == 15, 'Incomplete passed campaign')
        require(all(row.get('status') == 'passed' and all(row.get(k) == v for k, v in plan.items())
            for row, plan in zip(rows, schedule())), 'Passed schedule differs')
    else:
        # Root can attest a crashed client is terminal even if its last progress
        # write was running, incomplete or absent. Preserve that discrepancy.
        require(progress.get('status') != 'passed', 'Passed client cannot be declared failed')


def refused_construction(report):
    """Validate an actual refusal without changing/relabeling its passed flag."""
    allocation = validators.CHECKPOINT_TENSOR_BYTES + validators.REGISTERED_STATE_BYTES
    require(report['schema'] == 'ltx.host-embedding-memory-admission.v1'
        and report['stage'] == 'before-construction' and report['passed'] is False
        and type(report['tracked_allocation_bytes']) is int and report['tracked_allocation_bytes'] == allocation
        and report['existing_headroom_bytes'] == validators.HEADROOM_BYTES
        and report['required_available_bytes'] == allocation + validators.HEADROOM_BYTES
        and report['swap_counted_as_headroom'] is False and report['runtime_memory_settings_changed'] is False,
        'Unexpected construction refusal contract')
    observed = report['observed']
    require(observed['source'] == '/proc/meminfo', 'Wrong memory source')
    fields = dict(line.split(':', 1) for line in observed['raw'].splitlines())
    parsed = {}
    for key in ('MemTotal', 'MemAvailable', 'MemFree', 'SwapFree', 'SwapTotal'):
        parts = fields[key].split()
        require(len(parts) == 2 and parts[1] == 'kB' and parts[0].isdigit(), 'Invalid memory observation')
        parsed[key] = int(parts[0]) * 1024
    require(parsed == observed['bytes'] and all(type(v) is int for v in observed['bytes'].values())
        and 0 < parsed['MemTotal'] and parsed['MemAvailable'] <= parsed['MemTotal']
        and parsed['MemFree'] <= parsed['MemTotal'] and parsed['SwapFree'] <= parsed['SwapTotal']
        and parsed['MemAvailable'] < report['required_available_bytes'], 'Memory refusal arithmetic differs')
    return {'status': 'validated-memory-refusal', 'passed': False,
        'available_bytes': parsed['MemAvailable'], 'required_bytes': report['required_available_bytes']}


def partial_transition_checks(text, server, contract):
    checks = []
    server_sha = digest(text[shared.archive_name(SERVER / 'server-identity.json')].encode())
    model_sha = server['model_verification_sha256']
    for generation, mode, previous_mode in ((2, 'host-table', 'control'), (3, 'control', 'host-table')):
        prefix = f'host-components-{generation:02d}-{mode}'
        retirement_path = SERVER / (prefix + '-unload.json')
        if shared.archive_name(retirement_path) not in text:
            continue
        row = {'generation': generation, 'encoder_mode': mode}
        try:
            retirement = document(text, retirement_path)
            prior = [r for r in schedule() if r['generation'] == generation - 1][-1]
            previous = document(text, SERVER / ('host-embedding-placement-' + prior['run'] + '.json'))
            component = document(text, SERVER / f'host-components-{generation-1:02d}-{previous_mode}-result.json')
            row['retirement'] = validators.unload(retirement, contract=contract, previous=previous,
                old_generation=generation-1, new_generation=generation, mode=mode,
                server_sha=server_sha, model_sha=model_sha)
            row['release'] = validators.released(document(text, SERVER / (prefix + '-retired-owner-release.json')),
                previous_mode=previous_mode, old_generation=generation-1, new_generation=generation,
                shared=component['shared_owner_ids'], server_sha=server_sha, model_sha=model_sha)
            allocation = sum(r['bytes'] for kind in ('parameters', 'buffers')
                for r in retirement['before']['encoder'][kind]['records'] if r['device'] != 'cpu')
            row['before_restore'] = validators.memory(document(text, SERVER / (prefix + '-before-restore-memory.json')), 'before-restore', allocation)
            row['after_release'] = validators.memory(document(text, SERVER / (prefix + '-after-release-memory.json')), 'after-release', 0)
            construction = document(text, SERVER / (prefix + '-before-construction-memory.json'))
            if construction.get('passed') is False:
                row['construction'] = refused_construction(construction)
                result = document(text, SERVER / (prefix + '-result.json'))
                validators.identity(result, server_sha, model_sha)
                require(result['status'] == 'failed' and result['generation'] == generation
                    and result['failure']['phase'] == 'admit-CPU-encoder-construction'
                    and result['retained_partial_owners'] == 0
                    and result['shared_components_retained'] is True,
                    'Failed construction result differs')
                row['completed_new_component_proof'] = False
            else:
                row['construction'] = validators.memory(construction, 'before-construction',
                    validators.CHECKPOINT_TENSOR_BYTES + validators.REGISTERED_STATE_BYTES)
            row['status'] = 'validated-saved-transition-receipts'
        except (KeyError, TypeError, ValueError, RuntimeError) as error:
            # A bad/missing partial receipt must not prevent evidence preservation.
            row.update(status='partial-receipt-validation-failed', error=repr(error))
        checks.append(row)
    return checks


def selected_paths(manifest, contract, cold):
    paths = {PACKET / 'manifest.json', SERVER / 'server-identity.json', ROOT / CAMPAIGN / 'preregistration.json',
        ROOT / 'model-verification.json', LANE / 'data/host-embedding-registered-contract-01.json',
        LANE / 'data/host-embedding-cold-memory-contract-01.json', safe(contract['source_path']), Path(__file__).resolve()}
    for directory in (ROOT / CAMPAIGN, ROOT / 'host-transition-migration-12', ROOT / 'host-embedding-migration-12'):
        shared.add_tree(paths, directory)
    # Server root contains lifecycle/release/memory/placement receipts. Do not
    # recurse into its user/cache folders or inspect any output binary.
    for path in SERVER.iterdir():
        safe(path)
        if path.is_file() and path.suffix in shared.TEXT_SUFFIXES:
            paths.add(path)
    for name in (SERVER.name + '.log', CAMPAIGN + '.log', CAMPAIGN + '-client.log', 'FAULT.json'):
        path = safe(ROOT / name)
        if path.exists():
            paths.add(path)
    for run in [row['run'] for row in schedule()] + ['baseline-01', 'speed-oracle-marble', 'speed-oracle-bird']:
        shared.add_tree(paths, ROOT / 'requests' / run)
        path = safe(ROOT / 'output/validation' / run / 'summary.json')
        if path.exists():
            paths.add(path)
    for name in manifest['files']:
        path = Path(name)
        require(not path.is_absolute() and '..' not in path.parts, 'Unsafe manifest path')
        if path.suffix in shared.TEXT_SUFFIXES and (name.startswith(('launch/', 'graphs/', 'patches/', 'provenance/', 'source/scripts/'))
            or name.endswith('-parent-manifest.json') or name == 'model-paths.yaml'
            or (name.startswith('source/custom_nodes/ltx_') and name.endswith('/__init__.py'))
            or name in ('source/nodes.py', 'source/comfy/sd.py', 'source/comfy/model_patcher.py',
                'source/comfy/model_management.py', 'source/comfy/ops.py', 'source/comfy/sd1_clip.py',
                'source/comfy/text_encoders/llama.py', 'source/comfy/text_encoders/gemma4.py')):
            paths.add(PACKET / name)
    for name in HELPERS:
        paths.add(LANE / 'scripts' / name)
    for name in (*cold['source_sha256s'], *cold['saved_evidence_sha256s']):
        path = safe(name)
        require(path.suffix in shared.TEXT_SUFFIXES, 'Cold proof is not text')
        shared.archive_name(path)  # Enforce approved evidence roots.
        paths.add(path)
    for name in ('host-transition-runtime-12-prepared.json', 'host-transition-runtime-12-startup-check.json',
                 'host-transition-runtime-12-startup-admission.json', 'host-embedding-screen-v3-packet12-check.json',
                 'host-embedding-screen-02-postflight.json'):
        path = LANE / 'data' / name
        if path.exists():
            paths.add(path)
    require(len(paths) <= shared.MAX_SCAN_ENTRIES, 'Text inventory exceeds bound')
    return paths


def export(terminal_status):
    output = safe(DESTINATION)
    require(not output.exists() and output.parent.is_dir(), 'Require new fixed export directory')
    original = {}
    for path in (PACKET / 'manifest.json', SERVER / 'server-identity.json', ROOT / CAMPAIGN / 'preregistration.json',
                 LANE / 'data/host-embedding-registered-contract-01.json', LANE / 'data/host-embedding-cold-memory-contract-01.json'):
        original[path] = shared.read_stable(path)[0]
    manifest, server, prereg, contract, cold = [shared.unique_json(raw) for raw in original.values()]
    require(digest(original[PACKET / 'manifest.json']) == PACKET_SHA and manifest['schema'] == 'ltx.host-embedding-runtime-packet.v2', 'Packet12 identity changed')
    require(prereg['campaign'] == CAMPAIGN and prereg['schedule'] == schedule() and prereg['max_requests'] == 15
        and prereg['packet_manifest_sha256'] == PACKET_SHA and prereg['client_sha256'] == CLIENT_SHA
        and prereg['validator_sha256'] == VALIDATOR_SHA and prereg['registered_contract_sha256'] == CONTRACT_SHA
        and prereg['cold_memory_contract_sha256'] == COLD_SHA, 'Campaign identity differs')
    require(prereg['identity'] == server and server['encoder_run_dir'] == str(SERVER)
        and server['source_packet_path'] == str(PACKET) and server['source_packet_manifest_sha256'] == PACKET_SHA,
        'Server identity differs')
    require(digest(original[LANE / 'data/host-embedding-registered-contract-01.json']) == CONTRACT_SHA
        and digest(original[LANE / 'data/host-embedding-cold-memory-contract-01.json']) == COLD_SHA, 'Contract identity differs')
    paths = selected_paths(manifest, contract, cold)
    text, stable, total = {}, {}, 0
    for path in sorted(paths):
        raw, stable[path] = shared.read_stable(path)
        total += len(raw)
        require(total <= shared.MAX_TOTAL_BYTES, 'Text archive exceeds bound')
        text[shared.archive_name(path)] = raw.decode('utf-8')
        if path.is_relative_to(PACKET) and path != PACKET / 'manifest.json':
            require(digest(raw) == manifest['files'][str(path.relative_to(PACKET))], 'Sealed source changed')
    for path, raw in original.items():
        require(text[shared.archive_name(path)].encode() == raw, 'Identity changed during export')
    for name, expected in HELPERS.items():
        require(digest(text[shared.archive_name(LANE / 'scripts' / name)].encode()) == expected, 'Frozen helper changed')
    for name, expected in {**cold['source_sha256s'], **cold['saved_evidence_sha256s'], contract['source_path']: contract['source_sha256']}.items():
        require(digest(text[shared.archive_name(name)].encode()) == expected, 'Evidence source pin changed')
    progress = document(text, ROOT / CAMPAIGN / 'progress.json')
    terminal_gate(progress, terminal_status)
    partial = partial_transition_checks(text, server, contract)
    requests = []
    for row in schedule():
        run = row['run']
        requests.append({**row, 'parity': document(text, ROOT / CAMPAIGN / (run + '-parity.json')),
            'profile': document(text, ROOT / 'requests' / run / 'profile.json'),
            'request_result': document(text, ROOT / 'requests' / run / 'result.json'),
            'capture_summary': document(text, ROOT / 'output/validation' / run / 'summary.json')})
    bundle = gzip.compress(json.dumps(text, ensure_ascii=False).encode(), mtime=0)
    require(shared.unique_json(gzip.decompress(bundle)) == text, 'Archive roundtrip failed')
    require(paths == selected_paths(manifest, contract, cold), 'Evidence file set changed before sealing')
    for path, before in stable.items():
        require(shared.identity(safe(path).stat()) == before, 'Evidence changed before sealing: ' + str(path))
    require('torch' not in sys.modules, 'Text exporter imported Torch')
    inventory = {name: {'sha256': digest(value.encode()), 'bytes': len(value.encode())} for name, value in text.items()}
    summary = {'schema': 'ltx25.host-embedding-screen02-preservation.v1', 'status': 'exported-terminal-text',
        'owner_declared_terminal_status': terminal_status, 'reported_progress': progress, 'requests': requests,
        'scope': 'Exact text preservation, including partial receipts; saved retirement/release/memory checked, full quality/lifecycle/retention gates not rerun',
        'partial_transition_checks': partial,
        'campaign': CAMPAIGN, 'packet_manifest_sha256': PACKET_SHA, 'client_sha256': CLIENT_SHA,
        'validator_sha256': VALIDATOR_SHA, 'exporter_sha256': digest(Path(__file__).read_bytes()),
        'files': len(text), 'source_text_bytes': total, 'archive_bytes': len(bundle), 'archive_sha256': digest(bundle),
        'qualification_recomputed': False, 'speed_promotion': False, 'binary_outputs_included': False}
    archive = {'schema': 'ltx25.text-evidence-archive.v1', 'archive': 'evidence.json.gz', 'archive_sha256': digest(bundle),
        'files': inventory, 'encoding': 'gzip of UTF-8 JSON mapping archive-relative paths to exact source text'}
    output.mkdir()
    with (output / 'evidence.json.gz').open('xb') as stream:
        stream.write(bundle)
    for name, value in (('summary.json', summary), ('manifest.json', archive)):
        with (output / name).open('x') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')
    return {'status': 'exported-terminal-text', 'owner_declared_terminal_status': terminal_status,
        'output': str(output), 'files': len(text), 'archive_sha256': digest(bundle)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--terminal-status', choices=('passed', 'failed'), required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.terminal_status), indent=2))

#!/usr/bin/env python3
"""Finite encoder candidate client; never starts, stops, or retries a server."""
import argparse
import copy
import fcntl
import importlib.metadata
import importlib.util
import json
import math
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import urllib.request

LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
CAMPAIGN = 'encoder-screen-01'
PIN = '19e1058f4c445ef74047e77a23f9ca7684c1e4b6'
FROZEN = {
    'profile-clip.py': 'ad0141ff493c8c4cc5993ff4f8c2aceea76c2e99359477c7cef2d24628eb1980',
    'compare-clip.py': '80ee7a45468f95c6c0b8df9ecceea338af9fdf4d2537ba5966603b4f5b03fe0e',
    'run-stability.py': '7769cf87ed005be6e13dc6acced399f1541f68bc988953e7a409ba7fb80937b2',
}
BASELINE_SHA = 'fa3868afb3d81056a776d256e68ed5e239cb501bd8b254af7ff2d33339d742d7'
ARMS = ('control', 'crop', 'small_state', 'combined', 'control')
FIXTURES = ('boat', 'boat', 'marble', 'bird', 'boat')
REFERENCES = {'boat': ('baseline-01', 42), 'marble': ('speed-oracle-marble', 17),
              'bird': ('speed-oracle-bird', 123)}
IDENTITY_FIELDS = ('pid', 'proc_start_ticks', 'boot_id', 'source_commit',
    'source_packet_manifest_sha256', 'source_packet_path', 'encoder_run_dir',
    'extension_sha256s', 'launcher_sha256', 'model_verification_sha256',
    'server_args_sha256', 'torch')


def import_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


retention = import_file('encoder_screen_retention', LANE / 'scripts/run-stability.py')
require, sha, write_json = retention.require, retention.sha, retention.write_json


def schedule():
    return [{'arm': arm_index, 'variant': variant, 'fixture': fixture,
             'initialization': case_index == 0,
             'run': f'{CAMPAIGN}-r{arm_index * 5 + case_index + 1:02d}-{variant.replace("_", "-")}-{fixture}'}
            for arm_index, variant in enumerate(ARMS)
            for case_index, fixture in enumerate(FIXTURES)]


def validate_schedule(rows):
    require(rows == schedule() and len(rows) == 25, 'unreviewed or unbounded schedule')


def expected_graph(base, variant):
    graph = copy.deepcopy(base)
    graph['420']['inputs']['encoder_variant'] = variant
    graph['421'] = {'class_type': 'LTXEncoderPlacementCheck', 'inputs': {
        'clip': ['420', 1], 'conditioning': ['364', 0],
        'run_name': 'encoder-template', 'encoder_variant': variant}}
    graph['365']['inputs']['positive'] = ['421', 0]
    # Original CFG1 negative input references the same conditioning stream.
    graph['365']['inputs']['negative'] = ['421', 0]
    return graph


def normalize_graph(graph):
    graph = retention.normalized(graph)
    if '421' in graph:
        graph['421']['inputs']['run_name'] = '<run>'
    return graph


def validate_graph(graph, base, variant):
    require(normalize_graph(graph) == normalize_graph(expected_graph(base, variant)),
            'graph changed beyond encoder variant/diagnostic passthrough')


def get_json(path):
    with urllib.request.urlopen('http://127.0.0.1:8188' + path, timeout=15) as response:
        return json.load(response)


def validate_identity_values(identity, endpoint, *, packet, manifest_sha, server_run,
                             ticks, boot, model_sha, args_sha, extensions, launcher_sha, torch_version):
    require(endpoint == identity, 'endpoint identity differs from startup file')
    require(all(key in identity for key in IDENTITY_FIELDS), 'incomplete server identity')
    for key, expected in {
        'source_packet_path': str(packet), 'source_packet_manifest_sha256': manifest_sha,
        'encoder_run_dir': str(server_run), 'source_commit': PIN,
        'proc_start_ticks': str(ticks), 'boot_id': boot,
        'model_verification_sha256': model_sha, 'server_args_sha256': args_sha,
        'extension_sha256s': extensions, 'launcher_sha256': launcher_sha,
        'torch': torch_version,
    }.items():
        require(identity[key] == expected, 'server identity binding failed: ' + key)


def identity_binding(packet, manifest_sha, server_run, expected=None):
    import encoder_runtime_common as common
    from encoder_runtime_common import verify_packet, verify_runtime
    manifest = verify_packet(packet, manifest_sha)
    runtime = verify_runtime(manifest['runtime'])
    common.verify_model_receipt()
    require(sha(Path(common.__file__)) == manifest['startup_tools']['encoder_runtime_common.py'],
            'client verifier differs from prepared startup verifier')
    require(not (ROOT / 'FAULT.json').exists(), 'device fault; halt all new requests')
    require(not (server_run / 'FAULT.json').exists(), 'server fault; halt all new requests')
    path = retention.safe_path(server_run, 'server-identity.json')
    identity = json.loads(path.read_text())
    require(type(identity.get('pid')) is int and identity['pid'] > 1, 'invalid server PID')
    pid = identity['pid']
    ticks = Path(f'/proc/{pid}/stat').read_text().split(') ')[1].split()[19]
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    model_path = ROOT / 'model-verification.json'
    require(json.loads(model_path.read_text())['status'] == 'passed', 'model verification failed')
    extensions = {name: sha(packet / 'source/scripts' / name) for name in (
        'resident_node.py', 'ltx_layer_shard.py', 'capture_node.py', 'encoder_diagnostics.py', 'encoder_identity_node.py')}
    validate_identity_values(identity, get_json('/ltx-encoder/identity'), packet=packet,
        manifest_sha=manifest_sha, server_run=server_run, ticks=ticks, boot=boot,
        model_sha=sha(model_path), args_sha=sha(server_run / 'server-args.json'),
        extensions=extensions, launcher_sha=sha(packet / 'launch/serve-encoder.py'),
        torch_version=importlib.metadata.version('torch'))
    require(identity['runtime'] == runtime, 'runtime fingerprint identity changed')
    if expected is not None:
        require(identity == expected, 'server identity changed; no restart or retry')
    queue = get_json('/queue')
    require(queue['queue_running'] == [] and queue['queue_pending'] == [], 'server queue not idle')
    require(shutil.disk_usage(ROOT).free >= 5 * 1024**3, 'less than 5 GiB disk free')
    memory = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    require(int(memory['MemAvailable'].split()[0]) >= 8 * 1024**2, 'less than 8 GiB RAM available')
    for name, digest in FROZEN.items():
        require(sha(LANE / 'scripts' / name) == digest, 'frozen helper changed: ' + name)
    return identity, manifest


def validate_placement(receipt, run, variant, identity_sha, model_sha):
    require(receipt['schema'] == 'ltx.encoder-placement.v1' and receipt['stage'] == 'post_encode',
            'wrong placement receipt schema/stage')
    require(receipt['run_name'] == run and receipt['encoder_variant'] == variant,
            'placement receipt run/variant mismatch')
    require(receipt['passed'] is True and receipt['failures'] == [], 'placement diagnostic failed')
    require(receipt['server_identity_sha256'] == identity_sha and
            receipt['model_verification_sha256'] == model_sha, 'placement identity mismatch')
    accounting = receipt['inspection']['accounting']
    require(accounting['patcher_small_state_option'] == (variant in ('small_state', 'combined')) and
            accounting['crop_option'] == (variant in ('crop', 'combined')), 'observed encoder option mismatch')
    if variant in ('small_state', 'combined'):
        small = receipt['inspection']['small_state']
        require((small['rmsnorm_count'], small['scalar_count'], small['total_bytes']) ==
                (289, 48, 1539680), 'unexpected native small-state census')
        records = small['records']
        require(len(records) == 337 and len({row['name'] for row in records}) == 337,
                'missing/duplicate small-state records')
        require(sum(row['bytes'] for row in records) == 1539680 and
                all(row['device'] == 'xpu:2' and row['dtype'] == 'torch.bfloat16' for row in records),
                'small state not native BF16 resident on XPU2')
        require(sum(row['kind'] == 'rmsnorm' for row in records) == 289 and
                sum(row['kind'] == 'scalar' for row in records) == 48,
                'individual small-state kinds disagree with census')
        require(all(row['bytes'] > 0 and row['bytes'] == 2 * math.prod(row['shape']) and
                    (row['kind'] != 'scalar' or row['shape'] == [1]) for row in records),
                'small-state shape/byte metadata invalid')
        require(accounting['small_buffers_loaded'] and accounting['model_small_state_policy'] and
                not accounting['is_dynamic'] and accounting['reported_loaded_weight_bytes'] >= 1539680,
                'small-state ownership/accounting mismatch')


def run_subprocess(command, log, timeout):
    with log.open('x') as transcript:
        result = subprocess.run(command, stdout=transcript, stderr=subprocess.STDOUT, timeout=timeout)
    require(result.returncode == 0, 'subprocess failed; preserve evidence and halt without retry')


def validate_unload(receipt, previous, current, identity_sha, model_sha):
    require(receipt['schema'] == 'ltx.encoder-unload.v1' and receipt['passed'] is True and
            receipt['failures'] == [], 'encoder unload failed')
    require(receipt['old_generation'] == previous['generation'] and
            receipt['new_generation'] == current['generation'] and
            receipt['old_variant'] == previous['encoder_variant'] and
            receipt['new_variant'] == current['encoder_variant'], 'unload transition mismatch')
    require(receipt['server_identity_sha256'] == identity_sha and
            receipt['model_verification_sha256'] == model_sha, 'unload identity mismatch')
    for group in ('parameters', 'buffers'):
        before, after = receipt['before'][group]['records'], receipt['after'][group]['records']
        def owners(records):
            return {(r['name'], r['dtype'], tuple(r['shape']), r['bytes'], r['owner_id']) for r in records}
        require(len(before) == len(after) == len(owners(before)) and owners(before) == owners(after),
                'encoder registered ownership changed during unload')
        require(all(r['device'] == 'cpu' for r in after), 'encoder tensors remain on device after unload')
    a = receipt['after']['accounting']
    require(a['offload_device'] == 'cpu' and a['reported_loaded_weight_bytes'] == 0 and
            a['reported_offload_buffer_bytes'] == 0 and not a['marked_modules'] and
            not a['small_buffers_loaded'] and not a['model_small_state_policy'], 'unload accounting not cleared')


def latest_components(server_run, variant):
    receipts = []
    for path in server_run.glob('components-*-split-*.json'):
        retention.safe_path(server_run, path.name)
        row = json.loads(path.read_text())
        require(type(row.get('generation')) is int and row['generation'] > 0, 'invalid component generation')
        receipts.append((row['generation'], path, row))
    require(bool(receipts), 'component identity receipt missing')
    require(len({r[0] for r in receipts}) == len(receipts), 'duplicate component generations')
    generation, path, row = max(receipts, key=lambda r: r[0])
    require(row['encoder_variant'] == variant and row['placement'] == 'split', 'component configuration mismatch')
    return row


def run_screen(packet, manifest_sha, server_run):
    rows = schedule()
    validate_schedule(rows)
    base_path = LANE / 'data/speed-resident-split-api.json'
    require(sha(base_path) == BASELINE_SHA, 'frozen baseline graph changed')
    base = json.loads(base_path.read_text())
    identity, manifest = identity_binding(packet, manifest_sha, server_run)
    templates = {}
    for variant in set(ARMS):
        templates[variant] = json.loads((packet / 'graphs' / (variant + '.json')).read_text())
        validate_graph(templates[variant], base, variant)
    fixtures = {}
    for fixture, (reference, seed) in REFERENCES.items():
        reference_graph = json.loads(retention.safe_path(ROOT, Path('requests') / reference / 'prompt.json').read_text())
        require(all(reference_graph[node]['inputs']['noise_seed'] == seed for node in ('338', '339')),
                'protected reference seed mismatch')
        retention.safe_path(ROOT, Path('output/validation') / reference / 'tensors.safetensors')
        fixtures[fixture] = {'reference': reference, 'seed': seed,
                             'prompt': reference_graph['364']['inputs']['text']}
    runs = {row['run'] for row in rows}
    for run in runs:
        for relative in (Path('requests') / run, Path('output') / run, Path('output/validation') / run):
            require(not retention.safe_path(ROOT, relative, exists=False).exists(), 'output already exists')
        require(not retention.safe_path(server_run, f'encoder-placement-{run}.json', exists=False).exists(),
                'placement receipt already exists')
    output = retention.safe_path(ROOT, CAMPAIGN, exists=False)
    output.mkdir(exist_ok=False)
    write_json(output / 'preregistration.json', {
        'campaign': CAMPAIGN, 'max_requests': 25, 'schedule': rows, 'fixtures': fixtures,
        'purpose': 'bounded same-process encoder screen; four warm samples per arm, no promoted speed claim',
        'minimum_output': [256, 256], 'frames': 25, 'fps': 24,
        'initialization': 'first request of each arm includes any component reload/initialization; excluded from warm timing',
        'retention': 'all four tensors compared before pruning raw archive; at most three passed review previews retained',
        'failure_action': 'halt new requests, preserve failure evidence and running server; no retry/restart',
    })
    write_json(output / 'identity.json', identity)
    write_json(output / 'client-identity.json', {'client_sha256': sha(Path(__file__)),
        'frozen_helpers': FROZEN, 'common_sha256': sha(LANE / 'scripts/encoder_runtime_common.py'),
        'source_packet_manifest_sha256': manifest_sha})
    completed, files, deleted = [], {}, set()
    previous_components = None
    current = None
    attempted_run, stage = None, 'preflight'
    try:
        for planned in rows:
            current = None
            attempted_run, stage = planned['run'], 'preflight'
            require(len(completed) < 25, 'hard request bound reached')
            identity_binding(packet, manifest_sha, server_run, identity)
            current = copy.deepcopy(planned)
            fixture = fixtures[current['fixture']]
            run, variant = current['run'], current['variant']
            current.update(status='running', reference=fixture['reference'], before=retention.snapshot(identity['pid']))
            completed.append(current)
            write_json(output / 'progress.json', {'status': 'running', 'rows': completed})
            graph = copy.deepcopy(templates[variant])
            graph['364']['inputs']['text'] = fixture['prompt']
            for node in ('338', '339'):
                graph[node]['inputs']['noise_seed'] = fixture['seed']
            graph['421']['inputs']['run_name'] = run
            graph_path = output / (run + '-graph.json')
            write_json(graph_path, graph)
            command = [sys.executable, str(LANE / 'scripts/profile-clip.py'), run,
                       '--graph', str(graph_path), '--server-run', str(server_run), '--timeout', '600']
            current['command'] = command
            stage = 'request'
            try:
                run_subprocess(command, output / (run + '-client.log'), 650)
            finally:
                try:
                    current['after'] = retention.snapshot(identity['pid'])
                except Exception as snapshot_error:
                    current['after_snapshot_error'] = repr(snapshot_error)
            identity_binding(packet, manifest_sha, server_run, identity)
            stage = 'identity-placement-and-unload-gates'
            request = ROOT / 'requests' / run
            submitted = json.loads((request / 'prompt.json').read_text())
            validate_graph(submitted, base, variant)
            require(submitted['364']['inputs']['text'] == fixture['prompt'] and
                    all(submitted[n]['inputs']['noise_seed'] == fixture['seed'] for n in ('338', '339')),
                    'submitted fixture changed')
            require(submitted['421']['inputs']['run_name'] == run, 'diagnostic execution name mismatch')
            request_identity = json.loads((request / 'identity.json').read_text())
            for field in IDENTITY_FIELDS:
                require(request_identity[field] == identity[field], 'request identity changed: ' + field)
            placement_path = retention.safe_path(server_run, f'encoder-placement-{run}.json')
            placement = json.loads(placement_path.read_text())
            validate_placement(placement, run, variant, sha(server_run / 'server-identity.json'),
                               identity['model_verification_sha256'])
            write_json(output / (run + '-placement.json'), placement)
            components = latest_components(server_run, variant)
            require(components['model_verification_sha256'] == identity['model_verification_sha256'],
                    'component model identity mismatch')
            if previous_components is not None:
                if current['initialization']:
                    require(components['generation'] == previous_components['generation'] + 1,
                            'component generation did not advance once at arm transition')
                    unload_path = retention.safe_path(server_run,
                        f"encoder-unload-{previous_components['generation']:02d}-to-{components['generation']:02d}.json")
                    unload = json.loads(unload_path.read_text())
                    validate_unload(unload, previous_components, components, sha(server_run / 'server-identity.json'),
                                    identity['model_verification_sha256'])
                    write_json(output / (run + '-unload.json'), unload)
                else:
                    require(components == previous_components, 'component identity changed within arm')
            current['components'] = components
            previous_components = components
            # Compare every request, including initialization, before any deletion.
            parity = output / (run + '-parity.json')
            stage = 'oracle-comparison'
            run_subprocess([sys.executable, str(LANE / 'scripts/compare-clip.py'), fixture['reference'], run,
                            '--output', str(parity)], output / (run + '-compare.log'), 120)
            comparison = json.loads(parity.read_text())
            require(comparison['status'] == 'passed' and set(comparison['comparisons']) ==
                    {'images', 'video_latent', 'audio_latent', 'waveform'} and
                    all(x['bitwise_equal'] for x in comparison['comparisons'].values()),
                    'exact four-output oracle comparison failed')
            current['capture'] = retention.validate_capture(ROOT, run)
            current['profile'] = json.loads((request / 'profile.json').read_text())
            require(isinstance(current['profile']['preview_ready_seconds'], (float, int)), 'missing preview latency')
            current['status'] = 'passed'
            current['parity_path'] = str(parity)
            history = json.loads((request / 'history.json').read_text())
            previews = history['outputs']['75']['images']
            require(len(previews) == 1 and previews[0]['type'] == 'output' and previews[0]['subfolder'] == run,
                    'unexpected preview output')
            files[run] = [retention.inventory(ROOT, CAMPAIGN, runs, run,
                Path('output/validation') / run / 'tensors.safetensors'),
                retention.inventory(ROOT, CAMPAIGN, runs, run, Path('output') / run / previews[0]['filename'])]
            write_json(output / 'output-inventory.json', files)
            write_json(output / 'progress.json', {'status': 'running', 'rows': completed})
            stage = 'verified-retention'
            tensor = files[run][0]
            retention.delete_owned(ROOT, CAMPAIGN, runs, tensor, parity_passed=True,
                                   receipts=output / 'deletion-receipts.jsonl')
            deleted.add(tensor['relative_path'])
            pending_previews = [entry for records in files.values() for entry in records
                                if entry['relative_path'].endswith('.mp4') and entry['relative_path'] not in deleted]
            for entry in pending_previews[:-3]:
                retention.delete_owned(ROOT, CAMPAIGN, runs, entry, parity_passed=True,
                                       receipts=output / 'deletion-receipts.jsonl')
                deleted.add(entry['relative_path'])
            print(json.dumps({'run': run, 'status': 'passed', 'completed': len(completed),
                              'initialization': current['initialization'],
                              'preview_ready_seconds': current['profile']['preview_ready_seconds']}), flush=True)
        stage = 'final-identity'
        identity_binding(packet, manifest_sha, server_run, identity)
        summary = {'status': 'passed', 'rows': completed, 'completed_requests': len(completed),
            'speed_promotion': False, 'streaming_qualification': False,
            'screening_only': 'four warm measurements per arm in one process; no fresh-process speed claim',
            'arms': [{'arm': i, 'variant': variant,
                'initialization_preview_seconds': completed[i * 5]['profile']['preview_ready_seconds'],
                'warm_preview_median_seconds': statistics.median(
                    x['profile']['preview_ready_seconds'] for x in completed[i * 5 + 1:i * 5 + 5])}
                for i, variant in enumerate(ARMS)],
            'retained_outputs': [entry for records in files.values() for entry in records
                                 if entry['relative_path'] not in deleted]}
        write_json(output / 'progress.json', summary)
    except BaseException as error:
        if current is not None and current['status'] == 'running':
            current['status'] = 'failed'
        write_json(output / 'progress.json', {'status': 'failed', 'attempted_run': attempted_run,
            'failed_run': current and current['run'], 'failure_stage': stage,
            'rows': completed, 'error': repr(error), 'action': 'halt new requests; preserve server and failure evidence'})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--server-run', type=Path, required=True)
    args = parser.parse_args()
    packet, server_run = args.packet.absolute(), args.server_run.absolute()
    require(packet.parent == ROOT and server_run.parent == ROOT, 'packet/run must be direct evidence children')
    retention.safe_path(ROOT, packet.name)
    retention.safe_path(ROOT, server_run.name)
    with (server_run / 'encoder-screen-client.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run_screen(packet, args.manifest_sha256, server_run)


if __name__ == '__main__':
    main()

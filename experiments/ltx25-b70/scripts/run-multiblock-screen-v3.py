#!/usr/bin/env python3
"""Bounded packet08 all48 one-pass exactness and paired timing screen."""
import argparse
import copy
import fcntl
import importlib.util
import json
import math
import re
from pathlib import Path
import shutil
import statistics
import sys

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PACKET_SHA = 'a32f645772d2ef59d46b66c9181f1d9433950172bcc763924de8aa7acb679b6b'
RECEIPTS_SHA = 'aa72ba88cbce87ebe6f5c8b298112bcd6a72cea046020cab55fe2256a616d124'
SELECTIONS = {'all48': tuple(range(48))}
COLD_TIMEOUTS = {'all48': 7200}
ENCODER_CLIENT_SHA = '4ec94d7e69c3d93b2caa740209f6a84ff35d56bdbbb8bf55f4b9782bacde10b0'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


screen = load('compiler_screen_encoder_helpers', LANE / 'scripts/run-encoder-screen.py')
retention = screen.retention
require, sha, write_json = screen.require, screen.sha, screen.write_json


def campaign_name(value):
    if not isinstance(value, str) or re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', value) is None:
        raise argparse.ArgumentTypeError('campaign must be 1..64 lowercase safe filename characters')
    return value


def schedule(campaign):
    campaign = campaign_name(campaign)
    rows = []
    def append(mode, selection, fixture, qualified_before, initialization=False, pair=None):
        rows.append({'mode': mode, 'selection': selection, 'fixture': fixture,
                     'qualified_before': qualified_before, 'initialization': initialization,
                     'pair': pair,
                     'timeout_seconds': COLD_TIMEOUTS[selection] if mode == 'compiled' and initialization else 1200,
                     'run': f'{campaign}-r{len(rows)+1:02d}-{selection}-{mode}-{fixture}'})
    append('original', 'all48', 'boat', 0, True)
    append('original', 'all48', 'boat', 0)
    for selection in SELECTIONS:
        append('compiled', selection, 'boat', 0, True)
        for fixture in ('boat', 'marble', 'bird'):
            for mode in ('restored', 'compiled', 'restored'):
                append(mode, selection, fixture, 2, pair=selection + '-' + fixture)
    return rows


def expected_graph(base, mode, selection):
    require(mode in ('original', 'compiled', 'restored') and selection in SELECTIONS,
            'Unregistered graph choice')
    graph = screen.expected_graph(base, 'control')
    graph['422'] = {'class_type': 'LTXCompileBlocksGate', 'inputs': {
        'model': ['420', 0], 'mode': mode, 'selection': selection,
        'run_name': 'assign-unique-request-name'}}
    for node in ('388', '391'):
        graph[node]['inputs']['model'] = ['422', 0]
    return graph


def normalized(graph):
    graph = screen.normalize_graph(graph)
    if '422' in graph:
        graph['422']['inputs']['run_name'] = '<run>'
    return graph


def identity_binding(common, packet, manifest_sha, server_run, expected=None):
    manifest = common.verify_packet(packet, manifest_sha)
    runtime = common.verify_runtime(manifest['runtime'])
    common.verify_model_receipt()
    require(sha(Path(common.__file__)) == manifest['startup_tools']['encoder_runtime_common.py'],
            'Packet-local identity verifier differs')
    require(sha(LANE / 'scripts/run-encoder-screen.py') == ENCODER_CLIENT_SHA,
            'Frozen encoder helper changed')
    for name, digest in screen.FROZEN.items():
        require(sha(LANE / 'scripts' / name) == digest, 'Frozen helper changed: ' + name)
    require(not (server_run / 'FAULT.json').exists(), 'Server fault; halt requests')
    identity = json.loads((server_run / 'server-identity.json').read_text())
    pid = identity['pid']
    require(type(pid) is int and pid > 1, 'Invalid server PID')
    screen.validate_identity_values(identity, screen.get_json('/ltx-encoder/identity'),
        packet=packet, manifest_sha=manifest_sha, server_run=server_run,
        ticks=common.process_ticks(pid), boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        model_sha=common.MODEL_VERIFICATION_SHA256, args_sha=sha(server_run / 'server-args.json'),
        extensions={name: sha(packet / 'source/scripts' / name) for name in common.EXTENSIONS},
        launcher_sha=sha(packet / 'launch/serve-encoder.py'), torch_version=runtime['torch'])
    require(identity['runtime'] == runtime and (expected is None or identity == expected),
            'Runtime/server changed; no retry')
    strict = json.loads((server_run / 'determinism-after-import.json').read_text())
    require(strict['enabled'] is True and strict['warn_only'] is False and
            strict['server_identity_sha256'] == sha(server_run / 'server-identity.json'),
            'Strict startup receipt failed')
    queue = screen.get_json('/queue')
    require(not queue['queue_running'] and not queue['queue_pending'], 'Server busy')
    require(shutil.disk_usage(ROOT).free >= 5 * 1024**3, 'Less than 5 GiB disk free')
    mem = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    require(int(mem['MemAvailable'].split()[0]) >= 8 * 1024**2, 'Less than 8 GiB host RAM available')
    return identity, manifest



def receipt_helpers():
    path = LANE / 'scripts/ltx_multiblock_receipts_v3.py'
    require(sha(path) == RECEIPTS_SHA, 'Multiblock receipt validator changed')
    return load('multiblock_receipt_helpers_v3', path)


def validate_owner_continuity(owners, request):
    original = request['original_id']
    require(owners.get('original', original) == original, 'Original model owner changed')
    owners['original'] = original
    selection, candidate = request['selection'], request['candidate_id']
    if candidate is not None:
        require(owners.get(selection, candidate) == candidate, 'Retained selection candidate changed')
        require(all(candidate != value for key, value in owners.items() if key not in ('original', selection)),
                'Different selections unexpectedly share one candidate')
        owners[selection] = candidate
    require(request['retained_candidate_count'] == len(owners) - 1,
            'Retained selection count differs from the completed schedule')


def prepared_sources(args, common):
    require(args.manifest_sha256 == PACKET_SHA, 'Client requires sealed packet08')
    manifest = common.verify_packet(args.packet, args.manifest_sha256)
    common.verify_runtime(manifest['runtime'])
    common.verify_model_receipt()
    require(sha(LANE / 'scripts/run-encoder-screen.py') == ENCODER_CLIENT_SHA, 'Frozen encoder helper changed')
    for name, digest in screen.FROZEN.items():
        require(sha(LANE / 'scripts' / name) == digest, 'Frozen helper changed: ' + name)
    receipt_helpers()
    require(sha(LANE / 'data/speed-resident-split-api.json') == screen.BASELINE_SHA,
            'Original resident graph changed')
    base = json.loads((LANE / 'data/speed-resident-split-api.json').read_text())
    for selection in SELECTIONS:
        for mode in ('original', 'compiled', 'restored'):
            template = json.loads((args.packet / 'graphs' / f'multiblock-{selection}-{mode}.json').read_text())
            require(normalized(template) == normalized(expected_graph(base, mode, selection)),
                    'Packet multiblock graph differs')
    return base, manifest


def paired_results(rows):
    result = {}
    for selection in SELECTIONS:
        triples = []
        for fixture in ('boat', 'marble', 'bird'):
            chosen = [r for r in rows if r.get('pair') == selection + '-' + fixture]
            if len(chosen) != 3 or any(r.get('status') != 'passed' for r in chosen):
                continue
            require([r['mode'] for r in chosen] == ['restored', 'compiled', 'restored'], 'Pair order changed')
            times = [r['profile']['preview_ready_seconds'] for r in chosen]
            require(all(type(value) in (int, float) and math.isfinite(value) and value > 0 for value in times),
                    'Preview timing is invalid')
            mean = (times[0] + times[2]) / 2
            triples.append({'fixture': fixture, 'runs': [r['run'] for r in chosen],
                            'preview_seconds': times, 'control_mean_seconds': mean,
                            'compiled_minus_control_mean_seconds': times[1] - mean,
                            'control_mean_over_compiled': mean / times[1]})
        result[selection] = {'triples': triples, 'paired_samples': len(triples),
            'median_compiled_minus_control_mean_seconds': statistics.median(
                r['compiled_minus_control_mean_seconds'] for r in triples) if triples else None,
            'scope': 'Small matched preview-timing screen; not a promoted speed result or kernel timing'}
    return result


def run_campaign(args, common):
    campaign = campaign_name(args.campaign)
    base, _ = prepared_sources(args, common)
    identity, manifest = identity_binding(common, args.packet, args.manifest_sha256, args.server_run)
    validators = receipt_helpers()
    require(not list(args.server_run.glob('native-multiblock-*')), 'Selection already attempted; no retry')
    identity_sha = sha(args.server_run / 'server-identity.json')
    rows = schedule(campaign)
    require(len(rows) == 12, 'Unbounded compiler schedule')
    fixtures = {}
    for fixture, (reference, seed) in screen.REFERENCES.items():
        graph = json.loads((ROOT / 'requests' / reference / 'prompt.json').read_text())
        require(all(graph[n]['inputs']['noise_seed'] == seed for n in ('338', '339')), 'Reference seed changed')
        retention.safe_path(ROOT, Path('output/validation') / reference / 'tensors.safetensors')
        fixtures[fixture] = {'reference': reference, 'seed': seed, 'prompt': graph['364']['inputs']['text']}
    for row in rows:
        for relative in (Path('requests') / row['run'], Path('output') / row['run'],
                         Path('output/validation') / row['run']):
            require(not retention.safe_path(ROOT, relative, exists=False).exists(), 'Output already exists')
        require(not (args.server_run / ('compiler-' + row['run'])).exists(), 'Compiler receipts already exist')
    output = retention.safe_path(ROOT, campaign, exists=False)
    output.mkdir(exist_ok=False)
    write_json(output / 'preregistration.json', {
        'campaign': campaign, 'schedule': rows, 'max_requests': 12, 'fixtures': fixtures,
        'client_sha256': sha(Path(__file__)), 'encoder_helpers_sha256': ENCODER_CLIENT_SHA,
        'packet_manifest_sha256': args.manifest_sha256, 'identity': identity,
        'scope': 'all48 one-pass registry/state validation; original/compiled/restored in one process, control encoder',
        'receipt_validator_sha256': RECEIPTS_SHA, 'cold_timeout_seconds': COLD_TIMEOUTS,
        'compiler_limits': {'recompile_limit': 8, 'accumulated_recompile_limit': 256},
        'timeout_action': 'stop submissions and preserve server job; timeout is not cancellation',
        'quality': 'strict original four-output bitwise equality after every clip; native compiled gate before accepting candidate',
        'initialization': 'first original and first compiled per selection include initialization; every selected block checks both native shapes',
        'speed_promotion': False, 'streaming_qualification': False,
        'failure_action': 'halt new requests and preserve evidence/process, no retry or restart',
        'retention': 'delete only verified redundant raw archives, keep last three passed previews'})
    completed, files, deleted = [], {}, set()
    runs = {r['run'] for r in rows}
    components, compiler_owners = None, {}
    current, stage = None, 'preflight'
    try:
        for planned in rows:
            current = copy.deepcopy(planned)
            stage = 'preflight'
            identity_binding(common, args.packet, args.manifest_sha256, args.server_run, identity)
            current.update(status='running', before=retention.snapshot(identity['pid']))
            completed.append(current)
            write_json(output / 'progress.json', {'status': 'running', 'rows': completed})
            run, mode = current['run'], current['mode']
            fixture = fixtures[current['fixture']]
            graph = expected_graph(base, mode, current['selection'])
            graph['364']['inputs']['text'] = fixture['prompt']
            for node in ('338', '339'):
                graph[node]['inputs']['noise_seed'] = fixture['seed']
            for node in ('421', '422'):
                graph[node]['inputs']['run_name'] = run
            graph_path = output / (run + '-graph.json')
            write_json(graph_path, graph)
            stage = 'request'
            command = [sys.executable, str(LANE / 'scripts/profile-clip.py'), run,
                       '--graph', str(graph_path), '--server-run', str(args.server_run), '--timeout', str(current['timeout_seconds'])]
            current['command'] = command
            try:
                screen.run_subprocess(command, output / (run + '-client.log'), current['timeout_seconds'] + 60)
            finally:
                current['after'] = retention.snapshot(identity['pid'])
            identity_binding(common, args.packet, args.manifest_sha256, args.server_run, identity)
            stage = 'graph-identity-placement-compiler-gates'
            request = ROOT / 'requests' / run
            submitted = json.loads((request / 'prompt.json').read_text())
            require(normalized(submitted) == normalized(graph), 'Submitted graph differs')
            require(submitted['364']['inputs']['text'] == fixture['prompt'] and
                    all(submitted[n]['inputs']['noise_seed'] == fixture['seed'] for n in ('338', '339')),
                    'Fixture changed')
            require(all(submitted[n]['inputs']['run_name'] == run for n in ('421', '422')), 'Wrong diagnostic name')
            request_identity = json.loads((request / 'identity.json').read_text())
            require(all(request_identity[k] == identity[k] for k in screen.IDENTITY_FIELDS), 'Request identity changed')
            placement = json.loads((args.server_run / ('encoder-placement-' + run + '.json')).read_text())
            screen.validate_placement(placement, run, 'control', identity_sha, identity['model_verification_sha256'])
            observed = screen.latest_components(args.server_run, 'control')
            require(components is None or observed == components, 'Resident components changed within compiler screen')
            components = observed
            current['components'] = components
            current['compiler'] = validators.validate_compiler_receipts(
                args.server_run, run, mode, current['selection'], identity_sha, current['qualified_before'])
            owner = current['compiler']['request']
            validate_owner_continuity(compiler_owners, owner)
            write_json(output / (run + '-placement.json'), placement)
            stage = 'oracle-comparison'
            parity_path = output / (run + '-parity.json')
            screen.run_subprocess([sys.executable, str(LANE / 'scripts/compare-clip.py'), fixture['reference'], run,
                                   '--output', str(parity_path)], output / (run + '-compare.log'), 120)
            parity = json.loads(parity_path.read_text())
            require(parity['status'] == 'passed' and set(parity['comparisons']) ==
                    {'images', 'video_latent', 'audio_latent', 'waveform'} and
                    all(x['bitwise_equal'] for x in parity['comparisons'].values()), 'Original four-output parity failed')
            current['capture'] = retention.validate_capture(ROOT, run)
            current['profile'] = json.loads((request / 'profile.json').read_text())
            current.update(status='passed', reference=fixture['reference'], parity_path=str(parity_path))
            history = json.loads((request / 'history.json').read_text())
            previews = history['outputs']['75']['images']
            require(len(previews) == 1 and previews[0]['type'] == 'output' and previews[0]['subfolder'] == run,
                    'Unexpected preview path')
            files[run] = [retention.inventory(ROOT, campaign, runs, run,
                            Path('output/validation') / run / 'tensors.safetensors'),
                          retention.inventory(ROOT, campaign, runs, run,
                            Path('output') / run / previews[0]['filename'])]
            write_json(output / 'output-inventory.json', files)
            write_json(output / 'progress.json', {'status': 'running', 'rows': completed})
            stage = 'verified-retention'
            to_delete = [files[run][0]]
            previews = [x for records in files.values() for x in records
                        if x['relative_path'].endswith('.mp4') and x['relative_path'] not in deleted]
            to_delete.extend(previews[:-3])
            for entry in to_delete:
                retention.delete_owned(ROOT, campaign, runs, entry, parity_passed=True,
                                       receipts=output / 'deletion-receipts.jsonl')
                deleted.add(entry['relative_path'])
            print(json.dumps({'run': run, 'status': 'passed', 'initialization': current['initialization'],
                              'preview_ready_seconds': current['profile']['preview_ready_seconds']}), flush=True)
        identity_binding(common, args.packet, args.manifest_sha256, args.server_run, identity)
        write_json(output / 'progress.json', {'status': 'passed', 'rows': completed,
            'completed_requests': len(completed), 'paired_results': paired_results(completed), 'speed_promotion': False, 'streaming_qualification': False,
            'retained_outputs': [x for records in files.values() for x in records if x['relative_path'] not in deleted]})
    except BaseException as error:
        if current is not None and current.get('status') == 'running':
            current['status'] = 'failed'
        write_json(output / 'progress.json', {'status': 'failed', 'failure_stage': stage,
            'error': repr(error), 'rows': completed, 'action': 'halt new requests; preserve process/evidence'})
        raise


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=campaign_name, required=True)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--server-run', type=Path, required=True)
    parser.add_argument('--check-only', action='store_true')
    return parser.parse_args(argv)


def main():
    args = parse_args()
    args.packet, args.server_run = args.packet.absolute(), args.server_run.absolute()
    require(args.packet.parent == ROOT and args.server_run.parent == ROOT, 'Invalid packet/server location')
    retention.safe_path(ROOT, args.packet.name)
    retention.safe_path(ROOT, args.server_run.name, exists=not args.check_only)
    common = load('encoder_runtime_common', args.packet / 'launch/encoder_runtime_common.py')
    if args.check_only:
        prepared_sources(args, common)
        print(json.dumps({'status': 'inactive-client-check-passed', 'packet_manifest_sha256': PACKET_SHA,
                          'client_sha256': sha(Path(__file__)), 'receipt_validator_sha256': RECEIPTS_SHA,
                          'schedule': schedule(args.campaign), 'native_requests': 0}, indent=2))
        return
    with (args.server_run / 'encoder-screen-client.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run_campaign(args, common)


if __name__ == '__main__':
    main()

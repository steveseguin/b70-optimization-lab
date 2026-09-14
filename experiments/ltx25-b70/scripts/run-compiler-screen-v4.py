#!/usr/bin/env python3
"""Packet04 native-RMS compiler screen; all v2 gates retained plus two-graph RMS receipts."""
import argparse
import copy
import fcntl
import importlib.util
import json
import re
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
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
    if not isinstance(value, str) or re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', value) is None:
        raise argparse.ArgumentTypeError('campaign must be 1..64 lowercase safe filename characters')
    return value


def schedule(campaign):
    campaign = campaign_name(campaign)
    cases = [('eager', 'boat'), ('eager', 'boat'), ('compiled', 'boat'),
             ('compiled', 'boat'), ('compiled', 'marble'), ('compiled', 'bird'),
             ('compiled', 'boat'), ('restored', 'boat'), ('restored', 'boat')]
    return [{'mode': mode, 'fixture': fixture,
             'initialization': index in (0, 2, 7),
             'qualified_before': 0 if index <= 2 else 2,
             'run': f'{campaign}-r{index + 1:02d}-{mode}-{fixture}'}
            for index, (mode, fixture) in enumerate(cases)]


def expected_graph(base, mode):
    graph = screen.expected_graph(base, 'control')
    graph['422'] = {'class_type': 'LTXCompileOneBlockGate', 'inputs': {
        'model': ['420', 0], 'mode': mode, 'block_index': 24,
        'run_name': 'compiler-template'}}
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



NATIVE_ACTIVATIONS_BACKEND_SHA = '62b78186fdfc6d9a22cb8cb10423869ecc37cc09c9c0994a7ccebe2eafd41c2a'
NATIVE_RMS_BACKEND_SHA = '09defae7340dc3d7f33e16ab80c76f22b6a2ae733617704f2e7b69086108d9fb'
NATIVE_RMS_OPTIONS = {'compile_threads': 1, 'emulate_precision_casts': True,
    'eager_numerics.division_rounding': True, 'triton.cudagraphs': False,
    'max_autotune': False, 'max_autotune_gemm': False}


def validate_native_operation_receipts(server_run):
    directory = retention.safe_path(server_run, 'native-activation-graphs')
    paths = sorted(directory.glob('graph-*.json'))
    require([p.name for p in paths] == ['graph-001.json', 'graph-002.json'],
            'Native RMS requires exactly two graph receipts')
    records = []
    for number, path in enumerate(paths, 1):
        retention.safe_path(directory, path.name)
        row = json.loads(path.read_text())
        require(row.get('schema') == 'ltx25.native-activations-fx-rewrite.v1' and
                row.get('status') == 'compiled-native-activations-boundary' and
                type(row.get('graph')) is int and row['graph'] == number,
                'Native RMS graph schema/status/index failed')
        require(row.get('source_sha256') == NATIVE_ACTIVATIONS_BACKEND_SHA and
                row.get('dependency_sha256') == NATIVE_RMS_BACKEND_SHA and
                row.get('expected_count') == 15 and
                row.get('expected_activation_counts') == {'sigmoid': 6, 'gelu': 2} and
                row.get('options') == NATIVE_RMS_OPTIONS and 'error' not in row,
                'Native RMS backend/options identity failed')
        replacements = row.get('replacements')
        require(isinstance(replacements, list) and len(replacements) == 15,
                'Native RMS graph requires fifteen replacements')
        require(all(isinstance(r, dict) and isinstance(r.get('node'), str) for r in replacements) and
                len({r['node'] for r in replacements}) == 15,
                'Native RMS replacement identities are invalid or duplicated')
        for r in replacements:
            shape, metadata = r.get('normalized_shape'), r.get('input')
            require(isinstance(shape, list) and len(shape) == 1 and shape[0] in (2048, 4096) and
                    isinstance(metadata, dict) and metadata.get('dtype') == 'torch.bfloat16' and
                    metadata.get('device') == 'xpu:1' and metadata.get('contiguous') is True and
                    isinstance(metadata.get('shape'), list) and metadata['shape'][-1:] == shape,
                    'Native RMS input metadata differs from native block')
            require(type(r.get('weighted')) is bool and r.get('eps') == (1e-5 if r['weighted'] else 1e-6),
                    'Native RMS weighting/epsilon changed')
            weight = r.get('weight')
            require((not r['weighted'] and weight is None) or
                    (r['weighted'] and isinstance(weight, dict) and weight.get('shape') == shape and
                     weight.get('dtype') == metadata['dtype'] and weight.get('device') == metadata['device'] and
                     weight.get('contiguous') is True), 'Native RMS weight metadata changed')
        require(sum(r['weighted'] for r in replacements) == 12,
                'Native RMS expected twelve weighted and three unweighted sites')
        activations = row.get('activation_replacements')
        require(isinstance(activations, list) and len(activations) == 8 and
                all(isinstance(r, dict) and isinstance(r.get('node'), str) for r in activations) and
                len({r['node'] for r in activations}) == 8,
                'Native activation replacement count/identities failed')
        require({kind: sum(r.get('kind') == kind for r in activations) for kind in ('sigmoid', 'gelu')} ==
                {'sigmoid': 6, 'gelu': 2}, 'Native activation kind mix changed')
        video_tokens = 64 if number == 1 else 256
        expected_shapes = {'sigmoid': [[1, video_tokens, 32]] * 3 + [[1, 26, 32]] * 3,
                           'gelu': [[1, video_tokens, 16384], [1, 26, 8192]]}
        for kind in ('sigmoid', 'gelu'):
            selected = [r for r in activations if r.get('kind') == kind]
            require(all(isinstance(r.get('input'), dict) for r in selected) and
                    sorted(r['input'].get('shape', []) for r in selected) == sorted(expected_shapes[kind]),
                    'Native activation shape census changed')
            for r in selected:
                metadata = r['input']
                shape = metadata['shape']
                require(metadata.get('dtype') == 'torch.bfloat16' and metadata.get('device') == 'xpu:1' and
                        metadata.get('contiguous') is True and metadata.get('stride') ==
                        [shape[1] * shape[2], shape[2], 1], 'Native activation precision/device/layout changed')
                require((kind == 'gelu' and r.get('approximate') == 'tanh') or
                        (kind == 'sigmoid' and 'approximate' not in r), 'Native activation approximation changed')
        files = {'receipt': sha(path)}
        for phase in ('before', 'after'):
            graph_path = retention.safe_path(directory, f'graph-{number:03d}-{phase}.py')
            require(graph_path.is_file(), 'Native RMS graph source missing')
            files[phase] = sha(graph_path)
        records.append({'graph': number, 'replacements': replacements, 'activation_replacements': activations, 'files': files})
    return records


def validate_compiler_receipts(server_run, run, mode, identity_sha, qualified_before):
    directory = retention.safe_path(server_run, 'compiler-' + run)
    request = json.loads((directory / 'request.json').read_text())
    model_sha = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
    adapter_sha = 'c3f3e4ede85b2798981dca40562bd77586ad63afe55b043c0705fceddda29a1e'
    def bound(row, schema):
        require(row['schema'] == schema and row['run_name'] == run and row['block_index'] == 24 and
                row['server_identity_sha256'] == identity_sha and row['model_verification_sha256'] == model_sha and
                row['passed'] is True and row['failures'] == [], 'Compiler receipt identity/status failed')
    bound(request, 'ltx.compiler-request.v1')
    require(request['qualified_stage_count'] == qualified_before and qualified_before in (0, 2),
            'Compiler qualification differs from preregistered cold/warm position')
    require(type(request['original_id']) is int and request['original_id'] > 0 and
            ((mode == 'eager' and request['candidate_id'] is None) or
             (mode != 'eager' and type(request['candidate_id']) is int and request['candidate_id'] > 0 and
              request['candidate_id'] != request['original_id'])), 'Invalid compiler ownership identity')
    require(request['mode'] == mode and request['adapter_sha256'] == adapter_sha and
            request['compiler_options'] == {'compile_threads': 1, 'emulate_precision_casts': True,
                'eager_numerics.division_rounding': True, 'triton.cudagraphs': False,
                'max_autotune': False, 'max_autotune_gemm': False}, 'Compiler mode/options changed')
    calls = sorted(directory.glob('call-*.json'))
    if mode != 'compiled':
        require(not calls and (mode != 'restored' or request['qualified_stage_count'] == 2),
                'Eager/restored mode has unexpected compiled calls or no qualification')
        return {'request': request, 'calls': []}
    require([p.name for p in calls] == [f'call-{i:02d}.json' for i in range(1, 12)],
            'Expected exactly eleven completed native block calls')
    reports, stage_checks = [], []
    for number, path in enumerate(calls, 1):
        row = json.loads(path.read_text())
        bound(row, 'ltx.compiler-block-call.v1')
        require(row['call'] == number, 'Compiler call ordering differs')
        sig = row['stage_signature']
        require(len(sig) == 2 and sig[0]['shape'] == [1, 64 if number <= 8 else 256, 4096] and
                sig[1]['shape'] == [1, 26, 2048] and
                all(x['dtype'] == 'torch.bfloat16' and x['device'] == 'xpu:1' for x in sig),
                'Native stage shape/device/precision differs')
        delta = row['counter_delta']
        require(sum(delta.get('graph_break', {}).values()) == 0 and
                sum(delta.get('unimplemented', {}).values()) == 0 and
                1 <= delta.get('stats', {}).get('unique_graphs', 0) <= 2,
                'Compiler capture gate failed')
        if row['stage_check']:
            stage_checks.append(number)
            for field in ('eager_vs_compiled', 'compiled_vs_repeat'):
                require(len(row[field]) == 2 and all(x['finite'] is True and x['bitwise_equal'] is True
                                                    for x in row[field]), 'Native block numerical gate failed')
        if number == 1:
            census = row['state_census']
            records = census['records']
            require(len(records) == 84 and len({r['name'] for r in records}) == 84 and
                    sum(r['bytes'] for r in records) == census['bytes'] == 773349760 and
                    census['block_index'] == 24 and census['route_device'] == 'xpu:1' and
                    all(r['dtype'] == 'torch.bfloat16' and r['device'] == 'xpu:1' for r in records),
                    'Native registered block census failed')
        reports.append(row)
    require(stage_checks == ([1, 9] if qualified_before == 0 else []) and
            reports[-1]['qualified_stage_count'] == 2 and
            reports[-1]['counter_delta']['stats']['unique_graphs'] == 2,
            'Both native stages must pass once before warm compiled execution')
    return {'request': request, 'calls': reports,
            'native_operation_graphs': validate_native_operation_receipts(server_run)}


def validate_owner_continuity(previous, current):
    require(previous['original_id'] == current['original_id'], 'Original compiler model owner changed')
    if previous['candidate_id'] is not None:
        require(previous['candidate_id'] == current['candidate_id'], 'Compiled candidate owner changed')


def run_campaign(args, common):
    campaign = campaign_name(args.campaign)
    require(sha(LANE / 'data/speed-resident-split-api.json') == screen.BASELINE_SHA,
            'Original resident graph changed')
    base = json.loads((LANE / 'data/speed-resident-split-api.json').read_text())
    identity, manifest = identity_binding(common, args.packet, args.manifest_sha256, args.server_run)
    for mode in ('eager', 'compiled', 'restored'):
        template = json.loads((args.packet / 'graphs' / ('compiler-' + mode + '.json')).read_text())
        require(normalized(template) == normalized(expected_graph(base, mode)), 'Packet compiler graph differs')
    identity_sha = sha(args.server_run / 'server-identity.json')
    rows = schedule(campaign)
    require(len(rows) == 9, 'Unbounded compiler schedule')
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
        'campaign': campaign, 'schedule': rows, 'max_requests': 9, 'fixtures': fixtures,
        'client_sha256': sha(Path(__file__)), 'encoder_helpers_sha256': ENCODER_CLIENT_SHA,
        'packet_manifest_sha256': args.manifest_sha256, 'identity': identity,
        'scope': 'one native block24, eager/compiled/restored in one process, control encoder',
        'quality': 'strict original four-output bitwise equality after every clip; native compiled gate before accepting candidate',
        'initialization': 'first eager and compiled include initialization; compiled includes two native shape parity checks',
        'speed_promotion': False, 'streaming_qualification': False,
        'failure_action': 'halt new requests and preserve evidence/process, no retry or restart',
        'retention': 'delete only verified redundant raw archives, keep last three passed previews'})
    completed, files, deleted = [], {}, set()
    runs = {r['run'] for r in rows}
    components, compiler_owner = None, None
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
            graph = expected_graph(base, mode)
            graph['364']['inputs']['text'] = fixture['prompt']
            for node in ('338', '339'):
                graph[node]['inputs']['noise_seed'] = fixture['seed']
            for node in ('421', '422'):
                graph[node]['inputs']['run_name'] = run
            graph_path = output / (run + '-graph.json')
            write_json(graph_path, graph)
            stage = 'request'
            command = [sys.executable, str(LANE / 'scripts/profile-clip.py'), run,
                       '--graph', str(graph_path), '--server-run', str(args.server_run), '--timeout', '1200']
            current['command'] = command
            try:
                screen.run_subprocess(command, output / (run + '-client.log'), 1250)
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
            current['compiler'] = validate_compiler_receipts(args.server_run, run, mode, identity_sha,
                                                            current['qualified_before'])
            owner = current['compiler']['request']
            if compiler_owner is not None:
                validate_owner_continuity(compiler_owner, owner)
            compiler_owner = owner
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
            'completed_requests': len(completed), 'speed_promotion': False, 'streaming_qualification': False,
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
    return parser.parse_args(argv)


def main():
    args = parse_args()
    args.packet, args.server_run = args.packet.absolute(), args.server_run.absolute()
    require(args.packet.parent == ROOT and args.server_run.parent == ROOT, 'Invalid packet/server location')
    retention.safe_path(ROOT, args.packet.name)
    retention.safe_path(ROOT, args.server_run.name)
    common = load('encoder_runtime_common', args.packet / 'launch/encoder_runtime_common.py')
    with (args.server_run / 'encoder-screen-client.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run_campaign(args, common)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Inactive packet12 screen: retained nonencoder owners and exact 15-clip gates."""
import argparse
import copy
import fcntl
import importlib.util
import json
import hashlib
import struct
import math
from pathlib import Path
import re
import statistics
import sys

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PARENT_SHA = '34b7ff2f7a74b6951f87dd2621738b37930d15a5de9d064409c8b12351adcf08'
COLD_CONTRACT_SHA = 'f596d6b4ad0f83efce39342a0d4a897aedd267e7df0f2f23f4403e704cb96058'
LIFECYCLE_SHA = 'c9c2d81db33ab5d3174aaaaa87a31c6cf03e5d7923f1b9c305bae554e51ea452'
VALIDATOR_SHA = '8a86a290bfc7a225b86cf3e6fa50bfe985a64aaebd3d5aaa26cef7c95784d490'
CONTRACT_SHA = '80be5c70f42cbe004a0be7af7c8b43a02269d29d9b6fbb6eb53597176b6e4add'
V3_SHA = 'd8054e9866dfb314a5df37415811a5d4a5db79828b0494cca5f3526884ee3114'
EXTENSIONS = {
    'host_embedding_resident_node.py': 'bdaa14a06bd9937946eee470e562f6109df239273e905197d6e94fad28dd02f7',
    'host_embedding_transition_memory.py': '707de7176a47a26063b7282fc7368818d3362b1bd917c76141d58ed00dfcdb86',
    'host_embedding_clip.py': '53d45d883bcc46d1a5889d3b6f162b0e95417e834c62dde8d8836791cffe2994',
    'host_embedding_placement_node.py': '4ab92f1580f8f54ecc6631acd4fb74603d06bc8cf6c3760ede7638c655f5753b',
    'ltx_host_embedding_candidate.py': 'b58bf0bbfc084ea89f2673f3c10d9520b5f6ac1993517c79e346ea2c573ca7e9',
}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


v3 = load('na_axis_v3_helpers', LANE / 'scripts/run-multiblock-screen-v3.py')
screen, retention = v3.screen, v3.retention
require, sha, write_json = screen.require, screen.sha, screen.write_json
validators = load('host_embedding_receipts_v3', LANE / 'scripts/ltx_host_embedding_receipts_v3.py')


def schedule(campaign):
    require(isinstance(campaign, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,47}', campaign), 'Unsafe campaign')
    rows = []
    for generation, (arm, mode) in enumerate((('control-a', 'control'), ('host-table', 'host-table'),
                                            ('control-b', 'control')), 1):
        for ordinal, fixture in enumerate(('boat', 'boat', 'marble', 'bird', 'boat'), 1):
            rows.append({'arm': arm, 'mode': mode, 'generation': generation, 'ordinal': ordinal,
                         'fixture': fixture, 'initialization': ordinal == 1,
                         'run': f'{campaign}-r{len(rows)+1:02d}-{arm}-{fixture}'})
    return rows


def expected_graph(base, mode):
    require(mode in ('control', 'host-table'), 'Unregistered host graph mode')
    graph = screen.expected_graph(base, 'control')
    require('422' not in graph and all(graph[n]['inputs']['model'] == ['420', 0] for n in ('388', '391')) and
            graph['374']['class_type'] == 'VAEDecode', 'Original transformer/decoder required')
    for node, class_name in (('420', 'LTXHostEmbeddingComponents'), ('421', 'LTXHostEmbeddingPlacementCheck')):
        graph[node]['class_type'] = class_name
        del graph[node]['inputs']['encoder_variant']
        graph[node]['inputs']['encoder_mode'] = mode
    graph['421']['inputs']['run_name'] = 'assign-unique-request-name'
    return graph


def normalized(graph):
    return screen.normalize_graph(graph)


def validate_node_info(response, name):
    require(set(response) == {name}, 'Private host node did not load')
    node = response[name]
    if name == 'LTXHostEmbeddingComponents':
        inputs = {'placement': [['split']], 'encoder_mode': [['control', 'host-table']]}
        outputs = ['MODEL', 'CLIP', 'VAE', 'VAE', 'LATENT_UPSCALE_MODEL']
        output_names = ['model', 'clip', 'video_vae', 'audio_vae', 'upscaler']
    else:
        require(name == 'LTXHostEmbeddingPlacementCheck', 'Unknown private node')
        inputs = {'clip': ['CLIP'], 'conditioning': ['CONDITIONING'],
                  'run_name': ['STRING', {'default': 'assign-unique-request-name'}],
                  'encoder_mode': [['control', 'host-table']]}
        outputs = output_names = ['CONDITIONING']
    require(node['input'] == {'required': inputs} and node['output'] == outputs and
            node['output_name'] == output_names and node['output_is_list'] == [False] * len(outputs) and
            node['is_input_list'] is False and node['output_node'] is False and node['name'] == name and
            node['category'] == 'lab/validation' and node['python_module'] == 'custom_nodes.ltx_host_embedding_lab',
            'Private host node interface differs')
    # object_info does not expose FUNCTION; source/manifest pins bind that field.
    return node


def prepared_sources(args, common):
    require(re.fullmatch(r'[a-f0-9]{64}', args.manifest_sha256) is not None and
            args.packet == ROOT / 'prepared-encoder-host-embedding-12', 'Client requires explicit sealed packet12 identity')
    require(isinstance(VALIDATOR_SHA, str) and sha(LANE / 'scripts/ltx_host_embedding_receipts_v3.py') == VALIDATOR_SHA,
            'Receipt validator not frozen or changed')
    require(sha(LANE / 'scripts/run-multiblock-screen-v3.py') == V3_SHA, 'Inherited identity helper changed')
    require(sha(LANE / 'scripts/run-encoder-screen.py') == v3.ENCODER_CLIENT_SHA, 'Encoder helper changed')
    for name, digest in screen.FROZEN.items():
        require(sha(LANE / 'scripts' / name) == digest, 'Frozen helper changed: ' + name)
    manifest = common.verify_packet(args.packet, args.manifest_sha256)
    require(manifest['schema'] == 'ltx.host-embedding-runtime-packet.v2' and
            manifest['parent_manifest_sha256'] == PARENT_SHA, 'Wrong packet12 source ancestry')
    common.verify_runtime(manifest['runtime'])
    common.verify_model_receipt()
    host = manifest['host_embedding']
    require(host['modes'] == ['control', 'host-table'] and host['transformer_dispatch'] == 'original' and
            host['construction_device'] == 'cpu' and host['encoder_load_device'] == 'xpu:2' and
            host['table_device'] == 'cpu' and host['force_full_load'] is False and host['reserve_override'] is False,
            'Prepared host model/loading scope changed')
    require(host['component_receipt_schema'] == 'ltx.host-embedding-components.v2' and
            host['cache_scope'] == 'nonencoder-components-retained; encoder-replaced' and
            host['native_cpu_resident_lifecycle_qualified'] is True, 'Wrong retained-component lifecycle')
    lifecycle = host['admissions']['resident_lifecycle']
    require(lifecycle == {'path': 'provenance/host-transition/cpu-lifecycle-result.json', 'sha256': LIFECYCLE_SHA} and
            sha(retention.safe_path(args.packet, lifecycle['path'])) == LIFECYCLE_SHA, 'Wrong actual CPU lifecycle qualification')
    parent_host = manifest['host_embedding_parent11']
    require(parent_host['extension_sha256s']['host_embedding_resident_node.py'] ==
            'c34129c15bea2639a7916a6a4b2445428c22f2056cf9a7d419dc95b3b2c6ed7b', 'Lost original packet11 lifecycle provenance')
    for name, digest in EXTENSIONS.items():
        require(host['extension_sha256s'][name] == digest and sha(args.packet / 'source/scripts' / name) == digest,
                'Unqualified host source: ' + name)
    require(host['admissions']['cpu_integration']['sha256'] ==
            'b06e617ccb8c307eeb0a8b29981049f30561985480007c85259cca54b7e09326', 'Wrong actual CPU qualification')
    require(sha(LANE / 'data/speed-resident-split-api.json') == screen.BASELINE_SHA, 'Baseline graph changed')
    base = json.loads((LANE / 'data/speed-resident-split-api.json').read_text())
    for mode in ('control', 'host-table'):
        graph = json.loads((args.packet / 'graphs' / ('host-embedding-' + mode + '.json')).read_text())
        require(normalized(graph) == normalized(expected_graph(base, mode)), 'Graph changed beyond CLIP components/gate')
    path = LANE / 'data/host-embedding-registered-contract-01.json'
    require(sha(path) == CONTRACT_SHA, 'Original registration contract changed')
    contract = json.loads(path.read_text())
    require(sha(Path(contract['source_path'])) == contract['source_sha256'], 'Original placement provenance changed')
    require(isinstance(COLD_CONTRACT_SHA, str) and sha(LANE / 'data/host-embedding-cold-memory-contract-01.json') == COLD_CONTRACT_SHA,
            'Cold source-memory contract not frozen or changed')
    if args.check_only:
        cold_source_identity()
    return base, manifest, contract


def paired_results(rows):
    pairs = []
    # Match warm positions, including both newly recomputed boat repetitions.
    for ordinal in (2, 3, 4, 5):
        chosen = [r for r in rows if r['ordinal'] == ordinal]
        if len(chosen) != 3 or any(r['status'] != 'passed' for r in chosen):
            continue
        require([r['arm'] for r in chosen] == ['control-a', 'host-table', 'control-b'] and
                len({r['fixture'] for r in chosen}) == 1, 'Matched arm order/fixture changed')
        metrics = {}
        for metric in ('preview_ready_seconds', 'encoder_node_seconds'):
            times = [r[metric] for r in chosen]
            require(all(type(t) in (int, float) and math.isfinite(t) and t > 0 for t in times), 'Invalid timing')
            control_mean = (times[0] + times[2]) / 2
            metrics[metric] = {'seconds': times, 'control_mean': control_mean,
                               'host_minus_control_mean': times[1] - control_mean}
        pairs.append({'fixture': chosen[0]['fixture'], 'ordinal': ordinal,
                      'runs': [r['run'] for r in chosen], 'metrics': metrics})
    return {'pairs': pairs, 'paired_samples': len(pairs),
            'scope': 'Warm positions bracketed by control arms; repeated boat is not an independent fixture; client event intervals, no promotion'}


def run_with_post_snapshot(run_call, snapshot_call, record):
    """Preserve the request error as primary; snapshot diagnostics are secondary."""
    try:
        run_call()
    except BaseException:
        try:
            record['after'] = snapshot_call()
        except BaseException as snapshot_error:
            record['after_snapshot_error'] = {'error': repr(snapshot_error),
                                              'scope': 'secondary diagnostic failure after request failed'}
        raise
    else:
        # A failed postflight remains fatal even when the request returned.
        record['after'] = snapshot_call()


def cold_header(model, expected):
    require(model.is_file() and not model.is_symlink(), 'Cold model must be a regular original file')
    before = model.stat()
    with model.open('rb') as stream:
        prefix = stream.read(8)
        require(len(prefix) == 8, 'Incomplete model header length')
        length, = struct.unpack('<Q', prefix)
        require(length == expected['header_bytes'] and 0 < length < 16 * 1024**2, 'Model header length changed')
        header = stream.read(length)
    after = model.stat()
    require(all(getattr(before,k) == getattr(after,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),
            'Model changed during bounded header read')
    digest = hashlib.sha256(header).hexdigest()
    require(len(header) == length and digest == expected['header_sha256'] and
            after.st_size == expected['file_bytes'] == 8 + length + expected['tensor_payload_bytes'],
            'Model header identity or declared extent changed: ' + str(model))
    return {'path':str(model),'header_sha256':digest,'header_bytes':length,'file_bytes':after.st_size}


def cold_source_identity():
    path = LANE / 'data/host-embedding-cold-memory-contract-01.json'
    require(sha(path) == COLD_CONTRACT_SHA, 'Cold source contract changed')
    contract = json.loads(path.read_text())
    for name, digest in {**contract['source_sha256s'], **contract['saved_evidence_sha256s']}.items():
        require(sha(Path(name)) == digest, 'Cold source/evidence closure changed: ' + name)
    headers = {}
    require(set(contract['headers']) == {'diffusion','clip','video_vae','audio_vae','upscaler'}, 'Cold model set changed')
    for name, expected in contract['headers'].items():
        headers[name] = cold_header(Path(expected['path']), expected)
    return contract, {'source_contract_sha256':COLD_CONTRACT_SHA,'headers':headers,
        'source_and_saved_evidence_hashes_match':True,'full_weight_payload_rehashed':False,
        'scope':'Current bounded header/source identity; saved model-verification and four exact raw oracles remain required'}


def cold_server_args(args, common):
    packet, run = args.packet, args.server_run
    expected = [str(packet / 'source/main.py'), '--listen', '127.0.0.1', '--port', '8188',
        '--disable-auto-launch', '--cache-none', '--deterministic', '--disable-async-offload',
        '--disable-dynamic-vram', '--disable-comfy-compiler', '--disable-cuda-graphs', '--disable-pinned-memory',
        '--reserve-vram', '6', '--bf16-unet', '--bf16-text-enc', '--bf16-vae', '--use-pytorch-cross-attention',
        '--disable-xformers', '--disable-api-nodes', '--extra-model-paths-config', str(packet / 'model-paths.yaml'),
        '--output-directory', str(common.ROOT / 'output'), '--user-directory', str(run / 'user'),
        '--temp-directory', str(run / 'temp'), '--input-directory', str(run / 'input'),
        '--disable-all-custom-nodes', '--whitelist-custom-nodes', *common.NODES]
    require(json.loads((run/'server-args.json').read_text()) == expected, 'Audited cold initialization server flags changed')
    return sha(run/'server-args.json')


def cold_admission(server_sha, args, common):
    contract, source_identity = cold_source_identity()
    args_sha = cold_server_args(args, common)
    raw = Path('/proc/meminfo').read_text()
    fields = dict(line.split(':', 1) for line in raw.splitlines())
    values = {}
    for key in ('MemTotal', 'MemAvailable', 'MemFree', 'SwapFree', 'SwapTotal'):
        parts = fields[key].split()
        require(len(parts) == 2 and parts[1] == 'kB' and parts[0].isdigit(), 'Malformed current meminfo')
        values[key] = int(parts[0]) * 1024
    report = {'schema': 'ltx.host-embedding-cold-memory-admission.v1',
        'stage': 'before-initial-component-allocation', 'server_identity_sha256': server_sha,
        'source_contract_sha256': COLD_CONTRACT_SHA, 'required_available_bytes': 103102806218,
        'source_identity':source_identity, 'server_args_sha256':args_sha,
        'observed': {'source': '/proc/meminfo', 'raw': raw, 'bytes': values},
        'passed': values['MemAvailable'] >= 103102806218,
        'swap_counted_as_headroom': False, 'runtime_memory_settings_changed': False}
    validators.cold_memory(report, contract, COLD_CONTRACT_SHA, server_sha, require_pass=False)
    return report


def run_campaign(args, common):
    base, manifest, contract = prepared_sources(args, common)
    identity, _ = v3.identity_binding(common, args.packet, args.manifest_sha256, args.server_run)
    node_info = {name: validate_node_info(screen.get_json('/object_info/' + name), name)
                 for name in ('LTXHostEmbeddingComponents', 'LTXHostEmbeddingPlacementCheck')}
    identity_sha = sha(args.server_run / 'server-identity.json')
    require(not list(args.server_run.glob('host-components-*')) and not list(args.server_run.glob('host-embedding-placement-*')) and
            not list(args.server_run.glob('na-axis-*')) and not list(args.server_run.glob('native-multiblock-*')),
            'This server already attempted candidate work; no automatic retry')
    rows = schedule(args.campaign)
    require(len(rows) == 15, 'Unbounded schedule')
    fixtures = {}
    for name, (reference, seed) in screen.REFERENCES.items():
        graph = json.loads(retention.safe_path(ROOT, Path('requests') / reference / 'prompt.json').read_text())
        require(all(graph[n]['inputs']['noise_seed'] == seed for n in ('338', '339')), 'Reference seed differs')
        retention.safe_path(ROOT, Path('output/validation') / reference / 'tensors.safetensors')
        fixtures[name] = {'reference': reference, 'seed': seed, 'prompt': graph['364']['inputs']['text']}
    for row in rows:
        for path in (Path('requests') / row['run'], Path('output') / row['run'],
                     Path('output/validation') / row['run']):
            require(not retention.safe_path(ROOT, path, exists=False).exists(), 'Output collision')
        require(not retention.safe_path(args.server_run, 'host-embedding-placement-' + row['run'] + '.json', exists=False).exists(), 'Receipt collision')
    output = retention.safe_path(ROOT, args.campaign, exists=False)
    output.mkdir(exist_ok=False)
    write_json(output / 'preregistration.json', {'campaign': args.campaign, 'schedule': rows, 'max_requests': 15,
        'fixtures': fixtures, 'identity': identity, 'packet_manifest_sha256': args.manifest_sha256,
        'client_sha256': sha(Path(__file__)), 'validator_sha256': VALIDATOR_SHA,
        'inherited_v3_sha256': V3_SHA, 'frozen_helpers': screen.FROZEN, 'registered_contract_sha256': CONTRACT_SHA,
        'loaded_node_info': node_info,
        'registered_contract': contract, 'cold_memory_contract_sha256': COLD_CONTRACT_SHA,
        'scope': 'original transformer/decoder; control/host-table/control, initialization excluded from timing pairs',
        'failure_action': 'halt new requests; preserve geometry/ownership/parity failure; no retry or gate widening',
        'timeout_action': 'halt client submissions, preserve running server request; timeout is not cancellation',
        'retention': 'delete only own verified redundant raw archives; retain latest3 passing previews',
        'speed_promotion': False, 'streaming_qualification': False})
    completed, inventory, deleted = [], {}, set()
    previous, components, prior_components = None, None, None
    runs = {row['run'] for row in rows}
    current, stage = None, 'preflight'
    try:
        for plan in rows:
            current, stage = copy.deepcopy(plan), 'preflight'
            v3.identity_binding(common, args.packet, args.manifest_sha256, args.server_run, identity)
            require({name: validate_node_info(screen.get_json('/object_info/' + name), name) for name in node_info} == node_info,
                    'Private host node registration changed')
            current.update(status='running', before=retention.snapshot(identity['pid']))
            completed.append(current)
            write_json(output / 'progress.json', {'status': 'running', 'rows': completed})
            run, mode = current['run'], current['mode']
            fixture = fixtures[current['fixture']]
            graph = expected_graph(base, mode)
            graph['364']['inputs']['text'] = fixture['prompt']
            for node in ('338', '339'):
                graph[node]['inputs']['noise_seed'] = fixture['seed']
            graph['421']['inputs']['run_name'] = run
            graph_path = output / (run + '-graph.json')
            write_json(graph_path, graph)
            if current['generation'] == 1 and current['initialization']:
                require(not list(args.server_run.glob('host-components-*')), 'Cold admission requires initial component generation')
                require(screen.get_json('/queue') == {'queue_running': [], 'queue_pending': []}, 'Cold admission requires idle queue')
                current['cold_memory_admission'] = cold_admission(identity_sha, args, common)
                write_json(output / 'cold-memory-admission.json', current['cold_memory_admission'])
                require(current['cold_memory_admission']['passed'], 'Insufficient source-budgeted host RAM for cold initialization')
            stage = 'request'
            command = [sys.executable, str(LANE / 'scripts/profile-clip.py'), run, '--graph', str(graph_path),
                       '--server-run', str(args.server_run), '--timeout', '1200']
            current['command'] = command
            run_with_post_snapshot(
                lambda: screen.run_subprocess(command, output / (run + '-client.log'), 1260),
                lambda: retention.snapshot(identity['pid']), current)
            v3.identity_binding(common, args.packet, args.manifest_sha256, args.server_run, identity)
            stage = 'graph-placement-retirement-gates'
            request = ROOT / 'requests' / run
            submitted = json.loads((request / 'prompt.json').read_text())
            require(normalized(submitted) == normalized(graph), 'Submitted graph differs')
            require(submitted['364']['inputs']['text'] == fixture['prompt'] and
                    all(submitted[n]['inputs']['noise_seed'] == fixture['seed'] for n in ('338', '339')) and
                    submitted['421']['inputs']['run_name'] == run and
                    submitted['414']['inputs']['run_name'] == run and
                    submitted['75']['inputs']['filename_prefix'] == run + '/preview', 'Submitted fixture/output identity differs')
            request_identity = json.loads((request / 'identity.json').read_text())
            require(all(request_identity[k] == identity[k] for k in screen.IDENTITY_FIELDS), 'Request server changed')
            placement = json.loads(retention.safe_path(args.server_run, 'host-embedding-placement-' + run + '.json').read_text())
            prefix = f"host-components-{current['generation']:02d}-{mode}"
            started = json.loads(retention.safe_path(args.server_run, prefix + '-started.json').read_text())
            observed = json.loads(retention.safe_path(args.server_run, prefix + '-result.json').read_text())
            validators.component(started, observed, contract=contract, mode=mode, generation=current['generation'],
                                 server_sha=identity_sha, model_sha=identity['model_verification_sha256'],
                                 previous_component=components if current['initialization'] else prior_components)
            if current['initialization']:
                retirement = None
                if components is not None:
                    retirement = json.loads(retention.safe_path(args.server_run, prefix + '-unload.json').read_text())
                    current['retirement_validation'] = validators.unload(retirement, contract=contract, previous=previous,
                        old_generation=current['generation'] - 1, new_generation=current['generation'], mode=mode,
                        server_sha=identity_sha, model_sha=identity['model_verification_sha256'])
                    write_json(output / (prefix + '-unload.json'), retirement)
                    release = json.loads(retention.safe_path(args.server_run, prefix + '-retired-owner-release.json').read_text())
                    current['release_validation'] = validators.released(release, previous_mode=previous['mode'],
                        old_generation=current['generation'] - 1, new_generation=current['generation'],
                        shared=components['shared_owner_ids'], server_sha=identity_sha,
                        model_sha=identity['model_verification_sha256'])
                    write_json(output / (prefix + '-retired-owner-release.json'), release)
                else:
                    require(current['generation'] == 1 and not (args.server_run / (prefix + '-unload.json')).exists(),
                            'Initial component unexpectedly has prior ownership')
                stages = ['before-construction', 'after-construction']
                if retirement is not None:
                    stages += ['before-restore', 'after-release']
                memory_reports = {}
                for memory_stage in stages:
                    filename = prefix + '-' + memory_stage + '-memory.json'
                    memory_reports[memory_stage] = json.loads(retention.safe_path(args.server_run, filename).read_text())
                    write_json(output / filename, memory_reports[memory_stage])
                current['memory_validations'] = validators.transition_memory(observed, retirement, memory_reports)
                prior_components, components, previous = components, observed, None
                write_json(output / (prefix + '-started.json'), started)
                write_json(output / (prefix + '-result.json'), observed)
            else:
                require(components == observed, 'Resident component generation changed within arm')
            current['placement_validation'] = validators.placement(placement, contract=contract, run=run, mode=mode,
                ordinal=current['ordinal'], server_sha=identity_sha, model_sha=identity['model_verification_sha256'],
                initial=components['encoder_initial_ownership'], previous=previous)
            write_json(output / (run + '-placement.json'), placement)
            current['component_generation'] = components['generation']
            previous = placement
            stage = 'four-output-oracle'
            parity_path = output / (run + '-parity.json')
            screen.run_subprocess([sys.executable, str(LANE / 'scripts/compare-clip.py'), fixture['reference'], run,
                '--output', str(parity_path)], output / (run + '-compare.log'), 120)
            parity = json.loads(parity_path.read_text())
            require(parity['status'] == 'passed' and set(parity['comparisons']) ==
                    {'images', 'video_latent', 'audio_latent', 'waveform'} and
                    all(x['bitwise_equal'] is True for x in parity['comparisons'].values()), 'Original raw parity failed')
            current['capture'] = retention.validate_capture(ROOT, run)
            profile = json.loads((request / 'profile.json').read_text())
            encoder_rows = [row for row in profile['nodes'] if row['node'] == '364']
            require(len(encoder_rows) == 1, 'Missing/unexpected encoder profile intervals')
            current.update(reference=fixture['reference'], parity_path=str(parity_path), profile=profile,
                preview_ready_seconds=profile['preview_ready_seconds'], encoder_node_seconds=encoder_rows[0]['seconds'])
            stage = 'verified-retention'
            history = json.loads((request / 'history.json').read_text())
            previews = history['outputs']['75']['images']
            require(len(previews) == 1 and previews[0]['type'] == 'output' and previews[0]['subfolder'] == run,
                    'Unexpected preview path')
            inventory[run] = [retention.inventory(ROOT, args.campaign, runs, run, Path('output/validation') / run / 'tensors.safetensors'),
                              retention.inventory(ROOT, args.campaign, runs, run, Path('output') / run / previews[0]['filename'])]
            write_json(output / 'output-inventory.json', inventory)
            eligible = [entry for records in inventory.values() for entry in records
                        if entry['relative_path'].endswith('.mp4') and entry['relative_path'] not in deleted]
            for entry in [inventory[run][0], *eligible[:-3]]:
                retention.delete_owned(ROOT, args.campaign, runs, entry, parity_passed=True,
                                       receipts=output / 'deletion-receipts.jsonl')
                deleted.add(entry['relative_path'])
            current['status'] = 'passed'
            write_json(output / 'progress.json', {'status': 'running', 'rows': completed})
            print(json.dumps({'run': run, 'status': 'passed', 'preview_seconds': current['preview_ready_seconds']}), flush=True)
        v3.identity_binding(common, args.packet, args.manifest_sha256, args.server_run, identity)
        write_json(output / 'progress.json', {'status': 'passed', 'rows': completed, 'completed_requests': len(completed),
            'paired_results': paired_results(completed), 'speed_promotion': False, 'streaming_qualification': False,
            'retained_outputs': [entry for records in inventory.values() for entry in records if entry['relative_path'] not in deleted]})
    except BaseException as error:
        if current is not None:
            current['status'] = 'failed'
        write_json(output / 'progress.json', {'status': 'failed', 'failure_stage': stage, 'error': repr(error),
            'rows': completed, 'action': 'halt new requests; preserve process/evidence'})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', required=True)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--server-run', type=Path, required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    schedule(args.campaign)
    args.packet, args.server_run = args.packet.absolute(), args.server_run.absolute()
    require(args.packet.parent == ROOT and args.server_run.parent == ROOT, 'Unexpected packet/server paths')
    retention.safe_path(ROOT, args.packet.name)
    retention.safe_path(ROOT, args.server_run.name, exists=not args.check_only)
    common = load('encoder_runtime_common', args.packet / 'launch/encoder_runtime_common.py')
    if args.check_only:
        _, _, contract = prepared_sources(args, common)
        print(json.dumps({'status': 'source-check-passed', 'native_requests': 0, 'schedule': schedule(args.campaign),
                          'registered_parameters': len(contract['parameters']), 'registered_buffers': len(contract['buffers'])}, indent=2))
        return
    with (args.server_run / 'encoder-screen-client.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run_campaign(args, common)


if __name__ == '__main__':
    main()

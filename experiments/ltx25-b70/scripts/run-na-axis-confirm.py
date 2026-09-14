#!/usr/bin/env python3
"""Bounded18-request confirmation on the already-qualified packet10 process."""
import argparse
import copy
import fcntl
import importlib.util
import json
import math
from pathlib import Path
import re
import statistics
import sys

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PARENT_SHA = 'a32f645772d2ef59d46b66c9181f1d9433950172bcc763924de8aa7acb679b6b'
PACKET_SHA = 'd6ec6c63869d30dbe009708095f53811372e228becf16b7475ad30d11213fe6a'
VALIDATOR_SHA = 'ac11e8fc95275660d76336cafd892a6ec67e0c4f68b0208f5752a328b254274c'
V3_SHA = 'd8054e9866dfb314a5df37415811a5d4a5db79828b0494cca5f3526884ee3114'
ROUTER_SHA = '9aa3d6cc7be389555d60119ad3fd5960b762568e044eba49760fc03114c2b537'
NODE_SHA = 'ffd7549d29828a11f336f07873f63a407df7722328df519f2bec3514964ad32b'
FAILED09_SHA = 'a53e06ae5bd1be8931eff11d4e9112b850912147b37fcabf1bda064b12f419ed'
PRIOR_CLIENT_SHA = '28fd569ab0acecb10a9b59821a707eb917d80bb013bdb973d046a8e6ad074988'
ADMISSION_SHA = '2ee3f7d064454137a4192370cbf4e86247cbc5dd9f79c8c3de59cb9380210e0a'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


v3 = load('na_axis_v3_helpers', LANE / 'scripts/run-multiblock-screen-v3.py')
screen, retention = v3.screen, v3.retention
require, sha, write_json = screen.require, screen.sha, screen.write_json
validators = load('na_axis_receipts', LANE / 'scripts/ltx_na_axis_receipts.py')
prior = load('na_axis_completed_client', LANE / 'scripts/run-na-axis-screen-v2.py')
admission_helpers = load('na_axis_confirmation_admission', LANE / 'scripts/ltx_na_axis_confirmation.py')


BLOCKS = (('boat', 'OCO'), ('marble', 'COC'), ('bird', 'OCO'),
          ('bird', 'COC'), ('marble', 'OCO'), ('boat', 'COC'))


def schedule(campaign):
    require(isinstance(campaign, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,47}', campaign), 'Unsafe campaign')
    rows = []
    for block, (fixture, order) in enumerate(BLOCKS):
        for letter in order:
            mode = 'original' if letter == 'O' else 'axis-cache'
            rows.append({'mode': mode, 'fixture': fixture, 'pair': f'{block+1:02d}-{fixture}-{order.lower()}',
                'order': order, 'initialization': False,
                'run': f'{campaign}-r{len(rows)+1:02d}-{mode}-{fixture}'})
    return rows


def expected_graph(base, mode):
    require(mode in ('bare', 'original', 'axis-cache'), 'Unregistered NA graph mode')
    graph = screen.expected_graph(base, 'control')
    require('422' not in graph and all(graph[n]['inputs']['model'] == ['420', 0] for n in ('388', '391')),
            'Transformer must use original direct dispatch')
    require(graph['374']['class_type'] == 'VAEDecode', 'Unexpected original decoder node')
    if mode != 'bare':
        graph['374']['class_type'] = 'LTXNAAxisDecode'
        graph['374']['inputs'].update(mode=mode, run_name='assign-unique-request-name')
    return graph


def normalized(graph):
    result = screen.normalize_graph(graph)
    if result['374']['class_type'] == 'LTXNAAxisDecode':
        result['374']['inputs']['run_name'] = '<run>'
    return result


def validate_node_info(response):
    require(set(response) == {'LTXNAAxisDecode'}, 'Private decoder node did not load')
    node = response['LTXNAAxisDecode']
    expected = {'required': {
        'samples': ['LATENT', {'tooltip': 'The latent to be decoded.'}],
        'vae': ['VAE', {'tooltip': 'The VAE model used for decoding the latent.'}],
        'mode': [['original', 'axis-cache']],
        'run_name': ['STRING', {'default': 'assign-unique-request-name'}]}}
    require(node['input'] == expected and node['output'] == ['IMAGE'] and node['output_is_list'] == [False] and
            node['is_input_list'] is False and node['output_node'] is False and
            node['name'] == 'LTXNAAxisDecode' and node['category'] == 'lab/validation' and
            node['python_module'] == 'custom_nodes.ltx_na_axis_decode_lab', 'Loaded decoder node interface differs')
    # Legacy object_info does not expose FUNCTION; the pinned node source sets
    # FUNCTION=decode. The endpoint check establishes successful registration.
    return node


def source_identity(packet):
    files = {'node_sha256': 'scripts/na_axis_decode_node.py',
             'router_sha256': 'scripts/ltx_na_axis_router.py',
             'candidate_sha256': 'scripts/ltx_na_axis_candidate.py',
             'nodes_sha256': 'nodes.py', 'sd_sha256': 'comfy/sd.py',
             'decoder_sha256': 'comfy/ldm/lightricks/vae/na_diffusion_decoder.py'}
    values = {key: sha(packet / 'source' / path) for key, path in files.items()}
    require(values['router_sha256'] == ROUTER_SHA and values['candidate_sha256'] == validators.CANDIDATE_SHA,
            'Unreviewed NA implementation')
    values.update(original_na_sha256=validators.ORIGINAL_SHA,
                  decoder_seed_contract={'source_fixed_seed': 0, 'observed_rng_state': False})
    return values


def validate_source_closure(manifest, sources):
    require(sources['node_sha256'] == NODE_SHA and manifest['na_axis']['node_sha256'] == NODE_SHA,
            'Corrected packet10 node identity differs')
    closure = manifest['na_axis']['source_pin_closure']
    require(closure['status'] == 'passed-stdlib-source-pin-closure' and
            closure['native_imports'] is False and closure['startup_registration_qualified'] is False,
            'Missing stdlib startup-pin closure; source closure cannot claim registration')
    expected = {'NODES_SHA': sources['nodes_sha256'], 'SD_SHA': sources['sd_sha256'],
        'DECODER_SHA': sources['decoder_sha256'], 'ROUTER_SHA': sources['router_sha256'],
        'CANDIDATE_SHA': sources['candidate_sha256'], 'router.ORIGINAL_SHA': validators.ORIGINAL_SHA,
        'router.CANDIDATE_SHA': validators.CANDIDATE_SHA}
    require(set(closure['dependencies']) == set(expected), 'Incomplete startup dependency closure')
    for name, value in expected.items():
        require(closure['dependencies'][name] == {'declared_sha256': value, 'actual_sha256': value},
                'Startup declared pin differs from actual packet dependency: ' + name)
    correction = manifest['na_axis_correction']
    require(correction['failed_packet_manifest_sha256'] == FAILED09_SHA and
            correction['reason'] == 'startup-pin-mismatch-before-native-requests', 'Wrong correction provenance')
    require(set(correction['files']) == {'failed09-manifest.json', 'failed09-startup-failure.json',
                                       'failed09-startup-failure.log'}, 'Missing failed09 evidence')
    require(correction['files']['failed09-manifest.json'] == FAILED09_SHA, 'Failed09 manifest differs')
    for name, digest in correction['files'].items():
        require(manifest['files']['provenance/na-axis-correction/' + name] == digest,
                'Correction evidence differs from packet inventory')


def prepared_sources(args, common):
    require(sha(LANE / 'scripts/run-na-axis-screen-v2.py') == PRIOR_CLIENT_SHA, 'Prior screen client changed')
    require(isinstance(ADMISSION_SHA, str) and sha(LANE / 'scripts/ltx_na_axis_confirmation.py') == ADMISSION_SHA,
            'Confirmation admission helper not pinned or changed')
    require(isinstance(PACKET_SHA, str) and args.manifest_sha256 == PACKET_SHA,
            'Client is inactive until the reviewed10 manifest is pinned')
    require(isinstance(VALIDATOR_SHA, str) and sha(LANE / 'scripts/ltx_na_axis_receipts.py') == VALIDATOR_SHA,
            'NA receipt validator is not pinned or changed')
    require(sha(LANE / 'scripts/run-multiblock-screen-v3.py') == V3_SHA, 'Inherited identity helper changed')
    require(sha(LANE / 'scripts/run-encoder-screen.py') == v3.ENCODER_CLIENT_SHA, 'Encoder helper changed')
    for name, digest in screen.FROZEN.items():
        require(sha(LANE / 'scripts' / name) == digest, 'Frozen helper changed: ' + name)
    manifest = common.verify_packet(args.packet, args.manifest_sha256)
    require(manifest['schema'] == 'ltx.na-axis-runtime-packet.v2', 'Wrong runtime packet schema')
    require(manifest['parent_manifest_sha256'] == PARENT_SHA, 'Wrong packet08 parent')
    common.verify_runtime(manifest['runtime'])
    common.verify_model_receipt()
    require(sha(LANE / 'data/speed-resident-split-api.json') == screen.BASELINE_SHA, 'Baseline graph changed')
    base = json.loads((LANE / 'data/speed-resident-split-api.json').read_text())
    for mode in ('bare', 'original', 'axis-cache'):
        name = 'control.json' if mode == 'bare' else 'na-axis-' + mode + '.json'
        graph = json.loads((args.packet / 'graphs' / name).read_text())
        require(normalized(graph) == normalized(expected_graph(base, mode)), 'Packet graph changed beyond decoder scope')
    source = args.packet / 'source'
    contract = validators.source_contract((source / 'comfy/ldm/lightricks/vae/na_diffusion_decoder.py').read_text(),
        (source / 'comfy/sd.py').read_text(), validators.checkpoint_config(
            '/mnt/fast-ai/llm-models/LTX-2.5-baseline/vae/ltx-2.5-video-vae-bf16.safetensors'))
    sources = source_identity(args.packet)
    # verify_packet recomputes these declared-versus-actual dependencies in its
    # generated stdlib checker; also bind the returned receipt to our source view.
    validate_source_closure(manifest, sources)
    return base, manifest, contract, sources


def paired_results(rows):
    triples = []
    for block, (fixture, order) in enumerate(BLOCKS):
        pair = f'{block+1:02d}-{fixture}-{order.lower()}'
        chosen = [r for r in rows if r.get('pair') == pair]
        if len(chosen) != 3 or any(r.get('status') != 'passed' for r in chosen):
            continue
        modes = ['original' if letter == 'O' else 'axis-cache' for letter in order]
        require([r['mode'] for r in chosen] == modes and all(r['order'] == order for r in chosen), 'Pair order changed')
        metrics = {}
        for metric in ('preview_ready_seconds', 'decoder_node_seconds'):
            times = [r[metric] for r in chosen]
            require(all(type(t) in (int, float) and math.isfinite(t) and t > 0 for t in times), 'Invalid timing')
            original = (times[0] + times[2]) / 2 if order == 'OCO' else times[1]
            cached = times[1] if order == 'OCO' else (times[0] + times[2]) / 2
            metrics[metric] = {'seconds': times, 'original_mean': original,
                               'cache_mean': cached, 'cache_minus_original': cached - original}
        triples.append({'fixture': fixture, 'order': order, 'runs': [r['run'] for r in chosen], 'metrics': metrics})
    fixture_means = {}
    for fixture in ('boat', 'marble', 'bird'):
        selected = [t for t in triples if t['fixture'] == fixture]
        if len(selected) == 2:
            fixture_means[fixture] = {metric: statistics.mean(t['metrics'][metric]['cache_minus_original'] for t in selected)
                for metric in ('preview_ready_seconds', 'decoder_node_seconds')}
    return {'triples': triples, 'paired_samples': len(triples), 'fixture_mean_cache_minus_original': fixture_means,
        'median_triplet_preview_delta': statistics.median(t['metrics']['preview_ready_seconds']['cache_minus_original'] for t in triples) if triples else None,
        'scope': 'Balanced repeated same-fixture event timings; no kernel timing, automatic promotion, or streaming qualification'}


def run_campaign(args, common):
    base, manifest, contract, sources = prepared_sources(args, common)
    identity, _ = v3.identity_binding(common, args.packet, args.manifest_sha256, args.server_run)
    node_info = validate_node_info(screen.get_json('/object_info/LTXNAAxisDecode'))
    identity_sha = sha(args.server_run / 'server-identity.json')
    admission = admission_helpers.admit(ROOT, args.server_run, identity, base, contract, sources, prior)
    rows = schedule(args.campaign)
    require(len(rows) == 18, 'Unbounded schedule')
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
        require(not retention.safe_path(args.server_run, 'na-axis-' + row['run'], exists=False).exists(), 'Receipt collision')
    output = retention.safe_path(ROOT, args.campaign, exists=False)
    output.mkdir(exist_ok=False)
    write_json(output / 'preregistration.json', {'campaign': args.campaign, 'schedule': rows, 'max_requests': 18,
        'fixtures': fixtures, 'identity': identity, 'packet_manifest_sha256': args.manifest_sha256,
        'client_sha256': sha(Path(__file__)), 'validator_sha256': VALIDATOR_SHA,
        'inherited_v3_sha256': V3_SHA, 'frozen_helpers': screen.FROZEN, 'source_identity': sources,
        'loaded_node_info': node_info,
        'decoder_contract': contract, 'expected_na_sequence': validators.expected_calls(contract, [1, 128, 4, 8, 8]),
        'scope': 'same-process original transformer; balanced OCO/COC decoder triples, no extra warmup',
        'prior_screen_admission': admission, 'admission_helper_sha256': ADMISSION_SHA,
        'prior_client_sha256': PRIOR_CLIENT_SHA,
        'failure_action': 'halt new requests; preserve unexpected original sequence/failure; no retry or automatic widening',
        'timeout_action': 'halt client submissions, preserve running server request; timeout is not cancellation',
        'retention': 'delete only own verified redundant raw archives; retain latest3 passing previews',
        'speed_promotion': False, 'streaming_qualification': False})
    completed, inventory, deleted = [], {}, set()
    discovery, components = admission['discovery'], admission['components']
    runs = {row['run'] for row in rows}
    current, stage = None, 'preflight'
    try:
        for plan in rows:
            current, stage = copy.deepcopy(plan), 'preflight'
            admission_helpers.verify_bindings(ROOT, admission, prior)
            v3.identity_binding(common, args.packet, args.manifest_sha256, args.server_run, identity)
            require(validate_node_info(screen.get_json('/object_info/LTXNAAxisDecode')) == node_info,
                    'Private decoder registration changed')
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
            if mode != 'bare':
                graph['374']['inputs']['run_name'] = run
            graph_path = output / (run + '-graph.json')
            write_json(graph_path, graph)
            stage = 'request'
            command = [sys.executable, str(LANE / 'scripts/profile-clip.py'), run, '--graph', str(graph_path),
                       '--server-run', str(args.server_run), '--timeout', '1200']
            current['command'] = command
            try:
                screen.run_subprocess(command, output / (run + '-client.log'), 1260)
            finally:
                current['after'] = retention.snapshot(identity['pid'])
            v3.identity_binding(common, args.packet, args.manifest_sha256, args.server_run, identity)
            stage = 'graph-placement-decoder-gates'
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
            placement = json.loads(retention.safe_path(args.server_run, 'encoder-placement-' + run + '.json').read_text())
            screen.validate_placement(placement, run, 'control', identity_sha, identity['model_verification_sha256'])
            write_json(output / (run + '-placement.json'), placement)
            observed = screen.latest_components(args.server_run, 'control')
            require(components is None or components == observed, 'Resident components changed')
            components = observed
            current['components'] = observed
            directory = retention.safe_path(args.server_run, 'na-axis-' + run, exists=mode != 'bare')
            if mode == 'bare':
                require(not directory.exists(), 'Bare control unexpectedly entered scoped decoder')
            else:
                require(submitted['374']['inputs']['run_name'] == run, 'Decoder request name differs')
                started = json.loads(retention.safe_path(directory, 'started.json').read_text())
                result = json.loads(retention.safe_path(directory, 'result.json').read_text())
                write_json(output / (run + '-decoder-started.json'), started)
                write_json(output / (run + '-decoder-result.json'), result)
                validators.validate_started(started, result)
                current['decoder_validation'] = validators.validate_receipt(result, run_name=run, mode=mode,
                    identity_sha=identity_sha, sources=sources, contract=contract, previous=discovery)
            stage = 'four-output-oracle'
            parity_path = output / (run + '-parity.json')
            screen.run_subprocess([sys.executable, str(LANE / 'scripts/compare-clip.py'), fixture['reference'], run,
                '--output', str(parity_path)], output / (run + '-compare.log'), 120)
            parity = json.loads(parity_path.read_text())
            require(parity['status'] == 'passed' and set(parity['comparisons']) ==
                    {'images', 'video_latent', 'audio_latent', 'waveform'} and
                    all(x['bitwise_equal'] is True for x in parity['comparisons'].values()), 'Original raw parity failed')
            current['capture'] = retention.validate_capture(ROOT, run)
            if mode != 'bare' and discovery is None:
                discovery = result
                write_json(output / 'original-native-sequence.json', discovery)
            profile = json.loads((request / 'profile.json').read_text())
            decoder_rows = [row for row in profile['nodes'] if row['node'] == '374']
            require(len(decoder_rows) == 1, 'Missing/unexpected decoder profile intervals')
            current.update(reference=fixture['reference'], parity_path=str(parity_path), profile=profile,
                preview_ready_seconds=profile['preview_ready_seconds'], decoder_node_seconds=decoder_rows[0]['seconds'])
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
        base, _, contract, sources = prepared_sources(args, common)
        identity = json.loads((args.server_run / 'server-identity.json').read_text())
        admission = admission_helpers.admit(ROOT, args.server_run, identity, base, contract, sources, prior)
        print(json.dumps({'status': 'source-and-prior-evidence-check-passed', 'native_requests': 0,
            'client_sha256': sha(Path(__file__)), 'admission_helper_sha256': ADMISSION_SHA,
            'schedule': schedule(args.campaign), 'prior_progress_sha256': admission['progress_sha256'],
            'prior_evidence_files': len(admission['evidence_sha256s']),
            'prior_scoped_decodes': admission['prior_scoped_decodes'],
            'expected_na_calls': len(validators.expected_calls(contract, [1, 128, 4, 8, 8]))}, indent=2))
        return
    with (args.server_run / 'encoder-screen-client.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run_campaign(args, common)


if __name__ == '__main__':
    main()

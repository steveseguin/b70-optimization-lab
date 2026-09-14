"""Stdlib admission of the completed same-process decoder screen, never replay."""
import copy
import hashlib
import json
from pathlib import Path

CAMPAIGN = 'na-axis-screen-01'
PROGRESS_SHA = 'a0da72e9a1a85086b41bb02c66e9eda63401a649b5795e0a63e46deceb244568'
CLIENT_SHA = '28fd569ab0acecb10a9b59821a707eb917d80bb013bdb973d046a8e6ad074988'
PID = 84255


def require(value, message):
    if not value:
        raise RuntimeError(message)


def validate_progress(progress, prereg, identity, prior):
    plan = prior.schedule(CAMPAIGN)
    require(progress['status'] == 'passed' and progress['completed_requests'] == 11 and len(progress['rows']) == 11,
            'Prior11-request screen is incomplete')
    require(prereg['campaign'] == CAMPAIGN and prereg['max_requests'] == 11 and prereg['schedule'] == plan and
            prereg['client_sha256'] == CLIENT_SHA and prereg['validator_sha256'] == prior.VALIDATOR_SHA and
            prereg['packet_manifest_sha256'] == prior.PACKET_SHA, 'Prior preregistration/source identity differs')
    require(identity == prereg['identity'] and type(identity['pid']) is int and identity['pid'] == PID,
            'Confirmation requires the same packet10 process')
    components = progress['rows'][0]['components']
    for row, expected in zip(progress['rows'], plan):
        require(row['status'] == 'passed' and all(row[key] == value for key, value in expected.items()),
                'Prior row differs from completed schedule')
        require(row['components'] == components, 'Prior resident component generation changed')
    require(components['generation'] == 1 and components['encoder_variant'] == 'control' and
            components['prompt_encoding_cache'] is False and components['generated_output_cache'] is False,
            'Prior resident ownership/configuration differs')
    return plan, components


def validate_parity(parity, row, *, identity, prompt_id, prompt_sha, reference):
    require(parity['status'] == 'passed' and set(parity['comparisons']) ==
            {'images', 'video_latent', 'audio_latent', 'waveform'}, 'Missing prior four-output oracle')
    for comparison in parity['comparisons'].values():
        require(comparison['bitwise_equal'] is True and comparison['same_layout'] is True and
                comparison['unequal_values'] == 0 and comparison['max_abs_diff'] == 0,
                'Prior raw oracle did not pass exactly')
    executions = parity['executions']
    require(len(executions) == 2 and executions[0]['name'] == reference and executions[1]['name'] == row['run'] and
            executions[1]['prompt_id'] == prompt_id and executions[1]['prompt_sha256'] == prompt_sha and
            executions[1]['server_identity'] == identity and executions[1]['sample_rate'] == 48000 and
            executions[0]['server_identity']['model_verification_sha256'] == identity['model_verification_sha256'] and
            executions[0]['sample_rate'] == 48000 and executions[0]['prompt_id'] != prompt_id,
            'Prior oracle is bound to another run/fixture/process')


def admit(root, server_run, identity, base, contract, sources, prior):
    """Validate durable raw-comparison evidence; deleted raw archives stay deleted."""
    root, server_run = Path(root), Path(server_run)
    safe, sha = prior.retention.safe_path, prior.sha
    require(not (root / 'FAULT.json').exists() and not (server_run / 'FAULT.json').exists(), 'Fault recorded')
    bindings = {}
    def read(path):
        path = safe(root, Path(path).relative_to(root))
        bindings[str(path.relative_to(root))] = sha(path)
        return json.loads(path.read_text())
    folder = root / CAMPAIGN
    progress_path = safe(root, Path(CAMPAIGN) / 'progress.json')
    require(sha(progress_path) == PROGRESS_SHA, 'Prior completed progress hash changed')
    progress, prereg = read(progress_path), read(folder / 'preregistration.json')
    plan, components = validate_progress(progress, prereg, identity, prior)
    require(prereg['source_identity'] == sources and prereg['decoder_contract'] == contract,
            'Prior decoder source/config contract changed')
    discovery = read(folder / 'original-native-sequence.json')
    identity_sha = sha(safe(root, server_run.relative_to(root) / 'server-identity.json'))
    require(discovery['run_name'] == plan[2]['run'], 'Wrong original sequence discovery')
    prior.validators.validate_receipt(discovery, run_name=plan[2]['run'], mode='original',
        identity_sha=identity_sha, sources=sources, contract=contract)
    expected_receipts = {'na-axis-' + row['run'] for row in plan if row['mode'] != 'bare'}
    require({p.name for p in server_run.glob('na-axis-*')} == expected_receipts,
            'Unregistered prior decoder attempts; do not retry')
    require(not list(server_run.glob('native-multiblock-*')), 'Compiler attempts are outside confirmation scope')
    require(prior.screen.latest_components(server_run, 'control') == components, 'Current resident components changed')
    for row in progress['rows']:
        run, mode = row['run'], row['mode']
        reference, seed = prior.screen.REFERENCES[row['fixture']]
        require(row['reference'] == reference, 'Prior reference fixture changed')
        request = root / 'requests' / run
        prompt = read(request / 'prompt.json')
        original_prompt = read(root / 'requests' / reference / 'prompt.json')
        require(prior.normalized(prompt) == prior.normalized(prior.expected_graph(base, mode)) and
                prompt['364']['inputs']['text'] == original_prompt['364']['inputs']['text'] and
                all(prompt[n]['inputs']['noise_seed'] == original_prompt[n]['inputs']['noise_seed'] == seed
                    for n in ('338', '339')) and prompt['421']['inputs']['run_name'] == run and
                prompt['414']['inputs']['run_name'] == run and
                prompt['75']['inputs']['filename_prefix'] == run + '/preview', 'Prior submitted graph/fixture differs')
        require(read(request / 'identity.json') == identity, 'Prior request process changed')
        submission, result, history = [read(request / name) for name in ('submission.json', 'result.json', 'history.json')]
        prompt_id = submission['prompt_id']
        require(result['prompt_id'] == history['prompt'][1] == prompt_id and history['prompt'][2] == prompt and
                history['status']['status_str'] == 'success' and history['status']['completed'] is True and
                not any(message[1].get('nodes') for message in history['status']['messages'] if message[0] == 'execution_cached'),
                'Prior request incomplete or reused graph outputs')
        parity = read(folder / (run + '-parity.json'))
        validate_parity(parity, row, identity=identity, prompt_id=prompt_id,
                        prompt_sha=bindings[str((request / 'prompt.json').relative_to(root))], reference=reference)
        reference_request = root / 'requests' / reference
        require(parity['executions'][0]['prompt_sha256'] == bindings[str((reference_request / 'prompt.json').relative_to(root))] and
                parity['executions'][0]['prompt_id'] == read(reference_request / 'submission.json')['prompt_id'] and
                parity['executions'][0]['server_identity'] == read(reference_request / 'identity.json'),
                'Prior oracle reference provenance changed')
        capture = read(root / 'output/validation' / run / 'summary.json')
        original_capture = read(root / 'output/validation' / reference / 'summary.json')
        require(capture == row['capture'] and capture['run_name'] == run and capture['sample_rate'] == 48000 and
                capture['deterministic_enabled'] is True and capture['deterministic_warn_only'] is False,
                'Prior verified capture/strictness receipt changed')
        require(set(capture['tensors']) == set(parity['comparisons']), 'Prior capture tensor set changed')
        for key, value in capture['tensors'].items():
            expected = original_capture['tensors'][key]
            require(value['finite'] is True and all(value[field] == expected[field] for field in ('shape', 'dtype', 'sha256')),
                    'Prior output hashes/layout differ from original oracle')
        require(read(request / 'profile.json') == row['profile'], 'Prior timing receipt changed')
        placement = read(server_run / ('encoder-placement-' + run + '.json'))
        require(read(folder / (run + '-placement.json')) == placement, 'Prior placement copies differ')
        prior.screen.validate_placement(placement, run, 'control', identity_sha, identity['model_verification_sha256'])
        if mode != 'bare':
            require(prompt['374']['inputs']['run_name'] == run, 'Prior scoped decoder name changed')
            directory = server_run / ('na-axis-' + run)
            started, decoder_result = read(directory / 'started.json'), read(directory / 'result.json')
            require(read(folder / (run + '-decoder-started.json')) == started and
                    read(folder / (run + '-decoder-result.json')) == decoder_result, 'Prior decoder receipt copies differ')
            prior.validators.validate_started(started, decoder_result)
            validated = prior.validators.validate_receipt(decoder_result, run_name=run, mode=mode,
                identity_sha=identity_sha, sources=sources, contract=contract, previous=discovery)
            require(validated == row['decoder_validation'], 'Prior decoder validation receipt changed')
    return {'status': 'completed-screen-admitted', 'prior_campaign': CAMPAIGN, 'progress_sha256': PROGRESS_SHA,
        'identity': copy.deepcopy(identity), 'components': components, 'discovery': discovery,
        'evidence_sha256s': bindings, 'prior_requests': 11, 'prior_scoped_decodes': 9,
        'raw_evidence_scope': 'Revalidated durable original raw-comparison receipts and hashes; deleted archives not reread'}


def verify_bindings(root, admission, prior):
    for relative, digest in admission['evidence_sha256s'].items():
        require(prior.sha(prior.retention.safe_path(root, relative)) == digest, 'Prior admitted evidence changed: ' + relative)

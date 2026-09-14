"""Stdlib-only gates for the bounded, exact-output host-table screen."""
import math

TABLE_NAME = 'gemma3_12b.transformer.model.embed_tokens.weight'
TABLE_BYTES = 2013265920
MODES = ('control', 'host-table')


def require(value, message):
    if not value:
        raise RuntimeError(message)


def positive_id(value):
    require(type(value) is int and value > 0, 'Invalid owner identity')


def identity(report, server_sha, model_sha):
    require(report['server_identity_sha256'] == server_sha and report['model_verification_sha256'] == model_sha,
            'Receipt identity differs')


def record_key(row, owners=False):
    keys = ['name', 'kind', 'dtype', 'shape', 'bytes']
    if row['kind'] == 'buffer':
        keys.append('persistent')
    if owners:
        keys.append('owner_id')
    return tuple(tuple(row[k]) if k == 'shape' else row[k] for k in keys)


def inventory(report, expected, device=None):
    for group in ('parameters', 'buffers'):
        summary = report[group]
        rows = summary['records']
        require(type(summary['count']) is int and summary['count'] == len(rows), 'Incorrect tensor count')
        require(summary['bytes'] == sum(row['bytes'] for row in rows), 'Incorrect registered bytes')
        require(len({r['name'] for r in rows}) == len(rows), 'Duplicate registered name')
        require(sorted(record_key(r) for r in rows) == sorted(record_key(r) for r in expected[group]),
                'Registered geometry/dtype/bytes differs from original: ' + group)
        by_device = {}
        for row in rows:
            positive_id(row['owner_id'])
            require(row['device'] in ('cpu', 'xpu:2'), 'Unexpected registered device')
            require(type(row['bytes']) is int and row['bytes'] >= 0, 'Invalid tensor bytes')
            if device:
                require(row['device'] == device, 'Registered state is not fully on ' + device)
            key = row['device'] + '/' + row['dtype']
            entry = by_device.setdefault(key, {'tensors': 0, 'bytes': 0})
            entry['tensors'] += 1
            entry['bytes'] += row['bytes']
        require(summary['by_device_dtype'] == by_device, 'Device summary differs from actual records')
    account = report['accounting']
    require(account['offload_device'] == 'cpu' and account['load_device'] in ('cpu', 'xpu:2'), 'Wrong loader devices')
    for key in ('crop_option', 'patcher_small_state_option', 'model_small_state_policy', 'is_dynamic'):
        require(account[key] is False, 'Unsupported model policy: ' + key)
    for key in ('reported_loaded_weight_bytes', 'reported_offload_buffer_bytes', 'reported_model_size_bytes'):
        require(type(account[key]) is int and account[key] >= 0, 'Invalid accounting bytes')
    actual = sum(r['bytes'] for r in report['parameters']['records'] if r['device'] == account['load_device'])
    persistent = sum(r['bytes'] for r in report['buffers']['records'] if r['persistent'] and r['device'] == account['load_device'])
    require(account['registered_parameter_bytes_on_load_device'] == actual and
            account['registered_persistent_buffer_bytes_on_load_device'] == persistent, 'Residency summary differs')
    size = sum(r['bytes'] for r in expected['parameters']) + sum(r['bytes'] for r in expected['buffers'] if r['persistent'])
    require(account['reported_model_size_bytes'] == size, 'Eligible model accounting differs')
    return actual + persistent


def expected_inventory(contract, mode):
    require(mode in MODES, 'Unknown encoder mode')
    return {'parameters': [r for r in contract['parameters'] if mode == 'control' or r['name'] != TABLE_NAME],
            'buffers': contract['buffers']}


def same_owners(a, b):
    for group in ('parameters', 'buffers'):
        require(sorted(record_key(r, True) for r in a[group]['records']) ==
                sorted(record_key(r, True) for r in b[group]['records']), 'Registered owner changed')


def ownership(report, contract, mode, *, initial=False, previous=None):
    require(report['schema'] == 'ltx.host-embedding-placement.v1' and report['mode'] == mode,
            'Unexpected ownership schema/mode')
    require(report['original_combined_bytes'] == contract['original_combined_bytes'], 'Combined accounting changed')
    require(report['quality_qualified'] is False and report['speed_qualified'] is False, 'Metadata cannot qualify quality/speed')
    encoder = report['encoder']
    expected = expected_inventory(contract, mode)
    actual = inventory(encoder, expected, 'cpu' if initial else ('xpu:2' if mode == 'host-table' else None))
    require(encoder['accounting']['load_device'] == 'xpu:2', 'Wrong encoder load device')
    require(report['embedding_observation_limit'] == 4, 'Observation bound changed')
    if initial:
        require(report['encodes_completed'] == 0 and report['last_load'] is None and report['embedding_observations'] == [],
                'Initial CPU construction already encoded/loaded')
        require(encoder['accounting']['reported_loaded_weight_bytes'] == 0 and
                encoder['accounting']['reported_offload_buffer_bytes'] == 0, 'Encoder preloaded before ownership')
    if mode == 'host-table':
        table = next(r for r in contract['parameters'] if r['name'] == TABLE_NAME)
        table = {**table, 'name': 'embedding.weight'}
        require(table['shape'] == [262144, 3840] and table['dtype'] == 'torch.bfloat16' and table['bytes'] == TABLE_BYTES,
                'Original table contract differs')
        host = report['host']
        inventory(host, {'parameters': [table], 'buffers': []}, 'cpu')
        require(host['accounting']['load_device'] == 'cpu' and
                host['accounting']['reported_loaded_weight_bytes'] == (0 if initial else TABLE_BYTES),
                'Host owner is not correctly accounted by loader')
        owner = report['owner']
        require(owner['schema'] == 'ltx.host-embedding-ownership.v1', 'Wrong host-owner schema')
        for key in ('host_owner_id', 'host_weight_id'):
            positive_id(owner[key])
        require(owner['host_device'] == 'cpu' and owner['host_dtype'] == 'torch.bfloat16' and
                owner['host_registered_bytes'] == TABLE_BYTES and owner['execution_device'] == 'xpu:2' and
                owner['original_combined_bytes'] == contract['original_combined_bytes'] and
                owner['encoder_eligible_bytes'] == contract['original_combined_bytes'] - TABLE_BYTES and
                owner['encoder_reported_loaded_bytes'] == encoder['accounting']['reported_loaded_weight_bytes'] and
                owner['native_qualified'] is False, 'Host ownership/accounting differs')
        require(type(owner['inference_tensor']) is bool and type(owner['weight_version_tracked']) is bool and
                owner['weight_version_tracked'] is (not owner['inference_tensor']), 'Mutation-check scope differs')
        if not initial:
            require(actual == encoder['accounting']['reported_loaded_weight_bytes'] == owner['encoder_eligible_bytes'],
                    'Remaining encoder is not fully resident/accounted')
    else:
        require(report['host'] is None and report['owner'] is None, 'Control unexpectedly extracted table')
    if previous:
        same_owners(previous['encoder'], encoder)
        if mode == 'host-table':
            same_owners(previous['host'], report['host'])
            for key in ('host_owner_id', 'host_weight_id'):
                require(previous['owner'][key] == report['owner'][key], 'Host owner changed')


def placement(report, *, contract, run, mode, ordinal, server_sha, model_sha, initial, previous=None):
    identity(report, server_sha, model_sha)
    ownership(report, contract, mode, previous=previous or initial)
    require(report['stage'] == 'post_encode' and report['run_name'] == run and report['passed'] is True,
            'Placement result is not this completed request')
    require(report['generated_output_cache'] is False and report['prompt_encoding_cache'] is False,
            'Output/encoding reuse forbidden')
    require(type(report['encodes_completed']) is int and report['encodes_completed'] == ordinal,
            'Each request requires one newly completed encode')
    observations = report['embedding_observations']
    # The pinned text-only process_tokens path performs exactly one embedding call.
    require(len(observations) == 1 and observations[0]['ordinal'] == 1, 'Unexpected embedding call sequence')
    row = observations[0]
    require(row['input_ids'] == {'shape': [1, 1024], 'dtype': 'torch.int64', 'device': 'xpu:2'} and
            row['scaled_embedding'] == {'shape': [1, 1024, 3840], 'dtype': 'torch.float32', 'device': 'xpu:2'},
            'Actual token/embedding metadata differs from fixed original text path')
    load = report['last_load']
    require(type(load['memory_required']) in (int, float) and math.isfinite(load['memory_required']) and load['memory_required'] >= 0,
            'Invalid original memory estimate')
    require(load['force_full_load'] is False and load['reserve_override'] is False, 'Loader budget override forbidden')
    ids = load['patcher_ids']
    require(len(ids) == (2 if mode == 'host-table' else 1) and len(set(ids)) == len(ids), 'Missing/duplicate loaded owner')
    for value in ids:
        positive_id(value)
    if previous:
        require(ids == previous['last_load']['patcher_ids'] and load['memory_required'] == previous['last_load']['memory_required'],
                'Loaded patcher identity or fixed-token estimator changed')
    return {'status': 'passed-host-placement', 'new_encode_ordinal': ordinal,
            'table_bytes': TABLE_BYTES if mode == 'host-table' else 0,
            'encoder_loaded_bytes': report['encoder']['accounting']['reported_loaded_weight_bytes']}


def component(started, result, *, contract, mode, generation, server_sha, model_sha):
    for report in (started, result):
        identity(report, server_sha, model_sha)
        require(report['schema'] == 'ltx.host-embedding-components.v1' and report['encoder_mode'] == mode and
                type(report['generation']) is int and report['generation'] == generation and
                report['previous_generation'] == generation - 1 and report['placement'] == 'split' and
                report['previous_mode'] == (None if generation == 1 else ('control' if mode == 'host-table' else 'host-table')),
                'Component generation/transition differs')
        require(report['generated_output_cache'] is False and report['prompt_encoding_cache'] is False,
                'Component output cache forbidden')
    require(started['status'] == 'started' and result['status'] == 'completed', 'Incomplete component construction')
    require(all(result[k] == v for k, v in started.items() if k != 'status'), 'Component started/result changed')
    require(result['text_encoder_load_device'] == 'xpu:2' and result['vae_devices'] == ['xpu:3', 'xpu:3'] and
            result['model_load_device'] == 'xpu:0', 'Component device map changed')
    ownership(result['encoder_initial_ownership'], contract, mode, initial=True)


def unload(report, *, contract, previous, old_generation, new_generation, mode, server_sha, model_sha):
    identity(report, server_sha, model_sha)
    require(report['schema'] == 'ltx.host-embedding-unload.v1' and report['old_generation'] == old_generation and
            report['new_generation'] == new_generation == old_generation + 1 and
            report['old_mode'] == previous['mode'] and report['new_mode'] == mode and
            report['original_ownership_restored'] is True and report['all_shared_clones_retired'] is True and
            report['after_host_registered_bytes'] == 0, 'Incomplete owner retirement')
    before, after = report['before'], report['after_encoder']
    ownership(before, contract, previous['mode'], previous=previous)
    require(before['encodes_completed'] == previous['encodes_completed'] and before['embedding_observations'] == [],
            'Retirement did not consume exactly previous encode')
    inventory(after, expected_inventory(contract, 'control'), 'cpu')
    # Restoring the table changes its registration path only, not the table owner.
    expected = {g: {'records': list(before['encoder'][g]['records'])} for g in ('parameters', 'buffers')}
    if previous['mode'] == 'host-table':
        table = dict(before['host']['parameters']['records'][0], name=TABLE_NAME)
        expected['parameters']['records'].append(table)
    same_owners(expected, after)
    account = after['accounting']
    require(account['reported_loaded_weight_bytes'] == 0 and account['reported_offload_buffer_bytes'] == 0 and
            account['marked_modules'] == [] and account['small_buffers_loaded'] is False,
            'Retired encoder accounting not cleared')
    return {'status': 'passed-complete-owner-retirement', 'old_generation': old_generation, 'new_generation': new_generation}

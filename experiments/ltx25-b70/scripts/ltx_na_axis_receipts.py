"""Stdlib-only decoder-axis receipt validation; no tensor imports or device work."""
import ast
import copy
import hashlib
import json
import math
from pathlib import Path
import struct

ORIGINAL_SHA = '4f1d82fe02af995d395969667f6cfd8d10635c3144eec8ca78fe37c103803995'
CANDIDATE_SHA = '40e360bc1f791f0373997f907ca67e804087541498c86ffa5731c8a9eae40cc2'
MODEL_SHA = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
HEADER_SHA = 'bc4f0a9f8d1f436c6317e92ab057feeb746cdad6ab3d0e9c76df6b57b290602a'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def checkpoint_config(path):
    with Path(path).open('rb') as stream:
        prefix = stream.read(8)
        size = struct.unpack('<Q', prefix)[0]
        require(0 < size <= 4 * 1024**2, 'Unexpected VAE header length')
        header = stream.read(size)
    require(hashlib.sha256(prefix + header).hexdigest() == HEADER_SHA, 'Pinned VAE header changed')
    return json.loads(json.loads(header)['__metadata__']['config'])['vae']


def source_contract(decoder_source, sd_source, checkpoint_vae_config):
    """Read literal defaults; shape arithmetic follows the pinned forward methods.

    sd.py may supply checkpoint config, so actual decoder config is checked too.
    Caller binds both source hashes to its sealed packet before calling this.
    """
    tree = ast.parse(decoder_source)
    nodes = [n for n in tree.body if isinstance(n, ast.Assign) and
             any(isinstance(t, ast.Name) and t.id == 'LTX_24_VAE_CONFIG' for t in n.targets)]
    require(len(nodes) == 1, 'Missing unambiguous decoder defaults')
    config = ast.literal_eval(nodes[0].value)
    require('CausalDiffusionVAE(config=vae_config)' in sd_source,
            'VAE config loading path changed')
    actual = checkpoint_vae_config['decoder']
    require(all(actual.get(key, value) == value for key, value in config['decoder'].items()) and
            actual.get('t_emb_dim', 384) == 384 and checkpoint_vae_config.get('model_output_type', 'x0') ==
            config.get('model_output_type', 'x0'), 'Checkpoint overrides numerical decoder defaults')
    return {'config': config, 'checkpoint_vae_config': copy.deepcopy(checkpoint_vae_config),
            'checkpoint_header_sha256': HEADER_SHA,
            'decoder_source_sha256': hashlib.sha256(decoder_source.encode()).hexdigest(),
            'sd_source_sha256': hashlib.sha256(sd_source.encode()).hexdigest(),
            'path': 'default untiled decode; unexpected sequence stops before candidate'}


def expected_calls(contract, input_shape, actual_config=None):
    require(input_shape == [1, 128, 4, 8, 8], 'Unregistered latent geometry')
    defaults = contract['config']
    cfg = defaults['decoder']
    if actual_config is not None:
        require(isinstance(actual_config, dict), 'Actual decoder config missing')
        require(actual_config == contract['checkpoint_vae_config'], 'Actual checkpoint config differs from pinned header')
    depths, channels, kernels = cfg['stage_depths'], cfg['stage_channels'], cfg['stage_kernels']
    require(len(depths) == len(channels) == len(kernels) == len(cfg['upsamples']) + 1,
            'Malformed decoder architecture')
    require(all(type(n) is int and n > 0 for n in depths + channels), 'Invalid stage sizes')
    b, _, t, h, w = input_shape
    padding = (kernels[0][0] // 2) * 2
    t += padding
    calls = []
    def stage(index, kernel, repeats):
        require(channels[index] % cfg['head_dim'] == 0, 'Invalid attention heads')
        metadata = {'shape': [b, t, h, w, channels[index] // cfg['head_dim'], cfg['head_dim']],
                    'dtype': 'torch.bfloat16', 'device': 'xpu:3'}
        for _ in range(repeats):
            calls.append({'index': len(calls), 'status': 'completed',
                'inputs': [copy.deepcopy(metadata) for _ in range(3)],
                # Public Kitchen na3d normalizes caller None before the custom
                # op reaches the eager router; saved actual CPU receipts prove it.
                'kernel_size': list(kernel), 'is_causal': [False, False, False], 'scale': 1.0,
                'output': copy.deepcopy(metadata)})
    for index, (stride, reduction) in enumerate(cfg['upsamples']):
        stage(index, kernels[index], depths[index])
        t = t * stride[0] - (1 if stride[0] == 2 else 0)
        h, w = h * stride[1], w * stride[2]
    t -= padding * math.prod(stride[0] for stride, _ in cfg['upsamples'])
    stage(len(depths) - 1, cfg['stage5_kernel'], depths[-1] * cfg['default_num_inference_steps'])
    require(1 <= len(calls) <= 256, 'Unbounded decoder call contract')
    require([b * t, h * cfg['patch_size'], w * cfg['patch_size'], cfg['out_channels']] == [25, 256, 256, 3],
            'Decoder output geometry changed')
    return calls


def normalized_calls(calls):
    return [{key: copy.deepcopy(value) for key, value in row.items() if key != 'mode'} for row in calls]


def validate_receipt(receipt, *, run_name, mode, identity_sha, sources, contract, previous=None):
    require(mode in ('original', 'axis-cache'), 'Unregistered decoder mode')
    require(receipt['schema'] == 'ltx.na-axis-decode.v1' and receipt['status'] == 'passed-decode-route' and
            receipt['run_name'] == run_name and receipt['mode'] == mode, 'Decoder receipt status/identity differs')
    require(receipt['identity'] == {'server_identity_sha256': identity_sha,
                                   'model_verification_sha256': MODEL_SHA}, 'Decoder server/model identity differs')
    require(receipt['source_identity'] == sources, 'Decoder source identity differs')
    require(receipt['context_clear_after'] is True and receipt['quality_qualified'] is False and
            receipt['native_sequence_qualified'] is False, 'Decode scope/qualification fields differ')
    require(type(receipt['started_monotonic_ns']) is int and type(receipt['finished_monotonic_ns']) is int and
            0 < receipt['started_monotonic_ns'] <= receipt['finished_monotonic_ns'], 'Invalid decoder receipt timestamps')
    owners = receipt['owners']
    require(set(owners) == {'vae', 'patcher', 'first_stage_model', 'decoder'} and
            all(type(value) is int and value > 0 for value in owners.values()) and
            len(set(owners.values())) == 4, 'Invalid decoder ownership metadata')
    route = receipt['route']
    require(route['schema'] == 'ltx.na-axis-route.v1' and route['status'] == 'passed-route-coverage' and
            route['run_name'] == run_name and route['mode'] == mode and route['scope_reset'] is True,
            'Incomplete or mismatched NA route')
    require(route['original_sha256'] == ORIGINAL_SHA and route['candidate_sha256'] == CANDIDATE_SHA and
            type(route['thread_id']) is int and route['thread_id'] > 0, 'NA source/thread differs')
    require(receipt['input']['nested'] is False and receipt['input']['shape'] == [1, 128, 4, 8, 8] and receipt['input']['dtype'] == 'torch.float32',
            'Input latent shape/dtype differs')
    require(receipt['input']['device'] in ('cpu', 'xpu:0', 'xpu:1', 'xpu:2', 'xpu:3'),
            'Unexpected latent device metadata')
    require(receipt['output']['nested'] is False and receipt['output']['shape'] == [25, 256, 256, 3] and receipt['output']['dtype'] == 'torch.float32' and
            receipt['output']['device'] == 'cpu', 'Decoded output metadata differs')
    calls = route['calls']
    require(isinstance(calls, list) and all(row['mode'] == mode for row in calls), 'Wrong per-call NA route')
    for row in calls:
        require(type(row['index']) is int and type(row['scale']) in (int, float) and
                all(type(n) is int and n > 0 for n in row['kernel_size']) and
                type(row['is_causal']) is list and all(type(value) is bool for value in row['is_causal']),
                'Malformed native geometry/scalar metadata')
        require(all(type(n) is int and n > 0 for metadata in [*row['inputs'], row['output']]
                    for n in metadata['shape']), 'Malformed native tensor dimensions')
    normalized = normalized_calls(calls)
    expected = expected_calls(contract, receipt['input']['shape'], receipt['decoder_config'])
    require(normalized == expected, 'Native NA sequence differs from source-derived untiled decoder; preserve and review')
    if previous is not None:
        require(owners == previous['owners'], 'Decoder owner changed')
        require(receipt['input'] == previous['input'] and receipt['output'] == previous['output'] and
                receipt['decoder_config'] == previous['decoder_config'], 'Decoder metadata/config changed')
        require(normalized == normalized_calls(previous['route']['calls']), 'NA sequence changed from original discovery')
        require(route['thread_id'] == previous['route']['thread_id'], 'Decoder worker changed')
    else:
        require(mode == 'original', 'First scoped receipt must discover original sequence')
    return {'status': 'passed', 'call_count': len(calls), 'owners': owners,
            'sequence_sha256': hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()}


def validate_started(started, result):
    require(started['status'] == 'started' and started['route'] is None, 'Invalid pre-decode receipt')
    fields = ('schema', 'mode', 'run_name', 'source_identity', 'identity', 'started_monotonic_ns',
              'quality_qualified', 'native_sequence_qualified', 'owners', 'input', 'decoder_config')
    require(all(started[key] == result[key] for key in fields), 'Started/result evidence differs')

"""Packet123 opt-in auxiliary placement; CPU-only until supplied native owners.

Only loading targets change. No tensor arithmetic, casting, cache eviction,
device probing or global model-manager policy is introduced.
"""
import ast
import hashlib
import os

MODES = ('legacy', 'xpu2')
ENV = 'LTX_AUX_RESIDENCY'
HOST_SHA256 = '4f6119e13473610b0ff4d3ffc6c36096ba2e3f5e8ec3ebbacbcd0495cbf1a065'
SAFETY_SHA256 = '8a98f462417c4e5b630bbeb023666acc3829f8248361fb3b8ce0f73fa998fa0c'
UP_NODE_SHA256 = 'c9f225e4c54f19f31452016fd4e546119d69e9dec37b60a9dc4ddf133848a892'
UPSCALER_BYTES = 995735808
AUDIO_CHECKPOINT_BYTES = 364666868
GIB = 2**30
AUX_WORKSPACE_BYTES = 2*GIB
AUX_FLOOR_BYTES = 2*GIB
SCREENING_MARGIN_BYTES = 3*GIB//4
LEGACY_ROLES = {
    'sampler_primary': 'xpu:0', 'sampler_secondary': 'xpu:1',
    'upsampler': 'xpu:0', 'text_primary': 'xpu:2',
    'text_secondary': 'xpu:3', 'video_vae': 'xpu:3', 'audio_vae': 'xpu:3',
}


def launch(env=None):
    value = (os.environ if env is None else env).get(ENV, 'legacy')
    if type(value) is not str or value not in MODES:
        raise ValueError('LTX_AUX_RESIDENCY must be legacy or xpu2')
    return value


def roles(mode, audio_mode=None):
    launch({ENV: mode})
    result = dict(LEGACY_ROLES)
    if mode == 'xpu2':
        result.update(upsampler='xpu:2', audio_vae='xpu:2')
    import audio_residency132
    audio_mode = audio_residency132.launch() if audio_mode is None else audio_mode
    audio_residency132.launch({audio_residency132.ENV: audio_mode})
    if audio_mode == 'xpu2':
        if mode != 'legacy':
            raise ValueError('Isolated audio residency requires legacy auxiliary placement')
        result['audio_vae'] = 'xpu:2'
    return result


def vae_device(name, mode):
    expected = ('ltx-2.5-video-vae-bf16.safetensors', 'ltx-2.5-audio-vae-bf16.safetensors')
    if name not in expected:
        raise RuntimeError('Auxiliary residency requires the declared VAE checkpoint')
    return roles(mode)['video_vae' if name == expected[0] else 'audio_vae']


def check_aux_free(free_bytes, before):
    if type(free_bytes) is not int or free_bytes < 0 or type(before) is not bool:
        raise RuntimeError('Invalid auxiliary physical free-memory sample')
    required = AUX_FLOOR_BYTES + SCREENING_MARGIN_BYTES + (AUX_WORKSPACE_BYTES if before else 0)
    if free_bytes < required:
        raise RuntimeError('Auxiliary xpu:2 workspace admission failed')
    return {'free_bytes': free_bytes, 'required_bytes': required,
            'workspace_allowance_bytes': AUX_WORKSPACE_BYTES if before else 0,
            'floor_bytes': AUX_FLOOR_BYTES, 'screening_margin_bytes': SCREENING_MARGIN_BYTES,
            'before': before, 'passed': True}


def guard_aux(torch, label, before, mode):
    """Runtime-only injected device sampling; no counter reset or peak claim."""
    launch({ENV: mode})
    if mode == 'legacy':
        return None
    if label not in ('upsampler', 'audio'):
        raise RuntimeError('Unknown auxiliary workspace owner')
    torch.xpu.synchronize('xpu:2')
    record = check_aux_free(torch.xpu.mem_get_info('xpu:2')[0], before)
    return {'owner': label, 'device': 'xpu:2', 'mode': mode, **record}


def validate_aux_evidence(receipt, decode=None):
    """Check saved boundary evidence, never infer an unobserved kernel peak.

    receipt=None validates a standalone decode as it is committed. decode=None
    validates a receipt before its asynchronous decode has completed.
    """
    def need(ok, why):
        if not ok:
            raise ValueError('Auxiliary evidence: ' + why)

    need(receipt is None or type(receipt) is dict, 'receipt must be a dictionary')
    need(decode is None or type(decode) is dict, 'decode must be a dictionary')
    mode = ((receipt.get('server_options') or {}).get('aux_residency', 'legacy')
            if receipt is not None else (decode or {}).get('aux_residency', 'legacy'))
    if mode != 'xpu2':
        return {'enabled': False}

    def workspace(value, owner):
        need(type(value) is dict and set(value) == {'before', 'after'}, owner + ' workspace samples missing')
        for key, before in (('before', True), ('after', False)):
            row = value[key]
            need(type(row) is dict, owner + '/' + key + ' sample missing')
            try:
                expected = check_aux_free(row.get('free_bytes'), before)
            except RuntimeError as error:
                raise ValueError('Auxiliary evidence: ' + owner + '/' + key + ': ' + str(error)) from error
            expected.update(owner=owner, device='xpu:2', mode='xpu2')
            need(row == expected and row.get('before') is before and row.get('passed') is True,
                 owner + '/' + key + ' owner/device/admission fields differ')

    samples = []
    if receipt is not None:
        workspace(receipt.get('aux_upsampler_workspace'), 'upsampler')
        memory = receipt.get('memory')
        need(type(memory) is dict, 'memory census missing')
        for phase in ('before', 'after'):
            row = memory.get(phase)
            need(type(row) is dict, 'request ' + phase + ' memory missing')
            samples.append(('request-' + phase, row.get('free')))
        conditioning = memory.get('conditioning')
        need(type(conditioning) is list, 'conditioning memory missing')
        expected_stages = ['A', 'B'] if receipt.get('anchor_in') is not None else []
        need(all(type(row) is dict for row in conditioning) and
             [row.get('stage') for row in conditioning] == expected_stages,
             'conditioning stage memory census differs')
        for row in conditioning:
            samples.extend((row['stage'] + '-' + phase, row.get('free_' + phase)) for phase in ('before', 'after'))
        floors = dict(zip(('xpu:0', 'xpu:1', 'xpu:2', 'xpu:3'), (8*GIB, 8*GIB, 2*GIB, 9*GIB)))
        for label, free in samples:
            need(type(free) is dict and set(free) == set(floors), label + ' four-card free readings missing')
            for card, floor in floors.items():
                need(type(free[card]) is int and free[card] >= floor + SCREENING_MARGIN_BYTES,
                     label + '/' + card + ' misses floor plus 0.75 GiB')
    if decode is not None:
        need(decode.get('aux_residency') == 'xpu2' and decode.get('audio_device') == 'xpu:2',
             'decode audio placement differs')
        workspace(decode.get('aux_audio_workspace'), 'audio')
        if receipt is not None:
            need(decode.get('run_name') == receipt.get('run_name') and
                 decode.get('prompt_id') == receipt.get('prompt_id'), 'decode belongs to another receipt')
    return {'enabled': True, 'sample_sites': len(samples), 'screening_margin_bytes': SCREENING_MARGIN_BYTES}


def retarget_upsampler(patcher, torch, mode):
    """Select load target while every weight still lives on CPU, before preload.

    The original native model loader constructs and loads BF16 CPU weights. We
    preserve that owner, precision, storage and offload target. Actual residency
    and loaded-size checks remain the native/candidate adapter's responsibility.
    """
    expected = roles(mode)['upsampler']
    if mode == 'legacy':
        return {'mode': mode, 'load_device': 'xpu:0', 'changed': False}
    if str(patcher.load_device) != 'xpu:0' or patcher.loaded_size() != 0 or patcher.is_dynamic():
        raise RuntimeError('Upsampler target can only change before native loading')
    tensors = list(patcher.model.parameters()) + list(patcher.model.buffers())
    if not tensors or any(str(t.device) != 'cpu' or str(t.dtype) != 'torch.bfloat16' for t in tensors):
        raise RuntimeError('Auxiliary upsampler must retain its complete BF16 CPU weights')
    actual_bytes = sum(t.numel() * t.element_size() for t in tensors)
    if actual_bytes != UPSCALER_BYTES:
        raise RuntimeError('Auxiliary upsampler tensor byte census changed')
    patcher.load_device = torch.device(expected)
    return {'mode': mode, 'changed': True, 'load_device': expected,
            'tensor_bytes': actual_bytes, 'tensor_count': len(tensors),
            'weights_unchanged_on_cpu': True}


def _replace(raw, expected_sha256, replacements):
    if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise RuntimeError('Packet123 auxiliary source parent hash differs')
    text = raw.decode('utf-8')
    for old, new in replacements:
        if text.count(old) != 1:
            raise RuntimeError('Packet123 auxiliary source insertion is not unique')
        text = text.replace(old, new, 1)
    ast.parse(text)
    return text.encode('utf-8')


def transform_host(raw):
    return _replace(raw, HOST_SHA256, [
        ('import os as _os\n', 'import os as _os\nimport residency123\nAUX_RESIDENCY = residency123.launch(_os.environ)\n'),
        ("vae = comfy.sd.VAE(sd=weights, metadata=metadata, device=torch.device('xpu:3'))",
         'vae = comfy.sd.VAE(sd=weights, metadata=metadata, device=torch.device(residency123.vae_device(name, AUX_RESIDENCY)))'),
        ("                _pending.append(upscaler)\n", "                record['aux_residency'] = residency123.retarget_upsampler(upscaler, torch, AUX_RESIDENCY)\n                _pending.append(upscaler)\n"),
    ])


def transform_native_safety(raw):
    old = "ROLES = {\n    'sampler_primary': 'xpu:0', 'sampler_secondary': 'xpu:1',\n    'upsampler': 'xpu:0', 'text_primary': 'xpu:2',\n    'text_secondary': 'xpu:3', 'video_vae': 'xpu:3', 'audio_vae': 'xpu:3',\n}"
    return _replace(raw, SAFETY_SHA256, [(old,
        'import residency123\nROLES = residency123.roles(residency123.launch())')])


def transform_upsampler_node(raw):
    return _replace(raw, UP_NODE_SHA256, [
        ('import math\n', 'import math\nimport torch\nimport residency123\n_AUX_RESIDENCY = residency123.launch()\n'),
        ('        device = upscale_model.load_device\n',
         "        aux_before = residency123.guard_aux(torch, 'upsampler', True, _AUX_RESIDENCY)\n        device = upscale_model.load_device\n"),
        ('        return IO.NodeOutput(return_dict)\n',
         "        aux_after = residency123.guard_aux(torch, 'upsampler', False, _AUX_RESIDENCY)\n        if _AUX_RESIDENCY == 'xpu2':\n            upscale_model._ltx123_aux_workspace = {'before': aux_before, 'after': aux_after}\n        return IO.NodeOutput(return_dict)\n"),
    ])

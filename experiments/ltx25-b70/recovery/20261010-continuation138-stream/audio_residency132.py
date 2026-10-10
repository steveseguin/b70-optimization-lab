"""Packet132 isolated audio placement and uncached cross-card qualification.

Inert at import. The trusted host supplies torch and the native VAE. A private
CPU copy exists only for the three eager-control requests. It visits xpu:3 for
one decode at a time and returns to CPU before the next request. It is never a
model-manager owner, never changes the admitted xpu:2 VAE, and cannot survive on
xpu:3 into cone capture. All nine qualification chunks retain the ordinary
whole-chain/frozen reference gates. No alternate arithmetic, precision, output
cache, OOM fallback or retry is allowed.
"""
import ast
import copy
import hashlib
import math
import os
import re
import time

ENV = 'LTX_AUDIO_RESIDENCY'
MODES = ('legacy', 'xpu2')
GIB = 2**30
SCREENING_BYTES = 3*GIB//4
WORKSPACE_BYTES = 2*GIB
HOST_SHA256 = '769c21829a77a2147f1983851505469868e010a4b3218a94c0f904f6e5143f03'
REFERENCE_ATTRIBUTE = '_ltx132_audio_reference'


def require(ok, why):
    if not ok:
        raise RuntimeError('Audio residency132: ' + why)


def launch(env=None):
    value = (os.environ if env is None else env).get(ENV, 'legacy')
    if type(value) is not str or value not in MODES:
        raise ValueError('LTX_AUDIO_RESIDENCY must be legacy or xpu2')
    return value


def vae_device(name, aux_mode, audio_mode):
    import residency123
    launch({ENV: audio_mode})
    expected = ('ltx-2.5-video-vae-bf16.safetensors', 'ltx-2.5-audio-vae-bf16.safetensors')
    require(name in expected, 'undeclared VAE checkpoint')
    return residency123.roles(aux_mode, audio_mode)['video_vae' if name == expected[0] else 'audio_vae']


def tensors(model):
    return list(model.named_parameters()) + list(model.named_buffers())


def model_hash(model):
    h = hashlib.sha256()
    for name, tensor in tensors(model):
        h.update(name.encode())
        h.update(str(tensor.dtype).encode())
        h.update(str(tuple(tensor.shape)).encode())
        h.update(tensor.detach().to('cpu').contiguous().view(-1).view(__import__('torch').uint8).numpy())
    return h.hexdigest()


def prepare_reference(torch, vae, name, mode):
    launch({ENV: mode})
    if mode == 'legacy' or name != 'ltx-2.5-audio-vae-bf16.safetensors':
        return None
    require(not hasattr(vae, REFERENCE_ATTRIBUTE), 'reference already installed')
    require(str(vae.device) == 'xpu:2' and str(vae.output_device) == 'cpu' and
            vae.disable_offload is True, 'native audio placement or offload policy differs')
    require(vae.vae_dtype is torch.bfloat16 and vae.vae_output_dtype() is torch.float32,
            'native --bf16-vae model / float32 output precision differs')
    source = vae.first_stage_model
    require(type(source).__name__ == 'AudioVAE', 'unexpected native audio model')
    rows = tensors(source)
    require(rows and all(str(t.device) == 'cpu' for _, t in rows), 'reference must copy before native loading')
    require(not getattr(source, 'comfy_has_chunked_io', False), 'unsupported native chunked audio output')
    with torch.inference_mode(False), torch.no_grad():
        model = copy.deepcopy(source)
    require(all(a is not b for (_, a), (_, b) in zip(rows, tensors(model))), 'reference weights alias native weights')
    digest = model_hash(source)
    require(model_hash(model) == digest, 'reference weight bytes differ')
    state = {'model': model, 'weight_sha256': digest,
             'resident_bytes': sum(t.numel()*t.element_size() for _, t in rows),
             'calls': [], 'active': False, 'failed': None}
    setattr(vae, REFERENCE_ATTRIBUTE, state)
    return {'resident_bytes': state['resident_bytes'], 'weight_sha256': digest, 'device': 'cpu'}


def check_workspace(free_bytes, device, before, resident_bytes=0):
    require(type(free_bytes) is int and free_bytes >= 0 and type(before) is bool,
            'invalid physical free-memory sample')
    require(device in ('xpu:2', 'xpu:3') and type(resident_bytes) is int and resident_bytes >= 0,
            'invalid workspace owner')
    floor = (2 if device == 'xpu:2' else 9)*GIB
    required = floor + SCREENING_BYTES + (WORKSPACE_BYTES + resident_bytes if before else 0)
    require(free_bytes >= required, '%s workspace admission failed (%d < %d)' % (device, free_bytes, required))
    return {'device': device, 'free_bytes': free_bytes, 'required_bytes': required,
            'floor_bytes': floor, 'screening_margin_bytes': SCREENING_BYTES,
            'workspace_allowance_bytes': WORKSPACE_BYTES if before else 0,
            'new_resident_bytes': resident_bytes if before else 0, 'before': before, 'passed': True}


def workspace(torch, device, before, resident_bytes=0):
    torch.xpu.synchronize(device)
    return check_workspace(torch.xpu.mem_get_info(device)[0], device, before, resident_bytes)


def assert_reference_released(vae):
    state = getattr(vae, REFERENCE_ATTRIBUTE, None)
    require(type(state) is dict and state['failed'] is None and not state['active'], 'reference missing, active or failed')
    require(all(str(t.device) == 'cpu' for _, t in tensors(state['model'])), 'reference still resides on a card')
    return {'device': 'cpu', 'active': False, 'calls': len(state['calls']),
            'resident_bytes_on_xpu3': 0, 'weight_sha256': state['weight_sha256']}


def _digest(torch, waveform):
    return hashlib.sha256(waveform.detach().to('cpu').contiguous().view(torch.uint8).numpy()).hexdigest()


def compare(torch, candidate, reference):
    a, b = candidate['waveform'], reference['waveform']
    ah, bh = _digest(torch, a), _digest(torch, b)
    equal = (candidate['sample_rate'] == reference['sample_rate'] and a.dtype == b.dtype and
             tuple(a.shape) == tuple(b.shape) and ah == bh)
    require(equal, 'cross-card waveform byte gate failed')
    return {'equal': True, 'device': 'xpu:2', 'reference_device': 'xpu:3',
            'sample_rate': candidate['sample_rate'], 'shape': list(a.shape), 'dtype': str(a.dtype),
            'waveform_sha256': ah, 'reference_waveform_sha256': bh, 'mode': 'native-eager-uncached'}


def reference_decode(torch, vae, latent, run_name):
    state = getattr(vae, REFERENCE_ATTRIBUTE, None)
    assert_reference_released(vae)
    require(type(run_name) is str and run_name not in state['calls'] and len(state['calls']) < 3,
            'reference request duplicated or beyond the three eager controls')
    require(latent.shape[0] == 1 and str(latent.device) == 'cpu', 'reference requires private batch-one CPU latent')
    model = state['model']
    before = workspace(torch, 'xpu:3', True, state['resident_bytes'])
    require(model_hash(model) == state['weight_sha256'], 'CPU reference weights changed')
    state['active'] = True
    started = time.perf_counter()
    try:
        with torch.inference_mode(), torch.xpu.device('xpu:3'):
            model.to(device='xpu:3')
            samples = latent.to(device='xpu:3', dtype=vae.vae_dtype)
            torch.xpu.synchronize('xpu:3')
            copied = time.perf_counter()
            out = model.decode(samples)
            torch.xpu.synchronize('xpu:3')
            decoded = time.perf_counter()
            out = out.to(device=vae.output_device, dtype=vae.vae_output_dtype(), copy=True)
            pixels = torch.empty((latent.shape[0],) + tuple(out.shape[1:]),
                                 device=vae.output_device, dtype=vae.vae_output_dtype())
            pixels[0:1].copy_(out)
            vae.process_output(pixels[0:1])
            waveform = pixels.to(vae.output_device).movedim(1, -1).movedim(-1, 1).to(latent.device)
            output_copied = time.perf_counter()
            del samples, out, pixels
            model.to(device='cpu')
            torch.xpu.synchronize('xpu:3')
            released = time.perf_counter()
        after = workspace(torch, 'xpu:3', False)
        state['active'] = False
        state['calls'].append(run_name)
        released_state = assert_reference_released(vae)
        return {'waveform': waveform, 'sample_rate': int(model.output_sample_rate)}, {
            'workspace': {'before': before, 'after': after}, 'released': released_state,
            'seconds': {'reference_weight_and_latent_copy': copied-started,
                        'reference_decode': decoded-copied, 'reference_output_copy': output_copied-decoded,
                        'reference_unload': released-output_copied, 'reference_total': released-started}}
    except BaseException as error:
        state['failed'] = repr(error)
        raise


def decode(torch, vae, latent, native_decode, kind, run_name):
    """Candidate always uses the unchanged node; only eager controls add reference."""
    require(str(vae.device) == 'xpu:2', 'candidate audio must stay on xpu:2')
    assert_reference_released(vae)
    before = workspace(torch, 'xpu:2', True)
    started = time.perf_counter()
    audio = native_decode()
    torch.xpu.synchronize('xpu:2')
    elapsed = time.perf_counter()-started
    after = workspace(torch, 'xpu:2', False)
    evidence = {'mode': 'xpu2', 'device': 'xpu:2', 'kind': kind, 'run_name': run_name,
                'workspace': {'before': before, 'after': after},
                'candidate_native_node_seconds': elapsed, 'cross_card': None,
                'reference': None, 'reference_released': assert_reference_released(vae)}
    if kind == 'qualify-eager':
        reference, row = reference_decode(torch, vae, latent, run_name)
        evidence['cross_card'] = compare(torch, audio, reference)
        evidence['reference'] = row
        evidence['reference_released'] = assert_reference_released(vae)
    else:
        require(len(getattr(vae, REFERENCE_ATTRIBUTE)['calls']) == 3, 'all three cross-card eager controls required')
    return audio, evidence


def validate_evidence(receipt=None, decode=None):
    """Read-only receipt/client gate. Native qualification still owns admission."""
    def need(ok, why):
        if not ok:
            raise ValueError('Audio residency evidence: ' + why)
    source = receipt if receipt is not None else decode or {}
    mode = (source.get('server_options') or {}).get('audio_residency', 'legacy')
    need(mode in MODES, 'unknown mode')
    if mode == 'legacy':
        return {'enabled': False}
    if decode is None:
        return {'enabled': True, 'decode_pending': True}
    need(decode.get('audio_residency') == mode and decode.get('audio_device') == 'xpu:2', 'placement differs')
    if receipt is not None:
        need(decode.get('run_name') == receipt.get('run_name') and
             decode.get('prompt_id') == receipt.get('prompt_id'), 'decode belongs to another receipt')
    row = decode.get('audio_residency_evidence')
    need(type(row) is dict and row.get('mode') == mode and row.get('device') == 'xpu:2' and
         row.get('kind') == decode.get('kind') and row.get('run_name') == decode.get('run_name'), 'identity differs')
    def timing(value):
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    need(timing(row.get('candidate_native_node_seconds')), 'native timing missing')
    def workspace_row(value, device):
        need(type(value) is dict and set(value) == {'before', 'after'}, 'workspace samples missing')
        for phase, before in (('before', True), ('after', False)):
            sample = value[phase]
            need(type(sample) is dict, 'workspace sample missing')
            try:
                expected = check_workspace(sample.get('free_bytes'), device, before,
                                           sample.get('new_resident_bytes', 0))
            except RuntimeError as error:
                raise ValueError('Audio residency evidence: ' + str(error)) from error
            need(sample == expected and sample.get('passed') is True and sample.get('before') is before,
                 'workspace fields differ')
    workspace_row(row.get('workspace'), 'xpu:2')
    def released(value):
        need(type(value) is dict and set(value) == {'device', 'active', 'calls', 'resident_bytes_on_xpu3', 'weight_sha256'},
             'reference release missing')
        need(value['device'] == 'cpu' and value['active'] is False and type(value['resident_bytes_on_xpu3']) is int
             and value['resident_bytes_on_xpu3'] == 0 and type(value['calls']) is int and
             re.fullmatch('[0-9a-f]{64}', str(value['weight_sha256'])) is not None, 'reference release differs')
    released(row.get('reference_released'))
    eager = decode.get('kind') == 'qualify-eager'
    need(1 <= row['reference_released']['calls'] <= 3 if eager else row['reference_released']['calls'] == 3,
         'reference call count differs')
    if eager:
        ref, cross = row.get('reference'), row.get('cross_card')
        need(type(ref) is dict and type(cross) is dict, 'cross-card eager control missing')
        workspace_row(ref.get('workspace'), 'xpu:3')
        released(ref.get('released'))
        need(ref['released'] == row['reference_released'], 'release records disagree')
        seconds = ref.get('seconds')
        need(type(seconds) is dict and set(seconds) == {'reference_weight_and_latent_copy', 'reference_decode',
             'reference_output_copy', 'reference_unload', 'reference_total'} and all(timing(v) for v in seconds.values()),
             'isolated reference timing missing')
        wave = (decode.get('tensors') or {}).get('waveform') or {}
        need(cross.get('equal') is True and cross.get('device') == 'xpu:2' and cross.get('reference_device') == 'xpu:3'
             and cross.get('mode') == 'native-eager-uncached' and cross.get('sample_rate') == decode.get('sample_rate')
             and cross.get('waveform_sha256') == cross.get('reference_waveform_sha256') == wave.get('sha256')
             and cross.get('shape') == wave.get('shape') and cross.get('dtype') == wave.get('dtype'), 'waveform byte gate differs')
    else:
        need(row.get('reference') is None and row.get('cross_card') is None, 'unexpected post-capture reference')
    return {'enabled': True, 'cross_card': eager, 'reference_released': True}


def transform_host(raw):
    require(type(raw) is bytes and hashlib.sha256(raw).hexdigest() == HOST_SHA256, 'host parent hash differs')
    text = raw.decode()
    changes = [
        ('AUX_RESIDENCY = residency123.launch(_os.environ)\n',
         'AUX_RESIDENCY = residency123.launch(_os.environ)\nimport audio_residency132\nAUDIO_RESIDENCY = audio_residency132.launch(_os.environ)\n'),
        ('device=torch.device(residency123.vae_device(name, AUX_RESIDENCY)))',
         'device=torch.device(audio_residency132.vae_device(name, AUX_RESIDENCY, AUDIO_RESIDENCY)))'),
        ('                    vae.throw_exception_if_invalid()\n',
         '                    vae.throw_exception_if_invalid()\n                    audio_residency132.prepare_reference(torch, vae, name, AUDIO_RESIDENCY)\n')]
    for old, new in changes:
        require(text.count(old) == 1, 'host insertion is not unique')
        text = text.replace(old, new, 1)
    ast.parse(text)
    return text.encode()

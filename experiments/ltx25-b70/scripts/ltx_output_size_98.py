"""Packet 98 immutable per-server geometry; import is stdlib-only."""
import os
import contextvars
import functools
import inspect

SIZES = ('256x256', '512x320', '640x384')
DEFAULT = '256x256'


def dimensions(size):
    if size not in SIZES:
        raise ValueError('LTX_OUTPUT_SIZE must be one of %s, got %r' % (SIZES, size))
    return tuple(map(int, size.split('x')))


OUTPUT_SIZE = os.environ.get('LTX_OUTPUT_SIZE', DEFAULT)
WIDTH, HEIGHT = dimensions(OUTPUT_SIZE)
TOKENS = (4 * (HEIGHT // 64) * (WIDTH // 64), 4 * (HEIGHT // 32) * (WIDTH // 32))
TOKEN_SCALE = TOKENS[1] / 256
# The server has one resolution and one batch; increasing resolution adds no signatures.
MAX_SIGNATURES_PER_BLOCK = 8
_SPEED_ONLY = contextvars.ContextVar('packet98_speed_only', default=False)


def receipt_metadata(size=OUTPUT_SIZE, batch=None, speed_only=None):
    dimensions(size)
    batch = int(os.environ.get('LTX_SAMPLER_BATCH', '1')) if batch is None else batch
    speed = size != DEFAULT or (_SPEED_ONLY.get() if speed_only is None else speed_only)
    return {'output_size': size, 'speed_only': bool(speed),
            'comparison': 'none (speed only)' if speed else 'references:' + {1: 'w93c', 2: 'b2', 4: 'b4'}[batch]}


def receipt_scope(fn):
    """Keep explicit speed arms labelled even at the default size, including failures."""
    signature = inspect.signature(fn)
    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        speed = signature.bind(*args, **kwargs).arguments.get('speed_only', False)
        token = _SPEED_ONLY.set(speed)
        try:
            return fn(*args, **kwargs)
        finally:
            _SPEED_ONLY.reset(token)
    return wrapped


def require_reference_size():
    if OUTPUT_SIZE != DEFAULT:
        raise RuntimeError('stored reference path refused at output size ' + OUTPUT_SIZE)


def latent_shape(stage=2, batch=1, size=OUTPUT_SIZE):
    w, h = dimensions(size)
    divisor = 64 if stage == 1 else 32
    if stage not in (1, 2):
        raise ValueError('stage must be 1 or 2')
    return (batch, 128, 4, h // divisor, w // divisor)


def image_shape(size=OUTPUT_SIZE):
    w, h = dimensions(size)
    return (25, h, w, 3)


def admit_arm(output_size=DEFAULT, speed_only=False):
    dimensions(output_size)
    if output_size != OUTPUT_SIZE or (OUTPUT_SIZE != DEFAULT and speed_only is not True):
        raise RuntimeError('output size mismatch or non-speed arm on a size-only server')


def check_latent(tensor, stage, batch=1):
    if tuple(tensor.shape) != latent_shape(stage, batch):
        raise RuntimeError('unexpected stage %d latent shape %r (size %s)' % (stage, tuple(tensor.shape), OUTPUT_SIZE))


def probe_rows(fixtures, load_unused, native_decode, replica_decode):
    """No saved output oracle: ten seeded inputs, byte comparison against native decode.

    CPU seeds do not change global RNG state. Real decoders run only when the GPU
    campaign explicitly calls this function. No checkpoint is read here.
    """
    import torch
    import ltx_decode_replica as placement
    decoders = list(replica_decode.items()) if isinstance(replica_decode, dict) else [('replica', replica_decode)]
    if not decoders or len(fixtures) != 10:
        raise RuntimeError('ten probes and at least one replica required')
    rows = []
    for i, fx in enumerate(fixtures):
        generator = torch.Generator(device='cpu').manual_seed(980000 + i)
        v = torch.randn(latent_shape(), generator=generator, device='cpu', dtype=torch.float32)
        a = torch.randn((1, 8, 26, 16), generator=generator, device='cpu', dtype=torch.float32)
        row = {'fixture': fx['fixture'], 'seed': 980000 + i, 'output_size': OUTPUT_SIZE,
               'references': 'none (speed only)', 'video_latent_shape': list(v.shape),
               'video_latent_sha256': placement.tensor_sha256(v),
               'audio_latent_sha256': placement.tensor_sha256(a)}
        outputs = {}
        for slot, decode in [('native', native_decode)] + decoders:
            images, audio = decode({'samples': v.clone()}, {'samples': a.clone()})
            image = images.detach().cpu().contiguous()
            wave = audio['waveform'].detach().cpu().contiguous()
            if tuple(image.shape) != image_shape() or tuple(wave.shape) != (1, 2, 48480):
                raise RuntimeError('size probe decode output shape mismatch')
            if not bool(torch.isfinite(image).all()) or not bool(torch.isfinite(wave).all()):
                raise RuntimeError('non-finite size probe output')
            outputs[slot] = (image, wave)
            row[slot] = {'images_sha256': placement.tensor_sha256(image),
                         'waveform_sha256': placement.tensor_sha256(wave)}
        def equal(pair):
            return all(x.dtype == y.dtype and x.shape == y.shape and
                       torch.equal(x.view(torch.uint8), y.view(torch.uint8))
                       for x, y in zip(outputs['native'], pair))
        for slot, _ in decoders:
            row[slot + '_matches_native'] = equal(outputs[slot])
        row['cards_bytewise_equal'] = all(row[s + '_matches_native'] for s, _ in decoders)
        row['passed'] = row['cards_bytewise_equal']
        rows.append(row)
    return all(r['passed'] for r in rows), rows

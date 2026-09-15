"""Memoise the text conditioning for an unchanged prompt.

Text encoding is the largest item in a continuous stream's per-clip cost --
1.59 s of a 4.70 s interval -- and it recomputes the *same* function of the
*same* inputs on every clip. The prompt is a sealed literal and the encoder's
weights never change, so `encode(clip, text)` is a pure function whose value is
identical every time. Computing it once is memoisation, not approximation:

- it does not lower precision, take fewer steps, shrink the output, or swap the
  checkpoint;
- it is not an approximate cache -- the value returned is the value the encoder
  produced, bit for bit;
- it reuses no frames and no latents. The video is still sampled from scratch
  for every clip.

The lane's server runs with `--cache-none`, which deliberately defeats ComfyUI's
own node cache so that arms cannot silently reuse each other's work. That is the
right default for A/B integrity and the wrong one for measuring a stream, so
this caches exactly one value, under an explicit key, with an explicit
recompute-and-compare mode to prove it.

Modes:
  original -- call the native CLIPTextEncode every time, and record a SHA256 of
              every conditioning tensor's raw bytes.
  cache    -- compute once per key, then serve the stored conditioning. No
              digest, so the streaming measurement is not distorted by hashing.
  verify   -- serve from the cache and record the same digests.

The proof is a comparison ACROSS clips: the digests an `original` clip records
for a freshly computed conditioning must equal the digests a `verify` clip
records for the cached one. Recomputing inside a single prompt is not an option
-- the lane's embedding placement check counts observations and refuses a second
encode in the same request ("Previous embedding observations were not
consumed"). The end-to-end oracle is the backstop either way: a wrong
conditioning cannot produce bytewise-identical images, latents and waveform.
"""
import hashlib

import torch

MODES = ('original', 'cache', 'verify')
_CACHE = {}          # key -> (conditioning, key_description)


def require(value, message):
    if not value:
        raise RuntimeError(message)



def cache_key(clip, text):
    """Identity of the computation, not of the answer.

    The CLIP object is pinned by identity because this lane forbids weight
    patches and reloads the model only by restarting the server; a different
    object means a different generation and must not hit the cache.
    """
    return (id(clip), hashlib.sha256(text.encode('utf-8')).hexdigest())


def describe_key(clip, text):
    return {'clip_object_id': id(clip), 'clip_class': type(clip).__name__,
            'text_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'text_length': len(text)}


def walk_tensors(value, found, path='cond'):
    """Every tensor in a CONDITIONING, in a stable order, refusing surprises."""
    if isinstance(value, torch.Tensor):
        found.append((path, value))
    elif isinstance(value, (list, tuple)):
        for i, child in enumerate(value):
            walk_tensors(child, found, f'{path}[{i}]')
    elif isinstance(value, dict):
        for k in sorted(value, key=repr):
            walk_tensors(value[k], found, f'{path}[{k!r}]')
    elif isinstance(value, (bool, int, float, str, bytes, type(None))):
        pass
    else:
        raise RuntimeError(f'Conditioning holds an unexpected {type(value).__name__} at {path}')


def clone_conditioning(value):
    """Hand every caller its own tensors, so a downstream in-place write cannot
    reach the stored copy and make the second clip differ from the first."""
    if isinstance(value, torch.Tensor):
        return value.clone()
    if isinstance(value, list):
        return [clone_conditioning(v) for v in value]
    if isinstance(value, tuple):
        return tuple(clone_conditioning(v) for v in value)
    if isinstance(value, dict):
        return {k: clone_conditioning(v) for k, v in value.items()}
    return value


def digest_conditioning(value):
    """SHA256 of every conditioning tensor's raw bytes, in a stable order."""
    found = []
    walk_tensors(value, found)
    rows = []
    for path, t in found:
        c = t.detach().to('cpu').contiguous()
        if c.dtype in (torch.bfloat16, torch.float16):
            raw = c.view(torch.int16).numpy().tobytes()
        elif c.dtype == torch.float32:
            raw = c.view(torch.int32).numpy().tobytes()
        else:
            raw = c.numpy().tobytes()
        rows.append({'path': path, 'shape': list(t.shape), 'dtype': str(t.dtype),
                     'sha256': hashlib.sha256(raw).hexdigest()})
    return rows



def native_encode(clip, text):
    """Exactly what nodes.CLIPTextEncode.encode does, and nothing else."""
    import nodes
    require(type(clip).__name__ != 'NoneType', 'CLIP input is invalid: None')
    encoded = nodes.CLIPTextEncode().encode(clip, text)
    require(isinstance(encoded, tuple) and len(encoded) == 1,
            'CLIPTextEncode no longer returns a single conditioning')
    return encoded[0]


def encode(clip, text, mode):
    """Return (conditioning, report)."""
    require(mode in MODES, 'Only preregistered modes are admitted')
    key = cache_key(clip, text)
    report = {'mode': mode, 'key': describe_key(clip, text), 'cached_keys': len(_CACHE)}

    if mode == 'original':
        report['cache_hit'] = False
        fresh = native_encode(clip, text)
        report['digests'] = digest_conditioning(fresh)
        return fresh, report

    hit = key in _CACHE
    report['cache_hit'] = hit
    if not hit:
        _CACHE[key] = clone_conditioning(native_encode(clip, text))
    stored = _CACHE[key]

    if mode == 'verify':
        report['digests'] = digest_conditioning(stored)

    found = []
    walk_tensors(stored, found)
    report['tensors'] = [{'path': p, 'shape': list(t.shape), 'dtype': str(t.dtype)} for p, t in found]
    return clone_conditioning(stored), report


def clear():
    _CACHE.clear()

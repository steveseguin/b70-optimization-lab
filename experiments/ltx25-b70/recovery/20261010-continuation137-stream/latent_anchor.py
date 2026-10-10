"""Packet115 latent and guide anchors: file formats, the slot-0 copy, the guards and the pin diagnostics.

No Torch/Comfy import at module import; the runtime passes `torch` and the native
`get_noise_mask` (from the sealed comfy_extras/nodes_lt.py the bindings pin).

The anchor of chunk n is two latent slices of chunk n's own outputs, taken by the
output node before anything is handed to the decode thread:

- A: node 367 video_latent[:, :, T-1:T]   ([1,128,1,4,4], 8,192 bytes; stage A, before the upsampler)
- B: node 369 video_latent[:, :, T-1:T]   ([1,128,1,8,8], 32,768 bytes; stage B)

stored as one 40,960-byte file (A then B, little-endian F32, no header) written once
(exclusive create, fsync) and named by its whole-file SHA-256. Chunk n+1 re-reads it
and checks the length, finiteness and that hash before either stage uses it.

The conditioning is LTXVImgToVideoInplace.execute (nodes_lt.py:152-177) with the VAE
encode replaced by "take this latent": lines 156 (clone), 172 (slot copy) and 174-175
(mask slot set to 1 - strength, from get_noise_mask). Shapes, mask layout and token
counts are those of the packet113 graph at the same length, so the sampler graph
signatures are unchanged. The sampler then blends slot 0 back to the pinned latent
every step (samplers.py:638-642), so the stage output's slot 0 equals the anchor up to
signed zero; `pin_diagnostic` records that per chunk (diagnostic, never a gate).

Packet115:

- `mixed` uses the same 40,960-byte latent file, but only its stage-A slice: stage A is
  the slot-0 copy above (LatentConditionGuard with stages ('A',)); stage B is the native
  image conditioning on the predecessor's decoded frame (conditioning_guard.py,
  first_stage='B').
- `guide` keeps the last TWO latent slots of each stage, [1,128,2,4,4] and [1,128,2,8,8]
  (16,384 + 65,536 = 81,920 bytes, A then B, `.guide.f32`). The native LTXVAddLatentGuide
  appends them at latent index -2 and LTXVCropGuides removes them after each sampler;
  GuideGuard orders and checks those four native calls (guide A, crop A, guide B, crop B).
"""
import copy
import hashlib
import os
from pathlib import Path
import stat
import struct
import threading

import stream_contract as contract

SUFFIX = '.latent.f32'


class LatentAnchorError(RuntimeError):
    pass


def require(ok, why):
    if not ok:
        raise LatentAnchorError(why)


def finite_f32(raw):
    require(type(raw) is bytes and len(raw) % 4 == 0, 'F32 bytes required')
    require(all(word & 0x7f800000 != 0x7f800000 for (word,) in struct.iter_unpack('<I', raw)),
            'Nonfinite F32 value in the latent anchor')


def _safe(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts and
            not any(p.is_symlink() for p in (path, *path.parents)), 'Unsafe latent anchor path')
    return path


FORMATS = {
    # anchor mode -> (parts, part bytes, total bytes, slots per part, file suffix)
    'latent': (contract.LATENT_ANCHOR_PARTS, contract.LATENT_ANCHOR_PART_BYTES, contract.LATENT_ANCHOR_BYTES, 1,
               '.latent.f32'),
    'mixed': (contract.LATENT_ANCHOR_PARTS, contract.LATENT_ANCHOR_PART_BYTES, contract.LATENT_ANCHOR_BYTES, 1,
              '.latent.f32'),
    'guide': (contract.GUIDE_ANCHOR_PARTS, contract.GUIDE_ANCHOR_PART_BYTES, contract.GUIDE_ANCHOR_BYTES,
              contract.GUIDE_FRAMES, '.guide.f32'),
}


def _format(kind):
    require(kind in FORMATS, 'Unknown latent anchor kind: %r' % (kind,))
    return FORMATS[kind]


def slot_bytes(torch, samples, slot, count=1):
    """samples[:, :, slot:slot+count] as complete little-endian F32 bytes (CPU, contiguous copy)."""
    t = samples.detach().to('cpu')[:, :, slot:slot + count].contiguous()
    require(t.dtype is torch.float32, 'Latent anchor slices must be F32')
    return t.view(torch.uint8).numpy().tobytes()


def anchor_bytes(torch, stage_a_samples, stage_b_samples, frames, kind='latent'):
    """The anchor of a finished chunk: A slots then B slots (the last latent slot, or the last two for
    `guide`)."""
    parts, part_bytes, total, count, _ = _format(kind)
    g = contract.geometry(frames)
    first = g['latent_anchor_slot'] - (count - 1)
    require(list(stage_a_samples.shape) == g['stage_shapes']['A'] and
            list(stage_b_samples.shape) == g['stage_shapes']['B'], 'Latent anchor source shapes differ')
    a = slot_bytes(torch, stage_a_samples, first, count)
    b = slot_bytes(torch, stage_b_samples, first, count)
    require(len(a) == part_bytes['A'] and len(b) == part_bytes['B'], 'Latent anchor slice sizes differ')
    raw = a + b
    require(len(raw) == total, 'Latent anchor size differs')
    finite_f32(raw)
    return raw


def split(torch, raw, kind='latent'):
    """(A, B) CPU F32 tensors that own their storage, from verified anchor-file bytes."""
    parts, part_bytes, total, _, _ = _format(kind)
    require(type(raw) is bytes and len(raw) == total, 'Latent anchor must be %d bytes' % total)
    out, offset = [], 0
    for name, shape in parts:
        size = part_bytes[name]
        out.append(torch.frombuffer(bytearray(raw[offset:offset + size]), dtype=torch.float32)
                   .reshape(*shape).clone())
        offset += size
    return tuple(out)


def anchor_path(anchor_dir, run_name, kind='latent'):
    return _safe(anchor_dir) / (run_name + _format(kind)[4])


def write_anchor(anchor_dir, run_name, raw, frames, kind='latent'):
    parts, part_bytes, total, count, _ = _format(kind)
    require(type(raw) is bytes and len(raw) == total, 'Latent anchor must be %d bytes' % total)
    finite_f32(raw)
    path = anchor_path(anchor_dir, run_name, kind)
    import evidence_publication
    evidence_publication.publish_bytes(path, raw)
    g = contract.geometry(frames)
    last = g['latent_anchor_slot']
    slots = list(range(last - count + 1, last + 1))
    layout, offset = [], 0
    for name, shape in parts:
        size = part_bytes[name]
        layout.append({'part': name, 'shape': list(shape), 'offset': offset, 'bytes': size,
                       'source': ('367' if name == 'A' else '369') + ' video_latent slot%s %s'
                                 % ('s' if count > 1 else '', ','.join(str(s) for s in slots))})
        offset += size
    out = {'kind': kind, 'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(),
           'bytes': len(raw), 'slot': last, 'layout': layout, 'dtype': 'F32', 'byte_order': 'little'}
    if kind == 'guide':
        out.update(slots=slots, latent_idx=contract.GUIDE_LATENT_IDX)
    return out


def read_anchor(path, expected_sha256, kind='latent'):
    total = _format(kind)[2]
    require(type(expected_sha256) is str and contract.SHA_RE.fullmatch(expected_sha256),
            'Expected latent anchor SHA required')
    path = _safe(path)
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == total,
                'Latent anchor file is not a single-link %d-byte file' % total)
        raw = stream.read(total + 1)
        key = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
        require(len(raw) == total and key(before) == key(os.fstat(stream.fileno())) ==
                key(path.lstat()), 'Latent anchor changed during read')
    require(hashlib.sha256(raw).hexdigest() == expected_sha256, 'Latent anchor bytes differ from the recorded hash')
    finite_f32(raw)
    return raw


def condition(get_noise_mask, latent, anchor, strength):
    """nodes_lt.py LTXVImgToVideoInplace.execute lines 156, 172, 174-175 with t = anchor.

    Kept statement for statement (the test compares it with the sealed source by
    executing the native method on a stub VAE whose encode returns `anchor`)."""
    samples = latent["samples"].clone()
    t = anchor
    samples[:, :, :t.shape[2]] = t
    conditioning_latent_frames_mask = get_noise_mask(latent)
    conditioning_latent_frames_mask[:, :, :t.shape[2]] = 1.0 - strength
    return {"samples": samples, "noise_mask": conditioning_latent_frames_mask}


def pin_diagnostic(torch, output_samples, anchor, tail=False):
    """Does the stage output's slot 0 (or, tail=True, its last anchor.shape[2] slots: the guide
    frames before the crop) equal the pinned anchor? Byte equality, else whether every differing
    element is a signed-zero pair (-0.0 vs +0.0). Diagnostic only."""
    n = int(anchor.shape[2])
    full = output_samples.detach().to('cpu')
    out = (full[:, :, -n:] if tail else full[:, :, :n]).contiguous()
    ref = anchor.detach().to('cpu').contiguous()
    require(list(out.shape) == list(ref.shape) and out.dtype is ref.dtype is torch.float32,
            'Pin diagnostic shapes differ')
    a, b = out.view(torch.int32), ref.view(torch.int32)
    differ = a != b
    n = int(differ.sum())
    both_zero = (out == 0) & (ref == 0)
    return {'bytes_equal': n == 0, 'elements': int(out.numel()), 'differing_elements': n,
            'differing_all_signed_zero': bool((~differ | both_zero).all()),
            'anchor_negative_zeros': int(((ref == 0) & torch.signbit(ref)).sum()),
            'output_negative_zeros': int(((out == 0) & torch.signbit(out)).sum()),
            'output_finite': bool(torch.isfinite(out).all()), 'diagnostic_only': True}


class LatentConditionGuard:
    """Per-request guard for the two latent conditioning calls (A then B, exactly once each).

    tensor_metadata(tensor) returns object_id/storage_id/shape/dtype/device/contiguous
    (the packet113 bindings callback). No device work: every tensor here is CPU F32."""

    def __init__(self, *, tensor_metadata, get_noise_mask, frames):
        require(callable(tensor_metadata) and callable(get_noise_mask), 'Trusted callbacks required')
        self.tensor_metadata = tensor_metadata
        self.get_noise_mask = get_noise_mask
        self.geometry = contract.geometry(frames)
        self.active = None
        self.seen = set()
        self.failed = None
        self.receipts = []
        self.lock = threading.Lock()
        self.anchor_sha256 = self.parts = self.next_stage = self.thread = None
        self.stages = ('A', 'B')

    def _meta(self, tensor, shape):
        m = self.tensor_metadata(tensor)
        require(type(m) is dict and m.get('shape') == list(shape) and m.get('dtype') == 'torch.float32' and
                m.get('device') == 'cpu' and m.get('contiguous') is True, 'Latent conditioning tensor differs')
        return copy.deepcopy(m)

    def _latch(self, error):
        if self.failed is None:
            self.failed = str(error)[:512]
            self.receipts.append({'event': 'failure', 'request_id': self.active, 'reason': self.failed})

    def begin_request(self, request_id, anchor_sha256, parts, stages=('A', 'B')):
        """stages: ('A', 'B') for the latent anchor; ('A',) for the mixed anchor (stage B is the
        native image conditioning on the decoded frame, through conditioning_guard)."""
        with self.lock:
            try:
                require(self.failed is None, self.failed or 'Latent guard failed')
                require(stages in (('A', 'B'), ('A',)), 'Latent conditioning stages are (A, B) or (A,)')
                require(self.active is None and type(request_id) is str and request_id not in self.seen,
                        'New conditioned request required')
                require(type(anchor_sha256) is str and contract.SHA_RE.fullmatch(anchor_sha256), 'Anchor SHA required')
                require(type(parts) is tuple and len(parts) == 2, 'Two anchor parts required')
                metas = [self._meta(t, shape) for t, (_, shape) in zip(parts, contract.LATENT_ANCHOR_PARTS)]
                require(metas[0]['storage_id'] != metas[1]['storage_id'], 'Anchor parts alias')
                self.active, self.anchor_sha256, self.parts = request_id, anchor_sha256, parts
                self.part_meta = metas
                self.seen.add(request_id)
                self.stages, self.next_stage, self.thread = stages, 'A', threading.get_ident()
                self.receipts.append({'event': 'begin', 'request_id': request_id, 'anchor_sha256': anchor_sha256,
                                      'stages': list(stages)})
            except BaseException as error:
                self._latch(error)
                raise

    def run_stage(self, stage, *, request_id, latent, anchor, strength):
        with self.lock:
            try:
                require(self.failed is None, self.failed or 'Latent guard failed')
                require(request_id == self.active and threading.get_ident() == self.thread,
                        'Active conditioned request/thread changed')
                require(stage == self.next_stage and stage in self.stages,
                        'Expected stage%s %s in order, exactly once' % ('s' if len(self.stages) > 1 else '',
                                                                         ' then '.join(self.stages)))
                index = 0 if stage == 'A' else 1
                require(type(anchor) is dict and set(anchor) == {'samples'} and anchor['samples'] is self.parts[index],
                        'Stage %s must use its own anchor part' % stage)
                require(type(strength) in (int, float) and strength == 1.0, 'Strength is fixed at 1.0')
                require(type(latent) is dict and 'samples' in latent and 'noise_mask' not in latent,
                        'Expected an unconditioned latent without a mask')
                shape = self.geometry['stage_shapes'][stage]
                before = self._meta(latent['samples'], shape)
                require(self._meta(self.parts[index], contract.LATENT_ANCHOR_PARTS[index][1]) == self.part_meta[index],
                        'Anchor part ownership changed')
                result = condition(self.get_noise_mask, latent, self.parts[index], 1.0)
                require(self._meta(latent['samples'], shape) == before, 'Input latent ownership changed')
                samples = self._meta(result['samples'], shape)
                mask = self._meta(result['noise_mask'], self.geometry['noise_mask_shape'])
                require(len({before['storage_id'], self.part_meta[index]['storage_id'], samples['storage_id'],
                             mask['storage_id']}) == 4, 'Conditioning output aliases an input')
                self.receipts.append({'event': 'stage', 'request_id': request_id, 'stage': stage,
                                      'anchor_sha256': self.anchor_sha256, 'input': before, 'output': samples,
                                      'noise_mask': mask, 'completed': True})
                following = self.stages.index(stage) + 1
                self.next_stage = self.stages[following] if following < len(self.stages) else 'done'
                return result
            except BaseException as error:
                self._latch(error)
                raise

    def finish_request(self, request_id):
        with self.lock:
            try:
                require(self.failed is None and request_id == self.active and self.next_stage == 'done',
                        'Every latent conditioning stage must complete')
                self.receipts.append({'event': 'finish', 'request_id': request_id})
                parts = self.parts
                self.active = self.anchor_sha256 = self.parts = self.next_stage = self.thread = None
                return parts
            except BaseException as error:
                self._latch(error)
                raise

    def drain(self, request_id):
        rows = [r for r in self.receipts if r.get('request_id') == request_id]
        self.receipts = [r for r in self.receipts if r.get('request_id') != request_id]
        return rows


class GuideGuard:
    """Per-request guard for the guide anchor (LTX_ANCHOR=guide): the four native calls in order,
    guide A, crop A, guide B, crop B, each exactly once, on one thread.

    The runtime passes the native LTXVAddLatentGuide.execute / LTXVCropGuides.execute (pinned
    nodes_lt.py) as `native_call`; this guard checks their inputs and outputs only (identity,
    shapes, keyframe counts, the mask of the guide frames). No device work: CPU F32 tensors."""

    ORDER = (('guide', 'A'), ('crop', 'A'), ('guide', 'B'), ('crop', 'B'))

    def __init__(self, *, torch, tensor_metadata, get_keyframe_idxs, frames):
        require(callable(tensor_metadata) and callable(get_keyframe_idxs), 'Trusted callbacks required')
        self.torch = torch
        self.tensor_metadata = tensor_metadata
        self.get_keyframe_idxs = get_keyframe_idxs
        self.geometry = contract.geometry(frames)
        self.active = None
        self.seen = set()
        self.failed = None
        self.receipts = []
        self.lock = threading.Lock()
        self.anchor_sha256 = self.parts = self.step = self.thread = None
        self.guided = {}

    def _meta(self, tensor, shape):
        m = self.tensor_metadata(tensor)
        require(type(m) is dict and m.get('shape') == list(shape) and m.get('dtype') == 'torch.float32' and
                m.get('device') == 'cpu' and m.get('contiguous') is True, 'Guide tensor differs: %s' % (m,))
        return copy.deepcopy(m)

    def _latch(self, error):
        if self.failed is None:
            self.failed = str(error)[:512]
            self.receipts.append({'event': 'failure', 'request_id': self.active, 'reason': self.failed})

    def _expect(self, kind, stage, request_id):
        require(self.failed is None, self.failed or 'Guide guard failed')
        require(request_id == self.active and threading.get_ident() == self.thread,
                'Active guided request/thread changed')
        require(self.step < len(self.ORDER) and self.ORDER[self.step] == (kind, stage),
                'Expected guide A, crop A, guide B, crop B in order, exactly once')

    def _keyframes(self, cond, shape):
        idxs, count = self.get_keyframe_idxs(cond, shape)
        return 0 if idxs is None else int(count), None if idxs is None else list(idxs.shape)

    def begin_request(self, request_id, anchor_sha256, parts):
        with self.lock:
            try:
                require(self.failed is None, self.failed or 'Guide guard failed')
                require(self.active is None and type(request_id) is str and request_id not in self.seen,
                        'New guided request required')
                require(type(anchor_sha256) is str and contract.SHA_RE.fullmatch(anchor_sha256), 'Anchor SHA required')
                require(type(parts) is tuple and len(parts) == 2, 'Two guide parts required')
                metas = [self._meta(t, shape) for t, (_, shape) in zip(parts, contract.GUIDE_ANCHOR_PARTS)]
                require(metas[0]['storage_id'] != metas[1]['storage_id'], 'Guide parts alias')
                self.active, self.anchor_sha256, self.parts, self.part_meta = request_id, anchor_sha256, parts, metas
                self.seen.add(request_id)
                self.step, self.thread, self.guided = 0, threading.get_ident(), {}
                self.receipts.append({'event': 'begin', 'request_id': request_id, 'anchor_sha256': anchor_sha256})
            except BaseException as error:
                self._latch(error)
                raise

    def run_guide(self, stage, *, request_id, positive, negative, vae, latent, guide, strength, native_call):
        with self.lock:
            try:
                self._expect('guide', stage, request_id)
                index = 0 if stage == 'A' else 1
                require(type(guide) is dict and set(guide) == {'samples'} and guide['samples'] is self.parts[index],
                        'Stage %s must use its own guide part' % stage)
                require(self._meta(self.parts[index], contract.GUIDE_ANCHOR_PARTS[index][1]) == self.part_meta[index],
                        'Guide part ownership changed')
                require(type(strength) in (int, float) and strength == 1.0, 'Strength is fixed at 1.0')
                require(type(latent) is dict and 'samples' in latent and 'noise_mask' not in latent,
                        'Expected an unconditioned latent without a mask')
                require(self._keyframes(positive, latent['samples'].shape)[0] == 0 and
                        self._keyframes(negative, latent['samples'].shape)[0] == 0,
                        'Guide input conditioning already carries keyframes')
                before = self._meta(latent['samples'], self.geometry['stage_shapes'][stage])
                pos, neg, out = native_call(positive=positive, negative=negative, vae=vae, latent=latent,
                                            guiding_latent=guide, latent_idx=contract.GUIDE_LATENT_IDX,
                                            strength=1.0)
                require(self._meta(latent['samples'], self.geometry['stage_shapes'][stage]) == before,
                        'Input latent ownership changed')
                shape = self.geometry['guided_stage_shapes'][stage]
                samples = self._meta(out['samples'], shape)
                mask = self._meta(out['noise_mask'], self.geometry['guided_noise_mask_shape'])
                ones, zeros = out['noise_mask'][:, :, :-contract.GUIDE_FRAMES], out['noise_mask'][:, :, -contract.GUIDE_FRAMES:]
                require(bool((ones == 1.0).all()) and bool((zeros == 0.0).all()),
                        'Guide mask differs (ones on the chunk, zeros on the guide frames)')
                require(bitwise_equal(self.torch, out['samples'][:, :, -contract.GUIDE_FRAMES:], self.parts[index]),
                        'Guide frames are not the guide latent')
                kf = [self._keyframes(c, out['samples'].shape) for c in (pos, neg)]
                tokens = contract.GUIDE_FRAMES * shape[3] * shape[4]
                require(all(k[0] == contract.GUIDE_FRAMES and k[1] is not None and k[1][2] == tokens for k in kf),
                        'Guide keyframe tokens differ: %r' % (kf,))
                self.guided[stage] = out['samples']
                self.receipts.append({'event': 'guide', 'request_id': request_id, 'stage': stage,
                                      'anchor_sha256': self.anchor_sha256, 'input': before, 'output': samples,
                                      'noise_mask': mask, 'keyframe_idxs_shape': kf[0][1], 'guide_tokens': tokens,
                                      'stage_tokens': self.geometry['guided_stage_tokens'][stage], 'completed': True})
                self.step += 1
                return pos, neg, out
            except BaseException as error:
                self._latch(error)
                raise

    def run_crop(self, stage, *, request_id, positive, negative, latent, native_call):
        with self.lock:
            try:
                self._expect('crop', stage, request_id)
                shape = self.geometry['guided_stage_shapes'][stage]
                require(type(latent) is dict and list(latent['samples'].shape) == shape,
                        'Crop input is not the guided stage output')
                pos, neg, out = native_call(positive=positive, negative=negative, latent=latent)
                # The native crop returns a strided view (latent[:, :, :-2] of a clone): not contiguous by
                # design, so it is checked by shape, dtype and device instead of the contiguous metadata.
                cropped = out['samples']
                require(list(cropped.shape) == self.geometry['stage_shapes'][stage] and
                        cropped.dtype is self.torch.float32 and str(cropped.device) == 'cpu',
                        'Cropped stage output differs')
                samples = {'shape': list(cropped.shape), 'dtype': str(cropped.dtype), 'device': str(cropped.device),
                           'contiguous': bool(cropped.is_contiguous())}
                require(all(self._keyframes(c, out['samples'].shape)[0] == 0 for c in (pos, neg)),
                        'Cropped conditioning still carries keyframes')
                require(bitwise_equal(self.torch, out['samples'], latent['samples'][:, :, :-contract.GUIDE_FRAMES]),
                        'Crop changed the chunk frames')
                self.receipts.append({'event': 'crop', 'request_id': request_id, 'stage': stage, 'output': samples,
                                      'completed': True})
                self.step += 1
                return pos, neg, out
            except BaseException as error:
                self._latch(error)
                raise

    def finish_request(self, request_id):
        with self.lock:
            try:
                require(self.failed is None and request_id == self.active and self.step == len(self.ORDER),
                        'Guide A, crop A, guide B and crop B must all complete')
                self.receipts.append({'event': 'finish', 'request_id': request_id})
                parts = self.parts
                self.active = self.anchor_sha256 = self.parts = self.step = self.thread = None
                self.guided = {}
                return parts
            except BaseException as error:
                self._latch(error)
                raise

    def drain(self, request_id):
        rows = [r for r in self.receipts if r.get('request_id') == request_id]
        self.receipts = [r for r in self.receipts if r.get('request_id') != request_id]
        return rows



def bitwise_equal(torch, a, b):
    """Same dtype, shape and bits (int32 views of contiguous F32 copies)."""
    return (a.dtype is b.dtype is torch.float32 and list(a.shape) == list(b.shape) and
            torch.equal(a.detach().to('cpu').contiguous().view(torch.int32),
                        b.detach().to('cpu').contiguous().view(torch.int32)))

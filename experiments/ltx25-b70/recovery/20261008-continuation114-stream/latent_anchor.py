"""Packet114 latent anchor: file format, the slot-0 copy, its guard and the pin diagnostic.

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


def slot_bytes(torch, samples, slot):
    """samples[:, :, slot:slot+1] as complete little-endian F32 bytes (CPU, contiguous copy)."""
    t = samples.detach().to('cpu')[:, :, slot:slot + 1].contiguous()
    require(t.dtype is torch.float32, 'Latent anchor slices must be F32')
    return t.view(torch.uint8).numpy().tobytes()


def anchor_bytes(torch, stage_a_samples, stage_b_samples, frames):
    """The latent anchor of a finished chunk: A slot then B slot (both the last latent slot)."""
    g = contract.geometry(frames)
    slot = g['latent_anchor_slot']
    require(list(stage_a_samples.shape) == g['stage_shapes']['A'] and
            list(stage_b_samples.shape) == g['stage_shapes']['B'], 'Latent anchor source shapes differ')
    a, b = slot_bytes(torch, stage_a_samples, slot), slot_bytes(torch, stage_b_samples, slot)
    require(len(a) == contract.LATENT_ANCHOR_PART_BYTES['A'] and len(b) == contract.LATENT_ANCHOR_PART_BYTES['B'],
            'Latent anchor slice sizes differ')
    raw = a + b
    finite_f32(raw)
    return raw


def split(torch, raw):
    """(A, B) CPU F32 tensors that own their storage, from verified anchor-file bytes."""
    require(type(raw) is bytes and len(raw) == contract.LATENT_ANCHOR_BYTES, 'Latent anchor must be 40,960 bytes')
    out, offset = [], 0
    for name, shape in contract.LATENT_ANCHOR_PARTS:
        size = contract.LATENT_ANCHOR_PART_BYTES[name]
        out.append(torch.frombuffer(bytearray(raw[offset:offset + size]), dtype=torch.float32)
                   .reshape(*shape).clone())
        offset += size
    return tuple(out)


def anchor_path(anchor_dir, run_name):
    return _safe(anchor_dir) / (run_name + SUFFIX)


def write_anchor(anchor_dir, run_name, raw, frames):
    require(type(raw) is bytes and len(raw) == contract.LATENT_ANCHOR_BYTES, 'Latent anchor must be 40,960 bytes')
    finite_f32(raw)
    path = anchor_path(anchor_dir, run_name)
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    g = contract.geometry(frames)
    layout, offset = [], 0
    for name, shape in contract.LATENT_ANCHOR_PARTS:
        size = contract.LATENT_ANCHOR_PART_BYTES[name]
        layout.append({'part': name, 'shape': list(shape), 'offset': offset, 'bytes': size,
                       'source': ('367' if name == 'A' else '369') + ' video_latent slot %d' % g['latent_anchor_slot']})
        offset += size
    return {'kind': 'latent', 'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(),
            'bytes': len(raw), 'slot': g['latent_anchor_slot'], 'layout': layout,
            'dtype': 'F32', 'byte_order': 'little'}


def read_anchor(path, expected_sha256):
    require(type(expected_sha256) is str and contract.SHA_RE.fullmatch(expected_sha256),
            'Expected latent anchor SHA required')
    path = _safe(path)
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                before.st_size == contract.LATENT_ANCHOR_BYTES,
                'Latent anchor file is not a single-link 40,960-byte file')
        raw = stream.read(contract.LATENT_ANCHOR_BYTES + 1)
        key = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
        require(len(raw) == contract.LATENT_ANCHOR_BYTES and key(before) == key(os.fstat(stream.fileno())) ==
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


def pin_diagnostic(torch, output_samples, anchor):
    """Does the stage output's slot 0 equal the pinned anchor? Byte equality, else whether every
    differing element is a signed-zero pair (-0.0 vs +0.0). Diagnostic only."""
    out = output_samples.detach().to('cpu')[:, :, :1].contiguous()
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

    def _meta(self, tensor, shape):
        m = self.tensor_metadata(tensor)
        require(type(m) is dict and m.get('shape') == list(shape) and m.get('dtype') == 'torch.float32' and
                m.get('device') == 'cpu' and m.get('contiguous') is True, 'Latent conditioning tensor differs')
        return copy.deepcopy(m)

    def _latch(self, error):
        if self.failed is None:
            self.failed = str(error)[:512]
            self.receipts.append({'event': 'failure', 'request_id': self.active, 'reason': self.failed})

    def begin_request(self, request_id, anchor_sha256, parts):
        with self.lock:
            try:
                require(self.failed is None, self.failed or 'Latent guard failed')
                require(self.active is None and type(request_id) is str and request_id not in self.seen,
                        'New conditioned request required')
                require(type(anchor_sha256) is str and contract.SHA_RE.fullmatch(anchor_sha256), 'Anchor SHA required')
                require(type(parts) is tuple and len(parts) == 2, 'Two anchor parts required')
                metas = [self._meta(t, shape) for t, (_, shape) in zip(parts, contract.LATENT_ANCHOR_PARTS)]
                require(metas[0]['storage_id'] != metas[1]['storage_id'], 'Anchor parts alias')
                self.active, self.anchor_sha256, self.parts = request_id, anchor_sha256, parts
                self.part_meta = metas
                self.seen.add(request_id)
                self.next_stage, self.thread = 'A', threading.get_ident()
                self.receipts.append({'event': 'begin', 'request_id': request_id, 'anchor_sha256': anchor_sha256})
            except BaseException as error:
                self._latch(error)
                raise

    def run_stage(self, stage, *, request_id, latent, anchor, strength):
        with self.lock:
            try:
                require(self.failed is None, self.failed or 'Latent guard failed')
                require(request_id == self.active and threading.get_ident() == self.thread,
                        'Active conditioned request/thread changed')
                require(stage == self.next_stage and stage in ('A', 'B'), 'Expected stage A then B exactly once')
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
                self.next_stage = 'B' if stage == 'A' else 'done'
                return result
            except BaseException as error:
                self._latch(error)
                raise

    def finish_request(self, request_id):
        with self.lock:
            try:
                require(self.failed is None and request_id == self.active and self.next_stage == 'done',
                        'Both latent conditioning stages must complete')
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

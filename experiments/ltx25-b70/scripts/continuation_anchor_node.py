"""Inactive Comfy provider of one exact captured float frame; no media decoding.

Keep this file and continuation_anchor_io.py together in a future pinned runtime.
Importing this module alone does not import Torch or touch devices. Actual tensor
construction still requires native CPU/runtime qualification before deployment.
"""
from pathlib import Path
import re
import sys

from continuation_anchor_io import extract_anchor


FAULT_ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')


def read_predecessor(output_root, predecessor_run, expected_sha256):
    """Read one named validation capture; callers must keep it immutable.

    Reject existing symlink paths. This check does not lock out concurrent path
    replacement; a future stream controller must own the predecessor lifetime.
    The supplied frame hash is always checked against the actual bytes read.
    """
    if not isinstance(predecessor_run, str) or not re.fullmatch(
            r'[a-z0-9_-]+', predecessor_run):
        raise ValueError('predecessor_run must be a simple lowercase capture identifier')
    if not isinstance(expected_sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', expected_sha256):
        raise ValueError('expected SHA256 must be 64 lowercase hexadecimal characters')
    root = Path(output_root).resolve() / 'validation'
    capture = root / predecessor_run / 'tensors.safetensors'
    if capture.resolve() != capture or capture.is_symlink():
        raise ValueError('predecessor capture resolves through a symlink')
    payload, metadata = extract_anchor(capture)
    # Extraction has already checked length, layout, finiteness and the hash.
    # Compare the digest without another complete Python sample scan.
    if metadata['sha256'] != expected_sha256:
        raise ValueError('anchor SHA256 mismatch')
    return payload, metadata


class LTXLoadFloatContinuationAnchor:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'predecessor_run': ('STRING',),
                             'expected_sha256': ('STRING',)}}

    RETURN_TYPES = ('IMAGE',)
    FUNCTION = 'load'
    CATEGORY = 'lab/validation'

    @classmethod
    def IS_CHANGED(cls, predecessor_run, expected_sha256):
        # Re-read and verify each request, including same-input replay. A cached
        # IMAGE must never hide a missing, corrupted or replaced capture file.
        return float('nan')

    def load(self, predecessor_run, expected_sha256):
        if (FAULT_ROOT / 'FAULT.json').exists():
            raise RuntimeError('Host fault recorded; halt continuation requests')
        if sys.byteorder != 'little':
            raise RuntimeError('This pinned float-anchor provider requires little-endian CPU')
        import folder_paths
        payload, _ = read_predecessor(folder_paths.get_output_directory(),
                                      predecessor_run, expected_sha256)
        import torch
        # Writable backing avoids frombuffer's immutable-buffer warning. Clone
        # gives this IMAGE independent owned storage, with no dtype conversion.
        image = torch.frombuffer(bytearray(payload), dtype=torch.float32)
        image = image.reshape(1, 256, 256, 3).clone()
        return (image,)


NODE_CLASS_MAPPINGS = {'LTXLoadFloatContinuationAnchor': LTXLoadFloatContinuationAnchor}

"""Bounded XPU graph-capture gate for the native LTX video decoder.

`original` leaves the decoder untouched; `graph` shadows its two pure methods
with graph-backed stand-ins; `restored` puts the class methods back. The decoder
module, its registration and its weights are never modified.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import time

import torch

import ltx_graph_vae as adapter
from encoder_diagnostics import _context

MODEL_SHA256 = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
MODES = ('original', 'graph', 'restored')
_installed = None      # (vae, originals, report)
_original_vae = None
_failed = False


def require(value, message):
    if not value:
        raise RuntimeError(message)


def write_json(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def device_memory():
    return {f'xpu:{i}': {'allocated_bytes': int(torch.xpu.memory_allocated(i)),
                         'reserved_bytes': int(torch.xpu.memory_reserved(i))}
            for i in range(torch.xpu.device_count())}


class LTXVAEGraphGate:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'vae': ('VAE',), 'mode': (list(MODES),),
                             'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ('VAE',)
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, vae, mode, run_name):
        global _failed
        try:
            return self._apply(vae, mode, run_name)
        except BaseException:
            # Sticky: preserve the process and evidence, never retry or reset.
            _failed = True
            raise

    def _apply(self, vae, mode, run_name):
        global _installed, _original_vae
        require(not _failed, 'Previous VAE graph failure; halt submissions and inspect evidence')
        require(mode in MODES, 'Only preregistered modes are admitted')
        require(isinstance(run_name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', run_name),
                'Unsafe request name')
        run, identity = _context()
        require(identity['model_verification_sha256'] == MODEL_SHA256 and
                identity['server_identity_sha256'] == os.environ.get('LTX_ENCODER_IDENTITY_SHA256'),
                'Model/startup identity changed')
        server = json.loads((run / 'server-identity.json').read_text())
        hashes = {}
        for path, name in ((Path(adapter.__file__), 'ltx_graph_vae.py'),
                           (Path(__file__), 'graph_vae_node.py')):
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            require(server['extension_sha256s'][name] == actual, 'Sealed extension changed: ' + name)
            hashes[name] = actual
        require(torch.are_deterministic_algorithms_enabled() and
                not torch.is_deterministic_algorithms_warn_only_enabled(), 'Strict determinism required')
        require(_original_vae is None or vae is _original_vae, 'Resident VAE generation changed')
        _original_vae = vae
        decoder = adapter.decoder_of(vae, strict_placement=mode not in ('original', 'restored'))

        report = {'schema': 'ltx.vae-graph-request.v1', **identity, 'run_name': run_name,
                  'mode': mode, 'extension_sha256s': hashes,
                  'decoder_class': type(decoder).__name__,
                  'decoder_device': str(next(decoder.parameters()).device),
                  'decoder_placement': adapter.placement_of(decoder),
                  'captured_methods': list(adapter.METHODS),
                  'capture_proof': 'each captured graph must replay bit-identically to a fresh eager call '
                                   'of the same decoder method on the same inputs, and must be proven '
                                   'non-inert by perturbing a static input',
                  'not_captured': 'NADiffusionDecoder.forward itself draws x_t from a generator and is '
                                  'deliberately left eager',
                  'memory_before': device_memory(), 'passed': False}
        started = time.monotonic()
        try:
            if mode == 'original':
                require(_installed is None, 'Decoder methods are shadowed; run the restored mode first')
            elif mode == 'graph':
                if _installed is None:
                    captures, originals = adapter.install(vae)
                    _installed = (vae, originals, captures)
                    report['installed_now'] = True
                else:
                    resident, originals, captures = _installed
                    require(resident is vae, 'A different VAE is already shadowed')
                    report['installed_now'] = False
            else:
                # 'restored' means "ensure the original state". An arm that never
                # shadowed the decoder is already in that state, so this is a
                # no-op rather than an error; the receipt records which it was.
                if _installed is None:
                    adapter.decoder_of(vae, strict_placement=False)
                    report['restored_blocks'] = []
                    report['was_shadowed'] = False
                else:
                    resident, originals, captures = _installed
                    require(resident is vae, 'Restore target is not the shadowed VAE')
                    adapter.restore(vae, originals)
                    report['capture_summary_at_restore'] = captures.summary()
                    report['was_shadowed'] = True
                    _installed = None
            report['passed'] = True
        finally:
            report['seconds'] = time.monotonic() - started
            report['memory_after'] = device_memory()
            if _installed is not None and mode != 'restored':
                report['capture_summary'] = _installed[2].summary()
            write_json(run / ('vae-graph-' + run_name + '.json'), report)
        return (vae,)


NODE_CLASS_MAPPINGS = {'LTXVAEGraphGate': LTXVAEGraphGate}

"""Drop-in replacement for CLIPTextEncode that can memoise an unchanged prompt.

`original` is the native node. `cache` computes once per (clip, text) and serves
the stored conditioning afterwards. `verify` serves from the cache and also
recomputes natively, requiring the two to be bitwise equal, which is what makes
the cache an auditable claim rather than an assumption.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import time

import torch

import ltx_text_conditioning_cache as adapter
from encoder_diagnostics import _context

MODEL_SHA256 = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
_failed = False


def require(value, message):
    if not value:
        raise RuntimeError(message)


def write_json(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


class LTXCachedTextEncode:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'clip': ('CLIP',),
                             'text': ('STRING', {'multiline': True}),
                             'mode': (list(adapter.MODES),),
                             'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ('CONDITIONING',)
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, clip, text, mode, run_name):
        global _failed
        try:
            return self._apply(clip, text, mode, run_name)
        except BaseException:
            # Sticky: preserve the process and the evidence, never retry.
            _failed = True
            raise

    def _apply(self, clip, text, mode, run_name):
        require(not _failed, 'Previous text-cache failure; halt submissions and inspect evidence')
        require(mode in adapter.MODES, 'Only preregistered modes are admitted')
        require(isinstance(run_name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', run_name),
                'Unsafe request name')
        run, identity = _context()
        require(identity['model_verification_sha256'] == MODEL_SHA256 and
                identity['server_identity_sha256'] == os.environ.get('LTX_ENCODER_IDENTITY_SHA256'),
                'Model/startup identity changed')
        server = json.loads((run / 'server-identity.json').read_text())
        hashes = {}
        for path, name in ((Path(adapter.__file__), 'ltx_text_conditioning_cache.py'),
                           (Path(__file__), 'text_cache_node.py')):
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            require(server['extension_sha256s'][name] == actual, 'Sealed extension changed: ' + name)
            hashes[name] = actual
        require(torch.are_deterministic_algorithms_enabled() and
                not torch.is_deterministic_algorithms_warn_only_enabled(),
                'Strict determinism required')

        report = {'schema': 'ltx.text-cache-request.v1', **identity, 'run_name': run_name,
                  'extension_sha256s': hashes,
                  'claim': 'the conditioning is a pure function of (clip weights, prompt text); '
                           'this stores its value and does not approximate it. No precision, step '
                           'count, resolution, checkpoint, latent or frame is reused or changed.',
                  'passed': False}
        started = time.monotonic()
        try:
            conditioning, detail = adapter.encode(clip, text, mode)
            report.update(detail)
            report['passed'] = True
        finally:
            report['seconds'] = time.monotonic() - started
            write_json(run / ('text-cache-' + run_name + '.json'), report)
        return (conditioning,)


NODE_CLASS_MAPPINGS = {'LTXCachedTextEncode': LTXCachedTextEncode}

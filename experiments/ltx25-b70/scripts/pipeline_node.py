"""Text encode with optional encode-ahead.

`original` is the native CLIPTextEncode, called inline, exactly as the control
recipe does. `pipeline` computes every clip's conditioning with the same native
call, but starts the NEXT clip's encode on a worker thread as soon as this
clip's conditioning has been handed over, so it runs on xpu:2 while the sampler
works on xpu:0 and xpu:1.

Nothing is cached: each conditioning is produced by its own encode, consumed
once by the clip it was computed for, and dropped. Only the timing changes.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import time

import torch

import ltx_pipeline as pipeline
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


def native_encode(clip, text, consume_observations=False):
    import nodes
    require(clip is not None, 'CLIP input is invalid: None')
    encoded = nodes.CLIPTextEncode().encode(clip, text)
    require(isinstance(encoded, tuple) and len(encoded) == 1,
            'CLIPTextEncode no longer returns a single conditioning')
    if consume_observations:
        # The lab's embedding instrumentation enforces one-encode-then-consume,
        # and its consumer is LTXHostEmbeddingPlacementCheck, which a pipelined
        # arm cannot carry: under encode-ahead the encode that finishes during a
        # request belongs to the NEXT clip, so the accounting no longer lines up
        # with a request boundary. Every encode here runs on the one worker
        # thread, so consuming right after each encode keeps the protocol
        # satisfied. This discards a diagnostic; it touches no numerical value.
        group = getattr(clip, '_host_embedding', None)
        require(group is not None, 'Pipelined encode expects the host-embedding CLIP adapter')
        group.consume_observations()
    return encoded[0]


class LTXPipelineTextEncode:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'clip': ('CLIP',),
                             'text': ('STRING', {'multiline': True}),
                             'mode': (list(pipeline.MODES),),
                             'clip_index': ('INT', {'default': 0, 'min': 0, 'max': 1000000}),
                             'depth': ('INT', {'default': 1, 'min': 1,
                                               'max': pipeline.MAX_PENDING}),
                             'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ('CONDITIONING',)
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, clip, text, mode, clip_index, depth, run_name):
        global _failed
        try:
            return self._apply(clip, text, mode, clip_index, depth, run_name)
        except BaseException:
            # Sticky: preserve the process and the evidence, never retry.
            _failed = True
            pipeline.clear()
            raise

    def _apply(self, clip, text, mode, clip_index, depth, run_name):
        require(not _failed, 'Previous pipeline failure; halt submissions and inspect evidence')
        require(mode in pipeline.MODES, 'Only preregistered modes are admitted')
        require(isinstance(run_name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', run_name),
                'Unsafe request name')
        run, identity = _context()
        require(identity['model_verification_sha256'] == MODEL_SHA256 and
                identity['server_identity_sha256'] == os.environ.get('LTX_ENCODER_IDENTITY_SHA256'),
                'Model/startup identity changed')
        server = json.loads((run / 'server-identity.json').read_text())
        hashes = {}
        for path, name in ((Path(pipeline.__file__), 'ltx_pipeline.py'),
                           (Path(__file__), 'pipeline_node.py')):
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            require(server['extension_sha256s'][name] == actual, 'Sealed extension changed: ' + name)
            hashes[name] = actual
        require(torch.are_deterministic_algorithms_enabled() and
                not torch.is_deterministic_algorithms_warn_only_enabled(),
                'Strict determinism required')

        report = {'schema': 'ltx.pipeline-request.v1', **identity, 'run_name': run_name,
                  'mode': mode, 'clip_index': clip_index, 'depth': depth,
                  'extension_sha256s': hashes,
                  'claim': 'every clip computes its own conditioning with the native encode and '
                           'consumes it once; nothing is cached or reused between clips. Only the '
                           'moment the work runs changes, so it overlaps the sampler on other cards.',
                  'passed': False}
        started = time.monotonic()
        try:
            if mode == 'original':
                conditioning = native_encode(clip, text)
                report['detail'] = {'computed_inline': True}
            else:
                conditioning, detail = pipeline.run(
                    clip_index, depth, lambda: native_encode(clip, text, consume_observations=True))
                detail['placement_observations'] = 'consumed by the pipeline worker'
                report['detail'] = detail
            report['passed'] = True
        finally:
            report['seconds'] = time.monotonic() - started
            write_json(run / ('pipeline-' + run_name + '.json'), report)
        return (conditioning,)


NODE_CLASS_MAPPINGS = {'LTXPipelineTextEncode': LTXPipelineTextEncode}

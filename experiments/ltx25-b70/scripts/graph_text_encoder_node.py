"""Bounded XPU graph-capture gate for the Gemma4-12B text encoder stack.

`original` leaves the encoder untouched; `graph` shadows each of the 48 Gemma
layers with a graph-backed stand-in; `restored` puts the class methods back. The
encoder modules, their registration and their weights are never modified.

Text encoding is the largest node in the clip (1.81 s of 4.75 s) and runs 37x
above its weight-read roofline, so it is the largest issue-overhead target left.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import time

import torch

import ltx_graph_text_encoder as adapter
import ltx_pipeline
import ltx_text_shard
from encoder_diagnostics import _context

MODEL_SHA256 = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
MODES = ('original', 'graph', 'graph-shard', 'restored')
SHARD = ('xpu:2', 'xpu:3', 24)      # primary, secondary, split index
_installed = None      # (clip, originals, report)
_original_clip = None
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


class LTXTextEncoderGraphGate:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'clip': ('CLIP',), 'mode': (list(MODES),),
                             'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ('CLIP',)
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, clip, mode, run_name):
        global _failed
        try:
            return self._apply(clip, mode, run_name)
        except BaseException:
            # Sticky: preserve the process and evidence, never retry or reset.
            _failed = True
            raise

    def _apply(self, clip, mode, run_name):
        global _installed, _original_clip
        require(not _failed, 'Previous text encoder graph failure; halt submissions and inspect evidence')
        require(mode in MODES, 'Only preregistered modes are admitted')
        require(isinstance(run_name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', run_name),
                'Unsafe request name')
        run, identity = _context()
        require(identity['model_verification_sha256'] == MODEL_SHA256 and
                identity['server_identity_sha256'] == os.environ.get('LTX_ENCODER_IDENTITY_SHA256'),
                'Model/startup identity changed')
        server = json.loads((run / 'server-identity.json').read_text())
        hashes = {}
        for path, name in ((Path(adapter.__file__), 'ltx_graph_text_encoder.py'),
                           (Path(__file__), 'graph_text_encoder_node.py')):
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            require(server['extension_sha256s'][name] == actual, 'Sealed extension changed: ' + name)
            hashes[name] = actual
        require(torch.are_deterministic_algorithms_enabled() and
                not torch.is_deterministic_algorithms_warn_only_enabled(), 'Strict determinism required')
        require(_original_clip is None or clip is _original_clip, 'Resident CLIP generation changed')
        _original_clip = clip
        stack, layers = adapter.stack_of(clip)

        report = {'schema': 'ltx.text-encoder-graph-request.v1', **identity, 'run_name': run_name,
                  'mode': mode, 'extension_sha256s': hashes,
                  'stack_class': type(stack).__name__, 'layers': len(layers),
                  'encoder_device': str(next(stack.parameters()).device),
                  'gemma_source_sha256': adapter.GEMMA_SOURCE_SHA256,
                  'capture_proof': 'each captured graph must replay bit-identically to a fresh eager call '
                                   'of the same Gemma layer on the same inputs, and must be proven '
                                   'non-inert by perturbing its static input',
                  'not_captured': 'tokenisation, the embedding lookup, the final norm and the projection '
                                  'stay eager; only the 48 transformer layers are captured',
                  'memory_before': device_memory(), 'passed': False}
        started = time.monotonic()
        try:
            if mode == 'original':
                if _installed is not None:
                    resident, originals, captures = _installed
                    require(resident is clip, 'A different CLIP is shadowed')
                    require(not getattr(adapter.stack_of(clip)[0], '_ltx_text_shard_applied', False),
                            'The encoder is sharded across two cards for this server; only graph-shard arms may follow')
                    adapter.restore(clip, originals)
                    report['restored_from'] = 'graph'
                    _installed = None
            elif mode in ('graph', 'graph-shard'):
                if _installed is not None and mode == 'graph':
                    require(not getattr(adapter.stack_of(clip)[0], '_ltx_text_shard_applied', False),
                            'The encoder is sharded across two cards for this server; only graph-shard arms may follow')
                if _installed is None:
                    shard = None
                    if mode == 'graph-shard':
                        # Split the encoder across two cards before its first placement,
                        # load the shard now, and let two encode workers run.
                        stack, layers = adapter.stack_of(clip)
                        shard_patcher = ltx_text_shard.install(
                            clip, stack, layers, torch.device(SHARD[0]), torch.device(SHARD[1]), SHARD[2])
                        import comfy.model_management
                        comfy.model_management.load_models_gpu([shard_patcher], force_full_load=True)
                        ltx_pipeline.STAGE_WORKERS['encode'] = 2
                        shard = SHARD
                        report['text_shard'] = stack._ltx_text_shard_identity
                    captures, originals = adapter.install(clip, shard=shard)
                    _installed = (clip, originals, captures)
                    report['installed_now'] = True
                else:
                    resident, originals, captures = _installed
                    require(resident is clip, 'A different CLIP is already shadowed')
                    report['installed_now'] = False
            else:
                # 'restored' means "ensure the original state". An arm that never
                # shadowed the encoder is already in that state, so this is a
                # no-op rather than an error; the receipt records which it was.
                if _installed is None:
                    adapter.stack_of(clip)
                    report['was_shadowed'] = False
                else:
                    resident, originals, captures = _installed
                    require(resident is clip, 'Restore target is not the shadowed CLIP')
                    # Time the real captured layers before letting them go: XPU
                    # graph events cannot be profiled, so replaying each graph is
                    # the only ground truth for what the 48 layers cost.
                    report['graph_timing'] = adapter.measure(clip)
                    adapter.restore(clip, originals)
                    report['capture_summary_at_restore'] = captures.summary()
                    report['was_shadowed'] = True
                    _installed = None
            report['passed'] = True
        finally:
            report['seconds'] = time.monotonic() - started
            report['memory_after'] = device_memory()
            if _installed is not None and mode != 'restored':
                report['capture_summary'] = _installed[2].summary()
            write_json(run / ('text-encoder-graph-' + run_name + '.json'), report)
        return (clip,)


NODE_CLASS_MAPPINGS = {'LTXTextEncoderGraphGate': LTXTextEncoderGraphGate}

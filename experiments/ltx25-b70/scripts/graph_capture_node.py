"""Bounded XPU graph-capture gate for the native layer-sharded LTXAV transformer.

Modes: `original` leaves the installed native routes untouched and only records
a census; `graph` installs per-block graph-backed callables; `restored` puts the
original routes back. No plugin loading, module-forward change, parameter copy,
failure reset, server action or automatic retry path.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import time

import torch

import ltx_graph_capture as adapter
from encoder_diagnostics import _context

MODEL_SHA256 = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
SELECTIONS = {'all48': tuple(range(48)), 'single24': (24,), 'boundary4': (0, 20, 21, 47)}
MODES = ('original', 'graph', 'restored')
_installed = None      # (patcher, originals, report, selection)
_original_model = None
_failed = False


def require(value, message):
    if not value:
        raise RuntimeError(message)


def write_json(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def device_memory():
    rows = {}
    for index in range(torch.xpu.device_count()):
        rows[f'xpu:{index}'] = {
            'allocated_bytes': int(torch.xpu.memory_allocated(index)),
            'reserved_bytes': int(torch.xpu.memory_reserved(index))}
    return rows


class LTXGraphCaptureGate:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'model': ('MODEL',), 'mode': (list(MODES),),
                             'selection': (list(SELECTIONS),),
                             'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ('MODEL',)
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, model, mode, selection, run_name):
        global _failed
        try:
            return self._apply(model, mode, selection, run_name)
        except BaseException:
            # Sticky: preserve the process and evidence, never retry or reset.
            _failed = True
            raise

    def _apply(self, model, mode, selection, run_name):
        global _installed, _original_model
        require(not _failed, 'Previous graph-capture failure; halt submissions and inspect evidence')
        require(mode in MODES and selection in SELECTIONS, 'Only preregistered modes/selections are admitted')
        require(isinstance(run_name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', run_name),
                'Unsafe request name')
        run, identity = _context()
        require(identity['model_verification_sha256'] == MODEL_SHA256 and
                identity['server_identity_sha256'] == os.environ.get('LTX_ENCODER_IDENTITY_SHA256'),
                'Model/startup identity changed')
        server = json.loads((run / 'server-identity.json').read_text())
        hashes = {}
        for path, name in ((Path(adapter.__file__), 'ltx_graph_capture.py'),
                           (Path(__file__), 'graph_capture_node.py')):
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            require(server['extension_sha256s'][name] == actual, 'Sealed extension changed: ' + name)
            hashes[name] = actual
        require(torch.are_deterministic_algorithms_enabled() and
                not torch.is_deterministic_algorithms_warn_only_enabled(), 'Strict determinism required')
        require(_original_model is None or model is _original_model,
                'Original resident model generation changed')
        _original_model = model
        adapter.validate_patcher(model)
        require(model.ltx_layer_shard_report['split_index'] == 21, 'Expected the native 21/27 split')

        report = {'schema': 'ltx.graph-capture-request.v1', **identity, 'run_name': run_name,
                  'mode': mode, 'selection': selection, 'extension_sha256s': hashes,
                  'shard': dict(model.ltx_layer_shard_report),
                  'warmup_iterations': adapter.WARMUP_ITERATIONS,
                  'capture_proof': 'each captured graph must replay bit-identically to a fresh eager '
                                   'execution of the same block on the same inputs, and must be proven '
                                   'non-inert by perturbing its static input',
                  'memory_before': device_memory(), 'passed': False}
        started = time.monotonic()
        try:
            if mode == 'original':
                require(_installed is None, 'Graph routes are installed; run the restored mode first')
                report['installed_blocks'] = []
            elif mode == 'graph':
                if _installed is None:
                    indices = SELECTIONS[selection]
                    census, originals = adapter.install(model, indices)
                    _installed = (model, originals, census, selection)
                    report['installed_now'] = True
                else:
                    patcher, originals, census, previous = _installed
                    require(patcher is model and previous == selection,
                            'A different graph selection is already installed')
                    report['installed_now'] = False
                report['installed_blocks'] = sorted(_installed[1])
            else:
                require(_installed is not None, 'No graph routes are installed to restore')
                patcher, originals, census, previous = _installed
                require(patcher is model, 'Restore target is not the installed model')
                adapter.restore(model, originals)
                report['restored_blocks'] = sorted(originals)
                report['capture_summary_at_restore'] = census.summary()
                _installed = None
                report['installed_blocks'] = []
            report['passed'] = True
        finally:
            report['seconds'] = time.monotonic() - started
            report['memory_after'] = device_memory()
            if _installed is not None and mode != 'restored':
                report['capture_summary'] = _installed[2].summary()
            write_json(run / ('graph-capture-' + run_name + '.json'), report)
        return (model,)


NODE_CLASS_MAPPINGS = {'LTXGraphCaptureGate': LTXGraphCaptureGate}

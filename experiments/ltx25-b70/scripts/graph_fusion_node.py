"""Bounded gate for fusing shared-input projections in the native LTXAV blocks.

`original` leaves the projections alone; `fused` stacks the four qualifying
groups per block into one GEMM each; `restored` puts the separate projections
back. Weight values are unchanged and the originals are retained, so restore is
exact. Each fused group proves itself bit-for-bit against the separate
projections, once per input shape, before any of its output is used.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import time

import torch

import ltx_qkv_fusion as adapter
from encoder_diagnostics import _context

MODEL_SHA256 = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
MODES = ('original', 'fused', 'restored')
_installed = None
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
    return {f'xpu:{i}': {'allocated_bytes': int(torch.xpu.memory_allocated(i)),
                         'reserved_bytes': int(torch.xpu.memory_reserved(i))}
            for i in range(torch.xpu.device_count())}


class LTXFusionGate:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'model': ('MODEL',), 'mode': (list(MODES),),
                             'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ('MODEL',)
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, model, mode, run_name):
        global _failed
        try:
            return self._apply(model, mode, run_name)
        except BaseException:
            _failed = True
            raise

    def _apply(self, model, mode, run_name):
        global _installed, _original_model
        require(not _failed, 'Previous fusion failure; halt submissions and inspect evidence')
        require(mode in MODES, 'Only preregistered modes are admitted')
        require(isinstance(run_name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', run_name),
                'Unsafe request name')
        run, identity = _context()
        require(identity['model_verification_sha256'] == MODEL_SHA256 and
                identity['server_identity_sha256'] == os.environ.get('LTX_ENCODER_IDENTITY_SHA256'),
                'Model/startup identity changed')
        server = json.loads((run / 'server-identity.json').read_text())
        hashes = {}
        for path, name in ((Path(adapter.__file__), 'ltx_qkv_fusion.py'),
                           (Path(__file__), 'graph_fusion_node.py')):
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            require(server['extension_sha256s'][name] == actual, 'Sealed extension changed: ' + name)
            hashes[name] = actual
        require(torch.are_deterministic_algorithms_enabled() and
                not torch.is_deterministic_algorithms_warn_only_enabled(), 'Strict determinism required')
        require(_original_model is None or model is _original_model, 'Resident model generation changed')
        _original_model = model

        report = {'schema': 'ltx.fusion-request.v1', **identity, 'run_name': run_name, 'mode': mode,
                  'extension_sha256s': hashes, 'groups': [list(g[:2]) for g in adapter.GROUPS],
                  'proof': 'each fused group is compared bit-for-bit against the separate projections, '
                           'once per input shape, before any of its output is used',
                  'gate_excluded': 'the [heads, K] gate projection is not stacked: including it breaks '
                                   'exactness even where the same stack without it is exact',
                  'memory_before': device_memory(), 'passed': False}
        started = time.monotonic()
        try:
            if mode == 'original':
                require(_installed is None, 'Projections are fused; run the restored mode first')
            elif mode == 'fused':
                if _installed is None:
                    groups, added = adapter.install(model)
                    _installed = (model, groups, added)
                    report['installed_now'] = True
                else:
                    resident, groups, added = _installed
                    require(resident is model, 'A different model is already fused')
                    report['installed_now'] = False
                report['fusion_summary'] = adapter.summary(_installed[1], _installed[2])
            else:
                if _installed is None:
                    report['was_fused'] = False
                else:
                    resident, groups, added = _installed
                    require(resident is model, 'Restore target is not the fused model')
                    report['fusion_summary_at_restore'] = adapter.summary(groups, added)
                    adapter.restore(groups)
                    report['was_fused'] = True
                    _installed = None
            report['passed'] = True
        finally:
            report['seconds'] = time.monotonic() - started
            report['memory_after'] = device_memory()
            write_json(run / ('fusion-' + run_name + '.json'), report)
        return (model,)


NODE_CLASS_MAPPINGS = {'LTXFusionGate': LTXFusionGate}

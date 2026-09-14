"""Metadata-only encoder placement gates for an inactive LTX experiment node.

No tensor contents are read, copied, reduced, hashed, or allocated. Device/dtype
inspection is not a GPU health probe. Production expectations are not graph inputs.
"""
from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re

ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
VARIANTS = ('control', 'crop', 'small_state', 'combined')


@dataclass(frozen=True)
class SmallStateExpectation:
    rmsnorm_count: int = 289
    scalar_count: int = 48
    total_bytes: int = 1539680
    device: str = 'xpu:2'
    dtype: str = 'torch.bfloat16'


PRODUCTION_EXPECTATION = SmallStateExpectation()


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', value):
        raise ValueError('run_name must contain only lowercase letters, digits and hyphens')
    return value


def _context(root=ROOT):
    root = Path(root)
    if (root / 'FAULT.json').exists():
        raise RuntimeError('Fault recorded; encoder diagnostics halted')
    value = os.environ.get('LTX_ENCODER_RUN_DIR', '')
    run = Path(value)
    if (not value or not run.is_absolute() or run.resolve().parent != root.resolve()
            or not run.name.startswith('encoder-server-') or run.is_symlink() or not run.is_dir()):
        raise ValueError('A dedicated existing absolute encoder-server-* run directory is required')
    gate_bytes = (root / 'model-verification.json').read_bytes()
    if json.loads(gate_bytes).get('status') != 'passed':
        raise RuntimeError('Model verification has not passed')
    identity_bytes = (run / 'server-identity.json').read_bytes()
    json.loads(identity_bytes)
    return run, {'model_verification_sha256': hashlib.sha256(gate_bytes).hexdigest(),
                 'server_identity_sha256': hashlib.sha256(identity_bytes).hexdigest()}


def _exclusive_json(path, report, root):
    if (Path(root) / 'FAULT.json').exists():
        raise RuntimeError('Fault recorded; encoder diagnostics halted')
    # O_EXCL also rejects symlinks, including dangling ones.
    with Path(path).open('x') as stream:
        json.dump(report, stream, separators=(',', ':'), sort_keys=True)
        stream.write('\n')


def _tensor_metadata(name, value, kind, owner):
    return {'name': name, 'kind': kind, 'device': str(value.device),
            'dtype': str(value.dtype), 'shape': list(value.shape),
            'bytes': int(value.numel() * value.element_size()), 'owner_id': id(owner)}


def _summary(records):
    totals = defaultdict(lambda: {'tensors': 0, 'bytes': 0})
    for row in records:
        group = totals[row['device'] + '/' + row['dtype']]
        group['tensors'] += 1
        group['bytes'] += row['bytes']
    return {'count': len(records), 'bytes': sum(row['bytes'] for row in records),
            'by_device_dtype': dict(sorted(totals.items())), 'records': records}


def inspect_encoder(clip):
    """Inspect registered owners, not a reconstructed or cached state dictionary."""
    patcher = clip.patcher
    model = patcher.model
    if clip.cond_stage_model is not model:
        raise RuntimeError('CLIP component and ModelPatcher do not own the same encoder')
    parameters, buffers, small = [], [], []
    marked_bytes = 0
    marked_modules = []
    for prefix, owner in model.named_modules():
        kind = type(owner)
        rmsnorm = kind.__module__ == 'comfy.text_encoders.llama' and kind.__name__ == 'RMSNorm'
        scalar_owner = kind.__module__ == 'comfy.text_encoders.gemma4' and kind.__name__ == 'TransformerBlockGemma4'
        direct_bytes = 0
        for name, value in owner._parameters.items():
            if value is None:
                continue
            key = f'{prefix}.{name}' if prefix else name
            row = _tensor_metadata(key, value, 'parameter', owner)
            parameters.append(row)
            direct_bytes += row['bytes']
            if rmsnorm and name == 'weight':
                small.append({**row, 'kind': 'rmsnorm'})
        for name, value in owner._buffers.items():
            if value is None:
                continue
            key = f'{prefix}.{name}' if prefix else name
            row = _tensor_metadata(key, value, 'buffer', owner)
            row['persistent'] = name not in owner._non_persistent_buffers_set
            buffers.append(row)
            if row['persistent']:
                direct_bytes += row['bytes']
            if scalar_owner and name == 'layer_scalar':
                small.append({**row, 'kind': 'scalar'})
        if getattr(owner, 'comfy_patched_weights', False):
            marked_modules.append(prefix)
            marked_bytes += direct_bytes
    return {
        'small_state': {'rmsnorm_count': sum(r['kind'] == 'rmsnorm' for r in small),
                        'scalar_count': sum(r['kind'] == 'scalar' for r in small),
                        'total_bytes': sum(r['bytes'] for r in small), 'records': small},
        'parameters': _summary(parameters), 'buffers': _summary(buffers),
        'accounting': {
            'reported_loaded_weight_bytes': int(model.model_loaded_weight_memory),
            'reported_offload_buffer_bytes': int(model.model_offload_buffer_memory),
            'reported_model_size_bytes': int(patcher.size),
            'registered_parameter_bytes_on_load_device': sum(row['bytes'] for row in parameters if row['device'] == str(patcher.load_device)),
            'registered_persistent_buffer_bytes_on_load_device': sum(row['bytes'] for row in buffers if row['persistent'] and row['device'] == str(patcher.load_device)),
            'marked_direct_state_bytes': marked_bytes,
            'marked_modules': marked_modules,
            'small_buffers_loaded': bool(getattr(model, '_ltx_small_buffers_loaded', False)),
            'model_small_state_policy': bool(getattr(model, '_ltx_small_state_policy', False)),
            'patcher_small_state_option': bool(patcher.model_options.get('ltx_small_state_residency', False)),
            'crop_option': bool(getattr(model, 'ltx_crop_before_cpu', False)),
            'load_device': str(patcher.load_device), 'offload_device': str(patcher.offload_device),
            'is_dynamic': bool(patcher.is_dynamic()),
        },
    }


def placement_report(clip, run_name, encoder_variant, expectation=PRODUCTION_EXPECTATION):
    _identifier(run_name)
    if encoder_variant not in VARIANTS:
        raise ValueError('Unknown encoder variant')
    inspection = inspect_encoder(clip)
    small, accounting = inspection['small_state'], inspection['accounting']
    resident = encoder_variant in ('small_state', 'combined')
    failures = []
    if accounting['patcher_small_state_option'] != resident:
        failures.append('small_state_option_mismatch')
    if accounting['crop_option'] != (encoder_variant in ('crop', 'combined')):
        failures.append('crop_option_mismatch')
    if resident:
        if accounting['is_dynamic']:
            failures.append('dynamic_patcher_unsupported')
        if accounting['load_device'] != expectation.device or accounting['offload_device'] != 'cpu':
            failures.append('encoder_device_configuration_mismatch')
        if (small['rmsnorm_count'], small['scalar_count'], small['total_bytes']) != (
                expectation.rmsnorm_count, expectation.scalar_count, expectation.total_bytes):
            failures.append('small_state_inventory_mismatch')
        if any(row['device'] != expectation.device or row['dtype'] != expectation.dtype
               for row in small['records']):
            failures.append('small_state_placement_mismatch')
        if not accounting['small_buffers_loaded'] or not accounting['model_small_state_policy']:
            failures.append('small_state_accounting_marker_missing')
        if accounting['reported_loaded_weight_bytes'] < expectation.total_bytes:
            failures.append('small_state_missing_from_loaded_byte_count')
    return {'schema': 'ltx.encoder-placement.v1', 'stage': 'post_encode',
            'run_name': run_name, 'encoder_variant': encoder_variant,
            'passed': not failures, 'failures': failures,
            'resident_gate_required': resident,
            'expected_small_state': expectation.__dict__, 'inspection': inspection}


class LTXEncoderPlacementCheck:
    def __init__(self, *, expectation=PRODUCTION_EXPECTATION, evidence_root=ROOT):
        # Fixture injection exists only in Python tests, never in graph inputs.
        self.expectation = expectation
        self.evidence_root = Path(evidence_root)

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'clip': ('CLIP',), 'conditioning': ('CONDITIONING',),
                             'run_name': ('STRING', {'default': 'encoder-placement-01'}),
                             'encoder_variant': (list(VARIANTS),)}}

    RETURN_TYPES = ('CONDITIONING',)
    FUNCTION = 'check'
    CATEGORY = 'lab/validation'

    def check(self, clip, conditioning, run_name, encoder_variant):
        run, identity = _context(self.evidence_root)
        report = placement_report(clip, run_name, encoder_variant, self.expectation)
        report.update(identity)
        _exclusive_json(run / f'encoder-placement-{run_name}.json', report, self.evidence_root)
        if not report['passed']:
            raise RuntimeError('Encoder placement gate failed: ' + ', '.join(report['failures']))
        return (conditioning,)


def begin_encoder_unload(clip, old_generation, new_generation, old_variant, new_variant, *, root=ROOT):
    """Capture metadata while the old component still has its registered owners."""
    run, identity = _context(root)
    if not isinstance(old_generation, int) or old_generation < 1 or new_generation != old_generation + 1:
        raise ValueError('Invalid component generation transition')
    if old_variant not in VARIANTS or new_variant not in VARIANTS:
        raise ValueError('Unknown encoder variant')
    path = run / f'encoder-unload-{old_generation:02d}-to-{new_generation:02d}.json'
    if path.exists() or path.is_symlink():
        raise FileExistsError(f'Refuse existing encoder unload receipt: {path}')
    return {'schema': 'ltx.encoder-unload.v1', 'old_generation': old_generation,
            'new_generation': new_generation, 'old_variant': old_variant,
            'new_variant': new_variant, **identity, 'before': inspect_encoder(clip)}


def finish_encoder_unload(clip, report, *, root=ROOT):
    """Require actual encoder owners offloaded before replacement construction."""
    run, identity = _context(root)
    if any(report.get(k) != v for k, v in identity.items()):
        raise RuntimeError('Encoder unload identity changed')
    after = inspect_encoder(clip)
    failures = []
    expected_device = after['accounting']['offload_device']
    if expected_device != 'cpu':
        failures.append('encoder_offload_device_must_be_cpu')
    for group in ('parameters', 'buffers'):
        before_rows = report['before'][group]['records']
        after_rows = after[group]['records']
        def ownership(rows):
            return {(r['name'], r['dtype'], tuple(r['shape']), r['bytes'], r['owner_id']) for r in rows}
        if ownership(before_rows) != ownership(after_rows):
            failures.append(group + '_ownership_changed')
        if any(row['device'] != expected_device for row in after_rows):
            failures.append(group + '_still_on_other_device')
    accounting = after['accounting']
    if (accounting['reported_loaded_weight_bytes'] != 0 or accounting['reported_offload_buffer_bytes'] != 0
            or accounting['marked_modules'] or accounting['small_buffers_loaded'] or accounting['model_small_state_policy']):
        failures.append('unload_accounting_not_cleared')
    completed = {**report, 'after': after, 'passed': not failures, 'failures': failures}
    path = run / f"encoder-unload-{report['old_generation']:02d}-to-{report['new_generation']:02d}.json"
    _exclusive_json(path, completed, root)
    if failures:
        raise RuntimeError('Encoder unload gate failed: ' + ', '.join(failures))
    return completed


NODE_CLASS_MAPPINGS = {'LTXEncoderPlacementCheck': LTXEncoderPlacementCheck}

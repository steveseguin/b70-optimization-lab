#!/usr/bin/env python3
"""Eager-only read-only observer. Does not construct or launch a native model.

The in-process API works with torch forward hooks or an existing callable.
A driver owns the comparator, fresh request, token collection and graceful
shutdown; this module never changes its arithmetic or substitutes a reference.
See WINDOW-RUNBOOK.md for the unresolved certified-container identity.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
from functools import wraps

import jsonschema
import torch

from common import HERE, LANE, NAMES, digest, file_hash, json_bytes, token_hash

BASE_SCHEMA = LANE / 'stage1/packet1b/tests/fixture-extraction.schema.json'
MODELS = {
    '27b': ('Qwen/Qwen3.8-27B-FP8', '017b9c7af6b5689d5dd426a76e0bc077eb5ca20a', 'stage1'),
    'flash-next': ('Qwen/Qwen3.8-Flash-Next-FP8', 'bcd9f01ddc9cff2316eb84281bebcd5b058bddce', 'stage2'),
}


def normalize_oracle(oracle):
    """Stage 1 and Stage 2 retain different token-hash field spellings."""
    oracle = copy.deepcopy(oracle)
    for row in oracle['rows']:
        if 'sha256' not in row:
            row['sha256'] = row['token_ids_sha256']
    return oracle


def schema():
    """Versioned extension, preserving v1; one prompt is NEVER qualified.

    v1 mandates twelve measured output hashes and completed repeat artifacts.
    v2 retains those fields but distinguishes oracle pins from measurements,
    adds row/rank/call metadata and Flash families, and forbids qualification.
    """
    s = json.loads(BASE_SCHEMA.read_text())
    s['$id'] = 'urn:own-xpu-runtime:packet4:operator-fixture:v2'
    s['title'] = 'Diagnostic eager extraction; not a full native census'
    p = s['properties']
    p['schema']['const'] = 'own-xpu-runtime.packet4.operator-fixture.v2'
    p['status']['enum'] = ['extracted-unverified', 'rejected']
    p['inputs']['minItems'] = 0  # PLE integer-history arguments live in call JSON.
    p['model']['properties']['repository'] = {'enum': [x[0] for x in MODELS.values()]}
    p['model']['properties']['revision'] = {'enum': [x[1] for x in MODELS.values()]}
    # A367 is a host venv. null is honest; no invented digest is allowed.
    p['comparator']['properties']['image_digest'] = {'anyOf': [p['comparator']['properties']['image_digest'], {'type': 'null'}]}
    p['operator']['properties']['name']['enum'] += ['linear', 'silu', 'qsa', 'qsa_pool', 'qsa_select', 'router', 'moe', 'hc_mix', 'hc_combine', 'ple_ids', 'ple_lookup', 'ple_injection']
    p['extraction']['properties']['full_output_token_hashes']['minItems'] = 0
    p['extraction']['properties']['full_suite_token_oracle_equal']['const'] = False
    p['diagnostic'] = {'type': 'object', 'required': ['model_key', 'mock', 'rows', 'rank', 'reference_call', 'expected', 'source_layouts', 'run_identity', 'oracle_hashes', 'reference_sha256', 'schema_base_sha256'],
        'properties': {'model_key': {'enum': list(MODELS)}, 'mock': {'type': 'boolean'},
                       'rows': {'type': 'array', 'items': {'type': 'integer', 'minimum': 0}},
                       'rank': {'type': 'integer', 'minimum': 0},
                       'reference_call': {'type': ['object', 'null']}, 'expected': {'type': 'object'},
                       'source_layouts': {'type': 'object'}, 'run_identity': {'type': 'object'},
                       'oracle_hashes': {'type': 'array', 'minItems': 12, 'maxItems': 12, 'items': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'}},
                       'reference_sha256': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'},
                       'schema_base_sha256': {'const': file_hash(BASE_SCHEMA)}}, 'additionalProperties': False}
    s['required'].append('diagnostic')
    return s


def refuse_capture(config):
    """Only inspect CPU configuration: never probe any device from this guard."""
    if config.get('enforce_eager') is not True or config.get('graph_mode') != 'NONE' or config.get('compile_mode') != 'NONE':
        raise ValueError('eager only: graph capture and compilation must be disabled')
    if config.get('prefix_caching') is not False:
        raise ValueError('prompt cache must be disabled')
    for key in ('VLLM_XPU_ENABLE_XPU_GRAPH', 'VLLM_USE_CUDA_GRAPH'):
        if os.environ.get(key, '0').lower() not in ('0', 'false', ''):
            raise ValueError('graph capture enabled by ' + key)
    if torch.compiler.is_compiling():
        raise ValueError('compiled region: no fixture host reads allowed')


def validate_native_identity(identity):
    """Fail before importing comparator code. A claimed image is not a receipt."""
    if identity.get('mock') is True:
        return
    required = ('comparator', 'model', 'authorization', 'health', 'host', 'boot_id',
                'kernel', 'firmware', 'pci_ids', 'payload', 'suite', 'prompt',
                'kv_dtype', 'state_dtype', 'sampler', 'mtp', 'environment', 'flags',
                'binding_manifest', 'certified_environment_receipt', 'execution')
    missing = [key for key in required if key not in identity]
    if missing:
        raise ValueError('native identity missing: ' + ', '.join(missing))
    if identity['kv_dtype'] not in ('F16', 'BF16'):
        raise ValueError('16-bit KV required')
    for key in ('authorization', 'health', 'payload', 'suite', 'prompt',
                'binding_manifest', 'certified_environment_receipt'):
        item = identity[key]
        if file_hash(item['path']) != item['sha256']:
            raise ValueError('identity artifact changed: ' + key)
    receipt = json.loads(Path(identity['certified_environment_receipt']['path']).read_text())
    if receipt.get('passed') is not True or receipt.get('comparator') != identity['comparator']:
        raise ValueError('no matched certified comparator environment receipt')
    if identity['model'] not in MODELS:
        raise ValueError('unknown native model identity')
    if identity['state_dtype'] != ('F32' if identity['model']=='27b' else 'BF16'):
        raise ValueError('model-specific recurrent state precision mismatch')


@contextmanager
def forbid_graph_entrypoints(targets):
    """Install before native engine construction, remove only after teardown.

    The adapter supplies source-verified (owner, attribute) graph/capture entry
    points for its pinned runtime and torch. Merely setting flags is insufficient
    when a runtime ignores them. No device enumeration or query happens here.
    The CPU tests pass dummy entrypoints; real XPU APIs are never imported there.
    """
    restored = []
    def forbidden(*args, **kwargs):
        raise RuntimeError('graph capture refused by packet4 eager-only extraction')
    try:
        for owner, name in targets:
            old = getattr(owner, name)
            if not callable(old):
                raise ValueError('graph entrypoint is not callable')
            setattr(owner, name, forbidden)
            restored.append((owner, name, old))
        yield
    finally:
        for owner, name, old in reversed(restored):
            setattr(owner, name, old)


class Recorder:
    """One synchronous writer per rank. No background queue or retained tensors.

    The cap includes blobs and metadata. Pre/post copies serialize an eager
    computation and are diagnostic overhead, never speed evidence. Tensor
    copies use logical contiguous chunks <= chunk_bytes, including strided
    tensors; no whole GPU tensor is cloned or moved to the host.
    """
    def __init__(self, root, model, identity, config, oracle, prompt_id,
                 max_bytes=512 * 1024**2, chunk_bytes=1024**2):
        refuse_capture(config)
        validate_native_identity(identity)
        if model not in MODELS or max_bytes <= 0 or not 8 <= chunk_bytes <= 16 * 1024**2:
            raise ValueError('model/cap/chunk bound')
        oracle = normalize_oracle(oracle)
        if not identity.get('mock'):
            if identity['model'] != model:
                raise ValueError('native identity/selected model mismatch')
            frozen = normalize_oracle(json.loads((LANE / MODELS[model][2] / 'packet1/oracle-token-ids.json').read_text()))
            if oracle != frozen:
                raise ValueError('native oracle must be the complete frozen packet1 oracle')
        rows = oracle['rows']
        if len(rows) != 12 or len({r['prompt_id'] for r in rows}) != 12:
            raise ValueError('complete 12-row oracle required')
        for r in rows:
            if not isinstance(r['token_ids'], list) or any(type(t) is not int or t < 0 for t in r['token_ids']) or r['sha256'] != token_hash(r['token_ids']):
                raise ValueError('oracle token array/hash mismatch')
        self.oracle = next(r for r in rows if r['prompt_id'] == prompt_id)
        self.oracle_hashes = [r['sha256'] for r in rows]
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=False)
        self.model, self.identity, self.config = model, copy.deepcopy(identity), config
        self.max_bytes, self.chunk_bytes, self.used = max_bytes, chunk_bytes, 0
        self.sequence, self.tensor_sequence = 0, 0
        self.seen, self.files, self.failure = set(), [], None
        self._pending = {}
        self._write_json('oracle.json', oracle)
        self._write_json('schema.json', schema())
        pending = self._write_json('pending.json', {'status': 'UNTESTED', 'reason': 'single-prompt diagnostic; no full suite or repeat certification'})
        comparator = self.identity['comparator']
        if self.identity.get('mock'):
            for key in ('build_manifest', 'overlay_manifest'):
                comparator[key] = pending
            comparator['kernel_binaries'] = [pending]
        else:
            for key in ('authorization', 'health', 'payload', 'suite', 'prompt',
                        'binding_manifest', 'certified_environment_receipt'):
                self.identity[key] = self.import_artifact(key, self.identity[key])
            for key in ('build_manifest', 'overlay_manifest'):
                comparator[key] = self.import_artifact(key, comparator[key])
            comparator['kernel_binaries'] = [self.import_artifact(f'kernel-{i}', v) for i,v in enumerate(comparator['kernel_binaries'])]
        self._write_json('run-identity.json', self.identity)
        self.code = self._write('extractor.py.txt', Path(__file__).read_bytes())

    def _reserve(self, n):
        if n < 0 or self.used + n > self.max_bytes:
            raise ValueError(f'fixture byte cap exceeded: {self.used}+{n}>{self.max_bytes}')
        self.used += n

    def _write(self, name, data):
        self._reserve(len(data))
        with (self.root / name).open('xb') as f:
            f.write(data)
        return {'path': name, 'sha256': digest(data)}

    def _write_json(self, name, value):
        return self._write(name, json_bytes(value))

    def _artifact(self, name):
        return {'path': name, 'sha256': file_hash(self.root / name)}

    def import_artifact(self, name, item):
        """Bounded copy of native provenance; artifact paths become portable."""
        source = Path(item['path'])
        self._reserve(source.stat().st_size)
        target = self.root / (name + '.artifact')
        with source.open('rb') as inp, target.open('xb') as out:
            for chunk in iter(lambda: inp.read(self.chunk_bytes), b''):
                out.write(chunk)
        if file_hash(target) != item['sha256']:
            raise ValueError('native provenance hash mismatch: ' + name)
        return {'path': target.name, 'sha256': item['sha256']}

    def tensor(self, name, x):
        refuse_capture(self.config)
        if x.dtype not in NAMES or x.layout != torch.strided or sys.byteorder != 'little':
            raise ValueError('unsupported tensor dtype/layout/byte order')
        if not self.identity.get('mock') and x.device.type not in ('cpu', 'xpu'):
            raise ValueError('unexpected device')
        if self.identity.get('mock') and x.device.type != 'cpu':
            raise ValueError('mock accepts only CPU tensors')
        if x.ndim == 0:
            x = x.reshape(1)
        nbytes = x.numel() * x.element_size()
        self._reserve(nbytes)  # before any host transfer/allocation
        filename = f'tensor-{self.tensor_sequence:08d}.bin'
        self.tensor_sequence += 1
        h = __import__('hashlib').sha256()
        with (self.root / filename).open('xb') as f:
            def emit(view):
                if view.numel() == 0:
                    return
                if view.numel() * view.element_size() <= self.chunk_bytes:
                    # This is a blocking D2H read, permitted ONLY in eager mode.
                    raw = view.detach().to(device='cpu').contiguous().reshape(-1).view(torch.uint8).numpy().tobytes()
                    f.write(raw)
                    h.update(raw)
                    return
                # Split along the first non-unit dimension in logical order.
                dim = next(i for i, n in enumerate(view.shape) if n > 1)
                cut = max(1, min(view.shape[dim] // 2, self.chunk_bytes // max(1, math.prod(view.shape[dim+1:]) * view.element_size())))
                for start in range(0, view.shape[dim], cut):
                    emit(view.narrow(dim, start, min(cut, view.shape[dim]-start)))
            emit(x)
        stride, n = [], 1
        for size in reversed(x.shape):
            stride.insert(0, n)
            n *= max(1, size)
        return {'name': name, 'artifact': {'path': filename, 'sha256': h.hexdigest()},
                'dtype': NAMES[x.dtype], 'shape': list(x.shape), 'strides_elements': stride,
                'storage_offset_bytes': 0, 'byte_order': 'little', 'nbytes': nbytes}

    def tree(self, value, prefix, descriptors, layouts):
        if isinstance(value, torch.Tensor):
            descriptors.append(self.tensor(prefix, value))
            layouts[prefix] = {'shape': list(value.shape), 'strides_elements': list(value.stride()),
                               'storage_offset_bytes': value.storage_offset() * value.element_size()}
            return {'$tensor': prefix}
        if isinstance(value, torch.dtype):
            return {'$dtype': NAMES[value]}
        if isinstance(value, tuple):
            return {'$tuple': [self.tree(x, f'{prefix}.{i}', descriptors, layouts) for i, x in enumerate(value)]}
        if isinstance(value, list):
            return [self.tree(x, f'{prefix}.{i}', descriptors, layouts) for i, x in enumerate(value)]
        if isinstance(value, dict):
            return {str(k): self.tree(x, f'{prefix}.{k}', descriptors, layouts) for k, x in value.items()}
        if value is None or type(value) in (int, str, float, bool):
            return value
        raise ValueError('binding must normalize opaque native object: ' + type(value).__name__)

    def begin(self, spec, args, kwargs, state):
        refuse_capture(self.config)
        if spec['M'] not in (1, 2, 6) or spec['rows'] != list(range(spec['M'])):
            raise ValueError('M=1/2/6 and explicit row indices required; do not reshape native dispatch')
        if len(spec['positions']) != spec['M'] or len(spec['valid_rows']) != spec['M']:
            raise ValueError('row metadata length mismatch')
        key = (spec['location'], spec['layer'], spec['M'], spec.get('rank', 0))
        if key in self.seen:
            return None  # first occurrence per layer/shape/rank; no repeated prompt
        self.seen.add(key)
        idx = self.sequence
        self.sequence += 1
        inputs, before, layouts = [], [], {}
        call = {'function': spec['reference'],
                'args': self.tree(args, 'args', inputs, layouts),
                'kwargs': self.tree(kwargs, 'kwargs', inputs, layouts)} if spec.get('reference') else None
        if call is None:
            self.tree(args, 'args', inputs, layouts)
            self.tree(kwargs, 'kwargs', inputs, layouts)
        self.tree(state, 'state', before, layouts)
        value = (copy.deepcopy(spec), inputs, before, layouts, call)
        self._pending[idx] = value
        return idx

    def end(self, idx, observed, state):
        if idx is None:
            return
        refuse_capture(self.config)
        spec, inputs, before, layouts, call = self._pending.pop(idx)
        from common import flatten, load_ref
        outputs, after = [], []
        for name, value in observed.items():
            self.tree(value, name, outputs, layouts)
        self.tree(state, 'state', after, layouts)
        repo, revision, stage = MODELS[self.model]
        pending = self._artifact('pending.json')
        comparator = self.identity['comparator']
        # All portable evidence lives in this bundle. Native environment receipts
        # are additionally authenticated by validate_native_identity.
        fixture = {
            'schema': 'own-xpu-runtime.packet4.operator-fixture.v2', 'status': 'extracted-unverified',
            'fixture_id': f'{self.model}-rank{spec.get("rank", 0)}-{idx:06d}',
            'packet1_contract_sha256': file_hash(LANE / stage / 'packet1/tensor-contract.json'),
            'packet1b_receipt_sha256': file_hash(LANE / stage / ('packet1b/test-receipt-gate-correction.json' if self.model == '27b' else 'packet1b/test-receipt.json')),
            'model': {'repository': repo, 'revision': revision, 'payload_manifest': self.identity.get('payload', self._artifact('run-identity.json'))},
            'comparator': comparator, 'authorization_receipt': self.identity.get('authorization', self._artifact('run-identity.json')),
            'operator': {k: spec[k] for k in ('name', 'layer', 'M', 'N', 'K', 'positions', 'valid_rows', 'arithmetic_order', 'rounding_points', 'census_items')},
            'inputs': inputs, 'outputs': outputs, 'state_before': before, 'state_after': after,
            'extraction': {'code': self.code, 'hook_locations': [spec['location']],
                           'neutrality': pending, 'full_suite_token_oracle_equal': False,
                           'prompt_cache_disabled': True, 'full_output_token_hashes': []},
            'validation': {'same_process_repeat': pending, 'fresh_process_repeat': pending, 'cpu_comparison': pending,
                           'all_outputs_bit_identical': False, 'all_states_bit_identical': False,
                           'mismatch_policy': 'retain failure; no quality waiver or speed promotion'},
            'diagnostic': {'model_key': self.model, 'mock': self.identity.get('mock') is True,
                           'rows': spec['rows'], 'rank': spec.get('rank', 0), 'reference_call': call,
                           'expected': spec['expected'], 'source_layouts': layouts,
                           'run_identity': self._artifact('run-identity.json'), 'oracle_hashes': self.oracle_hashes,
                           'reference_sha256': file_hash(load_ref(self.model).__file__),
                           'schema_base_sha256': file_hash(BASE_SCHEMA)},
        }
        jsonschema.validate(fixture, schema())
        entry = self._write_json(f'fixture-{idx:06d}.json', fixture)
        self.files.append(entry)

    def finish(self, ids, cached_tokens=0):
        if self._pending:
            raise ValueError('incomplete hook invocation')
        if not self.files:
            raise ValueError('no operator fixtures recorded')
        matched = ids == self.oracle['token_ids'] and cached_tokens == 0
        result = {'schema': 'own-xpu-runtime.packet4.extraction-result.v1',
                  'status': 'extracted-unverified' if matched else 'rejected',
                  'mock': self.identity.get('mock') is True, 'prompt_id': self.oracle['prompt_id'],
                  'prompt_sha256': self.oracle['prompt_sha256'], 'token_ids': ids,
                  'oracle_token_sha256': self.oracle['sha256'], 'actual_token_sha256': token_hash(ids),
                  'single_prompt_oracle_equal': matched, 'cached_tokens': cached_tokens,
                  'full_suite_token_oracle_equal': False, 'fixtures': self.files,
                  'fixture_bytes_before_receipt': self.used, 'max_bytes': self.max_bytes,
                  'run_identity': self._artifact('run-identity.json')}
        self._write_json('extraction-result.json', result)
        if not matched:
            raise AssertionError('final token IDs differ from oracle or cached_tokens != 0; fixtures rejected')
        return result

    @contextmanager
    def hook(self, module, spec, inputs, outputs, states=lambda m: {}):
        """Adapters return views/metadata only; never tensor values from a device.

        inputs(module,args,kwargs) -> (reference_args,reference_kwargs).
        outputs(module,args,kwargs,result) -> named tensor dictionary.
        states(module) -> views of touched state, not the entire cache pool.
        spec may be a callable of (module,args,kwargs) for runtime M/positions.
        None spec means a non-admitted shape; no fictitious M is substituted.
        Both hooks return None, preserving original args/result object identity.
        """
        stack = []
        def pre(m, a, kw):
            refuse_capture(self.config)
            current = spec(m, a, kw) if callable(spec) else spec
            if current is None:
                stack.append(None)
                return
            ra, rk = inputs(m, a, kw)
            stack.append(self.begin(current, ra, rk, states(m)))
        def post(m, a, kw, result):
            if not stack:
                return
            idx = stack.pop()
            if idx is not None:
                if result is None:
                    raise ValueError('operator failed or has in-place output: use observe() with explicit output views')
                self.end(idx, outputs(m, a, kw, result), states(m))
        h1 = module.register_forward_pre_hook(pre, with_kwargs=True)
        h2 = module.register_forward_hook(post, with_kwargs=True, always_call=True)
        try:
            yield
        finally:
            h2.remove()
            h1.remove()

    def observe(self, function, args, kwargs, spec, reference_inputs, outputs, states):
        """Monkeypatch helper; calls the ORIGINAL exactly once, returns its result.

        Handles native ops returning None by recording caller-owned output
        buffers. Any native monkeypatch must be source/hash bound and restored
        in finally by its comparator adapter.
        """
        ra, rk = reference_inputs()
        idx = self.begin(spec, ra, rk, states())
        result = function(*args, **kwargs)
        self.end(idx, outputs(result), states())
        return result

    @contextmanager
    def monkeypatch(self, owner, name, spec, inputs, outputs, states):
        """Restore an in-place/functional native operator even when it raises.

        spec(args,kwargs), inputs(args,kwargs), outputs(args,kwargs,result),
        states(args,kwargs) are reviewed read-only layout adapters. Imported
        aliases must each be bound explicitly; this does not rewrite bytecode.
        """
        original = getattr(owner, name)
        @wraps(original)
        def observed(*args, **kwargs):
            current = spec(args, kwargs)
            if current is None:
                return original(*args, **kwargs)
            return self.observe(original, args, kwargs, current,
                                lambda: inputs(args, kwargs),
                                lambda result: outputs(args, kwargs, result),
                                lambda: states(args, kwargs))
        setattr(owner, name, observed)
        try:
            yield
        finally:
            setattr(owner, name, original)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mock', action='store_true')
    p.add_argument('--model', choices=MODELS, default='27b')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--max-bytes', type=int, default=512 * 1024**2)
    p.add_argument('--chunk-bytes', type=int, default=1024**2)
    p.add_argument('--driver', type=Path, help='reviewed in-process comparator adapter; never a shell command')
    p.add_argument('--identity', type=Path)
    p.add_argument('--prompt-id', default='incident-retrospective')
    a = p.parse_args()
    if os.getpriority(os.PRIO_PROCESS, 0) != 19 or os.environ.get('OMP_NUM_THREADS') != '2':
        p.error('requires nice 19 and OMP_NUM_THREADS=2')
    if a.mock:
        if a.driver or a.identity:
            p.error('mock cannot consume native identities/drivers')
        from mock_comparator import run_mock
        run_mock(a.output, a.model, a.max_bytes, a.chunk_bytes)
        return
    if not a.driver or not a.identity:
        p.error('native requires a reviewed --driver and --identity; A367 has no certified image digest (see runbook)')
    identity = json.loads(a.identity.read_text())
    if identity.get('mock') is not False:
        p.error('native driver requires mock=false')
    validate_native_identity(identity)
    binding = json.loads(Path(identity['binding_manifest']['path']).read_text())
    if file_hash(a.driver) != binding.get('driver_sha256'):
        p.error('driver does not match sealed binding manifest')
    # This check precedes importing comparator/driver code, not merely hooks.
    refuse_capture(identity['execution'])
    spec = importlib.util.spec_from_file_location('_packet4_native_driver', a.driver)
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    driver.run(a, Recorder)


if __name__ == '__main__':
    main()

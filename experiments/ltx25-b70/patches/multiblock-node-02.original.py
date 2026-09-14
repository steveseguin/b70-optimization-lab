"""Inactive bounded multi-block exactness gate for a sealed successor runtime.

Three retained selection candidates; no plugin loading, module-forward changes,
parameter copies, failure resets, server actions or automatic retry paths.
"""
import hashlib
import json
import os
from pathlib import Path
import re

import torch
from torch._dynamo.utils import counters
import ltx_multiblock_compile as adapter
from encoder_diagnostics import _context

MODEL_SHA256 = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
ACTIVATIONS_SHA256 = '62b78186fdfc6d9a22cb8cb10423869ecc37cc09c9c0994a7ccebe2eafd41c2a'
RMS_SHA256 = '09defae7340dc3d7f33e16ab80c76f22b6a2ae733617704f2e7b69086108d9fb'
SELECTIONS = {'single24': (24,), 'boundary4': (0, 20, 21, 47), 'all48': tuple(range(48))}
_states = {}
_original = None
_failed = False


def require(value, message):
    if not value:
        raise RuntimeError(message)


def write_json(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def counter_snapshot():
    return {str(group): {str(k): int(v) for k, v in entries.items()}
            for group, entries in counters.items()}


def counter_delta(start):
    now = counter_snapshot()
    return {g: {k: v - start.get(g, {}).get(k, 0) for k, v in values.items()}
            for g, values in now.items()}


def tensor_meta(value):
    return {'shape': list(value.shape), 'stride': list(value.stride()),
            'dtype': str(value.dtype), 'device': str(value.device)}


def signature(x):
    require(type(x) in (tuple, list) and len(x) == 2, 'Expected native video/audio pair')
    return json.dumps([tensor_meta(t) for t in x], sort_keys=True)


def independent_streams(x):
    # The native block mutates only its two streams. Reject unexpected aliasing
    # rather than silently changing an aliased-input program through cloning.
    require(all(type(t) is torch.Tensor and t.is_contiguous() for t in x),
            'Gate requires plain contiguous native input streams')
    require(x[0].untyped_storage().data_ptr() != x[1].untyped_storage().data_ptr(),
            'Aliased native input streams are unsupported by the comparison gate')
    return tuple(t.clone(memory_format=torch.preserve_format) for t in x)


class ComparisonError(RuntimeError):
    def __init__(self, message, rows):
        super().__init__(message)
        self.rows = rows


def require_exact(rows, message):
    if not all(row['finite'] and row['bitwise_equal'] for row in rows):
        raise ComparisonError(message, rows)


def exact_pair(expected, actual):
    require(type(actual) in (tuple, list) and len(actual) == 2, 'Unexpected block output')
    rows = []
    for name, eager, compiled in zip(('video', 'audio'), expected, actual):
        metadata_equal = eager.shape == compiled.shape and eager.dtype == compiled.dtype and eager.device == compiled.device
        # First-stage diagnostic only: byte hashes preserve signed zero and BF16.
        a, b = eager.detach().contiguous().cpu(), compiled.detach().contiguous().cpu()
        a_bytes = a.view(torch.uint8).reshape(-1)
        b_bytes = b.view(torch.uint8).reshape(-1)
        common = min(a_bytes.numel(), b_bytes.numel())
        unequal = int(torch.count_nonzero(a_bytes[:common] != b_bytes[:common])) + abs(a_bytes.numel() - b_bytes.numel())
        finite = bool(torch.isfinite(a).all() and torch.isfinite(b).all())
        rows.append({'output': name, 'finite': finite, 'metadata_equal': metadata_equal,
                     'bitwise_equal': bool(metadata_equal and unequal == 0),
                     'unequal_bytes': unequal,
                     'expected_sha256': hashlib.sha256(a_bytes.numpy().tobytes()).hexdigest(),
                     'actual_sha256': hashlib.sha256(b_bytes.numpy().tobytes()).hexdigest(),
                     'expected': tensor_meta(eager), **tensor_meta(compiled)})
    if not all(row['metadata_equal'] for row in rows):
        raise ComparisonError('Block output metadata differs', rows)
    return rows


def graph_receipts(directory, count, device):
    """Bind this block's own two stage compilations, never process-global totals."""
    require(count in (1, 2), 'Expected one or two qualified native stages')
    paths = sorted(directory.glob('graph-*.json'))
    require([p.name for p in paths] == [f'graph-{i:03d}.json' for i in range(1, count + 1)],
            'Missing graph, unexpected recompile or fallback')
    records = []
    for number, path in enumerate(paths, 1):
        require(not path.is_symlink(), 'Symlink graph receipt')
        row = json.loads(path.read_text())
        require(row.get('schema') == 'ltx25.native-activations-fx-rewrite.v1' and
                row.get('status') == 'compiled-native-activations-boundary' and
                type(row.get('graph')) is int and row['graph'] == number and 'error' not in row,
                'Native operation graph failed')
        require(row.get('source_sha256') == ACTIVATIONS_SHA256 and
                row.get('dependency_sha256') == RMS_SHA256 and
                row.get('options') == adapter.OPTIONS and row.get('expected_count') == 15 and
                row.get('expected_activation_counts') == {'sigmoid': 6, 'gelu': 2},
                'Native operation implementation/options changed')
        rms = row.get('replacements')
        require(isinstance(rms, list) and len(rms) == 15 and
                all(isinstance(r, dict) and isinstance(r.get('node'), str) for r in rms) and
                len({r['node'] for r in rms}) == 15, 'Native RMS site census changed')
        for r in rms:
            shape, metadata = r.get('normalized_shape'), r.get('input')
            require(isinstance(shape, list) and len(shape) == 1 and shape[0] in (2048, 4096) and
                    isinstance(metadata, dict) and metadata.get('dtype') == 'torch.bfloat16' and
                    metadata.get('device') == device and metadata.get('contiguous') is True and
                    isinstance(metadata.get('shape'), list) and metadata['shape'][-1:] == shape,
                    'Native RMS input metadata changed')
            require(type(r.get('weighted')) is bool and
                    r.get('eps') == (1e-5 if r['weighted'] else 1e-6), 'Native RMS epsilon changed')
            weight = r.get('weight')
            require((not r['weighted'] and weight is None) or
                    (r['weighted'] and isinstance(weight, dict) and weight.get('shape') == shape and
                     weight.get('dtype') == metadata['dtype'] and weight.get('device') == device and
                     weight.get('contiguous') is True), 'Native RMS weight changed')
        require(sum(r['weighted'] for r in rms) == 12, 'Native RMS weighting census changed')
        activations = row.get('activation_replacements')
        require(isinstance(activations, list) and len(activations) == 8 and
                all(isinstance(r, dict) and isinstance(r.get('node'), str) for r in activations) and
                len({r['node'] for r in activations}) == 8, 'Native activation sites changed')
        video_tokens = 64 if number == 1 else 256
        expected = {'sigmoid': [[1, video_tokens, 32]] * 3 + [[1, 26, 32]] * 3,
                    'gelu': [[1, video_tokens, 16384], [1, 26, 8192]]}
        for kind, shapes in expected.items():
            selected = [r for r in activations if r.get('kind') == kind]
            require(len(selected) == len(shapes) and
                    all(isinstance(r.get('input'), dict) for r in selected) and
                    sorted(r['input'].get('shape', []) for r in selected) == sorted(shapes),
                    'Native activation shape/kind census changed')
            for r in selected:
                m = r['input']; shape = m['shape']
                require(m.get('dtype') == 'torch.bfloat16' and m.get('device') == device and
                        m.get('contiguous') is True and m.get('stride') == [shape[1] * shape[2], shape[2], 1],
                        'Native activation precision/device/layout changed')
                require((kind == 'gelu' and r.get('approximate') == 'tanh') or
                        (kind == 'sigmoid' and 'approximate' not in r), 'Activation approximation changed')
        files = {'receipt': hashlib.sha256(path.read_bytes()).hexdigest()}
        for phase in ('before', 'after'):
            source = directory / f'graph-{number:03d}-{phase}.py'
            require(source.is_file() and not source.is_symlink(), 'Missing native graph source')
            files[phase] = hashlib.sha256(source.read_bytes()).hexdigest()
        records.append({'graph': number, 'files': files})
    return records


def census(route, index):
    route._validate(check_device=True)
    device = f'xpu:{0 if index < 21 else 1}'
    records = []
    for kind, items in (('parameter', route.block.named_parameters()),
                        ('buffer', route.block.named_buffers())):
        for name, value in items:
            records.append({'name': name, 'kind': kind, 'tensor_id': id(value),
                            'bytes': value.numel() * value.element_size(), **tensor_meta(value)})
    require(len(records) == 84 and len({r['name'] for r in records}) == 84 and
            sum(r['bytes'] for r in records) == 773349760,
            'Native block architecture census differs; review rather than broaden')
    require(all(r['dtype'] == 'torch.bfloat16' and r['device'] == device for r in records),
            'Native block BF16 placement changed')
    diffusion, bound_index, owner, registration, container, slot = route._binding
    require(bound_index == index and str(route.original_route.device) == device,
            'Native block registration/route index changed')
    return {'records': records, 'bytes': sum(r['bytes'] for r in records),
            'block_id': id(route.block), 'diffusion_id': id(diffusion), 'owner_id': id(owner),
            'container_id': id(container), 'registration': registration, 'slot': slot,
            'block_index': index, 'route_device': device}


class _Gate:
    def __init__(self, route, index, graph_directory):
        self.route, self.index = route, index
        self.native, self.compiled = route.block, route.compiled
        self.graph_directory = graph_directory
        self.stages = {}
        self.directory = None
        self.calls = 0
        self.identity = None
        self.failed = False
        self.graph_records = []

    def begin(self, directory, identity):
        require(not self.failed, 'Previous native gate failed')
        require(self.directory is None or self.calls == 11, 'Previous block request incomplete')
        if self.stages:
            require(len(self.stages) == 2, 'Prior block was only partially qualified')
            require(graph_receipts(self.graph_directory, 2, self.device) == self.graph_records,
                    'Qualified native graph evidence changed')
        directory.mkdir(exist_ok=False)
        self.directory, self.identity, self.calls = directory, identity, 0

    @property
    def device(self):
        return f'xpu:{0 if self.index < 21 else 1}'

    def __call__(self, x, **kwargs):
        global _failed
        report = {'schema': 'ltx.multiblock-call.v1', **(self.identity or {}),
                  'call': self.calls + 1, 'passed': False, 'failures': [], 'stage_check': False}
        try:
            require(not self.failed and not _failed, 'Multiblock compiler halted')
            require(self.directory is not None and self.calls < 11, 'Unexpected block invocation')
            self.calls += 1
            _context()
            require(not torch.is_grad_enabled(), 'Native gate requires inference/no-grad')
            self.route._validate_execution()
            shape = signature(x)
            metadata = json.loads(shape)
            video_tokens = 64 if self.calls <= 8 else 256
            require([m['shape'] for m in metadata] == [[1, video_tokens, 4096], [1, 26, 2048]] and
                    all(m['dtype'] == 'torch.bfloat16' and m['device'] == self.device for m in metadata),
                    'Native stage order/shape/device/precision changed')
            report['stage_signature'] = metadata
            report['state_census'] = census(self.route, self.index) if self.calls == 1 else None
            start = counter_snapshot()
            new_stage = shape not in self.stages
            if new_stage:
                require(len(self.stages) < 2 and self.calls in (1, 9), 'Unexpected new stage')
                eager_x, repeat_x = independent_streams(x), independent_streams(x)
                eager = self.native(eager_x, **kwargs)
                result = self.compiled(x, **kwargs)
                report['eager_vs_compiled'] = exact_pair(eager, result)
                require_exact(report['eager_vs_compiled'], 'Native block eager/compiled mismatch')
                repeated = self.compiled(repeat_x, **kwargs)
                report['compiled_vs_repeat'] = exact_pair(result, repeated)
                require_exact(report['compiled_vs_repeat'], 'Native block compiled/repeat mismatch')
                report['stage_check'] = True
                self.stages[shape] = self.calls
            else:
                result = self.compiled(x, **kwargs)
            delta = counter_delta(start)
            report['counter_delta'] = delta
            require(sum(delta.get('graph_break', {}).values()) == 0 and
                    sum(delta.get('unimplemented', {}).values()) == 0,
                    'Compiler graph break or unsupported operation')
            require(delta.get('stats', {}).get('unique_graphs', 0) == int(new_stage),
                    'Unexpected graph reuse, recompile or eager fallback')
            expected_names = [f'graph-{i:03d}.json' for i in range(1, len(self.stages) + 1)]
            require(sorted(p.name for p in self.graph_directory.glob('graph-*.json')) == expected_names,
                    'Per-block graph coverage changed')
            if new_stage or self.calls == 11:
                observed = graph_receipts(self.graph_directory, len(self.stages), self.device)
                require(observed[:len(self.graph_records)] == self.graph_records,
                        'Existing graph evidence changed')
                self.graph_records = observed
                report['native_graphs'] = observed
            report['qualified_stage_count'] = len(self.stages)
            if self.calls == 11:
                require(len(self.stages) == 2, 'Both native stages must qualify')
            report['passed'] = True
            return result
        except BaseException as error:
            self.failed = _failed = True
            if isinstance(error, ComparisonError):
                report['comparison_failure_rows'] = error.rows
            report['failures'].append(repr(error))
            raise
        finally:
            try:
                require(self.directory is not None, 'Gate has no request receipt directory')
                write_json(self.directory / f"call-{report['call']:02d}.json", report)
            except BaseException:
                self.failed = _failed = True
                raise


def _qualified(state):
    return {str(index): len(gate.stages) for index, gate in state['gates'].items()}


class LTXCompileBlocksGate:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'model': ('MODEL',), 'mode': (['original', 'compiled', 'restored'],),
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
            _failed = True
            raise

    def _apply(self, model, mode, selection, run_name):
        global _original
        require(not _failed, 'Previous multiblock failure; halt submissions')
        require(selection in SELECTIONS and mode in ('original', 'compiled', 'restored'),
                'Only preregistered modes/selections are admitted')
        require(isinstance(run_name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', run_name),
                'Unsafe request name')
        run, identity = _context()
        require(identity['model_verification_sha256'] == MODEL_SHA256 and
                identity['server_identity_sha256'] == os.environ.get('LTX_ENCODER_IDENTITY_SHA256'),
                'Model/startup identity changed')
        server = json.loads((run / 'server-identity.json').read_text())
        hashes = {}
        for path in (Path(adapter.__file__), Path(__file__),
                     Path(__file__).with_name('ltx_native_activations_backend.py'),
                     Path(__file__).with_name('ltx_native_rms_backend.py')):
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            require(server['extension_sha256s'][path.name] == actual, 'Sealed extension changed')
            hashes[path.name] = actual
        require(hashes['ltx_native_activations_backend.py'] == ACTIVATIONS_SHA256 and
                hashes['ltx_native_rms_backend.py'] == RMS_SHA256, 'Unqualified native operations')
        require(torch.are_deterministic_algorithms_enabled() and
                not torch.is_deterministic_algorithms_warn_only_enabled(), 'Strict determinism required')
        require(os.environ.get('TORCHINDUCTOR_COMPILE_THREADS') == '1', 'One compiler worker required')
        dynamo_limits = {'recompile_limit': torch._dynamo.config.recompile_limit,
                         'accumulated_recompile_limit': torch._dynamo.config.accumulated_recompile_limit}
        require(_original is None or model is _original, 'Original resident model generation changed')
        indices = SELECTIONS[selection]
        directory = run / ('compiler-' + run_name)
        directory.mkdir(exist_ok=False)
        report = {'schema': 'ltx.multiblock-request.v1', **identity, 'run_name': run_name,
                  'mode': mode, 'selection': selection, 'block_indices': list(indices),
                  'extension_sha256s': hashes, 'compiler_options': dict(adapter.OPTIONS),
                  'dynamo_limits': dynamo_limits,
                  'passed': False, 'failures': []}
        try:
            require(all(type(value) is int for value in dynamo_limits.values()) and
                    dynamo_limits == {'recompile_limit': 8, 'accumulated_recompile_limit': 256},
                    'Actual Dynamo limits differ from the preregistered unchanged8/256 settings')
            adapter._routes(model)
            require(model.ltx_layer_shard_report['split_index'] == 21, 'Expected native21/27 split')
            for state in _states.values():
                require(state['original'] is model and all(not g.failed and
                        (g.directory is None or g.calls == 11) for g in state['gates'].values()),
                        'A prior selection failed or did not complete')
            _original = model
            state = _states.get(selection)
            report['qualified_before'] = _qualified(state) if state else {str(i): 0 for i in indices}
            if mode == 'original':
                result = model
            else:
                if state is None:
                    require(mode == 'compiled' and len(_states) < 3, 'Candidate missing or bound exceeded')
                    receipt_root = run / ('native-multiblock-' + selection)
                    receipt_root.mkdir(exist_ok=False)
                    candidate = adapter.apply_blocks_compile(model, indices, receipt_root=receipt_root)
                    routes = candidate.model_options['transformer_options']['patches_replace']['dit']
                    gates = {}
                    for index in indices:
                        route = routes[('double_block', index)]
                        gate = _Gate(route, index, receipt_root / f'block-{index:02d}')
                        route.compiled = gate
                        gates[index] = gate
                    state = {'original': model, 'candidate': candidate, 'restored': None,
                             'gates': gates, 'receipt_root': receipt_root}
                    _states[selection] = state
                if mode == 'compiled':
                    for index, gate in state['gates'].items():
                        gate.begin(directory / f'block-{index:02d}',
                                   {**identity, 'run_name': run_name, 'selection': selection,
                                    'block_index': index})
                    result = state['candidate']
                else:
                    require(all(n == 2 for n in _qualified(state).values()),
                            'Cannot restore an incompletely qualified selection')
                    if state['restored'] is None:
                        state['restored'] = adapter.remove_blocks_compile(state['candidate'])
                    result = state['restored']
            report['original_id'] = id(model)
            report['candidate_id'] = id(state['candidate']) if state else None
            report['retained_candidate_count'] = len(_states)
            report['qualified_stage_counts'] = _qualified(state) if state else {str(i): 0 for i in indices}
            report['passed'] = True
            return (result,)
        except BaseException as error:
            report['failures'].append(repr(error))
            raise
        finally:
            write_json(directory / 'request.json', report)


NODE_CLASS_MAPPINGS = {'LTXCompileBlocksGate': LTXCompileBlocksGate}

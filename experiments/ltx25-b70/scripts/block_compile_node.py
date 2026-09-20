"""Opt-in one-native-block gate; import only in a sealed successor runtime.

The measured adapter is imported once as ltx_block_compile. No module forward,
registered parameter, or original resident patcher is replaced. Removal restores
dispatch only; one candidate is retained for this finite process-local screen.
"""
import hashlib
import json
import os
from pathlib import Path
import re

import torch
from torch._dynamo.utils import counters
import ltx_block_compile as adapter
from encoder_diagnostics import _context
from ltx_layer_shard import DECLARED_SPLIT_INDEX

ADAPTER_SHA256 = 'c3f3e4ede85b2798981dca40562bd77586ad63afe55b043c0705fceddda29a1e'
MODEL_SHA256 = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
_state = None
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


def check_counters(delta):
    require(sum(delta.get('graph_break', {}).values()) == 0, 'Compiler graph break')
    require(sum(delta.get('unimplemented', {}).values()) == 0, 'Unsupported compiler operation')
    require(delta.get('stats', {}).get('unique_graphs', 0) <= 2,
            'More than the two preregistered stage graphs; halt rather than change guards')


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


def census(route):
    route._validate(check_device=True)
    records = []
    for kind, items in (('parameter', route.block.named_parameters()),
                        ('buffer', route.block.named_buffers())):
        for name, value in items:
            records.append({'name': name, 'kind': kind, 'tensor_id': id(value),
                            'bytes': value.numel() * value.element_size(), **tensor_meta(value)})
    require(len(records) == 84 and sum(row['bytes'] for row in records) == 773349760,
            'Native block state census differs from verified checkpoint architecture')
    require(all(row['dtype'] == 'torch.bfloat16' and row['device'] == 'xpu:1'
                for row in records), 'Native BF16 block must already be resident on XPU1')
    diffusion, index, owner, registration, container, slot = route._binding
    return {'records': records, 'bytes': sum(row['bytes'] for row in records),
            'block_id': id(route.block), 'diffusion_id': id(diffusion), 'owner_id': id(owner),
            'container_id': id(container), 'registration': registration, 'slot': slot,
            'block_index': index, 'route_device': str(route.original_route.device)}


class _Gate:
    def __init__(self, route):
        self.route = route
        self.native = route.block
        self.compiled = route.compiled
        self.baseline = counter_snapshot()
        self.stages = {}
        self.directory = None
        self.calls = 0
        self.identity = None
        self.failed = False

    def begin(self, directory, identity):
        require(not self.failed, 'Previous compiler gate failed; no more requests')
        require(self.directory is None or self.calls == 11,
                'Previous compiled request did not complete exactly eleven block calls')
        self.directory, self.identity, self.calls = directory, identity, 0

    def __call__(self, x, **kwargs):
        global _failed
        require(not self.failed and not _failed, 'Compiler screen halted')
        require(self.directory is not None and self.calls < 11, 'Unexpected compiled invocation count')
        self.calls += 1
        report = {'schema': 'ltx.compiler-block-call.v1', **self.identity,
                  'call': self.calls, 'passed': False, 'failures': [],
                  'stage_check': False}
        try:
            _context()  # Shared fault and startup receipt gate, no GPU work.
            require(not torch.is_grad_enabled(), 'Native gate requires inference/no-grad execution')
            self.route._validate_execution()
            shape = signature(x)
            report['stage_signature'] = json.loads(shape)
            report['state_census'] = census(self.route) if self.calls == 1 else None
            check_counters(counter_delta(self.baseline))
            if shape not in self.stages:
                require(len(self.stages) < 2, 'Unexpected third native stage shape')
                # Both comparison inputs exist before either in-place forward.
                eager_x = independent_streams(x)
                repeat_x = independent_streams(x)
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
            report['counter_delta'] = counter_delta(self.baseline)
            check_counters(report['counter_delta'])
            require(report['counter_delta'].get('stats', {}).get('unique_graphs', 0) >= 1,
                    'No actual compiled graph coverage')
            report['qualified_stage_count'] = len(self.stages)
            if self.calls == 11:
                require(len(self.stages) == 2, 'Both native stage shapes were not qualified')
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
                write_json(self.directory / f'call-{self.calls:02d}.json', report)
            except BaseException:
                self.failed = _failed = True
                raise


class LTXCompileOneBlockGate:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'model': ('MODEL',), 'mode': (['eager', 'compiled', 'restored'],),
                'block_index': ('INT', {'default': 24, 'min': 24, 'max': 24}),
                'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ('MODEL',)
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, model, mode, block_index, run_name):
        global _state, _failed
        require(not _failed, 'Previous compiler gate failed; halt submissions')
        require(type(block_index) is int and block_index == 24, 'Only native block24 is admitted')
        require(mode in ('eager', 'compiled', 'restored'), 'Unsupported compiler mode')
        require(isinstance(run_name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', run_name),
                'Unsafe request name')
        run, identity = _context()
        require(identity['model_verification_sha256'] == MODEL_SHA256 and
                identity['server_identity_sha256'] == os.environ.get('LTX_ENCODER_IDENTITY_SHA256'),
                'Model/startup identity changed')
        server = json.loads((run / 'server-identity.json').read_text())
        for path, name in ((Path(adapter.__file__), 'ltx_block_compile.py'),
                           (Path(__file__), 'block_compile_node.py')):
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            require(server['extension_sha256s'][name] == actual, 'Compiler extension identity mismatch')
            if name == 'ltx_block_compile.py':
                require(actual == ADAPTER_SHA256, 'Unqualified compiler adapter source')
        require(torch.are_deterministic_algorithms_enabled() and
                not torch.is_deterministic_algorithms_warn_only_enabled(), 'Strict determinism required')
        require(os.environ.get('TORCHINDUCTOR_COMPILE_THREADS') == '1', 'One compiler worker required')
        directory = run / ('compiler-' + run_name)
        directory.mkdir(exist_ok=False)
        report = {'schema': 'ltx.compiler-request.v1', **identity, 'run_name': run_name,
                  'mode': mode, 'block_index': block_index, 'adapter_sha256': ADAPTER_SHA256,
                  'compiler_options': dict(adapter.OPTIONS), 'passed': False, 'failures': []}
        try:
            adapter._routes(model)
            require(model.ltx_layer_shard_report['split_index'] == DECLARED_SPLIT_INDEX,
                    'Expected the packet-declared split')
            if _state is not None:
                require(_state['original'] is model, 'Resident model generation changed')
                require(not _state['gate'].failed, 'Compiler gate already failed')
                require(_state['gate'].directory is None or _state['gate'].calls == 11,
                        'Prior compiled request incomplete')
            if mode == 'eager':
                result = model
            else:
                if _state is None:
                    require(mode == 'compiled', 'Cannot restore before candidate exists')
                    candidate = adapter.apply_block_compile(model, block_index)
                    route = candidate.model_options['transformer_options']['patches_replace']['dit'][('double_block', block_index)]
                    gate = _Gate(route)
                    route.compiled = gate
                    _state = {'original': model, 'candidate': candidate, 'gate': gate, 'restored': None}
                if mode == 'compiled':
                    _state['gate'].begin(directory, {**identity, 'run_name': run_name, 'block_index': block_index})
                    result = _state['candidate']
                else:
                    require(len(_state['gate'].stages) == 2, 'Cannot restore an unqualified candidate')
                    if _state['restored'] is None:
                        _state['restored'] = adapter.remove_block_compile(_state['candidate'])
                    result = _state['restored']
            report['candidate_id'] = id(_state['candidate']) if _state else None
            report['original_id'] = id(model)
            report['qualified_stage_count'] = len(_state['gate'].stages) if _state else 0
            report['passed'] = True
            return (result,)
        except BaseException as error:
            _failed = True
            report['failures'].append(repr(error))
            raise
        finally:
            try:
                write_json(directory / 'request.json', report)
            except BaseException:
                _failed = True
                raise


NODE_CLASS_MAPPINGS = {'LTXCompileOneBlockGate': LTXCompileOneBlockGate}

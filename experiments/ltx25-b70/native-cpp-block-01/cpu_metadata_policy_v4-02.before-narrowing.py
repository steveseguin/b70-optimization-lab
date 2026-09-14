"""Inactive CPU-only cache metadata refusal. Stdlib imports only.

Never calls the original Triton backend. Before binding the source-pinned cache
save function, every invocation refuses with the existing sticky BaseException.
"""
import hashlib
import os
from pathlib import Path
import sys
import time
import traceback
import types

SITE = Path('/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages')
PINS = {
    'torch/utils/_ordered_set.py': '5c232fb67e7c378fd46e19c89de9228397439b09f666996dbae177b487455716',
    'torch/utils/_triton.py': '4ff5137347620b8995807cfe3711f7826ef062581cde7d19e798ffbc781f810a',
    'torch/_inductor/codecache.py': '1edadc1e1229adbd7c6f84cef43a04c031add6e1793be0f12b73f22798966156',
    'torch/_inductor/output_code.py': '647fdca5e7ab214acdf8280885d419efc607f3a003353a46611e59ec6b3d8fe6',
}
DESCRIPTION = {
    'schema': 'ltx.cpu-cache-metadata-policy.v4',
    'hook': 'torch.utils._triton.triton_backend',
    'allowed_caller': 'Exact original pinned FxGraphCache._save_graph code object and globals',
    'allowed_metadata': "compiled_graph.device_types == {'cpu'}; extern_libs_key is None",
    'behavior': 'Recorded ordinary exception at allowed CPU save; sticky BaseException everywhere else; never call original backend',
    'scope': 'Same disposable CPU fixture process for eager, Python and C++ compiled/repeat arms',
    'expected_omissions': 4,
    'source_pins': PINS,
}


class CpuOnlyCacheMetadataUnavailable(RuntimeError):
    pass


def source_gate():
    for relative, expected in PINS.items():
        path = SITE / relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError('CPU metadata source pin changed: ' + str(path))


def source_code(relative, qualname):
    # Compile source to Python code objects only; never execute the dependency.
    source = SITE / relative
    root = compile(source.read_text(), str(source), 'exec', dont_inherit=True)
    def walk(code):
        for value in code.co_consts:
            if isinstance(value, types.CodeType):
                if value.co_qualname == qualname:
                    return value
                found = walk(value)
                if found is not None:
                    return found
        return None
    result = walk(root)
    if result is None:
        raise RuntimeError('Pinned code object not found: ' + qualname)
    return result


class MetadataPolicy:
    def __init__(self, triton_utils, report, guard):
        guard.require_clean(report)
        source_gate()
        if 'cpu_metadata_policy' in report:
            raise RuntimeError('CPU metadata policy cannot be reinstalled')
        if Path(triton_utils.__file__).resolve() != SITE / 'torch/utils/_triton.py':
            raise RuntimeError('Triton helper module path mismatch')
        original = triton_utils.triton_backend
        underlying = getattr(original, '__wrapped__', None)
        if not isinstance(underlying, types.FunctionType) or underlying.__code__ != source_code('torch/utils/_triton.py', 'triton_backend'):
            raise RuntimeError('Original Triton backend code changed')
        self.utils, self.report, self.guard = triton_utils, report, guard
        self.cache_class = self.original_save = self.original_save_code = self.ordered_set = None
        self.expected_save = source_code('torch/_inductor/codecache.py', 'FxGraphCache._save_graph')
        self.original_backend = original
        self.events = report.setdefault('cpu_metadata_omissions', [])
        if self.events:
            raise RuntimeError('CPU metadata evidence must start empty')
        # Retain a stable function identity instead of comparing fresh bound methods.
        self.hook = self._refuse_metadata
        self.utils.triton_backend = self.hook
        report['cpu_metadata_policy'] = {**DESCRIPTION, 'installed': True, 'bound': False,
            'original_backend_qualname': underlying.__qualname__,
            'original_backend_firstlineno': underlying.__code__.co_firstlineno}
        self.require_intact()

    def _halt(self, reason, frame=None):
        self.report['accelerator_guard_tripped'] = True
        self.report.setdefault('accelerator_guard_attempts', []).append({
            'entry': 'torch.utils._triton.triton_backend', 'reason': reason,
            'pid': os.getpid(), 'monotonic_ns': time.monotonic_ns(), 'phase': self.report.get('phase'),
            'caller': None if frame is None else {'file': frame.f_code.co_filename,
                'function': frame.f_code.co_qualname, 'line': frame.f_lineno},
            'stack': traceback.format_stack(limit=40)})
        raise self.guard.AcceleratorAccessBlocked('CPU metadata policy halted: ' + reason)

    def bind(self, cache_class):
        self.require_intact()
        if self.cache_class is not None:
            self._halt('Cache save binding cannot be replaced')
        descriptor = vars(cache_class).get('_save_graph')
        original = descriptor.__func__ if isinstance(descriptor, staticmethod) else None
        if not isinstance(original, types.FunctionType) or original.__code__ != self.expected_save:
            self._halt('Cache save code differs from pinned source')
        if original.__globals__.get('FxGraphCache') is not cache_class:
            self._halt('Cache save class/global ownership mismatch')
        ordered_set = original.__globals__.get('OrderedSet')
        if not isinstance(ordered_set, type) or vars(ordered_set).get('__slots__') != ('_dict',):
            self._halt('Expected pinned OrderedSet layout missing')
        if ordered_set.__init__.__code__ != source_code('torch/utils/_ordered_set.py', 'OrderedSet.__init__'):
            self._halt('OrderedSet constructor code changed')
        self.ordered_set = ordered_set
        self.cache_class, self.original_save = cache_class, original
        self.original_save_code = original.__code__
        self.report['cpu_metadata_policy'].update(bound=True, caller_file=original.__code__.co_filename,
            caller_qualname=original.__qualname__, caller_firstlineno=original.__code__.co_firstlineno)
        self.require_intact()

    def require_intact(self):
        self.guard.require_clean(self.report)
        if self.utils.triton_backend is not self.hook:
            self._halt('Metadata hook identity changed')
        if self.cache_class is not None:
            if self.original_save.__globals__.get('OrderedSet') is not self.ordered_set:
                self._halt('OrderedSet global identity changed')
            if self.cache_class._save_graph is not self.original_save or self.original_save.__code__ is not self.original_save_code:
                self._halt('Bound cache save identity changed')

    def _refuse_metadata(self, *args, **kwargs):
        self.require_intact()
        caller = sys._getframe(1)
        try:
            if args or kwargs:
                self._halt('Unexpected backend query arguments', caller)
            if self.original_save is None or caller.f_code is not self.original_save_code or caller.f_globals is not self.original_save.__globals__:
                self._halt('Backend query outside bound CPU cache save', caller)
            graph = caller.f_locals.get('compiled_graph')
            # Read plain instance fields only; no tensor/device API or property call.
            try:
                fields = object.__getattribute__(graph, '__dict__')
            except (AttributeError, TypeError):
                self._halt('Cache graph has no plain instance fields', caller)
            if type(fields) is not dict:
                self._halt('Cache graph fields are not a plain dict', caller)
            devices = fields.get('device_types')
            if type(devices) is self.ordered_set:
                mapping = object.__getattribute__(devices, '_dict')
                if type(mapping) is not dict or any(type(key) is not str for key in mapping):
                    self._halt('OrderedSet metadata is not a plain string-keyed dict', caller)
                devices = tuple(mapping)
            if type(devices) not in (set, frozenset, list, tuple) or any(type(value) is not str for value in devices):
                self._halt('Device metadata is not an exact builtin collection of strings', caller)
            cpu_only = set(devices) == {'cpu'}
            if not cpu_only or 'extern_libs_key' not in fields or fields['extern_libs_key'] is not None:
                self._halt('Cache graph is not qualified CPU-only metadata', caller)
            if len(self.events) >= DESCRIPTION['expected_omissions']:
                self._halt('Too many CPU cache metadata omissions', caller)
            self.events.append({'ordinal': len(self.events) + 1, 'pid': os.getpid(),
                'phase': self.report.get('phase'), 'monotonic_ns': time.monotonic_ns(),
                'caller_file': caller.f_code.co_filename, 'caller_function': caller.f_code.co_qualname,
                'caller_line': caller.f_lineno, 'device_types': ['cpu'], 'extern_libs_key': None,
                'action': 'Raise CpuOnlyCacheMetadataUnavailable; original backend never called'})
            raise CpuOnlyCacheMetadataUnavailable('CPU-only cache save omits accelerator extern-libs metadata')
        finally:
            del caller

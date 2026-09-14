"""Inactive CPU fixture Triton capability policy; stdlib imports only.

The pure replacement never calls the original detection/registry function.
Install before Dynamo imports; do not rewrite already captured aliases.
"""
import hashlib
from pathlib import Path
import sys
import time
import traceback
import types

SITE = Path('/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages')
PINS = {
    'torch/utils/_triton.py': '4ff5137347620b8995807cfe3711f7826ef062581cde7d19e798ffbc781f810a',
    'torch/_dynamo/utils.py': 'e550c68c924e1c0babaf31fc629e900c1d3b6ecbcf10aa88442d39b405b7102a',
    'torch/_dynamo/device_interface.py': 'b21d1fbaae999fee0bb98907c44f454f778bac6b28f43f4c2832930438208e8b',
    'torch/_dynamo/variables/builder.py': '900e23d3fad5636389796eefe1863e861fd848c69040de0d84decd6e00c52142',
}
DESCRIPTION = {
    'schema': 'ltx.cpu-triton-capability-policy.v6',
    'hook': 'torch.utils._triton.has_triton',
    'result': False,
    'implementation': 'Pure literal False; no call counters or original detection calls',
    'scope': 'Entire disposable CPU fixture process; identical eager/Python/C++ compile/repeat arms',
    'alias_policy': 'Install before Dynamo import; reject preexisting Dynamo module, verify later utils.has_triton alias',
    'registry_policy': None,
    'compiler_options_changed': False,
    'semantics': 'Explicit CPU-only Triton capability unavailable; not unchanged accelerator execution semantics',
    'source_pins': PINS,
}


def cpu_has_triton():
    return False


def source_gate():
    for relative, expected in PINS.items():
        if hashlib.sha256((SITE / relative).read_bytes()).hexdigest() != expected:
            raise RuntimeError('CPU Triton policy source changed: ' + relative)


class CpuTritonPolicy:
    def __init__(self, triton_utils, report, guard):
        guard.require_clean(report)
        source_gate()
        self.report, self.guard, self.utils = report, guard, triton_utils
        if 'cpu_triton_policy' in report:
            self._halt('Triton capability policy cannot be reinstalled')
        loaded = sorted(name for name in sys.modules if name == 'torch._dynamo' or name.startswith('torch._dynamo.'))
        if loaded:
            report['cpu_triton_preexisting_dynamo_modules'] = loaded
            self._halt('Install CPU Triton policy before Dynamo imports')
        path = SITE / 'torch/utils/_triton.py'
        if Path(triton_utils.__file__).resolve() != path:
            self._halt('Triton helper module path changed')
        original = triton_utils.has_triton
        underlying = getattr(original, '__wrapped__', None)
        root = compile(path.read_text(), str(path), 'exec', dont_inherit=True)
        expected = next(value for value in root.co_consts if isinstance(value, types.CodeType) and value.co_name == 'has_triton')
        if not isinstance(underlying, types.FunctionType) or underlying.__code__ != expected:
            self._halt('Original Triton detection code changed')
        self.original = original
        self.hook = cpu_has_triton
        triton_utils.has_triton = self.hook
        report['cpu_triton_policy'] = {**DESCRIPTION, 'installed': True,
            'installed_function': self.hook.__qualname__, 'original_firstlineno': underlying.__code__.co_firstlineno,
            'dynamo_utils_alias_verified': False}
        self.require_intact()

    def _halt(self, reason):
        self.report['accelerator_guard_tripped'] = True
        self.report.setdefault('accelerator_guard_attempts', []).append({
            'entry': 'torch.utils._triton.has_triton', 'reason': reason,
            'phase': self.report.get('phase'), 'monotonic_ns': time.monotonic_ns(),
            'stack': traceback.format_stack(limit=40)})
        raise self.guard.AcceleratorAccessBlocked('CPU Triton capability policy halted: ' + reason)

    def require_intact(self, *, require_alias=False):
        self.guard.require_clean(self.report)
        if self.utils.has_triton is not self.hook:
            self._halt('Triton capability hook identity changed')
        module = sys.modules.get('torch._dynamo.utils')
        if module is not None:
            if type(module) is not types.ModuleType or vars(module).get('has_triton') is not self.hook:
                self._halt('Dynamo utils captured a different Triton capability function')
            self.report['cpu_triton_policy']['dynamo_utils_alias_verified'] = True
        elif require_alias:
            self._halt('Expected Dynamo utils alias was never imported')

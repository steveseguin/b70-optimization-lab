"""Inactive CPU diagnostic: use native Triton device-detection disable setting.

Stdlib imports only. Set one process-local environment variable before Torch
imports, then verify native config/function behavior. No callable replacement.
"""
import hashlib
import os
from pathlib import Path
import sys
import time
import traceback
import types

SITE = Path('/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages')
ENV_KEY = 'TORCHINDUCTOR_TRITON_DISABLE_DEVICE_DETECTION'
PINS = {
    'torch/utils/_triton.py': '4ff5137347620b8995807cfe3711f7826ef062581cde7d19e798ffbc781f810a',
    'torch/_inductor/config.py': '9171c2ed249e13a19a2ae22dba0db14f3c4fe11762108f87c8a4e85f96945b0a',
    'torch/_dynamo/utils.py': 'e550c68c924e1c0babaf31fc629e900c1d3b6ecbcf10aa88442d39b405b7102a',
    'torch/_dynamo/device_interface.py': 'b21d1fbaae999fee0bb98907c44f454f778bac6b28f43f4c2832930438208e8b',
    'torch/_dynamo/variables/builder.py': '900e23d3fad5636389796eefe1863e861fd848c69040de0d84decd6e00c52142',
}
DESCRIPTION = {
    'schema': 'ltx.cpu-triton-device-detection-policy.v6',
    'environment': {ENV_KEY: '1'},
    'native_config': {'triton_disable_device_detection': True},
    'native_has_triton_expected': False,
    'scope': 'Same disposable CPU fixture process; set before Torch import and shared by eager/Python/C++ compile/repeat arms',
    'registry_policy': None,
    'callable_replacements': [],
    'numeric_OPTIONS_changed': False,
    'total_compiler_config_changed': True,
    'semantics': 'One explicit CPU diagnostic setting disables native Triton device detection; no unchanged GPU semantics claim',
    'source_pins': PINS,
}


def source_gate():
    for relative, expected in PINS.items():
        if hashlib.sha256((SITE / relative).read_bytes()).hexdigest() != expected:
            raise RuntimeError('CPU Triton policy source changed: ' + relative)


def prepare_environment(report):
    if any(name == 'torch' or name.startswith('torch.') for name in sys.modules):
        raise RuntimeError('Set CPU Triton environment before any Torch import')
    source_gate()
    if 'cpu_triton_environment' in report:
        raise RuntimeError('CPU Triton environment cannot be prepared twice')
    previous = os.environ.get(ENV_KEY)
    os.environ[ENV_KEY] = '1'
    report['cpu_triton_environment'] = {'key': ENV_KEY, 'previous': previous, 'effective': '1',
        'torch_imported': False, 'scope': 'Process-local CPU diagnostic; not installed or host/device settings'}


class CpuTritonPolicy:
    def __init__(self, triton_utils, config, report, guard):
        guard.require_clean(report)
        source_gate()
        self.report, self.guard, self.utils, self.config = report, guard, triton_utils, config
        if 'cpu_triton_policy' in report:
            self._halt('CPU Triton observation cannot be installed twice')
        if report.get('cpu_triton_environment', {}).get('effective') != '1':
            self._halt('Pre-import environment evidence missing')
        path = SITE / 'torch/utils/_triton.py'
        if Path(triton_utils.__file__).resolve() != path or Path(config.__file__).resolve() != SITE / 'torch/_inductor/config.py':
            self._halt('Native Triton/config module source path mismatch')
        original = triton_utils.has_triton
        underlying = getattr(original, '__wrapped__', None)
        code = compile(path.read_text(), str(path), 'exec', dont_inherit=True)
        expected = next(value for value in code.co_consts if isinstance(value, types.CodeType) and value.co_name == 'has_triton')
        if not isinstance(underlying, types.FunctionType) or underlying.__code__ != expected:
            self._halt('Original native has_triton code changed')
        self.original = original
        report['cpu_triton_policy'] = {**DESCRIPTION, 'verified': False,
            'native_function': underlying.__qualname__, 'native_function_firstlineno': underlying.__code__.co_firstlineno}
        self.require_intact()
        # This is the unchanged native function, invoked with all hardware traps
        # active. Its pinned config branch returns before registry enumeration.
        result = original()
        guard.require_clean(report)
        if result is not False:
            self._halt('Native has_triton did not return literal False')
        report['cpu_triton_policy'].update(verified=True, native_has_triton=False,
            observed_triton_disable_device_detection=config.triton_disable_device_detection)
        self.require_intact()

    def _halt(self, reason):
        self.report['accelerator_guard_tripped'] = True
        self.report.setdefault('accelerator_guard_attempts', []).append({
            'entry': 'CPU Triton device-detection policy', 'reason': reason, 'pid': os.getpid(),
            'phase': self.report.get('phase'), 'monotonic_ns': time.monotonic_ns(),
            'stack': traceback.format_stack(limit=40)})
        raise self.guard.AcceleratorAccessBlocked('CPU Triton device-detection policy halted: ' + reason)

    def require_intact(self):
        self.guard.require_clean(self.report)
        if os.environ.get(ENV_KEY) != '1' or self.config.triton_disable_device_detection is not True:
            self._halt('CPU Triton device-detection setting changed')
        if self.utils.has_triton is not self.original:
            self._halt('Native has_triton callable identity changed')

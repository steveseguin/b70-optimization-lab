"""Inactive virtual CPU fixture registry; stdlib imports only.

Uses native registration on a pristine dictionary to install the same six
unindexed interfaces as native initialization with zero enumeration iterations.
No device-count call, interface replacement, query simulation or repair.
"""
import hashlib
import os
from pathlib import Path
import sys
import time
import traceback
import types

SITE = Path('/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages')
DEVICE_SOURCE = 'torch/_dynamo/device_interface.py'
HANDLER_SOURCE = 'torch/_dynamo/variables/torch.py'
PINS = {
    DEVICE_SOURCE: 'b21d1fbaae999fee0bb98907c44f454f778bac6b28f43f4c2832930438208e8b',
    HANDLER_SOURCE: '28e9fce5a40ee7038f1ee8517d73781655849da99a02a560ae8c71ea39042995',
}
INTERFACES = (('cuda', 'CudaInterface'), ('xpu', 'XpuInterface'), ('mtia', 'MtiaInterface'),
              ('cpu', 'CpuInterface'), ('mps', 'MpsInterface'), ('tpu', 'TpuInterface'))
FUNCTIONS = ('register_interface_for_device', 'get_interface_for_device',
             'get_registered_device_interfaces', 'init_device_reg')
DESCRIPTION = {
    'schema': 'ltx.virtual-cpu-device-registry.v7',
    'registry': [name for name, _ in INTERFACES],
    'ordinal_entries': [],
    'semantics': 'Explicit virtual CPU fixture registry, equivalent mapping to native zero enumeration loops; not a host hardware claim',
    'scope': 'One disposable CPU process and one registry lifetime shared by eager/Python/C++ compile/repeat arms',
    'construction': 'Original register_interface_for_device on original empty dict, then original initialized flag True',
    'device_count_calls': 0,
    'repair_or_reset': False,
    'native_interface_classes_preserved': True,
    'numeric_OPTIONS_changed': False,
    'total_compiler_state_changed': True,
    'source_pins': PINS,
}


def source_gate():
    for relative, expected in PINS.items():
        if hashlib.sha256((SITE / relative).read_bytes()).hexdigest() != expected:
            raise RuntimeError('CPU registry source pin changed: ' + relative)


def source_code(relative, qualname):
    path = SITE / relative
    root = compile(path.read_text(), str(path), 'exec', dont_inherit=True)
    def find(code):
        for value in code.co_consts:
            if isinstance(value, types.CodeType):
                if value.co_qualname == qualname:
                    return value
                found = find(value)
                if found is not None:
                    return found
        return None
    result = find(root)
    if result is None:
        raise RuntimeError('Pinned registry code missing: ' + qualname)
    return result


class CpuDeviceRegistryPolicy:
    def __init__(self, device_module, torch, report, guard):
        guard.require_clean(report)
        source_gate()
        self.module, self.torch, self.report, self.guard = device_module, torch, report, guard
        if 'cpu_device_registry_policy' in report:
            self._halt('CPU registry policy cannot be reinstalled')
        if type(device_module) is not types.ModuleType or Path(device_module.__file__).resolve() != SITE / DEVICE_SOURCE:
            self._halt('Native device-interface module path/type changed')
        if sys.modules.get('torch._dynamo.device_interface') is not device_module:
            self._halt('Native device-interface module ownership changed')
        self.registry = device_module.device_interfaces
        if type(self.registry) is not dict or self.registry or device_module._device_initialized is not False:
            self._halt('CPU registry admission requires pristine empty uninitialized state; no repair')
        self.functions = {name: getattr(device_module, name) for name in FUNCTIONS}
        self.function_codes = {}
        for name, function in self.functions.items():
            if not isinstance(function, types.FunctionType) or function.__globals__ is not vars(device_module) or function.__code__ != source_code(DEVICE_SOURCE, name):
                self._halt('Native registry function code/ownership changed: ' + name)
            self.function_codes[name] = function.__code__
        self.classes = {key: getattr(device_module, name) for key, name in INTERFACES}
        for key, name in INTERFACES:
            cls = self.classes[key]
            if not isinstance(cls, type) or cls.__module__ != device_module.__name__ or cls.__qualname__ != name:
                self._halt('Native interface class identity mismatch: ' + key)
        self.aliases = {}
        self.raw_aliases = {}
        for key in ('cuda', 'xpu'):
            cls = self.classes[key]; namespace = getattr(torch, key)
            for name in ('current_device', 'set_device', 'device_count', 'current_stream', 'synchronize', 'get_device_properties'):
                value = getattr(cls, name)
                if value is not getattr(namespace, name):
                    self._halt('Native interface missed installed trap/wrapper: ' + key + '.' + name)
                self.aliases[(key, name)] = value
            raw = getattr(device_module, 'get_' + key + '_stream')
            if getattr(cls, 'get_raw_stream') is not raw or (raw is not None and raw is not getattr(torch._C, '_' + key + '_getCurrentRawStream', None)):
                self._halt('Native raw-stream interface missed installed trap: ' + key)
            self.raw_aliases[key] = raw
        self.handler_objects = {(key, name): getattr(cls, name) for key, cls in self.classes.items()
                                for name in ('stream', 'current_stream', 'Event')}
        handlers = sys.modules.get('torch._dynamo.variables.torch')
        cache_before = None
        if handlers is not None:
            cache_function = handlers.TorchInGraphFunctionVariable._get_handlers
            original = getattr(cache_function, '__wrapped__', None)
            if not isinstance(original, types.FunctionType) or original.__code__ != source_code(HANDLER_SOURCE, 'TorchInGraphFunctionVariable._get_handlers'):
                self._halt('Original generic handler constructor changed')
            cache_before = cache_function.cache_info()._asdict()
            if cache_before['currsize'] != 0:
                self._halt('Generic handler cache already populated before virtual registry')
        self.before = {'registry_id': id(self.registry), 'entries': [], 'initialized': False,
                       'handler_cache': cache_before}
        report['cpu_device_registry_policy'] = {**DESCRIPTION, 'installed': False, 'before': self.before}
        # Do not call init_device_reg: only the native six unindexed registrations.
        for key, _ in INTERFACES:
            self.functions['register_interface_for_device'](key, self.classes[key])
        if list(self.registry) != list(self.classes) or any(self.registry[key] is not cls for key, cls in self.classes.items()):
            self._halt('Native registration produced an unexpected registry')
        device_module._device_initialized = True
        self.require_intact()
        report['cpu_device_registry_policy'].update(installed=True,
            after={'registry_id': id(self.registry), 'initialized': True, 'entries': self._rows()})

    def _rows(self):
        return [{'name': key, 'class': cls.__module__ + '.' + cls.__qualname__, 'class_id': id(cls),
                 'handlers': {name: {'id': id(self.handler_objects[(key, name)]),
                    'qualified_name': getattr(self.handler_objects[(key, name)], '__qualname__', type(self.handler_objects[(key, name)]).__qualname__)}
                    for name in ('stream', 'current_stream', 'Event')}} for key, cls in self.classes.items()]

    def _halt(self, reason):
        self.report['accelerator_guard_tripped'] = True
        self.report.setdefault('accelerator_guard_attempts', []).append({
            'entry': 'virtual CPU device registry', 'reason': reason, 'pid': os.getpid(),
            'phase': self.report.get('phase'), 'monotonic_ns': time.monotonic_ns(),
            'stack': traceback.format_stack(limit=40)})
        raise self.guard.AcceleratorAccessBlocked('CPU registry policy halted: ' + reason)

    def require_intact(self):
        self.guard.require_clean(self.report)
        if sys.modules.get('torch._dynamo.device_interface') is not self.module:
            self._halt('Device-interface module identity changed')
        if self.module.device_interfaces is not self.registry or self.module._device_initialized is not True:
            self._halt('CPU registry dict/initialized identity changed')
        if list(self.registry) != list(self.classes) or any(self.registry[key] is not cls for key, cls in self.classes.items()):
            self._halt('CPU registry keys/order/native classes changed')
        for name, function in self.functions.items():
            if getattr(self.module, name) is not function or function.__code__ is not self.function_codes[name]:
                self._halt('Native registry function identity changed: ' + name)
        for key, name in INTERFACES:
            if getattr(self.module, name) is not self.classes[key]:
                self._halt('Native interface module binding changed: ' + key)
        for (key, name), value in self.aliases.items():
            if getattr(self.classes[key], name) is not value or getattr(getattr(self.torch, key), name) is not value:
                self._halt('Captured trap/wrapper identity changed: ' + key + '.' + name)
        for key, value in self.raw_aliases.items():
            if getattr(self.classes[key], 'get_raw_stream') is not value or getattr(self.module, 'get_' + key + '_stream') is not value:
                self._halt('Raw-stream interface identity changed: ' + key)
            if value is not None and getattr(self.torch._C, '_' + key + '_getCurrentRawStream', None) is not value:
                self._halt('Raw-stream trap identity changed: ' + key)
        for (key, name), value in self.handler_objects.items():
            if getattr(self.classes[key], name) is not value:
                self._halt('Generic handler callable identity changed: ' + key + '.' + name)

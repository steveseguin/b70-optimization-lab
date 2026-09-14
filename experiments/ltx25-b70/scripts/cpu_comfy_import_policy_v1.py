"""Inactive CPU diagnostic policy for one pinned Comfy import-time XPU query.

Stdlib only. Installs after the frozen accelerator guard and before the shared
availability policy captures identities. Never calls a hardware function.
"""
import hashlib
import os
from pathlib import Path
import sys
import time
import types

MODEL_SHA256 = 'ef3f3af0657c1b022ad69b25928fa52dd429db9aed9cb688e89c7fbe68ab50cd'
MODULE_NAME = 'comfy.model_management'
EXPECTED_PHASE = 'guarded-Kitchen-Inductor-import'
DESCRIPTION = {
    'schema': 'ltx.cpu-comfy-import-policy.v1',
    'hook': 'torch.xpu.device_count',
    'source_sha256': MODEL_SHA256,
    'allowed_caller': 'Pinned model_management top-level code and actual importing module globals',
    'preconditions': 'args.cpu is True; expected import phase; first and only omission',
    'behavior': 'Ordinary RuntimeError refusal for one import query; original sticky trap for every other call',
    'expected_omissions': 1,
    'scope': 'Same process across all CPU fixture arms; no device-count simulation or hardware query',
}


class CpuOnlyComfyImportQueryUnavailable(RuntimeError):
    pass


def source_gate(path):
    path = Path(path)
    if not path.is_absolute() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != MODEL_SHA256:
        raise RuntimeError('Comfy import policy requires exact pinned absolute source')
    return path.resolve()


class ComfyImportPolicy:
    def __init__(self, torch, report, guard, *, model_management_source):
        guard.require_clean(report)
        self.source = source_gate(model_management_source)
        if MODULE_NAME in sys.modules:
            raise RuntimeError('Comfy import policy must precede model_management import')
        if 'cpu_comfy_import_policy' in report:
            raise RuntimeError('Comfy import policy cannot be reinstalled')
        if 'torch.xpu.device_count' not in report.get('accelerator_guard_entries', []):
            raise RuntimeError('Install frozen accelerator guard before Comfy import policy')
        self.original_trap = torch.xpu.device_count
        if not isinstance(self.original_trap, types.FunctionType) or self.original_trap.__name__ != 'blocked':
            raise RuntimeError('Expected frozen device-count trap is missing')
        self.torch, self.report, self.guard = torch, report, guard
        self.expected_code = compile(self.source.read_text(), str(self.source), 'exec', dont_inherit=True)
        self.module = self.globals = self.observed_code = None
        self.complete = False
        self.events = report.setdefault('cpu_comfy_import_omissions', [])
        if self.events:
            raise RuntimeError('Comfy import omission evidence must start empty')
        self.hook = self._refuse_import_query
        torch.xpu.device_count = self.hook
        report['cpu_comfy_import_policy'] = {**DESCRIPTION, 'installed': True, 'complete': False,
            'source_path': str(self.source), 'expected_phase': EXPECTED_PHASE}
        self.require_intact()

    def _halt(self, reason, *args, **kwargs):
        self.report.setdefault('cpu_comfy_import_refusals', []).append({
            'reason': reason, 'phase': self.report.get('phase'), 'monotonic_ns': time.monotonic_ns()})
        # Calls the frozen Python trap, never the original hardware implementation.
        return self.original_trap(*args, **kwargs)

    def require_intact(self, *, require_complete=False):
        self.guard.require_clean(self.report)
        if self.torch.xpu.device_count is not self.hook:
            self._halt('Comfy device-count wrapper identity changed')
        if self.report.get('cpu_comfy_import_omissions') is not self.events:
            self._halt('Comfy import omission evidence identity changed')
        if self.module is not None:
            if sys.modules.get(MODULE_NAME) is not self.module or self.module.__dict__ is not self.globals:
                self._halt('Comfy importing module/global identity changed')
        if require_complete and (not self.complete or len(self.events) != 1):
            self._halt('Exactly one completed Comfy import omission required')

    def _refuse_import_query(self, *args, **kwargs):
        self.require_intact()
        caller = sys._getframe(1)
        try:
            module = sys.modules.get(MODULE_NAME)
            allowed = (not args and not kwargs and not self.complete and not self.events and
                self.report.get('phase') == EXPECTED_PHASE and
                type(module) is types.ModuleType and module.__dict__ is caller.f_globals and
                caller.f_globals.get('__name__') == MODULE_NAME and
                caller.f_globals.get('torch') is self.torch and
                caller.f_globals.get('__file__') == str(self.source) and
                caller.f_code == self.expected_code)
            if not allowed:
                return self._halt('Device-count query outside the single qualified CPU Comfy import', *args, **kwargs)
            try:
                args_fields = object.__getattribute__(caller.f_globals.get('args'), '__dict__')
            except (AttributeError, TypeError):
                return self._halt('Expected CPU argument namespace missing')
            if type(args_fields) is not dict or args_fields.get('cpu') is not True:
                return self._halt('Comfy import is not explicitly CPU-only')
            self.module, self.globals, self.observed_code = module, caller.f_globals, caller.f_code
            self.events.append({'ordinal': 1, 'pid': os.getpid(), 'phase': self.report['phase'], 'monotonic_ns': time.monotonic_ns(),
                'source_path': str(self.source), 'source_sha256': MODEL_SHA256,
                'caller_function': caller.f_code.co_name, 'caller_line': caller.f_lineno,
                'args_cpu': True, 'action': 'Raise CpuOnlyComfyImportQueryUnavailable; no hardware query'})
            raise CpuOnlyComfyImportQueryUnavailable('CPU fixture refuses Comfy import-time XPU enumeration')
        finally:
            del caller

    def finish_import(self, module):
        self.require_intact()
        if self.complete or module is not self.module or len(self.events) != 1:
            self._halt('Comfy import completion does not match its unique omission')
        if vars(module).get('xpu_available') is not False:
            self._halt('Comfy CPU import must leave xpu_available False')
        self.complete = True
        self.report['cpu_comfy_import_policy']['complete'] = True
        self.require_intact(require_complete=True)

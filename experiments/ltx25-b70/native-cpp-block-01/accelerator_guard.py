"""Inactive CPU diagnostic traps; install before Kitchen/Inductor imports.

No original accelerator function is called. A BaseException deliberately avoids
being swallowed by cache/property helpers which catch ordinary Exception.
"""
import os
import time
import traceback


class AcceleratorAccessBlocked(BaseException):
    pass


def install(torch, report):
    if torch.xpu.is_initialized() or torch.cuda.is_initialized():
        raise AcceleratorAccessBlocked('Accelerator already initialized before traps')
    attempts = report.setdefault('accelerator_guard_attempts', [])
    installed = []
    def trap(label):
        def blocked(*args, **kwargs):
            attempts.append({'entry': label, 'pid': os.getpid(), 'monotonic_ns': time.monotonic_ns(),
                'phase': report.get('phase'), 'argument_types': [type(value).__name__ for value in args],
                'keyword_names': sorted(kwargs), 'stack': traceback.format_stack(limit=40)})
            raise AcceleratorAccessBlocked('CPU diagnostic blocked accelerator entry: ' + label)
        return blocked
    python_entries = ('init', '_lazy_init', 'device_count', 'get_device_properties',
                      'get_device_capability', 'get_device_name', 'current_device', 'current_stream',
                      'set_device', 'synchronize')
    for device in ('cuda', 'xpu'):
        module = getattr(torch, device)
        for name in python_entries:
            if hasattr(module, name):
                label = 'torch.' + device + '.' + name
                setattr(module, name, trap(label)); installed.append(label)
    for name in ('_cuda_init', '_cuda_getDeviceCount', '_cuda_getDevice', '_cuda_setDevice',
                 '_cuda_getCurrentRawStream', '_xpu_init', '_xpu_getDeviceCount', '_xpu_getDevice',
                 '_xpu_getDeviceProperties', '_xpu_setDevice', '_xpu_getCurrentRawStream'):
        if hasattr(torch._C, name):
            label = 'torch._C.' + name
            setattr(torch._C, name, trap(label)); installed.append(label)
    report['accelerator_guard_entries'] = installed
    report['accelerator_guard_scope'] = ('Process-local Python/C entry traps only; no installed-source/registry/runtime mutation. '
        'They block device enumeration and metadata queries as well as initialization. '
        'No CPU/GPU availability simulation, compiler option changes or retry.')

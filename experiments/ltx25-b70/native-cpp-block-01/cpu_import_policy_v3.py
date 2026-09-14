"""Inactive process-local CPU availability policy; no device queries or imports.

The separate frozen v2 guard still owns every accelerator-entry trap. This is
an explicit fixture policy, not a statement about this host's hardware. It is
installed once before Kitchen/Inductor and shared by eager/Python/C++ arms.
"""

DESCRIPTION = {
    'schema': 'ltx.cpu-import-policy.v3',
    'availability': {'torch.cuda.is_available': False, 'torch.xpu.is_available': False},
    'scope': 'Entire disposable CPU fixture process, before Kitchen/Inductor imports through both compiled arms',
    'arms': ['eager', 'python', 'python_repeat', 'cpp', 'cpp_repeat'],
    'availability_call_logging': False,
    'availability_implementation': 'Pure literal False functions; original availability functions never called',
    'device_entry_traps': 'Frozen accelerator_guard_v2.py retained; sticky BaseException halt',
    'cache_metadata_hook': None,
    'native_admission': 'Pending separate review of Triton NVIDIA ctypes driver-query bypass',
}


def cpu_cuda_unavailable():
    return False


def cpu_xpu_unavailable():
    return False


def install(torch, report, guard):
    guard.require_clean(report)
    if 'cpu_import_policy' in report:
        raise RuntimeError('CPU policy cannot be reinstalled')
    labels = report.get('accelerator_guard_entries', [])
    required = {'torch.' + device + '.' + entry for device in ('cuda', 'xpu')
                for entry in ('_lazy_init', 'device_count', 'current_stream', 'get_device_properties')}
    if not required.issubset(labels):
        raise RuntimeError('Install accelerator traps before CPU availability policy')
    if not all(callable(getattr(getattr(torch, device), 'is_available', None)) for device in ('cuda', 'xpu')):
        raise RuntimeError('Expected CUDA/XPU availability functions missing')
    def resolve(label):
        target = torch
        for name in label.split('.')[1:]:
            target = getattr(target, name)
        return target
    identities = {label: resolve(label) for label in labels}
    torch.cuda.is_available = cpu_cuda_unavailable
    torch.xpu.is_available = cpu_xpu_unavailable
    identities.update({'torch.cuda.is_available': cpu_cuda_unavailable,
                       'torch.xpu.is_available': cpu_xpu_unavailable})
    report['cpu_import_policy'] = {**DESCRIPTION, 'availability': dict(DESCRIPTION['availability']),
        'arms': list(DESCRIPTION['arms']), 'installed': True,
        'installed_function_names': {name: value.__name__ for name, value in identities.items()
                                     if name.endswith('.is_available')},
        'trap_identity_count': len(labels)}
    # The original guard's description refers to the guard alone. Preserve it
    # verbatim as evidence and state the composite policy without ambiguity.
    report['accelerator_guard_original_scope'] = report['accelerator_guard_scope']
    report['accelerator_guard_scope'] = ('Frozen v2 device-entry traps plus explicit process-local CPU availability False policy; '
        'no installed source, compiler option, cache metadata, or device setting changes')
    def require_intact():
        guard.require_clean(report)
        for label, expected in identities.items():
            if resolve(label) is not expected:
                raise RuntimeError('CPU import policy/accelerator trap identity changed: ' + label)
    require_intact()
    return require_intact

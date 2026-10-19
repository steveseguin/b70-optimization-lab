"""CPU-only loader/argument probes: read-only library access, no models/devices.

Linux Landlock confines each child, without sudo, namespaces or services.
No fallback to unsandboxed execution. The host and parent are unchanged.
"""
import ctypes
import os
from pathlib import Path
import resource
import signal
import subprocess
import tempfile
from freeze_safe import Budget

CPU = set(range(8, 16)) | set(range(24, 32))
MEMORY = 2 * 1024**3


def restrict(binary):
    # These syscall numbers are shared by Linux x86_64 and aarch64.
    libc = ctypes.CDLL(None, use_errno=True)
    abi = libc.syscall(444, 0, 0, 1)  # LANDLOCK_CREATE_RULESET_VERSION
    if abi < 1:
        raise RuntimeError('Landlock is required for CPU-only native entry')
    handled = (1 << (15 if abi >= 3 else 14 if abi >= 2 else 13)) - 1
    ruleset = ctypes.c_uint64(handled)
    fd = libc.syscall(444, ctypes.byref(ruleset), ctypes.sizeof(ruleset), 0)
    if fd < 0:
        raise RuntimeError('cannot create read-only entry sandbox')

    class Rule(ctypes.Structure):
        _pack_ = 1
        _fields_ = [('access', ctypes.c_uint64), ('parent', ctypes.c_int32)]

    try:
        # Only installed runtime/tool files and the exact binary are visible.
        # Packet data, /mnt, /home, /dev/dri and /dev/accel are not granted.
        paths = [Path('/usr'), Path('/opt/intel/oneapi'), Path('/etc/ld.so.cache'),
                 Path('/etc/ld.so.conf'), Path('/dev/null'), Path(binary),
                 # Intel's allocator reads its own mapping metadata before
                 # main. Denying this file can spin inside loader startup.
                 # This grants no process memory, file contents or device fd.
                 Path('/proc/self/maps')]
        # Private loader shims may sit beside a packet binary. Only grant .so
        # files, never the packet directory (which can also contain model data).
        for root in (Path(binary).parent, Path(binary).parent.parent.parent / 'runtime'):
            paths.extend(root.glob('*.so*'))
        for path in paths:
            if not path.exists():
                continue
            path = path.resolve()
            allowed = (1 | 4 | 8) if path.is_dir() else (1 | 4)
            if path == Path('/dev/null'):
                allowed = 2 | 4
            parent = os.open(path, os.O_PATH | os.O_CLOEXEC)
            try:
                rule = Rule(allowed, parent)
                if libc.syscall(445, fd, 1, ctypes.byref(rule), 0) != 0:
                    raise RuntimeError('cannot grant loader input')
            finally:
                os.close(parent)
        if libc.prctl(38, 1, 0, 0, 0) != 0 or libc.syscall(446, fd, 0) != 0:
            raise RuntimeError('cannot restrict native entry')
    finally:
        os.close(fd)


def limits(binary):
    os.setpriority(os.PRIO_PROCESS, 0, 19)
    os.sched_setaffinity(0, CPU)
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY, MEMORY))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024**2, 1024**2))
    restrict(binary)


def run(argv, *, binary, cwd=None, timeout=15):
    """Bound output/time/memory; stdin closed; never inherit caller secrets."""
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        try:
            child = subprocess.Popen(argv, env={}, cwd=cwd, stdin=subprocess.DEVNULL,
                                     stdout=out, stderr=err, start_new_session=True,
                                     preexec_fn=lambda: limits(binary))
        except subprocess.SubprocessError as error:
            raise RuntimeError('entry sandbox setup failed') from error
        try:
            budget = Budget(timeout)
            while True:
                try:
                    code = child.wait(timeout=.25)
                    break
                except subprocess.TimeoutExpired:
                    if budget.tick() <= 0:
                        raise
        except subprocess.TimeoutExpired:
            # This process has no device/model access, including its children.
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
            code = 124
        out.seek(0)
        err.seek(0)
        return subprocess.CompletedProcess(argv, code, out.read(1024**2).decode(errors='replace'),
                                            err.read(1024**2).decode(errors='replace'))

#!/usr/bin/env python3
"""CPU-only sibling regular-file pidfd_getfd probe; no model/device imports."""
import ctypes
import json
import os
from pathlib import Path
import platform


def main():
    if platform.machine() != 'x86_64':
        raise RuntimeError('This probe pins the Linux x86_64 syscall ABI')
    status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    result = {'uid': os.getuid(), 'gid': os.getgid(),
              'cap_eff': status['CapEff'].strip(), 'cap_prm': status['CapPrm'].strip(),
              'no_new_privs': status['NoNewPrivs'].strip(), 'seccomp': status['Seccomp'].strip(),
              'sys_ptrace_effective': bool(int(status['CapEff'], 16) & (1 << 19)),
              'scope': 'sibling process ordinary file FD; no GPU or model access'}
    ready_r, ready_w = os.pipe()
    stop_r, stop_w = os.pipe()
    holder = os.fork()
    if holder == 0:
        os.close(ready_r); os.close(stop_w)
        try:
            fd = os.open('/tmp/lab-pidfd-probe', os.O_CREAT | os.O_RDWR | os.O_EXCL, 0o600)
            os.write(fd, b'lab-pidfd-sibling-ok')
            os.write(ready_w, str(fd).encode())
            os.close(ready_w)
            os.read(stop_r, 1)
            os.close(fd)
        finally:
            os._exit(0)
    os.close(ready_w); os.close(stop_r)
    reader = None
    report_r = report_w = None
    try:
        descriptor = int(os.read(ready_r, 64))
        os.close(ready_r)
        report_r, report_w = os.pipe()
        reader = os.fork()
        if reader == 0:
            os.close(report_r); os.close(stop_w)
            report = {'sibling_pid': holder, 'remote_fd': descriptor, 'passed': False}
            try:
                pidfd = os.pidfd_open(holder)
                libc = ctypes.CDLL(None, use_errno=True)
                received = libc.syscall(ctypes.c_long(438), ctypes.c_int(pidfd),
                                        ctypes.c_int(descriptor), ctypes.c_uint(0))
                if received < 0:
                    error = ctypes.get_errno()
                    report.update(errno=error, error=os.strerror(error))
                else:
                    report['passed'] = os.pread(received, 64, 0) == b'lab-pidfd-sibling-ok'
                    os.close(received)
                os.close(pidfd)
            except Exception as exc:
                report['error'] = repr(exc)
            os.write(report_w, json.dumps(report).encode())
            os.close(report_w)
            os._exit(0)
        os.close(report_w); report_w = None
        result.update(json.loads(os.read(report_r, 4096)))
        os.close(report_r); report_r = None
        os.waitpid(reader, 0); reader = None
    finally:
        # Releasing the pipe ends the holder normally, including error paths.
        os.close(stop_w)
        if reader is not None: os.waitpid(reader, 0)
        os.waitpid(holder, 0)
        for fd in (report_r, report_w):
            if fd is not None: os.close(fd)
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0 if result.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())

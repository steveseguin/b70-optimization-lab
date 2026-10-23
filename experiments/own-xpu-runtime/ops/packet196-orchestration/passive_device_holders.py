#!/usr/bin/env python3
"""Privileged metadata-only Intel DRM holder inventory; never opens a device."""
import json
import os
from pathlib import Path
import re
import stat


def scan(sys_drm=Path('/sys/class/drm'), proc_root=Path('/proc'), expected_devices=4):
    nodes, devices, holders, errors = {}, set(), [], []
    try:
        entries = list(sys_drm.iterdir())
    except OSError as error:
        return dict(passed=False, holders=[], errors=['DRM inventory: ' + str(error)], nodes={})
    for node in entries:
        if not re.fullmatch(r'(?:card\d+|renderD\d+)', node.name):
            continue
        try:
            if (node / 'device/vendor').read_text().strip().lower() != '0x8086':
                continue
            major, minor = map(int, (node / 'dev').read_text().strip().split(':'))
            nodes[os.makedev(major, minor)] = node.name
            devices.add(str((node / 'device').resolve(strict=True)))
        except OSError as error:
            errors.append('DRM node ' + node.name + ': ' + str(error))
        except ValueError as error:
            errors.append('DRM node metadata ' + node.name + ': ' + str(error))
    if len(devices) != expected_devices:
        errors.append(f'expected {expected_devices} Intel devices, found {len(devices)}')
    try:
        processes = list(proc_root.iterdir())
    except OSError as error:
        errors.append('process inventory: ' + str(error))
        processes = []
    for proc in processes:
        if not proc.name.isdigit():
            continue
        try:
            fds = list((proc / 'fd').iterdir())
        except (FileNotFoundError, ProcessLookupError):
            continue
        except OSError as error:
            errors.append('PID ' + proc.name + ' fd listing: ' + str(error))
            continue
        for fd in fds:
            try:
                info = fd.stat()
            except (FileNotFoundError, ProcessLookupError):
                continue
            except OSError as error:
                errors.append('PID ' + proc.name + ' fd ' + fd.name + ': ' + str(error))
                continue
            if stat.S_ISCHR(info.st_mode) and info.st_rdev in nodes:
                holders.append(dict(pid=int(proc.name), fd=fd.name, node=nodes[info.st_rdev]))
    return dict(passed=not holders and not errors, holders=holders, errors=errors,
                nodes={f'{os.major(k)}:{os.minor(k)}': v for k, v in sorted(nodes.items())},
                intel_devices=sorted(devices), metadata_only=True, device_opens=0)


def main():
    if os.geteuid() != 0:
        raise SystemExit('root required for complete process descriptor visibility')
    row = scan()
    print(json.dumps(row))
    return 0 if row['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

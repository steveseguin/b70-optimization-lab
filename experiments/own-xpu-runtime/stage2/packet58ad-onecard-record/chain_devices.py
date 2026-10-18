"""Passive Xe ownership checks and fixed masks for the four-card host.

Adapted from this lab's screen/v3/devices.py. Never opens a DRM node or loads
an accelerator library. Keep a private, hash-bound copy in each new chain.
"""
import os
from pathlib import Path
import re
import time

LANES = {'A': ('0000:23:00.0', '0000:27:00.0'),
         'B': ('0000:43:00.0', '0000:47:00.0')}
NATIVE_KEYS = set('HOME LANG LC_ALL LC_CTYPE OMP_NUM_THREADS PATH TMPDIR LD_LIBRARY_PATH'.split())


def onecard_mask():
    # Filter BEFORE Level Zero enumeration; a SYCL selector alone is too late.
    return dict(NEOReadDebugKeys='1', FilterBdfPath='0000:23:00.0',
                ZE_ENABLE_PCI_ID_DEVICE_ORDER='1', ZE_AFFINITY_MASK='0',
                ONEAPI_DEVICE_SELECTOR='level_zero:0')


def onecard_environment(closed_native, home):
    require(set(closed_native) <= NATIVE_KEYS, 'native environment was not closed/unmasked')
    return private_home(dict(closed_native, **onecard_mask()), home)


def verify_onecard_environment(environment):
    require(all(environment.get(k) == v for k, v in onecard_mask().items()),
            'one-card pre-open mask differs')
    home = Path(environment.get('HOME', ''))
    require(home.is_absolute() and home.is_dir() and not (home/'igdrcl.config').exists(),
            'private native HOME required without driver debug override')


def onecard_topology(by_path=Path('/dev/dri/by-path'), sys_drm=Path('/sys/class/drm'),
                     dev_dri=Path('/dev/dri'), cwd=None):
    """Passive exact mapping proof; never open a device or enumerate through L0."""
    bdf = onecard_mask()['FilterBdfPath']
    require(by_path.is_dir(), 'by-path directory required; no unfiltered fallback')
    matches = [p for p in by_path.iterdir() if bdf in p.name and p.name.endswith('-render')]
    require(len(matches) == 1 and matches[0].name == 'pci-' + bdf + '-render',
            'BDF filter must select exactly card 0')
    node = matches[0].resolve(strict=True)
    require(node.parent == dev_dri.resolve() and re.fullmatch(r'renderD[0-9]+', node.name),
            'unexpected render-node mapping')
    pci = (sys_drm / node.name / 'device').resolve(strict=True).name
    driver = (sys_drm / node.name / 'device/driver').resolve(strict=True).name
    require(pci == bdf and driver == 'xe', 'PCI/driver mapping differs')
    require(not ((Path.cwd() if cwd is None else cwd) / 'igdrcl.config').exists(),
            'unexpected driver debug configuration in cwd')
    return dict(mask=onecard_mask(), native_indices=[0],
                nodes=[dict(pci=pci, node=str(node), path=str(matches[0]), driver=driver)],
                device_nodes_opened=False)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def mask_for(lane):
    return dict(NEOReadDebugKeys='1', FilterBdfPath={'A': '0000:2', 'B': '0000:4'}[lane],
                ZE_ENABLE_PCI_ID_DEVICE_ORDER='1', ZE_AFFINITY_MASK='0,1',
                ONEAPI_DEVICE_SELECTOR='level_zero:0,1')


def mask_native(closed_native, lane='A'):
    """Call AFTER the packet's existing closed environment gate, never before."""
    require(set(closed_native) <= NATIVE_KEYS, 'native environment was not closed/unmasked')
    return dict(closed_native, **mask_for(lane))


def private_home(environment, home):
    """New empty HOME for native discovery; never consult a user's debug file."""
    home = Path(home)
    home.mkdir(mode=0o700, parents=True, exist_ok=False)
    return dict(environment, HOME=str(home.resolve()))


def topology_admit(lane='A', by_path=Path('/dev/dri/by-path'),
                   sys_drm=Path('/sys/class/drm'), dev_dri=Path('/dev/dri'), cwd=None):
    prefix = mask_for(lane)['FilterBdfPath']
    require(by_path.is_dir(), 'by-path directory required; no unfiltered fallback')
    rows = []
    for path in sorted(by_path.iterdir()):
        if prefix not in path.name or not path.name.endswith('-render'):
            continue
        match = re.fullmatch(r'pci-([0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7])-render', path.name)
        require(match is not None, 'unrecognized matching render path')
        node = path.resolve(strict=True)
        require(node.parent == dev_dri.resolve() and re.fullmatch(r'renderD[0-9]+', node.name),
                'unexpected render-node mapping')
        pci = (sys_drm / node.name / 'device').resolve(strict=True).name
        driver = (sys_drm / node.name / 'device/driver').resolve(strict=True).name
        require(pci == match[1] and driver == 'xe', 'PCI/driver mapping differs')
        rows.append(dict(pci=pci, path=str(path), node=str(node), driver=driver))
    require(sorted(r['pci'] for r in rows) == sorted(LANES[lane]),
            'BDF filter must select exactly the two registered lane devices')
    require(not ((Path.cwd() if cwd is None else cwd) / 'igdrcl.config').exists(),
            'unexpected driver debug configuration in cwd')
    return dict(lane=lane, mask=mask_for(lane), native_indices=[0, 1], nodes=rows,
                device_nodes_opened=False)


def process_identity(pid, proc=Path('/proc')):
    """Handle spaces and parentheses in comm; zombies no longer own device FDs."""
    try:
        fields = (proc / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return None
    require(len(fields) >= 20, 'malformed process stat')
    return None if fields[0] in ('Z', 'X') else int(fields[19])


def xe_fds(pid, proc=Path('/proc')):
    rows = []
    for info in sorted((proc / str(pid) / 'fdinfo').iterdir()):
        try:
            fields = dict(line.split(':', 1) for line in info.read_text().splitlines() if ':' in line)
        except (FileNotFoundError, ProcessLookupError):
            continue
        driver = fields.get('drm-driver', '').strip()
        # DRM counters without a driver cannot establish an unrelated device.
        if driver == 'xe' or not driver and any(k.startswith('drm-') for k in fields):
            rows.append(dict(pid=int(pid), fd=info.name, driver=driver,
                             pci=fields.get('drm-pdev', '').strip(),
                             client_id=fields.get('drm-client-id', '').strip()))
    return rows


def foreign_clients(scope, proc=Path('/proc'), owned=None):
    """Presence, not counter growth: idle foreign clients also reserve a card.

    As in screen v3, inaccessible foreign processes are counted for coordinator
    review. This cannot establish absence of another UID's hidden clients.
    Owned exemptions are PID AND start-tick bound; never use a bare PID list.
    """
    require(scope in ('lane-A', 'lane-B', 'whole-host'), 'unknown admission scope')
    owned = {} if owned is None else owned
    rows, hidden = [], 0
    for directory in sorted(proc.iterdir()):
        if not directory.name.isdigit():
            continue
        pid = int(directory.name)
        try:
            start = process_identity(pid, proc)
            if start is None:
                continue
            fds = xe_fds(pid, proc)
            if pid in owned and start == owned[pid] and process_identity(pid, proc) == start:
                continue
            rows.extend(fds)
        except PermissionError:
            hidden += 1
        except (FileNotFoundError, ProcessLookupError):
            continue
    selected = set(LANES['A' if scope == 'lane-A' else 'B'])
    known = set(LANES['A'] + LANES['B'])
    blocked = [r for r in rows if scope == 'whole-host' or r['pci'] in selected
               or r['pci'] not in known or r['driver'] != 'xe']
    result = dict(scope=scope, blocked=blocked, other=[r for r in rows if r not in blocked],
                  inaccessible_processes=hidden, hidden_clients_require_coordinator_ownership=True,
                  device_nodes_opened=False)
    return result


def admit_clients(scope, proc=Path('/proc'), owned=None):
    row = foreign_clients(scope, proc, owned)
    require(not row['blocked'], 'foreign Xe clients: ' + str(row['blocked']))
    return row


class DeviceMonitor:
    """Support serial fixture owners AND rank pairs; retain proof for each PID.

    Every owner must be observed holding an allowed Xe FD before it exits.
    Missing a very short owner refuses qualification, rather than guessing.
    """
    def __init__(self, lane='A', proc=Path('/proc'), now=time.monotonic):
        self.lane, self.proc, self.now = lane, proc, now
        self.owners, self.last, self.ready_checks = {}, None, 0

    def register(self, pid):
        require(pid not in self.owners, 'duplicate/reused owner PID')
        start = process_identity(pid, self.proc)
        require(start is not None, 'owner exited before isolation registration')
        self.owners[pid] = dict(start_ticks=start, seen=False, exited=False, fds=[])
        self.poll(force=True)

    def poll(self, force=False):
        now = self.now()
        if not force and self.last is not None and now - self.last < .25:
            return
        self.last = now
        allowed = set(LANES[self.lane])
        for pid, owner in self.owners.items():
            if owner['exited']:
                continue
            start = process_identity(pid, self.proc)
            if start is None:
                owner['exited'] = True
                require(owner['seen'], 'owner exited without observed Xe isolation proof')
                continue
            require(start == owner['start_ticks'], 'owner PID reused')
            try:
                fds = xe_fds(pid, self.proc)
            except (FileNotFoundError, ProcessLookupError):
                require(process_identity(pid, self.proc) is None and owner['seen'],
                        'owner disappeared before isolation proof')
                owner['exited'] = True
                continue
            owner['fds'] = fds  # retain the offending raw FD before refusal
            require(all(r['driver'] == 'xe' and r['pci'] in allowed for r in fds),
                    'owner holds foreign or unidentified Xe device')
            after = process_identity(pid, self.proc)
            require(after in (None, start), 'owner PID reused during fdinfo read')
            owner['seen'] = owner['seen'] or bool(fds)

    def ready(self, pids):
        """Call after both native READY replies, before the first request."""
        self.poll(force=True)
        require(len(pids) == 2 and len(set(pids)) == 2, 'two distinct ready ranks required')
        for rank, pid in enumerate(pids):
            owner = self.owners[pid]
            require(not owner['exited'] and LANES[self.lane][rank] in
                    {r['pci'] for r in owner['fds']}, 'ready rank mapped device unproven')
        self.ready_checks += 1

    def finish(self):
        self.poll(force=True)
        require(self.owners and all(r['seen'] and r['exited'] for r in self.owners.values()),
                'device owners still live or isolation unproven')

    def live_identities(self):
        return {pid: r['start_ticks'] for pid, r in self.owners.items() if not r['exited']}

"""Pre-open Intel BDF filtering plus passive proof of native fd ownership.

ZE_AFFINITY_MASK alone filters exposed devices after DRM discovery. Intel's
FilterBdfPath filters /dev/dri/by-path entries BEFORE open(2). The host's two
lane prefixes are admitted against the actual by-path and sysfs inventory.
No function here initializes a device or opens a device node.
"""
import os
from pathlib import Path
import re
import time
from common import SUPPORT, W, read, require, save
from conditions import LANES


def mask_for(lane):
    return dict(NEOReadDebugKeys='1', FilterBdfPath={'A': '0000:2', 'B': '0000:4'}[lane],
                ZE_ENABLE_PCI_ID_DEVICE_ORDER='1', ZE_AFFINITY_MASK='0,1',
                ONEAPI_DEVICE_SELECTOR='level_zero:0,1')


def masked_environment(lane, source=None, inherited=False):
    source = dict(os.environ if source is None else source)
    mask = mask_for(lane)
    if inherited:
        require(all(source.get(k) == v for k, v in mask.items()), 'worker device mask changed')
        source = {k: v for k, v in source.items() if k not in mask}
    env = W.closed_environment(source)
    # User-supplied selectors/debug options are rejected by closed_environment;
    # only this fixed mask can be inserted after the original environment gate.
    env.update(mask)
    return env


def topology_admit(lane, by_path=Path('/dev/dri/by-path'), sys_drm=Path('/sys/class/drm'),
                   dev_dri=Path('/dev/dri')):
    prefix = mask_for(lane)['FilterBdfPath']
    rows = []
    require(by_path.is_dir(), 'by-path directory required; no unfiltered DRM fallback')
    for path in sorted(by_path.iterdir()):
        if prefix not in path.name or not path.name.endswith('-render'):
            continue
        match = re.fullmatch(r'pci-([0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7])-render', path.name)
        require(match is not None, 'unrecognized matching render path')
        node = path.resolve(strict=True)
        require(node.parent == dev_dri and re.fullmatch(r'renderD[0-9]+', node.name),
                'unexpected render-node mapping')
        pci = (sys_drm / node.name / 'device').resolve(strict=True).name
        driver = (sys_drm / node.name / 'device/driver').resolve(strict=True).name
        require(pci == match[1] and driver == 'xe', 'PCI/driver mapping differs')
        rows.append(dict(pci=pci, path=str(path), node=str(node), driver=driver))
    require(sorted(r['pci'] for r in rows) == sorted(LANES[lane]['pci']),
            'BDF filter must select exactly the two registered lane devices')
    # NEO debug-file settings must not override the closed environment. Native
    # HOME is a fresh private cache; the working directory is the repo root.
    require(not Path('igdrcl.config').exists(), 'unexpected driver debug configuration in cwd')
    return dict(lane=lane, filter=prefix, native_indices=[0, 1], nodes=rows,
                device_nodes_opened=False)


def rank_fds(pid, proc=Path('/proc')):
    rows = []
    # Unlike foreign-client discovery, our own child's fdinfo MUST be readable.
    for info in sorted((proc / str(pid) / 'fdinfo').iterdir(), key=lambda p: int(p.name)):
        try:
            fields = dict(line.split(':', 1) for line in info.read_text().splitlines() if ':' in line)
        except FileNotFoundError:  # a descriptor can close between listing and read
            continue
        if fields.get('drm-driver', '').strip() == 'xe':
            rows.append(dict(fd=info.name, pci=fields.get('drm-pdev', '').strip(),
                             client_id=fields.get('drm-client-id', '').strip()))
    return rows


class DeviceMonitor:
    """Poll only owned PIDs, bound to start ticks; fail closed on foreign Xe FDs.

    Startup polls allow zero FDs while exec/initialization is in progress.
    Both ranks must hold their mapped PCI device at the ready checkpoint, and
    their union must be exactly the lane pair. Evidence is written before any
    refusal. Repeated polls run at most four times/sec; stable snapshots do not
    add repeated disk writes. A ready checkpoint always forces a fresh sample.
    """
    def __init__(self, lane, output, proc=Path('/proc'), now=time.monotonic):
        self.lane, self.output, self.proc, self.now = lane, output, proc, now
        self.pids, self.starts = [], {}
        self.last = None
        self.signature = None
        self.samples = 0
        self.proved = False

    def register(self, pid):
        require(pid not in self.pids and len(self.pids) < 2, 'unexpected rank launch')
        self.pids.append(pid)
        self.starts[pid] = SUPPORT.process_start(pid)
        self.poll(force=True)

    def poll(self, ready=False, force=False):
        now = self.now()
        if not ready and not force and self.last is not None and now - self.last < .25:
            return
        self.last = now
        self.samples += 1
        allowed = set(LANES[self.lane]['pci'])
        ranks, errors = [], []
        for rank, pid in enumerate(self.pids):
            fds = []
            try:
                require(SUPPORT.process_start(pid) == self.starts[pid], 'rank PID gone or reused')
                fds = rank_fds(pid, self.proc)
                actual = {row['pci'] for row in fds}
                require(actual <= allowed, 'rank holds foreign or unidentified Xe device')
                if ready:
                    require(LANES[self.lane]['pci'][rank] in actual, 'rank mapped device not observed')
                ranks.append(dict(rank=rank, pid=pid, process_start_ticks=self.starts[pid],
                                  pci=sorted(actual), fds=fds))
            except (OSError, ValueError) as error:
                # Preserve raw FDs, including the offending PCI, when available.
                ranks.append(dict(rank=rank, pid=pid, error=str(error),
                                  fds=fds))
                errors.append(str(error))
        if ready:
            if len(ranks) != 2 or set().union(*(set(r.get('pci', [])) for r in ranks)) != allowed:
                errors.append('two-rank lane coverage unproven')
            if not errors:
                self.proved = True
        signature = repr(ranks)
        if ready or errors or signature != self.signature:
            save(self.output / 'device-isolation.json', dict(
                schema='own-runtime.screen.device-isolation.v3', lane=self.lane,
                passed=self.proved and not errors, ready_checkpoint=ready,
                allowed_pci=sorted(allowed), mask=mask_for(self.lane), ranks=ranks,
                sample_count=self.samples, sampled_monotonic=now, errors=errors))
            self.signature = signature
        require(not errors, 'device isolation failed: ' + '; '.join(errors))

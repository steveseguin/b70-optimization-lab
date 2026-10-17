"""Fixed screen conditions and passive ownership checks; no device discovery."""
import fcntl
from drain_gate import DEFAULT_DRAIN_ROOT, screen_teardown_admit
import os
from pathlib import Path
import time
from common import HERE, SUPPORT, read, require, save

CPU_CORES = set(range(8, 16)) | set(range(24, 32))
LANES = {
    'A': dict(card=0, cards=[0, 1], pci=['0000:23:00.0', '0000:27:00.0'],
              cores=[0, 1, 2, 3, 16, 17, 18, 19], affinity='0-3,16-19', nice=0, native_card=0, native_cards=[0, 1]),
    'B': dict(card=2, cards=[2, 3], pci=['0000:43:00.0', '0000:47:00.0'],
              cores=[4, 5, 6, 7, 20, 21, 22, 23], affinity='4-7,20-23', nice=0, native_card=0, native_cards=[0, 1]),
}


def cpu_gate():
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19 and
            set(os.sched_getaffinity(0)) <= CPU_CORES, 'CPU preparation needs nice19, cores8-15,24-31')


def lane_gate(lane):
    require(os.getpriority(os.PRIO_PROCESS, 0) == 0 and
            set(os.sched_getaffinity(0)) == set(LANES[lane]['cores']),
            'device screen needs nice0 and exact lane affinity')


def selected_clients(lane, proc=Path('/proc'), *, owned_pids=(), whole_host=False):
    selected, other, hidden = [], [], 0
    for pid in proc.iterdir():
        if not pid.name.isdigit():
            continue
        if int(pid.name) in owned_pids:
            continue
        try:
            infos = list((pid / 'fdinfo').iterdir())
        except PermissionError:
            hidden += 1
            continue
        except FileNotFoundError:
            continue
        for info in infos:
            try:
                fields = dict(line.split(':', 1) for line in info.read_text().splitlines() if ':' in line)
            except PermissionError:
                hidden += 1
                continue
            except (FileNotFoundError, ProcessLookupError):
                continue
            if fields.get('drm-driver', '').strip() == 'xe':
                pci = fields.get('drm-pdev', '').strip()
                row = dict(pid=int(pid.name), pci=pci, fd=info.name)
                (selected if pci in LANES[lane]['pci'] or not pci else other).append(row)
    require(not selected, 'selected pair occupied or unidentified Xe client: ' + str(selected))
    require(not whole_host or not other, 'whole-host screen has another Xe client: ' + str(other))
    return dict(selected=selected, other=other, inaccessible_entries=hidden,
                hidden_clients_require_coordinator_ownership=True)


class Teardown:
    """Serialize complete drains, then hold the next drain for >=60 seconds.

    All v3 workers share this gate, including standalone screens and failures.
    An incomplete drain leaves an active record and refuses further launches.
    A coordinator stop is recorded by the caller but cannot bypass this gate.
    """
    def __init__(self, output, root=DEFAULT_DRAIN_ROOT, now=time.monotonic, sleep=time.sleep):
        self.output, self.root, self.now, self.sleep = output, root, now, sleep
        self.lock = None
        self.boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()

    def __enter__(self):
        self.lock = (self.root / 'teardown.lock').open('a')
        while True:
            try:
                fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                self.sleep(.25)
        try:
            path = self.root / 'teardown-state.json'
            prior = read(path) if path.exists() else {}
            if prior.get('boot_id') == self.boot:
                require(prior.get('drained') is True, 'previous teardown incomplete; coordinator required')
                until = prior['completed_monotonic'] + 60.0
                while self.now() < until:
                    self.sleep(min(.25, until - self.now()))
            self.record = dict(boot_id=self.boot, output=str(self.output), pid=os.getpid(),
                               started_monotonic=self.now(), drained=False)
            save(path, self.record)
            save(self.output / 'teardown.json', self.record)
            return self
        except BaseException:
            self.lock.close()
            raise

    def __exit__(self, kind, value, trace):
        if kind is None:
            self.record.update(drained=True, completed_monotonic=self.now())
            save(self.root / 'teardown-state.json', self.record)
            save(self.output / 'teardown.json', self.record)
        self.lock.close()


def teardown_admit(lane):
    # Only the prelaunch check permits live A computation. Actual Teardown
    # still locks, waits 60 seconds and refuses an incomplete previous drain.
    screen_teardown_admit(lane)

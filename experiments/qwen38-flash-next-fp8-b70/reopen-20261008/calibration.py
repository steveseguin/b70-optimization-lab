"""CPU accounting only. No accelerator library, privileged read or device ioctl.

RSS, cgroup and locked counters overlap; only MemTotal-MemAvailable is used
for whole-host pressure. Missing VRAM stays unknown, never zero.
"""
import hashlib
import json
from pathlib import Path
import re
import time

GIB = 2**30
INTERVAL = .5
PLATEAU_SECONDS = 20
HOST_LIMIT = 90_000_000_000


def parse_kib(text):
    fields = {}
    for line in text.splitlines():
        match = re.fullmatch(r'([\w()]+):\s+(\d+)\s+kB\s*', line)
        if match:
            fields[match[1]] = int(match[2]) * 1024
    return fields


def parse_meminfo(text):
    m = parse_kib(text)
    for key in ('MemTotal', 'MemAvailable', 'Committed_AS', 'Mlocked', 'Unevictable'):
        if key not in m:
            raise ValueError(f'missing {key}')
    if not 0 <= m['MemAvailable'] <= m['MemTotal']:
        raise ValueError('invalid MemAvailable')
    return {'monotonic': time.monotonic(), 'mem_total_bytes': m['MemTotal'],
            'mem_available_bytes': m['MemAvailable'],
            'accounted_pressure_bytes': m['MemTotal'] - m['MemAvailable'],
            'committed_as_bytes': m['Committed_AS'], 'mlocked_bytes': m['Mlocked'],
            'unevictable_bytes': m['Unevictable'],
            # Preserve attribution evidence (including GPUActive/GPUReclaim
            # when this kernel exposes them), without changing pressure math.
            'meminfo_bytes': m}


def trip_reason(sample):
    if sample['mem_available_bytes'] < 24 * GIB:
        return 'MemAvailable < 24 GiB'
    for rank, free in enumerate(sample.get('vram_free_bytes_per_rank', [])):
        if free is not None and free < 2 * GIB:
            return f'rank {rank} VRAM free < 2 GiB'
    return None


def read_vram(root=Path('/sys/class/drm')):
    """Read explicit byte-valued total/used sysfs pairs only, never xpu-smi.

    Some xe kernels expose no such counters. Return four unknowns in that
    case. PCI order matches the fixed flat 0,1,2,3 launch on this host;
    retain BDFs for review. Never mix Intel cards with other DRM devices.
    """
    devices = {}
    for card in root.glob('card[0-9]*'):
        if not re.fullmatch(r'card\d+', card.name):
            continue
        device = card / 'device'
        try:
            if (device / 'vendor').read_text().strip() != '0x8086':
                continue
            devices[device.resolve().name] = device
        except OSError:
            continue
    rows = []
    for bdf, device in sorted(devices.items()):
        row = {'pci_bdf': bdf, 'free_bytes': None, 'total_bytes': None}
        try:
            total = int((device / 'mem_info_vram_total').read_text())
            used = int((device / 'mem_info_vram_used').read_text())
            if total <= 0 or not 0 <= used <= total:
                raise ValueError('invalid VRAM counters')
            row.update(total_bytes=total, free_bytes=total-used,
                       source=str(device / 'mem_info_vram_used'))
        except (OSError, ValueError) as exc:
            row['unavailable'] = str(exc)
        rows.append(row)
    if len(rows) != 4:
        return [None]*4, rows
    return [row['free_bytes'] for row in rows], rows


class Sampler:
    def __init__(self, proc=Path('/proc'), cgroups=Path('/sys/fs/cgroup'), drm=Path('/sys/class/drm')):
        self.proc, self.cgroups, self.drm = proc, cgroups, drm
        self.container_pid = None
        self.phase = 'loading'

    def __call__(self):
        sample = parse_meminfo((self.proc / 'meminfo').read_text())
        sample.update(phase=self.phase, worker_rss_bytes=[None]*4,
                      worker_pids=[None]*4, cgroup_memory_current_bytes=None,
                      cgroup_memory_peak_bytes=None, cgroup_memory_stat=None,
                      attribution_errors=[], accounting_errors=[])
        if self.container_pid:
            try:
                entries = (self.proc / str(self.container_pid) / 'cgroup').read_text().splitlines()
                rel = next(x[3:] for x in entries if x.startswith('0::'))
                cg = self.cgroups / rel.lstrip('/')
                if self.cgroups.resolve() not in cg.resolve().parents:
                    raise ValueError('unsafe/root container cgroup')
                sample['cgroup_path'] = str(cg)
                sample['cgroup_memory_current_bytes'] = int((cg / 'memory.current').read_text())
                if (cg / 'memory.peak').exists():
                    sample['cgroup_memory_peak_bytes'] = int((cg / 'memory.peak').read_text())
                try:
                    # Values have the kernel's native units: memory sizes are
                    # bytes, pgfault and similar entries are counts.
                    sample['cgroup_memory_stat'] = {
                        k: int(v) for k, v in (line.split() for line in
                                              (cg / 'memory.stat').read_text().splitlines())}
                except (OSError, ValueError) as exc:
                    sample['attribution_errors'].append(str(exc))
                pid_files = [cg / 'cgroup.procs', *cg.glob('**/cgroup.procs')]
                pids = set(p for file in pid_files for p in file.read_text().split())
                for pid in sorted(pids):
                    try:
                        p = self.proc / pid
                        title = (p / 'comm').read_text() + (p / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
                        rank = re.search(r'Worker_TP([0-3])(?:\D|$)', title)
                        if rank:
                            r = int(rank[1])
                            if sample['worker_pids'][r] is not None:
                                raise ValueError(f'duplicate worker rank {r}')
                            sample['worker_pids'][r] = int(pid)
                            sample['worker_rss_bytes'][r] = parse_kib((p / 'status').read_text())['VmRSS']
                    except FileNotFoundError:
                        continue
            except (OSError, ValueError, KeyError, StopIteration) as exc:
                sample['accounting_errors'].append(str(exc))
        free, cards = read_vram(self.drm)
        sample.update(vram_free_bytes_per_rank=free, cards=cards)
        return sample


def phase_peaks(samples):
    result = {}
    for phase in ('loading', 'plateau', 'shutdown'):
        rows = [s for s in samples if s.get('phase') == phase and 'error' not in s]
        if not rows:
            result[phase] = None
            continue
        keys = ('accounted_pressure_bytes', 'committed_as_bytes', 'mlocked_bytes',
                'unevictable_bytes', 'cgroup_memory_current_bytes', 'cgroup_memory_peak_bytes')
        entry = {k: max((s[k] for s in rows if s.get(k) is not None), default=None) for k in keys}
        entry['mem_available_min_bytes'] = min(s['mem_available_bytes'] for s in rows)
        entry['worker_rss_peak_bytes'] = [max((s['worker_rss_bytes'][r] for s in rows if s['worker_rss_bytes'][r] is not None), default=None) for r in range(4)]
        entry['vram_free_min_bytes_per_rank'] = [min((s['vram_free_bytes_per_rank'][r] for s in rows if s['vram_free_bytes_per_rank'][r] is not None), default=None) for r in range(4)]
        entry.update(sample_count=len(rows), duration_seconds=rows[-1]['monotonic']-rows[0]['monotonic'])
        result[phase] = entry
    return result


def verdict(samples, *, ready, clean_exit, watchdog_reason=None, failure=None):
    samples = sorted(samples, key=lambda s: s['monotonic'])
    phases = phase_peaks(samples)
    reasons = []
    if not ready: reasons.append('readiness not reached')
    if not clean_exit: reasons.append('clean container exit not verified')
    if watchdog_reason: reasons.append(watchdog_reason)
    if failure: reasons.append(failure)
    if any('error' in s for s in samples): reasons.append('sampling failed')
    if any(b['monotonic']-a['monotonic'] > 1.5 for a,b in zip(samples,samples[1:])):
        reasons.append('sampling gap exceeds 1.5 seconds')
    plateau = phases['plateau']
    projected = None
    if not plateau or plateau['duration_seconds'] < PLATEAU_SECONDS or plateau['sample_count'] < 40:
        reasons.append('20 second plateau missing')
    if plateau:
        projected = (plateau['accounted_pressure_bytes'] * 115 + 99) // 100
        if projected > HOST_LIMIT: reasons.append('plateau plus 15% exceeds 90 GB')
    active = [s for s in samples if s.get('phase') in ('loading', 'plateau')]
    if any(s.get('accounted_pressure_bytes', HOST_LIMIT+1) > HOST_LIMIT for s in active):
        reasons.append('observed loading/plateau host peak exceeds 90 GB')
    if any(trip_reason(s) for s in active if 'mem_available_bytes' in s):
        reasons.append('observed stop threshold breach')
    steady = [s for s in active if s.get('phase') == 'plateau']
    if not steady or any(s.get('accounting_errors') or s.get('cgroup_memory_current_bytes') is None or
                         any(x is None for x in s.get('worker_rss_bytes', [None]*4)) for s in steady):
        reasons.append('plateau worker/cgroup accounting incomplete')
    reserves = []
    for r in range(4):
        values = [s.get('vram_free_bytes_per_rank', [None]*4)[r] for s in active]
        if not values or any(x is None for x in values):
            reserves.append(None)
            reasons.append(f'rank {r} VRAM reserve unknown')
        else:
            reserve = min(values)
            reserves.append(reserve)
            if reserve < 4*GIB: reasons.append(f'rank {r} VRAM reserve below 4 GiB')
    return {'passed': not reasons, 'refusal_reasons': reasons, 'phase_peaks': phases,
            'plateau_plus_15_percent_bytes': projected, 'vram_reserve_bytes_per_rank': reserves}


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


LOADING_GUARD_ENV = 'B70_SCREEN1B_CALIBRATE_LOAD_RAM_GUARD_BYTES'


def loading_guard_bytes(command):
    for i, value in enumerate(command):
        if value == '-e' and command[i+1].startswith(LOADING_GUARD_ENV + '='):
            return int(command[i+1].split('=', 1)[1])
    return None


def identity(command, package, model):
    # Canonical run path/name/port so a fresh MTP1 run can use the receipt.
    cmd = list(map(str, command))
    # Loading cancellation policy differs only in measurement mode. Record it
    # separately in the receipt; keep the model/runtime identity comparable
    # to MTP1, whose measured plateau + 15% admission gate is unchanged.
    for i in range(len(cmd)-2, -1, -1):
        if cmd[i] == '-e' and cmd[i+1].startswith(LOADING_GUARD_ENV + '='):
            del cmd[i:i+2]
    for flag in ('--name', '--port'):
        cmd[cmd.index(flag)+1] = '<run>'
    for i, value in enumerate(cmd):
        if value.endswith(':/screen'):
            cmd[i] = '<run>:/screen'
    files = ['overlay-manifest.json', 'placement-certified-v5.json', 'container-entrypoint.sh',
             'screen.py', 'calibration.py', 'memory_watchdog.py']
    return {'command': cmd, 'package_sha256': {f: file_hash(package/f) for f in files},
            'model_sha256': {f: file_hash(model/f) for f in ('config.json', 'model.safetensors.index.json')}}


def enforce_receipt(path, expected_identity):
    path = Path(path)
    receipt = json.loads(path.read_text())
    if receipt.get('schema') != 'neural.download.screen1b-calibration-load.v1' or receipt.get('identity') != expected_identity:
        raise RuntimeError('Calibration identity mismatch')
    if receipt.get('generation_requests') != 0:
        raise RuntimeError('Calibration must send zero generation requests')
    samples_path = path.parent / 'host-memory-samples.jsonl'
    if file_hash(samples_path) != receipt['samples_sha256']:
        raise RuntimeError('Calibration samples hash mismatch')
    samples = [json.loads(line) for line in samples_path.read_text().splitlines()]
    result = verdict(samples, ready=receipt['ready'], clean_exit=receipt['clean_exit'],
                     watchdog_reason=receipt['watchdog_reason'], failure=receipt['failure'])
    if not result['passed']:
        raise RuntimeError('Calibration refused: ' + '; '.join(result['refusal_reasons']))
    return result

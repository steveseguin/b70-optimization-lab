"""Passive owned-process DRM occupancy; duplicate client FDs count once."""
from pathlib import Path
import re
from legacy_memory_plan import require


def parse_size(value):
    """Linux drm_fdinfo_print_size: bytes, KiB or MiB (never GiB)."""
    match = re.fullmatch(r"[ \t]*([0-9]+)(?: (KiB|MiB))?[ \t]*", value)
    require(match is not None, 'DRM occupancy malformed')
    size = int(match[1]) * {None: 1, 'KiB': 1024, 'MiB': 1024**2}[match[2]]
    require(size <= 2**64-1, 'DRM occupancy overflow')
    return size


def observe(processes, proc=Path('/proc')):
    clients={}
    for process in processes:
        try:
            paths=list((proc/str(process['pid'])/'fdinfo').iterdir())
        except (FileNotFoundError,ProcessLookupError):
            continue
        for path in paths:
            try:
                fields=dict(line.split(':',1) for line in path.read_text().splitlines() if ':' in line)
            except (FileNotFoundError,ProcessLookupError):
                continue
            if fields.get('drm-driver','').strip()!='xe':continue
            key=(fields.get('drm-pdev','').strip(),fields.get('drm-client-id','').strip())
            require(all(key),'DRM client identity missing')
            value=fields.get('drm-total-vram0')
            require(value is not None,'DRM occupancy missing for owned Xe client')
            clients[key]=max(clients.get(key,0),parse_size(value))
    total=sum(clients.values())
    return dict(bytes=total,clients=len(clients),reserve_bytes=1_500_000_000,
                physical_floor_bytes=32_000_000_000,passed=total<=30_500_000_000)

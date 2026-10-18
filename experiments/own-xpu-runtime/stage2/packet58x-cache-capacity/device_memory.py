"""Passive owned-process DRM occupancy; duplicate client FDs count once."""
from pathlib import Path
from legacy_memory_plan import require


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
            parts=value.split()
            require(len(parts)==2 and parts[1]=='KiB' and parts[0].isdigit(),'DRM occupancy malformed')
            clients[key]=max(clients.get(key,0),int(parts[0])*1024)
    total=sum(clients.values())
    return dict(bytes=total,clients=len(clients),reserve_bytes=1_500_000_000,
                physical_floor_bytes=32_000_000_000,passed=total<=30_500_000_000)

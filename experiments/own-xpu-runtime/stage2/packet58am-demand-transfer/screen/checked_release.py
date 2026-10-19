"""Admit only the hash-bound, coordinator-owned localization proposal."""
import json
import shutil
from pathlib import Path
from release_gate import P, REPO, sha, require, build_gate

def authorize_checked():
    ready=json.loads((P/'checked-READY.json').read_text())
    require(ready.get('ready_for_device') is True and ready.get('diagnostic_only') is True,
            'checked localization release missing')
    for name,digest in ready['files'].items():
        require(sha(REPO/name)==digest,'checked localization identity changed: '+name)
    build_gate()
    proposal=json.loads((P/'proposals/checked.json').read_text())
    require(not Path(proposal['output']).exists(),'checked output already used')
    queue=REPO/'experiments/own-xpu-runtime/ops/lane-queue'
    require((queue/'PAUSE-B').exists(),'coordinator whole-host PAUSE-B required')
    for lane in ('A','B'):
        for line in (queue/f'queue-{lane}.txt').read_text().splitlines():
            if line.strip() and not line.lstrip().startswith('#'):
                require(json.loads(line).get('name')==proposal['job_name'],'foreign queued job')
    available=next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
    require(available>=proposal['admission']['host_required_available_bytes'],'checked host reserve')
    require(shutil.disk_usage('/').free>=25_000_000_000+proposal['storage']['planned_outstanding_write_bytes'],'checked disk reserve')

#!/usr/bin/env python3
"""Rebuild historical calibration from rescued files; CPU reads only."""
import csv
import hashlib
import io
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
RESCUE = Path('/home/steve/git-archives/flash-next-rescue-20261007')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize_pressure(text):
    rows = list(csv.DictReader(io.StringIO(text), delimiter='\t'))
    values = [int(row['mem_available_kib'])*1024 for row in rows]
    if not values or min(values) < 0:
        raise ValueError('invalid/empty host-pressure trace')
    return {'samples': len(values), 'first_available_bytes': values[0],
            'minimum_available_bytes': min(values),
            'minimum_timestamp': rows[values.index(min(values))]['timestamp'],
            'last_available_bytes': values[-1],
            'pressure_increase_from_first_sample_bytes': values[0]-min(values),
            'whole_host_peak_lower_bound_bytes': values[0]-min(values),
            'definition': 'MemAvailable(first)-min(MemAvailable); whole-host change, not worker RSS. Absolute peak unknown without historical MemTotal.'}


def main():
    result = {'schema': 'screen1b.rescued-calibration.v1', 'rescue_root': str(RESCUE),
              'rescue_file_count': sum(p.is_file() for p in RESCUE.rglob('*')), 'runs': {}}
    for attempt in (367,394):
        supervisor = next(RESCUE.glob(f'*attempt{attempt}-supervisor'))
        run = Path(str(supervisor).removesuffix('-supervisor'))
        trace = supervisor/'host-pressure.tsv'
        dest = HERE/'evidence'/f'a{attempt}-host-pressure.tsv'
        dest.write_bytes(trace.read_bytes())
        row = summarize_pressure(trace.read_text())
        row.update(source=str(trace),source_sha256=digest(trace),local_copy=str(dest.relative_to(HERE)),
                   worker_rss_bytes=[None]*4,measured_pinned_bytes=None,
                   loaded_model_reported_gib_per_rank=[None]*4,
                   complete_vram_peak_bytes_per_rank=[None]*4)
        log = run/'server.log'
        row['server_log_sha256']=digest(log)
        row['allocation_log_lines']=[]
        for line in log.read_text().splitlines():
            m = re.search(r'Worker_TP([0-3]).*Model loading took ([\d.]+) GiB memory',line)
            if m:
                row['loaded_model_reported_gib_per_rank'][int(m[1])]=float(m[2])
                row['allocation_log_lines'].append(line)
        row['allocation_scope']='rounded runtime allocation delta; excludes complete KV/graph/driver peak'
        row['idle_vram_snapshots']={}
        for directory in (run,supervisor):
            for path in sorted(directory.glob('xpu-stats-*.json')):
                j=json.loads(path.read_text())
                metrics={x['metrics_type']:x['value'] for x in j['device_level']}
                row['idle_vram_snapshots'][str(path)]={'sha256':digest(path),
                    'memory_used_reported':metrics.get('XPUM_STATS_MEMORY_USED'),
                    'memory_utilization_percent':metrics.get('XPUM_STATS_MEMORY_UTILIZATION')}
        row['same_certified_4352_configuration']=attempt==367
        result['runs'][f'A{attempt}']=row
    result['verdict']={'historical_host_calibration':'PARTIAL_MEASURED_PRESSURE_CHANGE',
        'v30_admitted':False,'reason':'A367 host peak lower bound exceeds 90 GB; old runtime does not calibrate V30 lifetimes. Complete live VRAM reserve and worker RSS unavailable. A394 is a different context/placement.'}
    (HERE/'rescued-calibration.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result['verdict'],indent=2))


if __name__=='__main__': main()

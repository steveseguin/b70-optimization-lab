#!/usr/bin/env python3
"""Summarize copy/compute microbenchmarks; never calls a device."""
import argparse
import json
import math
from pathlib import Path
import statistics


def summarize(root):
    root = Path(root)
    receipt = json.loads((root / 'receipt.json').read_text())
    if receipt.get('passed') is not True or receipt.get('safe_to_exit') is not True:
        raise ValueError('native run incomplete or unsafe')
    rows = [json.loads(line) for line in (root / 'iterations.jsonl').read_text().splitlines()]
    if receipt.get('rows') != len(rows) or len(rows) != 2 * 7 * 2 * 33 * 3:
        raise ValueError('incomplete benchmark grid')
    expected = {(slab, batch, shape, iteration, mode) for slab in (1971200, 2329600) for batch in range(4, 11)
                for shape in ('contiguous_batch', 'slab_commands') for iteration in range(-3, 30)
                for mode in ('copy', 'compute', 'concurrent')}
    keys = [(r['slab_bytes'], r['batch'], r['copy_shape'], r['iteration'], r['mode']) for r in rows]
    if set(keys) != expected or len(set(keys)) != len(keys):
        raise ValueError('missing or duplicate iteration')
    if not all(r['payload_verified'] is True and r['wall_ns'] > 0 for r in rows):
        raise ValueError('verification or timer failure')
    for row in rows:
        if row['warmup'] != (row['iteration'] < 0):
            raise ValueError('warmup labeling changed')
        for field in ('wall_ns', 'copy_device_envelope_ns', 'compute_event_ns', 'route_to_resident_ns'):
            if not math.isfinite(row[field]) or row[field] < 0:
                raise ValueError('nonfinite or negative timing')
        if row['mode'] != 'compute' and (row['copy_device_envelope_ns'] <= 0 or row['route_to_resident_ns'] <= 0):
            raise ValueError('missing copy duration')
        if row['mode'] != 'copy' and row['compute_event_ns'] <= 0:
            raise ValueError('missing compute duration')
    result = []
    for slab in (1971200, 2329600):
        for batch in range(4, 11):
            for shape in ('contiguous_batch', 'slab_commands'):
                group = [r for r in rows if r['slab_bytes'] == slab and r['batch'] == batch and r['copy_shape'] == shape and not r['warmup']]
                def median(mode, key):
                    return statistics.median(r[key] for r in group if r['mode'] == mode)
                copy, compute, both = [median(m, 'wall_ns') for m in ('copy', 'compute', 'concurrent')]
                byte_count = batch * slab
                result.append(dict(slab_bytes=slab, batch=batch, copy_shape=shape, bytes=byte_count,
                    copy_wall_us=copy / 1000, compute_wall_us=compute / 1000,
                    concurrent_wall_us=both / 1000,
                    copy_device_envelope_us=median('copy', 'copy_device_envelope_ns') / 1000,
                    concurrent_copy_device_envelope_us=median('concurrent', 'copy_device_envelope_ns') / 1000,
                    copy_wall_GB_s=byte_count / copy,
                    copy_device_envelope_GB_s=byte_count / median('copy', 'copy_device_envelope_ns'),
                    concurrent_copy_device_envelope_GB_s=byte_count / median('concurrent', 'copy_device_envelope_ns'),
                    copy_route_to_resident_us=median('copy', 'route_to_resident_ns') / 1000,
                    concurrent_route_to_resident_us=median('concurrent', 'route_to_resident_ns') / 1000,
                    compute_event_us=median('compute', 'compute_event_ns') / 1000,
                    concurrent_compute_event_us=median('concurrent', 'compute_event_ns') / 1000,
                    effective_overlap_fraction=(copy + compute - both) / min(copy, compute),
                    envelope_overlap_lower_bound_us=statistics.median(max(0, r['copy_device_envelope_ns'] + r['compute_event_ns'] - r['wall_ns']) / 1000 for r in group if r['mode'] == 'concurrent')))
    return dict(schema='ownrt.packet55.h2d.summary.v1', model_speed_claim=False,
                device_metadata=json.loads((root / 'metadata.json').read_text()), rows=result,
                interpretation='Effective overlap is a wall-time diagnostic, not a shared-clock trace. Negative means slowdown; values above one expose timing variation. No clipping. Synthetic compute is not the model expert workload.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    a.output.write_text(json.dumps(summarize(a.run), indent=2) + '\n')

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Read closed p201 evidence; emit a static inventory, never a speed estimate."""
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def main():
    here = Path(__file__).resolve().parent
    root = here.parents[3]
    owner = here.parent / 'packet201-streaming-serving/evidence/planned-a/output/owner'
    pins = {}

    def read(path):
        raw = path.read_bytes()
        pins[str(path.relative_to(root))] = hashlib.sha256(raw).hexdigest()
        return raw

    plan = json.loads(read(owner / 'plan.json'))
    census = json.loads(read(owner / 'census.json'))
    grouped = defaultdict(lambda: {'count': 0, 'logical_bytes': 0, 'stored_bytes': 0})
    for tensor in plan['tensor_owners']:
        row = grouped[(tensor['component'], tensor['card'])]
        row['count'] += 1
        row['logical_bytes'] += tensor['bytes']
        row['stored_bytes'] += tensor.get('stored_bytes', tensor['bytes'])
    allocations = defaultdict(int)
    for card in census:
        for allocation in card['allocations']:
            assert allocation['live']
            allocations[(allocation['category'], allocation['memory'])] += allocation['bytes']
    cache = [json.loads(line) for line in read(owner / 'cache.jsonl').splitlines()]
    fresh = owner / 'requests/he80a7bb9e7c9417c8c4e3dce2ba64229-0000000000000004'
    timing = [json.loads(line) for line in read(fresh / 'prefill-timings.jsonl').splitlines()]
    sites = read(fresh / 'sites.jsonl')
    assert len(timing) == 369 and not sites
    assert all(row['kernel_submissions'] == 1110 and row['host_waits'] == 6 for row in timing)
    selected = [tensor for tensor in plan['tensor_owners'] if tensor['name'] in {
        'blk.0.attn_qkv.weight', 'blk.0.attn_gate.weight', 'blk.0.ssm_out.weight'}]
    assert len(selected) == 3
    pins[str(Path(__file__).resolve().relative_to(root))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result = {
        'schema': 'packet202.static-prefill-planning-census.v1',
        'scope': 'Closed evidence only; inventory and recorded counters, not traffic, device time or candidate speed.',
        'source_sha256': pins,
        'tensor_inventory': [dict(component=k[0], card=k[1], **v) for k, v in sorted(grouped.items())],
        'allocation_inventory': [dict(category=k[0], memory=k[1], bytes=v) for k, v in sorted(allocations.items())],
        'layer0_q6_storage': selected,
        'fresh_370_nonfinal_prefill': {
            'positions': len(timing),
            'kernel_submissions_per_position': 1110,
            'host_waits_per_position': 6,
            'host_to_device_copies_per_position': sorted({r['copy_counts'][0]['host_to_device'] for r in timing}),
            'device_to_host_copies_per_position': sorted({r['copy_counts'][0]['device_to_host'] for r in timing}),
            'gemv_device_ms_all_zero': all(r['gemv_device_ms'] == 0 for r in timing),
            'non_gemv_device_ms_all_zero': all(r['non_gemv_device_ms'] == 0 for r in timing),
            'enqueue_family_ms_all_null': all(r['enqueue_family_ms'] is None for r in timing),
            'sites_trace_bytes': len(sites),
        },
        'cache_trace_rows': len(cache),
        'cache_trace_fields': sorted({key for row in cache for key in row}),
        'limitations': [
            'Tensor storage bytes are not measured bytes read; cache, transaction and reuse effects are unmeasured.',
            'Launch census is a logical plan; fused selected submission counts come from the actual timing trace.',
            'Zero device timing fields and empty site traces mean unmeasured, not zero work.',
            'Aggregate cache counters contain no per-layer route IDs; adjacent-row expert overlap is unknown.',
            'Current workspace totals do not price the extra row or prove an alias-safe allocation plan.',
            'No changed runtime, weights, native execution or device work is performed by this script.',
        ],
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()

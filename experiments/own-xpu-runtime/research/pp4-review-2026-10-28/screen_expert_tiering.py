#!/usr/bin/env python3
"""CPU-only optimistic static expert-cache screen on retained production routes."""
import collections
import hashlib
import json
import statistics
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    authority = json.loads((HERE / 'expert-parallel-screen.json').read_text())['measured_inputs']
    source = Path(authority['route_dump'])
    raw = source.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == authority['route_sha256']
    offset = 0
    routes = collections.defaultdict(list)
    while offset < len(raw):
        length, = struct.unpack_from('<I', raw, offset)
        offset += 4
        label = raw[offset:offset + length].decode()
        offset += length
        _, count = struct.unpack_from('<II', raw, offset)
        offset += 8
        values = list(struct.iter_unpack('<III', raw[offset:offset + 12 * count]))
        offset += 12 * count
        if label.endswith('expsdown'):
            routes[int(label.split('.')[1])].extend(v[0] for v in values)
    assert offset == len(raw) and sorted(routes) == authority['route_layers']
    per_layer = []
    for layer, ids in sorted(routes.items()):
        assert len(ids) == 4096 * 10 and all(0 <= x < 512 for x in ids)
        chunks = [set(ids[i:i + 2560]) for i in range(0, len(ids), 2560)]
        appearances = collections.Counter(x for chunk in chunks for x in chunk)
        # Hindsight-optimal fixed cache: minimize chunk transfers, not token misses.
        order = sorted(range(512), key=lambda x: (-appearances[x], x))
        weights = authority['routed_weight_bytes_per_layer'][str(layer)]
        assert weights % 512 == 0
        expert_bytes = weights // 512
        treatments = []
        for capacity in (128, 256, 384, 410, 448, 480, 512):
            resident = set(order[:capacity])
            misses = [len(chunk - resident) for chunk in chunks]
            treatments.append(dict(capacity=capacity,
                resident_weight_bytes=capacity * expert_bytes,
                freed_weight_bytes=(512 - capacity) * expert_bytes,
                missing_expert_chunk_pairs=sum(misses),
                maximum_missing_experts_in_chunk=max(misses),
                transfer_bytes=sum(misses) * expert_bytes))
        per_layer.append(dict(layer=layer, expert_bytes=expert_bytes,
            distinct_per_chunk=[len(x) for x in chunks], treatments=treatments))
    aggregate = []
    for index in range(len(per_layer[0]['treatments'])):
        rows = [x['treatments'][index] for x in per_layer]
        traffic = sum(x['transfer_bytes'] for x in rows)
        aggregate.append(dict(capacity=rows[0]['capacity'],
            observed_24_layers_freed_weight_bytes=sum(x['freed_weight_bytes'] for x in rows),
            observed_24_layers_4096_tokens_transfer_bytes=traffic,
            observed_missing_expert_chunk_pairs=sum(x['missing_expert_chunk_pairs'] for x in rows),
            conditional_48_layers_121852_tokens_transfer_bytes=traffic * 2 * 121852 / 4096,
            conditional_transfer_seconds_at_aggregate_GBps={str(b): traffic * 2 * 121852 / 4096 / (b * 1e9) for b in (8, 16, 32, 64)}))
    result = dict(schema='ownrt.static-expert-tiering-cpu-screen.v1',
        source=str(source), source_sha256=authority['route_sha256'],
        allocation_authority=str(HERE / 'expert-parallel-screen.json'),
        allocation_authority_sha256=hashlib.sha256((HERE / 'expert-parallel-screen.json').read_bytes()).hexdigest(),
        layers=sorted(routes), tokens_per_layer=4096, chunk_rows=256,
        distinct_experts_per_chunk_mean=statistics.mean(n for x in per_layer for n in x['distinct_per_chunk']),
        policy='Hindsight-optimal fixed per-layer cache; each missing expert transferred once per chunk and discarded afterward. No live policy or GPU implementation.',
        limits=['Uses archived 4096-token layers24..47, not measured121K locality.',
                'Assumes all gate/up/down bytes move together and ignores metadata, staging, latency and transfer/compute overlap.',
                'Transfer sensitivity is not a throughput prediction or a measured bandwidth.',
                'Cache capacity alone does not establish whole-engine VRAM fit; transient expert buffers and all other allocations remain required.',
                'This optimistic fixed-cache screen does not reject adaptive caches, remote expert execution, or other route distributions.'],
        aggregate=aggregate, per_layer=per_layer,
        next_step='Keep resident experts for speed baseline. Consider tiering only against a concrete context capacity deficit, with held-out route locality, staging allocation fit and an actual exact transfer/compute gate.')
    (HERE / 'expert-tiering-screen.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(distinct_mean=result['distinct_experts_per_chunk_mean'], aggregate=aggregate), indent=2))


if __name__ == '__main__':
    main()

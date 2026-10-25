#!/usr/bin/env python3
"""Inspect loader metadata and propose contiguous pipeline layer partitions; never launch."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def parse_placement(data):
    """Read the existing loader TSV, without opening model shards or accepting old masks.

    Quant IDs remain metadata: parsing a new ID does not qualify its decoder.
    This validates structural extents, not the format-specific encoded byte count.
    """
    tensors, names, intervals = [], set(), {}
    for line_number, line in enumerate(data.decode('utf-8').splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split()
        require(len(fields) >= 10, f'line {line_number}: incomplete placement')
        shard, name, component = fields[:3]
        kind, offset, size, layer, mask, ndim = map(int, fields[3:9])
        dims = list(map(int, fields[9:]))
        require(name not in names, f'duplicate tensor: {name}')
        require(kind >= 0 and offset >= 0 and size > 0 and layer >= -1 and mask >= 0,
                f'invalid extent/identity: {name}')
        require(ndim > 0 and len(dims) == ndim and all(d > 0 for d in dims),
                f'invalid dimensions: {name}')
        match = re.match(r'^blk\.(\d+)\.', name)
        if match:
            require(layer == int(match[1]), f'layer/name mismatch: {name}')
        names.add(name)
        intervals.setdefault(shard, []).append((offset, offset + size, name))
        tensors.append(dict(name=name, component=component, type_id=kind, bytes=size,
                            layer=layer, dimensions=dims))
    require(tensors, 'empty placement')
    for ranges in intervals.values():
        ranges.sort()
        for previous, current in zip(ranges, ranges[1:]):
            require(previous[1] <= current[0], f'overlapping tensor extents: {previous[2]}, {current[2]}')
    layers = sorted({t['layer'] for t in tensors if t['layer'] >= 0})
    require(layers == list(range(len(layers))) and layers, 'layers must be contiguous from zero')
    return tensors


def partition(costs, stages, overhead=None):
    """Exact minimax partition into nonempty contiguous stages (deterministic ties)."""
    require(type(stages) is int and 1 <= stages <= len(costs), 'stages must be between one and layer count')
    require(all(type(x) is int and x >= 0 for x in costs), 'layer costs must be nonnegative integers')
    overhead = [0] * stages if overhead is None else overhead
    require(len(overhead) == stages and all(type(x) is int and x >= 0 for x in overhead),
            'one nonnegative overhead per stage required')
    prefix = [0]
    for value in costs:
        prefix.append(prefix[-1] + value)
    previous = {0: (0, [])}
    for stage in range(stages):
        current = {}
        for end in range(stage + 1, len(costs) + 1):
            candidates = []
            for start, (maximum, cuts) in previous.items():
                if start < end:
                    candidates.append((max(maximum, prefix[end] - prefix[start] + overhead[stage]),
                                       cuts + [end]))
            if candidates:
                current[end] = min(candidates)
        previous = current
    maximum, cuts = previous[len(costs)]
    starts = [0] + cuts[:-1]
    return maximum, list(zip(starts, cuts))


def load_cost_profile(data, placement_sha, layers):
    profile = json.loads(data)
    require(profile.get('schema') == 'ownrt.pipeline.layer-costs.v1', 'cost profile schema')
    require(profile.get('placement_sha256') == placement_sha, 'cost profile placement hash mismatch')
    for key in ('runtime_sha256', 'measurement_sha256'):
        require(isinstance(profile.get(key), str) and re.fullmatch('[0-9a-f]{64}', profile[key]),
                f'cost profile requires {key}')
    require(isinstance(profile.get('run_identity'), dict) and profile['run_identity'], 'cost profile run identity required')
    costs = profile.get('layer_ns')
    require(isinstance(costs, list) and len(costs) == layers and all(type(x) is int and x >= 0 for x in costs),
            'cost profile must cover every layer with integer nanoseconds')
    require(isinstance(profile.get('stage_overhead_ns', {}), dict), 'stage overhead must be keyed by stage count')
    return profile


def summarize(tensors):
    types = {}
    for tensor in tensors:
        entry = types.setdefault(str(tensor['type_id']), dict(tensors=0, packed_bytes=0))
        entry['tensors'] += 1
        entry['packed_bytes'] += tensor['bytes']
    return dict(tensors=len(tensors), packed_bytes=sum(t['bytes'] for t in tensors),
                quantization_types=dict(sorted(types.items(), key=lambda item: int(item[0]))))


def plan(data, model_id, gpu_counts, cost_data=None):
    require(isinstance(model_id, str) and model_id.strip(), 'model label required')
    require(gpu_counts and len(set(gpu_counts)) == len(gpu_counts), 'distinct GPU counts required')
    tensors = parse_placement(data)
    layers = max(t['layer'] for t in tensors) + 1
    # Lookup tables are CPU resident in this lane; do not accidentally assign the
    # 28.8 GB PLE table to layer 1's GPU because its metadata names layer 1.
    lookups = [t for t in tensors if t['component'] in ('embedding', 'ple_lookup')]
    globals_ = [t for t in tensors if t['layer'] == -1 and t not in lookups]
    body = [t for t in tensors if t not in lookups and t not in globals_]
    layer_rows = [[t for t in body if t['layer'] == i] for i in range(layers)]
    require(all(layer_rows), 'each layer must contain non-lookup weights')
    digest = sha(data)
    profile = load_cost_profile(cost_data, digest, layers) if cost_data is not None else None
    costs = profile['layer_ns'] if profile else [summarize(rows)['packed_bytes'] for rows in layer_rows]
    proposals = []
    for count in gpu_counts:
        overhead = profile.get('stage_overhead_ns', {}).get(str(count)) if profile else None
        maximum, ranges = partition(costs, count, overhead)
        stages = []
        for rank, (first, end) in enumerate(ranges):
            rows = [t for group in layer_rows[first:end] for t in group]
            stages.append(dict(rank=rank, layer_start=first, layer_end_exclusive=end,
                               objective_cost=sum(costs[first:end]) + (overhead[rank] if overhead else 0),
                               supplied_overhead=overhead[rank] if overhead else 0, **summarize(rows)))
        proposals.append(dict(gpus=count, layout='one_pipeline_stage_per_gpu', maximum_stage_cost=maximum,
                              overhead_status='supplied' if overhead is not None else 'excluded', stages=stages))
    return dict(schema='ownrt.pipeline.partition-proposals.v1', model_label=model_id,
                placement_sha256=digest, cost_profile_sha256=sha(cost_data) if cost_data is not None else None,
                cost_profile=profile, planner_sha256=sha(Path(__file__).read_bytes()),
                scope='metadata-only planning; no runtime admission, memory-fit or speed claim',
                executable=False, objective='measured_layer_ns' if profile else 'packed_layer_weight_bytes',
                input_inventory=summarize(tensors), layer_inventory=summarize(body),
                excluded_lookup_tensors=lookups, excluded_global_tensors=globals_,
                excluded_costs=['activation/KV/recurrent buffers', 'scratch', 'expanded/converted weights',
                                'draft weights and work (unless stage cost supplied)', 'communication and pipeline bubbles',
                                'runtime allocation overhead and host RAM shadow'],
                qualifications=['Placement hash binds metadata, not weight payload authenticity.',
                                'Existing placement masks are historical; they are not execution authority.',
                                'Quant IDs are inventoried, not decoder support claims.',
                                'Layer timings require matched model/runtime/arithmetic/workload identity.',
                                'Supported proposal counts do not imply the engine can execute those counts.'],
                proposals=proposals)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--placement', type=Path, required=True)
    parser.add_argument('--model-id', required=True)
    parser.add_argument('--gpus', type=int, nargs='+', default=[1, 2, 4, 6])
    parser.add_argument('--cost-profile', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = plan(args.placement.read_bytes(), args.model_id, args.gpus,
                  args.cost_profile.read_bytes() if args.cost_profile else None)
    with args.output.open('x') as output:
        json.dump(result, output, indent=2, ensure_ascii=False, allow_nan=False)
        output.write('\n')


if __name__ == '__main__':
    main()

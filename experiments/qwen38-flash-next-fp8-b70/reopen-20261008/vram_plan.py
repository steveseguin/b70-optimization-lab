"""CPU-only attempt-6 planning; allowances are not measured phase bounds."""
import hashlib
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
GIB = 1 << 30
EXPERT_BYTES = 3 * 2560 * 640
PLACEMENT = 'placement-attempt6-v5.json'


def weight_census(tensors, mtp=True):
    """Replicate uncertain tensors; shard only source-proven weight shapes."""
    groups = defaultdict(int)
    for name, tensor in tensors.items():
        if ('ngram_embedding' in name or any(s in name for s in ('hashstats_', 'token_lookup'))
                or (not mtp and name.startswith('mtp.'))):
            continue
        size, group = tensor['bytes'], 'replicated_all_other'
        if '.experts.' in name and name.endswith('.weight'):
            size //= 4
            group = 'expert'
        elif ('embed_tokens' in name or 'lm_head' in name) and name.endswith('.weight'):
            size //= 4
            group = 'embed_head'
        elif any(s in name for s in ('linear_attn.in_proj_qkv.weight', 'linear_attn.in_proj_z.weight',
                                    'linear_attn.out_proj.weight', 'self_attn.q_proj.weight', 'self_attn.o_proj.weight')):
            size //= 4
            group = 'tp_attention'
        elif any(s in name for s in ('self_attn.k_proj.weight', 'self_attn.v_proj.weight')):
            size //= 2
            group = 'replicated_kv'
        groups[group] += size
    return dict(groups)


def expanded_placement(original, census, goal=2600):
    """Keep every old host row; add lowest-count pairs, retaining a device row.

    Routing frequencies select storage only. Every expert remains callable;
    the old workload does not predict V30's routing or prove an expert cold.
    """
    result, receipt = {}, []
    for rank in range(4):
        previous = {(int(layer), e) for layer, rows in original[str(rank)].items() for e in rows}
        selected = set(previous)
        counts = census[rank]
        if set(counts) != {str(i) for i in range(48)}:
            raise ValueError('incomplete routing census')
        candidates = sorted((counts[str(layer)]['counts'].get(str(e), 0), layer, e)
                            for layer in range(48) for e in range(128)
                            if (layer, e) not in selected)
        occupancy = [sum(l == layer for l, e in selected) for layer in range(48)]
        for count, layer, e in candidates:
            if len(selected) >= goal:
                break
            if occupancy[layer] < 127:
                selected.add((layer, e))
                occupancy[layer] += 1
        if len(selected) != goal or goal < len(previous):
            raise ValueError('infeasible expert row goal')
        result[str(rank)] = {str(layer): sorted(e for l, e in selected if l == layer)
                             for layer in range(48)}
        added_hits = sum(counts[str(l)]['counts'].get(str(e), 0) for l, e in selected - previous)
        receipt.append(dict(rank=rank, old_rows=len(previous), host_rows=len(selected),
                            expert_offload_bytes=len(selected)*EXPERT_BYTES,
                            additional_offload_bytes=(len(selected)-len(previous))*EXPERT_BYTES,
                            additional_historical_routed_selections=added_hits,
                            historical_routed_selections=sum(sum(v['counts'].values()) for v in counts.values()),
                            min_resident_rows_per_layer=128-max(occupancy)))
    return result, receipt


def scenario(floors, spec, identity):
    """floors already include full KV and the mmap device stage exactly once."""
    if (identity['max_model_len'], identity['max_num_batched_tokens'], identity['max_num_seqs']) != (4352, 64, 1):
        raise ValueError('VRAM scenario requires context4352, chunk64, one sequence')
    expected_capture = {0: [1], 1: [1, 2], 3: [1, 4]}[identity['mtp_depth']]
    if identity['compilation'].get('cudagraph_capture_sizes') != expected_capture:
        raise ValueError('VRAM scenario capture sizes differ from registered mode')
    overhead = sum(spec['allowance_bytes'].values())
    # Logs round to 0.01 GiB: use lower edge for both capacity and free memory.
    total = int(spec['reported_total_gib_lower_edge'] * GIB)
    budget = int(total * 90 // 100)
    rows = []
    for rank, floor in enumerate(floors):
        free = int(spec['reported_free_gib_lower_edges'][rank] * GIB)
        peak = floor + overhead
        rows.append(dict(rank=rank, resident_weight_floor_bytes=floor-identity['kv_bytes_per_rank']-163840,
                         kv_bytes=identity['kv_bytes_per_rank'], ple_device_step_bytes=163840,
                         **spec['allowance_bytes'], engine_peak_bytes=peak,
                         startup_unavailable_bytes=total-free,
                         total_used_peak_bytes=total-free+peak,
                         utilization_budget_bytes=budget,
                         utilization_headroom_bytes=budget-peak,
                         total_used_utilization_headroom_bytes=budget-(total-free+peak),
                         predicted_free_bytes=free-peak))
    return dict(qualified=False, prediction_is_measurement=False,
                scope='MTP1/calibrate-load planning; MTP0/MTP3 not qualified by this scenario',
                applicable=identity['mtp_depth'] == 1, ranks=rows,
                minimum_utilization_headroom_bytes=min(r['utilization_headroom_bytes'] for r in rows),
                minimum_total_used_utilization_headroom_bytes=min(r['total_used_utilization_headroom_bytes'] for r in rows),
                minimum_predicted_free_bytes=min(r['predicted_free_bytes'] for r in rows),
                assumptions=spec)


def generate():
    original = json.loads((HERE/'placement-certified-v5.json').read_text())
    paths = [HERE.parent/f'data/20260907-tp4-mtp1-a315-routing-census-rank{r}.json' for r in range(4)]
    placement, rows = expanded_placement(original, [json.loads(p.read_text()) for p in paths])
    (HERE/PLACEMENT).write_text(json.dumps(placement, indent=2, ensure_ascii=False)+'\n')
    receipt = dict(schema='screen1b.attempt6-placement.v1', algorithm='preserve certified rows, then (count, layer, expert) ascending; retain >=1 device row/layer',
                   goal_rows_per_rank=2600, expert_row_bytes=EXPERT_BYTES, ranks=rows,
                   input_sha256={str(p.relative_to(HERE.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in [HERE/'placement-certified-v5.json', *paths]},
                   placement_sha256=hashlib.sha256((HERE/PLACEMENT).read_bytes()).hexdigest(),
                   decode_cost=dict(assumed_ms_per_extra_selected_expert=0.1,
                                    measured_for_this_placement=False,
                                    formula='extra selected host expert hits on the critical path * 0.1 ms; not allocated rows * 0.1 ms',
                                    caveat='old census frequencies are not a decode-step denominator or a V30 workload prediction'))
    (HERE/'evidence/attempt6-placement.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False)+'\n')


if __name__ == '__main__':
    generate()

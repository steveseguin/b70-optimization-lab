#!/usr/bin/env python3
"""Packet58 metadata-only allocation/admission. Never opens model payloads/devices."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
GIB = 1024**3
CACHE_BYTES = 18_000_000_000
HOST_RESERVE = 8 * GIB
DEVICE_RESERVE = 1_500_000_000
CENSUS = REPO / 'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def census_inventory(path=CENSUS):
    source = json.loads(Path(path).read_text())
    rows = source['tensors']
    require(sum(r['bytes'] for r in rows) == source['tensor_bytes'], 'tensor census total changed')
    experts = [r for r in rows if r['component'] == 'routed_experts']
    require(len(experts) == 144, '48 complete expert layers required')
    per_layer = []
    for layer in range(48):
        tensors = [r for r in experts if r['layer'] == layer]
        require(len(tensors) == 3 and all(r['bytes'] % 512 == 0 for r in tensors), 'expert shape changed')
        n = sum(r['bytes'] for r in tensors) // 512
        require(n == (2_329_600 if layer == 2 else 1_971_200), 'expert packed bytes changed')
        per_layer.append(dict(layer=layer, experts=512, expert_bytes=n, layer_bytes=n * 512))
    return dict(pinned_expert_bytes=sum(r['bytes'] for r in experts), layers=per_layer,
                file_backed_nonexpert_bytes=sum(r['bytes'] for r in rows if r['component'] != 'routed_experts'),
                source_path=str(path.relative_to(REPO)), source_sha256=sha(path))


def allocation_inventory():
    paths = [HERE.parent / 'packet45-merged3/evidence/audit6' / f'W2m-c4096-dr1-r{rank}/census.json' for rank in (0, 1)]
    allocations = [a for p in paths for a in json.loads(p.read_text())['allocations']]
    target = [a for a in allocations if ':draft:' not in a['label']]
    weights = sum(a['bytes'] for a in target if a['category'] == 'weights' and 'exps.' not in a['label']) - 4_194_304
    state = sum(a['bytes'] for a in target if a['category'] == 'recurrent-state' and ':alternate:' not in a['label'])
    kv = sum(a['bytes'] for a in target if a['category'] == 'KV')
    require(weights == 5_815_529_984 and state == 59_019_280 and kv == 116_391_936, 'allocation census changed')
    return dict(target_nonexpert_bytes=weights, recurrent_bytes=state, kv_index_bytes=kv,
                sources={str(p.relative_to(REPO)): sha(p) for p in paths})


def plan():
    census, inv = census_inventory(), allocation_inventory()
    device = dict(target_nonexpert=inv['target_nonexpert_bytes'], expert_cache_arena=CACHE_BYTES,
                  expert_pointer_generation_tables=2 * 3 * 48 * 512 * 16,
                  target_recurrent=inv['recurrent_bytes'], target_4k_bf16_kv_index=inv['kv_index_bytes'],
                  workspace_bound=GIB, control_transaction_bound=GIB, transfer_bound=256 * 1024**2)
    total = sum(device.values())
    host = dict(pinned_packed_experts=census['pinned_expert_bytes'],
                gpuactive_shadow_bound=total, file_backed_nonexpert_and_lookup_bound=census['file_backed_nonexpert_bytes'],
                loader_staging_bound=256 * 1024**2, process_workspace_bound=GIB,
                cache_metadata_bound=16 * 1024**2)
    required = sum(host.values()) + HOST_RESERVE
    return dict(schema='own-runtime.packet58.memory.v1', device_executed=False, admitted=False,
                context=4096, gpu_count=1, decode_mode='plain', kv_dtype='BF16',
                census=census, allocation_inventory=inv, device_categories=device,
                device_owned_bound_bytes=total, arena_limit_bytes=30 * GIB,
                card_capacity_floor_bytes=32_000_000_000, device_reserve_bytes=DEVICE_RESERVE,
                device_margin_bytes=32_000_000_000 - total - DEVICE_RESERVE,
                host_categories=host, host_reserve_bytes=HOST_RESERVE,
                host_required_available_bytes=required,
                file_backed_expert_duplicate_allowed=False, large_pinning_cpu_test_allowed=False,
                caveat='Bounds must be checked against native allocation census; not a measured fit. Single-card contexts normally avoid GPUActive shadow; full shadow is reserved anyway.')


def meminfo(path=Path('/proc/meminfo')):
    fields = {}
    for line in path.read_text().splitlines():
        key, value = line.split(':', 1)
        if key in ('MemAvailable', 'MemTotal', 'SwapFree', 'SwapTotal', 'GPUActive'):
            fields[key] = int(value.split()[0]) * 1024
    require('MemAvailable' in fields, 'MemAvailable sensor missing')
    return fields


def admit(snapshot, budget=None):
    budget = plan() if budget is None else budget
    required = budget['host_required_available_bytes']
    available = snapshot['MemAvailable']
    require(budget['device_owned_bound_bytes'] <= budget['arena_limit_bytes'] and budget['device_margin_bytes'] >= 0, 'device bound does not fit')
    require(available >= required, f'host admission refused: available {available}, required {required}, shortage {required - available}; no pin or model load')
    return dict(passed=True, available_bytes=available, required_bytes=required,
                margin_bytes=available-required, baseline_gpuactive_bytes=snapshot.get('GPUActive', 0),
                snapshot=snapshot, plan=budget)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admit-current-host', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    row = admit(meminfo()) if args.admit_current_host else plan()
    text = json.dumps(row, indent=2) + '\n'
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end='')

if __name__ == '__main__':
    main()

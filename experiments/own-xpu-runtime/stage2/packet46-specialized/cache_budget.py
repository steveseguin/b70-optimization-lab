#!/usr/bin/env python3
"""Metadata-only one-card capacity model; never opens weight payloads or devices."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
GIB = 1024**3
ORDINARY = 2 * 640 * 820 + 2560 * 360
EXCEPTION = 2 * 640 * 1100 + 2560 * 360
CACHE_LIMIT = 18_000_000_000


def align(value, alignment=4096):
    return (value + alignment - 1) // alignment * alignment


def packed_bytes(layer):
    return EXCEPTION if layer == 2 else ORDINARY


def inventory():
    paths = [STAGE / 'packet45-merged3/evidence/audit6' /
             f'W2m-c4096-dr1-r{rank}/census.json' for rank in (0, 1)]
    allocations = [item for p in paths for item in json.loads(p.read_text())['allocations']]
    target = [a for a in allocations if ':draft:' not in a['label']]
    nonexpert = sum(a['bytes'] for a in target if a['category'] == 'weights'
                    and 'exps.' not in a['label']) - 4_194_304
    recurrent = sum(a['bytes'] for a in target if a['category'] == 'recurrent-state'
                    and ':alternate:' not in a['label'])
    kv = sum(a['bytes'] for a in target if a['category'] == 'KV')
    draft_path = paths[1].parent / 'draft-memory.json'
    draft = json.loads(draft_path.read_text())['device_allocation_bytes']
    return dict(target_nonexpert=nonexpert, target_recurrent=recurrent,
                target_kv_index=kv, complete_draft=draft,
                source_sha256={str(p.relative_to(STAGE.parent.parent.parent)):
                               hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in [*paths, draft_path]})


def placement(limit=CACHE_LIMIT):
    # No hotness trace: equal coverage first, then ascending ordinary layer ID.
    # Metadata is a design ABI allowance: slot owner/generation/offset/refcount
    # and hash identity 64 B; direct lookup 4 B/expert; layer directory 64 B.
    fixed_metadata = align(48 * 512 * 4 + 48 * 64)
    quotas = [189] * 48

    def sizes():
        slots = sum(quotas)
        allocation = sum(q * align(packed_bytes(layer)) for layer, q in enumerate(quotas))
        metadata = fixed_metadata + align(slots * 64)
        payload = sum(q * packed_bytes(layer) for layer, q in enumerate(quotas))
        return allocation, metadata, payload

    if sum(sizes()[:2]) > limit:
        raise ValueError('cache limit cannot hold preregistered equal-coverage floor')
    for layer in range(48):
        if layer == 2:
            continue
        quotas[layer] += 1
        if sum(sizes()[:2]) > limit:
            quotas[layer] -= 1
    allocation, metadata, payload = sizes()
    return dict(limit_bytes=limit, expert_count=sum(quotas),
                packed_payload_bytes=payload, aligned_slots_bytes=allocation,
                metadata_bytes=metadata, owned_bytes=allocation + metadata,
                unused_bytes=limit - allocation - metadata,
                slot_alignment_bytes=4096,
                layers=[dict(layer=layer, quota=q, expert_ids=list(range(q)),
                             packed_expert_bytes=packed_bytes(layer),
                             slot_stride_bytes=align(packed_bytes(layer)))
                        for layer, q in enumerate(quotas)])


def budget():
    inv = inventory()
    cache = placement()
    # All of these are explicit bounds, not a measured live allocation peak.
    owned = dict(target_nonexpert=inv['target_nonexpert'],
                 complete_draft=inv['complete_draft'], target_expert_cache=cache['owned_bytes'],
                 target_kv_index=inv['target_kv_index'], target_recurrent=inv['target_recurrent'],
                 recurrent_checkpoint_allowance=inv['target_recurrent'],
                 workspace_allowance=GIB, transaction_and_graph_allowance=GIB,
                 device_transfer_allowance=256 * 1024**2)
    total = sum(owned.values())
    selected = 10 * (47 * ORDINARY + EXCEPTION)
    # Each expert has probability 10/512 in this hypothetical uniform model.
    hit = cache['packed_payload_bytes'] / (512 * (47 * ORDINARY + EXCEPTION))
    misses = 480 - cache['expert_count'] * 10 / 512
    miss_bytes = selected - cache['packed_payload_bytes'] * 10 / 512
    mailbox_payload = 48 * 2560 * 2 + misses * 2560 * 2
    return dict(schema='own-runtime.packet46.cache-budget.v1', design_only=True,
                device_executed=False, admitted=False, context_capacity=4096,
                kv_dtype='BF16', placement=cache, source_inventory=inv,
                owned_categories=owned, owned_total_bytes=total,
                arena_limit_bytes=30 * GIB, arena_remaining_bytes=30 * GIB - total,
                conservative_card_bytes=32_000_000_000, physical_reserve_bytes=1_500_000_000,
                margin_after_physical_reserve_bytes=32_000_000_000 - total - 1_500_000_000,
                pinned_host_mailbox_allowance_bytes=2 * 48 * align(5120 + 10 * 5120 + 4096),
                host_backing_experts_ple_embedding_bytes=48_627_712_000 + 28_800_138_240 + 521_472_000,
                hypothetical_uniform=dict(byte_hit_fraction=hit, misses_per_target_position=misses,
                    expert_bytes_per_target_position=selected, cpu_bytes_per_target_position=miss_bytes,
                    mailbox_payload_bytes_per_target_position=mailbox_payload,
                    required_processed_GB_s_at_60_positions_s=miss_bytes * 60 / 1e9,
                    required_experts_s_at_60_positions_s=misses * 60),
                unresolved=['runtime cache metadata ABI and live allocation peak',
                    'complete speculative write-set and rollback storage',
                    'CPU latency distribution and observed per-layer IQ3 routing',
                    'host page admission, DMA and driver shadow',
                    'prefill peaks and graph rebuild overlap'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    row = budget()
    text = json.dumps(row, indent=2) + '\n'
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end='')

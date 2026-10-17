#!/usr/bin/env python3
"""CPU metadata check of R314's real hybrid prefix cache and exact overlay.

Run in the R314 image with /lab mounted, passing --tail 1 (default) or --tail 0.
No model, tensors, kernels, or scheduler instance are created. This checks the
following-token/cache-layout property, not numerical inference equivalence.
Oracle failures count requests, with all bad blocks in the first diagnostic.
Local prefill caching happens INSIDE allocate_slots; the scheduler's explicit
cache_blocks calls are for remote KV receipt, which this test does not simulate.
"""

import argparse
import hashlib
import inspect
import json
import os
import pickle
import random
import sys


BLOCK = 4
NUM_BLOCKS = 64
SEEDS = (314, 2718, 65537)
OVERLAY = "/lab/experiments/qwen38-27b-b70/overlays/b70-prefix-cache-exact"


def digest(value):
    return hashlib.sha256(pickle.dumps(value, protocol=5)).digest()


def emit(label, value):
    print(label, json.dumps(value, sort_keys=True), flush=True)


class OracleFailure(Exception):
    pass


def install_oracle(BlockPool):
    """Wrap before register(): real pool -> oracle -> overlay on cache writes.

    Receipts belong to each pool and are invalidated on actual eviction. Never
    inspect the overlay's `after` map, use its choice logic, or repair its hits.
    """
    original_cache = BlockPool.cache_full_blocks
    original_evict = BlockPool._maybe_evict_cached_block

    def cache(self, request, blocks, num_cached_blocks, num_full_blocks,
              block_size, kv_cache_group_id, block_mask=None):
        original_cache(self, request, blocks, num_cached_blocks, num_full_blocks,
                       block_size, kv_cache_group_id, block_mask)
        if kv_cache_group_id != 0:
            return
        for i in range(num_cached_blocks, min(num_full_blocks, len(blocks))):
            block = blocks[i]
            if block.is_null or (block_mask is not None
                                 and not block_mask[i - num_cached_blocks]):
                continue
            end = (i + 1) * block_size
            token = (request.prompt_token_ids[end]
                     if end < len(request.prompt_token_ids) else "none")
            self._oracle_receipts[block.block_id] = (
                block.block_hash, token, request.request_id, i)

    def evict(self, block):
        removed = original_evict(self, block)
        if removed:
            self._oracle_receipts.pop(block.block_id, None)
            self._oracle_evictions += 1
        return removed

    BlockPool.cache_full_blocks = cache
    BlockPool._maybe_evict_cached_block = evict


def overlay_stats(coordinator):
    # The overlay keeps stats in closures, without a public accessor.
    found = {}
    for name, cls in vars(coordinator).items():
        if not isinstance(cls, type):
            continue
        for method in ("cache_blocks", "find_longest_cache_hit"):
            fn = cls.__dict__.get(method)
            if inspect.isfunction(fn):
                stats = inspect.getclosurevars(fn).nonlocals.get("stats")
                if isinstance(stats, dict):
                    found[f"{name}.{method}"] = dict(stats)
    return found or {"available": False}


def random_prompts(seed):
    rng = random.Random(seed)
    roots = [[100 + j * 100 + i for i in range(48)] for j in range(3)]
    history = []
    for _ in range(400):
        roll = rng.random()
        growable = [p for p in history[-80:] if len(p) < 60]
        if roll < 0.35 and growable:
            base = rng.choice(growable)
            n = rng.randint(1, min(12, 60 - len(base)))
            prompt = base + [rng.randrange(1, 40) for _ in range(n)]
        elif roll < 0.45 and history:
            prompt = list(rng.choice(history[-40:]))
        else:
            root = rng.choice(roots)
            boundary = rng.choice((4, 8, 12, 16, 20, 24, 32))
            # Most forks are exactly at boundaries; some split a block.
            if roll > 0.85:
                boundary += rng.randint(1, 3)
            length = rng.randint(5, 60)
            fork = rng.choice((11, 22, 33))
            suffix = [fork] + [400 + fork + i % 7 for i in range(60)]
            prompt = (root[:boundary] + suffix)[:length]
        history.append(prompt)
        yield prompt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tail", choices=(0, 1), type=int, default=1)
    args = parser.parse_args()
    os.environ["B70_PREFIX_CACHE_EXACT"] = "1"
    os.environ["B70_PREFIX_CACHE_EXACT_TAIL"] = str(args.tail)
    os.environ["B70_PREFIX_CACHE_EXACT_BACK"] = "1"
    sys.dont_write_bytecode = True
    sys.path.insert(0, OVERLAY)

    import torch
    from vllm.sampling_params import SamplingParams
    from vllm.v1.core import kv_cache_coordinator as coordinator
    from vllm.v1.core.block_pool import BlockPool
    from vllm.v1.core.kv_cache_manager import KVCacheManager
    from vllm.v1.core.kv_cache_utils import (
        get_request_block_hasher, init_none_hash, make_block_hash_with_group_id,
    )
    from vllm.v1.kv_cache_interface import (
        FullAttentionSpec, KVCacheConfig, KVCacheGroupSpec, MambaSpec,
    )
    from vllm.v1.request import Request, RequestStatus
    import b70_prefix_cache_exact as overlay

    if getattr(coordinator, "_b70_prefix_cache_exact", False):
        raise RuntimeError("Overlay already registered; require a fresh process")
    install_oracle(BlockPool)
    overlay.register()
    init_none_hash(digest)
    hasher = get_request_block_hasher(BLOCK, digest)
    totals = dict(requests=0, total_prompt_tokens=0, total_hit_tokens=0,
                  oracle_failures=0)
    pools = []
    first_failure = None

    def manager_for(retention):
        config = KVCacheConfig(
            num_blocks=NUM_BLOCKS, kv_cache_tensors=[],
            kv_cache_groups=[
                KVCacheGroupSpec(
                    layer_names=["target.attn", "mtp.attn"],
                    kv_cache_spec=FullAttentionSpec(
                        block_size=BLOCK, num_kv_heads=1, head_size=8,
                        dtype=torch.bfloat16), is_eagle_group=True),
                KVCacheGroupSpec(
                    layer_names=["target.mamba"],
                    kv_cache_spec=MambaSpec(
                        block_size=BLOCK, shapes=((8,), (8,)),
                        dtypes=(torch.bfloat16, torch.bfloat16),
                        mamba_cache_mode="align", num_speculative_blocks=1)),
            ], prefix_cache_retention_interval=retention)
        manager = KVCacheManager(
            kv_cache_config=config, max_model_len=64,
            scheduler_block_size=BLOCK, hash_block_size=BLOCK,
            max_in_flight_tokens=BLOCK, enable_caching=True,
            use_eagle=True, num_prefill_lookahead=1)
        assert isinstance(manager.coordinator, coordinator.HybridKVCacheCoordinator)
        assert manager.coordinator.eagle_group_ids == {0}
        assert [type(m).__name__ for m in manager.coordinator.single_type_managers] == [
            "FullAttentionManager", "MambaManager"]
        manager.block_pool._oracle_receipts = {}
        manager.block_pool._oracle_evictions = 0
        pools.append(manager.block_pool)
        return manager

    def run(manager, name, prompt, verbose=False):
        nonlocal first_failure
        request = Request(name, list(prompt), SamplingParams(max_tokens=1),
                          pooling_params=None, block_hasher=hasher)
        manager.new_step_starts()
        blocks, hit, shared = manager.get_computed_blocks(request)
        request.shared_prefix_boundary = shared
        totals["requests"] += 1
        totals["total_prompt_tokens"] += len(prompt)
        totals["total_hit_tokens"] += hit
        if verbose:
            emit("hit", dict(request=name, tail=args.tail, prompt=len(prompt), hit=hit))
        errors = []
        if hit % BLOCK or not 0 <= hit <= len(prompt) - 1:
            errors.append("hit is not aligned or exceeds prompt-1")
        attn, mamba = blocks.blocks
        k = hit // BLOCK
        if len(attn) != k or any(b.is_null for b in attn):
            errors.append("attention layout differs from k real blocks")
        if (len(mamba) != k or any(b is not manager.block_pool.null_block
                                  for b in mamba[:-1])
                or (k and mamba[-1].is_null)):
            errors.append("Mamba layout differs from [null]*(k-1)+[state]")
        for i, block in enumerate(attn):
            record = manager.block_pool._oracle_receipts.get(block.block_id)
            end = (i + 1) * BLOCK
            want = prompt[end] if end < len(prompt) else "none"
            expected_hash = make_block_hash_with_group_id(request.block_hashes[i], 0)
            if (record is None or record[0] != block.block_hash
                    or block.block_hash != expected_hash or record[1] == "none"
                    or record[1] != want or record[3] != i):
                errors.append(dict(index=i, block_id=block.block_id, want=want,
                                   recorded=record[1:] if record else "missing"))
        if errors:
            totals["oracle_failures"] += 1
            if first_failure is None:
                first_failure = dict(request=name, prompt=prompt, hit=hit,
                                     shared_prefix_boundary=shared, errors=errors)
                emit("FIRST_ORACLE_FAILURE", first_failure)
            if args.tail:
                raise OracleFailure(name)

        # Admission passes hits separately while num_computed_tokens is zero.
        # Later steps use the running count, with no repeated prefix lookup.
        first = True
        try:
            while (hit if first else request.num_computed_tokens) < len(prompt):
                start = hit if first else request.num_computed_tokens
                if not first:
                    manager.new_step_starts()
                count = min(BLOCK, len(prompt) - start)
                allocated = manager.allocate_slots(
                    request, count, num_new_computed_tokens=hit if first else 0,
                    new_computed_blocks=blocks if first else None,
                    num_lookahead_tokens=1, has_scheduled_reqs=False)
                if allocated is None:
                    raise RuntimeError(f"allocation failed: {name}, start={start}")
                # allocate_slots already called coordinator.cache_blocks.
                request.status = RequestStatus.RUNNING
                request.num_computed_tokens = start + count
                request.is_prefill_chunk = request.num_computed_tokens < len(prompt)
                # Simulate completed synchronous execution before the next step.
                request.num_in_flight_tokens = 0
                first = False
        finally:
            request.status = RequestStatus.FINISHED_STOPPED
            manager.free(request)
        assert manager.block_pool.get_num_free_blocks() == NUM_BLOCKS - 1
        return request, hit

    result = 0
    try:
        for label, retention in (("dense", None), ("sparse4", 4 * BLOCK)):
            emit("variant", dict(name=label, tail=args.tail, retention_tokens=retention))
            manager = manager_for(retention)
            x = list(range(100, 120))  # Stock B hit lands on periodic state 16.
            a = x + [11, 31, 32, 33, 34, 35, 36, 37, 38]
            b = x + [22, 41, 42, 43, 44, 45, 46, 47, 48]
            run(manager, f"{label}/A", a, True)
            req_b, hit_b = run(manager, f"{label}/B", b, True)
            assert hit_b == 16, f"duplicate setup: expected stock B hit 16, got {hit_b}"
            key = make_block_hash_with_group_id(req_b.block_hashes[4], 0)
            copies = [r[1] for r in manager.block_pool._oracle_receipts.values()
                      if r[0] == key]
            assert 11 in copies and 22 in copies, ("missing duplicate X copies", copies)
            emit("duplicate_X_following_tokens", copies)
            for i in range(8):
                text = b if i % 2 == 0 else a
                run(manager, f"{label}/follow-{'B' if i % 2 == 0 else 'A'}-{i}",
                    text + [51, 52, 53, 54], True)
            for seed in SEEDS:
                emit("seed", dict(variant=label, seed=seed, requests=400))
                manager = manager_for(retention)
                before = dict(totals)
                for i, prompt in enumerate(random_prompts(seed)):
                    run(manager, f"{label}/seed-{seed}/request-{i}", prompt)
                emit("seed_summary", {key: totals[key] - before[key] for key in totals})
                assert manager.block_pool._oracle_evictions > 0, "eviction not exercised"
    except OracleFailure:
        result = 1
    except Exception as exc:
        emit("HARNESS_ERROR", dict(type=type(exc).__name__, message=str(exc)))
        result = 1
    finally:
        emit("TOTAL", dict(totals, tail=args.tail,
                           evictions=sum(p._oracle_evictions for p in pools)))
        emit("overlay_stats", overlay_stats(coordinator))
    return result


if __name__ == "__main__":
    sys.exit(main())

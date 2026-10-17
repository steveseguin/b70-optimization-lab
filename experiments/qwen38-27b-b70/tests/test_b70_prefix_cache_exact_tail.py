"""CPU check of B70_PREFIX_CACHE_EXACT_TAIL (b70_prefix_cache_exact 0.3.0) against stand-ins shaped like the R314 block
pool (duplicate copies per hash, first copy returned), the hybrid coordinator (one drafting attention group, one
recurrent-state group, stock drafting drop) and KVCacheManager. No vLLM, no GPU."""
import hashlib
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
B = 4  # block size; the overlay reads it from the coordinator, so any size exercises the same arithmetic
ATT, MAM = 0, 1  # group ids


def key(block_hash, gid):
    return block_hash + gid.to_bytes(4, 'big')


class Block:
    def __init__(self, block_id, is_null=False):
        self.block_id, self.is_null = block_id, is_null

    def __repr__(self):
        return f'B{self.block_id}'


class Table:  # R314 BlockHashToBlockMap: one block or {block_id: block} per key, insertion order kept
    def __init__(self):
        self._cache = {}

    def insert(self, k, blk):
        old = self._cache.get(k)
        if old is None:
            self._cache[k] = blk
        elif isinstance(old, dict):
            old[blk.block_id] = blk
        else:
            self._cache[k] = {old.block_id: old, blk.block_id: blk}

    def evict(self, k, block_id):
        old = self._cache.get(k)
        if isinstance(old, dict):
            old.pop(block_id, None)
            if len(old) == 1:
                self._cache[k] = next(iter(old.values()))
        elif old is not None and old.block_id == block_id:
            del self._cache[k]


class Pool:
    def __init__(self):
        self.cached_block_hash_to_block = Table()
        self.null_block = Block(0, is_null=True)
        self.next_id = 1

    def new(self):
        self.next_id += 1
        return Block(self.next_id)

    def get_cached_block(self, block_hash, gids):
        out = []
        for gid in gids:
            entry = self.cached_block_hash_to_block._cache.get(key(block_hash, gid))
            if entry is None:
                return None
            out.append(next(iter(entry.values())) if isinstance(entry, dict) else entry)
        return out

    def cache_full_blocks(self, request, blocks, num_cached_blocks, num_full_blocks, block_size, kv_cache_group_id,
                          block_mask=None):
        for i in range(num_cached_blocks, num_full_blocks):
            if not blocks[i].is_null:
                self.cached_block_hash_to_block.insert(key(request.block_hashes[i], kv_cache_group_id), blocks[i])


class FullAttentionManager:
    block_size = B


class MambaManager:
    block_size = B


class Hybrid:  # stock stand-in: longest run of attention blocks, drop one (drafting), land on a kept state
    def __init__(self, pool):
        self.block_pool, self.scheduler_block_size = pool, B
        self.eagle_group_ids, self.enable_partial_hash_hits, self.num_reprefillable_tokens = {ATT}, False, 0
        self.single_type_managers = [FullAttentionManager(), MambaManager()]

    def find_longest_cache_hit(self, block_hashes, max_cache_hit_length):
        found = []
        while len(found) < len(block_hashes) and (len(found) + 1) * B <= max_cache_hit_length:
            f = self.block_pool.get_cached_block(block_hashes[len(found)], [ATT])
            if f is None:
                break
            found.append(f[0])
        for k in range(len(found) - 1, 0, -1):
            state = self.block_pool.get_cached_block(block_hashes[k - 1], [MAM])
            if state:
                return (found[:k], [self.block_pool.null_block] * (k - 1) + [state[0]]), k * B, 0
        return ([], []), 0, 0


class Manager:
    def __init__(self, coordinator):
        self.coordinator = coordinator

    def get_computed_blocks(self, request):
        return self.coordinator.find_longest_cache_hit(request.block_hashes, request.num_tokens - 1)


def install(tail):
    os.environ['B70_PREFIX_CACHE_EXACT'] = '1'
    os.environ['B70_PREFIX_CACHE_EXACT_TAIL'] = '1' if tail else '0'

    class KVCacheCoordinator:
        def cache_blocks(self, request, num_computed_tokens):
            pass

    own = lambda cls: {k: v for k, v in vars(cls).items() if k not in ('__dict__', '__weakref__')}
    hybrid_cls = type('HybridKVCacheCoordinator', (KVCacheCoordinator,), own(Hybrid))  # methods in the class's own dict

    class MambaMask:
        @classmethod
        def reachable_block_mask(cls, *a, **k):
            return None

    mods = {name: types.ModuleType(name) for name in (
        'vllm', 'vllm.logger', 'vllm.v1', 'vllm.v1.core', 'vllm.v1.core.kv_cache_coordinator',
        'vllm.v1.core.single_type_kv_cache_manager', 'vllm.v1.core.block_pool', 'vllm.v1.core.kv_cache_manager',
        'vllm.v1.core.kv_cache_utils')}
    mods['vllm.logger'].init_logger = lambda name: types.SimpleNamespace(warning=lambda *a, **k: None)
    co = mods['vllm.v1.core.kv_cache_coordinator']
    co.KVCacheCoordinator, co.HybridKVCacheCoordinator = KVCacheCoordinator, hybrid_cls
    mods['vllm.v1.core.single_type_kv_cache_manager'].MambaManager = MambaMask
    pool_cls = type('BlockPool', (), own(Pool))
    mods['vllm.v1.core.block_pool'].BlockPool = pool_cls
    manager_cls = type('KVCacheManager', (), own(Manager))
    mods['vllm.v1.core.kv_cache_manager'].KVCacheManager = manager_cls
    mods['vllm.v1.core.kv_cache_utils'].make_block_hash_with_group_id = key
    core = mods['vllm.v1.core']
    for name in ('kv_cache_coordinator', 'single_type_kv_cache_manager', 'block_pool', 'kv_cache_manager',
                 'kv_cache_utils'):
        setattr(core, name, mods['vllm.v1.core.' + name])
    sys.modules.update(mods)
    spec = importlib.util.spec_from_file_location(
        'exact_tail', HERE / 'overlays/b70-prefix-cache-exact/b70_prefix_cache_exact.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.register()
    return pool_cls, hybrid_cls, manager_cls


def request(tokens):
    hashes, h = [], b'root'
    for i in range(len(tokens) // B):
        h = hashlib.sha256(h + repr(tokens[i * B:(i + 1) * B]).encode()).digest()
        hashes.append(h)
    return types.SimpleNamespace(all_token_ids=list(tokens), num_prompt_tokens=len(tokens), num_tokens=len(tokens),
                                 block_hashes=hashes)


def read(pool, req, nblocks, states=()):
    """A prompt read cold: attention blocks 0..nblocks-1 cached (after-tokens recorded by the overlay), recurrent
    states kept at the listed block indices. Returns the attention blocks."""
    att = [pool.new() for _ in range(nblocks)]
    pool.cache_full_blocks(req, att, 0, nblocks, B, ATT)
    mam = [pool.new() if i in states else pool.null_block for i in range(nblocks)]
    pool.cache_full_blocks(req, mam, 0, nblocks, B, MAM)
    return att, mam


X, Y, Z = [1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]


class TailTest(unittest.TestCase):
    def setUp(self):
        self.pool_cls, self.hybrid_cls, self.manager_cls = install(tail=True)
        self.pool = self.pool_cls()
        self.manager = self.manager_cls(self.hybrid_cls(self.pool))

    def hit(self, req):
        blocks, length, _ = self.manager.get_computed_blocks(req)
        return [b.block_id for b in blocks[ATT]], length, blocks[MAM]

    def test_interior_block_from_other_text_is_not_used(self):
        # A: X then 11...; B: X then 22 (Y) then 33. B's state kept only at the end of its second block.
        a = request(X + [11, 0, 0, 0] + [7])
        att_a, _ = read(self.pool, a, 2)
        b = request(X + [22] + Y[1:] + [33] + Z[1:] + [8])
        att_b, mam_b = read(self.pool, b, 3, states={1})
        c = request(X + [22] + Y[1:] + [33] + Z[1:] + [8])  # B's text again
        ids, length, mam = self.hit(c)
        self.assertEqual(length, 2 * B)
        self.assertEqual(ids, [att_b[0].block_id, att_b[1].block_id])  # B's copy of block 0, not A's (made with 11)
        self.assertNotIn(att_a[0].block_id, ids)
        self.assertIs(mam[-1], mam_b[1])

    def test_no_copy_with_the_right_token_means_no_block(self):
        a = request(X + [11, 0, 0, 0] + [7])
        read(self.pool, a, 2)
        b = request(X + [22] + Y[1:] + [33] + Z[1:] + [8])
        att_b, _ = read(self.pool, b, 3, states={1})
        self.pool.cached_block_hash_to_block.evict(key(b.block_hashes[0], ATT), att_b[0].block_id)  # only A's copy left
        ids, length, _ = self.hit(request(X + [22] + Y[1:] + [33] + Z[1:] + [8]))
        self.assertEqual((ids, length), ([], 0))

    def test_engine_interior_choice_replaced_by_matching_copy(self):
        a = request(X + [11, 0, 0, 0] + [7])
        att_a, _ = read(self.pool, a, 2)
        b = request(X + [22] + Y[1:] + [33] + Z[1:] + [44] + [0, 0, 0] + [9])
        att_b, mam_b = read(self.pool, b, 4, states={1})
        ids, length, mam = self.hit(request(b.all_token_ids))
        # stock: blocks 0..3 found (block 0 = A's copy), drop one, state at block 1 -> hit 2 with A's block 0
        self.assertEqual(ids, [att_b[0].block_id, att_b[1].block_id])
        self.assertEqual(length, 2 * B)

    def test_shortened_when_an_interior_block_has_no_good_copy(self):
        a = request(X + Y + [11, 0, 0, 0] + [7])
        att_a, _ = read(self.pool, a, 3, states={0})
        b = request(X + Y + [22, 0, 0, 0] + [8])  # shares X, Y; differs right after Y
        att_b, mam_b = read(self.pool, b, 3, states={0, 1})
        self.pool.cached_block_hash_to_block.evict(key(b.block_hashes[1], ATT), att_b[1].block_id)  # only A's Y copy
        ids, length, mam = self.hit(request(b.all_token_ids))
        self.assertEqual(length, 1 * B)  # stops before block 1 (made with 11, this text has 22), lands on state 0
        self.assertEqual(ids, [att_a[0].block_id] if att_a[0].block_id == ids[0] else [att_b[0].block_id])

    def test_plain_extension_kept(self):
        a = request(X + Y + Z + [5])
        att_a, mam_a = read(self.pool, a, 3, states={1, 2})
        ids, length, mam = self.hit(request(X + Y + Z + [5, 6, 7]))
        self.assertEqual(ids, [b.block_id for b in att_a])  # the dropped block is back: every after-token matches
        self.assertEqual(length, 3 * B)
        self.assertIs(mam[-1], mam_a[2])

    def test_block_ending_at_a_prompt_end_never_used(self):
        a = request(X + Y)  # prompt ends exactly at block 1's end: its drafter value came from the sampled token
        att_a, _ = read(self.pool, a, 2, states={0, 1})
        ids, length, _ = self.hit(request(X + Y + Z + [5]))
        self.assertEqual(length, 1 * B)
        self.assertEqual(ids, [att_a[0].block_id])


class SwitchOffTest(unittest.TestCase):
    def test_stock_result_unchanged(self):
        pool_cls, hybrid_cls, manager_cls = install(tail=False)
        pool = pool_cls()
        manager = manager_cls(hybrid_cls(pool))
        a = request(X + Y + Z + [5])
        att, _ = read(pool, a, 3, states={1, 2})
        blocks, length, _ = manager.get_computed_blocks(request(X + Y + Z + [5, 6, 7]))
        self.assertEqual(length, 2 * B)  # the stock drop
        self.assertEqual([b.block_id for b in blocks[ATT]], [att[0].block_id, att[1].block_id])


if __name__ == '__main__':
    unittest.main()

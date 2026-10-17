"""Prefix cache that is exact by construction on the hybrid FP8 lane (research overlay). B70_PREFIX_CACHE_EXACT=1.

Serve with `--enable-prefix-caching --mamba-cache-mode align`, the prompt read in pieces of exactly one cache block
(`--max-num-batched-tokens 832`), and a positive `--prefix-cache-retention-interval` (a multiple of 832).

The claim to protect: a request answered after a cache hit makes the same kernel calls on the same inputs as the same
request read cold, so its answer is bit-identical. With one-block pieces that holds for everything the cache stores
*while a prompt is being read*: block k is always computed by the piece [k*832, (k+1)*832), whatever came before.
Two things in the stock engine fall outside it (read from the R314 source, notes/2026-10-05-prefix-cache-reuse-rules.md):

1. Blocks finished while the model is *writing* are cached too (`KVCacheManager.allocate_slots` caches up to
   `request.num_tokens`, which counts output tokens; with drafting the recurrent state at those boundaries is kept as
   well). Their contents come from the decode and draft-verify kernels, not from the prompt-reading kernels a cold
   read would use. A later request that extends this conversation would be served those blocks.
   Fix: nothing past the prompt is ever cached (`cache_blocks` is capped at `request.num_prompt_tokens`). The next
   turn re-reads the previous answer as prompt, about 3,000 tokens a second, and caches it then.

2. With drafting, a hit is moved back by one block (the drafter needs the last block recomputed), and the recurrent
   state is only kept at the last full block of each prompt, so by default the engine keeps the state at *every*
   block instead (three extra blocks of memory per block of context: four times the memory per token).
   Fix: also keep the state one block before the end-of-prompt block (`B70_PREFIX_CACHE_EXACT_BACK`, default 1
   block), and use a sparse periodic interval for everything else. A repeat or an extension of a prompt then lands
   on a kept state, and an edit in the middle of a long context resumes from the last periodic state before it.

It changes which blocks are kept, never what is computed. One user at a time is what has been tested.

0.2.0 (2026-10-17), B70_PREFIX_CACHE_EXACT_TAIL=1: the drafting hit lands on the end-of-prompt state instead of one
block before it. Why the engine moves a drafting hit back one block (`kv_cache_coordinator.py`, the comment above the
multi-module MTP check): when the drafter reads a prompt piece, the KV it writes at the piece's last position is made
from that position's hidden state and the *next* token (the first token of the following piece), and that token is
not covered by the block hashes up to the boundary. So the engine requires one more matching block and then drops
it. With this switch the overlay records, for every block cached while a prompt is read, the token(s) after its end
(`num_prefill_lookahead`, one for a single MTP module). After the engine's search it walks the attention blocks past
the engine's hit (hash-chain order, as far as every attention group holds them) and takes the furthest block
boundary where every recurrent-state group has a kept state and the new request's token(s) after the boundary equal
the recorded ones. Then every cached value the request reads is what a cold read of the same prompt computes (the
hash chain covers the tokens before the boundary, the recorded token the one after it), and the request goes on from
the boundary in the same pieces. Gains: one block (832 tokens) of re-reading on the next call of an agent loop and on
a repeated prompt; an edit just before the end of a long text resumes from the kept state before the edit (the
end-of-prompt state or the one a block before it) instead of the last periodic one. Never past the prompt or
`num_tokens - 1`; with the switch off, behaviour equals 0.1.0.

0.3.0 (2026-10-17, same switch): the check covers every block of the hit, not only the last. The engine keeps
duplicate copies of a block hash (every drafting hit recomputes its dropped block) and its lookup returns the first
copy, so two texts that agree up to a block's end and then differ give two copies of that block whose drafter values
at the last position differ; a later request could be handed the other text's copy as an interior block (the stock
engine does the same; a Codex review found it, `notes/2026-10-17-fp8-cache-tail-block.md`). Now every block of a
drafting group must carry this request's own following token(s): the engine's copy if it does, otherwise another copy
that does; where none does, the hit stops before that block (at the furthest earlier kept state), and if no boundary
is left the request reads from the start. A block with no recorded token (a prompt that ended exactly at its end, so
its drafter value came from the sampled token) is never part of a hit. Only the drafter's values were ever at stake:
the main model's values in a block depend only on the tokens up to it.
"""
import os


def cap_tokens(num_computed_tokens, num_prompt_tokens):
    """Tokens that may be cached: never past the prompt."""
    return min(int(num_computed_tokens), int(num_prompt_tokens))


def with_back_boundaries(boundaries, alignment_tokens, back_blocks):
    """The engine's reuse points plus the points `back_blocks` blocks before each (where a drafting hit lands)."""
    out = list(boundaries)
    if not alignment_tokens or back_blocks <= 0:
        return out
    for boundary in list(boundaries):
        aligned = boundary // alignment_tokens * alignment_tokens
        for k in range(1, back_blocks + 1):
            earlier = aligned - k * alignment_tokens
            if earlier > 0 and earlier not in out:
                out.append(earlier)
    return out


def register():
    if os.environ.get('B70_PREFIX_CACHE_EXACT', '').strip() != '1':
        return
    back = int(os.environ.get('B70_PREFIX_CACHE_EXACT_BACK', '1') or '0')
    from vllm.logger import init_logger
    from vllm.v1.core import kv_cache_coordinator as coordinator
    from vllm.v1.core import single_type_kv_cache_manager as managers

    logger = init_logger('b70_prefix_cache_exact')
    if getattr(coordinator, '_b70_prefix_cache_exact', False):
        return
    stats = {'calls': 0, 'capped': 0}

    def wrap_cache_blocks(cls):
        original = cls.__dict__['cache_blocks']

        def cache_blocks(self, request, num_computed_tokens):
            capped = cap_tokens(num_computed_tokens, request.num_prompt_tokens)
            stats['calls'] += 1
            if capped < num_computed_tokens:
                stats['capped'] += 1
                if stats['capped'] in (1, 1000, 100000):
                    logger.warning('b70_prefix_cache_exact: %d caching calls so far stopped at the end of the prompt '
                                   '(of %d)', stats['capped'], stats['calls'])
            return original(self, request, capped)

        cls.cache_blocks = cache_blocks

    wrapped = []
    for cls in vars(coordinator).values():
        if isinstance(cls, type) and issubclass(cls, coordinator.KVCacheCoordinator) and 'cache_blocks' in cls.__dict__:
            wrap_cache_blocks(cls)
            wrapped.append(cls.__name__)

    mamba = managers.MambaManager
    original_mask = mamba.__dict__['reachable_block_mask'].__func__

    def reachable_block_mask(cls, start_block, end_block, alignment_tokens, kv_cache_spec, use_eagle,
                             retention_interval=None, reachable_boundaries=()):
        return original_mask(cls, start_block, end_block, alignment_tokens, kv_cache_spec, use_eagle,
                             retention_interval=retention_interval,
                             reachable_boundaries=with_back_boundaries(reachable_boundaries, alignment_tokens, back))

    mamba.reachable_block_mask = classmethod(reachable_block_mask)
    tail = os.environ.get('B70_PREFIX_CACHE_EXACT_TAIL', '').strip() == '1'
    if tail:
        install_tail(coordinator, logger)
    coordinator._b70_prefix_cache_exact = True
    logger.warning('b70_prefix_cache_exact: installed (nothing past the prompt is cached: %s; recurrent state also kept '
                   '%d block(s) before each reuse point%s)', ', '.join(wrapped), back,
                   '; drafting hits on the end-of-prompt state' if tail else '')


def install_tail(coordinator, logger):
    """B70_PREFIX_CACHE_EXACT_TAIL=1: record the token(s) after each cached block; a drafting hit uses only blocks made
    with the request's own following token(s), and lands on the furthest kept state they reach."""
    from vllm.v1.core import block_pool as pools
    from vllm.v1.core import kv_cache_manager as kvm
    from vllm.v1.core.kv_cache_utils import make_block_hash_with_group_id

    after = {}  # physical block id -> the prompt token(s) right after the block, when it was cached
    current = {'request': None}
    stats = {'lookups': 0, 'extended': 0, 'no_state': 0, 'token_differs': 0, 'replaced': 0, 'shortened': 0}
    pool_cls = pools.BlockPool
    original_cache = pool_cls.__dict__['cache_full_blocks']

    def cache_full_blocks(self, request, blocks, num_cached_blocks, num_full_blocks, block_size, kv_cache_group_id,
                          block_mask=None):
        original_cache(self, request, blocks, num_cached_blocks, num_full_blocks, block_size, kv_cache_group_id,
                       block_mask)
        n = getattr(self, '_b70_lookahead', 1)
        tokens, prompt = request.all_token_ids, request.num_prompt_tokens
        for i in range(num_cached_blocks, min(num_full_blocks, len(blocks))):
            blk = blocks[i]
            if blk.is_null:
                continue
            end = (i + 1) * block_size
            if end + n <= prompt:
                after[blk.block_id] = tuple(tokens[end:end + n])
            else:
                after.pop(blk.block_id, None)

    pool_cls.cache_full_blocks = cache_full_blocks

    manager_cls = kvm.KVCacheManager
    original_computed = manager_cls.__dict__['get_computed_blocks']

    def get_computed_blocks(self, request):
        current['request'] = request
        try:
            return original_computed(self, request)
        finally:
            current['request'] = None

    manager_cls.get_computed_blocks = get_computed_blocks

    hybrid = coordinator.HybridKVCacheCoordinator
    original_find = hybrid.__dict__['find_longest_cache_hit']

    def copies(pool, block_hash, gid):
        """Every cached block of this hash in this group (the engine keeps duplicates), the engine's own choice first."""
        table = getattr(pool.cached_block_hash_to_block, '_cache', None)
        if table is None:  # not the R314 map: only the engine's choice is visible
            found = pool.get_cached_block(block_hash, [gid])
            return [found[0]] if found else []
        entry = table.get(make_block_hash_with_group_id(block_hash, gid))
        if entry is None:
            return []
        return list(entry.values()) if isinstance(entry, dict) else [entry]

    def find_longest_cache_hit(self, block_hashes, max_cache_hit_length):
        blocks, hit, uncached = original_find(self, block_hashes, max_cache_hit_length)
        request = current['request']
        if request is None or not getattr(self, 'eagle_group_ids', None) or self.enable_partial_hash_hits:
            return blocks, hit, uncached
        n = self.num_reprefillable_tokens + 1
        self.block_pool._b70_lookahead = n
        size = self.scheduler_block_size
        first = hit // size
        top = min(max_cache_hit_length, request.num_prompt_tokens - n, len(block_hashes) * size) // size
        if hit % size or (top <= 0 and first == 0):
            return blocks, hit, uncached
        attn, states = [], []
        for gid, manager in enumerate(self.single_type_managers):
            kind = type(manager).__name__
            if manager.block_size != size or kind not in ('FullAttentionManager', 'MambaManager') \
                    or (kind == 'FullAttentionManager' and len(blocks[gid]) != first):
                stats['other_group'] = stats.get('other_group', 0) + 1
                return blocks, hit, uncached
            (attn if kind == 'FullAttentionManager' else states).append(gid)
        drafting = [gid for gid in attn if gid in self.eagle_group_ids]
        stats['lookups'] += 1
        if stats['lookups'] in (20, 1000) and not stats['extended']:
            logger.warning('b70_prefix_cache_exact: %d drafting-hit lookups, none extended %s; groups %s', stats['lookups'],
                           stats, [(type(m).__name__, m.block_size) for m in self.single_type_managers])
        pool, tokens = self.block_pool, request.all_token_ids
        # Every attention block of the hit, in hash-chain order, from the first: a drafting group's block holds the
        # drafter's value at its last position, made from the token after the block in the request that computed it,
        # which the hash does not cover. So a drafting block is usable only if that recorded token equals this
        # request's; among duplicate copies of a hash the engine's choice is taken first, then any copy that matches.
        chosen = {gid: [] for gid in attn}
        reach = 0
        for idx in range(top):
            want = tuple(tokens[(idx + 1) * size:(idx + 1) * size + n])
            row = []
            for gid in attn:
                engine = blocks[gid][idx] if idx < first else None
                if gid in drafting:
                    pick = next((b for b in ([engine] if engine is not None else []) + copies(pool, block_hashes[idx], gid)
                                 if after.get(b.block_id) == want), None)
                else:
                    pick = engine if engine is not None else next(iter(copies(pool, block_hashes[idx], gid)), None)
                if pick is None:
                    break
                row.append(pick)
            if len(row) < len(attn):
                if any(after.get(b.block_id) is not None for gid in drafting
                       for b in copies(pool, block_hashes[idx], gid)):
                    stats['token_differs'] += 1
                break
            for gid, b in zip(attn, row):
                chosen[gid].append(b)
            reach = idx + 1
        replaced = sum(a is not b for gid in attn for a, b in zip(chosen[gid], blocks[gid]))
        for k in range(reach, 0, -1):  # the furthest boundary with a kept state, every block before it usable
            if k == first and not replaced:
                return blocks, hit, uncached  # the engine's own hit, every block checked
            if k == first:
                kept = [blocks[gid][-1:] for gid in states]
            else:
                kept = [pool.get_cached_block(block_hashes[k - 1], [gid]) for gid in states]
            if any(not f for f in kept):
                stats['no_state'] += 1
                continue
            new = list(blocks)
            for gid in attn:
                new[gid] = chosen[gid][:k]
            for gid, f in zip(states, kept):
                new[gid] = [pool.null_block] * (k - 1) + [f[0]]
            if replaced:
                stats['replaced'] += 1
            if k < first:
                stats['shortened'] += 1
            if k > first:
                stats['extended'] += 1
                stats['blocks_gained'] = stats.get('blocks_gained', 0) + k - first
            noted = stats['extended'] if k > first else stats['replaced'] + stats['shortened']
            if noted in (1, 100, 10000):
                logger.warning('b70_prefix_cache_exact: drafting hit moved to a later kept state %d times, %d blocks in '
                               'all; %s', stats['extended'], stats.get('blocks_gained', 0), stats)
            return tuple(new), k * size, max(0, hit + uncached - k * size)
        if first == 0:
            return blocks, hit, uncached
        stats['shortened'] += 1  # no usable boundary: read from the start rather than use a block made for other text
        logger.warning('b70_prefix_cache_exact: engine hit of %d tokens refused (a block made for other text); %s',
                       hit, stats)
        return tuple([] for _ in blocks), 0, max(0, hit + uncached)

    hybrid.find_longest_cache_hit = find_longest_cache_hit

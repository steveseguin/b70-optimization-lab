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
    coordinator._b70_prefix_cache_exact = True
    logger.warning('b70_prefix_cache_exact: installed (nothing past the prompt is cached: %s; recurrent state also kept '
                   '%d block(s) before each reuse point)', ', '.join(wrapped), back)

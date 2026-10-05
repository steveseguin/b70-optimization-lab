# Prefix-cache reuse rules for Qwen3.8-27B (hybrid GDN) in align mode, from the code

Date: 2026-10-05. Source read: `/mnt/fast-ai/src/vllm-r314-site-packages/vllm` (R314 image, vLLM 0.29-based XPU fork).
Code reading only; nothing was run. Paths below are relative to that `vllm/` directory.

## Plain-words summary

1. The 48 "linear" layers carry a running summary (the state) instead of a per-token cache. A cached prefix can be reused only at a place where a copy of that summary was **kept**, and the attention cache also has to match there.
2. In this build the server keeps very few of those copies by default: **one per request, at the last 832-token boundary of the prompt** (`prefix_cache_retention_interval` defaults to 0). All other boundaries are computed and then thrown away.
3. That explains everything you saw. A repeat, or the same prompt with text added, matches that saved point. An edit before it leaves nothing to resume from, so the hit is 0, not "one block fewer". The block your 16-token answer filled was not kept, because only prompt ends are kept.
4. There is one extra rule. When a request finds its attention prefix in the cache but no saved summary there, it keeps a copy at that spot (the "junction") as it reads past it. So the **next** request that makes a similar edit gets a hit. One miss, then hits.
5. Saved copies stay until the memory is needed. The oldest go first (LRU), and they share one pool with the attention cache. In an agent loop, each earlier call's prompt end stays reusable until it is pushed out.
6. With chunk = block = 832, every boundary already lands on a chunk end. So 832 is not needed to get hits. It is needed for the "same kernel calls" exactness argument, and for keeping more than the default few copies.
7. One saved copy costs about **78 MiB per card** (the content is 73.4 MiB, padded to fit the slot). That is exactly **3 KV blocks**, the memory of 2,496 tokens of attention cache.
8. `--mamba-cache-mode all` (keep every boundary) is refused for this model. `none` means no prefix caching.
9. A small change can add saved points where you choose them, such as message starts: a request field, read in one function, plus a guard that never saves points reached during the answer. An edit in the middle of the context would then resume from the nearest saved point before it.
10. There is one exactness risk your 56/56 test did not exercise. Attention-cache blocks filled **while answering** are kept, and in a 3-turn chain they can be served to a later turn (details in section 7). With MTP on, the defaults change, and saved points can also come from answer tokens.

---

## 1. Where state checkpoints are made and what makes a prefix hittable

**Where the state physically lives.** In align mode a request's state is read from, and written to, the block that holds its last scheduled token. `v1/attention/backends/utils.py:1130-1168` (`mamba_get_block_table_tensor`):
> "align": ... output (#requests, 1 + num_speculative_blocks), which are the last 1 + num_speculative_blocks of each request.
> `start_indices = (seq_lens - 1) // kv_cache_spec.block_size`

Before the forward pass, `preprocess_mamba` (`v1/worker/mamba_utils.py:1433-1537`) copies the previous step's state into that block whenever the block index changes. So a step that ends exactly at token `k*832` leaves the state after `k*832` tokens in block `k-1`. A checkpoint therefore exists only at a **chunk end that is block-aligned**. This build's "internal prefill checkpoint" blocks are only used by Kimi KDA (`models/kimi_k3/nvidia/kda.py:599`), so they are 0 for GDN.

**Which checkpoints are kept (the key rule).** Each block is "kept" by giving it a hash in the block pool, in `SingleTypeKVCacheManager.cache_blocks` (`v1/core/single_type_kv_cache_manager.py:432-482`):
```
reachable_boundaries = [request.num_prompt_tokens - 1]          # :459
if request.shared_prefix_boundary:
    reachable_boundaries.append(request.shared_prefix_boundary)
block_mask = self.reachable_block_mask(..., retention_interval=retention_interval, reachable_boundaries=...)
```
`MambaManager.reachable_block_mask` (`:1472-1527`): `None` means dense, `0` means "keep only the reachable_boundaries states", `>0` means one per interval. For each boundary: `aligned = boundary_tokens // alignment_tokens * alignment_tokens; boundary_block = aligned // block_size - 1` (`:1521-1525`).
`block_pool.cache_full_blocks` skips null and masked-out blocks (`v1/core/block_pool.py:272-276`).

The default is 0:
- `config/cache.py:60-65`: `return 0 if env_value is None else int(env_value)`
- `config/cache.py:156-163`: "``0`` retains only semantic checkpoints, including the latest replay boundary and shared-prefix junctions ... ``None`` retains checkpoints densely."
- `engine/arg_utils.py:~2079-2087`: when the flag is unset, `retention_interval = 0`.
- Exception: hybrid model plus EAGLE-family speculation (including `mtp`, `config/speculative.py:1847`) gets dense `None` (`engine/arg_utils.py:2392-2407`).

So without MTP, per request only the block ending at `floor((num_prompt_tokens-1)/832)*832` is kept, plus a junction block if one was set. Every other state block is freed **unhashed** in `MambaManager.remove_skipped_blocks` (`:1529-1563`). Unhashed blocks go to the *front* of the free queue and are reused first (`block_pool.py:735-747`).

**Hit search.**
- `HybridKVCacheCoordinator.find_longest_cache_hit` (`v1/core/kv_cache_coordinator.py:770-903`): full attention goes first (the longest run of matching block hashes), then Mamba.
- `MambaManager.find_longest_cache_hit` (`single_type_kv_cache_manager.py:1447-1465`) searches **right to left** for the last block hash that has a kept state: `for i in range(max_num_blocks - 1, -1, -1): if cached_block := block_pool.get_cached_block(block_hashes[i], ...)`.
- The final hit is the smaller of the two. Here there are two spec groups (1 attention group plus 3 identical Mamba groups), so `is_simple_hybrid` holds and one pass is enough.
- `max_cache_hit_length = request.num_tokens - 1` (`v1/core/kv_cache_manager.py:258`).

So a prefix is hittable at boundary B when (a) all attention blocks up to B are cached and (b) a kept state block exists whose chained hash equals the hash of block `B/832 - 1`. Block hashes are chained, so (b) also means everything before B is identical.

**Your observations explained.**
- Repeat / append: P's kept checkpoint is at `floor((len(P)-1)/832)*832`, and that is the hit. ✔
- Change inside P's last partial block: the common prefix still includes that boundary, so it hits. ✔
- Change before that boundary: the attention hit is shorter, but **no state was kept** at any earlier boundary, so Mamba finds nothing and the hit is 0. ✔
- Deletion at 50%: same reason, no kept state before the edit. ✔
- Next turn after an answer that crossed a boundary: the attention group *did* hash the decode-completed block (section 3), but the Mamba group kept only P's prompt-end state. The hit is P's boundary, one block short of the common prefix. ✔

**Junction rule (Marconi-style).** `get_computed_blocks` returns `shared_prefix_boundary = num_new_computed_tokens + num_uncached` whenever attention matched further than Mamba (`kv_cache_manager.py:281-288`, coordinator `:895-899`). The scheduler stores it on the request (`scheduler.py:843`). `cache_blocks` then keeps the state block at that (block-floored) junction as the request reads past it. It can also stop a chunk there (`scheduler.py:458-462`); with chunk = block that stop is never needed.
**Prediction to test:** after a 0-hit mid-prompt edit, the same edit again, or any request sharing the prefix up to the edit, should hit at the block boundary just before the edit. In the next-turn case, the turn-2 request keeps a state at the end of the old answer's block, so turn 3 hits further.

**Agent loop (call k extends call k-1).**
- Every call keeps its prompt-end checkpoint and, if it had one, a junction checkpoint (the end of its attention match, usually the last block completed by call k-1's answer).
- Checkpoints from **all** earlier calls stay reusable, not only the latest, until evicted. Eviction is LRU over one shared block pool. Hashed blocks are appended to the free-queue tail, `get_new_blocks` pops the head and drops the hash (`block_pool.py:647-700, 723-747`), and a hit "touches" blocks back out of the free queue.
- There is no TTL. Lifetime depends only on how much new allocation happens after the request ends.
- `cached_blocks_this_step` (`single_type_kv_cache_manager.py:1587-1597`) stops a request from using a state that another request is writing in the same step. It waits one step instead.

## 2. How the scheduler shapes prefill in align mode

`Scheduler._mamba_block_aligned_split` (`v1/core/sched/scheduler.py:386-466`) runs on every prefill chunk, for running requests (`:606-609`) and for new ones (`:1002-1008`):
- `if end < prefill_end ...: aligned_end = end // block_size * block_size; if aligned_end > start or block_size <= max_prefill_tokens: end = aligned_end` (`:428-437`). Every non-final chunk is cut down to end on a block boundary.
- The final chunk, the partial tail, is exempt ("Exempt: the prompt's last chunk, whose slot decode advances to the boundary", `:424-427`).
- Extra stops (`:439-466`): the next boundary when a chunk starts mid-block; `last_cache_position = num_tokens - num_tokens % block_size` (`:416`, moved back one block under EAGLE/MTP, `:417-418`); the partial-tail boundary (only with `--prefix-match-unit` finer than the block; not used here because `hash_block_size` = gcd of the group block sizes = 832, `kv_cache_utils.py:750-751`); and the shared-prefix junction.
- `long_prefill_token_threshold` caps `num_new_tokens` beforehand (`:590-591, 984-986`). Inside the split it matters only when the block is wider than the chunk limit; then sub-block chunks are allowed and re-align at the next boundary.

Consequences:
- **832 is not required for hits.** The prompt-end checkpoint is always a forced stop. With 4096 the chunks would be 3328 tokens (4 blocks) and the prompt-end stop still lands. Checkpoints can never be **denser** than block-aligned chunk ends. In this build they are usually **sparser**: only the kept ones (retention 0).
- With `--prefix-cache-retention-interval N` (a multiple of 832) you keep one per N tokens, but only where a chunk ended. With 4096-token chunks the intermediate blocks are null (`allocate_new_blocks` fills skipped indices with null blocks, `single_type_kv_cache_manager.py:~1700-1706`).
- **832 is required for the exactness argument.** With 4096, a cold read chunks 0-3328-6656..., while a read after a hit at 1664 chunks 1664-4992...: different kernel calls. With 832, every chunk is [k·832, (k+1)·832) whatever the start, so the reads match.
- **Side effect worth knowing:** with `max_num_batched_tokens = 832`, a long prompt's chunk only runs when it gets the whole 832 budget. If any decode is scheduled in the same step, the remaining budget is under 832, `aligned_end` becomes 0, and the chunk is skipped (`scheduler.py:635-647`, reason 4: "Insufficient budget for a block-aligned chunk in hybrid models with mamba cache mode align"). New long prompts can therefore wait until the running decodes finish. This does not affect single-user tests; it matters for multi-user use.

## 3. Are blocks completed while decoding cached / checkpointed?

- **Attention KV: yes.** `allocate_slots` caches up to `min(total_computed_tokens + num_new_tokens, request.num_tokens)`, which includes output tokens (`kv_cache_manager.py:553-563`). The full-attention mask is `None`, meaning every block (`single_type_kv_cache_manager.py:484-503`).
- **GDN state, without MTP (retention 0): no.** The only kept boundaries are `num_prompt_tokens - 1` and the junction (`:459-461`), both inside the prompt. Decode-boundary state blocks are freed unhashed. That is why your answer block was not reused, and every kept state comes from the prefill path.
- **GDN state, with MTP (`num_speculative_tokens 5`): yes, by default.** Unless `--prefix-cache-retention-interval` is passed explicitly, `arg_utils.py:2392-2407` switches hybrid+EAGLE/MTP to dense (`None`). The mask returns `None`, so every non-null Mamba block that `cache_blocks` reaches is hashed, including blocks crossed while decoding. Their content is written by the spec-decode postprocess copy, `aligned_new_computed = (new_num_computed // block_size) * block_size; dest_block_idx = aligned_new_computed // block_size - 1` (`v1/worker/mamba_utils.py:460-470`), using the verify kernel's per-draft slots.
  - Under MTP the scheduler also moves the cacheable position back one block (`scheduler.py:417-418`), and the attention group matches one extra block and then drops it (`kv_cache_coordinator.py:836-850`).
  - If you set retention 0 explicitly with MTP, the comment at `arg_utils.py:2396-2399` says hits never happen ("EAGLE's tail-block drop makes [the replay boundary] unreachable").
  - **So with MTP on, a hit can land on a decode-produced state. Your exactness claim does not carry over to MTP-on without a guard.**

## 4. Memory per checkpoint (TP=2, per card)

Shapes (`model_executor/layers/mamba/mamba_utils.py:258-279`):
- `conv_dim = 128*16*2 + 128*48 = 10240`, giving conv state `(10240/2, 4-1+num_spec)`.
- Temporal (recurrent) state `(48/2, 128, 128)`.

Dtypes (`mamba_utils.py:96-109`; `models/config.py:801-815`):
- Conv state uses the model dtype (2 B).
- The SSM state uses the HF config's `mamba_ssm_dtype`, which is `float32` in `/mnt/fast-ai/llm-models/qwen3.8-27b-fp8/config.json`.

| item | no MTP | MTP 5 |
|---|---|---|
| conv state per layer | 5120×3×2 = 30,720 B | 5120×8×2 = 81,920 B |
| SSM state per layer | 24×128×128×4 = 1,572,864 B | same |
| content, 48 layers | 76,972,032 B (73.4 MiB) | 79,429,632 B (75.8 MiB) |

**Pages and padding.**
- Hybrid grouping (`v1/core/kv_cache_utils.py:1310-1321`) uses group_size = min layer count = 16, which gives 1 attention group and 3 GDN groups of 16 layers.
- The 64 layers share 16 tensors with one page per block id. All groups draw block ids from **one pool**.
- The Mamba page is padded up to the attention page (`platforms/interface.py:924-955`). The attention page per layer per card is 832 × 2(K,V) × 2 heads × 256 × 2 B = 1,703,936 B.
- One checkpoint uses one block id in each of the 3 GDN groups: 3 × 16 × 1,703,936 = **81,788,928 B ≈ 78.0 MiB per card** (156 MiB across both cards).
- One 832-token KV block is 16 × 1,703,936 = 27,262,976 B per card (= 832 × 32,768).
- **So one checkpoint = exactly 3 KV blocks = 2,496 tokens of KV.** About 94% of it is real content; the rest is padding.

With MTP the drafter's attention layer probably joins the attention bucket (17 layers, so group_size 17 with 3 padding layers in the GDN groups). A checkpoint is still 3 block ids; check the startup "padding layers" log line.

Live (unkept) state per running request: `2 + num_speculative_blocks` block ids per GDN group (`kv_cache_interface.py:888-892`). That is 6 block ids without MTP and 21 with MTP 5 (`num_speculative_blocks = num_speculative_tokens`, `layers/mamba/abstract.py:80-85`).

## 5. `--mamba-cache-mode` values

`Literal["all", "align", "none"]` (`config/cache.py:67, 188-196`):
- **none:** no prefix caching. Forced whenever prefix caching is off (`models/config.py:647-652`). One state slot per request (+spec).
- **align:** the default when prefix caching is on (`models/config.py:622-629`). It requires chunked prefill (`:641-644`) and chunked MM input (`config/vllm.py:2812-2817`). `mamba_block_size` is set equal to `block_size` (`platforms/interface.py:924-925`). The XPU platform rounds the block size up to a multiple of 64 for GDN (`platforms/xpu.py:~403-425`); 832 = 13×64 passes unchanged.
- **all:** caches the state at every `i*block_size` and reserves `cdiv(max_model_len, block_size)` state blocks per request (`kv_cache_interface.py:883-887`). **Refused for this model:** `qwen3_5.py:332-336` raises `NotImplementedError("Qwen3.5 currently does not support 'all' prefix caching, please use '--mamba-cache-mode=align'")`. Models without support are silently moved back to align (`models/config.py:630-640`).
  - Hypothetical cost here: 3 KV-block-equivalents of state per 832 tokens, i.e. state memory = 3× the KV memory (4× total per token), reserved per request up to max_model_len.

## 6. Hooks for chosen checkpoint positions

Existing knobs:
- **`--prefix-cache-retention-interval N`** (a multiple of 832) keeps periodic checkpoints. With chunk = block, `N = 832` gives a checkpoint at every boundary: `per_segment <= 1` returns `None`, i.e. dense (`single_type_kv_cache_manager.py:1508-1510`). **But** that also keeps decode-boundary states. There is no prompt-only limit, so it is not exactness-safe as is. Cost: 3 KV blocks per 832 prompt tokens, held as evictable LRU entries (not reserved), competing with KV.
- **Junction rule:** it already turns a miss into a hit for the *second* request with the same edit.
- **`cache_salt`:** it only changes the hash seed, separating cache namespaces. It cannot add checkpoints.
- **`vllm_xargs`** (chat request) maps into `SamplingParams.extra_args` (`entrypoints/openai/chat_completion/protocol.py:492, 705`), which is the natural carrier for a request parameter.

**Smallest change (overlay), with chunk = block = 832:**
In `SingleTypeKVCacheManager.cache_blocks` (`single_type_kv_cache_manager.py:459-461`), after building `reachable_boundaries`:
```python
sp = request.sampling_params
extra = (sp.extra_args or {}).get("state_checkpoints") if sp is not None else None
if extra:
    reachable_boundaries.extend(
        int(p) for p in extra if 0 < int(p) < request.num_prompt_tokens  # prompt-only
    )
```
- The existing mask code floors each boundary to 832 and marks that block.
- A server-side variant could instead scan `request.prompt_token_ids` for the `<|im_start|>` id and add those positions. That needs no client change, and puts a checkpoint at the block boundary at or before each message start.
- With `max_num_batched_tokens = 832`, every prompt boundary is already a chunk end, so the state block exists and only needs to be kept. With larger chunks you would also add the same positions to the `stops` tuple in `_mamba_block_aligned_split` (`scheduler.py:450-466`), like the junction stop, so that a chunk ends there.

What it must guarantee for bit-identity:
- (a) Checkpoints are only ever prompt positions produced by the prefill path (the `< num_prompt_tokens` guard).
- (b) Chunk boundaries after a resume equal the cold read's. True when every chunk is exactly [k·832, (k+1)·832). With bigger chunks you need "chunking restarts at each stop" plus the same stop list in the cold read, and no budget-dependent shortening.
- (c) Attention blocks reused up to the checkpoint are prefill-produced (see 7f).
- (d) Retention stays 0, so nothing else (decode boundaries) becomes hittable. Memory per added checkpoint: 78 MiB per card.

## 7. Paths where a hit could differ from a cold read

| # | difference | removed by our settings? |
|---|---|---|
| a | State dtype: SSM stored fp32, conv in model dtype. A cold read also stores/loads the state through the same cache between chunks, so there is no extra rounding. | Yes (no difference at all with chunk = block). Watch for `--mamba-ssm-cache-dtype` overrides. |
| b | Chunking after the hit: with 4096, cold = 0/3328/6656..., warm from 1664 = 1664/4992... | **Yes with 832**: every chunk is [k·832,(k+1)·832). |
| c | First chunk after the hit has a different length | Yes with 832 (always 832 or the final tail). |
| d | Concurrency shortening a chunk | Yes with 832: the aligned split gives either a full 832 or 0 (it waits), never a partial chunk (see the side effect in 2). With 4096 and concurrency, chunk sizes depend on load. |
| e | Final partial tail / "recompute last token" (`num_tokens - 1`) | Same tail as a cold read. Yes. |
| f | **Attention KV blocks completed during decode are hashed** (`kv_cache_manager.py:558`, full-attention mask None). For a duplicate hash, `get_one_block` returns the *first-inserted* block (`block_pool.py:61-72, 198-223`). In a 3-turn chain: turn 2 re-prefills the answer block and keeps a state at its end (junction), and also inserts its own copy of that KV block. Turn 3 then hits past that block, and its attention layers get **turn 1's decode-written KV** for it. A cold read would have prefill-written KV. | **No.** Untested by the 56/56 set (2 turns only). Test a 3-turn chain. Fix: cap `num_tokens_to_cache` at `request.num_prompt_tokens` (`kv_cache_manager.py:558`), or mask decode blocks in `FullAttentionManager`. |
| g | MTP on: dense retention keeps decode-produced GDN states (written by the spec-verify path), and hits can land on them | **No.** It needs the prompt-only guard (or an explicit retention of 0, which disables hits per the code comment). |
| h | Partial-block hits / copy-on-write (`--prefix-match-unit`) | Not active (hash unit = 832). |
| i | Initial state: a cold read starts from zero (`has_initial_state` false); a warm read loads the saved state | Same values as the cold read's in-between store/load. Fine with chunk = block. |
| j | Full-attention prefill with a cached prefix vs cold: the same query chunk [k·832,(k+1)·832) over the same KV length. Only the source of earlier KV differs (see f). | Yes, if f is closed. |

## Single most useful change for an agent that edits mid-context

Keep the GDN state at the **block boundary just before each message start** of the prompt (prompt positions only), using the `cache_blocks` overlay above, and keep chunk = block = 832. An edit in message *m* then resumes from the boundary at or before the start of *m* instead of from 0. Each checkpoint costs about 78 MiB per card (3 KV blocks).

Land it together with the one-line cap that stops caching **attention** blocks completed during decode (item f). Otherwise later turns can mix decode-written KV into a "cached" read.

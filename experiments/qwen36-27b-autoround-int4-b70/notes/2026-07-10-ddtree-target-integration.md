# DDTree target integration and KV commit repair (2026-07-10)

## Status

Active architecture lane; not a promoted result and not eligible for
LocalMaxxing yet. The real mixed-SWA DFlash draft now drives a target-verified
15-node DDTree through branch-aware full attention and GDN state. Eager
execution and the split PIECEWISE graph are mechanically exact. The active
gate is a single target `FULL_DECODE_ONLY` graph with an independently
PIECEWISE DFlash draft, followed by an acceptance-transfer investigation.

Current promoted Qwen27 result remains `68.23626314761921 tok/s`.

## What now works

- DFlash builds a best-first runtime tree and transports token IDs, parents,
  and logical depths through request/scheduler/worker metadata.
- Target RoPE uses logical depths while target KV writes use distinct physical
  slots.
- XPU full attention uses an exact boolean ancestor mask.
- all 48 GDN layers use the native graph-static whole-tree recurrent kernel.
- greedy sampling walks only target-argmax-matching children and emits a
  target-owned replacement/bonus token.
- accepted GDN state and full-attention KV state are promoted into canonical
  running slots before the next verifier step.
- the DFlash proposer receives only root plus accepted-path target hidden rows;
  rejected sibling rows do not become draft context.

## Endpoint failure and exact root cause

The first 15-node eager endpoint produced coherent text, `cached_tokens=0`,
and real tree acceptance, but diverged deterministically from a no-spec oracle
at generated token 49 on the seasons smoke. The following bisection isolated
the fault:

| Probe | Result | Meaning |
|---|---|---|
| three 15-node runs | identical speculative hashes; first oracle mismatch at token 49 | stable implementation issue, not request cache reuse |
| fresh replay of the exact 49-token prefix | next token matched oracle | accumulated transaction drift |
| one-node DDTree | all 64 tokens matched oracle | root GDN/commit path is exact |
| forced 15-node top-1 chain | all 64 tokens matched oracle | multi-row verifier and GDN promotion are exact when relocation is unnecessary |
| device sync before/after commit | unchanged mismatch | not an async ordering race |
| `flatten(...).index_copy_` | unchanged mismatch | flatten materialized another temporary for the interleaved cache layout |
| basic integer slot views | all 64 tokens matched oracle | noncanonical KV relocation was the defect |

The original destination expression was:

```python
kv_cache[:, destination_blocks, destination_offsets].copy_(staged)
```

Both block and offset are advanced indices, so PyTorch returns a temporary.
`copy_` updated that temporary and never scattered into the real KV cache.
Linear chains appeared correct because their accepted rows were already in
canonical slots. Sibling paths left stale canonical K/V rows.

The exact Python reference now uses basic integer indexing per ordered slot
pair. The production implementation is native
`torch.ops._xpu_C.kv_cache_copy_slots`: one SYCL kernel walks overlapping slot
pairs in order for each independent K/V element, with no D2H slot list and no
per-token Python kernel launches.

## Native validation

Build:

```bash
cd /home/steve/src/vllm-xpu-kernels
cmake --build build/xpu-c-only-2025 --target _xpu_C -j2
```

Installed binary SHA-256:

```text
4c67f64f30d7fdb46836984b7e631afec6baac399b9bb7288fd6352e318af0ec
```

Correctness command:

```bash
ZE_AFFINITY_MASK=0 ONEAPI_DEVICE_SELECTOR=level_zero:0 \
LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib \
/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/check-xpu-kv-cache-copy-slots.py
```

Result: exact pass for BF16, FP16, and FP32 on a deliberately non-contiguous
interleaved `[K/V, block, token, head, dim]` cache, including overlapping
`[2,3,7,10] -> [1,2,3,4]` ordered compaction.

The native endpoint then matched both the Python basic-copy reference and the
no-spec oracle for all 64 seasons-smoke token IDs.

## Cold-suite diagnostic

The eager Python-reference endpoint and no-spec oracle each ran the fixed 12
prompt suite once, with 64 generated tokens and `cached_tokens=0` on every
request:

- DDTree artifact:
  `data/qwen36-27b-autoround-int4-b70-diagnostics/qwen27-ddtree-basiccopy-eager-suite64-20260710.json`;
- no-spec artifact:
  `data/qwen36-27b-autoround-int4-b70-diagnostics/qwen27-ddtree-nospec-eager-suite64-20260710.json`.

This is diagnostic only. Eager DDTree measured `17.8169 tok/s` median for the
first 50 generated tokens; graph-none no-spec measured `11.0418 tok/s`. Neither
is a headline candidate. Seven of 12 first-pass output hashes matched. A direct
rerun of the code-review row changed from a token-30 mismatch to a complete
64-token match, consistent with known XPU technical-argmax instability. Do not
claim full baseline hash parity from this evidence; use repeated/crossover and
the normal repeat64 quality gate after the graph endpoint is stable.

## Graph integration and bottleneck isolation

The first PIECEWISE endpoint captured successfully but emitted deterministic
wrong tokens. A no-spec PIECEWISE control remained bit-stable, so this was not
generic XPU graph instability. Inspection of the compiled graph found that the
Python DDTree branch in `gdn_linear_attn.forward_xpu` had been resolved during
AOT tracing with non-tree dummy metadata. Replays therefore executed the
ordinary recurrent kernel even when live metadata described a tree.

The structural repair moves DDTree dispatch into
`vllm::gdn_attention_core_xpu`, which is a stable custom-op boundary. The
compiled model always invokes that op, while its eager implementation reads
the live `GDNAttentionMetadata` and chooses the native tree kernel. Capture
dummy metadata also initializes graph-static DDTree GDN source tables and uses
the capture token count as its sequence bound. With these changes, three cold
64-token responses were exact against both the eager DDTree endpoint and the
no-spec graph oracle, with `cached_tokens=0` throughout.

The exact split graph is not fast enough:

- fixed realistic suite, 12 prompts once, 128 generated / first-100 metric;
- median `17.60586624160095 tok/s`, p10 `16.6591`, mean `17.9555`;
- median TTFT `5124.5 ms`, median full-request wall throughput `10.418 tok/s`;
- `cached_tokens=0` on every request;
- diagnostic artifact:
  `data/qwen36-27b-autoround-int4-b70-diagnostics/qwen27-ddtree-gdnsplit-graph-suite128-20260710.json`.

Removing `vllm::gdn_attention_core_xpu` from the split list behind
`VLLM_XPU_DDTREE_CAPTURE_GDN_CORE=1` made the exact tree kernel part of each
PIECEWISE graph segment. This preserved exact output and reduced a warm smoke
step by about `13.7 ms` (roughly 10%), but total step latency remained about
`127 ms`; capturing GDN alone is therefore a real but insufficient win.
`cudagraph_copy_inputs=true` is not a fallback: it reproduces the known XPU
Inductor bounds assertion during startup.

A synchronized DFlash subprofile now provides the useful draft cost table for
the row-16 endpoint:

| DFlash component | Approximate ms/step |
|---|---:|
| context K/V setup and cache insert | `1.0-1.1` |
| five-layer draft forward | `6.0-6.2` |
| shared INT8 full-vocabulary LM head, 15 rows | `3.5-3.9` |
| top-15 + log normalization | `0.9-1.1` |
| compact D2H tree inputs + CPU heap + H2D IDs | `0.22-0.27` |
| complete synchronized draft region | **`14.1-14.3`** |

The draft is material but is not the earlier coarse `~70 ms` attribution. The
remaining major cost is the 16-row target verifier plus its many graph split
boundaries. The next graph experiment is `FULL_DECODE_ONLY`, keeping prefill
and the DFlash model PIECEWISE while capturing the target verifier as one
decode graph.

That experiment exposed a reusable vLLM bug: the draft config was a shallow
`dataclasses.replace` of the target config, so XPU's required FlashAttention
fallback from FULL to PIECEWISE mutated the target's shared
`CompilationConfig` too. DFlash now owns a separate compilation config and
runtime dispatcher. This lets the target retain FULL decode capture while the
draft remains PIECEWISE. The first full compile also found the root filesystem
full of `61 GiB` of generated vLLM cache entries; only pre-July-9 compile/AOT
cache was pruned, recovering `52 GiB`. No models, source, patches, logs, or
benchmark evidence were removed.

## Artifacts

- vLLM composite WIP patch (base
  `e7213ba8e13b74d7bfa3cbc05435a45df90eb76a`):
  `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-ddtree-target-integration-wip-20260710.patch`,
  SHA-256
  `19ae39c181ab5266acff0ffbd4e74549cc27608946d2e0f529bcaa27413c4cff`;
- native GDN-tree plus ordered-KV-copy stack:
  `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-kernels-qwen27-ddtree-native-stack-v2-20260710.patch`,
  SHA-256
  `d9c77973f8d4edf4b7f388b29e5795fa9a11b66c8fda5fd1b6fe2b536df9f9ff`;
- native correctness guard:
  `scripts/check-xpu-kv-cache-copy-slots.py`.

Both source trees contain unrelated historical local changes. The patch files
are durable experiment snapshots, not clean upstream-ready commits.

## Remaining gates

1. Complete the 16-row target `FULL_DECODE_ONLY` startup and exact-token smoke;
   the DFlash draft must remain on its independently resolved PIECEWISE mode.
2. Confirm dynamic parent masks and GDN source tables are refreshed on every
   full-graph replay; keep prefill and non-tree request shapes out of headline
   data.
3. Re-measure step latency and accepted visible tokens per verifier step. The
   current endpoint acceptance seen during eager diagnostics is closer to
   `2.5-2.8` visible tokens/step than the offline `3.9355` estimate, so explain
   that gap before assuming a `>100 tok/s` ceiling.
4. Run the fixed realistic 128-token diagnostic. Only proceed to promotion if
   it beats `68.236` with `cached_tokens=0` throughout.
5. Run exact short canaries, repeat64, 1K needle, baseline comparison, and
   same-window/card-order crossover. Treat sub-2% movement as variance until
   crossover supports it.
6. Submit to LocalMaxxing only after a strict fresh, target-verified,
   quality-passing record. No eager or synthetic diagnostic belongs there.

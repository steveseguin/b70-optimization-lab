# Laguna DFlash context-KV workspace preregistration

Date: 2026-07-25 America/Toronto

Status: **promoted exact four-card component pass. The third packet completed
`exact_component_pass` on all four physical cards; a separately committed and
sealed offline audit corrected the projected-V view-offset rule and returned
`exact_four_card_component_pass`. No endpoint, benchmark, or submission action
is authorized**.

## Purpose

The approved record is the exact persistent-attention-metadata Breakable-graph
stack at `94.92003934159611 tok/s`, LocalMaxxing
`cmrzrd4tf001ipa013xpx4kid`, with vLLM
`ef334233deabeaeedb607056a2db1c90edb3887c` and XPU kernels
`4772f727590c51b72add79350b913d098cf67872`.

The completed current-stream diagnostic and its source map found no honest
new target-MoE or attention-adjacent candidate. W1 N32/N128, QKV/O occupancy,
remote-zero, fused expert transactions, native shared projections, attention
capture, collective capture, and gather variants are already negative,
terminal, unsafe, or absorbed by the record. The source audit did identify a
separate unoptimized DFlash path: Laguna's eager context-KV precompute creates
new intermediate tensors on every proposal cycle.

The prior persistent metadata record changes only target q2-through-q8
attention metadata. It does not touch the DFlash model's six-layer context-KV
projection, so this lane is materially distinct.

## Frozen candidate

The candidate starts directly from approved record vLLM
`ef334233deabeaeedb607056a2db1c90edb3887c`. Its sole selector is:

```text
VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE=1
```

The frozen implementation is vLLM commit
`4459910e2ac5a7b552887fc0a3f3e3cf9a4701c0` in
`/home/steve/src/laguna-vllm-dflash-persistent-metadata-20260725`.

The selector is default-off and must fail closed unless all of these hold:

- Intel XPU;
- draft architecture `DFlashLagunaForCausalLM`;
- six DFlash layers with hidden size 3072 and target-layer IDs
  `[1,10,19,29,38,47]`;
- causal DFlash, depth seven, greedy draft sampling, and standard rejection;
- configured maximum one sequence, synchronous scheduling, TP4, PP1, DP1,
  no LoRA, and BF16 model dtype.

The later component and endpoint controllers, rather than the model helper,
own the rest of the frozen record identity: EP4, Breakable PIECEWISE graph,
the existing target metadata/elementwise/QKNorm selectors, no async request
boundary, exact model revisions, and the pinned XPU kernels.

Only steady context widths 1 through 8 use persistent buffers. Larger prompt
or prefill context widths retain the incumbent allocation path.

For each exact context width, the candidate lazily owns four non-checkpoint
buffers with the incumbent shapes and layouts:

1. layer-major normalized context states `[L,C,H]`;
2. BMM output `[L,C,2*kv]`;
3. contiguous K/V-packed output `[2,L,C,nkv,hd]`; and
4. normalized K `[L,C,nkv,hd]`.

The operation order remains exactly:

```text
RMSNorm
-> torch.bmm
-> separate BF16 bias add when present
-> permute plus contiguous-layout copy
-> K RMSNorm
-> in-place RoPE
-> unchanged per-layer KV-cache writes
```

No operation is fused, removed, reassociated, quantized differently, moved
across a BF16 store, or reordered. `positions.repeat`, RoPE, cache slot
mapping, cache writes, query attention, dense MLP, logits, draft argmax,
rejection, target verification, graph topology, and collective order remain
unchanged.

Every workspace tensor and all static context-KV weights are guarded by
data pointer, storage offset, shape, stride, dtype, and device signatures.
Workspace tensors must be mutually disjoint and may not alias context inputs
or weights. Any drift after first use is a hard error; the candidate may not
silently rebuild, fall back, or continue.

## Required validation ladder

Before any XPU action:

- focused CPU/reference tests must prove byte equality with the allocation path
  for changing context widths 1, 3, and 8 and repeated inputs; this is
  structural host evidence, not XPU raw-bit proof;
- exact-width buffers must retain object and tensor identity across reuse;
- width greater than eight must take the literal incumbent path;
- every workspace base, every static weight, projected-K handoff, input alias,
  and stream-capture drift must fail closed;
- a positive record-scope contract and one-field platform, architecture,
  layer/shape, target-ID, causal, depth, sampling, batch, scheduling, TP, PP,
  DP, LoRA, and dtype failures must be tested;
- selector-off source and behavior must remain the incumbent;
- Ruff, formatting, whitespace, relevant vLLM tests, and independent
  read-only review must pass;
- the exact vLLM source must be committed and the worktree clean.

Those host-only requirements passed before the source freeze:

- focused command:
  `PYTHONPYCACHEPREFIX=/tmp/laguna-dflash-workspace-pycache
  /home/steve/.venvs/deepseek-v4-xpu/bin/python -m pytest -q
  tests/models/test_laguna_dflash_context_kv_workspace.py`;
- result: `38 passed`, with no XPU use;
- full-file pre-commit checks passed for `vllm/envs.py`,
  `vllm/model_executor/models/laguna_dflash.py`, and
  `tests/models/test_laguna_dflash_context_kv_workspace.py`;
- `git diff --check` passed and the source commit left a clean worktree;
- two independent read-only reviews approved the narrow host-only source
  freeze. Both reviews explicitly withheld XPU, endpoint, throughput, and
  record approval pending the component gate below.

Only then may a separate committed component packet authorize an XPU run. The
component gate must cover all four physical B70s, all steady widths 1 through
8, changing BF16 context states, with and without KV bias if supported, and
raw-bit equality at projected K, projected V, normalized K, RoPE K, and final
cache-write boundaries. It must verify stable workspace pointers after first
use and unchanged slot mappings/cache locations.

The component packet is now implemented, but remains unexecuted until its
source is committed, the main worktree is clean, and independent re-review
approves it:

- `tools/run_laguna_dflash_context_kv_component.sh` owns the fresh one-shot
  internal-NVMe campaign and four sequential one-visible-card legs;
- `tools/create_laguna_dflash_context_kv_consumption.py` acquires the external
  packet-specific marker with `O_CREAT|O_EXCL|O_NOFOLLOW`, full-write and
  file/directory fsync semantics before any native import or tensor work;
- `tools/run_laguna_dflash_context_kv_component.py` writes a durable
  pre-import seal, verifies the frozen device/source/model identities, loads
  the real TP4 rank-local DFlash checkpoint slices, passes those slices through
  the actual `DFlashLagunaModel._build_context_kv_buffers` helper, and compares
  incumbent allocation against the frozen workspace helper;
- `tools/analyze_laguna_dflash_context_kv_component.py` independently rejects
  missing or malformed boundary hashes, shapes, strides, byte counts, context
  freshness, workspace-pointer reuse, checkpoint-to-builder linkage, cache
  layers, source identities, or physical-card mappings;
- `tools/test_analyze_laguna_dflash_context_kv_component.py` contains CPU-only
  tamper tests for the analyzer.

The real checkpoint arm is bias-free, as required by its hashed config and
the absence of all six QKV bias keys. A separately labelled synthetic-bias arm
exercises the source branch without representing it as the published model.
The downstream check uses the config-derived actual YaRN RoPE parameters and
the real `FlashAttentionImpl.do_kv_cache_update` implementation with its
native BF16 cache layout and slot mapping. It is still component evidence, not
an endpoint or TP4-generation claim. Width zero remains covered by host source
tests rather than launching an unsupported zero-range XPU RMSNorm; the XPU
fallback check uses width nine.

The exact committed packet is consumable only once across run directories:
before any native import or tensor work, the launcher must acquire an
`O_EXCL` packet-hash-specific marker under the internal-NVMe authorization
root. A failed packet therefore requires a new reviewed commit rather than a
rerun or rescued sample. Each physical-card leg also contains a bounded
non-generative XPU capture microcase. It must observe eager false, capture
true, the exact candidate `RuntimeError`, and unchanged workspace registry,
workspace pointers/bytes, cache bytes, and input bytes.

Host packet validation passes Python compilation, Ruff, formatting, Bash
syntax, whitespace checks, and 22 analyzer tamper tests. Two independent
read-only reviews approved committing and consuming the exact packet once for
component-only XPU evidence. No XPU was used for these checks or reviews.

## First packet failure

Main commit `bd84a0384202676fd12d2731545c7638f8d58bab` was consumed once at:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-dflash-context-kv-component-bd84a0384-4459910e2-20260725T062703Z
```

It failed closed on physical-card leg zero in 1.8 seconds, before the
pre-import seal, native imports, tensor work, or any accepted result:

```text
Laguna DFlash context-KV component: four-card physical mapping drift
```

Root cause is the discovery contract, not the candidate. `xpu-smi discovery`
inherits `ZE_AFFINITY_MASK`; inside a rank-zero one-visible-card worker it
correctly reports only physical card zero, while the worker incorrectly
required the unfiltered four-card list. The packet remains permanently
consumed and must not be rerun.

The repair captures and fsyncs an unfiltered four-card discovery artifact in
the launcher after the external packet is irreversibly consumed and before
applying per-leg affinity. Each worker now requires that artifact to match the
frozen four-card map and durably records its own affinity-filtered discovery,
which must contain exactly the selected card. The analyzer independently
parses, hashes, links, and validates both retained JSON artifacts. This
repaired source received two independent approvals and has one component-only
XPU execution after it is committed cleanly.

## Second packet failure and card-zero pass

Repaired main commit `c547b2a434c7f3ec852a02ca614c8a318ee58b1e` was consumed
once at:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-dflash-context-kv-component-c547b2a43-4459910e2-20260725T063404Z
```

Physical card zero completed the full component and wrote
`status=exact_component_pass`: both actual-no-bias and synthetic-bias arms
passed 16/16 changing-context rows, widths one through eight created and
reused stable workspaces, width nine stayed incumbent, every recorded BF16
boundary and all six cache layers matched, and the capture-true rejection
left workspace/cache/input state unchanged.

The packet then failed closed on card one before its pre-import seal:

```text
Laguna DFlash context-KV component: affinity-filtered physical-card mapping drift
```

The remaining harness error is another documented `xpu-smi` behavior:
after affinity filtering, the sole visible card is renumbered to logical
`device_id=0`. The stable physical identity fields still correctly report
card one's UUID, BDF, and DRM node. The repair therefore requires logical
device zero in every filtered artifact while binding UUID/BDF/DRM to the
selected unfiltered physical ordinal. The `c547b2a43` packet is permanently
consumed and must not be rerun.

Two independent reviews approved the narrow ordinal repair for one new
component-only packet after it is committed cleanly.

## Third packet: four card passes, analyzer false negative

Main commit `145050c5df2a7e0d9f6d056b7b1f5b1f61072d8e` was consumed once
at:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-dflash-context-kv-component-145050c5d-4459910e2-20260725T063712Z
```

All four card workers completed with `status=exact_component_pass`, empty
stderr, the full 32-row actual/synthetic matrix per card, capture-true
fail-closed evidence, and every worker-side raw-bit comparison passing. The
offline analyzer then rejected:

```text
rank 0/actual_no_bias/C1/r0/projected_v: storage offset drift
```

This is an analyzer bug. `projected_v` is the second dim-zero view of the
contiguous `[2,L,C,nkv,hd]` packed workspace, so its correct storage offset is
`L*C*nkv*hd`, or 1536 elements at C=1. The analyzer incorrectly required zero
for every tensor view. The repair validates offset zero for K and the owning
buffers, and exactly `6*C*2*128` for V. It also verifies frozen tool bytes from
the evidence commit rather than the current checkout and permits a new
analysis artifact only in a fresh owner-private child of the dedicated
internal-NVMe analyses root. That artifact records and verifies the clean
committed analyzer source SHA and exact analyzer-file SHA256. No XPU or worker
rerun is needed or allowed.

Two independent reviews approved committing this analyzer-only repair and
running it once against the sealed `145050c5d` evidence. They authorized no
XPU, worker, benchmark, endpoint, or submission action.

The offline audit at
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/analyses/laguna-dflash-context-kv-component-145050c5d-a97e9c086-20260725T064453Z`
passed and was sealed with its own manifest. Across the four physical cards,
the durable matrix contains 128 changing-input rows and 1,536 raw equality
assertions: 768 recorded operation-boundary comparisons and 768 six-layer
cache comparisons. Every comparison passed; weights, workspace pointers,
capture-rejection state, caches, and inputs stayed within the frozen contract.
Three independent read-only audits approved promotion as component-only
evidence. Preserve the structured
[`data` summary](../../../data/laguna-s-2.1-dflash-context-kv-component-20260725.json).

The next authority is design only: construct a fresh non-timing TP4
full-runtime exactness gate using the real loaded model/cache lifecycle and
selector-off/on paths. It must validate full greedy target/draft/rejection
token arrays and text before any cold performance crossover is authorized.

No endpoint is authorized by a component pass. A later graph-vs-graph cold
crossover may be constructed only if every card is bitwise exact and the
candidate shows a conservative material saving in the complete six-layer
context-KV precompute. That crossover must retain fresh cold prompts, one
active generation, zero cached tokens, depth seven, exact teacher/cross-leg
token arrays and text, no retries, and the approved graph/metadata stack.

No LocalMaxxing payload or submission is allowed unless the lower independent
candidate start is a real verified improvement over `94.92003934159611`
tok/s and every frozen causal gate passes.

## Explicit exclusions

- Do not bundle proposer `CommonAttentionMetadata` persistence into this
  treatment.
- Do not change DFlash depth, draft logits, token IDs, acceptance semantics,
  target verification, async scheduling, or request history.
- Do not pre-warm context-width workspaces with hidden model generations.
- Do not reuse terminal target-side components or weaken their old gates.
- Do not use the external USB drive for live model reads or run artifacts.

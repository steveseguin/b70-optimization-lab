# DeepSeek V4.1 Flash on six B70: ideas from other projects and papers (2026-11-11)

Survey for `2026-11-11-dsv41-speed-strategy.md` (helper output, nothing run on the cards).

Our numbers, from the lane note:
- one-token step 11.7 ms (85 tok/s), 1,051 launches per card per word;
- an empty back-to-back launch costs 2.1-2.4 us (§28);
- an exchange costs ~13 us (launch 2.4, flag leg ~2.5, load leg ~5-6), 160 exchanges per word;
- 1.69 GB of weights per card per word, ~1.29 GB of it dense (does not depend on routing, so it can be loaded
  before the input is ready);
- kernel time already equals wall time, so the host is not the limit: the gaps are inside and between kernels.

There are 4 exchanges per layer (o_a out, o_b out, SwiGLU out, MoE out), and that is the minimum: splitting K
across cards would change the order of the sums, and expert-sliced weights would not fit.

**In short:** the projects that reach 60-80 % of bandwidth at batch 1 all do the same thing. They run one persistent
kernel, load weights before waiting on the input, and replace kernel boundaries with counters in memory (Hazy,
Cohere, MPK). That is the only route found to 200 tok/s. Two cheaper steps come first and tell us whether it will
pay: Intel's own kernel-switch benchmarks, and kernels chained through flags with no barrier between them. Prompt
reading needs larger blocks with the tokens grouped by expert, plus an inner loop that decodes each weight once
per block.

## Ranked table

| # | Technique | Where (code to read) | Replaces in our engine | Expected effect | Lossless | Effort |
|---|---|---|---|---|---|---|
| 0 | Measure kernel-switch and barrier cost on B70 (enabler) | `intel/compute-benchmarks`: `ulls_benchmark/definitions/kernel_switch_latency.h`, `multi_kernel_execution.h`, `gpu_cmds_benchmark/definitions/barrier_between_kernels.h` | nothing (decides 1 and 2) | Splits the ~2.4 us per launch into dispatch, barrier and flush. Bounds 1-2 (≤ ~2.5 ms per word) | n/a | hours |
| 1 | Persistent kernel per layer phase, then per word: weights loaded before the input counter, exchanges inside | Cohere `cohere-ai/cohere-megakernel` (`src/decode`); Hazy `HazyResearch/Megakernels` (`include/{controller,loader,consumer,storer}.cuh`, `demos/low-latency-llama`, branch `throughput` for TP); MPK `mirage-project/mirage` `include/mirage/persistent_kernel/` | ~26 launches per layer, in-order barriers, each kernel's ramp and tail, weights waiting for inputs | 11.7 → ~5.5-7 ms: 145-180 tok/s plain, ~190-230 guessing | yes | large (2-4 weeks, staged) |
| 2 | Flag-chained kernels with no barriers (emulates CUDA PDL), recorded once, replayed | CUDA PDL (`cudaGridDependencySynchronize`, FlashInfer/SGLang `enable_pdl`); on Intel: L0 regular list without barriers, or a SYCL graph with no edges | the in-order barrier; part of the weights-after-input stall | −1.5 to −3 ms (100-125 tok/s) if B70 overlaps walkers | yes (same kernels) | ~1 week |
| 3 | LL / Lamport exchange: flag inside the data | NCCL `src/device/prims_ll.h`; TRT-LLM `cpp/tensorrt_llm/kernels/communicationKernels/allReduceFusionKernels.cu` (`allreduce_fusion_kernel_oneshot_lamport`); vLLM `csrc/custom_all_reduce.cuh` (`barrier_at_start`, `cross_device_reduce_1stage`) | `XchgPull`'s separate flag leg | 13 → ~9-10 us alone, ~5-6 us inside 1-2: −0.4 to −1.1 ms | yes with an LL flag word or a NaN sentinel (not -0.0 as is) | days (`xchg_lat_bench` exists) |
| 4 | Prompt: 128-512-token blocks, layer by layer, tokens grouped per expert | vLLM `csrc/moe/moe_align_sum_kernels.cu` + `fused_moe.py`; llama.cpp `ggml_cuda_mul_mat_id` (`ggml-cuda/ggml-cuda.cu`); DeepGEMM contiguous layout; vLLM Intel B-series blog (persistent MoE GEMM, atomic counter) | 16-token blocks where each expert serves ~1.1 tokens | expert bytes ~4x lower, grid decode shared by ~4-8 tokens: 300 → ~450-600 tok/s | yes | medium-large |
| 5 | Prompt: decode a weight tile once into registers/SLM, inner loop over tokens = mul + add only | llama.cpp `ggml-cuda/mmq.cuh` tile structure; sycl-tla mixed-input BMG grouped GEMM examples, with DPAS replaced by FPU mul+add | ~4 instructions per weight-token (§31 d2) | needed for 1,000+: ≤2.5 ops per weight-token at ~70 % ALU use gives ~1,000-1,300 at 3K | yes (`-ffp-contract=off` kept) | medium |
| 6 | Suffix-tree / prompt-lookup drafts beside DSpark | SuffixDecoding arXiv 2411.04975, `snowflakedb/ArcticInference` (`arctic_inference/suffix_decoding`) | DSpark-only drafts | agent/code/quoting text: 150-250 tok/s; neutral elsewhere. Not headline-eligible (AGENTS.md bans n-gram/history drafts in final gates) | yes (full-model check) | small-medium (host) |
| 7 | 2D block loads, LSC prefetch, cache hints for weight streams | sycl-tla `include/cute/atom/copy_traits_xe_2d.hpp`; ESIMD `lsc_load_2d`/`lsc_prefetch_2d`; `sycl_ext_intel_cache_controls`, `sycl_ext_oneapi_prefetch` | 16 B-per-lane block reads | more bytes in flight per thread; mostly pays inside 1-2: −0.3 to −1 ms | yes | medium |
| 8 | Two micro-batches in prompt blocks: one half's exchange during the other half's compute | SGLang `python/sglang/srt/batch_overlap/`; `deepseek-ai/profile-data`; Hazy TP "interleaving" | serial compute → exchange in blocks | +5-10 % prompt reading (more at big blocks) | yes | medium |
| 9 | Guess length that counts the expert union | Cascade arXiv 2506.20675; EcoSpec arXiv 2607.12696 | `OWN_SPEC_TAU` rule | +5-10 % guessing; more after 1 | yes | small |
| 10 | Prompt sparse attention: selected KV rows shared across queries and heads | FlashMLA sparse prefill (`flash_mla_sparse_fwd`, MQA mode) | per-token attention in blocks | long documents: +10-20 % reading | yes | medium |
| 11 | Cross-card MoE tiles in one persistent kernel | FlashDMoE arXiv 2506.04667, `osayamenja/FlashMoE` (`csrc/`) | reference for 1's MoE part | part of 1 | yes | reading only |
| 12 | L2 prefetch of predicted experts (draft's or last word's) | Pre-gated MoE arXiv 2308.12066; DraftExpert 2607.24434 | expert loads that start after the router | ≤ −0.2 ms | yes | small inside 1 |
| 13 | SYCL graph for host submission alone | llama.cpp `ggml/src/ggml-sycl/ggml-sycl.cpp` (graphs off by default: "not yet faster") | per-launch host calls | ~0 alone; only a container for 2 | yes | small |
| 14 | Exact prefix reuse across agent turns | DeepInfer "SWA bounded replay"; vLLM/SGLang prefix cache | re-reading the shared prefix | serving only; not headline-eligible (cache reuse rule) | yes | medium |

## Details

**0. Measure first (hours).** Intel's `compute-benchmarks` has the probes we need. `KernelSwitch` measures "time
from end of one kernel till start of next", with `ioq`, `barrier` and `ctrBasedEvents` switches.
`BarrierBetweenKernels` covers "a barrier ... including potential cache flush". `MultiKernelExecution` and
`QueueConcurrency` cover out-of-order lists. If the barrier plus flush is most of our 2.4 us and walkers overlap
in a barrier-free list, #2 is cheap and real; if not, go straight to #1. Hazy measured 2.1 us per dummy CUDA
launch (1.3 us with graphs), so our 2.4 us is ordinary. What is unusual is our launch count: 1,051 per word
against ~112 for their Llama-1B.

**1. Persistent kernel.**
- Cohere's open decode megakernel is the closest match: a 30B-A3.3B MoE at batch 1 on one H100 runs at 292 tok/s,
  62 % of speed of light and 1.58x vLLM with CUDA graphs. The design:
  - one work-group per SM and a task list per SM, with a fixed 32-int descriptor;
  - 16 opcodes built from existing kernels under one calling convention ("no compiler needed");
  - counters in global memory;
  - weights loaded before the dependency wait;
  - routing-dependent expert tiles taken from an atomic queue by "claimer" tasks.

  Their pitfalls: counting barriers drift into deadlock without checked arrival counts; shared-memory paging was
  dropped as too complex; dense schedulers did not carry over to MoE.
- Hazy's Llama-1B kernel reaches 78 % of H100 bandwidth. Shared-memory pages are handed to the next instruction so
  its loads start early, and the down projection has per-chunk counters. A warning for us: even there,
  activation store/load plus sync took ~250 of ~600 us on B200.
- The TP branch runs all-gather and reduce-scatter in the kernel: storer threads issue the peer stores, then raise
  a flag.
- MPK (OSDI '26) gains 1.0-1.7x over SGLang/vLLM; its compute-communication overlap alone gives 1.1x on 4-GPU TP.

For us, a card's work-groups load the next op's weight slice into registers or SLM while the previous exchange is in
flight. There is room: 32 cores x 8 XVE x 64 KB = 16 MB of registers, plus SLM, against 2-10 MB per op slice. Then
each work-group waits on the counter and computes. Budget:
- weights at 75 % of 600 GB/s: 3.75 ms;
- 160 exchanges at ~6 us: ~1 ms;
- serial small ops without launches: 1-1.5 ms;
- attention: ~0.8 ms.

Partly overlapped, that gives 5.5-7 ms.

Intel specifics:
- Co-residency: `zeKernelSuggestMaxCooperativeGroupCount` + `zeCommandListAppendLaunchCooperativeKernel`, or
  `sycl_ext_oneapi_root_group` (`max_num_work_groups`) with `sycl_ext_oneapi_forward_progress`.
- One sub-group size; today kernels use both 16 and 32.
- Large GRF.
- One polling sub-group per work-group while the rest wait at a barrier. Spinning draws power, and the 230 W cards
  drop clocks (§24).
- Peer pointers stay direct arguments (`DisableIndirectAccess`).

Staging: one layer's dense attention chain on one card (S1), then the MoE half with claimer tasks, then the
exchanges, then the whole word.

**2. PDL emulation.** NVIDIA added Programmatic Dependent Launch because the next kernel's prologue (weight loads)
waits for the previous kernel's tail. We can get the same effect without a new API:
- Append the word's kernels to a Level Zero regular command list with no barriers or events, or build a SYCL graph
  with no edges.
- Each kernel runs `load weights → wait counter ≥ k → compute → fence → counter += 1`.
- Walkers dispatch in order, so earlier kernels' groups are resident before later ones spin, the argument stream-K
  and decoupled look-back rely on.
- Native handles come from `sycl::get_native<backend::ext_oneapi_level_zero>`; the engine already links `ze_loader`
  (`tools/l0_launch_lock_bench.cpp`).
- Replay also removes the six submit threads' lock time.
- The failed L2-prefetch riders (§15-18) work in this form, because nothing waits for the prefetch groups.
- Risk: the driver may still insert a per-walker stall, which #0 shows.

**3. Exchange protocol.** Today the producer stores locally, writes its sequence number into each peer's flag
word, and the consumer then loads the slice: two legs. Options:
- **LL-pull:** the consumer polls the peer's slice; each 8 B word holds 4 B of data and a 4 B sequence number
  (NCCL LL), so the first good poll returns the data. Saves ~2.5 us; doubles the bytes (fine at 3.4 KB per card).
- **LL-push / Lamport:** the producer writes data with its flag into the consumer's memory, and the consumer polls
  locally. That is one posted-write latency. Pushes ran ~1 GB/s (§21), but the one-token push already beats pull
  (8.6 vs 12 us); bench 1-3 tokens.
- **Sentinel:** TRT-LLM's -0.0 sentinel rewrites real -0.0 to +0.0, which flips a zero's sign bit, so it is not
  proven exact. Use a NaN payload the engine cannot produce (with a flagged fallback), or the LL flag word.
- **Buffers:** three rotating buffers, cleared one exchange behind.
- **Inside 1-2:** consume slices in K order as they arrive. Each lane's chain over K is unchanged.

**4-5. Prompt reading.**
- With 16-token blocks a layer touches ~85 of 384 experts, each for ~1.1 tokens: ~5.8 GB of expert bytes per card
  per block (~13 of 57 ms), and every IQ grid decode serves about one token.
- Blocks of 128-512 tokens grouped by expert read each expert once per block for ~4 tokens on average (2-8): sorted
  token lists, one launch over all experts, an atomic work counter as in Intel's B60 MoE GEMM.
- Separate multiply and add is a floor of 2 FPU ops per weight-token, so the ALU ceiling is ~5.7 T weight-tokens/s
  per card. 1,000+ tok/s therefore needs ≤ ~2.5 ops per weight-token: decode the tile once to f32 (the mmq /
  sycl-tla mixed-input structure), loop tokens with mul+add only, and keep integer work on the ALU pipe.
- At 256-token blocks the exchanges are bandwidth-bound (~180 us each at 24 GB/s), which is where #8 pays.

**6. Free drafts.** SuffixDecoding proposes long continuations from a suffix tree of the prompt and earlier
outputs. It gets 5.3x on AgenticSQL and 2.5x on SWE-Bench (7.8 accepted per step against 3.2 for PLD), and loses
to EAGLE on non-repetitive text. Our checks of 6-16 tokens cost ~2.5-5 one-token steps, so 7-8 accepted tokens
gives 150-250 tok/s on such text. Fall back to DSpark below a match-frequency threshold. It is lossless, but the
lab's final gate disables n-gram/history drafts, so it is for serving only, never a headline.

**9. Guess length.** Cascade measures that checking K tokens moves 2-3x the data of one token on MoEs, and picks K
per request by utility. EcoSpec divides each draft path's probability by the experts it adds. It gains 1.22-1.36x
on Qwen3-235B, but its ~4 ms predictor is too slow for us; the cost term is the useful part. After #1 a check of 4
costs ~1.29 + 4 x 0.4 GB, about 1.7x one step, so guessing keeps paying. Prefer chains over trees: trees widen the
expert union.

**DeepSeek's own stack.** `deepseek-ai/DeepInfer` serves V4.1-Flash-1017:
- DSpark drafting up to 5, with confidence-scheduled checks (`DEEPINFER_ENABLE_MTP_VARLEN`,
  `DEEPINFER_USE_NEXTN_DECODE`); compare its rule with `OWN_SPEC_TAU`;
- TileLang ops in `deepinfer/model_executor/layers/tilelang_ops`;
- `deepseek-ai/TileKernels` `mhc/` (Sinkhorn), `engram/` (gate + RMSNorm) and `moe/` (top-k): fusion shapes for our
  2.9 ms of small serial steps, but not their order of sums.

FlashMLA, DeepGEMM and DeepEP are FP8 / bf16 (see the last section).

## Not useful at batch 1

- **Expert parallel / DeepEP low-latency mode:** with 6 picks on 6 cards the busiest card averages ~2.4 whole
  experts (all different cards only 1.5 % of the time). That is ~24 MB against TP's ~10 MB per layer, +1.2 ms per
  word. Keep TP.
- **Hazy's distributed transpose with a replicated O projection:** needs a batch.
- **Replicating a sliced matrix to drop an exchange:** pays only below ~5 MB of extra reads (13 us at 450 GB/s);
  o_b and down are larger.
- **IPEX-LLM:** archived, binary kernels.
- **OpenVINO GPU plugin:** its speed comes from dynamic activation quantization and XMX.

## Lossy, not usable

- llama.cpp SYCL/CUDA IQ kernels (`vecdotq.hpp`, `mmvq`): activations go to Q8_1, dp4a.
- Any DPAS/XMX GEMM (sycl-tla, oneDNN, vllm-xpu-kernels, XeTLA).
- Ozaki int8 emulation: exact products, but not our rounding order.
- DeepSeek's FP8 paths: DeepGEMM, the FlashMLA FP8 KV cache with bf16 math, the indexer's `fp8_mqa_logits`.
- bf16 fused all-reduce + norm (TRT-LLM/FlashInfer); the -0.0 sentinel without a proof; quantized all-reduce
  (SGLang/AMD quick all-reduce, TRT-LLM `customLowPrecisionAllReduceKernels`).
- Megatron column→row TP or a K-split down/o_b (sums across cards); split-KV decoding unless the combine matches
  our order.
- Expert budgeting in checks (MoE-Spec), dynamic top-k, expert deferral (ktransformers).
- KV compression.

## Suggested order

#0 (hours) → #3 bench (days) → #2 on one layer, one card (a week; keep if the overlap shows) → #1 staged. In
parallel, on other cards: #4+#5 for prompt reading, and #6 on the host side.

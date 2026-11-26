# Ideas from other people's recent B70 projects (to review and test later)

Date: 2026-11-25 (evening). Asked for by the owner: read the B70 projects updated in the last few days, and list
every idea that might help us while staying lossless, so we can test them after the current work.
Earlier list of the same kind: [2026-08-21](2026-08-21-b70-optimization-ideas-from-community-sources.md).

How this was made: reading-only helpers went through the repos (nothing was run, nothing posted, nothing downloaded
beyond source text). The numbers are the projects' own claims, quoted as found; none was checked by us yet.

## Short version

- Almost every big number out there comes from arithmetic we do not allow: 16-bit or 8-bit activations,
  8-bit K/V, re-quantized weights, or guessing whose text differs from plain writing. Their prompt speeds (3-4x
  ours) are 16-bit matrix-engine math. Our writing speed is ahead of all of them on one card.
- Several projects took ideas from our engine (one says so: otaliptus patch 0061 credits our inkling2 engine).
- What is new and lossless falls in four groups, best first:
  1. Cheaper guessing work (drafter head, verify count by load, the target head's exact screened argmax).
  2. Exact attention shortcuts (skip a rescale that is exactly 1, skip blocks nobody can see).
  3. Serving features (a host-memory cache of conversation branches, cap prompt reading while others write).
  4. For DeepSeek: a faster Engram row reader, and faster loading.

## Best picks (lossless, probably new to us, most value first)

1. **Clean multi-card exit** (all lanes, DeepSeek most): drain every queue, let the last copy finish, wait ~20 ms,
   disable peer access, never SIGKILL. Measured elsewhere: exiting 0-2 ms after the last copy-engine copy reset the
   copy engine at 3 of 30 exits (20 ms wait: 0 of 15, avra-m3/c0ven); SIGKILL right after GPU work hung the next
   process's upload 5 of 20 times (Dkirk25/ollama-intel-sycl); SergiioB: "bcs resets + next-launch hang ~50%" without
   it, "6/6 clean exits" with it. **Our host resets often came at the start of a six-card run**, right after another
   run ended: worth checking how our runs exit.
2. **Out-of-range bugs in the 48-head GDN prompt kernel** (Qwen lane): vllm-xpu-kernels commit 18b78776a (by wu1ff's
   arithmetic 48 heads leave sub-groups 1008-1023 out of range), PR #552 (a delta-epilogue write past the end),
   arcitech-psp/vllm-xpu-arc b6438d4a31 (a missing barrier + head guard). **This may be the real cause of our
   48-head prompt race** (we fixed it with the head-groups overlay). Read the three fixes against our overlay.
3. **Conv-state copy bug with 2+ accepted drafts** (wu1ff vLLM patch 013: reads `src_col + accepted - 1` instead
   of `src_col + token_bias`). Check our MTP-5 + prefix-cache base.
4. **Host memory held by the driver**: `NEOReadDebugKeys=1 EnableDeferBacking=0` (dndnglmw: "GPUActive 51.10 ->
   0.57 GiB", same bits; they say 7.0 kernels still hit the dma-buf variant, and we run 7.0); wu1ff's Level Zero
   peer-residency shim ("~101 GiB" -> "4.0-4.5 GiB" pinned on four cards). This is our 12.65 GiB driver-held problem
   beside the two-card server. Debug keys: test, and tell the owner.
5. **A second copy-engine reset trigger**: a 4 KiB host page moving under a copy ("reset after 1,941 host
   migrations"); 2 MiB pages or `NEO_EnableRecoverablePageFaults=0` gave no reset and the same tokens (c0ven).
   Debug key: tell the owner. Related to our own copy-engine fault (fixed by chunked uploads).
6. **Inkling guessing work**: the exact screened argmax for the output head (I1), the cheaper drafter head (I2; their
   draft round is ~5.0 ms of which the base logits are 1.57 ms).
7. **Qwen guessing work**: verify count by number of users (Q1), MTP draft from a cut-down vocabulary (Q2), MTP K/V
   only on prompt rows (Q3).
8. **DeepSeek Engram reads** (D1, plus horvay: O_DIRECT into ordinary memory then copy runs at 6.0-6.8 GB/s vs
   3.2-3.3 straight into pinned memory; a read being waited on jumps the queued prefetches, "4 ms instead of 73";
   up to 256 reads in flight).
9. **Inkling prompt attention**: stage the relative-bias rows in local memory per key tile (itstxl/arcangel: attention
   -15 %, 16K 4.16 -> 3.53 s), the exact rescale skip (I5), the mask classes (I6), pre-transposed key copies for prompt
   attention (horvay: a transposed load costs ~2.5x a VNNI load; 36.3 -> 25.7 ms).
10. **Push instead of pull between cards** (akapug, 16 MB copies: pushed by the source 28.4 GB/s, pulled by the
    destination 6.4 GB/s). Our resets came under card-to-card *reads*: whether writes are also safer is a guess to
    test. **Needs owner approval** (stable-mode transfer rules).

## Inkling-2-Mini (our engine, one card)

| # | Idea | Where | Their claim | Lossless? | Our status / what to test |
|---|---|---|---|---|---|
| I1 | **Exact screened argmax for the output head.** A small low-precision copy of the head plus a proven error bound finds the few rows that can still win; only those get the exact dot product. | Strata `engine/src/inkling2/cuda/ink_kernels.cuh` ~1867-2215, `head_argmax_exact` | 0.25 ms on an RTX 5090, "100.000% bit-exact argmax" | Yes for greedy, *if* the bound covers float rounding rigorously (theirs is a fudge factor ×1.001 + 1e-4), the candidates use our head kernel's exact sum order, and ties break the same way | New. Our head reads the full Q6_K matrix every step. Catch: the gate compares full logits, and logprobs need them; it would be a writing-only mode. A 4-bit screening copy against a Q6_K head gives a weaker filter than their int8 against BF16. |
| I2 | **Cheaper drafter head.** Score the drafter's first part for all 7 guesses in one pass, keep the top 256-512 rows, and score only those at each guess step. | Strata `ink_dspark.cuh` header lines 9-10, ~254-453, ~629, ~825 | whole drafter < 0.35 ms (RTX 5090) | Yes for the text (only guesses change); can be made identical to the full drafter with a bound + fallback | Check how many full-list head passes our drafter does per round (we use a 47,912-token list). Guesses changing would move the drafter gate's pinned guesses, not the text. |
| I3 | **Window size from a cost model.** Expected accepted tokens divided by the cost of a check of M rows, where the cost grows with the share of experts M rows touch. | Strata `ink_dspark.cuh` ~1756-1780, `ink_cuda_backend.cu` ~1040-1053 | a check costs 1.9-3 plain steps; accepts 1.7 on chat, 3.3-5.7 on code | Yes (decides from drafter probabilities, repeatable) | Compare with our adaptive count. |
| I4 | **Drafting on/off governor.** If guessing runs below 0.93x of plain, write 40 plain steps, then try again (doubling back-off). | Strata `ink_serve.h` ~511-532; Hy4 `sy_spec.h` | chat 0.97x -> 1.04x | Yes | Partly done (adaptive count). Prose/chat is where it would help. |
| I5 | **Online-softmax rescale skipped when no row's maximum rises** (the factor is exactly 1). | arcint docs/concepts.md §6, patches 0019-0020 | not stated alone | Yes (multiplying by exactly 1.0 changes nothing) | Check our prompt attention kernels (attn_flash / running-max block attention). |
| I6 | **Mask-class pre-pass**: one byte per block marks it as fully visible, fully hidden or mixed, so hidden blocks are never read. | arcint §6, `flash_attn_mask_cls`, patch 0038 | 5.43 -> 4.02 ms at 8K keys | Yes | We already skip causal blocks; check the windowed layers and the relative-bias edge. |
| I7 | **Host-memory cache of conversation branches.** Saved states share memory between branches; going back to a branch is nearly free. | otaliptus patches 0055, 0057 | back to a branch 24.73 -> 0.40 s; follow-ups 47.25 -> 1.19 s | Yes | We have saved prompts on disk and two on-card copies; a multi-branch host cache would be new. Host RAM is 15 GB, so a budget of a few GB at most. |
| I8 | **Cap prompt reading per step while another user is writing** (LAN server with more than one user). | Strata `STRATA_INK_PREFILL_CAP`, `ink_serve.h` ~497 | writing 12.6 -> 24 tok/s with cap 64 | Yes (answers identical) | For the Inkling LAN server if it serves several people. |
| I9 | **Send a lone request to the slot the drafter runs in.** | Strata v0.2.21 notes | agent sessions 85 -> 142-152 tok/s | Yes | Check that our server's single-user path always drafts. |
| I10 | **NVFP4 "split-half" nibble layout** (low nibbles one scale group, high nibbles the other). | vllm-inkling2-xpu `ops/moe_packed.py` `repack_nvfp4_split_half`; b70-inference results/20261123 | 110 vs 143 µs per call | Yes (layout only) | Probably the same as our planar layout; a 5-minute code check. |
| I11 | **Faster 4-bit decode**, from our own count today: the one-token matrix-engine kernel spends ~110 of ~170 instructions per input step turning 4-bit weights into 16-bit values. | our `xmx_moe.hpp` | - | Yes if the values are the same bits | Ours, not theirs; noted here so it is not lost. Strata found an integer E2M1 decode 1.5-2.5 % slower than a table. |
| I12 | **Drafter weights in BF16** (the original `mtp.safetensors`, 636 MB) instead of Unsloth's Q8_0. | Strata | not stated | The text stays exact; guesses change | Weights would have to come from the official publisher. Only if acceptance rises. |

Checked 2026-11-26 against our engine (nothing to do): I3 (our adaptive count already picks the checked guesses by
expected tokens per ms from the drafter's probabilities and measured step costs, `tools/ink_run.cpp` INK_SPEC_ADAPT),
I4 (a count of 0 is a plain step), I10 (our tile layout's byte b holds inputs b and b + 8: the split-half layout),
I14 (lookup's guesses are checked instead of, or continuing, the drafter's agreeing prefix: INK_SPEC_LOOKUP), I15
(the drafter always drafts its 8-row block, the count trims after), I16 (the drafter's ring). I11 closed: the decode
is not the one-token limit (`inkling2/tools/bench_xs.cpp`, DO-NOT-REPEAT). Pick 1 (clean exit) done: `Device` drains
its queue and pauses 20 ms.

More Inkling items from the wider search (repo, then idea; numbers are theirs):

| # | Idea | Source | Their claim | Lossless? / notes |
|---|---|---|---|---|
| I13 | Inkling on **two cards, bit-identical to one**: each card takes half the heads and 4 of 8 experts, pushes its per-expert outputs, both run the same fixed-order combine | Red-Weasel/machx `src/model/inkling2.cpp` 234-302, 755-782, 860-868 | 62.4 -> 82.4 tok/s | Yes. Only if the owner gives the lane a second card. |
| I14 | Suffix-lookup drafter chained after DSpark (lead mode when the last 8+ tokens repeat; chain mode after confident DSpark guesses) | arcitech-psp/inkling-arc `speculator.py` 7-19, 85-202 | not stated | Yes. We run lookup and DSpark; check whether we chain them this way. |
| I15 | Run the drafter at its native 8-row block, then trim | dndnglmw/inkling2-xpu | acceptance 2.74 vs 1.71 for a shrunk 4-row block | Yes |
| I16 | Fill the draft layer's cells from the prompt's last 2,048 rows | c0ven | drafts per round 1.800 -> 2.012; 85.59 -> 92.68 tok/s | Yes. Likely done (our drafter ring). |
| I17 | Two prefix checkpoints: before the first user token (if the system/tools prefix is 256+ tokens) and after the full prompt | MarcAldrich/TensorFold SERGIO_RECEIPT.md 24-27 | 94.8 ms vs 24.15 s cold | Yes. A shared system-prompt checkpoint may be new for our server. |
| I18 | Keep a long conversation's cache through short side requests (titles, tags) | kinoqdev/XeFP4 `engines.py` 92-125 | follow-up 0.7 s instead of 7.7 s | Yes. LAN server. |
| I19 | `--prefix-split-last`: the next turn hits the cache exactly where clients that drop reasoning diverge | urakozz README:213 | not stated | Yes. Agent servers. |
| I20 | Local-memory bank conflicts (consecutive threads write consecutive addresses); alias the accumulator onto the weight tile after the k loop | itstxl/arcangel PERF.md 22-34 | attention 16K 9.7 -> 5.0 s; 2K prompt 391 -> 462 | Yes. Check our XProd2 local-memory layout. |
| I21 | Zero the matrix-engine pad rows in the producer kernel instead of a memset | horvay `engines/glm.cpp/README.md`:688 | 1-3-row steps 1.1-1.2 ms faster, identical | Yes |
| I22 | **Pad matrix-engine buffers**: `joint_matrix_load` reads whole 8-row tiles, up to 7 rows past the end; this caused page faults and GuC resets for SergiioB/Strata | SergiioB Hy4 notes | - | Checked for our new path: one-token loads are 1-row block loads; 2-8 token rows have 8 rows of padding; prompt tiles are 16-row. Keep this rule for Phase B/C. |
| I23 | "The EU flushes fp16 subnormal operands" (inkling-arc) vs TensorFold claiming the opposite | inkling-arc `nvf4_kernels.hpp` 12-15 | - | Our 4-bit decode goes through a subnormal half for the code 0.5. The gate's agreement with the CPU reference says it works; a direct decode-vs-CPU check of every code is cheap and worth one run. |
| I24 | Hardware bf16 conversion differs from emulation in 33 of 1,572,864 values | okolenmi/oko-xpu-kernels | - | Our 3-part split uses integer rounding (bf_rn), not the hardware conversion: keep it that way. |
| I25 | Power-of-two row strides cost bandwidth (419 vs 559 GB/s at a 64 KB stride) | urakozz 12-kernels.md 230-236 | - | Check our big strides (head, K/V). |
| I26 | Only 16x16x16 / 8x16x16 joint_matrix shapes are real hardware; 32x64 shapes are emulated | newjordan/lagunaX | - | We use 8x16x16 / 1-8x16x16: fine. |
| I27 | A ~65,620-token prompt missed recall 5 of 7 times when its last chunk was only ~84 tokens (their untested guess) | djgene01 | - | Test our engines at lengths that leave a tiny last step. |
| I28 | The power test elsewhere: an MoE model at 150 W gave 125.7 tok/s vs 115.4 at 230 W | SergiioB skill | - | **Needs owner approval** (power settings are off limits). |

## DeepSeek V4.1 (our six-card engine)

| # | Idea | Where | Their claim | Lossless? | Our status / what to test |
|---|---|---|---|---|---|
| D1 | **Engram row reader**: O_DIRECT + FADV_RANDOM, 8 threads x 8 outstanding 4 KiB reads, duplicate rows removed, a hot-row table, an LRU row cache, and the next chunk's rows fetched 3 deep ahead; rows for guessed tokens fetched right after guessing. | Strata `engine/src/hy4flash/run/hy4_engram.h` ~53-140, `.cpp` ~356-410 | page faults through mmap 0.9 GB/s vs large preads 3+ GB/s | Yes (I/O only) | Directly about our 1.3-1.7 s Engram read stalls. Pinned memory cannot be an O_DIRECT target: they use an aligned bounce buffer. |
| D2 | **Faster model loading**: 8 reader threads into batches, copies overlapped. | Strata `docs/INTEL.md` | 76.2 -> 18.8 s | Yes | Must respect the 15 GB host limit and the "no test loads while serving" rule. |
| D3 | **Router as a split-K product with fixed tiles, fused top-k, ties to the lower id** (bitwise across batch sizes 1-100). | b70-inference `docs/flint-vllm-xpu-hillclimb-20261119.md` change 1 | 45.8 -> 10 µs per layer | Yes | Check our DeepSeek router time per layer. |
| D4 | **Shared expert folded into the routed expert kernel** as extra pseudo-experts. | same doc, change 3 | 43.6 -> 35.1 µs per layer | Only if the shared expert keeps its own sum and is added in our reference order | Check the current launch count around the shared expert. |
| D5 | **Two determinism lessons** (Hy4): a split-K partition that depended on the row count changed a row's sums; a "last work-group to finish" reduction read stale partial sums on Arc (fixed with two launches: before, 4 different results in 10 runs). | Strata commits 78d3edce15, 182df445f6 | - | - | Audit our kernels for any last-arriver reductions (our F1-F3 fold was correct but slow and is closed; check nothing similar is live). |

More DeepSeek / multi-card items:

| # | Idea | Source | Their claim | Notes |
|---|---|---|---|---|
| D6 | Cross-card sync rules: a queue barrier on the other card's event did NOT order the reads (machx: wrong values); a spin wait sees the flag 100/100 only with a system-scope acquire fence before each load (an acquire load alone: 21-37/100, c0ven); uncached loads for host flags (dual-b70, horvay); one writer per 64-byte line (urakozz: 16 stamps in one line failed 1-3 in a few dozen); stores into the peer card at 64 bytes or more (22.2-22.5 GB/s vs 1.9 GB/s with one fp16 per work-item) | several | - | Audit our six-card sync against each rule. |
| D7 | Probe peer writes at load (a verified 4 KiB copy and 64-byte write each way, pinned-host fallback) | c0ven commits 0cf97c94d0, 2d1c41b42c | catches bridges that drop peer writes | Add to preflight. |
| D8 | Give each submitting host thread its own core | akapug lines 216-233 | two engines on CPU 0: 24.6 -> 39.8-42.6 ms per step | Check our thread pinning. |
| D9 | No host waits inside a step: sync kernels publish ready/done flags, the step id lives in card memory | horvay `dsv_xpu/pager.py` 1-18 | exact 6.1 -> 7.2 tok/s | For our Engram pager. |
| D10 | Indexer: read each pooled key once for 8 prompt rows (49.0-52.7 -> 20.7 ms a layer at 239K); exact few-of-many top-k with ties (281.3 -> 26.2 µs); top-513 select (1.865 -> 0.92 ms a step at 246K) | c0ven | as stated | We have dtopk / idx_dsplit; compare. |
| D11 | Tag-check large allocations ("16.9 GiB allocation came back with its last GiBs mapped over its first") | horvay README 366-368 | - | Cheap safety check for big buffers (also Inkling at 530K). |
| D12 | Keep shared host mappings at 4 GiB or less ("busy" answers retried forever above that) | urakozz 01-hardware.md 209-212 | - | Hang hygiene. |
| D13 | Graph replay: a recorded list cannot be replayed while its previous replay may run; `zexCommandListAppendWaitOnMemory` waits in the command streamer with no EU threads | c0ven LEVEL_ZERO.md | - | Reference facts. |
| D14 | Float atomics made outputs vary run to run (fixed by block sums added in block order) | horvay | - | Audit all engines (and H3) for float atomics. |
| D15 | Do not run multi-card device-timing profilers (they cause "Engine memory CAT error"); under ~1 GiB free, transient allocations can trigger copy-engine faults | SergiioB skill | - | Matches our own rules (no GPU sampler in gates). |

## Qwen3.8-27B FP8 (vLLM, one or two cards)

| # | Idea | Where | Their claim | Lossless? | Our status / what to test |
|---|---|---|---|---|---|
| Q1 | **Verify fewer drafts when many users are active** (`num_speculative_tokens_per_batch_size: [[1,2,7],[3,32,3]]`). | vllm-inkling2-xpu README, commit 788440517f; b70-inference results/20261125-inkling2-draft-length-schedule | +11 % at 8 users, +19 % at 32 | Yes for fixed counts (static k3/k4/k5 matched greedy); their *adaptive* version did not | Our MTP depth is fixed at 5. Needs our row-invariance overlays checked with each count. |
| Q2 | **MTP draft from a cut-down vocabulary** (40,960 rows of the head); the target still checks the full vocabulary. | arcint docs/concepts.md §9, `src/exec/llama_spec.cpp` | 47.1 -> 50.8 tok/s | Yes for the output | Not done in our vLLM lane. |
| Q3 | **MTP head fills only its K/V on prompt rows.** | arcint §9, patch 0080, `LLAMA_MTP_KV_ONLY` | +6.6 % prompt at 41K | Yes (same K/V rows) | Check what our vLLM build computes for MTP on prompt rows. |
| Q4 | **GDN rollback snapshots written straight into the recurrent cache**, and verify batches of up to 8 on the one-token GDN kernel. | arcint §7, patches 0050, 0066 | +5.1-5.3 % | Yes (text identical) | Unclear for vLLM XPU; read our GDN path. |
| Q5 | **Many small copies as one launch; row-parallel snapshot copy.** | arcint §7, patches 0065, 0025 | 150 -> 30 launches (+1.8 %); 4,595.6 -> 95.2 µs | Yes | Check vLLM state copies in a profile. |
| Q6 | **FP32 LM-head fast path** (XPU otherwise casts the whole head to fp32 every step). | vLLM PR #69186 | head 9.05 -> 1.59 ms | Unclear | Only matters if our image uses an fp32 head path; check. |
| Q7 | **Caution**: fp32 `F.linear` / `mm(out_dtype=fp32)` on XPU is run-to-run nondeterministic and batch-variant (~3e-6); Triton's unified-attention chunked prefill is off by 1 ulp between runs. | b70-inference Flint docs | - | - | Keep in mind for any new vLLM kernel we adopt. |

More Qwen items:

| # | Idea | Source | Their claim | Notes |
|---|---|---|---|---|
| Q8 | Capture each graph twice and alternate (replaying the same graph exec blocks the host: 13.96 ms vs 8-12 µs alternating) | MikkoP88 `graph_exec_doublebuffer.py` 4-20, 77-124 | replay max 24 -> 0.37 ms, end to end neutral | Check our replays. |
| Q9 | Exact KV block size for hybrid models (the XPU platform rounded a 1,600-token block up to 2,048) | sybil-solutions/trellis `vllm_patches.py` 219-260 | 16 users 349.1 -> 409.9 | Check our padded page size. |
| Q10 | oneCCL: `CCL_SYCL_ALLREDUCE_TMP_BUF=1` + `CCL_SYCL_ALLGATHERV_TMP_BUF=1` cured cold-start hangs (wu1ff); `CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4194304` +4.8 % prompt (dndnglmw); split collectives over 2,621,440 bytes into ordered chunks ("can wedge the B70 device engine") | several | as stated | Each needs a bitwise test; compare with our LL256 ring-hang notes. |
| Q11 | Greedy verify gathers (max, id) per rank instead of full logits: 3,973,120 -> 4,096 bytes per rank | wu1ff TUNING_GUIDE:389 | - | TP2 only. |
| Q12 | Exact 12/16-row graph capture sizes (C3 201.5 -> 231.2) | wu1ff | - | Check our capture list against MTP-5 row counts. |
| Q13 | MTP partial-group guard (schedule only the target token if the budget cuts a speculative group) and pinning the replay snapshot block against LRU | arcitech-psp/vllm-xpu-arc patch 0001 ~385-406, 453-505 | - | Multi-user correctness. |
| Q14 | LM head in 16-row chunks (oneMKL switches kernels at M = 26) | dndnglmw `model.py` 541-589 | 49.5 -> 3.4 ms at 32 rows | Our 32-row head finding is related; re-sweep after upgrades. |
| Q15 | Boot canary: a few prompts checked bit-exact before admitting traffic (batched-matmul bits drift for "whole eras" of a process) | dndnglmw `boot_canary.py` | - | For LAN servers. |
| Q16 | Warnings: 395-508 fingerprints in 512 runs of a repeated oneDNN projection at 256 rows; duplicate SYCL kernel names across libraries caused DEVICE_LOST; a missing paged-decode config can silently fall back to PyTorch attention (vllm-xpu-kernels #713) | wu1ff, vllm-xpu-kernels | - | Grep our logs for the fallback. |
| Q17 | vllm-xpu-kernels #705 (merged): GDN prompt writes state checkpoints every 64 tokens inside one prompt | csrc/xpu/gdn_attn/... L969-990 | - | Could free our 832/1280 block-size coupling; needs the vLLM side. |

## Any engine (runtime, compiler, driver)

| # | Idea | Where | Their claim | Lossless? | Notes |
|---|---|---|---|---|---|
| R1 | **OpenCL runtime instead of Level Zero for cheaper launches.** | Strata Hy4 (`sy_launch_bench.cpp`) | "4x cheaper kernel launches"; A750 writing 6.6 -> 10.4 (other changes in the same commit) | Yes | Worth a short launch-cost test on a B70. Their B70 logs also show: SYCL graphs slower (23.5 vs 24.2-24.3 tok/s), immediate command lists on better, Level Zero V2 failed. |
| R2 | **Compiler tricks for exact fusions**: under fast-math IGC regrouped `(x*scale)*post`; an XOR with an always-zero argument keeps both roundings. The value-returning `__builtin_IB_subgroup_block_read_flat_*` keeps 2D block reads out of scratch. | arcint §8 patch 0049, §6 patch 0038 | - | Yes | We build with `-fp-model=precise -ffp-contract=off`; the block-read builtin may help our small kernels. |
| R3 | **Graph inputs staged through a host ring with one wait.** | arcint §8, patch 0047 | +1.3-1.5 % | Yes | DeepSeek host stalls; Qwen. |
| R4 | **xe driver fix "drm/xe: Order ring writes before ring tail updates"** (upstream 9f83c94469ff, mainline from 7.2), run as an out-of-tree module. They link it to a direct-submission fault. | arcint docs/docker.md, DESIGN.md §8.2 | correctness | Yes | **Needs owner approval** (kernel module). Possibly related to our faults and host resets; worth reading the patch first. |
| R5 | **Newer compute runtime** (26.40.40196.8, IGC 2.42.6) with `NEOReadDebugKeys=1 ForcePreemptionMode=3`. | b70-inference server setup | not stated | Should be, but a new compiler can change code: rerun every gate | **Needs owner approval** (host software change). A/B only. |
| R6 | **CPU boost off.** | b70-inference docs/b70-cpu-boost-off.md | not stated | - | **Needs owner approval** (host setting). |
| R7 | Drop the model file's pages from the page cache after upload (madvise / posix_fadvise DONTNEED in ~1 GiB batches) | itstxl/arcangel `src/gguf_file.cpp` 157-165 | start-up 7.2 -> ~3 s; keeps experts out of swap | Yes. Not a sysctl. Useful on our 15 GB host. |
| R8 | Missing `libumf.so.1` makes SYCL silently fall back to OpenCL; `SYCL_CACHE_PERSISTENT=1` segfaults (several repos); oneAPI 2026.2 measured ~27 % slower prompts and a moving gate hash (lact-lab) | several | - | Pin the toolchain; check containers. |
| R9 | Correctly rounded divide and sqrt (without them 4.7 % of x / 127 and 8.2 % of sqrt(x) differ) | c0ven, XeStrata | - | **Already done**: our build uses `-fp-model=precise -ffp-contract=off -foffload-fp32-prec-div -foffload-fp32-prec-sqrt`. |
| R10 | Keep NEO direct submission on (off: -6 % one card, -23 % two cards) | SergiioB skill | - | Check nothing turns it off. |
| R11 | Idle power cut via debugfs forcewake (idle ~42 W -> 8-20 W) | joshdev-de | - | **Needs owner approval**. |

The wider search covered about 35 repos updated since 2026-11-17 (list in the helper's report, kept in the session
notes); repos with no inference work (games, launch patches, monitoring tools, spam) were skipped.

## Lossy tricks behind other people's numbers (not for us)

- Strata: oneMKL FP16 matrix math for prompts and experts, FP16 K/V (FP8 at 32 users), int8 activations,
  re-quantized SQ packs (96.68 % top-1), approximate late layers, guess checks that differ from plain writing,
  "0.00000 KLD" quoted in place of bit identity. Their own B70 logs: Inkling ~30 tok/s writing, 500-590 tok/s prompts.
- vllm-inkling2-xpu / b70-inference: BF16 activations and BF16 matrix-engine kernels, FP8 K/V, BF16 flash attention,
  probabilistic drafting, drafted greedy text differing from plain greedy.
- otaliptus: int8 activations while writing, FP16 activations in prompt products, FP16 K/V with matrix-engine
  attention, re-quantized experts. Their 1,770 tok/s at 100K (ours 692) is that arithmetic.
- Furthen64 (ArcAngel ledger): 8-bit K/V, int8 activations (DOWNQ8), re-quantized Q4_K weights.
- arcint: int8 matrix math with quantized activations, FP16 products, q8_0/q4_0 K/V, Hadamard K/V rotation, a KL bar
  instead of bitwise output.
- The wider search, in one line each: MikkoP88 (fp8 K/V, fp16, probabilistic drafting), machx (q8_1 activations,
  fp16+remainder experts: "logits 1e-2 off"), arcangel (Q2 quants, int8 activations, 4/8-bit K/V, float atomics),
  c0ven (IQ quants, bf16 products), dndnglmw (bf16 activations, a non-exact drafter), urakozz (int4 weights, int8 head
  and K/V), inkling-arc (int8 dense/head, K8/V4 K/V), wu1ff (re-quantized FP8, probabilistic dFlash2), horvay (EXL3
  low-bit, fp16 P, W8A8), trellis (EXL3, fp8 K/V), dual-b70 (Q8_0/Q4, bf16/int8 all-reduce, f16 attention), XeFP4,
  LarcXe, the cookbook and its skill (FP8 K/V, BF16 SDPA, W4A8).

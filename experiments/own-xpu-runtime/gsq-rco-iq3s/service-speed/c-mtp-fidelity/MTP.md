# MTP acceptance: source audit and proposed experiments

Research/design only, 2026-10-24. No model, compiler, device query, service request or GPU operation was run. Nothing outside this output directory was edited. Memory figures below are decimal bytes/MB/GB unless explicitly marked MiB/GiB; proposed deltas are source-derived estimates, not measured allocations or speed results.

## Answer

The service's draft is **not running its routed expert weights in checkpoint FP8**. It decodes E4M3 values using the checkpoint's BF16 scales for each 128×128 block, then requantizes each row's 16-value groups to signed INT8, with a fresh F32 scale for every group. Dense draft matrices remain BF16; arithmetic uses F32 products/reductions followed by BF16 activation stores. The draft has its own full-length BF16 KV, populated during prompt processing. Its vocabulary is the full 248,320 rows. There is no 32-token draft window and no active 80,128-token vocabulary cutoff. There **is a 2,048-token sparse-attention budget**, retaining all KV but attending to the best 512 four-token blocks plus the incomplete tail. That budget agrees with the local official config; it is not evidence of an accidental truncation. [M:29–38, M:62, M:100–104, M:161–178, K:18–49, G:15–18, P:165–179, C:94–96, O:21–25]

The most promising isolated change is to **retain the original E4M3 codes and original block scales and dequantize directly to F32 inside the draft expert kernel**. This removes an additional quantization and saves **628,838,400 bytes (599.71 MiB)** on rank 0 compared with the current INT8-plus-many-scales layout. A draft-only budget increase to 4,096 is another small-memory experiment, but may worsen acceptance because it changes the draft's configured attention policy. Neither change is guaranteed to improve agreement with this different, quantized/abliterated target. Both must leave the target and its verifier unchanged, and pass exact emitted-token **and full target-state** equality. [M:30–38, M:100–104, D:10–3081, A:210–227, S:3–5, S:109–112, O:21–25]

## Citation map and executed-source identity

All citations below use **physical file line numbers**, ignoring embedded C++ `#line` directives. `L` means `experiments/own-xpu-runtime/gsq-rco-iq3s`. `X` means `L/recurrent-f32/build/source-v2/experiments/own-xpu-runtime/gsq-rco-iq3s`. `N` means `X/integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2`.

| Citation | Exact file, expanding L/X/N above |
|---|---|
| M | `X/integration/build/private/source/diet-native/native-src/mtp.hpp` |
| K | `N/packet194-expert-diet-engine/mtp_kernels.cpp` |
| P | `N/packet3/step/plan.hpp` |
| G | `N/packet3/kernels/api.hpp` |
| Q | `N/packet194-expert-diet-engine/core_v2.hpp` |
| QS | `N/packet194-expert-diet-engine/specialised.hpp` |
| NG | `N/packet194-expert-diet-engine/kernels.hpp` |
| QA | `N/packet194-expert-diet-engine/p49_qsa_submit.cpp` |
| C | `N/packet194-expert-diet-engine/native_controller.hpp` |
| R | `X/state-bundle/build/source-v4/rank.hpp` |
| E | `X/dense-packed-block/engine/build/source/main.cpp` |
| B | `X/integration/build/private/additive/admission.hpp` |
| SEL | `N/packet194-expert-diet-engine/p59c_select.hpp` |
| D | `L/mtp/draft-manifest.tsv` |
| A | `L/serving/lan/adapter.py` |
| S | `L/serving/lan/README.md` |
| SR | `L/serving/lan/RESULT.md` |
| MEM | `L/recurrent-f32/operating/candidate-ledger.json` |
| BUILD | `L/recurrent-f32/evidence/native-build.json` |
| O | `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8/config.json` (local metadata read only) |

The service points at the corrected binary SHA256 `5926a24746c62c6b0ecdc5c3e4895f310145e0f9d74a90a5d657035b9a8151f4`; adapter selection requires the successful 21-rebuilt/19-reused-object receipt. The receipt records the actual copied `source-v2` draft, rank loop and controller hashes, so this report follows those executed-source copies, not only the earlier MTP CPU bridge. [S:109–113, A:68–72, BUILD:1161–1175, BUILD:1223–1225]

The service sets `--gsq-packed`, rank-0 MTP, split 24/24, resident weights and 4096 context; native controller mode is selected explicitly. The source first installs `baseline_selection`, which resets draft choices to `production`. Consequently the optional packet59 fusions, Q4 draft head and historical prefix selectors are **available code, not active service settings**. [A:46–53, A:72, A:119, E:859, B:297–303, SEL:37–44]

## C1.1 Exact precision and checkpoint relationship

| Component | Checkpoint representation | Current draft representation and arithmetic |
|---|---|---|
| Routed gate/up/down experts | 512 experts × 3 matrices; each has 1,638,400 E4M3 values, with 100 BF16 scales (200 bytes) per matrix; 128×128 scaling blocks | `value = fp8(code) * widen_bf16(scale)` in F32; per row/group16, `s=max(abs(value))/127` (or 1 for all-zero), `q=nearbyint(value/s)`, clamp to −127…127; store one byte/value and one F32 scale/group. This is additional lossy draft quantization, **not** GGUF Q8_0 and not native FP8. [D:10–15, D:3076–3081, M:29–38, M:100–102] |
| Expert dot products | Checkpoint identifies weights, not this engine's arithmetic | BF16 activation inputs widened to F32, `F32(scale)*F32(int8)` then F32 multiply and explicit F32 addition/reduction; result BF16. There is no INT8 activation dot product here. [K:16–22, K:38–49] |
| Attention, router, shared expert, FC/HC dense matrices | BF16 | BF16 retained; normal production linear dispatch; BF16 output buffers. Router scores therefore round to BF16 before top-10 routing, while selected probabilities are F32. [D:1–9, D:3082–3101, M:100–104, M:126–141, P:80, P:197–218] |
| Norm weights | BF16 offset weights | Loader stores `1 + widen(BF16)` in F32. Norm arithmetic is F32, output BF16. [M:100–104, K:75–85] |
| Embedding and output head | Draft config uses non-dedicated embeddings | Uses **target** IQ4_XS token embedding, decoded then rounded BF16; output uses target's full Q6_K head with expanded variant 6. This is not the official FP8 model's original embedding/head. [M:179–190, M:232–233, L/mtp/README.md:59–67, O:97] |
| HC/activations/MoE combination | BF16 weights where present | F32 scalar math but repeated BF16 stores; MoE combine also rounds routed sum and shared contribution before final BF16 output. [K:94–99, K:112–119, P:102–121] |
| KV/index state | BF16 activation path in local config | Private BF16 keys, values, raw index vectors and pooled index vectors; no compressed/FP8 KV. [O:12, P:35, P:165–168, M:165] |

The name `weight_scale_inv` does **not** mean the loader divides by it: the executed code multiplies by its BF16-decoded value. It rejects non-finite E4M3 codes, validates shapes and scales, and requires nearest-even host rounding. Local config also declares FP8 dynamic activation quantization, but this custom draft's inputs are BF16; it is not reproducing the upstream runtime's FP8 activation recipe. [M:29–37, K:16–22, O:154–162]

A metadata-only sum of the 3,101 manifest entries gives 2,698,026,496 checkpoint bytes: 2,516,582,400 expert E4M3 bytes, 307,200 expert-scale bytes and 181,136,896 other BF16 bytes. These are checkpoint payload sums, **not** the loaded draft allocation: the current expert payload alone is 3,145,728,000 bytes, before dense weights, target head copy, cache and workspaces. [D:1–3101, M:100–104, M:167–189]

## C1.2 Context, positions, vocabulary and the long answer

Use zero-based target tokens `x_i` and final four-stream hidden state `H_i` after target layer 47 processes `x_i`. Rank 1 publishes 4×2560 BF16 values (**20,480 bytes**) after layer 47, tagged with position `i+1`; rank 0 validates that tag before handing the hidden data to the draft. [R:182–187, R:316–321, G:16]

At each step the controller supplies confirmed `x_(i+1)` and target hidden `H_i`. The draft writes its own KV row at **draft position i**, applies RoPE at that draft position, and when requested proposes `x_(i+2)`. `compute` requires `target_position == draft_position + 1`; the native publication tags the proposed token's position one further ahead. Thus this one-position offset is explicit and checked, not an apparent RoPE off-by-one to “fix” without an oracle. [C:94–96, M:228–233, R:324–325, QS:139–160]

**Prompt initialization is complete over the shifted input sequence.** The controller calls DRAFT on every confirmed prompt transition, not just the final prompt token. During earlier prompt transitions it disables only the final HC/head/argmax work; it still executes attention, appends KV/index entries and increments the draft position. For an N-token prompt, rows begin with `(H_0,x_1)` at draft position 0; no separate draft row represents `x_0` without a preceding hidden state. The same confirmed-input policy holds on proposal hits and misses: draft state is not populated with rejected guessed tokens. [C:69–96, M:234–255, M:265–281]

The draft builds one full-attention block from target geometry and allocates private state. It does not read any target layer's K/V cache, does not have its own GDN recurrence or PLE lookup, and obtains historical information through both the sequence of confirmed target hidden states and its own accumulated attention KV. Immutability/alias checks separate draft mutable allocations from target allocations. [M:161–166, M:199–202, M:231–233, P:271–290]

There are three distinct limits:

1. **Capacity 4096:** service request prompt+output bound; draft refuses an out-of-range append. All existing KV rows remain addressable; no sliding-window eviction exists in append/select code. [A:72, A:213, M:214–216, Q:395–412]
2. **Launch extent, initially 32:** grows to the next 32-position bucket and rebinds/re-captures selection/attention as positions cross the bucket. This is a dispatch optimization, **not** a 32-token context cap. [M:55, M:143, M:214–225]
3. **Attention budget 2048:** computes index scores for all complete four-token pools, selects the best `min(pool_count,512)` pools, expands to their original K/V rows and appends up to three incomplete-tail rows. Hence 2048–2051 attended rows maximum, not the most recent 2048 tokens. Full history is retained in the cache; older pools compete globally. The official local config has exactly `indexer_budget=2048`, compression ratio 4, and a single full-attention MTP layer. Enlarging this budget is a draft behavior experiment, not restoration of a demonstrated missing checkpoint feature. [G:18, Q:414–438, QS:161–178, O:21–25, O:87–97]

**No draft vocabulary truncation:** `prefix_rows()` returns `p.g.vocab` unconditionally in GSQ mode. The full Q6_K head is loaded on rank 0; both head projection and argmax receive the same full extent. Defaults choose neither `q4-g32` nor `p114-80128`. The older 80,128-row calibration must not be blamed for this service's misses. [M:61–62, M:107–108, M:152, M:179–190, B:303, SEL:37–44]

The recorded code chat was 106/109 = **97.25%**, versus 380/511 = **74.36%** for the 1756-prompt/512-output critique, a difference of **22.88 percentage points**; the long run had **131 missed proposals**. These are different tasks and lengths, not a matched context experiment. The service table records 63.5 s prompt time and 18.9 tok/s decode for the long request. [SR:17–26; arithmetic from those counts]

For that exact long request, the source loop gives 511 scored proposals from draft positions **1754 through 2264** inclusive. The first dropped complete pool is at draft position **2051** (2052 rows = 513 complete pools), because 2049–2051 rows still fit 512 pools plus an incomplete tail. Therefore the **first 297** scored proposals attend to all available draft rows, and the **last 214** can omit pools. At the final scored proposal, 2265 rows exist, 2049 are attended and **216 are omitted**. This is an indexing derivation, not a recorded distribution of the 131 misses. Aggregate acceptance cannot establish whether misses precede, follow or cluster at this boundary. [C:67–98, M:228–255, Q:415–437]

## C1.3 Concrete isolated experiments and rank-0 cost

Budget anchor: the corrected split-24/24 source ledger is **31,083,481,994 bytes** on rank 0 and 29,995,470,740 on rank 1. Against the task's nominal 32,000,000,000-byte ceiling this leaves **916,518,006 bytes** (874.06 MiB) before extra allocations. These logical totals were also confirmed by the corrected launch-b allocation census (`L/recurrent-f32/operating/launch-b/RESULT.md:11–13`); they are not physical free memory. The adapter additionally enforces `actual <= 30 GiB`, so the numerical logical admission margin is 1,128,772,726 bytes; neither number waives allocation/physical-fit validation. [MEM:5–23, MEM:30, A:148–159]

| Priority / proposed draft-only arm | Expected mechanism, not a guaranteed acceptance gain | Source-derived rank-0 delta |
|---|---|---:|
| 0: collect per-position misses and margins | Distinguish content mismatch, near-tie logits, route changes and the 2052-row sparse boundary. First compare a full unchanged draft control on fixed varied prompts; do not tune on one easy chat. Existing native result has per-proposal position, actual, hit and timings. [C:108–110] | No model-weight increase; diagnostics should stream small host records rather than keep a GPU trace. Proposed logging design. |
| 1: original FP8 codes + original scales | Remove INT8 requantization; change loader and draft expert kernel only. Decode E4M3 and BF16 scale directly to F32 before activation multiply. Do **not** reconstruct checkpoint weights from already-requantized INT8 or round expanded weights through BF16 first. [M:29–38, M:100–102, K:18–22] | **−628,838,400 B**: 2,516,582,400 + 307,200 versus 3,145,728,000. Net rank0 ≈30.455 GB. A separate ~1 KiB E4M3 lookup is negligible if used. |
| 2: F32 draft router/logit outputs | Avoid BF16 route-score ties and final-vocabulary argmax ties while target remains untouched. This needs typed draft consumers, not just bigger allocations. [P:199–203, P:293–295, M:150–152, K:49] | Router **+1,024 B**; full logits **+496,640 B** if replacing BF16, or **+993,280 B** for an additional F32 dual store. |
| 3: draft QSA budget 4096 at capacity4096 | Tests whether sparse selection is losing useful draft context in long answers. Target remains at its original attention policy. May worsen agreement because the official draft uses2048. [Q:414–438, O:21–25] | Explicit ids/scores/probabilities delta **401,408 B**: `2048*4 + 2*24*2048*4`. Existing 8 MiB draft scratch may suffice, but kernel scratch/compiled geometry must be checked before any fit claim. KV allocation unchanged. **Not a config-only change:** general validation rejects budget>2048 and the specialized QSA submitter requires2048. Add a draft-only admitted kernel path and re-size/re-audit its scratch; do not relax target validation. [M:167, P:169, NG:66, QA:39] |
| 4: F32 draft KV/index storage | Eliminates draft-cache BF16 storage rounding, but projected K/V must also become F32 or widening only preserves the same rounded values. [P:150–168] | Cache payload **+9,699,328 B** (9.25 MiB) if keys, values, raw and pooled index data all double. Producers/temporary buffers add more. [M:212] |
| Fallback: BF16 expansion of all experts | Simpler kernel format than direct FP8, but rounds scaled E4M3 values to BF16 and costs too much for the current placement. Prefer direct FP8→F32 decode. [M:100–104] | **+1,887,436,800 B**: 5,033,164,800 minus3,145,728,000; ~32.971GB total, beyond the stated32GB budget. |
| Narrow fallback: BF16 expansion of one matrix kind | Isolate gate/up/down contribution, but format change still adds BF16 weight rounding versus original scaled FP8. Do not choose arbitrary popular experts after inspecting holdout. [D:10–15] | **+629,145,600 B** per gate/up/down bank (600MiB), leaving~287.37MB nominal. Too tight for unbudgeted workspaces; direct FP8 preferred. |

Direct FP8 can save memory even while improving checkpoint fidelity because the current layout uses **1.25 bytes/value**, whereas original block-scaled FP8 uses `1+2/16384` bytes/value. One expert's three matrices expanded to BF16 would cost **+3,686,400 B**; full F32 expert expansion would cost **+6,920,601,600 B** over current INT8. Neither all-BF16 nor all-F32 weights are required to compute original FP8 weights in F32 inside a kernel. [D:10–15, M:31–37; calculations using512×3×2560×640]

There is another source mismatch worth measuring, not silently “correcting”: the official-draft identity suggests a training/runtime mismatch (inference, not a training audit): this lane supplies corrected-engine hidden states and SC117 quantized/abliterated embedding/head. Keeping target embedding/head is deliberate and currently full vocabulary. Replacing them with original-model weights may improve or worsen agreement and would require a separate approved memory/source design; it is not the first small-memory lever. [S:3–5, S:109–112, M:180–190, M:231–233, O:97]

### Preregistered lossless-output gate for every arm

Proposed future work, not work authorized/executed in this research task:

- Freeze exact target binary/arithmetic, weights, tokenizer, prompt token files, greedy EOS policy and response cap. Use at least prose, code, analysis, operations and structured writing; include fixed lengths below/above the sparse boundary and the original critique if its exact input can be recovered. Report per-class acceptance, per-position misses, TTFT, total latency and rank memory. Do not use cached prompt/response state across suite requests. The existing service's retention summary does not retain prompt/response text, so the long aggregate alone is not a reproducible fixture. [S:87–92]
- Compare target-only and each draft arm for **exact equality of all emitted token IDs and complete target state** on both ranks, including logical recurrent/history/KV/position state and rollback-relevant buffers. Existing attached comparison already checks both token and target-state equality; extend its coverage instead of accepting token-only evidence. [A:188–194, A:210–227, R:254–256]
- Exercise forced miss, invalid/stale/failed proposal, EOS with pending speculation, RESET, 31/32/33 and 2047/2048/2051/2052 positions, and two fresh processes. Draft state may differ across draft arms; target state may not. Keep every target acceptance/rollback operation unchanged. The native loop emits rank1 target results, accepts only matching rank0 speculation, otherwise rolls back/recomputes. [C:77–99, M:214–225, M:290–298]
- For direct FP8, independently compare every E4M3 decode and block-scale address against the existing loader's **pre-requantization** values, with exact F32 bit comparisons; no tolerance. Test zero groups, signs, subnormals, exceptional codes and matrix boundary coordinates. Then measure draft agreement; removal of extra weight quantization is a mechanism, not evidence of an acceptance improvement. [M:29–38]
- Select an arm only after exact target parity and a preregistered held-out acceptance/latency improvement. More accepted proposals with slower total decoding is not a speed win. Do not alter target quality gates to admit a better draft. [C:87–99, A:226–227]

## C1.4 More than one proposal

**No k>1 chain exists in this executed path.** The model metadata has one MTP hidden layer; the runtime builds one QSA/MoE block. The native `Publication` carries one token; controller `Guess` carries one position/guess/actual and starts one speculative rank0 half. `DraftRuntime` has one pending publication, and insists each next input is confirmed. There is no draft-depth flag or batch of speculative token positions in these interfaces. `Linear.batch<=10` is the routed-expert batch, not10 future tokens. [O:87–97, M:55–58, M:161–164, M:228–229, R:323–327, C:61–63, C:81–99, K:58]

A **recurrent k=2 draft using the same MTP layer** is feasible as a new design: feed the first draft output's four-stream hidden state plus its proposed embedding into the same layer for the second proposal, using private speculative draft KV/position; verify the entire proposal prefix through the unchanged target; discard and rebuild draft speculative state after a mismatch. This requires a new hidden-state handoff, vector publication/sequence checks, and draft commit/rollback semantics. The current confirmed-target-state requirement explicitly prevents treating this as an enabled-by-flag feature. It also is not a checkpoint with two separately trained MTP layers. [M:228–233, M:255, M:265–281, C:94–98, O:87–97]

Draft-side memory need not duplicate weights: a conservative second KV/index bank at current4096 capacity is **9,699,328 B**, plus a four-stream hidden copy20,480B and position/token metadata; an append-only rollback design can save less but must preserve partial four-row pooling. This is a lower-bound design estimate, not a full multi-token target verifier budget. Target speculative state is currently banked for each recurrent/conv temporal output and managed by one accept/rollback boundary; a deeper target pipeline could need additional target banks or serial verified replay. Cost must be counted from the exact target inventory before admission. [M:212, Q:395–412, R:73–94, C:95–99]

As a planning illustration only, if independent successive proposal agreement equalled the observed0.74364, a two-proposal chain would accept on average `p+p² = 1.29664` draft tokens and both would survive with probability0.55300. At0.97248, those numbers become1.91819 and0.94571. Conditional agreement may be substantially worse because the second proposal uses draft-generated hidden state, so these are **not predicted measured speeds or an acceptance claim**. The current target pipeline has no batched two-token verification, so extra draft work could reduce throughput even if more tokens are accepted. [SR:19–23 for p; C:68–99 for single-step target schedule]

Recommendation: first test original FP8 expert storage and a bounded draft precision arm; then test the sparse-budget hypothesis on fixed long prompts. Defer k>1 until per-position losses and target-parity qualification are established. This sequence removes a known avoidable approximation with a favorable memory delta before adding a new speculative state machine. [M:30–38, A:226–227, C:94–99]

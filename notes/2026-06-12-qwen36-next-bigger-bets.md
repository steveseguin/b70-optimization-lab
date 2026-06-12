# Qwen3.6 35B INT8 Next Experiments And Bigger Bets

Date: 2026-06-12

Current target:

- Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`.
- Hardware: 4x Intel Arc Pro B70 32GB.
- Runtime anchor: vLLM/XPU TP4, Quark W8A8 INT8, 32K context, accepted graph
  cache, no prefix caching.
- Quality constraint: the current Quark W8A8 model remains the source of truth.
  No Qwen3.5 substitutions, no 4-bit/AWQ substitutions, and no speed result is
  promoted without exact sentinel and canary proof.

Current speed anchor:

- Public exact-model Localmaxxing row:
  `cmq8yhxvo001ipb0149aoa79o`, `99.428 tok/s`, c1, 32K context,
  4x Arc Pro B70.
- Fresh local accepted A/B baseline before the offset endpoint test:
  `99.309 tok/s` corrected p512/o512/c1 decode, `98.068 tok/s` e2e,
  `10.051 ms/token` vLLM decode, and `75.3 ms` client TTFT.
- Fresh B70/Qwen3.6 Localmaxxing check:
  `99.770 tok/s` for the current Quark W8A8 INT8 vLLM run family is the top
  B70 row for this model class. Rows above `200 tok/s` remain architecture
  signals, mostly MTP/speculative, lower-bit, or non-B70 setups, not accepted
  comparables for the current no-quality-loss INT8 goal.
- Restored post-recovery local sanity run:
  `99.728 tok/s` corrected after-first and `98.212 tok/s` e2e at p512/o512/c1.
- Practical interpretation: about `100 tok/s` is now the proven quality baseline.
  The `>200 tok/s` c1 goal needs either verifier-safe speculation or a real
  MoE/kernel architecture improvement. Launch flags alone are unlikely to get
  there.

## Accepted Lane Manifest And Candidate Gate 20260612cz

Added a cache-versioned manifest for the current accepted Qwen3.6 Quark W8A8
INT8 lane:

- `scripts/qwen36-accepted-lane-manifest.py`
- `data/qwen36-quark-int8-tp4-accepted-lane-manifest-20260612cz.json`
- `data/qwen36-quark-int8-tp4-accepted-lane-manifest-20260612cz.md`

What the manifest pins:

- Live endpoint health on `http://127.0.0.1:18080`.
- Clean accepted cache root:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-accepted-clean-after-routeparity-20260612cy`.
- Cache tree digest: `4221` files, `1184728587` bytes,
  `754a30c22b94952565827ce6e0431c6589da23c3e540cebb3e15909313bef54e`.
- Runtime extension hashes and symbol presence. The live `_xpu_C.abi3.so`
  exposes the base W8A8 INT8 grouped GEMM symbol and does not expose the
  rejected offset/active-offset or oneDNN sidecar symbols.
- Launcher scrub state. `scripts/launch-qwen36-quark-int8-accepted.sh` now
  unsets the rejected diagnostic MoE env vars before serving.
- Runtime source repo heads and dirty counts for `/home/steve/src/vllm` and
  `/home/steve/src/vllm-xpu-kernels`.
- p512/o512/c1 speed baseline:
  `99.188 tok/s` corrected decode, `97.893 tok/s` e2e,
  `10.063 ms/token` vLLM decode, and `78.4 ms` client TTFT.
- Quality-smoke state: pass, including baseline comparison.
- Old exact-token provenance state: fail on this fresh clean cache. This is
  recorded separately instead of being hidden.

Gate status:

- `accepted_quality_baseline_with_stale_token_sentinel`

Meaning:

- This is the accepted quality/performance baseline for the next speed branch,
  but not a claim that the old token-sentinel file is cache-invariant.
- Future candidates must beat the manifest speed while passing the no-thinking
  quality suite and must report old-token sentinels separately from
  cache-versioned clean-cache token baselines.
- Kernel-path candidates also need graph-path or live compiled-path tensor
  parity before endpoint promotion.
- The manifest makes the `>200 tok/s` work more actionable: a candidate now
  has a single baseline packet to beat and a concrete evidence format to copy.

## W8A8 Offset Route Gate, Clean Restore Caveat, And Bigger Bets 20260612cy

Added after replaying the first-decode route fixture through the offset-capable
W8A8 INT8 grouped-GEMM build and restoring the accepted endpoint from an
isolated cache. This section updates the queue; it does not promote a new speed
path.

Route replay gate:

- Added `scripts/qwen36-offset-route-gate-summary.py` to summarize base replay,
  offset-env replay, and endpoint provenance as separate gates.
- Base route replay used the first-decode JSONL fixture across layers `0`, `9`,
  `19`, and `39`, route starts `0:12:1`, rows `1`, `20` iterations, and the
  stable offset-capable extension.
- Eager tensor parity was exact for both replays:
  `max_abs_diff_all_checked_paths=0.0`.
- Base env mean `xpu_fused_moe` latency was `347.086 us`; the env-on offset
  integration path was `409.229 us`, a `+17.904%` slowdown. The explicit
  fused-prologue offset micro-path is faster in isolation, but the real
  `xpu_fused_moe` integration does not realize that win.
- Endpoint gate still rejects the offset lane because the earlier offset
  endpoint provenance failed `repetitive_kernel_notes[14]` (`4752 -> 6126`) and
  `natural_latency_plan[25]` (`198 -> 271`), and the endpoint A/B was slower
  (`96.165 tok/s` corrected p512/o512/c1 versus accepted `99.309 tok/s`).

Clean restore and reliability caveat:

- The first post-routeparity restore reused the accepted cache root and failed
  provenance/quality. That made cache/source hygiene part of the result, not a
  side note.
- Patched `scripts/launch-qwen36-quark-int8-accepted.sh` to explicitly unset
  rejected diagnostic MoE env vars, including `VLLM_XPU_W8A8_USE_OFFSETS`,
  oneDNN sidecar probes, fused Silu+quant, and live ABI capture flags.
- Relaunched the accepted endpoint from an isolated clean cache root:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-accepted-clean-after-routeparity-20260612cy`.
- The clean endpoint passed the no-thinking quality smoke:
  exact arithmetic, copy phrase, JSON schema, repeat stability, and baseline
  comparison all passed.
- Clean p512/o512/c1 sanity speed is still the same class:
  `99.188 tok/s` corrected after-first decode, `97.893 tok/s` e2e,
  `10.063 ms/token` vLLM decode, and `78.4 ms` client TTFT.
- The old exact-token provenance sentinels did not pass on the fresh clean
  cache. The rerun is stable but differs at the same two early positions as
  the offset endpoint: `4752 -> 6126` and `198 -> 271`; `11436` still matches.
  Because the broader quality smoke passes, treat this as a provenance
  baseline/cache-dependence problem, not proof that offset is safe. The next
  reliability task is to replace the stale single-cache sentinel baseline with
  a pinned clean-cache baseline plus BF16/logit or semantic checks.

External leads checked:

- Intel's current XPU vLLM container notes call out persistent MoE GEMM and
  fused activation as the MoE direction, with a reported `2.6x` end-to-end
  Qwen3-30B-A3B improvement:
  https://github.com/intel/ai-containers/blob/main/vllm/0.10.2-xpu.md
- Intel's Triton/XPU grouped-GEMM issue says skewed runtime route
  distributions materially affect grouped-GEMM performance and should be used
  as tuning inputs:
  https://github.com/intel/intel-xpu-backend-for-triton/issues/6389
- Public B70 reports show the same split we are seeing: strong aggregate
  throughput at concurrency, but single-stream latency stays hard unless the
  MoE/kernel path changes:
  https://www.reddit.com/r/LocalLLM/comments/1sfa0iw/2x_intel_arc_b70_benchmark/
- Public Localmaxxing B70/Qwen/vLLM snapshot still has the same current family
  near the top: `99.770 tok/s` for `Qwen/Qwen3.6-35B-A3B` and `99.428 tok/s`
  for the exact `nameistoken/...Quark-W8A8-INT8` row.

New things to try next:

1. **Graph-path tensor capture before endpoint promotion.**
   Eager route replay can pass while compiled serving output drifts. Add a
   capture point in the compiled/custom-op path, or a live tensor compare
   around the graph replay path, before any more endpoint launches.

2. **Persistent c1 W8A8 MoE kernel island.**
   Stop optimizing the generic grouped-GEMM wrapper first. Build a
   target-shaped path for one decode token, topk `8`, `hidden_size=2048`,
   `moe_intermediate_size=512`, and Quark W8A8 scales, with resident expert
   descriptors and scratch.

3. **Route-distribution autotune harness.**
   Feed the real first-decode route ledger into SYCL/Triton/oneDNN/grouped-GEMM
   microbenches. Tune for the skewed rows-per-expert shape we actually see,
   not synthetic uniform groups.

4. **Quality gate v2.**
   Keep exact token sentinels, but make them cache-versioned and add a periodic
   BF16/logit or answer-scoring lane. The route gate should report
   "old-cache exact match", "clean-cache exact match", and "quality suite
   pass" separately.

5. **AOT cache provenance manifest.**
   Every accepted launch should write the cache root, AOT path hashes, extension
   SHA256, git SHAs, env scrub list, and sentinel baseline ID. This prevents a
   passing graph from being confused with a freshly recompiled graph that has
   different early-token choices.

6. **Latency lane split from aggregate lane.**
   If TP4 remains around `10 ms/token` for c1, test a dedicated single-user
   lane that trades some aggregate capacity for fewer per-token collectives,
   while a separate TP4 lane handles aggregate serving.

7. **Hot-expert memory-for-latency packs.**
   Use the route fixture to duplicate or prepack hot expert tuples across
   cards. Exact math stays unchanged; the common path gets fewer remote or
   long-tail route stalls, and cold routes fall back to current TP4.

8. **Whole-token command-list supernode.**
   Treat launch/fence overhead as a first-class target: capture a patchable
   Level Zero command-list sequence for fixed decode buckets covering MoE,
   attention, norms, logits, and sampling. Gate it with graph-path tensor
   parity before serving.

9. **Target-owned branch farm.**
   Use spare VRAM/cards only after we have exact request-state transactions.
   Branches can be ngram/MTP/route-trained, but the same Quark W8A8 target must
   verify every emitted token before commit.

10. **Upstream challenge packet.**
    Package the route fixture, failed offset proof, Localmaxxing rows,
    p512/o512 metrics, extension symbol matrix, and clean-cache provenance
    caveat for Intel/vLLM maintainers. The ask is specific: make exact c1
    Qwen3.6 A3B Quark W8A8 decode materially faster on B70 without token drift.

Artifacts for this pass:

- `scripts/qwen36-offset-route-gate-summary.py`
- `scripts/launch-qwen36-quark-int8-accepted.sh`
- `data/qwen36-quark-int8-firstdecode-l9-offset-parity-smoke-20260612cy.json`
- `data/qwen36-quark-int8-firstdecode-l9-offset-parity-smoke-20260612cy.md`
- `data/qwen36-quark-int8-firstdecode-l9-offset-integration-parity-smoke-20260612cy.json`
- `data/qwen36-quark-int8-firstdecode-l9-offset-integration-parity-smoke-20260612cy.md`
- `data/qwen36-quark-int8-firstdecode-multilayer-offset-gate-base-20260612cy.json`
- `data/qwen36-quark-int8-firstdecode-multilayer-offset-gate-base-20260612cy.md`
- `data/qwen36-quark-int8-firstdecode-multilayer-offset-gate-envon-20260612cy.json`
- `data/qwen36-quark-int8-firstdecode-multilayer-offset-gate-envon-20260612cy.md`
- `data/qwen36-quark-int8-firstdecode-multilayer-offset-gate-summary-20260612cy.json`
- `data/qwen36-quark-int8-firstdecode-multilayer-offset-gate-summary-20260612cy.md`
- `data/localmaxxing-qwen-b70-vllm-leaderboard-20260612cy.json`
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-routeparity-20260612cy.json`
- `data/qwen36-quark-int8-tp4-accepted-quality-after-routeparity-nothink-smoke-20260612cy.json`
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-routeparity-clean-20260612cy.json`
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-routeparity-clean-rerun-20260612cy.json`
- `data/qwen36-quark-int8-tp4-accepted-quality-after-routeparity-clean-nothink-smoke-20260612cy.json`
- `data/qwen36-quark-int8-tp4-accepted-clean-routeparity-p512o512-metrics-20260612cy.json`
- `data/qwen36-quark-int8-tp4-accepted-restored-after-routeparity-clean-20260612cy.log`

## W8A8 Offset Endpoint Rejection And Bigger Bets 20260612cx

Added after running the narrow offset endpoint A/B proposed in the previous
ABI smoke section. This is a rejection record, not a promoted speed result.

What changed:

- Added `scripts/launch-qwen36-quark-int8-w8a8-offset.sh`. The launcher keeps
  the accepted TP4 graph/runtime flags, overlays the stable offset-capable
  extension from
  `/home/steve/src/vllm-xpu-kernels/build/lib.linux-x86_64-cpython-312`,
  creates an isolated cache root under
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-${TAG}`, and sets
  `VLLM_XPU_W8A8_USE_OFFSETS=1`.
- Patched `scripts/check-qwen36-accepted-provenance.py` so an explicit
  `--expected-cache-fragment` can be used by a diagnostic launcher without
  also requiring the accepted production cache fragment. With no explicit
  fragment, it still defaults to the accepted cache root.

A/B result:

- Accepted pre-offset baseline, p512/o512/c1:
  `99.309 tok/s` corrected decode, `98.068 tok/s` e2e, `10.051 ms/token`
  vLLM decode, `75.3 ms` client TTFT.
- Offset endpoint, p512/o512/c1:
  `96.165 tok/s` corrected decode, `94.909 tok/s` e2e, `10.380 ms/token`
  vLLM decode, `80.8 ms` client TTFT.
- Offset provenance failed exact output parity even though the offset cache
  root was used. Failed sentinels:
  `repetitive_kernel_notes[14]` expected `4752`, got `6126`; and
  `natural_latency_plan[25]` expected `198`, got `271`.
- Accepted TP4 was restored on `18080` after the failed run. Post-restore
  provenance passed sentinels `4752`, `11436`, `198`, and the no-thinking
  quality smoke passed exact canaries, JSON schema, copy phrase, repeat
  stability, and baseline comparison.

Decision:

- Reject `VLLM_XPU_W8A8_USE_OFFSETS=1` for endpoint use. It is both slower and
  quality-breaking.
- The tiny ABI checksum smoke was not strong enough. Future kernel candidates
  need a no-server real-tensor compare against accepted route fixtures before
  they get an endpoint launch.
- Do not post the rejected offset run to Localmaxxing. The already-approved
  public result for the current exact model remains
  `cmq8yhxvo001ipb0149aoa79o` at `99.428 tok/s`.

Fresh external signals checked:

- Localmaxxing's public exact-model query already contains the approved
  4x Arc Pro B70 Quark W8A8 INT8 row at `99.428 tok/s`.
- Localmaxxing's broader Qwen3.6 leaderboard shows `>200 tok/s` rows, but the
  fastest ones are not accepted comparables for this goal: they use MTP/spec,
  lower-bit quantization, or non-B70 hardware.
- Intel's grouped-GEMM tuning issue for XPU explicitly points at runtime route
  distribution and decode-stage long-tail routing as grouped-GEMM tuning
  inputs. This lines up with our route-fixture direction.
- The public Arc Pro B70 benchmark repo still frames MoE as the B70 sweet
  spot, but its multi-GPU notes also reinforce that generic layer split is not
  a decode-speed multiplier by itself.

Near-term things to try:

1. **No-server W8A8 route-fixture tensor compare.**
   Build a harness that feeds captured first-decode hidden states, topk expert
   IDs, weights, and scales through accepted versus candidate MoE kernels and
   compares tensors before any endpoint launch. This is now mandatory for
   offset, active-offset, sidecar, or route-class kernels.

2. **Active-offset only after clean rebuild and tensor parity.**
   Active-offset is still the better conceptual shape because it can skip empty
   experts, but the next attempt must start from a clean build artifact with a
   symbol matrix, child-process smoke, and route-fixture parity.

3. **Route-realistic grouped-GEMM tuning bench.**
   Convert first-decode route fixtures into grouped-GEMM cases that preserve
   the real rows-per-expert distribution, not synthetic uniform groups. Use
   that to compare current W8A8 grouped GEMM, offset, active-offset, oneDNN
   grouped matmul, and Triton/SYCL variants without the server in the loop.

4. **Layer-9 single-token MoE microbench with real route tuples.**
   Use the existing first-decode fixture to isolate one representative MoE
   layer and measure launch count, quant time, GEMM1, activation+quant, GEMM2,
   gather, and synchronization. The goal is to find the real `~10 ms/token`
   device-side owner.

5. **Promote a route-fixture gate into every launcher experiment.**
   Endpoint launches should be reserved for candidates that already pass
   no-server tensor parity. This protects time and avoids cache churn from
   predictable quality failures.

Bigger, bolder ideas to add to the queue:

1. **Dedicated c1/topk-8 W8A8 MoE fast lane.**
   Build a target-specific kernel path for one decode token, topk=8,
   `hidden_size=2048`, `moe_intermediate_size=512`, Quark W8A8 scales, and
   TP-local packed expert shards. Fuse remap, activation quant, GEMM1,
   activation, second quant, GEMM2, and gather/reduce where possible. The
   generic grouped-GEMM wrapper looks like the wrong abstraction for the
   latency target.

2. **Persistent MoE worker with resident descriptors.**
   Keep expert descriptors, hot packed weights, scratch, and command lists
   resident per GPU. Feed route descriptors through a ring buffer so c1 decode
   avoids rebuilding grouped-GEMM setup and host launch state per token.

3. **Route-class kernels generated from accepted traces.**
   Compile a small set of exact-scheduling kernels for low-union, repeated hot
   tuple, broad-route, and cold fallback classes. Runtime still uses the
   target model's router; the route class changes layout/scheduling only.

4. **VRAM-for-latency hot expert packs.**
   Spend B70 headroom on duplicated or prepacked hot experts and hot expert
   pairs across ranks. The common path can avoid the slowest shard or a
   collective; rare routes fall back to current exact TP4.

5. **Single-user no-collective island.**
   Try a c1 lane where the active MoE subset, dense state, and logits path run
   on one primary card or a smaller card set, with exact fallback for cold
   routes. This is a bigger topology change than TP2 because the goal is to
   remove per-token collectives from the common path.

6. **Whole-token Level Zero supernode.**
   For fixed decode buckets, capture a patchable command-list sequence across
   MoE, attention, residual/norm, logits, and sampler boundaries. The payoff
   would be fewer host submissions and less inter-rank jitter, but it needs
   exact output proof.

7. **Verifier-safe target-owned speculation.**
   Do not use lower-quality drafts. Instead, use spare cards for
   target-owned branch farming only after we can transact KV/GDN/sampler state
   and verify every emitted token against the same Quark W8A8 target.

8. **Maintainer challenge packet.**
   Package the accepted route fixtures, failed offset proof, p512/o512
   timings, symbol matrix, and `~100 tok/s` baseline into a concise upstream
   `vllm-xpu-kernels`/Intel XPU request: "make this exact Qwen3.6 A3B W8A8
   c1 route fixture fast and bit-stable on B70."

Artifacts for this pass:

- `scripts/launch-qwen36-quark-int8-w8a8-offset.sh`
- `data/qwen36-quark-int8-tp4-accepted-pre-offset-p512o512-metrics-20260612cx.json`
- `data/qwen36-quark-int8-tp4-w8a8-offset-provenance-20260612cx.json`
- `data/qwen36-quark-int8-tp4-w8a8-offset-p512o512-metrics-20260612cx.json`
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-w8a8-offset-20260612cx.json`
- `data/qwen36-quark-int8-tp4-accepted-quality-after-w8a8-offset-nothink-smoke-20260612cx.json`
- `data/qwen36-quark-int8-tp4-w8a8-offset-20260612cx.log`
- `data/qwen36-quark-int8-tp4-accepted-restored-after-w8a8-offset-20260612cx.log`

## W8A8 Offset ABI Smoke And Bigger Bets 20260612cw

Added after isolating the local `vllm-xpu-kernels` W8A8 INT8 grouped-GEMM
extension candidates. This is an ABI and backlog update only. The accepted
endpoint on `18080` was not stopped or changed during the smoke.

What changed locally:

- Added `scripts/qwen36-w8a8-offset-abi-smoke.py`, which loads each extension
  candidate in a separate child process so a bad kernel can abort without
  killing the whole report.
- Added an env-gated local source hook in
  `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/fused_moe_interface.py`:
  `VLLM_XPU_W8A8_USE_OFFSETS=1` builds an exclusive prefix-sum offset vector
  from `rows_per_expert` and calls
  `cutlass_grouped_gemm_w8a8_int8_offsets_interface` for INT8 GEMM1/GEMM2 when
  the loaded extension exports that symbol. With the env var unset or the
  symbol missing, the existing base W8A8 path is used.
- Recorded the source hook as a patch note instead of a raw diff because the
  local `vllm-xpu-kernels` checkout already contains unrelated diagnostic
  changes in the same file.

Smoke findings:

- Installed extension:
  `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so` executes
  the base W8A8 INT8 op, but does not export the offset or active-offset op.
- Stable build candidate:
  `build/lib.linux-x86_64-cpython-312/vllm_xpu_kernels/_xpu_C.abi3.so`
  executes both base and offset W8A8 INT8 ops. The tiny synthetic checksum is
  identical for base and offset: `1452.126831`.
- Archived pre-sidecar candidate:
  `build/temp-before-onednn-grouped-20260612064136/_xpu_C.abi3.so` executes
  base, offset, and active-offset with the same checksum.
- Sidecar-probe candidate:
  `build/qwen36-sidecar-probe-20260612/_xpu_C.abi3.so` aborts with signal `6`
  for base, offset, and active-offset. Do not promote or benchmark that build
  until it is rebuilt or fixed.

Decision:

- The next no-quality-loss diagnostic lane is offset-only, using the stable
  `build/lib.linux-x86_64-cpython-312` candidate and
  `VLLM_XPU_W8A8_USE_OFFSETS=1`.
- Active-offset is not discarded, but it is blocked behind a clean rebuild and
  exact route-fixture tensor comparison. One archived build can execute it,
  while the sidecar-probe build aborts.
- Endpoint testing should be a single narrow A/B: accepted baseline versus
  offset-only overlay, same cache hygiene, same p512/o512 c1 benchmark, same
  provenance sentinels, then quality canaries. If the offset path is neutral or
  slower, reject it quickly.

Bigger, bolder ideas to keep in the queue:

1. **Offset-only endpoint bakeoff as a cheap gate.**
   This is not expected to produce `2x`, but it proves whether eliminating
   row-count reconstruction inside the grouped-GEMM wrapper matters at all. A
   fast rejection saves time before deeper kernel work.

2. **Rebuild active-offset from clean source with a reproducible ABI matrix.**
   The active-offset interface is closer to the desired c1 path because it can
   skip empty experts explicitly. It needs a clean build artifact, symbol list,
   child-process smoke, route-fixture tensor comparison, and only then an
   endpoint run.

3. **Dedicated c1 W8A8 MoE island.**
   Stop treating this as a generic grouped-GEMM problem. The common target is
   one decode token, topk=8, `hidden_size=2048`,
   `moe_intermediate_size=512`, TP-local packed weights/scales, and many empty
   experts. A dedicated fused island can remove remap, two quant launches, two
   generic grouped GEMMs, activation, gather, and temporary allocation churn
   from the one-token fast lane while preserving identical math.

4. **Persistent expert-resident service inside the worker.**
   A long-lived SYCL/Level Zero worker loop could keep hot expert descriptors,
   scratch buffers, and command lists resident. The Python/vLLM path would feed
   route descriptors and pointers through a small ring buffer instead of
   rebuilding launch work per token.

5. **Route-class generated kernels with exact fallback.**
   Use accepted route traces to compile a handful of kernels for route classes:
   low-union, repeated hot tuple, broad-route, and cold fallback. Runtime class
   selection changes only scheduling and layout; selected experts and weights
   stay target-owned.

6. **Expert duplication as a latency budget.**
   VRAM headroom should buy latency. Duplicate hot experts, hot pairs, or
   packed route classes on multiple cards so the common c1 path avoids a slow
   shard or collective. Cold routes fall back to the current exact path.

7. **No-collective single-user fast lane.**
   Investigate a c1 lane that keeps the active dense path and hot MoE subset on
   one primary card or fewer cards, then reconciles only when needed. This is
   bolder than TP2 because the goal is to remove per-token TP collectives from
   the common path, not just repartition the same graph.

8. **Whole-token command-list replay.**
   For stable decode buckets, capture a patchable Level Zero command-list
   sequence spanning MoE, attention, residual, normalization, logits, and
   sampler boundaries. The quality condition is exact same token/logits; the
   speed hypothesis is fewer host submissions and less stream dependency
   jitter.

9. **Target-verified branch farming after state transactions.**
   Speculation is allowed only if the same Quark W8A8 target verifies emitted
   tokens and KV/GDN/sampler state can be committed or rolled back cleanly.
   Spare cards could evaluate target-owned branches, not lower-quality draft
   guesses.

10. **No-server lower-bound runner.**
    Build a minimal c1 runner that reuses captured hidden states, route IDs,
    weights, and KV state to measure the real device-side lower bound without
    OpenAI serving, multiprocessing, scheduler, or HTTP result-path overhead.

11. **Intel stack challenge packet.**
    Package the route fixture, checksums, symbol matrix, current `~100 tok/s`
    baseline, and exact desired shape into an upstream `vllm-xpu-kernels` issue
    or maintainer benchmark request. Ask for a persistent W8A8 MoE target for
    Qwen3.6 A3B on B70, not generic "XPU is slow" advice.

Immediate next order:

1. Commit the offset ABI smoke and patch note.
2. Build an overlay launcher using the stable offset-capable extension.
3. Stop the accepted endpoint only for a narrow diagnostic run.
4. Launch with `VLLM_XPU_W8A8_USE_OFFSETS=1`, isolated cache root, and no
   sidecar build.
5. Run provenance, p512/o512 c1 speed, and quality canaries.
6. Restore accepted baseline immediately if the offset lane fails or is slower.

Artifacts for this pass:

- `scripts/qwen36-w8a8-offset-abi-smoke.py`
- `data/qwen36-w8a8-offset-abi-smoke-20260612cw.json`
- `data/qwen36-w8a8-offset-abi-smoke-20260612cw.md`
- `patches/vllm-xpu-kernels-qwen36-w8a8-offset-path-20260612cw.md`

## Kernel Path Audit And Bigger Bets 20260612cv

Added after a static/runtime audit of the current Quark W8A8 INT8 XPU MoE path.
This is a notes/backlog update only. The accepted endpoint on `18080` was
inspected but not changed.

Audit findings:

- Current Quark W8A8 INT8 dispatch does select the XPU INT8 MoE backend:
  `QuarkW8A8Int8MoEMethod` calls `select_int8_moe_backend`, XPU is prioritized
  before Triton on XPU, and `XPUExpertsInt8` passes `is_int8=True` into
  `xpu_fused_moe`.
- The runtime path is still a multi-stage MoE wrapper: remap, per-token INT8
  quant, W8A8 grouped GEMM 1, activation, per-token INT8 quant, W8A8 grouped
  GEMM 2, gather. That leaves several per-token launches and temporary tensors
  in the c1 decode path.
- The installed `_xpu_C.abi3.so` exports
  `cutlass_grouped_gemm_w8a8_int8_interface`, `per_token_quant_int8_xpu`, and
  `silu_and_mul_quant_int8_xpu`, but it does not export the route-aware
  `cutlass_grouped_gemm_w8a8_int8_offsets_interface` or
  `cutlass_grouped_gemm_w8a8_int8_active_offsets_interface` symbols.
- The dirty `vllm-xpu-kernels` source tree has those offset/active-offset
  prototypes, so the next useful engineering gate is rebuild/ABI validation,
  not another endpoint flag pass.
- `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1` and
  `VLLM_XPU_FUSED_MOE_FUSE_SILU_QUANT=1` remain rejected for promotion from
  earlier notes: one was slower, the other failed quality. Do not re-spend
  endpoint time on those toggles unless the implementation changes.

Fresh source-backed signals:

- Intel/vLLM's Arc Pro B-series writeup says naive MoE GEMM suffers from
  launch overhead, scheduling latency, and gate-dependent stalls; their
  persistent zero-gap kernel is the kind of architecture we need to reproduce
  for this exact W8A8 path.
- Intel's `0.10.2-xpu` container notes report persistent MoE GEMM plus fused
  activation reducing MoE bubbles, with `2.6x` end-to-end improvement on a
  related Qwen3-30B-A3B workload.
- Intel's grouped-GEMM tuning issue calls out runtime route distribution and
  tile configuration as key grouped-GEMM performance variables, with decode
  routing often long-tailed.
- The PyTorch locality-aware MoE post is NVIDIA/Triton-oriented, but the lesson
  transfers: schedule/layout choices around grouped GEMM can be worth multiples
  before model quality changes.
- The ROCm/vLLM MoE playbook reinforces that TP, DP, and EP are latency versus
  throughput topology choices. It is not an XPU recipe, but it is a useful
  checklist for our TP4, TP2+replicas, and possible TP+EP experiments.

Other bigger, bolder things to keep in the queue:

1. **Rebuild-to-proof route-aware W8A8.**
   Build the local `vllm-xpu-kernels` candidate so the offset/active-offset
   W8A8 INT8 symbols are actually exported, then run a no-server ABI smoke
   and first-decode route fixture tensor compare before touching the endpoint.

2. **Persistent topk-8 c1 MoE island.**
   Treat the current shape as a custom target: `hidden=2048`,
   `intermediate=512`, `topk=8`, one decode token, TP-local Quark scales and
   packed weights. The desired primitive fuses remap, quant, GEMM1,
   activation, quant, GEMM2, and gather/reduce for c1 without changing math.

3. **Route-class kernel generation.**
   From accepted route traces, generate a small set of specialized route
   classes: low-union, repeated hot tuple, broad-route, and cold fallback.
   Use exact route IDs after the router runs; this changes scheduling/layout,
   not selected experts.

4. **Persistent per-GPU MoE worker.**
   Keep expert weights, scratch, and command descriptors resident inside a
   long-lived SYCL/Level Zero worker loop. Feed route descriptors through a
   ring buffer to remove host launch bubbles from the common one-token path.

5. **Hot expert residency and duplication.**
   Spend spare VRAM on duplicated hot experts, hot expert pairs, or prepacked
   hot route classes. Cold routes fall back to the generic exact path. This is
   a memory-for-latency bet with a clean correctness boundary.

6. **TP+EP and TP2+replica topology lane.**
   Test whether c1 latency improves when expert work is distributed by expert
   ownership rather than full TP4 sharding. Keep this as a diagnostic lane
   until exact route fixtures show parity and latency benefit.

7. **C1 latency runner outside serving.**
   Build a minimal runner around the accepted model executor or a single-layer
   MoE/attention loop. The first purpose is to find the true device-side c1
   lower bound without vLLM multiprocess/result-path overhead.

8. **Whole-token command-list capture.**
   For stable decode buckets, experiment with a patchable command-list replay
   covering MoE, attention, residual, and sampler boundaries. This only wins if
   it preserves exact output while reducing command submission jitter.

9. **Target-owned branch farm after state transactions.**
   Revisit MTP/draft ideas only after KV/GDN/sampler state can be copied,
   committed, and rolled back. The emitted token must remain target-verified by
   the same Quark W8A8 model.

10. **Maintainer challenge packet.**
    Turn the compact route fixture, shape summary, symbol audit, tensor
    checksums, and current profiler evidence into a small upstream issue or
    benchmark request. Ask for a persistent W8A8 MoE target against this exact
    shape instead of a vague "B70 is slow" report.

Immediate next order:

1. Rebuild or isolate `vllm-xpu-kernels` with the route-aware W8A8 symbols
   exported.
2. Run ABI smoke tests for those symbols outside the server.
3. Replay the first-decode route fixture and compare tensors against the
   current accepted path.
4. Only then launch a diagnostic endpoint and measure c1 p512/o512 speed,
   provenance sentinels, and quality canaries.

Artifacts for this pass:

- `scripts/qwen36-quark-int8-xpu-kernel-path-audit.py`
- `data/qwen36-quark-int8-xpu-kernel-path-audit-20260612cv.json`
- `data/qwen36-quark-int8-xpu-kernel-path-audit-20260612cv.md`

Reference links captured during the scan:

- `https://vllm.ai/blog/2025-11-11-intel-arc-pro-b`
- `https://github.com/intel/ai-containers/blob/main/vllm/0.10.2-xpu.md`
- `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`
- `https://pytorch.org/blog/accelerating-moe-model/`
- `https://rocm.blogs.amd.com/software-tools-optimization/vllm-moe-guide/README.html`
- `https://github.com/vllm-project/vllm-xpu-kernels`

## External Leads And Bigger Bets Refresh 20260612cu

Added after the route-fixture planner pass and a fresh outside scan. This is a
notes/backlog update only; it does not change the accepted endpoint and does
not promote a new speed result.

Fresh public checks:

- Exact Localmaxxing query for
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` on B70/vLLM still returns one
  row: `99.428 tok/s`, c1, 32K, 4x Arc Pro B70.
- B70/Qwen/vLLM snapshot still has the same current run family at the top:
  `99.770 tok/s` for `Qwen/Qwen3.6-35B-A3B`, Quark W8A8 INT8, 4x B70.
- B70/Qwen/MoE/fp8 query returned zero rows. There is still no public
  comparable proving `>200 tok/s` for this exact model/hardware/quality lane.

Outside signals worth acting on:

- Intel's current `intel/vllm:0.10.2-xpu` notes explicitly call out persistent
  MoE GEMM plus fused activation for MoE, with a reported `2.6x` end-to-end
  gain on Qwen3-30B-A3B. This strongly supports our current route-fixture
  direction: persistent MoE is a serious lead, not a side quest.
- The `vllm-xpu-kernels` repo now advertises MoE top-k scoring, grouped top-k,
  MoE align/gather/expert remapping, FP8/MxFP4 GEMM, and grouped GEMM. That is
  the right home for any durable B70 W8A8 MoE island rather than piling more
  local Python hooks around the old path.
- vLLM's XPU RFC says the stack is moving from IPEX to `vllm-xpu-kernels` for
  performance, maintainability, and integration quality, with fp8 W8A8/W8A16
  GEMM and fp8 MoE marked complete in that migration plan. Our immediate task
  is to prove whether the Quark W8A8 path actually hits those kernels and, if
  not, create the smallest exact fixture showing the miss.
- Intel's B-Series vLLM blog shows high aggregate throughput on GPT-OSS MXFP4
  at high concurrency. That is not a c1 comparable, but it is evidence that the
  B-series software stack can move a lot of tokens when the kernels and
  batching policy fit the workload.

New concrete things to try:

1. **Latest `vllm-xpu-kernels` route-fixture bakeoff.**
   Build or install the newest XPU kernel stack in an isolated environment and
   replay the first-decode route fixture, not the whole server first. Gate:
   same captured inputs, same route IDs, same output tensor within the existing
   exact tolerance, then measure current Quark W8A8 MoE path versus newest
   kernel path.

2. **Persistent MoE kernel hit/miss proof.**
   Add one low-overhead marker around Quark W8A8 MoE dispatch to record the
   actual backend selected for each layer. If the current path is bypassing the
   persistent MoE/fused activation kernel, the next branch should be routing
   compatibility, not blind tuning.

3. **Intel 0.10.2-xpu container as a kernel lab.**
   Do not switch production to it blindly. Use it as a route-fixture lab for
   Qwen MoE persistent-kernel behavior, kernel availability, env defaults, and
   command lines. Bring back only reproducible deltas that pass our exact
   canaries.

4. **Single-token/topk-8 W8A8 MoE layerlet.**
   Implement the smallest DPC++/SYCL or custom-op layerlet that matches our
   measured c1 shape: one token, topk=8, `hidden_size=2048`,
   `moe_intermediate_size=512`, resident TP-local packed weights/scales,
   fused gate/up/activation/down/reduce, and no per-token primitive rebuild.

5. **Route-class generated kernels.**
   Compile a handful of exact route classes from captured traffic: one-hot
   dominant, low-union active experts, balanced broad route, and cold fallback.
   Runtime class selection changes scheduling only; math and selected experts
   remain target-owned.

6. **Hot/cold expert residency map.**
   Use real route traces to spend spare VRAM on duplicated hot experts or
   prepacked hot expert groups, while keeping cold experts exact through the
   existing path. This is a memory-for-latency bet with a clean fallback.

7. **No-collective c1 island experiment.**
   Explore whether the active dense plus hot-MoE subset for one-token decode
   can run on fewer cards or one primary card with cold expert fallback. It is
   bolder than TP2 because the aim is to remove TP collectives from the common
   c1 path, not simply repartition the same work.

8. **Level Zero command-list supernode.**
   For a fixed decode bucket, try capturing a patchable command-list sequence
   across MoE, attention, residual, and sampler boundaries. The quality gate is
   unchanged output; the speed hypothesis is fewer scattered host launches and
   less command submission jitter.

9. **Target-owned branch farm, revisited after state transactions.**
   The model's MTP/draft machinery is not acceptable until KV/GDN/sampler state
   can be verified, committed, and rolled back. Once that substrate exists,
   spare cards can evaluate candidate continuations under the same Quark W8A8
   target and only commit target-verified tokens.

10. **Power/thermal/PCIe audit as a no-quality lever.**
    Record B70 clocks, power, throttling flags, PCIe link width/speed, fan
    curve, oneCCL transport, and NUMA affinity during accepted and diagnostic
    runs. This will not create `2x` alone, but it prevents a kernel branch from
    chasing a hidden platform cap.

11. **Upstream challenge packet.**
    Package the compact route fixture, route-simulator output, current MoE
    backend selection, tensor checksums, and a small standalone benchmark for
    `vllm-xpu-kernels`/vLLM maintainers. Ask for a persistent W8A8 MoE kernel
    target against this exact shape instead of a vague "B70 is slow" report.

12. **Strict same-model engine shootout, expanded.**
    Include OpenVINO/oneDNN, latest Intel vLLM, llama.cpp SYCL, SGLang if XPU
    support is viable, and any Intel `llm-scaler` setup only when the current
    Quark W8A8 model or a byte-equivalent BF16 verifier path is used. No 4-bit,
    AWQ, or Qwen3.5 substitutions.

Artifacts for this pass:

- `data/localmaxxing-qwen36-quark-w8a8-int8-exact-refresh-20260612cu.json`
- `data/localmaxxing-qwen-b70-vllm-leaderboard-20260612cu.json`
- `data/localmaxxing-qwen-moe-fp8-leaderboard-20260612cu.json`

Reference links captured during the scan:

- `https://github.com/intel/ai-containers/blob/main/vllm/0.10.2-xpu.md`
- `https://github.com/vllm-project/vllm-xpu-kernels`
- `https://github.com/vllm-project/vllm/issues/33214`
- `https://vllm.ai/blog/2025-11-11-intel-arc-pro-b`

## EngineCore And All-Rank Timing Update 20260612bq/br

Added after the latest diagnostic gate. The hook is env-gated in local vLLM
and does not affect the accepted service unless
`VLLM_XPU_ENGINE_STEP_TIMING=1` is set. The accepted backend was restored after
timing, then passed provenance and a Qwen no-thinking quality smoke.

Measured facts:

- Rank-0 diagnostic run: `99.803 tok/s` corrected decode,
  `10.022 ms/token` TPOT, and `10.051 ms` mean EngineCore step total.
- All-rank diagnostic run: `99.829 tok/s` corrected decode,
  `9.985 ms/token` TPOT, and `9.942 ms` mean EngineCore step total.
- EngineCore is dominated by `future_result`: `9.835 ms` mean in the rank-0
  run and `9.703 ms` mean in the all-rank run.
- Scheduler schedule, scheduler update, execute submit, and sample-submit are
  all tiny compared with the token budget. Python scheduler work is not the
  missing `~5 ms/token`.
- All-rank worker labels show rank 3 as slowest:
  `6.058 ms` model-forward mean, compared with rank 1 at `5.580 ms`. This
  skew matters, but it only explains about `0.48 ms`, not the whole gap
  between no-sync worker timing and EngineCore wall time.

Immediate things to try from this:

1. **Split the `future_result` wait.**
   Add timings on the worker side around input queue receive, graph/command
   submit, command completion, all-reduce completion, output packaging, and
   result sendback. The next unknown is inside the model-execution completion
   path, not outside it.

2. **Rank-placement and affinity A/B.**
   Rotate rank-to-card placement, CPU affinity, Level Zero device order, and
   PCIe/NUMA locality. If rank 3 remains slow on the same physical card, treat
   it as topology or hardware behavior; if the slowness follows the rank, treat
   it as route skew or scheduling.

3. **All-rank route-skew ledger.**
   Log route-window statistics per layer/rank beside timing: active experts,
   max rows per expert, imbalance, and hot-expert IDs. If the slow rank is
   carrying hotter experts, topology or replication may beat kernel surgery.

4. **No-server c1 ceiling harness.**
   Build a fixed-shape in-process decode loop around the accepted model runner
   to measure the minimum possible c1 TPOT with exact token parity. This tells
   us whether vLLM's multiprocess/result path itself is burning the hidden
   `future_result` time.

5. **TP2 plus replicas as a real latency topology.**
   TP4 may be over-distributing a single token across four B70s. Test TP2 for
   c1 latency, then spend the other two cards on replicas, target-verifier
   branches, or aggregate traffic if TP2 wins.

6. **oneDNN execute-and-compare.**
   Keep advancing the sidecar, but only through a strict captured-tensor
   compare: same route window, current output checksum, oneDNN output checksum,
   max/mean diff, and automatic fallback.

7. **Future-result black-box alternates.**
   Run one short session with forced synchronization and one with deeper
   command queue traces. The goal is not to publish sync timings; it is to
   locate hidden work that no-sync labels currently miss.

Larger, bolder ideas added from this pass:

1. **C1 custom serving lane.**
   If the no-server harness shows much lower TPOT, build a production-adjacent
   c1 lane that keeps vLLM's loader/model code but replaces generic request
   scheduling with a fixed-shape, pinned, token-at-a-time loop. Quality remains
   identical because the model path and sampler output are parity-gated.

2. **Target-verifier branch farm.**
   Use spare cards or replicas to run speculative futures under the current
   Quark W8A8 target model, not a lower-quality output owner. A trained MTP or
   ngram proposer can suggest work, but only target-verified tokens commit.
   This is the clean path to `2x` if pure no-spec decode bottoms out near
   `160-180 tok/s`.

3. **Hybrid TP/EP MoE topology.**
   Keep dense/shared layers tensor-parallel, but place sparse MoE expert work
   expert-parallel or partially replicated. The current four-card TP path may
   be paying all-card synchronization for sparse work that should be local.

4. **Persistent MoE island with prepacked artifacts.**
   Prepack layer/rank/expert weights once, keep scratch and offsets resident,
   and drive each token through a persistent grouped-GEMM or oneDNN command
   ring. Store checksummed prepack metadata so reload behavior is reproducible.

5. **Whole-token Level Zero graph replay.**
   Capture fixed decode buckets across attention, MoE, residuals, sampler, and
   output handoff into a patchable command sequence. This is risky, but it is
   the boldest way to remove scattered host launches without changing math.

6. **Rank-local hot expert replicas.**
   Spend the large remaining VRAM budget on duplicated hot experts in layers
   where real route traces show repeated rank pressure. This is a memory-for-
   latency trade: identical weights, fewer cross-rank stalls.

7. **Route-class generated kernels.**
   Generate a small set of route classes from captured traffic: low active
   expert count, single hot expert, balanced broad route, and dense fallback.
   Runtime chooses a class from exact route statistics; numerical operations
   are unchanged.

8. **B70 maintainer challenge packet.**
   Package the exact W8A8 checkpoint, route-window fixtures, timing summaries,
   Localmaxxing rows, oneDNN/current-kernel compare results, xpu-smi/PCIe/NUMA
   details, and the `5 ms/token` target. This gives Intel/vLLM maintainers a
   concrete repro for "why is 4x B70 still only about 100 tok/s?"

9. **Strict 8-bit engine bakeoff.**
   Compare vLLM-XPU, OpenVINO/oneDNN, llama.cpp SYCL, and any Intel-friendly
   serving stack only when they can run the current model or a byte-equivalent
   W8A8/BF16 verifier path. The point is to learn topology and kernels, not to
   slide into 4-bit or Qwen3.5.

10. **Two production lanes with shared gates.**
    Stop assuming one launch must optimize c1 latency and aggregate throughput
    at the same time. Build a c1-latency lane and an aggregate lane, both
    judged by the same provenance, quality, and soak tests.

Artifacts for this pass:

- `patches/vllm-qwen36-engine-step-timing-20260612bq.diff`
- `data/qwen36-quark-int8-tp4-engine-step-timing-summary-20260612bq.md`
- `data/qwen36-quark-int8-tp4-engine-step-timing-summary-20260612bq.json`
- `data/qwen36-quark-int8-tp4-engine-allrank-timing-summary-20260612br.json`
- `data/localmaxxing-qwen36-b70-leaderboard-20260612bs.json`

## Follow-Up: Concrete Next Gates And Bigger Bets

Added after the latest user review. The current public Localmaxxing check still
shows only one exact-model B70/vLLM row for
`nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`, at `99.428 tok/s`. The live
endpoint mode/context sweep also ruled out two easy explanations: SSE
streaming overhead is only about `0.34%`, and p512-vs-p4096 steady decode only
moved about `0.55%`. The missing performance is therefore still in model
execution, XPU command/collective overhead, TP topology, MoE scheduling, or a
quality-safe multi-token acceptance path.

New items to keep in the near-term queue:

1. **Boundary timing maintenance run.**
   Restart the accepted endpoint with the new env-gated
   `gpu_model_runner.preprocess_total`, `forward_total`, `postprocess_total`,
   `sample_total`, and `async_output_wrap` labels. The objective is not a speed
   result; it is to partition the remaining `~4.98 ms/token` gap into named
   slices before another large kernel branch.

2. **No-server c1 ceiling lab.**
   Build a direct in-process c1 decode harness around the same model runner,
   fixed prompt shape, fixed KV allocation, and deterministic sampling. This
   isolates OpenAI API, streaming, scheduler, and request accounting overhead
   without changing math. Token-by-token parity with the live endpoint is the
   gate.

3. **Collective and command-submission ledger.**
   Add a small all-reduce and command-queue benchmark using the same oneCCL,
   Level Zero, affinity, and graph settings as the service. Current decode is
   TP4, so even a perfect MoE kernel will not reach `200 tok/s` if every token
   still burns milliseconds in collective setup or host-side synchronization.

4. **TP topology experiments as latency tests.**
   Test TP2, TP2 plus two replicas, and asymmetric latency/aggregate lanes with
   the current 32K target. If TP2 improves c1 TPOT, use the other cards for
   replicas, branch verification, or aggregate throughput instead of forcing
   every token through TP4 collectives.

5. **oneDNN sidecar execute-and-compare.**
   Move the sidecar from descriptor/probe mode to a one-layer execute-and-
   compare gate. The acceptance bar is exact output parity for captured
   route-window tensors, then a disabled live return path with rollback to
   `xpu_fused_moe`.

6. **Persistent MoE command ring.**
   Prototype a resident worker or command-list ring for the hot MoE layers:
   prepacked weights, persistent scratch, mutable route offsets, fused
   activation, and no per-token rebuild of primitives. This directly targets
   launch overhead and route imbalance instead of only GEMM math.

7. **Route-skew autotuner using real traces.**
   Feed the captured route windows into candidate schedules and emit a small
   runtime decision table keyed by layer, active expert count, max rows, and
   route skew. This keeps numerical output identical while avoiding a single
   kernel policy for both hot and sparse routes.

8. **Target-state transaction substrate.**
   Before more DFlash/MTP/ngram timing, implement the state capsule needed for
   verify, commit, and rollback: KV pages, Gated DeltaNet / hybrid state,
   scheduler counters, sampler state, and accepted-token ledgers. This is the
   prerequisite for speculation that cannot silently perturb output.

9. **Target-owned branch farming.**
   After transactional state exists, use spare VRAM/cards to evaluate multiple
   candidate continuations under the current Quark W8A8 target model. The
   proposer can be experimental, but emitted tokens must come from target
   verification. This is the cleanest route to a `2x` class result without a
   quantization downgrade.

10. **B70 W8A8 roofline packet.**
    Build a maintainer-grade packet with route-window fixtures, exact tensor
    checksums, oneDNN/current-kernel timings, XMX/DPAS counters where
    available, Localmaxxing rows, and the `5.000 ms/token` target budget. This
    makes upstream help concrete rather than asking generally why B70 is slow.

11. **Strict same-model 8-bit engine shootout.**
    Compare vLLM-XPU, OpenVINO/oneDNN, Intel `llm-scaler` or related stacks
    only if they run the current model or a byte-equivalent W8A8/BF16 verifier
    fallback. The goal is to learn scheduler/kernel topology, not to switch to
    4-bit, AWQ, Qwen3.5, or a lower-quality checkpoint.

12. **Quality and reliability scoreboard.**
    For every promising branch, record exact token parity, prompt-class
    canaries, long-context needle, BF16 fallback comparison where feasible,
    startup success, device-lost frequency, 30-60 minute soak, peak VRAM, and
    recovery behavior. A faster branch that fails soak or parity does not count.

Additional bolder ideas worth revisiting if the near-term gates stall:

- **Whole-token Level Zero supernode:** capture a fixed c1 token step as a
  command-list sequence from attention through sampler, patching only pointers
  and route offsets each token.
- **Router-predictive prefetch:** use previous-token/layer route statistics
  only for prefetch and staging. The actual router still decides computation,
  preserving output.
- **Hot-expert memory-for-latency replicas:** spend VRAM on duplicated hot
  experts in high-impact layers if route traces show the copied experts remove
  cross-rank pressure.
- **Pluggable XPU MoE backend branch:** exploit vLLM's ongoing MoE backend
  refactors and grouped-GEMM direction to make the B70 W8A8 path upstreamable,
  not a permanent local fork.
- **Two production lanes:** keep one launch optimized for c1 latency and one
  for aggregate throughput, both quality-gated against the same baseline.

External signals added to this pass:

- vLLM release notes now list Intel XPU work in the exact areas we care about:
  MXFP8/FP8 quantization, custom-op collectives, MoE top-k routing, and reduced
  XPU MoE host overhead:
  `https://github.com/vllm-project/vllm/releases`.
- vLLM's roadmap explicitly calls out a transition from `fused_moe` toward
  grouped-GEMM and expert-parallel work. That matches the local conclusion that
  generic fused-MoE scheduling is probably not enough for this c1 target:
  `https://github.com/vllm-project/vllm/issues/15735`.
- A recent vLLM quantized-MoE issue still shows quantized W8A8/W8A16 MoE
  paths falling into missing config or dtype/backend gaps. Treat this as
  evidence that B70 W8A8 MoE needs a reproducible maintainer packet, not just
  another launch flag:
  `https://github.com/vllm-project/vllm/issues/28622`.
- Localmaxxing remains useful as a public scoreboard, but the exact current
  row is still `~99 tok/s`; anything above `200 tok/s` is currently a design
  clue, not a promoted comparable result for this model/posture.

## Bigger/Bolder Refresh 20260612by

Added after the latest user review. This section is deliberately broader than
the immediate diagnostic queue, but every item keeps the hard quality rule:
the current Quark W8A8 INT8 Qwen3.6 35B-A3B target remains the owner of any
promoted output. No 4-bit/AWQ or Qwen3.5 detours.

Fresh external signals checked:

- Intel's newer XPU container notes explicitly call out the areas that map to
  our local bottlenecks: persistent MoE GEMM, fused activation, decode
  attention optimizations, data parallelism, pipeline parallelism, and expert
  parallelism. This is a strong signal that the next major gain is probably a
  backend/topology change, not a launch-flag tweak.
  Source: `https://github.com/intel/ai-containers/blob/main/vllm/0.10.2-xpu.md`
  and `https://github.com/intel/ai-containers/blob/main/vllm/0.14.1-xpu.md`.
- vLLM's XPU docs expose the relevant upstream hooks to study or adapt:
  custom ops, fused MoE modular kernels, fusion passes, model-runner v2,
  hybrid KV cache, profiling, benchmark sweeps, and optimization levels.
  Source: `https://docs.vllm.ai/en/v0.18.0/models/hardware_supported_models/xpu/`.
- Community B70 notes again point at MoE token-generation fusion as the sort
  of change that materially moves single-stream latency on Battlemage. The
  llama.cpp fused MoE TG example is a different quant/runtime path, but it is
  still a useful architectural clue for a vLLM/XPU W8A8 MoE island.
  Source: `https://github.com/Hal9000AIML/arc-pro-b70-ubuntu-gpu-speedup-bugfixes`.
- Localmaxxing exact-model public state is unchanged: the current exact-model
  B70/vLLM row is still `99.428 tok/s` at 32K context, c1, Quark W8A8 INT8.
  Source: `https://localmaxxing.com/api/benchmarks?hfId=nameistoken%2FQwen3.6-35B-A3B-Quark-W8A8-INT8&limit=20`.

Near-term ideas to keep queued:

1. **Tiny D2H token-copy isolation.**
   Benchmark shape `[1,1]` and small batched token tensors from XPU to pinned
   CPU outside vLLM. The async-output timing showed a `~3.8 ms` event wait,
   but the copied payload is only one `int32`. If the isolated copy is tiny,
   the wait is upstream queue/dependency exposure, not the token ferry itself.

2. **Device timeline for `async_copy_ready_event`.**
   Add Level Zero or torch event markers around sampler output, D2H token copy,
   worker response send, and EngineCore future completion. The current host
   labels are enough to identify the symptom, not the dependency chain.

3. **Official Intel XPU stack bakeoff.**
   Reproduce the exact model and gates on a clean Intel-maintained container
   or branch with persistent MoE and EP support. Treat this as a benchmark
   comparison, not an immediate service switch, until exact provenance and the
   Qwen no-thinking quality suite pass.

4. **EP-lite topology screen.**
   Test whether sparse MoE work can be made expert-parallel or placement-aware
   while dense/shared parts remain TP. A bad TP4 topology can leave four B70s
   doing more synchronization than useful c1 work.

5. **Rank-to-card rotation plus route ledger.**
   Repeat the all-rank timing with device order/affinity rotated and route
   skew logged per rank. If the slow rank maps to a physical card or route
   class, the solution is placement or replication before kernel surgery.

6. **oneDNN grouped-MoE resident execute path.**
   Continue from descriptor/probe mode to a resident execute-and-compare path:
   prepacked weights, persistent scratch, route-offset patching, current-output
   checksum, candidate-output checksum, max/mean diff, automatic fallback.

Bigger architecture bets:

1. **VLLM/XPU persistent MoE island.**
   Build a dedicated W8A8 MoE token-generation island for Qwen3.6 route shapes:
   resident weights, persistent scratch, fused activation/top-k weighting,
   grouped GEMM, and no per-token primitive rebuild. This is the closest local
   analog to the persistent-MoE direction Intel is advertising.

2. **Memory-for-latency hot expert replicas.**
   Use the large remaining per-card VRAM budget to duplicate the hottest expert
   shards/layers where route traces show repeated skew. This preserves weights
   exactly and buys latency by avoiding remote pressure or rank imbalance.

3. **Hybrid TP/EP scheduler for current model.**
   Stop treating TP4 as one global setting. Dense projections, attention, MoE,
   and logits may want different sharding. A layer/type-aware scheduler could
   use TP where reductions are cheap and EP/replication where sparsity makes
   all-card sync wasteful.

4. **One-token resident runner lane.**
   Build a c1-specific runner that keeps KV, sampler state, graph buckets,
   output buffers, and request state resident. It can still use vLLM's loader
   and model code, but it should skip generic request scheduling for the
   latency lane. Exact token parity with the promoted endpoint is the gate.

5. **Whole-token Level Zero replay.**
   Capture a fixed-shape token step as a patchable command-list sequence across
   attention, MoE, residuals, sampler, and output copy. This is risky, but it
   is the boldest route to removing launch/fence bubbles while keeping math
   unchanged.

6. **Target-owned speculative branch farm.**
   Once transactional state exists, use spare cards or replicas for future
   branches that are verified by the current target model before commit. The
   proposer can be weak, but emitted tokens stay target-owned.

7. **Same-model engine adapter shootout.**
   Try OpenVINO/oneDNN GenAI, llm-scaler, SGLang if XPU-ready, and llama.cpp
   only behind an adapter that proves byte-equivalent W8A8 or BF16-verifier
   parity. The purpose is stealing topology/kernel ideas, not silently changing
   model quality.

8. **B70 maintainer challenge packet.**
   Prepare a compact repro with route-window tensors, exact command line,
   kernel/oneDNN comparison results, xpu-smi and PCIe/NUMA topology, timing
   summaries, Localmaxxing row IDs, quality gates, and the `5 ms/token` target
   budget. This is the best way to get useful upstream help on "why only
   `~100 tok/s` on 4x B70?"

## Tiny D2H Token Copy Isolation 20260612by

Ran the new `scripts/bench-xpu-d2h-token-copy.py` isolation bench to test the
first item above. This did not change the model service.

Artifacts:

- `scripts/bench-xpu-d2h-token-copy.py`
- `data/qwen36-xpu-d2h-token-copy-20260612by.json`
- `data/qwen36-xpu-d2h-token-copy-xpu3-20260612by.json`
- `data/qwen36-xpu-d2h-token-copy-summary-20260612by.md`

Result:

- On `xpu:0`, pinned-host `1x1` nonblocking copy+event median was
  `0.010019 ms`, p99 `0.016331 ms`.
- On `xpu:0`, `48x1` nonblocking copy+event median was `0.011431 ms`, p99
  `0.018799 ms`.
- On `xpu:3`, the cross-check was similar: `1x1` median `0.010299 ms`,
  `48x1` median `0.011722 ms`.
- Empty event median was about `0.003 ms`; empty XPU synchronize median was
  about `0.025 ms`; blocking copy+sync was about `0.033-0.043 ms`.

Decision:

- The isolated token copy is roughly `200-380x` smaller than the live vLLM
  `~3.8 ms` `async_copy_ready_event.synchronize()` wait. The raw D2H token
  ferry is not the bottleneck.
- Do not spend more time on `.tolist()`, host buffer reuse, or pinned-memory
  token-copy micro-optimizations unless a later device timeline contradicts
  this result.
- Next target: device/worker timeline around sampler output, event record,
  D2H submission, worker response enqueue, and EngineCore future completion.
  The wait is almost certainly upstream queue/dependency exposure.

## Bigger/Bolder Backlog Refresh 20260612bz

Added after the D2H token-copy isolation and another external-signal scan. The
new constraint from the copy bench is important: the live `~3.8 ms`
`async_copy_ready_event.synchronize()` wait is not a tiny host token-copy
problem. It is likely exposing upstream device work, queue ordering, sampler
tail work, rank synchronization, or worker response handoff. The next ideas
therefore bias toward timeline attribution, topology changes, and architecture
changes that keep the exact current model as the quality owner.

Fresh external signals checked:

- Public B70 reports continue to show that Battlemage can scale well in some
  vLLM workloads, but MoE/runtime support is still fragile. One report cites
  high aggregate Gemma throughput while warning that MoE support is rough:
  `https://www.reddit.com/r/LocalLLaMA/comments/1sgdt7t/my_experience_with_the_intel_arc_pro_b70_for/`.
- Another B70 benchmark thread highlights MoE route shape and XPU kernels as
  the reason some multi-stream results look strong. That is useful as a design
  clue, not as a comparable Qwen3.6 INT8 result:
  `https://www.reddit.com/r/LocalLLM/comments/1sfa0iw/2x_intel_arc_b70_benchmark/`.
- vLLM's public INT8 W8A8 documentation still describes INT8 compute support
  in NVIDIA terms, which matches the local diagnosis that the XPU INT8 path is
  not a mature one-flag path for this model:
  `https://docs.vllm.ai/en/latest/features/quantization/llm_compressor/int8_w8a8/`.
- `vllm-xpu-kernels` is still the right upstream-adjacent place to watch for
  custom Intel GPU ops, SYCL/DPC++ kernels, and oneDNN-backed primitives:
  `https://github.com/vllm-project/vllm-xpu-kernels`.
- A grouped-GEMM issue in Intel's XPU backend for Triton explicitly calls out
  MoE routing skew and runtime tile tuning as the hard part. This lines up
  with the route-ledger and route-class kernel ideas:
  `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`.

Immediate next things to add to the queue:

1. **Worker/output timeline correlation.**
   Add object IDs and absolute age fields to async-output timing, then split
   worker response output into `get_output`, result pack, and response-MQ
   enqueue. Goal: prove whether the `~3.8 ms` wait starts immediately after
   sampling or whether the object sits behind worker/result queues.

2. **Event dependency chain probe.**
   Put device events around sampler/logits, token-ID copy submission,
   `async_copy_ready_event.record()`, and the rank-0 worker handoff. The D2H
   microbench says copy cost is tiny; this probe should reveal what the copy
   event is really waiting on.

3. **Rank-3 slow-path rotation.**
   Rotate rank-to-card order, CPU affinity, and Level Zero device order while
   collecting all-rank route skew. If the slow path follows a physical card,
   it is topology/hardware/driver. If it follows logical rank or route class,
   it is runtime scheduling or expert placement.

4. **Route-window roofline packet.**
   For a handful of hot layers, save route windows, active expert histograms,
   current kernel timing, tensor byte counts, and oneDNN/Triton candidate
   timings. This gives a real "bytes, DPAS work, launch count, and route skew"
   budget instead of arguing from endpoint tok/s alone.

5. **Strict clean-stack bakeoff.**
   Reproduce the exact checkpoint/gates in the latest Intel-maintained XPU
   container or `llm-scaler` stack. This is not a production switch unless
   exact provenance, quality canaries, and soak pass; it is a way to tell
   whether the local fork is behind upstream XPU kernel work.

6. **c1 lane without generic response materialization.**
   If timeline correlation shows worker response packing costs are real, build
   a fixed c1/no-logprobs output path that emits the scalar token from a pinned
   mailbox while preserving the exact same sampler result and API text.

Bigger no-quality-loss bets worth serious design time:

1. **MoE route-class kernel farm.**
   Generate and benchmark a small family of exact W8A8 MoE kernels keyed by
   real route shape: single-hot, two-hot, sparse-long-tail, broad-balanced, and
   fallback. Runtime selects by measured route statistics. Math and weights
   are unchanged; only scheduling/tile choice changes.

2. **Expert physical re-layout and hot-replica cache.**
   Reorder or duplicate experts by real Qwen3.6 traffic, not by checkpoint
   order. Hot experts that repeatedly create rank imbalance can be copied into
   spare VRAM with checksummed metadata. This spends memory to reduce remote
   pressure and slow-rank stalls without changing model values.

3. **Layer-type sharding instead of one global TP size.**
   Treat dense projections, GDN/hybrid state, MoE experts, logits, and sampler
   as different placement problems. TP4 may be right for some dense work while
   EP/replication is better for sparse MoE. A mixed scheduler is invasive but
   directly targets "four GPUs but only `~100 tok/s`."

4. **Persistent token engine.**
   Create a resident decode service inside the worker process with fixed
   graph buckets, resident KV, resident route scratch, resident output mailbox,
   and a minimal host control loop. This is a narrower alternative to rewriting
   vLLM: keep loader/model parity, remove per-token generic orchestration.

5. **Verifier-owned speculative transactions.**
   Build transactional target-state snapshots first, then let branch workers
   propose continuations that the current Quark W8A8 target verifies before
   commit. This remains the most plausible path to a true `2x` single-request
   result if no-spec decode bottoms out near `100-130 tok/s`.

6. **Cross-engine "kernel donor" harness.**
   Run OpenVINO/oneDNN GenAI, llama.cpp SYCL, and any Intel XPU stack against
   the same captured tensors or a BF16 verifier fallback, then port only the
   winning kernel/topology ideas back into the current accepted model path.
   This avoids silently changing model quality while still learning from other
   runtimes.

7. **Whole-token command-list replay with rollback.**
   Capture a token step as a patchable Level Zero command sequence and replay
   it under exact output parity checks. If a replay bucket ever diverges,
   rollback to vLLM's normal path. This is high risk, but it is the largest
   launch/fence-removal bet left.

8. **B70 maintainer challenge packet plus bounty-style issue.**
   Publish a compact packet with exact command line, model revision, local
   patches, route fixtures, timing summaries, Localmaxxing row, quality gates,
   `xpu-smi`, PCIe/NUMA, and the target budget: `5 ms/token` for c1 decode.
   The ask should be concrete: identify the hidden `~4 ms` event wait and the
   missing XPU W8A8 MoE/grouped-GEMM fast path.

Pruning rules for this backlog:

- Remove copy/list/pinned-buffer work unless a device timeline contradicts the
  D2H isolation result.
- Do not promote TP2, new containers, alternate engines, speculation, or
  re-layout work without exact provenance and the quality suite.
- Any branch that improves aggregate throughput but harms c1 latency belongs
  in a separate aggregate-serving lane, not the c1 speed goal.

## Route Overlay Diagnostic And Bolder Queue Refresh 20260612co

Added after the route-overlay diagnostic pass. This pass did not produce a new
speed win, but it added two important lessons: route capture must be placed in
the compiled replay path, and rank-map/topology diagnostics must not reuse the
production AOT cache root.

Measured facts:

- The first two route-overlay launches reused the production compile cache and
  failed during startup with cross-device tensors, e.g. `mat2 is on xpu:0,
  different from other tensors on xpu:3`. The likely cause is stale AOT state
  from the previous reversed-rank diagnostic.
- The same route-overlay launch with an isolated fresh cache root started
  cleanly and served the diagnostic request on `18081`.
- Diagnostic p512/o128/c1 on the fresh cache produced
  `94.938 tok/s` corrected after-first, `90.568 tok/s` e2e, and
  `10.453 ms/token` vLLM decode. This is attribution-only, not a promoted
  result.
- The boundary hook captured `576` all-rank rows. Pure-decode
  `forward_end_after_start_sync_ms` after the first five events was:
  rank 0 `4.020 ms` mean / `4.202 ms` median, rank 1 `4.554/4.516`,
  rank 2 `4.428/4.392`, rank 3 `4.453/4.411`.
- Route overlay payloads were present but empty: `captures=0` and no route
  hash on all rows. The current Python route-capture hook does not observe the
  actual compiled replay path used by this accepted graph family.

Operational notes to carry forward:

1. **Isolate diagnostic cache roots.**
   Any experiment that changes rank-to-device mapping, compiled graph shape,
   route capture, or worker device setup must use a dedicated
   `TORCHINDUCTOR_CACHE_DIR` and `VLLM_CACHE_ROOT`, or explicitly quarantine
   stale AOT hashes before restoring production.

2. **Move route capture below Python router callbacks.**
   Capture `topk_ids` / `topk_weights` at the lower compiled path: immediately
   after expert selection in the MoE runner, inside the shared MoE custom-op
   wrapper, or from a graph-safe side channel. A Python callback on the router
   object is not enough under AOT replay.

3. **Route overlay remains the next attribution gate.**
   The rank timing still says model-forward-side work is the wait. We need
   route signatures beside those timing rows before deciding between
   route-class kernels, expert replication, or TP/EP topology changes.

4. **Promoted service restore must include cache hygiene.**
   The accepted endpoint should be relaunched only after checking whether the
   production cache still selects the clean graph. If it selects the stale
   reversed-rank AOT hash, quarantine that hash rather than debugging service
   flags.

Restore status:

- Stopped the fresh-cache route-overlay diagnostic and restored the accepted
  TP4 endpoint on `18080` with `scripts/launch-qwen36-quark-int8-accepted.sh`.
- The standard accepted launcher came back without needing cache quarantine.
- Provenance passed exact sentinels `4752`, `11436`, and `198`.
- The no-thinking quality smoke passed and matched the previous accepted
  baseline across the checked cases.

New things to add to the near-term queue:

1. **Compiled-path route ledger.**
   Add a graph-safe route ledger in the MoE runner/custom-op path with per-rank
   route hash, active expert count, max rows per expert, top hot experts, and
   layer family. Keep it env-gated and limited to one-token decode windows.

2. **AOT cache provenance manifest.**
   Write a small cache manifest beside each accepted launch: source revision,
   rank map, physical device order, model revision, key env vars, and AOT hash.
   This turns cache pollution from a mystery into a visible mismatch.

3. **Route-fixture replay outside vLLM serving.**
   Extract real route windows and replay just the MoE layer kernels with the
   same W8A8 tensors. This avoids waiting on full endpoint startup for every
   kernel/tile idea.

4. **Layer-family timing with route context.**
   Split model forward into dense attention/GDN, sparse MoE, logits, and
   sampler-adjacent sections, then attach route summaries to MoE layers only.
   That tells us whether the `~4.5 ms` forward wait is broad or concentrated.

5. **TP2 latency with cache isolation.**
   Re-run TP2 as a latency experiment with a clean cache root and exact gates.
   If TP2 materially improves c1, the other two cards can serve replicas,
   target-verifier branches, or aggregate traffic.

6. **Localmaxxing comparison query before every claim.**
   Query the exact model ID and B70/vLLM class before posting. The best public
   exact row remains the `~99 tok/s` accepted result; new diagnostic rows do
   not get posted unless they pass provenance, quality, and stability.

Bigger and bolder ideas added from this pass:

1. **Route-aware expert cache compiler.**
   Use captured traffic to generate a static expert placement/replication
   plan per layer: hot experts duplicated, cold experts left sharded, and
   route-class kernels preselected. The model values are unchanged; memory is
   traded for less synchronization and less skew.

2. **XPU MoE plugin in `vllm-xpu-kernels`.**
   Build the W8A8 Qwen3.6 MoE island as a custom XPU op/plugin rather than
   burying it only in the local vLLM fork. The upstream XPU kernels repo is
   designed for Intel GPU custom ops and oneDNN-backed primitives, so this is
   the cleanest path to a maintainable fast path.

3. **oneDNN grouped-memory MoE sidecar.**
   oneDNN now has experimental grouped memory/grouped matmul support and a
   max-group-size execution hint for MoE-like workloads. Try it first on real
   route fixtures, then only wire it into serving behind exact compare/fallback.

4. **Column-major/locality schedule transfer.**
   Borrow the locality-aware grouped-GEMM idea from MoE kernel research: sort
   or bucket work for cache/locality without changing arithmetic. On XPU this
   should be evaluated with real Qwen3.6 route distributions, not synthetic
   balanced routes.

5. **Two-card latency cell plus two-card verifier/replica cell.**
   If TP4 keeps losing c1 time to cross-card coordination, split the machine
   into a lower-latency TP2 cell and a second utility cell for target-owned
   speculative verification, redundancy, or aggregate requests.

6. **Static c1 micro-engine as a truth oracle.**
   Build a minimal single-request decode loop that bypasses OpenAI serving but
   uses the same weights, graph buckets, KV state, and sampler. If it cannot
   beat `~100 tok/s`, the bottleneck is model/kernel. If it does, the serving
   stack still has removable orchestration cost.

7. **Maintainer-grade route/timeline bundle.**
   Publish a compact repro with the exact model, cache manifest, route
   fixtures, all-rank timing, oneDNN/current-kernel comparison, Localmaxxing
   row, and quality gates. The concrete ask: help close the gap from
   `~10 ms/token` to `~5 ms/token` for B70 W8A8 MoE decode.

Sources added to this refresh:

- vLLM's fused MoE kernel design documents describe expert-parallel all2all
  backends, quantization formats, fused expert kernels, and modular kernel
  families: `https://docs.vllm.ai/en/latest/design/moe_kernel_features/`.
- oneDNN release notes list experimental grouped memory/grouped matmul support
  for MoE and a `DNNL_ARG_HINT_MAX_GROUP_SIZE` execution-time hint:
  `https://github.com/uxlfoundation/oneDNN/releases`.
- Intel's Triton XPU grouped-GEMM issue highlights decode route skew and real
  token distributions as key to MoE performance tuning:
  `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`.
- `vllm-xpu-kernels` is the upstream-adjacent custom-op home for Intel XPU
  kernels and oneDNN-backed primitives:
  `https://github.com/vllm-project/vllm-xpu-kernels`.
- Public B70 llama.cpp/SYCL numbers show Qwen3.6 MoE can be attractive on B70,
  but the comparable rows are lower-bit and different-runtime signals rather
  than accepted W8A8/vLLM replacements:
  `https://github.com/PMZFX/intel-arc-pro-b70-benchmarks`.

Artifacts for this pass:

- `patches/vllm-qwen36-route-overlay-diagnostic-20260612co.md`
- `data/qwen36-quark-int8-tp4-routeoverlay-diagnostic-summary-20260612co.json`
- `data/qwen36-quark-int8-tp4-routeoverlay-20260612cn.log`
- `data/qwen36-quark-int8-tp4-routeoverlay-20260612cn2.log`
- `data/qwen36-quark-int8-tp4-routeoverlay-freshcache-20260612cn3.log`
- `data/qwen36-quark-int8-tp4-routeoverlay-freshcache-p512o128-metrics-20260612cn3.json`
- `data/qwen36-quark-int8-tp4-accepted-restored-after-routeoverlay-20260612co.log`
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-routeoverlay-20260612co.json`
- `data/qwen36-quark-int8-tp4-accepted-quality-after-routeoverlay-nothink-smoke-20260612co.json`

## Route Fixture Diagnostic 20260612cr

Added after the follow-up route-overlay work. This pass separated two things
that were previously conflated:

- The accepted compiled replay path still needs a lower-level route capture
  mechanism.
- Eager route fixtures are enough to understand the c1 decode route shape,
  even though eager timing is not comparable.

Measured facts:

- Compiled route-counter diagnostic `20260612cp2` stayed near the accepted
  timing envelope at `96.828 tok/s` corrected p512/o128 and
  `10.249 ms/token` vLLM decode, but route overlay still produced
  `captures=0`.
- The new counters show why: route capture was registered for all `40` MoE
  layers and called during the 512-token prefill rows (`capture_calls=80` per
  prefill row), but no one-token decode calls reached the Python route hook.
  Decode is being served by compiled replay that bypasses Python callbacks.
- Eager route-fixture diagnostic `20260612cq2` was intentionally slow:
  `10.718 tok/s` corrected p512/o32 and `90.374 ms/token` vLLM decode. Do not
  compare that speed to accepted graph runs.
- The eager route fixture captured `5440` route summaries over `76` boundary
  rows with `31` route hashes. Top repeated experts across the small sample
  included `117`, `43`, `134`, `20`, `189`, `182`, `158`, and `116`.
- The important shape lesson: c1 decode is not a hot-batched grouped-GEMM
  problem. Each layer is fundamentally one token routed to topk-8 unique
  experts. The c1 kernel target is a persistent single-token/topk-8 W8A8 MoE
  island with resident weights/scratch and minimal dispatch overhead.

Decisions:

1. **For accepted graph attribution, Python hooks are done.**
   The next route ledger must be graph-output based or live inside the XPU
   MoE custom-op path. Python callbacks can collect eager fixtures but not
   accepted decode replay routes.

2. **Lead with single-token/topk-8 MoE, not hot batching.**
   oneDNN grouped matmul and route-class kernels still matter, but the first
   c1 target should optimize the topk-8 single-token route shape, avoiding
   per-token primitive rebuilds and launch/fence bubbles.

3. **Keep hot expert replication as secondary.**
   Expert replication may help aggregate throughput, branch verification, or
   multi-token speculative lanes. It is less likely to be the primary c1 fix
   when each layer has one row per selected expert.

4. **Use eager route fixtures as kernel input.**
   Captured eager route summaries are acceptable input for offline kernel
   fixture design, as long as any serving integration is later proven by exact
   accepted-output gates.

New near-term implementation ideas:

1. **Custom-op route side channel.**
   Add an optional diagnostic output from the XPU MoE custom op: compact route
   hash, active expert count, and max rows per expert. Keep it disabled in
   production and avoid CPU copies inside the replay path.

2. **Single-token topk-8 W8A8 microbench.**
   Build a fixture that takes one hidden vector plus eight routed experts for
   a representative layer and measures current vLLM/XPU, oneDNN grouped
   matmul, and a hand-packed persistent path.

3. **Resident expert scratch ring.**
   Preallocate and reuse per-layer scratch for the topk-8 route shape so
   accepted decode does not rebuild small intermediates every token.

4. **Layer subset first.**
   Start with two or three representative layers from the route fixture before
   attempting all 40 MoE layers. Gate each layer with exact tensor compare.

5. **Graph-safe route hash only.**
   For the next accepted diagnostic, capture only route hashes/counts, not
   full IDs, so the probe is less likely to perturb graph replay.

Follow-up artifact:

- Extracted `data/qwen36-quark-int8-tp4-routefixture-firstdecode-routes-20260612cr.json`
  from the eager summary. It contains three first-decode examples with all
  `40` MoE layers and each layer's selected topk expert IDs. This is the
  compact input for the single-token/topk-8 microbench design.

Artifacts for this pass:

- `data/qwen36-quark-int8-tp4-routefixture-diagnostic-summary-20260612cr.json`
- `data/qwen36-quark-int8-tp4-routeoverlay-counters-20260612cp2.log`
- `data/qwen36-quark-int8-tp4-routeoverlay-counters-p512o128-metrics-20260612cp2.json`
- `data/qwen36-quark-int8-tp4-routeoverlay-eager-20260612cq2.log`
- `data/qwen36-quark-int8-tp4-routeoverlay-eager-p512o32-metrics-20260612cq2.json`
- `data/qwen36-quark-int8-tp4-routeoverlay-eager-summary-20260612cq2.json`
- `data/qwen36-quark-int8-tp4-routefixture-firstdecode-routes-20260612cr.json`
- `data/qwen36-quark-int8-tp4-accepted-restored-after-routefixture-20260612cr.log`
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-routefixture-20260612cr.json`
- `data/qwen36-quark-int8-tp4-accepted-quality-after-routefixture-nothink-smoke-20260612cr.json`

## Worker/Async Output Timeline 20260612bz

Implemented the first immediate queue item from the backlog refresh: object-ID
correlation and a split around worker output materialization. The local vLLM
patch is env-gated through existing timing flags and is tracked as:

- `patches/vllm-qwen36-worker-output-timeline-20260612bz.diff`

Diagnostic run:

- Endpoint posture: current accepted TP4/Quark W8A8 INT8/32K/no-prefix launch.
- Benchmark: p512/o384/c1 stream, two measured repeats after warmup.
- Corrected output throughput: `100.009 tok/s`.
- vLLM decode histogram mean: `9.975 ms/generation token`.
- vLLM TPOT/inter-token histogram mean: `10.001 ms/token`.

Key timing split:

- Engine step total mean: `9.973 ms`.
- Engine `future_result` mean: `9.783 ms`.
- `sample_tokens` executor response wait mean: `4.649 ms`.
- Rank-0 worker response enqueue mean: `4.325 ms`.
- Rank-0 `AsyncModelRunnerOutput.get_output()` mean: `4.241 ms`.
- Response-MQ enqueue mean: `0.081 ms`.
- Result tuple packing mean: `0.00047 ms`.
- Async object created to `get_output()` start: `0.269 ms`.
- D2H copy-submit end to `get_output()` start: `0.168 ms`.
- `async_copy_ready_event.synchronize()` mean: `4.044 ms`.
- Token scalar/list conversion mean: `0.019 ms`.

Interpretation:

- The output object is not waiting in a long Python queue. It reaches
  `get_output()` roughly `0.17 ms` after the copy submission ends.
- Python result packing and response-MQ enqueue are not the hidden
  multi-millisecond cost.
- The `~4 ms` cost is still the async event sync. Together with the tiny D2H
  isolation bench, this points at upstream device dependency exposure: sampler
  tail, logits, graph/event ordering, rank synchronization, or command-queue
  dependency, not host token-copy mechanics.

Restore/quality gate:

- Accepted backend restored in tmux session
  `qwen36-tp4-accepted-restored-after-worker-output-timeline-20260612bz`.
- Accepted provenance passed both prompt cases and sentinels `4752`, `11436`,
  and `198`.
- Short no-thinking Qwen text quality smoke passed exact OK, copy phrase,
  arithmetic, JSON schema, and repeat stability.

Artifacts:

- `data/qwen36-quark-int8-tp4-worker-output-timeline-20260612bz.log`
- `data/qwen36-quark-int8-tp4-worker-output-timeline-p512o384-metrics-20260612bz.json`
- `data/qwen36-quark-int8-tp4-worker-output-timeline-summary-20260612bz.json`
- `data/qwen36-quark-int8-tp4-worker-output-timeline-summary-20260612bz.md`
- `data/qwen36-quark-int8-tp4-accepted-restored-after-worker-output-timeline-20260612bz.log`
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-worker-output-timeline-20260612bz.json`
- `data/qwen36-quark-int8-tp4-accepted-quality-after-worker-output-timeline-nothink-smoke-20260612bz.json`

Next concrete measurement:

1. Add device events around sampler/logits completion, D2H token-copy
   submission, event record, and event sync.
2. Correlate that with rank/device route skew and rank-to-card rotation.
3. Keep result-packing/mailbox work pruned unless this device timeline shows a
   new host-side dependency.

## Async Device Timeline And Stage Split 20260612ca-cc

Followed the worker/output timeline with three diagnostic-only event probes:

1. `20260612ca`: device timing events around sampler/copy/default stream.
2. `20260612cb`: host sync split between the default-stream marker and the
   copy-ready event.
3. `20260612cc`: host sync split across sampler end, state update,
   bookkeeping, pre-async-wrap, default-before-copy, and copy-ready.

Patch:

- `patches/vllm-qwen36-async-device-timeline-20260612cc.diff`

Important caveat:

- These probes are not speed candidates. XPU timing events and staged host
  synchronizes slowed decode to about `76.6-77.4 tok/s` corrected. Use them
  only for attribution.

Key results:

- Device elapsed event timings were tiny:
  - `device_default_before_copy_to_ready_ms`: about `0.0077 ms`.
  - `device_copy_stream_entry_to_ready_ms`: about `0.0065 ms`.
  - `device_sample_start_to_copy_ready_ms`: about `0.064-0.065 ms`.
- Host sync remained multi-ms:
  - ca `sync_ms`: `4.962 ms` mean.
  - cb `sync_ms`: `5.957 ms` mean.
  - cc `sync_ms`: `5.066 ms` mean.
- cb showed the wait is default-stream readiness, not copy:
  - `default_ready_sync_ms`: `5.933 ms` mean.
  - `copy_after_default_sync_ms`: `0.021 ms` mean.
- cc showed the wait is already present at sampler end:
  - `stage_sample_end_sync_ms`: `5.007 ms` mean.
  - `stage_state_update_sync_ms`: `0.026 ms` mean.
  - `stage_bookkeeping_sync_ms`: `0.0088 ms` mean.
  - `stage_pre_async_wrap_sync_ms`: `0.0033 ms` mean.
  - `default_ready_sync_ms`: `0.0025 ms` mean.
  - `copy_after_default_sync_ms`: `0.0107 ms` mean.

Interpretation:

- The host returns from `_sample(...)` before the XPU/default-stream work
  needed for the token has completed. The async output event is where that
  unresolved device work becomes visible.
- Post-sample state update, bookkeeping, async-wrap setup, D2H copy, token list
  conversion, response tuple packing, and response-MQ enqueue are all ruled out
  as multi-ms c1 bottlenecks.
- Device elapsed event values alone are insufficient for host-latency
  attribution because they exclude time spent waiting for previously queued
  default-stream work to become ready.

New pruning rule:

- Stop output-materialization work for the `2x` target unless a later trace
  contradicts this result. The remaining `~5 ms` target is model tail, logits,
  sampler, graph/queue ordering, TP collectives, or rank imbalance.

Artifacts:

- `data/qwen36-quark-int8-tp4-async-device-timeline-20260612ca.log`
- `data/qwen36-quark-int8-tp4-async-device-timeline-p512o384-metrics-20260612ca.json`
- `data/qwen36-quark-int8-tp4-async-device-timeline-summary-20260612ca.json`
- `data/qwen36-quark-int8-tp4-async-device-syncsplit-20260612cb.log`
- `data/qwen36-quark-int8-tp4-async-device-syncsplit-p512o256-metrics-20260612cb.json`
- `data/qwen36-quark-int8-tp4-async-device-syncsplit-summary-20260612cb.json`
- `data/qwen36-quark-int8-tp4-async-device-stagesplit-20260612cc.log`
- `data/qwen36-quark-int8-tp4-async-device-stagesplit-p512o192-metrics-20260612cc.json`
- `data/qwen36-quark-int8-tp4-async-device-stagesplit-summary-20260612cc.json`
- `data/qwen36-quark-int8-tp4-async-device-stagesplit-summary-20260612cc.md`
- `data/qwen36-quark-int8-tp4-accepted-restored-after-async-device-stagesplit-20260612cc.log`
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-async-device-stagesplit-20260612cc.json`
- `data/qwen36-quark-int8-tp4-accepted-quality-after-async-device-stagesplit-nothink-smoke-20260612cc.json`

Next concrete measurement:

1. Split `_sample(...)` and the preceding model/logits tail with staged host
   synchronizes or lower-overhead queue markers.
2. Attribute the remaining `~5 ms` to logits processor, sampler kernels,
   graph-captured model tail, TP collectives, or rank imbalance.
3. Then decide between sampler/logits surgery, TP/rank placement, or MoE/graph
   kernel work. Do not start another output-copy branch.

## Larger Bet Addendum 20260612cd

Added after the async device stage split and a fresh public-source scan. The
headline is unchanged: no new promoted speed win. The value of this pass is
turning the `stage_sample_end_sync_ms ~= 5 ms` finding into bigger experiments
that could plausibly move c1 decode without changing model quality.

Fresh external/context signals:

- Localmaxxing exact-model query still has one approved public row for
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`: `99.428358 tok/s`,
  `76.454 ms` TTFT, `196.325` total tok/s. This remains the public exact
  checkpoint/B70/vLLM reference.
- Broader Qwen 30B-class leaderboard rows above `200 tok/s` are mostly not
  directly comparable because they use NVFP4, MTP/DFlash, CUDA/Blackwell, lower
  precision, shorter context, or different engines. Use them as architecture
  clues only.
- Intel Triton/XPU grouped-GEMM issues are still active. Issue #5918 reports a
  large gap between pointer-based grouped GEMM and contiguous-memory variants,
  with oneDNN and contiguous layouts showing much higher ceilings. Issue #6861
  tracks poor grouped-GEMM performance as a current performance task.
- Intel issue #6840 explicitly recommends comparing Triton, oneDNN, and
  SYCL-TLA baselines for GEMM-style work. For us, that argues for a provider
  bakeoff using real Qwen route windows, not another isolated launch flag.

New artifacts:

- `data/localmaxxing-qwen36-quark-w8a8-int8-exact-20260612.json`
- `data/localmaxxing-qwen36-30b-class-leaderboard-20260612.json`

Near-term measurements to add:

1. **Inside `_sample(...)` stage split.**
   The current split says the wait exists by sampler return. Next split logits
   processor, sampler kernel launch, sampler postprocess, and any final-logits
   sync inside `_sample`. Use low-repeat diagnostics only.

2. **Vocab-sharded greedy argmax proof.**
   For temperature `0`, no logprobs, and no penalties, compute per-rank top-1
   logits and all-reduce only `(value, token_id, tie_break)` instead of
   materializing/gathering the full vocab path. This can be exact if tie
   behavior matches. It is one of the few sampler/logits ideas with real
   multi-ms upside and no model-quality trade.

3. **Final-logits fingerprint harness.**
   Before changing sampler/logits, record deterministic hashes of full logits,
   per-rank top-k, final sampled token, and tie order for a small prompt suite.
   This becomes the no-quality-loss gate for greedy fast paths.

4. **Provider bakeoff on real MoE route windows.**
   Build a harness that feeds captured Qwen route windows into current
   `vllm-xpu-kernels`, oneDNN grouped matmul/BRGEMM where possible, SYCL-TLA,
   and Triton variants. Score exact output diff plus us/token. Use the current
   route histograms, not synthetic balanced groups.

5. **Retile/repack cache for W8A8 experts.**
   Keep the exact Quark INT8 values and scales, but store additional
   XPU-friendly physical layouts for hot experts. This spends spare VRAM for
   lower gather/descriptor overhead and should be quality-neutral if the math
   path is byte-equivalent.

6. **All-rank route-skew timeline.**
   Pair the sampler-end wait with active expert IDs, per-rank active rows, and
   collective spans. If the `~5 ms` wait follows a slow rank or route class,
   topology/layout work beats sampler surgery.

7. **One-token static runner ceiling.**
   A minimal in-process c1 loop with static buffers and no OpenAI serving path
   still matters. It separates vLLM scheduler/executor cost from model/kernel
   cost. Exact token parity is mandatory before any speed interpretation.

8. **Verifier-preserving speculation lane, but only after state proof.**
   Public fast rows keep pointing at MTP/DFlash-style acceptance. For this
   checkpoint, the only acceptable version is target-owned temporary KV/GDN/
   scheduler state with exact commit/rollback. Do not benchmark more speculation
   until `k=1` exact parity is fixed.

9. **Whole-token Level Zero replay experiment.**
   If `_sample` and model tail are mostly queue/graph-bound rather than raw
   kernel-bound, prototype a fixed decode-bucket command-list replay with
   patchable token/KV addresses. The target is fewer host submissions and fewer
   default-stream visibility points.

10. **B70 upstream challenge bundle.**
    Package the exact model, public Localmaxxing row, async stage-split logs,
    route-window fixtures, provider bakeoff harness, and `5 ms/token` budget for
    Intel/vLLM maintainers. The grouped-GEMM issue history suggests external
    kernel work may be needed for a real `2x`.

Biggest plausible no-quality-loss paths, ranked:

1. Exact sampler/logits fast path for greedy no-logprobs requests.
2. Provider/layout replacement for real Qwen W8A8 route windows.
3. Hybrid route-aware TP/EP plus hot-expert physical replication.
4. Fixed-shape c1 runner or Level Zero replay if host/graph boundaries dominate.
5. Verifier-owned speculation after state parity is proven.

## Bolder Opportunity Refresh 20260612bq

Added after the boundary timing discussion and the latest Localmaxxing refresh.
This is a backlog, not a claim. The hard constraint remains unchanged: current
Quark W8A8 INT8 Qwen3.6 35B-A3B output is the quality owner, and no 4-bit/AWQ
or Qwen3.5 shortcut belongs in the promoted path.

Fresh signals:

- Exact current-model Localmaxxing still has only one public exact-model row on
  B70/vLLM: `99.428 tok/s` for
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`.
- The broader Qwen/B70/vLLM refresh still tops out at `99.770 tok/s` for the
  same Quark W8A8 INT8 run family. This supports treating `~100 tok/s` as the
  honest accepted baseline, not a bad frontdoor artifact.
- Overall B70 rows above this are useful only as architecture clues: aggregate
  batch lanes, Gemma/MiniMax, lower precision, shorter contexts, or speculative
  paths. They do not replace the current-model 8-bit target.
- vLLM's current MoE design docs emphasize modular all2all/EP backends,
  backend-specific quantization formats, async overlap, and multiple experts
  kernels. That matches our next topology question: the B70 path probably needs
  a real mixed TP/EP or route-aware MoE backend, not just another wrapper around
  the current fused-MoE call.
- oneDNN has experimental grouped memory/grouped matmul support aimed at MoE
  workloads, including an execution-time max-group-size hint and Intel GPU
  optimized functionality. This keeps the oneDNN sidecar path worth pursuing,
  but only if it becomes a resident execute-and-compare path with real
  token-step accounting.

Items to keep in the immediate "things to try" queue:

1. **EngineCore wall-time ledger.**
   Add env-gated timing around `EngineCore.step()` and `step_with_batch_queue`:
   scheduler schedule, execute submit, future wait, sample fallback, aborts,
   and scheduler update. The boundary run left an apparent `~4.39 ms/token`
   gap between endpoint decode and rank-0 no-sync forward; this is the next
   highest-value measurement.

2. **All-rank timing and slow-rank attribution.**
   Repeat the timing run with all ranks sampled, then compare rank-local
   forward, attention, MoE, and all-reduce spans. If one rank consistently sets
   the token pace, attack placement, route skew, PCIe locality, or affinity
   before writing a new kernel.

3. **Synchronized step probe without promotion.**
   Run one short sync-on timing session to locate hidden device work, but do
   not use sync timings as a speed benchmark. The previous sync model-only
   proxy inflated model-forward to `~8.433 ms/token`, which is useful for
   diagnosis and dangerous for headline results.

4. **oneDNN execute-and-compare gate.**
   Promote the sidecar from descriptor creation to one captured layer execute:
   same live route-window tensors, current-kernel output checksum, oneDNN
   output checksum, max/mean diff, and fallback to current output. Only after
   parity should it enter a timing run.

5. **TP2 plus replicas as a latency topology.**
   Test whether TP4 collectives are the single-request limiter. If TP2 is
   faster for c1, spend the remaining two cards on replicas, verification
   branches, or aggregate throughput instead of forcing every token through
   TP4.

6. **c1 no-server model-runner lane.**
   Build the smallest in-process fixed-shape decode loop around the accepted
   model runner. The goal is a ceiling measurement for vLLM scheduler/API
   overhead with exact token parity, not a new production architecture yet.

7. **Verifier-state transaction proof.**
   Stop timing speculation until a minimal copy-on-write state fork exists for
   KV pages, Gated DeltaNet/hybrid state, scheduler counters, sampler state,
   and accepted-token ledgers. If it cannot prove exact rollback/commit, it is
   not a no-quality-loss path.

Bigger, bolder ideas to keep visible:

1. **Mixed TP/EP current-model topology.**
   Keep dense/shared work tensor-parallel where needed, but make MoE experts
   expert-parallel or placement-aware so sparse expert work stops paying
   full-TP collectives every token. This is a larger vLLM/XPU backend change,
   but it attacks the "four GPUs slower than expected" problem structurally.

2. **Rank-local persistent MoE island.**
   For hot MoE layers, create a resident rank-local worker/command ring with
   prepacked weights, preallocated scratch, mutable grouped offsets, fused
   activation/top-k weighting, and no per-token primitive rebuild. Treat the
   oneDNN route-window result as the fixture source.

3. **Whole-token command-list supernode.**
   Capture a fixed c1 decode bucket from attention through sampler into a
   Level Zero command sequence where only pointers, route offsets, and KV
   indices are patched per token. This is risky but directly targets host
   launch latency and scattered framework boundaries.

4. **Target-owned self-speculation.**
   Instead of trusting a separate weaker drafter, let spare cards run future
   target-model branches against transactional state. Only tokens accepted by
   the current target state commit. This is expensive in VRAM, but we have
   little c1 use for idle cards if TP2/replica topology wins.

5. **Route-class code generation.**
   Generate a few route-window kernel/layout classes from captured traces
   rather than one generic MoE policy. Examples: low-active-expert, high-skew
   hot expert, wide balanced route, and dense fallback. Numerical math stays
   identical; only scheduling/layout changes.

6. **B70 roofline plus maintainer challenge packet.**
   Package route-window tensors, per-stage timing, VTune/Level Zero counters,
   oneDNN and current-kernel timings, PCIe/CCL topology, and exact quality
   gates into a repro that an Intel/vLLM maintainer can run. The goal is to
   make "why only 100 tok/s?" answerable with counters, not anecdotes.

7. **Strict high-fidelity engine bakeoff with an adapter, not a detour.**
   Try OpenVINO/oneDNN GenAI, llama.cpp SYCL, llm-scaler, or a minimal custom
   runner only if the artifact is current-model W8A8/BF16-verifier-equivalent
   and passes the same prompt/token gates. Use other engines to steal topology
   ideas before accepting a service switch.

8. **Production split by objective.**
   Plan for two lanes if the data supports it: a c1 latency lane with fixed
   shapes/topology and a separate aggregate throughput lane with larger
   batching. Both lanes must share the same quality, provenance, soak, and
   recovery gates.

New artifacts from this refresh:

- `data/localmaxxing-qwen36-quark-w8a8-int8-exact-refresh-20260612bq.json`
- `data/localmaxxing-qwen-b70-vllm-leaderboard-20260612bq.json`
- `data/localmaxxing-b70-overall-leaderboard-20260612bq.json`

## Boundary Timing Gate 20260612bp

Ran the first maintenance-window boundary timing session with the current
accepted Quark W8A8 INT8 TP4 model and the env-gated labels added in the local
vLLM source. The live service was restored afterward.

Artifacts:

- `data/qwen36-quark-int8-tp4-boundary-timing-20260612bp.log`
- `data/qwen36-quark-int8-tp4-boundary-timing-p512o256-metrics-20260612bp.json`
- `data/qwen36-quark-int8-tp4-boundary-timing-summary-20260612bp.json`
- `data/qwen36-quark-int8-tp4-boundary-timing-summary-20260612bp.md`
- `data/qwen36-quark-int8-tp4-accepted-restored-after-boundary-timing-20260612bp.log`
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-boundary-timing-20260612bp.json`
- `data/qwen36-quark-int8-tp4-accepted-quality-after-boundary-timing-nothink-smoke-20260612bp.json`

Endpoint result:

- Prompt/output: vLLM-random p512/o256, c1, streaming, `ignore_eos=true`.
- Corrected decode median: `99.796 tok/s`.
- vLLM decode histogram median: `9.984 ms/token`.
- vLLM time-per-output-token median: `10.023 ms/token`.
- Queue time stayed negligible: `0.0075 ms/request`.
- Diagnostic timing labels therefore did not materially perturb the baseline.

Rank-0 sampled pure-decode step timing:

- `gpu_model_runner.forward_total`: `5.648 ms/step` mean.
- `gpu_model_runner.model_forward`: `5.593 ms/step` mean.
- Nested `gdn_attention_core_xpu.native`: `1.507 ms/step` mean across `30`
  calls per sampled step.
- `gpu_model_runner.postprocess_total`: `0.308 ms/step`.
- `gpu_model_runner.compute_logits`: `0.228 ms/step`.
- `gpu_model_runner.sample_total`: `0.162 ms/step`.
- `gpu_model_runner.async_output_wrap`: `0.104 ms/step`.

Interpretation:

- The endpoint is still about `10 ms/token`, while the rank-0 no-sync
  `model_forward` proxy is about `5.59 ms/token`. That leaves about
  `4.39 ms/token` unexplained by this asynchronous rank-0 forward proxy.
- The labels are nested and overlapping. They must not be summed into a token
  budget.
- The tiny gap between `forward_total` and `model_forward` means Python wrapping
  immediately around model forward is not the big missing slice.
- Postprocess, logits, sampler, and async output wrap are too small to reach
  `200 tok/s` by themselves.
- The next profiling branch should measure scheduler/engine step wall time,
  rank-to-rank variance, synchronized all-rank forward cost, collectives, and
  host/device synchronization. The prior sync model-only proxy
  (`~8.433 ms/token`) now looks like a real clue: most of the missing wall time
  may be hidden asynchronous device work or synchronization outside the
  no-sync rank-0 forward label.

Restore and quality:

- Restored accepted endpoint in
  `qwen36-tp4-accepted-restored-after-boundary-timing-20260612bp`.
- `/v1/models` reports the current
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` snapshot at 32K context.
- Accepted provenance passed both prefix cases and sentinels `4752`, `11436`,
  and `198`.
- A short Qwen-specific no-thinking text quality smoke passed exact OK, copy
  phrase, arithmetic, JSON schema, and repeat checks. The generic
  `openai-quality-canary.py` is not a valid Qwen3.6 direct-chat gate without
  the model-specific no-thinking path; it starts receiving thinking text.

## Live C1 200 Tok/s Gap Budget

Added a reproducible gap-budget artifact around the current accepted endpoint.
This does not change the server; it measures the live c1 path and converts the
result into the latency that must disappear to reach the `200 tok/s` goal.

Artifacts:

- `scripts/qwen36-c1-gap-budget.py`
- `data/qwen36-quark-int8-tp4-live-c1-p512o512-metrics-20260612bm.json`
- `data/qwen36-quark-int8-tp4-live-c1-gap-budget-20260612bm.json`
- `data/qwen36-quark-int8-tp4-live-c1-gap-budget-20260612bm.md`
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-c1-gap-budget-20260612bm.json`

Measurement:

- Endpoint: `http://127.0.0.1:18080`, current accepted Quark W8A8 INT8 TP4
  service, 32K context.
- Prompt/output: vLLM-random p512/o512, c1, streaming, `ignore_eos=true`,
  three measured repeats after a small warmup.
- Corrected decode median: `100.013 tok/s`.
- vLLM decode histogram median: `9.980 ms/token`.
- Target `200 tok/s` budget: `5.000 ms/token`.
- Required saving: `4.980 ms/token`, or `49.9%` of current decode latency.
- Queue time is not the issue for c1: `0.0086 ms/request`.
- Prefill for this p512 run is about `69.145 ms/request`; decode is about
  `5109.901 ms/request`.
- Inter-token latency histogram is essentially `10.000 ms/token`.

Interpretation:

- A subsystem that accounts for less than half of decode latency cannot reach
  `200 tok/s` by itself, even with infinite speedup.
- If the optimized stage is `60%` of decode, it needs about `5.94x` speedup.
  At `70%`, it still needs about `3.48x`; at `80%`, about `2.66x`.
- This makes a narrow microsecond-scale GEMM tweak insufficient as a standalone
  headline result. The sidecar/oneDNN/custom-kernel path is still worth doing,
  but only if it attacks a multi-millisecond decode slice such as persistent
  MoE scheduling, queue/command submission, activation/gather fusion, or
  collectives.
- Target-verified multi-token acceptance remains a separate `2x`-class path:
  it can reduce effective emitted-token latency while preserving the current
  Quark W8A8 verifier as the output owner.

Quality guard:

- After the benchmark, accepted provenance passed both prefix cases and all
  sentinel tokens: `4752`, `11436`, and `198`.

Immediate consequence:

1. Add device-side token-step timing before committing to another custom kernel.
2. Keep the sidecar launcher ready for the next maintenance window.
3. Treat TP2/single-lane and verifier-transaction experiments as serious
   candidates because the required saving is too large for small flag changes.

## C1 Stage Ledger From Prior Timing Runs

Added a second ledger that combines the fresh live endpoint gap budget with
existing timing-step logs. This is still not a new speed result; it tells us
where the missing `4.98 ms/token` might live and what timing is still too weak.

Artifacts:

- `scripts/qwen36-c1-stage-ledger.py`
- `data/qwen36-quark-int8-tp4-nosync-labeltiming-summary-20260612t.json`
- `data/qwen36-quark-int8-tp4-sync-modelonly-timing-summary-20260612u.json`
- `data/qwen36-quark-int8-tp4-c1-stage-ledger-20260612bn.json`
- `data/qwen36-quark-int8-tp4-c1-stage-ledger-20260612bn.md`

Findings:

- Fresh endpoint decode budget: `9.980 ms/token`; target is `5.000 ms/token`.
- Prior low-overhead/nosync pure-decode timing proxy:
  `gpu_model_runner.model_forward ~= 5.467 ms/token`.
- Prior sync model-only proxy:
  `gpu_model_runner.model_forward ~= 8.433 ms/token`.
- If the endpoint could match the nosync model-forward proxy exactly, the
  theoretical output rate would be about `182.9 tok/s`, still short of `200`.
- A no-speculative path therefore needs both:
  - outside/scheduler/stream/sync overhead close to the nosync path, and
  - at least another `0.467 ms/token` shaved from the model-forward proxy.
- The sync proxy shows why forced synchronization cannot be the profiling
  method for promotion: it can move the apparent model-forward cost by multiple
  milliseconds.

Interpretation:

- This reinforces that a oneDNN/custom MoE sidecar must be evaluated in a real
  token-step ledger, not only in isolated microseconds.
- Nested labels such as GDN, MoE, and all-reduce are directionally useful but
  not exclusive timing slices. They should not be summed into a token budget.
- The next instrumentation gate should capture model-forward, scheduler/output,
  sampler, streaming, and exclusive XPU substage timings in the same request id
  and tie that trace to quality/provenance.

## Isolated oneDNN Sidecar Probe Launcher

Added after the Python-side env hook. This is the missing reproducibility piece
for testing the rebuilt `_xpu_C` sidecar module without replacing the normal
installed/source `vllm_xpu_kernels` package and without touching the live
endpoint.

Artifacts:

- `scripts/launch-qwen36-quark-int8-sidecar-probe.sh`
- `data/qwen36-onednn-sidecar-isolated-launcher-20260612bm.json`

Launcher behavior:

- Builds a temporary overlay package under `/tmp`, containing only the rebuilt
  `build/qwen36-sidecar-probe-20260612/_xpu_C.abi3.so`.
- Uses `pkgutil.extend_path` so Python resolves the rebuilt extension first,
  while all ordinary `vllm_xpu_kernels` Python files still come from the local
  source checkout.
- Sources `/opt/intel/oneapi/setvars.sh --force` when available. This is
  required for the IntelLLVM 2026.0 sidecar build because the out-of-tree module
  depends on the oneAPI runtime path for `libsycl.so.9`.
- Defaults to port `18081`, separate cache roots, `--enforce-eager`, and graph
  capture disabled. The descriptor probe intentionally skips capture, so eager
  mode is the narrowest first live gate.
- Enables only one descriptor probe by default:
  `VLLM_XPU_MOE_ONEDNN_SIDECAR_MAX_CALLS=1`,
  `VLLM_XPU_MOE_ONEDNN_SIDECAR_RANK=0`, and
  `VLLM_XPU_MOE_ONEDNN_SIDECAR_LAYER_REGEX='layers\\.9\\.'`.
- Writes sidecar JSONL stats to
  `/tmp/qwen36-onednn-sidecar-probe-${TAG}-{pid}.jsonl`.
- Still returns the current accepted `xpu_fused_moe` output. This launcher is a
  descriptor/provenance gate, not a speed path.

Validation completed:

- `bash -n scripts/launch-qwen36-quark-int8-sidecar-probe.sh` passed.
- Script mode is executable: `775`.
- Live service on `127.0.0.1:18080` was left running.
- `xpu-smi dump` showed the current live TP4 service still owns essentially all
  VRAM: about `32651 MiB` used on each of the four B70s. The isolated backend
  run is therefore deferred until a maintenance window or explicit live-service
  stop.

Next maintenance-window gate:

1. Stop or move the live TP4 backend intentionally.
2. Launch the probe script in tmux on port `18081`.
3. Wait for `/health`, send one small deterministic completion, and inspect the
   sidecar JSONL file.
4. Confirm the probe saw `has_probe_op=true`, logged descriptor/offset stats,
   and emitted no model-output path change.
5. Restore the accepted live backend and rerun provenance/canary checks.

## Python Sidecar Probe Hook Checkpoint

Added after the compile-only oneDNN sidecar probe build. This moves the next
gate into Python without installing or promoting the sidecar module in the live
endpoint.

Artifacts:

- `patches/vllm-xpu-qwen36-onednn-sidecar-python-probe-20260612bl.diff`
- `data/qwen36-onednn-sidecar-python-probe-20260612bl.json`

Hook behavior:

- Adds a disabled-by-default call path behind
  `VLLM_XPU_MOE_ONEDNN_SIDECAR_PROBE=1`.
- Requires the rebuilt extension op
  `torch.ops._xpu_C.qwen36_moe_onednn_sidecar_probe` to exist. With the current
  installed/source extension, the env flag imports cleanly but the hook remains
  inert because `has_probe_op=false`.
- Skips during XPU stream capture, supports rank and layer regex filters, and
  limits calls with `VLLM_XPU_MOE_ONEDNN_SIDECAR_MAX_CALLS`.
- Computes oneDNN grouped-memory offsets on device from `rows_per_expert`.
  The helper emits int32 cumulative start offsets, for example
  `[2, 0, 3, 1] -> [0, 2, 2, 5]`. This follows oneDNN grouped memory's s32
  cumulative-offset buffer requirement and keeps it distinct from the local
  XE2 `expert_first_token_offset` convention.
- Always returns the current `xpu_fused_moe` output. Probe stats can be logged
  via `VLLM_XPU_MOE_ONEDNN_SIDECAR_LOG`, but they are not used for model
  output.
- Disables itself after the first probe exception in a worker.

Validation:

- `python3 -m py_compile vllm_xpu_kernels/fused_moe_interface.py` passed.
- Source-tree venv import passed both with the sidecar env disabled and
  enabled. With local shared-library paths set, `FUSEDMOE_AVAILABLE=true` and
  `has_probe_op=false`, proving the new env flag is inert until the rebuilt
  module is intentionally selected.
- A temporary package-path import with the out-of-tree
  `build/qwen36-sidecar-probe-20260612/_xpu_C.abi3.so` first failed without
  oneAPI runtime paths (`libsycl.so.9` missing), then passed after sourcing
  `/opt/intel/oneapi/setvars.sh --force`, with `has_probe_op=true`.
- Live endpoint on `http://127.0.0.1:18080` stayed healthy and continued to
  serve the current Quark W8A8 INT8 snapshot at 32K context.

Next gate:

1. Launch an isolated backend, not the live service, with oneAPI runtime paths
   and the rebuilt `_xpu_C` selected.
2. Enable `VLLM_XPU_MOE_ONEDNN_SIDECAR_PROBE=1`,
   `VLLM_XPU_MOE_ONEDNN_SIDECAR_MAX_CALLS=1`, and a single rank/layer regex.
3. Confirm descriptor stats are logged while final output still comes from the
   accepted path.
4. Only after that, extend the sidecar from descriptor-only to execute-and-
   compare for one layer.

## User-Review Follow-Up: Bigger, Bolder Ideas

Added after the "think bigger" pass. These are deliberately broader than the
next sidecar step, but still obey the same constraints: current Qwen3.6 Quark
W8A8 INT8 target, no AWQ/4-bit/Qwen3.5 substitutions, no output from an
unverified drafter, and no speed claim without exact quality gates.

Fresh leads to keep attached to the backlog:

- PyTorch's persistent cache-aware grouped-GEMM MoE work is CUDA/BF16 oriented,
  but the design pattern is relevant: persistent block scheduling and cache
  grouping for skewed expert batches rather than expert-by-expert eager loops:
  `https://pytorch.org/blog/accelerating-moes-with-a-triton-persistent-cache-aware-grouped-gemm-kernel/`.
- The public vLLM Arc Pro B writeup names the exact MoE bottleneck class we are
  seeing: launch overhead, route imbalance, and kernel bubbles. Treat its
  persistent zero-gap MoE design as a target shape for a B70/XPU W8A8 route
  replay, not as proof for our exact model:
  `https://vllm.ai/blog/2025-11-11-intel-arc-pro-b`.
- Intel Triton-XPU grouped-GEMM issue `#6389` emphasizes that realistic route
  skew, not uniform synthetic groups, must drive tile selection:
  `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`.
- Public Qwen3.6 DFlash/MTP reports point to the only plausible `2x` class of
  speedup outside kernel work, but they are proposer ideas only here. The
  current Quark W8A8 verifier must own the final token decision:
  `https://github.com/ZengboJamesWang/dgx-spark-vllm-qwen3.6-35b-a3b-dflash`.
- The Qwen3.6 vLLM recipe highlights the model's long-context posture and YaRN
  cautions. Production benchmarking should stay at the intended 32K service
  target unless the test explicitly studies longer context:
  `https://recipes.vllm.ai/Qwen/Qwen3.6-35B-A3B`.

New bolder branches to keep on the board:

1. **Decode-only c1 micro-runtime.**
   Build a separate, fixed-shape c1 runner that owns preallocated KV, fixed
   scheduler state, persistent command queues, packed weights, route buffers,
   and sampler state. vLLM remains the production server, but this runner tells
   us the ceiling after removing OpenAI-server and general scheduler overhead.
   Gate it with token-by-token parity against the live endpoint.

2. **Transactional target-state capsule.**
   Before more MTP/DFlash timing, isolate everything that changes during one
   decode step: KV pages, hybrid-attention/GDN state, scheduler counters,
   sampler RNG state, and accepted-token ledgers. Implement copy, verify,
   commit, and rollback for that capsule. This is the prerequisite for any
   target-verified speculative branch farming.

3. **Target-owned branch farm using spare VRAM.**
   Use spare cards/VRAM to evaluate multiple candidate continuations in
   parallel under the current target model, then commit only the branch that
   exactly matches target verification. This is larger than normal MTP because
   the target, not the proposer, emits the accepted stream. It only makes sense
   after the transactional-state capsule exists.

4. **Hybrid TP/EP latency topology.**
   Stop assuming TP4 is optimal for c1. Simulate and then test TP2 plus two
   replicas, TP2 plus hot-expert copies, and layer-local expert parallelism.
   The first decision metric is single-request TPOT, with aggregate throughput
   measured second.

5. **Hot-expert memory-for-latency replicas.**
   Route traces show long-tail expert use. Spend some of the apparent memory
   headroom on replicated hot experts for high-impact layers so common routes
   avoid cross-rank pressure and smaller per-expert batches. Gate by route
   replay exactness and a per-layer memory ledger.

6. **B70 W8A8 tile-layout bakeoff.**
   Treat the packed expert layout as a first-class artifact. Compare oneDNN
   `acb`, current XPU grouped-GEMM layout, and any Intel persistent-kernel
   layout on the same captured routes. Record source safetensor checksum,
   scale checksum, layout version, exactness, and latency.

7. **Whole-token Level Zero command-list replay.**
   Capture a fixed c1 token step as a command-list supernode: attention,
   router, MoE route packing, GEMM1, activation, GEMM2, gather, all-reduce, and
   sampler. Patch pointers and route offsets per token. This is high effort,
   but it directly attacks launch and CPU synchronization overhead.

8. **Router-predictive prefetch without changing math.**
   Use previous-token and previous-layer route statistics only to prefetch or
   stage likely expert tiles and scratch buffers. The router's actual top-k
   still decides the computation, so output quality is unchanged. Measure
   whether prefetch hides enough memory/layout latency to matter.

9. **Pinned CPU/PCIe/NUMA control-plane audit.**
   B70 performance may be gated by host synchronization and PCIe topology, not
   only XMX math. Add reproducible tests for CPU pinning, IRQ affinity, NUMA
   placement, PCIe link state, power limits, fan/thermal throttling, and queue
   thread placement. This is not glamorous, but it can unlock free latency.

10. **Upstream-quality B70 W8A8 challenge packet.**
    Package a minimal reproducible route-window benchmark, exact tensors,
    accepted output bytes, launch command, profiler trace, and Localmaxxing row
    so Intel/vLLM maintainers can reproduce the same target. Include a simple
    budget: which milliseconds must disappear to reach `>200 tok/s`.

11. **Engine bakeoff, but only same model and 8-bit quality posture.**
    Compare vLLM-XPU, Intel `llm-scaler`, OpenVINO/oneDNN paths, and any
    Intel-friendly 8-bit engine only if they run the current Qwen3.6 target or
    a byte-equivalent W8A8/BF16 verifier fallback. The purpose is kernel and
    scheduler learning, not switching to a lower-quality quant.

12. **Reliability scoreboard as a promotion gate.**
    For every promising speed branch, record startup success, device-lost
    frequency, 30-60 minute soak stability, peak VRAM, output parity, canaries,
    route replay exactness, and crash recovery. A fast branch that cannot soak
    is not production progress.

Highest-value ordering from this pass:

1. Keep the immediate sidecar path moving: Python env-guarded probe, correct
   `onednn_grouped_offsets`, descriptor call, then execute-and-compare.
2. In parallel, start the decode critical-path ledger so the next large branch
   targets measured wall time instead of intuition.
3. After one live parity sidecar exists, choose between persistent MoE schedule
   work and transactional target-state speculation based on the ledger.

## Post-Discussion Larger Bets Addendum

Added after the latest "what else could move the needle" pass. These ideas
remain bound by the current constraints: current Qwen3.6 Quark W8A8 INT8
target, no Qwen3.5 substitution, no AWQ/4-bit substitution, and no speed claim
without exact target-model quality gates.

New external signals folded in:

- The current Localmaxxing exact INT8/B70/vLLM rows are still around
  `99-100 tok/s`, while public Qwen3.6 rows above `200 tok/s` generally use
  MTP/speculation, NVFP4/FP4, MQ4/AWQ, or CUDA/ROCm kernels. The useful lesson
  for this project is verifier architecture, not quantization substitution:
  `https://localmaxxing.com/api/leaderboard?hfId=Qwen%2FQwen3.6-35B-A3B&limit=20`.
- vLLM's XPU hardware page validates Intel Arc Pro B-series and recommends
  nearby Qwen MoE models, but it does not make this Quark W8A8 Qwen3.6 path a
  generic upstream solved case:
  `https://docs.vllm.ai/en/stable/models/hardware_supported_models/xpu/`.
- `vllm-xpu-kernels` release notes now call out MoE grouped-GEMM policy updates
  for Xe2/Battlemage, FP8 tuning, and small-K behavior. We should diff those
  heuristics against the current local path before hand-writing another kernel:
  `https://github.com/vllm-project/vllm-xpu-kernels/releases`.
- Intel's XPU vLLM container notes claim persistent MoE GEMM plus fused
  activation reduced kernel bubbles and gave Qwen3-30B-A3B a `2.6x` end-to-end
  improvement. That is close enough to our model family to justify a direct
  transplant/reimplementation study:
  `https://github.com/intel/ai-containers/blob/main/vllm/0.10.2-xpu.md`.
- Intel's grouped-GEMM tuning issue emphasizes realistic MoE route skew:
  a few experts get many tokens while many experts get very few. This matches
  our routecapture data and reinforces real-route autotuning over uniform
  synthetic benchmarking:
  `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`.
- The Intel GPU inference paper frames oneDNN INT8 GEMM as an attainable BMG
  roofline and notes that small-matrix cases are especially sensitive to launch
  overhead. That points toward launch fusion, persistent command paths, and
  route-class scheduling rather than scale/precision shortcuts:
  `https://arxiv.org/html/2508.06753v2`.
- The public Qwen3.6 vLLM warning thread shows the model resolves through
  Qwen3.5 MoE classes and hybrid page/block constraints. This is a reminder to
  audit Gated DeltaNet / hybrid-attention state when adding speculation or
  static decode lanes:
  `https://discuss.vllm.ai/t/warning-while-serving-qwen-qwen3-6-35b-fp8/2570`.

Additional larger bets to keep visible:

1. **Port Intel's persistent MoE schedule into the Quark W8A8 path.**
   Treat the Intel container claim as a target design, not a black box:
   persistent worker, grouped GEMM, fused activation, real-route skew, and no
   kernel bubbles. First gate is a routecapture harness with exact bytes versus
   current `xpu_fused_moe`; second gate is a disabled live sidecar return path.

2. **Diff and replay upstream Xe2 grouped-GEMM heuristics.**
   Pull the latest `vllm-xpu-kernels` MoE grouped-GEMM policy changes into a
   branch and replay our captured layer-9 cases. If the policy alone improves
   the current XPU path, it is a lower-risk win than new ESIMD code. If not,
   the diff still gives tile/shape clues for the custom path.

3. **Build a B70 INT8 roofline ledger.**
   For each token stage, collect queue timestamps, XMX/DPAS counters where
   available, bytes moved, active experts, and achieved INT8 throughput versus
   oneDNN roofline. The goal is to stop optimizing by feel: every bigger patch
   should target a named gap in the ledger.

4. **Create an offline route-skew autotuner.**
   Feed thousands of real route windows into candidate schedules:
   oneDNN packed grouped GEMM, current XPU grouped GEMM, persistent MoE,
   route-class layerlets, and hot-expert replication. Export a tiny runtime
   decision table keyed by layer, active-expert count, max rows, and route
   skew. This preserves math while avoiding one-size-fits-all scheduling.

5. **Make speculation a target-verified product feature, not a benchmark hack.**
   Public `>200 tok/s` Qwen3.6 rows strongly suggest MTP/DFlash-style paths are
   the fastest route to the numeric goal. For us, a proposer can be lower
   precision or separate only if the current Quark W8A8 target verifies and
   commits every emitted token. Required work: transactional KV, transactional
   GDN/linear-attention state, accepted-token ledger, rollback tests, and
   quality parity hashes.

6. **Use spare VRAM for target-owned branch farming.**
   With four B70s, test whether spare capacity can verify multiple draft
   continuations in parallel under the current target model. This is more
   radical than normal MTP: branch candidates are discarded unless the target
   confirms them, so quality is preserved. It may only pay off after lower-TP
   or replicated-weight lanes reduce collective overhead.

7. **Re-evaluate TP topology as a latency problem, not just a capacity problem.**
   TP4 may fit comfortably but can make every token pay more collectives.
   Run TP2, asymmetric TP2+replica, and hot-expert replicated layouts with the
   current INT8 model and full 32K KV budget. If TP2 is faster for c1, use the
   remaining cards for replicas, branch farming, or aggregate lanes.

8. **Promote packed weights to a signed runtime artifact.**
   If oneDNN `acb` or a custom tile layout wins, make the transformed expert
   weights a reproducible load-time artifact with source safetensor checksum,
   scale checksum, layout version, and parity proof. This spends VRAM/disk for
   latency without changing numerical quality.

9. **Separate the c1 latency lane from the production aggregate lane.**
   A production server may want TP4, large context, and high concurrency; the
   record-chasing single-user lane may want fixed shapes, lower TP, replicated
   hot experts, and target speculation. Keep both lanes quality-gated, but do
   not force one launch configuration to solve both objectives.

10. **Send a maintainer-grade B70 W8A8 MoE packet upstream.**
    Package current exact rows, live ABI descriptors, route windows, oneDNN
    byte-exact fixtures, local patches, Localmaxxing links, and a concrete
    `>200 tok/s` budget. This is the best chance of getting Intel/vLLM eyes on
    the exact bottleneck instead of another generic "B70 is slow" issue.

## Compile-Only oneDNN Sidecar Probe Checkpoint

Added after the live ABI sidecar plan as the first guarded C++ integration
surface. This is not installed into the live endpoint and is not a speed claim.
It proves the narrow probe surface compiles and links against the current local
vLLM XPU kernel stack with oneDNN grouped matmul support.

Artifacts:

- `patches/vllm-xpu-qwen36-onednn-sidecar-probe-20260612bk.diff`
- `data/qwen36-onednn-sidecar-probe-build-20260612bk.json`
- Out-of-tree local build directory:
  `/home/steve/src/vllm-xpu-kernels/build/qwen36-sidecar-probe-20260612`

Source behavior:

- Adds `qwen36_moe_onednn_sidecar_probe(...)` in
  `csrc/xpu/onednn/qwen36_moe_sidecar.cpp`.
- Registers the op under `_xpu_C` only when explicitly called from Python.
- Validates the live ABI tensor device, dtype, contiguity, and expected shapes.
- Dry-creates oneDNN grouped-matmul primitive descriptors for GEMM1 and GEMM2
  using the live Qwen3.6 MoE shapes.
- Separates `rows_per_expert` from true grouped memory offsets. The probe only
  wraps grouped source/destination USM handles when an explicit
  `onednn_grouped_offsets` tensor is supplied; row counts alone are not used
  as offsets.

Validation:

- Configure passed with oneAPI IntelLLVM 2026.0:
  `icx`/`icpx`, `XPU_SPECIFIC_KERNELS_ENABLED=ON`, `MOE_KERNELS_ENABLED=ON`,
  and unrelated kernel families disabled for a narrower `_xpu_C` build.
- Build passed:
  `cmake --build build/qwen36-sidecar-probe-20260612 --target _xpu_C -j 8`.
- Built module:
  `build/qwen36-sidecar-probe-20260612/_xpu_C.abi3.so`, `56M`.
- Symbol check passed:
  `qwen36_moe_onednn_sidecar_probe(...)` is exported from the built module.
- Live endpoint stayed healthy on `http://127.0.0.1:18080` and continued to
  serve the current Quark INT8 model. The new module was not copied into the
  active venv or production path.

Next gate:

1. Add Python-side optional call plumbing behind a new environment variable.
2. Compute/provide `onednn_grouped_offsets` from `rows_per_expert` on XPU.
3. Call the probe for one layer/rank in metadata/descriptor mode and keep
   returning current `xpu_fused_moe` output.
4. Extend from descriptor-only to execute-and-compare for one layer, with final
   `max_abs_diff=0.0`, then broaden shape/layer coverage.

## Live ABI Sidecar Checkpoint And Bolder Queue

Added after the disabled-by-default live ABI smoke and a fresh Localmaxxing /
oneDNN / vLLM source scan.

New artifacts:

- `scripts/qwen36-live-abi-sidecar-plan.py`
- `data/qwen36-live-abi-sidecar-plan-20260612bj.json`
- `data/qwen36-live-abi-sidecar-plan-20260612bj.md`

Analyzer result:

- Loaded `48` live MoE ABI records from the TP4 smoke, `12` per rank.
- Layers covered: live layer `8` and `9` MoE calls.
- All required live tensors are present, contiguous, and have expected dtypes
  and shapes.
- Representative sidecar work:
  - GEMM1: `M=65536,K=2048,N=256`
  - GEMM2: `M=65536,K=128,N=2048`
  - Experts: `256`, top-k: `8`
  - Active experts in the first sample: `11`
  - Route offsets derived from `rows_per_expert` cover all routed rows.

Concrete next gate:

1. Add a disabled-by-default C++ sidecar entry point that accepts live
   Tensor-derived device pointers, not file exports.
2. Wrap those pointers as oneDNN/SYCL memory on the same rank-local XPU device
   and prove the path does not introduce implicit host copies.
3. Cache packed `w13`/`w2` weights and oneDNN grouped-matmul primitives by
   layer/shape; mutate `rows_per_expert` and offsets per call.
4. Execute GEMM1, activation/quant, GEMM2, and final gather with final-layer
   `max_abs_diff=0.0` versus current `xpu_fused_moe`.
5. Keep a kill switch and per-rank fallback to current `xpu_fused_moe` for any
   unsupported shape, pointer/queue mismatch, or parity failure.

Fresh external signals:

- Localmaxxing still shows the exact public Quark W8A8 INT8 row at
  `99.428 tok/s` and a same-family B70/vLLM row at `99.770 tok/s`. There is no
  public exact-model evidence that a flag-only change doubles c1 decode:
  `https://localmaxxing.com/api/leaderboard?hfId=nameistoken%2FQwen3.6-35B-A3B-Quark-W8A8-INT8&limit=20`.
- oneDNN documents grouped matmul with grouped encoding as an MoE-targeted
  example, and separately flags grouped memory / grouped GEMM as experimental
  MoE support. That supports continuing the oneDNN path, but with a hard
  in-process/cache requirement:
  `https://uxlfoundation.github.io/oneDNN/dev_guide_examples.html` and
  `https://uxlfoundation.github.io/oneDNN/dev_guide_experimental.html`.
- oneDNN matmul scale/zero-point docs confirm the sidecar must pass scale
  memory explicitly at execution time; no hidden scale computation should be
  assumed:
  `https://uxlfoundation.github.io/oneDNN/dev_guide_matmul.html`.
- oneDNN release notes call out Intel Arc / Battlemage and int8 matmul
  improvements, so testing current oneDNN builds against B70 is not just a
  portability exercise:
  `https://www.intel.com/content/www/us/en/developer/articles/release-notes/oneapi-deep-neural-network-library-release-notes.html`.
- Intel Extension for PyTorch release notes warn that INT8 dynamic-shape paths
  can be slow while dynamic-shape support is still work in progress. That
  reinforces fixed-shape buckets, c1 decode lanes, and primitive caches:
  `https://intel.github.io/intel-extension-for-pytorch/latest/tutorials/releases.html`.
- vLLM upstream carries rich W8A8 and grouped-MoE kernel source paths, but the
  visible optimized paths are CUDA/CUTLASS-oriented rather than a ready XPU
  answer for this Quark model:
  `https://github.com/vllm-project/vllm/blob/main/CMakeLists.txt`.

Bigger, bolder ideas now worth keeping on the board:

1. **Zero-copy oneDNN MoE sidecar.**
   Use live ABI pointers to make the resident oneDNN runner in-process. This is
   the closest no-quality-loss path because oneDNN already matched the current
   XPU bytes in file-backed full-layer replay.

2. **Fixed-shape c1 decode lane.**
   After the prompt is admitted, move latency-critical single-user decode into
   a shape-locked lane with fixed buffers, fixed block/table arenas, cached
   MoE primitives, and reduced scheduler metadata churn. Dynamic shape warnings
   and the route-cache hit-rate data both point here.

3. **Route-class layerlet generator.**
   Generate a small set of ESIMD/SYCL/DPAS layerlets for route classes that are
   frequent enough to matter. oneDNN remains the exact fallback and regression
   oracle. The goal is not a generic MoE kernel; it is to collapse launch and
   epilogue overhead on hot route classes.

4. **Spend spare VRAM on latency.**
   The current INT8 memory footprint leaves large headroom on 4x32GB. Use that
   budget for hot-expert replication, partial EP, duplicate packed weights, or
   one-card/two-card c1 lanes instead of only increasing concurrency.

5. **Verifier-owned speculative transaction API.**
   Stop treating speculation as an external replay problem. Let DFlash, MTP, or
   n-gram propose, but keep the Quark verifier in control of temporary KV and
   request state, then commit only accepted tokens. This preserves quality while
   attacking the only public path that can plausibly exceed `2x`.

6. **Level Zero command-list supernode.**
   Capture the one-token decode sequence as a rank-local command bundle:
   route metadata, remap/quant, grouped GEMM1, activation/quant, grouped GEMM2,
   gather, dense tail, attention, and TP collective boundaries. The target is
   the control/launch floor, not lower precision.

7. **B70 W8A8 MoE challenge packet.**
   Package route windows, exact inputs/expected bytes, live ABI descriptors, and
   oneDNN/current-XPU timings into a maintainer-friendly repro. This can attract
   Intel/vLLM attention without exposing the production endpoint and gives us a
   clean benchmark for upstreamable work.

8. **Engine bakeoff only if it stays 8-bit and exact.**
   Try LMDeploy/OpenVINO/oneDNN GenAI/SGLang only with current-model or
   equivalent W8A8/INT8 quality gates. Do not repeat the 4-bit/AWQ detour.

## Latest OneDNN W8A8 Parity Gate

The new oneDNN packet changes the near-term priority. We now have a
deterministic file-based fixture that exports real Quark W8A8 grouped-GEMM
inputs from layer-9 routecapture6 counts, runs the current XPU grouped GEMM,
runs oneDNN grouped matmul, and compares the raw bf16 output bytes.
The repository should track the exporter, runner, metadata, and JSON summaries;
raw expert-weight buffers are regenerated locally because the largest dumps are
over GitHub's normal file-size limit.

Full-layer follow-up:

- A file-backed layer-9 MoE island now proves the packed oneDNN GEMMs compose
  with the existing exact XPU remap, quantization, activation, and gather path.
  On routecapture6 rows=1, GEMM1 diff is `0.0`, GEMM2 diff is `0.0`, and final
  gathered MoE output diff is `0.0` versus current `xpu_fused_moe`. Checksums:
  reference `-751.800048828125`, oneDNN island `-751.800048828125`.
- Packed oneDNN timings inside that full-layer scaffold: GEMM1 p50
  `34.184 us`; GEMM2 p50 `24.687 us`. File-backed wall time is irrelevant to
  endpoint performance because it crosses Python, disk, and process
  boundaries.
- This narrows the next real implementation gate: keep packed weights and
  oneDNN primitives resident in-process, update route offsets/scales, execute
  GEMM1 and GEMM2 without file/process boundaries, and compare the complete
  layer against `xpu_fused_moe` before any endpoint promotion.

Result:

- GEMM1, shape `total_M=8,K=2048,N=256,E=256`, packed oneDNN `acb` weights:
  mean `35.950 us`, p50 `34.775 us`, `raw_equal=true`,
  `raw_diff_count=0`, `max_abs_diff=0.0`.
- GEMM2, shape `total_M=8,K=128,N=2048,E=256`, packed oneDNN `acb` weights:
  mean `26.078 us`, p50 `25.948 us`, `raw_equal=true`,
  `raw_diff_count=0`, `max_abs_diff=0.0`.
- Raw `abc` layout is exact too, but packed `acb` is the path to pursue:
  it matches the current XPU bytes and cuts the standalone GEMM timings.

Interpretation:

- This is not an endpoint speed result. It is a stronger gate than the earlier
  synthetic oneDNN probes because the output bytes match the current XPU
  grouped-GEMM output exactly on model-shaped tensors, weights, and scales.
- The construct cost is still around `100 ms`, so production use requires a
  route-signature primitive and memory cache. Rebuilding primitives in the
  decode loop is disqualified.
- The next implementation candidate is a full layer-9 MoE island using packed
  oneDNN GEMMs: quant/remap, GEMM1, SiLU/up-gate, quant2, GEMM2, top-k weight
  and gather. The promotion gate is full-layer `max_abs_diff=0.0` against
  current `xpu_fused_moe`, then timing with one command bundle or one host wait
  for the two GEMMs.

Immediate follow-up items:

1. **In-process layer-9 oneDNN MoE island.**
   Move the now-exact file-backed replay into an in-process C++/SYCL sidecar:
   resident packed weights, resident oneDNN primitives, direct XPU buffers,
   updated grouped offsets/scales, no file IO, and no runner process boundary.
   The gate is still final-layer `max_abs_diff=0.0` against current
   `xpu_fused_moe`.

2. **Route-signature primitive cache.**
   Cache oneDNN primitive, src/weight/dst memory descriptors, and packed
   weights by `(layer, GEMM side, active experts, rows_per_expert signature,
   dtype, layout)`. Route signatures that repeat should pay offset updates
   only, not primitive construction.

3. **Packed expert-weight load artifact.**
   Create a startup repack step that writes expert weights in the fastest
   checked oneDNN `acb` layout, with source tensor checksum and parity metadata.
   This makes packed weights an audited model-load artifact instead of a
   benchmark-side conversion.

4. **Two-GEMM command bundle.**
   Measure whether GEMM1 and GEMM2 can run through a single queue submission
   and one wait after the activation/quant boundary is included. The key metric
   is end-to-end layer time, not isolated GEMM time.

5. **OneDNN as the exact oracle for custom layerlets.**
   Use the file runner as the regression oracle while developing ESIMD/SYCL
   layerlets. If a custom kernel beats oneDNN, it still must match both the
   current XPU output and the oneDNN packet.

6. **Primitive-cache stress and reliability soak.**
   Run thousands of route signatures from prompt-class traces through the cache
   with repeated create/reuse/evict cycles. Record device-lost events, memory
   growth, and output parity before any endpoint integration.

New bigger bets from this gate:

1. **oneDNN-backed MoE sidecar inside vLLM.**
   Add a narrow sidecar for Qwen3.6 Quark W8A8 MoE layers that keeps packed
   weights and primitives resident, while vLLM still owns scheduler, KV, dense
   layers, and request handling. This is less invasive than replacing the
   engine and more realistic than waiting for a generic XPU W8A8 path.

2. **Route-class generated layerlets seeded by oneDNN parity.**
   Generate a few exact layerlet kernels for the dominant route classes found
   in live traces. oneDNN provides the verified reference and fallback; generated
   kernels compete only for route classes where they can remove host waits or
   fuse quant/activation boundaries.

3. **Resident MoE worker with oneDNN primitives as tasks.**
   Keep a device-side or long-lived host-side worker per rank that receives
   compact route descriptors and dispatches prebuilt oneDNN or custom kernels
   without per-token setup. This targets the launch/control floor directly.

4. **Hybrid oneDNN/custom pipeline.**
   Let oneDNN own the exact INT8 GEMMs while custom XPU kernels own remap,
   dynamic quant, SiLU/up-gate, and gather. This avoids reimplementing the
   hardest GEMM correctness path while still collapsing the smaller launch
   boundaries around it.

5. **Public B70 W8A8 grouped-GEMM challenge packet.**
   Publish the tiny file-based GEMM fixtures, expected bytes, route counts, and
   oneDNN/current-XPU timings as a focused challenge for Intel/vLLM. The ask is
   precise: beat the packed oneDNN and current XPU timings while preserving raw
   bf16 byte equality.

External signals folded into the backlog:

- Intel's grouped-GEMM issue says realistic route distributions matter for XPU
  MoE tuning and points at extending grouped-GEMM benchmarks with real token
  distributions:
  `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`.
- Intel's Arc Pro B-series vLLM writeup calls out the same MoE bottleneck:
  kernel launch overhead, gate dependency stalls, imbalance between groups, and
  a persistent zero-gap kernel design:
  `https://vllm.ai/blog/2025-11-11-intel-arc-pro-b`.
- The Intel Triton-XPU backend docs warn that grid dimension order can cost
  `20%` to `2x`, and explicitly call out MoE kernels where token/tile should
  stay on `axis=0` and expert on a higher axis:
  `https://github.com/intel/intel-xpu-backend-for-triton`.
- The PyTorch persistent grouped-GEMM writeup reinforces the same direction:
  grouped GEMM cuts launch overhead and persistent scheduling improves
  utilization for MoE workloads:
  `https://pytorch.org/blog/accelerating-moes-with-a-triton-persistent-cache-aware-grouped-gemm-kernel/`.
- vLLM's MoE kernel design treats all-to-all backend, activation format,
  quantization format, and async support as first-class tuning axes:
  `https://docs.vllm.ai/en/latest/design/moe_kernel_features/`.
- vLLM's public W8A8 INT8 docs still describe the official INT8 compute path
  as NVIDIA-only. The XPU/Quark route must therefore be treated as a
  vendor/local stack with its own correctness and performance proof, not as a
  generic upstream W8A8 path:
  `https://docs.vllm.ai/en/v0.18.0/features/quantization/int8/`.
- The open llm-compressor Qwen3.6 W8A8 issue confirms the model-specific
  quantization details are not trivial: Qwen3.6 uses Qwen3.5 MoE classes,
  fused expert tensors, Gated DeltaNet/linear attention, and needs W8A8
  coverage beyond ordinary dense attention layers:
  `https://github.com/vllm-project/llm-compressor/issues/2787`.
- Public B70 TP fault reports point at host-stack, firmware, PCIe topology,
  and vLLM ProcessGroupXCCL interactions as reliability/perf variables. This
  justifies a controlled host-BOM A/B lane before production hardening:
  `https://github.com/vllm-project/vllm/issues/41663`.
- Public B70 aggregate examples show large multi-request throughput can scale
  even while c1 latency remains around the same band. Treat aggregate B70 rows
  as production-capacity clues, not proof that c1 should automatically double:
  `https://forum.level1techs.com/t/intel-b70-launch-unboxed-and-tested/247873`.
- Public dual-B70 llama.cpp notes are another warning that naive multi-GPU
  layer splitting can fit larger models without improving one-request latency.
  Any multi-GPU speed claim needs true concurrent layer parallelism or a
  measured TP/EP benefit:
  `https://github.com/PMZFX/intel-arc-pro-b70-benchmarks/blob/master/multi-gpu.md`.
- Localmaxxing currently shows one approved public row for this exact INT8
  model/B70/vLLM setup, the existing `99.428 tok/s` c1 baseline:
  `https://localmaxxing.com/api/leaderboard?hfId=nameistoken%2FQwen3.6-35B-A3B-Quark-W8A8-INT8&hardwareName=Arc%20Pro%20B70&engineName=vllm&limit=10`.

Fresh post-parity scan:

- oneDNN's release notes and matmul docs explicitly describe grouped memory and
  grouped matmul as experimental MoE support, enabled with
  `ONEDNN_EXPERIMENTAL_GROUPED_MEMORY=ON`, with optimized Intel GPU
  implementation. This supports keeping the packed oneDNN path as a serious
  exactness-preserving candidate rather than a generic library detour:
  `https://github.com/uxlfoundation/oneDNN/releases`,
  `https://uxlfoundation.github.io/oneDNN/dev_guide_matmul.html`, and
  `https://uxlfoundation.github.io/oneDNN/dev_guide_experimental.html`.
- SonicMoE's IO/tile-aware framing is useful even if its implementation is not
  directly portable: grouped GEMM wins can come from tile sizing, prologue and
  epilogue IO, padding, and keeping per-expert work aligned with hardware
  matrix units. Add an explicit epilogue/IO audit to the custom layerlet plan:
  `https://arxiv.org/html/2512.14080v2`.
- AMD's vLLM MoE playbook is vendor-specific but the systems tradeoff applies:
  EP can trade all-to-all communication for more aggregate expert-weight memory
  bandwidth. For B70, this means TP4 should not be assumed best for c1 latency;
  route-driven TP2/EP/hot-replication simulations remain worth doing:
  `https://rocm.blogs.amd.com/software-tools-optimization/vllm-moe-guide/README.html`.
- Recent public B70 field reports still point at host-stack and runtime
  instability variance across Ubuntu/kernel/driver/container combinations.
  Treat the clean Intel container/BOM lane as production reliability work and
  as a possible performance unlock, but keep it separate from model-quality
  changes:
  `https://www.reddit.com/r/LocalLLaMA/comments/1siar7y/intel_arc_pro_b70_32gb_performance_on_qwen3527bq4/`,
  `https://forum.level1techs.com/t/intel-b70-launch-unboxed-and-tested/247873`.

## Immediate Things To Try

1. **Measure the exact scratch hook before another endpoint promotion.**
   The local microbench already shows a manual preallocated Quark W8A8 MoE path
   can match `xpu_fused_moe` exactly while cutting a routecapture6 layer sample
   from roughly `270 us` to roughly `206 us`. The existing endpoint screens
   already rejected shared mixed workspace and archived a per-layer scratch
   patch, so the next step is narrower: time the actual
   `xpu_fused_moe(..., scratch=...)` hook in the route-replay microbench and
   compare it against the manual staged path. Promote no source patch unless
   this hook proves a real wrapper-level win that the old endpoint result did
   not capture.

2. **Build a real-route persistent-MoE layerlet.**
   Reconstruct one Qwen3.6 MoE layer outside the server using captured
   `topk_ids`, Quark W8A8 scales, exact weights, grouped GEMM, SiLU/up-gate,
   down projection, top-k weighting, and gather. The test should compare:
   current `xpu_fused_moe`, preallocated staged path, SYCL-TLA grouped GEMM,
   Triton-XPU grouped GEMM with correct grid axis ordering, and any Intel
   persistent-kernel branch available locally.

3. **Make route-window tuning the kernel fixture, not a side report.**
   Routecapture artifacts should drive every MoE kernel screen. Synthetic uniform
   routing is useful only for basic correctness. Performance claims should use
   real layers such as `9`, `14`, `20`, and `21`, with prompt-class windows and
   active-expert histograms recorded next to timing.

4. **Measure the full token latency budget after recovery.**
   Before writing another large kernel, collect a low-overhead per-token
   breakdown: MoE total, grouped GEMM, quant/remap/gather, attention, TP
   collective, scheduler metadata copies, sampling, and OpenAI/frontdoor
   overhead. The offline endpoint parity already rules out frontdoor overhead;
   now the goal is to rank the remaining in-engine milliseconds.

5. **Try block-size and scheduler metadata changes in an isolated lane.**
   Block size `64` keeps showing up in public B70 aggregate recipes. Test it as
   a c1 metadata and graph-stability lever, not as a memory-headroom lever.
   Capture `block_table`, `num_computed_tokens`, `seq_lens`, host copies, and
   device-lost behavior.

6. **Run a strict 8-bit engine bakeoff.**
   Compare only high-fidelity 8-bit or BF16-compatible routes: current vLLM
   Quark W8A8, newer Intel vLLM/vllm-xpu-kernels stacks, OpenVINO/oneDNN GenAI
   only if Qwen3.6 A3B/GDN/MoE support is real, and any Q8/SYCL route that
   preserves target output. Exclude 4-bit, AWQ, Qwen3.5, and any route that
   changes the target model.

7. **Submit only material public rows.**
   The `99.728 tok/s` local sanity run is slightly above the current public
   `99.428 tok/s` row but not a new class of result. Post it only if we want an
   exact refreshed recovery datapoint; otherwise wait for a result that clears a
   meaningful threshold such as `105`, `120`, or `200 tok/s`.

8. **Add a host-stack A/B lane, but keep it separate from model tuning.**
   Reproduce the accepted command on the closest Intel-validated B70/XPU stack
   available, then compare against the current Ubuntu 24.04.4/HWE host:
   kernel/KMD, GuC firmware, compute-runtime, oneAPI, oneCCL, PyTorch, vLLM,
   and `vllm-xpu-kernels`. This is a reliability and collective-performance
   test, not permission to change the model.

9. **Build a CCL/topology matrix for c1 latency.**
   Keep the accepted model and graph cache fixed while sweeping only
   `CCL_*`, `FI_*`, affinity, worker placement, and TP shape. Record per-token
   all-reduce time and device reset risk. If TP4 communication is a measurable
   wall, the next engine bet should be TP/EP or static-lane routing, not more
   launch flags.

10. **Instrument command-stream overhead per token.**
    Capture the Level Zero/SYCL command timeline for one accepted decode token:
    kernel count, barriers, host waits, memory copies, and collective launches.
    The B70 persistent-kernel literature says host waiting and kernel launch
    gaps are central MoE losses; our routecapture fixtures need to prove how
    much of the `~10 ms/token` is launch/control overhead.

## Bigger, Bolder Ideas

1. **Persistent B70 MoE kernel for Qwen3.6 A3B decode.**
   Treat this as the main non-speculative `2x` bet. The current decode shape is
   launch- and imbalance-heavy: route packing, quant, grouped GEMM, activation,
   second grouped GEMM, and gather are separate enough that each step pays
   overhead. A B70-native persistent kernel should keep workers resident, pull
   dynamic expert tasks from a queue, preserve exact Quark W8A8 math, and emit
   the same output as `xpu_fused_moe`.

2. **Transactional resident-state verifier for exact speculation.**
   Build a verifier that forks live request state in-engine: immutable KV pages
   are aliased, mutable GDN/Mamba/request metadata is copied or versioned,
   candidate tokens are scored by the current Quark W8A8 model, then the
   transaction either commits or rolls back. This is the safest path to
   `>200 tok/s` because it allows MTP, DFlash, n-gram, or target-trace
   proposers without trusting their quality.

3. **Static one-request latency appliance.**
   vLLM is built for dynamic serving. For the c1 target, prototype a fixed-shape
   one-request engine lane with resident metadata, fixed decode buckets,
   no dynamic scheduler churn, preallocated KV/GDN state, fixed sampling, and
   cached graph provenance. It can live beside the production vLLM service as a
   latency-specialized lane.

4. **Hybrid TP/EP route simulation before implementation.**
   Simulate exact expert ownership from captured routes: TP4, TP2 plus
   replicated attention, EP4, hot-expert replication, and cold-expert sharding.
   Compare activation all-to-all bytes against TP allreduce bytes and include
   32K KV headroom. Implement only if the model predicts a real c1 win.

5. **Tile-native W8A8 repack cache with checksums.**
   At load time, repack expert weights into the layout consumed by the fastest
   XPU grouped-GEMM/persistent kernel. Keep a manifest with source tensor hash,
   permutation, tile format, and output equivalence checks. If this works, it
   becomes an engine-neutral asset usable by vLLM, a custom layerlet, or a
   future SYCL route.

6. **GPU-resident metadata update kernel.**
   The device-lost traces point at metadata-copy paths such as block tables and
   computed-token counters. A tiny resident kernel or graph-safe metadata
   update path could reduce per-token CPU/device synchronization and improve
   stability at the same time.

7. **B70 graph artifact certification.**
   Treat graph cache artifacts as quality-critical binaries. Store cache root,
   generated graph hashes, sentinel tokens, launch command, driver/runtime
   versions, and first-token branch proof. Production starts only from a
   certified cache root; benchmarks from uncertified cache roots are diagnostics.

8. **Target-trace-trained proposer, verified by target.**
   Record accepted target continuations and train or tune a small proposer on
   this exact model's token traces. The proposer is never trusted directly; it
   only feeds the resident-state verifier. This could outperform generic
   n-gram speculation while preserving exact target output.

9. **Production dual-lane architecture.**
   Keep TP4/32K for capacity and long prompts, but also evaluate single-card,
   two-card, or static-lane replicas for low-latency c1 traffic. Public B70
   reports suggest extra cards help aggregate throughput more reliably than
   single-request latency, so production may need routing instead of one
   universal backend.

10. **Upstreamable Qwen3.6 XPU perf packet.**
    Package route windows, exact expected token outputs, grouped-GEMM fixtures,
    launch commands, and failure artifacts into a small public repro for Intel
    and vLLM. The useful upstream artifact is not "Qwen3.6 is slow"; it is a
    route-exact MoE/kernel suite that makes B70 bottlenecks reproducible.

11. **Exact DPAS/XMX utilization audit.**
    Prove whether the hot W8A8 MoE and dense paths are actually issuing the
    intended Intel XMX/DPAS INT8 operations at high occupancy. If they are not,
    the biggest win may be a lower-level kernel/layout issue rather than vLLM
    scheduler tuning. The output should be a table per kernel: shape, layout,
    DPAS/XMX use, occupancy, bandwidth, and launch count.

12. **Quant-output out-variant and fusion campaign.**
    The current scratch hook reuses remap/GEMM/activation buffers, but dynamic
    activation quant still returns fresh tensors. Add an exact out-variant for
    per-token INT8 quantization, then evaluate fusing remap+quant1 and
    activation+quant2. The previously rejected fused SiLU+quant candidate failed
    arithmetic quality, so this must be rebuilt with strict equivalence tests
    before any endpoint run.

13. **Per-layer hot-expert duplicate-and-route experiment.**
    Use routecapture histograms to identify layers where a few experts dominate
    c1 decode. If VRAM allows, duplicate only those hot expert shards or their
    tile-native packed forms across ranks to reduce traffic or imbalance while
    preserving exact weights. Simulate first; implement only if the bytes and
    route windows predict a real latency win.

14. **Minimal exact decode engine outside vLLM.**
    Build a tiny single-request executable for one fixed prompt/output bucket
    that loads the same Quark W8A8 weights, runs the same tokenizer/model math,
    and bypasses vLLM scheduling entirely. This is not a replacement server; it
    is a truth-serum benchmark that tells us whether vLLM control flow is the
    c1 bottleneck or the kernels are.

15. **Two-lane production architecture with exact routing.**
    Keep the stable TP4/32K vLLM service as the general lane, but create a
    latency lane for common c1 chat shapes: fixed buckets, fixed sampling,
    certified graph cache, preallocated state, and stricter admission control.
    Route requests by context/output shape. This can improve user-perceived
    speed without weakening model quality or long-context capacity.

16. **Speculative proposer bakeoff with target-verified rollback.**
    Expand beyond n-gram by testing MTP, target-trace proposer, simple prefix
    trie, and small exact-model-trained proposer, all behind the same
    resident-state verifier. The only promoted metric is accepted target tokens
    per second with exact sentinel parity; raw draft speed does not count.

17. **Upstream branch archaeology and kernel transplant lane.**
    Track Intel `llm-scaler-vllm`, `vllm-xpu-kernels`, Triton-XPU, and oneDNN
    GenAI branches for B70/MoE/W8A8 changes. When a promising kernel appears,
    extract just the route-replay fixture and compare it against our accepted
    artifacts before considering a stack upgrade.

## Promotion Rules

- A speed candidate must pass the accepted provenance guard and the exact
  sentinel positions before it is compared to the public baseline.
- A kernel candidate must prove numeric equivalence against the current
  `xpu_fused_moe` or full endpoint output on captured real routes.
- A speculation candidate must use the current Quark W8A8 model as verifier and
  produce a transaction log with accept/reject/rollback evidence.
- A public benchmark should include command, context length, output length,
  TTFT, c1 decode speed, cache-root provenance, and exact quality artifact.

## 2026-06-12 Big-Bet Refresh

This section folds in the latest roofline packet, active-offset rejection, and
fresh external/API scan. It is notes-only; no endpoint change or new speed
claim is implied.

Current hard facts:

- Exact-model public baseline remains the quality-cleared `~99-100 tok/s` c1
  tier. The exact Localmaxxing filter still returns
  `cmq8yhxvo001ipb0149aoa79o` at `99.428 tok/s`; the broader B70/Qwen/vLLM
  family query also shows `cmq9ifq0500b0r8012f27j1xl` at `99.770 tok/s`,
  mapped to the base `Qwen/Qwen3.6-35B-A3B` row.
- Fresh live p512/o512 local-bypass timing measured `99.618 tok/s` corrected
  after first chunk with a `10.039 ms/token` decode histogram.
- The current route-exact MoE layer replay is `294.145 us/layer`; the
  preallocated staged lower bound is `220.530 us/layer`; the two-dispatch GEMM
  floor is `193.538 us`; the non-speculative `200 tok/s` target needs about
  `168.173 us/layer`.
- Active-offset grouped GEMM was exact but rejected for speed:
  `225.911 us/layer`, slightly slower than the plain offset path.
- External XPU signals match our measurements: Intel's grouped-GEMM issue says
  route skew and tile configuration are first-order MoE performance variables,
  the vLLM XPU migration is still moving kernel work into
  `vllm-xpu-kernels`, and upstream W8A8 support for Qwen3.6 remains
  model-specific rather than a solved generic path.

### Things To Try Next

1. **Fixed layer-9 persistent layerlet scaffold.**
   Build the smallest route-exact C++/SYCL op that accepts captured
   routecapture6 metadata and produces the exact current `xpu_fused_moe`
   output for layer 9. The first version may call existing launchers
   sequentially; that validates ABI, workspace ownership, and parity. The
   second version must remove at least one dispatch boundary. Kill gate:
   no path to `<=168 us/layer` by the time the first true fused variant runs.

2. **Quant out-variants as layerlet plumbing, not as a standalone bet.**
   Add exact preallocated-output variants for `per_token_quant_int8_xpu` and
   `silu_and_mul_quant_int8_xpu`. Use them to reduce allocator churn and to
   feed the layerlet. Do not promote them alone unless an endpoint run proves a
   real decode win and full parity.

3. **DPAS/XMX proof before more kernel archaeology.**
   Install or locate a working oneAPI/Level-Zero profiling path
   (`unitrace`, VTune, or equivalent) and capture one decode token plus the
   route-replay grouped-GEMM kernels. We need to know whether the W8A8 hot path
   is issuing high-occupancy DPAS/XMX INT8 work or whether layout/upconvert/
   launch overhead is dominating.

4. **Clean Intel container A/B.**
   Run the accepted command, same model, same prompt suite, and same p512/o512
   metric inside the newest Intel XPU/vLLM container that supports B70. Treat
   this as a host-stack A/B, not a model change. Required artifacts:
   version matrix, exact quality canary, speed metric, and device-lost scan.

5. **TP2/EP truth-serum lane.**
   Run a narrow latency test with TP2 or a simulated TP2+hot-expert plan, even
   if it reduces 32K capacity. The question is whether TP4 communication and
   small shards are hurting c1 more than they help. If TP2 is faster at smaller
   context, production can route latency-sensitive small-context traffic to a
   separate lane.

6. **Graph-safe metadata arena.**
   The repeated `block_table.copy_to_gpu` device-lost traces justify a fixed
   metadata arena experiment: precommit block-table/KV/GDN request state for a
   solo decode lane and update it with device-side or graph-safe kernels. This
   is both a stability bet and a possible latency win.

7. **Route-class autotune table.**
   For layers 9, 14, 20, and 21, generate route-class fixtures from natural,
   code, structured, math, and repetitive prompts. Autotune grouped-GEMM policy
   per fixture (`m16`, `m32`, base, offset, active-set, Triton-XPU if usable)
   and store a per-layer decision table. If no policy crosses the budget, stop
   spending time on ordinary grouped-GEMM variants.

8. **Resident verifier-state prototype.**
   Build the data model for speculative transactions before another speculative
   speed run: immutable KV aliasing, mutable GDN/request metadata copy,
   candidate scoring, accept/rollback log, and exact sentinel replay. Raw draft
   acceptance does not matter until this is exact.

9. **Localmaxxing race harness without auto-posting.**
   Keep querying public rows for exact model, base model, and B70/Qwen/vLLM
   family context. Generate dry-run payloads from local results, but only post
   results that are material and quality-cleared. Use an environment variable
   for API auth; never store the key in the repo.

10. **Upstream repro packet.**
    Package routecapture6 layer 9, the active-offset negative, the roofline
    budget, exact expected outputs, and a minimal grouped-GEMM fixture. This is
    the packet to hand to Intel/vLLM maintainers if we need help with the B70
    W8A8 MoE floor.

### Bigger And Bolder Ideas

1. **B70-resident MoE device service.**
   Instead of launching route/remap/quant/GEMM/activation/quant/GEMM/gather as
   separate operations, run a persistent device service per layer or layer
   group. Host code submits compact route/task descriptors; resident workers
   pull expert tiles, run exact W8A8 math, and write the final gathered output.
   This is the most plausible non-speculative `2x` route because the
   one-dispatch floor is the only local budget scenario that clearly exceeds
   `200 tok/s`.

2. **Layerlet code generator.**
   Generate specialized SYCL/ESIMD layerlets from captured real route classes:
   fixed hidden size, fixed expert topk, fixed Quark scale layout, fixed
   activation, and optional hot-expert duplication. The generator emits a
   small number of route-class kernels rather than one generic MoE kernel.
   Quality is protected by route-replay exactness before any endpoint use.

3. **Target-model branch lookahead.**
   For greedy/temperature-zero traffic, use spare XPU capacity to compute a
   small exact target-model branch tree ahead of the committed token. Only the
   target model chooses the branch; no lower-quality model is trusted. This is
   expensive, but if current decode underutilizes XMX, exact branch lookahead
   could trade parallel compute for lower visible latency.

4. **Trace-trained micro-proposer plus transactional verifier.**
   Train or tune a tiny same-tokenizer proposer on continuations emitted by this
   exact Quark model. It can be lower quality because it is never authoritative;
   the resident verifier commits only matching target tokens. This is a
   quality-preserving alternative to generic n-gram when n-gram acceptance is
   too prompt-dependent.

5. **Static c1 appliance beside vLLM.**
   Build a separate low-latency lane for common chat shapes: one active
   request, fixed prompt/output buckets, fixed sampling, preallocated KV/GDN
   state, certified graph cache, and strict admission. Keep vLLM TP4/32K as the
   general production lane. This accepts that dynamic serving and c1 latency
   may need different engines.

6. **Hot-expert memory-for-latency service class.**
   If VRAM headroom permits, duplicate only route-dominant expert tiles or
   packed hot experts across ranks. The route simulation says hot64 replication
   can cut the communication-row proxy to `0.155` at `1.75x` expert-memory
   cost. That is too large for blind implementation, but it is worth a
   controlled c1 lane if profiler data shows remote expert movement or load
   imbalance is material.

7. **One-card and two-card latency replicas.**
   The full quantized model is near the memory boundary, but smaller-context
   or reduced-capacity lanes may fit on fewer cards with less TP overhead. Test
   model fit and latency honestly. A slower aggregate lane can still be better
   for one user's perceived speed if TP4 communication dominates.

8. **IR-level whole-token command graph.**
   Capture the entire decode token, including metadata updates, collectives,
   MoE, attention, and sampling, as a static Level-Zero/SYCL command graph.
   This is more invasive than piecewise graph capture but directly targets
   launch gaps and host waits.

9. **Kernel challenge/bounty packet.**
   Publish a small reproducible performance challenge: exact route windows,
   W8A8 tensor shapes, expected outputs, and current timings. A focused public
   repro may attract Intel/vLLM help faster than a broad "make Qwen faster"
   issue.

10. **Production reliability score as a first-class metric.**
    Track every candidate with speed, exactness, device-lost count, restart
    time, graph-cache identity, and 30-60 minute c1 soak result. A `130 tok/s`
    route that survives production may be more valuable than a `180 tok/s`
    route that loses devices under real traffic.

## 2026-06-12 Follow-up

- Added the route-replay diagnostic fields for the real
  `xpu_fused_moe(..., scratch=...)` hook to
  `scripts/bench-qwen36-int8-moe-kernels.py`.
- Validation run:
  `/home/steve/.venvs/vllm-xpu/bin/python -m py_compile scripts/bench-qwen36-int8-moe-kernels.py`
  passed.
- Import/CLI validation:
  `/home/steve/.venvs/vllm-xpu/bin/python scripts/bench-qwen36-int8-moe-kernels.py --help`
  passed.
- The live accepted TP4 backend was left running. A one-shot `xpu-smi` memory
  check showed roughly `32651 MiB` used on each B70, so the route-replay XPU
  microbench should wait for a clean benchmark window.

## 2026-06-12 Live Decode Budget

Artifact:
`data/qwen36-quark-int8-tp4-live-c1-p512o512-metrics-hist-20260612q.json`.

Command shape:

```bash
/home/steve/.venvs/vllm-xpu/bin/python scripts/measure-openai-endpoint-metrics.py \
  --base-url http://127.0.0.1:18080 \
  --tokenizer /mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118 \
  --prompt-tokens 512 --output-tokens 512 \
  --prompt-kind vllm-random --seed 20260612 \
  --repeats 3 --warmup-output-tokens 32 \
  --endpoint completions --mode stream --ignore-eos --skip-vram
```

Observed direct-backend c1 p512/o512 budget:

- Corrected output throughput after first text chunk: `99.875 tok/s` mean.
- End-to-end output throughput: `98.613 tok/s` mean.
- vLLM TTFT: `74.163 ms` mean.
- vLLM prefill histogram: `69.128 ms` mean.
- vLLM decode histogram: `5116.930 ms` mean for 512 generated tokens.
- vLLM decode per generated token: `9.994 ms/token` mean.
- vLLM inter-token histogram: `10.014 ms/token` mean.
- vLLM queue time: `0.0069 ms` mean.
- vLLM iteration-tokens histogram: `2.0` tokens/step as reported.

Implication:

- The `>200 tok/s` target requires roughly `<=5 ms/token` decode. Queue,
  frontdoor, and normal prefill are too small to be the decisive bottleneck for
  this c1 shape. The next speed work must cut the steady decode path itself:
  MoE/linear-attention kernels, collectives, graph fences, scheduler metadata,
  or exact target-verified speculation.

Safer next controlled timing profile recipe:

```bash
tmux new -s qwen36-tp4-decode-timing-$(date +%Y%m%d%H%M%S) -- \
  env \
    VLLM_XPU_DECODE_TIMING_ALLOW=1 \
    VLLM_XPU_DECODE_TIMING=1 \
    VLLM_XPU_DECODE_TIMING_SYNC=0 \
    VLLM_XPU_DECODE_TIMING_RANK=0 \
    VLLM_XPU_DECODE_TIMING_LABEL_REGEX='^(xpu_moe[.]|moe_forward_shared[.]custom_op|all_reduce:|gpu_model_runner[.]model_forward|gdn_attention_core_xpu[.]native|logits[.])' \
    VLLM_XPU_DECODE_TIMING_STEP_SUMMARY=1 \
    VLLM_XPU_DECODE_TIMING_STEP_EVERY=32 \
    VLLM_XPU_DECODE_TIMING_STEP_SKIP_FIRST=64 \
    LOG_PATH=/tmp/qwen36-tp4-decode-timing.log \
    scripts/launch-qwen36-quark-int8-accepted.sh

/home/steve/.venvs/vllm-xpu/bin/python scripts/measure-openai-endpoint-metrics.py \
  --base-url http://127.0.0.1:18080 \
  --tokenizer /mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118 \
  --prompt-tokens 512 --output-tokens 512 \
  --prompt-kind vllm-random --seed 20260612 \
  --repeats 2 --warmup-output-tokens 32 \
  --endpoint completions --mode stream --ignore-eos --skip-vram \
  --out data/qwen36-quark-int8-tp4-decode-timing-profile-metrics.json

/home/steve/.venvs/vllm-xpu/bin/python scripts/summarize-xpu-decode-timing-log.py \
  --log /tmp/qwen36-tp4-decode-timing.log \
  --out data/qwen36-quark-int8-tp4-decode-timing-profile-summary.json \
  --all-lines
```

This no-sync version is the default next run. If a synchronized profile is
needed, add a label/category filter first and synchronize only a narrow MoE or
allreduce subset in a clean benchmark window, not against the live accepted
service.

## 2026-06-12 Sync Timing Result And Added Bets

Artifacts:

- Timing log:
  `data/qwen36-quark-int8-tp4-decode-timing-sync-devicelost-20260612r.log`.
- Parsed timing summary:
  `data/qwen36-quark-int8-tp4-decode-timing-sync-devicelost-summary-20260612r.json`.
- Restored accepted-backend log:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-timing-devicelost-20260612s.log`.
- Restored provenance guard:
  `data/qwen36-quark-int8-tp4-accepted-provenance-guard-after-timing-devicelost-20260612s.json`.
- Restored p512/o128 speed sanity:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-timing-devicelost-speed-p512o128-20260612s.json`.

Result:

- The synchronized timing backend crashed during warmup/main measurement with
  Level Zero `UR_RESULT_ERROR_DEVICE_LOST`, first in
  `block_table.copy_to_gpu(num_reqs)`, then with
  `UR_RESULT_ERROR_OUT_OF_RESOURCES` at `num_accepted_tokens.gpu.fill_(1)`.
- The timing hook still emitted a useful partial rank0 summary before shutdown.
  Treat absolute timings as distorted by explicit synchronization, but use the
  ranking as a directional decode-attribution signal.
- Top timing buckets:
  - `moe_forward_shared.custom_op`: `1248` calls, `4837.535 ms` total,
    `3.876 ms` average.
  - `xpu_moe.gemm2_w8a8`: `1248` calls, `1672.690 ms` total,
    `1.340 ms` average.
  - `xpu_moe.gemm1_w8a8`: `1248` calls, `1476.398 ms` total,
    `1.183 ms` average.
  - Largest dense allreduce bucket:
    `all_reduce:(8192, 2048):torch.bfloat16`, `49` calls,
    `122.319 ms` total, `2.496 ms` average.
- Directional takeaway: the W8A8 MoE custom-op and GEMM path dominates this
  profile. Allreduce still matters, but it is secondary in this partial timing
  capture. Queue, frontdoor, and normal prefill were already ruled out by the
  live histogram run.
- The normal accepted backend was restored afterward. Provenance guard passed
  the exact sentinel positions and the restored p512/o128 sanity run measured
  `100.234 tok/s` corrected after first text chunk, `95.391 tok/s` e2e output,
  and `9.901 ms/token` decode histogram. The quality/speed baseline is intact.

Immediate follow-ups:

1. **Replace global sync timing with safer selective profiling.**
   Do not run broad `VLLM_XPU_DECODE_TIMING_SYNC=1` as a default diagnostic
   again. Add a label-regex or category filter so only `xpu_moe.*` and selected
   allreduce labels synchronize, and start with no-sync counters plus periodic
   summaries before enabling any synchronized timing.

2. **Make metadata-copy stability part of every timing run.**
   The crash site was in scheduler/model-runner metadata movement, not inside
   the MoE timing bucket itself. Any future timing branch should record block
   table shape, `num_reqs`, `num_computed_tokens`, candidate-count buffers, and
   whether a host/device copy or fill was the first failing operation.

3. **Move the next speed bet down into W8A8 MoE, not launch flags.**
   The profile points at `gemm1_w8a8`, `gemm2_w8a8`, quant/remap/gather, and
   custom-op wrapper overhead. The next productive branch is a route-exact
   MoE layerlet or lower-level kernel change, not another service flag sweep.

4. **Keep a fast restore loop around risky profiling.**
   Before any synchronized timing, collect current tmux name, launch log,
   graph-cache fragment, and XPU process state. After any device-lost event,
   restore the accepted backend, run provenance guard, then run a short
   p512/o128 speed sanity before continuing.

Additional bigger, bolder ideas:

1. **Selective event-timing ring buffer inside hot kernels.**
   Instead of synchronizing Python labels, add a tiny device-side or low-level
   event recorder around the W8A8 MoE substeps. Dump one compact timeline per
   token after the run. This should reduce timing-induced device loss while
   still exposing launch gaps and kernel overlap.

2. **MoE flight recorder for one decode token.**
   For a single accepted token, capture route IDs, active experts, expert token
   counts, packed shapes, GEMM tile shapes, DPAS/XMX counters, command count,
   and gather/quant buffers. The goal is one file that explains why the token
   costs about `10 ms`, not only which high-level label is slow.

3. **Persistent expert-worker prototype with exact Quark math.**
   Build a small SYCL or Triton-XPU kernel that keeps expert workers resident
   across the two MoE GEMMs and dynamic quant steps for one layer. It must match
   `xpu_fused_moe` on captured routes before endpoint testing. If it cannot
   beat the current route replay fixture by a large margin, it will not close
   the `>200 tok/s` gap.

4. **Expert-parallel shadow simulator using real route windows.**
   Simulate EP4, TP2+EP2, hot-expert replication, and replicated-attention plus
   sharded-expert layouts from routecapture artifacts. Compute bytes moved,
   expected all-to-all/allreduce operations, per-rank hot spots, and VRAM. This
   is the cheapest way to decide if a more radical parallelism change is worth
   implementing.

5. **Graph-safe GPU-resident scheduler metadata.**
   Prototype moving block-table tails, accepted-token counters, and other tiny
   per-step metadata updates onto the device or into graph-stable buffers. This
   targets both latency and the recurring device-lost class around metadata
   copies/fills.

6. **Offline kernel replay binary.**
   Generate a standalone replay executable from captured one-token inputs:
   attention input, MoE routes, expert weights/scales, and collectives mocked or
   isolated. This separates vLLM scheduler noise from kernel reality and makes
   upstream Intel/vLLM conversations much sharper.

7. **Layer-specific tile-native W8A8 repack plus autotune cache.**
   Repack expert tensors into the exact layout needed by the fastest B70 kernel
   per layer, record checksums, and autotune only from real route windows. A
   layer-specific cache is more work than a global layout, but the route scans
   already showed global hot-expert assumptions are unreliable.

8. **Certified static c1 lane as a production sidecar.**
   Keep general vLLM for capacity and long contexts, but prototype a fixed
   p512/p2k decode sidecar with preallocated metadata, certified graph cache,
   fixed sampling, and strict admission control. This is a pragmatic way to get
   user-facing latency down while the general server remains reliable.

9. **Quality-first BF16 differential harness.**
   Continue using Quark W8A8 as the production target, but keep a BF16 fallback
   harness for periodic semantic/logit-rank checks on a small suite. This is
   not a speed candidate; it is an early warning system for kernel changes that
   pass token sentinels but distort nearby probabilities.

10. **Hardware/driver stress lane for profile safety.**
    The timing crash reinforces that B70 performance work needs a separate
    reliability lane. Sweep only host stack, firmware, oneCCL, and runtime
    versions with the accepted command and a fixed quality/speed smoke. Promote
    no kernel change from a stack that increases device-lost rate.

## 2026-06-12 Selective Timing Controls And Safer Profiles

Patch:

- `patches/vllm-qwen36-selective-xpu-decode-timing-20260612.patch`.
- Live source updated:
  `/home/steve/src/vllm/vllm/utils/xpu_decode_timing.py`.
- Accepted launch guard updated:
  `scripts/launch-qwen36-quark-int8-accepted.sh`.

New profiling environment controls:

- `VLLM_XPU_DECODE_TIMING_LABEL_REGEX`: record only labels matching this regex.
- `VLLM_XPU_DECODE_TIMING_EXCLUDE_LABEL_REGEX`: drop labels matching this regex.
- `VLLM_XPU_DECODE_TIMING_SYNC_LABEL_REGEX`: when sync timing is enabled,
  synchronize only matching labels.
- `VLLM_XPU_DECODE_TIMING_SYNC_EXCLUDE_LABEL_REGEX`: exclude matching labels
  from sync timing.
- The accepted launch script strips all four unless
  `VLLM_XPU_DECODE_TIMING_ALLOW=1`, so normal service stays timing-free.

Validation:

- `bash -n scripts/launch-qwen36-quark-int8-accepted.sh` passed.

- `/home/steve/.venvs/vllm-xpu/bin/python -m py_compile
  /home/steve/src/vllm/vllm/utils/xpu_decode_timing.py` passed.
- A small import/filter exercise recorded only `xpu_moe.*` when
  `VLLM_XPU_DECODE_TIMING_LABEL_REGEX='^xpu_moe[.]'`.

No-sync label timing profile:

- Session: `qwen36-tp4-nosync-labeltiming-20260612t`.
- Artifacts:
  - `data/qwen36-quark-int8-tp4-nosync-labeltiming-20260612t.log`.
  - `data/qwen36-quark-int8-tp4-nosync-labeltiming-summary-20260612t.json`.
  - `data/qwen36-quark-int8-tp4-nosync-labeltiming-p512o128-20260612t.json`.
- p512/o128 corrected after-first speed: `100.669 tok/s`.
- p512/o128 e2e output speed: `95.384 tok/s`.
- vLLM decode histogram: `9.863 ms/token`.
- Process summary emitted `28` timing labels and step summary emitted `8`
  decode steps without device loss.
- Active decode-step bucket, no sync:
  - `gpu_model_runner.model_forward`: `5.461 ms/step` mean.
  - `gdn_attention_core_xpu.native`: `1.505 ms/step` mean.
  - `logits.local_argmax_lm_head`: `0.067 ms/step` mean.
  - visible timed total: `7.033 ms/step` mean.
- Interpretation: no-sync timing is safe and useful for call counts and
  host/graph-enqueue visibility, but it is not a real kernel-time profile.
  MoE substep labels appear in the process summary but not in active decode-step
  summaries under accepted graph replay, so no-sync cannot directly rank live
  MoE replay kernels.

Model-forward-only synchronized timing profile:

- Session: `qwen36-tp4-sync-modelonly-20260612u`.
- Artifacts:
  - `data/qwen36-quark-int8-tp4-sync-modelonly-20260612u.log`.
  - `data/qwen36-quark-int8-tp4-sync-modelonly-summary-20260612u.json`.
  - `data/qwen36-quark-int8-tp4-sync-modelonly-p512o64-20260612u.json`.
- Sync was limited to exactly `gpu_model_runner.model_forward`:
  `VLLM_XPU_DECODE_TIMING_LABEL_REGEX='^gpu_model_runner[.]model_forward$'`
  and
  `VLLM_XPU_DECODE_TIMING_SYNC_LABEL_REGEX='^gpu_model_runner[.]model_forward$'`.
- p512/o64 corrected after-first speed under this profiling overhead:
  `96.957 tok/s`.
- vLLM decode histogram under profiling overhead: `10.162 ms/token`.
- Steady active decode-step model-forward timing:
  - mean `8.438 ms/token`.
  - median `8.433 ms/token`.
  - p90 `8.463 ms/token`.
- Process-wide model-forward summary averaged `9.421 ms` over `64` counted
  calls, with a large `71.216 ms` max from non-steady startup/prefill/capture
  work. Use the steady decode-step bucket for c1 decode budgeting.

Restored accepted backend:

- Session: `qwen36-tp4-accepted-restored-after-selective-timing-20260612v`.
- Artifacts:
  - `data/qwen36-quark-int8-tp4-accepted-restored-after-selective-timing-20260612v.log`.
  - `data/qwen36-quark-int8-tp4-accepted-provenance-guard-after-selective-timing-20260612v.json`.
  - `data/qwen36-quark-int8-tp4-accepted-restored-after-selective-timing-speed-p512o128-20260612v.json`.
- Provenance guard passed all exact sentinels after restore.
- Restored p512/o128 corrected after-first speed: `100.196 tok/s`.
- Restored p512/o128 e2e output speed: `95.184 tok/s`.
- Restored decode histogram: `9.906 ms/token`.

New budget:

- The useful c1 decode budget is now approximately:
  - `8.44 ms/token` inside accepted graph model forward.
  - `~1.5 ms/token` outside or around graph forward, including scheduler,
    sampling/logits, stream timing, and measurement-visible overhead.
- The `>200 tok/s` goal needs `<=5 ms/token` overall. A pure outside-graph
  cleanup cannot get there; the model-forward graph must drop to about
  `4.5 ms/token`, or exact target-verified speculation must amortize multiple
  accepted tokens per target forward.

Next best technical target:

1. Build a graph-aware MoE flight recorder or offline replay fixture, because
   active decode graph replay hides Python MoE substep timers.
2. Use the replay fixture to attack the W8A8 MoE path: persistent expert worker,
   tile-native W8A8 repack, out-variant quant buffers, and exact route-window
   scheduling.
3. Keep model-forward-only sync as the safe live regression gate for future
   kernel changes; avoid global sync profiles unless a label filter is active.

## 2026-06-12 CPU MoE Flight Recorder

Script:

- `scripts/qwen36-moe-flight-recorder.py`.

Purpose:

- Convert real route-capture JSONL into layer/window flight records without
  requiring GPUs or interrupting the accepted backend.
- Rank layers by hot-expert coverage, window active expert counts, repeated
  top-k tuple share, and route-window shape. This is the input needed before
  writing persistent MoE kernels, hot-expert replication, tile-native W8A8
  repack caches, or EP/TP simulations.

Routecapture5 exact-ID run:

```bash
python3 scripts/qwen36-moe-flight-recorder.py \
  data/qwen36-quark-int8-tp4-routecapture5-routes-rank0-20260611.jsonl \
  --out data/qwen36-quark-int8-tp4-routecapture5-flight-record-20260612w.json \
  --markdown-out data/qwen36-quark-int8-tp4-routecapture5-flight-record-20260612w.md \
  --require-topk-ids \
  --window-size 16 \
  --hot-sizes 8,16,32,64 \
  --topn 16
```

Artifacts:

- `data/qwen36-quark-int8-tp4-routecapture5-flight-record-20260612w.json`.
- `data/qwen36-quark-int8-tp4-routecapture5-flight-record-20260612w.md`.

Findings from the limited layer-8/layer-20 capture:

- `254` records, `2` layers, `127` decode records per layer.
- Layer `8`: `117` aggregate active experts; top-16 experts cover `54.8%`
  of assignments; top-32 cover `75.5%`; p50 window active experts is `44`.
- Layer `20`: `125` aggregate active experts; top-16 experts cover `53.4%`
  of assignments; top-32 cover `72.9%`; p50 window active experts is `46`.
- p50 top-k tuple share is only `6.25%`, so whole-tuple replay is not the main
  opportunity. Expert-set locality is the opportunity.

Implication:

- A blind global hot-expert remap is still rejected by earlier replay data, but
  layer/window-specific tile-native packing or hot expert replication has enough
  route locality to justify a deeper fixture. For these two layers, a top-32
  hot set captures roughly three quarters of assignments while touching only
  `12.5%` of the experts.
- The next route capture should cover the highest-priority layers `9`, `14`,
  `21`, and all prompt classes, then feed the same flight recorder before any
  persistent-kernel or EP/TP implementation work.

## 2026-06-12 Broader Flight Records And Hotset Planning

New script:

- `scripts/qwen36-moe-hotset-plan.py`.

Purpose:

- Estimate the memory cost and route coverage of exact hot-expert repack or
  replication plans from CPU-only flight records.
- Keep the plan exact: hot experts can use a faster tile-native or persistent
  path, but cold experts must fall back to the same Quark W8A8 math, so this is
  a performance layout change rather than a model-quality change.

New artifacts:

- `data/qwen36-quark-int8-tp4-routecapture6-flight-record-20260612x.json`.
- `data/qwen36-quark-int8-tp4-routecapture6-flight-record-20260612x.md`.
- `data/qwen36-quark-int8-tp4-promptclass-flight-record-20260612x.json`.
- `data/qwen36-quark-int8-tp4-promptclass-flight-record-20260612x.md`.
- `data/qwen36-quark-int8-tp4-routecapture6-hotset-plan-20260612x.json`.
- `data/qwen36-quark-int8-tp4-routecapture6-hotset-plan-20260612x.md`.
- `data/qwen36-quark-int8-tp4-promptclass-hotset-plan-20260612x.json`.
- `data/qwen36-quark-int8-tp4-promptclass-hotset-plan-20260612x.md`.

Routecapture6 exact-ID findings:

- `285` records across layers `9`, `14`, and `21`.
- Layer `9`: top-16 coverage `51.1%`, top-32 `72.2%`, top-64 `91.6%`,
  p50 window active experts `47.0`.
- Layer `21`: top-16 `48.9%`, top-32 `68.3%`, top-64 `86.4%`,
  p50 window active experts `48.5`.
- Layer `14`: top-16 `42.1%`, top-32 `64.5%`, top-64 `87.4%`,
  p50 window active experts `50.0`.
- p50 repeated top-k tuple share is still only `6.25%`, so full-route
  memoization is not the main path. Expert-set locality is the path.

Prompt-class findings:

- `2600` records across layers `8`, `9`, `14`, `20`, and `21`.
- These prompt-class JSONLs have count vectors but no exact `topk_ids`, so
  tuple-share metrics are unavailable.
- Top-32 coverage ranges from `57.8%` to `62.8%`; top-64 ranges from `78.6%`
  to `83.0%`.
- Prompt-class p50 window active experts is lower than routecapture6:
  `22` to `24` experts, which is favorable for persistent workers and
  hotset-local scheduling.

Hotset memory model from the current model config:

- `hidden_size=2048`, `moe_intermediate_size=512`, `num_hidden_layers=40`,
  `num_experts=256`, `tp_size=4`.
- Per local TP-shard expert, including current fp32 scales: `795648` bytes,
  or about `0.759 MiB`.
- One layer top-32 hotset costs about `24.3 MiB/rank`.
- All-layer local-rank estimates:
  - top-16: `485.6 MiB/rank`.
  - top-32: `971.2 MiB/rank`.
  - top-64: `1942.5 MiB/rank`.

Implication:

- A top-32 or top-64 hotset cache is cheap enough to prototype without
  threatening the 32 GiB B70 memory budget. This makes a tile-native W8A8
  repack cache or persistent hot-expert layerlet a serious next target.
- Do not implement another global expert physical remap. Earlier replay showed
  layer/window-specific wins and losses. The better exact design is a hotset
  fast path with cold-expert fallback, gated by layer and route-window evidence.
- Start with layers `9` and `20`. Layer `9` has the best exact-ID coverage in
  routecapture6, while layer `20` remains strong in prompt-class and earlier
  exact-ID captures.
- Keep the model-forward-only synchronized timing profile as the live regression
  gate. Any kernel patch must reduce the `8.44 ms/token` model-forward bucket,
  not only improve an isolated microbench.

External signals checked:

- The current Localmaxxing Arc Pro B70 Qwen snapshot has the accepted
  Qwen3.6 Quark W8A8 INT8 4x B70 run at the top of the public filtered result
  set, with `99.77 tok/s` and 32K context:
  <https://localmaxxing.com/api/leaderboard?hardwareName=Arc%20Pro%20B70&modelFamily=qwen&limit=20>.
- `vllm-xpu-kernels` is the right upstream surface for this work because it
  already exposes XPU MoE, expert remapping, FP8 quantization/GEMM, and grouped
  GEMM kernels:
  <https://github.com/vllm-project/vllm-xpu-kernels>.
- The vLLM XPU migration RFC records the move from IPEX to the dedicated
  `vllm-xpu-kernels` library and notes W8A16/W8A8 FP8 support work:
  <https://github.com/vllm-project/vllm/issues/33214>.
- Intel's newer XPU container notes claim persistent MoE GEMM plus fused
  activation gave Qwen3-30B-A3B a `2.6x` end-to-end improvement:
  <https://github.com/intel/ai-containers/blob/main/vllm/0.10.2-xpu.md>.
- The vLLM Arc Pro B-Series blog explains why persistent MoE matters: it
  removes per-iteration launch/scheduling gaps and keeps work resident despite
  routing dependencies:
  <https://vllm.ai/blog/2025-11-11-intel-arc-pro-b>.
- Public B70 benchmarking outside this repo shows Qwen3.6-35B-A3B MoE is a
  good B70 shape even when run through different engines and quants:
  <https://github.com/PMZFX/intel-arc-pro-b70-benchmarks>.

## Bigger Bolder Ideas After Hotset Planning

1. **Exact hotset persistent MoE layerlets.**
   Build one layer-specific persistent kernel for a top-32 or top-64 hotset.
   It should keep expert workers resident across gate, gather, W8A8 GEMM1,
   fused activation, dynamic quant, W8A8 GEMM2, scatter, and local reduction.
   Cold experts stay on the current exact path. This is the most direct way to
   test whether Intel's reported persistent-MoE class of wins can transfer to
   this exact Quark W8A8 model.

2. **Tile-native W8A8 repack cache with checksum promotion.**
   At load time, duplicate selected hot experts into the exact tile layout
   needed by the fastest B70 grouped-GEMM kernel. Store per-expert checksums and
   a manifest so the cache is reproducible and quality-auditable. The memory
   estimate says all-layer top-64 is only about `1.9 GiB/rank`, so this is now
   practical.

3. **Hybrid replicated-attention plus expert-parallel simulation.**
   Simulate a layout where dense attention and router state are replicated but
   MoE experts are sharded or replicated by hotness. This may remove some TP4
   dense allreduce cost while replacing it with tiny MoE token exchange. Use
   route windows before coding because c1 all-to-all overhead can erase the win.

4. **TP1/TP2 exact latency lane capacity proof.**
   Re-test the same Quark W8A8 model at lower max context and tighter
   `max_num_seqs` on TP1 or TP2. If it fits, it could beat TP4 c1 latency by
   removing cross-card collectives. It would not replace the 32K production
   lane until capacity and quality are proven.

5. **Static single-request decode appliance.**
   Build a fixed-bucket c1 runner outside the full vLLM scheduler that reuses
   the same tokenizer, weights, graph cache, sampling, and quality canaries.
   If it is still near `100 tok/s`, kernels are the ceiling. If it is much
   faster, production should add a certified latency sidecar.

6. **Persistent-MoE transplant bakeoff from newer Intel stack.**
   Isolate the persistent MoE and fused activation pieces from the newest Intel
   XPU container or `vllm-xpu-kernels`, then run them in a tiny route-replay
   harness before touching the accepted server. This avoids a full host-stack
   migration while still testing the big upstream kernel idea.

7. **Target-verified MTP/DFlash sidecar with resident verifier state.**
   Keep speculation on the table, but only with the current Quark W8A8 model as
   the in-engine verifier. The parent-state traces show external refill
   verification is not equivalent enough. The bold version is a transactional
   verifier that can accept several tokens per model-forward without losing
   exact sentinel parity.

8. **Graph-resident metadata lane.**
   Move block-table tail updates, accepted-token counters, slot mappings, and
   small scheduler fills into graph-stable device buffers. This targets both
   the `~1.5 ms/token` outside-forward budget and the device-lost class seen
   around metadata copy/fill operations.

9. **BF16 differential plus route-replay numeric gate.**
   Expand quality validation beyond exact token sentinels by sampling BF16
   fallback logit-rank deltas and replaying captured MoE inputs through old and
   new kernels. This catches subtle kernel drift before a speed candidate ever
   reaches the public endpoint.

10. **Upstreamable performance packet.**
    Package one captured route window, minimal weights/scales slice,
    model-forward timing, and hotset-plan numbers into a tiny repro for Intel
    and vLLM maintainers. The current evidence is specific enough to ask for
    persistent W8A8 MoE support on this model rather than generic "XPU is slow"
    advice.

## 2026-06-12 Layer 9/20 Hotset Manifest

New script:

- `scripts/qwen36-moe-hotset-manifest.py`.

Purpose:

- Build layer-specific hotset manifests from raw route JSONL files, not the
  summarized flight records, so full expert count vectors remain available.
- Combine exact-ID captures with prompt-class captures using source-normalized
  expert scores. This prevents long prompt-class files from dominating shorter
  exact captures.
- Emit replay start indices and command lines for the existing route-replay
  harnesses, so kernel work can start from fixed, reproducible windows.

Artifacts:

- `data/qwen36-quark-int8-tp4-hotset-manifest-l9-l20-20260612y.json`.
- `data/qwen36-quark-int8-tp4-hotset-manifest-l9-l20-20260612y.md`.
- `data/qwen36-quark-int8-tp4-hotset-manifest-l9-route6-dryrun-20260612y.json`.
- `data/qwen36-quark-int8-tp4-hotset-manifest-l20-route5-dryrun-20260612y.json`.
- `data/qwen36-quark-int8-tp4-hotset-manifest-l9-pcmath-dryrun-20260612y.json`.
- `data/qwen36-quark-int8-tp4-hotset-manifest-l20-pcrepetitive-dryrun-20260612y.json`.

Layer results:

- Layer `9` uses six sources: routecapture6 exact plus prompt-class code,
  math, repetitive, structured, and long-natural captures.
  - Source-normalized top-32 mean coverage: `78.4%`.
  - Source-normalized top-32 minimum coverage: `52.0%`.
  - Source-normalized top-64 mean coverage: `88.7%`.
  - Source-normalized top-64 minimum coverage: `75.0%`.
  - Source top-32 union size: `69`; intersection size: `0`.
  - Recommendation: top-64 hotset. Top-32 is worth a memory-minimal subtest,
    but it fails the `0.60` worst-source coverage threshold.
- Layer `20` uses six sources: routecapture5 exact plus the same prompt-class
  sources.
  - Source-normalized top-32 mean coverage: `80.2%`.
  - Source-normalized top-32 minimum coverage: `56.9%`.
  - Source-normalized top-64 mean coverage: `91.0%`.
  - Source-normalized top-64 minimum coverage: `78.4%`.
  - Source top-32 union size: `62`; intersection size: `2`.
  - Recommendation: top-64 hotset. Top-32 is close, but still below the
    worst-source guardrail.

Replay windows validated without GPU execution:

- Layer `9` exact-ID routecapture6:
  - route starts: `0,1,2,46,78`.
  - dry-run records matched: `95`.
  - selected 16-token windows have `37`, `38`, `38`, `58`, and `45` active
    experts.
- Layer `20` exact-ID routecapture5:
  - route starts: `11,12,13,52,63`.
  - dry-run records matched: `127`.
  - selected 16-token windows have `44`, `42`, `42`, `48`, and `42` active
    experts.
- Layer `9` prompt-class math stress windows:
  - route starts: `5,22,52,58,85,211`.
  - selected windows have `56` to `61` active experts.
- Layer `20` prompt-class repetitive stress windows:
  - route starts: `6,33,96,101,159,222`.
  - selected windows have `47` to `61` active experts.

Concrete next implementation target:

1. Prototype a top-64 hotset fast path for layer `9` first, because it has the
   best exact-ID coverage and a wide stress range in replay windows.
2. Keep top-32 as a subtest to measure the speed-memory tradeoff, but do not
   assume it is production-safe unless prompt-class worst-source coverage
   improves or the cold fallback overhead is negligible.
3. Implement as a hotset fast path plus exact cold fallback, not a physical
   global remap. The source top-32 intersections are too small for a global
   hotset to be trustworthy.
4. Use these replay commands as the first gate:
   - `scripts/bench-qwen36-int8-moe-kernels.py` for exact topk rows from
     routecapture6/routecapture5.
   - `scripts/bench-qwen36-route-exact-w8a8-grouped-gemm.py --dry-run` and then
     real grouped-GEMM runs for count-vector prompt-class stress windows.
5. Promote no endpoint change unless the accepted model-forward synchronized
   bucket drops below the current `8.44 ms/token` baseline and exact provenance
   sentinels still pass.

## 2026-06-12 Hotset Split Replay Model

Updated script:

- `scripts/bench-qwen36-route-exact-w8a8-grouped-gemm.py`.

New support:

- `--hotset-experts`: supply a logical expert hotset for replay windows.
- `--hotset-cold-mode full|compact|both`: model cold fallback either as the
  original full expert table with hot rows zeroed, or as an upper-bound compact
  cold table containing only active cold experts.
- Dry-run output now reports hot rows, cold rows, hot coverage, hot active
  experts, cold active experts, and cold fallback expert count per selected
  route window.

Artifacts:

- `data/qwen36-quark-int8-tp4-hotset-split-l9-route6-dryrun-20260612z.json`.
- `data/qwen36-quark-int8-tp4-hotset-split-l9-pcmath-dryrun-20260612z.json`.
- `data/qwen36-quark-int8-tp4-hotset-split-l20-route5-dryrun-20260612z.json`.
- `data/qwen36-quark-int8-tp4-hotset-split-l20-pcrepetitive-dryrun-20260612z.json`.

Layer `9` top-64 split:

- Exact-ID routecapture6 windows:
  - hot coverage: `93.8%`, `93.8%`, `93.8%`, `75.0%`, `78.9%`.
  - hot rows out of 128: `120`, `120`, `120`, `96`, `101`.
  - cold rows: `8`, `8`, `8`, `32`, `27`.
  - cold active experts: `5`, `5`, `5`, `22`, `19`.
- Prompt-class math stress windows:
  - hot coverage: `69.5%`, `83.6%`, `77.3%`, `72.7%`, `83.6%`, `83.6%`.
  - cold rows: `39`, `21`, `29`, `35`, `21`, `21`.
  - cold active experts: `30`, `18`, `22`, `26`, `18`, `18`.

Layer `20` top-64 split:

- Exact-ID routecapture5 windows:
  - hot coverage: `85.9%`, `85.9%`, `85.9%`, `87.5%`, `82.0%`.
  - cold rows: `18`, `18`, `18`, `16`, `23`.
  - cold active experts: `16`, `16`, `16`, `11`, `13`.
- Prompt-class repetitive stress windows:
  - hot coverage: `62.5%`, `87.5%`, `87.5%`, `87.5%`, `87.5%`, `87.5%`.
  - cold rows: `48`, `16`, `16`, `16`, `16`, `16`.
  - cold active experts: `34`, `12`, `12`, `13`, `12`, `12`.

Implication:

- Top-64 hotsets are strong enough to justify a real fast-path prototype. They
  move most rows into a small, stable expert set on the exact-ID windows and on
  most prompt-class stress windows.
- The cold fallback is small on most windows, but not free. A naive two-launch
  hotset path can lose to launch overhead unless the hot path is materially
  faster or the cold path is fused/cheap.
- The next implementation should not be only "run grouped GEMM twice." Better
  targets:
  1. a persistent top-64 hotset layerlet with an in-kernel cold fallback queue,
  2. a tile-native hotset repack cache with cold rows sent through the existing
     exact path only when needed,
  3. or a benchmark-only two-launch hot/cold model to establish the minimum
     speedup required before writing the persistent kernel.
- Layer `9` remains first because the exact-ID hot coverage is excellent and
  the stress window range is broad enough to expose fallback overhead.

## 2026-06-12 Follow-Up Ideas Added After Hotset Split

Current constraint:

- The accepted endpoint currently occupies essentially all four B70 cards. Do
  CPU-safe modeling, dry runs, and source inspection while the endpoint is live.
  Real XPU grouped-GEMM or fused-MoE microbenchmarks need a deliberate
  maintenance window where the accepted backend is stopped, benchmarked, and
  restored with the provenance guard.

Immediate things to try next:

1. **Hotset split floor model without GPU allocation.**
   Extend the existing W8A8 kernel-floor or route-replay scripts to estimate
   hot rows, cold rows, active hot experts, active cold experts, and launch
   counts per layer/window. The goal is to answer whether top-64 needs a
   persistent/fused kernel to win, or whether a simpler two-launch benchmark is
   worth testing during a maintenance window.
2. **Layer `9` top-64 GPU microbench during a backend stop.**
   First test only the routecapture6 exact windows with tiny iteration counts,
   then add the math stress windows. Record full-table, hot+full-cold, and
   hot+compact-cold timings. If hot+full-cold is slower, stop spending time on
   two independent grouped GEMMs and move straight to persistent/fused work.
3. **Grouped-GEMM policy override sweep on exact route windows.**
   Inspect and exercise the local XPU grouped-GEMM policy override path against
   the captured layer `9` and `20` windows. The route distributions are now
   realistic enough that a policy sweep can be more informative than synthetic
   uniform expert-count tests.
4. **Top-64 tile-native repack cache.**
   Build a benchmark-only repacked hotset table where the 64 hot experts are
   physically adjacent and aligned for the current XPU tile shape. Cold experts
   remain exact and unchanged. This should reveal whether the main win is from
   better memory/layout locality or from eliminating launches.
5. **Quality gate before endpoint promotion.**
   Every candidate above must pass: exact token sentinels, route-replay numeric
   comparison against the current kernel, prompt-class canaries, and a BF16
   differential spot check. A speed-only MoE microbench is not enough.

Bigger, bolder ideas to keep on the board:

1. **One resident hotset layerlet per high-impact MoE layer.**
   Keep top-64 hot expert weights/scales resident in a layer-local persistent
   kernel, route hot rows in-kernel, and enqueue rare cold rows to the exact
   existing path. This attacks both launch overhead and small-M grouped-GEMM
   underutilization while preserving the same top-k experts and weights.
2. **Fuse hot expert gate/up/SwiGLU/down for the common case.**
   For hot rows only, test a fused exact-arithmetic layerlet that avoids
   materializing the intermediate activation between expert projections. The
   cold fallback remains the existing path. This is larger than a repack but
   could remove memory traffic and launches at the actual decode bottleneck.
3. **Adaptive per-request hotset cache.**
   Use the first few decode tokens or prompt-class route history to choose a
   per-layer hotset for the request, then run exact cold fallback for misses.
   The math is unchanged; only the hot table changes. The risk is scheduler and
   cache churn, so the first version should be offline replay only.
4. **Hybrid TP/EP for MoE layers only.**
   Keep dense/attention TP4, but route MoE experts with expert affinity across
   cards so hot experts are not always narrow TP shards. This is a bigger
   architecture change and may introduce all-to-all overhead, but it is one of
   the few no-quality-loss paths that could materially improve single-request
   MoE utilization on four GPUs.
5. **Static c1 latency lane separate from production aggregate lane.**
   Maintain a warmed, shape-bucketed, low-concurrency service for c1 latency
   experiments while a separate endpoint handles aggregate throughput. This
   would let command graphs, static memory pools, and hotset caches specialize
   aggressively without constraining the eventual production server.
6. **Device-resident scheduler metadata for decode.**
   The recurring stability/performance hazards around metadata copies suggest
   moving more decode-step metadata, block-table decisions, and top-k route
   state onto device-resident buffers. This is not a weight/model change, but
   it could reduce host fences and lower device-lost risk.
7. **Resident-state verifier speculation, not external refill verification.**
   External prompt-logprob/refill checks already diverged from accepted graph
   state. The quality-preserving speculation path is an in-engine copy-on-write
   fork of KV/GDN/request state where the Quark verifier accepts or rejects
   candidate tokens transactionally.
8. **Backend bakeoff with the exact same INT8 weights.**
   Keep `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` fixed, but compare the
   local vLLM/XPU path against Intel-native or Triton/oneDNN/SYCL prototype
   paths for just the captured MoE layerlets. This can expose whether the
   current limit is vLLM scheduling, the grouped-GEMM kernel, or B70 hardware
   utilization.
9. **Upstreamable hotset repro packet.**
   Package the layer `9` and `20` route windows, top-64 manifests, cold fallback
   counts, and a minimal grouped-GEMM benchmark into a standalone repro. This is
   the clearest way to ask Intel/vLLM maintainers for a persistent XPU W8A8 MoE
   kernel without requiring them to run the full 35B model.
10. **Reliability soak as part of speed validation.**
    Treat any `>100 tok/s` improvement as provisional until it survives a
    restart/restore cycle, provenance guard, repeated p512/o512 c1 run, and a
    short mixed prompt-class soak. The target is not just a fast single screen;
    it is a fast path that can become production.

## 2026-06-12 Hotset Split Floor Model

New script:

- `scripts/qwen36-hotset-split-floor-model.py`.

Purpose:

- Consume hotset split dry-run JSON without allocating GPU memory.
- Estimate hot coverage, cold fallback size, compact/full cold table-slot
  ratios, extra launch count, and body-speedup requirements under launch
  overhead scenarios.
- Keep the accepted endpoint live while narrowing the next maintenance-window
  GPU benchmark.

Artifacts:

- `data/qwen36-quark-int8-tp4-hotset-split-floor-model-20260612aa.json`.
- `data/qwen36-quark-int8-tp4-hotset-split-floor-model-20260612aa.md`.

Command:

```bash
python3 scripts/qwen36-hotset-split-floor-model.py \
  --dry-run-json data/qwen36-quark-int8-tp4-hotset-split-l9-route6-dryrun-20260612z.json \
  --dry-run-json data/qwen36-quark-int8-tp4-hotset-split-l9-pcmath-dryrun-20260612z.json \
  --dry-run-json data/qwen36-quark-int8-tp4-hotset-split-l20-route5-dryrun-20260612z.json \
  --dry-run-json data/qwen36-quark-int8-tp4-hotset-split-l20-pcrepetitive-dryrun-20260612z.json \
  --baseline-us 150,200,270 \
  --launch-overhead-us 5,10,20,40 \
  --primary-baseline-us 200 \
  --primary-launch-overhead-us 10 \
  --output-json data/qwen36-quark-int8-tp4-hotset-split-floor-model-20260612aa.json \
  --markdown-out data/qwen36-quark-int8-tp4-hotset-split-floor-model-20260612aa.md
```

Primary scenario:

- Full path normalized to a `200 us` selected MoE layer window.
- Launch overhead scenario: `10 us`.
- Two GEMM stages modeled per MoE layer window.
- Every selected window has a cold fallback, so a simple hot/cold split adds
  `2` launches per full MoE layer window.
- Under this scenario, the split body must be at least `1.11x` faster than the
  full body before the extra launch overhead breaks even.

Compact-cold results:

- Layer `9` routecapture6 exact windows:
  - hot coverage minimum/mean: `75.0%` / `87.0%`.
  - max cold rows: `32`.
  - max active cold experts: `22`.
  - compact table-slot ratio mean/max: `0.29x` / `0.34x`.
- Layer `9` math stress windows:
  - hot coverage minimum/mean: `69.5%` / `78.4%`.
  - max cold rows: `39`.
  - max active cold experts: `30`.
  - compact table-slot ratio mean/max: `0.34x` / `0.37x`.
- Layer `20` routecapture5 exact windows:
  - hot coverage minimum/mean: `82.0%` / `85.5%`.
  - max cold rows: `23`.
  - max active cold experts: `16`.
  - compact table-slot ratio mean/max: `0.31x` / `0.31x`.
- Layer `20` repetitive stress windows:
  - hot coverage minimum/mean: `62.5%` / `83.3%`.
  - max cold rows: `48`.
  - max active cold experts: `34`.
  - compact table-slot ratio mean/max: `0.31x` / `0.38x`.

Decision:

- Full-cold split is not worth a maintenance-window benchmark first. It is
  `1.25x` table slots versus the exact full path and still adds launches.
- Compact-cold split is worth one small maintenance-window microbench because
  it reduces table slots to roughly `0.29x` to `0.38x` of the full table on
  these windows.
- The production target remains persistent/fused hotset fallback, because a
  two-launch compact split still needs enough body speedup to overcome launch
  overhead and row math is unchanged.
- Layer `9` routecapture6 exact windows remain the first GPU test. Then add
  layer `9` math stress. Do not spend endpoint downtime on full-cold split
  unless compact-cold unexpectedly wins and the comparison needs a control.

## 2026-06-12 Layer 9 Hotset Split GPU Microbench

Summary artifact:
`data/qwen36-quark-int8-tp4-hotset-split-l9-route6-gpu-hotsetbench-20260612ac.md`.

Artifacts:

- GPU timing JSON:
  `data/qwen36-quark-int8-tp4-hotset-split-l9-route6-gpu-hotsetbench-20260612ac.json`.
- Run log:
  `data/qwen36-quark-int8-tp4-hotset-split-l9-route6-gpu-hotsetbench-20260612ac.log`.
- XPU state snapshots:
  `data/qwen36-quark-int8-tp4-hotset-split-l9-route6-gpu-hotsetbench-20260612ac-pre-xpusmi-ps.txt`,
  `data/qwen36-quark-int8-tp4-hotset-split-l9-route6-gpu-hotsetbench-20260612ac-poststop-xpusmi-ps.txt`,
  and
  `data/qwen36-quark-int8-tp4-hotset-split-l9-route6-gpu-hotsetbench-20260612ac-postrestore-xpusmi-ps.txt`.
- Restored accepted-backend provenance:
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-hotsetbench-20260612ac.json`.
- Restored speed sanity:
  `data/qwen36-quark-int8-tp4-post-hotsetbench-sanity-repetitive-p512o256-20260612ac.json`.

Result:

- The top-64 layer `9` compact hot/cold split was exact but slower on XPU.
- Exact grouped-GEMM mean total: `213.852 us`.
- Compact hot/cold split mean total: `407.192 us`.
- Mean split/exact ratio: `1.928x` slower.
- The split was slower even on high-coverage windows:
  `1.525x`, `1.990x`, and `2.420x` slower at `93.75%` hot coverage.
- The accepted endpoint restored cleanly after the maintenance window:
  provenance guard passed exact sentinels and the repetitive p512/o256 sanity
  measured `99.157 tok/s` corrected after first text chunk with
  `10.047 ms/generated token` vLLM decode time.

Decision:

- Reject simple two-launch compact hot/cold split as a speed path.
- Do not spend more endpoint downtime on full-cold split, prompt-class
  two-launch split, or "try a different top-N" split variants unless a kernel
  change first removes most hot/cold launch overhead.
- Keep the hotset idea, but only in one-launch or persistent forms:
  in-kernel cold queue, tile-native repack inside the existing grouped-GEMM
  launch, or a persistent layerlet that does hot and fallback work without a
  second Python/dispatcher launch.
- The floor model was useful because it made the maintenance window narrow.
  The GPU result now replaces the floor-model decision: compact split was worth
  exactly one screen, and the screen says no.

Additional things to try from this result:

1. **One-launch hotset fallback kernel.**
   Keep hot and cold experts in one dispatch. The hot path can use a packed
   top-N table, while the cold path pulls exact fallback work from an in-kernel
   queue. This preserves exactness and attacks the launch overhead that killed
   the compact split.

2. **Grouped-GEMM small-shape policy screen.**
   Route replay shows compact fallback shapes such as `64+5`, `64+19`, and
   `64+22`. Build a policy benchmark that chooses between current grouped GEMM,
   direct per-expert GEMM, batched tiny GEMM, and persistent grouped GEMM for
   these shapes. The current kernel path is not optimized for the split sizes.

3. **Tile-native hotset repack used without splitting launches.**
   Repack hot experts into the best B70 tile layout, but feed the existing
   logical route through one kernel path. The fallback remains exact original
   weights. This tests whether layout helps without paying the split launch tax.

4. **Layer-local persistent MoE worker.**
   Prototype one layer that holds route metadata, expert tiles, intermediate
   activation, and quant buffers resident for both MoE GEMMs. This is the
   cleanest non-speculative route to halving the `~10 ms/token` decode budget.

5. **Route-conditioned EP/TP hybrid simulator.**
   Use the same route windows to simulate hot-expert replication, EP4, TP2+EP2,
   and replicated-attention/sharded-expert layouts. If the simulator cannot beat
   TP4 on bytes and imbalance, do not implement a new parallelism scheme.

6. **Decode command-buffer compaction.**
   Count every kernel launch and barrier for one token, then prototype a
   command-graph or persistent-loop lane that keeps the decode step on-device
   across MoE, GDN/linear attention, logits, and sampling metadata updates.

7. **Single-card hot-lane experiment as a control.**
   If TP4 communication or rank imbalance is hiding the best c1 path, run a
   memory-feasible single-card or two-card static lane for short contexts using
   the same exact model and quality sentinels. It may lose capacity but reveal
   whether multi-card TP is the latency wall.

8. **BF16 differential micro-suite for kernel changes.**
   Keep Quark W8A8 as the production target, but periodically compare sentinel
   prompts, route windows, and nearby logit ranks to BF16. This catches
   numerically suspicious "exact enough" kernel changes before they reach the
   live endpoint.

9. **Speculation only with resident target verification.**
   External refill/logprob sidecars already diverged from continuous accepted
   decode, so do not chase sidecar speculation. The bold path is in-engine
   copy-on-write KV/GDN/request state with target-model commit/rollback.

10. **Upstream perf repro packet.**
    Package the hotset negative, route windows, exact sentinel guard, and
    grouped-GEMM shapes into a small Intel/vLLM repro. A negative result with
    real routes is useful: it points maintainers toward persistent/grouped-GEMM
    policy work instead of more split-launch experiments.

## 2026-06-12 Route-Conditioned Parallelism Simulation

New script:

- `scripts/qwen36-route-parallelism-sim.py`.

Artifacts:

- Focused routecapture6 simulation:
  `data/qwen36-quark-int8-tp4-routecapture6-parallelism-sim-20260612ad.json`
  and
  `data/qwen36-quark-int8-tp4-routecapture6-parallelism-sim-20260612ad.md`.
- Prompt-class 16-record window simulation:
  `data/qwen36-quark-int8-tp4-promptclass-parallelism-sim-20260612ad.json`
  and
  `data/qwen36-quark-int8-tp4-promptclass-parallelism-sim-20260612ad.md`.
- Prompt-class 8-record window simulation, added so short code/structured
  traces are represented:
  `data/qwen36-quark-int8-tp4-promptclass-parallelism-sim-w8-20260612ad.json`
  and
  `data/qwen36-quark-int8-tp4-promptclass-parallelism-sim-w8-20260612ad.md`.

What the simulator measures:

- `compute_pressure_vs_tp4`: route-load pressure normalized so `1.0` means
  balanced row-work equal to the current TP4 proxy.
- `communication_row_fraction_proxy`: routed row fraction that still needs
  expert-parallel movement. Plain EP/TP-EP policies are `1.0`; hot replication
  reduces it by localizing hot rows.
- `expert_memory_relative_to_tp4`: per-rank expert-weight memory lower bound
  relative to current TP4. Dense weights and KV are intentionally excluded.

Result:

- Focused routecapture6, 15 windows:
  - `ep4_greedy_static`: mean pressure `1.238`, p95 `1.456`, comm proxy `1.000`.
  - `tp2_ep2_greedy_static`: mean pressure `1.079`, p95 `1.177`, comm proxy `1.000`.
  - `ep4_hot32_replicated_greedy`: mean pressure `1.002`, p95 `1.009`,
    comm proxy `0.311`, memory lower bound `1.375x`.
  - `ep4_hot64_replicated_greedy`: mean pressure `1.000`, p95 `1.000`,
    comm proxy `0.118`, memory lower bound `1.750x`.
- Prompt-class 16-record windows, 150 windows:
  - `ep4_greedy_static`: mean pressure `1.193`, p95 `1.312`, comm proxy `1.000`.
  - `tp2_ep2_greedy_static`: mean pressure `1.069`, p95 `1.156`, comm proxy `1.000`.
  - `ep4_hot64_replicated_greedy`: mean pressure `1.000`, p95 `1.000`,
    comm proxy `0.109`, memory lower bound `1.750x`.
- Prompt-class 8-record windows, 315 windows:
  - `ep4_greedy_static`: mean pressure `1.269`, p95 `1.562`, comm proxy `1.000`.
  - `tp2_ep2_greedy_static`: mean pressure `1.100`, p95 `1.250`, comm proxy `1.000`.
  - `ep4_hot64_replicated_greedy`: mean pressure `1.000`, p95 `1.000`,
    comm proxy `0.110`, memory lower bound `1.750x`.

Decision:

- Plain EP4 is not a clean c1 speed path. Even with static greedy placement it
  keeps the full expert-parallel movement proxy and shows meaningful p95
  imbalance.
- TP2+EP2 is less imbalanced than EP4, but it still keeps the full movement
  proxy and does not obviously halve the `~10 ms/token` decode budget.
- Hot-expert replication remains interesting, but only as an ingredient:
  top-64 replication can reduce routed-row movement to about `0.11x` while
  keeping route-load pressure near the TP4 proxy, at roughly `1.75x` per-rank
  expert-weight memory. It does not reduce MoE compute by itself, so it is not
  enough for `>200 tok/s` without a persistent/tile-native kernel, collective
  removal, or a static latency lane.
- The next implementation bet should not be a broad EP rewrite. The better
  sequence is:
  1. measure current per-rank expert-weight and KV headroom for hot64,
  2. prototype one-layer hot64 replicated routing in route replay only,
  3. pair it with one-launch persistent/tile-native MoE work,
  4. then consider a static c1 sidecar if the replay kernel shows a real
     latency drop.

## 2026-06-12 Hot-Replication Memory Feasibility

New script:

- `scripts/qwen36-hotrep-memory-plan.py`.

Artifacts:

- `data/qwen36-quark-int8-tp4-hotrep-memory-plan-20260612ae.json`.
- `data/qwen36-quark-int8-tp4-hotrep-memory-plan-20260612ae.md`.

Inputs:

- Accepted restore log:
  `/tmp/qwen36-quark-int8-tp4-accepted-restored-after-hotsetbench-20260612ac.log`.
- Live XPU telemetry from `xpu-smi dump -d -1 -m 18 -n 1`.
- Current model config:
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`.

Result:

- Per local-shard expert bytes: `795648`, matching the prior hotset plan and
  route-replay grouped-GEMM dimensions.
- Baseline all-expert MoE weight footprint per rank: `7770.0 MiB`.
- Live accepted lane memory snapshot:
  - device physical memory: `32656 MiB`.
  - max used: `32651.4 MiB`.
  - min free: `4.6 MiB`.
- Runtime KV report from vLLM:
  - available KV cache memory: `20.67 GiB`.
  - GPU KV cache size: `2052915` tokens.
  - maximum 32K-context concurrency: `62.65x`.
- Additional all-layer hot cache storage per rank:
  - hot16: `485.6 MiB`.
  - hot32: `971.2 MiB`.
  - hot64: `1942.5 MiB`.
- KV carve-out required for all-layer hot64:
  - no extra reserve: free about `188405` KV tokens, leaving `56.90x`
    theoretical 32K concurrency.
  - `512 MiB` reserve: free about `238064` KV tokens, leaving `55.38x`.
  - `1024 MiB` reserve: free about `287724` KV tokens, leaving `53.87x`.

Decision:

- Do not try to bolt all-layer hot64 storage onto the current accepted
  TP4/32K/c48 lane as-is. The lane is effectively full by telemetry.
- Hot64 storage is feasible in principle because it is small compared with the
  reported KV cache budget, but it needs an explicit KV/graph memory carve-out
  or a separate lower-context c1 latency lane.
- The next implementation step remains route-replay only:
  1. one-layer hot64 replicated routing,
  2. one-launch or persistent/tile-native execution,
  3. then a low-context sidecar memory screen if the route-replay kernel shows
     a real latency win.
- This keeps the production lane stable while we test whether hot replication
  has speed value before spending VRAM on it.

## 2026-06-12 Hot64 Route Work-Queue Prototype

New script:

- `scripts/qwen36-hotrep-route-plan.py`.

Artifacts:

- Layer 9 routecapture6:
  `data/qwen36-quark-int8-tp4-hotrep-route-plan-l9-route6-20260612af.json`
  and
  `data/qwen36-quark-int8-tp4-hotrep-route-plan-l9-route6-20260612af.md`.
- Layer 20 routecapture5:
  `data/qwen36-quark-int8-tp4-hotrep-route-plan-l20-route5-20260612af.json`
  and
  `data/qwen36-quark-int8-tp4-hotrep-route-plan-l20-route5-20260612af.md`.

Purpose:

- Convert captured exact `topk_ids` into kernel-facing per-rank hot/cold work
  queues and gather maps.
- Preserve exact routing: no expert dropping, no top-k approximation, and no
  prompt-class substitution.
- Keep this as route replay only; no live endpoint restart or production-lane
  VRAM changes.

Result:

- Layer 9, routecapture6, starts `0,1,2,46,78`:
  - assignments/window: `128`.
  - hot64 coverage mean/p95/min: `0.870` / `0.938` / `0.750`.
  - cold rows mean/max: `16.6` / `32.0`.
  - every selected window balances exactly to rows by rank `[32, 32, 32, 32]`.
  - generated JSON includes actual row detail and a complete 128-row gather map
    for each window.
- Layer 20, routecapture5, starts `11,12,13,52,63`:
  - assignments/window: `128`.
  - hot64 coverage mean/p95/min: `0.855` / `0.872` / `0.820`.
  - cold rows mean/max: `18.6` / `23.0`.
  - every selected window balances exactly to rows by rank `[32, 32, 32, 32]`.
  - generated JSON includes actual row detail and a complete 128-row gather map
    for each window.

Decision:

- Hot64 replicated routing is implementable as exact metadata for these
  route-replay windows. The route planner can produce:
  1. per-rank hot rows keyed by compact hot expert,
  2. per-rank cold rows keyed by logical expert,
  3. deterministic rank-local row indices,
  4. and a gather map back to original assignment order.
- This solves the route-metadata side of a one-launch hot64 layerlet, but it is
  not a speed result. The next meaningful gate is a kernel/microbench that
  consumes this exact queue format, runs hot and cold work in one dispatch or
  persistent loop, and compares output exactly against `xpu_fused_moe`.
- If that kernel cannot beat the current exact grouped-GEMM replay on these
  same windows, hot64 should stay a planning artifact rather than a production
  memory carve-out.

## 2026-06-12 Hotrep Route-Plan GEMM Shape Gate

New script:

- `scripts/bench-qwen36-hotrep-route-plan-gemm.py`.

Artifacts:

- Dry-run JSON:
  `data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-dryrun-20260612ag.json`.
- Dry-run summary:
  `data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-dryrun-20260612ag.md`.

Command:

```bash
python3 scripts/bench-qwen36-hotrep-route-plan-gemm.py \
  --dry-run \
  --route-plan-json \
    data/qwen36-quark-int8-tp4-hotrep-route-plan-l9-route6-20260612af.json \
    data/qwen36-quark-int8-tp4-hotrep-route-plan-l20-route5-20260612af.json \
  --output-json data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-dryrun-20260612ag.json \
  --markdown-out data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-dryrun-20260612ag.md
```

Purpose:

- Convert the exact hot64 route work queues into the grouped-GEMM shapes that
  a one-launch or persistent hot-replicated MoE layerlet would need to run.
- Compare three cases without changing the live endpoint:
  1. current exact full logical expert table,
  2. ideal per-rank hot+cold one-launch lower bound,
  3. hot and cold as separate per-rank launches.

Dry-run shape result:

- Current exact full table:
  - rows/window: `128`.
  - experts/table: `256`.
  - active experts/window: mean `43.4`, max `58`.
  - estimated allocation pressure: `128.56 MiB` for `gemm1`,
    `66.52 MiB` for `gemm2`.
- Hotrep per-rank one-launch shape:
  - rows/rank/window: `32`.
  - experts/rank/table: mean `68.1`, max `70`.
  - active experts/rank/window: mean `21.9`, max `25`.
  - estimated allocation pressure: max `35.15 MiB` for `gemm1`,
    `18.18 MiB` for `gemm2`.
- The two-launch hot/cold screen has the same shape pressure, but it will pay
  the same launch-tax failure mode that already made compact hotset splitting
  lose. Keep it as a diagnostic only.

Decision:

- This is a shape gate, not a speed result. It confirms the route-plan format
  produces plausible smaller per-rank work tables before any endpoint or kernel
  change.
- The next clean-XPU benchmark should run this same script without `--dry-run`
  after stopping the accepted endpoint, then restore the accepted backend and
  rerun provenance plus a short speed sanity.
- Promotion bar: a hotrep path only matters if the one-launch/persistent lower
  bound beats the current exact full-table grouped-GEMM replay on these same
  route windows. A two-launch hot/cold win is unlikely based on the previous
  negative GPU result.

Additional larger no-quality-loss ideas to track:

1. **Route-plan to persistent-kernel compiler.**
   Treat the hotrep JSON as an intermediate representation. Compile it into a
   persistent worker queue with fixed rank-local hot tables, cold overflow
   tasks, and deterministic gather maps. This avoids inventing the kernel API
   blind and makes route replay, parity, and production metadata share one
   format.

2. **Graph-resident MoE dispatch sequencer.**
   Move route packing, rows-per-expert metadata, and tiny scheduling decisions
   into graph-stable device buffers. The goal is to reduce host/device fences
   and stop making every decode token rebuild small MoE control structures.

3. **Hot cache as a low-context latency-lane feature only.**
   Do not spend the 32K production KV budget until a route-replay speed result
   exists. If hot64 wins, test it first in a smaller static c1 lane where
   `~2 GiB/rank` for all-layer hot cache is an intentional trade, not hidden
   pressure on the general service.

4. **Expert work-stealing inside a rank group.**
   Static row balance is good in the current windows, but cold experts can
   still create small irregular GEMMs. A persistent kernel could let idle
   workers steal cold expert tiles while preserving exact output order through
   the gather map.

5. **Per-layer route-class autotune cache.**
   Record a small menu of route classes per layer, prompt type, and decode
   phase, then pick a kernel policy from that cache: full table, hotrep
   one-launch, compact active-only, or persistent queue. The policy must be
   selected from route metadata, not from generated text semantics.

6. **XMX/DPAS roofline packet per MoE stage.**
   For each route-window shape, measure whether the XPU kernel is compute-bound,
   bandwidth-bound, or launch-bound. If hotrep reduces allocation but lowers
   DPAS occupancy too much, persistent full-table scheduling may be the better
   route than smaller tables.

7. **C++/SYCL single-layer parity binary.**
   Build one standalone executable that consumes captured hidden states,
   top-k routes, Quark W8A8 expert weights/scales, and the hotrep gather map.
   It should compare byte/logit-level against Python route replay while making
   Level Zero timelines and XMX counters easier to collect.

8. **Verified public perf packet after a real win.**
   When a material result clears a threshold such as `105` or `120 tok/s`,
   publish the Localmaxxing row with the exact command, dry-run shape artifact,
   route-window timing artifact, provenance guard, and quality sentinel file.
   The current `99.428 tok/s` row is still the only public exact-model B70 row
   as of this check, so a real improvement will be easy to distinguish.

## 2026-06-12 Hotrep Route-Plan GEMM Timing Result

Artifacts:

- Timing JSON:
  `data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-timing-20260612ah.json`.
- Timing summary:
  `data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-timing-20260612ah.md`.
- First restore log with device-lost event:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-hotrep-gemm-20260612ah.log`.
- Recovery snapshot:
  `data/qwen36-hotrep-gemm-device-lost-recovery-20260612ah/`.
- Successful second restore log:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-hotrep-gemm-recovery-20260612ah.log`.
- Successful provenance guard:
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-hotrep-gemm-recovery-20260612ah.json`.
- Successful p512/o128 speed smoke:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-hotrep-gemm-recovery-speed-p512o128-20260612ah.json`.

Command:

```bash
ZE_AFFINITY_MASK=0 ONEAPI_DEVICE_SELECTOR=level_zero:0 \
  /home/steve/.venvs/vllm-xpu/bin/python \
  scripts/bench-qwen36-hotrep-route-plan-gemm.py \
  --route-plan-json \
    data/qwen36-quark-int8-tp4-hotrep-route-plan-l9-route6-20260612af.json \
    data/qwen36-quark-int8-tp4-hotrep-route-plan-l20-route5-20260612af.json \
  --output-json data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-timing-20260612ah.json \
  --markdown-out data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-timing-20260612ah.md
```

Result:

- The benchmark ran cleanly on XPU 0 after stopping the accepted TP4 endpoint.
- Mean total grouped-GEMM time across the ten selected route windows:
  - `exact_full`: `189.694 us`.
  - `hotrep_one_launch_rankmax`: `197.037 us`.
  - `hotrep_two_launch_rankmax`: `389.275 us`.
- Stage means:
  - `exact_full/gemm1`: `97.138 us`.
  - `exact_full/gemm2`: `92.556 us`.
  - `hotrep_one_launch/gemm1`: `100.965 us`.
  - `hotrep_one_launch/gemm2`: `96.072 us`.
  - `hotrep_two_launch/gemm1`: `198.532 us`.
  - `hotrep_two_launch/gemm2`: `190.743 us`.

Decision:

- Hot64 route replication is rejected as a grouped-GEMM lower-bound speed path
  for these windows. Even the idealized one-launch rank-max screen is `3.9%`
  slower than the current full-table exact shape, despite the smaller
  per-rank table.
- The likely reason is small-shape/launch/occupancy overhead: shrinking the
  table from `256` experts to about `68-70` experts per rank does not make the
  B70 W8A8 grouped-GEMM kernel faster for this decode shape.
- Do not spend more production-lane downtime on endpoint hot64 replication,
  cold/hot two-launch variants, or KV carve-outs for hot64 unless a different
  persistent/tile-native kernel first reverses this lower-bound result.
- Keep the route-plan JSON format as useful metadata for persistent MoE,
  expert work queues, parity tests, and upstream repros. The data is still
  valuable; the current grouped-GEMM execution strategy is not.

Reliability note:

- The first accepted-backend restore after the microbench reached `/health`,
  then crashed on the first p512/o128 completion with
  `UR_RESULT_ERROR_DEVICE_LOST` in `block_table.copy_to_gpu(num_reqs)`, followed
  by `num_computed_tokens` copy failures. This is the same XPU metadata-copy
  failure class seen in earlier profiling restores.
- Recovery snapshot plus targeted vLLM cleanup succeeded; the four-XPU copy
  smoke passed with correct sums on devices `0-3`.
- The second restore passed the accepted provenance guard:
  `repetitive_kernel_notes` token `4752` at index `14`,
  `natural_latency_plan` token `11436` at index `17`, and token `198` at
  index `25`.
- The second restore speed smoke measured `99.733 tok/s` corrected after first
  text chunk and `9.953 ms/generated token` decode at p512/o128. The accepted
  quality/speed baseline is restored.

Next direction:

- Move hotrep out of the near-term serving path.
- Prioritize either:
  1. persistent/tile-native exact W8A8 MoE that can beat the full-table
     grouped-GEMM lower bound,
  2. graph-resident scheduler metadata to attack both latency and device-lost
     failure modes,
  3. exact target-verified speculation with a transactional resident-state
     verifier.

## 2026-06-12 Block-Table Dirty Commit Patch

New patch and validation:

- Patch:
  `patches/vllm-qwen36-xpu-block-table-dirty-commit-20260612.patch`.
- Validation script:
  `scripts/check-qwen36-block-table-dirty-commit.py`.
- Validation artifact:
  `data/qwen36-block-table-dirty-commit-check-20260612ai.json`.

Purpose:

- Reduce one known XPU reliability and latency pressure point:
  `block_table.copy_to_gpu(num_reqs)`.
- The current path copies the active block-table rows to XPU every prepare
  step. In c1 decode, that row normally changes only when the request is added,
  removed, moved, swapped, or receives a new KV block. For most generated
  tokens, the block table is unchanged.
- The default-off patch adds dirty-row tracking to `BlockTable` and makes
  `commit_block_table()` skip the host-to-XPU copy when no active rows changed,
  or copy only contiguous dirty row ranges when only a subset changed.

Controls:

- Runtime env:
  `VLLM_XPU_BLOCK_TABLE_DIRTY_COMMIT=1`.
- Optional stats log:
  `VLLM_XPU_BLOCK_TABLE_DIRTY_COMMIT_LOG_EVERY=<N>`.
- Production launch guard:
  `scripts/launch-qwen36-quark-int8-accepted.sh` now strips these env vars
  unless `VLLM_XPU_METADATA_COPY_ALLOW=1` is set.

Validation:

```bash
/home/steve/.venvs/vllm-xpu/bin/python -m py_compile \
  /home/steve/src/vllm/vllm/v1/worker/block_table.py \
  scripts/check-qwen36-block-table-dirty-commit.py

bash -n scripts/launch-qwen36-quark-int8-accepted.sh

/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/check-qwen36-block-table-dirty-commit.py \
  --output-json data/qwen36-block-table-dirty-commit-check-20260612ai.json
```

The CPU-device simulation passed:

- `total` commits: `7`.
- skipped commits: `2`.
- full commits: `1`.
- partial commits: `4`.
- copied dirty rows: `7`.

Decision:

- This is not a speed claim yet. It is a safe, default-off implementation
  candidate that specifically targets the repeated metadata-copy failure class
  observed after risky XPU runs.
- Next controlled A/B gate: launch accepted TP4/32K with
  `VLLM_XPU_METADATA_COPY_ALLOW=1`,
  `VLLM_XPU_BLOCK_TABLE_DIRTY_COMMIT=1`, and a moderate
  `VLLM_XPU_BLOCK_TABLE_DIRTY_COMMIT_LOG_EVERY`, then run provenance guard and
  p512/o128 plus p512/o512 speed smokes. Promote only if sentinels pass and
  decode latency improves or device-lost frequency drops.

## 2026-06-12 Dirty Block-Table Endpoint A/B

Session:

- `qwen36-tp4-dirty-blocktable-ab-20260612aj`.

Launch:

```bash
VLLM_XPU_METADATA_COPY_ALLOW=1 \
VLLM_XPU_BLOCK_TABLE_DIRTY_COMMIT=1 \
VLLM_XPU_BLOCK_TABLE_DIRTY_COMMIT_LOG_EVERY=64 \
LOG_PATH=data/qwen36-quark-int8-tp4-dirty-blocktable-ab-20260612aj.log \
scripts/launch-qwen36-quark-int8-accepted.sh
```

Artifacts:

- A/B log:
  `data/qwen36-quark-int8-tp4-dirty-blocktable-ab-20260612aj.log`.
- Provenance guard:
  `data/qwen36-quark-int8-tp4-dirty-blocktable-ab-provenance-20260612aj.json`.
- p512/o128 speed:
  `data/qwen36-quark-int8-tp4-dirty-blocktable-ab-speed-p512o128-20260612aj.json`.
- p512/o512 r2 speed:
  `data/qwen36-quark-int8-tp4-dirty-blocktable-ab-speed-p512o512-r2-20260612aj.json`.
- Restored accepted-backend log:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-dirty-ab-20260612aj.log`.
- Restored accepted-backend provenance:
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-dirty-ab-20260612aj.json`.
- Restored accepted-backend p512/o128 speed:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-dirty-ab-speed-p512o128-20260612aj.json`.

Quality/provenance:

- Provenance guard passed.
- `repetitive_kernel_notes` sentinel index `14`: expected/actual token `4752`.
- `natural_latency_plan` sentinel index `17`: expected/actual token `11436`.
- `natural_latency_plan` sentinel index `25`: expected/actual token `198`.
- Cache fragment matched the accepted TP4/32K no-prefix graph cache root.

Speed result:

- p512/o128:
  - corrected after-first output speed: `100.364 tok/s`.
  - e2e output speed: `95.451 tok/s`.
  - client TTFT: `75.614 ms`.
  - vLLM decode histogram: `9.893 ms/generated token`.
- p512/o512, 2 repeats:
  - corrected after-first output speed: `100.093 tok/s` mean.
  - e2e output speed: `98.814 tok/s` mean.
  - client TTFT: `76.200 ms` mean.
  - vLLM decode histogram: `9.972 ms/generated token` mean.

Dirty-commit counters:

- The patch worked mechanically. The latest visible per-worker counters reached
  roughly `1280` total commit calls with about `1270` skipped, `10` full
  copies, `0` partial copies, and `10` copied rows.
- There were no `DEVICE_LOST`, `Traceback`, or first-error lines in the A/B log
  during the provenance and speed smokes.

Decision:

- Neutral for c1 decode speed. The repeated block-table H2D copy is mostly
  redundant, but removing it did not move the `~10 ms/token` steady decode
  ceiling.
- Keep the patch default-off as a reliability and metadata-copy pressure
  reducer. It may matter more under multi-request churn, request add/remove
  cycles, swap/move events, or risky timing/profiling branches.
- Do not count this as a performance win toward `>200 tok/s`.
- Restore the normal accepted backend after the A/B because the env is still
  experimental.

Restore result:

- Session:
  `qwen36-tp4-accepted-restored-after-dirty-ab-20260612aj`.
- `/health` returned after `53 s`.
- Provenance guard passed all three exact sentinels after restore.
- Restored p512/o128 speed sanity:
  - corrected after-first output speed: `99.256 tok/s`.
  - e2e output speed: `94.425 tok/s`.
  - client TTFT: `76.050 ms`.
  - vLLM decode histogram: `10.003 ms/generated token`.
- The live backend is back on the normal accepted launch path, without the
  dirty block-table env enabled.

Things to try from this result:

1. **Metadata-copy stress soak.**
   Build a churn workload that repeatedly adds, removes, and completes requests
   while generating. Compare default block-table copies versus dirty commits for
   device-lost rate, host-copy count, TTFT p95, and c1 throughput.
2. **Unify tiny scheduler metadata updates.**
   The recurring failures also touched `num_computed_tokens` and
   `num_accepted_tokens`. Treat block tables as one member of a broader
   device-resident metadata project, not the whole project.
3. **Device-side metadata ring.**
   Prototype a graph-safe device buffer for block-table tails, computed-token
   counters, accepted-token counters, and slot maps, then update it with a tiny
   kernel instead of repeated host-to-device copies/fills.
4. **Keep a no-speed regression gate.**
   Any metadata patch must pass exact sentinels and stay within noise of the
   accepted `~100 tok/s` c1 baseline before it is used in risky profiling.
5. **Measure aggregate impact separately.**
   The A/B only tested single-request decode. Dirty commits may still improve
   aggregate throughput or tail latency at `c8`, `c16`, or `c48` where request
   churn and scheduler state are more active.

External context added while planning next steps:

- Localmaxxing currently shows the 4x Arc Pro B70 Qwen3.6-35B result set topped
  by two `~100 tok/s` c1 rows at 32K context, including the exact
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` run:
  <https://localmaxxing.com/api/leaderboard?hardwareName=B70&modelFamily=qwen&limit=20>.
- vLLM's Arc Pro B-series writeup lists the major XPU features that matter to
  this work: multi-GPU scaling, P2P transfer, optimized MoE models, async
  scheduling, prefill/decode disaggregation, n-gram/EAGLE/EAGLE3 speculative
  decoding, and mixed precision recipes:
  <https://vllm.ai/blog/2025-11-11-intel-arc-pro-b>.
- The Intel Triton-XPU grouped-GEMM issue specifically calls out skewed decode
  routing and real token distributions as critical for MoE kernel tuning:
  <https://github.com/intel/intel-xpu-backend-for-triton/issues/6389>.
- vLLM's public XPU page validates Arc Pro B-Series as the hardware target, but
  current recommended-model docs do not replace our exact-model validation:
  <https://docs.vllm.ai/en/stable/models/hardware_supported_models/xpu/>.
- vLLM's public W8A8 INT8 docs still describe the official INT8 compute support
  in NVIDIA terms, so our Quark/XPU path remains a local/vendor path that needs
  its own correctness and performance proof:
  <https://docs.vllm.ai/en/v0.18.0/features/quantization/int8/>.
- IPEX-LLM/OpenVINO/llama.cpp/Vulkan remain useful as control lanes for Intel
  hardware behavior, but they are not production candidates unless they can run
  the same Qwen3.6 A3B target with an 8-bit or BF16-equivalent fidelity gate.

New bigger, bolder ideas to keep visible:

1. **Exact decode appliance outside vLLM.**
   Build a fixed-bucket runner for one c1 shape that loads the exact Quark W8A8
   weights, certified graph/kernel artifacts, and fixed sampling, then bypasses
   the dynamic vLLM scheduler. If it stays near `100 tok/s`, the ceiling is
   kernel/hardware. If it jumps, production should add a latency sidecar.
2. **Persistent MoE kernel compiler from route windows.**
   Turn routecapture windows into generated kernel descriptors: layer, hotset,
   active experts, row maps, tile layout, and exact fallback policy. Generate a
   one-layer persistent worker and compare it against `xpu_fused_moe` before
   trying a server patch.
3. **Tile-native hotset cache with cold queue in one dispatch.**
   Keep top-64 hot experts packed in the fastest B70 layout, but execute hot and
   cold rows in one launch or persistent loop. The two-launch split lost; the
   one-dispatch form is still a serious no-quality-loss path.
4. **TP1/TP2 low-context sidecar as a latency control.**
   Try the exact model at lower max context and lower concurrency on one or two
   cards. The goal is not production capacity; it is to prove whether TP4
   collectives and rank synchronization are part of the c1 wall.
5. **XMX/DPAS proof packet.**
   Profile the hot W8A8 kernels down to DPAS/XMX utilization, occupancy, memory
   bandwidth, and launch gaps. If the current Quark path is not using the
   intended INT8 hardware efficiently, launch-flag tuning will never reach
   `>200 tok/s`.
6. **MTP/EAGLE/DFlash only behind resident target verification.**
   Speculation is still the clearest mathematical route to `>200 tok/s`, but
   only if the current model verifies candidate tokens from in-engine
   copy-on-write KV/GDN/request state. External refill verification is not good
   enough.
7. **Graph-resident decode loop.**
   Investigate keeping the whole single-token decode loop resident across
   scheduler metadata, GDN/linear attention, MoE, logits, and sampling metadata.
   This is larger than a kernel patch, but it attacks command gaps and host
   synchronization directly.
8. **Exact 8-bit engine bakeoff with route fixtures.**
   Compare vLLM/Quark, newer `vllm-xpu-kernels`, Intel container branches,
   OpenVINO/oneDNN GenAI if supported, IPEX-LLM, and llama.cpp/Vulkan as
   route-replay or short-context controls. Exclude 4-bit/AWQ and any Qwen3.5
   substitute.
9. **Host-stack breakglass lane.**
   Keep a separate disk/environment for aggressive Intel stack experiments:
   kernel/KMD, firmware, oneAPI, oneCCL, PyTorch XPU, Triton-XPU, and
   vLLM/vllm-xpu-kernels. A stack that improves speed but increases
   device-lost rate does not enter production.
10. **Public upstream perf packet.**
    Package exact sentinels, route windows, hotrep negative, dirty-copy A/B,
    model-forward timing, and Localmaxxing context into a small repro for Intel
    and vLLM. The ask should be precise: persistent or tile-native W8A8 MoE for
    skewed Qwen3.6 A3B decode on Arc Pro B70.

## 2026-06-12 Route-Exact Grouped-GEMM Roofline Packet

New script:

- `scripts/qwen36-gemm-roofline-from-timing.py`.

Purpose:

- Convert existing route-exact grouped-GEMM event timings into an offline
  roofline packet: GEMM shapes, active experts, estimated math operations,
  active-weight memory lower bound, full-table memory upper bound, effective
  TOPS, and implied bandwidth.
- This is a CPU-only analysis pass over timing JSON. It does not allocate XPU
  memory or interrupt the accepted backend.

Tooling boundary:

- `unitrace`, `oneprof`, and VTune are not installed in this environment.
- `xpu-smi` EU, bandwidth, and engine metrics require elevated MEI access; the
  current user does not have passwordless sudo.
- `intel_gpu_top` cannot see the current Xe devices from this user context.
- Therefore this packet cannot prove DPAS/XMX instruction use directly. It is a
  shape/timing roofline estimate from already-recorded kernel timings.

Command:

```bash
python3 scripts/qwen36-gemm-roofline-from-timing.py \
  --timing-json data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-timing-20260612ah.json \
  --output-json data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-roofline-20260612ak.json \
  --markdown-out data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-roofline-20260612ak.md
```

Artifacts:

- `data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-roofline-20260612ak.json`.
- `data/qwen36-quark-int8-tp4-hotrep-route-plan-gemm-roofline-20260612ak.md`.

Key numbers:

- `exact_full/gemm1`:
  - mean timing: `97.138 us`.
  - mean shape: `M=128, K=2048, N=256`.
  - mean active experts: `43.4`.
  - effective math throughput: `1.413 TOPS`.
  - active-weight lower-bound bandwidth: `0.245 TB/s`.
  - full-table upper-bound bandwidth: `1.419 TB/s`.
- `exact_full/gemm2`:
  - mean timing: `92.556 us`.
  - mean shape: `M=128, K=128, N=2048`.
  - mean active experts: `43.4`.
  - effective math throughput: `0.725 TOPS`.
  - active-weight lower-bound bandwidth: `0.133 TB/s`.
  - full-table upper-bound bandwidth: `0.754 TB/s`.
- `hotrep_one_launch_rankmax/gemm1`:
  - mean timing: `100.965 us`.
  - mean shape: `M=32, K=2048, N=256`.
  - effective math throughput: `0.337 TOPS`.
- `hotrep_one_launch_rankmax/gemm2`:
  - mean timing: `96.072 us`.
  - mean shape: `M=32, K=128, N=2048`.
  - effective math throughput: `0.175 TOPS`.
- `hotrep_two_launch_rankmax/cold` drops to roughly `0.050 TOPS` for `gemm1`
  and `0.026 TOPS` for `gemm2`, because the cold fallback is tiny
  (`~5` rows).

Interpretation:

- These effective TOPS are far below what a B70-class INT8 path should deliver
  if it were compute-saturating. The route-exact grouped-GEMM bottleneck is
  consistent with small-M/skewed-expert underutilization, launch/control
  overhead, a non-ideal kernel path, or some mix of those.
- The hotrep negative is now explained more clearly: shrinking the table also
  shrinks `M` per rank, and effective TOPS collapses further. Memory allocation
  pressure improved, but compute utilization got worse.
- This strengthens the decision to avoid more split-launch hot/cold variants.
  The credible no-quality-loss path is one of:
  1. persistent expert workers that keep skewed small-M work resident,
  2. tile-native W8A8 repack plus one-dispatch cold queue,
  3. grouped-GEMM policy/kernel work for real route distributions,
  4. or exact target-verified speculation that accepts multiple target tokens
     per expensive forward.

Next concrete ideas from this packet:

1. **Privilege/tooling lane for real counters.**
   Install or enable `unitrace`/VTune/oneprof, or grant MEI telemetry access to
   collect EU active/stall/idle, memory bandwidth, and DPAS/XMX counters on the
   route-replay GEMM harness.
2. **Grouped-GEMM shape amplification screen.**
   Benchmark synthetic exact-shape variants with larger `M` buckets
   (`128`, `256`, `512`, `1024`) but the same `K/N` and expert skew. If TOPS
   scales sharply with `M`, persistent batching/work aggregation is the right
   kernel direction.
3. **Small-M kernel policy search.**
   Compare current grouped GEMM against per-expert GEMM, packed batched GEMM,
   and persistent grouped GEMM for the observed route windows. The cold rows are
   too small for a normal grouped-GEMM launch to be viable.
4. **One-layer persistent MoE proof.**
   Start with one layer and one captured window. The success metric is not only
   lower microseconds; it must raise effective TOPS materially while matching
   `xpu_fused_moe` numerically.
5. **Upstream perf packet target.**
   Include the roofline packet with route windows, hotrep negative, and exact
   provenance sentinels when asking Intel/vLLM for persistent W8A8 MoE work.

## 2026-06-12 Bigger Bets Refresh And M-Scaling Gate

User direction:

- Keep tracking lessons, future experiments, results, and repro code in this
  repo.
- Continue pursuing speed on the current exact Qwen3.6 Quark W8A8 INT8 model
  without lowering quality.
- Think bigger than launch-flag tuning, but keep every idea tied to a proof
  artifact and a quality gate.

New dry-run artifact:

- Script: `scripts/bench-qwen36-grouped-gemm-m-scaling.py`.
- Dry-run JSON:
  `data/qwen36-quark-int8-tp4-grouped-gemm-mscaling-dryrun-20260612al.json`.
- Dry-run markdown:
  `data/qwen36-quark-int8-tp4-grouped-gemm-mscaling-dryrun-20260612al.md`.
- Validation:
  `python3 -m py_compile scripts/bench-qwen36-grouped-gemm-m-scaling.py`
  passed.
- Inputs:
  - `data/qwen36-quark-int8-tp4-hotrep-route-plan-l9-route6-20260612af.json`.
  - `data/qwen36-quark-int8-tp4-hotrep-route-plan-l20-route5-20260612af.json`.
- Dry-run generated `120` cases: `10` real route windows, `2` GEMM stages,
  and target row buckets `32,64,128,256,512,1024`.
- The artifact is intentionally timing-free. It validates shape construction
  only and should be run on XPU only in a clean benchmark window.

Why this gate matters:

- The roofline packet showed current route-exact grouped GEMM is far below B70
  INT8 compute potential.
- The hotrep split made `M` smaller and got slower, so the next question is
  whether larger `M` buckets recover TOPS.
- If TOPS scales strongly from `M=128` to `M=512/1024`, persistent batching,
  work aggregation, or a static c1 lane that amortizes more routed rows per
  launch is a credible no-quality-loss direction.
- If TOPS stays flat, the blocker is more likely the underlying kernel path,
  data layout, DPAS/XMX utilization, launch/control overhead, or a bad
  small-shape policy. In that case, route batching alone will not get us to
  `>200 tok/s`.

Public signals checked for this refresh:

- Localmaxxing still shows one approved public exact-model B70/vLLM row for
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`: our 4x B70, 32K,
  quality-gated `99.428 tok/s` baseline. No public exact-model faster row was
  found in the filtered result set.
- Intel's grouped-GEMM XPU issue remains aligned with our approach: MoE decode
  routing is skewed, and grouped-GEMM tuning needs realistic route
  distributions rather than only synthetic uniform shapes:
  <https://github.com/intel/intel-xpu-backend-for-triton/issues/6389>.
- Public B70 benchmark data from PMZFX reports Qwen3.6-35B-A3B MoE behavior
  across llama.cpp SYCL/Vulkan and dual-card runs, reinforcing two lessons:
  B70 can run this model family well, and naive multi-GPU layer splitting is
  not proof of better c1 latency:
  <https://github.com/PMZFX/intel-arc-pro-b70-benchmarks>.
- Xe-Forge is relevant as a process idea, not as a drop-in solution: start from
  a correct Triton/SYCL kernel, then run a hardware-in-the-loop optimization
  loop with correctness and performance checks on Intel GPU:
  <https://arxiv.org/html/2605.26118v1>.

## Things To Try Next

1. **Run the grouped-GEMM M-scaling timing screen.**
   Stop the accepted backend, run the new M-scaling script on `xpu:0`, restore
   the accepted backend, then run provenance and p512/o128 speed sanity. The
   decision table is simple: strong TOPS scaling means aggregate/persistent
   work is worth building; flat TOPS means go lower into kernel/layout/counter
   proof first.

2. **Build a one-layer exact MoE replay with hotset and cold fallback.**
   Use layer `9` and layer `20` route windows first. Compare current
   `xpu_fused_moe`, preallocated scratch, current grouped GEMM, top-64
   tile-native hotset, and cold fallback in the same harness. Promotion requires
   numeric equivalence against the current Quark W8A8 path.

3. **Turn M-scaling into a kernel policy search.**
   For the same route windows, compare grouped GEMM, per-expert GEMM,
   batch-packed GEMM, persistent grouped GEMM, and one-dispatch hot/cold queue.
   Record effective TOPS, lower/upper bandwidth bounds, active experts, and
   launch count per case.

4. **Get real DPAS/XMX counters or a credible substitute.**
   The current roofline is timing-derived. The next proof should install or
   enable `unitrace`, VTune, `oneprof`, or MEI telemetry access, then report
   whether the hot W8A8 kernels actually issue high-occupancy DPAS/XMX INT8.
   If privileged counters remain blocked, disassemble the generated kernels and
   at least prove the intended op path.

5. **Transplant, do not migrate, a newer persistent-MoE kernel.**
   Watch Intel `vllm-xpu-kernels`, `llm-scaler-vllm`, and Triton-XPU branches.
   When a persistent W8A8 MoE kernel appears, isolate it behind the route-replay
   harness before changing the accepted server stack.

6. **Prototype a static low-context latency lane.**
   Keep the TP4/32K service as the stable production lane, but test a fixed
   c1 sidecar with lower context, preallocated metadata, certified graph cache,
   and strict admission control. This is not a model-quality compromise; it is
   a serving-shape specialization.

7. **Run a TP/EP/hotset simulation with measured latencies.**
   Update the route-parallelism simulator with measured GEMM and allreduce
   costs, not only movement proxies. This will tell us whether TP2+EP2,
   replicated attention plus sharded experts, or hot-expert replication can
   beat TP4 c1 latency.

8. **Add a BF16/logit-rank differential gate for kernel experiments.**
   Exact token sentinels are necessary but not enough for a deep kernel rewrite.
   Add a small BF16 fallback/logit-rank suite and route-replay numeric checks so
   a candidate cannot silently distort nearby probabilities.

9. **Make reliability a first-class perf metric.**
   Every maintenance-window experiment should record device-lost state,
   recovery snapshot, provenance result, restore time, and post-restore speed.
   A fast kernel that raises reset rate is not production progress.

10. **Prepare the upstreamable packet in parallel.**
    Bundle one route window, minimal weights/scales slice, current timing,
    roofline, M-scaling result, and expected outputs. The packet should be
    small enough that Intel/vLLM maintainers can run it without the full
    production service.

## Bigger, Bolder Ideas Added

1. **Route-window generated MoE kernels.**
   Generate layer/window-specialized kernels from captured route shapes. Keep
   the math exact, but specialize scheduling, tile size, and active expert
   layout to the observed distribution. This is bold because it trades generic
   runtime flexibility for c1 latency, but it fits the static-lane idea.

2. **Resident expert-worker runtime.**
   Instead of launching independent MoE substeps, keep a persistent expert
   worker pool alive on each B70. Workers pull routed rows, run W8A8 GEMM1,
   fused activation/quant, W8A8 GEMM2, and scatter without returning to Python
   or host scheduling between substeps.

3. **Graph-resident decode transaction engine.**
   Build the verifier/speculation path as an in-graph transaction system:
   versioned KV/GDN state, candidate token scoring by the current model,
   accept/rollback buffers, and exact sentinel proof. This is the highest-upside
   path if pure kernel work cannot halve model-forward time.

4. **Automatic Intel-kernel optimization loop.**
   Use the route-replay harness as the evaluator for a Xe-Forge-style loop:
   candidate Triton/SYCL kernels are generated or transformed, compiled, checked
   against exact outputs, benchmarked, and kept only if they improve the
   route-exact fixture.

5. **Whole-block fusion experiment.**
   If MoE-only wins are insufficient, prototype a one-layer whole-block replay
   that fuses or graph-coalesces Gated DeltaNet/attention, MoE, residuals, and
   metadata updates. The aim is to remove barriers around the model-forward
   graph, not change model math.

6. **Hardware topology sidecar.**
   Try the same accepted model on alternative physical topologies if available:
   all four cards, best two cards, one card with lower context, and independent
   replicas. Public B70 data suggests extra cards often improve aggregate
   throughput more than c1 latency; production may need topology-aware routing.

7. **Tile-native hotset cache as a first-class model artifact.**
   Store packed hot expert tensors beside the model with source tensor hashes,
   layer/source coverage, route-class labels, and equivalence checks. Treat it
   like a compiled graph cache: reproducible, certified, and invalidated when
   weights or runtime kernels change.

8. **C1 latency leaderboard packet.**
   Once a material improvement clears `105` or `120 tok/s`, publish a refreshed
   Localmaxxing row with provenance, quality gates, command, and notes. Save
   `>200 tok/s` for a genuinely new class of result, not measurement noise.

9. **Production dual-policy scheduler.**
   Serve the same model through two exact lanes: a stable capacity lane and a
   latency lane with fixed shapes. Route by prompt length, requested output,
   temperature policy, and concurrency. This can improve real user experience
   before a single universal backend exists.

10. **B70 failure-forensics matrix.**
    Systematically vary kernel/KMD, compute-runtime, oneAPI, PyTorch,
    oneCCL/OFI, and graph settings with a tiny accepted smoke. The output is a
    known-good production stack and a list of combinations that increase
    device-lost risk.

## 2026-06-12 M-Scaling Timing Result

Artifacts:

- Broad M-scaling timing:
  `data/qwen36-quark-int8-tp4-grouped-gemm-mscaling-timing-20260612am.json`
  and `.md`.
- Small-M timing:
  `data/qwen36-quark-int8-tp4-grouped-gemm-smallm-timing-20260612an.json`
  and `.md`.
- First restore after broad M-scaling:
  - Log:
    `data/qwen36-quark-int8-tp4-accepted-restored-after-mscaling-20260612am.log`.
  - Provenance:
    `data/qwen36-quark-int8-tp4-accepted-provenance-after-mscaling-20260612am.json`.
  - Speed:
    `data/qwen36-quark-int8-tp4-accepted-restored-after-mscaling-speed-p512o128-20260612am.json`.
- Final restore after small-M screen:
  - Log:
    `data/qwen36-quark-int8-tp4-accepted-restored-after-smallm-20260612an.log`.
  - Provenance:
    `data/qwen36-quark-int8-tp4-accepted-provenance-after-smallm-20260612an.json`.
  - Speed:
    `data/qwen36-quark-int8-tp4-accepted-restored-after-smallm-speed-p512o128-20260612an.json`.

Broad M-scaling result:

| stage | M | mean us | TOPS |
|---|---:|---:|---:|
| `gemm1` | 32 | 111.628 | 0.309 |
| `gemm1` | 64 | 112.938 | 0.605 |
| `gemm1` | 128 | 107.196 | 1.281 |
| `gemm1` | 256 | 102.215 | 2.667 |
| `gemm1` | 512 | 93.805 | 5.731 |
| `gemm1` | 1024 | 106.699 | 10.272 |
| `gemm2` | 32 | 110.462 | 0.154 |
| `gemm2` | 64 | 108.577 | 0.313 |
| `gemm2` | 128 | 101.541 | 0.671 |
| `gemm2` | 256 | 101.566 | 1.340 |
| `gemm2` | 512 | 101.423 | 2.682 |
| `gemm2` | 1024 | 105.324 | 5.193 |

Small-M result:

| stage | M | mean us | TOPS |
|---|---:|---:|---:|
| `gemm1` | 8 | 100.506 | 0.086 |
| `gemm1` | 16 | 93.443 | 0.180 |
| `gemm1` | 24 | 92.881 | 0.271 |
| `gemm1` | 32 | 92.897 | 0.361 |
| `gemm1` | 64 | 93.287 | 0.720 |
| `gemm1` | 128 | 93.285 | 1.439 |
| `gemm2` | 8 | 93.032 | 0.045 |
| `gemm2` | 16 | 93.586 | 0.090 |
| `gemm2` | 24 | 93.702 | 0.134 |
| `gemm2` | 32 | 93.099 | 0.180 |
| `gemm2` | 64 | 93.438 | 0.359 |
| `gemm2` | 128 | 93.972 | 0.715 |

Restoration evidence:

- Both benchmark windows exited cleanly. No device-lost event was observed.
- After the broad M-scaling screen, the accepted backend restored to `/health`
  in `57 s`, provenance passed all exact sentinels, and p512/o128 measured
  `99.604 tok/s` corrected with `9.962 ms/token` decode.
- After the small-M screen, the accepted backend restored to `/health` in
  `57 s`, provenance passed all exact sentinels, and p512/o128 measured
  `99.845 tok/s` corrected with `9.941 ms/token` decode.

Interpretation:

- The XPU grouped-GEMM path has a near-fixed latency floor around
  `93-110 us` for these Qwen3.6 W8A8 MoE shapes.
- Effective TOPS rises roughly with `M` because the launch/kernel floor is
  being amortized. `gemm1` rises from `0.086 TOPS` at `M=8` to `10.272 TOPS`
  at `M=1024`; `gemm2` rises from `0.045 TOPS` to `5.193 TOPS`.
- This explains why hotrep split launches lost: reducing rows per rank makes
  the fixed cost dominate harder.
- For single-user decode, the model pays this small-M floor repeatedly across
  MoE layers. A plain route reshuffle or hot/cold two-launch design will not
  halve latency.
- The no-quality-loss speed path is now narrower:
  1. collapse the fixed MoE cost with persistent/fused expert workers,
  2. make one dispatch handle hotset plus cold fallback without extra launches,
  3. or use exact target-verified speculation so each expensive target forward
     accepts multiple tokens and moves the workload into larger effective `M`.

Next implementation implication:

- Start with a one-layer persistent/fused MoE replay, not another endpoint flag
  sweep.
- The first target should prove it can beat the `~93 us` per-GEMM floor on
  `M=8,16,32` while matching `xpu_fused_moe` numerically.
- If no small-M kernel beats the floor, shift effort to resident-state
  target-verified speculation because larger effective `M` clearly improves
  arithmetic utilization.

## 2026-06-12 Fusion Target Budget And Bigger Bets

Artifacts:

- Budget script:
  `scripts/qwen36-moe-fusion-target-budget.py`.
- Budget report:
  `data/qwen36-quark-int8-moe-fusion-target-budget-20260612ao.md`
  and `.json`.

Budget result:

- Current accepted endpoint decode is `9.941 ms/token`, or `99.845 tok/s`
  corrected after the first streamed text chunk.
- Model-forward-only timing is `8.438 ms/token`, leaving an estimated
  `1.502 ms/token` outside the model-forward bucket.
- A `200 tok/s` c1 target requires `5.000 ms/token` decode.
- If outside-forward overhead is unchanged, the model-forward bucket must save
  `4.941 ms/token`.
- Spread across `40` MoE layers, that means `123.514 us/layer` saved.
- The route-exact primary row replay averages `283.842 us/layer` for current
  `xpu_fused_moe`.
- The exact preallocated staged lower bound averages `214.179 us/layer`, which
  would estimate only `139.781 tok/s` if it transferred perfectly to the
  endpoint.
- The next non-speculative layerlet must therefore reach about
  `160.328 us/layer` or better with exact numeric parity.
- Two independent small-M grouped GEMM dispatches are already `193.538 us`, so
  any viable non-speculative path needs a one-dispatch or persistent layerlet.

External scan:

- Localmaxxing public results currently show our Qwen3.6 W8A8 INT8 B70 row as
  the top B70/Qwen single-stream row visible for this exact model family:
  `~99.77 tok/s`, `76.53 ms` TTFT, 32K context, 4x B70.
  Query:
  `https://localmaxxing.com/api/leaderboard?hardwareName=Arc%20B70&modelFamily=qwen&limit=20`.
- The same scan shows a one-card B70 llama.cpp Qwen3.6 Q4 result around
  `70.35 tok/s`, and a separate 4-card mirrored setup reporting `68.8 tok/s`
  c1 with `338 tok/s` aggregate at higher batch. Those are not acceptable
  target replacements because they are Q4, but they are useful engine and
  topology clues.
- vLLM's generic INT8 W8A8 docs still primarily describe NVIDIA support, so
  our Intel path remains a local/upstream-edge XPU path rather than a mature
  generic INT8 route:
  `https://docs.vllm.ai/en/stable/features/quantization/int8/`.
- `vllm-xpu-kernels` release notes after `v0.1.8` mention MoE grouped-GEMM
  policy updates, small-K behavior, mixed prefill/decode attention routing, and
  FP8 KV cache paged-decode work:
  `https://github.com/vllm-project/vllm-xpu-kernels/releases`.
- Our serving venv reports `vllm 0.20.2rc1.dev2+gc51df4300.d20260523.xpu`,
  `PyTorch 2.11.0+xpu`, Level Zero driver `26.18.38308.1-0`, and
  `vllm-xpu-kernels 0.1.9.dev27+g28e1f5e`. The local kernels tree is at
  `28e1f5e remove transpose from ref_fused_moe (#360)`, after the visible
  grouped-GEMM commits `#333` and `#340`, but the tree is dirty with our local
  experiments.
- The local oneDNN third-party tree documents experimental grouped memory and
  grouped GEMM for MoE workloads behind
  `ONEDNN_EXPERIMENTAL_GROUPED_MEMORY`. This is not a direct fix, but it is a
  candidate one-layer replay backend.
- A current Qwen3.6 W8A8 issue in `llm-compressor` confirms that Qwen3.6 MoE
  W8A8 still needs architecture-specific handling for fused expert tensors and
  hybrid attention:
  `https://github.com/vllm-project/llm-compressor/issues/2787`.
- The Event Tensor / dynamic megakernel paper is a useful north star for our
  specific failure mode: conventional kernel and graph boundaries are the
  bottleneck, and MoE routing creates data-dependent fine-grained tasks:
  `https://arxiv.org/html/2604.13327v2`.

Bigger bets to keep in the queue:

1. **One-dispatch W8A8 MoE layerlet.**
   Build a one-layer XPU replay kernel that fuses route/remap, quant1, GEMM1,
   activation, quant2, GEMM2, and gather under one dispatch boundary. Promotion
   gate: exact parity to `xpu_fused_moe` and `<160 us/layer` on rows=`1`.

2. **Persistent resident expert worker.**
   Keep a small set of workgroups resident across decode steps and feed them
   route windows from device memory. This is harder than a normal custom op, but
   it attacks the measured fixed `93-110 us` launch/kernel floor directly.

3. **Event-Tensor-style MoE scheduler for Xe.**
   Prototype a small device-side task scheduler for routed expert tiles: top-k
   writes counts/events, expert GEMM tiles trigger as soon as rows are ready,
   and gather consumes tile completions without returning to host/PyTorch
   between phases. Treat it as a research branch, not a quick patch.

4. **oneDNN grouped-GEMM replay bakeoff.**
   Build a narrow route-replay harness using oneDNN grouped memory/matmul for
   the exact Qwen3.6 W8A8 shapes. If oneDNN's grouped path beats the current
   small-M floor, use it as a reference or a replacement backend for MoE
   layerlets.

5. **Shape-generated route-window kernels.**
   Capture route histograms over real prompts, identify repeated active-expert
   windows, and generate AOT kernels for the common buckets. Use current generic
   `xpu_fused_moe` only for cold fallback. This preserves quality because the
   math stays exact; only the schedule changes.

6. **TP2 latency lane plus 2x replica capacity lane.**
   Revisit topology with the exact INT8 model: if TP2 fits with the required
   context, it may reduce collective overhead and raise small-M occupancy versus
   TP4. If not, record the memory cliff and keep TP4 for the production lane.

7. **Strict target-verified speculation V2.**
   Stop trying to let speculative mode mutate verifier inputs. Instead create a
   shadow verifier bucket or sidecar that writes draft KV into temporary slots
   and commits only tokens accepted by the target. This is no-quality-loss by
   construction and can amortize the target forward across multiple accepted
   tokens.

8. **Micro-drafter trained on Qwen3.6 trace data.**
   If exact verifier plumbing works, train or distill a tiny B70-friendly
   drafter on Qwen3.6 traces. The drafter can be lower quality because the
   target verifies every accepted token; the quality risk is only in latency and
   stability, not final output correctness.

9. **Whole-token Level Zero command-list runner.**
   For a static c1 decode lane, bypass more Python/vLLM scheduling overhead by
   prebuilding a Level Zero command-list sequence for the fixed decode shape.
   Use it first as an offline model-forward parity harness, not as the public
   endpoint.

10. **Hardware-counter proof before more kernel tuning.**
    Get `unitrace`, VTune, or an equivalent metric path working with MEI/PMU
    access so we can measure XMX/DPAS occupancy and memory pressure directly.
    Timing-derived TOPS already says underfilled small-M, but counters will
    tell us whether the next bottleneck is dispatch, DPAS issue, memory layout,
    or synchronization.

11. **Engine-mining without quantization compromise.**
    Mine llama.cpp SYCL/Vulkan, OpenVINO GenAI, oneDNN, and custom ESIMD kernels
    for scheduling ideas, but do not switch the production target to Q4 or INT4.
    Any borrowed implementation must reproduce the exact W8A8 target outputs.

12. **Upstreamable B70/Qwen3.6 perf packet.**
    Package the route replay, small-M floor, target budget, and exact parity
    checks into a minimal issue/PR-ready repro for `vllm-xpu-kernels`. This may
    attract kernel maintainer attention and gives us a clean artifact even if we
    carry a local patch first.

## 2026-06-12 Fused SiLU+Quant Gate And Fresh Bigger Bets

Artifacts:

- Baseline route replay:
  `data/qwen36-quark-int8-moe-routecapture6-layer9-baseline-gate-20260612ap.md`
  and `.json`.
- Fused SiLU+quant candidate replay:
  `data/qwen36-quark-int8-moe-routecapture6-layer9-fused-siluq-gate-20260612ap.md`
  and `.json`.
- Restored accepted endpoint log:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-siluqgate-20260612ap.log`.
- Restored accepted endpoint provenance:
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-siluqgate-20260612ap.json`.

Result:

- The route-gate fixture uses layer `9`, routecapture6 rank-0 exact-ID routes,
  rows=`1`, starts `0:64:4`, `30` timed iterations, and `5` warmup iterations.
- Baseline current path is exact against `xpu_fused_moe`: max diff `0.000`.
  Its mean `xpu_fused_moe` time is `283.098 us/layer`; preallocated staged
  lower-bound mean is `212.792 us/layer`.
- The fused SiLU+quant candidate is not exact: manual staged and preallocated
  staged paths both show max abs diff `0.750` versus `xpu_fused_moe`.
- Even ignoring the exactness failure, the candidate only moves mean
  `xpu_fused_moe` time to `272.862 us/layer`, far above the `~160 us/layer`
  target needed for a plausible non-speculative `200 tok/s` c1 lane.
- Decision: reject the fused SiLU+quant candidate for the no-quality-loss path.
  Keep any future activation/quant fusion behind strict bit/token parity and
  treat it as a small component cleanup, not the main speed plan.
- After the one-card route replay window, the accepted TP4 endpoint was
  restored on `127.0.0.1:18080`. Provenance passed exact sentinels and parsed
  the expected accepted graph cache root. `xpu-smi ps` showed one TP worker
  owning each B70 with about `32.76 GB` allocated per card and reported
  available KV cache memory in the log is `20.67 GiB`.
- Fresh Localmaxxing exact-model query still shows the approved public row at
  `99.428 tok/s` for this exact model/hardware/engine setup. Do not post the
  tiny `99.728 tok/s` local recovery datapoint as a public win; reserve public
  updates for a material threshold such as `105`, `120`, or `200 tok/s`, or for
  a clearly useful reproducibility packet.

Immediate things to try next:

1. **One-dispatch MoE parity prototype.**
   Stop optimizing individual activation/quant fragments in isolation. Build a
   one-dispatch replay for the full rows=`1` layer-9 MoE path and require exact
   parity plus `<160 us/layer`.

2. **Exact activation/quant out-variant only after parity root-cause.**
   The fused candidate drift means rounding, scale reuse, or BF16/FP32 ordering
   changed. If this path is revisited, first write a tiny scalar/reference
   fixture that proves identical SiLU, quant scale, clamp, and rounding for
   every activation element before timing.

3. **Whole-token command timeline.**
   Use Level Zero tracing or another command-stream view to count kernel
   launches, barriers, host waits, memory copies, and collective launches for
   one accepted decode token. The route replay says fixed dispatch cost is
   likely the bottleneck; the command stream should quantify it.

4. **Hardware-counter access path.**
   Get `unitrace`, VTune, or another XMX/DPAS metric path working with the
   current driver stack. The timing-derived TOPS are too low, but counters are
   needed to decide whether the limiting factor is DPAS issue, occupancy,
   memory layout, or synchronization.

5. **Upstream route-exact repro packet.**
   Package the layer-9 route-gate baseline, failed fused SiLU+quant candidate,
   M-scaling floor, and target budget into a minimal `vllm-xpu-kernels`
   maintainer packet. The useful artifact is a reproducible B70 small-M MoE
   benchmark with exactness gates, not just a throughput complaint.

Fresh bigger ideas to keep on the board:

1. **Resident transactional verifier lane.**
   Build a target-verifier path that versions KV, GDN/Mamba state, sampler
   metadata, and request counters. Draft tokens run in temporary state; only
   target-accepted tokens commit. This is still the cleanest quality-preserving
   route to `>200 tok/s` if a proposer can keep acceptance high.

2. **Device-side routed-expert work queue.**
   Treat Qwen3.6 MoE decode as a dynamic task problem. A small resident device
   scheduler can consume top-k route rows, issue expert tiles as they become
   ready, and gather outputs without round-tripping through host/PyTorch phase
   boundaries.

3. **Tile-native expert cache with certified manifests.**
   Prepack expert weights into the fastest B70/XMX layout at model load time,
   store checksums and layout metadata, and reuse that packed asset across
   vLLM, oneDNN, or a custom layerlet. This spends VRAM/disk to remove runtime
   layout friction without changing model quality.

4. **Static c1 decode appliance beside vLLM.**
   Prototype a fixed-shape single-request lane that bypasses dynamic scheduling:
   preallocated request state, prebuilt graph or command lists, fixed decode
   buckets, and certified graph cache. Keep vLLM TP4 as the general 32K lane;
   route latency-sensitive c1 traffic to the appliance only after quality proof.

5. **Hybrid TP/EP with hot-expert replication.**
   Use captured route windows to simulate TP4, TP2, EP4, and partial hot-expert
   replication. Implement only if the byte model predicts less communication
   and less small-M underfill than today's TP4 path.

6. **Automated kernel-branch archaeology.**
   Build a route-replay CI script that can bisect `vllm-xpu-kernels`,
   intel-xpu-backend-for-triton, oneDNN grouped-GEMM changes, and local patches
   against the same exactness/timing budget. This lets us mine upstream work
   without accidentally taking quality regressions.

7. **Same-model micro-drafter trained from traces.**
   If the transactional verifier lane works, train a tiny same-tokenizer
   proposer on Qwen3.6 target traces. The draft model can be fast and imperfect
   because the target still verifies every committed token.

8. **Benchmark-plus-reliability publication packet.**
   When a real threshold is crossed, post both speed and reliability: exact
   model ID, command, quality gates, provenance JSON, peak VRAM, single-request
   and aggregate throughput, uptime/soak result, and known failure modes. That
   is more valuable than a one-line tok/s leaderboard row.

## 2026-06-12 Fused Prologue Screen And Bigger Lanes

New route-exact prologue artifact:

- Script: `scripts/bench-qwen36-moe-prologue.py`.
- JSON:
  `data/qwen36-quark-int8-moe-prologue-layer9-routecapture6-20260612aq.json`.
- Markdown:
  `data/qwen36-quark-int8-moe-prologue-layer9-routecapture6-20260612aq.md`.

Result:

- The existing `torch.ops._moe_C.fused_moe_prologue` path exactly matched the
  current `rows_per_expert.zero_()+remap_hidden_states` route expansion on
  layer-9 routecapture6 rows=1 windows:
  `max_expand_abs_diff=0.0` and `max_rows_per_expert_diff=0`.
- Current zero+remap mean: `111.108 us`.
- Fused prologue mean: `106.637 us`.
- Mean component delta: `-4.471 us`.
- Decision: keep fused prologue as a correct building block for a
  one-dispatch or persistent MoE layerlet, but do not promote it as a standalone
  endpoint optimization. The measured win is real but too small to close the
  `~10 ms/token` to `<=5 ms/token` c1 target gap.

Restore/provenance:

- Accepted backend restored as
  `qwen36-tp4-accepted-restored-after-prologue-20260612aq`.
- Restore log:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-prologue-20260612aq.log`.
- Provenance guard:
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-prologue-20260612aq.json`.
- Guard result: all exact sentinels passed.
- Frontdoor status after restore: paused for remote generation, local bypass
  enabled, `0` active and `0` queued generations.

External refresh:

- Localmaxxing still shows only one approved exact-model B70/vLLM row for
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`: our existing
  `99.428 tok/s` c1 row. No public exact-model result currently suggests a
  simple config-only path to `>200 tok/s`.
- That keeps the priority order unchanged: first persistent/fused MoE and
  exact verifier-safe speculation, then production split-lane architecture.

New concrete items to try:

1. **Promote fused prologue into a route-replay layerlet, not the endpoint.**
   Wire `fused_moe_prologue` into a standalone layer replay that includes
   quant, both W8A8 grouped GEMMs, activation, second quant, gather, and
   top-k weighting. The gate is exact parity with `xpu_fused_moe` and a layer
   mean below the `~160 us` non-speculative budget.

2. **Add exact out-variants for quant and gather buffers.**
   The prologue component is now clean, but dynamic quant and gather still
   allocate/return tensors. Add exact out-variant APIs for the remaining small
   MoE buffers before attempting another fusion. The gate is byte-for-byte
   parity plus a route-replay timing win.

3. **Build a fixed-shape decode bundle for one bucket.**
   Compile one p512/o512 or p2k/o512 c1 lane with preallocated KV/GDN metadata,
   certified graph cache, fixed sampling, and no dynamic request scheduler
   churn. This is a truth-serum benchmark: if it does not move c1 speed, the
   kernel path dominates; if it does, production needs a split latency lane.

4. **Run a DPAS/XMX proof packet before more kernel speculation.**
   Use the best available Intel tooling on this host, or add a host-stack lane
   with VTune/unitrace if needed, to prove whether the W8A8 GEMMs are issuing
   the expected INT8 DPAS/XMX instructions at useful occupancy. If counters are
   poor, layout/kernel work outranks scheduler work.

5. **Generate route-aware AOT MoE kernels from captured windows.**
   Instead of a generic grouped-GEMM policy, emit a small set of route-window
   kernels for common layer/token patterns. Each kernel carries a route-shape
   manifest, tensor-hash provenance, and a fallback to the generic exact path.

6. **Prototype a transactional verifier sidecar inside vLLM state.**
   Fork request state, alias immutable KV pages, version mutable GDN/Mamba and
   scheduler metadata, run the current Quark W8A8 target as verifier, and commit
   only accepted draft tokens. This is still the cleanest no-quality-loss way
   to exceed `200 tok/s` if non-speculative MoE cannot halve token latency.

7. **Run a B70 host-stack stress matrix as a separate reliability lane.**
   Keep the accepted model and command fixed while varying only KMD/runtime,
   oneAPI, PyTorch, oneCCL, firmware, and PCIe placement. Measure device-lost
   rate, p512/o128 sentinel parity, and c1 speed. Do not mix this with model or
   kernel changes.

8. **Design production around two service classes if the static lane wins.**
   Keep the stable TP4/32K service for long context and aggregate throughput,
   but route low-latency c1 chat shapes to a certified static lane. This avoids
   sacrificing reliability or context length while still improving interactive
   speed.

9. **Prepare an upstreamable route-exact B70 packet.**
   Package the fused-prologue screen, grouped-GEMM M-scaling data, SiLU+quant
   rejection, routecapture windows, exact expected outputs, launch command, and
   provenance guards. The packet should let Intel/vLLM reproduce the small-M
   MoE floor and target the same bottleneck.

10. **Make quality validation multi-layered by default.**
    For every future speed candidate, run exact sentinel parity, prompt-class
    canaries, route-replay numeric parity, and a small BF16 differential/logit
    rank probe. Token sentinels are necessary, but the BF16/logit lane catches
    near-miss probability drift before it becomes production instability.

## 2026-06-12 Full-Layer Fused Prologue Staged Screen

Artifacts:

- Updated harness: `scripts/bench-qwen36-int8-moe-kernels.py`.
- JSON:
  `data/qwen36-quark-int8-moe-routecapture6-layer9-prologue-staged-20260612ar.json`.
- Markdown:
  `data/qwen36-quark-int8-moe-routecapture6-layer9-prologue-staged-20260612ar.md`.
- Restore log:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-prologuestaged-20260612as.log`.
- Provenance guard:
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-prologuestaged-20260612as.json`.

Result:

- The full-layer fused-prologue staged path is exact against current
  `xpu_fused_moe`: max abs diff `0.0`.
- Mean `xpu_fused_moe`: `288.237 us/layer`.
- Mean scratch `xpu_fused_moe`: `258.465 us/layer`.
- Mean exact manual preallocated staged: `216.361 us/layer`.
- Mean fused-prologue staged: `284.705 us/layer`.
- Restored accepted backend health passed after `64s`; provenance passed all
  exact sentinels; frontdoor remained paused with local bypass enabled and
  `0` active / `0` queued generations.

Decision:

- Do not wire the current exposed `fused_moe_prologue` path into the endpoint.
  It is exact, but it is not a meaningful full-layer speed win.
- Root cause: the prologue path emits `expert_first_token_offset`, while the
  exposed W8A8 grouped-GEMM op consumes `int32 rows_per_expert`. The required
  offset-to-count conversion and current glue erase the prologue-only substep
  win.
- The useful next branch is not another endpoint flag. It is one of:
  offset-native W8A8 grouped GEMM, exact quant/gather out-variant cleanup, or a
  larger one-dispatch/persistent MoE layerlet that lets prologue outputs feed
  downstream work without returning through today's Python/Torch ABI boundary.

Concrete next kernel ideas:

1. **Expose offset-native W8A8 grouped GEMM.**
   Add a W8A8 INT8 grouped-GEMM binding that consumes
   `expert_first_token_offset` directly, matching the lower-level grouped-GEMM
   scheduler shape. Gate it with route-replay exactness and compare it against
   both current `rows_per_expert` GEMM and the staged preallocated lower bound.

2. **Add an offset-to-count XPU helper only as a control.**
   A tiny helper that writes `int32 rows_per_expert` from offsets may recover
   some glue overhead, but it still leaves an extra operation. Use it as an ABI
   control, not as the main bet.

3. **Move quant/gather to out-variant APIs.**
   The staged path is still paying tensor-return allocation boundaries for
   dynamic quantization and gather. Exact out-variants are lower risk than
   arithmetic fusion and should be measured before another endpoint attempt.

4. **Keep the persistent/one-dispatch layerlet as the main non-speculative bet.**
   The full-layer fused-prologue result confirms that small standalone
   prologue savings are insufficient. The next plausible `>200 tok/s` path
   needs to remove multiple phase boundaries at once or amortize target forward
   work with exact verifier-safe speculation.

## 2026-06-12 Fresh Ideas After Offset-ABI Review

Scope:

- Keep the model fixed at
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`.
- Keep the quality bar fixed: no Qwen3.5, no 4-bit/AWQ substitute, no public
  row unless the current Quark W8A8 target verifies exact output.
- Treat public faster rows as architecture clues only. A fresh Localmaxxing
  query for `Qwen/Qwen3.6-35B-A3B` shows much faster public rows, but the top
  entries use different hardware and/or different fidelity classes such as
  MQ4-AWQ, NVFP4, Q4_K_M, speculative decoding, or MTP. They do not answer
  whether our B70 Quark W8A8 path should be faster without changing the model.
- The B70-specific filtered query still has our 4x B70 Quark W8A8 vLLM row at
  the top of visible Arc Pro B70 results for this family, with the closest B70
  comparables being llama.cpp Q4 variants. This supports publishing only
  material future wins, not tiny recovery refreshes.

External signals folded into this refresh:

- Localmaxxing model-family leaderboard:
  `https://localmaxxing.com/api/leaderboard?hfId=Qwen%2FQwen3.6-35B-A3B&limit=10`.
- Localmaxxing Arc Pro B70 filtered rows:
  `https://localmaxxing.com/api/leaderboard?hfId=Qwen%2FQwen3.6-35B-A3B&hardwareName=Arc%20Pro%20B70&limit=20`.
- vLLM/XPU B580 tuning question:
  `https://github.com/vllm-project/vllm/issues/35638`.
- Intel Triton-XPU grouped-GEMM performance epic:
  `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`.
- oneDNN grouped-memory grouped-GEMM documentation:
  `https://uxlfoundation.github.io/oneDNN/dev_guide_matmul.html#grouped-gemm-support`.
- PyTorch persistent grouped-GEMM writeup:
  `https://pytorch.org/blog/accelerating-moes-with-a-triton-persistent-cache-aware-grouped-gemm-kernel/`.
- vLLM XPU support matrix:
  `https://docs.vllm.ai/en/stable/models/hardware_supported_models/xpu/`.

New concrete things to try:

1. **Offset-native W8A8 grouped-GEMM prototype, but measure the loop.**
   The local `vllm-xpu-kernels` W8A8 grouped-GEMM path currently takes
   `int32 rows_per_expert` and computes row/tile prefixes inside the kernel.
   A binding-only change is not enough; the prototype needs a launcher/kernel
   variant that consumes `expert_first_token_offset` directly. The first gate
   is not endpoint speed, but a route-replay comparison against:
   current rows-per-expert GEMM, offset-to-count helper, and exact staged lower
   bound. If the kernel still loops all experts per workgroup, this may save
   glue but not the `2x` target.

2. **oneDNN grouped-memory replay as a control, not a migration.**
   oneDNN's grouped memory uses offsets for variable group boundaries, matching
   the prologue output shape more naturally than the current W8A8 exposed ABI.
   Build a narrow replay harness for one layer/window with identical Quark W8A8
   math or a clearly labeled BF16/int8-control variant. If it is slower, close
   the lane. If it is faster, mine its scheduling/layout for the custom kernel.

3. **Route-window persistent worker proof before endpoint downtime.**
   The fastest plausible no-speculative path is still a persistent or
   one-dispatch layerlet. Start with one layer, one route window, and a fixed
   hot/cold queue. It must consume prologue offsets directly, run both W8A8
   GEMMs, preserve exact dynamic quant behavior, and scatter/gather without a
   Python/Torch allocation boundary.

4. **W8A8 kernel roofline packet.**
   Use unitrace, VTune, or the lowest-friction Intel counter path to capture
   DPAS/XMX utilization, occupancy, memory bandwidth, command count, and launch
   gaps for `gemm1_w8a8`, `gemm2_w8a8`, and the full MoE custom op. This tells
   us whether the current bottleneck is math utilization, small-M scheduling,
   memory/layout, or graph/host control overhead.

5. **Static c1 lane as a separate product shape.**
   Prototype a fixed-bucket c1 runner with certified graph cache, preallocated
   request/KV/GDN metadata, fixed sampling, and no dynamic scheduler churn. Do
   not let it replace general TP4/32K serving. Use it to answer whether a
   production split-lane architecture can improve interactive speed without
   weakening long-context reliability.

6. **Target-verified speculation as the parallel track.**
   Keep MTP/DFlash/ngram/tree proposers on the board only behind a resident
   target verifier. The key design is a transactional request-state fork:
   alias immutable KV, version mutable GDN/Mamba/scheduler metadata, score
   candidates with the current Quark W8A8 target, then commit only verified
   tokens. Without this, faster public speculative rows are not comparable.

7. **Current-model micro-drafter, not external-model drafter.**
   Train or fit a tiny same-tokenizer proposer from accepted Qwen3.6 traces,
   but never trust it directly. Its only role is to feed the target verifier.
   This may outperform generic n-gram on prompt classes where n-gram collapsed,
   while preserving the exact target output.

8. **Route-class autotuner.**
   Convert routecapture windows into classes: concentrated hotset, broad
   hotset, cold-heavy, repetitive, math/code/natural. For each class, choose a
   policy: full-table current GEMM, active-only table, hot-cache persistent
   queue, oneDNN control, or custom layerlet. This avoids another global policy
   that wins one layer/window and loses another.

9. **Host-stack reliability matrix with speed as a secondary metric.**
   The repeated device-lost class means a production path needs a separate
   reliability lane: fixed accepted command, fixed graph cache, fixed sentinel
   probes, then vary KMD/runtime/oneAPI/PyTorch/oneCCL/PCIe placement. A stack
   that is 3% faster but less stable is rejected for production.

10. **Upstreamable B70 performance packet.**
    Package the prologue exactness, prologue-staged negative, M-scaling gate,
    hotrep negative, route windows, W8A8 shapes, provenance guard, and the
    public B70 leaderboard context. The ask to Intel/vLLM should be precise:
    "B70 W8A8 small-M MoE decode needs offset-native/persistent grouped GEMM",
    not a broad "XPU is slow" report.

Bigger, bolder ideas to keep visible:

1. **Graph-resident decode loop.**
   Move the whole steady-state c1 decode step into a resident command graph or
   persistent loop: attention/GDN, routing, MoE, collectives, logits, sampling,
   and metadata update. Host only receives committed tokens. This is a large
   engineering branch, but it attacks launch gaps, metadata copies, and
   scheduler churn simultaneously.

2. **Verifier-owned commit protocol.**
   Redesign speculative decode around the verifier, not around the proposer.
   The verifier owns token-state, KV/GDN state, rollback logs, and streaming
   commit. Proposers become replaceable plugins. This could unify MTP, DFlash,
   n-gram, trace-trained drafter, and future hardware-assisted draft paths.

3. **MoE-only hybrid parallelism.**
   Keep attention replicated or TP-light, but route experts with EP/hot-rep
   semantics only where captured routes justify it. The simulator already
   showed hot64 replication can reduce movement pressure but not compute. Pair
   it with persistent/tile-native MoE before attempting any endpoint rewrite.

4. **Tile-native packed-weight artifact registry.**
   At model load or offline prep time, produce per-layer packed W8A8 expert
   artifacts for the fastest B70 layout. Store tensor hashes, tile policy,
   graph-cache compatibility, and replay parity. This turns expensive runtime
   layout work into a certified artifact like the graph cache.

5. **Latency-market production router.**
   Production may not be one backend. Keep general TP4/32K for long-context and
   capacity, add one or more low-context static lanes for c1 chat, and route by
   request shape. Aggregate throughput stays secondary to c1 speed, but this
   makes both measurable instead of forcing one universal compromise.

## 2026-06-12 Additional Bigger Bets After Offset Prototype

Current new local branch:

- A source prototype is in progress for
  `cutlass_grouped_gemm_w8a8_int8_offsets_interface` in local
  `vllm-xpu-kernels`. It adds an offset-native W8A8 grouped-GEMM route that
  accepts `expert_first_token_offset` directly from the fused prologue path.
- This is not yet a speed result. It needs a C++ build, op-presence check,
  route-replay exactness gate, and accepted-backend restore/provenance guard if
  the XPUs are disturbed.
- Expected upside is modest if the kernel still loops across all experts per
  workgroup. The real decision metric is whether offset-native routing removes
  enough glue to make the fused prologue path approach the exact preallocated
  staged lower bound. If it does not, move immediately to persistent/one-dispatch
  MoE rather than polishing the ABI.

Additional things to try:

1. **Offset-op build gate plus route-replay kill switch.**
   Build the offset-native W8A8 op in `vllm-xpu-kernels`, run only the
   routecapture6 layer-9 rows=1 exactness/perf replay, and reject it quickly if
   it cannot beat fused-prologue staged by a material margin. Keep this as a
   one-maintenance-window test, not a multi-day branch.

2. **Expert-loop removal variant.**
   If offset-native GEMM is exact but only a small win, inspect whether the
   kernel still pays a full-expert loop for empty experts. The next variant
   should consume a compact active-expert list plus offsets, so workgroups skip
   cold experts instead of merely seeing zero rows.

3. **Fused hotset plus compact-cold single dispatch.**
   The top-64 hotset floor model says a naive hot/cold split risks launch
   overhead. Try a single dispatch that has fast hot expert tables plus a
   compact cold fallback queue inside the same kernel or layerlet. That preserves
   exact weights while avoiding the two-launch tax.

4. **Route-class graph library.**
   Precompile a small set of graph/layerlet variants by route class:
   concentrated hotset, broad hotset, cold-heavy, repetitive, math/code, and
   natural-chat. At runtime, choose the cheapest exact variant from the current
   route histogram. This is more realistic than a global hot-expert layout.

5. **Layerlet code generator.**
   Generate C++/SYCL or Triton-XPU layerlet code from captured layer metadata:
   expert shapes, W8A8 scales, hotset table, offsets, top-k, and output gather.
   The generated artifact can be specialized per layer while still checking
   tensor hashes and exact replay parity.

6. **MoE microservice inside the process.**
   Treat MoE as a persistent device service with resident queues and buffers,
   called from vLLM through a narrow ABI. The service owns hotset packing,
   active-expert scheduling, W8A8 GEMMs, activation, down projection, and
   gather. vLLM sees the same tensor result, but the device side avoids repeated
   allocation and launch setup.

7. **Single-card and TP2 truth-serum runs.**
   Run controlled c1 probes on single-card or TP2 variants only if memory allows
   the accepted model posture. The goal is not production capacity; it is to
   quantify how much TP4 collectives and graph metadata hurt one-request
   latency. If TP2 c1 is materially faster, revisit production as split lanes
   instead of forcing TP4 to do everything.

8. **Token-step command-list capture.**
   Capture or synthesize one full accepted decode token as a Level Zero command
   list: metadata updates, GDN/attention, MoE, allreduces, logits, sampler, and
   output copy. Replay it as a fixed-shape artifact to separate raw kernel
   latency from vLLM scheduler/control latency.

9. **BF16 shadow differential on a tiny suite.**
   Keep Quark W8A8 as the production target, but periodically compare candidate
   kernels against BF16 fallback on short prompts for logit-rank and semantic
   drift. This is a guardrail for subtle arithmetic changes that pass current
   token sentinels but move probability mass.

10. **Speculative verifier escrow for bonus/reject state.**
    The earlier no-bonus diagnostics exposed how hard rollback is. Build an
    explicit verifier-owned escrow for candidate tokens, token IDs, block-table
    updates, GDN/Mamba state, and streaming output. This is the minimum viable
    substrate for safe MTP/DFlash/tree speculation.

11. **Self-draft from shallow target layers.**
    Instead of an external model, try a proposer that reuses early target-model
    layers or a small adapter trained from target traces. The final output still
    comes only from the full Quark verifier. This may preserve tokenizer/style
    alignment better than generic n-gram and avoids Qwen3.5 substitution.

12. **Prompt-shape admission control.**
    For production, define a latency lane that accepts only shapes with known
    certified graph/cache/provenance and route-class behavior. Everything else
    goes to the general TP4 lane. This is not a quality compromise; it is a
    scheduling/product decision that protects c1 latency.

13. **Upstream performance challenge packet.**
    Publish the smallest route-exact W8A8 MoE repro that shows the gap:
    current grouped GEMM, exact staged lower bound, prologue-staged negative,
    offset prototype result, hotset floor model, and DPAS/XMX counters. This is
    more likely to attract useful Intel/vLLM help than a full server log.

14. **Reliability soak tied to every speed result.**
    Any candidate that touches kernels, graph cache, timing, or metadata needs a
    soak recipe: repeated load, p512/o128 c1, c4 aggregate, provenance sentinels,
    `xpu-smi ps`, and device-lost count. A fast but fragile backend is not a
    production candidate.

## 2026-06-12 Offset GEMM Prototype Gate

What was tested:

- Prototype source patch captured at
  `patches/vllm-xpu-kernels-w8a8-offset-gemm-prototype-20260612.patch`.
- The first local rebuild used a oneAPI 2026 runtime and linked against
  `libsycl.so.9`; reject that artifact for the accepted vLLM runtime. The
  accepted-compatible rebuild used oneAPI 2025.3, linked against
  `libsycl.so.8`, imported cleanly, and passed a basic XPU sync check.
- Route-exact layer-9 routecapture6 rows=1 replay passed exact output parity
  against current `xpu_fused_moe` (`max_abs_diff=0.0`). The offset path is a
  real component win in microbench:
  - `fused_prologue_offset_gemm_total_us_mean`: `213.233 us`
  - `fused_prologue_staged_total_us_mean`: `285.787 us`
  - `preallocated_staged_total_us_mean`: `218.158 us`
  - `xpu_fused_moe_scratch_total_us_mean`: `256.611 us`
- Serving gate failed. The offset-built backend reached `/health`, but the
  first provenance request crashed the engine with
  `UR_RESULT_ERROR_DEVICE_LOST` at `block_table.copy_to_gpu(num_reqs)`, then
  printed `UR_RESULT_ERROR_OUT_OF_RESOURCES` during shutdown. Do not promote
  this endpoint. Crash log:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-offset-gemm-20260612af.log`.
- Live rollback is complete: pre-offset `_xpu_C`, grouped GEMM, and GDN helper
  libraries were restored; the offset op is absent from the live runtime; the
  accepted backend passed exact provenance sentinels after rollback in
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-offset-rollback-20260612ag.json`.

Immediate follow-ups from this gate:

1. **Microbench-only offset plugin.**
   Split the offset prototype out of the full serving library and load it only
   for route-replay tests. This isolates whether the device-lost failure comes
   from device-image size, registration, or the serving call path.

2. **Narrow offset ABI.**
   Rebuild a smaller variant that exposes only the new offset path and avoids
   broad template duplication or ABI churn around the existing count-based
   W8A8 op. If the narrower image serves, promote it through the standard
   quality ladder.

3. **Active-expert list, not just offsets.**
   Check whether the kernel still loops over all experts. If it does, add a
   compact active-expert list so rows=1 decode skips cold experts instead of
   paying an empty-expert loop.

4. **One-dispatch MoE layerlet.**
   The offset microbench nearly reaches the manual preallocated lower bound,
   but the end-to-end target still needs millisecond-level savings. Move beyond
   ABI cleanup toward a single dispatch or persistent layerlet that owns
   prologue, quant, grouped GEMM, activation, down projection, and gather.

5. **First-token metadata failure minimizer.**
   Build a tiny post-load first-completion repro around block-table and graph
   metadata copies. The repeated `block_table.copy_to_gpu` device-lost class is
   now a production blocker category, not just a one-off failure.

6. **Promotion ladder for every kernel candidate.**
   Require this order before any endpoint exposure: import and XPU sync,
   route-microbench exactness, isolated one-token model execution, provenance
   sentinels, 10-minute c1 soak, then c4 aggregate. The offset prototype passed
   only the first two stages.

Larger ideas added after this result:

1. **Device-image budget analysis.**
   Track `.so` size, generated device images, persistent-cache entries, and
   first-use compile behavior before and after each kernel addition. A "small"
   template change may still create a serving-risky XPU image.

2. **Counter-proven small-M DPAS packet.**
   Pair the route replay with XMX/DPAS counters, EU occupancy, memory
   bandwidth, and kernel-launch timing. If offset GEMM is still math-starved at
   rows=1, persistent scheduling is mandatory.

3. **Graph-resident metadata update.**
   Stop treating block-table/GDN metadata copies as fixed overhead. Prototype a
   graph-resident or dirty-copy update path with a stability soak before speed
   timing.

4. **Persistent routed-expert worker.**
   Keep a resident device worker per layer or per hotset that consumes compact
   route tasks and writes exact outputs. This attacks both launch overhead and
   empty-expert work, at the cost of a larger engineering branch.

5. **Target-verified speculation as the high-upside track.**
   If non-speculative MoE work cannot remove roughly `5 ms/token`, the likely
   path to `>200 tok/s` c1 is verifier-owned speculation. The target model must
   score and commit tokens; any drafter remains replaceable and untrusted.

Public context:

- The Localmaxxing Arc Pro B70/Qwen view currently shows our quality-gated
  W8A8 result `cmq9ifq0500b0r8012f27j1xl` at about `99.77 tok/s`, ahead of the
  prior exact-model row. No new result was submitted for this offset prototype
  because it is not serving-safe.
- Faster public B70 Qwen rows using Q4/llama.cpp or other lower-fidelity
  setups are useful architecture clues, not quality-equivalent targets for
  this INT8/Quark production lane.

## 2026-06-12 Fresh External Scan And Larger Bets

What was added after the latest backlog prompt:

- Localmaxxing public API nuance: the broad Arc Pro B70/Qwen family query shows
  `cmq9ifq0500b0r8012f27j1xl` at `99.7697 tok/s` for Qwen3.6-35B-A3B on
  4x B70, but the exact `hfId=nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
  filter still returns only `cmq8yhxvo001ipb0149aoa79o` at `99.4284 tok/s`.
  Treat `cmq9ifq...` as the best public B70/Qwen-family row from this machine,
  but keep exact-model provenance artifacts in our notes before calling it a
  separate exact-HF row.
- vLLM's public W8A8 INT8 docs still describe the official INT8 compute path in
  NVIDIA terms. This supports the current rule: our XPU/Quark route needs local
  route-exact and endpoint-level proof for every kernel change.
  `https://docs.vllm.ai/en/latest/features/quantization/llm_compressor/int8_w8a8/`
- Intel Extension for PyTorch release notes now call out vLLM/TGI, MoE, and
  Arc B-Series validation. This is a good source of host-stack and kernel-stack
  candidates, but not a reason to relax quality gates.
  `https://github.com/intel/intel-extension-for-pytorch/releases`
- Intel's `ai-containers` XPU notes mention core vLLM serving, online FP8,
  multi-GPU scaling, experimental expert parallelism, and validated MoE support.
  This should be tested as a clean stack A/B against our accepted command, not
  mixed into the current source tree during kernel iteration.
  `https://github.com/intel/ai-containers/blob/main/vllm/0.17.0-xpu.md`
- The public B70 TP fault report confirms the risk class we keep hitting:
  multi-card vLLM/XPU can fault around ProcessGroupXCCL, driver, firmware, and
  graph/metadata paths. Device-lost count belongs in every performance report.
  `https://github.com/vllm-project/vllm/issues/41663`
- Community B70 rows show aggregate throughput can be large while single-stream
  decode remains modest. That reinforces the production split-lane idea:
  capacity and c1 latency may need different backends or admission policies.

Concrete things to try next:

1. **Active-offset grouped GEMM gate.**
   Finish the compact active-expert offset op as a microbench-only path first.
   It should pass import, XPU sync, route-exact layer-9 replay, and compare
   against both the offset prototype and current `xpu_fused_moe`. Do not expose
   it to the endpoint unless it avoids the earlier device-lost class.

2. **Device-image size and first-use compile budget.**
   For each `vllm-xpu-kernels` change, record `.so` size, device image count if
   inspectable, import time, first XPU op time, and whether a trivial XPU sync
   survives. The offset prototype's microbench win plus serving failure means
   binary/device-image cost is now a first-class gate.

3. **Clean Intel container A/B on spare root or isolated env.**
   Reproduce the accepted command on Intel's newest XPU vLLM container or a
   clean matching source stack. Keep the same model, prompt, context, quality
   gates, and no speculation. This answers whether our local stack is missing a
   newer MoE/expert-parallel path.

4. **Route-exact expert-parallel simulator before implementation.**
   Use existing routecapture windows to simulate TP4, TP2+EP2, EP4,
   replicated attention with sharded experts, and hot-expert replication.
   Include allreduce/all-to-all bytes, worst-rank hot spots, and VRAM. This is
   the cheapest way to decide whether a parallelism rewrite can help c1.

5. **Graph-safe metadata-copy kill gate.**
   Build a tiny repro around the repeated `block_table.copy_to_gpu` and
   `num_accepted_tokens.gpu.fill_` failure class. The goal is a stable
   first-completion smoke that can be run after kernel rebuilds before a full
   endpoint provenance request.

6. **Small-M DPAS/XMX proof packet.**
   Run the route-replay grouped-GEMM shapes under the best available Intel
   counters. For each hot kernel, record whether it uses XMX/DPAS INT8,
   occupancy, memory bandwidth, launch count, and time. If DPAS use is weak,
   layout/repack work outranks scheduler tuning.

7. **Static c1 graph runner as a truth-serum target.**
   Prototype a fixed-shape decode runner for one accepted prompt/output bucket:
   resident block tables, resident KV/GDN metadata, no dynamic admission, fixed
   sampling, and certified graph cache. It does not need to be the production
   server; it tells us how much vLLM dynamic control flow costs.

8. **Two-card latency lane investigation.**
   A single B70 is too small for this full W8A8 model with comfortable KV, but
   a TP2 or TP2-plus-offload lane may reduce cross-card collective and metadata
   complexity. Run this only as a c1 truth-serum benchmark with the same exact
   output gates, not as a capacity replacement.

9. **Resident-state verifier service.**
   Keep speculation on the board, but make the verifier own commit/rollback:
   alias immutable KV, version mutable GDN/request state, score candidates with
   the current Quark W8A8 model, and commit only verified tokens. External
   refill verification is already proven insufficient.

10. **Shallow target self-drafting.**
    Test a same-model drafter that runs fewer layers or a small trace-trained
    adapter, but only behind the resident-state verifier. This is a bigger
    engineering bet than n-gram, but it may provide accepted tokens without
    changing the served model's quality.

11. **Persistent MoE device service.**
    Instead of adding one custom op at a time, prototype a process-local device
    service with persistent USM buffers, hot expert packed weights, and compact
    route queues. It can serve route-replay requests first, then one layer, then
    a static c1 lane.

12. **Upstream performance challenge packet.**
    Package layer-9 routecapture6, the offset-GEMM exactness artifact, the
    device-lost promotion failure, the live timing budget, and Localmaxxing
    context into a concise repro for Intel/vLLM. The ask should be specific:
    persistent or active-expert W8A8 MoE for B70, not a general complaint.

13. **Reliability score as a benchmark field.**
    Alongside tok/s, record restarts, device-lost count, health-only failures,
    first-generation failures, and provenance-sentinel pass rate. A fast row
    that cannot survive restore/provenance is not a usable production result.

14. **Quality shadow set beyond exact sentinels.**
    Keep exact token sentinels as the hard gate, but add periodic BF16/logit
    rank or prompt-logprob shadow checks for kernel work. This catches nearby
    distribution distortion that may not flip the short canary token.

## 2026-06-12 Active-Offset GEMM Gate

What changed:

- Added a compact-active-expert variant of the experimental W8A8 offset grouped
  GEMM. The route replay passes `expert_first_token_offset` plus sorted
  `active_expert_ids`, so the kernel can loop over active experts instead of
  scanning all `256` experts.
- Build gate passed for the narrow CMake targets:
  `_xpu_C` and `grouped_gemm_xe_2`, using oneAPI 2025.3. Build log:
  `data/vllm-xpu-kernels-active-offset-build-20260612ai.log`.
- Direct `build/temp` import registered both experimental ops, then the package
  libs were temporarily swapped only for the route-replay microbench. Accepted
  package libs were restored immediately after the benchmark; the restored
  package import shows both experimental ops absent again.
- Source patch artifact:
  `patches/vllm-xpu-kernels-w8a8-active-offset-gemm-prototype-20260612ai.patch`.

Route-exact benchmark:

- Command shape: layer `9`, routecapture6 rows=1, starts `0:64:4`,
  `30` iterations, `10` warmup, `--enable-offset-gemm`, and
  `--enable-active-offset-gemm`.
- Main artifacts:
  `data/qwen36-quark-int8-moe-routecapture6-layer9-active-offset-gemm-20260612ai.json`,
  `.md`, `.log`, and
  `data/qwen36-quark-int8-moe-routecapture6-layer9-active-offset-gemm-summary-20260612ai.json`.
- Exactness: all compared paths matched current `xpu_fused_moe` with
  `max_abs_diff=0.0`, including the active-offset path.
- Mean timings across the 16 route windows:
  - Current `xpu_fused_moe`: `304.448 us/layer`.
  - Scratch `xpu_fused_moe`: `267.360 us/layer`.
  - Exact preallocated staged: `226.882 us/layer`.
  - Fused-prologue staged: `302.865 us/layer`.
  - Fused-prologue offset GEMM: `225.162 us/layer`.
  - Fused-prologue active-offset GEMM: `225.911 us/layer`.

Decision:

- Reject the active-offset op as an endpoint candidate. It is exact and the
  build works, but the compact active-expert loop does not improve the plain
  offset path on the rows=1 routecapture6 screen; it is slightly slower on
  mean (`225.911 us` versus `225.162 us`).
- The result reinforces the prior conclusion: small ABI cleanup is not enough
  for the `>200 tok/s` c1 target. The non-speculative path needs a larger
  one-dispatch/persistent MoE layerlet, quant/gather out-variants, or a
  graph/static c1 lane. The high-upside alternative remains resident-state
  target-verified speculation.
- Do not submit a Localmaxxing row for this. It is not a serving-safe speed
  result and it does not beat the accepted endpoint baseline.

Restore proof:

- Accepted package libs were restored from
  `backup-20260612ai-pre-active-offset`.
- Accepted backend relaunched as
  `qwen36-tp4-accepted-restored-after-activeoffset-20260612aj`; `/health`
  returned `200` after `48s`.
- Provenance guard passed all exact sentinels:
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-activeoffset-20260612aj.json`.
- Short p512/o128 speed sanity passed:
  `100.028 tok/s` corrected after first chunk, `95.153 tok/s` e2e, and
  `9.923 ms/token` decode histogram in
  `data/qwen36-quark-int8-tp4-accepted-restored-after-activeoffset-speed-p512o128-20260612aj.json`.
- XPU/frontdoor snapshots:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-activeoffset-xpusmi-ps-20260612aj.txt`
  and
  `data/qwen36-quark-int8-tp4-accepted-restored-after-activeoffset-frontdoor-status-20260612aj.json`.

Next concrete direction:

1. **Stop adding variants to the current two-GEMM ABI unless a roofline packet
   shows obvious waste.**
   The offset and active-offset paths are exact but hover around
   `225 us/layer`, still well above the `~160 us/layer` non-speculative budget.

2. **Build a one-layer persistent/layerlet replay.**
   Fuse route/prologue, quant1, GEMM1, activation, quant2, GEMM2, and gather
   for one captured layer-9 window. It should target the `160 us/layer` budget
   directly rather than another `~225 us` staged variant.

3. **Add out-variants for quant and gather only if they feed the layerlet.**
   Standalone out-variants can reduce allocation noise, but they are unlikely
   to close the millisecond-level gap by themselves.

4. **Parallel track: resident-state verifier design.**
   Non-speculative MoE work may not produce a `2x` c1 win fast enough. The
   speculation track should now focus on a target-verifier transaction design,
   not external refill checks or unverified n-gram speed.

## 2026-06-12 Bigger Bets After External Scan

What the fresh scan added:

- Localmaxxing now shows the quality-gated 4x B70 Qwen-family/vLLM row at
  `99.7697 tok/s`, and the exact-HF
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` row at `99.4284 tok/s`.
  Snapshots:
  `data/localmaxxing-qwen-b70-vllm-leaderboard-20260612ak.json` and
  `data/localmaxxing-qwen36-35b-quark-int8-exacthf-20260612ak.json`.
- vLLM's public INT8 W8A8 docs still describe INT8 computation support in
  NVIDIA terms, while the XPU support table validates Intel Arc Pro B-series
  for BF16/dynamic-FP8/model families, not a finished XPU INT8 fast path. This
  matches the local finding that the missing piece is real XPU W8A8 MoE kernel
  plumbing, not just flags.
- Intel/ipex-llm advertises FlashMoE work for Qwen3MoE-class models on Arc.
  That is worth reading as a design oracle even if we keep the serving endpoint
  on the current vLLM stack.
- Public B70 material lists `608 GB/s` per-card memory bandwidth for Arc Pro
  B70 and the Intel AI-PC paper lists B580 at `456 GB/s` and `233 TOPS` INT8.
  Our current `~100 tok/s` c1 decode is therefore almost certainly losing
  time to launch/dispatch, Python/scheduler overhead, small-M utilization, TP
  communication, allocation/copy churn, or non-XMX W8A8 coverage rather than
  raw card limits alone.

Quality-preserving bigger bets:

1. **Static c1 fast lane beside vLLM.**
   Build a fixed-shape single-sequence decode runner for this exact model and
   context class. vLLM remains the public scheduler/frontdoor, but latency
   class `c1` requests can be handed to a persistent runner with stable buffers,
   fixed tensor shapes, and no dynamic batching/scheduler churn. This is the
   cleanest path to attack single-user latency without changing model math.

2. **Persistent MoE layerlet, not another helper op.**
   Generate one layer-9 replay first, then all MoE layers: route/prologue,
   quant1, GEMM1, activation, quant2, GEMM2, and gather in one resident
   command path. The local offset/active-offset experiments show that small
   ABI fixes plateau around `~225 us/layer`; a layerlet can remove the
   dispatch and intermediate-memory boundaries that those variants keep.

3. **Expert-parallel / hybrid MoE sharding simulation.**
   Run route-exact EP/TP simulation before coding it: keep dense/attention TP
   as needed, but shard MoE experts by card and move compact activations
   instead of full tensor-parallel reductions. If B70 PCIe/CCL costs are
   dominating c1, MoE-specific parallelism may beat blanket TP4 for decode.

4. **IPEX/FlashMoE design extraction.**
   Do a controlled smoke test or source read of Intel's FlashMoE path against
   Qwen3MoE shapes. The goal is not to swap to a lower-quality model or a
   different quant; it is to steal architecture: persistent expert packing,
   routing layout, fused activation, and small-M DPAS/XMX handling.

5. **Graph-resident decode loop.**
   Move from per-token graph fragments to a persistent command-list loop with
   device-side state for token id, KV offsets, route buffers, and logits. Host
   should submit "next token" work with minimal metadata updates. This is a
   bolder version of XPU graph capture aimed at removing the remaining
   per-token host tax.

6. **Tile-native packed-weight artifact.**
   Prepack the current INT8 weights and scales into DPAS/XMX-friendly tiles
   offline, with a reversible provenance manifest that proves numerical
   equivalence. This changes storage layout only, not weights or quantization,
   and could remove runtime packing/transpose penalties.

7. **Route-class graph library.**
   Capture route histograms per layer and prompt class, then prebuild a small
   library of hot graph variants. Use a guard to fall back to the generic path
   for rare expert patterns. The risk is variant explosion; the upside is
   static scheduling for common c1 paths.

8. **Target-verified speculative escrow.**
   Keep this as the largest no-quality-loss speed lever. A same-model verifier
   owns KV state and commits only tokens that exactly match the target model's
   next-token decisions. Drafts can come from n-gram, a shallow same-model
   drafter, or a trace-trained micro-drafter, but the frontdoor exposes only
   target-verified output.

9. **Shallow target self-drafter.**
   Train or derive a small drafter from this exact target's traces, then make
   it propose token bundles into the verifier escrow. This is bolder than
   n-gram but can still be quality-preserving if every committed token is
   target-verified.

10. **B70 roofline and stall packet.**
    Use Level Zero/VTune/oneAPI profiling to prove whether each hot kernel is
    XMX-bound, bandwidth-bound, launch-bound, or communication-bound. Stop
    guessing from wall-clock once the next kernel branch begins.

11. **Single-card and TP2 truth-serum runs.**
    For this current model, run constrained diagnostic versions that fit only a
    subset or use offload/short context if required. The point is not
    production; it is to isolate whether TP4 communication is the reason four
    cards do not scale c1 decode.

12. **Model-specific generated engine as a moonshot.**
    If vLLM integration keeps absorbing the wins, generate a bespoke
    Qwen3.6-35B-A3B INT8 decode engine and run it behind the existing
    OpenAI-compatible frontdoor. Treat vLLM as the reference and fallback, not
    necessarily the only executor.

13. **Production latency classes.**
    Split future serving into at least two executor classes: c1 low-latency
    fast lane with strict shape limits, and aggregate-throughput lane using
    normal vLLM batching. This lets us optimize single-user speed without
    degrading production batching behavior.

14. **Reliability-promoted performance.**
    Any larger win must carry the same promotion bundle: exact provenance
    sentinels, short prompt-class quality, long-context needle, restore proof,
    device-lost scan, and a 30-60 minute c1 soak before it can replace the
    accepted endpoint.

Near-term order:

1. Build the roofline/stall packet for accepted c1 decode and the layer-9
   route replay. This tells us whether the next branch should target XMX
   occupancy, memory movement, dispatch count, or TP communication.
2. Read or smoke-test IPEX/FlashMoE for Qwen3MoE shape handling and record
   exactly what can be ported into vLLM without changing model quality.
3. Prototype a one-layer persistent MoE layerlet with fixed routecapture6
   metadata. The pass/fail budget is still `~160 us/layer` for a plausible
   non-speculative `>200 tok/s` path.
4. In parallel, write the verifier-escrow design doc because non-speculative
   kernel work may not deliver a full `2x` alone.

## 2026-06-12 Quant-Out Scaffold And Bolder Ideas Refresh

What was added locally:

- A quant out-variant scaffold now exists in the dirty source trees and the
  route replay script knows how to use it when the patched `_xpu_C` artifact is
  present. Details and validation are in
  `notes/2026-06-12-qwen36-quant-out-scaffold.md`.
- This is not a serving result. It compiled, imported from the isolated build
  artifact, and registered the new ops, but it was not installed over the
  accepted endpoint and did not run an XPU timing benchmark while the production
  workers were live.
- The practical reason to keep it is layerlet plumbing: the current exact
  staged paths allocate `gemm1_a/gemm1_a_scales` and `gemm2_a/gemm2_a_scales`
  unless the quant op can write into caller-owned buffers.

Fresh public signals from the scan:

- The vLLM Intel Arc Pro B-series writeup explicitly calls out persistent MoE
  kernels, single-kernel persistent loops, dynamic balancing of compute groups,
  and reduced MoE scheduling gaps as the core Intel path for MoE performance:
  https://vllm.ai/blog/2025-11-11-intel-arc-pro-b
- Intel's `0.10.2-xpu` container notes say Qwen3-30B-A3B improved `2.6x` from
  persistent MoE GEMM and fused activation work, and also call out small-batch
  FP16/BF16 GEMM improvements:
  https://github.com/intel/ai-containers/blob/main/vllm/0.10.2-xpu.md
- vLLM's XPU support table validates Arc Pro B-series for Qwen3-30B-A3B in
  BF16 and dynamic FP8 paths, but that is still not the same as a finished,
  production-ready XPU W8A8 INT8 MoE fast path for this model:
  https://docs.vllm.ai/en/v0.18.0/models/hardware_supported_models/xpu/
- PMZFX's public B70 llama.cpp data reports Qwen 3.6 35B A3B at `54.7 t/s`
  for UD-Q4_K_M on one B70 and `36.5 t/s` for Q8_0 across two B70s. Those are
  not quality-equivalent to our current W8A8/vLLM target, but they reinforce
  that MoE can run much faster than dense models on B70 when the execution path
  is hardware-friendly:
  https://github.com/PMZFX/intel-arc-pro-b70-benchmarks
- A public 2x B70 vLLM benchmark reports `40.60 tok/s` single-stream and
  `996.67 tok/s` aggregate output at higher concurrency. The useful signal is
  the same split we see locally: aggregate throughput can look fine while
  c1 latency remains dominated by small-batch scheduling and kernel bubbles:
  https://www.reddit.com/r/LocalLLM/comments/1sfa0iw/2x_intel_arc_b70_benchmark/
- A current Localmaxxing query shows our exact HF row for
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` at about `99.428 tok/s` and a
  same-family Arc Pro B70 row at about `99.770 tok/s`. Do not post the
  quant-out scaffold as a result; it is not a benchmark win.

Bigger, bolder ideas worth keeping on the board:

1. **Persistent MoE worker per card.**
   Instead of launching per-layer helper kernels from Python/vLLM, create a
   resident XPU-side MoE service that owns route buffers, quant buffers, expert
   work queues, and output buffers for the static c1 shape. Host writes only
   minimal token/layer metadata. This is the direct local analog of Intel's
   persistent MoE direction.

2. **Generated Qwen3.6 INT8 layerlets.**
   Generate C++/SYCL for this exact model layout, layer shape, expert count,
   and W8A8 scale format. First target layer 9 routecapture6, then generate the
   40 MoE layerlets. The code generator can bake tile sizes, expert metadata,
   scratch offsets, and DPAS-friendly memory layouts.

3. **Expert-parallel decode lane.**
   Stop assuming TP4 is the right c1 shape. Simulate and then test an EP-like
   decode lane where experts are partitioned or hot experts replicated by
   card, and activations move only when the chosen experts require it. For MoE
   c1, moving compact activations may beat reducing full tensor shards.

4. **One-card or two-card latency replicas.**
   If TP4 communication is a hard c1 tax, use the four B70s as separate
   latency replicas for lower-concurrency production while keeping a TP4 lane
   for long context or aggregate throughput. This sacrifices per-request model
   placement efficiency only if quality/32k context can still fit.

5. **Offline DPAS/XMX tiled weight pack.**
   Convert the existing W8A8 weights and scales into a tile-native format once
   and record a provenance manifest. If runtime kernels are spending time on
   layout, transpose, or non-coalesced scale loads, a reversible pack artifact
   may unlock speed without changing quantization.

6. **Whole-token command graph.**
   Capture an entire c1 decode token as one graph/command-list bundle with
   static KV block metadata and scratch arenas, not just individual kernels.
   Route guards can select a small number of graph variants and fall back to
   the generic path for rare patterns.

7. **Target-model branch lookahead.**
   Use the target model itself to score a small tree of likely next tokens,
   then commit only the branch that exactly matches the standard target
   decision. This is more expensive than n-gram speculation but avoids external
   drafter quality drift.

8. **Trace-trained micro-drafter with hard verifier escrow.**
   Train a tiny local drafter from our target traces and let it propose bursts,
   but keep commit ownership with the target verifier. This can be quality
   preserving if the verifier is transactional and rejects mismatches before
   they reach the client.

9. **Static c1 appliance behind the OpenAI frontdoor.**
   Keep vLLM as the reference path and batching lane, but build a separate
   fixed-shape executor for single-user low-latency traffic. The frontdoor can
   route by request shape and load, with exact canaries deciding whether the
   appliance is enabled.

10. **Clean Intel container A/B on spare disk.**
    Reproduce the Intel validated host/container stack as closely as possible,
    then run the same route replay and c1 benchmark. This separates our source
    work from host-stack issues around kernel driver, oneAPI, oneCCL, and PCIe
    topology.

11. **Public upstream performance challenge packet.**
    Package one layer-9 routecapture fixture, exactness checks, timings, and
    B70 environment details so vLLM/Intel kernel owners can reproduce the
    `~225 us/layer` plateau. A well-scoped repro may attract better XPU kernel
    advice faster than private guessing.

Next ordering after this refresh:

1. Clean benchmark window for quant-out route replay. Keep it isolated and
   reject unless exact and faster.
2. Roofline/stall packet with Level Zero or VTune counters for accepted c1 and
   layer-9 replay.
3. One-layer persistent layerlet proof. Stop spending time on helper-op variants
   unless the roofline packet says the helper itself is the bottleneck.
4. Verifier escrow design doc, because exact speculation may be the only
   quality-preserving way to get a full `2x` if non-speculative kernels plateau.

## 2026-06-12 Quant-Out Gate Result

The quant-out replay did pass its narrow gate, but not the larger speed target:

- Isolated overlay route replay reported `quant_out_op_available=True`.
- Layer-9 routecapture6 rows=1 exactness passed with `max_abs_diff=0.0`.
- Mean exact preallocated staged timing improved to `207.237 us/layer`.
- Prior comparable exact staged runs were `216.361 us/layer` in the
  prologue-staged screen and `226.882 us/layer` in the active-offset gate.
- It remains above the `~168 us/layer` non-speculative budget, so it is not an
  endpoint candidate by itself.

Updated decision:

- Keep quant-out as scratch ABI cleanup.
- Stop treating helper-op variants as likely to reach `>200 tok/s` alone.
- Next performance branch should be either:
  - a one-dispatch/persistent layer-9 MoE layerlet using the scratch ABI, or
  - a roofline/stall packet proving that one remaining helper kernel is the
    dominant bottleneck before another helper branch is attempted.

## 2026-06-12 W8A8 Floor Gate And Bigger Bets

Artifact:
`notes/2026-06-12-qwen36-w8a8-floor-and-layerlet-decision.md`.

New local floor facts:

- Route-window 1 exact grouped GEMM is `113.845 us` for gemm1 and
  `112.371 us` for gemm2.
- Route-window 16 exact grouped GEMM is still only `112.596 us` for gemm1 and
  `114.068 us` for gemm2.
- Quant helper calls sit around `88-115 us` depending shape and noise.
- Two exact grouped GEMM dispatches alone cost about `226 us/layer`, already
  above the `~168 us/layer` non-speculative budget before the rest of MoE.

Decision update:

- The c1 bottleneck is now best treated as a launch/control/tiny-shape floor,
  not merely a missing scratch buffer or one bad helper op.
- Keep quant-out and scratch variants as plumbing for a larger fused layerlet.
  Do not spend another benchmark window on isolated helper variants unless a
  profiler proves that helper is the largest remaining wall.
- Next non-speculative work should collapse dispatch boundaries: persistent
  MoE worker, one-dispatch layerlet, oneDNN grouped-matmul fused-control path,
  or whole-token command graph.

Additional larger ideas to keep in the queue:

1. **oneDNN grouped-matmul fused control.**
   Build a route-exact layer-9 replay using oneDNN grouped matmul on XPU as a
   control path. Its grouped API supports source/weight scales, SiLU, binary
   multiply post-ops, and `DNNL_ARG_HINT_MAX_GROUP_SIZE`; that is close enough
   to Quark W8A8 MoE to test whether the current SYCL-TLA grouped path is the
   true floor.

2. **Single persistent MoE layer service, not one kernel per helper.**
   The service owns static scratch buffers and receives only route descriptors.
   It should perform route expansion, activation quant, two W8A8 GEMMs,
   SiLU/up-gate, top-k weighting, and gather in one resident loop. First gate:
   layer 9 exact parity. Second gate: `<=168 us/layer`.

3. **Route-class layerlet codegen with shape buckets.**
   Generate a small family of exact kernels for common c1 route classes rather
   than a fully generic MoE kernel. The routecapture fixtures already give the
   class distribution. Rare route classes fall back to accepted `xpu_fused_moe`.

4. **Whole-token command-list appliance.**
   Capture metadata update, attention, MoE, collective, logits, and sampling
   as a fixed c1 command list for common buckets. This attacks the same flat
   launch floor at a larger scope than the MoE layerlet.

5. **Exact self-lookahead lane.**
   Use spare card time to run target-model branch lookahead while the current
   token is streaming. This does not trust a lower-quality model; it commits
   only target-model decisions and can be disabled for non-greedy traffic.

6. **One-card/two-card latency truth-serum with reduced context.**
   If TP4 communication and small shards are part of the c1 wall, a smaller
   context latency lane might be faster even if it is worse for 32K capacity.
   Treat this as a routing option, not a replacement for the TP4 production
   lane.

7. **Public kernel challenge packet.**
   Publish a minimal routecapture6 layer-9 W8A8 fixture with exact expected
   outputs and the `112-114 us` grouped-GEMM floor. This is specific enough
   for Intel/vLLM kernel owners to reproduce and improve.

## 2026-06-12 Post-Floor Follow-up Ideas

This section records the next ideas after the W8A8 floor packet and the latest
public/API scan. It is notes-only; no endpoint change or new benchmark post is
implied.

Additional facts from the follow-up scan:

- The exact Localmaxxing filter still has one public row for
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` on 4x Arc Pro B70:
  `cmq8yhxvo001ipb0149aoa79o`, `99.428 tok/s`, c1, 32K context. The broader
  B70/Qwen/vLLM query still shows the same-family `Qwen/Qwen3.6-35B-A3B` row
  at `99.770 tok/s`, but that remains a context clue rather than a replacement
  for the exact model row.
- The installed `/opt/intel/oneapi/dnnl/2026.0` headers do not expose
  `dnnl_memory_desc_create_with_grouped_encoding` or
  `DNNL_ARG_HINT_MAX_GROUP_SIZE` in this host image. The vendored oneDNN tree
  under `vllm-xpu-kernels/third_party/oneDNN` does expose both. A true oneDNN
  grouped-matmul experiment therefore needs an isolated vendored-oneDNN build
  with grouped memory enabled, not a quick link against the installed oneAPI
  oneDNN package.
- Build probe result: a local `vllm-xpu-kernels` build with
  `DNNL_EXPERIMENTAL_GROUPED_MEMORY=TRUE` configured successfully against the
  vendored oneDNN tree using oneAPI compiler `2025.3`. The relevant grouped
  units compiled:
  `matmul/grouped_micro_gemm.cpp.o`, `matmul/ref_grouped_gemm.cpp.o`,
  `matmul_grouped_micro_gemm_kernel.cpp.o`, and
  `matmul_ref_grouped_gemm_kernel.cpp.o`. The full extension build was stopped
  once it moved into broad generated attention-kernel compilation, because the
  grouped-memory question was already answered and the full build is too wide
  for iteration. Artifacts:
  `patches/vllm-xpu-kernels-onednn-grouped-memory-build-probe-20260612.patch`
  and
  `data/qwen36-onednn-grouped-memory-build-probe-20260612.json`.
- oneDNN's public grouped-GEMM docs describe exactly the MoE shape we need:
  variable token rows across expert groups, per-token source scales,
  per-expert-column weight scales, and binary/SiLU post-op support:
  `https://uxlfoundation.github.io/oneDNN/dev_guide_matmul.html`.
- The oneDNN release notes say grouped memory and grouped matmul are
  experimental, require `ONEDNN_EXPERIMENTAL_GROUPED_MEMORY=ON`, and have an
  optimized Intel GPU implementation:
  `https://github.com/uxlfoundation/oneDNN/releases`.
- Intel's Triton-XPU grouped-GEMM issue reinforces that decode routing is
  skewed and long-tailed, so routecapture distributions need to remain the
  benchmark fixture:
  `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`.
- NVIDIA's cuDNN MoE grouped-matmul API uses `first_token_offset` plus optional
  gather/scatter metadata. That is a useful cross-vendor ABI hint: our
  offset-native route was the right abstraction even though the current XPU
  implementation did not clear the speed/stability gates:
  `https://docs.nvidia.com/deeplearning/cudnn/v1.23.0/operations/MoeGroupedMatmul.html`.
- Public B70 examples with high aggregate throughput are still mostly batch
  capacity evidence. The Level1Techs B70 example reports high 50-request
  aggregate throughput but also very large per-request latency. Keep c1 and
  aggregate scorecards separate:
  `https://forum.level1techs.com/t/intel-b70-launch-unboxed-and-tested/247873`.

Concrete things to try next:

1. **Vendored-oneDNN grouped-memory route replay.**
   The first build probe proves the vendored grouped-memory path is viable
   enough to continue. Before adding a serving op, narrow the build to
   oneDNN/matmul-only or `libdnnl.a` so iteration is not blocked by generated
   attention kernels. Then add one experimental op that consumes packed routed
   activations, expert offsets, W8A8 weights, per-token activation scales, and
   per-expert-column weight scales. Gate it on layer-9 routecapture6 exactness
   first, then compare against the current `112-114 us` per grouped-GEMM
   dispatch floor. Kill it quickly if primitive creation or grouped scales
   force host waits.

2. **Command-stream floor measurement.**
   Measure a single routecapture6 layer with equivalent math but progressively
   fewer launches: current helper chain, two grouped GEMM dispatches only, one
   no-op dispatch with the same tensor plumbing, and one empty command-list
   dispatch. The goal is to separate XMX math time from host/SYCL/Level-Zero
   command overhead.

3. **One-dispatch fake layerlet before real fusion.**
   Create a one-dispatch layerlet scaffold that copies through or computes a
   cheap checksum, but uses the final ABI: route offsets, scratch arena,
   quant-scale pointers, expert metadata, and output buffer. If the empty
   layerlet itself costs too much, a full fused kernel will not hit the
   `<=168 us/layer` gate.

4. **PCIe/topology and affinity c1 A/B.**
   Capture `lspci -vv`, NUMA locality, `xpu-smi topology`, BAR size, ASPM,
   IOMMU mode, worker CPU affinity, and CCL fabric settings beside one c1
   run. Then try one controlled topology/affinity profile. This is a speed and
   reliability lane because TP4 collective and metadata-copy behavior can be
   host-topology sensitive.

5. **Rank-local timing without synchronization pollution.**
   Re-run the decode timing path with rank-local event timing and a separate
   synchronized sanity mode. The current high-level histogram proves the
   `~10 ms/token` wall; the next useful profile must avoid adding enough sync
   overhead that it changes the answer.

6. **Layer-pair pipeline thought experiment with proof script.**
   Before writing kernels, model whether layer N MoE work on one card can
   overlap with attention/logits/metadata or collectives for adjacent layers
   without violating autoregressive dependencies. If the dependency graph says
   no, record that and avoid a dead-end pipeline branch.

7. **Exact prefix/static-state lane.**
   For common chat prompts, test whether certified static prefix state plus
   fixed decode buckets can remove scheduler and metadata churn while still
   preserving exact target output. This is separate from ordinary vLLM prefix
   caching, which has been disabled in the accepted graph lane.

8. **Hot-expert packed tile cache with runtime checksum.**
   Prepack only the route-dominant expert weights into the fastest XPU layout
   and store checksums plus source tensor hashes. The first test is offline
   route replay. Endpoint use requires exact output, cache provenance, and a
   fallback to source weights if a checksum or route class misses.

9. **Speculative branch arbiter as a service boundary.**
   Keep all proposer ideas behind one verifier-owned interface:
   `propose(tokens, state) -> candidates`, `verify(target_model) ->
   accepted_prefix`, `commit_or_rollback`. This lets us test n-gram, MTP,
   trace-trained proposers, and exact branch lookahead without rewriting the
   safety logic each time.

Bigger, bolder ideas worth keeping visible:

1. **B70 MoE micro-runtime.**
   A tiny device/host runtime dedicated to Qwen3.6 decode MoE: static scratch,
   resident expert tasks, exact Quark W8A8 math, route-class specialization,
   and no dynamic serving abstractions inside the hot loop. vLLM remains the
   server, but the MoE layer becomes a specialized appliance.

2. **Whole-model c1 runner as a truth-serum benchmark.**
   Build a non-serving executable for one fixed prompt bucket that loads the
   exact weights and runs decode with static arenas. If it is still near
   `100 tok/s`, kernels/collectives are the wall. If it is much faster, vLLM
   control flow and metadata are the wall.

3. **Expert-parallel latency lane with replicated attention.**
   For c1 only, simulate and then prototype EP-style ownership of experts with
   replicated attention/linear-attention state if memory allows. The goal is to
   reduce TP all-reduce and tiny-shard overhead while keeping exact weights and
   exact outputs.

4. **Public XPU MoE challenge packet plus bounty framing.**
   Publish the layer-9 routecapture6 fixture, expected outputs, local timings,
   and budget math as a small public challenge. The target is not a generic
   issue report; it is a reproducible "beat `112 us` W8A8 grouped GEMM on B70
   without changing math" packet.

5. **Production split by latency class.**
   Treat `32K TP4 capacity`, `c1 low-latency chat`, and `large aggregate batch`
   as different products. A future production setup may route them to different
   launch configs or even different engines while keeping the same model and
   quality gates.

## 2026-06-12 GPU-Only oneDNN Grouped Smoke

Result:

- The narrow vendored oneDNN path now has a real GPU smoke, not just a partial
  source build. `DNNL_CPU_RUNTIME=NONE`,
  `DNNL_ENABLE_PRIMITIVE=MATMUL;SDPA`,
  `DNNL_EXPERIMENTAL_GROUPED_MEMORY=ON`,
  `DNNL_GPU_RUNTIME=SYCL`, `DNNL_ENABLE_PRIMITIVE_GPU_ISA=XE2`,
  `ONEDNN_BUILD_GRAPH=OFF`, and `DNNL_LIBRARY_TYPE=STATIC` produced a
  linkable `libdnnl.a`.
- The vendored `third_party/oneDNN/examples/matmul_grouped.cpp` example then
  compiled against that static library and passed on B70 with
  `ONEAPI_DEVICE_SELECTOR=level_zero:0`.
- The example is f32 and tiny: it proves the grouped-memory API can build,
  link, create a grouped matmul primitive, and execute on our GPU stack. It
  does not prove Qwen W8A8 quality or speed yet.
- Repro script:
  `scripts/probe-onednn-grouped-gpuonly.sh`.
- Result packet:
  `data/qwen36-onednn-grouped-gpuonly-smoke-20260612d.json`.

Lessons:

- `DNNL_CPU_RUNTIME=NONE` matters. With CPU runtime enabled, the build stayed
  broad and spent time compiling CPU matmul code that does not answer the B70
  decode question.
- `DNNL_ENABLE_PRIMITIVE=MATMUL` is too narrow for the top-level static
  library on this oneDNN tree because `gpu_sdpa_list.cpp` still compiles and
  fails when SDPA is disabled. `MATMUL;SDPA` is the current practical narrow
  recipe.
- The internal `dnnl_gpu_intel` target is useful as an object-level proof: it
  compiles `grouped_micro_gemm`, `ref_grouped_gemm`, and generated grouped
  GPU kernels. It is not enough by itself because it does not produce a
  standalone library.
- Runtime library hygiene matters. Compiler 2025.3 variables alone did not
  expose SYCL GPU platforms. The executable needed compiler 2025.3 plus UMF,
  TCM, and TBB library paths.

Things to try from this path:

1. **Routecapture6 W8A8 oneDNN replay.**
   Fork the example into a layer-9 routecapture6 replay that consumes the same
   routed rows, expert offsets, Quark scales, and weights used by current
   `xpu_fused_moe`. Gate first on `max_abs_diff=0.0`, then measure.

2. **Primitive creation versus execution split.**
   oneDNN primitive creation can hide expensive planning. Time create,
   reorder, execute, and sync separately. If creation is expensive, cache
   primitive descriptors by route signature and shape before judging speed.

3. **Real Qwen group shape expansion.**
   Move from the example's 4 experts and 30 rows to Qwen's real active-expert
   histograms: layer 9 routecapture6 first, then layers 14, 20, and 21.
   Record active experts, empty groups, row distribution, and wall time next
   to every result.

4. **Scale and dtype matrix.**
   Verify which oneDNN GPU grouped path supports the exact W8A8 semantics we
   need: s8/u8 source, s8 weights, per-token source scales, per-output/expert
   weight scales, f32 accumulation, output dtype, binary post-ops, and SiLU.
   Reject any path that silently changes the accepted model math.

5. **oneDNN as a layerlet backend, not just GEMM.**
   If grouped matmul is competitive, test whether oneDNN post-ops can absorb
   SiLU/up-gate or whether it should remain a GEMM island inside a custom
   route/activation/gather layerlet.

6. **Command-list reuse around oneDNN.**
   Test whether a route-class primitive can live inside a reused SYCL/Level
   Zero command path. If oneDNN execute still pays high host overhead every
   token, the next win probably requires a native persistent layerlet.

Bigger, bolder ideas added from this checkpoint:

1. **oneDNN route-signature primitive cache.**
   Build a small cache keyed by layer, active expert mask, row distribution
   bucket, M/K/N, dtype, and scale layout. Warm the cache during graph
   certification so decode does not create primitives on the hot path.

2. **oneDNN Graph MoE island.**
   Explore a static subgraph containing grouped matmul, activation, second
   grouped matmul, and gather for common route buckets. If oneDNN Graph can
   compile the island with updateable buffers, it may deliver a lower-risk
   fusion path than writing every kernel by hand.

3. **Native DPAS/XMX tile-pack contract.**
   Treat the weight pack as a first-class artifact: source tensor hash,
   expert id, tile layout, scale layout, alignment, and checksum. If oneDNN or
   a native SYCL layerlet exposes a faster layout, prepack once at load time
   and validate it like a model shard.

4. **Route-class compiled artifacts.**
   Instead of one universal MoE kernel, generate a small library of kernels or
   oneDNN primitive bundles for real route classes. The route classifier picks
   the nearest exact-safe bucket; rare routes fall back to current
   `xpu_fused_moe`.

5. **Decode-token flight recorder plus replay-to-kernel CI.**
   Every promising kernel should be fed by the same captured token flight
   recorder: routes, scales, tensors, expected outputs, and command timings.
   That turns future Intel/vLLM/kernel experiments into repeatable CI rather
   than one-off terminal archaeology.

6. **Level Zero command-bundle lane.**
   If the profiler confirms host launch gaps dominate, bypass higher-level
   scheduling for the c1 latency lane: prebuild updateable command bundles for
   a fixed decode bucket, then patch only token pointers, route offsets, and
   output buffers each step.

7. **OpenVINO/oneDNN GenAI micro-runtime check.**
   Do not switch serving engines blindly, but build a tiny Qwen3.6 layer or
   block replay in the newest Intel inference stack. If Intel's own stack has
   a materially faster B70 grouped-MoE path with exact math, transplant the
   lesson rather than the whole service.

8. **Hot-route SRAM-style expert service.**
   Keep route-dominant expert tiles resident in the fastest reusable packed
   form and dispatch cold routes through the generic path. This uses memory to
   buy latency only where routecapture proves reuse.

9. **Quality-shadowed kernel race.**
   Run BF16 or current accepted `xpu_fused_moe` in a shadow lane for a sampled
   subset while a faster W8A8 kernel candidate serves the primary path. Promote
   only if sampled shadow diffs remain exact or within the already accepted
   quantized semantics over a real prompt mix.

10. **Public grouped-MoE fixture as a collaboration magnet.**
    Publish a minimal layer-9 package with tensors, route offsets, expected
    output hash, current timings, oneDNN smoke recipe, and target budget. The
    ask is concrete: beat the `112-114 us` grouped-GEMM dispatch floor or the
    `168 us/layer` budget on B70 without changing math.

## 2026-06-12 Scratch Hook And oneDNN Qwen-Shape Probe

Artifacts:

- Scratch route replay:
  `data/qwen36-quark-int8-moe-routecapture6-layer9-scratch-hook-20260612au.json`,
  `.md`, and `.log`.
- oneDNN Qwen-shape probe:
  `tools/onednn_grouped_int8_dtype_probe.cpp`,
  `scripts/probe-onednn-grouped-int8-dtypes.sh`,
  `data/qwen36-onednn-grouped-int8-qwenshape-probe-20260612au.json`,
  `data/qwen36-onednn-grouped-int8-qwenshape-probe-20260612au.log`, and
  `data/qwen36-onednn-grouped-int8-qwenshape-probe-rerun-20260612au.log`.
- Restore proof:
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-onednn-probes-20260612au.json`.

Scratch-hook result:

- Ran layer-9 routecapture6 rows=1 over 16 captured route offsets with the
  accepted base W8A8 grouped-GEMM op only. Offset, active-offset, and quant-out
  experimental ops were absent in the restored runtime, as expected.
- Exactness passed: manual staged, scratch `xpu_fused_moe`, preallocated
  staged, and fused-prologue staged all had max abs diff `0.0` against
  current `xpu_fused_moe`.
- Timing was not a win:
  - Base `xpu_fused_moe`: `309.978 us/layer` mean.
  - Scratch `xpu_fused_moe`: `346.038 us/layer` mean.
  - Preallocated staged: `250.135 us/layer` mean.
  - Fused-prologue staged: `333.010 us/layer` mean.
- Decision: scratch wiring is exact but not useful as a standalone endpoint
  optimization. The lower staged number still points at allocator/control
  overhead, but it needs a real fused layerlet or output-buffer ABI change to
  become a serving win.

oneDNN grouped INT8 result:

- The new dtype probe confirmed oneDNN grouped-memory matmul supports the
  basic Qwen-relevant dtype and scale shape on B70:
  `s8` source, `s8` weights, grouped source/destination offsets, per-token
  source scales, per-expert-column weight scales, and f32 or bf16 destination.
- Small example shape warmed rerun: `s8/s8/f32` executed in `62 us`.
- Qwen layer-9 GEMM1 shape (`256` experts, `8` routed rows, `K=2048`,
  `N=256`) warmed rerun:
  - f32 dst: create `3296 us`, execute+wait `222 us`.
  - bf16 dst: create `5798 us`, execute+wait `258 us`.
- Qwen layer-9 GEMM2 shape (`256` experts, `8` routed rows, `K=128`,
  `N=2048`) warmed rerun:
  - f32 dst: create `4159 us`, execute+wait `210 us`.
  - bf16 dst: create `5142 us`, execute+wait `227 us`.
- Decision: oneDNN is viable at the API/dtype level, but two standalone
  oneDNN grouped GEMM calls are slower than the current XPU grouped-GEMM
  components (`~89-125 us` each in the scratch replay). Do not use oneDNN as a
  drop-in two-GEMM replacement.

Updated next actions:

1. **Stop pursuing scratch-only endpoint wiring.**
   It is exact, but the measured wrapper call is slower than base
   `xpu_fused_moe`. Keep the result as evidence that allocation/control
   matters; spend implementation time on a fused ABI, not on passing scratch
   into the current wrapper.

2. **Use oneDNN only if it removes boundaries.**
   The oneDNN path should continue only as a primitive-cache/fused-island or
   command-bundle experiment. A route-signature cache is mandatory because
   cold primitive creation was hundreds of milliseconds and warmed creation
   was still several milliseconds for Qwen shapes.

3. **Next non-speculative implementation should be a layerlet scaffold.**
   The current evidence now converges: base wrapper `~310 us`, current GEMM
   components `~90-125 us` each, oneDNN standalone `~210-222 us` each, and
   target budget `~168 us/layer`. The only plausible non-speculative path is
   fewer command boundaries: a one-dispatch fake layerlet first, then a fused
   route/quant/GEMM/activation/GEMM/gather layerlet.

4. **If oneDNN gets another run, make it reuse everything.**
   A fair next oneDNN run must create primitives once, allocate memories once,
   reuse scale buffers, execute many captured route windows, and report
   execute-only timing. If that still exceeds the current GEMM floor, close the
   oneDNN standalone branch.

## 2026-06-12 Larger Opportunity Refresh

This addendum records the next round of ideas after the scratch-hook and
oneDNN Qwen-shape probes. It is notes-only: no endpoint change, no new speed
claim, and no quality relaxation.

External scan update:

- Localmaxxing exact-model filter still shows one public exact row for
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` on 4x Arc Pro B70:
  `cmq8yhxvo001ipb0149aoa79o` at `99.428 tok/s`, c1, 32K context. The
  broader Arc Pro B70/Qwen/vLLM family query still shows our base-model-mapped
  `Qwen/Qwen3.6-35B-A3B` row `cmq9ifq0500b0r8012f27j1xl` at
  `99.770 tok/s`. Keep both references because the exact HF ID matters when
  comparing public results.
- Intel's B-series vLLM article remains the strongest external match to our
  measurements: MoE launch overhead, gate dependency stalls, route imbalance,
  persistent zero-gap kernels, and dynamic work distribution are the same
  themes now exposed by our `~10 ms/token` decode budget and route-replay
  floors:
  `https://vllm.ai/blog/2025-11-11-intel-arc-pro-b`.
- vLLM XPU docs list speculative decoding feature areas including MTP,
  n-gram, draft models, EAGLE, and parallel draft models, but public
  Qwen3.6 MTP reports include long-context crashes. Treat MTP as a serious
  `>200 tok/s` candidate only behind target-model verification, rollback
  logs, and long-context soak:
  `https://docs.vllm.ai/en/v0.18.0/models/hardware_supported_models/xpu/`,
  `https://github.com/vllm-project/vllm/issues/40756`.
- Public B70 reports keep showing the same split: aggregate throughput can look
  good at high concurrency, while single-request latency remains much harder.
  This supports a production plan with separate c1 latency and aggregate
  capacity lanes, not one universal serving mode:
  `https://forum.level1techs.com/t/intel-b70-launch-unboxed-and-tested/247873`,
  `https://www.reddit.com/r/IntelArc/comments/1ti1uw0/intel_arc_pro_b70_looking_for_llm_setup_guidance/`.

### New Things To Try

1. **One-dispatch fake layerlet overhead gate.**
   Before writing the full fused MoE layerlet, build the thinnest possible
   custom op with the final ABI shape: hidden state, top-k ids/weights, route
   offsets, workspace pointers, output pointer, and a layer id. It can do a
   checksum or copy. The only question is launch/call overhead. If this empty
   layerlet is already too expensive, the full fused design must move closer
   to a resident service or command graph.

2. **oneDNN reuse-only grouped INT8 benchmark.**
   Run one fair oneDNN follow-up: create Qwen GEMM1/GEMM2 primitives and
   memory objects once, reuse scale buffers, then replay many captured route
   windows. Record execute-only timing. If execute-only still trails the
   current XPU GEMM floor, close standalone oneDNN and keep it only as a
   design/reference stack.

3. **Layer-9 hotset fast path with cold fallback.**
   Routecapture says top-32/top-64 experts cover enough assignments to justify
   a fast path, and the memory cost is roughly `1-2 GiB/rank` for all layers.
   Prototype one layer first: hot experts use tile-native packed W8A8 buffers
   and cold experts fall back to current `xpu_fused_moe`. The quality rule is
   exact math for both paths and max diff `0.0` on captured routes.

4. **MTP/speculation state audit for Qwen3.6 GDN.**
   Do not start with a speed run. First map exactly which state must be
   copied, versioned, or rolled back for Qwen3.6's Gated DeltaNet and normal
   attention paths. The deliverable is a transaction-state table: KV pages,
   GDN recurrent state, scheduler buffers, sampled-token buffers, logits,
   and per-request metadata.

5. **Long-context speculative stability probe.**
   If MTP or another proposer is tried, test it at the failure shape reported
   publicly: long requests around `25K+` total tokens and `1000+` generated
   tokens. A short p512/o512 win is not enough. Speculation must survive the
   production context shapes we care about.

6. **B70 XMX/DPAS counter packet.**
   Capture hardware counters for the current grouped GEMM, quant, and any
   layerlet candidate. The question is binary: are the hot kernels using the
   intended INT8 XMX/DPAS path at useful occupancy? If not, the larger win is
   a hand-tuned ESIMD/SYCL DPAS kernel or a layout repack, not vLLM flags.

7. **Model-forward graph surgery point.**
   The safe live timing gate now says accepted graph model-forward costs about
   `8.44 ms/token`. Locate the exact graph node or compiled custom-op boundary
   where MoE can be replaced without losing graph replay. A microbench-only win
   is not enough; the patch must reduce this live model-forward bucket.

8. **Rank-group experiment for latency, not capacity.**
   Test whether all four cards are helping c1 latency or mainly serving memory
   and aggregate throughput. Candidate shapes: TP4 current, TP2 with lower
   context, two TP2 replicas, and one TP2 latency lane plus one TP2 aggregate
   lane. Use exact canaries and the same p512/o512 metric. If TP4 allreduce or
   small local GEMMs dominate, production should route c1 traffic differently.

9. **Command-bundle layer group.**
   If the one-dispatch fake layerlet is cheap but full fusion is hard, build a
   Level Zero/SYCL command bundle for a small group of layers with updateable
   memory pointers. This is less invasive than a full custom engine but attacks
   the same host-launch and graph-boundary costs.

10. **Quality-near-miss suite, not just sentinel suite.**
    Add a small BF16-vs-Quark and old-kernel-vs-new-kernel logit-rank harness
    that checks top-k rank stability and semantic answer class on canary
    prompts. Sentinels catch gross errors; logit-rank drift catches kernels
    that are numerically "close" but behaviorally risky.

### Bigger, Bolder Ideas To Keep Alive

1. **B70 MoE resident runtime.**
   Move beyond a fused op: keep resident expert workers alive across decode
   steps and feed them route/task descriptors from a device queue. This is the
   closest match to Intel's persistent zero-gap direction and avoids paying
   per-token setup for the same layer shapes.

2. **Route-class generated layerlet library.**
   Generate a small number of specialized kernels per layer from real route
   classes rather than one generic MoE implementation. A route classifier
   picks the closest exact-safe kernel; rare shapes use the generic fallback.
   The generator should emit both code and exact replay tests.

3. **Hot-expert tile cache as a first-class model artifact.**
   At load time, build a checksumed sidecar of tile-native packed expert
   buffers for selected layers/hotsets. This separates model quality from
   runtime layout: source tensors remain unchanged, while the fast path uses a
   certified layout cache.

4. **Verified multi-token target branch engine.**
   Instead of trusting a small draft model, use spare rank groups or idle time
   to evaluate several exact target branches, then commit the branch selected
   by the same target model. This preserves quality by construction but needs
   careful state sharing to avoid multiplying memory cost.

5. **Latency sidecar outside vLLM.**
   Build a tiny fixed-bucket serving sidecar for c1 chat traffic: one request,
   fixed prompt/output buckets, preallocated KV/GDN state, certified graph
   cache, exact tokenizer/model weights, and a narrow OpenAI-compatible shim.
   The point is not to replace vLLM; it is to prove the real lower bound for
   user-perceived latency.

6. **XPU kernel challenge packet with bounty-quality repro.**
   Publish route windows, tensor shapes, expected output hashes, current
   timings, oneDNN results, and target budgets. The ask should be specific:
   beat the B70 W8A8 layer-9 floor without changing math. This can pull help
   from Intel/vLLM/Triton-XPU people faster than a broad performance issue.

7. **Production split by service class.**
   Design production as multiple certified lanes: c1 latency, long-context,
   aggregate batch, and risky experimental. Each lane has its own graph cache,
   quality gates, soak target, and Localmaxxing payload. Do not force the
   32K TP4 backend to be optimal for every request shape.

8. **Driver/runtime regression farm.**
   Use the same accepted command, prompt suite, and provenance checks across
   kernel/KMD/firmware/oneAPI/oneCCL/vLLM container versions. This is tedious,
   but the B70 stack is still moving fast enough that one runtime upgrade could
   matter more than another week of local kernel surgery.

9. **Kernel-level mixed scheduler: hot path exact, cold path generic.**
   Build one scheduler that can choose among current `xpu_fused_moe`,
   hotset-packed GEMM, persistent layerlet, and oneDNN/ESIMD candidate per
   layer/window. The current route data argues against one static winner.

10. **Reliability-weighted benchmark scoreboard.**
    Track every candidate as `{tok/s, ms/token, exactness, logit drift,
    device-lost count, restart time, soak minutes, VRAM, graph-cache id}`.
    This prevents a fragile `120 tok/s` experiment from displacing a stable
    `100 tok/s` production candidate until it earns that status.

## 2026-06-12 oneDNN Reuse-Only Qwen-Shape Probe

Artifacts:

- Probe source:
  `tools/onednn_grouped_int8_reuse_probe.cpp`.
- Probe runner:
  `scripts/probe-onednn-grouped-int8-reuse.sh`.
- Result JSON/log:
  `data/qwen36-onednn-grouped-int8-reuse-qwenshape-20260612av.json`,
  `data/qwen36-onednn-grouped-int8-reuse-qwenshape-20260612av.log`.
- Restore/provenance:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-onednn-reuse-20260612av.log`,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-onednn-reuse-20260612av.json`.

Command shape:

```bash
REUSE_JSON_OUT="$PWD/data/qwen36-onednn-grouped-int8-reuse-qwenshape-20260612av.json" \
REUSE_WARMUP=50 \
REUSE_ITERATIONS=500 \
DEVICE_SELECTOR=level_zero:0 \
bash scripts/probe-onednn-grouped-int8-reuse.sh \
  2>&1 | tee data/qwen36-onednn-grouped-int8-reuse-qwenshape-20260612av.log
```

Result:

- The accepted backend was stopped for a clean one-card XPU timing window.
  VRAM dropped to roughly `26-50 MiB` per card before the run.
- The probe creates oneDNN grouped-memory matmul primitives, memory objects,
  grouped offsets, and scale memories once, then measures steady execution.
- Destination checksums are nonzero, so this is not just a launch/no-op
  artifact. It is still not a full numeric correctness proof against Quark
  W8A8 output.
- Layer-9 Qwen GEMM shapes over 8 routed rows:
  - GEMM1: `K=2048`, `N=256`, `256` experts.
  - GEMM2: `K=128`, `N=2048`, `256` experts.
- bf16 destination:
  - GEMM1 single execute+wait mean `42.741 us`, p50 `60.033 us`,
    p90 `63.209 us`.
  - GEMM2 single execute+wait mean `17.726 us`, p50 `17.293 us`,
    p90 `18.765 us`.
  - GEMM1+GEMM2 two-exec/one-wait mean `29.446 us`, p50 `29.145 us`,
    p90 `29.957 us`, max `90.660 us`.
- f32 destination:
  - GEMM1 single execute+wait mean `17.553 us`, p50 `17.182 us`,
    p90 `17.894 us`.
  - GEMM2 single execute+wait mean `17.525 us`, p50 `17.232 us`,
    p90 `17.964 us`.
  - GEMM1+GEMM2 two-exec/one-wait mean `26.465 us`, p50 `26.179 us`,
    p90 `27.412 us`, max `34.905 us`.
- Primitive/memory construction remains expensive:
  - GEMM1 bf16 construct `305365 us`.
  - GEMM2 bf16 construct `99437 us`.
  - GEMM1 f32 construct `186376 us`.
  - GEMM2 f32 construct `98932 us`.

Decision:

- The earlier oneDNN Qwen-shape result was a false negative for steady decode:
  it measured cold-ish primitive behavior and isolated execute+wait calls.
  Reused oneDNN grouped INT8 can be much faster than the current
  `~112-114 us` per grouped-GEMM route-replay floor, and the two-GEMM pair is
  far under the `~168 us/layer` non-speculative MoE budget before activation,
  quant, route, and gather.
- Do not promote anything to the endpoint yet. This probe uses synthetic
  tensors and fixed offsets. It does not update route windows, use real Quark
  W8A8 weights/scales, or compare against `xpu_fused_moe`.
- The next oneDNN task is now higher priority than another scratch-wrapper
  variant: build a routecapture6 layer-9 oneDNN replay that reuses primitives
  and memory, mutates grouped offsets/scales per captured route window, uses
  real model-shaped W8A8 tensors, and requires `max_abs_diff=0.0` against the
  current path.
- If the route-exact replay keeps the pair timing in this range, oneDNN
  becomes a serious layerlet backend. If route updates or real layouts erase
  the win, close the oneDNN branch and return to a custom persistent/ESIMD
  layerlet.

Restore result:

- Accepted backend was relaunched in
  `qwen36-tp4-accepted-restored-after-onednn-reuse-20260612av`.
- Backend `/health` returned `200` after `56s`.
- Provenance guard passed both prefix cases and all sentinel tokens:
  `4752` at `repetitive_kernel_notes:14`, `11436` at
  `natural_latency_plan:17`, and `198` at `natural_latency_plan:25`.

## 2026-06-12 oneDNN Route-Window Offset Replay

Artifacts:

- Route-count exporter:
  `scripts/export-qwen36-route-counts.py`.
- Route-count windows:
  `data/qwen36-quark-int8-routecapture6-layer9-r1-start0-64x4-counts-20260612aw.csv`,
  `data/qwen36-quark-int8-routecapture6-layer9-r1-start0-64x4-counts-20260612aw.json`.
- Route-window timing:
  `data/qwen36-onednn-grouped-int8-reuse-routecapture6-layer9-r1-20260612aw.json`,
  `data/qwen36-onednn-grouped-int8-reuse-routecapture6-layer9-r1-20260612aw.log`.
- Restore/provenance:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-onednn-routewindows-20260612aw.log`,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-onednn-routewindows-20260612aw.json`.

Command shape:

```bash
python3 scripts/export-qwen36-route-counts.py \
  data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl \
  --layer-regex 'layers[.]9[.]' \
  --rows 1 \
  --starts '0:64:4' \
  --out data/qwen36-quark-int8-routecapture6-layer9-r1-start0-64x4-counts-20260612aw.csv \
  --metadata-out data/qwen36-quark-int8-routecapture6-layer9-r1-start0-64x4-counts-20260612aw.json

REUSE_JSON_OUT="$PWD/data/qwen36-onednn-grouped-int8-reuse-routecapture6-layer9-r1-20260612aw.json" \
REUSE_ROUTE_COUNTS="$PWD/data/qwen36-quark-int8-routecapture6-layer9-r1-start0-64x4-counts-20260612aw.csv" \
REUSE_WARMUP=50 \
REUSE_ITERATIONS=500 \
DEVICE_SELECTOR=level_zero:0 \
bash scripts/probe-onednn-grouped-int8-reuse.sh \
  2>&1 | tee data/qwen36-onednn-grouped-int8-reuse-routecapture6-layer9-r1-20260612aw.log
```

Result:

- Exported `16` real routecapture6 layer-9 rows=1 windows using starts
  `0:64:4`.
- Each window has `8` total expert assignments and `8` active experts, matching
  the previous rows=1 route-replay microbench.
- The oneDNN probe now reuses primitives/memory and rewrites grouped
  source/destination offsets before each execute.
- Fixed-offset control timings reproduced the prior reuse result:
  - bf16 GEMM1+GEMM2 two-exec/one-wait mean `29.445 us`, p50 `29.225 us`,
    p90 `29.956 us`.
  - f32 GEMM1+GEMM2 two-exec/one-wait mean `26.452 us`, p50 `26.119 us`,
    p90 `27.431 us`.
- Route-window offset-update timings:
  - bf16 GEMM1 single update+execute+wait mean `25.698 us`, p50 `25.157 us`,
    p90 `26.801 us`.
  - bf16 GEMM2 single update+execute+wait mean `23.924 us`, p50 `23.464 us`,
    p90 `25.047 us`.
  - bf16 GEMM1+GEMM2 update+two-exec+one-wait mean `41.673 us`, p50
    `41.678 us`, p90 `42.700 us`, max `58.790 us`.
  - f32 GEMM1+GEMM2 update+two-exec+one-wait mean `39.458 us`, p50
    `38.902 us`, p90 `40.626 us`, max `51.807 us`.
- Checksums changed between fixed-offset and route-window runs, which confirms
  the grouped offset metadata is being mutated and consumed.

Decision:

- oneDNN remains a serious layerlet backend candidate. Even with per-window
  offset mutation, the two-GEMM pair stays far below the current XPU grouped
  GEMM floor and below the `~168 us/layer` non-speculative MoE budget before
  activation/quant/gather overhead.
- This still is not a quality proof. The current probe uses deterministic
  synthetic buffers and oneDNN scale semantics; it does not yet consume the
  exact PyTorch tensors used by `xpu_fused_moe`, nor compare output.
- Next implementation gate:
  1. build an exact layer-9 replay that feeds the same synthetic tensors to
     current `xpu_fused_moe` and the oneDNN path;
  2. match oneDNN grouped source/weight layout and scale semantics to Quark
     W8A8;
  3. require `max_abs_diff=0.0` or explain the precise expected rounding
     difference before considering endpoint integration;
  4. if exact, wrap it behind a route-signature primitive cache and measure the
     live `gpu_model_runner.model_forward` bucket.

Restore result:

- Accepted backend was relaunched in
  `qwen36-tp4-accepted-restored-after-onednn-routewindows-20260612aw`.
- Backend `/health` returned `200` after `56s`.
- Provenance guard passed both prefix cases and all sentinel tokens:
  `4752` at `repetitive_kernel_notes:14`, `11436` at
  `natural_latency_plan:17`, and `198` at `natural_latency_plan:25`.

## 2026-06-12 Wider Opportunity Addendum

This addendum records the next items to try plus larger bets after the
oneDNN route-window replay. It is intentionally notes-only: no endpoint
promotion, no model swap, and no public speed claim.

Fresh external scan:

- Localmaxxing exact-model public state is unchanged: the exact
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` / 4x B70 / vLLM row remains
  `cmq8yhxvo001ipb0149aoa79o` at `99.428 tok/s`.
- The broader B70/Qwen/vLLM family query still shows our base-model mapped
  `cmq9ifq0500b0r8012f27j1xl` at `99.770 tok/s`, plus external Qwen3.6 27B
  B70 MTP work. Treat those 27B rows as speculation and stack clues, not as
  a substitute for this 35B INT8 target.
- Localmaxxing's broader `Qwen/Qwen3.6-35B-A3B` rows above `200 tok/s` are
  mostly non-B70, non-W8A8, MTP/DFlash/NVFP4/MQ4-style paths. They reinforce
  that exact target-verified speculation can matter, but they do not justify
  lowering the target model quality or moving to 4-bit.
- vLLM's public INT8 W8A8 documentation still frames official INT8 compute
  support around NVIDIA GPU capability. Our XPU Quark W8A8 path remains a
  local/vendor path that needs its own route-exact correctness proof.
- oneDNN v3.13 explicitly documents grouped memory for MoE variable token
  counts, and recent oneDNN releases call out grouped matmul as an experimental
  opt-in with Intel GPU optimization. This matches the route-window replay and
  raises priority for the oneDNN parity gate.
- Triton and PyTorch grouped-GEMM references both point at fixed device-side
  scheduling and persistent kernels as the right shape for MoE. This reinforces
  the local conclusion that ordinary two-dispatch grouped GEMM is not the
  `2x` path.

Immediate additions to the try list:

1. **oneDNN/XPU grouped-GEMM parity harness.**
   Export one deterministic W8A8 grouped-GEMM case from the current XPU kernel:
   `A int8`, per-token `A_scales`, `B int8`, per-expert-column `B_scales`,
   `rows_per_expert`, and XPU output. Feed exactly the same buffers into the
   oneDNN grouped-memory runner. The first pass can compare GEMM1 and GEMM2
   independently; the required output is either `max_abs_diff=0.0` or a
   documented rounding-mode mismatch with a bounded diff.

2. **oneDNN scale/layout forensic packet.**
   Before full MoE replay, prove the meaning of oneDNN src and weight scales
   against a CPU reference and the current XPU kernel for tiny and Qwen-shaped
   cases. This should catch transposed weight layout, per-column scale indexing,
   and bf16 destination rounding errors early.

3. **Layer-9 full MoE parity replay.**
   Once GEMM parity is understood, compose route/remap, GEMM1, SiLU/up-gate,
   quant2, GEMM2, top-k weighting, and gather for one captured layer-9
   routecapture6 window. Required gate: exact agreement against current
   `xpu_fused_moe` before any timing conclusion.

4. **Profiler acquisition lane.**
   Install or locate `unitrace`, VTune, or an equivalent Level Zero trace stack
   and capture one accepted decode token plus one route-replay layer. The
   target table is kernel name, duration, launch gap, barriers, copies,
   collectives, and whether the W8A8 hot kernels are using DPAS/XMX as expected.

5. **Speculation state audit for Qwen3.6 GDN.**
   Inventory every mutable state that makes target-verified speculation hard:
   KV pages, GDN/Mamba state, block tables, computed-token counters, scheduler
   sequence metadata, RNG/sampling state, and graph-captured buffers. The
   output should be a commit/rollback data model, not a speed run.

6. **Clean host-stack and topology A/B.**
   Repeat only the accepted command on a clean Intel-supported container or
   runtime stack, then on alternate PCIe/root-complex placements if available.
   Keep same model, same prompts, same quality gate. If c1 changes materially,
   promote the host-stack finding separately from model/kernel changes.

7. **TP economics truth-serum.**
   Run narrowly scoped TP1/TP2/TP4 or simulated TP2+replicated-hot-expert
   tests at smaller context if needed. The purpose is to learn whether TP4
   communication and smaller shard shapes are costing more c1 latency than
   they save for this MoE.

8. **Localmaxxing dry-run discipline.**
   Generate a dry-run payload only when a result is material, quality-cleared,
   and reproducible. Do not spend submission cycles on the current `99.7 tok/s`
   refresh unless we explicitly want a recovery datapoint; wait for a real
   threshold such as `105+`, `120+`, or a new exactness category.

Additional bigger bets to keep alive:

1. **oneDNN route-signature primitive cache inside vLLM.**
   If the parity harness passes, cache oneDNN primitive/memory bundles by
   `(layer, rows_per_expert signature, dtype, output dtype)` and update only
   offset metadata at runtime. This is less ambitious than a full custom
   persistent kernel and could be a bridge to a real endpoint win.

2. **ESIMD/DPAS generated layerlet.**
   Generate a small number of route-class layerlets that directly issue Intel
   matrix operations for the exact Qwen shapes. Use tile-native packed expert
   weights with checksums, fixed Quark scale layout, and route-class metadata.
   This is the lower-level alternative if oneDNN parity or integration stalls.

3. **Resident MoE command processor.**
   Put a persistent kernel or device service in charge of route tasks for a
   layer group. The host writes compact descriptors; device workers perform
   remap, quant, GEMMs, activation, and gather without paying a host launch for
   each phase. This is still the cleanest non-speculative `2x` concept.

4. **Exact target branch farm.**
   Use spare hardware lanes to compute several target-model candidate branches
   speculatively, then commit only the branch proven by the target model. This
   is expensive, but it preserves quality and may be useful when decode is
   underutilizing compute.

5. **Trace-trained proposer behind verifier.**
   Train or tune a small proposer on continuations emitted by this exact Quark
   model. It never emits final text directly; it only feeds the target verifier.
   This could give higher acceptance than generic n-gram without changing
   output quality.

6. **Static c1 sidecar outside vLLM.**
   Build a tiny fixed-bucket single-request runner for p512/o512 and a few
   common chat shapes. Same tokenizer and same Quark weights, but no dynamic
   vLLM scheduler. Use it as a truth-serum for whether vLLM overhead or kernel
   math dominates.

7. **Hot-expert memory lane with admission control.**
   If VRAM remains high but workable, duplicate only hot expert packed tiles
   for selected layers in a latency lane. Routecapture says hot64 replication
   can nearly erase imbalance in simulation, but implementation should wait
   for a communication/stall trace.

8. **OpenVINO/oneDNN GenAI support check.**
   Do a fit-and-correctness check only if Qwen3.6 A3B, GDN, and Quark-like
   W8A8/MoE are genuinely supported. If unsupported, record it and stop. This
   is a possible engine truth-serum, not permission to change the target model.

9. **Public B70 W8A8 MoE challenge packet.**
   Publish a compact repro once parity fixtures are clean: route windows,
   model-shaped buffers, expected outputs, current XPU timings, oneDNN timings,
   and exact quality guard. This could attract useful Intel/vLLM feedback
   without exposing secrets or a huge private codebase.

10. **Reliability-weighted performance scoreboard.**
    Every future candidate should record speed, exactness, TTFT, device-lost
    count, graph-cache identity, restart time, and soak result. A stable
    `120 tok/s` lane is more useful for production than a fragile `180 tok/s`
    spike.

Explicit non-goals:

- No 4-bit, AWQ, or Qwen3.5 substitution for this target.
- No public promotion from synthetic tensors, draft-only speed, or BF16
  fallback quality alone.
- No more launch-flag sweeps unless a timing packet identifies the specific
  stall they are meant to address.

## 2026-06-12 Resident OneDNN Pair Gate And New Bolder Bets

This section folds in the resident two-GEMM oneDNN result plus a fresh external
scan. It is still notes-only. No endpoint throughput claim changes until the
full MoE island runs in-process, with direct XPU buffers, and matches the
current accepted path.

New hard facts:

- A resident C++ oneDNN runner now loads the real routecapture6 layer-9 GEMM1
  and GEMM2 buffers once, creates packed `acb` grouped-matmul primitives once,
  and times the pair in one process.
- First resident run: GEMM1+GEMM2 pair p50 `88.657 us`, mean `96.344 us`;
  both raw outputs equal the current XPU exported outputs.
- Warm reused-binary run: GEMM1+GEMM2 pair p50 `49.954 us`, mean `54.340 us`;
  both GEMMs remained raw-exact.
- This result is materially different from the older `~226 us/layer` current
  grouped-GEMM floor: the cost floor drops when primitive construction,
  process startup, and isolated dispatch overhead are removed.
- Caveat: the pair run excludes activation, dynamic quant2, route gather,
  top-k weighting, and direct vLLM tensor handoff. The only honest next claim
  is an in-process full-layer MoE island, not an endpoint `tok/s` projection.
- First backend restore after the isolated oneDNN run hit
  `UR_RESULT_ERROR_DEVICE_LOST` around scheduler metadata copies
  (`block_table.copy_to_gpu` and token-counter movement). This belongs on the
  reliability scoreboard: clean XPU windows and repeated Level Zero users can
  still perturb restart reliability.
- After killing the stale backend/workers and relaunching, `/health` returned
  and the retry provenance guard passed both prefix cases plus all sentinel
  tokens. Keep both the failed first provenance and successful retry provenance
  artifacts: the first is reliability evidence, the second proves the accepted
  endpoint recovered cleanly.

Fresh external signals:

- oneDNN v3.12/v3.12.1 now explicitly mentions Intel GPU grouped matmul for
  MoE, small-M/N large-K matmul improvements, and SYCL Graph record/replay
  support. This strengthens the case for a resident oneDNN path and for trying
  newer oneDNN builds behind exact parity gates:
  `https://github.com/uxlfoundation/oneDNN/releases`.
- The standalone `vllm-xpu-kernels` split is the right upstream integration
  target: it already registers XPU custom ops into PyTorch and lists MoE
  remap/gather/top-k, quant/GEMM, and grouped GEMM as supported categories:
  `https://github.com/vllm-project/vllm-xpu-kernels`.
- vLLM issue traffic for Arc B580/B70-class systems is still mostly about
  practical XPU tuning and stack uncertainty, not a solved recipe for c1
  Qwen3.6 MoE latency:
  `https://github.com/vllm-project/vllm/issues/35638`.
- Localmaxxing currently shows fast public rows for other Qwen/MoE families,
  but the exact target row remains the only thing that should govern public
  claims. Broader rows are useful as ambition markers, not quality evidence:
  `https://localmaxxing.com/en/models`.
- Public B70 llama.cpp/SYCL data shows Qwen3.6 35B-A3B Q8_0 at `36.5 tok/s`
  on two GPUs and Q4 around `54.7 tok/s` on one GPU. That context makes the
  current vLLM/Quark `~100 tok/s` respectable, but also reinforces that
  ordinary multi-GPU fit does not automatically solve single-request latency:
  `https://github.com/PMZFX/intel-arc-pro-b70-benchmarks/blob/master/llm-benchmarks.md`.
- Recent Intel-GPU inference research frames oneDNN INT8 as an attainable
  roofline on BMG-class GPUs, which matches the local decision to treat oneDNN
  as the correctness/performance oracle before hand-writing lower-level DPAS
  layerlets:
  `https://arxiv.org/html/2508.06753v2`.

Immediate things to try from this gate:

1. **Direct XPU tensor interop for the resident oneDNN runner.**
   Replace file-backed buffers with Level Zero/USM-compatible memory handed
   from the vLLM XPU tensors. First prove a no-op read/write alias and checksum
   path, then run GEMM1/GEMM2 on the same data without host copies.

2. **vLLM custom-op sidecar around resident oneDNN primitives.**
   Add the narrowest custom op possible under `vllm-xpu-kernels` style
   registration: one layer, one route signature, resident packed weights, and
   final output compared against `xpu_fused_moe`. This keeps scheduler/KV/dense
   layers in vLLM while isolating the MoE island.

3. **Route-signature cache hit-rate measurement.**
   Before building an elaborate cache, measure how often real route windows
   reuse the same `(layer, active experts, rows_per_expert)` signature across
   natural/chat/code/math prompt traces. If cache reuse is weak, key the cache
   by active-expert set plus max group size and only mutate offsets.

4. **Full resident MoE island timing.**
   Extend the resident runner beyond the GEMM pair: exact remap, GEMM1,
   SiLU/up-gate, exact activation quant, GEMM2, top-k weighting, and gather.
   Kill gate: cannot get below the `168 us/layer` non-speculative budget after
   removing file/process/construct costs.

5. **oneDNN SYCL Graph experiment.**
   With oneDNN v3.12+ or the vendored tree if practical, test whether the
   resident GEMM pair or full island can be captured/replayed as a SYCL Graph.
   Compare graph replay against normal resident execution with exact raw output
   equality. If graph replay is unstable, record it as a production risk.

6. **Packed expert-weight artifact at model load.**
   Repack experts into the fastest verified oneDNN layout at startup or as a
   precomputed artifact. Store source tensor hash, packed format, oneDNN
   version, route fixture, and raw-output parity metadata. This avoids hidden
   runtime repack cost and makes packed weights auditable.

7. **Device-lost restart reproducer.**
   Turn the observed restore failure into a small reliability test: run
   accepted backend, stop it, run the resident oneDNN Level Zero runner, then
   restart accepted backend and run provenance. Track whether failures require
   process cleanup, driver reset, sleep interval, or oneDNN runtime teardown.

8. **New oneDNN/vLLM-XPU stack A/B behind parity.**
   Try newer oneDNN and `vllm-xpu-kernels` builds only through the route-replay
   fixtures first. Promotion requires raw parity and an accepted-service
   provenance pass. Do not treat a stack upgrade as quality-neutral without
   evidence.

9. **BF16 fallback differential harness as a guardrail, not a target.**
   Keep the BF16 fallback around for logit-rank and semantic drift checks
   after kernel changes. It should detect subtle W8A8-path distortions, but it
   is not a speed candidate and should not replace the Quark W8A8 target.

10. **Localmaxxing dry-run from the best exact row only.**
    Prepare a dry-run payload for the current best exact-model c1 row, but
    publish only when the result is material beyond the existing `~99-100
    tok/s` class or when it documents a genuinely new exactness category such
    as resident oneDNN integration.

Bigger, bolder ideas worth keeping alive:

1. **A Qwen3.6 MoE island ABI.**
   Define a stable internal ABI for one MoE layer: route descriptor, expert
   packed weights, Quark scales, workspace pointers, output pointer, and parity
   checksum. Then implement multiple backends behind it: current
   `xpu_fused_moe`, resident oneDNN, generated ESIMD/DPAS, and future Triton
   XPU. This lets every radical idea compete on the same exact fixture.

2. **Micro-AOT route compiler.**
   Build a telemetry-driven compiler that emits a small set of route-class
   command bundles from captured prompts. Each bundle may choose oneDNN,
   custom DPAS, hot-expert packed tiles, or fallback current XPU. Runtime only
   selects a certified bundle if the route signature matches a proven class.

3. **Layer-group resident command graph.**
   Instead of optimizing one MoE layer at a time forever, try a two- or
   four-layer command graph where route metadata, quant buffers, GEMM work, and
   collectives are double-buffered. The goal is to overlap the CPU/control
   gaps between adjacent layers while preserving exact token dependencies.

4. **Latency lane with memory-for-speed expert placement.**
   Use the 4x32GB footprint to build a separate c1 lane that sacrifices
   concurrency and some context headroom for hot-expert replication or
   tile-native duplicate packs. The general production lane can stay TP4/32K;
   the latency lane is allowed to be stricter about prompt length and one
   active request.

5. **Exact branch farm on spare ranks.**
   If profiler evidence shows underused compute while waiting on small-M MoE
   work or collectives, use spare rank time to score exact target-model branch
   candidates. This preserves quality because the current target model is the
   verifier, but it may convert idle parallelism into lower visible latency.

6. **GPU-resident scheduler metadata service.**
   The recurring device-lost failures around block tables and token counters
   suggest a bigger reliability/perf opportunity: keep solo-lane scheduler
   metadata in graph-stable device buffers and update it from a tiny kernel
   rather than repeated host-to-device scalar/table movements.

7. **Minimal C++ decode truth-serum.**
   Build a standalone fixed-bucket executable that loads the accepted Quark
   weights, runs one prompt shape, and bypasses Python/vLLM scheduling while
   still using the same math. If it cannot beat vLLM meaningfully, the kernels
   are the wall. If it does, the production architecture should become
   two-lane rather than endlessly patching the general server.

8. **Public exact MoE challenge packet.**
   Once the resident oneDNN fixture is cleaned up, publish a compact challenge:
   route descriptor, tiny raw buffers, checksums, oneDNN result, current XPU
   result, and timing. Ask Intel/vLLM maintainers for any B70 kernel that beats
   the pair/island while preserving byte equality.

9. **Reliability-weighted leaderboard discipline.**
   Start scoring experiments by `(tok/s, exactness, restart reliability,
   device-lost rate, soak duration, provenance pass)` rather than tok/s alone.
   This keeps production reality attached to the speed chase.

10. **Profiler as a hard kill gate.**
    Once `unitrace`/VTune/Level-Zero tracing is available, every major kernel
    bet should show DPAS/XMX utilization, launch count, barriers, and bandwidth.
    If a path is not using the hardware correctly, stop polishing higher-level
    vLLM flags and fix layout/kernel selection first.

## 2026-06-12 Route-Signature Cache Analysis

New script:

- `scripts/qwen36-route-signature-cache-analysis.py`.

Purpose:

- Decide whether the resident oneDNN path should cache by generic primitive
  shape, exact rows-per-expert vector, active expert set, or ordered top-k
  route.
- Keep this CPU-only so it can run while the accepted backend stays live.

Artifacts:

- `data/qwen36-quark-int8-tp4-routecapture6-signature-cache-20260612ba.json`.
- `data/qwen36-quark-int8-tp4-routecapture6-signature-cache-20260612ba.md`.
- `data/qwen36-quark-int8-tp4-promptclass-plus-route6-signature-cache-20260612ba.json`.
- `data/qwen36-quark-int8-tp4-promptclass-plus-route6-signature-cache-20260612ba.md`.

Command shape:

```bash
python3 scripts/qwen36-route-signature-cache-analysis.py \
  'data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-*.jsonl' \
  data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl \
  --max-num-tokens 1 \
  --out data/qwen36-quark-int8-tp4-promptclass-plus-route6-signature-cache-20260612ba.json \
  --markdown-out data/qwen36-quark-int8-tp4-promptclass-plus-route6-signature-cache-20260612ba.md
```

Result from prompt-class traces plus routecapture6:

- Input size: `5485` c1 decode MoE route records across `5` captured layers.
- Mutable-offset primitive key: `5` unique keys, `99.9%` repeat rate,
  `99.9%` LRU hit rate at capacity `16` and `40`.
- Exact `count_vector` and `active_set` keys: `914` unique keys, but only
  `1.4%` LRU@16 and `1.8%` LRU@40 hit rate. They repeat over the whole
  dataset but not with useful short-window locality.
- Ordered `topk_tuple` is present only for the routecapture6 subset
  (`285` records). In that subset, all `285` ordered routes are unique, so
  exact ordered-route kernels have no reuse signal.
- Count histogram has `1` key because c1 decode mostly routes `8` assignments
  as `8x1`; this is useful for generic primitive sizing, not for exact route
  specialization.

Layer-9/14/21 routecapture6-only control:

- `285` records, `3` layers.
- Primitive key: `3` unique, `98.9%` LRU@40.
- Active-set/count-vector key: `282` unique, `1.1%` LRU@40.
- Ordered top-k tuple: `285` unique, `0.0%` reuse.

Decision:

1. **Cache resident oneDNN primitives by layer/shape, not exact route.**
   The right first integration is a small per-layer cache of packed weights,
   primitive descriptors, memory descriptors, and reusable buffers. Runtime
   should mutate offsets/counts and scales, then execute.

2. **Do not build exact active-set layerlet caches.**
   Exact active-set and ordered-route reuse is too weak at short cache sizes.
   Generated layerlets must target broader hot-expert or route classes, or they
   should be emitted only for fixtures that prove locality separately.

3. **Keep hot-expert planning as the route-specialization branch.**
   The earlier hotset and flight-recorder results remain the better way to
   specialize route work: pack/replicate hot experts by layer, with current XPU
   or oneDNN fallback for cold experts.

4. **Next implementation gate is now clearer.**
   Build a vLLM/XPU sidecar around resident per-layer oneDNN primitives with
   mutable offsets. The gate is full-layer `max_abs_diff=0.0` versus
   `xpu_fused_moe`, then timing below the `168 us/layer` non-speculative
   budget.

## 2026-06-12 Resident OneDNN Mutable-Offset Route Windows

Patch:

- `tools/onednn_moe_island_resident_runner.cpp` now accepts
  `ONEDNN_ROUTE_COUNTS_CSV`.
- In route-window mode it keeps both oneDNN grouped-matmul primitives, weights,
  and buffers resident, then mutates grouped src/dst offsets from real route
  count windows before executing GEMM1 and GEMM2 with one host wait.

Artifacts:

- `data/qwen36-onednn-moe-island-layer9-r1-resident-routewindows-20260612bb.json`.
- `data/qwen36-onednn-moe-island-layer9-r1-resident-routewindows-rerun-20260612bb.json`.
- `data/qwen36-quark-int8-tp4-accepted-restored-after-onednn-routewindow-resident-20260612bb.log`.
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-onednn-routewindow-resident-20260612bb.json`.

Command shape:

```bash
ONEDNN_GEMM1_META=$PWD/data/qwen36-onednn-moe-island-layer9-r1-20260612ay/gemm1.meta \
ONEDNN_GEMM2_META=$PWD/data/qwen36-onednn-moe-island-layer9-r1-20260612ay/gemm2.meta \
ONEDNN_ROUTE_COUNTS_CSV=$PWD/data/qwen36-quark-int8-routecapture6-layer9-r1-start0-64x4-counts-20260612aw.csv \
ONEDNN_PAIR_JSON=$PWD/data/qwen36-onednn-moe-island-layer9-r1-resident-routewindows-rerun-20260612bb.json \
ONEDNN_PAIR_WARMUP=100 \
ONEDNN_PAIR_ITERATIONS=1000 \
ONEDNN_WEIGHT_FORMAT=acb \
RUNNER_BIN=/tmp/qwen36-onednn-moe-island-resident-routewindows-20260612bb \
ONEDNN_SKIP_COMPILE=1 \
DEVICE_SELECTOR=level_zero:0 \
bash scripts/run-onednn-moe-island-resident.sh
```

Results:

- First run:
  - Base resident pair p50 `31.839 us`, mean `56.845 us`.
  - Mutable-offset route-window pair p50 `44.543 us`, mean `44.939 us`.
  - Base GEMM1/GEMM2 raw equality versus exported XPU outputs stayed true.
- Reused-binary rerun:
  - Base resident pair p50 `41.658 us`, mean `38.079 us`.
  - Mutable-offset route-window pair p50 `42.069 us`, mean `42.810 us`.
  - Base GEMM1/GEMM2 raw equality versus exported XPU outputs stayed true.
- Route-window output buffers differ from the base expected outputs
  (`gemm1_diff_vs_base_expected_count=3301`,
  `gemm2_diff_vs_base_expected_count=26352` in the rerun). This is expected:
  the benchmark mutates grouped route counts over fixed exported input buffers.
  It proves resident offset-update timing and cache viability, not full
  per-window output parity.
- Accepted backend restore after the clean XPU window was healthy after `64s`;
  provenance passed both prefix cases and all sentinel tokens.

Interpretation:

- A per-layer resident oneDNN primitive cache with mutable offsets remains the
  best immediate non-speculative implementation branch. The route-window
  overhead sits around `42 us` for the two GEMMs, comfortably below the old
  two-dispatch XPU floor and leaving budget for activation/quant/gather in a
  full island.
- The next exactness gate must eliminate the fixed-buffer caveat: export or
  directly hand off real per-window remapped inputs/scales so each route-window
  output can compare against current `xpu_fused_moe` or the staged exact path.
- If full-island timing stays below `168 us/layer` with `max_abs_diff=0.0`,
  wire the cache as a vLLM/XPU sidecar. If it does not, move the same ABI to a
  generated DPAS layerlet or exact target-verified speculation branch.

## 2026-06-12 Addendum: Current Queue And Larger Opportunities

This addendum captures the next items after the resident oneDNN mutable-offset
route-window result. It is deliberately quality-conservative: every promoted
path keeps the current Quark W8A8 INT8 model as the verifier/source of truth.

### Immediate Notes To Carry Forward

1. **Multi-window exactness packet is now the next gate.**
   The resident route-window benchmark proved offset-update cost and primitive
   reuse, but it reused fixed exported inputs. The next replay must export or
   directly hand off real per-window remapped inputs, activation scales, route
   rows, and expected outputs for all route starts in `0:64:4`. Promotion
   criteria: GEMM1 diff `0.0`, GEMM2 diff `0.0`, and final gathered MoE island
   diff `0.0` against current `xpu_fused_moe` for every window.

2. **Use resident oneDNN as the sidecar contract, not just a benchmark.**
   Define the sidecar ABI around resident packed expert weights, resident
   primitives, mutable offset/count buffers, preallocated activation/quant
   scratch, and one provenance JSON per layer/window. That ABI can later route
   to oneDNN, Triton-XPU, or a custom DPAS layerlet without changing the
   correctness harness.

3. **Budget the full layer from the measured GEMM floor.**
   The current mutable-offset two-GEMM route-window floor is about `42 us`.
   The non-speculative `200 tok/s` target implies roughly `168 us/layer` for
   the whole layer replay, leaving about `126 us` for remap, quant1,
   activation, quant2, gather, queue overhead, and host waits. Any full-island
   prototype that cannot stay near that envelope should be treated as a
   correctness/profiling asset, not a speed candidate.

4. **Route-signature caching should stay broad.**
   The cache-analysis result says primitive-cache keys should be based on
   stable layer/shape/layout state with mutable offsets, not exact ordered
   route signatures. Exact active-set or ordered-route layerlets should be
   generated only when a prompt-class fixture proves enough locality.

5. **Do not post tiny public deltas as wins.**
   The public Localmaxxing row is already a quality-cleared `~99-100 tok/s`
   exact-model result. A fresh post should either add materially better speed
   (`105+`, preferably `120+` or a real `200+` class result), stronger metrics
   such as peak VRAM/repeat quality, or a genuinely new implementation class.
   Localmaxxing API auth must stay outside the repo.

### Things To Try Next

1. **Multi-window file-backed exact replay.**
   Extend the oneDNN MoE island replay to run all real route-count windows,
   compile the oneDNN runner once, and emit a compact summary with max diffs,
   checksums, per-window row histograms, and per-window timing. This is the
   immediate reproducibility packet before any sidecar wiring.

2. **In-process sidecar smoke for one layer.**
   Build a narrow vLLM/XPU sidecar path for a single fixed layer and route
   window. The first version can still call separate kernels if it owns the
   buffers and parity logs. The second version must remove at least one host
   process/file boundary and one hot allocation boundary.

3. **Command-stream trace of the accepted decode token.**
   Capture a Level Zero/SYCL timeline for one accepted p512/o128 decode token:
   kernel count, command-list boundaries, waits, copies, all-reduces, and MoE
   substeps. The question is whether the missing `2x` is mainly kernel math,
   launch/control overhead, collectives, or scheduler metadata churn.

4. **DPAS/XMX utilization proof.**
   Profile the current XPU grouped GEMM, packed oneDNN grouped matmul, and any
   generated layerlet candidate for actual INT8 DPAS/XMX occupancy. If the hot
   path is not issuing the intended B70 matrix instructions efficiently, the
   priority shifts to layout/kernel generation rather than vLLM flags.

5. **OpenVINO/oneDNN GenAI feasibility lane.**
   Track OpenVINO/oneDNN GenAI only as an 8-bit/high-fidelity engine
   diagnostic for B70/Qwen3.6. Do not switch production unless it supports the
   actual Qwen3.6 A3B/GDN/MoE path, 32K context, and the same quality gates.

6. **cuDNN-style routing ABI check.**
   Even though cuDNN is not our backend, its grouped-MoE API shape around
   `first_token_offset` is a useful sanity check. Keep our sidecar route
   descriptors similarly compact: counts/offsets and packed token blocks,
   not bulky per-token host-side metadata in the hot loop.

7. **TritonMoE/SonicMoE idea mining without backend drift.**
   Extract ideas from fused dispatch, fused gate+up, in-register activation,
   and IO-aware epilogues, then implement only the pieces that can be proven
   exact on the current Quark W8A8 route fixtures. Do not depend on non-XPU
   kernels for a promoted path.

### Bigger, Bolder Ideas To Keep Alive

1. **B70-resident MoE microservice per rank.**
   Keep a long-lived per-rank worker with resident packed weights, route
   buffers, scratch arenas, and command lists. vLLM sends compact route
   descriptors; the worker returns layer outputs. This attacks dispatcher,
   allocation, and primitive setup overhead directly while preserving a simple
   fallback to the current `xpu_fused_moe` path.

2. **Whole-token static graph lane.**
   Build a c1-only latency lane that captures more than one layerlet: fixed
   request metadata, fixed KV/GDN state arenas, fixed sampling, and a certified
   graph cache. It can coexist with the general TP4 service. The purpose is to
   quantify and possibly remove scheduler/control overhead for common chat
   shapes without reducing model quality.

3. **Hybrid TP/EP with hot-expert replication.**
   Use routecapture histograms to simulate expert ownership and selective hot
   expert duplication under 32K KV constraints. If a small set of layer/expert
   replicas can cut collectives or imbalance, implement it behind an exact
   routing table. This is larger than a kernel patch but may be the cleanest
   non-speculative way to beat pure TP4 c1 latency.

4. **Target-verified speculative transaction engine.**
   Treat speculation as an engine-state problem, not just a draft-model knob:
   immutable KV aliases, versioned mutable GDN/request metadata, exact target
   verification, and accept/rollback logs. This keeps MTP, n-gram, DFlash, or
   target-trace proposers quality-safe because only verified target tokens
   commit.

5. **Route-exact public upstream packet.**
   Publish a small no-secret packet for Intel/vLLM: route windows, packed
   oneDNN fixtures, expected bytes, accepted baseline command, command-stream
   trace, and device-lost notes. The ask should be concrete: beat the current
   packed oneDNN and vLLM XPU W8A8 MoE timings while preserving exact outputs.

6. **Tile-native weight artifact shared across engines.**
   Create a checksumed packed-weight cache for the fastest proven B70 layout.
   It should be engine-neutral enough for vLLM sidecar, oneDNN runner, and
   custom layerlets. If this works, startup repack and runtime layout penalties
   both disappear without changing quantization.

7. **Minimal exact decode executable.**
   Build a small offline executable that runs the same tokenizer, prompt
   template, Quark W8A8 weights, and greedy sampler for one fixed c1 bucket,
   bypassing vLLM scheduling. If it is not faster, kernels are the wall. If it
   is much faster, production should get a latency lane or vLLM scheduler patch.

8. **B70 host-stack certification matrix.**
   Make a reversible matrix across kernel/KMD, GuC firmware, compute-runtime,
   oneAPI, oneCCL, PyTorch, and vLLM-XPU kernels. The target metric is not only
   tok/s; it is variance, device-lost rate, graph-cache repeatability, and
   whether the accepted sidecar fixtures remain exact across stacks.

9. **Persistent zero-gap MoE kernel clone.**
   Intel's own B-series vLLM write-up says the major MoE loss comes from per
   iteration GEMM launch overhead, routing-dependent stalls, and imbalanced
   expert work assignment. Treat that as the reference design: one persistent
   XPU kernel per rank, resident packed W8A8 weights, route offsets in device
   memory, and an atomic block queue so fast work-groups immediately steal the
   next expert tile. This is a bigger lift than a oneDNN sidecar, but it is the
   most direct path to a step-function single-user decode gain without changing
   model math.

10. **Exact speculative lane using real Qwen3.6 target verification.**
    Localmaxxing rows for adjacent Qwen3.6 setups show large wins from MTP /
    DFlash-style speculation when the implementation verifies against the
    target model before committing tokens. This is quality-safe only if every
    accepted token is target-verified and rollback is logged. Keep it as a
    second lane after the non-speculative sidecar, because it can stack with
    kernel work but should not mask slow base kernels.

11. **B70 one-instance-per-card mirror for low-latency routing.**
    A leaderboard B70 setup reports strong aggregate throughput by running one
    single-GPU instance per card instead of one TP instance. It uses lower
    fidelity Q4, so it is not directly acceptable, but the topology lesson is
    useful: compare TP4 single-request latency against four replicated W8A8
    runtimes behind a latency-aware router. If the replicated lane fits 32K on
    one card with this quant, it can remove TP all-reduce from the c1 path and
    reserve TP4 for longer contexts or batch throughput.

12. **Upstream W8A8 artifact and calibration lane.**
    The open `llm-compressor` Qwen3.6 W8A8 issue calls out missing tested
    registry/mapping support for `Qwen3_5MoeForConditionalGeneration`, fused
    MoE expert tensors, and hybrid GDN/full-attention linears. Even if the
    current Quark model remains the production candidate, building a clean
    calibration/export lane would let us compare Quark against a native
    compressed-tensors or upstream W8A8 artifact with the same eval gates.

13. **Host-stack A/B as a speed feature, not just reliability work.**
    The B70/vLLM crash issue shows that kernel/KMD/GuC/Level Zero/oneCCL
    choices change both stability and usable XPU graph/collective paths. Treat
    a spare-disk Ubuntu 25.x or Intel-validated BOM test as a performance
    experiment: same model, same prompt/eval gates, same benchmark harness,
    but a stack that may unlock graph capture, SYCL collectives, or lower
    variance without code changes.

External references to keep attached to this queue:

- oneDNN grouped matmul/grouped memory for MoE and Intel GPU optimization:
  `https://github.com/uxlfoundation/oneDNN/releases`.
- oneDNN grouped encoding examples:
  `https://uxlfoundation.github.io/oneDNN/dev_guide_examples.html`.
- Intel oneDNN 2026 notes for Xe2/Xe3 LLM matmul work:
  `https://www.intel.com/content/www/us/en/developer/articles/release-notes/onednn/2026.html`.
- Intel/vLLM Arc Pro B-series MoE persistent-kernel direction:
  `https://vllm.ai/blog/2025-11-11-intel-arc-pro-b`.
- Intel Triton-XPU grouped-GEMM tuning issue:
  `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`.
- PyTorch persistent cache-aware grouped GEMM article:
  `https://pytorch.org/blog/accelerating-moes-with-a-triton-persistent-cache-aware-grouped-gemm-kernel/`.
- Triton grouped-GEMM tutorial as a compact device-side scheduling reference:
  `https://triton-lang.org/main/getting-started/tutorials/08-grouped-gemm.html`.
- vLLM MoE kernel feature matrix:
  `https://docs.vllm.ai/en/latest/design/moe_kernel_features/`.
- cuDNN MoE grouped matmul routing API as an ABI comparison point:
  `https://docs.nvidia.com/deeplearning/cudnn/latest/operations/MoeGroupedMatmul.html`.
- Cross-platform fused MoE dispatch paper:
  `https://arxiv.org/html/2605.23911v1`.
- SonicMoE IO-aware MoE design notes:
  `https://tridao.me/blog/2026/sonicmoe-blackwell/`.
- Intel B-series vLLM persistent zero-gap MoE kernel write-up:
  `https://vllm.ai/blog/2025-11-11-intel-arc-pro-b`.
- B70/vLLM XPU host-stack stability issue:
  `https://github.com/vllm-project/vllm/issues/41663`.
- Qwen3.6 W8A8 INT8 support request in `llm-compressor`:
  `https://github.com/vllm-project/llm-compressor/issues/2787`.
- vLLM Ascend Qwen3.6-35B-A3B page, useful for architecture and eval
  cross-checks:
  `https://docs.vllm.ai/projects/ascend/zh-cn/v0.18.0/tutorials/models/Qwen3.6-35B-A3B.html`.
- Localmaxxing public Arc/Qwen3.6-35B sweep, checked 2026-06-12:
  `https://localmaxxing.com/api/leaderboard?hfId=Qwen%2FQwen3.6-35B-A3B&hwClass=DISCRETE_GPU&hardwareName=Arc&limit=20`.

## 2026-06-12 Multi-Window oneDNN MoE Island Exactness Packet

Patch:

- `scripts/replay-qwen36-onednn-moe-island.py` now supports
  `--route-start-indices`, including range syntax such as `0:64:4`.
- In multi-window mode it writes one subdirectory per route window and reuses
  the first window's large expert-weight dumps through relative meta paths, so
  only per-window activations, rows, expected outputs, and JSON summaries vary.
- The script now fails fast if the local `vllm_xpu_kernels` ops are not loaded,
  with an explicit reminder to set `PYTHONPATH` and `LD_LIBRARY_PATH` like the
  accepted service launcher.

Command shape:

```bash
PYTHONPATH=/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels \
LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:${LD_LIBRARY_PATH:-} \
/home/steve/.venvs/vllm-xpu/bin/python scripts/replay-qwen36-onednn-moe-island.py \
  --out-dir data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc \
  --route-start-indices 0:64:4 \
  --rows 1 \
  --warmup 20 \
  --iterations 100 \
  --case-bin /tmp/qwen36-onednn-moe-island-case-runner-multiwindow-20260612bc
```

Artifacts:

- `data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/multi_window_onednn_moe_island_result.json`.
- Per-window `gemm1.meta`, `gemm2.meta`, `*_onednn_acb_result.json`, and
  `onednn_moe_island_result.json` under
  `data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/window_*`.
- Raw `.bin` payloads are ignored recursively under
  `data/qwen36-onednn-moe-island-*`; they are regeneration artifacts, not
  GitHub payloads.
- Restore/provenance:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-multiwindow-20260612bc.log`
  and
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-multiwindow-20260612bc.json`.

Result:

- Replayed 16 real route windows for layer 9, route starts
  `0,4,8,12,16,20,24,28,32,36,40,44,48,52,56,60`.
- `all_exact=true`.
- Aggregate max diffs are all `0.0`:
  - `gemm1_vs_xpu_max_abs_diff`
  - `gemm2_vs_xpu_max_abs_diff`
  - `staged_vs_xpu_fused_moe_max_abs_diff`
  - `onednn_island_vs_xpu_fused_moe_max_abs_diff`
  - `onednn_island_vs_staged_max_abs_diff`
- oneDNN packed `acb` timing ranges over the windows:
  - GEMM1 mean `31.818-61.452 us`, p50 `31.719-58.891 us`.
  - GEMM2 mean `26.536-40.776 us`, p50 `26.370-40.506 us`.
- Accepted backend restore was healthy after `63s`; the provenance guard passed
  all sentinels after the clean XPU replay window.

Interpretation:

- This eliminates the fixed-buffer caveat from the previous resident
  route-window timing packet. Each window now regenerates the real remapped
  hidden input, per-token scales, oneDNN GEMM outputs, activation/quant2, and
  final gather for that captured route slice.
- The correctness case for a oneDNN-backed vLLM/XPU sidecar is now stronger:
  packed oneDNN GEMMs are byte-equivalent to current XPU GEMMs, and the full
  MoE island remains exact versus `xpu_fused_moe` over a route-window set.
- The next implementation step should be an in-process sidecar smoke that owns
  resident buffers and removes the Python/file/process boundaries while keeping
  this multi-window packet as the regression gate.

## 2026-06-12 Resident oneDNN Multi-Window Two-GEMM Smoke

Patch:

- `tools/onednn_moe_island_resident_runner.cpp` now supports
  `ONEDNN_WINDOW_MANIFEST`.
- The manifest mode loads all window `gemm1.meta,gemm2.meta` pairs once,
  keeps one resident oneDNN primitive and one resident packed weight/scales set
  per GEMM, and cycles per-window source/scales/offset/destination memory
  objects already resident on the device.
- `scripts/run-qwen36-onednn-resident-multiwindow.sh` builds the manifest from
  a multi-window replay directory and runs the resident C++ path.

Command shape:

```bash
RUNNER_BIN=/tmp/qwen36-onednn-moe-island-resident-compilecheck-20260612bd \
ONEDNN_SKIP_COMPILE=1 \
WARMUP=80 \
ITERATIONS=1000 \
OUT_JSON=data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/resident_multiwindow_pair_result_20260612bd.json \
MANIFEST=data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/resident_multiwindow_manifest_20260612bd.csv \
scripts/run-qwen36-onednn-resident-multiwindow.sh
```

Artifacts:

- `data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/resident_multiwindow_manifest_20260612bd.csv`.
- `data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/resident_multiwindow_pair_smoke_20260612bd.json`.
- `data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/resident_multiwindow_pair_result_20260612bd.json`.
- `data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/resident_multiwindow_pair_repeat_20260612bd.json`.
- Restore/provenance:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-resident-multiwindow-20260612bd.log`
  and
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-resident-multiwindow-20260612bd.json`.

Result:

- Smoke: 16/16 exact windows, total raw diff `0` for both GEMMs, resident pair
  p50 `123.321 us`, mean `122.164 us`.
- Timed run: 16/16 exact windows, total raw diff `0` for both GEMMs, resident
  pair p50 `32.111 us`, mean `42.384 us`, p90 `90.179 us`.
- Repeat: 16/16 exact windows, total raw diff `0` for both GEMMs, resident
  pair p50 `35.527 us`, mean `36.205 us`, p90 `38.452 us`.
- Accepted backend restore was healthy after `64s`; the provenance guard passed
  all sentinels after the clean XPU resident run.

Interpretation:

- This removes the file/process/primitive setup boundary from the two oneDNN
  GEMMs across the real multi-window route packet. It is the first successful
  resident sidecar-style timing over changing real window inputs.
- It is not a full MoE island yet. GEMM2 input is the captured
  post-activation/per-token-quant tensor for each window; activation, quant2,
  final gather, and vLLM scheduler integration are still outside this runner.
- The result says the two-GEMM floor is not the whole bottleneck. The next
  sidecar step should pull activation+quant2 into the resident process and
  then add a vLLM-rank call site or extension hook that passes device pointers
  instead of file-backed fixtures.

## 2026-06-12 Added Backlog From Post-Resident Discussion

User priorities to keep attached to every Qwen3.6 run:

- Current model only: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`.
- No AWQ, no 4-bit, no Qwen3.5 substitution, and no lower-quality speed path.
- c1 decode speed is the primary target. Aggregate throughput matters after c1
  is healthy.
- Quality must be validated several ways: exact canaries, rolling next-token
  verifier, prompt-class outputs, long-context checks, and BF16 or accepted
  baseline comparison when available.
- Keep GitHub notes, code, commands, and artifacts current enough that a clean
  machine can reproduce the important claims.

Items added to the immediate try queue:

1. **Gate fused SiLU plus INT8 quant before enabling it.**
   Previous fused SiLU/quant work drifted, so do not flip
   `VLLM_XPU_FUSED_MOE_FUSE_SILU_QUANT=1` in the endpoint until a fixture
   proves byte or exact integer parity against captured route windows. Use the
   multi-window oneDNN packet to compare current fused-kernel `q` and scales
   against the accepted two-step activation plus per-token quant path. If it is
   exact, benchmark it as a narrow A/B. If it drifts, keep it rejected and move
   on.

2. **Finish the resident full-MoE island before deeper endpoint surgery.**
   The resident two-GEMM p50 is around `32-36 us` across 16 real windows, so
   GEMM alone is not the full token bottleneck. Add activation, quant2, top-k
   weighting, and gather inside the resident runner next. Only after full-island
   exactness and timing are known should we wire the sidecar into a vLLM rank.

3. **Create a device-pointer ABI smoke for one vLLM rank.**
   The next useful integration proof is a tiny custom op or C++ extension that
   receives live device pointers for hidden states, route ids, weights, scales,
   and output. No files, no host copies, no runner process. Start with layer 9
   only and fall back to `xpu_fused_moe` for every other shape.

4. **Measure the missing token budget with queue profiling.**
   Since the resident GEMM pair is far below observed per-token latency, add a
   low-overhead token trace that includes attention, GDN, MoE non-GEMM work,
   collectives, graph replay, scheduler metadata movement, sampling, and stream
   waits. Use Level Zero/SYCL event timing where possible rather than Python
   wrappers, because compiled graph replay hides Python boundaries.

5. **Mine Localmaxxing, but submit only material wins.**
   The public exact-model row remains `99.428 tok/s` c1 on 4x Arc Pro B70.
   Do not repost noise. Post the next result only if it is a clean material
   improvement with command snippet, exact model revision, context length,
   batch size, quality proof, and preferably peak VRAM.

6. **Add a stack/BOM lane as a performance experiment.**
   Intel B70 reports keep pointing at kernel, KMD, oneAPI, oneCCL, and container
   version sensitivity. Test an Intel-validated or newer llm-scaler stack on a
   separate lane with the same model and quality gates. Treat this as an
   optimization candidate, not just reliability cleanup.

7. **Keep BF16 comparison scoped and honest.**
   BF16 is too slow for production, but it is still a useful quality reference
   for a small, fixed suite. Compare next-token decisions, logprob ordering, and
   task outputs against the accepted INT8 path and BF16 fallback where the BF16
   model can run. The promotion rule remains: speed changes must preserve the
   accepted target-model behavior.

## Bigger Bolder Ideas Worth Exploring

These are not all near-term patches, but they are the kinds of changes that
could plausibly move c1 from around `100 tok/s` toward the `>200 tok/s` goal
without reducing model quality.

1. **Single-call exact MoE island.**
   Replace the current multi-kernel MoE path for Qwen3.6 with one exact island
   call per MoE layer: route remap, W8A8 GEMM1, SiLU/up-gate, quant2, W8A8
   GEMM2, top-k weighting, and gather. The first version can use oneDNN for the
   GEMMs and custom kernels for the glue. Later versions can specialize hot
   route classes. The key is removing launch/control overhead while keeping the
   exact accepted math.

2. **Hybrid TP plus replicated hot-expert topology.**
   TP4 may be spending too much c1 time on communication and small grouped
   GEMM shape overhead. Simulate and test a topology where dense attention
   remains tensor-parallel, but hot MoE experts or whole hot layers are
   replicated across ranks so the common route classes execute locally. This is
   quality-preserving because weights are duplicated, not approximated. The
   tradeoff is VRAM and startup packing cost.

3. **Expert-parallel side lane for MoE only.**
   Build a narrow MoE execution lane that routes tokens to expert-owning ranks
   rather than forcing every layer through the same TP4 abstraction. This may
   be worse for aggregate traffic, but c1 could improve if it removes repeated
   allreduce or shard-gather overhead around small MoE work.

4. **Route-class generated kernels.**
   From live traces, generate exact kernels for the few dominant
   `(active experts, rows per expert)` signatures. oneDNN stays as fallback and
   oracle. A generated kernel can bake in offsets, small-M dimensions, and
   epilogue layout, removing generic grouped-GEMM overhead for the hot path.

5. **Persistent MoE worker per rank.**
   Instead of submitting many small kernels from Python/vLLM, keep a long-lived
   rank-local worker that receives compact route descriptors and dispatches
   prebuilt oneDNN primitives or specialized kernels. This targets the
   launch/control floor directly and matches Intel's public persistent
   zero-gap MoE direction.

6. **Exact speculative sidecar, target verified.**
   Speculation can be quality-neutral if the current Qwen3.6 INT8 model remains
   the verifier and rejected draft tokens never escape. Revisit only after the
   verifier path is stable and measurable. Candidate drafters: n-gram with
   fixed acceptance accounting, a tiny local model on spare CPU/GPU capacity,
   or future Qwen MTP weights if an exact-compatible W8A8 artifact exists.

7. **Production single-sequence fast lane.**
   Add a special c1 path for the common "one active user, long-lived chat"
   case. It can bypass some generic scheduler and batching machinery while
   preserving the same OpenAI-compatible surface and falling back to the normal
   vLLM path under concurrency. This is a product-level speed path, not a model
   shortcut.

8. **OpenVINO or oneDNN-Graph conversion lane.**
   Try a separate exactness-gated export path for this Qwen3.6 architecture.
   It may fail on Gated DeltaNet or Quark metadata, but if it runs it could
   expose Intel-optimized graph fusions unavailable through the current vLLM
   stack. Promotion requires token/logprob parity against the accepted endpoint.

9. **Upstream challenge packet for Intel/vLLM.**
   Publish the tiny route-window fixtures, exact expected bytes, and resident
   oneDNN timings as a focused B70 W8A8 MoE challenge. The ask is narrow:
   produce a faster exact XPU grouped-MoE path for these route signatures. This
   is more actionable than reporting "13 tok/s is slow" because it gives the
   kernel team a deterministic reproducer.

10. **Compiler/runtime fork lane with no endpoint pressure.**
    Keep one branch where we are willing to patch vLLM/XPU kernels, oneDNN,
    Triton-XPU, and oneCCL together. It should run offline fixtures first and
    only later touch the service. This is where larger changes like fused
    collective epilogues, route-aware primitive caches, and graph-captured MoE
    workers belong.

11. **VRAM-for-latency trade study.**
    The model memory looks small per rank because TP4 shards the W8A8 weights;
    the total still lines up with an INT8 35B-class model once all ranks and KV
    cache are counted. Use remaining VRAM deliberately: duplicate hot packed
    weights, keep more graph buckets warm, cache route-class primitives, and
    reserve scratch buffers to eliminate allocator churn.

12. **A real "red team" quality harness for speed patches.**
    Add a small but hostile suite that catches the kinds of failures already
    observed: broken HTML/JS generation, repeated words, JSON schema drift,
    long-context misses, code syntax errors, and next-token hash drift. Every
    candidate speed row should point to this suite before being called a win.

Fresh external signals from the follow-up scan:

- Localmaxxing still has one approved exact-model B70/vLLM row for this setup:
  `99.428 tok/s` output, `196.325 tok/s` total, `76.454 ms` TTFT, c1, 32K.
  API query:
  `https://localmaxxing.com/api/leaderboard?hfId=nameistoken%2FQwen3.6-35B-A3B-Quark-W8A8-INT8&hardwareName=Arc%20Pro%20B70&engineName=vllm&limit=20`.
- oneDNN grouped memory/grouped matmul remains directly relevant because it is
  explicitly MoE-oriented and optimized for Intel GPUs:
  `https://uxlfoundation.github.io/oneDNN/dev_guide_experimental.html`.
- Intel/vLLM's B-series article explicitly points at persistent zero-gap MoE
  kernels as the intended way around launch overhead, gate dependency stalls,
  and group imbalance:
  `https://vllm.ai/blog/2025-11-11-intel-arc-pro-b`.
- Public B70/vLLM crash reports keep justifying the stack/BOM lane:
  `https://github.com/vllm-project/vllm/issues/41663`.
- Public Arc Pro B70 user reports still suggest the hardware is ahead of the
  software stack for LLM serving; this argues for focused kernel/runtime work
  rather than abandoning the model or dropping quantization quality:
  `https://forum.level1techs.com/t/intel-b70-launch-unboxed-and-tested/247873`
  and
  `https://www.reddit.com/r/LocalLLaMA/comments/1siar7y/intel_arc_pro_b70_32gb_performance_on_qwen3527bq4/`.

## 2026-06-12 Fused SiLU+INT8 Quant Multi-Window Gate

Patch:

- Added `scripts/check-qwen36-silu-quant-parity.py`.
- The script loads the layer-9 multi-window oneDNN MoE packet, runs the current
  installed `_xpu_C.silu_and_mul_quant_int8_xpu` kernel, and compares its
  `q` and scale outputs against captured accepted GEMM2 inputs.
- It also reruns the current accepted two-step path,
  `fused_moe_activation(..., "silu")` plus
  `_xpu_C.per_token_quant_int8_xpu`, to separate fixture drift from fused
  kernel drift.
- The active extension build exposes `silu_and_mul_quant_int8_xpu` and
  `per_token_quant_int8_xpu`; the `_out` variants are still absent in the
  installed runtime.

Commands:

```bash
PYTHONPATH=/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels \
LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:${LD_LIBRARY_PATH:-} \
/home/steve/.venvs/vllm-xpu/bin/python scripts/check-qwen36-silu-quant-parity.py \
  --source xpu \
  --out-json data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/silu_quant_parity_xpu_20260612be.json

PYTHONPATH=/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels \
LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:${LD_LIBRARY_PATH:-} \
/home/steve/.venvs/vllm-xpu/bin/python scripts/check-qwen36-silu-quant-parity.py \
  --source onednn \
  --out-json data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/silu_quant_parity_onednn_20260612be.json
```

Artifacts:

- `data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/silu_quant_parity_xpu_20260612be.json`.
- `data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/silu_quant_parity_onednn_20260612be.json`.
- Restore/provenance:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-siluquant-parity-20260612be.log`
  and
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-siluquant-parity-20260612be.json`.

Result:

- XPU-source packet:
  - `window_count=16`
  - `all_fused_q_exact=false`
  - `all_fused_scales_exact=false`
  - `all_twostep_q_exact=true`
  - `all_twostep_scales_exact=true`
  - `max_fused_q_diff_count=35`
  - `max_fused_scale_abs_diff=0.0019685328006744385`
- oneDNN-source packet:
  - same summary as XPU-source.
- Accepted backend restored healthy after `64s`; provenance guard passed all
  sentinels.

Decision:

- Keep `VLLM_XPU_FUSED_MOE_FUSE_SILU_QUANT` off.
- The current installed fused SiLU+INT8 quant kernel is not exact on real
  route windows. It changes INT8 values by up to `2` and scale values by up to
  about `0.00197`, while the accepted two-step path reproduces the captured
  GEMM2 input exactly for both captured XPU and oneDNN GEMM1 sources.
- This reinforces the earlier endpoint decision in
  `notes/2026-06-10-qwen36-exact-siluq-rejected.md`: even a more exact fused
  variant was too small and failed repeat stability. The next path to
  `>200 tok/s` should be the resident full-MoE island and device-pointer ABI,
  not enabling the current fused SiLU quant shortcut.

## 2026-06-12 Resident GEMM1 -> SiLU+INT8 Quant -> GEMM2 Bridge

Patch:

- Extended `tools/onednn_moe_island_resident_runner.cpp` with opt-in
  `ONEDNN_PAIR_INCLUDE_ACTIVATION_QUANT=1`.
- The resident pair runner now supports the exact accepted island sequence:
  oneDNN GEMM1, an in-process SYCL BF16 SiLU+INT8 quant bridge, then oneDNN
  GEMM2.
- The bridge writes directly from GEMM1 resident dst memory into GEMM2 resident
  src memory and source-scale memory. It uses the accepted BF16 semantics:
  BF16 gate, BF16 SiLU, BF16 multiply, row absmax, INT8 round/clamp.
- This is deliberately separate from the rejected installed
  `_xpu_C.silu_and_mul_quant_int8_xpu` shortcut. The shortcut is faster-looking
  but not exact on these real route windows; this resident bridge is exact.

Commands:

```bash
RUNNER_BIN=/tmp/qwen36-onednn-moe-island-resident-fullisland-compile-20260612bf \
bash scripts/run-onednn-moe-island-resident.sh --compile-only

RUNNER_BIN=/tmp/qwen36-onednn-moe-island-resident-fullisland-compile-20260612bf \
ONEDNN_SKIP_COMPILE=1 \
ONEDNN_PAIR_INCLUDE_ACTIVATION_QUANT=1 \
WARMUP=20 \
ITERATIONS=100 \
OUT_JSON=data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/resident_multiwindow_full_silu_quant_pair_smoke_20260612bf.json \
MANIFEST=data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/resident_multiwindow_full_silu_quant_manifest_20260612bf.csv \
bash scripts/run-qwen36-onednn-resident-multiwindow.sh

RUNNER_BIN=/tmp/qwen36-onednn-moe-island-resident-fullisland-compile-20260612bf \
ONEDNN_SKIP_COMPILE=1 \
ONEDNN_PAIR_INCLUDE_ACTIVATION_QUANT=1 \
WARMUP=80 \
ITERATIONS=1000 \
OUT_JSON=data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/resident_multiwindow_full_silu_quant_pair_result_20260612bf.json \
MANIFEST=data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/resident_multiwindow_full_silu_quant_manifest_20260612bf.csv \
bash scripts/run-qwen36-onednn-resident-multiwindow.sh
```

Artifacts:

- `data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/resident_multiwindow_full_silu_quant_manifest_20260612bf.csv`.
- `data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/resident_multiwindow_full_silu_quant_pair_smoke_20260612bf.json`.
- `data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/resident_multiwindow_full_silu_quant_pair_result_20260612bf.json`.
- `data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/resident_multiwindow_full_silu_quant_pair_repeat_20260612bf.json`.
- Restore/provenance:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-full-siluquant-resident-20260612bf.log`
  and
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-full-siluquant-resident-20260612bf.json`.

Result:

- Smoke: `p50=108.825 us`, `mean=108.636 us`, `exact_windows=16/16`,
  `gemm1_total_diff=0`, `gemm2_total_diff=0`.
- Timed run: `p50=36.258 us`, `mean=55.248 us`, `p90=105.768 us`,
  `exact_windows=16/16`, `gemm1_total_diff=0`, `gemm2_total_diff=0`.
- Repeat: `p50=47.169 us`, `mean=45.762 us`, `p90=52.238 us`,
  `exact_windows=16/16`, `gemm1_total_diff=0`, `gemm2_total_diff=0`.
- Accepted backend restored afterward; provenance guard passed all sentinel
  positions.

Interpretation:

- This is a strong exactness gate for the resident oneDNN MoE-island path:
  GEMM1, accepted BF16 SiLU+INT8 quant2, and GEMM2 now compose exactly across
  the 16 real route windows.
- This is still not an endpoint speed result. It does not yet include top-k
  weighting/final gather, rank device-pointer ABI, vLLM scheduler integration,
  or production reliability soak.
- The result is still important because the activation/quant bridge did not
  destroy the resident timing profile. The next meaningful lab milestone is a
  full resident layer output that matches `xpu_fused_moe` exactly, then a
  device-pointer ABI smoke inside the vLLM rank.

Things to try immediately:

1. **Add exact top-k weight and final gather to the resident runner.**
   Consume the captured top-k weights and route map, write final BF16 hidden
   output, and compare the full layer against `xpu_fused_moe` bytes/values.
   This closes the last local correctness gap before any vLLM integration.

2. **Build the rank-local device-pointer ABI smoke.**
   Call the resident island from inside one vLLM rank using live device
   pointers for hidden states, route metadata, and output buffers. Start with a
   disabled-by-default diagnostic hook that runs both current and resident
   paths and compares output before returning the current path.

3. **Cache resident oneDNN objects by route signature.**
   The runner still records `~120 ms` construction cost. Production needs
   prebuilt primitives and packed weights per layer/GEMM, with per-token
   updates limited to route offsets, source handles, and scale handles.

4. **Measure command submission and queue waits around the bridge.**
   The bridge currently sits between two oneDNN executes with one final wait.
   Use Level Zero/SYCL event timing to decide whether command bundling, in-order
   queues, or explicit dependencies reduce the p90 tail without changing math.

5. **Run windows from more layers before promotion.**
   Repeat the resident full-bridge gate on routecapture layers `14`, `20`, and
   `21`. Layer 9 is the fixture, but production needs proof that route skew and
   expert shapes do not break exactness or timing elsewhere.

6. **Stress resident memory lifetime.**
   Loop thousands of route signatures with create/reuse/evict cycles, watch
   `xpu-smi`, and record device-lost or memory-growth behavior. This is a
   required reliability gate before the endpoint gets a new resident path.

Bigger, bolder ideas unlocked by this result:

1. **Full oneDNN MoE island as a drop-in vLLM custom op.**
   Keep vLLM scheduling/KV/dense layers intact, but replace only the Quark W8A8
   MoE layer with a resident oneDNN-backed island. This is the fastest route
   from a proven lab result to an endpoint A/B while preserving current model
   quality.

2. **Device-resident MoE island manager per rank.**
   Instead of rebuilding or dispatching through Python-side custom-op plumbing
   every layer call, create a long-lived C++ manager that owns packed weights,
   oneDNN primitives, route-signature caches, queues, and diagnostic parity
   hooks. Python only passes compact descriptors.

3. **Route-window autotuned island variants.**
   Generate several exact resident variants for common route windows:
   oneDNN-only, oneDNN plus custom gather, custom activation/quant plus oneDNN,
   and eventually persistent custom kernels. Pick per layer/route class using
   measured parity-gated timing, not static assumptions.

4. **Final-gather fusion into GEMM2 epilogue.**
   Once full gather parity is proven, explore whether top-k weight and gather
   can be fused into the GEMM2 output path or into a single post-GEMM kernel.
   This is a plausible way to remove another launch without touching GEMM math.

5. **Speculation plus faster exact verifier.**
   If the resident island cuts target-model verify cost, revisit target-verified
   speculation. A faster exact verifier makes n-gram/MTP/trace-trained
   proposers much more valuable while preserving exact target output.

6. **OneDNN fixture as an upstream Intel perf packet.**
   Package the resident bridge fixture as a small public challenge:
   real route windows, exact expected GEMM1/GEMM2 bytes, timings, bridge math,
   and the rejected fused shortcut result. This gives Intel/vLLM a precise B70
   W8A8 MoE optimization target.

7. **MoE island roofline from real windows.**
   Compute per-window bytes moved, INT8 ops, BF16 ops, launches, and achieved
   us/op for GEMM1, bridge, GEMM2, and future gather. Use it to decide whether
   the next `2x` win is launch elimination, tile/layout work, memory traffic,
   or parallelism changes.

8. **Latency-lane product architecture around a certified island.**
   If the resident island works but is specialized, make it a production
   latency lane rather than forcing it into every request shape. Route common
   c1 chat shapes to the certified island lane; keep the accepted vLLM lane for
   general 32K/capacity traffic.

## 2026-06-12 Resident Full-Layer Gather Gate

Patch:

- Added `scripts/export-qwen36-onednn-gather-fixtures.py`.
- Extended `tools/onednn_moe_island_resident_runner.cpp` with opt-in
  `ONEDNN_PAIR_INCLUDE_GATHER=1`.
- The resident runner now supports the complete exact layer-9 route-window
  island:
  oneDNN GEMM1 -> exact BF16 SiLU+INT8 quant bridge -> oneDNN GEMM2 ->
  `_moe_C.moe_gather`-equivalent BF16 top-k gather.
- The gather fixture exporter writes only small per-window files:
  `moe_topk_weights.f32.bin`, `moe_topk_ids.i64.bin`,
  `moe_unpermuted.i32.bin`, and `moe_ref_output.bf16.bin`. It deliberately
  does not rewrite the large GEMM weight/input files.

Commands:

```bash
python3 -m py_compile scripts/export-qwen36-onednn-gather-fixtures.py

RUNNER_BIN=/tmp/qwen36-onednn-moe-island-resident-gather-compile-20260612bg \
bash scripts/run-onednn-moe-island-resident.sh --compile-only

PYTHONPATH=/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels \
LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:${LD_LIBRARY_PATH:-} \
/home/steve/.venvs/vllm-xpu/bin/python scripts/export-qwen36-onednn-gather-fixtures.py \
  --manifest data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/resident_multiwindow_full_silu_quant_manifest_20260612bf.csv \
  --out-json data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/gather_fixture_export_20260612bg.json

RUNNER_BIN=/tmp/qwen36-onednn-moe-island-resident-gather-compile-20260612bg \
ONEDNN_SKIP_COMPILE=1 \
ONEDNN_PAIR_INCLUDE_ACTIVATION_QUANT=1 \
ONEDNN_PAIR_INCLUDE_GATHER=1 \
WARMUP=80 \
ITERATIONS=1000 \
OUT_JSON=data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/resident_multiwindow_full_island_gather_result_20260612bg.json \
MANIFEST=data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/resident_multiwindow_full_silu_quant_manifest_20260612bf.csv \
bash scripts/run-qwen36-onednn-resident-multiwindow.sh
```

Artifacts:

- `data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/gather_fixture_export_20260612bg.json`.
- `data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/resident_multiwindow_full_island_gather_smoke_20260612bg.json`.
- `data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/resident_multiwindow_full_island_gather_result_20260612bg.json`.
- `data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/resident_multiwindow_full_island_gather_repeat_20260612bg.json`.
- Restore/provenance:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-full-gather-resident-20260612bg.log`
  and
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-full-gather-resident-20260612bg.json`.

Result:

- Gather fixture export matched every previous file-backed full-island
  reference checksum: each `prior_ref_output_checksum_delta` is `0.0`.
- Full resident smoke: `window_count=16`, `exact_full_window_count=16`,
  `gather_total_raw_diff_count=0`, `p50=88.236 us`, `mean=88.422 us`,
  `p90=90.139 us`.
- Full resident timed run: `window_count=16`, `exact_full_window_count=16`,
  `gather_total_raw_diff_count=0`, `p50=50.404 us`, `mean=48.676 us`,
  `p90=55.494 us`.
- Full resident repeat: `window_count=16`, `exact_full_window_count=16`,
  `gather_total_raw_diff_count=0`, `p50=61.445 us`, `mean=53.445 us`,
  `p90=68.148 us`.
- Accepted backend restored afterward in `33s`; provenance guard passed all
  sentinel positions.

Important run note:

- Do not run two `scripts/run-qwen36-onednn-resident-multiwindow.sh` jobs in
  parallel against the same `MANIFEST`. The script rewrites a temporary manifest
  beside `MANIFEST`, so parallel runs can race and truncate the manifest. The
  invalid parallel timing covered only `5` windows and was discarded; the valid
  results above were rerun serially against all `16` windows.

Interpretation:

- This closes the local correctness scaffold for layer-9 routecapture6 rows=1:
  the resident oneDNN path now matches the current `xpu_fused_moe` final layer
  output exactly across all 16 route windows.
- This is still a lab runner result, not an endpoint speed result. It does not
  yet prove vLLM-rank device-pointer ownership, route-signature cache behavior,
  interaction with live scheduler buffers, or production reliability.
- The timing remains encouraging because adding the final gather did not blow
  up the resident island. The measured full-layer island is still in the same
  tens-of-microseconds class as the prior GEMM1+bridge+GEMM2 resident proof.

Next things to try:

1. **Rank-local device-pointer ABI smoke.**
   Add a disabled-by-default diagnostic call inside one vLLM rank that runs the
   resident island from live device pointers, compares against current
   `xpu_fused_moe`, then returns the current path. This is the next gate before
   any endpoint A/B.

2. **Route-signature cache API.**
   Promote the runner's resident objects into a C++ manager keyed by
   `(layer, active experts, rows-per-expert signature, dtype, layout)`.
   Primitive construction is still a `~120 ms` one-time cost; endpoint use needs
   cached primitives and packed weights.

3. **Gather fusion and epilogue audit.**
   The standalone gather is exact. Now test whether top-k weighting can move
   into a GEMM2 epilogue or one post-GEMM kernel without changing BF16 output.

4. **More layers and route shapes.**
   Repeat the full resident gather gate on layers `14`, `20`, and `21`, and on
   rows greater than `1`. Do not promote a rank hook from a single-layer,
   single-row fixture.

5. **Resident-lifetime stress.**
   Loop thousands of signatures through the resident manager once it exists:
   create/reuse/evict, verify exact output, monitor XPU memory, and record any
   device-lost events before endpoint testing.

## 2026-06-12 Post-Gather Bigger Bets

External signals checked after the full-gather gate:

- Localmaxxing still shows the exact
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` 4x Arc Pro B70 vLLM row as
  the only exact-model public row returned by the API, with `tokSOut=99.428`
  from the earlier quality-gated endpoint run:
  `https://localmaxxing.com/api/benchmarks?hfId=nameistoken%2FQwen3.6-35B-A3B-Quark-W8A8-INT8&limit=20`.
- The broader Arc Pro B70/Qwen leaderboard query has our later public family
  row at `tokSOut=99.770` and shows no public 8-bit exact-model result near the
  `>200 tok/s` target yet:
  `https://localmaxxing.com/api/leaderboard?hardwareName=Intel%20Arc%20Pro%20B70&modelFamily=qwen&limit=20`.
- Intel's XPU grouped-GEMM tracking issue explicitly calls out realistic MoE
  route skew and tile configuration as first-order tuning inputs:
  `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`.
- vLLM's MoE kernel design docs separate prepare/finalize, quantized
  activation formats, and expert-kernel choices. That maps cleanly onto a
  resident island manager rather than a monolithic endpoint fork:
  `https://docs.vllm.ai/en/latest/design/moe_kernel_features/`.
- The PyTorch locality-aware MoE work is CUDA/Triton-focused, but the
  scheduling lesson is portable: route order and locality can move MoE GEMM
  performance by multiples when cache behavior is the limiter:
  `https://pytorch.org/blog/accelerating-moe-model/`.
- The Intel LLM inference roofline paper reports Xe2/Battlemage INT8 and
  mixed-precision GEMM/GEMV behavior close to attainable rooflines in the right
  layout. Our tiny-M route windows are therefore probably paying launch,
  scheduling, layout, or dependency overhead, not simply "B70 is too slow":
  `https://arxiv.org/html/2508.06753v2`.

Items added to the active try list:

1. **Build the rank-local pointer smoke immediately.**
   The lab runner is exact only because it owns file-backed tensors. The next
   useful proof is a disabled diagnostic inside one live vLLM rank that consumes
   live device pointers, runs the resident island, compares raw BF16 output to
   the current `xpu_fused_moe`, logs parity/timing, and always returns the
   accepted path.

2. **Turn the runner into a resident MoE island manager.**
   Promote the current C++ code into an object with long-lived packed weights,
   primitives, scratch buffers, route descriptors, queues, and per-layer parity
   counters. Python should pass compact descriptors, not rebuild memory objects
   or primitives per call.

3. **Try a oneDNN Graph or Level Zero command-list supernode.**
   The full island still has multiple submits: GEMM1, bridge, GEMM2, gather.
   Capture or prebuild the dependency chain for a fixed layer/shape bucket and
   patch only pointers, route offsets, and scales. Gate this against the current
   exact gather fixture before any live endpoint hook.

4. **Generate route-class kernels, not exact-route kernels.**
   Exact ordered route tuples have weak reuse. Broader classes may still repeat:
   rows-per-expert shape, active expert count, hot-expert subset, and layer.
   Generate a small menu of exact-safe layerlets for those classes and let rare
   classes fall back to current `xpu_fused_moe`.

5. **Run a single-card or TP2 latency probe if memory actually permits.**
   The 4x TP path has collectives and multiprocess overhead on every token. If
   the Quark W8A8 model plus 32K KV can fit a useful lane on one or two B70s,
   even with lower aggregate throughput, it might beat TP4 single-request
   latency. This must be an exact-output probe with the current model only.

6. **Prototype a static c1 latency lane.**
   Production does not need one universal path first. Build a certified lane
   for the common single-request decode shape: current model, 32K budget,
   temperature 0/generic sampling, fixed TP plan, resident MoE island, exact
   canaries, and fallback to the accepted vLLM path on any unsupported shape.

7. **Revisit exact speculation only after verifier cost drops.**
   Speculation remains the most plausible way to exceed `200 tok/s` without
   quality loss, but only if the target verifier is much faster and all accepted
   tokens are verified by the current model. Pair the resident island with
   n-gram or MTP-style proposal experiments; reject anything that changes target
   logits or bypasses verification.

8. **Package a public Intel/vLLM performance packet.**
   Once the rank-local pointer smoke passes, publish a no-secret repro with
   route windows, tiny tensors, expected bytes, timing JSON, rejected shortcuts,
   Localmaxxing row links, and exactness gates. The goal is to give Intel/vLLM a
   focused B70 W8A8 MoE target instead of a vague "vLLM is slow" report.

9. **Measure where the remaining token budget actually goes.**
   Build a token-level stall packet: dense attention, router, route packing,
   MoE island, collectives, sampler, Python/scheduler. The resident layer result
   is promising, but the endpoint still spends roughly `10 ms/token`; we need a
   ranked budget before chasing the next large branch.

10. **Keep a high-fidelity engine bakeoff on the side.**
    Test only 8-bit or BF16-compatible paths that can prove parity against the
    current model: newer vLLM/XPU, Intel container builds, oneDNN/OpenVINO
    experiments, or llama.cpp Q8 if an exact comparable model exists. Exclude
    4-bit, AWQ, Qwen3.5, and any benchmark that cannot pass route-replay and
    endpoint quality gates.

## 2026-06-12 Expanded Bigger-Bet Backlog

User direction: add the current ideas to the durable notes and keep looking for
larger moves. Constraints remain unchanged: current Qwen3.6 35B Quark W8A8
INT8 target, no 4-bit/AWQ/Qwen3.5 detours, no unverified emission path, and
single-request decode speed is the first metric.

Fresh source checks:

- Exact-model Localmaxxing API query still returns one public B70/vLLM row:
  `tokSOut=99.42835812273452`, `ttftMs=76.45406149094924`,
  `tokSTotal=196.3252731420561`, c1, 32K context, 4x Arc Pro B70:
  `https://localmaxxing.com/api/leaderboard?hfId=nameistoken%2FQwen3.6-35B-A3B-Quark-W8A8-INT8&hardwareName=Arc%20Pro%20B70&engineName=vllm&limit=10`.
- Broader FP8 Qwen3.6 rows show the public `>200 tok/s` path uses DFlash and
  CUDA/Blackwell, not our exact INT8/B70 stack. Treat it as evidence that
  target-verified speculation can cross the target, not as a directly
  comparable quality or hardware result:
  `https://localmaxxing.com/api/leaderboard?hfId=Qwen%2FQwen3.6-35B-A3B-FP8&limit=10`.
- Intel/vLLM's Arc Pro B blog describes the MoE failure mode directly:
  launch overhead, gate dependency stalls, static route imbalance, and a
  persistent zero-gap kernel with dynamic work assignment. This validates the
  resident-worker / persistent-MoE direction:
  `https://vllm.ai/blog/2025-11-11-intel-arc-pro-b`.
- Intel Triton-XPU grouped-GEMM issue `#6389` says realistic route skew and
  tile configuration are core tuning inputs. Keep using routecapture windows as
  kernel fixtures, not synthetic uniform routing:
  `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`.
- oneDNN grouped memory / grouped GEMM is explicitly an experimental MoE path
  with profiling support. The next resident island should use oneDNN profiling
  rather than only host wall-clock timing:
  `https://uxlfoundation.github.io/oneDNN/dev_guide_experimental.html`.
- Public B70 community repos point at Intel `llm-scaler` / `intel/vllm` B70
  builds as the canonical stack to compare against, and specifically call out a
  persistent zero-gap MoE GEMM kernel. Test or transplant the kernel idea, but
  do not change the target model:
  `https://github.com/Hal9000AIML/arc-pro-b70-ubuntu-gpu-speedup-bugfixes`.
- DFlash's Qwen3.6 drafter docs require target-hidden-state handling patches
  and pair the drafter with `Qwen/Qwen3.6-35B-A3B`. Any DFlash attempt here
  must be a proposer only; the current Quark W8A8 target must verify before
  emission:
  `https://huggingface.co/z-lab/Qwen3.6-35B-A3B-DFlash`.
- vLLM's MoE kernel design docs show a modular route for prepare/finalize,
  expert kernels, quantized activation formats, and async backends. A resident
  XPU island should eventually be shaped as a modular expert/backend instead
  of an ad hoc Python-side branch:
  `https://docs.vllm.ai/en/latest/design/moe_kernel_features/`.

Bolder things to try:

1. **Transplant or reimplement Intel's persistent zero-gap MoE schedule.**
   Build a tiny B70/Qwen3.6 route-window harness that mimics the blog design:
   one persistent loop, dynamic atomic block assignment, real route skew, and
   Quark W8A8 output parity. If the isolated harness beats resident oneDNN, it
   becomes the custom layerlet target; if not, keep oneDNN as the production
   sidecar.

2. **Create a rank-local MoE command ring.**
   Instead of Python calling a custom op per MoE boundary, keep a per-rank
   resident worker with packed weights, scratch buffers, route descriptors, and
   queue objects already alive. The live path submits compact descriptors and
   waits for a completion fence. This attacks the control-plane floor directly.

3. **Make a tile-native W8A8 checkpoint artifact.**
   Convert Quark expert tensors at model-load time into the fastest proven B70
   layout, with checksums mapping back to the original safetensors. This
   preserves quality because the math and scales stay identical; only physical
   layout changes. The artifact should be reproducible and invalidated by
   source tensor checksum changes.

4. **Build a modular vLLM XPU MoE backend instead of patching one call path.**
   Use the vLLM modular MoE interfaces as the long-term shape: XPU prepare,
   XPU W8A8 experts, XPU finalize, with the resident oneDNN/custom worker under
   the expert implementation. That gives upstream reviewers a real integration
   point and lets fallback remain clean.

5. **Hot-expert partial replication across TP ranks.**
   Route traces show active experts are sparse. Simulate and then test a layout
   where each TP rank owns its normal shard plus replicated hot experts for a
   few layers. The goal is fewer cross-rank stalls and better local bandwidth
   without changing token math. Gate by exact route replay and endpoint
   canaries.

6. **TP2 or single-card c1 lane if memory permits.**
   TP4 may be a capacity solution with unavoidable c1 collective overhead.
   Run a strict current-model memory probe for TP2 and single-card service
   lanes at smaller and full 32K contexts. If a lower-TP lane beats TP4 latency,
   production can use more independent replicas for aggregate throughput.

7. **Target-owned speculative transaction log.**
   After resident pointer/COW work exists, implement speculation as a target
   transaction: copy request state, propose tokens, verify with the current
   Quark W8A8 model, commit only accepted tokens, and log parent hash,
   candidates, verifier top-k/logprob evidence, accepted length, and rollback
   reason. This is the clean path to `>200 tok/s` without quality handwaving.

8. **DFlash/MTP/n-gram bakeoff under one verifier harness.**
   Once target transactions are available, compare all proposer types under the
   same quality ledger. The metric is effective verified tok/s, not drafter
   tok/s. DFlash is interesting because public Qwen3.6 rows cross `200 tok/s`,
   but it is disqualified unless the current Quark model verifies emissions.

9. **OneDNN Graph / Level Zero command-list supernode.**
   Prebuild a fixed-shape MoE dependency chain for one layer bucket:
   remap/quant, GEMM1, activation/quant, GEMM2, gather/finalize. Patch only
   pointers, scales, and route offsets. If command-list replay removes host
   wait overhead while staying bit-exact, it may be faster to productionize
   than a new ESIMD kernel.

10. **Full token critical-path ledger with queue profiling.**
    Add low-overhead timing for attention, router, route packing, MoE island,
    collectives, scheduler metadata copies, sampler, and OpenAI/frontdoor. Use
    oneDNN/SYCL queue profiling where possible. The resident layer is now
    microsecond-scale; the endpoint is still about `10 ms/token`, so the next
    large patch should be guided by a ranked wall-time ledger.

11. **Intel-maintainer performance packet.**
    Package exact route windows, small tensors, raw expected bytes, environment
    manifest, Localmaxxing row, accepted/rejected patches, and a `>200 tok/s`
    target budget. This turns the problem into a concrete B70 W8A8 MoE target
    for Intel/vLLM instead of a vague slow-endpoint complaint.

12. **Production split between quality-certain and speed-experimental lanes.**
    Keep the current `~100 tok/s`, 32K, quality-gated Quark service as the
    conservative production answer while the latency lane experiments with
    resident MoE, lower TP, and verifier transactions. Promotion requires the
    same sentinels, prompt-class quality gates, route replay, and reliability
    soak.

Ideas to explicitly avoid for this goal:

- 4-bit, AWQ, Qwen3.5, or different-model shortcuts.
- Publishing drafter-only throughput as if it were target-verified output.
- Exact-route kernel caches keyed by ordered top-k tuples; prior trace analysis
  showed poor reuse. Cache by layer/shape and generate broader route classes
  instead.
- More flag sweeps without a token-level bottleneck ledger.

## Additional Bigger Bets After User Prompt

Added after the request to collect more ambitious ideas. These are intentionally
bolder than the next sidecar probe, but the admission rule remains strict:
current Qwen3.6 Quark W8A8 INT8 target, exact quality gates, no 4-bit/AWQ/
Qwen3.5 detours, and no unverifiable output stream.

Fresh source signals folded in:

- vLLM's Arc Pro B article names the exact bottleneck class: per-iteration MoE
  GEMM launches, gate-dependent stalls, and route imbalance. Its persistent
  zero-gap design is the clearest architectural target for a B70 W8A8 route
  harness: `https://vllm.ai/blog/2025-11-11-intel-arc-pro-b`.
- oneDNN's matmul docs support GPU grouped matmul, integer weights, grouped
  binary post-ops, and `eltwise_swish`/binary multiply style post-op fusion.
  That suggests the current oneDNN island should try fusing activation and scale
  work into the grouped primitive before we jump straight to hand-written
  kernels: `https://uxlfoundation.github.io/oneDNN/dev_guide_matmul.html`.
- oneDNN release notes add grouped memory / grouped matmul and an execution-time
  `DNNL_ARG_HINT_MAX_GROUP_SIZE` hint. That is directly relevant to our
  route-window replay because max group size changes with token bucket and
  route skew: `https://github.com/uxlfoundation/oneDNN/releases`.
- DFlash docs explicitly require target-hidden-state handling patches and pair
  the drafter with `Qwen/Qwen3.6-35B-A3B`. This keeps DFlash on the board only
  as a proposer behind a current-model verifier:
  `https://huggingface.co/z-lab/Qwen3.6-35B-A3B-DFlash`.
- The public B70 TP=2 vLLM issue records host-stack, oneCCL, firmware, and
  kernel/driver variables as plausible failure/performance factors. Treat host
  BOM testing as a real performance experiment, not just operations work:
  `https://github.com/vllm-project/vllm/issues/41663`.
- vLLM's modular MoE docs separate prepare/finalize, expert kernels, activation
  formats, and backend implementations. The production-quality version of the
  sidecar should eventually become a modular XPU MoE backend:
  `https://docs.vllm.ai/en/latest/design/moe_kernel_features/`.

New ideas to keep in the backlog:

1. **Fuse the whole oneDNN MoE island before writing ESIMD.**
   Current oneDNN proof only times the grouped GEMMs. Try grouped matmul
   post-ops for scale, SiLU/gate multiply, and GEMM2 preparation so the layer
   becomes fewer queue submissions. Gate by final gathered output
   `max_abs_diff=0.0` versus `xpu_fused_moe`.

2. **Use oneDNN `DNNL_ARG_HINT_MAX_GROUP_SIZE` as a route-bucket knob.**
   Our route windows already expose `max_rows_per_expert`. Feed that hint into
   the resident primitive path and compare by token bucket. This is a small
   change with unusually direct relevance to route skew.

3. **Build a token-step waterfall with device-side queue timestamps.**
   Add timestamp probes for attention, router, remap, quant, GEMM1, activation,
   GEMM2, gather, collectives, sampler, scheduler, and frontdoor streaming. The
   endpoint is around `10 ms/token`; the resident GEMM pair is microsecond
   scale. The next large patch should attack the measured wall-time winner.

4. **Persistent B70 MoE worker with dynamic work stealing.**
   Recreate the zero-gap idea in a small route-window harness: a resident worker
   owns packed weights and dynamically grabs expert blocks as they become ready.
   The first comparison is route-window latency and exact bytes versus current
   XPU output, not endpoint speed.

5. **Host BOM A/B as a speed and stability experiment.**
   Test the same current model under a known Intel-validated stack versus the
   current host stack: kernel, GuC firmware, compute runtime, oneAPI, oneCCL,
   PyTorch XPU, `vllm-xpu-kernels`, BIOS PCIe settings, ASPM, power limits, and
   fan policy. Track BCS resets/device-lost frequency as promotion blockers.

6. **Compile a c1-only no-server runner for ceiling measurement.**
   A C++/Python hybrid runner can own one request, static KV, fixed scheduler
   state, resident command queues, and direct sampler output. This is not the
   production server; it tells us whether `>200 tok/s` is physically reachable
   with current math after vLLM server overhead is removed.

7. **Make the Quark W8A8 layout itself an optimized artifact.**
   Prepack expert weights at load time into the fastest proven B70 layout and
   persist a checksum-indexed cache. Keep source safetensor checksums and scale
   checksums in the metadata so this remains a layout optimization, not a model
   change.

8. **Build a verifier transaction substrate before chasing DFlash.**
   Define copy/commit/rollback for KV blocks, Gated DeltaNet / hybrid state,
   scheduler counters, sampler state, and stream output. Then MTP, DFlash,
   n-gram, or branch farming can be compared under one target-verifier harness.

9. **Route-class kernels rather than exact-route kernels.**
   Prior cache analysis showed exact ordered top-k route reuse is poor. Generate
   kernels for broader classes: token bucket, max group size, hot expert set,
   and N/K shape. That preserves the lesson from routecapture without overfitting
   to single traces.

10. **Production split lanes with identical quality gates.**
    Keep the current TP4 `~100 tok/s` 32K endpoint as the conservative lane and
    build a c1 latency lane separately. Promotion requires identical model hash,
    exact canaries, prompt-class quality, route replay exactness, and soak
    stability.

## 2026-06-12 Bolder Addendum After Refresh

Added after the follow-up prompt to think bigger. This section folds in a fresh
public Localmaxxing refresh, local checkpoint metadata, and current MoE/XPU
source signals. It is explicitly not permission to use lower precision or a
different model; it is a list of architecture paths that might close the
`~4.98 ms/token` c1 gap without changing the accepted output owner.

Fresh artifacts:

- `data/localmaxxing-qwen36-quark-w8a8-int8-exact-refresh-20260612bn.json`
- `data/localmaxxing-qwen-b70-vllm-leaderboard-20260612bn.json`
- `data/localmaxxing-qwen36-35b-a3b-leaderboard-20260612bn.json`

Evidence snapshot:

- Localmaxxing still has one exact checkpoint row for
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`: `99.428 tok/s`, `76.45 ms`
  TTFT, `p512/o512`, c1, 32K context, 4x Arc Pro B70, vLLM, Quark W8A8 INT8.
  Our fresh local accepted endpoint at `100.013 tok/s` is consistent with that
  public row rather than obviously misconfigured.
- The public B70/vLLM/Qwen refresh still tops out near `100 tok/s` for the
  35B-A3B class: `99.770 tok/s` on `Qwen/Qwen3.6-35B-A3B` and `99.428 tok/s`
  on the exact Quark W8A8 INT8 checkpoint.
- Broader `Qwen/Qwen3.6-35B-A3B` rows above `200 tok/s` are useful targets but
  not direct substitutions for this goal: examples include R9700 `MQ4-AWQ` +
  MTP, Blackwell FP8 + DFlash, RTX 5090 NVFP4/FP8 + MTP, and RTX 5090
  `Q4_K_M`. Those violate the current-model/current-precision rule or change
  hardware, so they only justify verifier-safe speculation and architecture
  work as research directions.
- The local Quark W8A8 checkpoint's `model.safetensors.index.json` has no
  `mtp`/`next` keys. Native `qwen3_next_mtp` is therefore not an immediate
  switch for this exact quantized checkpoint. Any MTP/DFlash/ngram path must be
  framed as proposer work behind exact current-model verification.
- vLLM's Arc Pro B article, PyTorch's persistent grouped-GEMM work, and Intel's
  grouped-GEMM tuning issue all point at the same family of bottlenecks:
  launch overhead, gate-dependent stalls, route skew, tile selection, and
  persistent grouped execution. This lines up with our endpoint-vs-nosync
  ledger: small isolated GEMM wins are not enough unless they remove whole
  token-step overhead.

Bigger ideas to keep on the board:

1. **Exact c1 latency lab outside the server.**
   Build a one-request runner that bypasses HTTP, OpenAI streaming, request
   scheduling, dynamic batching, and generic paged-KV policy while still using
   the exact current weights, tokenizer, sampler, and KV state. This tells us
   whether `>200 tok/s` is physically reachable before spending weeks on the
   production server path.

2. **Transactional target-state verifier substrate.**
   Implement copy/commit/rollback for KV blocks, Gated DeltaNet state,
   scheduler metadata, sampler state, and output stream state. Then MTP,
   DFlash, n-gram, or branch farming can propose tokens, but only the current
   Quark W8A8 model commits final output. This is likely the cleanest
   no-quality-loss `2x` class path if kernel work stalls around `180 tok/s`.

3. **EP-lite or asymmetric TP topology for latency.**
   TP4 may be paying collectives every layer to make 32K production comfortable.
   Try a latency lane that duplicates selected non-MoE pieces, changes
   expert/data placement, or runs TP2 plus two replicas, then measure c1
   decode and reliability. This is a memory-for-latency trade, not a model
   change, and should be tested with the same 32K promotion gate after the
   ceiling is understood.

4. **Persistent XPU MoE command ring.**
   Move beyond normal kernel launches: one resident worker per rank owns packed
   expert weights, waits on route metadata, steals expert blocks dynamically,
   and emits final gathered output. The first proof can be a route-window
   harness with exact byte parity; endpoint integration comes later.

5. **Whole-layer MoE supernode using oneDNN Graph or Level Zero replay.**
   Prebuild fixed-bucket command lists for remap, quant, GEMM1, activation,
   GEMM2, and gather. Patch pointers, scales, and grouped offsets at runtime.
   If this captures most host/queue overhead, it may reach production sooner
   than a fully handwritten ESIMD megakernel.

6. **Hot-expert replication with exact weights.**
   Use real route traces to identify hot shared/routed experts and replicate
   only those weights across ranks or latency lanes. The output is unchanged,
   but route skew and cross-rank waits may improve. This should be coupled to a
   checksum-indexed packed-weight cache so it remains reproducible.

7. **B70 W8A8 roofline and utilization packet.**
   Build a single report with DPAS occupancy, HBM bandwidth, queue idle time,
   copy-engine use, all-reduce time, route skew, and token waterfall. Without
   this, it is too easy to optimize the wrong 5% slice. This packet also gives
   Intel/vLLM maintainers a concrete target.

8. **Strict same-model engine bakeoff.**
   Test SGLang, llama.cpp, KTransformers, or a custom runner only when the model
   representation is exact or a BF16 fallback is used as the quality oracle.
   No AWQ/4-bit shortcut qualifies, but another engine may reveal server or
   scheduler overhead we can port back to vLLM/XPU.

9. **Route-skew autotuning from real traces.**
   Feed our routecapture windows into grouped-GEMM autotuning instead of uniform
   synthetic cases. Sweep max group size hints, hotset buckets, and tile layouts
   against exact captured outputs. Promote only route classes that generalize
   across prompt classes.

10. **Context-length sensitivity as diagnosis, not promotion.**
    Run 4K/8K/32K c1 tests with the same model to separate MoE, attention, KV,
    and scheduler costs. The production target remains 32K, but shorter-context
    deltas can tell us whether the missing milliseconds are MoE-dominated or
    cache/attention/server dominated.

## 2026-06-12 Live Mode And Context Sweep

Added a bounded no-output-path-change sweep on the accepted endpoint to test two
easy hypotheses before deeper maintenance: whether SSE streaming/frontdoor
output handling is a large decode bottleneck, and whether shorter context
materially improves steady decode.

Artifacts:

- `scripts/qwen36-live-sweep-summary.py`
- `data/qwen36-quark-int8-tp4-live-stream-p512o512-c1-20260612bo.json`
- `data/qwen36-quark-int8-tp4-live-nonstream-p512o512-c1-20260612bo.json`
- `data/qwen36-quark-int8-tp4-live-stream-p512o256-c1-20260612bo.json`
- `data/qwen36-quark-int8-tp4-live-stream-p4096o256-c1-20260612bo.json`
- `data/qwen36-quark-int8-tp4-live-mode-context-sweep-summary-20260612bo.json`
- `data/qwen36-quark-int8-tp4-live-mode-context-sweep-summary-20260612bo.md`
- `data/qwen36-quark-int8-tp4-live-mode-context-sweep-20260612bo.json`

Findings:

- Stream p512/o512 corrected decode: `99.590 tok/s`, with vLLM decode median
  `10.023 ms/token`.
- Non-stream p512/o512 vLLM decode median: `9.989 ms/token`, only `-0.34%`
  versus stream; e2e tok/s moved by only `+0.35%`.
- Stream p512/o256 vLLM decode median: `9.925 ms/token`.
- Stream p4096/o256 vLLM decode median: `9.980 ms/token`, only `+0.55%`
  versus p512/o256, while TTFT rose from `74.2 ms` to `375.5 ms`.
- Queue time stayed around `0.008-0.009 ms/request`.

Interpretation:

- SSE streaming/output response mechanics are not the missing `~5 ms/token`.
- Reducing context from 4096 to 512 does not materially change steady decode,
  so the c1 gap is not primarily long-context attention/KV work at these
  lengths. Prefill/TTFT scales as expected, but decode remains near `10 ms`.
- The next high-value work should focus on model execution, command
  submission/synchronization, TP/collective topology, resident MoE scheduling,
  or target-verified multi-token acceptance.

Boundary timing patch:

- Added a local source patch artifact,
  `patches/vllm-qwen36-boundary-timing-labels-20260612bo.diff`, and applied it
  to `/home/steve/src/vllm/vllm/v1/worker/gpu_model_runner.py`.
- It adds disabled-by-default `timed_region` labels for
  `gpu_model_runner.preprocess_total`, `gpu_model_runner.forward_total`,
  `gpu_model_runner.postprocess_total`, `gpu_model_runner.sample_total`, and
  `gpu_model_runner.async_output_wrap`.
- `python3 -m py_compile vllm/v1/worker/gpu_model_runner.py` passed.
- The live endpoint was not restarted for this patch in this pass; the new
  labels are for the next maintenance timing run with
  `VLLM_XPU_DECODE_TIMING=1`.

## 2026-06-12 Rank-Local Live ABI Smoke

Added a disabled-by-default live pointer diagnostic to the current XPU Quark
W8A8 INT8 MoE path. It is only active when
`VLLM_XPU_MOE_LIVE_ABI_FILE` is set, records after `moe_gather`, and always
returns the accepted output path unchanged.

Source patch artifacts:

- `patches/qwen36-live-abi-fused-moe-interface-20260612bi.diff`
- `patches/qwen36-live-abi-vllm-xpu-moe-20260612bi.diff`
- `patches/qwen36-live-abi-vllm-quark-moe-20260612bi.diff`

Diagnostic env used for the smoke:

- `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1`
- `VLLM_XPU_MOE_LIVE_ABI_FILE=/tmp/qwen36-live-abi-20260612bi-{pid}.jsonl`
- `VLLM_XPU_MOE_LIVE_ABI_MAX_LINES=12`
- `VLLM_XPU_MOE_LIVE_ABI_LAYER_REGEX='layers\\.(8|9)\\.'`
- `VLLM_XPU_MOE_LIVE_ABI_INCLUDE_SAMPLES=1`

Validation before live run:

- `python3 -m py_compile` passed for:
  - `vllm_xpu_kernels/fused_moe_interface.py`
  - `vllm/model_executor/layers/fused_moe/experts/xpu_moe.py`
  - `vllm/model_executor/layers/quantization/quark/quark_moe.py`
- vLLM/XPU venv import check passed:
  `live_abi_env VLLM_XPU_MOE_LIVE_ABI_FILE`,
  `has_xpu_fused_moe True`.

Live smoke:

- Diagnostic backend session:
  `qwen36-tp4-live-abi-smoke-20260612bi`
- Launch log:
  `data/qwen36-quark-int8-tp4-live-abi-smoke-20260612bi.log`
- `/v1/models` healthy after `57s`.
- A small deterministic `/v1/completions` request completed successfully.
- Artifacts:
  - `data/qwen36-live-abi-smoke-summary-20260612bi.json`
  - `data/qwen36-live-abi-smoke-completion-20260612bi.json`
  - `data/qwen36-live-abi-20260612bi-1773478.jsonl`
  - `data/qwen36-live-abi-20260612bi-1773479.jsonl`
  - `data/qwen36-live-abi-20260612bi-1773480.jsonl`
  - `data/qwen36-live-abi-20260612bi-1773481.jsonl`

Summary:

- `48` total records, `12` per TP rank.
- Ranks covered: `0`, `1`, `2`, `3`.
- Layers covered: `language_model.model.layers.8.mlp.experts` and
  `language_model.model.layers.9.mlp.experts`, `24` records each.
- Captured live tensor metadata and data pointers for:
  hidden states, `w13`, `w13_scales`, `w2`, `w2_scales`, `topk_weights`,
  `topk_ids`, output, remapped hidden states, rows per expert,
  unpermuted-row map, GEMM1 output, GEMM2 output, `gemm1_a`,
  `gemm1_a_scales`, activation output, `gemm2_a`, and `gemm2_a_scales`.
- Captured route summaries including `rows_sum`, `nonzero_experts`, and
  `max_rows_per_expert`; first warm/capture records included
  `num_rows=8192`, later decode-bucket records included shapes such as
  `num_rows=96`, `88`, `80`, `72`, and `64`.
- Captured lightweight output/GEMM sample checksums for each record.

Post-smoke restore:

- Normal accepted backend session:
  `qwen36-tp4-accepted-restored-after-live-abi-smoke-20260612bi`
- Restore log:
  `data/qwen36-quark-int8-tp4-accepted-restored-after-live-abi-smoke-20260612bi.log`
- `/v1/models` healthy after `55s`.
- Provenance guard:
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-live-abi-smoke-20260612bi.json`
- Result: `ok=true`; both prefix cases matched and all sentinel tokens passed:
  `4752`, `11436`, `198`.

Interpretation:

- This proves the live vLLM rank path can expose exactly the pointer/shape/dtype
  metadata the resident MoE island needs, including scratch buffers, route
  rows, output, and GEMM intermediates.
- It is still not an endpoint speed result. The hook intentionally records
  metadata and returns the current accepted output.
- Next implementation gate: replace metadata-only recording with a guarded
  resident oneDNN sidecar call for one layer/rank, compare output against the
  current `xpu_fused_moe` path, log parity/timing, and still return the current
  accepted output until exact live parity is proven across more layers/shapes.

## 2026-06-12 RPC Future-Result Split And Bigger Bets

Added an env-gated RPC timing split around the vLLM multiprocess executor and
worker response path. The objective was to break the EngineCore `future_result`
wait into worker compute, response materialization, and driver response wait
without changing model output.

Artifacts:

- `patches/vllm-qwen36-engine-rpc-timing-20260612bt.diff`
- `data/qwen36-quark-int8-tp4-rpc-timing-20260612bt.log`
- `data/qwen36-quark-int8-tp4-rpc-timing-p512o256-metrics-20260612bt.json`
- `data/qwen36-quark-int8-tp4-rpc-timing-summary-20260612bt.json`
- `data/qwen36-quark-int8-tp4-rpc-timing-summary-20260612bt.md`
- `data/qwen36-quark-int8-tp4-rpc-fastoutput-20260612bu.log`
- `data/qwen36-quark-int8-tp4-rpc-fastoutput-p512o256-metrics-20260612bu.json`
- `data/qwen36-quark-int8-tp4-rpc-fastoutput-summary-20260612bu.json`
- `data/qwen36-quark-int8-tp4-accepted-restored-after-rpc-timing-20260612bu.log`
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-rpc-timing-20260612bu.json`
- `data/qwen36-quark-int8-tp4-accepted-quality-after-rpc-timing-nothink-smoke-20260612bu.json`
- `data/localmaxxing-b70-vllm-leaderboard-20260612bt.json`
- `data/localmaxxing-qwen36-quark-w8a8-int8-exact-refresh-20260612bt.json`
- `data/localmaxxing-qwen-b70-leaderboard-20260612bt.json`

Diagnostic run:

- Current model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`.
- Runtime: vLLM/XPU TP4, 32K context, accepted graph cache, no prefix caching.
- Prompt/output: vLLM-random p512/o256, c1, streaming, `ignore_eos=true`.
- Corrected output throughput after first chunk: `100.621 tok/s`.
- vLLM decode histogram: `9.902 ms/token`.
- vLLM time-per-output-token histogram: `9.941 ms/token`.
- Joined sampled RPC calls were `sample_tokens` because of the print cadence;
  this is still the relevant queued decode path for emitted tokens.

Measured `sample_tokens` split:

- Driver response wait: `4.297 ms` mean, `4.358 ms` median.
- Max worker function time: `0.351 ms` mean, `0.343 ms` median.
- Rank-0 response materialization / output enqueue:
  `3.900 ms` mean, `3.954 ms` median.
- Response wait minus max worker function:
  `3.946 ms` mean, `4.008 ms` median.
- Worker function skew across ranks: only `0.037 ms` mean.

Interpretation:

- `sample_tokens` compute is not the bottleneck; it is about `0.35 ms`.
- The output-rank response materialization path accounts for almost the whole
  `sample_tokens` wait. The likely target is
  `AsyncModelRunnerOutput.get_output()`, especially event synchronization or
  device-to-host token ID copy completion.
- The existing `gpu_model_runner.async_output_wrap` label is only about
  `0.1 ms`, so the cost is later, when the async output is converted into the
  worker response.
- The `VLLM_XPU_FAST_ASYNC_OUTPUT_LIST=1` plus
  `VLLM_XPU_REUSE_ASYNC_OUTPUT_COPY_BUFFER=1` A/B did not improve speed:
  `100.327 tok/s` corrected, `9.931 ms/token` decode, and
  `3.962 ms` mean output enqueue. A simple `.tolist()` shortcut or current
  reusable-buffer branch is therefore not enough.

Immediate things to try:

1. **Sub-time `AsyncModelRunnerOutput.get_output()`.**
   Split event sync, token-id conversion, logprobs conversion, and message
   enqueue. Record sampled-token dtype and whether the reusable CPU buffer path
   actually fires.

2. **Pinned scalar c1 output path.**
   For no-logprobs c1 completions, copy only one committed token ID into a
   pinned one-token host slot or ring. Avoid per-token tensor/list payload
   construction when the response only needs one ID.

3. **Async-copy branch proof.**
   Run `VLLM_XPU_SYNC_ASYNC_OUTPUT_COPY=1` and
   `VLLM_XPU_DEFER_ASYNC_OUTPUT_COPY=1` diagnostics. These are attribution
   tests, not promotion candidates.

4. **No-server c1 ceiling with identical sampler output.**
   If a direct model-runner loop avoids the `~4 ms` response materialization
   cost while preserving exact token parity, the production latency lane target
   becomes concrete.

5. **Output-rank-only focus.**
   All ranks are low-cost in `sample_tokens`; the output rank is where the
   response cost lands. Prioritize output materialization before broad sampler
   rewrites.

Public signals refreshed:

- Localmaxxing exact-model B70/vLLM row remains `99.428 tok/s`; nearby
  B70/Qwen3.6 rows remain around `100 tok/s` unless they change model,
  precision, batch/concurrency, or workload.
- Intel's grouped-GEMM tuning issue says MoE grouped GEMM performance depends
  strongly on real routing distribution and decode-stage skew:
  https://github.com/intel/intel-xpu-backend-for-triton/issues/6389
- The vLLM Arc Pro B-series post calls out persistent zero-gap MoE kernels,
  dynamic work balancing, host-wait/device-idle gaps, multi-GPU scaling, and
  speculative decoding as Intel Arc optimization targets:
  https://vllm.ai/blog/2025-11-11-intel-arc-pro-b
- oneDNN's INT8 inference path supports INT8 primitives, scaling attributes,
  zero-points, and fused post-ops:
  https://uxlfoundation.github.io/oneDNN/dev_guide_inference_int8.html
- vLLM's Intel quantization docs currently list W4A16 and W8A16 AutoRound
  support on Intel platforms, with additional recipes planned. Useful context,
  but not a reason to leave the current Quark W8A8 target:
  https://docs.vllm.ai/en/latest/features/quantization/inc/

Bigger bets added from this pass:

1. **Pinned scalar output ferry.**
   Replace per-token output materialization with a fixed pinned scalar ring and
   event handoff for c1/no-logprobs. Quality is unchanged because only the host
   transport changes.

2. **Device-resident sampler/streamer lane.**
   Keep token selection and short committed-token buffers device-side, then
   copy committed IDs through a persistent host-visible ring. This attacks one
   synchronization point per token.

3. **Single-request direct runner.**
   Keep the same model runner and sampler, but bypass OpenAI serving,
   scheduler queues, and multiprocessing for a fixed c1 latency lane. Exact
   token parity with accepted vLLM is mandatory.

4. **TP2 latency lane plus replicas.**
   Test whether TP4 is over-synchronizing sparse active-token decode. If TP2
   wins c1 latency, use the other B70s for replicas, branch verification, or
   aggregate throughput.

5. **Expert-parallel sparse island.**
   Keep dense/shared layers tensor-parallel, but route MoE expert work to
   rank-local or duplicated expert islands. Spend VRAM surplus to reduce
   synchronization and route skew.

6. **Whole-token command-list replay.**
   Capture a fixed decode bucket across attention, MoE, residual, sampler, and
   output handoff into a patchable Level Zero command sequence. This is large,
   but it directly targets host launch and synchronization overhead.

7. **Target-owned branch farm.**
   Use current Quark W8A8 target verification for ngram/MTP/EAGLE-style
   proposed futures. Proposed tokens never reach the user unless the current
   target model commits them.

8. **B70 maintainer packet.**
   Package route windows, exact checkpoint, command line, profiler traces,
   output-path timing, oneDNN sidecar fixtures, and the `5 ms/token` target for
   Intel/vLLM maintainers.

9. **Strict same-model engine bakeoff.**
   Compare OpenVINO/oneDNN, llama.cpp SYCL, SGLang, KTransformers, and custom
   runners only when they preserve current-model output or use BF16 as the
   quality oracle. No 4-bit/AWQ/Qwen3.5 shortcut qualifies.

10. **Parity/stability scoreboard.**
    Every performance branch needs exact provenance sentinels, no-thinking
    quality smoke, route-window parity where applicable, reproducible command,
    XPU memory, and a soak/stability result before promotion.

## 2026-06-12 Async-Output Timing Reframe And Larger Bets

Added a lower-level async-output timing pass after the RPC future-result split.
The previous result correctly found rank-0 response materialization at roughly
`4 ms/token`, but this pass narrows the cause.

The source patch artifact is the current local `gpu_model_runner.py` lab diff
used for this diagnostic. It includes accumulated runner instrumentation, not
only the small async-output timing hunk, because that is the exact source state
that produced the logs.

Artifacts:

- `patches/vllm-qwen36-async-output-timing-20260612bv.diff`
- `data/qwen36-quark-int8-tp4-async-output-timing-20260612bv.log`
- `data/qwen36-quark-int8-tp4-async-output-timing-p512o256-metrics-20260612bv.json`
- `data/qwen36-quark-int8-tp4-async-output-timing-summary-20260612bv.json`
- `data/qwen36-quark-int8-tp4-async-output-reuse-timing-20260612bw.log`
- `data/qwen36-quark-int8-tp4-async-output-reuse-timing-p512o256-metrics-20260612bw.json`
- `data/qwen36-quark-int8-tp4-async-output-reuse-timing-summary-20260612bw.json`
- `data/qwen36-quark-int8-tp4-async-output-timing-summary-20260612bv.md`
- `data/qwen36-quark-int8-tp4-accepted-restored-after-async-output-timing-20260612bw.log`
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-async-output-timing-20260612bw.json`
- `data/qwen36-quark-int8-tp4-accepted-quality-after-async-output-timing-nothink-smoke-20260612bw.json`
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-async-output-timing-rerun-20260612bw.json`
- `data/qwen36-quark-int8-tp4-accepted-quality-after-async-output-timing-nothink-smoke-rerun-20260612bw.json`

Measured result:

- Timing-only diagnostic: `88.990 tok/s` corrected, `11.196 ms/token` vLLM
  decode, `11.240 ms` TPOT. This is slower than the accepted baseline because
  the timing prints are enabled.
- Reuse-buffer plus fast-scalar diagnostic: `88.595 tok/s` corrected,
  `11.246 ms/token` decode, `11.290 ms` TPOT.
- Default path `get_output()` total mean: `3.815 ms`.
- Default path event synchronize mean: `3.798 ms`.
- Default path token-list conversion mean: `0.010 ms`.
- Reuse/fast path `get_output()` total mean: `3.873 ms`.
- Reuse/fast path event synchronize mean: `3.840 ms`.
- Reuse/fast path token-scalar conversion mean: `0.026 ms`.
- Copied token tensor for the measured c1/no-logprobs lane is tiny:
  `torch.int32`, shape `[1,1]`, pinned CPU destination.

Interpretation:

- The bottleneck is not `.tolist()`, Python list construction, or an obvious
  dtype mismatch. The reusable pinned buffer branch fired and still did not
  improve speed.
- The host waits roughly `3.8-3.9 ms` on the async-copy-ready event because
  this is where queued XPU work becomes visible. That wait may include model
  forward tail work, sampler work, D2H token copy completion, command-queue
  ordering, or collectives. The output path is a synchronization point, not
  necessarily the root cause.
- Do not spend more time on small output object-conversion changes unless a
  device timeline proves the D2H copy itself is slow.
- The accepted restore after this instrumentation produced one failed
  provenance/quality artifact, but an immediate rerun on the same backend
  passed: exact provenance sentinels `4752`, `11436`, and `198`, all
  no-thinking exact cases, repeat stability, and baseline matching. Treat the
  first failure as a transient warning, not a promoted regression, and keep the
  quality gate mandatory for every timing patch.

Near-term things to try:

1. **Rerun accepted gates before any new speed test.**
   This pass found no leaked timing/experimental flags in the APIServer,
   EngineCore, or TP0 worker. Provenance and no-thinking quality passed on
   rerun. Keep this as the first step after future backend restores.

2. **Device timeline for the event wait.**
   Capture Level Zero/VTune/oneAPI traces around the `get_output()` event. The
   question is whether the `3.8 ms` is sampler, copy, command queue, allreduce,
   or forward tail.

3. **TP2 latency truth-serum.**
   Test exact current model at TP2 on two B70s. If TP2 reduces the sync/tail
   wait, use the other two B70s for replicas or verifier work instead of TP4.

4. **Direct c1 runner ceiling.**
   Build the minimal loop around the same model runner and sampler, bypassing
   OpenAI serving and multiprocessing, then compare exact token IDs. If direct
   c1 is still near `100 tok/s`, the blocker is device/kernel/topology. If it
   jumps, the blocker is serving/executor synchronization.

5. **Per-token event accounting.**
   Record event creation, copy stream, model stream, sampler stream, and any
   rank-0 copy dependency. The output event should carry enough provenance to
   explain what it is waiting behind.

6. **Sampler-only isolation.**
   Run a synthetic final-logits tensor through the current sampler/output path
   on XPU. If it is sub-millisecond, sampler/output transport is innocent and
   all attention returns to forward/collectives.

7. **Cold-copy isolation.**
   Copy `[1,1]`, `[1,8]`, and `[1,32]` int32 XPU tensors to pinned CPU under
   the same stream/event pattern outside vLLM. This gives the lower bound for
   token-copy overhead.

Bigger, bolder ideas to keep in the queue:

1. **One-token resident decode lane.**
   A fixed c1 decode runtime with static buffers, static scheduler state, and
   patchable token input. It would use the current weights and sampler but stop
   paying general vLLM scheduling costs for the single-user latency lane.

2. **Whole-token Level Zero command-list replay.**
   Capture the repeated decode bucket as a patchable command-list sequence:
   attention, GDN/Mamba/state update if applicable, MoE, residual, sampler,
   and token handoff. The win target is fewer host submissions and fewer
   visible synchronization points.

3. **Persistent MoE device service.**
   Keep expert weights, route windows, and scratch buffers resident behind a
   small device-side service or long-lived command ring. This attacks the MoE
   dispatch and grouped-GEMM boundary rather than only the Python call site.

4. **Hybrid TP/EP topology for the current checkpoint.**
   Keep dense/shared work tensor-parallel but make active sparse experts more
   rank-local. Spend spare VRAM on duplicated hot experts if it lowers
   collectives and route skew.

5. **Hot-expert memory-for-latency plan.**
   Use real prompt-class route captures to identify stable hot experts, then
   duplicate or prepack those experts on more ranks. No quality loss because
   weights are identical; the risk is routing/memory complexity.

6. **Target-owned speculative transactions.**
   Keep the Quark W8A8 target as the verifier, but add temporary KV/request
   state so proposed tokens are committed only if the current model accepts
   them. This remains a no-quality-loss path if the transaction boundary is
   correct.

7. **Branch farm using spare B70s.**
   If TP2 wins latency, use the unused B70s to run target-owned branches or
   prompt-class predictors in parallel. Only the current target stream can
   commit user-visible tokens.

8. **B70 W8A8 MoE maintainer packet.**
   Package the exact checkpoint, route windows, timing logs, VTune/Level Zero
   traces, oneDNN parity fixtures, and the `5 ms/token` target for Intel/vLLM
   maintainers. The public ecosystem may need kernel/runtime changes.

9. **Strict engine bakeoff with current-model parity.**
   Try OpenVINO/oneDNN GenAI, llama.cpp SYCL, SGLang, KTransformers, or a custom
   runner only if they can load the current 8-bit target or match a BF16 oracle.
   No Qwen3.5, no 4-bit, no AWQ shortcuts.

10. **Two-lane production architecture.**
    Separate latency-first c1 workers from aggregate-throughput workers. The
    c1 lane can use static buffers and conservative batching; the aggregate
    lane can keep vLLM continuous batching once speed and quality are proven.

## 2026-06-12 TP2 Latency Truth-Serum

Ran the planned TP2 topology test on the current checkpoint to check whether
TP4 synchronization is the main c1 decode limiter. This was deliberately kept
as the same model and quantization: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`,
Quark W8A8 INT8, 32K context, no prefix cache, vLLM/XPU.

Artifacts:

- `data/qwen36-quark-int8-tp2-latency-truth-20260612bx.log`
- `data/qwen36-quark-int8-tp2-latency-truth-p512o256-metrics-20260612bx.json`
- `data/qwen36-quark-int8-tp2-latency-truth-p512o256-r3-metrics-20260612bx.json`
- `data/qwen36-quark-int8-tp2-latency-truth-provenance-20260612bx.json`
- `data/qwen36-quark-int8-tp2-latency-truth-quality-nothink-smoke-20260612bx.json`
- `data/qwen36-quark-int8-tp2-latency-truth-summary-20260612bx.md`
- `data/qwen36-quark-int8-tp4-accepted-restored-after-tp2-truth-20260612bx.log`
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-tp2-truth-20260612bx.json`
- `data/qwen36-quark-int8-tp4-accepted-quality-after-tp2-truth-nothink-smoke-20260612bx.json`
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-tp2-truth-rerun-20260612bx.json`
- `data/qwen36-quark-int8-tp4-accepted-quality-after-tp2-truth-nothink-smoke-rerun-20260612bx.json`
- `data/qwen36-quark-int8-tp4-restored-after-tp2-p512o256-metrics-20260612bx.json`

Launch comparison:

- TP2 used GPUs `0,1`, model load memory `16.88 GiB/rank`, KV cache
  `1,138,206` tokens, and max 32K concurrency `34.74x`.
- TP2 attention page size changed to `1088` tokens.
- Restored TP4 used GPUs `0,1,2,3`, model load memory `8.58 GiB/rank`, KV cache
  `2,052,915` tokens, and max 32K concurrency `62.65x`.
- TP4 attention page size was the accepted `576` tokens.

Speed result:

- TP2 first p512/o256 run: `91.592 tok/s` corrected, `10.877 ms/token` vLLM
  decode, `10.919 ms` TPOT.
- TP2 r3 p512/o256 run: `91.351 tok/s` corrected mean, range
  `91.204-91.542`, `10.906 ms/token` decode, `10.949 ms` TPOT.
- TP4 restored adjacent p512/o256 run: `100.475 tok/s` corrected,
  `9.916 ms/token` decode, `9.955 ms` TPOT.

Quality/provenance result:

- TP2 passed the short no-thinking quality smoke, including exact OK/copy,
  arithmetic, JSON, repeat stability, and baseline matching.
- TP2 failed exact accepted TP4 provenance. Sentinel drift:
  `4752 -> 6126`, `11436 -> 19087`, and `198 -> 321`.
- TP4 restore had one transient failed first gate, then passed on rerun:
  provenance sentinels `4752`, `11436`, `198`, and no-thinking quality
  `pass_all=true`.

Decision:

- Plain TP2 is ruled out as a no-quality-loss single-user latency path. It is
  slower than TP4 and changes the accepted token stream.
- Do not spend more time on TP2-as-production-latency-lane unless the question
  changes to aggregate replicas or a separate BF16-quality topology study.
- Next useful paths remain TP4 internal timing/profiling, hybrid TP/EP, a
  direct c1 runner, persistent MoE/command-list work, or exact target-owned
  speculative transactions.

## 2026-06-12 Sampler Stage-Split And Bolder Queue Refresh

Added after the sampler-stage diagnostic and the latest user review. This is a
backlog/strategy refresh, not a promoted speed result. The current accepted
single-user speed anchor remains about `99-100 tok/s`; the diagnostic timing
run was intentionally slower because it synchronized and printed per-token
stage data.

Artifacts:

- `patches/vllm-qwen36-sampler-stagesplit-20260612cf.diff`
- `data/qwen36-quark-int8-tp4-sampler-stagesplit-20260612ce-startupfail.log`
- `data/qwen36-quark-int8-tp4-sampler-stagesplit-20260612ce.log`
- `data/qwen36-quark-int8-tp4-sampler-stagesplit-p512o128-metrics-20260612ce.json`
- `data/qwen36-quark-int8-tp4-sampler-stagesplit-summary-20260612ce.json`
- `data/qwen36-quark-int8-tp4-sampler-stagesplit-nested-summary-20260612ce.json`
- `data/qwen36-quark-int8-tp4-accepted-restored-after-sampler-stagesplit-20260612ce.log`
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-sampler-stagesplit-20260612ce.json`
- `data/qwen36-quark-int8-tp4-accepted-quality-after-sampler-stagesplit-nothink-smoke-20260612ce.json`
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-sampler-stagesplit-rerun-20260612cf.json`
- `data/qwen36-quark-int8-tp4-accepted-quality-after-sampler-stagesplit-nothink-smoke-rerun-20260612cf.json`
- `data/localmaxxing-qwen36-quark-w8a8-int8-exact-refresh-20260612cf.json`
- `data/localmaxxing-qwen-moe-b70-leaderboard-refresh-20260612cf.json`
- `data/localmaxxing-vllm-b70-leaderboard-refresh-20260612cf.json`

Measured facts:

- The first sampler diagnostic launch failed during the dummy sampler pass
  because optional `SamplingMetadata` fields were `None`. The fix keeps the
  instrumentation env-gated and uses safe empty fallbacks.
- The successful p512/o128 timing run decoded at `67.341 tok/s` corrected
  after-first, so the speed number is diagnostic-only.
- `async_copy_ready_event.synchronize()` still averaged `5.934 ms`, but almost
  all of that wait was already present at `sampler_entry`: `5.811 ms` mean,
  `5.870 ms` median.
- Device elapsed time from sampler entry to output-ready averaged only
  `0.063 ms`.
- Greedy argmax itself averaged only `0.039 ms`.
- The default-ready sync after sampler output averaged `0.007 ms`, and the
  copy-after-default sync averaged `0.012 ms`.
- Accepted TP4 was restored afterward. The first corrected restore gate had a
  transient provenance/quality drift, but the rerun on the same backend passed
  exact sentinels `4752`, `11436`, and `198`, plus the no-thinking quality
  smoke (`OK`, copy phrase, arithmetic `60`, JSON, repeat stability).

Decision:

- The sampler, token-list conversion, and tiny D2H token copy are now ruled out
  as multi-millisecond roots for the greedy/no-logprobs c1 lane.
- The remaining hidden wait is before sampler entry. The next speed target is
  model tail, final hidden-state selection, logits projection/materialization,
  TP vocab gather or collective work, XPU graph/command-queue ordering, or
  rank imbalance.
- Exact-token shortcuts are still allowed only if they are mathematically
  equivalent and parity-gated against the current Quark W8A8 target. No
  Qwen3.5, 4-bit, AWQ, expert dropping, or unverified proposer output.

External signals checked in this refresh:

- Localmaxxing exact-model B70/vLLM state is unchanged: one public exact row,
  `cmq8yhxvo001ipb0149aoa79o`, `99.428358 tok/s`, c1, 32K context,
  4x Arc Pro B70, Quark W8A8 INT8.
  Source: `https://localmaxxing.com/api/benchmarks?hfId=nameistoken%2FQwen3.6-35B-A3B-Quark-W8A8-INT8&limit=20`
- The B70/Qwen/MoE Localmaxxing query also only returns this exact current row.
  Higher public B70/vLLM rows are currently different models, different
  precision, or aggregate/batch runs; they are design clues, not comparables.
  Source: `https://localmaxxing.com/api/leaderboard?hardwareName=Arc%20Pro%20B70&modelFamily=qwen&isMoE=true&limit=50`
- Intel's grouped-GEMM tuning issue for vLLM/XPU calls out the same problem
  the local traces are pointing at: MoE decode routing is skewed, grouped GEMM
  performance depends strongly on real token routing distributions, and the
  issue text says there is no SYCL-TLA fused-MoE kernel path yet. This supports
  feeding our real Qwen route windows into grouped-GEMM/oneDNN probes instead
  of relying only on synthetic launch flags.
  Source: `https://github.com/intel/intel-xpu-backend-for-triton/issues/6389`
- vLLM's fused-MoE modular-kernel docs and XPU kernel release notes are worth
  tracking because they expose the upstream direction: modular MoE pieces,
  all2all/grouped kernels, MLA/decode attention coverage, and MoE GEMM policy
  updates for Intel XPU.
  Sources: `https://docs.vllm.ai/en/stable/design/fused_moe_modular_kernel/`
  and `https://github.com/vllm-project/vllm-xpu-kernels/releases`

Immediate things to try next:

1. **Pre-sampler logits stage split.**
   Add device events before and after final hidden-state selection, logits
   computation, logits processor/materialization, TP vocab gather/reduce, and
   sampler entry. The test succeeds if the `5.8 ms` wait lands in one named
   pre-sampler slice.

2. **Exact token-only logits lane.**
   Prototype a no-logprobs, greedy-only path that computes the same next token
   without forcing unnecessary full-logits host-visible materialization. A
   sharded top-1 plus exact cross-rank max can be valid, but only if it matches
   the current full-logits sampler token-for-token and records tie behavior.

3. **TP collective microscope.**
   Time every rank around vocab/hidden collectives and oneCCL/custom-op calls.
   Add one controlled A/B for CCL/P2P/custom collective settings. The goal is
   not a launch-flag hunt; it is to prove whether the c1 token is waiting on
   collective setup or rank synchronization.

4. **Rank-card-route triangulation.**
   In one diagnostic, record all-rank timing, physical card assignment,
   xpu-smi clocks/power/memory, route-window active experts, max rows per
   expert, and hot IDs. Rotate rank-to-card mapping. If the slow path follows a
   card, chase topology/thermal/PCIe. If it follows route windows, chase MoE
   scheduling.

5. **Real-route grouped-GEMM shootout.**
   Feed captured Qwen3.6 decode route windows into Intel's grouped-GEMM style
   harness, oneDNN grouped matmul, current vLLM fused-MoE, and any
   vllm-xpu-kernels update. Compare exact outputs plus per-layer latency.

6. **Latest clean XPU kernel stack bakeoff.**
   Build an isolated current Intel/vLLM-XPU or `vllm-xpu-kernels` branch and
   replay route-window fixtures before attempting a full service. A fixture win
   without output parity does not count.

7. **Static c1 runner ceiling.**
   Keep this high priority. A direct in-process c1 decode loop tells us whether
   vLLM's executor/scheduler boundary is still hiding cost after the logits
   split.

Bigger, bolder ideas to keep on the board:

1. **Logits/projection supernode.**
   Fuse final hidden selection, lm-head projection, TP top-1 reduction, and
   token handoff for the greedy/no-logprobs lane. This is narrower and more
   plausible than a whole-model rewrite, but could remove the next visible
   synchronization point if logits materialization is the culprit.

2. **Route-class MoE kernels from real traffic.**
   Generate a small kernel policy table from actual captured routes: single
   hot expert, few hot experts, broad balanced route, and fallback. This keeps
   math identical while avoiding one generic grouped-GEMM policy for every
   decode shape.

3. **Hot-expert replicated work stealing.**
   Spend spare VRAM on duplicated hot experts, then let idle ranks steal heavy
   expert work for route windows proven to be skewed. Output remains identical
   because the weights are duplicated, but scheduling is no longer locked to
   one rank's hot route.

4. **Target-owned branch farm.**
   If static TP4 decode stalls below the `2x` goal, pursue multi-token speed by
   evaluating branches under the current target model with temporary KV/state
   transactions. Proposers may guess; only verified target tokens commit.

5. **Whole-token Level Zero replay after slice proof.**
   Do not jump straight to whole-token command replay. First prove the exact
   pre-sampler slice. If that slice is launch/queue dominated, then capture a
   patchable command list around that slice before expanding to whole-token
   replay.

6. **B70 maintainer challenge bundle.**
   Package the exact checkpoint, launch command, public Localmaxxing row, route
   fixtures, timing summaries, pre-sampler attribution, oneDNN/current-kernel
   parity data, xpu-smi/PCIe details, and a clear target: remove about
   `5 ms/token` without changing output.

7. **Latency and aggregate split as a product design.**
   Production may need two worker classes: one static c1 low-latency lane and
   one continuous-batching aggregate lane. Both share the same model, quality
   gates, provenance sentinels, and soak tests.

Reliability gates to keep attached to every promising branch:

- Exact provenance sentinels on the accepted prompts.
- Short no-thinking quality smoke.
- Prompt-class canaries and a longer-context check before promotion.
- Route-window or logits parity for kernel/logits changes.
- Startup success from cold and warm cache.
- 30-60 minute soak before production promotion.
- Device-lost/error-frequency log.
- Peak VRAM and xpu-smi clock/power snapshot.

## 2026-06-12 Pre-Sampler Probe Attempt And Bigger Ideas Addendum

This addendum records the next attempted diagnostic plus a wider backlog after
the latest user review. It does not promote a new speed result. The current
accepted c1 speed anchor remains the public Localmaxxing/topline range of
`99.4-99.8 tok/s` for this exact Qwen3.6 35B Quark W8A8 INT8 setup on 4x B70.

Artifacts:

- `patches/vllm-qwen36-presampler-stagesplit-20260612cg.diff`
- `data/qwen36-quark-int8-tp4-presampler-stagesplit-20260612cg.log`
- `data/qwen36-quark-int8-tp4-presampler-stagesplit-failure-20260612cg.json`
- `data/qwen36-quark-int8-tp4-accepted-restored-after-presampler-stagesplit-20260612cg.log`
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-presampler-stagesplit-20260612cg.json`
- `data/qwen36-quark-int8-tp4-accepted-quality-after-presampler-stagesplit-nothink-smoke-20260612cg.json`
- `data/localmaxxing-b70-qwen-leaderboard-20260612cg.json`
- `data/localmaxxing-qwen36-quark-int8-benchmarks-20260612cg.json`

Measured/restored facts:

- A pre-sampler stage-split patch was added behind env flags. It records device
  events around execute entry, forward, final hidden selection, logits, local
  argmax if used, sample start, and sampler entry.
- The isolated diagnostic backend on port `18081` reached health, but the first
  p512/o128 streaming completions probe failed with HTTP 500.
- The root stack was `UR_RESULT_ERROR_DEVICE_LOST` during first-request
  `block_table.copy_to_gpu`; cleanup then reported
  `UR_RESULT_ERROR_OUT_OF_DEVICE_MEMORY`.
- Because the crash happened before useful pre-sampler attribution was emitted,
  this run is a stability result, not a timing result.
- The accepted backend was restored on port `18080` with no timing flags in the
  API-server environment.
- Restore provenance passed exact sentinel IDs `4752`, `11436`, and `198`.
- Restore no-thinking quality smoke passed exact canaries, arithmetic, JSON
  schema/semantics, copy phrase, repeat stability, and baseline match.

Interpretation:

- The sampler-stage split remains valid: sampler work and token copy were
  already ruled out as the multi-ms bottleneck.
- The pre-sampler probe itself was too heavy for the current production-like
  `32K`/`gpu_memory_utilization=0.95` service. Adding many timed XPU events can
  perturb Level Zero enough to lose the device before decode attribution.
- Future timing probes should either use one boundary per run, reduce the event
  set to a binary search, lower `gpu_memory_utilization` only for diagnostic
  launches, or run the direct c1 model loop where vLLM server memory pressure is
  absent.

External leads added to the queue:

- vLLM's Intel Arc Pro B-series post explicitly calls out the same families of
  levers we are circling: persistent MoE kernels, dynamic balancing of compute
  groups, async scheduling, prefill/decode disaggregation, speculative
  decoding, and optimized MoE paths.
  Source: `https://vllm.ai/blog/2025-11-11-intel-arc-pro-b`
- Community B70 testing reports instability at high memory utilization and
  lower-context workarounds. That lines up with this failed diagnostic and
  makes a diagnostic-only `gpu_memory_utilization=0.80-0.90` branch reasonable,
  while keeping accepted production candidates at the validated 32K target.
  Source: `https://forum.level1techs.com/t/intel-b70-launch-unboxed-and-tested/247873`
- vLLM release notes show active XPU work in areas relevant to us:
  XPU MXFP8 MoE, FP8 block-scaled quantization, custom-op collective behavior,
  MoE host-overhead reduction, Quark fixes, and Qwen3.5/3.6 quantized-prefix
  mapping. These are candidates for an isolated clean-stack bakeoff.
  Source: `https://github.com/vllm-project/vllm/releases`
- Intel/vLLM issue traffic for 30B+ Intel Arc setups is still sparse, but
  confirms that many users are looking for stable argument sets rather than
  only raw kernels. We should publish exact repro packets when we have a clear
  bottleneck, not just scattered flags.
  Source: `https://github.com/vllm-project/vllm/issues/35638`
- A public B70 benchmark repo tracks two-card and vLLM/SYCL data with hardware
  topology detail. Useful for comparing PCIe layout, driver/kernel stack, and
  whether performance follows topology.
  Source: `https://github.com/PMZFX/intel-arc-pro-b70-benchmarks`
- An Intel GPU inference paper describes fused activation quant/dequant Xe2 GEMM
  kernels using DPAS and reports large end-to-end speedups over 16-bit paths.
  It is lower-bit focused, so it is not directly acceptable for the current
  W8A8-quality target, but its fused-QDQ and prepacked-layout ideas are relevant
  to a W8A8 expert/lm-head kernel design.
  Source: `https://arxiv.org/html/2508.06753v2`
- Localmaxxing public B70/Qwen leaderboard query on this date returned our
  4x-B70 Qwen3.6 35B rows at the top of the slice: `99.7697 tok/s` for the
  base-family row and `99.4284 tok/s` for the exact Quark W8A8 INT8 row.
  Source:
  `https://localmaxxing.com/api/leaderboard?hardwareName=Arc%20Pro%20B70&modelFamily=qwen&limit=20`

Near-term things to try after the failed heavy probe:

1. **Binary-search pre-sampler timing.**
   Replace the all-events pre-sampler patch with one or two boundaries per run:
   `forward_end`, `logits_end`, then `sampler_entry`. This should reduce event
   pressure and still tell us which half contains the wait.

2. **Diagnostic-only memory headroom.**
   Repeat the minimal boundary probe at `gpu_memory_utilization=0.90` and, if
   needed, `0.85`, keeping 32K first and reducing context only if the runtime
   still loses the device. Record that these are diagnostic settings, not
   accepted production settings.

3. **Direct c1 in-process runner.**
   Build a minimal loop over the loaded model runner with fixed p512 decode,
   no HTTP, no async-output server path, and no request scheduler churn. If it
   still sits near `10 ms/token`, the bottleneck is kernel/model-side. If it
   jumps, the hidden wait is in vLLM's serving/executor path.

4. **All-rank skew timing with fewer events.**
   Time one decode boundary per rank and correlate with route-window hot
   experts and card assignment. This is lower risk than a full stage split and
   directly tests whether one rank is holding the TP step.

5. **Exact sharded greedy-lm-head prototype.**
   In the no-logprobs, temperature-0 lane, compute local top-1 per vocab shard,
   reduce `(value, token_id, rank)` exactly, and bypass full-logits materialize
   where possible. Gate every output token against current full sampler output,
   including tie behavior.

6. **Route fixture kernel bakeoff.**
   Capture real Qwen3.6 active-expert windows and replay them through current
   vLLM fused-MoE, oneDNN grouped matmul, latest vllm-xpu-kernels, and any
   clean Intel container. This keeps quality identical because the weights and
   routes are fixed; only scheduling/kernel implementation changes.

7. **Clean-stack branch bakeoff.**
   Test current upstream/intel `vllm-xpu-kernels` or `intel/vllm` in an isolated
   environment against route fixtures first, then full service only if fixture
   parity and speed are promising.

Bigger, bolder ideas worth keeping alive:

1. **Persistent decode service inside the worker.**
   Collapse repeated per-token launch/queue work for the decode loop into a
   long-lived worker-side token engine. The HTTP server feeds requests; the
   token engine owns steady-state decode and emits only final token IDs.

2. **Rank-specialized expert placement.**
   Stop assuming equal expert placement is best. Use route histograms to place
   high-traffic experts near the fastest card/rank path and duplicate a small
   hot set when VRAM allows. Exact same weights, different physical schedule.

3. **TP/EP hybrid for c1.**
   TP4 may be paying collective cost every token. A hybrid expert-parallel
   design that keeps shared attention/lm-head efficient while reducing TP
   communication in MoE layers could beat pure TP4 for single-user latency.

4. **Fused final-token superkernel.**
   If the pre-sampler wait lands around final hidden selection plus lm-head,
   build a narrow kernel that fuses hidden select, projection, shard top-1, and
   cross-rank token selection for greedy output.

5. **Route-class kernel policy compiler.**
   Generate a small dispatch table for common route shapes: single hot expert,
   two-hot, broad-balanced, and overflow fallback. Keep exact arithmetic/output
   but avoid paying generic grouped-GEMM overhead on easy route windows.

6. **Verifier-owned multi-token transactions.**
   Use target-owned branch verification, not an external 4-bit/AWQ proposer.
   The target model can speculatively advance temporary KV states and commit
   only exact verified tokens. This is the only speculation path that satisfies
   the no-quality-loss constraint.

7. **Driver/runtime matrix as a first-class experiment.**
   Treat Linux kernel, oneAPI, Level Zero, IGC, oneCCL, and PCIe topology as
   tunable variables. Device-lost behavior at high memory utilization suggests
   performance and stability may change materially across stack versions.

8. **External challenge packet.**
   Publish a minimal, reproducible B70 issue/benchmark bundle once attribution
   is sharper: command, model revision, exact quality gates, route fixtures,
   timing summaries, xpu-smi/topology, Localmaxxing row, and the single target
   of removing about `5 ms/token` without changing output.

## 2026-06-12 Minimal Forward Boundary Split

This addendum records the lower-overhead replacement for the failed heavy
pre-sampler probe. It is still diagnostic, not a promoted speed result. The
important result is attribution: the remaining multi-ms wait is inside model
forward, between `forward_start_event` and `forward_end_event`.

Code/config changes:

- `scripts/launch-qwen36-quark-int8-accepted.sh` now has env overrides for
  `MAX_MODEL_LEN`, `MAX_NUM_BATCHED_TOKENS`, `MAX_NUM_SEQS`, and
  `GPU_MEMORY_UTILIZATION`. Defaults are unchanged: 32K, 8192, 48, and 0.95.
- `gpu_model_runner.py` now supports
  `VLLM_XPU_PRE_SAMPLER_BOUNDARY_TIMING=1` with a comma-separated
  `VLLM_XPU_PRE_SAMPLER_BOUNDARY_EVENTS` list. This records only selected
  non-timing XPU events unless full
  `VLLM_XPU_ASYNC_OUTPUT_DEVICE_TIMING=1` is also enabled.
- The pre-sampler sync splitter no longer requires full copy-stream timing, so
  boundary-only probes can avoid the heavy event path that previously triggered
  device loss.

Artifacts:

- `patches/vllm-qwen36-presampler-boundary-minimal-20260612ci.diff`
- `data/qwen36-quark-int8-tp4-presampler-minboundary-20260612ch.log`
- `data/qwen36-quark-int8-tp4-presampler-minboundary-p512o128-metrics-20260612ch.json`
- `data/qwen36-quark-int8-tp4-presampler-minboundary-summary-20260612ch.json`
- `data/qwen36-quark-int8-tp4-presampler-minboundary-nested-summary-20260612ch.json`
- `data/qwen36-quark-int8-tp4-presampler-forwardboundary-20260612ci.log`
- `data/qwen36-quark-int8-tp4-presampler-forwardboundary-p512o128-metrics-20260612ci.json`
- `data/qwen36-quark-int8-tp4-presampler-forwardboundary-summary-20260612ci.json`
- `data/qwen36-quark-int8-tp4-presampler-forwardboundary-nested-summary-20260612ci.json`
- `data/qwen36-quark-int8-tp4-accepted-restored-after-forwardboundary-20260612ci.log`
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-forwardboundary-20260612ci.json`
- `data/qwen36-quark-int8-tp4-accepted-quality-after-forwardboundary-nothink-smoke-20260612ci.json`

Run setup:

- Diagnostic services used port `18081`.
- Diagnostic-only headroom: `GPU_MEMORY_UTILIZATION=0.85`,
  `MAX_NUM_SEQS=8`, 32K context unchanged.
- Accepted service was restored afterward on port `18080` with default
  settings and no diagnostic timing env vars.

Measured facts:

- Minimal boundary run `20260612ch` stayed near baseline:
  p512/o128 corrected after-first decode was `97.707 tok/s`.
- In `20260612ch`, pure decode after the first five decode events showed:
  `forward_end` sync mean `3.470 ms`, median `3.778 ms`;
  `compute_logits_end` sync mean `0.0178 ms`, median `0.0056 ms`;
  `sample_start` sync mean `0.0087 ms`, median `0.0030 ms`.
- Forward-boundary run `20260612ci` also stayed near baseline:
  p512/o128 corrected after-first decode was `99.123 tok/s`.
- In `20260612ci`, pure decode after the first five decode events showed:
  `forward_start` sync mean `0.0020 ms`, median `0.0019 ms`;
  `forward_end` sync mean `3.674 ms`, median `3.775 ms`;
  `compute_logits_end` sync mean `0.0139 ms`, median `0.0054 ms`;
  `sample_start` sync mean `0.0043 ms`, median `0.0019 ms`.
- Accepted restore passed provenance sentinels `4752`, `11436`, and `198`.
- Accepted restore passed the no-thinking quality smoke: exact canaries,
  arithmetic, JSON, copy phrase, repeat stability, and baseline match.

Decision:

- Stop chasing input preparation, logits materialization, sampler, async output,
  D2H token copy, token-list conversion, or output packaging for the current
  `2x` target.
- The next target is the model forward itself or forward-stream dependencies:
  MoE decode kernels, attention/GDN pieces, TP collectives inside forward,
  XPU graph launch/replay, rank skew, route skew, or stream ordering before
  `forward_end`.

Immediate next probes:

1. **All-rank forward boundary timing.**
   Record a low-overhead `forward_start`/`forward_end` pair per TP rank, with
   route-window metadata and card IDs. If one rank owns the wait, chase route
   skew/topology. If all ranks wait similarly, chase shared forward kernels or
   graph replay.

2. **Layer-family forward split.**
   Use existing timing hooks or a narrow model-forward wrapper to split decode
   forward into attention/GDN, MoE, residual/norm, and collectives. Keep event
   count low; one family boundary per run if needed.

3. **Route-window replay against MoE kernels.**
   Since the bottleneck is now model-forward-side, prioritize captured Qwen3.6
   route windows in grouped-GEMM/MoE harnesses over more sampler/output work.

4. **Static c1 runner.**
   A direct in-process decode loop remains useful: if it still shows about
   `10 ms/token`, the model-forward attribution is confirmed outside server
   scheduling. If it improves, vLLM graph/executor coordination around forward
   is still part of the cost.

## 2026-06-12 All-Rank Forward Boundary And Larger Bets

This addendum records the all-rank follow-up to the minimal forward-boundary
split. It is diagnostic-only, not a promoted speed result. The key change was
to record and synchronize `forward_start`/`forward_end` on every TP worker,
instead of only seeing rank 0 through the async output path.

Artifacts:

- `data/qwen36-quark-int8-tp4-allrank-forwardboundary-20260612cj.log`
- `data/qwen36-quark-int8-tp4-allrank-forwardboundary-p512o128-metrics-20260612cj.json`
- `data/qwen36-quark-int8-tp4-allrank-forwardboundary-summary-20260612cj.json`
- `data/qwen36-quark-int8-tp4-allrank-forwardboundary-xpusmi-ps-20260612cj.json`
- `data/qwen36-quark-int8-tp4-accepted-restored-after-allrank-forwardboundary-20260612cj.log`
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-allrank-forwardboundary-20260612cj.json`
- `data/qwen36-quark-int8-tp4-accepted-quality-after-allrank-forwardboundary-nothink-smoke-20260612cj.json`
- `patches/vllm-qwen36-allrank-forward-boundary-20260612cj.diff`

Run setup:

- Diagnostic service used port `18081`.
- Diagnostic-only headroom: `GPU_MEMORY_UTILIZATION=0.85`,
  `MAX_NUM_SEQS=8`, 32K context unchanged.
- Rank-to-physical-device mapping from `xpu-smi ps`: rank 0 -> card 0,
  rank 1 -> card 1, rank 2 -> card 2, rank 3 -> card 3.
- Accepted TP4 was restored afterward on port `18080` with no diagnostic timing
  env vars.

Measured facts:

- p512/o128 diagnostic throughput stayed close enough for attribution:
  corrected after-first decode `95.529 tok/s`, e2e output `91.234 tok/s`,
  client TTFT `73.552 ms`, vLLM decode `10.389 ms/token`.
- All four TP ranks emitted forward-boundary rows.
- Pure decode after the first five decode events showed near-zero
  `forward_start` sync on every rank: all-rank mean `0.00159 ms`, median
  `0.00150 ms`.
- The model-forward wait sits after `forward_start`: all-rank
  `forward_end_after_start_sync_ms` mean `4.569 ms`, median `4.653 ms`.
- Per-rank `forward_end_after_start_sync_ms` means/medians:
  rank 0 `4.214/4.318 ms`, rank 1 `4.471/4.454 ms`,
  rank 2 `4.769/4.683 ms`, rank 3 `4.820/4.739 ms`.

Interpretation:

- This confirms the wait is model-forward-side on every TP rank, not a
  rank-0-only output/sampler artifact.
- In the unrotated mapping, ranks/cards 2 and 3 are consistently slower than
  ranks/cards 0 and 1 by roughly `0.55-0.61 ms` versus rank 0.
- The next attribution test is rank-to-card rotation. If the slow tail follows
  physical cards 2/3, focus on topology, PCIe, power, thermal, driver, or
  card-specific behavior. If the slow tail stays TP ranks 2/3, focus on shard
  imbalance, route skew, layer ownership, or per-rank graph shape.
- The accepted launcher now allows overriding `ONEAPI_DEVICE_SELECTOR` and
  `ZE_AFFINITY_MASK` while preserving the default `level_zero:0,1,2,3` /
  `0,1,2,3` mapping. That makes rotation runs reproducible without editing
  the production script.
- Restore gates passed: provenance sentinels `4752`, `11436`, `198`; no-thinking
  quality smoke with exact canaries, repeat stability, and baseline match.

Fresh external leads to keep in the queue:

- Intel's `intel/vllm:0.10.2-xpu` notes claim MoE models benefit from
  persistent MoE GEMM and fused activation kernels, including a reported
  `2.6x` end-to-end improvement for Qwen3-30B-A3B in that stack. Source:
  <https://github.com/intel/ai-containers/blob/main/vllm/0.10.2-xpu.md>.
- Intel's grouped-GEMM performance issue explicitly says MoE decode grouped
  GEMM depends strongly on real token routing distribution and that decode
  routing is often long-tail/skewed. Source:
  <https://github.com/intel/intel-xpu-backend-for-triton/issues/6389>.
- Recent `vllm-xpu-kernels` releases mention Xe2/Battlemage paged-decode and
  grouped-GEMM policy updates. Source:
  <https://github.com/vllm-project/vllm-xpu-kernels/releases>.
- vLLM's Arc Pro B-Series writeup names persistent-loop MoE, dynamic compute
  group balancing, multi-GPU scaling, PCIe P2P, async scheduling, and
  prefill/decode disaggregation as intended levers. Source:
  <https://vllm.ai/blog/2025-11-11-intel-arc-pro-b>.

Things to try next, from narrow to bolder:

1. **Rank/card rotation matrix.**
   Run the same all-rank probe with reversed and pair-swapped device order.
   This is the cheapest way to distinguish physical-card/topology skew from TP
   shard skew.

2. **Per-rank route ledger overlay.**
   Attach active-expert/window signatures to the all-rank forward-boundary
   rows. If ranks 2/3 also see heavier route shapes, prioritize route-aware
   expert placement or route-class kernels.

3. **Layer-family forward split, one boundary per run.**
   Split attention/GDN, MoE, residual/norm, and collectives with a very low
   event count. The all-rank probe says where to look; this identifies which
   forward family owns the `~4.5 ms` wait.

4. **Intel clean-stack bakeoff as a serious candidate.**
   Build or container-test the current Intel XPU stack against route fixtures
   first, then the full service only if exact output parity and route-fixture
   speed are clean. The container notes claim exactly the kind of MoE wins we
   need, but production adoption needs quality and stability gates.

5. **Persistent MoE island.**
   Prototype a resident W8A8 MoE execution path that keeps expert weights,
   scales, and common route-class state hot across decode tokens. This is a
   direct attempt to remove per-token kernel bubbles without changing model
   math.

6. **Dynamic compute-group balancing for skewed routes.**
   Instead of one generic grouped-GEMM policy, choose execution grouping based
   on the captured route class: one-hot, two-hot, broad-balanced, and
   long-tail. Exact same tokens and weights; only work partitioning changes.

7. **Expert physical re-layout or replication.**
   Use route histograms plus rank timing to move or duplicate the small hot
   expert set into faster card paths when VRAM allows. This is a schedule/data
   placement change, not a quantization or quality change.

8. **Hybrid TP/EP decode lane.**
   Keep attention/lm-head in the best current TP layout, but route MoE work
   through an expert-parallel island to reduce per-token TP collective pressure
   inside forward.

9. **Whole-token resident replay.**
   Capture the entire c1 decode step into a persistent Level Zero/SYCL path:
   input token, KV pointer advance, forward, exact greedy token, and commit.
   Use the current vLLM path as the reference oracle until every emitted token
   matches.

10. **Exact same-model branch verifier.**
    Speculate with the target model itself using temporary KV branches and
    commit only exact verified tokens. This avoids 4-bit/AWQ/draft-model
    quality risk, but it is only worth attempting after the single-token path
    is better understood.

11. **Topology/driver A-B lab.**
    Treat KMD, Level Zero, oneAPI, oneCCL, IGC, BIOS PCIe settings, ASPM, and
    physical slot order as real variables. The rank/card skew plus previous
    device-lost behavior suggests the runtime stack may be a major lever.

12. **External challenge bundle.**
    Package the route fixtures, all-rank timing, exact quality gates, launch
    command, Localmaxxing row, and hardware/topology into a small public issue
    or discussion. The target ask should be specific: remove `~4-5 ms/token`
    from Qwen3.6 35B-A3B W8A8 c1 decode on 4x B70 without changing outputs.

## 2026-06-12 Rank/Card Rotation Result

This addendum closes the first rank/card attribution loop. The result is
important because it prevents us from spending the next day on the wrong class
of fix.

Artifacts:

- `data/qwen36-quark-int8-tp4-allrank-forwardboundary-revmap-20260612ck.log`
- `data/qwen36-quark-int8-tp4-allrank-forwardboundary-revmap-p512o128-metrics-20260612ck.json`
- `data/qwen36-quark-int8-tp4-allrank-forwardboundary-revmap-summary-20260612ck.json`
- `data/qwen36-quark-int8-tp4-allrank-forwardboundary-revmap-xpusmi-ps-20260612ck.json`
- `data/qwen36-quark-int8-tp4-allrank-forwardboundary-rankmap-rev-20260612cl.log`
- `data/qwen36-quark-int8-tp4-allrank-forwardboundary-rankmap-rev-p512o128-metrics-20260612cl.json`
- `data/qwen36-quark-int8-tp4-allrank-forwardboundary-rankmap-rev-summary-20260612cl.json`
- `data/qwen36-quark-int8-tp4-allrank-forwardboundary-rankmap-rev-xpusmi-ps-20260612cl.json`
- `data/qwen36-quark-int8-tp4-accepted-restored-after-rankmap-rotation-20260612cl.log`
- `data/qwen36-quark-int8-tp4-accepted-provenance-after-rankmap-rotation-20260612cl.json`
- `data/qwen36-quark-int8-tp4-accepted-quality-after-rankmap-rotation-nothink-smoke-20260612cl.json`
- `data/qwen36-quark-int8-tp4-rankmap-rotation-comparison-20260612cl.json`
- `patches/vllm-qwen36-rankmap-forward-boundary-20260612cl.diff`

What happened:

- The env-only attempt with `ONEAPI_DEVICE_SELECTOR=level_zero:3,2,1,0` and
  `ZE_AFFINITY_MASK=3,2,1,0` did not rotate worker placement. `xpu-smi` still
  showed TP0/TP1/TP2/TP3 owning physical devices 0/1/2/3.
- A diagnostic-only vLLM hook,
  `VLLM_XPU_LOCAL_RANK_DEVICE_MAP=3,2,1,0`, was added to the XPU worker and
  distributed group device binding. With that hook, `xpu-smi` confirmed true
  reverse ownership: TP0 -> card 3, TP1 -> card 2, TP2 -> card 1, TP3 -> card 0.
- The true reversed diagnostic stayed near baseline: p512/o128 corrected
  after-first decode was `96.578 tok/s`; vLLM decode was `10.272 ms/token`.
- Accepted TP4 was restored afterward on port `18080`, with no timing or
  rank-map env vars. Restore gates passed: provenance sentinels `4752`,
  `11436`, `198`; no-thinking quality smoke with exact canaries, repeat
  stability, and baseline match.

Forward-boundary comparison, pure decode after first five events:

- Original unrotated mapping, rank -> physical card 0/1/2/3:
  rank 0 `4.214/4.318 ms` mean/median, rank 1 `4.471/4.454 ms`,
  rank 2 `4.769/4.683 ms`, rank 3 `4.820/4.739 ms`.
- Env-only reverse attempt was a no-op for placement. It still mapped
  0/1/2/3 and measured rank 0 `4.072/4.117 ms`, rank 1 `4.557/4.546 ms`,
  rank 2 `4.491/4.537 ms`, rank 3 `4.493/4.517 ms`.
- True reverse mapping, rank -> physical card 3/2/1/0:
  rank 0 `4.139/4.263 ms`, rank 1 `4.308/4.253 ms`,
  rank 2 `4.485/4.423 ms`, rank 3 `4.472/4.412 ms`.

Decision:

- The tail did not simply follow physical cards. Rank 0 stayed fastest after
  moving from physical card 0 to physical card 3.
- The remaining forward-side wait is more likely TP-rank/shard/route/graph
  behavior than a simple bad-card/topology-only issue.
- Physical topology is not cleared forever; card/rank interaction still shows
  some noise. But it is no longer the lead hypothesis for the `~4-5 ms/token`
  forward wait.

Next work that should move the result:

1. **Route-signature overlay on all-rank timing.**
   Add active expert/window IDs to the same all-rank boundary rows. We need to
   know whether ranks 1/2/3 are slower because they own heavier route windows
   or because their compiled shard does more work independent of routing.

2. **One-family-at-a-time forward split.**
   Add one low-overhead boundary per run around MoE, attention/GDN, residual
   norm, and TP collectives. The rank rotation says this is not a raw output
   path problem; now split the forward body without reintroducing the heavy
   event path that caused device loss.

3. **Rank-specific route fixture replay.**
   Replay captured route windows by TP rank in the kernel harness. If the slow
   rank windows are heavier in isolation, tune grouped-GEMM/route policy. If
   fixture costs are similar, focus on graph/collective ordering around those
   ranks.

4. **Persistent/route-class MoE path.**
   The highest-upside no-quality-loss bet remains exact W8A8 MoE execution
   with route-class-specific scheduling or persistent expert state. The rank
   rotation makes this more attractive than more device-environment tuning.

## 2026-06-12 Bigger/Bolder Ideas Refresh 20260612cm

This section records the next idea backlog after the rank/card rotation result.
It is intentionally separated from measured wins. The accepted speed anchor is
still the quality-gated `~100 tok/s` class TP4 endpoint, and the public
Localmaxxing exact-model/B70/vLLM query still returns only the existing
`99.428 tok/s` row. Nothing below is a promoted result until it passes the
usual provenance, exact canary, repeat-stability, and quality gates.

External signals checked during this refresh:

- Intel's current XPU container notes explicitly warn that some workloads can be
  slower than older releases while the stack transitions to the dedicated XPU
  kernel path. That makes a clean-stack bakeoff useful, but also means a newer
  image is not automatically a win. Source:
  <https://github.com/intel/ai-containers/blob/main/vllm/0.17.0-xpu.md>.
- oneDNN release notes now call out experimental grouped memory and grouped
  matmul for MoE, including Intel GPU optimization and an execution-time maximum
  group-size hint. This is directly relevant to route-skewed Qwen MoE decode.
  Source: <https://github.com/uxlfoundation/oneDNN/releases>.
- vLLM's XPU direction is moving into `vllm-xpu-kernels`, a dedicated SYCL/DPC++
  kernel package that already owns attention, GDN, MoE routing, gather, and
  expert-remapping operations. Source:
  <https://github.com/vllm-project/vllm-xpu-kernels>.
- The vLLM XPU migration RFC says the dedicated kernel library is meant to
  improve performance, maintainability, and integration quality versus the
  older IPEX-dependent path. Source:
  <https://github.com/vllm-project/vllm/issues/33214>.
- A public 4x Arc Pro B60 production-style benchmark reported that an
  Intel-optimized vLLM build improved TPOT by roughly `20-25%` on its workload.
  This is not a Qwen3.6/B70/current-model comparable, but it reinforces testing
  Intel-maintained builds and policies instead of assuming local flags are the
  whole story. Source:
  <https://embeddedllm.com/blog/benchmarking-llm-inference-intel-arc-pro-b60>.
- Upstream vLLM INT8/FP8 docs remain NVIDIA/AMD-centric for official fast paths,
  so our Quark W8A8-on-XPU path should be treated as an Intel-specific
  integration/kernel problem, not a generic vLLM quantization problem. Sources:
  <https://docs.vllm.ai/en/latest/features/quantization/llm_compressor/int8_w8a8/>
  and
  <https://docs.vllm.ai/en/latest/features/quantization/llm_compressor/fp8/>.

Near-term additions to things to try:

1. **Route overlay before more blind tuning.**
   Add low-overhead route signatures beside the all-rank forward-boundary rows:
   layer id, active expert count, max rows per expert, top expert ids, and a
   compact route hash. The rank/card rotation says the physical card is not the
   lead hypothesis; the next proof needs to say whether the slow ranks own
   heavier route windows or simply pay more graph/collective latency.

2. **Layer-family timing with route context.**
   Split the forward wait one family at a time: attention/GDN, router, MoE
   grouped GEMM, expert gather/scatter, dense/shared MLP, residual/norm, and TP
   collectives. Each run should add only one or two synchronization points so it
   does not repeat the heavy-probe `UR_RESULT_ERROR_DEVICE_LOST` failure mode.

3. **oneDNN grouped-matmul hint experiment.**
   Extend the existing route-window sidecar to test grouped memory with an
   execution-time max-group-size hint. The exact gate is captured-tensor output
   compare against `xpu_fused_moe`, not endpoint speed. If the hint helps
   skewed route windows, it becomes a candidate for a disabled live path.

4. **vllm-xpu-kernels MoE plugin branch.**
   Stop treating the local vLLM tree as the only integration point. Build a
   small branch in or beside `vllm-xpu-kernels` for the Quark W8A8 MoE decode
   path: route-class policy, expert remap, grouped GEMM, fused activation, and
   gather. This is better aligned with upstream XPU ownership and easier to
   turn into a maintainer challenge packet.

5. **Clean Intel stack matrix, measured by route fixtures first.**
   Compare local source, current Intel container, one release older/newer if
   available, and any Intel-optimized vLLM/LLM-Scaler variant. First gate:
   run real route fixtures or one-layer tensor compare, not the whole server.
   Second gate: full endpoint provenance and quality. Variables to record:
   oneAPI, IGC, Level Zero, oneCCL, PyTorch, vLLM, `vllm-xpu-kernels`,
   `SYCL_UR_USE_LEVEL_ZERO_V2`, block size, graph mode, and memory utilization.

6. **VTune/oneDNN/Level Zero proof packet.**
   Build one profiling packet for a short p512/o128 run: all-rank boundary
   timing, XPU occupancy/counters where available, oneDNN verbose for sidecar
   kernels, Level Zero queue timing if practical, xpu-smi power/frequency, and
   process-to-card mapping. This should answer whether the `~4-5 ms/token`
   forward wait is compute, command latency, collective synchronization, or
   idle dependency chaining.

7. **Static c1 decode micro-engine.**
   If the in-process no-server c1 harness beats vLLM materially, generate a
   fixed-shape c1 path for latency-critical requests while keeping vLLM as the
   correctness oracle. The micro-engine can reuse the exact checkpoint, KV
   state, tokenizer, and greedy sampler; it only removes generic serving
   machinery and dynamic graph overhead.

8. **Hybrid TP/EP MoE island with dense TP retained.**
   Keep attention, dense/shared layers, and logits in the current TP layout,
   but isolate MoE expert work into an expert-parallel or partially replicated
   island. The design goal is to avoid paying all-card TP synchronization for
   sparse expert work that can be local or route-class scheduled.

9. **VRAM-for-latency expert replication.**
   The 8-bit model leaves enough memory to consider duplicated hot experts or
   layer-specific expert packs. Use route histograms to choose a small hot set,
   not guesses. The quality gate is simple because weights are identical; only
   placement and scheduling change.

10. **Outlier-aware exactness guard.**
    Record whether particular layers/tokens have activation or route outliers
    that force slow conservative paths. A bolder branch could add an exact
    fallback lane for those rare windows while keeping the common window on the
    fastest W8A8 path. This is not a quality downgrade; it is a routing policy
    that prefers exactness over one-size-fits-all kernels.

11. **Two-card latency lane plus two-card utility lane.**
    Re-test TP2 as a first-class latency topology. If TP2 c1 is faster, use the
    other two cards for replicas, target-model branch verification, or
    aggregate traffic. Forcing every c1 token through four cards may be the
    wrong shape even if TP4 is good for capacity.

12. **Target-model branch farming as the real 2x fallback.**
    If exact single-token decode stalls below `150-170 tok/s`, the clean path to
    `>200 tok/s` is probably multi-token acceptance. Keep it quality-safe:
    branches may be proposed by ngram/MTP/heuristics, but only the current
    Quark W8A8 target model commits tokens after KV/hybrid-state transaction
    verification.

13. **Public maintainer challenge bundle.**
    Prepare a minimal repro bundle for Intel/vLLM maintainers: launch command,
    model id/revision, exact route fixtures, one-layer tensor checksums,
    all-rank timings, rank/card rotation result, Localmaxxing row, XPU stack
    versions, and the concrete target: remove `~4-5 ms/token` from c1 Qwen3.6
    35B-A3B Quark W8A8 decode on 4x B70 without changing emitted tokens.

14. **Quality gate expansion for bolder branches.**
    Keep the current exact canaries, but add BF16-fallback comparisons where
    feasible, prompt-class canaries, long-context needle, deterministic
    replay-hash checks, and a 30-60 minute stability soak before any bolder
    branch is called viable. Speed without output identity or stability still
    does not count.

Current priority order:

1. Route-signature overlay on all-rank boundary timing.
2. One-family-at-a-time forward split with route context.
3. Route-window oneDNN grouped-matmul hint test.
4. Clean Intel stack matrix on route fixtures.
5. Static c1/no-server ceiling harness.
6. If the ceiling remains poor, move serious effort into target-verified
   branch farming.

## Route-Fixture Bigger/Bolder Refresh 20260612cs

Added after the first-decode route fixture extraction. This refresh keeps the
same hard rule: the promoted answer must still be owned by the current
`nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` target model. The purpose here
is to turn the route-fixture lesson into a more aggressive work queue without
sliding into 4-bit, AWQ, Qwen3.5, or unverified speculation.

Fresh public benchmark snapshots:

- Exact current model on Localmaxxing is unchanged: one public exact-model row,
  `cmq8yhxvo001ipb0149aoa79o`, at `99.428 tok/s`, c1, 32K context.
- B70/Qwen/vLLM leaderboard snapshot has `Qwen/Qwen3.6-35B-A3B` at
  `99.770 tok/s` and the exact Quark W8A8 INT8 row at `99.428 tok/s`.
- B70/MoE leaderboard snapshot still has the exact Quark W8A8 row as the top
  returned B70 MoE row at `99.428 tok/s`.

Local model shape to bake into fixtures:

- `text_config.hidden_size=2048`
- `text_config.moe_intermediate_size=512`
- `text_config.num_hidden_layers=40`
- `text_config.num_experts=256`
- `text_config.num_experts_per_tok=8`
- `text_config.mtp_num_hidden_layers=1`
- Route fixture: three first-decode examples, `40` MoE layers each, one token
  per event, topk-8 expert IDs per layer.

External signals that reinforce the route-fixture direction:

- `vllm-xpu-kernels` is now the natural upstream XPU landing zone. Its public
  README lists SYCL/DPC++ custom ops using oneDNN, including MoE top-k,
  grouped top-k, MoE align/gather/expert remapping, and grouped GEMM:
  <https://github.com/vllm-project/vllm-xpu-kernels>.
- oneDNN matmul exposes `DNNL_ARG_HINT_MAX_GROUP_SIZE` as an execution-time
  hint for grouped matmul. The warning is important: the hint must be a valid
  upper bound or results can be incorrect, so this belongs behind captured
  route-fixture compare gates first:
  <https://uxlfoundation.github.io/oneDNN/dev_guide_matmul.html>.
- vLLM's MoE kernel design docs explicitly frame MoE as a kernel-selection
  problem with modular all-to-all and expert-kernel families:
  <https://docs.vllm.ai/en/latest/design/moe_kernel_features/>.
- Intel's public grouped-GEMM tuning issue says MoE grouped GEMM performance
  depends strongly on runtime route distributions and that decode-stage routes
  are often skewed/long-tailed:
  <https://github.com/intel/intel-xpu-backend-for-triton/issues/6389>.
- Other MoE runtime writeups point at two relevant ideas: expert parallelism
  can trade all-to-all communication for more expert-weight bandwidth, and
  alignment sorting matters for grouped-GEMM efficiency:
  <https://rocm.blogs.amd.com/software-tools-optimization/vllm-moe-guide/README.html>
  and
  <https://huggingface.co/blog/yiakwy-xpu-team/efficient-moe-align-sort-design-for-sglang>.

Concrete near-term additions:

1. **Route-fixture microbench first, endpoint second.**
   Build a small harness around the extracted first-decode routes and the exact
   Qwen shape above. The first version can use synthetic weights to measure
   dispatch/route overhead; the second version should load real layer weights
   and compare tensor output against `xpu_fused_moe` before any server wiring.

2. **Accepted-replay route side channel in the custom op.**
   Python route hooks are bypassed by compiled decode replay. Put the optional
   route hash/count capture inside the XPU MoE custom-op path or graph output
   path. It should emit only compact hashes/counters during diagnostics, not
   full expert lists on the serving path.

3. **Single-token/topk-8 persistent MoE lane.**
   Treat c1 decode as the primary target shape: one hidden vector, eight routed
   experts, hidden `2048`, expert intermediate `512`. Prepack weights, keep
   scratch resident, fuse activation/topk weighting where exact, and remove
   per-token primitive rebuilds.

4. **oneDNN grouped-matmul hint gate.**
   Try `DNNL_ARG_HINT_MAX_GROUP_SIZE` on captured topk-8 route windows with a
   strict current-output checksum, candidate-output checksum, max/mean diff,
   and automatic fallback. This is especially useful if real route windows show
   repeated skew, but it must be proven at the layer level first.

5. **Align/gather overhead split.**
   Measure route remap, align/sort, gather, GEMM1, activation, GEMM2, and
   unpermute separately for the single-token fixture. If align/gather dominates
   rows=1/topk=8, the kernel win is a fused path, not only faster GEMM.

6. **TP/EP simulator on real route fixtures.**
   Before another full endpoint topology test, run the route fixture through a
   placement simulator: current TP4, TP2, expert-parallel, hot-expert
   replicated, and hybrid dense-TP/MoE-EP. Score expected communication,
   weight bandwidth, and per-rank route pressure.

7. **No-server c1 ceiling with exact route ledger.**
   Pair the direct in-process c1 decode harness with route hashes from the
   custom-op side channel. If no-server c1 is still near `100 tok/s`, focus on
   kernels/topology. If it jumps materially, build the fixed-shape serving lane.

8. **Target-state transaction substrate before more speculation.**
   The config exposes one MTP layer, but it should not own emitted tokens until
   KV, GDN/hybrid state, scheduler counters, sampler state, and accepted-token
   ledgers have a verify/commit/rollback path. MTP is a proposer only; the
   Quark W8A8 target still commits.

Bigger, bolder ideas to keep alive:

1. **B70 W8A8 MoE island in `vllm-xpu-kernels`.**
   Build the persistent single-token/topk-8 path as an upstreamable XPU kernel
   island instead of a long-lived local vLLM monkeypatch. Inputs: hidden vector,
   topk IDs/weights, prepacked W8A8 expert tensors, resident scratch. Outputs:
   exact current hidden-state result and diagnostic timing counters.

2. **Memory-for-latency expert packs.**
   Spend spare VRAM on route-derived expert packs: duplicated hot experts,
   layer-local route packs, or card-local hotsets. This does not change weights
   or math; it trades memory for fewer remote/rank-stall cases.

3. **Whole-token command-list replay.**
   Capture the fixed decode bucket as a Level Zero command-list sequence with
   patchable pointers and route offsets. This is risky, but it directly attacks
   launch/fence bubbles across attention, MoE, residuals, logits, and sampler.

4. **Target-verified branch farm.**
   If exact c1 decode bottoms out below `150-170 tok/s`, use spare cards or
   spare VRAM to run target-model branches from cloned state. Proposers can be
   ngram, MTP, or route-trained, but only target-verified tokens commit. This
   is still no-quality-loss if the transaction substrate is exact.

5. **Latency lane plus aggregate lane.**
   Stop assuming TP4 must serve every use case. If TP2 or a fixed-shape c1 lane
   wins latency, use the other cards for replicas, target-verifier branches, or
   aggregate serving. Production can run two quality-gated lanes instead of one
   compromised launch.

6. **Route-class kernel generator.**
   Generate a tiny policy table from captured routes: single-token balanced
   topk, repeated hot expert, broad sparse, aggregate batch, and fallback.
   Runtime chooses the implementation from exact route statistics; numerical
   operations and weights stay identical.

7. **Maintainer challenge packet with executable fixtures.**
   Package the first-decode route fixture, exact model revision, launch command,
   vLLM/XPU stack versions, route-counter proof that Python hooks miss compiled
   replay, all-rank timings, Localmaxxing rows, and a one-layer executable
   compare harness. The ask should be specific: remove `~4-5 ms/token` from
   c1 Qwen3.6 35B-A3B Quark W8A8 decode on 4x B70 without token drift.

Artifacts for this refresh:

- `data/localmaxxing-qwen36-quark-w8a8-int8-exact-refresh-20260612cs.json`
- `data/localmaxxing-qwen-b70-vllm-leaderboard-20260612cs.json`
- `data/localmaxxing-b70-moe-leaderboard-20260612cs.json`

## First-Decode Route Fixture Planner 20260612ct

Added the CPU-only bridge from the compact first-decode fixture to the existing
route simulator and XPU MoE microbench tools:

- `scripts/qwen36-firstdecode-route-fixture-plan.py`

This does not touch the serving endpoint and does not run XPU kernels. It
emits JSONL route records that look like normal route-capture rows:
`counts`, `topk_ids`, `num_experts`, `num_tokens`, `layer`, `stage`,
`route_hash`, and fixture metadata. That makes the new compact route fixture
usable by `scripts/qwen36-route-parallelism-sim.py` and
`scripts/bench-qwen36-int8-moe-kernels.py`.

Validation run:

```bash
python3 -m py_compile scripts/qwen36-firstdecode-route-fixture-plan.py

python3 scripts/qwen36-firstdecode-route-fixture-plan.py \
  --output-json data/qwen36-quark-int8-tp4-firstdecode-route-fixture-plan-20260612ct.json \
  --output-jsonl data/qwen36-quark-int8-tp4-firstdecode-route-fixture-routes-20260612ct.jsonl \
  --markdown-out data/qwen36-quark-int8-tp4-firstdecode-route-fixture-plan-20260612ct.md

python3 scripts/qwen36-route-parallelism-sim.py \
  data/qwen36-quark-int8-tp4-firstdecode-route-fixture-routes-20260612ct.jsonl \
  --output-json data/qwen36-quark-int8-tp4-firstdecode-route-parallelism-sim-20260612ct.json \
  --markdown-out data/qwen36-quark-int8-tp4-firstdecode-route-parallelism-sim-20260612ct.md \
  --window-size 1 --stride 1 --max-num-tokens 1 --include-windows
```

Measured planning facts:

- The adapter emitted `120` records: `3` first-decode fixture events across
  all `40` MoE layers.
- The route rows cover `215` globally active experts, `960` total expert
  assignments, and `80` unique topk tuples.
- Each one-token layer record has exactly `8` active experts and `8`
  assignments.
- Across the three fixture events, the mean per-layer union active expert
  count is `13.45`; mean pairwise topk Jaccard is `0.471`. This confirms
  useful route reuse within a layer, but not a single static route.
- The TP-local expert weight/scale footprint for one MoE layer shard is about
  `194.250 MiB`; single-token scratch is only about `0.085968 MiB`. Memory is
  not the limiting factor for a persistent topk-8 layerlet.
- Naive EP placement is risky for c1: contiguous EP4 proxy mean pressure
  `1.771`, p95 `2.500`; round-robin EP4 mean `1.892`, p95 `2.500`.
- Static greedy placement on this tiny sample can balance row pressure
  (`1.000` mean/p95), but it is a route-derived policy, not a generic
  launch-flag win.
- A hot-replicated `ep4_hot16_replicated_greedy` proxy covers all rows in this
  small fixture with `1.000` mean/p95 pressure and `1.188x` max expert memory
  relative to TP4. Treat that as a direction for route-derived hot packs, not
  proof that EP/hot replication will beat the kernel path.

Decision:

- Do not lead with naive EP for c1. With only eight routed rows per layer,
  route imbalance can erase the theoretical bandwidth win.
- The next low-risk speed experiment should be a layer-9 rows=1 XPU MoE
  microbench using the generated JSONL, but only when the accepted serving
  endpoint is stopped or an isolated XPU is available.
- The highest-upside no-quality-loss kernel branch remains a persistent
  TP-local single-token/topk-8 W8A8 MoE path with active-expert or route-class
  dispatch, then exact tensor compare before any endpoint wiring.

Next XPU microbench command, deferred until the serving endpoint is isolated:

```bash
/home/steve/.venvs/vllm-xpu/bin/python scripts/bench-qwen36-int8-moe-kernels.py \
  --route-jsonl data/qwen36-quark-int8-tp4-firstdecode-route-fixture-routes-20260612ct.jsonl \
  --route-layer-regex 'layers[.]9[.]mlp[.]experts' \
  --rows 1 --iterations 100 --warmup 20 \
  --output-json data/qwen36-quark-int8-firstdecode-l9-r1-microbench-20260612ct.json \
  --markdown-out data/qwen36-quark-int8-firstdecode-l9-r1-microbench-20260612ct.md
```

Artifacts for this pass:

- `scripts/qwen36-firstdecode-route-fixture-plan.py`
- `data/qwen36-quark-int8-tp4-firstdecode-route-fixture-plan-20260612ct.json`
- `data/qwen36-quark-int8-tp4-firstdecode-route-fixture-plan-20260612ct.md`
- `data/qwen36-quark-int8-tp4-firstdecode-route-fixture-routes-20260612ct.jsonl`
- `data/qwen36-quark-int8-tp4-firstdecode-route-parallelism-sim-20260612ct.json`
- `data/qwen36-quark-int8-tp4-firstdecode-route-parallelism-sim-20260612ct.md`

## Bigger Bolder Queue Refresh 20260612da

This pass adds the follow-up ideas requested after the accepted-lane manifest
and route-fixture work. It is a planning/checkpoint update only: no endpoint
promotion, no quality claim, and no Localmaxxing submission. The accepted
single-request reference remains the clean `~99 tok/s` Qwen3.6 35B-A3B Quark
W8A8 INT8 TP4 lane.

Fresh outside signals:

- Localmaxxing public API still shows the exact
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` B70/vLLM row at
  `99.428 tok/s`, and the broader same-family B70/vLLM row at `99.770 tok/s`.
  There is no public exact-model B70/vLLM result above `200 tok/s` to copy.
- Intel's grouped-GEMM XPU issue says MoE decode routing is highly skewed and
  that kernels need tuning from real token distributions, not uniform synthetic
  groups.
  Source: <https://github.com/intel/intel-xpu-backend-for-triton/issues/6389>.
- A new Intel XPU benchmark issue says SYCL-TLA and Triton MoE timing must
  include the same work, especially token grouping/prologue and gather. This
  matters because our offset/prologue experiments can look good in isolation
  and still lose in end-to-end decode.
  Source: <https://github.com/intel/intel-xpu-backend-for-triton/issues/7190>.
- vLLM's Arc Pro B-Series writeup calls out persistent-loop MoE, dynamic
  compute-group balancing, fused activation, multi-GPU scaling, and
  speculative decoding as intended XPU directions.
  Source: <https://vllm.ai/blog/2025-11-11-intel-arc-pro-b>.
- Current vLLM XPU docs list Intel Arc Pro B-Series as validated hardware and
  Qwen3-30B-A3B as optimized for XPU FP16/dynamic-FP8, which is adjacent but
  not the exact Qwen3.6 Quark W8A8 checkpoint.
  Source: <https://docs.vllm.ai/en/v0.18.0/models/hardware_supported_models/xpu/>.
- The public 2x B70 Qwen3-30B-A3B FP8 report shows `40.60 tok/s`
  single-stream and about `997 tok/s` output throughput at high concurrency.
  That reinforces the split: B70 aggregate throughput can be strong, but
  single-request latency needs a different lane.
  Source: <https://www.reddit.com/r/LocalLLM/comments/1sfa0iw/2x_intel_arc_b70_benchmark/>.

Concrete next gates to add before more endpoint experiments:

1. **Graph-path tensor capture gate.**
   Eager route replay is insufficient. Add a capture point around the compiled
   XPU/custom-op path or graph replay path and compare live tensors against the
   accepted lane before any endpoint promotion. Required for all kernel-path
   changes.

2. **Prologue-inclusive MoE timing gate.**
   Every MoE microbench must report both kernel-only and end-to-end layerlet
   timing: route/topk, token grouping or offsets, GEMM1, activation, quant,
   GEMM2, gather, and final scatter. Kernel-only wins are not accepted unless
   the full layerlet also improves.

3. **Real-route grouped-GEMM autotune harness.**
   Feed the first-decode route fixture and later routecapture6 windows into a
   grouped-GEMM tuner. Score candidates against long-tail c1 route skew,
   not uniform `M=8192` or synthetic balanced groups.

4. **Quality gate v2.**
   Keep old token sentinels as cache-versioned provenance only. Add a modern
   lane with no-thinking answer canaries, generated-token logprob/argmax
   checks, graph/eager tensor parity, and selected BF16 fallback comparisons
   when affordable.

5. **AOT cache and binary manifest required for every candidate.**
   Continue using the accepted-lane manifest style: cache root digest, extension
   SHA256/symbols, source repo heads/dirty counts, env scrub, speed artifact,
   quality artifact, and provenance state.

Bigger no-quality-loss opportunities to keep in the queue:

1. **Persistent c1 W8A8 MoE island.**
   Build one exact Qwen3.6 decode layerlet with resident weights/scales,
   resident scratch, fixed topk-8 descriptors, and route-class dispatch.
   The goal is to remove per-token launch/prologue overhead while preserving
   identical W8A8 math and exact tensor parity.

2. **Tile-native Quark W8A8 repack at load time.**
   Repack the same int8 weights and scales into the layout the XPU grouped-GEMM
   kernels prefer. This should not change quality because values are identical;
   it may remove runtime swizzles, pointer chasing, or unfavorable memory
   access.

3. **Hot-expert memory-for-latency packs.**
   Use route histograms to duplicate or pre-pack common experts per GPU/rank.
   The route fixture says memory is available for layer-local packs; the gate is
   whether real longer traces keep enough hot-expert locality to pay back.

4. **Hybrid TP/EP or asymmetric latency lane.**
   Stop assuming TP4 is the only serving shape. Test a latency lane where dense
   blocks stay TP-friendly but MoE expert work is placed or replicated by route
   class. Also test TP2 plus two replicas if it reduces collectives and improves
   single-request decode while preserving a separate aggregate lane.

5. **Whole-token Level Zero command-list supernode.**
   Capture the fixed c1 decode bucket as one patchable command-list sequence
   across attention/GDN, MoE, residual, logits, and sampler. This is bold and
   risky, but it attacks the launch/fence overhead left after small Python
   changes stopped mattering.

6. **Target-owned branch farm.**
   If exact c1 decode stalls below `150-170 tok/s`, run target-model branches
   from cloned state on spare cards or spare process slots. Commit only tokens
   verified by the current Qwen3.6 target state. This can cross `200 tok/s`
   without quality loss if the state transaction/rollback substrate is exact.

7. **Route-class kernel generator.**
   Generate a small set of exact kernels or kernel policies from route classes:
   single-token sparse topk, repeated hot-expert topk, broad sparse topk,
   aggregate batch, and fallback. Dispatch from measured route statistics.

8. **Single-user direct runner.**
   Build a no-HTTP/no-frontdoor c1 decode runner around the exact accepted
   model path. If it is not materially faster, stop blaming API/frontdoor
   overhead and focus only on GPU kernels, collectives, and graph fences.

9. **Rank/card and PCIe/oneCCL topology bakeoff.**
   Make rank-to-card rotation and oneCCL/P2P topology a repeatable matrix.
   The gain may be modest, but it is cheap and can expose whether one GPU or
   link is consistently dragging TP4 latency.

10. **Maintainer-grade challenge packet.**
    Package the exact model revision, accepted manifest, route fixtures,
    prologue-inclusive timings, graph-path parity need, Localmaxxing rows,
    xpu-smi/topology, and a one-layer executable W8A8 compare harness. The ask:
    remove several ms/token from c1 Qwen3.6 35B-A3B Quark W8A8 decode on B70
    without changing outputs.

Immediate priority:

1. Build the graph-path tensor capture gate.
2. Make MoE timing prologue-inclusive.
3. Run real-route grouped-GEMM/autotune on the first-decode fixture.
4. Only then try another endpoint candidate.

## Prologue-Inclusive MoE Gate Plumbing 20260612db

Added the first concrete gate from the `20260612da` queue to
`scripts/bench-qwen36-int8-moe-kernels.py`. This is measurement/reporting
plumbing only; it does not change the live endpoint and does not claim a speed
win.

What changed:

- Each benchmark row now emits `prologue_inclusive_gate`.
- The run emits `prologue_inclusive_gate_summary`.
- The gate only considers full MoE layerlet timings that include route/remap,
  quant, GEMM1, activation, quant2, GEMM2, and gather. Isolated GEMM or
  prologue timings remain diagnostics only.
- A non-reference candidate must be exact within `--exactness-threshold`, meet
  `--target-layerlet-us`, and beat the current `xpu_fused_moe` full-layerlet
  timing by `--min-speedup-vs-xpu`.
- The default target is `160 us/layerlet`, matching the current rough budget
  for a plausible non-speculative `>200 tok/s` path. This is a gate target,
  not a current result.
- Markdown reports now include a "Prologue-Inclusive Gate" section with row
  readiness, best exact non-reference candidate, speedup, and endpoint
  promotion blockers.

Validation run without touching the live serving endpoint:

```bash
python3 -m py_compile scripts/bench-qwen36-int8-moe-kernels.py

/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/bench-qwen36-int8-moe-kernels.py --help

git diff --check -- scripts/bench-qwen36-int8-moe-kernels.py
```

I also ran a synthetic no-device import check of the new gate helpers. It
correctly marked an exact `150 us` full-layerlet candidate as ready against a
`160 us` target and selected `fused_prologue_offset_gemm` as the best exact
non-reference candidate.

Deferred real XPU command for the next isolated benchmark window:

```bash
/home/steve/.venvs/vllm-xpu/bin/python scripts/bench-qwen36-int8-moe-kernels.py \
  --route-jsonl data/qwen36-quark-int8-tp4-firstdecode-route-fixture-routes-20260612ct.jsonl \
  --route-layer-regex 'layers[.]9[.]mlp[.]experts' \
  --rows 1 --iterations 100 --warmup 20 \
  --target-layerlet-us 160 \
  --output-json data/qwen36-quark-int8-firstdecode-l9-r1-prologue-gate-20260612db.json \
  --markdown-out data/qwen36-quark-int8-firstdecode-l9-r1-prologue-gate-20260612db.md
```

Decision:

- Future MoE kernel candidates must pass this prologue-inclusive gate before
  any endpoint experiment.
- Passing this gate still is not enough for endpoint promotion; graph-path
  tensor capture, accepted-lane quality gates, and a manifest update remain
  mandatory.

## Graph-Capture Census Hook And Bolder Queue Addendum 20260612dc

This pass adds the next requested tracking checkpoint and records a concrete
first step toward the graph-path tensor capture gate. It is still diagnostic
plumbing only: no endpoint speed claim, no quality claim, and no serving
launcher change.

Local source hook:

- Added an opt-in graph-capture census hook to the dirty local
  `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/fused_moe_interface.py`
  tree. The scoped patch artifact is:
  `patches/qwen36-xpu-moe-graph-capture-census-20260612dc.diff`.
- New env switches are disabled by default:
  `VLLM_XPU_MOE_LIVE_ABI_CAPTURE_SKIPS`,
  `VLLM_XPU_MOE_LIVE_ABI_DEFER_CAPTURE_SAMPLES`,
  `VLLM_XPU_MOE_LIVE_ABI_DEFER_CAPTURE_DELAY_MS`, and
  `VLLM_XPU_MOE_LIVE_ABI_DEFER_CAPTURE_MAX_PENDING`.
- If the XPU stream is being captured, the hook can now write a safe metadata
  record instead of silently returning. It records tensor shape, dtype, device,
  stride, data pointer, layer, rank, call ID, and route shape, but it does not
  copy tensor contents during capture.
- If deferred samples are enabled, the hook schedules a bounded daemon thread
  that waits until after capture and then samples small tensors/checksums. It
  only calls `torch.xpu.synchronize()` when the sampled output is on XPU, so the
  helper is safe in CPU/no-device smoke tests.

New gate parser:

- Added `scripts/qwen36-moe-live-abi-graph-capture-gate.py`.
- The parser checks opt-in live-ABI JSONL logs for:
  `stream_capture_skip_no_tensor_copy` records, deferred
  `deferred_post_capture_sample` records, required capture-safe tensor metadata,
  and deferred output sample checksums.
- A passing parser result proves only that the requested graph-capture evidence
  was observed. It does not prove endpoint speed, output quality, or full
  graph/eager tensor parity.

Validation already run without touching the live serving endpoint:

```bash
python3 -m py_compile \
  /home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/fused_moe_interface.py

python3 -m py_compile scripts/qwen36-moe-live-abi-graph-capture-gate.py

python3 scripts/qwen36-moe-live-abi-graph-capture-gate.py \
  /tmp/qwen36-live-abi-gate-synthetic.jsonl \
  --layer-regex 'layers[.]9[.]' --rank 0 \
  --require-capture-skip --require-deferred-sample
```

Synthetic helper smoke also imported the local kernel module, wrote one
capture-safe record and one deferred sample record with CPU tensors, and
confirmed observations:

- `stream_capture_skip_no_tensor_copy`
- `deferred_post_capture_sample`

Deferred real endpoint diagnostic command for the next isolated launch window:

```bash
VLLM_XPU_MOE_LIVE_ABI_FILE=/mnt/fast-ai/vllm-cache-exp/qwen36-live-abi-{rank}-{pid}.jsonl \
VLLM_XPU_MOE_LIVE_ABI_CAPTURE_SKIPS=1 \
VLLM_XPU_MOE_LIVE_ABI_DEFER_CAPTURE_SAMPLES=1 \
VLLM_XPU_MOE_LIVE_ABI_MAX_LINES=20 \
VLLM_XPU_MOE_LIVE_ABI_LAYER_REGEX='layers[.]9[.]' \
VLLM_XPU_MOE_LIVE_ABI_RANK=0 \
scripts/launch-qwen36-quark-int8-accepted.sh

python3 scripts/qwen36-moe-live-abi-graph-capture-gate.py \
  /mnt/fast-ai/vllm-cache-exp/qwen36-live-abi-*.jsonl \
  --layer-regex 'layers[.]9[.]' --rank 0 \
  --require-capture-skip --require-deferred-sample \
  --output-json data/qwen36-quark-int8-liveabi-graph-capture-gate-20260612dc.json \
  --markdown-out data/qwen36-quark-int8-liveabi-graph-capture-gate-20260612dc.md
```

New external signals from the quick scan:

- Hugging Face lists the base Qwen3.6-35B-A3B artifact as compatible with
  vLLM, SGLang, KTransformers, and Transformers. Treat alternative engines as
  ceiling probes only; they are not substitutes unless they can run this exact
  W8A8 INT8 lane with comparable quality evidence:
  <https://huggingface.co/Qwen/Qwen3.6-35B-A3B>.
- A recent vLLM B70/XPU issue asks which host BOM should be targeted for dual
  B70 plus Qwen3 MoE dynamic FP8 and points at possible boundaries across
  vLLM, `vllm-xpu-kernels`, oneCCL, Level Zero, and the `xe` kernel driver.
  That reinforces keeping host stack, driver, oneCCL, and graph-cache identity
  in every manifest:
  <https://github.com/vllm-project/vllm/issues/41663>.
- LLM Compressor has an active W8A8 INT8 support thread for
  Qwen3.6-35B-A3B. That is relevant to quality and portable quant tooling, but
  it is not a reason to switch away from the current accepted checkpoint:
  <https://github.com/vllm-project/llm-compressor/issues/2787>.
- Community B70 setup notes continue to mention llama.cpp SYCL and Vulkan
  paths. Use them as strict same-model/same-quant ceiling probes if possible,
  not as production replacements or lower-bit shortcuts.

Additional bigger, bolder ideas to keep visible:

1. **Graph-capture tensor parity ladder.**
   Start with metadata-only capture proof, then deferred small checksums, then
   one-layer accepted-vs-candidate tensor compare, then all-layer route-window
   tensor compare. Endpoint candidates should climb that ladder in order.

2. **Per-layer route-class AOT micro-library.**
   Build a small library of exact layerlet variants at startup for the route
   classes actually observed: single-token sparse topk-8, repeated hot tuple,
   broad sparse tuple, and aggregate batch. Dispatch by route hash/class while
   keeping the current fallback.

3. **Persistent cross-layer MoE conveyor.**
   Instead of one persistent island per layer, try a resident device-side
   conveyor that keeps route descriptors, scratch buffers, and expert work
   queues alive across several MoE layers. This attacks host fences and
   repeated setup at a larger scale.

4. **DPAS/XMX tile-layout proof packet.**
   Create a tiny exact W8A8 Quark weight/scale repack experiment that proves
   which layout feeds B70 DPAS/XMX best. The values must be bit-identical after
   unpack; only memory order and descriptors change.

5. **Host BOM and stability matrix as a speed feature.**
   Benchmark kernel, Intel compute-runtime, oneAPI, oneCCL, BIOS PCIe ASPM,
   Resizable BAR, power limit, and fan curves as a controlled matrix. A stable
   lower-latency host stack is a valid no-quality-loss win.

6. **Strict 8-bit engine ceiling bakeoff.**
   Try SGLang, KTransformers, llama.cpp SYCL, and Intel containers only if they
   can run the same model family and an 8-bit W8A8-like quality lane. The goal
   is to find a ceiling or borrow a kernel idea, not to accept lower quality.

7. **Route-aware topology scheduler.**
   Use route ledgers plus rank/card timing to choose rank placement, hot expert
   placement, and possibly asymmetric dense/MoE placement. If rank skew is
   repeatable, bake that into the latency lane.

8. **Quality tribunal instead of one sentinel file.**
   Combine exact token sentinels, cache-versioned sentinels, no-thinking task
   canaries, prompt-logprob rank checks, route-window tensor parity, and a
   small BF16 fallback comparison packet. A bolder speed branch must satisfy
   multiple independent quality views.

9. **Maintainer/crowd challenge after the graph gate.**
   Publish the accepted manifest, Localmaxxing result, graph-capture gate,
   one-layer route fixture, and prologue-inclusive timings. Ask Intel/vLLM and
   B70 users for exact Qwen3.6 W8A8 INT8 settings or kernel patches that beat
   `~100 tok/s` c1 without output drift.

10. **Verifier-owned parallelism remains the only non-kernel 2x path.**
    If the kernel path stalls below the target, return to exact target-state
    transactions: temporary KV/GDN/request-state forks, target-owned branch
    farming, and commit-only-after-verification streaming. This is the biggest
    path to `>200 tok/s` without lowering quality, but only after exact state
    rollback is proven.

Updated immediate order:

1. Run the graph-capture census on an isolated endpoint launch and parse it
   with `scripts/qwen36-moe-live-abi-graph-capture-gate.py`.
2. Run the prologue-inclusive layer-9 real-route microbench when the serving
   endpoint can be stopped or an isolated XPU is available.
3. Build the first full layerlet tensor-compare gate against accepted
   `xpu_fused_moe`.
4. Use the results to choose between persistent MoE island, route-class AOT
   micro-library, topology/host-stack work, or exact verifier parallelism.

## Route-Class AOT Planning Gate 20260612dd

Added the first CPU-safe planning gate for the route-class AOT micro-library
idea:

- `scripts/qwen36-route-class-aot-plan.py`
- `data/qwen36-quark-int8-tp4-route-class-aot-plan-20260612dd.json`
- `data/qwen36-quark-int8-tp4-route-class-aot-plan-20260612dd.md`

Why this was the right next move:

- The accepted TP4 service is still live on `18080` and `xpu-smi ps` shows the
  four B70 cards are effectively occupied by the current workers. Running a
  side microbench on top of that would risk OOM or contaminate endpoint timing.
- The route-class AOT planner uses the already captured first-decode fixture,
  so it can refine the next kernel direction without touching the endpoint or
  changing model behavior.

Command run:

```bash
python3 -m py_compile scripts/qwen36-route-class-aot-plan.py

python3 scripts/qwen36-route-class-aot-plan.py \
  data/qwen36-quark-int8-tp4-firstdecode-route-fixture-routes-20260612ct.jsonl \
  --output-json data/qwen36-quark-int8-tp4-route-class-aot-plan-20260612dd.json \
  --markdown-out data/qwen36-quark-int8-tp4-route-class-aot-plan-20260612dd.md
```

Measured planning result:

- Status: `needs_more_route_windows_before_aot_commit`.
- Records used: `120/120`.
- Fixture events: `3`.
- Layers: `40`.
- Global unique route classes: `80`.
- Per-layer exact route classes: `80`, mean `2.000` per layer.
- Top-1 class per layer covers `66.7%` of this tiny fixture.
- Top-2 classes per layer cover `100%` of this tiny fixture.
- Exact unique hot-pack memory for the seen layers is only `408.229 MiB` per
  TP shard, about `5.3%` of the full seen-layer MoE shard footprint.
- Duplicate route-pack upper bound for two classes per layer is `485.625 MiB`
  per TP shard.

Interpretation:

- This supports the route-class AOT direction technically: a small
  per-layer/topk-8 route-class micro-library would be memory-cheap on B70 if
  broader route captures preserve similar locality.
- It is not enough evidence to write kernels yet. Three first-decode fixture
  events are too few; the next graph-capture pass needs to collect more
  route-window data before the AOT table is trusted.
- The current best no-quality-loss kernel sequence is now:
  graph-capture census, broader route-window capture, route-class AOT planner,
  prologue-inclusive layerlet timing, then a full layerlet tensor-compare gate.

New concrete next thing to try:

1. Extend the graph-capture census from metadata/checksum evidence into a
   compact route-window ledger for `10+` isolated decode requests.
2. Re-run `scripts/qwen36-route-class-aot-plan.py` against that larger ledger.
3. If per-layer classes stay small and hot-pack memory stays below about
   `1-2 GiB` per TP shard, build a layer-9 route-class AOT layerlet prototype.
4. If route classes explode, drop route-class codegen and focus on a more
   generic persistent MoE conveyor or verified multi-token parallelism.

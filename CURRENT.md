# Current Promoted Results

Date: 2026-06-12

## Qwen3.6 35B-A3B Quark W8A8 INT8

2026-06-13 notes update:

- Added `notes/2026-06-13-experiment-coverage-audit.md` and linked its main
  carryovers into `notes/2026-06-12-qwen36-next-bigger-bets.md` as
  `Historical Coverage Audit 20260613q`. The audit confirms the current Qwen
  W8A8 accepted base and rejected paths are covered, and it preserves older
  wins that are easy to forget: Qwen Q4 TP3 beating four-card latency
  (`46.194319 tok/s` versus `34.929313 tok/s`), exact graph/epilogue fusion,
  fused beta/alpha projection reaching `50.129900 tok/s`, validated FP8
  n-gram/topology/library-provenance lessons, and MiniMax warm-cache promotion
  discipline around `93.443623 tok/s`. No new endpoint, model, quantization, or
  speed result was promoted. Next Qwen work remains site-labeled all-rank
  layer/collective timing, collective replay, persistent W8A8 MoE layerlet
  work, and oracle `k=1` parity repair.

2026-06-13 notes update:

- Added `notes/2026-06-13-minimax-m27-transfer-audit-for-qwen36.md` and folded
  its findings into `notes/2026-06-12-qwen36-next-bigger-bets.md` as
  `MiniMax M2.7 Transfer Audit 20260613p`. The useful MiniMax transfers are
  instrumentation and promotion discipline, not 4-bit quantization: add
  site-labeled all-rank collective timing, test MoE output reduction inside or
  adjacent to the persistent W8A8 layerlet, apply tiny-collective policies only
  after shape/call-site proof, use warm-cache paired A/B promotion gates, and
  keep structured-output fast lanes separate from free-form chat decode claims.
  The older MiniMax GGUF wins add two conditional Qwen checks: verify
  attention/KV placement and CPU-staging behavior, then only run row-packing or
  microtile sweeps if the measured Qwen W8A8 shapes point there.
  Already-tried Qwen direct ports remain rejected: `block-size 256` and
  `MBT512`.

2026-06-13 notes update:

- Added an explicit `Active Backlog Index 20260613o` to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. It now separates current
  status, tried-and-ruled-out 2x levers, useful-but-insufficient building
  blocks, immediate next probes, larger untried bets, and quality/reliability
  gates. Next preferred work remains all-rank layer-family timing, then
  collective-only replay.

2026-06-13 notes update:

- Added `scripts/qwen36-rank-route-forward-overlay.py` and
  `data/qwen36-rank-route-forward-overlay-20260613n.{json,md}` to overlay
  accepted replay-digest `num_rows=1` route signatures with all-rank forward
  timing. The route counters are identical across ranks for `40/40` layers
  while forward-end wait still ranges from `4.214 ms` to `4.820 ms`, so simple
  rank route skew is rejected as the cause of the slow-rank spread. The digest
  did not include hot-expert pair payloads (`0/0` hot layers with data). Next
  probe should split model forward by layer family and collectives on the slow
  ranks before generating rank-specific route kernels.
- Re-checked the live Fast Gemma result API after the user pointed to the
  dashboard source again. The result feed is unchanged (`354` rows, same
  `470.526 tok/s` top row), but the Space source now has a useful production
  control-plane pattern: paginated bucket listings, content-hash file caching,
  bounded fetch fanout, background listing warmup, single-flight TTL refresh,
  and stale-good fallback. Added those ideas to the Gemma transfer notes as
  readiness/warm-artifact handling, not a direct Qwen speed claim.

2026-06-13 notes update:

- Re-checked the live Fast Gemma dashboard API after the user pointed to the
  Gemma E4B board again. The feed still has `354` rows, the same
  `470.526 tok/s` top row, and unchanged keyword counts versus
  `data/gemma-dashboard-results-summary-20260613k.json`, so I did not create a
  redundant snapshot. The transferable lesson remains methodology only:
  captured decode lanes, exact PPL/prompt-logprob fallback, readiness-gated
  warm artifacts, and preserving negative runs.
- Added a reusable Qwen forward-bottleneck decision artifact:
  `scripts/qwen36-forward-bottleneck-decision.py`,
  `data/qwen36-forward-bottleneck-decision-20260613m.json`, and
  `data/qwen36-forward-bottleneck-decision-20260613m.md`. It consolidates the
  current gap budget, tail check, all-rank forward-boundary timing, rank-map
  reversal, worker label timing, presampler split, and Gemma source check.
  Decision: c1 work should stay on model-forward/forward-stream dependencies,
  with rank/layer route-signature overlay and a persistent one-dispatch MoE
  layerlet as the next no-quality-loss target. HTTP/SSE, detok-only, static
  lm-head restriction, and physical-card-only topology tuning are deprioritized
  as lead levers for the `200 tok/s` target.

2026-06-13 notes update:

- Ran a non-invasive accepted-endpoint stream-vs-final-only c1 tail check on
  `127.0.0.1:18080` using the current Quark W8A8 INT8 Qwen3.6 service.
  Artifacts:
  `data/qwen36-quark-int8-tp4-tailcheck-stream-p512o256-20260613l.json`,
  `data/qwen36-quark-int8-tp4-tailcheck-nonstream-p512o256-20260613l.json`,
  and
  `data/qwen36-quark-int8-tp4-tailcheck-latency-decomp-20260613l.{json,md}`.
  Streaming corrected after-first throughput was `100.836 tok/s` with vLLM
  decode `9.919 ms/token`; non-streaming e2e was `97.827 tok/s` with vLLM
  decode `9.914 ms/token`. Backend stream throughput matched the vLLM decode
  histogram within `0.018%`, and queue time stayed around `0.012-0.016 ms`.
  Together with prior forward-boundary evidence, this rules out detok,
  final-only responses, SSE/HTTP, frontdoor queueing, and output packaging as
  2x-class levers for the current Qwen c1 path. Next work should stay on
  model-forward reductions, persistent MoE layerlets, TP topology/collectives,
  whole-token graph capture, or oracle `k=1` speculation repair.

2026-06-13 notes update:

- Refreshed the Fast Gemma dashboard snapshot in
  `data/gemma-dashboard-results-summary-20260613k.json` after the user
  pointed back to the E4B board as an ideas source for our own Gemma lane.
  Extended `notes/2026-06-12-gemma-dashboard-transfer-ideas.md` with a
  transfer matrix: first profile Gemma lm-head/logits, sampler, detok, and
  response-write costs; require full-head fallback and token-ID parity for any
  restricted logits path; audit sliding-window attention execution; keep a
  fast decode lane plus reference prompt-logprob/PPL lane; treat benchmark
  prompt precache as non-production. This is an ideas update only; no accepted
  Qwen endpoint or model configuration was changed.

2026-06-13 notes update:

- Added worker-boundary COW trace plumbing to
  `scripts/launch-qwen36-quark-int8-ngram-trace.sh` and ran
  `qwen36-quark-int8-tp4-oracle1-nobonus-cachefilter-cow-20260613j` with
  oracle `k=1`, graph disabled, full-accept bonus suppression, and worker
  cache filtering. Artifacts:
  `data/qwen36-quark-int8-tp4-oracle1-nobonus-cachefilter-cow-20260613j-*`
  plus
  `data/qwen36-spec-trace-rootcause-oracle1-nobonus-cachefilter-cow-20260613j.{json,md}`.
  The result still fails parity, but the cause is much narrower: schedule
  mismatches are `0`, accept mismatches are `2`, and the worker prepares the
  expected token window while the verifier repeats the prior accepted token.
  Next speculative work should trace no-spec/no-graph and full-bonus verifier
  logits/KV side by side before any wider speculation. The diagnostic endpoint
  was stopped afterward; the accepted endpoint was restored on `127.0.0.1:18080`
  and passed provenance in
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-cowtrace-20260613j.json`.
- Refreshed the Fast Gemma dashboard idea feed again in
  `data/gemma-dashboard-results-summary-20260613j.json` and updated
  `notes/2026-06-12-gemma-dashboard-transfer-ideas.md` plus
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. The latest parsed feed has
  `354` rows and a `470.526 tok/s` public top row for Gemma E4B, used only as
  a methodology signal: fast decode lane plus exact PPL/prompt-logprob fallback,
  readiness-gated warm/capture artifacts, lm-head/sampler isolation, and
  preserving negative runs.

2026-06-13 notes update:

- Tightened `scripts/replay-qwen36-spec-trace.py` to distinguish suppressed
  bonus schedule/replay/accept failures and to report post-output
  computed-token skew. Added
  `data/qwen36-spec-trace-rootcause-summary-20260613i.md` plus v2 replay
  artifacts for oracle cache-filter, keep-computed, recompute, and ngram5
  no-bonus traces. The actionable finding is that the oracle cache-filter trace
  has `0` schedule mismatches but `2` accept mismatches: the suppressed bonus is
  fed back as the next draft, then the exact target rejects it. This is a
  verifier/KV/input-position boundary problem, not a draft-quality problem.
  Next speculative work is gated on oracle `k=1` parity before any wider ngram
  or MTP work.

2026-06-13 notes update:

- Refreshed the Fast Gemma Challenge feed after the user pointed to the E4B
  dashboard as an ideas source for our Gemma lane. Added
  `data/gemma-dashboard-results-summary-20260613i.json` and expanded
  `notes/2026-06-12-gemma-dashboard-transfer-ideas.md` with the frontier
  checklist: token-ID decode records, exact prompt-logprob/PPL fallback,
  readiness-only warmup accounting, captured width-1 propose/decode graph,
  fused accept bookkeeping after parity is fixed, and full artifact parity
  bundles. The current top row is `470.526 tok/s`, but it is treated only as a
  process/control-plane signal because it is Gemma E4B on challenge hardware and
  includes benchmark-specific precache.

2026-06-13 notes update:

- Added a post-fullcandidate c1 endpoint budget using the currently restored
  Quark W8A8 INT8 backend. Artifacts:
  `data/qwen36-quark-int8-tp4-fullcandidate-c1-p512o512-metrics-20260613h.json`,
  `data/qwen36-c1-gap-budget-fullcandidate-20260613h.{json,md}`, and
  `data/qwen36-moe-fusion-target-budget-offsetactive-20260613h.{json,md}`.
  The fresh p512/o512/c1 baseline is `99.533 tok/s` corrected, `98.045 tok/s`
  e2e, and `10.048 ms/token` decode. Hitting `200 tok/s` requires saving
  `5.048 ms/token`, or `126.191 us` across each of the 40 MoE layerlets if
  outside-forward cost stays unchanged.
- Updated `scripts/qwen36-moe-fusion-target-budget.py` so it accounts for the
  newer exact fused-prologue offset-GEMM and active-offset-GEMM replay paths.
  The strongest exact offset replay mean is `209.052 us/layer`, estimating
  `172.471 tok/s` if it translated perfectly endpoint-wide. The calculated
  layerlet target is `189.101 us/layer`; offset-GEMM remains about
  `19.952 us/layer` short. Decision: do not promote this as a speed result.
  The next no-quality-loss implementation target is a persistent/one-dispatch
  MoE layerlet, whole-token capture, or exact verifier-safe multi-token
  acceptance stacked on top.

2026-06-13 notes update:

- Reviewed the live Fast Gemma Challenge dashboard result feed again after the
  user flagged the Gemma E4B board as a source of transferable ideas. Added
  `data/gemma-dashboard-results-summary-20260613-gemmalessons.json` and a
  "Fast Gemma Frontier Refresh 20260613" section in
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. Added reusable fetcher
  `scripts/fetch-gemma-dashboard-summary.py` and refreshed snapshot
  `data/gemma-dashboard-results-summary-20260613h.json`; the live feed now has
  `353` parsed rows and still tops out around `470.53 tok/s`. Strong recurring
  signals remain graph/capture, fast decode plus exact eval fallback,
  prefix-cache warmup, lm-head/sampler cost isolation, token-ID/end-only detok
  lanes, and acceptance telemetry for speculative paths. These are planning
  inputs only: no Qwen model, quantization, endpoint, or promoted result was
  changed.

2026-06-13 notes update:

- Restored the full W8A8 diagnostic XPU extension symbols from the archived
  `build/temp-before-onednn-grouped-20260612064136` candidate into the lab
  install after backing up binaries with tag `20260613-fullw8a8diag`. Extended
  `scripts/qwen36-w8a8-offset-abi-smoke.py` to cover quant-out ops and child
  timeouts. Fresh installed-package smoke now executes `base`, `offsets`,
  `active_offsets`, `quant_out`, and `silu_quant_out`. Binary hashes are in
  `data/qwen36-w8a8-fullcandidate-installed-sha256-20260613f.txt`.
- Ran layer-20 rank-0 replay with `--enable-offset-gemm` and
  `--enable-active-offset-gemm`. Artifacts:
  `data/qwen36-replay-digest-moe-layerfloor-offsetactive-20260613f.{json,log,md}`.
  All candidates were exact (`max_abs_diff=0.0`). Mean `xpu_fused_moe` was
  `315.292 us`; mean fused-prologue offset-GEMM was `209.052 us`; mean
  active-offset was `211.170 us`. Best exact row was `190.025 us`, but
  `0/16` rows met the `125 us/layerlet` target, so no endpoint promotion is
  allowed. The accepted backend was restarted with the full diagnostic
  extension, reached `/v1/models` after `63s`, and passed provenance in
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-fullcandidate-20260613g.json`.

2026-06-12 notes update:

- Ran a full MoE layerlet floor probe on layer-20 rank-0 replay-digest c1
  routes. Artifacts:
  `data/qwen36-replay-digest-moe-layerfloor-layer20-rank0-gpu-layerfloor-20260612dz.{json,log,md}`.
  Current `xpu_fused_moe` averaged `290.622 us` across the 16 route windows;
  the best exact non-reference candidate was `preallocated_staged`, exact
  (`max_abs_diff=0.0`) and `1.269x` faster, but still `217.342-239.290 us`
  per layerlet. The prologue-inclusive promotion gate found `0/16` rows under
  the `125 us` target, so no endpoint promotion is allowed. This confirms the
  main limiter is per-token dispatch/fixed MoE-layer overhead, not expert-table
  size. During the first restore, the backend hit
  `UR_RESULT_ERROR_DEVICE_LOST` on the provenance completion; the recovery
  snapshot in `data/qwen36-layerfloor-devicelost-recovery-20260612dz/` showed
  all four XPUs passed a copy smoke after stale vLLM workers were cleared. A
  clean retry restore passed provenance in
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-layerfloor-retry-20260612dz2.json`.
  The accepted endpoint is again serving `qwen36-35b-a3b-fp8` with `32768`
  max context on `127.0.0.1:18080`.

2026-06-12 notes update:

- Ran a compact-active upper-bound grouped-GEMM timing window on the same
  layer-20 rank-0 replay digest route file. Artifacts:
  `data/qwen36-replay-digest-compactactive-layer20-rank0-gpu-compactactive-20260612dy.{json,log,md}`.
  Compacting each route from the full 256-expert table to only the 8 active
  experts reduced temporary harness allocation by roughly `32x`, but barely
  moved latency: `gemm1` improved from `91.139 us` to `90.627 us` (`-0.5622%`)
  and `gemm2` improved from `90.998 us` to `90.213 us` (`-0.8632%`). The
  accepted endpoint was restored on `18080`, `/v1/models` reports
  `qwen36-35b-a3b-fp8` with `32768` max context, and provenance sentinels
  passed. Conclusion: active-expert table compaction is not the path to
  `>200 tok/s`; the next work should reduce dispatch count/fixed per-token
  overhead through persistent MoE layerlets or whole-token graph capture.

2026-06-12 notes update:

- Ran the real XPU top128 hot-only layer-20 grouped-GEMM timing window from the
  replay-digest route converter. Artifacts:
  `data/qwen36-replay-digest-hotset-top128-layer20-rank0-hotonly-gpu-20260612dx.{json,log,md}`.
  On `xpu:0`, fully covered rank-0 layer-20 decode rows showed no speed win:
  full 256-expert exact `gemm1` averaged `100.533 us`, while top128 hot-only
  averaged `101.408 us` (`+0.8703%`); full exact `gemm2` averaged `102.365 us`,
  while top128 hot-only averaged `103.594 us` (`+1.2005%`). The accepted
  endpoint was restored on `18080`, `/v1/models` reports
  `qwen36-35b-a3b-fp8` with `32768` max context, and the provenance sentinels
  passed. Conclusion: top128 admission is still valuable, but a table-size-only
  grouped-GEMM fast path is not; the speed path needs a persistent/one-dispatch
  layerlet, fused hot/cold kernel, or static decode graph.

2026-06-12 notes update:

- Added `scripts/qwen36-digest-hotpack-admission.py` and generated
  `data/qwen36-digest-hotpack-admission-top64-top128-decode1-20260612dw.{json,md}`.
  Across `55520` decode rows, top64 has mean coverage `0.7022` but is fully
  hot only `16.1%` of the time; top128 has mean coverage `0.9130`, median row
  coverage `1.0`, and is fully hot `58.2%` of the time. The high-value layer
  set `8,9,13,16,19,20,21,38` reaches top128 mean coverage `0.9377-0.9564`
  with roughly `67.7-72.3%` fully-hot admission, making top128 hot-only
  admission for these eight layers the next cleaner no-quality-loss prototype.
  Top64 remains a fused hot/cold kernel target, not a hot-only lane.

2026-06-12 notes update:

- Added `scripts/qwen36-replay-digest-to-route-jsonl.py` to convert replay
  digest rows into the route-count JSONL schema used by the existing
  grouped-GEMM hotset harness. The layer-20 rank-0 decode conversion emitted
  `347` rows with zero invalid rows and zero count mismatches. Dry-run hotset
  coverage from the converted route file shows top64 at `0.7788` mean coverage
  but fully-hot on only `84/347` rows, while top128 reaches `0.9564` mean
  coverage and is fully hot on `251/347` rows. This makes top128 a stronger
  first layer-20 layerlet candidate if VRAM is acceptable, and reinforces that
  top64 needs a one-dispatch/persistent hot+cold fallback rather than another
  split-launch path. No live XPU timing run was attempted because the accepted
  backend was using about `32653 MiB` on XPU 0. The Gemma dashboard lesson
  folded into this branch is process-level: keep speed claims tied to quality
  guards and preserve negative results when scheduler/launch overhead defeats a
  tempting optimization.

2026-06-12 notes update:

- Extended `scripts/qwen36-replay-digest-summary.py` with route-hash counters
  and `--num-rows` filtering, then generated route-class summaries for the
  20260612dq hot trace. The all-shape route-hash view is dominated by
  prefill/chunk rows and is not the right latency signal. The decode-only
  `num_rows=1` view has diffuse route hashes: top-16 route hashes average only
  `0.0596` coverage per layer, with about `342` unique route hashes per layer,
  so route-class kernel banks are not the first single-token target. A wider
  decode-only hot-expert plan shows static top32/top64/top128 resident packs at
  `0.503` / `0.702` / `0.913` weighted coverage for `971 MiB` / `1.94 GiB` /
  `3.89 GiB` per rank. This makes top64 or top128 static hot-pack replication
  the next stronger no-quality-loss branch, with exact cold fallback.

2026-06-12 notes update:

- Added `scripts/qwen36-digest-hotpack-plan.py` and
  `data/qwen36-digest-hotpack-plan-20260612ds.{json,md}` to turn the
  replay-digest hot atlas into a concrete VRAM-for-latency plan. The model's
  Quark W8A8 local-rank expert shard is `795648` bytes (`0.759 MiB`), and a
  static all-layer top-16 hot pack would add only `485.6 MiB/rank`. Static
  per-layer top-16 coverage is `0.620` weighted across the replay, while the
  recorded dynamic per-call top-16 upper bound is `0.751`. This shifts the next
  no-quality-loss implementation target toward exact route-aware hotset
  admission with cold fallback, while keeping a static top-16/threshold layer
  pack as the lower-risk first kernel prototype. The accepted endpoint on
  `18080` remained healthy.

2026-06-12 notes update:

- Added `notes/2026-06-12-gemma-dashboard-transfer-ideas.md` after reviewing
  the public Fast Gemma Challenge dashboard, workspace guide, eval-prompt page,
  and public digest/results API. Transferable ideas for our Gemma lanes:
  PPL as a first-class speed gate, prompt-logprob compatibility,
  production-safe static-prefix caching, lm-head keep-set pruning with full-head
  fallback, sliding-window attention audits, speculative acceptance histograms,
  exact-fidelity kernel checks for partial RoPE/cos-sin/BF16/tie-breaking,
  avoiding per-token host sync, paired multi-draw A/B, and immutable manifests.
  This is a planning note only; no endpoint or promoted speed result changed.

2026-06-12 notes update:

- Added a "Hot-Expert Replay Digest Atlas 20260612dq" section to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`, plus
  `patches/vllm-xpu-qwen36-replay-digest-hot-experts-20260612dq.diff`,
  hot-digest prompt metrics, four rank-local JSONL traces, and
  `data/qwen36-replay-digest-hot-summary-20260612dq.{json,md}`. The diagnostic
  build adds `VLLM_XPU_MOE_REPLAY_DIGEST_HOT_EXPERTS`; `git apply --check`
  passed against the active kernel checkout and `py_compile` passed for
  `scripts/qwen36-replay-digest-summary.py`. The atlas has `59040/59040` valid
  rows, zero invalid rows, all 40 MoE layers on all four workers, `48`-column
  rows (`16 + 2*16`), `493672` hot-pair observations, and top-16 hot-expert
  coverage of about `62%` to `82%` by layer. This makes hot-pack admission,
  top-16 replicated tile caches, route-class kernels, and hybrid hot/cold
  TP/EP policy the next concrete no-quality-loss branches. No diagnostic speed
  result was promoted.

2026-06-12 notes update:

- Added a "Post-Review Bigger Bets Refresh 20260612dq" section to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. It records the current public
  Localmaxxing status (`99.428 tok/s` exact quantized HF ID and `99.770 tok/s`
  B70/Qwen-family row), folds in current vLLM/XPU/EP/grouped-GEMM/B70 host-stack
  signals, and adds the next planning queue: hot-expert digest columns,
  hot-expert overlap scoring, explicit VRAM-for-latency budgeting, TP4/TP2/
  single-card latency splits, collective telemetry, validated-BOM A-B testing,
  real-route grouped-GEMM tournaments, and quality gate v3. The bolder backlog
  now includes hot-expert mirroring, hybrid TP-dense/EP-MoE, one-rank decode
  ownership with expert coprocessors, persistent W8A8 MoE layerlets, whole-token
  static decode supergraphs, expert layout compilation, route-class kernel
  banks, verifier-owned branch farming, replica/TP production split, and a
  maintainer challenge packet. No endpoint was changed and no speed result was
  promoted.

2026-06-12 notes update:

- Added an accepted backend p512/o512 telemetry baseline with
  `scripts/qwen36-xpusmi-dump-summary.py`. Direct backend streaming measured
  `99.885 tok/s` corrected after-first output throughput, `98.387 tok/s` e2e,
  and `10.012 ms/token` vLLM decode. `xpu-smi` sampled `25` rows per B70:
  mean GPU frequency was about `2517-2526 MHz`, mean power `98-104 W`, memory
  used about `32655 MiB` per card, PCIe read/write `0`, and every sample was
  `Not Throttled`. Non-daemon `xpu-smi` could not read utilization or
  temperature without elevated MEI access. This points the next speed work at
  runtime/kernel/collective latency rather than thermal throttling. No speed
  result was promoted.

2026-06-12 notes update:

- Added an "All-Rank Replay Digest Capture 20260612do" section to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. The replay-digest launcher
  now supports `VLLM_XPU_MOE_REPLAY_DIGEST_ALL_RANKS=1`, and
  `scripts/qwen36-replay-digest-summary.py` provides reusable JSON/Markdown
  summaries. The isolated all-rank run emitted four digest files, one per
  local rank/device, with `105120` valid rows total, `26280` rows on each of
  `xpu:0..3`, all 40 MoE layers on every local rank, zero invalid or negative
  layer rows, and c1 decode `(1, 8, 256, 2048)` dominating with `100960` rows.
  The accepted backend was restored on `18080`, `/v1/models` passed after
  `66s`, and a short completion smoke succeeded. No speed result was promoted.

2026-06-12 notes update:

- Added a "Replay Digest Layer-ID Fix And Bigger Ideas 20260612dn" section to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. The diagnostic replay digest
  path now receives explicit layer IDs from the Quark INT8 XPU fused-MoE path
  when replay digest, live-ABI, or oneDNN sidecar diagnostics are enabled.
  The isolated `18082` capture produced `40` records, `16518` valid digest
  rows, zero negative layer rows, and every MoE layer `0..39` present; the
  dominant shape was c1 decode `(1, 8, 256, 2048)` with `15534` rows. The
  accepted backend was restored on `18080`, `/v1/models` passed after `57s`,
  and a short completion smoke succeeded. New artifacts include the layer-ID
  JSONL/summary/completions, accepted restore log, a Localmaxxing B70/Qwen
  refresh, and active-stack source diff files under `patches/`. No speed
  result was promoted.

2026-06-12 notes update:

- Added an "Additional Bigger Bets After User Review 20260612dm" section to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. The new backlog items focus
  on larger no-quality-loss speed paths: VRAM-for-latency expert mirroring,
  hybrid TP/EP latency lanes, a rank-coordination elimination audit, an
  autotune tournament over real route classes, c1-specialized attention
  microbenching, one-rank logits/sampler ownership, exact same-quant engine
  shootouts, a static decode graph executor, power/clock/thermal telemetry as
  a required benchmark axis, and verifier-first speculative service design.
  Priority after the replay-digest layer-ID fix is to build the coordination
  ledger and static decode runner, then use the route atlas to choose between
  expert mirroring and route-class autotune. No endpoint was changed and no
  speed result was promoted.

2026-06-12 notes update:

- Added a "Replay Digest SYCL-8 Diagnostic 20260612dl" section to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. The oneAPI 2025.3/SYCL-8
  digest extension first built and linked against `libsycl.so.8`, but the
  initial endpoint failed on first completion because the helper defaulted
  `GDN_KERNELS=OFF` and the diagnostic `_xpu_C` lacked `gdn_attention`.
  Rebuilding with `GDN_KERNELS=ON` produced a larger `_xpu_C.abi3.so`
  (`55818904` bytes, SHA256
  `64b3198a0727091f0b3a8acd92dc014a6b5700c555ef51e49e7d19b9a65acd06`) that
  exports `gdn_attention`, `qwen36_moe_replay_digest_probe`, and
  `qwen36_moe_onednn_sidecar_probe`. The corrected no-filter diagnostic
  endpoint reached health in `71s`, completed four deterministic 64-token
  requests with identical outputs, and emitted
  `data/qwen36-replay-digest-replay-digest-sycl8-gdn-nofilter-20260612dl--1938680.jsonl`.
  The summary has `23` dumper records, `2336` valid digest rows, counter
  movement from `40` to `10920`, `300` unique shape summaries, and `1488`
  unique digest combinations. Limitation: all `layer_index` values are `-1`,
  so the next patch must pass reliable layer IDs into the fused path and log
  more/all ranks. `scripts/build-vllm-xpu-kernels-xpu-c-only.sh` now defaults
  `GDN_KERNELS=ON` to avoid rebuilding an extension that cannot execute this
  model. The accepted endpoint was restored afterward and `/v1/models` passed
  after `65s`. No speed result was promoted.

2026-06-12 notes update:

- Added a "Things To Try And Bigger Bets Refresh 20260612dj" section to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. It records the immediate
  follow-ups from the replay-digest diagnostic failure: lazy-load the digest
  module instead of preloading the package during vLLM registry inspection,
  finish the SYCL-8/oneAPI 2025.3 digest build, keep graph-replay evidence
  file-backed and bounded, post only clean accepted Localmaxxing results, build
  an upstream XPU diff table, run a host-stack/BOM A-B, measure collectives
  directly, and add context/KV sweeps. It also adds larger no-quality-loss bets:
  expert-parallel latency lane, single-rank dense path plus remote expert
  service, per-layer route-class microkernel library, persistent device-side
  MoE decode loop, tile-native Quark repack with tensor parity, target-verified
  branch farming, same-model engine bakeoff, validated-stack mirror boot, and
  an executable public challenge packet. Sources folded in include vLLM XPU
  docs, vLLM FusedMoE design docs, Intel grouped-GEMM routing discussion, and
  current dual-B70/vLLM stability issue traffic. The diagnostic launcher now
  keeps overlay `__init__.py` side-effect-light, symlinks digest `_xpu_C` as a
  normal extension, derives oneAPI `lib` from `ONEAPI_COMPILER_VARS`, and
  `DRY_RUN_IMPORT=1 scripts/launch-qwen36-quark-int8-replay-digest.sh` passed
  against the existing IntelLLVM 2026 digest build. No endpoint was changed and
  no speed result was promoted.

2026-06-12 notes update:

- Added the replay digest isolated build checkpoint to
  `notes/2026-06-12-qwen36-next-bigger-bets.md` and
  `data/qwen36-replay-digest-build-20260612di.{json,log}`, plus
  `scripts/launch-qwen36-quark-int8-replay-digest.sh`. The diagnostic patch
  artifact now has the correct added-file hunk count (`164` lines) and avoids
  `sycl::max` inside the device lambda. The first build failed because the
  copied source snapshot included stale `.deps`; after removing only the
  snapshot `.deps`, the build reached the digest source, exposed the hunk-count
  truncation, and then succeeded incrementally with IntelLLVM 2026. The
  build-tree `_xpu_C.abi3.so` is `50689752` bytes with SHA256
  `e033ad76c7d2c21938715763ba646f42b4f66ff19cb15476a1c10dac5b04e2fa`; `nm -D`
  shows `qwen36_moe_replay_digest_probe`, and direct Python import of the
  build-tree extension registers both replay-digest and sidecar ops. Importing
  through the copied `/tmp` package overlay segfaulted, so the new launcher
  creates an overlay package that direct-loads the build-tree extension via
  `importlib` before vLLM imports `_xpu_C`; `DRY_RUN_IMPORT=1` passed with
  `replay_digest_import_ok`. No endpoint was changed and no speed result was
  promoted.

2026-06-12 notes update:

- Added a "Bigger Opportunity Refresh 20260612di" section to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. The refresh records the
  latest public Localmaxxing confirmation for the exact
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` B70/vLLM row
  (`99.428 tok/s`) and the broader B70/Qwen current-family row
  (`99.770 tok/s`, about `127.55 GiB` total allocated VRAM across four B70s).
  It adds immediate things to try: isolated replay-digest build, upstream XPU
  MoE/collective diff packet, single-card/TP2 latency lane probe,
  expert-parallel sketch, power/frequency telemetry, target-owned verifier
  lane, native INT8 MoE microkernel fork point, and an external challenge
  bundle. It also adds larger bets: one-B70 hot active model lane, four exact
  replicas for production routing, expert-cache resident EP lane, decode-only
  scheduler bypass, Xe2 occupancy autopsy, patchable Level Zero decode loop,
  same-output engine bakeoff, hardware topology experiment, and target-owned
  speculative branch farming across idle cards. No endpoint was changed and no
  speed result was promoted.

2026-06-12 notes update:

- Added `patches/vllm-xpu-qwen36-replay-digest-probe-20260612dh.diff` and a
  "Replay Digest Patch Artifact 20260612dh" section to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. The patch adds a
  disabled-by-default XPU custom op, `qwen36_moe_replay_digest_probe`, called
  after INT8 MoE `moe_gather` to mutate a preallocated device digest ring with
  layer IDs, route hashes, rows-per-expert summaries, and bounded output-byte
  checksums. This is the next graph-path observability step after the live-ABI
  capture showed Python hooks do not reliably see replayed decode routes.
  `git -C /home/steve/src/vllm-xpu-kernels apply --check` passed for the patch;
  the only warning was the existing `fused_moe_interface.py` file-mode
  mismatch. The patch was not applied to the dirty kernel checkout, no endpoint
  was changed, and no speed result was promoted. Follow-up source audit found
  the patch depends on the active local W8A8/live-ABI/sidecar source stack:
  `qwen36_moe_sidecar.cpp` is untracked in the kernel checkout and the binding
  files are substantially modified, so the next isolated build should start
  from that active source snapshot rather than raw `origin/main`.

2026-06-12 notes update:

- Added a "Bolder Queue After Latency Gate 20260612dh" section to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. This records the immediate
  next work from the accepted latency decomposition and graph live-ABI lesson:
  a replay-safe XPU MoE digest custom-op patch artifact, graph-output parity
  before endpoint promotion, real-route prologue-inclusive layerlet timing,
  VRAM budget re-accounting for topology choices, cache-versioned quality gate
  v2, and reliability soak requirements for any faster branch. The refreshed
  bigger queue adds a single-token topk-8 W8A8 expert microprogram, persistent
  MoE conveyor with route work stealing, tile-native Quark W8A8 repack cache,
  latency topology inversion, whole-token static decode runner, patchable
  Level Zero decode supergraph, verifier-owned parallel branches, same-model
  engine ceiling bakeoff, and an executable maintainer challenge packet. No
  endpoint was changed and no speed result was promoted.

2026-06-12 notes update:

- Added `scripts/qwen36-latency-decomp-summary.py` and fresh accepted-lane
  c1 latency decomposition artifacts for the restored
  `liveabi-graphcapture-20260612df` endpoint. Backend streaming
  p512/o512/c1 measured `100.024 tok/s` corrected after first chunk and vLLM
  decode histogram `9.998 ms/token`; backend non-streaming measured only
  `99.044 tok/s` e2e with vLLM decode `9.952 ms/token`; frontdoor streaming
  measured `99.971 tok/s` corrected with vLLM decode `10.004 ms/token`.
  Queue time was effectively zero (`~0.012 ms`). The summary gate status is
  `device_or_vllm_runtime_bound_not_http_or_frontdoor`: client throughput
  matches vLLM decode within `0.006%`, frontdoor is within `-0.053%` of direct
  backend, and non-streaming is not faster enough to matter. Current best is
  `100.480 tok/s` from vLLM decode histogram, or `9.952 ms/token`; the
  `200 tok/s` target requires `5.000 ms/token`, so this path needs about a
  `49.76%` per-token latency reduction inside vLLM/XPU/runtime, not HTTP/SSE
  changes. No model or endpoint configuration was changed.

2026-06-12 notes update:

- Added `scripts/run-qwen36-liveabi-graph-capture.sh`, an opt-in graph-path
  live-ABI capture runner, and tightened
  `scripts/qwen36-live-abi-routes-to-jsonl.py` so truncated, invalid, or
  duplicate/dummy expert samples cannot be promoted into route-class AOT
  planning. The accepted launcher still scrubs live-ABI env vars by default;
  only `VLLM_XPU_MOE_LIVE_ABI_ALLOW=1` enables this diagnostic mode.
- The isolated `liveabi-graphcapture-20260612df` run restored the accepted TP4
  endpoint afterward on `18080` and the health check passed. The graph-capture
  gate passed with `228` records: `60` stream-capture skips, `60` deferred
  post-capture samples, and `108` checksum records across layers `9`, `19`,
  `29`, and `39`.
- The corrected filtered route ledger emitted `0` clean rows:
  `52` truncated route samples and `8` duplicate/dummy route samples were
  dropped, with `168` non-deferred records ignored. The route-class AOT plan is
  now explicitly `skipped_no_clean_route_rows`; the earlier optimistic planner
  interpretation from unfiltered graph-capture samples is not promotable.
- Key lesson: Python-level live-ABI hooks can prove graph-capture presence, but
  they do not reliably observe actual XPU graph replay decode routes. Next
  no-quality-loss performance work should move route observability into the
  XPU custom op/C++ layer or use an eager-route proxy gate before AOT kernel
  generation. The refreshed idea queue adds graph-safe route digests,
  persistent MoE conveyors, full/partial model replication probes, TP/EP
  topology splits, and verifier-owned branch farming as larger paths toward
  `>200 tok/s` without lowering quality.

2026-06-12 notes update:

- Added `scripts/qwen36-live-abi-routes-to-jsonl.py`, a CPU-safe bridge from
  graph-capture live-ABI deferred samples into the route JSONL format consumed
  by `scripts/qwen36-route-class-aot-plan.py`. This lets the next isolated
  endpoint capture become a route-class AOT planning ledger without touching
  the currently live accepted endpoint. The converter reads the current model
  config for `num_experts_per_tok` and `num_experts`, preserves source path and
  line provenance, emits stable route hashes, and marks partial/truncated
  top-k samples separately from clean rows. Synthetic validation converted two
  deferred samples into route rows and the AOT planner accepted that output.
  Added a "Live-ABI Route Ledger Bridge And Bigger Ideas 20260612de" section
  with immediate reproduction commands plus larger no-quality-loss bets:
  route entropy atlas, persistent/cache-aware MoE worker, B70 tile-layout
  proof, CCL/topology A/B, decode-only direct runner, route-class AOT codegen,
  and verifier-owned branch farming. No production endpoint was changed and no
  new speed result was promoted.

2026-06-12 notes update:

- Added `scripts/qwen36-route-class-aot-plan.py` plus route-class AOT planning
  artifacts:
  `data/qwen36-quark-int8-tp4-route-class-aot-plan-20260612dd.{json,md}`.
  Because the accepted TP4 endpoint still occupies all four B70s, this was a
  CPU-safe planning gate rather than an XPU timing run. It consumed the
  first-decode route fixture and found `120/120` usable rows, `3` fixture
  events, `40` layers, `80` global route classes, and exactly `2.000`
  route classes per layer on average. Top-1 route class per layer covers
  `66.7%` of the tiny fixture; top-2 covers `100%`. Exact unique hot-pack
  memory for the seen layers is only `408.229 MiB` per TP shard, about `5.3%`
  of the full seen-layer MoE shard footprint, so a route-class AOT
  micro-library is memory-plausible. Status is
  `needs_more_route_windows_before_aot_commit`: the next graph-capture pass
  should collect `10+` isolated decode requests before kernel codegen.

2026-06-12 notes update:

- Added the graph-capture census checkpoint and a wider no-quality-loss idea
  bank to `notes/2026-06-12-qwen36-next-bigger-bets.md`. The local dirty
  `vllm-xpu-kernels` tree now has disabled-by-default live-ABI graph-capture
  hooks for capture-safe metadata records and bounded deferred post-capture
  samples; the scoped patch artifact is
  `patches/qwen36-xpu-moe-graph-capture-census-20260612dc.diff`. Added
  `scripts/qwen36-moe-live-abi-graph-capture-gate.py` to validate JSONL logs
  for stream-capture skip records, deferred samples, tensor metadata, and
  output sample checksums. Static validation passed (`py_compile` on the local
  source and parser), and a synthetic helper smoke produced both
  `stream_capture_skip_no_tensor_copy` and `deferred_post_capture_sample`
  observations. The new backlog adds graph-capture parity ladder, per-layer
  route-class AOT micro-library, persistent cross-layer MoE conveyor,
  DPAS/XMX tile-layout proof packet, host BOM/stability matrix, strict 8-bit
  engine ceiling bakeoff, route-aware topology scheduler, multi-view quality
  tribunal, maintainer/crowd challenge packet, and verifier-owned parallelism
  as the remaining non-kernel 2x path. No endpoint was changed and no speed
  result was promoted.

2026-06-12 notes update:

- Added prologue-inclusive MoE gate plumbing to
  `scripts/bench-qwen36-int8-moe-kernels.py` and documented it in
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. Each benchmark row now emits
  `prologue_inclusive_gate`, and each run emits
  `prologue_inclusive_gate_summary`. The gate only counts full layerlet
  timings that include route/remap, quant, GEMM1, activation, quant2, GEMM2,
  and gather; isolated GEMM/prologue timings remain diagnostics. Defaults:
  `--target-layerlet-us 160`, `--exactness-threshold 0`, and
  `--min-speedup-vs-xpu 1.0`. Static validation passed
  (`py_compile`, `--help`, `git diff --check`) and a synthetic no-device helper
  check selected an exact `150 us` full-layerlet candidate correctly. No real
  XPU microbench was run because the accepted endpoint is still live; the note
  includes the deferred isolated benchmark command.

2026-06-12 notes update:

- Added a "Bigger Bolder Queue Refresh 20260612da" section to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. This records the next
  requested things-to-try after the accepted-lane manifest: graph-path tensor
  capture, prologue-inclusive MoE timing, real-route grouped-GEMM autotune,
  quality gate v2, and manifest-required candidate promotion. It also keeps
  larger no-quality-loss bets in view: persistent c1 W8A8 MoE island,
  tile-native Quark W8A8 repacking, hot-expert memory packs, hybrid TP/EP or
  asymmetric latency lanes, whole-token Level Zero command-list supernodes,
  target-owned branch farming, route-class kernel generation, a single-user
  direct runner, rank/card topology bakeoff, and a maintainer challenge packet.
  Fresh public signals were folded in: Localmaxxing still has the exact B70/vLLM
  row at `99.428 tok/s` and same-family row at `99.770 tok/s`; Intel's
  grouped-GEMM issue points at real skewed MoE decode routes; a new XPU timing
  issue warns to include prologue/gather work; and vLLM's Arc Pro B-Series
  writeup reinforces persistent-loop MoE and dynamic compute-group balancing.

2026-06-12 notes update:

- Added `scripts/qwen36-accepted-lane-manifest.py` and a clean accepted-lane
  manifest for future speed candidates:
  `data/qwen36-quark-int8-tp4-accepted-lane-manifest-20260612cz.{json,md}`.
  The manifest pins the live endpoint health, clean cache root digest
  (`4221` files, `1.184728587 GB`,
  `754a30c22b94952565827ce6e0431c6589da23c3e540cebb3e15909313bef54e`),
  runtime extension SHA256s/symbols, launcher diagnostic-env scrub, source repo
  heads/dirty counts, p512/o512/c1 speed (`99.188 tok/s` corrected,
  `10.063 ms/token`), quality-smoke pass, and old-token provenance status. Its
  gate status is `accepted_quality_baseline_with_stale_token_sentinel`: the
  current accepted lane is healthy and quality-smoke clean, but strict
  old-cache token sentinels are not a valid standalone promotion gate for fresh
  AOT caches. Next speed candidates must beat this manifest and include the
  same cache/binary/quality evidence plus graph-path tensor parity for kernel
  changes.

2026-06-12 notes update:

- Added a route-fixture offset gate and bigger-bets refresh to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`, plus
  `scripts/qwen36-offset-route-gate-summary.py`. The no-server eager replay
  across first-decode route rows was tensor-exact (`max_abs_diff=0.0`), but the
  env-on offset integration path regressed mean `xpu_fused_moe` latency from
  `347.086 us` to `409.229 us` (`+17.904%`) and the prior endpoint A/B remains
  rejected. The accepted launcher now hard-unsets rejected diagnostic MoE env
  vars. The first cache-reuse restore after routeparity failed, so the
  accepted lane was relaunched from a clean isolated cache root. That clean
  accepted restore on `18080` passed the no-thinking
  quality smoke and measured `99.188 tok/s` corrected p512/o512/c1 decode,
  `97.893 tok/s` e2e, `10.063 ms/token` vLLM decode, and `78.4 ms` client
  TTFT. The old exact-token provenance baseline did not pass on the fresh clean
  cache (`4752 -> 6126`, `198 -> 271` while `11436` still matched), so the
  lesson is sharper: endpoint promotion now needs graph-path tensor parity and
  a cache-versioned provenance/quality gate, not eager replay alone. New
  outside leads and things-to-try were added: persistent c1 W8A8 MoE island,
  real-route grouped-GEMM autotune, AOT cache manifests, latency-lane split,
  hot-expert memory packs, whole-token Level Zero command lists, target-owned
  branch farming, and an upstream Intel/vLLM challenge packet. New artifacts
  include `data/qwen36-quark-int8-firstdecode-multilayer-offset-gate-summary-20260612cy.json`,
  `data/qwen36-quark-int8-tp4-accepted-quality-after-routeparity-clean-nothink-smoke-20260612cy.json`,
  `data/qwen36-quark-int8-tp4-accepted-clean-routeparity-p512o512-metrics-20260612cy.json`,
  and `data/localmaxxing-qwen-b70-vllm-leaderboard-20260612cy.json`.

2026-06-12 notes update:

- Added an offset endpoint rejection record to
  `notes/2026-06-12-qwen36-next-bigger-bets.md` plus a reproducible overlay
  launcher, `scripts/launch-qwen36-quark-int8-w8a8-offset.sh`. The narrow
  A/B used the stable offset-capable extension from
  `/home/steve/src/vllm-xpu-kernels/build/lib.linux-x86_64-cpython-312`, an
  isolated offset cache root, and `VLLM_XPU_W8A8_USE_OFFSETS=1`. It is not
  promotable: provenance failed exact sentinels (`4752 -> 6126` and
  `198 -> 271`) and p512/o512/c1 speed regressed from `99.309 tok/s`
  corrected decode to `96.165 tok/s`. Accepted TP4 was restored afterward on
  `18080`, passed provenance sentinels `4752`, `11436`, `198`, and passed the
  no-thinking quality smoke. The public Localmaxxing exact-model B70 row is
  already approved at `99.428 tok/s`; no rejected offset result was posted.
  New artifacts:
  `data/qwen36-quark-int8-tp4-accepted-pre-offset-p512o512-metrics-20260612cx.json`,
  `data/qwen36-quark-int8-tp4-w8a8-offset-provenance-20260612cx.json`,
  `data/qwen36-quark-int8-tp4-w8a8-offset-p512o512-metrics-20260612cx.json`,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-w8a8-offset-20260612cx.json`,
  `data/qwen36-quark-int8-tp4-accepted-quality-after-w8a8-offset-nothink-smoke-20260612cx.json`,
  and the two matching endpoint logs. Next lead: route-realistic, no-server
  tensor comparison and a dedicated c1/topk-8 W8A8 MoE fast lane, not another
  offset endpoint run.

2026-06-12 notes update:

- Added `scripts/qwen36-w8a8-offset-abi-smoke.py`, the generated
  `data/qwen36-w8a8-offset-abi-smoke-20260612cw.{json,md}` report, and a
  "W8A8 Offset ABI Smoke And Bigger Bets 20260612cw" section to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. The accepted endpoint on
  `18080` was not stopped or changed. The installed extension executes only
  the base W8A8 INT8 grouped GEMM; the stable
  `build/lib.linux-x86_64-cpython-312` candidate executes base plus offset
  W8A8 with matching tiny-smoke checksum `1452.126831`; the archived
  pre-sidecar candidate executes active-offset too; the sidecar-probe build
  aborts with signal `6` and is not safe to promote. Local source now has an
  env-gated offset path (`VLLM_XPU_W8A8_USE_OFFSETS=1`) in
  `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/fused_moe_interface.py`;
  the patch note is
  `patches/vllm-xpu-kernels-qwen36-w8a8-offset-path-20260612cw.md`. Next gate:
  a narrow offset-only endpoint A/B using the stable offset-capable extension,
  isolated cache, provenance sentinels, p512/o512 c1 speed, and quality
  canaries, followed by immediate restore if neutral/slower.

2026-06-12 notes update:

- Added `scripts/qwen36-quark-int8-xpu-kernel-path-audit.py` plus a "Kernel
  Path Audit And Bigger Bets 20260612cv" section to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. This was a static/runtime
  audit only; the accepted endpoint on `18080` was inspected but not changed.
  The current Quark W8A8 INT8 path does select the XPU INT8 MoE backend, but
  runtime execution remains a multi-stage wrapper: remap, INT8 quant, W8A8
  grouped GEMM 1, activation, INT8 quant, W8A8 grouped GEMM 2, and gather. The
  installed `_xpu_C.abi3.so` exports the base W8A8 grouped GEMM and INT8 quant
  ops, but not the route-aware offset or active-offset W8A8 symbols that exist
  in the dirty source tree. Decision: the next meaningful no-quality-loss gate
  is to rebuild or isolate `vllm-xpu-kernels` with those symbols exported, run
  ABI smoke tests, replay the first-decode route fixture with exact tensor
  comparison, and only then launch a diagnostic endpoint. New bigger bets added:
  persistent topk-8 c1 MoE island, route-class kernel generation, long-lived
  per-GPU MoE workers, hot expert duplication, TP+EP/TP2+replica topology
  lanes, a no-server c1 runner, whole-token command-list capture, target-owned
  branch farming after state transactions, and an upstream maintainer challenge
  packet. New artifacts:
  `data/qwen36-quark-int8-xpu-kernel-path-audit-20260612cv.json` and
  `data/qwen36-quark-int8-xpu-kernel-path-audit-20260612cv.md`.

2026-06-12 notes update:

- Added an "External Leads And Bigger Bets Refresh 20260612cu" section to
  `notes/2026-06-12-qwen36-next-bigger-bets.md` and saved fresh public
  Localmaxxing snapshots. The exact-model B70/vLLM query still has one row at
  `99.428 tok/s`; the broader B70/Qwen/vLLM snapshot still has the same
  current run family at `99.770 tok/s`; and the B70/Qwen/MoE/fp8 query returned
  no comparable rows. The outside scan reinforces the current technical lead:
  Intel's current XPU release notes call out persistent MoE GEMM plus fused
  activation and a `2.6x` Qwen3-30B-A3B gain, while `vllm-xpu-kernels` now
  advertises MoE top-k/align/gather/remap, FP8/MxFP4 GEMM, and grouped GEMM.
  New queue items: isolate a latest-`vllm-xpu-kernels` route-fixture bakeoff,
  prove whether Quark W8A8 dispatch hits the persistent MoE path, use
  `intel/vllm:0.10.2-xpu` as a kernel lab only, implement a c1 topk-8 W8A8 MoE
  layerlet, route-class generated kernels, hot/cold expert residency maps,
  no-collective c1 islands, Level Zero command-list supernodes,
  target-owned branch farming after state transactions, a platform
  power/thermal/PCIe audit, and an upstream challenge packet. New artifacts:
  `data/localmaxxing-qwen36-quark-w8a8-int8-exact-refresh-20260612cu.json`,
  `data/localmaxxing-qwen-b70-vllm-leaderboard-20260612cu.json`, and
  `data/localmaxxing-qwen-moe-fp8-leaderboard-20260612cu.json`.

2026-06-12 notes update:

- Added `scripts/qwen36-firstdecode-route-fixture-plan.py` and a
  "First-Decode Route Fixture Planner 20260612ct" section to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. The CPU-only adapter converts
  the compact first-decode fixture into normal route JSONL rows compatible with
  the existing route simulator and XPU MoE microbench. It emitted `120` records
  from `3` first-decode events across all `40` MoE layers, covering `215`
  globally active experts, `960` total assignments, and `80` unique topk
  tuples. Mean per-layer union active experts across the three fixtures is
  `13.45`, with mean pairwise topk Jaccard `0.471`. The TP-local expert
  weight/scale footprint for one MoE layer shard is about `194.250 MiB`, while
  single-token scratch is only `0.085968 MiB`, so memory is available for a
  persistent topk-8 layerlet. The route placement proxy says naive EP is not
  the c1 lead path: contiguous EP4 mean/p95 pressure `1.771/2.500`,
  round-robin EP4 `1.892/2.500`. Route-derived greedy/hot-replicated placement
  can balance this tiny fixture, but that is a route policy/hot-pack direction,
  not a launch flag. Next deferred XPU gate: layer-9 rows=1 microbench from the
  generated JSONL when the serving endpoint is stopped or an isolated XPU is
  available. New artifacts:
  `data/qwen36-quark-int8-tp4-firstdecode-route-fixture-plan-20260612ct.json`,
  `data/qwen36-quark-int8-tp4-firstdecode-route-fixture-plan-20260612ct.md`,
  `data/qwen36-quark-int8-tp4-firstdecode-route-fixture-routes-20260612ct.jsonl`,
  `data/qwen36-quark-int8-tp4-firstdecode-route-parallelism-sim-20260612ct.json`,
  and
  `data/qwen36-quark-int8-tp4-firstdecode-route-parallelism-sim-20260612ct.md`.

2026-06-12 notes update:

- Added a "Route-Fixture Bigger/Bolder Refresh 20260612cs" section to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. This turns the first-decode
  route fixture into a concrete next queue: route-fixture microbench before
  endpoint work, accepted-replay route side channel inside the XPU MoE custom
  op or graph output path, single-token/topk-8 persistent MoE lane for Qwen's
  `hidden_size=2048`, `moe_intermediate_size=512`, `num_hidden_layers=40`,
  `num_experts=256`, `num_experts_per_tok=8`, oneDNN grouped-matmul hint gate,
  align/gather overhead split, TP/EP placement simulator on real routes,
  no-server c1 ceiling with route ledger, and target-state transactions before
  using the model's MTP layer as a proposer. Bigger bets now tracked include a
  B70 W8A8 MoE island in `vllm-xpu-kernels`, memory-for-latency expert packs,
  whole-token Level Zero replay, target-verified branch farming, separate
  latency/aggregate lanes, route-class kernel generation, and a maintainer
  challenge packet with executable fixtures. Fresh Localmaxxing public
  snapshots still show the exact current Quark W8A8 row at `99.428 tok/s`; the
  B70/Qwen/vLLM snapshot has a same-family `Qwen/Qwen3.6-35B-A3B` row at
  `99.770 tok/s`. New artifacts:
  `data/localmaxxing-qwen36-quark-w8a8-int8-exact-refresh-20260612cs.json`,
  `data/localmaxxing-qwen-b70-vllm-leaderboard-20260612cs.json`, and
  `data/localmaxxing-b70-moe-leaderboard-20260612cs.json`.

2026-06-12 notes update:

- Added a "Route Fixture Diagnostic 20260612cr" section to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. The compiled route-counter
  run `20260612cp2` measured `96.828 tok/s` corrected p512/o128 and confirmed
  Python route hooks are registered for all 40 MoE layers and called during
  prefill, but decode replay bypasses those callbacks (`captures=0`,
  `overlay_candidates=0` for one-token decode). The eager route-fixture run
  `20260612cq2` captured `5440` route summaries over `76` boundary rows but
  was intentionally slow (`10.718 tok/s`) and is not a speed candidate. The
  main route-shape lesson is that c1 decode is a single-token/topk-8 W8A8 MoE
  problem, not primarily a hot-batched expert pileup. New direction: graph-safe
  route hashes or custom-op side channel for accepted replay, then a
  single-token/topk-8 MoE microbench with resident weights/scratch and exact
  tensor compare. Accepted TP4 was restored on `18080` afterward and passed
  provenance sentinels `4752`, `11436`, `198` plus the no-thinking quality
  smoke. A compact route fixture was extracted with three first-decode
  examples, all 40 MoE layers, and each layer's selected topk expert IDs for
  the next microbench. New artifacts:
  `data/qwen36-quark-int8-tp4-routefixture-diagnostic-summary-20260612cr.json`,
  `data/qwen36-quark-int8-tp4-routeoverlay-eager-summary-20260612cq2.json`,
  `data/qwen36-quark-int8-tp4-routefixture-firstdecode-routes-20260612cr.json`,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-routefixture-20260612cr.json`,
  and
  `data/qwen36-quark-int8-tp4-accepted-quality-after-routefixture-nothink-smoke-20260612cr.json`.

2026-06-12 notes update:

- Added a "Route Overlay Diagnostic And Bolder Queue Refresh 20260612co"
  section to `notes/2026-06-12-qwen36-next-bigger-bets.md`. This is a
  diagnostic/backlog update, not a promoted speed result. The route-overlay
  attempts exposed a production-cache hygiene issue: two launches that reused
  the production AOT cache failed with cross-device tensors after the previous
  reversed-rank diagnostic, while the same launch with an isolated fresh cache
  started cleanly. The fresh-cache diagnostic measured `94.938 tok/s`
  corrected p512/o128, but route overlay payloads had `captures=0`, so the
  current Python route hook does not observe the compiled replay path. New
  tracked items: isolate diagnostic cache roots, add an AOT cache provenance
  manifest, move route capture into the compiled MoE runner/custom-op path,
  replay real route fixtures outside serving, split model-forward timing by
  layer family with route context, re-test TP2 latency with cache isolation,
  and keep broader no-quality-loss bets around route-aware expert caching,
  `vllm-xpu-kernels` custom MoE ops, oneDNN grouped-memory MoE sidecar,
  locality-aware schedule transfer, TP2 latency cells, static c1 micro-engine,
  and a maintainer-grade route/timeline bundle. Accepted TP4 was restored on
  `18080` afterward with the standard launcher; cache quarantine was not
  needed for restore. Provenance passed sentinels `4752`, `11436`, and `198`,
  and the no-thinking quality smoke matched the previous accepted baseline.
  New artifacts:
  `patches/vllm-qwen36-route-overlay-diagnostic-20260612co.md`,
  `data/qwen36-quark-int8-tp4-routeoverlay-diagnostic-summary-20260612co.json`,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-routeoverlay-20260612co.json`,
  and
  `data/qwen36-quark-int8-tp4-accepted-quality-after-routeoverlay-nothink-smoke-20260612co.json`.

2026-06-12 notes update:

- Added a "Bigger/Bolder Ideas Refresh 20260612cm" section to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. This is backlog, not a
  promoted speed result: the public Localmaxxing exact-model/B70/vLLM query
  still returns only the existing `99.428 tok/s` quality-gated row. The refresh
  folds in current Intel/XPU signals: Intel's latest XPU container notes warn
  that some workloads can regress during the migration to dedicated XPU
  kernels; oneDNN now exposes experimental grouped memory/grouped matmul and a
  max-group-size hint for MoE; vLLM XPU work is moving into
  `vllm-xpu-kernels`; and a public 4x B60 report shows Intel-optimized vLLM
  builds can materially improve TPOT on related workloads. New things to try:
  route-signature overlay on all-rank timing, layer-family forward timing with
  route context, oneDNN grouped-matmul hint experiments, a
  `vllm-xpu-kernels` MoE plugin branch, a clean Intel stack matrix measured by
  route fixtures first, VTune/oneDNN/Level Zero proof packets, a static c1
  micro-engine, hybrid TP/EP MoE islands, VRAM-for-latency expert replication,
  outlier-aware exact fallback lanes, TP2 latency plus utility-card topology,
  target-model branch farming, an upstream maintainer challenge bundle, and a
  broader quality/stability gate before any bolder branch is accepted.

2026-06-12 notes update:

- Added a "Rank/Card Rotation Result" addendum to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. The env-only reverse attempt
  with `ONEAPI_DEVICE_SELECTOR=level_zero:3,2,1,0` and `ZE_AFFINITY_MASK=3,2,1,0`
  did not rotate worker placement: TP0/TP1/TP2/TP3 still owned physical cards
  0/1/2/3. A diagnostic-only vLLM hook,
  `VLLM_XPU_LOCAL_RANK_DEVICE_MAP=3,2,1,0`, successfully reversed ownership:
  TP0 -> card 3, TP1 -> card 2, TP2 -> card 1, TP3 -> card 0. The true
  reversed diagnostic stayed near baseline at `96.578 tok/s` corrected
  p512/o128 and `10.272 ms/token` vLLM decode. The important attribution:
  rank 0 stayed fastest after moving from physical card 0 to physical card 3
  (`4.139/4.263 ms` mean/median forward-end-after-start), while ranks 2/3
  stayed in the slower tail (`4.485/4.423 ms`, `4.472/4.412 ms`). Decision:
  stop treating physical-card/topology as the lead hypothesis for the
  `~4-5 ms/token` forward wait; next work should overlay route signatures by
  rank, split model forward by layer family, replay rank-specific route
  fixtures, and keep pushing the exact W8A8 persistent/route-class MoE path.
  Accepted TP4 was restored on `18080` with no diagnostic env vars and passed
  provenance sentinels `4752`, `11436`, `198` plus the no-thinking quality
  smoke. New artifacts:
  `patches/vllm-qwen36-rankmap-forward-boundary-20260612cl.diff`,
  `data/qwen36-quark-int8-tp4-allrank-forwardboundary-rankmap-rev-summary-20260612cl.json`,
  `data/qwen36-quark-int8-tp4-allrank-forwardboundary-revmap-summary-20260612ck.json`,
  `data/qwen36-quark-int8-tp4-rankmap-rotation-comparison-20260612cl.json`,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-rankmap-rotation-20260612cl.json`,
  and
  `data/qwen36-quark-int8-tp4-accepted-quality-after-rankmap-rotation-nothink-smoke-20260612cl.json`.

2026-06-12 notes update:

- Added an "All-Rank Forward Boundary And Larger Bets" addendum to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. The all-rank diagnostic
  backend stayed close enough for attribution at `95.529 tok/s` corrected
  p512/o128 and showed the wait is model-forward-side on every TP rank:
  pure decode after the first five events had all-rank
  `forward_end_after_start_sync_ms` mean `4.569 ms` / median `4.653 ms`, while
  `forward_start` sync was near-zero (`0.00159 ms` mean). In the unrotated
  mapping, ranks/cards 2 and 3 were slower than ranks/cards 0 and 1
  (`4.769/4.683 ms` and `4.820/4.739 ms` mean/median versus rank 0
  `4.214/4.318 ms`). Decision: run rank-to-card rotation next to separate
  physical-card/topology skew from TP-shard/route skew, then split model
  forward by layer family. The note also adds bigger no-quality-loss bets:
  route-ledger overlays, Intel clean-stack bakeoff, persistent MoE island,
  dynamic route-class compute grouping, hot-expert re-layout/replication,
  hybrid TP/EP decode, whole-token resident replay, same-model branch
  verification, topology/driver A-B lab, and an external challenge bundle.
  The accepted launcher now preserves production defaults while allowing
  `ONEAPI_DEVICE_SELECTOR` and `ZE_AFFINITY_MASK` overrides for reproducible
  rank/card rotation. Accepted TP4 was restored on `18080` with no diagnostic
  timing env vars and passed provenance sentinels `4752`, `11436`, `198` plus
  the no-thinking quality smoke. New artifacts:
  `patches/vllm-qwen36-allrank-forward-boundary-20260612cj.diff`,
  `data/qwen36-quark-int8-tp4-allrank-forwardboundary-summary-20260612cj.json`,
  `data/qwen36-quark-int8-tp4-allrank-forwardboundary-p512o128-metrics-20260612cj.json`,
  `data/qwen36-quark-int8-tp4-allrank-forwardboundary-xpusmi-ps-20260612cj.json`,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-allrank-forwardboundary-20260612cj.json`,
  and
  `data/qwen36-quark-int8-tp4-accepted-quality-after-allrank-forwardboundary-nothink-smoke-20260612cj.json`.

2026-06-12 notes update:

- Added a "Minimal Forward Boundary Split" to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. This replaces the failed
  heavy pre-sampler probe with low-overhead boundary events and identifies the
  remaining hidden wait as model-forward-side. Diagnostic `20260612ch`
  stayed near baseline at `97.707 tok/s` corrected p512/o128 and showed
  `forward_end` carrying the wait: pure decode after first five decode events
  had `forward_end` sync mean `3.470 ms` / median `3.778 ms`, while
  `compute_logits_end` and `sample_start` were near-zero. Diagnostic
  `20260612ci` split `forward_start` vs `forward_end` and stayed near baseline
  at `99.123 tok/s`; `forward_start` sync mean was only `0.0020 ms`, while
  `forward_end` was `3.674 ms` mean / `3.775 ms` median. Decision: the next
  optimization target is inside model forward or its forward-stream
  dependencies: MoE decode kernels, attention/GDN pieces, TP collectives inside
  forward, XPU graph replay, rank skew, route skew, or stream ordering before
  `forward_end`. Accepted TP4 was restored on `18080` with no diagnostic env
  flags and passed provenance sentinels `4752`, `11436`, `198` plus the
  no-thinking quality smoke. The launch script now has default-preserving env
  overrides for diagnostic memory/context settings. New artifacts:
  `patches/vllm-qwen36-presampler-boundary-minimal-20260612ci.diff`,
  `data/qwen36-quark-int8-tp4-presampler-minboundary-nested-summary-20260612ch.json`,
  `data/qwen36-quark-int8-tp4-presampler-forwardboundary-nested-summary-20260612ci.json`,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-forwardboundary-20260612ci.json`,
  and
  `data/qwen36-quark-int8-tp4-accepted-quality-after-forwardboundary-nothink-smoke-20260612ci.json`.

2026-06-12 notes update:

- Added a "Pre-Sampler Probe Attempt And Bigger Ideas Addendum" to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. A heavier pre-sampler
  stage-split patch was captured, but the isolated diagnostic backend failed on
  the first p512/o128 request with `UR_RESULT_ERROR_DEVICE_LOST` during
  first-request block-table `copy_to_gpu`, followed by
  `UR_RESULT_ERROR_OUT_OF_DEVICE_MEMORY` during cleanup. This is a stability
  finding rather than timing attribution: the all-events probe is too intrusive
  for the current production-like 32K/0.95-memory TP4 launch. Accepted TP4 was
  restored on `18080` with no diagnostic env flags and passed provenance
  sentinels `4752`, `11436`, `198` plus the no-thinking quality smoke. The
  backlog now adds binary-search pre-sampler timing, diagnostic-only memory
  headroom runs, direct c1 in-process runner, all-rank skew timing, exact
  sharded greedy lm-head, route-fixture kernel bakeoff, clean-stack branch
  bakeoff, persistent decode service, rank-specialized expert placement,
  TP/EP hybrid, fused final-token superkernel, route-class kernel policy
  compiler, target-owned multi-token transactions, runtime/driver matrix, and
  an external B70 challenge packet. New artifacts:
  `patches/vllm-qwen36-presampler-stagesplit-20260612cg.diff`,
  `data/qwen36-quark-int8-tp4-presampler-stagesplit-failure-20260612cg.json`,
  `data/qwen36-quark-int8-tp4-presampler-stagesplit-20260612cg.log`,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-presampler-stagesplit-20260612cg.json`,
  `data/qwen36-quark-int8-tp4-accepted-quality-after-presampler-stagesplit-nothink-smoke-20260612cg.json`,
  `data/localmaxxing-b70-qwen-leaderboard-20260612cg.json`, and
  `data/localmaxxing-qwen36-quark-int8-benchmarks-20260612cg.json`.

2026-06-12 notes update:

- Added a "Sampler Stage-Split And Bolder Queue Refresh" to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. The diagnostic p512/o128 run
  was timing-only and slow (`67.341 tok/s` corrected), but it answered the
  current question: sampler/output is not the multi-ms bottleneck. The host
  sync wait averaged `5.934 ms`, with `5.811 ms` already present at sampler
  entry; sampler device work from entry to output-ready was only `0.063 ms`,
  and greedy argmax was only `0.039 ms`. Decision: stop chasing sampler,
  `.tolist()`, or tiny token-copy changes for the `2x` target. The next probe
  is pre-sampler: model tail, final hidden selection, logits projection or
  materialization, TP vocab collectives, graph/queue ordering, and rank skew.
  Accepted TP4 was restored afterward and passed provenance rerun sentinels
  `4752`, `11436`, `198` plus the no-thinking quality smoke. New artifacts:
  `patches/vllm-qwen36-sampler-stagesplit-20260612cf.diff`,
  `data/qwen36-quark-int8-tp4-sampler-stagesplit-20260612ce.log`,
  `data/qwen36-quark-int8-tp4-sampler-stagesplit-p512o128-metrics-20260612ce.json`,
  `data/qwen36-quark-int8-tp4-sampler-stagesplit-nested-summary-20260612ce.json`,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-sampler-stagesplit-rerun-20260612cf.json`,
  `data/qwen36-quark-int8-tp4-accepted-quality-after-sampler-stagesplit-nothink-smoke-rerun-20260612cf.json`,
  `data/localmaxxing-qwen36-quark-w8a8-int8-exact-refresh-20260612cf.json`,
  `data/localmaxxing-qwen-moe-b70-leaderboard-refresh-20260612cf.json`,
  and `data/localmaxxing-vllm-b70-leaderboard-refresh-20260612cf.json`.

- Added a "Larger Bet Addendum 20260612cd" to
  `notes/2026-06-12-qwen36-next-bigger-bets.md` after a fresh Localmaxxing and
  Intel grouped-GEMM/XPU scan. The public exact-model B70/vLLM row remains
  `99.428358 tok/s`, so this is backlog, not a win. New bigger bets now tracked:
  inside-`_sample` timing, exact vocab-sharded greedy argmax, final-logits
  fingerprint gates, provider bakeoff on real Qwen route windows, XPU-friendly
  W8A8 expert retile/repack cache, all-rank route-skew timelines, static c1
  runner ceiling, verifier-owned speculation only after state parity,
  whole-token Level Zero replay, and an upstream B70 challenge bundle. New
  public snapshot artifacts:
  `data/localmaxxing-qwen36-quark-w8a8-int8-exact-20260612.json` and
  `data/localmaxxing-qwen36-30b-class-leaderboard-20260612.json`.

- Added async device timeline and staged sync attribution for the output-event
  wait. This was diagnostic-only and slowed decode to `~76.6-77.4 tok/s`, so
  none of these speed numbers are candidates. The attribution is useful:
  `device_default_before_copy_to_ready_ms` was only about `0.0077 ms`, but the
  host still waited multi-ms. The sync split showed `default_ready_sync_ms`
  at `5.933 ms` mean and `copy_after_default_sync_ms` at `0.021 ms`, proving
  the D2H copy is not the wait. The stage split then showed the wait is already
  present at sampler end: `stage_sample_end_sync_ms` averaged `5.007 ms`, while
  state update (`0.026 ms`), bookkeeping (`0.0088 ms`), pre-async-wrap
  (`0.0033 ms`), default marker (`0.0025 ms`), and copy-after-default
  (`0.0107 ms`) were all tiny. Decision: stop output-materialization work for
  the `2x` target. The remaining `~5 ms` target is model tail, logits, sampler,
  graph/queue ordering, TP collectives, or rank imbalance. Accepted TP4 was
  restored afterward and passed exact provenance sentinels plus the short
  no-thinking quality smoke. New artifacts:
  `patches/vllm-qwen36-async-device-timeline-20260612cc.diff`,
  `data/qwen36-quark-int8-tp4-async-device-timeline-20260612ca.log`,
  `data/qwen36-quark-int8-tp4-async-device-timeline-p512o384-metrics-20260612ca.json`,
  `data/qwen36-quark-int8-tp4-async-device-timeline-summary-20260612ca.json`,
  `data/qwen36-quark-int8-tp4-async-device-syncsplit-20260612cb.log`,
  `data/qwen36-quark-int8-tp4-async-device-syncsplit-p512o256-metrics-20260612cb.json`,
  `data/qwen36-quark-int8-tp4-async-device-syncsplit-summary-20260612cb.json`,
  `data/qwen36-quark-int8-tp4-async-device-stagesplit-20260612cc.log`,
  `data/qwen36-quark-int8-tp4-async-device-stagesplit-p512o192-metrics-20260612cc.json`,
  `data/qwen36-quark-int8-tp4-async-device-stagesplit-summary-20260612cc.json`,
  `data/qwen36-quark-int8-tp4-async-device-stagesplit-summary-20260612cc.md`,
  `data/qwen36-quark-int8-tp4-accepted-restored-after-async-device-stagesplit-20260612cc.log`,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-async-device-stagesplit-20260612cc.json`,
  and
  `data/qwen36-quark-int8-tp4-accepted-quality-after-async-device-stagesplit-nothink-smoke-20260612cc.json`.

- Added and ran worker/async output timeline correlation for the current
  accepted TP4 backend. The p512/o384/c1 timing sanity stayed at baseline:
  `100.009 tok/s` corrected, `9.975 ms` vLLM decode/token, and `10.001 ms`
  TPOT. The split rules out Python result packing and worker response queueing
  as the hidden multi-ms cost: rank-0 worker response enqueue averaged
  `4.325 ms`, `AsyncModelRunnerOutput.get_output()` averaged `4.241 ms`,
  response-MQ enqueue was only `0.081 ms`, and result tuple packing was
  `0.00047 ms`. The async object reached `get_output()` only `0.168 ms` after
  copy submission ended, but `async_copy_ready_event.synchronize()` still
  averaged `4.044 ms`. Combined with the tiny D2H copy bench, the next target
  is device event dependency tracing around sampler/logits, copy submission,
  event record, graph/queue ordering, and rank sync. Accepted TP4 was restored
  afterward and passed exact provenance sentinels plus the short no-thinking
  quality smoke. New artifacts:
  `patches/vllm-qwen36-worker-output-timeline-20260612bz.diff`,
  `data/qwen36-quark-int8-tp4-worker-output-timeline-20260612bz.log`,
  `data/qwen36-quark-int8-tp4-worker-output-timeline-p512o384-metrics-20260612bz.json`,
  `data/qwen36-quark-int8-tp4-worker-output-timeline-summary-20260612bz.json`,
  `data/qwen36-quark-int8-tp4-worker-output-timeline-summary-20260612bz.md`,
  `data/qwen36-quark-int8-tp4-accepted-restored-after-worker-output-timeline-20260612bz.log`,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-worker-output-timeline-20260612bz.json`,
  and
  `data/qwen36-quark-int8-tp4-accepted-quality-after-worker-output-timeline-nothink-smoke-20260612bz.json`.

- Added a "Bigger/Bolder Backlog Refresh 20260612bz" section to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. The new items fold in the
  D2H copy isolation result plus fresh public B70/vLLM/XPU signals: worker and
  async-output timeline correlation, device event dependency tracing,
  rank-to-card/route-skew rotation, route-window roofline packets, strict
  Intel clean-stack bakeoff, a c1 scalar-output lane, MoE route-class kernel
  farm, hot-expert physical re-layout/replication, mixed TP/EP sharding,
  persistent token engine, verifier-owned speculative transactions,
  cross-engine kernel donor harness, whole-token Level Zero replay, and a
  maintainer challenge packet. Pruning rule added: stop spending time on tiny
  D2H/list/pinned-buffer token-copy work unless a device timeline contradicts
  the `~0.01 ms` isolation result.

- Added and ran `scripts/bench-xpu-d2h-token-copy.py` to isolate the tiny
  token-id XPU-to-host copy behind the async-output wait. The raw copy is not
  the `~3.8 ms` bottleneck: on `xpu:0`, pinned-host `1x1` nonblocking
  copy+event median was `0.010019 ms` with p99 `0.016331 ms`; `48x1` median
  was `0.011431 ms`; blocking copy+sync was only `0.033-0.037 ms`. A shorter
  `xpu:3` cross-check was similar (`1x1` median `0.010299 ms`, `48x1`
  `0.011722 ms`). Decision: stop chasing `.tolist()`, pinned-buffer reuse, or
  the raw token ferry as a multi-millisecond lever. The live
  `async_copy_ready_event.synchronize()` wait is almost certainly upstream
  queue/dependency exposure from model tail, sampler/logits, graph/event
  ordering, rank sync, or worker-result handoff. New artifacts:
  `scripts/bench-xpu-d2h-token-copy.py`,
  `data/qwen36-xpu-d2h-token-copy-20260612by.json`,
  `data/qwen36-xpu-d2h-token-copy-xpu3-20260612by.json`, and
  `data/qwen36-xpu-d2h-token-copy-summary-20260612by.md`.

- Added a "Bigger/Bolder Refresh 20260612by" section to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. It records the latest idea
  backlog after the async-output and TP2 truth-serum findings: tiny D2H token
  copy isolation, device-timeline attribution for `async_copy_ready_event`,
  official Intel XPU stack bakeoff, EP-lite topology, rank/device rotation
  with route ledgers, a resident oneDNN grouped-MoE execute-and-compare path,
  persistent W8A8 MoE island, hot-expert replication, hybrid TP/EP scheduling,
  a one-token resident c1 lane, whole-token Level Zero replay, target-owned
  speculative branch farming, same-model engine adapter shootout, and a B70
  maintainer challenge packet. Fresh external signals came from Intel's XPU
  container notes, vLLM XPU docs, Localmaxxing exact-model API state, and
  community B70 fused-MoE notes. The promoted baseline remains unchanged at
  about `100 tok/s`; these are next experiments and architecture bets, not
  wins yet.

- Ran the TP2 latency truth-serum for the current Qwen3.6 Quark W8A8 INT8
  checkpoint. TP2 used GPUs `0,1`, 32K context, Quark quantization, and the
  same p512/o256 c1 streaming measurement shape. It is not a win: TP2 repeated
  at `91.351 tok/s` corrected mean (`10.906 ms/token` vLLM decode,
  `10.949 ms` TPOT), while the restored TP4 lane measured `100.475 tok/s`
  corrected (`9.916 ms/token`, `9.955 ms` TPOT). TP2 also failed exact accepted
  provenance despite passing the short no-thinking quality smoke: sentinel
  drifts were `4752 -> 6126`, `11436 -> 19087`, and `198 -> 321`. TP2 loaded
  at `16.88 GiB/rank`, with `1,138,206` KV tokens and `34.74x` 32K
  concurrency; TP4 restored at `8.58 GiB/rank`, `2,052,915` KV tokens, and
  `62.65x` 32K concurrency. Decision: plain TP2 is ruled out for the
  no-quality-loss latency lane; keep work on TP4 internals, hybrid TP/EP, or
  verifier-owned transaction paths. TP4 accepted was restored afterward and
  passed provenance/quality on rerun after one transient failed first gate.
  New artifacts:
  `data/qwen36-quark-int8-tp2-latency-truth-20260612bx.log`,
  `data/qwen36-quark-int8-tp2-latency-truth-p512o256-metrics-20260612bx.json`,
  `data/qwen36-quark-int8-tp2-latency-truth-p512o256-r3-metrics-20260612bx.json`,
  `data/qwen36-quark-int8-tp2-latency-truth-provenance-20260612bx.json`,
  `data/qwen36-quark-int8-tp2-latency-truth-quality-nothink-smoke-20260612bx.json`,
  `data/qwen36-quark-int8-tp2-latency-truth-summary-20260612bx.md`,
  `data/qwen36-quark-int8-tp4-accepted-restored-after-tp2-truth-20260612bx.log`,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-tp2-truth-20260612bx.json`,
  `data/qwen36-quark-int8-tp4-accepted-quality-after-tp2-truth-nothink-smoke-20260612bx.json`,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-tp2-truth-rerun-20260612bx.json`,
  `data/qwen36-quark-int8-tp4-accepted-quality-after-tp2-truth-nothink-smoke-rerun-20260612bx.json`,
  and
  `data/qwen36-quark-int8-tp4-restored-after-tp2-p512o256-metrics-20260612bx.json`.

- Added async-output sub-timing after the RPC future-result split. The result
  changes the next target: rank-0 response materialization is almost entirely
  `async_copy_ready_event.synchronize()`, not token-list conversion. In the
  timing-only run, `get_output()` averaged `3.815 ms`, with `3.798 ms` spent
  synchronizing and only `0.010 ms` in token-list conversion. The reuse-buffer
  plus fast-scalar path fired correctly but stayed flat (`3.873 ms` total,
  `3.840 ms` sync), so `.tolist()`/CPU-buffer churn is not the lever. The
  copied tensor is only `torch.int32` shape `[1,1]` for c1/no-logprobs. Bigger
  ideas added to `notes/2026-06-12-qwen36-next-bigger-bets.md`: device
  timeline for the event wait, TP2 latency truth-serum, direct c1 runner
  ceiling, sampler/copy isolation, one-token resident decode lane, whole-token
  Level Zero command-list replay, persistent MoE device service, hybrid TP/EP,
  hot-expert duplication, target-owned speculative transactions, branch farm,
  maintainer packet, strict same-model engine bakeoff, and a split c1/aggregate
  production architecture. Important gate: the accepted restore after this
  diagnostic produced one failed provenance/quality artifact, but an immediate
  rerun on the same backend passed exact provenance sentinels (`4752`, `11436`,
  `198`) plus the no-thinking quality smoke; keep gates mandatory because the
  transient failure is a useful warning. New artifacts:
  `patches/vllm-qwen36-async-output-timing-20260612bv.diff`,
  `data/qwen36-quark-int8-tp4-async-output-timing-20260612bv.log`,
  `data/qwen36-quark-int8-tp4-async-output-timing-p512o256-metrics-20260612bv.json`,
  `data/qwen36-quark-int8-tp4-async-output-timing-summary-20260612bv.json`,
  `data/qwen36-quark-int8-tp4-async-output-reuse-timing-20260612bw.log`,
  `data/qwen36-quark-int8-tp4-async-output-reuse-timing-p512o256-metrics-20260612bw.json`,
  `data/qwen36-quark-int8-tp4-async-output-reuse-timing-summary-20260612bw.json`,
  `data/qwen36-quark-int8-tp4-accepted-restored-after-async-output-timing-20260612bw.log`,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-async-output-timing-20260612bw.json`,
  `data/qwen36-quark-int8-tp4-accepted-quality-after-async-output-timing-nothink-smoke-20260612bw.json`,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-async-output-timing-rerun-20260612bw.json`,
  `data/qwen36-quark-int8-tp4-accepted-quality-after-async-output-timing-nothink-smoke-rerun-20260612bw.json`,
  and
  `data/qwen36-quark-int8-tp4-async-output-timing-summary-20260612bv.md`.

- Added an RPC future-result split around the vLLM multiprocess executor and
  worker response path. The p512/o256/c1 diagnostic stayed at baseline speed:
  `100.621 tok/s` corrected, `9.902 ms/token` vLLM decode, and
  `9.941 ms/token` TPOT. The key finding is that joined `sample_tokens` worker
  compute is only `0.351 ms` mean, while rank-0 output materialization /
  response enqueue is `3.900 ms` mean and accounts for almost the whole
  `4.297 ms` driver response wait. The fast-output/reuse-buffer A/B did not
  improve this (`100.327 tok/s`, `3.962 ms` output enqueue), so the next target
  is sub-timing and optimizing `AsyncModelRunnerOutput.get_output()`, especially
  event sync / device-to-host token ID copy completion. The accepted backend was
  restored and passed exact provenance sentinels plus the Qwen no-thinking
  quality smoke. Added public-signal refreshes and bigger-bet items to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`, including pinned scalar output
  ferry, device-resident sampler/streamer lane, single-request direct runner,
  TP2 latency lane plus replicas, expert-parallel sparse island, whole-token
  command-list replay, target-owned branch farm, B70 maintainer packet, strict
  same-model engine bakeoff, and a parity/stability scoreboard. New artifacts:
  `patches/vllm-qwen36-engine-rpc-timing-20260612bt.diff`,
  `data/qwen36-quark-int8-tp4-rpc-timing-20260612bt.log`,
  `data/qwen36-quark-int8-tp4-rpc-timing-p512o256-metrics-20260612bt.json`,
  `data/qwen36-quark-int8-tp4-rpc-timing-summary-20260612bt.json`,
  `data/qwen36-quark-int8-tp4-rpc-timing-summary-20260612bt.md`,
  `data/qwen36-quark-int8-tp4-rpc-fastoutput-20260612bu.log`,
  `data/qwen36-quark-int8-tp4-rpc-fastoutput-p512o256-metrics-20260612bu.json`,
  `data/qwen36-quark-int8-tp4-rpc-fastoutput-summary-20260612bu.json`,
  `data/qwen36-quark-int8-tp4-accepted-restored-after-rpc-timing-20260612bu.log`,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-rpc-timing-20260612bu.json`,
  `data/qwen36-quark-int8-tp4-accepted-quality-after-rpc-timing-nothink-smoke-20260612bu.json`,
  `data/localmaxxing-b70-vllm-leaderboard-20260612bt.json`,
  `data/localmaxxing-qwen36-quark-w8a8-int8-exact-refresh-20260612bt.json`,
  and `data/localmaxxing-qwen-b70-leaderboard-20260612bt.json`.

- Added EngineCore and all-rank timing notes for the current accepted Quark
  W8A8 INT8 TP4 path. The diagnostic runs stayed at baseline speed
  (`99.803-99.829 tok/s` corrected decode, `9.985-10.022 ms/token` TPOT).
  EngineCore total time is `~9.94-10.05 ms/token`, with `~9.70-9.84 ms` spent
  waiting on `future_result`; Python scheduler/update/submit regions are each
  tiny. All-rank labels show rank 3 is slowest (`6.058 ms` model-forward mean
  versus rank 1 at `5.580 ms`), but the rank spread is not large enough to
  explain the full engine wait. Interpretation: the next speed work should
  attack hidden model-execution completion, collectives, command queues,
  rank placement, and a no-server c1 ceiling harness, not request streaming or
  scheduler micro-tuning. Restore validation passed accepted provenance and the
  no-thinking Qwen quality smoke. New artifacts:
  `patches/vllm-qwen36-engine-step-timing-20260612bq.diff`,
  `data/qwen36-quark-int8-tp4-engine-step-timing-20260612bq.log`,
  `data/qwen36-quark-int8-tp4-engine-step-timing-p512o256-metrics-20260612bq.json`,
  `data/qwen36-quark-int8-tp4-engine-step-timing-summary-20260612bq.json`,
  `data/qwen36-quark-int8-tp4-engine-step-timing-summary-20260612bq.md`,
  `data/qwen36-quark-int8-tp4-engine-allrank-timing-20260612br.log`,
  `data/qwen36-quark-int8-tp4-engine-allrank-timing-p512o256-metrics-20260612br.json`,
  `data/qwen36-quark-int8-tp4-engine-allrank-timing-summary-20260612br.json`,
  `data/qwen36-quark-int8-tp4-accepted-restored-after-engine-timing-20260612br.log`,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-engine-timing-20260612br.json`,
  `data/qwen36-quark-int8-tp4-accepted-quality-after-engine-timing-nothink-smoke-20260612br.json`,
  and `data/localmaxxing-qwen36-b70-leaderboard-20260612bs.json`.

- Added a fresh "Bolder Opportunity Refresh 20260612bq" section to
  `notes/2026-06-12-qwen36-next-bigger-bets.md` after the boundary timing
  discussion. The refreshed backlog keeps the immediate next items explicit:
  EngineCore wall-time timing, all-rank slow-rank attribution, oneDNN
  execute-and-compare, TP2+replica latency topology, c1 no-server ceiling,
  and verifier-state transactions before more speculation timing. The bigger
  queue now includes mixed TP/EP current-model topology, a rank-local
  persistent MoE island, whole-token Level Zero command-list capture,
  target-owned self-speculation, route-class code generation, a B70 roofline
  maintainer packet, strict high-fidelity engine bakeoff, and split latency/
  aggregate production lanes. Fresh public Localmaxxing artifacts confirm the
  exact/current-model B70/vLLM public row remains `99.428 tok/s`, while the
  broader Qwen/B70/vLLM class is still effectively `~99.770 tok/s`; higher B70
  rows remain different-model, aggregate, lower-precision, or speculative
  design clues. New artifacts:
  `data/localmaxxing-qwen36-quark-w8a8-int8-exact-refresh-20260612bq.json`,
  `data/localmaxxing-qwen-b70-vllm-leaderboard-20260612bq.json`, and
  `data/localmaxxing-b70-overall-leaderboard-20260612bq.json`.

- Ran the boundary-timing maintenance gate on the current accepted Quark W8A8
  INT8 TP4 endpoint, then restored the normal accepted backend. Diagnostic
  throughput stayed at baseline: p512/o256/c1 corrected streaming decode
  `99.796 tok/s`, vLLM decode `9.984 ms/token`, and time-per-output-token
  `10.023 ms/token`. Rank-0 no-sync pure-decode step timing shows
  `gpu_model_runner.forward_total ~= 5.648 ms/step` and
  `gpu_model_runner.model_forward ~= 5.593 ms/step`; postprocess/logits/sample/
  async-output labels are sub-millisecond. The measured endpoint-vs-rank0
  forward gap is therefore about `4.39 ms/token`, but the labels are nested and
  asynchronous, not exclusive wall-clock slices. Interpretation: the next
  timing target is scheduler/engine step wall time, rank-to-rank variance,
  host/device synchronization, and collectives across all ranks, not another
  narrow Python wrapper around model forward. Restore validation passed Qwen3.6
  accepted provenance (`4752`, `11436`, `198` sentinels) and a short
  no-thinking Qwen-specific text quality smoke. New artifacts:
  `data/qwen36-quark-int8-tp4-boundary-timing-20260612bp.log`,
  `data/qwen36-quark-int8-tp4-boundary-timing-p512o256-metrics-20260612bp.json`,
  `data/qwen36-quark-int8-tp4-boundary-timing-summary-20260612bp.json`,
  `data/qwen36-quark-int8-tp4-boundary-timing-summary-20260612bp.md`,
  `data/qwen36-quark-int8-tp4-accepted-restored-after-boundary-timing-20260612bp.log`,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-boundary-timing-20260612bp.json`,
  and
  `data/qwen36-quark-int8-tp4-accepted-quality-after-boundary-timing-nothink-smoke-20260612bp.json`.

- Added a follow-up "concrete next gates and bigger bets" section to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. It records that the latest
  Localmaxxing exact-model public row remains `99.428 tok/s`, while the live
  mode/context sweep ruled out SSE streaming and p512-vs-p4096 context as
  major steady-decode bottlenecks. New tracked items: boundary timing
  maintenance run, no-server c1 ceiling lab, collective/command-submission
  ledger, TP2/replica topology tests, oneDNN sidecar execute-and-compare,
  persistent MoE command ring, real-route autotuner, target-state transaction
  substrate, target-owned branch farming, B70 W8A8 roofline packet, strict
  same-model 8-bit engine shootout, and a parity/stability scoreboard.

- Added a no-output-path-change live mode/context sweep on the accepted
  endpoint and a disabled-by-default boundary timing patch for the next
  maintenance run. Stream p512/o512 was `99.590 tok/s` corrected with
  `10.023 ms/token` decode; non-stream p512/o512 was `9.989 ms/token`, only
  `-0.34%` different, so SSE/output streaming is not the missing `~5 ms/token`.
  Stream p4096/o256 was `9.980 ms/token` versus p512/o256 at
  `9.925 ms/token`, only `+0.55%`, while TTFT rose from `74.2 ms` to
  `375.5 ms`; steady decode is therefore not primarily a p512-vs-p4096 context
  issue. Queue time stayed around `0.008-0.009 ms/request`. Added
  `scripts/qwen36-live-sweep-summary.py`, four raw metric JSONs, summary
  JSON/MD artifacts, `data/qwen36-quark-int8-tp4-live-mode-context-sweep-20260612bo.json`,
  and `patches/vllm-qwen36-boundary-timing-labels-20260612bo.diff`.
  The local vLLM source now has env-gated labels for preprocess, forward,
  postprocess, sample, and async-output wrap; `py_compile` passed, but the live
  endpoint was not restarted for these labels yet.

- Added a bolder post-refresh idea backlog to
  `notes/2026-06-12-qwen36-next-bigger-bets.md` after a fresh public
  Localmaxxing refresh and local checkpoint metadata check. Current public
  evidence still has the exact Quark W8A8 INT8 B70/vLLM row at
  `99.428 tok/s`, with the broader B70/vLLM Qwen3.6 35B-A3B class topping near
  `99.770 tok/s`; rows above `200 tok/s` use other hardware, lower precision,
  or speculative/MTP paths and are research signals only. The local exact
  checkpoint index has no `mtp`/`next` tensors, so native MTP is not an
  immediate flag for this quantized checkpoint. Newly tracked ideas include a
  c1 no-server latency lab, transactional current-model verifier state, EP-lite
  or asymmetric TP topology tests, a persistent XPU MoE command ring,
  oneDNN/Level Zero whole-layer replay, hot-expert replication, a B70 W8A8
  roofline packet, strict same-model engine bakeoffs, route-skew autotuning,
  and context sensitivity as diagnosis rather than promotion. Fresh artifacts:
  `data/localmaxxing-qwen36-quark-w8a8-int8-exact-refresh-20260612bn.json`,
  `data/localmaxxing-qwen-b70-vllm-leaderboard-20260612bn.json`, and
  `data/localmaxxing-qwen36-35b-a3b-leaderboard-20260612bn.json`.

- Added a c1 stage-ledger pass that compares the fresh live endpoint gap budget
  to existing timing-step summaries. The endpoint is `9.980 ms/token` decode,
  while the prior low-overhead/nosync pure-decode proxy reports
  `gpu_model_runner.model_forward ~= 5.467 ms/token`; matching that proxy would
  only reach about `182.9 tok/s`. The synchronized model-only proxy is
  `8.433 ms/token`, showing forced synchronization can hide most of the
  apparent headroom. Conclusion: a no-speculative path to `200 tok/s` needs
  both endpoint/outside overhead near the nosync path and at least another
  `0.467 ms/token` off model-forward, or a target-verified multi-token path.
  New artifacts:
  `scripts/qwen36-c1-stage-ledger.py`,
  `data/qwen36-quark-int8-tp4-nosync-labeltiming-summary-20260612t.json`,
  `data/qwen36-quark-int8-tp4-sync-modelonly-timing-summary-20260612u.json`,
  `data/qwen36-quark-int8-tp4-c1-stage-ledger-20260612bn.json`, and `.md`.

- Added and ran a live c1 gap-budget measurement against the accepted Quark
  W8A8 INT8 TP4 endpoint. Fresh p512/o512/c1 streaming metrics show corrected
  decode median `100.013 tok/s`, vLLM decode histogram `9.980 ms/token`,
  inter-token latency `10.000 ms/token`, and queue time only
  `0.0086 ms/request`. The `200 tok/s` target is therefore a concrete
  `5.000 ms/token` budget requiring `4.980 ms/token` saved, or about `49.9%`
  of current decode latency. The new analyzer makes the implication explicit:
  optimizing a subsystem smaller than half of decode is mathematically
  insufficient by itself; a `60%` decode stage would need about `5.94x`
  speedup, `70%` needs `3.48x`, and `80%` needs `2.66x`. Post-run provenance
  passed both prefix cases plus sentinels `4752`, `11436`, and `198`.
  Artifacts:
  `scripts/qwen36-c1-gap-budget.py`,
  `data/qwen36-quark-int8-tp4-live-c1-p512o512-metrics-20260612bm.json`,
  `data/qwen36-quark-int8-tp4-live-c1-gap-budget-20260612bm.json`,
  `.md`, and
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-c1-gap-budget-20260612bm.json`.

- Added the isolated oneDNN sidecar probe launcher to the tracked reproduction
  path: `scripts/launch-qwen36-quark-int8-sidecar-probe.sh`. It creates a
  temporary overlay package that selects only the rebuilt `_xpu_C.abi3.so`,
  sources oneAPI runtime paths, runs an eager one-rank/one-layer descriptor
  probe on port `18081`, and still returns the current `xpu_fused_moe` output.
  `bash -n` passed and the script is executable (`775`). The live TP4 endpoint
  was not disturbed; current `xpu-smi` memory is still about `32651 MiB` used
  per B70, so the actual isolated backend run is deferred until a maintenance
  window. Tracking artifact:
  `data/qwen36-onednn-sidecar-isolated-launcher-20260612bm.json`.

- Added another "bigger bets" pass to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`, focused on ideas with a path
  to no-quality-loss speed: fusing the oneDNN MoE island with post-ops,
  testing `DNNL_ARG_HINT_MAX_GROUP_SIZE`, token-step device-side waterfall
  profiling, a persistent B70 MoE worker with dynamic work stealing, host BOM
  A/B as a real speed/stability experiment, a c1-only no-server ceiling runner,
  checksum-indexed Quark W8A8 prepacked layout artifacts, a verifier
  transaction substrate for DFlash/MTP/ngram branch farming, route-class
  kernels instead of exact-route caches, and split production/latency lanes with
  identical quality gates.

- Added disabled Python plumbing for the next oneDNN MoE sidecar probe gate in
  the local `vllm-xpu-kernels` tree. The new hook is behind
  `VLLM_XPU_MOE_ONEDNN_SIDECAR_PROBE=1`, requires the rebuilt
  `qwen36_moe_onednn_sidecar_probe` op to exist, skips stream capture, supports
  rank/layer/max-call gates, computes an on-device int32
  `onednn_grouped_offsets` buffer from `rows_per_expert`, and always returns
  the current `xpu_fused_moe` output. Validation passed `py_compile`, venv
  imports with the env disabled and enabled, the oneDNN offset helper
  `[2,0,3,1] -> [0,2,2,5]`, and a temporary oneAPI-backed import that selected
  the out-of-tree rebuilt module and saw `has_probe_op=true`. The normal source
  extension still reports `has_probe_op=false`, so the live endpoint remains
  untouched and inert. New tracking artifacts:
  `patches/vllm-xpu-qwen36-onednn-sidecar-python-probe-20260612bl.diff` and
  `data/qwen36-onednn-sidecar-python-probe-20260612bl.json`. This is not a
  speed claim; the next gate is an isolated backend with one rank/layer probe
  logging descriptor stats while output remains on the accepted path.

- Added a user-review follow-up section to
  `notes/2026-06-12-qwen36-next-bigger-bets.md` with larger ideas that remain
  within the current-model/no-quality-loss constraint. New tracked branches
  include a decode-only c1 micro-runtime, transactional target-state capsule
  for verifier-safe speculation, target-owned branch farming with spare VRAM,
  hybrid TP/EP latency topology tests, hot-expert memory-for-latency replicas,
  B70 W8A8 tile-layout bakeoffs, whole-token Level Zero command-list replay,
  router-predictive prefetch that does not alter math, CPU/PCIe/NUMA
  control-plane audits, upstream-quality B70 W8A8 challenge packets, strict
  same-model 8-bit engine bakeoffs, and a reliability scoreboard as a
  promotion gate. The ordering is now explicit: keep the env-guarded oneDNN
  sidecar probe moving, build a decode critical-path ledger in parallel, then
  choose between persistent-MoE work and transactional target-state speculation
  based on measured wall time.

- Added and compile-validated a guarded oneDNN MoE sidecar probe surface in the
  local `vllm-xpu-kernels` tree. The new `qwen36_moe_onednn_sidecar_probe`
  op validates live Qwen3.6 MoE tensor ABI inputs, dry-creates oneDNN grouped
  matmul descriptors for GEMM1/GEMM2, and only wraps grouped source/destination
  USM handles when an explicit `onednn_grouped_offsets` tensor is supplied.
  It does not treat `rows_per_expert` as offsets. Validation was non-invasive:
  an out-of-tree `_xpu_C` build with IntelLLVM 2026.0 completed successfully,
  `nm` confirmed the exported probe symbol, and the live endpoint on
  `127.0.0.1:18080` stayed healthy on the current Quark INT8 model. New
  tracking artifacts:
  `patches/vllm-xpu-qwen36-onednn-sidecar-probe-20260612bk.diff` and
  `data/qwen36-onednn-sidecar-probe-build-20260612bk.json`. This is a
  compile/link gate only, not a speed claim; the next gate is Python-side
  env-guarded probe calls with XPU offset tensor construction while still
  returning the current `xpu_fused_moe` output.

- Added a post-discussion larger-bets addendum to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. The new section records a
  fresh Localmaxxing/XPU/MoE source scan and keeps the interpretation explicit:
  public Qwen3.6 rows above `200 tok/s` are mostly speculative/MTP or lower
  precision, so for the current Quark W8A8 INT8 goal the lesson is
  target-verified architecture, not a quantization substitution. New ideas
  now tracked include transplanting Intel's persistent MoE schedule, diffing
  latest Xe2 grouped-GEMM heuristics, building a B70 INT8 roofline ledger,
  offline route-skew autotuning, target-verified speculative transactions with
  GDN state safety, spare-VRAM branch farming, TP2/asymmetric latency lanes,
  signed packed-weight artifacts, split c1/aggregate production lanes, and an
  upstream maintainer-grade B70 W8A8 MoE packet.

- Added a live-ABI-to-sidecar planning artifact for the next no-quality-loss
  oneDNN integration step. `scripts/qwen36-live-abi-sidecar-plan.py` consumes
  the disabled-by-default live ABI smoke JSONL records and emits a concrete
  rank-local sidecar descriptor/checklist. The current smoke logs cover `48`
  records, `12` per rank across four ranks, and all required live tensors are
  present with shape/dtype/contiguity checks passing. The derived representative
  oneDNN work is GEMM1 `M=65536,K=2048,N=256` and GEMM2
  `M=65536,K=128,N=2048`, with route offsets covering all routed rows. New
  artifacts:
  `data/qwen36-live-abi-sidecar-plan-20260612bj.json` and
  `data/qwen36-live-abi-sidecar-plan-20260612bj.md`.
  This keeps the next guarded call explicit: zero-copy live XPU/USM tensor
  handoff, cached packed oneDNN primitives, per-rank fallback to current
  `xpu_fused_moe`, and final-layer `max_abs_diff=0.0` before any endpoint
  timing claim.

- Refreshed the bigger-bet queue with current external signals. Localmaxxing
  still shows the public exact-model B70/vLLM row at `99.428 tok/s` and a
  same-family B70 row at `99.770 tok/s`, so the next gains must come from
  architecture rather than launch flags. The detailed note now adds bolder
  candidates: fixed-shape c1 decode lanes, zero-copy oneDNN sidecar entry,
  route-class layerlet generation, VRAM-for-latency expert replication, a
  verifier-owned speculative transaction API, Level Zero command-list
  supernodes, and upstream/challenge packets for B70 W8A8 MoE.

- Expanded `notes/2026-06-12-qwen36-next-bigger-bets.md` with a fresh
  higher-risk idea backlog after the full resident gather gate. The new section
  keeps the current-model/no-quality-loss constraints explicit, records public
  Localmaxxing and XPU/MoE source signals, and adds larger paths to test:
  Intel-style persistent zero-gap MoE scheduling, rank-local command rings,
  tile-native W8A8 checkpoint artifacts, modular vLLM XPU MoE backend work,
  hot-expert partial replication, lower-TP c1 lanes, verifier-owned speculative
  transactions, DFlash/MTP/n-gram proposer bakeoffs under the current Quark
  verifier, oneDNN Graph / Level Zero command-list supernodes, and a
  maintainer-ready B70 W8A8 MoE performance packet.

- Added and smoked a disabled-by-default rank-local live ABI diagnostic for the
  current Quark W8A8 INT8 XPU MoE path. With
  `VLLM_XPU_MOE_LIVE_ABI_FILE` set, the hook records live rank-local tensor
  pointers, shapes, dtypes, route rows, scratch buffers, GEMM intermediates, and
  output checksums after `moe_gather`, then returns the accepted output
  unchanged. A TP4 smoke captured `48` records across all four ranks for layers
  `8` and `9`; the normal accepted backend was restored afterward and
  provenance passed both prefix cases plus sentinels `4752`, `11436`, and
  `198`. New artifacts include
  `data/qwen36-live-abi-smoke-summary-20260612bi.json`, the four
  `data/qwen36-live-abi-20260612bi-*.jsonl` rank logs,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-live-abi-smoke-20260612bi.json`,
  and isolated source patches under `patches/qwen36-live-abi-*20260612bi.diff`.

2026-06-12 continuation:

- Extended the resident oneDNN MoE GEMM-pair runner with mutable grouped-offset
  route-window replay using the real routecapture6 layer-9 count windows. The
  runner still first proves base GEMM parity against exported XPU buffers, then
  mutates grouped offsets for `16` real route windows while keeping primitives,
  weights, and buffers resident. First run: route-window pair p50 `44.543 us`,
  mean `44.939 us`; reused-binary rerun: route-window pair p50 `42.069 us`,
  mean `42.810 us`. Base GEMM1/GEMM2 raw equality stayed true
  (`raw_diff_count=0` for both). Route-window outputs intentionally differ
  from the base expected buffers because this benchmark mutates route counts
  over fixed exported inputs; it is a timing/cache-path gate, not full
  route-output parity. Accepted backend was restored afterward and provenance
  passed both prefix cases plus all sentinel tokens. This is the strongest
  evidence so far that a vLLM-side resident primitive cache with mutable
  offsets is worth implementing before hand-writing DPAS layerlets.
  New artifacts:
  `data/qwen36-onednn-moe-island-layer9-r1-resident-routewindows-20260612bb.json`,
  `data/qwen36-onednn-moe-island-layer9-r1-resident-routewindows-rerun-20260612bb.json`,
  `data/qwen36-quark-int8-tp4-accepted-restored-after-onednn-routewindow-resident-20260612bb.log`,
  and
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-onednn-routewindow-resident-20260612bb.json`.

- Added a CPU route-signature cache analyzer for real Qwen3.6 MoE route traces
  to decide whether the resident oneDNN path should cache generic primitives or
  exact route-specialized bundles. Across prompt-class traces plus
  routecapture6 (`5485` c1 decode MoE records, `5` captured layers), the
  mutable-offset primitive key has only `5` unique entries and reaches `99.9%`
  LRU hit rate with capacity `16` or `40`. Exact route keys are a poor cache
  target: active-set/count-vector keys have `914` unique entries and only
  `1.8%` LRU@40 hit rate; ordered top-k tuples are available for the
  routecapture6 subset only and have `285/285` unique routes with `0.0%` reuse.
  Decision: the next oneDNN integration should cache resident primitives and
  packed weights by layer/shape, then mutate offsets/counts at execution time.
  Do not build exact active-set layerlet caches; generated kernels should
  target hot-expert or broader route classes instead.
  New artifacts:
  `scripts/qwen36-route-signature-cache-analysis.py`,
  `data/qwen36-quark-int8-tp4-routecapture6-signature-cache-20260612ba.json`,
  `.md`,
  `data/qwen36-quark-int8-tp4-promptclass-plus-route6-signature-cache-20260612ba.json`,
  and `.md`.

- Added a resident oneDNN MoE GEMM-pair runner after the full layer-9 island
  parity proof. The new runner loads the real exported routecapture6 layer-9
  GEMM1/GEMM2 buffers once, constructs packed `acb` oneDNN grouped-matmul
  primitives once, then times both GEMMs in one long-lived process. First run:
  pair p50 `88.657 us`, mean `96.344 us`, with GEMM1/GEMM2 raw output equality
  against the current XPU exports. Warm reused-binary rerun: pair p50
  `49.954 us`, mean `54.340 us`, again exact for both GEMMs. This is the
  strongest non-speculative kernel signal so far, but still not an endpoint
  claim: it excludes the activation/quant/gather stages and has not yet used
  direct in-process XPU tensor handoff from vLLM. Next gate is a vLLM-side
  route-signature oneDNN primitive cache or sidecar custom op with final-layer
  `max_abs_diff=0.0` against `xpu_fused_moe`. The first backend restore after
  this clean XPU window hit `UR_RESULT_ERROR_DEVICE_LOST` in scheduler metadata
  copy paths; the stale workers were cleaned up, the XPUs were freed, and a
  retry backend reached `/health`. The retry provenance guard passed both
  prefix cases and all sentinel tokens.
  New artifacts:
  `tools/onednn_moe_island_resident_runner.cpp`,
  `scripts/run-onednn-moe-island-resident.sh`,
  `data/qwen36-onednn-moe-island-layer9-r1-resident-pair-20260612az.json`,
  `data/qwen36-onednn-moe-island-layer9-r1-resident-pair-rerun-20260612az.json`,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-onednn-resident-pair-20260612az.json`,
  `data/qwen36-quark-int8-tp4-accepted-restored-after-onednn-resident-pair-retry-20260612az2.log`,
  and
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-onednn-resident-pair-retry-20260612az2.json`.

- Added and ran a file-backed full layer-9 oneDNN MoE island replay. This is
  the first full-layer exactness gate after the standalone GEMM parity: Python
  keeps the current XPU remap, quantization, activation, and gather semantics,
  while packed oneDNN `acb` grouped matmul supplies GEMM1 and GEMM2 from
  exported intermediate buffers. The routecapture6 layer-9 rows=1 replay
  matched current XPU exactly at every checked boundary: GEMM1 max abs diff
  `0.0`, GEMM2 max abs diff `0.0`, and final gathered MoE output max abs diff
  `0.0` versus `xpu_fused_moe`; the reference and oneDNN-island checksums both
  equal `-751.800048828125`. oneDNN packed timings inside the scaffold:
  GEMM1 mean `34.463 us`, p50 `34.184 us`; GEMM2 mean `24.756 us`, p50
  `24.687 us`. This is still not an endpoint speed claim because file IO and
  process boundaries dominate wall time. The next real optimization gate is to
  move this exact island into a resident route-signature primitive cache inside
  the process, then time the full layer without file/process boundaries or
  repeated primitive construction. Accepted backend was restored afterward;
  `/health` returned after `58s` and provenance passed both prefix cases plus
  all sentinel tokens. New artifacts:
  `scripts/replay-qwen36-onednn-moe-island.py`,
  `data/qwen36-onednn-moe-island-layer9-r1-20260612ay/onednn_moe_island_result.json`,
  `gemm1.meta`, `gemm2.meta`, `gemm1_onednn_acb_result.json`,
  `gemm2_onednn_acb_result.json`,
  `data/qwen36-quark-int8-tp4-accepted-restored-after-onednn-moe-island-20260612ay.log`,
  and
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-onednn-moe-island-20260612ay.json`.

- Added a deterministic W8A8 grouped-GEMM parity packet for oneDNN versus the
  current XPU grouped-GEMM output using real Qwen3.6 layer-9 routecapture6
  counts and real Quark INT8 weights/scales. Both raw `abc` and packed `acb`
  oneDNN weight layouts are bit-exact against the current XPU output; the
  packed `acb` path is the important result. GEMM1 (`K=2048,N=256`) packed
  `acb` measured mean `35.950 us`, p50 `34.775 us`; GEMM2
  (`K=128,N=2048`) packed `acb` measured mean `26.078 us`, p50 `25.948 us`.
  Both compare artifacts report `raw_equal=true`, `raw_diff_count=0`, and
  `max_abs_diff=0.0`. This promotes oneDNN from a synthetic timing curiosity
  to the next exactness-preserving integration candidate, but it is not an
  endpoint speed claim. The next gate is a full layer-9 MoE island with packed
  oneDNN GEMMs, exact activation/quant/gather parity, route-signature
  primitive caching, and no extra host wait between the two GEMMs. New
  artifacts:
  `scripts/export-xpu-w8a8-gemm-case.py`,
  `scripts/compare-w8a8-gemm-case.py`,
  `scripts/run-onednn-grouped-int8-case.sh`,
  `tools/onednn_grouped_int8_case_runner.cpp`, and
  committed metadata/result summaries under
  `data/qwen36-w8a8-gemm-parity-layer9-r1-20260612ax/`. The raw tensor
  buffers are local-only because the expert-weight dumps exceed GitHub's file
  limit; rerun the exporter to regenerate them.

- Added a wider-opportunity addendum to
  `notes/2026-06-12-qwen36-next-bigger-bets.md` after the oneDNN
  route-window replay. The addendum records the next concrete gates:
  oneDNN-vs-current-XPU W8A8 grouped-GEMM parity, oneDNN scale/layout
  forensics, layer-9 full MoE parity replay, profiler acquisition, Qwen3.6
  GDN speculative-state audit, clean host-stack/topology A/B, TP economics,
  and Localmaxxing dry-run discipline. It also captures bigger bets:
  route-signature oneDNN primitive caching, ESIMD/DPAS generated layerlets,
  resident MoE command processing, exact target branch farming,
  trace-trained proposer behind target verification, static c1 sidecar,
  hot-expert memory lane, OpenVINO/oneDNN GenAI truth-serum check, public B70
  W8A8 MoE challenge packet, and a reliability-weighted scoreboard. Explicit
  non-goals remain: no 4-bit, no AWQ, no Qwen3.5 substitution, and no public
  promotion from synthetic tensors or unverified draft speed.

- Added routecapture6 layer-9 count-window export plus mutable-offset oneDNN
  replay. This keeps the oneDNN grouped INT8 primitives and memory resident,
  then rewrites grouped src/dst offsets for 16 real rows=1 layer-9 route
  windows from starts `0:64:4`. The route-window timing remains strong enough
  to justify the exactness implementation gate: bf16 GEMM1+GEMM2 with offset
  updates and one wait averaged `41.673 us` (p50 `41.678 us`, p90
  `42.700 us`), and f32 averaged `39.458 us` (p50 `38.902 us`, p90
  `40.626 us`). Checksums changed between fixed and route-window runs, so
  offset mutation is taking effect. This is still not an endpoint claim or
  numeric parity proof; the next required step is an exact route replay using
  current model-shaped tensors and comparing oneDNN output with
  `xpu_fused_moe`/current staged output at `max_abs_diff=0.0`. Accepted
  backend was restored afterward; `/health` returned after `56s` and
  provenance guard passed both prefix cases plus all sentinel tokens. New
  artifacts:
  `scripts/export-qwen36-route-counts.py`,
  `data/qwen36-quark-int8-routecapture6-layer9-r1-start0-64x4-counts-20260612aw.csv`,
  `.json`,
  `data/qwen36-onednn-grouped-int8-reuse-routecapture6-layer9-r1-20260612aw.json`,
  `.log`,
  `data/qwen36-quark-int8-tp4-accepted-restored-after-onednn-routewindows-20260612aw.log`,
  and
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-onednn-routewindows-20260612aw.json`.

- Added and ran a oneDNN grouped INT8 reuse-only Qwen-shape probe in a clean
  XPU benchmark window. This revises the prior oneDNN conclusion: oneDNN is
  still not viable if primitives/memory are recreated or if every call pays an
  isolated wait, but reused primitives and one wait for the GEMM1+GEMM2 pair
  are fast enough to justify a route-exact integration test. Layer-9 Qwen
  shapes over 8 routed rows measured: bf16 GEMM1+GEMM2 two-exec/one-wait
  mean `29.446 us`, p50 `29.145 us`, p90 `29.957 us`; f32 pair mean
  `26.465 us`, p50 `26.179 us`, p90 `27.412 us`. Destination checksums were
  nonzero, so the run is not a no-op launch artifact. Setup remains expensive
  (`~99-305 ms` construct time), so a route-signature primitive/memory cache is
  mandatory. This is not an endpoint speed claim: the probe uses synthetic
  buffers and has not yet compared oneDNN output against current Quark W8A8
  `xpu_fused_moe` on captured routes. Accepted backend was restored afterward;
  `/health` returned after `56s` and provenance guard passed both prefix cases
  plus all sentinel tokens. New artifacts:
  `tools/onednn_grouped_int8_reuse_probe.cpp`,
  `scripts/probe-onednn-grouped-int8-reuse.sh`,
  `data/qwen36-onednn-grouped-int8-reuse-qwenshape-20260612av.json`,
  `.log`,
  `data/qwen36-quark-int8-tp4-accepted-restored-after-onednn-reuse-20260612av.log`,
  and
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-onednn-reuse-20260612av.json`.
  Next oneDNN gate: routecapture6 layer-9 replay with mutable grouped offsets,
  real Quark W8A8 weights/scales, persistent primitives/memory, max abs diff
  `0.0`, then live model-forward regression if exactness and layer timing hold.

- Added a larger-opportunity refresh to
  `notes/2026-06-12-qwen36-next-bigger-bets.md` after the scratch-hook and
  oneDNN Qwen-shape probes. The refresh records the current Localmaxxing
  public state, external B70/vLLM/MTP signals, and a new ordered backlog:
  one-dispatch fake layerlet overhead gate, oneDNN reuse-only timing, layer-9
  hotset fast path with cold fallback, Qwen3.6 GDN speculative-state audit,
  long-context speculative stability probe, XMX/DPAS counter packet,
  model-forward graph surgery, TP/rank-group latency lanes, command-bundle
  layer groups, and a quality-near-miss logit-rank suite. Bigger bets now
  include a B70 MoE resident runtime, generated route-class layerlets,
  checksumed hot-expert tile-cache artifacts, verified multi-token target
  branch engine, a fixed-bucket latency sidecar outside vLLM, an upstream XPU
  kernel challenge packet, production split by service class, a driver/runtime
  regression farm, mixed hot/cold MoE scheduling, and a reliability-weighted
  benchmark scoreboard. This is notes-only; no endpoint or speed claim changed.

- Ran the next route-exact layer-9 scratch-hook screen and a Qwen-shaped
  oneDNN grouped INT8 dtype probe while the accepted backend was stopped for a
  clean XPU window, then restored the backend and passed provenance. The
  scratch `xpu_fused_moe(..., scratch=...)` path was exact but slower than the
  base call over 16 captured layer-9 route offsets: base `xpu_fused_moe`
  averaged `309.978 us/layer`, scratch `xpu_fused_moe` averaged
  `346.038 us/layer`, preallocated staged averaged `250.135 us/layer`, and
  all max diffs were `0.0`. Decision: do not wire scratch into the endpoint as
  a standalone speed lever. The oneDNN probe confirmed grouped signed INT8
  support for Qwen-like shapes: `s8` source, `s8` weights, per-token source
  scales, per-expert-column weight scales, and f32/bf16 outputs all created
  and executed on B70. Warm rerun Qwen-shaped execution was still slower than
  current grouped-GEMM components: GEMM1 f32 `222 us`, GEMM2 f32 `210 us`,
  versus current route-replay grouped GEMM components around `89-125 us`.
  Decision: do not use oneDNN as two standalone GEMM calls; keep it only for
  primitive-cache, fused island, or command-bundle/layerlet experiments.
  Backend `/health` returned after `57s` and accepted provenance passed both
  prefix cases plus all sentinel tokens. Artifacts:
  `data/qwen36-quark-int8-moe-routecapture6-layer9-scratch-hook-20260612au.json`,
  `.md`, `.log`,
  `tools/onednn_grouped_int8_dtype_probe.cpp`,
  `scripts/probe-onednn-grouped-int8-dtypes.sh`,
  `data/qwen36-onednn-grouped-int8-qwenshape-probe-20260612au.json`,
  `data/qwen36-onednn-grouped-int8-qwenshape-probe-20260612au.log`,
  `data/qwen36-onednn-grouped-int8-qwenshape-probe-rerun-20260612au.log`, and
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-onednn-probes-20260612au.json`.

- Completed the next oneDNN grouped-memory smoke after the first broad build
  probe. A GPU-only vendored oneDNN build with
  `DNNL_CPU_RUNTIME=NONE`, `DNNL_ENABLE_PRIMITIVE=MATMUL;SDPA`,
  `DNNL_EXPERIMENTAL_GROUPED_MEMORY=ON`, `DNNL_GPU_RUNTIME=SYCL`, and
  `DNNL_ENABLE_PRIMITIVE_GPU_ISA=XE2` produced a linkable
  `libdnnl.a` and the vendored `matmul_grouped.cpp` example passed on a B70
  through Level Zero. Negative findings were also recorded: a CPU-enabled
  build stayed too broad, a MATMUL-only full `dnnl` target failed in
  `gpu_sdpa_list.cpp`, and the internal `dnnl_gpu_intel` target compiled the
  grouped GPU units but did not produce a standalone library. This remains a
  build/API smoke only, not a Qwen endpoint or speed claim. Next step is a
  routecapture6 layer-9 W8A8 oneDNN replay with primitive-creation timing and
  `max_abs_diff=0.0` against current `xpu_fused_moe`. Artifacts:
  `scripts/probe-onednn-grouped-gpuonly.sh`,
  `data/qwen36-onednn-grouped-gpuonly-smoke-20260612d.json`, and
  `notes/2026-06-12-qwen36-next-bigger-bets.md`.

- Captured the first vendored-oneDNN grouped-memory build probe after the
  post-floor backlog update. A local `vllm-xpu-kernels` CMake patch enabling
  `DNNL_EXPERIMENTAL_GROUPED_MEMORY=TRUE` configured successfully against the
  vendored oneDNN tree with oneAPI compiler `2025.3`; the grouped micro-GEMM
  and ref-grouped-GEMM host/generated GPU units compiled. The full extension
  build was stopped once it moved into broad generated attention-kernel
  compilation, so this is a build-viability result only, not an endpoint
  promotion or speed claim. Next step: narrow the build to oneDNN/matmul-only
  or `libdnnl.a`, then wrap a routecapture6 layer-9 grouped-memory matmul op
  and compare it against the current `112-114 us` W8A8 grouped-GEMM dispatch
  floor. Artifacts:
  `patches/vllm-xpu-kernels-onednn-grouped-memory-build-probe-20260612.patch`
  and `data/qwen36-onednn-grouped-memory-build-probe-20260612.json`.

- Added a post-floor follow-up backlog to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. The new section records a
  fresh Localmaxxing API check, the local oneDNN grouped-memory capability
  split, and larger exactness-preserving bets. Key additions: vendored-oneDNN
  grouped-memory route replay with `ONEDNN_EXPERIMENTAL_GROUPED_MEMORY=ON`,
  command-stream floor measurement, one-dispatch fake layerlet, PCIe/topology
  and affinity c1 A/B, rank-local timing without synchronization pollution,
  static prefix/state lane, hot-expert packed tile cache, verifier-service
  boundary for speculation, B70 MoE micro-runtime, whole-model c1 runner,
  expert-parallel latency lane, public XPU MoE challenge packet, and production
  split by latency class. This is notes-only; no endpoint change or new public
  benchmark claim was made.

- Added an isolated W8A8 kernel-floor packet for layer-9 routecapture6 after
  stopping the accepted backend for a clean XPU window. Exact grouped GEMM is
  essentially flat across route-window sizes: window 1 averages
  `113.845 us`/`112.371 us` for gemm1/gemm2, while window 16 averages
  `112.596 us`/`114.068 us`. Quant helper calls sit around `88-115 us`. The
  decision is that c1 decode is now best treated as a launch/control/tiny-shape
  floor: two exact grouped GEMM dispatches already cost about `226 us/layer`,
  above the `~168 us/layer` non-speculative budget before the rest of MoE.
  Next non-speculative work should collapse dispatch boundaries via a
  persistent/one-dispatch layerlet, a oneDNN grouped-matmul fused-control
  replay, or a whole-token command graph; helper variants remain plumbing, not
  endpoint candidates. Artifacts:
  `notes/2026-06-12-qwen36-w8a8-floor-and-layerlet-decision.md`,
  `data/qwen36-quark-int8-w8a8-kernel-floor-layer9-routecapture6-w1-20260612an.json`,
  `.log`,
  `data/qwen36-quark-int8-w8a8-kernel-floor-layer9-routecapture6-w16-20260612an.json`,
  `.log`, and
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-floor-20260612an.json`.
  Accepted backend was restored afterward; `/health` returned after `59s` and
  provenance passed both prefix cases plus all sentinel tokens.

- Ran the quant out-variant scaffold through an isolated layer-9 routecapture6
  rows=1 replay using a temporary package overlay, leaving the accepted source
  package untouched. The patched artifact exposed both quant out ops and the
  replay reported `quant_out_op_available=True` across 16 route windows.
  Exactness passed with `max_abs_diff=0.0` for manual staged, scratch
  `xpu_fused_moe`, preallocated staged, and fused-prologue staged versus
  current `xpu_fused_moe`. Mean timings: current `xpu_fused_moe`
  `299.072 us/layer`, scratch `xpu_fused_moe` `248.626 us/layer`,
  preallocated staged with quant-out buffers `207.237 us/layer`, and
  fused-prologue staged `282.710 us/layer`. Decision: keep the scaffold as
  layerlet plumbing because it improves the exact staged path versus prior
  `216-226 us/layer` screens, but do not promote it by itself because it is
  still above the `~168 us/layer` non-speculative budget. Accepted backend was
  relaunched after the benchmark, source-package import confirmed the
  experimental ops are absent from the served runtime, and provenance passed
  both prompt cases plus all sentinel tokens. Artifacts:
  `data/qwen36-quark-int8-moe-routecapture6-layer9-quant-out-scaffold-20260612am.json`,
  `.md`, `.log`, and
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-quantout-20260612am.json`.

- Added the quant out-variant scaffold note and refreshed the larger no-quality
  loss backlog with public B70/vLLM signals. The source scaffold adds strict
  caller-owned output buffers for INT8 quantization in the dirty
  `vllm-xpu-kernels` and `vllm` source trees, and the route replay script now
  uses those buffers when a patched `_xpu_C` artifact is available while
  falling back cleanly on the accepted package. Static Python compile, diff
  checks, native `_xpu_C` build, and isolated import/registration all passed;
  no endpoint install or XPU timing claim was made while the accepted TP4
  backend was live. Next gate is an isolated layer-9 routecapture6 rows=1
  replay requiring `max_abs_diff=0.0` and a real speed win before any promotion.
  The backlog refresh records bigger candidates: persistent MoE worker per
  card, generated Qwen3.6 INT8 layerlets, EP-like decode lane, one/two-card
  latency replicas, offline DPAS/XMX tiled weight pack, whole-token command
  graphs, target-model lookahead, verifier escrow with trace-trained
  micro-drafter, static c1 appliance behind the OpenAI frontdoor, clean Intel
  container A/B, and a public upstream performance challenge packet. Details:
  `notes/2026-06-12-qwen36-quant-out-scaffold.md` and
  `notes/2026-06-12-qwen36-next-bigger-bets.md`.

- Added a new big-bet refresh to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. It folds in the latest
  roofline packet, active-offset rejection, Localmaxxing API context, and
  external XPU/vLLM signals without changing the endpoint or claiming a new
  speed result. The updated near-term queue prioritizes a fixed layer-9
  persistent layerlet scaffold, quant out-variants as layerlet plumbing,
  DPAS/XMX profiling, clean Intel container A/B, TP2/EP truth-serum runs,
  graph-safe metadata arenas, route-class autotune tables, resident verifier
  state, Localmaxxing dry-run discipline, and an upstream repro packet. The
  larger bets now explicitly track a B70-resident MoE device service, layerlet
  code generation, exact target-model branch lookahead, trace-trained
  micro-proposers behind a transactional verifier, static c1 latency appliance,
  hot-expert memory-for-latency service class, one/two-card latency replicas,
  whole-token command graphs, a public kernel challenge packet, and a
  reliability score beside every speed result.

- Added a consolidated Qwen3.6 roofline/stall packet and refreshed the live c1
  endpoint budget. The accepted service remains healthy and paused-local on the
  public frontdoor. A fresh p512/o512 local-bypass run measured `99.618 tok/s`
  corrected after first chunk, `98.130 tok/s` e2e, `87.996 ms` client TTFT,
  and a vLLM decode histogram of `10.039 ms/token`. The refreshed MoE fusion
  target budget says a non-speculative `>200 tok/s` path needs roughly
  `168.173 us/layer` or better for rows=1, while the exact current MoE replay
  is `294.145 us/layer`, preallocated staged is `220.530 us/layer`, and the
  two-independent-grouped-GEMM floor is still `193.538 us`; therefore a
  two-dispatch path cannot reach the target by itself. The expanded
  prompt-class route simulation covered `5485` route records and `325` windows;
  `ep4_hot64_replicated_greedy` reduces the communication-row proxy to
  `0.155` with balanced pressure at `1.75x` expert-memory cost, so hot
  replication remains a serious medium-term layout idea but should not preempt
  the immediate one-layer persistent MoE layerlet proof. Decision: next
  implementation branch is a fixed routecapture6 layer-9 persistent layerlet
  with exact parity and a pass/fail target of `<=168 us/layer`; in parallel,
  keep target-verified speculation as the high-upside fallback if the layerlet
  cannot beat the budget. Artifacts:
  `notes/2026-06-12-qwen36-roofline-stall-packet.md`,
  `data/qwen36-quark-int8-tp4-live-c1-p512o512-metrics-20260612al.json`,
  `data/qwen36-quark-int8-moe-fusion-target-budget-20260612al.md`,
  `data/qwen36-quark-int8-moe-fusion-target-budget-20260612al.json`,
  `data/qwen36-quark-int8-tp4-promptclass-plus-route6-parallelism-sim-20260612al.md`,
  and
  `data/qwen36-quark-int8-tp4-promptclass-plus-route6-parallelism-sim-20260612al.json`.

- Built and gated the active-expert offset W8A8 grouped-GEMM prototype. The
  compact-active variant compiled through `_xpu_C` and `grouped_gemm_xe_2`
  with oneAPI 2025.3, registered cleanly from the build artifact, and passed
  route-exact layer-9 routecapture6 rows=1 replay across 16 windows with
  `max_abs_diff=0.0` against current `xpu_fused_moe`. It is not a speed win:
  active-offset averaged `225.911 us/layer`, effectively tied with and slightly
  slower than plain offset GEMM at `225.162 us/layer`, while the accepted
  current `xpu_fused_moe` screen averaged `304.448 us/layer` and scratch
  `xpu_fused_moe` averaged `267.360 us/layer`. Decision: keep the patch as a
  microbench prototype only, do not expose it to the endpoint, and shift the
  next non-speculative work to a larger one-dispatch/persistent MoE layerlet or
  quant/gather out-variants that feed that layerlet. Package libraries were
  restored to the accepted pre-active-offset binaries before backend restart;
  restored package import confirms both experimental ops are absent. Accepted
  backend relaunched in
  `qwen36-tp4-accepted-restored-after-activeoffset-20260612aj`, `/health`
  returned after `48s`, provenance guard passed all exact sentinels, and a
  p512/o128 sanity run measured `100.028 tok/s` corrected after first chunk
  with `9.923 ms/token` decode histogram. Artifacts:
  `patches/vllm-xpu-kernels-w8a8-active-offset-gemm-prototype-20260612ai.patch`,
  `data/vllm-xpu-kernels-active-offset-build-20260612ai.log`,
  `data/qwen36-quark-int8-moe-routecapture6-layer9-active-offset-gemm-20260612ai.md`,
  `.json`, `.log`,
  `data/qwen36-quark-int8-moe-routecapture6-layer9-active-offset-gemm-summary-20260612ai.json`,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-activeoffset-20260612aj.json`,
  and
  `data/qwen36-quark-int8-tp4-accepted-restored-after-activeoffset-speed-p512o128-20260612aj.json`.

- Added a fresh external-scan and larger-bets refresh to
  `notes/2026-06-12-qwen36-next-bigger-bets.md`. It records the Localmaxxing
  API nuance that the broad Arc Pro B70/Qwen family query shows our
  `cmq9ifq0500b0r8012f27j1xl` row at `99.7697 tok/s`, while the exact
  `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` filter still returns only the
  older `cmq8yhxvo001ipb0149aoa79o` row at `99.4284 tok/s`. It also folds in
  current vLLM W8A8 docs, Intel IPEX/XPU container notes, and B70 TP-fault
  reports. New tracked next ideas include active-offset grouped GEMM,
  device-image budget gates, a clean Intel container A/B, route-exact EP/TP
  simulation, graph-safe metadata-copy repros, DPAS/XMX proof packets, a
  static c1 graph runner, TP2 latency truth-serum runs, resident-state
  verifier speculation, shallow target self-drafting, a persistent MoE device
  service, an upstream performance challenge packet, reliability scoring, and
  BF16/logit-rank quality shadows. This is notes-only; no new speed claim or
  endpoint promotion.

- Built and tested the offset-native W8A8 grouped-GEMM prototype against the
  layer-9 routecapture6 rows=1 replay. The oneAPI 2026 build was rejected
  before use because it linked against `libsycl.so.9`; the rebuilt oneAPI
  2025.3 artifact linked against `libsycl.so.8`, imported cleanly, and passed
  XPU sync. Route replay was exact (`max_abs_diff=0.0`) and showed a real
  component win: fused prologue plus offset GEMM averaged `213.233 us/layer`
  versus fused prologue staged `285.787 us/layer`, exact preallocated staged
  `218.158 us/layer`, and current scratch `xpu_fused_moe` `256.611 us/layer`.
  Serving promotion failed: the offset-built backend reached `/health`, but the
  first provenance completion crashed with Level Zero
  `UR_RESULT_ERROR_DEVICE_LOST` in `block_table.copy_to_gpu`, followed by
  `UR_RESULT_ERROR_OUT_OF_RESOURCES` during shutdown. Decision: keep the source
  patch as a prototype only, do not expose it live, and move the next kernel
  work toward a narrower offset ABI, active-expert loop removal, or a
  persistent/one-dispatch MoE layerlet. Live libraries were rolled back to the
  accepted pre-offset runtime, the offset op is absent from live imports, and
  accepted provenance passed exact sentinels after rollback. Artifacts:
  `patches/vllm-xpu-kernels-w8a8-offset-gemm-prototype-20260612.patch`,
  `data/vllm-xpu-kernels-offset-gemm-rebuild-oneapi2025-20260612.log`,
  `data/qwen36-quark-int8-moe-routecapture6-layer9-offset-gemm-20260612ae.md`,
  `data/qwen36-quark-int8-moe-routecapture6-layer9-offset-gemm-20260612ae.json`,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-offset-gemm-20260612af.json`,
  `data/qwen36-quark-int8-tp4-accepted-restored-after-offset-gemm-20260612af.log`,
  and
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-offset-rollback-20260612ag.json`.

- Added another focused backlog refresh after the offset-native W8A8 grouped-GEMM
  prototype started. This is notes-only, not a speed claim. The new section
  treats the offset op as a fast build-and-kill-gate experiment, then records
  larger no-quality-loss bets: active-expert-loop removal, fused hotset plus
  compact-cold single dispatch, route-class graph libraries, layerlet code
  generation, a process-local MoE device service, TP2/single-card c1
  truth-serum runs, full-token command-list capture, BF16 shadow differential
  checks, verifier-owned speculative escrow, shallow target self-drafting,
  prompt-shape admission control, upstream performance challenge packets, and
  reliability soak requirements. Details:
  `notes/2026-06-12-qwen36-next-bigger-bets.md`.

- Added a fresh ideas refresh after reviewing the W8A8 grouped-GEMM offset ABI
  and current public benchmark context. The new notes distinguish faster
  Localmaxxing same-family rows as architecture clues rather than
  quality-equivalent targets because top public rows use other hardware and/or
  lower-fidelity quant/speculation such as MQ4-AWQ, NVFP4, Q4_K_M, MTP, or
  speculative decode. The focused backlog now adds concrete no-quality-loss
  branches: offset-native W8A8 grouped GEMM, oneDNN grouped-memory replay as a
  control, route-window persistent worker proof, DPAS/XMX roofline packet,
  static c1 latency lane, target-verified speculation, same-model
  trace-trained micro-drafter, route-class autotuning, host-stack reliability
  matrix, and an upstreamable B70 performance packet. Details:
  `notes/2026-06-12-qwen36-next-bigger-bets.md`.

- Extended `scripts/bench-qwen36-int8-moe-kernels.py` with a full-layer
  `fused_prologue_staged` replay path, then ran layer-9 routecapture6 rows=1
  starts `0:64:4`. The path is exact against current `xpu_fused_moe`
  (`max_abs_diff=0.0`), but the full path is not a speed win: mean
  `xpu_fused_moe` is `288.237 us/layer`, scratch `xpu_fused_moe` is
  `258.465 us/layer`, exact manual preallocated staged is
  `216.361 us/layer`, and fused-prologue staged is `284.705 us/layer`. The
  exposed prologue ABI emits expert offsets while the current W8A8 grouped GEMM
  op consumes `int32 rows_per_expert`, so the conversion/glue erases the small
  prologue-only win. Decision: do not wire the current prologue path into the
  endpoint. Next productive non-speculative work is either an offset-native
  W8A8 grouped-GEMM ABI, exact quant/gather out-variants, or a larger
  one-dispatch/persistent MoE layerlet that fuses prologue with downstream
  work. Accepted TP4 service was restored afterward and provenance passed all
  exact sentinels. Artifacts:
  `data/qwen36-quark-int8-moe-routecapture6-layer9-prologue-staged-20260612ar.md`,
  `data/qwen36-quark-int8-moe-routecapture6-layer9-prologue-staged-20260612ar.json`,
  and
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-prologuestaged-20260612as.json`.

- Added and ran a route-exact prologue screen for the existing
  `torch.ops._moe_C.fused_moe_prologue` path:
  `scripts/bench-qwen36-moe-prologue.py`. On layer-9 routecapture6 rows=1
  windows, the prologue exactly matched current `remap_hidden_states` expansion
  and expert counts (`max_expand_abs_diff=0.0`,
  `max_rows_per_expert_diff=0`) while reducing the current
  `rows_per_expert.zero_()+remap_hidden_states` substep from
  `111.108 us` mean to `106.637 us` mean, a `4.471 us` average component win.
  This is useful for a future one-dispatch MoE layerlet, but too small by
  itself to move the `~10 ms/token` c1 decode bottleneck. The accepted TP4
  service was restored on `127.0.0.1:18080` and provenance passed all exact
  sentinels after the benchmark. The refreshed backlog now adds larger lanes:
  kernel ABI cleanup with out-variants, fixed-shape static decode bundles,
  target-verified speculative transactions, DPAS/XMX counter proof, route-aware
  AOT MoE layerlets, host-stack stress gates, and production split-lane routing.
  Artifacts:
  `data/qwen36-quark-int8-moe-prologue-layer9-routecapture6-20260612aq.md`,
  `data/qwen36-quark-int8-moe-prologue-layer9-routecapture6-20260612aq.json`,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-prologue-20260612aq.json`,
  and `notes/2026-06-12-qwen36-next-bigger-bets.md`.

- Ran the layer-9 routecapture6 rows=1 fused SiLU+quant gate. Baseline current
  `xpu_fused_moe` is exact at max diff `0.000`, averaging
  `283.098 us/layer`; exact preallocated staged replay averages
  `212.792 us/layer`. The fused SiLU+quant candidate is rejected because it
  drifts by max abs diff `0.750` and only moves mean `xpu_fused_moe` timing to
  `272.862 us/layer`, still far above the `~160 us/layer` non-speculative
  budget. Accepted TP4 service was restored on `127.0.0.1:18080`; provenance
  passed exact sentinels against the accepted graph cache and `xpu-smi ps`
  showed one TP worker owning each B70 with about `32.76 GB` allocated per
  card. The detailed backlog now records the rejection plus larger next bets:
  one-dispatch/persistent W8A8 MoE, whole-token command tracing,
  hardware-counter proof, upstream route-exact repros, transactional
  target-verified speculation, device-side expert queues, tile-native expert
  caches, static c1 decode, hybrid TP/EP with hot-expert replication, kernel
  branch archaeology, and same-model micro-drafters. Artifacts:
  `data/qwen36-quark-int8-moe-routecapture6-layer9-baseline-gate-20260612ap.md`,
  `data/qwen36-quark-int8-moe-routecapture6-layer9-fused-siluq-gate-20260612ap.md`,
  `data/qwen36-quark-int8-tp4-accepted-provenance-after-siluqgate-20260612ap.json`,
  and `notes/2026-06-12-qwen36-next-bigger-bets.md`.

- Added a CPU-only MoE fusion target budget after the grouped-GEMM M-scaling
  screens. Current accepted p512/o128 decode remains about `99.845 tok/s`
  corrected with `9.941 ms/token`; model-forward-only timing is
  `8.438 ms/token`. A true `200 tok/s` c1 lane needs `5.000 ms/token`, so with
  outside-forward overhead unchanged the model-forward bucket must save
  `4.941 ms/token`, or `123.514 us/layer` across `40` MoE layers. Route-exact
  current `xpu_fused_moe` averages `283.842 us/layer`, exact preallocated
  staging averages `214.179 us/layer`, and the next non-speculative layerlet
  must target about `160.328 us/layer` or better. Two independent small-M GEMM
  dispatches already cost `193.538 us`, so the next no-quality-loss branch is a
  one-dispatch/persistent W8A8 MoE replay with exact parity; if that cannot beat
  the budget, shift to exact target-verified speculation. New artifacts:
  `scripts/qwen36-moe-fusion-target-budget.py`,
  `data/qwen36-quark-int8-moe-fusion-target-budget-20260612ao.md`, and `.json`.
  The detailed note also adds external leads and bigger bets from
  Localmaxxing, `vllm-xpu-kernels`, oneDNN grouped GEMM, Qwen3.6 W8A8 support
  gaps, and Event-Tensor-style dynamic megakernels:
  `notes/2026-06-12-qwen36-next-bigger-bets.md`.

2026-06-11 continuation:

- Added API-token-ID baseline capture and the rolling one-token verifier probe. `scripts/qwen36-completion-oracle-trace.py` now requests `return_token_ids=true` and stores API token IDs separately from retokenized text IDs. Fresh baseline `data/qwen36-quark-int8-tp4-accepted-current-apiids-p512o128-20260611h.json` matches the prior current baseline exactly, so earlier token IDs were not the cause of the verifier-probe failures. New script `scripts/probe-qwen36-rolling-next-token-verifier.py` re-prefills `prompt + accepted_output_prefix` and asks for one next token. Full result in `data/qwen36-quark-int8-tp4-rolling-next-token-verifier-apiids-p512o128-20260611h.json/.md`: `natural_latency_plan` matched `122/128` with first mismatch at pos `17` (`11436` expected, `321` generated), and `repetitive_kernel_notes` matched `126/128` with first mismatch at pos `14` (`4752` expected, `6126` generated). This proves a re-prefill sidecar is not semantically aligned with accepted incremental decode; the speculation path must preserve rolling verifier state, via in-engine temporary KV/request-state fork or a rolling sidecar advanced token-by-token in lockstep.
- Added the prompt-logprob sidecar verifier-bucket probe and refreshed the larger no-quality-loss ideas queue. The fresh current accepted baseline is `data/qwen36-quark-int8-tp4-accepted-current-p512o128-20260611g.json`; the stale no-async metadata fixture no longer matches the restored accepted backend (`data/qwen36-quark-int8-tp4-accepted-current-vs-metadata-p512o64-20260611g.json`), so verifier-bucket conclusions now use `data/qwen36-quark-int8-tp4-prompt-logprob-verifier-buckets-current-20260611g.json/.md`. Result: all mutated-first-token controls reject at prefix `0`, and perfect drafts are all rank-1 through window `4`, but larger windows fail (`w8` `30/32`, `w16` `32/64`, `w32` `52/128` accepted prefixes). Conclusion: prompt-logprob teacher forcing is useful as a short-window diagnostic, but it is not a production verifier and not a replacement for temporary-KV or rolling-KV shadow verification. Refreshed exact-model Localmaxxing data still shows our single public exact row at `99.428358 tok/s`; the detailed note now tracks bolder V3 ideas: temporary-KV verifier fork, rolling sidecar verifier, verified speculative streaming buffer, prompt-class speculation heatmaps, GDN/Mamba state audit, real-router capture, hot-expert memory-for-latency planning, single-stream Level Zero command-graph runner, strict 8-bit engine bakeoff, upstream repro packets, reliability scoreboard, and production service split after speed proof.
- Ran the accepted no-async versus oracle `k=1` no-mamba-spec-blocks metadata diagnostic. The row-0 cache state now matches exactly: four cache groups, Mamba groups `0/1/2` with `num_speculative_blocks=0`, identical request block IDs `[[1], [2], [3], [4]]`, and matching `num_tokens_no_spec`, prompt/computed counters, accepted-token counters, and `prev_num_draft_len=0`. The first real verifier-input mismatch moves to `tp_rank=0`, `rank_step=1`, where accepted schedules one verifier slot (`attn.slot_mappings.0.head=[33270]`) while oracle schedules verifier plus one draft slot (`[33270, 33271]`) with `prev_num_draft_len=1`. Conclusion: the remaining speculative drift is actual scheduled-draft row width/request accounting, not Mamba speculative block reservation. Next repair target is a shadow/sidecar verifier bucket or scheduler patch that verifies draft tokens in temporary KV and commits only accepted tokens. New artifacts include `data/qwen36-quark-int8-tp4-accepted-noasync-metadata-p512o128-20260611f.json`, `data/qwen36-quark-int8-tp4-oracle1-nomambaspec-metadata-p512o128-20260611f.json`, `data/qwen36-quark-int8-tp4-accepted-vs-oracle1-nomambaspec-metadata-parity-tprank-20260611f.md`, `data/qwen36-quark-int8-tp4-oracle1-nomambaspec-metadata-spec-summary-20260611f.md`, and `data/qwen36-quark-int8-tp4-oracle1-nomambaspec-metadata-drift-fixture-20260611f.md`. The detailed note now adds bolder V2 ideas: shadow verifier bucket, out-of-process verifier sidecar, static c1 decode lane, DFlash/MTP proposer-only route, route-aware `vllm-xpu-kernels` MoE suite, TP/EP simulator, graph-capture reliability campaign, and upstreamable repro packets. The first accepted restore after diagnostics hit `UR_RESULT_ERROR_DEVICE_LOST` during XPU graph capture on TP2; a clean retry restore in `qwen36-tp4-accepted-restored-after-metadata-retry-20260611f` reached `/health` after `62s`, and frontdoor local-bypass smoke returned `OK` while remote traffic remains paused.
- Added low-risk trace metadata instrumentation for the next Qwen3.6 speculative verifier-drift diagnostic. Local vLLM `gpu_model_runner.py` now enriches `VLLM_XPU_MODEL_INPUT_TRACE_FILE` rows with speculative method/width/proposer booleans, async/spec mode, KV cache group spec types, per-group `num_speculative_blocks`, request block-id heads, `num_tokens_no_spec`, prompt/computed/accepted counters, and `prev_num_draft_len`. The repo records this as `patches/vllm-qwen36-model-input-trace-metadata-20260611f.patch`; `scripts/check-qwen36-model-input-parity.py` now canonicalizes the new request-state rows while dropping volatile request IDs. Validation passed with `py_compile` on the checker and local runner, reverse patch check against `/home/steve/src/vllm`, and `git diff --check`. This does not change model behavior; use it on the next isolated `18081` accepted-vs-oracle/no-mamba run to decide whether the next repair is `spec-config/no-proposer`, zero-width actual-spec, or a sidecar verifier-bucket path.
- Added rank-normalized model-input parity support and a larger opportunity backlog refresh for Qwen3.6 Quark INT8. `scripts/check-qwen36-model-input-parity.py` now supports `--align-by tp-rank-step`, which buckets trace rows by TP rank and removes rank-order noise before comparing verifier inputs. New reports sharpen the speculative blocker: no-mamba-spec-blocks versus accepted no-async now first mismatches at `tp_rank=0`, `rank_step=1`, `attn.slot_mappings.0.head`, `[33270]` versus `[33270,33271]`, while the original logprob oracle still mismatches at `rank_step=0`, `attn.block_tables.0.cpu.head`, `[1]` versus `[1,2]`. Interpretation: the placebo/Mamba block fix was real, no-mamba removed one row-0 signal, but actual n-gram/oracle speculation still widens verifier attention/slot state and cannot be promoted. New artifacts: `data/qwen36-quark-int8-tp4-accepted-vs-oracle1-nomambaspec-modelinput-parity-tprank-20260611e.json/.md` and `data/qwen36-quark-int8-tp4-accepted-vs-oracle1-logprobs-modelinput-parity-tprank-20260611e.json/.md`. The detailed Qwen note now tracks next diagnostics plus bigger bets: speculation outside vLLM's scheduler path, official-MTP-as-proposer with Quark verifier, latency-first c1 runner, hybrid TP/EP, hot-expert replication, persistent route-window MoE, B70-native W8A8 tile cache, strict 8-bit engine bakeoff, whole-token command-list capture, and upstream/crowd repro packets.
- Ran the no-mamba-spec-blocks oracle `k=1` diagnostic. Local vLLM now has an opt-in `VLLM_XPU_NGRAM_NO_MAMBA_SPEC_BLOCKS=1` path, exposed through `NGRAM_NO_MAMBA_SPEC_BLOCKS=1` in `scripts/launch-qwen36-quark-int8-ngram-trace.sh`, that sets `MambaSpec.num_speculative_blocks=0` for `ngram`/`ngram_gpu` proposers only. It did not fix correctness: the isolated `p512/o128` fixture still has `baseline_match_all=false`, both tracked prompts diverged by output token index `3`, and model-input parity still shows immediate slot-mapping drift after rank-order noise. Conclusion: the prior zero-lookahead/placebo Mamba block fix was real, but actual oracle/n-gram speculation has another verifier-input reservation/accounting path beyond `MambaSpec.num_speculative_blocks`. Do not time or promote this path. New artifacts include `data/qwen36-quark-int8-tp4-oracle1-nomambaspec-p512o128-20260611d.json`, `data/qwen36-quark-int8-tp4-oracle1-nomambaspec-spec-summary-20260611d.md`, `data/qwen36-quark-int8-tp4-accepted-vs-oracle1-nomambaspec-modelinput-parity-20260611d.md`, and `patches/vllm-qwen36-ngram-no-mamba-spec-blocks-diagnostic-20260611.patch`. Accepted service restored in `qwen36-tp4-accepted-restored-after-nomambaspec-20260611d`; backend `/health` passed after `54s`, paused-local public frontdoor exact smoke returned `OK`, and final status is paused for remote generation with local bypass enabled, active `0`, queued `0`. The detailed note now adds larger next bets: rank/request-normalized model-input parity, spec-config/no-proposer and zero-width diagnostics, static solo decode lane, KV-resident verifier buckets, speculative scheduler bisect, route-window compiler, memory-for-latency hotsets, hybrid TP/EP, whole-token command-list capture, B70-native W8A8 retile cache, strict 8-bit engine bakeoff, reliability scoreboard, and upstreamable B70 repro packets.
- Added API logprob fingerprint capture to the Qwen oracle harness and a comparator script. The matched no-async accepted versus oracle `k=1` `p512/o128` logprob run still fails exact parity even though the oracle scheduler accepts `14/14` draft tokens. New evidence is stronger: top-k/logprob distributions diverge before the selected-token fork (`natural_latency_plan` top-k differs at row `0`; `repetitive_kernel_notes` selected tokens drift at index `14` and top-k differs earlier), and model-input parity mismatches from row `0` because oracle actual-spec has extra attention blocks (`[1]` vs `[1,2]`) while `scheduled_spec_decode_tokens={}` and `use_spec_decode=false`. This points at actual speculative cache/block-table state leaking into verifier inputs before drafts are active. New artifacts include `data/qwen36-quark-int8-tp4-accepted-vs-oracle1-logprobs-compare-20260611c.json/.md`, `data/qwen36-quark-int8-tp4-accepted-vs-oracle1-logprobs-modelinput-parity-20260611c.json/.md`, and the accepted/oracle logprob traces. Accepted service restored in `qwen36-tp4-accepted-restored-after-logprob-oracle-20260611c`; backend health and frontdoor local-bypass `OK` smoke pass. Next concrete experiment: an opt-in actual-spec diagnostic that zeros or hides speculative blocks for n-gram/oracle proposers only, with no-logprob and logprob parity gates before any MTP/DFlash work resumes.
- Ran the patched no-async oracle/perfect-draft lane and updated the Qwen note with results plus a bolder follow-up backlog. Short `p512/o32` oracle `k=5` passed exact parity against the no-async accepted baseline with `52/52` draft tokens accepted, but the longer `p512/o128` gate failed: oracle `k=5` matched only `31/40` draft tokens and drifted, and oracle `k=1` still drifted at output token index `14` on both fixtures despite `14/14` accepted drafts. This makes speculative verifier/KV/GDN state the current blocker, not drafter quality. Do not promote MTP/DFlash/n-gram or submit a new Localmaxxing speed result until oracle `k=1` exact parity passes on the longer fixture. New artifacts include the no-async accepted/oracle completion captures, spec summaries, drift fixtures, and public refreshes `data/localmaxxing-qwen36-fp8-top-refresh-20260611c.json` plus `data/localmaxxing-qwen36-dflash-refresh-20260611c.json`; details: `notes/2026-06-11-qwen36-aot-localmaxxing-and-runtime-screens.md`. Accepted service was restored in tmux session `qwen36-tp4-accepted-restored-after-oracle-noasynclane-20260611b`; backend `/health`, model listing, and frontdoor local-bypass `OK` smoke pass while frontdoor remains paused for remote users with local bypass enabled.
- Added a post-repair ideas/backlog section after fresh web and Localmaxxing context. Immediate next work is now ordered as: patched oracle/perfect-draft in the no-async parity lane, no-async accepted quality/speed baseline, logits/top-k fingerprints for verifier drift, isolated latest `vllm-xpu-kernels` bakeoff, and route histogram capture. Bigger tracked branches now include Quark-verifier MTP and DFlash sidecars, a static no-scheduler c1 decode lane, persistent route-window MoE, hybrid TP/EP plus hot-expert replication, XPU-native W8A8 retile/repack cache, a strict same-model 8-bit engine shootout, and upstream/bounty-quality XPU repro packets. Details: `notes/2026-06-11-qwen36-aot-localmaxxing-and-runtime-screens.md`.
- Zero-lookahead spec-placebo repair landed locally and is tracked as `patches/vllm-qwen36-spec-placebo-zero-mamba-blocks-20260611.patch`. Root cause for the row-0 block-table drift: Qwen3.6's GDN/mamba `MambaSpec.num_speculative_blocks` was still set from `speculative_config.num_speculative_tokens` even when `VLLM_XPU_SPEC_DECODE_PLACEBO=1`, so placebo reserved unused speculative mamba blocks below the scheduler. The patch forces `num_speculative_blocks=0` only for placebo mode. Patched placebo KV capacity returned to `2,052,915` tokens, matching no-spec accepted; the old placebo had `1,955,157`. New evidence: accepted async vs patched placebo no longer mismatches at row 0; first parity mismatch moves to row `26` after the first sampled-token fork. No-spec accepted with async disabled vs patched placebo passes both output parity (`baseline_match_all=true`) and model-input parity (`match_all=true`, `64` rows). New artifacts: `data/qwen36-quark-int8-tp4-accepted-modelinput-zerolookahead-p512o32-20260611a.json`, `data/qwen36-quark-int8-tp4-accepted-modelinput-zerolookahead-trace-20260611a.jsonl`, `data/qwen36-quark-int8-tp4-spec-placebo-zerolookahead-p512o32-20260611a.json`, `data/qwen36-quark-int8-tp4-spec-placebo-zerolookahead-trace-20260611a.jsonl`, `data/qwen36-quark-int8-tp4-accepted-vs-spec-placebo-zerolookahead-parity-20260611a.json`, `data/qwen36-quark-int8-tp4-accepted-vs-spec-placebo-zerolookahead-parity-20260611a.md`, `data/qwen36-quark-int8-tp4-accepted-noasync-modelinput-p512o32-20260611a.json`, `data/qwen36-quark-int8-tp4-accepted-noasync-modelinput-trace-20260611a.jsonl`, `data/qwen36-quark-int8-tp4-accepted-noasync-vs-spec-placebo-zerolookahead-parity-20260611a.json`, `data/qwen36-quark-int8-tp4-accepted-noasync-vs-spec-placebo-zerolookahead-parity-20260611a.md`. Next: use this no-async parity lane for patched oracle/perfect-draft speed upper bound, then decide whether production can move to a no-async quality-gated baseline or whether speculation must preserve async output exactly.
- Corrected graph spec-placebo tracing now has direct BlockTable evidence. Fresh accepted graph and graph spec-placebo p512/o32 runs both captured `64` model-input rows; spec-placebo still drifted `2/2` versus accepted, and the first mismatch is row `0` before any draft tokens are active: accepted attention group 0 block table is shape `[1, 1]` with row head `[1]`, while spec-placebo is `[1, 2]` with row head `[1, 2]`; groups 1/2 and GDN/mamba block IDs shift too. `scheduled_spec_decode_tokens={}`, `use_spec_decode=false`, and `spec_token_ids=[[]]` on that row, so this is speculative config/lookahead KV allocation changing verifier inputs, not proposer quality. New artifacts: `data/qwen36-quark-int8-tp4-accepted-modelinput-fresh-p512o32-20260611g.json`, `data/qwen36-quark-int8-tp4-accepted-modelinput-trace-20260611g.jsonl`, `data/qwen36-quark-int8-tp4-spec-placebo-modelinput-p512o32-20260611a.json`, `data/qwen36-quark-int8-tp4-spec-placebo-modelinput-trace-20260611a.jsonl`, `data/qwen36-quark-int8-tp4-accepted-vs-spec-placebo-modelinput-parity-20260611a.json`, and `data/qwen36-quark-int8-tp4-accepted-vs-spec-placebo-modelinput-parity-20260611a.md`. The notes now track the next repair and bigger bets: zero-lookahead placebo parity, deterministic solo KV arena, static verifier-bucket runner, auxiliary proposer API, Quark-trace-trained micro-drafter, route-window persistent MoE in `vllm-xpu-kernels`, layer-local hot-expert memory-for-latency, hybrid TP/EP simulation, whole-token Level Zero command-list runner, shape-exact XPU kernel shootout, KV-cache compression as headroom only, and an upstreamable B70 repro packet. Do not benchmark MTP/DFlash/EAGLE/n-gram/oracle speed again until accepted-vs-placebo model-input parity is exact.
- Accepted service was restored after the spec-placebo diagnostic in tmux session `qwen36-tp4-accepted-restored-after-spec-placebo-20260611a` with log `/tmp/qwen36-quark-int8-tp4-accepted-restored-after-spec-placebo-20260611a.log`. Backend `/health`, backend `/v1/models`, direct backend `OK` chat smoke, frontdoor loopback `OK` chat smoke, and frontdoor `/status` all passed. Current operational state: backend healthy on `127.0.0.1:18080`; frontdoor healthy on `8000`; remote generation intentionally paused with loopback bypass; active `0`, queued `0`.
- Fresh accepted TP4/no-prefix/32K restore passed frontdoor repeat quality after one stale long-lived process showed copy/repeat instability. The clean accepted p512/n512 r4 baseline measured `99.43` corrected after-first output tok/s, `98.16` e2e output tok/s, and `76.45 ms` TTFT. Artifacts: `data/qwen36-quark-int8-tp4-noprefix-accepted-clean-frontdoor-quality-rerun8-20260611.json`, `data/qwen36-quark-int8-tp4-noprefix-accepted-clean-single-r4-20260611.json`, `data/qwen36-quark-int8-tp4-noprefix-accepted-restored-frontdoor-quality-rerun8-20260611.json`.
- Added an AOT census tool for generated vLLM/XPU cache files. Accepted cache counts include `1364` `vllm_all_reduce`, `1804` `int8_gemm_w8a8`, `1368` `per_token_quant_int8`, `368` `moe_forward_shared`, and `480` `gdn_attention_core` calls. Artifact: `scripts/census-qwen36-aot-ops.py`, `data/qwen36-quark-int8-tp4-noprefix-current-aot-census-20260611.json`.
- Runtime screens were quality-gated and rejected or held neutral: MoE shared-add/all-reduce custom op (`99.02` corrected tok/s), TP2 on two B70s (`91.25`), TP4 max-seqs 24 (`98.89`), `CCL_WORKER_COUNT=2` startup failure under SYCL graph recording, and `CCL_REDUCE_SCATTER_MONOLITHIC_KERNEL=1` (`99.36`). No candidate beat the clean accepted baseline. Artifacts and notes: `notes/2026-06-11-qwen36-aot-localmaxxing-and-runtime-screens.md`, `patches/vllm-qwen36-moe-shared-add-allreduce-customop-rejected-20260611.patch`, `scripts/launch-qwen36-quark-int8-tp2-experimental.sh`.
- Localmaxxing public intake initially found `0` exact rows for `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`; after a dry run, the best clean quality-gated TP4 result was submitted and approved as `cmq8yhxvo001ipb0149aoa79o` with `99.43` tok/s output, `76.45 ms` TTFT, and `196.33` total tok/s. B70/Qwen comparables include llama.cpp Q4_K_M at `70.35 tok/s` on one B70 and `68.8 tok/s` four-card independent-slot aggregate. Artifacts: `data/localmaxxing-b70-qwen-leaderboard-refresh-20260611.json`, `data/localmaxxing-qwen36-quark-w8a8-int8-refresh-20260611.json`, `data/localmaxxing-qwen36-quark-w8a8-int8-tp4-noprefix-p512n512-20260611.payload.json`, `data/localmaxxing-qwen36-quark-w8a8-int8-tp4-noprefix-p512n512-20260611.response.json`, `data/localmaxxing-qwen36-quark-w8a8-int8-after-submit-20260611.json`.
- Next/bolder ideas were expanded in the Qwen note: stronger publish-grade r8/r10 plus peak VRAM capture, graph-census-first candidate rejection, exact dense quant/GEMM/all-reduce microbenches, GDN projection fusion, lower-level MoE epilogue/finalize work, TP rank-order tests, verifier-preserving Qwen3.6 draft/MTP speculation, hybrid expert-parallel layout, two-TP2 production aggregate replicas, persistent INT8 repack cache, decode-only fused layer boundaries, same-model 8-bit engine bakeoff, reversible root-level host policy tests, and upstreamable XPU backend repros. The highest-priority bigger bet is now explicit: repair/spec-test verifier-preserving speculation first, because it is the only current path that plausibly reaches a 2x single-request speedup without changing final output quality.
- Step-timing follow-up backlog was added after the graph/eager timing pass and public leaderboard refresh. The near-term ordered work is route-exact primitive MoE timing, endpoint-gating the `m32` grouped-GEMM policy, request-window timing reset, graph-visible MoE/XPU event profiling, a BF16 fallback quality comparator, and a direct c1 runner. The larger tracked bets are verifier-preserving MTP/DFlash/proposer work, persistent XPU W8A8 MoE, MoE prepare/finalize replacement, route-hot expert replication, hybrid TP/EP, B70-native W8A8 retile cache, decode command-list capture, overlapped all-reduce scheduling, same-model 8-bit engine bakeoff, and short-context latency slots. Artifacts: `notes/2026-06-11-qwen36-aot-localmaxxing-and-runtime-screens.md`, `data/localmaxxing-qwen36-quark-w8a8-int8-exact-refresh-20260611b.json`, `data/localmaxxing-arc-b70-qwen-top-refresh-20260611b.json`, `data/localmaxxing-30b-moe-top-refresh-20260611b.json`.
- The next-round ideas/backlog were expanded again with larger no-quality-loss options: a single-request direct graph runner, TP2-first layout with replicated hot dense work, layer-local expert replication, persistent route scratch, route-aware grouped-GEMM autotuning, borrowing OpenVINO/oneDNN/ITREX kernel ideas, full decode command-list capture, exact speculative draft lanes, an end-to-end kernel timeline budget, and quality-equivalent production service classes. The primitive MoE harness now times `rows_per_expert.zero_()` and `act_output.contiguous()` separately. Routecapture6 layers 9/14/21 raw and hotpack scans passed exact parity (`max_abs_diff=0.0`); hotpack was mixed at rows=1 and better at rows=16, with layer21 rows=16 improving `-20.39%` total and `-14.64%` preallocated total. Treat the primitive component sums as relative candidate evidence, not endpoint wall-clock truth. Artifacts: `data/qwen36-quark-int8-moe-routecapture6-primitive-plus-component-summary-20260611b.json`, `data/qwen36-quark-int8-moe-routecapture6-layer9-primitive-r15-20260611b.json`, `data/qwen36-quark-int8-moe-routecapture6-layer14-primitive-r15-20260611b.json`, `data/qwen36-quark-int8-moe-routecapture6-layer21-primitive-r15-20260611b.json`. The accepted TP4 server was restored in tmux session `qwen36-tp4-accepted-restored-after-primitive-timing-20260611e`; backend and frontdoor health passed, and a backend completion smoke succeeded.
- Added a Qwen3.6-specific offline `vllm.LLM` c1 runner mirroring the accepted TP4/Quark/32K/no-prefix posture. The p512/o512/c1 r4 run measured `96.56` mean output tok/s (`91.71` min, `98.35` max) and `193.12` total tok/s after one compile-polluted warmup, so in-process vLLM is not materially faster than the accepted backend/frontdoor path. Conclusion: HTTP/SSE/frontdoor are not hiding a `2x` win; keep attacking model-core/runtime or exact verifier-preserving speculation. Artifact: `data/qwen36-quark-int8-tp4-offline-c1-p512o512-r4-20260611.json`, script: `scripts/run-qwen36-offline-warm-throughput.py`. The offline run is not a quality proof because token hashes varied across temperature-0 repeats. The first accepted restore after offline init/teardown hit `UR_RESULT_ERROR_DEVICE_LOST` on the first completion despite `/health`; a clean retry restore in tmux session `qwen36-tp4-accepted-restored-after-offline-c1-retry-20260611g` passed backend generation and frontdoor health.
- Speculation tracing was added before another n-gram promotion attempt. The current Quark verifier has `0` `mtp` keys in its safetensors index, while the official FP8 snapshot has `1561`, so in-checkpoint MTP is not available for the current model. Added `scripts/qwen36-quality-token-trace.py`, `scripts/launch-qwen36-quark-int8-ngram5-trace.sh`, and the opt-in scheduler trace patch `patches/vllm-qwen36-spec-decode-jsonl-trace-20260611.patch`. The accepted frontdoor trace matched the accepted quality baseline exactly across output token IDs, including four repeat-color runs and the 8K needle case. Artifact: `data/qwen36-quark-int8-accepted-frontdoor-token-trace-20260611.json`. Next speculation work should launch n-gram with `VLLM_SPEC_DECODE_TRACE_FILE` and compare token-level divergence against this accepted trace.
- Added a post-offline no-quality-loss idea backlog. Immediate next work is to summarize existing n-gram2/cg3 prompt-class traces, add request-id correlation to speculative/client token traces, add a strict no-bonus-token speculative debug mode, replay verifier-only shadow decodes on failures, and build a graph-visible per-token timing budget. Bigger bets now tracked: exact sidecar draft speculation, persistent fused MoE decode kernels, hybrid TP/expert-parallel layout, a single-request static decode lane, B70-specific W8A8 kernel borrowing/upstreaming, route-aware prefetch/scratch persistence, same-quality engine bakeoffs, and a production latency lane with automatic baseline fallback. The priority remains speculation repair first, graph-visible timing second, and route-exact MoE microbenches as candidate generation only.
- Added `scripts/summarize-qwen36-spec-trace.py` and summarized the existing n-gram2/cg3 traces. Base synthetic n-gram2/cg3 acceptance was high (`76.48%`, max full-accept streak 147), but chat prompt-class acceptance collapsed to about `46%`. Seeded prompt-class speed versus accepted was negative for natural chat (`-8.77%`), code (`-5.91%`), and math (`-1.02%`); structured showed `+17.01%` only because n-gram2 stopped early at 440/445 output tokens instead of 512, so it is not a valid win. The deterministic quality suite remained clean (`pass_all=true`, `baseline_match_all=true`, repeat64 pass, long-context pass), but n-gram2/cg3 is rejected as a production/Localmaxxing speed candidate. Artifacts: `data/qwen36-quark-int8-tp4-ngram2-cg3-spec-summary-20260611.json`, `data/qwen36-quark-int8-tp4-ngram2-cg3-spec-summary-20260611.md`. Next speculation work should not be blind width sweeps; add request-id correlation plus strict no-bonus-token debug mode, then rerun prompt-class measurements with exact trace joins.
- Added an opt-in speculative no-bonus debug hook in the local vLLM scheduler and tracked it as `patches/vllm-qwen36-spec-decode-no-bonus-debug-20260611.patch`. The new env flag `VLLM_XPU_SPEC_DECODE_DISABLE_FULL_ACCEPT_BONUS=1` trims the extra emitted token only on full-accept speculative rows; partial-rejection rows still emit the verifier replacement token. `scripts/launch-qwen36-quark-int8-ngram-trace.sh` exposes this as `DISABLE_FULL_ACCEPT_BONUS=1`, and the spec summarizer now reports `suppressed_bonus_rows`. Validation passed: scheduler/summarizer `py_compile`, launcher `bash -n`, and patch `git apply --reverse --check` against the current local vLLM tree. This is not promoted; next diagnostic run should test n-gram5 with this flag plus request-id-aware prompt-class metrics, repeat64, and long-context parity.
- Added another ideas/backlog addendum focused on larger no-quality-loss paths. Near-term items now include a speculative correctness replay harness, request-id exact joins across client/scheduler traces, reduced-context MTP sidecar feasibility, live router-distribution capture, token-time budgeting, and a publish-grade accepted r10/r20 pack with peak VRAM. Larger bets tracked: full verifier-preserving speculation ladder, layer-local expert replication, hybrid TP/EP serving, persistent command-list decode, persistent fused MoE with real routing, tile-native W8A8 repack cache, tiny collective specialization/overlap, final projection/sampling audit, same-model 8-bit engine bakeoff, version/host stability matrix, upstreamable B70 repro package, and production dual-lane design. Priority after the current diagnostic: finish n-gram5 no-bonus quality gates, then either build the replay/MTP path if corruption clears or stop n-gram width sweeps and trace proposer/request state if it does not.
- N-gram5 with the no-bonus diagnostic hook is rejected before repeat64/speed. Short token-trace canaries matched the accepted baseline, but the long-context needle diverged: accepted `B70_QWEN36_NEEDLE_20260609`, no-bonus n-gram5 returned `B70_QWEN36!`. The scheduler trace shows a full-accept row emitted `_Q W EN 3 6` while suppressing bonus token `83098` (`_NEED`), followed by a full-reject row that emitted token `0` (`!`). Summary: no-bonus did not fix n-gram5; it exposed verifier/proposer state misalignment after full-accept suppression. Artifacts: `data/qwen36-quark-int8-tp4-ngram5-nobonus-frontdoor-token-trace-20260611.json`, `data/qwen36-quark-int8-tp4-ngram5-nobonus-spec-jsonl-20260611.jsonl`, `data/qwen36-quark-int8-tp4-ngram5-nobonus-spec-summary-20260611.json`, `data/qwen36-quark-int8-tp4-ngram5-nobonus-spec-summary-20260611.md`. The accepted recipe was restored in tmux session `qwen36-tp4-accepted-restored-after-ngram5-nobonus-20260611i`; backend `/health`, backend generation, frontdoor `/health`, and frontdoor exact `OK` chat smoke passed. Next: build a speculative replay harness from this four-row fixture and add request IDs/timestamps to token traces before any more speculation work.
- Added `scripts/replay-qwen36-spec-trace.py` and updated `scripts/qwen36-quality-token-trace.py` so token traces now record `response_id`, `request_id`, request start/finish timestamps, and selected response headers. Also fixed a repeat-comparison bug: repeated cases now compare as `repeat_colors[0]`, `repeat_colors[1]`, etc.; previously later repeats could overwrite an earlier bad repeat. Replaying the n-gram5 no-bonus fixture reports `1` suppressed follow-up mismatch: suppressed token `83098` (`_NEED`) was followed by verifier token `0` (`!`) instead of replaying `_NEED`. A fresh accepted frontdoor request-id trace with repeat-runs 4 passed exact baseline parity across all `9` cases and all cases have request IDs. Artifacts: `data/qwen36-quark-int8-tp4-ngram5-nobonus-spec-replay-20260611.json`, `data/qwen36-quark-int8-tp4-ngram5-nobonus-spec-replay-20260611.md`, `data/qwen36-quark-int8-accepted-frontdoor-token-trace-requestids-r4-20260611.json`. Future speculative tests must use request-id-capable token traces and replay to zero suppressed follow-up mismatches before speed claims.
- Added a follow-up ideas addendum after the replay harness. Immediate next items are a speculative scheduler state audit, request-id joined failure packs, verifier-only shadow retries, graph-bucket tracing for speculative decode lengths, and a per-token timing budget. Larger no-quality-loss bets now explicitly tracked include Quark-verifier MTP sidecars, adaptive n-gram2 only as a diagnostic/request-class lane, real-router grouped-GEMM tuning, persistent MoE coverage against current Intel XPU branches, a true 8-bit engine bakeoff, static solo decode, whole-token command-list capture, hybrid TP/EP with expert locality simulation, layer-local expert replication, XPU-native packed weights, persistent route scratch, collective overlap, a trained same-tokenizer proposer, a reusable production quality oracle, and an upstream-first B70 repro packet. Updated priority: inspect speculative scheduler/proposer state first, collect route histograms and token timing in parallel, then choose between verifier-preserving MTP/draft speculation and persistent MoE/layout work based on evidence. Details: `notes/2026-06-11-qwen36-aot-localmaxxing-and-runtime-screens.md`.
- Added local vLLM speculative state trace instrumentation and tracked it as `patches/vllm-qwen36-spec-state-trace-20260611.patch`. The opt-in scheduler trace now records request counters before reject rollback, after reject rollback, and after output append/stop trimming, plus scheduled-token counts and emitted-token-after-stop fields. `scripts/replay-qwen36-spec-trace.py` now renders counter-transition tables for new traces, and `scripts/summarize-qwen36-spec-trace.py` understands both legacy and nested state counters. Validation passed: scheduler/replay/summarizer `py_compile`, replay compatibility on the old n-gram5 no-bonus fixture still reports `1` suppressed follow-up mismatch, and summary compatibility reports `50.00%` acceptance over `4` rows / `3` requests. Next diagnostic run should collect request-id-capable client traces plus the enriched scheduler JSONL before any more n-gram width or speed claims.
- The enriched n-gram5/no-bonus state diagnostic reproduced the long-context divergence: accepted `B70_QWEN36_NEEDLE_20260609`, diagnostic `B70_QWEN36!`. Replay again found `1` suppressed follow-up mismatch: token `83098` (`_NEED`) was suppressed, then the next verifier token was `0` (`!`). The counter table shows a full-accept row with `5` visible tokens followed by a full-reject row rolling computed state back by `5` while emitting one wrong token, so the no-bonus hook is formally rejected. Artifacts: `data/qwen36-quark-int8-tp4-ngram5-nobonus-state-frontdoor-token-trace-20260611.json`, `data/qwen36-quark-int8-tp4-ngram5-nobonus-state-spec-jsonl-20260611.jsonl`, `data/qwen36-quark-int8-tp4-ngram5-nobonus-state-spec-replay-20260611.md`, `data/qwen36-quark-int8-tp4-ngram5-nobonus-state-spec-summary-20260611.md`. The notes now include an expanded bigger-bets backlog: prefix-aware trace joining, verifier-only replay, recompute-after-suppressed-bonus diagnostics, shallow MTP sidecar with Quark verifier, verifier-bucket graph optimization, real-router histogram capture, persistent MoE/grouped-GEMM work, memory-for-latency lanes, whole-token command-list capture, exact 8-bit engine shootout, and upstreamable B70/XPU repro packets.
- Prefix-aware trace joining is now implemented in `scripts/replay-qwen36-spec-trace.py` and `scripts/summarize-qwen36-spec-trace.py`. Client request IDs such as `chatcmpl-910ade65c5503c90` now join to scheduler IDs such as `chatcmpl-910ade65c5503c90-a467094e`; the regenerated state replay reports `joined_requests=3`, and the bad scheduler request is directly labeled `long_context_needle (scheduler_prefix)`. Summary joinability now reports `0` exact matches, `3` prefix matches, and timestamp joinability. Validation passed: trace tooling `py_compile`, state replay/summary regeneration, and old no-bonus fixture compatibility still reports `1` suppressed follow-up mismatch without a token-trace artifact. This removes ambiguity from the speculative-state diagnosis and makes the next step a verifier-only replay/recompute diagnostic or a move to shallow MTP sidecar work.
- Prompt-class route hotpack overlap was added from the existing route-capture artifacts without disturbing the accepted service. For the highest-signal layers 8/9/14/20/21, global K16 hotpacking covers only `40-44%` of weighted expert assignments; prompt/label-specific K16 improves this to `49-51%`; K32 reaches about `68-72%`; K64 reaches about `88-90%`. Conclusion: a single global hotpack is too blunt, route buckets are useful scheduling signal, and the credible backend path is persistent/fused MoE or memory-for-latency placement using real route distributions, not more static pack knobs. New artifacts: `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-hotpack-overlap.json`, `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-hotpack-overlap.md`. The notes also add bigger things to try: balanced natural-chat recapture, K32/K64 memory math, route-window persistent MoE, verifier-bucket speculation, TP/EP layout simulation, whole-token command-list capture, exact 8-bit engine bakeoff, and an upstreamable B70/XPU repro packet.
- The no-bonus speculative accounting diagnostic now has a focused scheduler regression and replay accounting checks. The old no-bonus state fixture reports `accounting_mismatch_count=2`, proving the previous diagnostic hid a bonus token while still counting it as committed; the patched live n-gram5/no-bonus/accounting trace reports `accounting_mismatch_count=0`. Quality still fails on long-context: accepted `B70_QWEN36_NEEDLE_20260609`, diagnostic `B70_QWEN36_NEEDLE_2020609`, with suppressed token `21` followed by verifier token `15`. Decision: n-gram5/no-bonus remains rejected; the old accounting bug is fixed, but the remaining issue is deeper verifier/proposer state or multi-token verification behavior. The accepted TP4 service was restored in `qwen36-tp4-accepted-restored-after-nobonus-accounting-20260611m` and passed backend/frontdoor health plus the frontdoor text quality canary. New artifacts: `scripts/check-qwen36-spec-no-bonus-state.py`, `patches/vllm-qwen36-spec-no-bonus-accounting-20260611.patch`, `data/qwen36-quark-int8-tp4-ngram5-nobonus-accounting-frontdoor-token-trace-20260611.json`, `data/qwen36-quark-int8-tp4-ngram5-nobonus-accounting-spec-replay-20260611.md`, `data/qwen36-quark-int8-tp4-accepted-restored-after-nobonus-accounting-text-smoke-20260611.json`. The notes now add the next bigger things to try: verifier-only recompute probes, minimal real-trace scheduler fixtures, verifier-bucket timing, shallow MTP sidecars with Quark verification, dual-lane production routing, token-level flight recording, one-token roofline snapshots, persistent MoE with real route windows, memory-for-latency mode, whole-token command-list replay, same-model 8-bit engine bakeoff, and upstreamable B70 repro packets.
- Added `scripts/probe-qwen36-verifier-followup.py` to replay suppressed-bonus mismatches against the accepted verifier via `/generative_scoring`. On the n-gram5/no-bonus/accounting long-context failure, the visible prefix was `B70_QWEN36_NEEDLE_202`; the accepted verifier scored the suppressed token `21` (`6`) at `0.9999974387` versus the wrong next token `15` (`0`) at `0.0000022603`. Conclusion: the remaining no-bonus failure is not verifier model math; it is hidden KV/proposer/scheduler state contamination after suppressing a verified bonus token. Artifact: `data/qwen36-quark-int8-tp4-ngram5-nobonus-accounting-verifier-followup-probe-20260611.json`.
- Standard n-gram5 with the full verifier bonus intact reached backend health and completed graph capture, but the first frontdoor quality request crashed the backend with `UR_RESULT_ERROR_DEVICE_LOST` during `block_table.copy_to_gpu` on the initial prefill (`prompt_token_ids_len=17`, `scheduled_spec_decode_tokens={}`, `step_counter=0`). No quality or speed result is valid; reject this graph/spec path for stability. Artifact: `data/qwen36-quark-int8-tp4-ngram5-standard-device-lost-20260611.json`. The accepted TP4 service was restored in `qwen36-tp4-accepted-restored-after-ngram5-standard-dl-20260611o`; backend/frontdoor health passed, and the frontdoor text quality canary passed with `pass_all=true`. Restore artifact: `data/qwen36-quark-int8-tp4-accepted-restored-after-ngram5-standard-dl-text-smoke-20260611.json`. The notes now add larger follow-up ideas: make bonus-intact speculation stable before timing it, treat bonus suppression as requiring real KV/proposer rewind, build a static solo decode lane that bypasses scheduler/block-table churn, test EAGLE/EAGLE3 or a trained Qwen3.6-family draft only behind the Quark verifier, spend spare VRAM on memory-for-latency profiles, and package B70/XPU repros for upstream help.
- Added a `/generative_scoring` item-length timing proxy. p512 scoring was flat around `75-80 ms` for item lengths 0-16, while p8192 scoring measured item0 at `726.72 ms` and small items at about `+12` to `+31 ms`. This is stable but not a true speculative decode verifier bucket because the endpoint recomputes prompt+item prefill. Decision: do not use HTTP scoring to predict MTP/EAGLE speed; build a lower-level KV-resident verifier-bucket harness next. Fresh accepted c1 sanity remains normal at `99.31` corrected after-first tok/s and `96.46` e2e p512/o256. Backend/frontdoor health and a post-probe frontdoor text smoke passed with `pass_all=true`. New artifacts: `scripts/probe-qwen36-generative-scoring-buckets.py`, `data/qwen36-quark-int8-tp4-generative-scoring-buckets-p512-20260611.json`, `data/qwen36-quark-int8-tp4-generative-scoring-buckets-p8192-20260611.json`, `data/qwen36-quark-int8-tp4-current-speed-sanity-p512o256-r2-20260611.json`, `data/qwen36-quark-int8-tp4-post-scoring-bucket-text-smoke-20260611.json`.
- Refreshed the idea backlog after Localmaxxing and upstream-signal scans. Fresh B70/Qwen leaderboard snapshots put the current Quark W8A8 INT8 TP4 rows at `99.77` and `99.43` tok/s, ahead of public B70 llama.cpp Q4 rows around `68-70` tok/s; broader Qwen rows reinforce DFlash/DDTree-style verifier-preserving speculation as the main visible route to large single-user gains. New tracked opportunities: real KV-resident decode-bucket timing, verifier-only replay, bonus-intact speculation stability isolation, shallow draft/MTP/EAGLE/DFlash behind the Quark verifier, latest XPU branch comparison, memory-for-latency expert replication, persistent route-window MoE, static solo decode, whole-token Level Zero command-list capture, oneDNN/BRGEMM MoE experiments, communication-avoidance layouts, exact final-logits shortcuts, true 8-bit engine bakeoff, production dual-lane routing, and an upstream-first B70 repro packet. Artifacts: `data/localmaxxing-b70-qwen-leaderboard-ideas-refresh-20260611.json`, `data/localmaxxing-arc-qwen-leaderboard-ideas-refresh-20260611.json`; details: `notes/2026-06-11-qwen36-aot-localmaxxing-and-runtime-screens.md`.
- Added a larger post-oracle backlog. Immediate reliability items are dynamic frontdoor pause/drain, a localhost-only quality lane, and post-restore repeat token flight recording. The next correctness items are a `k=1` speculative verifier-state minimizer, verifier-only single-step replay, and exact top-k/logit checksums. Bigger speed bets now tracked include verifier-preserving speculation ladder, FP8 MTP sidecar behind the Quark verifier, speculative scheduler/version bisect, hybrid TP/EP memory-for-latency lane, persistent route-window MoE, whole-token command-list capture, same-quality XPU 8-bit engine shootout, static solo-decode service class, expert-hotset VRAM trade study, upstreamable B70 repro packet, and a Localmaxxing race harness. Priority is to isolate quality first, fix/prove `k=1` speculation second, then choose between repaired speculation and persistent MoE/static decode work. Details: `notes/2026-06-11-qwen36-aot-localmaxxing-and-runtime-screens.md`.
- Implemented dynamic frontdoor pause/drain and a localhost-only quality lane. `scripts/openai-lan-frontdoor.py` now keeps serving status while paused, reports pause/drain/default-request fields, rejects new generation with HTTP `503`/`frontdoor_paused`, and exposes `/drain` plus `/frontdoor/drain`. `scripts/run-qwen36-local-quality-frontdoor.sh` binds the same no-thinking/model-rewrite defaults to `127.0.0.1:18082` with max-active `1`. Validation passed `py_compile`, `bash -n`, local status, dynamic pause rejection without queueing, and drain. Two local short quality canaries confirmed the current backend restore is still not quality-clean: first failed arithmetic (`58` vs `60`) while repeat passed; second passed arithmetic but failed repeat with unrelated text. Artifacts: `data/qwen36-quark-int8-tp4-local-quality-frontdoor-text-smoke-20260611.json`, `data/qwen36-quark-int8-tp4-local-quality-frontdoor-text-smoke-rerun-20260611.json`. Next: clean accepted-backend restore, then local quality lane, then public frontdoor quality before more speed work.
- Public frontdoor was restarted under the new dynamic-pause code and left paused via `/tmp/qwen36-35b-a3b-fp8-requant-frontdoor-not-paused`; paused public generation returns HTTP `503`/`frontdoor_paused` and does not increment generation counters. Two clean graph restore attempts (`qwen36-tp4-accepted-clean-restore-after-frontdoor-pause-20260611b`, retry2 `...20260611c`) reached `/health` but both device-losted on the first local quality-lane generation at `block_table.copy_to_gpu` with `speculative_config=None`, `prompt_token_ids_len=17`, and `step_counter=0`. An eager/no-graph fallback (`qwen36-tp4-eager-fallback-paused-20260611d`) stays alive but fails exact arithmetic twice (`58` vs `60`) while repeat stability passes. Current safety state: public frontdoor remains paused; eager fallback is alive on `127.0.0.1:18080` but is not quality-clean and should not be treated as production. New artifacts: `data/qwen36-quark-int8-tp4-eagerfallback-local-quality-frontdoor-text-smoke-r8-20260611.json`, `data/qwen36-quark-int8-tp4-eagerfallback-local-quality-frontdoor-text-smoke-rerun-r8-20260611.json`. Next: debug first-generation graph device-lost, likely stale Level Zero/oneCCL state, block-table/NHD KV copy path, graph cache corruption, local vLLM instrumentation regression, or need for XPU device reset after repeated device-losts.
- Fresh graph cache restore recovered quality. A new accepted graph cache root (`/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-freshrestore-20260611d`) reached health and passed the localhost quality lane: short r8 and full r8, including repeat stability and long-context needle, both `pass_all=true` / `baseline_match_all=true`. The first unpaused public-frontdoor full r8 failed arithmetic (`58` vs expected `60`) while external `10.0.0.214` traffic was interleaved, so public promotion now uses a paused-local gate. `scripts/openai-lan-frontdoor.py` now supports `FRONTDOOR_PAUSE_ALLOW_LOCAL=1`: remote generation stays `503` while loopback canaries can pass through the actual port `8000` route. The paused-local public full r8 passed (`pass_all=true`, `baseline_match_all=true`), the temporary local quality lane was stopped, and the public frontdoor was unpaused with backend `/health` returning HTTP `200`. New artifacts: `data/qwen36-quark-int8-tp4-freshcache-local-quality-frontdoor-text-smoke-r8-20260611.json`, `data/qwen36-quark-int8-tp4-freshcache-local-quality-frontdoor-full-r8-20260611.json`, `data/qwen36-quark-int8-tp4-freshcache-public-frontdoor-full-r8-20260611.json`, `data/qwen36-quark-int8-tp4-freshcache-public-frontdoor-pausedlocal-full-r8-20260611.json`, `data/localmaxxing-qwen36-quark-b70-pausedlocal-refresh-20260611.json`, `data/localmaxxing-qwen-b70-vllm-pausedlocal-refresh-20260611.json`. Next/bigger ideas added to the detailed note: content-addressed graph-cache discipline, resident block-table/KV-slot precommit, static c1 decode lane, persistent zero-gap MoE, route-bucket expert replication, verifier-only speculation repair, learned same-tokenizer proposer, strict 8-bit engine shootout, host-stack/BOM A/B tests, dual-lane production routing, and upstreamable B70 repro packs.
- Added `scripts/reduce-qwen36-oracle-fixture.py` to turn accepted-vs-oracle completion artifacts into a compact token-parity fixture. The current oracle `k=1` short graph probe fails `2/2` cases even though the scheduler accepted `14/15` draft tokens (`93.33%`). The reducer maps first diffs back to scheduler rows: `natural_latency_plan` diverges on a `verifier_bonus_after_full_accept` row (`reliability` expected, `memory` emitted), while `repetitive_kernel_notes` diverges on a `replacement_after_reject` row (`hardware` expected, `decode` emitted). This narrows the speculation blocker to multi-token verifier/GDN/KV state equivalence, not draft quality alone. New artifacts: `data/qwen36-quark-int8-tp4-oracle-k1-drift-fixture-20260611.json`, `data/qwen36-quark-int8-tp4-oracle-k1-drift-fixture-20260611.md`, `data/qwen36-quark-int8-tp4-oracle-k1-drift-replay-20260611.json`, `data/qwen36-quark-int8-tp4-oracle-k1-drift-replay-20260611.md`, `data/localmaxxing-qwen36-30b-top-continue-20260611.json`. Next speculation work must make this fixture exact before DFlash/MTP/ngram speed tests; non-spec work should continue in parallel on static c1 and persistent MoE. The detailed note now also tracks bigger bets: serial-fallback-inside-spec diagnostics, state fingerprints, first-class auxiliary proposer API, Quark-trace-trained proposers, self-speculative shallow verifier branches, memory-for-latency hot expert copies, hybrid TP/EP simulation, whole-token Level Zero command-list replay, latest-stack 8-bit engine shootout, an Intel-validated BOM boot test, and upstreamable B70 repro packets.
- Added `scripts/check-qwen36-oracle-fixture.py` as an executable gate around the reduced oracle fixture. Current known-drift mode passes only if the fixture still has `2` mapped mismatches with roles `verifier_bonus_after_full_accept` and `replacement_after_reject`, replay accounting remains clean, and all requests join. Future repaired speculation must pass the same checker in default exact mode. Also added the next opt-in vLLM scheduler diagnostic patch, `patches/vllm-qwen36-spec-ignore-drafts-diagnostic-20260611.patch`, and launcher support via `IGNORE_DRAFTS=1`. The new env `VLLM_XPU_SPEC_DECODE_IGNORE_DRAFTS=1` keeps speculative config/proposer plumbing alive but forces the scheduler to feed only the normal verifier token, separating scheduler/config side effects from actual speculative token execution and commit/rollback behavior. Validation passed `py_compile`, launcher `bash -n`, known-drift fixture gate, scheduler `py_compile`, and patch reverse-check against the local vLLM tree. The isolated run is not yet executed because the accepted TP4 public service is live; run it in a paused/isolated window before further speculation speed work.
- Ran the isolated `IGNORE_DRAFTS=1` oracle `k=1` graph diagnostic. Procedure: paused public frontdoor, drained active traffic, stopped the accepted backend, launched the diagnostic on `127.0.0.1:18081` with a fresh cache root, captured two p512/o32 oracle completions, then restored the accepted fresh-cache backend on `18080`. Result: no scheduler spec trace file was produced, confirming draft tokens were not fed to the verifier, while the oracle draft log recorded `256` rows with `188` matches. Output parity improved from `2/2` drift to `1/2` drift: `natural_latency_plan` matched exactly, but `repetitive_kernel_notes` still diverged at output index `15` (`hardware` expected, `decode` emitted). Conclusion: the remaining blocker is upstream of commit/rollback of executed draft tokens; speculative config/proposer/graph plumbing can perturb at least one decode path even when drafts are ignored. Accepted service restoration passed paused-local public full r8 with `pass_all=true` and `baseline_match_all=true`, then the frontdoor was unpaused with backend health `200`. New artifacts: `data/qwen36-quark-int8-tp4-oracle1-ignore-drafts-graph-completions-20260611.json`, `data/qwen36-quark-int8-tp4-oracle1-ignore-drafts-drift-fixture-20260611.json`, `data/qwen36-quark-int8-tp4-oracle1-ignore-drafts-drift-fixture-20260611.md`, `data/qwen36-quark-int8-tp4-oracle1-ignore-drafts-draft-20260611.jsonl`, `data/qwen36-quark-int8-tp4-restored-after-ignore-drafts-public-frontdoor-pausedlocal-full-r8-20260611.json`. Next isolation branch: compare spec-config/no-draft graph vs eager and spec-config/no-proposer graph, then inspect model-runner graph inputs for differences when `speculative_config` is present but `scheduled_spec_decode_tokens` is empty.
- Added a post-`IGNORE_DRAFTS=1` bigger-bets addendum. New tracked items: `IGNORE_DRAFTS=1` eager A/B, spec-config placebo mode, first-row model-runner tensor diff, real-router distribution capture, `vllm-xpu-kernels` shape lab, static batch-1 decode-core runner, peak-VRAM/headroom pack, first-class auxiliary proposer API, verifier-bucket graph specialization, persistent route-window MoE, tile-native W8A8 repack cache, memory-for-latency service classes, hybrid TP/EP simulation, end-to-end XPU timeline budget, strict 8-bit engine shootout, and upstreamable B70 repro bundles. Fresh source sweep points to `vllm-xpu-kernels`, vLLM XPU supported-model docs, vLLM speculative decoding docs, Intel grouped-GEMM routing-skew issue, vLLM W8A8 docs, and Intel XPU INT8 fusion docs. Priority remains: fix/isolate spec-mode verifier drift first, capture real routes and shape labs in parallel, rerun accepted r8/r10 plus peak VRAM after service restores, then benchmark proposer/MTP only after exact parity.
- Ran the eager `IGNORE_DRAFTS=1` oracle `k=1` control plus a no-spec eager accepted control. Eager `IGNORE_DRAFTS=1` reached `/health`, produced no scheduler spec trace, and logged `256` oracle-draft rows with `128` matches, but still drifted `2/2` versus the graph accepted baseline. The no-spec eager accepted control also drifted `2/2` with the same first diffs, and its outputs were exactly identical to eager `IGNORE_DRAFTS=1` for both prompts. Conclusion: eager mode itself differs from the graph accepted baseline, so eager is not a valid isolator for the remaining graph spec drift; in eager mode, speculative config plus ignored drafts adds no extra observable drift on this fixture. Accepted graph service was restored in `qwen36-tp4-accepted-restored-after-eager-control-20260611a`; paused-local public full r8 passed with `pass_all=true` and `baseline_match_all=true`, then the frontdoor was unpaused with backend health `200`. New artifacts: `data/qwen36-quark-int8-tp4-oracle1-ignore-drafts-eager-completions-20260611.json`, `data/qwen36-quark-int8-tp4-oracle1-ignore-drafts-eager-drift-fixture-20260611.json`, `data/qwen36-quark-int8-tp4-oracle1-ignore-drafts-eager-drift-fixture-20260611.md`, `data/qwen36-quark-int8-tp4-oracle1-ignore-drafts-eager-draft-20260611.jsonl`, `data/qwen36-quark-int8-tp4-accepted-eager-control-completions-20260611.json`, `data/qwen36-quark-int8-tp4-accepted-eager-control-drift-fixture-20260611.json`, `data/qwen36-quark-int8-tp4-accepted-eager-control-drift-fixture-20260611.md`, `data/qwen36-quark-int8-tp4-restored-after-eager-control-public-frontdoor-pausedlocal-full-r8-20260611.json`. Next: graph-mode spec-placebo plus first-row model-runner metadata diff.
- Added another bolder-ideas addendum after model-input parity and the ignore-drafts/eager controls. New tracked branches: service-health restore checklist, deterministic KV/block-table arena for solo decode, static model-input parity as the first speculation gate, post-parity perfect-draft upper bound, multi-column verifier graph buckets, Quark-compatible MTP sidecar, learned B70-native micro-drafter, route-to-kernel compiler, hot-expert memory-for-latency mode, hybrid TP/EP simulator, whole-token Level Zero command-list runner, direct `vllm-xpu-kernels` W8A8 shape work, exact 8-bit engine shootout, reliability scoreboard, and an upstream/bounty-style B70 repro packet. Priority remains graph-mode spec-placebo plus model-runner input diff first; real-router histograms and token timing can proceed in parallel because they do not depend on speculative correctness.
- Reliability restore after the roadmap update: a health check found frontdoor `502` and no `18080` listener. The prior backend had died after a remote large structured-output request (`prompt_token_ids_len=5907`, `max_tokens=2048`, `json_object=True`) timed out in `sample_tokens`, leaving stale workers. Remote generation was paused via `/tmp/qwen36-35b-a3b-fp8-requant-frontdoor-not-paused`, drained to active `0`/queued `0`, stale backend workers were removed, and the accepted backend was relaunched in `qwen36-tp4-accepted-restored-after-roadmap-20260611a` from the fresh graph cache. Backend `/health`, `/v1/models`, direct `OK` chat smoke, frontdoor loopback `OK` smoke, and frontdoor `/health` all passed. Current state: backend healthy on `127.0.0.1:18080`; frontdoor healthy on `8000`; remote generation intentionally paused with loopback bypass enabled until the large structured-output crash path is guarded or routed conservatively.

Current Qwen speed-candidate result:

- Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- Hardware: 4x Intel Arc Pro B70 32GB
- Engine: local vLLM XPU TP4 plus local `vllm-xpu-kernels`
- Recipe: Quark W8A8 INT8 weights, BF16 activation/runtime dtype, 32K context, native XPU dense INT8 linear, native XPU INT8 MoE backend, XPU PIECEWISE graph capture, clone-safe custom-op all-reduce collectives, and `--no-enable-prefix-caching` for the current unique-prompt speed candidate.
- Single request: current accepted no-prefix p512/n512 streaming refresh measured `98.69` corrected output tok/s after first chunk, `97.43` output tok/s end-to-end, and mean TTFT `77.39 ms` across eight repeats. This matches the quiet-logs screen within current variance, so quiet logs is not a proven speed optimization by itself. Artifacts: `data/qwen36-quark-int8-tp4-noprefix-accepted-single-refresh2-20260610.json`, `data/qwen36-quark-int8-tp4-noprefix-graph32k-single-confirm-20260610.json`.
- Prior prefix-caching single request: `94.52` output tok/s after first chunk, `93.21` output tok/s end-to-end, mean TTFT `76.10 ms` for p512/n512 streaming completions.
- Restart refresh: after the device-lost recovery and baseline relaunch, p512/n512 streaming measured `94.31` output tok/s after first chunk, `94.13` corrected after-first, `93.00` end-to-end, and `76.46 ms` mean client TTFT across four repeats. This is within noise of the promoted single-request baseline, so the restart did not materially change the accepted recipe. Artifact: `data/qwen36-quark-int8-graph32k-single-refresh-20260610.json`.
- Aggregate reference: current no-prefix frontdoor c48 p512/n256 streaming originally measured `1700.89` output tok/s wall and `1727.50` output tok/s from first text, while a later accepted c48 refresh after many runtime restarts measured `1479.66` wall and `1495.39` from-first. Prior prefix-caching c48 measured `1604.00` wall and `1622.33` from first text. No-prefix was mixed at c16/c32 and c48 is currently restart-sensitive, so shared-prefix/cache-hit workloads still need repeated A/B before treating no-prefix as the final production default. Artifacts: `data/qwen36-quark-int8-tp4-noprefix-graph32k-concurrency-20260610.json`, `data/qwen36-quark-int8-tp4-noprefix-accepted-c48-refresh-20260610.json`.
- Quality: text exact canaries, JSON field semantics, repeat hash stability, and 8K-class long-context needle recall passed with full baseline parity through the frontdoor route. Artifact: `data/qwen36-quark-int8-tp4-noprefix-frontdoor-quality-20260610.json`.
- Restore smoke after the rejected fused-kernel experiment also passed exact canaries, JSON field semantics, repeat stability, and long-context recall.
- Primary artifacts: `notes/2026-06-09-qwen36-quark-int8-xpu-graph-custom-collectives.md`, `data/qwen36-quark-int8-graph32k-customar-20260609.json`, `data/qwen36-quark-int8-graph32k-quality-20260609.json`, `data/qwen36-quark-int8-graph32k-restore-smoke-20260609.json`, `data/qwen36-quark-int8-graph32k-concurrency-20260609.json`, `data/qwen36-quark-int8-graph32k-single-metrics-20260609.json`.
- Repro patches: `patches/vllm-qwen36-quark-w8a8-int8-xpu-graph-20260609.patch`, `patches/vllm-xpu-kernels-qwen36-quark-w8a8-int8-xpu-20260609.patch`.
- Rejected candidate: `VLLM_XPU_FUSED_MOE_FUSE_SILU_QUANT=1` sped up an isolated activation/quant microbench but failed the quality gate by returning `58` instead of `60` for the arithmetic canary. Artifact: `data/qwen36-quark-int8-graph32k-fused-siluq-quality-20260609.json`. Keep this env unset.
- MoE kernel microbench: accepted Qwen3.6-shaped INT8 MoE rows 1/2/4/8 measured `298.96/304.89/272.78/283.87 us` with exact staged-path match. The rejected fused SiLU+quant diagnostic measured `238.91/232.35/229.18/260.70 us` for the same rows but drifted from the accepted staged output and remains disabled. Artifacts: `data/qwen36-quark-int8-moe-kernels-20260609.json`, `data/qwen36-quark-int8-moe-kernels-fused-siluq-20260609.json`.
- MoE scratch diagnostic: preallocated BF16/INT32 scratch in the staged path stayed exact versus `xpu_fused_moe` and measured rows 1/2/4/8 at `210.15/206.06/206.46/240.51 us`; rows 16/32 measured `322.35/489.85 us`. This is a diagnostic, not yet a runtime promotion, because production needs a mixed-dtype workspace route for BF16 activations, INT32 routing maps, INT8 activations, and FP32 scales. Artifact: `data/qwen36-quark-int8-moe-kernels-prealloc-20260610.json`.
- Mixed-workspace runtime screen: `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1` reused BF16/INT32 MoE scratch through vLLM's workspace manager and passed the smoke quality suite, but single-request p512/n512 speed measured `93.62` corrected after-first output tok/s and `92.52` end-to-end output tok/s, below the promoted `94.52` / `93.21`. Decision: reject for now; do not enable in production. Artifacts: `data/qwen36-quark-int8-mixedws-smoke-20260610.json`, `data/qwen36-quark-int8-mixedws-single-metrics-20260610.json`.
- RMSNorm plus INT8 per-token-quant fusion screen: the direct XPU fused kernel microbench was `37-46%` faster for hidden size 2048, but the fused kernel requires BF16 weight while the live Qwen norm path uses a FP32 transformed weight, producing small quant drift in direct checks. The endpoint compiled with `VLLM_XPU_FUSE_RMS_INT8_QUANT=1`, but the actual graph still had zero `rms_norm_dynamic_per_token_quant` calls, so the pattern did not match and was not benchmarked for promotion. Decision: reject/no-op for now; baseline restored. Patch artifacts: `patches/vllm-qwen36-quark-int8-runtime-candidates-20260610.patch`, `patches/vllm-xpu-kernels-qwen36-quark-int8-runtime-candidates-20260610.patch`.
- RMSNorm plus INT8 BF16-input/FP32-weight fused-kernel follow-up: a kernel patch was added to preserve Qwen's FP32 transformed norm weight and BF16 rounding before INT8 scale/quantization, but the build/test loop failed before quality or speed validation. The full oneAPI 2026 build was killed by the OS while compiling unrelated `paged_decode_xe2.cpp`; the partial `_C` binary then hung inside `torch.ops._C.rms_norm_dynamic_per_token_quant` on a `1x2048` tensor, and the rebuilt `_xpu_C` broke `per_token_quant_int8_xpu` with `RuntimeError: Invalid argument` plus Level Zero abort. Decision: reject; do not wire this patch into graph replacement. Artifacts: `notes/2026-06-10-qwen36-rms-int8-bf16fp32-rejected.md`, `data/qwen36-quark-int8-rms-int8-bf16fp32-rejected-20260610.json`, `patches/vllm-xpu-kernels-qwen36-rms-int8-bf16-fp32-rejected-20260610.patch`.
- Build-loop improvement: direct CMake `_C`-only build was validated with oneAPI 2025.3, B70-only AOT, and all non-basic extensions disabled. It built and installed a temp `_C.abi3.so` without touching the package or compiling attention/MoE/_xpu_C targets; import smoke passed and `torch.ops._C.rms_norm_dynamic_per_token_quant` was registered. Use this for future exact fused-kernel iteration before graph replacement. Artifacts: `notes/2026-06-10-vllm-xpu-kernels-c-only-build.md`, `data/qwen36-vllm-xpu-kernels-c-only-build-20260610.json`, `scripts/build-vllm-xpu-kernels-c-only.sh`.
- Reliability incident: after the rejected local fused-kernel diagnostics, the accepted backend later hit `UR_RESULT_ERROR_DEVICE_LOST` during an external chat completion request and exited `139`. No stale workers remained, all four B70s still enumerated, and the accepted TP4 32K baseline was relaunched successfully; backend and frontdoor `/v1/models` were ready again. Future unsafe extension diagnostics should stop or isolate the serving backend first. Artifacts: `notes/2026-06-10-qwen36-device-lost-restart.md`, `data/qwen36-quark-int8-device-lost-restart-20260610.json`.
- Reliability incident: after several runtime screens and restores, the accepted no-prefix backend reached `/health` but hit `UR_RESULT_ERROR_DEVICE_LOST` on the first frontdoor smoke request. All four B70s still enumerated through `xpu-smi` and `torch.xpu`, no stale workers remained after killing the session, and a clean relaunch passed backend generation plus frontdoor chat generation. Lesson: every restore needs an actual generation smoke, not just `/health`. Artifacts: `notes/2026-06-10-qwen36-device-lost-after-runtime-screens.md`, `data/qwen36-quark-int8-device-lost-after-runtime-screens-20260610.json`.
- Runtime no-prefix win: `--no-enable-prefix-caching` improved unique-prompt single-request p512/n512 decode to `98.04` corrected after-first output tok/s and `96.77` e2e output tok/s while preserving frontdoor quality parity. It also improved c48 aggregate to `1700.89` wall / `1727.50` from-first tok/s, but c16/c32 were slightly lower. Direct-backend chat quality without frontdoor template kwargs is not a valid comparison because it emits thinking text. Artifacts: `notes/2026-06-10-qwen36-noprefix-runtime-win.md`, `data/qwen36-quark-int8-tp4-noprefix-graph32k-single-confirm-20260610.json`, `data/qwen36-quark-int8-tp4-noprefix-frontdoor-quality-20260610.json`, `data/qwen36-quark-int8-tp4-noprefix-graph32k-concurrency-20260610.json`.
- Safe in-place all-reduce screen: an opt-in vLLM XPU graph pass gated by `VLLM_XPU_EXPERIMENTAL_SAFE_INPLACE_ALLREDUCE=1` rewrote a narrow set of BF16 single-use all-reduce nodes to `all_reduce_inplace`. It passed frontdoor quality parity and improved p512/n512 single-request speed to `98.81` corrected after-first output tok/s and `97.58` e2e output tok/s, but it regressed c48 aggregate from `1700.89` wall / `1727.50` from-first tok/s to `1534.37` / `1550.78`. A capped follow-up with `VLLM_XPU_SAFE_INPLACE_ALLREDUCE_MAX_REWRITES_PER_GRAPH=1` lost the single-request gain at `97.99` corrected after-first tok/s, so it was rejected before quality/aggregate sweeps. Decision: reject as production default; keep as opt-in diagnostic for collective-boundary work. Artifacts: `notes/2026-06-10-qwen36-safe-inplace-allreduce-mixed.md`, `patches/vllm-xpu-safe-inplace-allreduce-20260610.patch`, `data/qwen36-quark-int8-tp4-noprefix-safeinplacear2-graph32k-single-20260610.json`, `data/qwen36-quark-int8-tp4-noprefix-safeinplacear2-frontdoor-quality-20260610.json`, `data/qwen36-quark-int8-tp4-noprefix-safeinplacear2-graph32k-concurrency-20260610.json`, `data/qwen36-quark-int8-tp4-noprefix-safeinplacearmax1-graph32k-single-20260610.json`.
- All-reduce graph clone-off screen: disabling only `VLLM_XPU_CUSTOM_ALLREDUCE_GRAPH_CLONE_INPUT` while keeping `VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT=1` removed graph-side clone calls in the lowered cache, but p512/n512 single-request speed was only `98.22` corrected after-first tok/s and `96.97` e2e output tok/s. Decision: reject as neutral/noise; keep the accepted graph clone guard enabled. Artifacts: `notes/2026-06-10-qwen36-allreduce-graph-clone-off-neutral.md`, `data/qwen36-quark-int8-tp4-noprefix-nographclone-graph32k-single-20260610.json`.
- N-gram speculative decoding screen: `--speculative-config {"method":"ngram","num_speculative_tokens":5,"prompt_lookup_min":2,"prompt_lookup_max":5}` accepted startup, disabled async scheduling, expanded graph capture to 51 sizes, and then stopped during XPU graph capture at `47/51` before `/health`; the tmux session disappeared and worker PIDs were gone with no explicit traceback or `EXIT` line. Decision: reject; no quality or speed numbers are valid because the endpoint never served. The accepted no-prefix runtime was restored and passed backend plus frontdoor generation smokes. Artifacts: `notes/2026-06-10-qwen36-ngram-speculative-startup-fail.md`, `data/qwen36-quark-int8-tp4-noprefix-ngram5-startup-fail-20260610.json`.
- N-gram k=1 hold-prefill follow-up: `num_speculative_tokens=1` with graph capture capped at `128` served successfully and matched the accepted baseline on exact canaries plus long-context needle through the frontdoor, but failed 64-repeat stability with three corrupt outputs (`utexile.tex...`, extra words, and wrong colors). Decision: reject; do not promote n-gram speculation until token/state contamination is fixed. Loader lesson: keep `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels` first in `LD_LIBRARY_PATH` so editable `_xpu_C` resolves stable SYCL-8 helper kernels instead of stale SYCL-9 `build/temp` helpers. Artifacts: `notes/2026-06-10-qwen36-ngram1-holdprefill-rejected.md`, `patches/vllm-qwen36-ngram1-holdprefill-rejected-20260610.patch`, `data/qwen36-quark-int8-tp4-ngram1-cg128-holdprefill-frontdoor-quality-rerun64-20260610.json`.
- Accepted restore after the k=1 rejection passed frontdoor quality parity with 32-repeat stability, then measured `99.07` corrected after-first output tok/s, `97.84` e2e output tok/s, and `74.99 ms` mean TTFT across four p512/n512 direct-backend repeats. Artifacts: `data/qwen36-quark-int8-tp4-noprefix-restore-after-ngram1-frontdoor-quality-rerun32-20260610.json`, `data/qwen36-quark-int8-tp4-noprefix-restore-after-ngram1-single-r4-20260610.json`.
- Dedup-quant clone follow-up: after registering `VLLM_XPU_DEDUP_INT8_QUANT=clone`, the XPU graph pass ran but found only `1` or `2` INT8 quant nodes per lowered graph and removed `0` duplicates. p512/n512 measured `99.19` corrected after-first tok/s, `97.10` e2e tok/s, and a `122.22 ms` mean TTFT with an outlier. Decision: reject/no-op; no quality suite because it failed the speed gate. Artifact: `data/qwen36-quark-int8-tp4-noprefix-dedupquant-clone-envregistered-single-r4-20260611.json`.
- GDN `clone-ba` follow-up: cloning only the `ba` consumer of reused GDN qkvz/ba INT8 quant outputs started cleanly and smoked through the frontdoor, but p512/n512 measured `99.17` corrected after-first tok/s and `97.90` e2e tok/s across eight repeats, below the accepted full-clone controls. Decision: reject and keep `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone`. Restore afterward passed frontdoor exact canaries, JSON semantics, 8-repeat stability, and baseline hash parity. Artifacts: `notes/2026-06-10-qwen36-dedupclone-gdn-cloneba-rejected.md`, `patches/vllm-qwen36-dedupclone-gdn-cloneba-rejected-20260611.patch`, `data/qwen36-quark-int8-tp4-noprefix-gdn-cloneba-single-r8-20260611.json`, `data/qwen36-quark-int8-tp4-noprefix-restore-after-dedupclone-cloneba-short-quality-20260611.json`.
- GDN `clone-qkvz` follow-up: the mirror of `clone-ba` completed startup and graph capture, then hit `UR_RESULT_ERROR_DEVICE_LOST` on the first frontdoor exact-OK chat smoke before speed benchmarking. All four B70s still enumerated afterward, and the accepted full-clone backend was restored and passed frontdoor exact `OK`. Decision: reject as a stability failure. Artifact: `data/qwen36-quark-int8-tp4-noprefix-gdn-cloneqkvz-device-lost-20260611.json`.
- GDN op timing and internal scratch screen: sync timing showed `gdn_attention_core_xpu.native` averaged `0.094088 ms` across `4288` calls while `gpu_model_runner.model_forward` averaged `12.459275 ms`, making GDN worth targeting. A follow-up `VLLM_XPU_GDN_REUSE_INTERNAL_SCRATCH=1` candidate for reusing internal `q/k/v/b/a/conv_states_tmp` tensors built and reached `/health`, but failed the first frontdoor exact-OK smoke with `UR_RESULT_ERROR_DEVICE_LOST`; the accepted binaries were restored and the frontdoor smoke returned `OK`. Decision: reject scratch reuse under graph capture; pursue safer GDN kernel fusion/timing instead. Artifacts: `notes/2026-06-10-qwen36-gdn-op-timing-scratch-rejected.md`, `data/qwen36-quark-int8-gdn-op-timing-scratch-rejected-20260610.json`, `data/qwen36-quark-int8-tp4-noprefix-op-timing-p512n128-20260611.json`.
- GDN decode conv temp skip screen: `VLLM_XPU_GDN_SKIP_DECODE_CONV_TMP=1` skipped `conv_states_tmp` allocation on decode-only GDN calls and passed frontdoor exact `OK`, but p512/n512 speed measured only `99.27` corrected after-first tok/s and `97.93` e2e tok/s across four repeats, slightly below accepted full-clone controls. Decision: reject before quality/reliability sweeps. Restore afterward passed frontdoor exact `OK` and measured `99.01` corrected after-first tok/s, `97.66` e2e tok/s, and `81.31 ms` TTFT across four p512/n512 repeats. Restore lesson: `_xpu_C.abi3.so` resolves helper libraries from `build/temp`, so accepted restores must sync helper `.so` files there as well as in `vllm_xpu_kernels/`; stale `build/temp` helper libs caused `_xpu_C` import segfaults until synchronized. External idea intake from vLLM Intel Arc docs/issues, B70 repos, and Localmaxxing was captured for the next round. Artifacts: `notes/2026-06-10-qwen36-skipdecodeconvtmp-rejected-and-ideas.md`, `data/qwen36-quark-int8-tp4-noprefix-gdn-skipdecodeconvtmp-single-r4-20260611.json`, `data/qwen36-quark-int8-tp4-noprefix-restore-after-skipdecodeconvtmp-single-r4-20260611.json`, `data/localmaxxing-b70-qwen36-like-filtered-20260611.json`, `scripts/launch-qwen36-quark-int8-accepted.sh`.
- Host-link audit: read-only PCIe/driver audit found all four B70 endpoints and their immediate downstream Intel bridge ports reporting `2.5 GT/s x1` current and max, while the upstream/root bridge hops report x16. A follow-up Arc Pro B60 thread reports this Gen1 x1 endpoint display as a known Arc-card quirk where the upstream bridge carries the real link status, so this is likely not the main bottleneck but still needs root `lspci -vv` validation. ASPM is still `[default]` and endpoint runtime power is `auto`; root is required to test reversible `performance`/`power/control=on` policies. A short p512/n256 direct decode during audit stayed healthy at `98.53` corrected after-first tok/s, and load sampling showed clocks can hit `2800 MHz`, so the service is not broken and idle clocks alone are not the bottleneck. Added a dry-run-by-default policy helper for the root-only reversible sysfs writes. Decision: validate host policy, but shift the main no-quality-loss speed focus back to MoE/XPU kernel efficiency. Artifacts: `notes/2026-06-10-qwen36-b70-host-link-audit.md`, `data/qwen36-b70-host-link-audit-20260611.txt`, `data/qwen36-b70-runtime-policy-dryrun-20260611.txt`, `scripts/audit-b70-host-links.sh`, `scripts/tune-b70-runtime-performance-policy.sh`.
- Stream interval screen: `--stream-interval 8` preserved async scheduling and graph capture shape, but p512/n512 streaming fell to `97.50` corrected after-first tok/s and `96.26` e2e tok/s versus the accepted `98.04` and `96.77`; mean TTFT was effectively flat at `77.81 ms` and one repeat fell to `90.52` e2e tok/s. Decision: reject; keep default stream interval `1`. Artifacts: `notes/2026-06-10-qwen36-stream-interval8-rejected.md`, `data/qwen36-quark-int8-tp4-noprefix-streamint8-graph32k-single-20260610.json`.
- Quiet-logs screen: `--disable-log-stats --disable-uvicorn-access-log` passed frontdoor quality parity and measured p512/n512 single-request speed at `98.74` corrected after-first tok/s and `97.50` e2e tok/s, with mean TTFT `75.99 ms`. A same-state accepted no-prefix single refresh measured `98.69` / `97.43`, so the apparent single-request gain is within variance. Aggregate was also mixed versus the historical accepted sweep: c1/c2/c4/c16 improved, c8/c32 dipped, and c48 measured `1545.65` wall / `1564.93` from-first tok/s with a rerun at `1517.63` / `1539.37`; a later accepted c48 refresh measured only `1479.66` / `1495.39`, so the c48 drop from the original `1700.89` / `1727.50` reference is current lab variance rather than a proven quiet-logs regression. Decision: quiet logs is quality-safe and operationally reasonable for lower console noise, but do not count it as a speed win without repeated paired A/B. Artifacts: `notes/2026-06-10-qwen36-quietlogs-single-win-c48-regression.md`, `data/qwen36-quark-int8-tp4-noprefix-quietlogs-graph32k-single-20260610.json`, `data/qwen36-quark-int8-tp4-noprefix-quietlogs-frontdoor-quality-20260610.json`, `data/qwen36-quark-int8-tp4-noprefix-quietlogs-graph32k-concurrency-20260610.json`, `data/qwen36-quark-int8-tp4-noprefix-quietlogs-c48-confirm-20260610.json`, `data/qwen36-quark-int8-tp4-noprefix-accepted-c48-refresh-20260610.json`, `data/qwen36-quark-int8-tp4-noprefix-accepted-single-refresh2-20260610.json`.
- Runtime rejections: TP4 `max_num_seqs=1` / `max_num_batched_tokens=1024` measured only `85.11` corrected after-first tok/s because one repeat fell to about `57.7 tok/s`; TP2 32K fit with `16.88 GiB` model memory per active GPU and `31.92x` 32K max concurrency, but measured only `86.85` corrected after-first tok/s. `--block-size 256` was effectively neutral for single-request speed (`98.21` corrected after-first tok/s versus `98.04`) but worsened TTFT, increased hybrid attention/mamba padding, slightly reduced reported KV-token capacity, and regressed c48 aggregate to `1533.55` wall tok/s versus `1700.89`; keep the default XPU FlashAttention KV block size. `--max-num-batched-tokens 512` was also effectively flat for single-request speed (`98.20` corrected after-first tok/s), but c48 aggregate fell to `1351.21` wall tok/s and c16 fell to `485.89`; keep `--max-num-batched-tokens 8192`. `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0` was flat for single-request decode (`98.22` corrected after-first tok/s) but worsened TTFT and regressed c48 aggregate to `1635.20` wall tok/s; keep the oneCCL default. Forced XPU sequence parallelism with `sp_min_token_num=1` failed startup before serving with an Inductor symbolic shape mismatch between `s18` and `s18//4`; keep SP disabled until the shape issue is fixed. Skipping redundant `GemmaRMSNorm.forward_native` BF16-to-BF16 casts removed the direct cast signature from generated graphs but regressed single-request speed to `97.96` corrected after-first tok/s and `96.73` e2e tok/s versus the accepted refresh `98.69` / `97.43`; keep the accepted layernorm behavior. Removing Python-level `.contiguous()` before native XPU INT8 activation quant removed `view.contiguous` signatures from generated graphs but regressed single-request speed to `98.23` corrected after-first tok/s and `96.98` e2e tok/s; keep the accepted dense INT8 wrapper behavior. Artifacts: `data/qwen36-quark-int8-seq1-mbt1024-single-20260610.json`, `data/qwen36-quark-int8-tp2-graph32k-single-20260610.json`, `notes/2026-06-10-qwen36-blocksize256-rejected.md`, `data/qwen36-quark-int8-tp4-noprefix-block256-graph32k-single-20260610.json`, `data/qwen36-quark-int8-tp4-noprefix-block256-graph32k-concurrency-20260610.json`, `notes/2026-06-10-qwen36-mbt512-rejected.md`, `data/qwen36-quark-int8-tp4-noprefix-mbt512-graph32k-single-20260610.json`, `data/qwen36-quark-int8-tp4-noprefix-mbt512-graph32k-concurrency-20260610.json`, `notes/2026-06-10-qwen36-ccl-fabric-vertex-off-rejected.md`, `data/qwen36-quark-int8-tp4-noprefix-cclfabric0-graph32k-single-20260610.json`, `data/qwen36-quark-int8-tp4-noprefix-cclfabric0-graph32k-concurrency-20260610.json`, `notes/2026-06-10-qwen36-sequence-parallel-sp1-rejected.md`, `data/qwen36-quark-int8-tp4-noprefix-sp1-startup-fail-20260610.json`, `notes/2026-06-10-qwen36-skip-redundant-gemma-to-rejected.md`, `data/qwen36-quark-int8-tp4-noprefix-skip-gemma-to-graph32k-single-20260610.json`, `patches/vllm-qwen36-skip-redundant-gemma-to-rejected-20260610.patch`, `notes/2026-06-10-qwen36-skip-python-contiguous-rejected.md`, `data/qwen36-quark-int8-tp4-noprefix-skip-python-contig-graph32k-single-20260610.json`, `patches/vllm-qwen36-skip-python-contiguous-int8-rejected-20260610.patch`.
- Graph inspection after custom-op collectives: c10d/allreduce analyzers now return zero because the promoted backend routes collectives through `torch.ops.vllm.all_reduce`. The compiled graph still shows roughly 220 dense `per_token_quant_int8_xpu` assignments, 220 `int8_gemm_w8a8` assignments, 101 `vllm_ir.rms_norm.default` assignments, 81 custom all-reduce assignments, and 40 MoE custom-op assignments. This points the next work at dense RMS/quant/GEMM boundaries and exact MoE epilogues, not at the old c10d call path. Artifacts: `data/qwen36-quark-int8-mixedws-aot-allreduce-boundaries-20260610.json`, `data/qwen36-quark-int8-mixedws-aot-collectives-20260610.json`.
- Added decode-bucket timing metadata to the local vLLM runner and taught `scripts/summarize-xpu-decode-timing-log.py` to emit `step_summary_by_bucket`. The accepted TP4/Quark/32K/no-prefix timing probe captured `80` pure KV-resident bucket-1 decode steps under synchronized timing: PIECEWISE graph, `decode_bucket=1`, no speculative tokens, mean rank-0 `model_forward=12.393 ms`, and mean visible timed work `16.759 ms`. The largest visible regions were model forward, `gdn_attention_core_xpu.native=2.730 ms`, logits compute `0.780 ms`, local argmax/lm-head `0.542 ms`, and sampler `0.163 ms`; these do not add up to a likely 2x win by themselves. Endpoint throughput from this run (`65.99` corrected after-first tok/s) is diagnostic only because `VLLM_XPU_DECODE_TIMING_SYNC=1` intentionally slows serving. First instrumentation attempt found and fixed a `num_tokens_across_dp=None` metadata bug. Accepted no-timing service was restored in `qwen36-tp4-accepted-restored-after-bucket-timing-20260611q`; backend/frontdoor health and frontdoor smoke passed with baseline parity. Artifacts: `patches/vllm-qwen36-decode-bucket-timing-metadata-20260611.patch`, `data/qwen36-quark-int8-tp4-decode-bucket-timing-p512o96-20260611.json`, `data/qwen36-quark-int8-tp4-decode-bucket-timing-summary-20260611.json`, `data/qwen36-quark-int8-tp4-accepted-restored-after-bucket-timing-text-smoke-20260611.json`.
- Bigger no-quality-loss bets were expanded after checking current XPU/vLLM and oneDNN leads: current vLLM work is moving Intel support into `vllm-xpu-kernels`, oneDNN now documents experimental grouped memory/GEMM for MoE workloads, and persistent grouped-GEMM designs point at a larger MoE scheduling opportunity than flag tuning. The next structural paths are verifier-bucket timing for buckets `2,3,4,5,6,8`, a oneDNN grouped-GEMM route replay harness, a current vLLM-XPU kernel delta check, verifier-preserving sidecar/MTP speculation if bucket scaling is favorable, and persistent MoE/hybrid TP-EP/static solo decode if bucket scaling is not. Detailed backlog: `notes/2026-06-11-qwen36-aot-localmaxxing-and-runtime-screens.md`.
- Ran speculative verifier bucket timing probes with n-gram2/5/7 under synchronized timing. The important result is bucket scaling, not endpoint speed: bucket-3 forward was `15.27-15.43 ms`, bucket-6 was `15.54 ms`, and bucket-8 was `18.88 ms`, compared with `~12.24-12.39 ms` bucket-1. This keeps verifier-preserving speculation as the highest-upside path to `>200 tok/s` because multi-token verifier passes are clearly sublinear. The current n-gram proposer is still not production-worthy: n-gram2 acceptance was `78.87%` across mixed probes, but previous quality gates rejected n-gram variants; n-gram5 acceptance was only `41.30%`, and n-gram7 `54.29%`. Decision: stop blind n-gram width sweeps; build a real same-tokenizer sidecar/MTP/EAGLE proposer or verifier replay scorer, while keeping MoE/static decode as the fallback path. Accepted no-timing backend restored in `qwen36-tp4-accepted-restored-after-spec-bucket-timing-20260611u`; backend/frontdoor health and frontdoor text smoke passed with baseline parity. Artifacts: `data/qwen36-quark-int8-tp4-ngram2-bucket-timing-natural-summary-20260611.json`, `data/qwen36-quark-int8-tp4-ngram5-bucket-timing-repetitive-summary-20260611.json`, `data/qwen36-quark-int8-tp4-ngram7-bucket-timing-repetitive-summary-20260611.json`, `data/qwen36-quark-int8-tp4-ngram2-bucket-timing-spec-summary-20260611.md`, `data/qwen36-quark-int8-tp4-ngram5-bucket-timing-spec-summary-20260611.md`, `data/qwen36-quark-int8-tp4-ngram7-bucket-timing-spec-summary-20260611.md`, `data/qwen36-quark-int8-tp4-accepted-restored-after-spec-bucket-timing-text-smoke-20260611.json`.
- Added the next-step MTP and bigger-bets backlog. The current Quark verifier config advertises `mtp_num_hidden_layers=1` but its safetensors index has `0` MTP keys; the official FP8 snapshot has `1560` MTP keys and an `815M` `mtp.safetensors` blob. Local vLLM already has `Qwen3_5MoeMTP`, `method="mtp"`, and `VLLM_QWEN35_MTP_FORCE_FP8_BLOCK=1`, so the next concrete mechanics test is a disposable hybrid MTP launch: keep Quark INT8 as final verifier, add the official FP8 MTP tensors only as proposer assets, start with `--speculative-config '{"method":"mtp","num_speculative_tokens":1,"max_model_len":32768}'`, and require exact request-id token-trace parity before any speed claim. Bigger ideas now tracked include an auxiliary-MTP loader patch, same-tokenizer learned proposer, partial-layer self-drafter, perfect-draft verifier upper-bound harness, route-aware MTP/MoE co-design, memory-for-latency expert placement, persistent decode command graph, upstream XPU MoE repros, and a dual-lane production design. Details: `notes/2026-06-11-qwen36-aot-localmaxxing-and-runtime-screens.md`.
- Hybrid Quark-verifier plus official-FP8-MTP mechanics now loads and serves, but is rejected on strict quality. Added `scripts/create-qwen36-quark-fp8-mtp-hybrid.py` and `scripts/launch-qwen36-quark-int8-hybrid-mtp.sh`. Async MTP passed r1 frontdoor token parity but failed r4 with copy/arithmetic/repeat corruption; `--no-async-scheduling` still failed long-context needle parity (`B70_QWEN36_NEEDLE_20260609` became `B Lebens Mourinho \_QWEN36\_NEEDLE\_20260609`). No speed or Localmaxxing claim is valid for this path. Accepted Quark INT8 service was restored in `qwen36-tp4-accepted-restored-after-hybrid-mtp-20260611x`; backend/frontdoor health passed and short frontdoor text smoke passed exact arithmetic/copy/JSON/repeat checks. The newer public Localmaxxing generic-base row is `cmq9ifq0500b0r8012f27j1xl`: `99.769699` tok/s, `76.526643 ms` TTFT, and `127.547168 GB` total peak VRAM allocation across 4x B70. The next speculative priority is now a perfect-draft/verifier-only multi-token harness plus a minimal hybrid-MTP failure pack; stop MTP speed testing until long-context parity is exact.
- Added a timing-derived verifier upper-bound analysis and refreshed public B70/Qwen/vLLM leaderboard artifacts. `scripts/analyze-qwen36-verifier-upper-bound.py` reads the synchronized bucket timing summaries and writes `data/qwen36-quark-int8-tp4-verifier-upper-bound-20260611.{json,md}`. Best current bucket timings: bucket 3 `15.269 ms` / `196.47` perfect model-forward tok/s, bucket 6 `15.544 ms` / `386.01`, bucket 8 `18.883 ms` / `423.66`; endpoint-normalized perfect estimates are `239.95`, `471.42`, and `517.41` tok/s respectively. This is not a speed claim because current n-gram/MTP paths failed quality, but it proves the verifier has enough sublinear headroom if an exact proposer can be made. The notes now track bigger next bets: oracle-draft verifier harness, DFlash/MTP state-index audit, explicit auxiliary proposer API, Quark-trace-trained proposer, bucket-aware static latency lane, memory-for-latency expert placement, same-quality 8-bit LLM-Scaler/OpenVINO/vLLM-XPU shootout, whole-token command-list capture, and upstreamable B70/XPU repro packets. Artifacts: `data/localmaxxing-intel-arc-pro-b70-qwen-vllm-leaderboard-20260611c.json`, `data/localmaxxing-qwen36-base-top-20260611c.json`, `notes/2026-06-11-qwen36-aot-localmaxxing-and-runtime-screens.md`.
- Expanded the post-upper-bound "things to try" backlog with proof-oriented experiments and bolder branches. Near-term: oracle-draft `k=3/5/6/8`, recompute-after-reject diagnostics, speculative acceptance prediction, token-trace CI, and real-router histogram capture. Medium: first-class auxiliary proposer API, self-speculative shallow verifier branch, sidecar drafter pipeline, c1/c4 latency lane, hybrid TP/EP simulator, persistent MoE route-window kernel, tile-native W8A8 repack cache, and whole-token command-list capture. Moonshots: Quark-trace-trained proposer, route-aware speculation, memory-for-latency hot expert copies, strict 8-bit engine shootout, and upstream packet/bounty-quality repros. Action order: prove or disprove perfect-draft `>200 tok/s` first, then choose between proposer engineering and MoE/layout work. Details: `notes/2026-06-11-qwen36-aot-localmaxxing-and-runtime-screens.md`.
- Added the first oracle-draft harness for vLLM's n-gram proposer path. `scripts/qwen36-completion-oracle-trace.py` records raw completion prompt/output token IDs; `scripts/launch-qwen36-quark-int8-oracle-trace.sh` wires `VLLM_XPU_ORACLE_DRAFT_TRACE`; `patches/vllm-qwen36-oracle-draft-ngram-proposer-20260611.patch` records the local vLLM hook. Eager `k=5` proved draft injection works (`24` matched draft rows, scheduler acceptance `73.33%`) but failed exact parity versus the accepted graph baseline at output-token index `14`, so no speed claim is valid. Graph `k=5` reached `/health` but hit `UR_RESULT_ERROR_DEVICE_LOST` on external chat traffic before the controlled probe; isolate the next graph oracle run from frontdoor/production traffic. Accepted non-spec service restored in `qwen36-tp4-accepted-restored-after-oracle-20260611b`; backend and frontdoor health passed, and frontdoor short text smoke passed with `pass_all=true`. Artifacts: `data/qwen36-quark-int8-tp4-oracle-completions-accepted-20260611.json`, `data/qwen36-quark-int8-tp4-oracle5-eager-completions-20260611.json`, `data/qwen36-quark-int8-tp4-oracle5-eager-spec-summary-20260611.md`, `data/qwen36-quark-int8-tp4-accepted-restored-after-oracle-frontdoor-text-smoke-20260611.json`.
- The isolated graph-mode oracle `k=5` probe was run on backend port `18081` with a same-posture accepted graph baseline captured immediately beforehand. It no longer device-lost under the controlled probe, but still failed exact parity: scheduler trace `8` rows / `2` requests / `77.50%` acceptance, while `baseline_match_all=false`; first diffs were `natural_latency_plan` output index `25` and `repetitive_kernel_notes` output index `14`. This proves the current issue is not just proposer quality; even an oracle draft can perturb final output, so the next diagnostic is `k=1` oracle plus KV/block-table/scheduler accounting before more MTP or n-gram speed work. Accepted backend was restored in `qwen36-tp4-accepted-restored-after-notes-retry-20260611b`; backend and frontdoor health pass, but the latest short frontdoor smoke still fails the arithmetic exact canary (`58` vs `60`) while OK/copy/JSON/repeat pass under continuing external traffic. Treat service as healthy but do not promote a new quality result until the frontdoor canary is rerun in an isolated window or replaced with a request-id token-trace baseline. New artifacts: `data/qwen36-quark-int8-tp4-oracle-isolated-accepted-graph-20260611.json`, `data/qwen36-quark-int8-tp4-oracle5-graph-isolated-completions-20260611.json`, `data/qwen36-quark-int8-tp4-oracle5-graph-isolated-spec-summary-20260611.md`, `data/qwen36-quark-int8-tp4-accepted-restored-after-notes-retry-frontdoor-text-smoke-20260611.json`. The bigger backlog now includes a first-class auxiliary proposer API, an upstreamable speculative-state minimizer, route-aware verifier buckets, memory-for-latency expert hotsets, whole-token graph replay, strict 8-bit engine bakeoff, and B70/XPU repro bundles.
- Oracle `k=1` now also fails exact parity. A clean full-length p512/o128 accepted-baseline attempt on isolated `18081` hit `UR_RESULT_ERROR_DEVICE_LOST` at `block_table.copy_to_gpu` before writing a trace, so the full-length comparison did not complete. A shorter p512/o32 run did complete: accepted baseline captured from a freshly restored graph backend, graph oracle `k=1` on `18081` reached `/health`, scheduler trace recorded `15` rows / `2` requests / `93.33%` acceptance, but `baseline_match_all=false`; first diffs were `natural_latency_plan` output index `14` and `repetitive_kernel_notes` output index `15`. This proves the speculative problem is already below draft width/bonus behavior: stop n-gram/MTP speed work until scheduler/KV/block-table/verifier input state is fixed. Accepted backend restored in `qwen36-tp4-accepted-restored-after-oracle1-short-20260611a`; backend and frontdoor health pass, but three post-restore short frontdoor smokes were not production-clean due arithmetic/repeat instability under live traffic. The current frontdoor pause file is startup-only, so dynamic pause/drain and a local-only quality lane are now required production/reliability follow-ups. Artifacts: `data/qwen36-quark-int8-tp4-oracle-k1-clean-baseline-devicelost-20260611.json`, `data/qwen36-quark-int8-tp4-oracle-k1-short-accepted-graph-20260611.json`, `data/qwen36-quark-int8-tp4-oracle1-short-graph-completions-20260611.json`, `data/qwen36-quark-int8-tp4-oracle1-short-graph-spec-summary-20260611.md`, and the `accepted-restored-after-oracle1-short-frontdoor-text-smoke*` artifacts.
- Added a post-perfect-draft backlog refresh with public Localmaxxing snapshots and bolder no-quality-loss ideas. Immediate items are block-table parity tracing, an accepted-vs-placebo verifier-input comparator, real-router histogram capture, token-level timing budget, and publish-grade r8/r10 benchmark packaging. Larger branches now tracked include a Quark-verifier MTP sidecar, DFlash-style XPU drafter, persistent Qwen3.6 A3B MoE executor, layer-local hot expert replication, hybrid TP/EP single-user layout, direct fixed-shape graph runner, whole-token command-list capture, XPU-native W8A8 retile cache, same-model 8-bit engine bakeoff, production latency service classes, upstreamable B70 repro packet, and reliability metrics as first-class benchmark data. Artifacts: `data/localmaxxing-qwen36-35b-a3b-top-after-perfectdraft-20260611.json`, `data/localmaxxing-qwen-30b-class-top-after-perfectdraft-20260611.json`; details: `notes/2026-06-11-qwen36-aot-localmaxxing-and-runtime-screens.md`.
- Added `scripts/check-qwen36-model-input-parity.py` and the incremental local vLLM trace patch `patches/vllm-qwen36-model-input-blocktable-trace-20260611.patch`. The active `gpu_model_runner.py` trace now records `BlockTable` state through accessors instead of producing `AttributeError("'BlockTable' object has no attribute 'detach'")`; the newer `gpu/model_runner.py` trace records input/persistent tables plus `num_blocks`. Existing accepted-vs-placebo traces compare `80` rows and mismatch immediately at row `0`, `attn.slot_mappings.1.head[0]` (`65536` vs `98304`); accepted-vs-noasync first mismatches at row `26` in generated-token input history. Validation passed: parity script `py_compile`, both patched vLLM runner `py_compile`, and report generation. Next step is to rerun accepted/placebo traces with fixed block-table capture and use the checker as a hard gate before more speculation speed work.

Next Qwen targets: fix RMS/quant graph-pattern matching only if the exact FP32-weight semantics can be preserved, investigate dense W8A8 small-M GEMM epilogues and allocation reuse, revisit MoE scratch reuse only if it improves full-model speed, fuse MoE activation plus second-stage quant only if it reproduces current rounding/scaling behavior, and keep aggregate throughput tracked with the 1/2/4/8/16/32/48 concurrency harness.

## MiniMax M2.7

Section last updated: 2026-05-19

Current strict quality-passed speed result:

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Hardware: 4x Intel Arc Pro B70 32GB
- Engine: vLLM `0.20.1-local`, XPU TP4
- Recipe: FP16 activations, AutoRound INT4 W4A16, default XPU FlashAttention v2, XPU PIECEWISE graph, exact MiniMax router-logits path feeding llm-scaler INT4 MoE work-sharing decode with `VLLM_XPU_USE_LLM_SCALER_MOE_WS=1`, `VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS=1`, `VLLM_MINIMAX_M2_ATTN_DELAY_ALLREDUCE=0`, clone-safe compiled allreduce custom-op via `VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP=1` plus `VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT=1`, direct in-place Q/K variance allreduce+scale via `VLLM_MINIMAX_QK_RMS_DIRECT_INPLACE_SCALE=1`, final MoE output allreduce moved inside the MoE custom-op boundary via `VLLM_MINIMAX_MOE_OUTPUT_ALLREDUCE_INSIDE_CUSTOM_OP=1`, and decode-sized router-linear plus fused MoE wrapped in a guarded MiniMax full-forward custom-op boundary via `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP=1` with `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS=4`
- Shape: p512/n1536, ctx2048, batch 1
- Result: `89.314195` output tok/s, `119.085594` total tok/s, mean of four clean long repeats
- Output tok/s repeats: `[88.927239, 89.396677, 89.527321, 89.405544]`
- Quality: raw145 exact n64/n256 hashes, semantic suite, 16-repeat arithmetic, and extended sixpack all passed before benchmarking
- Delta: `+0.43%` output tok/s over the previous strict high (`88.927945`) and `+10.81%` over the earlier MoE-WS FlashAttention/PIECEWISE baseline (`80.602755`)
- LocalMaxxing: `cmpct6t4m007fnw01yjdtlcs4`

Primary artifacts:

- Current strict clean high: `notes/2026-05-19-minimax-moe-full-forward-customop-plus-output-ar.md`, `data/minimax-m27-moe-full-forward-customop-plus-output-ar-20260519.json`, `data/localmaxxing-minimax-m27-autoround-moe-full-forward-customop-plus-output-ar-p512n1536-20260519.payload.json`, `data/localmaxxing-responses/minimax-m27-autoround-moe-full-forward-customop-plus-output-ar-p512n1536-20260519.response.json`, `patches/minimax-moe-full-forward-customop-plus-output-ar-20260519.md`
- Previous MoE output-allreduce custom-op high: `notes/2026-05-19-minimax-moe-output-allreduce-inside-customop.md`, `data/minimax-m27-moe-output-allreduce-inside-customop-20260519.json`, `data/localmaxxing-minimax-m27-autoround-moe-output-allreduce-inside-customop-p512n1536-20260519.payload.json`, `data/localmaxxing-responses/minimax-m27-autoround-moe-output-allreduce-inside-customop-p512n1536-20260519.response.json`, `patches/minimax-moe-output-allreduce-inside-customop-20260519.patch`
- Current clean direct Q/K variance follow-up: `notes/2026-05-19-minimax-qk-direct-inplace-scale.md`, `data/minimax-m27-qk-direct-inplace-scale-20260519.json`, `data/localmaxxing-minimax-m27-autoround-qk-direct-inplace-scale-p512n1536-20260519.payload.json`, `data/localmaxxing-responses/minimax-m27-autoround-qk-direct-inplace-scale-p512n1536-20260519.response.json`, `patches/minimax-qk-direct-inplace-scale-20260519.patch`
- Cleaner Q/K-helper follow-up: `notes/2026-05-19-minimax-qk-helper-tinyfp32-inplace.md`, `data/minimax-m27-qk-helper-tinyfp32-inplace-20260519.json`, `data/localmaxxing-minimax-m27-autoround-qk-helper-tinyfp32-inplace-p512n1536-20260519.payload.json`, `data/localmaxxing-responses/minimax-qk-helper-tinyfp32-inplace-20260519.response.json`
- Cleaner alias-correct tiny-FP32 in-place path: `notes/2026-05-19-minimax-qkvar-inplace-fp32n2.md`, `data/minimax-m27-qkvar-inplace-fp32n2-20260519.json`, `data/localmaxxing-minimax-m27-autoround-qkvar-inplace-fp32n2-p512n1536-20260519.payload.json`, `data/localmaxxing-responses/minimax-m27-autoround-qkvar-inplace-fp32n2-20260519.response.json`, `patches/minimax-qkvar-inplace-fp32n2-20260519.patch`
- Previous warning-prone speed headline: `notes/2026-05-18-minimax-qkvar-skipclone-fp32n2-win.md`, `data/minimax-m27-qkvar-skipclone-fp32n2-win-20260518.json`, `data/localmaxxing-minimax-m27-autoround-qkvar-skipclone-fp32n2-p512n1536-20260518.payload.json`, `data/localmaxxing-responses/minimax-m27-autoround-qkvar-skipclone-fp32n2-p512n1536-20260518.response.json`, `patches/minimax-qkvar-skipclone-fp32n2-20260518.patch`
- Recent Q/K helper guard rejections: `notes/2026-05-19-minimax-qk-helper-max1-currenthigh-quality-fail.md`, `data/minimax-m27-qk-helper-max1-currenthigh-quality-fail-20260519.json`, `notes/2026-05-19-minimax-qk-helper-max2-currenthigh-negative.md`, `data/minimax-m27-qk-helper-max2-currenthigh-negative-20260519.json`
- QKV narrow-split negative: `notes/2026-05-19-minimax-qkv-narrow-split-negative.md`, `data/minimax-m27-qkv-narrow-split-negative-20260519.json`, `patches/minimax-qkv-narrow-split-negative-20260519.patch`
- Current-high CCL fabric-vertex override rejection: `notes/2026-05-19-minimax-currenthigh-ccl-fabric-vertex-off-negative.md`, `data/minimax-m27-currenthigh-ccl-fabric-vertex-off-negative-20260519.json`
- Current-high skip-contiguous rejection: `notes/2026-05-19-minimax-currenthigh-skip-redundant-contiguous-negative.md`, `data/minimax-m27-currenthigh-skip-redundant-contiguous-negative-20260519.json`

Previous promoted MiniMax baselines:

- MiniMax MoE full-forward custom-op high: `89.314195` output tok/s, `119.085594` total tok/s, LocalMaxxing `cmpct6t4m007fnw01yjdtlcs4`.
- MoE output-allreduce-inside-custom-op: `88.927945` output tok/s, `118.570593` total tok/s, LocalMaxxing `cmpco63q90052nw01ov1zxvwp`.
- Direct Q/K variance in-place scale: `88.501953` output tok/s, `118.002604` total tok/s, LocalMaxxing `cmpc8cmqm0060pc016g5l5ukh`.
- Q/K helper plus alias-correct tiny-FP32 in-place op: `88.313105` output tok/s, `117.750807` total tok/s, LocalMaxxing `cmpc5xmm6005jpc01k84dxd14`.
- Alias-correct tiny-FP32 in-place op: `88.103866` output tok/s, `117.471821` total tok/s, LocalMaxxing `cmpc1dxgv0052pc01s1j9i37l`.
- Warning-prone tiny-FP32 skip-clone headline: `88.748424` output tok/s, `118.331232` total tok/s, LocalMaxxing `cmpbz7lyc004rpc019jburzqv`.
- Clone-safe custom allreduce without tiny-FP32 clone elision: `87.279129` output tok/s, `116.372172` total tok/s, LocalMaxxing `cmpbsqm4l001qpc0199azisgz`.
- No-attention-delay logits-WS baseline without clone-safe compiled allreduce custom-op: `82.404268` output tok/s, `109.872357` total tok/s, LocalMaxxing `cmpbifcx3013bmn01747cxix8`.
- Delayed-attention logits-WS baseline: `81.758267` output tok/s, `109.011023` total tok/s, LocalMaxxing `cmpay7th600bbmn01v6csyaro`.
- Earlier MoE-WS FlashAttention/PIECEWISE baseline: `80.602755` output tok/s, `107.470340` total tok/s, LocalMaxxing `cmpasdq5v007nmn019elaut3s`.

Recent quality-safe rejections and screens:

- Q/K helper max1 current-high: lowered `VLLM_MINIMAX_QK_RMS_XPU_HELPER_MAX_TOKENS` from `4` to `1`. It failed `raw145-n64-exact` before benchmarking: expected `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`, observed `21404821eb70a2ee3de9e82c039b5cbb5c9eef884c5019579f442c6a272a9c5a`. Output was deterministic and non-degenerate, but exact-token drift violates the quality rule. Decision: reject, do not benchmark, do not submit to LocalMaxxing.
- Q/K helper max2 current-high: lowered `VLLM_MINIMAX_QK_RMS_XPU_HELPER_MAX_TOKENS` from `4` to `2`. It passed raw145 n64/n256 exact hashes, semantic suite, 16-repeat arithmetic, and extended sixpack. Result: `88.541226` output tok/s / `118.054968` total tok/s. Decision: reject and do not submit to LocalMaxxing because it is `0.772970` output tok/s below the promoted mean. Keep Q/K helper max tokens at `4`.
- Current-high CCL fabric-vertex override: `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0` passed raw145 n64/n256 exact hashes, semantic suite, 16-repeat arithmetic, and extended sixpack. Result: `89.037858` output tok/s / `118.717144` total tok/s across four repeats, `0.276337` output tok/s below the promoted mean. The arithmetic-repeat shutdown log also printed oneCCL/PMI `Broken pipe` and `ccl::v1::exception` teardown errors. Decision: reject, do not submit to LocalMaxxing, and keep this env unset.
- Current-high skip-redundant-contiguous: `VLLM_XPU_LLM_SCALER_MOE_MINIMAX_SKIP_REDUNDANT_CONTIGUOUS=1` passed raw145 n64/n256 exact hashes, semantic suite, 16-repeat arithmetic, and extended sixpack. Result: `89.141961` output tok/s / `118.855948` total tok/s across four repeats, `0.172235` output tok/s below the promoted mean. The extended-sixpack and first benchmark-repeat logs printed `Bad address (src/pipe.cpp:367)` during shutdown. Decision: reject and do not submit to LocalMaxxing.
- QKV narrow-split: `VLLM_MINIMAX_QKV_NARROW_SPLIT=1` replaced `qkv.split(...)` view extraction with explicit `Tensor.narrow()` views around the Q/K RMS helper. It passed raw145 n64/n256 exact hashes, semantic suite, 16-repeat arithmetic, and extended sixpack. Result: `88.802625` output tok/s / `118.403500` total tok/s. Decision: reject and do not submit to LocalMaxxing because it is `0.511570` output tok/s below the promoted mean. The lesson is that split-view selection is not a meaningful decode bottleneck under the current XPU graph replay path.
- MiniMax MoE full-forward guard sweep: max1 `89.031893`, max2 `88.854010`, max3 `88.886159`, max4 `89.314195`, max512 `85.209082` output tok/s. Decision: keep `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS=4`.
- Post-attention norm plus MoE custom-op: quality passed but measured `89.007143` output tok/s / `118.676191` total tok/s. Reject.
- Full-forward plus callable-cache: quality passed but measured `88.828891` output tok/s / `118.438521` total tok/s. Reject.
- MoE output-allreduce plus callable-cache stack: quality passed but measured `88.912296` output tok/s / `118.549728` total tok/s. Reject.
- MiniMax MoE WS skip-redundant-contiguous without full-forward custom-op: quality passed but measured `88.885135` output tok/s / `118.513514` total tok/s. Reject.
- Current-high `--block-size 128` failed `raw145-n64-exact`; keep `--block-size 256`.
- `VLLM_MINIMAX_MOE_FINAL_INPLACE_ALLREDUCE=1` failed the first strict quality gate before benchmarking; do not use larger FP16 hidden-state in-place allreduce under the current graph recipe.
- `VLLM_XPU_LOGITS_CHUNKED_GATHER=32768` failed 16-repeat arithmetic determinism; do not use chunked logits gather until deterministic.
- Exact-shape XCCL microbench found raw decode-sized allreduces around `15-17 us`; full-model loss is dominated by framework/compiler/graph boundaries around collectives, not raw CCL latency alone.
- `VLLM_XPU_CUSTOM_ALLREDUCE_INPLACE_MAX_NUMEL=4096` and `=2048` both passed quality but were slower than dtype-specific tiny-FP32 routing. Keep generic in-place threshold unset or `0`.

Detailed historical candidate screens remain in `notes/` and `data/`. The local lab copy of `CURRENT.md` may include a longer running chronology than this concise repo status file.

## Qwen3.6 27B

The quality-preserving Qwen targets remain separate from MiniMax AutoRound:

- Q4_0 GGUF TP3 remains the current Qwen decode-speed focus.
- Static FP8 TP4 remains the preferred long-context Qwen layout.
- AutoRound/INT4 results should not be compared as equal-quality replacements for FP8/BF16/GGUF without separate quality validation.

## Next Optimization Targets

- Use the MiniMax MoE full-forward custom-op result as the current strict baseline for future code work.
- Keep `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS=4`; the guard-size sweep found max4 as the local optimum.
- Keep `VLLM_MINIMAX_QK_RMS_XPU_HELPER_MAX_TOKENS=4`; max1 failed exact quality and max2 was quality-safe but slower.
- Keep `VLLM_XPU_CUSTOM_ALLREDUCE_INPLACE_MAX_NUMEL=0`; generic thresholds are quality-safe but slower than dtype-specific tiny-FP32 routing.
- Keep `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK` unset; the current-high retest was slower and showed oneCCL shutdown noise.
- Continue targeting true XPU fused-boundary work: hidden allreduce plus residual/RMSNorm, Q/K variance allreduce plus Q/K RMS apply, MoE output plus epilogue, and final lm-head/projection boundaries.
- Preserve vLLM's proven allreduce semantics unless a candidate has an exact repeatability proof across fresh graph/cache captures.
- Keep strict quality gates as promotion blockers; do not promote logits/router/argmax shortcuts unless they pass raw exact hashes, semantic checks, arithmetic repeat, and extended sixpack.
- Keep speculative decode optional and quality-gated; no current promoted MiniMax result uses speculation.

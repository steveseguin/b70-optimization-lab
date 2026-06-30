# Codex Agent Handoff

Last updated: 2026-06-29

This file is the first thing a new Codex agent should read when continuing the
Intel Arc Pro B70 LLM optimization work.

## Current Objective

Primary target:

- Gemma 4 26B A4B Q8/INT8-quality on Intel Arc Pro B70.
- Run one Q8 target/verifier replica per GPU where practical, using four GPUs
  for parallel research screens rather than TP4 unless explicitly testing a
  multi-GPU serving shape.
- Best strict realistic-suite one-B70 result is
  `121.41411987308553 tok/s` median generated-token throughput for tokens
  1-100 after TTFT across the fixed cold prompt suite. Evidence:
  `data/gemma4-q8-gpu3-q8lmhead-noreorder-control-full512-20260629T224927Z/summary.json`.
  It uses llama.cpp `c926ad098`, UD-Q8_K_XL target/verifier, Q4_0 MTP draft,
  reordered-Q8 VDR2, `FLASH_ATTN=on`, `CTX_SIZE=32768`,
  `GGML_SYCL_ENABLE_VMM=1`, `n_max=3`, `n_min=2`, `p_min=0.0475`,
  `UBATCH_SIZE=1024`, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`,
  `cached_tokens=0` on every prompt, and
  `realistic_final_gate.passed=true`.
- Representative / submitted status: this is the confirmed strict-gate VDR2
  selected-down fused weighted-sum family, now with FA-on 32K/VMM. The current
  high is approved by LocalMaxxing as `cmqztiqdn02vnoe01egox6q3f`.
  Same-family confirmation includes
  `data/gemma4-q8-gpu2-baseline-recordconfirm-full512-20260629T225215Z/summary.json`
  at `119.94842631460949 tok/s`; the prior FA-on 32K/VMM row
  `cmqzq5zu402troe01t774uyox`, selected-down rows `cmqyrpox4021dqk01co5o4fcw`
  and `cmqyo0jyt08ippk01vhiobdnm`, and prior submitted rows
  `98.34046474459183` (`cmqxchyra03xmqr01b963gmi1`),
  `95.82453787677183` (`cmqx3687103v4qr01ace1ft3m`),
  `90.98312252660529` (`cmqwxep4a03qiqr010chjn93s`),
  `90.32179401019857` (`cmqwt1zk803ozqr01hctqss2z`),
  `89.45543282863798` (`cmqwqzayr03o8qr01j6lgx93n`), and
  `87.61145306230438` (`cmqwnl2ag03lgqr01ch5bxknq`) are superseded.
- Current valid no-spec control is `74.29709476830473 tok/s` median on the same
  suite:
  `data/gemma4-q8-gpu0-vdr4default-nospec-realistic-gate-v2-20260627T165335Z/summary.json`.
  This is the clean target-side baseline for continued optimization.
- Latest full512 follow-up: fused selected-softmax into selected-down VDR2
  (`LLAMA_GEMMA4_MOE_FUSED_DOWN_SELECTED_SOFTMAX=1`) and the EOG-clip
  interaction were valid but lost. Best candidate was `111.90908727268967
  tok/s` with EOG clip, below controls and below the `121.41411987308553` record.
  Do not submit or retest this interaction as a record lane. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-fused-selected-softmax-full512-negative.md`.
- Latest strict128 source follow-up: adaptive bonus-row skipping is a closed
  negative. It preserved exact verification and passed the realistic cold gate,
  but the best adaptive lane reached only `109.5558044655227 tok/s` versus the
  same-build control at `112.02098406811635 tok/s`, with worse p10 and
  full-output speed. Do not full512-confirm or submit it. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-adaptive-bonus-row-negative.md`.
- Latest verifier-copy follow-up: deferred verifier pending-`h` copy
  (`LLAMA_MTP_DEFER_VERIFIER_PENDING_H_COPY=1`) is also a closed negative. A
  first paired screen had one attractive flag-on outlier (`118.10959835079939
  tok/s`), but the cross-over disproved it: control medians averaged
  `114.45317635681107`, flag-on medians averaged `112.421810001393`, with all
  lanes valid and `cached_tokens=0`. Do not full512-confirm or submit it.
  Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-defer-verifier-pending-h-copy-negative.md`.
- Latest verifier-design audit: exact LM-head candidate-vs-max has usable row
  plumbing in the narrow full-output MTP verifier shape, but it is not a
  current record lane. Exact speculative verification still needs the true
  target top token on mismatch, so the full-vocab max/challenger work remains
  unless a future design actually removes verifier rows or proves a cheaper
  exact candidate path. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-candidate-threshold-lmhead-no-go.md`.
- Latest selected-down rowpack follow-up: `ROWPACK=2` for the VDR2
  selected-down weighted-sum path is valid but rejected for the short-record
  metric. The strict128 screen looked mildly positive, but the full512
  cross-over lost primary tokens 1-100 versus controls while improving only
  full-output / wall throughput. Keep it as a possible service-lane idea, not
  a headline record path. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-vdr2-selecteddown-rowpack2-negative.md`.
- Latest profile refresh: the rebuilt baseline/profile run
  `gemma4-q8-gpu0-record-refresh-specprofile-strict128-20260630T002301Z`
  passed the fixed cold gate and `cached_tokens=0`, but is diagnostic only
  because profiling and `MAX_TOKENS=128` were enabled. It confirms the record
  identity is target/verifier-bound: target decode `38529.540 ms` versus draft
  `2665.342 ms`; target `process_ubatch_ms=36833.360`; sampled-ID extraction
  `1665.262 ms` is a backend read/sync boundary, not an integer-copy loop.
  Host sampler/accept bookkeeping remains negligible. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-record-refresh-specprofile.md`.
  Follow-up `LLAMA_SPEC_VERIFY_SYNC_PROFILE=1` timing showed the later
  accept-side `llama_synchronize(ctx)` is only `1.734 ms` total over `896`
  verifier calls (`0.002 ms/call`), so do not chase sampler-side sync cleanup
  as a record lever. The remaining credible target is real verifier graph cost
  or the backend sampled-output extraction boundary itself.
- Current context/service diagnostic split: the short-record recipe is now
  also the FA-on 32K/VMM service profile after a realistic-gate retest. The
  promoted row is `121.41411987308553 tok/s` with `FLASH_ATTN=on`,
  `CTX_SIZE=32768`, and `GGML_SYCL_ENABLE_VMM=1`; LocalMaxxing
  `cmqztiqdn02vnoe01egox6q3f`. For medium-long service, MTP with FA off
  remains useful through about `ctx24576` / `ctx25600`, degrades around
  `ctx26624`, and cliffs by `ctx27648`. For true
  `ctx32768`, enable `FLASH_ATTN=on`: the same MTP stack reached
  `~102.7-103.2 tok/s` after TTFT at `27648`, `28672`, and `32768` on the
  synthetic ~11K-token diagnostic, with `cached_tokens=0`. These are not
  LocalMaxxing headline records. Evidence:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-context-threshold-mtp-vs-nospec.md`.
- Current best non-duplicate Gemma code target is still verifier cost, but not
  by removing the bonus pipeline or by a naive candidate-threshold head scan.
  Work inside the existing target decode boundary only if it removes real
  verifier rows/full-vocab dot work or reduces the verifier MoE/kernel
  boundary. Bonus-preserving row-output designs remain interesting, but need a
  concrete exactness and cost argument before GPU time. See
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-verifier-next-target-audit.md`.
- Current synthetic diagnostic one-B70 best is `176.21623213048554 tok/s` after
  TTFT on row0 with `cached_tokens=0`, `1536` canary repeats / `6144` rows
  passed, LocalMaxxing `cmqwkedg303jeqr013z753j62`. Under the stricter
  2026-06-27 policy, this is diagnostic only. Its VDR2 setting does not
  transfer to the fixed cold suite and must not be submitted or advertised as
  real-world throughput.
- Start from `results/gemma4-26b-a4b-q8-b70/README.md`,
  `results/gemma4-26b-a4b-q8-b70/reproduce.md`, and
  `results/gemma4-26b-a4b-q8-b70/validity-gates.md`.
- Headline throughput must pass the fixed realistic final gate: each prompt
  once as a cold first response, `cached_tokens=0` every row, no prompt/KV
  cache reuse, no context checkpoints, no response reuse, no n-gram/history
  acceleration, and primary metric = median generated-token throughput for
  tokens 1-100 after TTFT across the suite. Do not use warmed n-gram/history
  rows, repeated-output continuation learning, prefix/cache reuse, context
  checkpoints, or any prior generated continuation as a record claim.
- Post-100 status: the reliable `>100 tok/s` barrier is broken. Do not spend
  more time on configuration-only repeats for this Gemma lane. The next
  plausible record attempt needs a real source-level verifier-cost reduction,
  especially a row-adaptive verifier-output design that preserves exactness, a
  head-only bonus path that preserves the current pipeline, or additional
  verifier MoE boundary reduction beyond selected-down fusion.

Historical / service targets:

- MiniMax M2.7 INT4 AutoRound on 4x Intel Arc Pro B70 32GB.
- Preserve answer quality while improving single-session decode, context,
  prefill, and eventually concurrent-session throughput.
- Do not use power-limit or overclocking changes as optimization paths.

Secondary targets:

- Qwen3.6 27B Q4_0 GGUF and FP8 on B70.
- MiniMax M2.7 GGUF remains useful as a capacity/quality comparison but is not
  the current speed path.

## Current Promoted MiniMax State

Current validated structured-output fast lane:

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Hardware: 4x Intel Arc Pro B70 32GB
- Engine: local vLLM/XPU `0.20.1-local`, TP4
- Backend stack: Level Zero/XPU, llm-scaler INT4 MoE kernels, forced XPU graph
  with communicator capture no-op
- Task: constrained simple HTML, `skeleton_status_html`
- Result: `94.406 tok/s` effective accepted output, `94.692 tok/s` post-first
- Quality gate: `30/30` accepted, `0` rejects, `100%` first-attempt pass
- LocalMaxxing: `cmphg048s00mppc0192sahyug`
- Note: `notes/2026-05-22-minimax-structured-fast-lane-regex2.md`
- Payload: `data/localmaxxing-minimax-m27-autoround-structured-regex2-20260522.payload.json`

Important caveat:

- This is a constrained structured-output lane. It does not prove unconstrained
  free-form website generation is clean on the forced XPU graph path.
- Structured JSON cross-check passed `9/9` with `0` rejects at `87.956 tok/s`
  and stable parsed JSON hashes.

Current older strict long-run MiniMax baseline:

- p512/n1536, ctx2048, batch 1
- Result: `89.314195 tok/s` output, `119.085594 tok/s` total
- LocalMaxxing: `cmpct6t4m007fnw01yjdtlcs4`
- Repro folder: `repro/minimax-m27-b70-89tps-20260520/`

Current fresh Ubuntu 24 deployment repro:

- Date: 2026-05-23
- Purpose: reproduce the deployable OpenAI-compatible vLLM endpoint on a mostly
  fresh Ubuntu 24.04 host with 4x B70s.
- Model: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`
- Endpoint: vLLM OpenAI-compatible server on `0.0.0.0:8000`
- Served context default: `32768` via `/home/steve/bin/minimax-vllm-serve` and
  `repro/minimax-m27-b70-110tps-ubuntu24-20260523/scripts/06-serve-openai-compatible.sh`
- Context used for the comparable smoke/quality lane: `2048`
- Quality gate: passed raw token-hash canaries, semantic suite, arithmetic
  repeat, and extended sixpack.
- Benchmark: `110.896 total tok/s`, `83.172 output tok/s` for p512/n1536.
- OpenAI endpoint context validation: `24576` started with
  `gpu_memory_utilization=0.95`, vLLM reported `25,344` GPU KV-cache tokens,
  prompt 24,400 / output 64 completed without OOM, and short decode remained
  `83.78-83.79 output tok/s` before/after the long-context request.
- After moving display to ASPEED VGA and booting with `xe.disable_display=1`,
  `32768` started successfully, vLLM reported `33,792` GPU KV-cache tokens,
  prompt `32408` / output `64` completed without OOM, and warm short decode was
  `84.12 output tok/s`. `33792` was tried but did not expose `/v1/models`
  within the wait window and is not promoted. Detailed note:
  `notes/2026-05-23-b70-display-disable-32768-context.md`. LocalMaxxing:
  `cmpj1fmvv001hqr01oj4hiu3d` (`APPROVED`).
- PCIe/prefill follow-up on 2026-05-23:
  `notes/2026-05-23-current-host-pcie4-prefill-check.md`.
  Current host upstream links are PCIe4 x16 (`16.0 GT/s`, width 16) while the
  cards advertise PCIe5 capability. XCCL broad allreduce measured `13.79 GB/s`
  at 256 MiB versus the older `27.88 GB/s` reference, making PCIe4 fabric
  bandwidth a credible explanation for most of the `89 -> 83` strict decode
  delta: `13.79 / 27.88 = 0.494`, roughly half the older bandwidth, while
  `83.8 / 89.314 = 0.938`, about a 6% end-to-end decode drop. Live endpoint
  prefill measured about `1.7k-1.8k tok/s` with `max_tokens=1` prompt-heavy
  requests. Keep warm and cold numbers separate; the older repro had a
  `69.33` output tok/s first post-reboot pass and `88.72` output tok/s warm
  rerun.
- Repro folder:
  `repro/minimax-m27-b70-110tps-ubuntu24-20260523/`
- Human deployment guide: `docs/b70-minimax-ubuntu24-deployment.md`
- Docs index: `docs/README.md`
- Model/community recipe index: `docs/model-recipes.md`
- Community results/build notes: `docs/community-results.md`
- Intel feedback: `docs/intel-b70-minimax-feedback-20260523.md`
- Lessons learned:
  `repro/minimax-m27-b70-110tps-ubuntu24-20260523/notes/learnings-20260523.md`

This fresh deployment is not the fastest output-token lane known in the repo.
Treat it as the current best documented "install from a fresh system and serve
on the LAN" baseline.

Current session-cache / long-context research state:

- Production c1 service docs:
  `docs/minimax-production-c1-service.md`
- Systemd unit source:
  `deploy/systemd/minimax-vllm.service` for the localhost backend and
  `deploy/systemd/minimax-openai-frontdoor.service` for the no-auth LAN
  OpenAI-compatible frontdoor.
- Service installer:
  `scripts/install-minimax-vllm-service.sh`
- LAN frontdoor:
  `scripts/openai-lan-frontdoor.py`; public URL remains
  `http://<server-lan-ip>:8000/v1`, backend is `http://127.0.0.1:18080`,
  and auth is intentionally `none`.
- Production health and benchmark helpers:
  `scripts/minimax-prod-health.py`,
  `scripts/minimax-prod-benchmark.py`
- Current service-managed c1 LocalMaxxing result:
  `cmpm35jsa0003rt01zghtmwip`, prompt `32264`, output `64`, `63.91`
  output tok/s after TTFT, approximate prefill `1382.57` tok/s, TTFT
  `23.336 s`.
- Research folder: `experiments/minimax_xpu_kv_offload/`
- Start with: `experiments/minimax_xpu_kv_offload/REPRODUCE.md`
- Artifact index: `experiments/minimax_xpu_kv_offload/ARTIFACTS.md`
- Operations note:
  `experiments/minimax_xpu_kv_offload/notes-20260525-session-cache-operations.md`
- Profile switcher:
  `experiments/minimax_xpu_kv_offload/scripts/switch_session_cache_profile.sh`
- Status helper:
  `experiments/minimax_xpu_kv_offload/scripts/session_cache_status.sh`
- c1 remains production: `32768`, `max_num_seqs=1`, no CPU KV offload.
- c2 is the current known-good RAM-backed session-cache profile for two parked
  `32768`-token window sessions. The near-full strict ladder passed two
  `32474`-prompt-token sessions (`64948` combined) with exact expected-word
  matches and second-pass reload TTFT of `0.668-1.232 s`. A smaller live ops
  smoke with two `22540`-token fact-word sessions matched exact output hashes
  across passes; treat that as an operations canary, not the target context
  ceiling.
- c4/c8 are still research. Earlier c4/c8 ladders produced useful results, and
  c4/c8 sustained small-context warmed total decode was about `110 tok/s`, but
  live c4 service switching later hit a second-pass waiting/deferred stall and
  `UR_RESULT_ERROR_DEVICE_LOST` during vLLM block-table copy to GPU.
- TurboQuant is experimental. The patch
  `patches/vllm-turboquant-xpu-workspace-fallback-20260525.patch` gets past
  the first XPU locked-workspace crashes, and `turboquant_k8v4` can report
  about `80128` GPU KV tokens at 32K. It remains much slower than the
  FP16-family KV baseline and does not provide true 196K active context.
- Dirty live-source snapshots are tracked for audit:
  `patches/vllm-live-src-snapshot-20260525.patch` and
  `patches/llm-scaler-live-src-snapshot-20260525.patch`. These capture the
  originating host's broad local source deltas after the current experiments;
  they are not clean upstream-ready patches.
- Full `196608` active context is not solved. The current exact-quality path is
  CPU-paged attention, documented in
  `experiments/minimax_xpu_kv_offload/notes-20260525-cpu-paged-attention-design.md`.

## Quality Rules

Do not promote a speed result unless quality is preserved.

For low-level MiniMax performance changes, use the strict gates already in the
repo:

- raw145 exact token hashes at n64 and n256
- semantic canaries
- arithmetic repeat
- extended sixpack

For practical task lanes:

- validate generated output structurally, not just token speed
- count rejected attempts against effective throughput
- keep raw outputs and result JSON under `/home/steve/bench-results/...`
- label constrained-output results as constrained; do not present them as
  unconstrained general generation quality

## Key Repro Paths

Start here on a fresh machine:

- `AGENTS.md`
- `docs/current-reproducibility-map.md`
- `docs/b70-minimax-ubuntu24-deployment.md`
- `repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md`
- `repro/minimax-m27-b70-110tps-ubuntu24-20260523/scripts/`
- `experiments/minimax_xpu_kv_offload/REPRODUCE.md`
- `experiments/minimax_xpu_kv_offload/ARTIFACTS.md`
- `repro/minimax-m27-b70-89tps-20260520/README.md`
- `repro/minimax-m27-b70-89tps-20260520/scripts/00-install-system-deps.sh`
- `repro/minimax-m27-b70-89tps-20260520/scripts/01-download-model.sh`
- `repro/minimax-m27-b70-89tps-20260520/scripts/02-build-stack.sh`
- `repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh`
- `repro/minimax-m27-b70-89tps-20260520/patches/`

Important notes:

- The 2026-05-23 repro is the best starting point for building a working
  endpoint from a fresh Ubuntu 24 system. It includes low-RAM SSD swap handling,
  a LAN bind server script, and Intel-facing failure notes.
- The repro folder is for the `89 tok/s` strict baseline, not the latest
  `94 tok/s` constrained HTML lane.
- The latest structured regex2 fix is recorded as a patch in
  `patches/minimax-website-structured-regex2-20260522.patch`.
- For the latest `94 tok/s` structured regex2 lane, use the focused public
  runner at `scripts/run-minimax-structured-skeleton-quality.py`. The broader
  local lab harness has more exploratory options, but this runner is the
  public reproducible harness for the promoted constrained HTML lane.

## Known Good Runtime Shape

Typical promoted environment flags include:

```bash
source repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh
unset VLLM_XPU_CUDAGRAPH_PARTITION_COLLECTIVES || true
unset VLLM_XPU_CUDAGRAPH_STATIC_INPUT_COPY || true
```

For the structured HTML fast lane:

```bash
python scripts/run-minimax-structured-skeleton-quality.py \
  --mode graph \
  --warmup-runs 1 \
  --repeat 30 \
  --retry-until-pass 5 \
  --max-tokens 96 \
  --max-model-len 4096 \
  --max-num-batched-tokens 512
```

Expected regex2 result class:

- `30/30` accepted
- `0` rejected attempts
- output throughput around `94 tok/s` after warmup on matching hardware

## What Is Not Fully Solved

- Unconstrained free-form website output on the forced XPU graph path can still
  corrupt or degrade. Keep validating practical tasks.
- JSON structured lanes are better than free-form but can run below the HTML
  fast lane; use parsed JSON validation and count retries.
- True active-context overflow is not ready. CPU KV offload works as a
  session-cache/reload path for contexts that individually fit in GPU KV; it
  does not yet let one exact-attention request exceed live GPU KV.
- c4/c8 are not production-ready. They have useful ladder data, but c4 live
  operations hit a scheduler stall and a Level Zero device-lost path.
- Larger prefill chunks such as 1024 tokens can trigger Intel `ocloc`/IGC
  compiler failures on this stack; keep `max_num_batched_tokens=512` unless
  testing that specifically.
- Generic in-place allreduce thresholds were usually slower. Favor exact
  shape/dtype fusion with quality proof.

## Optimization Directions

Best next work:

- Expand validated practical tasks while keeping the 90+ tok/s lane.
- Build reliable prefill/context measurements without lowering decode quality.
- Long-context/concurrency RAM-overflow work is now tracked as a separate
  research lane in `experiments/minimax_xpu_kv_offload/`. Keep the stable 32K
  endpoint as the fallback. The initial CUDA-only CPU KV offload blocker was
  moved forward with an XPU worker prototype. That prototype can move KV blocks
  through pinned host RAM and supports session-cache/reload behavior, but the
  active request still needs its working KV in live GPU memory. The next real
  task for full context is CPU-paged attention, not another launch-flag change.
- Next context/speed options are captured in
  `notes/2026-05-23-minimax-context-speed-next-options.md`. Best first
  candidate is FP8 KV cache (`--kv-cache-dtype fp8`, optionally
  `--calculate-kv-scales`) at 32K, then 49K/65K only if exact and semantic
  quality gates pass. TurboQuant is now exposed in this vLLM build, including
  XPU routing, but should be treated as experimental; upstream guidance favors
  FP8 KV as the default and `turboquant_4bit_nc` only for memory pressure.
  N-gram speculation remains low priority for MiniMax because the local
  historical result was strongly negative, though it helped Qwen FP8.
- Endpoint-facing measurement script:
  `scripts/measure-openai-endpoint-metrics.py`. It uses `/v1/completions`
  streaming plus vLLM `/metrics` deltas to capture TTFT, e2e, output tok/s,
  total tok/s, VRAM snapshots, and a conservative prefill lower-bound without
  changing server settings. First p510/n1536 32K endpoint artifact:
  `data/minimax-m27-openai-endpoint-metrics-32k-20260524.json`; measured
  `85.453` output tok/s after first streamed chunk, `111.635` total tok/s,
  `351.068 ms` vLLM TTFT, and `1445.634 tok/s` conservative prefill
  lower-bound. A LocalMaxxing payload with TTFT was prepared at
  `data/localmaxxing-minimax-m27-autoround-openai-32k-endpoint-metrics-20260524.payload.json`,
  but POST attempts returned HTTP 502; retry later.
- TurboQuant repro script:
  `scripts/repro-minimax-turboquant-xpu-workspace-bug.sh`. The current
  workspace fallback patch is tracked at
  `patches/vllm-turboquant-xpu-workspace-fallback-20260525.patch`; after the
  patch, `turboquant_k8v4` can answer strict-word canaries at about 8K and
  32.5K prompt sizes and reports about `80128` GPU KV tokens at 32K, but decode
  is much slower than the normal FP16-family KV lane.
- Speed recovery policy:
  `notes/2026-05-23-speed-recovery-quality-plan.md`. Do not promote 90+ tok/s
  graph/runtime paths unless exact-token, semantic, arithmetic, and practical
  quality gates pass.
- Debug c4/c8 service-mode failures with small canaries before trying long
  sustained decode. c2 is the current safer RAM-backed lane.
- Continue lower-level fusion only where math is exactly preserved:
  Q/K variance allreduce plus RMS apply, hidden allreduce plus residual/RMSNorm,
  MoE output plus epilogue, and final projection/lm-head boundaries.
- Mine llm-scaler for ideas, but require strict quality gates before promotion.

Avoid:

- claiming constrained decode as unconstrained quality
- comparing AutoRound INT4 as equivalent to Q4_0/FP8 without separate quality
  checks
- disabling clones/allreduces broadly without exact shape and quality proof
- power tuning as the explanation for speed

## GitHub And LocalMaxxing

Use whichever GitHub write path is configured for the environment, and record
the commit IDs in the final response. On this host, local git push over the
installed deploy key has been used successfully.

Significant benchmark results should be submitted to LocalMaxxing with payloads
and responses recorded under `data/`.

Recent important LocalMaxxing IDs:

- MiniMax structured regex2: `cmphg048s00mppc0192sahyug`
- MiniMax strict p512/n1536 high: `cmpct6t4m007fnw01yjdtlcs4`
- MiniMax OpenAI 32K context endpoint: `cmpj1fmvv001hqr01oj4hiu3d`
- JSON gated c1 practical task: `cmpgv9p9j007qpc01oq5zqhdg`
- JSON c1 2k-context follow-up: `cmpgx0yrb009fpc0183xjri4j`

## Models Expected On Disk

Main models of interest:

- `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Qwen3.6 27B Q4_0 GGUF
- Qwen3.6 27B FP8
- MiniMax M2.7 GGUF/UD-IQ4_XS for comparison

The model weights themselves are not in GitHub. Use the repro download scripts
and local Hugging Face cache conventions from the repro folder.

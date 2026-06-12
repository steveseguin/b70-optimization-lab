# Current Promoted Results

Date: 2026-06-12

## Qwen3.6 35B-A3B Quark W8A8 INT8

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

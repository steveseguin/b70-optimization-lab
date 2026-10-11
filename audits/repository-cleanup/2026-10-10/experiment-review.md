# Experiment learning review — 2026-10-10

This catalog gives every one of the **37 experiment areas** a source-backed outcome, useful lesson, validity limit and condition for revisiting it. It adds no performance record or launch authorization. [CURRENT.md](../../../CURRENT.md) owns today’s gates; scientific reads are pinned to commit `8c4505c311ba4c98fb1edcea0d22e2137a739997`.

**Read scope:** 67 distinct sources were semantically reviewed (69 area/source references), some only in the explicitly recorded sections. The mechanical inventory contains 23,755 documents, including 3,769 Markdown/RST narratives, 1,804 text receipts and 18,182 JSON/config documents. **Inventory is not a claim that all these files, campaigns or raw logs were read.**

The [machine-readable catalog](experiment-review.json) preserves every reviewed path, base-blob hash, full/partial read scope, delegated reviewer, per-area inventory count and retained evidence path. Its ignored compressed inventory is a local metadata artifact; committed counts and digests identify it. 847 documents lie in generated/vendor locations. Symlinks and Git internals were not traversed. Canonical sources outside `experiments/` are listed as reviewed evidence but excluded from the inventory denominator.

Later storage notes have a separately labeled working-tree identity. [Gemma](../../../patches/gemma4-26b-a4b-q8-b70/SOURCE-ARCHIVE.md) and [Laguna](../../../patches/laguna-s-2.1-xpu-b70/SOURCE-ARCHIVE.md) preserve archived source bytes with restore maps. Historical paths in frozen receipts remain restoration destinations. Neither source recovery nor this review proves the old binary is reproducible.

No live process, model or GPU was checked. Every gate below is recorded state at `8c4505c31`, including the four-card third-incident halt and Turin’s separate ownership, 15 GB budget and lane-specific admission. Later owner receipts or host-state updates can supersede this snapshot: consult the current CURRENT.md before acting. Old service/reboot instructions in historical source notes do not grant present authorization.

## Lessons worth carrying forward

- A valid component is only one gate: fresh capture, lifecycle, full-model exactness and representative workload can fail independently. See [minimax_ar_fused_rms_xpu](#minimax_ar_fused_rms_xpu), [qwen35-4b-b70](#qwen35-4b-b70), [qwen27_graphsafe_flash_attention](#qwen27_graphsafe_flash_attention).
- Measure the production bottleneck and fair baseline before endpoint work. Launch reduction, extra parallelism and speculative acceptance can all cost more than they save. See [qwen27_fused_postattn_rms_w4a16](#qwen27_fused_postattn_rms_w4a16), [laguna-s-2.1-xpu-b70](#laguna-s-21-xpu-b70), [deepseek-v4-flash-reap-xpu-b70](#deepseek-v4-flash-reap-xpu-b70), [ornith-15-b70](#ornith-15-b70).
- Quality failures and missing receipts remain visible after later successes. Fast corrupt output, a skipped NULL and an empty ENOSPC summary cannot be promoted. See [minimax-m27-reap-autoround-vllm](#minimax-m27-reap-autoround-vllm), [gemma4-26b-a4b-q8-b70](#gemma4-26b-a4b-q8-b70), [ltx25-b70](#ltx25-b70), [minicpm5-2b-b70](#minicpm5-2b-b70).
- Keep cache state, pacing, first-use, concurrency and metric interval definitions beside every number; a plausible rate can describe a different experiment. See [rapid-model-snapshots-b70](#rapid-model-snapshots-b70), [ltx25-b70](#ltx25-b70), [laguna-s-2.1-xpu-b70](#laguna-s-21-xpu-b70), [qwen38-flash-next-fp8-b70](#qwen38-flash-next-fp8-b70).
- Source-byte recovery, binary identity, complete Git ancestry and independent runtime reproduction are different guarantees. See [gemma4-26b-a4b-q8-b70](#gemma4-26b-a4b-q8-b70), [laguna-s-2.1-xpu-b70](#laguna-s-21-xpu-b70), [own-xpu-runtime](#own-xpu-runtime).
- Full source access and complete answers are different. Preserve omissions, failed tasks and unused holdouts; do not hide a wrong ownership join behind preserved numeric details. See [lab-navigator-20261007](#lab-navigator-20261007), [project-decision-recall-20261007](#project-decision-recall-20261007), [qwen38-27b-b70](#qwen38-27b-b70), [local-coding-worker](#local-coding-worker).
- Checkpoint names and ability to load are insufficient admission: census actual tensor types, memory residency, output contract and host budget first. See [deepseek-v4-flash-autoround-vllm](#deepseek-v4-flash-autoround-vllm), [qwen38-flash-next-ud-iq3xxs-b70](#qwen38-flash-next-ud-iq3xxs-b70), [minicpm5-2b-b70](#minicpm5-2b-b70), [minimax-h3-b70](#minimax-h3-b70).

## Area coverage

| Area | Narratives | All inventoried documents | Reviewed source references |
| --- | ---: | ---: | ---: |
| [deepseek-v4-flash-autoround-vllm](#deepseek-v4-flash-autoround-vllm) | 14 | 16 | 2 |
| [deepseek-v4-flash-reap-xpu-b70](#deepseek-v4-flash-reap-xpu-b70) | 111 | 263 | 2 |
| [gemma4-12b-int4-autoround-vllm](#gemma4-12b-int4-autoround-vllm) | 1 | 7 | 1 |
| [gemma4-26b-a4b-q8-b70](#gemma4-26b-a4b-q8-b70) | 277 | 282 | 5 |
| [lab-navigator-20261007](#lab-navigator-20261007) | 2 | 12 | 1 |
| [laguna-s-2.1-fp8-kv-xpu-b70](#laguna-s-21-fp8-kv-xpu-b70) | 6 | 12 | 1 |
| [laguna-s-2.1-xpu-b70](#laguna-s-21-xpu-b70) | 356 | 375 | 6 |
| [local-coding-worker](#local-coding-worker) | 54 | 793 | 1 |
| [ltx25-b70](#ltx25-b70) | 454 | 10560 | 2 |
| [minicpm5-2b-b70](#minicpm5-2b-b70) | 7 | 40 | 2 |
| [minimax-h3-b70](#minimax-h3-b70) | 20 | 74 | 2 |
| [minimax-m27-reap-autoround-vllm](#minimax-m27-reap-autoround-vllm) | 26 | 32 | 4 |
| [minimax_ar_fused_rms_xpu](#minimax_ar_fused_rms_xpu) | 0 | 0 | 4 |
| [minimax_moe_tuned_configs](#minimax_moe_tuned_configs) | 1 | 7 | 1 |
| [minimax_pair_argmax_xpu](#minimax_pair_argmax_xpu) | 1 | 1 | 1 |
| [minimax_qk_rms_xpu](#minimax_qk_rms_xpu) | 1 | 1 | 1 |
| [minimax_qk_rms_xpu_ipc](#minimax_qk_rms_xpu_ipc) | 1 | 1 | 1 |
| [minimax_xpu_kv_offload](#minimax_xpu_kv_offload) | 18 | 25 | 1 |
| [model-intake-resume-20261007](#model-intake-resume-20261007) | 0 | 3 | 2 |
| [muse-glimmer-30b-b70](#muse-glimmer-30b-b70) | 64 | 196 | 1 |
| [ornith-15-b70](#ornith-15-b70) | 80 | 549 | 1 |
| [own-xpu-runtime](#own-xpu-runtime) | 23 | 171 | 3 |
| [project-decision-recall-20261007](#project-decision-recall-20261007) | 3 | 48 | 1 |
| [qwen27-dflash-sycl-b70](#qwen27-dflash-sycl-b70) | 65 | 82 | 1 |
| [qwen27_fused_postattn_rms_w4a16](#qwen27_fused_postattn_rms_w4a16) | 1 | 1 | 1 |
| [qwen27_graphsafe_flash_attention](#qwen27_graphsafe_flash_attention) | 346 | 848 | 2 |
| [qwen35-4b-b70](#qwen35-4b-b70) | 16 | 464 | 1 |
| [qwen35-9b-b70](#qwen35-9b-b70) | 35 | 77 | 2 |
| [qwen36-27b-autoround-int4-b70](#qwen36-27b-autoround-int4-b70) | 210 | 392 | 1 |
| [qwen36-27b-mtp-gguf-q4-b70](#qwen36-27b-mtp-gguf-q4-b70) | 101 | 208 | 1 |
| [qwen36-27b-q8-gguf-b70](#qwen36-27b-q8-gguf-b70) | 26 | 49 | 1 |
| [qwen36-35b-quark-int8-b70](#qwen36-35b-quark-int8-b70) | 1 | 1 | 1 |
| [qwen38-27b-b70](#qwen38-27b-b70) | 961 | 6610 | 5 |
| [qwen38-flash-next-fp8-b70](#qwen38-flash-next-fp8-b70) | 477 | 1524 | 2 |
| [qwen38-flash-next-ud-iq3xxs-b70](#qwen38-flash-next-ud-iq3xxs-b70) | 6 | 18 | 2 |
| [rapid-model-snapshots-b70](#rapid-model-snapshots-b70) | 3 | 12 | 1 |
| [xpu_level_zero_peer_probe](#xpu_level_zero_peer_probe) | 1 | 1 | 2 |

## deepseek-v4-flash-autoround-vllm

Determine whether the Intel W4A16 checkpoint can run fully resident on four B70s.

**Outcome:** Deployment was rejected before download: 46 shards total 152,946,418,392 bytes, a 35.61
GiB/card weight-only floor versus 32 GB cards.

**What worked:** Direct shard accounting corrected the misleading 303.7 GB API storage figure. An
architecture class existing in vLLM was checked separately from support for this quantization.

**Failures and uncertainty:** Weights exceed device capacity before KV, graph and scratch
allocations; the exact AutoRound checkpoint also lacked the documented runtime support.

**Limits:** A metadata/fit decision, not model inference or a measured speed. The smaller K160
derivative is a different lane and cannot inherit this model identity.

**Worth revisiting when:** A smaller compatible checkpoint, more VRAM, or an explicitly separate
expert-offload design with measured latency and quality.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/deepseek-v4-flash-autoround-vllm/README.md](../../../experiments/deepseek-v4-flash-autoround-vllm/README.md) — full.
- [experiments/deepseek-v4-flash-autoround-vllm/notes/2026-05-31-deployment-decision.md](../../../experiments/deepseek-v4-flash-autoround-vllm/notes/2026-05-31-deployment-decision.md) — full.

## deepseek-v4-flash-reap-xpu-b70

Optimize an explicitly identified K160 derivative and target-verified speculative decoding on four
B70s.

**Outcome:** Historical target-verified DSpark7 record: 80.820052 tok/s; nonspeculative direct-MoE
anchor about 43.77 tok/s.

**What worked:** More verifier work per launch improved utilization. Exact fixed-geometry
command-list substrate and replay corpora remain reusable even though their endpoint speed did not
improve.

**Failures and uncertainty:** Submission collapse did not remove device execution time; tile-major
prepacking fragmented coalescing, and inexact MHC fusion changed about half the tokens. A small
EAGLE corpus overfit: offline hybrid acceptance rose only 2.8%, insufficient against extra draft
cost.

**Limits:** K160 is not the unmodified official checkpoint. The closeout rooflines are model
assumptions, not measurements or a permanent impossibility theorem. Old claims that the lane is
exhausted do not override the standing optimization policy. Some held-out packs were exposed to
broad searches.

**Worth revisiting when:** A mechanism reducing actual device work, or independently justified draft
training data that clears a predeclared acceptance-versus-cost gate; regenerate uncontaminated
evaluation before promotion.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/deepseek-v4-flash-reap-xpu-b70/README.md](../../../experiments/deepseek-v4-flash-reap-xpu-b70/README.md) — full.
- [experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-21-deepseek-v4-flash-frontier-closeout.md](../../../experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-21-deepseek-v4-flash-frontier-closeout.md) — full.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [patches/deepseek-v4-flash-reap-xpu-b70/README.md](../../../patches/deepseek-v4-flash-reap-xpu-b70/README.md).
- [results/deepseek-v4-flash-k160-b70/README.md](../../../results/deepseek-v4-flash-k160-b70/README.md).

## gemma4-12b-int4-autoround-vllm

Bring up text/image AutoRound inference and characterize context, concurrency and graph execution.

**Outcome:** The model-loader backport enabled text and image smoke tests. Historical c8/32K graph
profile improved short-request throughput; c12 burst load lost the device.

**What worked:** Transformers/model-registry/helper compatibility had to be repaired together. Graph
execution helped decode while 32K prefill stayed around 22.28 s TTFT; separating wall time from
post-first-text rates avoided claiming a prefill improvement.

**Failures and uncertainty:** One of 32 scheduled soak cycles returned a wrong copy phrase; later
passing repeats do not erase it. A final-interval harness bug generated rapid extra cycles. Explicit
zero audio/video limits broke dummy multimodal profiling.

**Limits:** Old production, LAN-listener and prefix-cache statements are historical.
Repeated/prefix-cached and synthetic throughput is not a present cold-suite headline; coalesced
long-prompt streaming made inter-token rates unusable.

**Worth revisiting when:** Use a current compatible loader, preserved failed canary, fixed soak
scheduling and a preregistered cold quality/concurrency gate; study prefill separately from decode.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/gemma4-12b-int4-autoround-vllm/README.md](../../../experiments/gemma4-12b-int4-autoround-vllm/README.md) — lines 1-108, 284-308, 482-580, 699-757, 908-940.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [patches/vllm-gemma4-unified-backport-b70-20260607.patch](../../../patches/vllm-gemma4-unified-backport-b70-20260607.patch).

## gemma4-26b-a4b-q8-b70

Improve the Q8 model without conflating decode records, prefill experiments and sampled-output
extraction.

**Outcome:** The accepted result packet remains the record authority. Two reviewed followups are
useful negatives: direct sampled egress failed strict value parity, and deleting an unused
local-memory declaration produced no prefill win.

**What worked:** A stricter null-value test exposed false reassurance from skipped NULL samples.
Mirrored prefill waves exposed noise that looked like a small single-run gain.

**Failures and uncertainty:** Direct egress returned -1 where copied outputs were valid, with
356/355 mismatches in variants; skipping the copy could leave logits missing. KQ no-LSM comparison
was about -0.0336% mean / +0.0669% median with alternating wave direction.

**Limits:** The 120.303 cleanup sanity run used a 64-token cap and 1-50 metric, not the record
protocol. The source snapshot is recoverable, but an absent original binary hash prevents claiming
exact historical binary identity.

**Worth revisiting when:** Bind the real graph sample producer and pass zero strict mismatches
before removing egress copies; revisit local-memory declarations only with compiler evidence that
they change occupancy.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

**Storage:** Historical source paths listed by the archive manifest are exact restore destinations.
Use SOURCE-ARCHIVE.md before a historical command that consumes an archived file; the archive
changes storage, not experimental status.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/gemma4-26b-a4b-q8-b70/README.md](../../../experiments/gemma4-26b-a4b-q8-b70/README.md) — full.
- [experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-direct-sampled-egress-negative.md](../../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-direct-sampled-egress-negative.md) — full (delegated to patch_audit).
- [experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-kq-reg-bcast-no-kq-lsm-negative.md](../../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-kq-reg-bcast-no-kq-lsm-negative.md) — full (delegated to patch_audit).
- [data/gemma4-global-fattn-kq-reg-bcast-no-kq-lsm-comparison-20260702.json](../../../data/gemma4-global-fattn-kq-reg-bcast-no-kq-lsm-comparison-20260702.json) — comparison fields and validity evidence (delegated to patch_audit).
- [patches/gemma4-26b-a4b-q8-b70/SOURCE-ARCHIVE.md](../../../patches/gemma4-26b-a4b-q8-b70/SOURCE-ARCHIVE.md) — full.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [results/gemma4-26b-a4b-q8-b70/README.md](../../../results/gemma4-26b-a4b-q8-b70/README.md).
- [patches/gemma4-26b-a4b-q8-b70/README.md](../../../patches/gemma4-26b-a4b-q8-b70/README.md).
- [patches/gemma4-26b-a4b-q8-b70/source-archive-manifest.json](../../../patches/gemma4-26b-a4b-q8-b70/source-archive-manifest.json).

## lab-navigator-20261007

Retrieve original commit-pinned evidence with verifiable paths, hashes and visible omissions.

**Outcome:** Frozen search retrieved every required passage for 4/6 development and 4/6 held-out
questions; held-out file discovery alone did not ensure passage completeness.

**What worked:** Exact Git/source/excerpt binding, complete-source reads, explicit included files
and omitted-line ranges make review auditable. The index is disposable while original evidence is
retained.

**Failures and uncertainty:** Flash-Next and worker evidence were among misses. Budgeted excerpts
can omit an oversized explicit-only source; a complete reader-side log is not proof that a model saw
untruncated tool output.

**Limits:** Retrieval, citation integrity and answer completeness are separate. These are
CPU/source-access checks, not local-model memory, general intelligence or speed qualification.

**Worth revisiting when:** A real unanswered coordinator question or demonstrated scale requirement;
first open the missing original source and verify displayed coverage rather than tune on frozen
holdouts.

**Gate at audit source commit `8c4505c31`:** Useful CPU source-navigation tool. CURRENT parks
worker/memory integration; historical host snapshots are not live authority.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/lab-navigator-20261007/README.md](../../../experiments/lab-navigator-20261007/README.md) — full.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [experiments/lab-navigator-20261007/evaluation/README.md](../../../experiments/lab-navigator-20261007/evaluation/README.md).
- [experiments/lab-navigator-20261007/results](../../../experiments/lab-navigator-20261007/results).

## laguna-s-2.1-fp8-kv-xpu-b70

Test calibrated E4M3 KV as a separate Laguna model/runtime identity with its own target-only
teacher.

**Outcome:** Replicated target embedding removed a collective and yielded two exact endpoint
medians, 95.0193/95.8187 tok/s. Earlier FP8 versus BF16 screen was 4.132% slower while doubling KV
capacity.

**What worked:** Target calibrated scales and draft unit scales were audited separately. The lane
preserved the BF16 oracle and froze a new FP8 teacher instead of borrowing cross-precision
exactness.

**Failures and uncertainty:** Native page-32 component tests passed, but candidate and restored
page-64 control stalled in XCCL initialization; endpoint page-size speed remains unknown.

**Limits:** Compressed KV is separately scoped and no longer a default under current owner rules.
Component correctness and capacity are not a performance promotion; old reboot instructions do not
grant permission.

**Worth revisiting when:** Only with explicit compressed-KV authorization, healthy current host
admission, fresh exact FP8 teacher, four-rank scale/topology evidence and two fresh complete suites.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/laguna-s-2.1-fp8-kv-xpu-b70/README.md](../../../experiments/laguna-s-2.1-fp8-kv-xpu-b70/README.md) — full.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [experiments/laguna-s-2.1-fp8-kv-xpu-b70/patches](../../../experiments/laguna-s-2.1-fp8-kv-xpu-b70/patches).
- [experiments/laguna-s-2.1-fp8-kv-xpu-b70/notes/2026-07-27-replicated-embedding-page32-and-xccl-boundary.md](../../../experiments/laguna-s-2.1-fp8-kv-xpu-b70/notes/2026-07-27-replicated-embedding-page32-and-xccl-boundary.md).

## laguna-s-2.1-xpu-b70

Optimize INT4/BF16-KV target-verified DFlash while preserving metric, topology and long-context
identity.

**Outcome:** Conventional short-suite record retained at 125.461973 tok/s. Long-context graph/cutoff
experiments did not qualify a replacement; a 32K graph diagnostic differs 9/128 tokens and lacks a
completed corrected run.

**What worked:** Exact shared-elementwise fusions and segmented drafting improved the scoped record.
Pure-prefill chunks improved prompt latency separately from 32K decode. Component cost gates avoided
an expensive local-TP endpoint trial.

**Failures and uncertainty:** Local TP4 draft replication added 4.208694 ms versus only 1.239689 ms
collective savings, failing its net gate. Fixed-input inline-gather V2 retained a 176-token exact
prefix then diverged; V1 did not save the failing response, so its first divergence is unknown.

**Limits:** Legacy 102.971436 uses inclusive-event accounting; conventional value is 101.941721.
Interpolated crossover and correctness-failing cutoff rate are not scores. Different
attention/router DSO source identities cannot be represented by one HEAD. The original and restored
Git bundles preserve complete identical source-tip trees, but share a missing historical parent.
Passing git bundle verify did not establish full ancestry; strict fsck detected the inherited
limitation. The archive preserves rather than repairs it.

**Worth revisiting when:** Prove a different producer/consumer dependency or communication saving
without multiplying projection work; pass exact real-cycle and fresh endpoint gates before speed. A
new long-context mechanism must preserve the pinned oracle and audit replay.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

**Storage:** Historical source paths listed by the archive manifest are exact restore destinations.
Use SOURCE-ARCHIVE.md before a historical command that consumes an archived file; the archive
changes storage, not experimental status.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/laguna-s-2.1-xpu-b70/RESUME.md](../../../experiments/laguna-s-2.1-xpu-b70/RESUME.md) — lines 1-110.
- [experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-local-tp-emulated-dflash-preregistration.md](../../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-local-tp-emulated-dflash-preregistration.md) — full (delegated to patch_audit).
- [data/laguna-dflash-local-tp4-negative-20260801.json](../../../data/laguna-dflash-local-tp4-negative-20260801.json) — parity, component costs and failed net gate (delegated to patch_audit).
- [experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-target-inline-gathers-negative.md](../../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-target-inline-gathers-negative.md) — full (delegated to patch_audit).
- [data/laguna-target-inline-gathers-fixed-input-v2-negative-20260801.json](../../../data/laguna-target-inline-gathers-fixed-input-v2-negative-20260801.json) — full-model parity failure and retained response (delegated to patch_audit).
- [patches/laguna-s-2.1-xpu-b70/SOURCE-ARCHIVE.md](../../../patches/laguna-s-2.1-xpu-b70/SOURCE-ARCHIVE.md) — full.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [patches/laguna-s-2.1-xpu-b70/README.md](../../../patches/laguna-s-2.1-xpu-b70/README.md).
- [patches/laguna-s-2.1-xpu-b70/source-archive-manifest.json](../../../patches/laguna-s-2.1-xpu-b70/source-archive-manifest.json).

## local-coding-worker

Test whether a local model completes real repairs under independently checked acceptance criteria.

**Outcome:** The scoped 27B attempt made 12 requests in 114.54 s, no edits and no acceptance
submission: 0/1 repairs. Five original cases remain unused.

**What worked:** Pinned small snapshots, source preservation and baseline/fix CPU controls worked;
the wrapper kept accounting and graceful lifecycle receipts. This separates valid infrastructure
from unsuccessful model behavior.

**Failures and uncertainty:** The relevant function was visible by request 3, but inspection
continued; six tool outputs truncated. Outputs ended naturally below the cap, so the failure is not
established as token-cap or request-timeout exhaustion.

**Limits:** The scoped attempt uses a historical R276 identity and differs from earlier
full-repository trials; neither proves improvement, current package qualification or general coding
capability.

**Worth revisiting when:** A new justified task/protocol and independently frozen acceptance checks,
without retuning the failed task or consuming the five unused cases casually. Address
observation-to-edit behavior and display completeness first.

**Gate at audit source commit `8c4505c31`:** CURRENT explicitly parks further worker tuning and
memory integration. Preserve failed attempts and five unused cases.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/local-coding-worker/scoped-task-20261007/CLOSEOUT.md](../../../experiments/local-coding-worker/scoped-task-20261007/CLOSEOUT.md) — full.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [experiments/local-coding-worker/scoped-task-20261007/runtime-plan.json](../../../experiments/local-coding-worker/scoped-task-20261007/runtime-plan.json).
- [experiments/local-coding-worker/evaluation-20261007](../../../experiments/local-coding-worker/evaluation-20261007).

## ltx25-b70

Improve exact video generation, then coherent continuing-video delivery faster than playback.

**Outcome:** Accepted w93c-reference batch-1 packet97 recorded 1.308 s/clip, 126/126 exact. Later
145-frame continuation packet135 has an early unthrottled 52-period median of 5.2415 s and raw
747-period median of 5.553 s.

**What worked:** Explicit reference changes, parallel scheduling and exact per-clip checks made
gains reviewable. Separating client pacing from server work corrected a misleading sustained-speed
interpretation. Sealed copies recovered an empty source helper after ENOSPC.

**Failures and uncertainty:** Batch2/4 clips differ from batch1 despite exactness to their own
references. Disk-full progress-lock failure left an empty summary and truncated log; a preceding
completed campaign cannot fill that missing receipt. Packet138 prefetch has CPU tests but no native
overlap/peak measurement.

**Limits:** Early unthrottled, raw paced delivery and hold-free diagnostics are distinct metrics.
Seam/audio acceptance and portable independent replay remain open; larger-size and output-changing
arms do not inherit accepted-reference quality.

**Worth revisiting when:** After owner resolves current fault halt, admit native packet138 with
unchanged conditioning checks and memory/disk reserves; measure sustained delivery including scene
cuts and maintenance, then obtain separate visual/audio acceptance.

**Gate at audit source commit `8c4505c31`:** CURRENT: four-card GPU halt after third fault;
packet137 stopped, packet138 native qualification pending. Old resume/launch queues are superseded.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/ltx25-b70/RESUME.md](../../../experiments/ltx25-b70/RESUME.md) — lines 1-120.
- [results/ltx25-continuation-stream-pacing-2026-10-10.md](../../../results/ltx25-continuation-stream-pacing-2026-10-10.md) — full.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [experiments/ltx25-b70/data/resume-20261008/continuation138-build.json](../../../experiments/ltx25-b70/data/resume-20261008/continuation138-build.json).
- [experiments/ltx25-b70/data/stability-01-window-prereg.json](../../../experiments/ltx25-b70/data/stability-01-window-prereg.json).
- [experiments/ltx25-b70/recovery/20261010-continuation138-stream/LAUNCH.md](../../../experiments/ltx25-b70/recovery/20261010-continuation138-stream/LAUNCH.md).

## minicpm5-2b-b70

Establish an unchanged native BF16 reference before optimizing a new small model.

**Outcome:** Checkpoint loads, but baseline is unqualified and optimization never started. Publisher
sampling passed 5/6 objective checks; the neutral-system preset passed 4/6.

**What worked:** Frozen arithmetic, copy and format requirements stopped invalid promotion before
broad repeats. Exact input hashes and all-four-card postflight were retained.

**Failures and uncertainty:** Greedy arithmetic failed even at the larger budget. Neutral-system
JSON tasks returned explanatory prose or fenced JSON; correct values in wrong required format still
fail. Full fresh-process repeat and cache parity were never reached.

**Limits:** Evidence applies to these declared presets/runtime, not a universal checkpoint defect.
Loading, semantic plausibility and a passing smoke do not certify the baseline or speed.

**Worth revisiting when:** A materially justified preset/runtime change with a new preregistration
and preserved original failures; no prompt replacement or relaxed checker merely to pass.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/minicpm5-2b-b70/README.md](../../../experiments/minicpm5-2b-b70/README.md) — full.
- [experiments/minicpm5-2b-b70/data/qualification-decision.json](../../../experiments/minicpm5-2b-b70/data/qualification-decision.json) — full.

## minimax-h3-b70

Increase exact scheduling throughput for the owner-selected Comfy-Org fitted-AdaLN denoiser on
turin.

**Outcome:** The measured eight-clip batch is 396.6 s/clip, 32 matching hash checks and eight
repeats against this denoiser. The 800.8 s baseline is ledger-only; raw baseline receipts are
missing.

**What worked:** One process per card overcame nonoverlapping Python-thread execution. Persistent
decode workers reduced repeated load/setup; controlling encoder rate control and mux timestamps made
output files repeatable, beyond tensor parity.

**Failures and uncertainty:** Threaded two-card decode was only 1.01x. FP16 decode changes pixels
and two-process FP16 was not repeatable; it is not an exact default. An early 4 GiB cgroup limit
during a 27 GB load beside a build exhausted the 15 GiB host.

**Limits:** The lab did not produce the fit. Exact scheduling relative to Comfy-Org weights is not
losslessness versus the official model. Steps count sigma-grid points: 51 means 50 evaluations.
Clean-build/runtime and full independent publication evidence remain absent.

**Worth revisiting when:** Complete missing reconstruction/reference receipts and independent
full-suite repeat; pursue process scheduling/measurement with unchanged fp32 picture decode and
watchdog, not unaccepted arithmetic changes.

**Gate at audit source commit `8c4505c31`:** CURRENT: active turin optimization lane, source/model
acceptance resolved, recipe remains draft. GPU work only through smoke_h3.sh with memory watchdog
and fresh host ownership.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/minimax-h3-b70/README.md](../../../experiments/minimax-h3-b70/README.md) — lines 1-108.
- [CURRENT.md](../../../CURRENT.md) — full.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [repro/minimax-h3-pruned-bf16-tp2-b70-20261004/README.md](../../../repro/minimax-h3-pruned-bf16-tp2-b70-20261004/README.md).
- [experiments/minimax-h3-b70/data/2026-10-03-gates](../../../experiments/minimax-h3-b70/data/2026-10-03-gates).

## minimax-m27-reap-autoround-vllm

Evaluate a smaller REAP W4A16 MiniMax derivative while retaining the larger-model reference.

**Outcome:** Historical quality-gated 89.499223 tok/s remains preserved but was not reproduced
quality-valid from later live source. Later safe paths are about 83–85 tok/s; fast stale-cache
results are not promoted.

**What worked:** A stronger async-output check exposed all-zero/NUL generation in a cache that still
benchmarked 88.63 tok/s. Clean-weight ownership repair restored usable output, showing that similar
graph counts did not prove equal runtime state.

**Failures and uncertainty:** The f728 cache without owner repair is corrupt; adding the shim
returns about 83.32 tok/s. Signed-compact template specialization passed quality but regressed to
80.0069 versus restored 84.2293; branch removal did not remove the bottleneck.

**Limits:** Checkpoint pruning, model size and metric differ from the full MiniMax line. Historical
record preservation does not make a stale cache usable. Instruction-cache/compiler-scheduling
explanations for specialization remain hypotheses.

**Worth revisiting when:** A graph-safe clean-weight ownership path or measured MoE/QK work
reduction, followed by fresh async quality and repeated matched timing; never recover a number by
reviving the corrupt cache.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/minimax-m27-reap-autoround-vllm/README.md](../../../experiments/minimax-m27-reap-autoround-vllm/README.md) — full.
- [experiments/minimax-m27-reap-autoround-vllm/REPRO.md](../../../experiments/minimax-m27-reap-autoround-vllm/REPRO.md) — full.
- [experiments/minimax-m27-reap-autoround-vllm/notes/2026-06-01-f728-quality-speed-split.md](../../../experiments/minimax-m27-reap-autoround-vllm/notes/2026-06-01-f728-quality-speed-split.md) — full.
- [experiments/minimax-m27-reap-autoround-vllm/notes/2026-06-02-u4-specialization-reject.md](../../../experiments/minimax-m27-reap-autoround-vllm/notes/2026-06-02-u4-specialization-reject.md) — full.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [patches/vllm-reap-piecewise-static-range-and-b70-e192-configs-20260531.patch](../../../patches/vllm-reap-piecewise-static-range-and-b70-e192-configs-20260531.patch).
- [experiments/minimax-m27-reap-autoround-vllm/patches/llm-scaler-ws-signedcompact-specialization-rejected-20260602.patch](../../../experiments/minimax-m27-reap-autoround-vllm/patches/llm-scaler-ws-signedcompact-specialization-rejected-20260602.patch).

## minimax_ar_fused_rms_xpu

Fuse attention all-reduce, residual add and RMSNorm while preserving model output.

**Outcome:** Both integration shapes were rejected before promoted timing: the c10d helper passed
one strict screen then failed n256 repeat exactness; post-reduce-only failed n64.

**What worked:** device_group.group_name fixed the c10d lookup bug; unique_name belongs to another
registry. Standalone add/RMS microchecks were exact.

**Failures and uncertainty:** Correct local formula and deterministic output within one run did not
preserve fresh graph/model output. Keeping collective order in the narrower epilogue still failed.

**Limits:** No throughput survives the failed quality gate; the failed-check 9.52 tok/s is not a
benchmark. Outcomes live in root notes/data, not a local README.

**Worth revisiting when:** A materially different lowering with integrated arithmetic and
fresh-capture parity, before long timing.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [notes/2026-05-19-minimax-ar-fused-rms-c10d-repeatability-negative.md](../../../notes/2026-05-19-minimax-ar-fused-rms-c10d-repeatability-negative.md) — full.
- [notes/2026-05-19-minimax-attn-post-reduce-rms-xpu-quality-fail.md](../../../notes/2026-05-19-minimax-attn-post-reduce-rms-xpu-quality-fail.md) — full.
- [data/minimax-m27-ar-fused-rms-c10d-repeatability-negative-20260519.json](../../../data/minimax-m27-ar-fused-rms-c10d-repeatability-negative-20260519.json) — full.
- [data/minimax-m27-attn-post-reduce-rms-xpu-quality-fail-20260519.json](../../../data/minimax-m27-attn-post-reduce-rms-xpu-quality-fail-20260519.json) — full.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [experiments/minimax_ar_fused_rms_xpu](../../../experiments/minimax_ar_fused_rms_xpu).

## minimax_moe_tuned_configs

Isolate MiniMax tile/configuration effects without overwriting the live runtime.

**Outcome:** The old device-config alias was selected but failed raw145-n64 exactness. Controlled
default, tile, warp and stage candidates remain.

**What worked:** Isolated config folders preserve the accepted runtime; exact device filename and
nearest numeric-key behavior identify what actually executes.

**Failures and uncertainty:** A missing key 1 selects the nearest larger key, not defaults. The
README does not establish outcomes for every listed candidate.

**Limits:** Shape-specific configuration screens do not establish a portable optimum or new model
result.

**Worth revisiting when:** A new tile/warp/stage mechanism with a safe decode key, observed selector
activation, exact canary and matched endpoint comparison.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

**Closeout gap:** The alias rejection is documented, but not every candidate has a reviewed outcome.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/minimax_moe_tuned_configs/README.md](../../../experiments/minimax_moe_tuned_configs/README.md) — full.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [patches/minimax-moe-config-alias-quality-fail-20260626.md](../../../patches/minimax-moe-config-alias-quality-fail-20260626.md).

## minimax_pair_argmax_xpu

Reduce gathered local maximum-logit/token-ID pairs using a tiny SYCL helper.

**Outcome:** Default-off helper design preserves all_gather then pair reduction; no promoted
endpoint outcome is established by the local README.

**What worked:** Explicit pair gathering avoids the problematic B70/XCCL packed MAX reduction.

**Failures and uncertainty:** Standalone correctness, raw145 hashes, semantic repeats and adjacent
timing remain stated prerequisites rather than recorded passes.

**Limits:** A math-preserving design is not demonstrated correctness or speed.

**Worth revisiting when:** Only after a measured tail bottleneck warrants it: prove tie/ID semantics
and model parity, then matched p512/n1536 timing.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

**Closeout gap:** Only design/promotion gates found in local narrative; no outcome closeout.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/minimax_pair_argmax_xpu/README.md](../../../experiments/minimax_pair_argmax_xpu/README.md) — full.

## minimax_qk_rms_xpu

Test isolated Q/K RMS and RoPE helpers while keeping the release kernel wheel.

**Outcome:** Tested helpers were numerically valid but slower in the model: QK/RoPE moved 39.610585
to 35.681825 tok/s; plain var/apply remained below stock.

**What worked:** An independent extension avoided changing unrelated kernels. Compiler-specific
oneAPI 2025.3 matched the runtime ABI.

**Failures and uncertainty:** Swapping the whole _C wheel regressed other kernels; generic
latest/2026.0 environment caused an undefined SYCL symbol. Warmed reload improvement did not beat
stock.

**Limits:** FP16 component validity is not full-model parity; cold and warmed compile/cache states
are different measurements.

**Worth revisiting when:** A modified kernel retaining release-wheel and ABI identity, then exact
model gates and fresh paired timing; keep helper flags off meanwhile.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/minimax_qk_rms_xpu/README.md](../../../experiments/minimax_qk_rms_xpu/README.md) — full.

## minimax_qk_rms_xpu_ipc

Explore cross-process peer-memory variance reduction for collective/RMS fusion.

**Outcome:** IPC access worked, but single-kernel polling cost about 417 ms/iteration versus XCCL
0.061791 ms for tiny FP32 payloads. Current integration rejected.

**What worked:** Directional capability tests separated memory access from remote atomics. A
two-kernel CPU-barrier variant validated at 0.290768 ms.

**Failures and uncertainty:** Cross-device atomics were absent; no-barrier and system-scope atomic
variants failed. Slot overwrite can hang an equality-based poll.

**Limits:** CPU-barrier success is neither graph-safe nor model-safe; rejection is scoped to this
protocol/stack.

**Worth revisiting when:** A correct graph-compatible primitive or proven event/barrier protocol;
demonstrate visibility and slot lifetime before model integration.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/minimax_qk_rms_xpu_ipc/README.md](../../../experiments/minimax_qk_rms_xpu_ipc/README.md) — full.

## minimax_xpu_kv_offload

Use host RAM for KV storage and investigate active context beyond device KV.

**Outcome:** Two 14K sessions completed with about 26K device-KV capacity, demonstrating session
swapping. Full 196K active context was not achieved.

**What worked:** Worker-side CUDA assumptions were separated from scheduler admission. Dense scratch
supplied promising synthetic attention/LSE evidence.

**Failures and uncertainty:** A 33,580-token active prompt timed out at 131/132 blocks. Paged
scratch LSE was unstable for exact merge; c4 continuation and compressed-KV quality stayed
unresolved.

**Limits:** Session reload is not host-paged active attention; cached repeat rates are not cold
benchmarks. Dense-scratch tolerance is not full-model exactness.

**Worth revisiting when:** A full-precision dense-staged implementation with exactness and PCIe-cost
gates; raising max_model_len/offload size alone is closed.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/minimax_xpu_kv_offload/README.md](../../../experiments/minimax_xpu_kv_offload/README.md) — lines 1-34,162-183,286-333,618-693.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [experiments/minimax_xpu_kv_offload/ARTIFACTS.md](../../../experiments/minimax_xpu_kv_offload/ARTIFACTS.md).
- [experiments/minimax_xpu_kv_offload/probes/xpu_cpu_dense_staged_attention_probe.py](../../../experiments/minimax_xpu_kv_offload/probes/xpu_cpu_dense_staged_attention_probe.py).

## model-intake-resume-20261007

Repair aria2 partial files mistaken for complete downloads because of preallocation.

**Outcome:** Applied fix resumes size-matching files with aria2 sidecars; complete files retain
skipping. Three tests/four offline cases passed.

**What worked:** Sparse fixtures and fake HTTP clients reproduced the bug without weights.
Application waited for active download exit and matched tested bytes.

**Failures and uncertainty:** File size alone was not completion; the old branch skipped an
unfinished payload.

**Limits:** Offline controls do not authenticate downloaded models; publisher hashes remain
required.

**Worth revisiting when:** A changed downloader or concrete failed-resume case with sidecar and hash
controls.

**Gate at audit source commit `8c4505c31`:** Applied CPU utility; CURRENT still requires storage
admission and authenticated model bytes.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/model-intake-resume-20261007/validation.json](../../../experiments/model-intake-resume-20261007/validation.json) — full.
- [experiments/model-intake-resume-20261007/application.json](../../../experiments/model-intake-resume-20261007/application.json) — full.

## muse-glimmer-30b-b70

Pursue fast Muse decoding with separate BF16 and compressed-model identities.

**Outcome:** BF16 did not reach 100 tok/s. Approved Q8/DFlash/fixed-N16 WOQ route recorded canonical
means 100.088/100.649; cold first-100 median 161.900 uses a different metric.

**What worked:** Fixed-N16 projection and verified drafting helped the compressed route.
Genre-specific acceptance and verifier/draft cost decomposition identified useful work.

**Failures and uncertainty:** Upstream greedy SYCL near-tie outputs were nondeterministic even
without speculation; single-card Q8 plus draft exceeded the envelope.

**Limits:** Compressed result is neither BF16 nor universally token-exact. Quantization changes
cannot solve the original BF16 objective under the same identity.

**Worth revisiting when:** A new preregistration with deterministic target oracle; single-card work
needs source-level memory reduction first.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/muse-glimmer-30b-b70/README.md](../../../experiments/muse-glimmer-30b-b70/README.md) — full.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [results/muse-glimmer-30b-q8-woq-b70/README.md](../../../results/muse-glimmer-30b-q8-woq-b70/README.md).
- [patches/muse-glimmer-30b-b70](../../../patches/muse-glimmer-30b-b70).

## ornith-15-b70

Optimize actual dense/MoE Ornith shapes and verify that gains survive integration.

**Outcome:** Ordered expert addition improved fresh-server throughput 4.85%; convolution/SiLU added
2.10% in scoped tests. Two-row verifier work remained below target-only.

**What worked:** Ordered FP32 addition removed launches without regrouping arithmetic. Actual Q4_K
gate/up and Q6_K down shapes avoided a misleading Qwen proxy.

**Failures and uncertainty:** MoE command graphs fell from 101.846 to 48.805 tok/s despite passing
components. Flash-off/Q8KV changed transcripts. Exact rollback fusion helped alone but regressed on
the preferred stack.

**Limits:** The apparent dense graph 2x gain was NFS mmap confounding. Qwen surrogate aggregate
scores, launch counts and isolated gains are not Ornith endpoint claims.

**Worth revisiting when:** A new device-work reduction, canonical transcript equality, stack
interaction test and two fresh-server comparisons.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/ornith-15-b70/README.md](../../../experiments/ornith-15-b70/README.md) — lines 1-140,440-532.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [experiments/ornith-15-b70/notes/2026-08-22-ornith35b-moe-add-reduce-positive.md](../../../experiments/ornith-15-b70/notes/2026-08-22-ornith35b-moe-add-reduce-positive.md).
- [experiments/ornith-15-b70/notes/2026-08-23-ornith35b-mtp2row-two-snapshot-state-research.md](../../../experiments/ornith-15-b70/notes/2026-08-23-ornith35b-mtp2row-two-snapshot-state-research.md).

## own-xpu-runtime

Build original model-specific Xe runtimes against certified model/output authorities.

**Outcome:** CPU identity/parser/reference packets pass; BF16 stored scales and sigmoid attention
gate were corrected. Native runtime and actual one-card fit remain unqualified.

**What worked:** Staged identity, arithmetic, resource ownership and native-fixture gates prevent
CPU preparation becoming a GPU claim. Historical pressure receipts constrain admission.

**Failures and uncertainty:** A367 used a host environment, not the reopen image. Its host
availability decline contains unattributed memory; LTX shadow savings cannot be borrowed. The
proposed 133,542,784 KiB floor exceeds capacity.

**Limits:** Mock devices, compiled SYCL and synthetic repeats are not device parity. README
packet-1-only wording is superseded by CURRENT. Planning floor is not a universal bound.

**Worth revisiting when:** Complete adapters; after halt resolution obtain matched load evidence and
owner-bound admission before fixtures. Preserve official/Unsloth source rule and original
implementation.

**Gate at audit source commit `8c4505c31`:** CURRENT: CPU preparation active; halt, capacity,
model-receipt mismatch and native-window authorization block device work.

**Closeout gap:** Ongoing staged work; no whole-runtime native qualification.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/own-xpu-runtime/README.md](../../../experiments/own-xpu-runtime/README.md) — full.
- [experiments/own-xpu-runtime/stage1/packet4-prep/MEMORY-ADMISSION-REVISION.md](../../../experiments/own-xpu-runtime/stage1/packet4-prep/MEMORY-ADMISSION-REVISION.md) — full.
- [CURRENT.md](../../../CURRENT.md) — full.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [experiments/own-xpu-runtime/stage1/packet2/README.md](../../../experiments/own-xpu-runtime/stage1/packet2/README.md).

## project-decision-recall-20261007

Compare source search and complete-source delivery on frozen project decisions.

**Outcome:** Search/read: 12/12 questions, 38/38 criteria. Paged full source: 11/12 complete, 37/38
criteria; missing caveat appeared in its citation.

**What worked:** Independent completeness grading separated real citations from adequate answers.
Paging retained the initial truncated/format-invalid failure.

**Failures and uncertainty:** One answer omitted the distinction between final answers and
intermediate-state correctness. Reader-side full logs did not prove visible delivery.

**Limits:** Curated assistant-authored records/questions and hosted sessions are a small development
diagnostic, not local-Qwen or generic memory/speed evidence. Search read the full corpus.

**Worth revisiting when:** A real retained-state/scale need unmet by ordinary sources, with new
fixed tasks and independent references; check caveats in answers explicitly.

**Gate at audit source commit `8c4505c31`:** CURRENT: source access and completeness review
recommended; structured memory and worker integration not admitted.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/project-decision-recall-20261007/RESULTS.md](../../../experiments/project-decision-recall-20261007/RESULTS.md) — full.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [experiments/project-decision-recall-20261007/results/search/semantic-review.json](../../../experiments/project-decision-recall-20261007/results/search/semantic-review.json).
- [experiments/project-decision-recall-20261007/results/full-paged/semantic-review.json](../../../experiments/project-decision-recall-20261007/results/full-paged/semantic-review.json).

## qwen27-dflash-sycl-b70

Develop a one-card Q4 GGUF verifier and DFlash path distinct from AutoRound vLLM.

**Outcome:** Strict Q4_0/DFlash record 47.818818 tok/s; 100/200 tok/s goals unmet. Unfinished
QKVZAB/Q5_K/trace work remains unvalidated.

**What worked:** F16 draft-KV control recovered about 94% acceptance. MMVQ rows 9–17 dispatch fix
removed repeated weight reads; explicit replay instrumentation detected graph ineligibility.

**Failures and uncertainty:** Compressed native draft KV collapsed acceptance. The target verifier
cost about 58.7 ms versus about 10 ms draft, making about 1 ms feature injection a poor first lever.
Old DISABLE environment names were ignored.

**Limits:** Favorable-code about 74 tok/s is not the mixed-suite record; four independent TP1
workers are not TP4; topology reuse is not device replay.

**Worth revisiting when:** A measured small-M verifier improvement and new exact cold gate; retain
unfinished source before integration.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/qwen27-dflash-sycl-b70/README.md](../../../experiments/qwen27-dflash-sycl-b70/README.md) — lines 1-105,125-end.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [notes/2026-07-13-qwen27-dflash-sycl-closure.md](../../../notes/2026-07-13-qwen27-dflash-sycl-closure.md).
- [experiments/qwen27-dflash-sycl-b70/harness](../../../experiments/qwen27-dflash-sycl-b70/harness).

## qwen27_fused_postattn_rms_w4a16

Fuse residual/RMS and four-row INT4 projection in a graph-compatible operation.

**Outcome:** Component/compile/1000-replay checks passed, but 0.206377 ms versus production 0.119454
ms was 72.8% slower; no integration.

**What worked:** Two ordered kernels respected the normalization/consumer dependency. The same
loaded weight layout supported a fair comparison.

**Failures and uncertainty:** Apparent improvement against 0.288957 ms eager allocation was unfair;
handwritten projection lost to oneDNN.

**Limits:** Numeric component parity is not model-token qualification, and the slower fair baseline
closes the tested design.

**Worth revisiting when:** Keep oneDNN/DPAS projection while fusing a larger boundary without a
graph split; compare real production primitives.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/qwen27_fused_postattn_rms_w4a16/README.md](../../../experiments/qwen27_fused_postattn_rms_w4a16/README.md) — full.

## qwen27_graphsafe_flash_attention

Enable attention graph capture without changing kernel math.

**Outcome:** Handler-owned local storage enabled graph replay; crossover means 91.019 versus 88.426
tok/s supported a historical gain. Later rebuild passed 6,000 packed and 6,000 one-token replays.

**What worked:** Poisoned outputs, live input/length mutations and shuffled blocks exposed stale
replay. Narrow AOT configs made the low-RAM rebuild practical.

**Failures and uncertainty:** Forced chunk decode scales badly: about 17 us at 128 KV versus about
220 us at 2048. Python dispatch bypassed the C++ force switch until separately patched.

**Limits:** Component tolerance is not universal token exactness; Qwen3.6 speed and Qwen3.8 rebuild
are separate identities. Historical launchers still consume work/source.

**Worth revisiting when:** A graph-safe paged kernel or other measured long-context mechanism, with
activation evidence at Python and C++ boundaries.

**Gate at audit source commit `8c4505c31`:** CURRENT explicitly protects this source/generated tree
in place; ignored work/ is not disposable.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/qwen27_graphsafe_flash_attention/README.md](../../../experiments/qwen27_graphsafe_flash_attention/README.md) — full.
- [repro/qwen38-27b-autoround-int4-b70/evidence/graph-stage-oracles-20260818.json](../../../repro/qwen38-27b-autoround-int4-b70/evidence/graph-stage-oracles-20260818.json) — full.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [experiments/qwen27_graphsafe_flash_attention/qwen27-chunk-prefill-local-accessor.patch](../../../experiments/qwen27_graphsafe_flash_attention/qwen27-chunk-prefill-local-accessor.patch).
- `experiments/qwen27_graphsafe_flash_attention/work` — protected, ignored local
  working tree; retained on this host and not included in a fresh Git checkout.

## qwen35-4b-b70

Qualify a fast INT4 target/MTP path across short prompts, request reuse and concurrency.

**Outcome:** R308 repaired single-active-request reentry: both 4B and 9B passed 60/60 oracle and
52/52 boundary cases on each of two fresh MTP3 processes, plus strict 12/12 suites. Historical
single-user and high-concurrency profiles remain separate results.

**What worked:** Preserving accepted-state metadata across paused-request reentry fixed the measured
lifecycle defect. Class-consistent padding replaced weight rereads in FP16 row chunks; MTP0
staggered throughput reached 2104/3164 tok/s at c64 on TP1/TP2.

**Failures and uncertainty:** Strict 12-prompt tests missed short-prompt degeneration and
request-lifecycle bugs. Deterministic PyTorch mode cost about 29% at c64 without repairing
batch-shape-dependent output changes. FP8 controls repeatedly missed the full quality gate.

**Limits:** R308 qualification covers one active request, fixed depth 3 and the specified
capacities, not concurrent speculation or a new 32K result. Reproducibility within a fixed
composition is not exactness across different batch shapes; MTP0 and MTP3 cannot inherit each
other’s gates.

**Worth revisiting when:** A newly specified workload beyond the qualified lifecycle, with short
prompts, interleaving/reentry and matching oracle tests before speed claims.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/qwen35-4b-b70/HANDOFF.md](../../../experiments/qwen35-4b-b70/HANDOFF.md) — full.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [experiments/qwen35-4b-b70/notes/2026-09-13-r308-qualified-single-request.md](../../../experiments/qwen35-4b-b70/notes/2026-09-13-r308-qualified-single-request.md).
- [experiments/qwen35-4b-b70/notes/2026-09-13-r307-single-request-and-r308-negative.md](../../../experiments/qwen35-4b-b70/notes/2026-09-13-r307-single-request-and-r308-negative.md).

## qwen35-9b-b70

Reduce draft vocabulary projection cost while retaining full target verification.

**Outcome:** The 67,248-row draft shortlist improved the paired measurements from 113.48/113.49 to
124.03/124.13 tok/s, about 9.3%; all G1/G2/G3 gates were 12/12.

**What worked:** The draft head previously covered 248,320 tokens and about 28% of step time. A
text-derived shortlist reduced proposal work; the target still verified against its full FP16 head.

**Failures and uncertainty:** A 32,776-row shortlist lost acceptance without improving speed
materially; 91,754 rows were slower than the chosen shortlist. Position-level profiling was noisy.

**Limits:** This is a proposal optimization with a full verifier, not target vocabulary pruning.
Exactness still depends on a valid verifier and lifecycle; the separate R308 single-request
qualification does not admit concurrent speculation.

**Worth revisiting when:** A different language/domain corpus or changed draft bottleneck, with
independent quality coverage, shortlist provenance and separate lifecycle gates.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/qwen35-9b-b70/notes/2026-09-12-the-draft-head-only-needs-a-shortlist.md](../../../experiments/qwen35-9b-b70/notes/2026-09-12-the-draft-head-only-needs-a-shortlist.md) — full.
- [experiments/qwen35-9b-b70/data/2026-09-12-qwen35-9b-draft-head-shortlist.json](../../../experiments/qwen35-9b-b70/data/2026-09-12-qwen35-9b-draft-head-shortlist.json) — full.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [experiments/qwen38-27b-b70/docker/r294-draft-head-shortlist.py](../../../experiments/qwen38-27b-b70/docker/r294-draft-head-shortlist.py).
- [repro/qwen35-9b-w4a16-b70/README.md](../../../repro/qwen35-9b-w4a16-b70/README.md).

## qwen36-27b-autoround-int4-b70

Optimize AutoRound INT4 inference and intrinsic MTP while preserving accepted state and source
identity.

**Outcome:** The historical webhie INT4 TP2 packet records 95.384867741895 tok/s. A later
matched-source August 17 gate ran 93.445681 tok/s but passed only 12/25 exact cases and is not
promotable.

**What worked:** Reading the accepted state slot instead of copying it removed expensive redundant
work. Repairing the public oneCCL installation and containing mixed-KV metadata to the DFlash path
restored intended execution.

**Failures and uncertainty:** Blind copy removal/full-accept state skipping broke needle quality. A
106.663 tok/s small RMS screen did not predict the complete exact gate. Higher replay/depth
configurations spilled and failed quality; offline adaptation did not transfer automatically.

**Limits:** Intel and webhie checkpoints, GGUF Q8 and Qwen3.8 FP8 are distinct identities. Top-k
oracle thought experiments assume free extraction and are not measured end-to-end speed. A
historical record does not validate later source combinations.

**Worth revisiting when:** A concrete device-work reduction with accepted-state diagnostics, matched
source/image and all exact cold cases; draft work must first show enough accepted tokens to pay its
measured cost.

**Gate at audit source commit `8c4505c31`:** CURRENT explicitly protects the historical INT4 tree
and evidence. It is not the active Qwen3.8 FP8 lane; any rerun requires fresh host admission and
respects the four-card halt.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/qwen36-27b-autoround-int4-b70/README.md](../../../experiments/qwen36-27b-autoround-int4-b70/README.md) — lines 1-70, 820-900, 970-1015.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [notes/2026-08-17-qwen36-int4-batch-invariant-rmsnorm-closeout.md](../../../notes/2026-08-17-qwen36-int4-batch-invariant-rmsnorm-closeout.md).
- [patches/qwen36-27b-autoround-int4-b70/record-20260711/README.md](../../../patches/qwen36-27b-autoround-int4-b70/record-20260711/README.md).

## qwen36-27b-mtp-gguf-q4-b70

Measure intrinsic MTP for the UD-Q4_K_XL GGUF model using cold requests.

**Outcome:** Initial n-max 3 MTP improved 23.567 to 30.679 tok/s; a cache-off refresh measured
30.812 tok/s. The p-min screen’s best tested combination reached 31.480 tok/s.

**What worked:** Explicit cache_prompt:false and zero cached-token checks made results
interpretable. Fixing shell JSON defaults and the oneAPI selector prevented harness/launch errors
from masquerading as model behavior.

**Failures and uncertainty:** Probability/minimum-draft tuning produced incremental changes, not a
major new mechanism. Larger speculative settings cannot be assumed faster.

**Limits:** This is a GGUF Q4/llama.cpp identity, separate from AutoRound and Q8. Historical graph
flags and short-suite results do not establish current replay or long-context qualification.

**Worth revisiting when:** A measured draft/verification bottleneck change with the same cold metric
and full gate, rather than another broad knob sweep.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/qwen36-27b-mtp-gguf-q4-b70/README.md](../../../experiments/qwen36-27b-mtp-gguf-q4-b70/README.md) — full.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [experiments/qwen36-27b-mtp-gguf-q4-b70/notes/2026-07-05-cacheoff-selector-refresh.md](../../../experiments/qwen36-27b-mtp-gguf-q4-b70/notes/2026-07-05-cacheoff-selector-refresh.md).
- [experiments/qwen36-27b-mtp-gguf-q4-b70/notes/2026-07-05-pmin-screen-and-harness-fix.md](../../../experiments/qwen36-27b-mtp-gguf-q4-b70/notes/2026-07-05-pmin-screen-and-harness-fix.md).

## qwen36-27b-q8-gguf-b70

Qualify a one-card full-context Q8 target and distinguish exact MTP gains from concurrency
tradeoffs.

**Outcome:** Target-only Q8/F16-KV 32K passed its gates. Matched embedded-MTP cold control improved
17.107772 to 36.048707 tok/s over 12 prompts with exact tokens/content. Four independent-service
evidence remains separately scoped.

**What worked:** VDR2 improved decode about 8.2-10% in tested bands. Disabling the implicated DNN
path preserved exactness without the severe cost of disabling every optimization.

**Failures and uncertainty:** ubatch 1024 cut near-32K prefill about fourfold but failed middle-band
exactness. Ordinary near-32K c2 passed functionality but failed performance/fairness: aggregate
10.144217 tok/s, fairness 0.498956. Full-MTP c2/32K was not launched after a 32,683 MiB projection.

**Limits:** Four TP1 services are not one c2 service. A forced continuation after a natural answer
is not proof of a wrong completed answer; natural-stop synchronization remains unmeasured.
Cross-paired publisher heads/converters cannot inherit the matched-model exact gate. Early
missing-identity data are trend evidence only.

**Worth revisiting when:** A mechanism improving measured c2 memory/fairness or prefill without
middle-band drift; preserve matched publisher model/head and use natural-stop as well as
forced-token checks.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/qwen36-27b-q8-gguf-b70/README.md](../../../experiments/qwen36-27b-q8-gguf-b70/README.md) — lines 1-104, 350-460.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [experiments/qwen36-27b-q8-gguf-b70/notes/2026-08-10-embedded-mtp-realistic-suite-matched-control-pass.md](../../../experiments/qwen36-27b-q8-gguf-b70/notes/2026-08-10-embedded-mtp-realistic-suite-matched-control-pass.md).
- [experiments/qwen36-27b-q8-gguf-b70/notes/2026-08-10-embedded-mtp-crossband-four-service-recovery-closeout.md](../../../experiments/qwen36-27b-q8-gguf-b70/notes/2026-08-10-embedded-mtp-crossband-four-service-recovery-closeout.md).

## qwen36-35b-quark-int8-b70

Preserve detached kernel edits from the older Quark INT8/GDN/MoE investigation.

**Outcome:** Three dirty kernel files were captured from detached source 3b4effe: speculative
convolution state commit, MoE top-k index types and interface diagnostics. This preservation note is
the reviewed outcome; no speed or quality qualification is established by it.

**What worked:** The convolution change snapshots a row/window within one work item to avoid
cross-work-item accepted-state read/write overlap. The MoE helper admits both int32 and int64 top-k
indices.

**Failures and uncertainty:** The surviving context did not establish which older 35B runs qualified
this snapshot. It must not be silently attributed to the later Qwen27 record.

**Limits:** A preserved patch is a recoverable hypothesis, not proof of correctness or a promoted
runtime. The note identifies provenance uncertainty explicitly.

**Worth revisiting when:** A current exact failure matching this mechanism, followed by isolated
patch replay and accepted-state/dtype tests before model qualification.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

**Closeout gap:** Preservation is documented; a decisive matching performance/quality closeout for
this detached source snapshot was not found in the reviewed note.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/qwen36-35b-quark-int8-b70/notes/2026-07-04-vllm-xpu-kernels-detached-dirty-snapshot.md](../../../experiments/qwen36-35b-quark-int8-b70/notes/2026-07-04-vllm-xpu-kernels-detached-dirty-snapshot.md) — full.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [patches/qwen36-35b-quark-int8-b70/vllm-xpu-kernels-detached-dirty-gdn-moe-snapshot-20260704.patch](../../../patches/qwen36-35b-quark-int8-b70/vllm-xpu-kernels-detached-dirty-gdn-moe-snapshot-20260704.patch).

## qwen38-27b-b70

Maintain qualified FP8 inference while testing exact kernels, concurrency and evidence-grounded
source workflows.

**Outcome:** CURRENT records about 875 aggregate tok/s for the accepted 64-request short FP8
profile, with two fresh exact 16/32/64 short and long passes. A separate source-access study
completed 24/24 tasks in each of two cold requests; historical Q8 and Q4 records remain separately
identified.

**What worked:** Operator census and exact component oracles avoided repeating roughly fifty closed
server-level bisects. In the decision-history study, the full immutable source preserved numerical
checkpoints and quoted postings; direct source access avoided the tested history summaries’
ownership-join errors.

**Failures and uncertainty:** History-summary rows scored 19/24, 19/24, 19/24 and 23/24 versus four
source-only 24/24 rows. Sixteen ownership joins used initial owners despite all 96 numeric
checkpoints and 202 quoted postings surviving. Unsafe DFlash was excluded; the PR45 mixed soak
remains unverified.

**Limits:** The source study used different information schedules and timing, so 27.75/34.86 s is
not a generic speed comparison or intermediate-step guarantee. The FP8 multiuser gate is not an
all-suite/single-user certificate. An old multi-host handoff’s 21.708532 baseline is historical;
later Q8 matched-kernel results do not overwrite a different identity’s score.

**Worth revisiting when:** An observed production-shape gap or changed kernel dependency, with
current exact workload and source census; use original source completeness checks before designing
additional memory machinery.

**Gate at audit source commit `8c4505c31`:** CURRENT retains the official FP8/multiuser lane on
Turin; new work needs its 15 GB host budget and single-heavy-job admission. Context/memory/worker
expansion is parked. Preserve both user-dirty scripts; no service start is implied.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/qwen38-27b-b70/DO-NOT-REPEAT.md](../../../experiments/qwen38-27b-b70/DO-NOT-REPEAT.md) — lines 1-28.
- [experiments/qwen38-27b-b70/MULTI-HOST-HANDOFF.md](../../../experiments/qwen38-27b-b70/MULTI-HOST-HANDOFF.md) — lines 1-100.
- [experiments/qwen38-27b-b70/notes/2026-10-07-history-state-study-result.md](../../../experiments/qwen38-27b-b70/notes/2026-10-07-history-state-study-result.md) — full.
- [experiments/qwen38-27b-b70/notes/2026-10-07-full-source-screen-result.md](../../../experiments/qwen38-27b-b70/notes/2026-10-07-full-source-screen-result.md) — full.
- [experiments/qwen38-27b-b70/data/2026-10-07-history-study-result/audit.json](../../../experiments/qwen38-27b-b70/data/2026-10-07-history-study-result/audit.json) — top-level audit and per-trial condition/case/quality/score; not every detailed trial field.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [experiments/qwen38-27b-b70/docker](../../../experiments/qwen38-27b-b70/docker).
- [experiments/qwen38-27b-b70/scripts/context/second-comparison.sh](../../../experiments/qwen38-27b-b70/scripts/context/second-comparison.sh).
- [experiments/qwen38-27b-b70/scripts/run-fp8-tp1-server.py](../../../experiments/qwen38-27b-b70/scripts/run-fp8-tp1-server.py).

## qwen38-flash-next-fp8-b70

Improve the official FP8 target and isolate the recurrent device-loss boundary before more
execution.

**Outcome:** The September closeout records 46.854250 tok/s on its fixed class-balanced 99-interval
protocol. Exact serial two-row GDN reduced that component from 42.7 to 33.7 ms. October evidence
narrowed the repeated fault to an abrupt process-exit path after correct computation.

**What worked:** Separating first-use from steady decode exposed a roughly 29 versus 47 tok/s
startup effect. Clean exit and a 10 s hold passed where abrupt exit after the same successful
compute failed; one-layer replay also passed.

**Failures and uncertainty:** MTP2 was slower; larger prefill settings improved TTFT but changed
outputs; multiuser exactness failed. In the decisive abrupt-exit probe, return preceded the abrupt
action by 0.297 ms and the first fault followed by 70.669 ms; this does not identify the faulty
resource or a full-rank remedy.

**Limits:** The 8/16/32K rows are separately scoped, not the complete frozen certificate. Correct
outputs before exit do not establish driver/runtime cleanup safety. Older health receipts and start
permissions are superseded by the current third-incident halt.

**Worth revisiting when:** Owner-directed recovery followed by a newly bounded fault-isolation plan
and current memory/health admission; no repeated launch merely to reconfirm the known abrupt-exit
failure.

**Gate at audit source commit `8c4505c31`:** CURRENT: four-card host is halted after its third
device-loss incident. Owner-directed recovery and fresh receipts are required; historical
launch/reboot notes are not authorization.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [results/qwen38-flash-next-fp8-b70/CLOSEOUT-20260913.md](../../../results/qwen38-flash-next-fp8-b70/CLOSEOUT-20260913.md) — full.
- [experiments/qwen38-flash-next-fp8-b70/notes/2026-10-10-exit-fault-reproduced.md](../../../experiments/qwen38-flash-next-fp8-b70/notes/2026-10-10-exit-fault-reproduced.md) — lines 1-76, 215-270.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [experiments/qwen38-flash-next-fp8-b70/data](../../../experiments/qwen38-flash-next-fp8-b70/data).
- [experiments/qwen38-flash-next-fp8-b70/reopen-20261008](../../../experiments/qwen38-flash-next-fp8-b70/reopen-20261008).
- [experiments/qwen38-flash-next-fp8-b70/stability](../../../experiments/qwen38-flash-next-fp8-b70/stability).

## qwen38-flash-next-ud-iq3xxs-b70

Establish an independent lossless GGUF storage/parser identity before admitting native inference.

**Outcome:** The three authenticated shards total 81,961,823,936 bytes and 1,224 tensors. CPU
qualification passed 112 loader tests, 576 synthetic blocks/104,448 decoded values and repeated
sampled real-tensor checks. No model inference or GPU fit is established.

**What worked:** Independent normative decoders, bitwise checks and real-file samples made format
errors visible. Tensor census exposed that the UD-IQ3_XXS label contains mixed
IQ2_S/IQ3_S/IQ4_NL/Q6_K/Q8/F32/BF16 tensors rather than IQ3_XXS tensors.

**Failures and uncertainty:** The target packed allocation is 53,304,619,520 bytes across two cards;
the 29,321,610,240-byte off-device projection exceeds Turin’s 15 GB host budget. A file-backed
lookup/I/O and driver-memory plan is required before device admission.

**Limits:** Sampled byte checks are not a complete-tensor finiteness proof. The model has no native
MTP block; any optional official MTP mixture needs separate admission. This GGUF identity cannot
borrow FP8 tolerances or quality certificates.

**Worth revisiting when:** Complete tokenizer/operator oracles and a measured file-backed
host-memory plan before device parity; only then consider bounded inference under the owner’s
current host gate.

**Gate at audit source commit `8c4505c31`:** CURRENT retains CPU identity/parser work. Device parity
and inference remain unlaunched and subject to the four-card halt or Turin’s separate 15 GB
admission.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/qwen38-flash-next-ud-iq3xxs-b70/README.md](../../../experiments/qwen38-flash-next-ud-iq3xxs-b70/README.md) — full.
- [experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/README.md](../../../experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/README.md) — full.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1](../../../experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1).

## rapid-model-snapshots-b70

Compare a small model set with a shared cold streaming harness and retain useful deployment screens.

**Outcome:** Historical scoped rates include Qwen3 MoE 107.4839, Qwen Coder 108.1165, GLM 40.769,
Phi Q4 96.548 versus Q8 72.246, DeepCoder 57.096 and Nemotron 50.904 tok/s. These are preserved
screen identities, not a current leaderboard.

**What worked:** Explicit cache_prompt:false removed hidden request reuse. Running Phi alone
recovered 96.5 tok/s from about 74.8 during concurrent four-GPU screening, showing the need for
uncontended headline measurements.

**Failures and uncertainty:** Reasoning-parser output for R1 had zero measurable output deltas at
the 128-token cap; the raw-think 512-token diagnostic still ended without a final answer. Nemotron
knob changes were effectively neutral.

**Limits:** Small-context speed wins do not establish long-context quality. A raw reasoning rate is
not completed-answer throughput, and parallel screening is not a standalone record. Historical
power/storage/service instructions are superseded by CURRENT.

**Worth revisiting when:** A new model or runtime mechanism, with current host admission, standalone
cold quality and completed-answer measurement; avoid replaying broad neutral knob screens.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/rapid-model-snapshots-b70/README.md](../../../experiments/rapid-model-snapshots-b70/README.md) — full.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [experiments/rapid-model-snapshots-b70/deepseek-r1-distill-qwen-14b-q4km.md](../../../experiments/rapid-model-snapshots-b70/deepseek-r1-distill-qwen-14b-q4km.md).
- [experiments/rapid-model-snapshots-b70/localmaxxing](../../../experiments/rapid-model-snapshots-b70/localmaxxing).

## xpu_level_zero_peer_probe

Check Level Zero peer access, IPC import/export and allocation lifetime assumptions before
communication kernels.

**Outcome:** The sibling IPC experiment records successful all-pair functional access and forked
import/export. Remote pairs reported ACCESS without ATOMICS while each device’s self-pair reported
both; these are capability checks, not model speed gains.

**What worked:** A known remote fill pattern and child import/export distinguish visibility from an
assumed pointer mapping. Capability enumeration prevents treating all cross-device operations as
equivalent.

**Failures and uncertainty:** Write/access success does not prove persistent peer-polling atomics
are safe. The sibling fused IPC path later hung during replay despite functional setup passing.

**Limits:** The standalone README describes the probe, while the reviewed measured outcomes are in
the sibling IPC README. No standalone dated machine receipt was established by this review;
driver-specific observations are not permanent hardware guarantees.

**Worth revisiting when:** A changed driver/runtime or communication design, first with a bounded
capability/lifetime check and only then a graph-replay/model gate.

**Gate at audit source commit `8c4505c31`:** Not listed as an active lane in CURRENT.md. Retain as
historical research; a new experiment needs current host ownership and admission. The four-card
fault halt remains binding.

**Closeout gap:** Functional measurements are documented by the sibling IPC closeout; this area has
no separately reviewed standalone dated receipt.

Reviewed sources (read scope and SHA-256 in the JSON catalog):

- [experiments/xpu_level_zero_peer_probe/README.md](../../../experiments/xpu_level_zero_peer_probe/README.md) — full.
- [experiments/minimax_qk_rms_xpu_ipc/README.md](../../../experiments/minimax_qk_rms_xpu_ipc/README.md) — full.

Additional retained source/evidence (linked, not implicitly semantically reviewed):

- [experiments/xpu_level_zero_peer_probe/peer_probe.cpp](../../../experiments/xpu_level_zero_peer_probe/peer_probe.cpp).

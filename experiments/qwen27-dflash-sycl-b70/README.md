# Qwen27 DFlash + SYCL Single-B70 Optimization Lane

Created: 2026-07-12

Goal: maximum decode tok/s for Qwen3.6-27B on a single Intel Arc Pro B70
(608 GB/s, 32 GB GDDR6, Xe2/Battlemage), using GGUF + llama.cpp/SYCL + DFlash
speculative decoding. Apples-to-apples comparison with hipfire's 213 tok/s
single-R9700 result.

This is a new research path, separate from the existing
`experiments/qwen36-27b-autoround-int4-b70` (vLLM/XPU AutoRound INT4) and
`experiments/qwen36-27b-mtp-gguf-q4-b70` (llama.cpp/SYCL MTP-only GGUF) lanes.

## Plan

The controlling requirements and ordered execution plan is:

`../../plans/2026-07-12-qwen27-tp1-max-speed-requirements-and-execution.md`

It fixes the target at TP1 on one B70, uses the four cards as independent TP1
workers, defines the persistent cache/model-pack architecture, and provides
the validation ladder, kill rules, fusion order, Xe2 verifier plan, and
MTP/DFlash policy.

The earlier exploratory plan remains at
`../../plans/2026-07-12-qwen27-dflash-sycl-single-b70-plan.md` as historical
context. It is superseded where the controlling plan differs.

## Identity

- Target model: `unsloth/Qwen3.6-27B-MTP-GGUF` (**Q4_0** primary, Q4_K_S comparison)
- Draft model: `Alittlehammmer/Qwen3.6-27B-DFlash-GGUF-llama.cpp` (Q4_K_M, ~1 GB)
- Runtime: llama.cpp/SYCL on Intel Arc Pro B70
- llama.cpp source: `/home/steve/src/llama.cpp`
- Build dir: `/home/steve/src/llama.cpp/build-sycl-b70-qwen36-mtp` (existing)
- Comparison target: hipfire 213 tok/s (Qwen3.6-27B MQ4 + DFlash + Q8 KV,
  single AMD Radeon AI PRO R9700)

## Prior Work In This Repo

- `experiments/qwen36-27b-mtp-gguf-q4-b70/`: UD-Q4_K_XL MTP-only, best 30.8
  tok/s MTP3. DFlash was never tested. Config-only sweeps exhausted. Build
  predates critical PR #25063 (1.538x K-quant speedup, merged 2026-07-07).
- `experiments/qwen36-27b-autoround-int4-b70/`: separate vLLM/XPU AutoRound
  INT4 reference, best 68.236 tok/s TP1 historically and 95.385 tok/s TP2.
  Its local ReplaySSM/GDN path is proven; do not repeat the outdated blanket
  claim that Qwen GDN cannot run in the local vLLM/XPU stack. This lane still
  targets GGUF/SYCL because it enables the desired Q4_0, native fusion,
  B70-specific packing, and DFlash executor work.
- `notes/2026-07-12-b70-qwen27-prior-art-research.md`: full prior-art audit.

## Current July 12 State

- Target: Q4_0, current llama.cpp `e3546c794`, AOT `bmg-g31`, NDEBUG.
- Warm diagnostics: no-spec about 26.58 tok/s; MTP3 about 53-58 tok/s.
- The complete Q4_0 MMVQ rows 9-17 dispatch fix removes a hidden repeated
  full-weight-read fallback. Diagnostic DFlash n_max=15 improved from about
  8.49 to about 38.5 tok/s.
- The active llama.cpp source is dirty in `ggml-sycl.cpp` and `mmvq.cpp` and
  is protected research state.
- The Qwen GGUF server and Q4_0 matrix launchers now export and record the
  current `GGML_SYCL_ENABLE_GRAPH`, `GGML_SYCL_ENABLE_DNN`, and
  `GGML_SYCL_ENABLE_OPT` controls. The prior `GGML_SYCL_DISABLE_*` names were
  ignored by this llama.cpp source.
- Target and MTP graphs contain `CONCAT`, which the SYCL graph compatibility
  check currently rejects. Graph-topology reuse is not proof of device replay.
- The local SYCL backend now emits structured requested, compatibility-rejected,
  recording-entered, replayed, and shutdown-summary evidence. See
  `notes/2026-07-12-sycl-graph-evidence.md`.
- These are diagnostic findings, not promoted strict rows.
- Current strict graph-off Q4_0/Q8-KV medians are `25.783 tok/s` no-spec and
  `47.244 tok/s` MTP3. DFlash5 with the external GGUF as `draft-simple` is a
  mixed-suite loss at `11.505 tok/s`; retain it only as a workload-targeted
  research lane.
- Four simultaneous independent MTP3 TP1 calibration rows passed at
  `47.976-49.708 tok/s` median. This is replica calibration, not TP4.

## TP1 And Cache Requirements

- TP1 on one B70 is the only active target configuration.
- Four B70s run independent workers, controls, candidates, and swapped
  crossover assignments.
- Persist B70-native weight packs, AOT modules, golden activations, GDN/KV
  state snapshots, and diagnostic post-prefill state to accelerate iteration.
- Keeping model weights and diagnostic state resident is allowed for research
  iteration. Promoted results must still use cold unique prompts with
  `cached_tokens=0` and no prompt/KV/history reuse.

The first Phase 1 implementation is in [`harness/`](harness/README.md). It
provides a validated four-worker assignment, dry-run-safe persistent server
control, and explicit model-pack and golden-corpus manifests. It is a
foundation, not a claim that native packed weights or device-state restore are
already implemented.

Implementation and validation are recorded in
[`notes/2026-07-12-phase1-persistent-harness-foundation.md`](notes/2026-07-12-phase1-persistent-harness-foundation.md).

## Cold-Start Validation Policy

All headline results must be cold-start validated:

- fixed realistic prompt suite;
- each prompt exactly once as a cold first response;
- no prompt/KV/cache/checkpoint/history/repeated-output/n-gram acceleration;
- target model and quantization unchanged;
- DFlash/MTP speculation allowed only when accepted tokens are verified by
  the target model;
- primary metric: median generated-token throughput for tokens 1-100 after
  TTFT across the suite, with p10, mean, TTFT, prompt/output hashes, model
  identity, llama.cpp commit, build flags, env vars, and flags recorded.

Diagnostic sweeps may use synthetic or repeated prompts, but headline
submissions require the strict cold gate. DFlash acceptance is
genre-conditional (code prompts get 7-9 accepted tokens; prose gets 1.2-1.7),
so report results by genre or use a mixed realistic suite that reflects the
target workload.

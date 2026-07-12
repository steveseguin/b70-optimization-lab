# Qwen3.6 27B Single-B70 Maximum-Speed Requirements And Execution Plan

Created: 2026-07-12

Status: controlling plan for the active Qwen27 TP1 optimization lane

## Mandate

Maximize Qwen3.6 27B decode throughput on one Intel Arc Pro B70. The other
three B70s are experiment accelerators for independent TP1 work, controls,
and crossover validation. They are not a reason to move the target to TP2 or
TP4.

The intended result is not a collection of small benchmark wins. The target
is an unusually fast, quality-valid, reproducible single-card decoder built
around maximum useful fusion, a replayed native device pipeline, and the
fastest speculation policy supported by measured end-to-end economics.

Do not begin TP2 or TP4 optimization for this model until the user explicitly
changes this mandate.

## Non-Negotiable Requirements

1. TP1 on one B70 is the product and headline configuration.
2. Use all four B70s as independent TP1 workers to shorten iteration time.
3. Pursue changes with a credible path to a large end-to-end gain. Close
   sub-percent and config-only lanes quickly.
4. Build toward the fewest practical device submissions and global-memory
   intermediates, while preserving fast projection kernels and occupancy.
5. Speculation must accept tokens verified by the declared target model.
6. Prompt, KV, response, n-gram/history, and context reuse are forbidden for
   promoted fresh-response results.
7. Model weights, B70-native weight packs, compiled kernels, representative
   activations, and diagnostic state snapshots may be cached and kept
   resident to accelerate development.
8. Persist every meaningful patch, exact run identity, result, failure, and
   decision. Do not silently discard negative work.
9. Do not promote a result until exact cases, repeat quality, recurrent/KV
   state behavior, cold realistic prompts, and `cached_tokens=0` pass.
10. No LocalMaxxing submission unless a strict matching record is genuinely
    broken and all submission-policy fields are present.

## Model And Runtime Identity

Primary research identity:

- target: `unsloth/Qwen3.6-27B-MTP-GGUF:Q4_0`;
- target format: Q4_0 weights consumed by Q8_1 MMVQ activations;
- KV target: Q8 where quality and speed pass, otherwise record the exact type;
- target runtime: private llama.cpp/SYCL or the extracted native B70 executor;
- target hardware: exactly one Arc Pro B70;
- draft candidates: intrinsic MTP and Qwen3.6-27B DFlash;
- compiler target: AOT `bmg-g31` for promoted binaries;
- quality label: do not call this a globally calibrated W4A8 checkpoint. Use
  `Q4_0 weights / transient Q8_1 GEMV activations / Q8 KV` when applicable.

Every comparison must record at least:

- target and draft file paths, sizes, hashes, and source revisions;
- llama.cpp/native-executor commit and dirty-state patch snapshot;
- compiler, IGC, oneAPI, Level Zero, driver, kernel, and firmware identity;
- GPU index, clocks/power state if available, process affinity, and thermals;
- graph/command-list mode and proof that replay was actually entered;
- context, batch, ubatch, KV types, flash attention, speculation depth/policy;
- prompt and output hashes, cached-token details, acceptance distribution;
- primary tokens 1-100 after-TTFT metric, p10, mean, TTFT, wall throughput,
  and full-output throughput.

## Current Evidence And Protected Work

As of plan creation:

- current warm Q4_0 diagnostics: about `26.58 tok/s` no-spec and
  `53-58 tok/s` MTP3, not yet strict headline rows;
- DFlash diagnostics are workload-dependent. `n_max=5` was competitive on
  code, while longer blocks were initially blocked by a real MMVQ dispatch
  cliff;
- the current Q4_0 multi-column MMVQ patch extends the fast path through 17
  rows and removes a fallback that reread the target weights once per row;
- after the complete dispatch fix, diagnostic DFlash `n_max=15` improved
  from about `8.49` to about `38.5 tok/s`, with mean accepted length around
  `7.41` on the tested code prompt;
- the patch is dirty in `/home/steve/src/llama.cpp` and preserved under
  `patches/qwen36-27b-autoround-int4-b70/`. Do not reset it;
- current llama.cpp source expects `GGML_SYCL_ENABLE_GRAPH`, but the Qwen GGUF
  launcher still exports obsolete `GGML_SYCL_DISABLE_*` names;
- both the recurrent target graph and MTP draft contain `CONCAT`, which the
  SYCL graph compatibility check rejects, so topology reuse is not proof of
  command-graph replay;
- the promoted separate vLLM/AutoRound reference remains `68.236 tok/s` TP1
  historically and `65.4-66.7 tok/s` in the latest reproduction band. It is
  a different checkpoint/runtime identity, but a useful single-B70 speed
  reference;
- the current promoted two-B70 vLLM result remains durable evidence, not the
  target configuration for this plan.

## Performance Model And North Star

Current approximate no-spec target pass:

```text
observed pass             37.6 ms
estimated Q4 read floor   24.3 ms
perfect overhead removal  1.55x
```

Therefore graph replay, host cleanup, and fusion cannot create an incredible
result alone at the current target byte count. They are required because they
shorten every speculative cycle, but the large multiplier must come from one
or both of:

1. accepting several output tokens per target weight stream;
2. materially reducing target bytes per weight stream.

Primary speed objectives:

- first: produce a strict current Q4_0 TP1 baseline and beat the separate
  `68.236 tok/s` TP1 reference with a quality-valid single-B70 path;
- next: exceed `80 tok/s` on the fixed realistic suite;
- main engineering target: exceed `100 tok/s` on the fixed realistic suite;
- workload-specific target: substantially higher code throughput when
  DFlash acceptance supports it;
- never represent a code-favorable result as general-chat performance.

## Work Selection And Kill Rules

A development lane must satisfy at least one condition:

- modeled whole-cycle upside of at least 10%;
- measured removal of at least `0.4-0.5 ms` per target pass;
- enables full replay, true batched verification, fewer target weight reads,
  or a later greater-than-2x mechanism;
- materially reduces bytes read per target pass.

Otherwise give it one bounded microbenchmark and, at most, one paired endpoint
screen before closing it.

Immediate depriorities:

- generic batch-one GEMV tuning with modeled whole-model gain below 1%;
- isolated sampler work unless profiling shows at least `0.4 ms` per cycle;
- new config/flag sweeps of already exhausted llama.cpp controls;
- XMX/DPAS batch-one work without real-shape evidence;
- a Rust device-kernel rewrite;
- a literal whole-model mega-kernel before projection-boundary fusion;
- simultaneous full DFlash and MTP execution without a cycle model;
- TP2/TP4 work;
- EAGLE3 endpoint work until offline accepted depth crosses a defined endpoint
  threshold and beats the current draft choices economically.

## Fast Iteration Architecture

### Persistent TP1 Workers

Create one long-lived worker per B70. Each worker must:

- load target and selected draft weights once;
- retain weights, graph arenas, KV buffers, GDN buffers, and scratch space;
- reset working KV/GDN/sampler/speculative state between tests;
- select versioned kernel implementations at runtime where practical;
- load a new AOT Level Zero/SYCL kernel module without reloading the model;
- rebuild only the affected command list or graph;
- expose a local control interface that returns structured correctness and
  timing results;
- never run a second active SYCL inference process on the same B70.

The first implementation may use a private harness and dispatch table rather
than modifying the production server. Full endpoint validation remains a
separate promotion step.

### Disk And RAM Caches

Build a versioned B70 model-pack format keyed by:

- source GGUF hash;
- packing-tool revision;
- target architecture (`bmg-g31`);
- kernel ABI/layout version;
- quantization and scale layout.

The pack should eventually contain:

- GPU-ready Q4/Q3 weights in the chosen vector layout;
- DPAS-compatible verification tiles or a unified layout usable by both
  batch-one and multi-row consumers;
- combined projection tensors such as compatible QKV and gate/up groups;
- adjacent scales/metadata in actual access order;
- tensor offsets, alignment, shape, and checksum tables;
- no startup-time weight reorder.

Keep the active GGUF and model pack on internal NVMe. Use mmap and the Linux
page cache so all four workers share one host copy. Use a bounded pinned
staging ring and large asynchronous uploads instead of per-tensor
malloc/copy/wait behavior where the backend permits it.

Do not use `SYCL_CACHE_PERSISTENT=1` on this B70 system.

### Golden Diagnostic State

Persist representative real-model inputs for:

- batch widths `M=1, 4, 8, 16` and any actual DFlash boundary width;
- full-attention and recurrent layers;
- gate/up/down, QKV, output, and LM-head shapes;
- GDN state before and after update;
- KV slices before and after update;
- target logits, tokens, acceptance masks, and rollback outcomes.

Keep a pristine post-prefill state snapshot in each development worker and
reset working state with device-to-device copies. This is valid for diagnostic
kernel and cycle iteration only. It is forbidden as evidence for the cold
realistic promotion gate.

### Kernel Build Cache

- Cache AOT native modules by source hash, compiler/IGC version, flags, and
  target architecture.
- Use a small standalone real-weight harness for the edit/compile/check loop.
- Prefer small dynamically loadable kernel modules to rebuilding the full
  SYCL backend for every candidate.
- Use incremental/JIT builds only for development screening; promote with the
  pinned AOT build and record its identity.

Iteration objectives:

- no model reload for representative kernel checks;
- no prompt prefill for representative decode-cycle checks;
- kernel-only edit-to-result loop measured in minutes, not full-suite time;
- one four-GPU paired strict gate only after a candidate clears the lower
  ladder.

## Four-GPU TP1 Workflow

Normal development allocation:

- GPU0: immutable baseline worker;
- GPU1: current promoted-best worker;
- GPU2: primary candidate;
- GPU3: second candidate or independent correctness/stress lane.

Promotion allocation:

- first assignment: candidate on GPUs 0/2, control on GPUs 1/3;
- swapped assignment: candidate on GPUs 1/3, control on GPUs 0/2;
- require agreement across assignments for changes near the variance floor;
- rotate physical cards periodically and preserve per-card results.

Do not interpret four independent TP1 workers as a four-GPU model result.

## Validation Ladder

Every candidate advances through these gates:

1. Saved-tensor parity against golden layer inputs and states.
2. Real-shape kernel timing, achieved bandwidth/compute, and spill/occupancy
   inspection.
3. One-layer replay with exact state transition checks.
4. Full no-spec target-forward A/B.
5. Complete MTP or DFlash cycle A/B with acceptance and rollback checks.
6. Short endpoint canary with fresh state.
7. Four-GPU paired/swapped realistic-suite crossover.
8. Exact cases, repeat quality, baseline parity, and longer-context state gate.
9. Promotion packet, reproduction recipe, and LocalMaxxing preflight if it is
   a genuine matching record.

Failing a gate closes or redesigns the candidate. A fast microbenchmark does
not justify skipping endpoint or state validation.

## Phase 0: Preserve And Rebaseline

Deliverables:

- preserve the current MMVQ ncols 9-17 patch and reconcile the superseded
  partial-result note with the complete dispatch-fix note;
- direct correctness tests for Q4_0 rows `1..17`, reordered and non-reordered;
- strict Q4_0 no-spec, MTP3, and DFlash depth baselines on current source;
- exact graph requested/entered/rejected/update/replay counters;
- low-perturbation UR/Level Zero timeline for `M=1,4,8,16`;
- a target-cycle ledger reconciling wall time, kernel time, device idle gaps,
  enqueue/update time, host waits, and speculation control.

Exit gate:

- current patch passes correctness and strict baseline quality;
- overhead accounting reconciles to wall time within measurement error;
- actual graph status is proven rather than inferred from topology reuse.

## Phase 1: Persistent Runner And Model Pack

Deliverables:

- long-lived TP1 development worker on each B70;
- golden activation/KV/GDN/state corpus;
- device-to-device diagnostic reset path;
- versioned native-module cache and runtime dispatch interface;
- first model-pack tool and checksum manifest;
- measured startup breakdown: disk/page faults, host staging, H2D upload,
  reorder/pack, graph construction, and first kernel activation.

Exit gate:

- representative kernel tests do not reload the full model;
- representative cycle tests do not recompute prompt prefill;
- cached artifacts are identity-checked and rejected on any ABI/hash mismatch;
- strict gates remain explicitly cache-free at the prompt/KV level.

## Phase 2: Full Device Replay

Deliverables:

- current `GGML_SYCL_ENABLE_*` launcher identity;
- capture-safe dimension-0 concat or fused recurrent conv-state assembly;
- target and draft command graphs/lists with fixed addresses;
- device control buffers for active width, position, and state selection;
- on-device acceptance/rollback metadata where supported;
- explicit proof of replay and its measured cycle effect.

Exit gate:

- target and selected draft/verify paths replay without unsupported host waits;
- exact outputs and recurrent/KV transitions match control;
- keep the work if it is a measured win or a necessary enabler for the fused
  speculative pipeline. Stop runtime-rewrite expansion if device idle gaps
  are already below 1 ms per forward.

## Phase 3: Maximum Useful Fusion

Priority fusion families:

1. output MMVQ + residual epilogue for attention/GDN output and FFN down;
2. residual + RMSNorm + Q8_1 production for the next projection;
3. combined gate/up projection with fused SiLU/multiply and down-input
   quantization;
4. compatible shared-input QKV projection with RoPE/KV write epilogues;
5. GDN convolution, gate preparation, state production, and direct persistent
   state write;
6. final norm, LM-head reduction, and sampler preparation;
7. multi-row equivalents for verifier widths.

Preserve the fastest projection producer. Split a fusion that causes material
GRF spills, occupancy loss, or less than 1.1x improvement over the unfused
boundary.

Exit gate:

- each retained fusion clears the validation ladder;
- the combined fused/replayed target cycle shows a material end-to-end win;
- removed launches and global intermediates are enumerated.

## Phase 4: True Xe2 Batched Verification

Architecture:

- keep a bandwidth-optimized DP4A/vector path for `M=1`;
- implement INT4 x INT8 DPAS/XMX projection kernels for `M=4,8,16`;
- use offline Xe2-packed weights and real target projection shapes;
- batch recurrent GDN, full attention, KV/state updates, and verifier logits;
- commit the accepted prefix and rollback rejected speculative state on device;
- synchronize with the host once per accepted block at most.

Exit gate:

- DPAS verification is at least 1.5x better per token than repeated vector
  MMVQ at real `M=4/8` shapes;
- exact target verification and state behavior pass;
- stop batch-one DPAS unless it beats DP4A by at least 10% on the real mix.

## Phase 5: Fastest Speculation Policy

### MTP

Use MTP3 as the reliable baseline. Optimize the complete cycle, not isolated
draft kernels:

- head preparation and token selection;
- batched target verification;
- device acceptance and state rollback;
- fixed command-list replay;
- accepted/generated tokens per target weight stream.

Stop increasing depth when marginal accepted tokens cost more cycle time than
they return.

### DFlash

Treat DFlash as the primary high-ceiling lane:

```text
small quantized draft block
  -> one parallel draft forward
  -> one true batched target verification
  -> longest-prefix acceptance and state commit
```

Use this cycle equation for every configuration:

```text
throughput = accepted output tokens / complete draft+verify+commit time
```

Do not optimize acceptance without cycle time, or cycle time without accepted
tokens. Report both by workload category.

### Adaptive Policy

- keep MTP and DFlash resident if VRAM permits;
- route DFlash to code/math and requests with strong rolling acceptance;
- route MTP to prose/chat or after DFlash acceptance falls;
- do not run both full drafts every cycle;
- require a hybrid to beat the better standalone policy by at least 10%.

Speculation exit gates:

- DFlash must clear its cycle-model break-even acceptance;
- mixed realistic suite improvement must be at least 1.5x before promotion;
- target workloads should show greater-than-2x where DFlash is enabled;
- if verifier time exceeds 80% of the cycle, work on target DPAS/fusion;
- if draft time exceeds about 35-40%, quantize/fuse the draft;
- quality and state gates remain mandatory.

## Phase 6: Reduce Target Bytes

After the Q4 fused speculative pipeline is functioning, evaluate an offline
rotated/codebook Q3 model pack. Consider Q2 only as a separately quality-gated
research lane.

Exit gates:

- Q3 must provide at least 1.20-1.25x end-to-end AR improvement and pass the
  quality envelope;
- Q2 must provide at least 1.6x AR improvement to justify its quality risk;
- count scale, codebook, and metadata bytes in the effective format size;
- stop immediately on unacceptable quality or insufficient real byte saving.

## Immediate Ordered Checklist

1. Mark the current protected main-repo paths and dirty llama.cpp MMVQ
   files as protected work.
2. Fix the experiment launcher to record current `GGML_SYCL_ENABLE_*` values.
3. Add explicit SYCL graph requested/rejected/entered/replayed counters.
4. Validate and promote the Q4_0 MMVQ rows `1..17` dispatch fix into the
   experiment ledger.
5. Run strict no-spec, MTP3, and DFlash baseline rows on current source.
6. Capture the first low-perturbation target/draft/verify timeline.
7. Build the golden `M=1/4/8/16` activation and state corpus.
8. Build the persistent one-GPU worker skeleton and native kernel-module ABI.
9. Implement capture-safe recurrent concat/state assembly and measure full
   replay.
10. In parallel, start the real-shape DPAS verification harness and the first
    output-MMVQ+residual fusion.
11. Integrate the winning verifier and fusion kernels into a complete MTP
    cycle.
12. Re-run DFlash block `5/8/15` economics, then implement adaptive routing.
13. Promote only through paired/swapped four-GPU strict gates.
14. Reassess Q3 only after the Q4 cycle is efficient.

## Required Durable Artifacts

For each phase, keep:

- source patch and exact external-tree status;
- build command, compiler output, binary/module hash, and cache key;
- model-pack manifest and source GGUF hash;
- diagnostic corpus manifest and golden-output hashes;
- microbenchmark and endpoint structured summaries;
- candidate/control GPU assignments and swapped crossover results;
- quality, state, acceptance, and failure evidence;
- explicit win/loss/inconclusive decision and next action.

Large model packs, native modules, and state corpora may stay outside Git under
the active benchmark/model storage tree. Track their paths, manifests,
checksums, and summaries in the repository.

## Definition Of Done

This lane is not done because a microkernel is fast or because a synthetic
prompt reaches a high number. It is done when:

- the fastest single-B70 policy is identified by workload and implemented;
- the target/draft/verify pipeline uses the measured useful fusion and replay;
- initialization and kernel iteration use the persistent cache architecture;
- the fixed realistic suite passes cold with `cached_tokens=0`;
- exact, repeat, multi-turn, recurrent-state, and longer-context gates pass;
- the result is reproducible from recorded source, model pack, commands, and
  manifests;
- the final one-B70 result is promoted and submitted if it is a genuine
  matching record;
- TP1 has no remaining measured high-upside lane before any TP2/TP4 discussion.

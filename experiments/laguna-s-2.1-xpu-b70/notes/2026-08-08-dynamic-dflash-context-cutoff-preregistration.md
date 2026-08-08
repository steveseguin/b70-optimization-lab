# Dynamic DFlash context cutoff: preregistration and offline implementation

Date: 2026-08-08 America/Toronto

Status: **offline candidate only. Default off; no device result and no
throughput claim.**

Source candidate: `00c8bbbb5c950abc69a27a2e733330652eece478` on prerequisite
`561698049656690a55ea0ca9826dceba0e33a9c7`. Preserved bundle and patch
checksums are in
[`2026-08-08-dynamic-cutoff-manifest.md`](../../../patches/laguna-s-2.1-xpu-b70/2026-08-08-dynamic-cutoff-manifest.md).

The first device attempt,
`20260808-dynamic-cutoff-transition-a`, is a harness-rejected source failure.
It reached committed context 4,162, latched DFlash off on all four ranks, and
the scheduler produced the intended M1 step. Before executing that step,
eligibility raised `AttributeError` because the new guard referenced mock-only
`num_prompt_tokens_cpu` instead of the real `InputBatch.num_prompt_tokens`.
The runner exited 1, worker shutdown completed, and the device-error scan was
empty. Commit `00c8bbbb5` corrects the field and its test fixture; 27 focused
worker tests pass after the correction. No throughput or correctness result is
claimed from attempt A.

## Why this treatment exists

The August 7 crossover note compared two separately launched services:

- q12 DFlash at width 12; and
- target-only decode at width 1.

It did not implement a context-dependent switch. A naive q12 service that
merely stops scheduling drafts would force its M1 target steps eager because
the graph contract captured only width 12. The runner-owned collective buffers
were also width-12-shaped, so simply admitting M1 would be unsafe.

The observed endpoints still justify a bounded implementation experiment. The
estimated crossover is model-dependent and lies roughly in the 6.9K--8.9K
range depending on fit; 7.6K is the power-law estimate, not a measured or
shipping threshold. Correctness and policy performance are separate gates.

## Default-off source contract

`VLLM_XPU_LAGUNA_DFLASH_CONTEXT_CUTOFF=0` preserves the existing static-width
path. A positive value is accepted only for Laguna XPU DFlash with greedy draft
sampling, standard rejection, depth 11, exact width 12, `max_num_seqs=1`, and
the PIECEWISE Breakable target graph. Unpadded drafting and KV transfer are
rejected.

After bookkeeping commits the tokens accepted by the current target cycle, the
worker compares `input_batch.num_tokens_no_spec` with the cutoff. At or above
the boundary it latches DFlash off by request ID, returns a real empty draft
tensor, and does not execute DFlash. The latch prevents an output-state
correction from re-enabling a stale draft KV cache if visible context shrinks.
KV transfer is rejected in this diagnostic contract. A width-12 cycle that
starts below and crosses the cutoff is verified normally; it publishes zero
drafts and the next target cycle is M1.

The opt-in graph contract requires capture sizes exactly `[1, 12]`. Runtime
eligibility admits only these pairs:

| target width | scheduled drafts |
| ---: | ---: |
| 12 | 11 |
| 1 | 0 |

Widths 2--11 remain forced eager. Separate fixed-address all-gather and
embedding-reduce buffers are preallocated for rows 1 and 12 before the first
forward; no allocation occurs inside capture or replay.

The scheduler ceiling remains service-wide and reserves worst-case DFlash
lookahead. It does not change at the context boundary. The harness now requires
the Scheduler-owned runtime marker that reports the exact member later copied
into `token_budget`; launcher arithmetic and warning text are not accepted as
proof.

Width-1 graph eligibility additionally requires that prefill is complete. A
one-token final prefill chunk therefore remains eager.

## Offline gates

- Ruff passes on every modified vLLM source and test file.
- Focused scheduler, graph-contract, cutoff-boundary/latch, empty-draft,
  dual-width eligibility, prefill rejection, capture-filter, and
  collective-buffer tests pass: 51 tests across the focused groups.
- Launcher host guards must pass, including rejection of cutoff runs without
  an exact oracle: 25 tests pass.
- Both modified shell scripts pass `bash -n` and both repositories pass
  `git diff --check`.

Independent review found and blocked an earlier pre-bookkeeping/unlatched
implementation. No model launch is allowed until the corrected source and
harness pass these offline gates and re-review. Follow-up review also caught
and closed the padded-DFlash retry type, request-ID reuse, first-capture
topology, oracle-qualification, and delayed-transition gaps.

## Bounded device gate

No device work begins unless independent review is clean. The first device
gate is correctness-only: one q12 service with cutoff 4,160 and the
`laguna-lc-04096-middle` request. That request starts below the cutoff and must
cross it during its 128-token generation, proving an actual within-request
M12-to-M1 transition. It is not a throughput measurement.

The correctness authority is frozen to:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-long-context-teacher-q1-gpu080-swap24g-20260802T184000Z/bench.json`

SHA256:
`b0e41df6b7e5b798749c97221dbae4c41e345a41785e9c6793d5f76b5b9b11b8`.
The harness validates the teacher status, run identity, global intrinsic/cache
gates, selected-row prompt identity, output length, and token payload before
launch. A different JSON cannot silently become the oracle.

Only after that passes may a separate policy experiment use cutoff 8,192 and
matched rows on both sides of the estimated crossover. Both gates exclude
24,576, whose engine-kill cause is unresolved.

Required evidence:

1. an explicitly required long-context oracle and final `PASS_ORACLE_EXACT`;
2. exactly one scheduler-owned runtime-budget marker with resolved budget
   8,182 and batched budget 8,192;
3. exactly one cutoff transition marker per TP worker, with committed context
   in the exact legal window `cutoff..cutoff+11` and request identity matching
   the sole benchmark request;
4. audited target capture and replay for both `BatchDescriptor(num_tokens=12)`
   and `BatchDescriptor(num_tokens=1)` on all four ranks in one process;
5. audited 14/13 DFlash capture/replay on all four ranks before the cutoff;
6. no intermediate-width graph admission, stale drafts, engine restart,
   device error, or surviving worker;
7. exact token identity against the declared long-context oracle for every
   scored row, including the transition; and
8. a same-commit cutoff-zero q12 control before attributing performance to the
   switch.

First-live graph capture latency is not a decode-speed sample. Each width must
be captured and replayed before its measured row. A result that is faster but
not oracle-exact remains diagnostic and cannot be promoted or submitted.

## Promotion boundary

Passing the 4,160 transition gate proves only transition correctness. Passing
the later 8,192 policy gate proves only that one configurable policy is safe
and useful on the tested cases. Calling ~7,600 a production threshold
additionally requires matched points around the crossover, a stability result
above 16K, and a decision about retaining DFlash weights and reserved
lookahead after the switch. The dynamic service retains those costs, so the
static no-drafter arm's 1.65x endpoint ratio is not its expected gain. No
LocalMaxxing submission follows from this diagnostic lane.

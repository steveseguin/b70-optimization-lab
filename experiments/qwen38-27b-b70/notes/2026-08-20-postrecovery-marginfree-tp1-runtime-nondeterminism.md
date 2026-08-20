# Qwen3.8 post-recovery margin-free TP1 runtime nondeterminism

Date: 2026-08-20

Classification: **correctness blocker; TP1 control negative**

Structured evidence:
[`../data/2026-08-20-postrecovery-marginfree-tp1-determinism.json`](../data/2026-08-20-postrecovery-marginfree-tp1-determinism.json)

## Result

The recovered measuring host reproduced the margin-free MTP5 speed but did not
recover token determinism. Two valid TP2 all-25 arms measured `102.132` and
`102.176 tok/s`, agreed on only 21/25 prompts, and each agreed with the fresh
target-only oracle on only 15/25 prompts. Arm B passed the quality gate; arm C
skipped it. The semantic pass is not a substitute for the token-identity gate.

The TP1 control is decisive. The final F2/G pair:

- used one physical B70 (GPU 2), so no TP2/cross-rank collective or custom
  oneCCL runtime injection existed (the world-size-one XCCL backend still
  initialized normally);
- started from and ended on the same 1,859-entry, 1,588-file,
  197,507,168-byte compile-cache tree (`02db4496...`);
- directly loaded the same b936 backbone and eagle outer artifacts and the
  same two AOT models;
- emitted no graph-compilation or AOT-save marker; and
- still agreed on only 2/4 preregistered prompts.

Structured extraction first diverged at zero-based token 225. Long rollover
first diverged at token 469. This is genuine runtime nondeterminism under a
sealed TP1 executable/cache identity. TP2/cross-rank oneCCL collectives and
allreduce are therefore not required for the observed output instability.

## Supporting controls

The fresh target-only oracle exists now. Its A/B arms measured `49.759` and
`50.016 tok/s`; A passed the margin-free semantic gate and B skipped it. They
agreed on 24/25 prompts. Long rollover alone diverged at token 469. That proves
at least one residual source is not specific to MTP verification.

The first TP1 A/B and `PYTHONHASHSEED=0` C/D pairs alternated between automatic
outer keys b936 and fa614. Their computation graphs and inner Inductor keys
were identical, but the serialized outer artifacts differed, so those pairs
could not settle compile versus runtime causality. The explicit b936 replay
closed that ambiguity. F2 and G used byte-identical pre- and post-cache trees
and still diverged.

One attempted sealed arm named `...sealed-b936-f...` is intentionally retained
as a failed preflight. It supplied `VLLM_CACHE_ROOT` rather than the harness's
scrub-safe `VALIDATION_VLLM_CACHE_ROOT`; the fail-closed gate inspected the
unrelated default cache and refused launch before GPU work. F2 is the corrected
arm.

## Consequences

- Do not promote `101.170`, `102.132`, or `102.176 tok/s` as a reproducible
  record.
- Do not attribute the instability to page-cache corruption or require a
  cross-rank oneCCL collective as its cause. TP1 still initialized XCCL at
  world size one, so this control does not exclude all oneCCL/XCCL code.
- Do not use the four-prompt medians as performance results; the reduced suite
  exists only to reproduce known token flips cheaply.
- Keep the cheap draft-fallback margin diagnostic-only. It can mask or alter
  the symptom and does not repair the target-only long-rollover flip.
- The next correctness experiment should trace the TP1 structured-extraction
  flip under the same explicit b936 cache. Start with the least intrusive
  existing layer/operator hashes and bisect toward the earliest divergent
  state before spending another full 25-prompt run.

All raw arms are under
`/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/`; exact names,
hashes, identities, and divergence indices are in the structured evidence.

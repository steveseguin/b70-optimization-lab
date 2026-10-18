# Packet90 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Prepare exact expert and HC candidates before packet86 reports its non-exact
limiter bounds. October 18, 2026; packet84 copied source lineage, hc-wide,
wide64, ordered and rec-parallel; `iq3-p49-split32-v1`; unchanged quantized
weights and BF16 KV, rank-1 draft, 24/24 target layers, context capacity 4096.
CPU-only on steve-b70s; future screens target two-card lanes A and B.

## Outcome

CPU preparation accepted. E1 caches exact decoded IQ2 half scales; H1 caches
exact decoded FP32 HC gate weights. Production and both individual candidates
are built and sealed. GNU and Intel each matched all bytes in two fresh runs
per view, with 28 fixture cases per run and exhaustive finite half patterns.
Six real full-size startup paths and unchanged memory admissions passed.
Twelve malformed allocations, five selections, fourteen unsupported modes and
the combined layout were refused. Device correctness and speed are unmeasured.

## What worked

The startup mock exercises real preparation, transformed allocation sizes,
argument validation, captured operations, speculative banks and draft startup,
while avoiding device storage and weight payload reads. Its native plan is
checked against actual arena allocations. The shared pinned v4 wrapper plans
all four A jobs and both possible B brackets. The real queue plans the two
proposal files on a temporary copy. Independent final review verified all four
seals over 3,758 bound files with no missing or changed inputs.

## What failed or remains uncertain

Pre-seal review found and fixed unsupported-mode admission, cached native-plan
sizes, an HC fixture label and nonfinite HC scale handling. Fixture-only errors
were corrected before sealing: a duplicate report key, draft-vs-target plan
filtering and the assumption that both ranks transform 48 expert tensors.
Actual rank-0 dispatch transforms 46 and rank 1 transforms 48. No device was
used to find or fix these. See [harness fixes](evidence/harness-fixes.md).

The candidates increase immutable weight storage and may regress bandwidth.
CPU identity does not establish device compiler behavior, model oracle parity,
deterministic fresh owners, acceptance or performance. Packet86 used different
HC geometry; its diagnostic deltas are only bounds. All saving estimates remain
hypotheses. Other candidates remain written designs, not implementations.

## Evidence and patches

[Preregistration](PREREGISTRATION.md), [build](build-device-receipt.json),
[raw byte gate](evidence/cpu-byte-identity.json),
[startup](evidence/full-shape.json),
[memory](evidence/full-shape-admission.json),
[Python gates](evidence/python-tests.json),
[final plans](evidence/final-check.json),
[temporary queue plans](evidence/queue-plans.json),
[retention/rebuild](ARTIFACT-RETENTION.md), [handoff](WINDOW.md).
Changes are confined to this copied packet; `parent-source-manifest.json`
records the original identities. Raw CPU bytes, case ledgers, compressed arena
censuses/native plans and all seals are retained. No measured device evidence
exists for these candidates yet.

## When to revisit

The coordinator runs the registered exact screens after packet86 and normal
lane admission. Apply the verdict table to the next design, and qualify any
winner on the other lane before a speed verdict. Integrate only after exact
oracle, determinism, unchanged acceptance and full-chain gates. The lane stays
open; this closeout completes CPU preparation only.

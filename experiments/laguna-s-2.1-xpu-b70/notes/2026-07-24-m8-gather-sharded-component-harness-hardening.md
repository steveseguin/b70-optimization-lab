# Laguna M=8 gather-sharded component harness hardening

Date: 2026-07-24 America/Toronto

Status: host-only tooling repair in progress. No candidate/native import,
candidate primitive, XPU tensor allocation, model load, endpoint, prompt,
generation, network submission, or LocalMaxxing action has occurred.

## Why execution remains gated

The standalone gather-sharded source, sealed CPU build, device-IR evidence,
288-epoch fixture corpus, and installed-schema operational preflight remain
intact after the reboot. The active model copies and live artifact roots are
on internal NVMe. The approved four-GPU record remains unchanged.

Independent read-only review of the first Phase-A, Phase-B, and Stage-0
completion tooling found fail-closed evidence gaps before any component
packet or production native bundle was created. These are harness defects,
not candidate correctness or performance results. The one-shot candidate
authorization has therefore not been consumed.

## Phase-A findings under repair

- The exact `env -i` child environment could not import its committed helper
  closure because safe-path mode removed the script directory and no explicit
  immutable import root replaced it.
- The inherited pipe payload was structurally forgeable and was not adequately
  bound to coordinator issuance, the precreated campaign/card roots, or an
  authenticated descriptor type.
- The nominal 65-second idle gate covered only 64 elapsed seconds and trusted
  shallow `status` fields instead of validating the complete observer report,
  raw capture, child identity, and boot continuity.
- Card results were sealed beneath a still-writable campaign parent; aggregate
  reads were path-racy, and the aggregate and terminal authorization remained
  mutable.
- Runtime/helper source was hashed and later imported by pathname, leaving a
  replacement window.
- Result validation did not fully link every advertised output digest and BF16
  classification to the corresponding raw-bit comparisons.
- Generated output roots had lexical prefix checks but lacked descriptor-bound
  live internal-NVMe attestation.

## Phase-B findings under repair

- Profiler arms need distinct, fresh private runtime/cache roots for every
  `A1/B1/B2/A2` execution.
- Every profiler arm must retain and revalidate the full eight-library native
  closure and fixture closure through session stop.
- The 47 post-stop outputs per arm, their BF16 classifications, and all input
  before/after hashes must be recorded and cross-bound to Phase A.
- Counter gates must pass independently for both matched pairs
  `A1 -> B1` and `A2 <- B2` on each physical card, as well as the per-card
  aggregate. Averaging may not rescue a failed pair or card.
- Each arm needs a real continuous 65-second idle/cooling interval with full
  observer evidence; a single shallow snapshot is insufficient.
- Timeout/failure paths must retain stdout, stderr, process termination, shared
  memory cleanup, and immutable terminal evidence.
- The one-shot coordinator must run the offline analyzer itself, seal the
  final pass/fail terminal tree, and return success only after every exactness,
  geometry, profiler, and counter gate passes.
- Phase B must require a sealed Phase-A terminal that explicitly authorizes the
  mandatory counter phase, not only an operator-supplied aggregate and digest.

## Stage-0 completion-certificate findings under repair

- Input and audit evidence was attested by pathname and reopened later; the
  attestation and stable read must use the same retained `O_NOFOLLOW`
  descriptor.
- The recorded child-validator argv duplicated the Python executable and did
  not match the executed argv.
- Git, Python, and freezer verification was pre-exec pathname verification.
  Strict pinning requires descriptor-backed execution or an equivalently
  immutable verified staging closure.
- Two distinct reviewer identifiers and exact audit scopes are enforced, but
  reviewer provenance remains an evidence convention rather than a
  cryptographic identity. No final audit report may be fabricated.

## Frozen decision

Do not create the production bundle, Stage-0 certificate, authorization
packets, or run either component phase until the repaired tools pass CPU-only
mutation tests and fresh independent audits. Phase A remains the only allowed
candidate timing/exactness campaign. Phase B remains conditional on a sealed
all-card Phase-A pass. Neither phase may be retried or selected among.

## First repair re-audit

The first repair passes improved import, timing, result-linkage, and
descriptor handling, and their CPU-only suites passed. Fresh independent
review nevertheless rejected both tools before execution:

- the Phase-A campaign-root helper recursively invoked itself, while the real
  coordinator bypassed it and created no card roots; the first card would
  deterministically fail before child launch;
- the replacement capability still accepted a caller-fabricated pipe,
  caller-created roots, and caller-created proof file, so it did not
  authenticate coordinator issuance;
- runtime-directory evidence recorded only leaf paths while its validator
  required every path prefix;
- actual child startup did not match the isolated `-S/-P` bootstrap test;
- raw idle bytes were hashed but not parsed and reconciled with the claimed
  sanitized observer result;
- several success/failure writes and tree freezes still reopened pathnames,
  and timeout cleanup could return without proving the child was reaped;
- Phase-A runtime, native, and retained-fixture records still had
  under-validated fields; and
- the Stage-0 validator fixed its original input/audit and executable races,
  but still reopened the certificate, source packet, fixture evidence, and
  operational preflight by pathname during long validation.

These are additional host-harness negative results. They do not consume or
characterize the candidate. A second repair/re-audit cycle is in progress.

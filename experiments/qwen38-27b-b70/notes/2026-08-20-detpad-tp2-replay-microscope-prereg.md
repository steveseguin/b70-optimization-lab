# Qwen3.8 sealed TP2 prompt-24 replay microscope preregistration

Date: 2026-08-20

Status: preregistered; M1 has not launched.

## Question

A broad target/verifier post-forward synchronization did not make the sealed
TP2 lane exact. Can one bounded replay-microscope record of the first prompt-24
execution show whether a corrupt first emitted token is already selected by
the target logits or appears later at sampling/output?

This is a perturbative diagnostic, not a performance arm or a determinism
screen. The microscope starts at `inputs`, where tensor reductions and host
copies synchronize rank 0 before the target forward. Therefore a sane or new
output family is inconclusive scheduling evidence; it cannot be called a
repair. Historical full microscope use wedged the async/MTP path after seven
records, so this experiment permits exactly six records and one server arm.

## Frozen identity

Driver:
[`../scripts/run-20260820-detpad-tp2-replay-microscope.sh`](../scripts/run-20260820-detpad-tp2-replay-microscope.sh)

M1 restores C1's unsynchronized sealed identity and full request history:

- GPUs 2,3, TP2, native MTP5, FP16, seed 0, margins zero;
- complete `4dd33601...` composite with graph-safe FA `33938cdd...`;
- oneDNN W4A16 determinism pad on, with one marker required per rank;
- native GDN on, ReplaySSM speculative path off, persistent scratch on;
- exact sealed b991 graph/AOT cache, direct loads only, byte-identical
  postflight;
- frozen 25-prompt order, smoke, fresh-response, and cached-zero gates;
- target/verifier post-forward synchronization off and expected off;
- packet and layer tracing off; quality skipped;
- B2 retained only as the existing report-only target-token reference; no
  peer-parity requirement can turn a scientifically different trace family
  into an infrastructure failure.

The driver pins C1's checksum set, environment, recurrence evidence, benchmark,
cache, B2 reference, and quality-baseline bytes. It requires clean pushed
`main`, an absent M1 root, and the immutable sealed checker snapshot.

## Microscope contract

The source receives these exact effective values through explicit
`VALIDATION_*` passthrough:

```text
FILE=<M1 root>/replay-microscope.jsonl
MAX_LINES=6
RANK=0
REQ_REGEX=^chatcmpl-bench-qwen36-27b-int4-independent-validation-20260815-v1-24-holdout--long-rollover-repository-audit$
TENSOR_LIMIT=1
TOPK=0
MIN_TOKENS_NO_SPEC=849
MAX_TOKENS_NO_SPEC=849
```

`TOPK=0` suppresses the duplicate whole-logits top-k capture. The one-row
logit helper still clamps to top-2, retaining the target top-1, runner-up, and
margin needed for diagnosis with less added work.

The post-run sealed checker must parse exactly six JSONL objects in this order:

1. `inputs`;
2. `hidden_after_forward`;
3. `sample_hidden`;
4. `logits_after_compute`;
5. `pre_sample`;
6. `sampler_output`.

Every record must be rank 0, match the exact internal `chatcmpl-...` request
ID, and contain exactly the prompt-24 token window with both prompt tokens and
`num_tokens_no_spec` equal to 849. Required tensors, one-row top-2 logits, and
one sampled-token head value must exist. Missing, malformed, duplicate,
misordered, wrong-request, wrong-rank, error-bearing, or warning-bearing trace
evidence fails closed. The checker records the raw trace SHA, top-1 values,
sampled token, benchmark first token, non-finite paths, and coherence booleans.
It preserves non-finite values or token disagreement as scientific evidence
rather than classifying them as malformed instrumentation.

## Stop and interpretation rules

1. Stop on any model, runtime, pad, cache, direct-load, freshness, cleanup, or
   structural trace-gate failure. Preserve partial artifacts; do not retry.
2. Run exactly one M1 arm. Never use its throughput for a comparison or
   LocalMaxxing submission.
3. If M1 emits a sane or new family, the microscope changed scheduling before
   the forward and the localization is inconclusive. Do not repeat it to claim
   determinism.
4. If the corrupt first token survives and target top-1 is already corrupt at
   both logit stages, the first bad value is upstream of sampling; compare the
   hidden and sample-hidden records before designing a narrower layer/state
   probe.
5. If target top-1 is sane but the sampled or emitted token is corrupt, the
   first visible split is downstream of target-logit computation. Treat any
   sampled-token versus benchmark disagreement as evidence to inspect, not a
   trace-parser success criterion.
6. If the server wedges, the JSONL is incomplete, or tracing reports an error,
   classify M1 as an invalid/invasive diagnostic and stop.

Parent result:
[`2026-08-20-detpad-tp2-postforward-sync-result.md`](2026-08-20-detpad-tp2-postforward-sync-result.md)

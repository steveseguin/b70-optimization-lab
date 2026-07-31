# Segmented DFlash in-place collective boundaries

Date: 2026-07-30 America/Toronto

Status: **preregistered before implementation or device execution.**

## Evidence and hypothesis

The exact segmented-DFlash candidate's first cold 13-prompt leg measured
`119.18937096651626 tok/s` under the historical published metric and
`117.9974772568511 tok/s` under preferred 99-interval accounting:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
  laguna-dflash-segmented-scored-20260730T150033Z
```

It is 13/13 token-and-text exact, cache-zero, and preserves the target's
146/145 plus the drafter's 20/19 audited topologies on all four ranks. A clean
post-device-loss reboot has since passed strict idle, one changing-value
single-device check on each physical B70, and exactly one corrected TP4 probe
with `PROBE_RESULT=PASS clean_teardowns=4/4`.

Each of the drafter's thirteen eager all-reduce boundaries currently does:

1. copy the captured graph segment's `[12,3072]` BF16 result into a separately
   preallocated fixed-address tensor; then
2. all-reduce that copied tensor in place.

The copy preserves a stable address for the following graph segment, but it
also submits thirteen additional device copies per speculative cycle. The
captured graph's own boundary result already has a fixed replay address. If
the state retains that exact tensor strongly after capture and validates its
full identity on every eager callback, the all-reduce can operate in place
without changing collective order or arithmetic.

## Sealed treatment

Add one default-off selector:

```text
VLLM_XPU_LAGUNA_DFLASH_INPLACE_COLLECTIVES=1
```

It is valid only with the exact BF16-KV width-12/depth-11 segmented-DFlash
contract. The treatment:

- keeps all thirteen TP all-reduces eager;
- keeps their order and XCCL operation unchanged;
- keeps six attention operations eager;
- keeps draft topology at exactly 20 graph segments / 19 eager breaks;
- keeps target topology at exactly 146/145;
- retains one strong reference and immutable tensor signature per collective
  slot after capture; and
- replaces `copy_(local); all_reduce(output)` with `all_reduce(local)` only
  after the slot's captured address, storage offset, shape, stride, dtype,
  device, and contiguity have been established.

The selector-off path must remain byte-for-byte behaviorally unchanged. No
target or draft weight, quantization, BF16 KV semantics, DFlash depth, target
width, sampling/rejection rule, prompt, scoring window, cache policy, graph
count, or collective count changes.

## Gates and stop rules

1. CPU/static tests must prove selector-off behavior, one-time slot binding,
   strong ownership, signature checks, order/count accounting, replay
   accounting, overflow, replacement rejection, and no preallocated copy
   buffers when the treatment is enabled.
2. Inspect the resulting source and preserved patch directly; do not trust an
   edit tool's success message.
3. Run one non-scored two-request, 400-token segmented smoke. It must be
   q1-prefix exact, cache-zero, exceed cycle 33 independently on both
   requests, retain a normal decaying acceptance curve, prove 146/145 and
   20/19 on every rank, and shut down cleanly.
4. Any identity drift, topology drift, token mismatch, zero/flat draft,
   collective hang, worker leak, or idle failure rejects the route. Do not
   retry, run a reset ladder, reload/unbind the driver, issue FLR, or delete
   shared-memory objects.
5. Only after the smoke passes may one cold 13-prompt scored leg run. Report
   the first valid result whether it wins or loses; do not warm, retry, omit
   prompts, move capture outside the scored window, or select the better of
   repeated starts.

This note makes no throughput or correctness claim for the treatment.

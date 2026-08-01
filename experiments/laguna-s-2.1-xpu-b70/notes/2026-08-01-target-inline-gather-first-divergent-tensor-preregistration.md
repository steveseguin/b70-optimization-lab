# Laguna target inline-gather first-divergent-tensor trace

Date: 2026-08-01 America/Toronto

Status: **preregistered; diagnostic only. No score or speed claim is
authorized.**

## Motivation

The protected BF16-KV record remains `125.4619731637751 tok/s`, 13/13 exact,
with target topology `146/145` and draft topology `14/13`. Capturing a prefix of
24 target all-gathers produces the expected `122/121` target topology but first
changes request-0 output token 331 during the frozen 512-token gate. Prefix 48
is exact for one 512-token request but changes request 1 token 0. These lifetime
results show that slot-local synthetic equality is insufficient; they do not
identify the first model tensor corrupted by replay.

## Diagnostic treatment

Use one new diagnostic vLLM worktree based on the prefix-bisection source. Run
two fresh services from that same source and the protected native kernel build:

- control: target inline gathers off, target topology `146/145`;
- candidate: target inline gathers on with prefix limit 24 and no skipped slot,
  target topology `122/121`.

Both arms retain BF16 KV, width 12, DFlash depth 11, segmented/inline DFlash,
the exact current target stack, the frozen request-0 prompt, and every sampling
parameter. Both arms enable the same parity instrumentation. The probe must be
target-only (`num_hidden_layers == 48`), use an explicit NVMe artifact root,
and record a bounded list of target `compute_logits` calls. Each packet records
the call number, input token, final verifier position, logits, embedding, every
layer's norm/attention/MLP/residual boundaries, and the existing detailed
layer-0 attention stages.

The trigger is created only after health so startup/capture calls cannot consume
the diagnostic call numbering. Multi-call packets live in separate per-call
directories. The trigger is removed on every success or failure path. Legacy
single-call trigger behavior remains unchanged.

## Ordered gate

1. Implement only configurable artifact-root, target-only, and bounded
   multi-call support. Preserve the selector-off/default behavior. Pass Ruff,
   compileall, focused tests, and source inspection before any service start.
2. First run the prefix-24 candidate with sampled calls. Require the already
   established first mismatch at request-0 token 331, `cached_tokens=0`, real
   speculation, exact `122/121` and `14/13` topology, complete four-rank
   packets, and clean teardown. If parity instrumentation removes or moves the
   mismatch materially, stop: the probe is perturbative and cannot localize
   this defect.
3. Run the matched selector-off control once using the identical call list and
   source. Require q=1 exactness, `146/145` and `14/13`, complete packets, and
   clean teardown.
4. Compare only calls whose input token and final verifier position match on
   every rank. Search tensors in model order and report the first bitwise
   difference. Comparisons after call alignment is lost are invalid.
5. If samples bracket the first divergent call, one refinement pair may sample
   only that bracket. Do not repeat an unchanged arm.
6. Any hang, device/collective error, missing execution marker, incomplete
   packet, or dirty teardown stops the experiment. Do not reset, reload,
   unbind, FLR, delete shared memory, or reboot.

## Decision rule

A matched first divergent tensor authorizes one separately preregistered repair
at that boundary. No endpoint integration is authorized by this trace. If the
first difference precedes a captured gather, or the instrumentation changes the
known output failure, close the inline-gather route until a less perturbative
probe exists.


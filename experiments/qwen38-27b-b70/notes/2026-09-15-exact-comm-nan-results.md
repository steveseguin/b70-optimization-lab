# Exact two-card communicator: NaN characterization results

Run `nan-semantics-01`, September 15, 2026, newest-base image `506fcc26`, two
B70s, no IPC. The stage completed cleanly: no kernel fault lines, the host-memory
guard exited normally and container exit was confirmed.

**No fixed add formulation can match XCCL bit for bit, but every disagreement is
between two NaN results. All real numbers and infinities matched exactly.**

## What was compared

Every ordered pair of 21 FP16 edge values (quiet and signaling NaNs with several
payloads and both signs, infinities, signed zeros, ones, maximum finite and a
subnormal), tiled over shapes 1, 2, 512 and 4,096 rows × 5,120. Each rank ran
standard XCCL all_reduce and four local add formulations: FP32 or native half,
with either rank's operand first.

## Findings

- XCCL outputs agree between the two ranks at every shape.
- Every formulation disagrees with XCCL on the same number of elements (for
  example 648 of 5,120 at one row, 2,567,965 of 20,971,520 at 4,096 rows).
- A classification of every mismatch, every mode, both ranks and all shapes
  found only one kind: XCCL returned a NaN and the formulation returned a NaN
  with a different payload or sign. There were no NaN-versus-number and no
  number-versus-number differences.
- For every element at least one formulation matched: XCCL's choice between the
  two NaN operands depends on the element's position, so no single per-element
  rule reproduces it.

## Consequence

Under the current rule, which requires every output bit including NaN payloads
to match XCCL, the communicator cannot pass and stage 05 is not admitted. It
could only continue if NaN results were compared as a class (any NaN equals any
NaN, while every non-NaN bit must still match). That is a change to the lab's
quality oracle and needs the user's decision.

## User decision

The user chose to count any two NaN results as equal for this communicator,
with every other output bit still required to match XCCL and inputs still
required to stay unchanged. The decision is recorded as `NAN-CLASS-DECISION.json`
in the campaign root, bound to this verdict's hash. Stage 05 admission re-analyzes
the saved outputs under that rule: all four formulations then match on every
element, and the Native04 arithmetic (`m0`) is selected. The gate records both
the rule result and whether each output was also bit-exact.

## Stage 05 result (operator screen)

`communication-native-05` ran September 15 12:45 UTC with the Native04
arithmetic (`m0`), peer IPC and the NaN-class rule. Both ranks passed all 64
quality cases at 1, 2, 512 and 4,096 rows (24 of 32 per shape were also
bit-exact; the rest differ only in NaN payload), finished all timing blocks and
retired their peer mappings normally. No kernel fault lines, the memory guard
exited cleanly and the container exited 0. The stage controller still ran the
pre-decision bit-exact analyzer and labeled the run failed; the saved outputs
were re-analyzed offline under the NaN-class rule
([re-analysis](../data/2026-09-15-exact-comm-stage05/analysis-nan-class.json)).

| Rows per call | XCCL, µs | Candidate, µs | Paired median change | Blocks faster |
| ---: | ---: | ---: | ---: | ---: |
| 1 | about 60 | about 155 | 153% slower | 0/5 |
| 2 | about 70 | about 155 | 124% slower | 0/5 |
| 512 | about 190 | about 245 | 30% slower | 0/5 |
| 4,096 | about 1,280 | about 1,200 | 8.2% faster | 5/5 |

Only the 4,096-row shape meets the operator gate (at least 5% paired median and
all blocks positive). This is an isolated operator timing that excludes the copy
a real integration would need to put model activations into the dedicated
buffer. Decode uses one or two rows per call, where the candidate is more than
twice as slow. At 4,096 rows the saving is about 0.1 ms per all-reduce; even
before integration costs that is on the order of 1% of a long prompt's prefill
time. The communicator is therefore not worth integrating for this lane; XCCL
stays. The clean IPC run without a fault also weakens the earlier suspicion that
the peer-mapping path itself caused the September 14 GPU fault, but one clean
run does not establish its cause.

Evidence: `/mnt/fast-ai/bench-results/optimization-validation-20260915/nan-semantics-01`,
`communication-native-05` and `communication-native-05-reanalysis`;
`/mnt/fast-ai/bench-results/optimization-validation-20260915/nan-semantics-01`
and [verdict copy](../data/2026-09-15-exact-comm-nan-semantics/nan-semantics-verdict.json).

# Qwen3.8 official-FP8 TP1 strict target-control result

## Decision

TP1 also fails the frozen fresh-server output gate. TP2 and cross-rank oneCCL
collectives are not required for the official-FP8 instability observed by this
suite. Do not run the planned TP2 P2P-off screen as a determinism fix.

| Attempt | Class-balanced decode | Workload/canaries | Cached tokens |
| --- | ---: | --- | ---: |
| R5A | `11.405360 tok/s` | pass | 0 on every row |
| R5B | `11.413057 tok/s` | pass | 0 on every row |

Only `8/12` complete token arrays matched. The divergent prompts and first
zero-based divergence positions were:

- `customer-email`: token 6, with natural lengths 281 versus 302;
- `sql-debugging`: token 23;
- `incident-retrospective`: token 34;
- `code-review`: token 130.

The [machine-readable comparison](../data/2026-08-27-qwen38-fp8-tp1-strict-target-control-comparison.json)
is generated directly from the two raw `performance.json` token arrays by the
general [strict comparator](../../../scripts/compare-strict-attempt-outputs.py).
Both attempts used the same official FP8 model revision, default FP8 dispatch,
MTP0, eager/graph-off execution, GPU 0, a new container, and a new empty
non-prompt cache directory.

## Scope

This result removes TP2 and cross-rank collectives as necessary causes; it does
not identify the remaining one-rank cause. Candidate surfaces include the
official-FP8 kernels, reductions, and runtime scheduling/numerics. The small
objective canaries are stable, but that cannot override four full-response
divergences.

The result has no authority to fill a TP2 headline, MTP1 32K, aggregate, or
long-context cell. It is also not a semantic-degradation claim: it is a failure
of the lab's stricter no-unadjudicated-output-change rule. The exact frozen
contract is in the [preregistration](2026-08-27-qwen38-fp8-tp1-strict-target-control-prereg.md).

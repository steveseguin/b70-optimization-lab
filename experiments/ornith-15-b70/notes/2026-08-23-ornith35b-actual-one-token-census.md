# Ornith 1.5 35B-A3B: actual one-token dispatch census

## Why the earlier profile needed an execution audit

The accepted eleven-feature stack intercepts logical graph nodes before the
generic SYCL dispatcher. A serialized logical-op profile can therefore charge
deferred work to a node that never launches its stock kernel. It is useful for
finding boundaries, but it is not a census of the kernels that survive the
accepted Qwen-derived fusions.

This diagnostic logged a node only at the final generic dispatch point, after
every accepted fusion and skip rule declined it. The capture gate required both
`result_output=[248320,1]` and `linear_attn_out-0=[2048,1]`. The second condition
matters: the output request can contain one row while the internal graph is
still processing more than one token.

## Measured dispatch inventory

The true steady-state graph contained 3,726 logical nodes and **592 actual
generic dispatches**:

| operation | launches/token |
| --- | ---: |
| `MUL_MAT` | 311 |
| `MUL` | 80 |
| `UNARY` | 70 |
| `L2_NORM` | 60 |
| `MUL_MAT_ID` | 40 |
| `SET_ROWS` | 10 |
| `FLASH_ATTN_EXT` | 10 |
| `CONT` | 10 |
| `GET_ROWS` | 1 |

There were zero surviving `ADD`, `SCALE`, `CONCAT`, `CPY`, `SSM_CONV`,
`RMS_NORM`, `ROPE`, or `GLU` dispatches. The diagnostic counters independently
recorded the expected accepted hits: 40 routed gate/up, 40 MoE shared-tail, 40
residual/RMS, 30 alpha-gate, 30 convolution/SiLU, 30 direct concat/state, 30
GDN state-I/O, 30 GDN RMS/gate, and 10 Q/K norm/rope.

The 311 projections split exactly into the model's Qwen-derived families: 60
alpha/beta, 40 routers, 40 shared-expert projections, 40 shared scalar gates,
30 recurrent QKV, 30 recurrent Z, 30 recurrent outputs, ten each of attention
Q/V/K/output, and one vocabulary head. The remaining non-projection families
also map to known boundaries in the do-not-repeat ledger.

## Decision

The audit validates that the eleven accepted fusions remove the launches they
claim. It also closes the misleading interpretation that the large serialized
`GET_ROWS` attribution represented recurrent gathers: only the already-tested
one-row output-head gather survives.

No throughput value is inferred from launch counts. The diagnostic patch is
not shipped and the accepted source was restored before rebuilding. Future
decode work should tune a remaining projection kernel or prove a genuinely new
cross-kernel dataflow; re-screening an absent logical operation is not useful.

Structured counts are in
`../data/2026-08-23-ornith35b-actual-one-token-census.json`; the compressed raw
log and the exact diagnostic patch are archived beside it.

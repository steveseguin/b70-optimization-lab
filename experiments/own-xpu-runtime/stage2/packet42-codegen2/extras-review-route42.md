# Independent route42 identity review

Reviewer: parallel/extras agent, not the route42 implementer. Reviewed the
actual packet18 adapter route family, including compact and scheduled bindings.

The retained maximum, exponential/subtree and selected-normalization phases
match the incumbent expression order. Merged rank recomputes `ex[k]/den` with
the identical upper adjacent tree, so ties remain ties after the same FP32
rounding. Integer counts partition over 32 lanes; their subgroup sum is exact
and cannot overflow (at most512). Only the winning rank writes, and lower input
ID retains stable priority. Event dependencies separate all phases. Inactive
and sticky-error checks keep the original policy. No local memory or barrier
was introduced. The128-byte concrete Args guard is present.

Two review findings were fixed before completion: the CPU/native frozen Core
reference was given a1MiB scratch arena rather than reusing the smaller device
stage scratch; and folded route descriptor expectations are explicitly derived
from the unchanged selected IDs, since Core route itself only supplies IDs and
probabilities. The native fixture uses scheduled ni3/no4 bindings and U32 route
descriptor types. Device memory/live/alignment/extent and conflicting
output/control/scratch guards are present.

The device fixture’s core oracle has finite valid inputs; invalid routes,
nonfinite input rejection, ties, inactive/sticky controls and odd sizes are
covered separately by the120-case host gate. No blocking arithmetic issue
remains in the reviewed source. Device byte equality and timings remain
pending and are not inferred from these CPU checks.

Reviewed SHA256 identities:

```json
{
  "route42.hpp": "96a9c2809d8416bbd24c37fb89c101ca810221cdabe324ed36fc357486b1f51f",
  "route42_submit.cpp": "96a1eac29ad37a1da75f20ec66e454448cc0ab958d659694c348cdbbe311de8d",
  "route42_cpu.cpp": "142deed2b70610f58ae5dabecf5587b7da7c96eb74cd8f349f37243728bab22a",
  "route42_timing.cpp": "11763d421c138e249bcf64a8de1bebcaa7b962144fd71d20ad7d6e58d8c76339"
}
```

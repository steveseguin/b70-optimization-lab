# Ornith 1.5 35B-A3B: twelve-feature one-token dispatch census

Date: 2026-08-23 EDT

Status: **diagnostic only; no throughput inference**

The accepted twelfth feature folds the Qwen-derived shared-expert sigmoid and
broadcast multiply into the existing shared/residual/RMS kernel. A fresh audit
at the final generic dispatcher captured the first graph containing
`linear_attn_out-0=[2048,1]`, an internal marker for real one-token recurrent
execution.

The graph still has 3,726 logical nodes, but only **512 actual generic
dispatches** survive:

| Operation | Launches/token |
| --- | ---: |
| `MUL_MAT` | 311 |
| `L2_NORM` | 60 |
| `MUL_MAT_ID` | 40 |
| `MUL` | 40 |
| `UNARY` | 30 |
| `SET_ROWS` | 10 |
| `FLASH_ATTN_EXT` | 10 |
| `CONT` | 10 |
| `GET_ROWS` | 1 |

Compared with the eleven-feature census, this is exactly 80 fewer launches:
40 fewer `UNARY` nodes and 40 fewer `MUL` nodes, with every other family
unchanged. This independently verifies the source matcher’s launch-removal
claim.

The remaining graph is projection dominated. The surviving elementwise
families are the 40 routed-expert weights and 30 recurrent beta sigmoids;
both already have bounded negative or neutral investigations in the ledger.
The 60 L2 norms and the major projection pairings have also been screened.
That makes a device-kernel timing trace more useful than another launch-count
guess for choosing the next candidate.

Raw rows are in
`../data/2026-08-23-ornith35b-twelve-feature-actual-one-token-census.stderr.log`;
the structured reduction and diagnostic patch are adjacent. The source was
restored to accepted diff SHA-256
`7b9204f8f44608fc5b1858a15498b3cf9bf52b4f02c27c0f91a1807af5b5d15d`
before rebuilding.

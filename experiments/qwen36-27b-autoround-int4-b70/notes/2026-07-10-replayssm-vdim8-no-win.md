# ReplaySSM `vdim8` recurrent bucket experiment (2026-07-10)

## Outcome

No win; restored `v_dim_per_sg=4` and skipped endpoint testing.

The ReplaySSM recurrent kernel assigns four value dimensions to each subgroup.
Increasing this to eight halves the number of value buckets and could have
reused Q/K normalization, history scores, and token matrices across more value
dimensions. A first cross-card measurement misleadingly suggested a large
recurrent gain, so the candidate was retested with card and order controls.

## Validation

The isolated `vdim8` extension passed the existing real-shape recurrent parity
guard, including exact pending metadata. The performance test then ran eight
fresh processes per GPU in balanced ABBA order on two GPUs, with the assignment
reversed between cards, 200 warmups, and 3000 timed iterations per process.
No continuous `xpu-smi` observer or endpoint server was active.

Card-balanced means:

| Region | `vdim4` | `vdim8` | Candidate change |
| --- | ---: | ---: | ---: |
| recurrent spec decode | 36.5675 us | 36.5762 us | +0.0240% slower |
| stage + recurrent pair | 43.7662 us | 43.7475 us | 0.0427% faster |

The pair effect changed sign by GPU: `-0.1733%` on GPU 0 and `+0.0887%` on
GPU 1 (negative means faster). This is measurement noise, not an optimization.
The initial apparent gain came from comparing different cards/cold states.

Artifacts are under
`data/qwen36-27b-autoround-int4-b70-profiles/replayssm-vdim8-20260710/`.
The one-line candidate patch is retained under
`patches/qwen36-27b-autoround-int4-b70/` for future architecture work.

## Learning

Simply widening the subgroup value bucket does not reduce the real kernel cost;
the compiler/hardware already overlaps the repeated scalar work or the added
register pressure cancels it. A credible next recurrent change must explicitly
share Q/K and token-matrix intermediates without increasing each subgroup's
live value-state footprint, or target the larger verifier-forward/LM-head cost.

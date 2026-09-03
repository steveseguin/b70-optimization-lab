# Decision memo: the exact-2K output authority for the Flash-Next TP4 line

Date: 2026-09-03 (for the user; nothing changes until they decide)

## The two records

| | native line (protected) | deterministic line (candidate) |
| --- | --- | --- |
| hash | `5fd297f79da317b0741140cccb52fb710f89dfd1444effe9068b806b0300e57e` | `afffd2110812762164862b6388f054bb56696ee57b07eadce411a702c40bc714` |
| origin | eager 3072-context attempt 2, 2026-08-27 | A70, A71, A72 (2026-09-02/03) |
| servers that reproduced it | 1 (plus matches in A9/A24-era runs; the same server class failed its own 2K/4K repeat in A7, A10, A15, A24, A25, A56, A58-A65) | 3 independently started servers, both rows each, byte for byte |
| logit-level exactness of the producing server | no (A58-A65 probes: first-step spreads 0.005-0.36 nats) | yes (A66/A67 probes: 8/8 identical first steps, 3/3 identical 128-token repeats, spread 0.0, depths 8-2048) |
| first difference | token 12 of 128 | |
| text at the difference | `"branch": "main", "prompt": "You are refactoring ... Include one risky step and how to verify it."` | `"branch": "main", "commit": "0000...", "prompt": "You are refactoring ... Include enough detail for a maintainer to execute the refactor directly."` |
| semantic battery, 16-repeat, needle | unchanged | unchanged |

Both continuations are well formed and on task; the divergence is a
near-tie choice inside a JSON fixture, not a quality event.

## Recommendation

Adopt `afffd211...` as the exact-2K authority of the deterministic graph
line and keep `5fd297f7...` as the native-line record, unchanged and
labelled as produced by a logit-jittery server class. Reasons: the
deterministic line is the only one that can be reproduced by a third party
on demand; three servers agree; the native record cannot be regenerated
reliably even on this host. The same policy should govern the 4K authority
when A73 runs (see the A73 proposal): first attempt records the candidate,
second attempt pins it.

## What promotion then looks like

The A70/A71/A72 triple becomes the promotion record of the deterministic
full-decode-graph TP4 endpoint at 2304 tokens: three-attempt short center
`23.028483 tok/s` (native A56 single attempt `23.626811`), exact-2K rows
`13.18-14.62 tok/s`, quality boundary unchanged, runtime receipt present
(A72). The eager deterministic line (A66) is the reference for the probe.

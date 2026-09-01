# Qwen3.8 Flash-Next FP8 TP4 graph allreduce selection

Date: 2026-09-01
Status: lossless component positive; endpoint qualification pending

The production-shaped collective screen now has a robust winner. With public
graph-safe oneCCL `4ceafd1`, threshold `4096`, and 97 ordered BF16 `[1,2560]`
allreduces in one graph, `twoshots` reduced the slowest-rank critical path by
`7.293496%`, `6.180802%`, and `4.678938%` across three fresh matched pairs.
The median was `6.180802%`; all three pairs cleared the frozen `3%` floor.
Every arm matched the CPU oracle for 100 changing-input replays on all four
ranks, produced 100 unique composite hashes per rank, and emitted no oneCCL
error.

Two evidence qualifications matter:

- The A1 census generated an over-broad summary. Its raw logs show that the
  deployed library accepts only `ring` and `twoshots`; `ring_markers` and
  `recursive_doubling` emitted an error and fell back. Their apparent timings
  are not valid measurements of those named algorithms.
- The first A2 confirmation requested 200 unique replays, but the existing
  changing-input fixture repeats after 127. Its trial-1 assertion failure is a
  procedural negative, not a collective or device failure. A3 used the valid
  100-replay bound and completed all six arms.

This is component evidence, not a model-speed claim. The projected gain is
only a few percent at the endpoint, so `twoshots` will be combined with any
other bit-exact component winner and then tested once in a fresh A47-style
host-guarded full-model graph arm. Protected eager and A44 diagnostic results
remain unchanged.

Structured result:
[`../data/20260901-allreduce-twoshots-component-confirmation.json`](../data/20260901-allreduce-twoshots-component-confirmation.json).
Full evidence remains outside Git under the three `20260901-allreduce-*`
component directories recorded there, with the completed A1/A3 manifests.
The A3 manifest seals its launch order, summary, and six logs, but that folder
does not contain its own runner, command transcript, device discovery, or
identity receipt. It is therefore sufficient to select the candidate but not
a self-contained reproduction packet. The endpoint successor must bind the
exact library, selector, source, and complete quality identity itself.

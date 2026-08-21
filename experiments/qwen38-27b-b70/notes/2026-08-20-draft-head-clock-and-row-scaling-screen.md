# Qwen3.8 draft-head clock and row-scaling screen

Date: 2026-08-20

Classification: **clock locking closed as neutral; operator scaling only**

Structured evidence:
[`2026-08-20-draft-head-clock-and-row-scaling-screen.json`](../data/2026-08-20-draft-head-clock-and-row-scaling-screen.json)

The measuring host compared the exact TP-local INT4 draft-head shape at its
normal `400-2800 MHz` range and at a fixed `2800 MHz` on physical GPU 2. M1
moved from `555.534` to `554.583 us` (`+0.171%`), while M6 moved from
`568.946` to `568.972 us` (`-0.0047%`). The clock range was restored to
`400-2800 MHz`. Together with the earlier position-balanced endpoint screen
that put a `2750-2800 MHz` floor at `-0.487%`, this closes clock locking as a
route to the requested `105 tok/s` target.

The two-B70 15-GiB worker cannot load the full model, so it instead ran the
same `4dd336...` W4A16 runtime through the existing weighted TP2 projection
profile on each card. Its row-6/MTP5 projection sum was `5.69%` and `5.66%`
cheaper than row 1. That is useful cost-model evidence for speculative
geometry; it is not endpoint latency, a clock comparison, or evidence that
MTP5 output throughput improves by the same percentage. The remote command
was stdout-only and wrote no raw result artifact, which is explicit in the
structured packet.

Decision: leave clocks at their default range, spend no full-server run on
power/clock tuning, and use the second computer only for source/operator work.
The active measuring-host candidate is the separately preregistered TP2
draft-margin correctness qualification; its diagnostic timing is invalid by
design.

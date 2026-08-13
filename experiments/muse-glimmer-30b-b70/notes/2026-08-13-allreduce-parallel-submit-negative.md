# TP4 allreduce parallel host submission

Date: 2026-08-13

## Decision

Close and revert the OpenMP-parallel TP4 allreduce submission path.  It was
arithmetic-exact, but a canonical 64-token control/candidate/control screen
measured a `-0.300%` arithmetic-mean regression.  Keep the incumbent serial
collective submission plus last-event readiness optimization.

## Why this was tested

The retained F32 recursive-doubling allreduce submits 16 commands from one
host thread at each TP4 boundary: four peer pulls and four adds in each of two
rounds.  Muse has 104 such boundaries per target pass.  The earlier
last-event optimization showed that command submission overhead is material,
while the prior persistent meta-thread experiment left collectives on the
master thread.

The candidate kept the two recursive-doubling rounds and F32 expression
grouping unchanged.  One four-thread OpenMP team submitted each independent
four-rank pull phase and add phase, with implicit phase barriers and the
incumbent peer events.  It was restricted to TP4 contiguous F32 tensors and
default-off behind `GGML_SYCL_COMM_PARALLEL_SUBMIT=1`.

## Result

All candidate hashes, proposal counts, and accepted counts matched both
controls exactly.

| arm | prose | code | JSON | arithmetic mean |
| --- | ---: | ---: | ---: | ---: |
| pooled controls | `69.344` | `114.5915` | `222.0185` | `135.318` |
| parallel submit | `68.388` | `114.550` | `221.800` | `134.9127` |
| candidate/control |  |  |  | **`0.997005x`** |

Request-derived milliseconds per speculative round were:

| arm | prose | code | JSON |
| --- | ---: | ---: | ---: |
| pooled controls | `57.6834` | `50.7732` | `48.0440` |
| parallel submit | `58.4898` | `50.7916` | `48.0914` |

The repeated OpenMP phase barriers cost more than the host-submit
serialization they remove, especially in prose.  Do not build a persistent
collective worker pool from this implementation without a materially
different no-barrier design.

## Evidence and operations

- source snapshot:
  `patches/muse-allreduce-parallel-submit-negative-20260813.patch`;
- sweep identity:
  `experiments/muse-glimmer-30b-b70/sweeps/20260813-dflash-allreduce-parallel-submit-smoke-cac.json`;
- JSONL SHA256:
  `dc377709ec2e84898957357fb7dab1697bacae9f374eca9a34f50e0b3de18e22`;
- control-before log SHA256:
  `558e9f2a06a02bdad045229944bbc25916528964969a58da32deeef8916001f6`;
- candidate log SHA256:
  `cf862e998410473679adad0b55bd3feffd2300010f68587a8b5df09e5842fafd`;
- control-after log SHA256:
  `9469e8dd471bbd05fdedf7074de5c741fa480fe636c5e32ed30aba2a8f25a851`.

The source experiment was reverted without a source commit. Production was
restored without reboot and passed the full cache-zero 512-token code and
vision health gate in
`data/muse-health-20260813-allreduce-parallel-submit-restore.json`.

# Packet87t decision

Measured transfer microbenchmark; gains below are predictions, not model speeds.

- target: +1.0685%; eligible for a seal-ready implementation design.
- draft: +0.7749%; eligible for a seal-ready implementation design.

| Transfer | Median µs | p90 µs |
| --- | ---: | ---: |
| best16/compute | 64.476 | 66.364 |
| best16/idle | 14.317 | 16.451 |
| best8/compute | 64.627 | 66.715 |
| best8/idle | 14.357 | 16.611 |
| hidden/compute | 66.435 | 68.820 |
| hidden/idle | 15.193 | 17.673 |
| mailbox20480/idle | 1.307 | 1.733 |
| pipeline20480/compute | 73.342 | 76.063 |
| pipeline20480/idle | 24.897 | 26.399 |

Exact model inputs and all idle/compute median/p90 sensitivities: [RESULT.json](RESULT.json).
Any eligible design still requires row arithmetic, tie/finite checks, memory admission and fresh-process output gates.

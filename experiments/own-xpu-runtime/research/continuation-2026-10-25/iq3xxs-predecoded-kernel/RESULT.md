# IQ3_XXS predecoded kernel candidate

Standalone B70 microbenchmark passed 409,600 bitwise output comparisons over 64 varied route cases. Median paired calls: packed 62.839 us, predecoded 48.864 us (1.286×); measured difference across 34 calls is 0.4751 ms per target pass. This is not an output-throughput result.

The candidate expands each 98-byte block to 266 bytes, so allocation/placement budgets must be solved before integration. Loader and production runtime remain unchanged. The retained headers and benchmark source are the tested candidate; [summary](summary.json), [command](run-command.json) and [raw result](run.log) retain the experiment. Full host observations remain in tmpfs at the source directory.

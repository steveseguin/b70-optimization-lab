# Grouped GDN state rows (card 27, 2026-10-27)

`OWNRT_GDN_STATE_ROWS=2` and `=4` were lab-only attempts to process two or four independent recurrent-state rows per 32-lane subgroup, reducing the 6,144 tiny workgroups in each GDN launch. Q/K preparation, per-row reduction, serial recurrence and state-update order were unchanged. The unprepared path and token-one behavior with the switch unset remained the B24 path.

## Exactness

The OpenCL CPU-device test ran both geometries through 80 cases and 320 calls across BF16/F32, packed/unpacked heads, state aliases, four serial tokens and guard/error cases: **1,014,501,120 compared bytes, zero mismatches**.

Each full rank-0 GPU run matched B24 across **1,029 target buffers and 71 draft allocations**, with identical prefill/decode draft tokens and no other differing fields. No kernel GPU fault lines were present after the experiments.

## Result: rejected

Device profiling used the same 256-token prompt and 48 decode halves for all three arms.

| Arm | GDN busy per half | Total device span per half |
|---|---:|---:|
| B24 single row | **566.77 µs** | **10,129.2 µs** |
| Two state rows | 597.29 µs | 10,201.1 µs |
| Four state rows | 596.87 µs | 10,203.9 µs |

Both grouped geometries cost about 30 µs per half. Reduced workgroup count did not remove enough overhead to offset the serial work per subgroup. Neither variant was integrated, and no unprofiled speed claim is made.

Binaries: four-row initial gate `729b83717671f09edcfe4fc8f1c21589f68ec851749f0c7d68b74a742b043b5f`; combined two/four-row build `076010a713764ebb1c16473aec900dbbe5250fa7081253b35a33b31550fdae19`.

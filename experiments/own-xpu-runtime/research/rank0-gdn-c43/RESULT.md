# Exact GDN producer/consumer schedule (card 43, 2026-10-26)

`OWNRT_GDN_PREP=1` changes only token-one GDN decode. Sixteen producer subgroups compute normalized Q/K and the 48
`decay`/`beta` gate values once; the incumbent 6,144 recurrent-state subgroups consume those F32 values. Product,
reduction and state-update order are unchanged. Multi-token calls retain the incumbent path.

- Patch: `gdn-prep.patch`; CPU-device test: `test_gdn_prep.cpp` (GPU access blocked).
- CPU: 40 cases, 160 calls, 507,250,560 compared bytes, zero mismatches. Covers BF16/F32, packed/unpacked heads,
  state aliasing, serial recurrence, inactive/invalid/sticky-error guards and gate boundaries.
- Candidate binary: `6ef80361db28d81e2b4e311fcc1016541c682f759a5e103b1b3b2d9c56281a15`.
- Reference and candidate both include B18's four draft switches.

| Round | Reference ms/half | Candidate ms/half | Delta |
|---|---:|---:|---:|
| 1 | 10.782 | 10.718 | -0.063 |
| 2 | 10.972 | 10.673 | -0.299 |
| 3 | 10.875 | 10.664 | -0.210 |
| **Median** | **10.875** | **10.673** | **-0.202** |

Diagnostic GDN cost: 649.374 -> 565.104 us/half. Profiling is not used for the speed claim.

Each of the three interleaved A/B comparisons and the diagnostic candidate passed 1,029 target buffers plus 71 draft
allocations with zero differences, no missing buffers or other differing fields, and identical prefill/decode draft
tokens. Every run held only renderD128 (PCI 0000:43:00.0) under `/dev/shm/card43.lock`; before/after kernel checks
found zero GPU fault lines.

B19 passed both context oracles with zero differences, prefill 13/13, continuation and prior-build session
compatibility. The cold 12-prompt suite matched B18 token for token and rose from 65.669 to 66.205 tok/s (+0.82%).
The 12.4K-token needle/continuation check passed; fresh decode measured 62.35 tok/s.
## Independent review and reproduction

Canonical B19 is binary `51f32b2655cc0a9d514081362ea6b3ceaa8b0d004df94fbbd83eb7fa76e3ae0a`. Independent code
review found no correctness defects in token gating, scratch sizing, launch dependencies, arithmetic, state aliasing,
multi-token fallback, guards or host-only compilation.

On card 47, one full unprofiled pair measured switch-off 10.8673 ms/half versus GDN_PREP 10.7077 ms/half (-0.1595 ms,
1.47%), with draft 1.7512 versus 1.7342 ms. All 1,029 target and 71 draft buffers matched and draft tokens were equal;
zero GPU fault lines. Evidence: `../rank0-iq4-c47/results-gdn.json` and `../rank0-iq4-c47/compare-gdn1.json`.

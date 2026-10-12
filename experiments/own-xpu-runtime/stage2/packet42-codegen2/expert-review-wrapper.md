# Independent wrapper and summary review

Reviewed CPU source only; no native device program was executed. The reviewer authored expert candidates, not the wrapper/summary/build generator.

Confirmed: the coordinator LD_LIBRARY_PATH is forwarded without rewriting; ldd accepts libraries resolved outside that variable. Kernel-log checks begin after the wrapper cursor, so old reviewed faults are not latched. Storage/JSON/refusal errors take the ordinary failed-window path. Atomic JSON writes remove incomplete temporary files and preserve failed-window stderr on ENOSPC. Missing /proc memory fields do not crash monitoring. The timeout is reported separately from its >=4x / >=300-second watchdog; the wrapper sends one SIGTERM and never hard-kills or retries. It writes failure before requesting teardown. Both native and wrapper return codes are checked; summary files are included in CPU mock-window tests.

Findings sent to the owner agent for correction:

1. T1 ordinary summary computes cases_passed from an empty K2 row list, hiding failed launch-floor cases. Propagate the floor rows' passed flags while retaining infrastructure success separately.
2. Heavy event aggregation collects buffer_copy IDs but never requires all eight actual banks. Require observed banks 0..7, not only the declared rotation_copies count.
3. Host timing is optional in aggregation although the requested output requires 200 host-wall samples. Missing wall samples must fail that case.
4. Dispatch family qualification checks only observed workloads. Require the registered complete workload set so a missing IQ3 workload cannot qualify the paired expert class from IQ2 alone.

The generated GEMV path retains the runtime's own incumbent submission (p28 paired/dense, p33 selected down), fixture CPU oracle, 200 measured repetitions and full eight-copy rotation with independent pre/post byte checks. Specialised/candidate failures are reported as rows. The build seals sources, old object identities and final binary hashes. No performance conclusion is made by this review.

Recheck: all four findings are corrected in the reviewed summary source. T1 failed rows propagate to cases_passed; heavy workloads require the observed copy set 0..7; host stats require 200 finite positive samples; dispatch requires both registered expert formats and the exact down/attention workload names. The source-hash binding below records this recheck. No remaining blocking wrapper/summary finding was found.

- `window.py` SHA-256 `7b82450ce6ce7a56e2b3534c2aeb11eeacd0f8ce5df2e44a49e8df1c022971e7`
- `summarize.py` SHA-256 `97de44fe3d1aedc2df6d6d6bd1fae17a4f7db5195e04d6dfc19ba7341b162f27`
- `build_gemv.py` SHA-256 `18a2d32a6e4956dfbcca3d5b09a836ecc3319d6d863fda5b476574485135c54a`
- `test_window.py` SHA-256 `9255ffec7549855640feabb79f0ddc53635258c7a215cd82863e78e10035858b`

Final normalization recheck: geometry_rows expands tiny/extras comma-separated aliases and validates every timing-eligible arm with 200 finite positive GPU and host samples. Untimed diagnostic rows cannot dispatch. Production route event aggregation expects the actual five incumbent versus four candidate stages. No new blocking finding.

- Final `window.py` SHA256 `53d66d0ab5486a39bcdc2a799b17216ad8b60b95b00271fd2d3cc105dd9d2893`
- Final `summarize.py` SHA256 `9a26fb3812f656807bd06affa25f7e8f6556a17c295c59fab27444ec5940c038`
- Final `build_gemv.py` SHA256 `18a2d32a6e4956dfbcca3d5b09a836ecc3319d6d863fda5b476574485135c54a`
- Final `test_window.py` SHA256 `ccb4cceb042ecfbcc1e0033b12fc60c0bc542e1ac189bb8f9ead1f53a515be1e`

## Final integration audit

The generated native GEMV source emits `gemv:expsgate` with workloads
`expsgate.iq2` and `expsgate.iq3`, `gemv:expsdown`/`expsdown`, and
`gemv:attention`/`attention.gdn`. These exactly match summary format coverage.
Its variant names are packet18/specialised as expected; the implementation
field correctly identifies the actual p28/p33 runtime incumbent. Each heavy
rotated arm observes all eight banks. Route produces five/four stages;
parallel produces recurrence and diagnostic route_gather under distinct names.
Tiny/extras use the separate normalized summary vocabulary, with 200 host and
GPU values checked before ranking. Native K0 flags in the seal match their
CLI parsers. The seal binds native binaries, fixture and runtime source
inputs, and CPU gate receipts; all current CPU gate receipts pass.

One remaining finding sent to the root author: dispatch family selection
includes untimed diagnostic rows in `all(passed and selected)`. This makes
extras families with a timed full-size fixture and other untimed gated
fixtures impossible to select. Retain every diagnostic gate, but require
speed selection only over a nonempty eligible measured subset. Unsupported
norm aliases and combine-norm dispatch scope are being narrowed by the extras
author; final receipt identities must be resealed after those changes.

- Integration audit `window.py` SHA256 `827dbc75549c95c6fa30828595baf1b96d70efe0f69fb979b189d58a0b689e7f`
- Integration audit `summarize.py` SHA256 `9a26fb3812f656807bd06affa25f7e8f6556a17c295c59fab27444ec5940c038`
- Integration audit `seal.py` SHA256 `9e00fc476ebfb04437af892dd402068f1d2a7ffb797883dbb70c9d073dcf01aa`
- Integration audit `build/gemv/gemv_generated.cpp` SHA256 `71a605df4094e107079a821f9e55dfebfc70198440d9f21e6b47cc6f0c774925`
- Integration audit `tiny_timing.cpp` SHA256 `d2478a5547074472248923ceafeba5bea79cbc2a56e3a2c177f4bab6f0c5ea60`
- Integration audit `extras_timing.cpp` SHA256 `5cfe8635189fed3d71f7b7cbfa2f7a5ed3292e73e110e7a0ccd66040ae9dc0bd`

Resolution: the final summary now requires a nonempty timed subset, complete
registered timed workloads, every family gate passing, and every timed row
selected. Untimed diagnostic rows still gate correctness but no longer block
a measured winner merely by lacking timings. The added regression test covers
this case. Re-read source confirms the finding is fixed. No remaining blocking
integration finding was found. Final norm aliases are source-backed:
packet3/step/plan.hpp hc() uses four norm rows, including its final hc() call;
combined norm is now diagnostic only.

- Resolved `summarize.py` SHA256 `2decf117924e8ef728feca549093534e9285e4c59dd2c24e67daf854e760459c`
- Resolved `seal.py` SHA256 `9e00fc476ebfb04437af892dd402068f1d2a7ffb797883dbb70c9d073dcf01aa`
- Resolved `test_window.py` SHA256 `1d922807dfbf44bc591ef4c2d7137671d3f090e16e29a75a47015de803c401e9`
- Resolved `extras_timing.cpp` SHA256 `5cfe8635189fed3d71f7b7cbfa2f7a5ed3292e73e110e7a0ccd66040ae9dc0bd`

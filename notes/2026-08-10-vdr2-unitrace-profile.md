# VDR2 reordered-Q8 unitrace profile

Date: 2026-08-10

## Classification

The wrapper run is `PROFILER_CONTROLLER_FAILED`, diagnostic-only, and not
performance-promotable.  Its exact model capture and raw filtered unitrace
timing are useful diagnostic evidence, but the run has no official completion
marker or wrapper artifact manifest.

Run:

`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/profile-vdr2-short-20260810T070057.215180477Z`

Trace:

`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/traces/profile-vdr2-short-20260810T070057.215180477Z`

The launch used wrapper commit `214586a6a`, exact wrapper SHA-256
`f7c04239be580f5cd006fde69b0296ef4d7a39c52ce1878c54db86867dcf2969`,
VDR2 manifest `4119790a79c55d158e7257d4fa0d95be0ca34639807c1a71ce87b60d6fdc1b49`,
and unitrace `5aaca1f418a212a1d298cac27afb6c471bf1fcf47a1622e0c20d1a2cf43fc85a`.

## Controller failure and orchestration mistake

The profiler resumed successfully when task 0 logged `n_decoded = 100`.
Under tracing, the next progress values were 149, 198, and so on; the wrapper
incorrectly required an exact 150 marker, so it did not stop at the intended
50-cycle boundary.  Root manually issued unitrace pause and stop after the
second 512-token row, and both controls returned zero.  Unittrace flushed the
raw timing files successfully.

Root then made a process-ownership mistake: it patched the wrapper file while
that Bash process was still running.  Bash read a later chunk from the changed
file and reported a syntax error near the new line 318 after capture.  This is
why the wrapper emitted no final gate or manifest.  Future live scripts must
remain byte-frozen until their owning process exits.  The follow-up source fix
uses a relative 45--55 decoded-cycle window instead of an exact log value, but
this failed run is not retroactively promoted.

The unitrace-injected server also ended with `terminate called without an
active exception` during teardown.  The model capture had already completed
exactly, and subsequent process, listener, and XPU checks were clean.  Treat
the teardown as a profiler lifecycle failure, not model/runtime correctness
evidence.

## Exact capture

`exact-tokens.json` SHA-256:
`809d07b37c15e8036b40d894b9aa45af8e4ff2110eeef43129f1bdda8ed0ed38`.

- intrinsic gate: PASS;
- oracle status: `PASS_ORACLE_EXACT` for both rows;
- both rows: 512 tokens, cache 0, limit stop, not truncated;
- post-512 canary: PASS;
- diagnostic D100: 16.374609 tok/s;
- diagnostic D511: 16.204701 tok/s.

Those rates include profiler overhead and are not benchmark results.

## Filtered kernel result

The corrected diagnostic summary SHA-256 is
`af33063d1e3d16c2634c2bab0b3f3f4638179028719e8ba52b0b783a9d734ae9`.
Raw `device_timing.txt` SHA-256 is
`964510de0867d22345167da9c6d8876d4bc4a75435da753b8c062eb91c57c806`;
raw `device_submission.txt` SHA-256 is
`eaf06859fd64f2cea85af25cd66905431d5b054ca0f1a9504464d12d6100f43d`.

The trace contains 921 complete decode graph cycles plus one boundary output
invocation.  The complete-cycle count is exact from the repeated shape counts:
117,888/128, 44,208/48, 14,736/16, 88,416/96, and 29,472/32 are all 921.
The 15,520 group-X output shape has 922 calls and accounts for the one boundary
invocation.

Exact selected-kernel device time is 46,593,445,008 ns, or 50.590060 ms per
complete cycle.  Against the sealed unprofiled VDR2 D511 baseline of
60.281 ms/token, the selected reordered-Q8 MMVQ consumes approximately
83.9237% of token time.  Unittrace was configured with an include filter, so
46,593,445,008 / 46,805,277,875 = 99.5474% describes only the filtered trace;
it is not an application-wide hotspot share.

All eight observed variants used SIMD16 and workgroup 256, with zero private
spill bytes.  Largest shares of selected-kernel time were:

- group X 1088: 41.6177%, average 165.235 us;
- group X 320: 29.3911%, average 116.692 us, range 61.354--215.000 us;
- group X 640: 9.4565%, average 100.120 us;
- group X 384: 8.0850%, average 85.600 us;
- group X 15520: 4.4474%, average 2.257705 ms;
- group X 768: 3.7295%, average 118.458 us.

## Decision

The >=70% preregistered hotspot gate is decisively met and spills are zero.
Advance one default-off, VDR2-preserving structural MMVQ experiment driven by
the measured shapes.  Do not rerun this profile merely to repair its wrapper
seal: the retained 921-cycle trace is already more precise than the intended
50-cycle diagnostic.  Validate any source delta with an exact four-card
balanced crossover before official isolated confirmation.

Post-run checks found all four cards at 43 MiB, no port 19940 listener, and no
remaining llama-server, capture, or unitrace process.  No reboot or driver
restart was used or indicated.

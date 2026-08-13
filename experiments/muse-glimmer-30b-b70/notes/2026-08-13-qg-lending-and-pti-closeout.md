# Q/gate lending and PTI scheduler measurement closeout

Date: 2026-08-13

## Decision (superseded for Q/gate lending)

Do not integrate TP4 Q/gate projection lending.  It is bit-exact in the
standalone two-device chain and saves `1.920 ms` when its measured per-layer
delta is scaled over 52 layers, but it misses the preregistered materiality
gate and cannot close the current century gap.

Also close PTI device-view tracing on the current Level Zero V2 runtime.  PTI
cannot timestamp the runtime's model-loading events reliably and remains
active before the deferred decode interposer.  The failed captures contain no
device records and do not establish an idle-pool size.

## Q/gate screen

The benchmark used two physical B70s and the exact Muse TP attention-owner
shape `M=2048, N=16, K=6656`.  The control submitted two full-width oneDNN
BF16/F32 GEMMs serially on the owner.  The candidate submitted the two
`M=1024` halves on owner and helper queues, scattered the helper Q/gate halves
back to the owner, and appended the reciprocal helper-queue handback required
for safe reuse.

Results over 800 iterations after warmup:

- control before/after `0.102798 / 0.098942 ms`, pooled `0.100870 ms`;
- candidate `0.063938 ms`;
- saving `0.036932 ms/layer`, candidate/control `0.633863x`;
- Q mismatches `0`, gate mismatches `0`;
- Q hash `1c46604f7f7c9738`, gate hash `38bf0bbbb8f12687` on both paths;
- exact gate PASS, `0.040 ms/layer` speed gate FAIL.

The measured best-case pass saving is `0.036932 * 52 = 1.920464 ms`.  Even
deleting all approximately `5 ms` of attention would project only about
`89.49 tok/s` from the current acceptance mix; the actual current mix needs
approximately `9.94 ms/round` saved to average 100.  A full implementation
would additionally need about 676 MiB/device of duplicated row-half weights
and new asymmetric meta/model scheduling.  That work is not justified by a
failed isolated gate.

## PTI attempt

The `intel-pti-dev-1.0` development package (`1.0.1-21`, 191 KiB installed)
was added locally; the PTI runtime was already installed.  A preload collector
was built to record kernel/copy/P2P/fill/barrier start and end timestamps.  It
was then narrowed to activate only around an interposed `llama_decode`.

Both forms were unusable.  PTI repeatedly reported
`zeEventQueryKernelTimestamp returned: 1 ... command type: 2`, wrote no view
records, and consumed a CPU core while polling/flushing.  The eager run and
deferred attempts were terminated with SIGTERM after bounded diagnostics.
One separate loader attempt with `LD_BIND_NOW=1` failed before collector/model
initialization because Intel `libimf` cannot be eagerly resolved against the
system `libm`; it performed no GPU work.

The adjacent untraced seven-repeat width-16 result has one cold sample at
`175.646 ms` and six stable samples from `42.331` to `42.529 ms`; the warm
mean is approximately `42.418 ms`.  This corroborates prior target-width
timing but does not expose internal idle gaps.

## Additional lossless-bandwidth screen

Independent 16 MiB samples from the embedding and six large BF16 projection
tensors compressed with zstd level 3 to only `1.2764--1.2775x`
(`12.524--12.535` effective bits/BF16).  Even an ideal general compressor
therefore exposes only about 22% raw-byte reduction on these samples, before
on-device decompression and random tensor access.  It is not a credible
lossless route to the roughly 19% whole-round reduction needed for 100.

## Evidence and operations

- Q/gate raw log SHA-256:
  `2d7a7b521a091a1b7dbaae70f943a97038123ae7e232750c67b786186914df4b`;
- PTI artifacts:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/pti-width16/`;
- valid untraced result:
  `target-width16-untraced-20260813.json`;
- final fleet gate:
  `data/muse-health-20260813-qg-pti-final-restore.json` (`ok=true`, models,
  cache-zero code, and vision all pass).

Production was restored after every window.  No reboot, driver reset, or GPU
recovery was required.

## Reopened by carried-event lifetime handback

The Q/gate decision above was superseded later the same day.  Replacing the
standalone reciprocal helper barrier with the owner scatter event carried as a
dependency on the next helper Q GEMM preserved the lifetime proof while
removing one command.  Over 1,200 iterations the exact candidate improved from
`0.063938` to `0.055408 ms/layer`; the matched full-width control measured
`0.100493 ms/layer`.  The resulting `0.045085 ms/layer` saving clears the
preregistered `0.040 ms/layer` integration gate and scales to a
`2.34442 ms/pass` isolated ceiling.

All Q and gate F32 bits remained exact.  Raw evidence:
`/mnt/fast-ai/bench-results/muse-glimmer-30b/qg-projection-lending/qg-projection-lending-carried-event-20260813.log`,
SHA-256 `72b4c5e11991999bb8ef73a4da839ae688e679c53564985600773f50a32af14a`.
The lane is therefore reopened only for a strict default-off full-model
integration and exact smoke.  The ceiling projects the current fixed-suite
mean from `80.879` to approximately `84.699 tok/s`; it is a supporting kernel
win, not a century result.

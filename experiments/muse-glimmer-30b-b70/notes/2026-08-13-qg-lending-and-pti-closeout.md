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

## Full-model integration result: closed

The strict default-off full-model implementation was compiled and independently
reviewed.  It duplicated only the second 1,024 Q/gate rows on helper devices,
kept the logical TP split and K/V/cache/FA/O/allreduce paths unchanged, and
required `GGML_MUSE_TP4_QG_LEND=1`.  The source delta touched only:

- `src/models/muse-glimmer.cpp`;
- `ggml/src/ggml-backend-meta.cpp`;
- `ggml/src/ggml-sycl/ggml-sycl.cpp`.

The initial implementation diff SHA-256 was
`f8419fb53c65fa0c33fa45d9eefca47b38f9441fbc3bd7162c9eb159e9a383f6`.
It compiled successfully in the authoritative BMG-G31 build.  The 64-token
leading control completed with canonical hashes and proposal identity:

- prose `67.977 tok/s`, hash `f45a2f2c58f1ca34`, drafted/accepted `155/48`;
- code `114.096 tok/s`, hash `2ca4135046a15a71`, drafted/accepted `126/53`;
- JSON `219.110 tok/s`, hash `32dc3aebb11684a4`, drafted/accepted `65/58`.

The candidate emitted both layer-0 execution markers (`owner=1 helper=0` and
`owner=3 helper=2`) but then made no progress for more than three minutes on
the first verifier pass.  This proves the path was reached rather than silently
falling back.  It was cancelled gracefully and produced no benchmark row.
The final cancelled log is:

`/mnt/fast-ai/bench-results/muse-glimmer-30b/servers/sweep-qg-lending-integration-smoke-cac-20260813-qg-lend-on.log`

SHA-256 `574db48e932461425b553bdfdda9d3623f6fc1ff70972da4171456c23312cff5`.

A bounded follow-up replaced both cross-device event dependencies with host
completion waits while retaining identical GEMMs, scatter arithmetic, and
buffer lifetimes.  Its source diff SHA-256 was
`29e6a65e8db6513e66e94d525558a9c7068180e34285e3b8ee7e735d3af31c2b`.
It again emitted both layer-0 markers and stalled at the same point.  Final log:

`/mnt/fast-ai/bench-results/muse-glimmer-30b/servers/sweep-qg-lending-hostwait-smoke-20260813-qg-lend-hostwait-on.log`

SHA-256 `52efdd8faf702643cb60e71236c0e9f964a67477d5ad5b770e4f87370ac29abf`.

One last candidate-only screen additionally disabled
`GGML_SYCL_COMM_LAST_EVENT_READY`.  It produced the same two layer-0 hit
markers and the same no-progress failure, ruling out the retained allreduce
readiness shortcut as the simple interaction.  Final log:

`/mnt/fast-ai/bench-results/muse-glimmer-30b/servers/sweep-qg-lending-hostwait-barrier-smoke-20260813-qg-lend-hostwait-barrier-on.log`

SHA-256 `eb7c193031ac4cf59d7f7ac1ee73f2c93a26775d80febf4135967b20c665a655`.

Decision: close the full-model Q/gate lending topology on the current runtime.
The standalone microbenchmark remains useful descriptor evidence, but its
`2.34442 ms/pass` scaling is not realizable evidence.  Do not spend another GPU
window on this implementation without a materially different scheduling
design that avoids submitting the helper's whole attention subgraph ahead of
the owner.

Production was restored after every window.  The final health artifact is
`data/muse-health-20260813T164324Z-qg-lending-closed-restore.json`; models,
cache-zero 512-token code, and vision all passed.  No reboot, driver reset, or
device recovery was needed.

### Owner-BF16 v2 also fails

A materially different v2 removed the helper-first schedule.  Owners were
submitted first; each owner converted its canonical normalized activation to
BF16, host-waited conversion readiness, PULL-copied exactly 212,992 BF16 bytes
to persistent helper-local memory, host-waited the helper Q/gate GEMMs, and
then enqueued the canonical owner scatter.  Helper ordinary graphs were
submitted only after the owner phase.  This removed every device-side
cross-device event and the obsolete helper-activation arena-survival guard.
Two independent source reviews found the resulting event/lifetime DAG sound.

The v2 binary compiled successfully and again emitted both layer-0 execution
markers.  It nevertheless made no progress after layer 0 and produced no
benchmark row.  This falsifies both cross-device-event progress and
helper-first scheduling as the sole causes.  The stronger conclusion is that
holding back any rank's ordinary attention graph is incompatible with the
owner remainder on this meta/SYCL topology.

Preserved source:
`patches/muse-qg-lending-owner-bf16-v2-deadlock-20260813.patch`, SHA-256
`35f89b80ab6cbe0b5818a61b8220e7588c816adb5f17690ba6d9d019731de31b`.
Final log:
`/mnt/fast-ai/bench-results/muse-glimmer-30b/servers/sweep-qg-lending-owner-bf16-v2-smoke-20260813-qg-lend-owner-bf16-v2-on.log`,
SHA-256 `8f0580438be8519acb7d01165bb169aeadfb95224f9fab53d2316917f2ab09f2`.

Production again restored cleanly.  The final v2 health artifact is
`data/muse-health-20260813T165830Z-qg-lending-v2-closed-restore.json` and passes
models, cache-zero 512-token code, and vision.  Do not retry another rank-phase
ordering variant.  Any further proof must submit all four ordinary rank graphs
together and isolate custom helper work on separate queues.

### All-rank side-queue v3 is exact but slower

The final materially different v3 retained concurrent submission of all four
ordinary rank graphs and moved helper Q/gate work onto dedicated in-order SYCL
queues with private oneDNN engine, stream, primitive, scratch, and output
state.  Host completion waits replaced cross-device event dependencies.
Separate owner/helper activation buffers closed the rotating-role overwrite
hazard, and direct device allocations avoided the strict-LIFO VMM pool.  Two
independent reviews found no remaining deadlock, ordering, arena-lifetime, or
teardown blocker before the bounded smoke.

The candidate completed the three canonical 64-token prompts and preserved
every output hash and proposal/acceptance count:

- prose `66.913 tok/s`, hash `f45a2f2c58f1ca34`, drafted/accepted `155/48`;
- code `112.039 tok/s`, hash `2ca4135046a15a71`, drafted/accepted `126/53`;
- JSON `217.520 tok/s`, hash `32dc3aebb11684a4`, drafted/accepted `65/58`.

The matching leading control was `67.977 / 114.096 / 219.110 tok/s`, so v3
regressed every class by roughly `1.5%`.  It is correct and reachable, but the
P2P copy, host waits, extra conversion, and side-queue work cost more than the
isolated half-projection saving.  Do not run a full 256-token C/A/C or another
Q/gate lending variant.

Evidence:

- result JSONL:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/qg-lending-sidequeue-v3-smoke-20260813.jsonl`;
- server log:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/servers/sweep-qg-lending-sidequeue-v3-smoke-20260813-qg-lend-sidequeue-v3-on.log`,
  SHA-256 `3c2deaceef19e35c77cf10d984e5dbb493dc1019e5056e5b6a70846ced23ecd8`;
- preserved source:
  `patches/muse-qg-lending-sidequeue-v3-negative-20260813.patch`, SHA-256
  `4855f83dd2c63c6977079933c32f4d54f18864503c89bb9da275be80e7b7846b`;
- restored production health:
  `data/muse-health-20260813T1720Z-qg-lending-v3-negative-restore.json`,
  SHA-256 `da6d58c72333cd047b9c063e61ff2b5fc521baa77d228fde870b2fd4168dfeb5`.

Production passed model listing, cache-zero 512-token code, and vision.  No
reboot, driver reset, or device recovery was needed.  Q/gate lending is closed
as an exact performance negative.

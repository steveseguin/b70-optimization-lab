# Laguna public-oneCCL DFlash collective-graph screen

Date: 2026-07-31 America/Toronto

Status: **preregistered before device execution; component only.**

## Why this is a new experiment

The exact BF16-KV record is `125.4619731637751 tok/s` conventionally.  Its
aggregate suite accounting gives about `32.326922 ms` per verifier cycle, so
130 tok/s at unchanged acceptance requires `1.128465 ms/cycle` of real
savings.

The segmented DFlash drafter still crosses thirteen eager TP4 BF16
`[12,3072]` all-reduces per cycle (embedding plus two per decoder layer).  A
current-source direct component measured twelve of those reductions at
`1.239689 ms`; the thirteenth and the thirteen Python/graph boundaries make
the complete scope plausibly large enough to matter.

The 2026-07-24 Laguna direct-capture negative used the then-installed oneCCL
and failed changing-input replay.  It remains closed and will not be rerun.
This screen instead uses the independently checksum-validated public oneCCL
build which later passed Qwen changing-input graph oracles `512/512` and
enabled a controlled `+5.39%` draft-graph gain.  Its identities are:

- oneCCL parent `b52f40c07f0b140e6aba87548c80720a350a9827`;
- libccl source `4ceafd15c03ce46f11eeaf91781a92afebd3cecf`;
- `libccl.so.1.0` SHA-256
  `43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700`;
- `kernels.spv` SHA-256
  `0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9`.

The archived bytes were mounted read-only and copied to internal ext4 at
`/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public`.  Laguna model, cache, build,
and evidence I/O remain on internal ext4.

## Frozen component

Use TP4/XCCL on all four B70s and thirteen fixed-address BF16 tensors of shape
`[12,3072]`.  Each stage records a small changing producer, an all-reduce, and
a consumer.  Change every producer input before every replay and compare every
raw BF16 output element with an exactly representable rank-sum oracle.

Run three fresh-process arms:

1. installed record runtime, eager/direct transaction (control);
2. checksum-gated public runtime, eager/direct transaction (runtime control);
3. the same public runtime, one XPU graph containing all thirteen transactions
   (candidate).

The public library must be loaded with `LD_PRELOAD`; `LD_LIBRARY_PATH` alone
does not override PyTorch's runtime binding.  Every result records the actual
`/proc/self/maps` libccl path.

## Gates and stop rules

1. Require clean pre-idle and no service/benchmark process or occupied public
   benchmark port.
2. Require the direct controls and public graph candidate to pass changing
   inputs on every rank.  The graph candidate requires at least `512/512`
   exact replays per rank.
3. Require clean four-rank teardown.  A timeout, mismatch, device error,
   stranded process, or failed idle check closes the screen.  No reset, driver
   reload, FLR, reboot, repeated probe, or recovery ladder is authorized.
4. Compare the complete thirteen-stage public graph transaction with the
   installed-runtime eager control using batched timing and the slowest rank.
   Require at least `1.4 ms/cycle` median net saving.  This deliberately covers
   the `1.128465 ms` endpoint need plus integration uncertainty.
5. A component pass authorizes only offline integration of the public runtime
   and an opaque fixed-address collective transaction into the already-exact
   segmented DFlash path.  It does not authorize a score.
6. Integration must retain the current target and draft checkpoints, INT4
   weights, BF16 KV, width 12 / depth 11, greedy target verification, one
   active generation, fixed cold suite, canonical q1 teacher, cache-zero rule,
   target `146/145`, first-valid-score rule, and clean pre/post idle gates.
   Before any endpoint, changing DFlash attention/context/proposal inputs must
   prove changing proposal IDs and non-flat acceptance through the complete
   captured transaction.

No target/draft/KV precision, prompt, metric, sampling, teacher, quality,
cache, retry, warmup-generation, or scoring-window change is allowed.


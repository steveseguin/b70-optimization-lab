# Qwen3.8 Q64K32 remote runtime-map r2 invalid result

Date: 2026-08-21

Status: **procedurally invalid cross-host CPU-oracle byte-pin false-fail; r2 is
terminal and must not be retried or repaired in place**. The structured summary
is
[`../data/2026-08-21-qwen38-q64k32-remote-runtime-map-r2-invalid.json`](../data/2026-08-21-qwen38-q64k32-remote-runtime-map-r2-invalid.json),
and the controlling registration is
[`2026-08-21-qwen38-q64k32-remote-runtime-map-diagnostic-prereg.md`](2026-08-21-qwen38-q64k32-remote-runtime-map-diagnostic-prereg.md).

## What ran

The reference host was clean on `main == origin/main` at
`f32d8af4c297d0fd33338706e845bd1dd2b4194f`. The frozen preflight passed and
the driver was invoked exactly once against the fresh root:

```text
/home/steve/qwen38-q64k32-remote-runtime-map-diagnostic-20260821-r2
```

Only the first GPU-0 control worker ran. It returned zero and atomically wrote
a `passed=true` arm packet, but the supervisor's independent validator rejected
that packet and published an invalid terminal. The driver returned `1`; it did
not start arms 2--4 or comparison. Cleanup validation passed and certified the
worker group absent without TERM or KILL.

The remote root has exactly nine max-depth-one regular files, all mode `0444`.
The structured summary records each basename, size, and full SHA-256. The
aggregate
`d88c90a1d6a1f252afec4bd50d9e1c88b4e7a5e6a0dcdc77fb583ce035af9632`
was produced from the lexically basename-sorted standard `sha256sum` lines by:

```text
find . -maxdepth 1 -type f -printf '%f\0' |
  LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum
```

The raw files remain remote-only and were not copied into Git.

## Exact false-fail boundary

The fixed KV128 fixture hash was
`0acb368f76405cfab88e47944437d0399bce0866fe9452096d3d5e0a2c9570cd`.
The XPU output hash was
`c3e022a5e724574d06e2388e33e2e29c4b1f8630f2b7eb236ffc5e349fe9c403`,
exactly the prior local control output. It passed the independent numerical
oracle at `max_abs_diff=0.00048828125` under `atol=0.02, rtol=0.01`.

Only the CPU oracle bytes differed. R2 computed
`eb71753ec76de2390e25f5bebacecf54cb63f7966311cdd6548a5ed03638364a`;
the source incorrectly required the local measuring-host digest
`5a9759d1bf2b3eeea8eb4b34ba40e259d7e356285b28f0edcd36bda4a92e2a2e`
inside every arm. The exact error was:

```text
ContractError: arm 1: correctness summary differs
```

The fixture and output equality plus the numerical pass isolate this to the
CPU reference's exact FP reduction/softmax byte representation, not the XPU
operator output. The same Torch version and selected Torch file hashes do not
make host-dispatched CPU floating-point reductions bitwise portable. The
measuring host reproduced its local oracle digest with CPU thread counts 1, 2,
4, 8, and 16, so local thread-count selection did not explain the difference.
The evidence does not identify a narrower CPU instruction or library dispatch
choice, so this packet does not claim one.

## Report-only runtime-map observation

R2 captured the same eight full rows before and after the first operator
return. Each row binds raw mapped pathname/basename/device/inode to canonical
pathname/basename/SHA/device/inode. The compact canonical
`{basename,path,sha256}` projection has SHA-256
`ba940a22a21a030be60ae54a33cac4f31560e4745565b2dd51e91203a16bffd3`,
using this exact byte recipe, including `jq`'s trailing newline:

```text
jq -cS '[.runtime_maps_after_first_return_before_correctness.libraries[] |
  {basename,path,sha256}]' arm-01.json | sha256sum
```

The observed rows are `libsycl.so.8`, the Level Zero, Level Zero v2, and OpenCL
UR adapters, `libur_loader.so.0`, the Intel Level Zero driver, Level Zero
loader, and tracing layer. Only the Intel driver and Level Zero loader were
exact canonical path/SHA matches to the prior passive five-library intent.
Three intended venv libraries had the same content hashes under unversioned
canonical basenames; three additional relevant libraries were present. The
structured summary records all eight exact rows and the comparison.

This is valid single-arm report evidence, not a completed diagnostic result:
there is no cross-process, cross-role, or cross-device comparison. Device and
inode values are same-boot observations, not portable path identities.

## Source-only r3 contract

R3 uses a fresh root and leaves r1/r2 immutable:

```text
/home/steve/qwen38-q64k32-remote-runtime-map-diagnostic-20260821-r3
```

It retains the exact fixture, production call/output-pointer semantics,
finite output, numerical oracle, `max_abs_diff <= 0.02`, and role marker gates.
It no longer requires a measuring-host CPU-oracle byte digest per arm. Instead,
comparison requires all four same-host fresh processes to produce one exact
oracle digest and one exact output digest. It reports whether each common value
equals the r2 observation; those cross-run comparisons are evidence, not
per-arm correctness gates.

R3 freezes the eight r2-observed portable raw/canonical basename/path/SHA rows.
Every arm still rederives live mapping and canonical `stat` device/inode, must
have identical before/after full rows, and comparison requires the full rows to
be identical across all four same-boot workers. The separate passive
five-library intent remains in the result rather than being relabeled as the
observed runtime inventory.

R2 is terminal. R3 remains source-only until its exact bytes, tests, and
chronological preregistration update pass independent review, are committed and
pushed, and the remote host is separately advanced and authorized. Neither r2
nor r3 authorizes the 16-arm clock campaign.

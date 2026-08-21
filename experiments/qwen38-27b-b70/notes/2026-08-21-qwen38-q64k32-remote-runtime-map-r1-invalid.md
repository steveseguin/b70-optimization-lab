# Qwen3.8 Q64K32 remote runtime-map r1 invalid result

Date: 2026-08-21

Status: **procedurally invalid harness false-fail; r1 is terminal and must not
be retried or repaired in place**. The structured summary is
[`../data/2026-08-21-qwen38-q64k32-remote-runtime-map-r1-invalid.json`](../data/2026-08-21-qwen38-q64k32-remote-runtime-map-r1-invalid.json),
and the controlling registration is
[`2026-08-21-qwen38-q64k32-remote-runtime-map-diagnostic-prereg.md`](2026-08-21-qwen38-q64k32-remote-runtime-map-diagnostic-prereg.md).

## What ran

The reference host was clean on `main == origin/main` at
`048b899069b223b8b13faf2a3706049ad8790f74`. The frozen preflight passed, then
the driver was invoked exactly once against the fresh root:

```text
/home/steve/qwen38-q64k32-remote-runtime-map-diagnostic-20260821-r1
```

Only the first GPU-0 control process started. It exited `2`, the supervisor
published an invalid terminal, and the enclosing driver returned `125`. No
second through fourth arm or comparison ran. The remote root retains exactly
seven max-depth-one regular files; the structured summary records every
pathname and SHA-256. Their sorted `sha256sum`-line aggregate is
`2eb9a8327ee53a5f7798caf5425643b441147bc6468e238ee3a8eedee1247bcc`.
The raw files remain remote-only and were not copied into Git, so this note
does not invent unrecorded modes, sizes, receipt timestamps, or nested fields.

## Exact false-fails

The worker log contains:

```text
error: runtime mapping is not a file: /dev/dri/renderD129
```

At r1 source SHA
`19f938ac71780648cbbce91129876025c4eb0e8646dd213209b1052bd18268e2`,
the map parser resolved and required every absolute `/proc/self/maps` pathname
to be a regular file before selecting `libsycl`, `libur_`, and `libze_`
basenames. The render node is an irrelevant absolute device mapping. This
failure occurred in the pre-call map snapshot, before the target operator was
invoked.

The terminal then reported `identity_safe=true`, `group_absent=true`, and no
TERM or KILL. The driver nevertheless rejected cleanup with:

```text
error: live scan: clock unit differs: xe-b70-minfreq.timer
FATAL: supervisor terminal does not prove owned worker-group absence (rc=1)
```

The producer accepted omitted `MainPID` as zero for the absent timer but
retained the missing field, while the validator required the canonical
`"MainPID":"0"` entry. Therefore group absence is terminal-reported evidence,
not validator-certified cleanup evidence. The post-run relevant process scan
was empty.

## Scientific boundary

R1 says nothing about stock or Q64K32 operator correctness, engagement,
runtime-library inventory, or performance. It stopped before the first
operator call and produced no arm packet. This is not a runtime-map mismatch
and cannot support or reject the later clock campaign. No retry, result-root
repair, clock mutation, sudo action, build, model launch, or further GPU action
occurred.

## Source-only r2 correction

R2 uses the new fresh root:

```text
/home/steve/qwen38-q64k32-remote-runtime-map-diagnostic-20260821-r2
```

Its parser filters irrelevant absolute mappings by their raw mapped basename
before filesystem validation, then keeps all canonical path, regular-file,
device/inode, and SHA gates for relevant runtime libraries. A not-found unit
with an omitted `MainPID` is canonicalized to `"0"`; the downstream validator
remains strict. Literal `/dev/dri/renderD129`, missing relevant-library, and
absent-timer fixtures cover these boundaries.

The corrected source-only identities are:

- diagnostic:
  `a78a2c1953952578ed7b63f0ec6d96f5c423e5199ad034c69cb002fe4a0191db`;
- driver:
  `f35c7dd564c0e8279c706e6003fcba44bdae4922bcb94eec72b6b8a65c410c1e`;
- CPU tests:
  `40a3cf207e3de994d8fbe614231fdf55fc4bc492826e8fc449850655add50b71`.

At the time this r1 packet was written, r2 was unrun and unauthorized pending
independent review, commit/push, clean remote advancement, and a separate
launch decision. It subsequently ran once and closed as a distinct
[`cross-host CPU-oracle byte-pin false-fail`](2026-08-21-qwen38-q64k32-remote-runtime-map-r2-invalid.md).
Neither result authorizes the clock campaign.

# Qwen3.8 Q64K32 reference-host passive inventory

Date: 2026-08-21

Status: **passive inventory complete; transfer, staging, clock changes, GPU work,
and launch remain unauthorized**.

The strict structured record is
[2026-08-21-qwen38-q64k32-remote-passive-inventory.json](../data/2026-08-21-qwen38-q64k32-remote-passive-inventory.json).
This inventory supplies evidence for, but does not amend or authorize, the
[remote clock preregistration](2026-08-21-qwen38-mtp5-m6-fa-q64k32-remote-clock-prereg.md).

## Evidence boundary

At `2026-08-21T05:32:14-04:00`, a read-only SSH session queried the existing
reference host at `10.0.0.108`. Evidence was returned only through command
stdout/stderr. No raw telemetry file was persisted remotely or locally. The
audit did not fetch or update Git, use sudo, change an XPU setting, transfer a
file, launch GPU compute, or start a model/operator workload. It finished with
the remote repository still clean.

The queries were limited to host/kernel identity, read-only `xpu-smi`
discovery/config/version calls, file/package hashes and versions, systemd and
clock-writer inspection, selected environment names, Git read operations, and
Python package metadata without importing torch. No credential value is
recorded.

## Current-boot identity

The locator resolves to `steve-TURIND8-2L2T`. The machine-ID was not recorded;
its SHA-256 is
`3942576cd46d01417795ef1ef737db2599485bd4158cc5119f6cde9b57e5f1a7`.
The boot ID is `a6cad22f-2685-43b7-8950-c0c771f73d99`.

The host runs kernel `7.0.0-28-generic`. Both sysfs and `modinfo` report xe
srcversion `85B7CA089405934276CBAD3`. The xe module file is SHA-256
`8fa065989f7d6c4c8d06f12fb9c52c3bab4c5a966c3abd1cc55bf5423c3c60a1`.

Exactly two devices were returned, both named `Intel(R) Arc(TM) Pro B70
Graphics` and both in `normal` state:

- device 0: UUID `00000000-0000-0003-0000-0000e2238086`, BDF
  `0000:03:00.0`, `/dev/dri/card2`, tile `0/0`, range 400--2800 MHz;
- device 1: UUID `00000000-0000-00e3-0000-0000e2238086`, BDF
  `0000:e3:00.0`, `/dev/dri/card0`, tile `1/0`, range 400--2800 MHz.

These ordinal mappings and ranges are current-boot evidence. They must be
recaptured and compared before any later launch.

## Telemetry and runtime identity

`/usr/bin/xpu-smi` is canonical and has SHA-256
`01c7b83881e99754642b827ba05418d263aed615933e3df35821af7733eb8d83`.
Its CLI and service are version `2.0.0.20250225`, build `8389eee7`; its reported
Level Zero version is `1.28.6`.

The discovery raw stdout SHA is
`c67bf2f7a2592c8a6a4a1247ce6f50a26405f908802285f8fd466c15f1364742`.
The GPU0 and GPU1 config raw stdout SHAs are respectively
`a65915cfcc76ea2357e0689caa6fdee037fa3acf18ecef6c75d029cd6c86aa15`
and `a2cb4837baf5e6f3654435ead2cc4393466cfdde8909d294a522a2074cf0d8e7`.
Both produce the exact combined-envelope structural SHA
`afb4b7fe6d1ea9847559734fae1b73241f18587f036ae3d18376c146fa6eafba`.
The JSON records the complete strict shapes and field paths.

The venv identifies Python 3.12.3, torch `2.11.0+xpu`, vLLM
`0.21.1rc1.dev289+g44fc8fde0.xpu`, and vLLM XPU kernels `0.1.8`. Under the
planned library ordering, `libtorch_xpu.so` resolves the venv's SYCL 2025.3.2
and Unified Runtime 2025.3.2 libraries. The JSON records the exact Torch,
SYCL, UR, Level Zero loader, and Intel GPU driver paths and hashes.

The session reported the passive five-file runtime candidate aggregate
`d2c3065435d60cc43d31a096406c98e8e5d725637ade11b70a67af2700b292d1`,
but its canonical byte recipe was not retained and cannot be rederived from the
five structured rows. It is therefore opaque session evidence, not a
reproducible inventory hash or authorization input. The separately recorded
`xpu-smi` dependency aggregate is reproducible: it hashes UTF-8 compact
sorted-key JSON of the 14 rows projected to exactly `soname`, `path`,
`resolved_path`, and `sha256`, in recorded order and without a trailing
newline. Neither passive inventory substitutes for the required
`/proc/self/maps` proof from an actual sealed worker, so
`AUTHORIZED_SYSTEM_RUNTIME_LIBRARIES` remains blocked.

## Clock-writer boundary

`xe-b70-minfreq.service` and `xe-b70-minfreq.timer` are not installed: both
reported `LoadState=not-found`, inactive/dead, with no fragment or drop-in.
No matching frequency writer was found in the inspected system/user systemd,
cron, timer, or `~/bin` scopes. The existing `qwen36-q8-b70.service` is disabled
and inactive; neither it nor its launcher contains an XPU frequency mutation.
All caller-environment variables named by the preregistration's clean-env
blocker were unset during this session.

Those are point-in-time observations, not durable exclusion. Service/timer
state, clock-writer absence, effective ranges, and the clean caller environment
remain launch-time evidence requirements.

## Repository and stage boundary

The remote repository `/home/steve/b70-optimization-lab` is clean on `main` at
`6d678cccf9519414f6f3a8162f2c3f263364f842`; its local `origin/main` tracking
ref is the same stale commit. A read-only `git ls-remote` reports server
`origin/main` at `ed7c95b40f0b3c8f77977e35eed122178f7e9482`.

No fetch or pull was performed. The `ed7c95b40` object and its five design
paths are absent from the remote worktree. The incoming transfer root,
candidate stage, control stage, and result root are also all absent. Therefore
neither the remote HEAD nor any stage hash can be authorized from this audit.

## Freeze boundary and verdict

The following values now have exact evidence suitable for a later reviewed
source update: hostname; canonical `xpu-smi` path, SHA, and version text; the
combined telemetry schema SHA and field paths; the current-boot UUID/BDF
mapping; and the same-boot kernel/xe identity.

The boot ID, ordinal mapping, device state, frequency ranges, service/timer
state, clock-writer scan, and caller environment are dynamic and must be
revalidated. The repository must first be updated through a separately
authorized workflow, both exact stages must be created and sealed, and mapped
runtime evidence must come from the final worker environment.

Verdict: **NOGO for transfer, staging, clock mutation, GPU work, or launch**.

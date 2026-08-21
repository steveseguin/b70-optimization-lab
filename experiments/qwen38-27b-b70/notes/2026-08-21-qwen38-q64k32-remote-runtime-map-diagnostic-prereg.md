# Qwen3.8 Q64K32 reference-host runtime-map diagnostic

Date: 2026-08-21

Status: **complete: r1 and r2 invalid and terminal; r3 ran once and closed as
a valid positive
[`valid-no-clock-runtime-map-match`](2026-08-21-qwen38-q64k32-remote-runtime-map-r3-result.md)**.
R1 stopped before its first operator call on two harness false-fails documented in
[`2026-08-21-qwen38-q64k32-remote-runtime-map-r1-invalid.md`](2026-08-21-qwen38-q64k32-remote-runtime-map-r1-invalid.md).
R2 reached and passed the first control call but was rejected by a nonportable
cross-host CPU-oracle byte pin, as documented in
[`2026-08-21-qwen38-q64k32-remote-runtime-map-r2-invalid.md`](2026-08-21-qwen38-q64k32-remote-runtime-map-r2-invalid.md).
R3 preserves the corrected scientific contract below under a fresh result root. This
diagnostic is separate
from, and cannot authorize, the blocked 16-arm clock campaign in
[`2026-08-21-qwen38-mtp5-m6-fa-q64k32-remote-clock-prereg.md`](2026-08-21-qwen38-mtp5-m6-fa-q64k32-remote-clock-prereg.md).
The passive input evidence is
[`../data/2026-08-21-qwen38-q64k32-remote-passive-enablement.json`](../data/2026-08-21-qwen38-q64k32-remote-passive-enablement.json).

## Bounded question

Which exact SYCL, Unified Runtime, Level Zero loader, and Intel Level Zero
driver paths/basenames are mapped by a fresh production-stage Q64 operator
worker? Static ELF and embedded-loader evidence derives this intended chain:

```text
_vllm_fa2_C -> libsycl.so.8 -> libur_loader.so.0
libur_loader.so.0 -> libur_adapter_level_zero.so.0
libur_adapter_level_zero.so.0 -> libze_loader.so.1
libze_loader.so.1 -> libze_intel_gpu.so.1
```

The last three edges are runtime `dlopen` behavior, not transitive ELF
`NEEDED` entries. Their actual `/proc/self/maps` basenames cannot be promoted
from file inventory alone.

## Frozen scope

The diagnostic uses four fresh processes in this exact order:

| Ordinal | Physical GPU | Stage role |
|---:|---:|---|
| 1 | 0 | control |
| 2 | 0 | candidate |
| 3 | 1 | candidate |
| 4 | 1 | control |

Each worker is affinity-scoped to one B70 and performs exactly one eager
M6/head256/KV128 production-shape operator call. It records relevant
`/proc/self/maps` entries immediately before that first call and again after
the synchronized return but before CPU-oracle correctness is evaluated. The
record binds the raw mapped pathname/basename and the mapping's device/inode to
the canonical target pathname/basename, SHA-256, and live `stat` device/inode;
a pathname replaced after mapping cannot be misattributed to the old mapping.
The worker also binds the exact Python executable, Python/Torch versions,
selected Torch files, clean environment, logical `xpu:0` B70 properties, and
physical affinity index. The
call must honor the supplied output, pass the existing independent FP16 CPU
oracle with the frozen KV128 fixture and production
`atol=0.02, rtol=0.01`, satisfy the additional conservative
`max_abs_diff <= 0.02` gate, and produce the exact role-specific policy marker.
The oracle and output digests must be valid per arm; comparison requires each
digest to be bitwise identical across all four same-host fresh processes and
reports whether the common digests equal r2. A cross-host oracle digest is not
a per-arm correctness gate. There is no graph,
timing, throughput, endpoint, or acceptance claim.

The source requires the same boot observed by the passive scan, clean remote
`main == origin/main`, the exact sealed-stage/source inventory
`0923804d40a14a19ee244ce4e38641a47d9c4327b0d5c700c7b6e2756ce1aa82`,
and a fresh exact result root:

```text
/home/steve/qwen38-q64k32-remote-runtime-map-diagnostic-20260821-r3
```

The immutable r1 and r2 roots remain
`/home/steve/qwen38-q64k32-remote-runtime-map-diagnostic-20260821-r1` and
`/home/steve/qwen38-q64k32-remote-runtime-map-diagnostic-20260821-r2`; neither
may be repaired, reused, or retried.

Before the sequence, before every supervisor, again inside every worker before
its imports/operator call, and at comparison time, the source passively
rechecks both exact UUID/BDF mappings, `device_state=normal`, unchanged
400--2800 MHz reported ranges, the named service/timer state, scheduled source
inventory, and live writer-process inventory. The first overall scan is an
immutable result artifact and the per-process scans are embedded in arm and
terminal authorizations. These endpoint observations can detect a persistent
change; they do **not** prove exclusive ownership or exclude a transient writer
between scans. They cannot authorize the later clock treatment. A1 must add
the separately reviewed source-enforced lock and pre/during/post writer
contract before that campaign can run.

The scheduled-writer scan is deliberately bounded: it inspects readable files
under `/etc/crontab`, `/etc/cron.d`, `/etc/systemd/system`, and
`/usr/lib/systemd/system`, the exact current-user no-crontab outcome, named
unit state, and readable live `/proc/*/cmdline` entries. An unreadable
nonvanished process is a failure. This is useful same-boot diagnostic evidence,
not a complete future writer-exclusion proof.

Every worker runs beneath the hardened process-group watchdog with a 300-second
timeout and 10-second TERM/KILL grace. The driver validates each immutable
terminal before starting the next worker and checks the pending signal gate at
each no-active boundary. The shell owns each background supervisor from its
spawn-publication state through validation; exit cleanup allows at most 30
seconds for quiescence and then requires a supervisor-PID-bound, deeply
validated cleanup terminal proving the worker group absent. Supervisor-start,
preflight-complete, before-spawn, and spawned receipts bind process and NUL-argv
identities. A preflight failure still publishes a supervisor-PID-bound invalid
terminal with the start receipt and explicit absence of worker artifacts. The
driver installs its signal/cleanup ownership before creating the result root or
running the overall scan. Any timeout, signal, correctness
failure, malformed output, source/stage mismatch, boot change, or live process
group stops the sequence. A final comparison accepts only four valid success
terminals, the immutable overall scan, four distinct worker processes in exact
chronological order, and requires every pre/post-call map to equal the eight
r2-observed portable raw/canonical basename/path/SHA identities. Each arm must
have identical before/after full rows and all four same-boot processes must
agree on the full rows, including live device/inode evidence. It preserves every
before-to-after map delta and separately reports the earlier five-library
passive intent. A structurally valid four-arm inventory whose portable identity
or same-boot full rows differ is a durable valid negative and the comparison
exits nonzero. Oracle or output digest disagreement across the four otherwise
valid arms is likewise a durable consistency negative. A raw mapping whose
device/inode disagrees with its live canonical target is instead an invalid
arm and stops before comparison. Terminal
publication uses the frozen final signal fence and a late-signal sidecar.

## Explicit prohibitions

The driver contains no `xpu-smi` frequency setter, frequency-range mutation,
clock, model-server, or vLLM launch command. Its passive device queries use
only `xpu-smi discovery -j` and `xpu-smi config -d DEVICE -t 0 -j`. It must not
change clocks, start the full model, build or edit remote source, or reuse an
existing result root. Its output cannot be used as performance evidence. The
management shell reexecutes through `env -i` and then rejects any deviation
from the exact 11 exported names and values, physical working directory, and
three locally defined functions; a forged clean marker does not bypass that
check. The
main campaign's
`CAMPAIGN_LAUNCH_AUTHORIZED=False` and
`CLOCK_WRITER_EXCLUSION_AUTHORIZED=False` remain unchanged.

## A0 artifacts

- diagnostic worker/supervisor:
  `scripts/qwen38_q64k32_remote_runtime_map_diagnostic.py`
  (`11156bbdbb687cc9ecec9a58918d2c294c60721436a9ee7d1f6b11aed5a2cead`);
- no-clock driver:
  `scripts/run-20260821-qwen38-q64k32-remote-runtime-map-diagnostic.sh`
  (`f0865bea674c4f7ac6a1affa225b694b3f81dbc7c35bf405042f1923526f50d3`,
  mode 0755);
- CPU tests:
  `scripts/test_qwen38_q64k32_remote_runtime_map_diagnostic.py`
  (`5fbd8acd6eab2c12ce2716f9c46e92cf80387e2a460249274af1d81fd8003cb9`).

The diagnostic source pins the revised campaign/watchdog source at
`7577f9313b60d4bb51b328eb63608ab8c3bf9af31b1e84e1390164f71ee1e2fb`.
Twenty-five focused CPU tests plus the existing 48-test campaign suite must pass,
along with Ruff lint/format, shell syntax, strict-JSON, link, and diff checks.
Independent review moved the frozen r2-observed portable-row equality out of
arm-level snapshot validation: per this preregistration it is enforced only at
comparison, where a differing portable identity is a durable valid negative
rather than an invalid arm.

R1 and r2 are permanently invalid and closed. R3 remains unrun until this correction
passes independent review, is committed/pushed, and the reference host advances
cleanly to that exact commit. The later A1 campaign-authority commit must freeze
valid resulting worker-map evidence and implement the strict direct-child
authorization-receipt contract. Only a subsequent commit that adds exactly
that single receipt may be considered for enabling the 16-arm campaign; this
A0 does not do so.

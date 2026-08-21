# Qwen3.8 Q64K32 reference-host runtime-map diagnostic

Date: 2026-08-21

Status: **source-only A0 packet; no GPU run yet**. This diagnostic is separate
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
oracle with the frozen KV128 fixture/oracle hashes and production
`atol=0.02, rtol=0.01`, satisfy the additional conservative
`max_abs_diff <= 0.02` gate, and produce the exact role-specific policy marker.
There is no graph,
timing, throughput, endpoint, or acceptance claim.

The source requires the same boot observed by the passive scan, clean remote
`main == origin/main`, the exact sealed-stage/source inventory
`0923804d40a14a19ee244ce4e38641a47d9c4327b0d5c700c7b6e2756ce1aa82`,
and a fresh exact result root:

```text
/home/steve/qwen38-q64k32-remote-runtime-map-diagnostic-20260821-r1
```

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
chronological order, and requires every post-call map to equal the exact five
statically derived canonical path/SHA identities. It preserves every
before-to-after map delta. A structurally valid four-arm inventory whose
canonical path/SHA or basename set differs from the frozen five-library
expectation is a durable valid negative and the comparison exits nonzero. A raw mapping whose
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
  (`19f938ac71780648cbbce91129876025c4eb0e8646dd213209b1052bd18268e2`);
- no-clock driver:
  `scripts/run-20260821-qwen38-q64k32-remote-runtime-map-diagnostic.sh`
  (`ed6a528d061bb7d62ed210d6250f4908eb6cadd5ee2789975e27142c0360cfcf`,
  mode 0755);
- CPU tests:
  `scripts/test_qwen38_q64k32_remote_runtime_map_diagnostic.py`
  (`81e31a603b33db1e0130f101a64c826468527e5eda01fab6f261f03419649df3`).

The diagnostic source pins the revised campaign/watchdog source at
`7577f9313b60d4bb51b328eb63608ab8c3bf9af31b1e84e1390164f71ee1e2fb`.
Twenty-two focused CPU tests plus the existing 48-test campaign suite must pass,
along with Ruff lint/format, shell syntax, strict-JSON, link, and diff checks.

The diagnostic remains unrun until this source packet passes independent
review, is committed/pushed, and the reference host advances cleanly to that
exact commit. The later A1 campaign-authority commit must freeze the resulting
worker-map evidence and implement the strict direct-child authorization-receipt
contract. Only a subsequent commit that adds exactly that single receipt may
be considered for enabling the 16-arm campaign; this A0 does not do so.

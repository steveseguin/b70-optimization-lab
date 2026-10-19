# Packet58aq — one-load publication and host-wait diagnostic

This is a private vendored copy of packet58aj, the 31.966820 tok/s one-card
resident-lookup line. It is a diagnostic, **never a speed result or submission**.
CPU preparation does not launch a device, start a service or edit a live queue.
The pending device run checks `iq3-p49-split32-v1` output tokens in every view.

The whole-host lane-A proposal is
`ops/lane-queue/proposed-p58aq-split-A.txt` (relative to own-xpu-runtime).
The coordinator holds PAUSE-B and admits the final `READY-FOR-DEVICE.json`.
One process loads the model once, retains the full 29.32 GB lookup copies,
and runs all twelve registered prompts at a 32-token cap in each view:

| View | Publication probe | Purpose |
| --- | --- | --- |
| A0 | Full construction, H2D upload, scatter, drain | Opening exact control |
| U0 | Zero-byte upload, unchanged scatter, drain | Upload differencing |
| S0 | Full upload, no scatter, drain | Scatter differencing |
| D0 | Host construction, no new device operation, drain | Construction and drain floor |
| W0 | Full publication, timestamps around every host wait | Wait call versus surrounding host work |
| A1 | Full publication | Closing exact control and drift |

Every probe drains and then performs a full correct publication and drain
before model computation can resume. A skipped publication must never let a
model kernel consume stale cache pointers. This repair runs in **all** arms,
including controls, and is timed separately. The diagnostic measures the probe
boundary; its whole-request duration is not the unchanged record-line speed.
All arms keep resident lookups, the 21,552,729,600-byte cache, BF16 KV,
HC-wide, p60 fusion, wide64+halfcache, other fusion, ordered foreground
retirement, tile16 and overlapped maintenance. View and request resets use
existing code; real host sensors surround both reset paths.

`screen/split_analyze.py` reports host construction, host submission, drain and
repair in milliseconds per generated token, plus separately labeled prefill
scopes. U0, S0 and the combined device-publication/drain removal in D0 are paired against **both** controls, without interpolation
or dropping A0. It reports publication counts and control drift. Different
publication cadence makes a causal difference inconclusive; it cannot produce
a saving or a negative closure. The host-wait arm records monotonic nanosecond
begin/call/end stamps, operation, phase and normal/probe/repair scope, with grouped per-operation totals. The
blocking call envelope includes device readiness, the inherited 1 ms poll
sleep and scheduler delay; it is **not GPU execution time**. Host scopes and
wait/publication scopes overlap and must not be added.

A component clearing 0.67 ms/token after the observed control-boundary drift,
with matched publication cadence, writes `BUILD-BRIEF.md`. The brief requires
an exact replacement, replacement-overhead accounting, the unchanged oracle
and fresh-process repeats. Named host work above 0.67 ms/token writes
`HOST-WORK.md`; the lookup residual remains explicitly an upper bound. If
neither qualifies, the analyzer writes a `DO-NOT-REPEAT.md` row beside the
complete summary. Every timing row must match the complete exact output, and prefill streams must be complete. Missing streams, invalid clocks or oracle mismatches refuse
the result; they never become a negative finding.

The opening control is the integrated smoke. The separate fresh smoke proposal
is optional and is **not** a prerequisite for the single-load split. Two small
inherited K1 device fixtures precede the model load. The planned model screen
is 600–900 seconds; inherited safety watchdogs allow a slow cold load. Each
native wait is 600 seconds. The measured parent cold prefill operation is
35.8815 seconds; 600 exceeds both four times that and the 300-second minimum.
The complete parent load was 216.636 seconds; the load watchdog is 7200 seconds.
There is no elapsed-time data-proof gate. In-run checks only validate stream
presence/format and oracle exactness. All model-reading launches use `ionice -c3`.

CPU receipts are in `evidence/`. GNU and Intel miniature runs compare every
retained layer byte against the frozen parent, execute 72 request resets and
six view resets per compiler, and test wrong-oracle refusal. The device-define
probe uses the real production parser, shapes, preparation and arm sequence,
with synthetic weights and a CPU transport. It reads real host sensors at
all resets; it does not test a GPU driver or device arithmetic. The actual
`Publish` host implementation separately tests skipped upload/scatter and
repair. The analyzer replays all 60 real parent device requests, including
cold A0, and refuses their missing new split fields.

The frozen `ops/rehearse_entry.py --report` supports only five 128-token views.
Its successful smoke and expected bracket schema failure are retained.
`report_adapter.py` changes only invented fixture input and expected cardinality
to exercise the actual six-view entry, driver, analyzer, window and queue report.
It does not replace any packet report function or modify the frozen ops tool.
The shared loader, argument, storage and deadline checks also run independently.
The shared ranked preparation adapter does not accept this unranked one-card
argv; `preparation_gate.py` provides the real device-define sequence instead.
These two shared-tool limitations are explicit in READY, not passed off as
successful shared-tool checks.

The build is under 300 MB; preparation stays on nice 19 and cores 8–15,24–31,
under 4 GiB RSS. CPU work stops below 27 GB root free. Device admission reserves
25 GB after planned writes. The split reserves 100 MB and optional smoke 50 MB,
under three times their measured parent's 39,891,848 and 24,745,115 bytes.
No GPU timing or performance conclusion exists yet.

## Retention and rebuilding

`vendor.json` identifies the parent. `lineage/parent-device/` retains real
parent device logs/results for replay; these are evidence, not generated
caches. The private 4 MiB `rope.bf16` is the unchanged required runtime table
(SHA256 `92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390`).
Native object files and executables remain ignored and are hash-bound in the
build receipt. The private inherited objects are copied from packet58aj;
`build_engine.py` compiles the changed entry through `ops/compile_turn.py`.
`k1_help.py` adds only a help/exec shim around the byte-identical inherited K1
binary. This is an internal research packet, not a public reproducible recipe.
The original parent tree and shared operational files remain frozen.

[Work note](../../../../notes/2026-10-19-own-runtime-packet58aq.md).

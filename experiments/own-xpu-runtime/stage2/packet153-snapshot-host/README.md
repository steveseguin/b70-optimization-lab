# Packet153: take speculative descriptors off the host path

Private symlink-preserving copy of packet136's banked bundle8, with packet150's
vendored one-load harness and unchanged host-scope clocks. Only
`snapshot_host=production|static` switches. The replay probe is fixed off.
Arithmetic remains `iq3-p49-split32-v1`; the 58.798 tok/s record is unchanged.

The static variant builds and uploads one immutable extent table at load.
All 37 rotating bank destinations are already omitted, so the same table is
valid for all six physical bank pairs. The 24 QSA rows keep their real copies;
the kernel calculates their offset from the captured position and immutable
row geometry. Capture and reverse copy share the table. Accept builds nothing.
Deferred bank copying is empty under the inherited bank policy.

Both directions and both endpoint positions pass the original CopyEngine
checks at load. Fixed lengths and monotone QSA offsets cover intermediate
positions. All IDs remain owner-bound, process-live dependencies at submission.
Request reset explicitly preserves only this registered immutable table.
Both selections allocate it at load, preserving one-load arena identity.

This removes source/extent construction, copy validation/capture, descriptor
construction and the descriptor-upload submission on each capture/restore.
It leaves the 19.0 MB copy, flat-kernel binary search, host state snapshots,
drains, acceptance/rollback semantics and bank rotation. The measured 0.743 ms
scope is an opportunity, not a promised saving. No second search-map variant is
included: first measure the requested host-path removal without changing tile
mapping. Device equality and performance remain pending.

The proposed lane-B smoke runs all twelve prompts at 64 tokens. Its first
incident64 response must immediately pass the same timing readers after it
completes. Elapsed time is informational, including cold prefill and freezes;
the historical filename remains `first-minute-data-proof.json`.
Every stream and required scope is mandatory. The
bracket refuses until that smoke passes, then loads once for production /
static / production / static / production, twelve cold 128-token prompts per
view plus separate incident64 resets. Acceptance counts, draft proposals and
all target tokens must match. Both candidates must beat every control by 2%,
with controls within 3%; this remains a screen, never record evidence.

Storage budget is 240 MB/view, 1.20 GB for the five-view bracket, below 3× the
measured packet149 total of 402 MB. Device proposals retain a 25 GB floor and a
3,600-second cooperative watchdog (at least four times the 900-second expected
upper duration). CPU preparation stops below 30 GB root free; builds stay below
300 MB and CPU work below 4 GiB. Compilers use the shared compile-turn arbiter.
No GGUF/full-shape input is read while the record chain runs.

Only `READY-FOR-DEVICE.json`, written last after gates, can admit this packet.
Inherited metadata is under `lineage-inputs/` and proves no new device result.
Proposals are prepared only, never queued by this task.

See [CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md) for the exact
completed test scope and retained failed attempts. Device results remain pending.

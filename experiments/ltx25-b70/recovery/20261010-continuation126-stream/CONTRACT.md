# Packet126 CPU preparation contract

Parent: sealed packet125 (`3c2ed91975343ceb1acd2c4fe06e0fe1d7b768e0fff594865a8ec3bbbb565421`).
This packet is CPU prepared, not device qualified. It inherits the parent's
model, arithmetic, graph and qualification gates. HTTP paths do not change.

## Storage option

`LTX_STORAGE_SCAN_MODE=request|background` defaults to `request`, the parent's
synchronous strict run-owned allocated-block accounting. `background` is an
explicit candidate, applied only after qualification reaches streaming. The
qualification captures retain synchronous checks. Run names add `-ssbackground`
only for the candidate; the value is bound to status, every receipt, decode,
preview and qualification verdict, and to the client's expected options.

A CPU helper runs the same strict walk at a 0.25-second interval and after
request/preview publication. It publishes a sample under a short state lock;
the filesystem walk never holds that state lock. Requests use a completed sample
and perform the unchanged whole-filesystem reserve check on every call. A sample
older than one second, a scan error or a two-second completion-epoch timeout
refuses admission. An additional 256 MiB of pending-write headroom is required
inside the chosen run allowance. No reserve, allowance or file-type/symlink
check is removed. With the option off, accounting follows the parent path.

Preview MP4 and JSON publication already runs on its own bounded CPU worker.
Its fsync-before-rename ordering, recorded hashes and completed-file readers
remain intact. Packet126 does not move preview work onto a different worker.

## Exact plan-integrity shortcut

The same explicit `background` option also enables the combined CPU bookkeeping
candidate: serialize the entire in-memory plan with Python's typed binary
`marshal.dumps(plan, 2)` on each integrity check. Initial loading still verifies the
canonical inner plan SHA256. If the full binary serialization matches the
previously verified tree exactly, its canonical hash is necessarily unchanged.
Any binary difference takes the original canonical validation path; it cannot
silently adopt a changed plan. This is a cheaper repeated proof of an unchanged
plan, not removal or sampling of the integrity check. `request` retains the
parent canonical serialization on every check. CPU timing predicts a useful
saving; the live receipt buckets decide the actual period effect.

## Unchanged proof requirements

The three qualification chains still compare complete captures and decoded
bytes. Cone-last-frame equality, native precompute equality, reference hashes,
route/signature freezes, memory floors, snapshots, fault latches, storage refusal
and no-retry rules stay. A candidate speed observation cannot replace any gate.
The new stream namespace and clip ids do not change the numerical contract;
all 3,960 qualification graphs must equal the parent after namespace normalization.

The sealed125 application maintenance code and transformed `source/main.py`
are inherited byte-for-byte. `LTX_GC_INTERVAL_SECONDS=10` is the first comparison;
60 remains a separate inherited candidate with its original scope restriction.

## Evidence status

The requested 5.61–5.64-second period at145 is a target, not a CPU measurement.
The initial forecast is 5.55–5.75 seconds per six seconds of video. Native output
identity, memory, stability and speed require coordinator-run qualification and
two fresh matched servers. This CPU task performs no launch or live preflight.

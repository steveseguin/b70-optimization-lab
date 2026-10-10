# Packet 129: publish complete evidence before exposing its name

The preview HTTP 500 at 04:32 UTC (packet 121, chunk 154) and decode HTTP 500
at 09:27 UTC (packet 127, chunk 80) were evidence publication failures while the
server remained healthy. A direct exclusive open protects against overwriting
an existing file, but exposes the final filename before writing finishes.
The client correctly stops without retrying an HTTP 500; each incident cost a
client restart and about twenty seconds of stream. Packet 123 addressed preview
MP4/JSON publication. Packet 129 extends that contract to every remaining
packet-owned route evidence writer.

Parent is sealed 128, manifest
`bd6471f7e10d2ec3219879a281820056178556a3388f50fb7c2c7896199f5ead`.
The [complete route/file inventory](../recovery/20261010-continuation129-stream/inventory129.md)
records readers, producers, old behavior and new publication. The
[contract](../recovery/20261010-continuation129-stream/CONTRACT.md) and
[future launch reference](../recovery/20261010-continuation129-stream/LAUNCH.md)
are coordinator instructions, not executed operations.

## Publication and the unchanged guard

A writer creates an exclusive private file in the same directory, finishes its
bytes, flushes and fsyncs, then calls Linux `renameat2(RENAME_NOREPLACE)` and
fsyncs the directory. The final filename is absent until its file is complete.
An abandoned private file or existing final refuses another publication.
A duplicate writer cannot replace an inode a reader already holds.

This last property is necessary: `read_regular` checks device, inode, size,
mtime, ctime and link count before/after reading and against the final path.
An ordinary replace or hard-link/unlink sequence can still violate that guard
without changing payload bytes. Packet 129 leaves the entire reader function
byte-for-byte unchanged, with a dedicated source-equality test. Actual mutation,
symlink, linked-file and size refusals remain. No guard failure is hidden, and
no new reader retry is added. Packet 123's preview helper is inherited unchanged.

`session.write_exclusive` now atomically publishes the identical canonical JSON
and returns the same hash. That covers receipts, decode records, verdicts,
freeze/halt records, run diagnostics, installation records and latches. Both
anchor writers retain their finite-value/shape checks, exact bytes, layout and
hash fields while changing publication only. Capture tensors use the same
safetensors serializer on a private filename; capture summaries preserve their
indented JSON bytes. Startup identity/fault JSON uses the verified packet helper.

The generic `/view` route rejects private `.name.partial` files, including
resolved aliases and asset-hash paths. Its admitted output files are preview
MP4s, capture safetensors and capture summaries. It sees a clean 404 while a
new final is absent. Record routes likewise return their existing clean 404 or
the complete existing record. Duplicate publication refuses, preserving that
record. Status is assembled from in-memory snapshots and existence checks;
identity serves its startup-validated object.

Qualification action still drains both workers, requires committed records,
and validates every receipt/decode/capture/reference hash before opening stream
phase. Plans, manifests and reference evidence are sealed before the listener
can start. No HTTP consumer reads an append-only evidence manifest, so there
is no new committed-prefix parser. Operational logs are not route evidence.

The external model-verification gate retains its fresh per-prompt status check.
Its finalizer already flushes/fsyncs a complete replacement and refuses to
replace a passed gate. The older `scripts/stage-model.py` preparation helper
already used a complete temporary replacement but lacked durability fsyncs;
this change adds file and directory fsync without executing staging. That
mutable status gate is intentionally old-or-new, unlike immutable run evidence.
Its existing pending-status 503 remains an admission refusal, not a torn read.

## Identity, launch and limits

Packet 129 changes the namespace and plan identity and requires
`features.atomic_evidence_publication=true` in the client. The client also pins
the publication helper before loading receipts. All plan pins are the inner
`plan_sha256`, never the JSON envelope's file hash. The complete parent history
and old bytes of changed files remain in recursive sealed provenance.

Packet 128's maintenance code, options and default behavior remain. The first
recommended arm keeps 127's 145-frame production geometry, serial display on
xpu:3 and legacy auxiliaries, with 128's idle maintenance and GC60, snapshot
digest cache1, background storage and a 16 GiB run allowance. The client workdir
default is `/home/steve/ltx-stream/s129-live01`. Both wrappers use the pinned
`bin/python -B`. The 169-frame display2 memory refusal remains unresolved; no
memory reserve was reduced. This is a reliability fix with no claimed speedup.
Native byte/three-chain, long-run memory and two fresh-server speed gates remain
with the coordinator. There is no model arithmetic, precision or quality waiver.

## CPU evidence

The [build receipt](../data/resume-20261008/continuation129-build.json) records
exact suite counts, source/log hashes, the seal, recursive verification, cache
counts and scratch cleanup. Tests invoke actual registered record/status/action
handlers and isolated actual upstream `/view`, identity and prompt handlers.
They pause real writers mid-write, check absent or unchanged committed files,
then verify complete bytes/hashes after publication. Failure injection checks
fsync refusal, duplicate publication, unchanged reader guard and private-name
protection. Capture math is mocked; these are publication tests, not native
model quality or performance measurements.

Development logs are retained. An initial anchor-writer edit accidentally
removed latent metadata construction; round-trip tests caught it and the exact
parent metadata construction was restored before seal. Inherited packet-number
and parent-source assertions needed the new namespace, as did graph namespace
normalization. A capture fixture initially compared tensor bytes with summary
bytes; it was corrected. Every relevant final suite is rerun after corrections.

All preparation and validation is CPU-only, nice19, OMP/MKL2 and the pinned
Python with `-B`. No GPU/device open, model server, launch/check-only, port8188,
systemd/unit, signal, existing-run/client-tree write or host-setting operation
occurred. Scratch belongs only to these CPU tests and is deleted after use.

Final validation: **796/796 recovery tests** in one complete corrected run,
including **33 atomic publication cases**; **3,850/3,850 client checks in 33
suites**; **10/10 mocked preflight checks**; and **two complete CPU runtime
cases** (145 frames with GC10 and GC60, 22 chunks, twelve cross-chain decoded
hash comparisons, identical GC10/GC60 decoded hashes). No final cases were
excluded or satisfied only by a separate recheck.

The sealed tree contains **2,196 manifest-bound files / 2,198 total files**.
Recursive parent verification passes; every bound file was rehashed after all
tests. There are zero Python caches. All 33 client `/tmp` roots are verified
absent, recovery scratch is removed, and runtime `/dev/shm` fixtures clean up
at completion. The broad pin audit still finds the same 231 existing Flash-Next
drifts as packet 128; packet 129 source closure and every inner-plan pin pass.

Manifest:
`42e6a7452e11873f33c78a953105754605121f2a96dfca1954b1d55966a4886c`.
Inner plan:
`466039fc05fa45169c4e7c054c824b375da4e0a4d4ecbe3f374c6679dbd06536`.

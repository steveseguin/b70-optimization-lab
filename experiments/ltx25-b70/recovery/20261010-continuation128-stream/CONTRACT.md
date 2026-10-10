# Packet 128 CPU preparation contract

Parent127 manifest `c2564507a9bb88a948bc726d079d8b5a981b3834ad54801be47d0d0c81dc359e`.
Prepared candidate only; no native quality, memory or speed qualification.

`LTX_MAINTENANCE_MODE=parent` defaults to packet127's periodic decisions and
queue timeout. `idle` changes only when the same full `gc.collect()` and
`soft_empty_cache()` pair runs on the original prompt worker. Automatic GC,
model arithmetic, precision, tensors, hashes, snapshots and preview encoding
are unchanged. No heap freezing, background collector or skipped cleanup.

After the GC interval expires, a250ms quiet gap allows cleanup. A queued
successor retains cleanup debt and runs normally. At60seconds since the prior
pair, cleanup is mandatory at the next prompt boundary; an in-flight prompt
can exceed this bound. Startup and explicit free/unload force cleanup. Due
queue waits do not spin. Native failures preserve the parent's exception flow:
failed collection never proceeds to allocator cleanup. Existing timestamps
remain; bounded32-decision schedule records add age, quiet time, reason and
run/defer selection. Forced/automatic collection can still delay a receipt.

Candidate scope:145/169, two-way20-28/frame/dg0/cone/bo1/pa1, fingerprint/full,
legacy auxiliaries, read-ahead0; serial display3/sampler-A or inherited parallel
display2/eager-display. Parent restrictions remain:169legacy requires display2;
GC60/cache1 remain145-only. GC10 is recommended; GC60 reaches the hard age when
first due and gets no extra deferral. Off preserves all127 admitted forms.

Mode is bound by the `-mi` suffix, launch identity, status, receipt/decode/preview
server options, qualification verdict and client expectation. Invalid values or
mismatches refuse. Client pins are inner plan hashes, covered by the all-pins
test. Nine captures, reference equality, three-chain repeat, conditioning,
cone/display, all recorded hashes, memory floors, storage freshness, refusals
and latches remain mandatory. Native fresh-server validation remains open.

The CPU timing gate invokes the actual registered receipt route under a
synthetic decode thread and simulated GIL-holding cleanup. It demonstrates the
scheduling change, not native network/model speed. Long client gaps and the
mandatory minute-age pair remain; an arbitrary GIL-owning thread can still
block Python. Quiet cleanup may overlap decoding as it could already in127.
Live period and memory plateau need coordinator qualification.

Author/build/test: CPU-only,nice19,OMP/MKL2,pinned Python -B. No launch/check-only,
GPU/device/port8188/unit/signal/live-client-tree/existing-run write or host change.

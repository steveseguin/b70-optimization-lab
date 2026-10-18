# Packet142 — class layout prepared ahead of packet141

CPU-only preparation began at 19:09 UTC, October 18; 75-minute limit.
The current two-card record remains 58.798 tok/s. This task makes no speed claim.

The new packet copies frozen packet136 bundle8. Every inherited symbolic-link
object is preserved; original destinations are recorded in `copy142.json`.
Non-allowlisted dependencies are local snapshots. The packet49 oracle remains
bound only through `oracle-binding.json` and `shared_oracle.py`.

The three preregistered candidates are attention-order512,
expert-gate-up-order512 and hc-gate-low-order512. They retain byte-identical
copies in consumer order, capped at 512 MiB per rank, with complete consumer
tuples only. This is a bounded prefix of each class, not full-class coverage.
Physical adjacency is an allocator hypothesis, not a guarantee. Both sets are
loaded before timing; view changes only bind existing buffers and recapture.
The expert arm keeps the accepted halfcache, packed rows and kernels. It does
not repeat packet104/104b's losing gate/up tile16 transpose.

The conservative maximum leaves 3,531,201,420 bytes on rank0 and 249,398,566
bytes on rank1 under the unchanged 30 GiB arena ceiling. Actual allocation
census and full-shape checks are still required. Host admission adds 1 GiB for
the two retained banks to the inherited 97 GiB allowance.

Git pull refused unrelated dirty work; fetch confirmed shared HEAD and
origin/main at e77a3cb0f209fab6838a869cc81584e4eaaed6d3. No unrelated file,
frozen packet, live queue, service, device, host setting or process was changed.

The initial build stopped before device linking when copied inherited objects
put build material at 306,110,535 bytes, above the 300 MB limit. Replacing these
redundant local copies with hash-bound links to the allowed frozen binary
objects reduced build material to 257,586,144 bytes. The refusal is retained;
no cap was raised. Source snapshots are tracked separately in `native-base`.

## CPU proofs and corrections, 19:39 UTC

The initial 512 MiB class bank was too small for one complete expert gate/up
consumer pair (550,502,400 bytes), so the registered variants are now
attention-order600, expert-gate-up-order600 and hc-gate-low-order600. The fixed
600 MiB cap leaves at least 157,123,878 bytes within rank1's unchanged 30 GiB
arena ledger. Host admission adds 1200 MiB to 97 GiB. No host setting changed.
The first whole-matrix copy hit CopyEngine's 128 MiB limit in the CPU fixture;
32 MiB load-time chunks fix that. Neither correction changes arithmetic.

All twelve full-shape fresh/switch checks and twelve real-parser startups passed.
These use numerical allocations and never read model payloads. All six rollback
capture pairs stay identical after normalizing the alternate weight allocation IDs;
request-state reset covers every mutable allocation, and boundaries neither allocate
nor write weights. The final guard rejects a different class before any mutation;
its rebuild is waiting behind the one-card hold through the compiler arbiter.

GNU and Intel each passed two fresh runs over real matrix dimensions with synthetic
finite bytes: 679,424,000 weight bytes, 2,163,264 FP32 checks and 55,616 output rows.
All four output transcript hashes agree; peak child RSS was 548,568 KiB. No model
or GGUF payload was read. The entry and queue gates are still being finalized.

The packet's own offline prepare_submission replayed a local copy of packet136's
chain bundle through its real payload/attestation checks and rederived
58.798108759182306 tok/s. A corrupt WS128 summary hash was refused. An inherited
validator looked for the oracle checker in the generic source map; the local copy
now validates it through the genuine oracle binding and shared-oracle seal.
This is rehearsal evidence only; no external submission and no new speed claim.

Local closure checks found inherited absolute native includes of packet136's
kernel_guard.hpp. They now name the byte-identical local copy. Historical metadata
and inactive v5 helpers are retained under lineage-inputs rather than treated as
current pins. The compiler, active runtime and wrapper source closures are local;
only allowed oracle/model inputs and hash-pinned frozen binaries remain external.

The explicit six-row admission receipt corrects the intermediate arena-margin
arithmetic above: the conservative rank1 margin is **155,895,078 bytes**.
Actual rank1 margins are 163,267,878 / 235,767,078 / 412,714,278 bytes for
attention / expert gate-up / HC gate-low. Coverage is 27 / 2 / 96 weight tensors
per rank respectively. The expert arm covers one layer per rank, while HC gate/low
covers all 24 layers per rank. This coverage limits any future negative inference.
All 182 inherited symbolic-link objects and every allowed external binary hash
passed the closure audit. No foreign process or stale coordination marker was touched.

## Entry preparation while the compiler waits

The final native rebuild waits through ops/compile_turn.py behind the whole-host
hold. Its recorded owner has exited; the marker remains coordinator-owned and
was not changed. Preliminary CPU-only probes simulate only the missing final
composition predecessor, and are explicitly **not** final readiness receipts.
They exercise the real unit/environment checks and intercept both native launches,
then cover all 65 bracket requests and corrupted-output cooperative teardown.
The first entry probe found a doubled vendor-root path in the inherited suite
loader. The packet142 worker now resolves its bound metadata against the real
repository root. The oracle authority itself is unchanged. The metadata helper
also keeps plan stdout to one JSON object while retaining the full authority check.
The preliminary plan parses with 4800 s watchdog and 720–1200 s estimate.

All six new proposal files now exist under ops/lane-queue and have local mirrors.
No live queue was edited. Final real-seal entry tests and temporary queue planning
remain pending. This intermediate state is published so the coordinator can see
why the final marker is absent; it grants no device-launch readiness.

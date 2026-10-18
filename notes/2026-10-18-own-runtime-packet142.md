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

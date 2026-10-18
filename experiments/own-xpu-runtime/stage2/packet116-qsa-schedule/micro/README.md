# Packet116 complete QSA layer micro

A copy of packet110's frozen harness, restored to QSA layer 3. It uses the
packet103 production selection and generated fixture weights/state at full
model dimensions. This is a diagnostic microbenchmark, not a model result.
No publisher model payload is loaded.

Production and p116 run in both orders at occupied contexts 128 and 4096.
Four exact cases compare every producer output and the entire scratch, score
and probability allocations immediately after selection/attention. All
logical state and mutable allocations are compared at layer completion.
The two fresh device processes each run 50 timing pairs per context, alternate
arm order, discard the first 10 pairs, and compare full mutable state outside
event timing. Every event attributed to qsa.attention and qsa.select is summed
before computing medians; attention spans multiple kernel events.

The kill gate is the ratio of candidate versus production median summed
attention+selection time <= 0.6 at context 128 in **each** fresh process.
Context 4096 is reported separately. Any byte mismatch, incomplete event
coverage, missing order/context, reused process or identity change closes
the gate. CPU tests and synthetic qualification-unit tests cannot pass the
device speed gate.

Expected device lifetime: 240 seconds per fresh owner; watchdog: 1200 seconds
(5 times the estimate). The coordinator alone may run the proposed jobs.
The preparation agent runs CPU compilation, exact host checks, and plans only.

Build uses packet94 compile_turn.py and read-only inherited packet111 objects;
new dispatcher objects belong to this micro. See build receipts and
source-origin.json for exact source/object identities. Every existing packet
and screen wrapper remains unchanged. Combined packet116 build is capped at
250 MB and root free space at 25 GB.

The micro owns a snapshot of the packet111r-derived entry, selection dispatcher,
and unused bracket instrumentation headers. These are copied under
`native-src/` and `native/`; only their include prefixes changed. Its GNU,
Intel and device dispatcher objects are compiled locally. Later v5 startup
fixes therefore cannot alter this micro's sealed source or object identity.
`native-snapshot.json` records the original and copied bytes. The root
`evidence/cpu-leaf.json` exceptional-value gate is independently revalidated,
including both compilers, both fresh processes, source hashes and output hashes.

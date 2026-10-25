# Persistent four-card rolling qualification

The corrected two-request run passed. One continuously loaded four-worker set
processed the same 87-token prompt twice, clearing request state between requests.
Each produced exactly the retained 32 output tokens and matched all 2,065 target
buffers and 73 canonical draft allocations. Native binary `02a47c059444` is
unchanged from the initial controller refusal; Python correction `bcffecb25`
inspects actual mmap bytes. No training or host setting changes were involved.

Both request identities and epochs are distinct. Native allocation identities
and global wire sequences remain continuous across RESET and DUMP. Each request
has 118 target input rows, 117 canonical draft pairs and 32 two-step predictions.
The scheduler used 34 and 35 speculative target rows, respectively. Both miss
depths occurred; each request passed seven first-stage provider-survival checks,
five after provider advancement. Observed provider borrows were depth0=94,
depth1=23, depth2=0 for each request. The earlier separate forced-pending test,
not this run, supplies two-pending-provider coverage.

All four workers exited zero, with no live PIDs in the terminal result. Across
77 passive samples, the 14 known fault signatures stayed unchanged; minimum
available memory was 68,420,321,280 bytes. The last passive sample precedes final
worker exit; terminal process status independently establishes exit. This run
used full diagnostic readbacks and is not a throughput result. Cold RESET did
not individually read back every cleared allocation; final full-state comparisons
are the separate byte-parity evidence.

[Proof](../experiments/own-xpu-runtime/research/continuation-2026-10-25/persistent-rolling-qualified-proof/summary.json)
qualifies ten per-request raw bundles. The archive preserves all sixteen raw
bundles, including unqualified final sentinel/FINISH copies. Its complete packet
is 537,758,698 bytes, SHA256
`aca9a6368e7492e1d951342bcd7baeebfc016f8e82dae0fcc799724c4b589acc`.
The compact packet is 5,119,973 bytes, SHA256
`9458087f43ba9b34bf43a250557880689452f50e5c3cbb9d4bdd218f69f42b3a`.
All 1,361,705,056 raw bytes exactly reuse the pinned portable-live base archive;
all sixteen restored independent copies passed the native sealed reader.
The compact packet is copied and rehashed on USB; originals and complete packet
remain retained. [Durable receipt](../experiments/own-xpu-runtime/research/continuation-2026-10-25/persistent-rolling-qualified-durable-archive.json).

Next is the same two-request cohort and native binary with a separately fixed
measured policy: diagnostic readbacks disabled, mandatory copies/host/error checks
retained. That run must match both this qualification and the accepted baseline
before the full twelve-prompt timing experiment. The six prior CPU-reference
disagreements remain unresolved; internal replay parity is not that claim.

# Packet99 CPU preparation closeout

Question: can exact grid representation or address-space changes shorten the
IQ2_S gate/up dependency exposed by packet86, without moving FP32 sums?

Identity: frozen packet97 source copy and inherited object hashes, wide64,
`iq3-p49-split32-v1`; seven sealed production/candidate views. See
`copy-lineage.json`, `build-device-receipt.json` and `screen-jobs-seal.json`.

Outcome: three IQ2 mechanisms plus half-cache combinations pass both compilers,
raw FP32 chains/trees, full-size engine startup/admission, negative allocations,
selection refusals and linked no-spill inspection. The actual SLM loads are
present. The IQ4 byte-pair alternative is exact but spills and is closed in
[its own record](DOWN-CLOSEOUT.md). No device result exists.

Useful mechanism: the IQ2 dependency is one eight-byte grid entry per eight
weights, with inline sign bits. Full SLM shortens address space; compact SLM
also reduces fill, while compact global trades more decode instructions for a
smaller table/read. Earlier compact-grid history remains credited. Static
instruction counts do not predict which trade wins.

Failures and uncertainty: a CPU negative test initially expected the wrong
refusal string for the cached stride; the engine correctly refused both
short and misaligned allocations. A proposal job name initially contained `+`;
temporary planning rejected it, then passed after unit-name normalization.
Neither incident launched a device. GPU synchronization, BF16 outputs, latency,
occupancy under the installed driver and whole-model speed remain unmeasured.

Retained evidence: both native binaries locally, copied sources, compressed
byte transcripts, all arena/plan archives, asm/vISA for passing and rejected
arms, seals and thirteen proposed queues. [Retention and rebuild](RETENTION.md).

Next gate: the coordinator's one-card microbenchmark, then only candidates
meeting the 15% threshold enter their own B bracket and A confirmation.
Lane A decides any record choice. This closes CPU preparation, not the lane.

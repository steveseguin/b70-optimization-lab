# Packet155 — bundle9 preparation ahead of packet153

CPU-only preparation requested for a copy of packet136's two-card record chain.
Bundle9 adds packet153's `snapshot_host=static`, keeping bundle8's remaining
choices and `iq3-p49-split32-v1`. The record remains 58.798 tok/s
(`cmve4dtir007wrf01k57sdf23`). No device result is claimed.

The initial copy preserves links and excludes prior build/run outputs, selections
and submission outputs. The original metadata is retained under
`lineage-inputs/packet136-history`. Packet153's two completed binaries and native
sources are copied into the new tree and bound by SHA-256 in the orchestration
`inputs/packet153-native.json`; launch must not depend on mutable parent files.

At copy completion root had 30.111 GB free. The CPU stop floor is 30 GB,
CPU memory ceiling 4 GiB, and build ceiling 300 MB. Existing packets, live
queues and orchestration are untouched. No service, GPU or host setting changed.

Readiness stays false pending coordinator confirmation of packet153's v5
bracket: both static views at least 0.5% above every warm control, exactness
throughout, control drift at most 1%, and strict combined gain above 2% over
58.798 unless the coordinator establishes that the lanes are idle. Device
admission and performance/quality qualification remain separate.

The final READY-FOR-DEVICE marker is not yet written. CPU gates and submission
rehearsal are pending. Submission scope must remain 128 tokens, strict512 false.
Packet150's 0.743 ms/cycle capture_snapshot host scope is attribution only,
not a promised gain. Packet153 bracket numbers are pending, never invented.

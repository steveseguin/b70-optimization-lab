# Host embedding packet11: prepared, not yet deployed

2026-09-14. The actual CPU CLIP integration passed six groups and the resident
component assembly passed nine stdlib tests. The new builder passed eleven
stdlib admission/graph/lineage checks. Root reviewed the source and ran its
check-only and prepare commands; the generated packet verifier and unchanged
launcher check-only also passed. No native GPU claim follows from these checks.

Packet `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-host-embedding-11`
is sealed at manifest SHA256
`34b7ff2f7a74b6951f87dd2621738b37930d15a5de9d064409c8b12351adcf08`.
It retains all packet10 numerical source bytes and graphs, adds four canonical
encoder extensions and one custom-node directory, and changes only nodes420/421
in the two added graphs. Original transformer dispatch and original VAEDecode
are used for the planned comparison. Encoder memory reserve and native loading
budget are unchanged. The CPU token table retains BF16 precision; conversion
and scaling remain on XPU2. There is no prompt/conditioning/output cache.

The source builder initially refused an ambiguous checker string replacement
before any packet preparation. Its corrected source anchors the extension tuple
to the following NODES assignment. Both the correction and failed source snapshot
are preserved; no live application was affected.

Evidence: [summary](../data/host-embedding-runtime-11/summary.json),
[manifest](../data/host-embedding-runtime-11/manifest.json),
[checker patch](../data/host-embedding-runtime-11/runtime.patch),
[eleven stdlib checks](../data/host-embedding-builder-source-01.json),
[offline preparation admission](../data/host-embedding-runtime-11-check-only.log),
and [launcher check-only](../data/host-embedding-runtime-11-launcher-check-only.log).

Next: independently review the bounded15-clip original/host-table/original
client, load this package through one controlled LTX application reload, and
verify startup registration before requests. Every clip must pass all four
original raw output oracles; the host arm must prove actual full remaining
encoder residency and unchanged token/embedding precision. Retain at most three
previews and prune only campaign-owned raw data after full comparison. The live
application remains packet10 PID84255 until the migration is explicitly recorded
in CURRENT.md. The computer has not been restarted.

# Lossless state capture qualification

The one-pair format qualification passed on October 24, 2026. Original prompt00
ran target-only and MTP with 128 output tokens each. Both complete token sequences,
all logical target buffers and state JSON match the original baseline exactly.
This qualifies the evidence format; it is not a speed or broad model-quality claim.

The independent audit read 166 physical artifacts (719,633,260 bytes). Six bundles
contain 6,324 original ranges totaling 665,229,504 bytes, with exact inventories,
lengths, contiguous offsets and hashes. Target-state files fell from 6,330 to 24;
draft files and other evidence are unchanged. Initial pre-RESET bytes happened to
match, but that comparison is informational rather than an assumed semantic oracle.

RESET repeated the first request capture. An explicit final DUMP repeated the last
capture before FINISH; FINISH itself only captures draft state. Closed maps and file
stamps remained unchanged. Both owners exited normally with no signals, no retained
processes, empty target descriptors and no new GPU faults. Allocations remained
30,947,490,698 and 29,824,495,508 bytes. The protected vision process was unchanged.
The coordinator completed in 135.531 seconds; this includes setup and evidence work
and is not an inference throughput measurement.

| Identity | SHA256 |
| --- | --- |
| Native binary | `5a8c9d3b58606022e21e2f0347360e4dd9cfdf6a869c8daac145e928fe4d4306` |
| Admitted plan | `13897666770be4f6cc7a6c6a21e7d9d833b543c9f76e13ad6d997beb2a217f31` |
| Full result | `d4d84f1d9bc6cbfa3b6b557cc5fe180ba76d9fc3f2fbfccbfe86504a152319a3` |
| Independent audit | `1c41b70d7b13f149ad8642b5de055937be3301488228e47120fd8bab6e21b82e` |

[Independent review](evidence/device-a/review.json),
[compact summary](evidence/device-a/summary.json),
[auditor](evidence/device-a/audit.py) and
[physical artifact index](evidence/device-a/artifact-index.jsonl.gz) preserve the
checks. Full raw evidence is at
`/mnt/usb-models/own-xpu-runtime-results/gsq-state-bundle-a`; coordinator receipts
are at `/home/steve/own-xpu-runtime-results/gsq-state-bundle-a.control`.
Retain these bundles as the exact format oracle. Read them with [reader.py](reader.py)
and their original index/seal files; no extraction or lossy conversion is needed.
The small compressed index is tracked to bind every retained artifact.

The format is adopted for subsequent internal diagnostics. It changes neither model
arithmetic nor target verification. Bundling reduces file count, not payload size;
future full suites still need enough storage. Next is a current-binary class profile,
with exact baseline checking and no speed claim, to select a worthwhile model change.

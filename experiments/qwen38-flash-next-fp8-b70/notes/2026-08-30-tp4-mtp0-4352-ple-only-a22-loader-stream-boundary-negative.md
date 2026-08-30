# Qwen3.8 Flash-Next FP8 A22 loader-stream boundary negative

Date: 2026-08-30
Status: bounded pre-endpoint validation-patch negative

A22 did not expose a missing or corrupt checkpoint shard. Artifact,
filesystem, staged-runtime, four-GPU, and TP4-XCCL preflights passed. All four
workers initialized and all four exact 11.92 GiB PLE host-placement receipts
appeared. During the external 131-file load, TP3 then failed closed with
`missing=[126, 127]`; the endpoint never became healthy and no client, request,
trace, quality row, or performance row existed.

The checkpoint index contains all 128 logical PLE shards. File 36 carries
shards 122-125. File 37 starts with the sibling `ple.conv1d.weight` and then
carries shards 126 and 127. `AutoWeightsLoader` groups contiguous child
prefixes, so the PLE embedding loader received shards 0-125 in one call and
126-127 in a later call. Patch 0023 incorrectly finalized coverage after the
first child call. The failure therefore validates that the check failed
closed, but also proves its boundary was wrong.

The corrected source at `f69a0ef46338f93636671c87caa527b3ac2ca129`
accumulates coverage across child calls and validates once after the root
`Qwen4ExpForConditionalGeneration` checkpoint stream is exhausted. Capability
discovery skips GPU placeholders and the AMD-resident PLE variant. It rejects
total omission, partial omission, duplicates, and unexpected indices while
accepting the actual 126+2 grouping. Twenty-one PLE tests and four root/offload
tests pass; ruff, formatting, and diff checks pass. Independent review found no
remaining blocker. Patch 0023 is preserved as a failed experiment; patch 0026
is the corrected successor. Neither patch changes forward inference,
placement, graph, scheduling, or performance selectors.

A22's raw `identity.txt` inherited the stale line `diagnostics=none`. The
launcher did configure a rank-templated trace file and `rank=all`, but loading
failed before a trace-eligible request. This is an evidence-receipt defect, not
a trace result. The successor must record those trace settings explicitly.

Cleanup completed without OOM, host reset, storage error, or B70 fault. No
server, worker, or port-19694 listener remains and all four GPUs rediscovered.
The fresh-boot load marker remains intentionally consumed, so there is no
same-boot retry. A23 must use new paths and a fresh boot. If it reaches the
trace, A23 becomes the first member and still needs an independently started
A24 peer.

Structured receipt:
[`../data/20260830-tp4-mtp0-4352-ple-only-a22-loader-stream-boundary-negative.json`](../data/20260830-tp4-mtp0-4352-ple-only-a22-loader-stream-boundary-negative.json).

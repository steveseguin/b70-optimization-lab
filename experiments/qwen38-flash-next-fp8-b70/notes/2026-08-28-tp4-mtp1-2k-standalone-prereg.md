# Flash-Next TP4 native-MTP1 exact-2K standalone preregistration

Date: 2026-08-28

## Purpose and changed evidence

Classify the still-missing TP4/EP4/eager/text/native-MTP1 active-2K cell with
one fresh server and at most two requests. The earlier combined 1K/2K program
correctly skipped this boot after MTP1/1K stopped. Since then, independent MTP2
and MTP3 servers have both completed this exact 2K transport shape, which is
the material new evidence authorizing a standalone bounded arm. Their parity
quarantines remain unchanged.

## Frozen identity

- local-NVMe model revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`, kernel checkout
  `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`, loaded stage build
  `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, eager/graph-off, text-only, native MTP1, max length 3,072,
  max batched tokens 64, one sequence, cache and async scheduling off;
- BLHNC automatic KV, exactly `376569856` bytes / 32 proven blocks;
- selective UVA PLE/input embeddings at 12.22 GiB per rank;
- attempt 2, port 19661, no diagnostics.

Launcher:
`tools/launch-tp4-ep4-eager-mtp1-3072-headroom32-attempt2.sh`, SHA-256
`aa6f6b17c07be9d00699da3244553f905fc2222cff189ecae61d568e86c3b893`.
The shared launcher, exact-depth harness, fixture, and frozen MTP0 repeat-v2
receipt retain SHA-256 values `62b40c9268a665727ff3946a621e4fcd2db072ed0bd4595dde7a6a006083ccb7`,
`8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067`,
`c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d`,
and `ecfbd7bf09fc2637bbee9be4658e1febc8ec8cc19f6f61c71864a615a2b25794`.
The frozen MTP0 token-array hash is
`5fd297f79da317b0741140cccb52fb710f89dfd1444effe9068b806b0300e57e`.

## Execution and stop rule

Require all launcher identity, clean-source, four-card/four-rank, staged import,
placement, exact 32-block cache, 3,072-token capacity, served identity, and
health gates. With no warmup, send the sealed exact-depth 2,048-prompt /
128-output request at temperature zero and seed one. Require the built-in
depth gate, zero cached tokens, length stop, the frozen MTP0 hash, and positive
MTP1 draft/accepted-token deltas. Only after every request-one gate passes may
the identical determinism sentinel run once.

Stop on any mismatch and do not send request two. Do not extend the 300-second
engine gate, change cache allocation, warm the shape, or reuse a server. The
arm is capped at one boot, two requests, and 35 GPU wall minutes. A pass adds
only this Grade-C cell; a stop is a retained quarantine. Neither changes MTP1
512/4K, MTP1/1K, MTP2/2K, MTP3/2K, featured results, or captured speeds.

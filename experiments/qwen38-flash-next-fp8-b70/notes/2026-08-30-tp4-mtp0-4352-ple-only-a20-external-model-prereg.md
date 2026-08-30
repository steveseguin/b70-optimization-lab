# Qwen3.8 Flash-Next FP8 A20 external-model trace preregistration

Date: 2026-08-30
Status: frozen before GPU launch

A20 removes the repeatedly implicated local NVMe from checkpoint reads. It
uses `/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8`, the original pinned
intake artifact validated on 2026-08-26: revision `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`,
144/144 files passed, 131 shards, 185523317458 shard bytes, and tree SHA-256
`4a3793bd4a795ea6761b3d322200b4a1fd8300cdeb75cc127d330d513f590eb2`.
Its file-name/size tree and index/config hashes also match the local copy.

Only model/tokenizer path and isolated attempt 20/port 19692 lifecycle,
cache, and evidence identities change from A19. Model revision, vLLM/kernel/
runtime heads, TP4/EP4, PLE-only UVA placement, MTP0, eager scheduling,
4352-token capacity, cache size, seeds, request order, quality helper, output
authorities, and report-only trace are exact. Load time receives no performance
credit. The A16/A20 149-digest comparison remains the sole diagnostic decision;
ordinary gates remain fail-closed. No protected result changes.

Frozen artifacts:

- launcher wrapper `efff9bf04d9b45afda80d0a80be8908c07901a51cc5e088f265cc54aebf5bffb`,
  generated source `76000b8c00eaf66ea735951e41f6233c64d7cd9af4317b8ea3194b5580d7ef35`;
- client wrapper `399546be606a48170f6b00dc6968cf7dabe75f2b0a4233f1d96accf8840f066f`,
  generated source `ad98b16cf2089790f57f85a9ad2d1fc618aeff7fd9164a91d844d4669c0f56c2`;
- supervisor wrapper `f12be3ddbc88d9d623f23ac54f73e528691b79ccd1eb33753ad7a70ab0e52009`,
  generated source `87e80a6ce1db88535738a2d89daba23439c5fd32a30e334569ead22addd4f691`.

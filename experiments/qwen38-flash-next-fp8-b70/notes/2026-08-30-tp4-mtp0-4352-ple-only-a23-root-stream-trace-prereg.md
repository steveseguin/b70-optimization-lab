# Qwen3.8 Flash-Next FP8 A23 root-stream trace preregistration

Date: 2026-08-30
Status: frozen before a fresh-boot GPU launch

A23 is the corrected successor to the bounded A22 loader-validation negative.
It uses attempt 23, port 19695, isolated run/cache/RPC/evidence paths, and vLLM
source `f69a0ef46338f93636671c87caa527b3ac2ca129`. It retains the exact validated
external checkpoint, TP4/EP4 eager MTP0, PLE-only 12.0 GiB UVA placement, 4352
capacity, 64-token batch cap, 134217728-byte KV cache, seed, disabled prefix
cache, request order, quality helper, authority hashes, kernel head, staged
runtime, and all-rank internal trace boundaries from A22. No forward arithmetic,
allocation, graph, scheduler, or performance selector changed.

The only source correction is load-time validation. PLE shard coverage begins
before the root `Qwen4ExpForConditionalGeneration` loader, accumulates across
all child-prefix calls, and finalizes after the root checkpoint stream. An
active empty session fails, as do partial, duplicate, and unexpected indices;
the checkpoint's actual 126+2 delivery passes. Twenty-one PLE tests and four
root/offload tests pass, along with ruff, formatting, syntax, and diff checks.
Independent review found no blocker. Patch 0023 remains preserved as the failed
boundary; patch 0026 is the corrected successor.

The evidence wrapper also corrects A22's stale `diagnostics=none` receipt. A23
requires `diagnostics=qwen4exp-ple-inner-trace-rank-all` in `identity.txt`, the
client summary, and the supervisor gate. A nonblocking lock makes the
check-and-mark boot claim atomic. The marker is deliberately written before
inner preflights, so any launch attempt conservatively consumes that boot.

A23 is forbidden on A22's consumed boot
`c9c86120-4735-4f7a-9500-d7e49f0d2f63`. It must run after another explicit
host reboot, against the external artifact, as the only full Flash-Next load in
that boot. The external load may make SSH/UI unresponsive for 10-15 minutes
through reclaim and swap pressure; that is not by itself a failure. The bounded
supervisor and post-run evidence determine outcome.

Frozen interpretation:

- a pre-endpoint stop remains infrastructure or loader evidence only;
- an emitted four-rank trace makes A23 the first member of the internal pair;
- first divergence among raw/dequantized lookup, projection/gate, convolution,
  attention, or MLP boundaries identifies the next bounded treatment;
- internally matching ranks or a complete battery still require an independent
  A24 fresh-start trace before promotion;
- all diagnostic timings receive no performance credit and every protected
  result remains unchanged.

Frozen wrappers and generated sources:

- launcher `9194d3065d2c6ad1fd0e86e6054d0dd398f3d2510f098090c0c06562bfe04874`,
  generated `8b8b9166f54d89808d7b7b6d9708ede0e61c0e88dd2cfa75edca7834bbc14eee`,
  inner derived `7ffd700cce21da36173ea795366a01de845694c0b61781f7a421a808dd19df91`;
- client `04cee0d187065cdbcbd3a24195163f93e448c465324b71488bf4720c06fd9f8d`,
  generated `91389d2ca017dd3f0d657b1a5822426780a22c47b9541038b4640a077286ed80`,
  inner derived `aa24172f7f22f46524f29bfcbd6a2dec94a0dfc0299df666bd13c31d3b9f1c7c`;
- supervisor `8c4311a6dfe1fbd1f15d599119ae345ba6bdb7c2ee81cdecc41454fa74182ed3`,
  generated `0d529335ef8ae3d450c4a50519210e45100eeffaa89d2e01b8aeebf79146b623`,
  inner derived `0a08c20662b0e031e4a2c222219e4d8d4e5cf20ffa37a7a1163d2190648ddc49`.

# Qwen3.8 Flash-Next FP8 A24 local-NVMe inner-trace preregistration

Date: 2026-08-30
Status: frozen before GPU launch

The first supervisor invocation stopped before the launch wrapper because its
generated wrapper/client filenames omitted the literal `-local` suffix. No A24
attempt marker, run directory, model read, or GPU process was created. The two
references and their dependent hashes were corrected before the launch gate;
the initial committed version remains in Git history. No model, runtime,
inference, quality, or trace field changed.

A24 is the local-checkpoint successor to the unrun external-checkpoint A23.
It retains vLLM `f69a0ef46338f93636671c87caa527b3ac2ca129`, the staged runtime and
kernel identities, TP4/EP4 eager MTP0, PLE-only 12.0 GiB UVA placement, 4352
capacity, 64-token batch cap, 134217728-byte KV cache, seed, disabled prefix
cache, request order, quality helper, authority hashes, and all-rank internal
trace boundaries. It changes only attempt 23/port 19695 to attempt 24/port
19696, isolated lifecycle/evidence/cache paths, and the checkpoint/tokenizer
location from the validated USB copy to the identically verified local tree at
`/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`.

The location change follows the 2026-08-30 removal of three verified older
local model copies. Internal free space increased from 100,875,149,312 to
247,405,604,864 bytes. Flash-Next's config and index hashes remained exact.
This avoids the approximately 583-second external load; prior local loads
completed in roughly 71--80 seconds.

A22 already attempted a load in this boot but stopped safely during loader
validation, before an endpoint or request. The user explicitly authorized this
local retry. A24 is therefore frozen to boot
`c9c86120-4735-4f7a-9500-d7e49f0d2f63` and requires the A22 boot marker,
`MemAvailable >= 120000000 KiB`, `SwapFree >= 8000000 KiB`, at least
220000000000 free NVMe bytes, and a new exclusive A24 attempt marker. Failure
of any gate stops before model launch. The supervisor remains responsible for
bounded teardown and evidence capture.

Frozen interpretation:

- a pre-endpoint stop is infrastructure or loader evidence only;
- an emitted four-rank trace makes A24 the first member of the corrected
  internal trace pair;
- the first differing PLE-internal boundary determines the next bounded
  treatment;
- a matching trace or complete battery still requires a fresh-start replica
  before promotion;
- diagnostic timings receive no performance credit and all protected results
  remain unchanged.

Frozen wrappers and generated sources:

- launcher `23afbb401bc0ad15403e20e734ce5b5d9f4095b95a29e641a85e292659bbcff6`,
  generated `bbfe3122d059c163aa6d03317b364f69059cde95e75cb666e29f0e27c01174af`,
  inner derived `eaa798bbe327bc1aea749cf8c47e9246c410637ea7bfef7a740350eca0100a30`;
- client `b485d3c98a448f09c7a2d0e2c3a69e93ea52aedc1bbe3e27314a058184e6715f`,
  generated `e98715a47fe8054ac93da324be7da96f7793935ee24c334db54a266dc356b6de`,
  inner derived `fda62b148177e7b5df43a9a812ddae39ef10cda9981fc8ea5a576f6d00f573be`;
- supervisor `e80d4e2248655f4a634f3b23561afb6873798fc21240eba9c4d7b9844e36839f`,
  generated `d4b8631f816f0105d358a58cb4124c5ae21dd948729255db0dfd81f1b9e0e568`,
  inner derived `8f34100d66f0d3f2b0f460a9f4cf857b56a43d6c2954b017c36b63eb644a6b65`.

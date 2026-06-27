# Adaptive MTP Depth Cap Patch Snapshot

Status: negative / preserved for reference. Do not promote as a record patch.

Patch:

```text
patches/gemma4-26b-a4b-q8-b70/20260627T1856-llamacpp-adaptive-mtp-dpnmax-negative.patch
sha256 08132eefce96f341ec1e1c498d32963ba72c92798d9698bdfd84c6ef75c783af
```

Source tree:

```text
/home/steve/src/llama.cpp-gemma-record-repro-c926
base commit: c926ad098
```

What it contains:

- existing local Gemma 26B Q8 llama.cpp performance patches in the working
  tree;
- default-off server adaptive MTP controls:
  `LLAMA_SPEC_ADAPTIVE_MTP`, `LLAMA_SPEC_ADAPTIVE_MTP_WARMUP`,
  `LLAMA_SPEC_ADAPTIVE_MTP_LOW_N_MAX`, `LLAMA_SPEC_ADAPTIVE_MTP_LOW`,
  `LLAMA_SPEC_ADAPTIVE_MTP_HIGH`, `LLAMA_SPEC_ADAPTIVE_MTP_ALPHA`;
- an MTP `dp.n_max` fix so per-request depth caps stop draft generation early
  rather than only truncating generated drafts later.

Strict realistic validation:

```text
experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T1841-realistic-adaptive-mtp-dpnmax.md
```

Result:

- all v13/v14 runs passed the realistic gate and had `cached_tokens=0`;
- best adaptive row was `83.34212495239542 tok/s` median100;
- current strict record remains `87.61145306230438 tok/s`;
- no LocalMaxxing submission.

Keep this patch so future agents do not repeat this adaptive-depth lane without
a materially different design.

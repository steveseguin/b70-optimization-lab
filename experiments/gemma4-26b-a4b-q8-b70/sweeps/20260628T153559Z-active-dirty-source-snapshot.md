# 2026-06-28 Active Dirty Source Snapshot

Purpose: preserve the active llama.cpp Gemma/B70 source state before more
optimization edits. This is a source-state artifact, not a promoted result.

## Source Identity

- Source tree: `/home/steve/src/llama.cpp-gemma-record-repro-c926`
- Base commit: `c926ad09857517978575d6a74d225b463f7417a0`
- Capture time: `20260628T153559Z`
- Patch artifact:
  `patches/gemma4-26b-a4b-q8-b70/20260628T153559Z-active-dirty-source-snapshot.patch`
- SHA256:
  `6698774e77908208224d8c4a9fb408a62789f1473d08647be0cda32cc393dea1`
- Size: `578779` bytes, `13270` lines

## Verification

The patch was written with:

```bash
git diff --binary --output=/home/steve/qwen36-results-main/patches/gemma4-26b-a4b-q8-b70/20260628T153559Z-active-dirty-source-snapshot.patch
```

It was checked against the live dirty tree with:

```bash
git apply --check --reverse /home/steve/qwen36-results-main/patches/gemma4-26b-a4b-q8-b70/20260628T153559Z-active-dirty-source-snapshot.patch
```

That reverse-check passed. No patch was applied or reversed during this
snapshot. The active source tree remained dirty after capture.

## Dirty Files

```text
 M common/sampling.cpp
 M common/speculative.cpp
 M common/speculative.h
 M ggml/include/ggml-rpc.h
 M ggml/include/ggml.h
 M ggml/src/ggml-backend-meta.cpp
 M ggml/src/ggml-cpu/ggml-cpu.c
 M ggml/src/ggml-cpu/ggml-cpu.cpp
 M ggml/src/ggml-cpu/ops.cpp
 M ggml/src/ggml-cpu/ops.h
 M ggml/src/ggml-sycl/common.hpp
 M ggml/src/ggml-sycl/ggml-sycl.cpp
 M ggml/src/ggml-sycl/mmvq.cpp
 M ggml/src/ggml-sycl/mmvq.hpp
 M ggml/src/ggml-sycl/norm.cpp
 M ggml/src/ggml-sycl/norm.hpp
 M ggml/src/ggml-sycl/presets.hpp
 M ggml/src/ggml-sycl/quants.hpp
 M ggml/src/ggml.c
 M include/llama.h
 M src/llama-context.cpp
 M src/llama-context.h
 M src/llama-cparams.h
 M src/llama-ext.h
 M src/llama-graph.cpp
 M src/llama-graph.h
 M src/models/gemma4-assistant.cpp
 M src/models/gemma4.cpp
 M tools/server/server-context.cpp
```

## Diff Stat

```text
 common/sampling.cpp              |  218 +-
 common/speculative.cpp           |  815 +++++++-
 common/speculative.h             |    3 +
 ggml/include/ggml-rpc.h          |    4 +-
 ggml/include/ggml.h              |  116 ++
 ggml/src/ggml-backend-meta.cpp   |   21 +
 ggml/src/ggml-cpu/ggml-cpu.c     |   49 +
 ggml/src/ggml-cpu/ggml-cpu.cpp   |   23 +
 ggml/src/ggml-cpu/ops.cpp        |  486 +++++
 ggml/src/ggml-cpu/ops.h          |    9 +
 ggml/src/ggml-sycl/common.hpp    |   25 +
 ggml/src/ggml-sycl/ggml-sycl.cpp | 4291 ++++++++++++++++++++++++++++++++++----
 ggml/src/ggml-sycl/mmvq.cpp      | 2070 +++++++++++++++++-
 ggml/src/ggml-sycl/mmvq.hpp      |  216 ++
 ggml/src/ggml-sycl/norm.cpp      |  311 +++
 ggml/src/ggml-sycl/norm.hpp      |    4 +
 ggml/src/ggml-sycl/presets.hpp   |    2 +-
 ggml/src/ggml-sycl/quants.hpp    |    9 +-
 ggml/src/ggml.c                  |  337 ++-
 include/llama.h                  |    2 +
 src/llama-context.cpp            |  495 ++++-
 src/llama-context.h              |   31 +
 src/llama-cparams.h              |    5 +
 src/llama-ext.h                  |   14 +
 src/llama-graph.cpp              |  618 +++++-
 src/llama-graph.h                |   11 +-
 src/models/gemma4-assistant.cpp  |  267 ++-
 src/models/gemma4.cpp            |  256 ++-
 tools/server/server-context.cpp  |  560 ++++-
 29 files changed, 10578 insertions(+), 690 deletions(-)
```

## Notes For The Next Agent

- Use this patch to recover or compare the active dirty source state before
  additional edits.
- From a clean checkout at `c926ad09857517978575d6a74d225b463f7417a0`, apply
  the artifact with `git apply`.
- In the current dirty checkout, `git apply --reverse` would remove this
  snapshot's changes. Do not do that unless intentionally reverting the active
  experiment state.
- The snapshot does not include result-repo documentation changes or data
  artifacts; it is only the active llama.cpp source diff.

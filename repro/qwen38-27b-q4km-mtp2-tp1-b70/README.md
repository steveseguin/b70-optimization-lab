# Qwen3.8 27B Q4_K_M + Q4_0 MTP2 on one Arc Pro B70
> **Candidate portable reproduction.** The strict one-user headline is
> `42.636988 tok/s`, from two fresh full-suite servers. It is 55.75% faster
> than the identical-build MTP0 control and matches all 12 complete target
> token arrays. Clean-host Intel/oneAPI installation remains unverified.

This is a separate deployment from the target-only Q4 package. It requires
both the 18.97 GB target and a 1.37 GB external MTP draft.

## Exact downloads

```bash
huggingface-cli download ggml-org/Qwen3.8-27B-GGUF \
  Qwen3.8-27B-Q4_K_M.gguf \
  --revision 0669b98607d47046c7c2b3f801011d54a08cfccf \
  --local-dir /path/to/qwen38-target

huggingface-cli download unsloth/Qwen3.8-27B-GGUF \
  MTP/mtp-Qwen3.8-27B-Q4_0.gguf \
  --revision 4ca720788d1e01f1bff70c033e0d0028fd02e502 \
  --local-dir /path/to/qwen38-draft-root
```

Set `DRAFT_DIR=/path/to/qwen38-draft-root/MTP`. The target SHA-256 is
`31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34`;
the draft is
`50d9ce5a6da381bbcfb31061cf73df94a90e6faf8efeddee379a9cb8f1501c6e`.
Both are checked through direct and ordinary reads before launch.

## Source and patches

Build the exact lab stack in a new directory:

```bash
SOURCE_DIR=/path/to/new/llama.cpp-qwen38-mtp2 \
  repro/qwen38-27b-q4km-mtp2-tp1-b70/restore-and-build.sh
```

The builder verifies and applies, in order:

1. [Full Intel SYCL lab stack](../../patches/qwen36-27b-q8-tp2-asrock-b70/llama-cpp-mndodd-4302fb599-lab-tp2-dp4a2-20260815.diff.gz.b64).
2. [Qwen3.8 Q4_K_M increment](../../patches/qwen38-27b-q4km-tp2-asrock-b70/llama-cpp-q4k-mmvq-swiglu-tp2-20260815.diff.gz.b64).
3. [TP1 GDN state-I/O widening](../../patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-gdn-state-io-widen-20260821.diff.gz.b64).
4. [TP1 convolution/QK widening](../../patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-conv-qk-widen-20260821.diff.gz.b64).
5. [TP1 QK source-shape widening](../../patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-qk-norm-rope-src-widen-20260821.diff.gz.b64).
6. [Memo hardening artifact](../../patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-q8out-rejected-memo320-20260821.diff.gz.b64); its rejected Q8-output door stays disabled.

The exact measured binary SHA-256 was
`35f2d2327f05f42feb40f1a015ff46791e7277771ed97653f085be05a6f2c545`
and `libggml-sycl.so` was
`0e7789313ac5776b197da813d482f78e2f396620cc745af0f9c1bb2ec39bd154`.
A locally rebuilt binary is a distinct identity until its validation passes.

## Preflight, launch, and validate

```bash
export TARGET_DIR=/path/to/qwen38-target
export DRAFT_DIR=/path/to/qwen38-draft-root/MTP
export BUILD_DIR=/path/to/new/llama.cpp-qwen38-mtp2/build-sycl-aot-bmg-g31

repro/qwen38-27b-q4km-mtp2-tp1-b70/preflight.sh
repro/qwen38-27b-q4km-mtp2-tp1-b70/run-server.sh
```

In a second terminal:

```bash
OUT_DIR=/path/to/new-qwen38-mtp2-result \
  repro/qwen38-27b-q4km-mtp2-tp1-b70/bench.sh
```

Success requires the full twelve-prompt/six-class 512-cap suite, cache zero,
all objective canaries, and `target_arrays_exact=12/12`. A speed printed by a
failed gate is not a result.

## Why depth 2

| MTP depth | strict tok/s | target-exact | decision |
| ---: | ---: | ---: | --- |
| 0 | 27.376 | 12/12 | matched control |
| 1 | 38.320 | 12/12 | valid |
| 2 | **42.637** | 12/12 | two-server winner |
| 3 | 42.123 | 12/12 | valid, slower |
| 5 | 32.241 | **0/12** | rejected |

See the [structured result](../../experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q4km-q4mtp-tp1-mtp2-strict-result.json)
and [result note](../../experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-q4km-q4mtp-tp1-mtp2-strict-result.md).
MTP5 is not an optional speed preset; it changed all twelve outputs.

## Current boundary

The measured headline is single-user and short-context. The separate
mixed-content exact-depth sweep used unrepeated technical prose, Python code,
and structured documentation at six exact depths. Each published point is the
median of the three classes and then the median of two fresh servers. At 32K
it measured `36.505065 tok/s` and `39.538 s` TTFT. All **36/36** MTP2 outputs
matched the fresh same-build MTP0 oracle; all 54 target/control/speculative
requests reported cache zero, no truncation, and complete 128-token streams.
See the [structured result](../../experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q4km-q4mtp-tp1-mixed-content-depth-r1-result.json),
[frozen fixture](../../data/qwen27-exact-depth/qwen38-bce40ca-mixed-content-depth-v1.json),
and [campaign runner](../../experiments/qwen38-27b-b70/scripts/run-20260827-qwen38-q4km-q4mtp-tp1-mixed-content-depth-arm.sh).

This is representative real-content context-shape evidence, not a natural
retrieval/task suite. The older repeated-token diagnostic still diverged from
MTP0 at generated token 23 at 2K, so target parity remains workload-scoped and
is not a universal claim. The no-MTP concurrency curve does not transfer.

To replay one MTP2 mixed-content arm after completing the exact build above:

```bash
TARGET_DIR=/path/to/qwen38-target \
DRAFT_DIR=/path/to/qwen38-draft-root/MTP \
BUILD_DIR=/path/to/new/llama.cpp-qwen38-mtp2/build-sycl-aot-bmg-g31 \
OUT_DIR=/path/to/new-mixed-content-result \
ARM=mtp2 ATTEMPT=local-r1 PORT=18140 \
  experiments/qwen38-27b-b70/scripts/run-20260827-qwen38-q4km-q4mtp-tp1-mixed-content-depth-arm.sh
```

The runner intentionally requires the measured binary hashes, clean synced
repository state, direct model verification, frozen fixture, and committed
MTP0 oracle. A locally different rebuild is a new runtime identity and needs a
new matched control rather than bypassing those checks.

The directly measured MTP2 serving profile is 16 slots with `--ctx-size 8192`
(512 nominal context tokens per slot). Across two fresh servers, aggregate
decode measured 34.893/41.255/52.355/47.914/**68.341 tok/s** at
1/2/4/8/16 concurrent users. All throughput requests returned 128 uncached raw
token IDs, output isolation passed, and 256/256 separate 16-way exact-answer
canaries passed. Multi-user greedy output is batch-shape-dependent, so it is
not a token-identity claim. Attempts at 32 slots/16K total and 64 slots at both
16K and 32K total failed startup with device OOM; do not advertise more than
16 active MTP2 users on one B70 from this evidence. The exact commands and raw
receipts are linked from the [concurrency result](../../experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-q4km-q4mtp-tp1-mtp2-http-concurrency-r2-result.md).

The tested small host had 16 GiB RAM plus swap; the launcher caps the scope at
13 GiB RAM and 12 GiB swap. Stop competing model processes before launch.

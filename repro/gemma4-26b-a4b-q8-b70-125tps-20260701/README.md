# Gemma 4 26B A4B Q8 on 1x B70, 125 tok/s

> **Certification: `candidate-portable-repro`, not a starter guide.** Install,
> restore, launch, and validation material is closed for the lab's own hosts;
> clean-host certification is still pending. The open items are listed under
> this guide's `missing` entry in [`repro/guide-catalog.json`](../guide-catalog.json).

This is the standalone promoted reproduction packet for the current Gemma 4
26B A4B Q8/INT8-quality short-decode record on one Intel Arc Pro B70.

> **Reconstruction status (2026-08-22):** the exact aggregate source snapshot
> now applies cleanly to its pinned base, but the historical server binary hash
> and local Q4_0 draft hash were not retained. This packet is therefore a
> source-verified reconstruction candidate, not yet a clean-host beginner
> install or a byte-identical historical replay.

Use the active script packet for day-to-day reruns:

- `../gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh`
- realistic suite:
  `../gemma4-26b-a4b-q8-b70/realistic-suite-v1.json`
- full result packet:
  `../../results/gemma4-26b-a4b-q8-b70/README.md`
- detailed reproduction notes:
  `../../results/gemma4-26b-a4b-q8-b70/reproduce.md`
- [canonical aggregate patch and verification receipt](../../patches/gemma4-26b-a4b-q8-b70/README.md);
- [pinned model identities](model-manifest.json).

## Headline Result

- Primary metric: `124.97714084813418 tok/s` median generated-token throughput
  for streamed tokens 1-100 after TTFT.
- Suite: fixed realistic cold prompt suite, 12 unique prompts, each prompt run
  once.
- Output length: `MAX_TOKENS=512`.
- Context limit: `CTX_SIZE=32768`.
- Cache policy: `cached_tokens=0` on every request; no prompt/KV/context
  checkpoint/response reuse, no n-gram or history acceleration.
- Quality lane: UD-Q8_K_XL target/verifier with Q4_0 MTP draft; all accepted
  speculative tokens are verified by the Q8 target.
- Canary: `512/512` chat canary rows passed.
- LocalMaxxing ID: `cmr1u77na01k2ld01kalwzs1e`.
- Evidence:
  `../../data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json`.

Record metrics from the evidence JSON:

| Metric | Value |
| --- | ---: |
| median tok/s, tokens 1-100 after TTFT | `124.97714084813418` |
| p10 tok/s, tokens 1-100 after TTFT | `103.83610041293295` |
| mean tok/s, tokens 1-100 after TTFT | `122.4743547166875` |
| median TTFT | `178.6938319564797 ms` |
| median full512 after-TTFT tok/s | `114.87107033590775` |
| median wall full512 tok/s | `108.58112847853889` |

Same-family support rows include `123.67689864739785`,
`121.59076340768573`, `121.41411987308553`, `119.94842631460949`,
`119.26425148518223`, and `113.63257982764395 tok/s`. This lane has several
percent run-to-run variance, so close comparisons require same-window controls.

Latest reproducibility check while creating this packet:

- run:
  `../../data/gemma4-q8-gpu0-125repro-docpass-20260702T231635Z/summary.json`;
- validity: `realistic_final_gate.passed=true`,
  `fresh_response_validity.valid=true`, `cached_tokens=0` on all 12 prompts,
  `512/512` canary rows passed;
- metric: `120.92334534956485 tok/s` median generated-token throughput for
  tokens 1-100 after TTFT, p10 `105.95927439380908`, mean
  `118.86003674156144`, median full512 after-TTFT `112.61378328154639`,
  median wall full512 `107.50910206155777`, median TTFT
  `177.91116051375866 ms`;
- interpretation: valid same-recipe support run, not a new record. It
  reproduces the promoted path and validity gate, while landing within the
  known several-percent run-to-run spread below the `124.977` high.

## Runtime Identity

- Host: one Intel Arc Pro B70 32 GB replica per run; the lab has four B70s and
  used them for parallel same-window A/B screens and cross-over checks.
- Source: llama.cpp `c926ad098` plus the local Gemma record stack.
- Active source checkout:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926`.
- Record build:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server`.
- Target model:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`.
- Draft model:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`.
- KV cache: `f16` target and draft.
- FlashAttention: on.
- VMM: on.
- Speculation: draft-MTP, `n_max=3`, `n_min=2`, `p_min=0.0475`.

## Restore The Record Source

The old lab checkout paths below document history; new users should not create
or edit those paths. Restore a new source directory from the in-repository
aggregate instead:

```bash
cd /path/to/b70-optimization-lab
SOURCE_DIR=/path/to/new/llama.cpp-gemma4-record \
  repro/gemma4-26b-a4b-q8-b70-125tps-20260701/restore-and-build.sh
```

The helper clones official llama.cpp tag `b9769`, verifies full base commit
`c926ad09857517978575d6a74d225b463f7417a0`, decodes and hash-checks our
canonical aggregate patch, applies it, runs `git diff --check`, and builds with
the record's VDR2 compile definition. The embedded browser UI and its remote
prebuilt-asset fetch are disabled so a changed web bundle cannot break or
silently alter the API-server reconstruction; the record workload used the
HTTP API, not that UI. The helper refuses to overwrite an existing source
directory and defaults to the historical oneAPI 2026.0 compiler paths.

The downloadable target and F16 MTP source are pinned in
`model-manifest.json`. Download them from revision
`3bb10d594514ef4edb7f3a65d41a7e4eb8c5767a` of
`unsloth/gemma-4-26B-A4B-it-GGUF`, verify their manifest hashes, then reconstruct
the local record draft:

- [UD-Q8_K_XL target/verifier](https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/resolve/3bb10d594514ef4edb7f3a65d41a7e4eb8c5767a/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf?download=true)
- [F16 MTP draft source](https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/resolve/3bb10d594514ef4edb7f3a65d41a7e4eb8c5767a/MTP/gemma-4-26B-A4B-it-F16-MTP.gguf?download=true)

Both are large-file objects; use a resumable downloader and keep the exact
filenames. `preflight.sh` checks the target SHA-256, while `prepare-draft.sh`
checks the F16 source SHA-256 before quantizing it.

```bash
F16_DRAFT=/models/MTP/gemma-4-26B-A4B-it-F16-MTP.gguf \
MTP_DRAFT_MODEL=/models/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf \
LLAMA_QUANTIZE=/path/to/new/llama.cpp-gemma4-record/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-quantize \
  repro/gemma4-26b-a4b-q8-b70-125tps-20260701/prepare-draft.sh
```

Save the printed `DRAFT_SHA256`. It pins the reconstructed draft for a run,
but it does not retroactively prove byte identity with the lost historical
local draft. The 2026.1.1 compatibility build produced a repeat-stable
reference (`3/3` byte-identical quantizations): `321126560` bytes,
SHA-256 `1f6706e4a09524c7aa83cea45eec637cd3e2aa7ccfa80c2dbef7a092ec0fddbd`.
The helper reports whether a new output matches that reference.

Important flags:

```text
GGML_SYCL_ENABLE_VMM=1
FLASH_ATTN=on
CTX_SIZE=32768
UBATCH_SIZE=1024
LLAMA_SYCL_F16_P021_SMALL_NCOLS=1
LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1
LLAMA_MTP_DEFER_TARGET_H_NEXTN=1
LLAMA_MTP_DRAFT_FAST_ARGMAX=1
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7
LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1
LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1
LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1
LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1
LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1
LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1
LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1
```

## Reproduce

The wrapper below runs the strict final gate. Pick a free GPU/port pair.

```bash
cd /path/to/b70-optimization-lab
LLAMA_SERVER=/path/to/build/bin/llama-server \
MODEL=/models/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf \
MTP_DRAFT_MODEL=/models/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf \
DRAFT_SHA256=<sha256-printed-by-prepare-draft> \
GPU_INDEX=0 PORT=19350 \
  CTX_SIZE=32768 FLASH_ATTN=on GGML_SYCL_ENABLE_VMM=1 \
  CANARY_REPEATS=128 MAX_TOKENS=512 \
  REALISTIC_GATE=1 REALISTIC_METRIC_TOKENS=100 \
  LABEL=gemma4-q8-gpu0-125repro-$(date -u +%Y%m%dT%H%M%SZ) \
  bash repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh
```

Equivalent local helper:

```bash
LLAMA_SERVER=/path/to/build/bin/llama-server \
MODEL=/models/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf \
MTP_DRAFT_MODEL=/models/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf \
DRAFT_SHA256=<sha256-printed-by-prepare-draft> \
GPU_INDEX=0 PORT=19350 \
  bash repro/gemma4-26b-a4b-q8-b70-125tps-20260701/run.sh
```

The run writes:

- `data/<LABEL>/summary.json`
- `data/<LABEL>/realistic-suite.json`
- `data/<LABEL>/chat-canary.json`
- server log under `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/`

Only promote or submit results when `realistic_final_gate.passed=true`,
`fresh_response_validity.valid=true`, and all `cached_tokens` values are zero.

## What Worked

- Use UD-Q8_K_XL as the target/verifier. The switch to `Q8_0` was not the
  quality-preserving headline lane.
- Keep the Q4_0 draft only as a verified MTP draft source. The Q8 target still
  verifies accepted tokens.
- Keep one full Gemma replica per B70 for research. Four independent GPUs were
  more useful than tensor-parallel PCIe sharing for this model.
- Reordered-Q8 VDR2 plus selected-down fused weighted-sum was the major
  target-side source win.
- `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`, bulk sampled-ID verifier host read,
  FA-on 32K/VMM, and final post-norm residual fusion each contributed to the
  promoted family.
- Use same-window A/B or cross-over runs for small changes. The record family
  has enough variance that single-run micro-claims are unreliable.

## What Did Not Count As Headline Throughput

- Synthetic filled-long rows, even when `cached_tokens=0`, are diagnostic only.
- Repeated-prompt or warmed n-gram/history rows are not fresh-response
  throughput.
- Prompt-processing and long-context service wins are separate from the short
  LocalMaxxing headline. They must pass their own exact long-context gates and
  then rerun the short guard to prove no decode regression.

## Variance And Fairness

The current reliability protocol measured same-GPU full512 repeats under
temperature telemetry and found several-percent natural spread without thermal
throttling. Active core stayed around `77-78 C`, memory around `86-90 C`, and
frequency stayed near max. The no-spec calibration workflow measured a p90
same-identity pairwise spread around `4.4%`; use the no-spec calibration
workflow or a four-GPU same-window A/B when a candidate lands inside that
range.

See:

- `../../results/gemma4-26b-a4b-q8-b70/reliability-protocol.md`
- `../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-finalpostnorm-thermal-variance.md`
- `../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-lmhead1col-subgroups.md`

## Prompt Processing And 32K Context

The short record uses `CTX_SIZE=32768`, `FLASH_ATTN=on`, and VMM, but it is
still a short-decode headline. The validated service/prompt-processing recipe
is tracked separately:

- `../gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh`
- `../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-current-service-context-ladder.md`
- `../../data/gemma4-long-context-service-gate-20260702Tservice-ladder-current-rep4.json`

That service recipe uses `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`,
SWA left-bound, KQ register/broadcast, phase prefill ubatch `2048`, 32K
context, FA on, and VMM. It passed exact long-context JSON validation with
`cached_tokens=0`, but it is not a short-decode record replacement.

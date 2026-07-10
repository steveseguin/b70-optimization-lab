# ReplaySSM transaction fusions (2026-07-10)

## Status

Validated incremental optimization, not a headline record.

- Current valid headline remains `68.23626314761921 tok/s`.
- The cooled full-quality candidate confirmation reached
  `68.16353882227102 tok/s`, so it was not submitted to LocalMaxxing.
- Across three card-balanced four-GPU rounds, the candidate produced a real
  mean improvement of `+1.3948%` with prompt-cluster bootstrap 95% CI
  `[+0.6276%, +2.5463%]`; 11 of 12 prompt-level effects were positive.
- Exact cases, repeat64, 1K context, and baseline matching all passed twice.

This result is worth retaining as a quality-safe component of a larger
transaction fusion, but it is too small to be the route from 68 to 100 tok/s.

## Candidate

Two default-off changes were tested together and separately:

1. `VLLM_XPU_GDN_REPLAYSSM_FUSE_PENDING_METADATA=1`
   writes `pending[slot]=1` and `pending_len[slot]=spec_len` inside the native
   ReplaySSM recurrent kernel, replacing the Python `index_fill_` and
   `index_copy_` sequence.
2. `VLLM_XPU_GDN_REPLAYSSM_DIRECT_CORE_OUT=1`
   writes pure-spec recurrent output directly into the final GDN output view,
   avoiding one temporary allocation and output copy.

The native stage-conv BF16 product rounding was also restored to
`static_cast<float>(T(x * w))`. This is required to match
`causal_conv1d_update`; the promoted-FP32 product variant has failed endpoint
canaries historically.

The working source is captured in:

- `patches/qwen36-27b-autoround-int4-b70/vllm-active-with-replayssm-transaction-fusions-20260710.patch`
- `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-kernels-active-with-replayssm-transaction-fusions-20260710.patch`

These are full active-stack snapshots because both source repos already
contained valuable uncommitted Qwen work. The corresponding pre-change
snapshots are under `patches/qwen36-27b-autoround-int4-b70/source-snapshots/`
with timestamp `20260710T014958Z`.

## Native guards

Both guards passed before any endpoint was started:

- stage-conv bitwise parity: Q/K/V, A/B, `conv_pending`, and unchanged
  `conv_state` all had zero differing elements at the real Qwen shape;
- recurrent parity: output and ReplaySSM caches stayed within the established
  tolerances, while `pending` and `pending_len` matched exactly.

Artifacts:

- `data/qwen36-27b-autoround-int4-b70-profiles/replayssm-transaction-20260710/stage-conv-bitwise-parity.json`
- `data/qwen36-27b-autoround-int4-b70-profiles/replayssm-transaction-20260710/spec-pending-metadata-parity.json`

The isolated extension was built for `bmg-g21-a0` with oneAPI 2025.3 and had
SHA-256 `4d01751ec1e15062973a74269ae512b1c71e82bb5595d26193d0cdd42b4aae08`.
The binary itself is intentionally outside Git.

## Four-GPU screen and crossover

All rows used the fixed realistic suite, one cold request per prompt,
`cached_tokens=0`, no prompt/KV/history reuse, target-verified MTP3, and the
same target model and quantization.

Initial screen medians:

| Lane | Median tok/s | p10 | Classification |
| --- | ---: | ---: | --- |
| control | 67.5761 | 60.3926 | strict-fresh diagnostic |
| pending metadata | 67.5539 | 63.0904 | neutral median |
| direct output | 67.6651 | 60.6402 | within noise |
| both | 67.7654 | 64.2095 | promising, needed crossover |

The combined lane improved 11/12 prompts in the first paired view, but its
95% interval still crossed zero. Two reversed assignment rounds then balanced
candidate and control over all four GPUs and start-order positions.

Card-balanced result:

- mean relative effect: `+1.3947727392%`;
- median prompt effect: `+0.9003835076%`;
- 95% prompt-cluster bootstrap CI: `[+0.6276134568%, +2.5462970681%]`;
- balanced raw means: `67.09985 -> 68.00900 tok/s` (`+0.90915`);
- positive prompt effects: 11/12.

Full analysis and round summaries:

- `data/qwen36-27b-autoround-int4-b70-profiles/replayssm-transaction-20260710/card-balanced-analysis.json`
- `data/qwen36-27b-autoround-int4-b70-profiles/replayssm-transaction-20260710/screen-round1-summary.json`
- `data/qwen36-27b-autoround-int4-b70-profiles/replayssm-transaction-20260710/crossover-round2-summary.json`
- `data/qwen36-27b-autoround-int4-b70-profiles/replayssm-transaction-20260710/crossover-round3-summary.json`

This is why the old fixed acceptance threshold was retired: the candidate is
small but statistically real. It still must not be described as a new record,
because its promoted confirmation did not beat the existing headline.

## Full quality confirmations

Two full gates used the identical isolated binary and flags:

| GPU | Median tok/s | p10 | Quality |
| --- | ---: | ---: | --- |
| 0 | 66.3166 | 57.7106 | exact + repeat64 + 1K + baseline match pass |
| 2, cooled to 37 C | 68.1635 | 59.9951 | exact + repeat64 + 1K + baseline match pass |

The cooled GPU 2 run also measured:

- mean first-100 decode: `68.1699 tok/s`;
- median full512 decode: `66.7429 tok/s`;
- median wall-clock full output: `62.7705 tok/s`;
- median TTFT: `476.171 ms`.

The start telemetry and complete benchmark/quality payloads are retained under
`data/qwen36-27b-autoround-int4-b70-profiles/replayssm-transaction-20260710/`.

## Harness correction

The first endpoint attempt failed before serving because
`VLLM_XPU_KERNELS_SRC` changed the library path but did not put the isolated
Python package before the editable source checkout. Python therefore called
the new 25-argument wrapper against the old 22-argument extension schema.

The durable fix is to set both:

```bash
VLLM_XPU_KERNELS_SRC="$OVERLAY_ROOT"
PYTHONPATH="$OVERLAY_ROOT${PYTHONPATH:+:$PYTHONPATH}"
```

The harness now verifies this layout through the successful endpoint rounds.

## Reproduction

Build the isolated extension:

```bash
CLEAN=1 \
BUILD_DIR=/home/steve/src/vllm-xpu-kernels/build/qwen27-replayssm-transaction-20260710 \
INSTALL_PREFIX=/tmp/vllm-xpu-qwen27-replayssm-transaction-20260710 \
AOT_DEVICES=bmg-g21-a0 JOBS=8 GDN_KERNELS=ON \
bash scripts/build-vllm-xpu-kernels-xpu-c-only.sh
```

Run the initial screen and the two crossover assignments:

```bash
STAGGER_S=90 \
bash experiments/qwen36-27b-autoround-int4-b70/scripts/run-replayssm-transaction-screen-4gpu.sh

LAYOUT=crossover STAGGER_S=60 \
bash experiments/qwen36-27b-autoround-int4-b70/scripts/run-replayssm-transaction-screen-4gpu.sh

LAYOUT=crossover-reverse STAGGER_S=60 \
bash experiments/qwen36-27b-autoround-int4-b70/scripts/run-replayssm-transaction-screen-4gpu.sh
```

## Next kernel

The next credible step is a larger default-off commit-plus-stage transaction
kernel. It should:

1. load each dimension's old three-column causal-conv history and accepted
   pending prefix into registers;
2. write the committed history without the current in-place cross-work-item
   dependency;
3. loop all MTP3 positions in one `(row, dimension-group)` workgroup instead
   of launching one group per speculative position;
4. stage Q/K/V/A/B and new `conv_pending` rows;
5. update ring cursors once per row while leaving pending metadata for the
   already validated recurrent fusion.

That removes the separate commit kernel and reduces stage workgroups by about
4x at the real Qwen shape. It targets the several-millisecond transaction cost
needed before higher-acceptance branch/regenerate work can plausibly reach
100 tok/s.

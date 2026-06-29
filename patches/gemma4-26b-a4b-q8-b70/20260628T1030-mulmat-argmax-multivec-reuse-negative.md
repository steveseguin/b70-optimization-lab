# 2026-06-28T1030 - Multi-vector verifier LM-head argmax reuse (negative)

Status: **negative / not promoted**.

Source tree:
`/home/steve/src/llama.cpp-gemma-record-repro-c926`

Main source file:
`ggml/src/ggml-sycl/mmvq.cpp`

Experiment gate:

```bash
LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1
LLAMA_SYCL_MUL_MAT_ARGMAX_MULTI_REUSE=1
```

Optional tile sweep:

```bash
LLAMA_SYCL_MUL_MAT_ARGMAX_TILE_SUBGROUPS=16
LLAMA_SYCL_MUL_MAT_ARGMAX_TILE_SUBGROUPS=8
LLAMA_SYCL_MUL_MAT_ARGMAX_TILE_SUBGROUPS=4
LLAMA_SYCL_MUL_MAT_ARGMAX_TILE_SUBGROUPS=2
```

Patch idea:

- Add `ggml_sycl_mul_mat_argmax_multi_reuse_enabled()`.
- Add non-reordered and reordered `*_argmax_multi_reuse_tile` kernels for
  `nvec=2..8`.
- Launch one tile workgroup per vocab tile and compute all verifier vectors in
  that workgroup, instead of launching one tile per `(vocab tile, verifier row)`.
- Preserve the existing vector-major scratch layout and the existing final
  reducer/tie-breaking semantics.

Why it was tried:

The existing fused verifier LM-head argmax path was much slower than the
backend full-logits/argmax-ID path. The hypothesis was that it reread the same
LM-head tile once per verifier row and that reusing output-weight loads across
`nvec` rows would close the gap.

Results:

| Run | Median 1-100 | p10 | Full | Notes |
| --- | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-argmaxreuse-fused-correctenv-128/summary.json` | `99.512` | `84.874` | `100.302` | strict 128-token screen only |
| `data/gemma4-q8-gpu0-argmaxreuse-fused-full512-A/summary.json` | `97.424` | `92.494` | `89.693` | full512, valid |
| `data/gemma4-q8-gpu1-argmaxreuse-fused-full512-B/summary.json` | `97.604` | `87.745` | `93.468` | full512, valid |
| `data/gemma4-q8-gpu2-argmaxreuse-fused-full512-C/summary.json` | `90.438` | `84.935` | `89.860` | full512, valid |
| `data/gemma4-q8-gpu3-argmaxreuse-fused-full512-D/summary.json` | `96.615` | `88.756` | `94.122` | full512, valid |

Tile-subgroup follow-up:

| Run | Tile subgroups | Median 1-100 | p10 | Full128 |
| --- | ---: | ---: | ---: | ---: |
| `data/gemma4-q8-gpu0-argmaxreuse-fused-tile16-128/summary.json` | `16` | `95.029` | `87.896` | `95.433` |
| `data/gemma4-q8-gpu1-argmaxreuse-fused-tile8-128/summary.json` | `8` | `97.975` | `90.229` | `99.229` |
| `data/gemma4-q8-gpu2-argmaxreuse-fused-tile4-128/summary.json` | `4` | `98.294` | `85.104` | `98.011` |
| `data/gemma4-q8-gpu3-argmaxreuse-fused-tile2-128/summary.json` | `2` | `96.341` | `87.039` | `93.825` |

Decision:

Do not promote and do not submit to LocalMaxxing. The patch makes the old fused
verifier argmax path much less bad, but the full512 result is still below the
current strict record (`98.340`) and does not crack `100` reliably.

Future note:

Do not spend more time on small tile-geometry tweaks for this fused argmax
kernel. If revisiting LM-head work, target either a full-logits-compatible
compact-output path or a different target-body reduction before the LM head.

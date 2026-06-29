# Gemma 4 26B Q8: selected-softmax weighted-sum split-N negative

Date: 2026-06-28

Goal: reduce the verifier-side Gemma MoE boundary cost enough to make the
strict cold-suite median crack `100 tok/s` reliably.

Patch tested in `/home/steve/src/llama.cpp-gemma-record-repro-c926`:

- added
  `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_WEIGHTED_SUM_SPLIT=1`;
- kept compatibility with the earlier
  `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_WEIGHTED_SUM_SPLIT2=1`;
- changed the selected-softmax weighted-sum experiment from a top-2-only path
  to a generic split path for `ids->ne[0] <= 8` and `dst->ne[1] <= 8`;
- split the fused op into two kernels:
  - compute `[token, selected_expert]` softmax weights once into scratch;
  - run a simple row-wise weighted sum from the scratch weights.

Reason tried: the current verifier path commonly has `ids->ne[0] == 8`, so the
initial top-2-only split patch would likely not fire on the real Gemma verifier
shape. The split-N version tested the actual top-8 shape.

Strict 128-token realistic-suite screen, all with `cached_tokens=0`, chat
canary pass, UD-Q8_K_XL target/verifier, Q4_0 MTP draft, VDR2 reordered Q8,
F16 p021, bulk sampled-ID verifier, `n_max=3`, `n_min=2`, `p_min=0.0475`,
`UBATCH_SIZE=1024`:

| Lane | Extra env | Median 1-100 | p10 | Mean | Full128 | Wall128 | TTFT ms | Summary |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| GPU0 | control | `100.1695` | `85.8161` | `98.1327` | `96.5062` | `83.7734` | `180.562` | `data/gemma4-q8-gpu0-strict-vdr2-f16p021-bulksampled-splitN-control-n3-nmin2-p00475-ub1024-128-20260628T070112Z/summary.json` |
| GPU1 | `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_WEIGHTED_SUM=1` | `98.3930` | `87.3720` | `97.0656` | `97.4072` | `83.5196` | `181.584` | `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-splitN-selwsum-n3-nmin2-p00475-ub1024-128-20260628T070112Z/summary.json` |
| GPU2 | `SELECTED_SOFTMAX_WEIGHTED_SUM=1`, `..._SPLIT=1` | `95.5263` | `88.5347` | `95.6902` | `97.8619` | `84.5987` | `180.147` | `data/gemma4-q8-gpu2-strict-vdr2-f16p021-bulksampled-splitN-selwsum-splitN-n3-nmin2-p00475-ub1024-128-20260628T070112Z/summary.json` |
| GPU3 | split-N plus `LLAMA_GEMMA4_MOE_WEIGHTED_SUM_2D=1` | `93.9143` | `86.5461` | `95.3633` | `93.8036` | `83.3323` | `179.971` | `data/gemma4-q8-gpu3-strict-vdr2-f16p021-bulksampled-splitN-selwsum-splitN-wsum2d-n3-nmin2-p00475-ub1024-128-20260628T070112Z/summary.json` |

Decision: **reject and revert from active source**. The split-N path is correct
under the strict gate, but slower than the current control path. It likely loses
because the extra scratch allocation/kernel launch costs more than the saved
local softmax work at these tiny verifier shapes.

The control lane's `100.1695` is useful but not a promoted result: it is a
128-token screen and the full512 repeat history for this stack has not shown a
reliable `>100` median. Treat it as normal near-threshold variance unless a
full512 repeat campaign reproduces it.


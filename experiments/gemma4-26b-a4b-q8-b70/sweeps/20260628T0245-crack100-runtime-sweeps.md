# 2026-06-28T0245 - Crack-100 runtime sweeps

Goal: find a strict, fresh-response Gemma 4 26B A4B IT UD-Q8_K_XL config that
reliably clears `100 tok/s` median generated-token throughput for tokens 1-100
after TTFT, without changing model/quantization quality or using warmed/cache
history.

Current promoted record to beat:

- Promoted strict full512 record:
  `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-confirm-B-n3-nmin2-p00475-ub1024-full512-20260628T052158Z/summary.json`
- median100 `98.3405`, p10 `85.9794`, mean `95.9529`,
  full512-after-TTFT `91.1739`, wall full512 `87.7371`, TTFT median `180.2 ms`.

All runs below used the same target/verifier and draft model identity:

- target/verifier:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- fresh realistic suite, `cached_tokens=0`, no prompt/KV/history reuse,
  `--ctx-checkpoints 0`, f16 KV, flash-attn off, `n_max=3`, `n_min=2`
  unless noted.

## `p_min` full512 sweep (`20260628T024511Z`)

Four-way strict full512 screen:

- `p_min=0.0400`, GPU0:
  `data/gemma4-q8-gpu0-strict-vdr2-f16p021-pmin0040-n3-nmin2-p00400-ub1024-full512-20260628T024511Z/summary.json`
  median100 `97.5294`, p10 `87.4518`, mean `97.8201`, full512 `93.5772`.
- `p_min=0.0475`, GPU1:
  `data/gemma4-q8-gpu1-strict-vdr2-f16p021-pmin00475-n3-nmin2-p00475-ub1024-full512-20260628T024511Z/summary.json`
  median100 `97.4032`, p10 `90.8743`, mean `97.1165`, full512 `91.1108`.
- `p_min=0.0550`, GPU2:
  `data/gemma4-q8-gpu2-strict-vdr2-f16p021-pmin0055-n3-nmin2-p00550-ub1024-full512-20260628T024511Z/summary.json`
  median100 `93.7459`, p10 `83.9246`, mean `95.7345`, full512 `91.0528`.
- `p_min=0.0650`, GPU3:
  `data/gemma4-q8-gpu3-strict-vdr2-f16p021-pmin0065-n3-nmin2-p00650-ub1024-full512-20260628T024511Z/summary.json`
  median100 `99.2473`, p10 `83.6326`, mean `96.3151`, full512 `92.3874`.

Decision: no promotion. `p_min=0.0650` is closest on median but weak p10 and
prompt rows show it moves the slow prompts around rather than fixing them.

## Draft direct-argmax unroll sweep (`20260628T024815Z`)

Four-way strict full512 screen at `p_min=0.0475`:

- unroll 5:
  `data/gemma4-q8-gpu0-strict-vdr2-f16p021-unroll5-n3-nmin2-p00475-ub1024-full512-20260628T024815Z/summary.json`
  median100 `96.1251`, p10 `87.1974`, mean `96.9824`, full512 `92.4289`.
- unroll 6:
  `data/gemma4-q8-gpu1-strict-vdr2-f16p021-unroll6-n3-nmin2-p00475-ub1024-full512-20260628T024815Z/summary.json`
  median100 `99.9805`, p10 `87.0224`, mean `96.5554`, full512 `91.7185`.
- unroll 7 control:
  `data/gemma4-q8-gpu2-strict-vdr2-f16p021-unroll7-n3-nmin2-p00475-ub1024-full512-20260628T024815Z/summary.json`
  median100 `96.0366`, p10 `90.9210`, mean `96.8762`, full512 `91.4109`.
- unroll 8:
  `data/gemma4-q8-gpu3-strict-vdr2-f16p021-unroll8-n3-nmin2-p00475-ub1024-full512-20260628T024815Z/summary.json`
  median100 `93.4241`, p10 `89.0576`, mean `95.1488`, full512 `92.0005`.

Decision: unroll 6 is a near miss, not a promoted result. It touched `99.98`
once but p10 stayed weak and follow-up did not repeat above 100.

## Unroll 6 + `p_min` sweep (`20260628T025034Z`)

Four-way strict full512 screen:

- unroll6, `p_min=0.0400`:
  `data/gemma4-q8-gpu0-strict-vdr2-f16p021-u6-pmin0040-n3-nmin2-p00400-ub1024-full512-20260628T025034Z/summary.json`
  median100 `99.1355`, p10 `89.3486`, mean `97.9962`, full512 `91.6600`.
- unroll6, `p_min=0.0475`:
  `data/gemma4-q8-gpu1-strict-vdr2-f16p021-u6-pmin00475-n3-nmin2-p00475-ub1024-full512-20260628T025034Z/summary.json`
  median100 `97.5358`, p10 `87.4840`, mean `96.3441`, full512 `89.4183`.
- unroll6, `p_min=0.0550`:
  `data/gemma4-q8-gpu2-strict-vdr2-f16p021-u6-pmin0055-n3-nmin2-p00550-ub1024-full512-20260628T025034Z/summary.json`
  median100 `97.2252`, p10 `89.1706`, mean `97.3113`, full512 `90.0701`.
- unroll6, `p_min=0.0650`:
  `data/gemma4-q8-gpu3-strict-vdr2-f16p021-u6-pmin0065-n3-nmin2-p00650-ub1024-full512-20260628T025034Z/summary.json`
  median100 `97.2035`, p10 `85.7844`, mean `97.0862`, full512 `89.7983`.

Decision: no promotion. `unroll6 + p_min=0.0400` was closest but still below
100 and did not improve the tail enough.

## Draft thread sweep (`20260628T025249Z`)

Four-way strict full512 screen:

- draft threads 16:
  `data/gemma4-q8-gpu0-strict-vdr2-f16p021-dth16-n3-nmin2-p00475-ub1024-full512-20260628T025249Z/summary.json`
  median100 `92.9227`, p10 `85.3803`, mean `94.7649`, full512 `90.7529`.
- draft threads 24:
  `data/gemma4-q8-gpu1-strict-vdr2-f16p021-dth24-n3-nmin2-p00475-ub1024-full512-20260628T025249Z/summary.json`
  median100 `96.2302`, p10 `88.4015`, mean `96.8454`, full512 `91.6404`.
- draft threads 32 control:
  `data/gemma4-q8-gpu2-strict-vdr2-f16p021-dth32-n3-nmin2-p00475-ub1024-full512-20260628T025249Z/summary.json`
  median100 `98.8543`, p10 `87.9415`, mean `97.1828`, full512 `91.1870`.
- draft threads 64:
  `data/gemma4-q8-gpu3-strict-vdr2-f16p021-dth64-n3-nmin2-p00475-ub1024-full512-20260628T025249Z/summary.json`
  median100 `95.8691`, p10 `86.4332`, mean `96.2237`, full512 `90.8926`.

Decision: no promotion. Thread count does not reliably lift the median.

## Solo validation checks

The hypothesis was that four concurrent replicas might be suppressing the best
single-session number through CPU/runtime contention. Solo runs did not confirm
that:

- current stack solo, GPU0:
  `data/gemma4-q8-gpu0-strict-vdr2-f16p021-solo-current-n3-nmin2-p00475-ub1024-full512-20260628T025505Z/summary.json`
  median100 `95.2789`, p10 `89.4705`, mean `97.2332`, full512 `92.4831`,
  canary rows `128`.
- unroll6 solo, GPU0:
  `data/gemma4-q8-gpu0-strict-vdr2-f16p021-solo-unroll6-n3-nmin2-p00475-ub1024-full512-20260628T025722Z/summary.json`
  median100 `98.2732`, p10 `87.6166`, mean `98.8423`, full512 `92.0925`,
  canary rows `128`.

Decision: no promotion. Solo execution is not the missing 5%.

## Server `THREADS` sweep (`20260628T030017Z`)

Four-way strict full512 screen:

- `THREADS=4`:
  `data/gemma4-q8-gpu0-strict-vdr2-f16p021-th4-n3-nmin2-p00475-ub1024-full512-20260628T030017Z/summary.json`
  median100 `95.6915`, p10 `89.4831`, mean `96.5906`, full512 `91.7438`.
- `THREADS=8` control:
  `data/gemma4-q8-gpu1-strict-vdr2-f16p021-th8-n3-nmin2-p00475-ub1024-full512-20260628T030017Z/summary.json`
  median100 `88.6701`, p10 `85.3094`, mean `92.2092`, full512 `88.9724`.
- `THREADS=12`:
  `data/gemma4-q8-gpu2-strict-vdr2-f16p021-th12-n3-nmin2-p00475-ub1024-full512-20260628T030017Z/summary.json`
  median100 `98.0602`, p10 `86.2579`, mean `96.4166`, full512 `89.4930`.
- `THREADS=16`:
  `data/gemma4-q8-gpu3-strict-vdr2-f16p021-th16-n3-nmin2-p00475-ub1024-full512-20260628T030017Z/summary.json`
  median100 `96.0969`, p10 `88.3201`, mean `96.2588`, full512 `91.9930`.

Decision: no promotion. Server thread count is not the missing lever.

## Verifier fused-output argmax scheduler screen (`20260628T032313Z`)

Hypothesis from source audit: `GGML_OP_MUL_MAT_ARGMAX` may have been batched as
`op->ne[1]` even though the real verifier hidden-row count is
`op->src[1]->ne[1]`. A tiny source patch changed only `get_op_batch_size()` for
`GGML_OP_MUL_MAT_ARGMAX`, then two control lanes were compared with two
`LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1` lanes.

Four-way strict 128-token screen:

- control A:
  `data/gemma4-q8-gpu0-strict-vdr2-f16p021-controlA-n3-nmin2-p00475-ub1024-20260628T032313Z/summary.json`
  median100 `95.7611`, p10 `85.7045`, mean `95.5339`, full128 `94.8780`.
- fused verifier A:
  `data/gemma4-q8-gpu1-strict-vdr2-f16p021-fusedA-n3-nmin2-p00475-ub1024-20260628T032313Z/summary.json`
  median100 `87.8123`, p10 `79.1151`, mean `87.5045`, full128 `87.6692`.
- control B:
  `data/gemma4-q8-gpu2-strict-vdr2-f16p021-controlB-n3-nmin2-p00475-ub1024-20260628T032313Z/summary.json`
  median100 `98.8722`, p10 `85.8004`, mean `97.5283`, full128 `95.3860`.
- fused verifier B:
  `data/gemma4-q8-gpu3-strict-vdr2-f16p021-fusedB-n3-nmin2-p00475-ub1024-20260628T032313Z/summary.json`
  median100 `82.9537`, p10 `77.7217`, mean `84.4938`, full128 `84.6454`.

Decision: reject. The scheduler change did not make fused verifier argmax
competitive; fused lanes were `~8-16 tok/s` slower than controls despite passing
the strict gate. The source patch was reverted. Continue using
`LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1` without
`LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1`.

## Selected-softmax weighted-sum current-stack screen (`20260628T032805Z`)

Hypothesis: the selected-softmax + weighted-sum combined path might help the
current VDR2/F16-small-ncols stack even though older tests were on a different
row/profile regime. Four-way strict 128-token screen:

- control A:
  `data/gemma4-q8-gpu0-strict-vdr2-f16p021-controlA-n3-nmin2-p00475-ub1024-20260628T032805Z/summary.json`
  median100 `99.6105`, p10 `91.9916`, mean `99.3133`, full128 `99.7357`.
- selected-softmax-weighted-sum A:
  `data/gemma4-q8-gpu1-strict-vdr2-f16p021-selwsumA-n3-nmin2-p00475-ub1024-20260628T032805Z/summary.json`
  median100 `97.8150`, p10 `90.4653`, mean `97.3952`, full128 `96.5316`.
- control B:
  `data/gemma4-q8-gpu2-strict-vdr2-f16p021-controlB-n3-nmin2-p00475-ub1024-20260628T032805Z/summary.json`
  median100 `94.2575`, p10 `86.4272`, mean `95.3981`.
- selected-softmax-weighted-sum B:
  `data/gemma4-q8-gpu3-strict-vdr2-f16p021-selwsumB-n3-nmin2-p00475-ub1024-20260628T032805Z/summary.json`
  median100 `95.3976`, p10 `87.8559`, mean `95.8769`.

Decision: reject. The candidate did not beat paired controls and is not a
path to reliable `>100` on this current stack.

## Current-stack full512 repeat batch (`20260628T032940Z`)

Because one 128-token control lane reached `99.61`, reran the exact current
stack as four independent strict full512 confirmations:

- repeat A:
  `data/gemma4-q8-gpu0-strict-vdr2-f16p021-repeatA-n3-nmin2-p00475-ub1024-full512-20260628T032940Z/summary.json`
  median100 `98.6727`, p10 `90.2182`, mean `98.3740`, full512 `91.6780`.
- repeat B:
  `data/gemma4-q8-gpu1-strict-vdr2-f16p021-repeatB-n3-nmin2-p00475-ub1024-full512-20260628T032940Z/summary.json`
  median100 `99.2291`, p10 `87.9499`, mean `97.9263`, full512 `93.3741`.
- repeat C:
  `data/gemma4-q8-gpu2-strict-vdr2-f16p021-repeatC-n3-nmin2-p00475-ub1024-full512-20260628T032940Z/summary.json`
  median100 `97.2018`, p10 `87.8132`, mean `95.9366`, full512 `92.9290`.
- repeat D:
  `data/gemma4-q8-gpu3-strict-vdr2-f16p021-repeatD-n3-nmin2-p00475-ub1024-full512-20260628T032940Z/summary.json`
  median100 `93.3506`, p10 `82.5367`, mean `93.6328`, full512 `91.7941`.

Decision: valid improvement over the promoted `95.8245` record in the best
lane, but not reliable `>100`. Treat `99.2291` as the best current-stack
strict full512 result until superseded.

## `n_max=2` tail screen (`20260628T033248Z`)

Hypothesis: slow prompts may be paying too much for position-3 verification.
Strict 128-token screen:

- `n_max=3` control:
  `data/gemma4-q8-gpu0-strict-vdr2-f16p021-control-n3-n3-nmin2-p00475-ub1024-20260628T033248Z/summary.json`
  median100 `97.5495`, p10 `89.0536`, mean `97.1981`, full128 `94.1236`.
- `n_max=2`, `n_min=2`, `p_min=0.0475`:
  `data/gemma4-q8-gpu1-strict-vdr2-f16p021-n2min2-p00475-n2-nmin2-p00475-ub1024-20260628T033248Z/summary.json`
  median100 `93.5410`, p10 `88.0007`.
- `n_max=2`, `n_min=1`, `p_min=0.0475`:
  `data/gemma4-q8-gpu2-strict-vdr2-f16p021-n2min1-p00475-n2-nmin1-p00475-ub1024-20260628T033248Z/summary.json`
  median100 `94.6554`, p10 `87.1466`.
- `n_max=2`, `n_min=2`, `p_min=0.0400`:
  `data/gemma4-q8-gpu3-strict-vdr2-f16p021-n2min2-p0040-n2-nmin2-p00400-ub1024-20260628T033248Z/summary.json`
  median100 `93.2766`, p10 `90.2156`.

Decision: reject. Reducing speculative depth is a clear median loss.

## Low `p_min` screen (`20260628T033414Z`)

Strict 128-token screen around lower direct-argmax `p_min` settings:

- `p_min=0.0200`: median100 `93.3198`, p10 `87.9860`.
- `p_min=0.0300`: median100 `99.3167`, p10 `86.2463`, mean `97.7961`.
- `p_min=0.0350`: median100 `97.1090`, p10 `86.0210`.
- `p_min=0.0475` control: median100 `96.3963`, p10 `84.7475`.

Decision: no promotion. `p_min=0.0300` is another near-100 screen, but the
p10 is weak and earlier full512 p-min sweeps did not repeat reliably.

## Context-size screen (`20260628T033609Z`)

Hypothesis: the strict suite is small-context and may not benefit from the
current `CTX_SIZE=8192`; smaller KV/cache footprint might lift decode. Four-way
strict 128-token screen:

- `CTX_SIZE=2048`:
  `data/gemma4-q8-gpu0-strict-vdr2-f16p021-ctx2048-n3-nmin2-p00475-ub1024-20260628T033609Z/summary.json`
  median100 `100.0355`, p10 `91.8813`, mean `99.1420`, full128 `100.4569`.
- `CTX_SIZE=4096`:
  `data/gemma4-q8-gpu1-strict-vdr2-f16p021-ctx4096-n3-nmin2-p00475-ub1024-20260628T033609Z/summary.json`
  median100 `96.9129`, p10 `88.7173`, mean `98.1989`.
- `CTX_SIZE=8192` control:
  `data/gemma4-q8-gpu2-strict-vdr2-f16p021-ctx8192-n3-nmin2-p00475-ub1024-20260628T033609Z/summary.json`
  median100 `98.9202`, p10 `92.9985`, mean `99.5180`.
- `CTX_SIZE=16384`:
  `data/gemma4-q8-gpu3-strict-vdr2-f16p021-ctx16384-n3-nmin2-p00475-ub1024-20260628T033609Z/summary.json`
  median100 `95.6252`, p10 `88.0273`, mean `96.2918`.

Decision: `CTX_SIZE=2048` was the first current-stack strict screen to cross
`100` with a strong p10, but it did **not** survive strict full512 repeats.
It is rejected for the headline gate.

### `CTX_SIZE=2048` strict full512 confirmation (`20260628T034006Z`)

Four independent strict full512 repeats, all fresh-response valid with
`cached_tokens=0` and canary `128/128`, fell far below the screen result:

- repeat 1:
  `data/gemma4-q8-gpu0-strict-vdr2-f16p021-ctx2048-repeat1-n3-nmin2-p00475-ub1024-full512-20260628T034006Z/summary.json`
  median100 `84.1710`, p10 `79.7854`, mean `86.2562`, full512 `83.9963`.
- repeat 2:
  `data/gemma4-q8-gpu1-strict-vdr2-f16p021-ctx2048-repeat2-n3-nmin2-p00475-ub1024-full512-20260628T034006Z/summary.json`
  median100 `89.3862`, p10 `81.0061`, mean `89.2874`, full512 `84.8720`.
- repeat 3:
  `data/gemma4-q8-gpu2-strict-vdr2-f16p021-ctx2048-repeat3-n3-nmin2-p00475-ub1024-full512-20260628T034006Z/summary.json`
  median100 `88.1530`, p10 `79.7356`, mean `86.8008`, full512 `83.7564`.
- repeat 4:
  `data/gemma4-q8-gpu3-strict-vdr2-f16p021-ctx2048-repeat4-n3-nmin2-p00475-ub1024-full512-20260628T034006Z/summary.json`
  median100 `86.3788`, p10 `80.1687`, mean `87.4874`, full512 `83.3792`.

Conclusion: the 128-token `CTX_SIZE=2048` result was a short-run artifact and
the smaller context is actively worse for full512 generation. Keep
`CTX_SIZE=8192` for the promoted lane.

## Overall conclusion

Runtime-only tuning has a strict full512 ceiling around `95-99.98 tok/s` on
the `CTX_SIZE=8192` stack. `CTX_SIZE=2048` did not repeat. The remaining path
to reliable `>100` likely needs source work against the largest profile costs:

1. target/verifier LM-head `Q8_0 MUL_MAT` / argmax path;
2. final-layer BF16 MoE gate/up (BF16 direct `MUL_MAT_ID` attempt crashed and
   was reverted);
3. low-prompt acceptance variability rather than global draft knob tuning.

Do not submit these near misses to LocalMaxxing. They are valid diagnostic
strict runs, but no new record was confirmed.

## Combined near-miss full512 sweep (`20260628T035059Z`)

Follow-up four-way strict full512 run tested the best remaining runtime knobs
from the near-miss screens: lower `p_min`, draft direct-argmax unroll `6/7`,
and host thread count. All runs were fresh-response valid (`cached_tokens=0`)
with canary `128/128`.

- `unroll=6`, `p_min=0.0300`, `THREADS=8`:
  `data/gemma4-q8-gpu0-strict-vdr2-f16p021-u6-pmin0030-th8-full512-20260628T035059Z/summary.json`
  median100 `97.5942`, p10 `88.6485`, mean `97.1138`, full512 `92.1487`.
- `unroll=6`, `p_min=0.0350`, `THREADS=8`:
  `data/gemma4-q8-gpu1-strict-vdr2-f16p021-u6-pmin0035-th8-full512-20260628T035059Z/summary.json`
  median100 `95.9899`, p10 `86.8443`, mean `96.2863`, full512 `91.3068`.
- `unroll=6`, `p_min=0.0300`, `THREADS=12`:
  `data/gemma4-q8-gpu2-strict-vdr2-f16p021-u6-pmin0030-th12-full512-20260628T035059Z/summary.json`
  median100 `93.4140`, p10 `86.9268`, mean `94.8190`, full512 `92.1969`.
- `unroll=7`, `p_min=0.0300`, `THREADS=8`:
  `data/gemma4-q8-gpu3-strict-vdr2-f16p021-u7-pmin0030-th8-full512-20260628T035059Z/summary.json`
  median100 `94.2564`, p10 `85.1061`, mean `94.5188`, full512 `89.7592`.

Decision: reject for promotion. The best lane was `unroll=6`,
`p_min=0.0300`, `THREADS=8`, but it still landed below both the earlier
`99.229` repeat and the `>100` objective. This reinforces that runtime-only
knob work is exhausted for reliable crack-100; the next viable work is source
optimization in the target/verifier path, especially the Q8 reordered MoE
kernel and final LM-head path.

## Q8 reordered MoE rowpack source patch (`20260628T040900Z`)

Patch: added a default-off launch-geometry variant for the existing reordered
Q8_0 multi-token MoE kernel:

- source tree:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926`;
- files touched:
  `ggml/src/ggml-sycl/mmvq.cpp`,
  `ggml/src/ggml-sycl/mmvq.hpp`,
  `ggml/src/ggml-sycl/ggml-sycl.cpp`,
  `scripts/run-gemma4-26b-first-baseline.sh`,
  `scripts/run-gemma4-26b-llamacpp-replica.sh`;
- env gate: `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_ROWPACK=2|4`;
- intended effect: keep the same route IDs, same reordered Q8 dot product, and
  same accumulation order, but increase the output rows handled per workgroup
  from `GGML_SYCL_MMV_Y` to `GGML_SYCL_MMV_Y * rows_pack`;
- graph eligibility was updated to require reordered Q8_0 state for this path;
- harness logging was updated so rowpack appears in `launcher_identity`.

Rationale: this tested whether launch/scheduler overhead in the hot
`ffn_moe_gate_up` / `ffn_moe_down` verifier MoE kernels was still material.
Unlike the rejected pair-slot/top8/direct-VDR2 variants, rowpack does not alter
route addressing or add per-thread expert state.

Strict full512 result, all rows fresh-response valid (`cached_tokens=0`) and
canary `128/128`:

| Lane | Data dir | Median 1-100 | p10 | Mean | Full512 |
| --- | --- | ---: | ---: | ---: | ---: |
| control, unroll7, `p_min=0.0475` | `data/gemma4-q8-gpu0-strict-vdr2-f16p021-rowpack-control-full512-20260628T040900Z/summary.json` | `93.7177` | `88.2419` | `96.3762` | `91.6172` |
| rowpack=2, unroll7, `p_min=0.0475` | `data/gemma4-q8-gpu1-strict-vdr2-f16p021-rowpack2-full512-20260628T040900Z/summary.json` | `95.9153` | `87.7989` | `95.7386` | `90.4440` |
| rowpack=4, unroll7, `p_min=0.0475` | `data/gemma4-q8-gpu2-strict-vdr2-f16p021-rowpack4-full512-20260628T040900Z/summary.json` | `92.9105` | `88.0608` | `94.2359` | `90.7530` |
| rowpack=2, unroll6, `p_min=0.0300` | `data/gemma4-q8-gpu3-strict-vdr2-f16p021-rowpack2-u6-pmin0030-full512-20260628T040900Z/summary.json` | `89.8947` | `86.6188` | `93.9487` | `90.3944` |

Decision: reject for promotion. Rowpack=2 is valid and not catastrophic, but it
does not beat the promoted `95.8245` record in a meaningful way and full512
falls behind. Rowpack=4 is worse. Keep the patch as a default-off experiment
artifact, but do not submit or recommend it for the headline lane.

## Verifier LM-head argmax tile subgroup patch (`20260628T042332Z`)

Patch: added a default-off tile-subgroup tuning knob for the existing
`GGML_OP_MUL_MAT_ARGMAX` / verifier LM-head fused-argmax SYCL path:

- source tree:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926`;
- files touched:
  `ggml/src/ggml-sycl/mmvq.cpp`,
  `ggml/src/ggml-sycl/mmvq.hpp`,
  `ggml/src/ggml-sycl/ggml-sycl.cpp`,
  `scripts/run-gemma4-26b-first-baseline.sh`,
  `scripts/run-gemma4-26b-llamacpp-replica.sh`;
- env gate: `LLAMA_SYCL_MUL_MAT_ARGMAX_TILE_SUBGROUPS=1|2|4|8|16|32`;
- intended effect: reduce scratch/tile pressure in the fused verifier LM-head
  argmax path by using fewer subgroups per tile, while preserving exact target
  argmax semantics.

Strict 128-token result, all rows fresh-response valid (`cached_tokens=0`) and
canary-valid:

| Lane | Data dir | Median 1-100 | p10 | Mean | Full128 |
| --- | --- | ---: | ---: | ---: | ---: |
| control | `data/gemma4-q8-gpu0-strict-vdr2-f16p021-argmaxtile-control-128-20260628T042332Z/summary.json` | `98.4448` | `85.7686` | `97.4566` | `95.7296` |
| fused argmax default | `data/gemma4-q8-gpu1-strict-vdr2-f16p021-argmaxtile-fused-default-128-20260628T042332Z/summary.json` | `88.7342` | `76.8173` | `86.3920` | `89.3138` |
| fused argmax, tile subgroups 8 | `data/gemma4-q8-gpu2-strict-vdr2-f16p021-argmaxtile-fused-tile8-128-20260628T042332Z/summary.json` | `84.3517` | `77.6629` | `84.8229` | `83.5912` |
| fused argmax, tile subgroups 4 | `data/gemma4-q8-gpu3-strict-vdr2-f16p021-argmaxtile-fused-tile4-128-20260628T042332Z/summary.json` | `82.4487` | `75.4398` | `84.5646` | `85.0958` |

Decision: reject. The fused verifier LM-head path is still materially slower
than the existing backend-argmax-IDs path, and reducing tile subgroups worsens
it. Keep the patch default-off as a durable experiment artifact, but do not run
full512 confirmation or submit it to LocalMaxxing. Future LM-head work needs a
different design than the current two-stage fused output-argmax kernel.

## CPU affinity strict full512 screen (`20260628T043413Z`)

Hypothesis: four concurrent one-B70 replicas may contend on the 32 host logical
CPUs. Added a logged `CPU_AFFINITY` pass-through to:

- `scripts/run-gemma4-26b-llamacpp-replica.sh`;
- `scripts/run-gemma4-26b-first-baseline.sh`.

The launcher now records the mask in both the server log and summary identity,
and runs the server under `taskset -c` when `CPU_AFFINITY` is set.

Four-way strict full512 screen with the promoted record identity preserved
(`UD-Q8_K_XL`, Q4_0 MTP draft, f16 KV, `n_max=3`, `n_min=2`,
`p_min=0.0475`, direct unroll 7, VDR2, p021 small-ncols, `cached_tokens=0`):

| CPU mask | Result path | Median 1-100 tok/s | p10 1-100 tok/s | Full512 tok/s |
| --- | --- | ---: | ---: | ---: |
| `0-3,16-19` | `data/gemma4-q8-strict-vdr2-f16p021-affinity-full512-20260628T043413Z-gpu0-cores0-3/summary.json` | `98.4252` | `87.1024` | `91.5009` |
| `4-7,20-23` | `data/gemma4-q8-strict-vdr2-f16p021-affinity-full512-20260628T043413Z-gpu1-cores4-7/summary.json` | `97.0377` | `87.4001` | `92.5773` |
| `8-11,24-27` | `data/gemma4-q8-strict-vdr2-f16p021-affinity-full512-20260628T043413Z-gpu2-cores8-11/summary.json` | `95.8814` | `85.4872` | `89.4061` |
| `12-15,28-31` | `data/gemma4-q8-strict-vdr2-f16p021-affinity-full512-20260628T043413Z-gpu3-cores12-15/summary.json` | `98.8597` | `88.3636` | `93.2359` |

Decision: no promotion. CPU partitioning is a useful reproducibility/control
knob and should remain in the harness, but it is not the missing reliable
`>100` lever. The best affinity lane remains below the earlier `99.2291`
current-stack full512 observation and below the `>100` target.

## Verifier sampled-ID bulk host-read patch (`20260628T050945Z`)

Patch: added a default-off verifier helper path gated by
`LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`.

Files touched in the llama.cpp source tree:

- `common/sampling.cpp`
- `include/llama.h`

Intent: the target verifier already runs backend argmax and then reads sampled
token IDs back to the host. The old path synchronized once and then resolved
each row with `llama_get_sampled_token_ith_nosync(ctx, idx)`. The experiment
added a consecutive-row fast path that reads `llama_get_sampled_tokens(ctx)`
once after the synchronize and indexes the returned host buffer directly. It is
semantically identical for consecutive verifier rows and falls back to the old
per-row accessor otherwise.

Four-way strict full512 screen, all rows fresh-response valid
(`cached_tokens=0`) and canary-valid:

| Lane | Data dir | Median 1-100 | p10 | Mean | Full512 | TTFT ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| GPU0 | `data/gemma4-q8-gpu0-strict-vdr2-f16p021-bulksampled-n3-nmin2-p00475-ub1024-full512-20260628T050945Z/summary.json` | `94.8270` | `91.5481` | `96.5440` | `91.3545` | `179.162` |
| GPU1 | `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-n3-nmin2-p00475-ub1024-full512-20260628T050945Z/summary.json` | `97.9715` | `88.3102` | `97.1210` | `90.6370` | `180.170` |
| GPU2 | `data/gemma4-q8-gpu2-strict-vdr2-f16p021-bulksampled-n3-nmin2-p00475-ub1024-full512-20260628T050945Z/summary.json` | `95.7431` | `85.6203` | `96.9729` | `91.4074` | `178.881` |
| GPU3 | `data/gemma4-q8-gpu3-strict-vdr2-f16p021-bulksampled-n3-nmin2-p00475-ub1024-full512-20260628T050945Z/summary.json` | `97.1538` | `88.4116` | `97.3393` | `91.4755` | `180.191` |

Decision after initial screen: promising but not yet enough evidence for
promotion. The patch is correct and low-risk, but the first four lanes were
within normal run variance and did not crack `100`.

Per-prompt comparison against the promoted `95.8245` record showed the same
slow-half pattern: some prompts remain `105-111 tok/s`, while code-review,
SQL-debugging, release-plan, performance-hypotheses, and decision-memo are the
median limiters. This confirms the missing gain is not host sampled-ID lookup;
future work should target verifier kernel cost or slow-prompt acceptance.

Follow-up exact confirmation used the exact same strict full512 gate on all
four B70s:

`gemma4-q8-gpu{0..3}-strict-vdr2-f16p021-bulksampled-confirm-{A..D}-n3-nmin2-p00475-ub1024-full512-20260628T052158Z`

All rows remained fresh-response valid (`cached_tokens=0`) and canary-valid:

| Lane | Data dir | Median 1-100 | p10 | Mean | Full512 | Wall full512 | TTFT ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GPU0/A | `data/gemma4-q8-gpu0-strict-vdr2-f16p021-bulksampled-confirm-A-n3-nmin2-p00475-ub1024-full512-20260628T052158Z/summary.json` | `96.0145` | `88.0516` | `95.8276` | `92.2874` | `89.0851` | `179.494` |
| GPU1/B | `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-confirm-B-n3-nmin2-p00475-ub1024-full512-20260628T052158Z/summary.json` | **`98.3405`** | `85.9794` | `95.9529` | `91.1739` | `87.7371` | `180.211` |
| GPU2/C | `data/gemma4-q8-gpu2-strict-vdr2-f16p021-bulksampled-confirm-C-n3-nmin2-p00475-ub1024-full512-20260628T052158Z/summary.json` | `95.9028` | `84.8895` | `96.6318` | `91.4144` | `88.3490` | `179.696` |
| GPU3/D | `data/gemma4-q8-gpu3-strict-vdr2-f16p021-bulksampled-confirm-D-n3-nmin2-p00475-ub1024-full512-20260628T052158Z/summary.json` | `94.9409` | `87.9386` | `96.5380` | `91.6525` | `87.8618` | `179.371` |

Final decision: **promote as a strict record bump, not as crack-100.** The best
lane beat the prior submitted `95.8245` row and was submitted to LocalMaxxing
as `cmqxchyra03xmqr01b963gmi1`, using payload
`data/localmaxxing-payloads/gemma4-q8-vdr2-f16p021-bulksampled-confirm-20260628T052158.json`
and response log
`data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-f16p021-bulksampled-full512-20260628.submit.log`.
The patch is worth keeping in the promoted recipe because it is
semantically identical for consecutive verifier rows, but the remaining gap is
not host sampled-ID lookup. Reliable `>100` likely requires reducing
target/verifier MoE or LM-head cost, improving fresh-valid speculation, or a
structural verifier shortcut.

## Confidence-gated non-direct MTP diagnostic (`20260628T051959Z`)

Question: since direct-unroll MTP bypasses `p_min`, top-k, and logit-gap
confidence checks, could the slower non-direct top-k path lift the slow prompts
enough to compensate for extra draft sampling cost?

Four-way strict 128-token diagnostic, all fresh-response valid with
`cached_tokens=0`:

| Lane | Direct IDs | Fast top-k | `top_k` | `p_min` | gap | Median 1-100 | p10 | Mean |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| control direct | on | off | 10 | `0.0475` | `0` | `91.4992` | `85.6160` | `94.1499` |
| topk4 p065 | off | on | 4 | `0.65` | `0` | `95.0601` | `85.6823` | `94.8388` |
| topk8 p075 | off | on | 8 | `0.75` | `0` | `94.0290` | `89.7341` | `95.8744` |
| topk4 p065 gap05 | off | on | 4 | `0.65` | `0.50` | `94.4734` | `82.1737` | `93.4525` |

Decision: reject. This was intentionally a short diagnostic, not a headline
candidate, and it did not show a path to `>100`. It agrees with the older
2026-06-23 top-k/logit-gap work: real confidence gating is valid but not fast
enough in the current implementation. Do not spend full512 budget on this path
unless a new source change makes confidence scores effectively free.

## Reordered Q8 aligned-load and gate/up route-cache seed screens (`20260628T055215Z`, `20260628T055449Z`)

Question: can the remaining `>100` gap be closed with a tiny verifier-MoE
kernel cleanup? The tested source change replaced the reordered Q8_0 verifier
weight load in `reorder_vec_dot_q_sycl<GGML_TYPE_Q8_0>` with the aligned
32-bit helper (`get_int_from_int8_aligned`) instead of reconstructing from two
16-bit loads. The layout should be semantically identical because reordered
Q8_0 block offsets are 32-byte multiples. The build completed, but the screen
did not show a promotable gain; the source change was reverted after testing.

Strict 128-token screen with the aligned-load build, all rows fresh-response
valid (`cached_tokens=0`) and canary-valid:

| Lane | Data dir | Median 1-100 | p10 | Mean | Full128 | Wall full128 | TTFT ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GPU0 | `data/gemma4-q8-gpu0-strict-vdr2-alignedq8load-n3-nmin2-p00475-ub1024-128-20260628T055215Z/summary.json` | `98.9895` | `87.3879` | `98.0177` | `97.8810` | `83.5000` | `179.467` |
| GPU1 | `data/gemma4-q8-gpu1-strict-vdr2-alignedq8load-n3-nmin2-p00475-ub1024-128-20260628T055215Z/summary.json` | `96.6234` | `88.4923` | `96.5366` | `95.8188` | `83.0505` | `179.837` |
| GPU2 | `data/gemma4-q8-gpu2-strict-vdr2-alignedq8load-n3-nmin2-p00475-ub1024-128-20260628T055215Z/summary.json` | `94.3431` | `91.3126` | `96.8317` | `95.6270` | `83.0678` | `179.272` |
| GPU3 | `data/gemma4-q8-gpu3-strict-vdr2-alignedq8load-n3-nmin2-p00475-ub1024-128-20260628T055215Z/summary.json` | `98.1090` | `88.0059` | `96.6323` | `92.9812` | `81.7906` | `179.334` |

Follow-up added only
`LLAMA_SYCL_MUL_MAT_ID_GATE_UP_FAST_SEED_ROUTE_CACHE=1` on top of the same
aligned-load build, to check whether the fused gate/up path could seed routing
for later MoE work. That also did not crack `100` and did not improve the
four-lane pattern:

| Lane | Data dir | Median 1-100 | p10 | Mean | Full128 | Wall full128 | TTFT ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GPU0 | `data/gemma4-q8-gpu0-strict-vdr2-alignedq8load-gateupseedroute-n3-nmin2-p00475-ub1024-128-20260628T055449Z/summary.json` | `99.2441` | `86.4199` | `97.4054` | `99.0232` | `86.8160` | `178.834` |
| GPU1 | `data/gemma4-q8-gpu1-strict-vdr2-alignedq8load-gateupseedroute-n3-nmin2-p00475-ub1024-128-20260628T055449Z/summary.json` | `95.7453` | `85.3365` | `95.2723` | `95.2455` | `83.6790` | `179.340` |
| GPU2 | `data/gemma4-q8-gpu2-strict-vdr2-alignedq8load-gateupseedroute-n3-nmin2-p00475-ub1024-128-20260628T055449Z/summary.json` | `94.0989` | `84.9756` | `94.9847` | `94.8460` | `82.3108` | `180.083` |
| GPU3 | `data/gemma4-q8-gpu3-strict-vdr2-alignedq8load-gateupseedroute-n3-nmin2-p00475-ub1024-128-20260628T055449Z/summary.json` | `97.0270` | `84.8915` | `96.9665` | `96.7536` | `85.1278` | `179.578` |

Decision: **do not promote**. Best strict screen lane reached `99.244`, but the
spread is consistent with normal lane variance and still below reliable
`>100`. No full512 confirmation and no LocalMaxxing submission. The aligned
source change was reverted; route-cache seeding can stay recorded as a
negative/inconclusive runtime toggle.

## Q8 reordered pair-slot top8 source screen (`20260628T061048Z`)

Question: can a lower-register-pressure version of the failed top8-slot MoE
kernel reuse each token activation across two expert slots at a time? The
tested source patch adapted the existing pair-slot reordered Q8_0 kernel to
Gemma's active verifier shape (`ids->ne[0] == 8`) by launching four slot-pair
groups per token (`slot0/slot1 = 0/1, 2/3, 4/5, 6/7`). The lane was default-off
behind `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_PAIR_SLOTS=1`.

Strict 128-token screen, all fresh-response valid and canary-valid:

| Lane | Data dir | Median 1-100 | p10 | Mean | Full128 | Wall full128 | TTFT ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GPU0 | `data/gemma4-q8-gpu0-strict-vdr2-pairslots8-n3-nmin2-p00475-ub1024-128-20260628T061048Z/summary.json` | `93.1952` | `86.9614` | `95.3774` | `95.1727` | `83.8521` | `179.114` |
| GPU1 | `data/gemma4-q8-gpu1-strict-vdr2-pairslots8-n3-nmin2-p00475-ub1024-128-20260628T061048Z/summary.json` | `98.2092` | `87.3417` | `96.1726` | `94.4179` | `82.8335` | `180.352` |
| GPU2 | `data/gemma4-q8-gpu2-strict-vdr2-pairslots8-n3-nmin2-p00475-ub1024-128-20260628T061048Z/summary.json` | `94.0377` | `88.4810` | `95.2924` | `91.9985` | `81.5866` | `179.329` |
| GPU3 | `data/gemma4-q8-gpu3-strict-vdr2-pairslots8-n3-nmin2-p00475-ub1024-128-20260628T061048Z/summary.json` | `98.1450` | `86.8008` | `98.2177` | `97.4697` | `85.0364` | `179.359` |

Decision: **do not promote**. Correctness held, but the best lane stayed below
the current strict full512 record (`98.3405`) and the four-lane pattern does not
show a reliable `>100` path. No LocalMaxxing submission. Preserve the result as
a negative source-level MoE attempt; if the default-off patch is kept in source,
its only known valid use is diagnostic and it should not be enabled in promoted
recipes.

## Bulk sampled-ID verifier + direct-argmax unroll6 full512 repeats (`20260628T062352Z` onward)

Question: an older full512 strict row with `DIRECT_ARGMAX_UNROLL=6` reached
`99.9805` without the newer bulk sampled-ID verifier. Could combining unroll6
with the current submitted stack (`LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`) crack
`100` reliably?

All runs below are strict final-gate full512 rows with the fixed realistic
suite, `cached_tokens=0`, chat canary pass, UD-Q8_K_XL target/verifier, Q4_0 MTP
draft, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`, VDR2 reordered
Q8, F16 p021 small-ncols, and bulk sampled-ID verifier.

First four-lane confirmation:

| Lane | Median 1-100 | p10 | Mean | Full512 | Wall512 | TTFT ms | Summary |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| GPU0 | **`101.0765`** | `93.1293` | `100.5125` | `92.4212` | `89.2135` | `179.391` | `data/gemma4-q8-gpu0-strict-vdr2-f16p021-bulksampled-unroll6-n3-nmin2-p00475-ub1024-full512-20260628T062352Z/summary.json` |
| GPU1 | `98.2811` | `89.7713` | `98.2189` | `91.1992` | `88.1284` | `179.583` | `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-unroll6-n3-nmin2-p00475-ub1024-full512-20260628T062352Z/summary.json` |
| GPU2 | `98.9589` | `88.5070` | `97.5965` | `90.8278` | `87.9341` | `179.373` | `data/gemma4-q8-gpu2-strict-vdr2-f16p021-bulksampled-unroll6-n3-nmin2-p00475-ub1024-full512-20260628T062352Z/summary.json` |
| GPU3 | `99.3081` | `91.1494` | `99.0708` | `91.5424` | `87.9308` | `179.453` | `data/gemma4-q8-gpu3-strict-vdr2-f16p021-bulksampled-unroll6-n3-nmin2-p00475-ub1024-full512-20260628T062352Z/summary.json` |

Exact repeat did **not** reproduce the `>100` lane:

| Lane | Median 1-100 | p10 | Mean | Full512 | Wall512 | TTFT ms | Summary |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| GPU0 | `97.3310` | `87.4403` | `96.7635` | `91.3560` | `87.8323` | `179.940` | `data/gemma4-q8-gpu0-strict-vdr2-f16p021-bulksampled-unroll6-repeat2-n3-nmin2-p00475-ub1024-full512-20260628T062641Z/summary.json` |
| GPU1 | `95.5434` | `86.9095` | `97.2472` | `91.5127` | `87.9658` | `180.320` | `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-unroll6-repeat2-n3-nmin2-p00475-ub1024-full512-20260628T062641Z/summary.json` |
| GPU2 | `95.6285` | `84.1539` | `96.1604` | `91.3832` | `88.6825` | `179.552` | `data/gemma4-q8-gpu2-strict-vdr2-f16p021-bulksampled-unroll6-repeat2-n3-nmin2-p00475-ub1024-full512-20260628T062641Z/summary.json` |
| GPU3 | `93.5473` | `85.7622` | `94.0697` | `90.5898` | `87.7718` | `180.097` | `data/gemma4-q8-gpu3-strict-vdr2-f16p021-bulksampled-unroll6-repeat2-n3-nmin2-p00475-ub1024-full512-20260628T062641Z/summary.json` |

Solo controls also missed:

- GPU0 no-affinity solo:
  `96.7987` median, `89.8294` p10, `97.2323` mean,
  `data/gemma4-q8-gpu0-strict-vdr2-f16p021-bulksampled-unroll6-solo-noaff-n3-nmin2-p00475-ub1024-full512-20260628T063012Z/summary.json`.
- GPU0 exact-affinity solo:
  `96.1383` median, `87.2495` p10, `97.1668` mean,
  `data/gemma4-q8-gpu0-strict-vdr2-f16p021-bulksampled-unroll6-solo-aff-n3-nmin2-p00475-ub1024-full512-20260628T063232Z/summary.json`.

Decision: **do not promote**. The `101.0765` lane is a valid strict observation,
but not a reliable result. Across the eight full512 four-lane unroll6+bulk rows,
the median lane is only about `97.8`, and solo runs do not explain the miss as
four-replica contention. Keep unroll6 as a near-miss diagnostic, not a
LocalMaxxing submission.

## Bulk sampled-ID verifier higher `n_max` screen (`20260628T063611Z`)

Question: can we crack `100` reliably by increasing verified MTP depth now that
the current direct-ID path avoids draft sampling and the verifier sampled-ID
read is bulked? This is valid speculation because every drafted token is still
verified by the UD-Q8_K_XL target model.

Strict 128-token screen, current submitted stack plus `n_max=4/5/6/7`
respectively:

| Lane | `n_max` | Median 1-100 | p10 | Mean | Full128 | Wall128 | TTFT ms | Summary |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| GPU0 | 4 | `97.4952` | `81.9963` | `94.7951` | `95.4637` | `84.2022` | `179.203` | `data/gemma4-q8-gpu0-strict-vdr2-f16p021-bulksampled-nmax4-nmin2-p00475-ub1024-128-20260628T063611Z/summary.json` |
| GPU1 | 5 | `89.3602` | `77.8415` | `88.0330` | `88.7643` | `78.0713` | `180.203` | `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-nmax5-nmin2-p00475-ub1024-128-20260628T063611Z/summary.json` |
| GPU2 | 6 | `81.5448` | `75.4617` | `84.8730` | `85.6619` | `76.1065` | `179.597` | `data/gemma4-q8-gpu2-strict-vdr2-f16p021-bulksampled-nmax6-nmin2-p00475-ub1024-128-20260628T063611Z/summary.json` |
| GPU3 | 7 | `77.8048` | `69.0609` | `78.9978` | `77.8477` | `68.9966` | `179.514` | `data/gemma4-q8-gpu3-strict-vdr2-f16p021-bulksampled-nmax7-nmin2-p00475-ub1024-128-20260628T063611Z/summary.json` |

Decision: **reject higher `n_max` for this model/runtime**. `n_max=4` already
misses the current full512 record on a cheap screen, and deeper verification
collapses quickly. The extra target verifier rows cost more than the additional
accepted tokens on the fixed realistic suite. Do not spend full512 budget on
`n_max>3` unless a future patch materially lowers target/verifier row cost.

## GPU0 frequency-floor systems check (`20260628T063855Z`)

Question: is short-suite jitter from clock ramping enough to explain why the
best strict rows hover around `98-99` with occasional `101` spikes? Temporarily
set GPU0 tile 0 frequency range from the default `400-2800 MHz` to
`2400-2800 MHz`, ran the unroll6+bulk sampled-ID full512 candidate, then
restored the default range.

During the run, `xpu-smi stats -d 0 -j` sampled GPU frequency around
`2600-2800 MHz` with high memory utilization, so the floor took effect.

Result:

- Summary:
  `data/gemma4-q8-gpu0-strict-vdr2-f16p021-bulksampled-unroll6-freq2400-n3-nmin2-p00475-ub1024-full512-20260628T063855Z/summary.json`
- Median 1-100: `94.9781`, p10 `85.5259`, mean `96.4185`
- Full512 after-TTFT: `92.7316`, wall512 `89.0269`, TTFT `179.363 ms`
- Canary and strict gate passed; `cached_tokens=0`

Decision: **do not promote**. Raising the floor did not improve the primary
1-100 metric and therefore does not explain the crack-100 variance. Full512
after-TTFT improved slightly, but not enough to matter for the stated primary
metric. GPU0 was restored to `400-2800 MHz`.

## MoE selected-softmax / weighted-sum boundary runtime screen (`20260628T064308Z`)

Question: do the existing graph/backend MoE boundary flags become useful after
the current bulk sampled-ID verifier record stack? This screened the dedicated
`LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_WEIGHTED_SUM` fused graph op and the SYCL
`LLAMA_GEMMA4_MOE_WEIGHTED_SUM_2D` backend variant.

Strict 128-token screen:

| Lane | Extra env | Median 1-100 | p10 | Mean | Full128 | Wall128 | TTFT ms | Summary |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| GPU0 | control | `93.5089` | `86.2557` | `95.6020` | `93.4339` | `82.2834` | `179.117` | `data/gemma4-q8-gpu0-strict-vdr2-f16p021-bulksampled-moeboundary-control-n3-nmin2-p00475-ub1024-128-20260628T064308Z/summary.json` |
| GPU1 | `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_WEIGHTED_SUM=1` | `98.2844` | `89.8891` | `96.9235` | `94.8823` | `83.0902` | `179.934` | `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-moeboundary-selsoftmaxwsum-n3-nmin2-p00475-ub1024-128-20260628T064308Z/summary.json` |
| GPU2 | `LLAMA_GEMMA4_MOE_WEIGHTED_SUM_2D=1` | `98.7905` | `89.5305` | `97.8137` | `97.3948` | `83.9092` | `179.519` | `data/gemma4-q8-gpu2-strict-vdr2-f16p021-bulksampled-moeboundary-wsum2d-n3-nmin2-p00475-ub1024-128-20260628T064308Z/summary.json` |
| GPU3 | both flags | `99.0305` | `85.0730` | `97.3197` | `97.9931` | `85.6346` | `179.371` | `data/gemma4-q8-gpu3-strict-vdr2-f16p021-bulksampled-moeboundary-selsoftmaxwsum-wsum2d-n3-nmin2-p00475-ub1024-128-20260628T064308Z/summary.json` |

Decision: **do not promote**. All variants were canary/gate valid, but none
cracked `100` even on a 128-token screen, and the low same-batch control means
the apparent spread is likely normal lane variance. Do not spend full512 budget
on these existing MoE boundary flags unless a new source change improves the
same area.

## Selected-softmax weighted-sum split-N source patch (`20260628T070112Z`)

Question: can we reduce verifier-side MoE boundary cost by computing selected
softmax weights once per token for the real top-8 shape, then doing a simple
row-wise weighted sum? This replaced the initial top-2-only idea with a generic
`ids->ne[0] <= 8` split path gated by
`LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_WEIGHTED_SUM_SPLIT=1`.

Strict 128-token screen:

| Lane | Extra env | Median 1-100 | p10 | Mean | Full128 | Wall128 | TTFT ms | Summary |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| GPU0 | control | `100.1695` | `85.8161` | `98.1327` | `96.5062` | `83.7734` | `180.562` | `data/gemma4-q8-gpu0-strict-vdr2-f16p021-bulksampled-splitN-control-n3-nmin2-p00475-ub1024-128-20260628T070112Z/summary.json` |
| GPU1 | `LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_WEIGHTED_SUM=1` | `98.3930` | `87.3720` | `97.0656` | `97.4072` | `83.5196` | `181.584` | `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-splitN-selwsum-n3-nmin2-p00475-ub1024-128-20260628T070112Z/summary.json` |
| GPU2 | selected-softmax weighted-sum + split-N | `95.5263` | `88.5347` | `95.6902` | `97.8619` | `84.5987` | `180.147` | `data/gemma4-q8-gpu2-strict-vdr2-f16p021-bulksampled-splitN-selwsum-splitN-n3-nmin2-p00475-ub1024-128-20260628T070112Z/summary.json` |
| GPU3 | split-N + weighted-sum 2D | `93.9143` | `86.5461` | `95.3633` | `93.8036` | `83.3323` | `179.971` | `data/gemma4-q8-gpu3-strict-vdr2-f16p021-bulksampled-splitN-selwsum-splitN-wsum2d-n3-nmin2-p00475-ub1024-128-20260628T070112Z/summary.json` |

Decision: **reject and revert from active source**. The split-N path is
correct, but slower. The extra scratch allocation and second kernel are not
worth the saved local softmax work at these tiny verifier shapes. The control
lane crossing `100` on a short 128-token screen is a useful near-threshold
observation, but not a promoted result; full512 repeats remain the reliability
filter and have not reproduced `>100` reliably for this stack.

Patch note:
`patches/gemma4-26b-a4b-q8-b70/20260628T0701-moe-selected-softmax-weighted-sum-splitN-negative.md`.

## Bulk sampled-ID `p_min` screens around the current threshold (`20260628T070547Z`, `20260628T070833Z`)

Question: can a slightly different MTP draft confidence threshold make the
current stack crack `100` reliably without changing the Q8 target/verifier or
using warmed/history effects? All rows are strict cold realistic-suite screens,
`cached_tokens=0`, chat canary pass, UD-Q8_K_XL target/verifier, Q4_0 MTP
draft, VDR2 reordered Q8, F16 p021, bulk sampled-ID verifier, `n_max=3`,
`n_min=2`, `UBATCH_SIZE=1024`.

Higher-threshold screen:

| Lane | `p_min` | Median 1-100 | p10 | Mean | Full128 | Wall128 | TTFT ms | Summary |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| GPU0 | `0.0550` | `98.3541` | `87.0529` | `97.6975` | `95.9113` | `84.1639` | `179.775` | `data/gemma4-q8-gpu0-strict-vdr2-f16p021-bulksampled-pmin00550-n3-nmin2-ub1024-128-20260628T070547Z/summary.json` |
| GPU1 | `0.0600` | `96.6513` | `86.2203` | `96.7667` | `98.1028` | `86.4460` | `180.753` | `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-pmin00600-n3-nmin2-ub1024-128-20260628T070547Z/summary.json` |
| GPU2 | `0.0650` | `93.2505` | `86.6618` | `94.3481` | `93.7801` | `83.1617` | `180.845` | `data/gemma4-q8-gpu2-strict-vdr2-f16p021-bulksampled-pmin00650-n3-nmin2-ub1024-128-20260628T070547Z/summary.json` |
| GPU3 | `0.0700` | `93.9900` | `85.4067` | `95.6818` | `94.2017` | `82.0348` | `180.180` | `data/gemma4-q8-gpu3-strict-vdr2-f16p021-bulksampled-pmin00700-n3-nmin2-ub1024-128-20260628T070547Z/summary.json` |

Narrow screen:

| Lane | `p_min` | Median 1-100 | p10 | Mean | Full128 | Wall128 | TTFT ms | Summary |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| GPU0 | `0.0425` | `98.2289` | `89.0922` | `98.0805` | `95.6153` | `84.3297` | `179.464` | `data/gemma4-q8-gpu0-strict-vdr2-f16p021-bulksampled-pmin00425-n3-nmin2-ub1024-128-20260628T070833Z/summary.json` |
| GPU1 | `0.0450` | `93.9947` | `86.4158` | `95.2944` | `97.8807` | `83.0163` | `180.689` | `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-pmin00450-n3-nmin2-ub1024-128-20260628T070833Z/summary.json` |
| GPU2 | `0.0500` | **`100.4977`** | **`93.6699`** | `99.7636` | `98.1525` | `86.1581` | `180.502` | `data/gemma4-q8-gpu2-strict-vdr2-f16p021-bulksampled-pmin00500-n3-nmin2-ub1024-128-20260628T070833Z/summary.json` |
| GPU3 | `0.0525` | `92.8439` | `87.1205` | `95.6594` | `95.2188` | `83.8086` | `181.527` | `data/gemma4-q8-gpu3-strict-vdr2-f16p021-bulksampled-pmin00525-n3-nmin2-ub1024-128-20260628T070833Z/summary.json` |

The `0.0500` short screen was promising enough to promote to a full512
confirmation, but it did **not** repeat:

| Lane | `p_min` | Median 1-100 | p10 | Mean | Full512 | Wall512 | TTFT ms | Summary |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| GPU0 | `0.0500` | `98.1353` | `86.7181` | `97.2123` | `91.9564` | `88.3597` | `180.462` | `data/gemma4-q8-gpu0-strict-vdr2-f16p021-bulksampled-pmin00500-confirm-n3-nmin2-ub1024-full512-20260628T071016Z/summary.json` |
| GPU1 | `0.0500` | `96.7921` | `91.4221` | `98.4375` | `92.4166` | `88.8216` | `182.159` | `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-pmin00500-confirm-n3-nmin2-ub1024-full512-20260628T071016Z/summary.json` |
| GPU2 | `0.0500` | `96.5547` | `83.3063` | `96.3872` | `92.2082` | `89.1998` | `180.251` | `data/gemma4-q8-gpu2-strict-vdr2-f16p021-bulksampled-pmin00500-confirm-n3-nmin2-ub1024-full512-20260628T071016Z/summary.json` |
| GPU3 | `0.0500` | `94.8539` | `87.7324` | `96.2241` | `91.7651` | `88.2139` | `182.325` | `data/gemma4-q8-gpu3-strict-vdr2-f16p021-bulksampled-pmin00500-confirm-n3-nmin2-ub1024-full512-20260628T071016Z/summary.json` |

Decision: **keep `p_min=0.0475` as the current promoted threshold**. The
neighborhood can produce `100+` short-screen observations, but full512 repeats
still settle below the current strict record. Do not submit or promote `0.0500`.

## Deferred `verify_h` resize source patch (`20260628T072238Z`)

Question: with `LLAMA_MTP_DEFER_TARGET_H_NEXTN=1`, can we avoid unnecessary
host-side verifier hidden-state buffer work by moving `verify_h.resize()` into
the fallback extraction path? This is exact/quality-neutral in principle: the
deferred path copies only the selected `h_nextn` row from the target context.

Patch tested in `common/speculative.cpp`: move
`verify_h[seq_id].resize(n_rows * n_embd)` from before the deferred
`llama_copy_embeddings_nextn_ith(...)` fast path to just before the full
`llama_get_embeddings_nextn_ith(...)` fallback extraction. The patch was
reverted after screening.

Strict 128-token screen, current promoted stack (`p_min=0.0475`):

| Lane | Median 1-100 | p10 | Mean | Full128 | Wall128 | TTFT ms | Summary |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| GPU0 | `95.9717` | `87.7851` | `97.1330` | `94.6257` | `80.8558` | `179.369` | `data/gemma4-q8-gpu0-strict-vdr2-f16p021-bulksampled-deferresize-n3-nmin2-p00475-ub1024-128-20260628T072238Z/summary.json` |
| GPU1 | `95.5005` | `85.3023` | `96.4706` | `96.8958` | `84.6751` | `182.603` | `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-deferresize-n3-nmin2-p00475-ub1024-128-20260628T072238Z/summary.json` |
| GPU2 | `95.4326` | `86.4995` | `96.6708` | `94.6786` | `84.1035` | `180.745` | `data/gemma4-q8-gpu2-strict-vdr2-f16p021-bulksampled-deferresize-n3-nmin2-p00475-ub1024-128-20260628T072238Z/summary.json` |
| GPU3 | `95.2455` | `85.2005` | `95.1176` | `94.7500` | `83.1553` | `182.049` | `data/gemma4-q8-gpu3-strict-vdr2-f16p021-bulksampled-deferresize-n3-nmin2-p00475-ub1024-128-20260628T072238Z/summary.json` |

Decision: **reject and revert**. The patch was correctness-safe in this screen
but clearly slower. The current bottleneck is not this host-side buffer resize;
the slow-prompt audit shows first-100 decode step count dominates throughput.

## Rebuild / control-semantics audit (`20260628T0730Z`)

Before continuing the crack-100 search, the source and binary were re-aligned:
`common/speculative.cpp` was newer than `llama-server` after the negative
defer-resize patch was reverted, so the SYCL/AOT build was refreshed with:

```bash
set +u
source /opt/intel/oneapi/setvars.sh >/tmp/oneapi-setvars-gemma-rebaseline.log 2>&1
set -u
cmake --build /home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 --target llama-server -j 8
```

The rebuild completed and relinked `bin/llama-server`.

Important source audit finding: several runtime knobs that appeared to explain
near-miss results are not meaningful in the current promoted direct-argmax
draft path:

- `common/speculative.cpp::draft_sampled_argmax_sample(...)` returns a single
  direct candidate with `p=1.0`. That makes `--spec-draft-p-min` effectively a
  no-op for this path.
- `LLAMA_MTP_DRAFT_LOGIT_GAP_MIN` is also ineffective when the direct candidate
  list has size 1.
- `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=6/7` labels are mostly misleading with
  `--spec-draft-n-max 3`: the server reports the actual unroll as clamped to
  `3`. The valid `101.0765` full512 lane is therefore best treated as a normal
  variance outlier from the current `n_max=3` direct-ID path, not as proof that
  unroll 6 is a real lever.

Decision: future crack-100 work should not spend more budget on `p_min`,
logit-gap, or unroll-only sweeps unless the draft sampler path is changed so
those knobs actually alter acceptance or verifier work.

## Adaptive MTP depth screen (`20260628T073610Z`)

Question: the slow prompts correlate strongly with first-100 decode step count.
Could an adaptive controller avoid expensive third-position verification on
low-acceptance prompts while keeping the fast prompts at `n_max=3`?

Strict 128-token screen after the rebuild, all rows fresh-response valid
(`cached_tokens=0`) and canary-valid:

| Lane | Extra adaptive env | Median 1-100 | p10 | Mean | Full128 | Wall128 | Summary |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| GPU0 | control | `100.3136` | `90.0116` | `99.9833` | `96.8547` | `85.0928` | `data/gemma4-q8-gpu0-strict-vdr2-f16p021-bulksampled-adapt-control-128-20260628T073610Z/summary.json` |
| GPU1 | low `0.50`, warmup `6`, alpha `0.25` | `90.9804` | `86.4062` | `93.9711` | `91.5975` | `80.4342` | `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-adapt-low050-w6-a025-128-20260628T073610Z/summary.json` |
| GPU2 | low `0.55`, warmup `4`, alpha `0.50` | `91.9832` | `84.4163` | `92.6302` | `91.7148` | `80.2648` | `data/gemma4-q8-gpu2-strict-vdr2-f16p021-bulksampled-adapt-low055-w4-a050-128-20260628T073610Z/summary.json` |
| GPU3 | low `0.60`, warmup `3`, alpha `0.50` | `91.1362` | `86.8833` | `93.7804` | `92.7607` | `81.5969` | `data/gemma4-q8-gpu3-strict-vdr2-f16p021-bulksampled-adapt-low060-w3-a050-128-20260628T073610Z/summary.json` |

Decision: **reject adaptive capping**. It does change behavior, but every tested
controller is much slower than the paired control. The cost of reducing
third-position verification is outweighed by lower acceptance / extra decode
steps. Revisit only with a controller based on a cheaper, stronger signal than
the current rolling accepted-token ratio.

## Postnorm fusion runtime screen (`20260628T073809Z`)

Question: can the existing default-off Gemma postnorm fusions lift the current
record stack without changing model quality or speculative correctness?

Strict 128-token screen after the rebuild, all rows fresh-response valid
(`cached_tokens=0`) and canary-valid:

| Lane | Extra env | Median 1-100 | p10 | Mean | Full128 | Wall128 | Slowest prompts |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| GPU0 | control | `94.3073` | `87.4413` | `95.4226` | `93.6345` | `83.0421` | performance-hypotheses `86.2`, code-review `87.2` |
| GPU1 | `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1` | `98.7298` | `88.6552` | `96.8001` | `97.1731` | `85.1717` | code-review `82.6`, performance-hypotheses `88.5` |
| GPU2 | `LLAMA_GEMMA4_MOE_FUSED_BRANCH_POST_NORM_ADD=1` | `98.4101` | `91.4218` | `98.2423` | `97.6208` | `84.4608` | sql-debugging `85.7`, performance-hypotheses `91.3` |
| GPU3 | both flags | `94.1645` | `89.1194` | `96.7005` | `95.6340` | `84.8920` | code-review `84.0`, release-plan `89.1` |

Decision: **not promoted yet**. The single postnorm flags are close, especially
the branch-postnorm lane with p10 `91.42`, but neither cracked `100` on the
short screen and the combined lane regressed. A full512 confirmation was
launched under stamp `20260628T074233Z` with two paired controls. Promote only
if the full512 run repeats above `100`; otherwise record postnorm as another
near-miss/variance-level tweak.

Full512 confirmation (`20260628T074233Z`) rejected the postnorm flags:

| Lane | Extra env | Median 1-100 | p10 | Mean | Full512 | Wall512 | Summary |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| GPU0 | control A | `97.5809` | `87.3977` | `96.6564` | `93.2107` | `89.4393` | `data/gemma4-q8-gpu0-strict-vdr2-f16p021-bulksampled-postnorm-controlA-full512-20260628T074233Z/summary.json` |
| GPU1 | `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1` | `97.4245` | `89.7220` | `98.2513` | `91.1101` | `87.7937` | `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-postnorm-final-full512-20260628T074233Z/summary.json` |
| GPU2 | `LLAMA_GEMMA4_MOE_FUSED_BRANCH_POST_NORM_ADD=1` | `96.8636` | `84.6947` | `96.2041` | `92.1694` | `89.0369` | `data/gemma4-q8-gpu2-strict-vdr2-f16p021-bulksampled-postnorm-branch-full512-20260628T074233Z/summary.json` |
| GPU3 | control B | `96.5779` | `88.8513` | `96.7901` | `90.6939` | `87.6942` | `data/gemma4-q8-gpu3-strict-vdr2-f16p021-bulksampled-postnorm-controlB-full512-20260628T074233Z/summary.json` |

Final decision: **reject postnorm as a crack-100 lever**. The short-screen
spread was normal variance. Neither single flag improved the paired controls at
full512, and the best lane stayed below the current strict record.

## Level Zero immediate command-list screen (`20260628T074738Z`)

Question: several older Gemma diagnostic / LocalMaxxing lanes used
`UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, while the current strict launcher had not
been logging or setting it. Could immediate command lists shave enough runtime
overhead to turn the current `98.34` strict record into a reliable `>100`?

Before the run, the strict launcher scripts were patched to log Level Zero copy
engine and immediate-command-list identity fields in the run summary. The screen
used the current promoted stack, full512 strict realistic gate, fresh responses
only, `cached_tokens=0`, no history/prompt/KV reuse, and 128 canary rows.

| Lane | Extra Level Zero env | Median 1-100 | p10 | Mean | Full512 | Wall512 | Summary |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| GPU0 | `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1` | `96.8750` | `87.0159` | `96.1845` | `90.8072` | `88.0840` | `data/gemma4-q8-gpu0-strict-vdr2-f16p021-bulksampled-immediatecl1-A-full512-20260628T074738Z/summary.json` |
| GPU1 | `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1` | `97.5200` | `85.7327` | `96.7140` | `91.3768` | `87.8000` | `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-immediatecl1-B-full512-20260628T074738Z/summary.json` |
| GPU2 | `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `UR_L0_USE_COPY_ENGINE=0` | `95.0637` | `81.7491` | `94.5903` | `91.4350` | `87.9279` | `data/gemma4-q8-gpu2-strict-vdr2-f16p021-bulksampled-immediatecl1-urcopy0-full512-20260628T074738Z/summary.json` |
| GPU3 | `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, `SYCL_PI_LEVEL_ZERO_USE_COPY_ENGINE=0` | `94.4455` | `87.7937` | `96.2257` | `90.0656` | `86.5526` | `data/gemma4-q8-gpu3-strict-vdr2-f16p021-bulksampled-immediatecl1-syclcopy0-full512-20260628T074738Z/summary.json` |

Decision: **reject immediate command lists as a crack-100 lever** for the
current strict stack. All four lanes were valid and canary-clean, but the best
lane (`97.5200`) is below the current strict submitted record (`98.3405`) and
below reliable `100`. The copy-engine variants regressed further. Keep the new
identity logging because it is useful for comparing future runtime sweeps, but
do not set immediate command lists in the promoted recipe.

## Bulk sampled-ID + CPU affinity server thread sweep (`20260628T075325Z`)

Question: the submitted `98.3405` record already uses CPU affinity plus
`LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`. Could a smaller/larger server thread
count stabilize that family above `100`?

Full512 strict realistic gate, current promoted stack, fresh responses only,
`cached_tokens=0`, 128 canary rows:

| Lane | `THREADS` | CPU mask | Median 1-100 | p10 | Mean | Full512 | Wall512 | Summary |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| GPU0 | 6 | `0-3,16-19` | `99.8795` | `83.5042` | `97.9368` | `91.6324` | `88.1678` | `data/gemma4-q8-gpu0-strict-vdr2-f16p021-bulksampled-aff-th6-n3-nmin2-p00475-ub1024-full512-20260628T075325Z/summary.json` |
| GPU1 | 8 | `4-7,20-23` | `96.6102` | `87.0216` | `96.4278` | `90.2577` | `87.5299` | `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-aff-th8-control-n3-nmin2-p00475-ub1024-full512-20260628T075325Z/summary.json` |
| GPU2 | 10 | `8-11,24-27` | `93.7374` | `85.7566` | `94.8968` | `91.2770` | `88.4022` | `data/gemma4-q8-gpu2-strict-vdr2-f16p021-bulksampled-aff-th10-n3-nmin2-p00475-ub1024-full512-20260628T075325Z/summary.json` |
| GPU3 | 12 | `12-15,28-31` | `97.2128` | `87.9862` | `97.8664` | `89.0730` | `86.1755` | `data/gemma4-q8-gpu3-strict-vdr2-f16p021-bulksampled-aff-th12-n3-nmin2-p00475-ub1024-full512-20260628T075325Z/summary.json` |

Decision: **near miss, not promoted**. `THREADS=6` reached `99.8795` but did not
clear `100`, and its p10 (`83.50`) is weaker than the current submitted lane.
This is still useful because it is the closest strict full512 result since the
`101.0765` unroll6 variance outlier. Follow-up launched under a new stamp with
`THREADS=6` fixed while testing exact verifier argmax variants and immediate
command lists. Promote only if a follow-up clears `100` and repeats.

Follow-up (`20260628T075619Z`) did **not** hold the near miss:

| Lane | Extra env | Median 1-100 | p10 | Mean | Full512 | Wall512 | Summary |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| GPU0 | `THREADS=6` control | `95.0619` | `87.6729` | `96.8480` | `92.4812` | `88.8003` | `data/gemma4-q8-gpu0-strict-vdr2-f16p021-bulksampled-th6-control-n3-nmin2-p00475-ub1024-full512-20260628T075619Z/summary.json` |
| GPU1 | `THREADS=6`, `LLAMA_SPEC_VERIFY_RAW_ARGMAX=1` | `96.7692` | `86.9834` | `97.4508` | `89.4669` | `86.1611` | `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-th6-rawargmax-n3-nmin2-p00475-ub1024-full512-20260628T075619Z/summary.json` |
| GPU2 | `THREADS=6`, `LLAMA_SPEC_VERIFY_SOFTCAP_ARGMAX=1` | `96.2152` | `87.6616` | `96.8856` | `91.4455` | `88.5051` | `data/gemma4-q8-gpu2-strict-vdr2-f16p021-bulksampled-th6-softcapargmax-n3-nmin2-p00475-ub1024-full512-20260628T075619Z/summary.json` |
| GPU3 | `THREADS=6`, `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1` | `96.6097` | `85.7709` | `95.6361` | `91.5913` | `88.6645` | `data/gemma4-q8-gpu3-strict-vdr2-f16p021-bulksampled-th6-immediatecl1-n3-nmin2-p00475-ub1024-full512-20260628T075619Z/summary.json` |

Decision: **reject `THREADS=6` and verifier raw/softcap argmax as crack-100
levers**. The earlier `99.8795` was a valid near miss but not repeatable. Raw
and softcap verifier argmax remain effectively neutral/lossy on the current
bulk sampled-ID stack, matching earlier non-bulk results. Immediate command
lists again failed to improve the strict current stack.

## Gemma4 MoE router `TOP_K` screen on current strict stack (`20260628T075936Z`)

Question: for Gemma4 selected-softmax routing, can the guarded
`GGML_OP_TOP_K` route selection (`LLAMA_GEMMA4_MOE_TOP_K=1`) replace full
`argsort_top_k` and recover enough MoE routing overhead to clear `100`?

This was worth one current-stack retest because earlier top-k router tests were
on older synthetic/filled-long record families, not the current strict
realistic full512 stack. It remains exact in principle: top-k selects the same
expert set, and later selected-softmax / weighted sum keeps weights paired with
expert IDs.

Full512 strict realistic gate, current promoted stack, fresh responses only,
`cached_tokens=0`, 128 canary rows:

| Lane | Extra env | Median 1-100 | p10 | Mean | Full512 | Wall512 | Summary |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| GPU0 | `LLAMA_GEMMA4_MOE_TOP_K=1`, `THREADS=8`, unsorted | `90.2281` | `81.2466` | `91.0748` | `84.7166` | `81.8013` | `data/gemma4-q8-gpu0-strict-vdr2-f16p021-bulksampled-moe-topk-th8-unsorted-n3-nmin2-p00475-ub1024-full512-20260628T075936Z/summary.json` |
| GPU1 | `LLAMA_GEMMA4_MOE_TOP_K=1`, `LLAMA_GEMMA4_MOE_SORTED_TOP_K=1`, `THREADS=8` | `93.1279` | `85.1246` | `92.1122` | `85.6481` | `82.6880` | `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-moe-topk-th8-sorted-n3-nmin2-p00475-ub1024-full512-20260628T075936Z/summary.json` |
| GPU2 | `LLAMA_GEMMA4_MOE_TOP_K=1`, `THREADS=6`, unsorted | `89.4949` | `80.3368` | `89.2084` | `85.9215` | `82.0787` | `data/gemma4-q8-gpu2-strict-vdr2-f16p021-bulksampled-moe-topk-th6-unsorted-n3-nmin2-p00475-ub1024-full512-20260628T075936Z/summary.json` |
| GPU3 | `LLAMA_GEMMA4_MOE_TOP_K=1`, `LLAMA_GEMMA4_MOE_SORTED_TOP_K=1`, `THREADS=6` | `89.3535` | `79.6942` | `88.7621` | `81.6724` | `79.4476` | `data/gemma4-q8-gpu3-strict-vdr2-f16p021-bulksampled-moe-topk-th6-sorted-n3-nmin2-p00475-ub1024-full512-20260628T075936Z/summary.json` |

Decision: **reject `LLAMA_GEMMA4_MOE_TOP_K=1` on the current strict stack**.
The idea is exact/canary-safe but materially slower (`~89-93` median versus the
current `98.34` record family). Do not make top-k routing the default for this
recipe. The existing `argsort_top_k` route remains faster despite its apparent
extra work.

## Slow-prompt triad diagnostic + profile (`20260628T080659Z`)

Purpose: isolate the prompt cluster that caps the strict full-suite median and
avoid mistaking fast-prompt variance for a reliable crack-100 path. This suite
contains only `code-review`, `sql-debugging`, and `performance-hypotheses`, so
it is **diagnostic only** and must not be submitted or advertised as headline
throughput.

All lanes used the current promoted UD-Q8_K_XL + Q4_0 MTP stack, fresh
responses only, each prompt once, `cached_tokens=0`, `MAX_TOKENS=128`, and
`LLAMA_SERVER_SPEC_PROFILE=1` / `LLAMA_MTP_DRAFT_PROFILE=1`.

| Lane | Variant | Median 1-100 | p10 | Mean | Per-prompt 1-100 notes | Summary |
| --- | --- | ---: | ---: | ---: | --- | --- |
| GPU0 | control `n_max=3`, `n_min=2`, `ubatch=1024` | `90.9886` | `88.0616` | `90.0279` | code `91.77`, SQL `87.33`, perf `90.99` | `data/gemma4-q8-gpu0-slowtriad-control-n3-th8-20260628T080659Z/summary.json` |
| GPU1 | `THREADS=6` | `83.5446` | `83.0395` | `84.3705` | code `82.91`, SQL `86.65`, perf `83.54` | `data/gemma4-q8-gpu1-slowtriad-th6-n3-20260628T080659Z/summary.json` |
| GPU2 | `n_max=4` | `87.5706` | `83.2683` | `89.3446` | code `87.57`, SQL `98.27`, perf `82.19` | `data/gemma4-q8-gpu2-slowtriad-nmax4-th8-20260628T080659Z/summary.json` |
| GPU3 | `n_min=3`, `ubatch=720` | `92.3479` | `83.7577` | `88.9392` | code `81.61`, SQL `92.86`, perf `92.35` | `data/gemma4-q8-gpu3-slowtriad-nmin3-ub720-th8-20260628T080659Z/summary.json` |

Profile interpretation:

- The persistent median cap is prompt-specific. Fast prompts in the full suite
  already run above `100`; the slow cluster is what keeps strict full-suite
  repeats in the `95-98` band.
- `n_max=4` reduces decode calls and can help SQL (`98.27` in this triad), but
  raises verifier-row cost enough to hurt `performance-hypotheses` (`82.19`).
  This is not a general crack-100 lever.
- `n_min=3` / smaller ubatch shifts the loss to `code-review` (`81.61`). It is
  not a general fix either.
- `THREADS=6` was a repeat loss here, matching the failed follow-up after the
  `99.8795` near miss.
- Current direct-unroll MTP exports compact argmax IDs only. In that path,
  `p_min` and logit-gap do not prune drafted tokens, so more `p_min` sweeps are
  mostly variance unless a real score side channel is reintroduced.
- MTP/server profile deltas show the dominant cost is still target/verifier
  `process_ubatch` work. Draft decode is visible but smaller; host sampled-ID
  extraction is not large enough by itself to close the gap.

Decision: **no promotion**. The next credible >100 work is verifier-side source
work or a real confidence side channel, not broad p_min/thread/top-k/adaptive
sweeps. A bounded follow-up shape screen was launched with control, `ubatch`
neighborhood, and `n_max=4` under the full fixed realistic suite to make sure
the slow-triad conclusion survives the full prompt mix.

## Full-suite shape/depth screen after slow-triad diagnostic (`20260628T081448Z`)

Purpose: verify whether the slow-triad observations hold under the full fixed
realistic prompt suite and whether a nearby `ubatch` or `n_max=4` setting can
reliably crack `100` without leaning on repeated/warmed outputs.

All lanes used the current promoted UD-Q8_K_XL target + Q4_0 MTP draft stack,
fresh responses only, each prompt once, `cached_tokens=0`, `MAX_TOKENS=128`,
and the fixed 12-prompt realistic suite. This screen is diagnostic only: it is
not a promoted full512 result and it did not beat the existing strict record
(`98.3405` median 1-100 on full512).

| Lane | Variant | Median 1-100 | p10 | Mean | Per-prompt notes | Summary |
| --- | --- | ---: | ---: | ---: | --- | --- |
| GPU0 | control `n_max=3`, `n_min=2`, `ubatch=1024` | `95.8612` | `88.6957` | `97.1323` | code `85.55`, SQL `90.14`, perf `89.06`; fast prompts still >100 | `data/gemma4-q8-gpu0-crack100-shape-control-n3-ub1024-20260628T081448Z/summary.json` |
| GPU1 | `ubatch=896`, `n_max=3`, `n_min=2` | `98.1694` | `86.4630` | `97.5805` | improved code/email/release; hurt SQL/perf/decision; near miss only | `data/gemma4-q8-gpu1-crack100-shape-ub896-n3-20260628T081448Z/summary.json` |
| GPU2 | `ubatch=1152`, `n_max=3`, `n_min=2` | `97.6784` | `88.9106` | `96.2656` | decent median but perf collapsed to `77.71` | `data/gemma4-q8-gpu2-crack100-shape-ub1152-n3-20260628T081448Z/summary.json` |
| GPU3 | `n_max=4`, `ubatch=1024` | `89.1031` | `83.2385` | `91.9840` | SQL improved to `95.89`, but broad regression elsewhere | `data/gemma4-q8-gpu3-crack100-shape-n4-ub1024-20260628T081448Z/summary.json` |

Decision: **no promotion**. `ubatch=896` is the only useful near miss in this
screen, but it did not beat the current valid record and worsened the lower
tail. `ubatch=1152` and `n_max=4` are rejected for this stack. Combined with
the slow-triad profile, this points away from more runtime shape churn and back
toward source-level verifier/target-cost reduction if we want a reliable
`>100` fresh-response result.

## Runtime combo screen: `ubatch=896` plus verifier/postnorm flags (`20260628Tnow`)

Purpose: one bounded follow-up before moving to kernel/source work. Combine the
only near-neutral runtime shape (`ubatch=896`) with the verifier/postnorm flags
that had previously been close or neutral, under the fixed realistic suite.

All lanes used fresh responses only, each prompt once, `cached_tokens=0`,
`MAX_TOKENS=128`, `CANARY_REPEATS=8`, UD-Q8_K_XL target, Q4_0 MTP draft, and
the current VDR2/F16 p021/bulk sampled-ID stack.

| Lane | Variant | Median 1-100 | p10 | Mean | Gate | Summary |
| --- | --- | ---: | ---: | ---: | --- | --- |
| GPU0 | control `ubatch=1024` | `96.6195` | `91.7071` | `98.1173` | pass | `data/gemma4-q8-gpu0-crack100-combo-control-20260628Tnow/summary.json` |
| GPU1 | `ubatch=896`, `LLAMA_SPEC_VERIFY_RAW_ARGMAX=1` | **`102.2126`** | `89.6575` | `99.5490` | pass | `data/gemma4-q8-gpu1-crack100-combo-ub896-rawargmax-20260628Tnow/summary.json` |
| GPU2 | `ubatch=896`, `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1` | `95.8198` | `86.9386` | `97.4098` | pass | `data/gemma4-q8-gpu2-crack100-combo-ub896-finalpost-20260628Tnow/summary.json` |
| GPU3 | `ubatch=896`, `LLAMA_GEMMA4_MOE_FUSED_BRANCH_POST_NORM_ADD=1` | `94.3481` | `86.9637` | `94.5662` | pass | `data/gemma4-q8-gpu3-crack100-combo-ub896-branchpost-20260628Tnow/summary.json` |

Decision: **candidate only, not promoted yet**. `ubatch=896 + raw verifier
argmax` is the first fresh strict screen in this lane to crack `100`, but it
must survive full512 repeat confirmation before being called reliable. The
postnorm combinations regressed and remain rejected as crack-100 levers. A
four-GPU full512 repeat of `ubatch=896 + LLAMA_SPEC_VERIFY_RAW_ARGMAX=1` was
launched next.

## Full512 confirmation: `ubatch=896 + raw verifier argmax` (`20260628T082311Z`)

Purpose: confirm whether the short-screen `102.21 tok/s` candidate reliably
cracks `100` under the stricter promoted-result shape: `MAX_TOKENS=512`,
`CANARY_REPEATS=32`, fixed realistic prompt suite, each prompt once, and
`cached_tokens=0` for every request.

All four lanes used the same UD-Q8_K_XL target, Q4_0 MTP draft, direct-ID MTP
stack, `n_max=3`, `n_min=2`, `p_min=0.0475`, `ubatch=896`, and
`LLAMA_SPEC_VERIFY_RAW_ARGMAX=1`.

| Lane | Median 1-100 | p10 | Mean | Full512 median | TTFT median | Validity | Summary |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 / A | `99.866` | `89.381` | `100.825` | `91.988` | `178.7 ms` | canary pass, cached0 | `data/gemma4-q8-gpu0-crack100-ub896-rawargmax-full512-A-20260628T082311Z/summary.json` |
| GPU1 / B | `95.980` | `84.716` | `96.369` | `89.661` | `179.9 ms` | canary pass, cached0 | `data/gemma4-q8-gpu1-crack100-ub896-rawargmax-full512-B-20260628T082311Z/summary.json` |
| GPU2 / C | `98.455` | `85.074` | `98.457` | `92.240` | `179.1 ms` | canary pass, cached0 | `data/gemma4-q8-gpu2-crack100-ub896-rawargmax-full512-C-20260628T082311Z/summary.json` |
| GPU3 / D | `92.364` | `85.937` | `94.001` | `90.028` | `179.8 ms` | canary pass, cached0 | `data/gemma4-q8-gpu3-crack100-ub896-rawargmax-full512-D-20260628T082311Z/summary.json` |

Decision: **no promotion**. The run is valid, fresh-response, and clean on the
canary/`cached_tokens=0` checks, but it does **not** crack `100` reliably. The
short-screen `102.21` was a useful diagnostic signal, not a stable headline
result. `LLAMA_SPEC_VERIFY_RAW_ARGMAX=1` may be kept as an optional near-neutral
variant, but it is not a record-breaking lever by itself and should not be
submitted to LocalMaxxing.

Next lane: source-level exact reduction of MTP overhead. The most credible
remaining low-risk candidate is `LLAMA_MTP_DRAFT_DEVICE_H_HANDOFF=1`, which
keeps target/draft quality unchanged and attempts to avoid host-side handoff
work between target `h_nextn` and the draft model.

## Device handoff screen (`20260628T082656Z`)

Purpose: test the exact `LLAMA_MTP_DRAFT_DEVICE_H_HANDOFF=1` path suggested by
the MTP audit. This keeps the same target model, draft model, quantization, and
verification policy, but copies target `h_nextn` directly into the draft input
tensor and skips host embedding upload.

All lanes used the fixed realistic suite, fresh responses only, each prompt
once, `cached_tokens=0`, `MAX_TOKENS=128`, and `CANARY_REPEATS=8`.

| Lane | Variant | Median 1-100 | p10 | Mean | Full128 median | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | control `ubatch=1024` | `99.187` | `87.305` | `97.939` | `96.357` | pass/cached0 | `data/gemma4-q8-gpu0-crack100-handoff-control-ub1024-20260628T082656Z/summary.json` |
| GPU1 | handoff, `ubatch=1024` | `97.114` | `87.170` | `96.862` | `92.861` | pass/cached0 | `data/gemma4-q8-gpu1-crack100-handoff-ub1024-20260628T082656Z/summary.json` |
| GPU2 | handoff, `ubatch=896` | `97.922` | `84.829` | `97.174` | `97.494` | pass/cached0 | `data/gemma4-q8-gpu2-crack100-handoff-ub896-20260628T082656Z/summary.json` |
| GPU3 | handoff, `ubatch=896`, raw verifier argmax | `100.858` | `86.002` | `98.535` | `97.565` | pass/cached0 | `data/gemma4-q8-gpu3-crack100-handoff-ub896-rawargmax-20260628T082656Z/summary.json` |

Server logs confirm the handoff mode activated:
`draft_device_h_handoff=1` and `MTP draft device-resident h_nextn handoff
enabled`.

Decision: **candidate only, not promoted**. Handoff by itself was not a win, and
the only lane over `100` was the same fragile `ubatch=896 + rawargmax` shape
with handoff added. A four-GPU full512 confirmation of
`ubatch=896 + rawargmax + handoff` was launched next. If that confirmation does
not reliably hold `>100`, the handoff lane is rejected as a headline lever.

## Full512 confirmation: `ubatch=896 + rawargmax + handoff` (`20260628T082903Z`)

Purpose: test whether the only handoff screen lane above `100` survives the
same full512 confirmation that rejected plain `ubatch=896 + rawargmax`.

All four lanes used `MAX_TOKENS=512`, `CANARY_REPEATS=32`, fresh fixed
realistic suite rows, `cached_tokens=0`, UD-Q8_K_XL target, Q4_0 MTP draft,
`ubatch=896`, `LLAMA_SPEC_VERIFY_RAW_ARGMAX=1`, and
`LLAMA_MTP_DRAFT_DEVICE_H_HANDOFF=1`.

| Lane | Median 1-100 | p10 | Mean | Full512 median | TTFT median | Validity | Summary |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 / A | `94.863` | `88.802` | `96.937` | `90.208` | `179.0 ms` | canary pass, cached0 | `data/gemma4-q8-gpu0-crack100-handoff-ub896-rawargmax-full512-A-20260628T082903Z/summary.json` |
| GPU1 / B | `97.557` | `87.126` | `96.475` | `90.558` | `180.0 ms` | canary pass, cached0 | `data/gemma4-q8-gpu1-crack100-handoff-ub896-rawargmax-full512-B-20260628T082903Z/summary.json` |
| GPU2 / C | `99.769` | `88.830` | `98.429` | `92.384` | `179.3 ms` | canary pass, cached0 | `data/gemma4-q8-gpu2-crack100-handoff-ub896-rawargmax-full512-C-20260628T082903Z/summary.json` |
| GPU3 / D | `92.941` | `86.040` | `95.511` | `90.604` | `179.5 ms` | canary pass, cached0 | `data/gemma4-q8-gpu3-crack100-handoff-ub896-rawargmax-full512-D-20260628T082903Z/summary.json` |

Decision: **reject for promotion**. Device handoff is exact and activates, but
it does not make the `ubatch=896 + rawargmax` near miss reliable. The best lane
reached only `99.769`, and the spread remains wide. Do not submit this to
LocalMaxxing. Handoff may still be useful for profiling, but it is not a
headline crack-100 lever in the current stack.

Next action: stop broad runtime sweeps. The reliable `>100` path now requires a
source-level reduction in target/verifier compute, most likely around the final
norm/LM-head verifier path or a narrow MoE micro-kernel change. The broad
fused-down/GEGLU-down families have already been tried and rejected in prior
notes, so avoid re-running those as plain env toggles.

## Current-stack top2 score side-channel retest (`20260628T092011Z`)

Purpose: retest the direct-argmax top1/top2 score side-channel on the current
strict VDR2/F16-p021/bulk sampled-ID stack, but at the actual useful MTP depth
(`n_max=3`) instead of the earlier deep-unroll experiments. The hope was that
top1 probability or top1/top2 logit gap could reject weak drafts and improve
the lower tail enough to make `>100 tok/s` reliable.

Shared setup: fixed realistic suite, fresh responses only, each prompt once,
`cached_tokens=0`, `MAX_TOKENS=128`, `CANARY_REPEATS=8`, UD-Q8_K_XL target,
Q4_0 MTP draft, `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_SCORES=1`, direct-ID draft
argmax, bulk verifier sampled IDs, `UBATCH_SIZE=1024`.

| Lane | Variant | Median 1-100 | p10 | Mean | Full128 median | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | score-channel control, `n_min=2`, `p_min=0.0475` | `94.951` | `85.670` | `96.011` | `95.729` | pass/cached0 | `data/gemma4-q8-gpu0-top2scores-control-p00475-nmin2-128-20260628T092011Z/summary.json` |
| GPU1 | stricter `p_min=0.60`, `n_min=2` | `94.545` | `86.108` | `96.970` | `93.472` | pass/cached0 | `data/gemma4-q8-gpu1-top2scores-p060-nmin2-128-20260628T092011Z/summary.json` |
| GPU2 | `p_min=0.70`, `n_min=1` | `96.129` | `85.273` | `95.166` | `97.422` | pass/cached0 | `data/gemma4-q8-gpu2-top2scores-p070-nmin1-128-20260628T092011Z/summary.json` |
| GPU3 | `logit_gap_min=0.50`, `n_min=1`, `p_min=0.0475` | `96.718` | `89.350` | `98.059` | `96.399` | pass/cached0 | `data/gemma4-q8-gpu3-top2scores-gap050-nmin1-128-20260628T092011Z/summary.json` |

Decision: **reject as a crack-100 lever**. The side-channel is correctness-safe
and useful diagnostically, but it did not improve the current `n_max=3` strict
lane. The profile showed average draft top1 confidence already around
`0.915-0.918` and average logit gap around `8.3-8.6`, so the new gates mostly
add compact-output bandwidth and reject a small number of drafts instead of
raising accepted throughput. Keep the default-off patch as a research artifact;
do not promote or submit any top2-score result.

Implication: reliable `>100` still needs target/verifier-side latency reduction
or variance reduction. More MTP confidence gating and deeper MTP depth are
exhausted for this stack.

## Strict realistic transfer check: old synthetic `n=7` shape (`20260628T092909Z`)

Purpose: test whether the older synthetic high-throughput VDR2 shape
(`n_max=7`, `n_min=3`, `p_min=0.10`) transfers to the fixed realistic
fresh-response suite. This was a necessary control because synthetic or repeated
prompt screens can make deeper speculation look much better than it is for cold
first responses.

Shared setup: UD-Q8_K_XL target, Q4_0 MTP draft, VDR2/F16-p021/bulk sampled-ID
stack, fixed realistic suite, fresh responses only, each prompt once,
`cached_tokens=0`, `MAX_TOKENS=128`, `CANARY_REPEATS=8`. The control used the
current promoted `n_max=3`, `n_min=2`, `p_min=0.0475`, `ubatch=1024` shape.

| Lane | Variant | Median 1-100 | p10 | Mean | Full128 median | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | `n=7`, `n_min=3`, `p=0.10`, `ubatch=720` | `77.570` | `73.567` | `78.777` | `79.208` | pass/cached0 | `data/gemma4-q8-gpu0-strict-vdr2-n7-nmin3-p010-ub720-128-20260628T092909Z/summary.json` |
| GPU1 | `n=7`, `n_min=3`, `p=0.10`, `ubatch=704` | `76.575` | `66.519` | `77.261` | `78.299` | pass/cached0 | `data/gemma4-q8-gpu1-strict-vdr2-n7-nmin3-p010-ub704-128-20260628T092909Z/summary.json` |
| GPU2 | `n=7`, `n_min=3`, `p=0.10`, `ubatch=768` | `81.997` | `69.649` | `82.146` | `80.960` | pass/cached0 | `data/gemma4-q8-gpu2-strict-vdr2-n7-nmin3-p010-ub768-128-20260628T092909Z/summary.json` |
| GPU3 | control `n=3`, `n_min=2`, `p=0.0475`, `ubatch=1024` | `95.898` | `88.394` | `97.285` | `95.691` | pass/cached0 | `data/gemma4-q8-gpu3-strict-vdr2-control-n3-nmin2-p00475-ub1024-128-20260628T092909Z/summary.json` |

Decision: **reject**. The deep synthetic speculation shape does not transfer to
fresh realistic prompts; it over-verifies weak drafts and collapses median
throughput to `76-82 tok/s` while the same run's control stays near `96 tok/s`.
Do not use `n=7/n_min=3/p=0.10` for real-world claims or further crack-100
work unless a new verifier/draft mechanism changes the acceptance economics.
Keep `n=3/n_min=2/p=0.0475` as the strict baseline.

## Full512 crossover repeat: variance check for near-100 lanes (`20260628T093402Z`)

Purpose: re-test the strongest near-miss runtime lanes under the promoted
full512 strict gate before writing more source code. All lanes used the fixed
realistic prompt suite, fresh responses only, each prompt once,
`cached_tokens=0`, `MAX_TOKENS=512`, `CANARY_REPEATS=32`, UD-Q8_K_XL target,
Q4_0 MTP draft, VDR2/F16-p021/bulk sampled-ID stack, and no history or cache
reuse.

| Lane | Variant | Median 1-100 | p10 | Mean | Full512 median | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | control `n=3`, `n_min=2`, `p=0.0475`, `ubatch=1024`, `threads=8` | `98.208` | `86.712` | `97.247` | `91.090` | pass/cached0 | `data/gemma4-q8-gpu0-crack100-xover-control-full512-20260628T093402Z/summary.json` |
| GPU1 | `ubatch=896`, `LLAMA_SPEC_VERIFY_RAW_ARGMAX=1` | `92.425` | `85.930` | `94.697` | `90.970` | pass/cached0 | `data/gemma4-q8-gpu1-crack100-xover-ub896-rawargmax-full512-20260628T093402Z/summary.json` |
| GPU2 | `THREADS=6`, core affinity | `97.938` | `89.130` | `97.419` | `89.970` | pass/cached0 | `data/gemma4-q8-gpu2-crack100-xover-th6-aff-full512-20260628T093402Z/summary.json` |
| GPU3 | `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=6` | `95.559` | `85.569` | `95.937` | `91.651` | pass/cached0 | `data/gemma4-q8-gpu3-crack100-xover-unroll6-full512-20260628T093402Z/summary.json` |

Decision: **no runtime promotion**. The control lane repeated near the current
record, but none of the near-miss runtime variants cracked `100` under the
full512 strict gate. The `ubatch=896 + rawargmax` lane in particular fell from
earlier `99-102` screens to `92.4`, confirming it is variance/noise rather
than a reliable lever. `THREADS=6` and `unroll=6` are also not stable
improvements. Reliable `>100` now requires a source-level target/verifier
latency reduction.

Source implication: current strict control still materializes full F32 target
logits and then emits compact sampled IDs; `LLAMA_SPEC_VERIFY_RAW_ARGMAX=1`
only skips post-LM-head softcap and is not enough. Existing fused
projection+argmax and router `top_k` paths were already rejected at scale. The
next real patch should either make a small-`nvec` fused verifier LM-head argmax
competitive with the full logits path, or reduce Gemma4 MoE verifier body cost.

## Adaptive MTP strict screen (`20260628T0943Z`)

Purpose: check whether the existing server-side adaptive MTP cap can cheaply
raise the lower tail enough to make `>100 tok/s` reliable before writing source
code. This is a strict **screen**, not a promotion: fixed realistic prompt
suite, fresh responses only, each prompt once, `cached_tokens=0`,
`MAX_TOKENS=128`, `CANARY_REPEATS=8`, UD-Q8_K_XL target, Q4_0 MTP draft,
VDR2/F16-p021/bulk sampled-ID stack, no history/cache reuse.

Adaptive policy implementation note: the server keeps an EMA of
`accepted_draft / drafted` per request, caps `n_max` when the EMA is below
`LLAMA_SPEC_ADAPTIVE_MTP_LOW`, and uncaps when above
`LLAMA_SPEC_ADAPTIVE_MTP_HIGH`. It can reduce bad verification work, but it
cannot create more accepted tokens on good rows.

| Lane | Variant | Median 1-100 | p10 | Mean | Full128 median | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | control `n=3`, `n_min=2`, `p=0.0475` | `95.366` | `88.705` | `96.951` | `94.453` | pass/cached0 | `data/gemma4-q8-gpu0-crack100-adapt-control-128/summary.json` |
| GPU1 | default adaptive, `n=3` | `93.596` | `85.095` | `92.835` | `92.506` | pass/cached0 | `data/gemma4-q8-gpu1-crack100-adapt-default-128/summary.json` |
| GPU2 | adaptive `low_n_max=1`, low/high `0.46/0.58`, `n=3` | `71.879` | `67.167` | `75.857` | `70.377` | pass/cached0 | `data/gemma4-q8-gpu2-crack100-adapt-low1-128/summary.json` |
| GPU3 | adaptive `n=4`, `low_n_max=2`, low/high `0.50/0.64` | `90.266` | `84.992` | `91.662` | `91.209` | pass/cached0 | `data/gemma4-q8-gpu3-crack100-adapt-n4-128/summary.json` |

Decision: **reject adaptive MTP as a crack-100 lever**. Default adaptive loses
throughput, the aggressive cap collapses output speed, and `n=4` with adaptive
fallback still over-verifies weak drafts. The current `n=3/n_min=2/p=0.0475`
shape remains the best strict baseline. Reliable `>100` needs source-level
target/verifier latency reduction, not more runtime policy gating.

## Top1-only argmax reduction patch screen (`20260628T1004Z`)

Purpose: test whether simplifying the SYCL Q-vector argmax kernels for the
top1-only path can reduce draft/verifier argmax overhead enough to make strict
`>100 tok/s` reliable. The patch keeps the existing top2-capable kernels but
adds fast top1-only reductions in `ggml/src/ggml-sycl/mmvq.cpp`, avoiding
second-best bookkeeping when `top2 == false`.

Shared setup: fixed realistic prompt suite, fresh responses only, each prompt
once, `cached_tokens=0`, `MAX_TOKENS=128`, `CANARY_REPEATS=8`, UD-Q8_K_XL
target, Q4_0 MTP draft, VDR2/F16-p021/bulk sampled-ID stack, `n_max=3`,
`n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`.

| Lane | Variant | Median 1-100 | p10 | Mean | Full128 median | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | patched control, no verifier-fused argmax | `99.289` | `85.802` | `97.713` | `98.779` | pass/cached0 | `data/gemma4-q8-gpu0-top1argmax-control-128/summary.json` |
| GPU1 | `LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1`, default tile shape | `88.365` | `76.023` | `86.693` | `86.538` | pass/cached0 | `data/gemma4-q8-gpu1-top1argmax-verifierfused-default-128/summary.json` |
| GPU2 | verifier-fused argmax, `LLAMA_SYCL_MUL_MAT_ARGMAX_TILE_SUBGROUPS=16` | `85.682` | `75.354` | `84.929` | `83.067` | pass/cached0 | `data/gemma4-q8-gpu2-top1argmax-verifierfused-tile16-128/summary.json` |
| GPU3 | verifier-fused argmax, `LLAMA_SYCL_MUL_MAT_ARGMAX_TILE_SUBGROUPS=4` | `84.114` | `73.948` | `83.520` | `83.473` | pass/cached0 | `data/gemma4-q8-gpu3-top1argmax-verifierfused-tile4-128/summary.json` |

Decision: **do not promote the verifier-fused argmax path**. The patch did not
make `LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1` competitive; all fused verifier
lanes are still far below the current strict record. The patched non-fused
control at `99.289 tok/s` is interesting but only a 128-token screen and may be
variance. It must pass full512 repeated validation before this patch is kept or
submitted.

Next action: run multiple full512 patched-control repeats against the strict
gate. If the patch does not move the full512 median above the current
`98.340 tok/s` record reliably, treat it as a negative/neutral source patch and
revert or archive it rather than promoting.

### Full512 follow-up: top1-only argmax reduction does not promote

Four full512 strict patched-control repeats were run immediately after the
screen. All used the fixed realistic suite, each prompt once, `cached_tokens=0`,
`MAX_TOKENS=512`, `CANARY_REPEATS=32`, same target/draft quantization, and the
same promoted `n=3/n_min=2/p_min=0.0475/ubatch=1024` stack. No verifier-fused
argmax was enabled in these follow-up lanes.

| Lane | Median 1-100 | p10 | Mean | Full512 median | Validity | Summary |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | `97.766` | `86.674` | `98.059` | `89.853` | pass/cached0 | `data/gemma4-q8-gpu0-top1argmax-control-full512-A/summary.json` |
| GPU1 | `97.273` | `83.141` | `94.983` | `90.972` | pass/cached0 | `data/gemma4-q8-gpu1-top1argmax-control-full512-B/summary.json` |
| GPU2 | `92.604` | `84.936` | `93.313` | `89.651` | pass/cached0 | `data/gemma4-q8-gpu2-top1argmax-control-full512-C/summary.json` |
| GPU3 | `96.082` | `87.362` | `96.943` | `90.935` | pass/cached0 | `data/gemma4-q8-gpu3-top1argmax-control-full512-D/summary.json` |

Decision: **reject / revert from the active lane**. The 128-token `99.289`
screen did not survive full512 validation; the best repeat (`97.766`) is below
the current `98.340` strict record, and the patch does not crack `100`
reliably. It also leaves the verifier-fused argmax family clearly negative.
Archive this as a useful negative result: top1 bookkeeping simplification is
not enough; the useful source target remains a real multi-row verifier LM-head
argmax that reuses output-weight loads across verifier rows, or a different
target-body latency reduction.

## Multi-vector verifier LM-head argmax reuse patch (`20260628T1030Z`)

Purpose: make the rejected verifier-fused LM-head argmax path competitive by
reusing output-weight loads across verifier rows. The prior fused path launched
one tile per `(vocab tile, verifier row)`, so it reread the same LM-head tile
for each verifier vector. The new default-off source path handles `nvec=2..8`
inside one tile workgroup and writes the existing vector-major scratch layout,
preserving the same final reducer/tie-breaking semantics.

Patch identity:

- source tree:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926`;
- main file:
  `ggml/src/ggml-sycl/mmvq.cpp`;
- env gate:
  `LLAMA_SYCL_MUL_MAT_ARGMAX_MULTI_REUSE=1`;
- requires the already-rejected fused verifier path:
  `LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1`;
- tile sweep also tested:
  `LLAMA_SYCL_MUL_MAT_ARGMAX_TILE_SUBGROUPS=16/8/4/2`;
- source status:
  default-off experiment artifact, **not** part of the promoted recipe.

Important reproducibility note: the first 128-token run used the wrong env name
(`LLAMA_GEMMA4_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1`), so the fused verifier path
was not active. Treat that lane as a control/typo artifact, not a patch result.
The harness was updated afterward to record
`LLAMA_SYCL_MUL_MAT_ARGMAX_MULTI_REUSE` in server logs and summaries.

Correct-env strict 128-token screen:

| Lane | Median 1-100 | p10 | Mean | Full128 | Validity | Summary |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| fused + multi-reuse | `99.512` | `84.874` | `98.433` | `100.302` | pass/cached0 | `data/gemma4-q8-gpu0-argmaxreuse-fused-correctenv-128/summary.json` |

Full512 confirmation with fused + multi-reuse enabled on all four GPUs:

| Lane | Median 1-100 | p10 | Mean | Full512 | Validity | Summary |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0/A | `97.424` | `92.494` | `98.011` | `89.693` | pass/cached0 | `data/gemma4-q8-gpu0-argmaxreuse-fused-full512-A/summary.json` |
| GPU1/B | `97.604` | `87.745` | `97.318` | `93.468` | pass/cached0 | `data/gemma4-q8-gpu1-argmaxreuse-fused-full512-B/summary.json` |
| GPU2/C | `90.438` | `84.935` | `93.715` | `89.860` | pass/cached0 | `data/gemma4-q8-gpu2-argmaxreuse-fused-full512-C/summary.json` |
| GPU3/D | `96.615` | `88.756` | `97.067` | `94.122` | pass/cached0 | `data/gemma4-q8-gpu3-argmaxreuse-fused-full512-D/summary.json` |

Tile-subgroup 128-token follow-up:

| Lane | Tile subgroups | Median 1-100 | p10 | Mean | Full128 | Validity | Summary |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | 16 | `95.029` | `87.896` | `95.597` | `95.433` | pass/cached0 | `data/gemma4-q8-gpu0-argmaxreuse-fused-tile16-128/summary.json` |
| GPU1 | 8 | `97.975` | `90.229` | `97.332` | `99.229` | pass/cached0 | `data/gemma4-q8-gpu1-argmaxreuse-fused-tile8-128/summary.json` |
| GPU2 | 4 | `98.294` | `85.104` | `96.148` | `98.011` | pass/cached0 | `data/gemma4-q8-gpu2-argmaxreuse-fused-tile4-128/summary.json` |
| GPU3 | 2 | `96.341` | `87.039` | `96.047` | `93.825` | pass/cached0 | `data/gemma4-q8-gpu3-argmaxreuse-fused-tile2-128/summary.json` |

Decision: **reject for promotion**. The multi-vector reuse design improves the
old fused verifier argmax family dramatically versus the `82-88 tok/s` fused
baseline, but it still does not beat the promoted bulk sampled-ID path and does
not reliably crack `100` at full512. Tile tuning did not rescue it. Do not
submit any of these runs to LocalMaxxing.

Implication: the full-logits/backend-argmax path remains better despite doing
more apparent work, likely because its dense multi-column LM-head matmul gets
better reuse/occupancy than the custom argmax tile. Future LM-head work should
not be another small tile-geometry tweak on this kernel; it would need either a
full-logits-compatible compact-output path or a different way to reduce target
body cost before the LM head.

## Unroll6 + postnorm full512 repeat (`20260628Tnow`)

Purpose: re-test the one `>100` strict full512 outlier shape (`unroll6` +
bulk sampled IDs) and combine it with the Gemma4 postnorm fusion knobs suggested
by source audit. This is a full512 strict/fresh validation, not a 128-token
screen: fixed realistic suite, each prompt once, all `cached_tokens=0`, no
history/ngram/cache acceleration.

Common identity:

- source tree:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926`;
- commit identity reported by harness:
  `c926ad098`;
- target:
  Gemma 4 26B A4B IT `Q8_0` GGUF, single B70 GPU, llama.cpp SYCL;
- MTP:
  draft-MTP `n_max=3`, `n_min=2`, `p_min=0.0475`, direct argmax unroll `6`,
  verifier bulk sampled IDs enabled, `--no-spec-draft-backend-sampling`;
- validity:
  `MAX_TOKENS=512`, `CANARY_REPEATS=32`, `REALISTIC_GATE=1`.

Results:

| Lane | Variant | Median 1-100 | p10 | Mean | Full512 | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | unroll6 bulk repeat | `98.027` | `88.083` | `98.149` | `90.670` | pass/cached0 | `data/gemma4-q8-gpu0-crack100-unroll6-bulk-repeat3-full512-20260628Tnow/summary.json` |
| GPU1 | + final postnorm residual | `93.863` | `85.960` | `96.048` | `92.482` | pass/cached0 | `data/gemma4-q8-gpu1-crack100-unroll6-bulk-finalpost-full512-20260628Tnow/summary.json` |
| GPU2 | + branch postnorm add | `96.521` | `86.568` | `95.123` | `91.443` | pass/cached0 | `data/gemma4-q8-gpu2-crack100-unroll6-bulk-branchpost-full512-20260628Tnow/summary.json` |
| GPU3 | + both postnorm fusions | `95.872` | `86.570` | `96.778` | `90.467` | pass/cached0 | `data/gemma4-q8-gpu3-crack100-unroll6-bulk-bothpost-full512-20260628Tnow/summary.json` |

Decision: **reject for promotion / no LocalMaxxing submission**. The clean
unroll6 repeat did not reproduce the old `101.08` outlier, and every postnorm
fusion variant was below the promoted `98.34` record. Treat final/branch
postnorm fusions as exhausted for the current bulk-sampled MTP stack. The next
useful work should be source-level verifier/body changes, not more postnorm or
runtime knob churn.

Source cleanup follow-up: the rejected `LLAMA_SYCL_MUL_MAT_ARGMAX_MULTI_REUSE`
hook was removed from the active llama.cpp source after these runs; the
negative result remains preserved here and in
`patches/gemma4-26b-a4b-q8-b70/20260628T1030-mulmat-argmax-multivec-reuse-negative.md`.

## Staged MTP3 verifier split (`20260628T112151Z`)

Purpose: avoid verifying all 4 target rows when the first or second draft token
is going to fail. The source experiment split target verification into Stage A
(rows 0-1) and Stage B (rows 2-3), gated by `LLAMA_SPEC_VERIFY_STAGE_MTP3=1`.
This preserves target-model verification semantics, but pays an extra target
decode when the first two draft tokens pass.

Patch identity:

- source tree:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926`;
- touched files:
  `tools/server/server-context.cpp`, `common/speculative.cpp`,
  `common/speculative.h`;
- env gate:
  `LLAMA_SPEC_VERIFY_STAGE_MTP3=1`;
- validation:
  strict/fresh 128-token suite, `CANARY_REPEATS=32`, `REALISTIC_GATE=1`,
  all `cached_tokens=0`.

Result:

| Lane | Median 1-100 | p10 | Mean | Full128 | Validity | Summary |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | `78.100` | `72.944` | `77.278` | `78.209` | pass/cached0 | `data/gemma4-q8-gpu0-stage-mtp3-strict128-smoke-20260628T112151Z/summary.json` |
| GPU1 profiled rerun | `72.681` | `71.221` | `73.050` | `73.788` | pass/cached0 | `data/gemma4-q8-gpu1-stage-mtp3-profile-strict128-20260628T200213Z/summary.json` |

Decision: **reject**. The current MTP stack already drafts high-confidence
tokens often enough that splitting the verifier costs far more than it saves.
Do not promote this path or spend full512 time on it. Future verifier work
should avoid extra target decode calls.

2026-06-28 profiled rerun note: adding `LLAMA_MTP_DRAFT_PROFILE=1`,
`LLAMA_MTP_DECODE_PHASE_PROFILE=1`, and
`LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1` made the row slower (`72.681`), not
better. The profile confirms this path is target/verifier-forward dominated:
final cumulative counters showed `target process_ubatch_ms=50061.620`,
`post_extract_ms=4342.406`, and `sampled_extract_ms=4341.895`, while draft
decode remained much smaller (`draft process_ubatch_ms=2139.800`). This closes
Stage-MTP3 as a crack-100 candidate for the current strict Q8 stack.

## Rawargmax + ubatch neighborhood full512 sweep (`20260628T112556Z`)

Purpose: revisit the nearest observed runtime family (`LLAMA_SPEC_VERIFY_RAW_ARGMAX=1`
plus `UBATCH_SIZE=896`) that produced some strict 128-token `>100` screens but
failed repeatability. This sweep tested nearby ubatch sizes under full512
fresh-response validation to see whether a stable pocket exists.

Common identity:

- source tree:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926`;
- target:
  Gemma 4 26B A4B IT `UD-Q8_K_XL` GGUF, single B70 GPU, llama.cpp SYCL;
- MTP:
  draft-MTP `n_max=3`, `n_min=2`, `p_min=0.0475`, direct argmax unroll `7`,
  verifier bulk sampled IDs enabled, `LLAMA_SPEC_VERIFY_RAW_ARGMAX=1`,
  `--no-spec-draft-backend-sampling`;
- validity:
  `MAX_TOKENS=512`, `CANARY_REPEATS=32`, `REALISTIC_GATE=1`,
  fixed realistic suite, each prompt once, all `cached_tokens=0`.

Results:

| Lane | UBatch | Median 1-100 | p10 | Mean | Full512 | Validity | Summary |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | 832 | `97.197` | `86.966` | `96.891` | `92.906` | pass/cached0 | `data/gemma4-q8-gpu0-crack100-rawargmax-ub832-full512-20260628T112556Z/summary.json` |
| GPU1 | 864 | `96.824` | `88.708` | `97.373` | `93.064` | pass/cached0 | `data/gemma4-q8-gpu1-crack100-rawargmax-ub864-full512-20260628T112556Z/summary.json` |
| GPU2 | 928 | `93.733` | `85.204` | `94.456` | `89.962` | pass/cached0 | `data/gemma4-q8-gpu2-crack100-rawargmax-ub928-full512-20260628T112556Z/summary.json` |
| GPU3 | 960 | `97.673` | `89.448` | `97.864` | `90.074` | pass/cached0 | `data/gemma4-q8-gpu3-crack100-rawargmax-ub960-full512-20260628T112557Z/summary.json` |

Decision: **reject for promotion / no LocalMaxxing submission**. The nearby
ubatch sizes are valid fresh-response runs, but none beats the promoted
`98.340` record or cracks `100` reliably. Combined with the earlier `ub896`
full512 repeats and xover runs, treat `RAW_ARGMAX + ubatch tuning` as exhausted
for the current stack. The remaining plausible path is source-level reduction
of target verifier/body overhead without changing target-verified sampling.

## Deferred target `h_nextn` accept-only cleanup (`20260628T1138-1149Z`)

Purpose: test whether the target `h_nextn` extraction could be delayed even
further by skipping the pre-verification copy and copying only the accepted row
in `common_speculative_accept()`. This was gated by
`LLAMA_MTP_DEFER_TARGET_H_ACCEPT_ONLY=1` on top of the existing promoted
`LLAMA_MTP_DEFER_TARGET_H_NEXTN=1` path. Token verification semantics were
unchanged; this only removed a candidate host/device row copy.

Validation: strict/fresh 128-token realistic suite, each prompt once,
`cached_tokens=0`, canary pass required. One early GPU0 smoke accidentally
omitted `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`, so it is recorded but not used as
the decision point.

Results:

| Lane | Variant | Median 1-100 | p10 | Mean | Full128 | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | accept-only, env mismatch | `90.893` | `86.589` | `93.868` | `90.324` | pass/cached0 | `data/gemma4-q8-gpu0-hnextn-acceptonly-128-20260628T1138-haccept/summary.json` |
| GPU0 | control | `93.904` | `89.820` | `96.160` | `95.601` | pass/cached0 | `data/gemma4-q8-gpu0-hnextn-control-128-20260628T1144-haccept-pair/summary.json` |
| GPU1 | accept-only | `95.992` | `83.744` | `94.809` | `93.643` | pass/cached0 | `data/gemma4-q8-gpu1-hnextn-acceptonly-128-20260628T1144-haccept-pairB/summary.json` |
| GPU0 | accept-only xover | `95.426` | `85.226` | `94.766` | `94.482` | pass/cached0 | `data/gemma4-q8-gpu0-hnextn-acceptonly-128-20260628T1149-haccept-xover/summary.json` |
| GPU1 | control xover | `101.021` | `89.093` | `98.932` | `97.756` | pass/cached0 | `data/gemma4-q8-gpu1-hnextn-control-128-20260628T1149-haccept-xover/summary.json` |

Decision: **reject and remove from active source**. The cross-over shows no
consistent gain; the normal control produced the best run (`101.021` strict128)
while accept-only trailed and had weaker p10/full128. The rejected source hook
was removed after recording this result. Keep the existing
`LLAMA_MTP_DEFER_TARGET_H_NEXTN=1` promoted path; only the accept-only extension
is rejected.

## Wrong-binary clean sweep (INVALID, `20260628Tnow*`)

Purpose: after removing the rejected accept-only source hook, run a clean
full512 four-GPU sweep to re-check the current record recipe and two small
runtime variants.

Result: **invalid due launcher identity mismatch**. These commands were run
without an explicit `LLAMA_SERVER`, so `scripts/run-gemma4-26b-llamacpp-replica.sh`
fell back to the older stack binary:

```text
/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31/bin/llama-server
```

The intended Gemma Q8 VDR2 repro binary is:

```text
/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server
```

The strict gate itself passed and all rows had `cached_tokens=0`, but the
runtime identity is wrong, so the numbers below are **not comparable** to the
current `98.340` record and must not be promoted or used as evidence of a
regression.

| Lane | Intended variant | Median 1-100 | p10 | Mean | Full512 | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | control, unroll7, `p_min=0.0475` | `45.252` | `41.289` | `45.651` | `44.137` | invalid: wrong binary | `data/gemma4-q8-gpu0-crack100-clean-control-full512-20260628TnowA/summary.json` |
| GPU1 | control, unroll7, `p_min=0.0475` | `46.105` | `41.329` | `45.801` | `43.964` | invalid: wrong binary | `data/gemma4-q8-gpu1-crack100-clean-control-full512-20260628TnowB/summary.json` |
| GPU2 | `p_min=0.0500`, unroll7 | `45.893` | `41.148` | `45.668` | `44.161` | invalid: wrong binary | `data/gemma4-q8-gpu2-crack100-clean-pmin005-full512-20260628TnowC/summary.json` |
| GPU3 | control `p_min=0.0475`, unroll6 | `43.399` | `41.120` | `44.686` | `43.371` | invalid: wrong binary | `data/gemma4-q8-gpu3-crack100-clean-unroll6-full512-20260628TnowD/summary.json` |

Action taken: the Gemma baseline wrapper now defaults `LLAMA_SERVER` to the
VDR2 repro binary and passes it explicitly into the replica launcher; the
replica launcher also uses that same default when called directly. Rerun this
sweep with the corrected wrapper before making any comparison.

## Corrected clean full512 rerun (`20260628T120458Z`)

Purpose: rerun the invalid `Tnow*` sweep after fixing the launcher default and
also passing `LLAMA_SERVER` explicitly. This is the real post-cleanup
comparison point.

Common identity:

- source/repro binary:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server`;
- target/verifier:
  `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft:
  `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- fixed realistic cold suite, each prompt once, `MAX_TOKENS=512`,
  `CANARY_REPEATS=32`, all `cached_tokens=0`, no cache/history/ngram reuse.

Results:

| Lane | Variant | Median 1-100 | p10 | Mean | Full512 | Wall512 | TTFT ms | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | control, unroll7, `p_min=0.0475` | `92.031` | `88.851` | `94.937` | `91.334` | `88.008` | `180.0` | pass/cached0/server-ok | `data/gemma4-q8-gpu0-crack100-rerun-control-full512-20260628T120458Z/summary.json` |
| GPU1 | control, unroll7, `p_min=0.0475` | `96.522` | `84.799` | `95.874` | `90.419` | `87.224` | `180.8` | pass/cached0/server-ok | `data/gemma4-q8-gpu1-crack100-rerun-control-full512-20260628T120458Z/summary.json` |
| GPU2 | unroll7, `p_min=0.0500` | `93.163` | `85.753` | `94.055` | `90.871` | `86.999` | `181.1` | pass/cached0/server-ok | `data/gemma4-q8-gpu2-crack100-rerun-pmin005-full512-20260628T120458Z/summary.json` |
| GPU3 | unroll6, `p_min=0.0475` | `99.042` | `80.643` | `96.151` | `90.884` | `87.520` | `180.6` | pass/cached0/server-ok | `data/gemma4-q8-gpu3-crack100-rerun-unroll6-full512-20260628T120458Z/summary.json` |

Decision: **near-miss only / no submission**. The unroll6 lane is again the
closest current full512 shape, but it is not reliable enough to call a `>100`
solution: prior exact repeats landed at `101.076`, `99.308`, `98.959`,
`98.027`, and now `99.042`, and this run had weak p10 because
`code-review` and `performance-hypotheses` fell to ~`79 tok/s`. Continue with
a narrow unroll6 `p_min` sweep before spending effort on deeper source work.

## Unroll6 `p_min` full512 threshold sweep (`20260628T1214Z`)

Purpose: test whether the closest full512 family (`LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=6`)
can be stabilized by lowering the draft confidence threshold. All rows use the
same Q8 target/verifier, Q4_0 MTP draft, VDR2 repro binary, F16 p021
small-ncols, bulk sampled-ID verifier, fixed cold realistic suite,
`MAX_TOKENS=512`, and `cached_tokens=0` throughout.

Results:

| Lane | `p_min` | Median 1-100 | p10 | Mean | Full512 | Wall512 | TTFT ms | Validity | Summary |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | `0.0350` | `98.757` | `88.038` | `98.293` | `92.235` | `87.486` | `180.0` | pass/cached0/server-ok | `data/gemma4-q8-gpu0-crack100-u6-p00350-full512-20260628T1214Z/summary.json` |
| GPU1 | `0.0400` | `97.692` | `87.159` | `97.281` | `91.972` | `89.129` | `181.9` | pass/cached0/server-ok | `data/gemma4-q8-gpu1-crack100-u6-p00400-full512-20260628T1214Z/summary.json` |
| GPU2 | `0.0425` | `98.373` | `84.443` | `95.212` | `88.047` | `85.463` | `180.3` | pass/cached0/server-ok | `data/gemma4-q8-gpu2-crack100-u6-p00425-full512-20260628T1214Z/summary.json` |
| GPU3 | `0.0450` | `93.373` | `85.264` | `94.655` | `91.860` | `88.089` | `183.0` | pass/cached0/server-ok | `data/gemma4-q8-gpu3-crack100-u6-p00450-full512-20260628T1214Z/summary.json` |

Decision: **runtime threshold tuning did not crack reliable `>100`**. The best
row (`p_min=0.0350`) is valid and close, but still below the promoted `98.340`
by only a small margin and below the `>100` target. With unroll/p_min/ubatch
screens repeatedly clustering around `98-99`, the next useful work is
source-level reduction of verifier or target-body overhead, not more
threshold-only sweeps.

## BF16 `MUL_MAT_ID` direct multi-token source branch (`20260628T123359Z`)

Purpose: reduce verifier/target-body MoE overhead instead of more runtime knob
churn. Node profiling shows the verifier is target-body-bound after the draft
path improvements; one visible cost is the final BF16 MoE gate/up family, which
can miss the Q8-specialized multi-token path. A default-off source branch added
`LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_BF16_DIRECT=1` to bypass the generic
host-routing path for BF16 `MUL_MAT_ID` when `src1=[ncols,1,n_tokens]` and
`ids=[n_experts_used,n_tokens]`.

Initial strict 128-token screen, same cold realistic gate and record stack as
above (`MAX_TOKENS=128`, `CANARY_REPEATS=8`, all `cached_tokens=0`):

| Lane | Variant | Median 1-100 | p10 | Mean | Full128 | Wall128 | TTFT ms | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | control | `92.571` | `86.122` | `95.639` | `95.704` | `84.760` | `181.6` | pass/cached0/server-ok | `data/gemma4-q8-gpu0-bf16direct-control-128-20260628T123359Z-bf16direct-screen3/summary.json` |
| GPU1 | BF16 direct, broad | `97.937` | `87.226` | `96.934` | `95.691` | `84.512` | `179.1` | pass/cached0/server-ok | `data/gemma4-q8-gpu1-bf16direct-broad-128-20260628T123359Z-bf16direct-screen3/summary.json` |
| GPU2 | BF16 direct, `ffn_moe_gate_up-29` only | `90.421` | `78.892` | `89.176` | `85.644` | `75.982` | `181.3` | pass/cached0/server-ok | `data/gemma4-q8-gpu2-bf16direct-gateup29-128-20260628T123359Z-bf16direct-screen3/summary.json` |
| GPU3 | BF16 direct, `ffn_moe_down-29` only | `90.836` | `80.108` | `89.554` | `88.162` | `77.722` | `181.2` | pass/cached0/server-ok | `data/gemma4-q8-gpu3-bf16direct-down29-128-20260628T123359Z-bf16direct-screen3/summary.json` |

Initial decision: **not a candidate yet**. The broad lane was valid but below
the current promoted `98.340` record, and the targeted lanes were clear losses.
However, follow-up review found the first patch was not fully fair/safe:

- the direct kernel only rejected negative route ids; it now also rejects
  `expert_id >= src0->ne[2]` before indexing expert weights;
- explicit `src1` stride checks were added;
- the SYCL graph eligibility checker did not include BF16 direct even when the
  dispatch path was enabled, so the BF16 op could force graph fallback. The
  graph checker is being updated to allow the same BF16 shape/stride gate.

Follow-up result (`20260628T124630Z-bf16direct-graphsafe-paired`): safety and
graph-eligibility fixes built cleanly, but the paired strict screen remained
negative.

| Lane | Variant | Median 1-100 | p10 | Mean | Full128 | Wall128 | TTFT ms | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | control | `99.519` | `87.055` | `96.775` | `94.661` | `83.890` | `179.2` | pass/cached0/server-ok | `data/gemma4-q8-gpu0-bf16graphsafe-control-128-20260628T124630Z-bf16direct-graphsafe-paired/summary.json` |
| GPU1 | BF16 direct, broad | `96.208` | `87.059` | `96.859` | `96.461` | `85.126` | `181.3` | pass/cached0/server-ok | `data/gemma4-q8-gpu1-bf16graphsafe-broad-128-20260628T124630Z-bf16direct-graphsafe-paired/summary.json` |
| GPU2 | control | `95.818` | `84.920` | `94.384` | `94.757` | `83.373` | `181.3` | pass/cached0/server-ok | `data/gemma4-q8-gpu2-bf16graphsafe-control-128-20260628T124630Z-bf16direct-graphsafe-paired/summary.json` |
| GPU3 | BF16 direct, broad | `97.722` | `86.277` | `97.446` | `95.597` | `83.965` | `180.6` | pass/cached0/server-ok | `data/gemma4-q8-gpu3-bf16graphsafe-broad-128-20260628T124630Z-bf16direct-graphsafe-paired/summary.json` |

Final decision: **BF16 direct is a closed loss for this target**. It is
default-off and validity-safe, but it does not beat paired controls or the
promoted `98.340` full512 record, and it does not move toward reliable `>100`.
Do not promote or submit. The useful follow-up is verifier economics: either
make the LM-head argmax path cheaper than full logits + argmax, or reduce MoE
target-body work on the slow rows.

## Selected-down epilogue retest under strict final gate (`20260628T145858Z`)

Purpose: re-test the older selected-down weighted-sum kernel family against the
current strict fresh-response gate and current promoted stack. Older rows in
this family produced `100-102 tok/s` under earlier measurement policy, but they
were rejected against a different frontier and not enough evidence for reliable
`>100` under the fixed realistic suite.

Shared setup: UD-Q8_K_XL target/verifier, Q4_0 MTP draft, one B70 per lane,
`n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH=1024`, F16 p021 small-ncols,
bulk sampled-ID verifier, fixed realistic prompt suite, each prompt once,
`MAX_TOKENS=512`, `CANARY_REPEATS=32`, all `cached_tokens=0`.

Results:

| Lane | Variant | Median 1-100 | p10 | Mean | Full512 | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | control | `96.168` | `86.638` | `96.211` | `90.896` | pass/cached0 | `data/gemma4-q8-gpu0-strict-selecteddown-control-u7-full512-20260628T145858Z/summary.json` |
| GPU1 | selected-down matmul epilogue | `75.698` | `67.867` | `75.709` | `71.890` | pass/cached0 | `data/gemma4-q8-gpu1-strict-selecteddown-matmulepi-u7-full512-20260628T145858Z/summary.json` |
| GPU2 | selected-down parallel slots | `75.593` | `66.053` | `74.995` | `69.802` | pass/cached0 | `data/gemma4-q8-gpu2-strict-selecteddown-parslots-u7-full512-20260628T145858Z/summary.json` |
| GPU3 | selected-down direct-F32 parallel slots | `78.686` | `72.042` | `78.431` | `72.147` | pass/cached0 | `data/gemma4-q8-gpu3-strict-selecteddown-directf32-parslots-u7-full512-20260628T145858Z/summary.json` |

Decision: **closed negative** for the current strict stack. The source gates are
correctness-safe but far below the same-batch control and far below the promoted
`98.340` record. Do not submit or promote. This also rules out treating the old
`100-102 tok/s` selected-down rows as a path to reliable `>100`; the remaining
work must reduce verifier/target-body cost through a different source design.

## Current ctx2048 retest under strict full512 gate (`20260628T150916Z`)

Purpose: verify whether the earlier `ctx2048` 128-token `100.035 tok/s`
diagnostic row transfers to the stricter full512 fresh-response gate. The
realistic suite prompts fit inside `ctx2048`, so this is a valid small-context
service shape for the current "small context, single-session decode" target.

Shared setup: UD-Q8_K_XL target/verifier, Q4_0 MTP draft, one B70 per lane,
`CTX_SIZE=2048`, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH=1024`,
F16 p021 small-ncols, bulk sampled-ID verifier, fixed realistic prompt suite,
each prompt once, `MAX_TOKENS=512`, `CANARY_REPEATS=32`, all
`cached_tokens=0`.

Results:

| Lane | Median 1-100 | p10 | Mean | Full512 | Validity | Summary |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | `97.814` | `85.889` | `96.265` | `91.463` | pass/cached0 | `data/gemma4-q8-gpu0-strict-ctx2048-current-u7-full512-20260628T150916Z/summary.json` |
| GPU1 | `98.117` | `86.546` | `96.819` | `90.952` | pass/cached0 | `data/gemma4-q8-gpu1-strict-ctx2048-current-u7-full512-20260628T150916Z/summary.json` |
| GPU2 | `96.256` | `86.411` | `96.920` | `91.342` | pass/cached0 | `data/gemma4-q8-gpu2-strict-ctx2048-current-u7-full512-20260628T150916Z/summary.json` |
| GPU3 | `97.441` | `86.449` | `97.162` | `90.696` | pass/cached0 | `data/gemma4-q8-gpu3-strict-ctx2048-current-u7-full512-20260628T150916Z/summary.json` |

Decision: **closed negative** for reliable `>100`. The smaller context is
valid and can be used operationally when a 2K window is enough, but it does not
beat the promoted `98.340` strict full512 record and does not make `100+`
reliable. Do not submit or promote. The `ctx2048` 128-token `100.035` row is a
diagnostic high observation only.

## Q3 MTP draft quant screen under strict full512 gate (`20260628Tq3screen2`)

Purpose: test whether cheaper MTP draft quantization can recover the last few
percent needed for reliable `100+` without lowering target quality. This is
quality-safe in principle because the target/verifier remains
`UD-Q8_K_XL`; the lower-precision file is only the speculative draft source and
every accepted token is verified by the Q8 target.

The first screen (`20260628Tq3screen`) is **invalid for comparison** because the
same-window Q4_0 control landed at only `74.781 tok/s`: the launch omitted
record-stack flags (`LLAMA_MTP_DRAFT_FAST_ARGMAX=1`,
`LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1`,
`LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1`) and used `POLL=50` instead of the
record `POLL=100`. Preserve those result directories as a launcher-identity
mistake, but do not interpret the Q3 values from that batch.

Corrected shared setup: UD-Q8_K_XL target/verifier, one B70 per lane, current
record `llama-server` binary, `n_max=3`, `n_min=2`, `p_min=0.0475`,
`UBATCH=1024`, F16 p021 small-ncols, route cache, multi-token fast path, fused
MTP output argmax, fast direct-argmax draft path, bulk sampled-ID verifier,
fixed realistic prompt suite, each prompt once, `MAX_TOKENS=512`,
`CANARY_REPEATS=32`, all `cached_tokens=0`.

Corrected results:

| Lane | Draft file | Median 1-100 | p10 | Mean | Full512 | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | Q4_0 control | `94.709` | `87.188` | `96.040` | `91.108` | pass/cached0 | `data/gemma4-q8-gpu0-draftq40-control-strict-full512-20260628Tq3screen2/summary.json` |
| GPU1 | Q3_K_S | `91.170` | `85.220` | `91.307` | `85.505` | pass/cached0 | `data/gemma4-q8-gpu1-draftq3ks-strict-full512-20260628Tq3screen2/summary.json` |
| GPU2 | Q3_K_M | `89.114` | `84.720` | `91.163` | `87.716` | pass/cached0 | `data/gemma4-q8-gpu2-draftq3km-strict-full512-20260628Tq3screen2/summary.json` |
| GPU3 | Q3_K_L | `92.452` | `86.326` | `93.755` | `88.802` | pass/cached0 | `data/gemma4-q8-gpu3-draftq3kl-strict-full512-20260628Tq3screen2/summary.json` |

Decision: **closed negative**. Q3 drafts are valid but slower than Q4_0 in the
current strict stack. The smaller draft files do not save enough draft time to
offset lower acceptance / less favorable generation behavior. Keep Q4_0 as the
draft default; do not submit or promote Q3 draft results.

## EAGLE3 Gemma4 speculator smoke (`20260628T1532-1537Z`)

Purpose: test whether the locally available EAGLE3 Gemma4 speculator changes
the acceptance/verifier-row economics enough to become a credible reliable
`>100 tok/s` path under the strict cold-suite rules.

Files tested:

- Target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- EAGLE3 Q4 draft:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-eagle3-gguf/gemma-4-26B-A4B-it-speculator.eagle3-Q4_K_M.gguf`
- EAGLE3 Q8 draft is also downloaded but not promoted:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-eagle3-gguf/gemma-4-26B-A4B-it-speculator.eagle3-Q8_0.gguf`

Findings:

- With the current record env inherited unchanged, startup crashes after
  `common_speculative_impl_draft_eagle3`:
  `GGML_ASSERT(logits->ne[1] == n_outputs) failed` in
  `src/llama-graph.cpp:3499`.
- Root cause: `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1` is global and gets
  applied to the EAGLE3 draft context, not only the target verifier context.
  The server then runs `common_context_can_seq_rm()` against the draft context;
  that probe decodes two tokens but only requests the final token as output.
  EAGLE3 emits logits for all input tokens and does not apply `inp_out_ids`,
  so the generic verifier direct-argmax path sees `2 != 1` rows and asserts.
- Disabling `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS` and
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS` gets past startup, but with SYCL graph
  enabled the first canary request crashes:
  `Graph nodes cannot depend on events from outside the graph` at
  `ggml-sycl.cpp:7927` (`OP MUL_MAT`).
- Disabling SYCL graph makes EAGLE3 run correctly, but it is slow:

| Lane | Variant | Median 1-100 | p10 | Mean | Full128 | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU1 | EAGLE3 Q4, graph off, verifier argmax disabled | `72.651` | `66.126` | `73.159` | `70.726` | pass/cached0 strict128 | `data/gemma4-q8-gpu1-eagle3q4-n3-graphoff-noverifierargmax-strict128-20260628T153726Z/summary.json` |

EAGLE acceptance in the graph-off run was not strong enough to offset the lost
graph/record-stack verifier path: cumulative `#mean acc len` was about `2.04`,
with position acceptance roughly `0.59-0.63`, `0.29`, `0.16`.

Decision: **closed negative for near-term crack-100 work**. EAGLE3 liveness is
proven only with graph off, where it is far below the promoted `98.340` strict
record. The graph-on crashes are real integration work, not a result-tuning
issue. A small source fix would gate target verifier direct-argmax away from
`LLM_ARCH_EAGLE3` draft contexts, but that only fixes startup; it does not solve
the graph-boundary `OP MUL_MAT` failure or prove better acceptance. Do not spend
full512 validation budget on EAGLE3 until the graph path is made stable.

## Stateless greedy verifier accept skip screen (`20260628T1543Z`)

Purpose: test the default-off `LLAMA_SPEC_VERIFY_SKIP_STATELESS_ACCEPT=1` path
in `common/sampling.cpp`. For greedy/stateless prompts it still reads compact
target-verifier sampled IDs, but skips redundant `common_sampler_accept()` calls
when the sampler has no state that can affect future logits. This should be
exact for the current strict greedy lane; the question is whether it saves
enough host time to move the strict frontier.

Shared setup: UD-Q8_K_XL target/verifier, Q4_0 MTP draft, VDR2/F16-p021/bulk
sampled-ID stack, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`,
fixed realistic prompt suite, each prompt once, `MAX_TOKENS=128`,
`CANARY_REPEATS=8`, all `cached_tokens=0`.

| Lane | Variant | Median 1-100 | p10 | Mean | Full128 | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | control | `101.432` | `94.208` | `101.898` | `98.782` | pass/cached0 | `data/gemma4-q8-gpu0-skipstateless-control-128-20260628T154345Z/summary.json` |
| GPU1 | `LLAMA_SPEC_VERIFY_SKIP_STATELESS_ACCEPT=1` | `98.910` | `88.096` | `98.523` | `97.020` | pass/cached0 | `data/gemma4-q8-gpu1-skipstateless-on-128-20260628T154346Z/summary.json` |
| GPU2 | control | `98.355` | `89.966` | `99.403` | `97.213` | pass/cached0 | `data/gemma4-q8-gpu2-skipstateless-control-128-20260628T154346Z/summary.json` |
| GPU3 | `LLAMA_SPEC_VERIFY_SKIP_STATELESS_ACCEPT=1` | `99.847` | `91.875` | `100.254` | `98.109` | pass/cached0 | `data/gemma4-q8-gpu3-skipstateless-on-128-20260628T154346Z/summary.json` |

Decision: **neutral / not promotable standalone**. The flag is correctness-safe
under the stateless greedy guard, but the paired screen does not show a clear
win over same-window controls. It may still be cheap enough to combine with the
strongest historical near-miss identities (`ubatch=896 + rawargmax`, unroll6 +
bulk sampled IDs), but it should not be submitted or treated as a record without
full512 confirmation above `98.340` and preferably reliable `>100`.

## Full512 crack-100 confirmation screen (`20260628T1546Z`)

Purpose: promote the `skip-stateless` and `ubatch=896 + rawargmax` near-miss
families from strict128 diagnostics to the real promotion gate: fixed realistic
cold prompt suite, each prompt once, `MAX_TOKENS=512`, `cached_tokens=0` for
every request, canaries passing, and headline metric `median_tok_s_1_100_after_ttft`.

Shared setup: UD-Q8_K_XL target/verifier, Q4_0 MTP draft, llama.cpp
`c926ad098` record-stack binary, VDR2/F16-p021/bulk sampled-ID stack,
`n_max=3`, `n_min=2`, `p_min=0.0475`, `BATCH_SIZE=1024`, `POLL=100`,
`CANARY_REPEATS=32` (`128` canary rows), `REALISTIC_GATE=1`, no prompt/KV
reuse, no n-gram/history acceleration.

| Lane | Variant | Median 1-100 | p10 | Mean | Full512 | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | control, `UBATCH=1024` | `95.659` | `89.657` | `99.114` | `94.438` | pass/cached0 | `data/gemma4-q8-gpu0-crack100-control-full512-20260628T154628Z/summary.json` |
| GPU1 | `LLAMA_SPEC_VERIFY_SKIP_STATELESS_ACCEPT=1`, `UBATCH=1024` | `101.640` | `91.570` | `101.816` | `94.581` | pass/cached0 | `data/gemma4-q8-gpu1-crack100-skipstateless-full512-20260628T154628Z/summary.json` |
| GPU2 | `UBATCH=896`, `LLAMA_SPEC_VERIFY_RAW_ARGMAX=1`, `SKIP_STATELESS=1` | `100.541` | `88.968` | `99.920` | `96.123` | pass/cached0 | `data/gemma4-q8-gpu2-crack100-ub896-rawargmax-skipstateless-full512-20260628T154628Z/summary.json` |
| GPU3 | GPU2 + `LLAMA_MTP_DRAFT_DEVICE_H_HANDOFF=1` | `100.237` | `93.348` | `101.290` | `96.011` | pass/cached0 | `data/gemma4-q8-gpu3-crack100-ub896-rawargmax-handoff-skipstateless-full512-20260628T154628Z/summary.json` |

Interpretation: first real full512 crack-100 screen produced three strict-valid
`>100` observations, but this family has prior one-off `>100` failures to
repeat. Treat these as **candidate / not promoted** until exact full512 repeats
hold above the promoted `98.340` record and ideally above `100` on the primary
metric. Repeat set launched immediately as `*-repeat2-full512-*` across the four
GPUs.

### Repeat outcome (`20260628T1552Z`): not reliable

Exact full512 repeats were launched on the same four GPUs with the same strict
gate and canary settings. All runs were valid (`cached_tokens=0`, canaries pass),
but the `>100` observations did **not** reproduce:

| Lane | Repeat median 1-100 | Repeat p10 | Repeat mean | Repeat Full512 | Summary |
| --- | ---: | ---: | ---: | ---: | --- |
| GPU0 control, `UBATCH=1024` | `99.261` | `87.530` | `98.806` | `92.516` | `data/gemma4-q8-gpu0-crack100-control-repeat2-full512-20260628T155231Z/summary.json` |
| GPU1 `SKIP_STATELESS=1`, `UBATCH=1024` | `96.392` | `86.352` | `96.502` | `92.002` | `data/gemma4-q8-gpu1-crack100-skipstateless-repeat2-full512-20260628T155231Z/summary.json` |
| GPU2 `UBATCH=896`, `RAW_ARGMAX=1`, `SKIP_STATELESS=1` | `91.323` | `84.688` | `95.464` | `89.198` | `data/gemma4-q8-gpu2-crack100-ub896-rawargmax-skipstateless-repeat2-full512-20260628T155232Z/summary.json` |
| GPU3 GPU2 + `DRAFT_DEVICE_H_HANDOFF=1` | `91.674` | `86.233` | `93.614` | `92.113` | `data/gemma4-q8-gpu3-crack100-ub896-rawargmax-handoff-skipstateless-repeat2-full512-20260628T155232Z/summary.json` |

Decision: **closed as non-reliable for headline promotion**. `SKIP_STATELESS`,
`RAW_ARGMAX`, and handoff variants can produce valid high-side passes, but the
repeat spread is too wide and below the existing promoted `98.340` record. Do
not submit these `>100` observations to LocalMaxxing. The practical lesson is
that crack-100 needs either a true source-level cost reduction on the same
strict suite or a repeat-stable runtime change; current flag combinations are
still variance-limited.

### Solo follow-up: four-GPU contention was not the cause

To check whether the repeat collapse was caused by running four independent
replicas concurrently, the cleanest high-side candidate was repeated solo on
GPU1:

| Lane | Median 1-100 | p10 | Mean | Full512 | Summary |
| --- | ---: | ---: | ---: | ---: | --- |
| GPU1 solo `SKIP_STATELESS=1`, `UBATCH=1024` | `96.389` | `92.092` | `97.385` | `92.757` | `data/gemma4-q8-gpu1-crack100-skipstateless-solo-full512-20260628T155609Z/summary.json` |

Decision: **runtime-only route closed for now**. The solo run matched the
repeat (`96.392`) rather than the high-side first pass (`101.640`), so the
failure to crack 100 reliably is not explained by four-GPU contention. Move
back to source-level verifier cost reduction.

## Source lane: exact verifier candidate-max (`20260628T1600Z`)

Lane: record / source-level verifier cost reduction.

Hypothesis: the strict realistic lane is still target/verifier-forward bound,
with the verifier LM-head full-vocab projection first in node profiles. A
reliable crack-100 path likely needs to reduce LM-head output traffic or
verification row cost, not another runtime flag. The proposed
`LLAMA_SPEC_VERIFY_CANDIDATE_MAX=1` path should consume the drafted candidate
IDs before target decode and emit compact sampled IDs only when the drafted
candidate is exactly the target argmax. It must preserve exact target
verification and keep `cached_tokens=0`; any shortcut that only reimplements
the already-rejected full-logits/raw-argmax path is not useful.

Initial implementation target:

- thread candidate token IDs from server speculative state into the target
  verifier decode graph;
- add a Gemma4 verifier LM-head branch before the normal full logits output;
- reuse the tuned dense/Q8 path as much as possible, avoiding the rejected
  `GGML_OP_MUL_MAT_ARGMAX` tile-family unless only for a smoke;
- output the same compact sampled-token rows already consumed by
  `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1` and
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`.

First test after build: strict128 with `CANARY_REPEATS=8`, then full512 only if
it beats the current identity or shows clear profile movement. Kill if it still
materializes full logits and simply moves host argmax work around.

### Reconfirm sweep after candidate-max review (`20260628T1610Z`)

Purpose: re-run the strongest runtime identities after the candidate-max source
review concluded that a cheap alias over the existing compact sampled-ID backend
would not be a real speed unlock. This was a strict full512 fresh-response gate,
not a synthetic prompt screen.

Shared setup: UD-Q8_K_XL target/verifier, Q4_0 MTP draft, llama.cpp
`c926ad098` record-stack binary, VDR2/F16-p021/bulk sampled-ID stack,
`BATCH_SIZE=1024`, `POLL=100`, `CANARY_REPEATS=32` (`128` canary rows),
`REALISTIC_GATE=1`, no prompt/KV reuse, no context checkpoints, no
n-gram/history acceleration. All runs had `cached_tokens=0` for every request.

| Lane | Variant | Median 1-100 | p10 | Mean | Full512 | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | current control, `CTX=8192`, `UBATCH=1024`, `n=3`, `n_min=2`, `p_min=0.0475`, unroll7 | `99.599` | `87.243` | `98.126` | `90.721` | pass/cached0 | `data/gemma4-q8-gpu0-crack100-reconfirm3-control-full512-20260628T1610Z/summary.json` |
| GPU1 | same, `CTX=2048` | `95.749` | `88.777` | `97.194` | `90.492` | pass/cached0 | `data/gemma4-q8-gpu1-crack100-reconfirm3-ctx2048-full512-20260628T1610Z/summary.json` |
| GPU2 | same, `p_min=0.0500` | `92.789` | `86.695` | `94.590` | `91.000` | pass/cached0 | `data/gemma4-q8-gpu2-crack100-reconfirm3-pmin00500-full512-20260628T1610Z/summary.json` |
| GPU3 | same, direct-argmax unroll6 | `94.872` | `86.405` | `95.996` | `89.674` | pass/cached0 | `data/gemma4-q8-gpu3-crack100-reconfirm3-unroll6-full512-20260628T1610Z/summary.json` |

Decision: **no reliable crack-100 runtime identity yet**. The current control is
close (`99.599`) but still below the reliable `>100` target, and the previously
interesting alternates regressed on repeat. Treat the high-side `>100` rows from
earlier screens as variance, not headline throughput. Do not submit any of
these to LocalMaxxing. Next work should be a genuine source-level reduction in
target verifier cost or draft/verify row count, not more small `p_min`, `ctx`,
or unroll sweeps without a new mechanism.

### Recheck4 after source-patch isolation (`20260628T161726Z`)

Purpose: run one more strict full512 set on the **pre-patch** binary before
building the graph-output cleanup, so any patch result has a clean same-day
control. This also checked whether removing explicit CPU affinity or using the
raw-argmax verifier lanes could reliably clear `100`.

Shared setup: same record-stack identity as above (`c926ad098`, UD-Q8_K_XL
target, Q4_0 MTP draft, `n=3`, `n_min=2`, `p_min=0.0475`, unroll7 unless
noted, `BATCH=1024`, `POLL=100`, `REALISTIC_GATE=1`, `CANARY_REPEATS=32`,
`cached_tokens=0`).

| Lane | Variant | Median 1-100 | p10 | Mean | Full512 | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | current control, **no CPU affinity**, `UBATCH=1024` | `99.863` | `90.021` | `99.411` | `91.736` | pass/cached0 | `data/gemma4-q8-gpu0-crack100-recheck4-control-noaff-full512-20260628T161726Z/summary.json` |
| GPU1 | `THREADS=6`, affinity `4-7,20-23` | `95.352` | `87.093` | `96.025` | `89.783` | pass/cached0 | `data/gemma4-q8-gpu1-crack100-recheck4-th6-aff-full512-20260628T161726Z/summary.json` |
| GPU2 | `UBATCH=896`, `LLAMA_SPEC_VERIFY_RAW_ARGMAX=1` | `96.503` | `87.093` | `97.436` | `92.644` | pass/cached0 | `data/gemma4-q8-gpu2-crack100-recheck4-rawargmax-ub896-full512-20260628T161726Z/summary.json` |
| GPU3 | `UBATCH=896`, `RAW_ARGMAX=1`, draft H handoff | `92.809` | `85.814` | `93.653` | `91.174` | pass/cached0 | `data/gemma4-q8-gpu3-crack100-recheck4-rawargmax-handoff-ub896-full512-20260628T161726Z/summary.json` |

Decision: the no-affinity control is now the closest strict cold result
(`99.863`), but it is still not a reliable `>100` headline. Raw argmax and draft
H handoff are not useful for this lane. Keep the `99.863` result as the
same-day control for the next source-level test; do **not** submit it to
LocalMaxxing because it does not cross the target and is not a new full512
record.

Subagent verifier/draft audit also closed two tempting shortcuts:

- `LLAMA_SPEC_VERIFY_CANDIDATE_MAX` does not exist in the current tree. A true
  exact candidate-max verifier would require threading candidate IDs into the
  target graph and falling back whenever the target argmax is outside the
  candidate set; a simple alias over compact sampled IDs would not reduce LM
  head work.
- `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_SCORES` / `LOGIT_GAP_MIN` only prune draft
  tokens before verification. They can reduce verifier rows indirectly, but
  prior strict rows showed the top2-score/gap path is slower in this stack, so
  it is not the next crack-100 lever unless a tail-only gate is added and tested
  as a real source change.

## Source lane: graph output cleanup (`20260628T1638Z`)

Change tested: only mark `t_embd` as graph output when `embeddings` are
requested and only mark `t_h_nextn` when `embeddings_nextn` is requested. This
was intended as a low-risk decode overhead cleanup for the current MTP path.
The broad build initially failed late on unrelated executable links with
SYCL/OpenMP undefined references; rebuilding the narrower `llama-server` target
with oneAPI environment sourced succeeded.

Strict smoke result (same current control identity, no CPU affinity,
`MAX_TOKENS=128`, `CANARY_REPEATS=8`):

| Lane | Median 1-100 | p10 | Mean | Full128 | Validity | Summary |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| graph-output cleanup | `98.256` | `84.614` | `96.764` | `96.056` | pass/cached0 | `data/gemma4-q8-gpu0-crack100-graphoutputs-smoke128-20260628T1638Z/summary.json` |

Decision: **negative / not promoted**. It did not beat the same-day no-affinity
control (`99.863` full512 median100) and does not justify a full512 repeat. The
source lines were reverted before further testing so later source experiments
are not contaminated by this near-noise cleanup.

## Source lane: tail-only draft logit-gap gate (`20260628T1650Z`)

Change tested: added `LLAMA_MTP_DRAFT_LOGIT_GAP_MIN_START_POS` so the existing
top2-score/logit-gap draft pruning can be applied only to later draft positions.
The intended use was `START_POS=3` for `n_max=3`, trimming weak third-token
tails without dropping high-value first/second draft tokens. This is
correctness-preserving because pruned draft tokens are never accepted without
target verification, but it can still lose speed if the score path costs more
than the verifier-row reduction saves.

Strict smoke setup: current no-affinity control identity, `MAX_TOKENS=128`,
`CANARY_REPEATS=4`, `REALISTIC_GATE=1`, `cached_tokens=0`, source rebuilt after
the tail-gate patch.

| Lane | Variant | Median 1-100 | p10 | Mean | Full128 | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | score path, `GAP=0`, `START_POS=3` | `99.861` | `85.558` | `98.448` | `100.811` | pass/cached0 | `data/gemma4-q8-gpu0-tailgap-score-gap000-start3-smoke128-20260628T1650Z/summary.json` |
| GPU1 | score path, `GAP=0.50`, `START_POS=3` | `94.297` | `86.629` | `96.391` | `95.567` | pass/cached0 | `data/gemma4-q8-gpu1-tailgap-gap050-start3-smoke128-20260628T1650Z/summary.json` |
| GPU2 | score path, `GAP=0.75`, `START_POS=3` | `97.331` | `87.041` | `96.725` | `97.249` | pass/cached0 | `data/gemma4-q8-gpu2-tailgap-gap075-start3-smoke128-20260628T1650Z/summary.json` |
| GPU3 | score path, `GAP=1.00`, `START_POS=3` | `94.556` | `85.953` | `95.870` | `91.930` | pass/cached0 | `data/gemma4-q8-gpu3-tailgap-gap100-start3-smoke128-20260628T1650Z/summary.json` |

Decision: **negative / not promoted**. `GAP=0` was effectively tied with the
same-day best (`99.863`) but did not improve the primary metric, and every real
gap threshold regressed. Do not run a full512 promotion for this path. If the
tail-gate code remains in the dirty source tree for reference, keep it
default-off and do not enable `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_SCORES` for the
headline lane.

## Reliability check: identical no-affinity controls on all four GPUs (`20260628T165242Z`)

Purpose: verify whether the `99.863` no-affinity control was a stable
near-100 plateau or one favorable lane. All four GPUs ran the exact same
strict full512 current-control recipe in parallel: UD-Q8_K_XL target/verifier,
Q4_0 MTP draft, VDR2/F16-p021/bulk sampled-ID stack, `n=3`, `n_min=2`,
`p_min=0.0475`, unroll7, `BATCH=1024`, `UBATCH=1024`, `POLL=100`,
`REALISTIC_GATE=1`, `CANARY_REPEATS=32`, no CPU affinity, no score/gap gate,
no prompt/KV/history reuse.

| Lane | Median 1-100 | p10 | Mean | Full512 | Validity | Summary |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | `96.034` | `82.411` | `96.426` | `90.854` | pass/cached0 | `data/gemma4-q8-gpu0-crack100-identical-control-noaff-full512-20260628T165242Z/summary.json` |
| GPU1 | `97.857` | `88.119` | `96.965` | `91.562` | pass/cached0 | `data/gemma4-q8-gpu1-crack100-identical-control-noaff-full512-20260628T165242Z/summary.json` |
| GPU2 | `97.165` | `87.419` | `97.464` | `91.736` | pass/cached0 | `data/gemma4-q8-gpu2-crack100-identical-control-noaff-full512-20260628T165242Z/summary.json` |
| GPU3 | `98.486` | `84.378` | `96.366` | `89.225` | pass/cached0 | `data/gemma4-q8-gpu3-crack100-identical-control-noaff-full512-20260628T165242Z/summary.json` |

Decision: **no reliable runtime-only crack-100**. The earlier `99.863` result
was a high-side strict run, not a repeatable floor. Continue with source-level
target/verifier cost reduction or exact verifier row-count reduction; do not
spend more time on unchanged control repeats, CPU affinity, raw argmax,
handoff, or draft-side logit-gap pruning.

## Source lane: skip duplicate full-accept `h_nextn` copy (`20260628Tcrack100A`)

Change tested in `common/speculative.cpp`: when
`LLAMA_MTP_DEFER_TARGET_H_NEXTN=1`, `process()` already copies the final target
verifier row into `pending_h`. The MTP `accept()` path now avoids copying that
same row again when `i_h == n_rows - 1` (the common full-accept case); partial
accepts still copy the earlier accepted row. This is intended to save one
synchronous `llama_copy_embeddings_nextn_ith()` / backend tensor read in a
correctness-preserving way.

Strict 128-token screen, current no-affinity control identity, `cached_tokens=0`
on every row, canary pass, no score/gap pruning:

| Lane | Variant | Median 1-100 | p10 | Mean | Full128 | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | patched control, `n=3`, `n_min=2`, `p_min=0.0475` | `94.219` | `87.220` | `96.156` | `93.794` | pass/cached0 | `data/gemma4-q8-gpu0-hnextn-skip-control-strict128-20260628Tcrack100A/summary.json` |
| GPU1 | patched + `LLAMA_SPEC_VERIFY_SKIP_STATELESS_ACCEPT=1` | `96.637` | `86.913` | `95.926` | `94.237` | pass/cached0 | `data/gemma4-q8-gpu1-hnextn-skipstateless-strict128-20260628Tcrack100A/summary.json` |
| GPU2 | patched, `n=4`, `n_min=2`, `p_min=0.0475` | `95.084` | `86.342` | `95.689` | `98.130` | pass/cached0 | `data/gemma4-q8-gpu2-hnextn-n4-strict128-20260628Tcrack100A/summary.json` |
| GPU3 | patched, `n=3`, `n_min=2`, `p_min=0.0425` | `98.679` | `85.422` | `96.583` | `95.107` | pass/cached0 | `data/gemma4-q8-gpu3-hnextn-p00425-strict128-20260628Tcrack100A/summary.json` |

Decision: **neutral / not promoted**. The patch did not shift the strict128
distribution above the existing best controls, and no lane justified a full512
confirmation. Keep only as a small exactness-preserving experiment artifact
unless a later profile proves this copy is a real bottleneck; it is not a
reliable crack-100 lever.

## Source lane: target-to-draft device `h_nextn` handoff (`20260628T1755Z`)

Purpose: test a separate default-off
`LLAMA_MTP_TARGET_DRAFT_DEVICE_H_HANDOFF=1` path for the first draft token. The
existing `LLAMA_MTP_DRAFT_DEVICE_H_HANDOFF` only copies draft `h_nextn` to the
next draft input within the same draft context; this experiment attempted to
copy the target verifier's `t_h_nextn[row]` directly into the draft context's
`t_inp_embd[0]`, avoiding the current target-row host staging.

Implementation result:

- Initial `ggml_view_1d()` row-copy version crashed immediately with
  `GGML_ASSERT(buffer)` in `ggml_backend_tensor_copy()`.
- Adding exported `ggml_backend_view_init()` on both temporary row views fixed
  the crash and produced valid canaries.
- The safe backend copy was slower than the existing host-staged path.

Strict 128-token screen, current no-affinity control identity, `cached_tokens=0`
on every row, canary pass, no score/gap pruning:

| Lane | Variant | Median 1-100 | p10 | Mean | Full128 | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | control, flag unset | `99.469` | `92.506` | `99.758` | `99.049` | pass/cached0 | `data/gemma4-q8-gpu0-targethandoff-control-strict128-20260628T1743Z/summary.json` |
| GPU1 | `LLAMA_MTP_TARGET_DRAFT_DEVICE_H_HANDOFF=1` + `ggml_backend_view_init()` | `93.456` | `88.244` | `96.287` | `94.803` | pass/cached0 | `data/gemma4-q8-gpu1-targethandoff-viewinit-strict128-20260628T1755Z/summary.json` |

Decision: **negative / reverted**. Cross-context eager
`ggml_backend_tensor_copy()` is not the right route for first-draft handoff; it
likely synchronizes/waits in the SYCL backend and costs more than the host
staging it replaces. Preserved details:
`patches/gemma4-26b-a4b-q8-b70/20260628T1755-target-draft-device-handoff-negative.md`.
If this idea is revisited, it should be graph-integrated or input-aliased, not
another eager backend copy between contexts.

## Full512 closure: tailgap / immediate-control crack-100 batch (`20260628T181728Z`)

Purpose: confirm whether the last strict128 near-misses were real crack-100
candidates under the actual strict full512 cold gate. All lanes kept the
headline-eligible target/verifier identity: `UD-Q8_K_XL` target, Q4_0 MTP
draft, one B70 per lane, `cached_tokens=0` for every prompt, fixed realistic
suite, no prompt/KV/history reuse, `MAX_TOKENS=512`, and 32 canary repeats.

| Lane | Variant | Median 1-100 | p10 | Mean | Full512 | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | current control, explicit graph/VMM identity | `96.203` | `84.214` | `94.357` | `90.526` | pass/cached0 | `data/gemma4-q8-gpu0-crack100-batch2-control-full512-20260628T181728Z/summary.json` |
| GPU1 | tail-only score path, `GAP=0`, `START_POS=3`, `p_min=0.0475` | `96.889` | `84.247` | `95.962` | `91.856` | pass/cached0 | `data/gemma4-q8-gpu1-crack100-batch2-tailgap-score-gap000-start3-full512-20260628T181728Z/summary.json` |
| GPU2 | same tail-only score path, `p_min=0.0500` | `96.627` | `84.822` | `95.662` | `88.049` | pass/cached0 | `data/gemma4-q8-gpu2-crack100-batch2-tailgap-score-gap000-start3-pmin0050-full512-20260628T181728Z/summary.json` |
| GPU3 | current control plus `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1` | `96.647` | `89.034` | `97.774` | `92.388` | pass/cached0 | `data/gemma4-q8-gpu3-crack100-batch2-immediate-control-full512-20260628T181728Z/summary.json` |

Live telemetry during the batch showed all four B70s at `2800 MHz` and roughly
`208-218 W`, so this miss is not obviously clock-throttle-driven. The prior
frequency-floor lane also failed repeatability. Decision: **tailgap, p_min=0.05,
and immediate-command-list controls are closed as reliable crack-100 routes**.
They can produce attractive strict128 or high-side full512 samples, but full512
confirmation falls back to the `~96-97 tok/s` band. Next work should be a real
source-level target-verifier cost reduction or accepted-token-count improvement,
not more unchanged runtime sweeps.

## Source lane: speculative sampler-clone skip (`20260628T184620Z`)

Purpose: remove hidden per-spec-step host overhead by skipping
`common_sampler_clone(slot.smpl.get())` when checkpoint restore cannot consume
the clone. The tested patch added a conservative helper in
`tools/server/server-context.cpp`: clone only if `ctx_tgt_seq_rm_type` is FULL,
or if RS rollback could exceed `llama_n_rs_seq(ctx_tgt)`. This preserves exact
rollback behavior because `finish_speculative_accept()` only uses the saved
sampler for checkpoint restore.

Build note: the dirty AOT build tree relinked `libggml-sycl` and spent about
10 minutes in Intel `ocloc` before producing the test binary. Future tiny
server-only patches should still be screened, but avoid rebuild-heavy churn
unless the expected gain is material.

Strict 128-token screen, current record identity on GPU1, `cached_tokens=0` on
every row, canary pass, no score/gap pruning:

| Lane | Variant | Median 1-100 | p10 | Mean | Full128 | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU1 | sampler clone skipped only when checkpoint restore impossible | `97.707` | `85.715` | `96.458` | `93.670` | pass/cached0 | `data/gemma4-q8-gpu1-cloneskip-screen128-20260628T184620Z/summary.json` |

Decision: **negative / reverted**. The result is below the standing strict
record (`98.340` median 1-100, full512) and does not justify a full512
confirmation. This closes sampler-clone skipping as a reliable crack-100 lever.
Preserved patch/result note:
`patches/gemma4-26b-a4b-q8-b70/20260628T184620-sampler-clone-skip-negative.md`.

## Source lane: verifier no-bonus-row retest (`20260628T1910Z`)

Purpose: retest the simple "skip bonus output row" idea on the current strict
record stack. The patch kept the target batch tokens as sampled + 3 draft
tokens, but marked the final draft token `output=false` and verified only the
three draft rows (`LLAMA_SPEC_VERIFY_NO_BONUS_ROW=1`). This is exact target
verification for the drafted tokens, but removes the normal bonus-token sample
from the verifier pass.

Strict 128-token screen, current record identity on GPU1, `cached_tokens=0` on
every row, canary pass:

| Lane | Variant | Median 1-100 | p10 | Mean | Full128 | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU1 | no bonus output row, `n=3`, `n_min=2`, `p_min=0.0475` | `84.920` | `77.610` | `83.724` | `83.070` | pass/cached0 | `data/gemma4-q8-gpu1-nobonusrow-screen128-20260628T1910Z/summary.json` |

Decision: **negative / reverted**. This passed quality but was dramatically
slower than the standing strict record (`98.340` full512 median). The likely
mechanism is pipeline loss: it saves one LM-head row, but the final accepted
draft token becomes the next sampled token and is effectively reprocessed in
the following target step. The simple no-bonus-row approach is closed. The
next useful verifier-economics path must keep the bonus pipeline and make the
bonus cheap (head-only bonus over `t_h_nextn`, or a true row-adaptive verifier),
not drop the bonus outright. Preserved note:
`patches/gemma4-26b-a4b-q8-b70/20260628T1910-spec-verify-no-bonus-row-negative.md`.

## Source lane: staged MTP3 split-bonus verifier (`20260628T202731Z`)

Purpose: test a safer row-economics variant after the simple no-bonus-row
approach failed. The patch is gated by
`LLAMA_SPEC_VERIFY_STAGE_MTP3_SPLIT_BONUS=1` and only activates with the
existing `LLAMA_SPEC_VERIFY_STAGE_MTP3=1` path. For `n_max=3`, it keeps target
verification exact but changes the staged verifier schedule from `2 + 2` rows
to `2 + 1 + 1`: verify rows 0/1 first, verify row 2 only if rows 0/1 matched,
and decode the bonus row only if row 2 also matched.

This preserves target-model verification semantics:

- row 0 verifies draft token 0;
- row 1 verifies draft token 1;
- row 2 verifies draft token 2;
- row 3 is still the bonus token, but only computed after full draft accept.

Strict 128-token screen, current record identity on GPU1, `cached_tokens=0` on
every row, canary pass:

| Lane | Variant | Median 1-100 | p10 | Mean | Full128 | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU1 | `STAGE_MTP3=1`, `STAGE_MTP3_SPLIT_BONUS=1` | `73.698` | `71.838` | `74.247` | `74.884` | pass/cached0 | `data/gemma4-q8-gpu1-stage-mtp3-splitbonus-strict128-20260628T202731Z/summary.json` |

Decision: **negative / do not promote**. The split-bonus path is slightly
better than the profiled staged run (`72.681`) but worse than the earlier
unprofiled staged control (`78.100`) and far below the standing full512 record
(`98.340`). The saved bonus-row work does not offset the extra decode-call
overhead and loss of the normal verifier batch shape. No full512 confirmation
was run.

The patch is default-off and preserved as an experiment artifact for future
reference. A deeper late-bonus head-only path was inspected separately: it is
not a quick safe win because row 3 hidden state still requires the target body
to consume draft token 2, and masking row 3 logits disables the current fused
verifier fast path. Implementing a true head-only bonus would need new
Gemma4/llama graph plumbing over `t_h_nextn`.

## Full512 repeat: unroll/thread/affinity high-side check (`20260628T203141Z`, `20260628T203420Z`)

Purpose: follow up the latest near-100 and one above-100 strict observations
under the real fresh-response gate. Every lane used the headline-eligible
identity: UD-Q8_K_XL target/verifier, Q4_0 MTP draft, one B70 per lane,
fixed realistic suite, each prompt once, `cached_tokens=0`, no prompt/KV/history
reuse, `MAX_TOKENS=512`, graph enabled, VMM disabled, f16 KV, VDR2,
`F16_P021_SMALL_NCOLS=1`, backend argmax IDs, bulk sampled IDs, selected-softmax
fused weights, weighted sum, route cache, `n_max=3`, `n_min=2`.

First screen:

| Lane | Variant | Median 1-100 | p10 | Mean | Full512 | Wall full512 | TTFT ms | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | unroll6, `p_min=0.0475`, `THREADS=8`, affinity `0-3,16-19` | `98.224` | `87.541` | `96.595` | `92.438` | `88.606` | `179.2` | pass/cached0 | `data/gemma4-q8-gpu0-crack100-repeat-u6-p00475-aff-full512-20260628T203141Z/summary.json` |
| GPU1 | unroll6, `p_min=0.0400`, `THREADS=8`, affinity | `95.432` | `85.860` | `95.998` | `91.323` | `87.823` | `180.1` | pass/cached0 | `data/gemma4-q8-gpu1-crack100-repeat-u6-p00400-aff-full512-20260628T203141Z/summary.json` |
| GPU2 | unroll7, `p_min=0.0475`, `THREADS=6`, affinity `8-11,24-27` | `100.799` | `88.252` | `98.872` | `92.030` | `88.795` | `179.6` | pass/cached0 | `data/gemma4-q8-gpu2-crack100-repeat-u7-p00475-th6-aff-full512-20260628T203141Z/summary.json` |
| GPU3 | unroll7, `p_min=0.0475`, `THREADS=8`, no affinity | `93.993` | `87.777` | `95.779` | `89.961` | `87.156` | `179.7` | pass/cached0 | `data/gemma4-q8-gpu3-crack100-repeat-u7-p00475-noaff-full512-20260628T203141Z/summary.json` |

The GPU2 `100.799` row was a valid strict fresh-response measurement, but it
needed immediate repeat before promotion because nearby runs showed high
variance and the p10 still sat below `90`.

Exact four-lane confirmation of the promising `THREADS=6` + affinity recipe:

| Lane | Variant | Median 1-100 | p10 | Mean | Full512 | Wall full512 | TTFT ms | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | unroll7, `p_min=0.0475`, `THREADS=6`, affinity `0-3,16-19` | `95.852` | `84.393` | `96.490` | `90.763` | `87.862` | `179.3` | pass/cached0 | `data/gemma4-q8-gpu0-crack100-confirm-th6-aff-full512-20260628T203420Z/summary.json` |
| GPU1 | same, affinity `4-7,20-23` | `95.509` | `88.695` | `96.597` | `91.075` | `87.660` | `180.1` | pass/cached0 | `data/gemma4-q8-gpu1-crack100-confirm-th6-aff-full512-20260628T203420Z/summary.json` |
| GPU2 | same, affinity `8-11,24-27` | `94.571` | `87.473` | `95.373` | `90.605` | `87.336` | `180.4` | pass/cached0 | `data/gemma4-q8-gpu2-crack100-confirm-th6-aff-full512-20260628T203420Z/summary.json` |
| GPU3 | same, affinity `12-15,28-31` | `96.175` | `86.895` | `96.630` | `91.870` | `87.737` | `179.4` | pass/cached0 | `data/gemma4-q8-gpu3-crack100-confirm-th6-aff-full512-20260628T203420Z/summary.json` |

Decision: **no promotion**. `100.799` was another valid high-side observation,
not a repeatable >100 configuration. `THREADS=6` plus CPU affinity does not
improve the current stack; it regressed to the normal `~94.5-96.2 tok/s`
strict-full512 band on exact confirmation. The current policy-compliant
headline remains `98.340` from
`data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-confirm-B-n3-nmin2-p00475-ub1024-full512-20260628T052158Z/summary.json`.

## Source lane: skip identity `out_ids` row gather (`20260628T205606Z`, `20260628T205810Z`)

Hypothesis: for single-session decode, many target graph builds have
`n_outputs == n_tokens`, making the generated `out_ids` tensor an identity
mapping. If the graph builder returns `nullptr` in that identity case, downstream
ops should consume contiguous rows directly and avoid the host `out_ids` update
plus any row-gather overhead. The patch was gated by
`LLAMA_GEMMA4_SKIP_IDENTITY_OUT_IDS=1` and was added to the run identity.

Strict 128-token paired screen:

| Lane | Variant | Median 1-100 | p10 | Mean | Full128 | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | control | `97.140` | `89.885` | `97.007` | `95.837` | pass/cached0 | `data/gemma4-q8-gpu0-skipoutids-control-128-20260628T205606Z/summary.json` |
| GPU1 | `SKIP_IDENTITY_OUT_IDS=1` | `98.458` | `89.573` | `97.972` | `96.876` | pass/cached0 | `data/gemma4-q8-gpu1-skipoutids-on-128-20260628T205606Z/summary.json` |
| GPU2 | control | `91.931` | `83.711` | `92.666` | `91.704` | pass/cached0 | `data/gemma4-q8-gpu2-skipoutids-control-128-20260628T205606Z/summary.json` |
| GPU3 | `SKIP_IDENTITY_OUT_IDS=1` | `96.438` | `88.237` | `96.555` | `95.903` | pass/cached0 | `data/gemma4-q8-gpu3-skipoutids-on-128-20260628T205606Z/summary.json` |

The 128-token screen was directionally positive versus paired controls, so it
was escalated to full512.

Strict full512 paired confirmation:

| Lane | Variant | Median 1-100 | p10 | Mean | Full512 | Wall full512 | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | control | `99.341` | `87.729` | `98.542` | `91.398` | `88.554` | pass/cached0 | `data/gemma4-q8-gpu0-skipoutids-control-full512-20260628T205810Z/summary.json` |
| GPU1 | `SKIP_IDENTITY_OUT_IDS=1` | `92.596` | `85.843` | `96.518` | `90.370` | `86.536` | pass/cached0 | `data/gemma4-q8-gpu1-skipoutids-on-full512-20260628T205810Z/summary.json` |
| GPU2 | control | `94.400` | `83.013` | `95.456` | `90.058` | `87.260` | pass/cached0 | `data/gemma4-q8-gpu2-skipoutids-control-full512-20260628T205810Z/summary.json` |
| GPU3 | `SKIP_IDENTITY_OUT_IDS=1` | `96.178` | `84.010` | `95.043` | `93.560` | `89.093` | pass/cached0 | `data/gemma4-q8-gpu3-skipoutids-on-full512-20260628T205810Z/summary.json` |

Decision: **negative / do not promote**. The full512 paired controls beat the
skip lanes on median 1-100, so identity `out_ids` removal is not a reliable
path to crack 100 on the current stack. The patch can remain default-off as a
research artifact but should not be enabled for headline runs.

The GPU0 control lane at `99.341` is a useful high-side observation, not a new
promoted record yet. An all-control full512 repeat was launched immediately to
check whether that number repeats or is just variance around the existing
`98.340` promoted result.

## All-control repeat after skip-out-ids high-side lane (`20260628T210051Z`)

Purpose: immediately retest the current record stack after the skip-out-ids
paired run produced a valid `99.341` control lane. All four lanes used the
normal current stack with `LLAMA_GEMMA4_SKIP_IDENTITY_OUT_IDS` unset.

| Lane | Median 1-100 | p10 | Mean | Full512 | Wall full512 | Validity | Summary |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | `96.201` | `86.780` | `95.653` | `91.100` | `87.987` | pass/cached0 | `data/gemma4-q8-gpu0-current-control-repeat-full512-20260628T210051Z/summary.json` |
| GPU1 | `96.340` | `88.490` | `97.298` | `89.521` | `86.796` | pass/cached0 | `data/gemma4-q8-gpu1-current-control-repeat-full512-20260628T210051Z/summary.json` |
| GPU2 | `98.595` | `88.234` | `98.258` | `88.566` | `85.912` | pass/cached0 | `data/gemma4-q8-gpu2-current-control-repeat-full512-20260628T210051Z/summary.json` |
| GPU3 | `93.043` | `84.255` | `93.699` | `88.606` | `85.976` | pass/cached0 | `data/gemma4-q8-gpu3-current-control-repeat-full512-20260628T210051Z/summary.json` |

Decision: **no promotion yet**. The repeat did not reproduce the `99.341`
control lane; the best repeat was `98.595`, which is only a small high-side
improvement over the promoted `98.340` and needs another exact confirmation
before it should replace the LocalMaxxing/reference record. The system remains
in the high-90s strict band, still short of the reliable `>100 tok/s` target.

## DFlash feasibility screen (`20260628T212540Z`)

Hypothesis: DFlash could improve strict fresh-response throughput by drafting a
longer block than the current Gemma MTP path (`n_max=3`) while still verifying
with the target model. This was worth checking because current MTP is acceptance
and target-row-cost limited, and DFlash can in principle draft up to block size
15.

Setup:

- isolated source: `/home/steve/src/llama.cpp-dflash-gemma4`
- upstream PR: llama.cpp `draft-dflash` PR 22105,
  commit `e8f1015ee7177fddc1f99c89772bef1b2640e375`
- target: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft: converted BF16 DFlash GGUF at
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/DFlash/gemma-4-26B-A4B-it-DFlash-BF16.gguf`
- converter patch artifact:
  `patches/gemma4-26b-a4b-q8-b70/20260628T2127-dflash-pr22105-gemma4-vocab-negative.md`
- run dir:
  `data/gemma4-q8-gpu0-dflash-pr22105-bf16-screen128-20260628T212540Z/`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-dflash-pr22105-bf16-screen128-20260628T212540Z.server.log`

Result: **negative / interrupted early**. The server loaded and DFlash operated,
but generation was orders of magnitude too slow:

| Task | Eval timing | Tok/s | Acceptance |
| --- | --- | ---: | --- |
| 0 | `5477.97 ms / 11 tokens` | `2.01` | `9/30`, mean len `5.50` |
| 5 | `4963.34 ms / 8 tokens` | `1.61` | `6/30`, mean len `4.00` |
| 10 | `4305.04 ms / 3 tokens` | `0.70` | `2/14`, mean len `3.00` |
| 14 | `4987.94 ms / 20 tokens` | `4.01` | `18/30`, mean len `10.00` |

The acceptance profile was not the primary blocker. The draft path itself was
too expensive: after 18 DFlash generate calls, the cumulative DFlash generation
duration was `2534.134 ms`, roughly `140 ms` per draft generation call. That is
far slower than no-spec (`~74 tok/s`) and the current MTP record stack
(`98.340 tok/s`).

Decision: do not promote, do not submit, and do not spend full-suite GPU time on
this PR snapshot. DFlash may be worth revisiting only if its SYCL path gets
substantial graph/fusion work; as tested here, it is not a route to reliable
`>100 tok/s`.

## Batch-size and poll interval screen (`20260628T213514Z` / `20260628T213715Z`)

Hypothesis: the current record stack might be leaving a few tok/s in cheap
runtime scheduling parameters after source-level changes stabilized. Tested
larger `BATCH_SIZE/UBATCH_SIZE` and a lower poll interval against the current
record identity.

Strict 128-token screen:

| Lane | Variant | Median 1-100 | p10 | Mean | Full128 | Wall full128 | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | control, batch/ubatch 1024, poll100 | `94.210` | `84.977` | `95.569` | `95.613` | `83.886` | pass/cached0 | `data/gemma4-q8-gpu0-crack100-batchpoll-control-128-20260628T213514Z/summary.json` |
| GPU1 | batch/ubatch 1536 | `91.525` | `84.944` | `93.991` | `93.478` | `82.052` | pass/cached0 | `data/gemma4-q8-gpu1-crack100-batch1536-128-20260628T213514Z/summary.json` |
| GPU2 | batch/ubatch 2048 | `92.259` | `84.011` | `94.079` | `93.306` | `81.414` | pass/cached0 | `data/gemma4-q8-gpu2-crack100-batch2048-128-20260628T213514Z/summary.json` |
| GPU3 | poll75 | `98.774` | `86.711` | `97.355` | `97.062` | `84.796` | pass/cached0 | `data/gemma4-q8-gpu3-crack100-poll75-128-20260628T213514Z/summary.json` |

Decision from the screen: larger batch/ubatch sizes are clear losses. `poll75`
was the only positive-looking signal, so it was escalated to a full512 paired
confirmation against two poll100 controls.

Full512 paired confirmation:

| Lane | Variant | Median 1-100 | p10 | Mean | Full512 | Wall full512 | TTFT ms | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | poll75 | `97.095` | `86.489` | `97.050` | `90.656` | `87.889` | `179.6` | pass/cached0 | `data/gemma4-q8-gpu0-crack100-poll75-confirm-p75-full512-20260628T213715Z/summary.json` |
| GPU1 | poll100 control | `98.390` | `86.840` | `98.003` | `91.226` | `87.929` | `180.2` | pass/cached0 | `data/gemma4-q8-gpu1-crack100-poll75-confirm-control-full512-20260628T213715Z/summary.json` |
| GPU2 | poll75 | `94.316` | `86.568` | `95.258` | `91.956` | `88.914` | `179.8` | pass/cached0 | `data/gemma4-q8-gpu2-crack100-poll75-confirm-p75-full512-20260628T213715Z/summary.json` |
| GPU3 | poll100 control | `93.948` | `85.822` | `95.351` | `89.181` | `86.542` | `180.2` | pass/cached0 | `data/gemma4-q8-gpu3-crack100-poll75-confirm-control-full512-20260628T213715Z/summary.json` |

Decision: **negative / closed**. `poll75` did not confirm; the best paired
lane was the poll100 control at `98.390`, essentially matching the promoted
`98.340` record. Keep the record recipe at `BATCH_SIZE=1024`,
`UBATCH_SIZE=1024`, and `POLL=100`. More cheap runtime-flag sweeps are low ROI
without a source/profile mechanism.

## Source lane: F16 p021 small-ncols pack4 (`20260628Tpack4A`)

Hypothesis: the active `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1` path handles small
multi-token F16 p021 verifier matmuls. The verifier commonly uses `ne[1] = 2`.
A default-off pack4 variant tried to compute up to four token columns inside one
workgroup, reusing the F16 weight load across token columns.

Patch artifact:
`patches/gemma4-26b-a4b-q8-b70/20260628-f16-p021-small-ncols-pack4-negative.patch`.

Build notes:

- The first raw build reached device compilation but failed host link with
  missing SYCL/OpenMP symbols. Re-running with
  `source /opt/intel/oneapi/setvars.sh --force` built successfully.
- The source change was gated by `LLAMA_SYCL_F16_P021_SMALL_NCOLS_PACK4=1`.
  Controls left the flag unset. The harness did not yet record this new flag in
  `launcher_identity`; labels and commands distinguish the lanes.

Strict 128-token A/B screen:

| Lane | Variant | Median 1-100 | p10 | Mean | Full128 | Wall full128 | Validity | Summary |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| GPU0 | control | `99.135` | `88.057` | `97.087` | `95.450` | `82.541` | pass/cached0 | `data/gemma4-q8-gpu0-pack4-control-strict128-20260628Tpack4A/summary.json` |
| GPU1 | pack4 enabled | `96.377` | `85.281` | `96.029` | `91.985` | `81.416` | pass/cached0 | `data/gemma4-q8-gpu1-pack4-enabled-strict128-20260628Tpack4A/summary.json` |
| GPU2 | control | `95.699` | `85.682` | `95.127` | `92.473` | `82.316` | pass/cached0 | `data/gemma4-q8-gpu2-pack4-control-strict128-20260628Tpack4A/summary.json` |
| GPU3 | pack4 enabled | `93.472` | `88.004` | `94.609` | `93.920` | `80.757` | pass/cached0 | `data/gemma4-q8-gpu3-pack4-enabled-strict128-20260628Tpack4A/summary.json` |

Decision: **negative / reverted**. Correctness was fine, but pack4 was slower
than both controls. The likely cause is reduced parallelism/occupancy from
collapsing token columns into one workgroup; the saved F16 load does not pay for
the lost workgroups. Do not promote, do not full512-confirm, and do not submit.
The source was reverted after preserving the patch artifact and result paths.

## Draft unroll / `p_min` retest (`20260628T225746Z` / `20260628T230022Z`)

Purpose: retest the only still-plausible runtime-side edge around the current
record recipe: draft direct-argmax unroll and `--spec-draft-p-min`. All lanes
used the strict realistic fresh-response gate (`MAX_TOKENS=512`, metric tokens
1-100 after TTFT, `cached_tokens=0`, no cache/history reuse) with the same
`UD-Q8_K_XL` target/verifier and Q4_0 MTP draft.

Initial four-lane screen:

| Lane | Variant | Median 1-100 | p10 | Mean | Validity | Summary |
| --- | --- | ---: | ---: | ---: | --- | --- |
| GPU0 | control, unroll 7, `p_min=0.0475` | `94.810` | `86.558` | `95.478` | pass/cached0 | `data/gemma4-q8-gpu0-crack100-batchB-control-u7-p00475-full512-20260628T225746Z/summary.json` |
| GPU1 | unroll 6, `p_min=0.0475` | `96.542` | `88.464` | `95.923` | pass/cached0 | `data/gemma4-q8-gpu1-crack100-batchB-u6-p00475-full512-20260628T225746Z/summary.json` |
| GPU2 | unroll 6, `p_min=0.0400` | `100.859` | `88.917` | `99.536` | pass/cached0 | `data/gemma4-q8-gpu2-crack100-batchB-u6-p00400-full512-20260628T225746Z/summary.json` |
| GPU3 | unroll 7, `p_min=0.0400` | `96.517` | `87.417` | `96.204` | pass/cached0 | `data/gemma4-q8-gpu3-crack100-batchB-u7-p00400-full512-20260628T225746Z/summary.json` |

The GPU2 lane was a real strict fresh-response `>100` observation, so the exact
`unroll=6`, `p_min=0.0400` recipe was immediately repeated across all four GPUs
before any promotion or submission.

Exact confirmation:

| Lane | Variant | Median 1-100 | p10 | Mean | Validity | Summary |
| --- | --- | ---: | ---: | ---: | --- | --- |
| GPU0 | unroll 6, `p_min=0.0400` | `94.363` | `89.746` | `97.166` | pass/cached0 | `data/gemma4-q8-gpu0-crack100-confirm-u6-p00400-full512-20260628T230022Z/summary.json` |
| GPU1 | unroll 6, `p_min=0.0400` | `95.752` | `87.398` | `96.468` | pass/cached0 | `data/gemma4-q8-gpu1-crack100-confirm-u6-p00400-full512-20260628T230022Z/summary.json` |
| GPU2 | unroll 6, `p_min=0.0400` | `94.652` | `84.836` | `94.516` | pass/cached0 | `data/gemma4-q8-gpu2-crack100-confirm-u6-p00400-full512-20260628T230022Z/summary.json` |
| GPU3 | unroll 6, `p_min=0.0400` | `91.959` | `87.680` | `95.218` | pass/cached0 | `data/gemma4-q8-gpu3-crack100-confirm-u6-p00400-full512-20260628T230022Z/summary.json` |

Decision: **not promoted / variance**. The initial `100.859` was valid as an
observation but not repeatable. The exact same GPU2 recipe repeated at
`94.652`, and the four confirmation lanes landed in the `91.96-95.75` band.
Prompt-level rates show the strict suite can swing by several tok/s because the
fresh generated text and MTP acceptance profile differ between runs. Keep the
headline record at the repeated `98.340` lane and do not submit this high-side
observation to LocalMaxxing.

Follow-up solo checks:

| Lane | Variant | Median 1-100 | p10 | Mean | Validity | Summary |
| --- | --- | ---: | ---: | ---: | --- | --- |
| GPU1 solo | current promoted recipe, unroll 7, `p_min=0.0475` | `98.680` | `89.522` | `98.729` | pass/cached0 | `data/gemma4-q8-gpu1-crack100-solo-current-u7-p00475-full512-20260628T230418Z/summary.json` |
| GPU2 solo | unroll 6, `p_min=0.0400` | `93.058` | `87.954` | `95.341` | pass/cached0 | `data/gemma4-q8-gpu2-crack100-solo-u6-p00400-full512-20260628T230642Z/summary.json` |

The isolated current-recipe run was a small valid high-side observation versus
the submitted `98.340`, but still below the desired reliable `>100` target. The
isolated `unroll=6`, `p_min=0.0400` run confirms that the earlier `100.859`
was not a hidden solo/concurrency condition. Runtime threshold/unroll tuning is
closed unless paired with a new verifier-cost mechanism.

## Fused verifier output argmax retest (`20260628T230943Z`)

Purpose: both code-reading subagents pointed at target/verifier LM-head cost as
the main remaining source-level bottleneck. The current promoted recipe uses
`LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1` plus
`LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`; it does not enable the Gemma4-specific
`LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1` path. This retested that fused path
on the current stack before spending more source work there.

Strict 128-token A/B screen:

| Lane | Variant | Median 1-100 | p10 | Mean | Validity | Summary |
| --- | --- | ---: | ---: | ---: | --- | --- |
| GPU0 | control, fused verifier off | `96.615` | `87.221` | `96.846` | pass/cached0 | `data/gemma4-q8-gpu0-crack100-fusedverify-control-128-20260628T230943Z/summary.json` |
| GPU1 | `LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1` | `86.931` | `83.418` | `86.410` | pass/cached0 | `data/gemma4-q8-gpu1-crack100-fusedverify-on-128-20260628T230943Z/summary.json` |
| GPU2 | control, fused verifier off | `96.056` | `85.987` | `95.702` | pass/cached0 | `data/gemma4-q8-gpu2-crack100-fusedverify-control-128-20260628T230943Z/summary.json` |
| GPU3 | `LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1` | `83.693` | `73.428` | `82.515` | pass/cached0 | `data/gemma4-q8-gpu3-crack100-fusedverify-on-128-20260628T230943Z/summary.json` |

Decision: **negative / closed**. The fused verifier argmax path is exact for
the eligible greedy verifier case, but it is much slower than the current
backend-argmax-ID route on this B70 stack. Do not enable it for headline runs.
Future verifier LM-head work must be a different design than the existing
`ggml_mul_mat_argmax(model.output, cur)` path.

## Draft quant control: Q2_K MTP screen (`20260628T231530Z`)

Purpose: close the only remaining low-precision draft question. The target and
verifier stayed fixed at `UD-Q8_K_XL`; only the MTP draft changed from the
promoted Q4_0 draft to Q2_K. This is not a target-quality change, but it can
still hurt accepted-token quality/speed if the draft becomes less predictive.

Strict 128-token screen, fixed realistic suite, each prompt once, no
prompt/KV/history reuse, `cached_tokens=0`, canaries pass:

| Lane | Variant | Median 1-100 | p10 | Mean | Validity | Summary |
| --- | --- | ---: | ---: | ---: | --- | --- |
| GPU0 | Q4_0 draft control, `p_min=0.0475` | `95.282` | `88.711` | `95.770` | pass/cached0 | `data/gemma4-q8-gpu0-crack100-q2screen-control-q40-p00475-128-20260628T231530Z/summary.json` |
| GPU1 | Q2_K draft, `p_min=0.0475` | `88.903` | `83.380` | `90.027` | pass/cached0 | `data/gemma4-q8-gpu1-crack100-q2screen-q2k-p00475-128-20260628T231530Z/summary.json` |
| GPU2 | Q2_K draft, `p_min=0.0400` | `85.779` | `82.827` | `88.077` | pass/cached0 | `data/gemma4-q8-gpu2-crack100-q2screen-q2k-p00400-128-20260628T231530Z/summary.json` |
| GPU3 | Q2_K draft, `p_min=0.0350` | `88.823` | `82.618` | `89.990` | pass/cached0 | `data/gemma4-q8-gpu3-crack100-q2screen-q2k-p00350-128-20260628T231530Z/summary.json` |

Decision: **negative / closed**. Q2_K loses roughly `6-10 tok/s` versus the
same-window Q4_0 control and offers no path to reliable `>100` fresh-response
throughput. Keep the promoted draft at Q4_0. Do not lower the draft further for
this target stack unless a future experiment has a new acceptance mechanism.

## Audit checkpoint: no more config-only repeats (`20260628T2325Z`)

Two independent read-only audits reviewed the strict fresh/cache0 ledger and
the local source tree after the Q2_K screen.

Findings:

- Every observed `>100 tok/s` strict/fresh/cache0 lane has an immediate exact
  repeat or confirmation batch that collapses below the promoted `98.340`
  record or below the solo `98.680` high-side observation.
- Rejected repeat families include frequency floor, unroll6+bulk, skip-stateless,
  late `unroll6 p_min=0.0400`, `ubatch=896 + rawargmax`, postnorm fusions,
  h_nextn handoff/defer variants, fused verifier argmax, tail logit-gap, and
  lower draft quantization.
- Existing source knobs around postnorm and h_nextn are already closed negative
  in this ledger. Re-running them is not useful without a new profile mechanism.
- The only credible remaining crack-100 lane is source-level verifier work:
  reduce the target-verifier LM-head/argmax cost or produce a compact
  verifier output for candidate-vs-max checking. The existing
  `ggml_mul_mat_argmax(model.output, cur)` fused path is too slow, so any new
  attempt must be a different design and must first prove reduced verifier
  output work on strict128 before full512 promotion.

Decision: **stop runtime/config roulette** for Gemma4 26B Q8 on this stack.
Future work should either implement a real compact-verifier source patch or
accept the current promoted record (`98.340` median 1-100, strict full512,
fresh/cache0) as the honest headline until a new mechanism exists.

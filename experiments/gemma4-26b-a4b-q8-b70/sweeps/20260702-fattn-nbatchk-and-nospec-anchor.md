# Gemma 4 26B Q8: no-spec anchor and FA nbatch_K tile sweep

Date: 2026-07-02

## Purpose

Capture a tight no-spec calibration point after cleanup, then test the only
bounded prompt-processing tile retune still worth trying from the long-context
audit:

- hot shape: `DKQ=576`, `DV=512`, `ncols=16`;
- baseline tile config: `nthreads=256`, `occupancy=2`, `nbatch_fa=64`,
  `nbatch_K=64`;
- candidates: `nbatch_K=32` and `nbatch_K=128`;
- service recipe kept constant:
  `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`,
  `LLAMA_PREFILL_UBATCH_SIZE=2048`,
  `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1`,
  `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048`,
  `CTX_SIZE=32768`, `FLASH_ATTN=on`, `BATCH_SIZE=2048`,
  `UBATCH_SIZE=1024`.

This is a service/prompt-processing diagnostic lane. It is not a LocalMaxxing
short-decode headline result.

## No-Spec Anchor

Four-GPU no-spec calibration:

- aggregate: `data/gemma4-nospec-anchor-20260702T045339Z-nospec-anchor.json`
- all lanes: fixed realistic cold suite, `cached_tokens=0`, canary pass,
  `realistic_final_gate.passed=true`
- medians by GPU: `76.923`, `76.718`, `76.289`, `76.682` tok/s
- average: `76.653` tok/s
- spread: `0.828%`

Use this as the current low-variance target-side micro-change reference. It is
diagnostic only; the promoted MTP record remains `124.97714084813418 tok/s`.

## Source And Build Preservation

Before editing, the active source stack and build were preserved:

- preedit source stack:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-fattn-nbatchk-preedit-source.patch`
- preedit diffstat:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-fattn-nbatchk-preedit-source.diffstat`
- temporary control build copy used during the sweep:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2-control-20260702-fattn-nbatchk`
- control `libggml-sycl.so.0.15.2`:
  `cede6cd2d3c5b5ae40f88c48d1b65e81d02ad6f34f214695148ba9c1e49a173b`

Candidate patches:

- `nbatch_K=32` focused patch:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-fattn-dv512-gqa16-nbatchk32-focused.patch`
- `nbatch_K=32` full source snapshot:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-fattn-dv512-gqa16-nbatchk32-source.patch`
- `nbatch_K=128` focused patch:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-fattn-dv512-gqa16-nbatchk128-focused.patch`
- `nbatch_K=128` full source snapshot:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-fattn-dv512-gqa16-nbatchk128-source.patch`

After the sweep, the active source file was restored to the preedit copy and
the active build was restored from the control build. Active
`libggml-sycl.so.0.15.2` again hashes to
`cede6cd2d3c5b5ae40f88c48d1b65e81d02ad6f34f214695148ba9c1e49a173b`.
The temporary copied build tree was removed after restore to avoid stale local
build artifacts; rebuild from the preserved source patches if another binary
A/B is needed.

## Validation Shape

Each candidate used the fixed deterministic long-context suite with each prompt
issued once per lane, exact JSON retrieval validation, and `cached_tokens=0`.
The A/B layout used two controls and two candidates, followed by a crossover:

- A/B: GPUs `0,2` control; GPUs `1,3` candidate;
- crossover: GPUs `0,2` candidate; GPUs `1,3` control.

Structured summary:

- `data/gemma4-fattn-nbatchk-sweep-20260702.json`

## Results

### `nbatch_K=32`

Labels:

- `data/gemma4-fattn-nbk32-labels-20260702T050943Z-fattn-nbk32-long-ab.txt`
- `data/gemma4-fattn-nbk32-labels-20260702T050943Z-fattn-nbk32-long-xover.txt`

All 8 lanes passed exact long-context validation and `cached_tokens=0`.

Average lane metrics:

- control prefill median average: `1122.142 tok/s`
- candidate prefill median average: `1123.065 tok/s`
- ratio: `+0.082%`
- control prefill mean average: `1117.339 tok/s`
- candidate prefill mean average: `1118.530 tok/s`
- ratio: `+0.107%`

Case ratios:

- `lc-12288-early`: `+0.144%`
- `lc-16384-late`: `+0.082%`
- `lc-22000-middle`: `+0.089%`

Decision: **reject / noise**. The result is valid but far below the `+1.5%`
service-lane promotion threshold.

### `nbatch_K=128`

Labels:

- `data/gemma4-fattn-nbk128-labels-20260702T052339Z-fattn-nbk128-long-ab.txt`
- `data/gemma4-fattn-nbk128-labels-20260702T052339Z-fattn-nbk128-long-xover.txt`

All 8 lanes passed exact long-context validation and `cached_tokens=0`.

Average lane metrics:

- control prefill median average: `1120.295 tok/s`
- candidate prefill median average: `1121.847 tok/s`
- ratio: `+0.139%`
- control prefill mean average: `1115.875 tok/s`
- candidate prefill mean average: `1117.035 tok/s`
- ratio: `+0.104%`

Case ratios:

- `lc-12288-early`: `+0.100%`
- `lc-16384-late`: `+0.139%`
- `lc-22000-middle`: `+0.071%`

Decision: **reject / noise**. The result is valid but far below the `+1.5%`
service-lane promotion threshold.

## Conclusion

The hot-shape `nbatch_K` retune does not move long-context prefill enough to
justify carrying a source change. Keep the validated service recipe unchanged:

```bash
GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8
LLAMA_PREFILL_UBATCH_SIZE=2048
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048
```

Do not retest `nbatch_K=32` or `nbatch_K=128` for this exact
`DKQ=576/DV=512/ncols=16` service lane unless a future FlashAttention rewrite
materially changes the kernel economics.

## Post-Restore Short Decode Sanity

After restoring the active llama.cpp source/build to the pre-`nbatch_K` record
stack, a compact GPU0 sanity run reconfirmed that the record lane still passes
the fixed cold realistic gate:

- evidence:
  `data/gemma4-q8-gpu0-postnbk-restore-sanity-20260702T053257Z-postnbk-restore-sanity/summary.json`
- canary: `64/64` rows pass
- realistic final gate: pass; every row had `cached_tokens=0`
- `MAX_TOKENS=64`, primary metric window `50` generated tokens after TTFT
- median tokens 1-50 after TTFT: `120.296 tok/s`
- p10 / mean tokens 1-50 after TTFT: `104.498` / `119.734 tok/s`
- median full-output tokens after TTFT: `114.594 tok/s`
- median wall-clock full-output throughput: `86.941 tok/s`
- median TTFT: `178.152 ms`

Decision: **sanity only, not a record claim**. This run is useful evidence that
the active binary was restored correctly after the source experiment, but it is
not a full512 LocalMaxxing submission candidate.

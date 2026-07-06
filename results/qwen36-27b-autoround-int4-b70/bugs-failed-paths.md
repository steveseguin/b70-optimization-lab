# Qwen3.6 27B AutoRound Bugs And Failed Paths

This file starts empty by design. Add loader failures, wrong-output signatures,
bad flags, invalid fast paths, and negative optimizations here as they happen.

## Observed During Bring-Up

- Default thinking mode can return OpenAI `content=null` with generated text in
  the `reasoning` field. The first smoke hit this and exhausted `max_tokens=64`
  with `finish_reason=length`. The smoke and launch scripts now disable
  thinking by default via `chat_template_kwargs={"enable_thinking": false}` /
  `--default-chat-template-kwargs '{"enable_thinking": false}'`.
- Initial Intel checkpoint MTP2 smoke did **not** reproduce the public
  0%-acceptance MTP packaging failure. Metrics after manual probes plus smoke:
  `105` accepted draft tokens out of `108`.
- Bring-up used XPU graph off. Do not infer graph safety from the smoke.

## Invalid Fast Paths

- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_FULL_ACCEPT=0` is fast but invalid. It
  produced `51.273 tok/s` median on the strict Qwen realistic suite and
  `74.877 tok/s` on synthetic p512/o512, but failed the 1024-token needle
  quality check with `B!!!!!!!!!!!!!!!!...` while the normal MTP3/cg8 baseline
  passed. The full-accept GDN/Mamba state copy is required; future work should
  make that copy cheaper, not skip it.
- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0` alone is diagnostic-only.
  It showed a speed lift but changed realistic-suite output hashes. Do not use
  it by itself for service, LocalMaxxing, or promoted claims. Important
  exception: pairing it with `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1` is
  the current valid speed win because the forward metadata reads the accepted
  speculative slot as the running source instead of simply dropping the
  accepted-state transition. See
  `promote-source-noacceptedpost-20260703.json`.
- `VLLM_XPU_MAMBA_BATCH_MEMCPY_BLOCK_SIZE=4096` via the preserved experiment
  patch `../../patches/qwen36-27b-autoround-int4-b70/vllm-mamba-batch-memcpy-block-size-env-20260703.patch`
  was no-win (`66.908 tok/s` synthetic vs clean MTP3/cg8 around `66.807`).
  The active source was reverted after the test.
- `max_cudagraph_capture_size=16` with the valid promote-source MTP3 env pair
  is unstable on this stack. During the strict Qwen suite it died with
  `UR_RESULT_ERROR_DEVICE_LOST` at
  `gpu_model_runner.py:_prepare_inputs -> num_accepted_tokens_event.synchronize()`.
  Do not retry cg16 as a config-only speed candidate unless the underlying XPU
  graph/event issue is fixed.
- `VLLM_XPU_SPEC_DECODE_KEEP_ACCEPTED_COUNTS_GPU=1` is no-win. The idea was to
  avoid the scalar accepted-count GPU -> CPU -> GPU round trip in the
  single-request non-align promote-source lane. It passed the strict fresh
  Qwen suite, but the clean same-source comparison lost to the flag-off
  control (`52.542` vs `53.420 tok/s`). The active vLLM source was reverted;
  patch/result are preserved in the July 3 experiment note.
- DFlash SWA/full-KV repair is no-record for this target/draft pair. The
  2026-07-06 PR40898-style patch fixed the old mixed-SWA plumbing failure and
  produced strict fresh diagnostic rows, but the best repaired row was only
  k4 `54.836 tok/s` versus the current `67.519 tok/s` record; k2 was `49.087`
  and k8 was `50.918`, all quality-skipped. Preserve the patch for future
  DFlash/upstream reference, but do not repeat k/capture-size sweeps for
  `z-lab/Qwen3.6-27B-DFlash` on this record lane.

## Current Hot Path

- Accepted-state copy tracing on MTP3/cg8 shows the postprocess copy is
  volume-heavy, not just a small launch overhead:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/mamba-copy-trace-summary-mtp3-cg8-p512o128-20260703T042542Z.json`.
  A p512/o128 diagnostic recorded `36` postprocess copy launches, `96` entries
  per launch, `5.65 GB` copied total, and `~156.9 MB` copied per launch. Full
  accepts accounted for `32/36` copies, and temporal state copy accounted for
  `5.44 GB`. Do not repeat simple memcpy block-size tuning; the next useful
  fix must preserve full-accept recurrent-state semantics while avoiding,
  rotating, or otherwise reducing the physical state-copy volume.

## Watch List

- AutoRound loader mapping: ensure `quant_method=auto-round` and
  `packing_format=auto_round:auto_gptq` stay on an XPU-supported W4A16 path.
- `auto_round` Python package is not installed in the current vLLM venv; vLLM
  may not need it for inference, but any import-time dependency failure belongs
  here.
- MTP head packaging: plain AutoRound Qwen3.5/3.6 checkpoints may quantize
  `mtp.fc` into packed `fc.qweight`, while vLLM's MTP loader expects
  `fc.weight`. If MTP loads but gives 0% acceptance or no speedup, compare the
  Intel checkpoint against the Lorbus packaging before writing source code.
- Tokenizer config: related Qwen3.5 Intel AutoRound snapshots reportedly used
  an incompatible `TokenizersBackend` class. This Qwen3.6 snapshot currently
  reports `tokenizer_class=Qwen2Tokenizer`, so do not patch unless startup
  actually fails in tokenizer construction.
- The local vLLM CLI imports `/home/steve/src/vllm`; record source commit and
  any local diffs before interpreting performance.
- Built-in `qwen3_next_mtp` is useful but must be labeled and target-verified.
- Long context and four-replica service should not be attempted until short
  TP1 smoke is stable.

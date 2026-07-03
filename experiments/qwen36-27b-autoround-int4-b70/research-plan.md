# Qwen3.6 27B AutoRound Optimization Research Plan

Date: 2026-07-03

This plan captures web and local-source research done while the Intel
AutoRound checkpoint was downloading.

## Sources Checked

- Intel model card:
  <https://huggingface.co/Intel/Qwen3.6-27B-int4-AutoRound>
- vLLM Intel quantization docs:
  <https://docs.vllm.ai/en/stable/features/quantization/inc/>
- vLLM Qwen3.6 27B recipe:
  <https://recipes.vllm.ai/Qwen/Qwen3.6-27B>
- Lorbus MTP-fixed AutoRound model card:
  <https://huggingface.co/Lorbus/Qwen3.6-27B-int4-AutoRound>
- Community vLLM Docker/flag reference:
  <https://github.com/tedivm/qwen36-27b-docker>
- LocalMaxxing model index:
  <https://www.localmaxxing.com/en/models>
- vLLM issue on Qwen hybrid MTP and graph/KV-cache degeneration:
  <https://github.com/vllm-project/vllm/issues/40880>
- vLLM issue on Qwen MTP latency regression:
  <https://github.com/vllm-project/vllm/issues/35387>
- Unsloth Qwen3.6 MTP GGUF card and llama.cpp MTP flags:
  <https://huggingface.co/unsloth/Qwen3.6-27B-MTP-GGUF>
- Tokenizer failure report for a related Intel Qwen3.5 AutoRound snapshot:
  <https://forums.developer.nvidia.com/t/vllm-qwen3-5-int4-autoround-intel-tokenizer-failure-fix/365016>

## Facts To Preserve

- Intel's model card says this checkpoint is INT4, group size `128`, generated
  by AutoRound from `Qwen/Qwen3.6-27B`.
- Intel's vLLM example uses TP1, `--max-model-len 2048`,
  `--reasoning-parser qwen3`, served model name `qwen`, and
  `--speculative-config '{"method":"qwen3_next_mtp","num_speculative_tokens":2}'`.
- vLLM's public Qwen3.6 27B recipe describes the base model as dense, hybrid
  GDN attention, 262K native context, and MTP-capable. The recipe says INT4 is
  expected to fit a single 24 GB GPU.
- vLLM's Intel quantization docs list AutoRound as the Intel quantization path
  and say current Intel-platform vLLM support includes W4A16 and W8A16.
- Local vLLM source confirms `quant_method="auto-round"` maps to `INCConfig`;
  `auto_round:auto_gptq` is in the supported packing formats. Do not force the
  community Docker's `--quantization auto_round` spelling in this checkout
  unless the CLI is proven to accept it.

## Immediate Risk: Intel MTP Head Packaging

The Lorbus model card documents a likely issue with plain AutoRound Qwen3.5/3.6
checkpoints: `mtp.fc` can be packed as INT4 (`fc.qweight`) while vLLM's
`Qwen3_5MTP` loader expects an unquantized `fc.weight`. The reported symptom is
that MTP speculative decoding loads but has `0%` acceptance / no speedup.
Lorbus fixed this by dequantizing `mtp.fc` back to BF16, saying the layer is
only about 100 MB and typical prompt acceptance reaches about 80-90%.

Action:

1. First load Intel's checkpoint exactly as requested.
2. Run no-MTP smoke/baseline (`QWEN36_27B_ENABLE_MTP=0`).
3. Run model-card MTP (`qwen3_next_mtp`, `num_speculative_tokens=2`).
4. Inspect logs/metrics for accepted speculative tokens or throughput lift.
5. If MTP is accepted at 0% or no speedup, compare against
   `Lorbus/Qwen3.6-27B-int4-AutoRound` as an alternate packaging of the same
   base/quantization family before writing code.

Local status: initial TP1 smoke with Intel's checkpoint did show healthy MTP
acceptance (`105/108` draft tokens accepted across manual probes plus smoke).
Keep the Lorbus lane as a fallback, but do not switch away from Intel's
requested checkpoint unless a real baseline demonstrates a speed/correctness
problem.

## Tokenizer Risk

A related Qwen3.5 Intel AutoRound snapshot reportedly failed with
`Tokenizer class TokenizersBackend does not exist`. The local Qwen3.6 27B
snapshot's `tokenizer_config.json` currently says `tokenizer_class:
Qwen2Tokenizer`, so do not preemptively patch it. If startup still fails in
tokenizer construction, compare the tokenizer files against the base
`Qwen/Qwen3.6-27B` snapshot and record the exact diff before changing anything.

## Optimization Sequence

### Phase 0: Make It Serve

- TP1, one B70, `max_model_len=2048`.
- MTP on first to mirror the model card; if it fails, immediately retry
  `QWEN36_27B_ENABLE_MTP=0`.
- Record exact vLLM branch, source diff status, torch version, model snapshot,
  and server log.

### Phase 1: Baseline Fresh Decode

- Build a small fixed cold prompt suite.
- Record no-spec vs MTP2 with `cached_tokens=0`.
- Primary early metric: generated tokens 1-100 after TTFT, not warmed repeated
  throughput.
- Check output text quality with JSON, arithmetic, color/order, and practical
  coding prompts.
- Disable thinking for the default short-decode lane with
  `chat_template_kwargs={"enable_thinking": false}`; keep a separate thinking
  lane later if needed.

### Phase 2: MTP / Speculation

Try in order:

- `num_speculative_tokens=1`, `2`, `3`, then maybe `4`.
- `qwen3_next_mtp` versus `qwen3_5_mtp` only if the local vLLM config accepts
  both for this model.
- Disable per-request settings that spec-decode may ignore; keep temperature
  and top-p fixed for reproducibility.
- Track accepted tokens/step, not just output tok/s.

Reject any MTP setting that fails fresh prompt quality, has `cached_tokens>0`,
or depends on repeated-output history.

### Phase 3: XPU Runtime Flags

Only after correctness:

- XPU graph on/off and PIECEWISE capture sizing.
- Treat MTP + graph/KV-cache experiments as correctness-sensitive. Public vLLM
  reports for Qwen hybrid/MTP paths include degenerate output and latency
  regression signatures; every graph/KV change needs the realistic gate, not
  only throughput.
- Prefix caching only as a service/context lane; do not count it for fresh
  response records.
- `--language-model-only` for text-only speed if vLLM accepts it with this
  checkpoint and it does not break the target use case.
- `--enable-chunked-prefill` and `max_num_batched_tokens` screens for prompt
  processing and multi-agent service throughput.
- `kv-cache-dtype=fp8` only as a clearly labeled quality/capacity mode after
  exact gates pass.

### Phase 4: Four B70 Research Throughput

The preferred research loop is four independent TP1 replicas, one per B70, to
screen configs in parallel. TP2/TP4 are secondary experiments; PCIe/CCL overhead
is likely not helpful unless weight bandwidth dominates enough to offset
collectives, and any multi-GPU result needs its own LocalMaxxing lane.

### Phase 5: Accepted-State Copy Optimization

This was the first highest-value INT4 source lane. It produced the current
valid env-pair win, but latest diagnostics show it is no longer the immediate
hot path for the promoted recipe.

Known facts:

- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_FULL_ACCEPT=0` is fast but invalid. It
  proves the full-accept GDN/Mamba state update is hot, but it failed the
  1024-token needle quality gate.
- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0` by itself is invalid /
  diagnostic because it changes realistic-suite output hashes. Do not use it
  alone.
- Pairing `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1` with
  `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0` is the current valid
  env-only win. It passed three strict fresh Qwen-suite rows at `54.861`,
  `53.992`, and `53.522 tok/s`, with a same-window plain-MTP3/cg8 control at
  `48.345 tok/s`. The quality suite also passed with baseline-match. Compact
  packet:
  `../../results/qwen36-27b-autoround-int4-b70/promote-source-noacceptedpost-20260703.json`.
- `VLLM_XPU_MAMBA_BATCH_MEMCPY_BLOCK_SIZE=4096` was no-win. The issue is not
  the inner copy chunk size.
- Trace summary:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/mamba-copy-trace-summary-mtp3-cg8-p512o128-20260703T042542Z.json`.
  The p512/o128 diagnostic recorded `36` accepted-state copy launches, `96`
  entries per launch, `5.65 GB` copied total, `~156.9 MB` copied per launch,
  and `32/36` full-accept copies. Temporal state copy dominates byte volume.
- Later promoted-recipe row-copy tracing found zero records for
  `_xpu_gdn_copy_state_rows_native` /
  `_xpu_gdn_promote_running_state_native`, so the current
  promote-source/no-accepted-postprocess recipe appears to have removed that
  promoted physical row-copy path. Do not keep tuning `batch_memcpy` or row
  copy mechanics without a new trace proving that path is active.

Source-level cleanup remains useful, but it is no longer the next performance
bottleneck:

1. Turn the promote-source env pair into a clean, reviewed source design:
   understand `running_state_source_indices_tensor`, `req_state.block_ids`,
   `mamba_state_idx`, and the block-table contract, then make the accepted
   speculative slot promotion explicit rather than a fragile two-flag combo.
   Keep the flags default-off until strict and quality gates pass.
2. If further slot rotation is unsafe, instrument timing around CPU metadata
   generation, metadata H2D copies, and the `batch_memcpy` kernel separately.
   The result should say whether Python metadata or raw state bandwidth is the
   limiting cost.
3. If raw bandwidth still dominates, prototype a device-side persistent copy plan or
   state layout reduction. Preserve the patch and run the quality suite before
   any strict-suite promotion.
4. Never use the invalid skip flags as service or LocalMaxxing evidence.

### Phase 6: Exact verifier / LM-head cost

This is the current next source lane.

Latest synchronized timing on the promoted recipe:

- `spec_decode.greedy_sample.compute_logits`: `1740` calls, average
  `4.451731 ms`;
- `gpu_model_runner.compute_logits`: `580` calls, average `4.423842 ms`;
- `gpu_model_runner.rejection_sampler`: `568` calls, average `0.440750 ms`;
- proposer model forward: `0.650451-0.830007 ms`;
- metadata / hidden-state selection / copy-buffer regions: small.

Evidence:
`../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-lmhead-verifier-bottleneck.md`.

Next attempts should be source-level and exact:

1. Exact target argmax-only verifier plumbing is closed no-win. It preserved
   exact target replacement / target-owned bonus semantics and passed the
   strict fresh gate with `cached_tokens=0`, but reached only `52.543 tok/s`.
   Do not repeat unless `get_top_tokens` / LM-head internals change. Evidence:
   `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-exact-argmax-verifier-no-win.md`.
2. Test proposer-side `use_local_argmax_reduction` only as a bounded screen.
   Closed no-win. After adding `get_top_tokens()` to the active Qwen MTP draft
   class, the path was active, but same-window GPU crossover measured
   controls at `53.0196 tok/s` average and candidates at `52.9727 tok/s`
   average (`-0.088%`). Evidence:
   `../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-draft-local-argmax-no-win.md`.
3. For a larger win, investigate an AutoRound/INC W4A16 LM-head top-1 or
   candidate-vs-max kernel that avoids materializing full vocab logits for
   greedy verification.

### Phase 7: External Target-Verified Drafters

External drafters remain valid in principle if every accepted token is verified
by the declared Intel AutoRound target and the final gate stays fresh-response
valid. The first EAGLE3 compressed compatibility branch is closed for now:

- `Ex0bit/Qwen3.6-27B-PRISM-EAGLE3` compressed loaded locally and k=1 passed
  the strict suite with `cached_tokens=0`, but only reached `30.063 tok/s` with
  `8734 ms` median TTFT;
- k=2 graph crashed with `UR_RESULT_ERROR_DEVICE_LOST`;
- k=3 graph with default accepted-state handling stalled after 8 prompts and
  hit zero-acceptance intervals;
- k=3 eager also crashed with `UR_RESULT_ERROR_DEVICE_LOST`.

Evidence:
`../../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-03-eagle3-drafter-compatibility.md`.

Do not retest EAGLE3 compressed as config roulette. Revisit only if upstream
vLLM/XPU EAGLE3 changes land, or if testing against stock BF16
`Qwen/Qwen3.6-27B` is needed to separate AutoRound-target mismatch from local
runtime instability. DFlash remains an explicit compatibility candidate, but
the model card references a vLLM PR requirement, so treat it as higher-risk
bring-up rather than a known-good record route.

Variance rule for this lane: same-recipe promoted rows currently span
`53.522-54.861 tok/s` (`2.48%` range of mean, stdev `0.612`). Treat sub-1%
candidate deltas as inconclusive unless a same-window paired/crossover check
supports them.

## Possible Alternate Checkpoints

Use these only after Intel's requested checkpoint has a recorded baseline:

- `Lorbus/Qwen3.6-27B-int4-AutoRound`: likely same family with BF16 MTP head
  preserved for vLLM MTP acceptance.
- `webhie/Qwen3.6-27B-int4-AutoRound`: claims an `auto-round-best` recipe with
  more calibration and preserved MTP/vision support. Treat quality claims as
  unverified until local gates pass.
- GGUF MTP builds such as Unsloth are useful if vLLM/XPU is blocked, but they
  are a different runtime lane and should not be mixed into vLLM results.

## Current Local Notes

- Model download completed into `/mnt/fast-ai/llm-cache/hf`; pinned snapshot:
  `/mnt/fast-ai/llm-cache/hf/hub/models--Intel--Qwen3.6-27B-int4-AutoRound/snapshots/abc86de19eb1ebbf6a7df4582341325c22ddcb7d`.
- TP1 vLLM/XPU smoke passed on GPU0 at port `19410`, with MTP2 enabled and
  XPU graph off.
- Local server metrics showed MTP acceptance is healthy on this runtime:
  `105/108` accepted draft tokens after the smoke/manual probes.
- First smoke exposed a Qwen thinking-template issue (`content=null`,
  non-empty `reasoning`). The smoke and launch scripts now disable thinking by
  default for deterministic content output.
- Local vLLM source is dirty on branch `codex/qwen36-quark-int8-tracking`.
  Record it for all baselines; do not modify it for Qwen27 until a loader or
  correctness failure demands it.
- Post-GGUF bounded vLLM config sweeps reproduced the current promoted
  AutoRound recipe at `53.608 tok/s` and found no stable replacement:
  no-parser was no-win, shorter max context rows were variance-confounded, and
  `MAX_NUM_BATCHED_TOKENS=384` produced one high row (`54.791`) that did not
  repeat (`53.373`). Summary:
  `../../results/qwen36-27b-autoround-int4-b70/post-gguf-config-sweeps-20260703.json`.
  The one-shot runner for future controlled candidates is
  `../../scripts/run-qwen36-27b-autoround-vllm-candidate.sh`.

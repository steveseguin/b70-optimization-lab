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

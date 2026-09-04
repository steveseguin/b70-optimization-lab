# R192: the depth-2 phantom first token appears on the STOCK upstream vLLM XPU image

Date: 2026-09-03 22:45-22:58 EDT, boot 88f0984f. Image `vllm/vllm-openai-xpu@sha256:f01e24f6c7ff...` (the
upstream nightly the lane's chain was built from; no lab patches, no lab env flags), Qwen3.8-27B-FP8, TP2,
`--quantization fp8 --dtype float16`, `qwen3_next_mtp` with `num_speculative_tokens=2`, `--max-model-len 256
--max-num-seqs 64 --max-num-batched-tokens 512`, default compile. Two servers: default (async scheduling on) and
`--no-async-scheduling`; the same 64-prompt sequential pass (greedy, seed 42, 128 tokens). Runner
`scripts/run-20260903-stock-vllm-f01e-mtp2-phantom-r192.sh`; result
`data/2026-09-03-qwen38-stock-f01e-mtp2-phantom-r192-result.json`.

| arm | first token != 271 | cache-c032 head |
|---|---|---|
| async on | none | `[271, 3833, 14542]` (normal) |
| async off | **cache-c032** | `[60, 271, 3833]` (the phantom: the prompt's last token, then the normal answer) |

Also: 60 of 64 rows differ somewhere mid-sequence between the two arms (indices 6-116). That is the unpatched
oneDNN W8A16 GEMM's run-to-run nondeterminism (the R120-R146 census), which the lane's R139 kernel removed; on
stock, which arm shows the phantom is therefore luck-dependent, not async-bound as on the lane's deterministic
build.

Reading: the phantom is not caused by any lab patch; it exists on unpatched vLLM with this model and MTP depth 2.
R194 (queued) repeats on stock: two more compiled arms and two `--enforce-eager` arms. If eager never shows it and
compiled does, the upstream report can stand on stock evidence alone.

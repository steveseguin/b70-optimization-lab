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

## R194 (23:11-23:37): four more stock servers

| arm | first token != 271 |
|---|---|
| default compile, async on (2nd) | none |
| default compile, `--no-async-scheduling` (2nd) | none |
| `--enforce-eager`, async on (1st) | **cache-c040** `[60, 271, 3833]` |
| `--enforce-eager`, async on (2nd) | **cache-c040** |

Stock tally: 2 of 6 servers show the phantom (one compiled async-off, one eager async-on), on different
requests. Tail test on every phantom row (stock and lane): tokens after the phantom equal the normal answer for
16-18 tokens, then drift. So the phantom token was inserted into the output stream without being in the model's
context, and later appended as if generated. This is an upstream defect independent of torch.compile and of
async scheduling; on the lane's deterministic build it manifests in exactly one configuration (piecewise +
async), and the whole-graph compile avoids that history. Published wording corrected accordingly; issue draft
`drafts/2026-09-03-vllm-issue-piecewise-mtp2-phantom.md` rewritten on the stock evidence (not filed).

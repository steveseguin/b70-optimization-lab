# Review: "OpenVINO vs vLLM vs llama.cpp, Qwen3.8-27B, on Intel Arc Pro B70"

A public post links SergiioB's
[intel-arc-pro-b70-inference-cookbook](https://github.com/SergiioB/intel-arc-pro-b70-inference-cookbook)
and states: "FP8 on vLLM needs two cards (30.9 GB physically cannot fit one
32 GB card)". Reviewed September 15, 2026 from the cookbook's README,
`docs/qwen38-27/FP8-TP2-W8A16.md`, `docs/qwen38-27/QWEN38-VLLM-XPU.md` and
`docs/BENCHMARK-CATALOG.md`. Their numbers are quoted as their self-reports; the
lab did not rerun their recipes, and no lab number below confirms theirs.

## "FP8 physically cannot fit one card": not correct

- The lab loaded the official `Qwen/Qwen3.8-27B-FP8` (revision `017b9c7a…`,
  66 files, 30,866,866,928 bytes, which is 28.7 GiB) on **one** B70 on
  August 26 in the same `f01e24f…` vLLM XPU image family the cookbook uses. It
  served an 8,448-token capacity in eager mode at 0.96 memory utilization, MTP0,
  about 10.75 tok/s at 2K-8K context
  ([result](../../../experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-official-fp8-tp1-fit-depth-r2-result.md)).
- A B70 exposes about 31.9 GiB of usable VRAM, so the weights alone leave
  roughly 3 GiB before runtime, compile, activation and KV memory.
- The cookbook's own catalog lists a single-card FP8 reroute measurement
  ("roughly 34% speedup and 48 token/s at p1024") excluded from its rankings,
  which also contradicts "physically cannot fit".

What is fair: a **practical** FP8 server needs two cards. On one card there is
too little room for long context, compiled graphs or MTP draft buffers. The
lab's strict one-card control on August 27 measured 11.41 tok/s and matched
only 8 of 12 reference outputs on that older arithmetic
([result](../../../experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-fp8-tp1-strict-target-control-result.md)).

## What the lab packages

- **FP8 on vLLM:** two cards only, in
  [packages/qwen38-27b-fp8-tp2-b70](../../../packages/qwen38-27b-fp8-tp2-b70/README.md)
  with the [reproduction guide](../../../repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md).
  There is no one-card FP8 package, and one is not recommended.
- **One card on vLLM:** AutoRound INT4
  ([recipe](../../../repro/qwen38-27b-autoround-int4-b70/README.md)).
- **One card on llama.cpp:** GGUF Q4_K_M and Q8_0 packages, with and without
  MTP2.

## Speed comparison (different methods; not like-for-like)

The lab's decode numbers use a fixed set of 12 varied natural prompts, each
answered once, with outputs up to 512 tokens and required to match a reference
exactly. The cookbook's use synthetic prompts (p512/p1024 with 128 forced
tokens), greedy decoding and five samples, with no output-exactness gate. Its
FP8 page says "No token-exact, logit/KL, task-quality, or independent-reproduction
claim exists."

| Setup | Cookbook | Lab |
| --- | --- | --- |
| vLLM FP8, 2 cards | MTP8: 53.4 (p512) / 60.1 (p1024) tok/s greedy; 22.2 / 11.7 with the model card's sampling | MTP1 54.9, MTP depth 5 86.2 tok/s, 12/12 exact outputs |
| vLLM INT4, 1 card | GPTQ-INT4 MTP4: 83.7 tok/s (BF16 draft), 112.7 (INT4 draft overlay), 106.7 in a LocalMaxxing run | AutoRound INT4: 81.2 tok/s |
| vLLM INT4, 2 cards | not listed | AutoRound INT4: 117.5 tok/s |
| llama.cpp, 1 card | Q4_K_M 20.0, Q5_K_M 17.0, Q8_0 13.6 tok/s (no MTP) | Q4_K_M 27.8, Q4_K_M + MTP2 42.6, Q8_0 19.6, Q8_0 + MTP2 37.1 tok/s |
| OpenVINO, 1 card | 15.8 tok/s | not measured |

Prompt-reading rates also use different definitions. The cookbook's "cold
input" rate comes from the client and includes fixed overhead (1,207 and 1,736
input tok/s at p512/p1024). The lab's FP8 rates are server prefill (2,859,
3,677 and 3,305 input tok/s at 512, 2,048 and 16,384 tokens).

## Bottom line

- The two-card FP8 statement is an overstatement: FP8 fits one B70, but only as
  a slow, short-context server that the lab does not package.
- The cookbook's one-card INT4 draft-overlay results are higher than the lab's
  one-card INT4 row, but they use a different checkpoint, draft and method.
  They need a matched run on the lab's strict suite before any comparison.
- The lab has no OpenVINO measurement for this model.

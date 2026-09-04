# DRAFT for review (not filed). Target: github.com/vllm-project/vllm issues

## Title
[XPU][Spec decode] Qwen3.8 MTP (num_speculative_tokens=2): about 1 request in 64 starts its answer with an extra token that the model never generated (the prompt's last token), on the unmodified upstream image

## Summary (plain language)
We run Qwen3.8 27B (FP8) on two Intel Arc Pro B70 GPUs with vLLM and speculative decoding (two draft tokens).
When we send 64 short prompts one after another, sometimes one answer starts with an extra token: the last
token of the prompt (a `]`) shows up as the first token of the answer, and then the real answer follows.

We know the model did not produce that token: the rest of the answer is word-for-word the normal answer for
the first 16 to 18 tokens, exactly as if the extra token were not there. Then, later, the answer drifts, because
by then vLLM has appended the extra token to the conversation as if the model had chosen it.

It happens on the unmodified upstream XPU image, with the default compile and also with `--enforce-eager`, with
async scheduling on and off, on 2 of 5 servers we ran (the request it hits varies). On our own build of the
same commit, which has deterministic kernels, it hits the same request every single time with the default
piecewise compile plus async scheduling, and never with `--compilation-config '{"splitting_ops": []}'`,
`--enforce-eager`, or `--no-async-scheduling`; we think that is the deterministic build picking one history,
not a fix.

## Environment
- vLLM 0.27.2rc1.dev77+gac7509e2b (commit ac7509e2b), XPU; image `vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f` (unmodified)
- torch 2.13.0+xpu, 2x Intel Arc Pro B70 (`--tensor-parallel-size 2`), Ubuntu 24.04
- Model: Qwen/Qwen3.8-27B-FP8 (hybrid GDN + full attention)
- `vllm serve /model --dtype float16 --quantization fp8 --kv-cache-dtype auto --block-size 64 --max-model-len 256 --max-num-seqs 64 --max-num-batched-tokens 512 --no-enable-prefix-caching --language-model-only --speculative-config '{"method":"qwen3_next_mtp","num_speculative_tokens":2}'`

## Steps to reproduce
1. Serve as above (default settings; also reproduces with `--enforce-eager`).
2. Send 64 prompts sequentially (concurrency 1), greedy: `temperature 0`, `seed 42`, `max_tokens 128`,
   `ignore_eos true`, completions API with `return_token_ids`. Our prompts: 64 short variants of one text
   (`<suite file link>`), 26-31 tokens each.
3. Repeat the whole pass a few times (the stock kernels are not bit-deterministic, so which pass shows it varies).

Observed: one row starts `[60, 271, 3833, ...]` where every other pass gives `[271, 3833, ...]` for that prompt.
Token 60 is `]`, the prompt's last token. Tokens 1..17 of the bad row equal tokens 0..16 of the good row; the
rows diverge from about token 16-18 on.

Seen on: `cache-c032` (default compile, `--no-async-scheduling`), `cache-c040` (`--enforce-eager`, async on).
Not seen on 3 other servers (default compile async on x2, `--no-async-scheduling` x1).

## What we ruled out on the deterministic build (each with a run)
- Stale KV/Mamba state pages (zeroing GDN conv/ssm pages on allocation: no change; note that `KVBlockZeroer`
  never zeroes Mamba pages because only `AttentionSpec` managers record new block ids).
- GDN kernel inputs/outputs and attention metadata (seq_lens, query_start_loc, slot_mapping, block_table):
  bit-identical between a failing and a clean run for all 64 requests.
- Inductor `allow_buffer_reuse`, `max_fusion_size`, `pattern_matcher`, all vLLM pass_config passes: no change.
- Device barrier before each step, blocking H2D copies: no change.
- In-situ: for the affected request the last two rows of the final hidden state differ from the clean run
  and the two TP ranks disagree on the last row (everything else identical).

## Why we think it is bookkeeping around the first spec-decode step
The inserted token is always the prompt's last token, and the answer continues as if the token were absent
before drifting later. That looks like a stale value at the "previous sampled token" position being
returned/appended for the request's first step, rather than a wrong model prediction.

## Extra data
Full notes, prereg and result JSON (R176-R194):
https://github.com/steveseguin/b70-optimization-lab/tree/main/experiments/qwen38-27b-b70/notes

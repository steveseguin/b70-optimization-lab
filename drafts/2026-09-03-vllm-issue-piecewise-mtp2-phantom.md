# DRAFT for review (not filed). Target: github.com/vllm-project/vllm issues

## Title
[XPU] With async scheduling + MTP (num_speculative_tokens=2), the default piecewise torch.compile makes one request in 64 start its answer with a wrong token; `splitting_ops=[]` fixes it

## Summary (plain language)
(Note for reviewer: on stock vLLM the unpatched W8A16 GEMM is nondeterministic run to run, so which server shows the wrong first token varies; on our deterministic build it is the same request every time.)

We run a Qwen3.8 27B model on two Intel Arc Pro B70 GPUs with vLLM. When we turn on speculative decoding with two draft tokens and send 64 short prompts one after another, the 33rd answer always starts with a wrong first token: the model repeats the last word of the prompt (or emits a stray space) before answering normally. It happens every time, on the same prompt, and only with:

- async scheduling on (the default), and
- vLLM's normal compile mode, which cuts the model into pieces at every attention layer and compiles each piece.

It goes away if we do any one of these: turn async scheduling off, run without torch.compile, compile the whole model as one graph (`--compilation-config '{"splitting_ops": []}'`), or use Dynamo only (`mode: 2`). So the model math is fine; the bug is in how the compiled pieces hand data between steps while the scheduler is already preparing the next step.

We looked inside: for that one request, the last two rows of the final hidden state are wrong, and the two GPUs even disagree with each other on the last row (they agree on every other row and on every other request). That looks like a kernel reading memory that the previous step left behind.

## Environment
- vLLM 0.27.2rc1.dev77+gac7509e2b (commit ac7509e2b), XPU build, vllm-xpu-kernels 1e90ffa
- torch 2.13.0+xpu, Intel oneAPI 2026.1.1, 2x Intel Arc Pro B70 (TP=2), Ubuntu 24.04
- Model: Qwen/Qwen3.8-27B-FP8 (hybrid GDN + full attention), `--quantization fp8 --dtype float16 --kv-cache-dtype auto --block-size 64 --no-enable-prefix-caching --language-model-only`
- `--speculative-config '{"method":"qwen3_next_mtp","num_speculative_tokens":2}'`, `--max-model-len 256 --max-num-seqs 64 --max-num-batched-tokens 512`
- XPU graphs disabled (default on this platform), compilation mode VLLM_COMPILE (3), inductor backend
- Reproduced on the unmodified upstream image `vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f` (R192: one of two default-compile servers showed it; R194 repeats pending, see below). Our own deeper runs used the same vLLM commit with local kernel patches that make the W8A16 GEMM deterministic; those patches do not touch the compile pipeline, and on that deterministic build the effect is 100% reproducible and strictly tied to async scheduling.

## Steps to reproduce
1. Serve the model with the flags above (async scheduling on, default compile).
2. Send the 64 prompts from `<suite file>` sequentially (concurrency 1), greedy (`temperature 0`, `seed 42`, `max_tokens 128`, `ignore_eos`), completions API with `return_token_ids`.
3. Compare the first token of each answer to a run of the same server with `--no-async-scheduling` (or with `--enforce-eager`).

Expected: identical first tokens. Observed: request 33 (`cache-c032` in our suite) starts with token 60 (`]`, the prompt's last token) or 220 (a space); the rest of the answer then continues from that wrong token.

## What we ruled out (each with a run)
- Stale KV/Mamba state pages: zeroing the GDN conv/ssm pages on allocation does not change it (note: `KVBlockZeroer` never zeroes Mamba pages because the scheduler only records new block ids for `AttentionSpec` managers; that is a separate, harmless-here gap).
- The GDN kernel and its metadata: layer-0 inputs/outputs are bit-identical between the failing and the clean run for all 64 requests.
- Attention metadata (seq_lens, query_start_loc, slot_mapping, block_table): identical in both runs.
- Inductor knobs `allow_buffer_reuse=False`, `max_fusion_size=1`, `pattern_matcher=False`, and every vLLM `pass_config` pass off: no change.
- Device barrier before each step and blocking H2D copies: no change.

## What removes it (measured on our deterministic build of the same commit)
- `--no-async-scheduling`
- `--enforce-eager`
- `--compilation-config '{"mode": 2}'` (DYNAMO_TRACE_ONCE)
- `--compilation-config '{"splitting_ops": []}'` (one Inductor graph)  <- our fix
- a mutating custom op inserted after every decoder layer (forces extra splits)

## Extra data
- In-situ measurement of the final-norm output for the failing request (abs-sum of last row, TP0/TP1): failing run 5982.85 / 6022.08, clean run 7167.73 / 7167.73; row before last 6518.65 vs 6510.96; every other request identical.
- Full notes and prereg/result JSON: https://github.com/steveseguin/b70-optimization-lab/blob/main/experiments/qwen38-27b-b70/notes/2026-09-03-qwen38-fp8-mtp2-phantom-inductor-knobs-r184-result.md

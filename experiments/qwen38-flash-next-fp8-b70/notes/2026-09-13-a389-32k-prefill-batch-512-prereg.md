# Preregistration: A389 - a 512-token prefill batch on the 33,280-capacity MTP0 server

## Question

At 32K input the promoted lines take 200 s to the first token because prefill runs in 64-token
batches (`max_num_batched_tokens=64`, a literal frozen into every packet since the eager era). Decode
does not touch that setting. With the wider placement freeing VRAM, can the 32K server prefill in
512-token batches and still produce the same output ids at every depth, and what does TTFT become?

## Arm

A389: the A381 packet with `PREFILL:512` (new generator option: the engine kwarg, the config assert,
the identity print and the server CLI arg move from 64 to 512; nothing else changes). Overlay
`2a372e86`, served stage, MAX_MODEL_LEN 33280, KV 1,341,530,112, never-hit + max-count-2 placement,
8 GB host floor, port 20006, the same depth ladder (2K/8K/16K/32K, two rows). Queued after A388.

## Gate and predictions

- Lossless: every depth's output ids must equal A381's (`afffd211`, `0126d542`, `789cbcb8`, `1cc1699e`).
  Prefill chunking changes the attention and MoE batch shapes during prefill, so this is a real test;
  the KV written by prefill is what decode reads.
- TTFT: if the prefill step is launch-bound at 64 tokens, 512-token batches cut TTFT by several times
  (32K: 200 s toward 30-60 s); decode rates unchanged (31-33 tok/s).
- Memory: a 512-token prefill needs more activation VRAM; if allocation fails the server does not
  reach health and the next step is 256.

## Stop rules

Server fails health (VRAM) -> retry at 256; any depth's ids differ from A381 -> the 64-token batch
stays the served identity and the result is recorded as a negative; rows fail.

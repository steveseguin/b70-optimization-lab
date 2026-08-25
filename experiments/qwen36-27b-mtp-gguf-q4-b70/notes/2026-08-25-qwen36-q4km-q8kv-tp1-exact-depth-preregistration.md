# Qwen3.6 Q4_K_M q8_0-KV TP1 exact-depth preregistration

Date: 2026-08-25. State: **preregistered; not launched**.

This is the q8_0-KV companion to the Qwen3.6 Q4_K_M F16-KV exact-depth arm.
At preregistration, all seven matching target-only cells remain missing in the
family coverage contract. The packet binds the same independently registered
Q4_K_M child at repository revision
`5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace`, 17,106,773,120 bytes, SHA-256
`a7cbd3ecc0e3f9b333edee61ae66bc87ed713c5d49587a8355814722ed329e0f`.
The model is present on the read-only USB store.

One frozen `llama-bench` invocation measures target-only MTP0 at exact active
depths `0`, `2048`, `4096`, `8192`, `16384`, `24576`, and `32768`. It uses
one B70, graph off, q8_0 K/V cache, FlashAttention on, `pp2048`, `tg128`, and
five repetitions. Passing the complete parser and lifecycle gate adds exactly
seven raw-engine cells. It does not measure HTTP serving and does not run a
fresh quality battery.

## Runtime choice and campaign isolation

The packet checksum-pins and reuses the committed Qwen3.6 Q4_K_M/F16 wrapper
for model/runtime identity and hardened lifecycle infrastructure only. The new
wrapper keeps the four canonical and legacy locks, including
`/tmp/b70-gpu0.lock`, and the corrected process census that rejects
`llama-batched-bench`. The q8_0 selectors, argv, metadata, campaign ID,
acknowledgement, and output root are independently frozen.

The F16 run root is never read, written, renamed, or reused by this packet.
The q8_0 arm cannot launch while the F16 arm owns any shared lock, and its
preflight also rejects an active F16 `llama-bench` process. This lets packet
preparation proceed during the F16 campaign without introducing a second GPU
owner.

There is no minimum speed gate. A q8_0 slowdown at long context is useful
evidence and does not lower or overwrite featured, promoted, or historical
decode speeds. No F16 result, Qwen3.8 result, or cross-quant quality judgment
is transferred into these cells.

## Launch

After these files are committed and pushed on clean `main`, and only after the
F16 arm has reached a clean terminal state and all four locks and GPU0 are idle:

```bash
python3 -B experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q4km-q8kv-tp1-exact-depth-r1.py \
  --execute \
  --ack 'RUN qwen36-q4km-q8kv-tp1-exact-depth-20260825-r1'
```

The default invocation is inert; `--check` performs only static CPU checks.

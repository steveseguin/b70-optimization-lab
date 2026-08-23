# Ornith 1.5 35B-A3B: keep flash attention enabled

Date: 2026-08-23 EDT

Status: **CLOSED CORRECTNESS/PERFORMANCE NEGATIVE**

The accepted recipe inherited `--flash-attn auto` from the Qwen-family lane,
but the lab had no explicit Ornith on/off comparison. A fixed-seed 128-token
screen tested the otherwise unchanged accepted 11-feature stack with
`--flash-attn off`.

Disabling flash attention changed the extracted transcript SHA-256 from the
canonical
`2e7965fcdc273f0433df359cff5188ae3585426fd32f28536121d1b5e35dad18`
to
`fe89f8ea8ca33aaf71341abacde9d883a8a7f19e88cc1b82f0632f6d94818e12`.
The same coarse run observed 83.3 tok/s generation, below the contemporary
flash-attention controls, but that observation is diagnostic only: exactness
failed, so no matched engine or fresh-server performance claim was made.

Keep `--flash-attn auto` in the validated Ornith packet. Raw stdout, stderr,
and the extracted transcript are under `../data/ornith-flash-off.*`; the
structured result is
`../data/2026-08-23-ornith35b-flash-attention-off-summary.json`.

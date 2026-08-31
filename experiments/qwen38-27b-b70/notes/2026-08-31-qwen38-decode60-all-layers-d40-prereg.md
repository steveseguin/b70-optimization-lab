# Qwen3.8 token-60 all-layer trace D40 preregistration

Date: 2026-08-31

Status: **preregistered before D40 model requests**

D39 made the M=71 prefill GDN boundary exact in four fresh processes, but the
first generated-token difference remains index 60. With two earlier engine
profile/warmup calls and prefill at per-layer call index 2, generated token 60
is produced by decoder-layer call index 62.

D40 wraps all 64 `Qwen3_5DecoderLayer` instances. At call 62 it retains
stream-ordered clones of each layer's input, hidden output, and residual; after
layer 63 completes it hashes the snapshots and writes one trace. Hashing and
CPU synchronization occur only after the complete decoder stack. Across four
fresh processes, identify the earliest layer/input or layer/output field with
more than one hash. This is a localization experiment only; no quality or
performance claim is authorized.

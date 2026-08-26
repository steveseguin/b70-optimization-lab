# Official f01e AutoRound TP1 eager MTP1/F16 8K sentinel R1

Status: **preregistered and executable; not launched**.

This is the current-f01e TP1/MTP1/eager/F16 exact-8K parent. It does not
depend on the blocked b2dd MTP2 campaign: that MTP2 full arm drafted and accepted
tokens and passed quality but missed a conservative separate-boot target
oracle on 2/25 coherent outputs. That older-image MTP2 result is conservatively
quarantined and is neither MTP1 nor current-f01e evidence.

There is no external draft model. The native MTP tensors live inside the exact
target repository revision in `model_extra_tensors.safetensors` (298,305,576
bytes, SHA-256 `94102b67...`). The index maps all 29 `mtp.*` tensors to that
file. Config says one hidden MTP layer with shared embeddings. MTP1 uses that
one native trained module for one speculative step, without recurrent reuse
beyond the trained depth. The unrelated llama.cpp external Q4_0 MTP artifact
must never be bound here; it diverged from its target at token six.

The exact requested binding is
`{"method":"qwen3_next_mtp","num_speculative_tokens":1}`. The continuity
alias is deprecated but was accepted by b2dd and resolves to method `mtp`.
Startup must prove the exact target model path as the resolved speculator,
depth one, AutoRound `quantization=inc`, F16/auto KV, explicit eager mode, and
no graph capture. An exact unsupported-method line may classify `unsupported`;
an explicit missing/native-MTP-weight line is a binding failure; a generic
timeout or worker failure stays generic `failed`.

One server lifetime snapshots speculative counters immediately before and
after the exact 8K request. Startup and later quality traffic cannot satisfy
the acceptance gate: drafted delta must be positive, accepted delta must be
positive, and accepted cannot exceed drafted. The exact request must pass all
prompt-depth, 128-completion, token-ID, cache-zero, and timing gates.

Target verification compares all 128 candidate IDs to the frozen same-image
TP1/MTP0/eager/F16 exact-8K receipt, whose token hash is `34e792cc...`. A
mismatch quarantines the arm. Because this oracle is cross-boot and target-only
compile variability is already known, a mismatch alone must not be described
as causal MTP corruption. The full frozen quality battery must also pass after
the exact request.

The current-f01e MTP4 evidence is an explicit limit, not supporting evidence
for depth one. Its first 8K sentinel matched all 128 target-only tokens, but
the later expansion on a separate boot diverged first at token 99. At 32K the
same expansion returned only 121/128 tokens before EngineCore died on the
`spec_token == num_spec_decodes * (num_speculative_tokens + 1)` assertion.
Therefore even a clean MTP1 8K pass authorizes only a separately preregistered
depth expansion; it does not establish long-context or 32K safety.

The current-f01e MTP3 expansion is also a limit: all six exact requests and
all six isolated acceptance gates passed, full quality and cleanup passed, but
only five of six frozen MTP0 token oracles matched. Its 2K arm first diverged
at token 90. That partial curve neither authorizes MTP1 nor predicts its result.

The runner pins the f01e image/source/package, target and native MTP artifact,
model config/index/quantization, target-only oracle and terminal receipt,
fixture, helpers, and baseline. It requires fresh ext4 roots, port `19479`, an
idle host, clean pushed `main`, the canonical GPU lock, one exact container,
global EXIT/INT/TERM cleanup, and strict postflight.

There is no speed floor. A result has no authority when acceptance, target,
quality, identity, or cleanup fails. Evidence is additive and cannot lower or
replace protected results; this sentinel fills at most its single exact 8K
parent cell and authorizes no automatic descendants. Failed exact, acceptance,
target, or quality gates retain a quarantined lower-grade diagnostic receipt.

Static check:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-mtp1-f16-eager-8k-sentinel-r1.sh --check
```

GPU execution:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-mtp1-f16-eager-8k-sentinel-r1.sh \
  --execute \
  --ack 'RUN qwen38-official-f01e-autoround-tp1-mtp1-f16-eager-8k-sentinel-20260826-r1'
```

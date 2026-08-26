# Official f01e AutoRound TP1 eager MTP4/F16 8K sentinel R1

Status: **preregistered and executable; not launched**.

This is the current-f01e TP1/MTP4/eager/F16 exact-8K parent. It is not a
rerun of the blocked b2dd campaign: that MTP2 full arm drafted and accepted
tokens and passed quality but missed a conservative separate-boot target
oracle on 2/25 coherent outputs, so its dependent MTP4 never ran. The newer
f01e identity and this exact-context contract are separate evidence.

There is no external draft model. The native MTP tensors live inside the exact
target repository revision in `model_extra_tensors.safetensors` (298,305,576
bytes, SHA-256 `94102b67...`). The index maps all 29 `mtp.*` tensors to that
file. Config says one hidden MTP layer with shared embeddings. vLLM recurrently
reuses that one trained module for four speculative steps; MTP4 does not mean
four independent trained heads, and vLLM warns that reuse at depth greater than
one may reduce acceptance. The unrelated llama.cpp external Q4_0 MTP artifact
must never be bound here; it diverged from its target at token six.

The exact requested binding is
`{"method":"qwen3_next_mtp","num_speculative_tokens":4}`. The continuity
alias is deprecated but was accepted by b2dd and resolves to method `mtp`.
Startup must prove the exact target model path as the resolved speculator,
depth four, AutoRound `quantization=inc`, F16/auto KV, explicit eager mode, and
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

The runner pins the f01e image/source/package, target and native MTP artifact,
model config/index/quantization, target-only oracle and terminal receipt,
fixture, helpers, and baseline. It requires fresh ext4 roots, port `19473`, an
idle host, clean pushed `main`, the canonical GPU lock, one exact container,
global EXIT/INT/TERM cleanup, and strict postflight.

There is no speed floor. A result has no authority when acceptance, target,
quality, identity, or cleanup fails. Evidence is additive and cannot lower or
replace protected results; this sentinel fills at most its single exact 8K
parent cell and authorizes no automatic descendants.

Static check:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-mtp4-f16-eager-8k-sentinel-r1.sh --check
```

GPU execution:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-mtp4-f16-eager-8k-sentinel-r1.sh \
  --execute \
  --ack 'RUN qwen38-official-f01e-autoround-tp1-mtp4-f16-eager-8k-sentinel-20260826-r1'
```

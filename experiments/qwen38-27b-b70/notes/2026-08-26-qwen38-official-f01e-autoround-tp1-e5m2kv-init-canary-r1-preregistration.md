# Official f01e AutoRound TP1 E5M2-KV init/canary sentinel R1

Status: **preregistered and executable; not launched**.

The older immutable e9d nightly explicitly rejected E5M2 KV cache at engine
initialization: `NotImplementedError` reported that XPU FlashAttention did not
support `fp8_e5m2` KV cache. All four attempted E5M2 arms failed at the same
parent gate, so its descendants were correctly closed without more GPU runs.

The immutable f01e runtime is a materially different source family—vLLM
`0.27.2rc1.dev77+gac7509e2b.xpu` at `ac7509e2b`, rather than
`0.26.1rc1.dev1102+ge9d1398d9`. This permits one init-first reopen, not an
assumption that backend support changed.

The packet uses the exact f01e AutoRound TP1/MTP0/eager identity already
qualified for F16 and E4M3, changing only `--kv-cache-dtype fp8_e5m2`. If the
server boots and proves the E5M2/eager/AutoRound startup markers, it runs one
exact 128-token active-context canary with 128 returned token IDs and cache
zero. Only a passing canary triggers the complete frozen quality battery in
the same server lifetime.

An exact-image log line that names E5M2, KV cache, and unsupported or invalid
dtype semantics closes the result as `unsupported`. A generic timeout, worker
failure, import error, or startup failure remains `failed`. A passing canary
plus passing full quality closes green; a quality failure preserves the canary
as screened evidence but authorizes no expansion.

There is no speed floor and no protected result may be replaced or relabeled.
All evidence is additive. One GPU/server lifetime, fresh ext4 roots, port
`19470`, clean pushed `main`, exact frozen hashes, direct model verification,
the canonical GPU lock, global EXIT/INT/TERM container cleanup, and strict
postflight are mandatory.

Static check:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-e5m2kv-init-canary-r1.sh --check
```

GPU execution:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-e5m2kv-init-canary-r1.sh \
  --execute \
  --ack 'RUN qwen38-official-f01e-autoround-tp1-e5m2kv-init-canary-20260826-r1'
```

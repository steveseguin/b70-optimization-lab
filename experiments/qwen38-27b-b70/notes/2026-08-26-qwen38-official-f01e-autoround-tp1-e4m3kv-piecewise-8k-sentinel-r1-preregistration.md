# Official f01e AutoRound TP1 PIECEWISE E4M3-KV 8K sentinel R1

Status: **preregistered and executable; not launched**.

The current f01e AutoRound TP1/MTP0/eager/E4M3-KV parent passed its complete
2K/4K/8K/16K/24K/32K exact-depth curve, the full frozen quality battery, and
strict cleanup. Its terminal receipt is pinned by SHA-256 in this runner. That
green parent authorizes one PIECEWISE graph sentinel, not a blind graph curve.

This packet changes only graph identity from the qualified eager E4M3 profile.
It uses `VLLM_XPU_ENABLE_XPU_GRAPH=1` and an explicit PIECEWISE compilation
configuration with capture size one. Startup must prove E4M3 KV, AutoRound,
`enforce_eager=False`, the PIECEWISE mixed prefill/decode capture marker, and
finished graph capture while proving no FULL decode-capture marker.

One GPU/server lifetime runs exact active context 8K with 128 output tokens,
then the complete frozen quality battery on that same server. Both must pass,
along with strict cleanup, for `passed-quality-clean-sentinel`. A passing depth
measurement with failed quality is quarantined and cannot authorize the six-
depth PIECEWISE expansion.

The immutable f01e image/source/package, AutoRound model revision, TP1/MTP0,
E4M3 dtype, server sizing, GPU0 selection, baseline, and frozen helpers match
the eager parent. Output, cache, port `19471`, and container identity are fresh.
The runner requires clean pushed `main`, direct model verification, ext4 roots,
an idle host, the canonical GPU lock, global EXIT/INT/TERM cleanup, and strict
postflight.

There is no speed floor. New evidence is additive and cannot replace or lower
the protected F16, eager E4M3, or existing graph-profile results. Even a pass
requires a separately preregistered graph-depth expansion.

Static check:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-e4m3kv-piecewise-8k-sentinel-r1.sh --check
```

GPU execution:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-e4m3kv-piecewise-8k-sentinel-r1.sh \
  --execute \
  --ack 'RUN qwen38-official-f01e-autoround-tp1-e4m3kv-piecewise-8k-sentinel-20260826-r1'
```

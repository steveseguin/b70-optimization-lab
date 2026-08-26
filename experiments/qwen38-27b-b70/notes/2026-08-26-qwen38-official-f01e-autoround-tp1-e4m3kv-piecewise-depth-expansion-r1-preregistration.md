# Official f01e AutoRound TP1 PIECEWISE E4M3-KV depth expansion R1

Status: **preregistered and executable; not launched**.

The identical current-f01e TP1/MTP0/PIECEWISE/E4M3-KV sentinel passed exact
8K at `28.726353926869724 tok/s`, the complete frozen quality battery, all
startup identity gates, and strict cleanup. Its terminal receipt is pinned by
SHA-256 in this runner. That parent authorizes this six-depth expansion.

The server identity is unchanged: immutable f01e image/source/package,
revision-pinned AutoRound model, TP1/MTP0, E4M3 KV cache, GPU0, explicit
PIECEWISE graph capture at size one, server sizing, caches disabled, and the
same frozen quality baseline. One server lifetime measures exact active
contexts 2K, 4K, 8K, 16K, 24K, and 32K with 128 generated token IDs and the
99-interval metric, then runs the full quality battery.

All six independent depth gates, full quality, and strict cleanup must pass
for `passed-quality-clean-expansion`. Passing depths remain screened evidence
if another depth fails. If all depths pass but quality fails, the measurements
are quarantined rather than promoted.

Startup must prove AutoRound, E4M3 KV, `enforce_eager=False`, the PIECEWISE
mixed prefill/decode capture marker, finished graph capture, and absence of a
FULL decode-capture marker. The runner also requires clean pushed `main`, exact
frozen hashes, the passing sentinel receipt, direct model verification, fresh
ext4 roots, port `19472`, an idle host, the canonical GPU lock, global
EXIT/INT/TERM cleanup, and strict postflight.

There is no speed floor. Every new result is additive and cannot lower or
replace any protected F16, eager E4M3, or existing graph result. Site
publication remains a separate evidence-reviewed action.

Static check:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-e4m3kv-piecewise-depth-expansion-r1.sh --check
```

GPU execution:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp1-e4m3kv-piecewise-depth-expansion-r1.sh \
  --execute \
  --ack 'RUN qwen38-official-f01e-autoround-tp1-e4m3kv-piecewise-depth-expansion-20260826-r1'
```

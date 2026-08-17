# Reproduce Qwen3.8 27B Q8_0 target-only TP2 on two B70s

This is the primary quality-conservative Qwen3.8 27B service snapshot for two
ASRock Intel Arc Pro B70 32 GiB cards. It uses Q8_0 target weights, F16 KV,
and no MTP, DFlash, draft model, response reuse, or speculation.

## Accepted result

- conventional 99-interval median: **`36.772932 tok/s`**
- p10: `36.046576 tok/s`
- full-output after-TTFT median: `36.661845 tok/s`
- TTFT median: `178.841 ms`
- cold suite: 12/12 complete output hashes exact against the matched control;
  every request had `cached_tokens=0`
- semantic gate: exact copy, arithmetic, JSON, factual, logic, Python-result,
  repeat-stability, and 3,829-token needle tests all passed on 2026-08-16

The 2026-08-17 snapshot adds a shape-scoped SG16 workgroup for the recurrent
GDN quad. Two order-balanced, same-binary cold-suite pairs both favored SG16.
Pooling the pair-level statistics measured `+0.257%` on the primary
tokens-1-100 median, `+0.481%` on full-decode median, and `+0.413%` on
full-decode mean. All four suites produced the same 12 complete output hashes;
the seven semantic canaries, eight repeats, and 3,829-token needle also matched
the promoted oracle exactly. A clean accepted-source `A-B-B-A` direct-decode
sanity bracket measured `37.321045` versus `36.978696 tok/s` (`+0.926%`). The
historical `36.772932 tok/s` conventional headline remains the highest valid
cold-suite capture and is not replaced by the lower-throughput matched A/B
session.

A fresh replay of the corrected full source stack on 2026-08-16 again passed
12/12 complete hashes and 12/12 cache-zero requests. It measured
`36.421061 tok/s` conventional (`36.788950` under the historical 100-event
metric), `36.471332 tok/s` full-output after TTFT, and `177.177 ms` median
TTFT. That is `0.957%` below the original conventional headline and within
the observed process-state spread. See the
[provenance correction](../../experiments/qwen38-27b-b70/notes/2026-08-16-q8-repro-provenance-correction.md).

Reasoning-mode provenance: the accepted speed capture above used
reasoning-enabled output and its stored completions contain `<think>`. The
current launcher intentionally uses `--reasoning off`; it is the
quality-conservative service default but is a distinct benchmark identity. A
position-balanced reasoning-off replay measured control medians of
`35.841542` and `36.288690 tok/s`, with 12/12 identical hashes across both
controls and two experimental arms. See the
[reasoning-off replay packet](../../experiments/qwen38-27b-b70/notes/2026-08-16-q8-distributed-greedy-argmax-neutral.md).
Always record reasoning mode when comparing or reproducing rates.

The launcher also selects the Unified Runtime Level Zero v2 adapter
explicitly. On the validated 2026.1.1 runtime, leaving the selector unset
already chose v2 (`36.040325` versus `36.079986 tok/s`, matched bracket), so
this is a reproducibility pin rather than a claimed speed gain. Forcing the
legacy adapter reduced target-only decode by `3.375%`; see the
[adapter audit](../../experiments/qwen38-27b-b70/notes/2026-08-16-q8-level-zero-v2-adapter-audit.md).

Keep `GGML_SYCL_COMM_DIRECT_Q8=2`. Experimental mode `3`, which attempted to
execute both cards' handoffs from one peer-visible kernel, caused an immediate
Level Zero device-lost/reset storm on the first bounded smoke and is
[explicitly rejected](../../experiments/qwen38-27b-b70/notes/2026-08-16-q8-peer-pair-collective-unsafe.md).

The semantic gate is deliberately stronger than output parity within one
quantization family. Q8 and Q4_K_M both returned `14` for the Python canary;
the tested GPTQ INT4 checkpoint returned `30`, so the faster GPTQ/MTP route is
not the quality-default deployment.

## Exact artifacts

- model: <https://huggingface.co/ggml-org/Qwen3.8-27B-GGUF/tree/0669b98607d47046c7c2b3f801011d54a08cfccf>
- file: `Qwen3.8-27B-Q8_0.gguf`
- bytes: `28,595,763,552`
- SHA-256: `f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8`
- source base: mndodd `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`
- exact source snapshot: [patch packet](../../patches/qwen38-27b-q8-tp2-asrock-b70/README.md)

The patch packet uses the one-chain Q8 DP4A body that produced this result and
then applies the Qwen3.8-only recurrent-quad SG16 increment. The later Qwen3.6
two-chain `DP4A2` schedule passed Qwen3.8's
quality gate but was not faster in two full cold suites, so it is not part of
this reproduction. See the [transfer decision](../../experiments/qwen38-27b-b70/notes/2026-08-16-q8-dp4a2-transfer-no-win.md).

## Build

After restoring the source patch, source oneAPI 2026.1 and configure a Release
BMG-G31 AOT build with `GGML_SYCL=ON`, `GGML_SYCL_TARGET=INTEL`,
`GGML_SYCL_DEVICE_ARCH=bmg_g31`, `GGML_SYCL_F16=ON`, graph and DNN off,
host-memory fallback off, and Level Zero API support on. Build
`llama-bench llama-cli llama-server` with `-j2` inside a 6/8 GiB cgroup. Do
not overlap the build with a model workload on a 16 GiB-class host.

The validated pre-DP4A2 source snapshot originally produced:

- `llama-server`: `d1d5f8d2c7903ef7a84eb9e698689fa803d1c59650d7dce914253efae2bb75b4`
- `llama-bench`: `b7fbea3d9081ea8c97350d90a63403039f30e99eecc6aea7ae98d4d4d3fed6c2`
- `libggml-sycl.so`: `707ea1b8f19b69aa31f968dd461815b408a552aaf2f4bfe23d3f83b0ee0e08ed`

The fresh correction replay used a later host-only relink (`llama-server`
`d0ca5aa6...`, `llama-bench` `8788242b...`) with the same exact
`707ea1b8...` SYCL library. Hashes are provenance aids; source patch, build
flags, runtime doors, model hash, output hashes, and cache-zero gate are the
portable reproduction contract.

The clean SG16 promotion build on oneAPI 2026.1.1 produced:

- `libggml-sycl.so.0.19.0`:
  `0b3cc38ce20fad568976a1ab1db1deda831eb375d49976c217c25fc02d7f3c26`
- `llama-bench`:
  `ce3ad8809ceca3dcc063ed00e93bfe0744d892b45af9c56e33c061d09c8cbc47`
- `llama-cli`:
  `d94c8cb6f3c0a3997bd24286ed0ff1e417860e3ff5913320edb7b012a49fbde3`
- `llama-server`:
  `b26ad789f7372c7a409183aa870dd52589cf9fb654c8324055517b1ff1cfd528`

## Run and verify

```bash
QWEN38_SOURCE_DIR=/path/to/llama.cpp-qwen38-q8-tp2 \
QWEN38_BUILD_DIR=/path/to/llama.cpp-qwen38-q8-tp2/build-sycl-aot-bmg-g31 \
QWEN38_MODEL=/path/to/Qwen3.8-27B-Q8_0.gguf \
  repro/qwen38-27b-q8-tp2-asrock-b70/run-server.sh
```

Wait for `/health` before benchmarking or stopping the endpoint. In another
terminal:

```bash
OUT=/path/to/result.json repro/qwen38-27b-q8-tp2-asrock-b70/bench.sh
repro/qwen38-27b-q8-tp2-asrock-b70/verify-artifacts.sh
```

The reference selector is `level_zero:1,0`, addressed as `SYCL0,SYCL1` by the
server. Confirm enumeration on another host. The launcher is loopback-only,
uses equal TP2, one slot, 8K context, F16 KV, FlashAttention, cache RAM zero,
context checkpoints zero, fit off, and an 8/10 GiB host-memory scope.

For the wider semantic test, run
[`scripts/qwen38-text-quality-suite.py`](../../scripts/qwen38-text-quality-suite.py)
against the endpoint. The 2026-08-16 decision evidence is summarized in the
[quality/KV validation note](../../community/sergiiob-qwen38-27b-vllm-xpu/validation/2026-08-16-quality-kv-dtype-decision.md).

## LocalMaxxing package

The policy-checked target-only Q8 submission package is
[`qwen38-27b-q8-tp2-target-only-36.773tok-20260815.queue.json`](../../experiments/qwen38-27b-b70/localmaxxing/qwen38-27b-q8-tp2-target-only-36.773tok-20260815.queue.json).
It records the conventional `36.772932 tok/s` interval metric, exact model and
server identities, all prompt/output hashes, the cache-zero gate, and the raw
completions thinking-mode provenance. Local validation passes. An
authenticated server dry-run and real submission remain pending because this
host currently has no LocalMaxxing API credential.

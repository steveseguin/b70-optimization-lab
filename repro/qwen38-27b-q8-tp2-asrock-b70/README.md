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

Reasoning-mode provenance: the accepted speed capture above used
reasoning-enabled output and its stored completions contain `<think>`. The
current launcher intentionally uses `--reasoning off`; it is the
quality-conservative service default but is a distinct benchmark identity. A
position-balanced reasoning-off replay measured control medians of
`35.841542` and `36.288690 tok/s`, with 12/12 identical hashes across both
controls and two experimental arms. See the
[reasoning-off replay packet](../../experiments/qwen38-27b-b70/notes/2026-08-16-q8-distributed-greedy-argmax-neutral.md).
Always record reasoning mode when comparing or reproducing rates.

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

## Build

After restoring the source patch, source oneAPI 2026.1 and configure a Release
BMG-G31 AOT build with `GGML_SYCL=ON`, `GGML_SYCL_TARGET=INTEL`,
`GGML_SYCL_DEVICE_ARCH=bmg_g31`, `GGML_SYCL_F16=ON`, graph and DNN off,
host-memory fallback off, and Level Zero API support on. Build
`llama-bench llama-cli llama-server` with `-j2` inside a 6/8 GiB cgroup. Do
not overlap the build with a model workload on a 16 GiB-class host.

The accepted local binaries are identified by:

- `llama-server`: `32c581628082fa1352824650d45f523d52b526aaefdfd23e1c34d438f7ad084a`
- `llama-bench`: `f7010c08b534a4f338b9cbd83f97f22b82f13ddab5be0c727d16c3bb0f8c4312`
- `libggml-sycl.so`: `944e2ddb026bfdcd3147323f7edbfdabbae7754a51cfdb74149045f8895ddd5f`

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

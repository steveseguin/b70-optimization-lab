# Reproduce official Qwen3.8 27B FP8 TP2 on two B70s

This is a quality-gated, target-only vLLM/XPU service snapshot for two ASRock
Intel Arc Pro B70 32 GiB cards. It uses Qwen's official block-scaled FP8
weights, native FP16 KV, TP2, one graph-captured decode size, and no MTP,
DFlash, draft model, response reuse, or speculation.

## Captured result

- median decode after TTFT: **`21.708532 tok/s`**
- median wall rate: `19.624649 tok/s`
- median TTFT: `626.227 ms`
- five unique p512/g128 requests; all completed 128 tokens and reported
  `cached_tokens=0`
- decode CV: `0.0738%`
- eager control: `17.097358 tok/s`; the captured size-one graph improved it
  by about `26.97%`

This is slower than the repository's GGUF Q8_0 TP2 record (`36.772932 tok/s`)
and Q4_K_M record (`49.717503 tok/s`). Its value is a working, pinned official
FP8/vLLM baseline and a clean starting point for XPU GDN and collective work.

## Quality boundary

The final graph run passed all seven exact semantic cases, eight identical
repeat runs, and a 3,829-token needle test. Every checked output hash matched
the established Q8_0 oracle, including the Python-result canary (`14`). Prefix
caching was disabled and every quality/benchmark request reported zero cached
tokens.

Longer free-form benchmark continuations were not byte-identical between the
eager and graph modes, so this packet does **not** claim universal token-exact
equivalence for arbitrary prompts. The official FP8 target is quantized and
should not be described as lossless BF16.

## Exact identities

- model: [`Qwen/Qwen3.8-27B-FP8`](https://huggingface.co/Qwen/Qwen3.8-27B-FP8/tree/017b9c7af6b5689d5dd426a76e0bc077eb5ca20a)
- revision: `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`
- 66 Safetensors files, `30,866,866,928` bytes
- aggregate basename-sorted `sha256sum` manifest:
  `82fb8f84fa117c81c3e8639c4675709dfb667d70ddaa2fd097d35fc37d95453a`
- image: `vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f`
- vLLM: `0.27.2rc1.dev77+gac7509e2b`
- Torch: `2.13.0+xpu`

The image selected `XPUFp8BlockScaledMMKernel`. It used Qwen Triton kernels
for the Qwen3.8 GDN path; that fallback is the principal source-level
optimization opportunity.

## Download and verify

Download the exact Hugging Face revision into one directory. For example,
with a recent `huggingface-cli`:

```bash
huggingface-cli download Qwen/Qwen3.8-27B-FP8 \
  --revision 017b9c7af6b5689d5dd426a76e0bc077eb5ca20a \
  --local-dir /mnt/fast-ai/llm-models/qwen3.8-27b-fp8

repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/verify-model.sh \
  /mnt/fast-ai/llm-models/qwen3.8-27b-fp8
```

Verification reads all 30.9 GB and fails on any file-count, byte-count, or
aggregate checksum mismatch.

## Start and benchmark

```bash
MODEL_DIR=/mnt/fast-ai/llm-models/qwen3.8-27b-fp8 \
VLLM_CACHE_DIR=/mnt/fast-ai/vllm-cache/q38-official-fp8-f01e/vllm \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-server.sh
```

The first start compiles 51 artifacts and took about 88 seconds locally. A
warm cache starts much faster, but reloading it briefly exceeded an 8 GiB host
cgroup; the launcher therefore uses the validated 9 GiB RAM / 12 GiB
RAM-plus-swap bounds. Do not remove the bounds on a 16 GB host.

After `/health` succeeds, benchmark from another terminal:

```bash
OUT=/path/to/result.json \
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/bench.sh
```

The launcher binds the endpoint to loopback, maps both `/dev/dri` devices, and
uses `ZE_AFFINITY_MASK=0,1`. Verify device enumeration before copying that
selector to a different host. Stop with `docker stop -t 20 qwen38-fp8-tp2`;
never interrupt the engine while graph initialization is still in progress.

## Deliberate settings

- `--tensor-parallel-size 2`
- `--dtype float16 --quantization fp8 --kv-cache-dtype auto`
- context 4,096; block size 64; max sequences 4; max batched tokens 256
- prefix caching disabled; text-only model path
- PIECEWISE graph capture limited to request size 1
- oneCCL direct send/receive, TCP loopback OFI, pidfd IPC, simple collective
  thresholds pinned high
- `CCL_TOPO_P2P_ACCESS=0`: forcing `1` changed decode by only `-0.011%`

vLLM warns that XPU Graph is officially supported only for single-GPU use.
This TP2 graph result is therefore experimental and stays fail-closed behind
the exact local quality gate. See the
[full experiment note](../../experiments/qwen38-27b-b70/notes/2026-08-16-official-fp8-vllm-graph-tp2.md)
and [structured result](../../experiments/qwen38-27b-b70/data/2026-08-16-official-fp8-vllm-graph-tp2.json).

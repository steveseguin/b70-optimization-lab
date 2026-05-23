# FAQ

## What is an Intel Arc Pro B70?

The B70 is a workstation/AI-oriented Intel Arc Pro GPU with 32 GB of VRAM. For local LLM work, the draw is memory capacity per dollar: 32 GB lets more models or larger context fit on the GPU than 16 GB and 24 GB cards.

## Why use four B70s?

Four cards provide 128 GB of aggregate VRAM. That does not behave like one simple 128 GB card; the software must split work across GPUs. For vLLM, this usually means tensor parallelism. For llama.cpp, it may mean SYCL tensor split, row split, layer split, or RPC workers depending on the model and backend.

## Should I buy two B70s or four?

Two is easier: cheaper platform, less power, less heat, fewer slot/layout problems, and often enough for Qwen-class FP8 or smaller local inference. Four is for capacity, larger model experiments, and concurrency headroom. Four is also more work; some models scale poorly if communication overhead dominates.

## Can I run MiniMax M2.7 INT4 on one B70?

Not with this recipe. The documented MiniMax M2.7 INT4 vLLM path uses tensor parallel size 4 across four B70s. Smaller models are better first targets for one card.

## Are B70 blower cards loud?

That depends on case airflow, load, fan curve, and where the system sits. Dense blower cards can be reasonable if intake is not blocked, but a four-card rig should be treated like a workstation/server build rather than a silent desktop by default. Community build notes should include whether the system is home-office tolerable.

## Are extra heatsinks or temperature stickers required?

No. They can be useful for quick visual checks or build documentation, and they may make photos easier to understand, but they are not part of the software recipe. If they affect cooling, document exactly where they were placed and why.

## Why does the recipe require so much SSD space?

The model is large, build trees are large, Hugging Face cache is large, and vLLM/Inductor compile caches can grow. The recipe assumes at least 512 GB of SSD so the machine does not fail halfway through a build or model download.

## Why can a 16 GB RAM system still work?

Runtime weights live mostly on the GPUs, but the native build can need much more host memory than 16 GB. The recipe creates temporary SSD swap for the heavy `vllm-xpu-kernels` compile. This is slower than having 128 GB+ RAM, but it makes the build possible.

## Why not just use Docker?

A container would help, but this stack still depends on exact host GPU drivers, Level Zero, oneAPI/compiler pieces, PyTorch XPU ABI compatibility, and native XPU kernel builds. A good future goal is an Intel-supported container or installer that pins these pieces.

## What is vLLM?

vLLM is the serving engine used here. It exposes an OpenAI-compatible API and handles model loading, scheduling, tensor parallel execution, KV cache management, and generation.

## What API do I get after setup?

The documented server exposes common OpenAI-compatible endpoints:

- `GET /health`
- `GET /v1/models`
- `POST /v1/completions`
- `POST /v1/chat/completions`
- `POST /v1/responses`
- `GET /metrics`

The base URL for LAN clients is:

```text
http://<server-ip>:8000/v1
```

## Why bind to `0.0.0.0`?

`0.0.0.0` makes the vLLM server listen on all network interfaces, so another machine on the LAN can reach it. Only do this on a trusted network or behind a firewall/reverse proxy.

## What does "quality gate" mean?

It means speed is not accepted unless output quality also passes. The MiniMax recipe checks exact token hashes, semantic canaries, arithmetic repeatability, and an extended six-prompt suite before benchmarking.

## Why do docs mention both total tok/s and output tok/s?

Total tok/s includes prompt tokens plus generated tokens. Output tok/s counts generated tokens only. Long prompt or short output tests can make total tok/s look very different from decode speed. Always label which number you mean.

## Is 83 output tok/s worse than the earlier 89-94 tok/s notes?

For pure output-token speed, yes, but the comparison needs labels.

The old `94 tok/s` result was a constrained structured-output lane, not the same
random p512/n1536 decode test. The closer comparison is the older strict
`89.314 output tok/s` p512/n1536 lane versus this fresh host's `83.17-83.79
output tok/s`.

The current host is running the cards over PCIe4 x16. A PCIe5 x16 path has about
twice the raw signaling rate. Our XCCL allreduce check matched that simple
math: the older reference was `27.88 GB/s`, while this host measured
`13.79 GB/s`, almost exactly half. MiniMax TP4 decode communicates across GPUs
often, so that is a plausible reason for most of the gap without changing model
quality.

Also compare warm runs to warm runs. Cold runs can be much slower because they
include compilation, graph capture, cache setup, or model-load effects.

## Is prompt processing/prefill good?

Yes. On the live 32k-context endpoint, prompt-heavy requests with `max_tokens=1`
measured about `1.7k-1.8k prompt tok/s` for 2k-16k prompts. The tradeoff is
time to first token: a 16k prompt took about `9 s` before the generated token.

## Can I use this for production?

Treat it as a reproducible lab baseline, not a finished production appliance. Production still needs service supervision, authentication, firewalling, monitoring, log rotation, restart policy, request limits, and a rollback plan.

## Why are there Intel compiler errors if the server works?

During one startup, Intel `ocloc`/IGC logged an internal compiler error while compiling a Triton reduction kernel, then vLLM continued and served successfully. That should still be reported and fixed; ambiguous nonfatal compiler crashes are not acceptable UX for ordinary users.

## What should community contributors publish?

Publish the model, quantization, hardware, OS, driver/runtime versions, exact commands, quality gate, benchmark shape, output tok/s, total tok/s, and raw artifacts. Negative results are useful too if they save others from repeating a bad path.

## Why talk about concurrency?

Single-request tok/s is only one metric. A local endpoint for coding or agentic workflows may need multiple overlapping requests, tool calls, long contexts, or background jobs. Multi-card systems can be valuable even when batch-1 tok/s does not scale perfectly.

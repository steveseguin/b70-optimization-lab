# MiniMax M2.7 INT4 AutoRound On B70

This packet is the maintained index for the MiniMax M2.7 INT4 AutoRound work
on four Intel Arc Pro B70 GPUs. It links the established recipes and evidence
without relocating the path-sensitive historical artifacts.

MiniMax results in this repository cover different tasks and must not be
collapsed into one score:

| Lane | Shape / purpose | Result | Quality and status | Primary pointer |
| --- | --- | --- | --- | --- |
| Fresh Ubuntu 24 deployable endpoint | TP4, p512/n1536 comparison at 2K; service supports 32K | `83.172` output tok/s, `110.896` total tok/s | Exact token hashes, semantic, arithmetic, and extended checks passed; maintained deployment starting point | [110 tok/s-class deployment repro](../../repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md) |
| Historical strict speed baseline | TP4, p512/n1536, ctx2048, batch 1 | `89.314195` output tok/s, `119.085594` total tok/s | Four clean repeats after strict quality gates; historical source/runtime packet | [89 tok/s strict repro](../../repro/minimax-m27-b70-89tps-20260520/README.md) |
| Constrained structured HTML | TP4, short constrained output | `94.406` effective accepted output tok/s | `30/30` accepted, zero rejects; valid only for the declared constrained task | [structured-lane note](../../notes/2026-05-22-minimax-structured-fast-lane-regex2.md) |
| Long-context service observation | TP4, prompt 32264 / output 64 | `63.91` output tok/s after TTFT | Approved service/capacity observation, not comparable to p512/n1536 speed rows | [production service guide](../../docs/minimax-production-c1-service.md) |

## Reproduction And Operations

- Fresh Ubuntu deployment:
  [repro/minimax-m27-b70-110tps-ubuntu24-20260523](../../repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md).
- Older strict-speed reproduction:
  [repro/minimax-m27-b70-89tps-20260520](../../repro/minimax-m27-b70-89tps-20260520/README.md).
- Production c1 service:
  [docs/minimax-production-c1-service.md](../../docs/minimax-production-c1-service.md).
- Session-cache and long-context research:
  [experiments/minimax_xpu_kv_offload](../../experiments/minimax_xpu_kv_offload/README.md).
- ReAP/AutoRound source experiments:
  [experiments/minimax-m27-reap-autoround-vllm](../../experiments/minimax-m27-reap-autoround-vllm/README.md).

## Interpretation Rules

- Keep constrained output, unconstrained generation, short decode, prefill,
  long-context, and concurrent-service results in separate comparison classes.
- AutoRound INT4, GGUF IQ4, FP16/BF16 activation, and compressed-KV lanes are
  separate quality identities.
- A faster graph result is not promoted unless the corresponding exact-token,
  semantic, arithmetic, and practical-task gates pass.
- Treat old accepted LocalMaxxing rows as historical evidence when later
  quality work changes their classification.
- Preserve failed patches and negative screens. Many of the best MiniMax leads
  came from ruling out launch flags and locating collective or fused-boundary
  costs instead.

## Historical Detail

The former top-level README chronology is preserved verbatim in
[the 2026-07-11 archive](../../notes/2026-07-11-readme-historical-b70-archive.md).
Detailed chronological evidence remains in `../../notes/`, structured results
in `../../data/`, and patch outcomes in `../../patches/`; those established
paths are intentionally not reorganized.

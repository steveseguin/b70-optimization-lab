# Arc Pro B70 + vLLM XPU, Qwen3.8-27B GPTQ INT4, 52 tok/s (Reddit report)

Status: **community-reported.** Source: r/LocalLLaMA post "Intel Arc Pro B70
+ vLLM XPU: 52 tok/s on Qwen3.8-27B INT4, 128K context, working tools +
agent" (https://www.reddit.com/r/LocalLLaMA/comments/1vulh45/). Relayed by
the maintainer 2026-08-22. Original raw logs not captured; the numbers below
are the poster's, not reference-lab measurements.

Maintainer checks performed: internal arithmetic/consistency, and
cross-reference to our archived GPTQ-route validation
([sergiiob](../../sergiiob-qwen38-27b-vllm-xpu/STATUS.md)). NOT performed:
running the poster's exact image/model/config; the rates are unverified here.

## Reported setup

- Hardware: 1x Arc Pro B70 32 GiB (31.9 GiB usable), 256 EUs; Ubuntu 26.04,
  kernel 7.0, 12 cores / 29 GiB RAM; in-kernel `xe`.
- Stack: Intel XPU (OMIX 0.3.0, DPC++ 2026.1, Level Zero 1.28.6,
  compute-runtime 26.22); vLLM 0.27.1 XPU (`vllm/vllm-openai-xpu:latest`,
  torch 2.13.0+xpu) in Docker.
- Model: Qwen3.8-27B GPTQ INT4 (sym G128, desc_act off, lm_head unquantized,
  MTP heads BF16), ~19.6 GB.
- Config: MTP2 speculative decoding, **fp8 KV cache**, prefix caching ON,
  graph mode PLAIN (eager+inductor), 64K production / 128K optional,
  `--max-num-seqs 1`.

## Reported speeds (poster; 5 runs/depth, single card = TP1)

| Config | median tok/s | vs off | GPU power |
| --- | ---: | ---: | ---: |
| MTP off | 33.2 | - | 230 W |
| MTP1 | 47.1 | +42% | 186 W |
| MTP2 | 52.2 | +57% | 174 W |
| MTP3 | 51.6 | +55% | 174 W |
| MTP4 | 51.9 | +56% | 176 W |

Prefill ~1.5K tok/s short; 763 tok/s at 111.8K. TTFT 0.18 s short;
~49 s cold at 64K; 146 s at 128K. Deep decode: 44.5 tok/s at ~50K (64K
profile), 35.8 tok/s at ~98K (128K profile). Context ladder 32K/64K/96K/128K
all PASS needle; 128K needs 0.95 util; 192K+ infeasible in 32 GB.
Vision PASS, tool-calling PASS, headless OpenCode agent test PASS.
llama.cpp SYCL best 29.0 tok/s (Q5_K_M, MTP2) -> vLLM ~1.8x.

## Reported caveats (operationally useful)

- **D17**: MTP + concurrent requests crash the engine on this hybrid model;
  worked around with `--max-num-seqs 1`. With MTP off, full concurrency works
  at ~33 tok/s.
- **D15**: vLLM 0.27.1 XPU prefix-caching pointer bug; worked around with a
  bind-mounted patch to `mamba_utils.py` (candidate upstream report).
- 128K marginal (~2.5 GB headroom); cold TTFT >64K slow; verbose reasoner
  (give generous `max_tokens`).
- Occasional repeated-token degeneration after very long agent turns; restart
  clears it (classic reasoning-model collapse).
- `xpu-smi` reports GPU utilization N/A; power/frequency are the proxies.

## Cross-reference and reconciliation (maintainer)

Our archived reference-lab GPTQ run (same family, one ASRock B70, target-only,
p512/g128, n=5) measured MTP1/2/4 = **54.18 / 68.23 / 83.70 tok/s** - higher
than the poster's 47.1 / 52.2 / 51.9. Consistent direction (MTP helps; MTP2 a
strong point) but ~24% lower absolute for the poster. Plausible causes, not
yet isolated: newer image (0.27.1 / torch 2.13 vs our pinned
`0.20.2rc1.dev13`), **fp8 KV** overhead vs our f16, the 64K-context serving
profile vs our 8K measurement, and eager+inductor PLAIN vs our PIECEWISE
graph. The MTP ladder SHAPE (off < 1 < 2 ~= 3 ~= 4, MTP2 the sweet spot) is
consistent across both, and the ~33 tok/s MTP-off floor is close to our TP2
detpad off-MTP region.

The GPTQ target itself failed our Python-result quality canary (`30` instead
of `14`) that Q8/Q4_K pass, so this route remains **quality-rejected as a
default** and experimental, independent of its speed. See
[the GPTQ quality/KV decision](../../sergiiob-qwen38-27b-vllm-xpu/validation/2026-08-16-quality-kv-dtype-decision.md).

## What the lab is doing with this

The poster's fp8-KV, MTP-ladder, prefix-caching, and `max-num-seqs 1`
findings feed the lab's own **TP1 benchmark matrix** (our AutoRound INT4
model, MTP off/1/2/3, context <=32K, KV fp8 vs f16, decode + prefill) to
fill the single-card blanks and validate these directions on our
quality-accepted model. Results land in the Qwen3.8 model board.

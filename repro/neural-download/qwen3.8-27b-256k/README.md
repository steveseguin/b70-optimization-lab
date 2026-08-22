# Qwen3.8-27B 256K flagship package — neural.download packet (DRAFT: fit-off pending)

Status: **FIT-OFF DECIDED — UD-Q5_K_S ships as the flagship quant**
(2026-08-22). It loaded and completed the diagnostic suite on one B70 at
`--ctx-size 262144` with q8_0 K/V, the vision mmproj, and the MTP draft
all resident, with **2.86 GiB VRAM still free**. Package suite rate
(**MTP-assisted**, 128/100 window, cache-zero): `27.004 tok/s` median /
`24.084` p10 (spread is content-dependent draft acceptance). UD-Q4_K_XL
becomes the documented headroom alternative. Target-only companion
number, canaries, and vision smoke still pending for the published
packet.

## Identity (all from `unsloth/Qwen3.8-27B-GGUF` @ `4ca720788d1e01f1bff70c033e0d0028fd02e502`)

| Component | File | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| Weights candidate A | `Qwen3.8-27B-UD-Q4_K_XL.gguf` | 17,559,178,144 | `3f227079003add2511437e5b1e94812e363385225bf6a9b47b0054a72bc8b01e` |
| Weights candidate B | `Qwen3.8-27B-UD-Q5_K_S.gguf` | 18,665,753,504 | `d8d62ffcf84d42658dd6ccf9782b4d0404700af78b26d750507510c7597b5bfe` |
| Vision tower | `mmproj-F16.gguf` | 927,607,488 | `cbb841a9ee0636b2ec172f5bb8df2ea8dfeb01e90fe7c6126581d662a0b4e43e` |
| MTP draft | `MTP/mtp-Qwen3.8-27B-Q4_0.gguf` | 1,369,590,656 | `50d9ce5a6da381bbcfb31061cf73df94a90e6faf8efeddee379a9cb8f1501c6e` |

Store: `/mnt/usb-models/llm-models/qwen3.8-27b-unsloth-gguf/`. Base:
upstream llama.cpp `9fee29e9435f...`, SYCL AOT bmg-g31. Device: 1x B70.

## The fit-off (preregistered decision rule)

Architecture: 64 layers, 16 full-attention (4 KV heads x head_dim 256),
so KV at 262144 costs 16.0 GiB at f16 or 8.5 GiB at q8_0. Paper budget
(31.5 GiB card): weights + KV(q8_0) + mmproj 0.87 + draft 1.28 (+draft
KV) + compute buffers + slack. Q4_K_XL fits with ~1.4 GiB margin;
Q5_K_S has ~0.2 GiB paper margin — inside the error bar of the
compute-buffer estimate.

Rule: load each candidate with the full package (262144 ctx, q8_0 K/V,
mmproj, MTP draft) on one B70. The **highest quant that loads and
completes the diagnostic suite at 262144 without OOM ships as the
package quant**; the other is recorded as an alternative operating
point at whatever context it supports. f16-KV variants are published
only as reduced-context operating points, never as the 256K headline.

## Recipe, benchmarks, quality — TBD (per the packet standard)

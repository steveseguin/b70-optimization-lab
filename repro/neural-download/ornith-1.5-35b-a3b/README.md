# Ornith 1.5 35B-A3B — neural.download packet (DRAFT: benchmarks pending)

Status: **intake verified pending; no published numbers yet.** Lane:
enthusiast MoE, one card first, two-card comparison only after a valid
one-card baseline (preregistered order).

## Identity

| Field | Value |
| --- | --- |
| Model | Ornith 1.5 35B-A3B, arch `qwen35moe` (256 experts / 8 used, 41 layers, GQA 16/2, embed 2048, native ctx 262144) |
| File | `Ornith-1.5-35B-Q4_K_M.gguf` (21,713,462,848 bytes) |
| SHA-256 | `ca6ea26329c88b78ffd90a85163be2e746c2fafd1024f56db47e499f117f9a7f` |
| Source | `ornith-ai/Ornith-1.5-35B-A3B-GGUF` @ `fbbaed45c2f0e200276ffa51701a24d45dc7f57e` |
| Store | `/mnt/usb-models/llm-models/ornith-1.5-35b-a3b-q4km/` (catalog id `ornith-15-35b-a3b-q4km`) |
| Base | upstream llama.cpp `9fee29e9435f865ec0b811a783a6471a136d9317`, SYCL AOT bmg-g31, IntelLLVM 2026.0.0 |
| Device | 1x Intel Arc Pro B70 (32 GiB); 2x comparison later |

Question this packet answers: validate the new family and an outside
one-B70 performance claim independently. The external report is a lead,
not evidence; only matched local runs are published.

## Recipe, benchmarks, quality — TBD (per the packet standard)

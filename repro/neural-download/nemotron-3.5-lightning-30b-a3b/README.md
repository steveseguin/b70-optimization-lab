# Nemotron 3.5 Lightning 30B-A3B — neural.download packet (DRAFT: benchmarks pending)

Status: **intake verified (direct+ordinary I/O) and baseline PASSED**
(2026-08-22) — the family runs on Intel B70 with no NVFP4 assumption.
Lane: mid MoE.

**Intake diagnostic baseline (1x B70, 8K ctx, f16 KV, target-only,
128/100 window, cache-zero verified): `72.873 tok/s` median /
`72.712` p10.** Full packet operating points still pending.

## Identity

| Field | Value |
| --- | --- |
| Model | NVIDIA Nemotron 3.5 Lightning 30B-A3B, arch `nemotron_h_moe` (hybrid Mamba-family, 53 blocks, 128 experts / 6 used, embed 2688, native ctx 1,048,576; official base `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16`) |
| File | `NVIDIA-Nemotron-3.5-Lightning-30B-A3B-UD-Q4_K_M.gguf` |
| SHA-256 | `edcb5d4650796ed2fb412498de6f83b585862312c747ddb74f0ea04b22206181` |
| Source | `unsloth/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-GGUF` @ `f2d3fe3694501008786e81e5f20360cbf715496a` |
| Store | `/mnt/usb-models/llm-models/nemotron-3.5-lightning-30b-a3b-udq4km/` (catalog id `nemotron-35-lightning-30b-a3b-udq4km`) |
| Base | upstream llama.cpp `9fee29e9435f865ec0b811a783a6471a136d9317`, SYCL AOT bmg-g31, IntelLLVM 2026.0.0 |
| Device | 1x Intel Arc Pro B70 (32 GiB); 2x comparison later |

Question this packet answers: does the family run on Intel B70 without
assuming NVIDIA's NVFP4 runtime works there.

## Recipe, benchmarks, quality — TBD (per the packet standard)

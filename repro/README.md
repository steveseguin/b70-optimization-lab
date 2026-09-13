# Reproduction Artifacts

This directory preserves several kinds of reproduction material. A directory
under `repro/` is **not automatically a beginner install guide**: some entries
are portable candidates, while others deliberately depend on lab source trees,
binaries, caches, models, or topology.

The authoritative classification is
[`guide-catalog.json`](guide-catalog.json). Its policy and promotion gates are
defined in the
[`reproduction-guide certification standard`](../docs/reproduction-guide-certification.md).
Run `python3 tools/validate-repro-guides.py` before changing a guide, its
dependencies, or a public “Read guide” link.

No entry is currently certified as a `starter-guide`. The website therefore
labels the current material as lab reports, expert reproductions, record
capsules, or research status. A starter label will appear only after the exact
instructions pass on a clean supported machine.

## Portable Candidates

These have substantial acquisition, restoration, launch, and validation
material. Their README and catalog entry list the remaining certification
gaps.

| Reproduction | Cards | Main remaining gate |
| --- | ---: | --- |
| [Qwen3.8 27B Q4_K_M llama.cpp/SYCL TP1](qwen38-27b-q4km-tp1-b70/) | 1 | Tested host-platform install and clean-host replay; [candidate package](../packages/qwen38-27b-q4km-tp1-b70/) |
| [Qwen3.8 27B Q8_0 llama.cpp/SYCL TP1](qwen38-27b-q8-tp1-b70/) | 1 | Tested host-platform install and clean-host replay; [candidate package](../packages/qwen38-27b-q8-tp1-b70/) |
| [Qwen3.8 27B official FP8 vLLM/XPU TP2](qwen38-27b-fp8-vllm-tp2-asrock-b70/) | 2 | Tested host-platform install and clean-host replay; [candidate package](../packages/qwen38-27b-fp8-tp2-b70/) |
| [Laguna S 2.1 INT4, 102 tok/s](laguna-s-2.1-int4-b70-102tps-20260726/) | 4 | Tested host-platform install and independent replay |
| [MiniMax M2.7, 110 tok/s](minimax-m27-b70-110tps-ubuntu24-20260523/) | multi-card | Immutable platform package lock and current clean-host replay |
| [MiniMax M2.7, 89 tok/s](minimax-m27-b70-89tps-20260520/) | multi-card | Current clean-host replay and beginner recovery path |
| [Muse-Glimmer-30B Q8, 100 tok/s](muse-glimmer-30b-q8-woq-b70-100tps-20260813/) | 4 | Platform installer, complete original model identity, independent replay |
| [Qwen3.6 27B AutoRound INT4](qwen36-27b-autoround-int4-b70/) | 2 | Platform installer, clean-host replay, simplified positive patch index |

## Lab Replays

These are useful to experienced developers restoring a known lab environment.
They are not clean-machine installation instructions.

| Reproduction | Preserved purpose |
| --- | --- |
| [DeepSeek V4 Flash K160, 80 tok/s](deepseek-v4-flash-k160-b70-80tps-20260718/) | Exact closed-lane source history, endpoint, and result gates |
| [Gemma 4 26B A4B Q8](gemma4-26b-a4b-q8-b70/) | Current result-family replay material |
| [Gemma 4 26B A4B Q8, 125 tok/s](gemma4-26b-a4b-q8-b70-125tps-20260701/) | Originating-host command, validity rules, and evidence |
| [Laguna S 2.1 INT4, 125 tok/s](laguna-s-2.1-int4-b70-125tps-20260731/) | Exact originating-host record gate |
| [Qwen3.6 AutoRound INT4 determinism](qwen36-27b-autoround-int4-b70-determinism-20260818/) | Determinism-specific rebuild and replay |
| [Qwen3.6 27B Q8 TP2](qwen36-27b-q8-tp2-asrock-b70/) | Source/patch restore and strict no-speculation gate |
| [Qwen3.8 27B Q4_K_M TP2](qwen38-27b-q4km-tp2-asrock-b70/) | Exact llama.cpp lab replay |
| [Qwen3.8 27B Q8 TP2](qwen38-27b-q8-tp2-asrock-b70/) | Exact single-request llama.cpp lab replay |
| [Qwen3.8 27B Q8 TP2 C2](qwen38-27b-q8-tp2-c2-asrock-b70/) | Concurrency-two extension of the Q8 replay |

## Research, Records, and Archive

| Artifact | Classification | Purpose |
| --- | --- | --- |
| [Qwen3.8 27B AutoRound INT4](qwen38-27b-autoround-int4-b70/) | `research-status` | Active lane with unpublished AOT/cache dependencies and an unresolved promoted identity |
| [Qwen3.8 Flash-Next FP8 TP4 lossless MTP1 + never-routed experts host-placed, 31.93 tok/s](qwen38-flash-next-fp8-tp4-mtp1-placement-b70-32tps-20260906/) | `lab-replay` | Originating-host replay of the fastest quality-preserving Flash-Next line (31.929 tok/s class-balanced, 12/12 outputs identical to the MTP0 line); placement overlay, kernel stage, oneCCL and placement file pinned and hosted; supersedes the 27.05 row; [candidate package](../packages/qwen38-flash-next-fp8-tp4-mtp1-placement-b70-32tps-20260906/) |
| [Qwen3.8 Flash-Next FP8 TP4 lossless MTP1 + never-routed experts host-placed + Triton HC glue, 37.05 tok/s](qwen38-flash-next-fp8-tp4-mtp1-hctriton-b70-37tps-20260907/) | `lab-replay` | Originating-host replay of the fastest Flash-Next line (37.045844 tok/s class-balanced); a new deterministic output authority (the Triton hyper-connection glue rounds at the last bf16 bit) reproduced on five servers with the certified rows' quality profile; overlays, kernel stage, oneCCL and placement file pinned and hosted; the 31.93 row remains the fastest bit-identical line; [candidate package](../packages/qwen38-flash-next-fp8-tp4-mtp1-hctriton-b70-37tps-20260907/) |
| [Qwen3.8 Flash-Next FP8 TP4 lossless MTP1 + never-routed experts host-placed + both reference Triton kernels, 37.83 tok/s](qwen38-flash-next-fp8-tp4-mtp1-qsafused-b70-38tps-20260907/) | `lab-replay` | Originating-host replay of the fastest Flash-Next line (37.825654 tok/s class-balanced); a new output authority whose difference is at depth (exact-2K coincides with the certified stream, exact-4K does not) with the quality profile preserved byte for byte; overlays, kernel stage, oneCCL and placement file pinned and hosted; [candidate package](../packages/qwen38-flash-next-fp8-tp4-mtp1-qsafused-b70-38tps-20260907/) |
| [Qwen3.8 Flash-Next FP8 TP4 lossless MTP1 + exact serial GDN rows in the kernel extension, 46.85 tok/s](qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/) | `lab-replay` | Originating-host replay of the fastest Flash-Next line; same output pins as the 37.83 line | four B70s |
| [Qwen3.8 Flash-Next FP8 TP4 MTP0 + never-routed experts host-placed + both reference Triton kernels + W13-N64 map, 34.50 tok/s](qwen38-flash-next-fp8-tp4-mtp0-w13n64-b70-34tps-20260908/) | `lab-replay` | The fastest non-speculative Flash-Next line (34.495292 tok/s class-balanced, LocalMaxxing `cmts8zca50032ps01e0ddqm18`), which supersedes the 33.797067 MTP0 record by one line of the tuned MoE map with no source change; outputs bit-identical across three servers |
| [Qwen3.8 Flash-Next FP8 TP4 lossless MTP1, 27.05 tok/s](qwen38-flash-next-fp8-tp4-mtp1-lossless-b70-27tps-20260905/) | `lab-replay` | Originating-host replay of the certified lossless MTP1 line (27.048 tok/s class-balanced, 12/12 outputs identical to the MTP0 line); every identity pinned, kernel stage and oneCCL hosted; not a clean-machine installer; [candidate package](../packages/qwen38-flash-next-fp8-tp4-mtp1-lossless-b70-27tps-20260905/) |
| [Qwen3.8 Flash-Next FP8 TP4/MTP3](qwen38-flash-next-fp8-tp4-mtp3-b70/) | `research-status` | Fail-closed model, source, and publicly hosted exact-runtime foundation; [2026-08-31 snapshot](qwen38-flash-next-fp8-tp4-mtp3-b70/EXPERIMENTAL-SNAPSHOT-20260831.md) records the 20.727 tok/s short MTP4 screen and preferred 15.502 tok/s exact-4K MTP3 profile; dependency lock and artifact-only replay remain open |
| [MiniMax M2.7 structured 94 tok/s](minimax-m27-b70-94tps-structured-20260522/) | `record-capsule` | Constrained-task result retained for audit, not general deployment |
| [Gemma 4 26B A4B Q8, 95 tok/s](gemma4-26b-a4b-q8-b70-95tps-20260624/) | `archived` | Superseded record retained for history and patch archaeology |

## Promotion Workflow

To promote a candidate, close every `missing` item in
`guide-catalog.json`, replay the written path from a clean supported OS, retain
the evidence in this repository, and then change the classification. If a
runtime is containerized, the host driver, kernel, device permissions, image
digest, model manifest, smoke test, quality gate, benchmark, and stop/recovery
path still have to be explicit.

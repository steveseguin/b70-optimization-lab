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
| [Qwen3.8 Flash-Next FP8 TP4/MTP3](qwen38-flash-next-fp8-tp4-mtp3-b70/) | `research-status` | Fail-closed model, source, and exact runtime identity foundation; public hosting and artifact-only replay remain open |
| [MiniMax M2.7 structured 94 tok/s](minimax-m27-b70-94tps-structured-20260522/) | `record-capsule` | Constrained-task result retained for audit, not general deployment |
| [Gemma 4 26B A4B Q8, 95 tok/s](gemma4-26b-a4b-q8-b70-95tps-20260624/) | `archived` | Superseded record retained for history and patch archaeology |

## Promotion Workflow

To promote a candidate, close every `missing` item in
`guide-catalog.json`, replay the written path from a clean supported OS, retain
the evidence in this repository, and then change the classification. If a
runtime is containerized, the host driver, kernel, device permissions, image
digest, model manifest, smoke test, quality gate, benchmark, and stop/recovery
path still have to be explicit.

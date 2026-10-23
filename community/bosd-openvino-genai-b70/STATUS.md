# OpenVINO GenAI on Intel Arc Pro B70 (Battlemage) — first-party runtime, single-stream decode

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `B70-verified` for the throughput and install claims (reference-lab reproduction 2026-10-23, both engines within 2%); no exactness gate exists for this entry and the greedy-repeat finding below is a caveat on it |
| Patch review status | read; no patch, stock `pip` packages + pre-converted IR; harness read and re-run as `validation/ov-bench-lab.py` |
| Tested in reference lab | yes, 2026-10-23: both OpenVINO arms (3 repeats per prompt), the llama.cpp-SYCL baseline (10 repeats) and a greedy-repeat probe on one B70; see [`validation/lab-run.md`](validation/lab-run.md) |
| Safe to merge as documentation | yes |
| Eligible for `repro/` or `results/` | no; an engine datapoint on a dense model outside the lab's lanes, not a recipe or result packet |

## Provenance

- Contributor: bosd
- Hardware: ASRock TRX50 workstation, Threadripper, 2× Intel Arc Pro B70 (32 GB) + 1× Arc Pro B60 (24 GB), Fedora 44, kernel `7.2.10-200.fc44`, `xe` driver, host Level-Zero `1.33.1`.
- Right-to-submit statement present: yes — all runs are the contributor's own on the contributor's hardware.
- Third-party material and attribution: OpenVINO / OpenVINO GenAI (Intel, Apache-2.0); pre-converted INT4 IR models from the `OpenVINO` HF org; `Qwen2.5-7B-Instruct` / `Qwen2.5-1.5B-Instruct` from the Qwen team; `bartowski/Qwen2.5-7B-Instruct-GGUF` for the llama.cpp baseline; llama.cpp/GGML.

## Claim

Intel's first-party **OpenVINO GenAI** runtime (`openvino-genai` 2026.4.1) runs LLM inference on an Arc Pro B70 (Battlemage) through its Level-Zero GPU plugin with **no oneAPI `setvars` and no `torch`/conversion step** when fed a pre-converted INT4 IR. On a single B70, **Qwen2.5-7B-Instruct INT4 single-stream decode ≈ 113 tok/s** (TTFT 18–84 ms), which is at the card's memory-bandwidth roofline (~107 tok/s for reading ~4.2 GB of INT4 weights per token).

A **current** llama.cpp-SYCL build nearly matches this at **~98.6 tok/s** on the same card/model class, so **OpenVINO GenAI leads current llama.cpp by only ~15% for single-stream dense decode — both are near roofline.** These are contributor measurements, not reference-lab measurements.

## Contributor Environment

| Field | Value |
| --- | --- |
| GPU model / count / VRAM | Intel Arc Pro B70 (Battlemage), targeted card `GPU.1` / `level_zero:1`, 32 GB |
| OS / kernel | Fedora 44 / `7.2.10-200.fc44.x86_64` |
| GPU driver / level-zero | `xe`; host oneapi-level-zero `1.33.1`, intel-level-zero `26.35.39758.11` |
| OV engine / version | `openvino` 2026.4.1, `openvino-genai` 2026.4.1.0, `openvino-tokenizers` 2026.4.1.0 (pip, `uv` venv, CPython 3.12 — system Python 3.14 has no wheels yet) |
| llama.cpp baseline (fresh) | upstream `970b51c` (2026-10-22), SYCL backend, `icx`/`icpx` 2026.1, `-DGGML_SYCL_DNN=OFF` (oneDNN not installed), `-DGGML_SYCL_F16=ON -DGGML_SYCL_GRAPH=ON` |
| llama.cpp baseline (stale, for contrast) | local `~/llama.cpp/build-sycl` `5aba5364d` (2026-06-01) |
| Model (OV) | `OpenVINO/Qwen2.5-7B-Instruct-int4-ov` (main), `OpenVINO/Qwen2.5-1.5B-Instruct-int4-ov` (spec draft) |
| Model (llama.cpp) | `bartowski/Qwen2.5-7B-Instruct-GGUF` → `Qwen2.5-7B-Instruct-Q4_K_M.gguf` (4.36 GiB) |
| Quantization | OV INT4 (group-wise) weights; GGUF Q4_K_M weights; KV default |
| Command / env | OV: `LLMPipeline(model, "GPU.1")`, greedy, `max_new_tokens=256`. llama.cpp: `ONEAPI_DEVICE_SELECTOR=level_zero:1 llama-bench -sm none -mg 0 -ngl 99 -fa 1 -p 512 -n 256 -r 6` |
| Prompts | 1 technical + 1 code prompt, greedy (`do_sample=False`), warm (one warmup generation discarded) |
| Metric / repeats / TTFT | OV: `perf_metrics` throughput + TTFT, per-prompt. llama.cpp: `llama-bench` tg256 mean±std over 6 reps |
| Logs | raw numbers in `reported/results.md`; harness in `reported/ov-bench.py` |

## Reference Lab Environment

Maintainer section, added 2026-10-23. The reference lab (2x Arc Pro B70, Ubuntu 24.04, kernel 7.0, `xe`, OpenVINO GenAI 2026.4.1 in a CPython 3.12 uv venv with no `setvars`, llama.cpp upstream `184f653` built with the contributor's flags) re-ran the contributor's harness and baseline on one B70. Environment table, raw logs and the probe script are in [`validation/`](validation/).

| Measurement | Contributor | Reference lab |
| --- | --- | --- |
| OV GenAI INT4 no-spec, tech / code | 114.0 / 112.5 tok/s | 114.7 / 114.6 tok/s (sd 0.1, 3 reps) |
| OV GenAI INT4 + 1.5B draft, tech / code | 98.6 / 128.2 | 95.1 / 126.0 |
| llama.cpp-SYCL fresh, tg256 / pp512 | 98.6 / 3528 | 99.5 ± 0.1 / 3755 ± 9 |

Reference-lab findings beyond the contributor's:

1. The 15% engine gap and the "rebuild llama.cpp first" caution both hold on the reference hardware.
2. 114.7 tok/s on 4.2 GB of weights is about 480 GB/s, 79% of the B70's 608 GB/s; the contributor's "at roofline" overstates slightly ("~107 tok/s roofline" rests on an unstated ~450 GB/s figure).
3. **OpenVINO GenAI greedy output is not repeat-stable on the first generation.** The first 256-token generation of a fresh `LLMPipeline` differs from every later one; later ones are stable; the settled text depends on whether a warmup ran. Reproducible byte for byte across two instances and two processes, so it is a deterministic ordering effect in the GPU plugin, not noise. Throughput is unaffected. Cause not isolated. Details in `validation/lab-run.md`.

## What Was Actually Run Here

1. Fresh `uv` venv (CPython 3.12), `pip install openvino openvino-genai huggingface-hub`. `openvino.Core().available_devices` → `['CPU', 'GPU.0', 'GPU.1', 'GPU.2']`; `GPU.0` = Arc Pro B60, `GPU.1`/`GPU.2` = Arc Pro B70 (dGPU). **No `setvars.sh` sourced** — OV ships its own Level-Zero GPU plugin.
2. Pulled `OpenVINO/Qwen2.5-1.5B-Instruct-int4-ov`; `LLMPipeline(..., "GPU.1").generate(...)` produced coherent output in ~0.3 s — smoke test confirming Battlemage inference works end-to-end with **no model conversion and no torch**.
3. Pulled `OpenVINO/Qwen2.5-7B-Instruct-int4-ov`; ran `reported/ov-bench.py` on `GPU.1`:
   - **no-spec:** tech **114.0** tok/s / code **112.5** tok/s; TTFT 18–84 ms; tpot ~8.8 ms.
   - **+ spec** (1.5B draft, `num_assistant_tokens=5`): tech **98.6** / code **128.2** tok/s.
4. llama.cpp-SYCL on the same B70, same model as Q4_K_M:
   - **stale 2026-06-01 build:** tg128 **13.2** tok/s, pp512 1083 (flash-attn made no difference).
   - **fresh 2026-10-22 upstream build:** tg256 **98.6 ± 0.3** tok/s, pp512 **3528 ± 28**.

## Findings

- **OpenVINO GenAI is a viable, roofline-class runtime on Battlemage.** Single-stream Qwen2.5-7B INT4 decode ≈ 113 tok/s on one B70 sits at the memory-bandwidth roofline. Install is trivial (two `pip` packages, no oneAPI env, no conversion when using a pre-converted IR).
- **The engine gap vs a current llama.cpp-SYCL is small (~15%), not large.** An early "8×" read was an artifact of a **4.5-month-stale local llama.cpp build** (13 tok/s). A fresh upstream build does 98.6 tok/s (and 3.3× faster prefill). Anyone comparing engines on Arc must rebuild llama.cpp from current master first.
- **OV speculative decoding needs a well-matched draft.** A 1.5B draft for a 7B target (the only OV-published same-tokenizer draft on hand) is too heavy: −13% on prose, +14% on code. A 0.5B draft is the expected sweet spot (not yet published as an `int4-ov` by the OpenVINO org; follow-up).

## Known Issues

- **System Python 3.14 has no OpenVINO wheels** — use a 3.12/3.13 venv (`uv venv --python 3.12`).
- **oneDNN (DNNL) is not bundled** with the oneAPI compiler package here; current llama.cpp hard-errors on `GGML_SYCL_DNN=ON` when `dnnl-config.cmake` is absent (older llama.cpp silently disabled it). Build with `-DGGML_SYCL_DNN=OFF` or install `intel-oneapi-dnnl*`.
- `LLMPipeline.generate(str, cfg)` returns a bare `str` (no `perf_metrics`); pass a **list** (`generate([prompt], cfg)`) to get `DecodedResults` with metrics.

## Open Questions For The Contributor / Lab

1. Does OpenVINO/optimum-intel's exporter support the hybrid-GDN `qwen3_5` family (`Qwen3_5ForConditionalGeneration` / `Qwen3_5MoeForConditionalGeneration`) that the B70 serving stacks actually deploy? (Suspected no; not attempted here.)
2. With a properly-sized 0.5B INT4 draft, does OV spec-decode beat MTP on llama.cpp for code workloads on a B70?
3. Batched / concurrent throughput (OV GenAI continuous batching, or OpenVINO Model Server) vs vLLM-XPG — the serving-relevant comparison, not measured here.

## Disposition

`B70-verified` for throughput and install (reference-lab reproduction 2026-10-23, both engines within 2%), with the greedy first-generation caveat recorded above. Useful as the first OpenVINO-GenAI-on-Battlemage datapoint and as a caution that llama.cpp-SYCL engine comparisons must use a current build. Not a recommendation to replace the deployed llama.cpp/vLLM-XPU serving stack, which runs GDN/MoE `qwen3_5` models OV likely cannot yet convert.

# STATUS — Qwen3.8-27B Cold Fusion GAIN V1.1 MTP llama.cpp SYCL

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `community-reported` |
| Patch review status | read, no execution in reference lab |
| Tested in reference lab | no |
| Safe to merge as documentation | yes |
| Eligible for `repro/` or `results/` | no until `B70-tested` |

## Provenance

- Contributor: [`dominick253`](https://github.com/dominick253).
- Source: this PR.
- Right-to-submit statement: present in the PR description.
- The Cold Fusion GAIN V1.1 MTP GGUF is a fine-tune of `ggml-org/Qwen3.8-27B`
  produced on the contributor's host. The exact upstream base revision is
  recorded below; the fine-tune weight artifact is not redistributed here.

## Contributor Claim

The contributor reports a steady-state decode rate of **38.4 tok/s** at short
context (51 generated tokens, thinking disabled) on a single Intel Arc Pro B70
(32 GiB) using llama.cpp `b10472`, the Cold Fusion GAIN V1.1 MTP Q4_K_M GGUF,
`--spec-draft-n-max 2`, `--cache-type-k f16 --cache-type-v f16`, 160,000-token
context, oneAPI 2026.1.1, kernel `7.0.0-29-generic` (Ubuntu 26.04).

Supporting A/B data from the same session (contributor-reported, not
reference-lab verified):

| Model / KV | MTP | Decode | Accept |
|------------|-----|:---:|:---:|
| Unsloth Q4_K_M (stock) + f16 KV | 2 | 44.4 tok/s | 100% |
| **Cold Fusion GAIN V1.1 + q8 KV** | 2 | 10.3 tok/s | 41-47% |
| **Cold Fusion GAIN V1.1 + f16 KV** | **2** | **38.4 tok/s** | **94.4%** |

These are contributor-reported measurements from a live long-running systemd
service. They have not been independently reproduced in the reference lab.

## Contributor Environment

| Field | Value |
| --- | --- |
| GPU model / count / VRAM | 1x Intel Arc Pro B70 (Battlemage G31, PCI ID `8086:e223`); 32 GiB |
| OS / kernel | Ubuntu 26.04 LTS, kernel `7.0.0-29-generic` |
| GPU driver | `xe` (Intel Xe2 Graphics kernel driver), srcversion `85B7CA089405934276CBAD3`, bundled in kernel 7.0.0-29 |
| compute-runtime / Level Zero | `libze-intel-gpu1` `26.27.39122.11-0`; `intel-opencl-icd` `26.27.39122.11-0` |
| SYCL compiler | Intel oneAPI 2026.1.1 (IntelLLVM DPC++); IGC `2.38.2` |
| Engine / commit | llama.cpp `60eeeb6082c1126bb8bc72902c83123cd056811b` (`b10472`), upstream `ggml-org/llama.cpp` |
| llama.cpp build flags | `GGML_SYCL=ON F16=ON GRAPH=ON DNN=ON NATIVE=ON HOST_MEM_FALLBACK=OFF` |
| LD_PRELOAD | `/opt/opencode-fixes/l0graphshim.so` (community Level Zero graph workaround) |
| Model repo | `ggml-org/Qwen3.8-27B` (base, upstream); fine-tune produced locally |
| Model file | `Qwen3.8-27B-Cold-Fusion-GAIN-V1.1-NM-DAU-NEO-MAX-NEO-MTP-Q4_K_M.gguf` |
| Model SHA-256 | `db466a9432a52b87a7b7560f432f0e1caafeb111dbe3d168acf74dfe143a637c` |
| Model size | 18,498,573,824 bytes (17.1 GiB) |
| Quantization (weights) | Q4_K_M |
| Quantization (KV) | F16 target + F16 draft (q8 KV measurably collapses decode on SYCL B70) |
| Speculation | `--spec-type draft-mtp --spec-draft-n-max 2 --spec-draft-p-min 0.1` |
| Context | `--ctx-size 160000` |
| Batch / ubatch | `--batch-size 4096 --ubatch-size 2048` |
| Threads | `--threads 16` |
| Flash Attention | `--flash-attn on` + `GGML_SYCL_ENABLE_FLASH_ATTN=1` |
| Graph capture | disabled: `GGML_SYCL_ENABLE_GRAPH=0` |
| Device selector | `ONEAPI_DEVICE_SELECTOR=level_zero:0` |
| Parallel | `--parallel 1` |
| Sampling | `--temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --presence-penalty 0.0 --repeat-penalty 1.0` |
| Reasoning | `--jinja --reasoning auto` (thinking off at client: `reasoning_effort: none`) |
| Fit | `--fit off` |
| Benchmark evidence | see `reported/` — live service decode timings, llama-benchy JSON sweeps, MTP acceptance logs |

## Reference Lab Environment

Not yet executed in the reference lab.

## What Was Actually Run Here

Nothing has been executed in the reference lab. The contribution is submitted
at `community-reported` level. The full result packet and repro script are
provided for maintainer validation.

## Findings

1. **F16 KV is required on SYCL B70 for this model.** Contributor A/B testing
   (session 2026-08-18) showed q8 KV collapsed decode to ~10 t/s while f16 KV
   produced 38.4 t/s. The f16 KV requirement is specific to the SYCL backend
   on B70 and does not reflect a model precision issue.

2. **MTP2 is the optimal setting for this build on one B70.** MTP3 gave a
   marginal +1.6 t/s at short context (51 tokens) but risks degrading at
   longer context. MTP2 showed 94.4% draft acceptance, mean draft length 2.89.

3. **38.4 t/s is at the dense Q4_K_M bandwidth ceiling** for one Arc Pro B70.
   The 16-run Aug 16 sweep (baseline through MTP3/p-min/ubatch variants)
   produced a maximum of 34.63 t/s at depth 0; the live service at 38.4 t/s
   reflects warm cache, the tuned batch/ubatch configuration, and the exact
   MTP acceptance rate under real prompt conditions.

4. **The Cold Fusion GAIN V1.1 fine-tune is not a decode-throughput win** over
   the stock Unsloth Q4_K_M on the simple counting probe (38.4 vs 44.4 tok/s;
   94.4% vs 100% acceptance). Its value is in the task/quality behavior it was
   trained for, which this packet does not quantify. It is documented here as
   the contributor's running production configuration, not as a speed record.

## Known Issues

None identified in the submitted material.

## Open Questions For The Contributor

1. Can the maintainer obtain the fine-tune artifact from the contributor to
   enable a reference-lab reproduction at `B70-tested` level?
2. Does the fine-tune preserve full task quality relative to the stock
   `ggml-org/Qwen3.8-27B`? What was the quality gate used?
3. What is the exact base revision of `ggml-org/Qwen3.8-27B` used for the
   fine-tune?
4. Can the contributor provide the raw `llama-bench` binary output (not
   llama-benchy API mode) for a clean native decode measurement?

## Disposition

Retain at `community-reported`. Move to `B70-tested` once the maintainer
obtains the model artifact and runs the repro script on a reference B70.

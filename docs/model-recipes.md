# Model Recipes

This is the historical community-facing recipe index. The repository now
distinguishes clean-host starter guides from expert candidates, lab replays,
records, research, and archives. Consult the machine-readable
[`repro/guide-catalog.json`](../repro/guide-catalog.json) and
[`reproduction-guide certification standard`](reproduction-guide-certification.md)
before treating any entry as an installer. No current entry is starter-certified.

## How To Read A Recipe

Every complete recipe should include:

- Hardware and OS assumptions.
- Exact model and quantization.
- Driver/runtime/compiler versions.
- Source commits and patches.
- Download path and cache layout.
- Build commands.
- Quality checks.
- Benchmark shape and speed.
- Serving command, if applicable.
- Known failures and workarounds.

Do not compare two results unless their model, quantization, prompt length, output length, context length, batch/concurrency, and quality gate are clear.

## Recipe Index

| Recipe | Status | What It Is For |
| --- | --- | --- |
| `../repro/qwen36-27b-q8-tp2-asrock-b70/` | `lab-replay` | Complete mndodd-based source patch, bounded build/server launchers, pinned Q8_0 model, fixed cold suite, and exact-output gates for `35.699 tok/s` conventional on two ASRock B70s with no speculation. Platform installation, model acquisition, and clean-host replay remain open. |
| `../repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/` | `candidate-portable-repro` | Four-B70 Muse UD-Q8_K_XL plus pretrained BF16 DFlash: public-base source restore, fixed-N16 oneDNN WOQ, ARGMAX, raw evidence, two canonical century runs, frozen cold suite, and explicit Q8/quality limits. |
| `../repro/laguna-s-2.1-int4-b70-102tps-20260726/` | `candidate-portable-repro` | Portable sealed-evidence audit, exact source bundles, model-at-revision restore and manifest, native loader verification, and one-cold-suite replay for the four-B70 Laguna row. |
| `../repro/deepseek-v4-flash-k160-b70-80tps-20260718/` | `lab-replay` | Exact source bundles, fail-closed launcher, validity gates, and evidence for the 80.820 tok/s target-verified DSpark7 result on four B70s. |
| `../results/gemma4-26b-a4b-q8-b70/` | Result packet | Gemma 4 26B A4B Q8/INT8 one-B70 speed frontier, long-context service lane, older baselines, failed paths, validity gates, vLLM comparison lanes, and LocalMaxxing evidence. |
| `../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/` | `lab-replay` | Originating-host Gemma 4 26B A4B Q8 target material for the `122.160 tok/s` class-balanced cold-suite result on one B70 (`123.727` all-prompt; `124.977` historical compatibility); not a clean-machine installer. |
| `../repro/gemma4-26b-a4b-q8-b70-95tps-20260624/` | `archived` | Superseded Gemma 4 26B A4B Q8 target material retained for history. |
| `../repro/minimax-m27-b70-110tps-ubuntu24-20260523/` | `candidate-portable-repro` | The closest historical Ubuntu deployment candidate, but mutable package/toolchain dependencies and its current clean-host replay remain open. |
| `../repro/minimax-m27-b70-89tps-20260520/` | `candidate-portable-repro` | Older strict quality-passed MiniMax M2.7 INT4 lane retained for expert optimization comparisons. |
| `../results/qwen36-35b-quark-int8-b70/` | Closed reference packet | Qwen3.6 35B A3B Quark W8A8 INT8 on 2x/4x B70. Best strict 4x baseline, invalid fast lanes, reproduction commands, and carryover notes. |
| `../experiments/minimax_xpu_kv_offload/` | Experimental | Session-cache c2/c4/c8, TurboQuant, and CPU-paged attention research. Use for review and experiments, not as the production recipe. |
| `../experiments/gemma4-12b-int4-autoround-vllm/` | Production slot plus research profiles | Gemma 4 12B IT INT4 AutoRound image+text endpoint on vLLM/XPU. Current production is c8 with 32K context and 8 active generations; c10/c12/c16/c64 are documented research or rejected profiles. |

The word "current" in older recipe folders means "current at the time that
recipe was promoted." Use [model-effort-index.md](model-effort-index.md) and
[../results/README.md](../results/README.md) for the live cross-model view.

## MiniMax M2.7 INT4 AutoRound

This section is an **expert candidate**, not a starter workflow. Its scripts
perform system changes with `sudo`; review them before use. The package sources
available in 2026 have not yet been replayed on a clean host with immutable
driver-package locks.

After that review, the historical sequence starts with:

```bash
cd repro/minimax-m27-b70-110tps-ubuntu24-20260523
sudo bash scripts/00-install-system-deps.sh
sudo reboot
```

After reboot:

```bash
sudo bash scripts/01-prepare-storage.sh
bash scripts/02-download-model.sh
bash scripts/03-build-stack.sh
bash scripts/04-verify-runtime.sh
bash scripts/05-run-quality-and-benchmark.sh
bash scripts/06-serve-openai-compatible.sh
```

Then in another terminal:

```bash
bash scripts/07-smoke-test-endpoint.sh
```

See [the full deployment guide](b70-minimax-ubuntu24-deployment.md) for explanation and troubleshooting.

## Session-Cache And Long-Context Experiments

For RAM-backed session-cache experiments, start with:

```bash
cd experiments/minimax_xpu_kv_offload
less REPRODUCE.md
```

Current status:

- c1 is the production 32K endpoint.
- c2 is the current known-good session-cache profile for two parked 32K-window
  conversations.
- c4/c8 have useful ladder results but are not production-ready.
- TurboQuant has a tracked XPU workspace fallback patch, but remains slower and
  experimental.

See [Current Reproducibility Map](current-reproducibility-map.md) for the full
artifact map.

## Gemma 4 12B INT4 AutoRound

The current image+text research profile is:

```bash
cd /home/steve/llm-optimizations
scripts/switch-vllm-model-slot.sh switch gemma4-12b-it-int4-autoround-c8
```

It serves `Intel/gemma-4-12B-it-int4-AutoRound` through the same no-auth
OpenAI-compatible LAN endpoint on `0.0.0.0:8000`, with 32K context, 8 active
generations, prefix caching, and XPU graph capture. It needs the local vLLM
`gemma4_unified` backport captured in
`patches/vllm-gemma4-unified-backport-b70-20260607.patch`.

See [the Gemma 4 experiment guide](../experiments/gemma4-12b-int4-autoround-vllm/README.md)
for the exact slot profiles, smoke tests, known bad multimedia-limit setting,
2K/512 concurrency results, c10/c12 full-32K boundary tests, and prefix-cache
results for shared-prefix plus unique-tail prompts.

## Gemma 4 26B A4B Q8 / INT8

The promoted strict command and validation packet is
[`../results/gemma4-26b-a4b-q8-b70/reproduce.md`](../results/gemma4-26b-a4b-q8-b70/reproduce.md).
The standalone
[`../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/`](../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md)
folder packages the 125 tok/s strict cold-suite recipe, 32K context
settings, validity rules, and links to the promoted evidence.
The older
[`../repro/gemma4-26b-a4b-q8-b70-95tps-20260624/`](../repro/gemma4-26b-a4b-q8-b70-95tps-20260624/README.md)
folder packages the older superseded 95 tok/s llama.cpp patch, Q8 target,
Q4_0 MTP draft preparation, command line, and LocalMaxxing artifacts.

The deeper lab packet is
[`../results/gemma4-26b-a4b-q8-b70/`](../results/gemma4-26b-a4b-q8-b70/README.md).
This lane intentionally avoids tensor-parallel splitting at first: run one
complete Gemma 4 26B A4B replica per B70 and use four replicas for parallel
research. Current headline for the realistic cold-suite lane is
`122.16035656735696 tok/s`, the median of per-input-class medians under
conventional 99-interval accounting. The secondary all-prompt median is
`123.72736943965285`; the published legacy 100-event value is
`124.97714084813418 tok/s`. The exact lane is:
llama.cpp `c926ad098`, UD-Q8_K_XL target/verifier, Q4_0 MTP draft,
reordered-Q8 VDR2, selected-down fused weighted-sum, bulk sampled-ID verifier
host read, `FLASH_ATTN=on`, `CTX_SIZE=32768`, VMM on, final post-norm
residual fusion, `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`,
`cached_tokens=0` on every fixed-suite prompt, and no cache/history reuse.
Older `103-176 tok/s` filled-long rows are
diagnostic/pre-final-gate artifacts unless revalidated by the fixed realistic
suite.

Start with llama.cpp SYCL and the Unsloth `UD-Q8_K_XL` GGUF:

```bash
scripts/build-llama-cpp-sycl-b70.sh
scripts/download-gemma4-26b-q8-gguf.sh
GPU_INDEX=0 PORT=18260 scripts/run-gemma4-26b-llamacpp-replica.sh
```

For the current standalone 125 tok/s path, use the repro wrapper:

```bash
GPU_INDEX=0 PORT=19350 bash repro/gemma4-26b-a4b-q8-b70-125tps-20260701/run.sh
```

The older 95 tok/s folder remains as an archival artifact, not the current copy
path.

The vLLM comparison lane should use `google/gemma-4-26B-A4B-it` with
`--quantization int8_per_channel_weight_only`, one DP=1 process per GPU. Do not
promote INT4 AutoRound results as this lane's default quality target.

## Future Recipe Slots

These are useful community targets to add as separate repro folders:

- Single active model-slot profiles for MiniMax, Qwen text, and Qwen-VL
  serving. See [Single Model Slot Switching](model-slot-switching.md).
- Gemma 4 12B INT4 AutoRound full fresh-install repro folder once the
  `gemma4_unified` backport is either upstream or packaged as a smaller patch.
- Gemma 4 26B A4B Q8/INT8 long-running endpoint profile that combines the
  current short-decode recipe with the validated service/prompt-processing
  gate without regressing the 125 tok/s short record.
- Qwen3.6 27B Q4_0 GGUF on llama.cpp/SYCL.
- Qwen3.6 27B FP8 on vLLM/XPU.
- Qwen3-VL 30B-A3B FP8 on vLLM/XPU for image+text requests.
- MiniMax M2.7 GGUF/UD-IQ4_XS on llama.cpp RPC/SYCL.
- Smaller single-card B70 recipes for 7B, 8B, 14B, and 27B models.
- Multi-user/concurrency recipes that report throughput and latency together.

For model-lane status and closed-out results, check the
[Model Effort Index](model-effort-index.md) before starting a new folder.

## Suggested Recipe Folder Template

Use a name that includes model, hardware, headline result, OS/date, and avoid spaces:

```text
repro/<model>-<hardware>-<headline>-<os>-<yyyymmdd>/
  README.md
  configs/
  scripts/
  patches/
  results/
  notes/
```

For example:

```text
repro/minimax-m27-b70-110tps-ubuntu24-20260523/
```

## Publishing Results

For a result to be useful to other people, include:

- Raw benchmark JSON/logs or a summarized JSON artifact.
- A copy of the exact environment variables.
- Source commits and patch files.
- A quality statement. "It ran fast" is not enough.
- Whether the endpoint was served through vLLM, llama.cpp, or another engine.
- Whether throughput is output-token throughput or total-token throughput.

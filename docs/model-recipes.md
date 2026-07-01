# Model Recipes

This page is the B70-facing index for reproducible model deployments and result
packets. Each recipe should make clear what it proves: installation, quality,
benchmark speed, serving, or all of the above.

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

Do not compare two results unless their model, quantization, prompt length,
output length, context length, batch/concurrency, and quality gate are clear.

## Current Recipes

| Recipe | Status | What It Is For |
| --- | --- | --- |
| `../repro/gemma4-26b-a4b-q8-b70-current-20260701/` | Current top-score identity | Gemma 4 26B A4B Q8 target with Q4_0 MTP draft, fixed cold realistic suite, and the `124.977 tok/s` record identity. The runner needs the full Gemma 26 harness imported or `HARNESS_ROOT` pointed at a checkout that has it. |
| `../repro/minimax-m27-b70-94tps-structured-20260522/` | Structured speed lane | MiniMax M2.7 INT4 constrained simple-HTML lane at `94.406 tok/s` effective accepted output. This is not unconstrained website generation. |
| `../repro/minimax-m27-b70-110tps-ubuntu24-20260523/` | Deployable baseline | Fresh Ubuntu 24.04 setup for 4x B70, MiniMax M2.7 INT4 AutoRound, vLLM OpenAI-compatible endpoint on `0.0.0.0:8000`. |
| `../repro/minimax-m27-b70-89tps-20260520/` | Strict speed baseline | Older strict quality-passed MiniMax M2.7 INT4 lane with higher output-token throughput. Useful for optimization comparisons. |
| `../results/qwen36-35b-quark-int8-b70/` | Closed reference packet | Qwen3.6 35B A3B Quark W8A8 INT8 on 2x/4x B70. Best strict 4x baseline, invalid fast lanes, reproduction commands, and carryover notes. |
| `../experiments/minimax_xpu_kv_offload/` | Experimental | Session-cache c2/c4/c8, TurboQuant, and CPU-paged attention research. Use for review and experiments, not as the production recipe. |
| `../experiments/gemma4-12b-int4-autoround-vllm/` | Production slot plus research profiles | Gemma 4 12B IT INT4 AutoRound image+text endpoint on vLLM/XPU. Current production is c8 with 32K context and 8 active generations; c10/c12/c16/c64 are documented research or rejected profiles. |
| `../experiments/minimax-m27-reap-autoround-vllm/` | Research/result lane | MiniMax M2.7 REAP AutoRound W4A16. Best approved archived row is `89.499 tok/s`, but current live-source quality-valid reproduction is lower; keep the caveat attached. |

## MiniMax M2.7 INT4 AutoRound

Start with:

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

For the constrained structured-output speed lane, use:

```bash
cd /home/steve/llm-optimizations
source repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh
timeout 35m /home/steve/.venvs/vllm-xpu/bin/python \
  scripts/run-minimax-structured-skeleton-quality.py \
  --mode graph --warmup-runs 1 --repeat 30 --retry-until-pass 5 \
  --out /home/steve/bench-results/minimax-structured-regex2/result.json \
  --sites-dir /home/steve/bench-results/minimax-structured-regex2/sites \
  --max-tokens 96 --max-model-len 4096 --max-num-batched-tokens 512
```

See
[`../repro/minimax-m27-b70-94tps-structured-20260522/`](../repro/minimax-m27-b70-94tps-structured-20260522/README.md)
for the caveats and LocalMaxxing evidence.

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

The current top-score identity is:

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`, verified by the Q8 target;
- engine: llama.cpp SYCL/Level Zero on one B70;
- context: `32768`;
- metric: fixed cold realistic suite, median generated tokens 1-100 after TTFT;
- score: `124.977 tok/s`, LocalMaxxing `cmr1u77na01k2ld01kalwzs1e`.

Start with
[`../repro/gemma4-26b-a4b-q8-b70-current-20260701/`](../repro/gemma4-26b-a4b-q8-b70-current-20260701/README.md).
This branch records the identity and wrapper; if the full Gemma 26 harness has
not been imported into the current checkout, run with
`HARNESS_ROOT=/home/steve/qwen36-results-main` or import the harness from
`main`.

## Qwen3.6 35B Quark INT8

The Qwen3.6 35B lane is closed for now. The best strict 4x B70 result is
`93.5505 tok/s` corrected output on the PIECEWISE forced-comm graph identity.
Use
[`../results/qwen36-35b-quark-int8-b70/reproduce.md`](../results/qwen36-35b-quark-int8-b70/reproduce.md)
and read
[`../results/qwen36-35b-quark-int8-b70/validity-gates.md`](../results/qwen36-35b-quark-int8-b70/validity-gates.md)
before comparing or promoting any new Qwen run.

## Future Recipe Slots

These are useful community targets to add as separate repro folders:

- Single active model-slot profiles for MiniMax, Qwen text, and Qwen-VL
  serving. See [Single Model Slot Switching](model-slot-switching.md).
- Gemma 4 12B INT4 AutoRound full fresh-install repro folder once the
  `gemma4_unified` backport is either upstream or packaged as a smaller patch.
- Gemma 4 26B A4B Q8 standalone repro folder with the full harness imported
  into this branch rather than referenced through `HARNESS_ROOT`.
- Qwen3.6 27B Q4_0 GGUF on llama.cpp/SYCL.
- Qwen3.6 27B FP8 on vLLM/XPU.
- Qwen3-VL 30B-A3B FP8 on vLLM/XPU for image+text requests.
- MiniMax M2.7 GGUF/UD-IQ4_XS on llama.cpp RPC/SYCL.
- Smaller single-card B70 recipes for 7B, 8B, 14B, and 27B models.
- Multi-user/concurrency recipes that report throughput and latency together.

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

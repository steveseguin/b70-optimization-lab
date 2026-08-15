# Unofficial Intel XPU Optimization Lab

Community setup guides, benchmark recipes, troubleshooting notes, and patches
for local AI work on Intel XPUs. This is not a single-model repo. It is a
working lab notebook and reproducibility collection for multiple model lanes
that we revisit as new runtime, compiler, and kernel ideas appear.

This is experimental research, not a supported product. Commands, patches,
and benchmark observations are provided under the repository [LICENSE](LICENSE)
and the risks described in [DISCLAIMER.md](DISCLAIMER.md); review and use them
at your own risk.

## Who This Is For

- Local AI users who want reproducible Intel Arc/B-series commands, patches and
  benchmark recipes.
- Anyone deciding whether Intel Arc/B-series hardware is worth it for local
  inference, and wanting to see the state of support.
- Optimization agents and contributors who need a map of current work,
  archived lessons, and validity rules.
- Upstream vLLM, llama.cpp, oneAPI, SYCL, and Intel/XPU developers looking for
  concrete repros and failure signatures.

## Start Here

| Need | Entry Point |
| --- | --- |
| Understand the repo structure | [Docs index](docs/README.md) |
| See every active, paused, and archived model lane | [Model effort index](docs/model-effort-index.md) |
| Reproduce promoted results | [Results index](results/README.md) and [model recipes](docs/model-recipes.md) |
| Start optimizing a new model | [Model optimization guide](docs/model-optimization-guide.md) |
| Plan PCIe slots, risers, or external GPUs | [PCIe topology and local-LLM inference](docs/pcie-topology-and-llm-inference.md) |
| Compare expected model performance | [Performance scoreboard](results/scoreboard.md) |
| Contribute a result, patch, or correction | [Contribution guide](CONTRIBUTING.md) and [verification policy](docs/contribution-verification.md) |
| Review or validate incoming work | [Manager playbook](MANAGER.md) |
| Reuse the best research prompts/workflows | [Research workflow playbook](docs/research-workflow-playbook.md) |
| Find the current host/service map | [Current reproducibility map](docs/current-reproducibility-map.md) |
| Submit or audit LocalMaxxing records | [LocalMaxxing submissions](docs/localmaxxing.md) |
| Handle local ops, secrets, sudo, and cross-agent delegation | [Local ops](docs/local-ops.md) |
| Review Intel-facing issues and asks | [Feedback for Intel](docs/feedback-for-intel.md) |

## How The Repo Is Organized

The repo is organized around model lanes, not one-off leaderboard
rows. A serious lane should leave behind:

- `results/<model>-<quant>-<hardware>/`: promoted or closed-out result packet,
  validity gates, best commands, invalid fast lanes, and lessons.
- `repro/<model>-.../`: copy-ready runnable recipe for a promoted result.
- `experiments/<model>-.../`: active research lanes that are not production
  recipes yet.
- `notes/`: chronological lab notebook entries, including negative results and
  postmortems.
- `patches/`: patch snapshots and source/config deltas, including failed
  experiments worth preserving.
- `data/`: compact structured benchmark records, payloads, responses, and logs.
- `scripts/`: reusable harnesses, analyzers, launchers, and submission helpers.
- `community/<contributor>-...`: runnable work contributed from outside the
  reference lab, with explicit evidence status and validation history.
- `community/field-reports/`: unverified measurements and observations from
  community systems, kept separate from recipes, patches, validation assets,
  and promoted results. See [`community/README.md`](community/README.md).

The point is to make model switching cheap. Gemma, Qwen, MiniMax, and future
lanes should all share validation discipline, result-packet shape, and reusable
kernel/runtime lessons without dragging stale generated builds or huge artifacts
forward.

## Representative Promoted Results

[`CURRENT.md`](CURRENT.md) alone owns the live service and active research
state. These are evidence-backed examples; the broader expected-performance
view is the [performance index](results/scoreboard.md).

These are entry points, not the whole repo:

| Lane | Status | Best Current Pointer |
| --- | --- | --- |
| **Muse-Glimmer-30B UD-Q8_K_XL on 4x B70** | Closed/banked no-training Q8/WOQ record: fixed-N16 oneDNN WOQ plus pretrained BF16 DFlash and distributed ARGMAX. Two canonical full-256 means **`100.088`** and **`100.649 tok/s`**; frozen 15-prompt cold conventional first-100 median **`161.900 tok/s`**, p10 `108.574`, all cache-zero. Target-verified, not BF16/lossless or universally token-exact; LocalMaxxing `cmss8515c00n0ms01n3begqgg` | [result packet](results/muse-glimmer-30b-q8-woq-b70/README.md), [standalone repro](repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/README.md), [source snapshots](patches/muse-glimmer-30b-b70/README.md) |
| **Poolside Laguna S 2.1 INT4 on 4x B70** | Exact target-verified DFlash depth 11 on the audited width-12 Breakable PIECEWISE graph, with segmented inline draft attention and a decode-only 128-GRF INT4 kernel: **`121.290561 tok/s`** conventional and **`122.515718 tok/s`** historical compatibility. Two independent cold suites passed 13/13 exact with all `cached_tokens=0`; LocalMaxxing `cms905x22003spm01pwyvp3c9` | [qualified result](results/laguna-s-2.1-int4-b70/README.md), [record evidence](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-decode-grf128-confirmed-record.md), [source snapshots](patches/laguna-s-2.1-xpu-b70/README.md), [older standalone repro](repro/laguna-s-2.1-int4-b70-102tps-20260726/README.md) |
| DeepSeek V4 Flash experimental uniform-K160 on 4x B70 | Paused/closed frontier; target-verified DSpark7 record **`80.820 tok/s`** high and `78.287 tok/s` three-suite median-of-medians; exact source bundles and fail-closed launcher preserved; LocalMaxxing `cmrquta9905w3lg013m5vxoqx` | [result packet](results/deepseek-v4-flash-k160-b70/README.md), [standalone repro](repro/deepseek-v4-flash-k160-b70-80tps-20260718/README.md), [closeout](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-21-deepseek-v4-flash-frontier-closeout.md) |
| Qwen3.6 27B INT4 AutoRound on 1-2x B70 | Closed reference lane; strict fresh-response TP2 record **`95.385 tok/s`**; pinned public oneCCL, captured MTP draft, graph-safe FlashAttention full target graph, and exact ReplaySSM pending/direct-output transaction fusions; exact cases, repeat128, baseline parity, 1K needle, unique cold prompts, and `cached_tokens=0` all passed; both swapped four-GPU crossover assignments favored the candidate; LocalMaxxing `cmrh35ct50092mj01h7jgydqj`; current service ladder passes exact cold retrieval through `17706` actual prompt tokens at `MAX_MODEL_LEN=32768`, but the forced chunk-decode record path is short-context-only | [current record packet](results/qwen36-27b-autoround-int4-b70/tp2-fp16-fullgraph-transaction-20260711.json), [handoff](results/qwen36-27b-autoround-int4-b70/HANDOFF.md), [record note](experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-11-fullgraph-transaction-record.md), [service ladder](experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-long-context-ladder-baseline.md), [general repro](repro/qwen36-27b-autoround-int4-b70/README.md) |
| Qwen3.6 27B GGUF Q8_0 target-only on 2x ASRock B70 | Active no-speculation TP2 optimization; clean-source record: **`36.604128 tok/s` conventional** (`36.973866` historical helper), full-512 after-TTFT `36.533899`; 12/12 512-token outputs exact and all cache counts zero; two-chain DP4A ILP plus recurrent/attention/collective fusions; `+17.981%` over the matched mndodd fork baseline | [handoff](results/qwen36-27b-q8-tp2-asrock-b70/HANDOFF.md), [result packet](results/qwen36-27b-q8-tp2-asrock-b70/README.md), [standalone repro](repro/qwen36-27b-q8-tp2-asrock-b70/README.md), [source patch](patches/qwen36-27b-q8-tp2-asrock-b70/README.md), [mndodd contributor packet](community/mndodd-qwen36-27b-llamacpp-sycl/README.md) |
| Gemma 4 26B A4B Q8 / INT8 on 1x B70 | Production-servable backend plus current strict fresh-response speed frontier; noisy near-record support band | [handoff](results/gemma4-26b-a4b-q8-b70/HANDOFF.md), [production service](results/gemma4-26b-a4b-q8-b70/production-service.md), [125 tok/s repro](repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md) |
| Gemma 4 26B long-context/prompt-processing service lane | Separate from short-decode record; approved LocalMaxxing service entry `cmr47ivql0045nv011pfdjlaa`; service gates must not regress short decode | [Gemma result packet](results/gemma4-26b-a4b-q8-b70/README.md), [service gate script](repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh) |
| Rapid one-B70 model snapshots | Quick strict/fresh decode baselines across practical GGUF/vLLM candidates; current promoted rows include Qwen3 30B-A3B `107.484 tok/s`, Qwen3-Coder 30B-A3B `108.117 tok/s`, Phi-4 mini Q4 `96.548 tok/s`, GLM-4.7-Flash `40.769 tok/s`, and Mistral Small 3.2 24B `27.297 tok/s` | [rapid result ledger](results/rapid-model-snapshots-b70/README.md), [rapid experiment notes](experiments/rapid-model-snapshots-b70/README.md) |
| Qwen3.6 35B A3B Quark W8A8 INT8 on B70 | Closed reference packet for now; preserve lessons for future return | [Qwen result packet](results/qwen36-35b-quark-int8-b70/README.md), [research map](docs/qwen36-research-map.md) |
| MiniMax M2.7 INT4 AutoRound on 4x B70 | Deployable baseline plus older strict-speed and source-fusion research leads | [result packet](results/minimax-m27-int4-autoround-b70/README.md), [Ubuntu 24 deploy repro](repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md), [production service notes](docs/minimax-production-c1-service.md) |
| Gemma 4 12B IT INT4 AutoRound | Current model-slot production profile and multimodal service lane | [experiment packet](experiments/gemma4-12b-int4-autoround-vllm/README.md), [slot switching](docs/model-slot-switching.md) |

For the full queue and archive, use [docs/model-effort-index.md](docs/model-effort-index.md).

### Qwen3.6 27B Model Board

Last audited **2026-08-15**. These rows share a model family, not a quality,
runtime, or benchmark class. “Target only” means no speculative draft; MTP and
DFlash rows retain the declared target as verifier. The first number is the
repository's historical published 100-event/99-interval rate where that
harness was used; the parenthesized value is conventional 99-interval
accounting from the same timestamps. Relative A/B gains are unchanged.

| Target and route | Hardware | Best captured decode result | Evidence boundary / pointer |
| --- | --- | ---: | --- |
| AutoRound INT4 W4A16, vLLM MTP3 | 2x B70, TP2 | **95.384868** (`94.431019` conventional) | Historical strict fixed-suite record; target-verified, cache-zero, full quality gates; [packet](results/qwen36-27b-autoround-int4-b70/tp2-fp16-fullgraph-transaction-20260711.json) |
| AutoRound INT4 W4A16, vLLM ReplaySSM MTP3 | 1x B70 | **68.236263** (`67.553901` conventional) | Valid quality-gated historical high; July 11 isolated reconfirmation was `65.4-66.7 tok/s`, so do not treat the high as every-run expectation; [TP1 attribution packet](results/qwen36-27b-autoround-int4-b70/tp1-draftgraph-attribution-reconfirm-20260711.json) |
| GGUF Q4_0, DFlash5 | 1x B70 | **47.818818** (`47.340630` conventional) | Strict fixed-suite speculative record; unchanged Q4_0 target verifies accepted tokens; [closure](notes/2026-07-13-qwen27-dflash-sycl-closure.md) |
| GGUF Q4_K_M, intrinsic MTP2 | 1x B70 | **38.112 tok/s** | One fixed greedy 128-token request, visible bytes matched its 25.307 tok/s target-only control; not token-exact and not a fixed-suite median; [community validation](community/dominick253-qwen36-27b-llamacpp-sycl/validation/2026-08-08-reference-lab-validation.md) |
| GGUF UD-Q4_K_XL, intrinsic MTP7 with `p_min=0.65` | 1x B70 | **31.480049** (`31.165249` conventional) | Best valid p-min support row; cache-zero fixed suite; [Q4 packet](results/qwen36-27b-mtp-gguf-q4-b70/README.md) |
| GGUF Q4_0, target only | 1x B70 | **25.937011** (`25.677641` conventional) | Strict cold-suite target-only control from the closed DFlash campaign; [timeline evidence](experiments/qwen27-dflash-sycl-b70/notes/2026-07-12-cycle-timeline-tooling.md) |
| GGUF Q8_0, mndodd base plus lab exact fusions, target only | 2x ASRock B70, TP2 | **36.973866** (**36.604128** conventional) | Current clean-source record; 12/12 cold 512-token output hashes exact and cache zero; full-512 after-TTFT `36.533899`; `+17.981%` over matched fork baseline; [result packet](results/qwen36-27b-q8-tp2-asrock-b70/README.md) |
| GGUF Q8_0, mndodd fork baseline, target only | 2x ASRock B70, TP2 | **31.338765** (**31.025377** conventional) | Matched contributor-fork baseline; 12/12 complete hashes match the upstream-derived control, cache zero; [community packet](community/mndodd-qwen36-27b-llamacpp-sycl/README.md) |
| GGUF Q8_0, mndodd fork, target only | 1x ASRock B70 | **17.955800** (**17.776242** conventional) | Matched raw-completions fixed suite; quality-cleared, cache zero; [community validation](community/mndodd-qwen36-27b-llamacpp-sycl/validation/2026-08-12-asrock-b70-validation.md) |
| GGUF Q8_0, upstream-derived VDR2, target only | 1x ASRock B70 | **17.297038** (`17.124067` conventional) | Matched one-card control for the fork; cache zero; [community validation](community/mndodd-qwen36-27b-llamacpp-sycl/validation/2026-08-12-asrock-b70-validation.md) |
| GGUF Q8_0, mndodd fork, intrinsic MTP4 | 1x ASRock B70 | **39.618445** (`39.222260` conventional) | Support row pending the packet's explicit-greedy rerun; F16 target/draft KV; [community packet](community/mndodd-qwen36-27b-llamacpp-sycl/README.md) |
| GGUF Q8_0, mndodd fork, DFlash5 | 1x ASRock B70 | **38.084045** (`37.703205` conventional) | Support row, not target-only; the `65.00 tok/s` observation was one favorable prompt, not the fixed-suite median; [community packet](community/mndodd-qwen36-27b-llamacpp-sycl/README.md) |
| Native FP8 Safetensors, vLLM | 2x B70, TP2 | **30.171 tok/s** median decode | Different 15-row prompt-length benchmark, so not rank-comparable to the fixed suite; [community validation](community/dominick253-qwen36-27b-fp8-tp2-docker/STATUS.md) |

The official BF16 target was not downloaded in the current campaign. At
55.586 GB of weights, two 608 GB/s B70s have a target-only one-weight-read
roofline of about `21.9 tok/s` before collective and runtime overhead, so a
plain lossless TP2 goal above 30 tok/s is not physically credible. The Q8
target-only TP2 lane remains active toward the 40 tok/s stretch goal;
speculative rows stay separate.

## Validity Rules For Speed Claims

Diagnostic runs are allowed and useful, but headline records require the
model-lane gate. For Gemma/Qwen-style fresh-response records, that means:

- fixed realistic prompt suite;
- each prompt run once as a cold response;
- `cached_tokens=0` for every request;
- no prompt/KV cache reuse, context checkpoints, response reuse, warmed
  repeated prompts, or n-gram/history acceleration;
- target model and quantization unchanged;
- speculative decoding/MTP allowed only when accepted tokens are verified by
  the declared target model;
- primary metric is the median conventional rate across the 99 inter-token
  intervals between timestamps 1 and 100 after TTFT, with p10, mean, TTFT,
  wall-clock full-output throughput, full-output after-TTFT throughput, hashes,
  runtime identity, env vars, flags, and logs. Historical 100-event/99-interval
  compatibility fields must be labeled as such.

Synthetic, repeated, warmed, cached, or history-assisted rows stay diagnostic
unless revalidated by the lane's promotion gate. This matters because several
very fast historical rows were useful optimization clues but not real-world
fresh-response claims.

## Hardware Scope

Historical reference results in this repository were produced on four
Intel-branded Arc Pro B70 32 GB cards. The current validation host has **two
ASRock Arc Pro B70 32 GB cards** (`64 GB` aggregate VRAM), full-size ReBAR, and
PCIe 5.0 x16 links. Hardware/count therefore remains part of every result
identity. B70 is the platform on which maintainers can independently reproduce
and verify submitted patches, but this is an Intel Arc/XPU project, not a
B70-only repository.

Results, fixes, and portability reports from Intel Arc Pro B50, B60, B65, and
B70 owners are welcome, as are useful observations from other Intel Arc and
XPU systems. A B70 rerun verifies what a patch does on B70; it does not certify
a contributor's score on hardware the maintainers do not possess. Hardware and
verification status therefore stay explicit in every promoted result.

The historical four-card host enabled TP4 and four independent one-GPU
screens; the current two-card host supports TP2 or two isolated one-card
screens. Higher-memory Intel devices would broaden model coverage, but that is
not a prerequisite for contributing useful patches, results, failures, or
optimization lessons.

Steve Seguin maintains this repo and posts ongoing build notes at
<https://x.com/xyster>.

<img height="600" alt="quad" src="https://github.com/user-attachments/assets/e6ce5633-17ff-4a73-924d-31dcbc913ede" />

<img width="1666" height="478" alt="Gemma 4 26B B70 result context" src="https://github.com/user-attachments/assets/14602c6b-5c72-483d-aec7-415fbc4a8114" />

## How To Contribute

This remains primarily a working optimization lab, but careful outside
contributions are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md) and
the [manual verification policy](docs/contribution-verification.md). No result
needs to be a record to be useful.

Useful contributions include:

- reproducing a result on another Intel/XPU stack and sharing exact versions;
- testing a failed lane after a driver, PyTorch XPU, vLLM, llama.cpp, or oneAPI
  update;
- turning local patches into clean upstream issues or PRs;
- adding quality canaries for new model families;
- sharing high-signal failure logs with model, quantization, graph mode, and
  hardware identity intact;
- providing temporary access to larger Intel hardware for models that do not
  fit cleanly on 32 GB cards.

When opening an issue or discussion, include GPU, OS, model, quantization,
runtime, exact command, benchmark shape, quality gate, result JSON/log paths,
and what changed from the closest known-good run.

## Reusable Optimization Lessons

The durable value of this lab is not only its fastest rows. Start with the
[cross-model pattern catalog](docs/research-workflow-playbook.md#cross-model-patterns-worth-reusing)
for evidence-linked strategies that transfer across model lanes, and the
[model optimization guide](docs/model-optimization-guide.md) for the
identity, quality, A/B, variance, and negative-result process used to test them.
Model-specific packets retain the commands and caveats behind each lesson.

## Deep Historical Notes Below

The former top-level chronology was preserved verbatim in
[notes/2026-07-11-readme-historical-b70-archive.md](notes/2026-07-11-readme-historical-b70-archive.md).
It remains useful for chronology and link recovery, but maintained navigation
now lives in the result packets, model-effort index, reproduction recipes, and
optimization guides.

## Historical B70 Findings And Open Leads

Use the [historical archive](notes/2026-07-11-readme-historical-b70-archive.md)
for the original long-form findings. Current model-specific starting points are
the [results index](results/README.md), including the
[MiniMax M2.7 packet](results/minimax-m27-int4-autoround-b70/README.md), and the
[cross-model effort index](docs/model-effort-index.md). Underlying notes, data,
patches, experiments, and reproduction paths were intentionally left in place.

## Layout

Use the [docs index](docs/README.md) for maintained navigation and the
[repository organization](#how-the-repo-is-organized) above for placement
rules. The former file-by-file inventory is retained in the
[historical archive](notes/2026-07-11-readme-historical-b70-archive.md); it is
not duplicated here because detailed inventories become stale quickly.

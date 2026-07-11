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

- Local AI users who want reproducible Intel Arc/B-series commands and
  benchmark recipes, not just screenshots of results.
- Anyone deciding whether Intel Arc/B-series hardware is worth it for local
  inference, and wanting real numbers to compare against.
- Optimization agents and contributors who need a map of current work,
  archived lessons, and validity rules before touching code.
- Upstream vLLM, llama.cpp, oneAPI, SYCL, and Intel/XPU developers looking for
  concrete repros and failure signatures.

## Start Here

| Need | Entry Point |
| --- | --- |
| Understand the repo structure | [Docs index](docs/README.md) |
| See every active, paused, and archived model lane | [Model effort index](docs/model-effort-index.md) |
| Reproduce promoted results | [Results index](results/README.md) and [model recipes](docs/model-recipes.md) |
| Start optimizing a new model | [Model optimization guide](docs/model-optimization-guide.md) |
| Compare expected model performance | [Performance scoreboard](results/scoreboard.md) |
| Contribute a result, patch, or correction | [Contribution guide](CONTRIBUTING.md) and [verification policy](docs/contribution-verification.md) |
| Review or validate incoming work | [Manager playbook](MANAGER.md) |
| Reuse the best research prompts/workflows | [Research workflow playbook](docs/research-workflow-playbook.md) |
| Find the current host/service map | [Current reproducibility map](docs/current-reproducibility-map.md) |
| Submit or audit LocalMaxxing records | [LocalMaxxing submissions](docs/localmaxxing.md) |
| Handle local ops, secrets, sudo, and cross-agent delegation | [Local ops](docs/local-ops.md) |
| Review Intel-facing issues and asks | [Feedback for Intel](docs/feedback-for-intel.md) |

## How The Repo Is Organized

The repo is organized around model lanes, not branches or one-off leaderboard
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

The point is to make model switching cheap. Gemma, Qwen, MiniMax, and future
lanes should all share validation discipline, result-packet shape, and reusable
kernel/runtime lessons without dragging stale worktrees or huge artifacts
forward.

## Representative Promoted Results

[`CURRENT.md`](CURRENT.md) alone owns the live service and active research
state. These are evidence-backed examples; the broader expected-performance
view is the [performance index](results/scoreboard.md).

These are entry points, not the whole repo:

| Lane | Status | Best Current Pointer |
| --- | --- | --- |
| Qwen3.6 27B INT4 AutoRound on 1-2x B70 | Active optimization target; strict fresh-response TP2 FP16-compute record **`91.714 tok/s`** with a pair-swapped high of `92.637`; pinned public oneCCL fixes target all-reduce, an opaque compiled all-gather enables the MTP draft graph, and capturing GDN target segments reduces target graph pieces from 129 to 33; exact cases, repeat128, baseline parity, 1K needle, unique cold prompts, and `cached_tokens=0` all passed; two four-GPU pair assignments measured FP16 gains of `5.70%` and `7.09%`; LocalMaxxing `cmrgojixq005rmj0141e9fjj2`, prior TP2 `cmrgn3szj005dmj01u8tel6yd`, previous TP1 `68.236 tok/s` at `cmr9atqb800msqr01u760xh0t`; current service ladder passes exact cold retrieval through `17706` actual prompt tokens at `MAX_MODEL_LEN=32768` | [current record packet](results/qwen36-27b-autoround-int4-b70/tp2-fp16-capture-gdn-20260711.json), [handoff](results/qwen36-27b-autoround-int4-b70/HANDOFF.md), [record note](experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-11-tp2-capture-gdn-core-record.md), [service ladder](experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-long-context-ladder-baseline.md), [general repro](repro/qwen36-27b-autoround-int4-b70/README.md) |
| Gemma 4 26B A4B Q8 / INT8 on 1x B70 | Production-servable backend plus current strict fresh-response speed frontier; noisy near-record support band | [handoff](results/gemma4-26b-a4b-q8-b70/HANDOFF.md), [production service](results/gemma4-26b-a4b-q8-b70/production-service.md), [125 tok/s repro](repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md) |
| Gemma 4 26B long-context/prompt-processing service lane | Separate from short-decode record; approved LocalMaxxing service entry `cmr47ivql0045nv011pfdjlaa`; service gates must not regress short decode | [Gemma result packet](results/gemma4-26b-a4b-q8-b70/README.md), [service gate script](repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh) |
| Rapid one-B70 model snapshots | Quick strict/fresh decode baselines across practical GGUF/vLLM candidates; current promoted rows include Qwen3 30B-A3B `107.484 tok/s`, Qwen3-Coder 30B-A3B `108.117 tok/s`, Phi-4 mini Q4 `96.548 tok/s`, GLM-4.7-Flash `40.769 tok/s`, and Mistral Small 3.2 24B `27.297 tok/s` | [rapid result ledger](results/rapid-model-snapshots-b70/README.md), [rapid experiment notes](experiments/rapid-model-snapshots-b70/README.md) |
| Qwen3.6 35B A3B Quark W8A8 INT8 on B70 | Closed reference packet for now; preserve lessons for future return | [Qwen result packet](results/qwen36-35b-quark-int8-b70/README.md), [research map](docs/qwen36-research-map.md) |
| MiniMax M2.7 INT4 AutoRound on 4x B70 | Deployable baseline plus older strict-speed and source-fusion research leads | [result packet](results/minimax-m27-int4-autoround-b70/README.md), [Ubuntu 24 deploy repro](repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md), [production service notes](docs/minimax-production-c1-service.md) |
| Gemma 4 12B IT INT4 AutoRound | Current model-slot production profile and multimodal service lane | [experiment packet](experiments/gemma4-12b-int4-autoround-vllm/README.md), [slot switching](docs/model-slot-switching.md) |

For the full queue and archive, use [docs/model-effort-index.md](docs/model-effort-index.md).

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
- primary metric is median generated-token throughput for tokens 1-100 after
  TTFT, with p10, mean, TTFT, wall-clock full-output throughput, full-output
  after-TTFT throughput, hashes, runtime identity, env vars, flags, and logs.

Synthetic, repeated, warmed, cached, or history-assisted rows stay diagnostic
unless revalidated by the lane's promotion gate. This matters because several
very fast historical rows were useful optimization clues but not real-world
fresh-response claims.

## Hardware Scope

The reference lab has four Intel Arc Pro B70 32 GB cards (`128 GB`
aggregate VRAM). B70 is the platform on which maintainers can independently
reproduce and verify submitted patches, but this is an Intel Arc/XPU project,
not a B70-only repository.

Results, fixes, and portability reports from Intel Arc Pro B50, B60, B65, and
B70 owners are welcome, as are useful observations from other Intel Arc and
XPU systems. A B70 rerun verifies what a patch does on B70; it does not certify
a contributor's score on hardware the maintainers do not possess. Hardware and
verification status therefore stay explicit in every promoted result.

The four-card B70 host is enough for useful vLLM/XPU, llama.cpp/SYCL, driver,
and model-port work, and it can run four independent one-GPU screens when a
model fits. Higher-memory Intel devices would broaden model coverage, but that
is not a prerequisite for contributing useful patches, results, failures, or
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

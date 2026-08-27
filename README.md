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
| Find a tested result or reproduction artifact | [Results index](results/README.md), [classified reproduction catalog](repro/README.md), and [certification standard](docs/reproduction-guide-certification.md) |
| Try a packaged candidate | Browse the [model guide library](guides.html) or its [machine-readable package catalog](packages/catalog.json) — twelve candidates/replays, none yet starter-certified |
| Start optimizing a new model | [Model optimization guide](docs/model-optimization-guide.md) |
| See or prepare the next model downloads | [Model intake queue](model-intake/README.md) |
| Follow the Docker and Windows packaging path | [Distribution and packaging roadmap](docs/model-distribution-and-packaging-roadmap.md) |
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
- `repro/<model>-.../`: classified reproduction artifacts, ranging from
  portable candidates to originating-host lab replays and archived records;
  the catalog, not the directory name, states portability.
- `packages/<model>-.../`: user-facing, machine-readable front doors over
  exact in-repository guides, commands, dependencies, and evidence.
- `experiments/<model>-.../`: active research lanes that are not production
  recipes yet.
- `notes/`: chronological lab notebook entries, including negative results and
  postmortems.
- `patches/`: patch snapshots and source/config deltas, including failed
  experiments worth preserving.
- `data/`: compact structured benchmark records, payloads, responses, and logs.
- `scripts/`: reusable harnesses, analyzers, launchers, and submission helpers.
- `model-intake/`: revision-pinned candidate catalog, storage budget, and the
  boundary between discovery, download, validation, and promotion.
- `community/<contributor>-...`: runnable work contributed from outside the
  reference lab, with explicit evidence status and validation history.
- `community/field-reports/`: unverified measurements and observations from
  community systems, kept separate from recipes, patches, validation assets,
  and promoted results. See [`community/README.md`](community/README.md).

The point is to make model switching cheap. Gemma, Qwen, MiniMax, and future
lanes should all share validation discipline, result-packet shape, and reusable
kernel/runtime lessons without dragging stale generated builds or huge artifacts
forward.

## Representative Results and Public Packages

[`CURRENT.md`](CURRENT.md) alone owns the live service and active research
state. These are evidence-backed examples; the broader expected-performance
view is the [performance index](results/scoreboard.md).

### Current public package headlines

This table is generated from the package manifests. It is a synchronization
view, not a ranking: workloads, context lengths, card counts, quantization,
and speculative-decoding modes differ. Open the detail page for the exact
measurement scope and evidence.

<!-- BEGIN GENERATED PUBLIC PACKAGE HEADLINES -->
| Model and deployment | Package status | Measured headline | Exact guide |
| --- | --- | ---: | --- |
| **[LFM2.5 2.6B Q8_0 on one Intel Arc Pro B70](models/lfm25-26b-q8-b70.html)**<br>1&times; B70 · Q8_0 · llama.cpp SYCL | `candidate` · clean-host replay pending | **`132.137457 tok/s`**<br>strict class-balanced decode | [reproduction guide](repro/lfm25-26b-q8-b70/README.md) |
| **[Laguna S 2.1 INT4 with DFlash on four Intel Arc Pro B70 cards](models/laguna-s-2.1-int4-b70-125tps-20260731.html)**<br>4&times; B70 · INT4 / BF16 KV · vLLM XPU | `candidate` · clean-host replay pending | **`125.461973 tok/s`**<br>conventional decode median | [reproduction guide](repro/laguna-s-2.1-int4-b70-125tps-20260731/README.md) |
| **[Gemma 4 26B A4B UD-Q8_K_XL on one Intel Arc Pro B70](models/gemma4-26b-a4b-q8-b70-125tps-20260701.html)**<br>1&times; B70 · UD-Q8_K_XL + Q4_0 MTP · llama.cpp SYCL | `candidate` · clean-host replay pending | **`122.160357 tok/s`**<br>decode (MTP-assisted) | [reproduction guide](repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md) |
| **[Muse-Glimmer 30B Q8/WOQ with DFlash on four Intel Arc Pro B70 cards](models/muse-glimmer-30b-q8-woq-b70-100tps-20260813.html)**<br>4&times; B70 · UD-Q8_K_XL / BF16 draft · llama.cpp SYCL | `candidate` · clean-host replay pending | **`100.3685 tok/s`**<br>pooled canonical mean | [reproduction guide](repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/README.md) |
| **[MiniMax M2.7 AutoRound INT4 on four Intel Arc Pro B70 cards](models/minimax-m27-b70-89tps-20260520.html)**<br>4&times; B70 · AutoRound W4A16 INT4 · vLLM XPU + llm-scaler | `candidate` · clean-host replay pending | **`89.314195 tok/s`**<br>mean output throughput | [reproduction guide](repro/minimax-m27-b70-89tps-20260520/README.md) |
| **[Qwen3.8 27B Q4_K_M on two Intel Arc Pro B70 cards](models/qwen38-27b-q4km-tp2-asrock-b70.html)**<br>2&times; B70 · Q4_K_M / F16 KV · llama.cpp SYCL | `candidate` · clean-host replay pending | **`49.717503 tok/s`**<br>conventional decode median | [reproduction guide](repro/qwen38-27b-q4km-tp2-asrock-b70/README.md) |
| **[Qwen3.8 27B Q4_K_M + MTP2 on one Intel Arc Pro B70](models/qwen38-27b-q4km-mtp2-tp1-b70.html)**<br>1&times; B70 · Q4_K_M target + Q4_0 MTP draft · llama.cpp SYCL | `candidate` · clean-host replay pending | **`42.636988 tok/s`**<br>strict varied-prompt decode | [reproduction guide](repro/qwen38-27b-q4km-mtp2-tp1-b70/README.md) |
| **[Qwen3.8 27B Q8_0 + MTP2 on one Intel Arc Pro B70](models/qwen38-27b-q8-q4mtp-mtp2-tp1-b70.html)**<br>1&times; B70 · Q8_0 target + Q4_0 MTP draft · llama.cpp SYCL | `candidate` · clean-host replay pending | **`37.062028 tok/s`**<br>strict varied-prompt decode | [reproduction guide](repro/qwen38-27b-q8-q4mtp-mtp2-tp1-b70/README.md) |
| **[Qwen3.8 27B Q8_0 on two Intel Arc Pro B70 cards](models/qwen38-27b-q8-tp2-asrock-b70.html)**<br>2&times; B70 · Q8_0 / F16 KV · llama.cpp SYCL | `candidate` · clean-host replay pending | **`36.726447 tok/s`**<br>strict varied-prompt decode | [reproduction guide](repro/qwen38-27b-q8-tp2-asrock-b70/README.md) |
| **[Qwen3.8 27B Q4_K_M on one Intel Arc Pro B70](models/qwen38-27b-q4km-tp1-b70.html)**<br>1&times; B70 · Q4_K_M · llama.cpp SYCL | `candidate` · clean-host replay pending | **`27.825726 tok/s`**<br>decode | [reproduction guide](repro/qwen38-27b-q4km-tp1-b70/README.md) |
| **[Qwen3.8 27B 256K + vision + MTP draft on one Intel Arc Pro B70](models/qwen38-27b-256k-vision-mtp-b70.html)**<br>1&times; B70 · UD-Q5_K_S (shipped) / UD-Q4_K_XL (alternative) · llama.cpp SYCL | `candidate` · clean-host replay pending | **`26.668277 tok/s`**<br>decode (MTP-assisted, full package resident) | [reproduction guide](repro/qwen38-27b-256k-vision-mtp-b70/README.md) |
| **[Qwen3.8 27B Q8_0 on one Intel Arc Pro B70](models/qwen38-27b-q8-tp1-b70.html)**<br>1&times; B70 · Q8_0 · llama.cpp SYCL | `candidate` · clean-host replay pending | **`19.61924 tok/s`**<br>strict varied-prompt decode | [reproduction guide](repro/qwen38-27b-q8-tp1-b70/README.md) |
| **[Nemotron 3.5 Lightning 30B-A3B UD-Q4_K_M on one Intel Arc Pro B70](models/nemotron-35-lightning-30b-a3b-b70.html)**<br>1&times; B70 · UD-Q4_K_M · llama.cpp SYCL | `candidate` · clean-host replay pending | **strict headline pending**<br>The 72.169452/72.035976 varied-suite observations and reasoning-off canary summary are preserved in the guide, but their raw operating-point and canary JSON files are not closed in this repository. Import and hash-bind those files, then replay the quality/determinism gate before assigning a strict headline. | [reproduction guide](repro/nemotron-35-lightning-30b-a3b-b70/README.md) |
| **[Ornith 1.5 35B-A3B Q4_K_M on one Intel Arc Pro B70](models/ornith-15-35b-a3b-q4km-b70.html)**<br>1&times; B70 · Q4_K_M · llama.cpp SYCL | `candidate` · clean-host replay pending | **strict headline pending**<br>The 131.460231 tok/s two-server observation and matched patch A/B evidence remain valid scoped measurements, but the runtime produced 0/12 identical complete natural-response hashes across fresh stock servers. Keep the mechanism and context evidence; require a stable, registered cross-server oracle before assigning a strict package headline. | [reproduction guide](repro/ornith-15-35b-a3b-q4km-b70/README.md) |
| **[Ornith 1.5 9B Q8_0 on one Intel Arc Pro B70](models/ornith-15-9b-q8-b70.html)**<br>1&times; B70 · Q8_0 · llama.cpp SYCL | `candidate` · clean-host replay pending | **strict headline withheld**<br>Strict headline withheld after output-gate failure. Two complete fresh-server, cache-zero, 12-prompt/six-class attempts measured 49.593582 and 49.515869 tok/s and passed both objective-canary batteries, but complete token arrays matched only 8/12 across servers. | [reproduction guide](repro/ornith-15-9b-q8-b70/README.md) |
| **[Qwen3.8 27B official FP8 on two Intel Arc Pro B70 cards](models/qwen38-27b-fp8-vllm-tp2-asrock-b70.html)**<br>2&times; B70 · FP8 · vLLM XPU | `candidate` · clean-host replay pending | **strict headline withheld**<br>The compliant 12-prompt/512-cap two-server matrix is complete, but no single-user profile passed the 12/12 complete-token-array gate: MTP0, MTP1, and dynamic MTP8 each matched only 8/12. Sealed-cache, eager graph-off, eager W8A16-off, and one-B70 TP1 controls also failed. TP2 and cross-rank oneCCL are not required for the instability. Single-user headlines and MTP1 32K remain withheld; the scoped MTP0 32K and short-context aggregate results remain valid. | [reproduction guide](repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md) |
<!-- END GENERATED PUBLIC PACKAGE HEADLINES -->

### Research and historical entry points

These are entry points, not the whole repo:

| Lane | Status | Best Current Pointer |
| --- | --- | --- |
| **Muse-Glimmer-30B UD-Q8_K_XL on 4x B70** | Closed/banked no-training Q8/WOQ record: fixed-N16 oneDNN WOQ plus pretrained BF16 DFlash and distributed ARGMAX. Two canonical full-256 means **`100.088`** and **`100.649 tok/s`**; frozen 15-prompt cold conventional first-100 median **`161.900 tok/s`**, p10 `108.574`, all cache-zero. Target-verified, not BF16/lossless or universally token-exact; LocalMaxxing `cmss8515c00n0ms01n3begqgg` | [result packet](results/muse-glimmer-30b-q8-woq-b70/README.md), [standalone repro](repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/README.md), [source snapshots](patches/muse-glimmer-30b-b70/README.md) |
| **Poolside Laguna S 2.1 INT4 on 4x B70** | Exact target-verified DFlash depth 11 on the audited width-12 Breakable PIECEWISE graph, with segmented inline draft attention, a decode-only 128-GRF INT4 kernel, and the shared-elementwise M12 fusion: **`125.461973 tok/s`** conventional and **`126.729266 tok/s`** historical compatibility. The final-source cold suite passed 13/13 exact with all `cached_tokens=0`; LocalMaxxing `cms9wuuf300cqpm01t5i285tq` | [qualified result](results/laguna-s-2.1-int4-b70/README.md), [record evidence](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-shared-elementwise-m12-record.md), [source snapshots](patches/laguna-s-2.1-xpu-b70/README.md), [package guide](repro/laguna-s-2.1-int4-b70-125tps-20260731/README.md) |
| DeepSeek V4 Flash experimental uniform-K160 on 4x B70 | Paused/closed frontier; target-verified DSpark7 record **`80.820 tok/s`** high and `78.287 tok/s` three-suite median-of-medians; exact source bundles and fail-closed launcher preserved; LocalMaxxing `cmrquta9905w3lg013m5vxoqx` | [result packet](results/deepseek-v4-flash-k160-b70/README.md), [standalone repro](repro/deepseek-v4-flash-k160-b70-80tps-20260718/README.md), [closeout](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-21-deepseek-v4-flash-frontier-closeout.md) |
| Qwen3.6 27B INT4 AutoRound on 1-2x B70 | **Lane closed 2026-08-18, superseded by the Qwen3.8 INT4 lane above.** July TP2 row **`95.385 tok/s`** under its original metric/bar; LocalMaxxing `cmrh35ct50092mj01h7jgydqj`. The final fixed-RMSNorm screen matched then-sealed controls at `106.663`, but the matched 25-prompt candidate was only 12/25 exact at `93.446`; no new submission. | [final closeout](notes/2026-08-17-qwen36-int4-batch-invariant-rmsnorm-closeout.md), [independent validation](experiments/qwen36-27b-autoround-int4-b70/validation-20260815/README.md), [historical repro](repro/qwen36-27b-autoround-int4-b70/README.md) |
| Qwen3.6 27B GGUF Q8_0 target-only on 2x ASRock B70 | Active no-speculation TP2 optimization; clean-source record: **`36.604128 tok/s` conventional** (`36.973866` historical helper), full-512 after-TTFT `36.533899`; 12/12 512-token outputs exact and all cache counts zero; two-chain DP4A ILP plus recurrent/attention/collective fusions; `+17.981%` over the matched mndodd fork baseline | [handoff](results/qwen36-27b-q8-tp2-asrock-b70/HANDOFF.md), [result packet](results/qwen36-27b-q8-tp2-asrock-b70/README.md), [standalone repro](repro/qwen36-27b-q8-tp2-asrock-b70/README.md), [source patch](patches/qwen36-27b-q8-tp2-asrock-b70/README.md), [mndodd contributor packet](community/mndodd-qwen36-27b-llamacpp-sycl/README.md) |
| **Qwen3.8 27B GGUF target-only on 2x ASRock B70** | Q4_K_M **`49.717503 tok/s` conventional** (`50.219700` historical helper; LocalMaxxing `cmsy530c70cpwms01bl1sjk6g`). Q8_0 now has a strict packaged **`36.726447 tok/s`** headline from two fresh cache-zero varied-prompt servers with 12/12 complete token arrays exact; the historical raw-completions capture was `36.772932`. A narrow fixed-prompt Q8 c2 capture sustained **`57.398122 tok/s` aggregate** (~`28.70` each), but broader prompts confirmed schedule-dependent outputs, so it is capacity evidence rather than a general quality guarantee. All are no-MTP/DFlash/speculation; aggregate and single-stream rates are kept distinct | [Q8 primary repro](repro/qwen38-27b-q8-tp2-asrock-b70/README.md), [Q8 strict result](experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-q8-tp2-strict-reasoningoff-native-r2-result.md), [Q8 c2 repro](repro/qwen38-27b-q8-tp2-c2-asrock-b70/README.md), [Q4_K_M repro](repro/qwen38-27b-q4km-tp2-asrock-b70/README.md) |
| **Qwen3.8 27B official FP8/W8A16 on 2x B70** | **Strict varied-prompt single-user headline withheld after output-gate failure.** The compliant MTP0 pair measured `34.772270`/`34.740755 tok/s`, MTP1 `55.760069`/`55.782147`, and dynamic MTP8 `68.049727`/`62.432362`, but every pair matched only 8/12 complete outputs. Sealed-cache, graph-off, and W8A16-off controls also failed. Independently scoped target-only capacity evidence remains `1,112.570323 tok/s` aggregate at c128 and `31.489587 tok/s` decode at exact 32K. | [strict matrix](experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-fp8-strict-profile-matrix-result.md), [package](packages/qwen38-27b-fp8-tp2-b70/README.md), [reproduction guide](repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md) |
| **Qwen3.8 27B AutoRound INT4 speculative on 2x B70** | Active research, **not currently promoted**. Honest margin-free MTP5 anchor: **`101.170 tok/s`** all-25 (`92.851` selection-12), median of three arms; pairwise repeatability is only 21–22/25. Fresh post-recovery arms reached `102.132`/`102.176` but remained 21/25, and a sealed-cache TP1 pair was only 2/4, proving residual runtime nondeterminism without TP2/cross-rank oneCCL collectives or allreduce. Published `101.922`/`100.497` rows used an output-changing greedy margin and should be withdrawn | [TP1 result](experiments/qwen38-27b-b70/notes/2026-08-20-postrecovery-marginfree-tp1-runtime-nondeterminism.md), [repro/status](repro/qwen38-27b-autoround-int4-b70/README.md), [submission audit](results/localmaxxing-submissions.md) |
| Gemma 4 26B A4B Q8 / INT8 on 1x B70 | Production-servable backend plus current strict fresh-response speed frontier; noisy near-record support band | [handoff](results/gemma4-26b-a4b-q8-b70/HANDOFF.md), [production service](results/gemma4-26b-a4b-q8-b70/production-service.md), [125 tok/s repro](repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md) |
| Gemma 4 26B long-context/prompt-processing service lane | Separate from short-decode record; approved LocalMaxxing service entry `cmr47ivql0045nv011pfdjlaa`; service gates must not regress short decode | [Gemma result packet](results/gemma4-26b-a4b-q8-b70/README.md), [service gate script](repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh) |
| Rapid one-B70 model snapshots | Historical strict/fresh decode baselines across practical GGUF/vLLM candidates; retained for evidence and regression work rather than current model recommendations | [rapid result ledger](results/rapid-model-snapshots-b70/README.md), [rapid experiment notes](experiments/rapid-model-snapshots-b70/README.md) |
| Qwen3.6 35B A3B Quark W8A8 INT8 on B70 | Closed reference packet for now; preserve lessons for future return | [Qwen result packet](results/qwen36-35b-quark-int8-b70/README.md), [research map](docs/qwen36-research-map.md) |
| MiniMax M2.7 INT4 AutoRound on 4x B70 | Deployable baseline plus older strict-speed and source-fusion research leads | [result packet](results/minimax-m27-int4-autoround-b70/README.md), [Ubuntu 24 deploy repro](repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md), [production service notes](docs/minimax-production-c1-service.md) |
| Gemma 4 12B IT INT4 AutoRound | Current model-slot production profile and multimodal service lane | [experiment packet](experiments/gemma4-12b-int4-autoround-vllm/README.md), [slot switching](docs/model-slot-switching.md) |

For the full queue and archive, use [docs/model-effort-index.md](docs/model-effort-index.md).

### Qwen3.8 27B Model Board

Last audited **2026-08-27**. Qwen3.8 retains Qwen3.6's exact 64-layer,
three-GDN-to-one-full-attention tensor geometry, so the accepted exact-shape
TP2 stack transfers mechanically. Every new weight set is still independently
gated. Every row states whether it is target-only or speculative; promoted
measurements are cache-zero. Other B70 hosts
and agents should start with the [multi-host handoff](experiments/qwen38-27b-b70/MULTI-HOST-HANDOFF.md)
and [do-not-repeat index](experiments/qwen38-27b-b70/DO-NOT-REPEAT.md).

| Target and route | Hardware | Best captured decode result | Evidence boundary / pointer |
| --- | --- | ---: | --- |
| GGUF Q4_K_M, lab TP2 stack + device-local dense-FFN fusion | 2x ASRock B70, TP2 | **`50.219700` (`49.717503` conventional)** | No speculation; 12/12 complete output hashes exact against the prior target oracle; full-output after-TTFT `49.734644`; LocalMaxxing [`cmsy530c70cpwms01bl1sjk6g`](https://www.localmaxxing.com/en/runs/cmsy530c70cpwms01bl1sjk6g); [standalone repro](repro/qwen38-27b-q4km-tp2-asrock-b70/README.md), [source increment](patches/qwen38-27b-q4km-tp2-asrock-b70/README.md) |
| GGUF Q8_0, accepted packaged TP2 stack | 2x ASRock B70, TP2 | **`36.726447` strict paired headline** (`36.772932` historical raw-completions capture) | No speculation; two fresh full 12-prompt/six-class, 512-cap attempts passed cache-zero and objective-canary gates with 12/12 complete token arrays exact. The current outputs also match 12/12 historical response hashes. SG16 added `+0.257%`, SG24 added `+0.356%`, and DP4A2×SG24 beat one-chain SG24 in both endpoint pairs; [strict result](experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-q8-tp2-strict-reasoningoff-native-r2-result.md), [standalone repro](repro/qwen38-27b-q8-tp2-asrock-b70/README.md), [base summary](experiments/qwen38-27b-b70/data/2026-08-15-q8-tp2-transfer-summary.json), [DP4A2×SG24 result](experiments/qwen38-27b-b70/data/2026-08-17-q8-dp4a2-sg24-accepted.json) |
| GGUF Q8_0, accepted stack, two simultaneous requests | 2x ASRock B70, TP2, c2 | **`57.398122` aggregate (`28.70` per request)** | Narrow fixed-prompt capacity result, not single-stream or a general quality guarantee; broader prompt pairs confirmed schedule-dependent outputs; no speculation; [c2 repro](repro/qwen38-27b-q8-tp2-c2-asrock-b70/README.md), [capture](experiments/qwen38-27b-b70/data/2026-08-16-q8-tp2-c2-summary.json), [broader audit](experiments/qwen38-27b-b70/data/2026-08-16-q8-c2-batch-shape-audit.json) |
| **Official block-scaled FP8 + block-W8A16** | 2x ASRock B70, TP2 | **Single-user headline withheld; target-only `1,112.570323 tok/s` aggregate c128** | The compliant 512-cap strict pairs measured MTP0 `34.772270`/`34.740755`, MTP1 `55.760069`/`55.782147`, and dynamic MTP8 `68.049727`/`62.432362 tok/s`, but each was only 8/12 exact across fresh servers. Target-only/MTP0 independently measures `31.489587 tok/s` at exact 32K and passed its scoped aggregate/output gates; [strict matrix](experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-fp8-strict-profile-matrix-result.md), [package](packages/qwen38-27b-fp8-tp2-b70/README.md), [standalone repro](repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md) |
| Official block-scaled FP8, older Intel vLLM `0.21.0-b3.1` | 2x ASRock B70, TP2 | Not promoted | Superseded negative: artifact loaded, but bounded initialization hit device-lost/out-of-resource errors; [bring-up note](experiments/qwen38-27b-b70/notes/2026-08-15-bringup-checkpoint.md) |
| **AutoRound INT4 W4A16, vLLM/XPU MTP5 speculative** | 2x B70, TP2 | **`101.170 tok/s` all-25; `92.851` selection-12** | Current margin-free research anchor: median of `101.394`/`100.455`/`101.170`, but only 21/25, 21/25, and 22/25 pairwise token parity. A fresh target-only oracle exists; its A/B was 24/25. Post-recovery MTP5 remained 21/25 and a byte-identical sealed-cache TP1 pair was 2/4, so this is not promotable. The historical `101.922` LocalMaxxing throughput remains a measured speed observation of its exact margin-on configuration, but the output-changing margin invalidates its published exactness/quality interpretation; upstream disposition remains a human decision. [TP1 result](experiments/qwen38-27b-b70/notes/2026-08-20-postrecovery-marginfree-tp1-runtime-nondeterminism.md), [repro/status](repro/qwen38-27b-autoround-int4-b70/README.md), [position dossier](experiments/qwen38-27b-b70/notes/2026-08-23-lmx-position-and-candidates.md) |
| AutoRound INT4 W4A16, vLLM/XPU MTP4 speculative | 2x B70, TP2 | historical **`100.497 tok/s` all-25; `96.627` selection-12** | Preserved as a measured speed observation of the exact margin-on configuration, not a promotion-grade exactness result. The output-changing margin and margin-on quality baseline prevent clean comparison with margin-free rows; upstream disposition remains a human decision. LocalMaxxing [`cmszarna10e0nms0103hv0tve`](https://www.localmaxxing.com/en/runs/cmszarna10e0nms0103hv0tve); [audit and position](experiments/qwen38-27b-b70/notes/2026-08-23-lmx-position-and-candidates.md) |
| **AutoRound INT4 W4A16, vLLM XPU nightly, target-only, XPU graph on** | 1x B70, TP1 | **`30.22 / 30.26 tok/s` conventional (boot pair)** | Fastest single-card lane for this model (llama.cpp Q4_K_M TP1 is `27.82`). No speculation, cache-zero gated, objective battery pass (code canary `14`, repeats, 8K needle) on the exact config. The captures used diagnostic `ignore_eos=true`; no real baseline comparison was run. Caveat: deterministic within a boot but NOT across boots (autotuned kernels; 19/25 boot-pair output agreement), so no cross-boot token-exactness claim and no sealed record/LMX submission yet; [finding](experiments/qwen38-27b-b70/notes/2026-08-22-qwen38-tp1-vllm-nightly-bringup-finding.md), [data](experiments/qwen38-27b-b70/data/2026-08-22-qwen38-tp1-vllm-nightly-matrix.json) |
| **AutoRound INT4 W4A16, vLLM XPU nightly, target-only, XPU graph on** | 4x B70, TP4 | **`71.67 / 71.55 tok/s` conventional (boot pair)** | Fastest target-only Qwen3.8 result measured in this lab for this AutoRound/nightly identity; the objective canaries, 8-run repeat, cache-zero checks, and 8K needle passed, with 0.17% speed spread. The captures used diagnostic `ignore_eos=true`; no real baseline comparison was run. The two boots matched 21/25 complete outputs, and vLLM explicitly labels multi-GPU XPU Graph unsupported/experimental. Eager mode measured `17.4`; TP3 is impossible (16 GDN K heads % 3); TP4 needs `gpu-memory-utilization <= 0.6`; [TP-scale finding](experiments/qwen38-27b-b70/notes/2026-08-23-qwen38-tpscale-nightly-finding.md), [data](experiments/qwen38-27b-b70/data/2026-08-23-qwen38-tpscale-nightly-matrix.json) |

Community-reported alternatives are kept outside the promoted rows above:

| Target and route | Hardware | Best captured result | Evidence boundary / pointer |
| --- | --- | ---: | --- |
| GGUF Q4_K_M, oneAPI 2025.3-family JIT Docker using the lab TP2 patches | 1x/2x B70 on contributor host | Contributor reports **33.4 TP1 / 51.1 TP2 tok/s** target-only | `community-reported`; no raw benchmark data, fixed-suite evidence, cache telemetry, output hashes, or reference-lab execution. The container disables the lab's Q4K fusion under JIT after reported corruption. No files were vendored because the source has no explicit license; provenance and the useful packaging delta are retained in our [internal status and review](community/0xsero-qwen38-27b-q4km-docker/STATUS.md). |
| GPTQ INT4 G128, vLLM XPU target-only / native MTP4 | 1x ASRock B70 local; 1x Intel B70 contributor | **34.160467 / 87.605425 tok/s local** with native FP16 KV | Experimental performance only: native FP16 KV beat FP8 at 8K, MTP4 accepted 511/540 drafts and matched its target, and loaded MTP parameters were verified FP16. The GPTQ target failed a deterministic code-result canary (`30` versus correct Q8/Q4 result `14`), so this is not the no-quality-loss default or a promoted headline; [decision](community/sergiiob-qwen38-27b-vllm-xpu/validation/2026-08-16-quality-kv-dtype-decision.md), [community packet](community/sergiiob-qwen38-27b-vllm-xpu/STATUS.md) |
| GPTQ INT4 G128, vLLM **0.27.1** XPU Docker, fp8 KV, MTP ladder | 1x Arc Pro B70 32 GB (Reddit poster, single-card = TP1) | Reddit report **33.2 off / 47.1 MTP1 / 52.2 MTP2 tok/s**, 128K context | `community-reported` field report; poster's numbers, raw logs not captured, not reference-lab run. fp8 KV, prefix-caching, PLAIN eager+inductor, `--max-num-seqs 1` (MTP + concurrent requests crash the engine on this hybrid model). Newer 0.27.1 image than our pinned lane; our archived GPTQ A/B measured higher (`68.23` MTP2) but the GPTQ target fails our code-result quality canary, so GPTQ stays quality-rejected as a default; [field report](community/field-reports/reddit-arc-b70-vllm-52tps/README.md) |

#### TP1 single-card context + KV-cache sweep (Q4_K_M, llama.cpp)

Measured 2026-08-22 on one Arc Pro B70 with the accepted llama.cpp SYCL TP1
lane build, Q4_K_M target-only, flash-attn on, `llama-bench` pp2048 + tg128,
5 reps per depth. These are **raw-engine** rates for the decode/prefill *shape*
and the KV-dtype delta - not the promoted `27.83 tok/s` class-balanced
realistic-suite metric (depth-0 tg128 here is `24.81`; different harness, both
real). Raw data and chart: [sweep JSON](experiments/qwen38-27b-b70/data/2026-08-22-q4km-tp1-context-kv-sweep.json),
[chart SVG](experiments/qwen38-27b-b70/data/2026-08-22-q4km-tp1-context-kv-sweep.svg),
[finding](experiments/qwen38-27b-b70/notes/2026-08-22-qwen38-q4km-tp1-context-kv-sweep-finding.md).

| context depth | decode KV **f16** | decode KV **q8_0** | q8 vs f16 | prefill KV f16 | prefill KV q8_0 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 24.81 | 24.27 | -2.2% | 825 | 818 |
| 4096 | 24.25 | 21.05 | -13.2% | 893 | 887 |
| 8192 | 23.83 | 18.68 | -21.6% | 851 | 843 |
| 16384 | 23.10 | 14.86 | -35.7% | 780 | 772 |
| 32768 | 21.77 | 10.66 | **-51.0%** | 668 | 663 |

**KV8-vs-KV16 finding:** the q8_0-KV decode penalty *grows with context* -
~2% at 0 ctx to **-51% at 32K** - because the per-token KV dequant scales with
cached length. f16-KV decode stays nearly flat (`24.81 -> 21.77`, -12% to 32K).
Prefill is KV-dtype-independent (<1.5% at every depth). **Practical rule:**
keep KV at **f16 for speed** on this lane; use q8_0 KV only to fit longer
context in 32 GiB, accepting a large long-context decode hit. (The Reddit vLLM
report ran fp8 KV by default on the newer 0.27.1 XPU path. Our own vLLM TP1 is
now unblocked on the XPU nightly image - see the matrix below; there,
fp8_e4m3 KV measured decode-neutral at short context but output-divergent,
and fp8_e5m2 is refused outright by FlashAttention on this device.)

#### TP1 weight-quant ladder (Q4_K_M vs UD-Q4_K_XL vs UD-Q5_K_S, f16 KV)

Same lane, same config, f16 KV, three weight files. Decode tg128 (tok/s):

| context | **Q4_K_M** (17.67 GiB) | UD-Q5_K_S (17.38 GiB) | UD-Q4_K_XL (16.35 GiB) |
| ---: | ---: | ---: | ---: |
| 0 | **24.81** | 22.72 | 21.81 |
| 8192 | **23.83** | 21.79 | 21.06 |
| 16384 | **23.10** | 21.19 | 20.49 |
| 32768 | **21.77** | 20.09 | 19.45 |

**Counter-intuitive result:** decode speed is *inverse* to file size here -
the smallest file (UD-Q4_K_XL, 16.35 GiB) is the **slowest** decoder, and the
largest (plain Q4_K_M) is the **fastest** at every depth. Decode is therefore
not purely bandwidth-bound on this build: it is Q4_K-tuned (Q4_K reorder +
MMVQ), so uniform Q4_K_M hits the fast path while the unsloth UD mixed-precision
dynamic quants do not. This ordering is a property of the tuned lane build, not
a universal ranking of the formats. **Takeaway:** on this lane, prefer Q4_K_M
for speed (it is also the quality-validated promoted lane); pick a UD quant only
for its quality/size, accepting slower decode here.
[data](experiments/qwen38-27b-b70/data/2026-08-22-qwen38-tp1-weight-ladder-sweep.json),
[chart](experiments/qwen38-27b-b70/data/2026-08-22-qwen38-tp1-weight-ladder-sweep.svg),
[finding](experiments/qwen38-27b-b70/notes/2026-08-22-qwen38-q4km-tp1-context-kv-sweep-finding.md).

#### TP1 vLLM on the XPU nightly image (AutoRound INT4): unblocked; graph +25%; MTP verify-bound

Measured 2026-08-22/23 on one B70 (GPU0), same 25-prompt realistic suite and
conventional metric as the promoted lanes, cache-zero gated, prefix caching
off, `--max-num-seqs 1`. Image: `vllm-openai-xpu` nightly `e9d1398d9`
(dated 11 calendar days after v0.27.1 but not its descendant, torch 2.13+xpu).
The pinned `0.20.2rc1` TP1 crashes do not
reproduce here; container bring-up needs `CCL_ZE_IPC_EXCHANGE=sockets` + a
read-only `/dev/dri/by-path` mount. The full quality battery (code canary
`14`, repeats, 8K needle) passed on both certified configs: MTP-off f16
graph-off AND graph-on. Those battery runs did not supply `--baseline-json`,
so their `baseline_match_all=true` compatibility field is vacuous and is not
used as evidence of oracle parity.

| Config (f16 KV unless noted) | conventional decode tok/s | acceptance | outputs vs MTP-off oracle |
| --- | ---: | ---: | --- |
| MTP off (two boots) | **23.72 / 24.25** | - | oracle pair (20/25 cross-boot agreement) |
| MTP off, **XPU graph on** (two boots) | **30.22 / 30.26** | - | faithful (23/25, within boot envelope) |
| MTP off, fp8_e4m3 KV | 24.10 | - | **divergent (3/25)** - capacity lever only |
| MTP1 / MTP2 / MTP3 | 4.51 / 4.41 / 4.30 | 1.91 / 2.70 / 3.47 | faithful (23-24/25) |
| MTP1 + XPU graph | 7.63 | **0.00** | **corrupt (0/25) - do not use** |
| any MTP, fp8_e5m2 KV | fails to boot | - | `NotImplementedError` |

**TP scaling on the same container** (2026-08-23, same suite/metric,
characterization-only): eager multi-GPU decode is FLAT (~17 tok/s at both
TP2 and TP4, below single-card - per-step container collective tax), while
**XPU graph restores scaling: 30.2 / 48.8 / 71.7 tok/s at TP1 / TP2 / TP4**.
The 71.7 TP4 row is the fastest target-only Qwen3.8 result for this
AutoRound/nightly identity, not the lab-wide target-only record. All three
graph configs passed the objective battery, but multi-GPU XPU Graph is
explicitly unsupported/experimental in this vLLM build. The only TP4 MTP2
probe is infrastructure-invalid: concurrent ranks lost shared Triton-cache
artifacts, and the later `shm_broadcast` starvation was a downstream symptom.
It does not establish a TP>1 speculative-decode deadlock. Prefill
scales even in eager (281 -> ~500 -> ~860 tok/s); TTFT drops to 0.09 s at
TP4. TP3 is architecturally impossible (16 GDN K heads % 3). TP4 needs
`gpu-memory-utilization <= 0.6` (XPU single-allocation cap).
[TP-scale data](experiments/qwen38-27b-b70/data/2026-08-23-qwen38-tpscale-nightly-matrix.json),
[TP-scale finding](experiments/qwen38-27b-b70/notes/2026-08-23-qwen38-tpscale-nightly-finding.md).

Key findings: **XPU graph** (`VLLM_XPU_ENABLE_XPU_GRAPH=1`, default off on the
nightly) is worth **+25%** MTP-off and is output-faithful. **MTP at TP1
works and is output-faithful with excellent acceptance, but the verify step
costs ~190-200 ms per extra verify token** (~4-5x a whole MTP-off step), so
net decode collapses ~5x and deeper drafts cannot amortize it - opposite to
the community GPTQ result, pointing at the INC/AutoRound W4A16 small-batch
verify path or GDN serial verify. **Graph + MTP corrupts outputs** (0%
acceptance and 0/25 oracle match) - quarantined. The lane is deterministic
within a boot but not across boots (autotuned kernel selection), so it makes
no cross-boot token-exactness claim yet.
[data](experiments/qwen38-27b-b70/data/2026-08-22-qwen38-tp1-vllm-nightly-matrix.json),
[finding](experiments/qwen38-27b-b70/notes/2026-08-22-qwen38-tp1-vllm-nightly-bringup-finding.md),
[driver](experiments/qwen38-27b-b70/scripts/run-20260822-qwen38-tp1-nightly-docker-bench.sh).

Plain-language explainers for these results live in the Learn library:
[Quantization vs decode speed](https://neural.download/learn/quantization-and-speed.html),
[KV cache precision](https://neural.download/learn/kv-cache-precision.html),
[Context length](https://neural.download/learn/context-length.html),
[The MTP ladder](https://neural.download/learn/mtp-ladder.html).

### Qwen3.6 27B Model Board

Last audited **2026-08-15**. These rows share a model family, not a quality,
runtime, or benchmark class. “Target only” means no speculative draft; MTP and
DFlash rows retain the declared target as verifier. The first number is the
repository's historical published 100-event/99-interval rate where that
harness was used; the parenthesized value is conventional 99-interval
accounting from the same timestamps. Relative A/B gains are unchanged.

| Target and route | Hardware | Best captured decode result | Evidence boundary / pointer |
| --- | --- | ---: | --- |
| AutoRound INT4 W4A16, vLLM MTP3 | 2x B70, TP2 | historical **95.384868** (`94.431019` conventional) | **Lane closed 2026-08-18**; superseded by the Qwen3.8 INT4 research lane, whose current honest margin-free anchor is `101.170` but is not promotable. The July row is retained and unbeaten on its own 12-prompt suite. Two durable findings from the closeout: complete-token parity against a differently-configured reference is unsatisfiable at fp16, and XPU batch invariance is dead code behind `is_cuda_alike()` gates; [determinism/speed closeout](notes/2026-08-18-qwen36-int4-determinism-speed-tradeoff.md), [source packet](patches/qwen36-27b-autoround-int4-b70/determinism-closeout-20260818/README.md), [prior closeout](notes/2026-08-17-qwen36-int4-batch-invariant-rmsnorm-closeout.md) |
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

The measuring host has four Intel Arc Pro B70 32 GB cards and about 125 GiB
system RAM. A second host has **two ASRock Arc Pro B70 32 GB cards** (`64 GB`
aggregate VRAM), full-size ReBAR, PCIe 5.0 x16 links, and only about 15 GiB
system RAM; it is currently restricted to source/build/op-level work. Hardware,
count, and host identity remain part of every result. B70 is the platform on
which maintainers can independently reproduce and verify submitted patches,
but this is an Intel Arc/XPU project, not a B70-only repository.

Results, fixes, and portability reports from Intel Arc Pro B50, B60, B65, and
B70 owners are welcome, as are useful observations from other Intel Arc and
XPU systems. A B70 rerun verifies what a patch does on B70; it does not certify
a contributor's score on hardware the maintainers do not possess. Hardware and
verification status therefore stay explicit in every promoted result.

The four-card host enables TP4 or independent one-/two-GPU screens. The
two-card host has enough VRAM for TP2 but not enough system RAM for the current
Qwen3.8 AutoRound server, so GPU count alone is not a safety signal.

### Arc Pro B65 orientation

Intel specifies B65 and B70 with the same 32-GiB VRAM capacity and `608 GB/s`
memory bandwidth, but B65 has 20 versus 32 Xe cores and 160 versus 256 XMX
engines. A community report relayed from boyter claims roughly `42 tok/s` with
MTP, `22 tok/s` without MTP, and `19 tok/s` at a 150-W limit on one B65. The
command, prompt, metric, and exact power/MTP identity were not captured, so
these are purchasing-orientation anecdotes rather than verified comparisons.
Also note that this lab's `49.717503 tok/s` Qwen3.8 Q4_K_M result uses **two**
B70s, not one. See the [B65 field report](community/field-reports/boyter/arc-pro-b65-qwen38/README.md).

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

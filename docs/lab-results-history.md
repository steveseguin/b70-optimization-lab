# Lab results history (moved from the README)

These sections were the front page of the repository until October 28, 2026.
They were moved here verbatim so the README can stay short; links were
rebased to this folder. Numbers here are historical observations at the
dates stated in each entry. For current results use
[neural.download](https://neural.download/), the [package catalog](../packages/catalog.json)
and [CURRENT.md](../CURRENT.md).

## Representative results and package notes (to October 19, 2026)

The [official 27B FP8 quickstart](../packages/qwen38-27b-fp8-tp2-b70/README.md)
now uses the qualified October 17 one-launch attention overlay, MTP5 and 32K
input capacity. Its October 19 public-source acceptance passed 12/12 strict
reference outputs, six practical requests with exact repeats, and a clean stop.
It measured 46.013 tok/s on steve-b70s; the historical 90.3 tok/s pair on Turin
remains separately identified. These different hosts and runtime releases are
not a matched speed comparison.

The latest [own Xe runtime one-card recipe](../repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/README.md)
and [two-card recipe](../repro/qwen38-flash-next-iq3xxs-ownrt-tp2-b70/README.md)
now include two full-512 suites and distinct 512-input prefill observations.
They remain expert lab replays: complete outputs repeat exactly, but independent
oracle coverage stops at 128 tokens and portable admission remains incomplete.
The 36.603/63.612 tok/s capped records are documented separately, not substituted
for full-512 results or promoted through an incomplete quality gate.

| Updated text recipe | Decode observations | Prefill / context / concurrency coverage |
| --- | --- | --- |
| [27B FP8 TP2](../packages/qwen38-27b-fp8-tp2-b70/README.md) | Current-host acceptance 46.013 tok/s; historical Turin 90.3 tok/s | 512-input synthetic prefill 2164.081 tok/s (six requests); separate overlay screens 2K–32K and validated multi-user profile through 64 requests |
| [Flash-Next IQ3 own runtime TP1](../repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/README.md) | Full 512 cap 31.510–31.782 tok/s, two loads | 512 / native TTFT reading 32.595–32.752 tok/s; context curve absent; one request at a time |
| [Flash-Next IQ3 own runtime TP2](../repro/qwen38-flash-next-iq3xxs-ownrt-tp2-b70/README.md) | Full 512 cap 58.557–58.632 tok/s, two loads | 512 / native TTFT reading 75.884–75.973 tok/s; context curve absent; one request at a time |
| [Gemma 4 Q8](../packages/gemma4-26b-a4b-q8-b70/README.md) | Qualified 122.160357 tok/s; existing record | Separate production prefill 1307.54/1167.81/909.27 tok/s at 1867/7623/29400 actual tokens; faster kernel remains unshipped |
| [Nemotron 3.5 UD-Q4_K_M](../repro/nemotron-35-lightning-30b-a3b-b70/README.md) | Historical 72.17/72.04 tok/s withheld from strict headline | Raw depth sweep retained; full-suite hashes match 1/12; owner deferred strict replay |

The tables describe different measurement scopes. See each recipe for raw
receipts, exact flags, quality gates, sample counts and missing measurements.

Official **27B FP8 reading speed** now includes a 2,048-token prompt measurement
and a final bounded profiling review. [Results and evidence](../experiments/qwen38-27b-b70/notes/2026-09-14-fp8-prefill-focus-results.md)
cover two B70s, one user and fixed MTP1; no new optimization was promoted.

A bounded [AMD-to-B70 transfer test](../experiments/qwen38-27b-b70/notes/2026-09-14-amd-transfer-results.md)
adds 512/2K/16K reading measurements for the recommended 27B FP8 setup.
The exact projection-dispatch candidate was neutral. The newer-runtime/V2/
DFlash2 startup froze the host before inference; the user rebooted it and the
original qualified service was restored. No new speedup is claimed.
The [MTP-only source follow-up](../community/1337hero-r9700-qwen38-radiance/validation/2026-09-14-mtp-fp8-transfer-review.md)
excludes DFlash and ranks the remaining exactness-preserving ideas.
The [implementation follow-up](../experiments/qwen38-27b-b70/notes/2026-09-14-mtp-lossless-transfer-results.md) built metadata and exact
communication candidates. The communication attempt failed exactness and
recorded GPU faults; no speedup or new default was qualified.

[`CURRENT.md`](../CURRENT.md) alone owns the recorded host and active research
state. These are evidence-backed examples; the broader expected-performance
view is the [performance index](../results/scoreboard.md).

Additional **512-token prefill measurements** now cover 4B/9B on two B70s and
27B INT4 on one B70. [Results and optimization findings](../experiments/qwen38-27b-b70/notes/2026-09-14-prefill-followup-results.md)
keep reading speed separate from decode and HTTP first-token wait.

The optional R308 single-request boundary repair is available for
[Qwen3.5 4B](../repro/qwen35-4b-w4a16-b70/README.md) and
[9B](../repro/qwen35-9b-w4a16-b70/README.md). Both models passed fresh-server
boundary and strict identity gates; the [qualification note](../experiments/qwen35-4b-b70/notes/2026-09-13-r308-qualified-single-request.md)
defines its one-card, fixed-depth scope.

## Research and historical entry points

These are entry points, not the whole repo:

| Lane | Status | Best Current Pointer |
| --- | --- | --- |
| **Muse-Glimmer-30B UD-Q8_K_XL on 4x B70** | Closed/banked no-training Q8/WOQ record: fixed-N16 oneDNN WOQ plus pretrained BF16 DFlash and distributed ARGMAX. Two canonical full-256 means **`100.088`** and **`100.649 tok/s`**; frozen 15-prompt cold conventional first-100 median **`161.900 tok/s`**, p10 `108.574`, all cache-zero. Target-verified, not BF16/lossless or universally token-exact; LocalMaxxing `cmss8515c00n0ms01n3begqgg` | [result packet](../results/muse-glimmer-30b-q8-woq-b70/README.md), [standalone repro](../repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/README.md), [source snapshots](../patches/muse-glimmer-30b-b70/README.md) |
| **Poolside Laguna S 2.1 INT4 on 4x B70** | Exact target-verified DFlash depth 11 on the audited width-12 Breakable PIECEWISE graph, with segmented inline draft attention, a decode-only 128-GRF INT4 kernel, and the shared-elementwise M12 fusion: **`125.461973 tok/s`** conventional and **`126.729266 tok/s`** historical compatibility. The final-source cold suite passed 13/13 exact with all `cached_tokens=0`; LocalMaxxing `cms9wuuf300cqpm01t5i285tq` | [qualified result](../results/laguna-s-2.1-int4-b70/README.md), [record evidence](../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-shared-elementwise-m12-record.md), [source snapshots](../patches/laguna-s-2.1-xpu-b70/README.md), [package guide](../repro/laguna-s-2.1-int4-b70-125tps-20260731/README.md) |
| DeepSeek V4 Flash experimental uniform-K160 on 4x B70 | Paused/closed frontier; target-verified DSpark7 record **`80.820 tok/s`** high and `78.287 tok/s` three-suite median-of-medians; exact source bundles and fail-closed launcher preserved; LocalMaxxing `cmrquta9905w3lg013m5vxoqx` | [result packet](../results/deepseek-v4-flash-k160-b70/README.md), [standalone repro](../repro/deepseek-v4-flash-k160-b70-80tps-20260718/README.md), [closeout](../experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-21-deepseek-v4-flash-frontier-closeout.md) |
| Qwen3.6 27B INT4 AutoRound on 1-2x B70 | **Lane closed 2026-08-18, superseded by the Qwen3.8 INT4 lane above.** July TP2 row **`95.385 tok/s`** under its original metric/bar; LocalMaxxing `cmrh35ct50092mj01h7jgydqj`. The final fixed-RMSNorm screen matched then-sealed controls at `106.663`, but the matched 25-prompt candidate was only 12/25 exact at `93.446`; no new submission. | [final closeout](../notes/2026-08-17-qwen36-int4-batch-invariant-rmsnorm-closeout.md), [independent validation](../experiments/qwen36-27b-autoround-int4-b70/validation-20260815/README.md), [historical repro](../repro/qwen36-27b-autoround-int4-b70/README.md) |
| Qwen3.6 27B GGUF Q8_0 target-only on 2x ASRock B70 | Retained no-speculation TP2 clean-source record: **`36.604128 tok/s` conventional** (`36.973866` historical helper), full-512 after-TTFT `36.533899`; 12/12 512-token outputs exact and all cache counts zero; two-chain DP4A ILP plus recurrent/attention/collective fusions; `+17.981%` over the matched mndodd fork baseline | [handoff](../results/qwen36-27b-q8-tp2-asrock-b70/HANDOFF.md), [result packet](../results/qwen36-27b-q8-tp2-asrock-b70/README.md), [standalone repro](../repro/qwen36-27b-q8-tp2-asrock-b70/README.md), [source patch](../patches/qwen36-27b-q8-tp2-asrock-b70/README.md), [mndodd contributor packet](../community/mndodd-qwen36-27b-llamacpp-sycl/README.md) |
| **Qwen3.8 27B GGUF on 2x ASRock B70** | Q4_K_M + Q4_0 MTP2 has a replicated strict **`64.237301 tok/s`** one-user headline (two fresh servers, 24/24 complete candidate arrays exact to MTP0). Q4_K_M target-only remains `49.717503 tok/s` for one user and reaches **`192.341954 tok/s aggregate at c96`** with the exact F16 `ffn_down+ffn_gate` cache: two fresh candidates, 96/96 same-shape batch-oracle identity each, cache zero, effective 49,152-token pool, and near-capacity ~30.5 GiB/card use. The separate sequential comparison was 50/96, so this is not a batch-invariant-text claim. Q8_0 target-only is `36.726447 tok/s`. Speculative, target-only, aggregate, and single-stream rates remain distinct. | [Q4 MTP2 repro](../repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/README.md), [Q4 target-only repro](../repro/qwen38-27b-q4km-tp2-asrock-b70/README.md), [c96 result](../experiments/qwen38-27b-b70/notes/2026-08-30-qwen38-q4km-tp2-exact-f16-cache-c96-result.md), [Q8 primary repro](../repro/qwen38-27b-q8-tp2-asrock-b70/README.md) |
| **Qwen3.8 27B official FP8/W8A16 on 2x B70** | **Strict R187: MTP1 `54.935 tok/s`, MTP depth-2 `70.142 tok/s`, MTP depth-3 `79.183 tok/s`, MTP depth-4 `82.396 tok/s`, MTP depth-5 `86.182 tok/s`, MTP0 `33.097 tok/s`** (2026-09-03/04 clean boots; every pair 12/12; repeat-exact at 224-300-token prompts; MTP0 output-identical through c64 at 927.9 tok/s aggregate, MTP1 through c16 at 477.7, depth 3 through c16 at 557.0, depth 4 through c16 at 529.4, depth 5 through c16 at 493.2, depth 2 through c4 at 210.8). R187 = R156 served with one whole-graph torch.compile (`splitting_ops=[]`; on the piecewise compile MTP depth 2 emitted a phantom first token on one request in 64, an unfixed upstream defect that also occurs on the unmodified image; no whole-graph pass has shown it). Prebuilt image on GHCR (`ghcr.io/steveseguin/vllm-openai-xpu-qwen38-fp8`, digest `173660ec…`). LocalMaxxing approved R187 MTP1 `cmtmfa23g01tvl601eyqliy9y`, depth-2 `cmtmfa2i701tyl601yrkxjn46`, depth-3 `cmtmfa2t101u1l601gth9lyx6`, depth-4 `cmtmk61qo01x8l601vtqbitg5`, depth-5 `cmtn23c500005mm010ierd4g3`. R156 = the row-invariant R139 W8A16 image (release `qwen38-fp8-tp2-r139-20260902`, LocalMaxxing `cmtkvle7a0428p701k0ttabyy`) plus a Python mixed-step GDN split. Independent-host replay passes all gates; its slower CPU/fabric lowers c1 decode 1.8x graph-off, 94% recovered graph-on. | [fresh-cache audit](../experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-public-reproduction-audit.md), [R54 result](../experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-explicit-deterministic-matrix-r54-result.json), [package](../packages/qwen38-27b-fp8-tp2-b70/README.md), [reproduction guide](../repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md) |
| **Qwen3.8 27B official FP8 on 1x B70** | MTP depth 5 **`53.52 tok/s`** (fresh servers 53.58/53.45) with a 16,384-token context; no-quantization profile `51.61 tok/s` at 12,544 tokens; no MTP `19.40`. Prompt reading 1,987-2,043 tok/s at 2K-12K inputs. Outputs identical to no MTP on the strict suite, long-prompt continuations and a chat quality suite; repeat requests are bitwise identical. Replaces the August one-card eager screen (10.75 tok/s, 8,448 tokens). | [package](../packages/qwen38-27b-fp8-tp1-b70/README.md), [recipe](../repro/qwen38-27b-fp8-vllm-tp1-b70/README.md) |
| **Qwen3.8 27B AutoRound INT4 on 1–2x B70** | Best qualified shortlist record **117.528 tok/s** on two cards (R299/R294b, pair 117.46/117.59). Current R304 / vLLM v0.29.0 revalidation: TP2 **117.24/116.95**, TP1 **81.17/81.16**, G1/G2/G3 12/12. Multi-user limits are independently tested; see the two-pass matrix. Older output-changing MTP5 rows remain withdrawn. | [recipe](../repro/qwen38-27b-autoround-int4-b70/README.md), [package](../packages/qwen38-27b-int4-fixed-k-tp2-b70/README.md) |
| **[Flash-Next UD-IQ3_XXS, quantized compressed version · own Xe runtime · 2× B70](../models/qwen38-flash-next-iq3xxs-ownrt-tp2-b70.html)** | Current full-512 lab replay **58.557–58.632 tok/s**; 512-input native reading **75.884–75.973 tok/s**. Full-output independent quality, context sweep and concurrency remain pending. Historical packet44 retained separately. | [Recipe](../repro/qwen38-flash-next-iq3xxs-ownrt-tp2-b70/README.md), [test details](../results/qwen38-flash-next-ud-iq3xxs-b70/README.md) |
| **Qwen3.8 Flash-Next 125B-A6B official FP8 on 4x B70** | Current qualified lossless MTP1 record **46.854250 tok/s**, A367, approved September 13; exact serial GDN, unchanged verifier and output pins. Exact-32K **44.05 tok/s**, four-row median across A382/A394. The no-MTP profile separately measures **34.50 tok/s**, **32.67** at 32K. Multi-user result withheld after output mismatch; clean-host deployment remains pending. | [family](../models/qwen-flash-next.html), [record and evidence](../results/qwen38-flash-next-fp8-b70/README.md), [recipe](../repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/README.md) |
| Gemma 4 26B A4B Q8 / INT8 on 1x B70 | Production-servable backend plus current strict fresh-response speed frontier; noisy near-record support band | [handoff](../results/gemma4-26b-a4b-q8-b70/HANDOFF.md), [production service](../results/gemma4-26b-a4b-q8-b70/production-service.md), [125 tok/s repro](../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md) |
| Gemma 4 26B long-context/prompt-processing service lane | Separate from short-decode record; approved LocalMaxxing service entry `cmr47ivql0045nv011pfdjlaa`; service gates must not regress short decode | [Gemma result packet](../results/gemma4-26b-a4b-q8-b70/README.md), [service gate script](../repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh) |
| Rapid one-B70 model snapshots | Historical strict/fresh decode baselines across practical GGUF/vLLM candidates; retained for evidence and regression work rather than current model recommendations | [rapid result ledger](../results/rapid-model-snapshots-b70/README.md), [rapid experiment notes](../experiments/rapid-model-snapshots-b70/README.md) |
| Qwen3.6 35B A3B Quark W8A8 INT8 on B70 | Closed reference packet for now; preserve lessons for future return | [Qwen result packet](../results/qwen36-35b-quark-int8-b70/README.md), [research map](../docs/qwen36-research-map.md) |
| MiniMax M2.7 INT4 AutoRound on 4x B70 | Deployable baseline plus older strict-speed and source-fusion research leads | [result packet](../results/minimax-m27-int4-autoround-b70/README.md), [Ubuntu 24 deploy repro](../repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md), [production service notes](../docs/minimax-production-c1-service.md) |
| Gemma 4 12B IT INT4 AutoRound | Historical deployment and multimodal research profiles; host state is recorded in [CURRENT.md](../CURRENT.md) | [experiment packet](../experiments/gemma4-12b-int4-autoround-vllm/README.md), [slot switching](../docs/model-slot-switching.md) |

For the full queue and archive, use [docs/model-effort-index.md](../docs/model-effort-index.md).

## Qwen3.8 27B Model Board

Last audited **2026-08-30**. Qwen3.8 retains Qwen3.6's exact 64-layer,
three-GDN-to-one-full-attention tensor geometry, so the accepted exact-shape
TP2 stack transfers mechanically. Every new weight set is still independently
gated. Every row states whether it is target-only or speculative; promoted
measurements are cache-zero. Other B70 hosts
and agents should start with the [multi-host handoff](../experiments/qwen38-27b-b70/MULTI-HOST-HANDOFF.md)
and [do-not-repeat index](../experiments/qwen38-27b-b70/DO-NOT-REPEAT.md).

| Target and route | Hardware | Best captured decode result | Evidence boundary / pointer |
| --- | --- | ---: | --- |
| **GGUF Q4_K_M + external Q4_0 draft, MTP2** | 2x ASRock B70, TP2 target; draft on first card | **`64.237301 tok/s` strict paired headline** | Median of two fresh candidate servers (`64.180644`/`64.293959`) versus matched fresh MTP0 `49.787366` (+29.02%); full 12-prompt/six-class cache-zero suites, objective canaries passed, and 24/24 complete candidate arrays target-exact. Short-context one-user result only; no target-only 32K or concurrency value transfers. [standalone repro](../repro/qwen38-27b-q4km-q4mtp-mtp2-tp2-b70/README.md), [promotion attestation](../experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-q4mtp-tp2-mtp2-promotion-attestation.json) |
| GGUF Q4_K_M, lab TP2 stack + device-local dense-FFN fusion | 2x ASRock B70, TP2 | **one user `50.219700` (`49.717503` conventional); c96 aggregate `192.341954`** | No speculation; the one-user suite remains 12/12 complete-output exact. The separate two-family exact-cache c96 profile used two fresh candidate servers, prompt cache off, and 96/96 same-shape batch-oracle identity in each. It used an effective 49,152-token pool and about 30.5 GiB/device; isolated sequential identity remained 50/96 and one-user MMVQ decode is unchanged. [standalone repro](../repro/qwen38-27b-q4km-tp2-asrock-b70/README.md), [c96 result](../experiments/qwen38-27b-b70/notes/2026-08-30-qwen38-q4km-tp2-exact-f16-cache-c96-result.md), [source increment](../patches/qwen38-27b-q4km-tp2-asrock-b70/README.md) |
| GGUF Q8_0, accepted packaged TP2 stack | 2x ASRock B70, TP2 | **`36.726447` strict paired headline** (`36.772932` historical raw-completions capture) | No speculation; two fresh full 12-prompt/six-class, 512-cap attempts passed cache-zero and objective-canary gates with 12/12 complete token arrays exact. The current outputs also match 12/12 historical response hashes. SG16 added `+0.257%`, SG24 added `+0.356%`, and DP4A2×SG24 beat one-chain SG24 in both endpoint pairs; [strict result](../experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-q8-tp2-strict-reasoningoff-native-r2-result.md), [standalone repro](../repro/qwen38-27b-q8-tp2-asrock-b70/README.md), [base summary](../experiments/qwen38-27b-b70/data/2026-08-15-q8-tp2-transfer-summary.json), [DP4A2×SG24 result](../experiments/qwen38-27b-b70/data/2026-08-17-q8-dp4a2-sg24-accepted.json) |
| GGUF Q8_0, accepted stack, two simultaneous requests | 2x ASRock B70, TP2, c2 | **`57.398122` aggregate (`28.70` per request)** | Narrow fixed-prompt capacity result, not single-stream or a general quality guarantee; broader prompt pairs confirmed schedule-dependent outputs; no speculation; [c2 repro](../repro/qwen38-27b-q8-tp2-c2-asrock-b70/README.md), [capture](../experiments/qwen38-27b-b70/data/2026-08-16-q8-tp2-c2-summary.json), [broader audit](../experiments/qwen38-27b-b70/data/2026-08-16-q8-c2-batch-shape-audit.json) |
| **Official block-scaled FP8 + block-W8A16** | 2x ASRock B70, TP2 | **strict MTP1 `51.808087 tok/s`; target-only `1,112.570323 tok/s` aggregate c128** | The R53/R54 matrix used two fresh MTP1 candidates and two same-image MTP0 controls. Every complete natural-512 workload/canary gate passed and all four target/candidate comparisons were 12/12 exact. MTP0 centers at `33.733520 tok/s`; dynamic MTP stays withheld. The historical exact-depth profile separately measured `46.636241 tok/s` at 32K; [audit](../experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-public-reproduction-audit.md), [R54 result](../experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-explicit-deterministic-matrix-r54-result.json), [32K result](../experiments/qwen38-27b-b70/notes/2026-08-28-qwen38-fp8-w8a16-mtp1-exact-depth-r33-result.md), [package](../packages/qwen38-27b-fp8-tp2-b70/README.md), [standalone repro](../repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md) |
| Official block-scaled FP8, older Intel vLLM `0.21.0-b3.1` | 2x ASRock B70, TP2 | Not promoted | Superseded negative: artifact loaded, but bounded initialization hit device-lost/out-of-resource errors; [bring-up note](../experiments/qwen38-27b-b70/notes/2026-08-15-bringup-checkpoint.md) |
| **AutoRound INT4 W4A16, MTP4, XPU graphs + 67k draft shortlist** | 2x B70, TP2 | **117.528 tok/s** pair center (117.46/117.59, R299/R294b) | G1/G2/G3 12/12; approved shortlist record. Current R304 replay 117.24/116.95; one-card 81.17/81.16. Output-identical concurrency is scoped separately in the [recipe](../repro/qwen38-27b-autoround-int4-b70/README.md). |
| AutoRound INT4 W4A16, vLLM/XPU MTP4 speculative | 2x B70, TP2 | historical **`100.497 tok/s` all-25; `96.627` selection-12** | Preserved as a measured speed observation of the exact margin-on configuration, not a promotion-grade exactness result. The output-changing margin and margin-on quality baseline prevent clean comparison with margin-free rows; upstream disposition remains a human decision. LocalMaxxing [`cmszarna10e0nms0103hv0tve`](https://www.localmaxxing.com/en/runs/cmszarna10e0nms0103hv0tve); [audit and position](../experiments/qwen38-27b-b70/notes/2026-08-23-lmx-position-and-candidates.md) |
| **AutoRound INT4 W4A16, vLLM XPU nightly, target-only, XPU graph on** | 1x B70, TP1 | **`30.22 / 30.26 tok/s` conventional (boot pair)** | Fastest single-card lane for this model (llama.cpp Q4_K_M TP1 is `27.82`). No speculation, cache-zero gated, objective battery pass (code canary `14`, repeats, 8K needle) on the exact config. The captures used diagnostic `ignore_eos=true`; no real baseline comparison was run. Caveat: deterministic within a boot but NOT across boots (autotuned kernels; 19/25 boot-pair output agreement), so no cross-boot token-exactness claim and no sealed record/LMX submission yet; [finding](../experiments/qwen38-27b-b70/notes/2026-08-22-qwen38-tp1-vllm-nightly-bringup-finding.md), [data](../experiments/qwen38-27b-b70/data/2026-08-22-qwen38-tp1-vllm-nightly-matrix.json) |
| **AutoRound INT4 W4A16, vLLM XPU nightly, target-only, XPU graph on** | 4x B70, TP4 | **`71.67 / 71.55 tok/s` conventional (boot pair)** | Fastest target-only Qwen3.8 result measured in this lab for this AutoRound/nightly identity; the objective canaries, 8-run repeat, cache-zero checks, and 8K needle passed, with 0.17% speed spread. The captures used diagnostic `ignore_eos=true`; no real baseline comparison was run. The two boots matched 21/25 complete outputs, and vLLM explicitly labels multi-GPU XPU Graph unsupported/experimental. Eager mode measured `17.4`; TP3 is impossible (16 GDN K heads % 3); TP4 needs `gpu-memory-utilization <= 0.6`; [TP-scale finding](../experiments/qwen38-27b-b70/notes/2026-08-23-qwen38-tpscale-nightly-finding.md), [data](../experiments/qwen38-27b-b70/data/2026-08-23-qwen38-tpscale-nightly-matrix.json) |

Community-reported alternatives are kept outside the promoted rows above:

| Target and route | Hardware | Best captured result | Evidence boundary / pointer |
| --- | --- | ---: | --- |
| GGUF Q4_K_M, oneAPI 2025.3-family JIT Docker using the lab TP2 patches | 1x/2x B70 on contributor host | Contributor reports **33.4 TP1 / 51.1 TP2 tok/s** target-only | `community-reported`; no raw benchmark data, fixed-suite evidence, cache telemetry, output hashes, or reference-lab execution. The container disables the lab's Q4K fusion under JIT after reported corruption. No files were vendored because the source has no explicit license; provenance and the useful packaging delta are retained in our [internal status and review](../community/0xsero-qwen38-27b-q4km-docker/STATUS.md). |
| GPTQ INT4 G128, vLLM XPU target-only / native MTP4 | 1x ASRock B70 local; 1x Intel B70 contributor | **34.160467 / 87.605425 tok/s local** with native FP16 KV | Experimental performance only: native FP16 KV beat FP8 at 8K, MTP4 accepted 511/540 drafts and matched its target, and loaded MTP parameters were verified FP16. The GPTQ target failed a deterministic code-result canary (`30` versus correct Q8/Q4 result `14`), so this is not the no-quality-loss default or a promoted headline; [decision](../community/sergiiob-qwen38-27b-vllm-xpu/validation/2026-08-16-quality-kv-dtype-decision.md), [community packet](../community/sergiiob-qwen38-27b-vllm-xpu/STATUS.md) |
| GPTQ INT4 G128, vLLM **0.27.1** XPU Docker, fp8 KV, MTP ladder | 1x Arc Pro B70 32 GB (Reddit poster, single-card = TP1) | Reddit report **33.2 off / 47.1 MTP1 / 52.2 MTP2 tok/s**, 128K context | `community-reported` field report; poster's numbers, raw logs not captured, not reference-lab run. fp8 KV, prefix-caching, PLAIN eager+inductor, `--max-num-seqs 1` (MTP + concurrent requests crash the engine on this hybrid model). Newer 0.27.1 image than our pinned lane; our archived GPTQ A/B measured higher (`68.23` MTP2) but the GPTQ target fails our code-result quality canary, so GPTQ stays quality-rejected as a default; [field report](../community/field-reports/reddit-arc-b70-vllm-52tps/README.md) |

### TP1 single-card context + KV-cache sweep (Q4_K_M, llama.cpp)

Measured 2026-08-22 on one Arc Pro B70 with the accepted llama.cpp SYCL TP1
lane build, Q4_K_M target-only, flash-attn on, `llama-bench` pp2048 + tg128,
5 reps per depth. These are **raw-engine** rates for the decode/prefill *shape*
and the KV-dtype delta - not the promoted `27.83 tok/s` class-balanced
realistic-suite metric (depth-0 tg128 here is `24.81`; different harness, both
real). Raw data and chart: [sweep JSON](../experiments/qwen38-27b-b70/data/2026-08-22-q4km-tp1-context-kv-sweep.json),
[chart SVG](../experiments/qwen38-27b-b70/data/2026-08-22-q4km-tp1-context-kv-sweep.svg),
[finding](../experiments/qwen38-27b-b70/notes/2026-08-22-qwen38-q4km-tp1-context-kv-sweep-finding.md).

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

### TP1 weight-quant ladder (Q4_K_M vs UD-Q4_K_XL vs UD-Q5_K_S, f16 KV)

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
[data](../experiments/qwen38-27b-b70/data/2026-08-22-qwen38-tp1-weight-ladder-sweep.json),
[chart](../experiments/qwen38-27b-b70/data/2026-08-22-qwen38-tp1-weight-ladder-sweep.svg),
[finding](../experiments/qwen38-27b-b70/notes/2026-08-22-qwen38-q4km-tp1-context-kv-sweep-finding.md).

### TP1 vLLM on the XPU nightly image (AutoRound INT4): unblocked; graph +25%; MTP verify-bound

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
[TP-scale data](../experiments/qwen38-27b-b70/data/2026-08-23-qwen38-tpscale-nightly-matrix.json),
[TP-scale finding](../experiments/qwen38-27b-b70/notes/2026-08-23-qwen38-tpscale-nightly-finding.md).

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
[data](../experiments/qwen38-27b-b70/data/2026-08-22-qwen38-tp1-vllm-nightly-matrix.json),
[finding](../experiments/qwen38-27b-b70/notes/2026-08-22-qwen38-tp1-vllm-nightly-bringup-finding.md),
[driver](../experiments/qwen38-27b-b70/scripts/run-20260822-qwen38-tp1-nightly-docker-bench.sh).

Plain-language explainers for these results live in the Learn library:
[Quantization vs decode speed](https://neural.download/learn/quantization-and-speed.html),
[KV cache precision](https://neural.download/learn/kv-cache-precision.html),
[Context length](https://neural.download/learn/context-length.html),
[The MTP ladder](https://neural.download/learn/mtp-ladder.html).

## Qwen3.6 27B Model Board

Last audited **2026-08-15**. These rows share a model family, not a quality,
runtime, or benchmark class. “Target only” means no speculative draft; MTP and
DFlash rows retain the declared target as verifier. The first number is the
repository's historical published 100-event/99-interval rate where that
harness was used; the parenthesized value is conventional 99-interval
accounting from the same timestamps. Relative A/B gains are unchanged.

| Target and route | Hardware | Best captured decode result | Evidence boundary / pointer |
| --- | --- | ---: | --- |
| AutoRound INT4 W4A16, vLLM MTP3 | 2x B70, TP2 | historical **95.384868** (`94.431019` conventional) | **Historical campaign closeout, 2026-08-18**; later Qwen3.8 INT4 qualifications and limits live in its [maintained recipe](../repro/qwen38-27b-autoround-int4-b70/README.md). The July row is retained and unbeaten on its own 12-prompt suite. Two durable findings from the closeout: complete-token parity against a differently-configured reference is unsatisfiable at fp16, and XPU batch invariance is dead code behind `is_cuda_alike()` gates; [determinism/speed closeout](../notes/2026-08-18-qwen36-int4-determinism-speed-tradeoff.md), [source packet](../patches/qwen36-27b-autoround-int4-b70/determinism-closeout-20260818/README.md), [prior closeout](../notes/2026-08-17-qwen36-int4-batch-invariant-rmsnorm-closeout.md) |
| AutoRound INT4 W4A16, vLLM ReplaySSM MTP3 | 1x B70 | **68.236263** (`67.553901` conventional) | Valid quality-gated historical high; July 11 isolated reconfirmation was `65.4-66.7 tok/s`, so do not treat the high as every-run expectation; [TP1 attribution packet](../results/qwen36-27b-autoround-int4-b70/tp1-draftgraph-attribution-reconfirm-20260711.json) |
| GGUF Q4_0, DFlash5 | 1x B70 | **47.818818** (`47.340630` conventional) | Strict fixed-suite speculative record; unchanged Q4_0 target verifies accepted tokens; [closure](../notes/2026-07-13-qwen27-dflash-sycl-closure.md) |
| GGUF Q4_K_M, intrinsic MTP2 | 1x B70 | **38.112 tok/s** | One fixed greedy 128-token request, visible bytes matched its 25.307 tok/s target-only control; not token-exact and not a fixed-suite median; [community validation](../community/dominick253-qwen36-27b-llamacpp-sycl/validation/2026-08-08-reference-lab-validation.md) |
| GGUF UD-Q4_K_XL, intrinsic MTP7 with `p_min=0.65` | 1x B70 | **31.480049** (`31.165249` conventional) | Best valid p-min support row; cache-zero fixed suite; [Q4 packet](../results/qwen36-27b-mtp-gguf-q4-b70/README.md) |
| GGUF Q4_0, target only | 1x B70 | **25.937011** (`25.677641` conventional) | Strict cold-suite target-only control from the closed DFlash campaign; [timeline evidence](../experiments/qwen27-dflash-sycl-b70/notes/2026-07-12-cycle-timeline-tooling.md) |
| GGUF Q8_0, mndodd base plus lab exact fusions, target only | 2x ASRock B70, TP2 | **36.973866** (**36.604128** conventional) | Current clean-source record; 12/12 cold 512-token output hashes exact and cache zero; full-512 after-TTFT `36.533899`; `+17.981%` over matched fork baseline; [result packet](../results/qwen36-27b-q8-tp2-asrock-b70/README.md) |
| GGUF Q8_0, mndodd fork baseline, target only | 2x ASRock B70, TP2 | **31.338765** (**31.025377** conventional) | Matched contributor-fork baseline; 12/12 complete hashes match the upstream-derived control, cache zero; [community packet](../community/mndodd-qwen36-27b-llamacpp-sycl/README.md) |
| GGUF Q8_0, mndodd fork, target only | 1x ASRock B70 | **17.955800** (**17.776242** conventional) | Matched raw-completions fixed suite; quality-cleared, cache zero; [community validation](../community/mndodd-qwen36-27b-llamacpp-sycl/validation/2026-08-12-asrock-b70-validation.md) |
| GGUF Q8_0, upstream-derived VDR2, target only | 1x ASRock B70 | **17.297038** (`17.124067` conventional) | Matched one-card control for the fork; cache zero; [community validation](../community/mndodd-qwen36-27b-llamacpp-sycl/validation/2026-08-12-asrock-b70-validation.md) |
| GGUF Q8_0, mndodd fork, intrinsic MTP4 | 1x ASRock B70 | **39.618445** (`39.222260` conventional) | Support row pending the packet's explicit-greedy rerun; F16 target/draft KV; [community packet](../community/mndodd-qwen36-27b-llamacpp-sycl/README.md) |
| GGUF Q8_0, mndodd fork, DFlash5 | 1x ASRock B70 | **38.084045** (`37.703205` conventional) | Support row, not target-only; the `65.00 tok/s` observation was one favorable prompt, not the fixed-suite median; [community packet](../community/mndodd-qwen36-27b-llamacpp-sycl/README.md) |
| Native FP8 Safetensors, vLLM | 2x B70, TP2 | **30.171 tok/s** median decode | Different 15-row prompt-length benchmark, so not rank-comparable to the fixed suite; [community validation](../community/dominick253-qwen36-27b-fp8-tp2-docker/STATUS.md) |

The official BF16 target was not downloaded in the current campaign. At
55.586 GB of weights, two 608 GB/s B70s have a target-only one-weight-read
roofline of about `21.9 tok/s` before collective and runtime overhead, so a
plain lossless TP2 goal above 30 tok/s is not physically credible. The Q8
target-only TP2 lane remains active toward the 40 tok/s stretch goal;
speculative rows stay separate.

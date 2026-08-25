# neural.download existing-evidence coverage backlog

Date: 2026-08-24
Status: read-only evidence audit converted to an implementation backlog
Primary rule: improve complete, simple family coverage before optional tuning
research. Rank by recent/popular model value and quality/evidence maturity, then
by optimization maturity; decode rate is only a tie-breaker.

## Boundaries

- Qwen3.6-27B and Qwen3.8-27B remain revisions of the same Qwen 27B family.
  Measurements remain revision-bound, while compatible source/configuration
  findings may be carried forward and requalified.
- Weight quantizations, KV quantizations, and runtime representations are
  deployment variants/selectors, not new model families. Do not fill a Quark
  cell with AutoRound evidence or a Q8-weight cell with Q4 weights plus Q8 KV.
- `EVID` below rates the evidence packet, not model intelligence. No new `CAP`
  grade is inferred from canaries or speed evidence.
- Every item below is a no-GPU measured import from tracked evidence. Values
  retain their exact runtime, workload, topology, context, and quality scope.
  None authorizes lowering or replacing a protected result.
- `D`, `P`, and `T` in compact rows mean decode tok/s, prefill tok/s, and TTFT
  milliseconds respectively.

## Ranked no-GPU imports

### 1. Qwen 27B: expose dated custom-current-main TP1 qualification evidence

Target: new runtime-version coverage slice for Qwen3.8 AutoRound INT4,
TP1, MTP0, graph on, F16 model/KV, configured 32K context. Keep TP2/TP4 and the
live `09fddeb4ce` + `1e90ffa672` identity explicitly missing until measured.

| Exact runtime cell | Exact strict values | Proposed state / boundary |
|---|---:|---|
| vLLM `0ecc284790`, stock base XPU kernels | `30.324297716696414`, `30.325970521145816` | `lab-measured`, EVID B; complete quality and immutable-cache replay, qualified dated control, not the live head |
| vLLM `0ecc284790`, XPU kernels `baaa05bb4e` | `30.27919625650121`, `30.261661472495938` | `lab-measured`, EVID C; quality-clean but both strict speed gates missed, not promoted |
| vLLM `6a9c69fa85`, XPU kernels `baaa05bb4e` | `30.26782494070049`, `30.27119782672338` | `lab-measured`, EVID C; complete repeatable quality-clean speed-only miss, not promoted or current |

Sources:

- `experiments/qwen38-27b-b70/data/2026-08-24-qwen38-0ecc-tp1-qualification-attempts.json`;
- `experiments/qwen38-27b-b70/data/2026-08-24-qwen38-6a9c69fa85-tp1-r1-speed-only-miss.json`;
- `experiments/qwen38-27b-b70/data/2026-08-24-qwen38-09fd-1e90-prebuild-storage-rotation.json` proves storage/build preparation only and supplies no performance value.

Import status: **completed 2026-08-24**. The three preregistered rows are now
exact measured cells in a dated-source-stack view, alongside the later frozen
`b2dd9ce73d` + `1e90ffa672` quality-clean strict-A snapshot. Failed or
incomplete candidates are not featured, and no dated head is called “current.”

### 2. Qwen 27B: complete the Qwen3.8 Q4_K_M KV-by-context cells

Target: TP1, MTP0, llama.cpp SYCL, graph off. Add the real F16-KV zero-depth
cell currently omitted from exact coverage, and add the entire Q8_0-KV context
slice already present in normalized series data.

| KV | Active context | Exact D / P |
|---|---:|---:|
| F16 | `0` | `24.81 / 825.24` |
| Q8_0 | `0` | `24.27 / 817.78` |
| Q8_0 | `2048` | `22.45 / 912.17` |
| Q8_0 | `4096` | `21.05 / 887.17` |
| Q8_0 | `8192` | `18.68 / 843.21` |
| Q8_0 | `16384` | `14.86 / 772.01` |
| Q8_0 | `24576` | `12.40 / 711.48` |
| Q8_0 | `32768` | `10.66 / 662.56` |

Source: `experiments/qwen38-27b-b70/data/2026-08-22-q4km-tp1-context-kv-sweep.json`.

Proposed state: exact `lab-measured` point cells. Curve evidence is EVID D
(five-repetition raw-engine shape characterization without its own language-
quality gate); keep the deployment packet's quality evidence separate. The
`x=0` rows are observed `n_depth=0` measurements, not graph origins invented by
the renderer.

Import status: **completed 2026-08-24**. The F16 zero-depth point and all seven
Q8_0-KV points now have exact coverage cells. TP2/TP4 context curves remain
unknown and explicit rather than inferred.

### 3. Ornith 1.5: surface multi-sequence throughput and the 9B zero point

Target A: Ornith 1.5 35B-A3B Q4_K_M, accepted twelve-feature stack, one B70,
F16 KV. Normalize the already-published aggregate profile into family coverage;
this answers a serving-capacity question that single-user decode does not.

| Concurrent engine sequences | Aggregate tok/s | Per-sequence tok/s |
|---:|---:|---:|
| `1` | `98.024651` | `98.024651` |
| `2` | `102.671738` | `51.335869` |
| `4` | `118.882942` | `29.720736` |
| `8` | `146.283051` | `18.285381` |
| `16` | `162.503937` | `10.156496` |
| `32` | `216.513077` | `6.766034` |

Source: `experiments/ornith-15-b70/data/2026-08-23-ornith35b-multirow-aggregate-summary.json`.
Boundary: raw `llama-batched-bench` continuous batching, not HTTP users or a
server scheduler. Proposed `lab-measured`, retain the 35B packet's EVID B.

Target B: add the observed Ornith 1.5 9B Q8_0 TP1 zero-depth point to the
package profile: `D50.291618 / P3184.490007`.

Source: `repro/ornith-15-9b-q8-b70/ornith-15-9b-q8.sweep.json`.
Proposed `lab-measured`, retain packet EVID C. It is an observed zero-depth row.

Import status: **completed 2026-08-24**. The 35B accepted-stack concurrency
series now exposes combined and per-sequence rates through c32, with two- and
four-card capacity curves explicit as unknown. The 9B zero-depth point remains
bound to its exact measured context curve. Engine sequences are not relabeled
as HTTP users.

### 4. Qwen 27B: add exact Qwen3.6 Q8_0 context-by-MTP coverage

Target A: normalize the isolated, band-tuned target-only TP1 profile.

| Active context | Exact D / P / T |
|---:|---:|
| `4369` | `16.587155022411466 / 606.0653917225968 / 7187.438126500638` |
| `17274` | `15.138173254861634 / 157.69755861897968 / 109245.59903149202` |
| `31846` | `13.689452617380034 / 628.7871123260159 / 50690.98523899447` |

The band-specific ubatch values are `1024/128/1024`; do not present this as a
single universally fixed batching curve.

Target B: add the matched same-card MTP0/MTP3 functional comparison.

| Active context | MTP0 D | MTP3 D | MTP3 draft acceptance |
|---:|---:|---:|---:|
| `17274` | `15.016411985013098` | `44.485166750615846` | `0.9718670076726342` |
| `31846` | `13.662820064556456` | `41.491242761811996` | `0.9743918053777209` |

Source: `experiments/qwen36-27b-q8-gguf-b70/data/goal1-c1-c2-scorecard-20260809.json`.

Proposed `lab-measured`, EVID C. The matched MTP comparison passed same-card
full-token/content and cache-zero checks but is a functional screen, not the
official isolated score. Treat this as the older-weight revision's evidence
and optimization lineage; never transfer its rates to Qwen3.8.

Import status: measured import.

### 5. Qwen 27B: expand Qwen3.8 quant-subset context classification

Target: separate TP1, MTP0, graph-off, F16-KV context slices for UD-Q5_K_S and
UD-Q4_K_XL, plus the Q8_0-KV UD-Q5_K_S package slice. Quants stay rows under
Qwen3.8, not separate models.

| Variant / KV | Contexts | Exact decode values | Exact prefill values |
|---|---|---|---|
| UD-Q5_K_S / F16 | `0/2K/4K/8K/16K/24K/32K` | `22.72/22.37/22.13/21.79/21.19/20.61/20.09` | `849.3/778.35/759.39/726.59/671.59/625.83/588.21` |
| UD-Q4_K_XL / F16 | `0/2K/4K/8K/16K/24K/32K` | `21.81/21.53/21.37/21.06/20.49/19.95/19.45` | `762.57/735.45/719.47/689.58/639.46/596.49/564.86` |
| UD-Q5_K_S / Q8_0 | `0/2K/4K/8K/16K/24K/32K` | `22.641875/21.013731/19.763244/17.627474/14.139247/11.904055/10.32272` | `915.077622/831.413858/822.288881/807.562129/760.357526/750.98526/678.867511` |

Sources:

- `experiments/qwen38-27b-b70/data/2026-08-22-qwen38-tp1-weight-ladder-sweep.json`;
- `repro/qwen38-27b-256k-vision-mtp-b70/qwen38-27b-q5ks-flagship.sweep.json`.

Proposed `lab-measured`. The curves themselves are EVID D/performance-only;
the Q5 deployment packet remains separately EVID C. Add the Q5 Q8_0 observed
zero point to its package profile as well. TP2/TP4 stay missing.

Import status: measured import.

### 6. Nemotron 3.5 Lightning: add family coverage and package zero point

Target A: TP1 UD-Q4_K_M, MTP0, graph off, F16-KV context cells.

| Contexts | Exact decode values | Exact prefill values |
|---|---|---|
| `0/2K/4K/8K/16K/24K/32K` | `73.008586/72.420657/71.846756/70.6952/68.557408/66.552475/64.622975` | `1260.029381/1166.922303/1153.135384/1145.645326/1106.136083/1102.582316/1018.926677` |

Source: `repro/nemotron-35-lightning-30b-a3b-b70/nemotron-35-lightning.sweep.json`.
Also add the real zero-depth row to the package performance profile.

Target B: a separate same-serving topology slice at configured 8K:
TP1 `72.169452/72.035976`; TP2 layer split
`69.445407/69.485984`.

Source: `repro/nemotron-35-lightning-30b-a3b-b70/README.md`.

Proposed `lab-measured`, EVID C: two fresh serving runs, a seven-point raw
profile, pinned identity, and objective canaries exist; clean-host replay and
context beyond 32K remain open. TP4 remains missing.

Import status: measured import.

### 7. Qwen 35B: classify AutoRound as its own quant subset

Target: do not use AutoRound evidence to fill a Quark W8A8 cell. Add a separate
AutoRound W4A16, TP1, MTP0, piecewise-graph slice and concurrent-sequence slice.

- r16 one-sequence decode: `90.90948338800597` tok/s;
- r14 aggregate at `1/2/4/8/16/32/64` sequences:
  `87.6382088209863/77.18628015630631/149.48350787682995/276.7655048798564/488.6474098238277/823.1508450629442/1039.408012834992` tok/s;
- r16 64-sequence aggregate: `1052.8704424119495` tok/s.

Source: `data/qwen36-35b-autoround-b70-concurrency-20260824.json`.

Proposed state: retain `lab-screened`, EVID C. The r16 treatment passed 100/100
literal canaries, but only 29/64 fixed-seed sequences matched and it is not a
promoted deployment. Keep r14 and r16 as separate profiles; never join the two
r16 points to the seven-point r14 curve. TP2/TP4 remain missing.

Import status: measured/screened import, not an estimate.

### 8. Gemma 4: add exact context and MTP coverage matrices

Target A: TP1 service-context cells at their exact observed token counts.

| Active context | Exact D / P / T |
|---:|---:|
| `741` | `161.89843663684636 / 847.9619132833765 / 873.9445414976217` |
| `2806` | `144.8662058096366 / 1401.0150752344389 / 2002.938948746305` |
| `5643` | `141.11391660033576 / 1469.4385849395155 / 3840.5072987661697` |
| `10976` | `135.93492558486764 / 1330.3881630879202 / 8250.644568965072` |
| `16213` | `127.63665710590647 / 1256.9527613956354 / 12899.11724528065` |
| `22730` | `120.48241930243164 / 1128.9763236685953 / 20134.24033729825` |
| `30400` | `114.00353788462567 / 1028.1957534609096 / 29567.641104455106` |
| `32571` | `114.8486529751413 / 1001.687171893108 / 32517.333841737127` |

Source: `data/gemma4-26b-a4b-q8-b70-context-performance-profile-20260702.json`.

Target B: TP1/MTP3 short-profile cell, D `123.72736943965285`, T
`178.6938319564797`.

Source: `data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json`.

Proposed `lab-measured`, EVID B for the reconstructed deployment packet. Keep
the service-context profile separate from the short headline; MTP0/1/2/4 and
TP2/TP4 remain missing. Do not invent a zero-context point because Gemma's
first actual point is 741.

Import status: measured import.

### 9. MiniMax M2.7: classify operational context and prefill observations

Target A: TP4, MTP0, graph-on production-service observations:

- context `372/18924/32264`;
- D `96.82/77.89/63.91`;
- T `227/13085/23336`.

Source: `docs/minimax-production-c1-service.md`.

Proposed `lab-measured` operational cells, EVID C. These use different output
and workload classes, so render as discrete observations, never a connected or
controlled context curve.

Target B: exact prefill-only observations at context
`510/2036/8144/16288`: P `1607.9/1750.1/1830.3/1810.3`.

Source: `notes/2026-05-23-current-host-pcie4-prefill-check.md`.

Proposed `lab-measured`, EVID D prompt-processing characterization. The broader
deployable packet may retain a stronger separate grade; this narrow series does
not inherit it automatically.

Import status: measured import.

### 10. LFM2.5 2.6B: add exact TP1 context coverage and package zero point

Target: Q8_0, TP1, MTP0, F16 KV.

| Contexts | Exact decode values | Exact prefill values |
|---|---|---|
| `0/2K/4K/8K/16K/24K/32K` | `135.198135/131.259551/127.211224/120.195857/107.980065/98.138413/89.93812` | `9130.854812/4699.373204/4584.945629/4399.719712/3752.42491/3698.15006/2824.910192` |

Source: `repro/lfm25-26b-q8-b70/lfm25-26b-q8.sweep.json`.

Proposed `lab-measured`, EVID C. This is raw-engine context characterization,
not the language-quality gate; the clean-host beginner flow remains open. Add
the observed x=0 point to the package profile. TP2/TP4 remain missing.

Import status: measured import.

## Estimate blocker and next estimate candidates

No versioned estimate is currently publishable from tracked state:

- every family currently has an empty `estimates` array;
- the browser ML Bottleneck bridge loads a mutable remote SDK and evidence
  snapshot;
- there is no tracked estimate record containing the required engine version,
  frozen snapshot SHA-256, generation time, selectors, interval, basis
  measurement IDs, limitations, and `not_for_promotion=true` contract.

Therefore this backlog contains **zero publishable estimate values today**.
The live bridge must not be copied into family cells as if it were durable
evidence. First freeze and hash the engine plus evidence snapshot, generate a
tracked record, and validate it. After that, the best estimate candidates are
Qwen3.8 TP2/TP4 context for known-working target-only profiles, followed by
lower-value Nemotron/Gemma topology gaps. Do not estimate graph+MTP4 until the
exact current-head lane has at least a boot/correctness sentinel; the pinned
graph+MTP corruption evidence makes a speed-only estimate misleading.

## Ordered implementation batches

1. **Finish Qwen35 first.** Let the existing Qwen35 owner finish and validate
   its current work; fold rank 7 into that same ownership if it is not already
   covered. Do not concurrently edit `families/qwen-35b.json`.
2. **Then one Qwen27 owner.** After Qwen35 is finished, implement ranks 1, 2,
   4, and 5 sequentially in `families/qwen-27b.json` and the relevant package
   surfaces. Regenerate once after the combined source edit, preserving all
   historical values and exact selectors.
3. **Then Nemotron and Gemma.** Ranks 6 and 8 touch different family/package
   roots and may proceed in parallel with one owner per family. Validate their
   real zero/non-zero context origins independently.
4. **Then remaining families.** Implement rank 3 (Ornith), rank 9 (MiniMax),
   and rank 10 (LFM) with non-overlapping owners or sequentially. Keep aggregate
   engine sequences, operational observations, and raw context profiles as
   distinct workload classes.
5. Only after the measured-import batches are merged should an estimate owner
   freeze the projection engine/snapshot and propose versioned estimates.

Each implementation batch should update normalized source first, regenerate
derived pages, validate exact evidence links and values, run the family/package
test suites, and inspect the compact rendered gap output. No GPU run is needed
for any ranked import above.

# DeepSeek V4.1 Flash on six B70: speed strategy and scoreboard (started 2026-11-11)

Owner, 2026-11-11: "we've started to move at a crawl, trial and error optimization" ... "lets try to get token
decode rate to like 200 tok/s and much faster prompt processing." Use more helpers, more cards at once, older
code, other open-source projects, tools that predict speed without running, and big-picture changes. This file is
the plan, the idea list and the scoreboard of strategies (kept current; detailed evidence stays in the lane note
`2026-11-09-dsv41-device-load-host-memory.md`, sections cited as §N).

## Goal and the hard rule

- Answers (decode): 85 tok/s plain, 104-117 with guessing (§32) -> **200 tok/s**.
- Prompt reading: ~300 tok/s at 3K tokens (§28, §31) -> **much faster** (target 1,000+).
- **Lossless = bit-identical** to the current engine: the 3-step trace byte-identical to `runs/ab1/base.trc`, the
  40 / 128 / 256-token answers the same, guessing output the same as plain. Allowed: anything that computes the same
  floats in the same order (layout, scheduling, fusion, launch structure, overlap, proven-exact shortcuts with a
  fallback, guesses checked by the full model). Not allowed: reordered float sums without a proof, lower-precision
  activations (fp16 / bf16 / int8 activation quantization), rounding matrix units (TF32 / bf16 DPAS), any
  approximation.

## Where the time goes (start of this plan)

Card 2, answer steps, `OWN_GPROF=2` (§32; profiled step 13.7 ms, a real step 11.7 ms at 85 tok/s, so profiling
inflates the idle gaps):

| Part | ms per word | Best possible (rough) |
|---|---|---|
| Weight-reading kernels (experts, attention matrices, shared expert, head) | ~7.6 | ~3.1 for the whole step's bytes (1.69 GB per card per word at ~550 GB/s) |
| Small serial steps (norms, router, mix finish, engram, publish) | ~2.9 | well under 1 |
| Exchanges between cards (160 per word, ~13 us each) | ~2.1 | ~1 with fewer / overlapped exchanges |
| Attention core | ~1.1 | |

The cards read their weights at ~145 GB/s of ~600 (§28): the step is latency-bound (about 1,051 short launches per
card per word, each ramping up and tailing off; 160 waits on the slowest card; serial loops), not memory-bound.

What 200 tok/s needs: 5.0 ms per word plain, or ~6.8 ms plain (~148 tok/s) with guessing at today's ~1.35x. Either
way the weight reading must get close to the card's bandwidth and the exchanges and small steps must mostly hide.
That is a structural change, not more per-kernel polish.

Prompt reading: a 16-token block takes ~57 ms (§27). With each token's arithmetic fixed to the one-token order, the
ceiling is set by ALU work per weight-token (~4 instructions per weight and token in today's Q8_0 forms, §31 d2):
roughly 4x above today. Bigger blocks (weights read once per block), fewer instructions per weight-token and a
faster prompt attention are the levers.

## Guessing math (g82 logs: code / analysis / 3K prompts)

Per cycle today: 2.58 / 2.02 / 2.48 tokens (70-77 % of guesses kept, only ~1.3-1.8 guesses per cycle because the
adaptive count stops early), draft 2.2-2.3 ms + check 17-20 ms (1.5-1.7x a one-token step of 11.7 ms). tok/s =
tokens per cycle / (draft + check). For 200 tok/s at 2.6 tokens per cycle a cycle must cost ~13 ms (about one plain
step); at a 75 % keep rate, five guesses every cycle would give ~3.3 tokens per cycle (1 + 0.75 + ... + 0.75^5),
needing a cycle of ~16.5 ms. So the guessing route to 200 = a check of 5-6 tokens costing little more than a
one-token step (dense rows read once for all tokens already; the experts and per-token small steps are what grows)
+ a cheaper draft (2.2 ms = 11-13 % of a cycle) + the plain step itself faster.

## Method (replaces "take the top kernel and try variants")

1. **Budget first.** A time-vs-floor ledger for every kernel type and every part, on all six cards, including who
   waits for whom at each exchange (`b1` profiles, `tools/perf/` below). Rank by milliseconds recoverable. Rebuild
   after each batch.
2. **Fix categories, not kernels.** The biggest gaps are structural (launch count, exchange latency, weight reads
   that start only when the input is ready); one structural fix outweighs ten kernel polishes.
3. **Predict before running.** The machine-code census and floor model (`tools/perf/`) give a predicted time per
   kernel; the stall sampler (`tools/bench/pcs.hpp`) and the machine code explain a slow kernel before any variant
   is written; one hypothesis, one test.
4. **Six cards, six experiments.** One-card benches run on different cards at the same time (each A/B on its own
   card, so card-to-card clock differences do not matter); six-card runs only for gates and budgets.
5. **Batch the gates.** Several bench-proven exact changes go into one build and one gate campaign; short notes per
   lever, one full note section per batch.
6. **Read before inventing.** Other projects (llama.cpp SYCL / Vulkan, OpenVINO, IPEX-LLM, vLLM / SGLang custom
   all-reduce, Mirage / Hazy megakernels, DeepSeek's kernels) and our own older engines (the Qwen own runtime, the
   FP8 lanes) are searched for faster forms first.
7. **Value check.** Before a lever: the most it can win (its share of the budget) x the odds / hours. Under ~2 %:
   at most 30 minutes.
8. **Helpers.** Reading, surveys, tool building and bench scaffolding go to helper agents; decisions, GPU runs and
   engine edits stay in the main thread.

## Ideas (ranked by expected size; status in the scoreboard)

Structural (decode):
- S1. (CLOSED for the dense chain by pc1, see the scoreboard; may still matter for chains of tiny serial steps.)
  **Persistent layer kernels ("megakernel")**: one long-running kernel per layer phase (or per word) instead of
  ~26 launches per layer; each work-group loads its weight rows **before** waiting on the flag for its input, so
  weight reading overlaps the previous step's tail and the exchanges. Same arithmetic per output. First a one-card
  bench of one layer's dense chain: separate launches vs one persistent kernel with weights-first loads.
- S2. **Exchanges**: fewer per layer (merge, or compute redundantly where cheaper), overlapped with independent
  work, and cheaper inside a persistent kernel (no launch, flag wait overlapped with weight loads).
- S3. **Launch overhead without fusion**: recorded command lists / SYCL graph replay of a whole word; measure the
  real (unprofiled) launch tax first.
- S4. **Card balance**: who arrives last at each exchange; even the slow card (0000:e3 clocks lower, §26).

Guessing:
- G1. Cheaper checks (a block of 4 costs ~1.8x a one-token step, §21-24): with S1 the extra tokens of a check cost
  little more than their weight reads.
- G2. Better guesses: more tokens per round, tree guesses, acceptance by prompt class.

Kernels (only where the budget says a kernel is far from its floor):
- K1. One reusable proven-exact "fast serial sum" helper (bracket + fallback) for every remaining serial double
  chain (mix finish, compressor pool, ...). Done so far: norms (§32), engram gate (eg1-eg2 below).
- K2. Expert kernels: decode instructions per weight (IQ2 / IQ1 / IQ3 grids); compare llama.cpp / OpenVINO forms.

Prompt reading:
- P1. Blocks larger than 16 tokens (weights read once per block), per-shape kernel forms from the predictor.
- P2. Instructions per weight-token (d2-d4 in §31): fewer converts / moves per weight.
- P3. Prompt attention and the index work at long context (§29-31).

## Scoreboard: strategies that worked, and ones that did not

Worked (all bit-identical):
| Strategy | Example | Gain |
|---|---|---|
| Replace serial loops by a proven bracket with a fallback | norm sums 14.9 -> 8.2 us (§32); engram gate 96 -> 8.7 us (eg2), 116 -> 12 us in the engine (§33) | +2.9 % (norm), ~+1 % (engram) |
| Spread serial work over more cores | norm launches 16 -> 4 rows per group (§32) | +1.7 % |
| Fewer comparisons, no branches in selection | router pick 21.4 -> 9.2 (§32) -> 2.7 us (rp3, branch-free, fixed candidate count); router launch 12.8 -> 10.9 us in the engine (§33) | +3.3 % (§32), ~+1 % (§33) |
| Stall sampler before variants | pcs1 (2026-11-11): production IQ2_XXS experts busy 48 % + ALU-pipe 22 % + send queue 17 % (issue-bound); the packed-lane form waits a third of its samples on block-start loads, which says exactly what to fix | saves the variant sweep |
| Riders: independent small work inside a big launch | mix dots in the norm launch, shared rows with the router (§14-18) | several % |
| Packed weight rows for sub-group block loads | §p7-p10 era, 9 -> 28 tok/s | large |
| Pull exchanges for big slices, push for tiny ones | prompt 91 -> 179 tok/s (§21) | large |
| Keep idle cards warm | 5.3 -> 9.1 tok/s (early) | large |
| Ahead-of-time build + large register mode | first run 6 min -> 30 s; fewer spills (§23, §26) | small |

Did not work (and why):
| Strategy | Why |
|---|---|
| S1 as stated: one persistent kernel for the dense weight chain (pc1, 2026-11-11, `tools/bench/bench_persist_chain.cpp`) | separate launches already run a 16-layer x 6-stage Q8_0 chain (35.3 MB per layer, 12-head card shapes) at 74.1 us per layer = 475 GB/s, 79 % of the 603 GB/s measured read floor; persistent forms with 16 / 32 / 64 work-groups of 512 were 166 / 108 / 95 us per layer (too few loads in flight), reading the next rows early made it worse (154-371 us), 128 work-groups are not all resident (waits gave up safely). Launch gaps between dependent GEMVs are ~1 us on B70, not the problem. The engine's same matrices cost ~130 us per layer (card 2 profile: q_a + q_b + o_a + o_b + shared + router groups): the extra is in riders, small steps and launch structure inside those groups, not in launching. |
| S3 / PDL emulation: launches on an out-of-order queue with no barriers, each kernel loading its weights then spinning on a counter (pc2, `bench_persist_chain` forms Q / Qi, 2026-11-11) | 215 / 184 us per layer against 74 for plain launches: one counter per stage, incremented by every sub-group, serializes the atomics; and there is little to win: `bench_launch_gap` (lg1) shows back-to-back dependent 6 us launches leave 0.12-0.28 us between them (an empty kernel costs ~1.6 us per launch). Launch gaps between big kernels are not where the 1.1 ms of idle time is. |
| K2 as packed logical lanes for IQ2_XXS (`RoutedIQ2XXSK<NB, P, STAB, PF, XB>`, kb1-kb3 + pcs1/pcs1b, 2026-11-11) | every form bitwise PASS (18,432 gate+up and 20,736 down outputs), every form slower: gate+up production 33.4 us, P = 4 35.5, P = 8 58, P = 2 42-50; loading the next block early (PF) 40.5 / 68, the block's x up front (XB) 42.3, sign masks from a table (STAB) 41.8-49.3. The machine code has ~14-30 % fewer instructions per weight, but an item needs P x values per group that the one-weight form gets from one shared block read, so it either waits on per-lane x loads (sampler: a third of samples SbidStall on the multiply that consumes x) or holds them in registers and falls to the 256-register mode with half the threads. Production is issue-bound (busy 48 %, ALU pipe 22 %, send queue 17 %); the 3 float ops per weight are fixed by the order. Revisit only with x permuted by its producer so a block read hands each item its own P values. |
| L1 transport: one shared native Level Zero context over the six cards (SC117's setup) for direct peer stores (`tools/bench/probe_shared_ctx_ram.cpp`, `tools/bench/xchg_direct_bench.cpp`, `data/.../round19-l1-transport/`, 2026-11-11) | safe but no faster. Host RAM: 6.02 GiB on six cards in one shared context moved MemAvailable by 0.05 GiB (also with peer residency, and with the default backing; peer copies correct), so the 1:1 host-RAM cost of §1 is the SYCL multi-card context, not Level Zero. Speed: the shared context and today's IPC peers give the same times to 0.1 us (pair one-way 0 B 2.36 vs 2.42 us, 3,456 B 5.20 vs 5.21, 9,728 B 6.38 vs 6.36). The fabric sets the cost: a flag one way ~2.4 us, a 3.4-9.7 KB push one way 5.5-5.7 us with 4+ work-groups; a six-card all-gather by push 10.5-14 us at 3.5-9.7 KB per card (noisy), against 11.89-13.53 us for the engine's own XchgPull of the one-token h exchange (e81b) and 12.2 us in the step ledger; all-to-all pushes of 64 KB collapse to ~9 GB/s total (208 us) while pulls keep 73 GB/s. The engine already pushes the tiny exchanges. What is left for exchanges: fewer of them (merge) or hide them behind weight reads. |
| Trusting one-card bench winners blindly | Q8_0 5120 / 4096-column forms lost inside the engine (riders, fewer rows, §31) |
| L2 prefetch riders | a launch ends only when its prefetch groups do (§15-18) |
| Fused softmax into the attention output | slower (§31 s6) |
| Row-block-free head | the 230 W cards drop clocks (§24-25) |
| Split checks / draft across card pairs | each pair exchange costs more than it saves (§28) |
| Trial-and-error variant sweeps | slow; the stall sampler or machine code answers in one run |

## Work in flight (2026-11-11, updated ~02:05)

- Done: g83 gate (router branch-free + engram gate over 16 sub-groups, §33): 85.2 -> 86-87 tok/s, bit-identical.
- Done: the ledger (`2026-11-11-dsv41-step-budget.md`), our older code and other projects
  (`2026-11-11-dsv41-ideas-local.md`), the prompt-reading plan (`2026-11-11-dsv41-prefill-plan.md`).
- K2 expert kernels, packed logical lanes (`tools/bench/bench_routed_m1.cpp` `RoutedIQ2XXSK<NB, P, STAB, PF>`): v1
  bitwise PASS (18,432 pair outputs, 20,736 down) but slower (P = 8: 58 us, P = 4: 35.5 against production 33.5);
  stall samples show block-start load waits; v2 loads block blk + 1 while computing blk (running).
- Found (gs1, `tools/bench/bench_grf_switch.cpp`, `round19-gs1-grf-switch-card3/4.txt`): **a 256-register kernel
  between 128-register kernels costs ~2.9 us extra** (host clock; profiling gap 1.10 vs 0.12 us per launch): a
  2.1 MB Q8_0 step followed by a tiny step is 6.86 us per pair with the tiny step at 128 registers and 9.80 us at
  256. Local memory size changes cost nothing. In the plain step only `SparseSoftmaxPN` (38 per step) runs at 256
  registers: ~0.11 ms per step (~1 %), fix = build it for 128 registers (or slim it). Checks and prompt blocks have
  many more 256-register kernels (83 of 180 in `bench_dense_m16`'s dump): count the mode changes per block there.
  Also seen: a chain of tiny kernels alone runs at ~2.0 us per launch (the card's launch rate), while a tiny
  kernel right after a 6 us kernel adds only ~0.8 us (its setup overlaps the long kernel).
- Found (ad1-ad4, `tools/bench/bench_attn_dec.cpp`, card 3, 2026-11-11 ~02:00): the one-token attention's score +
  softmax per layer runs **13.8 -> 6.1 us** at short lists (n = 160) and 13.1 -> 10.8-11.0 us at 640 slots, every
  output bit-identical: (a) `SparseScoreHG<512, 1>` instead of `<512, 4>` (4x the sub-groups, the same per-(head,
  slot) sum; 7.1 -> 4.2 us at n = 160); (b) the trimmed lists' softmax as `SparseSoftmaxP<n>` built for each slot
  count (n = 160 ... 608) instead of `SparseSoftmaxPN<640>{n}`: 128 registers, 3.9 -> 1.7 us, and no register-mode
  change around it (the chain saves another ~2.8 us, as gs1 predicted). The "bit-mask" slim form tried first still
  built at 256 registers (flag spills) and was dropped; a lean runtime-loop form is 128 registers but slower at 640.
  In the engine as `OWN_ATT_HG=1 OWN_ATT_PK=1` (opt-in, tp86; gate tg86 queued). Expected ~0.29 ms per step at
  short context (~2.5 %), ~0.08 ms at 3K+. Lesson: check the register mode in the dump before calling a fix done.
- Found (tl85, `OWN_TIMELINE` on tp85 = tp84 + the timeline patch, answer steps 20-27 of prompt 1, all six cards,
  `data/dsv41-bringup-20261109/round19-tl85-timeline/`; device clock only, since the host/device clock mapping came
  out implausible and the copies carry no profiling times): per card and step **busy 10.75 ms, idle inside the
  step 0.47 ms, idle between steps 0.44 ms** (of which ~0.28 ms was the timeline's own per-step clock calibration:
  six cards x four 12.5 us brackets; now done at the window's edges only). Inside the step: **~0.26 ms are
  register-mode changes**: the pull exchange kernel (the `xchg()` lambda, 83 per step) is built at 256 registers,
  so every exchange is entered and left with a ~1 us device gap (166 per step), and `SparseSoftmaxPN` adds 76 more;
  every other launch follows its predecessor by ~0.12 us. The rest: the engram rows' uploads (`EngRowsA` waits
  2 x 42 us per step: the host's row reads come after layer 0's launches) and the pre-mix copy (`HcPreA`, 3 x 8.6
  us). Fix in hand: `OWN_XPULL_GRF=128` (`XPullK128`, the same code pinned to 128 registers; 256 bytes of spill,
  `tools/perf/xpull_grf_tu.cpp`) for tp87. Exchanges in the profile: XchgPull 16.5 us x 83 + XchgP 6.35 us x 80
  = 1.88 ms per step (17 %).
- Done: S2 transport L1 (shared native context, direct stores): safe for host RAM, but no faster than today's
  setup; closed (scoreboard). Exchanges can only shrink by merging or hiding them.
- Gaps: a per-launch timeline on all cards + who waits for whom (`OWN_TIMELINE`, `OWN_XWAIT`; helper writing the
  patch) - the 1.1 ms between kernels is not launch cost (lg1), so it must be waits or host-side delays.
- Prompt: the plan's first steps (decode each shared weight once per 8-16 tokens; 64-token steps; measure the
  distinct experts per step first).

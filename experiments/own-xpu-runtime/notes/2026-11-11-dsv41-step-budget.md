# DeepSeek V4.1 Flash on six B70: the step budget, time against floor (2026-11-11)

The strategy note's method step 1 (`2026-11-11-dsv41-speed-strategy.md`) asks for a ledger before any more kernel
work. This note is that ledger. It was built from the b1 profiles: the answer steps of all six cards on tp82, with the
committed defaults. The tool is `engine/tools/perf/dsv41_step_budget.py` (how it works: `engine/tools/perf/BUDGET.md`).
The tables in the second half of this note are its output, unedited.

## Outcome in plain words

- **One answer step takes 11.7 ms today (85 tok/s).** Suppose each card read every byte it needs exactly once, at
  full memory speed (550 GB/s). The slowest card would then need **4.7 ms (213 tok/s)**; the other four cards would
  need 4.0 ms. So 200 tok/s is just inside what the memory allows, and only if almost everything except reading
  disappears or hides behind the reading.
- **Where the 7 ms above the floor goes** (mean card, ms per step):

  | part | today | floor | above floor |
  |---|---|---|---|
  | routed experts (gate+up, down) | 2.88 | 0.77 | **2.11** |
  | idle gaps between kernels (real step - kernel sum) | 1.10 | 0 | **1.10** |
  | small serial ops (norms, mix, engram gate, swiglu, ...) | 1.39 | 0.33 | **1.06** |
  | dense matrices (q_a/kv, q_b, output-a/b, router, shared, head) | 4.09 | 3.08 | **1.01** |
  | attention at short context (score, softmax, output) | 0.86 | 0.03 | **0.82** |
  | exchanges (163 per step) | 1.41 | 0.61 | **0.80** |

- **Three findings that change the plan.**
  1. **The dense matrices are already close to the floor.** q_a + kv runs at 500 GB/s, output-b at 470, output-a and
     the router at about 450, and the head at 572 (it beats the 550 floor). Kernel polish on them can win only
     about 1 ms in total. **The routed experts run at 16-34 % of the floor speed** (IQ1_S gate+up at 90 GB/s), so
     they hold the largest kernel-level gap: 2.1 ms.
  2. **Every card reads 713 MB per step that every other card also reads** (q_a + kv 8.3 MB, the router 3.9 MB and
     the stream-mix rows 2 x 2 MB, per layer). That is 1.3 ms of the 4.7 ms floor. Splitting these reads six ways
     lowers the floor by 1.08 ms, but each split needs its own all-gather (~12 us each today, 40 per step per
     matrix). It pays only once exchanges are cheap or merged.
  3. **The pull exchanges cost 12.2 us each, the same as an idle bench where all cards arrive together** (e81b:
     11.9 us). So most of their cost is the two PCIe round trips, not waiting for a slow card. Making them faster
     means fewer exchanges, one round trip instead of two, or hiding them behind weight reads (strategy S1/S2).
     Polishing the exchange kernel will not help.
- **The cards are not balanced.** Cards 2 and 5 hold two attention groups (16 heads) in one-token steps, so they
  read 0.38 GB more per step: +0.7 ms floor and +0.7 ms busy time. Yet their exchange time is not lower than the
  others', so the simple story "everyone waits for card 2" is not what the data shows. Finding out who waits for
  whom needs the new `OWN_XWAIT` diagnostic below.
- **Prompt reading** comes from the older e80 profiles (tp66), because the b1 prompt logs have no profile (see
  "b1 prompt logs" below). A 16-token block takes about 63 ms profiled. Its floor is 14.8 ms (about 1,080 tok/s).
  The floor is dominated by reading about 80 distinct experts per layer per block, which is 10 ms on its own.
  Bigger blocks are therefore the prompt lever. With uniform expert picks (an upper bound on how many distinct
  experts a block reads), the floor rises from 1,020 tok/s at 16 tokens to 1,290 at 64, 1,600 at 128 and 1,840 at
  256. The dense prompt kernels run at about 1/5 of the FMA peak (q_a 4.8 ms against 0.8, q_b 3.8 against 0.7),
  exchanges take 7.9 ms per block, and gaps 8.5 ms.

## Top recoverable items, answer step (ms per step above the floor, mean over the six cards)

| # | item | ms | what would recover it |
|---|---|---|---|
| 1 | idle gaps between kernels (1,051 launches per step) | 1.10 (c1 1.54) | fewer launches; a persistent layer kernel (S1); a recorded or graph replay of the step (S3) |
| 2 | XchgPull, 83 per step at 12.2 us | 0.66 | one round trip instead of two (data and flag together), merging exchanges, hiding them behind weight reads |
| 3 | routed gate+up, IQ2_S (15 layers), 51 us against 13.9 | 0.56 | expert kernel decode work per weight (K2); weights loaded before the input is ready |
| 4 | routed gate+up, IQ1_S (10 layers), 52 us against 8.5 | 0.44 | the same; IQ1_S runs at 16 % of floor speed, so decode work dominates, not bytes |
| 5 | routed gate+up, IQ2_XXS (15 layers), 35 us against 11.9 | 0.36 | the same |
| 6 | 5,120-wide norm + mix dots, 77 per step, 8.1 us against 3.8 | 0.33 | the norm's serial chain sets the launch time; the dots' 2 MB read alone would take 3.6 us |
| 7 | routed down, IQ2_S (15 layers), 28 us against 7.1 | 0.32 | as 3 |
| 8 | attention score, 38 per step, 8.4 us | 0.31 | one fused attention launch per layer (score + softmax + output) at short context |
| 9 | routed down, IQ3_XXS (15 layers), 25 us against 8.4 | 0.26 | as 3 |
| 10 | engram gate, 2 per step at 116 us | 0.24 | **already in hand**: eg2 (16 sub-groups, 96 -> 8.7 us in the bench), waiting for the next batch gate |
| 11 | attention softmax, 38 per step, 5.4 us | 0.21 | as 8 |
| 12 | attention output, 40 per step, 5.3 us | 0.20 | as 8 |
| 13 | q_a / kv norms, 40 per step, 4.0 us | 0.16 | riders, or fold into q_b's launch |
| 14 | router pick + shared gate/up, Q8_0 layers, 12.7 us against 7.6 | 0.14 | partly in hand: rp3 (router launch 11.8 -> 9.7 us) |
| 15 | XchgP pushes, 80 per step at 4.9 us | 0.14 | as 2 |

Grouped by what a single change would address: routed expert kernels 2.11 ms, small launches (attention, norms,
riders, gate) about 1.9 ms, exchanges 0.80 ms, gaps 1.10 ms. Structural levers (they move the floor itself):
splitting the replicated reads (-1.08 ms of floor), splitting heads 12/12/12/12/8/8 in one-token steps too (-0.34
ms on the slowest card's floor, costs 40 pair exchanges per step), and hiding exchanges and gaps behind weight
reads (up to 2.5 ms, the persistent-kernel rewrite).

What this means for the 200 tok/s plan (5.0 ms per step):
- It is not reachable with today's launch structure. The time today outside weight reading (gaps, exchanges,
  small ops, attention) is 4.8 ms. With every one of today's 1,051 launches kept, the small ops and the attention
  alone cannot go below 1.3 ms (each launch costs at least 2.2 us), and the exchanges cannot go below 0.6 ms.
- The order the budget suggests:
  1. The persistent layer kernel (S1). It attacks gaps, exchanges and small launches together, about 4.8 ms of
     non-reading time.
  2. The expert kernels (K2), 2.1 ms.
  3. Splitting the replicated reads, once exchanges are cheap, 1.1 ms of floor.
  4. Head balance, 0.3-0.7 ms.

## What the profiles cannot show (instrumentation the engine lacks)

1. **Who arrives last at each exchange.** The exchange kernels spin on flags. Their duration mixes PCIe cost with
   waiting, and nothing records which peer a card waited for. **`engine/tools/perf/dsv41_xwait.patch`** adds this
   (see below).
2. **All six cards in one run.** `OWN_GPROF_CARD` profiles one card per run, so the six per-card tables come from six
   runs with different step times (12.95-14.17 ms). The profiled card's barriers (one per mark, 696 per step)
   inflate its step by 1.2-2.5 ms and can change who waits for whom.
3. **Per-launch start/end timestamps.** The profile keeps sums per kernel type only. Placing a gap (the host was late
   to submit, a dependency, or a copy) needs the launch-by-launch timeline. `kev()` already holds the events.
4. **The host side of the step.** `OWN_TP_HOSTPROF` gives busy and blocked time per card thread, but not when each
   launch was submitted relative to when the card became idle.
5. **Distinct experts per prompt block.** The prompt floor depends on it. `OWN_MT_IDSTAT=1` exists (card 0, with
   waits) but has not been run on the 3K prompt. The ledger assumes 80 per (block, layer).
6. **Clocks per card during the step.** The telemetry sampler runs at 50 ms. Card 2 or 5 clocking lower would look
   like extra kernel time.
7. **b1 prompt logs.** `pre_c*.log` ran with one answer token. `own_run_v41` then runs no answer step, so
   `n_prof = 0` and no profile is printed. The prompt ledger needs these runs repeated with **2 answer tokens**
   (as e77/e80 did). The kernel tables then hold the whole read plus one step.

## The diagnostic patch: `OWN_XWAIT` (`engine/tools/perf/dsv41_xwait.patch`)

The patch is env-gated and records nothing when the variable is unset. It was made against the working tree of
2026-11-11 00:47 and `git apply --check` passes. **It is not compiled or run**, because this helper had no GPU and
no compile access.

- `XchgP` and `XchgPull` get two members, `xw` (null = off) and `xk`. When `xw` is set, each waiting item `t` stores
  two numbers in slot `xk` of the card's per-step ring: the spin loads until peer `t`'s flag arrived (0 = the peer
  was there first) and the sub-group clock ticks it waited (`sycl::ext::oneapi::experimental::clock`, the same call
  packet194's `OWNRT_TP_EXCHANGE_STATS` used on these cards). `XchgPull` records in work-group 0 only.
- The backend sets `xw` and `xk` in `xchg()` for every waiting exchange (mode 0 or 2). It labels each exchange as
  layer x 100 + phase x 10 + part, resets the ring at the start of `tp_card_step`, and copies it back after the
  step's last wait. It appends `xw <step> <card> <k> <label> <spins x6> <ticks x6>` to `$OWN_XWAIT`. Only one-token
  steps are recorded. The prompt blocks' `XchgPair` and the draft are left out, to keep the patch small.
- Cost when on: one 16 KB device-to-host copy per card per step, plus a clock read around each wait.
- Analysis: `dsv41_step_budget.py --xwait FILE [--xw-mhz MHZ]`. For each exchange type (output-a, output-b,
  expert activations, FFN rows, engram) it prints which card arrived last and how often, and the wait per card per
  step. It was tested on synthetic records only. The tick rate (`--xw-mhz`, default 2400) is not calibrated; check
  it against the exchange kernel times of a profiled run.
- Suggested first use: `OWN_XWAIT=/tmp/xw.txt` on the plain 128-token run, without `OWN_GPROF`, so all cards run
  unprofiled. Then compare it with an `OWN_GPROF=2` run to see how much the profiling barriers change the pattern.

## How the bytes were modelled

The bytes are modelled from the GGUF headers (40 layers, 1,043 tensors, shapes and quant types) and the engine's
own slicing (`tp_rows`, `tp_setup`, `head_layout`, `pk41::packed_row_bytes`). The tool rebuilds the launch
sequence of `tp_card_step` and checks the launch count of every kernel type against the profile. All 52 kernel
types on all six cards agree within 0.6 launches per step. The one difference is c5's `HcPostPreP`, 77.3 against
78, which is rounding in the profile.

Caveats:
- The floor bandwidth is a parameter. At 600 GB/s the step floor is 4.30 ms (233 tok/s) and the 16-token block
  floor 13.9 ms.
- "gaps, real" assumes the kernels take as long with profiling as without it.
- Attention bytes are those of a short context (about 59 positions). Long documents need their own ledger, made
  from the x19k/x69k profiles.
- The prompt section uses tp66 (e80), which reads at about 250 tok/s profiled. tp82 reads 258-263 profiled and
  about 293-300 unprofiled.

Reproduce (CPU only, about 0.2 s):

```bash
cd /home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine/tools/perf
python3 -I dsv41_step_budget.py --runs /home/steve/dsv41-work/runs/b1 --md ledger.md --json ledger.json
```

---

## Ledger (generated by `dsv41_step_budget.py`, b1 run, defaults)


Model: 6 GGUF headers in `/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/UD-IQ2_XXS` (1043 tensors). Slicing (OWN_TP=6): expert/shared mid rows [384, 384, 384, 384, 384, 384]; model rows [848, 848, 864, 848, 848, 864]; vocab rows [21536, 21552, 21552, 21536, 21552, 21552]; heads per card for one token [8, 8, 16, 8, 8, 16], for prompt blocks [12, 12, 12, 12, 8, 8].

### Answer step (one token), 6 cards profiled

Real step (unprofiled, `plain.log`): **11.73 ms** (85.3 tok/s). Profiled walls: c0 13.28, c1 12.95, c2 14.17, c3 13.49, c4 13.87, c5 14.05 ms.
Context for the attention bytes: 59 positions. Floors: weights/activations at 550 GB/s; exchanges 2.5 us sync + bytes at 25 GB/s; standalone launch 2.2 us.

| card | weight bytes / step | activation bytes | link bytes | weight floor ms | all-bytes floor ms | kernels ms | launches |
|---|---|---|---|---|---|---|---|
| 0 | 2.13 GB | 60.81 MB | 4.99 MB | 3.87 | 3.98 | 10.29 | 1051 |
| 1 | 2.13 GB | 60.90 MB | 5.00 MB | 3.87 | 3.99 | 10.19 | 1051 |
| 2 | 2.51 GB | 64.67 MB | 4.86 MB | 4.57 | 4.69 | 11.21 | 1051 |
| 3 | 2.13 GB | 60.71 MB | 5.00 MB | 3.87 | 3.98 | 10.41 | 1051 |
| 4 | 2.13 GB | 60.79 MB | 5.00 MB | 3.87 | 3.98 | 10.45 | 1051 |
| 5 | 2.51 GB | 64.61 MB | 4.86 MB | 4.57 | 4.69 | 11.19 | 1051 |

Replicated reads (every card reads the whole tensor each step): 712.84 MB per card (1.30 ms at the floor): q_a + kv 331.99 MB; router 157.29 MB; hc_ffn_fn 78.64 MB; hc_attn_fn 72.74 MB; compressor 36.70 MB; q_a + kv + hc_attn_fn 35.14 MB; indexer attn_k 327.7 KB.

#### Per kernel type (ms per step, mean over cards; us/launch and floor ranges over the cards)

| kernel | role | cat | launches | us/launch (min-max) | ms/step mean | bytes/launch (c0) | floor us | floor ms | gap ms (mean) | GB/s (c0) |
|---|---|---|---|---|---|---|---|---|---|---|
| `XchgPull` | exchange (pull) | exchanges | 83.0 | 11.00-13.30 | 1.015 | 43.8 KB | 4.17-4.25 | 0.351 | 0.664 | - |
| `RoutedIQ2SP<20u, ActF32, NoRows>` | routed gate+up | weights | 15.0 | 50.46-51.68 | 0.767 | 7.63 MB | 13.88 | 0.208 | 0.559 | 151 |
| `RowsP<RowsPair<NormRows<5120u, 4u>, HcDotsRows<5120u, 8u> > >` | norm + mix dots | small serial ops | 76.9 | 8.03-8.25 | 0.626 | 2.11 MB | 3.84 | 0.295 | 0.331 | 262 |
| `RoutedIQ2XXSP<20u, ActF32, NoRows>` | routed gate+up | weights | 15.0 | 34.56-36.68 | 0.534 | 6.53 MB | 11.87 | 0.178 | 0.356 | 189 |
| `RoutedIQ1SP<20u, ActF32, true, NoRows>` | routed gate+up | weights | 10.0 | 52.02-53.12 | 0.526 | 4.68 MB | 8.52 | 0.085 | 0.441 | 90 |
| `RowsP<RowsPair<RowsPair<HcFinishRows, RopeRows<ActF32> >, DenseRows...` | q_b | weights | 27.0 | 15.43-23.54 | 0.492 | 5.59 MB | 10.17-20.33 | 0.366 | 0.126 | 360 |
| `RowsP<RowsPair<NoRows, RowsPair<DenseRows<GemvQ8P<160u, ActF32> >, ...` | q_a + kv | weights | 24.0 | 19.61-19.73 | 0.472 | 9.78 MB | 17.77 | 0.427 | 0.045 | 498 |
| `GemvH16P<160u, ActF32>` | router logits + compressor | weights | 47.0 | 9.15-9.25 | 0.433 | 4.15 MB | 7.54 | 0.355 | 0.078 | 453 |
| `GemvQ8P<256u, ActF32>` | output-b | weights | 27.0 | 15.84-16.14 | 0.431 | 7.42 MB | 13.49-13.74 | 0.366 | 0.065 | 466 |
| `RoutedIQ2SP<9u, ActF32, NoRows>` | routed down | weights | 15.0 | 27.79-28.79 | 0.425 | 3.90 MB | 7.09-7.23 | 0.107 | 0.318 | 140 |
| `XchgP` | exchange (push) | exchanges | 79.9 | 3.71-6.81 | 0.390 | 17.0 KB | 3.18 | 0.255 | 0.135 | - |
| `RoutedIQ3XXSP<9u, ActF32, NoRows>` | routed down | weights | 15.0 | 25.21-26.09 | 0.386 | 4.63 MB | 8.43-8.58 | 0.127 | 0.258 | 184 |
| `GemvQ8P<128u, ActF32>` | output-a | weights | 27.0 | 10.19-18.14 | 0.348 | 4.48 MB | 8.14-16.28 | 0.293 | 0.055 | 435 |
| `RoutePRows<RowsPair<HcFinishRows, RowsPair<DenseRows<GemvQ8P<160u, ...` | route pick + shared gate/up | weights | 27.0 | 12.58-12.82 | 0.342 | 4.20 MB | 7.64 | 0.206 | 0.135 | 332 |
| `SparseScoreHG<512u, 4u>` | attention score | attention | 37.9 | 8.39-8.50 | 0.321 | 203.1 KB | 0.37 | 0.015 | 0.307 | - |
| `EngramGateP` | engram gate | small serial ops | 2.0 | 116.17-128.64 | 0.238 | 348.2 KB | 0.63 | 0.001 | 0.236 | - |
| `RowsP<RowsPair<NoRows, RowsPair<DenseRows<GemvQ6KP<20u, ActF32> >, ...` | q_a + kv | weights | 13.0 | 17.44-17.61 | 0.228 | 7.57 MB | 13.76 | 0.179 | 0.049 | 434 |
| `RowsP<RowsPair<RowsPair<HcFinishRows, RopeRows<ActF32> >, DenseRows...` | q_b | weights | 13.0 | 14.65-21.85 | 0.223 | 4.35 MB | 7.90-15.80 | 0.137 | 0.086 | 297 |
| `SparseOutJC<512u, 16u, 128u, 16u>` | attention output | attention | 40.1 | 5.34-5.61 | 0.217 | 200.6 KB | 0.36 | 0.015 | 0.202 | - |
| `SparseSoftmaxPN<640>` | attention softmax | attention | 37.9 | 5.43-5.80 | 0.210 | 11.3 KB | 0.02 | 0.001 | 0.209 | - |
| `GemvQ6KP<32u, ActF32>` | output-b | weights | 13.0 | 14.87-15.15 | 0.196 | 5.73 MB | 10.43-10.62 | 0.136 | 0.059 | 386 |
| `GemvQ6KP<16u, ActF32>` | output-a | weights | 13.0 | 12.23-19.75 | 0.193 | 3.46 MB | 6.29-12.59 | 0.109 | 0.084 | 283 |
| `GemvQ8P<72u, ActF32>` | shared down | weights | 27.0 | 6.21-6.32 | 0.169 | 2.09 MB | 3.80-3.87 | 0.103 | 0.066 | 336 |
| `RowsP<RowsPair<NormRows<1280u, 4u>, NormRows<512u, 2u> > >` | q_a/kv norms | small serial ops | 40.0 | 4.03-4.13 | 0.164 | 21.5 KB | 0.04 | 0.002 | 0.162 | - |
| `GemvQ6KP<20u, ActF32>` | head | weights | 1.0 | 158.52-160.49 | 0.159 | 90.73 MB | 164.96-165.09 | 0.165 | -0.006 | 572 |
| `RoutePRows<RowsPair<HcFinishRows, RowsPair<DenseRows<GemvQ5KP<20u, ...` | route pick + shared gate/up | weights | 13.0 | 11.72-12.00 | 0.155 | 2.73 MB | 4.96 | 0.065 | 0.090 | 233 |
| `RoutedIQ2XSP<9u, ActF32, NoRows>` | routed down | weights | 6.0 | 25.20-25.95 | 0.154 | 3.49 MB | 6.35-6.47 | 0.038 | 0.116 | 139 |
| `HcPostPreP<ActF32>` | stream post+collapse | small serial ops | 78.0 | 1.20-1.28 | 0.096 | 204.8 KB | 0.37 | 0.029 | 0.067 | - |
| `GemvQ6KP<24u, ActF32>` | engram kv | weights | 2.0 | 45.82-46.15 | 0.092 | 21.49 MB | 39.08-39.22 | 0.078 | 0.014 | 469 |
| `WindowAppendP<ActF32>` | window append | attention | 39.9 | 2.02-2.16 | 0.085 | 3.8 KB | 0.01 | 0.000 | 0.085 | - |
| `GemvQ5KP<9u, ActF32>` | shared down | weights | 12.9 | 6.23-6.49 | 0.082 | 1.36 MB | 2.47 | 0.032 | 0.050 | 216 |
| `RowsP<RowsPair<HcDotsRows<5120u, 8u>, RowsPair<DenseRows<GemvQ8P<16...` | q_a + kv + mix dots | weights | 3.0 | 23.56-24.05 | 0.071 | 11.82 MB | 21.50 | 0.064 | 0.007 | 502 |
| `RoutedIQ2XXSP<9u, ActF32, NoRows>` | routed down | weights | 3.0 | 20.86-21.36 | 0.063 | 3.33 MB | 6.06-6.17 | 0.018 | 0.045 | 159 |
| `MoeCombineA<ActF32>` | moe combine | small serial ops | 40.3 | 1.44-1.51 | 0.059 | 27.1 KB | 0.05 | 0.002 | 0.057 | - |
| `CompressPoolP<ActF32>` | compress pool | small serial ops | 1.5 | 36.65-37.18 | 0.055 | 8.2 KB | 0.01 | 0.000 | 0.055 | - |
| `SwigluBothS<ActF32>` | swiglu | small serial ops | 40.0 | 1.08-1.10 | 0.044 | 32.3 KB | 0.06 | 0.002 | 0.041 | - |
| `RowsP<RopeRows<ActF32> >` | q rope | small serial ops | 39.8 | 0.88-0.92 | 0.036 | 4.1 KB | 0.01 | 0.000 | 0.035 | - |
| `RmsNormPS<5120u, 4u>` | norm | small serial ops | 4.0 | 7.36-7.57 | 0.030 | 61.4 KB | 0.11 | 0.000 | 0.029 | - |
| `RoutedQ2KF<9u>` | routed down | weights | 1.0 | 22.48-23.49 | 0.023 | 3.92 MB | 7.13-7.26 | 0.007 | 0.016 | 174 |
| `SparseScoreP<512u>` | attention score | attention | 1.9 | 6.16-6.36 | 0.012 | 151.6 KB | 0.28 | 0.001 | 0.012 | - |
| `RmsNormA<ActF32>` | norm | small serial ops | 2.5 | 3.37-3.82 | 0.009 | 1.5 KB | 0.00 | 0.000 | 0.009 | - |
| `GemvH16P<16u, ActF32>` | indexer k | weights | 2.7 | 2.89-3.12 | 0.008 | 133.1 KB | 0.24 | 0.001 | 0.007 | 44 |
| `CidxFill` | index fill | attention | 7.6 | 0.79-0.80 | 0.006 | 2.0 KB | 0.00 | 0.000 | 0.006 | - |
| `PubAppendA<ActF32>` | publish append | small serial ops | 2.6 | 2.15-2.43 | 0.006 | 3.8 KB | 0.01 | 0.000 | 0.006 | - |
| `ArgmaxP1O` | argmax | small serial ops | 1.0 | 4.93-5.10 | 0.005 | 86.1 KB | 0.16 | 0.000 | 0.005 | - |
| `ToF32A<ActF32>` | to f32 | small serial ops | 6.4 | 0.77-0.86 | 0.005 | 4.1 KB | 0.01 | 0.000 | 0.005 | - |
| `RopePairsA<ActF32>` | rope pairs | small serial ops | 4.8 | 0.82-0.91 | 0.004 | 4.6 KB | 0.01 | 0.000 | 0.004 | - |
| `EngRowsA<ActF32>` | engram rows decode | small serial ops | 1.9 | 2.12-2.15 | 0.004 | 28.8 KB | 0.05 | 0.000 | 0.004 | - |
| `SparseSoftmaxP<128>` | attention softmax | attention | 2.1 | 1.81-2.17 | 0.004 | 8.2 KB | 0.01 | 0.000 | 0.004 | - |
| `HcPreA<ActF32>` | stream collapse | small serial ops | 3.3 | 1.18-1.23 | 0.004 | 102.4 KB | 0.19 | 0.001 | 0.003 | - |
| `HcPostP<ActF32>` | stream post | small serial ops | 2.1 | 1.32-1.40 | 0.003 | 184.3 KB | 0.34 | 0.001 | 0.002 | - |
| `RmsNormPS<512u, 2u>` | norm | small serial ops | 0.9 | 2.20-2.46 | 0.002 | 6.1 KB | 0.01 | 0.000 | 0.002 | - |

#### Per role (all kernel types of a role summed; mean over cards)

| role | cat | launches | ms/step | floor ms | standalone floor ms | gap ms | max card |
|---|---|---|---|---|---|---|---|
| routed gate+up | weights | 40 | 1.827 | 0.471 | 0.471 | 1.356 | c3 1.856 |
| routed down | weights | 40 | 1.051 | 0.298 | 0.298 | 0.753 | c4 1.065 |
| exchange (pull) | exchanges | 83 | 1.015 | 0.351 | 0.351 | 0.664 | c5 1.104 |
| q_b | weights | 40 | 0.715 | 0.503 | 0.503 | 0.212 | c5 0.920 |
| q_a + kv | weights | 37 | 0.700 | 0.606 | 0.606 | 0.094 | c4 0.703 |
| output-b | weights | 40 | 0.627 | 0.503 | 0.503 | 0.124 | c2 0.632 |
| norm + mix dots | small serial ops | 77 | 0.626 | 0.295 | 0.295 | 0.331 | c2 0.636 |
| output-a | weights | 40 | 0.541 | 0.402 | 0.402 | 0.139 | c5 0.747 |
| route pick + shared gate/up | weights | 40 | 0.497 | 0.271 | 0.271 | 0.226 | c2 0.501 |
| router logits + compressor | weights | 47 | 0.433 | 0.355 | 0.355 | 0.078 | c2 0.435 |
| exchange (push) | exchanges | 80 | 0.390 | 0.255 | 0.255 | 0.135 | c2 0.545 |
| attention score | attention | 40 | 0.333 | 0.015 | 0.088 | 0.318 | c3 0.336 |
| shared down | weights | 40 | 0.251 | 0.135 | 0.135 | 0.115 | c4 0.255 |
| engram gate | small serial ops | 2 | 0.238 | 0.001 | 0.004 | 0.236 | c5 0.257 |
| attention output | attention | 40 | 0.217 | 0.015 | 0.088 | 0.202 | c2 0.224 |
| attention softmax | attention | 40 | 0.214 | 0.001 | 0.088 | 0.213 | c2 0.224 |
| q_a/kv norms | small serial ops | 40 | 0.164 | 0.002 | 0.088 | 0.162 | c1 0.165 |
| head | weights | 1 | 0.159 | 0.165 | 0.165 | -0.006 | c4 0.160 |
| stream post+collapse | small serial ops | 78 | 0.096 | 0.029 | 0.171 | 0.067 | c2 0.099 |
| engram kv | weights | 2 | 0.092 | 0.078 | 0.078 | 0.014 | c0 0.092 |
| window append | attention | 40 | 0.085 | 0.000 | 0.088 | 0.085 | c3 0.086 |
| q_a + kv + mix dots | weights | 3 | 0.071 | 0.064 | 0.064 | 0.007 | c4 0.072 |
| moe combine | small serial ops | 40 | 0.059 | 0.002 | 0.088 | 0.057 | c0 0.060 |
| compress pool | small serial ops | 1 | 0.055 | 0.000 | 0.003 | 0.055 | c1 0.056 |
| swiglu | small serial ops | 40 | 0.044 | 0.002 | 0.088 | 0.041 | c0 0.044 |
| norm | small serial ops | 7 | 0.041 | 0.000 | 0.016 | 0.040 | c3 0.042 |
| q rope | small serial ops | 40 | 0.036 | 0.000 | 0.088 | 0.035 | c2 0.037 |
| indexer k | weights | 3 | 0.008 | 0.001 | 0.006 | 0.007 | c0 0.008 |
| index fill | attention | 8 | 0.006 | 0.000 | 0.017 | 0.006 | c0 0.006 |
| publish append | small serial ops | 3 | 0.006 | 0.000 | 0.006 | 0.006 | c0 0.006 |
| argmax | small serial ops | 1 | 0.005 | 0.000 | 0.002 | 0.005 | c0 0.005 |
| to f32 | small serial ops | 6 | 0.005 | 0.000 | 0.014 | 0.005 | c0 0.005 |
| rope pairs | small serial ops | 5 | 0.004 | 0.000 | 0.011 | 0.004 | c5 0.005 |
| engram rows decode | small serial ops | 2 | 0.004 | 0.000 | 0.004 | 0.004 | c0 0.004 |
| stream collapse | small serial ops | 3 | 0.004 | 0.001 | 0.007 | 0.003 | c0 0.004 |
| stream post | small serial ops | 2 | 0.003 | 0.001 | 0.005 | 0.002 | c0 0.003 |

#### Categories per card (ms per step: actual / floor / standalone floor)

"Standalone floor": every launch kept, each at least 2.2 us. Gaps have no floor (0).

| category | c0 | c1 | c2 | c3 | c4 | c5 | slowest card | its floor |
|---|---|---|---|---|---|---|---|---|
| weights | 6.70 / 3.62 / 3.63 | 6.76 / 3.62 / 3.63 | 7.37 / 4.32 / 4.32 | 6.82 / 3.62 / 3.62 | 6.81 / 3.62 / 3.63 | 7.39 / 4.32 / 4.32 | c5 7.39 | 4.32 |
| small serial ops | 1.38 / 0.33 / 0.89 | 1.37 / 0.33 / 0.89 | 1.40 / 0.33 / 0.89 | 1.38 / 0.33 / 0.89 | 1.39 / 0.33 / 0.89 | 1.41 / 0.33 / 0.89 | c5 1.41 | 0.33 |
| exchanges | 1.37 / 0.61 / 0.61 | 1.21 / 0.61 / 0.61 | 1.57 / 0.60 / 0.60 | 1.35 / 0.61 / 0.61 | 1.39 / 0.61 / 0.61 | 1.54 / 0.60 / 0.60 | c2 1.57 | 0.60 |
| attention | 0.85 / 0.03 / 0.37 | 0.85 / 0.03 / 0.37 | 0.87 / 0.03 / 0.37 | 0.86 / 0.03 / 0.37 | 0.85 / 0.03 / 0.37 | 0.85 / 0.03 / 0.37 | c2 0.87 | 0.03 |
| gaps, profiled (marks - kernels) | 2.78 | 2.60 | 2.78 | 2.79 | 3.00 | 2.67 | c4 3.00 | 0.00 |
| gaps, real (real step - kernels) | 1.44 | 1.54 | 0.52 | 1.31 | 1.28 | 0.53 | c1 1.54 | 0.00 |
| profiling inflation (profiled wall - real) | 1.56 | 1.23 | 2.45 | 1.76 | 2.14 | 2.33 | c2 2.45 | 0.00 |
| **profiled wall** | 13.28 | 12.95 | 14.17 | 13.49 | 13.87 | 14.05 | | |

Busy outside exchanges: c0 8.92, c1 8.98, c2 9.64, c3 9.06, c4 9.05, c5 9.65 ms; the most-loaded card is c5 (+0.74 ms over the least loaded). Exchange kernel time c0 1.37, c1 1.21, c2 1.57, c3 1.35, c4 1.39, c5 1.54 ms. Each run profiles one card, so these come from six runs; their min, 1.21 ms, bounds the pure exchange cost from above, the rest of a card's exchange time is waiting for a slower card. If the busiest card were always the last to arrive, it would have the least exchange time; it does not here, so who waits for whom changes from exchange to exchange or the exchange itself costs more on some cards (needs the per-exchange arrival data, `OWN_XWAIT`).

Whole-step floor (slowest card, every byte once at 550 GB/s, exchanges hidden): **4.69 ms** (213 tok/s); with the 163 exchanges at the 2.5 us sync floor not hidden: 5.09 ms (196 tok/s). Mean card 4.22 ms (the head groups put 0.70 ms more on c5). Today: 11.73 ms.

#### Top 15 recoverable items (ms per step above the floor; mean over cards, max card in brackets)

| # | item | category | recoverable ms | note |
|---|---|---|---|---|
| 1 | idle gaps between kernels (real step - kernel sum) | gaps | 1.104 (1.539) | profiled gaps 2.60-3.00 ms; ~1,050 launches per step |
| 2 | `XchgPull` exchanges (83/step, 12.2 us each) | exchanges | 0.664 (0.757) | floor 0.35 ms (2.5 us sync + bytes); includes waiting for slower cards |
| 3 | `RoutedIQ2SP<20u, ActF32, NoRows>` (routed gate+up, 15/step) | weights | 0.559 (0.567) | runs at 27% of floor speed |
| 4 | `RoutedIQ1SP<20u, ActF32, true, NoRows>` (routed gate+up, 10/step) | weights | 0.441 (0.446) | runs at 16% of floor speed |
| 5 | `RoutedIQ2XXSP<20u, ActF32, NoRows>` (routed gate+up, 15/step) | weights | 0.356 (0.372) | runs at 33% of floor speed |
| 6 | `RowsP<RowsPair<NormRows<5120u, 4u>, HcDotsRows<5120u, 8u>...` (norm + mix dots, 77/step) | small serial ops | 0.331 (0.340) | runs at 47% of floor speed |
| 7 | `RoutedIQ2SP<9u, ActF32, NoRows>` (routed down, 15/step) | weights | 0.318 (0.326) | runs at 25% of floor speed |
| 8 | `SparseScoreHG<512u, 4u>` (attention score, 38/step) | attention | 0.307 (0.309) | runs at 5% of floor speed |
| 9 | `RoutedIQ3XXSP<9u, ActF32, NoRows>` (routed down, 15/step) | weights | 0.258 (0.265) | runs at 33% of floor speed |
| 10 | `EngramGateP` (engram gate, 2/step) | small serial ops | 0.236 (0.256) | runs at 1% of floor speed |
| 11 | `SparseSoftmaxPN<640>` (attention softmax, 38/step) | attention | 0.209 (0.218) | runs at 0% of floor speed |
| 12 | `SparseOutJC<512u, 16u, 128u, 16u>` (attention output, 40/step) | attention | 0.202 (0.208) | runs at 7% of floor speed |
| 13 | `RowsP<RowsPair<NormRows<1280u, 4u>, NormRows<512u, 2u> > >` (q_a/kv norms, 40/step) | small serial ops | 0.162 (0.163) | runs at 1% of floor speed |
| 14 | `RoutePRows<RowsPair<HcFinishRows, RowsPair<DenseRows<Gemv...` (route pick + shared gate/up, 27/step) | weights | 0.135 (0.140) | runs at 60% of floor speed |
| 15 | `XchgP` exchanges (80/step, 4.9 us each) | exchanges | 0.135 (0.290) | floor 0.25 ms (2.5 us sync + bytes); includes waiting for slower cards |

#### Structural levers (they move the floor or hide whole categories)

| lever | floor change ms | today's time involved ms | cost |
|---|---|---|---|
| split the replicated reads 6 ways (q_a + kv 8.30 MB, router 3.93 MB, stream-mix rows 1.97 MB, compressor) | -1.08 | q_a + kv launches 0.77 | an all-gather per split matrix (~12 us each today) unless fused into an existing exchange |
| heads split 12,12,12,12,8,8 in one-token steps too (as prompt blocks) | -0.34 (slowest card 4.69 -> 4.34) | q_b + output-a on c2/c5 | 40 head-pair exchanges per step (~8 us each today) |
| exchanges hidden behind weight reads (persistent layer kernel, weights loaded before the flag wait) | 0 | exchanges 1.41 + gaps 1.10 | a persistent-kernel rewrite (strategy S1/S2) |

Launch-count check (model vs profile, per step): c5 `HcPostPreP<ActF32>`: profile 77.34, model 78.00

(The prompt logs pre_c0.log, pre_c1.log, pre_c2.log, pre_c3.log, pre_c4.log, pre_c5.log carry no kernel table: with one answer token the runner prints no profile; run them with 2 answer tokens. Using round18-e80-prompt-3k-heads-profile-card0.txt, round18-e80-prompt-3k-heads-profile-card2.txt, round18-e80-prompt-3k-heads-profile-card4.txt, round18-e80-prompt-3k-heads-profile-card5.txt instead.)

### Prompt reading, blocks of 16 tokens (4 cards profiled)

Profiles: round18-e80-prompt-3k-heads-profile-card0.txt, round18-e80-prompt-3k-heads-profile-card2.txt, round18-e80-prompt-3k-heads-profile-card4.txt, round18-e80-prompt-3k-heads-profile-card5.txt. Kernel times are totals over the read, divided by the block count. Routed experts: 80 distinct of 384 per (block, layer) assumed (`--distinct`; OWN_MT_IDSTAT=1 measures it). Floor = max(bytes / 550 GB/s, multiply-adds / 5.70 T/s).

| role | cat | launches / block | ms / block (mean) | max card | weight bytes / block (c0) | multiply-adds (c0) | floor ms | bound | gap ms |
|---|---|---|---|---|---|---|---|---|---|
| routed gate+up | weights | 40.0 | 11.917 | c5 12.309 | 3.44 GB | 15.10 G | 6.247 | bytes | 5.670 |
| exchange | exchanges | 163.8 | 7.942 | c4 9.199 | - | 0.00 G | 0.409 | - | 7.533 |
| routed down | weights | 40.0 | 7.045 | c5 7.291 | 2.13 GB | 7.50 G | 3.913 | bytes | 3.131 |
| q_a + mix dots | weights | 40.0 | 4.820 | c5 4.951 | 336.67 MB | 4.51 G | 0.791 | compute | 4.029 |
| q_b | weights | 40.0 | 3.756 | c2 4.414 | 309.95 MB | 5.03 G | 0.736 | compute | 3.020 |
| router logits + mix dots | weights | 40.0 | 3.209 | c5 3.289 | 235.93 MB | 1.57 G | 0.429 | bytes | 2.780 |
| output-b | weights | 40.0 | 2.634 | c5 2.742 | 273.37 MB | 4.45 G | 0.787 | compute | 1.847 |
| output-a | weights | 80.0 | 2.100 | c2 2.647 | 247.58 MB | 4.03 G | 0.589 | compute | 1.511 |
| route pick + shared gate/up | weights | 40.0 | 1.807 | c5 1.855 | 147.95 MB | 2.52 G | 0.442 | compute | 1.366 |
| shared down | weights | 40.0 | 1.271 | c5 1.301 | 73.51 MB | 1.25 G | 0.221 | compute | 1.050 |
| kv | weights | 40.0 | 1.007 | c5 1.043 | 103.21 MB | 1.68 G | 0.294 | compute | 0.713 |
| attention output | attention | 40.0 | 1.004 | c0 1.061 | - | 0.00 G | 0.000 | - | 1.004 |
| norm | small serial ops | 85.0 | 0.870 | c5 0.892 | - | 0.00 G | 0.000 | - | 0.870 |
| attention score | attention | 40.0 | 0.622 | c2 0.682 | - | 0.00 G | 0.000 | - | 0.622 |
| engram kv | weights | 2.0 | 0.603 | c5 0.628 | 42.90 MB | 0.84 G | 0.147 | compute | 0.456 |
| exchange (head pairs) | exchanges | 80.4 | 0.541 | c2 0.635 | - | 0.00 G | 0.201 | - | 0.340 |
| stream post+collapse | small serial ops | 78.0 | 0.437 | c2 0.442 | - | 0.00 G | 0.000 | - | 0.437 |
| indexer q_b | weights | 6.3 | 0.436 | c5 0.448 | 83.89 MB | 0.67 G | 0.153 | bytes | 0.283 |
| expert grouping | small serial ops | 40.0 | 0.426 | c5 0.438 | - | 0.00 G | 0.000 | - | 0.426 |
| index score | attention | 6.3 | 0.352 | c5 0.362 | - | 0.00 G | 0.000 | - | 0.352 |
| q_a/kv norms | small serial ops | 40.0 | 0.343 | c5 0.352 | - | 0.00 G | 0.000 | - | 0.343 |
| compressor + indexer proj | weights | 13.3 | 0.274 | c2 0.275 | 39.32 MB | 0.31 G | 0.071 | bytes | 0.203 |
| attention softmax | attention | 40.0 | 0.269 | c2 0.273 | - | 0.00 G | 0.000 | - | 0.269 |
| engram gate | small serial ops | 2.0 | 0.241 | c5 0.264 | - | 0.00 G | 0.000 | - | 0.241 |
| moe combine | small serial ops | 39.9 | 0.124 | c4 0.124 | - | 0.00 G | 0.000 | - | 0.124 |
| index top-k | attention | 7.2 | 0.112 | c5 0.115 | - | 0.00 G | 0.000 | - | 0.112 |
| compress pool | small serial ops | 3.0 | 0.103 | c5 0.106 | - | 0.00 G | 0.000 | - | 0.103 |
| swiglu | small serial ops | 40.1 | 0.101 | c4 0.105 | - | 0.00 G | 0.000 | - | 0.101 |
| window append | attention | 40.1 | 0.094 | c5 0.096 | - | 0.00 G | 0.000 | - | 0.094 |
| ring commit | attention | 40.1 | 0.083 | c5 0.085 | - | 0.00 G | 0.000 | - | 0.083 |
| q rope | small serial ops | 50.4 | 0.069 | c5 0.072 | - | 0.00 G | 0.000 | - | 0.069 |
| small | small serial ops | 38.9 | 0.054 | c4 0.054 | - | 0.00 G | 0.000 | - | 0.054 |
| indexer k | weights | 4.0 | 0.021 | c5 0.021 | 524.3 KB | 0.00 G | 0.001 | bytes | 0.020 |
| engram rows decode | small serial ops | 2.0 | 0.011 | c5 0.011 | - | 0.00 G | 0.000 | - | 0.011 |
| stream collapse | small serial ops | 3.0 | 0.009 | c4 0.010 | - | 0.00 G | 0.000 | - | 0.009 |
| stream post | small serial ops | 2.0 | 0.009 | c5 0.009 | - | 0.00 G | 0.000 | - | 0.009 |
| index fill | attention | 1.7 | 0.003 | c4 0.003 | - | 0.00 G | 0.000 | - | 0.003 |
| (outside blocks: answer step, last head) | - | - | 0.056 | | | | | | |

Kernel time per block (mean over cards): 54.72 ms; profiled read 63.17 ms per block (c0 64.18, c2 63.37, c4 62.55, c5 62.60); by category: weights 40.90 (floor 14.82); exchanges 8.48 (floor 0.61); small serial ops 2.80 (floor 0.00); attention 2.54 (floor 0.00).

Gaps per block (profiled read per block - kernel sum): 8.45 ms.

Block floor (all kernels at their floor, exchanges hidden): 14.82 ms -> 1080 tok/s at 16 tokens per block (today ~253 tok/s profiled).

Floor per token by block size (card c0; weight roles only; distinct experts per layer from uniform picks, an upper bound; exchanges and small ops excluded):

| tokens per block | distinct experts / layer | expert bytes / block | other weight bytes / block | floor ms / block | floor tok/s | bound |
|---|---|---|---|---|---|---|
| 16 | 85 | 5.92 GB | 1.89 GB | 15.68 | 1021 | bytes |
| 32 | 151 | 10.53 GB | 1.89 GB | 28.56 | 1120 | bytes |
| 64 | 243 | 16.91 GB | 1.89 GB | 49.59 | 1291 | bytes |
| 128 | 332 | 23.12 GB | 1.89 GB | 79.73 | 1605 | bytes |
| 256 | 377 | 26.24 GB | 1.89 GB | 138.84 | 1844 | compute |
| 512 | 384 | 26.72 GB | 1.89 GB | 277.67 | 1844 | compute |


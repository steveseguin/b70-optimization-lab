# Kernel time from machine code (no GPU)

These tools estimate how long one launch of an engine kernel takes on a B70 without running anything on a card.
They read the machine code that the Intel graphics compiler (IGC) writes during an ahead-of-time build, count what
each kernel does, and turn the counts into a time with a small model fitted to measured times.

Use them to ask "is this kernel near its floor, and if not, what holds it?" before spending GPU time, and to
compare kernel forms (work-group size, rows per sub-group, load forms) on paper first. They do not replace a
measurement. The model's error is stated per kernel family below; read it before trusting a number.

`dsv41_step_budget.py` and `BUDGET.md` in this folder belong to a different tool (time against floor for a whole
step, from profiles). This README covers the files listed next.

## Files

| file | what it does |
| --- | --- |
| `dump_isa.sh` | Ahead-of-time compiles one small translation unit for `intel_gpu_bmg_g31` with IGC's dumps on. The `.asm` files land in a directory. Host only: nothing is run. |
| `engine_kernels_tu.cpp` | Compile-only translation unit. It instantiates every kernel type of the card-2 answer-step profile (round 18, g82) with the engine's launch form: work-group size, 32-lane sub-groups, local memory. It never launches anything (`main` returns unless `argc > 1000`). |
| `isa_census.py` | Parses the `.asm` dumps. For each kernel it reports instruction counts by class, send bytes, spills and fills, GRF mode, SIMD width, loops with instructions per iteration, and a block map. |
| `predict.py` | Predicts one launch's time from the census and the launch shape. It also prints the calibration table (`--table`) and refits the constants (`--fit`). |
| `cases.py` | The calibration cases: kernel, launch shape, bytes read, loop trips, and the measured time with its source file. |
| `calib.json` | The fitted constants. `predict.py` reads them by default. |

## Usage

All commands run from `experiments/own-xpu-runtime/engine`. Nothing here touches a GPU.

### 1. Dump the machine code

```bash
# a bench (or any small translation unit); never own_run_v41.cpp
tools/perf/dump_isa.sh /home/steve/dsv41-work/perf/isa-norm_ff tools/bench/bench_norm_ff.cpp
# the engine's own kernels, from a source snapshot, in the engine's launch forms
SRC_ROOT=/home/steve/dsv41-work/src82/src \
  tools/perf/dump_isa.sh /home/steve/dsv41-work/perf/isa-engine82 tools/perf/engine_kernels_tu.cpp
```

The script refuses to compile `own_run_v41*`. It refuses when `MemAvailable` is below 6 GiB, takes a lock so only
one compile runs at a time, and runs under `nice -n 10`. A bench compiles in 4 to 10 s (`bench_dense_m16.cpp`,
182 kernels: about 100 s). It keeps only the `.asm` files and `build.log` (`KEEP_VISA=1` also keeps the vISA text).

**Checked: IGC dumps work without a GPU.** `IGC_ShaderDumpEnable=1 IGC_DumpToCustomDir=DIR` during the
`-fsycl-targets=intel_gpu_bmg_g31` AOT step writes one `OCL_asm*_simd32_entry_NNNN.asm` per kernel (SIMD32 for the
engine's kernels). Source-line mapping does not work in this path: `-gline-tables-only` is ignored for the device,
and `-options -g` makes ocloc fail. To leave out a runtime branch, use block ranges (`--blocks`, then `--skip`).

Dumps made so far, all in `/home/steve/dsv41-work/perf/`:

| dump | source | kernels | 256-GRF | spilling |
| --- | --- | ---: | ---: | ---: |
| `isa-engine82` | `engine_kernels_tu.cpp` against `/home/steve/dsv41-work/src82/src` (the profiled g82 build) | 39 | 1 | 0 |
| `isa-dense_m16` | `tools/bench/bench_dense_m16.cpp` | 180 | 83 | 18 |
| `isa-norm_ff` | `tools/bench/bench_norm_ff.cpp` | 14 | 2 | 2 |
| `isa-route_rows` | `tools/bench/bench_route_rows.cpp` | 11 | 0 | 0 |
| `isa-route_pick` | `tools/bench/bench_route_pick.cpp` | 17 | 0 | 0 |
| `isa-engram_ff` | `tools/bench/bench_engram_ff.cpp` | 3 | 0 | 0 |

The kernel counts leave out the runtime's fill kernels and empty symbol-table programs. Every kernel is SIMD32.
None of the engine's decode kernels spills. Only `SparseSoftmaxPN` runs in 256-GRF mode, which halves its
threads per XVE. `names.txt` in the same folder lists every kernel's short name.

### 2. Census

```bash
python3 tools/perf/isa_census.py /home/steve/dsv41-work/perf/isa-engine82 --list
python3 tools/perf/isa_census.py /home/steve/dsv41-work/perf/isa-engine82 --match '^GemvQ8P<128u'
python3 tools/perf/isa_census.py DUMP --match '^RowsP<NormRows<5120u, 4u> > @wg512$' --blocks   # block map
python3 tools/perf/isa_census.py DUMP --json census.json
```

Short names drop the SYCL wrapper. A kernel instantiated through a launch helper reads `Kernel @wgN`, where N is
the work-group size. Per kernel the census prints:

- SIMD width, GRF mode (128 or 256 registers), instruction count, spill bytes, spill stores and fills, flag spills;
- counts by group: sends, fp32, fp16, fp64, madm (IEEE divide and square-root steps), math, int, moves, sync, control;
- counts by pipe (float, int, long = FP64 and 64-bit integer, math, send, control) and by detailed class:
  - sends: `send.load.global`, `send.load.slm`, store, atomic, spill, fill, fence, barrier, eot;
  - math functions: `math.inv`, `math.sqt`, `math.exp`, ...;
  - moves: indirect, convert, strided, broadcast, scalar, fp64;
  - sync: `sync.allrd`, `sync.allwr`, `sync.bar`;
  - control: `ctrl.jmpi`, `ctrl.goto`, ...;
- send bytes per form. A block load `d32x64t` reads 256 bytes once per sub-group. A per-lane load `d16u32` at
  SIMD32 reads 2 bytes x 32 lanes;
- loops, found as back edges in the block graph: id, depth, blocks, kind (uniform `jmpi` or SIMD `goto`), and
  instructions and bytes per iteration. The loop ids are what `predict.py --trips` takes.

### 3. Predict one launch

```bash
python3 tools/perf/predict.py /home/steve/dsv41-work/perf/isa-engine82 --match '^GemvQ8P<128u, ActF32> @wg512$' \
    --wg 512 --groups 128 --bytes 8.91e6 --hot 'load\.ugm\.d32x64t' --explain
python3 tools/perf/predict.py /home/steve/dsv41-work/perf/isa-engine82 --match '^EngramGateP @wg32$' \
    --wg 32 --groups 4 --trips 0=160,1=160 --bytes 0.26e6 --loads warm --explain
```

Arguments:

| argument | meaning |
| --- | --- |
| `--wg`, `--groups` | Work-group size in items, and number of work-groups. |
| `--threads` | Active sub-groups, when fewer than all of them do the work. |
| `--bytes` | Bytes the launch must read from memory. |
| `--warm` | The data is already in L2 (a bench that repeats one launch). |
| `--loads warm` | Loads wait for L2, but the bytes still come from DRAM. Use it for a launch that reads what the previous launch wrote (most non-weight engine kernels). |
| `--trips L0=..,L1=..` | Loop trips. Fractions are allowed: issue counts use the average, the critical path rounds up. |
| `--skip B020-B032,...` | Blocks of a runtime branch the launch does not take. |
| `--hot REGEX` | Loads that hit cache, matched on the instruction text. Example: the activations every sub-group re-reads. |

`--explain` prints, for each thread kind:

- the dynamic instruction counts and issue cycles per pipe;
- the bytes per thread;
- the critical path split by what it waited for (DRAM or L2 load, FP64 pipe, barrier, ...);
- the slowest blocks.

A launch with several thread kinds (a `RowsPair` launch: one serial row beside many dense rows) is described in
`cases.py` with `parts=[...]`.

### 4. Table and refit

```bash
python3 tools/perf/predict.py --table                     # predicted vs measured, error by group, floor ranking
python3 tools/perf/predict.py --table --csv /home/steve/dsv41-work/perf/table.csv
python3 tools/perf/predict.py --fit                       # refit the constants -> calib.json
# held-out check: fit the benches only, then look at the engine launches
python3 tools/perf/predict.py --fit --defaults --fit-on '^(n5|rt5|rp3|eg2|d3|d4) ' \
    --calib /home/steve/dsv41-work/perf/calib-benches.json
python3 tools/perf/predict.py --table --calib /home/steve/dsv41-work/perf/calib-benches.json --only '^eng '
```

A new measurement goes into `cases.py` as one `add(...)` line: the kernel, the launch shape, the bytes, the loop
trips, the measured microseconds and the source file. Then refit. `--table` takes about 10 s. `--fit` takes about
15 minutes on one CPU core: four rounds of coordinate descent over the constants in `FREE`, within `BOUNDS`.
Each group of cases weighs 1/sqrt(its size), and each case's squared log error is capped at 1.

## The model

One launch is timed by its events (command start to command end), as the engine profile and the benches measure.

```
T = launch + wave_ns x (waves - 1) + smooth_max(T_issue, T_fp64, T_lat, T_mem, T_port)
```

- **Launch.** Event-timed. An empty kernel measures 0.52 us (rp r3 V7) and the fit gives 0.65 us. The engine's
  wall-clock cost per launch is larger, about 2.2 us (see `BUDGET.md`).
- **Issue (T_issue).** All threads' instructions spread over the XVEs in use, at `dual` instructions per clock per
  XVE. The cost of one instruction is:
  - float and int: `ceil(lanes x bits / 512)` cycles, so a SIMD32 float op takes 2 cycles;
  - FP64: `lanes / fp64_lanes` cycles;
  - math: `lanes / math_lanes` cycles;
  - send, sync and branch: 1 cycle.
- **FP64 (T_fp64).** The long pipe's cycles on the busiest XVE.
- **Latency (T_lat).** One thread's critical path times the number of waves. The tool replays the thread's
  instruction stream with the compiler's own dependence marks:
  - `F@n`, `I@n`, `L@n`, `M@n`, `A@n` distances;
  - `$n` send tokens and their `.src` / `.dst` waits;
  - `sync.allrd`, `sync.allwr`, `sync.bar`.

  Result latencies per pipe and per load kind are listed in the constants table. A narrow load (fewer bytes than a
  64-byte line) shares its line with the next loads, so on average only bytes/64 of it waits for memory. A serial
  part of a fused launch (one sub-group) runs once, not once per wave.
- **Memory (T_mem).** DRAM bytes / `bw_dram` for a cold launch (weights streamed once per step), or L2 bytes /
  `bw_l2` for a bench that repeats one launch.
- **Data port (T_port).** Every byte every thread loads, cache hits included, per Xe-core, at `port_bpc` bytes
  per clock. Local-memory loads use `slm_bpc`. This term covers the activations that each sub-group of a
  16-token dense launch re-reads.
- **smooth_max.** `(sum of bound^k)^(1/k)`: k large gives the plain max, smaller k lets bounds that are close
  add up partly.
- **Occupancy.** Threads per work-group = work-group size / SIMD width. 8 threads per XVE in 128-GRF mode and 4 in
  256-GRF mode. 32 Xe-cores x 8 XVEs. Work-groups beyond the resident ones run in further waves.
- **Floor.** Launch plus memory time: what the launch would take if it did nothing but read its bytes.

What the model does not know:

- data-dependent branches and loop trips (given per case, or the case is shown unfitted);
- bank conflicts, cache misses beyond the cold, warm and hot classes, and the timing of other cards;
- whether the compiler's SWSB marks are tighter than the hardware needs.

It sees one thread's stream, not how threads of one XVE interleave. The fitted `dual` and `smooth_k` absorb that
on average, and per-kernel error remains.

## How accurate it is

The constants were fitted on 175 measured launches and checked on 193. The table and CSV are in
`/home/steve/dsv41-work/perf/table.txt` and `table.csv`. To redo it: `predict.py --table --csv ...`.

- **All fitted cases (175):** median error 12 %. 145 are within 25 % and 169 within 50 %. The worst is +104 %.
- **The engine's own launches (32, card-2 answer step):** median error 12 %. 26 are within 25 %, 31 within 50 %.
  The worst is -50 %, the 2.9 us indexer-k publish launch.
- **Held out, the honest test:** with the constants fitted on the benches only, the engine launches the fit never
  saw come out at a median error of 33 %. Dense rows, attention and small launches have medians of 25 to 33 %.
  The routed experts come out 2 to 4 times too slow, and so does `SparseOutJC` (+395 %). No bench uses local memory heavily, so the local-memory rate
  (`slm_bpc`) is set only by the engine launches that use it. Until a local-memory bench is added to `cases.py`,
  treat a prediction for a new local-memory-heavy kernel as good to a factor of 2.
- **Not fitted (18 cases):** router-pick and RouteP forms whose loop trips depend on the data. They are predicted
  with one trip per loop, median error 42 %, and shown for reference only.
- **The constants are effective values, not hardware latencies.** Some ended at a bound of their range: the
  float-pipe latency at one clock, the barrier cost at 5 ns, the L2 bandwidth at 4,000 GB/s. That means the cases do
  not pin them. The fitted DRAM bandwidth (496 GB/s) is below the 572 GB/s the output head reaches, so the head is
  predicted 32 % slow. The SIMD32 dependent double add the constants imply is 14.6 ns, against about 26 ns measured
  alone. Use the bound columns to see which limit a kernel hits. Do not read single constants as measurements.

Largest remaining errors and their likely reasons:

| case | error | likely reason |
| --- | ---: | --- |
| `rt5 H` router scores, `rt5 C` mix finish alone | +104 %, +82 % | One sub-group of straight-line code. The replay probably waits longer on cross-pipe dependences than the hardware does. |
| `eng q_a + kv Q6_K`, `eng o_b Q6_K` | +87 %, +39 % | The cost of the Q6_K bit unpacking is overestimated in these forms. The single Q6_K rows are -18 %. |
| `eng publish: indexer k`, `eng WindowAppendP` | -50 %, -42 % | Tiny launches (2 to 3 us). Something outside the code, probably first touch of small cold buffers, costs time. |
| `d4 Q6_K 768x4096 G8 R2` | -43 % | A 256-GRF form with 4 threads per XVE. The model probably underrates the stall of having few threads. |
| `d3 Q8_0 6144x1280 G8R2` (9 forms) | -25 to -36 % | Issue-bound 128-GRF forms that run 30 % slower than their issue count says. Reason not found. |
| unfitted router picks (`rp3 V1/V3/V4/V6/V10`, `rt5 B/I`) | -48 to -64 % | Data-dependent loops counted once. |

## Which kernels are farthest from their floor, and why

Card 2's answer step, from the g82 profile. The floor of a launch is 0.52 us of launch plus its bytes at 550 GB/s.
The launches listed below spend 9.3 ms per step, and 4.3 ms of that is above their floors. The ranking table
further down has every launch.

1. **Routed experts: 7 kernels, about 2.0 ms above the floor per step, 2.5 to 5.8 times the floor.**
   - The model says they are issue-bound. In the gate/up forms (IQ2_S, IQ1_S) one sub-group runs about 5,900
     instructions for its 2.25 rows of 5,120 weights. That is about 16 instructions per weight per lane. About
     half of them are integer instructions that decode the IQ grid index; the rest are the local-memory grid
     lookup and the multiply-add. Reading the weights alone would take 7 to 14 us. The instructions take 18 to
     47 us.
   - IQ1_S is the furthest (5.8x): it has the fewest bytes and the same decode work.
   - The IQ2_XXS forms are limited by the load port instead. Every sub-group re-reads the whole 20 KB activation
     vector for each row it does. In the gate/up form that is 102 MB of global loads (mostly cache hits) plus
     94 MB of local-memory loads, for 6.5 MB of weights.
   - Rows / 2048 = 2.25 row chunks per sub-group, so a quarter of the sub-groups run a third chunk while the rest
     sit idle.
2. **Sparse attention: 3 kernels, about 0.67 ms per step, 6 to 10 times the floor.**
   - The grids are tiny. `SparseScoreHG` runs 24 sub-groups and `SparseSoftmaxPN` 16, one per work-group, so at
     most 24 of the card's 256 XVEs are busy.
   - Each sub-group runs a serial chain of about 6,000 instructions (score) or 2,200 (softmax), and waits for its
     own loads.
   - `SparseOutJC` adds fences and barriers.
   - These are latency-bound: the bytes are under 0.25 MB.
3. **Norm + stream-mix dots: about 0.45 ms per step.** That is 77 launches at 1.9x the floor, plus the 1280/512
   norms (40 launches at 7.7x). They are FP64 work at about 1/11 of the float rate (`fp64_lanes` 1.44), and the
   serial norm row waits for its loads.
4. **Engram gate: 2 launches of 116 us, 0.23 ms per step, 117 times the floor.** Four sub-groups do it all. Each
   runs 160 loop trips. A trip waits for a load round trip, then runs three interleaved scalar double-add chains
   of 32 dependent steps. The FP64 latency and the load latency are almost the whole time. The structural lever is to
   spread the chains over more sub-groups.
5. **Router two-stage pick: 0.13 ms per step.** A serial pick beside the shared rows, 1.6x the floor. Its loop
   trips depend on the data, so the model does not cover it in detail.

Near the floor: the Q8_0 dense rows (`o_a`, `o_b`, `q_a + kv`, `q_b`, router rows) run at 1.0 to 1.1 times the
floor and are memory-bound. The only lever left there is fewer bytes. The Q6_K rows run at 1.2 to 1.5 times the
floor, limited by issue (unpacking 6-bit values). The output head is at the floor.

## Numbers

### Fitted constants (`calib.json`)

| constant | value | meaning |
| --- | ---: | --- |
| `dual` | 0.735 | instructions issued per clock per XVE, all threads together |
| `fp64_lanes` | 1.44 | FP64 lanes per clock per XVE (16 would be full rate) |
| `lat_f` | 0.4 | float pipe result latency, ns |
| `lat_i` | 3.23 | int pipe result latency, ns |
| `lat_l` | 10 | FP64 pipe result latency, ns |
| `lat_gl_cold` | 387 | global load from DRAM, ns |
| `lat_gl_warm` | 100 | global load from L2, ns |
| `lat_gl_hot` | 104 | global load the case marks hot (activations), ns |
| `lat_slm` | 11.6 | local-memory load, ns |
| `lat_bar` | 5 | work-group barrier, ns |
| `lat_m` | 2.5 | math pipe result latency, ns |
| `lat_fill` | 99.8 | spill fill, ns |
| `launch_ns` | 646 | event-timed launch, ns |
| `wave_ns` | 827 | extra cost per extra wave of work-groups, ns |
| `bw_dram` | 496 | DRAM bandwidth, GB/s |
| `bw_l2` | 4e+03 | L2 bandwidth for warm benches, GB/s |
| `port_bpc` | 92.4 | load bytes per clock per Xe-core (all loads, cache hits included) |
| `slm_bpc` | 60.6 | local-memory load bytes per clock per Xe-core |
| `smooth_k` | 10.3 | smooth-max exponent (large = plain max) |

### Error by group

Error = predicted / measured - 1. "Not fitted" cases have loops whose trip counts depend on the data; they are
predicted with one trip per loop and shown for reference only.

| group | cases | median error | mean error | worst | within 25 % | within 50 % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| all fitted cases | 175 | 12 % | 16 % | +104 % | 145 | 169 |
| engine launches (fitted) | 32 | 12 % | 16 % | -50 % | 26 | 31 |
| benches (fitted) | 143 | 12 % | 16 % | +104 % | 119 | 138 |
| not fitted (data-dependent loops) | 18 | 42 % | 35 % | -64 % | 6 | 13 |
| engine dense | 12 | 18 % | 24 % | -50 % | 8 | 11 |
| engine fused | 4 | 15 % | 12 % | -15 % | 4 | 4 |
| engine experts | 7 | 4 % | 5 % | -13 % | 7 | 7 |
| engine attention | 3 | 12 % | 20 % | +41 % | 2 | 3 |
| engine serial | 1 | 10 % | 10 % | -10 % | 1 | 1 |
| engine small | 5 | 12 % | 14 % | -42 % | 4 | 5 |
| bench dense m16 | 119 | 15 % | 16 % | -43 % | 101 | 118 |
| bench dense warm | 1 | 34 % | 34 % | +34 % | 0 | 1 |
| bench fp64 rows | 3 | 1 % | 1 % | -1 % | 3 | 3 |
| bench fused | 6 | 2 % | 2 % | -4 % | 6 | 6 |
| bench serial | 14 | 12 % | 30 % | +104 % | 9 | 10 |

### Held-out check

Constants fitted on the bench cases only (`--fit-on '^(n5|rt5|rp3|eg2|d3|d4) '`), then applied to the engine
profile's launches, which the fit did not see:

| group | cases | median error | mean error | worst | within 25 % | within 50 % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| engine launches (unseen) | 32 | 33 % | 83 % | +395 % | 13 | 19 |
| engine dense | 12 | 27 % | 32 % | -65 % | 6 | 9 |
| engine fused | 4 | 62 % | 40 % | +69 % | 2 | 2 |
| engine experts | 7 | 218 % | 210 % | +351 % | 1 | 1 |
| engine attention | 3 | 25 % | 142 % | +395 % | 1 | 2 |
| engine serial | 1 | 21 % | 21 % | -21 % | 1 | 1 |
| engine small | 5 | 33 % | 37 % | -67 % | 2 | 4 |
| benches (the fitted set) | 143 | 12 % | 14 % | -43 % | 122 | 139 |

### Engine launches against their floor

Card 2, one answer step (round 18 g82 profile). Floor = 0.52 us launch + bytes at 550 GB/s. "Above" =
(measured - floor) x launches per step. The model columns are its two largest bounds for that launch.

| launch | per step | measured us | floor us | x floor | above, us per step | model: largest bounds (us) |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| experts RoutedIQ2SP<20u | 15 | 51.14 | 14.32 | 3.6 | 552 | issue 46.7, latency 42.0 |
| experts RoutedIQ1SP<20u | 10 | 52.08 | 8.96 | 5.8 | 431 | issue 44.2, latency 34.4 |
| experts RoutedIQ2XXSP<20u | 15 | 34.84 | 12.32 | 2.8 | 338 | port 34.6, issue 31.1 |
| experts RoutedIQ2SP<9u | 15 | 27.99 | 7.61 | 3.7 | 306 | issue 26.6, port 17.9 |
| norm + mix dots @wg64 (ff) | 77 | 8.25 | 4.28 | 1.9 | 305 | latency 6.4, issue 4.7 |
| SparseScoreHG<512,4> | 38 | 8.46 | 0.92 | 9.2 | 287 | latency 7.0, issue 6.5 |
| experts RoutedIQ3XXSP<9u | 15 | 25.22 | 8.96 | 2.8 | 244 | issue 24.9, latency 19.0 |
| EngramGateP (3 double chains) | 2 | 116.07 | 0.99 | 116.9 | 230 | latency 104.4, issue 28.4 |
| SparseSoftmaxPN<640> | 38 | 5.79 | 0.57 | 10.1 | 198 | latency 4.4, issue 2.4 |
| SparseOutJC<512,16,128> | 40 | 5.61 | 0.90 | 6.2 | 188 | latency 7.2, issue 5.8 |
| norms 1280 + 512 @wg64 | 40 | 4.10 | 0.53 | 7.7 | 143 | latency 6.1, issue 4.9 |
| router + finish + shared Q8_0 (two-stage pick) | 27 | 12.83 | 8.12 | 1.6 | 127 | latency 11.5, memory 8.4 |
| experts RoutedIQ2XSP<9u | 6 | 25.11 | 6.85 | 3.7 | 110 | issue 25.5, port 17.7 |
| o_a Q6_K | 13 | 19.56 | 13.03 | 1.5 | 85 | issue 14.7, memory 13.9 |
| q_b Q8_0 8192x1280 + mix finish | 27 | 23.41 | 20.77 | 1.1 | 71 | memory 22.4, issue 13.8 |
| q_b Q6_K + mix finish | 13 | 21.60 | 16.25 | 1.3 | 70 | issue 20.8, memory 17.4 |
| WindowAppendP | 40 | 2.14 | 0.53 | 4.0 | 64 | latency 0.6, issue 0.2 |
| router / compressor rows (halves) | 47 | 9.22 | 8.03 | 1.1 | 56 | memory 8.3, latency 4.4 |
| o_b Q8_0 864x8192 | 27 | 16.14 | 14.19 | 1.1 | 53 | memory 15.2, latency 10.6 |
| shared down Q8_0 864x2304 | 27 | 6.30 | 4.37 | 1.4 | 52 | memory 4.3, latency 3.8 |
| o_b Q6_K | 13 | 15.04 | 11.08 | 1.4 | 51 | latency 20.3, issue 12.1 |
| shared down Q5_K | 13 | 6.31 | 3.01 | 2.1 | 43 | latency 6.3, issue 3.9 |
| experts RoutedIQ2XXSP<9u | 3 | 20.60 | 6.56 | 3.1 | 42 | port 17.7, issue 17.6 |
| q_a + kv Q6_K | 13 | 17.46 | 14.23 | 1.2 | 42 | issue 31.7, latency 25.4 |
| MoeCombineA | 40 | 1.48 | 0.57 | 2.6 | 36 | latency 0.9, issue 0.1 |
| o_a Q8_0 2048x4096 | 27 | 18.06 | 16.72 | 1.1 | 36 | memory 17.9, issue 8.9 |
| q_a + kv Q8_0 1792x5120 | 24 | 19.68 | 18.25 | 1.1 | 34 | memory 19.6, issue 19.0 |
| HcPostPreP | 78 | 1.24 | 0.88 | 1.4 | 28 | latency 0.4, memory 0.4 |
| SwigluBothS | 40 | 1.10 | 0.57 | 1.9 | 21 | latency 0.6, issue 0.2 |
| RowsP<RopeRows> | 40 | 0.92 | 0.52 | 1.8 | 16 | latency 0.3, issue 0.0 |
| engram_kv Q6_K 4272x6144 | 2 | 45.91 | 39.67 | 1.2 | 12 | latency 45.9, issue 45.1 |
| q_a+kv Q8_0 + attn dots (L0/1/14) | 3 | 23.66 | 21.83 | 1.1 | 5 | memory 23.6, issue 13.2 |
| publish: indexer k | 2 | 2.91 | 0.76 | 3.8 | 4 | latency 0.8, issue 0.3 |
| output head Q6_K 21552x5120 | 1 | 158.97 | 165.41 | 1.0 | -6 | issue 190.9, memory 182.7 |

Sum above the floor over these launches: 4.28 ms per step (measured kernel time of the same launches: 9.29 ms).

### Every case

<details><summary>Predicted vs measured, all cases</summary>

Model floor = the fitted launch time + bytes at the fitted bandwidth (DRAM, or L2 for warm benches).

| case | measured us | predicted us | error | main bound | model floor us | measured / model floor | source |
| --- | ---: | ---: | ---: | --- | ---: | ---: | --- |
| **engine dense** | | | | | | | |
| eng o_a Q8_0 2048x4096 | 18.06 | 18.60 | +3 % | memory | 18.60 | 1.0 | round18-g82-pf_new-decode-profile-card2.txt |
| eng o_b Q8_0 864x8192 | 16.14 | 15.83 | -2 % | memory | 15.80 | 1.0 | round18-g82-pf_new-decode-profile-card2.txt |
| eng shared down Q8_0 864x2304 | 6.30 | 5.04 | -20 % | memory | 4.92 | 1.3 | round18-g82-pf_new-decode-profile-card2.txt |
| eng o_a Q6_K | 19.56 | 15.98 | -18 % | issue | 14.51 | 1.3 | round18-g82-pf_new-decode-profile-card2.txt |
| eng o_b Q6_K | 15.04 | 20.95 | +39 % | latency | 12.35 | 1.2 | round18-g82-pf_new-decode-profile-card2.txt |
| eng output head Q6_K 21552x5120 | 158.97 | 209.73 | +32 % | issue | 191.63 | 0.8 | round18-g82-pf_new-decode-profile-card2.txt |
| eng engram_kv Q6_K 4272x6144 | 45.91 | 52.25 | +14 % | latency | 45.68 | 1.0 | round18-g82-pf_new-decode-profile-card2.txt |
| eng shared down Q5_K | 6.31 | 6.96 | +10 % | latency | 3.41 | 1.9 | round18-g82-pf_new-decode-profile-card2.txt |
| eng router / compressor rows (halves) | 9.22 | 8.97 | -3 % | memory | 8.97 | 1.0 | round18-g82-pf_new-decode-profile-card2.txt |
| eng publish: indexer k | 2.91 | 1.46 | -50 % | latency | 0.91 | 3.2 | round18-g82-pf_new-decode-profile-card2.txt |
| eng q_a + kv Q8_0 1792x5120 | 19.68 | 21.41 | +9 % | memory | 20.29 | 1.0 | round18-g82-pf_new-decode-profile-card2.txt |
| eng q_a + kv Q6_K | 17.46 | 32.60 | +87 % | issue | 15.84 | 1.1 | round18-g82-pf_new-decode-profile-card2.txt |
| **engine fused** | | | | | | | |
| eng q_b Q8_0 8192x1280 + mix finish | 23.41 | 26.41 | +13 % | memory | 26.40 | 0.9 | round18-g82-pf_new-decode-profile-card2.txt |
| eng q_b Q6_K + mix finish | 21.60 | 25.07 | +16 % | issue | 21.38 | 1.0 | round18-g82-pf_new-decode-profile-card2.txt |
| eng q_a+kv Q8_0 + attn dots (L0/1/14) | 23.66 | 24.26 | +2 % | memory | 24.26 | 1.0 | round18-g82-pf_new-decode-profile-card2.txt |
| eng norm + mix dots @wg64 (ff) | 8.25 | 7.04 | -15 % | latency | 4.82 | 1.7 | round18-g82-pf_new-decode-profile-card2.txt |
| eng router + finish + shared Q8_0 (two-stage pick) (not fitted) | 12.83 | 12.18 | -5 % | latency | 9.07 | 1.4 | round18-g82-pf_new-decode-profile-card2.txt |
| eng norms 1280 + 512 @wg64 (not fitted) | 4.10 | 6.81 | +66 % | latency | 0.66 | 6.2 | round18-g82-pf_new-decode-profile-card2.txt |
| **engine experts** | | | | | | | |
| eng experts RoutedIQ2SP<20u | 51.14 | 48.85 | -4 % | issue | 15.94 | 3.2 | round18-g82-pf_new-decode-profile-card2.txt |
| eng experts RoutedIQ2XXSP<20u | 34.84 | 36.23 | +4 % | port | 13.72 | 2.5 | round18-g82-pf_new-decode-profile-card2.txt |
| eng experts RoutedIQ1SP<20u | 52.08 | 45.18 | -13 % | issue | 9.99 | 5.2 | round18-g82-pf_new-decode-profile-card2.txt |
| eng experts RoutedIQ2SP<9u | 27.99 | 27.32 | -2 % | issue | 8.50 | 3.3 | round18-g82-pf_new-decode-profile-card2.txt |
| eng experts RoutedIQ3XXSP<9u | 25.22 | 25.73 | +2 % | issue | 9.99 | 2.5 | round18-g82-pf_new-decode-profile-card2.txt |
| eng experts RoutedIQ2XSP<9u | 25.11 | 26.23 | +4 % | issue | 7.66 | 3.3 | round18-g82-pf_new-decode-profile-card2.txt |
| eng experts RoutedIQ2XXSP<9u | 20.60 | 19.53 | -5 % | port | 7.33 | 2.8 | round18-g82-pf_new-decode-profile-card2.txt |
| **engine attention** | | | | | | | |
| eng SparseScoreHG<512,4> | 8.46 | 7.91 | -6 % | latency | 1.09 | 7.8 | round18-g82-pf_new-decode-profile-card2.txt |
| eng SparseSoftmaxPN<640> | 5.79 | 5.08 | -12 % | latency | 0.71 | 8.2 | round18-g82-pf_new-decode-profile-card2.txt |
| eng SparseOutJC<512,16,128> | 5.61 | 7.90 | +41 % | latency | 1.07 | 5.2 | round18-g82-pf_new-decode-profile-card2.txt |
| **engine serial** | | | | | | | |
| eng EngramGateP (3 double chains) | 116.07 | 105.04 | -10 % | latency | 1.17 | 99.2 | round18-g82-pf_new-decode-profile-card2.txt |
| **engine small** | | | | | | | |
| eng HcPostPreP | 1.24 | 1.09 | -12 % | latency | 1.05 | 1.2 | round18-g82-pf_new-decode-profile-card2.txt |
| eng WindowAppendP | 2.14 | 1.24 | -42 % | latency | 0.66 | 3.3 | round18-g82-pf_new-decode-profile-card2.txt |
| eng SwigluBothS | 1.10 | 1.25 | +14 % | latency | 0.71 | 1.6 | round18-g82-pf_new-decode-profile-card2.txt |
| eng MoeCombineA | 1.48 | 1.53 | +4 % | latency | 0.71 | 2.1 | round18-g82-pf_new-decode-profile-card2.txt |
| eng RowsP<RopeRows> | 0.92 | 0.91 | -1 % | latency | 0.65 | 1.4 | round18-g82-pf_new-decode-profile-card2.txt |
| **bench dense m16** | | | | | | | |
| d3 Q8_0 6144x1280 engine G4 R4 | 105.10 | 79.91 | -24 % | issue | 19.31 | 5.4 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 6144x1280 G4R4 D0V0 | 101.10 | 79.91 | -21 % | issue | 19.31 | 5.2 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 6144x1280 G4R4 D1V0 | 155.20 | 158.67 | +2 % | latency | 21.79 | 7.1 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 6144x1280 G4R4 D2V0 | 132.00 | 106.75 | -19 % | issue | 21.79 | 6.1 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 6144x1280 G4R4 D0V1 | 100.80 | 79.89 | -21 % | issue | 19.31 | 5.2 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 6144x1280 G4R4 D0V2 | 97.50 | 77.53 | -20 % | issue | 19.31 | 5.0 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 6144x1280 G4R4 D0V3 | 96.70 | 76.24 | -21 % | issue | 19.31 | 5.0 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 6144x1280 G4R4 D2V1 | 132.00 | 106.75 | -19 % | issue | 21.79 | 6.1 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 6144x1280 G4R4 D2V2 | 131.20 | 106.79 | -19 % | issue | 21.79 | 6.0 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 6144x1280 G4R4 D2V3 | 134.40 | 105.61 | -21 % | issue | 21.79 | 6.2 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 6144x1280 G8R2 D0V0 | 105.40 | 68.24 | -35 % | issue | 19.31 | 5.5 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 6144x1280 G8R2 D1V0 | 126.00 | 94.82 | -25 % | latency | 21.79 | 5.8 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 6144x1280 G8R2 D2V0 | 113.20 | 84.44 | -25 % | issue | 21.79 | 5.2 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 6144x1280 G8R2 D0V1 | 105.70 | 68.24 | -35 % | issue | 19.31 | 5.5 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 6144x1280 G8R2 D0V2 | 99.00 | 70.92 | -28 % | issue | 21.79 | 4.5 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 6144x1280 G8R2 D0V3 | 105.80 | 67.50 | -36 % | issue | 19.31 | 5.5 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 6144x1280 G8R2 D2V1 | 112.70 | 84.44 | -25 % | issue | 21.79 | 5.2 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 6144x1280 G8R2 D2V2 | 112.10 | 84.44 | -25 % | issue | 21.79 | 5.1 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 6144x1280 G8R2 D2V3 | 112.70 | 83.78 | -26 % | issue | 21.79 | 5.2 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 1792x5120 engine G4 | 80.90 | 94.32 | +17 % | port | 23.43 | 3.5 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 1792x5120 G4 D0V0 | 80.20 | 94.31 | +18 % | port | 23.43 | 3.4 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 1792x5120 G4 D1V0 | 98.40 | 125.36 | +27 % | issue | 23.43 | 4.2 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 1792x5120 G4 D2V0 | 89.30 | 120.11 | +34 % | issue | 23.43 | 3.8 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 1792x5120 G4 D0V1 | 80.70 | 94.31 | +17 % | port | 23.43 | 3.4 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 1792x5120 G4 D0V2 | 80.00 | 94.54 | +18 % | port | 23.43 | 3.4 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 1792x5120 G4 D0V3 | 79.40 | 94.16 | +19 % | port | 23.43 | 3.4 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 1792x5120 G4 D2V1 | 88.90 | 120.24 | +35 % | issue | 23.43 | 3.8 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 1792x5120 G4 D2V2 | 83.10 | 121.74 | +46 % | issue | 23.43 | 3.5 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 1792x5120 G4 D2V3 | 86.90 | 118.92 | +37 % | issue | 23.43 | 3.7 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 1792x5120 G8R2 D0V0 | 70.30 | 64.24 | -9 % | issue | 21.78 | 3.2 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 1792x5120 G8R2 D1V0 | 97.20 | 111.16 | +14 % | latency | 21.78 | 4.5 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 1792x5120 G8R2 D2V0 | 85.30 | 82.45 | -3 % | issue | 21.78 | 3.9 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 1792x5120 G8R2 D0V1 | 70.60 | 64.24 | -9 % | issue | 21.78 | 3.2 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 1792x5120 G8R2 D0V2 | 66.60 | 63.44 | -5 % | issue | 21.78 | 3.1 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 1792x5120 G8R2 D0V3 | 66.70 | 62.69 | -6 % | issue | 21.78 | 3.1 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 1792x5120 G8R2 D2V1 | 85.00 | 82.49 | -3 % | issue | 21.78 | 3.9 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 1792x5120 G8R2 D2V2 | 86.20 | 82.37 | -4 % | issue | 21.78 | 4.0 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 1792x5120 G8R2 D2V3 | 88.20 | 81.99 | -7 % | issue | 21.78 | 4.1 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x8192 engine G4 | 67.00 | 71.23 | +6 % | port | 17.68 | 3.8 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x8192 G4 D0V0 | 65.60 | 71.39 | +9 % | port | 17.68 | 3.7 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x8192 G4 D1V0 | 82.40 | 95.47 | +16 % | issue | 17.68 | 4.7 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x8192 G4 D2V0 | 74.20 | 89.98 | +21 % | issue | 17.68 | 4.2 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x8192 G4 D0V1 | 65.50 | 71.39 | +9 % | port | 17.68 | 3.7 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x8192 G4 D0V2 | 66.10 | 71.38 | +8 % | port | 17.68 | 3.7 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x8192 G4 D0V3 | 65.00 | 71.12 | +9 % | port | 17.68 | 3.7 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x8192 G4 D2V1 | 72.50 | 90.07 | +24 % | issue | 17.68 | 4.1 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x8192 G4 D2V2 | 70.30 | 91.37 | +30 % | issue | 17.68 | 4.0 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x8192 G4 D2V3 | 73.40 | 89.00 | +21 % | issue | 17.68 | 4.2 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x8192 G8R2 D0V0 | 52.70 | 47.77 | -9 % | issue | 16.85 | 3.1 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x8192 G8R2 D1V0 | 82.20 | 109.42 | +33 % | latency | 16.85 | 4.9 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x8192 G8R2 D2V0 | 71.80 | 66.76 | -7 % | issue | 16.85 | 4.3 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x8192 G8R2 D0V1 | 53.10 | 47.80 | -10 % | issue | 16.85 | 3.2 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x8192 G8R2 D0V2 | 61.60 | 47.68 | -23 % | issue | 16.85 | 3.7 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x8192 G8R2 D0V3 | 62.30 | 47.21 | -24 % | issue | 16.85 | 3.7 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x8192 G8R2 D2V1 | 66.60 | 61.62 | -8 % | issue | 16.85 | 4.0 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x8192 G8R2 D2V2 | 66.40 | 61.50 | -7 % | issue | 16.85 | 3.9 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x8192 G8R2 D2V3 | 66.90 | 61.15 | -9 % | issue | 16.85 | 4.0 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x2304 engine G4 | 26.80 | 22.18 | -17 % | issue | 6.04 | 4.4 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x2304 G4 D0V0 | 26.60 | 22.19 | -17 % | issue | 6.04 | 4.4 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x2304 G4 D1V0 | 32.60 | 29.80 | -9 % | issue | 6.04 | 5.4 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x2304 G4 D2V0 | 29.60 | 28.46 | -4 % | issue | 6.04 | 4.9 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x2304 G4 D0V1 | 26.60 | 22.19 | -17 % | issue | 6.04 | 4.4 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x2304 G4 D0V2 | 26.00 | 22.28 | -14 % | issue | 6.04 | 4.3 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x2304 G4 D0V3 | 26.50 | 22.08 | -17 % | issue | 6.04 | 4.4 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x2304 G4 D2V1 | 29.40 | 28.51 | -3 % | issue | 6.04 | 4.9 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x2304 G4 D2V2 | 28.90 | 28.42 | -2 % | issue | 6.04 | 4.8 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x2304 G4 D2V3 | 28.10 | 28.42 | +1 % | issue | 6.04 | 4.7 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x2304 G4R2 D0V0 | 23.80 | 18.41 | -23 % | issue | 5.21 | 4.6 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x2304 G4R2 D1V0 | 29.80 | 27.06 | -9 % | issue | 5.21 | 5.7 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x2304 G4R2 D2V0 | 27.10 | 25.80 | -5 % | issue | 5.21 | 5.2 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x2304 G4R2 D0V1 | 23.60 | 18.44 | -22 % | issue | 5.21 | 4.5 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x2304 G4R2 D0V2 | 23.30 | 18.41 | -21 % | issue | 5.21 | 4.5 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x2304 G4R2 D0V3 | 23.60 | 18.14 | -23 % | issue | 5.21 | 4.5 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x2304 G4R2 D2V1 | 27.30 | 25.92 | -5 % | issue | 5.21 | 5.2 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x2304 G4R2 D2V2 | 26.60 | 25.84 | -3 % | issue | 5.21 | 5.1 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 864x2304 G4R2 D2V3 | 26.60 | 25.49 | -4 % | issue | 5.21 | 5.1 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 768x4096 engine G4 | 37.10 | 32.95 | -11 % | port | 8.73 | 4.2 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 768x4096 G4 D0V0 | 36.90 | 32.94 | -11 % | port | 8.73 | 4.2 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 768x4096 G4 D1V0 | 46.70 | 46.90 | +0 % | latency | 8.73 | 5.3 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 768x4096 G4 D2V0 | 42.60 | 42.04 | -1 % | issue | 8.73 | 4.9 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 768x4096 G4 D0V1 | 36.90 | 32.94 | -11 % | port | 8.73 | 4.2 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 768x4096 G4 D0V2 | 37.70 | 33.04 | -12 % | port | 8.73 | 4.3 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 768x4096 G4 D0V3 | 37.00 | 32.85 | -11 % | port | 8.73 | 4.2 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 768x4096 G4 D2V1 | 42.80 | 42.07 | -2 % | issue | 8.73 | 4.9 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 768x4096 G4 D2V2 | 40.40 | 42.59 | +5 % | issue | 8.73 | 4.6 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 768x4096 G4 D2V3 | 41.50 | 41.65 | +0 % | issue | 8.73 | 4.8 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 768x4096 G2R4 D0V0 | 34.40 | 34.65 | +1 % | issue | 7.90 | 4.4 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 768x4096 G2R4 D1V0 | 101.80 | 170.10 | +67 % | latency | 8.73 | 11.7 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 768x4096 G2R4 D2V0 | 83.90 | 66.89 | -20 % | latency | 8.73 | 9.6 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 768x4096 G2R4 D0V1 | 34.30 | 34.65 | +1 % | issue | 7.90 | 4.3 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 768x4096 G2R4 D0V2 | 36.60 | 33.91 | -7 % | issue | 7.90 | 4.6 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 768x4096 G2R4 D0V3 | 32.60 | 32.87 | +1 % | issue | 7.90 | 4.1 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 768x4096 G2R4 D2V1 | 80.90 | 64.81 | -20 % | latency | 8.73 | 9.3 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 768x4096 G2R4 D2V2 | 80.60 | 65.26 | -19 % | latency | 8.73 | 9.2 | round18-d3-dense-m16-decode-variants.txt |
| d3 Q8_0 768x4096 G2R4 D2V3 | 80.80 | 64.54 | -20 % | latency | 8.73 | 9.3 | round18-d3-dense-m16-decode-variants.txt |
| d4 Q6_K 6144x1280 engine G4 R4 | 114.80 | 99.86 | -13 % | issue | 18.02 | 6.4 | round18-d4-dense-m16-q6k-forms.txt |
| d4 Q6_K 6144x1280 G4 | 107.00 | 117.28 | +10 % | issue | 22.99 | 4.7 | round18-d4-dense-m16-q6k-forms.txt |
| d4 Q6_K 6144x1280 G8 | 109.50 | 93.58 | -14 % | issue | 22.99 | 4.8 | round18-d4-dense-m16-q6k-forms.txt |
| d4 Q6_K 6144x1280 G4 R2 | 116.10 | 104.51 | -10 % | issue | 18.02 | 6.4 | round18-d4-dense-m16-q6k-forms.txt |
| d4 Q6_K 6144x1280 G8 R2 | 107.50 | 80.87 | -25 % | issue | 18.02 | 6.0 | round18-d4-dense-m16-q6k-forms.txt |
| d4 Q6_K 6144x1280 G2 R4 | 131.50 | 144.32 | +10 % | issue | 18.02 | 7.3 | round18-d4-dense-m16-q6k-forms.txt |
| d4 Q6_K 1792x5120 engine G4 | 144.50 | 126.07 | -13 % | latency | 18.98 | 7.6 | round18-d4-dense-m16-q6k-forms.txt |
| d4 Q6_K 1792x5120 G8 | 92.80 | 91.51 | -1 % | port | 18.98 | 4.9 | round18-d4-dense-m16-q6k-forms.txt |
| d4 Q6_K 1792x5120 G4 R2 | 89.60 | 104.17 | +16 % | issue | 18.98 | 4.7 | round18-d4-dense-m16-q6k-forms.txt |
| d4 Q6_K 1792x5120 G4 R4 | 95.00 | 106.10 | +12 % | issue | 17.32 | 5.5 | round18-d4-dense-m16-q6k-forms.txt |
| d4 Q6_K 1792x5120 G8 R2 | 92.70 | 82.13 | -11 % | issue | 17.32 | 5.4 | round18-d4-dense-m16-q6k-forms.txt |
| d4 Q6_K 1792x5120 G2 R4 | 138.20 | 189.73 | +37 % | latency | 18.98 | 7.3 | round18-d4-dense-m16-q6k-forms.txt |
| d4 Q6_K 864x8192 engine G4 | 77.90 | 87.20 | +12 % | issue | 15.89 | 4.9 | round18-d4-dense-m16-q6k-forms.txt |
| d4 Q6_K 864x8192 G8 | 87.00 | 71.65 | -18 % | port | 14.23 | 6.1 | round18-d4-dense-m16-q6k-forms.txt |
| d4 Q6_K 864x8192 G4 R2 | 75.50 | 90.03 | +19 % | latency | 14.23 | 5.3 | round18-d4-dense-m16-q6k-forms.txt |
| d4 Q6_K 864x8192 G4 R4 | 84.30 | 92.25 | +9 % | latency | 13.41 | 6.3 | round18-d4-dense-m16-q6k-forms.txt |
| d4 Q6_K 864x8192 G8 R2 | 80.80 | 73.24 | -9 % | latency | 13.41 | 6.0 | round18-d4-dense-m16-q6k-forms.txt |
| d4 Q6_K 864x8192 G2 R4 | 124.60 | 147.30 | +18 % | latency | 14.23 | 8.8 | round18-d4-dense-m16-q6k-forms.txt |
| d4 Q6_K 768x4096 engine G4 | 72.00 | 50.72 | -30 % | latency | 7.20 | 10.0 | round18-d4-dense-m16-q6k-forms.txt |
| d4 Q6_K 768x4096 G8 | 41.10 | 32.29 | -21 % | port | 7.20 | 5.7 | round18-d4-dense-m16-q6k-forms.txt |
| d4 Q6_K 768x4096 G4 R2 | 39.70 | 39.02 | -2 % | latency | 7.20 | 5.5 | round18-d4-dense-m16-q6k-forms.txt |
| d4 Q6_K 768x4096 G4 R4 | 45.90 | 48.06 | +5 % | latency | 6.37 | 7.2 | round18-d4-dense-m16-q6k-forms.txt |
| d4 Q6_K 768x4096 G8 R2 | 54.00 | 30.76 | -43 % | latency | 6.37 | 8.5 | round18-d4-dense-m16-q6k-forms.txt |
| d4 Q6_K 768x4096 G2 R4 | 51.60 | 59.51 | +15 % | latency | 7.20 | 7.2 | round18-d4-dense-m16-q6k-forms.txt |
| **bench dense warm** | | | | | | | |
| rt5 D shared gate+up rows alone | 6.56 | 8.81 | +34 % | issue | 1.69 | 3.9 | round18-rt5-route-rows-bench.txt |
| **bench fp64 rows** | | | | | | | |
| n5 C mix dots alone @wg512 | 9.69 | 9.63 | -1 % | issue | 1.16 | 8.3 | round18-n5-norm-ff-bench.txt |
| n5 N mix dots alone @wg128 | 5.73 | 5.76 | +0 % | latency | 1.16 | 4.9 | round18-n5-norm-ff-bench.txt |
| n5 O mix dots alone @wg64 | 5.73 | 5.76 | +0 % | latency | 1.16 | 4.9 | round18-n5-norm-ff-bench.txt |
| **bench fused** | | | | | | | |
| n5 A norm(chain) + mix dots @wg512 | 9.90 | 10.10 | +2 % | issue | 1.17 | 8.4 | round18-n5-norm-ff-bench.txt |
| n5 G norm(fast) + mix dots @wg512 | 9.90 | 9.76 | -1 % | issue | 1.17 | 8.4 | round18-n5-norm-ff-bench.txt |
| n5 J norm(chain) + mix dots @wg128 | 9.06 | 8.91 | -2 % | latency | 1.17 | 7.7 | round18-n5-norm-ff-bench.txt |
| n5 L norm(fast) + mix dots @wg128 | 6.04 | 5.91 | -2 % | latency | 1.17 | 5.1 | round18-n5-norm-ff-bench.txt |
| n5 K norm(chain) + mix dots @wg64 | 9.27 | 8.91 | -4 % | latency | 1.17 | 7.9 | round18-n5-norm-ff-bench.txt |
| n5 M norm(fast) + mix dots @wg64 | 6.04 | 5.91 | -2 % | latency | 1.17 | 5.1 | round18-n5-norm-ff-bench.txt |
| **bench serial** | | | | | | | |
| n5 B norm 5120 chain | 5.52 | 8.91 | +62 % | latency | 0.66 | 8.4 | round18-n5-norm-ff-bench.txt |
| n5 F norm 5120 fast bracket | 5.62 | 5.74 | +2 % | latency | 0.66 | 8.6 | round18-n5-norm-ff-bench.txt |
| n5 H norm 1280 chain | 3.54 | 3.57 | +1 % | latency | 0.65 | 5.5 | round18-n5-norm-ff-bench.txt |
| n5 I norm 1280 fast bracket | 2.81 | 3.17 | +13 % | latency | 0.65 | 4.3 | round18-n5-norm-ff-bench.txt |
| n5 E1 fast norm V1 alone | 5.62 | 5.34 | -5 % | latency | 0.66 | 8.6 | round18-n5-norm-ff-bench.txt |
| n5 E2 fast norm, no fallback | 4.69 | 5.24 | +12 % | latency | 0.66 | 7.1 | round18-n5-norm-ff-bench.txt |
| n5 E3 fast sum, no check | 4.69 | 5.24 | +12 % | latency | 0.66 | 7.1 | round18-n5-norm-ff-bench.txt |
| n5 E0 fast norm, two roots | 11.56 | 11.08 | -4 % | latency | 0.66 | 17.6 | round18-n5-norm-ff-bench.txt |
| rt5 C mix finish alone (1 sub-group) | 6.67 | 12.13 | +82 % | latency | 0.65 | 10.3 | round18-rt5-route-rows-bench.txt |
| rt5 H router scores only | 0.94 | 1.92 | +104 % | latency | 0.65 | 1.4 | round18-rt5-route-rows-bench.txt |
| rp3 V2 Sets<PickV<2> > | 2.71 | 2.44 | -10 % | latency | 0.65 | 4.2 | rp/r3/out.txt |
| rp3 V5 Sets<PickV<5> > | 1.04 | 1.65 | +59 % | latency | 0.65 | 1.6 | rp/r3/out.txt |
| rp3 V7 Sets<Empty> | 0.52 | 0.78 | +49 % | latency | 0.65 | 0.8 | rp/r3/out.txt |
| eg2 A engram chains (engine82 code, warm) | 96.14 | 105.04 | +9 % | latency | 0.71 | 135.2 | eg/r2/bench_engram_ff.txt |
| **bench branchy** | | | | | | | |
| rt5 B RouteP alone (two=False) (not fitted) | 21.35 | 10.46 | -51 % | latency | 0.65 | 32.9 | round18-rt5-route-rows-bench.txt |
| rt5 K RouteP alone (two=True) (not fitted) | 9.17 | 10.46 | +14 % | latency | 0.65 | 14.1 | round18-rt5-route-rows-bench.txt |
| rt5 I RouteQ alone (not fitted) | 8.65 | 4.28 | -50 % | latency | 0.65 | 13.3 | round18-rt5-route-rows-bench.txt |
| rp3 V0 Sets<RouteP> (not fitted) | 8.65 | 9.56 | +10 % | latency | 0.65 | 13.4 | rp/r3/out.txt |
| rp3 V1 Sets<PickV<1> > (not fitted) | 8.54 | 4.30 | -50 % | latency | 0.65 | 13.2 | rp/r3/out.txt |
| rp3 V3 Sets<PickV<3> > (not fitted) | 8.12 | 3.70 | -54 % | latency | 0.65 | 12.6 | rp/r3/out.txt |
| rp3 V4 Sets<PickV<4> > (not fitted) | 10.11 | 3.69 | -64 % | latency | 0.65 | 15.6 | rp/r3/out.txt |
| rp3 V6 Sets<PickV<6> > (not fitted) | 8.54 | 4.40 | -48 % | latency | 0.65 | 13.2 | rp/r3/out.txt |
| rp3 V8 Sets<PickV<8> > (not fitted) | 6.67 | 4.84 | -27 % | latency | 0.65 | 10.3 | rp/r3/out.txt |
| rp3 V9 Sets<PickV<9> > (not fitted) | 3.33 | 3.62 | +9 % | latency | 0.65 | 5.1 | rp/r3/out.txt |
| rp3 V10 Sets<PickV<10> > (not fitted) | 8.54 | 4.30 | -50 % | latency | 0.65 | 13.2 | rp/r3/out.txt |
| rp3 V11 Sets<PickV<11> > (not fitted) | 4.79 | 3.96 | -17 % | latency | 0.65 | 7.4 | rp/r3/out.txt |
| rp3 V12 Sets<PickC<72> > (not fitted) | 6.04 | 4.25 | -30 % | latency | 0.65 | 9.3 | rp/r3/out.txt |
| rp3 V13 Sets<PickV<13> > (not fitted) | 2.71 | 3.85 | +42 % | latency | 0.65 | 4.2 | rp/r3/out.txt |
| rp3 V14 Sets<PickV<14> > (not fitted) | 3.65 | 3.87 | +6 % | latency | 0.65 | 5.6 | rp/r3/out.txt |
| rp3 V15 Sets<PickV<15> > (not fitted) | 2.81 | 3.94 | +40 % | latency | 0.65 | 4.3 | rp/r3/out.txt |

</details>


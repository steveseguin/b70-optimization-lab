# Ahead-of-time (AOT) build of the SC117 engine for the Arc Pro B70 (2026-10-31)

**Question.** A fresh lab server's first decode half JIT-compiles every kernel: 53-62 s on rank 0, which races the ranks'
60 s `--wait-seconds` deadline (server fc2-r3-c131072 of [hc-split](../tp/hc-split-2026-10-30/RESULT.md) halted on it).
The startup gate's first batched case also compiles the batched-prefill kernels. Does building the SYCL kernels ahead
of time for the B70 (`-fsycl-targets=intel_gpu_bmg_g31`) remove that cost, with outputs bit-identical to the JIT build?

**Answer.** **Yes, and it is exact. Fresh servers are ready about 2.3 minutes sooner, and the first decode half drops from
53 s to 0.08 s, so the 60 s `--wait-seconds` deadline is no longer at risk.**
- Build: AOT build `a1959e7ccf88` of lab build r1 `40388fc92c43`, made with
  `engine/build.py OUT --jobs 4 --name sc117-engine --aot-target intel_gpu_bmg_g31`. Every other compile and link argument
  is r1's. It took 248 s; the binary is 63.5 MB against 31.2 MB.
- Exactness: bit-identical to the JIT build in every harness configuration.
  - 12 one-card JIT/AOT pairs (both ranks, the four-card and the two-card flag sets).
  - The four-card TP harness against one card, and against the archived JIT TP runs.
  - All 7 fresh servers: outputs equal to B19, and the F32 self-tests and state oracles passed.
- No kernel is JIT-compiled at run time: the NEO cache stays empty, where the JIT build fills it with 27-28 modules.
- Four cards at 65536, A/B/A/B (JIT r1 / AOT, same flags):
  - launch to ready 670.1 / 695.3 s -> 528.2 / 553.7 s (**-142 s** in both pairs);
  - first request 106 s -> 1.2 s; first half 53.2 s -> 0.08 s on rank 0;
  - decode unchanged: mean of medians 94.05 -> 94.26 tok/s (noise).
- Two cards (one pair):
  - after the weight load, 476 -> 340 s (-136 s, as on four cards);
  - the raw launch-to-ready gain was only 54 s, because this AOT server's weight load happened to take 82 s longer;
  - decode 72.45 / 72.44 tok/s.
- An AOT server at 131072 with the default 60 s deadline: JIT server fc2-r3 halted there because its first half took
  61-62 s. The AOT server's first half took 83 ms; it was ready in 919 s (JIT: 1051-1072 s with the deadline raised to
  300 s). Its 121,854-token request gave the reference output, unchanged in speed.

## The build (step 1)

- **Binary:** AOT build `a1959e7ccf88` of lab build r1 `40388fc92c43`'s tree (`engine/src` at `979462f7c` +
  [engine-fixed-cost-2.patch](../tp/fixed-cost-2-2026-10-30/engine-fixed-cost-2.patch) +
  [engine-hc-split.patch](../tp/hc-split-2026-10-30/engine-hc-split.patch)). It was built from a private copy of the tree,
  `/dev/shm/aot-tp-2026-10-31/tree`, by [build_aot.py](build_aot.py). Neither `engine/src` nor the r1 tree was written.
- **Recipe:** the engine's own `engine/build.py --aot-target intel_gpu_bmg_g31`, as the 10-28 AOT build
  ([aot-cold-gate](../pp4-review-2026-10-28/aot-cold-gate/RESULT.txt)) did. It adds one argument,
  `-fsycl-targets=intel_gpu_bmg_g31`, to every compile and to the link. **No build-config patch is needed**: `build.py` and
  the manifest already support it.
- **Every other argument is r1's.** `build_aot.py` checks every compile and link argv against r1's
  [build receipt](../tp/hc-split-2026-10-30/results/build-r1-build-receipt.json): they are equal once the tree and build
  paths are swapped and the one target flag is removed. That covers -O2, `-fno-fast-math -ffp-contract=off
  -fdenormal-fp-math=ieee -foffload-fp32-prec-div -foffload-fp32-prec-sqrt` on every compile, the same link line, and the
  pinned `/opt/intel/oneapi/compiler/2026.0/bin/icpx`.
  - The binary's `NEEDED`/`RUNPATH` equal r1's: `libsycl.so.9` through the 2026.0 rpath, `libze_loader.so.1`,
    `libcrypto.so.3`.
  - Toolchain: icpx 2026.0.0 (20260331), ocloc 26.18.38308.1, IGC 2.34.4 (`/usr/local/lib/libigc.so.2.34.4`, the same
    library the Level Zero runtime JIT loads), runtime `libze_intel_gpu` 26.18.38308. These are the 10-28 build's
    identities; hashes are in [results/build-aot-r1.json](results/build-aot-r1.json).
- **Cost:** 247.8 s wall at nice 19 on CPUs 8-15 with `--jobs 4`, peak 2.1 GB (unit), with no fresh-server timing
  running.
  - The compiles take about 120 s of wall time; `entry.o` is the longest at 113 s, and the compile seconds sum to 459.8 s.
  - The link takes 127.9 s, because ocloc now compiles every device image there.
- **Size:** 63.47 MB, against 31.20 MB for the JIT binary.
- **No JIT image is left.** The binary carries one `__CLANG_OFFLOAD_BUNDLE__sycl-spir64_gen` bundle and no `spir64`
  (SPIR-V) image, so the runtime has nothing to compile. At run time each binary had its own NEO cache directory:
  - the AOT cache held **0 files** after all 16 AOT harness arms and after every AOT server (below);
  - the JIT cache received 27 compiled modules (servers: 28 on rank 0, 23 on rank 1).
- **Receipt and compiled-source hashes.**
  - The 269 compiled-source hashes are identical to r1's.
  - The engine receipt [results/engine-receipt-a1959e7ccf88.json](results/engine-receipt-a1959e7ccf88.json) (made by
    [make_receipt.py](make_receipt.py)) pins the absolute paths of the copy in `/dev/shm/aot-tp-2026-10-31`. The lab
    adapter re-hashes those at every launch, so that tree and `build-r1` must stay in place while the receipt is used, as
    r1's do.
  - All 40 objects differ from r1's, as expected (device bitcode for another triple).
  - The receipt also records `aot_target`. The lab adapter ignores it; this folder's suite admits an AOT arm only with it.

**The precision flags.** r1's link line is `-fsycl -Wl,--gc-sections ... -lcrypto -lze_loader` with no offload
precision flags, and the 10-28 AOT build's was the same.
- A `-###` dry run shows that icpx 2026.0 drops `-foffload-fp32-prec-div/-sqrt` from the device compile entirely; they
  act only through the link line.
  - In a JIT build they would add `-foffload-fp32-prec-div -foffload-fp32-prec-sqrt` to the image's compile options
    (r1's image carries only `-ftarget-register-alloc-mode=pvc:-ze-intel-enable-auto-large-GRF-mode`).
  - In an AOT build they would become ocloc `-options`.
- So r1's GPU fp32 divide and sqrt use IGC's default, not correctly rounded (the lab's 2026-10-11 finding: the flags
  take effect only on the link line).
- The AOT build keeps r1's link line exactly, so it makes the same choice, and that is why it can be bit-identical.
- Adding the flags to the link line would change outputs in both builds and needs its own gate and an owner decision. It
  was not done here.

## Exactness (step 2)

Rank harness of [two-card-flags-2026-10-31](../two-card-flags-2026-10-31/RESULT.md) and
[hc-split-2026-10-30](../tp/hc-split-2026-10-30/RESULT.md), copied: [run_phase.sh](run_phase.sh) (each arm names its
binary: extra `jit` or `aot`), [launch_phase.sh](launch_phase.sh), [compare.sh](compare.sh) with the exact-pattern ones
checker ([compare_driver.py](compare_driver.py)), [gates.sh](gates.sh) (arm lists and compare pairs). Verdicts:
[results/gate-summary.json](results/gate-summary.json).

**g1, one card** (0000:43:00.0; 24 arms; every configuration with JIT r1 and with AOT in one phase). Two flag sets:
- "4": the four-card stack's flags as its one-card references ran them (hc-split g1): `rd,hk=1,tf=1`, plus `df=1` on
  rank 0 and `ph,db` in the batched arms;
- "B": [two-card-flags flags.py](../two-card-flags-2026-10-31/flags.py) B, read in place.

| Compare, JIT vs AOT ([logs/g1-compare.txt](logs/g1-compare.txt)) | Result |
| --- | --- |
| rank 1, token by token (128 prompt rows, 64 halves), both sets | 1079/1079 buffers, 64 tokens, 192/192 exported draft-input rows |
| rank 1, batched + RESET + second request ("4": 128 + 64 rows; "B": 600 + 600) | both requests 1079/1079 and tokens, exports 192+128 / 664+664, reset inventories 30/30 twice, ones checker OK |
| rank 0 `h`, `hmcn`, `m`, both sets | 1029/1029 target buffers, 71/71 draft buffers, 64 draft tokens |
| rank 0, batched + RESET + second request ("4": `dc,db`, 64 rows; "B": 600 rows `hmcn` `dc`) | both requests 1029/1029 + 71/71 + draft tokens, inventories 118/118 twice, ones OK |

- All 12 pairs are equal, all 24 arms returned rc 0, and the kernel log was clean before the phase (24 h) and after
  every arm.
- **g1x:** AOT also equals the 12 archived JIT runs of the same configurations on other cards (hc-split g1 on 43:00.0,
  two-card-flags g1 on 47:00.0) ([logs/g1x-compare.txt](logs/g1x-compare.txt)).

**g2, four-card TP rank harness, AOT** (the hsp flags: `ep,rd,hk=1,tf=1` (+`df=1` on rank 0) and
`hs=low+gate+final+prefill`; rank 1 on 23+47, rank 0 on 23+27; [logs/g2-compare.txt](logs/g2-compare.txt)):
- **Token by token against one card** (the AOT and the JIT g1 arms): rank 1 1079/1079 + 64 tokens + 192 exports; rank 0
  1029/1029 + 71/71 + draft tokens.
- **Batched + second request against the archived JIT TP runs with the same flags** (hc-split `g2-r1-onp-b`,
  `g2-r0-onp-db`): fully equal, including the reset inventories (rank 1 63/63, rank 0 294/294). Only `tp-exchange-control`
  is excluded, as timing-only, as in every TP compare.
- **Batched TP against one card:** state, tokens, exports and both requests are equal. The reset inventories differ only
  in layout-specific prefill scratch (TP-only buffers, packing), and the difference records are identical to hc-split's
  JIT-era g2x records (JIT TP against JIT one card).
- Every arm passed the card-1 vs card-0 replicate compare with 0 exchange timeouts; kernel log clean after every arm.

**The harness also shows the startup cost** ([results/g1-g2-halves.json](results/g1-g2-halves.json)):
- The first, cold JIT rank-1 arm read its 128 prompt rows in 47.8 s (AOT: 1.50 s), and its first decode half took 6.2 s.
  The JIT arms after it reused the JIT cache.
- Steady half medians are unchanged:
  - rank 1: 11.32-11.42 ms JIT, 11.34-11.41 ms AOT;
  - rank 0 `h`: 9.90 ms JIT, 9.89 ms AOT;
  - TP: rank 1 8.52 ms, rank 0 7.67 ms (hc-split's JIT r1: 8.53 / 7.68 ms).

## Startup and timing (step 3)

Fresh lab servers, A = JIT r1 `40388fc92c43`, B = AOT `a1959e7ccf88`, same flags, same lab service and adapter.
- Tooling: [suite/](suite/), a copy of two-card-flags-2026-10-31's suite, which includes the `ONE_CARD_KEYS` adapter fix.
  It adds hc-split's hsp arm and long probe, and [suite/startup_metrics.py](suite/startup_metrics.py).
- The chain [suite/run_endgate.sh](suite/run_endgate.sh) ran in unit `sc117-tp-svc-aot-chain-20261031`. Its lock holder
  waited 66 min for another agent's 131072 chain. Then, with no other timing or build running:
  - four cards hspJ-r1, hspA-r1, hspJ-r2, hspA-r2;
  - two cards twoBJ-r1, twoBA-r1;
  - hspA60-r1 at 131072.
- Every server ran once, in a fresh transient unit: Restart=no, KillMode=process, no SIGKILL, LimitNOFILE=1048576,
  nice 19, CPUs 0-3,16-19, `NEOReadDebugKeys=1 EnableDeferBacking=0`. Each passed:
  - the preconditions and a kernel-log check (sudo) before the run, after ready, after the suite and after the stop
    (all clean; one benign apparmor line from a snap timer);
  - the load, the F32 self-tests and the 4096/65536 (and 131072) state oracles;
  - the 13/13 startup gate;
  - the 12-prompt suite, the 3,490-token TTFT request, a graceful stop and `terminal.json`.
- Rank environments were read from `/proc` after ready ([suite/logs/rank-env-*.txt](suite/logs/)):
  - all A/B ranks passed `--wait-seconds 300` (`SC117_LAB_WAIT_SECONDS`, both arms alike);
  - hspA60's ranks had no `--wait-seconds` (default 60 s);
  - twoB ranks carried the flags.py B keys.

| Server | Launch -> ready | Weight load | Load -> ready | First request | First half r0 / r1 | Startup gate (first batched case) | NEO cache r0/r1 | Median tok/s | Outputs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| hspJ-r1 (4 cards, JIT) | 670.1 s | 130.2 s | 539.9 s | 106.4 s | 53.24 / 46.76 s | 397.8 s (27.97 s) | 28 / 23 | 94.15 | = B19 |
| **hspA-r1 (AOT)** | **528.2 s** | 122.6 s | **405.6 s** | **1.19 s** | **0.079 / 0.068 s** | 369.2 s (1.22 s) | **0 / 0** | 94.16 | = B19 |
| hspJ-r2 | 695.3 s | 154.7 s | 540.6 s | 105.9 s | 53.17 / 46.32 s | 399.0 s (28.01 s) | 28 / 23 | 93.94 | = B19 |
| **hspA-r2** | **553.7 s** | 147.1 s | **406.6 s** | **1.20 s** | **0.076 / 0.069 s** | 370.1 s (1.22 s) | **0 / 0** | 94.37 | = B19 |
| twoBJ-r1 (2 cards, JIT) | 622.2 s | 145.8 s | 476.4 s | 112.0 s | 53.23 / 46.32 s | 335.2 s (28.51 s) | 27 / 22 | 72.45 | = B19 |
| **twoBA-r1 (AOT)** | **568.2 s** | 228.2 s | **340.0 s** | **1.44 s** | **0.066 / 0.053 s** | 309.5 s (1.67 s) | **0 / 0** | 72.44 | = B19 |
| **hspA60-r1 (AOT, 131072, 60 s)** | **918.7 s** | 166.4 s | **752.3 s** | **1.22 s** | **0.083 / 0.077 s** | 681.4 s (1.23 s) | **0 / 0** | 93.96 | = B19 |
| *hc-split hsp-r4 (JIT, 131072, 300 s)* | *1051.4 s* | *156.7 s* | *894.7 s* | *123.5 s* | *61.68 / 55.37 s* | *701.6 s (27.95 s)* | *29 / 24* | *93.94* | *= B19* |

Definitions ([suite/startup_metrics.py](suite/startup_metrics.py); [results/startup-summary.json](results/startup-summary.json)):
- *Launch -> ready*: the unit's systemd start to the service's `{"ready": true}` journal line.
- *Weight load*: launch to the start of the first request, the ranks' load.
- *First request*: self-test 1 (87 prompt tokens token by token, 32 outputs; warm: 1.1-1.9 s).
- *First half*: each rank's first decode half (`timings.jsonl` position 0; the JIT build compiles inside its enqueue loop).
- *Startup gate*: the 13-case batched-prefill gate, start of its first request to end of its last; its first batched case
  compiles the batched-prefill kernels under JIT.

**Where the time goes.**
- AOT removes 134-142 s from every server after the weight load:
  - four cards: -134.3 and -134.0 s at 65536, -142.4 s at 131072 (against hc-split's JIT hsp-r4);
  - two cards: -136.4 s.
- That is the first request (about -105 s; -110 s on two cards), the startup gate's first batched case (-27 s), and a few
  seconds more of first-use costs inside the gate.
- The raw launch-to-ready gain is that plus the weight-load noise: -141.9 s and -141.6 s in the two four-card pairs,
  -54.0 s in the two-card pair.
  - twoBA's ranks took 197 s against 114 s to load their weights (rank `host-status-before_load` to `after_load` file
    times), before any kernel ran. No other lab job or archive was found running then.
  - AOT does not slow the load: the four-card AOT loads were 7.6 s faster.
  - Model-file reads from disk and page cache vary from server to server. The coordinator judged a second two-card pair
    unnecessary.
- The JIT first half sits at 53 s on rank 0 at 65536 and 62 s at 131072. The AOT first half is 66-83 ms, so the 60 s
  deadline has 59.9 s of margin instead of -2 to +7 s.

**Speed and outputs are unchanged** ([suite/results/suite/summary.json](suite/results/suite/summary.json)).
- Four cards at 65536: mean of medians JIT 94.05, AOT 94.26 tok/s (+0.23%). Per prompt AOT/JIT is 0.997-1.011, and both
  are within the 94.04/94.31 that hc-split measured for the same JIT configuration.
- Two cards: 72.45 against 72.44 tok/s, per prompt 0.9995-1.0006 (two-card-flags measured 72.46/72.44).
- TTFT for the 3,490-token prompt: 6.39-6.42 s on four cards, 9.95 s on two cards, in both arms.
- On all 7 servers, every output id, sha256 and MTP guess/hit equals B19 (`f32-suite-51f32b2655cc-ctx65536-split23.json`),
  with 0 cached tokens.
- hspA60's 121,854-token / 512-output request matches the JIT hsp-r4 run:
  - TTFT 215.85 s (JIT 215.69 s), decode 89.88 tok/s (JIT 89.82);
  - output ids `bf1f0867d1bd`, equal to the 3+1 262K reference, MTP 418/511, identical to JIT.

## What a service would change

- **The build.** Make the binary with the same tree and toolchain:
  `python3 -B engine/build.py OUT --jobs 4 --name sc117-engine --aot-target intel_gpu_bmg_g31`.
  - Run it at nice 19 with limited -j, never during anyone's timing.
  - It takes about 4 min at -j4 with no other load.
  - Then write an engine receipt for it, as [make_receipt.py](make_receipt.py) does, and point `SC117_ENGINE_RECEIPT` at
    it.
  - No source, flag, environment or adapter change is needed: `build.py` and the manifest already carry
    `--aot-target`.
- **The deadline workaround can go.** The lab adapters' `SC117_LAB_WAIT_SECONDS=300` (hc-split's 131072 servers, all of
  two-card-flags' servers) was only there for the cold-JIT first half. With AOT, the default 60 s deadline was shown
  enough at 131072, the case that failed.
- **The NEO cache.** Each launch's fresh NEO cache directory stays empty, so it needs no space and no warm-up. Do not
  pre-populate a JIT cache instead: a persistent cache is not a fresh-cold start, and it is keyed to the driver.
- **Re-gate on any toolchain change.**
  - The binary is BMG-G31-only. It has no SPIR-V fallback, so it will not run on another GPU, and a JIT build is still
    needed for anything else.
  - Its device code is fixed by the build host's ocloc and IGC. That pins the device code against runtime driver updates,
    whereas a JIT binary silently recompiles with the runtime's IGC.
  - So an icpx, ocloc, IGC or driver change needs a new AOT build and a bitwise gate against the JIT build (this folder's
    g1/g2) before the service uses it.
  - Identities of this build: icpx 2026.0.0 (20260331), ocloc 26.18.38308.1, IGC 2.34.4, `libze_intel_gpu` 26.18.38308.
- **The receipt pins a tree.** As with r1, the engine receipt pins the absolute paths of the tree the binary was built
  from. The adapter re-hashes all 269 compiled sources and 40 objects at every launch, and the engine reads
  `rope-65536.bf16` next to its compiled `main.cpp`. A service build needs its tree and build directory kept in place,
  or a receipt rewritten for wherever they are restored.
- **What stays open.**
  - r1's engine changes (fixed-cost-2, hc-split) are still not in the shared `engine/src`; the AOT treatment applies to
    whatever tree is built.
  - The committed LAN service (`serving/lan`) was not touched; it runs B19.
  - The JIT-vs-AOT equality holds for r1's link line, which carries no offload precision flags (above). If the owner
    adds them, both builds change and the oracles must be re-recorded.

## Files

- Build: [build_aot.py](build_aot.py), [make_receipt.py](make_receipt.py); record [results/build-aot-r1.json](results/build-aot-r1.json),
  build receipt [results/build-aot-r1-build-receipt.json](results/build-aot-r1-build-receipt.json), engine receipt
  [results/engine-receipt-a1959e7ccf88.json](results/engine-receipt-a1959e7ccf88.json), logs `logs/build-aot-r1.*`.
- Exactness: [gates.sh](gates.sh), [run_phase.sh](run_phase.sh), [launch_phase.sh](launch_phase.sh), [compare.sh](compare.sh),
  [compare_driver.py](compare_driver.py), [klog.py](klog.py), [drivers/](drivers/), [archive_runs.sh](archive_runs.sh), [archive_build.sh](archive_build.sh);
  `logs/g1*.txt`, `logs/g2*.txt`, [results/gate-summary.json](results/gate-summary.json).
- End gate: [suite/](suite/) (copy of two-card-flags-2026-10-31's suite with hc-split's hsp arm and long probe:
  [suite/arm_env.py](suite/arm_env.py) arms hspJ/hspA/hspA60/twoBJ/twoBA, [suite/run_endgate.sh](suite/run_endgate.sh),
  [suite/startup_metrics.py](suite/startup_metrics.py)).
- Raw runs (each verified by its `.sha256` beside it; the /dev/shm run copies were removed after verification):
  - gate runs: `/mnt/raid-models/ownrt-experiment-archives/2026-10-31/aot-tp-gates-runs` (the 28 g1/g2 runs);
  - end gate: `.../2026-10-31/aot-tp-endgate` (all seven servers' work directories);
  - the AOT build and its tree: `.../2026-10-31/engine-builds/aot-tp-r1`. The `/dev/shm/aot-tp-2026-10-31/{tree,build-r1}`
    copies stay in place, because the receipt pins them.

## Incidents

- No device incident: the kernel log was clean before every phase and after every arm and server (24 h window before
  g1/g2).
- No halts or retries.
- The tooling's first launch of the build unit failed before any build: `python3 build_aot.py` was run with a relative
  path from the unit's home directory. It was relaunched with the absolute path (unit `aot-tp-build-r1b`).
- Scheduling:
  - the build waited for another agent's 131072 timing chain (02:19-03:27);
  - g1 waited 15 min and g2 16 min for that agent's four-card harness phases;
  - the end gate's lock holder waited 66 min for its next chain;
  - nothing of this folder ran during their timing.

# Current Workspace State

Consolidated **2026-10-10** from the recorded ledger; this summary does not establish freshly verified host state.

The full 5,077-line source is preserved byte-for-byte in [CURRENT-history-20261010.md](CURRENT-history-20261010.md), at the same directory level so its relative links retain their meaning.

Source commit: `f7b5356bafa5bc2af06e9dffbc88822fb0d2cded`. Archive SHA256: `b0dec25fb12e796963454e28101c88b8f53c7678fff48b0c11504b5ca642036c`.

The [repository cleanup audit](audits/repository-cleanup/README.md) records the inventory, preservation rules and exact dispositions. The graph-safe research tree remains protected and in place; this consolidation archives only this page's
chronology.

## Authority And Update Rule

This is the sole cross-repository authority for recorded host state, active lanes, protected work and next actions. [AGENTS.md](AGENTS.md) supplies the owner's standing rules. Verify Git status, lane ownership, relevant processes/listeners and the
actual endpoint before operational changes; a deployable recipe does not establish what is running.

Update the affected host and lane here when ground truth changes, in the same commit as the work. Keep detailed chronology and receipts in lane notes, and date unresolved owner decisions. The [October archive](CURRENT-history-20261010.md) and
[September archive](CURRENT-history-20260909.md) are history: their launch, service, restart and cleanup instructions do not authorize new action.

## Recorded Host State

| Host | Latest operational observation in the source ledger | Current constraint |
| --- | --- | --- |
| Four B70: `steve-b70s`, 128 GiB installed, bad-memory blocks fenced | **2026-10-11 05:47 exit / 05:52 watch, UTC:** fixed Flash-Next mmap-line proof exited cleanly; profile and completed post-exit watch recorded no new faults ([closure](notes/2026-10-11-fourth-incident-closed.md)) | Fourth incident closed; future work needs current coordinator admission; LTX remains off. This is a run receipt, not a fresh host-wide idle check. |
| Two B70: `steve-TURIND8-2L2T` (turin), 15 GiB ECC RAM | **2026-10-12 10:47 EDT:** the owner-requested Gemma 4 26B Q8 LAN service is on both cards again and answers, after context campaign 11 (03:12-06:03, nine runs) and campaign 12 (06:26-10:47, eleven runs from one research-server start; no GPU fault line in either). **The guard events at the end of 1M-token proxy runs are explained and fixed:** `summarize_results.py`, run by the job script right after a trial, held 1.7 GB of context snapshots at once (2.1 GB resident beside a server with about 2 GB spare); it holds one at a time now (50 MB) and the server stayed up after both 1M runs of campaign 12. The campaign 11 server was the last one stopped that way (05:58, idle, after its last run). **2026-10-12 02:17 EDT:** the owner-requested Gemma 4 26B Q8 LAN service (`gemma4-26b-q8-quad-*` units, `throughput` recipe, port 8000) is on both cards again and answers, after context campaign 10 held them from 17:47 to 23:32 on October 11 (one research-server start, 24 runs from a queue) and campaign 10b from 23:58 to 02:17 (nine runs, server stopped cleanly); no GPU fault line in either. The guard (1.6 GiB floor) stopped that server at 23:27, idle, two seconds after the last client was ended: for the third time the cause was a client's end-of-run bookkeeping after a 1M-token run; its three queued runs were made in campaign 10b. The long-horizon context lane takes the cards for a few hours at a time: its runner stops Gemma, runs one two-card Qwen 27B FP8 research server, and puts Gemma back. Round 3's server was stopped by the host memory guard at 03:15 (launched at the 2.0 GiB default instead of the owner-approved 1.6 GiB research floor); no GPU fault line, Gemma reloaded on both cards afterwards. **16:35 EDT:** the guard (1.6 GiB floor) stopped the campaign-9 server once more, idle, right after the last arm had finished and been graded: a client holding a 1M-token history took 0.8 GiB in its end-of-run bookkeeping. No GPU fault line; Gemma restored at 16:40 and both cards answer. | Qwen 27B FP8 and H3 remain its optimization lanes. Every research launch passes `B70_GUARD_MIN_AVAILABLE_GIB=1.6`; nothing else runs on the host beside a two-card server (it leaves 2.0-2.3 GiB), and a client that has run 1M tokens is ended only after the server has been stopped. Recheck actual state before using the host. |

No resident server is authorized by this consolidation. Start/measure/gracefully stop experiments; leave cards empty unless the owner explicitly requests hosting. One GPU lane per host at a time. Do not revive the withdrawn September 13
continuous-service rule or superseded relaunch queues.

**October 12, 16:41 UTC — our IQ3 runtime: twelve-prompt median 38.25 tok/s on two cards, every request bit-exact; the reference on the same prompts is 28.49.** The integrated runtime (two processes, one per card; the model's official draft head on the second card supplying the guesses; kernels selected on the card; native controller) ran the reference's twelve prompts twice each in one launch: 24 of 24 requests equal to their own CPU oracles (1,536 tokens and 9,216 layer fixtures, no tolerance), median 38.25 tok/s, range 35.05–41.43, guesses right 79% overall; 39.05 tok/s on the development prompt. Kernel log clean. This uses the reference table's 64-token definition; the public submission metric needs at least 100 generated tokens per prompt, and that run (128-token oracles exist for all twelve prompts) is being prepared, together with a speed run without the layer-fixture capture that still slows the first eight tokens of every request. [Receipts](experiments/own-xpu-runtime/stage2/packet38-integrated/receipts-cards01-20261012-chain/README.md).

**October 12, 05:56 UTC — our IQ3 runtime: 30.37 and 31.02 tok/s on two cards with the model's own draft head, bit-exact (development prompt).** The official one-token draft head now runs on the second card and supplies the guesses for the two-card pipeline: 53 of 63 guesses right, 64/64 tokens and 384/384 layer fixtures equal to the oracle in two fresh runs, kernel log clean; the draft's device arithmetic equals its host implementation byte for byte. A right guess costs 28.7 ms and a wrong one 55.3 ms. The 28.49 tok/s reference is a median over twelve prompts, so this is not yet the comparable sealed figure: the integrated runtime with a twelve-prompt suite window and the oracles for the other eleven prompts are being built. The root filesystem filled up at 04:57 UTC (packet build trees); 27 GB of regenerable build output was removed and recorded ([record](experiments/own-xpu-runtime/stage2/DISK-CLEANUP-20261012.md)). [Receipts](experiments/own-xpu-runtime/stage2/packet36-draft/receipts-cards01-20261012-chain/README.md).

**October 12, 03:05 UTC — our IQ3 runtime: both cards now work at once; 22.49 tok/s sealed sequential, 24–26 ms per token when every guess is right.** The runtime runs as two processes, one per card; the first card starts the next position from a guessed token while the second finishes the current one, a wrong guess is discarded and redone, and the emitted tokens stay the target's own (64/64 tokens and 384/384 layer fixtures in every run; kernel log clean). Sequential decode is sealed at 22.49 tok/s (one process) and 19.47 (two processes); with guesses fed from the oracle (diagnostic, not a speed result) a token takes 26.2 ms mean. The official draft head agrees with this quantized target 77.3% of the time on CPU, which projects to about 31 tok/s once it runs on the second card (reference 28.49); that packet and a kernel merge are being built. Replaying a recorded launch list is not faster; the token is GPU kernel time. [Note with receipts](notes/2026-10-12-two-card-pipeline-and-kernel-rounds.md).

**October 11, 22:30 UTC — our IQ3 runtime: 17.85 tok/s on two cards, bit-exact.** Same day progression of the exact two-card decode: 3.15 tok/s as first sealed, 12.08 after a linear allocation scan in the two-card backend was replaced by an ordered lookup, 17.85 with specialised non-GEMV kernels selected class by class from a timing run on the card (packet 26). Reference 28.49 tok/s. The token is GPU-bound (53.5 ms of kernel time, 11 ms of host issuing). The fused generic kernels of packets 21/23/24 were bit-exact but 50–100 times slower per launch and are abandoned. GPU work continued all afternoon on the boot that faulted at 09:09 with no further fault. [Scoreboard](experiments/own-xpu-runtime/SCOREBOARD.md).

**October 11, 16:10 UTC — GPU work resumed on the owner's instruction; first bit-exact two-card decode from our runtime.** After the parked process was ended and the four-card health probe passed, the IQ3 runtime reproduced its CPU oracle exactly on one card and on two (64/64 tokens, 384/384 layer fixtures) on the card pair that faulted at 09:09 UTC, with no fault. Measured speed is 2.46 tok/s, and 3.15 tok/s with the faster GEMV variants, against the 28.49 tok/s reference; about two thirds of each token is the runtime's own per-launch timing queries, not GPU work (issuing a kernel measures 3.4–5 µs). A build without that instrumentation and with the fused launch schedule is being prepared. [Note with receipts](notes/2026-10-11-first-exact-two-card-decode.md).

**October 11, 09:10 UTC — FAULT HALT, second GPU fault on this boot; device launches stopped; a reboot is the owner's decision.** A two-card resident decode run of our runtime (packet 16, cards `0000:47:00.0` + `0000:43:00.0`) took a GPU page fault and compute-engine reset on both cards at its first computation after loading 53 GB of weights. The host stayed up; the process (PID 183867) is parked after one cooperative stop and was not killed. First fault of this boot was 02:34 UTC. Most likely a software defect in the never-before-run two-card resident path; evidence and coredumps are in [the incident folder](experiments/own-xpu-runtime/stage2/packet16-decode/evidence/20261011-w2x-two-card-fault/README.md). Before the fault: packet 16's one-card check passed (48/48 layers and token equal to packet 13 on the card, 485 s instead of 5,247 s), and the bit-exactness problem was traced to a build error — Intel's correctly-rounded divide/sqrt options must also be on the link line; with them our own `exp`/`log` match the host on the card for all 2^32 inputs ([forensics](experiments/own-xpu-runtime/stage2/packet17-detmath/evidence/20261011-wb-a-link-flags/README.md)). CPU-only work continues.

**October 11, 07:28–08:11 UTC, first device answer from our runtime:** On card 3 the IQ3 program produced the oracle's first eight tokens (`**Incident Retrospective: Production`), but 0 of 48 layer fixtures are bit-identical to the CPU oracle, because the card's `exp`/`log` and `1/sqrt` results are not glibc's (packet 4 core on card versus host: 50/72 fixtures). The parallel non-GEMV kernels match that core on the same card 72/72 and cut the non-GEMV cost from about 52 s to about 23 ms per token. The two-card within-layer split is bit-identical to one card on layer 0, but its 41 exchanges per layer cost more than the split saves. Arithmetic identity v2 (our own deterministic `exp`/`log`, host RoPE table) is being built so the device can match the CPU oracle exactly; this is a recorded change for the owner to judge. [Note with receipts](notes/2026-10-11-first-device-answer-and-arithmetic-v2.md).

**October 11, CPU-only IQ3 screen preparation:** The [one-card and two-card plans](experiments/qwen38-flash-next-ud-iq3xxs-b70/baseline-llamacpp/run-identity.md) now let the coordinator select cards and run on disjoint cards, with automatic fitting and fuller logs for one card. The [two-card ledger](results/qwen38-flash-next-ud-iq3xxs-b70/README.md) retains nine first-repeat rows before a host fault stopped the screen; repeat checks and certification remain incomplete. No GPU work was run in this preparation; the coordinator owns recovery and any new window.

## Four-Card Flash-Next Status

**October 11: the fourth incident is [closed as a router-padding software defect](notes/2026-10-11-fourth-incident-closed.md).** The fixed experimental attempt-8 line loaded and finished its four-card profiling run with no boundary violations or new kernel faults, then stopped cleanly. Available host memory fell from **119.17 GB** after hashing to **47.10 GB**, with **77.08 GB** peak pressure, compared with attempt 8's **75.45 GB**. This was one run with no generation requests, and missing card-memory measurements still prevent qualification; it does not establish the certified recipe's memory need or change its floor. Next is a bounded generation screen under the checks, then certified-recipe calibration when the owner approves its floor; current coordinator admission still applies and LTX stays off.

The certified FP8 result remains **46.854250 tok/s**, with its exact identity and gates in the [closeout](results/qwen38-flash-next-fp8-b70/CLOSEOUT-20260913.md), [handoff](results/qwen38-flash-next-fp8-b70/HANDOFF.md) and [reproduction
guide](repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/README.md). Reopening diagnostics and CPU preparation do not replace that record.

## LTX Continuing Video

The recorded production arm is **137, stopped under the owner's existing instruction**. Packet **138 is sealed and CPU-tested; native qualification is pending**. Its scheduled text prefetch is off by default, compares unchanged conditioning when produced and consumed,
and predicts 0.095 seconds/chunk saved without a native measurement. It retains at most 1.3125 MiB extra CPU conditioning; overlap and memory peaks remain unmeasured. See the [design](notes/2026-10-10-continuation138-stream-design.md), [build
receipt](experiments/ltx25-b70/data/resume-20261008/continuation138-build.json) and [coordinator launch packet](experiments/ltx25-b70/recovery/20261010-continuation138-stream/LAUNCH.md).

The continuing-video line uses 256×256, 145-frame chunks with 144 new frames (six seconds). For packet 135 GC-10, the first uninterrupted 52 periods had a **5.2415 s median**; the whole 747-period session had a **5.553 s raw median** affected by
client pacing. Neither the short prefix nor the later hold-free diagnostic establishes sustained unthrottled speed. [Corrected metric ledger](results/ltx25-continuation-stream-pacing-2026-10-10.md).

The goal remains coherent continuing video faster than playback, then higher resolution. Preserve the accepted short-window text-encoder reference (`stability-01-w93c-*`, `experiments/ltx25-b70/data/stability-01-window-prereg.json`) and exact
continuation lineage. Do not blend it with padded-encoder or other output-changing baselines. Unaccepted soft-latent, mixed or guide-anchor alternatives remain separate.

The **9 GiB device floor, 5 GiB capture reserve, 0.75 GiB screening band and 50 GiB disk reserve** remain in force. Preserve the full snapshot schedule; the optional reduced `a-xpu3-sync` barrier still needs owner acceptance. The latest larger-chunk
screen permits considering 169 frames with graphs off, but it was not launched and predicts no gain; larger graph arms remain unqualified.

Owner seam/audio acceptance and portable public runtime reconstruction plus independent replay remain open. The [public recipe](repro/ltx25-continuation-stream-b70-145f-20261010/README.md) records these limits. Packet 138 and any relaunch wait for
the host halt decision and their own admission; old streaming requests do not erase those gates.

Preserve `/home/steve/src/ComfyUI-ltx25-baseline`, `/home/steve/.venvs/ltx25-baseline`, `/mnt/fast-ai/bench-results/ltx25-baseline-20260913`, `/home/steve/ltx-stream/`, all reference/unique captures, negative runs, manifests and restore receipts.
Approved duplicate retirements are recorded in lane notes; a later full proof must restore the required ordinary-copy layout first.

## Our Own Intel Xe Runtimes

**October 11, CPU-only first-token correctness check:** The reported wrong answer was actually the incoming prompt; at 06:25 UTC the device job had read 27 of 87 prompt tokens and had emitted no answer. A fresh CPU pass completed all 48 layers, matched the runtime-order CPU oracle's 48 hashes, and predicted the same first token, `**`; the [investigation](notes/2026-10-11-first-token-correctness.md) retains the text, fixtures and regression checks. Device agreement remains pending until that existing job writes its final-prompt fixtures; no GPU run or production arithmetic change was made here.

**October 11, CPU-only packet 14 two-card decode:** [Packet 14](experiments/own-xpu-runtime/stage2/packet14-tp2/README.md) splits dense rows, expert IDs and attention state across two owners, using ordered peer gathers that preserve the one-card calculation. All 18 CPU integration checks, the full tensor coverage check and the SYCL build pass; no GPU ran, and the extra exchanges mean a 1.5× gain is still unproven. The coordinator can next compare layer 0 and then the first token on cards 2+3 against packet 13's completed one-card result using the [gated commands](experiments/own-xpu-runtime/stage2/packet14-tp2/WINDOW.md).

**October 11, CPU-only IQ3 oracle rebase:** [Packet 3](experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/README.md) now follows the runtime's fixed arithmetic and completed the 87-token incident prompt plus 64 generated tokens, averaging 9.17 seconds per decode token. Exact CPU reference checks pass, with all 48 layer states saved for the first eight predictions; the first difference from the old BLAS oracle is token 18, with logit margins of 0.375 versus 0.250. No GPU ran here; these fixtures are ready for device comparison, while device and full-model repeat checks remain open.

**October 11, CPU-only packet 13 integration:** [The integrated IQ3 program](experiments/own-xpu-runtime/stage2/packet13-integrate/README.md) now uses the measured kernel choices, streams one layer's weights and selected experts on one card, and can retain weights across two cards using the existing sequential layer split. The CPU mini-model checks and SYCL build pass, and the real first layer's new hash is saved; comparison waits for the oracle's new arithmetic order. No GPU ran here; the coordinator has a [bounded card-3 command](experiments/own-xpu-runtime/stage2/packet13-integrate/WINDOW.md) to process the whole first prompt, emit eight tokens and record where the time goes, with cards 2+3 reserved for a later resident test.

**October 11, CPU-only packet10 exactness repair:** The coordinator's first
card-3 gate failed an IQ3_S output comparison after 57 checks; teardown was
clean and no kernel faults were recorded. [The repair](experiments/own-xpu-runtime/stage2/packet10-kopt5/README.md#october-11-exactness-repair)
reproduces a NaN sign change when the compiler specializes the expanded path,
preserves the original bits explicitly, and adds the missing CPU comparisons
and detailed failure reporting. The original device row was not saved; the CPU
reproduction is separate evidence. Original receipts and the latch remain.
No GPU ran in this repair; the coordinator owns the fresh exactness gate and,
only if it passes, timing.

**October 11, CPU-only two-card exchange preparation:** The [tensor-parallel design](experiments/own-xpu-runtime/stage2/TWO-CARD-TP.md) and [packet 12 harness](experiments/own-xpu-runtime/stage2/packet12-peer/README.md) prepare both cards to work within each layer. CPU tests and the SYCL build pass; no device program ran. The design corrects the count to 48 layers and keeps exact output agreement as a gate: simply adding two partial sums can change answers. Peer support and exchange timing remain unmeasured. The coordinator's next step is the documented cards-2/3 transport window after admission; the speed scenarios are calculations, not model results.

**October 11, CPU-only packet9 repair:** The coordinator's 04:40 UTC card-3 attempt stopped before completing any checks because staging buffers reused names; teardown was clean and no kernel faults were reported. [The repair](experiments/own-xpu-runtime/stage2/packet9-kopt4/README.md#october-11-allocation-and-failure-classification-repair) gives each buffer a unique name and separates infrastructure aborts from output mismatches and kernel faults. All 31 Python tests, 28 mock expert cases and the SYCL build pass. Original evidence is preserved; new scratch is removed. No GPU ran in this repair. The coordinator owns the next card-3 exactness and timing windows; device qualification is still pending.

**October 11, CPU-only round-3 kernel preparation:** [Packet 8](experiments/own-xpu-runtime/stage2/packet8-kopt3/README.md) shares quantized-weight decoding work, compares constant tables with shared local tables, and selects kernels by the measured matrix shapes. It also prepares one launch for all ten experts’ gate/up projections and a separate down launch. The CPU exactness checks and SYCL build pass; all 1,224 tensors have a checked operation mapping. No GPU ran, and no new speed winner is claimed. The coordinator owns the two documented card-3 exactness and timing commands; the previous shape choices remain until measured replacements pass.

**October 11, CPU-only round-2 kernel preparation:** [Packet 7](experiments/own-xpu-runtime/stage2/packet7-kopt2/README.md) is ready for card 3 to measure its memory-reading ceiling, then compare split sums, wider row loads and grouped projections. The CPU checks and SYCL build pass; no GPU command ran here. Split sums have a new fixed arithmetic order, so full-model output parity remains unproven. The coordinator owns the two documented device windows; the speed estimates are hypotheses.

**October 11, CPU-only kernel optimization preparation:** [Packet 6](experiments/own-xpu-runtime/stage2/packet6-kopt/README.md) adds separate packed-matrix candidates with wider loads, shared unpack work and a four-matrix diagnostic. The SYCL build, ten protocol tests, 207,360 decoded values and 1,416 CPU row comparisons pass. Its new reduction changes 134 FP32 accumulators but no final 16-bit fixture outputs; full-model parity remains open. No GPU binary ran. The coordinator owns the documented card-3 exactness and timing windows; no new speed is claimed.

**October 11, CPU-only copy measurement preparation:** [Packet 5](experiments/own-xpu-runtime/stage2/packet5-h2d/README.md) now builds our bounded native copy test at the actual expert sizes, with pinned/pageable buffers and a copy-versus-compute overlap check. Eleven Python tests, host ownership checks and the SYCL build pass; no device binary ran and no transfer speed is claimed. The coordinator can run the documented card 3 window next, then use its measured copy rates in the one-card plan.

**October 11, CPU-only one-card plan:** The [IQ3 one-card design](experiments/own-xpu-runtime/stage2/ONE-CARD-PLAN.md) follows the two-card target and recommends keeping dense weights and a cache of experts on the card, copying missing experts from host RAM. A 24 GB cache has a calculated transfer-only ceiling of 39.50 tokens/s at the assumed 19 GB/s rate; this is not a measured runtime speed, and actual memory fit remains to be checked. First measure our copy speed on this host and collect the CPU oracle's expert choices; this documentation work used no GPU or model payload.

**October 11, CPU-only:** the owner's first real-model target for our own engine is now the IQ3 quantized compressed version on two B70s; the 27B FP8 work remains documented. [Stage 2 packet 2](experiments/own-xpu-runtime/stage2/packet2/README.md) adds the GGUF loader and packed kernels, with exact CPU checks and a successful SYCL build. Nothing ran on a GPU in this task; the next step is the [bounded one-card device comparison](experiments/own-xpu-runtime/stage2/packet2/WINDOW.md) in a separately authorized window.

The October 10 [objective](docs/own-xpu-runtime-objective.md) is our own model-specific code. Other projects supply credited ideas, not a code base. Official-publisher or Unsloth weights are permitted; another source needs written justification and
owner approval. The earlier ISTA IQ3_S proposal is withdrawn. These CPU packets do not qualify a native runtime or authorize a GPU window.

- **27B stage 1:** [identity packet 1](experiments/own-xpu-runtime/stage1/packet1/README.md) freezes tokenizer requirements, twelve saved answers and 1,606 tensors. [Packet 1b](experiments/own-xpu-runtime/stage1/packet1b/README.md) adds synthetic CPU
  arithmetic/readers. [Packet 2](experiments/own-xpu-runtime/stage1/packet2/README.md) checks the existing official USB weights: 67 large-file hashes, 14 small publisher files and repeated CPU samples. Text plus MTP requires 29.945 GB with on-card
  embedding; actual one-card fit is unproven.
- **Native preparation:** [packet 3](experiments/own-xpu-runtime/stage1/packet3-prep/README.md) tests memory ownership with mocks and compiles, but does not run, SYCL. Attention gating is corrected to sigmoid. [Packet
  4](experiments/own-xpu-runtime/stage1/packet4-prep/README.md) maps 44 source boundaries and tests synthetic capture; the native worker and internal-state bindings remain incomplete. A367 used a host environment whose extension differs from the
  reopen image; no certified image has been established.
- **Fixture-window blockers:** the [memory admission review](experiments/own-xpu-runtime/stage1/packet4-prep/MEMORY-ADMISSION-REVISION.md) derives a **133,542,784 KiB floor**, above current capacity; no lower passing floor is justified. Eighteen
  certified kernel files match, but a historical model-receipt hash mismatch and separate native admission also block the [planned 60-minute Flash-only window](experiments/own-xpu-runtime/stage1/packet4-prep/WINDOW-RUNBOOK.md). Any admission revision needs the
  driver's document-bound owner receipt.
- **A367 calibration, CPU preparation October 11:** the [load-only packet](experiments/own-xpu-runtime/stage1/packet4-prep/a367-calibrate/README.md) is prepared for the first certified-recipe launch after the fourth incident. It makes no generation requests, measures memory through a 20-second ready hold and graceful stop, and proposes a floor only from a complete clean run. The default floor, separate native admission and receipt mismatch remain; any calibration-only start-floor exception needs a separate explicit owner decision. No model was launched during preparation.
- **Flash-Next stage 2:** [packet 1](experiments/own-xpu-runtime/stage2/packet1/README.md) freezes official tensor identity and twelve certified answers; the two-card official-weight plan needs about 65 GB of experts off-device before workspace.
  [Packet 1b](experiments/own-xpu-runtime/stage2/packet1b/README.md) passes synthetic CPU math/repeats, preserving Flash's BF16 inter-row state versus 27B's FP32 state; device parity remains unverified. The
  [plan](experiments/own-xpu-runtime/STAGE2-PLAN.md) separates calculated bandwidth from measured speed.
- **Separate quantized compressed version:** Unsloth UD-IQ3_XXS has its own [lane/CPU packet](experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/README.md). All three file hashes, tensor census and fresh-process sampled CPU repeats now pass,
  superseding the incomplete-download note. Packed target weights require **53.305 GB across two cards** with large lookup tables off-device; fit, complete-model answers and speed remain unmeasured. Next: its tokenizer/operator oracle. The [pinned
  llama.cpp measurement baseline](experiments/qwen38-flash-next-ud-iq3xxs-b70/baseline-llamacpp/README.md) builds for B70 and passes CPU help/version; its proposed target-only twelve-prompt, two-fresh-process run uses full 16-bit KV and still needs
  native admission.
- **Identity boundary:** IQ3 must be lossless and deterministic against its own bytes and CPU dequantization oracle; FP8 differences are informational, not a tolerance gate. Never call it the FP8 model or compare it as the same record. The [Unsloth
  header census](experiments/own-xpu-runtime/stage2/packet1c/README.md) finds no extra MTP block in the three checked variants; packed-weight arithmetic alone does not establish runtime fit. Other variant acquisition, quality and device work remain
  separately gated.

**IQ3 CPU oracle, October 11:** [Packet 2](experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle/README.md) now follows the official Flash-Next sigmoid gates and completed 64 tokens each for the incident and code-review prompts, at 43.33 and 46.18 seconds per decode token. The three-hour CPU-only run stopped cleanly with 128 generated tokens, two complete sets of layer fixtures and a third prompt stopped after 32 layers; peak memory was 1.06 GB. Baseline differences are informational, full-model repeat checks remain open, and no GPU work was performed.

**October 11, CPU-only IQ3 decode orchestration:** [Stage 2 packet 3](experiments/own-xpu-runtime/stage2/packet3/README.md) now checks every tensor's placement and runs the ordered step on synthetic CPU inputs; 23 Python tests and 18 C++ cases pass, including exact NumPy comparisons and fresh-process repeats. Its plan has 1,873 dispatch sites and 4.951 GB of weight/lookup reads per token, which are planning counts, not measured speed. The step follows the corrected sigmoid GDN gate; device execution and host lookup mapping remain open, and no GPU or model payload was touched.

**October 11, CPU-only IQ3 timing preparation:** [Packet 2 timing window](experiments/own-xpu-runtime/stage2/packet2/README.md#timing-window) now prepares the real layer shapes and ten selected experts, with a whole-GDN GEMV sequence and a fault-watched receipt. The native binary compiles; CPU plan, receipt and ownership checks pass. No timing window was run. The coordinator’s next step is the bounded card-3 measurement against the 507/537 GB/s byte floors.

**October 11, CPU-only IQ3 integration:** [Stage 2 packet 4](experiments/own-xpu-runtime/stage2/packet4/README.md) builds one runnable program and its SYCL target; the two-layer mini-model matches Python exactly. The real first layer completed all 87 prompt tokens but differs from the CPU oracle in 2,293 of 10,240 BF16 values, so its quality gate remains failed. No GPU was used; the coordinator’s first card-3 layer comparison is prepared, and full-step checks must wait for exact agreement.

**October 11, CPU-only expert-path preparation:** [Round 4 packet9](experiments/own-xpu-runtime/stage2/packet9-kopt4/README.md) adds one gate/up launch, one down launch and an ordered weighted-sum launch, plus whole-layer GEMV timing. CPU checks and the SYCL build pass; no device program ran. The census corrects the planning inputs to 36 GDN + 12 QSA layers and 19.712 MB per ordinary expert block. The coordinator can next run the packet's card-3 exactness and paired timing commands after admission. Full-model output checks and actual speed remain pending.

**October 11, CPU-only exact weight expansion:** [Round 5 packet10](experiments/own-xpu-runtime/stage2/packet10-kopt5/README.md) prepares expanded dense weights and two output-head kernels. The budget is 55.194 GB of weights, or 63.348 GB with the existing reserve; routed experts remain packed. CPU bit checks and device-program compilation are complete, but no GPU program ran. The speed estimates remain below the reference, and native fit and full-model quality are untested. The coordinator's next step is the packet's card-3 exactness and paired timing commands after admission.

**October 11, CPU-only packed expert decode:** [Round 6 packet11](experiments/own-xpu-runtime/stage2/packet11-kopt6/README.md) reads native Xe2 assembly and prepares three exact decode alternatives. Integer unpacking and sign handling take most of the visible instructions; the full IQ2 register table spills, while the packed pipeline has a smaller arithmetic body. All CPU checks and device-program builds pass. No GPU program ran, and speed predictions remain unverified. The packet gives the two card-3 commands for the coordinator after separate admission; the existing host halt remains in force.

**October 11, CPU-only non-GEMV arithmetic correction:** [Stage 2 packet 15](experiments/own-xpu-runtime/stage2/packet15-nongemv/README.md) now checks the frozen Packet 4 core. All 72 cases pass in two fresh runs under each compiler, and all 18 protocol tests pass for each build. The old Torch reference still differs in twelve cases and is kept as a diagnostic. The prepared card-3 window compares against Packet 4 on the same device; native exactness and timing remain pending. No device ran and the live runtime is unchanged.

## Two-Card Lanes And Context Work

**Qwen 27B FP8:** optimize the official FP8 model with native MTP and full 16-bit KV; DFlash stays excluded by the September 14 owner decision. Read the [multi-host handoff](experiments/qwen38-27b-b70/MULTI-HOST-HANDOFF.md), [closed
experiments](experiments/qwen38-27b-b70/DO-NOT-REPEAT.md) and [TP2 recipe](repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md) before runtime changes.

The October 7 public-package acceptance passes short and 2K–8K long prompts at 16/32/64 users, two passes exact to the single-user answers. **875 tok/s is aggregate short-prompt throughput at 64 users**, not a single-user or all-workload rate. The
same acceptance session recorded a 90.31 tok/s recommended-profile median. Evidence: `experiments/qwen38-27b-b70/data/2026-10-07-fp8-two-card-multi-user/`. Clean-host qualification and multi-user drafting (R314, local only) remain open.

**MiniMax-H3:** the October 10 owner decision accepts **Comfy-Org's pruned BF16 denoiser with fitted AdaLN**, including that source as an explicit exception to the source rule. The lab analyzed this published file; it did not produce the fit. The
fit-search/redownload queue is superseded. The [draft package and recipe](repro/minimax-h3-pruned-bf16-tp2-b70-20261004/README.md) targets turin, two B70 and 15 GiB RAM.

The measured eight-clip batch is **396.6 seconds/clip**, with 32 matching hash checks and eight repeat passes against this denoiser's own reference. That exact scheduling result is not losslessness versus the official model. The older 800.8 s/clip
baseline is ledger-only, with raw receipts not retained. Publisher input pins are checked; baseline/reference receipts, clean build/runtime, independent full-suite repeat and portable release evidence remain missing. Turbo LoRA and other changed
arithmetic stay separate. H3 GPU work must use `experiments/minimax-h3-b70/scripts/smoke_h3.sh` and its memory watchdog.

**Long-horizon context (restarted October 10):** the [program charter](docs/long-horizon-context-program.md) holds the problem, every idea and the benchmark. At the fast scale (32K live cap, 240K history, two seeds) archive-and-recall is ahead on every axis (63/65 against 56/65 window-drop, 48/65 compaction) and as quick as any. On the new rule and method questions **no method kept a rule stated at the start (0/5 each)**; the archive method kept the method only. Permanent rule lines in the pinned state fix that at 240K (5/5, 35/39 overall). The same method then read a **1M-token history through a 32K live budget: 163/203 probe answers (80 %), flat with distance and with history length, 8.7 minutes per 100K with no slowdown** (a stopped run: the final write wiped the answers file; the probe answers are rebuilt from the transcript). Weak spots at scale: old values 64 %, the pinned rule lapsing in use 76 %. **The keeper** (campaigns 6-8) then replaced it as the lead: the agent manages nothing; the harness archives what it cuts, has the model rewrite NOTES (RULES / STATE / OPEN) at each cut and repeats the rules at each question. 39/39 and 46/46 on two 240K rule streams, and **226/228 (99 %), not void, on the 1M stream in 83 minutes with 865 model calls** (protocol arm: 2,170 calls). The same policy is `tools/ctxkeeper/`, an OpenAI-compatible proxy (standard library, 24 tests): after the fixes its first runs prompted, 39/39 and 44/46 at 240K and **222/228 (97 %), not void, on the 1M stream in 95 minutes**, with an agent that sends its whole history and manages nothing. The summary baseline (C32) scored 23/29 in 29 minutes, below window-drop. **Campaign 10 (October 11 evening): in-place notes** (the notes call is the live conversation plus one message, a changes-only reply written with thinking and checked by the harness, then every turn in view is moved out) give the same answers in about 40 % less time: 39/39 and 46/46 at 240K in 9.5 and 8.5 minutes, and **228/228, not void, on the 1M stream in 50 minutes**, with NOTES that an audit against the true ledger finds right in all 63 versions (`notes_audit.py`; the full keeper lost five lines once on the same stream, and notes written without thinking carry 2 to 8 wrong values a run whatever they score). **Retrieval alone** (every item in a store outside the sandbox, BM25 over sentences, no notes) equals the keeper at 240K (39/39, 45/46) and for the first 420 items at 1M, then falls behind (56/70 in the last third; the rule lost 4 times in 29; final list not answered) and is worse on a stream that refers to things indirectly (10/15 against 15/15). Campaign 10b (October 12, 00:01-02:08) ran the fully-checked in-place arm on both 240K seeds: 39/39 and 46/46 in 10 minutes (NOTES audit: nothing wrong on seed 0 and at 1M, one counter wrong for a stretch on seed 1), so **313 of 313 over the three rule streams**; and on the hard stream the keeper with retrieval at question time added reached 47 and 46 of 50 (42 and 43 without). Not yet run: in-place notes in the proxy, the keeper with retrieval at 1M, the plain 200K-window baseline at 1M, second seeds at 1M and of the hard stream, the proxy under a real agent. Results, plans and the reason round 3 stopped: [lane note](experiments/qwen38-27b-b70/notes/2026-10-10-context-16k-baseline.md). One seed per new axis; one synthetic task family; not yet a general memory claim. **Campaigns 11 and 12 (October 12): the proxy has the fast notes.** `tools/ctxkeeper --notes-mode inplace` scores 39/39 in 8.8 minutes and 46/46 in 9.7 on the two 240K streams (the harness arm: 9.9 and 10.0; the proxy's full-rewrite form: 17 and 18), with no value wrong in any saved NOTES version, and **220 of 228 on the 1M stream in 53 minutes, not void** (the bar set beforehand: 220 in under 70; its first build, the night before, scored 216 in 76). Seven of the eight misses are one confusion (the search tool counted messages, the questions count items); code state p fixes that (`--recall-label`), was reviewed read-only before running, and scored **39/39 in 8.5 minutes, 46/46 in 9.4 and 226 of 228 at 1M in 50 minutes**: within two answers of the harness arm and as fast. The harness keeper on a second 1M stream: 210 of 222 in 50 minutes (the first stream: 228 of 228), so 438 of 450 (97.3 %) over two streams; seven of the twelve misses are one question item that an ordinary cut moved out of view while the model was still searching for it (a hole to close: an open question must survive every cut). **A rule that names nothing** ("any figure below zero is reported as the word overdrawn"): the keeper answered the governed questions 16 of 16 over two seeds, retrieval alone 0 of 16. Hard stream, second seed: keeper with retrieval 46 of 49 in 23 minutes (the day's stricter checks slow that stream; fix in code state p, not yet run there). Built and not yet run: a real-code task (`make_repair_tasks.py`: more-itertools with 40 injected defects, tickets one at a time, standing instructions that arrive mid-task). Still the owner's decision: which real agent program to put in front of the proxy.

**Context/retention:** October 8 owner rule: decide studies within a few hours using pilots/concurrency/early stops; no more full-day soaks. The [LongMemEval stage-2 result](experiments/qwen38-27b-b70/notes/2026-10-08-longmemeval-stage2-result.md)
recommends archive-and-recall within 32K for that study; the 27B self-judge is secondary evidence, and abstention is the next weakness. Do not turn this into a general memory or speed claim.

For the two short controlled documents, [direct full-source reading](experiments/qwen38-27b-b70/notes/2026-10-07-full-source-screen-result.md) got 24/24 on each in one cold request; this is a static final-answer comparison, not an intermediate-state
or general speed guarantee. The [history study](experiments/qwen38-27b-b70/notes/2026-10-07-history-state-study-result.md) failed on ownership joins despite exact numeric checkpoints. Preserve its archive inventories and failed revisions 3/4; keep
t03/t04 and the other held-out rows unused. Do not reopen short-document interface tuning; new work needs a concrete streaming/audit requirement or relevant independent history, as the [research
priorities](experiments/qwen38-27b-b70/notes/2026-10-07-context-research-priorities.md) specify.

[Project decision recall](experiments/project-decision-recall-20261007/RESULTS.md) covered 38/38 criteria by ordinary search/read; complete-source delivery missed one caveat (37/38). These were hosted assistant sessions over curated records, not a
local-model qualification. No structured memory store or worker integration is admitted. The [local worker scoped attempt](experiments/local-coding-worker/scoped-task-20261007/CLOSEOUT.md) made no edit or accepted submission; preserve prior failed
worker/recall trials and five unused tasks. Further worker tuning/integration is parked.

## Known Issues And Next Actions

1. **Owner decision dated October 11:** the fourth software incident is closed; the certified-recipe calibration floor still needs approval. Follow the bounded-generation next step above with current coordinator admission; the old engine-window receipt is spent and LTX stays off.
2. Finish the CPU runtime tokenizer/operator and adapter work, retaining the fixture memory-floor, receipt and native-window blockers above. Keep H3's missing publication evidence explicit; its source acceptance is already resolved.
3. Keep each certified result under its exact model, weights, arithmetic, topology, metric and quality identity. Preserve historical high scores and negative patches; host/session drift does not by itself justify merging different benchmark
   identities or lowering a record. Consult the [reproducibility map](docs/current-reproducibility-map.md), [effort index](docs/model-effort-index.md) and [scoreboard](results/scoreboard.md).
4. The GDN PR #45 community contribution still needs its actual mixed-session soak before production promotion; shorter strict-oracle passes do not verify that incident. Historical replay hash mismatches remain evidence, not permission to repin
   shared tools blindly. Follow the [replay audit](notes/2026-09-09-replay-and-validator-audit.md).
5. ML Bottleneck automatic refresh stays paused: 4070 interpretation, nine ambiguous measurements and calibration thresholds block publication in that repository's `docs/refresh-review-2026-09-08.md`. Keep its published evidence unchanged. Duplicate
   LocalMaxxing record `cmu6ytvxr082alq015dpjgiz4` remains flagged for owner-only withdrawal; canonical record is `cmu6ytqyr0827lq01b76whp6d`.
6. A reproducible package needs pinned inputs, a clean build, unchanged quality gates and graceful teardown, with the public asset/replay checks required by [AGENTS.md](AGENTS.md). An older runnable command, CPU test pass or accepted model choice
   does not satisfy missing gates.

## Storage And Recovery

Retain the **50 GiB free-space reserve** and admit the peak temporary writes before creating archives or copies with `scripts/check-storage-headroom.py`; old free-space numbers are not admission. Verify current capacity, mount identity and ownership
before new model downloads. Do not do bulk reads of the protected external trees during this documentation cleanup.

Cache archives live under `/home/steve/git-archives/cache-consolidation-20261006/`; eight inactive staging builds are archived under `/home/steve/git-archives/staging-consolidation-20261007/` and need restoration before old launchers work. Keep
`data/maintenance/consolidation-20261006/summary.json` and `data/maintenance/staging-consolidation-20261007/summary.json`, with their inventories, hashes and restore instructions.

The selected research/Git backup is `/mnt/usb-models/lab-backups/steve-b70s-20261007/` (nine verified archives, selected source only, not a whole-machine backup). Preserve `/home/steve/git-archives/flash-next-rescue-20261007/`,
`/home/steve/worker-container-controls-20261007/`, and the official 27B cold copy `/mnt/usb-models/worker-models/qwen38-27b-fp8-20261007/017b9c7af6b5689d5dd426a76e0bc077eb5ca20a/`. This page does not assert the USB disk's current mount state. It is
cold backup storage, not an active model-serving path; no force, repair/reinitialization or SMART bridge passthrough.

Preserve source/build deltas, unique outputs, anchors, failure/coredump/OOM evidence, model/cache inventories, quarantined damaged LTX files, rejected/partial downloads and restore maps unless their exact disposition has been independently
established. In particular retain `/mnt/fast-ai/bench-results/mtp-lossless-transfer-20260914/FAULT.json` and all four stages, and `/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914` with its stopped incident container. A compressed archive or Git
history does not by itself demonstrate recoverability of ignored artifacts.

## Protected Work And Artifacts

Preserve these paths and inspect their status before any build, cleanup, or
service change:

- `/home/steve/src/llama.cpp-muse-100`: preserved source/build used by the inactive Muse fleet;
- `/mnt/fast-ai/src/llama.cpp-q38-q4k-glu-tp2`: accepted Qwen3.8 Q4_K_M source at
  `a4349bcee`; preserve its intentional three-file uncommitted fusion delta;
- `/mnt/fast-ai/src/llama.cpp-q38-q4k-glu-tp2/build-sycl-aot-bmg-g31-oneapi-2026.1.1`:
  accepted oneAPI 2026.1.1 BMG-G31 AOT build;
- `/mnt/fast-ai/llm-models/qwen3.8-27b-gguf/`: accepted Qwen3.8 GGUF targets and MTP sidecars;
- `/mnt/fast-ai/llm-models/qwen3.8-27b-fp8/`: official FP8 artifact retained for the separate vLLM lane;
- `/mnt/fast-ai/bench-results/qwen38-official-fp8-vllm-xpu-20260816/`:
  official FP8 eager/graph/P2P controls, final quality gate, cache-zero result,
  runtime capture, and post-run health evidence;
- `/mnt/fast-ai/llm-models/qwen3.8-27b-gptq-int4-mtp/`: hash-verified
  SergioB GPTQ INT4 target with 15 BF16 MTP tensors; community replay lane;
- `/mnt/fast-ai/bench-results/qwen38-q4km-asrock-b70-20260815-pass2/`:
  accepted Q4_K fusion A/B and cold-suite evidence;
- `/mnt/fast-ai/bench-results/qwen38-gptq-int4-asrock-b70-20260816/`:
  SergioB target-only eager/graph validation, failed conservative-U graph
  attempt, logs, inspect records, prompts, and raw SSE evidence;
- `/mnt/fast-ai/bench-results/qwen38-gptq-quality-20260816/`: native/FP8 KV,
  semantic quality, MTP runtime-dtype, Q8/Q4 controls, and reset-window evidence;
- `/mnt/fast-ai/src/llama.cpp-q8-tp2-directq8-isolated`: current accepted Qwen TP2 source;
- `/mnt/fast-ai/src/llama.cpp-q38-tp2-distributed-greedy-directq8`: closed
  exact distributed-argmax candidate; preserve for mechanism reuse only;
- `/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260816-distributed-greedy/`:
  position-balanced reasoning-off controls/candidates and exact output oracle;
- `/mnt/fast-ai/src/llama.cpp-mndodd-intel-sycl`: prior accepted Qwen TP2 source; preserve as control;
- `/mnt/fast-ai/llm-models/qwen3.6-27b-q8_0-gguf/`: accepted Qwen model;
- `/mnt/fast-ai/bench-results/qwen36-q8-asrock-b70-20260813-tp2-fusion/`:
  promoted Qwen evidence and bounded negatives;
- `/mnt/fast-ai/bench-results/qwen36-q8-asrock-b70-20260814-40tps/`:
  Qwen pass-1/pass-2 evidence and current clean result;
- `experiments/qwen27_graphsafe_flash_attention/`: graph-safe INT4 source and
  generated research state;
- `experiments/qwen36-27b-autoround-int4-b70/`: INT4/MTP research packet and
  diagnostic artifacts.

Large ignored Qwen artifacts may be archived only after a complete inventory,
hash verification, and a recorded restore path. Never use broad `git clean` or
delete tracked experiment material to make the tree look tidy.

## Additional Preserved Work And Operational Guards

Preserve the pre-existing dirty files; inspect their status before editing:

- `experiments/qwen38-27b-b70/scripts/context/second-comparison.sh`
- `experiments/qwen38-27b-b70/scripts/run-fp8-tp1-server.py`
- `experiments/qwen35-9b-b70/probes/drift-reproduction.py`
- `experiments/qwen35-9b-b70/scripts/analyze-admission-composition.py`
- `experiments/qwen35-9b-b70/scripts/run-20260908-drift-reproduction.sh`

The prior ledger also protects the dirty Flash-Next source tree; do not reuse or modify it for the Qwen3.8 R50 review. Root-NVMe/BIOS work remains paused: no bulk reads/scans of `/mnt/fast-ai` or `/mnt/usb-models`; do not start
`generate-q38-root-nvme-link-clearance-v1.py` or any `w13`/`hc` runner. Do not run process-search commands containing `w13-m1-xpu-graph-gate.py` or the A2 result path: frozen health checks can mistake the search itself for a surviving runner.
Preserve the [archived ownership notice](CURRENT-history-20260909.md#immediate-manager-actions) and its exact frozen-runner paths.

Power settings are off limits, including restoring old values. Host memory/swap/page-cache changes and reboot require owner authorization; do not alter any approved workaround as cleanup. On the four-card host, blocks **53–57** remain offlined by
`b70-offline-bad-memory.service`; RAM replacement is deferred for 2026. The approved deepest-idle-state and lockup-panic settings are recorded in the [stability guide](docs/host-stability-and-fault-diagnosis.md); old September statements that the
mitigation was absent are historical.

On turin retain approved `vm.swappiness=1`, earlyoom, disabled automatic kernel/GPU-firmware upgrades, and kernel `7.0.0-38` with `7.0.0-31` fallback. Only one memory-heavy job at a time on its 15 GiB host, never beside a build container. Do not
start another job close to an active server's memory-guard floor.

Follow [AGENTS.md](AGENTS.md) for main-only Git, secrets, graceful GPU shutdown, first-fault evidence and bounded health checks, strict lossless gates and full 16-bit KV. All superseded results and historical incidents remain available in the
[verbatim October ledger](CURRENT-history-20261010.md); archiving them does not retire protected work or grant operational permission.

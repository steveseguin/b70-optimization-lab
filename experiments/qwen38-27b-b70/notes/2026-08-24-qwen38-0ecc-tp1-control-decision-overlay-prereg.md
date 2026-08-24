# 0ecc TP1 stock-control decision overlay qualification preregistration

Date: 2026-08-24. State: closed stale before launch. No arm from this program
ran before or after the reboot.

## Closure before execution

The final pre-commit freshness gate resolved vLLM `main` to
`e239947777e18071c8053195ce599b6511717f67`, one commit after 0ecc. That commit
only changes OpenAI batch-output upload handling; it does not touch XPU, Qwen,
speculative decode, compilation, autotune, distributed runtime, dependencies,
or Rust inputs. Even so, 0ecc is no longer the literal-current source identity,
so this preregistered program is closed without a hardware gate or model arm.

The 38-file packet, its manifest, and the completed 0ecc parent evidence stay
unchanged as historical artifacts. The active path is to rebuild e239, map a
new versioned packet against e239's fresh cache identities, and repeat the
untreated-first qualification under a separately frozen preregistration. No
0ecc result or protected historical speed is replaced or lowered.

## Goal

Qualify whether the protected TP1 strict speed class is preserved on the
literal-current vLLM-0ecc/XPU-kernel-`baaa05bb4e` stack and the current host
kernel without reverting upstream code and without transporting any compiled
artifact. This is a performance-preservation step required before TP2/TP4 and
the wider neural.download coverage matrix.

## Frozen parent evidence

The completed six-arm campaign used vLLM
`0ecc284790e5403f74b899524ef82ecb69f83cb3` and official XPU-kernel main
`baaa05bb4e92901219a5a072dd63f2474896f6d1`. Remote checks after completion
still resolved both commits as literal `main` and the official image as digest
`sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`.

The stock-base-kernel control passed at
`30.282672968694783 / 30.324297716696414 / 30.325970521145816 tok/s`. The
current-kernel lane passed all correctness and quality gates but measured
`30.293320491708876 / 30.27919625650121 / 30.261661472495938 tok/s`, missing
both strict gates. That lane remains frozen evidence from the old boot, not a
same-boot control for the program below.

That parent campaign ran on host kernel `7.0.0-28-generic`. Before this
decision-overlay program was committed or launched, the host became
unresponsive, was hard-rebooted, and selected `7.0.0-30-generic`. The prior
boot has no graceful shutdown record or terminal fault that attributes the
freeze, and the candidate overlay did not run. NVMe SMART after reboot reports
zero media errors and zero NVMe error-log entries; one corrected PCIe receiver
AER event was observed. Upstream vLLM, XPU-kernel main, and the official
nightly digest were re-resolved after reboot and remain the exact identities
above.

The program is therefore explicitly cross-boot. It may qualify this packet as
a current-host performance overlay, but it cannot prove that the decision
packet, rather than the host-kernel transition or noise, caused a change from
the old untreated strict measurements. All three candidate arms must run on
one boot of exactly `7.0.0-30-generic`; a boot or kernel change stops the
program stale.

## Post-reboot prerequisites and same-boot control

Before model work, the one-shot
`run-20260824-qwen38-postreboot-hardware-gate.sh` must pass on the exact boot.
It requires four exact B70 identities, a compute operation on every card, the
four-device peer-read oracle, a four-rank XCCL barrier/allreduce, no combined
selector-plus-mask environment, and a clean kernel-journal delta. The first
untreated control arm then performs the exact model identity check and exact
generation canary before its timed requests.

The host-kernel change requires a new same-boot untreated current-code control.
Run at most three untreated arms on one fresh cache: diagnostic, full-quality
strict A, and strict B. They use the same protected floors and all non-speed
gates below. If all three speed gates pass, stop: current main is qualified
without this packet, and the packet remains unqualified and unnecessary. If
any speed gate misses while every non-speed gate passes, freeze that result and
only then permit the three decision-overlay arms. If a non-speed control gate
fails, stop without testing the packet.

The two fresh compile caches have:

- identical outer namespace `d65565f7e2`;
- identical AOT namespace
  `68fc8c632858eb7c65d6de5b3d4f347cb96e1b18357ec6468847d6c7010adc9d`;
- identical code/compiler/config hashes
  `fb13d4aa1ef8a386c76ab56d39925ff4de083895d9dcbd136e778046e78bb118`,
  `ddcad03736`, and `7fd9f3bcb2`;
- identical canonical environment SHA-256
  `58a8631879b3855c3c1a408d3dad33d48f66b17f7541f08d51d3f1030d7baceb`;
- byte-identical computation graph SHA-256
  `f493f62d98181193e6760136123c70511e9a0a7f1d91cbf3243008a619553339`;
- the same 38 decision paths and 38/38 matching embedded `configs_hash`
  values;
- 17 differing normalized winner selections and 21 identical selections.

That establishes exact mapping compatibility but does not predict a speed win.

## Frozen decision packet

The candidate packet is
`experiments/qwen38-27b-b70/autotune-winner-overlays/tp1-0ecc-stock-kernel-best-config-candidate/`.
It contains exactly 38 regular `.best_config` JSON files. Its manifest SHA-256
is `b941bb71c1d264dcd55104b106b2dff6a85c686776b072e0ef6cc18a8354c928`.

All 38 files are copied unchanged. The experiment must not synthesize a hybrid
decision, transfer only the 17 differences, or edit timing metadata. The packet
contains no generated kernel, `.py`, `.so`, binary, AOT model, outer cache,
modelinfo, lock, or XDG file.

The target starts with a nonexistent ext4 cache. Before launch, the runner may
create only the exact AOT/inductor directory and copy the 38 decision records
with their relative paths. It then must prove:

- the precompile cache contains exactly those 38 files;
- the current-kernel image performs a fresh graph/AOT compile;
- no prior AOT model is directly loaded;
- generated outer/AOT/code/compiler/config/environment/graph identities equal
  the constants above;
- the compiler and workload leave all 38 decision bytes unchanged and create
  no extra `.best_config` records.

The image remains `neural.download.overlay=none` because no source or image
overlay exists. Run evidence must separately label this as a runtime
`best_config` decision overlay.

## Conditionally capped decision-overlay arms

Maximum after a clean same-boot control speed miss: three TP1/GPU0 arms,
serialized on a second new cache. All use MTP0,
F16 model/KV, 32K maximum context, graph `FULL_AND_PIECEWISE` with sizes
`[1,2]`, one sequence, 1024 batched tokens, 0.90 memory utilization, async
scheduling, prefix cache off, chunked prefill on, and `PYTHONHASHSEED=0`.

1. Seeded-fresh diagnostic: 25 unique cold prompts, 512 tokens, EOS ignored.
   It must clear `30.2178 tok/s` and every normal model, canary, benchmark
   shape, GPU, graph, cache, image, and source-recency gate. Stop on a miss.
2. Exact-cache natural-EOS replay A: full quality battery and frozen baseline.
   It must clear `30.31067504052998 tok/s`, pass seven exact cases, eight
   repeats, the 8K/7,617-token needle, 24/24 baseline comparisons, and all
   cache-zero gates. Stop on a miss.
3. Exact same-cache natural-EOS replay B: it must also clear
   `30.31067504052998 tok/s`. The complete cache must remain byte-identical
   across both replays.

All three arms retain returned token IDs and 100-event/99-interval accounting.
Replay A/B full and first-100 token-array agreement is reported but remains
non-gating, matching the parent preregistration.

## Frozen interpretation

- If the untreated same-boot control passes all speed gates, stop and qualify
  the zero-decision-overlay current base; do not run or credit this packet.
- If the untreated control has a speed-only miss and all three overlay arms
  pass, this exact 38-decision packet is a qualified
  versioned runtime overlay for vLLM 0ecc/kernel `baaa05bb4e` on the recorded
  `7.0.0-30-generic` boot. The result proves that this current configuration
  preserves the frozen speed contract. It does not prove that the packet
  caused recovery from the cross-boot untreated measurements or identify a
  kernel source cause.
- If any overlay arm misses, preserve the packet and result as a negative. Do not
  advance TP2, do not lower a floor, and do not retreat to an older active
  source base.
- If upstream vLLM, XPU-kernel, official-base digest, the exact built image,
  host kernel/boot, or the clean pushed lab commit changes during the program,
  stop stale. Rebuild or rederive mapping compatibility rather than blindly
  carrying the decisions.
- No result replaces the historical TP1/2/4 captures.

On pass, immediately build topology-specific current-main runners and remap the
accepted 78-decision TP2 and 152-decision TP4 packets using the same exact-path
and embedded-`configs_hash` rules. TP4 remains fixed at memory utilization
0.60; 0.90 is forbidden.

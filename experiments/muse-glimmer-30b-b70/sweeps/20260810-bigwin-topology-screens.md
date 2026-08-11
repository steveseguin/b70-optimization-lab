# 2026-08-10 Big-Win Topology Screens (Post-Priority-Pivot)

Operator pivot: chase large fast wins first; defer slow/source-level fixes
(including the determinism lane) to later. Same harness and identity as
prior sweeps unless noted. Raw JSONL under
`/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/`.

## Screen results

1. **Multi-slot DFlash is broken for serving.** Q8 2-card, `-np 2`,
   dflash n5 p0.1: c1 on the same server 40.3 tok/s (code), but two
   concurrent streams collapse to 5.7 tok/s per request, 11.0 aggregate -
   below a single no-spec stream. Fleet rule: DFlash replicas run
   single-slot; concurrency comes from replica count.
   Log: `servers/np2-dflash-test.log`.

2. **Single-card no-spec is a big baseline win.** Official kquant-17gb
   (16.76 GB) on one B70: 27.6-27.8 tok/s flat across prompt classes,
   twice per-card efficiency of the 2-card Q8 split (15.9). Bytes/token
   scaling held (90%+ efficiency). laneC/laneE JSONL.

3. **DFlash on a single card is neutral-to-negative today.** Best rung
   n_max=4 p0.1: avg 26.8 vs 27.6 no-spec (n5 25.1, n6 22.8). The 2-card
   dflash win came from drafter work hiding in pipeline bubbles; on one
   card it serializes. laneC JSONL.

4. **Cross-card drafter is blocked upstream.** `-dev SYCL0
   --spec-draft-device SYCL1` aborts at
   `ggml-backend.cpp:930: pre-allocated tensor (output.weight) in a buffer
   (SYCL0) that cannot run the operation` - the dflash draft graph shares
   the target's LM head, so the drafter cannot colocate on another device
   without mirroring shared tensors. Filed to the later source-work lane;
   expected upside is restoring the ~2.4x dflash ratio on top of the
   single-card base. laneE JSONL + `servers/sweep-E-crossdraft-nmax4.log`.

5. **Determinism discriminator answered: kernel-level, not split.**
   Single-card no-spec repeats differ on prose/code (json matched), same
   pattern as 2-card. Confirms upstream SYCL kernel nondeterminism; parked
   in the later lane. laneC ref-nospec vs ref-nospec-2.

## Fleet shapes on the board (avg-of-3-classes per replica)

| Shape | per-replica | replicas | aggregate | quality | status |
| --- | --- | --- | --- | --- | --- |
| 2-card Q8 + dflash n5p01 | 38.0 (29.7/44.8/39.4) | 2 | 76 | Q8_K_XL near-lossless | measured |
| 1-card 17gb no-spec | 27.6 | 4 | 110 | 1.0% degradation (below bar) | measured |
| 1-card dynamic no-spec | ~23.5 proj | 4 | ~94 | 0.2% (compliant) | laneD pending |
| **2-card dynamic + dflash** | ~55-62 proj | 2 | ~110-124 | 0.2% (compliant) | laneF pending |
| 1-card + cross-card drafter | ~50+ proj | up to 4 | 200+ | artifact-dependent | blocked (source work) |

laneD (single-card dynamic, GPU1) and laneF (2-card dynamic + dflash,
GPUs 2+3) fire automatically when the dynamic download lands.

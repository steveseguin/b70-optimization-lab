# Laguna INT4 kernel optimization loop — running ledger

Started: 2026-07-28 America/Toronto. Orchestrator owns the GPU and all
measurements; subagents write and attack code and never run a leg.

## Fixed context

| field | value |
| --- | --- |
| kernel tree | `/home/steve/src/laguna-xpu-kernels-tile12-20260728` |
| branch | `experiment/laguna-tile12-20260728` |
| loop baseline commit | `46a88e09d96fe06871c87a23de534fb47f1e039b` |
| vLLM tree | `/home/steve/src/laguna-vllm-replemb-bf16-20260727` @ `d1a72ff78f2db4a51b9c7d84506b201c26d0baae` |
| installed `libgrouped_gemm_xe_2.so` | `53f3d2941ce322bcdff1b0463ec6fe72387036ea54d3f602a08d690744b3459f` |
| runtime lock | `tools/runtime-lock-mad.json` = `792ed7a94f77881b72935f28470f6d2281b738d99c681eb09a0fc801ee6f1563` |
| noise floor | 1.63% — nothing under ~1.5% resolves in one leg |

## Incumbent

`VLLM_XPU_LAGUNA_SCALE_VEC=1`, `VLLM_XPU_LAGUNA_DEQUANT_MAD=0`, prefetch 6,
W1 N-tile 64, width 12 / DFlash 11, BF16 KV, TP4+EP4.

| arm | n | median | mean | >=102 |
| --- | ---: | ---: | ---: | ---: |
| **incumbent (mad0)** | 13 | **102.134914** | 101.946829 | 8 |
| control `SCALE_VEC=0` | 3 | 100.048816 | 100.240049 | 0 |

Reproduced independently from the run artifacts by
`tools/laguna_ab_summarize.py`, which refuses to report a rate from any leg
that failed exactness. Those numbers agree to all six decimals with the
recorded result, so the reading pipeline is validated, not assumed.

## Tooling added this session

- `tools/laguna_ab_campaign.sh` — round-robin interleaved multi-arm campaign on
  ONE binary. Arms differ only in selector values; drift hits every arm
  equally.
- `tools/laguna_ab_summarize.py` — per-arm median/mean/min/max/`>=102`/failed.
  A leg that failed exactness contributes no rate.
- `run_laguna_replemb_measurement_leg.sh` extended with argument 25,
  `VLLM_XPU_LAGUNA_SCALE_HOIST`. Script sha256 is now
  `c245bb39bba1fb14d6320c1cd928576f43c68df2d9819ea3ff5cfbbeac1e74e2`; every leg
  in this campaign shares that one hash, so no leg is compared across script
  versions.
- `tools/mint_runtime_lock.py` — copies the SEALED packet lock and changes
  exactly one field, the mapped `libgrouped_gemm_xe_2.so` sha256, located by
  path rather than index. Refuses to overwrite the sealed lock and asserts the
  sealed file round-trips byte-for-byte under its serializer first.
  **Validated**: re-minting against the installed `.so` reproduces
  `792ed7a94f77881b72935f28470f6d2281b738d99c681eb09a0fc801ee6f1563`, the exact
  lock the recorded 13-leg campaign ran under.
- `tools/binaries/libgrouped_gemm_xe_2.so.53f3d294-incumbent-46a88e0` — a
  verified copy of the **incumbent 102.13 binary**, taken before any promotion
  overwrites `vllm_xpu_kernels/`. Its sha256 was checked against
  `53f3d294...3459f` after copying. Rebuilding it from `46a88e0` would cost a
  ~50-minute build and is not guaranteed byte-reproducible, so the file is the
  rollback path, not the commit.
- GPU interlock at
  `/tmp/claude-1000/-home-steve/aa7f8c7a-aca4-4926-b457-af0a6974ada3/scratchpad/GPU_LOCK`.
  Subagents poll it before any GPU execution; compile-only work is
  unrestricted. Four concurrent GPU users once distorted a measurement ~2x.

## Iterations

### Iteration 1

- **T1 — `SCALE_HOIST`. DEAD AT STAGE 0/1.** No code, no build, no GPU. IGC
  already hoists it: the 21 instructions of scale reload and address recompute
  sit behind `(W&~f1.0) jmpi` and run once per group, and at `G=32` IGC deletes
  the predicate outright. The "53 non-arithmetic" figure was a **static
  listing** count; the dynamic cost is 39.25. A floor probe that deletes the
  whole mechanism puts the body at 128.0 against 137.25, and 5.25 of that 9.25
  is the reload any correct scheme must still perform — leaving **4.00
  instructions, 2.9% of the body, ~2.1% net**, under the 5% bar and under the
  1.63% noise floor. Note:
  `notes/2026-07-28-scale-hoist-already-done-by-igc.md`.
  **Stage-0/1 death #2 of the 3 that end the loop.**

### Iteration 2

- **T5 — make `PREFETCH_DIST` reachable on decode.** T1's exit finding, verified
  independently by the orchestrator: `MoEGEMMLauncher` never calls
  `laguna_int4_prefetch_dist()`; its only three call sites are the M8 launchers
  that `num_rows=12` never reaches, so decode compiles against a
  constant-folded 6 (`add r4.12, r4.9, 768`, 768 = 6*128). **This retires the
  recorded closure "prefetch distance 3 and 12 vs 6" as evidence** — those arms
  were the same machine code on the decode path.

  A **different class of lever**: memory timing, not instruction count, so the
  stage-1 instruction gate cannot screen it and only a leg can size it. That
  matters, because the termination rule exists to say "the next move is a
  different class of change" — this is one. Bitwise-neutral by construction:
  Xe2 block prefetch is a null-destination send that writes no GRF.

  Chief risk, briefed explicitly: naive runtime plumbing may de-fold the
  constant and import the M8 path's ~100-instruction prologue (522 vs 422),
  regressing the default at every distance. If runtime costs more than ~2% of
  the body the fallback is compile-time specialization over the existing
  literal allowlist, paid for by dropping a dispatch combination. Optimizer
  running. Status: **open**.

  Attractive property: after one build, 3/6/12 is a **free runtime sweep on one
  binary**, and dist=6 doubles as a built-in neutrality check — it must
  reproduce today exactly.

## A harness defect caught before it spent GPU

`laguna_ab_campaign.sh` originally expanded each arm's argument string with
plain word splitting. Three leg arguments are legitimately empty —
`EVENT_PROFILE_ROOT` (17), `MXFP4_SMALL_M_N` (20) and `SCALE_HOIST` (25) — and
word splitting turns `''` into a **literal two-character token**, not an empty
string. The leg would then have exported
`VLLM_XPU_LAGUNA_REPLAY_EVENT_PROFILE_ROOT="''"`, a non-empty value, plausibly
switching event profiling on inside a scored measurement and distorting the
very timing being measured.

Found by running the arm specs against a stub that prints `%q` for every
argument, before any leg ran. Fixed by re-parsing each spec with the shell's own
quoting rules (`eval "argv=($args)"`) and passing `"${argv[@]}"`. Re-verified
end to end: `argc=25`, arguments 17/20/25 genuinely empty, and `PREFETCH_DIST`
landing in slot 21 as 3, 6 and 12 across the three arms with `SCALE_VEC=1` and
`DEQUANT_MAD=0` held fixed.

This is the same class of hole the adversary brief lists as "empty-string env
values" — and it was in the orchestrator's own harness, not the kernel. Verify
the instrument before trusting what it measures.

## T5 interim findings

**Stage 0: the premise HOLDS.** Reachability confirmed independently by the
agent from source and bmg ISA, matching the orchestrator's own check. Decode
carries `add r4.12, r4.9, 768:w` (768 = 6*128); compile-time 3 and 12 give
`384:w` and `1536:w`. Harness cross-validated by reproducing the SCALE_VEC
33-instruction delta.

**Reachability is not free, and the naive fix is the wrong one** — the risk
briefed in advance is real and measured:

| build | total | mainloop | prologue | spills |
| --- | ---: | ---: | --- | ---: |
| today, compile-time 6 | 375 | 137 | unrolled, 18 prefetch sends | 0 |
| naive runtime `int` | 475 | 137 | **rolled: 147-instr loop + 25 remainder** | 0 |
| shipped change | 647 | 137 | 3 unrolled arms (9/18/36 sends) | see below |

The cost is *entirely* prologue; the mainloop is 137 instructions with an
identical float/int/mem/dpas split in every case. So the distance travels as a
runtime `int` — no new kernel or mainloop instantiations — and only the
prologue is emitted per allowlist value behind a scalar branch. At dist=6 that
is today's 90-instruction prologue plus ~9 scalar instructions.

**Stage 3 PASSED.** today vs new at {unset, 3, 6, 12}: bitwise identical across
155 tensors and 11.7M elements, and again with `DEQUANT_MAD=1`. The scale
populations were verified to contain what they claim rather than assumed:
7970 negative, 745 zeros of which **321 are −0.0**, 8006 BF16 subnormals,
max |s| = 3.097e38.

**Self-reported defect, accepted:** dist=6 is **not** byte-identical in the
mainloop. Instruction count, pipe split and scoreboard-wait count all match,
but one `mov` becomes a `shl` and two single-token `sync.nop` become
three-token `sync.allrd`.

**Two open items blocking promotion:**
1. The shipped library's largest kernel, `w4a16_policy` — the >=128-row
   **prefill** path, not decode — reports a **4928/960-byte spill**. Today's
   build has zero spills everywhere. A pristine-tree probe is deciding whether
   this is pre-existing or introduced. If introduced, the specialization gets
   gated to the small-M decode policies and rebuilt. The scored suite contains
   an 863-token prompt, so prefill is on the measured path; "decode is
   unaffected" is not an acceptable answer.
2. Build peak rose to **119.8 GB** from 117.1 GB, on a 125 GB box. This is now
   the binding constraint on the campaign, not a footnote.

## The plumbing tax is real and sits in the mainloop

Follow-up measurement, both answers worse than hoped and both volunteered:

- **`sync.allrd` is in the loop body**, in the prefetch-issue block, executing
  nearly every k-tile. It went 1 token to 3 because IGC must conservatively
  union the SBIDs live across the three prologue arms. **Whether the extra
  tokens ever stall is unknown from static ISA** and needs an endpoint leg.
  That is the correct answer to give; a guess here would have been worthless.
- **`mov` -> `shl` is not a flat substitution.** The predicate dependency chain
  goes 2 -> 4: `add->cmp` becomes `shr->add->shl->cmp`. It fires every
  iteration at G=32, 1-in-4 at G=128, and is absent at G=256. Not removable at
  source level — IGC re-associates the hoisted form back to identical ISA.

So `new-pd6` may genuinely be slower than `old`. That makes the `old` arm an
early-kill signal for the whole approach, not just an anchor, and it is why it
stays in the campaign.

**It does not invalidate the distance comparison.** All three plumbed arms
carry the same tax, so `pd3`/`pd12` versus `pd6` remains a clean within-binary
measurement of the lever itself. The efficient path is therefore: sweep on the
plumbed binary to find out whether distance matters at all, and only if it does
spend a second build on a compile-time-specialized binary at the winning
distance, which would carry today's exact mainloop and no tax. That defers a
50-minute build until it is known to be worth it, and never builds the losers.

## The 125 GB ceiling is pre-existing, and it is one kernel

The pristine tree at `46a88e0` reaches **116.7 GB for the single
`w4a16_policy` INT4 instantiation alone**, with 6 GB free. The ceiling was set
before this candidate existed; T5 adds to it but did not create it. This
**exonerates T5 on build memory** and promotes T2 from cleanup to the
structural blocker on every future candidate, since one kernel already consumes
the machine. It also means gating the specialization away from `w4a16_policy`
would recover the build-memory delta and the spill together, because that
kernel is where nearly all of both live.

## Revised measurement design, forced by the non-identical mainloop

Because dist=6 is not byte-identical, **`pd6` cannot be treated as
performance-neutral by construction** and the plumbing cost must be measured.
That comparison is unavoidably cross-binary — but the old binary *ignores*
`PREFETCH_DIST` entirely, which is the whole finding, so it collapses to a
single arm rather than three.

Four arms, round-robin, binary swapped in per leg by
`tools/laguna_xbin_campaign.sh`:

| arm | binary | distance | answers |
| --- | --- | --- | --- |
| `old` | 53f3d294 | n/a (knob unreachable) | the incumbent, re-measured today |
| `new-pd6` | e0bb78a3 | 6 | what the plumbing itself cost |
| `new-pd3` | e0bb78a3 | 3 | does a shorter distance help |
| `new-pd12` | e0bb78a3 | 12 | does a longer distance help |

Interleaving at **leg** granularity rather than in blocks is what makes a
cross-binary comparison defensible: every arm sees the same drift, thermal
state and ordering. n=5 per arm is 20 legs, roughly 140 minutes.

**One checked-out tree per binary, not a swapped `.so`.** The leg script stamps
`kernel_commit` from `git -C "$kernel_root" rev-parse HEAD`
(`run_laguna_replemb_measurement_leg.sh:135`, recorded at line 356) and never
validates it against the binary actually loaded. Installing the incumbent
`.so` into a tree checked out at `ec4c7ea` would therefore have stamped every
`old` leg with the wrong commit — the `.so` hash is recorded and validated, so
no decision was at risk, but the artifact would have been misleading. Fixed by
giving the incumbent its own worktree,
`/home/steve/src/laguna-xpu-kernels-incumbent-46a88e0`, checked out at
`46a88e0` with the incumbent binary in place. Commit and binary now agree per
arm, and the per-leg install — along with its failure mode of silently
measuring the previous arm — is gone entirely.

`run_pfreach_campaign.sh` asserts each tree's grouped-GEMM sha256 against the
binary its arm is named for before the first leg. Verified to fire: with the
new `.so` not yet installed it aborts with the incumbent hash and the reason.
Without that guard a forgotten install would leave all four arms measuring the
same code for 140 minutes and produce a confident null result meaning nothing.

The ship decision is `best-new-arm` vs `old`. `new-pd6` vs `old` is reported
separately as the plumbing tax, and `pd3`/`pd12` vs `new-pd6` as the lever
itself.

## Planned T5 sweep

Three arms on ONE binary, round-robin, n>=5 each: `pd6` (control **and**
plumbing-neutrality check), `pd3`, `pd12`. Roughly 105 minutes.

`pd6` must reproduce today's behaviour, because unset and 6 are the same
compile-time default the decode path already uses. Comparing `pd6` on the new
binary against the incumbent's 102.134914 on the old one is a **cross-binary**
sanity indicator only — it is reported as such and never as the decision. The
decision is `pd3` and `pd12` against `pd6` within the new binary.

## GPU accounting

Deliberately idle during iteration 2's build. The runtime selector space on the
installed binary is exhausted: `SCALE_VEC=1` and `DEQUANT_MAD=0` are the
measured optimum, `SCALE_FOLD` breaks exactness, `W1_N_TILE` 32/128 are closed,
and `PREFETCH_DIST` is now known to be unreachable on decode. There is no
decision a leg could change until T5's binary exists, and a full build plus a
vLLM server would exceed 125 GB. Idle is the correct state, not a wasted one.

One weak closure noted for the record: `DEQUANT_MAD=1` was closed on **n=3**
(median 101.619698) against mad0's n=13 (median 102.134914). That 0.50% gap
sits under the 1.63% noise floor and under the loop's own n>=5 decision bar, so
it is inconclusive rather than refuted. Not re-opened — the mechanism (int pipe
50->65, and int binds) argues against it and the expected value does not
justify delaying T5's build by 75 minutes.
- **T4 — prefetch co-tune premise. DEAD AT STAGE 0.** ~9 min CPU, zero GPU,
  saved ~105 min of 4-card GPU. `prefetch_dist` is a runtime `int`
  (`grouped_gemm_xe2_interface.hpp:103`) threaded as a function argument
  (`gemm_xe2.hpp:631,687`); there are **zero** per-distance template
  instantiations, so 3/6/12 execute the same compiled kernel and the mainloop
  is byte-identical apart from the immediate `32 * dist`. Register pressure was
  never binding either: spill+fill 0, `numGRF` 256, `HWThreadNumberPerEU` 4 in
  all eight builds, and Xe2 block prefetch is a null-destination send that
  writes no GRF. Verified independently by the orchestrator from source before
  acceptance. Note:
  `notes/2026-07-28-prefetch-cotune-premise-dead.md`.
  **Stage-0/1 death #1 of the 3 that end the loop.**

  Lead recorded but **not** promoted: templating the distance would drop a
  ~147-instruction runtime prologue (522 vs 422 instructions at VEC=0), but
  that prologue runs once per workgroup against a mainloop running K/32 times
  — roughly 2.3% at K=1024 and 0.8% at K=3072, under the ~5% stage-1 bar.

## Termination conditions

- A candidate dies when it shows no median gain over its matched control at
  n >= 5. Only a leg decides that; the `mad` fusion was bitwise-perfect over
  1,044,480 cases, cut float-pipe work 45%, and was ~1% slower.
- The loop ends when three consecutive candidates die at stage 0 or 1.

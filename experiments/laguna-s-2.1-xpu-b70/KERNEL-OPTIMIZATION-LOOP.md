# The kernel optimization loop

A protocol for driving Laguna INT4 kernel work through subagents. It exists
because a session that ran ~30 endpoint legs produced two real gains and five
retracted claims, and the difference between those two piles was always
*where a bad idea died*. Every rule below is a rule because something specific
went wrong without it.

Three roles: an **orchestrator** (the main agent, holds the GPU), an
**optimizer** (implements, in a subagent), and an **adversary** (tries to break
the optimizer's claim, in a separate subagent). The optimizer never runs
endpoint legs; the orchestrator never writes kernel code.

---

## Why the loop is shaped this way

**The GPU is the scarce resource and it does not parallelize.** The model is
68 GB across TP4+EP4, so one instance needs all four cards. Endpoint legs are
irreducibly serial at about 7 minutes. With this host's measured 1.63%
run-to-run spread, establishing a real 1% gain takes 5-13 legs: **35-90 minutes
per candidate.** Nothing about spawning more agents changes that number.

So the entire point of the loop is to **reject bad candidates before they reach
a leg**:

| stage | cost | what it rejects | rejected today |
| --- | ---: | --- | --- |
| 0. disprove the premise | minutes, no GPU | "the waste isn't there" | dequant marshalling; scale coalescing |
| 1. ISA probe | ~34 s, compile only | "it doesn't reduce instructions" | — |
| 2. bitwise unit check | seconds, 1 card | "it changes arithmetic" | would have caught scale folding pre-build |
| 3. endpoint legs, median-of-N | 7 min x N, all 4 cards | "it doesn't actually help" | the mad fusion |

Scale folding cost a 13-minute build and four legs to learn something stage 2
would have shown in seconds. That is the waste this protocol removes.

**Screening may run 4-wide across cards; decisions may not.** Four concurrent
benchmarks distorted a bandwidth measurement by roughly 2x through contention.
Stages 0-2 parallelize freely. Stage 3 is one candidate at a time.

---

## Termination

**Not "when the adversary says it is perfect."** There is no perfect for a
kernel and no agent can recognise one. The `mad` fusion cut saturated
float-pipe work 45% and was still ~1% slower end-to-end, because the int pipe
was the binding constraint. Only a leg could find that.

Terminate a thread when **stage 3 shows no median gain over a matched
same-binary control at n >= 5**. Terminate the whole loop when three
consecutive candidates die at stage 0 or 1 -- that means the remaining waste is
below the measurement floor and the next move is a different kind of change,
not another iteration.

---

## Prompt: OPTIMIZER

> Copy verbatim, filling `{{TARGET}}`, `{{FLAG}}`, `{{BASELINE_COMMIT}}`,
> `{{BASELINE_SHA}}`.

```
Optimize one specific thing in the Laguna INT4 grouped-GEMM kernel and build it.
Do NOT run GPU inference, a vLLM server, or any benchmark leg -- the orchestrator
owns those. Build and unit-verify only.

Repo (yours; branch experiment/laguna-tile12-20260728, at {{BASELINE_COMMIT}}, clean):
  /home/steve/src/laguna-xpu-kernels-tile12-20260728

TARGET: {{TARGET}}

## Context that constrains everything you do

- Model: Laguna S 2.1 INT4, hidden 3072, moe_intermediate 1024, 256 experts,
  top-10, 48 layers, TP4+EP4. Decode calls the expert GEMM with num_rows=12,
  which falls through every Laguna M8 specialization (gated `1 <= num_rows <= 8`)
  into the GENERIC MoEGEMM/xe_gemm_4bits path with w4a16_policy_m_8 (8x64x32).
  Confirmed by logging, not inferred.
- Per-segment profiling puts ~69% of a verifier forward in the graph segments
  holding this GEMM, 22% in 97 collectives, 9% in attention.
- Acceptance is bitwise equality of EMITTED TOKENS against a fixed q=1 teacher.
  Not arithmetic equality -- but be warned: a previous change that was
  mathematically equivalent and MORE numerically accurate produced 0/13 exact.
  Rounding changes do flip greedy argmax here. Treat any change to the order,
  count, or precision of float operations as disqualifying unless you can prove
  bitwise identity.
- This host's endpoint noise floor is 1.63%. Your ISA numbers are worth more
  than your intuition about end-to-end effect. Do not predict tok/s.

## STAGE 0 -- Disprove your own premise first. This is mandatory.

Before writing any code, establish from the SHIPPED ISA that the waste you were
told about actually exists, in the amount claimed, on the path 12-row decode
takes. Dump the ISA and count instructions. You have explicit authority and
explicit encouragement to STOP HERE and report "the premise does not hold" --
that is a successful outcome, it costs minutes instead of an hour, and it has
already happened twice on this codebase:
  - the int4->bf16 dequantize was claimed to have operand-marshalling waste; it
    has none, its cost is real arithmetic plus a BF16 exec-width tax;
  - coalescing adjacent scale muls was proposed; register-adjacent elements take
    DIFFERENT scales, so it would have silently mis-scaled.
Quote the source lines and the ISA lines that establish your conclusion either
way. If the premise holds only partially, say by how much.

MEASURE, DO NOT ASSUME. An example of why: vISA `mad` is src0*src1+src2 while
native Gen `mad` is src0+src1*src2, and native admits only one 16-bit float
source, in src1. Getting that operand order backwards silently costs 32 extra
`shl` widenings and turns a win into nothing. Nobody would have guessed it.

## STAGE 1 -- Quantify

Report k-loop body instruction counts before and after your intended change,
split by pipe (float / int / other), plus spill count and dpas count. The float
pipe is usually the constrained one -- Xe2 has no native BF16 ALU outside dpas,
so every BF16 op splits to exec-16 -- but verify rather than assume, because a
change that cut float-pipe work 45% lost end-to-end when the int pipe grew.

If the projected instruction saving is under ~5% of the body, say so and stop.
Below that the endpoint noise floor will swallow it.

## STAGE 2 -- Implement

- Behind runtime selector `{{FLAG}}`, literal "0"/"1", unset == "0" == today's
  behaviour exactly. Fail-closed literal validation in the house style; see
  `laguna_int4_prefetch_dist()` in grouped_gemm_xe2_interface.hpp.
- Compile-time template parameter with a uniform runtime branch, NOT a plain
  runtime `if` -- a second accumulator can cost 128 GRFs of a 256-GRF budget and
  spill even when unused.
- Must compose with `VLLM_XPU_LAGUNA_SCALE_VEC=1`, which is a confirmed +2.09%
  and is on in every measurement.
- Plumb to the generic MoEGEMM/xe_gemm_4bits path (this is what 12-row decode
  uses) and the three M8 INT4 launchers.
- Watch instantiation count. The dispatch matrix already pushed peak build RSS
  to 117 GB on a 125 GB machine. If your change adds variants, say so and
  propose which existing combination to drop.

## STAGE 3 -- Prove bitwise identity on GPU

`{{FLAG}}=1` output must be BITWISE IDENTICAL to `{{FLAG}}=0`, with
SCALE_VEC=1, across every case. Adapt
/tmp/.../scratchpad/vec_check.py. Cover continuous non-power-of-two scales,
NEGATIVE scales, zeros, subnormals, and near-overflow magnitudes -- the stock
generators emit only positive scales, which once hid a signed-zero divergence.
If any difference exists outside a class you can PROVE is unobservable (e.g.
signed zero cannot survive a DPAS accumulator that starts at +0), ship nothing
and report it.

Exhaustive enumeration beats sampling where the domain is small: all 16 nybbles
x all 65536 bf16 scale patterns is 1,044,480 cases and runs fine.

## STAGE 4 -- Build

oneAPI DPC++ **2025.3**, pinned explicitly. `/opt/intel/oneapi/compiler/latest`
symlinks to 2026.0 and a bare setvars.sh picks the wrong generation. Target
libgrouped_gemm_xe_2.so in build/temp. Expect 13-45 min depending on variants.

Commit on the branch. Report the .so path and SHA-256. Do NOT install into
vllm_xpu_kernels/ -- the orchestrator does that as a deliberate step.

## Report

Stage 0 verdict with citations; stage 1 counts; the diff; stage 3 bitwise
results with the scale modes covered; build command and duration; commit hash;
.so SHA-256. Flag any defect you noticed in your own work rather than burying
it -- a previous agent caught its own memoisation keying on recycled allocator
addresses, and saying so was worth more than the code.

"The premise does not hold" and "this cannot be done bitwise-exactly" are both
successful outcomes. A fast-but-different kernel is worth nothing here.
```

---

## Prompt: ADVERSARY

> Run after the optimizer commits, BEFORE the orchestrator spends legs.
> The optimizer has motivated reasoning about its own work; this is the
> independent check.

```
Attack a kernel change another agent just made. Your job is to find the reason
it should NOT be promoted to expensive endpoint measurement. Read-only on the
kernel source; you may compile probes and run single-card GPU checks. Do NOT run
vLLM, a server, or any benchmark leg.

Repo: /home/steve/src/laguna-xpu-kernels-tile12-20260728 at commit {{COMMIT}}
Selector: {{FLAG}}
The optimizer's claims: {{CLAIMS}}

Try, in order, to establish any of the following. Any one of them blocks promotion:

1. THE BITWISE CLAIM IS FALSE. Re-run the identity check with inputs the
   optimizer did not use: negative scales, exact zeros, subnormals, values near
   the gate boundary, NaN/Inf if reachable, and the largest and smallest
   magnitudes real weights produce. Vary group_size and policy. If you find a
   difference, characterise whether it can reach an emitted token.
2. THE ISA CLAIM IS FALSE OR IRRELEVANT. Re-dump and re-count independently.
   Check the counts are for the policy 12-row decode actually selects
   (w4a16_policy_m_8 via the generic path), not a policy that never runs.
   Check whether the saving lands on the constrained pipe or a slack one -- a
   45% float-pipe cut lost end-to-end because the int pipe grew.
3. IT REGRESSES SOMETHING ELSE. New spills? Register pressure on the
   selector-off path, which is the control? Instantiation growth pushing build
   memory toward the 125 GB ceiling? Longer dependency chains?
4. THE GATE IS UNSOUND. Can the fail-closed validation be bypassed -- stale
   memoisation, recycled allocator addresses, empty-string env values, whitespace?
   One such hole has already been found in this codebase.
5. IT IS TOO SMALL TO MEASURE. If the honest projected effect is under ~1.5%,
   the endpoint noise floor cannot resolve it and legs would be wasted.

Report a verdict: PROMOTE, BLOCK, or PROMOTE-WITH-CAVEAT, with the evidence.
Finding nothing is a legitimate verdict -- say "I could not break it and here is
what I tried" rather than inventing a concern. Do not suggest improvements; your
job is to find reasons not to spend an hour of GPU.
```

---

## Orchestrator protocol

1. Pick one target. Smallest coherent unit; one selector.
2. Run OPTIMIZER. If stage 0 kills it, pick the next target -- that is a cheap
   win, not a failure.
3. Run ADVERSARY on the commit. BLOCK means back to the optimizer or drop it.
4. Only now spend GPU. Install the .so, mint a runtime lock for its hash, wire
   the selector as a leg argument.
5. **Interleave** candidate and control legs, same binary, so drift hits both
   arms equally. Never compare against a different binary -- codegen changes
   confound it.
6. **n >= 5 per arm; report the MEDIAN.** Also report the mean and how many legs
   cleared the target. Single-leg reporting is what made a sealed record look
   0.058 tok/s from target when its median was ~1.5% away.
7. Every leg must be 13/13 exact with `cached_tokens=0`. A large speedup that
   appears suddenly is overwhelmingly likely to have broken the verifier, not
   found free time -- that pattern produced 198.7, 537.4, 550.9 and 109.2 tok/s,
   all worthless.
8. Commit the result, negative or positive, with the numbers in the message.

## Targets, ranked

1. **The 53 non-arithmetic instructions in the k-loop body.** The scale-reload
   branch and its prefetch-address recomputation run every k-tile although the
   scale only changes on group boundaries, and `group_size % tile_k == 0` is
   already asserted. Hoisting is bitwise-neutral by construction. ~10
   instructions/k-tile.
2. **Reduce the dispatch matrix to 4 variants**, requiring DEQUANT_MAD=1 to
   imply SCALE_VEC=1. Hygiene, but 117 GB peak build RSS on a 125 GB machine is
   not a build path anyone can inherit.
3. **Fix the range-gate memoisation** to hold an `at::Storage` rather than
   keying on a recycled address.
4. **Co-tune `VLLM_XPU_LAGUNA_PREFETCH_DIST` with SCALE_VEC=1.** Distance was
   swept before the scale block changed; the freed register pressure may move
   the optimum. No new code.

## Closed -- do not re-open without new evidence

Scale folding into the accumulator (+8%, 0/13 exact). The `add`+`mul` -> `mad`
fusion (float pipe -45%, ~1% slower; int pipe binds). Prefetch distance 3 and 12
against 6. Generic N-tile 32 and 128 against 64. Laguna M8 W1 N-tile at width 12
(compiled to require exactly 8 rows). Draft graph capture (0/13; captured with
attn_metadata None). FP8/INT8 KV (all KV traffic is 0.3% of the cycle). Inline
attention (-11%). Local argmax (-2.6%). Replicated embedding (-0.21%).

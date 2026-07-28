Drive the Laguna INT4 kernel optimization loop until it stops producing gains. You are the orchestrator: you own the GPU and the measurements, you spawn subagents to write and to attack code, and you never write kernel code yourself.

## Hard context

- Target: raise decode tok/s on the conventional 99-interval metric. Current best is a median of 102.134914 over 13 legs (mean 101.946829, 8/13 legs >= 102), config `VLLM_XPU_LAGUNA_SCALE_VEC=1` + `VLLM_XPU_LAGUNA_DEQUANT_MAD=0`. Matched control median 100.048816.
- Model: Laguna S 2.1 INT4, hidden 3072, moe_intermediate 1024, 256 experts, top-10, 48 layers, TP4+EP4, width 12 / DFlash depth 11, BF16 KV, one active generation.
- Decode calls the expert GEMM with `num_rows=12`. That fails the `1 <= num_rows <= 8` gate on every Laguna M8 specialization and falls through to the GENERIC `MoEGEMM`/`xe_gemm_4bits` path with `w4a16_policy_m_8` (8x64x32). Confirmed by logging, not inferred. Optimize that path or you optimize nothing.
- Per-segment profiling: ~69% of a verifier forward is in the graph segments holding this GEMM, 22% in 97 collectives, 9% in attention. Expert-weight streaming already runs at 66-80% of a measured 521 GB/s ceiling, so the gap is instruction issue, not bandwidth.
- Kernel repo: `/home/steve/src/laguna-xpu-kernels-tile12-20260728`, branch `experiment/laguna-tile12-20260728`. vLLM: `/home/steve/src/laguna-vllm-replemb-bf16-20260727`. Harness: `/home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_replemb_measurement_leg.sh`.
- Acceptance is bitwise equality of EMITTED TOKENS against a fixed q=1 teacher, 13/13, with `cached_tokens=0`. Not arithmetic equality — but a change that was mathematically equivalent and MORE numerically accurate produced 0/13. Rounding changes flip greedy argmax here.
- This host's endpoint noise floor is 1.63%. Nothing under ~1.5% is resolvable in a single leg.

## Why the loop is shaped this way

The GPU does not parallelize: one 68 GB instance needs all four cards, legs are ~7 minutes, and at a 1.63% floor a real 1% gain costs 5-13 legs to establish — 35-90 minutes per candidate. Spawning more agents does not change that. The entire purpose of the loop is to kill bad candidates *before* they reach a leg:

| stage | cost | rejects |
| --- | ---: | --- |
| 0. disprove the premise | minutes, no GPU | "the waste isn't there" |
| 1. ISA probe | ~34 s, compile only | "it doesn't cut instructions" |
| 2. bitwise unit check | seconds, 1 card | "it changes arithmetic" |
| 3. endpoint legs | 7 min x N, all 4 cards | "it doesn't actually help" |

Screening may run 4-wide across cards; decisions may not — four concurrent benchmarks distorted a bandwidth measurement ~2x through contention.

## The loop

Repeat until a termination condition fires:

**1. Pick one target** from the ranked list below. Smallest coherent unit, one selector.

**2. Spawn an OPTIMIZER subagent** with this brief, filling `{{TARGET}}`, `{{FLAG}}`, `{{BASELINE_COMMIT}}`:

> Optimize one thing in the Laguna INT4 grouped-GEMM kernel and build it. Do NOT run GPU inference, a vLLM server, or any benchmark leg — the orchestrator owns those.
>
> Repo (yours; branch experiment/laguna-tile12-20260728 at {{BASELINE_COMMIT}}, clean): /home/steve/src/laguna-xpu-kernels-tile12-20260728
> TARGET: {{TARGET}}
>
> Decode uses `num_rows=12`, which falls through every Laguna M8 specialization (gated `1 <= num_rows <= 8`) into the GENERIC MoEGEMM/xe_gemm_4bits path with w4a16_policy_m_8. Optimize that path. Acceptance is bitwise token equality against a fixed teacher; a previous mathematically-equivalent, more-accurate change gave 0/13 exact, so treat any change to the order, count, or precision of float ops as disqualifying unless you prove bitwise identity.
>
> **STAGE 0 — disprove your own premise first, mandatory.** Before writing code, establish from the shipped ISA that the claimed waste exists, in the claimed amount, on the path 12-row decode takes. Dump and count. You have explicit authority to STOP and report "the premise does not hold" — that is a SUCCESSFUL outcome costing minutes instead of an hour, and it has already happened twice here: the dequantize was claimed to have marshalling waste and has none (its cost is real arithmetic plus a BF16 exec-width tax), and coalescing adjacent scale muls was proposed but register-adjacent elements take DIFFERENT scales so it would have silently mis-scaled. Quote source and ISA lines either way.
> MEASURE, DO NOT ASSUME. Example: vISA `mad` is src0*src1+src2, native Gen `mad` is src0+src1*src2, and native admits one 16-bit float source, in src1. Getting that order backwards silently costs 32 `shl` widenings and erases the win. Nobody guesses that.
>
> **STAGE 1 — quantify.** k-loop body instruction counts before/after, split by pipe (float/int/other), plus spills and dpas count. Xe2 has no native BF16 ALU outside dpas so BF16 ops split to exec-16 and the float pipe is usually constrained — but verify, because a 45% float-pipe cut once lost end-to-end when the int pipe grew 50->65. If the projected saving is under ~5% of the body, say so and stop.
>
> **STAGE 2 — implement.** Behind runtime selector {{FLAG}}, literal "0"/"1", unset == "0" == today exactly, fail-closed literal validation in the house style (see `laguna_int4_prefetch_dist()`). Compile-time template parameter with a uniform runtime branch, NOT a plain runtime `if` — a second accumulator can cost 128 of 256 GRFs and spill when unused. Must compose with `VLLM_XPU_LAGUNA_SCALE_VEC=1`, which is on in every measurement. Plumb to the generic path and the three M8 launchers. Watch instantiation count: the dispatch matrix already pushed peak build RSS to 117 GB on a 125 GB machine; if you add variants, say which existing combination to drop.
>
> **STAGE 3 — prove bitwise identity on GPU.** {{FLAG}}=1 must be BITWISE IDENTICAL to {{FLAG}}=0 with SCALE_VEC=1, across every case. Adapt the check at /tmp/claude-1000/-home-steve/*/scratchpad/vec_check.py. Cover continuous non-power-of-two scales, NEGATIVE scales, zeros, subnormals, near-overflow magnitudes — stock generators emit only positive scales, which once hid a signed-zero divergence. Where the domain is small, enumerate exhaustively (all 16 nybbles x all 65536 bf16 scale patterns = 1,044,480 cases runs fine). Any difference outside a class you can PROVE unobservable (signed zero cannot survive a DPAS accumulator starting at +0) means ship nothing.
>
> **STAGE 4 — build.** oneAPI DPC++ 2025.3, pinned explicitly — /opt/intel/oneapi/compiler/latest symlinks to 2026.0 and a bare setvars.sh picks the wrong generation. Target libgrouped_gemm_xe_2.so in build/temp. 13-45 min. Commit on the branch. Report the .so path and SHA-256. Do NOT install into vllm_xpu_kernels/.
>
> Report: stage 0 verdict with citations, stage 1 counts, the diff, stage 3 bitwise results and scale modes covered, build command and duration, commit hash, .so SHA-256. Flag defects in your own work rather than burying them — a previous agent caught its own memoisation keying on recycled allocator addresses and saying so was worth more than the code. "The premise does not hold" and "this cannot be done bitwise-exactly" are both successful outcomes. A fast-but-different kernel is worth nothing.

**3. If the optimizer stopped at stage 0 or 1**, record it and go to the next target. That is a cheap win, not a failure.

**4. Spawn an ADVERSARY subagent** on the commit, before spending any GPU:

> Attack a kernel change another agent just made. Your job is to find the reason it should NOT be promoted to expensive endpoint measurement. Read-only on kernel source; you may compile probes and run single-card GPU checks. Do NOT run vLLM, a server, or any benchmark leg.
> Repo: /home/steve/src/laguna-xpu-kernels-tile12-20260728 at {{COMMIT}}. Selector: {{FLAG}}. The optimizer's claims: {{CLAIMS}}
> Try to establish any of these; any one blocks promotion:
> 1. THE BITWISE CLAIM IS FALSE — re-run identity with inputs the optimizer did not use: negative scales, exact zeros, subnormals, gate-boundary values, NaN/Inf if reachable, the largest and smallest magnitudes real weights produce. Vary group_size and policy. If you find a difference, characterise whether it can reach an emitted token.
> 2. THE ISA CLAIM IS FALSE OR IRRELEVANT — re-dump and re-count independently. Confirm the counts are for the policy 12-row decode actually selects (w4a16_policy_m_8 via the generic path), not one that never runs. Check whether the saving lands on the constrained pipe or a slack one.
> 3. IT REGRESSES SOMETHING ELSE — new spills, register pressure on the selector-off path which is the control, instantiation growth toward the 125 GB build ceiling, longer dependency chains.
> 4. THE GATE IS UNSOUND — stale memoisation, recycled allocator addresses, empty-string env values, whitespace. One such hole already existed here.
> 5. TOO SMALL TO MEASURE — if the honest projected effect is under ~1.5%, the noise floor cannot resolve it.
> Verdict: PROMOTE, BLOCK, or PROMOTE-WITH-CAVEAT, with evidence. Finding nothing is legitimate — say "I could not break it, here is what I tried" rather than inventing a concern. Do not suggest improvements.

**5. On BLOCK**, send the adversary's evidence back to the optimizer or drop the target. On PROMOTE, spend GPU:

- Install the .so into `vllm_xpu_kernels/`, mint a runtime lock JSON with the new hash (copy, never edit, the sealed packet's lock), export `REPRO_GROUPED_GEMM_SHA256`, `REPRO_RUNTIME_LOCK`, `REPRO_RUNTIME_LOCK_SHA256`, and add the selector as a leg argument.
- **Interleave** candidate and control legs on the SAME binary so drift hits both arms equally. Never compare across binaries — codegen differences confound it.
- **n >= 5 per arm. Report the MEDIAN, and also the mean and how many legs cleared 102.** Single-leg reporting is why a sealed record looked 0.058 tok/s from target when its median was ~1.5% away.
- Every leg must be 13/13 exact with `cached_tokens=0`. **A large speedup that appears suddenly is overwhelmingly likely to have broken the verifier, not found free time** — that pattern produced 198.7, 537.4, 550.9 and 109.2 tok/s, all worthless.

**6. Commit the result, positive or negative, with the numbers in the message.** Then loop.

## Termination

- A candidate dies when stage 3 shows no median gain over its matched control at n >= 5. Not when an agent calls it good — the `mad` fusion was bitwise-perfect across 1,044,480 cases, cut saturated float-pipe work 45%, and was ~1% slower because the int pipe binds. Only a leg found that.
- The whole loop ends when three consecutive candidates die at stage 0 or 1. That means the remaining waste is below the measurement floor and the next move is a different class of change, not another iteration.

## Targets, ranked

1. **The 53 non-arithmetic instructions in the k-loop body.** The scale-reload branch and its prefetch-address recomputation run every k-tile although the scale only changes on group boundaries, and `group_size % tile_k == 0` is already asserted. Hoisting is bitwise-neutral by construction. ~10 instructions/k-tile.
2. **Reduce the dispatch matrix to 4 variants**, making DEQUANT_MAD=1 require SCALE_VEC=1. 117 GB peak build RSS on a 125 GB machine is not a build path anyone can inherit.
3. **Fix the range-gate memoisation** to hold an `at::Storage` rather than keying on a recycled address.
4. **Co-tune `VLLM_XPU_LAGUNA_PREFETCH_DIST` with SCALE_VEC=1.** Swept before the scale block changed; freed register pressure may move the optimum. No new code.

## Closed — do not re-open without new evidence

Scale folding into the accumulator (+8%, 0/13 exact). `add`+`mul` -> `mad` fusion (float pipe -45%, ~1% slower). Prefetch distance 3 and 12 vs 6. Generic N-tile 32 and 128 vs 64. Laguna M8 W1 N-tile at width 12 (compiled to require exactly 8 rows). Draft graph capture (0/13, captured with attn_metadata None). FP8/INT8 KV (all KV traffic is 0.3% of the cycle). Inline attention (-11%). Local argmax (-2.6%). Replicated embedding (-0.21%).

## Standing rules

Never report a rate from a run that failed exactness. Never select the best of N legs as the result. State the mean alongside any median. Record negative results with the same care as positive ones — six of this project's most useful notes are failures. If you catch yourself reasoning forward from a plausible mechanism instead of measuring it, stop and measure: that pattern produced five retracted claims in one session, while every result that survived came from an agent required to disprove itself first.

# Packet 71 — dependent two-row target engine

2026-10-17. CPU preparation only. Packet64 is copied, never edited. Packet49
`iq3-p49-split32-v1` remains the target oracle; KV and recurrent state stay BF16.
This supersedes packet68's serial hybrid choice for this new packet only.

## Transaction and arithmetic

A half accepts two consecutive input tokens and positions. It walks the layer
plan once, issuing one M=2 operation for each enabled class, otherwise two
production M=1 operations. Each row has private intermediates, routing, scratch,
position and stream output. Weights are shared. The per-class table starts with
routed gate/up and down, followed by production dense projections and attention
output. Unknown/unqualified classes remain explicitly serial M=1.

The rows are dependent: at every conv/GDN site row 1 reads the state produced
by row 0; at every QSA site row 1 sees row 0's appended KV and pool entry, with
its own position and causal extent. Never run both rows from the same initial
state. Reduction order, FP32 chains, BF16 stores, split partials and rounding
are those of production M=1. No tensor-core or reassociation substitution.

Retain three logical prefixes: before the pair, after row 0, after row 1.
Separate row storage makes a prefix selectable without recomputing accepted
arithmetic. Copy temporal state forward at its writer boundary; preserve the
original state until resolution. Use packet62's checked flat batched copies
for state movement. Preserve overwritten KV/pool bytes, token/PLE history,
launch extents and scratch/cache metadata; sticky errors cannot be restored
away. A discarded suffix cannot enter the committed target or draft state.

## Verification and the two-card pipeline

Given target state through t and its verified next token, the draft runs its
ordinary pass and then a recursive MTP pass (packet66 mechanism) to propose
two future inputs d1,d2. The recursive pass reads the draft's own last hidden
streams. It runs on an isolated draft transaction and restores its input image
before the confirmed path advances. No draft token is emitted without target
verification.

Rank0 runs the proposed pair as one dependent half while rank1 completes the
preceding target half. The handoff carries two distinct streams and token/position
identities, with release/acquire publication. Rank1 runs the dependent pair;
its first-row logit verifies the second input. The previous target logit verifies
the first input. Keep the rank0 prefixes until both comparisons are resolved.
Do not confuse a row's input token with the next-token logit it produces.

| Outcome | Committed inputs and repair |
| --- | --- |
| Both accepted | Keep prefix 2 on both ranks; emit only verified tokens. The last target logit supplies the next confirmed frontier token. |
| d1 only | Keep prefix 1. Restore row 1's KV/pool, GDN/conv and draft changes; execute the corrected second input through unchanged M=1. |
| d1 rejected | Keep prefix 0; discard both rows and dependent proposals. Execute the target correction, redraft from its confirmed hidden state and resume. |

Never use row1's logit if row0's input failed verification. Output cap/EOS can
truncate a valid pair: commit precisely the consumed prefix and discard its
suffix. Prompt feeding stays the existing single-row path. Bound lookahead to
one pair; a drain/repair bubble is preferable to an unverified carry. The first
screenable implementation may drain at a transaction boundary. Its measured
cost, not the optimistic model, decides further overlap work.

## Cost model (projection, not measurement)

The copied `analyze_probe.py` uses record **52.90**, hit **16.45 ms**, miss
**28.37 ms**, a1=.787, conditional a2=.718, and corrected half **13.5636 ms**.
Packet68's measured restore is **0.980923 ms** (a different 23/25 screen).
Pair probabilities are .565066 both, .221934 second miss, .213 first miss.
The inherited pipelined projection rewards **two** completed tokens per
interval; never substitute the blocking verifier's 2.352066 reward into it.

Using H1=(14.23,14.69), H2=r*H1, zero cancellation overlap credit, and one
2.38 ms extra draft, the inherited optimistic model reaches the 57.132 tok/s
(+8%) bar at **r <= 1.56037**. It projects 65.73 / 60.48 / 56.02 tok/s at
r=1.30 / 1.45 / 1.60. These mix measurements from different runs and exclude
unmeasured causal state movement and pipeline bubbles.

Reserving another **2.38 ms per pair** for feedback/draft repair or synchronization
reduces the threshold to **r <= 1.42499** (approximately 1.42). Thus 1.45 is a
useful engineering target, not a guaranteed +8% result. Report both the inherited
optimistic bound and this reserve; actual per-half and end-to-end receipts win.
The fallback M1 implementation is a correctness/screening bridge, not a speed
candidate. Packet68b independent-row timings do not establish causal identity.

## Lean gates and handoff

1. CPU byte gates for every enabled M2 class against production M1, under GNU
   and Intel host compilers. Copy packet68c sources and bind their hashes.
2. Small dependent-state fixtures and all three forced acceptance cases; exact
   packet64 target token/state comparisons, at most 32 tokens per fixture.
3. Build and seal a serial fallback before integrating M2. No long CPU model
   run; native quality remains pending until coordinator receipts arrive.
4. Coordinator lane B: one prompt x32 smoke, then 12 prompts x128 matched
   packet64 control/candidate quick screen. Separate output paths, no retry,
   release leases after drain before reporting. Watchdogs at least 4x the
   estimated 3/4 minute windows. These are diagnostic, never promotion gates.

CPU work uses nice19, cores 8–15,24–31, Python -B, stdin /dev/null, one compile
at a time, 8 GiB address-space ceiling, build <1.2 GB and disk floor 12 GiB.
The coordinator owns all GPU execution. No frozen packet/screen/ops edits.

Ideas and evidence: packet68 DESIGN.md and measured device-cost.json;
packet68b analyzer; packet66 recursive draft/state probe; packet62 flat rollback;
packet64 production engine; packet68c production-derived paired kernels.
All are lab code. No outside runtime is used as a base.


## Implemented steady pipeline (integration milestone)

Use positions explicitly: canonical target state is through p-1 and x[p] is
verified. The current rank0 tile contains x[p] and a guess for x[p+1]. Rank1's
row0 output verifies that second input; row1's output predicts x[p+2]. Rank0
simultaneously processes the future proposals for x[p+2],x[p+3], starting from
the current tile's private prefix-2 state. It does not mutate canonical state.
At the next iteration compare the future tile's first input with the previous
rank1 row1 output before sending that tile to rank1.

Rank0 owns two private tile transactions; rank1 owns one. After both current
rows pass, commit their prefix 2 and rotate the pending future transaction.
If the first future input fails, discard its prefix 0 and rebuild it from the
verified first input before rank1 starts. If a current second input fails,
commit prefix 1 on both ranks, discard the entire future transaction, and
resume from the target correction. EOS/cap use the same prefix selection.

The draft first consumes the verified x[p] with target hidden[p-1]. If a
current second guess already exists, use that exact input for the recursive
branch. Two recursive passes then propose the future tile, using draft hidden
state and rolling back all mutable draft allocations afterward. This is a
feedback pass plus two recursive passes per tile, not two free predictions.
After both inputs are verified, advance the committed draft with the current
row0 target hidden and the accepted second input. A rejected suffix never
advances the committed draft.

The initial serial milestone drained tiles. Integration now overlaps a full
rank0 pair with a full rank1 pair. Its cost still differs from the inherited
ideal model: a second-input miss produces one token before repair, and state
movement/draft copies are explicit work. `cost_model.py` labels this gap.

Memory admission adds 1,090 MiB on rank0 (two bounded tile images plus reserve)
and 577 MiB on rank1 (one image, draft backup, copy table and reserve), only for
24/24, rank1 draft, 4096 context. The original 30 GiB per-card arena cap and
1.5 GB free-device reserve remain enforced. CPU fixtures use tiny synthetic
weights, never full model payloads.

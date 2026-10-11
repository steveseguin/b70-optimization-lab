# Packet 24: parallel schedules, arithmetic identity v2

CPU preparation only. No device executable, driver discovery, Level Zero call,
`/dev/dri` access, power change or model server was run. Device qualification and
all speed claims remain pending. The coordinator owns every command in
[WINDOW.md](WINDOW.md). This packet is isolated from the protected packets.

The source is packet23-fast as committed at the `source_commit` in
[source-proof.json](source-proof.json); each copied file has its original SHA256.
`--kernels v1` selects its original numerical kernels and fused schedule in the
same executable; `--kernels v2` selects the new work distribution. The default is
v1, to make accidental adoption impossible before the device gates. Fusion,
GEMV dispatch, and arithmetic identity are independent choices. K1 exercises the
actual new kernels, original kernels, and frozen v2 reference core. Model windows
compare every registered layer fixture and generated token with the v2 CPU oracle.

## What changes

Packet23's general fused chain runs its phases and all their groups inside one
work-group. V2 breaks those dependent phases into ordered submissions and gives
independent output pieces to separate work items. It never treats a work-group
barrier as a device-wide barrier. Each submission remains in the owner's event
chain, with lifetime tracking, checked argument captures, error propagation,
bounded waits and failure reporting. Scratch is owner-local and reused only after
its previous consumer in that chain. Every binding and scratch extent is checked.

The 16-bit stores between operations remain. In particular a combined residual is
rounded to BF16 before the following norm squares it; GDN state is rounded between
tokens; QSA value is rounded before its gate; rotary inputs are rounded before
rotation. The runtime's attention projection already folds its residual combine
into GEMV's BF16 epilogue. Its following norm uses the new two-stage norm. FFN's
combine uses independent element writers and the next norm uses the same new norm;
layer snapshots and card boundaries are retained. The standalone combine+norm
kernel is also tested directly. V2 does not change any large GEMV kernel.

## Exact reduction decomposition

Let `T(n)` be the original adjacent tree. At stride `s=1,2,4,...<n`, node `i`
(where `i` is a multiple of `2s`) is `left[i] + right[i+s]`, or `left[i] + +0`
when the right node is absent. The left operand is always evaluated as the left
operand; no algebraic identity or associative reduction is substituted.

For cut width `B=2^k`, each work item computes the original nodes within one
aligned B-leaf subtree, through stride `min(B,n)/2` (including the final occupied
stride for odd lengths). It stores the subtree root as F32. The upper tree over
`ceil(n/B)` roots executes precisely the remaining nodes, in their original
left/right order. An incomplete last subtree performs the original `+0` at every
missing-right level. It does not fill fictitious leaves and reduce them, nor add
extra levels above a tree shorter than B. For n=1 there is no addition; n=3 has
`(x0+x1)+(x2+0)`; n=17 has the original singleton-tail `+0` at every level; n=255
has one missing final leaf; n=2560 has80 complete32-leaf subtrees, followed by the
80-root tree including its original odd upper levels. The independent symbolic
review checks26 exact ordered trees over13 lengths with cuts16 and32.

| Class | Work distribution and identity argument |
|---|---|
| route + gather |16-leaf maximum chunks; ordered left-biased maximum scan preserves first equal including signed zero; exponentials are independent deterministic `exp`;16-leaf sum subtrees and the original upper tree; F32 divide before ranking; each element ranks against every normalized score with descending score/index-ascending tie order. Unique rank owns its selected ID/probability/triples. Nonfinite inputs fail before outputs. Selected probabilities are normalized by the unchanged GEMV-side tree. Fused consumers index one2560-wide row: no top-k copies. Unfused compatibility mode still materializes its original gather ABI. |
| HC/final norms, combine norm |32-leaf squared-value subtrees; upper root is recomputed privately per four output elements, preserving all upper nodes. Only the owning item writes each output. Combine is BF16 before square/normalization. Two launches, no barriers. |
| GDN recurrence |Precompute q/k norms and gates once per head/tile. **Not** an adjacent128-leaf dot: each lane starts at +0 and serially adds its four original products, followed by the original adjacent32-lane tree. One item owns one128-value state row, computes prediction/update/output with that same dot, and retains sequential token order and BF16 state stores. No two items write a state row. |
| QSA prepare |32-leaf norm subtrees, then independent groups of four output coordinates. A rotary coordinate recomputes its partner's normalized BF16 value; the original multiply/subtract or multiply/add order remains. Gate outputs have unique coordinate owners. |
| QSA append/pool |Appends write positions>=old position; pooled sums read cached positions<old position and current inputs elsewhere, so they do not depend on another group's append. The four-value fold is serial from +0, divided by4 then BF16-rounded before norm. Norm and rotary use the prepare decomposition. |
| QSA select |One item per block computes each128-leaf score tree privately and adds the four head scores serially. A separate stage ranks each block and writes its four unique selected IDs; tail IDs occupy disjoint slots. Sentinel initialization finishes before ranking. NaN behavior follows original `max(0, score)` and finite checks. |
| QSA attention scores |One item per head/selected position computes the original256-leaf tree privately; division by sqrt256 is unchanged. IDs are validated before indexing. |
| QSA attention softmax |Chunked left-biased maxima, deterministic exp with32-leaf sum subtrees, then original upper tree and F32 division. No cross-group in-place reduction. |
| QSA attention values |32 selected-position leaves per independent output/subtree; upper tree in a second stage. BF16(value), sigmoid gate, final BF16 remain separate rounding points. |
| argmax |Independent256-value scans produce best-index and finite flags. A second stage picks earliest maximum. Invalid-input diagnostic path reproduces v1's128-lane winner, then sets error, so even failure outputs match. |
| HC combine, broadcast, standalone gather |Unique output-element owners. Gather delays sticky error until all defined diagnostic outputs are initialized. No reduction arithmetic changes. |
| conv, activation, mixture and tiny control sites |Existing independent group kernels retained where already parallel; v2 no longer serializes all those groups inside the general chain. |

[Independent arithmetic review](tree-review.json) and [race review](race-review.json)
record the fixes and their scope. Private upper trees duplicate arithmetic work
but do not change its nodes. Actual occupancy, register spills, and whether an
extra launch wins are questions for K2, not conclusions from this proof.

## Timing targets, not measured improvements

The supplied old numbers below are **unfused R5 first-start/last-end spans**, not
measurements of packet23/v1 in this binary. K2 measures v1 and v2 event execution
with identical fixtures. One issue costs roughly4us; targets below are per native
launch, and multi-stage group totals are separately stated. None is a pass or a
speed claim. The desired ceiling is15us/launch; any miss goes into the next lever.

| Class | Supplied old span us | V2 target us/launch | Launches/group and rationale |
|---|---:|---:|---|
| route + fused gather |204 +80 |4–12 |4; small max/exp/sum stages, many independent ranks, no input copies |
| attn.combine / ffn.combine |156 /154 |4–8 |1 elementwise; attn combine already belongs to GEMV epilogue in fused mode |
| HC norm / final norm |21–22 |4–12 |2;32-leaf subtrees then private upper trees; group target8–24 |
| standalone gather |80 |4–8 |2 compatibility stages including delayed error; absent from fused input-copy path |
| QSA attention score |part of88 |4–15 |1; independent256-leaf dots |
| QSA attention softmax |part of88 |4–10 |3; max, exp/subtree, normalize |
| QSA attention value |part of88 |4–15 |2; independent output/subtrees, upper tree; whole attention group24–80 target |
| GDN recurrence |52 |5–15 |2; head normalization then disjoint rows; state read/write alone about5us at roofline |
| QSA select |68 |4–12 |2; independent block scores then stable ranks |
| QSA prepare / pool |not isolated here |4–12 |2 each; parallel subtrees and coordinate stores |
| argmax |810 |5–15 |2; independent256-value scans then small final selection |
| conv / gates / mixture / PLE elementwise |varied, see raw trace |4–15 |existing parallel groups, dependencies split out of giant chain |
| begin / commit / status / PLE hash |small controls |4–8 |existing bounded scalar/control work |

The class named `attention` in the supplied trace is the **output GEMV projection**,
not QSA softmax. Its68us span is not a non-GEMV kernel; its batched GEMV arithmetic
and residual epilogue remain unchanged. `gdn.conv`, `qsa.prepare`, `moe`, `ple.kn`
and `streams` in K2 identify fused *launch groups*: their constituent operations
remain visible through individual captured events and the source schedule.

## Small GEMV audit

The numerical batch implementation is byte-identical to packet23. Every descriptor
owns a disjoint interval of work-groups and every logical output row owns its own
group; the descriptor lookup does not execute sibling matrices serially. HC low
and inject are one batch. HC gate depends on low/activation, so cannot share that
producer's launch; its rows are parallel. GDN a/b share the qkv/z batch. Router,
shared gate, and paired shared-expert gate/up share one batch; shared down waits
for its activation. No serial sibling decomposition was found to repair. Their
old11–30us spans are not converted into new claims. Repeated BF16 prologue work
and subgroup utilization are recorded in [GEMV-NEXT.md](GEMV-NEXT.md); large GEMV
redesign is deliberately a subsequent packet as requested.

## Gates and reproduction

[build-receipt.json](build-receipt.json) binds source closure, inputs, precise
compile **and link** flags, binaries and CPU gate counts. `build.py` builds native
programs without executing them. K0 compiles the identical kernel object/image
set linked into every native entry. Every functor has a <=1024-byte assertion,
with a1025-byte negative compile control. Host programs use renamed entry shims
just like native programs; successful return codes are checked. K0 itself is
exercised through a pure C++ API mock, with no device libraries or discovery.

CPU gates include unit/failure/owner controls; both card counts; fusion on/off,
core/parallel and three timing modes crossed with v1/v2; two fresh fixture
processes under GNU and Intel host compilers; direct Core/v1/v2 supported-kernel
fixtures and odd lengths; route ties/NaNs; ASan/UBSan mini cases with four shuffled
work-item orders; and one-card streaming eight-token/384-layer v2 oracle matching.
Long two-card CPU receipts are carried only as v1 evidence under the source proof,
never as v2 qualification. GPU arithmetic, determinism and speed remain untested
by this packet. [Closeout](CLOSEOUT.md) lists what the coordinator must still run.

## Sealed CPU result

All 312 integration cases passed. Sixteen fresh fixture processes under GNU and
Intel passed; each non-GEMV process includes 92 direct kernel cases with 276
Core/v1/v2 pairwise comparisons and 15 route edge cases checked under both versions.
The 32 sanitizer mini-runs cover both card counts and four shuffled orders.
All 66 window-protocol checks, 26 symbolic tree cases, and three K0 mock exits pass.
The one-card streaming v2 run matches all eight generated tokens and all 384 layer
fixtures. Precision flags are asserted at compile and link; all five native entries
share 21 kernel objects. The largest of 46 compiled captures is 224 bytes, and the
1025-byte negative control is rejected. Native execution remains unqualified.

Native binary SHA256 (local ignored `build/device/`; all source and host hashes
are in the build receipt):

```text
own-rt-iq3 704c8e785e6018e0fb5fb369700ea17e303eb7047b9abadefd73e96c825edf2b
jit-smoke 5f6ce2586609200f744b27b3e2f4f57e941614fe9c7b42eb8456cc0c4197cdd3
k2-fixtures 96f5980eb05e06f8b8e5013e9e3fe483aca6e96e119add1abdb6ff547193800c
fused-fixtures 3d6f7f8fbe39e83029a1246079c7aaef79f06d69008445807956d7b6a297ed0c
nongemv-fixtures a6d28acd2aafeef9f614b544a2ccff02d7b5dc5e08cfcf60b59006ec1b41f6fe
```

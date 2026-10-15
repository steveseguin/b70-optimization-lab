# Packet45 within-layer split, step 1: exchange schedule and rejection

2026-10-15. **REJECT this full-row layout on the retained transport costs.**
Do not build the complete split or start its step-2 device A/B. Its legal
communication schedule is much smaller than packet14's, but the measured
ordered-copy path still does not meet the requested **23.5–24 ms complete
step** budget. This closes this layout/cost combination, not within-layer
parallelism in general.

There are **three unavoidable data-exchange phases per layer** for the
placement below, plus **one route-agreement phase** when retaining the earlier
TP design's check-before-expert-read contract. That is **four phases / eight
directed messages per normal GDN, upgraded GDN, or QSA block**. The final head
needs one data phase; final result/error agreement adds one control phase.
The complete schedule is **194 phases / 388 directed messages**, before any
request admission or extra transport-level acknowledgements.

At the measured small-peer-copy medians, four phases over 48 layers cost
**7.0875 ms** before packing, comparisons, the head exchange, or owner overhead.
Even granting an impossible perfect halving of the unchanged 37.1 ms target
work leaves only **4.95–5.45 ms** for exchanges and all other overhead. That
screen projects **25.6375 ms**, already over budget. A more generous, explicitly
unmeasured duplex sensitivity is discussed below; it does not supply a passing
forecast either once the replicated kernels are accounted for.

These are planning calculations from retained measurements, **not a measured
TP speed or a physical latency lower-bound theorem**. In particular, a sum of
waited copy medians is not proof that a new event-only transport cannot be
faster. No such transport is qualified or timed here.

## Scope and evidence identity

Only this note and [its CPU metadata helper](p45_within_layer_split_step1.py)
were written. Both packet trees remained read-only. Commands used `nice -n 19`
on cores `4-15,20-31`; Python used `python3 -B`. No model payload, build, device
binary, `/dev/dri`, sudo, or host setting was used. This is step 1 of
[the recommended project](2026-10-15-p45-roofline-and-structural-levers.md#the-single-next-project-and-its-stopping-test),
within the owner's 90-minute limit.

Inspection base: `593922498ed78c32712bce9f4deaf4a14b3cbc3b`, on `main`,
`steve-b70s`. `P` below is
`experiments/own-xpu-runtime/stage2/packet45-merged3`.
The actual executed plan is SPEED7 cards01's
`P/build/speed7-c4096-dr1-s23-cards01-gpu/WS/run/ranks/rank{0,1}/launch-plan.json`.
The helper verifies equality with both SPEED6 headline launch plans. It reads
metadata only, checks the dependency chain on **all 48 layers**, and hashes its
inputs. This is stronger evidence than reconstructing the DAG from the older
unfused Builder alone.

| Retained input | SHA-256 |
| --- | --- |
| Rank 0 launch plan, S6 headline and S7 | `7a29e4b02662799f2bdb711df64b0d5f9cc40a0aa28d9740e82b2274d10461e9` |
| Rank 1 launch plan, S6 headline and S7 | `6426b6c84fbf668fa5c287e767a09b605eb71c70ead56756a15e20e8d534b57f` |
| `P/build/input/plan.tsv` | `9926b7a266ba2774f02fe00583257ab2aaff96ee0313d350d3ba54602ae2a656` |
| S7 `K2/run0/dispatch-measured.json` | `477f62ec5cea61624047267ff69d74580c153ef40afe8558822dedb544018612` |
| S7 `K2/run0/summary.json` | `550f2b0a4f3a7d64c87ca1d7616833e028ec2e63f04bca8fc8a44e90df9f0da8` |
| [Packet12 transport `native.json`][peer-raw] | `6eb91df0fae285711d54b3233dd3545c6a89c12894466c295e6177db005ee738` |

The source authority is [Builder][builder] for dimensions and unfused dataflow,
[current `main.cpp`][main] for grouping/binding, [P39 plan rewriting][p39-plan]
and [P39 bodies][p39] for the surviving epilogues, [arithmetic identity][arith]
plus the [original shape dispatch][shape-dispatch] for each row's reduction,
and the current non-GEMV bodies linked below. Retained `build/` receipts are
local evidence, not a claim that an untracked build tree is a public recipe.
The helper requires those receipts; it does not reconstruct missing data.

The census is **34 ordinary GDN + one PLE GDN (layer 1) + one upgraded GDN
(layer 2) + 12 QSA = 48 layers**. The model is the separate quantized compressed
Unsloth UD-IQ3_XXS release, with unchanged `iq3-p17-detmath-v2` arithmetic.
No FP8-model equivalence, new quantization, or compressed KV is implied.

## Placement: what the minimum is conditional on

“Minimum exchanges” needs a placement and replication policy. Replicating the
entire model would give zero exchanges and no useful two-card speedup. The
following is the communication-minimizing **head/whole-expert split** being
screened, not a minimum over every possible repartition or new algorithm.

- Both cards start a block with identical BF16 `streams[4,2560]`, token,
  position, active flag and clean/agreed sticky error. Replicate both HC paths,
  the router and selected `small.ffn` tuple, the complete shared expert, and
  the final HC. Do not count any of that work as halved.
- Divide GDN/QSA attention work by **complete heads**, then the attention
  output projection by **complete output rows**, 1,280 per card. Each output
  row still consumes all 6,144 input values. Keep the current fused
  attention-projection/HC-combine epilogue.
- A owns expert IDs 0–255 and B owns 256–511, including each expert's complete
  gate/up/down triplet. Each selected expert computes all 640 gate/up rows
  and all 2,560 down rows. Preserve the original ten route slots and their
  order. Storage balance is not execution balance.
- Replicate QSA indexer projections, index state and selection. Shard KV by
  whole KV heads. This buys the same exchange count as GDN; it costs real
  replicated work and memory. Never split a selected-history reduction.
- Divide the final vocabulary projection into rows 0–124159 on A and
  124160–248319 on B, each with the full K=2560 reduction. Replicate the final
  HC and, after the logit gather, the unchanged argmax.

The schedule is a dependency design, **not an existing launch option**.
Current dispatch rejects unregistered shapes; current kernels contain fixed
head counts, global strides and row-derived addresses. A future row-range
adapter would have to retain original global indices, original matrix strides,
and the **original full-shape arithmetic variant**. Re-dispatching a matrix
with half its rows is not justified. In particular, changing P39's `rows` to
1280 also changes its stream stride; that would write the wrong streams.
An adapter must translate storage addresses without changing row arithmetic.
No such adapter was written here.

All messages below are copies of finished representations, not arithmetic
reductions. Within a phase, both directed payloads are ready independently
and may be grouped. Across phases, the dependencies below prohibit grouping.
One compute queue per card is assumed; no same-card compute overlap is credited.

## Normal GDN: exact schedule

Dimensions are W[out,in]. The replicated entry HC is:

`streams -> norm[4,2560] -> low[320] -> act[320] -> gate[4,2560] -> mix[2560]`.

`inject[4]` independently depends on that HC's normalized streams. The current
low+activation is P39-fused; injection is a separate full-row projection.

The production GDN uses **packed key mapping `key = h % 16`**, not the tiny
fixture's `h / 3` mapping ([round2 GDN][round2], [binding][main]). Therefore:

| Card | Key/Q heads | Value/state heads, in original global order |
| --- | --- | --- |
| A | 0–7 | 0–7, 16–23, 32–39 |
| B | 8–15 | 8–15, 24–31, 40–47 |

Each card owns 5,120 QKV output rows: 1,024 Q, 1,024 K, and 3,072 V.
It also owns 3,072 Z rows and 24 rows of each alpha/beta projection.
All those GEMV rows retain K=2560. The independent QKV, Z and alpha/beta
projections require **no exchange among themselves** with this head mapping.
Use the current paired alpha/beta grouping without changing its arithmetic.

The local chain is QKV BF16 -> four-tap channelwise convolution -> GDN
recurrence -> per-value-head norm/sigmoid-Z gate. Convolution history and each
128×128 value-head state stay on their owning card. No Q/K reduction crosses
cards. Each card produces 3,072 finished BF16 `gdn.gated` values.

1. **E1: gather `gdn.gated`**, 6,144 B each direction, 12,288 B aggregate.
   Restore global head order. Every owned attention output row now has its
   entire input. Do not send QKV, Z, alpha, beta or recurrent state separately.
2. Execute the unchanged full-K output rows, `ssm_out[2560,6144]` Q6_K, and
   P39's BF16 branch store followed by its HC residual update. Each card
   updates its 1,280 columns in **all four** streams.
3. **E2: gather those updated stream columns**, four spans of 2,560 B per
   sender = 10,240 B each direction, 20,480 B aggregate. Both cards now have
   the full post-attention `streams[4,2560]` for HC-FFN normalization.
4. Run replicated HC-FFN, the selected router/shared tuple, and route+gather.
   The tuple computes router, shared gate/up and shared scalar gate from the
   same HC mix; its members are independent. Shared activation/down may run
   while an independent transfer is in flight, subject to owner dependencies.
5. **E3: exchange and compare route records before expert reads.** Compare
   all ten U32 IDs, ten FP32 probabilities and both ten-entry U32×3 Route
   arrays: **320 B per direction**. Compare the controls too. Local-bank
   addressing must not overwrite these canonical descriptors or renumber the
   visible expert IDs. A mismatch poisons the transaction; it is not averaged.
6. Execute each locally owned selected expert's paired gate/up -> BF16
   activation -> down, preserving the P39 status/check outputs.
7. **E4: gather the ten slot-indexed BF16 down vectors**, plus their status
   records. The useful expert data is 10×2560×2 = **51,200 B total**, regardless
   of the split. Both cards then run the original serial slot-0-through-slot-9
   mixture, shared blend and HC-FFN residual. The resulting full streams are
   replicated, so there is **no fifth data exchange at layer end**.

E2's 20,480 B deliberately follows the **actual selected fusion**. An unfused
alternative could gather only the 5,120 B attention branch and repeat the HC
combine locally. That has the same dependency-phase count, changes the executed
kernel composition, and requires its own timing. It does not remove E2.

### Upgraded GDN, layer 2

The schedule, shapes, state sizes and exchange bytes are identical. “Upgraded”
is a weight-format exception, not another head geometry:

| Component | Ordinary GDN | Layer 2 |
| --- | --- | --- |
| QKV and Z | Q6_K | Q8_0 |
| Paired expert gate/up | IQ2_S | IQ3_S |
| Shared gate/up | Q6_K | Q8_0 |
| Expert down | IQ4_NL | IQ4_NL |
| GDN output projection | Q6_K | Q6_K |

Layer 2's expert gate/up retains **two separate status checks**. Ordinary IQ2
uses P39's fused checks. Down/status remains P39-fused in both. The Q8 shared
GEMVs use the original one-part tree; ordinary Q6 uses four parts. Both QKV/Z
families keep their original one-part tree. None of these differences creates
an independent value that can cross E1/E2/E3/E4 earlier. The helper explicitly
checks the layer-2 exception against the executed plan and tensor metadata.

### PLE exception, layer 1

This is the other GDN exception and cannot disappear from a full-step forecast.
Replicate its complete PLE front end on both cards: token-history hash and
lookup, `[10240,2560]` key / `[2560,2560]` value projections, per-stream norms,
PLE gate, dilation-3 convolution/history9, and stream addition **before HC-A**.
Both cards use the same exact lookup row bytes and I64 token history. This
adds **no inter-card phase** in this layout, but does not halve PLE work.
Its state/casts are listed below. Initial embedding/lookup input distribution
and request admission remain full-step costs, not free transport measurements.

## QSA: exact schedule

Each card owns twelve contiguous Q heads and their gate halves: A heads 0–11,
B heads 12–23. It owns the corresponding KV head (A=0, B=1). Each head has
width 256. Thus the Q/gate projection is 6,144 complete output rows per card,
and K and V are 256 rows each; all use full K=2560. Head-local norms and RoPE
stay local. Keep `kh = h / 12` using **global** h, not a renumbered local head.

Replicate all four width-128 index-query heads and the width-128 raw index key,
including their BF16 projection weights, norm, RoPE, raw history, pools and
selection. Each card independently performs the same chronological pool-4
operation and the same four-head score accumulation, stable ranking and ordered
selected-ID expansion. The entire 2,051-entry ID vector, including -1 tails,
must agree in the exactness proof. Sharding index heads instead would add an
ordered reduction/gather dependency; it is deliberately not this layout.

Append the new local BF16 KV head at the original position. With the complete
replicated selection, each local Q head reads only its own KV head. Execute the
selected P30 score/softmax and value stages, with the original selected-token
order and every BF16 boundary. Each side produces twelve×256 BF16 `qsa.y` values.

- **E1:** gather that `qsa.y`, 6,144 B each way, exactly as GDN's `gated`.
- Run full-row Q6_K `[2560,6144]` output projection with the current P39 stream
  update; **E2** gathers four half-stream spans, 10,240 B each way.
- HC-FFN, router/shared tuple, **E3** route agreement, whole owned experts,
  **E4** slot gathering, replicated ordered mixture/shared blend/residual are
  exactly the common GDN suffix above.

No KV cache, pooled history, score vector or softmax vector is transmitted per
step. That is legal because heads do not depend on another head's attention
output, and the entire index computation is replicated. It is not legal to
split one head's time-axis dot/softmax/PV tree between cards. Physical KV layout
may be sharded, but its full logical `[C,2,256]` BF16 bytes must reconstruct the
unchanged state, including untouched rows.

## Final head

Replicate `final.norm -> final.low/act -> final.gate -> final.mix`, with the
same HC rounding as a layer. Run 124,160 complete Q6_K vocabulary rows/card,
K=2560, using the original **one-part head tree** and expanded row stride
3,380 B. Do not reselect a tree from the new half-row shape.

**H1:** allgather the BF16 logit halves: **248,320 B each direction,
496,640 B aggregate**. Both cards can now execute the unchanged global argmax
on identical full vectors. This is **one data phase / two independent copies**.
It preserves lowest-global-ID ties, signed-zero ties, the finite check and the
current nonfinite fallback behavior in [the adapter][adapter]. Final HC needs
no earlier exchange because the last layer left full streams on both cards.

**H2:** after both argmax operations finish, exchange the next-token I32 and
completion/error/position header, **36 B each way**. Compare before allowing
position/transaction commit or externally emitting the token. This is one
additional control phase. A single authoritative commit coordinator can lower
this to an acknowledgement protocol, but it still needs both completion facts;
it is not included in a free local-argmax claim.

For finite logits alone, local `(value, global ID, finite)` summaries could
replace the large logit gather and give the same winning token. That is a
separate reduction wrapper, loses the full logit materialization, and needs a
specific proof for the current nonfinite fallback/observed state. We do not
silently use it to price an unchanged head. The rejection calculation below
actually grants **zero cost to H1/H2**, so head compression cannot rescue it.

## Exact bytes, grouping, and the minimum-phase proof

An exchange **phase** is a pair of messages whose producers are ready without
consuming the opposite message. It is not automatically one DMA, one ordered
round trip, or one host handoff. To obtain two copies per phase rather than one
copy per span, this design needs owned contiguous staging and exact pack/scatter
operations. Those operations and their completion events cost time too.

Define a 32-byte proposed control header: U64 request epoch followed by six
U32 fields, token, position, layer, phase, active and sticky error. It is a
proposed envelope, **not the existing packet45 ABI**. Counts below exclude
additional wire framing, runtime-private acknowledgements and alignment padding.

| Phase, all three block types | Useful data, both directions combined | A→B bytes in the fixed envelope | B→A bytes | Prerequisite for the next phase |
| --- | ---: | ---: | ---: | --- |
| E1: finished GDN gated / QSA y | 12,288 | 6,176 | 6,176 | Every full-K output row needs both halves |
| E2: fused updated streams | 20,480 | 10,272 | 10,272 | HC-FFN norms need every column of each stream |
| E3: route IDs/probabilities/descriptors | 640, duplicated comparison data | 352 | 352 | Agreement precedes any selected-expert read |
| E4: ten expert down rows | 51,200 useful | 51,352 | 51,352 | Ordered mixture needs every original slot |
| **Per layer** | **83,968 activation bytes, plus metadata/status** | **68,152** | **68,152** | Full replicated layer output |

**Important fixed-size-copy distinction:** E4 cannot be priced as two fixed
25,600 B transfers. All ten routes may select one card. Current prepared
memcpy sizes are host-known; routing is device-resident. With no host route
readback and no new device-driven peer-copy primitive, allocate/send ten slots
in **each direction**: 51,200 B down data + 120 B for three ten-entry U32 status
arrays + 32 B header = 51,352 B. Only slots owned by the sender are installed
at the receiver; other packet slots are initialized padding, never summed.
This gives **102,400 activation bytes on the wire**, although only 51,200 are
useful. A future descriptor-driven copy could reach the useful-byte count,
but it is not the measured memcpy mechanism.

| Selected experts on A/B | Useful A→B / B→A down bytes | Fixed A→B / B→A envelope bytes |
| --- | ---: | ---: |
| 5 / 5 | 25,600 / 25,600 | 51,352 / 51,352 |
| 9 / 1 | 46,080 / 5,120 | 51,352 / 51,352 |
| 10 / 0 | 51,200 / 0 | 51,352 / 51,352 |
| 0 / 10 | 0 / 51,200 | 51,352 / 51,352 |

No division of work into five convenient experts is permitted. A zero-owner
card must skip expert loads safely, retain canonical slot identities/status,
and still participate in the control exchange. All-on-one-card routes remove
the expert compute speedup; they do not make that block cheap.

The actual DAG supplies this witness on every layer (the helper versions
in-place `streams` writes and ignores sticky-error edges when proving the
numeric dependencies):

```text
GDN gated / QSA attention
  -> output projection + stream residual               [E1 before this]
  -> HC-FFN norm -> low/act -> gate -> mix               [E2 before this]
  -> router -> route agreement -> local experts         [E3 before experts]
  -> expert down -> ordered mixture -> shared blend
  -> HC-FFN residual -> next layer's HC-A                [E4 before mixture]
```

Proof of the count, for the stated placement:

1. At E1 each output-projection row is a dot over *all* 6,144 inputs. A remote
   head value is not available locally without transmission or replicated
   head computation. Full-row arithmetic excludes partial-dot all-reduce.
2. E2's stream values are descendants of E1 and the projection. Each next
   per-stream norm reduces all 2,560 columns; HC low then reads all 10,240
   normalized stream values. A local half cannot compute the unchanged router.
3. E3's route bytes therefore do not exist before E2. Agreement-before-read
   prevents postponing E3 into E4. The check is a protocol requirement of the
   [earlier exact TP design][tp-design], not an intrinsic floating-point
   lower bound: with a separately established replicated-routing invariant,
   three data phases are the arithmetic minimum. We show that distinction
   explicitly rather than claiming four is a theorem for all runtimes.
4. E4 is produced by those routes, two nonlinear expert stages and the down
   projection. The mixture is a serial sum of ten rounded slot results; two
   locally accumulated sums change its order. The output must wait for the
   remote slots. Combining E4 with the next layer's E1 would create a cycle.
5. Opposite-direction pieces *within* each phase, the four stream spans, and
   completed expert slots are independent and may be packed together. A route
   packet and its downstream expert results are not independent. Nor are the
   two HC paths, or attention output and the following router.

Thus the **minimum data phases are GDN 3, upgraded GDN 3, QSA 3, head 1**.
Retaining live route agreement makes each block **4**; final completion makes
the head **2 including control**. This is **not** “one exchange per projection,”
and does not inherit packet14's 41 exchanges. Sharding HC low/up or shared FFN
instead of replicating them creates more dependent gathers; removing these
replicas is not a free way to improve the compute fraction.

At fixed envelopes: `48*136304 + 496704 + 72 = 7,039,368 B/step`,
194 phases and 388 directed copies. H1's 496,704 B includes its two headers.
This is delivered inter-card payload, not aggregate PCIe link traffic through
host bounce. A bounce has D2H and H2D legs per directed message. The pure
activation minimum excluding metadata, status and E4 padding is 4,527,104 B
including the complete logit allgather. Request uploads and extra owner events
are additional.

## Rounding boundaries and state that cannot change

`B(x)` below is the current BF16 round-to-nearest-even store. Copies preserve
raw bytes, including signed zeros and NaN payloads. No reduced precision,
reassociated sum, new fast-math, implicit FMA, changed denormal behavior or
replacement oracle is allowed. Explicit operations inside `detmath` stay as
implemented. All FP32 partials/status arrays that the selected implementation
materializes are also comparison boundaries, not just the BF16 layer output.

| Boundary | Required unchanged arithmetic / stored representation |
| --- | --- |
| Every GEMV row | Same packed/expanded weight bytes and scales, full K, lane assignment, product/add sequence and adjacent 32-lane reduction. Preserve existing split4 partitions and `(p0+p1)+(p2+p3)` FP32 finish where selected; one BF16 output store after the finish. Never round a cross-card partial. Expert gate/up/down and final head retain one-part trees. |
| HC norm | Ordered FP32 square tree, mean, epsilon, reciprocal sqrt, gain multiply, then BF16 normalized streams. Same stored gains/unit policy. |
| HC low/activation/up | Low GEMV BF16 **before** `detmath::silu_div4`; activation BF16; up projection BF16 **before** sigmoid. P39 fusion still writes low and act. |
| HC mix/injection/residual | FP32 sum in stream order 0,1,2,3; divide by four then BF16 mix. Injection GEMV writes four BF16 values. Residual is `B(old + branch*(2*sigmoid(inject/4)))`; branch already BF16. Preserve both attention and FFN stream updates. |
| GDN inputs/conv | QKV, Z, alpha and beta are BF16, even when projection weights are F32. Four chronological convolution taps accumulate FP32 without FMA; ordinary GDN applies SiLU then BF16, with **no** pre-SiLU BF16 accumulator cast. Shift/store BF16 history exactly. |
| GDN recurrence | `dot128` is 32 lanes, four consecutive products per lane with serial addition from +0, then the same adjacent tree. Q/K normalization remains FP32. Preserve alpha+bias softplus, stored `ssm_a=-exp(A_log)` use, decay, prediction, beta sigmoid correction and outer addition. Compute output dot from the **unrounded updated row**, then BF16 y and BF16 next state. Never store/round state before that dot. |
| GDN output norm/gate | RMS on the BF16 y head, gain in FP32 with no intermediate normalized BF16, sigmoid of BF16 Z, then BF16 gated output. E1 sends these bytes, not unrounded values. |
| QSA prepare | Q/gate, K, V, IQ and raw IK projection results are BF16. Normalize Q/K/IQ to BF16 **before** RoPE; use the unchanged BF16 table; round rotated outputs to BF16. Gate is copied from its original Q/gate half. |
| QSA pool/select | Sum four raw rows chronologically in FP32, divide by four, BF16; norm BF16 then RoPE BF16 at the block's original position. Preserve each index dot, ReLU, serial head-0…3 sum, sqrt scaling, lower-block-ID ties, selected-block order, four-row expansion, tail and -1 fill. Selection scores are FP32, selected IDs I32. |
| QSA attention | Identical selected-ID order, score tree/scaling, max and deterministic exp, softmax sum tree/division, PV tree. Preserve `B(B(PV)*sigmoid(gate))`. Scores/probabilities are FP32. P30's blocked tree includes original odd-tail +0 nodes and no extra tree levels. Do not sort IDs into chronological order for convenience. |
| Router | GEMV logits are BF16 despite F32 router weights. Softmax and both normalization sums are FP32; stable top ten uses lower original expert ID on ties. IDs U32, probabilities raw FP32, both descriptors U32×3. The P42/P39 route and gather outputs all remain visible. |
| Experts | BF16 gate and up separately, BF16 `SiLU(gate)*up`, BF16 down **before** probability multiply. Status remains per original slot. Layer 2 retains its separate checks. |
| Mixture/shared | `performance.cpp::mixture` sums slots 0…9 in FP32, then stores BF16 `ordered-mixture`. Current `prepare_site` feeds that into a one-slot blend with probability 1.f: preserve its +0, *1 and BF16 round, rounded `shared_down*sigmoid(shared_gate)`, then rounded addition. This is more specific than replacing the current path with a generic ten-slot expression. Shared down and scalar gate are themselves BF16. |
| PLE | I64 hash/history and exact lookup bytes; projections/norms BF16. Products round BF16 before the gate's tree; preserve the BF16 sum, division, root/sign/sigmoid intermediates in `ple_gate`. Dilation-3 convolution rounds its accumulator BF16 **before** SiLU, unlike GDN. `ple_add` preserves the inner and outer BF16 sums. |
| Head | BF16 final HC boundaries and BF16 full logits. Global argmax's finite check, lowest-ID/signed-zero ties, sticky error and failure fallback remain unchanged. Token/position are integer state, not float approximations. |

Sources: [core equations][core], [production kernel boundaries][kernels],
[round2 recurrence][round2], [P30 attention][attention], [P30 small tuples][small],
[P39 epilogues][p39], [ordered mixture][performance] and [adapter][adapter].
The selected P39 attention and expert bodies take precedence over a generic
GEMV dispatch name; the shared-up epilogue is **disabled in the production
plan** to preserve `small.ffn`, as documented in [the lever-2 audit][lever2].

| State/allocation family | Complete logical bytes to preserve and compare |
| --- | --- |
| GDN recurrent state | BF16 `[48,128,128]` = **1,572,864 B per bank per layer**, mapped as 786,432 B/card. Preserve every element of both active and spare banks wherever banks exist; no “only future reads matter” exclusion. |
| GDN convolution | BF16 `[10240,3]` = **61,440 B per bank**, 30,720 B/card. Preserve chronological slots and both bank parities. |
| QSA KV | Keys and values each BF16 `[C,2,256]` = **1024 C B** each, half per card. At C=4096: 4,194,304 B each logical array. Compare appended rows, all prior rows and untouched tails. |
| QSA index | Replicate raw `[C,128]` BF16 = **256 C B** and pooled `[ceil(C/4),128]` BF16 = **256 ceil(C/4) B**. At C=4096: 1,048,576 and 262,144 B per replica. Partial-pool history cannot be replaced by an accumulated running sum. |
| QSA selection/work | Full I32 IDs = **8,204 B** per layer; each FP32 score/probability array `[24,2051]` = **196,896 B**, mapped as 98,448 B/card. Preserve initialized sentinels, invalid tails, selector scratch and the admitted launch extent, not only the selected prefix. |
| PLE | BF16 history `[10240,9]` = **184,320 B per existing bank**, replicated. I64 token history **16 B**, host history0/history1, sixteen I64 lookup IDs **128 B** and exact lookup outputs. |
| Intermediates | All named plan buffers: normalized streams, low/act/gate/inject/mix, projections, conv/y/gated, QSA prepare outputs, expert gate/up/activation/down, route/probability/descriptors and all status arrays, shared values, attention branch, mixture and final logits. Compare every rounding boundary listed above using the full logical index order. |
| Standalone mutable state | `ordered-mixture` 5,120 B, `mixture-one` 4 B, operator scratch, GEMV split-part workspace, compact route storage, FP32 input-cache bytes/validity/source/extent, snapshots and both prepared-bank bindings/launch extents. Do not omit allocations because they are not launch-plan outputs. |
| Controls/ownership | Token, next token, position, active, sticky error; bank parity; request epoch; pending/cancelled/swapped state; request reset and completion ownership. New transport staging has separate initialized-padding/lease checks and cannot alias live state. |

The current [rank implementation][rank] banks recurrence/conv on **rank 0
only**; rank 1 executes its target in place. A split of every layer across both
cards must explicitly map the source layer's active/spare semantics to both
shards. Simply giving both new card processes today's rank-0 behavior, or
assuming rank 1 already supports rollback, is wrong. Target-only removes
speculative capture/redo, not the obligation to retain exact committed state,
sticky errors and safe failed-transaction/reset behavior. Physical bank and
prepared-argument parity need a new proof before implementation.

For comparisons, concatenate owned shards into canonical global order and
compare raw bytes against the unchanged same-input execution. Replicas each
compare independently; different physical allocation sizes are not compared
as though they were the same layout. Original untouched storage/tails and
spare-bank contents must still have explicit expected bytes. New staging
padding is tested separately, never used to mask missing original state.
The full inventories in [request-state inventory][inventory] and
[strict snapshot][snapshot] define the boundary; the layer output or winning
token alone is insufficient. No new byte-for-byte device pass is claimed here.

## Timing decision, including the optimistic counter-case

[Packet12's raw receipt][peer-raw] gives these medians, including its explicit
owner completion wait. Twenty samples/copy and all five exchange samples are
retained, including the first sample; no new timing was collected.

| Measured operation | Wall median |
| --- | ---: |
| Peer 10,240 B A→B / B→A | **18.319 / 18.595 µs** |
| Peer 65,536 B A→B / B→A | **18.8205 / 20.4385 µs** |
| Peer 1,048,576 B A→B / B→A | **54.362 / 53.0545 µs** |
| 60 ordered peer rounds, B→A + combine + A→B | **3.139943 ms**, **52.3324 µs/round** |
| 60 ordered host-bounce rounds | **9.995331 ms**, **166.5889 µs/round** |

The [current handoff analysis][after6] separately measures HALF-send to
rank-receive at **6.73 µs on hits / 9.80 µs on misses**. This is mailbox/start
latency, **not** the complete 20,480 B D2H/shared-slot/H2D transfer. Its much
larger `rank0_to_rank1_handover_ms` includes intervening computation and cannot
be multiplied by a layer count. Do not substitute 6.73 µs for a device exchange,
or add it mechanically to packet12's already waited timings. Packet12's
shared-context owner also does not qualify a new IPC path for packet45's
one-process-per-card ownership.

The original study's target-work baseline is **37.1 ms** (about 17.7+19.4 ms,
without draft and speculative capture). Keep its planning model:

`T = 37.1*(1 - f/2) + exposed exchange/packing/coordination cost`.

Even f=1 gives 18.55 ms, leaving only 4.95–5.45 ms. For 192 layer phases,
that is **25.781–28.385 µs per complete phase**, before either head phase.
Using the two measured 10 KiB directed medians as a small-message proxy gives
36.914 µs/phase, hence **7.087488 ms** and **25.637488 ms total**. Using the
actually measured dependent-round envelope gives **10.047818 ms** before
compute. A phase is not the same operation as that round; the latter is a
sensitivity, not an extra cost added to the copy-pair estimate.

The exact 352/6176/10272/51352 B envelopes have **not** been timed. These are
latency-proxy calculations, not interpolated benchmark points or claims of a
measured minimum. The larger E4 is deliberately given the cheaper 10 KiB cost
in the first screen. Packing/scattering, comparison kernels, copying the
head, initial inputs, completion and extra protocol traffic all receive zero
cost there. The old [packet14 result][tp14] independently found 41 exchanges
costing 1.53 ms/layer; we do not multiply that older count into this new DAG.

### Could independent opposite directions save it?

They are legally independent. We must not turn packet12's serial owner chain
into a proof that every future implementation needs two sequential waits.
For an exceptionally favorable sensitivity, give both directions perfect
overlap, charge only `max(18.319,18.595)` per data phase, and give the **entire
route-agreement phase zero exposed cost**. The three data phases alone then
cost `48*3*18.595 µs = 2.677680 ms`. This is **not a duplex measurement**.

That sensitivity must also pay for the replication which removed the other
exchanges. The following is a **partial K2 isolation proxy**, using the selected
production-shape implementations. It excludes HC norms/mixes, PLE, indexer,
shared activation, mixture, residuals and other replicated work; those are not
silently claimed to halve. No generic mixed-shape aggregate is assigned to
one production site.

| Replicated work retained by this layout | Count | Selected µs/site | Sum ms |
| --- | ---: | ---: | ---: |
| HC low + activation, P39 | 97 | 16.042 | 1.556074 |
| HC-A gate | 48 | 17.292 | .830016 |
| HC-F gate | 48 | 17.500 | .840000 |
| Final HC gate | 1 | 17.500 | .017500 |
| HC-A injection | 48 | 9.688 | .465024 |
| HC-F injection | 48 | 8.125 | .390000 |
| Route + gather, P42 | 48 | 41.042 | 1.970016 |
| Ordinary shared/router tuple, P30 | 47 | 17.500 | .822500 |
| Upgraded shared/router tuple, P30 | 1 | 16.042 | .016042 |
| Shared down | 48 | 9.791 | .469968 |
| **Partial replicated work R** | | | **7.377140** |

These values are from the hash-bound S7 K2 summary above. The tuple includes
the router GEMV; route+gather is the subsequent selection, so those rows do
not double-count the same kernel. The P39 low/act row replaces the generic
low/act dispatch. Norms and mixes are excluded rather than assigning an
unproved production wall cost to their generic fixture aggregates.

If this isolated proxy transfers into the 37.1 ms envelope, even halving
**everything else**, allowing the entire .465024 ms HC-A injection to hide
under E1, free E3, free head communications, free staging, perfectly balanced
experts and no small-shape scaling loss gives:

```text
(37.1 + 7.377140)/2 + 2.677680 - .465024 = 24.451226 ms
```

This is an optimistic **planning sensitivity**, not a subtraction of an exact
pipeline profile. The margin is insufficient, and the omitted positive costs
work against it. Counting just three data phases does not produce a credible
sub-23.5–24 ms forecast by pretending all 37.1 ms halves. All-on-one-card
expert routes make the compute fraction worse. A matched changed-transport
measurement could revise the cost assumptions; nothing here proves an
immutable physical ceiling.

## Closeout and revisit condition

Question: can the current full-row/head/whole-expert kernels be placed inside
each layer, with legally coalesced transfers, cheaply enough to justify the
complete target-only runtime? **Outcome: REJECT this layout with the measured
ordered transport; do not schedule its step-2 device A/B.** The proposed
sub-24 ms forecast fails even an intentionally favorable duplex/replication
sensitivity. No quality decision, runtime edit, rebuild, device reservation,
new server, publication or scoreboard change follows this CPU study.

Useful retained result: a three-data-cut proof, explicit fourth route check,
normal/upgraded/QSA/head schedules, global packed-head map, fixed-size versus
useful expert bytes, exact fusion/cast requirements and state-bank inventory.
Uncertainty: new event-only/duplex IPC cost, pack/scatter cost, actual selected
route imbalance, and shape-specific half-work scaling are unmeasured. Medians
from the old shared-context test are not transport guarantees for a new owner.

Revisit only with a concretely different mechanism: an ownership-safe transport
that materially beats the measured per-phase cost, or a placement/arithmetic
proof that removes replicated HC/router work **without adding equally costly
cuts**. For the three-phase optimistic screen above, with R=7.377140 and the
same generous injection overlap, communication would have to fit below
**1.726454–2.226454 ms** across 144 data phases, roughly **11.99–15.46 µs/phase**,
with still more room needed for the omitted costs and head. These are required
budgets, not projected measurements. A generic contiguous half-K all-reduce,
changed oracle, local expert sums, or compressed state does not meet that
condition.

No step-2 implementation is requested by this note. A later changed design
must first update its cost/dependency proof; this rejection is not evidence
that the optimization lane is finished.

Reproduce the checks and arithmetic (stdout only):

```bash
nice -n 19 taskset -c 4-15,20-31 \
  python3 -B notes/p45_within_layer_split_step1.py
```

The helper checks both retained launch plans against the S6 headline, 48
versioned data-dependency witnesses, the block-format/check exceptions, packed
head coverage, payload arithmetic and selected timing identities. It refuses
file writes, child execution and device-path opens. It prints all input hashes.
It neither imports runtime modules nor evaluates model arithmetic.

[builder]: ../experiments/own-xpu-runtime/stage2/packet3/step/plan.hpp
[main]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/main.cpp
[rank]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/rank.hpp
[arith]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/arithmetic.hpp
[shape-dispatch]: ../experiments/own-xpu-runtime/stage2/packet9-kopt4/dispatch.hpp
[p39-plan]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/p39_plan.hpp
[p39]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/p39_fused.hpp
[core]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/core_v2.hpp
[kernels]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/kernels.hpp
[round2]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/round2.hpp
[attention]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/p30_attention.hpp
[small]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/p30_small.hpp
[performance]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/performance.cpp
[adapter]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/adapter.cpp
[inventory]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/request_state_inventory.hpp
[snapshot]: ../experiments/own-xpu-runtime/stage2/packet45-merged3/strict_snapshot.hpp
[peer-raw]: ../experiments/own-xpu-runtime/stage2/packet12-peer/cards2-3-20261011/native.json
[tp-design]: ../experiments/own-xpu-runtime/stage2/TWO-CARD-TP.md#determinism-and-what-is-actually-exchanged
[tp14]: 2026-10-11-first-device-answer-and-arithmetic-v2.md#4-within-layer-two-card-split-is-exact-on-the-cards-and-its-exchanges-are-too-many-packet-14-cards23
[after6]: 2026-10-15-p45-after-speed6-levers.md
[lever2]: 2026-10-15-p45-lever2-design.md

# Exact launch chains

This is a source and recorded-plan audit, not a device result. `B(x)` means
round with `iq3::bf16_bits`, then widen the stored BF16 bits to FP32. All
arithmetic between explicit B operations is FP32, with contraction disabled.
`S(x)=1/(1+detmath::exp(-x))`; `L(x)=x*S(x)`. Keep NaN signs/payload policy
of packet29's BF16 conversion and deterministic math, not a native exp.
Dimensions: H=2560, low=320, mid=640, top=10, experts=512; GDN has
16 key heads and 48 value heads of 128; QSA has 24 query heads and 2 KV
heads of 256, and 4 index heads of 128. There are 36 GDN and 12 QSA layers.

Sources: [Builder](../packet3/step/plan.hpp), [packet29 plan transforms and
binding](../packet29-merged/main.cpp), [core v2](../packet29-merged/core_v2.hpp),
[non-GEMV bodies](../packet29-merged/kernels.hpp),
[specialised stages](../packet29-merged/specialised.hpp),
[round2](../packet29-merged/round2.hpp),
[paired GEMV](../packet29-merged/p28/submit.cpp),
[mixture adapter](../packet29-merged/performance.cpp),
[ordered mixture](../packet9-kopt4/reference.hpp).
The recorded `packet29/build/w2c-r29/run/plan.json` launch census was read
independently; its 1,777 logical sites are not the 2,307 timed device launches.
The tracked [class timing receipt](../packet29-merged/receipts-cards01-20261012-chain/w2c-r29/class-times.json)
is authoritative for launch multiplicities and costs. It represents 63 tokens.

## Common layer chains (48 layers)

| Tiny site / count per token | Exact inputs -> outputs and rounding | Producer and epilogue eligibility |
| --- | --- | --- |
| `hc.a.norm`, `hc.f.norm` / 48 each, two device stages each | BF16 streams[4,H] -> BF16 norm[4,H]; adjacent tree of FP32 squares, `inv=rsqrt(tree/H+1e-6)`, `B((x*inv)*weight)` | Whole-vector reduction for each stream. Cannot append to the preceding output GEMV. Keep the existing parallel reduction and scale stages. |
| `hc.a.act`, `hc.f.act` / 48 each | BF16 low[320] -> `B(L(low/4))` | Each low GEMV row owns exactly this scalar. Pure epilogue after GEMV's B rounding. Low is only consumed here. |
| `hc.a.mix`, `hc.f.mix` / 48 each | norm[4,H], gate[4,H] -> mix[H]; `sum=+0; sum=sum+S(gate[s,H+k])*norm[s,H+k]`, s=0,1,2,3, then `B(sum/4)` | Gate GEMV produces one of FOUR input rows, not the complete result. Not an unchanged-body row epilogue. Four-row recomputation or serial GEMVs would change geometry; retain mix. |
| `hc.a.inject`, `hc.f.inject` / 48 each | Dense norm[4H] -> inject[4], each `B(dot)` | The four inject values are scalars shared by all H output coordinates. Existing `small.hc` can merge sibling projections; it is a separate accepted mechanism, not counted as an epilogue saving. |
| `attn.combine` / 48 | streams[s,H+k], attention[k], inject[s] -> `streams=B(streams + attention*(2*S(inject/4)))` | GDN/QSA output projection owns attention[k]. After rounding that row B, its lane 0 can update all four stream coordinates. No cross-row dependency or reduction. Inject is already ready. Keep attention materialization if tests/observers inspect it. |
| `router`, `shared_gate` / 48 each | hc.f.mix[H] -> router[512] or shared_gate[1], each B(dot) | Both are dense projections of the same immutable input; scalar shared_gate may move before shared down. Router output requires global selection, not an epilogue. |
| `route` / 48 logical, five device launches in timed receipt | BF16 router[512] -> uint32 IDs[10], FP32 probabilities[10], gate/down route descriptors; finite check, max, exp, adjacent sum, division, stable top ten, adjacent selected sum, division | Router GEMV owns one of 512 logits, so max, denominator and rank need cross-row data. Cannot fuse route as a row epilogue. Ties favor smaller index. Failure sets sticky. |
| `gather` / absent as separate site in recorded plan | selected IDs and mix[H] -> descriptors and optionally repeated expert input | `route+gather` already absorbed descriptors; main rewrites paired expert source to the single mix row. Do not claim removal again. |
| `expsgate.check`, `expsup.check` / 48 each | uint32 status[10] -> sticky error=1 iff active, prior error=0 and any status nonzero | Paired gate/up GEMV already writes both statuses. Route validity predicts both checks, but a fused activation must suppress ALL slots on ANY failed route. Checking only the current slot is wrong. |
| `expsact` / 48 | BF16 gate[10,640], up[10,640] -> `B(L(gate)*up)` | `p28.paired.wg32` computes both rows in one subgroup. Pure epilogue after separately B-rounding gate and up. Neither intermediate has another computational consumer in Builder; retain them for observable-output equality in fixtures. |
| `expsdown.check` / 48 | uint32 down status[10] -> sticky as above | `p33.down.select` owns route status. Status fusion is possible without changing the 640-column dot or row order. |
| First device launch inside `moe` / 48 | BF16 down[10,H], FP32 prob[10] -> BF16 mixture[H]; `sum=+0`, ten ordered `sum=sum+down[slot,k]*prob[slot]`, then B | Each expert-down subgroup produces only one slot. The ten-slot ordered mixture is NOT an expert-down row epilogue; no unordered atomics, serial extra reduction or cross-SG wait. Keep this launch. This adapter is unconditional even if sticky is set. |
| `shexpact` / 48 | BF16 shared gate[640], up[640] -> `B(L(gate)*up)` | A shared up GEMV epilogue can read already-stored gate row; a paired dense gate/up can also produce both with unchanged individual dots. Gate/up are otherwise unused except diagnostics. |
| Second device launch inside `moe` / 48 | stored BF16 mixture[k], shared-down[k], shared-gate[1] -> BF16 moe[k] | Binding sets top=1 and probability=1, so exact expression is `B(B(+0 + mixture*1) + B(shared_down*S(shared_gate)))`; do not silently delete `+0`, multiply-by-one or B when asserting exceptional/signed-zero identity. Shared-down can own this epilogue AFTER moving shared_gate and existing mixture earlier. |
| `ffn.combine` / 48 | streams, moe, hc.f.inject -> four residual stream rows using same combine expression | Can append to shared-down after the preceding exact moe expression. Keep both intermediate B points and never add a norm reduction. Shared_gate and mixture must already be available. |

Logical order before epilogues: `hc.a.norm -> low -> act -> gate -> mix ->
inject -> attention branch -> attention output GEMV -> attn.combine ->
hc.f.norm -> low -> act -> gate -> mix -> inject -> router -> route/gather ->
paired experts -> gate.check -> up.check -> act -> expert down -> down.check
-> shared gate -> shared up -> shared act -> shared down -> shared_gate ->
mixture -> moe epilogue -> ffn.combine`.

For shared-down fusion move the scalar `shared_gate` and existing mixture
before shared down, preserving all data dependencies. `small.ffn` may already
move shared gate/up/scalar to the router issue; a new dispatch must account for
that grouping rather than execute those siblings twice. Fusing the route
checks requires careful failure ordering, described below.

## GDN branch (36 layers)

| Site | Exact data dependency / rounding | Eligibility |
| --- | --- | --- |
| `gdn.qkv`, `gdn.z`, `gdn.a`, `gdn.b` | All consume hc mix[H] and store B(dot): qkv[10240], z[6144], a[48], b[48]. z is not consumed until gated_norm. | `a+b` is an existing sibling GEMV merge; not an epilogue. |
| `gdn.conv` / 36 | qkv[ch] plus BF16 history[ch,3] and four FP32 decoded weights. `acc=+0`, taps 0..3: `acc=acc+input*weight`; output `B(L(acc))`; history shifts, last value=B(qkv). | Pure per-channel epilogue of qkv; B-round dot before convolution. History is observable state and must be updated identically. No BF16 acc round for this dilation=1 branch. |
| `gdn.recurrence` / 36 | conv q/k/v, a, b, BF16 state -> y[6144] and new BF16 state. q/k norms and 128-term recurrent dot use four consecutive products per logical lane then 32-leaf tree. y/state each B-rounded. | Reduction and state recurrence, not an element-wise GEMV epilogue. |
| `gdn.gated` / 36 | y[48,128] -> adjacent 128-square tree per head; `inv=rsqrt(sum/128+1e-6)`; output `B(((y*inv)*norm_weight)*S(z))`. No B between norm multiplication and sigmoid multiplication. | Not pure as issued: reduction needs all y. Could retain a standalone existing parallel norm-statistics stage, move z GEMV after it, and put final pointwise expression in z epilogue. This does not remove the reduction launch and the measured one-launch packet18 gated path would be replaced by a statistics launch, so **zero net launches removed** there. If the selected baseline were specialised two-stage gated_norm, retaining its Stage0 and fusing its Stage1 after moving z could remove one existing stage. That is a different baseline from this receipt. Keep the measured one-stage path as-is unless a separately measured split-stage implementation wins. |
| `attention` | gated[6144] -> attention[H], B(dot) | Owns attn.combine epilogue described above. |

## QSA branch (12 layers)

| Site | Exact data dependency / rounding | Eligibility |
| --- | --- | --- |
| `qsa.qgate`, `qsa.k`, `qsa.v`, `qsa.iq`, `qsa.ik` / 12 each | Each consumes hc.a.mix[H] and stores B(dot): qgate[12288], k[512], v[512], iq[512], ik[128] | Separate sibling GEMVs; all inputs exist before the first. Norm/rotary stages consume qgate/k/iq; pool copies v and combines/normalizes ik. No whole-chain tiny launch disappears just by fusing one copy. |
| `qsa.prepare` / 12 | qgate[24,512], k[2,256], iq[4,128], position -> q, gate, kn, iqn. Split q/gate; norm q/k/iq across head, B, RoPE pair operations using BF16 table, B. Gate is copied BF16 unchanged. | Whole-head reductions and rotary partner data. Cannot fuse whole prepare into any preceding GEMV row. Copying gate alone would leave the launch and offers no counted saving. |
| `qsa.pool` / 12 | kn,v,ik,position,raw -> persistent keys/values/raw and normalized rotary pooled keys. Four raw rows add left-to-right then B(mean); norm across 128; B norm then B RoPE. | Copies are row-local but norm/pool needs other rows and persistent state. Do not remove pool after fusing only a copy. |
| `qsa.select` / 12 logical, two device launches | iqn and pooled -> IDs; 128-product adjacent tree per head; sum four `max(0,dot)` scores; divide sqrt(128), stable top block selection, fill trailing tokens and -1 suffix | Reduction/ranking, preserve. Nonfinite scores set sticky; tie order is smaller block ID. |
| `qsa.attention` / 12 logical, three device launches | q/gate, keys/values, IDs -> y; score dot, softmax max/exp/tree sum/division, value tree; `B(B(value_tree)*S(gate))` | Score/softmax/value reductions, preserve. Final gating is already fused into value kernel. |
| `attention` | y[6144] -> attention[H], B(dot) | Same pure output-projection residual epilogue as GDN. |

## One-off PLE and token-boundary chain

| Sites / occurrences per token | Inputs -> outputs, rounding and reduction | Eligibility |
| --- | --- | --- |
| `begin.0`, `begin.1`, commits / one each in two-card plan | active/position/error; begin bounds-checks position, commit increments if active and error=0 | Control boundary; retain. |
| embedding lookup + `streams` / one | Host-prepared BF16 embedding -> copy into four streams | No preceding GEMV. |
| `ple.hash`, lookup / one, layer 1 only | token/history/metadata -> bounded token IDs + history, then host-prepared lookup | Hash/check/control, no preceding GEMV. |
| `ple.kn`, `ple.qn` / one each, two stages each | GEMV-produced key[4,H] and streams[4,H] -> head norms, B | Whole-H norm reductions; retain. |
| `ple.gated` / one | kn/qn: B(product) per coordinate; adjacent tree -> B -> divide sqrt(H) -> B; B(sqrt(max(abs(z),1e-6))); signed root -> B; sigmoid -> B; gate[s]*value projection[k] -> B | Reduction across H, not pure value GEMV epilogue unless gate scalar is first computed by retained parallel stages. No assumed saving. |
| `ple.cn` / one, two stages | gated[4,H] -> norm BF16 | Whole-vector reduction; retain. |
| `ple.conv` / one | cn and nine-position history, dilation 3; four-tap FP32 accumulation -> **B(acc)** -> L -> B, plus history shift | No preceding GEMV: cn is a norm output. Could fuse later add into convolution body, but this is a separate non-GEMV fusion. |
| `ple.add` / one | `B(streams + B(gated+conv))` | Row-local convolution epilogue; keep if this packet is limited to GEMV epilogues. |
| `final.norm`, `final.low`, `final.act`, `final.gate`, `final.mix` / one each | Same hc equations, no inject | Final low->act is pure (one extra launch saved); final gate->mix still four-row dependency. |
| logits -> `argmax` / one logical, two device launches | B logits, finite test and stable first maximal index; sets sticky on nonfinite | Global reduction; not output-row epilogue. |
| handoff/result | Ordered peer copies in two-card plan | Outside one-card G4, retain runtime ordering. |

## Failure and observer contract

The ng activation, convolution, moe blend, gated norm and other ng bodies also
check signed position after active/error: `pos<0 || pos>capacity-tokens` sets
sticky 1 and returns without output writes. For token-at-a-time epilogues this
is `0<=pos<capacity`. Simple hc_combine and check_status do **not** perform
this position test. A full token normally establishes validity in begin, but
standalone identity fixtures must retain this operation-specific distinction.

GEMV submission does not consume active/error; it writes its rows and uint32
statuses even when non-GEMV work is disabled. Non-GEMV steps return for inactive
or preexisting sticky error. A route check writes literal uint32 1 only when
active and incoming error=0; existing nonzero sticky bytes remain unchanged.
A bad expert descriptor writes status=1 and canonical NaN row; valid rows
beyond `row_count` also receive NaN but status remains 0. Preserve this distinction.

Paired gate/up yields both status arrays before either check. If **any** route
is invalid, both original checks result in sticky 1 and the entire activation
is untouched. Local lane status alone cannot reproduce that behavior. A fused
kernel must determine all ten route predicates before activation stores and
must not let sibling writes to sticky race with whether good rows execute.
A same-value 1 write is only valid if every writer is known to store the exact
same 32 bits and no writer restores 0 or overwrites a preexisting nonzero code.
Use atomic loads/stores where concurrent lanes share that word. Do not suppress
unconditional GEMV/status output stores just because the epilogue is disabled.

The mixture adapter is also unconditional. A shared-down fusion must preserve
its resulting BF16 bytes separately if the comparison treats them as observable,
even when the final moe/combine steps are skipped. Dense NaN payload/sign
behavior is inherited from packet29's finite arithmetic contract: exceptional
fixtures document equality to the actual selected body; they do not expand
that body's already-limited qualification against another GEMV implementation.

Norm's post-reduction scaling cannot be an epilogue of the earlier producer
without a readiness dependency on that reduction. A kernel cannot know the
whole-vector sum before its sibling rows finish. No busy wait, new barrier,
serial sum, extra work-group or recomputed norm is an admissible workaround.

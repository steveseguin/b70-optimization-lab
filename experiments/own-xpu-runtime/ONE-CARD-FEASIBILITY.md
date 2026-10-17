# Packet 55: deciding the one-card IQ3 engine

October 17, 2026. **Preparation, not a one-card speed result.** The coordinator
will fill the measured inputs below after separate route, CPU and transfer
windows. Packet 49c's two-card 45.6955 tok/s remains its own result; it is not
a one-card timing input. The 15.9 tok/s reference uses stock llama.cpp CPU
offload, different arithmetic and placement. Neither number is a prediction.

This is the Unsloth UD-IQ3_XXS **quantized compressed version**, revision
`766911a6b7369840a91dbcd95f9f997acaab6cd6`, with packet 49c's
`iq3-p49-split32-v1` arithmetic and full BF16 KV. Preserve the exact target
verification and MTP weights. Credit **Niko1221 / Strata** for the hot-expert
cache and CPU-miss design idea documented in [ONE-CARD-DESIGN](ONE-CARD-DESIGN.md).
All packet 55 code is independently written; no external runtime code is used.

## Inputs the coordinator must fill

| Input | Measurement and scope | Value |
| --- | --- | --- |
| Route misses | Held-out 12 of 24 independent calibration prompts, all executed target visits, including rejected speculation; LRU/LFU/static at 8/12/18/24 decimal GB | Pending |
| CPU `C_l(m,t)` | Exact full expert batch time, `m=4,6,10`, `t=1,4,8,12,16`, ordinary and exceptional layer separately, both fresh owners | Pending |
| H2D `X_l(m)` | Route-known to all slabs resident, `m=4..10`, isolated and concurrent compute; ordinary and layer-2 payloads separately | Pending |
| Copy overlap | Measured common-clock event overlap and wall time, plus compute slowdown | Pending |
| One-card `A_l,G_l,F_l,D` | Nonexpert prefix, hit/shared and miss expert work, final combination, and same-card draft time | Not measured by packet 55 |
| Work ratios `r_T,r_D` | Executed target positions and draft calls divided by emitted tokens; retain partial/rejected work | Pending route/controller receipts |
| Mailbox `Q_l` and host contention | Input/route D2H, CPU wakeup and BF16 result return; shared CPU/DMA/PLE memory pressure | Not measured by packet 55 |

The three requested measurements choose a promising implementation. They do
not establish its end-to-end speed without the remaining GPU, mailbox and
scheduling inputs. Fill missing values with `null`, never zero. Use actual
per-layer miss distributions and tails, not a single uniform hit-rate average.

## Bytes, fit and units

Ordinary complete experts are `B_l=1,971,200` packed bytes. Layer 2 uses
`B_2=2,329,600`. One complete target position selects
`sum_l 10 B_l = 949,760,000` bytes. A byte hit rate is
`h = hit_payload_bytes / requested_payload_bytes`; weights do not weight this
ratio, because every selected expert executes regardless of its route weight.
For each observed layer visit `v`, `M_v = misses_v * B_layer(v)`.

The cache simulator charges the packet46 slot strides (1,974,272 ordinary,
2,330,624 exceptional), 64 metadata bytes per slot and the fixed map/directory.
DMA/CPU processed bytes remain the packed payload, not padded slot sizes.
GB means `10^9` bytes, GiB means `2^30` bytes, and all formulas below use seconds.

Use the corrected [packet46 budget](stage2/packet46-specialized/CACHE-BUDGET.md):
the 18 GB cache plus nonexpert, resident draft, state, workspaces and transfer
allowances totals 29,818,616,662 bytes, leaving about 681 MB beyond the 1.5 GB
physical reserve against 32 decimal GB. This is a design allowance, not a fit
receipt. **24 GB is a route-locality sensitivity point and does not fit this
placement.** Longer context, graph pools and full speculative rollback require
new admission. Do not pin the whole expert bank.

## Per-layer latency models

Let `A_l` be GPU work before routes/input are ready; `F_l` the fixed original
slot-order combination and subsequent work; `G_l(h)` GPU hit experts plus
independent shared work; `J_l(m)` GPU execution of the streamed miss experts.
All are measured on one card with the declared formats. Expert results return
to their original ten slots; completion order cannot change the mixture.

**(a) GPU cache plus exact CPU misses.** With measured mailbox cost `Q_l(m)`,

```
T_CPU(l,m,t) = A_l + max(G_l(10-m), Q_l(m) + C_l(m,t)) + F_l
```

This requires demonstrated current-layer overlap. A conservative serial case
replaces `max` with addition. Threads above ten cannot be presumed useful from
expert-only parallelism; the row-vector kernel must expose rows as well.
`C_l` comes from measured dependent batches, not `m` times an isolated best
expert. Packed-byte throughput is work processed, not a DRAM bandwidth reading.

**(b) GPU cache plus H2D misses.** For a conservative implementable schedule,
start DMA and GPU hits/shared work after the route is known, then execute GPU
misses once both the compute queue and complete slabs are ready:

```
T_DMA(l,m) = A_l + max(G_l(10-m), X_l(m)) + J_l(m) + F_l
```

`X_l` includes host enqueue and completion latency. Do not replace it with
payload/bandwidth unless explicitly showing an ideal lower-bound scenario.
The serial control adds `G_l + X_l + J_l`. A more finely pipelined slab schedule
needs its own event-DAG measurement before reducing this estimate. Copy-engine
overlap with a synthetic kernel does not prove overlap with actual expert work.

**(c) Hybrid.** Assign `c` of the `m` misses to CPU and `s=m-c` to DMA. With
independent workers and proven overlap, the schedule above becomes

```
T_HYBRID(l,m,c,t) = A_l
  + max(Q_l(c) + C_l(c,t), max(G_l(10-m), X_l(s)) + J_l(s)) + F_l
```

Use simultaneous CPU/DMA measurements for `C_l` and `X_l`: they share host
memory bandwidth, PLE traffic and issuing CPUs. Taking each component's isolated
best time is an optimistic scenario, not a hybrid forecast. For unmeasured
miss counts, measure them in the integration window rather than interpolating
4/6/10-miss CPU samples or 4..10-slab copy samples. `C_l(0)=X_l(0)=J_l(0)=0`
only when the implementation performs no work for an empty branch.

## Turning work into emitted tokens

Sum dependency-constrained layer times for **every executed visit** in the
held-out trace, including rejected/corrected work. Charge head, rollback,
embedding/PLE, controller and cache initial fills separately. Keep prefill/TTFT
separate from decode; report cold cache fill as its own cost, never hide it.

```
projected_decode_tok_s = N_emitted /
  (sum_executed_target_visits T_design(l,m)
   + sum_draft_calls D_same_card + T_heads + T_rollback + T_control)
```

Avoid double-counting heads or other work already included in `A_l/F_l`.
Equivalently, when complete target passes are well defined,
`tok_s = 1 / (r_T * mean(T_target) + r_D * mean(D) + overhead_per_token)`.
Partial speculative passes require the event sum, not fractional invented
passes. The draft and target share the card's compute engine and their GPU
times serialize. Only demonstrated copy/CPU overlap can be subtracted.
Do not import the two-card pipeline's acceptance rate as a one-card speedup.
Even if outputs match, placement changes timing and the controller must be
measured. MTP's rejected work remains charged in both numerator definitions.

For a latency budget `L` after fixed GPU/draft/control costs, the ideal streaming
requirement alone is `BW_required = miss_bytes_per_emitted_token / L`; the CPU
analogue uses exact packed-byte processing throughput. These are necessary
read/work bounds, not sufficient speed predictions.

## Which implementation comes first

Build **one-layer GPU cache plus bounded H2D streaming first**, as the exact
control path. It retains the qualified GPU expert arithmetic, provides all-hit,
all-miss and mixed-route byte gates, and directly measures the missing copy and
compute schedule. It is not yet the selected fastest full engine.

Then use the held-out per-layer distributions and both fresh quiet CPU results
to select CPU misses or a hybrid only where the measured critical path is
smaller. The earlier 3.9–5.3 GB/s packet46 result rules out assuming CPU speed;
it does not decide the new row-vector path. Keep layer 2 separate. Qualify
one-card target state, same-card MTP rollback, exact packet49 oracle tokens and
fresh-process determinism before any full-suite speed claim. The coordinator
records the decision after filling the measured table; no forecast is promoted.

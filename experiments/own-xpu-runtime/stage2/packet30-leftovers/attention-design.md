# QSA attention: prepared candidates, not device measurements

The runtime incumbent is packet18's `submit_parallel` adapter selecting the
three `ng::submit` stages in its own `native.cpp`, not a rewritten baseline.
Packet27 retains the same arithmetic and launch geometry in `kernels.hpp`.
The frozen K2 events at `../packet27-round2/receipts-cards01-20261012-chain/k2-r27/events.jsonl.gz`
give per-stage medians (200 events per stage) of **21.146 / 14.271 / 140.104 us**
for packet18 score / softmax / value. The rejected round2 path is
**8.333 / 14.271 / 166.875 us**. Its score saving loses to a slower value kernel.
Sums of these stage medians are not a replacement for the recorded median of
each launch group's event-time sum (175.5 versus 189.5 us in K2).
The separate in-model class is about **268 us/layer**, 12 layers/token.
These workload identities differ. G3 must flag a baseline outside +/-15% of
268 us as not representative; fixture K2 success cannot promote a saving.

## Where the incumbent time goes

* Score: 24 times `min(capacity,budget+3)` work-groups, each WG128/SG32.
  At capacity4096/budget2048 this is 49,224 groups, including most unadmitted
  slots at short context. An admitted slot multiplies 256 key/query pairs,
  performs the explicit eight-level local-memory sum, divides by sqrt(256),
  and stores one float. There are 12 group barriers including guard, fill,
  reduction and final store ordering. Each of 128 lanes multiplies two
  leaves; progressively fewer lanes update reduction nodes. Even rejected
  `-1` groups execute the initial guard barriers.
* Softmax: 24 WG128 groups, with `(budget+3)*4` local-memory bytes/group.
  Every work-item scans the same selected IDs and maximum; the exponentials
  and normalized stores spread over the group. There are 4+ceil(log2(n))
  barriers for n selected slots. At n=88, 40 lanes do no exponential work.
* Value: 6,144 WG128 groups, one per head/output coordinate; each repeats ID
  scanning and the selected-order n-leaf local-memory product tree.
  It allocates the full `(budget+3)*4` local bytes even for n=88, and executes
  4+ceil(log2(n)) barriers. This is the dominant K2 event. At n=88, 40 lanes
  never multiply a leaf; subsequent tree levels idle progressively more.

## Designs and work per launch

`p30.attention.sg32` has **three launches**:

1. Exactly `24*admitted_bound` WG32 groups. Each is one (head, selected-slot)
   subgroup, eight adjacent key/query products/lane, a three-level private
   tree and five subgroup select levels. No local memory or barrier.
2. 24 WG32 groups. Each head computes the max in incumbent selected order,
   then aligned 32-leaf exponential subtrees with five subgroup selects,
   the upper tree in lane zero, and normalized probability stores.
3. 6,144 WG32 groups. Each head/output coordinate evaluates aligned 32-leaf
   selected-order value subtrees, then the upper tree in lane zero. Only lane
   zero rounds/stores the result; all lanes participate in the reductions.

`p30.attention.score_softmax` has **two launches**:

1. 24 WG32 groups. Lane l handles selected slots l, l+32, ... with a private
   256-leaf score tree for each. Scores remain in 65 registers per lane at
   maximum capacity (plus score-tree private storage). Each lane computes
   max in the same selected order through subgroup register selects; exp
   and the same aligned tree then produce probabilities. The global scores
   are stored for diagnostics, but never read within this launch. No memory
   rendezvous is required.
2. The identical WG32 value stage above.

The second candidate trades much less score parallelism and larger private
arrays for one fewer launch. It may spill or lose occupancy; it is a measured
candidate, not a prediction of a win. Softmax could instead be duplicated in
all 6,144 value groups, but 256 copies/head of detmath exp plus denominator
work is not pursued. A general merge across independent work-groups would
need synchronization and is not implemented.

The schedule can compute an admitted bound without reading device memory:
`4*min((position+1)/4,budget/4) + (position+1)%4`. Put that bound in `s.extra`.
No selected slot beyond that bound may be present. G3 uses exact counts known
from its generated fixtures. This specialization is decode (`tokens=1`) only.

## Bit identity and races

For an aligned 32-leaf block b, subgroup level stride=1 combines original
leaves 32b+2i and 32b+2i+1; stride=2 combines their original adjacent parents,
and strides 4/8/16 give original levels 3/4/5. Only existing left nodes update.
An absent right child is **added as +0**, as in the incumbent odd-tail rule.
No level is evaluated once stride>=the original global n. The block roots
are contiguous nodes at original level five; the scalar adjacent tree over
those roots computes exactly the remaining original nodes, with the same
odd-tail +0 additions. For n<32, there are no invented upper levels.
The score variant's 8-leaf private blocks followed by five SG32 levels are
likewise original levels 1-3 followed by 4-8. Neither score path changes any
multiplication or addition parent, and division occurs after the root.

Max keeps the incumbent selected-order `std::max(-infinity, score)` behavior.
Detmath exp, denominator division and value products are unchanged. Value
retains selected ID order even when it differs from context order. The final
result retains **both** BF16 points: BF16(tree(value_products)) before sigmoid
multiplication, then BF16 output store. No compressed cache is involved.

Each score/probability cell has one writer. Each output has one lane-zero
writer. Register shuffles communicate values; there is no work-group memory
communication. Each kernel's dependencies include the preceding event.
Sticky failures use atomic accesses; selected IDs/input/control buffers must
remain immutable for the launch group. Argument guards reject output aliases,
short/null/misaligned bindings, invalid geometry and unknown variants.

## CPU evidence and limits

`attention_cpu.cpp` directly invokes unchanged `ng::cpu` and `integrated::Core`
for ten finite fixtures, including positions 1,3,87,255, odd selected lengths,
selected order reversed, and the full 2,051-slot budget. It checks admitted
score/probability bytes and all output BF16 bytes for both candidate layouts.
All lengths 1..2051 exercise the blocked tree with signed-zero/cancellation
inputs. Zero-score selection ties use both the incumbent qsa_select and Core.
Host argument rejection runs for both device entry points. Each of g++ and
icpx runs in two fresh processes; `attention-gates.json` records **266,547
checks/process** and binary hashes. SYCL translation compiled, not executed.

**Existing empty-selection mismatch:** packet18 returns with unchanged output
and no error; Core rejects empty attention. Both candidate paths match the
incumbent empty semantics, and the gate explicitly requires the Core failure.
That is a diagnostic disagreement, not a claim that the empty case passes
triple equality. Legal decode selection with budget>=4 is nonempty. Inactive
score scratch suffixes are unobservable scratch and are not written by the
admitted-only candidate; compare admitted scratch cells and all output bytes,
not previously initialized scratch suffixes.

Hypotheses for the 268 us in-model identity: **100-220 us** for three-stage
SG32 and **90-220 us** for score+softmax. These are deliberately broad testing
hypotheses, not measured times or savings. Empty, poisoned or mismatched
baselines never produce a speed row. No device was run for this packet.

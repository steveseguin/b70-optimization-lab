# Rank0 draft and balanced halves (design only)

Today rank1 runs its target half then the draft. Using packet32's measured
host halves A=23.8 ms and B=23.4 ms, a successful guessed cycle has a lower
bound max(A,B+m), where m is the draft wall time. m has not been measured in
this packet. Moving the draft to rank0 and moving enough target layers to rank1
aims for rank0 target+draft = rank1 target. With T=A+B=47.2 ms, the ideal cycle
is (T+m)/2 rather than T/2+m: it saves m/2 per hit before other overhead.
Illustrative m=4/8/12 ms yields ideal cycles 25.6/27.6/29.6 ms versus 27.6/31.6/35.6
ms. These are scheduling projections, never performance measurements. Misses
and the measured 77.7% development acceptance reduce the benefit.

Memory plan: packet36's rank1 ledger has 27,855,798,676 target bytes and
3,345,271,094 draft bytes, totaling 31,201,069,770 of 34,242,297,856 bytes. Its
head is shared. A rank0 draft needs a second output head: 839,321,600 bytes at
the current representation, plus 3,345,271,094 draft bytes, about 4.185 GB extra
on rank0 before target layers move. Rank1 would release the 3.345 GB private
draft allocation but retain its target head. Rank0 also has 29,601,792 bytes of
rollback banks. Determine exact per-layer allocation sizes, transfer enough
target layers to fund rank0's draft/head plus at least 1.5 GB margin, then
solve balance from measured per-layer times. Driver overhead must be measured
on both cards; allocation totals alone do not qualify residency. Confirmed
hidden streams must travel back to the rank0 draft and be included in timing.

The historical rank0 driver receipt reports 26,718,540 KiB resident VRAM
(27,359,784,960 bytes), distinct from the allocation-only rank1 ledger.
Adding the draft and second head to that observation gives a planning estimate
of 31,544,377,654 bytes, leaving 2,697,920,202 bytes before layer transfer.
Rank1 after removing its draft has 6,386,499,180 bytes free; reserving 1.5 GB
allows at most 4,886,499,180 added layer bytes. If L bytes move from rank0 to
rank1, the two estimates become 31,544,377,654−L and 27,855,798,676+L.
Use actual per-layer bytes and draft time to choose L; no layer count is
approved by this estimate. Source: packet32
receipts-cards01-20261012-chain/w2s-r32/rank0/drm-memory-after_load.txt.
These recorded values are read-only historical evidence, not a new device probe.

<div style="break-after: page"></div>

# Double speculation (design only)

Compute a draft from an unconfirmed guess while the target verifies its parent.
At development acceptance alpha=199/256=0.77734, independent two-step survival
would be alpha squared=0.6043; independence is an assumption and must be
measured, not used as an acceptance claim. The upper benefit is hiding at most
one further half/draft cycle for those surviving chains. Packet32's diagnostic
all-hit 24.1 ms cycle sets a useful comparison, not a speed forecast. Wrong
parents require discarding every descendant and redoing target work.

This needs a second private draft bank (all QSA cache writes and position),
separate confirmed and provisional hidden/embedding histories, transaction IDs
per ancestry edge and a two-position target rollback design. Only the target
may emit; verifying the first guess never verifies the second. Reuse immutable
weights/head only. Add exhaustive trees including late EOS/provider errors,
fresh-process exactness and complete byte comparisons before timing. Negative
acceptance correlations, doubled scratch and extra wrong-path work may erase
the gain. Packet38 intentionally implements only one outstanding guess.

<div style="break-after: page"></div>

# Batch prefill (design only)

The current pipeline reads prompt positions one at a time. The development
prompt begins near 88 positions; at the measured 47.2 ms sum of halves, a serial
approximation is 4.15 s of prompt arithmetic, excluding overlap and startup.
Existing prompt overlap can approach half that ideal bound. These are
projections; no batch-prefill speed has been measured. Larger matrix batches
could reuse weight reads across positions and avoid per-token scheduling.

Needed: block shapes for every dense/routed projection; token-position-specific
expert routes; causal QSA with correct cache append/pooling order; exact serial
GDN recurrence and convolution state boundaries; PLE history generation;
per-position hyper-connection streams; equivalent error and BF16 rounding
boundaries. GEMM reductions must reproduce arithmetic-v2 exactly, not merely
be close. Inventory every production shape before bisection if batching changes
a greedy output. A block scratch plan must fit both cards without compressing
KV. Gate block sizes 1/2/4/8 against single-position fixtures including tails,
EOS and multiple request orders, then measure prompt reading separately from
decode. No batch-prefill implementation is included.

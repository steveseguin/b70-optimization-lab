# Packet 68: two proposals, measured cost before a lossless engine

2026-10-17. CPU preparation only; the coordinator owns every device window.
Parent: frozen packet64 production, 24/24, draft rank 1, ordinary rollback.
Oracle: `iq3-p49-split32-v1`. All target rows retain the original M=1
arithmetic, BF16 KV, reduction order, rounding and target head.

## Inputs and limits

Packet61x measured 51.033041 tok/s, hit/miss 17.24/28.48 ms, a1=0.787.
Packet64 attribution measured rank0/rank1 halves at 14.23/14.69 ms;
corrected rank0 is 12.99 ms. Packet66 measured conditional a2=0.718 and
second draft 1.72 ms GPU / 2.38 ms wall. These are separate runs, so the
following calculations are projections, not matched performance evidence.

Expected accepted block length is 1+a1+a1*a2 = 2.352066 tokens.
Probabilities of reject-first, accept-first-only, accept-both are respectively
0.213, 0.221934, 0.565066. A rejected suffix must never emit a token.

## Alternatives

| Design | Cost model and projected rate | Restore costs and risk |
| --- | --- | --- |
| (a) Two-deep speculative pipeline, serial target rows | Two ordinary pipeline intervals cost 34.48 ms plus failed guesses. If d1 fails, discard d2 and regenerate from the corrected target. Effective second acceptance is a1*a2+(1-a1)*a1=0.732697. Using the measured 11.24 ms miss penalty gives 39.878 ms per two tokens, **50.15 tok/s**, before any extra scheduling or state-copy cost. Two draft passes replace two ordinary passes; they are not free. | Existing exact rank0 snapshot per row includes spare GDN/conv banks, mutable intermediates, overwritten KV rows/tails, histories and launch extents. Two simultaneously outstanding rank0 rows would also need a third recurrent bank and two stream slots. High protocol risk for little predicted benefit. |
| (b) M=3 target verification [t,d1,d2] | With a hypothetical fully shared dense-weight pass, T3 = H0(3)+H1(3)+two draft passes+restore. Neither half at M=3 is measured. The packet66 equivalent-cycle proxy 35.02+4.129+2.38=41.53 ms predicts **56.63 tok/s**, but omits several costs and assumes rank overlap that this blocking verifier does not have. It is not a conservative bound. A serial three-row implementation costs at least 3*(14.23+14.69)+2*2.38=91.52 ms, about **25.70 tok/s** before rollback. | GDN/conv rows are sequential recurrence; QSA needs causal per-row extents. Save state at prefixes 0/1/2 and restore the accepted prefix. MoE routes differ per row; sharing all expert weights cannot be assumed. Every dense/expert batched kernel needs row-invariant arithmetic and independent CPU/device byte gates. Highest engineering risk; not justified by an unmeasured proxy. |
| (c) Two-proposal hybrid, bounded one-row target speculation | Generate d1 and d2 together, retain d2 as a hint for the next pipeline interval, and verify each target row through unchanged M=1. Resolve each rank0 candidate before starting the next. Same **50.15 tok/s** first-order estimate as (a); potential benefit is earlier availability of the second hint, bounded by the existing draft/half overlap. No claimed 10% win. | One existing target snapshot at a time. Recursive d2 runs on private draft state, then restores it exactly. Advance the ordinary draft with confirmed target hidden state even when its head is skipped. Rejected d1 invalidates d2. This avoids a second outstanding target transaction and keeps the original target kernels. Lower engineering risk. |

## Decision

Choose **(c)** as the lossless depth-2 prototype and cost screen. It is an
honest test of two proposals in this engine, not a claim that the 56.6 tok/s
proxy is reachable. Do not implement an M=3 kernel under the name of a serial
row loop. The substantial M=3 opportunity remains a separate, unmeasured
engineering arm. No speed verdict before matched fresh device controls.

The probe will measure the added speculative target-half and exact restore
cost using actual requests, with extra work discarded. Probe requests keep
the original emitted tokens. Log snapshot, half and restore separately;
compare all thirteen packet49 token streams. Sample bounded generated
positions; never insert device work inside a publication callback.

The prototype drafts twice per proposal cycle. It commits only target tokens,
uses d2 only after d1 matches, and falls back to an ordinary draft after a
first-token miss. Draft state after the recursive pass is restored before
the confirmed path advances. A skipped head still advances draft KV from
confirmed hidden state, preserving future draft inputs. Target work remains
one row at a time, including batches of 1/2/3 in the CPU fixture.

## Gates and execution order

1. Commit this design before implementation.
2. Build and seal an outputs-unchanged lane-B cost probe; commit and push it
   immediately so the coordinator can measure it while CPU work continues.
3. Check small target fixture bytes at M=1/2/3 against packet64, exact
   rollback for all acceptance cases, and two deterministic draft repeats.
   No CPU model run or multi-hour qualification.
4. Seal prototype. Coordinator first runs one prompt × 32 tokens, then
   fresh production/candidate/production screens on each lane, each with
   incident64 plus twelve prompts × 128 tokens and all thirteen exact.
5. Keep device timing/quality pending until actual receipts exist. Never
   promote a quick screen as the full final gate.

CPU jobs: nice19, cores 8–15,24–31, Python -B, stdin /dev/null, 8 GiB maximum,
serial compilation. Build budget <1.5 GB; stop writing below 9 GB free.
Only this packet and the requested chronological note are writable.
No CURRENT.md or frozen runtime edits. No GPU use, service, sudo or host change.

Sources: packet64 attribution note; packet66 device-acceptance.json and probe
implementation; packet64's existing speculative pipeline and exact snapshots.
Recursive MTP reuse is the architecture idea supplied by the owner; code is
independent lab code, with no external runtime code imported.

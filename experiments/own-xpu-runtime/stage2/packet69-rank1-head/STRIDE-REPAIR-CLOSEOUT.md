# Packet69 wide-head stride repair — CPU closeout

<!-- campaign-closeout -->

## Question and identity

Why did lane B's `p69-quick-B-02-combined-a` stop with rank1's sticky error
after production passed? This repair uses packet69's own candidate tree,
the same selections and `iq3-p49-split32-v1` arithmetic. Packet49 remains the
target oracle. Work on October 17 was CPU-only, nice19, cores8–15,24–31,
one compiler at a time; no model, GPU, service or host setting was used.

## Outcome

The addressing defect is reproduced and fixed on CPU. `p69::Head<64>` at
target/draft `logits` advanced by 3,200 bytes per row. The expanded layout
stores an additional 180 bytes of original Q6_K metadata per row, making
the stride 3,380. The failed run's head allocation is 839,321,600 bytes for
248,320 rows, confirming that layout. The same defect affected wide128.

With two synthetic rows, row 1 should produce BF16 `0x42cc`; the old head
produces NaN `0xfff7`. The real production argmax's finishing stage
(`round2::simple_group<Op::argmax,1>`, site `argmax`) then sets sticky
`error=1`. The fix derives row stride from `integrated::arithmetic::row_bytes`.
The error remains sticky; it is never cleared to hide the failure.

## What worked

A linked multi-row fixture exposed the defect that the original single-row
arithmetic test missed. The new fixture compares against the unchanged linked
production head and checks full/prefix outputs, tail sentinels, argmax/ties,
NaN rejection and sticky status. Both head compilers pass 96 cases in two
fresh processes each. Recompiling the archived original head still fails the
same test with NaN and sticky error, making the regression test sensitive to
the bug. Existing head arithmetic and draft fixture output hashes are unchanged.
The original padded WG64/WG128 coverage checks also pass.

## What failed or remains uncertain

The initial CPU fixture checked only a row's arithmetic, not its storage
stride. Useful code/scale reads remain 3,200 bytes per row; they are not the
allocated stride or physical DRAM traffic. Both head-enabled paths first fail
after the device trace's 86 completed target prompt halves. The device trace
has no per-kernel error provenance, so the exact writer is established by the
CPU reproduction, not a new device trace. Full device parity, draft acceptance
and speed remain pending; no performance claim is made.

## Evidence and patches

- [Diagnosis and original evidence hashes](candidates/evidence/reseal-r3/diagnosis.json).
- [Linked fixture and legacy negative control](candidates/evidence/head-status/receipt.json).
- [Original arithmetic/draft fixture gate](candidates/evidence/cpu-gates.json).
- [Revision-3 validation and queue plans](candidates/evidence/reseal-r3/validation.json).
- [Offline compiler evidence, before and after](candidates/evidence/reseal-r3/offline-head/receipt.json).
- [Changed kernel](candidates/p69_head.cpp), [layout helper](candidates/p69_head.hpp).

Original source, receipts, selections and wrapper records are copied under
`candidates/evidence/reseal-r3/previous/`. Original executables remain locally
hardlinked under `candidates/build/previous-r3/{gnu-host,device}/own-rt-iq3`;
their hashes are in `previous/manifest.json`. Generated build trees remain
untracked. The pre-repair source is also retained by Git parent history.
The raw failed device run remains untouched under its original screen path.

## When to revisit

The coordinator can rerun the complete eight-screen grid with
`screen/quick/jobs-A-r3.txt` and `jobs-B-r3.txt`. `combined` stays in the same
position, with fresh production controls first and last on each lane. All
sixteen plans and both proposed queues pass on CPU. Stop at any failed screen;
do not retry it or clear a live latch automatically. Device results decide
whether any candidate advances. The seven-screen fallback was unnecessary.

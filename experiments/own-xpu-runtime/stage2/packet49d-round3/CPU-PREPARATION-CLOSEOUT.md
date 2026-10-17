# Packet49d CPU preparation closeout

<!-- experiment-closeout -->

Question: can the packet49c engine include the three banked packet53b winners
and every eligible packet54 choice without changing arithmetic, with a sealed
selection after device measurement and no additional device rebuild?

Identity: separate packet49d source tree; packet49c parent at 8d43f6e77;
packet54 seal c27ecf935060a2e59a9acb9615be447e32f7881c9a886687a4b9f75dc5d0f508;
packet53b summary 8c20eddf341b541c90b87f4b4dbea521cacec8a6fff6220b853ebdd3ae0b94ef.
Arithmetic remains iq3-p49-split32-v1 and uses the unchanged packet49 oracle.

Preparation status is recorded in the [task note](../../../../notes/2026-10-17-own-runtime-packet49d.md).
The numerical evidence is the new packet's mode and gate receipts, not copied
historical receipts. Device qualification remains pending and no model speed
is claimed. All selections are tested independently of selection.json.

Useful mechanisms: compile all choices once, bind submit functions at engine
initialization, verify the exact parsed selection bytes, and separate immutable
CPU proof from the final selection seal. Both M=2 rows retain serial state.

Failure retained: the first CPU fixture's supposedly undersized QKV allocation
was actually a 4MiB RoPE allocation. The runtime guard correctly accepted it.
The test now uses a 12-byte allocation. [Correction evidence](evidence/preparation-corrections/receipt.json)
retains the failed run; the corrected fixture passes 682 checks.

Retained evidence: source/kernel files, build/gate/retention receipts, compact
CPU outputs and external executables. [Independent review](REVIEW-INDEPENDENT.md)
records protocol checks and limits. No protected source/chain/oracle was edited.

Next/revisit: the coordinator runs packet54 and only seals 49d if both combined
savings reach 40us. Then all early/model windows must pass. A failed trigger
keeps 49d off-device. Captured replay and full-model identity require those
windows; CPU operator parity is not their substitute. The current submitted
record is preserved in the coordinator-maintained threshold ledger.

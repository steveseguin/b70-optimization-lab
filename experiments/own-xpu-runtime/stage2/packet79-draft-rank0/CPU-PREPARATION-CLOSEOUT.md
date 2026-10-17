# Packet79 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can the packet75 record-line binary place its unchanged MTP draft on rank0
with only its 91,392-row head prefix, at 23/25 or24/24 target layers? Prepared
October 17, 2026 on steve-b70s, CPU only. Arithmetic remains
`iq3-p49-split32-v1`, packet49 remains the oracle, KV remains BF16.

## Outcome

Accepted for coordinator screening, not as a measured optimization. Six
placement/HC views are sealed. [Final check](evidence/final-check.json) passes
12 actual shared-wrapper plans,75 Python tests and temporary A/B queue plans.
No device or real model was executed.

## What worked

The existing reverse-handoff/native callback protocol supports asynchronous
rank0 drafting. [Protocol checks](evidence/protocol.json) cover hits, misses,
suppression, rollback, EOS and delayed publication under GNU/Intel.
[Miniature engine checks](evidence/cpu-gates.json) match packet75 target and
draft bytes in 12 fresh candidate processes. [Selected operator checks](evidence/composed-byte-identity.json)
match GNU/Intel bytes in both HC views. [Full-shape checks](evidence/full-shape.json)
run actual initialization, capture and post-load allocation for both ranks;
[real admission](evidence/memory-admission.json) retains both memory limits.

## What failed or remains uncertain

Preparation initially lacked a copied prototype include; it was supplied before
successful engine compilation. The mock linker needed the existing wait-policy
object and explicit spin selection. The first mini invocation omitted
OMP_NUM_THREADS=2 and correctly refused. A memory assertion initially matched
attention-output weights as well as the final head and was narrowed to the
exact final-head label. The queue planner's success key is`plan`, not`passed`;
the receipt parser was corrected. These were CPU harness issues, not GPU faults.

Real model acceptance, packet49 device equality, physical memory residency,
repeatability and speed remain unmeasured. The roughly 5% projection is not a
result. A full record chain is not prepared by this screen-only packet.

## Evidence and patches

[Runtime delta](rank0-prefix.patch), [copied-source pins](parent-source-manifest.json),
[unchanged kernel identity](evidence/kernel-identity.json), [shared-wrapper pins](dependency-pins.json),
[proposed jobs and commands](WINDOW.md), [retention](RETENTION.md).
Existing packets, shared screen source and live queues were left unchanged.

## When to revisit

The coordinator runs A's four screens, then its exact improving winner on B
between fresh controls. Compare draft acceptance/proposals as well as target
outputs and speed. A both-lane winner can compose with the sealed hc-wide view
and then enter a separately prepared full record chain.

# Packet82b: recurrence round 2

October 18, 2026. CPU preparation only. Arithmetic: `iq3-p49-split32-v1`.
The source snapshot is packet84, with its ordered host cleanup, wide HC,
wide64 experts, production routing/norm/dense/draft head, draft-HC, batch
rollback, rank1 draft and 24/24 target layers. Recurrence control is
packet84's `rec-parallel`. No frozen packet, shared wrapper or live queue is
edited.

## Composition finding

The brief's two packet82 results are separate screens, but their mechanisms
are nested in the implementation. `p82rec::Kernel<false>` puts decay and beta
on separate subgroups. `p82rec::Kernel<true>` already does that **and** separates
Q/K normalization. In its source, the decay role is subgroup2 and beta is
subgroup3; normalization uses subgroups0/1. Adding `rec-gates` again has no
meaningful delta.

`rec-both` therefore resolves to exactly the same `recurrence82<true>`
function and kernel as the production `rec-parallel` choice. It is an honest
null control, not a new candidate or a possible winner. The source equality
and selection mapping are tested. Prior +0.88% and +0.99% measurements must
not be added together. The packet84 composition's device qualification is
separate from this CPU preparation.

## Further serial preparation reduction

Packet82 identified preparation latency inside 1,536 four-row workgroups,
not a shortage of groups. `rec-both-plus` removes the initial guard-only
workgroup barrier and its SLM scalar exchange. Each subgroup's leader reads
the controls and broadcasts a three-way integer decision locally. Preparation
can start without waiting for the other subgroups at this first barrier.
The local allocation shrinks from 259 to 258 FP32 elements. No extra launch,
global scratch, persistent constant cache, state layout or precision changes.

The gate math is already fused into this recurrence launch. Packet67's
separate rec-head prepass remains closed. Hoisting the F32 decay parameter
alone cannot remove the dependent softplus/decay chain. This packet instead
tests a concrete synchronization saving before those independent producers.
Its device benefit is unknown and may be small or negative; extra subgroup
control loads could offset the saved rendezvous. No CPU timing is a speed claim.

## Barrier and control proof

The existing submission dependencies complete all earlier control writers.
Active and position remain immutable throughout one recurrence submission.
The recurrence can write only its sticky error, only for an invalid position.
The production backend constructs an in-order queue in
`single_device.cpp:64–65`; controls live in device allocations and their queued
copies share that order. The host does not asynchronously write these device
control words while the recurrence runs. This proof relies on that engine
contract; it does not permit reuse on independently concurrent control writers.

* For a valid position, there is no error writer in the kernel. Every subgroup
  observes the same active/error values and either all return or all enter the
  unchanged preparation/update loop.
* For an invalid position, every subgroup returns before the first remaining
  barrier. They may observe the old error or the error just recorded by
  workgroup0's leader, but both decisions return. Only that leader may record
  error1, and only if active and no prior error, preserving existing errors.
* Inactive calls and calls with an existing error preserve every state/output
  byte and the existing error. The host fixture enumerates the guard cases,
  including inactive plus invalid and existing error plus invalid positions.

The entire device token-loop body is literal-identical to frozen packet84's
`p82_recurrence.hpp`. Q/K divisions, tree order, gate functions, FP32 operations,
BF16 writes, preparation barrier and inter-token global/local barrier are
unchanged. CPU fixtures compare complete state, output and control bytes after
each of four consecutive calls and a separate four-token call, with both
head mappings and in-place/separate state. CPU execution cannot establish
device subgroup scheduling or device exactness; the pinned v4 screens must.

## Gates and screen decision

GNU and Intel each compile and execute every view twice. Candidate bytes must
match the same-compiler packet84 recurrence control with no tolerance. Existing
cross-compiler NaN payload differences are separately inspected and disclosed.
Offline BMG-G31 compilation must show no scratch spill. Full-size mocked
startup runs both ranks through actual allocation, configuration and operation
capture, with ordered host cleanup and HC-wide enabled. Shared wrapper import,
admission and placement checks run unchanged. Device smoke remains pending.

Both lanes have full-grid proposals and opposite-lane best confirmations,
planned on temporary queues. Each grid is production / rec-both /
rec-both-plus / production. Only rec-both-plus is eligible; it must match all
13 requests and beat **all three** null/production controls. Confirmation is
production / exact improving opposite-lane winner / production, with 90-second
gaps and no retries. These 128-token screens are diagnostic, never final
performance or promotion gates.

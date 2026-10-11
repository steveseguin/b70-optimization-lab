# Packet 24 negative-result and guard index

No device result is recorded here. These are CPU preparation findings.

| Arm or mistake | Outcome and retained evidence | Revisit condition |
|---|---|---|
| Many independent operations forced into one work-group | Replaced in v2 with ordered stages and independent work items. The old schedule remains v1. GPU benefit is pending K2. | Compare exact event execution, not old spans, before choosing a winner. |
| Argmax/gather set sticky error before defined diagnostic outputs | Independent review found output parity differences on invalid values. Fail is delayed until original diagnostic stores complete. [Review](tree-review.json). | Keep invalid-value byte checks when changing guards. |
| Scratch trusted without an allocation extent check | New global scratch requires explicit byte checks at entry; added along with original binding-count guards. [Race review](race-review.json). | No scratch reuse without an owner/event and extent proof. |
| Infer new-kernel fixture coverage from copied snapshot tests | Closed. A separate actual-kernel gate compares all72 inherited cases plus20 odd-width cases against Core and v1. | Every new body must appear in the executed fixture path. |
| K2 clears error before examining previous class | Would time no-op kernels after a failure. Per-class, per-sequence and preparation error checks added. [K2 review](k2-review.json). | Never erase failure evidence during timing. |
| K2 v2 starts from v1's mutated state | Closed using identical deterministic logical-buffer snapshots restored outside each measured class/sequence. | Retain matching inputs and distinguish stateful synthetic repeats from real decode. |
| K2 sums first-to-last span | Closed: store every owned event's command_start/end, sum durations, validate200 distinct repetitions. | Spans remain a separately labeled W2k profile only. |
| CPU sanitizer used default card3 with card-count2 | Harness rejected the range before work; corrected to explicit mock card0. No device or numerical failure. | Explicit mock topology in every CPU command. |
| Native fixture imported host-only Operation type unconditionally | Compile failed; using declaration is now within the host-only guard. No executable ran. | Keep both compiler paths in compile gates. |

K0/JIT build, K1 fresh native owners, K2 timing, W0 and real-model W2/W3/W2k
remain pending coordinator windows. Estimates are not results. Large GEMV changes
belong to [GEMV-NEXT.md](GEMV-NEXT.md), not a silent extension of this packet.

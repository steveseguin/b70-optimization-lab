# Packet 45: merged runtime, CPU qualified

One runtime based on packet44-context at `421a4ab50`, with packet40-suite at
`50d9e0031`, the measured packet42 candidates, packet39 epilogues, and selectable
official draft placement. The target stays the quantized compressed Unsloth
UD-IQ3_XXS release with `iq3-p17-detmath-v2` arithmetic and full BF16 caches.
No device is executed during this task. Predecessor speed numbers are motivation,
not measurements of this merged binary.

Capacities are 256, 4,096 and 32,768. Capacity behavior takes precedence in merge
conflicts. Suite caps come from their bound 32/64/128-token manifests. Fixture
retention and speed-companion binding come from packet40. A 128-token suite can
report the 99-interval metric but cannot satisfy the full 512-cap publication gate.

`--draft-rank 0` selects 22 target layers on rank0 and 26 on rank1; `--draft-rank 1`
keeps the 24/24 split. Rank1 alone chooses emitted tokens. Its final layer streams
return through a separate position-bound slot before its head and argmax.
The draft receives only confirmed input tokens, with private weights, cache and
hidden staging. Wrong target halves are drained, restored and repeated exactly.

[CAPACITY.md](CAPACITY.md) gives both memory plans. [WINDOW.md](WINDOW.md) gives
the coordinator chain. [INTEGRATE.md](INTEGRATE.md) lists the complete merge
inventory against both immutable parents. Gate receipts qualify only their recorded sources and binaries.

The CPU checks include 79 fresh pipeline executions, 854,164 selection checks,
22,326 arithmetic checks across GNU/Intel and all capacities, 6,899 dispatch
validation checks, 3,657 maximum-capacity ASAN/UBSAN checks, six captured draft
arms with 378 frozen-reference matches, 18 owner/lifetime suites, 72 kernel/K2
tests, 101 wrapper tests (78 mocked window combinations), and 65 memory-plan
checks. Normal/ASAN/TSAN controller mocks cover 1,123 cases each; mailbox tests
cover five gates each. Counts overlap where a helper is included in a larger
fixture arm; they are not one summed headline. Real-model correctness subsets
and the final sealed-window admission are separately receipted.

[KERNELS.md](KERNELS.md) gives prior measured per-class savings and explains why
`p42.dense.fourparts` is excluded. [ROLLBACK.md](ROLLBACK.md) describes the reverse
handoff and exact wrong-half discard. [CLOSEOUT.md](CLOSEOUT.md),
[DO-NOT-REPEAT.md](DO-NOT-REPEAT.md) and [ARTIFACT-RETENTION.md](ARTIFACT-RETENTION.md)
retain failures, limitations and restoration instructions. [CPU-REPRO.md](CPU-REPRO.md)
lists the host-only reproduction commands. Device qualification remains pending.

The six real-model CPU cases passed: both draft placements at every capacity,
48 emitted-token matches and 2,304 layer-fixture matches against the fixed
first-prompt oracle. All three same-capacity placement pairs have identical
complete draft-state hashes. All six runs share the same guesses and decision
counts; 17 fixed-size semantic draft buffers match across capacities. Full cache
hashes across capacities are deliberately not compared because their allocated
tails differ. The observed aggregate CPU anonymous-memory peak was
7,942,012,928 bytes. No model process remains from this CPU campaign.

The final [build receipt](build-receipt.json) binds the implementation, 41 linked
artifacts, parent/source pins and all required CPU receipts. The detached
[window admission binding](window-seal-binding.json) binds the unchanged seal to
the no-launch rehearsal. [Binary hashes](BINARY-HASHES.md) identify the exact
compiled artifacts. Neither the CPU seal nor the rehearsal qualifies device
speed, device residency or the full manifest-bound model suites.


The [October 13 HC repair](HC-ACTIVATION-CLOSEOUT.md) explains the first device
chain failure: case 54 is the NaN scenario, not the pre-seeded error scenario
(case 53). A deterministic unary NaN payload rule and six compiler regression
arms close the CPU code-generation gap. The repaired seal supersedes the old
binary identities and requires new coordinator chains. The historical failure
latch and commands are retained unchanged; device qualification is pending.

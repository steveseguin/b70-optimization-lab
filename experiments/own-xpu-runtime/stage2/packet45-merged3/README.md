# Packet 45: merged runtime, CPU qualified

[SPEED7 size-aware snapshot batching](SPEED7-CLOSEOUT.md) preserves the exact
SPEED6 byte sets and arena headroom while bounding batch size spread at 8:1.
Its new binary identity requires fresh coordinator device qualification.

[SPEED5 split23](SPEED5-CLOSEOUT.md) is CPU sealed: 23/25 with draft rank 1 at
4K, with 32K refused below the unchanged reserve. The coordinator owns device
exactness and performance qualification on both card pairs.

[SPEED4 miss-path repair](SPEED4-CLOSEOUT.md) restores 18.13 MiB before a
confirmed 24/24 redo, while retaining the complete 46.36 MiB restore for
terminal rollback. Its new artifact identity needs coordinator qualification.

[SPEED2 write-set repair](SPEED2-CLOSEOUT.md) preserves full-state rollback while
avoiding copies of untouched scratch and QSA tails. Device qualification remains
the coordinator's exact-token responsibility under the named seal amendment.

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
tests, 131 wrapper tests (78 mocked combinations plus 27 actual coordinator
CPU rehearsal windows), and 65 memory-plan
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
7,942,635,520 bytes. No model process remains from this CPU campaign.

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

The [October 14 sequential-owner repair](SEQUENTIAL-OWNER-CLOSEOUT.md) accepts
exactly the five merged fixture owners while retaining every exit safety check.
The owner reports that the NaN repair passed K1a arithmetic on both card pairs;
the host gate then rejected its healthy fifth owner. The [sibling audit](SIBLING-AUDIT.md)
and all three complete coordinator CPU rehearsals now pass. The full CPU suite
was rerun and resealed; all 41 build artifacts, including all five device binaries,
are unchanged. Fresh device chains still need the new host seal.


The [October 14 storage follow-up](STORAGE-ADMISSION-CLOSEOUT.md) removes the
packet38 aggregate 3 GB limit from the merged retention plan without weakening
the 8 GB free-space floor. The new finite ceiling is the 3 GB base allowance
plus a worst-context chain, bounded again by live disk headroom with another
chain reserved. It also fixes context-dependent model-state projections and
makes CPU rehearsal validate the real reserves. [Capacity arithmetic](CAPACITY.md)
and the [whole admission audit](ADMISSION-AUDIT.md) give the exact limits.

The [October 14 route+gather repair](ROUTE-GATHER-CLOSEOUT.md) reproduces K2's
failure on CPU: folded incumbent implementation 0 omitted both gather descriptor
outputs. The retained K2 events stop before rank32 is reached. The repair adds
those stores without changing the unfused reference, route arithmetic or ABI.
The new six-setting compiler matrix executes every registered fusion through
its actual owner submission: 36 failures before, 2,232/2,232 checks after.
The previous HC matrix covered only cases 51–54; the ordinary adapter fixture
never folded implementation 0. The closeout gives the complete fusion audit.
The host rehearsal also now binds rebuilt binaries from the current mode-build
receipt instead of copying stale hashes from the preceding final seal.

The route+gather repair passed the complete CPU suite and all three 9/9
rehearsal chains (4,096 draft ranks 0/1; 32,768 draft rank 0). The new seal
binds 25 gate receipts and 41 primary build artifacts. All five device binary
hashes changed; the ABI is unchanged. All 150 protected incident/device files
are unchanged. No device binary ran; fresh device qualification is required.

The [October 14 copy-extent repair](COPY-EXTENT-CLOSEOUT.md) fixes the next K2
setup failure: P39 tried to upload a complete 268.7 MB expert bank in one
128 MiB-limited copy. It now uses waited 4 MiB slabs. A CPU gate exercises all
eight P39 classes at full production geometry, and a registry-driven sweep
loads every selectable GEMV/attention choice through the actual K2 owners.
The full-size/adoption receipt is required by the coordinator rehearsal and seal.

The [October 15 fix 6 closeout](FIX6-CLOSEOUT.md) records the measured-dispatch P39/small-GEMV composition failure, the plan-local fallback and the 48-row metadata-only plan sweep. Qualification status and build identities are recorded there; prior seals do not qualify changed binaries.

Seal 6: [owner-directed ASAN rebuild and exact fix6 device-oracle amendment](SEAL6-CLOSEOUT.md). Historical CPU results are retained; speed publication requires passing device suite windows.

The [October 15 SPEED1 repair](SPEED1-CLOSEOUT.md) batches the same strict snapshot
bytes into 32/34 submissions and restores small-FFN composition, removing 192
extra target commands. Whole-buffer writer exclusions failed the full-state proof
and remain unimplemented; byte traffic is unchanged. Fresh mini/plan gates and
the named seal-6 extension precede coordinator device qualification.

The [SPEED3 closeout](SPEED3-CLOSEOUT.md) removes duplicate draft profiling and
admits an independent 24/24 target split with drafting on rank 0 at 4K only.
It includes exact coordinator commands, fresh mini/plan/event/admission gates,
forecasts and the new seal hashes. The 32K version of that split is refused.

The [SPEED6 closeout](SPEED6-CLOSEOUT.md) repairs pre-launch arena admission and
bounds operator scratch for 23/25 dr1 at 4K, with production-size sparse checks,
mini full-state gates, the new seal identity and both-pair coordinator commands.

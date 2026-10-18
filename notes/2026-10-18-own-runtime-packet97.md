# Packet97: compose the in-flight exact choices

The new bundle copies packet91 and adds the packed target head, reply-first
reporting, HC norm fusion, expert grid prefetch and exact half-scale cache.
Grid prefetch and the half-cache compose in one kernel. H1 remains closed.
The recorded frontier is still packet84's 55.68696298163401 tok/s; this work
contains no new device result.

The GNU and Intel builds pass. Each compiler passes two fresh byte repeats for
every changed operator, including the combined expert path and reply-first
state/error cases. The 128 selectable compositions bind those raw operator
transcripts. All 256 full-size startup checks pass, including actual allocation
and VRAM admission on both ranks, with model payloads/backend mocked only.
The packed target head's separate expanded draft prefix is included.

The compiled composition and CPU proof were committed and pushed as
`3566f04a0`. All 128 selections are now sealed. The largest composition and the
restored baseline both pass the complete CPU chain rehearsal, including window
plans and submission consumers. The packet tests pass 276 tests and 136
subtests; orchestration passes 29 tests. Both lane proposals pass planning on
temporary queue copies: six control/candidate/control jobs in total.

The orchestrator reads both directions through each source compare module.
The final snapshot rejects packet91's A screen with the source comparator's
`unfinished/failed screen` verdict; its B grid and the other five sources remain
pending. Readiness is false. The full-chain disk check also remains false:
15,752,671,232 bytes free versus 18,812,225,206 required, a 3.06 GB shortfall.
The CPU build uses 334,579,274 bytes. No storage reserve was lowered and no
unrelated evidence was deleted. A fresh invocation rechecks current evidence.

Tests cover invalid evidence, revert-only pins, closures, both comparison
directions and the packet84 temporary-path regression. The submission tool
already passes the frozen receipt bytes as `data=` and discloses the packed
target head's separate expanded draft prefix. These tools were finalized before
the final seals. No GPU, service, live queue, frozen tree or host setting was
changed by this work.

Commands and evidence are under
`experiments/own-xpu-runtime/stage2/packet97-record-bundle/evidence/`.
Build commands use nice 19, cores 8–15/24–31, stdin /dev/null, the packet94 compile
turn guard and an 8 GiB address-space cap. Root remains above 12 GB free; build
scratch is well below 1.5 GB. Each fixture scratch directory is removed after its
verified raw transcript and case log are archived.

The largest composition leaves 4,225,394,604 bytes of arena headroom on rank0
and 639,463,734 on rank1. Rank1's planned free VRAM is 2,669,506,870 bytes,
above the unchanged 1.5 GB floor. The minimum arena headroom across every
selection is 630,519,094 bytes on rank1 (half-cache without the packed head).
These are allocation/admission checks, not measured device memory use.

Final receipts: [CPU verification](../experiments/own-xpu-runtime/stage2/packet97-record-bundle/evidence/final-verification.json),
[closeout](../experiments/own-xpu-runtime/stage2/packet97-record-bundle/CPU-PREPARATION-CLOSEOUT.md),
[orchestration instructions](../experiments/own-xpu-runtime/ops/packet97-orchestration/README.md).
Proposals: [lane A](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p97-A.txt)
and [lane B](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p97-B.txt).
The current templates refuse execution. Once source decisions resolve, the
helper writes the confirmed selection and fresh output paths, then plans the
actual jobs. Full-model oracle equality, device determinism and speed remain
future gates; the CPU byte evidence is a factorized operator proof.

The requested initial `git pull --rebase` refused unrelated dirty work. A fetch
showed main equal to origin/main; no unrelated file was stashed or overwritten.
A read-only subagent reviewed orchestration while the existing GPU job ran,
as AGENTS.md directs. All implementation and compilation remained serial here.

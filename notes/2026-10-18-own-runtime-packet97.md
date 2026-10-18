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

The first milestone is the compiled composition and CPU proof. Seals, queue
plans and the final chain rehearsal are being completed next. The new
orchestrator already reads both directions through each source compare module;
its snapshot reports all six sources pending and readiness false. Tests cover
invalid evidence, revert-only pins, closures and the packet84 temporary-path
regression. No GPU, service, live queue, frozen tree or host setting was changed.

Commands and evidence are under
`experiments/own-xpu-runtime/stage2/packet97-record-bundle/evidence/`.
Build commands use nice19, cores8–15/24–31, stdin /dev/null, the packet94 compile
turn guard and an8GiB address-space cap. Root remains above12GB free; build
scratch is well below1.5GB. Each fixture scratch directory is removed after its
verified raw transcript and case log are archived.

The requested initial `git pull --rebase` refused unrelated dirty work. A fetch
showed main equal to origin/main; no unrelated file was stashed or overwritten.
A read-only subagent reviewed orchestration while the existing GPU job ran,
as AGENTS.md directs. All implementation and compilation remained serial here.

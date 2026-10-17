# Packet60 integration note — October 17

The coordinator accepted three kernels per HC side: norm; low plus inject;
gate plus mix. This replaces the earlier request for one kernel per side.
The decision is recorded here under the explicit own-folder edit scope;
`notes/2026-10-17-own-runtime-packet60.md` remains the earlier dated history.
There is no remaining permission question about the launch topology.

The packet56 engine copy dispatches both target HC sides through this path.
The preceding residual still completes before the norm, and layer-end hooks
retain their labels. The draft is untouched; packet59 owns that work.

The requested initial pull refused because another job had staged work.
A read-only fetch showed no incoming commits. No other job's index or files
were stashed, reset, edited or committed as part of this packet.

The parent's compiled objects had been reclaimed. The local builder therefore
recompiles those unchanged inputs inside packet60 from the verified parent
mirror, with the same flags. An initial link attempt found the missing objects
and stopped before linking; no binary ran on a device.

All compilation and CPU fixture work use nice19, cores 8–15/24–31 and Python
with `-B`. No GPU, model payload, sudo, service, signal, power, host memory,
swap, page-cache change or reboot is part of this task. Device A/B belongs to
the coordinator. Speed and full-model device equality remain unmeasured.

Integration review retained the common BF16-writer invalidation after the new
HC hook, so cached FP32 input descriptors cannot survive an HC write. The
integrated fixture checks that edge as well as prepared capture counts.
An initial test import also imported the primitive fixture's main function;
a data-only include guard now shares just its data and production reference.
The first integrated run passed but its Python reader expected JSON-only
stdout. The lifetime backend prints teardown messages first; the reader now
reads the final JSON report. These were CPU harness fixes, not device results.

The first screen seal correctly refused the parent's external build symlink.
Packet60 now retains exact compiler-input snapshots under
`evidence/inherited-build-inputs/`, with original paths and hashes in the build
receipt. The builder verifies the originals before compilation and both sides
of each snapshot after linking. This keeps the screen's path guard intact.
The linked engine consumes those compiled bytes; its runtime RoPE and draft
manifest remain separately bound repository files. No parent path was changed.

Final CPU checks passed: 878,040 compared bytes, 96 target layer fixtures and
24 tokens. The diagnostic seal and `screen.py --plan` both pass. No GPU ran.
Repository hygiene reports no errors; the one 12.58 MB compiler-input snapshot
has an explicit retention record. Four inherited mirror lines retain their
original trailing whitespace to preserve the sealed bytes; authored source
changes pass the whitespace check.

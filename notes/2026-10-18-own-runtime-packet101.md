# Packet101: re-test the remaining draft attention option

Packet97 already uses all fourteen settings in packet69's draft-HC view, with
the same HC kernel bytes. That arm is closed as a duplicate. Its split32 draft
attention is still disabled in packet97's baseline, so packet101 prepares that
one remaining candidate using copied packet97 sources and unchanged binaries.

The old +0.82% `combined` result included target and draft wide64 heads as well
as attention and HC. It cannot be described as attention-plus-HC alone. Those
heads are not imported. The current head paths already use the correct
3,380-byte storage stride, including the separate expanded draft prefix when
the target head is packed. The old HC cost is not used to forecast a new gain.

Four views are sealed: `control`, `draft_attention`, `draft_hc` and `combined`.
HC is an explicit control alias; combined is an attention alias. The proposed
B job file has only control / attention / control, with the same A mirror.
Records run on A. One exact first-lane win over both controls qualifies this
source for composition; all thirteen outputs and every prompt's hit/guess
counts must stay unchanged. There is no 1.5% source cutoff. Device results and
record readiness remain pending.

CPU validation passed:

- Both GNU and Intel pass two fresh 88-case linked attention runs and two HC
  runs. Raw bytes agree between compilers. Split32 is checked against its own
  fixed reference arithmetic, not falsely labeled equal to the old draft tree.
- Both ranks pass every one of 256 selections: packet97's 128 compositions
  crossed with both attention choices. All 512 runs execute actual full-size
  startup, allocation, draft construction and command capture, mocking only
  model payloads and the backend. Draft-specific operation counts prove that
  the intended attention path and all three existing HC mixtures are reached.
- Four short/misaligned-head refusals and eight Python tests pass. All four
  seals and all six queue plans pass; planning used temporary queue copies.

Preparation exposed two Intel link-driver problems, repaired with PIE flags
and the matching Intel linker driver while retaining GNU OpenMP for inherited
objects. A serial-mode refusal fixture failed because serial startup is not
itself rejected; that generic fallback was not counted as a passing gate.
The logs are retained. No runtime behavior was patched to bypass a failure.

Build scratch was below 300 MB. Cleanup removed test binaries and objects,
leaving 64,755,902 logical build bytes, including the reused runtime binaries.
No GPU, service, sudo, settings, live queue or existing packet tree changed.
The opening `git pull --rebase` refused unrelated staged and unstaged work.
A fetch showed no incoming commits; unrelated work and concurrent commits
were preserved without stashing, branching or creating a worktree.

[Packet handoff](../experiments/own-xpu-runtime/stage2/packet101-draft-geometry/README.md),
[source audit](../experiments/own-xpu-runtime/stage2/packet101-draft-geometry/evidence/source-audit.json),
[CPU closeout](../experiments/own-xpu-runtime/stage2/packet101-draft-geometry/CPU-PREPARATION-CLOSEOUT.md),
[do-not-repeat entry](../experiments/own-xpu-runtime/stage2/packet101-draft-geometry/DO-NOT-REPEAT.md),
[B proposal](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p101-B-grid.txt),
[A mirror](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p101-A-grid.txt).

# Bound lifecycle callback: real CPU compiler capture

Status: **one bounded CPU capture case passed; no GPU speed result.**
This follows the [25-check lifecycle gate](ltx-block-compile-pre-run-lifecycle.md).
That earlier gate used a dispatch spy and explicitly left compiler interaction
with the new lifecycle object unqualified.

The [new helper](../scripts/test-ltx-bound-lifecycle-capture.py) applies the
unchanged ownership guard followed by lifecycle v2 in temporary source storage.
It selects block 24 in the original registered shard layout, invokes native
`ModelPatcher.pre_run`, and supplies actual route, callback and wrapper registries
to the block. The callback registry contains the real lifecycle guard, including
its registered owners and successful executing-patcher weak reference. A
per-forward transfer cache also contains retained source/destination tensors.
No metadata or compiler guards are filtered away.

The tiny native BF16 block uses 64 video tokens, 26 audio tokens, 32-wide
channels and seed 17. The eager argument mapping comes from the frozen native
`block_wrap` AST. Real Inductor execution and a second execution both match the
eager video/audio output bytes exactly and remain finite. Native cleanup clears
the executing patcher afterward.

The [receipt](../data/ltx-bound-lifecycle-capture-cpu-01.json) and
[log](../data/ltx-bound-lifecycle-capture-cpu-01.log) record six passing checks,
one compiled graph, 493 captured operations, one successful AOT compilation and
zero graph breaks. One compiler worker and one CPU thread were used, with the
same rounding-preservation options as the earlier compiler gates. Peak parent
RSS was 1,141,888 KiB; compiler-subprocess peak memory is not summed into this
figure. The process exited successfully. Source hashes recorded before import
still match the files after completion; temporary compiler caches were removed.

This is one synthetic CPU component case, not native checkpoint qualification,
the second-stage shape, masked/altered branches, cross-XPU execution, a full
clip, or a performance measurement. Those limits remain explicit. The helper
preserves the earlier interrupted experiment and both lifecycle source versions;
it does not alter the candidate's numerical code or restart any server.

## Next action and pending decision

The prepared encoder GPU screen is the next measured speed experiment. Its
actual copied launcher again passed `--check-only`. The
[post-check state](../data/bound-capture-postcheck-state.json) confirms the
unchanged manifest, original PID24848/start ticks, empty queue, absent fault
latch and absence of a replacement run directory. The
[concrete launch and 25-request comparison](encoder-runtime-v2-ready.md) remain
ready; compiler work is separate and is not added to that immutable packet.

The user decision requested before replacing the running server is still
pending. It has remained pending across the routed CPU, lifecycle CPU, and
bound-capture goal turns. Those turns produced useful evidence; they have not
advanced the measured 6.515-second median baseline. Further local source work
cannot establish a GPU speed gain or replace the next controlled comparison.
The goal is now waiting on that decision rather than cycling through more
preparatory checks. This is not a conclusion that the subsecond objective is
impossible or achieved. No automatic continuation is treated as approval.

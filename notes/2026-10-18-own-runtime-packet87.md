# Packet 87: can the first card help with either head?

**No seal-ready design from the available receipts.** The CPU model shows room
for both splits, but the new device-copy costs are not measured. The old copy
timers report zero-width timestamps; treating that as free transfer would make
the result look better than the evidence supports.

The [closeout](../experiments/own-xpu-runtime/stage2/packet87-slack-model/DECISION.md)
contains the hit and miss chains, row boundaries, transfers, tie rules and
remaining budgets. The [JSON](../experiments/own-xpu-runtime/stage2/packet87-slack-model/DECISION.json)
and [CPU model](../experiments/own-xpu-runtime/stage2/packet87-slack-model/model.py)
retain the calculations and input hashes.

After charging the measured host boundaries, but before the unknown device-copy
costs, splitting the target at row **201,728** predicts **54.690 tok/s (+1.08%)**.
Splitting the draft prefix at row **46,080**, on hits only, predicts
**54.524 tok/s (+0.77%)**. These are optimistic forecasts, not measured gains.
In that scenario every modeled miss improves with the target split, and misses
are unchanged with the draft split. A few low-slack hits get slower with the
target split; the calculation keeps them.

There is a small baseline identity correction: packet85 called **54.064 tok/s**
the control, but that root summary belongs to the instrumented run. The actual
control receipts and control summary give **54.107 tok/s**. Packet87 uses that
matching control and leaves packet85 unchanged.

To remain above +0.5%, the target split can afford about **52.6 microseconds**
of unmeasured work on each of three transfer legs; the draft split can afford
about **25.3 microseconds** each, with its row boundary adjusted. These are
budgets, not proof that the transfers are fast enough. Reopen after an actual
end-to-end transfer measurement; this packet schedules no GPU work.

Validation: the model reproduces packet85's components from all 1,188 control
intervals, checks shared input hashes, searches every 256-row-aligned split,
recovers the exact control rate with no split, and verifies the nominal miss
effects on all 252 misses. Its `--check` command requires byte-identical JSON.
All Python runs use `nice -n 19`, `taskset -c 8-15,24-31`, `python3 -B`, and
stdin `/dev/null`, with the inherited 4 GiB address-space ceiling.

Only the new packet87 folder and this requested note were written. No engine
code, GPU, service, queue, sudo, settings or reboot was used. All existing
runtime and evidence trees, including `CURRENT.md`, stayed frozen.

The opening `git pull --rebase` refused the pre-existing unstaged work.
`git fetch origin main` then confirmed local and remote main were identical.
No stash, branch or secondary worktree was created; unrelated work was preserved.

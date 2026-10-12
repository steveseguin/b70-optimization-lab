# Packet38 integrated runtime

CPU preparation is sealed: 91 gate receipts passed. No device ran and no model
speed is claimed. The persistent native/MTP CPU suite matched all 192 tokens
and 1,152 retained fixtures for its three-prompt snapshot. The complete twelve-
prompt device suite remains coordinator work. See [CPU-RESULTS.md](CPU-RESULTS.md).

The runtime merges packet36's official draft provider into packet37's prepared
host path and packet33 kernels, against their common packet32 base. The target
is the quantized compressed Unsloth UD-IQ3_XXS release; arithmetic stays
`iq3-p17-detmath-v2` and KV/state stay full BF16. Draft-only expert weights use
the same official-head 8-bit requantisation as packet36. Target rank1 alone
chooses emitted tokens. Packet39 remains a disabled dispatch hook.

`--controller python` retains the reference. `--controller native` starts one
request through the existing sockets, then rank0 schedules both halves directly.
Rank1 consumes a shared-memory sequence mailbox with release/acquire publication
and process-shared futex wakes. There is no spin. Waits check cancellation every
10 ms and have an absolute deadline. Python supervises both ranks, the kernel
journal and the stop pipe. Failure receipts precede teardown; nothing retries.

The suite starts the ranks once, warms kernels, then resets all mutable target
and draft state in place between requests. Rank-local HOME directories under
build retain driver cache files; their presence is reported without pretending
it proves a driver cache hit. Each request writes tokens, eight fixture steps,
timings and acceptance. Read-only suite_check.py checks exact bytes. Exactness
failures are recorded while remaining requests run. A runtime fault stops the
window. See [SUITE.md](SUITE.md), [ROLLBACK.md](ROLLBACK.md).

[KERNELS.md](KERNELS.md) describes model-shape K2 coverage. [WINDOW.md](WINDOW.md)
lists coordinator commands; [DEADLINES.md](DEADLINES.md) separates estimates from
watchdogs. Build/gate authority is [build-receipt.json](build-receipt.json).

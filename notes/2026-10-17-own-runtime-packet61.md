# Packet61 — controller spin plus HC fusion

October 17, 2026. CPU preparation on steve-b70s is complete. The combined
candidate is built and sealed; the coordinator can run its screen and full
chain. No GPU or service ran in this task, and no packet61 speed is claimed.

Packet61 keeps packet56w's 250 µs spin and rank-0 queue profiling property and
uses packet60's exact three HC kernels on both target sides, including both
serial M=2 rows. The draft prefix remains 91,392 rows. The full target, BF16
intermediates, BF16 KV and packet49 oracle are unchanged. Kernel sources and
reused HC object bytes are identical to packet60; the controller and device
wait sources are identical to packet56w.

Both builds pass. The CPU checks match 878,040 HC bytes, all 96 target fixtures
and 24 tokens against packet56. All 1,123 controller cases, five mailbox fault
cases and 31 chain/submission checks pass. Screen v1 and v3 both accept the
seal. The full chain plan verifies the oracle and the two parent prefix
windows. Storage passed with about 4.65 GB above its required reserve; the
coordinator must recheck before launch.

The build uses about 143 MB logically, about 108 MiB allocated with hardlinks,
below the 400 MB cap. Packet56x was not sealed when integration began around
15:15 UTC, so its later wait variants are left out. `wait-option.json` records
a clean extension point and keeps packet56w waits fixed. No shared screen,
packet56x, cleanup, CURRENT.md or sealed parent file was edited; the explicit
own-folder scope takes precedence for this handoff, apart from this requested
note. The initial pull rebased main successfully; later concurrent main
commits remain intact.

The submission helper reads `scripts/packet49_record_threshold.json` and
requires a rate above its current floor, 46.96269702286488 tok/s at preparation.
Payload notes name the prefix, spin/queue property and HC fusion. A full chain
is still required. The 128-token scope remains explicit and the strict
512-token gate remains false. No dry-run, API call or submission was sent.

The initial compile failures were local harness issues: a missing `.inc`
copy, colliding object basenames and two checked-header trees included in the
same fixture. They were corrected before sealing. The passing fixtures and
commands are retained in the packet, along with its CPU closeout.

- [Packet and all receipts](../experiments/own-xpu-runtime/stage2/packet61-spin-hcfusion/README.md)
- [Exact screen and chain commands](../experiments/own-xpu-runtime/stage2/packet61-spin-hcfusion/WINDOW.md)
- [Submission commands](../experiments/own-xpu-runtime/stage2/packet61-spin-hcfusion/SUBMISSION.md)
- [CPU closeout](../experiments/own-xpu-runtime/stage2/packet61-spin-hcfusion/CPU-PREPARATION-CLOSEOUT.md)

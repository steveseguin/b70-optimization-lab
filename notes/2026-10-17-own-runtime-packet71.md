# Packet 71 — dependent depth-two engine

The owner requested a CPU-only engine packet, with device windows owned by the
coordinator. Frozen packet64–70, screen and ops trees are read-only inputs.

Design milestone: [design](../experiments/own-xpu-runtime/stage2/packet71-depth2-engine/DESIGN.md).
The updated optimistic cost model reaches +8% at H2/H1 <=1.56037; allowing one
extra draft/repair step tightens that to approximately 1.42. Neither is a speed
measurement. Serial fallback, causal state gates, device commands and copied
packet68c integration remain in progress.

Initial free space was 17 GiB. `git pull --rebase` refused the coordinator's
dirty ops log/readiness files. `git fetch origin main` confirmed HEAD and
origin/main identical (0 ahead/0 behind); no stash or edit of those live files.
No GPU, service, model load or host-setting change was run.

Serial fallback milestone: GNU host and Intel device compilation pass without
opening a device. Three small synthetic four-layer prompts (8, 11 and 32 output
tokens) match the packet64 executable with all three acceptance cases forced.
All **1,854** final plan/spare-bank byte comparisons pass, including the QSA
extent boundary. The recursive draft path also emits the parent target tokens.
This is small-engine correctness evidence; full-model device identity is pending.

The first controller overlaps rank0's proposed pair with rank1's current row,
then drains to resolve the pair. It is screenable but carries extra copying and
bubbles, so the optimistic two-token pipeline model must not describe its speed.
The copied packet70 wrapper releases drained lane leases before reporting.
Smoke and matched control/candidate/control jobs are in the packet README.
The control uses packet64's sealed `1-draft-hc-batch` view: its top-level screen
seal is stale after the record bundle was selected. That failed CPU plan is
retained and no device ran. Build is approximately 93 MiB; free disk about 17 GiB.

Final integration milestone: the controller now pipelines two dependent rows
per half. Rank0 owns separate current and future tiles; the future starts from
the current tile's private second-row state. Rank1 verifies the current tile
while rank0 computes the future. A rejection discards the appropriate private
tile and copies only the accepted prefix into canonical state. Recursive draft
proposals restore their private changes before any confirmed advancement.

Packet68c sources were copied byte-for-byte and pinned in
[the import manifest](../experiments/own-xpu-runtime/stage2/packet71-depth2-engine/packet68c-import.json).
Nine classes select production-derived M2, prioritizing routed experts. The
production model includes IQ3 expert shapes unsupported by those M2 kernels;
these keep production M1. Other classes remain serial, including causal QSA and
GDN recurrence. The all-M1 seal uses the same final pipelined engine.

The final binary passes all nine forced-acceptance fixture cases (8, 11 and 32
tokens), **1,854** plan/spare comparisons, both-bank extent/history/lookup
metadata and **five** draft-cache comparisons. GNU and Intel each pass **1,428**
operator byte checks, with matching bytes across compilers. Seven wrapper tests
pass, including the exact 32-token smoke and lease release before reporting.
Retained production metadata validates supported M2 shapes and explicit serial
fallbacks. Host and device compilation pass; neither invokes a GPU.

The CPU gates exposed stale per-row lookup metadata and an extent/bank-swap
ordering error; both were fixed before the final passing run. Mixed IQ3 experts
also required per-site fallback rather than assuming one type per class. The
serial milestone and failed/intermediate logs remain available as described in
[retention](../experiments/own-xpu-runtime/stage2/packet71-depth2-engine/RETENTION.md).

The ideal analyzer's +8% threshold is H2/H1 <=1.56037; reserving another 2.38 ms
gives <=1.42498. The actual engine runs three draft passes per tile and incurs
copy/repair costs, so these are sensitivities, not an engine speed prediction.
The build occupies 125 MiB and free disk is about 30 GiB. No frozen tree, host
setting, service or GPU job was changed by this work.

Coordinator handoff: [exact commands and jobs](../experiments/own-xpu-runtime/stage2/packet71-depth2-engine/README.md),
[CPU preparation closeout](../experiments/own-xpu-runtime/stage2/packet71-depth2-engine/CPU-PREPARATION-CLOSEOUT.md).
Run the lane-B smoke first, then control/candidate/control quick screens. Full
packet49 device identity and any speed gain remain unmeasured.

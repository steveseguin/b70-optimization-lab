# Packet122: draft time before the target halves

The fresh complete-draft probe compiles and its two proposed lane-B jobs pass
the coordinator planner on a temporary queue. No GPU or service ran here.
The live queues and frozen packet sources are unchanged. Pull refused the
unrelated dirty tree; fetch confirmed HEAD equaled origin/main at c21b6000f.

The probe uses packet118 bundle7, including the fixed 80,128-row prefix and
packet101 attention. It measures all prepared draft events at context 128 and
4096 in two fresh processes. Each measured replay checks all mutable bytes
against a second unchanged replay. Initialization, uploads and readback are
outside the event sums. The 150 real hidden/token inputs come from the sealed
host reference capture; context fill cycles them, so this is not a natural
4K prompt measurement. Expected duration is about two minutes per process,
with a 1,200-second watchdog; actual runtime remains unmeasured.

Proposal: [budget B](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p122-draft-budget-B.txt).
[Build and temporary queue evidence](../experiments/own-xpu-runtime/stage2/packet122-draft-budget/evidence/).

Next: finish the byte/roofline table and the independent exact HC gate schedule.
The old HC fusions are already selected. The new mechanism maps all four streams
of a column into one subgroup, removes the shared-memory barrier and computes
independent sigmoid products in parallel, while retaining chain/reduction order,
BF16 boundaries and ordered four-stream addition. It must cut the affected
classes to at most 0.8 of production in both fresh processes before v5 can run.

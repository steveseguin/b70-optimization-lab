# Packet122 fresh draft budget

CPU-compiled, device execution pending. The coordinator proposal is
`../../ops/lane-queue/proposed-p122-draft-budget-B.txt`: two fresh lane-B
processes, one complete packet118 bundle7 draft step, context 128 and 4096,
10 warmups and 40 measured replays each, all mutable allocations byte-checked.
The head remains 80,128 rows. Every prepared draft event is counted, including
MTP, merge/norm, prefix and argmax. Transfers and setup are outside event sums.

Inputs are 150 hash-checked target hidden states and confirmed tokens from the
registered iq3-p49-split32-v1 host reference capture. Long-context cache fill
cycles these real captures; it is a diagnostic replay, not a natural 4K prompt.
The official draft weights and target head/embedding are loaded with the
existing authenticated readers. No target layers or server are loaded.
Expected runtime is about two minutes per process (unmeasured); watchdog 1200
seconds. The wrapper retains lane reservations, fault checks, physical card
masking, host memory admission, pre-exec getrlimit checks and the drain fix.
Only the coordinator may execute it. No live queue was edited.

CPU entry: `nice -n 19 taskset -c 8-15,24-31 python3 -B build_budget.py </dev/null`,
then `queue_plan_budget.py` with the same prefix. Other copied preparation
scripts are provenance, not packet122 entry points. Runtime wrappers never
install CPU caps. Build inputs/objects are hash bound; frozen parents read only.

The candidate and its conditional v5 bracket live separately in
`../packet122-draft-hc/` so their preparation cannot invalidate this probe.

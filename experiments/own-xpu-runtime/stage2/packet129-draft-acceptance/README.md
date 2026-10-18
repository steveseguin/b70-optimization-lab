# Packet129: faithful draft-expert acceptance diagnostic

CPU-prepared; device acceptance is pending. The single candidate uses publisher
FP8 expert codes and BF16 block scales, decoded without INT8 requantization.
Production bundle7 still supplies every actual draft guess. The target,
verifier, BF16 KV, 24/24 placement and 80,128-row head prefix are unchanged.
[Format audit and costs](FORMAT-AUDIT.md).

The shadow starts after attention and routing, where the expert-only change
first matters. It uses the same expert inputs, routes and pre-FFN streams,
then recomputes the suffix through argmax. Attention cache updates precede the
changed experts and cannot depend on them in later draft calls: each call
receives fresh confirmed target streams. Every production mutable allocation
is restored and checked byte-for-byte before its guess is published.

Only ten selected experts are staged, costing 49,920,000 extra device bytes.
The diagnostic pays tensor authentication, uploads, a second suffix and full
restoration checks. Its times are not performance evidence. A production
implementation could retain the packed FP8 bank and use fewer bytes than INT8,
but that implementation is conditional on this acceptance gate.

Ten independent inputs use the first and last 128 tokens from packet114's five
pinned general documents. Each generates **up to 128 tokens with natural EOS**.
All ten requests count; none may be selected or replaced after results. At least
512 verified proposals are required for a decision. The candidate must improve
pooled acceptance by **at least 1.5 percentage points**. Otherwise close it.
The twelve fixed suite prompts run second, as a separate report and exact target
oracle check; they cannot rescue the independent gate or tune the candidate.

The coordinator entry is
[`proposed-p129-accept-B.txt`](../../ops/lane-queue/proposed-p129-accept-B.txt).
It runs one lane-B load, about **15–30 minutes** estimated, with a **7,200-second
watchdog** (four times the upper estimate), cooperative teardown and unchanged
live admission. This estimate includes conservative diagnostic overhead and is
unmeasured. No automatic restart or retry is registered. CPU planning uses a
temporary queue directory. No live queue is changed here.

Only this acceptance proposal is prepared. If it passes, the next separate
packet must implement resident FP8 draft experts, rerun GNU/Intel exact bytes,
new-draft KD host references, all-window/whole-queue gates on the packet124c
pattern, memory/residency gates, and a sealed one-load v5 timing bracket.
No acceptance result, speed gain or adopted format is claimed now.

CPU reproduction uses `nice -n 19 taskset -c 8-15,24-31`, `python3 -B`,
`OMP_NUM_THREADS=2`, and stdin `/dev/null`. `cpu_prepare.py` applies the 8 GiB
cap only in its CPU main process. Run `build_engine.py`, then `cpu_prepare.py`
with `cpu_gate.py full_shape.py format_gate.py reset_gate.py test_acceptance.py
test_drain_fix.py`; run `seal_view.py`, `cpu_prepare.py argument_gate.py`, and
`queue_plan.py`. `prepare129.py` records the one-shot derivation and is not an
ongoing preparation command. Never run the device binary from CPU preparation.

The original oracle symlink is preserved. The real oracle CLI, real worker
argument assembly and production-shape parser are checked on CPU. Target
arithmetic objects are reused by exact hash. [Evidence](evidence),
[work note](../../../../notes/2026-10-18-own-runtime-packet129.md).

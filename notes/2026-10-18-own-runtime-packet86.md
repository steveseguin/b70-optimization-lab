# Packet86: measure expert and HC limiters without claiming exact output

CPU-only preparation for a diagnostic screen. The new packet copies packet75's
bundle sources and applies packet77's observation harness. It changes expert
decoding, lookup, repeated-expert addressing and HC scaling on purpose. Every
view is labeled `diagnostic_nonexact: true`; no view is eligible for a bundle,
chain, submission or headline. Production stays byte-identical.

[Packet and evidence](../experiments/own-xpu-runtime/stage2/packet86-limiter-diagnostic/README.md).
[Commands and queue proposals](../experiments/own-xpu-runtime/stage2/packet86-limiter-diagnostic/WINDOW.md).

Eight views share one device binary: production, the five requested ablations,
and two exact controls that retain otherwise-unused loads. Those extra controls
separate changes in compiler load lowering from lookup/dequantization effects.
Original multiply/add order, shape, allocation, KV and safety checks remain in
place. The onecached arm keeps the route validity checks while reading expert 0
for each slot. It tests repeated addresses; cache residency is not established
without a device measurement.

Both builds pass. Production, control and two fresh instrumented miniature runs
match packet75's 96 target fixtures, 24 tokens, proposals and draft state. GNU and
Intel operator tests pass twice each, including expected changed outputs and
invalid-route rejection. All sixteen full-size startup cases pass, including
real preparation, post-load allocation and unchanged memory admission. They use
synthetic device addresses, read no weights and execute no model arithmetic.
Eight Python tests cover actual promotion-path refusals, mismatch classification,
length/protocol failure, full 25-request worker/drain behavior, report aggregation
and identity rejection. Both temporary lane queue plans pass all eight views.

The shared v4 wrapper remains pinned and unmodified. Its quality check correctly
refuses non-exact results after safety postflight and lock release. The adapter
retains that refusal and emits a separate diagnostic completion; it recognizes
no other failure as success. It never invents a passing exactness result.

The report generator will show sampled per-site ms per half against production,
with signed raw-byte, lookup, remaining-decode, repeated-address and HC-scale
ablation bounds. It preserves missing samples and negative deltas. Those bounds
are not additive and do not establish an achievable lossless optimization.
**New device times and achievable savings are unmeasured.** Historical packet77
costs and packet85's model remain separately attributed.

`git pull --rebase` was attempted first and refused because other active work was
dirty. Fetch confirmed no incoming main commits at that point; that work was
neither stashed nor modified. Subsequent focused commits from other operators
were preserved. Work remained on main. Initial compile/env/collector fixes and
byte-verified earlier seals are retained in the packet's retention record.

No GPU, service, sudo, model payload, host setting, live queue or unrelated process
was touched. Proposed lane B and equivalent A files are the only new ops files.
The coordinator's next action is the lane-B diagnostic screen after normal
admission. No further exact expert build is justified by these CPU checks alone.

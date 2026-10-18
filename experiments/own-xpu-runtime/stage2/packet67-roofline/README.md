# Packet67: non-expert roofline candidates

CPU preparation is complete; device correctness and speed are pending. This packet copies packet64's sources and keeps the `iq3-p49-split32-v1` target, packet49 oracle, BF16 state/KV, 24/24 placement and all expert/draft choices. It does not change any frozen packet. [Roofline accounting](ROOFLINE.md), [machine-readable inventory](roofline.json), [all-layer types](all-layer-bytes.json).

The audit changes the priority: QKV/Z/Q-gate already deliver about 500–511 useful GB/s. Recurrence and HC gates have more room. Multi-kernel labels must be summed before taking medians: attention costs about 46 µs, and route about 19 µs, rather than their mixed-stage event medians. Route needs a separate study of the existing packet54 path and is deferred.

| View | Changed sites | Mechanism | Planning saving, µs/half |
| --- | --- | --- | ---: |
| production | none | packet64 choices | 0 |
| hc-a | hc.a.gate | four streams per subgroup; four mixed outputs per workgroup | 87 |
| hc-f | hc.f.gate | same geometry for FFN HC | 87 |
| rec-head | gdn.recurrence | normalize q/k and calculate decay/beta once per head | 108 |
| combined | all three | both mechanisms together | 281 |

These numbers are **planning budgets, not predictions or measurements**: 20% of the rank0 useful-byte excess, rounded. Packet65's weak transfer from microbenchmarks motivates this conservative budget. Zero gain or a regression remains possible; combined effects need not add. The real-composition screen decides whether an arm proceeds.

`p67_hc.hpp` retains each dot's original product/accumulation order, adjacent reduction tree, BF16 gate rounding, stream order, initial +0, and final divide by four. Each physical lane carries four original logical leaves. Four stream leaders calculate independent sigmoid/product terms, then lane zero adds them in original order. Non-finite activations take the unchanged logical-SG32 calculation because the first virtual-tree implementation changed NaN payloads. No NaN tolerance or canonicalization is permitted.

`p67_recurrence.hpp` moves duplicated head work to a prepass. The update still performs the same four sequential products per lane and adjacent tree32 reduction, with the same BF16 state stores. Its 49,920-byte FP32 scratch fits the existing arena; the rollback writer bound includes it. Scratch bytes intentionally change, but output and persistent model state must not. Two kernels replace one; this extra launch is a cost to test, not a launch-fusion claim. The existing one-row submission supports serial M2 calls; multi-token calls are rejected.

The five sealed views share one device binary and strict per-site `choices`. The production recurrence selector still delegates to the existing recurrence choice. Unknown keys/values and identity mismatches fail closed. [Build receipt](build-device-receipt.json), [seals](selections/production/screen-seal.json), [offline compiler report](register-report.json).

CPU gates compare 60 fixtures in each of two fresh runs under GNU and Intel: 240 cases total, 73,402,872 bytes per compared stream/run and 18,432 raw FP32 HC leaf checks per run. They cover both HC sites, finite/cancellation/subnormal/NaN/Inf inputs, guards and invalid calls, both recurrence mappings, F32/BF16 bias, distinct state banks, consecutive tokens and the 4095→4096 boundary. Candidate and production bytes agree within each compiler. Compilers differ only on production NaN/Inf payloads; finite outputs agree across compilers. [Compiler evidence](evidence/host-compilers.json), [actual submission interfaces and 15 parser cases](evidence/selection-tests.json), [validation](cpu-validation.json).

These host gates cannot certify device subgroup execution. Offline BMG-G31 compilation checks the actual prepared translation units without opening a device; it is not a measured occupancy or installed-driver JIT result. Register pressure/spills remain a risk. Packet49 token parity on the device is mandatory before any speed interpretation.

[Lane jobs and coordinator commands](WINDOW.md) use packet65's copied quick screen protocol, production first/last, reversed candidate order across lanes, one candidate lifetime per lane, 90-second gaps and a 3,600-second watchdog. The 128-token screen is diagnostic: it is not the full 512-token realistic promotion gate or a record claim. [CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md), [negative findings](DO-NOT-REPEAT.md), [retention and rebuild](RETENTION.md).

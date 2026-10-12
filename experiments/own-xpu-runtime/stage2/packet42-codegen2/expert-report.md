# Expert codegen round 2

No device was run. All instruction figures below are conditional GEN control-flow sums, not measured issue counts or cycles. They assume valid routes, finite normal half scales and full interior tiles. Each paired tile has eight gate weights plus eight up weights per active lane. Both projections share the activation input. Dividing SIMD instruction counts by this weight count provides a comparison, not a hardware throughput model.

| Kernel | GEN instructions per compared region | Data messages | Weights per active lane | Instructions/weight | Messages/weight |
|---|---:|---:|---:|---:|---:|
| p28.paired.wg32.IQ2_S | 392 | 22 | 16 | 24.5000 | 1.3750 |
| p28.paired.wg32.IQ3_S | 418 | 22 | 16 | 26.1250 | 1.3750 |
| p33.down.bank | 188 | 7 | 8 | 23.5000 | 0.8750 |
| p33.down.select | 482 | 17 | 8 | 60.2500 | 2.1250 |
| p42.down.bank_scalar | 288 | 11 | 8 | 36.0000 | 1.3750 |
| p42.down.select_vector | 441 | 7 | 8 | 55.1250 | 0.8750 |
| p42.gate.packed.IQ2_S | 859 | 32 | 32 | 26.8438 | 1.0000 |
| p42.gate.packed.IQ3_S | 459 | 18 | 16 | 28.6875 | 1.1250 |

Gate/up uses `p42.gate.packed`. Packed 32-bit constant-table words replace byte extraction from independently addressed tables, and each eight-value BF16 input tile explicitly requests packed loads. IQ2 table pairs become one `d32x2` gather per projection; IQ3 keeps two `d32` gathers. Both use four packed input messages instead of eight halfword messages. This cuts the paired IQ2 hot-path messages from 22 to 16 and IQ3 from 22 to 18 per eight inputs, while instruction counts increase. The IQ2 candidate compiler unrolls two tiles, so its displayed region contains 32 weights; the equivalent single-tile instruction average is 429.5 versus 392. The IQ3 candidate is 459 versus 418. Bounds and pointer arithmetic are shared across projection calculations; distinct gate/up packed bytes cannot themselves be shared because their values differ. Restrict-qualified read-only bases and validated 32-bit row offsets retain the packet33 approach. Full hashes, block lists and compressed complete dumps are in `expert-codegen.json` and `expert-assembly/`.

Two expert slots in one work-group were considered but not introduced here. Independent subgroups cannot share activations without either cross-subgroup memory/synchronization or redundant loads, while this task prohibits adding local memory/barriers. Within one subgroup, two slots would add two independent projection accumulators and halve available subgroup parallelism for the same rows. The simpler table/input-message changes isolate a concrete assembly effect first.

Down uses two orthogonal combinations. `p42.down.select_vector` combines the previously measured select lookup with explicit packed input/code loads: the interior tile falls from 17 messages to 7, with mixed-arm instruction union 482 to 441. Its homogeneous lookup path is 249–265 instructions versus 290–306 for the incumbent select. `p42.down.bank_scalar` removes the vector load request from bank lookup as a diagnostic control; the compiler retains packed inputs in the first tile but emits eight halfword input gathers in interior tiles, raising the interior path from 188/7 to 288/11 instructions/messages. It is retained as a bounded factorial control, not predicted to win. The assembly has no table gathers in either down candidate.

The measured packet33 select result (about 90 us) beating bank (about 101 us) despite 17 versus 7 messages disproves a send-count-only bottleneck explanation. Bank uses a dependent variable-shift/extract/sign-extension lookup; select exposes predicate decisions and independent alternatives to scheduling. Dynamic instruction count also predicts the wrong direction (188 versus at least 290), so neither instruction count nor send count establishes the actual stall source. A dependency/latency or occupancy explanation remains a hypothesis; the vector-select versus scalar-bank cross-combinations test it without claiming an unmeasured bottleneck. No new speed estimate is promoted.

CPU gates reuse the exact packet29 `seed()` generation recipe for finite varied values, signed zeros, subnormal and finite extreme inputs, odd row counts and invalid/empty/partial routes. Additional packet33 diagnostic patterns cover K=1,3,17,255,639,640 down tails, exhaustive IQ4 lookup values, 20 half-scale patterns and exceptional inputs. Both GNU and Intel host compilers run twice in fresh processes. Each candidate compares to the incumbent; paired gate/up also compares to the reference dot core. Reduction-tree and BF16 fixture outputs are checked. `expert-gates.json` binds CPU binaries and reports zero failures in the qualified scope; finite hashes agree across compilers and repeats.

Nonfinite GEMV follows packet29 `NONFINITE-GEMV.md`: it is outside production qualification, never NaN-category equality. Candidate-to-incumbent raw bytes match for every nonfinite diagnostic in both compilers. GNU has 256 preexisting raw lane differences against the frozen reference on nonfinite scales; Intel has zero. These remain explicitly recorded diagnostic failures, not silently accepted as bit identity.

`expert_submit.hpp` exposes `p42expert::submit` with the packet33 signature. IDs are `p42.gate.packed`, `p42.down.select_vector`, and `p42.down.bank_scalar`. Validation delegates to the unchanged p28/p29 validation, then rejects a packed-weight extent above UINT32_MAX before using 32-bit row offsets. Device lambdas use `p28::checked` (capture <=1024 bytes). No barrier or local accessor is added. Device comparison/timing must use the runtime submission interface and reject any output/status byte mismatch.

gcc: 335,620 qualified checks plus 533,028 nonfinite diagnostics per process; CPU binary SHA-256 `43bec16e7eaff13fd279c20f04e4e85c378e2da797b7b657e481aa801042aa7e`.

icpx: 335,620 qualified checks plus 533,028 nonfinite diagnostics per process; CPU binary SHA-256 `532770027c89db0dda3475d268fe898948df891c067297641a88e3c0f5f76d99`.

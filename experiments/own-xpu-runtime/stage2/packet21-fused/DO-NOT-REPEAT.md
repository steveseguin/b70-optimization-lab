# Packet 21 negative results and boundaries

| Arm or shortcut | Outcome and evidence | Revisit condition |
| --- | --- | --- |
| CPU HC prologue recomputed per GEMV row | First full attempt stopped cooperatively; far too much duplicate CPU work. Pure expression is now evaluated once per submission input; device arithmetic unchanged. [Preregistration](PREREGISTRATION.md). | A different host emulator requiring row-local evaluation. |
| Gate receipts from before final descriptor validation | Second attempt stopped; never counted as a pass. All complete gates bind final runtime bytes. | None; rebuild and rerun after any runtime edit. |
| M=87 GDN groups serialized in a single work-group fixture | Removed from standalone candidate; retain original parallel group geometry. The smaller actual fused chains still need device timing. | New measured device evidence below the submission budget. |
| Reused fixture allocation labels | The owner correctly refused duplicate labels before arithmetic. All fixture owners now assign monotonically unique labels; GNU gates passed afterwards. | None; retain owner admission checks. |
| Intel host fixture without compiler-library RPATH | Loader stopped before execution because libiomp5.so was missing. Fixture CMake now embeds the installed compiler library directory; no shell-wide loader setting is needed. | Compiler installation moves; rebuild and reseal. |
| Cross-work-group producer/consumer fusion without a global barrier | Not implemented. Retain boundary or execute the whole dependent phase within one group. | A proved synchronization mechanism with unchanged arithmetic. |
| Early overwrite of a sibling input | Descriptor admission rejects it; output/input spans are checked across the bundle. | Separate stable input storage plus fresh exactness/alias gates. |
| Device execution on this boot | Forbidden. All windows reject the sealed FAULT HALT boot. | Owner-authorized reboot/recovery and explicit device-work authorization. |
| Launch count promoted as tokens/second | Forbidden; 30 us/launch is a labeled issue-cost projection only. | Matched device windows and all quality gates. |

The CPU preparation closes only the implementation/gate arm. Device correctness,
submission duration, occupancy and speed are open. The next lever is replay;
see [README.md](README.md) and [packet20 design](../packet20-launch/REPLAY.md).

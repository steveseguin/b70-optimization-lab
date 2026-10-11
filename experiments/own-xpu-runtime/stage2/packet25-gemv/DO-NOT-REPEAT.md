# Packet 25 negative and pending index

| Direction | Evidence / outcome | Revisit condition |
| --- | --- | --- |
| R6 register-grid decoder | 1.45 ms whole expert block versus 0.298 ms control, 6 KiB IQ2 spill | A different mechanism with bounded pressure; not repeated here |
| R6 SLM pair / packed pipeline | 2.34 / 2.60 ms versus 0.298 ms; 5–9× slower | New evidence, not instruction-count forecasts; neither is implemented here |
| R2 two rows per work-item with whole-row wide staging | Regressed across shapes | This packet uses independent SG32 rows and direct eight-byte loads, not that design |
| Expand all experts | Packet10 capacity exceeds two cards | A different measured memory budget; not proposed |
| Claim scale hoisting is new | R3/R6 already share metadata scales | Half-table arm only removes exact half conversion; measure its extra reads |
| Treat mathematical equality as NaN bit equality | initial-failures.json records payload/sign changes | Shared current fallback plus CPU/native gates; no canonicalization |
| Scalar dot alone is the universal oracle | Mixed nonfinite operands can differ from the frozen compiler path | Frozen row remains authority; scalar oracle is additionally checked in the finite domain |
| Pack rows by changing lanes or split4 | Changes the declared reduction | Forbidden in this identity |
| Time only expanded consumer | Omits per-token scratch decode | Both GPU events plus sequence wall must be counted |
| Force SiLU cross-compiler NaNs to agree by canonicalization | epilogue-diagnostic.json: GEMV fields agree, added SiLU field does not | Exact nonlinear identity work before fused integration; no canonicalization |
| Infer model speed from tiled fixture timing | Omits real cache/residency/prologue/dependency behavior | Exact real-model oracle and matched fresh-owner timings |

Source lessons: [R6](../packet11-kopt6/DO-NOT-REPEAT.md), its measured README,
[R5](../packet10-kopt5/DO-NOT-REPEAT.md), and [R3](../packet8-kopt3/DO-NOT-REPEAT.md).

# Round-3 negative and pending index

| Direction | Evidence / outcome | Revisit condition |
| --- | --- | --- |
| Two rows per subgroup plus whole-row wide staging | Round-2 card-3 table: slower across tested shapes; earlier packets preserved | New mechanism and resource evidence, not another width-only sweep |
| Split4 on every shape | Round-2 expert/up matrices regress; [dispatch](dispatch.json) selects by full shape/type/bank | New matched evidence on that shape |
| Treat quantized GEMVs as streaming-load limited | F32 router ~289 GB/s, quantized paths 50–100, read ceiling ~590 | Instruction/occupancy evidence that changes the diagnosis |
| Direct icpx device-only `-S` / `-S -emit-llvm` | Compiler rejects IR output; [offline receipt](assembly-receipt.json) records the supported bitcode/translator route | Compiler capability change |
| System spirv-dis | Rejects decoration 5940 on this installed version | Updated disassembler; bundled llvm-spirv text already works |
| Fold IQ sign without exceptional-value fallback | Special CPU fixtures exposed NaN sign mismatch; corrected in decode.hpp | A separately exact-proven special-value implementation |
| Real gate/up/down in one independent-input launch | Down requires the intervening activation result | Actual dependency-correct design; this packet uses gate/up then down |
| Promote a decode candidate from instruction forecasts | Device measurements absent; all new candidates pending | Hash-bound exactness and matched fresh-owner timing repeats |

[Preparation closeout](CLOSEOUT.md). This index closes methods, not the model lane.

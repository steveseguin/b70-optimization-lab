# Packet52 preparation findings

| Finding | Outcome | Revisit condition |
| --- | --- | --- |
| Eight-expert fixture for the brief's quoted10.496MB gate/up | Rejected before build: production selects ten experts | Separate model/topology registration |
| Use p48b QKV/Z candidate timings as adopted control | Rejected: those replacements were not integrated | Measure actual production controls |
| CPU mirror calling the device lane helper | Replaced with independent scalar product traversal | Shared decoder remains explicit; future model oracle decodes original packed bytes |
| Small FFN E as four independent launches, T as one fused tuple | Corrected before qualification; full host composition gate passes | E/T must exercise the same binding path |
| Full mutable-arena restoration for every candidate arm | Replaced with scoped operand/output/control resets from four snapshots | Require explicit dependency and output coverage for any reset change |
| Generic runtime format/K inside every new device loop | Replaced with compiled format/K specialization | Generic kernel only with separately justified scope |
| Intel host binary missing compiler runtime search path | First CPU process refused before main; RPATH corrected, refusal retained | Verify process reaches arithmetic receipt |
| Final BF16 outputs agree on finite synthetic fixture | Diagnostic only; rounding can hide FP32 order differences | Fresh device mirrors and later full-model oracle, never infer old-order equivalence |

These are preparation findings, not measured candidate speed failures. The
arithmetic-v3 decision is pending the coordinator's E/T windows. See the
[preparation closeout](CPU-PREPARATION-CLOSEOUT.md).

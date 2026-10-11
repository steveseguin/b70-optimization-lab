# IQ3 CPU oracle — closed choices

| Date | Closed choice or method | Evidence and condition for revisiting |
| --- | --- | --- |
| 2026-10-11 | GDN SiLU inferred from the 27B path; asking again whether Flash should use sigmoid | The coordinator chose official architecture code. Qwen4Exp reads output_gate_type=sigmoid; QSA also uses sigmoid. Reopen only for a new pinned model/code identity. [Gate evidence](../own-xpu-runtime/stage2/packet1b/gate-evidence.json). |
| 2026-10-11 | Treating partial prefill or empty baseline text as output agreement; treating synthetic repeats as full-model qualification | [Three-hour CPU closeout](packet2-cpu-oracle/CLOSEOUT-20261011.md) records two complete 64-token rows and the missing suite/repeat gates. |

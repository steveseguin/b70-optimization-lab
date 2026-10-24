# Dense Q6 class diagnostic, separate launch B

Launch A remains a failed, safely closed attempt. Its fixed full-run external forecast was charged again after completed captures had consumed space. This additive correction preserves the qualified binary, prompts, class timing, baseline oracle, passive ownership checks, and retained-owner cleanup. Only the remaining payload forecast changes after acknowledged capture boundaries. Root alone creates the operational plan and launches the separate `gsq-dense-q6-class-b` unit/control/evidence paths.

The target capture is T = 221,743,168 bytes; draft capture is D = 9,699,332 bytes. A target DUMP does not write draft state. RESET writes the previous request's draft state, while FINISH writes the final draft state. Thus the remaining payload is:

| Confirmed boundary | Remaining bytes |
| --- | ---: |
| Before initial RESET | 694,327,500 = 3(T+D) |
| Initial RESET acknowledged | 462,885,000 = 2(T+D) |
| Warmup target DUMP verified | 241,141,832 = T+2D |
| Second RESET acknowledged | 231,442,500 = T+D |
| Measured target DUMP verified | 9,699,332 = D |
| FINISH/owner close completed | 0 |

The explicit final target DUMP repeat does not decrement anything. Failed RESET, DUMP, or FINISH cannot advance its boundary. No file existence or arbitrary on-disk byte count is used as a completion signal. Each check retains the entire 128 MiB metadata allowance and 2 GiB external floor. The root 27,000,000,000-byte floor plus 128 MiB cache allowance is unchanged. Initial admission still reserves all three captures (694,327,500 bytes plus metadata).

Seven focused CPU tests exercise the actual qualification call order with simulated writes and actual storage-guard accounting, including exact starting threshold, one byte below every boundary, the old guard's false refusal after warmup, failed acknowledgements, retained-owner identity, and unchanged class argv. They do not execute a model, device, operational plan, or sealer. `evidence/preparation.json` binds the tests and source. The original A source, authority, and diagnosis are hash-pinned in `parent-pins.json`.

The diagnostic remains one excluded eight-output target warmup followed by original prompt 00, target-only, cap 128; both requests fully RESET. It checks original baseline tokens and target state, explicit final DUMP repeat, FINISH and closed maps. Whole-request class durations and separate half-event phase totals remain distinct; there is no throughput or per-class phase claim.

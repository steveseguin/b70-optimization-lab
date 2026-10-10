# Flash-Next FP8: 46.85 tokens/s on four B70 cards

Flash-Next is a 125B-A6B model. This recipe uses four 32 GiB B70 cards, official FP8 weights, full BF16 KV and one target-verified draft token for one user.

The approved A367 headline is **46.854250 tok/s**, +23.87% vs the previous
37.825654 line, with the fixed realistic-suite output pins unchanged.
Separate A382/A394 depth measurements reproduce through 32K: **44.052 tok/s**
four-row median at 32,768 input tokens, all output hashes equal to A381.

- [Recipe, exact identity and measured context profiles](../../repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/README.md)
- [Campaign closeout and nonpromoted trials](../../results/qwen38-flash-next-fp8-b70/CLOSEOUT-20260913.md)
- [Package manifest](package.json)

Expert lab-replay candidate; clean-host/container qualification and the frozen
long-context quality battery remain open. Historical host-controlled replay is
not authorized by the current user's no-power-change/no-repeated-restart policy.

Prompt reading at 512 tokens is **not measured** on this exact setup. The 875 tokens/s result belongs to the [separate 27B two-card multi-user package](../qwen38-27b-fp8-tp2-b70/README.md), where it is combined output from 64 short requests.

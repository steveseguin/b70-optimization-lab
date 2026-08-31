# Qwen3.8 Gemma RMSNorm cross-process D3b result

Date: 2026-08-31

Status: **negative causal screen; 26/26 cases stable**

Direct, per-row serial, and M=128 padded Gemma RMSNorm repeated bitwise within
and across four fresh processes for plain and fused-residual calls at M=1 and
all 12 strict-suite prefill sizes. The four process receipts were byte
identical. Direct and padded outputs matched in all 26 cases; serial matched
direct only for the two M=1 cases because it selects a different kernel shape.

RMSNorm is not the remaining MTP0 source. This is raw operator evidence only.
Next, hash the complete ordinary native GDN transition—prefill output/state
and a fixed recurrent decode trajectory—across fresh processes.

Condensed result:
`../data/2026-08-31-qwen38-gemma-rms-cross-process-d3b-result.json`.

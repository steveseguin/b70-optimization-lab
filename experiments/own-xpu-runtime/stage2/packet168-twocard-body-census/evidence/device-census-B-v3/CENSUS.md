# Packet168 diagnostic body census

Diagnostic marginal differences; never a model speed result.

| Class | Measured ms/body pass | Prompt spread ms | Share of 17 ms | Closed-lever boundary |
|---|---:|---:|---:|---|
| dense_hc | 11.531830 | 0.056240 | 67.83% | p140: replaces assumed transfer pricing only after complete matched census |
| routed_experts | 5.534780 | 0.044310 | 32.56% | p81/p95/p102/p162: fewer loads are not measured end-to-end savings |
| router_shared_expert | 3.341220 | 0.067700 | 19.65% | p109/p112/p164: route/shared activation and shared-down/mixture stay fused; exact routes/ties required |
| gdn | 2.049900 | 0.076200 | 12.06% | p113/p107: unchanged recurrence order; no nonfinite arithmetic waiver |
| norms_glue | 1.834700 | 0.034800 | 10.79% | p78/p94/p107: full rounded producer/consumer boundary remains required |
| residual (not causally isolated) | -7.158339 | — | — | control ms/token − sum of measured classes; includes transfer, split head and overlap |

Control drift 0.101% (view means); largest single-prompt drift 0.834%.

Top-two **conditional ceilings**, not measured speed:
- dense_hc: {'0.3': 73.8389557975459, '0.5': 88.98134050167013}; 30%/50% of lower-quartile marginal removed; no replacement overhead; 17ms reference; not measured optimized speed
- routed_experts: {'0.3': 65.18213485440626, '0.5': 70.24422864636912}; 30%/50% of lower-quartile marginal removed; no replacement overhead; 17ms reference; not measured optimized speed

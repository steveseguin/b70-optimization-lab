# Qwen3.6 Quark INT8 TP2 Latency Truth-Serum

Date: 2026-06-12

Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`

Purpose: test whether TP4 synchronization is hurting single-request decode enough that TP2 on two B70s could be a no-quality-loss latency lane.

## Launch

| Runtime | GPUs | TP | Model load memory | KV cache | Max 32K concurrency | Attention page |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| TP2 candidate | 0,1 | 2 | 16.88 GiB/rank | 1,138,206 tokens | 34.74x | 1088 tokens |
| TP4 restored | 0,1,2,3 | 4 | 8.58 GiB/rank | 2,052,915 tokens | 62.65x | 576 tokens |

## Speed

| Runtime | Prompt/output | Repeats | Corrected tok/s | Decode ms/token | TPOT ms |
| --- | --- | ---: | ---: | ---: | ---: |
| TP2 candidate | p512/o256 | 1 | 91.592 | 10.877 | 10.919 |
| TP2 candidate | p512/o256 | 3 | 91.351 mean, 91.204-91.542 range | 10.906 | 10.949 |
| TP4 restored | p512/o256 | 1 | 100.475 | 9.916 | 9.955 |

## Quality And Provenance

- TP2 passed the no-thinking smoke suite: exact OK/copy/arithmetic/JSON, repeat stability, and baseline matching.
- TP2 failed exact accepted TP4 provenance. Sentinel drifts:
  - `repetitive_kernel_notes` index `14`: expected `4752`, actual `6126`.
  - `natural_latency_plan` index `17`: expected `11436`, actual `19087`.
  - `natural_latency_plan` index `25`: expected `198`, actual `321`.
- TP4 restore produced one transient failed gate immediately after launch, then passed on rerun:
  - Provenance sentinels `4752`, `11436`, `198`.
  - No-thinking quality smoke `pass_all=true`.

## Decision

TP2 is ruled out as a promotion path for the current goal. It is slower than TP4 and does not preserve the accepted TP4 token stream. Future topology work should focus on TP4 internals, hybrid TP/EP, or exact verifier-owned transaction paths rather than a plain TP2 latency lane.

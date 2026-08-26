# Qwen3.6 embedded-Q8 q8_0-KV MTP route 8K sentinel R1 result

The bounded q8_0-KV route screen passed all five fresh TP1 graph-off arms at exact 8K prior active context. Serving decode was 12.4243 tok/s at MTP0, 22.7998 at MTP1, 34.3653 at MTP2, 38.9711 at MTP3, and 41.1343 at MTP4. Relative to the fresh MTP0 control, MTP1/2/3/4 gained 83.51%, 176.60%, 213.67%, and 231.08%.

All five responses produced the identical output-token hash `a5d484b53727b903cd925d6521c100fdd2114094801253363661b370cb4692ef`. MTP1/2/3/4 drafting engaged and conserved at 61/66, 80/92, 91/108, and 96/123 accepted/generated tokens. Every request was cache-zero, every arm passed, and all five server lifetimes cleaned up successfully.

Both target and draft KV are explicitly `q8_0`: the sealed argv uses `-ctk q8_0`, `-ctv q8_0`, `--spec-draft-type-k q8_0`, and `--spec-draft-type-v q8_0`. Identity is pinned to `unsloth/Qwen3.6-27B-MTP-GGUF@5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace`, model SHA `9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8`, llama.cpp source `15586e2d7165570fb3aa7c26e0d442e289ef69de`, server SHA `1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7`, and the eight local DSOs preserved in the result. Because the raw identity stored only four environment fields, the structured result also reconstructs and binds the committed runner's complete explicit environment overlay: DNN/OPT/VMM, oneDNN/MKL/FlashAttention, ZES/UR, selectors, proxy removal, oneAPI base, and runtime-library prepend.

The result binds all 37 raw files through inventory SHA `247479b3ec508f8d3eb35cd4e1e2d6c87d080b1967114ec1cbba1395539095dc`; terminal SHA is `c2109be250e576e228a056e2f8fe15e668082ccd8a0698da4b3acba6b19cc35d`.

Authority remains route-gate-only: MTP1–4 may proceed to separately preregistered q8_0-KV depth curves. This sentinel creates zero site or matrix cells and grants no family publication, graph, headline, protected replacement, record, or LocalMaxxing authority.

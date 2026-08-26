# Qwen3.6 embedded-Q8 MTP route 8K sentinel R2 result

R2 passed its bounded route screen. At exact 8K prior active context, the same graph-off TP1/F16-KV runtime measured 16.1000 tok/s at MTP0, 27.6829 at MTP1, 36.4399 at MTP2, 41.4292 at the MTP3 positive control, and 43.8364 at MTP4. Relative to the fresh MTP0 arm, the speculative gains were 71.94%, 126.33%, 157.32%, and 172.28%.

All five arms returned the identical output-token hash `a5d484b53727b903cd925d6521c100fdd2114094801253363661b370cb4692ef`. MTP1/2/3/4 drafting engaged and conserved at 61/66, 80/92, 91/108, and 96/123 accepted/generated tokens. Every request was cache-zero, each alias check passed, and every fresh server lifetime cleaned up with a closed port, idle render node, no survivor, and no forced kill.

R1 remains preserved as a pre-GPU failure. Its ldd parser required SONAMEs at column zero and falsely rejected the ordinary leading indentation before `libllama-server-impl.so`. R2 changed only the regex from `^{soname}` to `^\s*{soname}`; the model, server, eight-DSO closure, environment, arms, workload, gates, and authority were unchanged. No R1 row was reused.

Identity is sealed to `unsloth/Qwen3.6-27B-MTP-GGUF@5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace`, model SHA `9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8`, llama.cpp `15586e2d7165570fb3aa7c26e0d442e289ef69de`, server SHA `1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7`, and the eight local DSOs recorded in the structured result. The result binds all 37 R2 raw files plus the immutable R1 failure receipt.

Authority is deliberately narrow: MTP1, MTP2, and MTP4 may proceed to separately preregistered seven-depth curves. This 8K sentinel creates no website or matrix cell, does not replace the successful MTP3 R3 profile or any protected value, and grants no headline, record, or LocalMaxxing authority.

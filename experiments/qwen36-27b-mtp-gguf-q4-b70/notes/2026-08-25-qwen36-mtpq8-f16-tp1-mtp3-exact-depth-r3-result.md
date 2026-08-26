# Qwen3.6 embedded-Q8 MTP3/F16 TP1 exact-depth R3 result

R3 passed and is promoted only as a quality-battery-certified family research profile. Across the seven graph-off HTTP-serving cells at 0/2/4/8/16/24/32K prior active context, MTP3 produced 31.806–41.392 decode tok/s versus 13.626–17.187 tok/s for the same-run MTP0 controls: gains of 105.73%–157.02%.

Every candidate response had exact output-token parity with its depth-matched control. Drafting engaged and conserved at every depth (accepted/generated: 87/115, 81/135, 88/115, 91/108, 82/130, 88/117, 87/119), all measurement and quality requests were cache-zero, the four-canary/two-repeat/long-context-needle battery passed, and both server arms cleaned up without forced termination or survivors. The needle was configured for approximately 29.4K tokens; the fixture contained 27,234 prompt tokens before chat templating and the API reported 27,246 prompt tokens.

The x=0 point is **zero prior active context plus one explicit ordinary prompt token** (`[90]`, `usage.prompt_tokens == 1`). It is not a literal empty prompt or a raw-engine zero-token call. The 2K–32K points use the exact declared active depths unchanged.

Identity is sealed to `unsloth/Qwen3.6-27B-MTP-GGUF@5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace`, model SHA `9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8`, llama.cpp source `15586e2d7165570fb3aa7c26e0d442e289ef69de`, server SHA `1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7`, the eight-DSO closure in the structured result, TP1, F16 target/draft KV, graph disabled, and the backend-sampling MTP3 policy (`n_max=3`, `n_min=0`, `p_split=.10`, `p_min=0`). Raw terminal SHA is `40907a9061c343da7cbc540178788adb38404fba26bdd0a1cc788e1870e0c6ae`.

This review authorizes seven family-matrix cells and a compact family-site profile. It does not replace any historical, featured, primary-packet, protected, serving-headline, or record value and grants no LocalMaxxing submission authority.

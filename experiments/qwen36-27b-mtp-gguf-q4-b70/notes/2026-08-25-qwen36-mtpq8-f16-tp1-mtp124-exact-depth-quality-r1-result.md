# Qwen3.6 embedded-Q8 MTP1/2/4 F16 exact-depth result

The MTP1, MTP2, and MTP4 routes each passed all seven graph-off TP1/F16-KV HTTP-serving cells at 0/2/4/8/16/24/32K prior active context. MTP1 measured 23.731–28.483 tok/s (63.32%–74.15% over the same-run MTP0 control), MTP2 measured 29.043–37.237 tok/s (91.55%–125.48%), and MTP4 measured 31.285–43.716 tok/s (105.60%–171.39%).

All 21 candidate responses matched their depth-specific control output-token hashes exactly. Drafting engaged and conserved at every cell; the structured result preserves every accepted/generated count and acceptance ratio. Every measurement request was cache-zero, all four fresh server lifetimes cleaned up, and the x=0 points mean zero prior active context plus one explicit ordinary prompt token ID 90 (`usage.prompt_tokens == 1`) rather than a literal empty prompt.

Each route independently passed four exact canaries, two stable repeats, and a long-context needle. For all three needles, the configured target was approximately 29.4K tokens, the fixture contained 27,234 prompt tokens before templating, and the API reported 27,246 prompt tokens with zero cached tokens.

Identity is sealed to `unsloth/Qwen3.6-27B-MTP-GGUF@5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace`, model SHA `9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8`, llama.cpp source `15586e2d7165570fb3aa7c26e0d442e289ef69de`, server SHA `1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7`, and the eight local DSOs recorded in the result. The result binds the separate 105-file raw inventory manifest at SHA `1d386022c1540827abcf1b9fa01fb8ccac9e922b69db1fbdad8c3a482d06d388`; terminal SHA is `2d7552538912ee22c40b4fccfd6df8a0046c11529372b34f9ce4390d1a57d357`.

Independent review authorizes exactly 21 family matrix cells and the existing compact MTP context view. It does not replace the sealed MTP3 R3 series, historical speeds, featured results, the primary packet, protected rows, records, or LocalMaxxing submissions.

# Qwen3.8 Flash-Next FP8 M1 HyperConnection native-MV screen

Date: 2026-08-30
Status: exploratory component negative

A28 showed that 193 of 532 dense GEMMs in one target token are the two M1
HyperConnection projections. A small one-B70 screen loaded the real layer-0
attention HyperConnection weights and compared the existing
`torch.nn.functional.linear` path with native `torch.mv` and transposed
`torch.matmul` calls.

The `[1,10240] x [336,10240]` down/injection candidate was slower and changed
output bytes. The `[1,320] x [10240,320]` up candidate retained exact bytes but
was also slower. This screen is deliberately not an endpoint or promotion
measurement; its synchronize-per-call timing is sufficient only to reject
these direct substitutions.

Do not add an MV dispatch or a transposed-matmul rewrite. A future treatment of
the dense bucket needs a purpose-built exact skinny kernel or a larger
HyperConnection fusion with its own component and endpoint gates. Structured
evidence is in
[`20260830-hc-m1-native-mv-exploratory-negative.json`](../data/20260830-hc-m1-native-mv-exploratory-negative.json).

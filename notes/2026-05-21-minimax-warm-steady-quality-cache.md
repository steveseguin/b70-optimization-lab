# MiniMax Warm Steady-State Cache Validation

Result: quality-passed warm steady-state MiniMax M2.7 AutoRound TP4 on 4x B70.

The first warm steady-state run reused the older `20260519` vLLM compile cache and measured `92.941669` output tok/s, but the strict gate caught a raw145 n256 exact-token mismatch:

- Expected raw145 n256 hash: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- Stale-cache hash: `f77e2a46bd82d2e4c2a00dacd9f464fec6c3091b24a87bdd984cb1920aefc2fb`
- The output was deterministic and non-degenerate, but it skipped one token in the alphabet continuation, so the run is rejected for quality-sensitive publication.

A fresh cache root was compiled and then validated:

- Cache root: `/mnt/fast-ai/vllm-cache-exp/minimax-quality-clean-20260521T152425Z`
- Strict gate: `quality_passed`
- Raw145 n64: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- Raw145 n256: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- Semantic suite: `adacbf144264486ea7d378ebb6a4c0ba23951b72c4cf86251a762b07ebef5805`
- Arithmetic repeat: `def6899500b2364bc97d561fc5f9cc78aa9fbcd5a0eb032eab1f2c6735d2bbec`
- Extended sixpack: `1e3560554f57b2b56cec8f49f28bc8ba12e9e0ced26bdc99a976f1433c99caa7`

After that gate passed, the same cache root produced:

- Methodology: one persistent vLLM engine, two p512/n1536 warmups discarded, four measured greedy p512/n1536 repeats
- Output tok/s mean: `93.443623`
- Total tok/s mean: `124.591498`
- Output tok/s range: `93.408569` to `93.472185`
- Output tok/s stdev: `0.026560`

This is a warm steady-state number. It is valid for services that keep a vLLM engine resident and discard warmup requests, but it should be labeled separately from the colder process-per-benchmark harness that produced `89.696348` output tok/s.

Reproduction rule: do not reuse stale compiled vLLM/AOT cache roots without running raw145 n64+n256, semantic, arithmetic-repeat, and extended-sixpack gates. The promoted environment now points away from the old `20260519` cache root.

# Qwen3.8 official AutoRound TP1 eager/F16 MTP4 depth expansion r1

The preregistered six-depth expansion is a mixed partial diagnostic result, not a publishable curve. All six mechanism-acceptance gates passed, five of six exact-depth gates passed, and only 4K, 16K, and 24K matched the frozen target token sequence. No family or site cells are authorized by this seal.

| Depth | Decode tok/s | TTFT | Acceptance | Target outcome | Classification |
|---:|---:|---:|---:|---|---|
| 2K | 12.005765140784916 | 2.3760272930085193 s | 82/180 | diverged at token 90 | exact, target-divergent diagnostic |
| 4K | 14.850597409841217 | 2.9985333750082646 s | 90/148 | exact parity | exact parity diagnostic |
| 8K | 15.360198998480438 | 6.025442046011449 s | 97/124 | diverged at token 99 | exact, target-divergent diagnostic |
| 16K | 12.361817762397319 | 12.356159284012392 s | 88/156 | exact parity | exact parity diagnostic |
| 24K | 13.116686989341177 | 19.10413311100274 s | 92/144 | exact parity | exact parity diagnostic |
| 32K | — | 26.220595320992288 s (partial) | 81/156 | 121 tokens, no usage | engine-fatal incomplete; no speed cell |

At 32K the engine died near the final output tokens with `RuntimeError: Expected spec_token == num_spec_decodes * (num_speculative_tokens + 1) to be true, but got false.` The partial response returned 121 tokens and no usage object. Its helper-observed 12.198861745354137 tok/s timing is retained only as a non-publishable partial observation. The quality battery then returned rc=1 against the dead engine and did not produce `quality.json`; this is not a quality failure on a completed curve because the battery never ran.

The separately booted 8K parent remains the passed result of record: 15.694764790035633 tok/s, 6.8153263599961065 s TTFT, 92/140 accepted, exact target hash parity `34e792ccf3c1d795b686750f27990de2ca605c22046c97b3fff8ad0a7fc82e53`, and the full quality battery passed. The divergent expansion-run 8K sample neither replaces nor lowers that parent.

This seal preserves clean cleanup, zero publication cells, no historical/protected/headline replacement authority, and x0 as missing. The three parity-passed depths and two divergent exact depths may only be considered later as explicitly lower-grade, per-cell diagnostics; this result grants no full-curve publication authority.

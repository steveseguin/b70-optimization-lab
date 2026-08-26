# Qwen3.8 official AutoRound TP1 eager/F16 MTP2 8K sentinel r1

This sentinel is **quarantined for failed target verification**, not promoted as strong measured coverage. Its exact 8K request passed at 11.53170763636204 conventional 99-interval tok/s (11.648189531678828 historical 100-event tok/s) with 6.722347527989768 s TTFT and zero cached tokens. The MTP mechanism passed, accepting 82 of 94 drafted tokens (0.8723404255319149), and the complete quality, baseline, long-context, repeat-determinism, model-read, and cleanup gates passed.

The decisive failure is output parity: the candidate diverged from the frozen same-image TP1/MTP0 eager/F16 oracle at token 99 (zero-based 98), producing token 411 instead of 579. The candidate hash is `dd31856f45269d222efe0f6f5f1ac9342b6c9ae55e5ce9129fc02b27abdb7e8e`; the target is `34e792ccf3c1d795b686750f27990de2ca605c22046c97b3fff8ad0a7fc82e53`.

This seal authorizes zero family/site cells, no strong measured coverage, no expansion, and no protected, historical, graph, headline, frontier, or LocalMaxxing replacement. It records the useful mechanism and quality evidence without concealing the parity failure; x0 remains missing.

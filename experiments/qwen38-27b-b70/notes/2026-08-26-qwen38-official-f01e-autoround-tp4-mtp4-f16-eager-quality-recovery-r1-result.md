# Current-f01e AutoRound TP4/MTP4 eager F16 quality recovery R1 result

Result: **passed quality-clean recovery; three Grade C cells under explicit per-depth adjudication**.

The fresh TP4/MTP4 server passed exact-depth, cache-zero, isolated-acceptance, same-topology target, objective-quality, baseline-quality, topology, model, rank-cache-isolation, and cleanup gates. Exact 4K, 16K, and 24K matched their TP4/MTP0 target oracles and are published at conventional 99-interval rates of 21.97463738631815, 23.789706915057792, and 25.753606722449813 tok/s.

The recovery intentionally did not rerun the known-divergent 2K cell or the known-fatal 32K cell. It reproduced the quarantined 8K MTP4 parent exactly, including the token-99 target divergence. Therefore 2K remains quarantined, 8K remains quarantined, 32K remains a runtime-fatal closure, and x=0 remains missing. None of those cells receives a displayed speed.

The earlier 32K request streamed 126 token IDs matching the target prefix before the XPU GDN speculative-token shape assertion killed the engine. It did not produce a complete response, so it is a current-profile runtime closure rather than evidence of model corruption or stop-token behavior. The recovery supersedes only the prior lack of quality authority at 4K/16K/24K.

This publication adds exactly three measured Grade C cells and one new structural quarantine plus one runtime closure. It does not replace the existing 8K state, any graph/headline/frontier route, protected speed, or LocalMaxxing result, and transfers no authority to other TP, MTP, graph, KV, or runtime profiles.

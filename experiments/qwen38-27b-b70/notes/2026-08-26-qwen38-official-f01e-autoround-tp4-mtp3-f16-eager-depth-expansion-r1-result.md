# Current-f01e AutoRound TP4/MTP3 eager F16 depth expansion R1 result

Result: **partial Grade C under explicit per-depth adjudication**.

All six exact-depth, cache-zero, isolated-acceptance, objective-quality, topology, cache-isolation, and cleanup gates passed. The same-topology MTP0 target matched at 4K, 8K, 16K, 24K, and 32K. The 2K candidate diverged at token 90 (candidate 16539, target 59178), so the raw arm correctly terminated `partial-depth-expansion` with return code 37.

The valid 4K, 16K, 24K, and 32K cells are published additively at conventional 99-interval decode rates of 25.3203, 21.9448, 22.0889, and 22.5484 tok/s. The previously published exact-8K sentinel remains 21.07719065875979 tok/s unchanged; the expansion's independent 27.035413282340656 observation does not rewrite it. The 2K selector is quarantined without a displayed speed, and x=0 remains missing.

This human adjudication does not change the fail-closed raw receipt and transfers no graph, other-MTP, headline, protected-route, or LocalMaxxing authority. The protected decode values remain unchanged.

# Independent draft wiring review

Reviewer: Codex subagent `/root/wiring_review`, independent source read of packet31's draft_reference.py, qsa_reference.py and the vLLM sources listed in its wiring-review.md, followed by packet36's actual implementation.

Confirmed: shifted input `(H[p-1], embedding(x[p]))`, cache/RoPE `p-1`, first row `H0+x1`, materialized final streams, global 10240 norm, stream-major projections, indexer split, private cache, no PLE, ten routes and shared head. All 29 non-expert tensors and 3072 expert/scale tensors map to the official names. Requantizer uses group16 nearest-even max/127 and multiplicative publisher scales.

Required arithmetic disclosures: packet31's torch reduction and CPU reference are not the device oracle. Dense trees, HC reassociation, weighted-down rounding, sigmoid boundaries and deterministic transcendental differences must be measured. Existing specialised.hpp was verified byte-identical to packet32; a concern about its pre-existing 512-element workspace was withdrawn.

Found and fixed: disabled provider was checked after its cache-position assertion; later disabled calls could abort target. Disabled now returns before the assertion. Recoverable `ProviderError` exceptions are caught and permanently disable the provider only after a successful drain. Model authentication errors and owner/device errors abort safely.

No device or heavy tests were run by the reviewer. Actual gates are separately bound in build-receipt.json.

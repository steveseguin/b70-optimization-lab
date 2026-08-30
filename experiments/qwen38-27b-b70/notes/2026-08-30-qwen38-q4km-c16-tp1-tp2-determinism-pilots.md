# Qwen3.8-27B Q4_K_M c16 topology determinism pilots

Both preregistered oracle-generation pilots passed their isolation and systems gates.

| Topology | Residency | Diagnostic aggregate rate | Pilot gates |
| --- | ---: | ---: | --- |
| TP1, one B70 | ~21.4 GiB on one card | 15.502239899072196 tok/s | pass |
| TP2 tensor 1,1 | ~10.8 GiB per card | 17.659748646572798 tok/s | pass |

The TP2 gain at this fully synchronized c16 shape was only 13.9%. These rates are diagnostic and not promoted.

TP1 and TP2 produced exactly the same 128-token sequence for only 2/16 prompts. That is a topology-dependent numerical boundary, not proof of run-to-run nondeterminism: the first divergence in the other prompts ranged from token 15 to token 122. Each topology therefore has its own frozen 16-row oracle and must be replayed against itself.

- TP1 oracle SHA-256: `63f76b4518228c14620d5214556ec651737af69fd21d11662fba5569bf7a7699`
- TP2 oracle SHA-256: `e0fd85fe21a1b6d023d0de4274664d3a800f0e0135bd2f78c30be800d9aae9b2`

Both pilots completed 16/16 responses with 128 token IDs, zero cached tokens, zero cross-base collisions, WDC absent, empty kernel-error files, and clean shutdowns.

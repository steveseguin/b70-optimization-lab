# Qwen3.8 Flash-Next FP8 TP4 MTP0 active-16K fresh-server A4 preregistration

Date: 2026-08-28
Status: frozen before execution

## Question and boundary

A3 proved that the first 16,213-token semantic request was correct and the
identical second request on the same server was corrupted despite reporting
zero cached tokens. A3 correctly blocked its dependent fresh-server phase.
A4 asks one narrower question: does one first request on a separately started
server reproduce A3's correct request-1 text and complete token-id hashes?

A4 cannot erase or reclassify the A3 same-server failure. Even if A4 passes,
the matrix cell remains `grade-d-quarantined-capability`, receives no speed,
deployment, headline, or context-quality credit, and does not authorize 24K or
32K serving. A pass only isolates the failure to repeated serving rather than
fresh first-request behavior.

## Frozen identity and execution

- Exact A3 model, revision, source, staged runtime, TP4/EP4/eager/MTP0,
  16,512-token maximum, 33-block/358,465,536-byte cache, offload placement,
  graph/decode selectors, semantic suite, and harness are unchanged.
- Attempt 5, port 19677, and every state, cache, compile, RPC, run, supervisor,
  and evidence path are new and fail closed against reuse.
- The external byte-identical checkpoint remains the model source. The
  recurring corrected local-NVMe receiver notices are counted and disclosed,
  but do not decide this model-level question. Any I/O error, B70 reset/fatal
  event, lifecycle residue, semantic failure, nonzero cache use, incomplete
  token IDs, identity drift, or output-hash mismatch fails A4.
- The only request must use 16,000--16,400 prompt tokens, fit within 16,512,
  pass all five semantic fields, report zero cached tokens, and exactly match
  A3 request 1's text hash
  `4a607a7526ec5a996e6f8b7c744c7afeb3721d33e2bff3a688c13dcc772249e5`
  and token-ID hash
  `380723446d56b37cb63699dac78b6fd57b0df2f6b68103c66d780e333db25bab`.

Frozen hashes:

- launcher `a02da638b8eaa69d9dbe2c068c80251e93d41d5df048f6ca931ac01f2d9d6594`;
- supervisor `a968f6647e3e8148602e417dce309b2ba1b8e9b4d849da42e51ef8cb16ee780c`;
- client `c1786d2d3ca3e70f8abd70de9f26f18c3e61eb1da179ffd85e9d9a440765272c`;
- semantic suite `61d94377bcb5a8252d4796d27ab0a16714c4c603bb20e8f5533641cb9e982e6a`;
- harness `f3bbf3369152a55aa0c9acc8bbad7ff15db2d4d694f03cb5ed275efde7f99459`;
- tracked A3 result reference
  `60898a11ab90238e11bc90b73038de5d00c2e72b1b185cc3851989371c429ef0`.

The no-argument supervisor is the only authorized server entrypoint; the
frozen no-argument client is the only authorized request path. The evidence
manifest and final result will be sealed after controlled teardown.

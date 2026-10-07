# Independent document annotation

Source: `documents.json`, SHA-256
`8fe86d7dc3ebd7d16ee06672ab0f7b8dc950a2ecc6b92c88f8019849dfcdb579`.

All twelve documents were read directly. Each variant's events, balance history,
ownership history and seven answers were entered separately before comparing
pairs. No existing generator, ledger, adapter or answer key was read or used.
Python only serialized the manually entered annotations and checked quote
membership, source ordering, coverage, answer types and completed pair equality.
The raw documents were not modified.

`annotations-independent.json` contains 84 actual balance events with exact
complete sentence quotes, 48 end-of-batch states, 84 answers with reasons,
non-balance facts, and explicit exclusions for proposals and historical mentions.
Character offsets use Python string indexing and an exclusive end. Alias-based
events retain their complete operative sentence plus the complete notice-local
alias declaration as contextual evidence. The reversal retains its historical
and non-retroactive context separately. No unresolved ambiguity was found under
the supplied reading conventions.

Manual balance traces, expressed as `(amber10, birch11)` after batches 1–4:

| Pair | Batch 1 | Batch 2 | Batch 3 | Batch 4 |
|---|---|---|---|---|
| s01 | (10, 20) | (10, 17) | (14, 17) | (14, 18) |
| s02 | (10, 20) | (17, 20) | (17, 26) | (15, 23) |
| s03 | (10, 20) | (17, 20) | (10, 22) | (13, 18) |
| s04 | (10, 20) | (14, 17) | (12, 25) | (18, 20) |
| s05 | (10, 20) | (15, 16) | (19, 19) | (12, 24) |
| s06 | (10, 20) | (18, 15) | (7, 24) | (9, 13) |

For s01–s05, ticket ownership is amber10 through batch 2 and birch11 from
batch 3 onward. For s06 it is amber10, birch11, amber10, amber10. In s06 the
review-to-ticket link has the intermediate case node; the archived directory
and cancelled proposals do not override effective ownership.

After the separate annotations were complete, every stress/control pair had
the same ordered actual balance events, all batch states, and all seven answers.
This is equivalence for the tested postings, histories and questions, not a
claim that the variants contain identical incidental propositions: stress
variants additionally describe proposals, drafts, aliases or historical context.

This artifact remains a development annotation awaiting the second review.
It is neither external validation nor a model-performance result.

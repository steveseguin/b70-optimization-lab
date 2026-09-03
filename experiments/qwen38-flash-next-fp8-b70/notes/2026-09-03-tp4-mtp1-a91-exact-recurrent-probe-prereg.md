# A91 preregistration: logprob probe of the exact-recurrent MTP1 line at depths 8, 256, 2048

Date: 2026-09-03. The A84 probe measured the plain MTP1 identity (A81),
before the exact recurrent path was in use. A85 fixed part of the gap; the
MoE and dense GEMMs are cleared offline; the QSA attention kernel is
per-row with the same split count for one and two rows, and its indexer
selects every token while the context is under the 2048-token budget. If
the exact-recurrent MTP1 line (A85 packet, attempt 91 / port 19763,
`tools/rewrite-q38-a85-to-a91-exact-probe.py`) is logit-exact against the
MTP0 line at depths 8 and 256 and diverges only at 2048 (where the
continuation crosses the budget), the residual is the over-budget index
selection of the two-row verification step; if it still diverges at depth
8, something in the two-row step other than the recurrent kernel, GEMMs,
MoE and attention kernel remains (sampler, norms, the draft's shared
buffers). Compared offline with `compare-q38-logprob-probes.py` against
the A76 MTP0 probe.

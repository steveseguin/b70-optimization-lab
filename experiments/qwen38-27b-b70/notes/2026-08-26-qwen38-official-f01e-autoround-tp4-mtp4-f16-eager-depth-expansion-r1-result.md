# Current-f01e AutoRound TP4/MTP4 eager F16 depth expansion R1

Result: **diagnostic quarantine; zero site cells**.

The exact 32K request killed the engine after returning only 126 of the required
128 IDs. All four workers reported the speculative GDN invariant failure
`Expected spec_token == num_spec_decodes * (num_speculative_tokens + 1)`, and
the engine then failed fatally. The quality helper's first request consequently
received HTTP 500. No `quality.json` was produced, so objective quality and the
same-topology baseline were not evaluated successfully; this is an engine
failure, not evidence of a semantic quality mismatch.

The 4K, 16K, and 24K receipts locally passed exact depth, cache zero, isolated
finite acceptance, and TP4/MTP0 target parity. Their conventional timings
(`28.772138902083974`, `23.942660537746576`, and
`25.730788439576674` tok/s) remain diagnostic only. The preregistration
requires full global quality before any locally valid non-8K depth can freeze.
Because that gate failed, the terminal receipt freezes no depths and grants no
per-depth or publication authority.

At 2K, target parity still diverged at token 90. At 8K, the quarantined parent
was reproduced exactly (`dd31856f…`) with 97/124 acceptance, but it still
diverged from the TP4/MTP0 target at token 99 and remains structurally
quarantined. The 32K timing window is also diagnostic only: the exact request
failed, usage was absent, and only 126 IDs returned.

This seal changes no family data, generated HTML, site cell, chart, headline,
LocalMaxxing submission, descendant authority, or protected route. The
protected decode values `71.45427094575045`, `30.329809361830037`,
`49.05894025767351`, and `71.9001988117144` remain untouched. A separately
preregistered fresh-boot recovery is required before 4K, 16K, or 24K can be
published.

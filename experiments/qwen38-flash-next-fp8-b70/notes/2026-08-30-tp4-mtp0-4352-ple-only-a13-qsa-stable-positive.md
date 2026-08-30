# Qwen3.8 Flash-Next FP8 TP4 MTP0 QSA-stable A13 result

Date: 2026-08-30
Status: bounded treatment positive; fresh-server A14 still required

A13 changed only the XPU QSA group-selection rule from the variable custom
top-k ordering to stable score-descending, logical-index-ascending selection.
The model revision, 51.200-GB PLE-only host placement, TP4/EP4 topology, eager
MTP0 serving identity, 128-MiB cache, native stage, prompts, seeds, and complete
A10 gate remained frozen.

All lifecycle and lossless gates passed. Every rank offloaded exactly 11.92 GiB,
model load again reported 31.57 GiB/card, and the server exposed 4,747 cache
tokens. Recovery passed; the established semantic battery remained 6/7 with
only the inherited `code_execution=30` boundary; the short repeat was 16/16 one
hash; and the exact-4K needle passed with no cache reuse.

The three p146/o256 rows returned the protected short authority and measured
`5.452158 / 5.312499 / 5.380076 tok/s`, median **`5.380076 tok/s`**. That is
2.99% above the protected current-runtime median, though slightly below the A9
same-server screen. Both byte-identical p4096/o128 rows returned the retained
exact-4K authority and measured `5.226466 / 5.226935 tok/s`, median
**`5.226701 tok/s`**, 9.85% above the protected 4K median. Usage was exactly
4096/128/4224 and cached tokens were zero in both rows.

This closes the concrete mechanism-to-treatment loop: A10 and A12 varied only
after QSA subset selection became active, the existing XPU operation varied on
an exact-tie microtest, and stable QSA selection restored the retained full-model
authority twice. It is still bounded evidence rather than final deployment
qualification. Per preregistration, a separately started A14 server must pass
the same full battery before the treatment is called reliable/lossless or added
to the promoted production patch series.

Owned teardown was complete: no server, listener, compile/RPC directory, or
device allocation remained, and all four cards returned below 43 MiB. No
B70-addressed event occurred. Corrected receiver events for local NVMe
`0000:01:00.0` remain a disclosed clean-host caveat. No protected result was
changed or replaced.

Structured receipt:
[`../data/20260830-tp4-mtp0-4352-ple-only-a13-qsa-stable-positive.json`](../data/20260830-tp4-mtp0-4352-ple-only-a13-qsa-stable-positive.json).

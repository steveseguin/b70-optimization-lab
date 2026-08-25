# b2dd TP1 eager-control r1 closeout

Date: 2026-08-25. Classification: **passed quality-clean short-suite parent;
no exact active-context cell filled.**

The frozen b2dd/1e90 Qwen 3.8 AutoRound INT4 TP1 eager MTP0/F16 control
completed all 25 benchmark prompts and the full quality battery. Its preferred
99-interval decode median was `23.851819544748224 tok/s`. That is a dated
graph-off control, not a regression against or replacement for the protected
graph-on `~30.3 tok/s` record. Speed was not a correctness gate.

Correctness was fully clean: the exact canary passed, every benchmark request
reported cache zero, all seven exact quality cases passed, eight repeat runs
had one stable hash, the 8K needle passed, all 24 frozen baseline comparisons
passed, and all 16 quality requests reported cache zero. Runner, phase, and
post-cleanup return codes were zero.

The first wrapper invocation completed this evidence and cleanup but did not
write its receipt. A separate agent pushed two unrelated commits while it was
running, and the old wrapper incorrectly required live `origin/main` equality
again after completion. The frozen image, source, inputs, local launch HEAD,
and runtime did not change. Commit `afcf8aaa4` now keeps live-origin equality as
a launch-only gate, records later remote movement as non-gating, and preserves
a non-passing receipt for genuine local post-run mutations.

The existing output was then finalized report-only. Recovery rechecked the
exact p2/r1 root, predecessor, six frozen inputs, launch HEAD, b2dd/1e90 source,
image digest, phase statuses, evaluator result, and cleanup. It launched no GPU
or container. The recovered receipt is terminal `passed` at SHA-256
`e4513a9a76ff8c5673a06099c8f1f00ba7b25b60cd0635c6914c1e397495ba86`.

This short suite is not `active_context_tokens=0`, and configured max context
does not make it an exact 32K measurement. The separate 8K/32K serving-input
expansion remains eligible. The parent now directly authorizes the
preregistered eager MTP2 and graph+MTP1 parents. E4M3 and E5M2 retain their
separate p4→p5→p6 stage-order gates.

The structured closeout is
[`2026-08-25-qwen38-b2dd9ce73d-tp1-eager-control-r1.json`](../data/2026-08-25-qwen38-b2dd9ce73d-tp1-eager-control-r1.json).
Complete run evidence remains under
`/home/steve/qwen38-current-main-runs/tp1-parent-sentinels-b2dd9ce73d-20260825-r1/02-eager-control/full-short`.

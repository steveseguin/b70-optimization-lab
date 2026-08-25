# Qwen3.6 target-Q8/F16 TP1 SYCL-graph exact-depth R3 preregistration

R3 is a create-only retry of the sealed R2 seven-context packet. It preserves
R2's `-v` argv, source, model, build, runtime, 32-DSO closure, selectors,
environment, contexts, graph requirements, and zero publication/submission/
quality authority.

The sole evidence-policy delta is preregistered in
`data/2026-08-25-qwen36-q8-f16-tp1-sycl-graph-exact-depth-r3-prereg.json`.
R2 depth 0 emitted two positive summaries: prompt bench `24 requested / 8
created / 16 cache_hit`, then decode bench `641 / 3 / 638`. R2 failed closed
because its parser required exactly one summary.

R3 requires at least one summary and validates every summary independently:
device 0/cache limit 8; zero rejection, unsupported, full, update, and recreate;
positive capture and hit/replay; and exact accounting identities
`requested=hit+miss`, `hit=direct_replay`, `miss=recorded=created`, and
`replayed=requested`. Only then are counters summed, with `cache_entries` set to
the observed maximum and `summary_count` recorded. A failure in any summary
fails the context and packet.

Campaign/root/ack end in `r3`. No R2 artifacts may be modified. Passing R3
would produce only seven raw graph cells with quality still pending; it cannot
replace protected graph-off values or authorize site publication or a record.


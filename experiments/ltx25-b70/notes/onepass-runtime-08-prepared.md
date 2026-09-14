# One-pass state runtime08 prepared

September 14, 2026. Packet08 changes only the compiler adapter's state traversal
and its source identity checker. Node, graphs, numerical backend, compiler
options and launcher remain unchanged. All three lifecycle/registry boundaries
remain; only local state enumeration uses one module walk. Packet07 checker and
adapter bytes are preserved under provenance, with every other inherited file
unchanged. Historical adjacent_state metadata stays bound to packet07; the
current adapter identity is in multiblock and onepass_state.

Manifest SHA256: `a32f645772d2ef59d46b66c9181f1d9433950172bcc763924de8aa7acb679b6b`.
Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-compiler-08`.
[Sealed manifest/checks](../data/onepass-runtime-08/summary.json).
Source preparation, launcher check-only and independent builder review passed.
The adapter passed60 existing CPU lifecycle checks plus48 focused acceptance
comparisons for aliases, None/empty registrations, dtype/device and late hooks.
[Edge cases](onepass-state-cpu-edges-01.md), [CPU cost](onepass-state-04-cpu.md).

The pinned v3 client uses the same12-request all48 schedule as v2: two original
boat generations, one cold compiled qualification, then restored/compiled/
restored triples for boat42, marble17 and bird123. Full original four-output
parity, per-block native/repeat checks, default8/256 Dynamo limits, owner/source
identity and fault-halt/retention rules are unchanged.40 stdlib client/receipt
contracts and offline client check-only passed. Native exactness and speed are
pending; preparation is not a promoted result.

After a necessary controlled application reload, run the bounded comparison.
Then use a separately qualified retained-candidate diagnostic to profile the
warmed compiled path without another reload. Profiling timings remain diagnostic
and cannot replace the uninstrumented paired measurements. No host reboot,
driver reset, settings change or approval pause is required for this authorized
application transition. CURRENT.md records actual process state.

# Integration contract — prepared, not adopted

No packet33 device window has run. Do not install predictions as dispatch entries.
The coordinator's K2 writes `run/dispatch-measured.json` using
`packet26.dispatch.v1` with `classes`, `gemv`, and `fusions` maps. Empty means R5 /
the established default remains. `fusions` stays empty here.

| Map/key | New value | Required shape / arithmetic identity v2 |
|---|---|---|
| gemv/expsdown | p33.down.bank | IQ4_NL, K640, rows2560, ten selected experts; BF16 input/output; original adjacent32 tree |
| gemv/expsdown | p33.down.select | Same; rejected assembly diagnostic, retained to test model failure |
| gemv/expsgate | p33.gate.restrict | IQ2_S **and** IQ3_S K2560; paired gate/up; both types must win |
| gemv/gdn.qkv | p33.dense.segment | Expanded Q6_K **and** Q8_0 K2560 split1; both must win |
| gemv/qsa.k | p33.dense.segment | Expanded Q6_K K2560 split4, two candidate events including exact finish |
| classes/route | p33.route.rank4 | N512, top10; original tie order; all three candidate stages |
| classes/qsa.attention | p33.qsa.shape | capacity128/budget2048/tokens1; score, softmax, value; unchanged round2 fallback otherwise |

These are new registry names. Packets26–29 do not yet recognize them; loading
this dispatch into an unchanged runtime must not silently select an alternative.
A future integration must add explicit registry branches, link `p33_submit.cpp`
and the generated round2 implementation, preserve validation, then run the
runtime's full oracle/repeat/fresh-process gates. This packet changes no registry.

The K2 selector admits a class only if every declared workload is byte-exact,
has200 complete measured repetitions, and its median is below90% of its paired
runtime control. It sorts by conservative saved milliseconds per token: minimum
saving across required formats times48 expert/route,36 GDN,12 QSA calls, divided
by1000. These call counts describe the frozen decode schedule, not a new measured
end-to-end result. First admitted row per class wins. New dense split4 retains
its finishing event; stage counts cannot be omitted to improve the number.

GEMV controls call the unchanged runtime's `integrated::experts` / `dense`.
Route control is the existing five-stage specialised path. QSA control is the
existing three-stage round2 path; legacy receipt arm strings `packet18` and
`specialised` mean control and candidate, and do not redefine code provenance.
The unchanged packet18 QSA assembly is studied separately.

Finite identity only: exceptional expert disagreements and historical QSA
stored-fixture discrepancies remain diagnostic, as documented in
[candidates-notes.md](candidates-notes.md). Do not describe these gates as
all-bit-pattern GPU identity. Any model-level admission still needs its existing
quality and determinism gates. No compressed KV or floating-point relaxation.

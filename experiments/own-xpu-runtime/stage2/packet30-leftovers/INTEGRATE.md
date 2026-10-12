# Packet30 integration after measured qualification

This packet does not edit or integrate packet29. Run the prepared [K0/G3](WINDOW.md)
first, inspect all exclusions and baseline representativeness, and retain both
fresh-owner receipts. A prepared kernel is not an adopted kernel.

The output `dispatch-measured.json` uses `schema: packet26.dispatch.v1` and
`classes`, `fusions`, `gemv`. It is a measured overlay, not permission to replace
the whole existing dispatch. Preserve packet28/29 winners and unchanged classes.

1. Route goes through `fusions["route+gather"]`; `p30.route.*` calls
   `p30::route::validate` then `submit`. Bind slots0 logits,2 IDs,3 probabilities,
   5/6 descriptors,15 sticky error,18 active; reserve512 floats. Descriptors are
   `(expert,0,640)` and `(expert,0,2560)`. Consumers must already index source row
   zero from the original input, with shared gate/up input enabled. Do not retain
   a consumer of the removed ten-row gather. The source accepts one BF16 row,
   <=512 logits and <=10 choices; runtime uses512/10. Unsupported geometry stays
   on its old branch.
2. `classes["qsa.attention"]` maps the two named attention variants to
   `p30::attention::submit`. Bind the existing score/probability scratch and all
   unchanged cache/output arrays. `shape.extra` is the scheduler-known upper bound
   on admitted slots (from the same position/budget rule as selection), not a
   device readback. IDs must form a packed prefix ending in -1. Dispatch only on
   supported decode geometry; retain the incumbent for other shapes. No cache
   precision or selection order changes.
3. `fusions["small.hc"]` and `fusions["small.ffn"]` call the compiled small tuple.
   Choose Q6 versus Q8 from existing tensor metadata before launch; preserve all
   split bounds and all sibling shared-input dependencies. Both FFN formats must
   qualify before their common key changes. Do not fuse gate with its low producer.
   `gemv["hc.a.gate"]`, `gemv["hc.f.gate"]`, `gemv["shexpdown"]` compare against
   packet28 wg32, not the superseded R5 arithmetic spelling. Their matched model
   timing anchor is pending, so G3 must not admit them on the old30/16us anchors.
4. `fusions["attn.combine+norm"]` and `fusions["ffn.combine+norm"]` preserve both
   combined stream and normalized output. The first consumes hc.f.norm; the
   second consumes the next hc.a.norm only when it is the immediate scheduled
   successor (the final/PLE boundary requires its own predicate). Check read/write
   sets, shapes, gains, owners and no intervening writer at plan time. No cross-card
   fusion and no triple combine/norm/mix: low/activation/gate lie before mix.
5. `classes["norm"]` and `classes["hc.mix"]` are p30 family proposals and require
   all their a/f workload rows. Add an explicit p30 resolver before the old integer
   implementation selector: `class_name(label)` must equal `hc.a.norm` or
   `hc.f.norm` for the norm proposal, and `hc.a.mix` or `hc.f.mix` for mix. Treat
   these as limited family overrides of the old a/f entries. Never apply the norm
   proposal to final.norm, ple.kn, ple.qn, ple.cn or other Op::norm sites. The old
   op_class fallback does not map hc_mix, so it cannot resolve this key for you.
   Either select the norm class or an overlapping combined chain based on measured
   chain savings, never sum both savings. Summary retains overlap conflicts and
   requires an explicit selection to resolve them. Defaults keep the old dispatch.
6. Extend the closed non-GEMV value allowlist in `Dispatch::load` with only the
   declared p30 candidate strings. Existing `implementation_for` maps unknown
   strings to0; it cannot execute p30. Resolve p30 names into the family wrappers
   before that fallback, under the predicates above. Keep rejection of unknown
   variants and add parser/resolver tests for every emitted key and excluded shape.
   Add p30 source files as compiled translation units; never route them through a
   device descriptor interpreter. The queue bridge returns every constituent
   event for profiling and chains dependencies explicitly. Check Arena ownership,
   liveness, device association and extents, then the raw pointer validators.
   Keep controls/output/scratch separate; preserve guard-before-launch behavior.
7. Compile AND link with no fast math, no contraction, IEEE denormals and correctly
   rounded offload FP32 divide/sqrt. Run integrated K1 exact bytes, all host argument
   gates, full model64-token/384-layer oracle captures and fresh-owner one/two-card
   repeats. Only a matched two-card model wall-time run establishes movement toward
   35ms/token. No estimated kernel saving is model throughput.

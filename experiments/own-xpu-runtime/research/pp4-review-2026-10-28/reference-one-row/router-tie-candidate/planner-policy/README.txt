Reference route policy propagation, 2026-10-28

Scope: qualified reference tie ordering applies to F32 target route operations.
BF16 draft routing is unchanged, and draft proposals remain target verified.
The same explicit OWNRT_REFERENCE_ROUTE_TIE_SORT=0/1 is carried to all owners;
there are no per-owner role switches or mixed target policy. The base planner
already requires F32 target activations. Other unsupported F32 route geometry
continues to fail closed. Existing lookup copy/view configuration is preserved.

Root applied native-precision-scope.patch (two conditions only) and the exact
planner-policy.patch. Do not apply native-precision-scope-comment-unbuilt.patch:
it is retained solely to record an unbuilt comment variant created during a
handoff race. native-source.json names the actual tested source authority025f.
The candidate author did not edit canonical sources. Root owns build/admission.

Planner config reference_route_tie_sort is strictly Boolean and defaults false.
Owners receive explicit0 even if parent environment has1. An existing adapter
flag inconsistent with explicit config is refused, preventing silent treatment
changes. Enabled policy requires both adapter and addressed helper in the build
receipt; the existing full source/hash checks authenticate actual source content.
The plan records f32-target-only and unchanged-bf16 scope. Both persistent and
dedicated process request hashes bind those fields, and persistent per-request
identities inherit the process request identity.

CPU tests: test_policy.py, cpu-result.json, cpu-tests.log. 22 executions pass;
this includes existing and inherited planning tests. Base planning uses existing
fake binary fixtures; derived planners use existing mocked base fixtures. These
verify policy propagation and admission, not GPU execution or model quality.

Required numerical gate: same newly built binary and flag1 in every owner.
Use existing prefill_gate.py with the authenticated1677-token prompt, max32,
262K context, serial then pipelined prefill256 in one PP4 owner lifetime. All
native owners must FINISH cleanly before treating comparison as successful.
Use the pipelined request as reference for existing dedicated-gate/prepare.py
and compare.py, dedicated3+1 with the same prompt/max/context, four transport
slots, copy lookup, full qualification. Compare all2065 target sources and73
draft sources, output tokens, canonical hidden/token provider pairs, restore
survival evidence, and quiescent native FINISH receipts. Dedicated comparison
currently expects target-set.prefill-provenance.json in the reference request,
not merely target-set.json. Preserve its authenticated stage prefill provenance;
do not create a renamed or weakened manifest. Parent/review_direction own that
oracle preparation. The existing2+1 gate can use the same policy but has a
separate capacity envelope; this change alone makes no262K2+1 capacity claim.

After this gate, use fair long-context topology timing with equal token budget
and existing copy lookup. No timing or speed claim follows from planner tests.

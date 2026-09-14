# One-pass state/hook traversal, inactive candidate

The corrected CPU metadata harness measured about0.480 seconds for528 bound
route invocations with three state and registry checks each. Its separate
instrumented profile pointed to recursive state enumeration; cumulative times
for parameters, buffers and named_modules overlap and are not additive.

Only `CompiledBlockRoute._validate` changes. Existing class, route, owner and
global-hook checks remain. One native `block.modules()` traversal checks each
module's local hooks and direct `_parameters`/`_buffers` registrations. `None`
entries are skipped. Every other registered tensor must remain BF16 and, when
requested, on the original device; no registered tensors still fails.

For this pinned native module tree, named_parameters/named_buffers recursively
visit those same module registrations, omitting None and duplicate objects.
Shared modules remain deduplicated by modules(). Shared tensors registered in
different modules can be checked more than once, which cannot change acceptance
because dtype and device requirements are identical everywhere in the block.
There is no tensor comparison, tensor hashing, copy, numerical operation or
cross-call cache. Parameter and buffer aliases, including an object present in
both registries, retain the same acceptance conditions.

All three lifecycle boundaries and full registry checks remain. Each call
observes the current registrations and hooks. Unsupported simultaneous
violations can change which error is raised first because checks interleave;
this does not turn a rejected state into an accepted one. Concurrent mutation
of module dictionaries remains outside the existing single-request static
native inference contract. No atomic guarantee is added or claimed.

This candidate removes two recursive traversals per state-validation call:
3,168 fewer hierarchy traversals over528 selected-block calls. It does not
remove state-validation boundaries or predict application savings. CPU tests,
shared/None registration negative gates and native exact-output/timing gates
remain pending. Only this patch directory was created; live and scripts
adapters, packets, server, settings and cache state were untouched.

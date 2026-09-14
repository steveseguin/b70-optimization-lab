# Adjacent state validation reuse, inactive candidate

Parent packet06 adapter: `12ffb29cb4c8a61e8d9a22586a5f9f96ad170de882d62bfb4981f269d3b1bd3f`.

For a bound route, `_validate_execution()` calls the aggregate lifecycle guard.
Its `_validate(patcher, route)` checks strict mode, the current model/shard owners,
selection, all48 registered routes, callback/wrapper identities and bindings,
then validates the active route with `check_device=True` as its final action.
The candidate returns `True` only after this succeeds. The adjacent caller
therefore skips its duplicate `_validate`; an unbound route returns `False`
and retains its original explicit validation, including its original device flag.

The removed calls immediately followed `_validate_execution()` in `__call__`
and `_call_native`. No argument translation, tensor routing, model call, or
supported user callback intervenes in either pair. All three existing lifecycle
boundaries remain: route entry, native-call entry after transfers, and node-gate
entry. No validation is reused across routing, compilation, model execution,
requests, or sampler stages. Late mutations before any boundary remain subject
to that boundary's full checks.

This proof uses the existing static single-request native inference contract.
It does not introduce an atomic guarantee against concurrent external mutation,
which the parent also lacks. Monkeypatching the validator itself is not an
admitted callback. Root must retain lifecycle negative tests, especially mutation
between route entry and native-call entry and unbound-route fallback behavior.

Warm all48 executes 48 x 11 = 528 selected block invocations. The candidate
reduces five current-block state/hook scans to three per invocation: 1,056
fewer scans. All1,584 inner-call lifecycle/registry checks remain. Census and
pre-run validation are unchanged. This is an operation-count hypothesis, not
a timing result or native quality qualification.

Only this inactive patch directory was created. No live or scripts adapter,
packet, model, server, compiler setting, host setting, or cache was changed.
No Torch import, test, or native execution was performed. The manifest binds
both source snapshots and the exact diff; root owns subsequent validation.

# Qwen3.8 active packaged GDN stage trace D38r result

D38r is **technical-invalid** for the same request failure as D38. It exposed a
second fail-path gap: the benchmark client exits nonzero for the empty response,
and `set -e` terminated the runner before the missing-trace logging branch.

The client invocation is now guarded explicitly; on nonzero exit it saves
container logs before failing. D38s is a single-process exception-capture gate.
It must not continue beyond process 1 if the hook still fails.

# Qwen3.8 Flash-Next FP8 A72 receipt-repair preregistration

Date: 2026-09-03
Status: frozen before launch; the intended promotion record for the
deterministic graph line

## Question

A70 and A71, two independently started servers of the deterministic graph
identity, agreed on every output and passed every quality and speed gate,
but both clients stopped at the final runtime-receipt verifier because the
`--cudagraph-metrics` dispatch table never appears in this line's server
logs. A read-only Codex audit
(`2026-09-03-codex-cudagraph-metrics-receipt-audit.md`) found the cause: the
XPU worker selects the V2 model runner, which never constructs the
`CUDAGraphStat` that the legacy runner reports, so
`ModelRunnerOutput.cudagraph_stats` is always `None` and the API-side
logger has nothing to print. Does the same server, with the runner
reporting the stat, pass the whole frozen client including the receipt?

## Design

Overlay commit `2169dbfe38c2954edc5ae50e94f68d45be071b79` (on `805cde59...`)
builds `CUDAGraphStat` in the V2 runner after graph dispatch when
`cudagraph_metrics` is on, carries it in `ExecuteModelState`, and attaches
it to `ModelRunnerOutput` in `sample_tokens`; no dispatch or numerical path
changes. `verify-moe-m1-w13-n32-selection.py` accepts that head (its MoE
file hashes remain the guard; 7 tests pass; SHA-256 `4f494228...`).

`tools/rewrite-q38-a67-to-a72-receipt-repair.py` derives A72 from frozen A67
as A71 was, with the head moved to `2169dbfe...` in the launcher (two
literals) and the client (three literals), the new verifier hash pinned, the
64 GiB bounded-read cap, the restored helper pin, the
`mkldnn_deterministic=1` receipt, and the exact-2K candidate pin
`afffd2110812...`. Attempt 72 / port 19744. Packet: launcher `d4a363c6...`, client
`676c38ec...` (hash pin only), supervisor `085c7687...`, host wrapper
`343f572a...`.

## Reading

- `client-gates-passed.txt` and `fullgraphdet-runtime-after.json` with
  `size_1_full_dispatch_count > 0`, plus the same outputs as A70/A71: the
  deterministic graph line has a complete promotion record (three servers
  agreeing on every output; two-attempt short median from A70/A71 plus this
  attempt's rows).
- Any output or hash difference from A70/A71: the receipt change is not
  numerically neutral after all (it must not be; investigate).
- Receipt still absent: the table print path is broken elsewhere (the
  audit's ruled-out list is then wrong at one point).

Nothing protected changes. The 2K-authority decision remains the user's.

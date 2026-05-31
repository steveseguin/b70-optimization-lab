# 2026-05-31 pidfd CCL Easy Win

## Result

The REAP lane has a small but repeatable CCL-side improvement from forcing
oneCCL Level Zero IPC to `pidfd` while keeping the REAP-specific fabric-vertex
override:

```bash
CCL_IPC=pidfd
CCL_ZE_IPC_EXCHANGE=pidfd
CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0
VLLM_BENCH_TEMPERATURE=0
```

Best promoted-config run:

- Log: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260531T232017Z.log`
- JSON: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260531T232017Z.json`
- Elapsed: `17.16216013500525 s`
- Total throughput: `119.3322975598359 tok/s`
- Output throughput: `89.49922316987691 tok/s`

This improves the prior corrected greedy best (`89.18670709734161 tok/s`) by
about `0.35%`.

## Same-Window Screen

| Candidate | JSON timestamp | Output tok/s | Decision |
| --- | --- | ---: | --- |
| `CCL_IPC=pidfd` | `20260531T230921Z` | `89.42738863012866` | positive |
| `CCL_IPC=pidfd` repeat | `20260531T231105Z` | `89.32689830491869` | positive |
| default IPC control | `20260531T231243Z` | `89.27580338562741` | lower |
| `CCL_IPC=sockets` | `20260531T231421Z` | `88.90492979756878` | reject |
| promoted config, default wrapper path | `20260531T232017Z` | `89.49922316987691` | new best |

## Quality

Explicit `pidfd` quality smoke passed:

- File: `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/quality-smoke-20260531T231727Z.json`
- `passed=true`
- Generated tokens: `1473`
- Deterministic: true
- NUL/control/degenerate output: none

The earlier smoke at `quality-smoke-20260531T231558Z.json` also passed, but it
did not translate the `CCL_IPC=pidfd` shorthand. The wrapper now translates
`CCL_IPC` for quality and serve paths, and the benchmark log records both
`ccl_ipc` and `ccl_ze_ipc_exchange`.

## Promotion

REAP defaults now set:

- `CCL_IPC=pidfd`
- `CCL_ZE_IPC_EXCHANGE=pidfd`
- `CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0`

Files changed:

- `configs/reap.env`
- `scripts/quality-smoke.sh`
- `scripts/serve.sh`
- `/home/steve/llm-optimizations/scripts/bench-vllm-minimax-autoround-xpu.sh`

Keep `CCL_IPC=sockets` rejected. Keep deeper optimization focused on MoE and
attention/collective fusion; this was a useful runtime setting win, not a
source-level bottleneck fix.

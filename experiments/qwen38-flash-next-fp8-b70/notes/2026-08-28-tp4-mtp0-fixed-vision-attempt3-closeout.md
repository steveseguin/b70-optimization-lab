# Flash-Next TP4 eager MTP0 fixed-vision attempt 3 closeout

Date: 2026-08-28

## Result

Attempt 3 failed before EngineCore workers or model loading. The API process
accepted the frozen serving arguments, then failed while binding its first ZMQ
IPC socket. The generated filesystem path was 109 bytes:

`/tmp/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-vision-512-r1-attempt3-rpc/bb02c023-ccc8-49b1-98ef-6e96d4390ebd`

The runtime limit is 107 bytes, so it was two bytes over. `server.log` contains
no Worker_TP, EngineCore PID, model-weight loading, checkpoint-shard loading,
per-worker selective-offload receipt, healthy API, or application-start
record. Its generic argument summary does mention the configured offload
options. No client ran and no text or vision request occurred.

The launcher's old failure order reported missing per-worker offload receipts.
That was downstream absence: there were no workers from which such receipts
could exist. It is not evidence against the selective UVA placement. The
machine-readable result is
`data/20260828-tp4-mtp0-fixed-vision-attempt3-result.json`.

## Preservation and credit

All 84 regular files in the run and supervisor trees verify against
`data/20260828-tp4-mtp0-fixed-vision-attempt3-primary-evidence.sha256`, whose
SHA-256 is
`01e64cb82513c747bda0aac8e035b34336eba62e5f3c06648c4bd8bb78da5326`.
The admission manifest itself verifies 28/28 files. Both prelaunch runtime
scans and the postflight scan were structurally clear. Teardown left no
listener, runtime owner, compile directory, or RPC directory; the kernel
journal was clean and the cards returned to 42.875-42.883 MiB.

This is a Grade-D administrative path-length negative. It grants no vision,
quality, deployment, speed, matrix, or website credit and changes no protected
result.

## Attempt 4 treatment

Attempt 4 changes only the temporary compile and RPC roots to
`/tmp/q38v-a4-c` and `/tmp/q38v-a4-r`. The maximum derived fixture path uses a
36-character UUID and is 51 bytes, leaving 56 bytes below the 107-byte limit.
The base now writes a prelaunch JSON receipt and fails closed if this derived
path exceeds the runtime limit. Failure classification also checks the exact
IPC-limit signature and the absence of any worker before consulting offload
receipts. Every model, runtime, selective-UVA, cache, modality, test, timeout,
classifier, interpretation, and protected-performance field remains frozen.

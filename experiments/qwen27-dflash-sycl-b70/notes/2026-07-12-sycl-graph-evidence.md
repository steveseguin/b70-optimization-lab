# 2026-07-12 SYCL Graph Control And Evidence

## Purpose

Prove whether a Qwen27 run merely requested a SYCL graph, was rejected by the
compatibility gate, entered command-graph recording, or submitted an executable
graph. Topology reuse elsewhere in llama.cpp is not command-graph replay.

## Launcher Correction

Current `/home/steve/src/llama.cpp` reads these controls:

- `GGML_SYCL_ENABLE_GRAPH` (default `0`);
- `GGML_SYCL_ENABLE_DNN` (default `1`);
- `GGML_SYCL_ENABLE_OPT` (default `1`).

The Qwen GGUF server and Q4_0 matrix launchers previously exported
`GGML_SYCL_DISABLE_GRAPH`, `GGML_SYCL_DISABLE_DNN`, and
`GGML_SYCL_DISABLE_OPT`. This source does not read those names. The launchers
now export and record the current `ENABLE` names. The server and generic
matrix keep graph requesting off unless
`GGML_SYCL_ENABLE_GRAPH=1` is explicitly supplied.

The matrix also copies llama.cpp stderr into its `.meta.txt` artifact so graph
status is durable instead of appearing only on the terminal.

The server launcher accepts fixed `SPEC_PROFILE` identities for the required
baseline matrix: `no-spec`, `mtp3`, `dflash5`, `dflash8`, and `dflash15`.
`custom` preserves the lower-level `SPEC_TYPE` interface, and the historical
`ENABLE_MTP=0|1` behavior is retained when neither is selected. The DFlash
profiles use `draft-simple` with the locally stored DFlash Q4_K_M draft,
`SYCL0`, all draft layers, and `q8_0` draft K/V caches. The distinct
`draft-dflash` executor is not interchangeable with this GGUF draft path.
Every resolved value is written to the server log.
Both Qwen launchers now default to the active local Q4_0 target instead of the
older Q4_K_XL target or a stale Q4_0 path.

## Runtime Evidence

When built with `GGML_SYCL_GRAPH=ON`, the backend reports power-of-two progress
markers and an exact clean-shutdown summary:

```text
[SYCL-GRAPH] requested ...
[SYCL-GRAPH] compatibility_rejected ...
[SYCL-GRAPH] recording_entered ...
[SYCL-GRAPH] replayed ...
[SYCL-GRAPH] summary ...
```

The summary separates requested, compatibility-rejected, device-unsupported,
recorded, initially created, updated, recreated, and replayed counts. If graph
support was omitted at compile time, startup reports
`status=disabled_by_compile_flag` alongside the requested environment value.

For the current recurrent Qwen target and MTP draft, `CONCAT` is expected to
produce `compatibility_rejected` evidence until that operation's blocking wait
is removed or moved outside capture. A run is not graph-replayed unless its log
contains `recording_entered` and `replayed` evidence.

## Validation Status

- `bash -n` covers both changed launchers.
- The graph-enabled B70 build compiled the modified `ggml-sycl.cpp` object.
- No GPU workload was launched for this instrumentation change.
- End-to-end evidence remains pending the manager's assigned GPU run.

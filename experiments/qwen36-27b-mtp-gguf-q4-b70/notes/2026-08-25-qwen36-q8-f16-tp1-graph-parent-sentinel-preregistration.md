# Qwen3.6 target-Q8 F16 TP1 graph parent sentinel preregistration

State: **preregistered, not launched**. This is one bounded parent sentinel,
not a context-depth curve and not website evidence.

## Question

Can the retained graph-enabled llama.cpp/SYCL artifact execute persistent SYCL
graphs for the target-only Unsloth Qwen3.6 27B Q8_0 model on one B70 while
preserving exact deterministic output relative to a same-binary graph-off
control?

This question is intentionally narrower than throughput. A pass establishes a
usable graph mechanism and parity parent for a later exact-depth packet. It does
not authorize any of the seven context cells, a speed claim, a site edit, a
LocalMaxxing submission, or replacement of a protected historical result.

## Frozen identity

- campaign: `qwen36-q8-f16-tp1-graph-sentinel-20260825-r1`;
- run root:
  `/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-graph-sentinel-20260825-r1`;
- model: target-only `unsloth/Qwen3.6-27B-GGUF` revision
  `82d411acf4a06cfb8d9b073a5211bf410bfc29bf`, file
  `Qwen3.6-27B-Q8_0.gguf`, SHA-256
  `f93f517f38e696d35a1a7df2c0e3155a64f4c4dcd662107a146ae263f7fb14ce`;
- thin launcher:
  `/home/steve/src/llama.cpp/build-sycl-b70-qwen36-mtp/bin/llama-cli`,
  SHA-256
  `6d38f7c31e7c5b7ca7299c8b38dd31c356d86e0514bd406546c789eca7b73dcc`;
- both arms use that exact launcher, model, argv, F16 K/V cache, seed 42,
  temperature zero, 64 forced output tokens, and fresh arm-local runtime
  directories;
- control: `GGML_SYCL_ENABLE_GRAPH=0`,
  `GGML_SYCL_GRAPH_CACHE_SIZE=0`;
- candidate: `GGML_SYCL_ENABLE_GRAPH=1`,
  `GGML_SYCL_GRAPH_CACHE_SIZE=8`.

Cache size 8 is frozen because the July persistent-cache evidence used and
mechanically qualified that bounded setting. This preregistration does not
perform a cache-size sweep.

The manifest freezes the thin launcher, graph-enabled CMake/build receipts,
and the complete 34-row effective local/external DSO closure as canonical
realpaths plus SHA-256. Inherited `LD_LIBRARY_PATH` and `LIBRARY_PATH` fail
closed, as do loader/Python injection and `GIT_*` repository redirection; the
runner uses absolute control tools and constructs sanitized control, verifier,
compute, and pinned oneAPI environments.

## Source-provenance limitation

The retained build came from the protected private llama.cpp tree at base HEAD
`e3546c7948e3af463d0b401e6421d5a4c2faf565`, with a dirty source overlay. A
complete exact source snapshot for that historical build was not captured.
Therefore the base commit is not presented as a reconstruction recipe. The
artifact hashes, graph-enabled build receipts, effective DSO closure, and
runtime graph evidence are authoritative for this sentinel. The current dirty
source worktree is not asserted to match the binary byte-for-byte.

This limitation is acceptable only for the bounded mechanism sentinel. A
future publishable recipe should use a closed source packet or a clean current
source build with its own qualification.

## Mandatory preflight and lifecycle

Execution requires:

1. the exact acknowledgement
   `RUN qwen36-q8-f16-tp1-graph-sentinel-20260825-r1`;
2. clean, pushed repository `main` and an absent create-only ext4 run root;
3. no inherited accelerator/runtime/library-path variables;
4. the canonical host, benchmark, legacy GPU0, and current GPU0 lease locks;
5. no llama/vLLM server, benchmark, CLI, or running Docker container;
6. the expected GPU0 render-node mapping and no render-node owner;
7. direct/O_DIRECT (or direct-dd fallback) model SHA-256 first, followed by an
   ordinary unbuffered SHA-256, both equal to the frozen digest; the verifier
   runs as an isolated child process group with a 1,200-second hard bound;
8. a real GPU0 compute gate under `ZE_AFFINITY_MASK=0`: exactly one visible XPU
   must compute `sum(ones(1024,1024)+1) == 2097152.0`;
9. fresh processes and empty, separate HOME/XDG/SYCL/TMP directories for the
   two model arms;
10. hard process-group bounds for model verification, the compute gate, and
    each model arm. Timeout
    sends TERM to the complete group, waits ten seconds, sends KILL if needed,
    and requires the process group to be empty. Parent SIGINT/SIGTERM is turned
    into a caught campaign failure, with child cleanup in `finally`;
11. a terminal receipt and post-arm cleanup/idle gate;
12. a postflight seal requiring the same clean/pushed `main` HEAD, byte-exact
    Git blob identities for all four packet files, the same model filesystem
    identity, and a freshly rehashed binary/build/protected/34-DSO closure.

No server or container is started. No source build is part of the campaign.

## Frozen safety exclusions

All three variables below must be absent from the caller and from both arm
environments:

- `SYCL_GRAPH_FORCE_NATIVE_RECORDING`;
- `GGML_SYCL_GRAPH_RECORD_QUEUE`;
- `GGML_SYCL_GRAPH_REPLAY_NO_UPDATE`.

In particular, native recorder forcing is not the mechanism under test. Its
prior TP2 device-loss/reset failure makes it an explicit unsafe exclusion. The
candidate uses the ordinary SYCL graph path plus the evidence-supported bounded
persistent executable cache.

## Exact gates

The control must report graph support compiled in, runtime graph and cache
values `0/0`, and a shutdown summary with every graph counter zero.

The candidate must report all of the following in stderr:

- `[SYCL-GRAPH] requested`;
- `[SYCL-GRAPH] recording_entered`;
- `[SYCL-GRAPH] replayed`;
- `[SYCL-GRAPH] direct_replay`;
- `[SYCL-GRAPH] summary`.

The parsed shutdown summary must have:

- `compatibility_rejected=0` and `device_unsupported=0`;
- `cache_limit=8`;
- positive `requested`, `recorded`, `created`, `replayed`, `direct_replay`, and
  `cache_hit` counts.

A graph request without actual recording and replay fails. Compatibility
rejection is not a graph-on result.

Finally, the two fresh-process stdout byte streams must be nonempty and match
exactly, including one common SHA-256. “Cache-zero” here means no prompt-cache,
response, history, or state reuse and fresh arm-local process/cache roots. It
does not claim an HTTP `cached_tokens` field because this sentinel deliberately
uses `llama-cli`, not a server.

There is no throughput floor and the runner does not extract or publish a
speed. That prevents the mechanism check from lowering, replacing, or
relabeling any captured decode frontier.

## Frozen interpretation

- **Pass:** classify only as `passed-parent-sentinel-only`. Then write a new,
  separately reviewed preregistration for the seven exact Qwen3.6 target-Q8
  F16 TP1 graph cells at active depths 0/2/4/8/16/24/32K.
- **Graph missing, rejected, unsupported, requested-but-unreplayed, output
  mismatch, timeout, or cleanup failure:** terminal failure; publish zero graph
  cells and do not expand.
- **Crash/device failure:** preserve the create-only root and terminal cleanup
  evidence. Do not retry under this preregistration.

## Files and inert command

- manifest:
  `data/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-prereg.json`;
- runner:
  `scripts/run-20260825-qwen36-q8-f16-tp1-graph-parent-sentinel-r1.py`;
- CPU-only tests:
  `scripts/test_qwen36_q8_f16_tp1_graph_parent_sentinel.py`.

The runner is inert by default. Static validation is:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q8-f16-tp1-graph-parent-sentinel-r1.py \
  --check
```

This note does not authorize `--execute`; launch authority remains with the
parent campaign manager after the packet is committed and independently
reviewed.

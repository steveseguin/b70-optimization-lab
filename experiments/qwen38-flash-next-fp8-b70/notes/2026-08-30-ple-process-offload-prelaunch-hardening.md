# Qwen3.8 Flash-Next FP8 PLE process-offload prelaunch hardening

Date: 2026-08-30
Status: CPU/source gates passed; no full-model process-offload launch yet

The official PLE design moves the 51.2B-entry n-gram table into one dedicated
CPU process and overlaps its lookup/output transfer with accelerator work. The
current XPU port is only a correctness bring-up candidate: it uses shared host
semaphores and a blocking host-to-XPU copy, so it must not be described as the
finished asynchronous implementation or assumed faster than the retained UVA
lane.

Four source patches now close the known prelaunch blockers:

1. `0027` lets the empty GPU placeholder skip CPU-owned shard-coverage state.
2. `0028` gives XPU host-semaphore waits a finite runtime deadline, propagates
   ordinary CPU-worker failure to every registered TP target, and leaves CUDA
   stream synchronization unchanged.
3. `0029` uses the safetensors index to select PLE names and files before tensor
   materialization. It fails closed for non-lazy, non-indexed, multithreaded,
   or secondary-source loading rather than silently scanning the whole model.
4. `0030` makes the selected-name observation set conditional on filtered mode.
   Ordinary UVA checkpoint iteration retains its original materialization loop
   without per-name set allocation or insertion.

Patch SHA-256 values are:

- 0027: `d560814d5dbd5bbdebcc0aba29a608b5cc13bc685238d1caddff1c2bab2b99dd`;
- 0028: `ce1dbfb070e2d06d82279a126d0d90868070933cdafaae2281cf17cb4a32d2f1`;
- 0029: `1129c3107a42907650ba6ad43438831c9c58a49a5458c0881cbad568d02bbc1b`.
- 0030: `69e591e23d5f3ceae7b7cee84c043da3b4cb701f528661d7230b822d84406aa5`.

Focused validation passed:

- 34 PLE/liveness tests passed and one device-specific test skipped;
- 31 filtered-loader and worker tests passed;
- ruff and format checks passed;
- a read-only run against the real checkpoint index selected exactly 132 PLE
  entries in 33 of 131 files, from shard 00005 through shard 00037, without
  materializing a checkpoint tensor.

This removes the former risk that the CPU child would scan/materialize the
entire 173 GiB checkpoint concurrently with four accelerator loaders. It also
turns a child exit or stall into a bounded server failure instead of an
unbounded four-rank wait.

The first GPU comparison remains ordered behind A25. It will use a separately
materialized launcher with `VLLM_PLE_CPU_OFFLOAD=1`, V2 model runner, lazy
indexed safetensors, and a frozen runtime timeout. Advancement requires the
same exact short/4K output authorities and quality battery as UVA before any
timing is credited. Because the initial XPU copy is synchronous, a slowdown is
an expected possible result; that would identify asynchronous XPU transfer and
overlap as the implementation target rather than invalidate the protected UVA
lane.

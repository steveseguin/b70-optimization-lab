# Target-only contiguous pipeline qualification

`pipeline_driver.py` reuses the current packed F32 engine and a recorded LAN adapter
launch recipe. A CPU-only planner is the default. `--run` explicitly admits one
persistent set of stage processes for one prompt and bounded generation, then dumps
all target state and finishes cooperatively. No retries, restarts, forced kills,
driver resets, memory-setting or power-setting changes are implemented.

This is a target-only correctness foundation for later overlapping speculation.
Sequential HALF/ACCEPT host relays are not a single-conversation speedup claim.
The old two-stage speculative service remains the default. CPU tests cover 1/2/4/6
partitions; runtime qualification is separate. Current native model geometry and
quant admission remain unchanged (SC117 Flash-Next, 48 layers). This does not claim
arbitrary models, quants or one-card fit. In particular this model's one-stage
54.7 GB packed payload exceeds the driver cap.

## Plan and admission

Write a config with schema `ownrt.pipeline-driver-config.v1` and fields:

```json
{
  "schema": "ownrt.pipeline-driver-config.v1",
  "adapter_plan": "/absolute/path/recorded-adapter-plan.json",
  "build_receipt": "/absolute/path/new-build/build-receipt.json",
  "boundaries": [0, 13, 25, 37, 48],
  "bdfs": ["0000:23:00.0", "0000:27:00.0", "0000:43:00.0", "0000:47:00.0"],
  "output": "/absolute/private-parent/new-pp4-run",
  "prompt_tokens": [248045, 8948, 198],
  "context": 4096,
  "max_new": 32,
  "vocab": 248320,
  "eos": 248044,
  "seconds": 1800,
  "grace_seconds": 120,
  "memory_start_bytes": 107374182400,
  "memory_floor_bytes": 8589934592,
  "root_floor_bytes": 27000000000,
  "evidence_floor_bytes": 2147483648
}
```

Prompt IDs above illustrate the format, not the qualification prompt. The owner
chooses one fixed actual prompt for both topologies. Use `[0,23,48]` and the two
reviewed BDFs for a matched two-stage target-only reference. This is a pair of
necessary distinct configurations, each started once, not a fresh-server sweep.

```
python3 engine/tools/pipeline_driver.py --config CONFIG.json --plan PLAN.json
```

The plan hashes its config, recorded adapter plan, current binary and build
receipt, placement and shard authority, observer and planner sources, and any
selection/dispatch files. It preserves arithmetic flags but removes draft and
prefill paths, and binds each stage to exactly one BDF. Per-stage packed GPU
weights must be <=31 GB; host embedding/PLE tables are excluded, and final head
weights are assigned only to the final stage. This is not a VRAM/RAM fit proof:
the engine's existing allocation budget remains enforced. The first stage must
retain host lookup preparation, including PLE layer 1. Cross-cut tensor references
and the unqualified cross-layer `OWNRT_GSQ_FUSE_NORM=1` transform are refused.

After reviewing an external passive baseline and freeing the intended cards,
create admission schema `ownrt.pipeline-admission.v1` with `owner_authorized:true`,
`plan_sha256`, `baseline` (absolute passive observe JSON path), `baseline_sha256`,
and timezone-aware `expires_utc`. Run in one dedicated systemd user unit with
`Restart=no`, `KillMode=process`, `SendSIGKILL=no`, and no forced timeout kill:

```
python3 engine/tools/pipeline_driver.py --run --plan PLAN.json \
  --admission ADMISSION.json --unit THE-OWNING-UNIT.service
```

The driver must inherit nice 19. It verifies the owning unit's MainPID and
InvocationID. SIGINT/SIGTERM sets a stop event; the driver then writes a single
cooperative stop byte to each stage. An embedded coordinator can instead supply
`--coordinator-stop-fd FD`; EOF/readability stops work. Keep an independent external
observer during hardware qualification. The internal passive observer checks
kernel faults, BDF holders, boot/DRM identity and memory/disk floors throughout,
and stops on any new fault or ambiguous target holder. Timed-out children are
reported as live PIDs; the driver never kills or restarts them.

## Protocol and evidence

Each stage has its own socket, stop pipe and shared mapping under `stageN/`.
Native `--output` is the separate, initially absent `stageN/native/` directory;
the engine creates it. Stage IPC/process logs never pre-create native output. Every request/reply
includes stage identity and final-stage boolean. Nonfinal HALF replies must publish
exactly the negotiated F32 stream extent (<=65536 bytes) and no output token. The
host copies those complete raw bytes to the next stage's input slot. Only the final
stage returns a token; it alone owns the head. Every HALF is accepted before the
next input token. No speculative HALF or native two-stage controller entry is
admitted by this path.

After generation the driver requests a full dump at position marker2147483647,
then FINISH on every stage. `stageN/native/launch-plan.json` contains dtype/shape descriptors;
`stageN/native/pipeline-stage.json` records boundaries, roles and explicit inactive
alternate-bank names. `stageN/native/state-2147483647/` preserves raw state and checksums.
`tokens.jsonl`, `result.json`, process logs, plan/admission, launch identity and
passive observations are retained. `compare_pipeline_state.py` performs the
whole-model comparison using a matched target-only two-stage reference and the
stage sidecars. Compare committed canonical state; inactive spare banks are only
excluded by the explicit target-only sidecar declaration and recorded by the
comparator. Output token equality alone is insufficient.

## CPU validation

```
g++ -std=c++20 -O0 -DOWN_RT_HOST_ONLY -I engine/src \
  engine/planning/test_pipeline_layout.cpp -o /dev/shm/ownrt-test-pipeline-layout
/dev/shm/ownrt-test-pipeline-layout gsq-rco-iq3s/loader/placement.tsv
python3 -m unittest discover -s engine/tools -p test_pipeline_driver.py -v
```

The C++ test proves identical launch/buffer fields for the established 23/25 split,
complete unique layer and weight ownership across 1/2/4/6 partitions, and rejection
of invalid ranges and cross-cut tensor dependencies. Python tests cover plan hashes,
launch transformation, BDF/extent/fit rejection, and stale stage/final/sequence wire
rejection. These checks do not replace native state qualification.

# Qwen3.8 Flash-Next TP4 PIECEWISE MTP0 attempt 7 preregistration

Date: 2026-08-28
Status: frozen; not launched

## Why this arm exists

Attempt 6 stopped before the model because schema-v2 runtime classification
enumerated PID `1922600` and then found its first required identity file,
`/proc/1922600/stat`, already absent. The receipt contained zero conflicts,
one initial-stat ENOENT, and no observed identity for that PID. Under the frozen
v2 contract this was `rc=2`. No model, compile-thread treatment, health request,
client, quality gate, replay, or speed row ran. Its exact result and 73-entry
evidence manifest are preserved in
[`20260828-tp4-mtp0-current-piecewise-graph-attempt6-result.json`](../data/20260828-tp4-mtp0-current-piecewise-graph-attempt6-result.json)
and
[`20260828-tp4-mtp0-current-piecewise-graph-attempt6-primary-evidence.sha256`](../data/20260828-tp4-mtp0-current-piecewise-graph-attempt6-primary-evidence.sha256).

## Sole retry treatment and classifier-v3 rule

The intended model-performance treatment remains exactly
`TORCHINDUCTOR_COMPILE_THREADS=1`, applied after the frozen base scrubs inherited
`TORCHINDUCTOR_*` values and proven through the same launch, live-process, and
result-summary gates. Relative to attempt 6, the only material retry change is
the prospective shared runtime-classifier policy below; fresh attempt, port,
and paths are administrative identity.

Schema `neural.download.q38-runtime-conflict-scan.v3` first enumerates numeric
proc directories, then applies this exact distinction:

- for a non-excluded PID only, initial `stat` ENOENT before any identity has
  been observed is recorded in `vanished_races[]` with the PID and skipped;
- scanner, supervisor, and direct-parent PIDs are structurally bound by exact
  PID, PPID, and start time before enumeration. Their later initial-stat ENOENT
  is `stat-after-binding`/`rc=2`, with the bound identity retained;
- after initial stat succeeds, a bound identity must still exactly match its
  saved tuple. Changed PPID or start time is `identity-after-binding`/`rc=2`;
- every later missing/unreadable required field, stat/status PPID mismatch,
  second-stat identity change, and proc-root/binding error remains `rc=2`;
- a real runtime owner remains `rc=1` even when another PID is a benign
  vanished race; a vanished race plus any strict error remains `rc=2`.

The fixture-only `stat.scan` path can deterministically represent a
post-binding transition under a synthetic `--proc-root`; it cannot exist in
live procfs and does not weaken live reads. The shared suite covers excluded
disappearance, bound PPID/start-time changes, vanished-plus-owner,
vanished-plus-later-error, PID reuse, unreadable/missing later fields, exact
runtime positives, false self-matches, and binding. It also performs eight
bounded full live scans while creating short-lived process churn. Three frozen
prefreeze repetitions passed and recorded 8, 8, and 16 live vanished races.

Every attempt-7 clear gate requires classifier `rc=0`, exact schema v3, zero
conflicts, zero errors, an array-valued `vanished_races`, valid entries limited
to `classification=vanished_race` and `field=stat`, exact structural binding,
and at least one fully scanned process. The derived launcher applies this gate
before model start. The outer supervisor applies it when exact process-group
resolution is unavailable, before any swapoff, and in final evidence.

## Frozen model, runtime, and request identity

Everything else remains the attempt-6 contract:

- model `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`, revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`, kernel source
  `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`, runtime build
  `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, Triton MoE, `allgather_reducescatter`, MTP0, PIECEWISE graph,
  capture size `[1]`, `max_model_len=4352`, and
  `max_num_batched_tokens=64`;
- selective UVA offload of the PLE n-gram embedding and token embedding,
  `cpu_offload_gb=12.25`;
- BLHNC KV layout and exactly `201326592` KV-cache bytes;
- no reasoning parser, prefix caching, async scheduling, speculative decode,
  legacy graph controls, or diagnostic flags.

After health, identity, graph, cache-capacity, model-list, journal, classifier,
and compile-thread gates, the unchanged client runs the exact cache-zero `OK`
recovery canary, eager-a4 comparator and short quality battery, 96 exact color
plus 96 exact JSON replays, runtime PIECEWISE evidence, and three p146/o256/c1
short rows. Row 1 has one warmup; rows 2-3 have none. Every measured row still
requires zero `pswpin`/`pswpout` delta and no temporary-swap-use increase.

## Resource and lifecycle contract

The 64-GiB fully allocated root-ext4 temporary swap remains priority `-1` with
the same 64-GiB-plus-40-GiB precreate floor, 40-GiB postcreate root floor, and
16-GiB swapoff reserve. The phase-aware watchdog still stops below 30 GiB
available after all four loads or the first compile marker, or on an 8-GiB
one-sample loss while below 40 GiB. TTM eviction/allocation failures, OOM,
B70-addressed events, fatal/unattributable storage events, the absolute memory
and combined swap floors, sustained PSI, and heartbeat gates remain unchanged.

Direct server-group TERM/KILL, controller and watchdog PID/start-time/command
binding, bounded journal reads, terminal structured classification, swap-use
measurement boundaries, swapfile identity/allocation checks, bounded swapoff,
exact unlink, and original-layout restoration are unchanged. Any unresolved
runtime, controller, watchdog, classifier error, or process-group member
preserves the swap and fails closed.

## Fresh identity and paths

- port: `19684`;
- state: `/tmp/q38-mtp0-current-piecewise-graph-a7*`;
- ext4 resource root: `/var/tmp/q38-piecewise-graph-a7-resource`;
- ext4 temporary swap: `/var/tmp/q38-piecewise-graph-a7-64g.swap`;
- USB run/cache/supervisor roots: exact `attempt7` successors;
- post-closeout archive:
  `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1-attempt7-resource-archive`.

Every path must be absent before launch. No attempt-6 path may be reused or
altered.

## Frozen hashes

- base launcher:
  `533be64e1c7584448c07a5f8895301a32288f4b0472948a91d87235e78c6f09f`;
- shared runtime classifier v3:
  `ecd18d133eef946bacf2750717bc458eca8e64dc1d97beabe060bdf314bf2ab3`;
- shared classifier fixture/live-churn suite:
  `c30a1d552388c10df0e61f882b633cf57304fd76e40eadc886676b78b27ff63e`;
- attempt-7 wrapper:
  `12b4ff60157e7b9aedec0f827460ac8534dca08486eadf12d243777c82c9dd23`;
- mechanically derived compile-thread launcher:
  `33d53c462d0cf24bdce2f81c4323c86ba598df724b28e9badc461e9f48ced971`;
- attempt-7 client adapter:
  `7a4a5e9bc4bff783d59aae5a1390e9c0c232273015d7076fee2151d1153280cd`;
- mechanically derived client:
  `d93a97e6ea0414e579007fdf036b0e9c379bff8dda2d958e5e100de7f71da95a`;
- attempt-7 watchdog:
  `d1ba962fb9bfb0abf80d78789017014a7512e9e2f0fef1edfe66946b2e334dd9`;
- mechanically derived inner supervisor:
  `c9aeefd80f121e7a90673f654753ccdf65d00720d6e1c4f57ed47283f6fc1c1a`;
- attempt-7 outer supervisor:
  `1eb1f9d1e1ac3c05186a6d745b36259004a11152c55bf7fbf2c431a3e44c7d02`;
- attempt-7 runtime/self-match fixture:
  `e0b3b1387eaee8ee651f78b6b466fb98f5c6208660410b0c6b395a43e3cb5740`;
- attempt-7 resource/lifecycle fixture:
  `0bba72bd129a1731556ac2e760f62d3084d1bef5e25bc97496851e70abd597a1`;
- shared attempt-5 event-block classifier:
  `440d7d0636bef8b5baf9bd5603ced988e22fe64c7df912ed15e55561aea8ea16`.

Protected publication hashes at freeze time:

- `families/qwen-flash-next.json`:
  `c378b6f584235632d5fe8d178bc756be6c6ff12309ba5ec352a9cd1369e9254d`;
- `packages/catalog.json`:
  `d8e4b1fe2309b772476de6afeca9fd59d57d93738100fee44410c3247c888ce5`;
- `results/qwen38-flash-next-fp8-b70/README.md`:
  `deb1869104c941cf784594d0bb6c8e3d1e7523075ed74d54a80f930413360a7d`;
- `results/qwen38-flash-next-fp8-b70/HANDOFF.md`:
  `51eb4714f9f4050fd4d49a906ee2f7e2ae83fcc081218244756812ed7cc9f63f`.

## Launch gate

This note does not authorize a GPU launch. Independent read-only audit must
recheck every direct and derived hash, source hash, executable mode, syntax,
schema-v3 predicate, shared and attempt-specific fixtures, exact fresh paths,
port `19684`, host resource floors, swap layout, B70 lock ownership, and
protected publication hashes. The only authorized entry point after that audit
is the no-argument attempt-7 outer supervisor. No direct wrapper, client,
watchdog, or derived-script invocation is authorized.

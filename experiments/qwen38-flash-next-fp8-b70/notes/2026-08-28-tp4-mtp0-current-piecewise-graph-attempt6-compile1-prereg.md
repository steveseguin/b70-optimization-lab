# Qwen3.8 Flash-Next FP8 TP4 PIECEWISE MTP0 attempt 6 preregistration

Date: 2026-08-28
Status: frozen; not launched

## Why this arm exists

Attempt 5 loaded all 131 model shards on all four ranks, then entered the
PIECEWISE compile phase. Rank 0 recorded its first compile-range marker at
11:43:16 America/Toronto. Host memory then fell to 9,070,068 KiB available,
temporary-swap use reached 6,392,412 KiB, and the kernel recorded allocation,
TTM-eviction, and OOM evidence. No health endpoint, model request, quality
gate, replay, or speed row ran. The first attempt-5 OOM occurred at 11:44:21;
the old indirect teardown path did not fully end the model process group and a
later OOM killed model ranks at 12:56:35. The attempt-5 result and primary
evidence remain authoritative; attempt 6 does not rewrite them.

## Frozen treatment and attribution

The sole performance-relevant treatment is:

```text
TORCHINDUCTOR_COMPILE_THREADS=1
```

The frozen base launcher first removes all inherited `TORCHINDUCTOR_*`
variables. The attempt-6 wrapper therefore derives a new launcher from the
exact base, fixes only the staged script's repository-root resolution, and
inserts the treatment immediately after the base scrub and cache-directory
exports. Before any vLLM launch, the pinned interpreter must import
`torch._inductor.config` and prove both the environment value and effective
`compile_threads` value equal `1`. The base identity file and a separate
receipt record both values. The client additionally requires the same two
receipts and reads the live server process environment before it can issue a
request. Its result summary must record
`identity.torchinductor_compile_threads=1`.

All other model and performance identity is unchanged from attempt 5:

- model `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`, revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`, kernel source
  `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`, retained runtime build
  `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, Triton MoE, `allgather_reducescatter`, MTP0, PIECEWISE graph with
  capture size `[1]`, `max_model_len=4352`, `max_num_batched_tokens=64`;
- selective UVA offload of the PLE n-gram embedding and token embedding,
  `cpu_offload_gb=12.25`;
- BLHNC KV layout and exactly `201326592` KV-cache bytes;
- no reasoning parser, prefix caching, async scheduling, speculative decode,
  legacy graph controls, or diagnostic flags.

The earlier-root-NVMe event policy is unchanged and continues to use the exact
attempt-5 complete-event-block classifier. The new resource and termination
guards below are prospective safety controls, not additional performance
treatments and not a retrospective reinterpretation of attempt 5.

## Phase-aware resource and stop contract

The one-second watchdog retains the attempt-5 swap, root, PSI, heartbeat,
kernel-event, and journal-classifier gates. The compile-pressure phase begins
at the first of either:

1. all four unique `Worker_TP0_EP0` through `Worker_TP3_EP3` model-load
   completion markers; or
2. a first Dynamo/compile-range/PIECEWISE capture marker.

Once that phase begins, the run stops immediately if:

- `MemAvailable < 31,457,280 KiB` (30 GiB); or
- one watchdog sample loses at least `8,388,608 KiB` (8 GiB) and the new
  `MemAvailable` is below `41,943,040 KiB` (40 GiB).

At every phase, the first TTM buffer-eviction, page-allocation-failure, or OOM
signature is an immediate stop. Existing B70-addressed events, fatal or
unattributable PCIe/storage events, root-space below 40 GiB, the 12-GiB
absolute memory floor, combined-memory/swap floor, sustained PSI-full rule,
and watchdog-heartbeat rules remain fail closed.

On any outer resource/deadline/watchdog stop, the outer supervisor resolves
the exact saved server PID and PGID, proves the model/port/context/graph command
and the `PGID == server PID` `setsid` identity, then sends TERM to the whole
server process group. It uses `/proc/uptime` monotonic deadlines: 12 seconds
for TERM, then KILL and an 8-second final bound. Only after this direct group
stop does it terminate the exact controller PIDs under short monotonic bounds.
The watchdog is also bound by its PID, `/proc` start time, and exact command;
its normal stop, TERM, and KILL windows are monotonic and bounded. It never
enters the attempt-5 72-minute indirect wait. If any non-zombie server-group
member, controller, or watchdog remains, cleanup fails closed and any created
temporary swap is preserved; swapoff and unlink are forbidden.

The attempt-1 launcher's broad process-name search is replaced in the exact
mechanically derived launcher. A hash-pinned structured `/proc` classifier
binds its caller by PID, start time, script path, and direct parent and returns
`0` only for a clear scan, `1` for a runtime conflict, and `2` for any binding
or read error. The outer supervisor applies the same fail-closed classifier
when an exact server group cannot be resolved, at the terminal pre-swap gate,
and again in final evidence. A clear terminal classifier receipt and absence
of every saved server-group member are required before *any* swapoff path,
including a nominal inner `rc=0` or ordinary inner failure. All kernel-journal
reads are independently bounded; a timeout or read failure is not a clean
journal.

## Request and adjudication protocol

No request is authorized until the unchanged server health, identity, graph,
cache-capacity, model-list, and clean pre-client journal gates pass. The
unchanged client then runs, in order:

1. exact cache-zero `OK` recovery canary;
2. frozen current-runtime eager-a4 comparator and short quality battery;
3. 96 exact color replays plus 96 exact JSON replays;
4. runtime PIECEWISE/compile-cache evidence gates;
5. three p146/o256/c1 short rows, row 1 with one warmup and rows 2-3 without.

Each measured row must have zero `pswpin`/`pswpout` delta and no increase in
temporary-swap use. Any paging invalidates speed. Only the exact existing
client success sentinel may authorize a normal stop. A successful outer result
additionally requires the compile-thread receipts and result-summary identity.
No attempt-6 observation may replace or lower an eager, MTP, context, featured,
or historical speed. A pre-client stop is a bounded negative with no website
coverage or performance credit.

## Fresh identity and paths

- port: `19680`;
- state: `/tmp/q38-mtp0-current-piecewise-graph-a6*`;
- ext4 live resource root:
  `/var/tmp/q38-piecewise-graph-a6-resource`;
- ext4 temporary swap:
  `/var/tmp/q38-piecewise-graph-a6-64g.swap` (64 GiB, priority `-1`);
- USB run/cache/supervisor roots: exact `attempt6` successors of attempt 5;
- declared post-closeout resource archive:
  `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1-attempt6-resource-archive`.

Every path must be absent before launch. `/var/tmp` must still resolve to the
frozen root ext4 device; the precreate floor remains 64 GiB plus 40 GiB root
headroom. The ext4 resource directory remains primary live evidence and is
mirrored only after closeout.

## Frozen hashes

- base launcher:
  `533be64e1c7584448c07a5f8895301a32288f4b0472948a91d87235e78c6f09f`;
- attempt-6 wrapper:
  `1c85dfbafabb9348cbef9f1cd08cdc4e2efba81935e352389ef4f4fc2c9e860c`;
- mechanically derived compile-thread launcher:
  `252e8ad668edef075e1f957f09b79b94d79fffdaf5544201c68763babd00d713`;
- attempt-6 client adapter:
  `6be2e474f1d077890e2b5ce1d8ce21bfcffcad145f2ec8760fde27202b103a71`;
- mechanically derived client:
  `6124378a02578b95948ccd04cad92aab806a9a25cf23e1f7d0d24a949b7d2ce6`;
- attempt-6 watchdog:
  `bf731e482e5721aa0ac12c5eae696158f5174d1be4391fba70146e64135220c8`;
- mechanically derived inner supervisor:
  `03c9d7d2a6ec489a54c2383e43609c60f6d7c207f7725c5e8e99007e3da81fb8`;
- attempt-6 outer supervisor:
  `f67297f1eb9f8ade7d83e284cf1bb8e5887b321d2c4231cf438baac2987274ea`;
- shared attempt-5 event-block classifier:
  `440d7d0636bef8b5baf9bd5603ced988e22fe64c7df912ed15e55561aea8ea16`;
- shared event-policy fixture test:
  `f705d5210bd7041528e05223b571fdc7a59cf29a13b8f4373e7f288b6af75191`;
- shared structured runtime-conflict classifier:
  `c6f9ee76fec1f3343c223ac8264312b6ec3ae6ad6c242e8154fb5d3e3d0ae390`;
- shared runtime-conflict fixture test:
  `fe146ba53bf0eb2f0c0ea60647fbdace353a39a564317e6375574815c2c2dd85`;
- attempt-6 runtime/self-match fixture test:
  `72bdbb09a4a3eaf9291f8019ea349784265f2cb81e2b5268cdb2c9d8fca6813a`;
- attempt-6 phase/resource/process-group fixture test:
  `c8363033273411b97daa9699dbc7d7d9559558b7f790965098922fe67569163b`.

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

No GPU launch is authorized by this note alone. Before launch, an independent
read-only audit must recheck all hashes, derived hashes, exact fresh paths,
syntax, phase/resource fixtures, complete-event-block fixtures, live host
resource floors, both structured runtime-conflict fixture suites, actual
attempt-5 phase-log parsing, absence of port `19680`, and absence of the
canonical B70 benchmark locks. The authorized launcher after that audit is the
no-argument outer supervisor; no direct invocation of the wrapper, client,
watchdog, or derived scripts is part of the protocol.

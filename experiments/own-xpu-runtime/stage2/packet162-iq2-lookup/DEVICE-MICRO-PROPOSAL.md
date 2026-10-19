# Conditional single-card micro proposal — NOT READY / NOT QUEUED

This specifies the requested experiment but does not supply a runnable job.
The current implementations fail strict CPU bytes and close in this packet.
There is no `READY-FOR-DEVICE.json`, no ops proposal and no live queue edit.
Only a materially revised, strictly exact candidate should incur this work.

Provisional fresh identity: `packet162-enum11-micro-B`; unit
`screen-packet162-enum11-micro-B.service`; output `evidence/enum11-micro-B/`.
At actual reopening choose new attempt names if any already exist, and test
the exact names/lane/argv through coordinator rehearsal rather than retaining
literal identities from an older wrapper. The coordinator alone queues it.

## Geometry, controls and output gate

- **One lane-B card only:** current lane-B physical card 2,
  PCI `0000:43:00.0`; verify topology at admission. Use the existing shared
  reservation, isolated mask, client census, fault review, drain and release
  protocol. No server, model load, throughput suite or service restoration.
- Compare bundle8's actual `p90exp::Kernel<IQ2_S,2560,64,false,true>` E1
  gate/up to the revised candidate: 512 banks, 640 rows, ten selected experts,
  two independent streams, K2560, WG64/SG32/V8. Down is outside this test.
- Synthetic full-size banks, no GGUF. Use at least dispersed and adjacent
  route sets, two deterministic finite input seeds, plus untimed adversarial
  byte cases and invalid/tail routes. Generate rows once; do not select easy
  real prompts or copy an expert into every route slot.
- Before timing, compare every output/status/error byte against production.
  CPU raw-chain and exceptional-payload checks must also pass beforehand.
  A finite output match cannot waive NaN or invalid-input differences.
- Forty alternating pairs per registered route/input stratum, both orders.
  Record device event start/end, host wall separately, repetition, shape,
  arm, route/input hashes, build hashes and byte-result hashes. Keep every
  sample; do not discard a slow first arm after inspecting results.
- Include a matched cache-displaced stratum using a device-local sweep before
  **each** arm, and report the ordinary repeated stratum separately. No host
  cache drops. The sweep is setup time, explicitly recorded and excluded from
  kernel time for both arms. Do not infer model cache residency from it.
- A build brief requires **byte exact AND candidate/production ≤0.85**, overall,
  in both orders and every registered route/input/cache stratum. Analyze only
  after graceful completion/release. Partial samples, lost events or equality
  failures are inconclusive/failing, never an estimated pass. A micro pass
  merely permits a build brief; it is not a model gain or publication gate.

## Preparation and safety contract

Expected complete micro lifetime **under five minutes**, one process, one
attempt, no retry. Bound the sample count, not the number of valid outputs
that must arrive by an arbitrary elapsed second. A 300-second whole-job safety
watchdog requests graceful stop; no hard/group kill, and drain may take longer.
Timeout means an incomplete run, never evidence that outputs are incorrect.
**No wall-clock data-proof limits:** no “first row by N seconds”, per-class
arrival deadline, or early exactness/timing verdict. In-run data checks cover
stream format/presence and byte correctness; timing conclusions are offline.

Device-phase **root free-space floor: 25,000,000,000 bytes**, checked at
admission and monitored. This is a disk floor, not a new GPU-memory setting.
CPU preparation stops below 27,000,000,000 bytes, runs nice 19 on
8–15/24–31 with stdin `/dev/null`, Python `-B`, ≤4 GiB RAM, and compiler turns
through `ops/compile_turn.py`. No full-shape preparation during a one-card
timing window. No power, host-memory, swap or page-cache changes.

The standalone device allocation plan can hold original and candidate
synthetic banks together (~1.13 GB) plus bounded inputs/outputs and a 256 MiB
cache sweep, under a 2 GiB device allocation ceiling. Keep at least 8 GiB host
available reserve, admit the actual anonymous peak, and use bounded host
generation chunks. This small micro admission does **not** admit a full model
startup; the modeled 157 MB final arena margin requires a separate real loader
allocation rehearsal before a build brief can be executed.

Before making a runnable proposal, compile and run a CPU **preparation-path
probe using the exact future device binary and real proposed argv**, with a
CPU-only exit before device enumeration/allocation. Exercise parsing, full
bank extents, row-bit packing, route bounds, buffer names, masks and memory
admission, including malformed/truncated cases. Verify through file tracing
that this probe opens neither a GPU nor GGUF. No guessed entrypoint, startup
stub or `--help` can substitute for this path. Inspect linked device code for
actual lookup removal, spills and unexpected constant-table reconstruction.
Bind sources, compiler flags, dependencies, binary, probe receipt, analyzer
fixtures and proposal hash. Rehearse the shared proposal entry/gate identity.
Write **READY last**, only after all these checks pass. None is asserted here.

Faults stop new launches and retain journal/coredump evidence. Shared recovery
rules and the coordinator's bounded health probe apply; this CPU packet grants
no recovery, GPU, reboot or driver operation.

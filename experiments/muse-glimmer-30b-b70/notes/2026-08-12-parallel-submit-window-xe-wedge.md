# Parallel-submit A/B window: invalid run and xe wedge

Date: 2026-08-12

## Intended experiment

Test a default-off `GGML_META_PARALLEL_SUBMIT=1` path that submits the four
independent simple-backend graphs concurrently before each existing TP
collective. The source change is one uncommitted file in
`/home/steve/src/llama.cpp-muse-100` and built successfully. The operation
profiler and all diagnostic counters were disabled. An independent review
found the OpenMP barrier and per-device status handling suitable for an A/B,
while identifying lazy environment-gate statics that must be hardened before
promotion if the experiment wins.

## Invalid windows

The first configuration launched without the oneAPI runtime environment. Both
arms exited before model load with missing `libsvml.so`; the two error records
are preserved at:

`/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/meta-parallel-submit-ab-20260812.jsonl`

SHA-256: `b68cbc92b930a6bc0f58e429d8106dcfdb1df8a36595ad826c7be846c92ce055`.

The corrected v2 runner was still active in the serial control arm when the
tool wrapper yielded without a completion record. Production was restarted
prematurely, causing the incumbent TP2 processes to overlap the TP4 control.
This was an orchestration error. It occurred with
`GGML_META_PARALLEL_SUBMIT=0`; it is not evidence about the candidate patch.
The v2 JSONL remained empty (empty-file SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).
No speed or correctness result from this window is valid.

## Failure and recovery evidence

- the benchmark and production workers were terminated after the overlap was
  detected;
- one production worker remained in kernel `D` state at
  `drm_exec_lock_obj`;
- the kernel logged an xe page-table teardown fault and later a TTM page fault;
- an XPU-SMI call made during diagnosis faulted in `xe_ttm_vram_mgr_new`; this
  violated the recovery runbook's warning against active probing on a flapping
  device and must not be repeated;
- the required 60-second quiet period did not drain the worker;
- passive checks confirmed `xe.disable_display=1`, ASPEED console graphics,
  and the live BDFs `23:00.0`, `27:00.0`, `43:00.0`, `47:00.0`;
- the documented xe unbind/reload recovery stuck in kernel after unbinding
  `23:00.0`, `27:00.0`, and `43:00.0`; `47:00.0` remained bound at the last
  passive snapshot.

The services are stopped/failed and GPU work must not resume in this boot. A
host reboot is now the remaining documented recovery and requires explicit
operator authorization. PCI FLR was not attempted.

## After authorized reboot

1. Verify four-device discovery and stable BDF/UUID mapping.
2. Require idle VRAM, per-card copy/compute smoke, P2P access, and a
   representative collective test.
3. Start the unchanged incumbent production services and pass the full Muse
   code/cache-zero/vision health gate.
4. Preserve both invalid result identities. Create a fresh v3 identity before
   retrying the serial-control/candidate A/B.
5. Use an explicit process-liveness wait plus completed JSONL row count before
   restarting production; never infer benchmark completion from a yielded tool
   wrapper.

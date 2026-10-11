# Certified A367 load calibration — CPU prepared, native run pending

This packet prepares one measurement of the **A367 recipe itself**. It has not
launched a model or used a GPU. Attempt 8 used the experimental mmap adapter,
faulted before ready and cannot supply this measurement. Read the corrected
[admission review](../MEMORY-ADMISSION-REVISION.md#measured-on-2026-10-11-attempt-8)
and [fourth-incident note](../../../../../notes/2026-10-11-attempt8-fourth-incident.md).
The host halt and the historical model-verification receipt mismatch remain
blockers. No source, stage, model, host setting, FAULT marker or old receipt is
changed by this packet.

## Recipe and declared differences

The [certified guide](../../../../../repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/README.md)
uses `/home/steve/.venvs/vllm-xpu`, source `6d872457`, and the rebuilt extension
at `/mnt/usb-models/qwen38-build/runtime-gdn-roundstate-bbae3c5-b70`.
The model is the launcher's USB publisher copy at
`/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8`, revision
`bcd9f01ddc9cff2316eb84281bebcd5b058bddce`. A payload receipt for the NVMe copy
alone does not admit this path. No download or restoration runs here.

The supervisor reconstructs the frozen server command; it does **not** run the
historical shell wrappers. The guide itself prohibits their host-control and
forced-stop behavior. CPU tests apply only the launcher's awk text transform,
verify the derived script's historical SHA256, and compare every server
argument and literal compute environment export. The script output is never
executed. The existing packet-4 entry script invokes the same vLLM CLI through
the pinned Python and checks source imports in spawned processes. The only
runtime injection is its cooperative cleanup guard, not its extraction worker.

TP4/EP4, MTP1, BF16 activations/KV, exact-GDN selectors, 4,352 context, 64-token
prefill chunks, 376,569,856 KV bytes, UVA offload, original expert placement,
tuned MoE map, oneCCL, `FULL_DECODE_ONLY` graph capture sizes 1/2 and one warmup
stay unchanged. Compilation remains NONE; graph capture remains enabled.
`TORCH_TRACE` remains enabled in the evidence directory. No mmap adapter,
allocation-policy override, `NEOReadDebugKeys` or `EnableDeferBacking` is added.

[preregistration.json](preregistration.json) records each identity delta:

- Zero generation requests; readiness uses only GET `/health` and `/v1/models`,
  then 20 seconds ready. Startup dummy forwards and graph capture still run.
- A host memory sampler/watchdog and kernel journal watcher start before the
  model, with 0.5-second polling. The original 12,000,000 KiB loaded-state
  reserve is a live stop threshold, not a claim of instantaneous protection.
- Current owner-window, fresh health, payload, halt, ownership and seal gates
  replace unsafe historical host-control operations. An optional start-floor
  exception is **calibration only**, must be explicitly owner-approved, and is
  retained in `identity.json`; it never lowers the fixture driver's floor.
- One SIGINT to the API PID, cooperative child cleanup, wait for the whole
  session to disappear, fresh post-exit kernel read, then a 305-second gap.
  There is no retry, force kill, driver reset or recovery launch. A 300-second
  soft teardown overrun records failure and keeps waiting for owner recovery.
- Task-required nice 19 and `OMP_NUM_THREADS=2` (historically 1); new private
  cache/IPC/evidence paths. These differences are explicit, so this is not an
  unmodified performance replay. Scratch is deleted only after owners exit.

The original host's swap/power/page-cache conditions are not recreated. Current
memory exclusions remain in place. These historical host-state differences do
not authorize changing the machine. The recipe's loaded arithmetic and memory
allocation selectors stay fixed; the receipt pins current kernel and firmware.

## Admission and the circular floor problem

Without an exception, the script still requires **120,000,000 KiB** available.
It therefore refuses this boot. The load-only experiment cannot derive a new
floor before running; its owner may separately accept the unknown loading risk
with a numeric calibration-only start floor and the existing live watchdog.
This is an explicit experiment admission delta, not matched evidence that the
chosen start floor is safe. A 0.5-second watchdog may not react before a rapid
allocation exhausts memory; historical A367 demand may still fail this run.

Use the [packet-4 owner-window fields](../driver/README.md), including the
packet-4 `preregistration_sha256`, boot, host, firmware, PCI IDs, output,
health/payload hashes, resolved halt and previous teardown time. Add:

```json
{
  "purpose": "a367-calibrate-load",
  "calibration_preregistration_sha256": "SHA256 of a367-calibrate/preregistration.json",
  "calibration_seal_sha256": "SHA256 of a367-calibrate/seal.json",
  "admission_revision_sha256": null
}
```

The owner-window must be current, at most 3,600 seconds long, and bind this
fresh output directory. The four-card health receipt must be passing, on this
boot/kernel, at most 600 seconds old, with no earlier boot faults. All nested
`FAULT.json` latches in packet-4 and the two existing campaign roots must be
absent; this tool never removes or archives them. No ltx*, ComfyUI or vLLM
process may exist. It does not inspect a device node, contact port 8188 or
operate any LTX/systemd unit. Only port 19980 is used in a later native run.

The 75 patch/bundle seal members, frozen four-script packet, all 2,305 source
Python files, 18 loadable stage members, collective libraries, installed
runtime versions, placement, tuned map and model metadata are checked using
the packet-4 byte audit. The historical model receipt mismatch is **not silently
repinned**. Fresh full payload verification (within one hour) is additionally
required. The seal pins the shared supervisor/bootstrap/cleanup implementation.
Admission, health freshness, ownership and actual capacity are rechecked after
the potentially slow byte audit. A 60 GiB free-disk reserve is retained.

If the owner elects a calibration-only floor, add this object to that same
window flag only after their actual approval (all placeholders are mandatory):

```json
{
  "calibration_memory_exception": {
    "approved": false,
    "approved_by": "owner",
    "minimum_mem_available_kib": "OWNER-CHOSEN INTEGER",
    "owner_approval_text": ""
  }
}
```

It is deliberately invalid as printed. The exact owner sentence is:

> I authorize one A367 calibrate-load measurement on steve-b70s with a calibration-only MemAvailable start floor of FLOOR KiB, a 0.5-second watchdog and the 12000000 KiB live reserve, under preregistration SHA256 REG_DIGEST and seal SHA256 SEAL_DIGEST. This accepts the unmatched loading-memory risk, does not lower the packet-4 fixture floor, and does not resolve the halt or authorize another launch.

Replace all three placeholders with the chosen integer and actual file hashes.
The exception floor must exceed the live reserve and be below the old floor;
actual available memory must meet it. No approval is supplied in this packet.
A stale sentence fails after either seal or preregistration changes.

## Sampling, teardown and limits

`samples.jsonl` records baseline, loading (including profile/capture), plateau
and shutdown. The baseline is written immediately before Popen, after admission
and payload verification. The need is the baseline-to-trough decline across all
those phases, rounded **up** to KiB. MemTotal minus MemAvailable is recorded
separately as absolute host pressure. Never add worker RSS, cgroup usage,
GPUActive or known pinned weights to either whole-host counter.

Rank RSS comes from `/proc/<pid>/status`, matching rank-labelled worker names
only inside the launched session. Unknown or ambiguous rank attribution does
not become zero. Each distinct session cgroup's `memory.current` is recorded
with its source path and labelled as potentially shared with siblings; this
packet creates no cgroup or service. All four ranks and readable cgroup values
are required throughout the ready plateau to derive a floor. GPUActive is read
from `/proc/meminfo` if exposed. Exact driver-shadow attribution is unknown;
no inference from RSS subtraction or xpu-smi fallback is made.

Host-memory read failures, more than 1.5 seconds between samples, reserve
crossings, owner revocation/expiry, faults or kernel-watch failures request one
SIGINT. Sampling continues through teardown. Both monitors run independently
of readiness HTTP polling. Signals received by the coordinator also take the
same one-stop path. The native bootstrap disables vLLM's force-termination
cleanup branches in favor of cooperative waiting. Clean parent exit alone is
insufficient: every process in the launched session must disappear first.

A completed plateau plus clean teardown is a **startup/idle health observation
of the certified line**, not an output-quality check. No full-model generation
or fixture peak is measured, and no native test has yet established this new
controller's behavior. A proposed floor always carries that limitation and the
existing reserve/fixture budget. A failed or partial run yields no proposal.

## Commands for the later owner window

CPU plan, with a new absolute output path whose parent already exists:

```bash
nice -n 19 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage1/packet4-prep/a367-calibrate/a367_calibrate_load.py --plan --output "$CALIBRATION"
```

After owner halt resolution, fresh bounded health and all admission receipts,
in the owner's durable terminal (never an agent shell or automatic unit):

```bash
nice -n 19 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage1/packet4-prep/a367-calibrate/a367_calibrate_load.py --execute --owner-window "$OWNER_WINDOW" --health-receipt "$HEALTH_RECEIPT" --payload-receipt "$PAYLOAD_RECEIPT" --output "$CALIBRATION"
```

After a complete successful receipt, CPU derivation:

```bash
nice -n 19 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage1/packet4-prep/a367-calibrate/derive_floor.py --run "$CALIBRATION" --output "$FLOOR_PROPOSAL"
```

The output contains the arithmetic and hash-bound evidence, a proposed complete
revision document, an **unapproved** receipt and the exact approval sentence.
The calculation is `ceil(observed decline / 1024) + 12000000 + 8388608` KiB.
The last term is the existing 4 × 2 GiB fixture allowance, not measured copies.
No canonical document, approved receipt, fixture threshold or host state is
changed. Review the proposal, install its exact bytes as the canonical revision
in a focused commit, and update the fixture driver's document seal before
requesting the owner's exact document-bound approval. If the document changes,
regenerate its hash and pending receipt; never reuse the old approval sentence.
A new boot needs a current owner receipt, and host/runtime changes need review
of whether this calibration still matches. Fixture admission is a separate
window with its own fresh health, actual capacity and 305-second gap checks.

## CPU tests

```bash
nice -n 19 env OMP_NUM_THREADS=2 python3 -B -m unittest discover -s experiments/own-xpu-runtime/stage1/packet4-prep/a367-calibrate -p test_calibrate.py -v
```

The standard-library tests use mocked launchers, sessions, clocks, HTTP and
proc/cgroup files. They never import Torch/vLLM, run a server, access a GPU,
launch a health probe or contact any endpoint. Temporary synthetic approvals
and receipts are removed by `TemporaryDirectory`. Their samples are not
measurements. [test-receipt.json](test-receipt.json) records the CPU check.

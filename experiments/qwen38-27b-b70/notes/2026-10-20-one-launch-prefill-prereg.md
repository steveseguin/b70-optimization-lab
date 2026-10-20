# One-server FP8 overlay 0.2.0 prefill screen — preregistration

Status: prepared on CPU, **not executed**. The coordinator reviews the plan
and decides when to run it. This does not authorize an unattended rerun.

Purpose: close the missing measured 512-token prefill point for the package's
current recommended two-card identity. This is a synthetic speed screen;
it neither replaces the natural-completion headline suite nor establishes a
new no-quality-loss result. Existing strict and context evidence remains
separate.

## Identity and workload

- Host: `steve-b70s`, physical cards 0/1, PCI `0000:23:00.0` and
  `0000:27:00.0`, render nodes `renderD130,renderD131`. Refuse a changed map.
- Model: official Qwen3.8 27B FP8 revision
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`, freshly verified against
  [model-direct.json](../../../repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/model-direct.json),
  reused from `/mnt/fast-ai/llm-models/qwen3.8-27b-fp8`.
- Runtime and every numerical flag: unchanged
  [package launcher](../../../packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py),
  `recommended` profile, overlay 0.2.0 with
  `B70_FA_VERIFY_ROWS_ONE_LAUNCH=1`, TP2, MTP5, one sequence, 33,024-token
  window, full 16-bit KV, no prefix reuse. The image is pinned by digest;
  the plan and run receipt contain the complete Docker argv/environment.
  The pinned image must already exist locally and its identity is checked
  before server launch; the wrapper never pulls or builds an image.
- Port: localhost `18124`. One new server, one attempt, no retries.
- Unchanged [bench-short-prefill.py](../scripts/bench-short-prefill.py):
  `--lengths 512 --repeats 2 --max-tokens 128 --max-model-len 33024`.
  Three synthetic prompt classes (prose/code/docs), six measured requests;
  one client prose warmup in addition to the package's distinct startup
  warmup. The client deliberately uses `ignore_eos=true` and repeats prompt
  IDs. It requires explicit zero cached tokens, matching numeric IDs across
  repeats, and exact 512-token input/128-token output accounting. This is
  self-consistency, not comparison to an unchanged no-MTP target oracle.
- Measurement: median of the six request-level server histogram prefill
  rates when valid and available. Keep HTTP prompt-tokens/TTFT separately
  labeled as an end-to-end proxy; never substitute it for missing server
  histogram data. Preserve all six values and dispersion, all requests and
  SSE/usage/counter receipts. No speed pass threshold or best-of selection.

The [source-pin manifest](../data/2026-10-20-one-launch-prefill-prereg.json)
binds the wrapper, launcher, overlays, client and model verifier. Any source drift refuses launch and requires explicit review and a
new preregistration identity; nothing refreshes pins automatically.

## Lifecycle and fault policy

The current host prohibits benchmark-controlled server lifecycle. `--run`
explicitly refuses. The prepared automatic controller was never executed;
any retained proposal is historical evidence, not an operating instruction.
The coordinator starts one persistent service and invokes the client separately.
The client cannot start, stop or restart the server. There are no active
single-device or collective health probes. Passive journal, device ownership,
source/image identity and endpoint checks gate work.

The serving adapter holds the host/GPU0/GPU1 flock descriptors for its lifetime.
It verifies the model, fixed PCI mapping, cached image, all source pins and exact
package Docker argv. Admission requires16GiB available host RAM,5GiB root free,
and30GiB output free. These new run-only disk floors account for a cached image
and an external output/cache mount; they do not change historical native-runtime
admission floors. Nothing is pulled, built, deleted or changed in host settings.
The initial ten-minute journal check supplements the coordinator's earlier
current-boot fault review; it does not clear an unresolved incident.

Only owned cleanup changes: the original package's timed Docker stop could
escalate to SIGKILL, so the adapter sends one ownership-checked TERM and passively
waits up to180seconds. It never escalates or retries. If work remains alive it
retains locks and writes HALTED for operator review. No automatic reboot,
driver reset, power, memory, swap or cache change occurs.

The separate client checks the passive kernel journal before every HTTP request.
On fault/error it halts requests and retains partial evidence. Its unchanged
payloads deliberately use ignore_eos for a synthetic timing screen; no strict
headline or new quality qualification follows. HTTP TTFT includes admission
check overhead; server histogram timing remains separately defined.

## Reviewed commands

First inspect the CPU-only `--plan`. Start the persistent service with
`systemd-run --user --unit=fp8-prefill-service-20261020`, `Restart=no`,
`KillMode=process`, `SendSIGKILL=no`, `TimeoutStopSec=infinity`, and
`ExitType=cgroup`, executing this adapter with `--serve-adapter` from the repo.
After the saved server state is ready and the journal remains clean, separately
invoke `--client-adapter` in a user unit with the same no-restart/no-kill policy.
There is no chained start/benchmark/stop command. The coordinator reviews client
receipts, then requests one graceful service stop before daily endpoint restore.

Output: `/mnt/usb-models/bench-results/fp8-one-launch-prefill-20261020`.
Pins: [preregistration JSON](../data/2026-10-20-one-launch-prefill-prereg.json).
Runtime settings, source identity and partial/final receipts remain preserved.

## CPU admission correction

The first service admission at03:53UTC verified every model hash, then refused
an argv comparison: the template retained the model symlink while package
start resolves it. No launch.json, server.log or container ID was created;
Docker was never spawned. The server_attempts field in that adapter's lifecycle
receipt is an admission counter, not evidence of a GPU launch. Preserve that
directory as failed CPU admission. The corrected adapter resolves MODEL before
rendering the comparison; use fresh output ending `-a2` and a fresh unit.
No arithmetic, numerical flags, model bytes or runtime changes follow from this
path correction. This is the first actual server launch, not a server retry.

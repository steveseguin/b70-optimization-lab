# Packet201 streaming serving worker — CPU preparation

This additive worker attaches the reviewed streaming session to one native owner.
It retains the canonical bounded profile: 16 requests, context4096, output cap512,
full BF16 KV, 512MiB parking, 256MiB SAVE reservation, 768MiB monitored write
forecast and27GB root floor. No fresh profile plan, operational manifest, client,
controller or launch is supplied by this preparation.

The parent is frozen packet200 `device_worker.py`, SHA256
`1e2832c190608ad4227cecf1689a919fc7d04d7c5a358f2a1ffa78178c06fd0f`.
`integration_origins()` checks that parent pin before planning or authorization.
The copied parent CPU tests are pinned at
`2e77102590253aa1f096b9e4780caffd3067758f77c4b052038b683571ad319e`.

The implementation delta is limited to:

- New packet201 unit, manifest/plan schema, import namespace and helper thread names.
- Import `streaming_v1.session` and check its canonical and streaming origins.
- Include its explicit additional `streaming_sources` map/digest and parent worker
  provenance in `cpu_plan`; authorization requires every streaming source in the
  separately sealed execution closure and checks conflicts with canonical pins.
- Pass that exact map to streaming `attach` alongside the unchanged profile.

`UNIT` is `packet201-streaming-serving-a`. The future manifest is this packet's
`READY-FOR-DEVICE.json`, schema `packet201.execution-admission.v1`. Only the
read-only `--plan --staging-parent PATH [--activity-mode launch|mapped-cold-start]`
CLI exists. It still calls the canonical fresh-profile storage checks and must
not be run until the coordinator has sufficient headroom. `execute()` remains
behind a separate operational admission manifest; this document authorizes none.

Reservation/drain acquisition, private output/checkpoint creation, guarded launch,
one native process, diagnostics-before-readiness, passive monitoring, single
incident SIGTERM, retained uncertainty, borrowed-resource close ordering and
two-phase precompletion/final evidence are copied unchanged. A successful JSON
receipt still requires worker exit0; failure after final append is not success.
The original runtime error stays primary. No retries, hard kills, device resets,
cache/power/memory changes or automatic restoration are introduced.

CPU tests adapt all26 packet200 cases and add streaming closure/attach/namespace
gates plus an AST comparison of resource ownership methods. Native `Popen`,
service actions and placement changes are intercepted. Actual Python pipe and
bounded evidence tests remain. Plan fixtures reuse the retained packet200 CPU
profile (`ops/packet200-window/actual-cpu-plan.json`, SHA256
`95ef80738a0283738c31c7bb1d834c56b3ccafe6020142a9019935c46c9f0839`)
with only temporary output/checkpoint path substitution and a mocked profile
builder. They do not derive a fresh real plan or rely on current root free space.
Synthetic authorization manifests exist only inside test temporary directories.

Run the focused CPU suite from the repository root:

```sh
taskset -c 8-15,24-31 nice -n 19 /home/steve/.venvs/vllm-xpu/bin/python -B -m unittest discover -s experiments/own-xpu-runtime/stage2/packet201-streaming-serving -p test_device_worker.py -v
```

Actual streaming output correctness, token-time SSE, client completion and
device drain need a separately reviewed client/controller and future window.
CPU source gates do not qualify GPU execution or guarantee peer delivery.

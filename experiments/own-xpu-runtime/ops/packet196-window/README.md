# Packet196 qualification window

Manual one-shot coordinator for the sealed packet196 seven-window chain on
card 0. This directory is separate from the sealed packet and orchestration;
it never edits either one's source or declaration. It preserves the three
owner endpoints established by the preceding authorized windows.

Read-only admission (no service changes or privileged inventory):

```sh
python3 -B experiments/own-xpu-runtime/ops/packet196-window/window.py \
  --check --restore-suffix 20261023-restore25 \
  --output experiments/own-xpu-runtime/ops/packet196-window/evidence/window-a
```

After coordinator review, replace `--check` with `--run` exactly once. Use a
fresh coordinator evidence directory and restore suffix. The chain's registered
output and fault-review paths must also be fresh. Do not retry a refused or
failed attempt automatically. An enclosing systemd unit should use a `window-*`
name and `Restart=no`, `SendSIGKILL=no`, `TimeoutStopSec=infinity`,
`KillMode=process`, `ExitType=cgroup`.

The coordinator records current idle endpoints, original PAUSE bytes and the
sealed launcher digest, requests graceful endpoint stops once, and requires
complete privileged passive Intel DRM ownership inventory. It archives and
removes PAUSE-A only at launch; PAUSE-B remains unchanged. The exact sealed
`packet196-orchestration/launch_chain.sh` then performs its own memory, storage,
source, command, fault, ownership and quiet-host admission. It is invoked once.
No queue is modified. The window does not freeze agents; the coordinator must
keep CPU workers quiescent during timing, as the registered chain requires.

Monitoring requires the seven gates in order: K1a, K1b, KD, W2m, WS, WS128x,
WS128. Each completed window must pass with the current boot/build identity
and no live child. Final success requires all seven, queue `passed=true`, a
finish timestamp, and inactive unit with successful zero exit status. One
status snapshot per poll avoids mistaking the active-to-inactive transition
for failure; at most two final metadata rereads tolerate an in-place queue
write near process exit. This is never a launch or request retry.

New faults, external STOP, re-armed PAUSE-A, changed PAUSE-B, failed gates,
missing final receipts or a deadline halt the operation and withhold restore.
Incident handling first re-arms PAUSE-A and writes STOP-A and the chain's own
output/STOP without overwriting any existing latch. If the launched chain is
still active, at most one SIGTERM goes to the coordinator's main process only.
The sealed queue runner's signal handler forwards one cooperative SIGTERM to
its owned window; no process-group signal or hard kill occurs. After the drain
bound, an active unit is left with latches armed. No restart, reboot, driver
reset, settings change or automatic recovery exists.

Only a completely successful, fault-free, fully drained chain can restore the
previous endpoints once. External STOP remains authoritative through every
restoration validation HTTP request. Any restoration failure stops subsequent
work without retry; partial restored services are not killed automatically.
The metadata-only privileged inventory reads its outside-Git sudo credential
only through stdin and never opens device nodes or runs compute.

CPU mocks:

```sh
cd experiments/own-xpu-runtime/ops/packet196-window
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest test_window -v
```

`provenance.json` records the preceding screened window helpers; the original
endpoint settings and pinned per-request validator are retained. Preparation
has not invoked any service operation, privileged command or GPU work.

## Reviewed predevice continuation

`--resume-predevice REVIEW.json` is a narrow manual continuation for the retained
`evidence/window-a` endpoint-state refusal (`systemctl is-active` returned code 4
with `inactive` for an unloaded endpoint unit). It skips endpoint stop/start
operations and reruns passive ownership/drain admission before the one sealed
launcher invocation. It never archives or removes an incident latch. The
coordinator must separately review and archive its STOP-A as
`window-a/STOP-A.archived`; any current STOP still refuses. Use fresh output
`evidence/window-b`, retaining the original window unchanged otherwise.

The review JSON requires schema `packet196.predevice-resume-review.v1`,
`reviewed=true`, `predevice_refusal="systemctl-is-active-rc4-inactive"`,
`chain_launched=false`, `stop_manually_archived=true`, current `boot_id`,
`previous_launcher_sha256`, `replacement_launcher_sha256`, and the unchanged
`chain_command_sha256`. Its `prior_files_sha256` maps exactly these original
window-a files to their digests: `window-result.json`, `preflight.json`,
`launcher.log`, `post-stop-drain.json`, `PAUSE-A.before`, `PAUSE-B.before`,
`STOP-A.archived`. The repaired launcher must differ from the original and
match current READY. The original log must contain only the known early
refusal; no completed gates or cooperative signal may exist. Live admission
requires inactive endpoints, an unloaded chain unit with MainPID zero, absent
chain output/fault review, unchanged pause bytes and current clean fault guards.
This mode is never selected automatically and is not a retry policy.

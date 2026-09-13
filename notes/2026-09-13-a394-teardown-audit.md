# A394 teardown audit without device work, 2026-09-13

## Findings

A394 benchmark success and host health are separate. The offline checker confirms
all eight saved row summaries match A382, with zero raw row exit codes; supervisor
exit remains 143 and cached GPU receipts are explicitly unverified. See the
[hash-bound audit](../experiments/qwen38-flash-next-fp8-b70/data/20260913-a394-offline-teardown-audit.json).
This checker does not rehash raw token streams or certify model identity.

1. **Stop protocol mismatch.** The shared `q38-depth-ladder-driver.sh` writes
   `STOP after the depth ladder a394`. A394's supervisor requires the historical
   MTP0 short-client stop/pass strings, runtime receipts, 4352 context and old KV
   budget. Its successful-stop path cannot accept this ladder. This explains why
   passed rows are compatible with rc 143; it does not explain the host freeze.
2. **Historical telemetry passes as current health.** `q38_xpusmi_bypass.py`
   copies A146 device receipts into postflight filenames. The supervisor then
   uses them to accept current discovery and memory checks. The `.err` marker
   discloses the bypass but the acceptance predicate ignores that marker.
3. **Nested cleanup budgets conflict.** The root host wrapper waits 30 seconds
   before killing its runuser child, then at most 10 more seconds. Supervisor
   cleanup can itself take approximately 60 seconds before postflight. The
   wrapper proceeds to ASPM/swap restoration even after detecting a surviving
   child; it does not establish descendant or process-group termination.
   This is a reachable abnormal-exit race, not proof it happened during A394.
4. **Failed rows do not fail the ladder promptly.** The shared driver continues
   its row loop under `set +e`; summary parsing can exit before writing any stop
   file. There is no EXIT handler requesting teardown on that path, leaving the
   supervisor's much longer deadline as fallback.

Frozen A394 packets and generator behavior were preserved. Do not silently repin
those files or retry them unchanged. These defects were independently reviewed
by a read-only subagent and checked against the actual ladder driver.

## Integrity and passive health checks

- `git fsck --connectivity-only --no-dangling`: exit 0, no findings.
- `git fsck --full --no-dangling`: exit 0, no findings (bounded to 60 seconds).
- One bounded `smartctl -H -A /dev/nvme0`: health PASSED, critical warning 0,
  media/data integrity errors 0, error log entries 0, 44 C, wear 4%, lifetime
  unsafe shutdown count 33. This does not rule out power, firmware, PCIe or
  filesystem issues and does not date individual unsafe shutdowns.
- Root filesystem had 301 GiB available. ASPM was already performance; swap
  was already enabled and unused. Neither setting was changed.

Git logs are retained under
`/home/steve/identified-mistakes/recovery-20260913-a394/`. Full Git fsck validates
object integrity/connectivity, not every worktree file, storage hardware or
filesystem metadata. No online filesystem repair, SMART self-test, GPU probe,
model launch, mount change, cache drop, swap toggle, reset or reboot was done.

## Next implementation, before a device experiment

Use a new lifecycle harness and fresh attempt identity, leaving historical
packets intact. Its CPU-only mocked acceptance tests must cover:

- atomic ladder outcome with explicit success, failure and interruption states;
  first failed row stops requests, and every exit requests owned teardown;
- separate row-quality, process-cleanup and device-health statuses; cached or
  absent telemetry is `not_measured`, never a successful current health gate;
- one shutdown owner, tracked descendants/process group and explicit cleanup
  acknowledgement; parent timeout exceeds the complete child cleanup budget;
- restoration stages recorded with timestamps and fsync before/after each
  operation, in persistent evidence outside `/tmp`; failed cleanup must not
  immediately restore host settings under the assumption that devices are idle;
- no post-stop GPU telemetry loop. Retain bounded passive journal/listener/
  process checks; future device qualification remains a separate explicit gate.

Only after those CPU tests should a small preregistered device experiment be
considered. Do not run another depth ladder merely to test shutdown. The freeze
root cause remains unresolved; no reboot is required for the offline work.

## Validation

`audit-depth-ladder-offline.py` is a read-only artifact checker. Five CPU tests
cover truncated summaries, missing row receipts, hash mismatch, failed teardown
with successful rows and rc-zero without a device-health certification. All pass;
the actual A394/A382 packet passes row comparison while reporting nonzero
teardown and unverified device health.

Repository link and manifest-path checks pass. The literal-pin checker reports
87 matches and 231 drifted pins (no absent targets), so frozen replay integrity
is not globally green. No existing pinned tool was edited in this audit; these
drift findings are retained in `pinned-hash-audit.log` in the recovery directory
and were not repinned to manufacture a pass.

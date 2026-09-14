# Encoder GPU screen ready for a maintenance decision

The inactive v2 packet contains startup identity, actual tensor-placement and
unload checks, and explicit encoder variants. The bounded client is complete.
No new GPU job or process migration occurred during this preparation. The
previous goal turn was progress: it built the candidate source and real-loader
CPU tests. This turn completes the startup/client integration and closes the
remaining preparation gaps for the encoder screen. The subsecond goal remains
unmet; the measured 30-request baseline remains 6.515 s median preview latency.

Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-02`.
Manifest SHA256:
`920d0e35774f298c9b11f80b3dd5e3708d0541f914e4c1857e96493bfd7282a8`.
The [manifest](../data/encoder-runtime-prepared-02-manifest.json) inventories
1,214 files and binds Python/Torch fingerprints, source, patches, startup helpers
and graph templates. The source is an ordinary exported directory, not a Git
branch or worktree. The first packet and all original sources remain intact.

## Verification completed

- [Eight startup rejection tests](../data/encoder-startup-cpu.json) pass for
  changed hashes, extra files, symlinks, traversal, mismatched node copies,
  exclusive receipt creation and ownership failure before device import.
- [Ten diagnostic tests](../data/encoder-diagnostics-cpu.json) pass for the actual
  registered-state inspector, unchanged conditioning return, and unload hooks.
  Tests reject tensor-content reads/copies and allocation calls. Native candidate
  expectations are 289 RMSNorm weights and 48 scalars totaling 1,539,680 BF16
  bytes on XPU2; actual GPU placement remains unmeasured.
- [Eight client tests](../data/encoder-screen-client-cpu.json) pass, including a
  simulated 25-request campaign, exact-gate failure retention, and a later
  preflight failure that preserves the previous request's passing status.
  The simulation is not a GPU result.
- The actual copied launcher passed `--check-only` under the pinned LTX venv.
  [Post-check verification](../data/encoder-runtime-v2-check.json) rehashed every
  packet file, checked all four graph variants and frozen client dependencies,
  and confirmed no bytecode files or new server directory were created.
- [Original-process state](../data/encoder-v2-premaintenance-state.json) still
  binds PID24848, its start ticks, boot, frozen extensions and model verification.
  Its queue is idle and the fault latch is absent.

Independent review found three startup issues, fixed before freezing v2:
disable Python bytecode writes before the first packet-local import; include
final device selection and journal observation in fault recording; direct input
uploads into the new run directory. These change no power, swap or page-cache
settings. Database, input and temporary files are outside the source snapshot.

## Concrete next action, not executed

The current process cannot load these new capabilities through a supported
live API. A single deliberate graceful replacement would install them, then
all five screen arms would use that one new process. The current server remains
running pending that maintenance decision. This is not a restart/retry chain.

1. Revalidate PID24848's identity, idle queue, fault state and the preregistered
   hashes. Send that exact process one SIGINT only after the maintenance decision.
   Wait for its exit; if it does not exit cleanly, stop and preserve evidence.
   No automatic escalation, driver reset, reboot, or second start attempt.
2. Start the copied launcher once with the command below. It refuses existing
   evidence paths, conflicting locks/listeners/device owners, identity drift,
   insufficient memory/disk or a device fault. It performs one small copy/compute
   check on each card and then retains all locks for the persistent service.
3. Bind readiness to its actual process handle and `/ltx-encoder/identity`, not
   just a file. Startup observation timeout is not permission to restart it.
4. Run the [preregistered 25-request screen](../data/encoder-screen-01-prereg.json):
   control, crop, small_state, combined, control. Five requests per arm include
   initialization and four warm samples. Every request must match its original
   four-tensor oracle before the next request; every arm transition must pass
   actual unload ownership/accounting checks. A failure halts requests.
5. Preserve the new server afterward. Report screening results, initialization,
   timing drift, memory and failures. A passing candidate still needs the varied
   30-request qualification; four warm samples cannot support a speed headline.

Prepared launch command (no process has been started):

```bash
/home/steve/.venvs/ltx25-baseline/bin/python -u \
  /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-02/launch/serve-encoder.py \
  --packet /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-02 \
  --manifest-sha256 920d0e35774f298c9b11f80b3dd5e3708d0541f914e4c1857e96493bfd7282a8 \
  --run-name encoder-server-01
```

Append `--check-only` for the completed CPU/read-only check. When a real launch
is performed, capture its stdout/stderr into a new exclusively created log;
do not overwrite prior evidence. The client command, receipt paths and failure
semantics are in [the client note](encoder-screen-client.md).

Retain original references and failures. Prune only verified campaign archives
and older passing previews, with deletion receipts and at most three recent
previews. The existing lossless reference samples remain protected. No lower
precision, output dimensions, frame count or sampling steps are part of v2.
Compiler integration remains separate and is not enabled by this packet.

Repository checks: touched-document links and all 5,531 manifest paths pass.
The broad literal-pin audit still reports 231 historical drifted pins and zero
missing targets, unchanged from the previous turn; those are not this packet's
validation. The LTX client independently verifies every frozen helper digest,
and the v2 verification checks the complete prepared file inventory.

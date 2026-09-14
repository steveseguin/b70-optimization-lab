# Same-boot health assessment policy review

Read-only review after the packet11 OOM/xe incident. No device query, native
import, endpoint request, process change, or fault-latch change was performed.

`docs/local-ops.md:50–58` permits later work on the same boot after health is
re-established; a boot ID is provenance, not a consumption token. Its recovery
steps at lines61–73 first require stopped launches, preserved passive evidence,
at least60 seconds of quiet/drain assessment and a passive ownership recheck.
After assessing risk, line69 permits **at most one bounded active discovery/health
probe** if needed to classify the failure. This is a narrow diagnostic exception,
not permission to resume model or native CPU experiments. The current hold in
`CURRENT.md:50–68` should remain explicit, with any one diagnostic scoped in its
own incident-bound evidence. `AGENTS.md:5–25` still prohibits automatic reboot,
driver reset, power/memory-setting changes and restart/retry chains. The older
reload recipe in local-ops cannot override those newer user constraints.

There is no directly reusable current-incident driver. The existing
`scripts/check-external-boot-recovery-01.py` under this lane is pinned to a
different historical fault, a changed boot, and an unused historical output;
its journal gate rejects every fault in the current boot. Its lines51–73 contain
the relevant lock/ownership/memory/filter checks, and lines75–91 contain the
existing four-card tiny copy/compute diagnostic. Preserve that historical script.
The repository `scripts/check-qwen36-xpu-xccl-health.sh` instead continues after
individual device failures and proceeds to XCCL, so it does not implement this
incident's single stop-on-failure assessment. The recovery-snapshot shell helper
makes many active XPU-SMI calls and is expressly identified as nonpassive in
local-ops.

Supported next step: prepare/review a separate one-attempt diagnostic bound to
the current boot, exact unchanged FAULT hash, complete known incident journal
records/cursor and an unused evidence path. Require the normal exclusive host
and four-device locks, no conflicting owner/listener/container, runtime/source
identity, host-memory floor and no new journal fault. Reuse the tiny four-card
copy/compute operation and predeclare only the required peer-copy checks. Halt
at the first error/timeout/new fault; preserve its result and check passive
ownership/journal evidence after the diagnostic process exits. A narrow pass
means only that the tested discovery/copy/compute/peer paths worked once. Empty
render ownership alone proves none of those operations. Neither a pass nor a
quiet journal qualifies large model loads, the replacement memory policy, or
new native model work.

The inherited kernel detector omits OOM signatures; an incident assessment must
also reject new OOM/out-of-memory/process-kill events, while preserving the exact
known historical incident. The sealed packet11 checker still refuses any
`FAULT.json` (`launch/encoder_runtime_common.py:456–460`), and its launcher still
refuses historical current-boot fault matches. A diagnostic must not remove the
latch or weaken those gates automatically. Any later recovery admission requires
separate explicit review and a durable receipt; no reset authorization is implied.

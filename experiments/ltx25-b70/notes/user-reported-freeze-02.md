# User-reported freeze and confirmed reboot

On September14 the user reported another computer freeze and explicitly
confirmed restarting the computer afterward. Passive inspection at19:19UTC
observed boot `5414a640-c223-4a67-baa2-ec2f4c4c5917`, started about19:12UTC.
The agent did not reboot, reset a driver, change power or memory settings, or
launch the proposed GPU health assessment before this restart.

The old boot was `8e4b1b65-1c38-47bb-8ca5-e4fd6bbdf94a`. Its final saved
kernel entries are the18:12:58 host OOM and18:13:01 xe fault already preserved
with the failed LTX screen. The journal boot listing ends that boot's overall
saved entries at18:35:01UTC. Neither timestamp establishes when the later
freeze happened or what caused it. No new native LTX experiment had been
admitted after the OOM; the prepared same-boot diagnostic's one-use output
directory does not exist. Its old-boot admission is now invalid.

[Passive report](../data/user-reported-freeze-02/report.json) preserves the
user confirmation, changed boot, unchanged original FAULT hash, memory state,
and unowned render nodes. The new boot's captured kernel journal has no matches
from the existing GPU/watchdog/RCU/hung-task detector. This is passive evidence,
not GPU health or model-stability qualification.

The first collector saved command output but then failed while listing the
root-only pstore directory. Its command return codes were lost; that limitation
is recorded in the report. A separate read-only privileged listing found
**no pstore entries**; see [listing receipt](../data/user-reported-freeze-02/pstore-listing.json).
The initial old-boot journal selection also used a hyphenated ID unsupported by
this journalctl invocation. The corrected unhyphenated query returned exit0
and281,573 bytes; [its receipt](../data/user-reported-freeze-02/previous-kernel-corrected-command.json)
and compressed log preserve the actual historical evidence. Empty output from
the failed query must not be interpreted as missing old logs or a clean boot.

The existing root FAULT remains byte-identical. A separately pinned diagnostic
for the user-confirmed new boot is being prepared and reviewed; it may assess
limited device health while keeping that latch and model/CPU holds intact.
It must not silently reuse the obsolete same-boot admission or start a model.
Source preparation of the encoder lifecycle fixture and numerical speed leads
continues independently.

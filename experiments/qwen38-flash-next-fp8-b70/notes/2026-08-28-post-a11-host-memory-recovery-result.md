# Flash-Next post-A11 host-memory recovery result

Date: 2026-08-28
Status: reload lifecycle completed through one automatic reinsertion, but the post-reload memory-stability gate failed; no active qualification or successor model arm authorized

The preregistered 15-minute quiet window never reached its 105-GiB MemAvailable threshold. Sixteen passive samples ended at 105,109,064 KiB, so the single all-four recovery action was authorized.

The first privileged preflight stopped before any device action because the runtime classifier was invoked without an exact supervisor-script binding. That control failure is retained separately; it touched no card. A small bound wrapper fixed the classifier invocation and was committed before retrying the preflight.

The second preflight passed every frozen gate: clean repository, exact original swap layout, zero root-level card/render holders, clear runtime classifier, no relevant listener, inactive display manager, AST-connected console, disconnected B70 connectors, `xe.disable_display=1`, four freshly resolved BDFs, and healthy system/user managers.

All four unbind writes then completed. The strict sequence advanced past `modprobe -r xe` without recorded stderr. Before its immediate module-absence assertion, udev had already reinserted `xe`; the assertion stopped the script and the explicit `modprobe xe` command was never reached. The kernel journal proves the actual lifecycle: all four xe NVM instances were removed and each B70 completed one fresh driver initialization. I did not repeat the reload, use FLR, or reboot.

Four devices rediscovered at the established 42.87–42.88 MiB idle level and the bounded journal contained no new OOM, killed process, TTM eviction failure, reset, or timeout. Host memory nevertheless failed the mandatory stability gate. Across the following ten minutes, eleven passive samples ranged from 102,234,248 to 103,202,884 KiB and ended at 102,894,676 KiB, never approaching the required 110,100,480 KiB.

The recovery qualification therefore stops before per-card compute, peer access, XCCL, the known-good generation canary, or another vision packet. Lowering the admission floor and repeating the reload are both prohibited. The next device-lane action is a host reboot, which the local recovery policy requires the user to authorize explicitly. In the meantime, CPU-only website/package work remains safe and useful.

The pre-action-abort manifest contains 31 entries with SHA-256 `f4d3afc31ff584d4ae5b50acac239442e81b1a6d4ae355161fb4c98bd2a2d90a`. The primary recovery evidence manifest contains 61 entries with SHA-256 `1aa761b4f93866d8db49b276268c9c228b57f02c4be7e95744b7c634138ea196`; both verify. No protected speed, quality, coverage, or featured-result row changed.

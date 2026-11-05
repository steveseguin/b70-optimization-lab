# Four-card SC117 LAN service expiry review

Reviewed November 4, 2026, around 20:12 EST on steve-b70s. The owner reported
that Qwen Flash in the custom inference engine stopped responding after a couple
of days. This was a read-only operational investigation; only these records changed.

## Finding

The October 31 service deliberately expired after 47 hours. The launch script
`experiments/own-xpu-runtime/serving/four-card-lan/serve.sh` defaults
`LIFETIME_H=47` and passes it to the lab service. In
`experiments/own-xpu-runtime/research/tp/prefill-shexp-split-2026-10-31/lab/service.py`,
the monotonic deadline at line 1838 leads to the planned-lifetime branch at
1844 and graceful transport close at 1870. The sibling `adapter6_tp.py` line
122 enforces a native maximum of 172800 seconds (48 hours).

The prior boot journal confirms the sequence:

- October 31 21:40:01 EDT: service and separate card-lock unit started.
- October 31 21:58:16 EDT: service reported ready.
- November 2 19:40:12 EST: final service summary, reproduced below.

```json
{"passed": true, "stopped": "2026-11-03T00:40:11.733167+00:00", "requests": 309, "first_error": null, "monitor_first": null, "notes": [], "drained": true, "restarts": 0, "kills": 0, "retries": 0}
```

The count is the service's request counter, not a verified count of distinct
user requests. The clock changed from EDT to EST during this run; that accounts
for the one-hour discrepancy with CURRENT's earlier 20:40 prediction.
There is no evidence of an engine crash at shutdown. A filtered kernel-journal
review from October 31 through the end of the previous boot found no matching
fault, reset, timeout, OOM, killed-process, hardware-error or I/O-error lines.
This does not establish that every individual client request succeeded.

Journal source: `journalctl --user -b -1 -u sc117-tp-svc-4card-lan.service`,
previous boot ID `2cba7160054a4ffeb4c4e252eb956f5f`.
The original launch/environment logs remain under
`experiments/own-xpu-runtime/serving/four-card-lan/logs/`.

## State after today's reboot

Current boot ID: `f3360802694f4c1aa92779c40200c82c`, beginning about 19:25 EST.
The previous journal ends at 19:20:24 EST. The reboot's cause was not established.
No inference process or listener on 18160 was present. Both four-card transient
unit definitions are absent after reboot; the launcher uses `systemd-run`, not
an installed boot-start service.

Receipt `experiments/own-xpu-runtime/engine/receipts/37ee90a428cd.json` pins:

- binary `/dev/shm/engine-build-pss-20261031-r1/sc117-engine`;
- SHA256 `37ee90a428cd3b6ce1a6cca80457832de3abc314676d8085567533f8f77711a2`.

That binary path is absent. The handoff already warns that builds and runtime
assets in `/dev/shm` disappear at reboot. No rebuild or archive restoration was
attempted during this review.

All four expected B70 render-node symlinks exist. Memory blocks 53–57 each
report offline; `b70-offline-bad-memory.service` is enabled and active/exited.
Root storage reports about 30 GiB available (97% used); MemAvailable is about
113 GiB. No matching GPU fault lines were found in the new boot's journal.
No active GPU health probe was run, so this is not compute qualification.

## Required work for durable hosting

Rebuild and qualify the pinned engine and required runtime assets at persistent
paths. Add explicit persistent-serving lifetime support across the service,
transport and native engine rather than extending only `LIFETIME_H` or adding
a restart loop. Tie the separate card-lock holder's lifecycle to the server;
currently its `sleep infinity` is independent of a normal service expiry.
Keep fault monitoring and graceful shutdown. Decide boot-start behavior
separately from runtime persistence. The recorded model/configuration remains
SC117 Qwen3.8 Flash-Next IQ3S, four B70s, 131072 context, build `37ee90a428cd`,
flag set `tptsxqckhcbgls`, port 18160.

No engine/source behavior, units, power settings, memory settings, swap or
page-cache settings were changed. No service was started or restarted.

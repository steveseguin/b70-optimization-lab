# Qwen3.8 Flash-Next FP8 TP4 PIECEWISE MTP0 attempt 5 preregistration

Date: 2026-08-28
Status: frozen; not launched

Attempt 4 reached model loading on the intended ext4-staged packet and was at
78/131 shards when the watchdog stopped it at 11:20:28 America/Toronto. The
trigger was the corrected, non-fatal root-NVMe record for
`nvme 0000:01:00.0 [0] RxErr (First)`. The API/worker traceback at 11:20:34
followed the intentional TERM and is secondary. Attempt 4 produced no health,
request, quality, replay, or speed result.

Attempt 5 changes one safety-policy decision: a corrected/non-fatal RxErr that
is attributable only to frozen root-NVMe endpoint `0000:01:00.0` is retained in
the full journal and an exact complete-event-block extract but does not itself
stop the run. Watchdog and final adjudication call the same frozen classifier.
It parses complete APEI/AER blocks, binds each block's endpoint and severity,
and fails closed on orphan detail lines or any block that is not explicitly
corrected, RxErr-class, and exclusively rooted at `0000:01:00.0`. It accepts
severity separators using spaces, `=`, or `:`. The watchdog and final
adjudicator still fail closed on:

- any event naming B70 endpoints `0000:23:00.0`, `0000:27:00.0`,
  `0000:43:00.0`, or `0000:47:00.0`;
- an OOM, uncorrected/fatal PCIe record, RxErr not attributable to the frozen
  root NVMe, or corrected PCIe event naming another endpoint;
- an I/O error, NVMe error/reset/timeout/controller-down/offline condition,
  filesystem error/warning or read-only remount, and the other adverse storage
  signatures frozen in both watchdog and final adjudicator.

The original watchdog reason is durable: terminal adjudication creates its
generic watchdog-stop/heartbeat reason only when `resource.failed` is absent.

All attempt-4 ext4 staging, stable file identities, 64-GiB swap at priority
`-1`, resource floors, memory-pressure gates, paging-contamination exclusion,
heartbeat/race handling, lifecycle, exact cleanup, model/runtime identity,
PIECEWISE/MTP0 protocol, quality/replay/speed gates, and protected prior speeds
remain unchanged. Administrative identity alone advances to attempt 5, port
`19679`, `/var/tmp/q38-piecewise-graph-a5-resource`,
`/var/tmp/q38-piecewise-graph-a5-64g.swap`, attempt-5 USB run/cache/evidence and
archive paths, and `/tmp/q38-mtp0-current-piecewise-graph-a5*` state paths.

Frozen hashes:

- wrapper: `19f08177b2d12bd25e9b2c21f96fb5ee81aec7b8bd6c8c8e37af00b289631487`
- client adapter: `8da39d3c001651c05ca1d534c8e80f7f326207a61ead89a3be1499e1c14203b9`
- watchdog: `8cd82a5fd68ceaaf2fee28232996c24051c53902f247eebc50d623a667c1e40f`
- outer supervisor: `5096072f1097bd3d0ef0e80525247f6685473ad6e1aa94ceaef09f1318556649`
- shared event-block classifier:
  `440d7d0636bef8b5baf9bd5603ced988e22fe64c7df912ed15e55561aea8ea16`
- frozen fixture test:
  `f705d5210bd7041528e05223b571fdc7a59cf29a13b8f4373e7f288b6af75191`
- mechanically derived client:
  `0b7606190d48dea05d48660de9971bc7b76b64c0eb58a48c507fd60b22d40fc4`
- mechanically derived inner supervisor:
  `a3344488b98afc4d7ce7010a3da36a58ec6fbeee38e0f9061d188e08baf03aac`

No launch is authorized until independent read-only audit confirms the hash
chain, policy fixtures, fresh paths, and bounded attempt-4-to-attempt-5 diff.
The fixture test preserves the complete actual attempt-4 APEI/AER block and
requires it to pass byte-for-byte extraction; mixed root plus other-endpoint
RxErr, `event severity = fatal`, B70-addressed, and NVMe-timeout fixtures must
all fail.

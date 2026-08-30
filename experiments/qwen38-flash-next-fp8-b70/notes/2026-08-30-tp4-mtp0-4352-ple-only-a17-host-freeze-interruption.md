# Qwen3.8 Flash-Next FP8 A17 host-freeze interruption

Date: 2026-08-30
Status: infrastructure interruption; no model result

A17 passed artifact, four-card, staged-runtime, and TP4 collective preflight.
The API process then started on the frozen command and all four workers entered
distributed initialization. The last server record was at 01:49:11, before any
checkpoint-shard progress, PLE placement receipt, healthy endpoint, client
request, model output, trace, or timing. The host subsequently stopped
responding and was manually rebooted at 10:45. The journal contains no orderly
shutdown, OOM kill, B70-addressed reset/fault, kernel panic, or storage I/O
error. A17 is therefore neither a reliability result nor a model failure.

The prior boot had only about 35 GiB memory available and 73% swap occupied at
01:40 after the completed A16 load. It also recorded eight corrected PCIe
receiver events for the local Samsung NVMe (`0000:01:00.0`) earlier in the boot
and three delayed-file-release workqueue warnings at 01:44. Those observations
make accumulated host-memory/storage pressure the leading explanation, but do
not prove a single root cause because kernel logging stopped before the host.

The partial attempt-17 paths remain preserved and will not be reused. A fresh
post-reboot replica must use a new attempt, port, cache, lifecycle, and evidence
identity. No protected result changes.

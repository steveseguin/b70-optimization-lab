# Qwen3.8 Flash-Next FP8 A49 local-NVMe guard negative

Date: 2026-09-01
Status: bounded host-storage negative; zero quality or speed credit

A49 passed artifact, source, storage, four-device, host-policy, and initial
pressure gates. During early startup I/O, before useful checkpoint loading, the
local Samsung 980 PRO corrected-event count increased from `51` to `53`.
Memory remained above 126 million KiB, swap remained disabled, ASPM remained
at performance, and root-port AER remained zero. The one-second guard stopped
the arm immediately.

No endpoint or inference request existed. A few registry/compiler helpers
outlived the first teardown sample and caused final rc `70`; they exited on
their own within seconds. There is now no model process or listener, all four
B70s enumerate, and swap/ASPM were restored. The run and supervisor evidence
are retained under their attempt-49 paths on `/mnt/usb-models`.

This is direct evidence that high-volume reads from the local root NVMe are an
unsafe launch source on the current hardware link. It is not a Qwen, graph,
oneCCL, or GPU-memory failure. A50 keeps the complete A49 inference and quality
identity but reads the already validated identical 131-shard checkpoint from
the external drive.

# Qwen3.8 Flash-Next FP8 A45 worker trace-verifier negative

Date: 2026-09-01
Status: preserved healthy-endpoint, zero-request negative

A45 loaded the official checkpoint, captured the size-1 full-decode graph on
all four ranks, emitted four exact nonempty rank trace logs, and became healthy
under the real supervisor. The pre-request A43 verifier then rejected worker
rank 0 because PyTorch structured logging had consumed `TORCH_TRACE` from that
worker's environment. Zero inference requests were sent.

Offline validation of the captured evidence found exactly one log for each
rank 0–3, 20 allowed compile events, and only the pinned
`get_masked_input_and_mask:168` target. A46 permits a missing selector only for
the Linux-truncated EngineCore/worker process names and only after those exact
four nonempty rank logs exist. A conflicting value, missing/duplicate/extra
rank, empty log, unexpected log name, source drift, or unexpected compile
target remains fatal. Thirty combined A37/A43/A46 tests pass.

The supervisor tore down cleanly and all four B70s remained visible. The kernel
journal recorded two hardware-corrected PCIe receive events for the local NVMe
controller during the heavy checkpoint I/O; it recorded no B70 reset or fault.
No reboot is required.

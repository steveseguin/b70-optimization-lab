# Qwen3.8 Flash-Next FP8 A38 transient libccl-check negative

Date: 2026-09-01
Status: preserved pre-load integrity negative

A38 reached the frozen graph-safe oneCCL integrity gate, where one SHA-256 read
reported a mismatch. The launcher stopped before starting a model server or
loading any checkpoint. The same immutable path then produced the exact frozen
digest on five immediate independent reads; size, inode, and July mtime were
unchanged. No new kernel event appeared in the bounded journal.

This is retained as a transient artifact-read observation, not silently
discarded. A39 is a fresh path-only successor and adds three exact outer
oneCCL reads before entering the otherwise unchanged A38 launcher. Any mismatch
still fails closed. The earlier corrected PCIe receive reports naming the local
NVMe controller remain a plausible host-level concern, but there is no evidence
of a changed library or B70 failure.

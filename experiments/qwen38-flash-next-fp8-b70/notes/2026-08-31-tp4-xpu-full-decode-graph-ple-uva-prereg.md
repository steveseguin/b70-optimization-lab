# Qwen3.8 Flash-Next TP4 graph selective-UVA PLE preregistration

Date: 2026-08-31

Status: frozen before device execution

The collective sequence gate passed. This final no-model prerequisite captures
the synchronous PLE decode operation used by the protected endpoint: changing
global row IDs, rank-local masking, `index_select` from pinned host memory via
an XPU UVA view, byte-zeroing of nonlocal FP8 rows, and the 5,120-byte TP4
reduction through public oneCCL `4ceafd1`.

The production decode shape is one row, 16 n-gram heads, and head dimension
160. Each rank uses 65,536 synthetic local rows so the component remains small
while exercising the same pinned-host address space and FP8 output geometry.
For 100 replays, every row ID changes, the combined output must exactly equal
the CPU-generated FP8 oracle on all four ranks, and all 100 output hashes per
rank must be unique.

The probe SHA-256 is
`a5b6e9a2455aa4d1661ae403ef5d0d8423ebe55e3d4d9476d3e481a2be8850e2`.

Async PLE remains disabled. Timing includes input generation/copies,
synchronization, output copies, and CPU oracle work and is diagnostic only. A
pass authorizes one full-model `FULL_DECODE_ONLY` size-1 arm with the complete
quality battery; it is not itself a model or speed result. No reboot is
authorized.

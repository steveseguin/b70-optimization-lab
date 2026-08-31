# Qwen3.8 layer-0 GDN out-projection padding D32 result

D32 completed all 80 loaded-projection calls: two repeats at ten row counts
in each of four fresh processes.

| Rows | Unique hashes (8 calls) | Classification |
| ---: | ---: | --- |
| 1 | 5 | nondeterministic |
| 2 | 1 | deterministic |
| 4 | 1 | deterministic; same row-0 result as M=2 |
| 8 | 1 | deterministic; same row-0 result as M=2 |
| 16 | 1 | deterministic; same row-0 result as M=2 |
| 32 | 1 | deterministic |
| 64 | 3 | nondeterministic |
| 128 | 4 | nondeterministic |
| 256 | 1 | deterministic through existing M=512 pad |
| 512 | 1 | deterministic |

M=2 is the smallest passing dispatch and requires only one zero row. The
M=1 race is both within-process and cross-process, directly explaining why
standalone tests that happened to use benign weight contents did not close the
production lane.

The repair patch extends the existing oneDNN determinism gate with M=1→M=2:
`../patches/vllm-xpu-kernels-qwen38-onednn-int4-m1pad2-determinism-20260831.patch`.

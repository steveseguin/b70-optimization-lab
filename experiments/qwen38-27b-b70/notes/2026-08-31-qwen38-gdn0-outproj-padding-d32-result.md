# Qwen3.8 layer-0 GDN out-projection padding D32 result

D32 completed all 80 loaded-projection calls: two repeats at ten labels in
each of four fresh processes. A post-run audit found that the label `1` did
**not** construct a one-row tensor: it passed the complete 71-row normalized
prefill tensor. The other labels constructed tensors with the stated row
count and copied only prefill row zero into them.

| Rows | Unique hashes (8 calls) | Classification |
| ---: | ---: | --- |
| `1` label (actual M=71) | 5 | nondeterministic |
| 2 | 1 | deterministic |
| 4 | 1 | deterministic; same row-0 result as M=2 |
| 8 | 1 | deterministic; same row-0 result as M=2 |
| 16 | 1 | deterministic; same row-0 result as M=2 |
| 32 | 1 | deterministic |
| 64 | 3 | nondeterministic |
| 128 | 4 | nondeterministic |
| 256 | 1 | deterministic through existing M=512 pad |
| 512 | 1 | deterministic |

The original conclusion that M=1 was the failing dispatch is withdrawn. D32
did not test true M=1 at all. It instead proves that the loaded projection is
nondeterministic at the real M=71 prefill boundary, while separately
constructed M=2/4/8/16/32 and M=512 row-zero calls are stable. Earlier true
M=1 standalone and stacked-production screens passed, which is consistent
with this correction.

The two M=1→M=2 kernel patches derived from the mislabeled row are retained as
negative historical artifacts and must not be deployed. D35 instead tests a
dispatcher-ordered prefill repair for the actual failing row band.

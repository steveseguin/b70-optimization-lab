# Qwen3.8 Flash-Next FP8 A79 result: loading from the local NVMe copy

Date: 2026-09-03 10:00--10:16 EDT
Status: **complete frozen-client pass; every output identical to A73/A78**;
the lane's servers now load from the NVMe copy

## Timing

| phase | A79 (NVMe copy) | A78 (USB copy) | A73 (USB copy) |
| --- | ---: | ---: | ---: |
| `Loading weights took` | **66.1 s** | 545.9 s | 541.8 s |
| engine init (profile, KV, warmup, graph capture) | 227.7 s | about 228 s | 228.1 s |
| launch to `Application startup complete` | **6.5 min** | 14.5 min | 14.5 min |
| frozen client | 9.0 min | 9.5 min | 9.0 min |

A full attempt therefore takes about 16 minutes instead of 24. The engine
init is now the largest fixed cost: about 45 s of graph capture and the
rest profiling and warmup, which the eager line paid as well.

## Gates

`client-gates-passed.txt` names `exact-4K-repeat`; the runtime receipt
passed (1487 size-1 FULL dispatches); the summary equals the A73 and A78
summaries field for field apart from timings: short rows
`24.729239 / 23.913248 / 22.849184 tok/s`, exact-2K `14.485850 / 14.576682`
(hash `afffd211...`), exact-4K `13.114159 / 12.608820` (TTFT 96.2 / 98.7 s,
hash `c6193cc6...`), quality 6/7 with the same normalized outputs, 16/16
repeat, exact needle. No guard fired: the bounded root-NVMe read guard now
allows 256 GiB, and the corrected-AER delta stayed within its unchanged
64-event bound while the load read 173 GB from the root SSD at Gen4.

## Reading

The deterministic line is unchanged by where the bytes come from, as it
must be, and the lane gains eight minutes per attempt. Later packets derive
from A79 (`MODEL_PATH` on `/mnt/fast-ai`, read cap 536,870,912 sectors). Two
operational notes for anyone driving this lane: the host wrapper refuses
to start while any swap is in use, and hashing or copying the model on the
same host pages a few tens of MB out, so `swapoff`/`swapon` (the wrapper's
own toggle) and a dropped page cache precede every launch; and process
checks must not use a pattern that appears in the checking shell's own
command line.

Receipts: run dir `...attempt79/`, tracked
[`summary`](../data/20260903-tp4-mtp0-a79-nvme-load-deterministic-summary.json)
and [`runtime-after`](../data/20260903-tp4-mtp0-a79-fullgraph-runtime-after.json).

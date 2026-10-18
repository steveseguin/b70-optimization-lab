# Packet123: bundle7 slack admission is unproven

The old command-only formula reports 0.482640 ms on hits, but it includes
mandatory rank0 suffix-head service. It is not evidence that a mixer or FFN
can move to rank0. Usable slack is unknown; no candidate is admitted.
[Closeout](SLACK-CLOSEOUT.md), [boundaries](DO-NOT-REPEAT.md),
[task note](../../../../notes/2026-10-18-own-runtime-packet123.md).

## Measured command accounting

Lane B, cards2+3, existing packet118 composite candidate, fixed bundle7
selection `0a43e349d1bd86562c2b674392a12f917d36d9918839b34aee8c33a5df22545c`,
binary `f77e0e9c50fa9f75d6d0900efa0241911fee34806dc9d118e1d9fab7edb73a01`.
The target is the quantized compressed Flash-Next lane, unchanged
`iq3-p49-split32-v1`. This analysis is not a benchmark or promotion.

Each of twelve saved 128-token requests contributes its first99 emission
intervals. Hit/miss labels the guess verified at the starting emission.
Conditional pooled means are not class-balanced throughput.

| Bundle7 measurement, ms | Hits (932) | Misses (256) |
| --- | ---: | ---: |
| Full interval | 14.960747 | 25.803577 |
| Rank0 recorded command union | 12.853664 | 25.254390 |
| Rank0 outside recorded commands | 2.107083 | 0.549188 |
| Rank1 recorded command union | 14.940611 | 14.989112 |
| Rank1 outside recorded commands | 0.020136 | 10.814465 |
| Next rank0 speculation A | 12.853387 | 12.848083 |
| Rank1 target B, including head merge wait | 13.335624 | 13.383911 |
| Rank1 draft D | 1.604737 | 1.604953 |
| Rank0 correction C | 0 | 11.846807 |
| Rank0 restore R | 0 | 0.559249 |
| Apparent tail B − A − start offset | 0.482640 | 0.535270 |
| Loose mean usable-slack upper bound | 0.439630 | 0.492260 |
| Actual usable slack | unknown | unknown |

Packet118's preceding control is packet103 bundle5, with no split head.
Its apparent hit/miss race slack is 0.496203 / 0.845679 ms (936/252
intervals); it cannot establish bundle7 admission. Both runs' individual
intervals and per-prompt summaries are retained. The candidate's summary was
not present at the snapshot; all twelve request receipts were present. This
does not certify completion of its enclosing screen or bracket.

## Why the head makes the old formula insufficient

`native_controller.hpp::Backend::wait` invokes `before_remote_wait` outside
`execute` and hence outside the `rank_trace` command envelopes.
`rank.hpp` binds that callback to `p105::Runtime::service`. Rank0 waits for
the verified hidden vector, imports it, executes its suffix projection and
argmax, exports its best result, and publishes its reply. Rank1's
`merge_target` waits for this reply **inside** its target command.

Thus rank0's apparent outside time contains real work. The copied packet108
formula `B-A-offset` also includes that work and cannot label it spare time.
This is an accounting limitation, not a head correctness finding.

Across all1,600 candidate head services (the incident64 plus twelve128-token
requests), hidden import takes at least21.169 µs and best export at least
21.841 µs. Every service therefore contains at least43.010 µs of recorded
copy envelopes. Their sum gives a conservative upper bound after subtraction;
it is not a measurement of pure DMA or total head service. Suffix compute,
uploads and mailbox waits are additional and unseparated. The transfer rows
have durations but no absolute timestamps, request identity or position.
Both ranks' `sites.jsonl` and `timings.jsonl` are empty.

A new timing receipt must expose common-clock service entry, hidden-ready,
suffix compute begin/end, reply publication, rank1 prefix-ready and merge
completion, bound to request/position/sequence. That permits separating
dependency wait from required work and identifying which completion limits
the cycle. A CPU replay cannot create these missing device observations.
Only after ≥0.3 ms usable hit slack is supported should partial placement,
memory census, GNU/Intel byte checks, startup/seals and the conditional v4
B→A proposals proceed. No speed estimate is a substitute for that gate.

## Reproduce without the original untracked trace files

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet123-partial-placement/extract.py --check </dev/null
```

`method/p108_extract.py` and `method/p85_model.py` are byte-preserved copies.
Only the unchanged `union_ms`, `duration` and `intervals` function ASTs are
executed; historical import-time resource caps are never executed or imported.
The new CPU entry applies its own cap. `--check` verifies every archived
input's size/hash and reproduces both outputs without writing them.

`inputs.tar.gz` preserves44 original-byte members, including an index, the
24 receipts, identities, selections, manifests, relevant rank logs and the
three controller/head source files. `capture_inputs.py` verifies source bytes
again after capture and verifies every archive member before writing. It
refuses to overwrite a snapshot. The original frozen files remain untouched.
`slack.json` contains the summary and pins; `intervals.json.gz` preserves all
2,376 interval rows and the original method's fields. Its historical field
`rank0_slack_ms` means **apparent tail**, never admitted slack on bundle7.

[Validation](validation.json): deterministic replay passes. A separate
read-only reviewer recomputed all4,752 rank unions with a sweep-line method;
the maximum difference was0.0 ms. Both copied methods match their originals,
and all43 original input members match their pinned hashes and current bytes.

## Retention

The1,344,905-byte input archive exceeds1 MiB intentionally: the device receipts
were untracked when read, and hashes alone would not make this diagnosis
reproducible from Git. Its exact bytes are required to review the accounting.
No originals were removed. Restore by reading members with Python `tarfile`
or extracting to a new scratch directory; member paths are repository-relative.
The analysis requires no model weights, GPU, service or compiler. There is no
build directory; all retained packet artifacts together are under2 MB.

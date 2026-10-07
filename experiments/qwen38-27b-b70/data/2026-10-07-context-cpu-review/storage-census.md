# Completed context campaigns: storage census

CPU-only, read-only measurement on 2026-10-07. No active history outputs were inspected. Byte counts are exact at inspection; this report separates actual disk files from logical serialized content. These are completed-run sizes, not peak RAM, peak WAL, write traffic, GPU memory or extrapolated scaling measurements.

**Finding:** the 44 trial directories occupy 15,210,751 apparent bytes. Sparse trial evidence occupies 21.52–30.70 times original source text; tiny semantic trials occupy 114.50–309.69 times source, largely from fixed SQLite/SHM and evidence overhead. The useful final 128-counter table is only 1,895–1,900 compact JSON bytes, compared with roughly 1.28–1.43 MB of trial files. Prompt limits are not total-memory bounds.

## Per-trial storage

`DB` is main SQLite plus WAL and SHM. `Logs` is model-call evidence. `Trace` excludes result receipts. `Receipts` includes native/outer result.json. Snapshot bytes were zero in every trial: these engines do not have history_v1 snapshots. `Disk/source` divides all trial-directory apparent file bytes by unique original batch-text bytes, not by model tokens.

| Run/case | Arm | Source bytes / tokens | Final counters / state checkpoints | DB bytes | Logs bytes | Trace bytes | Receipts bytes | Total trial bytes | Disk/source |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| semantic-v1/s01-control | summary | 494 / 145 | 0/0 | 65,536 | 26,137 | 2,212 | 6,205 | 102,473 | 207.44× |
| semantic-v1/s01-control | archive | 494 / 145 | 2/4 | 65,536 | 61,173 | 2,280 | 7,501 | 140,287 | 283.98× |
| semantic-v1/s01-control | quoted | 494 / 145 | 2/4 | 65,536 | 63,932 | 7,251 | 12,472 | 152,987 | 309.69× |
| semantic-v1/s01-stress | archive | 736 / 195 | 2/4 | 65,536 | 65,933 | 2,292 | 7,753 | 145,792 | 198.09× |
| semantic-v1/s01-stress | quoted | 736 / 195 | 2/4 | 65,536 | 69,279 | 7,314 | 12,773 | 159,179 | 216.28× |
| semantic-v1/s01-stress | summary | 736 / 195 | 0/0 | 65,536 | 28,770 | 2,610 | 6,601 | 106,076 | 144.12× |
| semantic-v1/s02-control | quoted | 517 / 155 | 2/4 | 65,536 | 54,230 | 7,431 | 12,319 | 142,810 | 276.23× |
| semantic-v1/s02-control | summary | 517 / 155 | 0/0 | 65,536 | 24,702 | 2,241 | 6,236 | 101,131 | 195.61× |
| semantic-v1/s02-control | archive | 517 / 155 | 2/4 | 65,536 | 50,740 | 2,280 | 7,170 | 129,021 | 249.56× |
| semantic-v1/s02-stress | summary | 811 / 221 | 0/0 | 65,536 | 26,935 | 2,632 | 6,624 | 104,305 | 128.61× |
| semantic-v1/s02-stress | archive | 811 / 221 | 2/4 | 65,536 | 57,679 | 2,292 | 7,450 | 136,791 | 168.67× |
| semantic-v1/s02-stress | quoted | 811 / 221 | 2/4 | 65,536 | 59,906 | 7,494 | 12,650 | 149,419 | 184.24× |
| semantic-v1/s03-control | archive | 542 / 160 | 2/4 | 65,536 | 65,368 | 2,292 | 8,129 | 146,157 | 269.66× |
| semantic-v1/s03-control | quoted | 542 / 160 | 2/4 | 65,536 | 57,410 | 7,622 | 12,535 | 146,445 | 270.19× |
| semantic-v1/s03-control | summary | 542 / 160 | 0/0 | 65,536 | 25,186 | 2,325 | 6,319 | 101,829 | 187.88× |
| semantic-v1/s03-stress | quoted | 743 / 205 | 2/4 | 65,536 | 57,008 | 7,678 | 12,772 | 146,703 | 197.45× |
| semantic-v1/s03-stress | summary | 743 / 205 | 0/0 | 65,536 | 25,819 | 2,313 | 6,304 | 102,425 | 137.85× |
| semantic-v1/s03-stress | archive | 743 / 205 | 2/4 | 65,536 | 63,829 | 2,292 | 7,388 | 142,755 | 192.13× |
| semantic-v1/s04-control | summary | 564 / 172 | 0/0 | 65,536 | 25,901 | 2,369 | 6,363 | 102,641 | 181.99× |
| semantic-v1/s04-control | archive | 564 / 172 | 2/4 | 65,536 | 60,920 | 2,292 | 7,468 | 140,004 | 248.23× |
| semantic-v1/s04-control | quoted | 564 / 172 | 2/4 | 65,536 | 65,136 | 7,801 | 13,093 | 155,503 | 275.71× |
| semantic-v1/s04-stress | archive | 838 / 218 | 2/4 | 65,536 | 64,795 | 2,292 | 7,739 | 144,695 | 172.67× |
| semantic-v1/s04-stress | quoted | 838 / 218 | 2/4 | 65,536 | 69,185 | 7,855 | 13,300 | 160,208 | 191.18× |
| semantic-v1/s04-stress | summary | 838 / 218 | 0/0 | 65,536 | 26,628 | 2,470 | 6,462 | 103,604 | 123.63× |
| semantic-v1/s05-control | quoted | 564 / 173 | 2/4 | 65,536 | 72,915 | 7,802 | 13,092 | 163,281 | 289.51× |
| semantic-v1/s05-control | summary | 564 / 173 | 0/0 | 65,536 | 25,836 | 2,353 | 6,345 | 102,524 | 181.78× |
| semantic-v1/s05-control | archive | 564 / 173 | 2/4 | 65,536 | 53,387 | 2,292 | 7,225 | 131,828 | 233.74× |
| semantic-v1/s05-stress | summary | 868 / 255 | 0/0 | 65,536 | 28,349 | 2,764 | 6,755 | 106,059 | 122.19× |
| semantic-v1/s05-stress | archive | 868 / 255 | 2/4 | 65,536 | 66,967 | 2,292 | 7,766 | 146,953 | 169.30× |
| semantic-v1/s05-stress | quoted | 868 / 255 | 2/4 | 65,536 | 73,458 | 7,809 | 13,375 | 164,669 | 189.71× |
| semantic-v1/s06-control | archive | 645 / 195 | 2/4 | 65,536 | 52,212 | 2,336 | 7,323 | 130,897 | 202.94× |
| semantic-v1/s06-control | quoted | 645 / 195 | 2/4 | 65,536 | 59,068 | 7,839 | 12,821 | 148,750 | 230.62× |
| semantic-v1/s06-control | summary | 645 / 195 | 0/0 | 65,536 | 26,172 | 2,449 | 6,440 | 103,097 | 159.84× |
| semantic-v1/s06-stress | quoted | 958 / 258 | 2/4 | 65,536 | 57,876 | 7,839 | 13,034 | 148,200 | 154.70× |
| semantic-v1/s06-stress | summary | 958 / 258 | 0/0 | 65,536 | 31,209 | 3,071 | 7,060 | 109,695 | 114.50× |
| semantic-v1/s06-stress | archive | 958 / 258 | 2/4 | 65,536 | 53,338 | 2,354 | 7,554 | 132,722 | 138.54× |
| sparse-v1/sparse-n8-seed83 | archive | 38,663 / 7534 | 8/17 | 135,168 | 759,669 | 15,576 | 59,044 | 1,048,536 | 27.12× |
| sparse-v1/sparse-n8-seed83 | quoted | 38,663 / 7534 | 8/17 | 143,360 | 840,057 | 40,428 | 85,061 | 1,187,138 | 30.70× |
| sparse-v1/sparse-n128-seed83 | quoted | 57,772 / 12063 | 128/24 | 196,608 | 784,617 | 136,562 | 170,118 | 1,344,313 | 23.27× |
| sparse-v1/sparse-n128-seed83 | archive | 57,772 / 12063 | 128/24 | 163,840 | 867,994 | 157,950 | 188,472 | 1,428,193 | 24.72× |
| sparse-replication-v1/sparse-n128-seed83 | archive | 57,772 / 12063 | 128/24 | 163,840 | 867,992 | 157,950 | 188,592 | 1,428,347 | 24.72× |
| sparse-replication-v1/sparse-n128-seed83 | quoted | 57,772 / 12063 | 128/24 | 196,608 | 784,619 | 136,562 | 170,241 | 1,344,474 | 23.27× |
| sparse-replication-v1/sparse-n128-seed97-dispatch | quoted | 59,560 / 12242 | 128/24 | 196,608 | 714,955 | 140,146 | 174,469 | 1,281,996 | 21.52× |
| sparse-replication-v1/sparse-n128-seed97-dispatch | archive | 59,560 / 12242 | 128/24 | 163,840 | 824,232 | 158,206 | 192,958 | 1,395,839 | 23.44× |

Summary arms intentionally have no structured observed counter table/checkpoint history; their reference documents still have counters. The reference counts, maximum observed counts and every file size are in the JSON. Checkpoint correctness is not inferred from count or storage size.

## Whole completed campaigns

| Run | Apparent file bytes | Allocated bytes, unique inode | Bytes outside trial directories |
|---|---:|---:|---:|
| context-semantic-v1-20261007 | 126,333,914 | 129,204,224 | 121,581,999 |
| context-sparse-v1-20261007 | 126,781,187 | 128,999,424 | 121,773,007 |
| context-sparse-replication-v1-20261007 | 127,316,447 | 129,540,096 | 121,865,791 |

Whole-run directories additionally preserve about 120 MB of server compiler-cache artifacts each. These are shared launch/runtime artifacts, not model source archive, counter state, prompt/KV reuse, or per-trial working state. Their exact sizes are recorded separately in JSON; retaining three copies makes the whole-run total much larger than the trial census.

## What occupies trial disk

| File category | Apparent bytes | Share |
|---|---:|---:|
| model_call_evidence | 8,241,523 | 54.2% |
| sqlite | 3,719,168 | 24.5% |
| result_receipt | 1,551,371 | 10.2% |
| attempt_trace | 1,092,510 | 7.2% |
| answer_session | 255,816 | 1.7% |
| retrieval_evidence | 246,354 | 1.6% |
| other_identity_and_evidence | 75,906 | 0.5% |
| latest_checkpoint | 28,103 | 0.2% |

The categories sum to trial-directory files. Whole-run totals also include compiler caches, launcher, health, strict qualification, identity and summary artifacts outside those directories. Shared packet files/model/tokenizer weights and repository source are excluded from run-directory totals. Allocated sizes use st_blocks×512, deduplicated by inode for the whole-run measure; filesystem metadata, compression/dedup beyond inode identity and deleted files are not measured.

## Runtime state versus retained evidence

All three arms archive every original batch in canonical.sqlite for later retrieval. SQLite logical source text exactly matches the packet text in this census. The archive arm name does not mean SQLite stores its accepted counter table: archive and summary leave SQL current_state/events/receipts empty. Archive keeps its model-produced state in the Python state variable and latest checkpoint.json. Quoted alone also persists SQL current_state, applied event payloads and receipts. All tables/page allocations and logical UTF-8 text-column bytes are listed in JSON. SQL row JSON sizes are logical proxies, not the physical SQLite encoding.

Small DBs pay page/schema/index overhead, plus a 32 KiB shared-memory sidecar. WAL was empty for every completed trial; the script refuses to ignore any nonempty WAL. This does not measure peak WAL or cumulative writes. Main SQLite reads use mode=ro&immutable=1, so no checkpoint/recovery writes occur.

Evidence duplication is intentional but large: result.json repeats trace batches and the complete final answer session; trace records accepted response states as well as observed states; calls.jsonl records full prompts, response text and raw/model-response evidence; prompts repeatedly serialize retained source/state/memory. answer-session.json repeats cached source retrievals and retrieval.jsonl records their returned copies. Quoted event payloads repeat verified source quotes inside the DB. Logical sizes of each of these views overlap and must not be summed as unique information. The JSON marks the exact result/trace and result/session equalities.

There is one latest checkpoint file per trial, overwritten on each accepted batch, not one separate checkpoint file per historical state. Historical states in these runs survive in audit trace/result evidence; they were not an exposed state_at retrieval facility. Snapshot files are absent, so no claim about history_v1 snapshot amplification follows from this census.

The 32,768-byte limit bounds each serialized model prompt, and the 6,553-byte limit bounds the model-authored memory string. They do not bound process RAM, total disk, accumulated source archive, counter-table cardinality, full task/oracle input, cached retrievals, or retained calls/trace lists. The frozen live.py retains calls and trace rows in Python across the trial and loads the whole compiled task/public source. It also repeatedly writes full trace JSON. Thus prompt-bounded is accurate; constant-space or bounded-total-memory is unsupported. This census measures serialized lower-level proxies only; no live/peak RSS or Python heap was sampled.

Each trial includes actual final state JSON bytes, peak observed state bytes/count, all observed-state serialization, final memory bytes, final retrieval-cache bytes and retained call/trace serialization in JSON. These help distinguish a small useful current-state table from large reproducibility artifacts, but do not isolate a minimal production implementation or predict its speed/memory.

## Reproduce and interpretation limits

Run with PYTHONDONTWRITEBYTECODE=1 /mnt/fast-ai/venvs/clm/bin/python3 /tmp/context-storage-census.py. It reads only the three explicitly named completed campaign roots and their frozen packets, plus the local tokenizer; it writes only /tmp/context-storage-census.json and /tmp/context-storage-census.md. No imports from frozen runtime modules, model requests, synthetic replay or mutations of original databases are needed. Source token counts sum independent original-batch encodings without special tokens/chat template; they are not prompt tokens. Tokenizer identity/version and source/result/summary hashes are recorded in JSON.

This is a resource-accounting diagnostic. It does not weaken quality gates, establish long-stream asymptotics, estimate active history outcomes or authorize storage pruning. Raw evidence remains preserved. A future RAM claim needs separately designed peak-RSS/heap measurement and an explicit archive/evidence retention policy; merely shrinking the prompt or memory string is insufficient.

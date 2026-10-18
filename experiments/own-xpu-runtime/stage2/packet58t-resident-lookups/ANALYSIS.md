# Packet58t: exact packed lookup storage at load

The production and tile16 prepared one-card paths read exactly two GGUF
weight tensors on the host during `prepare_token`. Their lookup path is the
same. [Metadata census](evidence/lookup-inventory.json) and
[source analysis](../packet58q-onecard-variance/ANALYSIS.md) pin the inputs.

| Tensor | Packed bytes | Row bytes | Rows per token | Selection |
| --- | ---: | ---: | ---: | --- |
| token_embd.weight, Q6_K | 521,472,000 | 2,100 | 1 | current token |
| per_layer_token_embd.weight, IQ4_NL | 28,800,138,240 | 90 | 16 | two history hashes, eight independent vocabulary segments each |

Both live in GGUF shard 2, absolute byte ranges `[29328644032,29850116032)`
and `[528505792,29328644032)` respectively. There is no lookup sidecar.
The model contains 248,320 embedding rows and 320,001,536 PLE rows. The
per-token source traffic is just **3,540 packed bytes**, spread across 17
row mappings; rows can cross 4 KiB page boundaries. `Slice` maps read-only
file pages privately and unmaps after each read. Source reads in packet58q
were inferred from code and correlated counters, not measured fault addresses.

The 35 PLE metadata integers (280 bytes) are copied from parsed GGUF header
metadata into an ordinary vector during initialization. The per-token IDs
(4 + 16×8 = 132 bytes), history, directory entries and cache/index maps are
ordinary owned host objects. Route weights and device index tables are loaded
before inference. The 48,627,712,000 expert bytes already live in pinned banks
in both views; misses do not read a GGUF mapping. Quantization scales are
inside the two packed rows: 340 bytes of the 3,540-byte input, not a separate
scale-table mmap. IQ4's 16-level dequantization table is compiled code data.
Dequantization writes 10,240 BF16 bytes before the existing uploads.

The candidate copies all rows of exactly these two tensors at load, in at
most 4 MiB chunks, into anonymous memory. Streaming SHA-256 of source chunks
must equal SHA-256 of copied chunks before read-only protection. Per-token
reads use these copies; a missing selected tensor refuses instead of silently
falling back. Arithmetic, packed representation, uploads, device weights,
expert cache, BF16 KV and packet49 oracle are unchanged. There is no mlock,
page-cache advice, cache drop or whole-model pre-read. Anonymous pages are
faulted in by the copy but are not unswappable; zero future faults under every
possible host pressure is not promised.

The additional private allocation is **29,321,610,240 bytes**. Existing timing
admission reserved the same bytes as file-backed nonexpert/lookup pages; the
new plan splits that category into anonymous lookup storage and remaining
file-backed weights. The 118,308,908,048-byte timing requirement and 8 GiB live
reserve remain. Exactness windows previously allowed sparse reclaimable
lookups, so their requirements increase by the full copy size. Source chunks
are ordinary reclaimable file pages, with no second full mapping or private
copy. The 256 MiB loader staging bound covers the 4 MiB chunk and hash work.
Actual full-size resident loading remains a device-window admission check.

Packet58r is present but frozen. Packet58t therefore carries a separate copy
of its one-load bracket machinery and adds a backing view: tile16 file-backed
A0 / tile16 resident B0 / tile16 file-backed A1. All copies are made before A0,
and retained through all three views, so memory pressure is matched. Loading
the copies necessarily reads their source pages; **this bracket cannot recreate
58n's original cold file state**. It tests backing choice after the same load,
not a claimed elimination of the historical disk delay. No selected prompts
or prompt/KV/response state are reused. The repeated suite is a diagnostic
screen, never an independent fresh-process performance repeat or final gate.
Every token retains preparation and whole-token fault counters alongside times.

The inherited `model_payload_bytes_read` field counts logical weight reads,
including anonymous lookup reads. It is not a disk-I/O counter. The new
preparation fault fields measure process faults around the actual preparation
call; the CPU replay separately proves zero file-reader calls for resident rows.

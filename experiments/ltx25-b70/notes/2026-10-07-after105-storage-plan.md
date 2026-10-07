# One bounded storage plan for106

At19:47:05UTC, the actual destination filesystem had56,271,626,240 bytes
(52.407036GiB) available. The proposed106 budget is57 requests:
20 native +14 candidate +14 timed +9 setup, with50 raw captures
(20+14+14+2 setup). A4GiB runtime allowance plus384MiB source copy above the
50GiB reserve requires54.375GiB. It is **not currently admitted**; the gap is
2,113,085,440 bytes (about1.968GiB).

**105 is retained live and protected.** PID3329528 and successful completion
were reported by the coordinator; independent full sealed105 proof is owned
by the coordinator. This audit read receipt JSON and exact-path file metadata
only. No raw archive content was read, no proof was rerun, and no file/process
was changed. These are conditional options, not a deletion authorization.

The bounded metadata record is
[client106-storage-plan.json](../data/resume-20261007/client106-storage-plan.json).
It contains receipt SHA256 bindings, all40 candidate/keeper mappings, original
stat metadata, stored full-file hashes and all26 protected restoration anchors
from the existing103 and post104 retirement maps.

## Recommended conditional40-file subset

The50 scored105 archives have ten distinct full-file hashes in the recorded
proof. Each is74,621,016 logical bytes, regular, with nlink1 at this metadata
check. Preserve all ten
`resolution-client-reverse-20261007-native-p1-FIXTURE` archives as direct local
keepers. The candidate sets are:

| Request-name suffix after `resolution-client-reverse-20261007-` | Files | Current allocated bytes |
| --- | ---: | ---: |
|`native-p2-FIXTURE`, all ten original fixtures |10 |746,274,816 |
|`candidate-check-04` through`candidate-check-13` |10 |746,270,720 |
|`timed-fast-04` through`timed-fast-13` |10 |746,287,104 |
|`timed-04` through`timed-13` |10 |746,287,104 |
|Total |40 |2,985,119,744 |

Each exact archive path is
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/output/validation/NAME/tensors.safetensors`.
Map by the verified **emitted** fixture to native-p1, not the currently submitted
pipeline prompt. Every recorded whole-file hash matches its proposed keeper;
this has not been freshly verified against the archive bytes by this audit.
Preserve all request histories, phase/policy receipts, tensor summaries, timing
records, previews, fills/setup outputs, models, source, patches and failed work.
All existing103 anchors and post104 restoration keepers remain untouched.

The conditional allocated reclaim is2.780109GiB. Estimated available space
would become59,256,745,984 bytes (about55.187GiB), leaving872,034,304 bytes
(0.812145GiB) beyond the combined106 allowance and reserve. A fresh storage
check after actual verified cleanup must admit the complete remaining budget;
these figures reserve nothing. The384MiB source copy alone fits now, but the
runtime4GiB does not. If the source is built first, account for that completed
write rather than double-counting it at final runtime admission.

Fifty nominal archives consume3,731,050,800 bytes (3.474811GiB), leaving about
0.525189GiB of the4GiB allowance for previews/logs/other writes. This is a bounded
planning allowance, not a hard global cache-size guarantee; retain the actual
free-space refusal and fixed request/capture limits.

## Why stop at this one option

Retiring only the30 candidate/fast/control duplicates while keeping both native
passes would leave about0.117123GiB beyond the full budget. That technically
fits this snapshot but is too small a margin to recommend over the40-file plan.
Historical101c/102 duplicates from the prior plan are already retired; their
remaining native-p1 files are restoration anchors, so none can be counted again.
104's remaining native-p2 set could contribute about0.695GiB, but its full proof
now requires restoring already-retired candidate/fast archives.103 similarly
needs a30-archive restoration cycle before unchanged full replay. Neither is a
less intrusive route than a fresh complete105 proof followed by one direct map.
No broad cache/model scan or old-proof restoration cycle is proposed.

Before any retirement: complete105's unchanged sealed native/candidate/fast/control
proof while all raw paths exist; perform only the necessary controlled reload
stop; verify the exact stopped identity and absence of fault; freshly verify
whole archives, sizes, distinct nlink1 inodes and execution bindings; review a
fixed40-file ledger; then use durable exclusive restore maps and per-file
intent/completion receipts. Restore with exclusive ordinary copies and fsync,
never hardlinks. Affected105 proof would thereafter mean “verified before
retirement”; full original-path replay requires restoration. No verifier bypass
or new helper is included in this planning note.

## Completed conditional retirement

After106 source sealing,105 stopped cleanly for the necessary application reload.
All four cards passed postflight at20:13:55UTC with no kernel faults. The unchanged
sealed105 final-control verifier reconstructed the entire native/candidate/fast/
control proof twice: once when forming the exact plan and again immediately
before applying it. Root reviewed40 whole-file hash matches and ten retained
native-p1 anchors. All26 earlier restoration anchors remain protected.

Plan: `data/resume-20261007/post105-retirement-plan.json`, SHA-256
`e7bcebdd89002487bc4e9c675a02de1b155fefc034e0b869ae88fa4eaea9ddfa`.
Receipt, durable before-change intent and per-file events share the
`post105-retirement-receipt.json` prefix. All40 removals completed, recovering
2,985,119,744 allocated bytes (2.780109GiB). Previews, metadata, patches, models,
failed outputs and retained references were not removed. Every retired archive
can be rebuilt byte-for-byte as an ordinary copy from its mapped retained source.

Before rerunning105's full raw proof, restore all40 mapped paths with the reviewed
`recovery/20261007-post105-retirement/retire.py restore --plan ABS_PLAN --sha256`
`e7bcebdd89002487bc4e9c675a02de1b155fefc034e0b869ae88fa4eaea9ddfa --receipt ABS_FRESH_RECEIPT`.
The helper requires fresh restoration space above50GiB, all destinations absent,
unchanged retained sources and stopped105. It refuses overwrite/retry; no restore
has been run. Existing closeout bindings describe the pre-retirement artifacts.

Fresh106 admission after sealed construction and cleanup observed55.06739GiB
available, leaving51.06739GiB after its4GiB write allowance. This is recorded in
`sampler106-storage-admission.json`; the retained50GiB reserve still applies.

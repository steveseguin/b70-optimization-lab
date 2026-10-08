# Continuation111 storage review

The proposed **4 GiB runtime allowance plus 384 MiB source-build allowance above a 50 GiB reserve is reasonable for monitored admission**. This is not a hard filesystem quota or a proven peak-write bound. Metadata observed on October7 showed57.944 GiB available on the actual destination filesystem: spending both complete allowances would leave53.569 GiB. Build and launch must still perform their fresh checks.

The frozen111 plan permits eight requests, exactly six full captures and no persisted anchor payloads. Its six-file bound is877,383,216 bytes (0.81713 GiB). An explicit engineering allocation is:

| Item | Allowance |
| --- | ---: |
| Six full captures, including bounded headers |877,383,216 bytes |
| Compiler and other caches |1 GiB |
| Previews |0.5 GiB |
| Logs, requests and proof receipts |0.1875 GiB |
| Unassigned margin inside the4 GiB allowance |1.49537 GiB |

These noncapture allowances are planning amounts, not enforced per-category limits. The IMAGE anchor is2,949,120 bytes in CPU memory, owned through post-request checks; no separate on-disk anchor is required.

The completed110 run is the closest measured storage reference. Its exact run directory contains22,096,963 logical bytes across652 files, primarily logs and receipts. Its inductor-cache directory has zero payload files, and no triton-cache directory exists. Its closeout-listed456 request evidence files total10,944,847 bytes;24 preview files total7,938,986 bytes;50 capture metadata files total73,352 bytes. All were checked by stat against recorded sizes, without reading raw tensor contents. The110 run performed57 requests/50 captures, substantially more than111's eight/six. Its50 raw archives total5,851,616,960 bytes, including its small fill captures; that mixed total must not be treated as a full-capture-size estimate.

The sealed110 launcher redirects Inductor/Triton caches into the run, sets one compiler worker, disables the Comfy compiler and disables Python bytecode writes. These policies explain why a large source-cache write is not expected; they do not bound new native image-encoding kernels or shared driver/SYCL cache writes. This audit did not scan those shared caches. Final empty cache metadata also does not prove that no transient cache writes occurred earlier.

The110 manifest's1,678 inherited regular files occupy110,077,765 logical bytes and113,680,384 allocated file bytes. The successor builder separately computes the complete transformed payload, includes preserved predecessor copies, and refuses if payload plus4 MiB exceeds384 MiB. This review did not run assembly or copy source.

Client and server monitor available space and debit observed positive free-space decreases, with a50 GiB reserve. They reserve no capacity: unrelated writers, bursts between checkpoints, and deletions masking simultaneous allocations remain limitations. Only the six raw capture files have explicit prewrite shape/count/size limits. The evidence supports a bounded trial admission, not a claim that every possible runtime write is capped at4 GiB.

[storage-review.json](storage-review.json) records exact source/closeout/plan hashes, scoped metadata totals and the dated filesystem observation. Cancellation ownership was also rechecked against the recorded integration hash: no new finding. The worker remains owned through cancellation cleanup; admission stays closed until completion and a permanent halt; no thread/process termination is introduced.

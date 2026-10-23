# One-card expert instruction diet: engine screen

CPU preparation resumed October 23 after the qualified micro. Device speed and full-engine exactness are pending. This is the Qwen3.8 Flash-Next 125B-A6B **UD-IQ3_XXS quantized compressed version**, one B70, unchanged `iq3-p49-split32-v1` arithmetic and BF16 KV. The matching record is 36.602512 tok/s (`packet58-onecard-cache23-chain`); this screen cannot establish a new record.

The cache23 engine gains `--expert-gateup production|diet`. Both arms keep max23 capacity (23,049,601,024 bytes), resident lookups, kernel foreground I/O, overlap maintenance, zero-copy misses and the same oracle. The pinned micro header supplies the exact gate/up instruction diet. At each drained view boundary the engine re-prepares commands: 47 IQ2_S halfcache sites switch; layer 2 retains its other-layout kernel. The live boundary check requires exactly 47 selected sites and zero sites of the opposite arm.

Engine SHA256: `537c080767f241653a8ac13c77289cd59e8f7444cbee2a4fcb35586eb1e743d4`. Parent SHA256: `083e3853427041be36faeaf804781e4204b79ed19296648e0aaa7f6c5f1b151a`. `native-dietengine-delta.patch` preserves the exact source change. `restore-inputs.json` binds unchanged objects. All 47 parent SPIR-V images are unchanged; one diet image is added. GNU and Intel CPU twins establish finite-value exactness; NaN-only exceptional fixtures explicitly use is-NaN rather than payload identity. The qualified micro supplies device evidence for the kernel, not this full engine.

## Registered screen

One lane-A row on card 0: K1a, K1b, then one model load with A0/B0/A1/B1/A2 = max23/max23+diet/max23/max23+diet/max23. Each view runs the same 12 varied prompts with 128-token caps, empty prompt/KV/response caches, and exact oracle checks. A0 is excluded only from warm speed/drift comparisons. No separate model smoke or automatic rerun. Expected 700–1200 seconds, watchdog 3600 seconds.

Both diet views must beat each warm control by at least 0.5%, with all 60 requests exact, drift at most 3%, and no kill rule. A record-chain candidate additionally needs 2% over every control (including A0) and at least 37.33456224 tok/s. Kills: inexact output; DRM above 30.5 GB; warm control below 36.0 tok/s; drift above 3%; attributed compute-window saving below 5 microseconds per layer; or changed fills/bytes between arms. The reported saving divides the whole compute-window delta by 48; it is **not direct gate/up kernel timing**. The micro's projected 2.1–2.8% gain is not a measured engine gain.

## Admission and reproduction

The memory plan is unchanged from cache23: device-owned bound 29,828,911,360 bytes, driver allowance 671,088,640, unchanged 30.5 GB DRM guard; host requirement 100,487,123,456 bytes plus the queue's 1 GiB start margin. CPU preparation keeps 27 GB root free; device admission requires 25 GB after reserved writes. No host power, memory, swap, or page-cache settings change.

Run CPU commands with nice 19, CPUs 8–15/24–31 and at most two threads. Existing receipts are in `evidence/`; do not overwrite a completed experiment to reconstruct preparation. `gates.py --check` verifies the required CPU receipts. `package_rows.py` seals only after gates pass; `check_queue_rows.py` runs the temporary queue plan, shared report rehearsal and pin guard; `final_checks.py --ready` writes readiness last. The proposal is `ops/lane-queue/proposed-p58-dietengine-one-card-A.txt`. A READY marker never launches or authorizes a device job.

The resumed preparation corrects stale capacity-screen metadata, relocated private host-admission pins, argument triple unpacking, and test fixtures. Initial failed CPU evidence is retained. The screen is still a 128-token diagnostic; full record-chain gates, determinism and submission eligibility remain separate.

See [boundaries](DO-NOT-REPEAT.md), [retention](RETENTION.md), and [the experiment note](../../../../notes/2026-10-23-packet58-onecard-diet-engine.md).

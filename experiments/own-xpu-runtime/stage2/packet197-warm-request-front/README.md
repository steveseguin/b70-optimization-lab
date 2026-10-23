# Packet197: dynamic warm request front

Status: the single device pilot passed all eight requests and 1,408 output tokens, exact checkpoint state, one model load and clean shutdown. See the [result](RESULT.md) and [independent device audit](evidence/independent-device-result.json). This qualifies the bounded lifecycle, not a full serving interface or a performance record. All three compile-only targets and the actual tiny host lifecycle also pass: [build](evidence/build-compile-only.json), [host](evidence/host-probe.json), [host artifact hashes](evidence/host-probe-artifacts.json). Parent packet181 is unchanged; generated native files and all compiled objects are ignored under `build/`.

The first bridge uses packet181's existing checkpoint engine and 21,552,729,600-byte expert cache. It does not merge the max23/diet treatment from packet196. Initialization and weights remain alive while a bounded stdin loop accepts requests. The inherited reset, token step, checkpoint save and checkpoint restore bodies remain byte-exact. Request boundaries drain compute and quiesce cache publication without clearing resident immutable expert bytes. KV/recurrent/control state is reset before every request and then optionally restored. Cache counters are process totals; expert-cache warmth is not reusable prompt/KV state.

Each request starts with a fresh copy of startup options. Only its input tokens, response cap, checkpoint restore/save IDs and output directory change. Model, tokenizer identity, placement, capacity, arithmetic, context allocation and kernel selection stay fixed. Any malformed frame, failed checkpoint validation, sticky device error or native exception ends intake; existing cooperative teardown owns the drain. There is no request retry, service restart or owner replacement.

Start-mode flags are `--request-front --request-front-max-requests N --request-front-idle-seconds N --request-front-checkpoints ABS_ROOT --request-front-tokenizer-identity ABS_FILE`, alongside the normal admitted engine arguments and `--retain-steps none`. Max requests is explicitly 1..1024, idle timeout 1..3600 seconds, and the existing absolute `--seconds` deadline remains active while waiting for input. The checkpoint root and tokenizer file are fixed startup paths, never client request fields.

Input is six tab-separated fields, terminated by LF:

```text
RUN<TAB>request-id<TAB>max_new<TAB>restore-id-or--<TAB>save-id-or--<TAB>space-separated-token-ids
QUIT
```

The literal `-` means no restore/save. Frames including LF are limited to 262,144 bytes. IDs are unique per process, 1..64 safe ASCII characters, start alphanumeric, and cannot end `.lock`; no slashes or client-chosen paths. Caps are 1..512; token IDs and prompt-plus-cap fit the fixed vocabulary/context. EOF, QUIT, idle expiry, max-request count or process deadline ends the loop. SIGINT/SIGTERM are one-way process stop signals. No mid-request cancellation/reuse is claimed.

Protocol stdout is JSONL only. Existing model diagnostics are redirected to stderr before load. Events are `ready` after initialization, `request-start`, zero-based `token`, `request-complete` referencing `requests/<id>/result.json`, and `stopped` only after successful owner teardown. `request-complete` states `request_quiesced=true, owner_resident=true`; it is not a device-release receipt. Errors emit `fatal` after teardown handling when the transport remains writable. Output backpressure has a five-second deadline; failure ends intake. The client must handle autonomous stopped events at max-request, idle and absolute deadlines.

Checkpoint manifests use `experimental-warm-front`, `v1.2+p197`, packet197 identity and an empty device qualification list. Exact binary SHA validation remains mandatory, so the new binary cannot silently restore old packet181 checkpoints. The inherited legacy metadata reader remains; it does not bypass engine identity.

Source preparation only:

```bash
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet197-warm-request-front/prepare_overlay.py
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 python3 -B -m unittest discover -s experiments/own-xpu-runtime/stage2/packet197-warm-request-front/tests -p test_source_overlay.py
```

`parent-pins.json` binds the input sources and build recipes; `native-request-front.patch` is the exact delta. Parent read-only includes stay in place. The overlay explicitly binds packet181's frozen RoPE fixture and selection file because the adjacent `build/native/rope.bf16` is absent on this host. No fixture/object payload is copied into Git.

The authorized compile-only run compiled the new entry translation unit and relinked exactly 41 pinned device objects and 33 pinned GNU host objects; no parent builder or parent path was changed. Native compilation and the CPU probes are complete. Device arithmetic, dynamic lifecycle and independent readiness review remain separate gates. No generated executable/object payload is tracked.

Per-request front results explicitly report `request_front_scope=experimental-warm-owner-v1` and `session_reuse`. Fresh requests report `cached_tokens=0`; restored requests report the restored processed-prefix position. `reset.json` remains zero because reset precedes restore. Historical non-front result fields remain unchanged.

Reproduction commands for the completed CPU proofs (compilation still requires a separately authorized, quiet host):

```bash
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet197-warm-request-front/build_engine.py --target all --compile-only
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet197-warm-request-front/host_probe.py --run-host-only
```

The first command compiles the standalone C++ protocol probe, GNU host entry with 33 unchanged ancestor objects, and device entry with 41 unchanged packet181 objects. It executes no generated binary; each object is hash checked before and after relinking. The second verifies the compiled host-only marker and hash, executes the actual C++ parser/pipe tests and argv refusals, then uses one warm tiny-geometry CPU owner for fresh A/save, B, restore A/save, append/save, repeat append/save, fresh appended reference/save, uninterrupted A reference and repeated B. It compares tokens and checkpoint blobs, then requires graceful stop. Device qualification is still separate. The CPU harness performs one cooperative incident termination only on a failed host test, never restart/kill/retry. Both commands ran successfully. The initial Python parent-import failure and preliminary host receipt remain under `lineage/`; the corrected harness isolates the parent import namespace.

Compiler dependency closure is now explicit: the parent compiler depfiles identify 95 device and 97 host repository inputs, all hash-pinned before compilation. The new compiler depfile must match that exact inherited closure with the three entry/main/checkpoint files substituted by the overlay and the request-front header added. Missing/unexpected repository inputs refuse before link, and every input is rehashed after compilation and linking. The standalone protocol probe source/header are also pinned and its own depfile must match exactly. Toolchain/system headers are outside repository source pins. Original pre-closure preparation receipts are retained under `lineage/`; the authorized compilation verifies this corrected closure.

The fixed [device worker](device_worker.py) prepares one continuous owner and eight real-model requests: canonical A/save256, fresh B128, resume A128/save, canonical NEW469 append128/save, repeat append128/save, fresh appended reference128/save, uninterrupted A384, repeated B128. It compares A against the fixed parent and CPU oracle128, resumed A against uninterrupted A, append/repeat/fresh tokens and state blobs, and repeated B. It carries full BF16 KV, context4096, the baseline 21.55 GB expert cache, a 98.99 GB host admission and an 800 MB write budget above the 27 GB root floor. The budget exceeds five <80 MB state snapshots at maximum processed position596, eight 8 MB request logs, and a 336 MB margin. The matching p181 S1/S2 manifests are pinned local evidence for that estimate.

The [CPU device gates](device_gates.py) intercept the actual production launch function before exec, pass the full startup shape through the GNU host parser, and check the worker's fixed request/guard behavior. Their [receipt](evidence/device-cpu-gates.json) is CPU readiness only. The future `READY-FOR-DEVICE.json` binds the source closure, binary identities, parent fixtures and command. The window controller alone may run the explicit `--authorized-device-window` path; `device_worker.py --plan` performs read-only CPU verification. Every new request requires guards; journal reads time out after15seconds. Any failure stops intake and permits one cooperative SIGTERM to the retained owner. No retry, process-group signal or forced kill is present. A failed drain keeps crash-closed lease markers for coordinator review.

This is a bounded native pilot, not yet a ctxkeeper/OpenAI serving adapter. RUN fixes its checkpoint save ID before generation; a post-reply `Engine.save` operation is not implemented. Session states and `cached_tokens` are explicit. Warm expert caching does not make reused prompt state eligible for a benchmark headline.

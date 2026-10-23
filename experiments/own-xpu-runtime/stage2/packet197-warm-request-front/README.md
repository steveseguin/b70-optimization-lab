# Packet197: dynamic warm request front

Status: source overlay prepared; eight CPU source/transport-contract tests pass. No C++ compilation, native model/device execution, serving qualification or performance claim yet. The standalone C++ parser/pipe probe is written but has not run. Parent packet181 is unchanged; generated native files and all compiled objects are ignored under `build/`.

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

After separate build authorization, follow packet181 `build_checkpoint.py`: compile only the new ignored `build/native/entry-main.cpp`, then relink the same 41 pinned device objects from packet181's `one-card/lineage/packet181-build.json`, replacing only entry-main.o and output/dependency paths. Use the existing compile-turn lock, nice 19, helper cores, two threads and 27 GB disk floor. A GNU host mock can follow packet181 `checkpoint_probe.py:build_probe`, substituting the overlay entry TU and preserving all ancestor object pins. Do not run those parent builders directly: they mutate parent paths. Native compilation, standalone parser execution, warm multi-request host mocks, fault/drain tests and independent review remain required before any device proposal.

Per-request front results explicitly report `request_front_scope=experimental-warm-owner-v1` and `session_reuse`. Fresh requests report `cached_tokens=0`; restored requests report the restored processed-prefix position. `reset.json` remains zero because reset precedes restore. Historical non-front result fields remain unchanged.

Prepared next commands, ONLY after coordinator build authorization and timing/restoration completion:

```bash
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet197-warm-request-front/build_engine.py --target all --compile-only
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet197-warm-request-front/host_probe.py --run-host-only
```

The first command compiles the standalone C++ protocol probe, GNU host entry with 33 unchanged ancestor objects, and device entry with 41 unchanged packet181 objects. It executes no generated binary; each object is hash checked before and after relinking. The second verifies the compiled host-only marker and hash, executes the actual C++ parser/pipe tests and argv refusals, then uses one warm tiny-geometry CPU owner for fresh A/save, B, restore A/save, append/save, repeat append/save, fresh appended reference/save, uninterrupted A reference and repeated B. It compares tokens and checkpoint blobs, then requires graceful stop. Device qualification is still separate. The future CPU harness performs one cooperative incident termination only on a failed host test, never restart/kill/retry. Both commands are prepared, not run.

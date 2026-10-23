# Packet198: postreply SAVE and RELEASE

Status: all three compile-only targets pass, the actual C++ parser/state probe passes, and the tiny-host lifecycle passes eight requests/eight dispositions with exact tokens and state. Five actual native refusal fixtures and pending QUIT also pass. [Build receipt](evidence/build-compile-only.json), [host proof](evidence/host-probe.json), and [complete retained host hashes](evidence/host-probe-artifacts.json) bind the results. Seven CPU source/dependency tests pass. This packet is a separate thin overlay on frozen packet197; p198 device arithmetic, serving behavior and performance remain unqualified.

The delta adds protocol `ownrt.request-front.v2`. One RUN leaves a quiescent pending descriptor containing the exact original prompt, processed history, pending token, request identity and restore-parent lineage. A subsequent SAVE chooses a new checkpoint ID after seeing the reply. SAVE validates the supplied full visible token sequence, calls the existing checkpoint writer, requires quiescence and emits a hash-bound receipt. RELEASE discards only that pending descriptor. A second RUN cannot overwrite undisposed state.

The reset, token step, checkpoint save, checkpoint restore and existing host inspect/delete bodies stay byte-exact. Full BF16 KV, p181 arithmetic, context allocation and the 21,552,729,600-byte expert cache are unchanged. A front-mode restore reserves the existing writer's required free position even though RUN no longer chooses an immediate save. Checkpoints carry the explicit experimental label `experimental-postreply-front`, contract `v1.2+p198` and the new binary's exact identity. Earlier checkpoints do not silently become compatible or qualified.

Frames use tabs and LF, safe IDs of 1–64 ASCII characters, decimal token IDs and a 262144-byte limit:

```text
RUN      request-id  max-new     restore-id-or--  -              input-token-ids
SAVE     operation-id request-id checkpoint-id                  full-visible-token-ids
RELEASE  operation-id request-id
QUIT
```

RUN has the same six fields as v1, but its save field must be `-`. There is exactly one successful SAVE or RELEASE per RUN, at most `max_requests` control operations, unique request IDs and unique operation IDs. Existing idle and absolute deadlines remain active while waiting for disposition. The final permitted RUN stays alive until SAVE/RELEASE, QUIT/EOF, signal or deadline; only then does it drain. The terminal event reports completed request/control counts and whether an unsaved descriptor was discarded. Any malformed frame or native failure stops intake; no retries, forced kills or owner replacement are added.

SAVE events bind `operation_id`, `request_id`, the exact checkpoint ID, manifest SHA256, startup-root-relative checkpoint path and `operations/<operation-id>/save.json`. The checkpoint writer retains its native payload hashes, locks, no-overwrite rule and manifest-last visibility. INSPECT/DELETE protocol operations, policy projections, ctxkeeper parking and OpenAI serving are deferred. Existing external host-only checkpoint commands remain available in the underlying source; the new transport does not call them.

Inputs are bound by `parent-pins.json`, including the frozen p197 generated sources, parent compiler dependencies, compile recipe, new header/probe and v2 client. `prepare_overlay.py` also checks the four parent generated files against p197's READY receipt, then writes ignored `build/native` sources and the tracked `native-postreply.patch`. No parent sources, object files or binaries are modified. `build_engine.py` loads a private instance of the pinned p197 compile recipe with only its output packet rebound: the same 41 p181 device objects and 33 GNU host objects are retained. Compiler depfiles must match the exact admitted inherited closure plus the new entry sources/header.

Prepared CPU commands (the first two do not compile or run a native executable):

```bash
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet198-postreply-checkpoint/prepare_overlay.py
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 python3 -B -m unittest discover -s experiments/own-xpu-runtime/stage2/packet198-postreply-checkpoint/tests -p test_source_overlay.py -v
```

The coordinator ran the following commands after separate authorization and a quiet compile turn (future repetition still requires an authorized turn):

```bash
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet198-postreply-checkpoint/build_engine.py --target all --compile-only
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet198-postreply-checkpoint/host_probe.py --run-host-only
```

The completed host probe used one tiny-geometry owner for A/save, B/release, A resume/save, append/save, repeat/save, fresh appended reference/save, uninterrupted A/release and repeated B/final save. It compares tokens and state with packet197's retained immediate-save host evidence, tests the actual C++ parser/state machine, then runs separate host-only negative fixtures for a wrong full prefix, a new RUN before disposition, a stale request, an existing checkpoint ID and a duplicate operation. A final pending QUIT fixture checks explicit discard and clean shutdown. The host receipt records 44 generated tokens, six SAVE and two RELEASE operations; the final operation is SAVE, proving disposition can complete after the last RUN. These CPU fixtures do not establish real-model or device qualification. A separately prepared real-device worker uses five SAVE and three RELEASE operations, including final RELEASE, and remains gated by its own readiness/window receipt.

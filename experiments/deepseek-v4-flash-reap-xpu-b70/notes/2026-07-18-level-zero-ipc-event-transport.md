# Level Zero IPC Event Transport for the TP4 Markov Sampler

Date: **2026-07-18**

Status: **exact primitive passed; sampler integration endpoint rejected**

## Outcome

The four-B70 path now has a working device-to-device readiness primitive that
does not route each sequential Markov winner exchange through oneCCL or a host
barrier. XPU-kernel commit `88db339` adds a SYCL/Level Zero bridge that:

1. writes each rank's FP32 `(score, token)` pair into its persistent IPC
   workspace;
2. makes the SYCL write event a dependency of a native immediate command list;
3. signals one local IPC event and waits for the three peer events;
4. imports the native completion event back into SYCL; and
5. selects the exact maximum score with lowest-token tie breaking on device.

The exact four-rank gate uses 12 warmups and 80 measured cycles with seven
sequential decisions per cycle. Winners change on every step and every
eleventh cycle forces a tie. All four ranks pass with zero mismatches. The
slowest-rank median falls from 1,484.5065 us for seven tiny XCCL pair gathers
to **184.7965 us** for the event path.

## What was actually fixed

The first production bridge build still used a device-restricted IPC event
pool. The standalone probe had already established that peer B70s can open the
pool only when it is created context-wide. Correcting `zeEventPoolCreate` to
use the context-wide device set repaired the peer-open contract. Cleanup also
accepts the B70 driver's `ZE_RESULT_ERROR_UNSUPPORTED_FEATURE` response from
`zeEventPoolPutIpcHandle`, matching the working oneCCL/standalone lifecycle.

The opaque 64-byte event-pool handle must be retained and only its embedded FD
replaced with the SCM_RIGHTS duplicate. A zeroed handle plus FD is invalid on
this runtime.

## Forward-progress proof and reuse limit

The standalone native test records 80 one-shot event epochs into a cached
command list. With no artificial skew, all epochs complete in about 5.35-5.36
ms. Delaying rank 3 by 200 ms delays ranks 0-2 to 205.89-205.91 ms, proving
that the peer device wait is real rather than a false-ready condition. All 320
events queried on every rank are signaled.

A separate two-slot reset/reuse protocol hung with one rank failing to reach
teardown. That result is preserved as a rejection. The supported design is
therefore one event per decision for the bounded current request, followed by
pool retirement/recreation between requests. No event is reset or reused.

## Honest performance interpretation

The 1.299710 ms pair-microgate delta is not a model-level saving. The current
DSpark implementation gathers the much larger BF16 bias shard, which oneCCL
routes more efficiently; its measured seven-step median is 371.347 us. Against
that production transport, the event pair path has only a **186.5505 us/cycle
transport ceiling** before accounting for local winner selection.

The importance of this pass is architectural: it enables W2 to stay sharded
and lets a fixed M7 sampler transaction exchange only the final pair without
seven Python/c10d collective submissions. It becomes valuable when bundled
with local-logit reduction, the seven W2 projections, Markov state updates,
and next-W1 production. It is not independently LocalMaxxing-eligible.

## Evidence

- exact reusable gate: `../scripts/bench-tp4-ipc-event-max-token.py`;
- standalone Level Zero gate: `../scripts/bench-tp4-level-zero-ipc-events.py`;
- native cached-command-list probe:
  `/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/tests/mhc/tp4_ipc_event_probe.py`;
- exact raw result:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp4-ipc-event-max-token-20260718Tresume/summary.json`;
- no-delay and delayed-rank proof:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp4-level-zero-ipc-event-probe-20260718T2020Z/`.

## Next gate

Add default-off request-lifetime event-pool brokering to the DSpark worker
startup and replace the seven full-bias gathers with local winner reduction
plus exact event-pair exchange. Then capture the entire fixed M7 transaction
and compare it against the current sampler with ordered exact canaries. Only a
strict endpoint record is eligible for LocalMaxxing.

## Integration closure

The requested bundle was subsequently implemented, including local base
logits, exact BF16 Xe2 DPAS W2, direct W1 lookup, one native M7 call, and final
draft-buffer writes. The exact component saved 0.994 ms, but the strict
endpoint reached only 67.227723 tok/s versus the 80.820052 record. See
`2026-07-18-dspark-m7-ipc-dpas-bundle-closure.md`. This supersedes the “next
gate” above: ordinary one-shot event integration is rejected unless a reusable
fixed-address submission architecture removes the eager synchronization cost.

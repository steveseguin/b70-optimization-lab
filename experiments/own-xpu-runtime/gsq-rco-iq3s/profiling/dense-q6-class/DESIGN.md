# Current dense-Q6 class diagnostic — design only

No new native build is needed. The compiled candidate accepts `--timing token|launch|class|attribution`; class mode enables actual event profiling and per-class accumulation. Attribution is a separate mode and records only routed-family labels at fixtures9..16, not all classes or all phases. Keep this first diagnostic in class mode.

After the candidate's full actual audit passes, privately adapt the qualified `profiling/current-combined` wrapper to the new candidate adapter, current native receipt/binary and actual passed review. Retain every selected optimization flag, model/placement/draft identity, rank split and device census. Change only native timing argument token→class. Rank1 queue profiling changes by this flag and must remain disclosed; no performance claim for this diagnostic.

One persistent pair, one excluded disjoint target-only warmup8 followed by original prompt00 target-only128, full RESET, first warmup redump verification, explicit final DUMP repeat, normal FINISH and independent closed logical-map readback. Draft remains allocated but not requested, preserving the target configuration. Exactly3 capture groups/6 target bundles; raw forecast694,327,500B plus128MiB metadata and unchanged root/external floors. Original prompt00 tokens/full target state must equal the immutable baseline. Both actual physical owner contacts and normal fault/vision/queue/retention safeguards remain mandatory. Do not create a plan or launch until root explicitly chooses this diagnostic.

## What can be separated without a rebuild

- Per-class device milliseconds in `class-times.json` are **whole request**. Class counters reset on RESET; warmup output remains separate. No event timestamps or position keys accompany the class bins, so class-by-prefill/decode attribution cannot be reconstructed from them.
- The same class-mode request retains `rank_trace` entries with op, rank, absolute position, fixture and `gpu_ms`. `rank.hpp::half` returns the delta of accumulated gemv+nongemv event time for that half. Thus per-rank **total profiled device duration** can be partitioned by target position, after filtering actual half operations and checking complete unique positions/no speculation.
- For prompt length87 and128 outputs, each rank has214 target halves at positions0..213. The controller uses `fixture=max(0,p-87+2)`: positions0..85 are fixture0; position86/fixture1 produces the first output; positions87..213 are the127 later generated-token intervals. Report three explicit bins: prompt positions0..85, final prompt/first output position86, and later decode positions87..213. A TTFT-oriented subtotal combines the first two. Do not call fixture>0 entirely decode.
- Independently reconcile summed half event duration with whole-request class totals and retain any residual; do not force equality or subtract host timing from device timing. `half_completion_ms`/`busy_ms` and `enqueue_family_ms` are host measurements; enqueue families can be grouped by those same positions but are not kernel-class device times. Never compare device clock timestamps across ranks.
- Existing attribution mode could subsequently identify routed format costs only at fixtures9..16 = positions94..101 (early generated steps). It cannot supply broad prefill class attribution, and no need for it is established before class results.

Minimal future edits, only if selected: new private profile/once adaptation, a small summary routine that validates trace position coverage and computes these totals, fixed source pins and a few metadata-only tests of phase boundaries/missing or duplicate positions. Reuse existing class/closed bundle parsers and actual baseline oracle. No native mutation, additional warmup prompts, fresh-server chain or new tracing framework.

## Source bindings inspected

- `experiments/own-xpu-runtime/gsq-rco-iq3s/dense-q6-p33/build/source/main.cpp` — `c35f1271033658e6384bf6d8cc1fab62014c2fe5d942f21e238abd2995f2e565`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/state-bundle/build/source/rank.hpp` — `3048c31d11102e3692ac9f5c3276ec342d8b9c2cf5891ec657ae371e4cb9ae71`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/request_reset.hpp` — `0e718893e0bae5434b37fc9d329c9480d7ea5fb823cb9511b4a4e73ea1d79ab8`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/native_controller.hpp` — `cbc2c25f2e64a3ff77e2ce4e2d6cfeaf94217a79bb098853588abf66d4cde4c9`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/p65_attribution.hpp` — `d87c7d8343b336f5b9dedfd3ce7bc8af3e06a80351fb3590082c7742acaa8e1a`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/profiling/current-combined/profile.py` — `fb68fc65a9f565f025f46e7fafe585759e88dcf2ffced3cb384f49742e9a1a13`
- `experiments/own-xpu-runtime/gsq-rco-iq3s/profiling/current-attribution/profile.py` — `dc2cce7925aba377e00d50b20db8470a5943a2242dd2f13fdbc939194e6e7cd5`

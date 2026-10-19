# Packet58as result: bounded spin wait is +8.6% on the one-card record line (60/60 exact); record chain prepared

Card 0, whole host, boot 2cba7160. The one-load v5 `packet58as-v5-A` ran 08:37–08:51 UTC with every Codex unit frozen. GPU fault count stayed 2.

The line is packet58aj (the 31.966820 tok/s record line). The only change is the native `wait()` policy: a 1 ms `sleep_for` poll versus a bounded spin. The spin is a reimplementation of the two-card packet56w/56x semantics: a per-invocation spin budget with periodic yields, every wait keeps its deadline, async errors are checked on every iteration, and `wait_and_throw` runs on completion. Arithmetic, selection and kernels are identical. No host setting, governor or power state changed.

| View | Wait policy | Class-balanced tok/s | Owner-thread CPU |
| --- | --- | ---: | ---: |
| A0 | poll | 31.901 (warm-up, excluded) | 42.7% |
| B0 | **spin** | **34.577** | 33.0% |
| A1 | poll | 31.838 | 25.1% |
| B1 | **spin** | **34.568** | 32.9% |
| A2 | poll | 31.807 | 24.5% |

- All 60 prompt checks are exact vs `iq3-p49-split32-v1`. Warm-control drift is 0.096%.
- Spin beats every warm control by **+8.58% to +8.71%**, against a gate of +0.5%.

**Why it is bigger than packet58aq predicted:**
- packet58aq priced only the publication drain (1.108 ms/token, about +3.6%).
- The same 1 ms poll sits under every hot-path `wait()` on the one-card engine. Each wait that found its event incomplete slept a full scheduler quantum.
- The two-card line removed millisecond polling long ago (packet56w/56x DO-NOT-REPEAT: "Do not reintroduce millisecond polling"), but the one-card port inherited the older device layer.

**Trade-off:** the owner thread uses about 33% of a core instead of about 25% (the process is whole-host).

**Next:**
- Codex packet58asc is preparing the record-chain handoff (`ops/packet58as-orchestration`). The coordinator's `fn-run/chain-58as.sh` launches the quiet chain (Codex frozen from before K1a) once `onecard-chain.sh --check` passes. A submission requires WS128 > 31.966820.
- packet58ar (structural drain removal against the poll parent) was stopped unbuilt: spin removes the sleep that dominated the drain. Its partial tree is kept untracked at `stage2/packet58ar-ordered-publication/` for a possible later "drain removal on top of spin" job, if the chain's residual justifies one.

Evidence: `experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/screen/evidence/card0-58as-v5-a/resident/WSCREEN/summary.json`.

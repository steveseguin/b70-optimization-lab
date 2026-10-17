# Own runtime packet 47: QSA decode attention on card 0 (2026-10-17) — split32 is 5.3-8.2x

Windows `p47-b` on boot `2cba7160`, card 0 (PCI `0000:23:00.0`). The fault review covered the 2 known lines from 01:09; no new fault lines appeared.

Window `p47-a-e1` refused before any kernel ran. Its identity check compared against DRM `card0`, which is `0000:43:00.0` on this host. That check was fixed in `3ee379260`.

| Window | Result |
|---|---|
| E1, E2 (fresh processes) | **passed**: 316/316 checks each. Both variants match their CPU references (ordered: the existing oracle; split32: oracle `iq3-p47-qsa-split32-v1`) at contexts 1K/2K/4K/8K/32K (+1027/2051/4099), M=1 and M=2 |
| T1, T2 | passed: 2,100 paired timing checks each |

`qsa.attention` GPU µs (medians; owners 1 and 2 agree within 0.5%):

| Shape | Current | Ordered | **Split32** | Split32 speedup |
|---|---:|---:|---:|---:|
| 1K, M=1 | 1194.6 | 2227.1 | **225.6** | 5.30x |
| 2K, M=1 | 2379.4 | 3937.8 | **417.8** | 5.69x |
| 4K, M=1 | 2376.7 | 3404.7 | **416.0** | 5.71x |
| 8K, M=1 | 2343.5 | 3386.5 | **412.4** | 5.69x |
| 32K, M=1 | 2680.9 | 3516.8 | **451.6** | 5.98x |
| 1K, M=2 | 2366.7 | 3445.0 | **311.6** | 7.62x |
| 4K, M=2 | 4750.8 | 5335.5 | **587.7** | 8.08x |
| 32K, M=2 | 5205.5 | 5549.6 | **644.3** | 8.18x |

- `qsa.select` is unchanged (about 54 µs at 1K).
- `qsa.qgate` is about 76-81 µs at M=1, with split32's slightly higher.

**Verdict.**

- **Split32 is the integration candidate**: it clears the 3x bar at every shape.
- The order-preserving variant is slower (0.54-0.69x) and is closed.
- Split32 changes the reduction tree, so the engine needs the new oracle identity and full-suite requalification against a matching CPU reference. That follows the IQ3 lossless-against-its-own-reference rule and the October 11 rebase precedent.

**Expected effect.**

- At 4K context, about 2.0 ms saved per QSA layer at M=1 (12 QSA layers), and more at M=2.
- On the 128-token realistic suite the prompts are 60-90 tokens, so the gain is smaller: Codex estimated it before measurement.
- Long-context decode benefits most.

Evidence: `experiments/own-xpu-runtime/stage2/packet47-qsa-attn/evidence/p47-b-{e1,e2,t1,t2}/`, `p47-b-summary.json`.

# Device requalification — 2026-10-20 evening window

Commit `72bddd50d` (evidence), whole-host reservation, sealed admission satisfied
(35G free disk, 112G free RAM, fresh fault review `requal-20261020-fault`).

Four fresh model loads against the **historical sealed packet165 binary**
(`build/device/own-rt-iq3`, sha256 `cb2cef71…`, matches the packet identity record):

| Profile | Load A | Load B | Published loads | Result |
|---|---|---|---|---|
| TP2 full512 (two cards) | 58.724 | 58.676 | 58.632 / 58.557 | passed |
| TP1 full512 (one card) | 31.766 | 31.774 | 31.782 / 31.510 | passed |

Exactness (all four loads, both profiles):
- 13 requests × 6495 output tokens byte-identical across A/B loads.
- Suite and prefill token arrays byte-identical to the **original sealed
  qualification** (`device-warm512-B-a` embedded bracket requests).
- `all_available_oracle_tokens_exact: true` on both requal brackets; quality-gate
  fields match the originals field-for-field.

Scope notes:
- This re-affirms the published recipes' measurements on this boot; it does not
  transfer to the portable rebuilt binaries (`c2573efd…`, CPU compile validated
  only). The rebuilt binaries' device gate requires a **new sealed packet** —
  `build/device/own-rt-iq3` is seal-pinned in both card seals, so no in-place
  substitution is possible. That is the next campaign item.
- Evidence dirs (raw): `packet165-warm-prefill/{two,one}-card/evidence/requal-*-20261020`.

Endpoint restoration after the window: all three daily units recreated from
`local-daily-restore-plan.json` (transient units, Restart=no etc. as documented).
FP8 state dirs are single-use ("File exists" on reuse) — relaunched with
`…-20261020-restore2` state dirs. Vision cwd reused (llama-server has no
single-use constraint). 18130 ready ~225s, 18131 ~165s, 18100 ~45s; all serving.

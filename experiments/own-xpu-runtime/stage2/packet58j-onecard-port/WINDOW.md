# Proposed card-0 windows — coordinator only

Plan only in packet58j preparation. Run after the two-card record chain drains,
in a whole-host gap. Every window, including K1, holds lane B through the copied
chain-lanes-v1 protocol and checks all cards for foreign Xe clients. No lane-B
TP2 screen may overlap the 85.6 GB model-window admission. WS128 keeps the
118.3 GB timing admission. The 8 GiB reserve, memory-block fence, card-0 BDF
mask, fault boundary, drain protocol and 90-second gaps remain enforced.
No live queue, lease or service is created by `--plan`.

From the repository root, the coordinator supplies its already reviewed UTC
fault boundary and reviewed library path as `REVIEWED_UTC` and `XPU_LIBS`.
Neither value is inferred or renewed by the launcher.

```bash
P=experiments/own-xpu-runtime/stage2/packet58j-onecard-port
bash "$P/launch-proposed.sh" bracket --plan "$REVIEWED_UTC" "$XPU_LIBS" < /dev/null
bash "$P/launch-proposed.sh" record --plan "$REVIEWED_UTC" "$XPU_LIBS" < /dev/null
```

The later device commands, not executed during preparation, are:

```bash
bash "$P/launch-proposed.sh" bracket --launch "$REVIEWED_UTC" "$XPU_LIBS" < /dev/null
# Only after the complete bracket passes:
bash "$P/launch-proposed.sh" record --launch "$REVIEWED_UTC" "$XPU_LIBS" < /dev/null
```

These start `packet58-j-bracket-a.service` and `packet58-j-record-a.service`.
Both inherit nice 0 and lane-A timing cores. K1/KD child windows lower priority
and use helper cores; W children retain the original timing placement. Stop
requests forward one cooperative SIGTERM. No hard kill, retry, restart or
service restoration is configured.

The bracket writes only under `evidence/card0-58j-bracket-a/`:

1. `production-before`: original 58g kernel choices.
2. `port`: down-tile16 + route-fast + rec-both-plus.
3. `production-after`: original 58g kernel choices again.

Each arm is a complete fresh seven-window queue:
`K1a / K1b / KD / W2m / WS / WS128x / WS128`.
No K1 seal, cache, model process or response crosses an arm. The unchanged
p49 oracle checks all twelve prompts and retained layer bytes. Every request
has zero reused prompt/KV/response tokens; immutable weight-cache persistence
within one process remains exactly the 58g policy. K1 selects zero-copy versus
copy-on-miss using the actual chosen DOWN layout.

The port must beat both controls and the saved **24.338653323339745 tok/s**
one-card record. Controls must differ by at most 3%. All arms and the fresh
confirmation must use the same K1-selected miss path. The metric is the median
of six prompt-class medians over 99 inter-token intervals. A loss, failed
exactness gate or failed drain stops the campaign; no automatic alternative
view or retry is chosen.

The conditional fresh chain writes under
`evidence/card0-58j-record-a/record-port/`. Its WS128 is the preregistered
submission measurement; the earlier candidate WS128 is an independent fresh
confirmation, never a selectable higher headline. The fresh run must also
beat both bracket controls and the saved record. A failed confirmation is
recorded and does not trigger another attempt.

The inherited suite uses a 128-token cap, so its strict 512-token gate stays
false. No external submission is performed by these commands. A later submission
must preserve that scope, carry its own exact quality/record evidence and any
required applicable scope authorization; the older record's authorization is
not silently transferred.

For any individual view, use the copied packet58 queue directly with `--view`
and a new output root. The sealed views are in `views.json`. The proposed
bracket itself always uses `production / port / production`.

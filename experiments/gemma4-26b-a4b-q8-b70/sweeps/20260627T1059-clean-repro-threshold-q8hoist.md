# 2026-06-27 Clean Repro, Threshold, and Q8 Hoist Screens

Goal: continue Gemma 4 26B A4B Q8 one-B70 optimization from a clean
reconstructed llama.cpp source tree and avoid confusing benchmark identities.

Current promoted fresh-response record for comparison:

- `data/gemma4-q8-gpu0-rmsreuse-ub768-nmin3-pmin010-fullrepeat-20260627T070421Z/`
- row0 fresh after TTFT: `104.30919255569083 tok/s`
- support mean: `103.93445004566178 tok/s`
- canary: `6144/6144`
- LocalMaxxing: `cmqw1tgzx0366qr01g4lkv7f1`

## Benchmark identity correction

An initial clean-source rebuild smoke accidentally used the wrapper default
`BENCH_PROMPT_MODE=long`, which produces an actual `75`-token prompt. It
measured only `47.70728573595139 tok/s`, but that was not comparable to the
record lane.

The comparable lane is:

- `BENCH_PROMPT_MODE=filled-long`
- `PROMPT_TOKENS=512`
- actual prompt tokens: `588`
- output tokens: `512`
- row0 only is the fresh-response headline; later repeated-prompt rows are
  support only, even when `cached_tokens=0`.

The corrected clean-rebuild control restored the expected lane:

| Run | Prompt tokens | Canary | Row0 fresh tok/s | Support mean | Decision |
|---|---:|---:|---:|---:|---|
| `data/gemma4-q8-gpu1-cleanrepro-rmsreuse-ub768-nmin3-pmin010-screen-20260627T105908Z/` | `75` | `64/64` | `47.70728573595139` | `45.134280892081634` | invalid comparison; wrong prompt mode |
| `data/gemma4-q8-gpu1-cleanrepro-rmsreuse-ub768-nmin3-pmin010-filledlong-screen-20260627T110211Z/` | `588` | `64/64` | `102.2521600027975` | `102.3745597619006` | valid control; below record |

## Q8 ncols hoist screen

The Q8 ncols-hoist build did not show a material gain when tested under the
correct filled-long identity.

| Run | Gate | Canary | Row0 fresh tok/s | Support mean | Decision |
|---|---|---:|---:|---:|---|
| `data/gemma4-q8-gpu2-q8hoistbinary-gateoff-filledlong-screen-20260627T110354Z/` | off | `64/64` | `104.01802608834869` | `103.22456564964622` | valid control; below record |
| `data/gemma4-q8-gpu3-q8ncols-hoist-filledlong-screen-20260627T110354Z/` | on | `64/64` | `104.1631964042177` | `103.13102921269883` | neutral; do not promote |

Conclusion: do not promote the Q8 ncols-hoist patch. If revisited, it needs a
larger structural change to the Q8 MMVQ body rather than this hoist alone.

## MTP threshold screens

All runs below used the clean reconstructed `c926ad098` source stack, Q8 target,
Q4_0 MTP draft, `BENCH_PROMPT_MODE=filled-long`, `BATCH_SIZE=1024`,
`UBATCH_SIZE=768`, `THREADS=8`, `POLL=100`, f16 KV, `--ctx-checkpoints 0`,
`MTP_N_MAX=7`, backend draft sampling off, and the current record source flags
including `LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1`.

| Run | Thresholds | Canary | Row0 fresh tok/s | Support mean | Decision |
|---|---|---:|---:|---:|---|
| `data/gemma4-q8-gpu0-cleanrepro-sweep-nmin3-pmin008-filledlong-20260627T110534Z/` | `n_min=3`, `p_min=0.08` | `64/64` | `102.3070397714914` | `103.1247257327032` | valid loss |
| `data/gemma4-q8-gpu1-cleanrepro-sweep-nmin3-pmin005-filledlong-20260627T110534Z/` | `n_min=3`, `p_min=0.05` | `64/64` | `102.45538754662321` | `103.38591938248454` | valid loss |
| `data/gemma4-q8-gpu2-cleanrepro-sweep-nmin2-pmin010-filledlong-20260627T110534Z/` | `n_min=2`, `p_min=0.10` | `64/64` | `103.896735921303` | `103.89826372212935` | valid loss |
| `data/gemma4-q8-gpu3-cleanrepro-sweep-nmin2-pmin005-filledlong-20260627T110534Z/` | `n_min=2`, `p_min=0.05` | `64/64` | `104.45384848910177` | `103.34199756491268` | screen-only possible win; required full run |
| `data/gemma4-q8-gpu1-cleanrepro-sweep-nmin2-pmin003-filledlong-20260627T110719Z/` | `n_min=2`, `p_min=0.03` | `64/64` | `103.8234720039123` | `103.80544126341594` | valid loss |
| `data/gemma4-q8-gpu2-cleanrepro-sweep-nmin2-pmin002-filledlong-20260627T110720Z/` | `n_min=2`, `p_min=0.02` | `64/64` | `104.28243601872896` | `103.2303243569199` | valid screen; below record |
| `data/gemma4-q8-gpu3-cleanrepro-sweep-nmin1-pmin005-filledlong-20260627T110720Z/` | `n_min=1`, `p_min=0.05` | `64/64` | `104.23404405601694` | `104.17690857001215` | valid screen; below record |

Full confirmation of the only promising screen:

| Run | Thresholds | Canary | Row0 fresh tok/s | Support mean | Decision |
|---|---|---:|---:|---:|---|
| `data/gemma4-q8-gpu0-cleanrepro-nmin2-pmin005-filledlong-full-20260627T110719Z/` | `n_min=2`, `p_min=0.05` | `384/384` | `104.20012931972596` | `103.76574354452279` | valid full loss; do not submit |

The `n_min=2`, `p_min=0.05` full run was comparable and fresh-valid
(`cached_tokens=0` on all rows), but it did not beat the current
`104.30919255569083 tok/s` LocalMaxxing record. No LocalMaxxing submission.

## Current conclusion

The clean reconstructed source stack is usable. The apparent `47 tok/s`
regression was a prompt-mode mistake, not a source rebuild regression. The
threshold neighborhood remains mostly runtime noise around the `104 tok/s`
plateau; `n_min=2,p_min=0.05` did not confirm as a record. Q8 ncols hoist is
neutral.

## Follow-up: UBATCH / CTX / runtime / pressure screens

The next batch tested the easy shape and runtime knobs around the record
identity (`n_min=3,p_min=0.10`, Q8 target, Q4_0 MTP draft,
`BENCH_PROMPT_MODE=filled-long`, actual prompt `588`, output `512`). These
runs confirmed that this lane is dominated by screen variance around the
`104 tok/s` plateau.

### UBATCH sweep

| Run | UBATCH | Canary | Row0 fresh tok/s | Support mean | Decision |
|---|---:|---:|---:|---:|---|
| `data/gemma4-q8-gpu0-cleanrepro-ub640-nmin3-pmin010-filledlong-screen-20260627T111202Z/` | `640` | `64/64` | `102.190680` | `103.275393` | valid loss |
| `data/gemma4-q8-gpu1-cleanrepro-ub704-nmin3-pmin010-filledlong-screen-20260627T111203Z/` | `704` | `64/64` | `104.778837` | `103.026600` | screen-only possible win; required full run |
| `data/gemma4-q8-gpu2-cleanrepro-ub832-nmin3-pmin010-filledlong-screen-20260627T111203Z/` | `832` | `64/64` | `102.191189` | `102.985872` | valid loss |
| `data/gemma4-q8-gpu3-cleanrepro-ub896-nmin3-pmin010-filledlong-screen-20260627T111203Z/` | `896` | `64/64` | `104.161300` | `103.688067` | valid screen; below record |

Full confirmation of the only UBATCH screen above record:

| Run | UBATCH | Canary | Row0 fresh tok/s | Support mean | Decision |
|---|---:|---:|---:|---:|---|
| `data/gemma4-q8-gpu1-cleanrepro-ub704-nmin3-pmin010-filledlong-full-20260627T111355Z/` | `704` | `384/384` | `104.191834` | `103.590469` | valid full loss; do not submit |

### Thread / poll pressure screens

| Run | Change | Canary | Row0 fresh tok/s | Support mean | Decision |
|---|---|---:|---:|---:|---|
| `data/gemma4-q8-gpu0-cleanrepro-ub704-thr6-poll100-filledlong-screen-20260627T111443Z/` | `THREADS=6` | `64/64` | `102.411385` | `102.410763` | valid loss |
| `data/gemma4-q8-gpu2-cleanrepro-ub704-thr10-poll100-filledlong-screen-20260627T111444Z/` | `THREADS=10` | `64/64` | `104.082856` | `104.384820` | row0 below record; support mean only |
| `data/gemma4-q8-gpu3-cleanrepro-ub704-thr8-poll50-filledlong-screen-20260627T111444Z/` | `POLL=50` | `64/64` | `102.209148` | `102.760882` | valid loss |
| `data/gemma4-q8-gpu1-cleanrepro-pressure-control-dt32-filledlong-screen-20260627T112322Z/` | control, draft threads `32/32` | `64/64` | `102.046305` | `102.886781` | valid loss |
| `data/gemma4-q8-gpu2-cleanrepro-pressure-thr12-dt32-filledlong-screen-20260627T112322Z/` | `THREADS=12`, draft threads `32/32` | `64/64` | `104.322118` | `104.251808` | tiny screen above record, not enough to promote |
| `data/gemma4-q8-gpu3-cleanrepro-pressure-thr8-dt24dtb32-filledlong-screen-20260627T112322Z/` | draft threads `24/32` | `64/64` | `104.319003` | `104.668242` | tiny screen above record, not enough to promote |

The pressure screens are not material and are within the observed row0
variance. They do not justify a LocalMaxxing submission or another full run
unless paired with a source-level mechanism.

### Unique-prompt fresh checks

The unique-prompt lane is stricter because all rows are fresh-eligible when
prompt hashes are distinct and `cached_tokens=0`. It remains below the repeated
row0 record, so the repeated-prompt support means are not hiding a better
fresh-response headline.

| Run | Shape | Canary | Row0 tok/s | Fresh-eligible mean | Decision |
|---|---|---:|---:|---:|---|
| `data/gemma4-q8-gpu0-cleanrepro-unique-control-ub768-nmin3-pmin010-20260627T111705Z/` | record shape | `64/64` | `100.826366` | `100.926397` | valid loss |
| `data/gemma4-q8-gpu1-cleanrepro-unique-ub704-nmin3-pmin010-20260627T111834Z/` | `UBATCH=704` | `64/64` | `99.809206` | `100.434196` | valid loss |
| `data/gemma4-q8-gpu2-cleanrepro-unique-b1536ub768-nmin3-pmin010-20260627T111705Z/` | `BATCH=1536`, `UBATCH=768` | `64/64` | `101.146655` | `101.476496` | valid loss |
| `data/gemma4-q8-gpu3-cleanrepro-unique-ub896-nmin3-pmin010-20260627T111705Z/` | `UBATCH=896` | `64/64` | `101.099536` | `101.536356` | valid loss |

### CTX and runtime toggles

| Run | Change | Canary | Row0 fresh tok/s | Support mean | Decision |
|---|---|---:|---:|---:|---|
| `data/gemma4-q8-gpu0-cleanrepro-ctx4096-ub768-nmin3-pmin010-filledlong-screen-20260627T111913Z/` | `CTX=4096` | `64/64` | `102.329562` | `102.871497` | valid loss |
| `data/gemma4-q8-gpu2-cleanrepro-ctx6144-ub768-nmin3-pmin010-filledlong-screen-20260627T111913Z/` | `CTX=6144` | `64/64` | `104.257106` | `104.267266` | close screen; below record |
| `data/gemma4-q8-gpu3-cleanrepro-ctx12288-ub768-nmin3-pmin010-filledlong-screen-20260627T111913Z/` | `CTX=12288` | `64/64` | `102.162482` | `103.706680` | valid loss |
| `data/gemma4-q8-gpu1-cleanrepro-ctx16384-ub768-nmin3-pmin010-filledlong-screen-20260627T112039Z/` | `CTX=16384` | `64/64` | `103.356054` | `103.089425` | valid loss |
| `data/gemma4-q8-gpu0-cleanrepro-runtime-immediate0-filledlong-screen-20260627T112115Z/` | `UR_L0_USE_IMMEDIATE_COMMANDLISTS=0` | `64/64` | `104.386620` | `104.016573` | screen-only possible win; required full run |
| `data/gemma4-q8-gpu0-cleanrepro-immediate0-filledlong-full-20260627T112322Z/` | `UR_L0_USE_IMMEDIATE_COMMANDLISTS=0` | `384/384` | `102.440578` | `103.593739` | valid full loss; do not submit |
| `data/gemma4-q8-gpu2-cleanrepro-runtime-graphoff-filledlong-screen-20260627T112115Z/` | `GGML_SYCL_DISABLE_GRAPH=1` | `64/64` | `104.215683` | `104.405119` | row0 below record; support mean only |
| `data/gemma4-q8-gpu3-cleanrepro-runtime-vmmon-filledlong-screen-20260627T112115Z/` | `GGML_SYCL_ENABLE_VMM=1` | `64/64` | `100.775260` | `101.317997` | valid loss |

## Final conclusion from this batch

No run in this clean-repro threshold/Q8-hoist/shape/runtime batch beats the
current `104.30919255569083 tok/s` fresh-response record after full
confirmation. The apparent `UBATCH=704` and `immediate0` screen wins both
collapsed under the required full canary + benchmark confirmation.

Do not spend more GPU time on isolated `p_min`, `n_min`, UBATCH, CTX, thread,
poll, VMM, graph-off, or immediate-command-list sweeps unless they are attached
to a source-level mechanism. The next useful Gemma work should target
verifier-side MoE / LM-head economics or a fresh-valid speculation structure
that increases accepted tokens per expensive verifier step.

# Packet 118b launch procedure (coordinator only; not executed during this rebuild)

118b rebuilds the blocked 118 design from sealed 117. Sealed 118 is withdrawn and was
never launched. The review fixes change safety comparisons and timing bookkeeping,
not request topology, model operations or tensor arithmetic. XPU qualification is pending.
The timing instrumentation has unmeasured CPU overhead; walk mode is the 117 inspector
with that instrumentation, not a literal whole-path 117 control.

| Item | Value |
|---|---|
| Packet | `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-118b` |
| Manifest SHA-256 | `248e762de49d21b02a4f95d3791dbd9da7504b731f1a88cb5a930a78448db1f1` |
| Parent | sealed 117, `5826174ee3a3965d033758de006552742878f624800dadb90423879b3f0802c9` |
| Supersedes | withdrawn, never-launched 118, `cb68515a1e770697ad0ac2d0c2abd9709780043e9d1579cba81706bb53f482f6` |
| Plan | `d36c188d695c36b2a8849da687d7fe004859888d22af606d94e2ec48afa47b30`; 132 qualification ids, 264 graph pins per qualification row |
| Build receipt | [continuation118b-build.json](../../data/resume-20261008/continuation118b-build.json) |
| Unit | `ltx118b-stream-server-20261009` |
| Launch script | `launch-118b.sh <frames> <anchor> <dg> <ad> <bo> <pa> <walk\|fingerprint> <cap GB\|-> <receipt> [launch\|--check-only]` |
| Client | `stream/start-client-118b.sh <frames> <dg> <ad> <bo> <pa> <walk\|fingerprint> <cap GB\|none>`; `ltx_continuation_client.py --packet 118b` |

## 0. What is different from 117, operationally

- `LTX_SNAPSHOT_MODE=walk|fingerprint` remains explicit. Fingerprint compares residence
  facts bound at placement, falling back to the walk if facts change. Four-card setup
  and qualification snapshots compare both modes; streaming also compares every 20th
  chunk and after a reading within **or equal to** 0.5 GiB of a pre-request floor.
  Either dual sample can make that condition sticky. Both samples must agree on memory
  admission using the site's before/after floors and counter validity.
- Decode-thread P7 always compares both paths, regardless of the successor's chunk.
  The actual P5 free reading is observed without an extra memory read for policy.
- `LTX_DECODER_GRAPH_POOL_CAP_GB` is unset for dg0 and optionally set for dg1. The cap
  is a threshold deciding whether to capture the next decoder method, not a hard
  memory limit. Capped methods use the existing eager cache path and must pass the
  unchanged byte gates. `CAP=-` clears an inherited cap in both launcher env commands.
  Unknown tenth-argument modes refuse before any operational command.
- Latches retain the 116b precedent: `decoder-graph-116-refused.json` for dg1;
  `anchor-decode-117-refused.json` / `anchor-decode-118-refused.json` for cone;
  `precompute-117-refused.json` / `precompute-118-refused.json` for overlap or prep;
  `snapshot-118-refused.json` for fingerprint. Re-identification does not bypass them.
- Names are `stream118b-`; the packet id is the **string** `"118b"`. Wire schemas and
  node classes remain 118. Clip bases are 11820000 / 11821000. The parent is 117,
  recursively verified through 116b and its ancestors to 111.

## 1. Fresh admission (future authorized coordinator work)

This document is a command reference, not authorization to operate the host. The CPU
rebuild did not inspect services, port 8188, devices, health receipts or host fault state.
The coordinator must respect CURRENT.md, current owner authorization and protected work.

Before a future launch, the coordinator requires an available endpoint and cards,
the documented five-minute gap after any separately authorized controlled stop, no
FAULT or applicable lever latch, and a fresh same-boot four-card health receipt under
six hours old. Never stop another agent's work or retry a failed launch automatically.
The launcher checks storage (50 GiB reserve plus 3 GiB run allowance), new run directory,
results-root output/validation/requests name collisions, and zero packet __pycache__.
Use `/home/steve/.venvs/ltx25-baseline/bin/python3 -B` throughout.

Future rehearsal, **not run here** (from repository root; set FRESH_HEALTH_RECEIPT to
an independently authorized fresh receipt path):

```bash
experiments/ltx25-b70/recovery/20261009-continuation118b-stream/launch-118b.sh 121 frame 0 cone 1 1 fingerprint - "$FRESH_HEALTH_RECEIPT" --check-only
```

## 2. Launch command (first: 121 frames, frame anchor, dg0, cone/1/1, fingerprint, no cap)

The measured comparison line is packet 117 at 121 frames dg0: **5.40 s per 5.04 s chunk**.
First test the snapshot change against that configuration. These are separate future
launch choices, not an unattended sequence and not permission to launch now.

```bash
experiments/ltx25-b70/recovery/20261009-continuation118b-stream/launch-118b.sh 121 frame 0 cone 1 1 fingerprint - "$FRESH_HEALTH_RECEIPT"
```

It names unit `ltx118b-stream-server-20261009`, uses venv python3 with `-B`, and starts
`launch/serve-encoder.py` with the pinned manifest above. The run name is
`encoder-server-continuation-stream-118b-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f121`.
Both the direct and unit env commands unset `LTX_DECODER_GRAPH_POOL_CAP_GB` before
adding explicit settings. Unit policy remains Restart=no, SendSIGKILL=no, SIGINT,
TimeoutStopSec=180 and LimitNOFILE=65536:1048576.

| order | frames | dg | mode | cap | reason |
|---|---|---|---|---|---|
| 1 | 121 | 0 | fingerprint | - | matched 117 121 dg0 line |
| 2 | 121 | 1 | fingerprint | 1.0 | test bounded decoder capture against the xpu:3 floor |
| 3 | 97 | 1 | fingerprint | - | uncapped 97-frame decoder graph |

Second and third command arguments after the script: respectively
`121 frame 1 cone 1 1 fingerprint 1.0 "$FRESH_HEALTH_RECEIPT"` and
`97 frame 1 cone 1 1 fingerprint - "$FRESH_HEALTH_RECEIPT"`.
First client: `stream/start-client-118b.sh 121 0 cone 1 1 fingerprint none`
(from `experiments/ltx25-b70`). Mode and cap expectations refuse mismatches at preflight.

## 3. Health and identity after a future start

Status must report packet `"118b"`, phase `stream_setup`, no halt/fault, frame/121,
decoder_graph 0, cone/1/1, snapshot_mode fingerprint, null pool cap and the pinned
runtime manifest. Timing and snapshot features remain true. Preparation binds the
residence ledger; qualification requires all dual snapshot agreements and zero
snapshot failures. Verify each receipt retains the admitted server options.

## 4. Memory (existing evidence and unproven estimates)

Floors are unchanged: before 8/8/2/9 GiB, after 2 GiB per card, and 9 GiB before each
decode/precomputed encode on xpu:3. Packet 117's 121 dg0 run had about 15.64 GB free
on xpu:3; uncapped 121 dg1 refused at 9.59 GB, below 9 GiB (about 9.66 GB).
The original design estimated 11.0–11.8 GB with cap 1.0; this rebuild does not validate
allocator reuse or that estimate. 10.16 GB is an estimate-falsification threshold,
not a changed admission floor. P7's extra CPU checks may change cost; no speed is claimed.

## 5. Qualification (11 requests and one verdict action)

Use the 118b client with exact expectations. Order remains window probe, prepare,
three eager chunks, three graph chunks, three repeat chunks, verdict. Streaming needs
all unchanged eager/replay/repeat tensor gates, reference hashes where present, cone
last-frame equality, precompute/native equality, no new captures after freeze, and
snapshot verdict agreement. With a cap, the admitted capture set stays fixed; newly
seen decoder signatures refuse. A failure latches; no automatic fallback or retry.

## 6. Streaming: what to inspect

Inspect receipts' submit_split, snapshots, authority_checks, turnaround, server_options,
and client turnaround/post fields. `queued` is **POST handler return**, refreshed before
receipt staging; it can follow executor entry. `first_served` is **successful receipt
read and HTTP 200 response construction**, not completed network delivery or fsync.
Missing values and negative intervals stay visible. Split sums alone do not establish
causal accuracy or zero cost. Compare measured chunk periods, exact output gates and
memory floors before making any speed claim. GPU safety operation remains the future
coordinator's authorized work, not part of this rebuild.

## 7. Owner view

The owner still judges seams and quality. This packet adds no quality adoption,
speed improvement, XPU snapshot-equivalence proof or capped-decoder qualification.
See [rebuild evidence](../../notes/2026-10-09-continuation118b-rebuild.md) and
[the independent review](../../notes/2026-10-09-continuation118-review.md).

# Qwen3.8 nightly TP-scale audit correction

Date: 2026-08-23. This note corrects classifications and evidence scope after
reviewing the raw USB artifacts. It does not replace, delete, or alter any raw
run. The measurements remain historical facts; only overbroad conclusions are
superseded.

## TP4 MTP2: infrastructure-invalid

Root `tp4-mtp2-f16-a` is not evidence of an intrinsic TP4 or TP>1
speculative-decode deadlock. Its `server.log` records:

- ranks 1 and 3: `FileNotFoundError` for the same shared Triton
  `triton_red_fused_4.zebin` during Inductor autotuning;
- rank 2: `FileNotFoundError` for `triton_poi_fused_5.json`;
- rank 0: compilation completed, then it waited for failed peers;
- EngineCore: subsequent 60-second `shm_broadcast` starvation warnings.

The runner assigned every rank one writable `TRITON_CACHE_DIR` under the NTFS
USB cache root. The frozen classification is therefore
`infrastructure-invalid: concurrent shared-cache artifact failure with
downstream peer starvation`. Do not report a TP>1 deadlock from this root. The
next valid door is a separately identified TP2 eager-MTP2 boot/canary with
isolated rank caches or a sealed precompiled cache; TP4 follows only after a
TP2 pass.

Raw log SHA-256:
`b229f25b3f605e03be773859a0a504d3b70300b4ef8804bbadc608f2bc34a007`.

## TP4 graph evidence scope

The `71.6741 / 71.5488 tok/s` conventional pair is preserved. It is the
fastest target-only Qwen3.8 measurement for this AutoRound/nightly identity,
not the lab-wide target-only record. The pair matches 21/25 complete outputs.
The runtime warns that XPU Graph currently supports only single-GPU execution,
so TP2/TP4 graph results are unsupported/experimental characterization even
though they completed.

The quality artifacts genuinely pass seven objective expected-answer canaries,
an 8-run same-server repeat, cache-zero checks, and an 8K needle. They did not
receive `--baseline-json`; `baseline_comparisons={}` makes the stored
`baseline_match_all=true` value vacuously true. It is not oracle-parity
evidence. Future record gates must supply a real baseline.

The benchmark payload also set `ignore_eos=true`. These are deliberate
diagnostic timing captures, not natural-EOS submission gates. No displayed
speed is recomputed or lowered; a new final run must use strict 100-event /
99-interval accounting and allow natural EOS.

## Bound raw evidence

Paths are relative to
`/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/tp1-nightly-20260822/`:

| Artifact | SHA-256 |
| --- | --- |
| `tp2-mtp0-f16-graph-a/bench.json` | `e0acf134286db1180931daad3841bfa2ca880c4ae44b5d5c660bd7f231d246ec` |
| `tp4-mtp0-f16-graph-a3/bench.json` | `404c6fe5d2c8071a41fba159a11cf8e1044d330b282da4b07d38e4c631baebc5` |
| `tp4-mtp0-f16-graph-b/bench.json` | `8f30b6e80c087291673bde34775fe1e3c9798afd4d83f0158848b75353f73715` |
| `quality-tp2-f16-graph/quality.json` | `e51d506f12d30004ec55354fbbe40080c096ce5309939a79ccbdac340d900075` |
| `quality-tp4-f16-graph/quality.json` | `4d1b126823464ef72fd57cacb9a47f1ef405c86fa6c707e698e93237d1ff50d0` |
| `tp4-mtp2-f16-a/server.log` | `b229f25b3f605e03be773859a0a504d3b70300b4ef8804bbadc608f2bc34a007` |

## Separate mechanisms

Do not merge the nightly TP1 graph+MTP immediate corruption (0% acceptance,
0/25 output match) with the pinned TP2 MTP5 dose-8 multi-chunk corruption. No
shared mechanism has been established. The preregistered D1/D2 state-slot and
initial-state program remains a separate two-run investigation.

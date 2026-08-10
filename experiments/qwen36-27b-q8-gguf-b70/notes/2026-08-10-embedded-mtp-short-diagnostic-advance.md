# Embedded publisher-MTP short diagnostic: confirmed `ADVANCE`

Date: 2026-08-10

## Decision

The pinned integrated publisher MTP artifact is a strong **short, two-prompt
diagnostic lead**.  A prospective matched-horizon correction to the comparator
was committed before the confirmation run, and the unchanged configuration
then classified `ADVANCE_FULL_VALIDATION`.

This is not a promoted performance result.  Both valid packets are
`official-isolated-diagnostic` with `performance_promotable=false`.  The work
does not establish the fixed cold realistic suite, middle or near-32K
retention, a second-card reproduction, c2 behavior, production readiness, or a
LocalMaxxing-eligible result.

## Identity

- model: integrated `unsloth/Qwen3.6-27B-MTP-GGUF`
- revision: `5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace`
- file: `Qwen3.6-27B-Q8_0.gguf`
- size: `29,047,084,160` bytes
- SHA-256: `9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8`
- GGUF/runtime gate: 65 blocks, 64 trunk layers plus one declared next-token
  layer, and `66/66` layers offloaded in both arms
- llama.cpp commit: `15586e2d7165570fb3aa7c26e0d442e289ef69de`
- `llama-server` SHA-256:
  `1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7`
- VDR2 runtime manifest SHA-256:
  `4119790a79c55d158e7257d4fa0d95be0ca34639807c1a71ce87b60d6fdc1b49`
- GPU: isolated B70 GPU 0, BDF `0000:23:00.0`
- common service identity: `-c 32768 -np 1 -b 1024 -ub 1024`, F16 K/V,
  flash attention on, no prompt/context/response cache, one slot
- control: `--spec-type none`
- candidate: embedded `draft-mtp`, `n_max=3`, `n_min=0`, `p_split=0.10`,
  `p_min=0.00`, backend sampling explicit, draft device `SYCL0`, all draft
  layers offloaded, F16 draft K/V, and no sidecar model

The two measured prompts contain 4,369 and 4,317 prompt tokens.  Each arm
captured two forced 512-token streams, exact replay, and a separate 128-token
post-canary with native cache reuse at zero.  Both arms match the sealed
integrated-model oracles derived from the official VDR2 target-only oracles;
the derivation proof changes only the model hash.

## Sealed pre-measurement failures

These are harness false starts, not performance measurements, and remain
preserved so the same mistakes are not repeated.

1. `embedded-mtp-vdr2-two-arm-gpu0-20260810T083532.916412563Z`
   stopped before model measurement because this runtime rejects the obsolete
   `-fitp` argument.  `run-status.txt` is `FAIL`; its 42-entry manifest verifies
   and has SHA-256
   `99a07a5fc720b94df96b33acb38811d42b518e8e67b25b3550a3ad66af37fc44`.
   Commit `c337c4649` removed only that invalid fitter argument and added its
   regression check.
2. `embedded-mtp-vdr2-two-arm-gpu0-20260810T084031.947279449Z`
   loaded the control successfully but stopped before requests because the
   harness searched for stale `n_layer_nextn = 1` text.  The actual runtime
   correctly logged `qwen35.nextn_predict_layers u32 = 1`, 65 total blocks,
   and `66/66` offload.  `run-status.txt` is `FAIL`; its 43-entry manifest
   verifies and has SHA-256
   `42239f5f3ba952bd199bf7b6bde196c8f63b286845b083123637c3316b6a092a`.
   Commit `418f3e320` bound the gate to the actual metadata line.

Neither packet has a completion marker or supports a speed claim.

## First valid packet and the historical classifier

The first fully measured packet is:

```text
/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/
  embedded-mtp-vdr2-two-arm-gpu0-20260810T084545.325933113Z
```

- 78-entry artifact manifest SHA-256:
  `35820eb781d1977ca6353cb2c5b4d52f50f8de1a49876e4e8ec00a0863e4dc23`
- completion SHA-256:
  `f52d9093faceffbe8efc41a8dbb1f489aced02d0a8d67f4b0bb36d9093be1725`
- comparison SHA-256:
  `bc484bc4fd1bc7155aca5e3313bd2fccfcbb056510a8556e3c7411cadc42f2a8`
- manifest verification: `78/78`
- evidence: valid; both arms exact; all integrity and cleanup gates pass
- retained historical classification: `ONE_BOUNDED_NMAX_PMIN_FOLLOWUP`

Measured medians were:

| View | Control | MTP3 | MTP3/control |
|---|---:|---:|---:|
| primary 99-interval decode | `16.586983` | `44.697177` | `2.694714x` |
| matched full-window D511 | `16.591187` | `48.064195` | `2.896971x` |
| stream-native 512-token rate | `16.623595` | `48.157360` | `2.896928x` |
| replay-native rate | `16.606763` | `48.063198` | `2.894194x` |
| TTFT | `7.195851 s` | `7.515125 s` | `1.044369x` |

The MTP metrics endpoint and response fields agree: 1,597 accepted tokens,
1,709 drafted tokens, and 572 verifications across the two streams, their
replays, and canary.  The two measured stream/replay request pairs account for
1,516 accepted of 1,574 drafted tokens.  Acceptance is `0.934465`, accepted
tokens per verification are `2.791958`, and effective target-verified tokens
per verification are `3.791958`.  Control speculative counters remain zero.

The only failed advance check compared unlike horizons: the 99-interval SSE
view covers early token events, while native server timing covers all 512
generated tokens.  Speculative bursts make those views useful independent
measurements, but their speedup ratios need not agree.  The observed unmatched
ratio disagreement was `0.202214`; it did not invalidate exactness or the
large gain.  The original completion classification is preserved rather than
rewritten.

## Prospective comparator repair and confirmation

Commit `d878aecb9` changed the consistency co-gate prospectively.  It retains
and independently gates the policy 99-interval metric, but compares native
all-512 timing with the matched full-window D511 metric.  Tests were extended
before hardware replay.  No result artifact was edited or retrospectively
reclassified.

The unchanged confirmation is:

```text
/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/
  embedded-mtp-vdr2-confirmation-gpu0-20260810T090326.726315114Z
```

- 78-entry artifact manifest SHA-256:
  `2d044a5c1891de7e1885487515a418b2194c80d61f663deaea6f0274b2062716`
- comparison SHA-256:
  `0fde58da836cf95b0b20b78a024db85d6859056d8f6000532abcf68bf6ada6f9`
- completion SHA-256:
  `567556079e1cfdda164288cccef2358599d08f2e9072ab027dca6ff29dc609bc`
- manifest verification: `78/78`
- completion: `passed=true`, `evidence_valid=true`, `advance=true`
- classification: `ADVANCE_FULL_VALIDATION`

Confirmation medians were:

| View | Control | MTP3 | MTP3/control |
|---|---:|---:|---:|
| primary 99-interval decode | `16.586788` | `44.696620` | `2.694712x` |
| matched full-window D511 | `16.590928` | `48.037351` | `2.895399x` |
| stream-native 512-token rate | `16.623274` | `48.131415` | `2.895423x` |
| replay-native rate | `16.611110` | `48.052665` | `2.892803x` |
| TTFT | `7.192316 s` | `7.517484 s` | `1.045210x` |

The per-prompt primary ratios are `2.743380x` and `2.646045x`.  The matched
full-window/native ratio disagreement is only `0.00002456`, while the retained
unmatched early-interval/native diagnostic is `0.200711`.  Every preregistered
speed, per-prompt, TTFT, exactness, acceptance, and counter check passes.  The
confirmation reproduces exactly the original counter totals: 1,597 accepted,
1,709 drafted, 572 verifications, `0.934465` acceptance, `2.791958` accepted
per verification, and `3.791958` effective target-verified tokens per
verification.

## Fit, integrity, and cleanup

Both valid packets report the same fit and cleanup state:

- control: fitter projected `3,891 MiB >= 1,024 MiB` headroom with no
  adjustment; observed load `43 -> 28,642 MiB`;
- embedded MTP3: fitter projected `2,563 MiB >= 1,412 MiB` headroom with no
  adjustment; observed load `43 -> 29,911 MiB`;
- control and MTP3 each offloaded `66/66` layers; both target contexts, and the
  MTP draft context, retained `n_batch=n_ubatch=1024`;
- harness inputs, model stat/SHA, runtime bundle, and resolved dependencies
  remained unchanged;
- each arm stopped without a forced kill or survivor, closed its port, and
  returned GPU 0 from `43 -> 43 MiB`;
- retained device/server/kernel scans are clear.

## Scope and next gate

The result proves that this exact integrated artifact plus embedded MTP3 can
produce a large, repeatable, target-verified decode gain on two known short
prompts.  It does **not** yet prove generality.  It must remain separate from
the target-only Q8 baseline and must not be represented as a production,
broad-suite, c2, cross-band, or LocalMaxxing result.

The next gate is the fixed realistic suite, once per prompt, cold and
cache-zero, with the target/verifier identity and exact outputs retained and
the conventional 99-interval metric reported.  Only if that passes should the
same policy advance to middle and near-32K retention checks, then a second-card
confirmation and the relevant concurrency gate.  Do not tune `n_max` or
`p_min` from the historical `ONE_BOUNDED` label before this generality test.

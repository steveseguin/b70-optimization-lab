# Laguna separate shared gate+up native-M8 counter terminal negative

Date: 2026-07-24 America/Toronto

Status: the first and only authorized cold-counter capture completed all
sixteen arms and is terminal before endpoint work. The candidate remained
bitwise exact, but the frozen parser failed and the immutable counter bytes
also fail the core matched-pair and per-card promotion requirements. There is
no rerun, acceptance repair, endpoint, model generation, payload, network
access, record claim, reboot, or LocalMaxxing submission.

## Frozen identity and closure

The counter tooling is commit
`34db11e8f9cee45e455390da7961e28c959b0441`. The immediate packet-only
authorization is commit
`a8c8c595978e1803a354869d53cef77cae79781c`; its packet SHA-256 is
`a91749870de477207d21c464660adde164cf1c9b24faca2e62d836a4046b4748`.
The complete live root is on internal NVMe:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/shared-gate-up-m8-counters-20260724T063300Z
```

The one-shot runner completed physical cards 0 through 3 sequentially, with
`A1 -> B1 -> B2 -> A2` on every card. Each arm contains exactly 13
completion-bounded gate-then-up pairs, exact PID-bound unitrace timing and
ComputeBasic files, and a closed manifest. The principal seals are:

- campaign intent:
  `591aeb60b3fddf42006f1152a7ee307c6f814145f64c1cb9a10c68de29e8a7c1`;
- campaign open:
  `473ec7f973a0f3ecf86f7cf0c17dcaf38ff4828c1ed4622988f70f4523393516`;
- campaign complete:
  `0c082d4c3ce71987587ba5c8293ad6348d750840a3084121714a581baa943654`;
  and
- analysis error:
  `7f6738d0b8c75b43e63ced5208a89cadfe7f9c6fff63ec423c38133fc8ed9b84`.

The external USB was not used.

## Exactness

The fixture-level exactness closure passed. Every one of the sixteen arms
repeated the same raw BF16 gate and up hashes on all 13 pairs, and the
cross-arm/card tuple count is one:

- input fixture:
  `49fd9c1dc22472e942bfae8031b8b8e5aa08ffb85b98158edea6c3134d16bd37`;
- gate:
  `bf117165cb35ce114581e127522ba287b9440b7ef88ea8ed068647556edc5e40`;
  and
- up:
  `0f005ce34fbf306b9177b2f70043cb0ef4ad8b3472d3a40774f25676f4b0be32`.

The sealed component predecessor still covers the nine downstream BF16
boundaries with final-manifest SHA-256
`8aa2a45a8bcc31c5d2e84e5f55568ad43144ebd6c380d6d914cf91f77d10a10d`.
Quality was not sacrificed.

## Frozen parser failure

The offline analyzer stopped at the first card-0 A1 metric row:

```text
nonzero invalidity/traffic proxy SLM_BYTE_READ[bytes]
```

All 416 selected metric rows actually report exactly 245,760 SLM bytes read
and 245,760 SLM bytes written, for both control and candidate. Every row has
zero SLM bank conflicts, zero LSC partial writes, and zero LSC byte writes.
This shows the preregistered parser misclassified ordinary constant SLM
traffic as a zero-required failure proxy.

That observation does not authorize changing the acceptance rule after
seeing the result. The parser and packet were frozen before capture, so the
campaign remains failed and `analysis.error.json` remains immutable. No
offline repair is used to manufacture a pass.

## Diagnostic result cannot rescue the candidate

For research direction only, the retained metric rows were summarized
without treating that summary as a replacement analyzer decision. Even if
the SLM rule were ignored, the candidate fails the original no-rescue
requirements:

| Rank | B1/A1 GPU time | B2/A2 GPU time | Candidate/control aggregate | Occupancy delta pp | XVE-stall delta pp |
|---:|---:|---:|---:|---:|---:|
| 0 | 0.994767 | 0.633845 | 0.812314 | +0.798427 | +1.105145 |
| 1 | 0.937180 | 1.401331 | 1.163663 | +1.105352 | +0.645766 |
| 2 | 1.056653 | 0.815515 | 0.921325 | +1.741008 | +1.650995 |
| 3 | 0.956882 | 1.320946 | 1.117919 | -2.450955 | -2.292902 |

Required matched comparisons fail at rank 1 B2/A2, rank 2 B1/A1, and rank 3
B2/A2. Card aggregates fail on ranks 1 and 3. Complete per-card guardrails
also fail: ranks 0 through 2 exceed the 0.5 percentage-point XVE-stall
allowance, and rank 3 loses 2.451 occupancy percentage points. The global
candidate/control GPU-time ratio is `0.9935168`, a diagnostic 0.6483% win,
but global evidence is explicitly forbidden from rescuing any failed pair,
card, or guardrail.

The component loop's 9.4-11.2% repeated-cycle gain therefore does not survive
the cold per-dispatch variance contract. This is useful negative evidence,
not a promotion result.

## Terminal decision

The separate shared gate+up native-M8 promotion lane is closed. The capture
must not be rerun, selectively sampled, reinterpreted, or used to authorize an
endpoint. Preserve the candidate and this evidence as a measured negative.
The next optimization must be materially different and preregistered before
its evidence is observed.

The structured summary is
`data/laguna-s-2.1-shared-gate-up-m8-counter-terminal-negative-20260724.json`.

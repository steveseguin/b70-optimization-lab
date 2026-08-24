# 6a9c TP1 r1 completed with a speed-only miss

Date: 2026-08-24. Status: **complete, quality-clean, not qualified; no
promotion and no lower floor.**

The committed zero-overlay TP1 packet ran its entire frozen sequence once on
literal-current vLLM `6a9c69fa851389dcf1ee5d3a2363e27af665d26d`, current XPU
kernels `baaa05bb4e92901219a5a072dd63f2474896f6d1`, and official nightly base
digest
`sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`.
The hardware gate, diagnostic arm, strict quality replay A, and strict replay B
all completed. Every non-speed gate passed. Both strict arms missed the frozen
`30.31067504052998 tok/s` floor, so the exact result is
`complete-speed-only-regression-no-overlay-run` and cannot qualify TP1.

This result does not lower or relabel any captured speed, authorize TP2/TP4,
or discard an accepted optimization. It authorizes only a separately
preregistered TP1 decision-compatibility test. That successor may seed exact
path- and `configs_hash`-compatible `.best_config` decisions into a wholly
fresh cache and compile from scratch; it may not copy compiled outputs or the
old cache.

## Measurements

All rates below use the conventional 99 inter-token intervals after TTFT on
25 unique, cache-zero prompts.

| Arm | Median tok/s | Frozen floor | Result |
| --- | ---: | ---: | --- |
| fresh diagnostic, ignore EOS | `30.27858669748398` | `30.2178` | pass by `0.060786697483980134` (`0.201162%`) |
| strict natural-EOS replay A | `30.26782494070049` | `30.31067504052998` | miss by `0.04285009982949006` (`0.141370%`) |
| strict natural-EOS replay B | `30.27119782672338` | `30.31067504052998` | miss by `0.039477213806598854` (`0.130242%`) |

The strict mean is `30.269511383711937 tok/s`. The diagnostic observation is
`0.02168669748397889 tok/s` above the protected `30.2569` diagnostic high, but
it remains dated support rather than a replacement because the complete
qualification failed its two strict speed gates.

Strict replay A passed all seven objective exact cases, an 8/8 one-hash repeat,
the 8K needle (`7,617` actual prompt tokens), and all 24 baseline comparisons.
The fresh/replay token comparison matched 17/25 complete arrays and 23/25
first-100 arrays; that frozen field is report-only, while the declared quality
battery passed.

## Integrity and preservation

The fresh post-reboot gate passed 70/70 sealed files, including four-card
identity and compute, peer read, four-rank XCCL, coherent runtime, root-NVMe
health, kernel taint 0, and clean postflight. Its manifest SHA-256 is
`b15e94a256fcc4870edfa21240d0230fcd4ee7a7329cc33feb2a81f5f01cadbe`.

The campaign verifies 255/255 evidence files and 21/21 frozen inputs:

- campaign manifest SHA-256
  `ecc882372a9408ede3e660d56a6ed9e986adf2d748199e9caa331fd57ef00e10`;
- input manifest SHA-256
  `e493930467912721f58422afef5a6ebe2494bae1288f251500efe4536a17b28b`;
- aggregate result SHA-256
  `fc4c81bdf75dd632c60bde47865272e5f63a0a21e457abe5de4bc2cc9ef2b213`;
- immutable 1,097-file compile-cache manifest SHA-256
  `4a41a96bb1ddb9c5a96d476c11bca89278742a61f9b20aace40cfbcec39364a4`.

All three arms directly and ordinarily verified the model, returned exact
canary content `14` with zero cached tokens, retained exact source and image
identity before and after work, left the compile cache byte-identical across
replays, and exited with clean container, port, render-holder, kernel, and
repository postflight state. The sealed raw roots remain at:

- `/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-6a9c69fa85-20260824-086de284-venvlib-r1`;
- `/home/steve/qwen38-current-main-runs/tp1-untreated-6a9c69fa85-20260824-r1`.

The diagnostic arm classified and accepted exactly one already-known 21-line
corrected root-NVMe event under the frozen host-noise rule; it had zero rejected
events. Both strict arms had zero accepted and zero rejected events. This is
not a hidden model, GPU, or quality failure.

A fresh remote check at `2026-08-24T20:25:11Z` still resolved the exact built
vLLM head, kernel head, and nightly digest. The protected performance ledger
remains byte-semantically exact at canonical SHA-256
`e6ee2cb9908ce940087788243eac5b544c0d2831b94efa47fe6441232c740e8f`.
The 78-decision TP2 and 152-decision TP4 artifacts remain intact, disabled, and
unapplied at their existing manifest hashes.

## Next gate

Derive and independently audit one new 6a9c TP1 overlay-only packet. It must
freeze this completed parent result, re-map the historical qualified TP1
decisions against the sealed 6a9c cache by exact relative path and embedded
`configs_hash`, seed only the compatible subset into an absent ext4 cache,
compile fresh, and rerun diagnostic plus strict A/B under the unchanged floors
and full quality battery. If upstream moves before launch, close that packet
stale and build the newer head. If the overlay misses, preserve the negative;
do not lower the floor or advance to TP2.

The structured record is
[`2026-08-24-qwen38-6a9c69fa85-tp1-r1-speed-only-miss.json`](../data/2026-08-24-qwen38-6a9c69fa85-tp1-r1-speed-only-miss.json).

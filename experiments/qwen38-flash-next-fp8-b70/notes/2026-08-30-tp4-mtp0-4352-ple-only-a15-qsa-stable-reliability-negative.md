# Qwen3.8 Flash-Next FP8 TP4 MTP0 A15 reliability result

Date: 2026-08-30
Status: rejected at exact-4K repeat and authority gate

A15 was the separately started recovery replica required after A14 ended before
inference. It retained the exact A13 deterministic QSA treatment, model,
TP4/EP4 eager MTP0 topology, 51.200-GB PLE-only host placement, 128-MiB cache,
prompts, seeds, and full battery.

Bring-up and all short-context gates passed. Every rank offloaded exactly
11.92 GiB, model load reported 31.57 GiB/card, recovery passed, the established
quality battery remained 6/7 with only the inherited code case, the repeat was
16/16 one hash, and the exact-4K needle passed without cache reuse. The three
short rows returned the protected authority at `5.449165 / 5.339399 /
5.381340 tok/s`, median **`5.381340 tok/s`**—essentially identical to A13 and
3.02% above the protected current-runtime median.

The two byte-identical exact-4K rows each passed every transport and timing
gate at `5.226537` and `5.272196 tok/s`, but returned different non-authority
hashes, `b55aa3ab...c19e0` and `f2829dab...f645d`. They first differ at
zero-based generated token 2 and differ at 125 of 128 positions. The client
therefore failed closed and none of these 4K timings receives performance or
promotion credit.

The stable selection patch fixed a concrete exact-tie/order mechanism, but A15
proves it is not sufficient to make the full forward/score path deterministic.
A13 remains a bounded same-server positive; it cannot be called reliable or
lossless, and the patch remains outside the promoted production series. The
next bounded work is source/device diagnosis of the QSA score/reduction path,
not another unchanged full-model load.

Owned teardown was complete and all four cards returned below 43 MiB with no
B70-addressed event. Corrected local-NVMe receiver records remain a clean-host
caveat. No protected result changed.

Structured receipt:
[`../data/20260830-tp4-mtp0-4352-ple-only-a15-qsa-stable-reliability-negative.json`](../data/20260830-tp4-mtp0-4352-ple-only-a15-qsa-stable-reliability-negative.json).

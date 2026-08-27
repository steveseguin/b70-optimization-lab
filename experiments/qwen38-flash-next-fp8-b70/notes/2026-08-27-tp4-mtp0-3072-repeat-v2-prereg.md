# Qwen3.8 Flash-Next FP8 TP4 repeat-v2 and 2K retry preregistration

Date: 2026-08-27

## Purpose

Separate the historical open-choice color sensitivity from prescribed-answer
repeat stability, then retry the quarantined 2K measurement only if the new
quality gate passes. The original configured-3,072 attempt and its quarantine
remain immutable evidence.

## Evidence behind the protocol correction

Across 56 retained open-choice repeats from healthy production servers, 54
returned `blue, green, red, yellow` and two returned `black, blue, green, red`.
Both satisfy the old instruction to invent any four color words and sort them.
The two deviations occurred at unrelated positions on different boots. In
contrast, all seven prescribed short cases were byte-identical across five
healthy batteries, and both retained long-context needles were identical.

Temperature zero uses direct greedy argmax. A request seed cannot resolve a
small numerical change in the first-token `black`/`blue` ordering. The
historical result therefore proves sensitivity on an under-specified prompt,
but it does not by itself establish broad output instability.

The updated repeat protocol fixes the input set to `yellow, red, green, blue`,
requires all 16 outputs to equal `blue, green, red, yellow`, and requires one
hash. Baseline comparison now covers the repeat protocol and aggregate result,
not only repeat zero. Prior suite files, hashes, receipts, and the quarantined
attempt remain unchanged in Git history.

## Frozen server identity

Use the unchanged configured-3,072 TP4/EP4/eager/MTP0 launcher with
`ATTEMPT=2`. No server source, runtime binary, environment, cache, placement,
communication, graph, scheduler, or performance option changes from attempt 1.
The server must again prove:

- model revision `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- vLLM `658965050f259999e635b52a850004a3771cd644` and kernels
  `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- exact sealed production stage, TP4/EP4, eager, MTP0, graph off;
- four exact 12.22-GiB placement receipts and the expected 31.27-GiB footprint;
- 192-MiB BLHNC/auto KV, prefix cache off, one sequence, 64 batched tokens;
- configured maximum 3,072 and at least 2,304 reported cache tokens;
- diagnostics absent.

## Capped request program

1. Run `scripts/qwen38-repeat-sensitivity-probe.py` with 32 requests per
   phase. Each request asks for only the first greedy token and returns scores
   for token IDs 11,124 (`black`) and 11,855 (`blue`). The historical
   open-choice phase is diagnostic and may vary; the fixed-set phase must
   return `blue` 32/32. Every request must be cache-zero and return both named
   scores. Diagnostic request timing is never performance evidence.
2. Run `scripts/qwen38-text-quality-suite.py` once with 16 fixed-set repeats,
   thinking disabled, and calibrated `--long-context-tokens 2157`. Require
   the same five prescribed short passes and no new short failure, exactly
   16/16 expected repeat outputs with one hash, exactly 2,048 server prompt
   tokens for the needle, exact needle output, and cache-zero throughout.
   Do not compare this changed repeat protocol to the old v1 repeat row.
3. Only if steps 1 and 2 pass, run the sealed formal exact-depth p2048/o128
   request. Require exact prompt depth, zero cached tokens, no context shift or
   truncation, 128 token IDs, length stop, and valid 100-event/99-interval
   timing.
4. Only if the formal receipt passes, run three no-logprob p2048/o256/c1
   requests with no warmups, requested prompt-token target 2,099, and salts
   `context-r1`, `context-r2`, and `context-r3`. Each must report exactly 2,048
   prompt and 256 completion tokens. These use the unchanged legacy accounting
   solely for comparison to the retained 1K screen.
5. Stop normally and preserve all logs, responses, request order, hashes, and
   shutdown evidence.

The realistic 12-prompt suite is not repeated because the same production
source/runtime already passed it and this arm changes no server behavior.

## Frozen interpretations

- Fixed-set instability, missing named scores, a nonzero cached-token value,
  a new short failure, needle failure, or any identity/capacity mismatch stops
  the speed phase and triggers the previously designed report-only state audit.
- A stable fixed-set phase plus small or sign-changing open-choice
  `black`/`blue` margins classifies the old color row as a sensitivity probe,
  not a deployment gate. It does not erase the old raw divergence.
- A passing retry may add a new `lab-screened` 2K measurement while retaining
  attempt 1 as superseded quarantine evidence. It cannot lower or overwrite
  the 512 or 1K rates.
- Even a full pass remains research-only because the substantive 5/7 short
  quality boundary still blocks deployment promotion.
- No throughput from a request with logprobs is publishable.

## Sealed inputs

- repeat-v2 quality suite SHA-256
  `3350671d03fa7c08e579df8bef9affbee51a3cf2f160a9d120c7166c0012c678`;
- sensitivity probe SHA-256
  `7c948e3e2844279c7249d74d51eca462d3e0083134f79fb640778da5b4bb7c01`;
- repeat protocol tests SHA-256
  `5a746008cad813fed30ed14b3c3692d95e4b99e30119fac63f204ecf5272f766`;
- exact-depth fixture SHA-256
  `c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d`;
- exact-depth harness SHA-256
  `8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067`;
- legacy depth harness SHA-256
  `0703d8f0564cab625183a02f010d238c8456d2e9e6aac04f4b8e11f81c8d6ae0`.

## Result

Attempt 2 kept the exact server identity and again reported 6,144 cache tokens,
four 12.22-GiB placement receipts, and 31.27 GiB per rank. The sensitivity
probe passed cache-zero: both phases selected `blue` 32/32. On the open-choice
prompt, the `blue`-over-`black` returned-score margin varied among only 0.125,
0.25, and 0.375; with the input set prescribed, the margin was 9.1875 to
10.1875. This supports retaining the old divergence as an ambiguity-sensitivity
finding rather than treating it as broad state failure.

The full repeat-v2 battery then returned the exact prescribed list 16/16 with
one hash, passed the exact 2,048-server-token needle, and kept all 24 requests
cache-zero. The same known five-of-seven short boundary remained with no new
failure.

The formal exact-depth row passed every gate at p2048/o128 and measured
`3.864878 tok/s` on the conventional 99-interval window with `111.660 s`
TTFT. Three separate p2048/o256 legacy-comparative rows measured `5.034313`,
`5.257402`, and `5.228429 tok/s` after first text, median `5.228429 tok/s`;
all returned 256 tokens with the same output hash. The legacy harness does not
retain cached-token detail, so the formal row is the cache-zero authority.

All four workers and the application completed a controlled stop, with the
known post-manager API message and four resource-tracker cleanup items; no
process or listener remained. Attempt 1 remains retained quarantine evidence.
Attempt 2 supplies a new research-only `lab-screened` 2K measurement. Receipt:
`data/20260827-tp4-mtp0-3072-context-repeat-v2-screen.json`.

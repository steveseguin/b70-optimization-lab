# Qwen3.8 Flash-Next FP8 A56 tuned M1 W13-N32 map endpoint result

Date: 2026-09-02 10:17--11:25 EDT, boot `67848b88-c7c7-452a-bef1-124364a300b9`
(BIOS 2.4a, root SSD Gen4 x4 under the validated clearance)
Status: short-context exact speed positive; exact-2K repeat negative; the arm
failed closed at the client's final assertion, so nothing is promoted

## What ran

`sudo tools/run-q38-a56-host-controlled.sh` (swap off, ASPM performance,
numeric AER baselines), the frozen A56 launcher/supervisor, then the client
as a separate step. The A56 packet is A55 plus one inference change:
`VLLM_TUNED_CONFIG_FOLDER=configs/moe-m1-w13-n32` (eight warps at M1 plus
the W13-only `BLOCK_SIZE_N=32` delta). All identity receipts held: the
launcher wrote `tuned_config_folder=moe-m1-w13-n32` and the map hash, the
live server environment carried exactly that folder, vLLM logged
`Using configuration from .../moe-m1-w13-n32/...`, and the official resolver
receipt in the run directory proved key 1, W13 N32/eight warps, W2 N64/eight
warps, and M2--M512 preservation.

External checkpoint load `551.69 s`; full-decode graph captured; API healthy
at 10:32. Note for operators: the supervisor waits for the client's stop
file and does not launch the client; the server idled healthy for 47 minutes
until the client was started by hand at 11:19.

## Results

| gate | A56 | A55 (same identity minus the map) |
|---|---|---|
| recovery canary | pass | pass |
| semantic quality | 6/7 (sole known miss `code_execution`) | 6/7 |
| 16 short repeats | one hash `3b0b3192...` | one hash |
| exact needle, cache zero | pass | pass |
| short rows p146/o256, cache zero, output hash | `5f407446...` on all three | `5f407446...` on all three |
| short rows tok/s after TTFT | `23.626811 / 22.218021 / 23.809477` | `19.071017` median |
| short median | **`23.626811 tok/s`** | `19.071017 tok/s` |
| exact-2K rows tok/s (99-interval) | `12.982052 / 12.333460` | `11.354325` (row 1) |
| exact-2K output hashes | `243b555d...`, `ec96db80...` | `6bebd491...` (row 1) |
| 2K authority `5fd297f7...` matched | no (neither row) | no (row 1) |

Short-context decode is `+23.9%` over A55 and `+15.2%` over the A44
diagnostic `20.507849 tok/s`, with the protected output hash intact on every
row and the full quality boundary unchanged. Two lossless component wins
(eight-warp M1 and W13-N32) therefore compose into a real endpoint gain, and
the map is safe at M1 decode: 16 repeats plus three rows produced one hash.

The exact-2K rows both passed transport, cache zero, 2048/128/2176 usage,
and the payload/prompt hashes, but their 128-token outputs differ from each
other within the same server and from the 2026-08-28 eager-line authority.
The client's final assertion (`len(set(depth_hashes)) == 1`) failed, the
supervisor recorded `FAIL ... client rc=1`, tore the server down cleanly
(rc 143), and the host wrapper restored swap and ASPM. No protected result
changed.

## Interpretation of the 2K failure

This is not the tuned map. A55, without the map, already returned
`6bebd491...` on its only 2K row, which is also not the authority; the
earlier A55 note called that row "passed" because its transport gate passed,
not because the hash matched. A44 saw the same pattern at 4K (row 1 matched,
row 2 did not). The map's non-M1 entries are byte-identical to vLLM's
defaults for every prefill chunk shape (`max_num_batched_tokens=64`), and
M1 decode is proven exact here. What A56 adds is the sharpest observation so
far: two identical 2K requests to one healthy server disagree. Long-prefill
output in the full-graph line is nondeterministic run to run, and the
certified lossless context for this line currently ends below 2K prompts.

## What this authorizes

- The tuned M1 map advances as the endpoint's M1 MoE configuration for
  short-context service; its promotion needs an arm whose acceptance matches
  the certifiable context (short rows, repeats, needle, canary) or a fix for
  the 2K nondeterminism, and a fresh-server repeat of the `23.626811 tok/s`
  short median.
- The 2K nondeterminism is the next diagnosis: same-server repeat rows at
  256, 512, 1024, 1536, and 2048 prompt tokens to find the boundary, then
  the twoshots/public-oneCCL and chunked-prefill suspects in turn.

Evidence: run directory
`.../qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-2304-ple-only-r1-attempt56/`
(`identity.txt`, `moe-m1-w13-n32-selection-receipt.json`,
`fullgraph-runtime-before.json`, `recovery-canary.json`,
`quality-current.json`, `bench-short-r{1,2,3}.json`,
`exact-depth-2k-r{1,2}.json`, `server.log`), supervisor directory
`...-attempt56-supervisor/` (`host-pressure.tsv`, `aer-baseline.txt`,
`kernel-follow.log`), state `/tmp/q38-mtp0-ple-only-a56.{rc,failed}`.

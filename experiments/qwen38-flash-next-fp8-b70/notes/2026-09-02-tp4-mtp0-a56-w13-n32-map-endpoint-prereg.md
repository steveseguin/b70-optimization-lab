# Qwen3.8 Flash-Next FP8 A56 tuned M1 W13-N32 map endpoint preregistration

Date: 2026-09-02
Status: frozen before GPU launch; requires the same-boot Gen4 root-NVMe
clearance receipt and an idle four-B70 host

## Question

Does the component-qualified tuned M1 MoE map, selected through the real
deployment mechanism, change the protected short-output hash, the exact-2K
repeat, or the quality boundary of the full-graph TP4/EP4 MTP0 endpoint, and
what does it do to the p146/o256 cache-zero decode rate?

## Treatment and its provenance

A55 (and every full-graph arm since A44) ran with no tuned MoE folder, so its
M1 Triton MoE resolved vLLM's default block-FP8 entry: `BLOCK_SIZE_M=16`,
`BLOCK_SIZE_N=64` for both GEMMs, `BLOCK_SIZE_K=128`, `GROUP_SIZE_M=1`,
`num_warps=4`, `num_stages=4`. A56 exports

```
VLLM_TUNED_CONFIG_FOLDER=experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32
```

whose key-1 entry is the retained `moe-warps8-m1` map (`num_warps=8`) plus the
nested `"W1_CONFIG": {"BLOCK_SIZE_N": 32}` delta that the default-off
per-phase resolver applies to the W13 launch only (XPU, M1, block FP8
`[128,128]`); W2 keeps N64. Both deltas are lossless component positives on
real weights:

- eight warps at M1: 8.46--9.27% lower median M1 MoE latency, exact hashes
  (`notes/2026-08-30-moe-m1-warps8-component-positive.md`);
- W13-N32 on the eight-warp base: `22.246154%` median matched reduction,
  worst cell `21.551557%`, all eight layer/rank cells exact
  (`notes/2026-09-02-moe-m1-w13-n32-xpu-graph-confirmation-a2-result.md`).

The map is therefore one integration unit; A56 attributes any endpoint change
to "the tuned M1 map". If A56 is positive and attribution between the two
deltas is wanted, a later arm may select `configs/moe-warps8-m1` alone.

Expected magnitude: the W13 path costs about `48 x 215 us = 10.3 ms` per
target token on the eight-warp base; a 22% cut is about 2.3 ms/token, roughly
4% of A55's `52 ms/token` (19.07 tok/s). The eight-warp delta adds an
unmeasured endpoint share. Three short rows have historically spread 9%
between fastest and slowest, so a positive A56 is a direction signal, not a
promoted rate; losslessness gates are the binding result.

## Derivation and identity

`tools/rewrite-q38-a55-to-a56-w13-n32-map.py` derives A56 from the frozen A55
files (launcher `acc6c559...`, client `d3289f93...`, supervisor
`ada6baf2...`, host wrapper `e70543b3...`). Renames are attempt `55 -> 56`,
port `19727 -> 19728`, and the corresponding run/cache/compile/RPC/temporary/
supervisor/lifecycle paths, applied outside 40/64-hex identity tokens (the
oneCCL kernel hash contains the substring `a55` and is preserved verbatim).
Content changes, and nothing else:

- launcher: static map hash `a8f1f8982e3e1af80ff31b9e0a00afaacf1af1b3c401585109b4d60d3c8267be`,
  key-1 shape check (eight warps, `W1_CONFIG.BLOCK_SIZE_N=32`, no
  `W2_CONFIG`), the `VLLM_TUNED_CONFIG_FOLDER` export beside the frozen
  server exports, two identity receipts (`tuned_config_folder`,
  `tuned_config_map_sha256`), and derived-source assertions for all three;
- client: the A55 "tuned folder must be absent" check becomes "exactly this
  folder must be present"; the map hash and Codex's selection verifier
  (`a464b0f6...`) are rechecked and the verifier is executed against the live
  vLLM source and the prerequisite patch into
  `moe-m1-w13-n32-selection-receipt.json`, which must prove key 1, W13
  N32/eight warps, W2 N64/eight warps, and M2--M512 preservation; the two
  identity tokens are required in `identity.txt` and written into the summary;
- supervisor: a valid stop additionally requires the two identity keys;
  wrapper/client hashes are re-pinned;
- host wrapper: the supervisor hash is re-pinned.

Everything else is A55: external checkpoint and tokenizer, model revision
`bcd9f01d...`, vLLM `cbc3cb58...`, kernels `e4218899...`, stage build
`2f829747...`, TP4/EP4, MTP0, synchronous PLE-only UVA placement, full decode
graph `[1]`, public oneCCL `twoshots` with its pinned library/kernel hashes,
2304 max model length, 128 MiB KV, the recovery canary, the 6/7 semantic
boundary, 16/16 short repeat, exact-2K needle with cache zero, the three
p146/o256 short rows, both exact-2K depth rows, the protected short output
hash `5f407446...` and exact-2K token hash `5fd297f7...`, the host guards
(swap off, ASPM performance, 120-million/16-million KiB floors, 64 corrected
local-NVMe events, zero root-port events, 16,777,216-sector local read cap),
teardown, and four-card postflight. No reboot or per-boot load rule applies.

## Frozen packet

- rewrite helper: `tools/rewrite-q38-a55-to-a56-w13-n32-map.py`;
- launcher `dfd7d0671c70a45be5b270800c5d033a521876124b109086b027f0fbdd8bdce0`;
- client `ed23aa1e34216445a64228f64025b679d18167dd240e75f301e6860297f037c5`;
- supervisor `f5f59dba379b36ec9f7e3252bf81fb04466d8aee6a7c23138b6fe04db64dc131`;
- host wrapper `85bdae253355a33f5e22b53264079601527cea0bb0adf6e7de3113691dfe1a1a`;
- derived launcher `b6cae5abedbe8052fc776be7d0648e58c72a2d9e5da073e03b791e32d1462dd3`.

Static validation: rewrite idempotent; `Q38_A56_VALIDATE_ONLY=1` launcher
passes with the export and both receipts present in the derived script; host
wrapper static identity passes; client and supervisor parse. The selection
verifier was exercised once outside the packet under the server's runtime
identity (stage PYTHONPATH and library path, `VLLM_TARGET_DEVICE=xpu`) and
produced a passing receipt: key 1, W13 N32/eight warps, W2 N64/eight warps,
M2--M512 preserved. Without that runtime identity vLLM resolves an
unspecified platform and the resolver cannot name the device, which is why
the client mirrors those exports around the verifier call.

## Preconditions and acceptance

- Gen4 root-NVMe clearance receipt validated in this boot;
- no other B70 process; the two HC component gates and the W13 config-folder
  qualification finish first;
- run as `sudo run-q38-a56-host-controlled.sh`.

Pass: valid supervisor stop with all A55 gates plus the two new identity keys
and the selection receipt. The short-row median is reported against A55's
`19.071017 tok/s` and A44's diagnostic `20.507849 tok/s`. Any hash mismatch
fails closed and the map does not advance. Protected results remain unchanged.

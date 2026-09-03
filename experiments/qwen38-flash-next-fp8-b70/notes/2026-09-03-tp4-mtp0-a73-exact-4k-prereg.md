# Qwen3.8 Flash-Next FP8 A73 exact-4K preregistration

Date: 2026-09-03
Status: frozen before launch; the intended promotion record of the
deterministic full-decode-graph line at 4352 served tokens

## Question

The deterministic graph identity (overlay head `2169dbfe...`,
`VLLM_XPU_MKLDNN_DETERMINISTIC=1`, public oneCCL twoshots, tuned M1 W13-N32
map, `FULL_DECODE_ONLY` size 1) passed the complete frozen client on three
2304-token servers (A70-A72; exact-2K `afffd2110812...`) and was logit-exact
through 4096-token prefill on two 4352-token servers (A76, A77; exact-4K
continuation `c6193cc6c9a1...`, 2K continuation again `afffd2110812...`).
Does one 4352-token server of that identity pass the entire frozen client,
including two exact-4K rows, with both depth hashes pinned to the
deterministic line's own two-server values?

## Authority policy applied

The 2026-09-03 decision memo's option (a): the deterministic line carries
its own authorities (2K `afffd211...`, five servers; 4K `c6193cc6...`, two
servers). The native-line records (`5fd297f7...` at 2K, `1d833e5f...` at 4K,
both from a server class since shown to be logit-jittery) stay in place,
unchanged and unreplaced; every summary this attempt writes is marked
additive with `protected_results_changed: false`. The user's stated
standard for new work (lossless, deterministic, reproducible by a third
party) is what this policy implements; if they prefer option (b), this
attempt's record is still valid as a deterministic-line screen.

## Design

`tools/rewrite-q38-a77-to-a73-exact-4k.py` derives A73 from the frozen A77
packet (server byte-identical apart from attempt 73 / port 19745 paths).
Client changes, all in the frozen client and hash-pinned by the supervisor:

- the exact-2K rows state the served capacity (`--context-capacity 4352`;
  the request payload and its hash `3aa1bba4...` do not include it);
- two exact-4K rows follow (`--depth 4096 --context-capacity 4352`, 1500 s
  bound, fixture case `aedf2eb7...`, payload `2d92a285...`, usage
  4096/128/4224, cache zero, finish `length`);
- the served KV cache must cover 4224 tokens (the metrics check rises from
  2176);
- the summary gains an `exact_4k` section and pins
  `c6193cc6c9a1553f56d7ce78faea9c8bfa628a67fcea229b1c99279a149f6639` on both
  rows next to the 2K pin; the gate line names `exact-4K-repeat`.

Everything else (recovery canary, 7-case quality suite with 16-repeat and
exact-2K needle, three short rows, runtime receipt with size-1 FULL
dispatch count) is the A72 client unchanged. Packet: launcher
`867584a8...`, client `24ac1167...`, supervisor `3e5bce30...`, host wrapper
`add9c0a0...`. Expected cost: about 15 minutes to serve, about 10 minutes of
client.

## Reading

- `client-gates-passed.txt` naming `exact-4K-repeat`, receipt with
  `size_1_full_dispatch_count > 0`, and the same outputs as A70-A72 on every
  shared gate: the deterministic line has a promotable 4352-token record
  (short center from this attempt's three rows; exact-2K and exact-4K rows
  with two-server hashes). A fresh-server repeat (A78) then makes it a pair.
- Any depth hash other than the pinned values: the line is not
  server-independent after all at that depth; investigate before any
  promotion.
- Any short-row or quality difference from A70-A72: the served capacity
  changes an output (it must not; the 2K needle and the 2K rows already
  matched at 4352 in A76/A77).

Nothing protected changes.

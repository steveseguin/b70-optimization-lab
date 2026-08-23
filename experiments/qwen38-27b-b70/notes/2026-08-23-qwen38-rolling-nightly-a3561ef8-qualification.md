# Qwen3.8 rolling-nightly `a3561ef8` TP-scale qualification

Date: 2026-08-23. This note characterizes the current upstream development
base. It does not lower or relabel the pinned `e9d1398d9` frontier.

## Outcome

The stock current rolling XPU nightly is quality-qualified at every valid
target-only topology, but it is not a wholesale performance replacement for
the pinned image. TP1 established a small new diagnostic high while both strict
repeats were about 0.22% slower. TP2 was 0.37% slower diagnostically and 1.08%
slower strictly. TP4 produced one 71.9002 strict high, but an exact same-cache
repeat fell to 71.2457; the high is preserved as a valid capture, not promoted
as a replicated record.

| TP | New diagnostic tok/s | Old diagnostic reference | New strict tok/s | Old strict reference | Frozen result |
|---:|---:|---:|---:|---:|---|
| 1 | **30.329809** | best 30.2569 | 30.241645 / 30.243714 | 30.310675 | diagnostic high; bounded strict regression |
| 2 | 48.647592 | floor/best 48.8301 / 48.950459 | 48.490490 | 49.019651 | bounded diagnostic and strict regression |
| 4 | 71.344049 | floor/best 71.5488 / 71.6741 | 71.900199 / 71.245742 | 71.293263 / 71.398430 | quality-green but performance-variable; high did not replicate |

The old `30.2 / 48.9 / 71.7` diagnostic values and strict
`30.310675 / 49.019651 / 71.293263-71.398430` values remain the certified
rollback/comparison frontier. No LocalMaxxing submission was made.

A separately preregistered TP4 preservation overlay then seeded only 152
hash-matched historical Triton winner decisions into a fresh current-runtime
compile. Its diagnostic arm reached `71.722545 tok/s`; exact-cache strict A/B
reached `71.352872 / 71.454271 tok/s`. Both strict arms cleared the frozen
`71.293263` floor and B cleared the `71.398430` high bar, so the exact
`a3561ef8`-plus-overlay profile is accepted as stable full recovery. Report it
as the observed strict range; `71.352872` is only the lower endpoint of these
two replays, not a guaranteed floor. The stock and pinned profiles remain
separate and unchanged.

## Immutable identities and transferred overlay

The current image is repository digest
`sha256:d3f5daa1552a231471a5ec5097475d282e07788db336819ed9e932f9193b0e35`,
linux/amd64 manifest
`sha256:ad7d8e8ef69e3dcc1ad08339b12c0c118bf98b9602b89f66aa5efc236e1df41a`,
and vLLM source `a3561ef8e49d3545c4078df43444beb4c98ae124`. The
pinned comparator is source `e9d1398d9edfd90fcc1cf783805240e3effec013`
with recorded image identity
`sha256:bc979d1ba312dc8a666c57a40205f35d7fc5d96b2f7450c2c77f5b3d5243f0e0`.

The pinned graph column used a stock image, not a hidden source patch. The
complete performance overlay was carried forward: identical model/revision,
INC W4A16, MTP0, F16 KV, 32K, one sequence, 1024 batched tokens, prefix cache
off, FULL+PIECEWISE graph capture, oneCCL sockets, device/IPC/shm mounts,
`ZE_AFFINITY_MASK` only, 0.90 memory utilization at TP1/2, 0.60 at TP4,
fresh per-topology ext4 caches, and the same suite/metric/quality contracts.
Effective engine configuration and server arguments matched apart from the
served-model alias and the runtime package/source identity.

## Correctness, quality, and cache gates

Every diagnostic and strict arm had 25/25 eligible rows, returned token IDs,
cached tokens zero, exact code-14 canary, `quantization=inc`,
`enforce_eager=False`, and completed PIECEWISE plus FULL graph capture. Direct
and ordinary reads verified all 19 model files before every boot.

The strict quality arm at TP1, TP2, and TP4 passed:

- seven of seven exact/objective cases;
- eight of eight same-server repeat hashes;
- the requested 8K needle at 7,617 actual prompt tokens;
- all 24 nonempty baseline comparisons;
- cache zero on all 16 quality requests.

The replay manifests were byte-identical before and after benchmark/quality:

| TP | Files | Manifest-file SHA-256 |
|---:|---:|---|
| 1 | 1,097 | `fd397d219af8a9e0a098e19744ce286913eeef16da29fd8c48bd0958f5ef5bf9` |
| 2 | 2,277 | `f9ec035fee46d360bb1297a5736704b067aa044c9f6b7e0490bb43b24def1eb7` |
| 4 | 4,421 | `86273698225e57c89f3f8ab26e4ab346985f468141515c34f9164f2f294ffd1c` |

After the stock qualification and TP4 winner mapping were sealed, the live
TP4 compile cache was archived to the USB evidence store as
`tp4-default-cache.tar`. GNU tar comparison passed, source and archive both
contained 5,270 entries, and the 648,949,760-byte archive verifies as SHA-256
`805ef3bbe8089ec929e4fd38eaa1fad7d1fa1b749d279fd6cf7453649fd2f0f9`.
Only the exact live cache was then removed to create safe headroom for the
separate TP4 overlay compile; raw roots and the manifest above remain intact.

After the TP4 overlay's three-arm program closed, its live current-runtime
cache was also archived as `tp4-autotune-winner-cache.tar`. GNU tar comparison
passed, source and archive both contained 2,678 entries, and the 635,105,280-byte
archive verifies as SHA-256
`0a768ca0050521663f465dcf2d7d0fca321f44a57be0507eac742758a0a33ae1`.
The raw roots, tracked 152-file overlay, and archive remain recoverable after
the exact live ext4 cache was removed.

## Performance and output stability

TP1 strict A/B were nearly identical in speed, and the old run was faster on
25/25 and 23/25 paired prompts respectively. TP2 strict was slower on 25/25
paired prompts. These are bounded `a3561ef8`-runtime regressions, not a single
median outlier.

TP4 strict A beat the old replay on 21/25 paired prompts, but strict B on the
same immutable cache was 0.91% slower than A and slightly below the old best.
That failure to repeat blocks record promotion. It also shows why captured
highs and replicated floors must remain separate fields on the website.

The historical-winner overlay changed that repeat classification without
discarding the stock data. Its strict pair spans `71.352872-71.454271 tok/s`
(`0.1421%`), with B faster on 15/25 paired prompts. Replay A ran the full
quality battery; replay B ran the preregistered canary, benchmark, model, and
cache checks. This passes the frozen stable-recovery rule, but it does not beat
the stock `71.900199` single capture or make that capture replicated.

Exact output nondeterminism persists even with unchanged cache contents. TP1
stock strict A/B matched completely on 19/25 prompts, and TP4 stock strict A/B
also matched on 19/25. The TP4 overlay strict A/B pair matched completely on
20/25. First-100-token agreement was 24/25 in all three comparisons. The
existing cross-run nondeterminism disclosure remains mandatory. Multi-GPU XPU
Graph is also still reported by the runtime as
experimental/single-GPU-supported.

## Why speed moved and how it will be recovered

The 18 intervening vLLM commits did not change the compiled Qwen computation
graphs. Old and new caches have matching model code hashes, compiler hashes,
normalized cache-key environment, byte-identical graphs, and identical Triton
candidate sets/config hashes. The selected autotune winner changed in 20/38
TP1 records, 46/78 TP2 records, and 78/152 TP4 records.

`VllmConfig.compute_hash()` includes the vLLM package version, so the routine
nightly version bump invalidated the outer compile namespace and forced a new
autotune even though the graph-relevant inputs were unchanged. The subsequent
bounded test kept the then-current upstream and carried forward only the 78 historical
TP2 `.best_config` decisions under fail-closed graph/compiler/environment and
candidate-hash gates. It compiled all binaries and AOT artifacts fresh.

That overlay raised the `a3561ef8`-runtime diagnostic from 48.647592 to 49.058940
tok/s and the strict result from 48.490490 to 49.009352 tok/s. Full quality and
cache immutability passed. The strict result nevertheless missed the frozen
49.019651 historical gate by 0.010299 tok/s, so the result is a
quality-qualified partial recovery rather than a promoted replacement. See the
[overlay closure](2026-08-23-qwen38-tp2-autotune-winner-overlay-result.md).

The same fail-closed mechanism at TP4 transferred 152 decisions and compiled
all current-runtime code and binaries fresh. Fresh diagnostic improved from
71.344049 to 71.722545; the exact-cache strict pair of
71.352872 / 71.454271 passed the preregistered historical floor/high rule and
full replay-A quality. That exact overlay profile is accepted. See the
[TP4 overlay closure](2026-08-23-qwen38-tp4-autotune-winner-overlay-result.md).

## Frozen disposition

- Keep `a3561ef8` as the active development base.
- Keep all pinned diagnostic and strict frontiers unchanged.
- Treat all TP1/2/4 newest arms as quality-qualified runtime profiles.
- Accept the exact `a3561ef8` TP4 historical-winner overlay as a separate
  stable profile with an observed strict range of
  `71.352872-71.454271 tok/s`; remap and requalify it on a newer nightly.
- Promote the TP1 diagnostic high only within its exact current-runtime
  identity; do not use it to rewrite the strict result.
- Preserve TP4 71.9002 as a captured high, not a replicated record.
- Do not mutate the old 96-cell matrix. It remains complete for its pinned
  image; newest-code sentinel probes are a separate matrix version.

The compact structured packet is
[`2026-08-23-qwen38-rolling-nightly-a3561ef8-tpscale.json`](../data/2026-08-23-qwen38-rolling-nightly-a3561ef8-tpscale.json).

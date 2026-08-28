# Qwen3.8 Flash-Next TP4 MTP0 current-runtime anchor preregistration

Date: 2026-08-28

## Purpose

Fill two useful website cells with measured current-runtime evidence in one
bounded boot: TP4/eager/MTP0 at short context and exact 4K. This is additive.
It cannot replace, lower, or relabel any legacy-runtime speed, MTP result,
estimate, or published claim.

The boot also closes the post-MTP2 recovery gate before measurement: the base
launcher must pass its exact four-rank collective, then the client must return
the frozen cache-zero `OK` canary before quality or timing begins.

## Frozen identity

- model revision: `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`
- local model: `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`
- vLLM: `1372c62d975c554f4b465c8299bc5f3295301ceb`
- XPU kernels: `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`
- staged runtime build: `2f829747503c77d4814834dffd0840fb1dd9f75a`
- TP/EP: `4/4`; eager; graph off; MTP0
- max model length: `4352`; max sequences: `1`; max batched tokens: `64`
- KV cache: `201326592` bytes, BLHNC; prefix cache off
- selective UVA placement: 12.25 GiB/rank, PLE/input embeddings
- async scheduling off; reasoning parser absent; diagnostics absent
- attempt: `3`; port: `19672`; every run/cache/compile/RPC path must be new

The unchanged base launcher is SHA-256
`62b40c9268a665727ff3946a621e4fcd2db072ed0bd4595dde7a6a006083ccb7`.
The fixed wrapper, supervisor, and client are respectively:

- `0461ac7400043a6738ed69b663a6e9098278125abcdaf8b572fa7a5ef7ce7d6f`;
- `699ca16fc7e104c3891ca025df520cc5a17707b560d2f74262ba63032e48c0d3`;
- `683bdbe3913d798866d612b178c50b0ad8bc59dc556f09706f100e2c9c6a7888`.

The supervisor lifecycle is bounded at 10,000 seconds. The client refuses to
begin unless at least 4,800 seconds remain, so a slow boot cannot strand an
incompletely bounded measurement sequence.

## Ordered gates

1. Fresh four-rank preflight and healthy exact server identity.
2. Exact `OK` recovery canary: normal stop, 17/2/19 usage, both cache counters
   zero, frozen output hash.
3. Direct-answer quality: seven semantic cases, 16 fixed repeats, and exact
   4,096-token needle. Accept 7/7, or the already known 6/7 only when the sole
   miss remains `code_execution=30`; require one repeat hash, complete usage,
   zero cache counters, and the exact needle. Any other change stops timing.
4. Three immutable established p128-requested/p146-actual, o256, c1 rows. The
   first invocation performs one conditioning request before its measured row;
   rows two and three use no warmup. Require exact 146/256/402 usage
   and one established output hash. The legacy harness does not retain cache
   detail or finish reason, so those are not claimed for these rows.
5. Two exact p4096/o128 requests through the frozen exact-depth fixture.
   Require every structural gate, exact usage, cache zero, length stop, 128
   returned IDs, frozen prompt/payload hashes, and identical output-token hashes.
6. Controlled stop followed by no listener/process/scratch residue, four-card
   discovery, under-256-MiB idle memory on every card, and no B70-addressed
   event in the run journal.

Frozen helper hashes are:

- direct quality: `8e18afee22a0fda4b44583ca55e3a43aef5f86fe8387a1bd28c533d1534bd3de`
- short benchmark: `d590c63c87b1e664417b4198dbbb873cbe4f252509fa8f9fc50830efca2b4cf4`
- exact-depth benchmark: `8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067`
- exact-depth fixture: `c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d`

## Interpretation

All gates plus clean teardown permit Grade-C lab-screened current-runtime
TP4/eager/MTP0 short and exact-4K coverage. The two 4K requests establish
same-boot repeat evidence only. A failed gate is a bounded negative with its
artifacts preserved; all existing website rows and speed records remain
unchanged.

## Attempt 3 closeout

Attempt 3 reached a healthy exact server after the four-rank preflight. Local
NVMe checkpoint loading took 73.67 seconds versus 552.92 seconds in the prior
external-disk quality run. Before the recovery canary or any model request,
the client rejected the live supervisor because it had been invoked with a
relative path while the check expected an absolute path. The failure sentinel
performed the intended controlled stop. Final supervisor rc was 143; journal
read rc was zero; all four cards returned to 42.88 MiB; no listener, server,
worker, scratch path, or B70-addressed event remained. This is a no-request
harness negative and grants no quality, speed, matrix, or recovery-canary
credit. Attempt 4 supersedes only the supervisor-path check and uses fresh
paths and a fresh port.

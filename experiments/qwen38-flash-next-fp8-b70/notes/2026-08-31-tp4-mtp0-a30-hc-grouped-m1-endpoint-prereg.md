# Qwen3.8 Flash-Next FP8 A30 grouped-HC plus M1 endpoint preregistration

Date: 2026-08-31
Status: frozen before GPU launch

## Question

Does the component-qualified grouped HyperConnection up-projection path,
combined with the already-qualified production-M1 MoE eight-warp map, improve
the TP4 target-only decode lane while preserving its complete short and exact-
4K quality, repeatability, and authority contract?

## Frozen identity

- checkpoint: `Qwen/Qwen3.8-Flash-Next-FP8` revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`, read from local NVMe;
- vLLM: `797769b34b6db5c934609b75dc04cc61ec66e5f9`, exact clean checkout;
- kernel workspace head: `eeee7d671abfa964626baa18da2174bb92cac80a`,
  exact clean tracked state and frozen five-commit chain;
- full-serving hybrid stage:
  `/mnt/fast-ai/qwen38-build/runtime-serving-hcgrouped-eeee7d6-a2`;
- stage native head: `eeee7d671abfa964626baa18da2174bb92cac80a`;
- stage retained 15-file base head:
  `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- stage manifest SHA-256:
  `a4e83ec34d91b70a666dc170fcc3bda75562592c58fce198f29cfa4d25755d0d`;
- A4 qualification-manifest SHA-256:
  `ca218488129510e0bc29175f96fd17f0572ecbc2e0f7913ce3c576d25b5b3591`;
- TP4/EP4, PP1/DP1, eager/graph-off, MTP0, seed `20260609`;
- synchronous selective PLE-only UVA placement, 12.0 GiB offload budget;
- maximum model length 4,352, maximum sequences 1, maximum batched tokens
  64, scheduled-token override absent, and KV cache `134217728` bytes;
- prefix cache, asynchronous scheduling, async PLE, tracing, and profiling
  disabled;
- attempt `30`, port `19702`, with isolated run, cache, RPC, compile, and
  supervisor-evidence paths.

The stage has already passed accepted/candidate schema closure, 5/5 grouped-HC
tests, 25/25 Qwen configuration tests, two fresh 6,400-call GDN histories, the
real-weight M1 MoE receipt, TP4 device/collective repeatability, journal, and
loader closure. That qualification permits this endpoint test; it is not an
endpoint result.

## Treatments and attribution boundary

A30 derives from the complete frozen A29 launcher/client/supervisor chain. It
retains A29's official M1 resolver receipt—requested M1, selected key 1,
effective `num_warps=8`—and adds only the default-off
`VLLM_XPU_QWEN4_EXP_HC_GROUPED_UP=1` selector with the qualified full-serving
stage and their exact source identities. The selector is exported after the
inherited environment scrub, asserted through vLLM's environment registry, and
proved again from the live server process. Source, stage, patch, manifest, and
qualification identities are checked before the boot marker and immediately
before `vllm serve`.

Relative to the protected endpoint baseline this is a composite M1-MoE plus
grouped-HC candidate, not a causal single-variable result. A passing A30 run
may establish that the combined deployment is reliable and faster. Attribution
and promotion still require a separately booted same-stage flag-off control
followed by a fresh flag-on repeat, all with the same battery. The matched
control must retain the M1 map so the grouped-HC delta is isolated. No later
control may lower or overwrite a protected result.

## Required endpoint gates

The inherited A29 battery is unchanged:

- recovery canary and the accepted seven-case semantic boundary;
- 16-repeat exact-output check;
- three short decode rows with protected output SHA-256
  `5f40744644b98ddd58a0c202fe855af324c0b1c33e1a6275afd74c12488f89f0`;
- cache-zero exact-4K needle;
- two exact-4K rows with protected output SHA-256
  `1d833e5f463366223a669aa15495840d1337b173e675a9ea04f00a5ae339d5cc`;
- repeat authority SHA-256
  `3b0b3192cd70de9c19caf7a6f6f69a4dda63cc4e66049c2cf9c15633103896b7`;
- exact live source/config/stage receipts, bounded journal window, and clean
  teardown; the postflight also rejects any new internal-NVMe
  `nvme 0000:01:00.0:` journal event during the supervised window.

Any quality, output, repeat, identity, lifecycle, or evidence failure is a
bounded negative. A quality pass whose short median does not exceed the
protected `5.515783 tok/s` MTP0 result is not a speed win. A faster quality pass
is candidate evidence only until the matched control and fresh repeat close
attribution. The approximately `20.727 tok/s` MTP4 result is a separate mode
and remains unchanged.

## Frozen tools

- launcher SHA-256:
  `19ea4096d8de475ea40738b8d0c2bde006c6e660a653e93d010a56717aff094e`;
- generated outer launcher SHA-256:
  `fe815b8419a60ba24bc9a2f21182fc3b780bb40e22885358c2eed53782f21e95`;
- generated inner launcher SHA-256:
  `8733a114124632c3fe47edaefac261f57e4999d1af211152f79a0ca8a29758f0`;
- client SHA-256:
  `71387d4df1f9c5fa2527cd301a8a8992a8ef370cae418eb83e5a44ca56814b07`;
- generated client SHA-256:
  `116ddf13fff1a556565b98484ebcb78724d30d56ad9a82d9fcebbf72dbcdd703`;
- supervisor SHA-256:
  `c5a8490f801616844ecf0ef7517879e414e2577369cf70753e7884943d8b91b1`;
- generated supervisor SHA-256:
  `4a498eceb1d6797598dd28b2a01efe554a45fd691553556f015f6370ff7666db`;
- rewrite helper SHA-256:
  `b68ce87cdd3403e4a7ac246c6c9580e420a5492ab4c91e42b9ea15ef19d229d4`;
- static contract test SHA-256:
  `1d0ec20c0d69ccd80919147cab85545fdd6eb3407cd5c133f03b0056f7f8387d`.

Six static contract tests, shell parsing for all four generated sources,
validation-only derivation, Ruff, Python compilation, and diff checks pass.
Validation-only execution does not claim the one-load boot marker or create
attempt-30 runtime paths.

## Current boot note

The preceding boot ended uncleanly overnight while no A30 or full-model
process was running. Its journal has no orderly shutdown or fatal/OOM record;
it does contain earlier hardware-corrected receive errors for the internal
NVMe PCIe endpoint, which are correlation evidence rather than a proven reset
cause. The current boot has the correct mounts, full free swap, sufficient RAM,
no model process, and no consumed full-load marker. A30 therefore needs no
additional reboot, but its normal preflight must pass immediately before any
launch.

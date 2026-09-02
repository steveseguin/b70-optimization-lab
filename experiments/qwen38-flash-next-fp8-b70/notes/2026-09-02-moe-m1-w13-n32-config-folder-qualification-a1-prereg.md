# Qwen3.8 Flash-Next FP8 W13-N32 config-folder qualification A1

Date: 2026-09-02
Status: frozen before component execution

## Question and boundary

This bounded component run asks whether the A2 W13-N32 result survives the
real deployment selection mechanism. It does not inject a free-form launch
configuration: every fresh process sets `VLLM_TUNED_CONFIG_FOLDER`, invokes
the live vLLM tuned-map resolver, records the selected map and phase configs,
and only then runs the unchanged A2 real-weight component gate. It performs no
full-model load, endpoint request, reboot, or serving promotion.

## Frozen design

- model revision `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- vLLM `cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9`, kernels
  `e421889999bc1e5a5f11044d14548b9afdba644d`;
- layers 0 and 47, EP ranks 0--3, seed `20260827`;
- eight cells, each in fresh sequential control/candidate/control processes;
- 100 changing eager/captured inputs per process;
- controls select `configs/moe-warps8-m1`; candidates select
  `configs/moe-m1-w13-n32`;
- exact base/candidate map hashes
  `91e5d8b692da3febbba7cb07ee4fdab319909da0c82c1fda95b92dc42d680464` /
  `a8f1f8982e3e1af80ff31b9e0a00afaacf1af1b3c401585109b4d60d3c8267be`;
- every process must receipt key 1, W2 N64/eight warps, and either control W13
  N64 or candidate W13 N32 through the actual resolver.

The A2 health, four-shard checkpoint receipt, root-NVMe clearance, exclusive
cache, process teardown, journal capture, and no-clobber gates are retained.
New evidence is written only to
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260902-moe-m1-w13-n32-config-folder-qualification-a1`,
with a new tmpfs cache, lock, and derived-runner path.

## Frozen acceptance

All 24 exits and all 24 folder-selection receipts must pass. All eight cells
must preserve A2 eager/graph and control-authority equality across all 100
inputs. Control drift must be at most 2%; median matched reduction at least 3%;
at least 7/8 cells must be positive; no cell may regress by more than 2%.
Failure preserves partial evidence and authorizes no endpoint arm.

## Frozen implementation hashes

- runner: `06141adafb320f3eb7386fcddb31ba9a467931c8076111b89a2b33f139ff40a0`;
- derived runner: `656524e10a2f86cc064502156f37ab3423fd16ff3c089ceae1671dc58f520e25`;
- in-process folder adapter: `ec9e8c3f1f99605d1a75bd93c1aa833aada18f4eef9d38d504eaf78ec5fff950`;
- summarizer: `52e798b94836bc50d91266f5a6eda4d10edab76bec4fc6789203a1dad860163b`;
- CPU/static tests: `242b5fdbf8d173284541f8aad78d095f0766d084016ae37b8a384122614349d8`.

Six focused tests pass, plus Ruff, Python compilation, shell syntax, and the
runner's no-GPU validate-only gate. Protected results remain unchanged.

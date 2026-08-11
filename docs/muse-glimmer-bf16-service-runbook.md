# Muse Glimmer 30B BF16 Fleet Runbook

Production service since 2026-08-10. Lossless BF16 target with DFlash
speculative decoding; two replicas, each spanning two B70s, single slot per
replica. Selected because BF16 accepts future fine-tuned/abliterated
checkpoints directly (convert to BF16 GGUF, same pipeline, gate with
byte-exact replay) and is the deterministic exact-replay identity.

## Endpoint

```text
http://<server-lan-ip>:8000/v1     model: muse-glimmer-30b-bf16    auth: none
modalities: text + image (vision canary validated)
concurrency: 2 active generations (one per replica); sticky routing via
X-Agent-Id / X-Session-Id / X-Sticky-Mode: strict or JSON user/session_id
context: 65536 tokens per request
```

Backends: `127.0.0.1:19470` (GPUs 0+1), `127.0.0.1:19471` (GPUs 2+3).

## Identity

- Target: `/mnt/usb-models/muse-glimmer-30b-extra/Muse-Glimmer-30B-BF16-0000{1,2}-of-00002.gguf`
- Drafter: `dflash-kquant.gguf`, `n_max=5 p_min=0.1`; vision:
  `mmproj-Muse-Glimmer-30B-BF16.gguf` (both on NVMe)
- Runtime: `/home/steve/src/llama.cpp-muse-glimmer` upstream `030ebb558`,
  SYCL AOT bmg-g31 build, version 10358, clean master
- Measured: ~9.85 tok/s no-spec; with DFlash 22.6 prose / 33.6 code /
  30.0 json per replica; c2 aggregate ~57 tok/s wall
- VRAM: ~32.1 GB on cards 0/2 (weights half + mmproj + drafter), ~28.6 GB
  on cards 1/3. Card 0/2 headroom is thin; vision encode validated at
  224x224, but watch OOM if image sizes grow

## Exactness properties (validated 2026-08-10)

- Per-backend byte-exact repeats (greedy, cache off): PASS
- Cross-replica identity (same request to both backends): byte-equal
- DFlash vs no-spec: byte-exact on code/json classes; prose flips within a
  small near-tie variant set (k-quant drafter in loop)
- Prompt-cache reuse changes numerics: run all gates with
  `cache_prompt: false`; production keeps the cache for TTFT
- Tiny images (<=24px) degrade perception (patch-14 ViT); use real sizes

## Operate

```bash
sudo bash scripts/install-muse-glimmer-bf16-service.sh --start   # install/start
scripts/muse-glimmer-prod-health.py --base-url http://127.0.0.1:8000 \
  --model muse-glimmer-30b-bf16 --output-json data/muse-health-$(date -u +%Y%m%dT%H%M%SZ).json
journalctl -u muse-glimmer-bf16-fleet.service -f
journalctl -u muse-glimmer-frontdoor.service -f
ls -t /mnt/fast-ai/bench-results/muse-glimmer-30b/servers/prod-bf16-*.log | head -2

sudo systemctl disable --now muse-glimmer-frontdoor.service muse-glimmer-bf16-fleet.service   # stop
```

Units conflict with the Gemma quad services and older :8000 frontdoors; the
install --start path stops those first. Gemma remains restorable via
`docs/gemma4-26b-q8-service-runbook.md`.

Note: gemma4-26b-prod-health.py is NOT valid against this model (its token
budgets starve reasoning output); use muse-glimmer-prod-health.py.

## Swapping in a fine-tuned/abliterated checkpoint

1. Convert the new checkpoint to BF16 GGUF (llama.cpp convert script).
2. Point `MODEL` in `scripts/serve-muse-glimmer-bf16-fleet.sh` (or the
   systemd Environment) at the new 2-part GGUF; keep drafter and flags.
3. Restart the fleet unit; run `muse-glimmer-prod-health.py`.
4. Gate: greedy byte-exact repeat per backend, cross-replica identity,
   plus your own behavior canaries for the tune. The DFlash drafter needs
   no retraining - it only proposes; the new target's verification keeps
   outputs faithful to the new weights (acceptance/speed may shift).

## Known limits / next levers

- Prose-class DFlash exactness gap -> BF16 drafter conversion (needs a fit
  rebalance; drafter no longer fits card 0/2 as-is).
- Alternate high-throughput fleet (4x single-card kquant-dynamic + dflash,
  ~109 tok/s aggregate at 0.2% degradation) is measured and can be wired
  as a switchable profile; see
  `experiments/muse-glimmer-30b-b70/sweeps/20260810-fleet-frontier-decision.md`.
- k-quant batched-verify kernels and cross-card drafter mirroring are the
  deferred source-work unlocks.

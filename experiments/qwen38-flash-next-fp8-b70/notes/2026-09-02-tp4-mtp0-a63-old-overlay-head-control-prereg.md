# Qwen3.8 Flash-Next FP8 A63 old-overlay-head control preregistration

Date: 2026-09-02
Status: diagnostic; frozen before launch; no promotion claim possible

## Question

A62 (eager, bundled oneCCL, tuned M1 map) still returned different
first-step logits for identical 8-token prompts (spread 0.2173 nats over
eight repeats) and different 128-token outputs, so the decode graph and the
public oneCCL preload are both excluded. The last server proven bit-exact
across fresh starts (2026-08-28, 2K and 4K authorities) ran the vLLM overlay
at `1372c62d975c554f4b465c8299bc5f3295301ceb`; every later arm runs
`cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9`, 18 overlay commits later
(bounded PLE offload waits, PLE shard filtering, the QSA selection
determinism change, opt-in UVA prefetch, HC grouped-up integration, the
per-phase MoE config door, traces). Is today's jitter a regression inside
those commits?

## Design

`tools/rewrite-q38-a62-to-a63-old-head.py` derives A63 from frozen A62 by
(a) deleting the launcher's head override so the eager base's native pin
`1372c62d...` applies, and (b) deleting the tuned-map folder export, its
static hash checks, receipts, and assertions, because the per-phase resolver
and the nested `W1_CONFIG` map key do not exist at the old head. Everything
else is A62: eager, bundled oneCCL, external checkpoint, PLE-only UVA
placement, 2304 max model length, 64-token chunked prefill, Torch trace,
host guards, staged kernels `2f829747...`. Attempt 63 / port 19735; names
carry `oldhead`. Packet: launcher `f657dcae...`, client `6449d16c...` (hash
pin only), supervisor `eaba88cf...`, host wrapper `9160ddf4...`.

Operational steps: after the Codex read-only source audit has exited and
the GPUs are idle, `git -C /home/steve/src/vllm-current-main checkout
1372c62d975c554f4b465c8299bc5f3295301ceb` (detached, clean tree), launch
A63 detached, run the unchanged logprob probe (`--depths 8,64,256,2048`),
then `git -C /home/steve/src/vllm-current-main checkout cbc3cb58...` before
any other arm. The overlay is a plain source checkout, not a lab branch.

## Reading

- Bit-identical first steps and identical 128-token repeats at every depth:
  the regression is inside the 18 commits; bisect with the same packet
  (about four more server loads).
- Same jitter: the source lies below the overlay (staged kernels, Torch/
  Triton/oneAPI runtime, driver/GuC, or the model's kernels as they always
  were); the 2026-08-28 exactness must then be re-examined for margin luck,
  and Codex's kernel audit becomes the primary guide.

No speed is claimed. Protected results remain unchanged.

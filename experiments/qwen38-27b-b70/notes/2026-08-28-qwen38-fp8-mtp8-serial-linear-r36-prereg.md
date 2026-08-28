# Qwen3.8 FP8 MTP8 packed-linear R36 diagnostic preregistration

Date: 2026-08-28

R35 made a static-MTP1 `risk-register` sentinel exactly match all 512 tokens
from the qualified target, with both serial GDN markers reached, but dynamic
MTP8 still first diverged at token 128. The nine-row verifier pack therefore
still has at least one shape-dependent operation outside the now-serial
Gemma RMSNorm and GDN transactions.

R36 tests one mechanism: for block-FP8 linear calls whose active input is
exactly the nine rows of an MTP8 verifier pack, replay the unchanged selected
W8A16 linear kernel once per row and concatenate the outputs. All other shapes
and all weights remain unchanged. This is an intentionally slow localization
lane, not a performance candidate.

## Fixed gate

- base: R35 image `sha256:38f737c4b5ded15709046929b89cb7cbe851708ae9c47c079ac537d9a07a7a6b`
- treatment variable: `VLLM_XPU_FP8_PACKED_SERIAL_EXACT=1`
- dynamic schedule: MTP8 for one request, MTP1 for 2–128
- one request, TP2, 1,024-token service shape, graphs disabled, deterministic
  Inductor, prefix cache disabled, unchanged official FP8 model
- serial packed RMSNorm and serial GDN remain enabled
- required markers: packed-FP8 R36 plus both R35 GDN markers on both ranks

Run one fresh-server, empty-cache `risk-register` sentinel from the fixed
twelve-prompt suite with seed 42, temperature 0, top-p 1, natural 512-token
cap, returned token IDs, and zero cached tokens. Pass requires exact equality
of all 512 generated IDs with qualified MTP0 R15. Any divergence closes this
mechanism. A pass would authorize only a separately preregistered full-suite
campaign; its diagnostic speed cannot be promoted.

## Result

The compiled attempt did not provide the required packed-FP8 mechanism proof,
so it is not causal evidence. R36b repeated the treatment in eager mode; the
packed-FP8 marker and both serial-GDN markers fired, but the cache-zero output
still diverged at zero-based token 440 (`11447` versus target `24679`). This
moved the R35 divergence from token 127 to 440, identifying packed block-FP8
row shape as one contributor without closing exactness. No speed is promoted.

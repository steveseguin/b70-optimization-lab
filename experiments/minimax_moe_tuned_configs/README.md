# MiniMax M2.7 B70 MoE Tuned Config Screens

These config folders are isolated `VLLM_TUNED_CONFIG_FOLDER` inputs for
MiniMax M2.7 INT4 AutoRound on the current Intel Arc Pro B70 device identity:

```text
Intel(R)_Arc(TM)_Pro_B70_Graphics
```

Use these folders instead of copying candidate JSON files into the live vLLM
source tree. vLLM selects a config file by exact filename and then picks the
nearest numeric key to runtime `M`, so every candidate must include a safe
decode-sized key. A missing `"1"` key does **not** fall back to vLLM defaults;
it makes decode use the nearest larger key.

The first source-tree alias of the old tuned file selected successfully but
failed `raw145-n64-exact`. That rejected patch is preserved in
`patches/minimax-moe-config-alias-quality-fail-20260626.md`.

## Candidates

- `explicit-default-current-device/`: mirrors current default int4 choices for
  the current B70 device filename. This should be quality-neutral and is a
  control for config-file selection itself.
- `m1-old-bn64-bk128-current-device/`: keeps default metadata except for the old
  decode tile `BLOCK_SIZE_N=64`, `BLOCK_SIZE_K=128`. This isolates whether the
  old decode tile is already unsafe without also adding old warps/stages.
- `m1-bn64-bk128-warps4-current-device/`: starts from the quality-safe old
  decode tile and adds only `num_warps=4`, isolating one field from the
  quality-failing old alias.
- `m1-bn64-bk128-stages4-current-device/`: starts from the quality-safe old
  decode tile and adds only `num_stages=4`, isolating the other field from the
  quality-failing old alias.
- `m1-bn32-bk128-current-device/`: keeps default decode `BLOCK_SIZE_N=32` and
  only increases `BLOCK_SIZE_K` to 128.
- `m1-bn64-bk64-current-device/`: keeps default decode `BLOCK_SIZE_K=64` and
  only increases `BLOCK_SIZE_N` to 64.

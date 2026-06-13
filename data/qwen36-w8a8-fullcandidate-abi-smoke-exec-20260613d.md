# Qwen3.6 W8A8 Offset ABI Smoke

Generated: `2026-06-13T02:50:07.544980+00:00`

## Summary

- `installed` `base`: executed
  checksum `1452.126831`, mean_abs `0.440564`, max_abs `3.421875`
- `installed` `offsets`: missing_symbol
- `installed` `active_offsets`: missing_symbol
- `installed` `quant_out`: missing_symbol
- `installed` `silu_quant_out`: missing_symbol
- `build/temp-before-onednn-grouped-20260612064136` `base`: executed
  checksum `1452.126831`, mean_abs `0.440564`, max_abs `3.421875`
- `build/temp-before-onednn-grouped-20260612064136` `offsets`: executed
  checksum `1452.126831`, mean_abs `0.440564`, max_abs `3.421875`
- `build/temp-before-onednn-grouped-20260612064136` `active_offsets`: executed
  checksum `1452.126831`, mean_abs `0.440564`, max_abs `3.421875`
- `build/temp-before-onednn-grouped-20260612064136` `quant_out`: executed
  checksum `683.000000`, mean_abs `30.204264`, max_abs `127.000000`
- `build/temp-before-onednn-grouped-20260612064136` `silu_quant_out`: executed
  checksum `-28.000000`, mean_abs `7.816081`, max_abs `127.000000`

## Decision

Use the full diagnostic candidate(s) that executed base, offsets, active-offset, quant-out, and SiLU+quant-out: build/temp-before-onednn-grouped-20260612064136. Keep endpoint promotion gated on exactness, speed, and provenance; this smoke proves only ABI and tiny execution.

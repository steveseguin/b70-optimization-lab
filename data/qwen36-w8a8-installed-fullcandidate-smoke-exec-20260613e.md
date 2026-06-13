# Qwen3.6 W8A8 Offset ABI Smoke

Generated: `2026-06-13T02:50:49.438028+00:00`

## Summary

- `installed` `base`: executed
  checksum `1452.126831`, mean_abs `0.440564`, max_abs `3.421875`
- `installed` `offsets`: executed
  checksum `1452.126831`, mean_abs `0.440564`, max_abs `3.421875`
- `installed` `active_offsets`: executed
  checksum `1452.126831`, mean_abs `0.440564`, max_abs `3.421875`
- `installed` `quant_out`: executed
  checksum `683.000000`, mean_abs `30.204264`, max_abs `127.000000`
- `installed` `silu_quant_out`: executed
  checksum `-28.000000`, mean_abs `7.816081`, max_abs `127.000000`

## Decision

Use the full diagnostic candidate(s) that executed base, offsets, active-offset, quant-out, and SiLU+quant-out: installed. Keep endpoint promotion gated on exactness, speed, and provenance; this smoke proves only ABI and tiny execution.

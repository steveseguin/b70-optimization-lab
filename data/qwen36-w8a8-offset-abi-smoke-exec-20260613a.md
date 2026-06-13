# Qwen3.6 W8A8 Offset ABI Smoke

Generated: `2026-06-13T02:43:26.484730+00:00`

## Summary

- `installed` `base`: executed
  checksum `1452.126831`, mean_abs `0.440564`, max_abs `3.421875`
- `installed` `offsets`: missing_symbol
- `installed` `active_offsets`: missing_symbol
- `build/lib.linux-x86_64-cpython-312` `base`: executed
  checksum `1452.126831`, mean_abs `0.440564`, max_abs `3.421875`
- `build/lib.linux-x86_64-cpython-312` `offsets`: executed
  checksum `1452.126831`, mean_abs `0.440564`, max_abs `3.421875`
- `build/lib.linux-x86_64-cpython-312` `active_offsets`: missing_symbol
- `build/temp-before-onednn-grouped-20260612064136` `base`: executed
  checksum `1452.126831`, mean_abs `0.440564`, max_abs `3.421875`
- `build/temp-before-onednn-grouped-20260612064136` `offsets`: executed
  checksum `1452.126831`, mean_abs `0.440564`, max_abs `3.421875`
- `build/temp-before-onednn-grouped-20260612064136` `active_offsets`: executed
  checksum `1452.126831`, mean_abs `0.440564`, max_abs `3.421875`
- `build/qwen36-sidecar-probe-20260612` `base`: signal 6
- `build/qwen36-sidecar-probe-20260612` `offsets`: signal 6
- `build/qwen36-sidecar-probe-20260612` `active_offsets`: signal 6

## Decision

Use the stable offset-only candidate as the next no-quality-loss diagnostic lane. Treat active-offset as split: one archived build executed it successfully, but the sidecar-probe build aborted, so do not promote active-offset until that candidate is rebuilt or fixed. Active-offset crashed in at least one candidate.

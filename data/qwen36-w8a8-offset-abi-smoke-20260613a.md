# Qwen3.6 W8A8 Offset ABI Smoke

Generated: `2026-06-13T02:42:47.135251+00:00`

## Summary

- `installed` `base`: registered
- `installed` `offsets`: missing_symbol
- `installed` `active_offsets`: missing_symbol
- `build/lib.linux-x86_64-cpython-312` `base`: registered
- `build/lib.linux-x86_64-cpython-312` `offsets`: registered
- `build/lib.linux-x86_64-cpython-312` `active_offsets`: missing_symbol
- `build/temp-before-onednn-grouped-20260612064136` `base`: registered
- `build/temp-before-onednn-grouped-20260612064136` `offsets`: registered
- `build/temp-before-onednn-grouped-20260612064136` `active_offsets`: registered
- `build/qwen36-sidecar-probe-20260612` `base`: registered
- `build/qwen36-sidecar-probe-20260612` `offsets`: registered
- `build/qwen36-sidecar-probe-20260612` `active_offsets`: registered

## Decision

No offset candidate executed successfully; stop before endpoint testing and rebuild the XPU extension.

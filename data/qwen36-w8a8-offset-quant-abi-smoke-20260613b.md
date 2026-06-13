# Qwen3.6 W8A8 Offset ABI Smoke

Generated: `2026-06-13T02:44:39.378381+00:00`

## Summary

- `installed` `base`: registered
- `installed` `offsets`: missing_symbol
- `installed` `active_offsets`: missing_symbol
- `installed` `quant_out`: missing_symbol
- `installed` `silu_quant_out`: missing_symbol
- `build/lib.linux-x86_64-cpython-312` `base`: registered
- `build/lib.linux-x86_64-cpython-312` `offsets`: registered
- `build/lib.linux-x86_64-cpython-312` `active_offsets`: missing_symbol
- `build/lib.linux-x86_64-cpython-312` `quant_out`: missing_symbol
- `build/lib.linux-x86_64-cpython-312` `silu_quant_out`: missing_symbol
- `build/temp-before-onednn-grouped-20260612064136` `base`: registered
- `build/temp-before-onednn-grouped-20260612064136` `offsets`: registered
- `build/temp-before-onednn-grouped-20260612064136` `active_offsets`: registered
- `build/temp-before-onednn-grouped-20260612064136` `quant_out`: registered
- `build/temp-before-onednn-grouped-20260612064136` `silu_quant_out`: registered
- `build/qwen36-sidecar-probe-20260612` `base`: registered
- `build/qwen36-sidecar-probe-20260612` `offsets`: registered
- `build/qwen36-sidecar-probe-20260612` `active_offsets`: registered
- `build/qwen36-sidecar-probe-20260612` `quant_out`: registered
- `build/qwen36-sidecar-probe-20260612` `silu_quant_out`: registered

## Decision

No offset candidate executed successfully; stop before endpoint testing and rebuild the XPU extension.

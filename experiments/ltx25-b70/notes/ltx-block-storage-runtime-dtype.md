# Stored scale-shift dtype versus the frozen runtime

The [transformer header census](../data/native-block-header-census.json) reports six FP32 scale-shift parameter tables
per block alongside the BF16 linear/norm tensors. This does **not** imply that
the six tables remain FP32 in the frozen static `--bf16-unet` runtime.

Source inspection at ComfyUI commit
`19e1058f4c445ef74047e77a23f9ca7684c1e4b6` establishes this path:

1. `comfy/model_management.py:1129` selects `torch.bfloat16` for `--bf16-unet`.
   `comfy/sd.py:2355` supplies the selected dtype to
   `model_config.set_inference_dtype`.
2. `comfy/supported_models_base.py:118` places that dtype into
   `unet_config['dtype']`; LTXAV inherits this implementation.
   `comfy/model_base.py:184` constructs the diffusion model with that config.
3. `comfy/ldm/lightricks/av_model.py:603` passes the same dtype through the
   transformer-block constructor. Lines 189–205 construct all six scale-shift
   tables as ordinary `nn.Parameter(torch.empty(..., dtype=dtype))`, hence BF16.
4. `comfy/sd.py:2368` calls `load_model_weights(...,
   assign=model_patcher.is_dynamic())`. The frozen static patcher returns false.
   `comfy/model_base.py:370` invokes `diffusion_model.load_state_dict` with that
   `assign=False`. LTXAV and its block have no overriding `_load_from_state_dict`;
   the inherited model-config state-dict processing returns the state unchanged.
5. Installed Torch's native `nn.Module._load_from_state_dict` preserves the
   destination parameter with `param.copy_(input_param)` at
   `torch/nn/modules/module.py:2500`. Thus checkpoint FP32 table values are
   copied into the already-created BF16 parameters. This is existing baseline
   loader behavior, not a new compiler optimization or precision change.

Comfy's lazy Linear loader is different: `comfy/ops.py:495` can replace a Linear
weight with a parameter carrying the state-dict tensor's dtype. The six raw
tables belong directly to `BasicAVTransformerBlock`, so they do not take that
Linear-specific override. This distinction matters when interpreting a mixed
storage-dtype census.

Reviewed source hashes:

| Source | SHA256 |
| --- | --- |
| `comfy/sd.py` | `3eba634a7311bc51cf19c54b12c91149306fe71ae28fa37744e36cfb9290f00a` |
| `comfy/model_base.py` | `6280712f8315f00f19a1ada53e48bf243c818b017fa751b3412092fa0f381e68` |
| `comfy/supported_models_base.py` | `0b234d6f6ceacd04ff96e4126c388cd7c763e21a7d1aed672ba3a235d7a914a5` |
| Installed `torch/nn/modules/module.py` | `d139fc1dc9adb172c208b8b470fc405d8037612c0f08768d275c5bbcc284b9c9` |

The installed Torch source path is
`/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/torch/nn/modules/module.py`.

This is a source-derived conclusion, not live parameter inspection. The future
native compiler gate must still record actual loaded parameter names, dtypes,
shapes and devices and preserve the guard's rejection on any discrepancy.
Dynamic `assign=True` loading or a different loader may preserve stored FP32
tables and requires separate qualification. No checkpoint tensors were loaded,
no model was instantiated and no GPU work was performed for this dtype audit.

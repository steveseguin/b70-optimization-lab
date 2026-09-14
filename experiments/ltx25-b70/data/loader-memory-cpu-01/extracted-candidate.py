native_assign = model_options.get('ltx_native_bf16_assign', False)
if native_assign:
    if model_patcher.is_dynamic() or comfy.memory_management.aimdo_enabled or custom_operations is not None or (model_config.quant_config is not None) or (model_config.unet_config.get('image_model') != 'ltxav') or (unet_dtype != torch.bfloat16) or (offload_device.type != 'cpu'):
        raise RuntimeError('Native LTX assignment requires static CPU BF16 construction')
    targets = model.diffusion_model.state_dict()
    if targets.keys() != new_sd.keys():
        raise RuntimeError('Native LTX assignment requires complete matching state keys')
    report = {'policy': 'ltx_native_bf16_assign', 'assigned_source_bytes': 0, 'converted_destination_bytes': 0, 'dtype_conversions': {}}
    for key, value in new_sd.items():
        target = targets[key]
        if type(value) is not torch.Tensor or value.device.type != 'cpu' or target.device.type != 'cpu' or (value.shape != target.shape) or (value.layout != torch.strided) or (target.layout != torch.strided) or (value.stride() != target.stride()):
            raise RuntimeError('Native LTX assignment layout mismatch: ' + key)
        if value.dtype != target.dtype:
            report['dtype_conversions'][key] = [str(value.dtype), str(target.dtype)]
            report['converted_destination_bytes'] += target.nbytes
            new_sd[key] = value.to(dtype=target.dtype)
        else:
            report['assigned_source_bytes'] += value.nbytes
    del targets
    model_patcher._ltx_native_assign_report = report
model.load_model_weights(new_sd, '', assign=model_patcher.is_dynamic() or native_assign)

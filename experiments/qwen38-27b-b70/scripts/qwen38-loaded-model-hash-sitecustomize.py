"""Diagnostic-only vLLM load hook installed as sitecustomize.py."""

import hashlib
import json
import os
from pathlib import Path


OUTPUT = os.environ.get("VLLM_XPU_LOADED_MODEL_HASH_OUT")
if OUTPUT:
    import torch
    from vllm.v1.worker.gpu_model_runner import GPUModelRunner

    _original_load_model = GPUModelRunner.load_model

    def _hash_tensor(tensor):
        detached = tensor.detach()
        metadata = {
            "dtype": str(detached.dtype),
            "shape": list(detached.shape),
            "stride": list(detached.stride()),
            "numel": detached.numel(),
        }
        if detached.numel() == 0:
            metadata["sha256"] = hashlib.sha256(b"").hexdigest()
            return metadata
        cpu = detached.contiguous().cpu().view(torch.uint8)
        metadata["sha256"] = hashlib.sha256(cpu.numpy().tobytes()).hexdigest()
        return metadata

    def _load_and_hash(self, load_dummy_weights=False):
        result = _original_load_model(self, load_dummy_weights=load_dummy_weights)
        model = self.get_model()
        tensors = {}
        for kind, values in (
            ("parameter", model.named_parameters(remove_duplicate=False)),
            ("buffer", model.named_buffers(remove_duplicate=False)),
        ):
            for name, tensor in values:
                item = _hash_tensor(tensor)
                item["kind"] = kind
                tensors[name] = item
        payload = {
            "schema": "neural.download.qwen38-loaded-model-hashes.raw.v1",
            "tensor_count": len(tensors),
            "tensors": tensors,
        }
        destination = Path(OUTPUT)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        os.replace(temporary, destination)
        return result

    GPUModelRunner.load_model = _load_and_hash

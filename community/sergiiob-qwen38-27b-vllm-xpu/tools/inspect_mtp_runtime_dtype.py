#!/usr/bin/env python3
"""Add a fail-closed, logging-only MTP parameter-dtype probe to pinned vLLM."""

from __future__ import annotations

import importlib.util
from pathlib import Path


spec = importlib.util.find_spec("vllm")
if spec is None or spec.submodule_search_locations is None:
    raise SystemExit("vllm package not found")

target = (
    Path(next(iter(spec.submodule_search_locations)))
    / "model_executor"
    / "models"
    / "qwen3_5_mtp.py"
)
text = target.read_text()

old = """        loader = AutoWeightsLoader(self)
        return loader.load_weights(remap_weight_names(weights))
"""
new = """        loader = AutoWeightsLoader(self)
        loaded = loader.load_weights(remap_weight_names(weights))
        dtype_rows = []
        owned_prefixes = (
            \"model.fc\",
            \"model.pre_fc_norm_embedding\",
            \"model.pre_fc_norm_hidden\",
            \"model.layers\",
            \"model.norm\",
        )
        for parameter_name, parameter in self.named_parameters():
            if parameter_name.startswith(owned_prefixes):
                dtype_rows.append(
                    f\"{parameter_name}:{parameter.dtype}:{tuple(parameter.shape)}\"
                )
        print(\"[B70_MTP_RUNTIME_DTYPE] \" + \" | \".join(dtype_rows), flush=True)
        return loaded
"""

if "[B70_MTP_RUNTIME_DTYPE]" in text:
    print(f"already patched {target}")
elif text.count(old) != 1:
    raise SystemExit(
        f"expected exactly one Qwen3.5 MTP load_weights anchor in {target}, "
        f"found {text.count(old)}"
    )
else:
    target.write_text(text.replace(old, new))
    compile(target.read_text(), str(target), "exec")
    print(f"patched {target}")

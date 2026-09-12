#!/usr/bin/env python3
"""Fail-fast four-card copy/compute smoke, no collective or model."""
import json
import torch

assert torch.xpu.device_count() == 4
for device in range(4):
    torch.xpu.set_device(device)
    print(json.dumps({"ordinal": device, "name": torch.xpu.get_device_name(device),
                      "properties": str(torch.xpu.get_device_properties(device))}), flush=True)
    x = torch.ones((1024, 1024), device=f"xpu:{device}")
    y = float((x + 1).sum().cpu().item())
    torch.xpu.synchronize(device)
    assert y == 2097152.0, (device, y)
    print(json.dumps({"ordinal": device, "sum": y, "passed": True}), flush=True)
    del x

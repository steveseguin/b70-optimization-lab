# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM project
"""UVA-based CPU offloading using Unified Virtual Addressing."""

from collections.abc import Generator
from contextlib import nullcontext

from vllm import screen1b_guard as _s1b
import torch
import torch.nn as nn
from torch.func import functional_call

import vllm.envs as envs
from vllm.logger import init_logger
from vllm.model_executor.offloader.base import BaseOffloader, should_pin_memory
from vllm.utils.gpu_sync_debug import gpu_sync_allowed
from vllm.utils.mem_utils import format_gib
from vllm.utils.platform_utils import is_uva_available
from vllm.utils.torch_utils import get_accelerator_view_from_cpu_tensor

logger = init_logger(__name__)


class UVAOffloader(BaseOffloader):
    """Offloader using Unified Virtual Addressing (UVA) for zero-copy access.

    This offloader moves parameters to pinned CPU memory and creates CUDA views
    using UVA. The GPU can then directly access the CPU memory without explicit
    transfers, at the cost of PCIe bandwidth (slower than GPU memory).

    When UVA is disabled via env var, falls back to a functional_call-based
    approach that moves parameters on-demand.

    Args:
        cpu_offload_max_bytes: Maximum bytes to offload to CPU.
        cpu_offload_params: Set of parameter name segments to selectively
            offload. If empty, all parameters are eligible up to the byte limit.
    """

    supports_tower_offload = True

    def __init__(
        self,
        cpu_offload_max_bytes: int,
        cpu_offload_params: set[str] | None = None,
    ):
        self.cpu_offload_max_bytes = cpu_offload_max_bytes
        self.cpu_offload_bytes = 0
        self.cpu_offload_params = cpu_offload_params or set()

        self.pin_memory = should_pin_memory()
        self.uva_offloading = (
            is_uva_available() and not envs.VLLM_WEIGHT_OFFLOADING_DISABLE_UVA
        )
        if _s1b.enabled() and (not self.pin_memory or not self.uva_offloading):
            raise RuntimeError("Screen 1b requires pinned XPU UVA; no fallback")

    def wrap_modules(
        self,
        modules_generator: Generator[nn.Module, None, None],
        prefix: str = "",
    ) -> list[nn.Module]:
        """Wrap modules with UVA offloading."""
        if prefix:
            prefix = f"{prefix}."
        modules = [
            self._maybe_offload_to_cpu(module, prefix) for module in modules_generator
        ]
        if self.cpu_offload_bytes > 0:
            logger.info(
                "Total CPU offloaded parameters: %s",
                format_gib(self.cpu_offload_bytes),
            )
        return modules

    def _make_cpu_data(self, p):
        if not _s1b.enabled():
            data = p.data.to(device="cpu")
            return data.pin_memory() if self.pin_memory else data
        if not self.pin_memory or not self.uva_offloading:
            raise RuntimeError("Screen 1b requires pinned UVA; no fallback transport")
        nbytes = p.numel() * p.element_size()
        with _s1b.admission("offload_final_storage", nbytes):
            data = torch.empty_like(p.data, device="cpu", pin_memory=True)
            if not data.is_pinned():
                raise RuntimeError("Screen 1b offload allocation failed to pin")
        # Only the explicitly checkpoint-backed PLE may discard its old bytes.
        if not getattr(p, "_vllm_offload_discard_initial_data", False):
            _s1b.bounded_copy(data, p.data)
        return data

    def _maybe_offload_to_cpu(self, module: nn.Module, prefix: str = "") -> nn.Module:
        """Offload module parameters to CPU using UVA if budget allows."""
        _s1b.retain_module(module)
        if (params := next(module.parameters(), None)) is None:
            return module

        device = params.device

        if device == torch.device("cpu"):
            return module

        if self.cpu_offload_bytes >= self.cpu_offload_max_bytes:
            return module

        # offload parameters to CPU
        # use pin_memory if possible, which helps cudagraph capture speed
        offloaded_parameters = False
        for name, p in module.named_parameters():
            if _s1b.enabled() and getattr(p, "_screen1b_direct_ple", False):
                if not getattr(p, "_screen1b_budget_counted", False):
                    # The PLE final host allocation happened in its constructor.
                    # It still consumes exactly the same generic UVA budget.
                    if not any(f".{part}." in f".{prefix}{name}."
                               for part in self.cpu_offload_params):
                        raise RuntimeError("direct PLE must be in selective offload set")
                    if self.cpu_offload_bytes >= self.cpu_offload_max_bytes:
                        raise RuntimeError("PLE does not fit before offload budget cutoff")
                    self.cpu_offload_bytes += p.numel() * p.element_size()
                    p._screen1b_budget_counted = True
                continue
            if self.cpu_offload_bytes >= self.cpu_offload_max_bytes:
                # we use per-parameter offloading
                # one module might have some parameters offloaded and some not
                break

            # Skip parameters an earlier wrap_modules call already offloaded.
            # The UVA path leaves p.device as the accelerator (a view of CPU
            # memory), so the marker is the only way to recognize those.
            if p.device.type == "cpu" or getattr(p, "_vllm_is_uva_offloaded", False):
                continue

            if self.cpu_offload_params:
                # Check if parameter belongs to the offloading set
                # Add dots here to ensure we match full segments only
                # e.g., "experts.w2_weight" matches "mlp.experts.w2_weight"
                # but not "mlp.experts.w2_weight_scale"
                should_offload = any(
                    f".{param}." in f".{prefix}{name}."
                    for param in self.cpu_offload_params
                )
                if not should_offload:
                    continue

            cpu_data = self._make_cpu_data(p)

            if not self.uva_offloading:
                p.data = cpu_data
            else:
                p.data = get_accelerator_view_from_cpu_tensor(cpu_data)
                p._vllm_is_uva_offloaded = True
                p._screen1b_host_storage = cpu_data

            self.cpu_offload_bytes += p.data.numel() * p.data.element_size()
            offloaded_parameters = True

        if offloaded_parameters and not self.uva_offloading:
            original_forward = module.forward

            def forward(*args, **kwargs):
                module.forward = original_forward
                with nullcontext() if self.pin_memory else gpu_sync_allowed():
                    device_state = {
                        # here we blindly call `to(device)`
                        # if the parameter is already on the device,
                        # it will be a no-op
                        k: v.to(device, non_blocking=True)
                        for k, v in module.state_dict().items()
                    }

                # set `tie_weights=False` as tied weights in original model
                # become untied when calling .to(device) individually
                output = functional_call(
                    module,
                    device_state,
                    args=args,
                    kwargs=kwargs,
                    tie_weights=False,
                )
                module.forward = forward
                return output

            module.forward = forward

        return module

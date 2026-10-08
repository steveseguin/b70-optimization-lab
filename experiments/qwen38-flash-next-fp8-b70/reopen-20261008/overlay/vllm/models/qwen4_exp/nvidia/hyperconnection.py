# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM project
"""HyperConnection (Gated Residual) utilities — NVIDIA model variant.

Implements the HyperConnection residual scheme proposed in
"HyperConnections" (https://arxiv.org/abs/2409.19606). This NVIDIA variant
delays each HC combine to the following HC mix boundary. HC glue kernels,
including fused combine+RMSNorm, live in ``ops/hc.py``; projections remain
standard vLLM Linear modules.

Hidden states between layers have shape ``[..., HC*HS]`` with HS inner
(HC outer, HS inner — checkpoint-native layout).

Typical usage inside a transformer decoder layer::

    self.attn_hc = GatedResidual(hc_config)

    hidden_states, block_input, injection = self.attn_hc.mix(hidden_states)
    attention_output = attention(block_input)
    hidden_states, block_input, injection = self.mlp_hc.combine_and_mix(
        hidden_states, attention_output, injection
    )
"""

import torch
import torch.nn.functional as F
from torch import nn

from vllm.logger import init_logger
from vllm.model_executor.layers.linear import (
    MergedColumnParallelLinear,
    ReplicatedLinear,
)
from vllm.model_executor.models.utils import maybe_prefix

from ..common.hyperconnection import (
    GroupedGemmaRMSNorm,
    HyperConnectionConfig,
)
from .ops.hc import (
    grouped_gemma_rmsnorm,
    hc_combine,
    hc_combine_norm,
    hc_gate_mix,
    hc_silu,
)

logger = init_logger(__name__)


def _is_xpu() -> bool:
    from vllm.platforms import current_platform

    return current_platform.is_xpu()


# ---------------------------------------------------------------------------
# XPU HC down-GEMM determinism (K-split)
#
# The skinny BF16 HC down projection (K = hyper_hidden_size = 10240 -> N in
# {336 merged, 320 final mixer}) is run-to-run racy on XPU for row widths
# > 64: the oneDNN accumulation re-samples its split-K draw every execution,
# which is what made PIECEWISE-256 prefill replay diverge from eager
# (bitwise-equal inputs, few-ULP output flips). Replacing the single GEMM
# with two K=5120 GEMMs over contiguous weight halves is bitwise-deterministic
# in eager, fresh-clone and graph capture+replay at every width tested
# (M in {64, 128, 256}; 0/512 flips at M=256). See
# docs/HC_DOWN_GEMM_FIX_RECON.md for the offline campaign.
#
# Widths <= 64 keep the stock single GEMM (bitwise-clean there, and decode
# graphs never exceed 8 rows, so M1 FULL decode keeps stock numerics).
# CUDA is untouched: the halves are prepared only on XPU
# (UnquantizedLinearMethod.process_weights_after_loading calls the
# ``hc_ksplit_prepare`` marker set below), so the split branch is never
# armed on non-XPU platforms.
# ---------------------------------------------------------------------------
_HC_KSPLIT_MAX_STOCK_WIDTH = 64
_HC_KSPLIT_WIDTHS_LOGGED: set[int] = set()


# ---------------------------------------------------------------------------
# Gated-residual variant
# ---------------------------------------------------------------------------
class GatedResidual(nn.Module):
    """Gated HyperConnection with learnable low-rank mixing and injection.

    ``combine_and_mix()`` runs the pre pipeline (grouped GemmaRMSNorm -> merged
    low-rank down+inject GEMM -> silu -> up GEMM -> sigmoid -> gated mean
    over the HC streams). When passed a pending block output, it fuses its
    residual combine with the RMSNorm. A missing injection selects unit-weight
    combine. Final mixers use ``use_combine=False`` and do not produce a new
    injection.

    Weights: the norm owns the grouped GemmaRMSNorm affine; the projections
    are vLLM Linear modules (merged replicated linear for down+inject), so
    GEMM dispatch (e.g. the low-latency skinny GEMM) applies through the
    standard quant_method mechanism.
    """

    def __init__(
        self,
        config: HyperConnectionConfig,
        use_combine: bool = True,
        prefix: str = "",
    ) -> None:
        super().__init__()
        self.config = config
        self.lora_rank = config.hc_lowrank
        self.hc_count = config.hc_count
        self.hidden_size = config.hidden_size
        self.use_combine = use_combine

        norm_size = (
            self.hyper_hidden_size if config.hc_per_branch_norm else config.hidden_size
        )
        group_size = config.hidden_size if config.hc_per_branch_norm else None
        # Normalize each H-sized HC stream independently while retaining a
        # separate affine weight for every element of the HC*H layout.
        self.hc_norm = GroupedGemmaRMSNorm(
            norm_size,
            eps=config.rms_norm_eps,
            group_size=group_size,
            dtype=config.params_dtype,
        )

        # -- vLLM Linear weights --------------------------------------------
        # The merged skinny-GEMM shape is physically padded to 16 rows to ensure
        # good alignment and performant implementation chosen by CuBLAS heuristics.
        self.pad_size = (-(self.lora_rank + self.hc_count)) % 16 if use_combine else 0
        if use_combine:
            self.input_mix_weight_down_block_inject = MergedColumnParallelLinear(
                self.hyper_hidden_size,
                [self.lora_rank, self.hc_count]
                + ([self.pad_size] if self.pad_size else []),
                bias=False,
                params_dtype=config.params_dtype,
                quant_config=None,
                prefix=maybe_prefix(prefix, "input_mix_weight_down_block_inject"),
                return_bias=False,
                disable_tp=True,
            )
        else:
            self.input_mix_weight_down = ReplicatedLinear(
                self.hyper_hidden_size,
                self.lora_rank,
                bias=False,
                params_dtype=config.params_dtype,
                quant_config=None,
                prefix=maybe_prefix(prefix, "input_mix_weight_down"),
                return_bias=False,
            )
        self.input_mix_weight_up = ReplicatedLinear(
            self.lora_rank,
            self.hyper_hidden_size,
            bias=False,
            params_dtype=config.params_dtype,
            quant_config=None,
            prefix=maybe_prefix(prefix, "input_mix_weight_up"),
            return_bias=False,
        )

        # -- XPU deterministic K-split state --------------------------------
        # Contiguous K=5120 halves of the down weight, prepared once at load
        # time on XPU only (see _prepare_kdown_ksplit). ``None`` everywhere
        # else, which keeps the stock single GEMM armed.
        self._kdown_lo: torch.Tensor | None = None
        self._kdown_hi: torch.Tensor | None = None
        self._kdown_k = 0
        down_linear = (
            self.input_mix_weight_down_block_inject
            if use_combine
            else self.input_mix_weight_down
        )
        # Marker consumed by
        # UnquantizedLinearMethod.process_weights_after_loading (XPU only).
        down_linear.hc_ksplit_prepare = self._prepare_kdown_ksplit

    def _prepare_kdown_ksplit(self) -> None:
        """One-time contiguous K-half prep for the deterministic XPU split."""
        if self._kdown_lo is not None:
            return
        down_linear = (
            self.input_mix_weight_down_block_inject
            if self.use_combine
            else self.input_mix_weight_down
        )
        weight = down_linear.weight
        if weight is None or weight.ndim != 2 or weight.shape[1] % 2 != 0:
            logger.debug(
                "HC down GEMM %s: unexpected weight geometry %s; "
                "K-split left disarmed",
                type(down_linear).__name__,
                None if weight is None else tuple(weight.shape),
            )
            return
        self._kdown_k = weight.shape[1] // 2
        self._kdown_lo = weight.data[:, : self._kdown_k].contiguous()
        self._kdown_hi = weight.data[:, self._kdown_k :].contiguous()
        logger.debug(
            "HC down GEMM: K-split halves prepared (K=%d -> 2x%d, N=%d)",
            weight.shape[1],
            self._kdown_k,
            weight.shape[0],
        )

    def _down_gemm(self, xn: torch.Tensor) -> torch.Tensor:
        """Down projection; width-gated deterministic K-split on XPU.

        Row widths <= 64 (all decode graphs) keep the stock single GEMM,
        which is bitwise-clean there. Wider rows (prefill chunks) take the
        two-GEMM split over the contiguous K-halves. The branch conditions
        are shape/attribute reads only, so stream capture bakes the correct
        arm per graph and replays deterministically.
        """
        if (
            self._kdown_lo is not None
            and _is_xpu()
            and xn.shape[0] > _HC_KSPLIT_MAX_STOCK_WIDTH
        ):
            width = xn.shape[0]
            if width not in _HC_KSPLIT_WIDTHS_LOGGED:
                _HC_KSPLIT_WIDTHS_LOGGED.add(width)
                logger.info(
                    "HC down GEMM: deterministic K-split engaged at row width "
                    "%d (stock single GEMM kept for widths <= %d)",
                    width,
                    _HC_KSPLIT_MAX_STOCK_WIDTH,
                )
            return F.linear(xn[..., : self._kdown_k], self._kdown_lo) + F.linear(
                xn[..., self._kdown_k :], self._kdown_hi
            )
        if self.use_combine:
            return self.input_mix_weight_down_block_inject(xn)
        return self.input_mix_weight_down(xn)

    def mix(
        self, hidden_states: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor | None]:
        xn = grouped_gemma_rmsnorm(
            hidden_states,
            self.hc_norm.weight,
            self.config.rms_norm_eps,
            self.hc_count,
        )

        if self.use_combine:
            # produce injection logits for combine
            split_sizes = [self.lora_rank, self.hc_count, self.pad_size]
            down_and_injection = self._down_gemm(xn)
            lora, injection, _ = down_and_injection.split(split_sizes, dim=-1)
        else:
            lora = self._down_gemm(xn)
            injection = None

        lora = hc_silu(lora, self.hc_count)
        gate = self.input_mix_weight_up(lora)  # [M, D]
        block_input = hc_gate_mix(xn, gate, self.hc_count)

        return hidden_states, block_input, injection

    def combine_and_mix(
        self,
        hidden_states: torch.Tensor,
        prev_block_output: torch.Tensor,
        prev_injection: torch.Tensor | None,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor | None]:
        """Consume a pending combine, then prepare the next block input.

        ``hidden_states`` is the multi-stream state from before the pending
        block's mix. Its combine with ``block_output`` is fused with this
        module's input RMSNorm. A missing injection applies the block output
        to every stream with unit weight.
        """
        hidden_states, xn = hc_combine_norm(
            hidden_states,
            prev_block_output,
            prev_injection,
            self.hc_norm.weight,
            self.config.rms_norm_eps,
            self.hc_count,
        )

        if self.use_combine:
            # produce injection logits for combine
            split_sizes = [self.lora_rank, self.hc_count, self.pad_size]
            down_and_injection = self._down_gemm(xn)
            lora, injection, _ = down_and_injection.split(split_sizes, dim=-1)
        else:
            lora = self._down_gemm(xn)
            injection = None

        lora = hc_silu(lora, self.hc_count)
        gate = self.input_mix_weight_up(lora)  # [M, D]
        block_input = hc_gate_mix(xn, gate, self.hc_count)

        return hidden_states, block_input, injection

    def combine(
        self,
        hidden_states: torch.Tensor,
        block_output: torch.Tensor,
        injection: torch.Tensor | None,
    ) -> torch.Tensor:
        return hc_combine(hidden_states, block_output, injection, self.hc_count)

    @property
    def hyper_hidden_size(self) -> int:
        return self.hc_count * self.hidden_size


__all__ = [
    "GatedResidual",
    "GroupedGemmaRMSNorm",
    "HyperConnectionConfig",
]

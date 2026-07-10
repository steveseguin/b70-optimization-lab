#!/usr/bin/env python3
"""Train a diagnostic stacked refinement layer on Qwen3.6 intrinsic MTP.

The frozen checkpoint IntrinsicMTP remains the first draft predictor. One new
full-attention, dense-MLP decoder layer consumes its output sequence and is
trained against recorded target trajectories. The new layer is initialized by
cloning the dequantized intrinsic ``mtp.layers.0`` weights and ``mtp.norm``.

Outputs from this script are offline diagnostics. The refinement artifact is
not an endpoint overlay, is not eligible for headline throughput claims, and
requires explicit runtime/cache integration before endpoint use.
"""

from __future__ import annotations

import argparse
import gc
import importlib.util
import json
import math
import os
import random
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
from safetensors.torch import load_file, save_file


SCRIPT_DIR = Path(__file__).resolve().parent
TRAINER_FILENAME = "train-qwen27-intrinsic-mtp-adapter.py"
ARTIFACT_FILENAME = "stacked_mtp_refinement.safetensors"
SUMMARY_FILENAME = "training_summary.json"
FORMAT_VERSION = 1
CLASSIFICATION = "diagnostic_not_headline_endpoint_incompatible"


def load_local_module(module_name: str, filename: str) -> Any:
    path = SCRIPT_DIR / filename
    if not path.is_file():
        raise ImportError(f"Required local utility does not exist: {path}")
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to import local utility from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# The trainer imports the evaluator with its own path-safe loader. Reusing that
# exact module instance keeps dataset, rollout, RoPE, and quantization semantics
# aligned across all three standalone scripts.
TRAINER = load_local_module(
    "qwen27_intrinsic_mtp_trainer_for_stacked_refinement",
    TRAINER_FILENAME,
)
EVAL = TRAINER.EVAL


SOURCE_KEYS = {
    "input_layernorm.weight": "mtp.layers.0.input_layernorm.weight",
    "post_attention_layernorm.weight": ("mtp.layers.0.post_attention_layernorm.weight"),
    "final_norm.weight": "mtp.norm.weight",
    "self_attn.q_norm.weight": "mtp.layers.0.self_attn.q_norm.weight",
    "self_attn.k_norm.weight": "mtp.layers.0.self_attn.k_norm.weight",
    "self_attn.q_proj.weight": "mtp.layers.0.self_attn.q_proj (dequantized)",
    "self_attn.k_proj.weight": "mtp.layers.0.self_attn.k_proj (dequantized)",
    "self_attn.v_proj.weight": "mtp.layers.0.self_attn.v_proj (dequantized)",
    "self_attn.o_proj.weight": "mtp.layers.0.self_attn.o_proj (dequantized)",
    "mlp.gate_proj.weight": "mtp.layers.0.mlp.gate_proj (dequantized)",
    "mlp.up_proj.weight": "mtp.layers.0.mlp.up_proj (dequantized)",
    "mlp.down_proj.weight": "mtp.layers.0.mlp.down_proj (dequantized)",
}


def stable_key(local_name: str) -> str:
    return f"mtp.refinement_layers.0.{local_name}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Offline diagnostic training for a cloned full-attention/MLP layer "
            "stacked after Qwen27 IntrinsicMTP."
        ),
    )
    parser.add_argument("--model-dir", default=EVAL.DEFAULT_MODEL_DIR)
    parser.add_argument(
        "--model-extra-path",
        default="",
        help=(
            "Optional intrinsic MTP model_extra_tensors.safetensors source. "
            "Defaults to MODEL_DIR/model_extra_tensors.safetensors."
        ),
    )
    parser.add_argument(
        "--dataset-dir",
        default=[],
        action="append",
        help=(
            "Directory containing qwen36_eagle_sequence_v1/v2 .pt files. "
            "May be repeated; the ordered tail is held out."
        ),
    )
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--max-steps", type=int, default=5)
    parser.add_argument("--max-samples", type=int, default=0)
    parser.add_argument("--heldout-samples", type=int, default=4)
    parser.add_argument("--train-starts", type=int, default=2048)
    parser.add_argument("--heldout-starts", type=int, default=768)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument(
        "--max-train-steps",
        type=int,
        default=0,
        help="Global optimizer-step cap; 0 runs all requested epochs.",
    )
    parser.add_argument("--lr", type=float, default=2e-6)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=27)
    parser.add_argument("--device", default="auto")
    parser.add_argument(
        "--dtype",
        default="bfloat16",
        choices=("float32", "bfloat16", "float16"),
    )
    parser.add_argument(
        "--draft-lm-head",
        default="int4-dequant",
        choices=("bf16", "int4-dequant"),
        help=(
            "Offline draft head. int4-dequant mirrors endpoint groupwise INT4 "
            "quantization before diagnostic dense matmul."
        ),
    )
    parser.add_argument("--draft-lm-head-group-size", type=int, default=128)
    parser.add_argument(
        "--draft-lm-head-scale-dtype",
        default="bf16",
        choices=("bf16", "fp16", "fp32"),
    )
    parser.add_argument(
        "--scope",
        default="full",
        choices=("full", "attn", "mlp", "gate"),
        help=(
            "Train all refinement weights, attention plus associated norms, "
            "MLP plus associated norms, or only the residual gate."
        ),
    )
    parser.add_argument(
        "--residual-mode",
        default="replace",
        choices=("replace", "scalar", "vector"),
        help=(
            "replace applies the refinement directly; scalar/vector interpolate "
            "refined-base through a learned residual gate."
        ),
    )
    parser.add_argument(
        "--residual-gate-init",
        type=float,
        default=0.0,
        help="Initial scalar or per-hidden-channel residual gate value.",
    )
    parser.add_argument(
        "--loss-mode",
        default="all-steps",
        choices=("all-steps", "conditional-prefix"),
        help=(
            "all-steps averages every teacher-forced rollout step; "
            "conditional-prefix keeps later rows only while the prior greedy "
            "draft prefix remains exact."
        ),
    )
    parser.add_argument(
        "--skip-official-rope",
        action="store_true",
        help="Force the evaluator's local text-only Neox RoPE fallback.",
    )
    parser.add_argument("--eval-every", type=int, default=0)
    parser.add_argument("--print-every", type=int, default=50)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace only this script's two known output files if present.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run a tiny CPU BF16 forward/backward/export smoke without a model.",
    )
    return parser.parse_args(argv)


class ClonedQwenRMSNorm(torch.nn.Module):
    def __init__(self, source_weight: torch.Tensor, eps: float) -> None:
        super().__init__()
        if source_weight.ndim != 1:
            raise ValueError(
                f"RMSNorm source must be rank 1, got {tuple(source_weight.shape)}"
            )
        self.weight = torch.nn.Parameter(source_weight.detach().clone())
        self.eps = float(eps)

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        return EVAL.qwen_rms_norm(hidden, self.weight, self.eps)


class ClonedDenseLinear(torch.nn.Module):
    """Bias-free linear cloned from evaluator-style [in, out] weight."""

    def __init__(self, source_weight_in_out: torch.Tensor) -> None:
        super().__init__()
        if source_weight_in_out.ndim != 2:
            raise ValueError(
                "Linear source must be rank 2 [in, out], got "
                f"{tuple(source_weight_in_out.shape)}"
            )
        self.weight = torch.nn.Parameter(source_weight_in_out.detach().t().contiguous())

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        return F.linear(hidden, self.weight)


def require_shape(name: str, tensor: torch.Tensor, expected: tuple[int, ...]) -> None:
    actual = tuple(tensor.shape)
    if actual != expected:
        raise ValueError(f"{name} has shape {actual}; expected {expected}")


def validate_clone_source(base_mtp: Any) -> None:
    shape = base_mtp.shape
    hidden = int(shape.hidden_size)
    intermediate = int(shape.intermediate_size)
    query_width = int(shape.num_heads * shape.head_dim)
    kv_width = int(shape.num_kv_heads * shape.head_dim)
    if shape.num_heads < 1 or shape.num_kv_heads < 1 or shape.head_dim < 1:
        raise ValueError("Attention head counts and head_dim must be positive")
    if shape.num_heads % shape.num_kv_heads:
        raise ValueError(
            "num_attention_heads must be divisible by num_key_value_heads; "
            f"got {shape.num_heads} and {shape.num_kv_heads}"
        )
    expected = {
        "input_layernorm": (hidden,),
        "post_attention_layernorm": (hidden,),
        "final_norm": (hidden,),
        "q_norm": (shape.head_dim,),
        "k_norm": (shape.head_dim,),
        "q_proj": (hidden, query_width * 2),
        "k_proj": (hidden, kv_width),
        "v_proj": (hidden, kv_width),
        "o_proj": (query_width, hidden),
        "gate_proj": (hidden, intermediate),
        "up_proj": (hidden, intermediate),
        "down_proj": (intermediate, hidden),
    }
    missing = [name for name in expected if not hasattr(base_mtp, name)]
    if missing:
        raise ValueError(
            "IntrinsicMTP is missing clone source attribute(s): " + ", ".join(missing)
        )
    for name, wanted in expected.items():
        tensor = getattr(base_mtp, name)
        if not isinstance(tensor, torch.Tensor):
            raise TypeError(
                f"IntrinsicMTP clone source {name} is not a tensor: "
                f"{type(tensor).__name__}"
            )
        require_shape(name, tensor, wanted)


class RefinementSelfAttention(torch.nn.Module):
    def __init__(self, base_mtp: Any) -> None:
        super().__init__()
        self.shape = base_mtp.shape
        self.q_proj = ClonedDenseLinear(base_mtp.q_proj)
        self.k_proj = ClonedDenseLinear(base_mtp.k_proj)
        self.v_proj = ClonedDenseLinear(base_mtp.v_proj)
        self.o_proj = ClonedDenseLinear(base_mtp.o_proj)
        self.q_norm = ClonedQwenRMSNorm(base_mtp.q_norm, self.shape.rms_norm_eps)
        self.k_norm = ClonedQwenRMSNorm(base_mtp.k_norm, self.shape.rms_norm_eps)

    def forward(
        self,
        hidden: torch.Tensor,
        positions: torch.Tensor,
        rope: Any | None,
    ) -> torch.Tensor:
        # This intentionally mirrors IntrinsicMTP.self_attention operation order.
        if hidden.ndim != 3:
            raise ValueError(
                f"Refinement attention expects [B, S, H], got {tuple(hidden.shape)}"
            )
        bsz, seq_len, hidden_size = hidden.shape
        if tuple(positions.shape) != (bsz, seq_len):
            raise ValueError(
                "positions must match refinement sequence shape [B, S]; got "
                f"{tuple(positions.shape)} for hidden {tuple(hidden.shape)}"
            )
        if hidden_size != self.shape.hidden_size:
            raise ValueError(
                f"Hidden width {hidden_size} != configured {self.shape.hidden_size}"
            )

        flat = hidden.reshape(bsz * seq_len, hidden_size)
        q_gate = self.q_proj(flat)
        k = self.k_proj(flat)
        v = self.v_proj(flat)
        q_gate = q_gate.view(
            bsz * seq_len, self.shape.num_heads, self.shape.head_dim * 2
        )
        q, gate = torch.chunk(q_gate, 2, dim=-1)
        q = q.reshape(bsz * seq_len, self.shape.num_heads * self.shape.head_dim)
        gate = gate.reshape(bsz * seq_len, self.shape.num_heads * self.shape.head_dim)
        k = k.view(bsz * seq_len, self.shape.num_kv_heads, self.shape.head_dim)

        q = self.q_norm(
            q.view(bsz * seq_len, self.shape.num_heads, self.shape.head_dim)
        ).reshape(bsz * seq_len, self.shape.num_heads * self.shape.head_dim)
        k = self.k_norm(k).reshape(
            bsz * seq_len, self.shape.num_kv_heads * self.shape.head_dim
        )

        flat_positions = positions.reshape(-1)
        if rope is not None:
            q, k = rope(flat_positions.to(hidden.device), q, k)
        else:
            q, k = EVAL.fallback_apply_rope(flat_positions, q, k, self.shape)

        q = q.view(bsz, seq_len, self.shape.num_heads, self.shape.head_dim).permute(
            0, 2, 1, 3
        )
        k = k.view(bsz, seq_len, self.shape.num_kv_heads, self.shape.head_dim).permute(
            0, 2, 1, 3
        )
        v = v.view(bsz, seq_len, self.shape.num_kv_heads, self.shape.head_dim).permute(
            0, 2, 1, 3
        )
        repeat = self.shape.num_heads // self.shape.num_kv_heads
        if repeat > 1:
            k = k.repeat_interleave(repeat, dim=1)
            v = v.repeat_interleave(repeat, dim=1)

        scores = torch.matmul(q.float(), k.float().transpose(-2, -1))
        scores *= 1.0 / math.sqrt(float(self.shape.head_dim))
        causal = torch.triu(
            torch.ones(
                seq_len,
                seq_len,
                device=hidden.device,
                dtype=torch.bool,
            ),
            diagonal=1,
        )
        scores = scores.masked_fill(causal[None, None, :, :], float("-inf"))
        probs = F.softmax(scores, dim=-1).to(hidden.dtype)
        attn = torch.matmul(probs, v)
        attn = (
            attn.permute(0, 2, 1, 3)
            .contiguous()
            .view(bsz * seq_len, self.shape.num_heads * self.shape.head_dim)
        )
        attn = attn * torch.sigmoid(gate)
        return self.o_proj(attn).view(bsz, seq_len, hidden_size)


class RefinementMLP(torch.nn.Module):
    def __init__(self, base_mtp: Any) -> None:
        super().__init__()
        self.gate_proj = ClonedDenseLinear(base_mtp.gate_proj)
        self.up_proj = ClonedDenseLinear(base_mtp.up_proj)
        self.down_proj = ClonedDenseLinear(base_mtp.down_proj)

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        return self.down_proj(F.silu(self.gate_proj(hidden)) * self.up_proj(hidden))


class RefinementDecoderLayer(torch.nn.Module):
    def __init__(
        self,
        base_mtp: Any,
        residual_mode: str = "replace",
        residual_gate_init: float = 0.0,
    ) -> None:
        super().__init__()
        validate_clone_source(base_mtp)
        if residual_mode not in {"replace", "scalar", "vector"}:
            raise ValueError(f"Unknown residual mode {residual_mode!r}")
        eps = base_mtp.shape.rms_norm_eps
        self.input_layernorm = ClonedQwenRMSNorm(base_mtp.input_layernorm, eps)
        self.self_attn = RefinementSelfAttention(base_mtp)
        self.post_attention_layernorm = ClonedQwenRMSNorm(
            base_mtp.post_attention_layernorm, eps
        )
        self.mlp = RefinementMLP(base_mtp)
        self.final_norm = ClonedQwenRMSNorm(base_mtp.final_norm, eps)
        self.rms_norm_eps = float(eps)
        self.residual_mode = residual_mode
        self.residual_gate_init = float(residual_gate_init)
        if residual_mode == "replace":
            self.register_parameter("residual_gate", None)
        else:
            shape = () if residual_mode == "scalar" else (base_mtp.shape.hidden_size,)
            self.residual_gate = torch.nn.Parameter(
                torch.full(
                    shape,
                    self.residual_gate_init,
                    device=base_mtp.fc.device,
                    dtype=base_mtp.fc.dtype,
                )
            )

    def forward(
        self,
        hidden: torch.Tensor,
        positions: torch.Tensor,
        rope: Any | None,
    ) -> torch.Tensor:
        layer_input = hidden
        residual = layer_input
        refined = self.input_layernorm(layer_input)
        refined = self.self_attn(refined, positions, rope)
        refined, residual = EVAL.qwen_rms_norm_residual(
            refined,
            residual,
            self.post_attention_layernorm.weight,
            self.rms_norm_eps,
        )
        refined = self.mlp(refined)
        refined, _ = EVAL.qwen_rms_norm_residual(
            refined,
            residual,
            self.final_norm.weight,
            self.rms_norm_eps,
        )
        if self.residual_gate is None:
            return refined
        return layer_input + self.residual_gate * (refined - layer_input)


class StackedIntrinsicMTP(torch.nn.Module):
    """Frozen IntrinsicMTP followed by one trainable refinement decoder."""

    def __init__(
        self,
        base_mtp: Any,
        residual_mode: str = "replace",
        residual_gate_init: float = 0.0,
    ) -> None:
        super().__init__()
        self.base_mtp = base_mtp
        for parameter in self.base_mtp.parameters():
            parameter.requires_grad_(False)
        self.base_mtp.eval()
        self.shape = base_mtp.shape
        self.refinement_layers = torch.nn.ModuleList(
            [RefinementDecoderLayer(base_mtp, residual_mode, residual_gate_init)]
        )
        self.draft_lm_head = getattr(base_mtp, "draft_lm_head", "unknown")

    @property
    def rope(self) -> Any | None:
        return getattr(self.base_mtp, "rope", None)

    def forward(
        self,
        hidden_states: torch.Tensor,
        input_ids: torch.Tensor,
        positions: torch.Tensor,
        spec_step_idx: int = 0,
    ) -> torch.Tensor:
        hidden = self.base_mtp(
            hidden_states,
            input_ids,
            positions,
            spec_step_idx=spec_step_idx,
        )
        for layer in self.refinement_layers:
            hidden = layer(hidden, positions, self.rope)
        return hidden

    def logits(self, hidden: torch.Tensor) -> torch.Tensor:
        return self.base_mtp.logits(hidden)


def scope_parameter_names(layer: RefinementDecoderLayer, scope: str) -> list[str]:
    all_names = [name for name, _ in layer.named_parameters()]
    if scope == "full":
        return all_names
    if scope == "attn":
        return [
            name
            for name in all_names
            if name.startswith("self_attn.")
            or name
            in {
                "input_layernorm.weight",
                "post_attention_layernorm.weight",
                "residual_gate",
            }
        ]
    if scope == "mlp":
        return [
            name
            for name in all_names
            if name.startswith("mlp.")
            or name
            in {
                "post_attention_layernorm.weight",
                "final_norm.weight",
                "residual_gate",
            }
        ]
    if scope == "gate":
        if "residual_gate" not in all_names:
            raise ValueError("gate scope requires scalar or vector residual mode")
        return ["residual_gate"]
    raise ValueError(f"Unknown trainable scope {scope!r}")


def make_refinement_trainable(
    model: StackedIntrinsicMTP,
    scope: str,
) -> tuple[list[torch.nn.Parameter], list[str]]:
    if len(model.refinement_layers) != 1:
        raise ValueError(
            "This artifact format requires exactly one refinement layer; found "
            f"{len(model.refinement_layers)}"
        )
    layer = model.refinement_layers[0]
    selected = scope_parameter_names(layer, scope)
    selected_set = set(selected)
    params: list[torch.nn.Parameter] = []
    for name, parameter in layer.named_parameters():
        trainable = name in selected_set
        parameter.requires_grad_(trainable)
        if trainable:
            params.append(parameter)
    if not params:
        raise ValueError(f"Scope {scope!r} selected no refinement parameters")
    return params, [stable_key(name) for name in selected]


def refinement_export_tensors(
    model: StackedIntrinsicMTP,
) -> dict[str, torch.Tensor]:
    if len(model.refinement_layers) != 1:
        raise ValueError("Only one refinement layer can be exported")
    tensors = {
        stable_key(name): parameter.detach().cpu().to(torch.bfloat16).contiguous()
        for name, parameter in model.refinement_layers[0].named_parameters()
    }
    expected = {stable_key(name) for name in SOURCE_KEYS}
    if model.refinement_layers[0].residual_gate is not None:
        expected.add(stable_key("residual_gate"))
    actual = set(tensors)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise ValueError(
            "Refinement export key mismatch: "
            f"missing={missing}, unexpected={unexpected}"
        )
    non_bf16 = [key for key, value in tensors.items() if value.dtype != torch.bfloat16]
    if non_bf16:
        raise ValueError(f"Refinement export contains non-BF16 keys: {non_bf16}")
    return tensors


def atomic_save_safetensors(
    tensors: dict[str, torch.Tensor],
    path: Path,
    metadata: dict[str, str],
) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    if tmp.exists():
        raise FileExistsError(f"Refusing to replace stale temporary file: {tmp}")
    try:
        save_file(tensors, str(tmp), metadata=metadata)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def atomic_write_json(payload: dict[str, Any], path: Path) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    if tmp.exists():
        raise FileExistsError(f"Refusing to replace stale temporary file: {tmp}")
    try:
        tmp.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def validate_device(device: torch.device) -> None:
    if device.type == "xpu":
        if not hasattr(torch, "xpu") or not torch.xpu.is_available():
            raise RuntimeError(
                f"Requested device {device}, but torch.xpu is unavailable"
            )
    elif device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError(f"Requested device {device}, but torch.cuda is unavailable")
    elif device.type not in {"cpu", "xpu", "cuda"}:
        raise ValueError(
            f"Unsupported device type {device.type!r}; use cpu, xpu, cuda, or auto"
        )


def validate_args(args: argparse.Namespace) -> None:
    if args.self_test:
        return
    if not args.out_dir:
        raise ValueError("--out-dir is required unless --self-test is used")
    integer_minima = {
        "--max-steps": (args.max_steps, 1),
        "--max-samples": (args.max_samples, 0),
        "--heldout-samples": (args.heldout_samples, 1),
        "--train-starts": (args.train_starts, 1),
        "--heldout-starts": (args.heldout_starts, 1),
        "--batch-size": (args.batch_size, 1),
        "--epochs": (args.epochs, 1),
        "--max-train-steps": (args.max_train_steps, 0),
        "--draft-lm-head-group-size": (args.draft_lm_head_group_size, 1),
        "--eval-every": (args.eval_every, 0),
        "--print-every": (args.print_every, 0),
    }
    for flag, (value, minimum) in integer_minima.items():
        if value < minimum:
            raise ValueError(f"{flag} must be >= {minimum}, got {value}")
    if not math.isfinite(args.lr) or args.lr <= 0:
        raise ValueError(f"--lr must be finite and > 0, got {args.lr}")
    if not math.isfinite(args.weight_decay) or args.weight_decay < 0:
        raise ValueError(
            f"--weight-decay must be finite and >= 0, got {args.weight_decay}"
        )
    if not math.isfinite(args.grad_clip) or args.grad_clip < 0:
        raise ValueError(f"--grad-clip must be finite and >= 0, got {args.grad_clip}")
    if not math.isfinite(args.residual_gate_init):
        raise ValueError("--residual-gate-init must be finite")
    if args.residual_mode == "replace" and args.residual_gate_init != 0:
        raise ValueError(
            "--residual-gate-init is only meaningful with scalar/vector --residual-mode"
        )
    if args.scope == "gate" and args.residual_mode == "replace":
        raise ValueError("--scope gate requires scalar/vector --residual-mode")

    model_dir = Path(args.model_dir).expanduser()
    if not model_dir.is_dir():
        raise FileNotFoundError(f"Model directory does not exist: {model_dir}")
    for filename in ("config.json", "model.safetensors.index.json"):
        path = model_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"Required model file does not exist: {path}")
    model_extra_path = (
        Path(args.model_extra_path).expanduser()
        if (args.model_extra_path)
        else model_dir / "model_extra_tensors.safetensors"
    )
    if not model_extra_path.is_file():
        raise FileNotFoundError(
            f"Intrinsic MTP tensor file does not exist: {model_extra_path}"
        )

    if not args.dataset_dir:
        args.dataset_dir = [EVAL.DEFAULT_DATASET_DIR]
    normalized_dataset_dirs: list[str] = []
    for value in args.dataset_dir:
        if not value:
            continue
        path = Path(value).expanduser()
        if not path.is_dir():
            raise FileNotFoundError(f"Dataset directory does not exist: {path}")
        normalized_dataset_dirs.append(str(path.resolve()))
    if not normalized_dataset_dirs:
        raise ValueError("At least one non-empty --dataset-dir is required")
    args.dataset_dir = normalized_dataset_dirs
    args.model_dir = str(model_dir.resolve())
    args.model_extra_path = str(model_extra_path.resolve())

    out_dir = Path(args.out_dir).expanduser().resolve()
    if out_dir == model_dir.resolve():
        raise ValueError("--out-dir must not be the source model directory")
    if out_dir.exists() and not out_dir.is_dir():
        raise NotADirectoryError(f"Output path is not a directory: {out_dir}")
    for filename in (ARTIFACT_FILENAME, SUMMARY_FILENAME):
        output = out_dir / filename
        if output.exists() and not args.overwrite:
            raise FileExistsError(
                f"Output already exists: {output}; pass --overwrite to replace it"
            )
    args.out_dir = str(out_dir)


def validate_base_depth(base_mtp: Any, max_steps: int) -> None:
    for label, count_name in (
        ("position FC", "position_fc_count"),
        ("position adapter", "position_adapter_count"),
    ):
        count = int(getattr(base_mtp, count_name, 0))
        if count and count < max_steps:
            raise ValueError(
                f"Base MTP has {count} {label}s but --max-steps={max_steps}; "
                "use a compatible overlay or lower the rollout depth"
            )


def split_samples(
    samples: list[dict[str, Any]],
    heldout_count: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if heldout_count >= len(samples):
        raise ValueError(
            "--heldout-samples must leave at least one train sample; "
            f"loaded {len(samples)} usable samples, requested {heldout_count} held out"
        )
    return samples[:-heldout_count], samples[-heldout_count:]


def sample_paths(samples: list[dict[str, Any]]) -> list[str]:
    return [str(sample.get("_path", "")) for sample in samples]


def train_refinement(
    model: StackedIntrinsicMTP,
    train_samples: list[dict[str, Any]],
    train_refs: list[Any],
    heldout_samples: list[dict[str, Any]],
    heldout_refs: list[Any],
    params: list[torch.nn.Parameter],
    args: argparse.Namespace,
    device: torch.device,
    dtype: torch.dtype,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    model.eval()
    base_only = TRAINER.evaluate_batched(
        model.base_mtp,
        heldout_samples,
        heldout_refs,
        device,
        dtype,
        args.max_steps,
        args.batch_size,
    )
    print(f"[stacked-mtp-refinement] base-only heldout={base_only}", flush=True)
    before = TRAINER.evaluate_batched(
        model,
        heldout_samples,
        heldout_refs,
        device,
        dtype,
        args.max_steps,
        args.batch_size,
    )
    print(f"[stacked-mtp-refinement] before heldout={before}", flush=True)

    optimizer = torch.optim.AdamW(
        params,
        lr=args.lr,
        weight_decay=args.weight_decay,
    )
    started = time.perf_counter()
    optimizer_steps = 0
    batches_seen = 0
    loss_sum = 0.0
    last_loss: float | None = None
    epochs_started = 0
    stopped_by_step_cap = False
    model.train()
    model.base_mtp.eval()

    for epoch in range(args.epochs):
        epochs_started += 1
        random.shuffle(train_refs)
        for offset in range(0, len(train_refs), args.batch_size):
            if args.max_train_steps > 0 and optimizer_steps >= args.max_train_steps:
                stopped_by_step_cap = True
                break
            batch_refs = train_refs[offset : offset + args.batch_size]
            if not batch_refs:
                continue
            batches_seen += 1
            batch = TRAINER.build_batch(
                train_samples,
                batch_refs,
                device,
                dtype,
                args.max_steps,
            )
            optimizer.zero_grad(set_to_none=True)
            loss, accs = TRAINER.rollout_loss(
                model,
                batch,
                args.max_steps,
                args.loss_mode,
            )
            if not loss.requires_grad:
                raise RuntimeError(
                    "Training loss has no gradient; scope selection or graph "
                    "construction is invalid"
                )
            if not bool(torch.isfinite(loss.detach()).item()):
                raise FloatingPointError(
                    f"Non-finite training loss at optimizer step {optimizer_steps + 1}"
                )
            loss.backward()
            gradients = [
                parameter.grad for parameter in params if parameter.grad is not None
            ]
            if not gradients:
                raise FloatingPointError(
                    f"No refinement gradient at step {optimizer_steps + 1}"
                )
            torch.nn.utils.clip_grad_norm_(
                params,
                args.grad_clip if args.grad_clip > 0 else float("inf"),
                error_if_nonfinite=True,
            )
            optimizer.step()
            optimizer_steps += 1
            last_loss = float(loss.detach().item())
            loss_sum += last_loss

            if args.print_every > 0 and optimizer_steps % args.print_every == 0:
                print(
                    f"[stacked-mtp-refinement] epoch={epoch + 1}/{args.epochs} "
                    f"step={optimizer_steps} loss={last_loss:.5f} "
                    f"teacher_acc={[round(value, 4) for value in accs]}",
                    flush=True,
                )
            if args.eval_every > 0 and optimizer_steps % args.eval_every == 0:
                model.eval()
                mid = TRAINER.evaluate_batched(
                    model,
                    heldout_samples,
                    heldout_refs,
                    device,
                    dtype,
                    args.max_steps,
                    args.batch_size,
                )
                print(
                    f"[stacked-mtp-refinement] mid step={optimizer_steps} "
                    f"heldout={mid}",
                    flush=True,
                )
                model.train()
                model.base_mtp.eval()
        if stopped_by_step_cap:
            break

    if optimizer_steps < 1:
        raise RuntimeError("Training completed without an optimizer step")
    training_elapsed_s = time.perf_counter() - started
    model.eval()
    after = TRAINER.evaluate_batched(
        model,
        heldout_samples,
        heldout_refs,
        device,
        dtype,
        args.max_steps,
        args.batch_size,
    )
    print(f"[stacked-mtp-refinement] after heldout={after}", flush=True)
    stats = {
        "optimizer_steps": optimizer_steps,
        "batches_seen": batches_seen,
        "epochs_started": epochs_started,
        "stopped_by_max_train_steps": stopped_by_step_cap,
        "max_train_steps": args.max_train_steps,
        "mean_training_loss": loss_sum / optimizer_steps,
        "last_training_loss": last_loss,
        "training_elapsed_s": training_elapsed_s,
    }
    return base_only, before, after, stats


def save_outputs(
    model: StackedIntrinsicMTP,
    args: argparse.Namespace,
    train_samples: list[dict[str, Any]],
    heldout_samples: list[dict[str, Any]],
    train_refs: list[Any],
    heldout_refs: list[Any],
    trainable_keys: list[str],
    base_only: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
    train_stats: dict[str, Any],
    device: torch.device,
    dtype: torch.dtype,
    total_elapsed_s: float,
) -> tuple[Path, Path]:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = out_dir / ARTIFACT_FILENAME
    summary_path = out_dir / SUMMARY_FILENAME
    tensors = refinement_export_tensors(model)
    residual_gate = model.refinement_layers[0].residual_gate
    residual_gate_stats = None
    if residual_gate is not None:
        gate_float = residual_gate.detach().float().cpu()
        residual_gate_stats = {
            "numel": gate_float.numel(),
            "mean": float(gate_float.mean().item()),
            "min": float(gate_float.min().item()),
            "max": float(gate_float.max().item()),
            "l2": float(torch.linalg.vector_norm(gate_float).item()),
        }
    metadata = {
        "format": "qwen27_stacked_mtp_refinement",
        "format_version": str(FORMAT_VERSION),
        "classification": CLASSIFICATION,
        "dtype": "bfloat16",
        "linear_weight_orientation": "out_features,in_features",
        "initialization": "cloned_dequantized_intrinsic_mtp_layer_0",
        "residual_mode": args.residual_mode,
        "residual_gate_init": str(args.residual_gate_init),
        "endpoint_compatible": "false",
        "runtime_integration_required": "true",
        "valid_headline_throughput": "false",
        "localmaxxing_eligible": "false",
    }
    atomic_save_safetensors(tensors, artifact_path, metadata)

    all_export_keys = sorted(tensors)
    frozen_export_keys = sorted(set(all_export_keys) - set(trainable_keys))
    summary = {
        "purpose": "diagnostic_stacked_intrinsic_mtp_refinement_training",
        "classification": CLASSIFICATION,
        "valid_headline_throughput": False,
        "endpoint_candidate_compatible": False,
        "runtime_integration_required": True,
        "localmaxxing_eligible": False,
        "headline_warning": (
            "Offline accepted-depth diagnostic only. The added decoder has no "
            "endpoint runtime/KV-cache integration and must not be reported as "
            "headline throughput or submitted to LocalMaxxing."
        ),
        "architecture": {
            "base": "frozen evaluator IntrinsicMTP",
            "refinement_layer_count": 1,
            "refinement_layer_type": "causal_full_attention_dense_mlp",
            "placement": "after_base_intrinsic_mtp_output_sequence",
            "attention_semantics": (
                "evaluator_gated_q_grouped_kv_qk_norm_rope_causal_softmax"
            ),
            "residual_norm_semantics": "matching_evaluator_qwen_rms_norm_residual",
            "initialization": "clone_intrinsic_mtp.layers.0_and_mtp.norm",
            "initialization_sources": {
                stable_key(name): source for name, source in SOURCE_KEYS.items()
            },
            "residual_mode": args.residual_mode,
            "residual_gate_init": args.residual_gate_init,
            "residual_gate_shape": (
                list(model.refinement_layers[0].residual_gate.shape)
                if model.refinement_layers[0].residual_gate is not None
                else None
            ),
            "residual_gate_after": residual_gate_stats,
            "linear_weight_orientation": "out_features,in_features",
            "hidden_size": model.shape.hidden_size,
            "intermediate_size": model.shape.intermediate_size,
            "num_attention_heads": model.shape.num_heads,
            "num_key_value_heads": model.shape.num_kv_heads,
            "head_dim": model.shape.head_dim,
        },
        "model_dir": args.model_dir,
        "model_extra_path": args.model_extra_path,
        "dataset_dirs": args.dataset_dir,
        "dataset_split": {
            "strategy": "ordered_usable_sample_tail_holdout",
            "usable_samples": len(train_samples) + len(heldout_samples),
            "train_samples": len(train_samples),
            "heldout_samples": len(heldout_samples),
            "train_sample_paths": sample_paths(train_samples),
            "heldout_sample_paths": sample_paths(heldout_samples),
            "train_start_refs": len(train_refs),
            "heldout_start_refs": len(heldout_refs),
        },
        "max_steps": args.max_steps,
        "max_samples": args.max_samples,
        "train_starts_limit": args.train_starts,
        "heldout_starts_limit": args.heldout_starts,
        "batch_size": args.batch_size,
        "epochs": args.epochs,
        "max_train_steps": args.max_train_steps,
        "lr": args.lr,
        "weight_decay": args.weight_decay,
        "grad_clip": args.grad_clip,
        "seed": args.seed,
        "scope": args.scope,
        "residual_mode": args.residual_mode,
        "residual_gate_init": args.residual_gate_init,
        "loss_mode": args.loss_mode,
        "device": str(device),
        "dtype": str(dtype).removeprefix("torch."),
        "draft_lm_head": args.draft_lm_head,
        "draft_lm_head_group_size": args.draft_lm_head_group_size,
        "draft_lm_head_scale_dtype": args.draft_lm_head_scale_dtype,
        "rope": (
            "vllm_get_rope_shared_with_base"
            if model.rope is not None
            else "local_text_only_neox_rope_fallback"
        ),
        "trainable_keys": trainable_keys,
        "frozen_export_keys": frozen_export_keys,
        "trainable_param_count": sum(
            parameter.numel()
            for parameter in model.refinement_layers[0].parameters()
            if parameter.requires_grad
        ),
        "total_refinement_param_count": sum(
            parameter.numel() for parameter in model.refinement_layers[0].parameters()
        ),
        "base_only": base_only,
        "before": before,
        "after": after,
        "training": train_stats,
        "artifact": {
            "path": str(artifact_path),
            "filename": ARTIFACT_FILENAME,
            "format_version": FORMAT_VERSION,
            "dtype": "bfloat16",
            "keys": all_export_keys,
            "metadata": metadata,
            "size_bytes": artifact_path.stat().st_size,
        },
        "training_summary_path": str(summary_path),
        "torch_version": torch.__version__,
        "total_elapsed_s": total_elapsed_s,
    }
    atomic_write_json(summary, summary_path)
    return artifact_path, summary_path


def add_synthetic_gptq_linear(
    tensors: dict[str, torch.Tensor],
    prefix: str,
    in_features: int,
    out_features: int,
    generator: torch.Generator,
) -> None:
    """Add a tiny symmetric group-128 GPTQ linear for the real evaluator."""
    if in_features % 8 or out_features % 8:
        raise ValueError("Synthetic GPTQ dimensions must be divisible by 8")
    codes = torch.randint(
        5,
        12,
        (in_features, out_features),
        generator=generator,
        dtype=torch.int64,
    ).view(in_features // 8, 8, out_features)
    qweight = torch.zeros(in_features // 8, out_features, dtype=torch.int64)
    for index in range(8):
        qweight |= codes[:, index, :] << (4 * index)

    groups = math.ceil(in_features / 128)
    zero_codes = torch.full((groups, out_features), 7, dtype=torch.int64).view(
        groups, out_features // 8, 8
    )
    qzeros = torch.zeros(groups, out_features // 8, dtype=torch.int64)
    for index in range(8):
        qzeros |= zero_codes[:, :, index] << (4 * index)

    scales = (
        torch.rand(groups, out_features, generator=generator, dtype=torch.float32)
        * 0.02
        + 0.01
    ).to(torch.bfloat16)
    tensors[f"{prefix}.qweight"] = qweight.to(torch.int32)
    tensors[f"{prefix}.qzeros"] = qzeros.to(torch.int32)
    tensors[f"{prefix}.scales"] = scales


def make_synthetic_intrinsic_mtp() -> Any:
    """Construct the imported IntrinsicMTP from tiny in-memory tensors."""
    shape = EVAL.QwenMTPShape(
        hidden_size=16,
        intermediate_size=32,
        vocab_size=64,
        num_heads=4,
        num_kv_heads=2,
        head_dim=4,
        rms_norm_eps=1e-6,
        rope_theta=10000.0,
        rope_parameters={"partial_rotary_factor": 1.0},
    )
    generator = torch.Generator(device="cpu")
    generator.manual_seed(2718)

    def random_tensor(*dimensions: int, scale: float = 0.04) -> torch.Tensor:
        return (
            torch.randn(*dimensions, generator=generator, dtype=torch.float32) * scale
        ).to(torch.bfloat16)

    hidden = shape.hidden_size
    query = shape.num_heads * shape.head_dim
    kv = shape.num_kv_heads * shape.head_dim
    intermediate = shape.intermediate_size
    tensors = {
        "mtp.fc.weight": random_tensor(hidden, hidden * 2),
        "mtp.pre_fc_norm_embedding.weight": random_tensor(hidden, scale=0.01),
        "mtp.pre_fc_norm_hidden.weight": random_tensor(hidden, scale=0.01),
        "mtp.layers.0.input_layernorm.weight": random_tensor(hidden, scale=0.01),
        "mtp.layers.0.post_attention_layernorm.weight": random_tensor(
            hidden, scale=0.01
        ),
        "mtp.layers.0.self_attn.q_norm.weight": random_tensor(
            shape.head_dim, scale=0.01
        ),
        "mtp.layers.0.self_attn.k_norm.weight": random_tensor(
            shape.head_dim, scale=0.01
        ),
        "mtp.norm.weight": random_tensor(hidden, scale=0.01),
    }
    for prefix, in_features, out_features in (
        ("mtp.layers.0.self_attn.q_proj", hidden, query * 2),
        ("mtp.layers.0.self_attn.k_proj", hidden, kv),
        ("mtp.layers.0.self_attn.v_proj", hidden, kv),
        ("mtp.layers.0.self_attn.o_proj", query, hidden),
        ("mtp.layers.0.mlp.gate_proj", hidden, intermediate),
        ("mtp.layers.0.mlp.up_proj", hidden, intermediate),
        ("mtp.layers.0.mlp.down_proj", intermediate, hidden),
    ):
        add_synthetic_gptq_linear(
            tensors,
            prefix,
            in_features,
            out_features,
            generator,
        )
    return EVAL.IntrinsicMTP(
        shape=shape,
        tensors=tensors,
        embed_weight=random_tensor(shape.vocab_size, hidden),
        lm_head_weight=random_tensor(shape.vocab_size, hidden),
        device=torch.device("cpu"),
        dtype=torch.bfloat16,
        use_official_rope=False,
        draft_lm_head="int4-dequant",
        draft_lm_head_group_size=16,
        draft_lm_head_scale_dtype="bf16",
    ).eval()


def self_test() -> int:
    torch.manual_seed(27)
    dtype = torch.bfloat16
    base = make_synthetic_intrinsic_mtp()
    model = StackedIntrinsicMTP(base)
    layer = model.refinement_layers[0]

    scope_counts: dict[str, int] = {}
    for scope in ("full", "attn", "mlp"):
        params, names = make_refinement_trainable(model, scope)
        if not params or len(params) != len(names):
            raise AssertionError(f"Scope {scope} did not select stable parameters")
        scope_counts[scope] = sum(parameter.numel() for parameter in params)

    params, trainable_keys = make_refinement_trainable(model, "full")
    hidden = torch.randn(2, 3, 16, dtype=torch.float32).to(dtype)
    input_ids = torch.tensor([[1, 2, 3], [4, 5, 6]], dtype=torch.long)
    positions = torch.arange(3, dtype=torch.long).repeat(2, 1)
    source_attention = base.self_attention(hidden, positions)
    cloned_attention = layer.self_attn(hidden, positions, base.rope)
    if not torch.allclose(source_attention, cloned_attention, rtol=1e-3, atol=1e-3):
        raise AssertionError("Cloned refinement attention does not match evaluator")
    source_mlp = base.matmul(
        F.silu(base.matmul(hidden, base.gate_proj)) * base.matmul(hidden, base.up_proj),
        base.down_proj,
    )
    cloned_mlp = layer.mlp(hidden)
    if not torch.allclose(source_mlp, cloned_mlp, rtol=1e-3, atol=1e-3):
        raise AssertionError("Cloned refinement MLP does not match evaluator")
    output = model(hidden, input_ids, positions)
    if output.shape != hidden.shape or not bool(torch.isfinite(output).all()):
        raise AssertionError("Synthetic stacked forward produced invalid output")

    gated_model = StackedIntrinsicMTP(
        base,
        residual_mode="vector",
        residual_gate_init=0.0,
    )
    gated_output = gated_model(hidden, input_ids, positions)
    base_output = base(hidden, input_ids, positions)
    if not torch.equal(gated_output, base_output):
        raise AssertionError("Zero residual gate did not preserve exact base output")
    gate_params, gate_names = make_refinement_trainable(gated_model, "gate")
    if len(gate_params) != 1 or gate_names != [stable_key("residual_gate")]:
        raise AssertionError("Residual gate scope selected unexpected parameters")
    gated_tensors = refinement_export_tensors(gated_model)
    if stable_key("residual_gate") not in gated_tensors:
        raise AssertionError("Residual gate was omitted from the export")

    changed_hidden = hidden.clone()
    changed_hidden[:, -1, :] += torch.tensor(3.0, dtype=dtype)
    changed_ids = input_ids.clone()
    changed_ids[:, -1] = 9
    changed_output = model(changed_hidden, changed_ids, positions)
    if not torch.allclose(output[:, :-1], changed_output[:, :-1], rtol=1e-3, atol=1e-3):
        raise AssertionError("Refinement attention violated causal prefix invariance")

    batch = {
        "hidden": torch.randn(2, 1, 16, dtype=torch.float32).to(dtype),
        "ids": torch.tensor([[2], [3]], dtype=torch.long),
        "positions": torch.zeros(2, 1, dtype=torch.long),
        "targets": torch.tensor([[4, 5], [6, 7]], dtype=torch.long),
        "target_positions": torch.tensor([[1, 2], [1, 2]], dtype=torch.long),
    }
    conditional_loss, _ = TRAINER.rollout_loss(model, batch, 2, "conditional-prefix")
    if not bool(torch.isfinite(conditional_loss.detach()).item()):
        raise AssertionError("conditional-prefix loss is not finite")
    conditional_loss_value = float(conditional_loss.detach().item())
    del conditional_loss

    synthetic_samples = [
        {
            "hidden_state": torch.randn(8, 16, dtype=torch.float32),
            "sampled_next_token_ids": torch.randint(0, 64, (8,), dtype=torch.long),
            "_positions": torch.arange(8, dtype=torch.long),
            "_length": 8,
            "_path": "synthetic.pt",
        }
    ]
    refs = [TRAINER.StartRef(0, 0), TRAINER.StartRef(0, 1)]
    smoke_args = argparse.Namespace(
        max_steps=2,
        batch_size=2,
        lr=1e-3,
        weight_decay=0.0,
        grad_clip=1.0,
        epochs=3,
        max_train_steps=1,
        loss_mode="all-steps",
        print_every=0,
        eval_every=0,
        model_dir="<synthetic>",
        model_extra_path="<synthetic>",
        dataset_dir=["<synthetic>"],
        max_samples=0,
        train_starts=2,
        heldout_starts=2,
        seed=27,
        scope="full",
        residual_mode="replace",
        residual_gate_init=0.0,
        draft_lm_head="int4-dequant",
        draft_lm_head_group_size=16,
        draft_lm_head_scale_dtype="bf16",
    )
    base_only, before, after, train_stats = train_refinement(
        model,
        synthetic_samples,
        refs,
        synthetic_samples,
        refs,
        params,
        smoke_args,
        torch.device("cpu"),
        dtype,
    )
    if after["starts"] != 2:
        raise AssertionError("Synthetic accepted-depth evaluation lost starts")
    if train_stats["optimizer_steps"] != 1:
        raise AssertionError("Synthetic --max-train-steps cap was not honored")

    with tempfile.TemporaryDirectory(prefix="qwen27-stacked-mtp-selftest-") as tmp:
        smoke_args.out_dir = tmp
        artifact_path, summary_path = save_outputs(
            model,
            smoke_args,
            synthetic_samples,
            synthetic_samples,
            refs,
            refs,
            trainable_keys,
            base_only,
            before,
            after,
            train_stats,
            torch.device("cpu"),
            dtype,
            0.0,
        )
        tensors = refinement_export_tensors(model)
        loaded = load_file(str(artifact_path), device="cpu")
        if set(loaded) != set(tensors):
            raise AssertionError("Synthetic safetensors export key mismatch")
        if any(tensor.dtype != torch.bfloat16 for tensor in loaded.values()):
            raise AssertionError("Synthetic safetensors export is not all BF16")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("endpoint_candidate_compatible") is not False:
            raise AssertionError("Synthetic summary lost endpoint-incompatible mark")
        if summary.get("valid_headline_throughput") is not False:
            raise AssertionError("Synthetic summary lost diagnostic headline mark")
        if summary["training"]["optimizer_steps"] != 1:
            raise AssertionError("Synthetic summary lost optimizer-step cap result")

    print(
        json.dumps(
            {
                "self_test": "passed",
                "device": "cpu",
                "dtype": "bfloat16",
                "clone_attention_parity": True,
                "clone_mlp_parity": True,
                "causal_prefix_invariance": True,
                "zero_gate_exact_base_parity": True,
                "vector_gate_exported": True,
                "all_steps_loss": train_stats["last_training_loss"],
                "conditional_prefix_loss": conditional_loss_value,
                "accepted_depth_starts": after["starts"],
                "max_train_steps_honored": train_stats["optimizer_steps"] == 1,
                "export_key_count": len(SOURCE_KEYS),
                "scope_param_counts": scope_counts,
                "layer_param_count": sum(
                    parameter.numel() for parameter in layer.parameters()
                ),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    validate_args(args)
    if args.self_test:
        return self_test()

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = EVAL.choose_device(args.device)
    validate_device(device)
    dtype = EVAL.dtype_from_name(args.dtype)
    total_started = time.perf_counter()

    paths = EVAL.iter_sample_paths(args.dataset_dir, args.max_samples)
    samples = TRAINER.load_samples(paths)
    train_samples, heldout_samples = split_samples(samples, args.heldout_samples)
    train_refs = TRAINER.collect_starts(
        train_samples, args.max_steps, args.train_starts
    )
    heldout_refs = TRAINER.collect_starts(
        heldout_samples, args.max_steps, args.heldout_starts
    )
    if not train_refs:
        raise ValueError(
            "No train starts remain at the requested --max-steps; use longer "
            "samples or lower the rollout depth"
        )
    if not heldout_refs:
        raise ValueError(
            "No heldout starts remain at the requested --max-steps; use longer "
            "samples or lower the rollout depth"
        )
    random.shuffle(train_refs)

    config = EVAL.load_config(args.model_dir)
    shape = EVAL.shape_from_config(config)
    if shape.hidden_size % args.draft_lm_head_group_size:
        raise ValueError(
            "--draft-lm-head-group-size must divide hidden_size; got "
            f"{args.draft_lm_head_group_size} and {shape.hidden_size}"
        )
    base_tensors = load_file(args.model_extra_path, device="cpu")
    embed = EVAL.load_indexed_tensor(
        args.model_dir, "model.language_model.embed_tokens.weight"
    )
    lm_head = EVAL.load_indexed_tensor(args.model_dir, "lm_head.weight")
    base_mtp = EVAL.IntrinsicMTP(
        shape=shape,
        tensors=base_tensors,
        embed_weight=embed,
        lm_head_weight=lm_head,
        device=device,
        dtype=dtype,
        use_official_rope=not args.skip_official_rope,
        draft_lm_head=args.draft_lm_head,
        draft_lm_head_group_size=args.draft_lm_head_group_size,
        draft_lm_head_scale_dtype=args.draft_lm_head_scale_dtype,
    ).eval()
    del base_tensors, embed, lm_head
    gc.collect()
    validate_base_depth(base_mtp, args.max_steps)
    model = StackedIntrinsicMTP(
        base_mtp,
        residual_mode=args.residual_mode,
        residual_gate_init=args.residual_gate_init,
    )
    params, trainable_keys = make_refinement_trainable(model, args.scope)

    base_only, before, after, train_stats = train_refinement(
        model,
        train_samples,
        train_refs,
        heldout_samples,
        heldout_refs,
        params,
        args,
        device,
        dtype,
    )
    artifact_path, summary_path = save_outputs(
        model,
        args,
        train_samples,
        heldout_samples,
        train_refs,
        heldout_refs,
        trainable_keys,
        base_only,
        before,
        after,
        train_stats,
        device,
        dtype,
        time.perf_counter() - total_started,
    )
    print(
        f"[stacked-mtp-refinement] wrote diagnostic artifact {artifact_path}",
        flush=True,
    )
    print(
        f"[stacked-mtp-refinement] wrote summary {summary_path}",
        flush=True,
    )
    print(
        "[stacked-mtp-refinement] endpoint-compatible=false "
        "headline-eligible=false runtime-integration-required=true",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        FileNotFoundError,
        FileExistsError,
        NotADirectoryError,
        ValueError,
        RuntimeError,
        FloatingPointError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from None

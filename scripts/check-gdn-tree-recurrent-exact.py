#!/usr/bin/env python3
"""Branch-aware Qwen3.6 GDN tree correctness contract.

This is a synthetic correctness harness, not a benchmark.  It verifies that a
topologically ordered token tree forks width-4 causal-convolution and Gated
DeltaNet recurrent state from each node's logical parent.  The packed branch
executor is checked against an independent root-to-node sequential replay for
every node, then several possible winning paths are promoted into commit rows
and checked exactly.

The projected-input convention matches Qwen3.5/Qwen3.6 GDN:

* ``projected_states_qkvz`` is contiguous ``[q, k, v, z]``;
* ``projected_states_ba`` is contiguous ``[b, a]``;
* convolution applies to raw ``[q, k, v]`` only, while ``z`` is passthrough
  output-gate input and does not affect recurrent state;
* conv state stores the three prior raw projected rows in time-major order;
* SSM state is ``[value_heads, value_dim, key_dim]``.

By default no vLLM or native extension is imported, so the high-level contract
runs on CPU and PyTorch/XPU.  Optional native modes compare the production
depth-batched indexed op and the graph-static whole-tree op against independent
root-to-node native replay.
"""

from __future__ import annotations

import argparse
import importlib
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import torch


CLASSIFICATION = "correctness_harness_not_benchmark"
SCHEMA = "qwen36_gdn_tree_recurrent_exact_v2"
WIDTH = 4
DTYPE_NAMES = ("bf16", "fp16", "fp32")


@dataclass(frozen=True)
class GDNConfig:
    num_k_heads: int
    num_v_heads: int
    head_k_dim: int
    head_v_dim: int
    width: int = WIDTH

    @property
    def q_size(self) -> int:
        return self.num_k_heads * self.head_k_dim

    @property
    def k_size(self) -> int:
        return self.q_size

    @property
    def v_size(self) -> int:
        return self.num_v_heads * self.head_v_dim

    @property
    def z_size(self) -> int:
        return self.v_size

    @property
    def conv_dim(self) -> int:
        return self.q_size + self.k_size + self.v_size

    @property
    def qkvz_dim(self) -> int:
        return self.conv_dim + self.z_size

    @property
    def ba_dim(self) -> int:
        return 2 * self.num_v_heads


@dataclass
class GDNInputs:
    projected_states_qkvz: torch.Tensor
    projected_states_ba: torch.Tensor
    conv_weights: torch.Tensor
    conv_bias: torch.Tensor | None
    A_log: torch.Tensor
    dt_bias: torch.Tensor
    base_conv_state: torch.Tensor
    base_ssm_state: torch.Tensor


@dataclass(frozen=True)
class PackedTreeContract:
    parents: torch.Tensor
    depths: torch.Tensor
    path_lengths: torch.Tensor
    path_table: torch.Tensor
    path_offsets: torch.Tensor
    path_nodes: torch.Tensor
    source_state_rows: torch.Tensor
    destination_state_rows: torch.Tensor
    paths: tuple[tuple[int, ...], ...]
    leaves: tuple[int, ...]
    max_depth: int

    @property
    def num_nodes(self) -> int:
        return int(self.parents.numel())

    def to_json(self) -> dict[str, Any]:
        return {
            "root_parent": -1,
            "path_padding": -1,
            "base_state_row": 0,
            "node_state_row_rule": "node i publishes post-node state to row i+1",
            "source_state_row_rule": ("root reads row 0; node i reads parent[i]+1"),
            "parent_indices": self.parents.tolist(),
            "depths": self.depths.tolist(),
            "path_lengths": self.path_lengths.tolist(),
            "path_table": self.path_table.tolist(),
            "path_offsets": self.path_offsets.tolist(),
            "path_nodes": self.path_nodes.tolist(),
            "source_state_rows": self.source_state_rows.tolist(),
            "destination_state_rows": self.destination_state_rows.tolist(),
            "projected_input_rows": list(range(self.num_nodes)),
            "leaves": list(self.leaves),
            "max_depth": self.max_depth,
            "topologically_ordered": True,
        }


@dataclass
class TreeExecution:
    outputs: torch.Tensor
    conv_state_rows: torch.Tensor
    ssm_state_rows: torch.Tensor

    @property
    def conv_node_states(self) -> torch.Tensor:
        return self.conv_state_rows[1:]

    @property
    def ssm_node_states(self) -> torch.Tensor:
        return self.ssm_state_rows[1:]


@dataclass
class NativeIndexedWorkspace:
    conv_state: torch.Tensor
    ssm_state: torch.Tensor
    output: torch.Tensor
    z: torch.Tensor
    depth_calls: tuple[tuple[torch.Tensor, torch.Tensor, torch.Tensor], ...]
    tree_call: tuple[torch.Tensor, torch.Tensor, torch.Tensor]
    published_rows: torch.Tensor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--device",
        default="cpu",
        help="PyTorch device such as cpu, xpu:0, or auto (default: cpu).",
    )
    parser.add_argument(
        "--dtype",
        action="append",
        choices=DTYPE_NAMES,
        dest="dtypes",
        help="Dtype to check; repeat as needed. Default checks all three.",
    )
    parser.add_argument(
        "--shape",
        action="append",
        choices=(
            "chain",
            "siblings",
            "binary",
            "ddtree16",
            "ddtree_wide_deep",
        ),
        dest="shapes",
        help="Tree shape to check; repeat as needed. Default checks all.",
    )
    parser.add_argument("--seed", type=int, default=20260710)
    parser.add_argument("--num-k-heads", type=int, default=2)
    parser.add_argument("--num-v-heads", type=int, default=4)
    parser.add_argument("--head-k-dim", type=int, default=16)
    parser.add_argument("--head-v-dim", type=int, default=16)
    parser.add_argument(
        "--conv-bias",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include a synthetic convolution bias (default: enabled).",
    )
    parser.add_argument(
        "--atol",
        type=float,
        default=0.0,
        help="Absolute tolerance for branch-vs-path output/state checks.",
    )
    parser.add_argument(
        "--rtol",
        type=float,
        default=0.0,
        help="Relative tolerance for branch-vs-path output/state checks.",
    )
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument(
        "--native-indexed",
        action="store_true",
        help=(
            "also execute torch.ops._xpu_C.gdn_attention_indexed_decode once "
            "per tree depth and compare it with the independent path oracle"
        ),
    )
    parser.add_argument(
        "--native-tree-loop",
        action="store_true",
        help=(
            "also execute the graph-static gdn_attention_tree_indexed_decode "
            "op once for the complete topologically ordered tree"
        ),
    )
    parser.add_argument(
        "--kernel-prefix",
        default="/home/steve/src/vllm-xpu-kernels",
        help="path containing vllm_xpu_kernels._xpu_C",
    )
    parser.add_argument(
        "--native-timing-samples",
        type=int,
        default=0,
        help="XPU-event samples for the depth-batched native tree path",
    )
    parser.add_argument(
        "--native-timing-calls-per-sample",
        type=int,
        default=8,
        help="tree executions between one pair of XPU timing events",
    )
    parser.add_argument(
        "--native-timing-warmup",
        type=int,
        default=8,
        help="untimed native tree executions before event sampling",
    )
    return parser.parse_args()


def dtype_from_name(name: str) -> torch.dtype:
    if name == "bf16":
        return torch.bfloat16
    if name == "fp16":
        return torch.float16
    if name == "fp32":
        return torch.float32
    raise ValueError(f"unsupported dtype: {name}")


def _deduplicate(items: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(items))


def tree_shapes() -> dict[str, tuple[int, ...]]:
    chain = tuple([-1] + list(range(8)))
    siblings = tuple([-1] + [0] * 8)
    binary = tuple([-1] + [(node - 1) // 2 for node in range(1, 15)])
    ddtree16 = (
        -1,
        0,
        0,
        0,
        0,
        1,
        1,
        2,
        2,
        3,
        5,
        5,
        6,
        7,
        10,
        14,
    )

    # Root plus 32 verifier nodes distributed across broad early levels and a
    # six-edge tail.  This resembles a best-first DDTree result without tying
    # the correctness contract to one draft distribution or token vocabulary.
    ddtree_wide_deep = (
        -1,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        1,
        1,
        1,
        2,
        2,
        3,
        4,
        5,
        9,
        9,
        10,
        11,
        12,
        14,
        16,
        17,
        17,
        18,
        20,
        23,
        24,
        25,
        28,
        29,
    )
    return {
        "chain": chain,
        "siblings": siblings,
        "binary": binary,
        "ddtree16": ddtree16,
        "ddtree_wide_deep": ddtree_wide_deep,
    }


def _parents_to_list(parents: Sequence[int] | torch.Tensor) -> list[int]:
    if isinstance(parents, torch.Tensor):
        if parents.ndim != 1:
            raise ValueError("parent indices must be a one-dimensional tensor")
        return [int(value) for value in parents.detach().cpu().tolist()]
    return [int(value) for value in parents]


def build_packed_tree_contract(
    parents: Sequence[int] | torch.Tensor,
) -> PackedTreeContract:
    """Build the logical-tree and physical state-row contract.

    Node zero is a real verifier row.  Its parent ``-1`` selects the pre-tree
    base state row, and its post-token state is published like every other
    node.  A winning node ``-1`` used by the commit check means commit the base
    state without processing a tree row.
    """

    parent_list = _parents_to_list(parents)
    if not parent_list:
        raise ValueError("tree must contain at least one node")
    if parent_list[0] != -1:
        raise ValueError("node 0 must be the root with parent -1")
    if parent_list.count(-1) != 1:
        raise ValueError("tree must contain exactly one root")

    paths: list[tuple[int, ...]] = []
    depths: list[int] = []
    for node, parent in enumerate(parent_list):
        if node == 0:
            paths.append((0,))
            depths.append(0)
            continue
        if parent < 0 or parent >= node:
            raise ValueError(
                f"node {node} parent {parent} is not a prior topological node"
            )
        paths.append(paths[parent] + (node,))
        depths.append(depths[parent] + 1)

    max_path_len = max(len(path) for path in paths)
    path_table = torch.full((len(parent_list), max_path_len), -1, dtype=torch.int32)
    path_nodes: list[int] = []
    path_offsets = [0]
    for node, path in enumerate(paths):
        path_table[node, : len(path)] = torch.tensor(path, dtype=torch.int32)
        path_nodes.extend(path)
        path_offsets.append(len(path_nodes))

    parents_with_children = {parent for parent in parent_list if parent >= 0}
    leaves = tuple(
        node for node in range(len(parent_list)) if node not in parents_with_children
    )
    source_rows = [0 if parent == -1 else parent + 1 for parent in parent_list]
    destination_rows = list(range(1, len(parent_list) + 1))

    return PackedTreeContract(
        parents=torch.tensor(parent_list, dtype=torch.int32),
        depths=torch.tensor(depths, dtype=torch.int32),
        path_lengths=torch.tensor([len(path) for path in paths], dtype=torch.int32),
        path_table=path_table,
        path_offsets=torch.tensor(path_offsets, dtype=torch.int32),
        path_nodes=torch.tensor(path_nodes, dtype=torch.int32),
        source_state_rows=torch.tensor(source_rows, dtype=torch.int32),
        destination_state_rows=torch.tensor(destination_rows, dtype=torch.int32),
        paths=tuple(paths),
        leaves=leaves,
        max_depth=max(depths),
    )


def validate_packed_tree_contract(contract: PackedTreeContract) -> list[str]:
    """Independently reconstruct paths and report contract inconsistencies."""

    errors: list[str] = []
    parents = [int(value) for value in contract.parents.tolist()]
    offsets = [int(value) for value in contract.path_offsets.tolist()]
    flat_paths = [int(value) for value in contract.path_nodes.tolist()]

    if offsets[0] != 0 or offsets[-1] != len(flat_paths):
        errors.append("CSR path offsets do not span path_nodes")
    if len(offsets) != contract.num_nodes + 1:
        errors.append("CSR path offset count must be num_nodes + 1")

    for node, parent in enumerate(parents):
        rebuilt: list[int] = []
        current = node
        while current >= 0:
            rebuilt.append(current)
            current = parents[current]
        rebuilt.reverse()

        length = int(contract.path_lengths[node].item())
        dense = [int(value) for value in contract.path_table[node, :length].tolist()]
        csr = flat_paths[offsets[node] : offsets[node + 1]]
        expected_source = 0 if parent == -1 else parent + 1
        if dense != rebuilt:
            errors.append(f"node {node} dense path does not follow parents")
        if csr != rebuilt:
            errors.append(f"node {node} CSR path does not follow parents")
        if int(contract.depths[node].item()) != len(rebuilt) - 1:
            errors.append(f"node {node} depth does not match its path")
        if int(contract.source_state_rows[node].item()) != expected_source:
            errors.append(f"node {node} source state row is incorrect")
        if int(contract.destination_state_rows[node].item()) != node + 1:
            errors.append(f"node {node} destination state row is incorrect")
        if bool(torch.any(contract.path_table[node, length:] != -1).item()):
            errors.append(f"node {node} dense path padding is not -1")
    return errors


def _randn_fixture(
    generator: torch.Generator,
    shape: tuple[int, ...],
    *,
    scale: float,
    dtype: torch.dtype,
    device: torch.device,
) -> torch.Tensor:
    value = torch.randn(shape, generator=generator, dtype=torch.float32)
    value.mul_(scale)
    return value.to(device=device, dtype=dtype).contiguous()


def build_inputs(
    *,
    num_nodes: int,
    config: GDNConfig,
    dtype: torch.dtype,
    device: torch.device,
    seed: int,
    with_conv_bias: bool,
) -> GDNInputs:
    """Create deterministic fixtures on CPU, then cast and transfer."""

    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    projected_qkvz = _randn_fixture(
        generator,
        (num_nodes, config.qkvz_dim),
        scale=0.35,
        dtype=dtype,
        device=device,
    )
    projected_ba = _randn_fixture(
        generator,
        (num_nodes, config.ba_dim),
        scale=0.4,
        dtype=dtype,
        device=device,
    )
    conv_weights = _randn_fixture(
        generator,
        (config.conv_dim, config.width),
        scale=0.2,
        dtype=dtype,
        device=device,
    )
    conv_bias = (
        _randn_fixture(
            generator,
            (config.conv_dim,),
            scale=0.03,
            dtype=dtype,
            device=device,
        )
        if with_conv_bias
        else None
    )
    A_log = _randn_fixture(
        generator,
        (config.num_v_heads,),
        scale=0.15,
        dtype=torch.float32,
        device=device,
    )
    dt_bias = _randn_fixture(
        generator,
        (config.num_v_heads,),
        scale=0.2,
        dtype=dtype,
        device=device,
    )
    base_conv = _randn_fixture(
        generator,
        (config.width - 1, config.conv_dim),
        scale=0.25,
        dtype=dtype,
        device=device,
    )
    base_ssm = _randn_fixture(
        generator,
        (
            config.num_v_heads,
            config.head_v_dim,
            config.head_k_dim,
        ),
        scale=0.05,
        dtype=dtype,
        device=device,
    )
    return GDNInputs(
        projected_states_qkvz=projected_qkvz,
        projected_states_ba=projected_ba,
        conv_weights=conv_weights,
        conv_bias=conv_bias,
        A_log=A_log,
        dt_bias=dt_bias,
        base_conv_state=base_conv,
        base_ssm_state=base_ssm,
    )


def validate_inputs(
    inputs: GDNInputs,
    config: GDNConfig,
    *,
    num_nodes: int,
) -> None:
    if config.width != WIDTH:
        raise ValueError(f"this contract requires causal-conv width {WIDTH}")
    if config.num_v_heads % config.num_k_heads != 0:
        raise ValueError("num_v_heads must be divisible by num_k_heads")

    expected_shapes = {
        "projected_states_qkvz": (num_nodes, config.qkvz_dim),
        "projected_states_ba": (num_nodes, config.ba_dim),
        "conv_weights": (config.conv_dim, config.width),
        "A_log": (config.num_v_heads,),
        "dt_bias": (config.num_v_heads,),
        "base_conv_state": (config.width - 1, config.conv_dim),
        "base_ssm_state": (
            config.num_v_heads,
            config.head_v_dim,
            config.head_k_dim,
        ),
    }
    for name, expected in expected_shapes.items():
        observed = tuple(getattr(inputs, name).shape)
        if observed != expected:
            raise ValueError(f"{name} shape {observed} != expected {expected}")
    if inputs.conv_bias is not None:
        if tuple(inputs.conv_bias.shape) != (config.conv_dim,):
            raise ValueError("conv_bias shape does not match conv channels")

    activation_dtype = inputs.projected_states_qkvz.dtype
    activation_tensors = (
        inputs.projected_states_ba,
        inputs.conv_weights,
        inputs.dt_bias,
        inputs.base_conv_state,
        inputs.base_ssm_state,
    )
    if inputs.conv_bias is not None:
        activation_tensors += (inputs.conv_bias,)
    if any(tensor.dtype != activation_dtype for tensor in activation_tensors):
        raise ValueError("projected, conv, dt_bias, and cache tensors need one dtype")
    if inputs.A_log.dtype != torch.float32:
        raise ValueError("A_log must be FP32")

    device = inputs.projected_states_qkvz.device
    all_tensors = activation_tensors + (inputs.A_log,)
    if any(tensor.device != device for tensor in all_tensors):
        raise ValueError("all GDN inputs must be on one device")


def _threshold_softplus(value: torch.Tensor) -> torch.Tensor:
    return torch.where(
        value <= 20.0,
        torch.log1p(torch.exp(value)),
        value,
    )


def _branch_conv_step(
    raw_qkv: torch.Tensor,
    source_conv: torch.Tensor,
    inputs: GDNInputs,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Batched width-4 conv with activation-dtype product rounding."""

    window = torch.cat((source_conv, raw_qkv.unsqueeze(1)), dim=1)
    if inputs.conv_bias is None:
        accumulator = torch.zeros(
            (raw_qkv.size(0), raw_qkv.size(1)),
            dtype=torch.float32,
            device=raw_qkv.device,
        )
    else:
        accumulator = (
            inputs.conv_bias.float().unsqueeze(0).expand(raw_qkv.size(0), -1).clone()
        )
    for position in range(WIDTH):
        # Both operands remain in activation dtype for multiply.  Converting
        # the rounded product, rather than the operands, is required parity.
        product = (
            window[:, position, :] * inputs.conv_weights[:, position].unsqueeze(0)
        ).float()
        accumulator = accumulator + product
    activated = accumulator / (1.0 + torch.exp(-accumulator))
    next_conv = window[:, 1:, :].contiguous()
    return activated.to(raw_qkv.dtype), next_conv


def _branch_delta_step(
    mixed_qkv: torch.Tensor,
    projected_ba: torch.Tensor,
    source_ssm: torch.Tensor,
    inputs: GDNInputs,
    config: GDNConfig,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Batched exact one-token Gated DeltaNet recurrence in FP32."""

    batch = mixed_qkv.size(0)
    q_end = config.q_size
    k_end = q_end + config.k_size
    q = mixed_qkv[:, :q_end].reshape(batch, config.num_k_heads, config.head_k_dim)
    k = mixed_qkv[:, q_end:k_end].reshape(batch, config.num_k_heads, config.head_k_dim)
    v = mixed_qkv[:, k_end:].reshape(batch, config.num_v_heads, config.head_v_dim)
    b, a = projected_ba.split(config.num_v_heads, dim=-1)

    q_float = q.float()
    k_float = k.float()
    q_float = q_float * torch.rsqrt(
        (q_float * q_float).sum(dim=-1, keepdim=True) + 1e-6
    )
    k_float = k_float * torch.rsqrt(
        (k_float * k_float).sum(dim=-1, keepdim=True) + 1e-6
    )
    q_float = q_float * (config.head_k_dim**-0.5)

    kv_ratio = config.num_v_heads // config.num_k_heads
    head_map = (
        torch.arange(config.num_v_heads, dtype=torch.long, device=mixed_qkv.device)
        // kv_ratio
    )
    q_hv = q_float.index_select(1, head_map)
    k_hv = k_float.index_select(1, head_map)

    x = a.float() + inputs.dt_bias.float().unsqueeze(0)
    negative_A = -torch.exp(inputs.A_log.float()).unsqueeze(0)
    decay = torch.exp(negative_A * _threshold_softplus(x))
    beta = torch.sigmoid(b.float())

    decayed_state = source_ssm.float() * decay[:, :, None, None]
    predicted_value = (decayed_state * k_hv[:, :, None, :]).sum(dim=-1)
    delta = (v.float() - predicted_value) * beta[:, :, None]
    next_state_float = decayed_state + delta[:, :, :, None] * k_hv[:, :, None, :]
    output_float = (next_state_float * q_hv[:, :, None, :]).sum(dim=-1)

    # A child reads the published cache dtype, just like independent one-token
    # decode.  The current output is formed before this publication cast.
    return output_float.to(mixed_qkv.dtype), next_state_float.to(source_ssm.dtype)


def run_packed_branch_reference(
    contract: PackedTreeContract,
    inputs: GDNInputs,
    config: GDNConfig,
) -> TreeExecution:
    """Execute each node once, forking from its packed parent state row."""

    validate_inputs(inputs, config, num_nodes=contract.num_nodes)
    device = inputs.projected_states_qkvz.device
    dtype = inputs.projected_states_qkvz.dtype
    num_rows = contract.num_nodes + 1
    conv_rows = torch.empty(
        (num_rows, config.width - 1, config.conv_dim),
        dtype=dtype,
        device=device,
    )
    ssm_rows = torch.empty(
        (
            num_rows,
            config.num_v_heads,
            config.head_v_dim,
            config.head_k_dim,
        ),
        dtype=dtype,
        device=device,
    )
    outputs = torch.empty(
        (contract.num_nodes, config.num_v_heads, config.head_v_dim),
        dtype=dtype,
        device=device,
    )
    conv_rows[0].copy_(inputs.base_conv_state)
    ssm_rows[0].copy_(inputs.base_ssm_state)

    for depth in range(contract.max_depth + 1):
        nodes_cpu = torch.nonzero(contract.depths == depth, as_tuple=False).flatten()
        nodes = nodes_cpu.to(device=device, dtype=torch.long)
        source_rows = contract.source_state_rows.index_select(0, nodes_cpu).to(
            device=device, dtype=torch.long
        )
        destination_rows = contract.destination_state_rows.index_select(
            0, nodes_cpu
        ).to(device=device, dtype=torch.long)

        raw_qkv = inputs.projected_states_qkvz.index_select(0, nodes)[
            :, : config.conv_dim
        ]
        mixed_qkv, next_conv = _branch_conv_step(
            raw_qkv,
            conv_rows.index_select(0, source_rows),
            inputs,
        )
        node_outputs, next_ssm = _branch_delta_step(
            mixed_qkv,
            inputs.projected_states_ba.index_select(0, nodes),
            ssm_rows.index_select(0, source_rows),
            inputs,
            config,
        )
        conv_rows.index_copy_(0, destination_rows, next_conv)
        ssm_rows.index_copy_(0, destination_rows, next_ssm)
        outputs.index_copy_(0, nodes, node_outputs)

    return TreeExecution(outputs, conv_rows, ssm_rows)


def _sequential_token_step(
    node: int,
    conv_state: torch.Tensor,
    ssm_state: torch.Tensor,
    inputs: GDNInputs,
    config: GDNConfig,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Independent scalar-path implementation of one GDN token."""

    raw = inputs.projected_states_qkvz[node, : config.conv_dim]
    window = torch.cat((conv_state, raw.unsqueeze(0)), dim=0)
    if inputs.conv_bias is None:
        accumulator = torch.zeros(
            (config.conv_dim,), dtype=torch.float32, device=raw.device
        )
    else:
        accumulator = inputs.conv_bias.float().clone()
    for position in range(WIDTH):
        rounded_product = (window[position] * inputs.conv_weights[:, position]).to(
            torch.float32
        )
        accumulator = accumulator + rounded_product
    mixed = (accumulator / (1.0 + torch.exp(-accumulator))).to(raw.dtype)
    next_conv = window[1:].contiguous()

    q_end = config.q_size
    k_end = q_end + config.k_size
    q = mixed[:q_end].reshape(config.num_k_heads, config.head_k_dim).float()
    k = mixed[q_end:k_end].reshape(config.num_k_heads, config.head_k_dim).float()
    v = mixed[k_end:].reshape(config.num_v_heads, config.head_v_dim).float()
    projected_ba = inputs.projected_states_ba[node]
    b = projected_ba[: config.num_v_heads].float()
    a = projected_ba[config.num_v_heads :].float()

    q = q * torch.rsqrt((q * q).sum(dim=-1, keepdim=True) + 1e-6)
    k = k * torch.rsqrt((k * k).sum(dim=-1, keepdim=True) + 1e-6)
    q = q * (config.head_k_dim**-0.5)
    kv_ratio = config.num_v_heads // config.num_k_heads
    head_map = (
        torch.arange(config.num_v_heads, dtype=torch.long, device=q.device) // kv_ratio
    )
    q_hv = q.index_select(0, head_map)
    k_hv = k.index_select(0, head_map)

    x = a + inputs.dt_bias.float()
    softplus_x = torch.where(
        x <= 20.0,
        torch.log1p(torch.exp(x)),
        x,
    )
    decay = torch.exp(-torch.exp(inputs.A_log.float()) * softplus_x)
    beta = torch.sigmoid(b)
    decayed = ssm_state.float() * decay[:, None, None]
    predicted = (decayed * k_hv[:, None, :]).sum(dim=-1)
    delta = (v - predicted) * beta[:, None]
    next_state_float = decayed + delta[:, :, None] * k_hv[:, None, :]
    output = (next_state_float * q_hv[:, None, :]).sum(dim=-1)
    return (
        output.to(raw.dtype),
        next_conv,
        next_state_float.to(ssm_state.dtype),
    )


def run_independent_path_reference(
    contract: PackedTreeContract,
    inputs: GDNInputs,
    config: GDNConfig,
) -> TreeExecution:
    """Replay every root-to-node path from base without parent state rows."""

    validate_inputs(inputs, config, num_nodes=contract.num_nodes)
    outputs: list[torch.Tensor] = []
    conv_states: list[torch.Tensor] = []
    ssm_states: list[torch.Tensor] = []
    for path in contract.paths:
        conv = inputs.base_conv_state.clone()
        ssm = inputs.base_ssm_state.clone()
        output: torch.Tensor | None = None
        for path_node in path:
            output, conv, ssm = _sequential_token_step(
                path_node, conv, ssm, inputs, config
            )
        if output is None:
            raise AssertionError("a tree node path cannot be empty")
        outputs.append(output)
        conv_states.append(conv)
        ssm_states.append(ssm)

    return TreeExecution(
        outputs=torch.stack(outputs),
        conv_state_rows=torch.cat(
            (inputs.base_conv_state.unsqueeze(0), torch.stack(conv_states)), dim=0
        ),
        ssm_state_rows=torch.cat(
            (inputs.base_ssm_state.unsqueeze(0), torch.stack(ssm_states)), dim=0
        ),
    )


def run_flattened_negative_control(
    contract: PackedTreeContract,
    inputs: GDNInputs,
    config: GDNConfig,
) -> TreeExecution:
    """Deliberately process topological rows as one invalid sequential chain."""

    conv = inputs.base_conv_state.clone()
    ssm = inputs.base_ssm_state.clone()
    outputs: list[torch.Tensor] = []
    conv_states: list[torch.Tensor] = []
    ssm_states: list[torch.Tensor] = []
    for node in range(contract.num_nodes):
        output, conv, ssm = _sequential_token_step(node, conv, ssm, inputs, config)
        outputs.append(output)
        conv_states.append(conv)
        ssm_states.append(ssm)
    return TreeExecution(
        outputs=torch.stack(outputs),
        conv_state_rows=torch.cat(
            (inputs.base_conv_state.unsqueeze(0), torch.stack(conv_states)), dim=0
        ),
        ssm_state_rows=torch.cat(
            (inputs.base_ssm_state.unsqueeze(0), torch.stack(ssm_states)), dim=0
        ),
    )


def run_native_indexed_tree(
    contract: PackedTreeContract,
    inputs: GDNInputs,
    config: GDNConfig,
) -> tuple[TreeExecution, torch.Tensor]:
    """Run the existing XPU parent-source op in race-free depth batches.

    Native row zero is treated as a null/sentinel by the indexed kernels, so
    this harness stores the pre-tree base at row one and node ``i`` at row
    ``i + 2``. Every source row is therefore positive. Nodes at one depth have
    no dependencies on each other and can share a launch; a child depth is
    submitted only after its parent depth on the same in-order XPU queue.
    """

    if inputs.projected_states_qkvz.device.type != "xpu":
        raise ValueError("native indexed tree execution requires an XPU device")
    if config.head_k_dim % 32 != 0:
        raise ValueError("native indexed GDN requires head_k_dim divisible by 32")
    if not hasattr(torch.ops._xpu_C, "gdn_attention_indexed_decode"):
        raise RuntimeError(
            "torch.ops._xpu_C.gdn_attention_indexed_decode is unavailable"
        )

    device = inputs.projected_states_qkvz.device
    dtype = inputs.projected_states_qkvz.dtype
    native_row_count = contract.num_nodes + 2
    base_row = 1
    native_conv = torch.zeros(
        (native_row_count, config.width - 1, config.conv_dim),
        dtype=dtype,
        device=device,
    )
    native_ssm = torch.zeros(
        (
            native_row_count,
            config.num_v_heads,
            config.head_v_dim,
            config.head_k_dim,
        ),
        dtype=dtype,
        device=device,
    )
    native_conv[base_row].copy_(inputs.base_conv_state)
    native_ssm[base_row].copy_(inputs.base_ssm_state)
    native_out = torch.empty(
        (contract.num_nodes, config.num_v_heads, config.head_v_dim),
        dtype=dtype,
        device=device,
    )
    native_z = torch.empty_like(native_out)

    for depth in range(contract.max_depth + 1):
        nodes_cpu = torch.nonzero(contract.depths == depth, as_tuple=False).flatten()
        token_indices = nodes_cpu.to(device=device, dtype=torch.int32)
        state_indices = (nodes_cpu + 2).to(device=device, dtype=torch.int32)
        parents = contract.parents.index_select(0, nodes_cpu)
        source_indices = torch.where(
            parents < 0,
            torch.full_like(parents, base_row),
            parents + 2,
        ).to(device=device, dtype=torch.int32)
        torch.ops._xpu_C.gdn_attention_indexed_decode(
            native_out,
            native_z,
            inputs.projected_states_qkvz,
            inputs.projected_states_ba,
            config.num_k_heads,
            config.num_v_heads,
            config.head_k_dim,
            config.head_v_dim,
            native_conv,
            native_ssm,
            inputs.conv_weights,
            inputs.conv_bias,
            "silu",
            inputs.A_log,
            inputs.dt_bias,
            token_indices,
            state_indices,
            source_indices,
            int(nodes_cpu.numel()),
            contract.num_nodes,
            1,
            True,
        )

    published_rows = torch.cat(
        (
            torch.tensor([base_row], device=device, dtype=torch.long),
            torch.arange(2, native_row_count, device=device, dtype=torch.long),
        )
    )
    return (
        TreeExecution(
            outputs=native_out,
            conv_state_rows=native_conv.index_select(0, published_rows),
            ssm_state_rows=native_ssm.index_select(0, published_rows),
        ),
        native_z,
    )


def prepare_native_indexed_workspace(
    contract: PackedTreeContract,
    inputs: GDNInputs,
    config: GDNConfig,
) -> NativeIndexedWorkspace:
    device = inputs.projected_states_qkvz.device
    dtype = inputs.projected_states_qkvz.dtype
    native_row_count = contract.num_nodes + 2
    base_row = 1
    native_conv = torch.zeros(
        (native_row_count, config.width - 1, config.conv_dim),
        dtype=dtype,
        device=device,
    )
    native_ssm = torch.zeros(
        (
            native_row_count,
            config.num_v_heads,
            config.head_v_dim,
            config.head_k_dim,
        ),
        dtype=dtype,
        device=device,
    )
    native_conv[base_row].copy_(inputs.base_conv_state)
    native_ssm[base_row].copy_(inputs.base_ssm_state)
    native_out = torch.empty(
        (contract.num_nodes, config.num_v_heads, config.head_v_dim),
        dtype=dtype,
        device=device,
    )
    native_z = torch.empty_like(native_out)
    depth_calls: list[tuple[torch.Tensor, torch.Tensor, torch.Tensor]] = []
    for depth in range(contract.max_depth + 1):
        nodes_cpu = torch.nonzero(contract.depths == depth, as_tuple=False).flatten()
        token_indices = nodes_cpu.to(device=device, dtype=torch.int32)
        state_indices = (nodes_cpu + 2).to(device=device, dtype=torch.int32)
        parents = contract.parents.index_select(0, nodes_cpu)
        source_indices = torch.where(
            parents < 0,
            torch.full_like(parents, base_row),
            parents + 2,
        ).to(device=device, dtype=torch.int32)
        depth_calls.append((token_indices, state_indices, source_indices))
    all_nodes = torch.arange(contract.num_nodes, dtype=torch.int32)
    all_parents = contract.parents.to(dtype=torch.int32)
    tree_call = (
        all_nodes.to(device=device),
        (all_nodes + 2).to(device=device),
        torch.where(
            all_parents < 0,
            torch.full_like(all_parents, base_row),
            all_parents + 2,
        ).to(device=device),
    )
    published_rows = torch.cat(
        (
            torch.tensor([base_row], device=device, dtype=torch.long),
            torch.arange(2, native_row_count, device=device, dtype=torch.long),
        )
    )
    return NativeIndexedWorkspace(
        conv_state=native_conv,
        ssm_state=native_ssm,
        output=native_out,
        z=native_z,
        depth_calls=tuple(depth_calls),
        tree_call=tree_call,
        published_rows=published_rows,
    )


def execute_native_indexed_workspace(
    workspace: NativeIndexedWorkspace,
    inputs: GDNInputs,
    config: GDNConfig,
    num_nodes: int,
) -> None:
    for token_indices, state_indices, source_indices in workspace.depth_calls:
        torch.ops._xpu_C.gdn_attention_indexed_decode(
            workspace.output,
            workspace.z,
            inputs.projected_states_qkvz,
            inputs.projected_states_ba,
            config.num_k_heads,
            config.num_v_heads,
            config.head_k_dim,
            config.head_v_dim,
            workspace.conv_state,
            workspace.ssm_state,
            inputs.conv_weights,
            inputs.conv_bias,
            "silu",
            inputs.A_log,
            inputs.dt_bias,
            token_indices,
            state_indices,
            source_indices,
            int(token_indices.numel()),
            num_nodes,
            1,
            True,
        )


def execute_native_tree_loop_workspace(
    workspace: NativeIndexedWorkspace,
    inputs: GDNInputs,
    config: GDNConfig,
    num_nodes: int,
) -> None:
    token_indices, state_indices, source_indices = workspace.tree_call
    torch.ops._xpu_C.gdn_attention_tree_indexed_decode(
        workspace.output,
        workspace.z,
        inputs.projected_states_qkvz,
        inputs.projected_states_ba,
        config.num_k_heads,
        config.num_v_heads,
        config.head_k_dim,
        config.head_v_dim,
        workspace.conv_state,
        workspace.ssm_state,
        inputs.conv_weights,
        inputs.conv_bias,
        "silu",
        inputs.A_log,
        inputs.dt_bias,
        token_indices,
        state_indices,
        source_indices,
        num_nodes,
        num_nodes,
        1,
        True,
    )


def run_native_tree_loop(
    contract: PackedTreeContract,
    inputs: GDNInputs,
    config: GDNConfig,
) -> tuple[TreeExecution, torch.Tensor]:
    if not hasattr(torch.ops._xpu_C, "gdn_attention_tree_indexed_decode"):
        raise RuntimeError(
            "torch.ops._xpu_C.gdn_attention_tree_indexed_decode is unavailable"
        )
    workspace = prepare_native_indexed_workspace(contract, inputs, config)
    execute_native_tree_loop_workspace(workspace, inputs, config, contract.num_nodes)
    return (
        TreeExecution(
            outputs=workspace.output,
            conv_state_rows=workspace.conv_state.index_select(
                0, workspace.published_rows
            ),
            ssm_state_rows=workspace.ssm_state.index_select(
                0, workspace.published_rows
            ),
        ),
        workspace.z,
    )


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def benchmark_native_indexed_tree(
    contract: PackedTreeContract,
    inputs: GDNInputs,
    config: GDNConfig,
    *,
    warmup: int,
    samples: int,
    calls_per_sample: int,
) -> dict[str, Any]:
    workspace = prepare_native_indexed_workspace(contract, inputs, config)
    for _ in range(warmup):
        execute_native_indexed_workspace(workspace, inputs, config, contract.num_nodes)
    torch.xpu.synchronize(inputs.projected_states_qkvz.device)

    samples_ms: list[float] = []
    for _ in range(samples):
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(calls_per_sample):
            execute_native_indexed_workspace(
                workspace, inputs, config, contract.num_nodes
            )
        end.record()
        end.synchronize()
        samples_ms.append(float(start.elapsed_time(end)) / calls_per_sample)

    return {
        "classification": "diagnostic_device_event_not_endpoint",
        "timer": "XPU event; reusable tensors; allocations excluded",
        "samples": samples,
        "calls_per_sample": calls_per_sample,
        "warmup_calls": warmup,
        "tree_depth_launches": len(workspace.depth_calls),
        "native_ops_per_tree": len(workspace.depth_calls),
        "underlying_conv_plus_gdn_kernels_per_tree": 2 * len(workspace.depth_calls),
        "per_tree_ms": {
            "median": statistics.median(samples_ms),
            "mean": statistics.fmean(samples_ms),
            "p10": _percentile(samples_ms, 0.10),
            "p90": _percentile(samples_ms, 0.90),
            "min": min(samples_ms),
            "max": max(samples_ms),
            "population_stdev": (
                statistics.pstdev(samples_ms) if len(samples_ms) > 1 else 0.0
            ),
        },
    }


def benchmark_native_tree_loop(
    contract: PackedTreeContract,
    inputs: GDNInputs,
    config: GDNConfig,
    *,
    warmup: int,
    samples: int,
    calls_per_sample: int,
) -> dict[str, Any]:
    workspace = prepare_native_indexed_workspace(contract, inputs, config)
    for _ in range(warmup):
        execute_native_tree_loop_workspace(
            workspace, inputs, config, contract.num_nodes
        )
    torch.xpu.synchronize(inputs.projected_states_qkvz.device)

    samples_ms: list[float] = []
    for _ in range(samples):
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(calls_per_sample):
            execute_native_tree_loop_workspace(
                workspace, inputs, config, contract.num_nodes
            )
        end.record()
        end.synchronize()
        samples_ms.append(float(start.elapsed_time(end)) / calls_per_sample)

    return {
        "classification": "diagnostic_device_event_not_endpoint",
        "timer": "XPU event; reusable tensors; allocations excluded",
        "samples": samples,
        "calls_per_sample": calls_per_sample,
        "warmup_calls": warmup,
        "tree_depth_launches": 1,
        "native_ops_per_tree": 1,
        "underlying_conv_plus_gdn_kernels_per_tree": 2,
        "per_tree_ms": {
            "median": statistics.median(samples_ms),
            "mean": statistics.fmean(samples_ms),
            "p10": _percentile(samples_ms, 0.10),
            "p90": _percentile(samples_ms, 0.90),
            "min": min(samples_ms),
            "max": max(samples_ms),
            "population_stdev": (
                statistics.pstdev(samples_ms) if len(samples_ms) > 1 else 0.0
            ),
        },
    }


def run_native_independent_paths(
    contract: PackedTreeContract,
    inputs: GDNInputs,
    config: GDNConfig,
) -> tuple[TreeExecution, torch.Tensor]:
    """Replay every root-to-node path with the production one-token op.

    This is the bit-exact native oracle. The high-level PyTorch recurrence is
    mathematically equivalent, but subgroup reduction order can differ by one
    BF16/FP16 publication unit and therefore cannot define native bit parity.
    """

    device = inputs.projected_states_qkvz.device
    dtype = inputs.projected_states_qkvz.dtype
    native_row_count = contract.num_nodes + 1
    native_conv = torch.empty(
        (native_row_count, config.width - 1, config.conv_dim),
        dtype=dtype,
        device=device,
    )
    native_ssm = torch.empty(
        (
            native_row_count,
            config.num_v_heads,
            config.head_v_dim,
            config.head_k_dim,
        ),
        dtype=dtype,
        device=device,
    )
    native_conv[0].copy_(inputs.base_conv_state)
    native_ssm[0].copy_(inputs.base_ssm_state)
    native_conv[1:].copy_(inputs.base_conv_state.unsqueeze(0))
    native_ssm[1:].copy_(inputs.base_ssm_state.unsqueeze(0))
    native_out = torch.empty(
        (contract.num_nodes, config.num_v_heads, config.head_v_dim),
        dtype=dtype,
        device=device,
    )
    native_z = torch.empty_like(native_out)

    for node, path in enumerate(contract.paths):
        state_row = torch.tensor([node + 1], device=device, dtype=torch.int32)
        for path_node in path:
            token_index = torch.tensor([path_node], device=device, dtype=torch.int32)
            torch.ops._xpu_C.gdn_attention_indexed_decode(
                native_out,
                native_z,
                inputs.projected_states_qkvz,
                inputs.projected_states_ba,
                config.num_k_heads,
                config.num_v_heads,
                config.head_k_dim,
                config.head_v_dim,
                native_conv,
                native_ssm,
                inputs.conv_weights,
                inputs.conv_bias,
                "silu",
                inputs.A_log,
                inputs.dt_bias,
                token_index,
                state_row,
                None,
                1,
                contract.num_nodes,
                1,
                True,
            )

    return TreeExecution(native_out, native_conv, native_ssm), native_z


def tensor_comparison(
    left: torch.Tensor,
    right: torch.Tensor,
    *,
    atol: float,
    rtol: float,
) -> dict[str, Any]:
    left_float = left.float()
    right_float = right.float()
    finite = bool(
        (torch.isfinite(left_float).all() & torch.isfinite(right_float).all())
        .detach()
        .cpu()
        .item()
    )
    max_abs = float((left_float - right_float).abs().max().detach().cpu().item())
    return {
        "equal": bool(torch.equal(left, right)),
        "close": bool(torch.allclose(left_float, right_float, atol=atol, rtol=rtol)),
        "finite": finite,
        "max_abs_diff": max_abs,
    }


def select_winning_nodes(contract: PackedTreeContract) -> list[int]:
    """Select base, internal, and divergent leaf outcomes for commit checks."""

    deepest = [
        node
        for node, depth in enumerate(contract.depths.tolist())
        if int(depth) == contract.max_depth
    ]
    candidates = [
        -1,
        0,
        contract.num_nodes // 2,
        contract.num_nodes - 1,
        contract.leaves[0],
        contract.leaves[len(contract.leaves) // 2],
        contract.leaves[-1],
        deepest[0],
        deepest[-1],
    ]
    return list(dict.fromkeys(candidates))


def validate_winning_commits(
    contract: PackedTreeContract,
    branch: TreeExecution,
    oracle: TreeExecution,
    *,
    atol: float,
    rtol: float,
) -> dict[str, Any]:
    winners = select_winning_nodes(contract)
    device = branch.outputs.device
    source_rows = torch.tensor(
        [0 if node == -1 else node + 1 for node in winners],
        dtype=torch.long,
        device=device,
    )
    first_commit_row = contract.num_nodes + 1
    commit_rows = torch.arange(
        first_commit_row,
        first_commit_row + len(winners),
        dtype=torch.long,
        device=device,
    )

    conv_table = torch.cat(
        (
            branch.conv_state_rows,
            torch.empty(
                (len(winners), *branch.conv_state_rows.shape[1:]),
                dtype=branch.conv_state_rows.dtype,
                device=device,
            ),
        ),
        dim=0,
    )
    ssm_table = torch.cat(
        (
            branch.ssm_state_rows,
            torch.empty(
                (len(winners), *branch.ssm_state_rows.shape[1:]),
                dtype=branch.ssm_state_rows.dtype,
                device=device,
            ),
        ),
        dim=0,
    )
    selected_conv = conv_table.index_select(0, source_rows).clone()
    selected_ssm = ssm_table.index_select(0, source_rows).clone()
    conv_table.index_copy_(0, commit_rows, selected_conv)
    ssm_table.index_copy_(0, commit_rows, selected_ssm)
    observed_conv = conv_table.index_select(0, commit_rows)
    observed_ssm = ssm_table.index_select(0, commit_rows)
    expected_conv = oracle.conv_state_rows.index_select(0, source_rows)
    expected_ssm = oracle.ssm_state_rows.index_select(0, source_rows)

    copy_conv = tensor_comparison(observed_conv, selected_conv, atol=0.0, rtol=0.0)
    copy_ssm = tensor_comparison(observed_ssm, selected_ssm, atol=0.0, rtol=0.0)
    oracle_conv = tensor_comparison(observed_conv, expected_conv, atol=atol, rtol=rtol)
    oracle_ssm = tensor_comparison(observed_ssm, expected_ssm, atol=atol, rtol=rtol)
    winner_rows = []
    for node, source_row, commit_row in zip(
        winners,
        source_rows.detach().cpu().tolist(),
        commit_rows.detach().cpu().tolist(),
    ):
        winner_rows.append(
            {
                "winner_node": node,
                "path": [] if node == -1 else list(contract.paths[node]),
                "source_state_row": int(source_row),
                "commit_state_row": int(commit_row),
            }
        )

    passed = bool(
        copy_conv["equal"]
        and copy_ssm["equal"]
        and oracle_conv["close"]
        and oracle_ssm["close"]
    )
    return {
        "winners": winner_rows,
        "copy_conv": copy_conv,
        "copy_ssm": copy_ssm,
        "sequential_oracle_conv": oracle_conv,
        "sequential_oracle_ssm": oracle_ssm,
        "exact_equality_required": "state-row copy; oracle uses configured tolerance",
        "passed": passed,
    }


def compare_native_execution(
    *,
    execution: str,
    contract: PackedTreeContract,
    inputs: GDNInputs,
    config: GDNConfig,
    native: TreeExecution,
    native_z: torch.Tensor,
    native_oracle: TreeExecution,
    native_oracle_z: torch.Tensor,
    math_oracle: TreeExecution,
    atol: float,
    rtol: float,
) -> tuple[dict[str, Any], bool]:
    native_output = tensor_comparison(
        native.outputs, native_oracle.outputs, atol=0.0, rtol=0.0
    )
    native_conv = tensor_comparison(
        native.conv_node_states,
        native_oracle.conv_node_states,
        atol=0.0,
        rtol=0.0,
    )
    native_ssm = tensor_comparison(
        native.ssm_node_states,
        native_oracle.ssm_node_states,
        atol=0.0,
        rtol=0.0,
    )
    expected_z = inputs.projected_states_qkvz[:, config.conv_dim :].reshape(
        contract.num_nodes, config.num_v_heads, config.head_v_dim
    )
    native_z_check = tensor_comparison(native_z, expected_z, atol=0.0, rtol=0.0)
    native_oracle_z_check = tensor_comparison(
        native_oracle_z, expected_z, atol=0.0, rtol=0.0
    )
    native_commit = validate_winning_commits(
        contract, native, native_oracle, atol=0.0, rtol=0.0
    )
    math_output = tensor_comparison(
        native.outputs, math_oracle.outputs, atol=atol, rtol=rtol
    )
    math_conv = tensor_comparison(
        native.conv_node_states,
        math_oracle.conv_node_states,
        atol=atol,
        rtol=rtol,
    )
    math_ssm = tensor_comparison(
        native.ssm_node_states,
        math_oracle.ssm_node_states,
        atol=atol,
        rtol=rtol,
    )
    passed = bool(
        native_output["equal"]
        and native_conv["equal"]
        and native_ssm["equal"]
        and native_z_check["equal"]
        and native_oracle_z_check["equal"]
        and native_commit["passed"]
    )
    return (
        {
            "execution": execution,
            "base_native_state_row": 1,
            "node_native_state_row_rule": "node i publishes to row i+2",
            "outputs": native_output,
            "conv_states": native_conv,
            "ssm_states": native_ssm,
            "z_passthrough": native_z_check,
            "independent_path_z_passthrough": native_oracle_z_check,
            "winning_path_commits": native_commit,
            "python_math_reference_descriptive": {
                "gating": "not used for native bit-exact pass/fail",
                "outputs": math_output,
                "conv_states": math_conv,
                "ssm_states": math_ssm,
            },
            "passed": passed,
        },
        passed,
    )


def run_case(
    *,
    shape_name: str,
    contract: PackedTreeContract,
    dtype_name: str,
    config: GDNConfig,
    device: torch.device,
    seed: int,
    with_conv_bias: bool,
    atol: float,
    rtol: float,
    native_indexed: bool,
    native_tree_loop: bool,
    native_timing_samples: int,
    native_timing_calls_per_sample: int,
    native_timing_warmup: int,
) -> dict[str, Any]:
    dtype = dtype_from_name(dtype_name)
    inputs = build_inputs(
        num_nodes=contract.num_nodes,
        config=config,
        dtype=dtype,
        device=device,
        seed=seed,
        with_conv_bias=with_conv_bias,
    )
    with torch.no_grad():
        branch = run_packed_branch_reference(contract, inputs, config)
        oracle = run_independent_path_reference(contract, inputs, config)
        flattened = run_flattened_negative_control(contract, inputs, config)

    output_check = tensor_comparison(
        branch.outputs, oracle.outputs, atol=atol, rtol=rtol
    )
    conv_check = tensor_comparison(
        branch.conv_node_states,
        oracle.conv_node_states,
        atol=atol,
        rtol=rtol,
    )
    ssm_check = tensor_comparison(
        branch.ssm_node_states,
        oracle.ssm_node_states,
        atol=atol,
        rtol=rtol,
    )
    base_conv_check = tensor_comparison(
        branch.conv_state_rows[0],
        inputs.base_conv_state,
        atol=0.0,
        rtol=0.0,
    )
    base_ssm_check = tensor_comparison(
        branch.ssm_state_rows[0],
        inputs.base_ssm_state,
        atol=0.0,
        rtol=0.0,
    )
    commit_check = validate_winning_commits(
        contract, branch, oracle, atol=atol, rtol=rtol
    )

    flat_output = tensor_comparison(
        flattened.outputs, branch.outputs, atol=atol, rtol=rtol
    )
    flat_conv = tensor_comparison(
        flattened.conv_node_states,
        branch.conv_node_states,
        atol=atol,
        rtol=rtol,
    )
    flat_ssm = tensor_comparison(
        flattened.ssm_node_states,
        branch.ssm_node_states,
        atol=atol,
        rtol=rtol,
    )
    is_chain = all(
        parent == node - 1
        for node, parent in enumerate(contract.parents.tolist())
        if node > 0
    )
    flat_all_close = bool(
        flat_output["close"] and flat_conv["close"] and flat_ssm["close"]
    )
    negative_control_passed = flat_all_close if is_chain else not flat_all_close

    native_report: dict[str, Any] | None = None
    native_passed = True
    native_tree_report: dict[str, Any] | None = None
    native_tree_passed = True
    native_oracle: TreeExecution | None = None
    native_oracle_z: torch.Tensor | None = None
    if native_indexed or native_tree_loop:
        native_oracle, native_oracle_z = run_native_independent_paths(
            contract, inputs, config
        )
    if native_indexed:
        native, native_z = run_native_indexed_tree(contract, inputs, config)
        assert native_oracle is not None and native_oracle_z is not None
        native_report, native_passed = compare_native_execution(
            execution="one native indexed op per tree depth",
            contract=contract,
            inputs=inputs,
            config=config,
            native=native,
            native_z=native_z,
            native_oracle=native_oracle,
            native_oracle_z=native_oracle_z,
            math_oracle=oracle,
            atol=atol,
            rtol=rtol,
        )
        if native_timing_samples > 0:
            native_report["timing"] = benchmark_native_indexed_tree(
                contract,
                inputs,
                config,
                warmup=native_timing_warmup,
                samples=native_timing_samples,
                calls_per_sample=native_timing_calls_per_sample,
            )

    if native_tree_loop:
        native_tree, native_tree_z = run_native_tree_loop(contract, inputs, config)
        assert native_oracle is not None and native_oracle_z is not None
        native_tree_report, native_tree_passed = compare_native_execution(
            execution="one graph-static native op for the complete tree",
            contract=contract,
            inputs=inputs,
            config=config,
            native=native_tree,
            native_z=native_tree_z,
            native_oracle=native_oracle,
            native_oracle_z=native_oracle_z,
            math_oracle=oracle,
            atol=atol,
            rtol=rtol,
        )
        if native_timing_samples > 0:
            native_tree_report["timing"] = benchmark_native_tree_loop(
                contract,
                inputs,
                config,
                warmup=native_timing_warmup,
                samples=native_timing_samples,
                calls_per_sample=native_timing_calls_per_sample,
            )

    parity_passed = bool(
        output_check["close"]
        and conv_check["equal"]
        and ssm_check["close"]
        and output_check["finite"]
        and conv_check["finite"]
        and ssm_check["finite"]
    )
    passed = bool(
        parity_passed
        and base_conv_check["equal"]
        and base_ssm_check["equal"]
        and commit_check["passed"]
        and negative_control_passed
        and native_passed
        and native_tree_passed
    )
    return {
        "shape": shape_name,
        "dtype": dtype_name,
        "seed": seed,
        "num_nodes": contract.num_nodes,
        "leaf_count": len(contract.leaves),
        "max_depth": contract.max_depth,
        "branch_vs_independent_paths": {
            "outputs": output_check,
            "conv_states": conv_check,
            "ssm_states": ssm_check,
            "passed": parity_passed,
        },
        "base_row_preserved": {
            "conv": base_conv_check,
            "ssm": base_ssm_check,
            "passed": bool(base_conv_check["equal"] and base_ssm_check["equal"]),
        },
        "winning_path_commits": commit_check,
        "flattened_tree_negative_control": {
            "expected": "match" if is_chain else "diverge",
            "outputs": flat_output,
            "conv_states": flat_conv,
            "ssm_states": flat_ssm,
            "passed": negative_control_passed,
        },
        "native_indexed": native_report,
        "native_tree_loop": native_tree_report,
        "passed": passed,
    }


def resolve_device(requested: str) -> torch.device:
    if requested == "auto":
        requested = (
            "xpu:0" if hasattr(torch, "xpu") and torch.xpu.is_available() else "cpu"
        )
    device = torch.device(requested)
    if device.type == "xpu":
        if not hasattr(torch, "xpu") or not torch.xpu.is_available():
            raise SystemExit("torch.xpu is not available")
        torch.xpu.set_device(device)
    return device


def validate_args(args: argparse.Namespace) -> GDNConfig:
    dimensions = {
        "num-k-heads": args.num_k_heads,
        "num-v-heads": args.num_v_heads,
        "head-k-dim": args.head_k_dim,
        "head-v-dim": args.head_v_dim,
    }
    for name, value in dimensions.items():
        if value <= 0:
            raise SystemExit(f"--{name} must be positive")
    if args.num_v_heads % args.num_k_heads != 0:
        raise SystemExit("--num-v-heads must be divisible by --num-k-heads")
    if (args.native_indexed or args.native_tree_loop) and args.head_k_dim % 32 != 0:
        raise SystemExit(
            "native indexed execution requires --head-k-dim divisible by 32"
        )
    if args.native_timing_samples < 0:
        raise SystemExit("--native-timing-samples must be non-negative")
    if args.native_timing_calls_per_sample <= 0:
        raise SystemExit("--native-timing-calls-per-sample must be positive")
    if args.native_timing_warmup < 0:
        raise SystemExit("--native-timing-warmup must be non-negative")
    if args.native_timing_samples and not (
        args.native_indexed or args.native_tree_loop
    ):
        raise SystemExit(
            "--native-timing-samples requires --native-indexed or --native-tree-loop"
        )
    if args.atol < 0.0 or args.rtol < 0.0:
        raise SystemExit("tolerances must be non-negative")
    return GDNConfig(
        num_k_heads=args.num_k_heads,
        num_v_heads=args.num_v_heads,
        head_k_dim=args.head_k_dim,
        head_v_dim=args.head_v_dim,
    )


def device_metadata(device: torch.device, requested: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "requested": requested,
        "resolved": str(device),
        "type": device.type,
        "torch_version": torch.__version__,
        "xpu_available": bool(hasattr(torch, "xpu") and torch.xpu.is_available()),
    }
    if device.type == "xpu":
        index = device.index if device.index is not None else torch.xpu.current_device()
        metadata["name"] = torch.xpu.get_device_name(index)
        metadata["index"] = int(index)
    return metadata


def main() -> int:
    args = parse_args()
    config = validate_args(args)
    device = resolve_device(args.device)
    if args.native_indexed or args.native_tree_loop:
        if device.type != "xpu":
            raise SystemExit("native indexed execution requires an XPU device")
        kernel_prefix = (
            str(args.kernel_prefix.expanduser().resolve())
            if isinstance(args.kernel_prefix, Path)
            else str(Path(args.kernel_prefix).expanduser().resolve())
        )
        if kernel_prefix not in sys.path:
            sys.path.insert(0, kernel_prefix)
        importlib.import_module("vllm_xpu_kernels._xpu_C")
    dtype_names = _deduplicate(args.dtypes or list(DTYPE_NAMES))
    selected_shapes = _deduplicate(args.shapes or list(tree_shapes().keys()))

    torch.manual_seed(args.seed)
    if device.type == "xpu":
        torch.xpu.manual_seed_all(args.seed)

    contracts: dict[str, PackedTreeContract] = {}
    contract_reports: dict[str, dict[str, Any]] = {}
    for shape_name in selected_shapes:
        contract = build_packed_tree_contract(tree_shapes()[shape_name])
        errors = validate_packed_tree_contract(contract)
        contracts[shape_name] = contract
        contract_reports[shape_name] = {
            **contract.to_json(),
            "validation_errors": errors,
            "passed": not errors,
        }

    cases: list[dict[str, Any]] = []
    for shape_index, shape_name in enumerate(selected_shapes):
        case_seed = args.seed + shape_index * 9973
        for dtype_name in dtype_names:
            cases.append(
                run_case(
                    shape_name=shape_name,
                    contract=contracts[shape_name],
                    dtype_name=dtype_name,
                    config=config,
                    device=device,
                    seed=case_seed,
                    with_conv_bias=args.conv_bias,
                    atol=args.atol,
                    rtol=args.rtol,
                    native_indexed=args.native_indexed,
                    native_tree_loop=args.native_tree_loop,
                    native_timing_samples=args.native_timing_samples,
                    native_timing_calls_per_sample=(
                        args.native_timing_calls_per_sample
                    ),
                    native_timing_warmup=args.native_timing_warmup,
                )
            )

    if device.type == "xpu":
        torch.xpu.synchronize(device)

    result = {
        "schema": SCHEMA,
        "classification": CLASSIFICATION,
        "benchmark": False,
        "device": device_metadata(device, args.device),
        "seed": args.seed,
        "dtypes": dtype_names,
        "shapes": selected_shapes,
        "config": {
            "num_k_heads": config.num_k_heads,
            "num_v_heads": config.num_v_heads,
            "head_k_dim": config.head_k_dim,
            "head_v_dim": config.head_v_dim,
            "width": config.width,
            "conv_state_length": config.width - 1,
            "conv_dim": config.conv_dim,
            "qkvz_dim": config.qkvz_dim,
            "conv_bias": bool(args.conv_bias),
        },
        "tolerances": {"atol": args.atol, "rtol": args.rtol},
        "native_indexed_enabled": bool(args.native_indexed),
        "native_tree_loop_enabled": bool(args.native_tree_loop),
        "expression_contract": {
            "projection_layout": "q,k,v,z and b,a; z is not recurrent",
            "conv_history": "three prior raw qkv rows, oldest to newest",
            "conv_product": (
                "multiply in activation dtype, cast each rounded product to FP32, "
                "accumulate left-to-right from FP32 bias"
            ),
            "conv_activation": "SiLU in FP32, then cast qkv to activation dtype",
            "qk_normalization": "FP32 L2 norm with epsilon 1e-6; q scaled by K^-0.5",
            "gating": "softplus(a+dt_bias), exp(-exp(A_log)*softplus), sigmoid(b) in FP32",
            "recurrence": (
                "decay state; delta=(v-state@k)*beta; state+=outer(delta,k); "
                "output=state@q"
            ),
            "publication": (
                "form output from FP32 next state, then cast/publish state at every node"
            ),
        },
        "packed_tree_contracts": contract_reports,
        "cases": cases,
    }
    result["passed"] = bool(
        all(report["passed"] for report in contract_reports.values())
        and all(case["passed"] for case in cases)
    )

    text = json.dumps(
        result,
        sort_keys=True,
        indent=2 if args.pretty else None,
        allow_nan=False,
    )
    print(text)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
